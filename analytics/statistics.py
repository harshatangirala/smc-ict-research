"""Statistical Research Engine: bootstrap confidence intervals, significance
tests, effect sizes, and false-discovery-rate correction.

What changed and why
--------------------
Three defects in the original module produced the study's headline numbers:

1. **The significance flag was sign-blind.** ``significant_vs_baseline`` came
   from a two-sided Welch t-test, so a concept whose mean return was
   significantly *worse* than random entry received the same flag as one that
   was significantly better. In the published `concept_rankings.csv`, 27 of the
   28 concepts flagged "significant vs baseline" had a *negative*
   ``effect_size_vs_baseline`` -- they lost to random entry. The report then
   listed them under "Signals that beat the random-entry baseline". Tests here
   are one-sided by default, with the direction stated.

2. **The comparison was not composition-matched.** A concept's trades and the
   baseline's trades were drawn from different mixes of tickers, and mean
   returns differ enormously across tickers over 2010-2026. Pooling both and
   running Welch's test therefore measured ticker mix as much as signal
   quality. ``matched_randomization_test`` fixes the mix exactly.

3. **Overlapping returns were treated as independent.** h-day forward returns
   computed on consecutive bars share h-1 days of price path, so the effective
   sample size is far below the nominal trade count. The iid t-test p-values
   were correspondingly tiny (many reported as exactly 0.0).
   ``hac_mean_test`` uses Newey-West standard errors instead.

4. **The first matched-null test was anti-conservative for clustered
   signals.** ``matched_randomization_test`` derives its variance from entry
   dates drawn independently at random. Real signals fire together: a
   market-wide move triggers the same pattern on many tickers on one day, so
   their trades share a single market outcome. Simulating uninformative
   signals on real prices (``tools/calibration_study.py``), it rejects at 28%
   when tickers draw from a shared pool of dates and 40% when all fire on the
   same dates, at a nominal 5%. ``matched_excess_calendar_test`` -- the
   per-trade excess over the same benchmark, with calendar-time Newey-West
   inference -- is calibrated in those designs and is now the primary test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from utils.config import (
    BOOTSTRAP_ITERATIONS,
    FDR_ALPHA,
    HAC_MAX_LAG_MULTIPLIER,
    RANDOM_SEED,
)
from utils.rng import get_rng

#: Above this many observations a single reproducible subsample is bootstrapped
#: instead of the full array. Bootstrap CI width is governed by the resample
#: size, so this is a performance measure, not a validity shortcut.
MAX_BOOTSTRAP_SAMPLE = 20_000


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def bootstrap_mean_ci(
    returns: np.ndarray,
    n_iter: int = BOOTSTRAP_ITERATIONS,
    alpha: float = 0.05,
    seed: int = RANDOM_SEED,
    label: str = "bootstrap",
) -> tuple[float, float, float]:
    """Percentile-bootstrap CI for the mean.

    Vectorised: the original drew ``n_iter`` samples in a Python loop, which
    at the new 10,000-iteration budget would have dominated total runtime.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 5:
        return (np.nan, np.nan, np.nan)

    rng = get_rng(label, master_seed=seed)
    if len(r) > MAX_BOOTSTRAP_SAMPLE:
        r = rng.choice(r, size=MAX_BOOTSTRAP_SAMPLE, replace=False)

    n = len(r)
    # Chunked to bound peak memory at ~40 MB regardless of n_iter x n.
    chunk = max(1, min(n_iter, int(5_000_000 / max(n, 1)) or 1))
    means = np.empty(n_iter, dtype=float)
    done = 0
    while done < n_iter:
        k = min(chunk, n_iter - done)
        idx = rng.integers(0, n, size=(k, n))
        means[done : done + k] = r[idx].mean(axis=1)
        done += k

    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return (float(r.mean()), lo, hi)


