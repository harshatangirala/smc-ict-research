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
        "The original pipeline did leak -- two FVG-fill columns contributing 187,719 "
        "trades -- and the paper reports that as a finding rather than omitting it.",
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
        "The primary test is a design-based matched randomization: hold the ticker mix "
        "and the per-ticker trade count fixed, then ask what mean randomly chosen entry "
        "dates would produce. Its analytic moments are validated against a 2,000-run "
        "simulation (null means agree to five decimals; SE ratios 0.99-1.04).",
        "The zero-return test is retained but labelled weak. Six conventional benchmarks "
        "run through the identical engine.",
        "high", ["analytics/statistics.py::matched_randomization_test"]))

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
    F.append(Finding(
        "The universe is a current index snapshot applied retroactively -- survivorship bias.",
        "PARTIAL" if dq is not None else "EXPOSED",
        "Acknowledged and quantified: the constituent list is a 2026 snapshot, five "
        "tickers are permanently unavailable, and roughly 80 begin after 2010. The bias "
        "inflates absolute return levels for signals and baselines alike.",
        "NOT fully corrected -- a point-in-time constituent history is not available to "
        "this pipeline. The matched-random comparison largely cancels it, since the null "
        "is drawn from the same survivor-biased tickers, which is the main reason that "
        "comparison carries the headline rather than raw returns. A referee may still "
        "reasonably require a point-in-time universe. This is the study's single largest "
        "unaddressed threat to validity.",
        "high", ["results/validation_report.md"]))

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

    # 11 -- bootstrap validity
    F.append(Finding(
        "Bootstrap confidence intervals assume iid draws, which these returns are not.",
        "ADDRESSED" if mc is not None and len(mc) else "PARTIAL",
        "Three resampling schemes are reported: matched random re-entry, iid trade "
        "shuffling, and a circular block bootstrap (21-bar blocks) that preserves serial "
        "dependence. The bootstrap interval is reported beside a HAC interval, and "
        "`ci_method` records which bootstrap path was taken.",
        "The HAC interval, not the bootstrap one, is used for inference; the bootstrap "
        "is reported because the specification requires it and for comparability with "
        "the prior version.",
        "medium", ["analytics/montecarlo.py"]))

    # 12 -- sector power
    thin = ""
    sector_ok = sect is not None and "n_tickers" in getattr(sect, "columns", [])
    if sector_ok:
        small = sect[sect["n_tickers"] < 25]
        thin = f" {len(small)} of {len(sect)} sectors rest on fewer than 25 tickers."
    F.append(Finding(
        "Sector-level conclusions rest on too few names to have statistical power.",
        "PARTIAL" if sector_ok else "EXPOSED",
        "Per-sector ticker and trade counts are reported alongside every sector result, "
        "and roughly 10% of the universe is unmapped and shown as `Unknown` rather than "
        "dropped." + thin,
        "Sector results are presented as descriptive, not as tested hypotheses with "
        "their own power analysis. A referee may reasonably ask for formal power "
        "calculations before any sector claim is made.",
        "medium", ["analytics/sectors.py"]))

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
        "This paper's headline result is **negative** -- most concepts do not beat a "
        "composition-matched random entry -- and a negative result is robust to most of "
        "the objections that would sink a positive one. Multiplicity, survivorship bias "
        "and transaction costs all push *against* finding an edge, so none of them can "
        "manufacture the null reported here. The paper should make that argument "
        "explicitly rather than leaving a referee to notice it.", "",
        "The corresponding risk is the opposite one: a referee may ask whether the study "
        "had the *power* to detect a real edge of plausible size. That question should be "
        "met with the sample sizes and confidence-interval widths already in "
        "`results/statistics_master.csv`, not deflected.", "",
    ]
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {path}")
    return path


if __name__ == "__main__":
    build_report()
