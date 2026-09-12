# CHANGES

Every code, data and parameter change made on branch `ssrn-ready/claude-opus-5`,
with the reason for each. Ordered by severity.

Defects are labelled by how they were found:
**[proved]** a mechanical check now in `tests/` demonstrates it;
**[measured]** quantified against the previously committed results in `data/bundle/`;
**[read]** found by inspection and confirmed by running the code.

---

## 1. Critical — defects that changed published conclusions

### 1.1 Look-ahead leakage in the tradeable event table  **[proved]**

**Files:** `signals/ict_signals.py`, `signals/event_engine.py`, `tests/test_no_lookahead.py`

`detect_fvg` produced `ict_fvg_bullish_filled` / `ict_fvg_bearish_filled` by
searching up to 60 bars *forward* from each Fair Value Gap formation bar and
stamping the answer **on the formation bar**. `melt_events` selected every
boolean column as a tradeable signal, so both columns became entry signals, and
the backtester opened a position at the formation bar's close using a value
that could only be known 60 bars later.

*Evidence.* A truncation-invariance probe — recompute each detector on data cut
at bar *i*, compare with the full-series value at bar *i* — flips on exactly
these two columns and no others. In the committed full-universe event table
(4,348,698 events over 499 tickers, `data/bundle/master_events.parquet`) they
contributed **187,719 events (4.3%)**, which became 187,374 trades at h = 10,
and occupied both extremes of the concept ranking: `ict_fvg_bearish_filled` had
the most negative effect size in the entire study (d = −0.222) and was listed in
`docs/final_research_report.md` under "Signals that beat the random-entry
baseline".

*Fix.* Fill state is now an **outcome label**, not a detection input. The
columns are renamed `*_filled_label`, carry an explicit forward-looking warning
in the docstring, and are excluded from the event registry. The fill window `N`
is a parameter (default 60 = the longest holding period), so a reported fill
rate always states the window it refers to.

### 1.2 The significance flag was sign-blind  **[measured]**

**Files:** `analytics/statistics.py`, `analytics/master_stats.py`,
`analytics/concept_ranking.py`, `analytics/combinations.py`,
`analytics/stock_ranking.py`, `tests/test_statistics.py`

`significant_vs_baseline` came from `scipy.stats.ttest_ind`, whose default is
**two-sided**. A concept whose mean return was significantly *worse* than
random entry set the flag exactly as one that was significantly better.

*Evidence.* In the committed `concept_rankings.csv`, **28 of 42** concepts were
flagged significant against the baseline. Of those 28, **27 had a negative
`effect_size_vs_baseline`** — they lost to random entry. Only one
(`ict_ob_bullish_mitigated`, +0.033) was actually better. The report's Section 2
table, headed "Signals that beat the random-entry baseline", lists entries with
Sharpe −0.199 and mean return −0.39%.

*Fix.* All comparisons are one-sided (`alternative="greater"`) with the
direction stated. The headline flag additionally requires a positive excess
return. Both the one- and two-sided p-values are retained in the output so the
difference is auditable. Losing concepts are reported as losing, in their own
count.

### 1.3 The random-entry baseline was not reproducible  **[proved]**

**Files:** `backtest/baselines.py`, `utils/rng.py`, `tests/test_pipeline_integrity.py`

`random_entry` derived its per-ticker seed as
`seed + abs(hash(tuple(df.index[:1].astype(str)))) % 10_000`. Python salts
`str` hashing per process (PEP 456), so **every run drew a different baseline**.

*Evidence.* Running the original function in three separate interpreters
produced three disjoint entry sets (verified). Since the baseline is the
comparator behind every `significant_vs_baseline` flag, the published
significance counts could not be reproduced by rerunning the pipeline.

*Fix.* New `utils/rng.py` derives child seeds with BLAKE2b over a UTF-8 label —
stable across processes, machines and Python versions. A test pins a specific
derived value so a change to the scheme cannot pass silently. `results/seed.txt`
records the master seed and derivation.

### 1.4 A degenerate signal supplied 45% of all events  **[measured]**

