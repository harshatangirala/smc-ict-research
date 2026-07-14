"""Two-sided confirmed pivot detector: TradingView's ta.pivothigh/ta.pivotlow.

Used by ICT's zigzag engine (docs/task02_pine_analysis.md Section 1.1, the
basis for MSS/BOS and Liquidity pools). A pivot high at bar i (with left/right
lookback) requires high[i] to be the maximum over the symmetric window
[i-left, i+right]; it only becomes *knowable* once `right` further bars have
closed, so the confirmed signal must be read `right` bars after the pivot
bar itself -- this file returns both the pivot's own bar location (for
price/return anchoring) and the confirmation bar (for no-look-ahead gating).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _pivot(series: pd.Series, left: int, right: int, mode: str) -> pd.Series:
    values = series.to_numpy(dtype=float)
    n = len(values)
    is_pivot = np.zeros(n, dtype=bool)

    for i in range(left, n - right):
        window = values[i - left : i + right + 1]
        center = values[i]
        if np.isnan(window).any():
            continue
        if mode == "high":
            if center == window.max() and np.argmax(window) == left:
                is_pivot[i] = True
        else:
            if center == window.min() and np.argmin(window) == left:
                is_pivot[i] = True

    return pd.Series(is_pivot, index=series.index)


def pivot_high(high: pd.Series, left: int, right: int) -> tuple[pd.Series, pd.Series]:
    """Returns (is_pivot_at_bar, confirmed_at_bar) boolean series.

    `is_pivot_at_bar[i]` is True on the bar that *is* the swing high.
    `confirmed_at_bar[i]` is True on the bar where that pivot becomes known
    to a no-look-ahead strategy (i.e. `is_pivot_at_bar` shifted forward by
    `right` bars) -- always use `confirmed_at_bar` for signal gating.
    """
    is_pivot = _pivot(high, left, right, "high")
    confirmed = is_pivot.shift(right).fillna(False).astype(bool)
    confirmed.index = high.index
    return is_pivot, confirmed


def pivot_low(low: pd.Series, left: int, right: int) -> tuple[pd.Series, pd.Series]:
    is_pivot = _pivot(low, left, right, "low")
    confirmed = is_pivot.shift(right).fillna(False).astype(bool)
    confirmed.index = low.index
    return is_pivot, confirmed
