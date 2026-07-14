"""Event Detection Engine (Task 6).

Runs every ICT + SMC detector for every cached ticker and assembles the
master "long" event dataframe: one row per (ticker, date, signal_name) where
that signal fired True, with a `direction` column (+1/-1) so downstream
backtesting doesn't need to know each signal's naming convention.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from signals.ict_signals import detect_all_ict
from signals.smc_signals import detect_all_smc
from utils.config import DATA_CACHE_DIR
from utils.logging_config import get_logger

log = get_logger("event_engine")

# Boolean "formed" columns that represent tradeable entry signals (as opposed
# to continuous reference levels like smc_prior_day_high or state columns
# like smc_zone/smc_trailing_top, which are features, not events).
BOOLEAN_EVENT_SUFFIXES = ("_formed", "_bullish", "_bearish", "_swept", "_mitigated")
NON_EVENT_COLUMNS = {
    "smc_zone", "smc_trailing_top", "smc_trailing_bottom",
    "smc_prior_day_high", "smc_prior_day_low",
    "smc_prior_week_high", "smc_prior_week_low",
    "smc_prior_month_high", "smc_prior_month_low",
    "ict_fvg_bullish_top", "ict_fvg_bullish_bottom",
    "ict_fvg_bearish_top", "ict_fvg_bearish_bottom",
    "ict_nwog_gap_size", "ict_ndog_gap_size",
}

BULLISH_HINT = ("bullish", "buyside")
BEARISH_HINT = ("bearish", "sellside")


def _direction_for(col: str) -> int:
    lc = col.lower()
    if any(h in lc for h in BULLISH_HINT):
        return 1
    if any(h in lc for h in BEARISH_HINT):
        return -1
    return 0


def detect_ticker(ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    """Run every detector for one ticker and return a wide per-bar frame."""
    ict = detect_all_ict(df)
    smc = detect_all_smc(df)
    wide = pd.concat([ict, smc], axis=1)
    wide.insert(0, "ticker", ticker)
    wide.insert(1, "close", df["close"])
    return wide


def melt_events(wide: pd.DataFrame) -> pd.DataFrame:
    """Wide per-bar signal frame -> long (ticker, date, signal, direction) frame,
    keeping only rows where a boolean event actually fired.
    """
    event_cols = [
        c for c in wide.columns
        if c not in ("ticker", "close") and c not in NON_EVENT_COLUMNS
        and wide[c].dtype == bool
    ]
    frames = []
    for col in event_cols:
        mask = wide[col]
        if not mask.any():
            continue
        sub = wide.loc[mask, ["ticker", "close"]].copy()
        sub["signal"] = col
        sub["direction"] = _direction_for(col)
        sub["date"] = sub.index
        frames.append(sub)
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "signal", "direction", "close"])
    out = pd.concat(frames, ignore_index=True)
    return out[["ticker", "date", "signal", "direction", "close"]]


def build_master_events(cache_dir: Path = DATA_CACHE_DIR, tickers: list[str] | None = None) -> pd.DataFrame:
    """Run detection across every cached ticker and return the master event table."""
    files = sorted(Path(cache_dir).glob("*.parquet"))
    if tickers is not None:
        wanted = set(tickers)
        files = [f for f in files if f.stem in wanted]

    log.info("Running event detection for %d tickers", len(files))
    all_events = []
    for i, f in enumerate(files, 1):
        ticker = f.stem
        try:
            df = pd.read_parquet(f)
            df = df.sort_index()
            df = df[~df.index.duplicated(keep="first")]
            if len(df) < 300:
                log.warning("Skipping %s: only %d rows (too short for reliable detection)", ticker, len(df))
                continue
            wide = detect_ticker(ticker, df)
            events = melt_events(wide)
            all_events.append(events)
        except Exception as exc:  # noqa: BLE001
            log.error("Detection failed for %s: %s", ticker, exc)
        if i % 50 == 0 or i == len(files):
            log.info("Detected events for %d/%d tickers", i, len(files))

    master = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    log.info("Master event table: %d rows across %d tickers, %d distinct signals",
              len(master), master["ticker"].nunique() if len(master) else 0,
              master["signal"].nunique() if len(master) else 0)
    return master
