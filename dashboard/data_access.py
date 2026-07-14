"""Read-only data accessors for the dashboard. No calculation happens here or
in app.py -- every number displayed is read from a file already produced by
the research pipeline (utils/config.RESULTS_DIR / EXPORTS_DIR), per the
Task 13 validation gate ("no duplicated calculations inside the UI").
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from utils.config import DATA_CACHE_DIR, RESULTS_DIR


def _safe_read_csv(path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        return pd.DataFrame()


def _safe_read_parquet(path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except FileNotFoundError:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def get_data_quality_report() -> pd.DataFrame:
    return _safe_read_csv(RESULTS_DIR / "data_quality_report.csv")


@lru_cache(maxsize=1)
def get_master_events() -> pd.DataFrame:
    return _safe_read_parquet(RESULTS_DIR / "master_events.parquet")


@lru_cache(maxsize=1)
def get_trades() -> pd.DataFrame:
    return _safe_read_parquet(RESULTS_DIR / "trades.parquet")


@lru_cache(maxsize=8)
def get_concept_rankings(holding_period: int | None = None) -> pd.DataFrame:
    df = _safe_read_csv(RESULTS_DIR / "concept_rankings.csv")
    if holding_period is not None and "holding_period" in df.columns:
        df = df[df["holding_period"] == holding_period]
    return df


@lru_cache(maxsize=1)
def get_stock_rankings() -> pd.DataFrame:
    return _safe_read_csv(RESULTS_DIR / "stock_rankings.csv")


@lru_cache(maxsize=1)
def get_combination_rankings() -> pd.DataFrame:
    return _safe_read_csv(RESULTS_DIR / "combination_rankings.csv")


@lru_cache(maxsize=1)
def get_regime_analysis() -> pd.DataFrame:
    return _safe_read_csv(RESULTS_DIR / "regime_analysis.csv")


@lru_cache(maxsize=1)
def get_sector_analysis() -> pd.DataFrame:
    return _safe_read_csv(RESULTS_DIR / "sector_analysis.csv")


@lru_cache(maxsize=500)
def get_price_history(ticker: str) -> pd.DataFrame:
    return _safe_read_parquet(DATA_CACHE_DIR / f"{ticker}.parquet")


def list_tickers() -> list[str]:
    events = get_master_events()
    if events.empty:
        return []
    return sorted(events["ticker"].unique().tolist())


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
