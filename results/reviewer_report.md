# Reviewer Report

*Generated 2026-09-12 20:35 UTC*

An adversarial pre-read: the objections a referee or an informed reader is most likely to raise, checked programmatically against the artefacts this run produced. `EXPOSED` items are genuine weaknesses that are **not** fixed; they are listed so the paper can state them rather than have a reader discover them.

| Status | Count |
|---|---:|
| ADDRESSED | 9 |
| PARTIAL | 6 |
| EXPOSED | 1 |

---

## 1. Backtest results are contaminated by look-ahead bias.

**PASS** · severity: critical

**Evidence.** No forward-looking column reaches the event table. Causality is proved by truncation invariance over every registered detector, plus an index-position audit asserting that exits and MAE/MFE read only bars strictly after entry. A canary test confirms the probe still detects a known-leaky column, so a pass is not vacuous.

**Response.** The original pipeline did leak -- two FVG-fill columns emitting 187,719 look-ahead events (187,374 trades at h = 10) -- and the paper reports that as a finding rather than omitting it.

*See:* `tests/test_no_lookahead.py`, `results/validation_report.md`

---

## 2. Are the p-values calibrated? A test that assumes independent entry dates overstates significance for signals that fire on the same dates.

**PARTIAL** · severity: critical

**Evidence.** Designs with a true edge of zero, nominal 5%: the first primary test (SRS variance) rejects up to 41%; the calendar-time test now used rejects at most 6.8%. clustered: srs 0.406 / calendar 0.068 / rotation 0.069; independent: srs 0.057 / calendar 0.000 / rotation 0.058; semi: srs 0.281 / calendar 0.035 / rotation 0.073; sim_clustered: srs 0.343 / calendar 0.030 / rotation 0.044; sim_independent: srs 0.051 / calendar 0.000 / rotation 0.050; sim_vol_timed: srs 0.383 / calendar 0.050 / rotation 0.188. Anti-conservative in: srs -- clustered, semi, sim_clustered, sim_vol_timed; calendar -- clustered; rotation -- clustered, semi, sim_vol_timed.

**Response.** Found by the authors' own audit, not a referee. Every headline count was recomputed with the calendar-time test; the SRS p-value is kept beside it in results/statistics_master.csv so the difference is auditable. The calendar test is conservative when entries are dispersed, which costs power but cannot manufacture the paper's null result; the exact rotation test is reported beside it for every hypothesis.

*See:* `tools/calibration_study.py`, `results/test_calibration.csv`

---

## 3. A two-sided test cannot support a directional claim about outperformance.

**PASS** · severity: critical

**Evidence.** All comparisons are one-sided with the direction stated, and the headline flag additionally requires a positive excess return. No row is flagged as beating the null with a non-positive excess (asserted in tools/check_artifacts.py).

**Response.** This corrects the prior version, in which 27 of 28 concepts reported as significant had in fact LOST to random entry. Documented in CHANGES.md 1.2.

*See:* `CHANGES.md`

---

## 4. Testing dozens of concepts across eight horizons guarantees false positives.

**PASS** · severity: high

**Evidence.** BH-FDR at alpha = 0.05 is applied once across all 352 (signal x horizon) hypotheses rather than within slices. Combination search is bounded by a minimum occurrence count (100) and a hard cap (60 combinations).

**Response.** Note the direction of the result: the study's conclusion is mostly negative, so multiplicity works against finding an edge, not for it.

*See:* `analytics/master_stats.py`

---

## 5. Overlapping forward returns and cross-sectional correlation invalidate the t-tests.

**PASS** · severity: high

**Evidence.** Inference collapses trades to calendar time and applies Newey-West with Bartlett weights at lag h -- the calendar-time-portfolio treatment. On a synthetic panel with a pure common factor the iid standard error is understated by roughly 16x. For 42 of 44 concepts the panel-robust p-value is more than 100x the iid one.

**Response.** Both p-values are reported (`p_value_vs_zero` and `p_value_vs_zero_iid`), so the difference is auditable rather than asserted.