def bootstrap_mean_and_d(
    returns: np.ndarray,
    n_iter: int = BOOTSTRAP_ITERATIONS,
    alpha: float = 0.05,
    seed: int = RANDOM_SEED,
    label: str = "bootstrap",
) -> dict:
    """Bootstrap a CI for the mean and Cohen's d, from one resample matrix.

    Both statistics are closed-form functions of the resample's mean and
    standard deviation, so they are computed vectorised over the whole chunk.
    An earlier draft routed Cohen's d through ``np.apply_along_axis``, which
    is a Python-level loop over rows -- at 10,000 iterations x 368 buckets
    that alone would have dominated the run.

    For samples larger than ``MAX_BOOTSTRAP_SAMPLE`` the *resampling* runs on
    one reproducible subsample, so the interval is the CI for a mean of
    ``MAX_BOOTSTRAP_SAMPLE`` observations and is therefore *wider* than the CI
    for the full sample -- conservative, not anti-conservative. The *point
    estimates* (``mean``, ``cohens_d``) are always computed on the full array
    regardless of ``n_iter``'s subsampling, so they agree exactly with
    ``avg_return``/``effect_size_vs_baseline`` computed elsewhere and are never
    themselves subject to resampling noise -- only the interval around them
    is. (An earlier version returned the subsample's own mean as the point
    estimate too; for large concepts that silently differed from the
    documented population mean by up to ~1 bp, a real but purely cosmetic
    inaccuracy in `statistics_master.csv` since no downstream inference used
    it -- `excess_return_vs_matched_random` and every p-value already read the
    full array directly.) ``ci_method`` records which path the *interval*
    took, and the HAC interval (``hac_ci_lower``/``hac_ci_upper``), centred on
    the same full-sample point estimate, is the one used for inference, since
    an iid bootstrap is not valid for overlapping returns in any case.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    out = {
        "mean": np.nan, "ci_lower": np.nan, "ci_upper": np.nan,
        "cohens_d": np.nan, "cohens_d_ci_lower": np.nan, "cohens_d_ci_upper": np.nan,
        "ci_method": "insufficient_data", "n_bootstrap_iter": 0,
    }
    if len(r) < 5:
        return out

    full_mean = float(r.mean())
    full_sd = r.std(ddof=1)
    full_cohens_d = full_mean / full_sd if full_sd > 0 else np.nan

    rng = get_rng(label, master_seed=seed)
    full_n = len(r)
    subsampled = full_n > MAX_BOOTSTRAP_SAMPLE
    r_resample = rng.choice(r, size=MAX_BOOTSTRAP_SAMPLE, replace=False) if subsampled else r
    n = len(r_resample)

    means = np.empty(n_iter, dtype=float)
    ds = np.empty(n_iter, dtype=float)
    chunk = max(1, min(n_iter, int(5_000_000 / max(n, 1)) or 1))
    done = 0
    while done < n_iter:
        k = min(chunk, n_iter - done)
        sample = r_resample[rng.integers(0, n, size=(k, n))]
        m = sample.mean(axis=1)
        sd = sample.std(axis=1, ddof=1)
        means[done : done + k] = m
        with np.errstate(divide="ignore", invalid="ignore"):
            ds[done : done + k] = np.where(sd > 0, m / sd, np.nan)
        done += k

    lo_q, hi_q = 100 * alpha / 2, 100 * (1 - alpha / 2)
    # Percentile intervals are re-centred on the full-sample point estimate:
    # a resample-based interval is naturally centred near the resample's own
    # mean, which for a subsample can differ slightly from the population
    # mean it is meant to bracket. Shifting by the (small) subsample bias
    # keeps the interval a CI *for the reported point estimate*, not for a
    # different, unreported one.
    mean_shift = full_mean - float(means.mean()) if subsampled else 0.0
    d_shift = full_cohens_d - float(np.nanmean(ds)) if subsampled and np.isfinite(full_cohens_d) else 0.0
    out.update(
        {
            "mean": full_mean,
            "ci_lower": float(np.percentile(means, lo_q)) + mean_shift,
            "ci_upper": float(np.percentile(means, hi_q)) + mean_shift,
            "cohens_d": full_cohens_d,
            "cohens_d_ci_lower": float(np.nanpercentile(ds, lo_q)) + d_shift,
            "cohens_d_ci_upper": float(np.nanpercentile(ds, hi_q)) + d_shift,
            "ci_method": f"percentile_bootstrap_subsample_{n}_recentred" if subsampled
                         else "percentile_bootstrap_full",
            "n_bootstrap_iter": int(n_iter),
        }
    )
    return out


# ---------------------------------------------------------------------------
# Overlapping-sample inference
# ---------------------------------------------------------------------------
def newey_west_se(x: np.ndarray, max_lag: int) -> float:
    """Newey-West HAC standard error of the sample mean.

    h-day forward returns on consecutive bars overlap by h-1 days, inducing
    strong positive autocorrelation. Ignoring it (as a plain t-test does)
    understates the standard error by roughly sqrt(h) and turns ordinary
    noise into astronomically small p-values.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.nan
    dev = x - x.mean()
    gamma0 = float(dev @ dev) / n
    total = gamma0
    max_lag = int(min(max_lag, n - 1))
    for lag in range(1, max_lag + 1):
        cov = float(dev[lag:] @ dev[:-lag]) / n
        weight = 1.0 - lag / (max_lag + 1.0)  # Bartlett kernel
        total += 2.0 * weight * cov
    total = max(total, 1e-24)
    return float(np.sqrt(total / n))


