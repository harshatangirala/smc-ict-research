"""Every number the manuscript states, computed from the artefacts in one place.

The manuscript, README, CHANGES and review notes quote these values. Computing
them here -- rather than transcribing them from terminal output -- is what lets
tools/check_manuscript_numbers.py and a reader verify that the prose matches the
data. It also computes the corresponding facts for the PREVIOUS version of the
study from data/bundle/, so claims about what the earlier analysis got wrong are
checked against its own committed outputs rather than asserted.

    python tools/manuscript_facts.py      # prints, and writes results/manuscript_facts.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.statistics import apply_fdr_correction  # noqa: E402
from utils.config import (  # noqa: E402
    DATA_CACHE_DIR,
    FDR_ALPHA,
    MIN_SAMPLE_SIZE,
    PRIMARY_HOLDING_PERIOD,
    RESULTS_DIR,
)

H = PRIMARY_HOLDING_PERIOD
BUNDLE = ROOT / "data" / "bundle"


def _r(name: str, base: Path = RESULTS_DIR):
    p = base / name
    if not p.exists():
        return None
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def _f(x, nd: int = 6):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


def _beats(frame: pd.DataFrame, p_col: str) -> pd.Series:
    """Headline rule: positive excess, BH-FDR survivor, adequate sample."""
    fdr = apply_fdr_correction(frame[p_col], alpha=FDR_ALPHA)
    return (
        fdr["reject_null"].fillna(False).astype(bool)
        & (frame["excess_return_vs_matched_random"] > 0)
        & (frame["n_trades"] >= MIN_SAMPLE_SIZE)
    )


def headline(F: dict) -> None:
    m = _r("statistics_master.csv")
    prim = m[m["holding_period"] == H]
    tested = prim[~prim["low_sample_warning"].fillna(True)]
    beats = prim["beats_matched_random"].fillna(False).astype(bool)
    loses = (tested["reject_vs_matched_random"].fillna(False).astype(bool)
             & (tested["excess_return_vs_matched_random"] < 0))
    F["n_hypotheses"] = int(len(m))
    F["n_concepts"] = int(prim["signal"].nunique())
    F["n_beats"] = int(beats.sum())
    F["n_loses"] = int(loses.sum())
    F["n_indistinguishable"] = F["n_concepts"] - F["n_beats"] - F["n_loses"]
    F["n_sig_vs_zero"] = int(prim["reject_vs_zero"].fillna(False).sum())
    F["n_sig_vs_zero_all"] = int(m["reject_vs_zero"].fillna(False).sum())
    F["n_long_concepts"] = int((prim["direction"] == 1).sum())
    F["mean_gross_long_bp"] = _f(prim.loc[prim["direction"] == 1, "avg_return"].mean() * 1e4, 1)
    F["mean_null_long_bp"] = _f(prim.loc[prim["direction"] == 1, "matched_null_mean"].mean() * 1e4, 1)
    F["entry_dates_h"] = {r.signal: int(r.n_entry_dates) for r in prim.itertuples()
                          if pd.notna(r.n_entry_dates)}
    F["mean_excess_all_bp"] = _f(prim["excess_return_vs_matched_random"].mean() * 1e4, 2)

    # What the first (SRS-variance) primary test would have reported on the SAME
    # data, same family, same FDR -- the size of the calibration correction.
    if "p_value_vs_matched_random_srs" in m.columns:
        srs = _beats(m, "p_value_vs_matched_random_srs")
        at_h = srs & (m["holding_period"] == H)
        F["n_beats_under_srs_test"] = int(at_h.sum())
        F["beats_under_srs_test"] = sorted(m.loc[at_h, "signal"])

    by_h = m.pivot_table(index="signal", columns="holding_period",
                         values="excess_return_vs_matched_random")
    beat_h = m.assign(b=m["beats_matched_random"].fillna(False).astype(float)).pivot_table(
        index="signal", columns="holding_period", values="b")
    F["beats_by_horizon"] = {int(h): int(beat_h[h].sum()) for h in beat_h.columns}
    rows = prim[beats].sort_values("excess_return_vs_matched_random", ascending=False)
    F["winners"] = [
        {
            "signal": r.signal, "direction": int(r.direction), "n_trades": int(r.n_trades),
            "n_entry_dates": int(r.n_entry_dates) if pd.notna(r.n_entry_dates) else None,
            "mean_bp": _f(r.avg_return * 1e4, 2),
            "null_bp": _f(r.matched_null_mean * 1e4, 2),
            "excess_bp": _f(r.excess_return_vs_matched_random * 1e4, 2),
            "se_bp": _f(r.matched_null_se * 1e4, 2),
            "p_adj": _f(r.p_adj_vs_matched_random, 6),
            "d": _f(r.effect_size_cohens_d, 4),
            "d_lo": _f(r.cohens_d_ci_lower, 4), "d_hi": _f(r.cohens_d_ci_upper, 4),
            "excess_by_h_bp": {int(h): _f(by_h.loc[r.signal, h] * 1e4, 2) for h in by_h.columns},
            "horizons_beating": int(beat_h.loc[r.signal].sum()),
        }
        for r in rows.itertuples()
    ]

    F["min_p_primary_h"] = _f(prim["p_value_vs_matched_random"].min(), 4)
    F["min_p_primary_h_signal"] = str(prim.loc[prim["p_value_vs_matched_random"].idxmin(), "signal"])
    F["min_p_primary_all"] = _f(m["p_value_vs_matched_random"].min(), 4)
    F["min_p_adj_primary_all"] = _f(m["p_adj_vs_matched_random"].min(), 4)
    F["n_positive_excess_h"] = int((prim["excess_return_vs_matched_random"] > 0).sum())
    if "loses_to_matched_random" in m.columns:
        F["n_loses_two_sided_all"] = int(m["loses_to_matched_random"].fillna(False).sum())
        F["min_p_adj_two_sided_all"] = _f(m["p_adj_vs_matched_random_two_sided"].min(), 4)
    if "p_value_vs_matched_random_srs" in m.columns:
        srs_all = _beats(m, "p_value_vs_matched_random_srs")
        F["n_beats_under_srs_all_horizons"] = int(srs_all.sum())
        F["srs_beats_by_horizon"] = {int(k): int(v) for k, v in
                                     m[srs_all].groupby("holding_period").size().items()}

    # Power: what the data can and cannot exclude.
    se = prim["matched_null_se"] * 1e4
    ex = prim["excess_return_vs_matched_random"] * 1e4
    upper = ex + 1.645 * se
    F["power"] = {
        "se_median_bp": _f(se.median(), 1), "se_min_bp": _f(se.min(), 1),
        "se_max_bp": _f(se.max(), 1),
        "mde_median_bp": _f(2.486 * se.median(), 1), "mde_min_bp": _f(2.486 * se.min(), 1),
        "n_upper95_below_0": int((upper < 0).sum()),
        "n_upper95_below_11": int((upper < 11).sum()),
        "n_upper95_below_26": int((upper < 26).sum()),
        "upper95_below_11_signals": sorted(prim.loc[upper < 11, "signal"]),
    }
    pos = prim[prim["excess_return_vs_matched_random"] > 0].sort_values(
        "excess_return_vs_matched_random", ascending=False)
    F["positive_point_estimates"] = [
        {"signal": r.signal, "direction": int(r.direction), "n_trades": int(r.n_trades),
         "n_entry_dates": int(r.n_entry_dates) if pd.notna(r.n_entry_dates) else None,
         "mean_bp": _f(r.avg_return * 1e4, 1), "null_bp": _f(r.matched_null_mean * 1e4, 1),
         "excess_bp": _f(r.excess_return_vs_matched_random * 1e4, 1),
         "se_bp": _f(r.matched_null_se * 1e4, 1), "se_srs_bp": _f(r.matched_null_se_srs * 1e4, 1),
         "p": _f(r.p_value_vs_matched_random, 3), "p_srs": _f(r.p_value_vs_matched_random_srs, 4),
         "p_adj": _f(r.p_adj_vs_matched_random, 4),
         "upper95_bp": _f((r.excess_return_vs_matched_random + 1.645 * r.matched_null_se) * 1e4, 1)}
        for r in pos.itertuples()
    ]

    ok = prim.dropna(subset=["hac_se", "std_return", "n_trades"])
    ratio = ok["hac_se"] / (ok["std_return"] / np.sqrt(ok["n_trades"]))
    F["se_inflation_vs_zero"] = {"min": _f(ratio.min(), 2), "median": _f(ratio.median(), 2),
                                 "max": _f(ratio.max(), 2)}
    top = ok.assign(ratio=ratio).nlargest(5, "ratio")
    F["se_inflation_top5"] = [
        {"signal": r.signal, "n_trades": int(r.n_trades),
         "iid_se": _f(r.std_return / np.sqrt(r.n_trades), 6), "hac_se": _f(r.hac_se, 6),
         "ratio": _f(r.ratio, 2)} for r in top.itertuples()
    ]
    if "matched_null_se_srs" in prim.columns:
        rr = (prim["matched_null_se"] / prim["matched_null_se_srs"]).replace(
            [np.inf, -np.inf], np.nan).dropna()
        F["matched_se_calendar_over_srs"] = {"min": _f(rr.min(), 2), "median": _f(rr.median(), 2),
                                             "max": _f(rr.max(), 2)}


def universe(F: dict) -> None:
    from signals.event_engine import EVENT_REGISTRY

    F["n_registered_signals"] = len(EVENT_REGISTRY)
    ev = _r("master_events.parquet")
    if ev is not None:
        F["n_events"] = int(len(ev))
        F["n_tickers_with_events"] = int(ev["ticker"].nunique())
        F["n_signals_firing"] = int(ev["signal"].nunique())
        F["n_registered_never_fire"] = F["n_registered_signals"] - F["n_signals_firing"]
        F["registered_never_fire"] = sorted(set(EVENT_REGISTRY) - set(ev["signal"].unique()))
    tp = RESULTS_DIR / "trades.parquet"
    if tp.exists():
        t = pd.read_parquet(tp, columns=["holding_period"])
        F["n_trades_total"] = int(len(t))
        F["n_trades_at_h"] = int((t["holding_period"] == H).sum())
    dq = _r("data_quality_report.csv")
    if dq is not None:
        F["n_downloaded"] = int(len(dq))
        F["n_short_history_after_2010"] = int((dq["start"] > "2010-01-05").sum())
    # Materially invalid OHLC bars (>1e-6 of close), straight from the cache.
    material, noise = [], 0
    for f in sorted(Path(DATA_CACHE_DIR).glob("*.parquet")):
        d = pd.read_parquet(f).sort_index()
        hi = d[["high", "open", "close"]].max(axis=1)
        lo = d[["low", "open", "close"]].min(axis=1)
        mag = ((hi - d["high"]).abs() + (d["low"] - lo).abs()) / d["close"].abs()
        noise += int(((mag > 0) & (mag <= 1e-6)).sum())
        material += [f"{f.stem} {ix.date()}" for ix in mag[mag > 1e-6].index]
    F["ohlc_material_invalid_bars"] = material
    F["ohlc_float_noise_bars"] = noise


def calibration(F: dict) -> None:
    c = _r("test_calibration.csv")
    if c is not None:
        F["calibration"] = {f"{r.design}:{r.test}": _f(r.rejection_rate, 4) for r in c.itertuples()}
        F["calibration_reps"] = {r.test: int(r.reps) for r in c.itertuples()}
        if "se_ratio" in c.columns:
            F["calibration_se_ratio"] = {f"{r.design}:{r.test}": _f(r.se_ratio, 2)
                                         for r in c.itertuples()}
            F["calibration_verdict"] = {f"{r.design}:{r.test}": r.size_verdict
                                        for r in c.itertuples()}
            F["calibration_mean_estimate_bp"] = {f"{r.design}:{r.test}": _f(r.mean_estimate * 1e4, 2)
                                                 for r in c.itertuples()}


def rotation(F: dict) -> None:
    fam = _r("rotation_null_all.csv")
    if fam is None or fam.empty:
        return
    beats = fam["beats_rotation_null"].fillna(False).astype(bool)
    F["rot_n_hypotheses"] = int(len(fam))
    F["rot_n_beats"] = int(beats.sum())
    F["rot_beats"] = [f"{s}@h{int(h)}" for s, h in
                      zip(fam.loc[beats, "signal"], fam.loc[beats, "holding_period"])]
    F["rot_n_loses"] = int(fam["loses_to_rotation_null"].fillna(False).sum())
    F["rot_offsets"] = {"min": int(fam["n_offsets"].min()), "max": int(fam["n_offsets"].max())}
    F["rot_min_p_adj"] = _f(fam["p_adj"].min(), 4)
    h = fam[fam["holding_period"] == H].set_index("signal")
    F["rot_n_loses_h"] = int(h["loses_to_rotation_null"].fillna(False).sum())
    F["rot_h"] = {s: {"p": _f(r.p_value, 4), "p_adj": _f(r.p_adj, 4),
                      "excess_bp": _f(r.excess_vs_rotation * 1e4, 1),
                      "null_se_bp": _f(r.null_se * 1e4, 1)}
                  for s, r in h.sort_values("p_value").iterrows()}


def walkforward(F: dict) -> None:
    w = _r("walkforward_summary.csv")
    if w is None or w.empty:
        return
    F["wf_folds"] = int(len(w))
    F["wf_mean_train_excess_selected_bp"] = _f(w["train_excess_selected"].mean() * 1e4, 2)
    F["wf_mean_test_excess_selected_bp"] = _f(w["test_excess_selected"].mean() * 1e4, 2)
    F["wf_mean_test_excess_all_bp"] = _f(w["test_excess_all"].mean() * 1e4, 2)
    F["wf_mean_hit_rate"] = _f(w["hit_rate_selected"].mean(), 4)
    F["wf_mean_rank_corr"] = _f(w["rank_correlation"].mean(), 4)
    F["wf_folds_positive_test_excess"] = int((w["test_excess_selected"] > 0).sum())
    ts = w["test_excess_selected"] * 1e4
    tr = w["train_excess_selected"] * 1e4
    yr = pd.to_datetime(w["test_start"]).dt.year
    F["wf_test_bp_2013_2020"] = _f(ts[yr <= 2020].mean(), 1)
    F["wf_test_bp_2021_2023"] = _f(ts[(yr >= 2021) & (yr <= 2023)].mean(), 1)
    F["wf_train_bp_2021_2023"] = _f(tr[(yr >= 2021) & (yr <= 2023)].mean(), 1)
    F["wf_train_bp_other"] = _f(tr[(yr < 2021) | (yr > 2023)].mean(), 1)
    det = _r("walkforward_detail.csv")
    if det is not None and "selected" in det.columns:
        sel = det[det["selected"].fillna(False).astype(bool)]
        F["wf_selected_by_fold"] = {int(k): sorted(g["signal"]) for k, g in sel.groupby("fold")}
    F["wf_by_fold"] = [
        {"fold": int(r.fold), "test_start": str(r.test_start),
         "train_bp": _f(r.train_excess_selected * 1e4, 2),
         "test_bp": _f(r.test_excess_selected * 1e4, 2),
         "hit": _f(r.hit_rate_selected, 3), "rho": _f(r.rank_correlation, 3)}
        for r in w.itertuples()
    ]


def costs(F: dict) -> None:
    b = _r("breakeven_costs.csv")
    if b is None:
        return
    F["be_gross_over_26"] = int((b["breakeven_cost_bps"] > 26).sum())
    m = _r("statistics_master.csv")
    if m is not None:
        d = m[m["holding_period"] == H].set_index("signal")["direction"]
        over = b.loc[b["breakeven_cost_bps"] > 26, "signal"].map(d)
        F["be_gross_over_26_n_long"] = int((over == 1).sum())
    F["be_gross_over_11"] = int((b["breakeven_cost_bps"] > 11).sum())
    if "breakeven_excess_cost_bps" in b.columns:
        bx = b.dropna(subset=["breakeven_excess_cost_bps"])
        F["be_excess_over_26"] = int((bx["breakeven_excess_cost_bps"] > 26).sum())
        F["be_excess_over_11"] = int((bx["breakeven_excess_cost_bps"] > 11).sum())
        F["be_excess_over_26_signals"] = sorted(bx.loc[bx["breakeven_excess_cost_bps"] > 26, "signal"])
        F["be_excess_over_11_signals"] = sorted(bx.loc[bx["breakeven_excess_cost_bps"] > 11, "signal"])
    n = _r("net_of_cost_rankings.csv")
    if n is not None:
        F["n_positive_net_mean"] = int((n["net_mean"] > 0).sum())


def sectors_regimes(F: dict) -> None:
    s = _r("sector_analysis.csv")
    p = _r("sector_power.csv")
    if s is not None:
        e = s.set_index("sector")["excess_return_vs_matched_random"] * 1e4
        F["n_sectors"] = int(len(s))
        F["n_sectors_unknown"] = int((s["sector"] == "Unknown").sum())
        F["sector_excess_bp"] = {k: _f(v, 2) for k, v in e.items()}
        F["n_sectors_positive"] = int((e > 0).sum())
        if "p_value_vs_matched_random" in s.columns:
            F["sector_p_two_sided"] = {r.sector: _f(r.p_value_vs_matched_random, 6)
                                       for r in s.itertuples()}
            fs = apply_fdr_correction(s["p_value_vs_matched_random"], alpha=FDR_ALPHA)
            F["sector_p_adj"] = {sec: _f(p, 4) for sec, p in zip(s["sector"], fs["p_adjusted"])}
            F["sectors_significant_bh"] = sorted(s.loc[fs["reject_null"].fillna(False).astype(bool), "sector"])
            F["sector_n_tickers"] = {r.sector: int(r.n_tickers) for r in s.itertuples()}
    if p is not None:
        F["sector_mde_bp"] = {"min": _f(p["mde_bps"].min(), 2), "max": _f(p["mde_bps"].max(), 2)}
        F["n_sectors_powered"] = int(p["adequately_powered"].sum())
        F["sector_mde_by_sector_bp"] = {r.sector: _f(r.mde_bps, 2) for r in p.itertuples()}
    g = _r("regime_analysis.csv")
    if g is not None:
        F["regimes"] = [
            {"trend": r.trend_regime, "vol": r.vol_regime, "n_trades": int(r.n_trades),
             "excess_bp": _f(r.excess_return_vs_matched_random * 1e4, 2)}
            for r in g.itertuples()
        ]


def survivorship(F: dict) -> None:
    s = _r("survivorship_summary.csv")
    if s is not None:
        F["surv"] = dict(zip(s["metric"], s["value"]))
    j = RESULTS_DIR / "survivorship_comparison.json"
    if j.exists():
        F["surv_cmp"] = json.loads(j.read_text(encoding="utf-8"))
    ma = _r("survivorship_membership_aware.csv")
    if ma is not None and "winners" in F:
        mi = ma.set_index("signal")
        F["surv_winners"] = [
            {"signal": w["signal"],
             "n_full": int(mi.loc[w["signal"], "n_trades_full"]),
             "n_aware": int(mi.loc[w["signal"], "n_trades_aware"]),
             "excess_full_bp": _f(mi.loc[w["signal"], "excess_return_vs_matched_random_full"] * 1e4, 2),
             "excess_aware_bp": _f(mi.loc[w["signal"], "excess_return_vs_matched_random_aware"] * 1e4, 2),
             "beats_aware": bool(mi.loc[w["signal"], "beats_matched_random_aware"])
             if pd.notna(mi.loc[w["signal"], "beats_matched_random_aware"]) else None}
            for w in F["winners"] if w["signal"] in mi.index
        ]
    d = _r("sector_map_disagreements.csv")
    if d is not None:
        F["curated_map_missing"] = int((d["kind"] == "missing").sum())
        F["curated_map_mismatch"] = int((d["kind"] == "mismatch").sum())
        F["curated_map_mismatch_tickers"] = sorted(d.loc[d["kind"] == "mismatch", "ticker"])


def sweeps_mc_combos(F: dict) -> None:
    tg = _r("sensitivity_targeted_grid.csv")
    if tg is not None and len(tg):
        F["sweep"] = {
            s: {"n": int(len(v)),
                "positive": int((v["excess_return_vs_matched_random"] > 0).sum()),
                "p_below_05": int((v["p_value_vs_matched_random"] < 0.05).sum()),
                "min_p": _f(v["p_value_vs_matched_random"].min(), 3),
                "mean_bp": _f(v["excess_return_vs_matched_random"].mean() * 1e4, 2),
                "range_bp": _f((v["excess_return_vs_matched_random"].max()
                                - v["excess_return_vs_matched_random"].min()) * 1e4, 2)}
            for s, v in tg.groupby("signal")
        }
        gap = tg[tg["signal"] == "ict_nwog_gap_up"]
        if len(gap) and "ict.gap_min_atr" in gap.columns:
            F["gap_excess_by_threshold_bp"] = {
                str(k): _f(v * 1e4, 2) for k, v in
                gap.groupby("ict.gap_min_atr")["excess_return_vs_matched_random"].mean().items()
            }
    st = _r("sensitivity_stability.csv")
    if st is not None and "responds_to_sweep" in st.columns:
        F["broad_grid_signals_responding"] = int(st["responds_to_sweep"].sum())
    mc = _r("monte_carlo.csv")
    if mc is not None and len(mc):
        F["mc"] = [
            {"signal": r.signal, "observed_bp": _f(r.observed_mean * 1e4, 2),
             "rotation_p": _f(getattr(r, "rotation_p_value", np.nan), 4),
             "rotation_p_adj": _f(getattr(r, "rotation_p_adj", np.nan), 4),
             "srs_mc_p": _f(r.mc_p_value, 4), "block_p": _f(r.block_p_value, 4)}
            for r in mc.itertuples()
        ]
        F["mc_runs"] = int(mc["n_runs"].iloc[0])
    cb = _r("combination_rankings.csv")
    if cb is not None and len(cb):
        F["n_combos_tested"] = int(len(cb))
        F["n_combos_beating"] = int(cb.get("beats_matched_random", pd.Series(False)).fillna(False).sum())
    sk = _r("stock_rankings.csv")
    if sk is not None and len(sk):
        F["n_stocks_eligible"] = int(sk["eligible"].sum()) if "eligible" in sk else None
        F["n_stocks_significant"] = int(sk["significant_vs_baseline"].fillna(False).sum()) \
            if "significant_vs_baseline" in sk else None


def previous_version(F: dict) -> None:
    """The earlier study's own committed outputs -- the basis of every 'it got X wrong'."""
    old = _r("concept_rankings.csv", BUNDLE)
    if old is not None:
        flagged = old["significant_vs_baseline"].fillna(False).astype(bool)
        F["old_n_concepts"] = int(len(old))
        F["old_n_flagged_vs_baseline"] = int(flagged.sum())
        F["old_flagged_with_positive_effect"] = int((flagged & (old["effect_size_vs_baseline"] > 0)).sum())
        F["old_flagged_with_negative_effect"] = int((flagged & (old["effect_size_vs_baseline"] < 0)).sum())
        F["old_n_sig_vs_zero"] = int(old["significant_vs_zero"].fillna(False).sum())
        leak = old[old["signal"].str.contains("filled")]
        F["old_leaky_trades_at_h10"] = int(leak["n_trades"].sum())
    ev = _r("master_events.parquet", BUNDLE)
    if ev is not None:
        F["old_n_events"] = int(len(ev))
        F["old_n_tickers"] = int(ev["ticker"].nunique())
        filled = ev["signal"].str.contains("filled")
        F["old_leaky_events"] = int(filled.sum())
        F["old_leaky_share_pct"] = _f(100 * filled.mean(), 2)
        nd = ev["signal"] == "ict_ndog_formed"
        F["old_ndog_events"] = int(nd.sum())
        F["old_ndog_share_pct"] = _f(100 * nd.mean(), 2)
    tb = BUNDLE / "trades_sample.parquet"
    F["old_trades_sample_exists"] = tb.exists()


def main() -> int:
    F: dict = {"holding_period": H}
    for step in (headline, universe, calibration, rotation, walkforward, costs,
                 sectors_regimes, survivorship, sweeps_mc_combos, previous_version):
        try:
            step(F)
        except Exception as exc:  # noqa: BLE001 - report which block failed, keep the rest
            F[f"error_{step.__name__}"] = f"{type(exc).__name__}: {exc}"
    out = RESULTS_DIR / "manuscript_facts.json"
    out.write_text(json.dumps(F, indent=2, default=str), encoding="utf-8")
    print(json.dumps(F, indent=1, default=str))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
