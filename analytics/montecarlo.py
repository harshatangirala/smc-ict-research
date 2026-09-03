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
