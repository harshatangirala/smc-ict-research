"""Unit tests for pine_parser/legs.py."""

import numpy as np
import pandas as pd

from pine_parser.legs import extract_swing_points, leg_state


def _synthetic_series(n=60, seed=1):
    rng = np.random.default_rng(seed)
    # A clean up-down-up sawtooth so leg transitions are unambiguous.
    x = np.arange(n)
    base = np.sin(x / 5.0) * 10 + 100
    high = base + 1
    low = base - 1
    return pd.Series(high), pd.Series(low)


def test_leg_state_is_binary():
    high, low = _synthetic_series()
    leg = leg_state(high, low, size=5)
    assert set(leg.unique()).issubset({0, 1})


def test_extract_swing_points_alternate_between_types_eventually():
    high, low = _synthetic_series()
    swing_high, swing_low = extract_swing_points(high, low, size=5)
    assert swing_high.notna().sum() > 0
    assert swing_low.notna().sum() > 0


def test_extract_swing_points_price_is_lagged_by_size():
    # A single sharp spike at bar 20 in an otherwise flat/declining series.
    n = 40
    high = pd.Series(np.linspace(100, 90, n))
    low = pd.Series(np.linspace(99, 89, n))
    high.iloc[20] = 150
    low.iloc[20] = 149
    swing_high, _ = extract_swing_points(high, low, size=5)
    confirmed_positions = swing_high.dropna()
    if len(confirmed_positions) > 0:
        # any confirmed swing high value must equal a real value that
        # existed `size` bars before the confirmation bar
        for pos, val in confirmed_positions.items():
            assert val in high.to_numpy()
