"""Regression tests for defects found in the end-to-end audit.

Each class pins one finding so it cannot quietly return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

H = 10


def _clustered_panel(seed: int, n_tickers: int = 40, n_days: int = 1500):
    """Tickers sharing a strong market factor, so same-day trades co-move."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2012-01-02", periods=n_days)
    market = rng.normal(0.0004, 0.012, n_days)
    prices = {}
    for k in range(n_tickers):
        r = market + rng.normal(0.0002 * (k % 5), 0.015, n_days)
        prices[f"T{k}"] = pd.DataFrame({"close": 100 * np.exp(np.cumsum(r))}, index=dates)
    fwd = {
        t: pd.Series(df["close"].to_numpy()[H:] / df["close"].to_numpy()[:-H] - 1,
                     index=df.index[:-H])
        for t, df in prices.items()
    }
    return prices, fwd, dates


def _same_day_signal(fwd, dates, rng, n_dates=60):
    """An UNINFORMATIVE signal that fires on every ticker on the same dates."""
    d = rng.choice(dates[:-H], size=n_dates, replace=False)
    return pd.concat(
        [pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy(),
                       "direction": 1}) for t, s in fwd.items()],
        ignore_index=True,
    )


class TestClusteredSignalCalibration:
    """Audit finding: the SRS-variance matched test rejected 28-40% of the time
    on uninformative clustered signals at a nominal 5%."""

    def test_primary_test_is_calibrated_where_srs_is_not(self):
        from analytics.statistics import (
            build_return_pools,
            matched_excess_calendar_test,
            matched_randomization_test,
        )

        prices, fwd, dates = _clustered_panel(1)
        pools = build_return_pools(prices, [H])
        rng = np.random.default_rng(2)
        reps, srs_rej, cal_rej = 120, 0, 0
        for _ in range(reps):
            tr = _same_day_signal(fwd, dates, rng)
            counts = tr.groupby("ticker").size().to_dict()
            srs_rej += matched_randomization_test(
                counts, float(tr["fwd_return"].mean()), 1, pools, H)["p_value"] < 0.05
            cal_rej += matched_excess_calendar_test(tr, pools, H, 1)["p_value"] < 0.05
        assert srs_rej / reps > 0.15, "SRS variance should be visibly anti-conservative here"
        assert cal_rej / reps < 0.12, f"primary test rejected {cal_rej / reps:.2f} at nominal 0.05"

    def test_point_estimate_is_unchanged_only_the_se_differs(self):
        from analytics.statistics import (
            build_return_pools,
            matched_excess_calendar_test,
            matched_randomization_test,
        )

        prices, fwd, dates = _clustered_panel(3)
        pools = build_return_pools(prices, [H])
        tr = _same_day_signal(fwd, dates, np.random.default_rng(4))
        counts = tr.groupby("ticker").size().to_dict()
        mr = matched_randomization_test(counts, float(tr["fwd_return"].mean()), 1, pools, H)
        ct = matched_excess_calendar_test(tr, pools, H, 1)
        assert ct["excess_return"] == pytest.approx(mr["excess_return"], abs=1e-12)
        assert ct["se"] > 2 * mr["null_se"], "clustering should inflate the SE well above SRS"

    def test_mixed_direction_population(self):
        """direction=None reads each trade's own direction (used for sectors)."""
        from analytics.statistics import build_return_pools, matched_excess_calendar_test

        prices, fwd, dates = _clustered_panel(5)
        pools = build_return_pools(prices, [H])
        tr = _same_day_signal(fwd, dates, np.random.default_rng(6))
        tr.loc[tr.index % 2 == 1, "direction"] = -1
        tr.loc[tr["direction"] == -1, "fwd_return"] *= -1
        out = matched_excess_calendar_test(tr, pools, H, direction=None)
        assert np.isfinite(out["se"]) and out["n"] == len(tr)


class TestRotationNull:
    """The rotation null must preserve clustering, so it is not fooled either."""

    def test_rotation_null_is_not_fooled_by_clustering(self):
        from analytics.montecarlo import monte_carlo_rotation_null

        prices, fwd, dates = _clustered_panel(7, n_tickers=25)
        rng = np.random.default_rng(8)
        reps, rej = 60, 0
        for i in range(reps):
            tr = _same_day_signal(fwd, dates, rng, n_dates=50)
            rej += monte_carlo_rotation_null(tr, prices, H, n_runs=99,
                                             label=f"t{i}")["p_value"] < 0.05
        assert rej / reps < 0.2, f"rotation null rejected {rej / reps:.2f} at nominal 0.05"


