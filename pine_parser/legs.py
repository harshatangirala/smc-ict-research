"""Rolling-breakout pivot ("leg") detector.

Both source scripts use structurally the same rolling-breakout pivot test,
just under different names and at different default lookbacks:

- SMC's `leg(size)` (docs/task02_pine_analysis.md Section 2.1):
    newLegHigh = high[size] > ta.highest(size)
    newLegLow  = low[size]  < ta.lowest(size)
    var leg = 0 (BEARISH_LEG); leg := BEARISH_LEG on newLegHigh, BULLISH_LEG on newLegLow
- ICT's `swings(len)` (docs/task02_pine_analysis.md Section 1.3), used only for
  Order Block formation, is the identical breakout test; it additionally
  records the swing point's price/bar at the moment of the flip.

Both are implemented here once and reused, since they are the same primitive
(see Task 2 dependency map).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BEARISH_LEG = 0
BULLISH_LEG = 1


def leg_state(high: pd.Series, low: pd.Series, size: int) -> pd.Series:
    """Replicates Pine's `leg(size)` / ICT's `os` state variable.

    Returns an int series: 0 = bearish leg (most recent confirmed extreme was
    a high), 1 = bullish leg (most recent confirmed extreme was a low). State
    persists between bars exactly like Pine's `var` semantics, so this is
    computed with an explicit sequential loop rather than vectorized ops.
    """
    highest_excl = high.rolling(size).max()
    lowest_excl = low.rolling(size).min()
    new_leg_high = (high.shift(size) > highest_excl).fillna(False).to_numpy()
    new_leg_low = (low.shift(size) < lowest_excl).fillna(False).to_numpy()

    n = len(high)
    states = np.zeros(n, dtype=np.int8)
    state = BEARISH_LEG
    for i in range(n):
        if new_leg_high[i]:
            state = BEARISH_LEG
        elif new_leg_low[i]:
            state = BULLISH_LEG
        states[i] = state
    return pd.Series(states, index=high.index, dtype="int8")


def start_of_bullish_leg(leg: pd.Series) -> pd.Series:
    """ta.change(leg) == +1 -- a transition from BEARISH_LEG(0) to BULLISH_LEG(1)."""
    return (leg == BULLISH_LEG) & (leg.shift(1) == BEARISH_LEG)


def start_of_bearish_leg(leg: pd.Series) -> pd.Series:
    """ta.change(leg) == -1 -- a transition from BULLISH_LEG(1) to BEARISH_LEG(0)."""
    return (leg == BEARISH_LEG) & (leg.shift(1) == BULLISH_LEG)


def extract_swing_points(
    high: pd.Series, low: pd.Series, size: int
) -> tuple[pd.Series, pd.Series]:
    """Confirmed swing-high / swing-low price series, aligned to the
    confirmation bar (the bar on which the leg-state transition fires), with
    the price value taken from `size` bars earlier -- exactly Pine's
    `high[size]` / `low[size]` at the moment of the flip.

    Returns (swing_high, swing_low): each a float series, NaN except on the
    bar the corresponding swing point was confirmed.
    """
    leg = leg_state(high, low, size)
    is_new_high = start_of_bearish_leg(leg)  # a new *swing high* is confirmed
    is_new_low = start_of_bullish_leg(leg)  # a new *swing low* is confirmed

    swing_high = pd.Series(np.nan, index=high.index)
    swing_low = pd.Series(np.nan, index=low.index)
    swing_high[is_new_high] = high.shift(size)[is_new_high]
    swing_low[is_new_low] = low.shift(size)[is_new_low]
    return swing_high, swing_low
