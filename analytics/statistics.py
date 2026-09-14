"""Statistical Research Engine (Task 8): bootstrap confidence intervals,
significance tests, effect sizes, and false-discovery-rate correction across
every concept/combination tested, so conclusions are distinguishable from
chance rather than accepted at face value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from utils.config import BOOTSTRAP_ITERATIONS, FDR_ALPHA, RANDOM_SEED


MAX_BOOTSTRAP_SAMPLE = 20_000  # subsample cap for performance -- see note below


def bootstrap_mean_ci(
    returns: np.ndarray, n_iter: int = BOOTSTRAP_ITERATIONS, alpha: float = 0.05, seed: int = RANDOM_SEED
) -> tuple[float, float, float]:
    """Percentile-bootstrap CI for the mean forward return of a signal.

    For signals with very large sample sizes (some ICT signals have 1-2M+
    trades across the full universe), resampling the *full* array n_iter
    times is needlessly expensive and statistically unnecessary: bootstrap
    CI width is governed by the resample size, and a bootstrap of 20,000
    draws already gives a tighter CI than is meaningful at this scale. Above
    MAX_BOOTSTRAP_SAMPLE, we first take one random subsample of that size
    (fixed seed, reproducible) and bootstrap from it -- this is a standard,
    documented performance practice, not a validity shortcut.
    """
    r = np.asarray(returns)
    r = r[~np.isnan(r)]
    if len(r) < 5:
        return (np.nan, np.nan, np.nan)

    rng = np.random.default_rng(seed)
    if len(r) > MAX_BOOTSTRAP_SAMPLE:
        r = rng.choice(r, size=MAX_BOOTSTRAP_SAMPLE, replace=False)

    n = len(r)
    boot_means = np.empty(n_iter)
    for i in range(n_iter):
        sample = rng.choice(r, size=n, replace=True)
        boot_means[i] = sample.mean()
    lo = np.percentile(boot_means, 100 * alpha / 2)
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return (float(r.mean()), float(lo), float(hi))


def cluster_robust_mean_ci(returns: np.ndarray, clusters: np.ndarray, alpha: float = 0.05) -> tuple[float, float, float]:
    """Cluster-robust confidence interval for the mean, using the same
    cluster-by-ticker sandwich variance as the significance tests above,
    rather than a percentile bootstrap over individual (non-independent)
    trades. Closed-form and O(n), so it scales to multi-million-row signals
    without `bootstrap_mean_ci`'s subsampling shortcut."""
    r = np.asarray(returns)
    c = np.asarray(clusters)
    mask = ~np.isnan(r)
    r, c = r[mask], c[mask]
    if len(r) < 5:
        return (np.nan, np.nan, np.nan)
    mean = float(r.mean())
    var, g = _cluster_robust_variance(r, c)
    if g < 2 or not np.isfinite(var) or var < 0:
        return (mean, np.nan, np.nan)
    se = np.sqrt(var)
    t_crit = stats.t.ppf(1 - alpha / 2, df=max(g - 1, 1))
    return (mean, mean - t_crit * se, mean + t_crit * se)


def one_sample_significance(returns: np.ndarray) -> dict:
    """One-sample t-test: is the mean forward return significantly != 0?"""
    r = np.asarray(returns)
    r = r[~np.isnan(r)]
    if len(r) < 5:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan, "n": len(r)}
    t_stat, p_value = stats.ttest_1samp(r, 0.0)
    cohens_d = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else np.nan
    return {"t_stat": float(t_stat), "p_value": float(p_value), "effect_size_cohens_d": float(cohens_d), "n": len(r)}


