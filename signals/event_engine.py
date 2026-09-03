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
from utils.config import DATA_CACHE_DIR, MIN_BARS_FOR_DETECTION
from utils.prices import load_prices
from utils.logging_config import get_logger

log = get_logger("event_engine")

# ---------------------------------------------------------------------------
# Event registry -- the allow-list of tradeable entry signals
# ---------------------------------------------------------------------------
# The previous selection rule was "every column whose dtype is bool", with a
# hand-maintained NON_EVENT_COLUMNS deny-list. That is fail-open: a new bool
# column is traded by default. It is exactly how ict_fvg_*_filled -- computed
# from up to 60 FUTURE bars -- became a tradeable entry signal contributing
# 187,719 leaked trades to the published results.
#
# The rule is now fail-closed. A boolean column is tradeable only if it is
# registered here with an explicit direction. Anything else must be declared
# as a feature or a label, or detection raises. See tests/test_event_registry.py.

#: signal name -> +1 (long) or -1 (short)
EVENT_REGISTRY: dict[str, int] = {
    # --- ICT ---------------------------------------------------------------
    "ict_displacement_bullish": +1,
    "ict_displacement_bearish": -1,
    "ict_volume_imbalance_bullish": +1,
    "ict_volume_imbalance_bearish": -1,
    "ict_fvg_bullish_formed": +1,
    "ict_fvg_bearish_formed": -1,
    "ict_bpr_bullish": +1,
    "ict_bpr_bearish": -1,
    "ict_mss_bullish": +1,
    "ict_mss_bearish": -1,
    "ict_bos_bullish": +1,
    "ict_bos_bearish": -1,
    "ict_ob_bullish_formed": +1,
    "ict_ob_bearish_formed": -1,
    "ict_ob_bullish_mitigated": -1,   # a bullish OB failing is a bearish event
    "ict_ob_bearish_mitigated": +1,
    "ict_liquidity_buyside_pool_formed": +1,
    "ict_liquidity_sellside_pool_formed": -1,
    "ict_liquidity_buyside_swept": +1,
    "ict_liquidity_sellside_swept": -1,
    "ict_sweep_buyside_bearish": -1,
    "ict_sweep_sellside_bullish": +1,
    "ict_nwog_gap_up": +1,
    "ict_nwog_gap_down": -1,
    "ict_ndog_gap_up": +1,
    "ict_ndog_gap_down": -1,
    # --- SMC ---------------------------------------------------------------
    "smc_swing_bos_bullish": +1,
    "smc_swing_bos_bearish": -1,
    "smc_swing_choch_bullish": +1,
    "smc_swing_choch_bearish": -1,
    "smc_swing_ob_bullish_formed": +1,
    "smc_swing_ob_bearish_formed": -1,
    "smc_swing_ob_bullish_mitigated": -1,
    "smc_swing_ob_bearish_mitigated": +1,
    "smc_internal_bos_bullish": +1,
    "smc_internal_bos_bearish": -1,
    "smc_internal_choch_bullish": +1,
    "smc_internal_choch_bearish": -1,
    "smc_internal_ob_bullish_formed": +1,
    "smc_internal_ob_bearish_formed": -1,
    "smc_internal_ob_bullish_mitigated": -1,
    "smc_internal_ob_bearish_mitigated": +1,
    "smc_fvg_bullish_formed": +1,
    "smc_fvg_bearish_formed": -1,
    # Equal highs = resistance (a liquidity pool above) -> bearish;
    # equal lows = support -> bullish. The original melt assigned direction 0
    # to both because neither name contains "bullish"/"bearish", and the
    # backtester then silently coerced direction 0 to +1, so BOTH were traded
    # long and smc_equal_highs was scored with the wrong sign.
    "smc_equal_highs": -1,
    "smc_equal_lows": +1,
}

#: Boolean columns that are deliberately NOT tradeable.
#: `_label` columns are forward-looking outcome labels (see signals/ict_signals).
NON_EVENT_BOOLEAN_COLUMNS: frozenset[str] = frozenset(
    {
        "ict_fvg_bullish_filled_label",
        "ict_fvg_bearish_filled_label",
    }
)

#: Continuous reference levels / state columns -- features, never events.
NON_EVENT_COLUMNS = {
    "smc_zone", "smc_trailing_top", "smc_trailing_bottom",
    "smc_prior_day_high", "smc_prior_day_low",
    "smc_prior_week_high", "smc_prior_week_low",
    "smc_prior_month_high", "smc_prior_month_low",
    "ict_fvg_bullish_lower", "ict_fvg_bullish_upper",
    "ict_fvg_bearish_lower", "ict_fvg_bearish_upper",
    "ict_nwog_gap_size", "ict_ndog_gap_size",
}


class UnregisteredSignalError(RuntimeError):
    """Raised when a detector emits a boolean column that is neither a
    registered tradeable event nor an explicitly declared non-event."""


def validate_event_columns(columns) -> None:
    """Fail loudly on any boolean column that is not explicitly classified."""
    unknown = [
        c for c in columns
        if c not in EVENT_REGISTRY
        and c not in NON_EVENT_BOOLEAN_COLUMNS
        and not c.endswith("_label")
    ]
    if unknown:
        raise UnregisteredSignalError(
            "Boolean detector columns are not classified as tradeable events or "
            f"declared non-events: {sorted(unknown)}. Add them to EVENT_REGISTRY "
            "with an explicit direction, or to NON_EVENT_BOOLEAN_COLUMNS / give "
            "them a '_label' suffix if they are forward-looking outcome labels."
        )


def _direction_for(col: str) -> int:
    """Direction for a registered signal. Unregistered names raise."""
    try:
        return EVENT_REGISTRY[col]
    except KeyError:
        raise UnregisteredSignalError(
            f"{col!r} is not in EVENT_REGISTRY; refusing to guess its direction. "
            "The previous name-substring heuristic returned 0 for unmatched "
            "names and the backtester coerced 0 to +1, silently trading "
            "direction-less signals long."
        ) from None


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
    keeping only rows where a *registered* boolean event actually fired.
    """
    bool_cols = [
        c for c in wide.columns
        if c not in ("ticker", "close")
        and c not in NON_EVENT_COLUMNS
        and wide[c].dtype == bool
    ]
    validate_event_columns(bool_cols)

    event_cols = [c for c in bool_cols if c in EVENT_REGISTRY]
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
            df = load_prices(f)
            if len(df) < MIN_BARS_FOR_DETECTION:
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
