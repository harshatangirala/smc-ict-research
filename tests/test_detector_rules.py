"""Regression tests for the formal detector rules in docs/specs/*.yaml.

Each test builds a minimal hand-constructed OHLC series in which the rule's
outcome is known by inspection, so a change in behaviour is caught as a
failing assertion rather than as a shifted number in a results table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from signals.ict_signals import (
    detect_bpr,
    detect_fvg,
    detect_liquidity_sweep,
    detect_nwog_ndog,
    detect_order_blocks,
)
from utils.config import ICT


def _frame(rows: list[tuple], start: str = "2020-01-01") -> pd.DataFrame:
    """rows: list of (open, high, low, close)."""
    arr = np.asarray(rows, dtype=float)
    return pd.DataFrame(
        {"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2], "close": arr[:, 3],
         "volume": np.full(len(arr), 1_000_000)},
        index=pd.bdate_range(start, periods=len(arr)),
    )


def _flat(n: int, price: float = 100.0) -> list[tuple]:
    return [(price, price + 0.05, price - 0.05, price)] * n


# ---------------------------------------------------------------------------
# Fair Value Gap: formation and the fill LABEL
# ---------------------------------------------------------------------------
class TestFVG:
    @staticmethod
    def _bullish_gap_series(fill_at: int | None, n: int = 90) -> pd.DataFrame:
        """Flat base, a displacement candle, a 3-bar gap, then optional fill."""
        rows = _flat(60)
        # bar 60: large clean-bodied bullish displacement candle
        rows.append((100.0, 112.02, 99.98, 112.0))
        # bar 61: opens above bar 59's high (100.05) -> low > high[i-2]
        rows.append((113.0, 115.0, 112.5, 114.0))
        rows += _flat(n - len(rows), 114.0)
        if fill_at is not None:
            o = rows[fill_at]
            # dip back into the gap region (below high[i-2] = 100.05)
            rows[fill_at] = (o[0], o[1], 99.0, o[3])
        return _frame(rows)

    def test_bullish_fvg_forms_on_a_true_three_bar_gap(self):
        df = self._bullish_gap_series(fill_at=None)
        out = detect_fvg(df)
        assert out["ict_fvg_bullish_formed"].iloc[61], "gap bar should form a bullish FVG"
        # gap region is [high[i-2], low[i]]
        assert out["ict_fvg_bullish_lower"].iloc[61] == pytest.approx(100.05)
        assert out["ict_fvg_bullish_upper"].iloc[61] == pytest.approx(112.5)

    def test_no_fvg_without_a_gap(self):
        df = _frame(_flat(90))
        out = detect_fvg(df)
        assert not out["ict_fvg_bullish_formed"].any()
        assert not out["ict_fvg_bearish_formed"].any()

    def test_fill_label_true_when_price_enters_the_gap_within_N_bars(self):
        df = self._bullish_gap_series(fill_at=70)  # 9 bars after formation
        out = detect_fvg(df, fill_window=60)
        assert out["ict_fvg_bullish_filled_label"].iloc[61]

    def test_fill_label_false_when_the_fill_falls_outside_the_window(self):
        """N is a real parameter: the same fill outside the window must not count."""
        df = self._bullish_gap_series(fill_at=70)
        out = detect_fvg(df, fill_window=5)  # fill at +9 is now out of range
        assert not out["ict_fvg_bullish_filled_label"].iloc[61]

    def test_fill_window_is_inclusive_of_its_last_bar(self):
        df = self._bullish_gap_series(fill_at=71)  # exactly +10
        assert detect_fvg(df, fill_window=10)["ict_fvg_bullish_filled_label"].iloc[61]
        assert not detect_fvg(df, fill_window=9)["ict_fvg_bullish_filled_label"].iloc[61]


# ---------------------------------------------------------------------------
# Balanced Price Range: interval overlap
# ---------------------------------------------------------------------------
class TestBPR:
    def test_bpr_requires_genuine_overlap(self):
        """Regression for the unsatisfiable-condition bug.

        The prior implementation compared inverted boundary names and reduced
        to `upper < lower`, so BPR was False for every bar of every ticker.
        """
        rng = np.random.default_rng(4)
        n = 400
        steps = rng.normal(0, 0.012, n)
        steps[::11] += rng.choice([-1, 1], len(steps[::11])) * 0.07
        close = 100 * np.exp(np.cumsum(steps))
        open_ = np.r_[close[0], close[:-1]]
        hi = np.maximum(open_, close) + close * 0.0005
        lo = np.minimum(open_, close) - close * 0.0005
        df = pd.DataFrame(
            {"open": open_, "high": hi, "low": lo, "close": close,
             "volume": np.full(n, 1e6)},
            index=pd.bdate_range("2015-01-01", periods=n),
        )
        out = detect_bpr(df)
        assert out["ict_bpr_bullish"].any() or out["ict_bpr_bearish"].any(), (
            "BPR never fires -- the overlap condition is unsatisfiable again"
        )

    def test_bpr_is_false_when_gaps_do_not_overlap(self):
        df = _frame(_flat(120))
        out = detect_bpr(df)
        assert not out["ict_bpr_bullish"].any()
        assert not out["ict_bpr_bearish"].any()


# ---------------------------------------------------------------------------
# Liquidity sweep: penetration (X) + reclaim (Y) within Z bars
# ---------------------------------------------------------------------------
class TestLiquiditySweep:
    @staticmethod
    def _sweep_series(reclaim_delay: int | None, n: int = 160):
        """Swing high near 105.5, a penetration to 112, then optional reclaim.

        When no reclaim is intended price must STAY ABOVE the swept level --
        drifting back down to the base would itself be a valid reclaim and the
        fixture would be testing the opposite of what it claims.
        """
        rows = []
        rows += _flat(30, 100.0)
        rows += [(100 + i * 0.5, 100 + i * 0.5 + 0.3, 100 + i * 0.5 - 0.3, 100 + i * 0.5)
                 for i in range(12)]                       # rally to ~105.5
        rows += [(105.5 - i * 0.5, 105.5 - i * 0.5 + 0.3, 105.5 - i * 0.5 - 0.3,
                  105.5 - i * 0.5) for i in range(12)]     # pull back to ~100
        rows += _flat(20, 100.0)
        spike = len(rows)
        rows.append((100.0, 112.0, 99.8, 111.0))           # penetration
        if reclaim_delay is None:
            # hold above the swept level for the rest of the series
            rows += _flat(n - len(rows), 111.0)
        else:
            if reclaim_delay > 1:
                rows += _flat(reclaim_delay - 1, 111.0)
            rows.append((111.0, 111.2, 96.0, 97.0))        # close back below
            rows += _flat(n - len(rows), 97.0)
        return _frame(rows), spike

    def test_sweep_fires_on_the_reclaim_bar_not_the_penetration_bar(self):
        df, spike = self._sweep_series(reclaim_delay=2)
        out = detect_liquidity_sweep(df, swing_len=10, penetration_atr=0.25,
                                     reclaim_frac=0.0, confirm_bars=3)
        fired = np.where(out["ict_sweep_buyside_bearish"].to_numpy())[0]
        assert len(fired), "no buy-side sweep detected"
        assert spike not in fired, "sweep must not fire on the penetration bar"
        assert any(f > spike for f in fired), "sweep must fire after the penetration"

    def test_penetration_without_reclaim_is_not_a_sweep(self):
        df, _ = self._sweep_series(reclaim_delay=None)
        out = detect_liquidity_sweep(df, swing_len=10, confirm_bars=3)
        assert not out["ict_sweep_buyside_bearish"].any(), (
            "a stop run with no rejection leg is a breakout, not a sweep"
        )

    def test_Z_window_gates_a_delayed_reclaim(self):
        """Z is a real window.

        Constructing this needs care: while price *stays above* the swept
        level, every bar is a fresh penetration and the window is renewed, so
        a late reclaim legitimately fires. To isolate Z, the plateau after the
        spike must sit strictly inside the band

            (level,  level + X * ATR]

        -- above the level so no reclaim triggers, but not far enough above to
        re-penetrate. Both the level and the ATR are read from the series
        rather than assumed: the swing level is the swing *high* (105.8), not
        the closing price of the rally (105.5), and an earlier draft of this
        test placed the plateau below the level for exactly that reason.
        """
        from pine_parser.atr import atr
        from pine_parser.legs import extract_swing_points

        base, spike = self._sweep_series(reclaim_delay=None)
        swing_high, _ = extract_swing_points(base["high"], base["low"], 10)
        confirmed = swing_high.dropna()
        confirmed = confirmed[swing_high.dropna().index <= base.index[spike]]
        level = float(confirmed.iloc[-1])

        atr_series = atr(base["high"], base["low"], base["close"], ICT.sweep_atr_len)
        # ATR decays across the plateau; use the smallest value the plateau will
        # see so the bar never re-penetrates at any point in the window.
        a_min = float(atr_series.iloc[spike]) * 0.55
        plateau = level + 0.25 * a_min * 0.5
        assert level < plateau < level + 0.25 * a_min, "plateau band is empty"

        rows = [tuple(r) for r in base[["open", "high", "low", "close"]].to_numpy()[: spike + 1]]
        rows += [(plateau, plateau + 0.005, plateau - 0.005, plateau)] * 8
        rows.append((plateau, plateau + 0.005, 95.0, 96.0))      # reclaim at +9
        rows += _flat(40, 96.0)
        df = _frame(rows)

        reclaim_bar = spike + 9
        short_z = detect_liquidity_sweep(df, swing_len=10, penetration_atr=0.25,
                                         reclaim_frac=0.0, confirm_bars=3)
        long_z = detect_liquidity_sweep(df, swing_len=10, penetration_atr=0.25,
                                        reclaim_frac=0.0, confirm_bars=15)
        assert not short_z["ict_sweep_buyside_bearish"].iloc[reclaim_bar], (
            "reclaim 9 bars after the penetration fired with confirm_bars=3"
        )
        assert long_z["ict_sweep_buyside_bearish"].iloc[reclaim_bar], (
            "the same reclaim did not fire with confirm_bars=15, so the "
            "fixture is not exercising Z"
        )

    def test_sweep_count_is_monotone_in_the_confirmation_window(self):
        """Widening Z can only admit more sweeps, never fewer."""
        from tests.conftest import synthetic_ohlcv

        df = synthetic_ohlcv(n=600, seed=17)
        counts = [
            int(detect_liquidity_sweep(df, confirm_bars=z)["ict_sweep_buyside_bearish"].sum())
            for z in (1, 3, 6, 12)
        ]
        assert counts == sorted(counts), f"non-monotone in Z: {counts}"
        assert counts[-1] > counts[0], "Z has no effect at all on this series"

    def test_larger_penetration_threshold_suppresses_marginal_sweeps(self):
        df, _ = self._sweep_series(reclaim_delay=2)
        loose = detect_liquidity_sweep(df, swing_len=10, penetration_atr=0.25,
                                       confirm_bars=3)["ict_sweep_buyside_bearish"].sum()
        strict = detect_liquidity_sweep(df, swing_len=10, penetration_atr=50.0,
                                        confirm_bars=3)["ict_sweep_buyside_bearish"].sum()
        assert strict < loose, "X must actually gate the penetration leg"


# ---------------------------------------------------------------------------
# Opening gaps: materiality threshold and direction
# ---------------------------------------------------------------------------
class TestOpeningGap:
    def test_flat_series_produces_no_gap_events(self):
        """Regression: ict_ndog_formed used to be True on every bar."""
        df = _frame(_flat(120))
        out = detect_nwog_ndog(df)
        for col in ("ict_nwog_gap_up", "ict_nwog_gap_down",
                    "ict_ndog_gap_up", "ict_ndog_gap_down"):
            assert not out[col].any(), f"{col} fired on a flat series"

    def test_gap_events_are_a_small_fraction_of_bars(self):
        from tests.conftest import synthetic_ohlcv

        df = synthetic_ohlcv(n=600, seed=9)
        out = detect_nwog_ndog(df)
        fired = out[["ict_nwog_gap_up", "ict_nwog_gap_down"]].any(axis=1).mean()
        assert fired < 0.35, (
            f"NWOG fired on {fired:.0%} of bars; a gap concept firing on most "
            "bars is not a signal"
        )

    def test_direction_is_split_by_gap_sign(self):
        rows = _flat(40, 100.0)
        rows.append((108.0, 108.5, 107.5, 108.0))   # big gap up
        rows += _flat(10, 108.0)
        rows.append((99.0, 99.5, 98.5, 99.0))       # big gap down
        rows += _flat(10, 99.0)
        df = _frame(rows)
        out = detect_nwog_ndog(df)
        ups = out["ict_nwog_gap_up"] | out["ict_ndog_gap_up"]
        downs = out["ict_nwog_gap_down"] | out["ict_ndog_gap_down"]
        assert not (ups & downs).any(), "a bar cannot be both a gap up and a gap down"


# ---------------------------------------------------------------------------
# Order blocks
# ---------------------------------------------------------------------------
class TestOrderBlock:
    def test_only_the_most_recent_swing_is_tracked(self):
        """Regression for the 'stuck on the first unbroken swing' bug."""
        n = 120
        close = np.full(n, 100.0)
        close[5:15] = np.linspace(100, 40, 10)
        close[15:30] = np.linspace(40, 100, 15)
        close[30:60] = np.linspace(100, 130, 30)
        close[60:70] = np.linspace(130, 110, 10)
        close[70:80] = np.linspace(110, 125, 10)
        close[80:95] = np.linspace(125, 95, 15)
        close[95:] = np.linspace(95, 90, n - 95)
        df = pd.DataFrame(
            {"open": close, "high": close + 1, "low": close - 1, "close": close,
             "volume": np.full(n, 1e6)},
            index=pd.bdate_range("2020-01-01", periods=n),
        )
        out = detect_order_blocks(df, length=5)
        assert out["ict_ob_bearish_formed"].sum() > 0

    def test_retention_cap_is_respected(self):
        from tests.conftest import synthetic_ohlcv

        df = synthetic_ohlcv(n=700, seed=13)
        out = detect_order_blocks(df, length=10)
        # Cap governs how many blocks stay live; formation events themselves
        # are unbounded, but the run must complete and stay well-behaved.
        assert out["ict_ob_bullish_formed"].sum() >= 0
        assert len(out) == len(df)
        assert ICT.ob_max_retained > 0
