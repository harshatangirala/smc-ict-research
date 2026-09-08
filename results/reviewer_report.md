# Reviewer Report

*Generated 2026-09-08 08:59 UTC*

An adversarial pre-read: the objections a referee or an informed reader is most likely to raise, checked programmatically against the artefacts this run produced. `EXPOSED` items are genuine weaknesses that are **not** fixed; they are listed so the paper can state them rather than have a reader discover them.

| Status | Count |
|---|---:|
| ADDRESSED | 9 |
| PARTIAL | 4 |
| EXPOSED | 1 |

---

## 1. Backtest results are contaminated by look-ahead bias.

**PASS** · severity: critical

**Evidence.** No forward-looking column reaches the event table. Causality is proved by truncation invariance over every registered detector, plus an index-position audit asserting that exits and MAE/MFE read only bars strictly after entry. A canary test confirms the probe still detects a known-leaky column, so a pass is not vacuous.

**Response.** The original pipeline did leak -- two FVG-fill columns contributing 187,719 trades -- and the paper reports that as a finding rather than omitting it.

*See:* `tests/test_no_lookahead.py`, `results/validation_report.md`

---

## 2. A two-sided test cannot support a directional claim about outperformance.

**PASS** · severity: critical

**Evidence.** All comparisons are one-sided with the direction stated, and the headline flag additionally requires a positive excess return. No row is flagged as beating the null with a non-positive excess (asserted in tools/check_artifacts.py).

**Response.** This corrects the prior version, in which 27 of 28 concepts reported as significant had in fact LOST to random entry. Documented in CHANGES.md 1.2.

*See:* `CHANGES.md`

---

## 3. Testing dozens of concepts across eight horizons guarantees false positives.

**PASS** · severity: high

**Evidence.** BH-FDR at alpha = 0.05 is applied once across all 352 (signal x horizon) hypotheses rather than within slices. Combination search is bounded by a minimum occurrence count (100) and a hard cap (60 combinations).

**Response.** Note the direction of the result: the study's conclusion is mostly negative, so multiplicity works against finding an edge, not for it.

*See:* `analytics/master_stats.py`

---

## 4. Overlapping forward returns and cross-sectional correlation invalidate the t-tests.

**PASS** · severity: high

**Evidence.** Inference collapses trades to calendar time and applies Newey-West with Bartlett weights at lag h -- the calendar-time-portfolio treatment. On a synthetic panel with a pure common factor the iid standard error is understated by roughly 16x. For 42 of 44 concepts the panel-robust p-value is more than 100x the iid one.

**Response.** Both p-values are reported (`p_value_vs_zero` and `p_value_vs_zero_iid`), so the difference is auditable rather than asserted.

*See:* `analytics/statistics.py::calendar_time_mean_test`

---

## 5. A zero-return null is meaningless over a bull market; the benchmark must be a real alternative strategy.

**PASS** · severity: high

**Evidence.** The primary test is a design-based matched randomization: hold the ticker mix and the per-ticker trade count fixed, then ask what mean randomly chosen entry dates would produce. Its analytic moments are validated against a 2,000-run simulation (null means agree to five decimals; SE ratios 0.99-1.04).

**Response.** The zero-return test is retained but labelled weak. Six conventional benchmarks run through the identical engine.

*See:* `analytics/statistics.py::matched_randomization_test`

---

## 6. Everything is in-sample; there is no out-of-sample evidence.

**PASS** · severity: high

**Evidence.** Rolling walk-forward: train 3 years, test 1, step 1. Concepts are ranked on the training window only, and null pools are rebuilt inside each window so the training null never sees test prices. 13 folds; mean out-of-sample excess of selected concepts -0.1629pp; mean hit rate 53.8%.

**Response.** Selection skill and concept skill are reported separately, together with the train-to-test rank correlation of the concept ordering.

*See:* `analytics/walkforward.py`

---

## 7. Gross returns are not tradeable; realistic costs would erase a few-basis-point edge.

**PASS** · severity: high

**Evidence.** A cost-aware engine applies fixed + spread + stochastic slippage (11-26 bps round trip). Break-even cost is reported per concept and a cost grid shows where each claim dies. 22 of 44 concepts have a break-even round-trip cost above the modelled 26 bps upper bound.

**Response.** Reporting break-even cost rather than a single cost assumption forestalls the objection that the assumption was chosen to preserve the result.

*See:* `backtest/engine_tc.py`

---

## 8. The universe is a current index snapshot applied retroactively -- survivorship bias.

**PARTIAL** · severity: high

