"""Backtesting engine (Task 7): forward returns for every detected event at
every holding period, with MAE/MFE and no look-ahead by construction.

Timing contract (enforced by tests/test_no_lookahead.py)
-------------------------------------------------------
For an event on bar ``p`` and holding period ``h >= 1``:

===================  ============================  ====================
Quantity             Bars read                     Relative to entry
===================  ============================  ====================
entry_price          ``close[p]``                  bar 0 (the close of
                                                   the signal bar -- known
                                                   at decision time)
exit_price           ``close[p + h]``              strictly future
MFE / MAE            ``high/low[p+1 .. p+h]``      strictly future
===================  ============================  ====================

Nothing between ``p+1`` and ``p+h`` influences ``entry_price``, and no bar
beyond ``p+h`` is read at all. ``audit_positions()`` re-derives the exact
index positions each trade touches so a test can assert this mechanically
rather than by inspection.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import DATA_CACHE_DIR, HOLDING_PERIODS, RESULTS_DIR
from utils.prices import load_price_cache
from utils.logging_config import get_logger

log = get_logger("backtest.engine")

TRADE_COLUMNS = [
    "ticker", "date", "signal", "direction", "holding_period",
    "entry_price", "exit_price", "fwd_return", "mfe", "mae",
]


def _load_price_cache(cache_dir: Path = DATA_CACHE_DIR) -> dict[str, pd.DataFrame]:
    """Load every cached ticker as a positionally-indexed frame with a 'date' column."""
    return {t: df.reset_index() for t, df in load_price_cache(cache_dir).items()}


def audit_positions(pos: int, h: int, n: int) -> dict[str, list[int]]:
    """Return the exact index positions a trade at bar `pos` with horizon `h`
    reads, split by role. Used by the no-look-ahead test; kept beside the
    computation so the two cannot drift apart.
    """
    exit_pos = pos + h
    if exit_pos >= n:
        return {"entry": [], "exit": [], "excursion": []}
    return {
        "entry": [pos],
        "exit": [exit_pos],
        "excursion": list(range(pos + 1, exit_pos + 1)),
    }


def _compute_trades_for_ticker(
    ticker: str, price_df: pd.DataFrame, events: pd.DataFrame, holding_periods: list[int]
) -> pd.DataFrame:
    """Forward returns and excursions for one ticker's events.

    price_df: reset-index frame with a 'date' column (positional lookup).
    events:   subset of the master event table for this ticker.
    """
    date_to_pos = pd.Series(price_df.index, index=price_df["date"])
    date_to_pos = date_to_pos[~date_to_pos.index.duplicated(keep="first")]
    close = price_df["close"].to_numpy()
    high = price_df["high"].to_numpy()
    low = price_df["low"].to_numpy()
    n = len(price_df)

    rows = []
    for row in events.itertuples(index=False):
        pos = date_to_pos.get(row.date)
        if pos is None:
            continue
        pos = int(pos)
        entry_price = close[pos]
        if not np.isfinite(entry_price) or entry_price <= 0:
            continue
        # A registered signal always carries +1/-1; 0 would mean an
        # unregistered direction-less signal silently coerced long.
        direction = int(row.direction)
        if direction not in (1, -1):
            raise ValueError(
                f"{ticker} {row.signal} on {row.date}: direction={direction!r}. "
                "Every tradeable signal must declare +1 or -1 in EVENT_REGISTRY."
            )

        for h in holding_periods:
            exit_pos = pos + h
            if exit_pos >= n:
                continue
            exit_price = close[exit_pos]
            fwd_return = direction * (exit_price / entry_price - 1)

            # Strictly-future window: bars p+1 .. p+h inclusive.
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
                (ticker, row.date, row.signal, direction, h,
                 entry_price, exit_price, fwd_return, mfe, mae)
            )

    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


def run_backtest(
    events: pd.DataFrame | None = None,
    holding_periods: list[int] = HOLDING_PERIODS,
) -> pd.DataFrame:
    """Run the forward-return backtest over an event table."""
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

    result = (
        pd.concat(all_trades, ignore_index=True)
        if all_trades
        else pd.DataFrame(columns=TRADE_COLUMNS)
    )
    log.info("Backtest complete: %d trades", len(result))
    return result
