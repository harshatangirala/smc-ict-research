"""Smart Money Concepts [LuxAlgo] signal detectors, translated from
docs/reference/SMC_Concepts_LuxAlgo.pine per docs/concepts_extraction.md
(Section 2) and docs/task02_pine_analysis.md.

Internal and Swing scale structure/order-block detectors are run through one
shared function (`_structure_and_ob`) parameterized by pivot lookback, since
that is exactly what the Pine source does (`getCurrentStructure`/
`displayStructure` called twice with different `size`/`internal` args).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pine_parser.atr import atr, true_range, wilder_rma
from pine_parser.legs import extract_swing_points
from utils.config import SMC

BULLISH, BEARISH = 1, -1


def _structure_and_ob(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    open_: pd.Series,
    size: int,
    prefix: str,
    other_high_level: np.ndarray | None = None,
    other_low_level: np.ndarray | None = None,
    confluence: bool = False,
    parsed_high: np.ndarray | None = None,
    parsed_low: np.ndarray | None = None,
    ob_max_retained: int | None = None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """One pass: BOS/CHoCH structure breaks + order block formation/mitigation.

    Returns (events_df, current_high_level_array, current_low_level_array) --
    the level arrays are exposed so the swing-scale call's output can be fed
    back in as `other_high_level`/`other_low_level` for the internal-scale
    call (matching Pine's `internalHigh.currentLevel != swingHigh.currentLevel`
    guard).
    """
    ob_max_retained = SMC.ob_max_retained if ob_max_retained is None else ob_max_retained
    n = len(high)
    h, l, c, o = high.to_numpy(), low.to_numpy(), close.to_numpy(), open_.to_numpy()
    swing_high, swing_low = extract_swing_points(high, low, size)
    sh, sl = swing_high.to_numpy(), swing_low.to_numpy()

    if parsed_high is None:
        parsed_high = h
    if parsed_low is None:
        parsed_low = l

    if confluence:
        bullish_bar = (h - np.maximum(c, o)) > (np.minimum(c, o) - l)
        bearish_bar = ~bullish_bar
    else:
        bullish_bar = np.ones(n, dtype=bool)
        bearish_bar = np.ones(n, dtype=bool)

    bos_bull = np.zeros(n, dtype=bool)
    choch_bull = np.zeros(n, dtype=bool)
    bos_bear = np.zeros(n, dtype=bool)
    choch_bear = np.zeros(n, dtype=bool)
    ob_bull_formed = np.zeros(n, dtype=bool)
    ob_bear_formed = np.zeros(n, dtype=bool)
    ob_bull_mitigated = np.zeros(n, dtype=bool)
    ob_bear_mitigated = np.zeros(n, dtype=bool)

    cur_high_level = np.full(n, np.nan)
    cur_low_level = np.full(n, np.nan)

    trend_bias = 0
    high_level, low_level = np.nan, np.nan
    high_crossed, low_crossed = True, True
    high_pivot_bar, low_pivot_bar = -1, -1

    bullish_obs: list[dict] = []
    bearish_obs: list[dict] = []

    for i in range(n):
        if not np.isnan(sh[i]):
            high_level = sh[i]
            high_crossed = False
            high_pivot_bar = i - size  # Pine: bar_index[size] at the moment of the flip
        if not np.isnan(sl[i]):
            low_level = sl[i]
            low_crossed = False
            low_pivot_bar = i - size

        cur_high_level[i] = high_level
        cur_low_level[i] = low_level

        if i > 0 and not high_crossed and not np.isnan(high_level):
            crossover = c[i] > high_level and c[i - 1] <= high_level
            extra = bullish_bar[i]
            if other_high_level is not None:
                extra = extra and (high_level != other_high_level[i])
            if crossover and extra:
                is_choch = trend_bias == BEARISH
                (choch_bull if is_choch else bos_bull)[i] = True
                trend_bias = BULLISH
                high_crossed = True
                # Pine storeOrdeBlock(p_ivot, internal, BULLISH): the block is the
                # bar with the LOWEST parsed low in [pivot bar, break bar) -- the
                # pullback low the move launched from. The first version took the
                # HIGHEST parsed high and included the break bar, which put every
                # bullish block at the top of the move and fired its mitigation
                # almost at once. Found in the end-to-end audit.
                seg_hi = parsed_high[max(high_pivot_bar, 0) : i]
                seg_lo = parsed_low[max(high_pivot_bar, 0) : i]
                if len(seg_lo) > 0:
                    j = int(np.argmin(seg_lo))
                    bullish_obs.append({"top": seg_hi[j], "btm": seg_lo[j]})
                    if len(bullish_obs) > ob_max_retained:
                        bullish_obs.pop(0)
                    ob_bull_formed[i] = True

        if i > 0 and not low_crossed and not np.isnan(low_level):
            crossunder = c[i] < low_level and c[i - 1] >= low_level
            extra = bearish_bar[i]
            if other_low_level is not None:
                extra = extra and (low_level != other_low_level[i])
            if crossunder and extra:
                is_choch = trend_bias == BULLISH
                (choch_bear if is_choch else bos_bear)[i] = True
                trend_bias = BEARISH
                low_crossed = True
                # Pine storeOrdeBlock(..., BEARISH): the bar with the HIGHEST
                # parsed high in [pivot bar, break bar). Mirror of the fix above.
                seg_hi = parsed_high[max(low_pivot_bar, 0) : i]
                seg_lo = parsed_low[max(low_pivot_bar, 0) : i]
                if len(seg_hi) > 0:
                    j = int(np.argmax(seg_hi))
                    bearish_obs.append({"top": seg_hi[j], "btm": seg_lo[j]})
                    if len(bearish_obs) > ob_max_retained:
                        bearish_obs.pop(0)
                    ob_bear_formed[i] = True

        # Mitigation (High/Low mode -- SMC's default mitigation source). Pine
        # REMOVES a mitigated block from its array, so the 100-block cap counts
        # live blocks only. Keeping mitigated blocks in the list (the first
        # version) evicted older live blocks early and suppressed their later
        # mitigations.
        if bullish_obs and any(l[i] < ob["btm"] for ob in bullish_obs):
            ob_bull_mitigated[i] = True
            bullish_obs = [ob for ob in bullish_obs if not l[i] < ob["btm"]]
        if bearish_obs and any(h[i] > ob["top"] for ob in bearish_obs):
            ob_bear_mitigated[i] = True
            bearish_obs = [ob for ob in bearish_obs if not h[i] > ob["top"]]

    events = pd.DataFrame(
        {
            f"{prefix}_bos_bullish": bos_bull,
            f"{prefix}_choch_bullish": choch_bull,
            f"{prefix}_bos_bearish": bos_bear,
            f"{prefix}_choch_bearish": choch_bear,
            f"{prefix}_ob_bullish_formed": ob_bull_formed,
            f"{prefix}_ob_bullish_mitigated": ob_bull_mitigated,
            f"{prefix}_ob_bearish_formed": ob_bear_formed,
            f"{prefix}_ob_bearish_mitigated": ob_bear_mitigated,
        },
        index=high.index,
    )
    return events, cur_high_level, cur_low_level


def _parsed_high_low(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Volatility-adjusted high/low used for order-block extreme selection
    (SMC Section 2.3): swap high/low on abnormally wide-range bars so a
    single outlier bar isn't mistaken for the order block.
    """
    if SMC.ob_filter_mode == "Atr":
        vol = atr(df["high"], df["low"], df["close"], SMC.ob_atr_len)
    else:
        tr = true_range(df["high"], df["low"], df["close"])
        vol = tr.cumsum() / np.arange(1, len(df) + 1)
    high_vol_bar = (df["high"] - df["low"]) >= (2 * vol)
    parsed_high = np.where(high_vol_bar, df["low"], df["high"])
    parsed_low = np.where(high_vol_bar, df["high"], df["low"])
    return parsed_high, parsed_low


