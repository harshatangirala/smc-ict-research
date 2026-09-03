"""Performance metrics computed on a set of trade forward returns.

Interpretation caveat that applies to every path-dependent metric here
---------------------------------------------------------------------
These trades are *overlapping and cross-sectional*: a single signal can be
open on hundreds of tickers at once, and consecutive entries share most of
their holding window. The sequence of trade returns is therefore not an
account equity curve, and ``max_drawdown``, ``calmar`` and ``cagr_annualized``
are aggregate descriptive statistics of that sequence, not results a trader
would have experienced. ``sharpe`` and ``sortino`` are annualised as if the
trades were independent and non-overlapping, which they are not -- they are
comparable *across signals in this study* but should not be read as portfolio
Sharpe ratios. Inference is done in ``analytics/statistics.py``, which models
the overlap explicitly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as _stats


def summarize_returns(
    returns: pd.Series, holding_period: int, trading_days_per_year: int = 252
) -> dict:
    """Full metric set for one signal/holding-period bucket."""
    r = pd.Series(returns).dropna()
    n = len(r)
    if n == 0:
        return {"n_trades": 0}

    wins = r[r > 0]
    losses = r[r < 0]
    win_rate = len(wins) / n
    avg_return = r.mean()
    median_return = r.median()
    std_return = r.std(ddof=1) if n > 1 else np.nan

    gross_profit = wins.sum()
    gross_loss = -losses.sum()
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0
        else np.inf if gross_profit > 0 else np.nan
    )

    periods_per_year = trading_days_per_year / holding_period
    sharpe = (
        (avg_return / std_return) * np.sqrt(periods_per_year)
        if std_return and std_return > 0 else np.nan
    )

    downside = r[r < 0]
    downside_std = downside.std(ddof=1) if len(downside) > 1 else np.nan
    sortino = (
        (avg_return / downside_std) * np.sqrt(periods_per_year)
        if downside_std and downside_std > 0 else np.nan
    )

    # Expectancy: probability-weighted average outcome per trade. Weights use
    # len(wins)/n and len(losses)/n rather than win_rate and 1 - win_rate, so
    # exactly-zero returns are not silently counted as losses.
    p_win = len(wins) / n
    p_loss = len(losses) / n
    expectancy = (p_win * wins.mean() if len(wins) else 0.0) + (
        p_loss * losses.mean() if len(losses) else 0.0
    )

    # Compounded in log space: naively compounding millions of overlapping,
    # cross-ticker returns overflows float64. See the module caveat -- this is
    # a descriptive aggregate, not a real equity curve.
    r_clipped = r.clip(lower=-0.999999)
    log_cum = np.log1p(r_clipped).cumsum().to_numpy()
    running_max_log = np.maximum.accumulate(log_cum)
    drawdown = np.expm1(log_cum - running_max_log)
    max_drawdown = float(drawdown.min())
    avg_drawdown = float(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0.0

    with np.errstate(over="ignore", invalid="ignore"):
        cagr = np.expm1(log_cum[-1] * (periods_per_year / n)) if n > 0 else np.nan
    if not np.isfinite(cagr):
        cagr = np.nan

    calmar = (
        cagr / abs(max_drawdown)
        if np.isfinite(cagr) and max_drawdown < 0 else np.nan
    )

    return {
        "n_trades": n,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "median_return": median_return,
        "std_return": std_return,
        "skewness": float(_stats.skew(r, bias=False)) if n > 2 else np.nan,
        "kurtosis": float(_stats.kurtosis(r, fisher=True, bias=False)) if n > 3 else np.nan,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "sortino": sortino,
        "expectancy": expectancy,
        "max_drawdown": max_drawdown,
        "avg_drawdown": avg_drawdown,
        "calmar": calmar,
        "cagr_annualized": cagr,
        "reward_risk_ratio": (
            (wins.mean() / abs(losses.mean()))
            if len(wins) and len(losses) and losses.mean() != 0 else np.nan
        ),
    }


def mfe_mae_summary(mfe: pd.Series, mae: pd.Series) -> dict:
    """Distribution summary of maximum favourable / adverse excursion."""
    mfe = pd.Series(mfe).dropna()
    mae = pd.Series(mae).dropna()
    out = {
        "avg_mfe": mfe.mean() if len(mfe) else np.nan,
        "avg_mae": mae.mean() if len(mae) else np.nan,
        "median_mfe": mfe.median() if len(mfe) else np.nan,
        "median_mae": mae.median() if len(mae) else np.nan,
    }
    if len(mfe):
        out["p90_mfe"] = float(mfe.quantile(0.90))
    if len(mae):
        out["p10_mae"] = float(mae.quantile(0.10))
    if len(mfe) and len(mae):
        denom = mae.abs().mean()
        out["mfe_mae_ratio"] = float(mfe.mean() / denom) if denom > 0 else np.nan
    return out