class TestExactRotation:
    """The FFT rotation must equal brute force over every offset."""

    def test_exact_matches_brute_force_over_every_offset(self):
        from analytics.montecarlo import rotation_matrix, rotation_null_exact

        prices, fwd, dates = _clustered_panel(3, n_tickers=6)
        tr = _same_day_signal(fwd, dates, np.random.default_rng(1), n_dates=20)
        tr.loc[tr.index[::3], "direction"] = -1          # mixed signs exercise W
        tickers, cal, F = rotation_matrix(prices, H)
        out = rotation_null_exact(tr, H, matrix=(tickers, cal, F))

        k = tr["ticker"].map({t: i for i, t in enumerate(tickers)}).to_numpy()
        pos = cal.get_indexer(pd.to_datetime(tr["date"]))
        d = tr["direction"].to_numpy(float)
        T = len(cal)
        sims = np.array([np.nanmean(d * F[k, (pos + o) % T]) for o in range(H + 1, T - H - 1)])
        observed = np.nanmean(d * F[k, pos])

        assert out["n_offsets"] == len(sims)
        assert np.isclose(out["observed_mean"], observed)
        assert np.isclose(out["null_mean"], sims.mean(), rtol=1e-9)
        assert np.isclose(out["null_se"], sims.std(ddof=1), rtol=1e-9)
        assert np.isclose(out["p_value"], (1 + (sims >= observed).sum()) / (len(sims) + 1))
        assert np.isclose(out["p_value_less"], (1 + (sims <= observed).sum()) / (len(sims) + 1))

    def test_exact_rotation_is_not_fooled_by_clustering(self):
        from analytics.montecarlo import rotation_matrix, rotation_null_exact

        prices, fwd, dates = _clustered_panel(7, n_tickers=25)
        matrix = rotation_matrix(prices, H)
        rng = np.random.default_rng(8)
        reps = 100
        rej = sum(
            rotation_null_exact(_same_day_signal(fwd, dates, rng, n_dates=50), H,
                                matrix=matrix)["p_value"] < 0.05
            for _ in range(reps)
        )
        assert rej / reps < 0.15, f"exact rotation rejected {rej / reps:.2f} at nominal 0.05"

    def test_family_applies_fdr_and_flags_both_tails(self):
        from analytics.montecarlo import rotation_null_family

        prices, fwd, dates = _clustered_panel(5, n_tickers=10)
        rng = np.random.default_rng(2)
        tr = pd.concat([
            _same_day_signal(fwd, dates, rng, n_dates=30).assign(signal=s, holding_period=H)
            for s in ("a", "b")
        ])
        fam = rotation_null_family(tr, prices)
        assert len(fam) == 2
        assert {"p_adj", "beats_rotation_null", "p_value_two_sided",
                "loses_to_rotation_null"} <= set(fam.columns)
        assert (fam["p_adj"] >= fam["p_value"] - 1e-12).all()


class TestWalkForwardPurge:
    """Audit finding: ~1% of training trades exited inside the test window."""

    def test_trades_whose_exit_crosses_train_end_are_purged(self):
        from analytics.walkforward import purge_train

        dates = pd.bdate_range("2015-01-01", periods=300)
        out = purge_train(pd.DataFrame({"date": dates}), dates[0], dates[250], H)
        assert out["date"].max() == dates[239]
        assert (out["date"] < dates[250] - pd.tseries.offsets.BDay(H)).all()


class TestCostsKeyedToTradeIdentity:
    """Audit finding: slippage was keyed to row position, not the trade."""

    def test_same_trade_same_cost_regardless_of_order(self):
        from backtest.engine_tc import apply_costs

        rng = np.random.default_rng(9)
        n = 400
        t = pd.DataFrame({
            "ticker": rng.choice(["A", "B", "C"], n),
            "date": pd.bdate_range("2015-01-01", periods=n),
            "signal": "s", "holding_period": 10,
            "fwd_return": rng.normal(0, 0.02, n),
        })
        forward = apply_costs(t)["cost_bps"].to_numpy()
        backward = apply_costs(t.iloc[::-1])["cost_bps"].to_numpy()[::-1]
        subset = apply_costs(t.iloc[100:200])["cost_bps"].to_numpy()
        assert np.allclose(forward, backward)
        assert np.allclose(forward[100:200], subset)

    def test_distinct_trades_get_distinct_costs(self):
        from backtest.engine_tc import apply_costs

        t = pd.DataFrame({"ticker": "A", "date": pd.bdate_range("2015-01-01", periods=200),
                          "signal": "s", "holding_period": 10, "fwd_return": 0.0})
        assert apply_costs(t)["cost_bps"].nunique() > 150