*See:* `analytics/statistics.py::calendar_time_mean_test`

---

## 6. A zero-return null is meaningless over a bull market; the benchmark must be a real alternative strategy.

**PASS** · severity: high

**Evidence.** The benchmark is composition-matched: each trade is measured against its own ticker's unconditional mean forward return, so ticker mix and per-ticker trade counts are held fixed. Inference is a calendar-time Newey-West test on that per-trade excess.

**Response.** The zero-return test is retained but labelled weak. Six conventional benchmarks run through the identical engine.

*See:* `analytics/statistics.py::matched_excess_calendar_test`

---

## 7. Everything is in-sample; there is no out-of-sample evidence.

**PASS** · severity: high

**Evidence.** Rolling walk-forward: train 3 years, test 1, step 1. Concepts are ranked on the training window only, and null pools are rebuilt inside each window so the training null never sees test prices. 13 folds; mean out-of-sample excess of selected concepts -0.3931pp; mean hit rate 36.9%.

**Response.** Selection skill and concept skill are reported separately, together with the train-to-test rank correlation of the concept ordering.

*See:* `analytics/walkforward.py`

---

## 8. Gross returns are not tradeable; realistic costs would erase a few-basis-point edge.

**PASS** · severity: high

**Evidence.** A cost-aware engine applies fixed + spread + stochastic slippage (11-26 bps round trip). Break-even cost is reported per concept and a cost grid shows where each claim dies. 22 of 44 concepts have a break-even round-trip cost above the modelled 26 bps upper bound.

**Response.** Reporting break-even cost rather than a single cost assumption forestalls the objection that the assumption was chosen to preserve the result.

*See:* `backtest/engine_tc.py`

---

## 9. The universe is a current index snapshot applied retroactively -- survivorship bias.

**PARTIAL** · severity: high

**Evidence.** Sized with published index-entry dates: of 498 analysed tickers, 265 were members at the sample start and at least 235 since-removed constituents are absent. Look-ahead membership is removed exactly by a re-test that filters both signals and matched-null pools: 19.8% of trades drop out; no concept beats the null in either universe (full 0, membership-aware 0); the sign of the excess is preserved for 97.7% of concepts.

**Response.** The removed firms cannot be recovered from free sources; Wikipedia no longer publishes its historical changes table. Survivor bias inflates signal and null alike, so it largely cancels in the excess -- unless removed firms, which are disproportionately distressed, responded to these patterns differently. A point-in-time universe remains the largest open threat to validity.

*See:* `analytics/survivorship.py`, `results/survivorship_comparison.json`

---

## 10. A null result from an underpowered test is not evidence of absence.

**PARTIAL** · severity: high

**Evidence.** Minimum detectable excess at 80% power: median 45 bp, best 27 bp (h = 10). The one-sided 95% upper bound on the excess is below the 11 bp minimum round-trip cost for 10 of 44 concepts and below 26 bp for 27.

**Response.** The paper reports, per concept, the largest edge the data can exclude and separates concepts where a cost-covering edge is ruled out from those where the data are simply uninformative. Small edges -- the 10-20 bp range where a practitioner would care -- cannot be ruled out for most concepts, and the Limitations section says so.

*See:* `results/statistics_master.csv`, `docs/manuscript.md`

---

## 11. Findings may not generalise beyond US large caps on daily bars, 2010-2026.

**PARTIAL** · severity: high

**Evidence.** Scope is stated explicitly: S&P 500 constituents, daily bars, 2010-2026, a period dominated by a bull market. Regime analysis splits results by trend and volatility state.

**Response.** No other market, asset class or timeframe is tested. Since SMC/ICT is most often taught on intraday FX and futures, the daily-equity restriction is a real limit on what the paper can claim, and the title reflects it.

*See:* `analytics/regimes.py`

---

## 12. No economic mechanism is proposed for why these patterns would predict returns.

**OPEN** · severity: medium

