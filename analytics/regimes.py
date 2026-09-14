"""Market Regime Analysis: split results by bull/bear/sideways trend and by
high/low volatility, using each stock's own state as of the signal date.

The comparator
--------------
Regime buckets are compared against a **regime-conditional, direction-matched
null**: the mean h-day forward return of *every bar* that sat in the same
regime, on the same tickers, taken in the signal's own direction.

That null has to be built from bars, not from the trades themselves. An
earlier draft compared each regime bucket against the pool of signal trades in
that same bucket — which is the bucket itself, so the excess was identically
zero. It also cannot be the long-only random-entry baseline: roughly half the
signal population is short, so subtracting a long-only benchmark from it
measures net directional exposure rather than signal quality, and does so
almost uniformly across buckets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backtest.metrics import summarize_returns
from utils.config import DATA_CACHE_DIR, PRIMARY_HOLDING_PERIOD, RESULTS_DIR
from utils.logging_config import get_logger
from utils.prices import load_prices

log = get_logger("analytics.regimes")


def classify_regime(df: pd.DataFrame, trend_window: int = 200, vol_window: int = 63) -> pd.DataFrame:
    """Per-bar regime labels derived from the ticker's own price series.

    Trend comes from price versus its SMA(200) and that SMA's slope; volatility
    from realised vol relative to its own expanding median, so "high vol" means
    high *for this stock* rather than an absolute cut.
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
    """Attach the entry bar's regime labels to every trade."""
    regime_frames = []
    for ticker, grp in trades.groupby("ticker"):
        path = Path(cache_dir) / f"{ticker}.parquet"
        if not path.exists():
            continue
        regimes = classify_regime(load_prices(path))
        merged = grp.merge(regimes, left_on="date", right_index=True, how="left")
        regime_frames.append(merged)
    return pd.concat(regime_frames, ignore_index=True) if regime_frames else trades


def build_regime_null(
    tickers: list[str],
    holding_period: int,
    cache_dir: Path = DATA_CACHE_DIR,
) -> dict[tuple[str, str], float]:
    """Mean h-day forward return of every bar, by (trend_regime, vol_regime).

    This is the *long* null; a short signal's null is its negation. Built from
    bars rather than trades so it is a genuine random-entry comparator.
    """
    sums: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], int] = {}
    for ticker in tickers:
        path = Path(cache_dir) / f"{ticker}.parquet"
        if not path.exists():
            continue
        df = load_prices(path)
        if len(df) <= holding_period + 1:
            continue
        regimes = classify_regime(df)
        close = df["close"].to_numpy(dtype=float)
        fwd = close[holding_period:] / close[:-holding_period] - 1.0
        trend = regimes["trend_regime"].to_numpy()[: len(fwd)]
        vol = regimes["vol_regime"].to_numpy()[: len(fwd)]
        ok = np.isfinite(fwd)
        for t, v, r in zip(trend[ok], vol[ok], fwd[ok]):
            key = (t, v)
            sums[key] = sums.get(key, 0.0) + float(r)
            counts[key] = counts.get(key, 0) + 1
    return {k: sums[k] / counts[k] for k in sums if counts[k] > 0}


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def regime_analysis(
    trades: pd.DataFrame | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> pd.DataFrame:
    """Per-regime performance against the regime-conditional matched null."""
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period]
    tagged = tag_trades_with_regime(subset)
    if "trend_regime" not in tagged.columns:
        return pd.DataFrame()

    log.info("Building regime-conditional null from bars")
    regime_null = build_regime_null(
        sorted(tagged["ticker"].unique()), holding_period
    )

    baseline_trades = _load_baseline_trades()
    baseline_regime_avg = {}
    if baseline_trades is not None:
        base = tag_trades_with_regime(
            baseline_trades[baseline_trades["holding_period"] == holding_period]
        )
        if "trend_regime" in base.columns:
            baseline_regime_avg = (
                base.groupby(["trend_regime", "vol_regime"])["fwd_return"].mean().to_dict()
            )

    rows = []
    for (trend_regime, vol_regime), grp in tagged.groupby(["trend_regime", "vol_regime"]):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        long_null = regime_null.get((trend_regime, vol_regime), np.nan)

        null_num, excess_num, n_total = 0.0, 0.0, 0
        for direction, dgrp in grp.groupby("direction"):
            if not np.isfinite(long_null):
                continue
            null_d = int(direction) * long_null
            n_d = len(dgrp)
            null_num += null_d * n_d
            excess_num += (float(dgrp["fwd_return"].mean()) - null_d) * n_d
            n_total += n_d

        metrics.update(
            {
                "trend_regime": trend_regime,
                "vol_regime": vol_regime,
                "n_tickers": int(grp["ticker"].nunique()),
                "n_long_trades": int((grp["direction"] == 1).sum()),
                "n_short_trades": int((grp["direction"] == -1).sum()),
                "avg_return_long": float(grp.loc[grp["direction"] == 1, "fwd_return"].mean())
                if (grp["direction"] == 1).any() else np.nan,
                "avg_return_short": float(grp.loc[grp["direction"] == -1, "fwd_return"].mean())
                if (grp["direction"] == -1).any() else np.nan,
                "regime_null_long": long_null,
                "matched_null_mean": null_num / n_total if n_total else np.nan,
                "excess_return_vs_matched_random": excess_num / n_total if n_total else np.nan,
                # Long-only baseline retained for continuity; not the headline,
                # for the reason given in the module docstring.
                "baseline_avg_return": baseline_regime_avg.get(
                    (trend_regime, vol_regime), np.nan
                ),
            }
        )
        rows.append(metrics)

    out = pd.DataFrame(rows)
    front = ["trend_regime", "vol_regime", "n_trades", "n_tickers",
             "n_long_trades", "n_short_trades", "avg_return",
             "avg_return_long", "avg_return_short", "regime_null_long",
             "matched_null_mean", "excess_return_vs_matched_random"]
    cols = [c for c in front if c in out.columns] + [c for c in out.columns if c not in front]
    return out[cols].sort_values(["trend_regime", "vol_regime"]).reset_index(drop=True)


def regime_analysis_by_signal(
    trades: pd.DataFrame | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> pd.DataFrame:
    """Per-signal regime breakdown: is a concept's result stable across regimes?"""
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period]
    tagged = tag_trades_with_regime(subset)
    if "trend_regime" not in tagged.columns:
        return pd.DataFrame()

    regime_null = build_regime_null(sorted(tagged["ticker"].unique()), holding_period)

    rows = []
    for (signal, trend_regime), grp in tagged.groupby(["signal", "trend_regime"]):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        direction = int(grp["direction"].iloc[0])
        nulls = [
            regime_null.get((trend_regime, v), np.nan)
            for v in grp["vol_regime"].dropna().unique()
        ]
        long_null = float(np.nanmean(nulls)) if nulls else np.nan
        rows.append(
            {
                "signal": signal,
                "trend_regime": trend_regime,
                "direction": direction,
                **metrics,
                "matched_null_mean": direction * long_null,
                "excess_return_vs_matched_random": metrics.get("avg_return", np.nan)
                - direction * long_null,
            }
        )
    return pd.DataFrame(rows)
