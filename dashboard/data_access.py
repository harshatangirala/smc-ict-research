"""Read-only data accessors for the dashboard. No calculation happens here or
in app.py/streamlit_app.py -- every number displayed is read from a file
already produced by the research pipeline, per the Task 13 validation gate
("no duplicated calculations inside the UI").

Two data sources, checked in order:
1. results/ -- the full local pipeline output (utils/config.RESULTS_DIR).
   Present after running `python main.py all` yourself. Gitignored: the
   trades table alone is ~760MB, far too large to commit.
2. data/bundle/ -- a lightweight, git-committed subset built by
   utils/build_cloud_bundle.py (full events, a 500k-row trade sample, price
   history for the top 50 tickers by index weight, and all the small
   ranking/analysis CSVs in full). This is what a fresh clone or a
   Streamlit Community Cloud deploy actually runs on.

Every accessor falls back from (1) to (2) automatically, so the dashboard
works out of the box after `git clone` even though the full multi-GB
pipeline output was never committed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from utils.config import DATA_CACHE_DIR, PROJECT_ROOT, RESULTS_DIR

BUNDLE_DIR = PROJECT_ROOT / "data" / "bundle"
BUNDLE_PRICES_DIR = BUNDLE_DIR / "prices"


def _resolve(filename: str) -> Path | None:
    """First existing path for `filename`, checking results/ then the
    bundled fallback. Returns None if neither has it."""
    full = RESULTS_DIR / filename
    if full.exists():
        return full
    bundled = BUNDLE_DIR / filename
    if bundled.exists():
        return bundled
    return None


def _safe_read_csv(filename: str) -> pd.DataFrame:
    path = _resolve(filename)
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _safe_read_parquet(filename: str) -> pd.DataFrame:
    path = _resolve(filename)
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except FileNotFoundError:
        return pd.DataFrame()


def using_bundled_data() -> bool:
    """True if the full local pipeline output isn't present and the
    dashboard is running on the lightweight committed bundle instead --
    used to show an honest "this is a demo subset" note in the UI."""
    return not (RESULTS_DIR / "trades.parquet").exists()


@lru_cache(maxsize=1)
def get_data_quality_report() -> pd.DataFrame:
    return _safe_read_csv("data_quality_report.csv")


@lru_cache(maxsize=1)
def get_master_events() -> pd.DataFrame:
    return _safe_read_parquet("master_events.parquet")


@lru_cache(maxsize=1)
def get_trades() -> pd.DataFrame:
    """Full trades.parquet if a local pipeline run produced it, else the
    bundled 500k-row sample (see utils/build_cloud_bundle.py)."""
    full = RESULTS_DIR / "trades.parquet"
    if full.exists():
        return _safe_read_parquet("trades.parquet")
    return _safe_read_parquet("trades_sample.parquet")


@lru_cache(maxsize=8)
def get_concept_rankings(holding_period: int | None = None) -> pd.DataFrame:
    df = _safe_read_csv("concept_rankings.csv")
    if holding_period is not None and "holding_period" in df.columns:
        df = df[df["holding_period"] == holding_period]
    return df


@lru_cache(maxsize=1)
def get_stock_rankings() -> pd.DataFrame:
    return _safe_read_csv("stock_rankings.csv")


@lru_cache(maxsize=1)
def get_combination_rankings() -> pd.DataFrame:
    return _safe_read_csv("combination_rankings.csv")


@lru_cache(maxsize=1)
def get_regime_analysis() -> pd.DataFrame:
    return _safe_read_csv("regime_analysis.csv")


@lru_cache(maxsize=1)
def get_sector_analysis() -> pd.DataFrame:
    return _safe_read_csv("sector_analysis.csv")


@lru_cache(maxsize=500)
def get_price_history(ticker: str) -> pd.DataFrame:
    full = DATA_CACHE_DIR / f"{ticker}.parquet"
    if full.exists():
        try:
            return pd.read_parquet(full)
        except FileNotFoundError:
            pass
    bundled = BUNDLE_PRICES_DIR / f"{ticker}.parquet"
    if bundled.exists():
        try:
            return pd.read_parquet(bundled)
        except FileNotFoundError:
            pass
    return pd.DataFrame()


def has_price_history(ticker: str) -> bool:
    return (DATA_CACHE_DIR / f"{ticker}.parquet").exists() or (BUNDLE_PRICES_DIR / f"{ticker}.parquet").exists()


def list_tickers() -> list[str]:
    events = get_master_events()
    if events.empty:
        return []
    return sorted(events["ticker"].unique().tolist())


def list_tickers_with_price_history() -> list[str]:
    """Subset of list_tickers() that actually has a chart to show -- the
    dropdown a fresh clone / cloud deploy should offer by default."""
    return sorted(
        p.stem for p in list(DATA_CACHE_DIR.glob("*.parquet")) + list(BUNDLE_PRICES_DIR.glob("*.parquet"))
    )


def list_signals() -> list[str]:
    events = get_master_events()
    if events.empty:
        return []
    return sorted(events["signal"].unique().tolist())


def summary_stats() -> dict:
    events = get_master_events()
    dq = get_data_quality_report()
    trades = get_trades()
    years = None
    if not events.empty:
        span = pd.to_datetime(events["date"])
        years = round((span.max() - span.min()).days / 365.25, 1)
    return {
        "total_stocks_analyzed": dq["ticker"].nunique() if not dq.empty else 0,
        "total_events": len(events),
        "total_trades_backtested": len(trades),
        "distinct_signals": events["signal"].nunique() if not events.empty else 0,
        "years_covered": years,
    }