**Evidence.** Acknowledged and quantified: the constituent list is a 2026 snapshot, five tickers are permanently unavailable, and roughly 80 begin after 2010. The bias inflates absolute return levels for signals and baselines alike.

**Response.** NOT fully corrected -- a point-in-time constituent history is not available to this pipeline. The matched-random comparison largely cancels it, since the null is drawn from the same survivor-biased tickers, which is the main reason that comparison carries the headline rather than raw returns. A referee may still reasonably require a point-in-time universe. This is the study's single largest unaddressed threat to validity.

*See:* `results/validation_report.md`

---

## 9. Findings may not generalise beyond US large caps on daily bars, 2010-2026.

**PARTIAL** · severity: high

**Evidence.** Scope is stated explicitly: S&P 500 constituents, daily bars, 2010-2026, a period dominated by a bull market. Regime analysis splits results by trend and volatility state.

**Response.** No other market, asset class or timeframe is tested. Since SMC/ICT is most often taught on intraday FX and futures, the daily-equity restriction is a real limit on what the paper can claim, and the title reflects it.

*See:* `analytics/regimes.py`

---

## 10. No economic mechanism is proposed for why these patterns would predict returns.

**OPEN** · severity: medium

**Evidence.** The study is deliberately an evaluation of publicly documented indicator logic, not a theory paper. It offers no risk-based or behavioural model.

**Response.** A genuine limitation, and it should be stated rather than glossed. The defensible framing is that a null result needs no mechanism: showing that widely-taught rules do not predict returns is informative regardless of theory.

---

## 11. Results are reported at one parameter configuration inherited from the source scripts.

**PASS** · severity: medium

**Evidence.** Grid and randomised parameter sweeps report sign-consistency and the coefficient of variation of the excess return across configurations.

**Response.** The defaults are the Pine `input.*` values, fixed before any result was seen, which is the honest starting point; the sweep shows whether the conclusion survives moving them.

*See:* `analytics/sensitivity.py`

---

## 12. SMC/ICT concepts are vaguely defined in the source material; the paper may be testing a strawman.

**PARTIAL** · severity: medium

**Evidence.** 14 machine-readable specifications give each concept a formal boolean definition, directionality, parameter ranges and an explicit causality argument. Ambiguities in the Pine transcription are named and the chosen reading is justified.

**Response.** Irreducible limitation: these are two specific LuxAlgo implementations, not the SMC/ICT literature as a whole. The title and scope section say so. A practitioner can reasonably object that their own variant differs.

*See:* `docs/specs/`

---

## 13. Bootstrap confidence intervals assume iid draws, which these returns are not.

**PASS** · severity: medium

**Evidence.** Three resampling schemes are reported: matched random re-entry, iid trade shuffling, and a circular block bootstrap (21-bar blocks) that preserves serial dependence. The bootstrap interval is reported beside a HAC interval, and `ci_method` records which bootstrap path was taken.

**Response.** The HAC interval, not the bootstrap one, is used for inference; the bootstrap is reported because the specification requires it and for comparability with the prior version.

*See:* `analytics/montecarlo.py`

---

## 14. Sector-level conclusions rest on too few names to have statistical power.

**PARTIAL** · severity: medium

**Evidence.** Per-sector ticker and trade counts are reported alongside every sector result, and roughly 10% of the universe is unmapped and shown as `Unknown` rather than dropped. 3 of 12 sectors rest on fewer than 25 tickers.

**Response.** Sector results are presented as descriptive, not as tested hypotheses with their own power analysis. A referee may reasonably ask for formal power calculations before any sector claim is made.

*See:* `analytics/sectors.py`

---

## Summary for the authors

1 objection(s) remain genuinely unaddressed and must be stated plainly in the Limitations section:

* No economic mechanism is proposed for why these patterns would predict returns.

4 are partially addressed and should be scoped explicitly rather than claimed as solved:

* The universe is a current index snapshot applied retroactively -- survivorship bias.
* Findings may not generalise beyond US large caps on daily bars, 2010-2026.
* SMC/ICT concepts are vaguely defined in the source material; the paper may be testing a strawman.
* Sector-level conclusions rest on too few names to have statistical power.

### The strongest defensible position

This paper's headline result is **negative** -- most concepts do not beat a composition-matched random entry -- and a negative result is robust to most of the objections that would sink a positive one. Multiplicity, survivorship bias and transaction costs all push *against* finding an edge, so none of them can manufacture the null reported here. The paper should make that argument explicitly rather than leaving a referee to notice it.

The corresponding risk is the opposite one: a referee may ask whether the study had the *power* to detect a real edge of plausible size. That question should be met with the sample sizes and confidence-interval widths already in `results/statistics_master.csv`, not deflected.
