"""No-look-ahead guarantees, proved mechanically rather than by inspection.

Two independent checks:

1. **Index-position audit** (``backtest.engine.audit_positions``): every bar a
   trade reads is classified as entry / exit / excursion, and the test asserts
   that exit and excursion bars are strictly after the entry bar. This is the
   check Priority Check C asks for -- it fails if any exit or MAE/MFE
   computation touches ``entry_bar + 0``.

2. **Truncation invariance** on the detectors: a detector is causal iff
   recomputing it on data truncated at bar ``i`` yields the same value at bar
   ``i`` as computing it on the full series. This catches leaks that reading
   the code misses -- it is how ``ict_fvg_*_filled`` was found.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.engine import _compute_trades_for_ticker, audit_positions
from signals.event_engine import EVENT_REGISTRY, detect_ticker
from tests.conftest import assert_detectors_are_active, synthetic_ohlcv as _synthetic_ohlcv


# ---------------------------------------------------------------------------
# 1. Index-position audit
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("h", [1, 2, 3, 5, 10, 20, 40, 60])
def test_exit_and_excursion_bars_are_strictly_after_entry(h):
    n = 500
    for pos in (0, 1, 100, 250, n - h - 1):
        audit = audit_positions(pos, h, n)
        if not audit["entry"]:
            continue
        entry = audit["entry"][0]
        assert entry == pos
        for bar in audit["exit"]:
            assert bar > entry, f"exit bar {bar} is not strictly after entry {entry}"
        for bar in audit["excursion"]:
            assert bar > entry, f"excursion bar {bar} is not strictly after entry {entry}"
        assert max(audit["excursion"]) == audit["exit"][0], (
            "excursion window must end exactly at the exit bar"
        )
        assert entry not in audit["excursion"], (
            "MAE/MFE must not include the entry bar itself"
        )


def test_trade_returns_depend_only_on_bars_up_to_exit():
    """Perturbing any bar AFTER the exit must not change the trade."""
    rng = np.random.default_rng(0)
    n = 300
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2015-01-01", periods=n),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
        }
    )
    entry_pos, h = 100, 10
    events = pd.DataFrame(
        {"ticker": ["T"], "date": [df["date"].iloc[entry_pos]],
         "signal": ["s"], "direction": [1]}
    )
    base = _compute_trades_for_ticker("T", df, events, [h])

    tampered = df.copy()
    after = slice(entry_pos + h + 1, None)
    tampered.loc[tampered.index[after], ["open", "high", "low", "close"]] *= 5.0
    after_trades = _compute_trades_for_ticker("T", tampered, events, [h])

    pd.testing.assert_frame_equal(base, after_trades)


def test_entry_price_is_unaffected_by_bars_after_entry():
    rng = np.random.default_rng(1)
    n = 200
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2015-01-01", periods=n),
            "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
        }
    )
    entry_pos = 50
    events = pd.DataFrame(
        {"ticker": ["T"], "date": [df["date"].iloc[entry_pos]],
         "signal": ["s"], "direction": [1]}
    )
    base = _compute_trades_for_ticker("T", df, events, [5])
    tampered = df.copy()
    tampered.loc[tampered.index[entry_pos + 1 :], ["open", "high", "low", "close"]] *= 3.0
    tampered_trades = _compute_trades_for_ticker("T", tampered, events, [5])
    assert base["entry_price"].iloc[0] == tampered_trades["entry_price"].iloc[0]


# ---------------------------------------------------------------------------
# 2. Truncation invariance of the detectors
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [3, 11])
def test_registered_event_columns_are_truncation_invariant(seed):
    """THE look-ahead test.

    Recomputes every registered event column on progressively truncated data
    and requires the value at the truncation bar to be unchanged. A column
    that reads future bars flips here.
    """
    df = _synthetic_ohlcv(seed=seed)
    full = detect_ticker("SYN", df)
    # Only columns that actually fire can demonstrate anything, and there must
    # be enough of them for the test to be meaningful.
    cols = assert_detectors_are_active(full, EVENT_REGISTRY, minimum=12)

    violations = {}
    for cut in range(500, 690, 19):
        part = detect_ticker("SYN", df.iloc[: cut + 1])
        for c in cols:
            if bool(full[c].iloc[cut]) != bool(part[c].iloc[cut]):
                violations.setdefault(c, []).append(cut)

    assert not violations, (
        "Look-ahead detected -- these columns change when future bars are "
        f"removed: { {k: v[:3] for k, v in violations.items()} }"
    )


def test_forward_looking_label_is_correctly_identified_as_leaky():
    """Guard on the guard.

    The truncation test above is only meaningful if it can actually detect a
    leak. ``ict_fvg_bullish_filled_label`` is forward-looking by construction,
    so it MUST fail truncation invariance. If this test ever passes-by-being-
    causal, the probe has stopped working and the test above proves nothing.
    """
    df = _synthetic_ohlcv(seed=5)
    from signals.ict_signals import detect_fvg

    full = detect_fvg(df)
    formed_col, label = "ict_fvg_bullish_formed", "ict_fvg_bullish_filled_label"

    # Probe at FORMATION bars only: the label is False everywhere else, so
    # truncating at a non-formation bar can never show a flip and would make
    # this canary vacuously pass.
    formation_bars = np.where(full[formed_col].to_numpy())[0]
    formation_bars = [i for i in formation_bars if 100 <= i <= len(df) - 5]
    assert formation_bars, "synthetic series produced no bullish FVGs to probe"

    flipped = False
    for i in formation_bars:
        part = detect_fvg(df.iloc[: i + 1])
        if bool(full[label].iloc[i]) != bool(part[label].iloc[i]):
            flipped = True
            break
    assert flipped, (
        "The forward-looking label did not flip under truncation, so the "
        "look-ahead probe is not sensitive and cannot certify the detectors."
    )


def test_leaky_labels_are_not_tradeable_events():
    """The leak must stay out of the event table."""
    from signals.event_engine import melt_events

    df = _synthetic_ohlcv(seed=7)
    wide = detect_ticker("SYN", df)
    assert any(c.endswith("_label") for c in wide.columns), "labels missing from wide frame"
    events = melt_events(wide)
    leaked = [s for s in events["signal"].unique() if s.endswith("_label") or "filled" in s]
    assert not leaked, f"forward-looking labels reached the event table: {leaked}"
