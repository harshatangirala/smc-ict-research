# Replication Guide

**SMC/ICT Statistical Edge Study** · branch `ssrn-ready/claude-opus-5`

This guide is self-contained. Following it end to end reproduces every number in
`docs/manuscript.md`, `results/validation_report.md` and
`results/master_summary.md`.

---

## 1. The one-line reproduction

```bash
docker build -t smc-ict-research . && docker run --rm -v "$PWD/results:/app/results" smc-ict-research full
```

Without Docker:

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && ./run_full_pipeline.sh
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and run the
stages individually (`python main.py ingest`, `detect`, …) — the shell scripts
assume a POSIX shell.

## 2. Three levels of reproduction

| Level | Command | Time | Network | What it establishes |
|---|---|---|---|---|
| **Tests** | `pytest tests/ -v` | ~30 s | no | Every invariant holds: no look-ahead, fail-closed registry, deterministic seeding, correct detector rules, calibrated statistics. |
| **Fast validation** | `./run_fast_validation.sh` | 2–4 min | no | The full pipeline runs end to end on 12 tickers from the committed sample and produces every artefact. Numbers will **not** match the paper — the universe is 12 tickers, not 496. |
| **Full run** | `./run_full_pipeline.sh` | 3–6 h | **yes** | Reproduces the published numbers. |

The fast path is hermetic: `data/bundle/prices/` holds a committed 50-ticker
sample, of which the fast path and CI use the first 12, so neither needs a Yahoo
Finance call. Use it for checking that a change did not break the pipeline.

## 3. Requirements

* **Python 3.11 or 3.12.** Tested on both.
* **~8 GB RAM.** The trade table is ~17.6 M rows (≈ 380 MB on disk, ~2 GB in
  memory during the statistics stage).
* **~2 GB disk** for the price cache and results.
* **Network** for the full run only, to reach Yahoo Finance via `yfinance`.

## 4. Stage by stage

```bash
python main.py ingest        # ~2 min   503 tickers -> data/cache/*.parquet
python main.py detect        # ~6 min   -> results/master_events.parquet
python main.py backtest      # ~4 min   -> results/trades.parquet
python main.py baseline      # ~2 min   -> results/baseline_trades.parquet
python main.py statistics    # ~2 h     -> results/statistics_master.csv
python main.py analyze       # ~30 min  -> concept/stock/combination/sector/regime CSVs
python main.py walkforward   # ~1 min   -> results/walkforward_{detail,summary}.csv
python main.py costs         # ~10 s    -> net-of-cost and break-even tables
python main.py montecarlo    # ~8 min   -> rotation_null_all.csv (exact rotation, all 352
                             #             hypotheses) and monte_carlo.csv (15 concepts)
python main.py survivorship  # ~3 min   -> survivorship_*.csv, sector_map_disagreements.csv
python main.py sensitivity   # ~2 h     -> broad, random and targeted sweeps (excluded from `all`)
python main.py report        # ~5 s     -> validation_report.md, master_summary.md
python tools/make_figures.py # ~10 s    -> results/figures/*.png + matching *.csv
python tools/calibration_study.py  # ~20 min on 6 cores -> results/test_calibration.csv
python tools/manuscript_facts.py   # ~1 min -> results/manuscript_facts.json
```

Timings are for the final profile (10,000 bootstrap iterations) on a 12-thread
laptop; the statistics stage is dominated by the bootstrap over 17.6 M trades.

`python main.py all` runs everything except `sensitivity`, which re-runs
detection once per grid point and dominates total runtime. Add `--skip ingest`
to reuse an existing cache.

**One deviation from the original brief.** The brief's acceptance criteria say
`python main.py backtest` should produce `results/statistics_master.csv`. It
does not, by design: `backtest` writes `trades.parquet`, and `statistics` writes
`statistics_master.csv`. Keeping them separate matters because the statistics
stage is the slowest in the pipeline at the final bootstrap budget and is re-run
far more often than the 4-minute backtest, so fusing them would force a full
recompute of 17.6 M trades every time a test changes. `python main.py all` produces both, and
the `backtest` stage logs the handoff explicitly.

## 5. Determinism

Reproducibility is a property the code enforces, not a hope:

* **Seeding.** `utils/rng.py` derives every child seed with BLAKE2b over a
  UTF-8 label. It does **not** use Python's `hash()`, which is salted per
  process — the defect that made the original baseline irreproducible. The master
  seed and derivation are written to `results/seed.txt`.
