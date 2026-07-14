"""Performance metrics computed on a set of trade forward returns (Task 7)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_returns(returns: pd.Series, holding_period: int, trading_days_per_year: int = 252) -> dict:
    """Compute the full Task 7 metric set for one signal/holding-period bucket."""
    r = returns.dropna()
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
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf if gross_profit > 0 else np.nan

    periods_per_year = trading_days_per_year / holding_period
    sharpe = (avg_return / std_return) * np.sqrt(periods_per_year) if std_return and std_return > 0 else np.nan

    downside = r[r < 0]
    downside_std = downside.std(ddof=1) if len(downside) > 1 else np.nan
    sortino = (avg_return / downside_std) * np.sqrt(periods_per_year) if downside_std and downside_std > 0 else np.nan

    expectancy = win_rate * wins.mean() if len(wins) else 0
    expectancy += (1 - win_rate) * losses.mean() if len(losses) else 0

    cumulative = (1 + r).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_drawdown = drawdown.min()
    avg_drawdown = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0.0

    cagr = cumulative.iloc[-1] ** (periods_per_year / n) - 1 if n > 0 and cumulative.iloc[-1] > 0 else np.nan

    return {
        "n_trades": n,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "median_return": median_return,
        "std_return": std_return,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "sortino": sortino,
        "expectancy": expectancy,
        "max_drawdown": max_drawdown,
        "avg_drawdown": avg_drawdown,
        "cagr_annualized": cagr,
        "reward_risk_ratio": (wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan,
    }


def mfe_mae_summary(mfe: pd.Series, mae: pd.Series) -> dict:
    return {
        "avg_mfe": mfe.mean(),
        "avg_mae": mae.mean(),
        "median_mfe": mfe.median(),
        "median_mae": mae.median(),
    }
