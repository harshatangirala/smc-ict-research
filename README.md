---
title: SMC/ICT Statistical Edge Research
emoji: 📈
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: cc-by-nc-sa-4.0
---

# SMC/ICT Statistical Edge Research

A quantitative research platform that tests whether **Smart Money Concepts (SMC)** and
**ICT (Inner Circle Trader)** trading concepts — translated directly from two LuxAlgo Pine
Script indicators — provide statistically significant, out-of-sample-honest trading edges on
daily OHLCV data for the S&P 500, 2010-01-01 through 2026-06-13.

> The YAML block above is Hugging Face Spaces configuration (harmless metadata on GitHub).

## Research objective

The two source indicators (`docs/reference/*.pine`) are treated as **one combined
methodology**, not implemented separately. Every concept in both scripts was translated into
Python, run as an event detector across the S&P 500 universe, and backtested with forward-return
statistics, robustness checks, and multiple-hypothesis-corrected significance testing — with the
explicit goal of answering whether these concepts add predictive power beyond simple baselines
(buy & hold, random entry, EMA crossover, RSI mean reversion, 52-week breakout, momentum).

This is **not** an attempt to replicate TradingView's visual output. Boxes, lines, colors, and
labels in the source scripts are irrelevant; only the underlying trigger logic matters.

## Key findings

**On daily S&P 500 bars over 2010-2026, these implementations of SMC/ICT carry
little to no exploitable predictive information.** Of 44 formalised concepts, at
the 10-day horizon and with Benjamini-Hochberg control across all 352
(concept x horizon) hypotheses:

| Benchmark | Concepts significant |
|---|---:|
| Zero-return null | **39 / 44** |
| Composition-matched random entry | **5 / 44** |
| — significantly *worse* than random entry | 0 / 44 |
| — statistically indistinguishable | 39 / 44 |

The two rows differ by a factor of nearly eight **on identical data**. Against a
zero-return null almost everything looks significant, because over a 16-year bull
market any long-biased signal clears that bar on drift alone. The number you
report depends almost entirely on the benchmark you choose.

The five concepts that do clear the bar have excess returns of **5-33 basis
points** per ten-day trade. A targeted 36-configuration sweep over the
parameters those detectors actually read cuts that to **two** — both liquidity
sweeps — whose edge survives its own parameterisation; `ict_nwog_gap_up` changes
sign across the threshold range and is withdrawn. Three further results bound
what the remainder is worth:

- **Costs.** Measured against the gross mean return, 22 of 44 concepts clear a
  26 bp round-trip cost. Measured against the *excess over the matched null* --
  the part actually attributable to the signal -- only **1 of 44** does, and only
  4 clear even 11 bp. The returns are real; they are mostly market drift that
  random entry captures too.
- **Out of sample.** Across 13 walk-forward folds (train 3y / test 1y / step 1y),
  concepts selected on training data earn a mean out-of-sample excess of
  **-0.16 pp**, against +0.65 pp in sample.
- **Standard errors.** Forward returns overlap in time and cluster
  cross-sectionally. Ignoring that understates standard errors by a median factor
  of **5.8x** (max 11.8x) in this sample, which is how a large trade count turns
  into a spuriously tiny p-value.

Full results: [`docs/manuscript.md`](docs/manuscript.md) /
[`docs/manuscript.pdf`](docs/manuscript.pdf), with
[`results/validation_report.md`](results/validation_report.md) and
[`results/master_summary.md`](results/master_summary.md) generated directly from
the artefacts.

### This corrects an earlier version of the same study

The previous version of this pipeline reported that **28 of 42** concepts beat a
random-entry baseline. That result was wrong, and the reasons are documented in
full in [`CHANGES.md`](CHANGES.md) and Section 6 of the manuscript:

1. **A two-sided test behind a directional claim.** Of the 28 concepts flagged
   significant, **27 had a negative effect size** — they lost to random entry,
   and were listed under the heading "Signals that beat the random-entry
   baseline".
2. **Look-ahead.** Two FVG-fill columns were computed from up to 60 *future* bars
   and stamped on the formation bar, then traded as entry signals — 187,719
   leaked trades.
3. **An irreproducible benchmark.** The random baseline seeded from Python's
   salted `hash()`, so every run drew a different comparator and the published
   counts could not be reproduced.
