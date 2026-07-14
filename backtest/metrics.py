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

    # NOTE: for signals with very large trade counts (some ICT signals have
    # 1-2M+ occurrences across the whole universe), naively compounding every
    # trade's return sequentially -- as if it were one continuous account --
    # both overflows float64 (millions of compounded, overlapping,
    # cross-ticker returns is not a real equity curve) and isn't a
    # statistically meaningful "path" to begin with, since these trades
    # overlap in time across hundreds of different tickers. We compute it in
    # log-space to stay numerically stable, and treat max_drawdown/cagr for
    # very high-n signals as an illustrative aggregate rather than a literal
    # single-account equity curve (documented in README limitations).
    r_clipped = r.clip(lower=-0.999999)
    log_cum = np.log1p(r_clipped).cumsum().to_numpy()
    running_max_log = np.maximum.accumulate(log_cum)
    drawdown = np.expm1(log_cum - running_max_log)
    max_drawdown = float(drawdown.min())
    avg_drawdown = float(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0.0

    with np.errstate(over="ignore"):
        cagr = np.expm1(log_cum[-1] * (periods_per_year / n)) if n > 0 else np.nan
    if not np.isfinite(cagr):
        cagr = np.nan

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