**Files:** `signals/ict_signals.py`, `utils/config.py`, `tests/test_detector_rules.py`

`detect_nwog_ndog` set `ict_ndog_formed = True` whenever `open` and the prior
`close` were both non-null — i.e. on essentially **every bar of every ticker**.

*Evidence.* 1,946,675 events in the committed table, **44.8% of the entire
event population**, for a concept meant to mark notable opening gaps. It also
ignored the `ICT.ndog_enabled = False` / `nwog_enabled` config flags entirely,
and emitted an unsigned gap size, so the melted event carried `direction = 0`.

*Fix.* A gap event now requires materiality:
`|open − close_prev| ≥ gap_min_atr × ATR(14)_prev`, default 0.10 ATR. Gaps are
split into `_gap_up` / `_gap_down` so they carry a directional hypothesis. The
enable flags are honoured. The week-open test is now "the calendar weekday
decreased", which is robust to a Monday holiday; the previous
`dayofweek.diff() > 1` test also fired on a mid-week holiday gap.

### 1.5 Direction was guessed from the signal name  **[read]**

**Files:** `signals/event_engine.py`

`_direction_for` matched the substrings `bullish`/`buyside` and
`bearish`/`sellside`, returning **0** when neither matched — and
`backtest/engine.py` coerced `direction 0` to `+1`. Affected signals:

| Signal | Old direction | Correct | Consequence |
|---|---|---|---|
| `smc_equal_highs` | 0 → traded long | −1 | resistance traded as if bullish |
| `smc_equal_lows` | 0 → traded long | +1 | correct by accident |
| `ict_ndog_formed`, `ict_nwog_formed` | 0 → traded long | ± by gap sign | unsigned |
| `ict_ob_bullish_mitigated` | +1 | **−1** | a bullish block *failing* is bearish |
| `ict_ob_bearish_mitigated` | −1 | **+1** | mirror of the above |

*Fix.* An explicit `EVENT_REGISTRY` maps every tradeable signal to `+1` or `−1`.
Unregistered names raise rather than defaulting. The backtest engine raises on
any direction outside `{+1, −1}`.

### 1.6 A detector was silently dead  **[proved]**

**Files:** `signals/ict_signals.py`, `docs/specs/ict_bpr.yaml`

`detect_bpr` tested `(up_bot < dn_top) & (dn_bot < up_bot)` against column names
whose meaning was inverted: for a bullish FVG the gap spans
`[high[i−2], low[i]]` with `high[i−2] < low[i]`, so the column named `_top` held
the **lower** edge. Substituting the real edges, the condition reduces to
`upper < lower` — unsatisfiable.

*Evidence.* `ict_bpr_bullish` and `ict_bpr_bearish` were `False` for every bar
of every ticker. `melt_events` drops all-False columns without comment, so both
concepts vanished from the study with no error: the "42 concepts tested"
headline was 42 of 44 declared detectors.

*Fix.* Gap boundaries renamed `_lower` / `_upper`, and BPR now uses a correct
interval-overlap test, `max(a_lo, b_lo) < min(a_hi, b_hi)`. Both signals fire.

---

## 2. High — methodology

### 2.1 Overlapping, cross-sectionally correlated returns treated as iid  **[proved]**

**Files:** `analytics/statistics.py` (`calendar_time_mean_test`, `newey_west_se`)

*h*-day forward returns started on consecutive bars share *h*−1 days of price
path, and trades entered on the same date across ~500 tickers share the market
factor. The original used `ttest_1samp` on the pooled array, which assumes both
away. Many reported p-values were literally `0.000e+00`.

*Evidence.* On a synthetic panel with a pure common factor and 240,000 trades
over 800 dates, the iid t-test gives *t* = −48.3; the calendar-time estimator
gives *t* = −3.0. **The iid standard error is understated by ~16×.**

*Fix.* Inference collapses trades to calendar time and applies Newey-West with
Bartlett weights at lag *h* — the standard calendar-time-portfolio treatment.
The iid p-value is retained as `p_value_vs_zero_iid` for comparison.

