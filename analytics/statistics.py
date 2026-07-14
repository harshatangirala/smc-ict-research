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


def bootstrap_mean_ci(
    returns: np.ndarray, n_iter: int = BOOTSTRAP_ITERATIONS, alpha: float = 0.05, seed: int = RANDOM_SEED
) -> tuple[float, float, float]:
    """Percentile-bootstrap CI for the mean forward return of a signal."""
    r = np.asarray(returns)
    r = r[~np.isnan(r)]
    if len(r) < 5:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    n = len(r)
    boot_means = np.empty(n_iter)
    for i in range(n_iter):
        sample = rng.choice(r, size=n, replace=True)
        boot_means[i] = sample.mean()
    lo = np.percentile(boot_means, 100 * alpha / 2)
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return (float(r.mean()), float(lo), float(hi))


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
    """Welch's t-test: does the signal's mean return differ from a baseline's?"""
    a = np.asarray(signal_returns)
    a = a[~np.isnan(a)]
    b = np.asarray(baseline_returns)
    b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return {"t_stat": np.nan, "p_value": np.nan, "effect_size_cohens_d": np.nan}
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    pooled_std = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    cohens_d = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else np.nan
    return {"t_stat": float(t_stat), "p_value": float(p_value), "effect_size_cohens_d": float(cohens_d)}


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
    """Full statistical workup for one (signal, holding_period) bucket."""
    subset = trades[(trades["signal"] == signal_name) & (trades["holding_period"] == holding_period)]
    returns = subset["fwd_return"].to_numpy()

    mean, ci_lo, ci_hi = bootstrap_mean_ci(returns)
    sig = one_sample_significance(returns)

    result = {
        "signal": signal_name,
        "holding_period": holding_period,
        "n_trades": len(returns[~np.isnan(returns)]),
        "mean_return": mean,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "p_value": sig["p_value"],
        "effect_size_cohens_d": sig["effect_size_cohens_d"],
    }

    if baseline_trades is not None and not baseline_trades.empty:
        base_subset = baseline_trades[baseline_trades["holding_period"] == holding_period]
        vs_baseline = two_sample_significance(returns, base_subset["fwd_return"].to_numpy())
        result["p_value_vs_baseline"] = vs_baseline["p_value"]
        result["effect_size_vs_baseline"] = vs_baseline["effect_size_cohens_d"]

    return result
