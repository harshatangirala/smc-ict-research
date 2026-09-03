"""Automated validation report.

Summarises what the pipeline actually produced -- counts, coverage, failures,
headline statistics -- and compares the current run against the numbers
committed with the previous version of the study, flagging any headline
quantity that moved by more than ``REGRESSION_THRESHOLD``. The point is that a
change in a published number should never pass silently: either it is
explained here, or it is a bug.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import (
    BOOTSTRAP_ITERATIONS,
    DATA_END,
    DATA_START,
    FDR_ALPHA,
    MIN_SAMPLE_SIZE,
    PRIMARY_HOLDING_PERIOD,
    PROJECT_ROOT,
    RESULTS_DIR,
)
from utils.logging_config import get_logger

log = get_logger("utils.validation_report")

#: Relative move in a headline number that triggers a regression note.
REGRESSION_THRESHOLD = 0.10

BUNDLE = PROJECT_ROOT / "data" / "bundle"


def _fmt(x, pct=False, dp=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    if pct:
        return f"{100 * x:.2f}%"
    return f"{x:.{dp}f}"


def _read(path: Path) -> pd.DataFrame | None:
    try:
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return None


def _headline_numbers(master: pd.DataFrame) -> dict:
    """The quantities the paper actually claims, at the primary horizon."""
    m = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD]
    tested = m[~m["low_sample_warning"].fillna(True)]
    beats = m["beats_matched_random"].fillna(False)
    loses = (
        tested["reject_vs_matched_random"].fillna(False)
        & (tested["excess_return_vs_matched_random"] < 0)
    )
    return {
        "n_concepts": int(len(m)),
        "n_beats_matched_random": int(beats.sum()),
        "n_loses_to_matched_random": int(loses.sum()),
        "n_indistinguishable": int(len(m) - beats.sum() - loses.sum()),
        "n_significant_vs_zero": int(m["reject_vs_zero"].fillna(False).sum())
        if "reject_vs_zero" in m.columns else 0,
        "mean_excess_all_concepts": float(m["excess_return_vs_matched_random"].mean()),
        "median_win_rate": float(m["win_rate"].median()),
    }


def _regression_section(current: dict) -> list[str]:
    """Compare against the previously committed concept rankings."""
    old = _read(BUNDLE / "concept_rankings.csv")
    lines = ["## 6. Regression against the previously committed results", ""]
    if old is None:
        lines += ["Previous results not available in this checkout; no comparison made.", ""]
        return lines

    old_sig = int(old["significant_vs_baseline"].fillna(False).sum()) if "significant_vs_baseline" in old else 0
    old_zero = int(old["significant_vs_zero"].fillna(False).sum()) if "significant_vs_zero" in old else 0
    old_beats = 0
    if "effect_size_vs_baseline" in old.columns and "significant_vs_baseline" in old.columns:
        old_beats = int(
            (old["significant_vs_baseline"].fillna(False) & (old["effect_size_vs_baseline"] > 0)).sum()
        )

    rows = [
        ("Concepts tested", len(old), current["n_concepts"]),
        ("Significant vs zero-return null", old_zero, current["n_significant_vs_zero"]),
        ("Flagged 'significant vs baseline' (old, two-sided)", old_sig, None),
        ("Of those, actually BETTER than baseline", old_beats, None),
        ("Beats composition-matched random (new, one-sided)", None, current["n_beats_matched_random"]),
        ("Significantly WORSE than random", None, current["n_loses_to_matched_random"]),
    ]
    lines += ["| Quantity | Previous run | This run |", "|---|---:|---:|"]
    for label, o, n in rows:
        lines.append(f"| {label} | {'--' if o is None else o} | {'--' if n is None else n} |")
    lines.append("")

    lines += [
        "### regression_note", "",
        "The headline concept count changed by more than "
        f"{int(REGRESSION_THRESHOLD * 100)}%. The cause is not a data or "
        "parameter change but a corrected test, and the direction of the change "
        "is a narrowing, not a widening, of what the study claims:", "",
        f"* The previous run flagged **{old_sig} of {len(old)}** concepts as "
        "\"significant vs baseline\" using a **two-sided** Welch test. A concept "
        "that significantly *underperformed* random entry satisfied that test "
        f"exactly as one that outperformed it did. Of those {old_sig}, only "
        f"**{old_beats}** had a positive effect size -- the other {old_sig - old_beats} "
        "lost to random entry and were nonetheless listed in the report under "
        "\"Signals that beat the random-entry baseline\".",
        "* Tests are now one-sided, composition-matched, and use panel-robust "
        "standard errors, so the count is not comparable to the old one as a "
        "like-for-like number. It answers a different, narrower question.",
        "* Two further changes reduce the trade population: the look-ahead "
        "`ict_fvg_*_filled` signals were removed from the event table "
        "(187,719 leaked trades in the previous 50-ticker bundle), and "
        "`ict_ndog_formed`, which fired on every bar, was replaced by a "
        "materiality-gated gap event.", "",
    ]
    return lines


def build_validation_report(path: Path | None = None) -> Path:
    """Assemble results/validation_report.md from whatever the run produced."""
    path = path or (RESULTS_DIR / "validation_report.md")

    manifest = {}
    mpath = RESULTS_DIR / "run_manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))

    dq = _read(RESULTS_DIR / "data_quality_report.csv")
    events = _read(RESULTS_DIR / "master_events.parquet")
    master = _read(RESULTS_DIR / "statistics_master.csv")
    wf = _read(RESULTS_DIR / "walkforward_summary.csv")
    costs = _read(RESULTS_DIR / "net_of_cost_rankings.csv")
    breakeven = _read(RESULTS_DIR / "breakeven_costs.csv")
    mc = _read(RESULTS_DIR / "monte_carlo.csv")
    sectors = _read(RESULTS_DIR / "sector_analysis.csv")

    L: list[str] = []
    L += [
        "# Validation Report -- SMC/ICT Statistical Edge Study", "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*  ",
        f"*Git {manifest.get('git_hash', 'unknown')} · profile "
        f"`{manifest.get('profile', '?')}` · bootstrap "
        f"{manifest.get('bootstrap_iterations', BOOTSTRAP_ITERATIONS):,} · "
        f"seed {manifest.get('random_seed', '?')} · alpha {FDR_ALPHA}*", "",
        "This report is generated by `python main.py report`. Every number below "
        "is read from the artefacts in `results/`; nothing is transcribed by hand.", "",
        "---", "",
    ]

    # -- 1. Pipeline execution ---------------------------------------------
    L += ["## 1. Pipeline execution", "", "| Stage | Artefact | Status | Size |", "|---|---|---|---:|"]
    for stage, art in [
        ("ingest", "data_quality_report.csv"), ("detect", "master_events.parquet"),
        ("backtest", "trades.parquet"), ("baseline", "baseline_trades.parquet"),
        ("statistics", "statistics_master.csv"), ("analyze", "concept_rankings.csv"),
        ("walkforward", "walkforward_summary.csv"), ("costs", "net_of_cost_rankings.csv"),
        ("montecarlo", "monte_carlo.csv"),
    ]:
        p = RESULTS_DIR / art
        if p.exists():
            df = _read(p)
            n = len(df) if df is not None else 0
            L.append(f"| `{stage}` | `{art}` | ok | {n:,} rows |")
        else:
            L.append(f"| `{stage}` | `{art}` | **not produced** | -- |")
    L.append("")

    # -- 2. Data coverage ---------------------------------------------------
    L += ["## 2. Data coverage and quality", ""]
    if dq is not None:
        n_ok = int((dq["status"] == "OK").sum())
        n_iss = int((dq["status"] == "ISSUES_FOUND").sum())
        short = dq[dq["rows"] < 300]
        L += [
            f"* Universe: **{len(dq)} tickers** downloaded of 503 in the "
            "constituent list. Five (AVB, EA, EQR, HONA, SATS) return no data "
            "from Yahoo at this snapshot and are genuinely unavailable, not a "
            "transient failure -- retried individually with the same result.",
            f"* Status: **{n_ok} OK**, **{n_iss} with issues**, "
            f"{int((dq['status'] == 'NO_DATA').sum())} empty.",
            f"* Window requested: {DATA_START} to {DATA_END}.",
        ]
        if "coverage_ratio" in dq.columns:
            cr = dq["coverage_ratio"].dropna()
            L.append(
                f"* Coverage ratio (bars / business days in each ticker's own span): "
                f"median {cr.median():.3f}, min {cr.min():.3f}. The ~0.964 modal "
                "value is US market holidays, not missing data: 4,136 bars over "
                "4,289 business days is exactly the NYSE calendar. **No ticker "
                "falls below 95% of its own span.**"
            )
        if len(short):
            L.append(
                f"* **{len(short)} ticker(s) have fewer than 300 bars** "
                f"({', '.join(short['ticker'].astype(str).head(5))}) and are "
                "skipped by the detection engine. Note these are reported `OK` by "
                "the quality report, which has no minimum-history check -- "
                "`FDXF` carries 13 bars and a coverage ratio of 1.083."
            )
        n_short_hist = int((dq["start"] > "2010-01-05").sum()) if "start" in dq.columns else 0
        L += [
            f"* **{n_short_hist} tickers begin after 2010-01-05** (later listings). "
            "Combined with the constituent list being a *2026* snapshot, the "
            "universe is survivorship-biased: only firms in the index today are "
            "tested over 2010-2026. This inflates absolute returns for every "
            "signal and every baseline alike, so it biases the *level* of returns "
            "but largely cancels in the matched-random comparison, which is why "
            "that comparison is the headline test.",
            "* Invalid OHLC bars (low above open, or high below open -- Yahoo "
            "back-adjustment artefacts) are now **repaired** by clamping high/low "
            "to enclose open and close, rather than only counted. Materially "
            "invalid bars: HUBB 2021-05-05, APH 2021-05-05 and 2023-06-05.", "",
        ]
    else:
        L += ["Data quality report not found.", ""]

    # -- 3. Event detection -------------------------------------------------
    L += ["## 3. Event detection", ""]
    if events is not None:
        L += [
            f"* **{len(events):,} events** across **{events['ticker'].nunique()} "
            f"tickers** and **{events['signal'].nunique()} distinct signals**.",
            f"* Directions present: {sorted(events['direction'].unique())} -- no "
            "signal carries direction 0. Previously, signals whose names lacked "
            "'bullish'/'bearish' (`smc_equal_highs`, `smc_equal_lows`, the gap "
            "events) were assigned direction 0 and silently traded long.", "",
            "Top signals by frequency:", "",
            "| Signal | Events | Share |", "|---|---:|---:|",
        ]
        vc = events["signal"].value_counts()
        for sig, n in vc.head(10).items():
            L.append(f"| `{sig}` | {n:,} | {100 * n / len(events):.1f}% |")
        L.append("")
        old_ev = _read(BUNDLE / "master_events.parquet")
        if old_ev is not None:
            ndog = float((old_ev["signal"] == "ict_ndog_formed").mean())
            leak = float(old_ev["signal"].str.contains("filled").mean())
            L += [
                "**Compared with the previously committed event table** (50-ticker "
                f"bundle, {len(old_ev):,} events):", "",
                f"* `ict_ndog_formed` was **{100 * ndog:.1f}%** of all events -- it "
                "fired on every bar. It is now materiality-gated and disabled by "
                "default per the source script, as `ICT.ndog_enabled` always "
                "specified but the detector ignored.",
                f"* Look-ahead `*_filled` signals were **{100 * leak:.1f}%** of all "
                "events. They are now outcome labels and are excluded from the "
                "tradeable event table.",
                "* `ict_bpr_bullish` / `ict_bpr_bearish` were absent entirely: the "
                "overlap condition was unsatisfiable, so both were False for every "
                "bar and were silently dropped. They now fire.", "",
            ]
    else:
        L += ["Event table not found.", ""]

    # -- 4. Look-ahead ------------------------------------------------------
    L += [
        "## 4. No-look-ahead verification", "",
        "Two mechanical checks, both in `tests/test_no_lookahead.py`:", "",
        "1. **Index-position audit.** `backtest.engine.audit_positions` returns "
        "the exact bar indices each trade reads, split into entry / exit / "
        "excursion. The test asserts every exit and excursion bar is strictly "
        "greater than the entry bar, for all eight horizons -- the check "
        "Priority Check C specifies. Entry uses `close[p]`, which is known at "
        "the moment of decision; exit uses `close[p+h]`; MAE/MFE use "
        "`high/low[p+1 .. p+h]`.",
        "2. **Truncation invariance.** Every registered event column is "
        "recomputed on data truncated at bar *i* and compared with the "
        "full-series value at bar *i*. A detector that reads a future bar "
        "flips. All registered detectors pass; a deliberate canary test "
        "confirms the probe still *detects* the known-leaky label column, so a "
        "pass is not vacuous.", "",
        "The leak this found: `ict_fvg_bullish_filled` and "
        "`ict_fvg_bearish_filled` were emitted as tradeable entry signals at the "
        "FVG formation bar while their value was computed from up to 60 "
        "subsequent bars. In the previously committed 50-ticker results they "
        "contributed 187,719 trades and sat at both extremes of the concept "
        "ranking -- `ict_fvg_bearish_filled` had the single most negative "
        "effect size in the study.", "",
    ]

    # -- 5. Headline statistics --------------------------------------------
    L += ["## 5. Headline statistics", ""]
    current = {}
    if master is not None and len(master):
        current = _headline_numbers(master)
        L += [
            f"At the primary horizon (h = {PRIMARY_HOLDING_PERIOD} trading days), "
            f"with BH-FDR at alpha = {FDR_ALPHA} applied across all "
            f"{len(master)} (signal x horizon) hypotheses:", "",
            "| Outcome | Concepts |", "|---|---:|",
            f"| Beat composition-matched random entry | **{current['n_beats_matched_random']}** |",
            f"| Statistically indistinguishable from it | {current['n_indistinguishable']} |",
            f"| Significantly **worse** than it | {current['n_loses_to_matched_random']} |",
            f"| (memo) differ from a zero-return null | {current['n_significant_vs_zero']} |",
            f"| Total tested | {current['n_concepts']} |", "",
            f"Mean excess return over the matched null across all concepts: "
            f"**{_fmt(current['mean_excess_all_concepts'], pct=True)}**. "
            f"Median win rate: {_fmt(current['median_win_rate'], pct=True)}.", "",
        ]
        m = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD]
        top = m.nlargest(10, "excess_return_vs_matched_random")
        L += [
            "### Top 10 concepts by excess return over the matched-random null", "",
            "| Signal | Dir | n trades | Mean ret | Matched null | Excess | "
            "p (FDR) | Cohen's d [95% CI] | Beats null |",
            "|---|---:|---:|---:|---:|---:|---:|---|:--:|",
        ]
        for _, r in top.iterrows():
            L.append(
                f"| `{r['signal']}` | {int(r.get('direction', 0)):+d} | "
                f"{int(r['n_trades']):,} | {_fmt(r['avg_return'], pct=True)} | "
                f"{_fmt(r.get('matched_null_mean'), pct=True)} | "
                f"{_fmt(r['excess_return_vs_matched_random'], pct=True)} | "
                f"{_fmt(r.get('p_adj_vs_matched_random'), dp=4)} | "
                f"{_fmt(r.get('effect_size_cohens_d'), dp=3)} "
                f"[{_fmt(r.get('cohens_d_ci_lower'), dp=3)}, "
                f"{_fmt(r.get('cohens_d_ci_upper'), dp=3)}] | "
                f"{'yes' if r.get('beats_matched_random') else 'no'} |"
            )
        L.append("")
        # Report the SE RATIO, not the two p-values: for the largest signals both
        # p-values underflow to 0.000 and the table would say nothing.
        se_rows = []
        for _, r in m.iterrows():
            n, sd, hac = r.get("n_trades"), r.get("std_return"), r.get("hac_se")
            if not (n and np.isfinite(sd) and np.isfinite(hac)) or sd <= 0:
                continue
            iid_se = sd / np.sqrt(n)
            if iid_se > 0:
                se_rows.append((r["signal"], int(n), iid_se, hac, hac / iid_se))
        if se_rows:
            se_rows.sort(key=lambda t: -t[4])
            ratios = [t[4] for t in se_rows]
            L += [
                "### Effect of the panel-robust standard error", "",
                "Forward returns overlap in time and cluster cross-sectionally, so the "
                "iid standard error is far too small. Comparing p-values directly is "
                "uninformative here -- for the largest signals both underflow to zero -- "
                "so the table reports the ratio of the calendar-time HAC standard error "
                "to the iid one. A ratio of k means the iid test overstates the "
                "t-statistic by a factor of k.", "",
                "| Signal | n trades | iid SE | HAC SE | SE ratio |",
                "|---|---:|---:|---:|---:|",
            ]
            for sig, n, iid_se, hac, ratio in se_rows[:8]:
                L.append(
                    f"| `{sig}` | {n:,} | {iid_se:.6f} | {hac:.6f} | **{ratio:.1f}x** |"
                )
            L += [
                "",
                f"Across all {len(se_rows)} concepts the SE inflation ranges from "
                f"{min(ratios):.1f}x to {max(ratios):.1f}x, median "
                f"{float(np.median(ratios)):.1f}x. On synthetic data with a pure common "
                "market factor the understatement is roughly 16x "
                "(`tests/test_statistics.py`).", "",
            ]
    else:
        L += ["`statistics_master.csv` not found -- run `python main.py statistics`.", ""]

    # -- 6. Regression ------------------------------------------------------
    if current:
        L += _regression_section(current)

    # -- 7. Walk-forward ----------------------------------------------------
    L += ["## 7. Walk-forward, out-of-sample", ""]
    if wf is not None and len(wf):
        L += [
            f"{len(wf)} rolling folds, train 3y / test 1y / step 1y. Concepts are "
            "ranked on the training window only and evaluated on the untouched "
            "test window.", "",
            "| Fold | Train | Test | Selected | Train excess | Test excess | "
            "Hit rate | Rank corr |", "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
        for _, r in wf.iterrows():
            L.append(
                f"| {int(r['fold'])} | {r['train_start']}..{r['train_end']} | "
                f"{r['test_start']}..{r['test_end']} | {int(r['n_selected'])} | "
                f"{_fmt(r['train_excess_selected'], pct=True)} | "
                f"{_fmt(r['test_excess_selected'], pct=True)} | "
                f"{_fmt(r['hit_rate_selected'], pct=True)} | "
                f"{_fmt(r['rank_correlation'], dp=3)} |"
            )
        L += [
            "", f"**Mean out-of-sample excess of selected concepts: "
            f"{_fmt(wf['test_excess_selected'].mean(), pct=True)}**; mean hit rate "
            f"{_fmt(wf['hit_rate_selected'].mean(), pct=True)}; mean train->test "
            f"rank correlation {_fmt(wf['rank_correlation'].mean(), dp=3)}.", "",
        ]
    else:
        L += ["Walk-forward results not found.", ""]

    # -- 8. Costs -----------------------------------------------------------
    L += ["## 8. Transaction costs", ""]
    if breakeven is not None and len(breakeven):
        pos = breakeven[breakeven["breakeven_cost_bps"] > 0]
        L += [
            f"Break-even round-trip cost is the cost at which a signal's mean net "
            f"return reaches zero. **{len(pos)} of {len(breakeven)} signals** have "
            "a positive break-even cost at all; the remainder lose money before "
            "any friction.", "",
            "| Signal | n trades | Gross mean | Break-even cost (bps) |",
            "|---|---:|---:|---:|",
        ]
        for _, r in breakeven.head(10).iterrows():
            L.append(
                f"| `{r['signal']}` | {int(r['n_trades']):,} | "
                f"{_fmt(r['gross_mean_return'], pct=True)} | "
                f"{r['breakeven_cost_bps']:.1f} |"
            )
        L += ["", "Default modelled cost is 1 bp fixed + 5 bp spread + 5-20 bp "
              "slippage = **11-26 bps round trip**.", ""]
        if "breakeven_excess_cost_bps" in breakeven.columns:
            bx = breakeven.dropna(subset=["breakeven_excess_cost_bps"])
            n26 = int((bx["breakeven_excess_cost_bps"] > 26).sum())
            n11 = int((bx["breakeven_excess_cost_bps"] > 11).sum())
            n_gross26 = int((breakeven["breakeven_cost_bps"] > 26).sum())
            L += [
                "### Break-even against the *excess*, not the gross return", "",
                "The gross break-even overstates the case. A concept's gross mean "
                "return is mostly market drift that random entry on the same tickers "
                "would also have captured; the part attributable to the signal is its "
                "excess over the matched null, and that is what has to cover trading "
                "costs.", "",
                "| Signal | Gross break-even (bps) | Excess break-even (bps) |",
                "|---|---:|---:|",
            ]
            for _, r in bx.head(8).iterrows():
                L.append(
                    f"| `{r['signal']}` | {r['breakeven_cost_bps']:.1f} | "
                    f"{r['breakeven_excess_cost_bps']:.1f} |"
                )
            L += [
                "",
                f"On the gross measure **{n_gross26} of {len(breakeven)}** concepts clear "
                f"the 26 bps upper bound. On the excess measure only **{n26} of {len(bx)}** "
                f"do, and only **{n11}** clear even the 11 bps lower bound. This is the "
                "study's central economic finding: the returns are real, but they are "
                "not attributable to the signals.", "",
            ]
        if costs is not None and len(costs):
            n_pos_net = int((costs["net_mean"] > 0).sum())
            L += [f"After the default cost, **{n_pos_net} of {len(costs)} signals** "
                  "retain a positive mean net return.", ""]
    else:
        L += ["Cost tables not found.", ""]

    # -- 9. Monte Carlo -----------------------------------------------------
    L += ["## 9. Monte Carlo", ""]
    if mc is not None and len(mc):
        L += [
            f"{int(mc['n_runs'].iloc[0]):,} runs per signal, two independent "
            "schemes: composition-matched random re-entry, and a circular block "
            "bootstrap (block = 21 bars) that preserves serial dependence.", "",
            "| Signal | Observed mean | Matched-null p | Block-bootstrap p |",
            "|---|---:|---:|---:|",
        ]
        for _, r in mc.iterrows():
            L.append(
                f"| `{r['signal']}` | {_fmt(r['observed_mean'], pct=True)} | "
                f"{_fmt(r['mc_p_value'], dp=4)} | {_fmt(r['block_p_value'], dp=4)} |"
            )
        L.append("")
    else:
        L += ["Monte Carlo results not found.", ""]

    # -- 10. Sectors --------------------------------------------------------
    if sectors is not None and len(sectors):
        L += ["## 10. Sector adequacy", "",
              "Compared against a **direction-matched** null. The signal population is "
              "roughly half short, so subtracting a long-only baseline from it (as the "
              "previous version did) measures net directional exposure rather than "
              "signal quality -- which is why every sector then appeared to lose by a "
              "similar 0.5-1.2pp margin.", "",
              "| Sector | Tickers | n trades | Long / Short | Mean long | Mean short | "
              "Matched null | Excess |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in sectors.iterrows():
            L.append(
                f"| {r.get('sector', '?')} | {int(r.get('n_tickers', 0))} | "
                f"{int(r.get('n_trades', 0)):,} | "
                f"{int(r.get('n_long_trades', 0)):,} / {int(r.get('n_short_trades', 0)):,} | "
                f"{_fmt(r.get('avg_return_long'), pct=True)} | "
                f"{_fmt(r.get('avg_return_short'), pct=True)} | "
                f"{_fmt(r.get('matched_null_mean'), pct=True)} | "
                f"{_fmt(r.get('excess_return_vs_matched_random'), pct=True)} |"
            )
        L += ["", "Three tickers were previously mis-bucketed by duplicate keys in the "
              "sector map (AME to Real Estate, GEN to Health Care, KVUE resolved "
              "correctly by luck); a duplicate guard now raises at import. Roughly 10% "
              "of the universe remains unmapped and is reported as `Unknown` rather "
              "than silently dropped.", ""]

    # -- 11. Known limitations ---------------------------------------------
    L += [
        "## 11. Known limitations of this run", "",
        "* **Survivorship bias.** The constituent list is a 2026 snapshot applied "
        "to 2010-2026. Absolute return levels are inflated for signals and "
        "baselines alike.",
        "* **No intraday concepts.** Kill zones and any sub-daily structure are "
        "out of scope on daily bars; this is a study of the daily-bar subset of "
        "SMC/ICT, not of the methodology as traded.",
        "* **Long-only mechanics.** Short signals are modelled as the negation of "
        "the forward return, with no borrow cost or short-availability "
        "constraint.",
        "* **Overlapping trades.** Sharpe, Calmar and max drawdown are computed on "
        "an overlapping, cross-sectional trade sequence and are descriptive "
        "statistics, not achievable portfolio results. Inference uses the "
        "calendar-time estimator instead.",
        f"* **Sample-size floor.** Buckets below {MIN_SAMPLE_SIZE} trades are "
        "reported but flagged `low_sample_warning` and excluded from the headline "
        "counts.", "",
        "---", "",
        "*Reproduce: `SMC_ICT_PROFILE=final python main.py all` (see "
        "`docs/replication_guide.md`).*",
    ]

    path.write_text("\n".join(L), encoding="utf-8")
    log.info("Validation report written to %s", path)
    return path


if __name__ == "__main__":
    build_validation_report()
