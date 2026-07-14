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
│   └── data_access.py           read-only accessors the Gradio app calls
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

```bash
python app.py
```

Opens a local Gradio app with Home / Stock Explorer / Concept Explorer / Combination Explorer /
Rankings / Sector & Regime / Validation tabs. Every number displayed is read from files the
pipeline already produced — nothing is recalculated inside the UI.

## Data source

- **Price data:** `yfinance`, daily OHLCV, 2010-01-01 to 2026-06-13, cached locally under
  `data/cache/` (parquet) so re-runs never re-download unchanged history. 500 of 503
  constituents downloaded successfully; 2 failed (`HONA`, `SATS` — both flagged in advance in
  `docs/concepts_extraction.md` as likely thin/recent-listing tickers).
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
5. **Statistical validation** (`analytics/statistics.py`): bootstrap confidence intervals,
   one-sample and two-sample significance tests, effect sizes, and Benjamini-Hochberg
   false-discovery-rate correction across every concept/combination tested. **Two distinct
   significance tests are reported and deliberately kept separate**: significance vs. a
   zero-return null (`significant_vs_zero`), and significance vs. a random-entry baseline
   run through the identical backtest mechanics at the same holding periods
   (`significant_vs_baseline`, via `backtest/baseline_engine.py`). The first test alone is
   misleading over a long bull market (2010-2026) — almost any long-biased signal clears it
   from broad market drift alone. The dashboard's and report's headline
   `statistically_significant` flag uses the baseline comparison, not the zero-null one,
   wherever the baseline backtest is available.
6. **Analysis** (`analytics/*`): stock-level, concept-level, combination, sector, and market
   regime rankings, all built from the single backtested-trades table (no duplicated
   calculation between modules).

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

- **Data quality:** `results/data_quality_report.csv` — missing values, duplicate rows,
  invalid OHLC relationships, coverage ratios per ticker; 500/501 downloaded tickers passed
  clean, 1 (`HUBB`) flagged with a genuine anomalous single-day OHLC print, surfaced rather
  than silently patched.
- **Unit tests:** `tests/` covers the pivot/leg primitives and includes a regression test for
  the order-block bug described above. Run with `pytest tests/ -v`.
- **No-look-ahead construction:** verified by code review of `backtest/engine.py` — entry uses
  only the signal bar's close; every exit price, MAE, and MFE slice starts at `entry_position +
  1`.
- **Statistical rigor:** every concept/combination ranking reports a bootstrap CI, a p-value,
  an FDR-adjusted p-value, and an effect size — not just a point-estimate win rate.

## Limitations

- Sector mapping is a static, manually curated approximation, not a live data source.
- FVG/gap "filled" state uses a bounded 60-bar forward search (matching the longest backtest
  holding period) rather than an unbounded search, documented in `signals/ict_signals.py`.
- Combination analysis is capped at pairwise combinations of same-direction signals with a
  minimum occurrence floor, to keep the multiple-testing correction meaningful rather than
  testing thousands of near-empty combinations.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) are not implemented —
  no corresponding logic exists in the supplied source scripts.
- **Concept rankings compare against a random-entry baseline (see below); combination
  rankings currently only test against a zero-return null**, not yet against the same
  random-entry baseline. A concept "beating a zero-return null" over 2010-2026 (a long bull
  market) is a much weaker claim than "beating a random-entry baseline at the same
  frequency" — see the Methodology note below on why both tests are reported separately.
  Wiring the baseline comparison into `analytics/combinations.py` the same way it's wired
  into `analytics/concept_ranking.py` is a natural next step.
- A handful of signals have no inherent long/short polarity in the source scripts
  (`ict_nwog_formed`, `ict_ndog_formed`, `smc_equal_highs`, `smc_equal_lows` — these are
  reference/gap levels, not directional calls). The backtest engine defaults undirected
  signals to a long entry rather than dropping them, so their reported win rates should be
  read as "does price tend to rise after this reference level appears," not as a
  directional trading rule.
- This is a research tool, not investment advice; nothing here accounts for transaction costs,
  slippage, liquidity constraints, or position sizing.

## Future improvements

- Wire in a live sector/industry data source instead of the static mapping.
- Walk-forward / out-of-sample validation split (current results are in-sample across the full
  2010-2026 window).
- Transaction-cost-aware backtest variant.
- Extend the Fibonacci-between-concepts tool (currently display-only in source) into an actual
  feature (e.g. "is price in the 0.618-0.786 retracement zone between the last two order
  blocks") for combination analysis.

## License

The two source Pine Script indicators are © LuxAlgo, licensed CC BY-NC-SA 4.0. This research
codebase follows the same non-commercial share-alike spirit.
