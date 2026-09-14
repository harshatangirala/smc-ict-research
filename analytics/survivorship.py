"""Survivorship-bias diagnostics and the membership-aware robustness test.

The problem, stated precisely
-----------------------------
The constituent list is a 2026 snapshot applied to 2010-2026. That biases the
study in two distinguishable ways, and only one of them can be repaired here:

**(a) Look-ahead membership -- repairable.** 237 of the 503 current constituents
joined the index *during* the sample. Trading them from 2010 uses knowledge that
they would later become large enough to be included. ``membership_aware_trades``
drops every trade dated before a ticker's index-entry date, which removes this
component exactly.

**(b) Absent removed members -- not repairable here.** At least 234 names (~47%
of the index) were constituents during 2010-2026 and have since been removed;
they are missing from the dataset entirely. Recovering them needs a
point-in-time constituent history, which no free source provides -- Wikipedia's
"changes" table is no longer published. ``survivorship_summary`` quantifies the
hole rather than gesturing at it.

Why the headline result is nonetheless robust to (b)
----------------------------------------------------
The study's claim is an *excess* over a composition-matched null drawn from the
same tickers. Survivor bias inflates the signal's return and the null's return
by the same amount, so it largely cancels in the difference. It would matter if
survivors responded to SMC/ICT signals differently from non-survivors -- a real
possibility, since delisted names are disproportionately distressed. That is
stated as a limitation, not dismissed.

``compare_membership_aware`` runs the headline test both ways so the reader sees
the magnitude rather than taking the argument on faith.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.statistics import (
    apply_fdr_correction,
    build_return_pools,
    matched_excess_calendar_test,
    matched_randomization_test,
)
from utils.config import FDR_ALPHA, MIN_SAMPLE_SIZE, PRIMARY_HOLDING_PERIOD, RESULTS_DIR
from utils.logging_config import get_logger
from utils.universe import (
    coverage_report,
    estimate_missing_members,
    membership_mask,
)

log = get_logger("analytics.survivorship")


def survivorship_summary(tickers: list[str] | None = None) -> pd.DataFrame:
    """One-row-per-metric table sizing the survivorship problem.

    Sized over the tickers actually analysed (the cached universe) by default,
    not the whole snapshot, which is a later vintage and differs from the
    study's list by a few index changes.
    """
    if tickers is None:
        from utils.config import DATA_CACHE_DIR

        tickers = sorted(p.stem for p in DATA_CACHE_DIR.glob("*.parquet"))
    est = estimate_missing_members(tickers=tickers or None)
    rows = [{"metric": k, "value": v} for k, v in est.items() if k != "note"]
    rows.append({"metric": "note", "value": est["note"]})
    return pd.DataFrame(rows)


def membership_aware_trades(
    trades: pd.DataFrame, unknown_policy: str = "keep"
) -> pd.DataFrame:
    """Trades restricted to dates on which the ticker was an index constituent."""
    mask = membership_mask(trades, unknown_policy=unknown_policy)
    kept = trades[mask]
    log.info(
        "Membership filter: kept %d of %d trades (%.1f%%)",
        len(kept), len(trades), 100 * len(kept) / max(len(trades), 1),
    )
    return kept


def _rank(trades: pd.DataFrame, pools: dict, holding_period: int) -> pd.DataFrame:
    """Per-signal excess over the matched null, with BH-FDR."""
    rows = []
    for signal, grp in trades.groupby("signal"):
        r = grp["fwd_return"].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        if len(r) == 0:
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
                "n_tickers": int(grp["ticker"].nunique()),
                "mean_return": float(r.mean()),
                "matched_null_mean": mr["null_mean"],
                "excess_return_vs_matched_random": mr["excess_return"],
                "p_value_vs_matched_random": matched_excess_calendar_test(grp, pools, holding_period, int(grp["direction"].iloc[0]))["p_value"],
                "p_value_vs_matched_random_srs": mr["p_value"],
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    fdr = apply_fdr_correction(out["p_value_vs_matched_random"], alpha=FDR_ALPHA)
    out["p_adj_vs_matched_random"] = fdr["p_adjusted"]
    out["reject_vs_matched_random"] = fdr["reject_null"]
    out["beats_matched_random"] = (
        out["reject_vs_matched_random"].fillna(False).astype(bool)
        & (out["excess_return_vs_matched_random"].fillna(-np.inf) > 0)
        & (out["n_trades"] >= MIN_SAMPLE_SIZE)
    )
    return out.sort_values("excess_return_vs_matched_random", ascending=False)


def compare_membership_aware(
    trades: pd.DataFrame | None = None,
    prices: dict | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> tuple[pd.DataFrame, dict]:
    """Headline test on the full universe vs. the membership-aware subset.

    Returns a per-signal comparison and a summary dict. A concept whose edge
    survives the filter is not an artefact of look-ahead membership; one that
    does not was partly reading the index committee's later decisions.
    """
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    trades = trades[trades["holding_period"] == holding_period].copy()
    trades["date"] = pd.to_datetime(trades["date"])

    if prices is None:
        from backtest.engine import _load_price_cache

        prices = {t: df.set_index("date") for t, df in _load_price_cache().items()}

    # Null pools for the full universe.
    pools_all = build_return_pools(prices, [holding_period])
    full = _rank(trades, pools_all, holding_period)

    # Membership-aware: both the trades AND the null pools must be restricted,
    # otherwise the signal is filtered while its benchmark is not.
    aware_trades = membership_aware_trades(trades)
    from utils.universe import entry_dates

    added = entry_dates()
    aware_prices = {}
    for t, df in prices.items():
        entry = added.get(t)
        aware_prices[t] = df[df.index >= entry] if pd.notna(entry) else df
    pools_aware = build_return_pools(aware_prices, [holding_period])
    aware = _rank(aware_trades, pools_aware, holding_period)

    comp = full.merge(aware, on="signal", suffixes=("_full", "_aware"), how="outer")
    comp["excess_delta_bps"] = (
        comp["excess_return_vs_matched_random_aware"]
        - comp["excess_return_vs_matched_random_full"]
    ) * 10_000
    comp["sign_preserved"] = (
        np.sign(comp["excess_return_vs_matched_random_full"])
        == np.sign(comp["excess_return_vs_matched_random_aware"])
    )

    beats_full = set(full.loc[full["beats_matched_random"], "signal"]) if len(full) else set()
    beats_aware = set(aware.loc[aware["beats_matched_random"], "signal"]) if len(aware) else set()
    summary = {
        "holding_period": holding_period,
        "trades_full": int(len(trades)),
        "trades_membership_aware": int(len(aware_trades)),
        "trades_dropped_pct": round(
            100 * (1 - len(aware_trades) / max(len(trades), 1)), 1
        ),
        "n_beats_full": len(beats_full),
        "n_beats_membership_aware": len(beats_aware),
        "survived_filter": sorted(beats_full & beats_aware),
        "lost_under_filter": sorted(beats_full - beats_aware),
        "gained_under_filter": sorted(beats_aware - beats_full),
        "sign_preserved_pct": round(100 * comp["sign_preserved"].mean(), 1)
        if len(comp) else np.nan,
        "median_excess_shift_bps": round(float(comp["excess_delta_bps"].median()), 2)
        if len(comp) else np.nan,
    }
    log.info("Membership-aware comparison: %s", summary)
    return comp, summary


def sector_map_disagreements() -> pd.DataFrame:
    """Where the hand-curated SECTOR_MAP disagrees with published GICS sectors."""
    from analytics.sectors import SECTOR_MAP
    from utils.universe import sector_map_from_snapshot

    official = sector_map_from_snapshot()
    rows = []
    for ticker, official_sector in official.items():
        curated = SECTOR_MAP.get(ticker)
        if curated is None:
            rows.append({"ticker": ticker, "curated": "(absent -> Unknown)",
                         "official": official_sector, "kind": "missing"})
        elif curated != official_sector:
            rows.append({"ticker": ticker, "curated": curated,
                         "official": official_sector, "kind": "mismatch"})
    return pd.DataFrame(rows).sort_values(["kind", "ticker"]).reset_index(drop=True)
