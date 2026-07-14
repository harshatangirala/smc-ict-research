# SMC/ICT Statistical Edge Research

A quantitative research framework that tests whether Smart Money Concepts (SMC) and ICT
(Inner Circle Trader) trading concepts — as implemented in two specific LuxAlgo Pine Script
indicators — provide statistically significant, out-of-sample-honest trading edges on daily
OHLCV data for the S&P 500, from 2010-01-01 through 2026-06-13.

**Status: early scaffolding.** This project is being built incrementally, one approved task
at a time (see [`docs/concepts_extraction.md`](docs/concepts_extraction.md) for the first
completed milestone). This README will be filled in fully as each subsequent module lands;
right now it documents what exists so far.

## Research objective

The two source indicators (`docs/reference/*.pine`) are treated as **one combined
methodology**, not implemented separately. Every concept in both scripts is translated into
Python, run as an event detector across the full S&P 500 universe, and backtested with
forward-return statistics, robustness checks, and multiple-hypothesis-corrected significance
testing — with the explicit goal of answering whether these concepts add predictive power
beyond simple baselines (buy & hold, random entry, moving-average crossover, RSI mean
reversion, 52-week breakout, momentum).

This is **not** an attempt to replicate TradingView's visual output. Boxes, lines, colors, and
labels in the source scripts are irrelevant; only the underlying trigger logic matters.

## Project structure

```
smc-ict-research/
├── data/
│   ├── raw/              # static inputs (S&P 500 constituent list)
│   └── cache/             # cached OHLCV downloads (gitignored)
├── docs/
│   ├── concepts_extraction.md   # Requirement 1 deliverable: full concept spec
│   └── reference/                # plain-text transcriptions of the source Pine scripts
├── pine_parser/           # (planned) Pine → Python translation layer
├── signals/               # (planned) event detectors per concept
├── backtest/              # (planned) forward-return / statistics engine
├── analytics/              # (planned) ranking, combination, regime, sector analysis
├── dashboard/              # (planned) Gradio app
├── utils/                  # (planned) shared helpers (caching, logging, config)
├── tests/                   # (planned) unit tests
├── results/                 # generated research outputs (gitignored, kept as folder)
├── exports/                 # generated CSV/Excel/JSON deliverables (gitignored, kept as folder)
├── main.py                  # (planned) CLI entry point for the research pipeline
├── app.py                   # (planned) Gradio dashboard entry point
└── requirements.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Data source

- **Price data:** `yfinance`, daily OHLCV, 2010-01-01 to 2026-06-13, cached locally under
  `data/cache/` so re-runs never re-download unchanged history.
- **Universe:** `data/raw/sp500_constituents.csv`, the S&P 500 constituent list supplied for
  this project (ticker, company name, index weight as of list creation). Tickers containing a
  `.` (e.g. `BRK.B`, `BF.B`) are converted to `-` for yfinance compatibility during ingestion.

## Methodology

See [`docs/concepts_extraction.md`](docs/concepts_extraction.md) for the full, per-concept
breakdown of every SMC/ICT signal extracted from the two Pine scripts, how overlapping
vocabulary between the two scripts is reconciled without being force-merged, and the
assumptions carried forward into the Python translation. Backtesting, validation, and
dashboard methodology sections will be added here as those modules are built and approved.

## Development approach

This project is being developed one task at a time, with validation gates between stages and
explicit approval checkpoints, per the project's engineering standards. See commit history for
the milestone-by-milestone build log.

## Limitations (living section, updated as work proceeds)

- Two concepts referenced in general ICT literature — *Rejection Blocks* and *Optimal Trade
  Entry* — have no corresponding logic in either supplied Pine script and are therefore **not
  implemented**. See `docs/concepts_extraction.md` §4 for details.
- Several concepts (Killzones, intraday session logic) are intraday-only and have no daily-bar
  equivalent; they are documented but intentionally excluded from the daily event detector.

## Future improvements

Tracked as the corresponding modules are built; see the requirements captured in project
planning for the full 20-requirement scope (data ingestion, event detection, backtesting,
concept/stock/combination ranking, statistical validation, sector/regime analysis, Gradio
dashboard, GitHub CI).
