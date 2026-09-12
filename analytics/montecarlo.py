"""Monte Carlo evidence that an observed edge is not a sampling artifact.

Three independent resampling schemes, each answering a different objection:

``monte_carlo_matched_null``
    Re-draws the concept's entry *dates* uniformly at random while holding the
    ticker mix and the per-ticker trade count fixed. This is the simulation
    counterpart of ``analytics.statistics.matched_randomization_test``; running
    both is what licenses using the (far cheaper) analytic version everywhere
    else. ``validate_analytic_null`` checks they agree.

``monte_carlo_trade_shuffle``
    Bootstraps the concept's own realised trade returns to get the sampling
    distribution of the mean. Answers "how much of this mean is luck in which
    trades happened to occur?"

``monte_carlo_block_bootstrap``
    Circular block bootstrap over each ticker's return path, preserving serial
    dependence within blocks. Answers "would a strategy with this trade count
    look this good on a resampled price path?"

``monte_carlo_rotation_null`` / ``rotation_null_exact``
    Shift the signal's whole entry calendar by one offset, the same for every
    ticker. The only scheme here that preserves which trades share a date, and
    so the only one that is not fooled by signals that fire together. The
    exact version enumerates every admissible offset by FFT and is what the
    pipeline reports (``rotation_null_family``); the sampled version is kept
    because its behaviour is easier to read and the tests compare the two.

The three schemes above the rotation draw dates independently per ticker and
are anti-conservative for clustered signals -- see tools/calibration_study.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.config import MONTE_CARLO_RUNS, RANDOM_SEED
from utils.logging_config import get_logger
from utils.rng import get_rng

log = get_logger("analytics.montecarlo")


def _forward_returns(close: np.ndarray, h: int) -> np.ndarray:
    if len(close) <= h:
        return np.array([], dtype=float)
    fwd = close[h:] / close[:-h] - 1.0
    return fwd[np.isfinite(fwd)]


def monte_carlo_matched_null(
    counts_by_ticker: dict[str, int],
    prices: dict[str, pd.DataFrame],
    holding_period: int,
    direction: int,
    observed_mean: float,
    n_runs: int = MONTE_CARLO_RUNS,
    seed: int = RANDOM_SEED,
    label: str = "mc_matched",
) -> dict:
    """Empirical null for the pooled mean under composition-matched random entry.

    Draws, for each ticker, ``n_t`` entry dates uniformly without replacement
    from that ticker's eligible bars, ``n_runs`` times.
    """
    rng = get_rng(label, master_seed=seed)

    pools = {}
    for ticker, n_t in counts_by_ticker.items():
        df = prices.get(ticker)
        if df is None:
            continue
        fwd = _forward_returns(df["close"].to_numpy(dtype=float), holding_period)
        if len(fwd) >= 2 and n_t > 0:
            pools[ticker] = (fwd, int(min(n_t, len(fwd))))
    if not pools:
        return {"p_value": np.nan, "null_mean": np.nan, "null_se": np.nan, "n_runs": 0}

    total = sum(n for _, n in pools.values())
    sims = np.empty(n_runs, dtype=float)
    for b in range(n_runs):
        acc = 0.0
        for fwd, n_t in pools.values():
            # WITHOUT replacement -- this is the actual null sampling design
            # (a set of distinct entry dates), and it is what the analytic
            # finite-population-corrected variance in
            # statistics.matched_randomization_test assumes. Sampling with
            # replacement here would inflate the simulated SE by 1/sqrt(FPC)
            # and the two would not be comparable.
            idx = rng.choice(len(fwd), size=n_t, replace=False)
            acc += direction * fwd[idx].sum()
        sims[b] = acc / total

    # +1 numerator/denominator: never report p = 0 from a finite simulation.
    p = float((np.sum(sims >= observed_mean) + 1) / (n_runs + 1))
    return {
        "p_value": p,
        "null_mean": float(sims.mean()),
        "null_se": float(sims.std(ddof=1)),
        "observed_mean": float(observed_mean),
        "n_runs": int(n_runs),
        "n_matched": int(total),
    }


def validate_analytic_null(
    counts_by_ticker: dict[str, int],
    prices: dict[str, pd.DataFrame],
    holding_period: int,
    direction: int,
    n_runs: int = 2_000,
    label: str = "mc_validate",
) -> dict:
    """Check the analytic matched-null moments against simulation.

    The analytic test is used for every concept because simulating each one is
    expensive; this function is the evidence that shortcut is sound.
    """
    from analytics.statistics import build_return_pools, matched_randomization_test

    pools = build_return_pools(prices, [holding_period])
    analytic = matched_randomization_test(
        counts_by_ticker, 0.0, direction, pools, holding_period
    )
    sim = monte_carlo_matched_null(
        counts_by_ticker, prices, holding_period, direction,
        observed_mean=0.0, n_runs=n_runs, label=label,
    )
    return {
        "analytic_null_mean": analytic["null_mean"],
        "simulated_null_mean": sim["null_mean"],
        "analytic_null_se": analytic["null_se"],
        "simulated_null_se": sim["null_se"],
        "mean_abs_diff": abs(analytic["null_mean"] - sim["null_mean"]),
        "se_ratio": (
            sim["null_se"] / analytic["null_se"]
            if analytic["null_se"] and np.isfinite(analytic["null_se"]) and analytic["null_se"] > 0
            else np.nan
        ),
    }


def monte_carlo_trade_shuffle(
    returns: np.ndarray,
    n_runs: int = MONTE_CARLO_RUNS,
    seed: int = RANDOM_SEED,
    label: str = "mc_shuffle",
) -> dict:
    """Bootstrap distribution of the mean of a concept's realised trades."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 5:
        return {"mean": np.nan, "ci_lower": np.nan, "ci_upper": np.nan,
                "p_value_ge_zero": np.nan, "n_runs": 0}
    rng = get_rng(label, master_seed=seed)
    n = len(r)
    cap = min(n, 20_000)
    if n > cap:
        r = rng.choice(r, size=cap, replace=False)
        n = cap
    sims = np.empty(n_runs, dtype=float)
    chunk = max(1, int(5_000_000 / max(n, 1)) or 1)
    done = 0
    while done < n_runs:
        k = min(chunk, n_runs - done)
        sims[done : done + k] = r[rng.integers(0, n, size=(k, n))].mean(axis=1)
        done += k
    return {
        "mean": float(r.mean()),
        "ci_lower": float(np.percentile(sims, 2.5)),
        "ci_upper": float(np.percentile(sims, 97.5)),
        "p_value_ge_zero": float((np.sum(sims <= 0) + 1) / (n_runs + 1)),
        "n_runs": int(n_runs),
    }