def calendar_time_mean_test(
    trades: pd.DataFrame,
    holding_period: int,
    return_col: str = "fwd_return",
    date_col: str = "date",
    alternative: str = "two-sided",
) -> dict:
    """HAC test for the mean of a *panel* of overlapping trades.

    Why not plain Newey-West on the pooled array
    --------------------------------------------
    A concept's trade table is a panel: hundreds of tickers x thousands of
    dates, concatenated ticker-by-ticker. Two distinct dependence structures
    make the iid t-test invalid, and neither is addressed by running
    Newey-West over the pooled array (whose row order is an artifact of the
    concatenation, not time):

    * **Cross-sectional.** Trades entered on the same day across 500 names
      share the market factor; on a big up day nearly every long trade wins
      together. The effective number of independent observations is closer to
      the number of *dates* than the number of trades.
    * **Serial.** h-day forward returns started on consecutive days overlap by
      h-1 days of price path.

    Estimator
    ---------
    Collapse to calendar time, then apply Newey-West to the date series --
    the standard calendar-time-portfolio treatment. With ``n_d`` trades on
    date ``d`` and date mean ``rbar_d``, the pooled mean is
    ``mu = sum_d n_d rbar_d / N``. Writing ``x_d = n_d (rbar_d - mu) / N`` so
    that ``mu - E[mu] = sum_d x_d``, the HAC variance of that sum is

        S = sum_d x_d^2 + 2 sum_{lag=1..L} w_lag sum_d x_d x_{d-lag}

    with Bartlett weights ``w_lag = 1 - lag/(L+1)`` and ``L = h``. Dates with
    no trades enter as ``x_d = 0``, which is correct: they contribute nothing
    to the sum but do separate lags properly.
    """
    if trades.empty:
        return {"mean": np.nan, "hac_se": np.nan, "t_stat": np.nan, "p_value": np.nan,
                "n": 0, "n_dates": 0}

    df = trades[[date_col, return_col]].dropna()
    if len(df) < 5:
        return {"mean": np.nan, "hac_se": np.nan, "t_stat": np.nan, "p_value": np.nan,
                "n": len(df), "n_dates": 0}

    grp = df.groupby(date_col)[return_col].agg(["sum", "count"]).sort_index()
    n_total = float(grp["count"].sum())
    mu = float(grp["sum"].sum() / n_total)

    # Reindex onto a BUSINESS-day grid so a lag of h means h trading days.
    # A calendar-day grid (the first version) pads weekends with zeros and
    # shrinks the effective bandwidth to roughly 5h/7 trading days. Any
    # non-business date that does carry trades is kept by the union.
    full_idx = pd.bdate_range(grp.index.min(), grp.index.max()).union(grp.index)
    counts = grp["count"].reindex(full_idx, fill_value=0).to_numpy(dtype=float)
    sums = grp["sum"].reindex(full_idx, fill_value=0.0).to_numpy(dtype=float)
    x = (sums - counts * mu) / n_total

    max_lag = int(max(1, HAC_MAX_LAG_MULTIPLIER * int(holding_period)))
    max_lag = min(max_lag, len(x) - 1)
    total = float(x @ x)
    for lag in range(1, max_lag + 1):
        cov = float(x[lag:] @ x[:-lag])
        total += 2.0 * (1.0 - lag / (max_lag + 1.0)) * cov
    if total <= 0:
        return {"mean": mu, "hac_se": np.nan, "t_stat": np.nan, "p_value": np.nan,
                "n": int(n_total), "n_dates": int((counts > 0).sum())}

    se = float(np.sqrt(total))
    t = mu / se
    if alternative == "greater":
        pv = float(stats.norm.sf(t))
    elif alternative == "less":
        pv = float(stats.norm.cdf(t))
    else:
        pv = float(2 * stats.norm.sf(abs(t)))
    return {
        "mean": mu,
        "hac_se": se,
        "t_stat": float(t),
        "p_value": pv,
        "n": int(n_total),
        "n_dates": int((counts > 0).sum()),
    }