def two_sample_significance(signal_returns: np.ndarray, baseline_returns: np.ndarray) -> dict:
    """Welch's t-test: does the signal's mean return differ from a baseline's?

    NOTE: this treats every trade as an independent draw. With holding
    windows up to 60 days, trades on the same ticker have heavily overlapping
    forward-return windows, and trades across tickers correlate on shared
    market-wide dates -- neither is i.i.d., so this test's p-value is
    optimistic (see `two_sample_significance_clustered` below, which is what
    concept/combination/sector/regime rankings now use). Kept for reference
    and for call sites without a natural cluster key (single-ticker subsets).
    """
    a = np.asarray(signal_returns)
    a = a[~np.isnan(a)]
    b = np.asarray(baseline_returns)
    b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan, "excess_return_vs_baseline": np.nan}
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    pooled_std = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    cohens_d = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else np.nan
    return {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "effect_size_cohens_d": float(cohens_d),
        "excess_return_vs_baseline": float(a.mean() - b.mean()),
    }


def _cluster_robust_variance(r: np.ndarray, clusters: np.ndarray) -> tuple[float, int]:
    """Cluster-robust variance of the sample mean (the CR1 finite-sample
    sandwich estimator for an intercept-only OLS fit -- Cameron, Gelbach &
    Miller 2011 / Stata's default `vce(cluster)`), clustered by `clusters`.

    Trades sharing a cluster (here, ticker) are not independent: overlapping
    holding-period windows on the same ticker induce serial correlation that
    a naive standard error ignores, understating it and overstating
    significance. This sums residuals *within* each cluster before summing
    their squares *across* clusters, instead of summing squared residuals
    directly -- the standard fix.
    """
    xbar = r.mean()
    resid = r - xbar
    cluster_sums = pd.Series(resid).groupby(np.asarray(clusters)).sum()
    g = len(cluster_sums)
    n = len(r)
    if g < 2:
        return (np.nan, g)
    finite_sample_correction = g / (g - 1)
    var = finite_sample_correction * cluster_sums.pow(2).sum() / (n * n)
    return (float(var), int(g))


def one_sample_significance_clustered(returns: np.ndarray, clusters: np.ndarray) -> dict:
    """One-sample test for mean return != 0, with cluster-robust SE (clustered
    by ticker) instead of assuming i.i.d. trades. See `_cluster_robust_variance`."""
    r = np.asarray(returns)
    c = np.asarray(clusters)
    mask = ~np.isnan(r)
    r, c = r[mask], c[mask]
    if len(r) < 5:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan, "n": len(r), "n_clusters": 0}
    var, g = _cluster_robust_variance(r, c)
    cohens_d = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else np.nan
    if g < 2 or not np.isfinite(var) or var <= 0:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": float(cohens_d), "n": len(r), "n_clusters": g}
    se = np.sqrt(var)
    t_stat = r.mean() / se
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=g - 1))
    return {"t_stat": float(t_stat), "p_value": float(p_value), "effect_size_cohens_d": float(cohens_d), "n": len(r), "n_clusters": g}


def two_sample_significance_clustered(
    signal_returns: np.ndarray,
    signal_clusters: np.ndarray,
    baseline_returns: np.ndarray,
    baseline_clusters: np.ndarray,
) -> dict:
    """Welch-style two-sample test with cluster-robust SE on each side
    (clustered by ticker), replacing the naive `two_sample_significance` for
    every concept/combination/sector/regime ranking. Degrees of freedom use
    the smaller side's cluster count minus one -- a conservative choice given
    two-way (ticker x date) clustering is not implemented here."""
    a = np.asarray(signal_returns)
    ca = np.asarray(signal_clusters)
    ma = ~np.isnan(a)
    a, ca = a[ma], ca[ma]
    b = np.asarray(baseline_returns)
    cb = np.asarray(baseline_clusters)
    mb = ~np.isnan(b)
    b, cb = b[mb], cb[mb]

    if len(a) < 5 or len(b) < 5:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan, "excess_return_vs_baseline": np.nan, "n_clusters_signal": 0, "n_clusters_baseline": 0}

    diff = float(a.mean() - b.mean())
    pooled_std = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    cohens_d = diff / pooled_std if pooled_std > 0 else np.nan

    var_a, ga = _cluster_robust_variance(a, ca)
    var_b, gb = _cluster_robust_variance(b, cb)
    if ga < 2 or gb < 2 or not np.isfinite(var_a) or not np.isfinite(var_b):
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": float(cohens_d), "excess_return_vs_baseline": diff, "n_clusters_signal": ga, "n_clusters_baseline": gb}

    se = np.sqrt(var_a + var_b)
    if se <= 0 or not np.isfinite(se):
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": float(cohens_d), "excess_return_vs_baseline": diff, "n_clusters_signal": ga, "n_clusters_baseline": gb}

    t_stat = diff / se
    df = max(min(ga, gb) - 1, 1)
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=df))
    return {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "effect_size_cohens_d": float(cohens_d),
        "excess_return_vs_baseline": diff,
        "n_clusters_signal": ga,
        "n_clusters_baseline": gb,
    }


