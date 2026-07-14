"""Stock-Level Analysis (Task 9): which S&P 500 stocks respond best/worst to
SMC/ICT signals, ranked by win rate, Sharpe, profit factor, average return,
signal frequency, and cross-period stability.

A raw per-ticker Sharpe is a misleading "most responsive stock" ranking on
its own: a stock that simply rallied hard over 2010-2026 (SNDK, GEV, PLTR,
NVDA, ...) will show a high Sharpe on *any* long-biased signal population,
independent of whether the SMC/ICT signal added anything beyond chance on
that specific stock. Every ticker's signal-trade returns are therefore also
compared against that SAME ticker's random-entry baseline (same backtest
mechanics, same holding period) via a two-sample test, so "this stock
responds well to SMC/ICT" and "this stock went up a lot" are distinguishable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.statistics import two_sample_significance
from backtest.metrics import summarize_returns
from utils.config import RESULTS_DIR

MIN_TRADES_FOR_RANKING = 20
MIN_BASELINE_TRADES = 15  # per-ticker baseline sample floor for a meaningful two-sample test


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def rank_stocks(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    baseline_trades = _load_baseline_trades()
    baseline_subset = (
        baseline_trades[baseline_trades["holding_period"] == holding_period] if baseline_trades is not None else None
    )
    baseline_by_ticker = (
        {t: g["fwd_return"].to_numpy() for t, g in baseline_subset.groupby("ticker")}
        if baseline_subset is not None else {}
    )

    subset = trades[trades["holding_period"] == holding_period]
    rows = []
    for ticker, grp in subset.groupby("ticker"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        metrics["ticker"] = ticker
        metrics["signal_frequency"] = len(grp)

        base_returns = baseline_by_ticker.get(ticker)
        if base_returns is not None and len(base_returns) >= MIN_BASELINE_TRADES:
            vs_baseline = two_sample_significance(grp["fwd_return"].to_numpy(), base_returns)
            metrics["baseline_avg_return"] = float(np.nanmean(base_returns))
            metrics["excess_return_vs_baseline"] = metrics["avg_return"] - metrics["baseline_avg_return"]
            metrics["p_value_vs_baseline"] = vs_baseline["p_value"]
            metrics["effect_size_vs_baseline"] = vs_baseline["effect_size_cohens_d"]
        else:
            metrics["baseline_avg_return"] = np.nan
            metrics["excess_return_vs_baseline"] = np.nan
            metrics["p_value_vs_baseline"] = np.nan
            metrics["effect_size_vs_baseline"] = np.nan

        rows.append(metrics)

    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking

    ranking["eligible"] = ranking["n_trades"] >= MIN_TRADES_FOR_RANKING
    from analytics.statistics import apply_fdr_correction

    valid = ranking[ranking["p_value_vs_baseline"].notna()]
    if not valid.empty:
        fdr = apply_fdr_correction(valid.set_index("ticker")["p_value_vs_baseline"])
        ranking = ranking.merge(
            fdr[["p_adjusted", "reject_null"]].rename(columns={"p_adjusted": "p_adjusted_vs_baseline", "reject_null": "significant_vs_baseline"}),
            left_on="ticker", right_index=True, how="left",
        )
    else:
        ranking["p_adjusted_vs_baseline"] = np.nan
        ranking["significant_vs_baseline"] = False

    # Headline ranking is by excess return vs. that ticker's own baseline
    # where available (the "genuinely responsive to SMC/ICT" ordering), not
    # raw Sharpe (which just rewards stocks that went up a lot).
    ranking = ranking.sort_values(
        ["excess_return_vs_baseline", "sharpe"], ascending=[False, False], na_position="last"
    ).reset_index(drop=True)
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