* **Run manifest.** Every invocation writes `results/run_manifest.json` with the
  git hash, profile, bootstrap budget, seed, α and Python version.
* **Profiles.** `SMC_ICT_PROFILE=final` (default) uses 10,000 bootstrap
  iterations; `fast` uses 5,000. The published numbers are `final`.
* **Archiving.** `run_full_pipeline.sh` copies each run's outputs to
  `results/runs/<timestamp>_<githash>/`.

A test pins one derived seed value (`derive_seed("AAPL", 42) == 3361008404`), so
a change to the derivation scheme fails CI rather than silently changing results.

## 6. Expected variation between runs

| Source | Effect |
|---|---|
| **Yahoo Finance revisions** | Yahoo back-adjusts for splits and dividends, so a cache rebuilt on a later date differs slightly from one built earlier. Mean returns move in the fourth decimal; no headline count has changed across rebuilds during this work. |
| **Universe drift** | `data/raw/sp500_constituents.csv` is a fixed snapshot. Five tickers (AVB, EA, EQR, HONA, SATS) return no data and are permanently unavailable; 498 of 503 download, 496 pass the 300-bar minimum. Sectors and index-entry dates come from `data/raw/sp500_wikipedia_snapshot.csv`, a committed September 2026 snapshot refreshed only by `tools/refresh_universe.py`; it differs from the June list by four removals and four additions, none of which are in the analysed universe. |
| **Everything else** | Deterministic. Same cache + same seed + same profile ⇒ identical output, verified across processes. |

## 7. Verifying a run

```bash
python tools/check_artifacts.py
```

This asserts every required artefact exists with a plausible row count, that
`statistics_master.csv` carries all 21 required columns, that **no concept is
flagged as beating the null with a non-positive excess return**, that no
forward-looking label reached the event table, and that every event carries
direction ±1. It exits non-zero naming the first failure.

## 8. Where each published claim lives

| Claim | Artefact |
|---|---|
| Concept counts (beats / loses / indistinguishable) | `results/statistics_master.csv`, `beats_matched_random` |
| Per-concept metrics, CIs, effect sizes | `results/statistics_master.csv`, `results/master_summary.md` |
| Out-of-sample results | `results/walkforward_summary.csv` |
| Cost sensitivity and break-even | `results/breakeven_costs.csv`, `results/cost_sensitivity_grid.csv` |
| Exact rotation test, all 352 hypotheses | `results/rotation_null_all.csv` |
| Monte Carlo comparison of resampling schemes | `results/monte_carlo.csv` |
| Every number in the manuscript, computed in one place | `results/manuscript_facts.json` (`tools/manuscript_facts.py`) |
| Sector and regime breakdowns | `results/sector_analysis.csv`, `results/regime_analysis.csv` |
| Data coverage and repairs | `results/data_quality_report.csv`, `results/validation_report.md` §2 |
| Figures (with their underlying data) | `results/figures/*.png` and matching `*.csv` |
| Calibration of the significance tests | `results/test_calibration.csv` (`tools/calibration_study.py`) |
| Survivorship: size of the gap, membership-aware re-test | `results/survivorship_*.csv`, `results/survivorship_comparison.json` |
| Sector power and the GICS audit | `results/sector_power.csv`, `results/sector_map_disagreements.csv` |

## 9. Concept definitions

Every detector has a machine-readable specification in `docs/specs/*.yaml`:
formal boolean definition, directionality, parameters with defaults and allowed
ranges, expected minimum occurrences, and an explicit causality argument. CI
regenerates them and fails on drift, and a test asserts the directions in the
specs match `EVENT_REGISTRY`.

## 10. Building the replication package

```bash
python tools/make_replication_package.py
```

Writes `results/replication_package.zip` containing the manuscript, this guide,
the key CSVs, the figures, the specs, the seed and run manifests, and the source
tree needed to rerun.

## 11. Known limitations that affect replication

* **Survivorship bias, partly corrected.** The constituent list is a 2026
  snapshot applied to 2010–2026. Trading a firm before it joined the index is
  removed by the membership-aware re-test (`python main.py survivorship`); firms
  removed from the index since 2010 are absent and cannot be recovered from free
  sources.
* **Daily bars only.** Kill zones and intraday structure are out of scope. This
  is a study of the daily-bar subset of SMC/ICT, not of the methodology as
  traded.
* **Long/short mechanics are symmetric.** Short signals are the negation of the
  forward return, with no borrow cost or availability constraint.
* **Not investment advice.** The study is an evaluation of publicly documented
  indicator logic.
