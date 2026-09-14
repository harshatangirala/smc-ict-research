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

_See `docs/final_research_report.md` for the full, auto-generated report, and `docs/ssrn_paper.pdf`
for the academic working-paper writeup with literature review._

**The aggregate, unconditional claim "SMC/ICT signals beat chance" is not supported by this
dataset — and neither is the narrower claim that a specific minority of concepts do.** Every one
of the 42 tested concepts clears a *zero-return* null (42/42) — but that is a weak bar over
2010-2026, a long bull market, where almost any long-biased signal shows a positive mean return
from broad market drift alone. Tested properly against a **random-entry baseline**, run through
identical backtest mechanics at the same frequency with standard errors **clustered by ticker**
(trades on the same stock share overlapping holding windows and are not independent draws),
**35/42** concepts differ significantly from the baseline — and every one of those 35 differs in
the *negative* direction. **0/42** concepts, **0/60** tested combinations, **0/12** sectors, and
**0/9** market-regime cells beat the baseline with statistical significance. Where the data comes
closest to a positive result, it stops well short of significance (see Section 2 of the final
report). See Section 1 for the full picture.

This finding went through two rounds of correction, both driven by validation catching a result
that looked too good to be true. The first: an initial pipeline run reported all 42 concepts as
"significant" using only the zero-return test — a red flag, not a good result — which led to
building `backtest/baseline_engine.py` and rewiring every ranking module to compare against a
random-entry baseline. The second, later round: an independent audit found that baseline itself
had a seeding bug (roughly 84% of tickers were drawing *identical* "random" dates rather than
independent ones, because the seed was derived from a low-cardinality hash of each ticker's first
cached bar date), that significance tests treated non-independent, overlapping-window trades as
i.i.d. draws, and that sector/regime rankings carried no significance test at all despite the
docs claiming they did. Fixing all three — along with an unrelated bug in the SMC order-block
detector's bullish/bearish candle selection — changed the result from "a real, specific minority
of signals clear the bar" to the clean null above. See commit history for the full account.

## Project structure

```
smc-ict-research/
├── data/
│   ├── raw/                 static inputs (S&P 500 constituent list)
│   ├── cache/                cached OHLCV downloads, parquet (gitignored)
│   └── bundle/                lightweight pre-computed data bundle checked into git, so the
│                                dashboard works on a fresh clone without running the full
│                                pipeline (built by utils/build_cloud_bundle.py)
├── docs/
│   ├── concepts_extraction.md   full per-concept technical spec (Task 1/2)
│   ├── task02_pine_analysis.md  plain-English + dependency + parameter + Pine-builtin inventory
│   ├── architecture.md           module responsibility map (Task 3)
│   ├── deployment_notes.md        notes on the Cloudflare quick-tunnel dashboard deploy path
│   ├── final_research_report.md   auto-generated executive report (utils/generate_report.py)
│   ├── findings_report.html       polished public write-up (findings_report.pdf is its PDF render)
│   ├── ssrn_paper.pdf             academic working-paper draft, with literature review
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
│   ├── baselines.py             buy&hold, random entry, EMA/RSI/breakout/momentum benchmarks
│   └── baseline_engine.py       runs the baseline strategies through the same backtest engine,
│                                  across the universe, so they're comparable on equal footing
├── analytics/
│   ├── statistics.py           bootstrap CI, cluster-robust significance tests, FDR correction
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
│   ├── export.py                 Task 14 CSV/Excel/JSON export
│   ├── generate_report.py        builds docs/final_research_report.md from results/*
│   ├── render_pdf.py             renders an HTML report to PDF via Playwright/Chromium
│   ├── build_cloud_bundle.py     builds data/bundle/ for a dependency-free dashboard clone
│   ├── audit_cache.py, check_missing.py, rebuild_quality_report.py   cache/data-quality helpers
├── tests/                        unit tests (pivot/leg/order-block regression tests)
├── results/                      generated research outputs (gitignored, folder kept)
├── exports/                      generated CSV/Excel/JSON deliverables (gitignored, folder kept)
├── main.py                       CLI entry point (ingest / detect / backtest / baseline /
│                                    analyze / export)
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
python main.py baseline    # run baseline/benchmark strategies through the same backtest engine
python main.py analyze     # concept/stock/combination/sector/regime rankings
python main.py export      # write CSV/Excel/JSON deliverables to exports/
python main.py all         # run every stage in order (includes baseline)
```