### 2.2 The baseline comparison did not control ticker composition  **[read]**

**Files:** `analytics/statistics.py` (`matched_randomization_test`,
`build_return_pools`), `analytics/montecarlo.py`

A concept's trades and the pooled baseline's trades came from different mixes of
tickers, and mean returns differ enormously across names over 2010–2026. Welch's
test on the two pools therefore measured ticker mix as much as signal quality.

*Fix.* A **composition-matched null**: hold the ticker mix and the per-ticker
trade count fixed, and ask what mean would arise from choosing those entry
dates at random. Each trade is measured against its own ticker's unconditional
h-day mean, signed by direction.

*Superseded in part — see §8.1.* The first version tested that excess with the
simple-random-sampling variance of the null mean (`n_t` of `N_t` bars without
replacement, finite-population correction). Its moments match a 2,000-run
simulation exactly, but that simulation draws dates independently per ticker,
so it validates the test only for signals that do not fire together. The
calibration study found it rejecting 28–43% of uninformative clustered signals
at a nominal 5%. The primary test is now a calendar-time Newey–West test on the
same per-trade excess (`matched_excess_calendar_test`); the SRS p-value is kept
as `p_value_vs_matched_random_srs` for comparison.

### 2.3 No transaction costs  **[read]**

**New file:** `backtest/engine_tc.py`

The study reported gross forward returns as results. Added configurable fixed +
spread + stochastic slippage costs (default 1 + 5 + 5–20 bps = **11–26 bps round
trip**), a cost grid, and `breakeven_cost_bps` — the cost at which each concept's
mean net return reaches zero, which is the number a reader needs to judge
tradeability.

### 2.4 No out-of-sample evaluation  **[read]**

**New file:** `analytics/walkforward.py`

Every concept was selected and evaluated on the same 2010–2026 sample. Added a
rolling walk-forward: train 3 years, test the next 1, step 1. Concepts are ranked
on the training window only; null pools are rebuilt inside each window so the
training null never sees test prices. Reports out-of-sample excess, hit rate and
train→test rank correlation per fold.

### 2.5 No parameter sensitivity  **[read]**

**New file:** `analytics/sensitivity.py`

All results came from the Pine `input.*` defaults with no variation. Added grid
and randomised sweeps that re-run detection under overridden parameters, plus
`stability_summary` reporting sign-consistency across configurations.

### 2.6 Sector map silently mis-assigned tickers  **[proved]**

**File:** `analytics/sectors.py`

`SECTOR_MAP` merges one dict comprehension per sector; a ticker listed twice
resolves to whichever sector appears **last**, with no error.

| Ticker | Declared in | Resolved to | Correct |
|---|---|---|---|
| `AME` | Industrials, Real Estate | Real Estate | **Industrials** |
| `GEN` | Info. Technology, Health Care | Health Care | **Info. Technology** |
| `KVUE` | Health Care, Consumer Staples | Consumer Staples | correct by luck |
| `AVB` | Real Estate ×2 | Real Estate | harmless duplicate |

*Fix.* Assignments corrected; `_assert_no_duplicate_assignments()` runs at import
and raises. Added `sector_coverage_report` — ~10% of the universe is unmapped and
is reported as `Unknown` rather than dropped.

*Superseded — see §8.4.* The curated map is no longer the source of sector
labels. Published GICS sectors from a committed constituent snapshot replace it;
against that snapshot the curated map left 54 constituents unclassified and
mis-classified six (APP, AWK, BLDR, DD, TKO, UBER).

### 2.7 Invalid OHLC bars were counted but never repaired  **[measured]**

**New file:** `utils/prices.py`

The data-quality report counted bars violating the OHLC invariant and then fed
them to the detectors unchanged, where an impossible bar can manufacture a
spurious pivot, swing or order block.

*Measurement.* Across 498 tickers there are **exactly 3 materially invalid bars**
— APH 2023-06-05 (0.378% of close), APH 2021-05-05 (0.179%), HUBB 2021-05-05
(0.116%) — plus 1,301 bars whose violation is below 1e-6 of close, i.e. float
representation noise from parquet round-tripping.