def monte_carlo_block_bootstrap(
    prices: dict[str, pd.DataFrame],
    counts_by_ticker: dict[str, int],
    holding_period: int,
    direction: int,
    observed_mean: float,
    block_size: int = 21,
    n_runs: int = MONTE_CARLO_RUNS,
    seed: int = RANDOM_SEED,
    label: str = "mc_block",
) -> dict:
    """Circular block bootstrap of each ticker's forward-return path.

    Resampling in blocks preserves short-horizon serial dependence that an iid
    bootstrap destroys, so the null is a fairer opponent for a strategy whose
    trades cluster in time.
    """
    rng = get_rng(label, master_seed=seed)
    pools = {}
    for ticker, n_t in counts_by_ticker.items():
        df = prices.get(ticker)
        if df is None:
            continue
        fwd = _forward_returns(df["close"].to_numpy(dtype=float), holding_period)
        if len(fwd) > block_size and n_t > 0:
            pools[ticker] = (fwd, int(n_t))
    if not pools:
        return {"p_value": np.nan, "null_mean": np.nan, "n_runs": 0}

    total = sum(n for _, n in pools.values())
    sims = np.empty(n_runs, dtype=float)
    for b in range(n_runs):
        acc = 0.0
        for fwd, n_t in pools.values():
            n_blocks = int(np.ceil(n_t / block_size))
            starts = rng.integers(0, len(fwd), size=n_blocks)
            offsets = np.arange(block_size)
            idx = (starts[:, None] + offsets[None, :]).ravel() % len(fwd)
            acc += direction * fwd[idx[:n_t]].sum()
        sims[b] = acc / total
    return {
        "p_value": float((np.sum(sims >= observed_mean) + 1) / (n_runs + 1)),
        "null_mean": float(sims.mean()),
        "null_se": float(sims.std(ddof=1)),
        "observed_mean": float(observed_mean),
        "n_runs": int(n_runs),
    }