Running stages individually rather than via `all`? Don't skip `baseline` — every ranking's
headline significance flag depends on it, and running `analyze` without it first just means every
`*_vs_baseline` column comes back empty.

## Read the findings

- **`docs/findings_report.html`** (`docs/findings_report.pdf` for the PDF render) — the polished,
  public-facing write-up: headline scoreboard, per-concept/combination/sector/regime breakdowns,
  and a plain-English methodology section.
- **`docs/ssrn_paper.pdf`** — the same underlying results, written up as an academic working
  paper: formal abstract, literature review situating this study against the technical-analysis
  data-snooping literature (Brock/Lakonishok/LeBaron, White's Reality Check, Hansen's SPA test,
  Bajgrowicz & Scaillet's FDR-based critique), and a full methodology section.
- **`docs/final_research_report.md`** — the shortest version: auto-generated directly from
  `results/*`, regenerated by `python -m utils.generate_report` after any pipeline re-run.

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
  `data/cache/` (parquet) so re-runs never re-download unchanged history. 501 of 503
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
5. **Statistical validation** (`analytics/statistics.py`): cluster-robust (by-ticker) confidence
   intervals, one-sample and two-sample significance tests, effect sizes, and Benjamini-Hochberg
   false-discovery-rate correction across every concept/combination/sector/regime tested (and,
   with a naive rather than clustered test, for stocks — see Limitations).
   **Two distinct significance tests are reported and deliberately kept separate**: significance
   vs. a zero-return null (`significant_vs_zero`), and significance vs. a random-entry baseline
   run through the identical backtest mechanics at the same holding periods
   (`significant_vs_baseline`, via `backtest/baseline_engine.py`). The first test alone is
   misleading over a long bull market (2010-2026) — almost any long-biased signal clears it
   from broad market drift alone.
   **A third flag, `beats_baseline`, is what "N concepts beat the baseline" headlines should
   read from, not `significant_vs_baseline`**: the latter is two-sided (it flags a concept
   whether it's significantly *better than* or *worse than* the baseline), while
   `beats_baseline` additionally requires the excess return to be positive. Collapsing the two
   is a real mistake this project made and then caught — see "Key findings."
   Significance tests are clustered by ticker (a cluster-robust "sandwich" variance estimator,
   not a naive per-trade t-test), because trades on the same ticker share overlapping
   forward-return windows and are not independent draws; a naive test understates the true
   standard error and can manufacture significance out of noise as sample size grows. This
   corrects for *within-ticker* correlation only, not a full two-way (ticker-by-date) correction
   for cross-ticker correlation on shared market-wide dates — see Limitations.
6. **Analysis** (`analytics/*`): stock-level, concept-level, combination, sector, and market
   regime rankings, all built from the single backtested-trades table (no duplicated
   calculation between modules). Every module compares against the baseline consistently:
   - `concept_ranking.py` / `combinations.py`: each concept/combination vs. the universe-wide
     random-entry baseline.
   - `stock_ranking.py`: each ticker's signal-trades vs. **that same ticker's own**
     random-entry baseline (so a stock ranking highly isn't just rewarded for having rallied
     hard over the period — see `results/stock_rankings.csv` or the final report's stock
     breakdown for the current per-ticker ranking).
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

- **Data quality:** `results/data_quality_report.csv` — missing values, duplicate rows,
  invalid OHLC relationships, coverage ratios per ticker; 500/501 downloaded tickers passed
  clean, 1 (`HUBB`) flagged with a genuine anomalous single-day OHLC print, surfaced rather
  than silently patched.
- **Unit tests:** `tests/` covers the pivot/leg primitives and includes a regression test for
  the order-block bug described above. Run with `pytest tests/ -v`.
- **No-look-ahead construction:** verified by code review of `backtest/engine.py` — entry uses
  only the signal bar's close; every exit price, MAE, and MFE slice starts at `entry_position +
  1`.
- **Statistical rigor:** every concept/combination/sector/regime ranking reports a bootstrap CI,
  a p-value against a zero-return null, a p-value against a random-entry baseline, FDR-adjusted
  versions of both, and an effect size — not just a point-estimate win rate. This distinction
  changed the headline conclusion materially (see "Key findings" above) and was caught during
  self-review, not requested — the first full pipeline run reported 42/42 concepts "significant"
  using only the zero-return test, which was the signal that a baseline comparison was missing,
  not present. Sector and regime rankings did **not** carry any significance test at all in the
  first published cut of this project (a raw excess-return point estimate with no test of
  whether it differs from noise, despite this section previously claiming otherwise) — caught
  in a later audit and fixed; they now go through the same cluster-robust test as everything
  else.
- **Baseline reproducibility:** the random-entry baseline's per-ticker seed was, in an earlier
  version, derived from a low-cardinality hash of each ticker's first cached bar date — since
  most tickers share that date, roughly 84% of the universe was drawing *identical* "random"
  entries rather than independent ones. Caught in the same audit; the fix seeds each ticker
  from a stable hash of its own symbol. This bug is the reason results shifted materially
  between the first published cut of this study and the current one (see "Key findings").

## Limitations

- **Standard errors are clustered by ticker only, not two-way (ticker-by-date).** This corrects
  for within-ticker serial correlation from overlapping holding-period windows; it does not
  separately correct for cross-ticker correlation on shared market-wide dates (e.g. 2020, 2022).
  A full two-way correction would tighten inference further, not loosen it — the results here
  should be read as, if anything, a conservative upper bound on how much would survive that
  correction.
- **The universe is not point-in-time-correct.** `data/raw/sp500_constituents.csv` reflects
  current-day S&P 500 membership and weights, applied retroactively across the full 2010-2026
  window. Constituents removed from the index during the period are entirely absent;
  constituents added more recently contribute their full available trading history despite not
  having been index members for most of it. A form of survivorship bias; no point-in-time
  membership data was available to correct it.
- **Per-ticker significance tests (`stock_ranking.py`) are not cluster-corrected** — a single
  ticker's own trades have no cluster structure to cluster by, so this module still uses the
  naive per-trade test. Read per-stock excess-return figures as directional evidence, not a
  validated edge, more so than for the other modules.
- **The stock-ranking table covers 499 of the 501 tickers with usable price data**, not 501:
  two tickers (`FDXF`, `Q`) have clean price history but produced zero detected SMC/ICT events
  across the full window and drop out of that specific table without a separate flag.
- Sector mapping is a static, manually curated approximation, not a live data source.
- FVG/gap "filled" state uses a bounded 60-bar forward search (matching the longest backtest
  holding period) rather than an unbounded search, documented in `signals/ict_signals.py`.
- Combination analysis is capped at pairwise combinations of same-direction signals with a
  minimum occurrence floor, to keep the multiple-testing correction meaningful rather than
  testing thousands of near-empty combinations.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) are not implemented —
  no corresponding logic exists in the supplied source scripts.
- Per-ticker and per-sector/regime baseline comparisons have smaller sample sizes than the
  universe-wide concept-level comparison (a per-ticker baseline is only ~50 random entries),
  so those significance tests are correspondingly less powered — read per-stock excess-return
  figures as directional evidence and the accompanying p-value as the honest confidence level,
  not as a list of proven single-stock edges.
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