*Fix.* `repair_ohlc` clamps `high`/`low` to enclose open and close — the minimal
change that restores the invariant. Only material repairs are logged, so the
three real cases are not buried under 1,301 noise entries. All four call sites
that separately re-implemented "read parquet, sort, dedupe" now route through
one loader, so a repair cannot apply in one path and not another.

---

## 3. Medium — correctness and hygiene

| # | File | Change | Reason |
|---|---|---|---|
| 3.1 | `backtest/engine.py` | `holding_periods and h` → `h` | Evaluated to `h` only because the list was non-empty; nonsense that silently depended on an unrelated variable. |
| 3.2 | `backtest/engine.py` | Added `audit_positions()` | Exposes the exact bar indices each trade reads so no-look-ahead is testable mechanically, not by inspection. |
| 3.3 | `backtest/engine.py` | Raise on `direction ∉ {+1,−1}`; skip non-finite/zero entry prices | Prevents the silent `0 → +1` coercion; guards against division by zero. |
| 3.4 | `backtest/baselines.py` | 52-week breakout fires on the *transition*, not the state | `close >= rolling_max` is true for long runs during a trend, making the "breakout" baseline a trend-following strategy with inflated trade counts. |
| 3.5 | `backtest/baselines.py` | Random entries per ticker 50 → 500 | At 50 draws the baseline's own standard error dominated every comparison. |
| 3.6 | `backtest/metrics.py` | Expectancy uses `len(losses)/n`, not `1 − win_rate` | Exactly-zero returns were being counted as losses. |
| 3.7 | `backtest/metrics.py` | Added skewness, kurtosis, Calmar, MFE/MAE percentiles and ratio | Required by the reporting spec; absent before. |
| 3.8 | `analytics/statistics.py` | Vectorised the bootstrap; mean and Cohen's d share one resample matrix | The Python loop at the new 10,000-iteration budget would have dominated runtime; `apply_along_axis` for *d* is a row-wise Python loop. |
| 3.9 | `analytics/statistics.py` | `ci_method` column records full vs subsampled bootstrap | Above 20,000 observations the bootstrap runs on a subsample, giving a *wider* (conservative) interval. Previously undocumented in the output. |
| 3.10 | `analytics/master_stats.py` | BH-FDR applied once across the whole (signal × horizon) family | Correction was previously applied inside each ranking module at one horizon, understating multiplicity. |
| 3.11 | `analytics/combinations.py` | `MIN_COMBO_OCCURRENCES` 30 → 100, sourced from config | A 30-trade combination cannot support a claim and inflates the corrected family. |
| 3.12 | `utils/data_loader.py` | `normalize_ticker` falls through to a general `.` → `-` rule | Only `BRK.B` and `BF.B` were handled; a constituent-list refresh introducing a new dotted ticker would have dropped it silently. Both current cases verified correct. |
| 3.13 | `utils/config.py` | Added `PRIMARY_HOLDING_PERIOD`, cost, walk-forward, Monte Carlo, HAC, sample-floor and gate parameters; profile switch | Magic numbers were scattered across modules. |
| 3.14 | `main.py` | Added `statistics`, `walkforward`, `costs`, `montecarlo`, `sensitivity`, `report` stages; `--skip`; run manifest | New capability, and every run now stamps git hash, profile, seed and timestamp. |
| 3.15 | `signals/event_engine.py` | Removed the dead `BOOLEAN_EVENT_SUFFIXES` constant | Defined but never used; implied a filter that did not exist. |

## 4. Parameter changes