def hac_mean_test(
    returns: np.ndarray, holding_period: int = 1, alternative: str = "two-sided"
) -> dict:
    """Test mean(returns) == 0 using Newey-West HAC standard errors."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 5:
        return {"mean": np.nan, "hac_se": np.nan, "t_stat": np.nan, "p_value": np.nan, "n": n}
    lag = max(1, HAC_MAX_LAG_MULTIPLIER * int(holding_period))
    se = newey_west_se(r, lag)
    if not np.isfinite(se) or se <= 0:
        return {"mean": float(r.mean()), "hac_se": np.nan, "t_stat": np.nan, "p_value": np.nan, "n": n}
    t = float(r.mean() / se)
    if alternative == "greater":
        p = float(stats.norm.sf(t))
    elif alternative == "less":
        p = float(stats.norm.cdf(t))
    else:
        p = float(2 * stats.norm.sf(abs(t)))
    return {"mean": float(r.mean()), "hac_se": se, "t_stat": t, "p_value": p, "n": n}


def one_sample_significance(returns: np.ndarray, holding_period: int = 1) -> dict:
    """Is the mean forward return different from zero?

    Reports both the naive iid t-test (for comparability with the original
    results) and the HAC test that should be used for inference.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 5:
        return {
            "t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan,
            "n": len(r), "p_value_iid": np.nan, "hac_se": np.nan,
        }
    t_iid, p_iid = stats.ttest_1samp(r, 0.0)
    sd = r.std(ddof=1)
    hac = hac_mean_test(r, holding_period)
    return {
        "t_stat": hac["t_stat"],
        "p_value": hac["p_value"],          # HAC-corrected -- used for inference
        "p_value_iid": float(p_iid),        # naive, retained for comparison
        "hac_se": hac["hac_se"],
        "effect_size_cohens_d": float(r.mean() / sd) if sd > 0 else np.nan,
        "n": len(r),
    }


def two_sample_significance(
    signal_returns: np.ndarray,
    baseline_returns: np.ndarray,
    alternative: str = "greater",
) -> dict:
    """Welch's t-test, ONE-SIDED by default: is the signal *better* than the baseline?

    ``alternative='greater'`` is the hypothesis the study actually asks. The
    original used the SciPy default (two-sided), which is why concepts that
    significantly underperformed random entry were flagged as significant.
    """
    a = np.asarray(signal_returns, dtype=float)
    a = a[np.isfinite(a)]
    b = np.asarray(baseline_returns, dtype=float)
    b = b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return {
            "t_stat": np.nan, "p_value": np.nan, "p_value_two_sided": np.nan,
            "effect_size_cohens_d": np.nan, "mean_diff": np.nan,
        }
    t_stat, p_two = stats.ttest_ind(a, b, equal_var=False)
    if alternative == "greater":
        p = p_two / 2 if t_stat > 0 else 1 - p_two / 2
    elif alternative == "less":
        p = p_two / 2 if t_stat < 0 else 1 - p_two / 2
    else:
        p = p_two
    pooled_std = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    d = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else np.nan
    return {
        "t_stat": float(t_stat),
        "p_value": float(p),
        "p_value_two_sided": float(p_two),
        "effect_size_cohens_d": float(d),
        "mean_diff": float(a.mean() - b.mean()),
    }


