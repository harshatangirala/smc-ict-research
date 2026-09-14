"""Shared synthetic-data fixtures.

The generator here deliberately injects gap bars and swing structure. A plain
Gaussian random walk with wide bars produces almost no 3-bar Fair Value Gaps,
which would make the look-ahead and detector tests pass vacuously -- they would
be checking columns that are False everywhere. ``assert_detectors_are_active``
is the guard against exactly that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def synthetic_ohlcv(n: int = 700, seed: int = 3, jump_every: int = 14) -> pd.DataFrame:
    """Price path containing swings, trends and periodic gap bars.

    Every ``jump_every`` bars a displacement candle is injected whose body is
    large enough to open a 3-bar gap, so FVG / BPR / displacement detectors
    have something to find.
    """
    rng = np.random.default_rng(seed)
    cycle = np.sin(np.arange(n) / 37.0) * 0.006
    steps = cycle + rng.normal(0, 0.010, n)

    jump_idx = np.arange(jump_every, n, jump_every)
    signs = rng.choice([-1.0, 1.0], size=len(jump_idx))
    steps[jump_idx] += signs * rng.uniform(0.055, 0.095, len(jump_idx))

    close = 100 * np.exp(np.cumsum(steps))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1] * (1 + rng.normal(0, 0.002, n - 1))

    body_hi = np.maximum(open_, close)
    body_lo = np.minimum(open_, close)
    # Tight wicks so a big body really does leave a gap; jump bars get
    # near-zero wicks, which is what "displacement" means.
    wick = close * rng.uniform(0.0008, 0.0035, n)
    wick[jump_idx] = close[jump_idx] * 0.0004

    high = body_hi + wick
    low = body_lo - wick
    return pd.DataFrame(
        {
            "open": open_, "high": high, "low": low, "close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n),
        },
        index=pd.bdate_range("2015-01-01", periods=n),
    )


def assert_detectors_are_active(wide: pd.DataFrame, registry: dict, minimum: int = 12) -> list[str]:
    """Fail if too few registered detectors fired on the fixture.

    A truncation-invariance test over columns that are False everywhere proves
    nothing. This turns that silent failure mode into a loud one.
    """
    active = [c for c in wide.columns if c in registry and bool(wide[c].any())]
    assert len(active) >= minimum, (
        f"only {len(active)} registered detectors fired on the fixture "
        f"({sorted(active)}); the test would be vacuous. Adjust the generator."
    )
    return active


@pytest.fixture(scope="session")
def synth_df() -> pd.DataFrame:
    return synthetic_ohlcv()


@pytest.fixture(scope="session")
def synth_wide(synth_df):
    from signals.event_engine import detect_ticker

    return detect_ticker("SYN", synth_df)
