"""Parameter sensitivity analysis.

Every SMC/ICT detector carries free parameters -- swing lookbacks, ATR
lengths, body-size thresholds -- that were inherited from the Pine sources'
`input.*` defaults and then never varied. A result that holds only at those
exact defaults is a coincidence, not an edge, and the reader has no way to
tell the two apart from a single-configuration study.

This module re-runs detection and backtesting over a parameter grid on a
ticker subsample and reports how the headline statistic moves. Two sweeps:

``grid_sweep``
    Full factorial over an explicit grid. Interpretable; use for 1-2
    parameters at a time.
``random_sweep``
    Latin-hypercube-style random draws over the allowed ranges. Covers
    interactions the grid misses without a combinatorial blow-up.

Both report ``excess_return_vs_matched_random`` -- the same statistic the
headline tables use -- so a heatmap cell is directly comparable to the
published number. Both run on a *subsample* of tickers by default: the point
is the shape of the response surface, not a second full-universe result.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from analytics.statistics import build_return_pools, matched_randomization_test
from backtest.engine import _compute_trades_for_ticker
from utils.config import ICT, PRIMARY_HOLDING_PERIOD, RESULTS_DIR, SMC
from utils.logging_config import get_logger
from utils.prices import load_price_cache
from utils.rng import get_rng

log = get_logger("analytics.sensitivity")

#: Parameter -> (dataclass name, allowed range) for the sweeps below.
SWEEPABLE = {
    "ict.ob_swing_len": ("ICT", (5, 25)),
    "ict.mss_pivot_len": ("ICT", (3, 10)),
    "ict.displacement_perc_body": ("ICT", (0.10, 0.60)),
    "ict.sweep_penetration_atr": ("ICT", (0.05, 1.00)),
    "ict.sweep_confirm_bars": ("ICT", (1, 10)),
    "ict.sweep_reclaim_frac": ("ICT", (0.0, 1.0)),
    "ict.gap_min_atr": ("ICT", (0.02, 0.60)),
    "smc.swing_len": ("SMC", (10, 80)),
    "smc.internal_len": ("SMC", (3, 15)),
    "smc.equal_hl_threshold": ("SMC", (0.02, 0.40)),
}


def _detect_with_params(
    prices: dict[str, pd.DataFrame], ict_over: dict, smc_over: dict
) -> pd.DataFrame:
    """Run detection across `prices` with overridden parameters.

    The frozen ``ICT`` / ``SMC`` dataclasses are swapped on the detector module
    objects and restored afterwards. This only works because the detectors
    resolve their parameters from those objects *inside the function body*. When
    they were bound as default arguments -- ``def detect(df, length=ICT.x)`` --
    Python froze the value at import and this swap did nothing: the first
    version of this sweep returned byte-identical results at all 16 grid points.
    ``tests/test_pipeline_integrity.py::TestParametersAreLateBound`` guards it.
    """
    import signals.ict_signals as ict_mod
    import signals.smc_signals as smc_mod
    from signals.event_engine import detect_ticker, melt_events

    old_ict, old_smc = ict_mod.ICT, smc_mod.SMC
    try:
        ict_mod.ICT = replace(old_ict, **ict_over) if ict_over else old_ict
        smc_mod.SMC = replace(old_smc, **smc_over) if smc_over else old_smc
        frames = []
        for ticker, df in prices.items():
            try:
                frames.append(melt_events(detect_ticker(ticker, df)))
            except Exception as exc:  # noqa: BLE001
                log.warning("Sweep detection failed for %s: %s", ticker, exc)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    finally:
        ict_mod.ICT, smc_mod.SMC = old_ict, old_smc


def _evaluate(
    events: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    pools: dict,
    holding_period: int,
    signals: list[str] | None,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    pos_prices = {t: df.reset_index() for t, df in prices.items()}
    trades = []
    for ticker, grp in events.groupby("ticker"):
        if ticker in pos_prices:
            trades.append(
                _compute_trades_for_ticker(ticker, pos_prices[ticker], grp, [holding_period])
            )
    if not trades:
        return pd.DataFrame()
    td = pd.concat(trades, ignore_index=True)

    rows = []
    for signal, grp in td.groupby("signal"):
        if signals and signal not in signals:
            continue
        r = grp["fwd_return"].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        if len(r) < 10:
            continue
        mr = matched_randomization_test(
            grp.groupby("ticker").size().to_dict(),
            float(r.mean()),
            int(grp["direction"].iloc[0]),
            pools,
            holding_period,
        )
        rows.append(
            {
                "signal": signal,
                "n_trades": len(r),
                "mean_return": float(r.mean()),
                "excess_return_vs_matched_random": mr["excess_return"],
                "p_value_vs_matched_random": mr["p_value"],
            }
        )
    return pd.DataFrame(rows)


def _split_overrides(params: dict) -> tuple[dict, dict]:
    ict_over, smc_over = {}, {}
    for key, value in params.items():
        family, _, name = key.partition(".")
        if family == "ict":
            ict_over[name] = value
        elif family == "smc":
            smc_over[name] = value
    return ict_over, smc_over


def grid_sweep(
    grid: dict[str, list],
    tickers: list[str] | None = None,
    n_tickers: int = 40,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
    signals: list[str] | None = None,
) -> pd.DataFrame:
    """Full factorial sweep. `grid` maps 'ict.param'/'smc.param' -> values."""
    prices = load_price_cache(tickers=tickers)
    if tickers is None and len(prices) > n_tickers:
        rng = get_rng("sensitivity_subsample")
        keep = rng.choice(sorted(prices), size=n_tickers, replace=False)
        prices = {t: prices[t] for t in keep}
    pools = build_return_pools(prices, [holding_period])

    keys = list(grid)
    combos = list(itertools.product(*(grid[k] for k in keys)))
    log.info("Grid sweep: %d combinations x %d tickers", len(combos), len(prices))

    out = []
    for i, values in enumerate(combos, 1):
        params = dict(zip(keys, values))
        ict_over, smc_over = _split_overrides(params)
        events = _detect_with_params(prices, ict_over, smc_over)
        res = _evaluate(events, prices, pools, holding_period, signals)
        for k, v in params.items():
            res[k] = v
        out.append(res)
        log.info("  combination %d/%d done (%s)", i, len(combos), params)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def random_sweep(
    params: list[str],
    n_draws: int = 24,
    tickers: list[str] | None = None,
    n_tickers: int = 40,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
    signals: list[str] | None = None,
    seed_label: str = "sensitivity_random",
) -> pd.DataFrame:
    """Randomised sweep over the allowed ranges in ``SWEEPABLE``."""
    rng = get_rng(seed_label)
    prices = load_price_cache(tickers=tickers)
    if tickers is None and len(prices) > n_tickers:
        keep = get_rng("sensitivity_subsample").choice(
            sorted(prices), size=n_tickers, replace=False
        )
        prices = {t: prices[t] for t in keep}
    pools = build_return_pools(prices, [holding_period])

    out = []
    for draw in range(1, n_draws + 1):
        chosen = {}
        for key in params:
            if key not in SWEEPABLE:
                continue
            lo, hi = SWEEPABLE[key][1]
            chosen[key] = (
                int(rng.integers(lo, hi + 1))
                if isinstance(lo, int) and isinstance(hi, int)
                else float(rng.uniform(lo, hi))
            )
        ict_over, smc_over = _split_overrides(chosen)
        events = _detect_with_params(prices, ict_over, smc_over)
        res = _evaluate(events, prices, pools, holding_period, signals)
        for k, v in chosen.items():
            res[k] = v
        res["draw"] = draw
        out.append(res)
        log.info("  random draw %d/%d done", draw, n_draws)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def stability_summary(sweep: pd.DataFrame) -> pd.DataFrame:
    """How much does each signal's edge move across the swept configurations?

    ``sign_consistency`` is the fraction of configurations in which the excess
    return kept its majority sign. A concept whose edge flips sign as a lookback
    moves by a few bars has not been shown to have an edge at all.

    ``responds_to_sweep`` matters for reading the rest of the row. A parameter
    that does not enter a detector cannot move it, so ``std_excess == 0`` there
    means "this sweep did not test this concept", NOT "this concept is robust".
    Sweeping ``ict.ob_swing_len`` tells you nothing about ``ict_sweep_*``, which
    reads ``ict.sweep_swing_len``. Read a zero-variance row as untested unless
    ``responds_to_sweep`` is True.
    """
    if sweep.empty:
        return pd.DataFrame()
    g = sweep.groupby("signal")["excess_return_vs_matched_random"]
    summary = g.agg(
        n_configs="count", mean_excess="mean", median_excess="median",
        std_excess="std", min_excess="min", max_excess="max",
    ).reset_index()
    summary["std_excess"] = summary["std_excess"].fillna(0.0)
    summary["sign_consistency"] = (
        sweep.assign(pos=sweep["excess_return_vs_matched_random"] > 0)
        .groupby("signal")["pos"]
        .apply(lambda s: max(s.mean(), 1 - s.mean()))
        .values
    )
    summary["coefficient_of_variation"] = (
        summary["std_excess"] / summary["mean_excess"].abs()
    ).replace([np.inf, -np.inf], np.nan)
    summary["responds_to_sweep"] = summary["std_excess"] > 0
    summary["swept_range_bps"] = (summary["max_excess"] - summary["min_excess"]) * 10_000
    return summary.sort_values("mean_excess", ascending=False).reset_index(drop=True)
