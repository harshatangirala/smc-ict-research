"""Transaction-cost-aware backtest variant.

The headline engine (``backtest/engine.py``) reports gross forward returns:
entry at the signal bar's close, exit at the close ``h`` bars later, no
frictions. That is the right quantity for asking "does this event carry
information", but it is not a tradeable result, and the original study
reported it as though it were.

This module applies an explicit round-trip cost to every trade::

    cost_bps = fixed_bps + spread_bps + slippage_bps
    net_return = gross_return - cost_bps / 10_000

where ``slippage_bps ~ Uniform(slippage_bps_low, slippage_bps_high)``. The draw
is keyed to the trade's identity -- (ticker, date, signal, holding period) --
so a given trade gets the same cost on every rerun and whatever order or
subset it arrives in. The first version drew by row position, so filtering
or re-sorting the input silently changed which trade paid which cost.

Cost is charged once per round trip and is direction-agnostic: crossing the
spread costs the same going long or short. Defaults (1 bp fixed + 5 bp spread
+ 5-20 bp slippage) are deliberately mid-range for large-cap US equities;
``sweep_cost_grid`` re-prices a result set across a range so the reader can
see where each claim breaks even rather than trusting one cost assumption.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.config import COSTS, CostParams
from utils.logging_config import get_logger
from utils.rng import get_rng

log = get_logger("backtest.engine_tc")


def per_trade_cost_bps(
    n_trades: int, costs: CostParams = COSTS, seed_label: str = "slippage"
) -> np.ndarray:
    """Round-trip cost in basis points for `n_trades` trades.

    Slippage is stochastic; the fixed and spread components are not.
    """
    rng = get_rng(seed_label)
    slippage = rng.uniform(costs.slippage_bps_low, costs.slippage_bps_high, size=n_trades)
    return costs.fixed_bps + costs.spread_bps + slippage


def _trade_uniforms(trades: pd.DataFrame, seed_label: str) -> np.ndarray:
    """One Uniform[0,1) per trade, a function of the trade's identity only."""
    from utils.rng import derive_seed

    key = [c for c in ("ticker", "date", "signal", "holding_period") if c in trades.columns]
    if not key:
        return get_rng(seed_label).uniform(size=len(trades))
    frame = trades[key].copy()
    # Identical keys are identical trades; the occurrence counter still gives
    # each duplicate its own draw.
    frame["_occ"] = frame.groupby(key, sort=False).cumcount()
    hash_key = f"{derive_seed(seed_label):016d}"[-16:]
    h = pd.util.hash_pandas_object(frame, index=False, hash_key=hash_key).to_numpy()
    return (h >> np.uint64(11)).astype(np.float64) / float(2**53)


def apply_costs(
    trades: pd.DataFrame, costs: CostParams = COSTS, seed_label: str = "slippage"
) -> pd.DataFrame:
    """Return `trades` with `cost_bps` and `net_return` columns added.

    The gross ``fwd_return`` column is preserved unchanged so gross and net
    results stay directly comparable in the same table.
    """
    if trades.empty:
        out = trades.copy()
        out["cost_bps"] = pd.Series(dtype=float)
        out["net_return"] = pd.Series(dtype=float)
        return out

    out = trades.copy()
    u = _trade_uniforms(out, seed_label)
    out["cost_bps"] = (
        costs.fixed_bps + costs.spread_bps + costs.slippage_bps_low
        + (costs.slippage_bps_high - costs.slippage_bps_low) * u
    )
    out["net_return"] = out["fwd_return"] - out["cost_bps"] / 10_000.0
    log.info(
        "Applied transaction costs to %d trades: mean %.2f bps (%.4f%% of notional)",
        len(out), out["cost_bps"].mean(), out["cost_bps"].mean() / 100,
    )
    return out


def sweep_cost_grid(
    trades: pd.DataFrame,
    signal_col: str = "signal",
    grid_bps: tuple[float, ...] = (0.0, 5.0, 10.0, 20.0, 40.0, 60.0),
) -> pd.DataFrame:
    """Mean net return per signal across a grid of flat round-trip costs.

    Answers the question a reader actually needs: *at what cost level does
    this edge disappear?* Reporting a single cost assumption invites the
    objection that it was chosen to preserve the result.
    """
    rows = []
    for cost in grid_bps:
        grouped = trades.groupby(signal_col)["fwd_return"].agg(["mean", "count"])
        for sig, r in grouped.iterrows():
            rows.append(
                {
                    "signal": sig,
                    "cost_bps": cost,
                    "n_trades": int(r["count"]),
                    "mean_net_return": r["mean"] - cost / 10_000.0,
                }
            )
    return pd.DataFrame(rows)


def breakeven_cost_bps(
    trades: pd.DataFrame,
    signal_col: str = "signal",
    excess_by_signal: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Round-trip cost at which a signal stops paying, on two different bars.

    ``breakeven_cost_bps`` is measured against the GROSS mean return -- the
    cost at which the strategy stops making money in absolute terms.

    ``breakeven_excess_cost_bps`` is measured against the signal's excess over
    the composition-matched random-entry null, and it is the number that
    actually matters. A concept can carry a gross mean of 80 bps and still be
    worthless, because random entry on the same tickers would have earned
    nearly all of it: the part attributable to the *signal* is the excess. If
    the excess is smaller than the cost of trading, the signal cannot pay for
    itself even though its gross break-even looks comfortable.
    """
    g = trades.groupby(signal_col)["fwd_return"].agg(["mean", "count"]).reset_index()
    g["breakeven_cost_bps"] = g["mean"] * 10_000.0
    g = g.rename(columns={signal_col: "signal", "mean": "gross_mean_return",
                          "count": "n_trades"})
    if excess_by_signal:
        g["excess_return_vs_matched_random"] = g["signal"].map(excess_by_signal)
        g["breakeven_excess_cost_bps"] = g["excess_return_vs_matched_random"] * 10_000.0
    return g.sort_values("breakeven_cost_bps", ascending=False).reset_index(drop=True)
