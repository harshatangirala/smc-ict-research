"""ICT Concepts [LuxAlgo] signal detectors, translated from
docs/reference/ICT_Concepts_LuxAlgo.pine per the spec in
docs/concepts_extraction.md (Section 1) and docs/task02_pine_analysis.md.

Every function takes a date-indexed OHLCV dataframe and returns boolean/float
event columns aligned to the same index. Formation events are the primary,
fully-faithful translation target; mitigation/fill states are implemented
with a bounded forward-search simplification (documented inline) since the
backtest engine consumes formation events + forward returns, not on-chart
fill animation.

No look-ahead: every signal at bar i only uses data from bars <= i (pivot
confirmation lag is preserved explicitly, matching Pine's ta.pivothigh/low).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pine_parser.atr import atr
from pine_parser.legs import extract_swing_points
from pine_parser.pivots import pivot_high, pivot_low
from utils.config import ICT

MAX_FORWARD_SEARCH = 60  # bars; matches the longest backtest holding period


def _mx_mn(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    mx = df[["close", "open"]].max(axis=1)
    mn = df[["close", "open"]].min(axis=1)
    return mx, mn


def detect_displacement(df: pd.DataFrame, length: int = ICT.mss_pivot_len) -> pd.DataFrame:
    """ICT Section 1.4: clean-body, above-average-range candle."""
    mx, mn = _mx_mn(df)
    body = (df["close"] - df["open"]).abs()
    mean_body = body.rolling(length).mean()
    clean_body = (
        (df["high"] - mx < body * ICT.displacement_perc_body)
        & (mn - df["low"] < body * ICT.displacement_perc_body)
    )
    up = (body > mean_body) & clean_body & (df["close"] > df["open"])
    dn = (body > mean_body) & clean_body & (df["close"] < df["open"])
    return pd.DataFrame({"ict_displacement_bullish": up.fillna(False), "ict_displacement_bearish": dn.fillna(False)})


def detect_volume_imbalance(df: pd.DataFrame) -> pd.DataFrame:
    """ICT Section 1.5."""
    mx, mn = _mx_mn(df)
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bull = (
        (o > c.shift(1)) & (h.shift(1) > l) & (c > c.shift(1))
        & (o > o.shift(1)) & (h.shift(1) < mn)
    )
    bear = (
        (o < c.shift(1)) & (l.shift(1) < h) & (c < c.shift(1))
        & (o < o.shift(1)) & (l.shift(1) > mx)
    )
    return pd.DataFrame(
        {"ict_volume_imbalance_bullish": bull.fillna(False), "ict_volume_imbalance_bearish": bear.fillna(False)}
    )


def detect_fvg(df: pd.DataFrame, mode: str = ICT.fvg_mode) -> pd.DataFrame:
    """ICT Section 1.6: 3-candle gap, gated by a displacement candle one bar prior."""
    disp = detect_displacement(df)
    up_disp_prev = disp["ict_displacement_bullish"].shift(1).fillna(False)
    dn_disp_prev = disp["ict_displacement_bearish"].shift(1).fillna(False)

    h2, l2 = df["high"].shift(2), df["low"].shift(2)
    if mode == "FVG":
        imbalance_up = up_disp_prev & (df["low"] > h2)
        imbalance_dn = dn_disp_prev & (df["high"] < l2)
    else:  # 'IFVG' -- LuxAlgo's literal (non-standard) definition, see Ambiguity A1
        imbalance_up = up_disp_prev & (df["low"] < h2)
        imbalance_dn = dn_disp_prev & (df["high"] > l2)

    top_up = np.where(imbalance_up, df["high"].shift(2), np.nan)
    bot_up = np.where(imbalance_up, df["low"], np.nan)
    top_dn = np.where(imbalance_dn, df["high"], np.nan)
    bot_dn = np.where(imbalance_dn, df["low"].shift(2), np.nan)

    filled_up = _bounded_forward_fill(df["low"].to_numpy(), bot_up, imbalance_up.to_numpy(), "below")
    filled_dn = _bounded_forward_fill(df["high"].to_numpy(), top_dn, imbalance_dn.to_numpy(), "above")

    return pd.DataFrame(
        {
            "ict_fvg_bullish_formed": imbalance_up.fillna(False),
            "ict_fvg_bullish_top": top_up,
            "ict_fvg_bullish_bottom": bot_up,
            "ict_fvg_bullish_filled": filled_up,
            "ict_fvg_bearish_formed": imbalance_dn.fillna(False),
            "ict_fvg_bearish_top": top_dn,
            "ict_fvg_bearish_bottom": bot_dn,
            "ict_fvg_bearish_filled": filled_dn,
        },
        index=df.index,
    )


def _bounded_forward_fill(
    price: np.ndarray, boundary: np.ndarray, formed: np.ndarray, direction: str
) -> np.ndarray:
    """For each formation bar, was the gap boundary breached within
    MAX_FORWARD_SEARCH bars? Bounded simplification documented in the module
    docstring -- exact for horizons <= MAX_FORWARD_SEARCH, which covers every
    holding period this project backtests.
    """
    n = len(price)
    out = np.zeros(n, dtype=bool)
    idx = np.where(formed)[0]
    for i in idx:
        end = min(n, i + 1 + MAX_FORWARD_SEARCH)
        window = price[i + 1 : end]
        if len(window) == 0:
            continue
        b = boundary[i]
        out[i] = (window < b).any() if direction == "below" else (window > b).any()
    return out


def detect_bpr(df: pd.DataFrame) -> pd.DataFrame:
    """ICT Section 1.7: overlap of the most recent bullish and bearish FVG.

    Simplification: evaluated using the latest still-open FVG on each side as
    of each bar (forward-filled boundaries), matching the source's "most
    recent FVG box" semantics without replaying the exact box-mutation
    sequence.
    """
    fvg = detect_fvg(df)
    up_top = fvg["ict_fvg_bullish_top"].where(fvg["ict_fvg_bullish_formed"]).ffill()
    up_bot = fvg["ict_fvg_bullish_bottom"].where(fvg["ict_fvg_bullish_formed"]).ffill()
    dn_top = fvg["ict_fvg_bearish_top"].where(fvg["ict_fvg_bearish_formed"]).ffill()
    dn_bot = fvg["ict_fvg_bearish_bottom"].where(fvg["ict_fvg_bearish_formed"]).ffill()

    bull_bpr = (up_bot < dn_top) & (dn_bot < up_bot) & fvg["ict_fvg_bullish_formed"].cumsum().gt(0)
    bear_bpr = (dn_bot < up_top) & (up_bot < dn_bot) & fvg["ict_fvg_bearish_formed"].cumsum().gt(0)

    return pd.DataFrame(
        {"ict_bpr_bullish": bull_bpr.fillna(False), "ict_bpr_bearish": bear_bpr.fillna(False)}
    )


def detect_mss_bos(df: pd.DataFrame, length: int = ICT.mss_pivot_len) -> pd.DataFrame:
    """ICT Section 1.1 + 1.2: zigzag pivots -> Market Structure Shift -> BOS.

    Sequential (stateful) by necessity -- mirrors Pine's aZZ ring buffer and
    MSS.dir state machine bar by bar.
    """
    _, conf_high = pivot_high(df["high"], length, 1)
    _, conf_low = pivot_low(df["low"], length, 1)
    high_val = df["high"].shift(1).to_numpy()  # Pine: y2 := nz(hi[1]) at the confirmation bar
    low_val = df["low"].shift(1).to_numpy()
    close = df["close"].to_numpy()
    n = len(df)

    # zigzag vertices: list of (direction, price); direction 1=up-vertex(from a low), -1=down-vertex
    vertices: list[tuple[int, float]] = []
    mss_dir = 0
    mss_bull = np.zeros(n, dtype=bool)
    mss_bear = np.zeros(n, dtype=bool)
    bos_bull = np.zeros(n, dtype=bool)
    bos_bear = np.zeros(n, dtype=bool)
    last_mss_level_bull = np.nan
    last_mss_level_bear = np.nan
    last_bos_level_bull = np.nan
    last_bos_level_bear = np.nan

    is_ph = conf_high.to_numpy()
    is_pl = conf_low.to_numpy()

    for i in range(n):
        if is_ph[i]:
            top = high_val[i]
            if not vertices or vertices[-1][0] != 1:
                vertices.append((1, top))
            else:
                if top > vertices[-1][1]:
                    vertices[-1] = (1, top)
        if is_pl[i]:
            btm = low_val[i]
            if not vertices or vertices[-1][0] != -1:
                vertices.append((-1, btm))
            else:
                if btm < vertices[-1][1]:
                    vertices[-1] = (-1, btm)

        if len(vertices) < 2:
            continue

        # iH: most recent up-vertex (swing high); iL: most recent down-vertex (swing low)
        up_vertices = [p for d, p in vertices if d == 1]
        dn_vertices = [p for d, p in vertices if d == -1]
        if not up_vertices or not dn_vertices:
            continue
        swing_high = up_vertices[-1]
        swing_low = dn_vertices[-1]

        if close[i] > swing_high and mss_dir < 1:
            mss_dir = 1
            mss_bull[i] = True
            last_mss_level_bull = swing_high
        elif close[i] < swing_low and mss_dir > -1:
            mss_dir = -1
            mss_bear[i] = True
            last_mss_level_bear = swing_low
        elif mss_dir == 1 and close[i] > swing_high:
            if swing_high != last_bos_level_bull and swing_high != last_mss_level_bull:
                bos_bull[i] = True
                last_bos_level_bull = swing_high
        elif mss_dir == -1 and close[i] < swing_low:
            if swing_low != last_bos_level_bear and swing_low != last_mss_level_bear:
                bos_bear[i] = True
                last_bos_level_bear = swing_low

    return pd.DataFrame(
        {
            "ict_mss_bullish": mss_bull,
            "ict_mss_bearish": mss_bear,
            "ict_bos_bullish": bos_bull,
            "ict_bos_bearish": bos_bear,
        },
        index=df.index,
    )


def detect_order_blocks(df: pd.DataFrame, length: int = ICT.ob_swing_len, use_body: bool = ICT.ob_use_body) -> pd.DataFrame:
    """ICT Section 1.3: order blocks formed at the extreme candle between a
    swing point and the bar structure breaks it, with breaker-block
    (mitigation) state tracking.

    Pine's `swings()` returns a *single* persistent `top`/`btm` swing object
    (`var swing top = swing.new(na, na)`) that is completely replaced --
    including its `.crossed` flag resetting to false -- every time a newer
    swing point of that type is confirmed. An older, never-broken swing
    point is therefore silently forgotten, not queued for later testing.
    This must track only the *most recent* swing point per side (not a
    FIFO queue of every historical swing) or it silently gets stuck forever
    on the first swing point that never breaks (confirmed bug found during
    Task 6 validation: AAPL produced zero bearish order blocks across 16
    years because the code was stuck testing its all-time-low 2010 swing).
    """
    mx, mn = _mx_mn(df)
    max_src = mx if use_body else df["high"]
    min_src = mn if use_body else df["low"]

    swing_high, swing_low = extract_swing_points(df["high"], df["low"], length)
    close = df["close"].to_numpy()
    open_ = df["open"].to_numpy()
    max_arr = max_src.to_numpy()
    min_arr = min_src.to_numpy()
    n = len(df)

    bull_formed = np.zeros(n, dtype=bool)
    bear_formed = np.zeros(n, dtype=bool)
    bull_mitigated = np.zeros(n, dtype=bool)
    bear_mitigated = np.zeros(n, dtype=bool)

    bullish_obs: list[dict] = []  # active bullish order blocks
    bearish_obs: list[dict] = []

    sh = swing_high.to_numpy()
    sl = swing_low.to_numpy()

    top_level, top_bar, top_crossed = np.nan, -1, True
    btm_level, btm_bar, btm_crossed = np.nan, -1, True

    for i in range(n):
        if not np.isnan(sh[i]):
            top_level = sh[i]
            top_bar = i - length
            top_crossed = False
        if not np.isnan(sl[i]):
            btm_level = sl[i]
            btm_bar = i - length
            btm_crossed = False

        if not top_crossed and not np.isnan(top_level) and close[i] > top_level:
            top_crossed = True
            lo = max(top_bar, 0)
            seg_min = min_arr[lo : i + 1]
            seg_max = max_arr[lo : i + 1]
            if len(seg_min) > 0:
                j = int(np.argmin(seg_min))
                bullish_obs.append({"top": seg_max[j], "btm": seg_min[j], "breaker": False})
                if len(bullish_obs) > ICT.ob_max_retained:
                    bullish_obs.pop(0)
                bull_formed[i] = True

        if not btm_crossed and not np.isnan(btm_level) and close[i] < btm_level:
            btm_crossed = True
            lo = max(btm_bar, 0)
            seg_min = min_arr[lo : i + 1]
            seg_max = max_arr[lo : i + 1]
            if len(seg_max) > 0:
                j = int(np.argmax(seg_max))
                bearish_obs.append({"top": seg_max[j], "btm": seg_min[j], "breaker": False})
                if len(bearish_obs) > ICT.ob_max_retained:
                    bearish_obs.pop(0)
                bear_formed[i] = True

        # Mitigation checks
        for ob in bullish_obs:
            if not ob["breaker"] and min(close[i], open_[i]) < ob["btm"]:
                ob["breaker"] = True
                bull_mitigated[i] = True
        for ob in bearish_obs:
            if not ob["breaker"] and max(close[i], open_[i]) > ob["top"]:
                ob["breaker"] = True
                bear_mitigated[i] = True

    return pd.DataFrame(
        {
            "ict_ob_bullish_formed": bull_formed,
            "ict_ob_bullish_mitigated": bull_mitigated,
            "ict_ob_bearish_formed": bear_formed,
            "ict_ob_bearish_mitigated": bear_mitigated,
        },
        index=df.index,
    )


def detect_liquidity(df: pd.DataFrame, length: int = ICT.mss_pivot_len, margin: float = ICT.liquidity_margin) -> pd.DataFrame:
    """ICT Section 1.8: clustered-pivot liquidity pools and sweeps."""
    _, conf_high = pivot_high(df["high"], length, 1)
    _, conf_low = pivot_low(df["low"], length, 1)
    high_val = df["high"].shift(1).to_numpy()
    low_val = df["low"].shift(1).to_numpy()
    close = df["close"].to_numpy()
    a = 10.0 / margin
    atr10 = atr(df["high"], df["low"], df["close"], ICT.liquidity_atr_len).to_numpy()
    n = len(df)

    buy_pool_formed = np.zeros(n, dtype=bool)
    sell_pool_formed = np.zeros(n, dtype=bool)
    buy_swept = np.zeros(n, dtype=bool)
    sell_swept = np.zeros(n, dtype=bool)

    vertices: list[tuple[int, float]] = []
    active_buy_pool = None  # dict(top, bottom, brokenTop, brokenBtm)
    active_sell_pool = None

    is_ph = conf_high.to_numpy()
    is_pl = conf_low.to_numpy()

    for i in range(n):
        if is_ph[i]:
            top = high_val[i]
            if not vertices or vertices[-1][0] != 1:
                vertices.append((1, top))
            else:
                if top > vertices[-1][1]:
                    vertices[-1] = (1, top)

            band = atr10[i] / a if not np.isnan(atr10[i]) else 0
            same_dir = [p for d, p in vertices[-50:] if d == 1]
            cluster = [p for p in same_dir if abs(p - top) < band and top - band < p < top + band]
            if len(cluster) > ICT.liquidity_min_cluster:
                lo, hi = min(cluster), max(cluster)
                mid = (lo + hi) / 2
                active_buy_pool = {"top": mid + band, "bottom": mid - band, "brokenTop": False, "brokenBtm": False}
                buy_pool_formed[i] = True

        if is_pl[i]:
            btm = low_val[i]
            if not vertices or vertices[-1][0] != -1:
                vertices.append((-1, btm))
            else:
                if btm < vertices[-1][1]:
                    vertices[-1] = (-1, btm)

            band = atr10[i] / a if not np.isnan(atr10[i]) else 0
            same_dir = [p for d, p in vertices[-50:] if d == -1]
            cluster = [p for p in same_dir if abs(p - btm) < band and btm - band < p < btm + band]
            if len(cluster) > ICT.liquidity_min_cluster:
                lo, hi = min(cluster), max(cluster)
                mid = (lo + hi) / 2
                active_sell_pool = {"top": mid + band, "bottom": mid - band, "brokenTop": False, "brokenBtm": False}
                sell_pool_formed[i] = True

        if active_buy_pool is not None and not (active_buy_pool["brokenTop"] and active_buy_pool["brokenBtm"]):
            if close[i] > active_buy_pool["top"]:
                active_buy_pool["brokenTop"] = True
            if close[i] > active_buy_pool["bottom"]:
                if not active_buy_pool["brokenBtm"]:
                    buy_swept[i] = True
                active_buy_pool["brokenBtm"] = True

        if active_sell_pool is not None and not (active_sell_pool["brokenTop"] and active_sell_pool["brokenBtm"]):
            if close[i] < active_sell_pool["bottom"]:
                active_sell_pool["brokenBtm"] = True
            if close[i] < active_sell_pool["top"]:
                if not active_sell_pool["brokenTop"]:
                    sell_swept[i] = True
                active_sell_pool["brokenTop"] = True

    return pd.DataFrame(
        {
            "ict_liquidity_buyside_pool_formed": buy_pool_formed,
            "ict_liquidity_buyside_swept": buy_swept,
            "ict_liquidity_sellside_pool_formed": sell_pool_formed,
            "ict_liquidity_sellside_swept": sell_swept,
        },
        index=df.index,
    )


def detect_nwog_ndog(df: pd.DataFrame) -> pd.DataFrame:
    """ICT Section 1.9. On daily bars this reduces to simple gap checks;
    NWOG uses the most recent completed week's Friday close (see Ambiguity
    A7 -- deliberately not replicating the stale-on-holiday var carry-over).
    """
    dow = df.index.to_series().dt.dayofweek  # Monday=0 ... Sunday=6
    is_monday = dow == 0
    prior_close = df["close"].shift(1)

    ndog_gap = (df["open"] - prior_close).abs()
    ndog_formed = pd.Series(True, index=df.index) & df["open"].notna() & prior_close.notna()

    # NWOG: only meaningful on the first trading bar after a weekend/gap in
    # weekday sequence (Monday, or the first bar after a multi-day gap).
    day_gap = dow.diff().fillna(1)
    is_week_open = (day_gap < 0) | (day_gap > 1) | ((dow == 0) & (day_gap != 0))
    nwog_formed = is_week_open & df["open"].notna() & prior_close.notna()
    nwog_gap = (df["open"] - prior_close).abs()

    return pd.DataFrame(
        {
            "ict_nwog_formed": nwog_formed.fillna(False),
            "ict_nwog_gap_size": nwog_gap,
            "ict_ndog_formed": ndog_formed.fillna(False),
            "ict_ndog_gap_size": ndog_gap,
        }
    )


def detect_all_ict(df: pd.DataFrame) -> pd.DataFrame:
    """Run every ICT detector and concatenate into one wide event frame."""
    parts = [
        detect_displacement(df),
        detect_volume_imbalance(df),
        detect_fvg(df),
        detect_bpr(df),
        detect_mss_bos(df),
        detect_order_blocks(df),
        detect_liquidity(df),
        detect_nwog_ndog(df),
    ]
    return pd.concat(parts, axis=1)
