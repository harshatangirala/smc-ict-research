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
these two columns and no others. In the committed 50-ticker results they
contributed **187,719 trades (4.3% of all events)** and occupied both extremes
of the concept ranking: `ict_fvg_bearish_filled` had the most negative effect
size in the entire study (d = −0.222) and was listed in
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

*Fix.* A design-based **matched randomization test**: hold the ticker mix and
the per-ticker trade count fixed, and ask what mean would arise from choosing
those entry dates at random. Sampling `n_t` of `N_t` bars without replacement
gives an exact variance under the sampling design (with finite-population
correction), assuming nothing about the return distribution. The analytic
moments are validated against a 2,000-run simulation: null means agree to five
decimal places, SE ratios 0.99–1.04.

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
docs/manuscript.md               the paper
docs/replication_guide.md        2-page replication guide
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
