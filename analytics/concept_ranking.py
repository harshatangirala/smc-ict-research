"""Concept Ranking (Task 10): rank every individual SMC/ICT signal (and the
baseline strategies) by win rate, Sharpe, average return, profit factor, and
expectancy, with statistically-insignificant concepts flagged rather than
silently included as if equally reliable.
"""

from __future__ import annotations

import pandas as pd

from analytics.statistics import apply_fdr_correction, evaluate_signal
from backtest.metrics import summarize_returns
from utils.config import RESULTS_DIR

MIN_SAMPLE_SIZE = 30  # below this, a concept's stats are reported but flagged low-confidence


def rank_concepts(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")

    subset = trades[trades["holding_period"] == holding_period]
    rows = []
    for signal, grp in subset.groupby("signal"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        stats_result = evaluate_signal(trades, signal, holding_period)
        rows.append({"signal": signal, **metrics, **{k: v for k, v in stats_result.items() if k not in ("signal", "holding_period")}})

    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking

    fdr = apply_fdr_correction(ranking.set_index("signal")["p_value"])
    ranking = ranking.merge(fdr[["p_adjusted", "reject_null"]], left_on="signal", right_index=True, how="left")
    ranking["low_sample_warning"] = ranking["n_trades"] < MIN_SAMPLE_SIZE
    ranking["statistically_significant"] = ranking["reject_null"].fillna(False) & ~ranking["low_sample_warning"]

    ranking = ranking.sort_values("sharpe", ascending=False, na_position="last")
    return ranking.reset_index(drop=True)


def rank_concepts_all_horizons(trades: pd.DataFrame | None = None) -> pd.DataFrame:
    """Same ranking repeated at every holding period, for the dashboard's
    per-horizon concept explorer."""
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    frames = []
    for h in sorted(trades["holding_period"].unique()):
        r = rank_concepts(trades, holding_period=h)
        r["holding_period"] = h
        frames.append(r)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
