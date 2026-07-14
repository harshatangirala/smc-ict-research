"""Stock-Level Analysis (Task 9): which S&P 500 stocks respond best/worst to
SMC/ICT signals, ranked by win rate, Sharpe, profit factor, average return,
signal frequency, and cross-period stability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.metrics import summarize_returns
from utils.config import RESULTS_DIR

MIN_TRADES_FOR_RANKING = 20


def rank_stocks(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")

    subset = trades[trades["holding_period"] == holding_period]
    rows = []
    for ticker, grp in subset.groupby("ticker"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        metrics["ticker"] = ticker
        metrics["signal_frequency"] = len(grp)
        rows.append(metrics)

    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking

    ranking["eligible"] = ranking["n_trades"] >= MIN_TRADES_FOR_RANKING
    ranking = ranking.sort_values("sharpe", ascending=False, na_position="last").reset_index(drop=True)
    return ranking


def stability_across_horizons(trades: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-ticker win-rate stability across holding periods -- a simple
    "most predictable vs least predictable" measure: low std of win rate
    across the 8 holding periods indicates a stable, horizon-robust edge.
    """
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")

    pivot = (
        trades.groupby(["ticker", "holding_period"])["fwd_return"]
        .apply(lambda s: (s > 0).mean())
        .unstack("holding_period")
    )
    stability = pd.DataFrame(
        {
            "avg_win_rate": pivot.mean(axis=1),
            "win_rate_std_across_horizons": pivot.std(axis=1),
        }
    )
    stability["stability_score"] = stability["avg_win_rate"] - stability["win_rate_std_across_horizons"]
    return stability.sort_values("stability_score", ascending=False).reset_index()


def best_worst_stocks(trades: pd.DataFrame | None = None, holding_period: int = 10, top_n: int = 50) -> dict:
    ranking = rank_stocks(trades, holding_period)
    eligible = ranking[ranking["eligible"]]
    return {
        "best": eligible.head(top_n),
        "worst": eligible.tail(top_n).sort_values("sharpe"),
    }