def apply_fdr_correction(p_values: pd.Series, alpha: float = FDR_ALPHA) -> pd.DataFrame:
    """Benjamini-Hochberg FDR correction across many simultaneous hypothesis
    tests (every concept x holding period x stock combination tested).
    """
    valid = p_values.dropna()
    if valid.empty:
        return pd.DataFrame({"p_value": p_values, "reject_null": pd.Series(dtype=bool), "p_adjusted": pd.Series(dtype=float)})
    reject, p_adj, _, _ = multipletests(valid.to_numpy(), alpha=alpha, method="fdr_bh")
    out = pd.DataFrame(index=p_values.index)
    out["p_value"] = p_values
    out["p_adjusted"] = np.nan
    out["reject_null"] = False
    out.loc[valid.index, "p_adjusted"] = p_adj
    out.loc[valid.index, "reject_null"] = reject
    return out


def significance_label(p_adjusted: float, effect_size: float) -> str:
    """Human-readable classification combining FDR-adjusted significance and
    effect size magnitude, per Task 8's "distinguish significant from weak
    from random" requirement.
    """
    if pd.isna(p_adjusted):
        return "insufficient_data"
    if p_adjusted >= FDR_ALPHA:
        return "not_significant"
    if abs(effect_size) < 0.1:
        return "significant_but_negligible_effect"
    if abs(effect_size) < 0.3:
        return "significant_small_effect"
    return "significant_meaningful_effect"


def evaluate_signal(
    trades: pd.DataFrame, signal_name: str, holding_period: int, baseline_trades: pd.DataFrame | None = None
) -> dict:
    """Full statistical workup for one (signal, holding_period) bucket.

    Both the zero-null and baseline tests are cluster-robust, clustered by
    ticker (`_cluster_robust_variance`) -- required columns: `fwd_return`,
    `ticker`. See the audit finding this responds to: naive per-trade t-tests
    on overlapping-window, cross-sectionally correlated trades understate the
    true standard error and can manufacture significance out of noise.
    """
    subset = trades[(trades["signal"] == signal_name) & (trades["holding_period"] == holding_period)]
    returns = subset["fwd_return"].to_numpy()
    clusters = subset["ticker"].to_numpy()

    mean, ci_lo, ci_hi = cluster_robust_mean_ci(returns, clusters)
    sig = one_sample_significance_clustered(returns, clusters)

    result = {
        "signal": signal_name,
        "holding_period": holding_period,
        "n_trades": len(returns[~np.isnan(returns)]),
        "n_clusters": sig["n_clusters"],
        "mean_return": mean,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "p_value": sig["p_value"],
        "effect_size_cohens_d": sig["effect_size_cohens_d"],
    }

    if baseline_trades is not None and not baseline_trades.empty:
        base_subset = baseline_trades[baseline_trades["holding_period"] == holding_period]
        vs_baseline = two_sample_significance_clustered(
            returns, clusters, base_subset["fwd_return"].to_numpy(), base_subset["ticker"].to_numpy()
        )
        result["p_value_vs_baseline"] = vs_baseline["p_value"]
        result["effect_size_vs_baseline"] = vs_baseline["effect_size_cohens_d"]
        result["excess_return_vs_baseline"] = vs_baseline["excess_return_vs_baseline"]

    return result
