"""Market data ingestion: yfinance download, local parquet cache, retries,
parallel downloading, and ticker-symbol normalization (Task 4).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from utils.config import (
    DATA_CACHE_DIR,
    DATA_END,
    DATA_START,
    SP500_CONSTITUENTS_CSV,
    TICKER_SYMBOL_OVERRIDES,
)
from utils.logging_config import get_logger

log = get_logger("data_loader")

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def normalize_ticker(raw_ticker: str) -> str:
    """Convert constituents-list tickers to yfinance-compatible symbols.

    Yahoo encodes share-class separators as '-' where the index constituent
    list uses '.' (BRK.B -> BRK-B, BF.B -> BF-B). The explicit override table
    is consulted first; any *other* dotted symbol falls through to the general
    '.' -> '-' rule rather than being silently passed through unchanged and
    failing to download. The original code only handled the two hard-coded
    cases, so a future constituent-list refresh introducing a new dotted
    ticker would have dropped it with no error.
    """
    if raw_ticker in TICKER_SYMBOL_OVERRIDES:
        return TICKER_SYMBOL_OVERRIDES[raw_ticker]
    return raw_ticker.replace(".", "-")


def load_constituents() -> pd.DataFrame:
    """Load the S&P 500 constituents list with normalized yfinance symbols."""
    df = pd.read_csv(SP500_CONSTITUENTS_CSV)
    df["Weight"] = df["Weight"].str.rstrip("%").astype(float)
    df["YFSymbol"] = df["Symbol"].apply(normalize_ticker)
    return df


def _cache_path(ticker: str) -> "Path":
    from pathlib import Path

    safe = ticker.replace("/", "_")
    return DATA_CACHE_DIR / f"{safe}.parquet"


def _download_one(ticker: str, start: str, end: str, retries: int = 3) -> pd.DataFrame | None:
    """Download one ticker with retries, or None if it is unavailable.

    `yfinance` is imported here rather than at module scope so that the pure
    helpers in this module -- `normalize_ticker`, `load_constituents` -- work
    without it. CI installs a lean dependency set and runs the pipeline from a
    committed sample cache, so nothing there needs a network client; a
    module-level import made `pytest` fail on a string-normalisation test.
    """
    import yfinance as yf

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if df is None or df.empty:
                log.warning("No data returned for %s (attempt %d/%d)", ticker, attempt, retries)
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.lower)
            df = df[[c for c in REQUIRED_COLUMNS if c in df.columns]]
            df.index.name = "date"
            return df
        except Exception as exc:  # noqa: BLE001 - broad on purpose, this is a network call
            last_err = exc
            log.warning("Download error for %s (attempt %d/%d): %s", ticker, attempt, retries, exc)
            time.sleep(1.5 * attempt)
    log.error("Giving up on %s after %d attempts: %s", ticker, retries, last_err)
    return None


def get_prices(
    ticker: str,
    start: str = DATA_START,
    end: str = DATA_END,
    force_refresh: bool = False,
) -> pd.DataFrame | None:
    """Return cached OHLCV for `ticker`, downloading only if not cached."""
    path = _cache_path(ticker)
    if path.exists() and not force_refresh:
        try:
            return pd.read_parquet(path)
        except Exception:  # noqa: BLE001 - corrupted cache, refetch
            log.warning("Corrupt cache for %s, refetching", ticker)

    df = _download_one(ticker, start, end)
    if df is not None and not df.empty:
        df.to_parquet(path)
    return df


def download_universe(
    tickers: list[str],
    start: str = DATA_START,
    end: str = DATA_END,
    max_workers: int = 8,
    force_refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Download (or load from cache) the full ticker universe in parallel."""
    results: dict[str, pd.DataFrame] = {}
    to_fetch = []
    for t in tickers:
        path = _cache_path(t)
        if path.exists() and not force_refresh:
            try:
                results[t] = pd.read_parquet(path)
                continue
            except Exception:  # noqa: BLE001
                pass
        to_fetch.append(t)

    log.info(
        "Universe: %d tickers total, %d already cached, %d to download",
        len(tickers),
        len(tickers) - len(to_fetch),
        len(to_fetch),
    )

    if to_fetch:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_download_one, t, start, end): t for t in to_fetch
            }
            done = 0
            for fut in as_completed(futures):
                t = futures[fut]
                done += 1
                try:
                    df = fut.result()
                except Exception as exc:  # noqa: BLE001
                    log.error("Unhandled error downloading %s: %s", t, exc)
                    df = None
                if df is not None and not df.empty:
                    df.to_parquet(_cache_path(t))
                    results[t] = df
                if done % 25 == 0 or done == len(to_fetch):
                    log.info("Downloaded %d/%d", done, len(to_fetch))

    return results