| Parameter | Old | New | Reason |
|---|---|---|---|
| `BOOTSTRAP_ITERATIONS` | 2,000 | 10,000 (`final`) / 5,000 (`fast`) | Reporting spec. Profile-switched so CI stays fast. |
| Random entries per ticker | 50 | 500 | §3.5 |
| `MIN_COMBO_OCCURRENCES` | 30 | 100 | §3.11 |
| `ICT.ndog_enabled` | ignored | honoured (`False`) | §1.4 — the flag always existed; the detector ignored it. |
| `ICT.gap_min_atr` | — | 0.10 | New: gap materiality threshold. |
| `ICT.sweep_penetration_atr` / `sweep_reclaim_frac` / `sweep_confirm_bars` | — | 0.25 / 0.0 / 3 | New: the X, Y, Z of the formal sweep rule. |
| `COSTS` | — | 1 bp fixed + 5 bp spread + 5–20 bp slippage | New: §2.3 |
| Walk-forward windows | — | train 3y / test 1y / step 1y | New: §2.4 |
| `MIN_SAMPLE_SIZE` | 30 (local) | 30 (central) | Unchanged; moved to config. |

**No change was made to the data window (2010-01-01 → 2026-06-13), the holding
periods, α = 0.05, or the FDR method.**

## 5. Detector definitions changed

| Concept | Change |
|---|---|
| **Liquidity sweep** | Replaced. The old `*_swept` columns fired when `close > pool_bottom` — price merely *entering* the pool, with no rejection leg. That is a breakout, not a sweep, which is why the "swept" signals behaved almost identically to pool formation. New `ict_sweep_*` implements penetration ≥ X·ATR beyond the swing level, then a close back past it within Z bars, stamped on the **reclaim** bar. The old columns are retained under their original names so the change is visible rather than substituted. |
| **FVG fill** | Now an outcome label with an explicit window `N` (default 60). |
| **Opening gaps** | Materiality threshold and direction split (§1.4). |
| **BPR** | Correct interval-overlap test (§1.6). |
| **Order block mitigation** | Direction inverted relative to formation (§1.5). |
| **Equal highs / lows** | Explicit directions: highs −1, lows +1 (§1.5). |

## 5b. Deliverable gaps closed after the first PR

An audit against the original brief found seven items that were specified but
not delivered. All are now closed.

| # | Gap | Resolution |
|---|---|---|
| 1 | **`analytics/sectors` docstring described `load_sector_map`, which did not exist.** A docstring that promises an API is worse than none. | Implemented `load_sector_map(source="static"\|"live")` and `fetch_live_sectors()`. Static remains the default and is what every published number uses; a live lookup would make results depend on when they were run. |
| 2 | **Per-sector statistical power was never computed** (brief §8: "report sample size and power"). | `sector_power_analysis()` reports the minimum detectable effect per sector, written to `results/sector_power.csv`. *Corrected in §8.1:* the first version computed it from the anti-conservative SRS standard error and concluded that all 12 sectors were adequately powered (MDE 1.8–4.5 bp). From the calendar-time standard error the MDE is 14.7–57.1 bp across the 11 GICS sectors, and **none** is powered to detect a 10 bp effect. Sector results are descriptive. |
| 3 | **10 of 46 registered signals had no specification** -- ICT market structure, volume imbalance, and the liquidity pool/sweep pair were tested and reported but undocumented. | Three spec families added; coverage is now 46/46, enforced by `test_every_registered_signal_has_a_specification`. |
| 4 | **No disambiguation artefact** (brief §1). | `docs/disambiguation.md`: now 16 entries, each with the choice made, the rationale, and a table of which could move a published number. Three (A5, A6, A7) are genuine judgement calls; A8 sets the sign of the gap excess, which decided `ict_nwog_gap_up`'s status under the superseded test and decides nothing under the calibrated one. |
| 5 | **The `export` stage had never been run on the full universe.** | Run; `exports/` now holds the CSV/JSON/Excel deliverables. |
| 6 | **`docs/findings_report.html` / `.pdf` still stated the pre-correction numbers**, and `docs/final_research_report.md` had a stale sector count (0/12 rather than 1/12, from reading a renamed column). | Findings report moved to `docs/superseded/` with a README naming exactly what it gets wrong; `utils/render_pdf.py` repointed and marked superseded. `utils/generate_report.py` now resolves the excess-return column dynamically, and the report is regenerated. |
| 7 | **Acceptance criterion mismatch**: the brief says `main.py backtest` produces `statistics_master.csv`; it produces `trades.parquet`. | Kept separate by design -- statistics takes ~15 min and is re-run far more often than the 4-min backtest. The stage now logs the handoff, and the deviation is documented in `docs/replication_guide.md` §4. |

