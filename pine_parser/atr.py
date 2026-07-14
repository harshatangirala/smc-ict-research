"""Average True Range using TradingView's ta.atr() convention (Wilder's RMA).

See docs/task02_pine_analysis.md Ambiguity A6: TradingView's ta.atr() is not
a simple moving average of true range -- it uses Wilder's RMA (an EMA with
alpha = 1/length). This must be pinned down before any concept that consumes
ATR (SMC order-block volatility filter, SMC EQH/EQL threshold, ICT liquidity
clustering) is translated, since the wrong smoothing silently shifts which
bars qualify.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Classic true range: max(H-L, |H-Cprev|, |L-Cprev|)."""
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    tr = ranges.max(axis=1)
    tr.iloc[0] = (high.iloc[0] - low.iloc[0])
    return tr


def wilder_rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing (a.k.a. RMA): TradingView's ta.rma().

    Equivalent to an EMA with alpha = 1/length, but seeded with a simple
    average of the first `length` values (Wilder's original definition,
    which is also what Pine's ta.atr()/ta.rma() implement).
    """
    values = series.to_numpy(dtype=float)
    out = np.full_like(values, np.nan)
    if len(values) < length:
        return pd.Series(out, index=series.index)

    out[length - 1] = np.nanmean(values[:length])
    alpha = 1.0 / length
    for i in range(length, len(values)):
        out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
    return pd.Series(out, index=series.index)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """TradingView-equivalent ta.atr(length): Wilder RMA of true range."""
    tr = true_range(high, low, close)
    return wilder_rma(tr, length)
