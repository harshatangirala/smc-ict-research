"""Tests for the statistical engine.

These cover the three defects that produced the original headline numbers:
a sign-blind significance test, an unmatched baseline comparison, and iid
standard errors on overlapping panel data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from analytics.statistics import (
    apply_fdr_correction,
    bootstrap_mean_and_d,
    build_return_pools,
    calendar_time_mean_test,
    matched_randomization_test,
    newey_west_se,
    one_sample_significance,
    significance_label,
    two_sample_significance,
)


# ---------------------------------------------------------------------------
# One-sided testing -- the sign bug
# ---------------------------------------------------------------------------
class TestOneSidedComparison:
    def test_a_worse_signal_is_not_significant_at_greater(self):
        """THE regression test for the headline bug.

        A signal that loses badly to the baseline must not be flagged as
        having beaten it. The original code used a two-sided test, so 27 of
        the 28 concepts it reported as 'significant vs baseline' were in fact
        significantly worse than random entry.
        """
        rng = np.random.default_rng(0)
        signal = rng.normal(-0.02, 0.05, 4000)
        baseline = rng.normal(+0.01, 0.05, 4000)
        res = two_sample_significance(signal, baseline, alternative="greater")
        assert res["p_value"] > 0.5, (
            "a signal far worse than baseline produced a small one-sided p"
        )
        assert res["p_value_two_sided"] < 1e-10, (
            "the two-sided p should be tiny -- that is exactly why the "
            "two-sided test mislabelled these concepts"
        )
        assert res["effect_size_cohens_d"] < 0

    def test_a_better_signal_is_significant_at_greater(self):
        rng = np.random.default_rng(1)
        signal = rng.normal(+0.02, 0.05, 4000)
        baseline = rng.normal(0.0, 0.05, 4000)
        res = two_sample_significance(signal, baseline, alternative="greater")
        assert res["p_value"] < 1e-6
        assert res["effect_size_cohens_d"] > 0

    def test_one_sided_p_values_are_complementary(self):
        rng = np.random.default_rng(2)
        a, b = rng.normal(0.01, 0.05, 800), rng.normal(0.0, 0.05, 800)
        g = two_sample_significance(a, b, alternative="greater")["p_value"]
        l = two_sample_significance(a, b, alternative="less")["p_value"]
        assert g + l == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Overlapping / cross-sectional standard errors
# ---------------------------------------------------------------------------
class TestOverlapAwareInference:
    def test_newey_west_exceeds_iid_se_under_positive_autocorrelation(self):
        rng = np.random.default_rng(3)
        e = rng.normal(0, 1, 6000)
        x = np.convolve(e, np.ones(10), mode="same")  # 10-lag overlap
        iid = x.std(ddof=1) / np.sqrt(len(x))
        assert newey_west_se(x, 10) > 2 * iid

    def test_newey_west_matches_iid_for_white_noise(self):
        rng = np.random.default_rng(4)
        x = rng.normal(0, 1, 20000)
        iid = x.std(ddof=1) / np.sqrt(len(x))
        assert newey_west_se(x, 5) == pytest.approx(iid, rel=0.15)

    def test_calendar_time_se_dwarfs_iid_under_a_common_factor(self):
        """A market-wide factor makes same-day trades near-duplicates.

        The iid t-test counts 240,000 independent observations; there are
        effectively 800.
        """
        rng = np.random.default_rng(5)
        dates = pd.bdate_range("2015-01-01", periods=800)
        market = rng.normal(0, 0.02, len(dates))
        frames = [
            pd.DataFrame({"date": d, "fwd_return": market[i] + rng.normal(0, 0.01, 300)})
            for i, d in enumerate(dates)
        ]
        trades = pd.concat(frames, ignore_index=True)

        cal = calendar_time_mean_test(trades, holding_period=10)
        iid_se = trades["fwd_return"].std(ddof=1) / np.sqrt(len(trades))
        assert cal["n_dates"] == 800
        assert cal["hac_se"] > 8 * iid_se, (
            f"calendar-time SE {cal['hac_se']:.6f} vs iid {iid_se:.6f} -- the "
            "cross-sectional correlation is not being captured"
        )

    def test_calendar_time_test_is_calibrated_on_independent_data(self):
        """With no common factor and no overlap, it should agree with the t-test."""
        rng = np.random.default_rng(6)
        dates = pd.bdate_range("2015-01-01", periods=1500)
        trades = pd.DataFrame(
            {"date": dates, "fwd_return": rng.normal(0.0, 0.02, len(dates))}
        )
        cal = calendar_time_mean_test(trades, holding_period=1)
        t = sps.ttest_1samp(trades["fwd_return"], 0.0)
        assert cal["p_value"] == pytest.approx(t.pvalue, rel=0.35)


# ---------------------------------------------------------------------------
# Matched randomization null
# ---------------------------------------------------------------------------
class TestMatchedRandomization:
    @staticmethod
    def _prices(seed=7, n=1200, tickers=6):
        rng = np.random.default_rng(seed)
        out = {}
        for k in range(tickers):
            drift = 0.0002 * (k + 1)  # deliberately different per-ticker means
            close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
            out[f"T{k}"] = pd.DataFrame(
                {"close": close}, index=pd.bdate_range("2015-01-01", periods=n)
            )
        return out

    def test_random_entries_do_not_beat_their_own_null(self):
        prices = self._prices()
        pools = build_return_pools(prices, [10])
        rng = np.random.default_rng(8)
        counts, means, total = {}, [], 0
        for t, df in prices.items():
            fwd = df["close"].to_numpy()[10:] / df["close"].to_numpy()[:-10] - 1
            idx = rng.choice(len(fwd), 150, replace=False)
            counts[t] = 150
            means.append(fwd[idx].sum())
            total += 150
        observed = float(np.sum(means) / total)
        res = matched_randomization_test(counts, observed, 1, pools, 10)
        assert 0.02 < res["p_value"] < 0.98, (
            f"random entries got p={res['p_value']:.4f} against their own null"
        )

    def test_null_mean_tracks_ticker_composition(self):
        """Weighting toward a high-drift ticker must raise the null mean.

        This is the confound the original pooled Welch comparison ignored.
        """
        prices = self._prices()
        pools = build_return_pools(prices, [10])
        low = matched_randomization_test({"T0": 500}, 0.0, 1, pools, 10)["null_mean"]
        high = matched_randomization_test({"T5": 500}, 0.0, 1, pools, 10)["null_mean"]
        assert high > low

    def test_direction_flips_the_null_mean(self):
        prices = self._prices()
        pools = build_return_pools(prices, [10])
        long_null = matched_randomization_test({"T3": 300}, 0.0, 1, pools, 10)["null_mean"]
        short_null = matched_randomization_test({"T3": 300}, 0.0, -1, pools, 10)["null_mean"]
        assert short_null == pytest.approx(-long_null)

    def test_analytic_null_agrees_with_simulation(self):
        from analytics.montecarlo import validate_analytic_null

        prices = self._prices()
        counts = {t: 200 for t in prices}
        r = validate_analytic_null(counts, prices, 10, 1, n_runs=800, label="test_v")
        assert abs(r["analytic_null_mean"] - r["simulated_null_mean"]) < 1e-4
        assert 0.85 < r["se_ratio"] < 1.15, f"SE ratio {r['se_ratio']:.3f}"


# ---------------------------------------------------------------------------
# Bootstrap, FDR, labels
# ---------------------------------------------------------------------------
class TestBootstrapAndFDR:
    def test_bootstrap_ci_covers_the_true_mean(self):
        rng = np.random.default_rng(9)
        r = rng.normal(0.004, 0.03, 5000)
        b = bootstrap_mean_and_d(r, n_iter=2000, label="t1")
        assert b["ci_lower"] < r.mean() < b["ci_upper"]
        assert b["ci_method"] == "percentile_bootstrap_full"

    def test_bootstrap_is_reproducible_across_calls(self):
        rng = np.random.default_rng(10)
        r = rng.normal(0.004, 0.03, 3000)
        a = bootstrap_mean_and_d(r, n_iter=1000, label="same")
        b = bootstrap_mean_and_d(r, n_iter=1000, label="same")
        assert a["ci_lower"] == b["ci_lower"] and a["ci_upper"] == b["ci_upper"]

    def test_cohens_d_ci_brackets_the_point_estimate(self):
        rng = np.random.default_rng(11)
        r = rng.normal(0.01, 0.05, 4000)
        b = bootstrap_mean_and_d(r, n_iter=2000, label="t2")
        assert b["cohens_d_ci_lower"] < b["cohens_d"] < b["cohens_d_ci_upper"]

    def test_large_samples_are_flagged_as_subsampled(self):
        rng = np.random.default_rng(12)
        b = bootstrap_mean_and_d(rng.normal(0, 0.03, 60000), n_iter=200, label="t3")
        assert b["ci_method"].startswith("percentile_bootstrap_subsample_")

    def test_fdr_is_monotone_and_conservative(self):
        p = pd.Series([0.001, 0.01, 0.02, 0.04, 0.2, 0.5, 0.9])
        out = apply_fdr_correction(p, alpha=0.05)
        assert (out["p_adjusted"] >= out["p_value"] - 1e-12).all()
        assert out["reject_null"].sum() < (p < 0.05).sum() or out["reject_null"].sum() == (p < 0.05).sum()

    def test_fdr_handles_all_nan(self):
        out = apply_fdr_correction(pd.Series([np.nan, np.nan]))
        assert not out["reject_null"].any()

    def test_significance_label_thresholds(self):
        assert significance_label(np.nan, 0.5) == "insufficient_data"
        assert significance_label(0.9, 0.5) == "not_significant"
        assert significance_label(0.01, 0.05) == "significant_but_negligible_effect"
        assert significance_label(0.01, 0.2) == "significant_small_effect"
        assert significance_label(0.01, 0.5) == "significant_meaningful_effect"

    def test_one_sample_reports_both_iid_and_hac_p_values(self):
        rng = np.random.default_rng(13)
        r = rng.normal(0.001, 0.02, 3000)
        res = one_sample_significance(r, holding_period=10)
        assert "p_value_iid" in res and "hac_se" in res
        assert res["n"] == 3000
