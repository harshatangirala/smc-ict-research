# Task 3 — Python Architecture

Each module has exactly one responsibility. Downstream modules only ever import from
upstream modules (no circular deps), and no module recomputes something another module
already computed (per the Task 3 "no duplicated functionality" validation gate).

```
utils/            <- shared infrastructure, no research logic
  config.py         central paths / date range / concept-parameter defaults
  logging_config.py shared logger factory
  data_loader.py    yfinance download + parquet cache + retry/parallel logic
  data_quality.py   Task 4 validation report
  export.py         save/load parquet & csv/xlsx/json export helpers
  audit_cache.py    audits the parquet price cache for gaps/staleness
  check_missing.py  reports tickers/dates missing from the universe
  generate_report.py auto-generates docs/final_research_report.md from results/*
  rebuild_quality_report.py rebuilds the data quality report from cached data
  build_cloud_bundle.py builds the lightweight pre-computed data/bundle/
  render_pdf.py     renders an HTML report to PDF via Playwright

pine_parser/       <- low-level primitives shared by multiple concept detectors
  pivots.py          ta.pivothigh/pivotlow equivalent (2-sided confirmed pivot)
  legs.py            SMC leg()/startOfNewLeg() rolling-window pivot
  atr.py             Wilder RMA ATR (see Ambiguity A6)

signals/           <- one file per source script, one function per concept
  ict_signals.py     MSS, BOS, OB, Displacement, Volume Imbalance, FVG/IFVG,
                     BPR, Liquidity pools+sweeps, NWOG/NDOG
  smc_signals.py     Internal/Swing BOS+CHoCH, Internal/Swing OB, EQH/EQL,
                     FVG, Premium/Discount/Equilibrium, Strong/Weak H/L,
                     MTF D/W/M levels
  event_engine.py    runs every detector over every ticker, assembles the
                     master event dataframe (Task 6)

backtest/
  engine.py          forward returns at every holding period, no look-ahead
  metrics.py         win rate, Sharpe, Sortino, profit factor, MAE/MFE, etc.
  baselines.py       buy&hold, random entry, EMA cross, RSI reversion,
                     52w breakout, momentum (the benchmark comparisons)
  baseline_engine.py runs the random-entry and other baseline strategies
                     through the same backtest engine as the real signals --
                     central to the project's headline "beats a naive
                     benchmark" methodology

analytics/
  statistics.py      bootstrap CI, significance tests, effect size, FDR
  stock_ranking.py    Task 9
  concept_ranking.py  Task 10
  combinations.py     Task 11
  regimes.py           Task 12 (bull/bear/sideways + rolling Premium/Discount)
  sectors.py           Task 12 (sector grouping)

dashboard/
  data_access.py     read-only accessors both front ends call (no calculation)
  analysis.py        chart/table builders shared by both front ends

data/bundle/       <- lightweight pre-computed data bundle checked into git so
                      the dashboard works on a fresh clone without running the
                      full pipeline; built by utils/build_cloud_bundle.py

tests/
  test_pivots.py, test_legs.py, test_ict_order_blocks.py -- unit tests with
  synthetic OHLC fixtures that have a hand-computed expected answer

main.py           CLI: orchestrates ingest -> detect -> backtest -> baseline
                     -> analyze -> export
app.py            Gradio dashboard entry point, imports dashboard/ only
streamlit_app.py  Streamlit dashboard entry point (second front end,
                     alongside app.py), also imports dashboard/ only
```

## Data contracts between modules

- `data_loader.get_prices(ticker) -> pd.DataFrame` indexed by date, columns
  `open, high, low, close, volume`, always sorted ascending, never containing
  partially-adjusted data (see Task 4 validation).
- `event_engine.build_master_events() -> pd.DataFrame` with one row per
  `(ticker, date, signal_name)` and boolean/float payload columns — this is
  the **single artifact** every downstream module (backtest, analytics,
  dashboard) reads. No module re-derives events from raw OHLC directly except
  `event_engine.py`.
- `backtest.engine.run() -> pd.DataFrame` one row per `(ticker, date,
  signal_name, holding_period)` with the forward return and MAE/MFE for that
  trade — the single artifact `analytics/*` and `dashboard/*` read for
  performance numbers.

## Validation gate for this task

- Every planned component above maps to exactly one Requirement/Task from the
  24-milestone plan; no two modules compute the same statistic.
- Folder structure matches `README.md`'s documented layout (Task 1).