# ---------------------------------------------------------------------------
# Matched randomization test (the primary "beats chance" test)
# ---------------------------------------------------------------------------
def build_return_pools(
    prices: dict[str, pd.DataFrame], horizons: list[int]
) -> dict[tuple[str, int], tuple[int, float, float]]:
    """Per-(ticker, horizon) pool of every available forward return.

    Returns ``{(ticker, h): (N, mean, var)}`` for the *long* direction; a short
    signal's null mean is the negation (the variance is unchanged).
    """
    pools: dict[tuple[str, int], tuple[int, float, float]] = {}
    for ticker, df in prices.items():
        close = df["close"].to_numpy(dtype=float)
        n = len(close)
        for h in horizons:
            if n <= h + 1:
                continue
            fwd = close[h:] / close[:-h] - 1.0
            fwd = fwd[np.isfinite(fwd)]
            if len(fwd) < 2:
                continue
            pools[(ticker, h)] = (len(fwd), float(fwd.mean()), float(fwd.var(ddof=1)))
    return pools


def matched_randomization_test(
    counts_by_ticker: dict[str, int],
    observed_mean: float,
    direction: int,
    pools: dict[tuple[str, int], tuple[int, float, float]],
    holding_period: int,
    alternative: str = "greater",
) -> dict:
    """Design-based test: could this mean arise from entering the SAME tickers
    the SAME number of times, on randomly chosen dates?

    Under the null the entry dates are a uniform random subset of each ticker's
    bars. Sampling ``n_t`` of ``N_t`` bars without replacement gives a sample
    mean with variance ``(sigma_t^2 / n_t) * (N_t - n_t) / (N_t - 1)``
    (finite-population correction), so for the pooled mean

        E[mean]   = sum_t n_t * mu_t / n
        Var[mean] = sum_t n_t * sigma_t^2 * (N_t - n_t)/(N_t - 1) / n^2

    with ``mu_t`` negated for short signals. This is exact under the sampling
    design: it assumes nothing about how returns are distributed or correlated
    in time, only that the null entry dates are drawn uniformly. It removes the
    ticker-composition confound that made the original pooled Welch comparison
    uninterpretable.
    """
    num_mean = 0.0
    num_var = 0.0
    n_total = 0
    n_tickers_matched = 0
    for ticker, n_t in counts_by_ticker.items():
        key = (ticker, holding_period)
        if key not in pools or n_t <= 0:
            continue
        big_n, mu, var = pools[key]
        n_t = int(min(n_t, big_n))
        if big_n < 2 or n_t < 1:
            continue
        fpc = (big_n - n_t) / (big_n - 1) if big_n > 1 else 0.0
        num_mean += n_t * (direction * mu)
        num_var += n_t * var * fpc
        n_total += n_t
        n_tickers_matched += 1

    if n_total == 0:
        return {
            "null_mean": np.nan, "null_se": np.nan, "z_stat": np.nan,
            "p_value": np.nan, "excess_return": np.nan, "n_matched": 0,
            "n_tickers": 0,
        }

    null_mean = num_mean / n_total
    null_se = float(np.sqrt(num_var) / n_total) if num_var > 0 else np.nan
    excess = observed_mean - null_mean
    if not np.isfinite(null_se) or null_se <= 0:
        return {
            "null_mean": null_mean, "null_se": null_se, "z_stat": np.nan,
            "p_value": np.nan, "excess_return": excess, "n_matched": n_total,
            "n_tickers": n_tickers_matched,
        }
    z = excess / null_se
    if alternative == "greater":
        p = float(stats.norm.sf(z))
    elif alternative == "less":
        p = float(stats.norm.cdf(z))
    else:
        p = float(2 * stats.norm.sf(abs(z)))
    return {
        "null_mean": float(null_mean),
        "null_se": float(null_se),
        "z_stat": float(z),
        "p_value": p,
        "excess_return": float(excess),
        "n_matched": int(n_total),
        "n_tickers": int(n_tickers_matched),
    }


