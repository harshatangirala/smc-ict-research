"""Generate reviewer_report.md -- an adversarial pre-read of the manuscript.

Runs the objections a referee at a finance journal or an informed SSRN reader
would raise, as programmatic checks against the actual artefacts, and reports
for each whether the study addresses it, addresses it partially, or is exposed.
The point is to surface rejection reasons before a referee does, not to argue
the paper is beyond criticism.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.config import PRIMARY_HOLDING_PERIOD, RESULTS_DIR  # noqa: E402


@dataclass
class Finding:
    objection: str
    status: str          # ADDRESSED | PARTIAL | EXPOSED
    evidence: str
    response: str
    severity: str = "medium"
    refs: list[str] = field(default_factory=list)


def _read(name):
    p = RESULTS_DIR / name
    if not p.exists():
        return None
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def run_checks() -> list[Finding]:
    F: list[Finding] = []
    master = _read("statistics_master.csv")
    events = _read("master_events.parquet")
    wf = _read("walkforward_summary.csv")
    be = _read("breakeven_costs.csv")
    dq = _read("data_quality_report.csv")
    mc = _read("monte_carlo.csv")
    sect = _read("sector_analysis.csv")
    sens = _read("sensitivity_stability.csv")

    prim = None
    if master is not None and len(master):
        prim = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD]

    # 1 -- look-ahead
    leaked = []
    if events is not None:
        leaked = [s for s in events["signal"].unique()
                  if "filled" in s or s.endswith("_label")]
    F.append(Finding(
        "Backtest results are contaminated by look-ahead bias.",
        "ADDRESSED" if not leaked else "EXPOSED",
        ("No forward-looking column reaches the event table. Causality is proved by "
         "truncation invariance over every registered detector, plus an index-position "
         "audit asserting that exits and MAE/MFE read only bars strictly after entry. "
         "A canary test confirms the probe still detects a known-leaky column, so a "
         "pass is not vacuous."
         if not leaked else f"Leaked signals present: {leaked}"),
        "The original pipeline did leak -- two FVG-fill columns emitting 187,719 "
        "look-ahead events (187,374 trades at h = 10) -- and the paper reports that "
        "as a finding rather than omitting it.",
        "critical", ["tests/test_no_lookahead.py", "results/validation_report.md"]))

    # 2 -- multiple testing
    n_hyp = len(master) if master is not None else 0
    F.append(Finding(
        "Testing dozens of concepts across eight horizons guarantees false positives.",
        "ADDRESSED" if n_hyp else "EXPOSED",
        f"BH-FDR at alpha = 0.05 is applied once across all {n_hyp} (signal x horizon) "
        "hypotheses rather than within slices. Combination search is bounded by a "
        "minimum occurrence count (100) and a hard cap (60 combinations).",
        "Note the direction of the result: the study's conclusion is mostly negative, "
        "so multiplicity works against finding an edge, not for it.",
        "high", ["analytics/master_stats.py"]))

    # 3 -- overlapping returns
    has_hac = master is not None and "p_value_vs_zero_iid" in master.columns
    ratio_note = ""
    if has_hac and prim is not None:
        m = prim.dropna(subset=["p_value_vs_zero", "p_value_vs_zero_iid"])
        if len(m):
            infl = int((m["p_value_vs_zero"]
                        > 100 * m["p_value_vs_zero_iid"].clip(lower=1e-300)).sum())
            ratio_note = (f" For {infl} of {len(m)} concepts the panel-robust p-value "
                          "is more than 100x the iid one.")
    F.append(Finding(
        "Overlapping forward returns and cross-sectional correlation invalidate the t-tests.",
        "ADDRESSED" if has_hac else "EXPOSED",
        "Inference collapses trades to calendar time and applies Newey-West with "
        "Bartlett weights at lag h -- the calendar-time-portfolio treatment. On a "
        "synthetic panel with a pure common factor the iid standard error is "
        "understated by roughly 16x." + ratio_note,
        "Both p-values are reported (`p_value_vs_zero` and `p_value_vs_zero_iid`), so "
        "the difference is auditable rather than asserted.",
        "high", ["analytics/statistics.py::calendar_time_mean_test"]))

    # 4 -- benchmark quality
    has_matched = master is not None and "p_value_vs_matched_random" in master.columns
    F.append(Finding(
        "A zero-return null is meaningless over a bull market; the benchmark must be a "
        "real alternative strategy.",
        "ADDRESSED" if has_matched else "EXPOSED",
        "The benchmark is composition-matched: each trade is measured against its own "
        "ticker's unconditional mean forward return, so ticker mix and per-ticker trade "
        "counts are held fixed. Inference is a calendar-time Newey-West test on that "
        "per-trade excess.",
        "The zero-return test is retained but labelled weak. Six conventional benchmarks "
        "run through the identical engine.",
        "high", ["analytics/statistics.py::matched_excess_calendar_test"]))

    # 4b -- calibration of the primary test
    cal = _read("test_calibration.csv")
    if cal is not None and len(cal):
        piv = cal.pivot(index="design", columns="test", values="rejection_rate")
        worst_cal = float(cal.loc[cal["test"] == "calendar", "rejection_rate"].max())
        worst_srs = float(cal.loc[cal["test"] == "srs", "rejection_rate"].max())
        anti = {}
        if "size_verdict" in cal.columns:
            anti = {t: sorted(cal.loc[(cal["test"] == t)
                                      & (cal["size_verdict"] == "anti-conservative"), "design"])
                    for t in ("srs", "calendar", "rotation")}
        ev4b = (
            "Designs with a true edge of zero, nominal 5%: the first primary test (SRS "
            f"variance) rejects up to {worst_srs:.0%}; the calendar-time test now used "
            f"rejects at most {worst_cal:.1%}. "
            + "; ".join(
                f"{d}: srs {piv.loc[d, 'srs']:.3f} / calendar {piv.loc[d, 'calendar']:.3f}"
                f" / rotation {piv.loc[d, 'rotation']:.3f}" for d in piv.index)
            + ("." if not anti else
               ". Anti-conservative in: " + "; ".join(
                   f"{t} -- {', '.join(v) if v else 'none'}" for t, v in anti.items()) + ".")
        )
        st4b = "ADDRESSED" if not anti.get("calendar") and worst_cal <= 0.08 else "PARTIAL"
    else:
        ev4b, st4b = "No calibration study found -- run tools/calibration_study.py.", "EXPOSED"
    F.append(Finding(
        "Are the p-values calibrated? A test that assumes independent entry dates "
        "overstates significance for signals that fire on the same dates.",
        st4b, ev4b,
        "Found by the authors' own audit, not a referee. Every headline count was "
        "recomputed with the calendar-time test; the SRS p-value is kept beside it in "
        "results/statistics_master.csv so the difference is auditable. The calendar test "
        "is conservative when entries are dispersed, which costs power but cannot "
        "manufacture the paper's null result; the exact rotation test is reported "
        "beside it for every hypothesis.",
        "critical", ["tools/calibration_study.py", "results/test_calibration.csv"]))

    # 5 -- one-sided
    sign_ok = True
    if prim is not None and "beats_matched_random" in prim.columns:
        bad = prim[prim["beats_matched_random"].fillna(False)
                   & (prim["excess_return_vs_matched_random"] <= 0)]
        sign_ok = len(bad) == 0
    F.append(Finding(
        "A two-sided test cannot support a directional claim about outperformance.",
        "ADDRESSED" if sign_ok else "EXPOSED",
        "All comparisons are one-sided with the direction stated, and the headline flag "
        "additionally requires a positive excess return. No row is flagged as beating "
        "the null with a non-positive excess (asserted in tools/check_artifacts.py).",
        "This corrects the prior version, in which 27 of 28 concepts reported as "
        "significant had in fact LOST to random entry. Documented in CHANGES.md 1.2.",
        "critical", ["CHANGES.md"]))

    # 6 -- out of sample
    oos = wf is not None and len(wf) > 0
    oos_note = ""
    if oos:
        oos_note = (f" {len(wf)} folds; mean out-of-sample excess of selected concepts "
                    f"{100 * wf['test_excess_selected'].mean():+.4f}pp; mean hit rate "
                    f"{100 * wf['hit_rate_selected'].mean():.1f}%.")
    F.append(Finding(
        "Everything is in-sample; there is no out-of-sample evidence.",
        "ADDRESSED" if oos else "EXPOSED",
        "Rolling walk-forward: train 3 years, test 1, step 1. Concepts are ranked on the "
        "training window only, and null pools are rebuilt inside each window so the "
        "training null never sees test prices." + oos_note,
        "Selection skill and concept skill are reported separately, together with the "
        "train-to-test rank correlation of the concept ordering.",
        "high", ["analytics/walkforward.py"]))

    # 7 -- costs
    cost_ok = be is not None and len(be) > 0
    cost_note = ""
    if cost_ok:
        n_above = int((be["breakeven_cost_bps"] > 26).sum())
        cost_note = (f" {n_above} of {len(be)} concepts have a break-even round-trip "
                     "cost above the modelled 26 bps upper bound.")
    F.append(Finding(
        "Gross returns are not tradeable; realistic costs would erase a few-basis-point edge.",
        "ADDRESSED" if cost_ok else "EXPOSED",
        "A cost-aware engine applies fixed + spread + stochastic slippage (11-26 bps "
        "round trip). Break-even cost is reported per concept and a cost grid shows "
        "where each claim dies." + cost_note,
        "Reporting break-even cost rather than a single cost assumption forestalls the "
        "objection that the assumption was chosen to preserve the result.",
        "high", ["backtest/engine_tc.py"]))

    # 8 -- survivorship
    surv = _read("survivorship_summary.csv")
    sc_path = RESULTS_DIR / "survivorship_comparison.json"
    if surv is not None and sc_path.exists():
        import json as _json

        sv = dict(zip(surv["metric"], surv["value"]))
        sc = _json.loads(sc_path.read_text(encoding="utf-8"))
        outcome = (
            f"{len(sc['survived_filter'])} of {sc['n_beats_full']} headline concepts "
            f"survive, {len(sc['lost_under_filter'])} are lost"
            if sc["n_beats_full"] else
            f"no concept beats the null in either universe (full {sc['n_beats_full']}, "
            f"membership-aware {sc['n_beats_membership_aware']})"
        )
        ev8 = (
            f"Sized with published index-entry dates: of {sv.get('current_constituents')} "
            f"analysed tickers, {sv.get('in_index_at_sample_start')} were members at the "
            f"sample start and at least {sv.get('estimated_removed_names_missing')} "
            "since-removed constituents are absent. Look-ahead membership is removed exactly "
            "by a re-test that filters both signals and matched-null pools: "
            f"{sc['trades_dropped_pct']}% of trades drop out; {outcome}; the sign of the "
            f"excess is preserved for {sc['sign_preserved_pct']}% of concepts."
        )
    else:
        ev8 = "Survivorship outputs not found -- run `python main.py survivorship`."
    F.append(Finding(
        "The universe is a current index snapshot applied retroactively -- survivorship bias.",
        "PARTIAL", ev8,
        "The removed firms cannot be recovered from free sources; Wikipedia no longer "
        "publishes its historical changes table. Survivor bias inflates signal and null "
        "alike, so it largely cancels in the excess -- unless removed firms, which are "
        "disproportionately distressed, responded to these patterns differently. A "
        "point-in-time universe remains the largest open threat to validity.",
        "high", ["analytics/survivorship.py", "results/survivorship_comparison.json"]))

    # 9 -- parameter mining
    F.append(Finding(
        "Results are reported at one parameter configuration inherited from the source scripts.",
        "ADDRESSED" if sens is not None and len(sens) else "PARTIAL",
        ("Grid and randomised parameter sweeps report sign-consistency and the "
         "coefficient of variation of the excess return across configurations."
         if sens is not None and len(sens) else
         "Sweep machinery exists (analytics/sensitivity.py) but no sweep output is "
         "present in this run -- run `python main.py sensitivity`."),
        "The defaults are the Pine `input.*` values, fixed before any result was seen, "
        "which is the honest starting point; the sweep shows whether the conclusion "
        "survives moving them.",
        "medium", ["analytics/sensitivity.py"]))

    # 10 -- concept fidelity
    spec_dir = ROOT / "docs" / "specs"
    specs = sorted(spec_dir.glob("*.yaml")) if spec_dir.exists() else []
    F.append(Finding(
        "SMC/ICT concepts are vaguely defined in the source material; the paper may be "
        "testing a strawman.",
        "PARTIAL" if specs else "EXPOSED",
        f"{len(specs)} machine-readable specifications give each concept a formal "
        "boolean definition, directionality, parameter ranges and an explicit causality "
        "argument. Ambiguities in the Pine transcription are named and the chosen "
        "reading is justified.",
        "Irreducible limitation: these are two specific LuxAlgo implementations, not the "
        "SMC/ICT literature as a whole. The title and scope section say so. A "
        "practitioner can reasonably object that their own variant differs.",
        "medium", ["docs/specs/"]))

    # 11 -- resampling validity
    fam = _read("rotation_null_all.csv")
    has_rot = fam is not None and len(fam) > 0
    rot_note = ""
    if has_rot:
        rot_note = (
            f" The exact rotation test covers all {len(fam)} hypotheses; "
            f"{int(fam['beats_rotation_null'].sum())} beat it after BH-FDR and "
            f"{int(fam['loses_to_rotation_null'].sum())} lose to it."
        )
    F.append(Finding(
        "Resampling schemes that draw dates independently per ticker ignore that trades "
        "cluster on the same dates.",
        "ADDRESSED" if has_rot else "PARTIAL",
        "The rotation null shifts the whole entry calendar by one offset for every "
        "ticker, preserving which trades share a date, and is evaluated exactly over "
        "every admissible offset by FFT, so its p-values can clear a family-wide FDR "
        "threshold. The independent-draw and per-ticker block schemes are kept for "
        "comparison and labelled anti-conservative. Confidence intervals used for "
        "inference are HAC, not iid bootstrap." + rot_note,
        "The iid bootstrap interval is still reported because the brief requires it; "
        "`ci_method` records when it ran on a subsample.",
        "medium", ["analytics/montecarlo.py::rotation_null_exact", "results/rotation_null_all.csv"]))

    # 11b -- power
    if prim is not None and "matched_null_se" in prim.columns:
        se = prim["matched_null_se"] * 1e4
        ex = prim["excess_return_vs_matched_random"] * 1e4
        upper = ex + 1.645 * se
        mde = 2.486 * se      # z_0.95 + z_0.80, one-sided test at 5%, 80% power
        ev_pow = (
            f"Minimum detectable excess at 80% power: median {mde.median():.0f} bp, best "
            f"{mde.min():.0f} bp (h = {PRIMARY_HOLDING_PERIOD}). The one-sided 95% upper "
            f"bound on the excess is below the 11 bp minimum round-trip cost for "
            f"{int((upper < 11).sum())} of {len(prim)} concepts and below 26 bp for "
            f"{int((upper < 26).sum())}."
        )
        st_pow = "PARTIAL"
    else:
        ev_pow, st_pow = "No standard errors found.", "EXPOSED"
    F.append(Finding(
        "A null result from an underpowered test is not evidence of absence.",
        st_pow, ev_pow,
        "The paper reports, per concept, the largest edge the data can exclude and "
        "separates concepts where a cost-covering edge is ruled out from those where "
        "the data are simply uninformative. Small edges -- the 10-20 bp range where a "
        "practitioner would care -- cannot be ruled out for most concepts, and the "
        "Limitations section says so.",
        "high", ["results/statistics_master.csv", "docs/manuscript.md"]))

    # 12 -- sector power
    pw = _read("sector_power.csv")
    if pw is not None and len(pw) and "mde_bps" in pw.columns:
        n_ok = int(pw["adequately_powered"].sum())
        st12 = "ADDRESSED" if n_ok == len(pw) else "PARTIAL"
        ev12 = (
            "Minimum detectable effect per sector from its calendar-time standard error: "
            f"{pw['mde_bps'].min():.1f}-{pw['mde_bps'].max():.1f} bp; {n_ok} of {len(pw)} "
            "sectors are adequately powered (MDE < 10 bp). Sectors are published GICS, "
            "with no unclassified tickers."
        )
    else:
        st12, ev12 = "EXPOSED", "No sector power analysis found."
    F.append(Finding(
        "Sector-level conclusions rest on too few names to have statistical power.",
        st12, ev12,
        "Sector differences are still presented as descriptive rather than pre-registered "
        "hypotheses, and GICS labels are current rather than point-in-time.",
        "medium", ["analytics/sectors.py", "results/sector_power.csv"]))

    # 13 -- mechanism
    F.append(Finding(
        "No economic mechanism is proposed for why these patterns would predict returns.",
        "EXPOSED",
        "The study is deliberately an evaluation of publicly documented indicator logic, "
        "not a theory paper. It offers no risk-based or behavioural model.",
        "A genuine limitation, and it should be stated rather than glossed. The "
        "defensible framing is that a null result needs no mechanism: showing that "
        "widely-taught rules do not predict returns is informative regardless of theory.",
        "medium", []))

    # 14 -- generalisation
    F.append(Finding(
        "Findings may not generalise beyond US large caps on daily bars, 2010-2026.",
        "PARTIAL",
        "Scope is stated explicitly: S&P 500 constituents, daily bars, 2010-2026, a "
        "period dominated by a bull market. Regime analysis splits results by trend and "
        "volatility state.",
        "No other market, asset class or timeframe is tested. Since SMC/ICT is most often "
        "taught on intraday FX and futures, the daily-equity restriction is a real limit "
        "on what the paper can claim, and the title reflects it.",
        "high", ["analytics/regimes.py"]))

    return F


def build_report(path: Path | None = None) -> Path:
    path = path or (RESULTS_DIR / "reviewer_report.md")
    findings = run_checks()
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.status != "EXPOSED"))

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.status] = counts.get(f.status, 0) + 1

    L = [
        "# Reviewer Report", "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*", "",
        "An adversarial pre-read: the objections a referee or an informed reader is most "
        "likely to raise, checked programmatically against the artefacts this run "
        "produced. `EXPOSED` items are genuine weaknesses that are **not** fixed; they "
        "are listed so the paper can state them rather than have a reader discover them.",
        "", "| Status | Count |", "|---|---:|",
    ]
    for k in ("ADDRESSED", "PARTIAL", "EXPOSED"):
        if k in counts:
            L.append(f"| {k} | {counts[k]} |")
    L += ["", "---", ""]

    for i, f in enumerate(findings, 1):
        badge = {"ADDRESSED": "PASS", "PARTIAL": "PARTIAL", "EXPOSED": "OPEN"}.get(f.status, "-")
        L += [
            f"## {i}. {f.objection}", "",
            f"**{badge}** · severity: {f.severity}", "",
            f"**Evidence.** {f.evidence}", "",
            f"**Response.** {f.response}", "",
        ]
        if f.refs:
            L += ["*See:* " + ", ".join(f"`{r}`" for r in f.refs), ""]
        L += ["---", ""]

    exposed = [f for f in findings if f.status == "EXPOSED"]
    partial = [f for f in findings if f.status == "PARTIAL"]
    L += [
        "## Summary for the authors", "",
        f"{len(exposed)} objection(s) remain genuinely unaddressed and must be stated "
        "plainly in the Limitations section:", "",
    ]
    for f in exposed:
        L.append(f"* {f.objection}")
    L += ["", f"{len(partial)} are partially addressed and should be scoped explicitly "
          "rather than claimed as solved:", ""]
    for f in partial:
        L.append(f"* {f.objection}")
    L += [
        "", "### The strongest defensible position", "",
        "This paper's headline result is **negative** -- no concept beats a "
        "composition-matched random entry after FDR control -- and a negative result is "
        "robust to most of the objections that would sink a positive one. Multiplicity "
        "and transaction costs push *against* finding an edge, and an anti-conservative "
        "test would have produced rejections, not fewer of them, so none of these can "
        "manufacture the null reported here. The paper should make that argument "
        "explicitly rather than leaving a referee to notice it.", "",
        "The corresponding risk is the opposite one, and it is real here: the primary "
        "test is conservative when entries are dispersed, and its minimum detectable "
        "effect is larger than a plausible edge for most concepts. The power finding "
        "above states what the data can and cannot exclude; the paper should lead with "
        "it rather than let 'no concept beats the null' be read as 'no concept has an "
        "edge'.", "",
    ]
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {path}")
    return path


if __name__ == "__main__":
    build_report()
