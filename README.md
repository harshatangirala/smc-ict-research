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

A reproducible study of whether **Smart Money Concepts (SMC)** and **ICT (Inner Circle
Trader)** trading concepts — translated directly from two LuxAlgo Pine Script indicators —
carry a statistically detectable, out-of-sample edge on daily OHLCV data for S&P 500
constituents, 2010-01-01 through 2026-06-13.

> The YAML block above is Hugging Face Spaces configuration (harmless metadata on GitHub).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LuxAlgo-derived files: CC BY-NC-SA 4.0](https://img.shields.io/badge/LuxAlgo--derived-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE-CC-BY-NC-SA)

**Paper:** [`docs/manuscript.md`](docs/manuscript.md) · [`docs/manuscript.pdf`](docs/manuscript.pdf)
· **Reproduce:** `./run_full_pipeline.sh` · **Guide:** [`docs/replication_guide.md`](docs/replication_guide.md)

## Key findings

**No concept beats random entry.** Of 44 formalised concepts, tested against a
composition-matched random-entry null with Benjamini–Hochberg control across all 352
(concept × horizon) hypotheses, **none** beats the null at any of eight horizons, and none
is significantly worse.

| Benchmark and test | h = 10 | All horizons |
|---|---:|---:|
| Zero-return null | 38 / 44 | 268 / 352 |
| Matched null, SRS variance (superseded, anti-conservative) | 4 / 44 | 28 / 352 |
| Matched null, exact rotation (secondary) | 0 / 44 | 0 / 352 |
| **Matched null, calendar-time Newey–West (primary)** | **0 / 44** | **0 / 352** |

- **The benchmark decides the answer.** Against a zero-return null, 38 of 44 concepts look
  significant, because any long-biased signal clears that bar on 16 years of market drift.
  The 22 concepts whose gross return clears a 26 bp trading cost are exactly the 22 long
  ones.
- **So does the variance formula.** SMC/ICT signals fire together: a market-wide move
  triggers the same detector on hundreds of tickers the same day, and many fire mostly in
  turbulent markets. A calibration study with a known zero edge
  (`tools/calibration_study.py`) finds the simple-random-sampling variance rejecting
  28–41% of uninformative clustered signals at a nominal 5%; the calendar-time test stays
  between 0% and 6.8% in every design.
- **Power, stated plainly.** For 10 concepts the data exclude, at 95% confidence, an edge
  large enough to cover even the lowest modelled round-trip cost (11 bp). The median
  concept's minimum detectable edge is 45 bp, so small edges cannot be ruled out for most
  concepts. The two liquidity-sweep detectors carry the largest well-measured point
  estimates, +11–12 bp over ten days, with p = 0.23 and 0.29.
- **Out of sample.** Across 13 walk-forward folds, the concepts ranked best on three years
  of data earn **−39 bp** in the following year, against +61 bp in sample.
- **Survivorship.** Dropping the 19.8% of trades dated before each ticker joined the index
  leaves the result unchanged: no concept beats the null in either universe.

Full results: [`docs/manuscript.md`](docs/manuscript.md), with
[`results/validation_report.md`](results/validation_report.md),
[`results/master_summary.md`](results/master_summary.md) and
[`results/reviewer_report.md`](results/reviewer_report.md) generated directly from the
artefacts. Every number in the paper is recomputed from the artefacts, and checked
against the text, by `tools/check_manuscript_numbers.py`.

### This corrects two earlier versions

The **original pipeline** reported that **28 of 42** concepts beat a random-entry baseline
([`CHANGES.md`](CHANGES.md) §1, manuscript §6):

1. **A two-sided test behind a directional claim.** Of the 28 concepts flagged
   significant, **27 had a negative effect size**: they lost to random entry.
2. **Look-ahead.** Two FVG-fill columns were computed from up to 60 *future* bars and
   traded as entry signals: 187,719 look-ahead events (187,374 trades at h = 10).
3. **An irreproducible benchmark.** The random baseline seeded from Python's salted
   `hash()`, so every run drew a different comparator.
4. **A degenerate signal.** `ict_ndog_formed` fired on essentially every bar, 45% of the
   event table.
5. **A dead detector.** The Balanced Price Range condition was unsatisfiable; two concepts
   silently vanished.

The **first draft of this re-analysis** reported **5 of 44** concepts beating the matched
null, 2 of them robust. Its own audit ([`CHANGES.md`](CHANGES.md) §8) found:

6. **A variance formula validated against its own assumptions.** The simple-random-sampling
   variance is exact for independent entry dates and was checked by a simulation that drew
   dates the same way; with clustered entries it rejects 28–41% of uninformative signals.
7. **An order block taken from the wrong candle.** The SMC detector picked the opposite
   extreme from LuxAlgo's `storeOrdeBlock` and never retired mitigated blocks.

Each is a line or two of code. The mechanical guards now in `tests/` — truncation
invariance, an index-position audit, a fail-closed signal registry, a pinned seed
derivation, calibration regressions and Pine-fidelity tests — exist because code review
caught none of them.

## Research objective

The two source indicators (`docs/reference/*.pine`) are treated as **one combined
methodology**. Every concept in both scripts was translated into Python, run as an event
detector across the S&P 500 universe, and backtested with forward-return statistics,
robustness checks, and multiple-hypothesis-corrected significance testing, to answer
whether these concepts add predictive power beyond random entry on the same stocks.

This is **not** an attempt to replicate TradingView's visual output. Boxes, lines, colors,
and labels in the source scripts are irrelevant; only the underlying trigger logic matters.

## Project structure

```
smc-ict-research/
├── data/
│   ├── raw/          constituent list + committed GICS / index-entry snapshot
│   ├── bundle/       committed 50-ticker price sample + the previous version's outputs
│   └── cache/        cached OHLCV downloads, parquet (gitignored)
├── docs/
│   ├── manuscript.md, .pdf      the paper
│   ├── replication_guide.md     how to reproduce every number
│   ├── disambiguation.md        every ambiguous reading of the Pine source, and the choice made
│   ├── specs/*.yaml             machine-readable definition of every concept
│   ├── reference/               plain-text transcriptions of the source Pine scripts
│   └── superseded/              pre-correction reports, kept for the record
├── pine_parser/      pivot, leg and ATR primitives
├── signals/          SMC and ICT detectors; the fail-closed EVENT_REGISTRY
├── backtest/         forward returns (engine.py), costs (engine_tc.py), baselines
├── analytics/        statistics, master_stats, walkforward, montecarlo, sensitivity,
│                     survivorship, sectors, regimes, rankings, combinations
├── utils/            config, rng (BLAKE2b seeds), prices (loader + OHLC repair),
│                     universe (GICS, index entry), report generators
├── tools/            calibration study, manuscript facts and checks, figures, PDF,
│                     reviewer check, replication package, spec generator
├── tests/            look-ahead, detector rules, statistics, calibration, Pine fidelity
├── results/          generated outputs: reports, tables, figures
├── main.py           CLI entry point (one stage per command; `all` runs the pipeline)
├── app.py, streamlit_app.py   dashboards
└── Dockerfile, run_full_pipeline.sh, run_fast_validation.sh
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the pipeline

```bash
python main.py all                 # ingest -> detect -> backtest -> statistics -> ... -> report
python main.py sensitivity         # parameter sweeps (slow; excluded from `all`)
python tools/calibration_study.py  # size of each significance test under a zero edge
python tools/make_figures.py && python tools/build_manuscript_pdf.py
python tools/check_manuscript_numbers.py
```

[`docs/replication_guide.md`](docs/replication_guide.md) lists every stage with its runtime
and outputs.

## Running the dashboard

Two front ends, same data, same charts — both call the identical framework-agnostic functions
in `dashboard/analysis.py`, so they can never disagree with each other.

```bash
python app.py                   # Gradio, http://localhost:7860
streamlit run streamlit_app.py  # Streamlit, http://localhost:8501
```

Every number displayed is read from files the pipeline already produced; nothing is
recalculated inside the UI.

## Data source

- **Price data:** `yfinance`, daily OHLCV, 2010-01-01 to 2026-06-13, cached locally under
  `data/cache/` (parquet). **498 of 503** constituents download; five (`AVB`, `EA`, `EQR`,
  `HONA`, `SATS`) return no data at this snapshot, verified permanent by retrying each
  individually. **496** have at least 300 bars and enter the study.
- **Universe and sectors:** `data/raw/sp500_constituents.csv` defines the universe.
  Sectors (published GICS) and index-entry dates come from a committed snapshot,
  `data/raw/sp500_wikipedia_snapshot.csv`, refreshed only deliberately by
  `tools/refresh_universe.py`, so results never depend on when they were run. Dotted
  tickers (`BRK.B`, `BF.B`) are converted to `-` for yfinance.
- **Survivorship bias (important):** the constituent list is a 2026 snapshot applied to
  2010–2026. Of the 498 constituents with data, 265 were index members at the sample start
  and 233 joined later, so at least 235 since-removed members are absent. A
  membership-aware re-test removes the look-ahead part of the bias exactly (no concept
  beats the null either way); the absent firms cannot be recovered from free sources.

## Methodology

1. **Concept extraction** (`docs/concepts_extraction.md`, `docs/task02_pine_analysis.md`):
   every concept in both Pine scripts was documented with exact trigger logic and
   cross-referenced against each script's `alertcondition()` list. **Rejection Blocks** and
   **Optimal Trade Entry** have no corresponding logic in either script and are **not
   implemented** (not invented either).
2. **Translation** (`pine_parser/`, `signals/`): overlapping vocabulary between the two
   scripts is kept as separate, independently testable signal families. Every ambiguous
   reading is recorded in `docs/disambiguation.md`; each concept has a formal specification
   in `docs/specs/`.
3. **Event detection** (`signals/event_engine.py`): every detector runs on every cached
   ticker. A boolean column is tradeable only if registered in `EVENT_REGISTRY` with an
   explicit direction; anything else raises.
4. **Backtesting** (`backtest/engine.py`): forward returns at 1, 2, 3, 5, 10, 20, 40 and 60
   trading days, entering at the event bar's close and reading only strictly later bars.
5. **Statistical validation** (`analytics/statistics.py`, `analytics/master_stats.py`):
   - **Benchmark:** each trade against its own ticker's unconditional h-day return — a
     composition-matched random-entry null.
   - **Primary test:** calendar-time Newey–West on the per-trade excess, one-sided, with
     BH-FDR across all 352 hypotheses. A concept beats the null only with a positive excess,
     FDR survival and at least 30 trades. A separate two-sided family asks whether any
     concept is significantly worse.
   - **Secondary test:** exact rotation of each concept's entry calendar over every
     admissible offset (FFT), preserving which trades share a date.
   - **Calibration:** `tools/calibration_study.py` measures each test's size in six
     zero-edge designs; this is why the calendar-time test is primary.
   - **Power:** per-concept minimum detectable effect and one-sided 95% upper bounds.
6. **Robustness** (`analytics/*`): purged walk-forward (train 3y / test 1y / step 1y),
   transaction costs (11–26 bp round trip), parameter sweeps, a membership-aware
   survivorship re-test, GICS sectors with power analysis, and trend × volatility regimes.

## Key assumptions (see docs for full rationale)

- Daily bars only; intraday-only concepts (kill zones) are excluded.
- "Historical" mode semantics throughout (Pine's 500-bar "Present" display window is dropped).
- `ta.atr()` replicated via Wilder's RMA smoothing, not a simple moving average.
- SMC Premium/Discount zones use the literal all-time expanding high/low from the Pine
  source as the default; a rolling-window variant is available.
- Order blocks follow the source exactly: the most recently confirmed swing per side, and
  for a bullish SMC block the bar with the lowest low between the swing pivot and the
  break (LuxAlgo `storeOrdeBlock`), retired once mitigated. `tests/test_ob_fidelity.py`
  guards both.

## Validation performed

- **Unit tests:** 121 tests in `tests/`, run with `pytest tests/ -v`: pivot and leg
  primitives, every formalised detector rule on hand-constructed OHLC, the statistical
  engine, calibration regressions, Pine fidelity, deterministic seeding, transaction
  costs, data repair, index membership, and walk-forward purging.
- **No look-ahead, proved mechanically** (`tests/test_no_lookahead.py`): an index-position
  audit asserts every exit and excursion bar is strictly after the entry bar, and
  truncation invariance recomputes every registered detector on data cut at bar *i*. A
  canary test confirms the probe still detects a known-leaky column, so a pass is not
  vacuous.
- **Calibrated inference:** `results/test_calibration.csv` reports each test's size in six
  zero-edge designs; `tests/test_audit_regressions.py` keeps the primary test calibrated
  on clustered signals.
- **Reproducibility:** seeds derive from BLAKE2b over a stable label, never Python's salted
  `hash()`; a test pins one derived value. Every run writes `results/run_manifest.json`
  and `results/seed.txt`. The exact rotation test needs no seed at all.
- **Data quality:** exactly **3 materially invalid OHLC bars** exist in the universe (APH
  2021-05-05 and 2023-06-05, HUBB 2021-05-05) and are repaired, not merely counted.
- **Artefact checks:** `python tools/check_artifacts.py` asserts every required output
  exists, that no concept is flagged as beating the null with a non-positive excess, and
  that no forward-looking label reached the event table.
- **Manuscript verification:** `python tools/check_manuscript_numbers.py` recomputes every
  numeric claim in the paper from the artefacts and checks that its text still appears.
- **Adversarial pre-read:** `python tools/reviewer_check.py` writes
  `results/reviewer_report.md`, listing likely referee objections, each marked ADDRESSED,
  PARTIAL or EXPOSED.

## Reproducing

```bash
pytest tests/ -v                 # 121 tests, ~30 s, no network
./run_fast_validation.sh         # hermetic 12-ticker end-to-end, 2-4 min
./run_full_pipeline.sh           # full study, 3-6 h, needs network
```

Or with Docker:

```bash
docker build -t smc-ict-research . && docker run --rm -v "$PWD/results:/app/results" smc-ict-research full
```

## Limitations

1. **Power.** The median concept's minimum detectable edge is 45 bp; edges of 10–30 bp
   cannot be excluded for most concepts, and the primary test is conservative for
   dispersed signals.
2. **Survivorship, partly corrected** — at least 235 since-removed index members are absent.
3. **Daily bars only** — kill zones and all intraday structure are out of scope. SMC/ICT is
   most often taught on intraday FX and futures.
4. **Two specific implementations**, not SMC/ICT as a discretionary practice.
5. **Symmetric short mechanics** — no borrow cost or availability constraint.
6. **Path-dependent metrics are descriptive** — Sharpe, Calmar and max drawdown are computed
   over an overlapping, cross-sectional trade sequence, not an attainable equity curve.
7. **No economic mechanism** is proposed; this evaluates indicator logic, not theory.

## License

**Two licenses, split by what's actually derivative.** Most of this repository — the
statistical methodology, backtest engine, data pipeline, dashboard, tests, tooling, and
manuscript — is original work released under **MIT** (`SPDX-License-Identifier: MIT`,
full text in [`LICENSE`](LICENSE)). Five files are a line-by-line translation of LuxAlgo's
own custom logic from two third-party Pine Script indicators and remain **CC BY-NC-SA 4.0**
(`SPDX-License-Identifier: CC-BY-NC-SA-4.0`, full text in
[`LICENSE-CC-BY-NC-SA`](LICENSE-CC-BY-NC-SA)):

- `docs/reference/ICT_Concepts_LuxAlgo.pine`, `docs/reference/SMC_Concepts_LuxAlgo.pine`
  (the source indicators themselves, © LuxAlgo)
- `pine_parser/legs.py` (LuxAlgo's own `leg()`/`swings()` swing-detection logic)
- `signals/ict_signals.py`, `signals/smc_signals.py`

Two related files are deliberately **MIT, not CC BY-NC-SA**, despite living in the same
directory: `pine_parser/pivots.py` replicates a documented TradingView Pine *platform*
built-in (`ta.pivothigh`/`ta.pivotlow`), not LuxAlgo's own code, and `pine_parser/atr.py`
implements Wilder's Average True Range, a public-domain formula from 1978 with no
relationship to LuxAlgo. Neither translates LuxAlgo's creative expression, so neither
carries a ShareAlike obligation.

Full reasoning, including why two adjacent `pine_parser/` files are MIT rather than
CC BY-NC-SA, is in [`NOTICE`](NOTICE).

GitHub's sidebar will correctly detect **MIT** as this repository's license — MIT is in
its `licensee` catalogue, unlike CC BY-NC-SA 4.0 (`GET /licenses/cc-by-nc-sa-4.0` still
404s, which is why the CC BY-NC-SA portion can't itself carry a detected badge). The MIT
badge describes the repository's default license correctly; it does not override the
CC BY-NC-SA 4.0 terms on the five paths above.

Not investment advice.
