"""Master statistics table: every (signal, holding-period) hypothesis in one
place, with Benjamini-Hochberg control applied across the whole family.

Why a single table
------------------
The original pipeline ran FDR separately inside each ranking module -- once
over concepts, once over combinations, once over stocks -- at a single holding
period, and reported results for all eight horizons elsewhere without
correction. The family of hypotheses the study actually tests is
``signals x horizons`` (plus combinations, stocks, sectors and regimes), so
correcting within slices understates the multiplicity. This module assembles
the whole family first and corrects once, which is what
``results/statistics_master.csv`` records.

Three p-values are reported per bucket, and they answer different questions:

``p_value_vs_zero``
    Is the mean forward return different from zero? Weak over 2010-2026:
    a long-biased signal clears it on market drift alone.
``p_value_vs_matched_random``
    Is it better than entering the *same tickers* the *same number of times*
    on random dates? This is the primary test -- see
    ``analytics.statistics.matched_randomization_test``.
``p_value_vs_baseline_welch``
    One-sided Welch against the pooled random-entry baseline. Retained for
    continuity with the original results; it does not control ticker mix, so
    ``p_value_vs_matched_random`` supersedes it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.statistics import (
    apply_fdr_correction,
    build_return_pools,
    calendar_time_mean_test,
    evaluate_signal,
    significance_label,
)
from backtest.engine import _load_price_cache
from backtest.metrics import mfe_mae_summary, summarize_returns
from utils.config import (
    BOOTSTRAP_ITERATIONS,
    FDR_ALPHA,
    HOLDING_PERIODS,
    MIN_SAMPLE_SIZE,
    RESULTS_DIR,
)
from utils.logging_config import get_logger

log = get_logger("analytics.master_stats")


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def build_statistics_master(
    trades: pd.DataFrame | None = None,
    holding_periods: list[int] | None = None,
    n_boot: int = BOOTSTRAP_ITERATIONS,
    prices: dict | None = None,
) -> pd.DataFrame:
    """One row per (signal, holding_period) with the full statistical workup."""
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    holding_periods = holding_periods or HOLDING_PERIODS
    baseline_trades = _load_baseline_trades()

    if prices is None:
        log.info("Loading price cache to build matched-random null pools")
        prices = _load_price_cache()
    pool_prices = {t: df.set_index("date") if "date" in df.columns else df
                   for t, df in prices.items()}
    pools = build_return_pools(pool_prices, holding_periods)
    log.info("Built %d (ticker, horizon) return pools", len(pools))

    rows = []
    signals = sorted(trades["signal"].unique())
    total = len(signals) * len(holding_periods)
    done = 0
    # Group once rather than re-scanning the full trade table per bucket.
    baseline_by_h = (
        {h: baseline_trades[baseline_trades["holding_period"] == h]
         for h in holding_periods}
        if baseline_trades is not None else {}
    )
    for h in holding_periods:
        h_trades = trades[trades["holding_period"] == h]
        groups = dict(tuple(h_trades.groupby("signal")))
        for signal in signals:
            grp = groups.get(signal)
            done += 1
            if grp is None or grp.empty:
                continue
            metrics = summarize_returns(grp["fwd_return"], h)
            metrics.update(mfe_mae_summary(grp["mfe"], grp["mae"]))
            stat = evaluate_signal(
                trades, signal, h, baseline_trades=baseline_by_h.get(h),
                pools=pools, n_boot=n_boot, subset=grp,
            )
            row = {**metrics, **stat}
            row["direction"] = int(grp["direction"].iloc[0])
            row["n_tickers"] = int(grp["ticker"].nunique())
            rows.append(row)
            if done % 40 == 0 or done == total:
                log.info("Statistics: %d/%d buckets", done, total)

    master = pd.DataFrame(rows)
    if master.empty:
        return master

    master = master.rename(
        columns={
            "p_value": "p_value_vs_zero",
            "p_value_iid": "p_value_vs_zero_iid",
        }
    )

    # --- BH-FDR across the entire family, per test type --------------------
    for src, dst in (
        ("p_value_vs_zero", "p_adj_vs_zero"),
        ("p_value_vs_matched_random", "p_adj_vs_matched_random"),
        ("p_value_vs_baseline_welch", "p_adj_vs_baseline_welch"),
    ):
        if src in master.columns:
            fdr = apply_fdr_correction(master[src], alpha=FDR_ALPHA)
            master[dst] = fdr["p_adjusted"]
            master[dst.replace("p_adj", "reject")] = fdr["reject_null"]

    master["low_sample_warning"] = master["n_trades"] < MIN_SAMPLE_SIZE

    # The headline flag. An edge must (a) beat composition-matched random
    # entry after FDR control, and (b) rest on enough trades to be meaningful.
    # The original flag was a two-sided test against a pooled baseline, so a
    # concept that significantly LOST to random entry set it to True.
    master["beats_matched_random"] = (
        master.get("reject_vs_matched_random", pd.Series(False, index=master.index))
        .fillna(False)
        .astype(bool)
        & (master["excess_return_vs_matched_random"].fillna(-np.inf) > 0)
        & ~master["low_sample_warning"]
    )
    master["significance_label"] = [
        significance_label(p, d)
        for p, d in zip(
            master.get("p_adj_vs_matched_random", pd.Series(np.nan, index=master.index)),
            master["effect_size_cohens_d"],
        )
    ]

    master = master.sort_values(
        ["holding_period", "excess_return_vs_matched_random"], ascending=[True, False]
    )
    return master.reset_index(drop=True)


def write_statistics_master(master: pd.DataFrame) -> "Path":  # noqa: F821
    path = RESULTS_DIR / "statistics_master.csv"
    master.to_csv(path, index=False)
    log.info("Wrote %s (%d rows)", path, len(master))
    return path
