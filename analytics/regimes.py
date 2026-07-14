"""Market Regime Analysis (Task 12): split results by bull/bear/sideways and
by high/low volatility, using each stock's own trend/volatility state as of
the signal date (no external index required).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backtest.metrics import summarize_returns
from utils.config import DATA_CACHE_DIR, RESULTS_DIR


def classify_regime(df: pd.DataFrame, trend_window: int = 200, vol_window: int = 63) -> pd.DataFrame:
    """Per-bar regime labels derived from the ticker's own price series:
    trend regime from price vs. its SMA(200) and that SMA's own slope;
    volatility regime from realized volatility relative to its own expanding
    median (so "high vol" means high *for that stock*, not an absolute cut).
    """
    close = df["close"]
    sma = close.rolling(trend_window, min_periods=trend_window // 2).mean()
    sma_slope = sma.diff(20)

    trend = pd.Series("sideways", index=df.index)
    trend[(close > sma) & (sma_slope > 0)] = "bull"
    trend[(close < sma) & (sma_slope < 0)] = "bear"

    daily_ret = close.pct_change()
    realized_vol = daily_ret.rolling(vol_window).std()
    vol_median = realized_vol.expanding(min_periods=vol_window).median()
    vol_regime = pd.Series("normal_vol", index=df.index)
    vol_regime[realized_vol > 1.5 * vol_median] = "high_vol"
    vol_regime[realized_vol < 0.67 * vol_median] = "low_vol"

    return pd.DataFrame({"trend_regime": trend, "vol_regime": vol_regime})


def tag_trades_with_regime(trades: pd.DataFrame, cache_dir: Path = DATA_CACHE_DIR) -> pd.DataFrame:
    regime_frames = []
    for ticker, grp in trades.groupby("ticker"):
        path = Path(cache_dir) / f"{ticker}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path).sort_index()
        regimes = classify_regime(df)
        merged = grp.merge(regimes, left_on="date", right_index=True, how="left")
        regime_frames.append(merged)
    return pd.concat(regime_frames, ignore_index=True) if regime_frames else trades


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def regime_analysis(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period]
    tagged = tag_trades_with_regime(subset)

    baseline_trades = _load_baseline_trades()
    baseline_regime_avg = {}
    if baseline_trades is not None:
        base_subset = baseline_trades[baseline_trades["holding_period"] == holding_period]
        base_tagged = tag_trades_with_regime(base_subset)
        baseline_regime_avg = base_tagged.groupby(["trend_regime", "vol_regime"])["fwd_return"].mean().to_dict()

    rows = []
    for (trend_regime, vol_regime), grp in tagged.groupby(["trend_regime", "vol_regime"]):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        baseline_avg = baseline_regime_avg.get((trend_regime, vol_regime), float("nan"))
        metrics["baseline_avg_return"] = baseline_avg
        metrics["excess_return_vs_baseline"] = metrics["avg_return"] - baseline_avg
        rows.append({"trend_regime": trend_regime, "vol_regime": vol_regime, **metrics})

    return pd.DataFrame(rows).sort_values(["trend_regime", "vol_regime"]).reset_index(drop=True)


def regime_analysis_by_signal(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    """Same as regime_analysis but broken out per signal, to answer "are
    results stable for THIS concept across regimes" rather than only in
    aggregate."""
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period]
    tagged = tag_trades_with_regime(subset)

    rows = []
    for (signal, trend_regime), grp in tagged.groupby(["signal", "trend_regime"]):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        rows.append({"signal": signal, "trend_regime": trend_regime, **metrics})
    return pd.DataFrame(rows)
