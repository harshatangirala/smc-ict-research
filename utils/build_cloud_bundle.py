"""Build a lightweight, git-committable data bundle under data/bundle/ so
the dashboard has something real to show on a fresh clone / cloud deploy
(Streamlit Community Cloud, Hugging Face Spaces), where the full pipeline
output (results/trades.parquet alone is ~760MB) is never committed.

Bundle contents:
- All the small aggregate ranking/analysis CSVs (a few hundred KB total).
- master_events.parquet in full (~27MB -- every detected event, no data loss).
- A reproducible 500k-row random sample of trades.parquet (~15-25MB) so the
  Concept Explorer's return-distribution histogram still has real data.
- Daily OHLCV for the top 50 S&P 500 constituents by index weight (~63% of
  total index weight), so the Stock Explorer works for the names most people
  would actually look up in a demo, without shipping all 500 price files.

Run after `python main.py all` has produced a full local results/ directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from utils.config import DATA_CACHE_DIR, PROJECT_ROOT, RESULTS_DIR, SP500_CONSTITUENTS_CSV
from utils.data_loader import normalize_ticker
from utils.logging_config import get_logger

log = get_logger("build_cloud_bundle")

BUNDLE_DIR = PROJECT_ROOT / "data" / "bundle"
BUNDLE_PRICES_DIR = BUNDLE_DIR / "prices"
TOP_N_TICKERS = 50
TRADES_SAMPLE_SIZE = 500_000
SAMPLE_SEED = 42

SMALL_CSVS = [
    "concept_rankings.csv",
    "stock_rankings.csv",
    "combination_rankings.csv",
    "sector_analysis.csv",
    "regime_analysis.csv",
    "data_quality_report.csv",
]


def build_bundle() -> None:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_PRICES_DIR.mkdir(parents=True, exist_ok=True)

    for name in SMALL_CSVS:
        src = RESULTS_DIR / name
        if src.exists():
            shutil.copy(src, BUNDLE_DIR / name)
            log.info("Bundled %s", name)
        else:
            log.warning("Skipping %s: not found in results/ (run main.py analyze first)", name)

    events_src = RESULTS_DIR / "master_events.parquet"
    if events_src.exists():
        shutil.copy(events_src, BUNDLE_DIR / "master_events.parquet")
        log.info("Bundled master_events.parquet (%.1f MB)", events_src.stat().st_size / 1e6)

    trades_src = RESULTS_DIR / "trades.parquet"
    if trades_src.exists():
        trades = pd.read_parquet(trades_src)
        sample = trades.sample(n=min(TRADES_SAMPLE_SIZE, len(trades)), random_state=SAMPLE_SEED)
        sample.to_parquet(BUNDLE_DIR / "trades_sample.parquet")
        log.info("Bundled trades_sample.parquet: %d of %d rows (%.1f MB)",
                  len(sample), len(trades), (BUNDLE_DIR / "trades_sample.parquet").stat().st_size / 1e6)
    else:
        log.warning("Skipping trades sample: results/trades.parquet not found")

    constituents = pd.read_csv(SP500_CONSTITUENTS_CSV)
    constituents["Weight"] = constituents["Weight"].str.rstrip("%").astype(float)
    constituents["YFSymbol"] = constituents["Symbol"].apply(normalize_ticker)
    top_tickers = constituents.nlargest(TOP_N_TICKERS, "Weight")["YFSymbol"].tolist()

    copied = 0
    for ticker in top_tickers:
        src = DATA_CACHE_DIR / f"{ticker}.parquet"
        if src.exists():
            shutil.copy(src, BUNDLE_PRICES_DIR / f"{ticker}.parquet")
            copied += 1
    log.info("Bundled price history for %d/%d top-weight tickers", copied, len(top_tickers))

    total_size = sum(f.stat().st_size for f in BUNDLE_DIR.rglob("*") if f.is_file())
    log.info("Total bundle size: %.1f MB", total_size / 1e6)


if __name__ == "__main__":
    build_bundle()