**Evidence.** The study is deliberately an evaluation of publicly documented indicator logic, not a theory paper. It offers no risk-based or behavioural model.

**Response.** A genuine limitation, and it should be stated rather than glossed. The defensible framing is that a null result needs no mechanism: showing that widely-taught rules do not predict returns is informative regardless of theory.

---

## 13. Results are reported at one parameter configuration inherited from the source scripts.

**PASS** · severity: medium

**Evidence.** Grid and randomised parameter sweeps report sign-consistency and the coefficient of variation of the excess return across configurations.

**Response.** The defaults are the Pine `input.*` values, fixed before any result was seen, which is the honest starting point; the sweep shows whether the conclusion survives moving them.

*See:* `analytics/sensitivity.py`

---

## 14. SMC/ICT concepts are vaguely defined in the source material; the paper may be testing a strawman.

**PARTIAL** · severity: medium

**Evidence.** 14 machine-readable specifications give each concept a formal boolean definition, directionality, parameter ranges and an explicit causality argument. Ambiguities in the Pine transcription are named and the chosen reading is justified.

**Response.** Irreducible limitation: these are two specific LuxAlgo implementations, not the SMC/ICT literature as a whole. The title and scope section say so. A practitioner can reasonably object that their own variant differs.

*See:* `docs/specs/`

---

## 15. Resampling schemes that draw dates independently per ticker ignore that trades cluster on the same dates.

**PASS** · severity: medium

**Evidence.** The rotation null shifts the whole entry calendar by one offset for every ticker, preserving which trades share a date, and is evaluated exactly over every admissible offset by FFT, so its p-values can clear a family-wide FDR threshold. The independent-draw and per-ticker block schemes are kept for comparison and labelled anti-conservative. Confidence intervals used for inference are HAC, not iid bootstrap. The exact rotation test covers all 352 hypotheses; 0 beat it after BH-FDR and 54 lose to it.

**Response.** The iid bootstrap interval is still reported because the brief requires it; `ci_method` records when it ran on a subsample.

*See:* `analytics/montecarlo.py::rotation_null_exact`, `results/rotation_null_all.csv`

---

## 16. Sector-level conclusions rest on too few names to have statistical power.

**PARTIAL** · severity: medium

**Evidence.** Minimum detectable effect per sector from its calendar-time standard error: 14.7-57.1 bp; 0 of 11 sectors are adequately powered (MDE < 10 bp). Sectors are published GICS, with no unclassified tickers.

**Response.** Sector differences are still presented as descriptive rather than pre-registered hypotheses, and GICS labels are current rather than point-in-time.

*See:* `analytics/sectors.py`, `results/sector_power.csv`

---

## Summary for the authors

1 objection(s) remain genuinely unaddressed and must be stated plainly in the Limitations section:

* No economic mechanism is proposed for why these patterns would predict returns.

6 are partially addressed and should be scoped explicitly rather than claimed as solved:

* Are the p-values calibrated? A test that assumes independent entry dates overstates significance for signals that fire on the same dates.
* The universe is a current index snapshot applied retroactively -- survivorship bias.
* A null result from an underpowered test is not evidence of absence.
* Findings may not generalise beyond US large caps on daily bars, 2010-2026.
* SMC/ICT concepts are vaguely defined in the source material; the paper may be testing a strawman.
* Sector-level conclusions rest on too few names to have statistical power.

### The strongest defensible position

This paper's headline result is **negative** -- no concept beats a composition-matched random entry after FDR control -- and a negative result is robust to most of the objections that would sink a positive one. Multiplicity and transaction costs push *against* finding an edge, and an anti-conservative test would have produced rejections, not fewer of them, so none of these can manufacture the null reported here. The paper should make that argument explicitly rather than leaving a referee to notice it.

The corresponding risk is the opposite one, and it is real here: the primary test is conservative when entries are dispersed, and its minimum detectable effect is larger than a plausible edge for most concepts. The power finding above states what the data can and cannot exclude; the paper should lead with it rather than let 'no concept beats the null' be read as 'no concept has an edge'.