def detect_structure(df: pd.DataFrame) -> pd.DataFrame:
    """SMC Section 2.2/2.3: Swing-scale then Internal-scale BOS/CHoCH + OB."""
    parsed_high, parsed_low = _parsed_high_low(df)

    swing_events, swing_hi_level, swing_lo_level = _structure_and_ob(
        df["high"], df["low"], df["close"], df["open"],
        size=SMC.swing_len, prefix="smc_swing",
        parsed_high=parsed_high, parsed_low=parsed_low,
    )
    internal_events, _, _ = _structure_and_ob(
        df["high"], df["low"], df["close"], df["open"],
        size=SMC.internal_len, prefix="smc_internal",
        other_high_level=swing_hi_level, other_low_level=swing_lo_level,
        confluence=SMC.internal_filter_confluence,
        parsed_high=parsed_high, parsed_low=parsed_low,
    )
    return pd.concat([swing_events, internal_events], axis=1)


def detect_equal_highs_lows(
    df: pd.DataFrame, size: int | None = None, threshold: float | None = None
) -> pd.DataFrame:
    """SMC Section 2.4."""
    size = SMC.equal_hl_len if size is None else size
    threshold = SMC.equal_hl_threshold if threshold is None else threshold
    swing_high, swing_low = extract_swing_points(df["high"], df["low"], size)
    atr_measure = atr(df["high"], df["low"], df["close"], SMC.equal_hl_atr_len)

    high_vals = swing_high.dropna()
    low_vals = swing_low.dropna()

    eq_high = pd.Series(False, index=df.index)
    eq_low = pd.Series(False, index=df.index)

    prev_h = None
    for idx, val in high_vals.items():
        if prev_h is not None:
            tol = threshold * atr_measure.loc[idx]
            if not np.isnan(tol) and abs(val - prev_h) < tol:
                eq_high.loc[idx] = True
        prev_h = val

    prev_l = None
    for idx, val in low_vals.items():
        if prev_l is not None:
            tol = threshold * atr_measure.loc[idx]
            if not np.isnan(tol) and abs(val - prev_l) < tol:
                eq_low.loc[idx] = True
        prev_l = val

    return pd.DataFrame({"smc_equal_highs": eq_high, "smc_equal_lows": eq_low})