def matched_excess_calendar_test(
    subset: pd.DataFrame,
    pools: dict[tuple[str, int], tuple[int, float, float]],
    holding_period: int,
    direction: int | None,
    alternative: str = "greater",
) -> dict:
    """Primary test: calendar-time Newey-West on per-trade excess over the matched null.

    Each trade is measured against its own ticker's unconditional mean h-day
    forward return, signed by direction -- the same composition-matched
    benchmark as ``matched_randomization_test``, so the point estimate is
    identical. Inference collapses the per-trade excess to calendar time and
    applies Newey-West: the calendar-time abnormal-return test of the
    event-study literature (Fama 1998; Lyon, Barber and Tsai 1999).

    It replaces the simple-random-sampling variance because real signals cluster
    in time; see the module docstring, item 4. ``direction=None`` reads each
    trade's own direction, which lets a mixed long/short population (a sector,
    say) be tested in one pass with the same-day covariance between its long and
    short legs counted rather than assumed away.
    """
    mu = subset["ticker"].map(
        {t: pools[(t, holding_period)][1] for t in subset["ticker"].unique()
         if (t, holding_period) in pools}
    )
    d = subset["direction"] if direction is None else direction
    sub_ = subset.assign(_excess=subset["fwd_return"] - d * mu).dropna(subset=["_excess"])
    if sub_.empty:
        return {"excess_return": np.nan, "se": np.nan, "z_stat": np.nan,
                "p_value": np.nan, "n": 0, "n_dates": 0}
    cal = calendar_time_mean_test(
        sub_, holding_period, return_col="_excess", alternative=alternative
    )
    return {
        "excess_return": cal["mean"],
        "se": cal["hac_se"],
        "z_stat": cal["t_stat"],
        "p_value": cal["p_value"],
        "n": cal["n"],
        "n_dates": cal["n_dates"],
    }


# ---------------------------------------------------------------------------
# Multiple testing
# ---------------------------------------------------------------------------
def apply_fdr_correction(p_values: pd.Series, alpha: float = FDR_ALPHA) -> pd.DataFrame:
    """Benjamini-Hochberg FDR correction over a family of tests."""
    valid = p_values.dropna()
    out = pd.DataFrame(index=p_values.index)
    out["p_value"] = p_values
    out["p_adjusted"] = np.nan
    out["reject_null"] = False
    if valid.empty:
        return out
    reject, p_adj, _, _ = multipletests(valid.to_numpy(), alpha=alpha, method="fdr_bh")
    out.loc[valid.index, "p_adjusted"] = p_adj
    out.loc[valid.index, "reject_null"] = reject
    return out


def significance_label(p_adjusted: float, effect_size: float) -> str:
    """Classify a result by FDR-adjusted significance and effect magnitude."""
    if pd.isna(p_adjusted):
        return "insufficient_data"
    if p_adjusted >= FDR_ALPHA:
        return "not_significant"
    if pd.isna(effect_size):
        return "significant_unknown_effect"
    if abs(effect_size) < 0.1:
        return "significant_but_negligible_effect"
    if abs(effect_size) < 0.3:
        return "significant_small_effect"
    return "significant_meaningful_effect"