## 6. New files

```
utils/rng.py                     deterministic seed derivation
utils/prices.py                  shared loader + OHLC repair
utils/validation_report.py       results/validation_report.md
utils/master_summary.py          results/master_summary.md
backtest/engine_tc.py            transaction-cost variant
analytics/master_stats.py        statistics_master.csv, family-wide FDR
analytics/walkforward.py         rolling out-of-sample evaluation
analytics/sensitivity.py         parameter sweeps
analytics/montecarlo.py          matched-null, shuffle, block bootstrap
tools/generate_specs.py          emits docs/specs/*.yaml
tools/make_figures.py            manuscript figures
tools/prepare_sample.py          hermetic sample cache for CI
tools/check_artifacts.py         acceptance-criteria checks
tools/make_replication_package.py  replication_package.zip
tests/conftest.py                synthetic fixtures + non-vacuity guard
tests/test_no_lookahead.py       truncation invariance + index audit
tests/test_detector_rules.py     synthetic-OHLC rule regressions
tests/test_statistics.py         one-sided, HAC, matched-null, FDR
tests/test_pipeline_integrity.py registry, seeding, costs, data, metrics
docs/specs/*.yaml                machine-readable concept definitions
docs/disambiguation.md           every ambiguous reading, the choice, the rationale
docs/manuscript.md               the paper
docs/replication_guide.md        2-page replication guide
utils/universe.py                GICS sectors and index-entry dates from the snapshot
analytics/survivorship.py        survivorship sizing + membership-aware re-test
tools/refresh_universe.py        deliberate refresh of the constituent snapshot
tools/calibration_study.py       size of each significance test under zero edge
tools/manuscript_facts.py        every manuscript number, computed in one place
tools/reviewer_check.py          results/reviewer_report.md
tests/test_audit_regressions.py  calibration, rotation, purge, cost-identity guards
tests/test_ob_fidelity.py        order-block candle selection vs the Pine source
tests/test_universe.py           membership mask, survivorship arithmetic, snapshot
data/raw/sp500_wikipedia_snapshot.csv  committed GICS + date-added snapshot
.github/workflows/ci.yml         tests + trimmed pipeline + spec drift
Dockerfile, docker-entrypoint.sh
run_full_pipeline.sh, run_fast_validation.sh
requirements-ci.txt
```

## 7. What was deliberately NOT changed

* **The Pine translation of structure, legs, pivots and ATR.** These were checked
  against the source and against truncation invariance and are correct. The
  confirmation-lag handling in `pine_parser/` is careful work and was left alone.
* **The SMC FVG percentage scaling.** `bar_delta_pct` divides by `open * 100`
  where the source uses `/ open * 100`. Both sides of the comparison carry the
  same 1e-4 factor, so the test is scale-invariant and results are unaffected.
  Changing it would move no number; it is documented in
  `docs/specs/smc_fvg.yaml` instead.
* **The data window and universe definition**, so the new numbers remain
  comparable to the old ones.
* **Sharpe / Calmar / max-drawdown formulas.** They are computed on an
  overlapping, cross-sectional trade sequence and are not achievable portfolio
  results. Rather than silently redefine them, the module docstring and every
  report state what they are; inference uses the calendar-time estimator.

---

## 8. Audit of this re-analysis's own first results

An end-to-end audit of the results this branch first reported (commit
`fdb570a` and earlier: "5 of 44 concepts beat the matched null, 2 robust")
found defects that changed that headline too. Everything below is fixed from
commit `a9db8a8` on, and every number in the manuscript comes from the
corrected pipeline. They are listed here because the paper's argument — that
ordinary choices can manufacture a positive result — applies to the first
draft of this re-analysis as much as to the original study.

