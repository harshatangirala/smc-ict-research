"""Unit tests for pine_parser/pivots.py against a hand-constructed series
with known pivot locations."""

import pandas as pd

from pine_parser.pivots import pivot_high, pivot_low


def test_pivot_high_simple_peak():
    # index:      0  1  2  3  4  5  6
    values = [1, 2, 5, 2, 1, 1, 1]
    high = pd.Series(values)
    is_pivot, confirmed = pivot_high(high, left=2, right=2)
    assert is_pivot[2] == True  # noqa: E712 -- bar 2 (value 5) is the peak
    assert is_pivot.sum() == 1
    # confirmation lag: known only `right`=2 bars later, at index 4
    assert confirmed[4] == True  # noqa: E712
    assert confirmed[3] == False  # noqa: E712 -- not yet confirmed


def test_pivot_low_simple_trough():
    values = [5, 4, 1, 4, 5, 5, 5]
    low = pd.Series(values)
    is_pivot, confirmed = pivot_low(low, left=2, right=2)
    assert is_pivot[2] == True  # noqa: E712
    assert confirmed[4] == True  # noqa: E712


def test_no_pivot_on_flat_series():
    high = pd.Series([3, 3, 3, 3, 3, 3, 3])
    is_pivot, confirmed = pivot_high(high, left=2, right=2)
    assert is_pivot.sum() == 0