def monte_carlo_rotation_null(
    trades: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    holding_period: int,
    n_runs: int = MONTE_CARLO_RUNS,
    seed: int = RANDOM_SEED,
    label: str = "mc_rotation",
) -> dict:
    """Randomization null that PRESERVES cross-sectional clustering.

    Shifts the signal's whole entry calendar by one random offset -- the same
    offset for every ticker, wrapping circularly -- and re-reads each trade's
    h-day forward return at the shifted date. That keeps the ticker mix, the
    per-ticker counts, the spacing of entries within each ticker and, crucially,
    which trades share a date.

    ``monte_carlo_matched_null`` and ``monte_carlo_block_bootstrap`` draw dates
    independently per ticker, which destroys that clustering; like the analytic
    SRS variance they were built to validate, they are anti-conservative for
    signals that fire together. This is the primary Monte Carlo scheme.
    """
    rng = get_rng(label, master_seed=seed)
    tickers = sorted(set(trades["ticker"]) & set(prices))
    h = int(holding_period)
    empty = {"p_value": np.nan, "null_mean": np.nan, "null_se": np.nan,
             "observed_mean": np.nan, "n_runs": 0, "n_trades": 0}
    if not tickers:
        return empty
    cal = pd.DatetimeIndex(sorted(set().union(*(prices[t].index for t in tickers))))
    T = len(cal)
    if T <= 2 * h + 4:
        return empty
    F = np.full((len(tickers), T), np.nan)
    for k, t in enumerate(tickers):
        c = prices[t]["close"].to_numpy(dtype=float)
        if len(c) <= h:
            continue
        F[k, cal.get_indexer(prices[t].index[:-h])] = c[h:] / c[:-h] - 1.0
    sub = trades[trades["ticker"].isin(tickers)]
    kidx = sub["ticker"].map({t: i for i, t in enumerate(tickers)}).to_numpy()
    pos = cal.get_indexer(pd.to_datetime(sub["date"]))
    ok = pos >= 0
    kidx, pos = kidx[ok], pos[ok]
    d = sub["direction"].to_numpy(dtype=float)[ok]
    observed = float(np.nanmean(d * F[kidx, pos]))
    sims = np.empty(n_runs, dtype=float)
    for b in range(n_runs):
        off = int(rng.integers(h + 1, T - h - 1))
        sims[b] = np.nanmean(d * F[kidx, (pos + off) % T])
    return {
        "p_value": float((np.sum(sims >= observed) + 1) / (n_runs + 1)),
        "null_mean": float(np.nanmean(sims)),
        "null_se": float(np.nanstd(sims, ddof=1)),
        "observed_mean": observed,
        "n_runs": int(n_runs),
        "n_trades": int(ok.sum()),
    }


def rotation_matrix(
    prices: dict[str, pd.DataFrame],
    holding_period: int,
    tickers: list[str] | None = None,
) -> tuple[list[str], pd.DatetimeIndex, np.ndarray]:
    """h-day forward returns on the union trading calendar, NaN where absent.

    One matrix serves every signal at a horizon, so the exact rotation null can
    run a whole family of hypotheses without rebuilding it.
    """
    tickers = sorted(prices) if tickers is None else sorted(tickers)
    h = int(holding_period)
    cal = pd.DatetimeIndex(sorted(set().union(*(prices[t].index for t in tickers))))
    F = np.full((len(tickers), len(cal)), np.nan)
    for k, t in enumerate(tickers):
        c = prices[t]["close"].to_numpy(dtype=float)
        if len(c) <= h:
            continue
        F[k, cal.get_indexer(prices[t].index[:-h])] = c[h:] / c[:-h] - 1.0
    return tickers, cal, F


