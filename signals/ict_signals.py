# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Translated from LuxAlgo's Pine Script logic -- see NOTICE and
# LICENSE-CC-BY-NC-SA, not the repository's default MIT license.
"""ICT Concepts [LuxAlgo] signal detectors, translated from
docs/reference/ICT_Concepts_LuxAlgo.pine per the spec in
docs/concepts_extraction.md (Section 1) and docs/task02_pine_analysis.md.

Every function takes a date-indexed OHLCV dataframe and returns boolean/float
event columns aligned to the same index. Formation events are the primary,
fully-faithful translation target; mitigation/fill states are implemented
with a bounded forward-search simplification (documented inline) since the
backtest engine consumes formation events + forward returns, not on-chart
fill animation.

No look-ahead: every *event* column at bar i uses only bars <= i (pivot
confirmation lag is preserved explicitly, matching Pine's ta.pivothigh/low).

Detection vs. evaluation labels
-------------------------------
Columns whose name ends in ``_label`` are FORWARD-LOOKING BY DESIGN. They
answer "what happened after this event?" (e.g. was an FVG later filled) and
exist only as outcome labels for descriptive statistics. They are excluded
from the tradeable event table by ``signals.event_engine.EVENT_REGISTRY`` and
must never be used as entry signals.

This separation is the fix for a confirmed look-ahead leak: the previous
``ict_fvg_bullish_filled`` / ``ict_fvg_bearish_filled`` columns were plain
booleans, so ``melt_events`` -- which selected every bool column -- emitted
them as tradeable entries at the *formation* bar while their value was
computed from up to 60 *subsequent* bars. 187,719 look-ahead events reached the
published results, and both columns land at the extremes of the concept
ranking as a direct artifact. See tests/test_no_lookahead.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pine_parser.atr import atr
from pine_parser.legs import extract_swing_points
from pine_parser.pivots import pivot_high, pivot_low
from utils.config import ICT

MAX_FORWARD_SEARCH = 60  # bars; matches the longest backtest holding period (N in the FVG-fill rule)


def _mx_mn(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    mx = df[["close", "open"]].max(axis=1)
    mn = df[["close", "open"]].min(axis=1)
    return mx, mn


def detect_displacement(df: pd.DataFrame, length: int | None = None) -> pd.DataFrame:
    """ICT Section 1.4: clean-body, above-average-range candle."""
    length = ICT.mss_pivot_len if length is None else length
    perc_body = ICT.displacement_perc_body
    mx, mn = _mx_mn(df)
    body = (df["close"] - df["open"]).abs()
    mean_body = body.rolling(length).mean()
    clean_body = (
        (df["high"] - mx < body * perc_body)
        & (mn - df["low"] < body * perc_body)
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


def detect_fvg(
    df: pd.DataFrame, mode: str | None = None, fill_window: int | None = None
) -> pd.DataFrame:
    """ICT Section 1.6: 3-candle gap, gated by a displacement candle one bar prior.

    Formal rule (docs/specs/ict_fvg.yaml)
    ------------------------------------
    Bullish FVG forms at bar i iff bar i-1 was a bullish displacement candle
    and ``low[i] > high[i-2]`` (a true 3-bar gap). The gap region is
    ``[high[i-2], low[i]]``.

    "Filled" is an OUTCOME LABEL, not a detection input: the gap counts as
    filled if price enters the gap region within ``fill_window`` bars *after*
    formation (default N = 60 = the longest holding period backtested). It is
    returned with a ``_label`` suffix and is excluded from the tradeable event
    table -- see the module docstring.
    """
    mode = ICT.fvg_mode if mode is None else mode
    fill_window = MAX_FORWARD_SEARCH if fill_window is None else fill_window
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

    # Gap regions, stored as (lower edge, upper edge). The previous code named
    # these "top"/"bottom" the other way round: a bullish FVG spans
    # [high[i-2], low[i]] with high[i-2] < low[i], so the column called "_top"
    # actually held the LOWER edge. detect_bpr then compared them as if the
    # naming were literal, producing an unsatisfiable condition -- which is why
    # ict_bpr_bullish/bearish fired exactly zero times across the entire
    # universe and silently never reached the event table.
    lo_up = np.where(imbalance_up, df["high"].shift(2), np.nan)
    hi_up = np.where(imbalance_up, df["low"], np.nan)
    lo_dn = np.where(imbalance_dn, df["high"], np.nan)
    hi_dn = np.where(imbalance_dn, df["low"].shift(2), np.nan)

    filled_up = _bounded_forward_fill(
        df["low"].to_numpy(), lo_up, imbalance_up.to_numpy(), "below", fill_window
    )
    filled_dn = _bounded_forward_fill(
        df["high"].to_numpy(), hi_dn, imbalance_dn.to_numpy(), "above", fill_window
    )

    return pd.DataFrame(
        {
            "ict_fvg_bullish_formed": imbalance_up.fillna(False),
            "ict_fvg_bullish_lower": lo_up,
            "ict_fvg_bullish_upper": hi_up,
            "ict_fvg_bullish_filled_label": filled_up,
            "ict_fvg_bearish_formed": imbalance_dn.fillna(False),
            "ict_fvg_bearish_lower": lo_dn,
            "ict_fvg_bearish_upper": hi_dn,
            "ict_fvg_bearish_filled_label": filled_dn,
        },
        index=df.index,
    )


def _bounded_forward_fill(
    price: np.ndarray,
    boundary: np.ndarray,
    formed: np.ndarray,
    direction: str,
    window: int = MAX_FORWARD_SEARCH,
) -> np.ndarray:
    """For each formation bar, was the gap boundary breached within `window`
    bars *after* it?

    FORWARD-LOOKING BY CONSTRUCTION. The result is stamped on the formation
    bar, so it is only ever valid as an outcome label -- never as an entry
    signal. Callers must surface it with a ``_label`` suffix.
    """
    n = len(price)
    out = np.zeros(n, dtype=bool)
    idx = np.where(formed)[0]
    for i in idx:
        end = min(n, i + 1 + window)
        seg = price[i + 1 : end]
        if len(seg) == 0:
            continue
        b = boundary[i]
        out[i] = (seg < b).any() if direction == "below" else (seg > b).any()
    return out


def detect_bpr(df: pd.DataFrame) -> pd.DataFrame:
    """ICT Section 1.7: Balanced Price Range -- the overlap of the most recent
    bullish and bearish Fair Value Gaps.

    Two intervals ``[a_lo, a_hi]`` and ``[b_lo, b_hi]`` overlap iff
    ``max(a_lo, b_lo) < min(a_hi, b_hi)``. The event fires on the bar the
    *second* of the two gaps forms, which is the bar on which the overlap
    first becomes observable, so the detector stays causal.

    Bug fixed here
    --------------
    The previous condition was ``(up_bot < dn_top) & (dn_bot < up_bot)``,
    written against column names whose meaning was inverted (see
    ``detect_fvg``). Substituting the real edges makes it require
    ``dn_upper < dn_lower``, which is unsatisfiable by construction -- so
    ``ict_bpr_bullish`` and ``ict_bpr_bearish`` were identically False for
    every ticker and every bar. ``melt_events`` drops all-False columns
    silently, so the two concepts vanished from the study without any error:
    the "42 concepts tested" headline was really 42 of 44 declared detectors.
    """
    fvg = detect_fvg(df)
    formed_up = fvg["ict_fvg_bullish_formed"]
    formed_dn = fvg["ict_fvg_bearish_formed"]

    # Most recent gap of each polarity, carried forward.
    up_lo = fvg["ict_fvg_bullish_lower"].where(formed_up).ffill()
    up_hi = fvg["ict_fvg_bullish_upper"].where(formed_up).ffill()
    dn_lo = fvg["ict_fvg_bearish_lower"].where(formed_dn).ffill()
    dn_hi = fvg["ict_fvg_bearish_upper"].where(formed_dn).ffill()

    overlap = (
        np.maximum(up_lo, dn_lo) < np.minimum(up_hi, dn_hi)
    ) & up_lo.notna() & dn_lo.notna()

    # Fire only on the bar that completes the pair, not on every subsequent
    # bar the (unchanged) overlap keeps holding.
    bull_bpr = overlap & formed_up
    bear_bpr = overlap & formed_dn

    return pd.DataFrame(
        {"ict_bpr_bullish": bull_bpr.fillna(False), "ict_bpr_bearish": bear_bpr.fillna(False)},
        index=df.index,
    )


def detect_mss_bos(df: pd.DataFrame, length: int | None = None) -> pd.DataFrame:
    """ICT Section 1.1 + 1.2: zigzag pivots -> Market Structure Shift -> BOS.

    Sequential (stateful) by necessity -- mirrors Pine's aZZ ring buffer and
    MSS.dir state machine bar by bar.
    """
    length = ICT.mss_pivot_len if length is None else length
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


def detect_order_blocks(
    df: pd.DataFrame, length: int | None = None, use_body: bool | None = None
) -> pd.DataFrame:
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
    length = ICT.ob_swing_len if length is None else length
    use_body = ICT.ob_use_body if use_body is None else use_body
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
            # Pine: `for i = 1 to (n - top.x) - 1` -- bars strictly between the
            # swing bar and the break bar, [top.x + 1, n - 1]. The first version
            # included both endpoints, so a break bar with a deep lower body
            # could become its own order block. Found in the audit.
            lo = max(top_bar + 1, 0)
            seg_min = min_arr[lo : i]
            seg_max = max_arr[lo : i]
            if len(seg_min) > 0:
                j = int(np.argmin(seg_min))
                bullish_obs.append({"top": seg_max[j], "btm": seg_min[j], "breaker": False})
                if len(bullish_obs) > ICT.ob_max_retained:
                    bullish_obs.pop(0)
                bull_formed[i] = True

        if not btm_crossed and not np.isnan(btm_level) and close[i] < btm_level:
            btm_crossed = True
            # Pine: `for i = 1 to (n - btm.x) - 1` -- mirror of the bullish case.
            lo = max(btm_bar + 1, 0)
            seg_min = min_arr[lo : i]
            seg_max = max_arr[lo : i]
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


def detect_liquidity(
    df: pd.DataFrame, length: int | None = None, margin: float | None = None
) -> pd.DataFrame:
    """ICT Section 1.8: clustered-pivot liquidity pools and sweeps."""
    length = ICT.mss_pivot_len if length is None else length
    margin = ICT.liquidity_margin if margin is None else margin
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


def detect_liquidity_sweep(
    df: pd.DataFrame,
    swing_len: int | None = None,
    penetration_atr: float | None = None,
    reclaim_frac: float | None = None,
    confirm_bars: int | None = None,
) -> pd.DataFrame:
    """Formal, prospective liquidity sweep (stop run + rejection).

    Rule (docs/specs/ict_liquidity_sweep.yaml)
    ------------------------------------------
    Buy-side sweep (bearish reversal expected) at bar ``k``:

    1. ``L`` is the most recently *confirmed* swing high, taken from
       ``extract_swing_points`` so its confirmation lag is preserved.
    2. Penetration at some bar ``j``: ``high[j] > L + X * ATR[j]``.
    3. Reclaim at bar ``k``, with ``j < k <= j + Z``:
       ``close[k] < L - Y * ATR[k]``.

    The event is stamped on bar ``k``, the reclaim bar, and every input is
    from bars ``<= k``, so the detector is causal. This replaces the previous
    ``ict_liquidity_*_swept`` logic, which fired the moment price merely
    *entered* the pool (``close > pool_bottom``) with no rejection leg at all
    -- that is a breakout, not a sweep, and it is why the "swept" signals
    behaved almost identically to the pool-formation signals.

    Sell-side sweep is the mirror image and is bullish.
    """
    swing_len = ICT.sweep_swing_len if swing_len is None else swing_len
    penetration_atr = (
        ICT.sweep_penetration_atr if penetration_atr is None else penetration_atr
    )
    reclaim_frac = ICT.sweep_reclaim_frac if reclaim_frac is None else reclaim_frac
    confirm_bars = ICT.sweep_confirm_bars if confirm_bars is None else confirm_bars
    high, low, close = df["high"], df["low"], df["close"]
    atr_v = atr(high, low, close, ICT.sweep_atr_len).to_numpy()
    swing_high, swing_low = extract_swing_points(high, low, swing_len)
    sh, sl = swing_high.to_numpy(), swing_low.to_numpy()
    h, l, c = high.to_numpy(), low.to_numpy(), close.to_numpy()
    n = len(df)

    buy_sweep = np.zeros(n, dtype=bool)
    sell_sweep = np.zeros(n, dtype=bool)

    level_high = np.nan
    level_low = np.nan
    pen_high_bar, pen_high_level = -1, np.nan
    pen_low_bar, pen_low_level = -1, np.nan

    for i in range(n):
        a = atr_v[i]
        if np.isnan(a):
            if not np.isnan(sh[i]):
                level_high = sh[i]
            if not np.isnan(sl[i]):
                level_low = sl[i]
            continue

        # --- reclaim leg (evaluated before levels are refreshed) ---
        if pen_high_bar >= 0:
            if i - pen_high_bar > confirm_bars:
                pen_high_bar = -1
            elif c[i] < pen_high_level - reclaim_frac * a:
                buy_sweep[i] = True
                pen_high_bar = -1
        if pen_low_bar >= 0:
            if i - pen_low_bar > confirm_bars:
                pen_low_bar = -1
            elif c[i] > pen_low_level + reclaim_frac * a:
                sell_sweep[i] = True
                pen_low_bar = -1

        # --- penetration leg ---
        if not np.isnan(level_high) and h[i] > level_high + penetration_atr * a:
            pen_high_bar, pen_high_level = i, level_high
        if not np.isnan(level_low) and l[i] < level_low - penetration_atr * a:
            pen_low_bar, pen_low_level = i, level_low

        # --- refresh reference levels with newly confirmed swings ---
        if not np.isnan(sh[i]):
            level_high = sh[i]
        if not np.isnan(sl[i]):
            level_low = sl[i]

    return pd.DataFrame(
        {
            # A buy-side sweep runs stops ABOVE highs then rejects -> bearish.
            "ict_sweep_buyside_bearish": buy_sweep,
            "ict_sweep_sellside_bullish": sell_sweep,
        },
        index=df.index,
    )


def detect_nwog_ndog(df: pd.DataFrame) -> pd.DataFrame:
    """ICT Section 1.9: New Week / New Day Opening Gaps.

    Formal rule (docs/specs/ict_opening_gap.yaml)
    --------------------------------------------
    A gap event requires a *material* gap:
    ``|open[i] - close[i-1]| >= gap_min_atr * ATR(gap_atr_len)[i-1]``.

    The previous implementation set ``ict_ndog_formed = True`` on every bar
    with a non-null open and prior close -- i.e. essentially every bar in the
    sample. That produced 1,946,675 "events" (45% of the entire event table)
    for a concept meant to mark notable gaps, and it dominated every pooled
    aggregate it entered. It also ignored the ``ICT.ndog_enabled`` /
    ``ICT.nwog_enabled`` config flags entirely.

    Gaps are also split by direction, which the original did not do: an
    unsigned ``gap_size`` carries no directional hypothesis, so the melted
    event inherited ``direction = 0`` and was forced long by the backtester.
    """
    dow = df.index.to_series().dt.dayofweek  # Monday=0 ... Sunday=6
    prior_close = df["close"].shift(1)
    gap = df["open"] - prior_close
    atr_prev = atr(df["high"], df["low"], df["close"], ICT.gap_atr_len).shift(1)

    material = (gap.abs() >= ICT.gap_min_atr * atr_prev) & gap.notna() & atr_prev.notna()

    # A new week opens on the first bar whose weekday is <= the previous bar's
    # (the calendar week rolled over). This is robust to Monday holidays,
    # unlike the previous `dow.diff() > 1` test, which also fired on a
    # mid-week holiday gap (e.g. Mon -> Wed) and mislabelled it a week open.
    is_week_open = dow.diff().fillna(-1) <= 0

    false_series = pd.Series(False, index=df.index)
    nwog = (material & is_week_open) if ICT.nwog_enabled else false_series
    ndog = material if ICT.ndog_enabled else false_series

    return pd.DataFrame(
        {
            "ict_nwog_gap_up": (nwog & (gap > 0)).fillna(False),
            "ict_nwog_gap_down": (nwog & (gap < 0)).fillna(False),
            "ict_ndog_gap_up": (ndog & (gap > 0)).fillna(False),
            "ict_ndog_gap_down": (ndog & (gap < 0)).fillna(False),
            "ict_nwog_gap_size": gap.abs().where(nwog),
            "ict_ndog_gap_size": gap.abs().where(ndog),
        },
        index=df.index,
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
        detect_liquidity_sweep(df),
        detect_nwog_ndog(df),
    ]
    return pd.concat(parts, axis=1)
