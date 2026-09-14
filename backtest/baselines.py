"""Baseline / benchmark strategies (the extra requirement appended to the
brief): buy & hold, random entry, EMA(20/50) crossover, RSI(14) mean
reversion, 52-week breakout, and 126-day momentum turn. Used to answer
"do SMC/ICT signals add predictive power beyond simple technical
strategies?" -- the same event schema (ticker, date, signal, direction) as
the SMC/ICT event engine so they can be run through the identical backtest
engine and compared on equal footing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.rng import get_rng

RNG_SEED = 42
# Random entries drawn per ticker. The original value (50) was far too sparse
# to be a stable comparator: a 50-draw per-ticker baseline has a standard error
# roughly 40x wider than the concepts it was benchmarked against, so the Welch
# test was dominated by baseline noise. 500 keeps the per-ticker baseline
# meaningful while staying cheap (500 x 498 tickers = 249k baseline trades).
DEFAULT_RANDOM_ENTRIES_PER_TICKER = 500


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
    at_high = df["close"] >= roll_high
    at_low = df["close"] <= roll_low
    # Fire on the *transition* into the breakout state, not on every bar the
    # state persists. As a level test this produced long runs of consecutive
    # "signals" during trends, which inflated the trade count and made the
    # baseline a trend-following strategy rather than a breakout event.
    bull = at_high & ~at_high.shift(1, fill_value=False)
    bear = at_low & ~at_low.shift(1, fill_value=False)
    return pd.DataFrame({"baseline_52w_breakout_bullish": bull.fillna(False), "baseline_52w_breakout_bearish": bear.fillna(False)})


def momentum_turn(df: pd.DataFrame, length: int = 126) -> pd.DataFrame:
    mom = df["close"].pct_change(length)
    bull = (mom > 0) & (mom.shift(1) <= 0)
    bear = (mom < 0) & (mom.shift(1) >= 0)
    return pd.DataFrame({"baseline_momentum_bullish": bull.fillna(False), "baseline_momentum_bearish": bear.fillna(False)})


def random_entry(
    df: pd.DataFrame,
    n_signals: int = DEFAULT_RANDOM_ENTRIES_PER_TICKER,
    seed: int = RNG_SEED,
    ticker: str | None = None,
) -> pd.DataFrame:
    """Random long entries on this ticker -- the "beats chance" comparator.

    Reproducibility fix
    -------------------
    The previous implementation seeded from ``abs(hash(tuple(...)))`` over the
    first index value rendered as a string. Python salts ``str`` hashing per
    process (PYTHONHASHSEED), so every run drew a *different* baseline and the
    published ``significant_vs_baseline`` counts could not be reproduced --
    verified by running the old function in three separate interpreters and
    getting three disjoint entry sets. Seeding now goes through
    ``utils.rng.derive_seed`` (BLAKE2b), which is stable across processes,
    machines and Python versions.

    Entries are drawn without replacement from ALL bars. An entry too close to
    the end of the series for a given horizon is dropped by the backtest at
    that horizon -- exactly as a concept event near the end is -- so baseline
    and concepts are truncated identically. (An earlier version of this
    docstring claimed the draw was restricted to bars with a forward bar; the
    code never did that.)
    """
    n = len(df)
    if n_signals <= 0 or n == 0:
        return pd.DataFrame({"baseline_random_bullish": pd.Series(False, index=df.index)})

    label = ticker if ticker is not None else str(df.index[0])
    rng = get_rng(f"random_entry:{label}", master_seed=seed)

    mask = np.zeros(n, dtype=bool)
    idx = rng.choice(n, size=min(n_signals, n), replace=False)
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


def detect_all_baselines(
    df: pd.DataFrame,
    n_random_signals: int = DEFAULT_RANDOM_ENTRIES_PER_TICKER,
    ticker: str | None = None,
) -> pd.DataFrame:
    """Run every benchmark strategy and return one wide boolean frame."""
    parts = [
        ema_crossover(df),
        rsi_mean_reversion(df),
        breakout_52w(df),
        momentum_turn(df),
        random_entry(df, n_random_signals, ticker=ticker),
    ]
    return pd.concat(parts, axis=1)