def rotation_null_exact(
    trades: pd.DataFrame,
    holding_period: int,
    prices: dict[str, pd.DataFrame] | None = None,
    matrix: tuple | None = None,
) -> dict:
    """Rotation null over EVERY admissible offset, not a random sample of them.

    Why not the sampled version
    ---------------------------
    With 1,000 sampled offsets the smallest attainable p-value is 1/1001. A
    Benjamini-Hochberg threshold over the study's 352 hypotheses starts at
    0.05/352 = 0.00014, so a sampled rotation test cannot clear FDR on its own
    however strong the signal. Enumerating all offsets lowers the floor to
    about 1/(T - 2h - 1) and removes the seed from the result.

    How
    ---
    The rotated mean at offset ``o`` is ``num(o) / den(o)`` with

        num(o) = sum_k sum_p W_k[p] G_k[(p + o) mod T]
        den(o) = sum_k sum_p C_k[p] V_k[(p + o) mod T]

    where ``W_k``/``C_k`` are ticker k's direction-weighted and plain trade
    counts by date, ``G_k`` its forward returns with NaN set to 0, and ``V_k``
    the availability mask. Both are circular cross-correlations, so the FFT
    gives them for every ``o`` at once. The statistic is exactly the sampled
    version's ``nanmean`` over rotated trades (checked in the tests); the
    admissible offsets are the same ``h+1 .. T-h-2``.
    """
    h = int(holding_period)
    if matrix is None:
        if prices is None:
            raise ValueError("pass either prices or a prebuilt matrix")
        matrix = rotation_matrix(prices, h, sorted(set(trades["ticker"]) & set(prices)))
    tickers, cal, F = matrix
    T = len(cal)
    empty = {"p_value": np.nan, "p_value_less": np.nan, "null_mean": np.nan,
             "null_se": np.nan, "observed_mean": np.nan, "excess_vs_rotation": np.nan,
             "n_offsets": 0, "n_trades": 0}
    index = {t: i for i, t in enumerate(tickers)}
    sub = trades[trades["ticker"].isin(index)]
    if sub.empty or T <= 2 * h + 4:
        return empty
    kidx = sub["ticker"].map(index).to_numpy()
    pos = cal.get_indexer(pd.to_datetime(sub["date"]))
    ok = pos >= 0
    if not ok.any():
        return empty
    kidx, pos = kidx[ok], pos[ok]
    d = sub["direction"].to_numpy(dtype=float)[ok]
    observed = float(np.nanmean(d * F[kidx, pos]))

    rows, local = np.unique(kidx, return_inverse=True)
    W = np.zeros((len(rows), T))
    C = np.zeros((len(rows), T))
    np.add.at(W, (local, pos), d)
    np.add.at(C, (local, pos), 1.0)
    Fr = F[rows]
    V = np.isfinite(Fr)
    G = np.where(V, Fr, 0.0)
    num = np.fft.irfft(
        (np.conj(np.fft.rfft(W, axis=1)) * np.fft.rfft(G, axis=1)).sum(axis=0), n=T)
    den = np.rint(np.fft.irfft(
        (np.conj(np.fft.rfft(C, axis=1)) * np.fft.rfft(V.astype(float), axis=1)).sum(axis=0), n=T))
    offs = np.arange(h + 1, T - h - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sims = num[offs] / den[offs]
    sims = sims[np.isfinite(sims)]
    if sims.size < 2 or not np.isfinite(observed):
        return empty
    # FFT round-off is ~1e-15; near-ties are counted against the signal.
    tol = 1e-12 * max(1.0, abs(observed))
    n = sims.size
    null_mean = float(sims.mean())
    return {
        "p_value": float((1 + np.sum(sims >= observed - tol)) / (n + 1)),
        "p_value_less": float((1 + np.sum(sims <= observed + tol)) / (n + 1)),
        "null_mean": null_mean,
        "null_se": float(sims.std(ddof=1)),
        "observed_mean": observed,
        "excess_vs_rotation": observed - null_mean,
        "n_offsets": int(n),
        "n_trades": int(ok.sum()),
    }


def rotation_null_family(
    trades: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Exact rotation test for every (signal, horizon) hypothesis, BH-FDR across all.

    The study's secondary test. tools/calibration_study.py finds it right-sized
    for random entry timing on real prices, where the primary calendar-time
    test is conservative; it conditions on the realised path, though, and
    over-rejects when entries concentrate in volatile periods (the simulated
    vol-timed design). Survivors here that fail the primary test are reported
    as such, not as evidence of edge.
    """
    from analytics.statistics import apply_fdr_correction
    from utils.config import FDR_ALPHA, MIN_SAMPLE_SIZE

    if horizons is None:
        horizons = sorted(int(h) for h in trades["holding_period"].unique())
    rows = []
    for h in horizons:
        sub = trades[trades["holding_period"] == h]
        if sub.empty:
            continue
        matrix = rotation_matrix(prices, h)
        for sig, grp in sub.groupby("signal", sort=True):
            r = rotation_null_exact(grp, h, matrix=matrix)
            rows.append({"signal": sig, "holding_period": int(h),
                         "direction": int(grp["direction"].iloc[0]), **r})
        log.info("Exact rotation null done at h=%d (%d signals)", h, sub["signal"].nunique())
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    enough = out["n_trades"] >= MIN_SAMPLE_SIZE
    fdr = apply_fdr_correction(out["p_value"], alpha=FDR_ALPHA)
    out["p_adj"] = fdr["p_adjusted"]
    out["reject"] = fdr["reject_null"].fillna(False).astype(bool)
    out["beats_rotation_null"] = out["reject"] & (out["excess_vs_rotation"] > 0) & enough
    # Descriptive two-sided family: does anything reliably LOSE to its null?
    out["p_value_two_sided"] = np.minimum(1.0, 2.0 * np.minimum(out["p_value"], out["p_value_less"]))
    fdr2 = apply_fdr_correction(out["p_value_two_sided"], alpha=FDR_ALPHA)
    out["p_adj_two_sided"] = fdr2["p_adjusted"]
    out["loses_to_rotation_null"] = (
        fdr2["reject_null"].fillna(False).astype(bool) & (out["excess_vs_rotation"] < 0) & enough
    )
    return out
