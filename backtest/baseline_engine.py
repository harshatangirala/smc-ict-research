"""Runs the baseline/benchmark strategies (backtest/baselines.py) across the
same universe as the SMC/ICT event engine, so every concept's significance
can be tested against "does this beat a simple technical strategy / random
entry at the same frequency" rather than only "is the mean return different
from zero" -- the latter is a much weaker test that a long-biased signal can
pass purely from broad market drift over a long bull period.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest.baselines import detect_all_baselines
from utils.config import DATA_CACHE_DIR
from utils.logging_config import get_logger

log = get_logger("backtest.baseline_engine")


def melt_baseline_events(ticker: str, wide: pd.DataFrame) -> pd.DataFrame:
    event_cols = [c for c in wide.columns if wide[c].dtype == bool]
    frames = []
    for col in event_cols:
        mask = wide[col]
        if not mask.any():
            continue
        sub = pd.DataFrame({"close": wide.loc[mask, "close"]})
        sub["ticker"] = ticker
        sub["signal"] = col
        sub["direction"] = 1 if "bearish" not in col else -1
        sub["date"] = sub.index
        frames.append(sub)
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "signal", "direction", "close"])
    out = pd.concat(frames, ignore_index=True)
    return out[["ticker", "date", "signal", "direction", "close"]]


def build_baseline_events(cache_dir: Path = DATA_CACHE_DIR, n_random_signals: int = 50) -> pd.DataFrame:
    files = sorted(Path(cache_dir).glob("*.parquet"))
    all_events = []
    for i, f in enumerate(files, 1):
        ticker = f.stem
        try:
            df = pd.read_parquet(f).sort_index()
            df = df[~df.index.duplicated(keep="first")]
            if len(df) < 300:
                continue
            wide = detect_all_baselines(df, ticker=ticker, n_random_signals=n_random_signals)
            wide["close"] = df["close"]
            events = melt_baseline_events(ticker, wide)
            all_events.append(events)
        except Exception as exc:  # noqa: BLE001
            log.error("Baseline detection failed for %s: %s", ticker, exc)
        if i % 100 == 0 or i == len(files):
            log.info("Baseline-detected %d/%d tickers", i, len(files))

    master = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    log.info("Baseline event table: %d rows, %d signals", len(master), master["signal"].nunique() if len(master) else 0)
    return master
