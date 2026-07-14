"""Regression test for the order-block "stuck on the first swing forever"
bug found and fixed during Task 6 validation (see docs/task02_pine_analysis.md
and the Task 5-6 commit message): Pine's swings() always replaces the
tracked swing point with the newest one, so an old unbroken swing must be
forgotten, not queued forever.
"""

import numpy as np
import pandas as pd

from signals.ict_signals import detect_order_blocks


def test_bearish_ob_fires_on_a_later_swing_even_if_the_first_swing_never_breaks():
    # Construct a series with an early, very deep swing low (never broken
    # again) followed by a shallower, more recent swing low that DOES get
    # broken. A "stuck on the first swing" bug would report zero bearish
    # order blocks; correct behavior fires on the later, broken swing.
    n = 120
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    close = np.full(n, 100.0)

    # Deep early low around bar 10 (never revisited).
    close[5:15] = np.linspace(100, 40, 10)
    close[15:30] = np.linspace(40, 100, 15)
    # Uptrend with a shallow local low around bar 60 that IS broken shortly after.
    close[30:60] = np.linspace(100, 130, 30)
    close[60:70] = np.linspace(130, 110, 10)  # shallow pullback low ~110
    close[70:80] = np.linspace(110, 125, 10)
    close[80:95] = np.linspace(125, 95, 15)  # breaks back below the shallow low (~110)
    close[95:] = np.linspace(95, 90, n - 95)

    high = close + 1
    low = close - 1
    open_ = close.copy()

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

    result = detect_order_blocks(df, length=5)
    assert result["ict_ob_bearish_formed"].sum() > 0, (
        "Bearish order block never fired -- regression of the "
        "'stuck on first unbroken swing' bug"
    )
