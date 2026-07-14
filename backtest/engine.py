"""Backtesting engine (Task 7): forward returns for every detected event at
every holding period, with MAE/MFE, and no look-ahead by construction (each
trade's entry uses only the signal bar's own close; every exit/extreme value
comes strictly from bars *after* the entry bar).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import DATA_CACHE_DIR, HOLDING_PERIODS, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("backtest.engine")


def _load_price_cache(cache_dir: Path = DATA_CACHE_DIR) -> dict[str, pd.DataFrame]:
    prices = {}
    for f in Path(cache_dir).glob("*.parquet"):
        df = pd.read_parquet(f).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        prices[f.stem] = df.reset_index()
    return prices


def _compute_trades_for_ticker(
    ticker: str, price_df: pd.DataFrame, events: pd.DataFrame, holding_periods: list[int]
) -> pd.DataFrame:
    """price_df: reset-index frame with a 'date' column (positional lookup).
    events: subset of the master event table for this ticker.
    """
    date_to_pos = pd.Series(price_df.index, index=price_df["date"])
    close = price_df["close"].to_numpy()
    high = price_df["high"].to_numpy()
    low = price_df["low"].to_numpy()
    n = len(price_df)

    rows = []
    for row in events.itertuples(index=False):
        pos = date_to_pos.get(row.date)
        if pos is None:
            continue
        entry_price = close[pos]
        direction = row.direction if row.direction != 0 else 1
        for h in holding_periods:
            exit_pos = pos + h
            if exit_pos >= n:
                continue
            exit_price = close[exit_pos]
            fwd_return = direction * (exit_price / entry_price - 1)

            window_high = high[pos + 1 : exit_pos + 1]
            window_low = low[pos + 1 : exit_pos + 1]
            if len(window_high) == 0:
                mfe = mae = np.nan
            elif direction == 1:
                mfe = (window_high.max() / entry_price) - 1
                mae = (window_low.min() / entry_price) - 1
            else:
                mfe = 1 - (window_low.min() / entry_price)
                mae = 1 - (window_high.max() / entry_price)

            rows.append(
                (ticker, row.date, row.signal, direction, holding_periods and h,
                 entry_price, exit_price, fwd_return, mfe, mae)
            )

    return pd.DataFrame(
        rows,
        columns=["ticker", "date", "signal", "direction", "holding_period",
                 "entry_price", "exit_price", "fwd_return", "mfe", "mae"],
    )


def run_backtest(
    events: pd.DataFrame | None = None,
    holding_periods: list[int] = HOLDING_PERIODS,
) -> pd.DataFrame:
    if events is None:
        events = pd.read_parquet(RESULTS_DIR / "master_events.parquet")

    log.info("Loading price cache for backtest join")
    prices = _load_price_cache()

    all_trades = []
    tickers = events["ticker"].unique()
    for i, ticker in enumerate(tickers, 1):
        if ticker not in prices:
            continue
        ticker_events = events[events["ticker"] == ticker]
        trades = _compute_trades_for_ticker(ticker, prices[ticker], ticker_events, holding_periods)
        all_trades.append(trades)
        if i % 50 == 0 or i == len(tickers):
            log.info("Backtested %d/%d tickers", i, len(tickers))

    result = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    log.info("Backtest complete: %d trades", len(result))
    return result
