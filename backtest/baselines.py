"""Baseline / benchmark strategies (the extra requirement appended to the
brief): buy & hold, random entry, EMA(20/50) crossover, RSI(14) mean
reversion, 52-week breakout, and 126-day momentum turn. Used to answer
"do SMC/ICT signals add predictive power beyond simple technical
strategies?" -- the same event schema (ticker, date, signal, direction) as
the SMC/ICT event engine so they can be run through the identical backtest
engine and compared on equal footing.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

RNG_SEED = 42


def _stable_ticker_seed(ticker: str, seed: int) -> int:
    """Deterministic, collision-resistant per-ticker seed offset.

    Python's built-in `hash()` on strings is process-randomized (PYTHONHASHSEED)
    unless explicitly pinned, and was previously combined with a low-cardinality
    `% 10_000` bucket keyed on each ticker's *first cached bar date* -- since most
    tickers share the same first trading date and bar count, this collided for
    the large majority of the S&P 500 universe, so "random" entries were
    identical across hundreds of tickers (see audit finding, Phase 1 #1).
    SHA-256 of the ticker symbol itself is stable across processes/runs and,
    with a 2**32 range, has a negligible collision probability across 501
    tickers (~1 in 17,000 by the birthday bound).
    """
    digest = hashlib.sha256(f"{seed}:{ticker}".encode("utf-8")).digest()
    return seed + (int.from_bytes(digest[:8], "big") % (2**32))


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def ema_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    ema_fast, ema_slow = _ema(df["close"], fast), _ema(df["close"], slow)
    bull = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
    bear = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))
    return pd.DataFrame({"baseline_ema_cross_bullish": bull.fillna(False), "baseline_ema_cross_bearish": bear.fillna(False)})


def rsi_mean_reversion(df: pd.DataFrame, length: int = 14, oversold: float = 30, overbought: float = 70) -> pd.DataFrame:
    rsi = _rsi(df["close"], length)
    bull = (rsi < oversold) & (rsi.shift(1) >= oversold)
    bear = (rsi > overbought) & (rsi.shift(1) <= overbought)
    return pd.DataFrame({"baseline_rsi_reversion_bullish": bull.fillna(False), "baseline_rsi_reversion_bearish": bear.fillna(False)})


def breakout_52w(df: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    roll_high = df["high"].rolling(length).max()
    roll_low = df["low"].rolling(length).min()
    bull = df["close"] >= roll_high
    bear = df["close"] <= roll_low
    return pd.DataFrame({"baseline_52w_breakout_bullish": bull.fillna(False), "baseline_52w_breakout_bearish": bear.fillna(False)})


def momentum_turn(df: pd.DataFrame, length: int = 126) -> pd.DataFrame:
    mom = df["close"].pct_change(length)
    bull = (mom > 0) & (mom.shift(1) <= 0)
    bear = (mom < 0) & (mom.shift(1) >= 0)
    return pd.DataFrame({"baseline_momentum_bullish": bull.fillna(False), "baseline_momentum_bearish": bear.fillna(False)})


def random_entry(df: pd.DataFrame, n_signals: int, ticker: str, seed: int = RNG_SEED) -> pd.DataFrame:
    """Random long entries, same count as a comparison signal, for a fair
    "is this better than chance at this frequency" baseline.

    Seeded deterministically per-ticker via `_stable_ticker_seed` so each
    ticker draws its own independent set of random dates (see that function's
    docstring for why the previous date-hash-based seed collided).
    """
    rng = np.random.default_rng(_stable_ticker_seed(ticker, seed))
    n = len(df)
    if n_signals <= 0 or n == 0:
        return pd.DataFrame({"baseline_random_bullish": pd.Series(False, index=df.index)})
    idx = rng.choice(n, size=min(n_signals, n), replace=False)
    mask = np.zeros(n, dtype=bool)
    mask[idx] = True
    return pd.DataFrame({"baseline_random_bullish": mask}, index=df.index)


def buy_and_hold_return(df: pd.DataFrame) -> dict:
    """Whole-period buy & hold summary (not an event-based signal)."""
    if len(df) < 2:
        return {}
    total_return = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else np.nan
    daily_ret = df["close"].pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else np.nan
    cum = (1 + daily_ret).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    return {"total_return": total_return, "cagr": cagr, "sharpe": sharpe, "max_drawdown": max_dd}


def detect_all_baselines(df: pd.DataFrame, ticker: str, n_random_signals: int = 50) -> pd.DataFrame:
    parts = [
        ema_crossover(df),
        rsi_mean_reversion(df),
        breakout_52w(df),
        momentum_turn(df),
        random_entry(df, n_random_signals, ticker=ticker),
    ]
    return pd.concat(parts, axis=1)