### 8.1 The primary test was anti-conservative for clustered signals  **[proved]**

**Files:** `analytics/statistics.py`, `analytics/master_stats.py`,
`tools/calibration_study.py`, `tests/test_audit_regressions.py`

The first draft tested the matched excess with the simple-random-sampling
variance of the null mean (§2.2). That variance is exact when every ticker's
entry dates are an independent random draw, and it passed the check it was
given — a 2,000-run simulation that drew dates the same way. SMC/ICT signals do
not fire independently: a market-wide move triggers the same detector on
hundreds of tickers on the same day, and many detectors fire mostly in turbulent
markets.

*Evidence.* `tools/calibration_study.py` measures each test's size in six
designs with a true edge of exactly zero (1,000 replications each, nominal 5%):

| Design | SRS variance | Calendar-time | Exact rotation |
|---|---:|---:|---:|
| Real prices, independent | 5.7% | 0.0% | 5.8% |
| Real prices, semi-clustered | **28.1%** | 3.5% | 7.3% |
| Real prices, clustered | **40.6%** | 6.8% | 6.9% |
| Simulated GARCH panel, independent | 5.1% | 0.0% | 5.0% |
| Simulated GARCH panel, clustered | **34.3%** | 3.0% | 4.4% |
| Simulated GARCH panel, volatility-timed | **38.3%** | 5.0% | **18.8%** |

Real signals are more clustered than any of these designs: the calendar-time
standard error of the matched excess is a median 7.0 times the SRS one across
the 352 hypotheses (1.4–16.2).

*Fix.* The primary test is now a calendar-time Newey–West test on each trade's
excess over its ticker's matched mean (`matched_excess_calendar_test`), the only
one of the three that stays near nominal whenever entries cluster. It is
conservative when entries are dispersed, which costs power but cannot produce
false positives; the manuscript reports the power consequence. The exact
rotation test (§8.3) is reported beside it for every hypothesis; it
over-rejects for volatility-timed signals, so a rotation rejection the primary
test does not confirm is not counted.

*Effect.* On the corrected data the SRS variance gives 4 winning concepts at
h = 10 and 28 winning hypotheses across horizons; the calendar-time test gives
none. The first draft's headline of "5 of 44" (4 of these plus
`smc_internal_ob_bearish_mitigated`, §8.2) and its "2 robust" sweep detectors
do not survive.

### 8.2 The SMC order-block detector selected the wrong candle  **[proved]**

**Files:** `signals/smc_signals.py`, `signals/ict_signals.py`, `tests/test_ob_fidelity.py`

LuxAlgo's `storeOrdeBlock` takes, for a bullish order block, the bar with the
**lowest** parsed low between the swing pivot and the break bar (bearish: the
highest parsed high), and removes a block from the active list once price
mitigates it. The translation took the opposite extreme and never removed
mitigated blocks, so it could report the same block's mitigation again and
again. Every `smc_*_ob_*` signal was affected, including
`smc_internal_ob_bearish_mitigated`, one of the five concepts in the first
draft's headline. The ICT order-block loop also searched a range that included
the break bar, so a block could be its own breaking candle.

*Fix.* Pine-faithful ranges and extremes; mitigated blocks are removed. The
regression tests build series on which the two readings disagree. The event
table moved from 2,226,881 to 2,204,425 events. Only the six order-block
*mitigation* signals changed trade count (the four SMC ones fell by 490 to
14,423 trades at h = 10, the two ICT ones rose by 12 and 31); every other
signal is identical. Disambiguation entry A16.

### 8.3 The rotation Monte Carlo could not clear a family-wide FDR threshold  **[proved]**

**Files:** `analytics/montecarlo.py`, `main.py`, `tests/test_audit_regressions.py`

With 1,000 sampled rotations the smallest attainable p-value is 1/1001, above
the first Benjamini–Hochberg threshold of 0.05/352, so the rotation test could
never reject on its own across the study's family. `rotation_null_exact` now
enumerates every admissible offset (4,014–4,132 of them) with an FFT circular
cross-correlation. The statistic is identical to the sampled version's (a test
compares the two over every offset), the result needs no seed, and it runs for
all 352 hypotheses in about a minute (`results/rotation_null_all.csv`).

