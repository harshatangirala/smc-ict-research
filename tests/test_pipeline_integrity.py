"""Integrity guards on the pipeline's plumbing: the event registry, seeding,
transaction costs, data repair, metrics and walk-forward folds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.conftest import synthetic_ohlcv


# ---------------------------------------------------------------------------
# Event registry -- fail-closed
# ---------------------------------------------------------------------------
class TestEventRegistry:
    def test_every_registered_signal_has_a_nonzero_direction(self):
        from signals.event_engine import EVENT_REGISTRY

        assert EVENT_REGISTRY
        bad = {k: v for k, v in EVENT_REGISTRY.items() if v not in (1, -1)}
        assert not bad, f"signals with an invalid direction: {bad}"

    def test_an_unregistered_boolean_column_raises(self):
        """Fail-closed: a new bool column must not become tradeable by default.

        This is the guard that would have stopped ict_fvg_*_filled from being
        traded. The previous rule selected every bool column and relied on a
        deny-list.
        """
        from signals.event_engine import UnregisteredSignalError, melt_events

        wide = pd.DataFrame(
            {
                "ticker": ["T"] * 5,
                "close": np.arange(5.0),
                "ict_bos_bullish": [True, False, False, True, False],
                "some_new_detector_output": [False, True, False, False, True],
            },
            index=pd.bdate_range("2020-01-01", periods=5),
        )
        with pytest.raises(UnregisteredSignalError, match="some_new_detector_output"):
            melt_events(wide)

    def test_label_suffixed_columns_are_accepted_but_not_traded(self):
        from signals.event_engine import melt_events

        wide = pd.DataFrame(
            {
                "ticker": ["T"] * 5,
                "close": np.arange(5.0),
                "ict_bos_bullish": [True, False, False, True, False],
                "anything_filled_label": [True, True, True, True, True],
            },
            index=pd.bdate_range("2020-01-01", periods=5),
        )
        events = melt_events(wide)
        assert set(events["signal"]) == {"ict_bos_bullish"}

    def test_registry_covers_everything_the_detectors_emit(self):
        from signals.event_engine import (
            EVENT_REGISTRY,
            NON_EVENT_BOOLEAN_COLUMNS,
            detect_ticker,
        )

        wide = detect_ticker("SYN", synthetic_ohlcv(n=500, seed=21))
        bool_cols = [c for c in wide.columns if wide[c].dtype == bool]
        unclassified = [
            c for c in bool_cols
            if c not in EVENT_REGISTRY
            and c not in NON_EVENT_BOOLEAN_COLUMNS
            and not c.endswith("_label")
        ]
        assert not unclassified, f"unclassified boolean columns: {unclassified}"

    def test_every_registered_signal_has_a_specification(self):
        """The brief requires a spec per detector; enforce it mechanically.

        Ten registered signals (ICT market structure, volume imbalance, and the
        liquidity pool/sweep pair) were tested and reported but had no
        specification until this was checked.
        """
        import pathlib
        import re

        from signals.event_engine import EVENT_REGISTRY

        spec_dir = pathlib.Path("docs/specs")
        if not spec_dir.exists():
            pytest.skip("specs not generated")
        documented = set()
        for f in spec_dir.glob("*.yaml"):
            if f.name.startswith("_"):
                continue
            documented |= set(re.findall(r"- name: (\w+)", f.read_text(encoding="utf-8")))
        missing = sorted(set(EVENT_REGISTRY) - documented)
        assert not missing, (
            f"{len(missing)} registered signal(s) have no specification in "
            f"docs/specs/: {missing}"
        )

    def test_registry_directions_match_the_yaml_specs(self):
        """The specs are the contract; drift between them and code is a bug."""
        import pathlib
        import re

        from signals.event_engine import EVENT_REGISTRY

        spec_dir = pathlib.Path("docs/specs")
        if not spec_dir.exists():
            pytest.skip("specs not generated")
        mismatches = []
        for f in spec_dir.glob("*.yaml"):
            if f.name.startswith("_"):
                continue
            text = f.read_text(encoding="utf-8")
            for name, direction in re.findall(
                r"- name: (\w+)\n\s+direction: ([+-]\d)", text
            ):
                if name in EVENT_REGISTRY and EVENT_REGISTRY[name] != int(direction):
                    mismatches.append((f.name, name, int(direction), EVENT_REGISTRY[name]))
        assert not mismatches, f"spec/registry direction mismatches: {mismatches}"


# ---------------------------------------------------------------------------
# Deterministic RNG
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_derive_seed_is_stable_and_distinct(self):
        from utils.rng import derive_seed

        assert derive_seed("AAPL") == derive_seed("AAPL")
        assert derive_seed("AAPL") != derive_seed("MSFT")
        assert derive_seed("AAPL", 1) != derive_seed("AAPL", 2)

    def test_derive_seed_matches_a_pinned_value(self):
        """Pinned so a change to the derivation is a visible, deliberate act.

        A silent change would alter the random baseline and therefore every
        significance result, without any test failing.
        """
        from utils.rng import derive_seed

        assert derive_seed("AAPL", 42) == 3361008404

    def test_random_entry_is_reproducible(self):
        from backtest.baselines import random_entry

        df = synthetic_ohlcv(n=400, seed=2)
        a = random_entry(df, 50, ticker="XYZ")["baseline_random_bullish"].to_numpy()
        b = random_entry(df, 50, ticker="XYZ")["baseline_random_bullish"].to_numpy()
        assert np.array_equal(a, b)
        assert a.sum() == 50

    def test_random_entry_differs_across_tickers(self):
        from backtest.baselines import random_entry

        df = synthetic_ohlcv(n=400, seed=2)
        a = random_entry(df, 50, ticker="AAA")["baseline_random_bullish"].to_numpy()
        b = random_entry(df, 50, ticker="BBB")["baseline_random_bullish"].to_numpy()
        assert not np.array_equal(a, b)

    def test_breakout_baseline_fires_on_transitions_not_states(self):
        """A level test produced long runs of consecutive 'signals'."""
        from backtest.baselines import breakout_52w

        n = 700
        close = np.r_[np.full(300, 100.0), np.linspace(100, 200, n - 300)]
        df = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close},
            index=pd.bdate_range("2015-01-01", periods=n),
        )
        out = breakout_52w(df)
        fired = out["baseline_52w_breakout_bullish"]
        assert fired.sum() < 20, (
            f"{fired.sum()} breakout signals during one continuous trend -- "
            "the detector is testing state, not transition"
        )


# ---------------------------------------------------------------------------
# Transaction costs
# ---------------------------------------------------------------------------
class TestTransactionCosts:
    @staticmethod
    def _trades(n=1000, mean=0.005):
        rng = np.random.default_rng(3)
        return pd.DataFrame(
            {
                "signal": ["s"] * n,
                "fwd_return": rng.normal(mean, 0.03, n),
                "holding_period": [10] * n,
            }
        )

    def test_costs_reduce_returns_by_the_stated_amount(self):
        from backtest.engine_tc import apply_costs

        t = self._trades()
        out = apply_costs(t)
        expected = t["fwd_return"] - out["cost_bps"] / 10_000
        assert np.allclose(out["net_return"], expected)
        assert (out["net_return"] < out["fwd_return"]).all()

    def test_costs_are_reproducible(self):
        from backtest.engine_tc import apply_costs

        t = self._trades()
        assert np.allclose(apply_costs(t)["cost_bps"], apply_costs(t)["cost_bps"])

    def test_slippage_stays_within_configured_bounds(self):
        from backtest.engine_tc import apply_costs
        from utils.config import COSTS

        out = apply_costs(self._trades())
        lo = COSTS.fixed_bps + COSTS.spread_bps + COSTS.slippage_bps_low
        hi = COSTS.fixed_bps + COSTS.spread_bps + COSTS.slippage_bps_high
        assert out["cost_bps"].min() >= lo - 1e-9
        assert out["cost_bps"].max() <= hi + 1e-9

    def test_breakeven_cost_equals_gross_mean_in_bps(self):
        from backtest.engine_tc import breakeven_cost_bps

        t = self._trades(mean=0.004)
        be = breakeven_cost_bps(t)
        assert be["breakeven_cost_bps"].iloc[0] == pytest.approx(
            t["fwd_return"].mean() * 10_000
        )

    def test_cost_grid_is_monotone_decreasing(self):
        from backtest.engine_tc import sweep_cost_grid

        g = sweep_cost_grid(self._trades()).sort_values("cost_bps")
        assert g["mean_net_return"].is_monotonic_decreasing


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------
class TestDataQuality:
    def test_repair_restores_the_ohlc_invariant(self):
        from utils.prices import repair_ohlc

        df = pd.DataFrame(
            {
                "open": [100.0, 100.0],
                "high": [99.0, 101.0],   # row 0: high below open
                "low": [101.0, 99.0],    # row 0: low above open
                "close": [100.5, 100.0],
            },
            index=pd.bdate_range("2020-01-01", periods=2),
        )
        fixed, n = repair_ohlc(df, "T")
        assert n == 1
        assert (fixed["high"] >= fixed[["open", "close"]].max(axis=1)).all()
        assert (fixed["low"] <= fixed[["open", "close"]].min(axis=1)).all()

    def test_repair_leaves_valid_bars_untouched(self):
        from utils.prices import repair_ohlc

        df = pd.DataFrame(
            {"open": [100.0], "high": [102.0], "low": [98.0], "close": [101.0]},
            index=pd.bdate_range("2020-01-01", periods=1),
        )
        fixed, n = repair_ohlc(df, "T")
        assert n == 0
        pd.testing.assert_frame_equal(df, fixed)

    def test_ticker_normalisation_handles_dots_generally(self):
        from utils.data_loader import normalize_ticker

        assert normalize_ticker("BRK.B") == "BRK-B"
        assert normalize_ticker("BF.B") == "BF-B"
        assert normalize_ticker("NEW.A") == "NEW-A"   # not in the override table
        assert normalize_ticker("AAPL") == "AAPL"

    def test_sector_map_has_no_duplicate_assignments(self):
        from analytics.sectors import _assert_no_duplicate_assignments

        _assert_no_duplicate_assignments()

    def test_known_sector_corrections(self):
        from analytics.sectors import SECTOR_MAP

        assert SECTOR_MAP["AME"] == "Industrials"
        assert SECTOR_MAP["GEN"] == "Information Technology"
        assert SECTOR_MAP["KVUE"] == "Consumer Staples"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class TestMetrics:
    def test_win_rate_and_profit_factor(self):
        from backtest.metrics import summarize_returns

        r = pd.Series([0.1, 0.1, -0.1, 0.0])
        m = summarize_returns(r, 10)
        assert m["n_trades"] == 4
        assert m["win_rate"] == pytest.approx(0.5)
        assert m["profit_factor"] == pytest.approx(2.0)

    def test_expectancy_does_not_count_zeros_as_losses(self):
        """Zero-return trades belong to neither the win nor the loss leg."""
        from backtest.metrics import summarize_returns

        r = pd.Series([0.10, -0.05] + [0.0] * 8)
        m = summarize_returns(r, 10)
        # p_win = p_loss = 0.1 -> 0.1*0.10 + 0.1*(-0.05)
        assert m["expectancy"] == pytest.approx(0.1 * 0.10 + 0.1 * (-0.05))

    def test_reports_skew_kurtosis_and_calmar(self):
        from backtest.metrics import summarize_returns

        rng = np.random.default_rng(5)
        m = summarize_returns(pd.Series(rng.normal(0.005, 0.03, 900)), 10)
        for key in ("skewness", "kurtosis", "calmar", "sortino", "max_drawdown"):
            assert key in m
        assert abs(m["skewness"]) < 0.5   # near-symmetric input

    def test_empty_input_is_handled(self):
        from backtest.metrics import summarize_returns

        assert summarize_returns(pd.Series([], dtype=float), 10)["n_trades"] == 0

    def test_mfe_mae_summary_shape(self):
        from backtest.metrics import mfe_mae_summary

        out = mfe_mae_summary(pd.Series([0.05, 0.02]), pd.Series([-0.01, -0.03]))
        assert out["avg_mfe"] > 0 > out["avg_mae"]
        assert "mfe_mae_ratio" in out


# ---------------------------------------------------------------------------
# Walk-forward folds
# ---------------------------------------------------------------------------
class TestWalkForward:
    def test_folds_do_not_overlap_train_and_test(self):
        from analytics.walkforward import make_folds

        folds = make_folds(pd.Timestamp("2010-01-01"), pd.Timestamp("2026-01-01"))
        assert folds
        for f in folds:
            assert f["train_end"] <= f["test_start"], "train window leaks into test"
            assert f["train_start"] < f["train_end"] < f["test_end"]

    def test_folds_step_forward_and_stay_in_range(self):
        from analytics.walkforward import make_folds

        folds = make_folds(pd.Timestamp("2010-01-01"), pd.Timestamp("2026-01-01"))
        starts = [f["train_start"] for f in folds]
        assert starts == sorted(starts)
        assert len(set(starts)) == len(starts)
        assert all(f["test_end"] <= pd.Timestamp("2026-01-01") for f in folds)

    def test_short_history_yields_no_folds(self):
        from analytics.walkforward import make_folds

        assert make_folds(pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01")) == []


# ---------------------------------------------------------------------------
# Config late-binding -- the sensitivity sweep must actually sweep
# ---------------------------------------------------------------------------
class TestParametersAreLateBound:
    """Detector parameters must resolve from config at CALL time.

    Python evaluates default arguments once, at `def` time. Writing
    ``def detect(df, length=ICT.ob_swing_len)`` freezes the value at import, so
    rebinding the module-level ``ICT`` afterwards -- which is exactly what
    ``analytics.sensitivity`` does -- has no effect and every grid point returns
    identical results. That happened: the first sweep reported ``std_excess``
    of exactly 0.0 for all 44 signals across all 16 configurations.
    """

    def test_no_config_value_is_frozen_in_a_default_argument(self):
        import pathlib
        import re

        offenders = []
        for rel in ("signals/ict_signals.py", "signals/smc_signals.py"):
            text = pathlib.Path(rel).read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*\w+:\s*[\w\[\]| ]+\s*=\s*(ICT|SMC)\.\w+", text, re.M):
                offenders.append(f"{rel}: {m.group(0).strip()}")
        assert not offenders, (
            "config values frozen in default arguments -- these will not respond "
            f"to a parameter sweep: {offenders}"
        )

    def test_overriding_config_changes_detector_output(self):
        """End-to-end: swapping the dataclass must move the numbers."""
        from dataclasses import replace

        import signals.ict_signals as ict_mod

        df = synthetic_ohlcv(n=600, seed=31)
        base = ict_mod.detect_order_blocks(df)["ict_ob_bullish_formed"].sum()

        original = ict_mod.ICT
        try:
            ict_mod.ICT = replace(original, ob_swing_len=original.ob_swing_len * 3)
            swept = ict_mod.detect_order_blocks(df)["ict_ob_bullish_formed"].sum()
        finally:
            ict_mod.ICT = original

        assert base != swept, (
            "tripling the order-block swing lookback produced identical output; "
            "the parameter is not being read at call time"
        )

    def test_sweep_helper_produces_varying_results(self):
        """The sweep machinery itself, not just the detectors."""
        from analytics.sensitivity import _detect_with_params

        prices = {"SYN": synthetic_ohlcv(n=600, seed=33)}
        a = _detect_with_params(prices, {"ob_swing_len": 5}, {})
        b = _detect_with_params(prices, {"ob_swing_len": 25}, {})
        counts_a = a.groupby("signal").size().to_dict()
        counts_b = b.groupby("signal").size().to_dict()
        assert counts_a != counts_b, (
            "the parameter sweep returned identical event counts for "
            "ob_swing_len 5 and 25 -- the sweep is not sweeping"
        )


# ---------------------------------------------------------------------------
# Dashboard views must survive the schema changes
# ---------------------------------------------------------------------------
class TestDashboardViews:
    """Every dashboard view must render against the current results schema.

    Renaming `excess_return_vs_baseline` to `excess_return_vs_matched_random`
    broke `sector_regime_view` with a bare KeyError; nothing caught it because
    the dashboards have no tests. This walks every public view function.
    """

    def test_all_views_render(self):
        import inspect

        pytest.importorskip("plotly")
        analysis = pytest.importorskip("dashboard.analysis")

        views = [
            n for n in dir(analysis)
            if not n.startswith("_")
            and n.endswith(("_view", "_markdown", "_scoreboard"))
            and callable(getattr(analysis, n))
        ]
        assert views, "no dashboard view functions found"

        failures = []
        for name in views:
            fn = getattr(analysis, name)
            sig = inspect.signature(fn)
            args = [None for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty]
            try:
                fn(*args) if args else fn()
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
        assert not failures, "dashboard views failed to render: " + "; ".join(failures)


class TestSpecDefaultsMatchConfig:
    """Every spec parameter that names a config field must state its live default.

    The audit checked the 27 such parameters and found none stale; this keeps
    it that way when a default changes in utils/config.py.
    """

    def test_spec_defaults_equal_config(self):
        import dataclasses
        import pathlib
        import re

        from utils.config import ICT, SMC

        live = {}
        for obj in (ICT, SMC):
            for f in dataclasses.fields(obj):
                live.setdefault(f.name, []).append(getattr(obj, f.name))
        pattern = re.compile(r"- name: (\w+)\n\s+type: \w+\n\s+default: ([^\n]+)")
        stale, checked = [], 0
        for spec in pathlib.Path("docs/specs").glob("*.yaml"):
            if spec.name.startswith("_"):
                continue
            for name, default in pattern.findall(spec.read_text(encoding="utf-8")):
                if name not in live:
                    continue
                checked += 1
                d = default.strip().strip('"')
                numeric = re.fullmatch(r"-?\d+(\.\d+)?", d) is not None
                if not any(
                    str(v) == d
                    or (numeric and isinstance(v, (int, float)) and not isinstance(v, bool)
                        and float(d) == float(v))
                    for v in live[name]
                ):
                    stale.append((spec.stem, name, d, live[name]))
        assert checked >= 20, f"only {checked} spec parameters matched config fields"
        assert not stale, f"spec defaults disagree with utils/config.py: {stale}"