def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """SMC Section 2.5: adaptive %-move-threshold 3-candle gap."""
    close, open_, high, low = df["close"], df["open"], df["high"], df["low"]
    bar_delta_pct = (close.shift(1) - open_.shift(1)) / (open_.shift(1) * 100)
    n = np.arange(1, len(df) + 1)
    threshold = (bar_delta_pct.abs().cumsum() / n * 2) if SMC.fvg_auto_threshold else pd.Series(0.0, index=df.index)

    last2_high = high.shift(2)
    last2_low = low.shift(2)

    bullish = (low > last2_high) & (close.shift(1) > last2_high) & (bar_delta_pct > threshold)
    bearish = (high < last2_low) & (close.shift(1) < last2_low) & ((-bar_delta_pct) > threshold)

    return pd.DataFrame(
        {
            "smc_fvg_bullish_formed": bullish.fillna(False),
            "smc_fvg_bearish_formed": bearish.fillna(False),
        }
    )


def detect_zones(df: pd.DataFrame, window: int | None = None) -> pd.DataFrame:
    """SMC Section 2.6/2.7: Premium/Discount/Equilibrium zones and Strong/Weak
    High/Low, computed against the trailing extreme range.

    `window=None` reproduces the literal Pine behavior (all-time expanding
    high/low, see Ambiguity A3); pass an int for the rolling-window
    robustness-check variant used in Task 12.
    """
    if window is None:
        trailing_top = df["high"].cummax()
        trailing_bottom = df["low"].cummin()
    else:
        trailing_top = df["high"].rolling(window, min_periods=1).max()
        trailing_bottom = df["low"].rolling(window, min_periods=1).min()

    band = SMC.premium_discount_band
    premium_lo = (1 - band) * trailing_top + band * trailing_bottom
    discount_hi = (1 - band) * trailing_bottom + band * trailing_top

    zone = pd.Series("equilibrium", index=df.index)
    zone[df["close"] >= premium_lo] = "premium"
    zone[df["close"] <= discount_hi] = "discount"

    return pd.DataFrame(
        {
            "smc_zone": zone,
            "smc_trailing_top": trailing_top,
            "smc_trailing_bottom": trailing_bottom,
        }
    )


def detect_mtf_levels(df: pd.DataFrame) -> pd.DataFrame:
    """SMC Section 2.8: prior Day/Week/Month high & low as reference levels."""
    prior_day_high = df["high"].shift(1)
    prior_day_low = df["low"].shift(1)

    weekly = df.resample("W").agg(high=("high", "max"), low=("low", "min"))
    monthly = df.resample("ME").agg(high=("high", "max"), low=("low", "min"))

    prior_week = weekly.shift(1).reindex(df.index, method="ffill")
    prior_month = monthly.shift(1).reindex(df.index, method="ffill")

    return pd.DataFrame(
        {
            "smc_prior_day_high": prior_day_high,
            "smc_prior_day_low": prior_day_low,
            "smc_prior_week_high": prior_week["high"],
            "smc_prior_week_low": prior_week["low"],
            "smc_prior_month_high": prior_month["high"],
            "smc_prior_month_low": prior_month["low"],
        }
    )


def detect_all_smc(df: pd.DataFrame) -> pd.DataFrame:
    """Run every SMC detector and concatenate into one wide event frame."""
    parts = [
        detect_structure(df),
        detect_equal_highs_lows(df),
        detect_fvg(df),
        detect_zones(df),
        detect_mtf_levels(df),
    ]
    return pd.concat(parts, axis=1)