### 8.4 Sectors were hand-curated  **[measured]**

**Files:** `utils/universe.py`, `analytics/sectors.py`, `data/raw/sp500_wikipedia_snapshot.csv`

Sector labels now come from the published GICS classification in a committed
constituent snapshot (503 rows, 11 sectors), refreshed only deliberately by
`tools/refresh_universe.py`. Against it the curated map left 54 constituents
unclassified and mis-classified six (APP, AWK, BLDR, DD, TKO, UBER;
`results/sector_map_disagreements.csv`). Sector power, recomputed from the
calendar-time standard error, gives minimum detectable effects of 14.7–57.1 bp:
no sector is powered to detect a 10 bp effect, so sector results are
descriptive (§5b item 2 corrected).

### 8.5 Survivorship bias was acknowledged but not measured  **[measured]**

**Files:** `utils/universe.py`, `analytics/survivorship.py`, `main.py`

The snapshot's index-entry dates size the problem: of the 498 constituents with
price data, 265 were members at the sample start and 233 joined during it, so
at least 235 of the 500 index slots at the start (47.0%) were held by
since-removed members that are absent. The
look-ahead-membership component is removed exactly by a re-test that drops
trades dated before a ticker's index entry **and** restricts the matched-null
pools the same way: 19.8% of trades drop out, no concept beats the null in
either universe, and the sign of the excess is preserved for 97.7% of concepts
(median shift 0.88 bp). The removed members cannot be recovered from free
sources.

### 8.6 The parameter sweep was vacuous  **[proved]**

**Files:** `signals/*.py`, `analytics/sensitivity.py`, `tests/test_pipeline_integrity.py`

`def detect(df, length=ICT.ob_swing_len)` freezes the config value at import,
so overriding the config had no effect and the sweep produced identical results
at every grid point (`std_excess` was exactly 0.0 for all 44 signals).
Parameters are now resolved at call time; `TestParametersAreLateBound` guards it.

### 8.7 The calendar-time estimator used calendar days  **[read]**

**File:** `analytics/statistics.py::calendar_time_mean_test`

The date series was reindexed onto a calendar-day grid, padding weekends with
zeros, so a Newey–West lag of *h* spanned only about 5*h*/7 trading days. It is
now a business-day grid.

### 8.8 Walk-forward training trades overlapped the test window  **[proved]**

**File:** `analytics/walkforward.py::purge_train`

About 1% of training trades had exits inside the following test year. Training
trades entered within *h* business days of the training end are now purged.

### 8.9 Transaction-cost draws were keyed to row position  **[proved]**

**File:** `backtest/engine_tc.py`

The stochastic slippage draw depended on the row order of the trade table, so
the same trade could be charged a different cost after a re-sort. Draws are now
keyed to the trade's identity (ticker, date, signal, horizon, occurrence).

### 8.10 The regime null compared a bucket with itself  **[read]**

**File:** `analytics/regimes.py`

Rebuilt as a direction-matched, regime-conditional null computed from all bars.

### 8.11 A "loses to the null" count from a one-sided test  **[read]**

**Files:** `analytics/master_stats.py`, `utils/validation_report.py`, `utils/master_summary.py`, `analytics/concept_ranking.py`

The headline test is one-sided, so a count of concepts that significantly
*lose* to the null built from it is zero by construction. That count now comes
from a separate two-sided family with its own BH-FDR correction
(`loses_to_matched_random`). It is still zero: the smallest adjusted two-sided
p-value across all 352 hypotheses is 0.061.

### 8.12 Documentation claims that did not match the data  **[measured]**

"187,719 leaked trades in the committed 50-ticker results" appeared in five
places. 187,719 is the number of look-ahead **events** in the full
499-ticker event table; they became 187,374 trades at h = 10. Corrected
everywhere, including code comments. The claim that all sectors were
adequately powered is corrected in §5b and §8.4.
