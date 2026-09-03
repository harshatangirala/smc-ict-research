"""Walk-forward, out-of-sample evaluation.

The original study reported one number per concept, computed over the whole
2010-2026 sample, and called it a result. Every concept was therefore selected
and evaluated on the same data. This module supplies the missing out-of-sample
half: rolling folds in which concepts are *ranked* on a training window and
then *evaluated* on the following, untouched window.

Design
------
Rolling windows over calendar time (defaults from ``utils/config.py``):

* train 3 years, test the next 1 year, step forward 1 year;
* selection uses training-window excess return over the composition-matched
  random null, with a minimum trade count -- never test-window information;
* a concept's test-window return is recorded whether or not it was selected,
  so selection skill can be separated from concept skill.

The headline output is the *hit rate* -- the share of folds in which the
concepts chosen on training data went on to beat their matched null out of
sample. A methodology with a real edge should clear 50% reliably; one that
does not is fitting noise, however impressive its full-sample statistics look.

Trades are assigned to a fold by ENTRY date. A trade entered near the end of a
test window can still be held past the window's edge; that is intended -- the
alternative (truncating the holding period) would silently change the horizon
being measured.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.statistics import build_return_pools, matched_randomization_test
from utils.config import (
    MIN_SAMPLE_SIZE,
    PRIMARY_HOLDING_PERIOD,
    RESULTS_DIR,
    WALK_FORWARD_STEP_YEARS,
    WALK_FORWARD_TEST_YEARS,
    WALK_FORWARD_TRAIN_YEARS,
)
from utils.logging_config import get_logger

log = get_logger("analytics.walkforward")


def make_folds(
    start: pd.Timestamp,
    end: pd.Timestamp,
    train_years: int = WALK_FORWARD_TRAIN_YEARS,
    test_years: int = WALK_FORWARD_TEST_YEARS,
    step_years: int = WALK_FORWARD_STEP_YEARS,
) -> list[dict]:
    """Rolling (train, test) date windows covering [start, end]."""
    folds = []
    train_start = pd.Timestamp(start)
    while True:
        train_end = train_start + pd.DateOffset(years=train_years)
        test_end = train_end + pd.DateOffset(years=test_years)
        if test_end > pd.Timestamp(end):
            break
        folds.append(
            {
                "fold": len(folds) + 1,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
            }
        )
        train_start = train_start + pd.DateOffset(years=step_years)
    return folds


def _window_stats(
    trades: pd.DataFrame, pools: dict, holding_period: int
) -> pd.DataFrame:
    """Per-signal mean return and matched-null excess inside one window."""
    rows = []
    for signal, grp in trades.groupby("signal"):
        r = grp["fwd_return"].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        if len(r) == 0:
            continue
        counts = grp.groupby("ticker").size().to_dict()
        direction = int(grp["direction"].iloc[0])
        mr = matched_randomization_test(
            counts, float(r.mean()), direction, pools, holding_period
        )
        rows.append(
            {
                "signal": signal,
                "n_trades": len(r),
                "mean_return": float(r.mean()),
                "matched_null_mean": mr["null_mean"],
                "excess_return": mr["excess_return"],
                "p_value": mr["p_value"],
            }
        )
    return pd.DataFrame(rows)


def walk_forward_analysis(
    trades: pd.DataFrame | None = None,
    prices: dict | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
    top_k: int = 5,
    min_trades: int = MIN_SAMPLE_SIZE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the walk-forward evaluation.

    Returns ``(per_fold_signal_table, fold_summary_table)``.
    """
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    if prices is None:
        from backtest.engine import _load_price_cache

        prices = {
            t: df.set_index("date") for t, df in _load_price_cache().items()
        }

    trades = trades[trades["holding_period"] == holding_period].copy()
    trades["date"] = pd.to_datetime(trades["date"])

    folds = make_folds(trades["date"].min(), trades["date"].max())
    log.info("Walk-forward: %d folds at h=%d", len(folds), holding_period)
    if not folds:
        return pd.DataFrame(), pd.DataFrame()

    detail_rows = []
    summary_rows = []
    for f in folds:
        tr = trades[(trades["date"] >= f["train_start"]) & (trades["date"] < f["train_end"])]
        te = trades[(trades["date"] >= f["test_start"]) & (trades["date"] < f["test_end"])]
        if tr.empty or te.empty:
            continue

        # Null pools are rebuilt from the prices inside each window, so the
        # train-window null never sees test-window prices.
        tr_prices = {
            t: df[(df.index >= f["train_start"]) & (df.index < f["train_end"])]
            for t, df in prices.items()
        }
        te_prices = {
            t: df[(df.index >= f["test_start"]) & (df.index < f["test_end"])]
            for t, df in prices.items()
        }
        tr_pools = build_return_pools(tr_prices, [holding_period])
        te_pools = build_return_pools(te_prices, [holding_period])

        tr_stats = _window_stats(tr, tr_pools, holding_period)
        te_stats = _window_stats(te, te_pools, holding_period)
        if tr_stats.empty or te_stats.empty:
            continue

        eligible = tr_stats[tr_stats["n_trades"] >= min_trades]
        selected = (
            eligible.nlargest(top_k, "excess_return")["signal"].tolist()
            if not eligible.empty else []
        )

        merged = tr_stats.merge(
            te_stats, on="signal", suffixes=("_train", "_test"), how="inner"
        )
        merged["fold"] = f["fold"]
        merged["train_start"] = f["train_start"]
        merged["test_start"] = f["test_start"]
        merged["selected"] = merged["signal"].isin(selected)
        detail_rows.append(merged)

        sel = merged[merged["selected"]]
        summary_rows.append(
            {
                "fold": f["fold"],
                "train_start": f["train_start"].date(),
                "train_end": f["train_end"].date(),
                "test_start": f["test_start"].date(),
                "test_end": f["test_end"].date(),
                "n_signals": len(merged),
                "n_selected": len(sel),
                "train_excess_selected": float(sel["excess_return_train"].mean())
                if len(sel) else np.nan,
                "test_excess_selected": float(sel["excess_return_test"].mean())
                if len(sel) else np.nan,
                "test_excess_all": float(merged["excess_return_test"].mean()),
                "hit_rate_selected": float((sel["excess_return_test"] > 0).mean())
                if len(sel) else np.nan,
                "rank_correlation": float(
                    merged["excess_return_train"].corr(
                        merged["excess_return_test"], method="spearman"
                    )
                ) if len(merged) > 2 else np.nan,
            }
        )

    detail = pd.concat(detail_rows, ignore_index=True) if detail_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        log.info(
            "Walk-forward complete: %d folds, mean OOS excess of selected = %.5f, "
            "mean hit rate = %.2f, mean train->test rank corr = %.3f",
            len(summary),
            summary["test_excess_selected"].mean(),
            summary["hit_rate_selected"].mean(),
            summary["rank_correlation"].mean(),
        )
    return detail, summary