4. **A degenerate signal.** `ict_ndog_formed` fired on essentially every bar,
   contributing 45% of the entire event table.
5. **A dead detector.** The Balanced Price Range condition reduced to
   `upper < lower` and was false everywhere; two concepts silently vanished.

Each is a one-line mistake. Together they moved the conclusion from "5 of 44
concepts show a small edge that costs mostly consume" to "28 of 42 beat random
entry". The mechanical guards now in `tests/` — truncation invariance, an
index-position audit, a fail-closed signal registry, and a pinned seed
derivation — exist because code review did not catch any of them.

## Project structure

```
smc-ict-research/
├── data/
│   ├── raw/                 static inputs (S&P 500 constituent list)
│   └── cache/                cached OHLCV downloads, parquet (gitignored)
├── docs/
│   ├── concepts_extraction.md   full per-concept technical spec (Task 1/2)
│   ├── task02_pine_analysis.md  plain-English + dependency + parameter + Pine-builtin inventory
│   ├── architecture.md           module responsibility map (Task 3)
│   └── reference/                 plain-text transcriptions of the source Pine scripts
├── pine_parser/            low-level primitives shared by many detectors
│   ├── pivots.py             ta.pivothigh/pivotlow equivalent
│   ├── legs.py                SMC leg() / ICT swings() rolling-breakout pivot
│   └── atr.py                  Wilder RMA ATR
├── signals/
│   ├── ict_signals.py         every ICT Concepts [LuxAlgo] detector
│   ├── smc_signals.py          every Smart Money Concepts [LuxAlgo] detector
│   └── event_engine.py          runs every detector across the universe (Task 6)
├── backtest/
│   ├── engine.py               forward returns, no look-ahead (Task 7)
│   ├── metrics.py               win rate, Sharpe, Sortino, profit factor, MAE/MFE, ...
│   └── baselines.py             buy&hold, random entry, EMA/RSI/breakout/momentum benchmarks
├── analytics/
│   ├── statistics.py           bootstrap CI, significance tests, FDR correction (Task 8)
│   ├── stock_ranking.py         Task 9
│   ├── concept_ranking.py       Task 10
│   ├── combinations.py          Task 11
│   ├── regimes.py                Task 12 (bull/bear/sideways, vol regime)
│   └── sectors.py                Task 12 (sector grouping)
├── dashboard/
│   ├── data_access.py            read-only accessors (files -> DataFrames)
│   └── analysis.py                chart/table builders shared by app.py and streamlit_app.py
├── utils/
│   ├── config.py                paths, date range, every concept parameter default
│   ├── logging_config.py
│   ├── data_loader.py            yfinance ingestion + parquet cache + retry/parallel
│   ├── data_quality.py           Task 4 validation report
│   └── export.py                 Task 14 CSV/Excel/JSON export
├── tests/                        unit tests (pivot/leg/order-block regression tests)
├── results/                      generated research outputs (gitignored, folder kept)
├── exports/                      generated CSV/Excel/JSON deliverables (gitignored, folder kept)
├── main.py                       CLI entry point (ingest / detect / backtest / analyze / export)
├── app.py                        Gradio dashboard entry point
├── streamlit_app.py               Streamlit dashboard entry point
└── requirements.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the pipeline

```bash
python main.py ingest      # download + cache + validate OHLCV for the S&P 500
python main.py detect      # run every SMC/ICT detector across the universe
python main.py backtest    # forward returns at 8 holding periods, no look-ahead
python main.py analyze     # concept/stock/combination/sector/regime rankings
python main.py export      # write CSV/Excel/JSON deliverables to exports/
python main.py all         # run every stage in order
```

## Running the dashboard

Two front ends, same data, same charts — both call the identical framework-agnostic functions
in `dashboard/analysis.py`, so they can never disagree with each other.

```bash
python app.py                 # Gradio, http://localhost:7860
streamlit run streamlit_app.py  # Streamlit, http://localhost:8501
```

Both open a local dashboard with Home / Stock Explorer / Concept Explorer / Combination Explorer
/ Rankings / Sector & Regime / Validation tabs (the Streamlit Home tab additionally surfaces the
headline zero-vs-baseline numbers as KPI tiles). Every number displayed is read from files the
pipeline already produced — nothing is recalculated inside the UI.

## Data source

- **Price data:** `yfinance`, daily OHLCV, 2010-01-01 to 2026-06-13, cached locally under
  `data/cache/` (parquet) so re-runs never re-download unchanged history. **498 of 503**
  constituents download; five (`AVB`, `EA`, `EQR`, `HONA`, `SATS`) return no data at this
  snapshot, verified permanent rather than transient by retrying each individually. **496**
  have at least 300 bars and enter the study.
- **Survivorship bias (important):** the constituent list is a *2026 snapshot* applied
  retroactively to 2010-2026, so only firms in the index today are tested. This inflates
  absolute return levels. It largely cancels in the matched-random comparison, since the null
  is drawn from the same survivor-biased tickers — which is why that comparison, not raw
  return, carries the headline.
- **Universe:** `data/raw/sp500_constituents.csv`, the S&P 500 constituent list supplied for
  this project. Tickers containing a `.` (`BRK.B`, `BF.B`) are converted to `-` for yfinance
  compatibility during ingestion.
- **Sector labels:** a manually curated static GICS-style mapping in `analytics/sectors.py`
  (documented limitation — no live sector API is wired in; unmapped tickers report as
  `"Unknown"` rather than being silently dropped or guessed).

## Methodology

1. **Concept extraction** (`docs/concepts_extraction.md`, `docs/task02_pine_analysis.md`):
   every concept in both Pine scripts was read line by line, documented with exact trigger
   logic, and cross-referenced against each script's own `alertcondition()` list to confirm
   nothing was missed. Two concepts named in general ICT literature — **Rejection Blocks** and
   **Optimal Trade Entry** — have no corresponding logic in either script and are **not
   implemented** (not invented either).
2. **Translation** (`pine_parser/`, `signals/`): overlapping vocabulary between the two scripts
   (e.g. three different definitions of "BOS") is kept as separate, independently-testable
   signal families rather than force-merged — see `concepts_extraction.md §3`.
3. **Event detection** (`signals/event_engine.py`): every detector runs on every cached ticker,
   producing a master event table of `(ticker, date, signal, direction)`.
4. **Backtesting** (`backtest/engine.py`): for every event, forward returns are computed at 1,
   2, 3, 5, 10, 20, 40, and 60 trading days ahead, using only the entry bar's own close and
   strictly-future bars for the exit/MAE/MFE — no look-ahead by construction.
5. **Statistical validation** (`analytics/statistics.py`, `analytics/master_stats.py`):
   three benchmarks are reported per (concept, horizon), and they are not interchangeable:
   - **vs. a zero-return null** — reported, but weak: a long-biased signal clears it on
     market drift over 2010-2026.
   - **vs. a composition-matched randomization null** — the primary test. Hold the concept's
     ticker mix and per-ticker trade count fixed and ask what mean return randomly chosen
     entry *dates* would produce. Exact under the sampling design (finite-population
     correction), assumes nothing about the return distribution, and removes the
     ticker-composition confound that makes a pooled comparison uninterpretable. Validated
     against a 2,000-run simulation.
   - **vs. a pooled random-entry baseline** — one-sided Welch, retained for continuity.

   All tests are **one-sided** with the direction stated; a concept counts as beating the
   null only if its excess is positive, it survives BH-FDR across the whole
   (concept x horizon) family, and it rests on >= 30 trades. Standard errors are
   **calendar-time Newey-West**, not iid: forward returns overlap by h-1 days and cluster
   cross-sectionally, and ignoring that understates the SE by a median 5.8x here.

6. **Analysis** (`analytics/*`): stock-level, concept-level, combination, sector, and market
   regime rankings, all built from the single backtested-trades table (no duplicated
   calculation between modules). Every module compares against the baseline consistently:
   - `concept_ranking.py` / `combinations.py`: each concept/combination vs. the universe-wide
     random-entry baseline.
   - `stock_ranking.py`: each ticker's signal-trades vs. **that same ticker's own**
     random-entry baseline (so a stock ranking highly isn't just rewarded for having rallied
     hard over the period — see the VRT/SNDK/GEV discussion in the final report).
   - `sectors.py` / `regimes.py`: excess average return vs. the baseline's average return in
     the same sector/regime bucket.

## Key assumptions (see docs for full rationale)

- Daily bars only; intraday-only concepts (Killzones) are excluded.
- "Historical" mode semantics throughout (Pine's 500-bar "Present" display window is dropped).
- `ta.atr()` replicated via Wilder's RMA smoothing, not a simple moving average.
- SMC's Premium/Discount zones use the literal all-time expanding high/low from the Pine
  source (not a rolling window) as the default; a rolling-window variant is available for
  robustness comparison in `signals/smc_signals.py::detect_zones(window=...)`.
- Order block detection tracks only the **most recently confirmed** swing point per side,
  matching Pine's `swings()`/`leg()` semantics exactly (a "keep testing every historical
  swing forever" implementation is a bug, not a valid alternate reading — this was caught
  and fixed during Task 6 validation; see the Task 5-6 commit message and
  `tests/test_ict_order_blocks.py` for the regression test).

## Validation performed

- **Unit tests:** 85 tests in `tests/`, run with `pytest tests/ -v`. They cover the pivot and
  leg primitives, every formalised detector rule against hand-constructed OHLC, the
  statistical engine, deterministic seeding, transaction costs, data repair, and walk-forward
  fold construction.
- **No look-ahead, proved mechanically** (`tests/test_no_lookahead.py`), not by code review —
  code review is what missed the original leak:
  1. an **index-position audit** re-derives the exact bar indices each trade reads and asserts
     every exit and excursion bar is strictly after the entry bar, at all eight horizons;
  2. **truncation invariance** recomputes every registered detector on data cut at bar *i* and
     requires the value at bar *i* to be unchanged. A deliberate canary test confirms the
     probe still detects the known-leaky label column, so a pass is not vacuous.
- **Fail-closed signal registry:** a boolean column is tradeable only if registered with an
  explicit direction. Anything else raises. The previous rule was fail-open, which is how a
  forward-looking column became an entry signal.
- **Reproducibility:** seeds derive from BLAKE2b over a stable label, never Python's salted
  `hash()`; a test pins one derived value. Every run writes `results/run_manifest.json`
  (git hash, profile, seed, bootstrap budget) and `results/seed.txt`.
- **Data quality:** `results/data_quality_report.csv`. 496 of 498 tickers clean; exactly
  **3 materially invalid OHLC bars** exist in the whole universe (APH 2021-05-05 and
  2023-06-05, HUBB 2021-05-05) and are now **repaired**, not merely counted. A further 1,301
  sub-1e-6 violations are float noise.
- **Artefact checks:** `python tools/check_artifacts.py` asserts every required output exists,
  that `statistics_master.csv` carries all 21 required columns, that no concept is flagged as
  beating the null with a non-positive excess, and that no forward-looking label reached the
  event table.
- **Manuscript verification:** `python tools/check_manuscript_numbers.py` re-derives all 25
  numeric claims in the paper from the artefacts and fails on any mismatch.
- **Adversarial pre-read:** `python tools/reviewer_check.py` writes
  `results/reviewer_report.md`, listing likely referee objections with each marked ADDRESSED,
  PARTIAL or EXPOSED.

## Reproducing

```bash
pytest tests/ -v                 # 85 tests, ~15s, no network
./run_fast_validation.sh         # hermetic 12-ticker end-to-end, 2-4 min
./run_full_pipeline.sh           # full study, 45-90 min, needs network
```

Or with Docker:

```bash
docker build -t smc-ict-research . && docker run --rm -v "$PWD/results:/app/results" smc-ict-research full
```

See [`docs/replication_guide.md`](docs/replication_guide.md) for the full guide, including
what varies between runs and where each published claim lives.

## Limitations

1. **Survivorship bias** — the universe is a 2026 snapshot applied to 2010-2026.
2. **Daily bars only** — kill zones and all intraday structure are out of scope. SMC/ICT is
   most often taught on intraday FX and futures, so this is a study of the daily-equity
   subset, not of the methodology as traded.
3. **Two specific implementations**, not SMC/ICT as a discretionary practice.
4. **Symmetric short mechanics** — no borrow cost or availability constraint.
5. **Path-dependent metrics are descriptive** — Sharpe, Calmar and max drawdown are computed
   over an overlapping, cross-sectional trade sequence that is not an attainable equity curve.
   Inference uses the calendar-time estimator instead.
6. **No economic mechanism** is proposed; this evaluates indicator logic, not theory.

## License

CC BY-NC-SA 4.0. Not investment advice.