def evaluate_signal(
    trades: pd.DataFrame,
    signal_name: str,
    holding_period: int,
    baseline_trades: pd.DataFrame | None = None,
    pools: dict | None = None,
    n_boot: int = BOOTSTRAP_ITERATIONS,
    subset: pd.DataFrame | None = None,
) -> dict:
    """Full statistical workup for one (signal, holding_period) bucket.

    `subset` lets a caller that has already grouped the trade table pass the
    bucket directly. Without it every call re-scans the full table, which at
    17.7M trades x 368 buckets is minutes of pure filtering.
    """
    if subset is None:
        subset = trades[
            (trades["signal"] == signal_name) & (trades["holding_period"] == holding_period)
        ]
    returns = subset["fwd_return"].to_numpy(dtype=float)

    boot = bootstrap_mean_and_d(
        returns, n_iter=n_boot, label=f"boot:{signal_name}:{holding_period}"
    )
    sig = one_sample_significance(returns, holding_period)
    # Panel-aware standard error supersedes the pooled-array one.
    cal = calendar_time_mean_test(subset, holding_period, alternative="two-sided")
    sig["hac_se"] = cal["hac_se"]
    sig["p_value"] = cal["p_value"]
    sig["t_stat"] = cal["t_stat"]

    # Inferential interval: normal CI on the Newey-West HAC standard error.
    # Valid under the overlap these forward returns have by construction; the
    # bootstrap interval beside it assumes iid draws and is reported only for
    # comparability with the original results.
    hac_se = sig["hac_se"]
    if np.isfinite(hac_se) and np.isfinite(boot["mean"]):
        hac_lo = boot["mean"] - 1.959964 * hac_se
        hac_hi = boot["mean"] + 1.959964 * hac_se
    else:
        hac_lo = hac_hi = np.nan

    result = {
        "signal": signal_name,
        "holding_period": holding_period,
        "n_trades": int(np.isfinite(returns).sum()),
        "mean_return": boot["mean"],
        "ci_lower": boot["ci_lower"],
        "ci_upper": boot["ci_upper"],
        "ci_method": boot["ci_method"],
        "n_bootstrap_iter": boot["n_bootstrap_iter"],
        "hac_ci_lower": hac_lo,
        "hac_ci_upper": hac_hi,
        "p_value": sig["p_value"],
        "p_value_iid": sig["p_value_iid"],
        "hac_se": hac_se,
        "n_entry_dates": cal["n_dates"],
        "effect_size_cohens_d": boot["cohens_d"],
        "cohens_d_ci_lower": boot["cohens_d_ci_lower"],
        "cohens_d_ci_upper": boot["cohens_d_ci_upper"],
    }

    if baseline_trades is not None and not baseline_trades.empty:
        base_subset = baseline_trades[baseline_trades["holding_period"] == holding_period]
        vs = two_sample_significance(
            returns, base_subset["fwd_return"].to_numpy(dtype=float), alternative="greater"
        )
        result["p_value_vs_baseline_welch"] = vs["p_value"]
        result["p_value_vs_baseline_welch_two_sided"] = vs["p_value_two_sided"]
        result["effect_size_vs_baseline"] = vs["effect_size_cohens_d"]
        result["mean_diff_vs_baseline"] = vs["mean_diff"]

    if pools is not None and len(subset):
        counts = subset.groupby("ticker").size().to_dict()
        direction = int(subset["direction"].iloc[0])
        mr = matched_randomization_test(
            counts, float(np.nanmean(returns)), direction, pools, holding_period,
            alternative="greater",
        )
        ct = matched_excess_calendar_test(subset, pools, holding_period, direction)
        # Primary inference is the calendar-time test. The SRS-variance p-value
        # is kept beside it only to document how anti-conservative it is.
        result["excess_return_vs_matched_random"] = mr["excess_return"]
        result["matched_null_mean"] = mr["null_mean"]
        result["p_value_vs_matched_random"] = ct["p_value"]
        result["matched_null_se"] = ct["se"]
        result["matched_z"] = ct["z_stat"]
        result["p_value_vs_matched_random_srs"] = mr["p_value"]
        result["matched_null_se_srs"] = mr["null_se"]

    return result
