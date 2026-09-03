"""Concept Ranking: rank every individual SMC/ICT signal by its edge over a
composition-matched random-entry null, with statistically indistinguishable
concepts flagged rather than silently presented as if reliable.

The ranking is a view onto ``results/statistics_master.csv`` (see
``analytics.master_stats``), which holds every (signal, horizon) hypothesis
with Benjamini-Hochberg control applied once across the whole family. Ranking
here by ``excess_return_vs_matched_random`` rather than by Sharpe is
deliberate: raw Sharpe over 2010-2026 mostly rewards long-biased signals for
being long during a bull market.
"""

from __future__ import annotations

import pandas as pd

from analytics.master_stats import build_statistics_master
from utils.config import MIN_SAMPLE_SIZE, PRIMARY_HOLDING_PERIOD, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("analytics.concept_ranking")

RANKING_COLUMNS = [
    "signal", "direction", "n_trades", "n_tickers", "n_entry_dates",
    "win_rate", "avg_return", "median_return", "std_return", "skewness",
    "kurtosis", "profit_factor", "expectancy", "sharpe", "sortino",
    "max_drawdown", "calmar", "reward_risk_ratio",
    "avg_mfe", "avg_mae", "median_mfe", "median_mae",
    "mean_return", "ci_lower", "ci_upper", "ci_method",
    "hac_ci_lower", "hac_ci_upper", "hac_se",
    "effect_size_cohens_d", "cohens_d_ci_lower", "cohens_d_ci_upper",
    "p_value_vs_zero", "p_adj_vs_zero", "reject_vs_zero",
    "matched_null_mean", "excess_return_vs_matched_random",
    "p_value_vs_matched_random", "p_adj_vs_matched_random",
    "reject_vs_matched_random",
    "p_value_vs_baseline_welch", "p_adj_vs_baseline_welch",
    "beats_matched_random", "significance_label", "low_sample_warning",
]


def _statistics_master(trades: pd.DataFrame | None) -> pd.DataFrame:
    path = RESULTS_DIR / "statistics_master.csv"
    if path.exists():
        return pd.read_csv(path)
    log.info("statistics_master.csv not found -- computing it now")
    return build_statistics_master(trades)


def rank_concepts(
    trades: pd.DataFrame | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> pd.DataFrame:
    """Concept ranking at one holding period, ordered by matched-random excess."""
    master = _statistics_master(trades)
    if master.empty:
        return master
    sub = master[master["holding_period"] == holding_period].copy()
    if sub.empty:
        return sub
    cols = [c for c in RANKING_COLUMNS if c in sub.columns]
    sub = sub[cols].sort_values(
        "excess_return_vs_matched_random", ascending=False, na_position="last"
    )
    # Legacy alias kept for the dashboard and report layers. Its MEANING has
    # changed: it now requires beating the matched-random null, not merely
    # differing from a pooled baseline in either direction.
    if "beats_matched_random" in sub.columns:
        sub["statistically_significant"] = sub["beats_matched_random"]
    return sub.reset_index(drop=True)


def rank_concepts_all_horizons(trades: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every (concept, horizon) row, for the per-horizon concept explorer."""
    master = _statistics_master(trades)
    if master.empty:
        return master
    cols = [c for c in (["holding_period"] + RANKING_COLUMNS) if c in master.columns]
    out = master[cols].copy()
    if "beats_matched_random" in out.columns:
        out["statistically_significant"] = out["beats_matched_random"]
    return out.reset_index(drop=True)


def summarise_edge_counts(
    trades: pd.DataFrame | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> dict:
    """Headline counts: how many concepts clear each bar, and in which direction.

    Reported separately for "beats" and "loses to" the matched random null.
    Collapsing those into one two-sided count is precisely the error that made
    the original study report 28/42 concepts as significant when 27 of those 28
    were significantly *worse* than random entry.
    """
    r = rank_concepts(trades, holding_period)
    if r.empty:
        return {}
    n = len(r)
    beats = int(r["beats_matched_random"].fillna(False).sum())
    tested = r[~r["low_sample_warning"].fillna(True)]
    loses = int(
        (
            tested["reject_vs_matched_random"].fillna(False)
            & (tested["excess_return_vs_matched_random"] < 0)
        ).sum()
    )
    return {
        "holding_period": holding_period,
        "n_concepts": n,
        "n_beats_matched_random": beats,
        "n_loses_to_matched_random": loses,
        "n_indistinguishable": n - beats - loses,
        "n_significant_vs_zero": int(r["reject_vs_zero"].fillna(False).sum())
        if "reject_vs_zero" in r.columns else None,
        "n_low_sample": int(r["low_sample_warning"].fillna(False).sum()),
    }

__all__ = [
    "rank_concepts",
    "rank_concepts_all_horizons",
    "summarise_edge_counts",
    "MIN_SAMPLE_SIZE",
    "RANKING_COLUMNS",
]
