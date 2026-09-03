"""Verify that the numbers asserted in docs/manuscript.md match the artefacts.

A manuscript is written once and the pipeline is rerun many times. Without a
check, a re-run that moves a number leaves the paper quietly wrong. This script
re-derives each headline claim from `results/` and compares it with the value
the manuscript states, exiting non-zero on any mismatch.

It is deliberately a *claim list*, not a parser: each entry names the claim, the
value in the text, and the code that recomputes it. Adding a numeric claim to
the paper means adding it here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.config import PRIMARY_HOLDING_PERIOD, RESULTS_DIR  # noqa: E402

TOL_ABS = 1e-4   # for returns expressed as fractions
TOL_REL = 0.02   # 2% relative tolerance for ratios and derived quantities


def _read(name):
    p = RESULTS_DIR / name
    if not p.exists():
        return None
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def main() -> int:
    master = _read("statistics_master.csv")
    events = _read("master_events.parquet")
    trades_path = RESULTS_DIR / "trades.parquet"
    dq = _read("data_quality_report.csv")
    wf = _read("walkforward_summary.csv")
    be = _read("breakeven_costs.csv")

    if master is None:
        print("statistics_master.csv missing -- run the pipeline first", file=sys.stderr)
        return 1

    prim = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD]
    tested = prim[~prim["low_sample_warning"].fillna(True)]

    checks: list[tuple[str, float, float, float]] = []  # name, stated, actual, tol

    def add(name, stated, actual, tol=TOL_REL, absolute=False):
        checks.append((name, stated, actual, tol, absolute))

    # --- Abstract / Section 3-5 counts ------------------------------------
    add("concepts tested", 44, int(prim["signal"].nunique()), 0, True)
    add("hypotheses in the FDR family", 352, int(len(master)), 0, True)
    add("beats matched null (h=10)", 5,
        int(prim["beats_matched_random"].fillna(False).sum()), 0, True)
    add("loses to matched null (h=10)", 0,
        int((tested["reject_vs_matched_random"].fillna(False)
             & (tested["excess_return_vs_matched_random"] < 0)).sum()), 0, True)
    add("significant vs zero (h=10)", 39,
        int(prim["reject_vs_zero"].fillna(False).sum()), 0, True)
    add("indistinguishable (h=10)", 39,
        int(len(prim) - prim["beats_matched_random"].fillna(False).sum()), 0, True)

    if events is not None:
        add("detected events", 2_226_881, int(len(events)), 0, True)
        add("tickers with events", 496, int(events["ticker"].nunique()), 0, True)
    if trades_path.exists():
        n_trades = len(pd.read_parquet(trades_path, columns=["signal"]))
        add("simulated trades", 17_731_944, int(n_trades), 0, True)
    if dq is not None:
        add("tickers downloaded", 498, int(len(dq)), 0, True)

    # --- Table 3: the five winners ----------------------------------------
    winners = {
        "smc_swing_choch_bearish": 0.0033,
        "ict_sweep_sellside_bullish": 0.0012,
        "ict_sweep_buyside_bearish": 0.0011,
        "smc_internal_ob_bearish_mitigated": 0.0008,
        "ict_nwog_gap_up": 0.0005,
    }
    actual_winners = set(
        prim.loc[prim["beats_matched_random"].fillna(False), "signal"]
    )
    if actual_winners != set(winners):
        print(
            "MISMATCH  set of concepts beating the null\n"
            f"          manuscript: {sorted(winners)}\n"
            f"          artefacts : {sorted(actual_winners)}",
            file=sys.stderr,
        )
        return 1
    for sig, stated in winners.items():
        row = prim[prim["signal"] == sig].iloc[0]
        add(f"excess {sig}", stated,
            float(row["excess_return_vs_matched_random"]), 5e-5, True)

    # --- Section 4.4: SE inflation ----------------------------------------
    ratios = []
    for _, r in prim.iterrows():
        n, sd, hac = r.get("n_trades"), r.get("std_return"), r.get("hac_se")
        if n and np.isfinite(sd) and np.isfinite(hac) and sd > 0:
            iid = sd / np.sqrt(n)
            if iid > 0:
                ratios.append(hac / iid)
    if ratios:
        add("SE inflation min", 1.5, float(min(ratios)), 0.1)
        add("SE inflation max", 11.8, float(max(ratios)), 0.05)
        add("SE inflation median", 5.8, float(np.median(ratios)), 0.05)

    # --- Section 5.3: walk-forward ----------------------------------------
    if wf is not None and len(wf):
        add("walk-forward folds", 13, int(len(wf)), 0, True)
        add("mean OOS excess of selected", -0.0016,
            float(wf["test_excess_selected"].mean()), 2e-4, True)
        add("mean hit rate", 0.538, float(wf["hit_rate_selected"].mean()), 0.02)
        add("mean rank correlation", 0.387, float(wf["rank_correlation"].mean()), 0.05)

    # --- Section 5.4: costs ------------------------------------------------
    if be is not None and "breakeven_excess_cost_bps" in be.columns:
        bx = be.dropna(subset=["breakeven_excess_cost_bps"])
        add("gross break-even clearing 26bp", 22,
            int((be["breakeven_cost_bps"] > 26).sum()), 0, True)
        add("excess break-even clearing 26bp", 1,
            int((bx["breakeven_excess_cost_bps"] > 26).sum()), 0, True)
        add("excess break-even clearing 11bp", 4,
            int((bx["breakeven_excess_cost_bps"] > 11).sum()), 0, True)

    # --- Table 6: targeted sensitivity sweep -------------------------------
    tg = _read("sensitivity_targeted_grid.csv")
    if tg is not None and len(tg):
        frac = tg.groupby("signal")["excess_return_vs_matched_random"].apply(
            lambda x: (x > 0).sum()
        )
        n_cfg = tg.groupby("signal").size()
        for sig, stated_pos, stated_n in [
            ("ict_sweep_sellside_bullish", 33, 36),
            ("ict_sweep_buyside_bearish", 36, 36),
            ("ict_nwog_gap_up", 24, 36),
            ("ict_nwog_gap_down", 0, 36),
        ]:
            if sig in frac.index:
                add(f"sweep configs positive {sig}", stated_pos, int(frac[sig]), 0, True)
                add(f"sweep configs total {sig}", stated_n, int(n_cfg[sig]), 0, True)
        gap = tg[tg["signal"] == "ict_nwog_gap_up"]
        if len(gap) and "ict.gap_min_atr" in gap.columns:
            by_thr = gap.groupby("ict.gap_min_atr")["excess_return_vs_matched_random"].mean() * 10_000
            for thr, stated in [(0.05, 2.6), (0.10, 0.4), (0.25, -1.6)]:
                if thr in by_thr.index:
                    add(f"gap excess at threshold {thr}", stated, float(by_thr[thr]), 0.15, True)

    # --- report ------------------------------------------------------------
    failures = []
    for name, stated, actual, tol, absolute in checks:
        if absolute:
            ok = abs(stated - actual) <= max(tol, 0)
        else:
            denom = abs(stated) if stated else 1.0
            ok = abs(stated - actual) / denom <= tol
        status = "ok  " if ok else "FAIL"
        print(f"  {status} {name:<42} manuscript={stated:<14} artefact={actual}")
        if not ok:
            failures.append((name, stated, actual))

    print()
    if failures:
        print(f"{len(failures)} manuscript claim(s) no longer match the artefacts:",
              file=sys.stderr)
        for name, stated, actual in failures:
            print(f"  - {name}: manuscript says {stated}, artefacts say {actual}",
                  file=sys.stderr)
        return 1
    print(f"All {len(checks)} manuscript claims match the artefacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
