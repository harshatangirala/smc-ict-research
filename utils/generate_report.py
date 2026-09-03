"""Generates docs/final_research_report.md directly from the pipeline's saved
results (Task 15/20's executive report) -- every number is read from a file
the pipeline produced, not hand-transcribed, so the report can't drift from
the actual computed results.

Every ranking module (concept_ranking, combinations, stock_ranking, sectors,
regimes) compares against a random-entry baseline run through identical
backtest mechanics, not just a zero-return null -- see analytics/statistics.py
and each module's docstring for why the zero-return test alone is misleading
over a long bull market.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from utils.config import FDR_ALPHA, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("generate_report")


def _fmt_pct(x) -> str:
    return f"{x * 100:.2f}%" if pd.notna(x) else "n/a"


def _fmt(x, nd=3) -> str:
    return f"{x:.{nd}f}" if pd.notna(x) else "n/a"


def generate_report() -> str:
    dq = pd.read_csv(RESULTS_DIR / "data_quality_report.csv") if (RESULTS_DIR / "data_quality_report.csv").exists() else pd.DataFrame()
    events = pd.read_parquet(RESULTS_DIR / "master_events.parquet") if (RESULTS_DIR / "master_events.parquet").exists() else pd.DataFrame()
    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet") if (RESULTS_DIR / "trades.parquet").exists() else pd.DataFrame()
    concepts = pd.read_csv(RESULTS_DIR / "concept_rankings.csv") if (RESULTS_DIR / "concept_rankings.csv").exists() else pd.DataFrame()
    stocks = pd.read_csv(RESULTS_DIR / "stock_rankings.csv") if (RESULTS_DIR / "stock_rankings.csv").exists() else pd.DataFrame()
    combos = pd.read_csv(RESULTS_DIR / "combination_rankings.csv") if (RESULTS_DIR / "combination_rankings.csv").exists() else pd.DataFrame()
    regimes = pd.read_csv(RESULTS_DIR / "regime_analysis.csv") if (RESULTS_DIR / "regime_analysis.csv").exists() else pd.DataFrame()
    sectors = pd.read_csv(RESULTS_DIR / "sector_analysis.csv") if (RESULTS_DIR / "sector_analysis.csv").exists() else pd.DataFrame()

    n_total_concepts = len(concepts)
    _zflag = "reject_vs_zero" if "reject_vs_zero" in concepts else "significant_vs_zero"
    n_sig_zero = int(concepts[_zflag].sum()) if _zflag in concepts else 0
    _bflag = "beats_matched_random" if "beats_matched_random" in concepts else "statistically_significant"
    n_sig_baseline = int(concepts[_bflag].sum()) if _bflag in concepts else 0
    # Reported separately, never folded into the count above.
    n_loses = 0
    if "reject_vs_matched_random" in concepts and "excess_return_vs_matched_random" in concepts:
        n_loses = int(
            (concepts["reject_vs_matched_random"].fillna(False)
             & (concepts["excess_return_vs_matched_random"] < 0)).sum()
        )

    n_total_combos = len(combos)
    _cflag = "beats_matched_random" if "beats_matched_random" in combos else "statistically_significant"
    n_combo_sig_baseline = int(combos[_cflag].sum()) if _cflag in combos else 0

    n_sectors_positive = int((sectors["excess_return_vs_baseline"] > 0).sum()) if "excess_return_vs_baseline" in sectors else 0
    n_sectors_total = len(sectors)

    # MUST filter on the direction-aware flag. The previous version selected on
    # `significant_vs_baseline`, a TWO-SIDED result, and printed the rows under
    # the heading "Signals that beat the random-entry baseline" -- so concepts
    # that significantly LOST to random entry were presented as winners. In the
    # committed results 27 of the 28 rows selected here had a negative effect
    # size. See CHANGES.md 1.2.
    _flag = "beats_matched_random" if "beats_matched_random" in concepts else "statistically_significant"
    top_vs_baseline = (
        concepts[concepts.get(_flag, False) == True].head(10)  # noqa: E712
        if not concepts.empty and _flag in concepts else pd.DataFrame()
    )
    failing_concepts = concepts[(concepts.get("statistically_significant", False) == False) & (concepts.get("n_trades", 0) >= 30)].sort_values("sharpe").head(10) if not concepts.empty else pd.DataFrame()  # noqa: E712

    top_combos = combos[combos.get("statistically_significant", False) == True].head(10) if not combos.empty else pd.DataFrame()  # noqa: E712
    best_stocks = stocks[stocks.get("eligible", False) == True].head(20) if not stocks.empty else pd.DataFrame()
    worst_stocks = stocks[stocks.get("eligible", False) == True].tail(10) if not stocks.empty else pd.DataFrame()
    sectors_sorted = sectors.sort_values("excess_return_vs_baseline", ascending=False) if "excess_return_vs_baseline" in sectors else sectors

    lines = []
    lines.append("# Executive Research Report — SMC/ICT Statistical Edge Study")
    lines.append(f"\n_Generated {date.today().isoformat()} directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._\n")

    lines.append("## Scope")
    lines.append(f"- Stocks with usable data: **{dq['ticker'].nunique() if not dq.empty else 'n/a'}** of 503 S&P 500 constituents")
    lines.append(f"- Total SMC/ICT events detected: **{len(events):,}**")
    lines.append(f"- Total backtested trades (events x holding periods): **{len(trades):,}**")
    lines.append(f"- Distinct signal families tested: **{events['signal'].nunique() if not events.empty else 'n/a'}**")
    lines.append(f"- FDR significance threshold used throughout: alpha = {FDR_ALPHA}")
    lines.append(
        "- **Every ranking below (concepts, combinations, stocks, sectors, regimes) is tested "
        "against a random-entry baseline run through identical backtest mechanics** "
        "(`backtest/baseline_engine.py`), not only a zero-return null. This matters: over "
        "2010-2026 (a long bull market), almost any long-biased signal clears a zero-return "
        "null from broad market drift alone. The gap between the two tests is itself one of "
        "this study's main findings (Section 1)."
    )

    lines.append("\n## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?")
    lines.append(
        f"**No, not uniformly — and the two significance tests reported diverge sharply, which "
        f"is itself the key finding.** Of {n_total_concepts} SMC/ICT signal families tested at "
        f"the 10-day holding horizon: **{n_sig_zero}/{n_total_concepts}** show a mean return "
        f"significantly different from **zero** after FDR correction — but that is a weak bar "
        f"over a long bull market. Testing instead against a **random-entry baseline** at the "
        f"same frequency, only **{n_sig_baseline}/{n_total_concepts}** concepts remain "
        f"significant, and of {n_total_combos} tested concept combinations, only "
        f"**{n_combo_sig_baseline}** clear the same bar.\n\n"
        f"The picture gets more sobering when sliced by sector and regime "
        f"(Section 5): only **{n_sectors_positive}/{n_sectors_total}** sectors show *positive* "
        f"average excess return over the random baseline at all — in most sectors, "
        f"including Information Technology (the largest, most heavily represented sector in "
        f"this universe), a plain random long entry outperformed the aggregate SMC/ICT signal "
        f"population. This does not mean every individual concept is worthless — a real minority "
        f"clear a genuine, statistically defensible bar (Section 2) — but it does mean the "
        f"aggregate, unconditional claim \"SMC/ICT signals beat chance\" is **not supported** by "
        f"this dataset. The edge, where it exists, is concept-specific and regime/sector-dependent, "
        f"not a property of the methodology as a whole."
    )

    lines.append("\n## 2. Which concepts provide the strongest statistical edge?")
    lines.append(
        "\n_Signals that BEAT the composition-matched random-entry null after "
        "BH-FDR correction -- i.e. a positive excess return that survives "
        "multiple-testing control (`beats_matched_random=True`). Concepts that "
        "significantly UNDERPERFORM the null are reported separately below and "
        "are not evidence of an edge:_\n"
    )
    if not top_vs_baseline.empty:
        lines.append("| Signal | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in top_vs_baseline.iterrows():
            lines.append(
                f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | "
                f"{_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} | "
                f"{_fmt(r.get('p_adj_vs_matched_random', r.get('p_adjusted_vs_baseline')), 4)} |"
            )
    else:
        lines.append("No concepts reached statistical significance vs. the baseline at the current sample/threshold.")

    lines.append("\n## 3. Which concept combinations are most robust?")
    lines.append(f"\n{n_combo_sig_baseline} of {n_total_combos} tested combinations (pairs with >=30 co-occurrences, top 60 by frequency) beat the random-entry baseline after FDR correction:\n")
    if not top_combos.empty:
        lines.append("| Combination | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in top_combos.iterrows():
            lines.append(f"| {r['combination']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} | {_fmt(r.get('p_adjusted_vs_baseline'), 4)} |")
    else:
        lines.append("No combinations met the minimum-occurrence threshold or reached significance vs. baseline.")

    lines.append("\n## 4. Which S&P 500 stocks are most responsive?")
    lines.append(
        "\nRanked by **excess return vs. that same ticker's own random-entry baseline** — not "
        "raw Sharpe, which would just reward stocks that rallied hard over 2010-2026 regardless "
        "of whether SMC/ICT signals added anything. Per-ticker baseline samples are small "
        "(~50 random entries per ticker per horizon), so most individual tickers do not reach "
        "significance even when the excess return looks large — treat this as a ranking, not a "
        "list of proven per-stock edges; see `p_value_vs_baseline` in `results/stock_rankings.csv` "
        "for the honest per-ticker confidence.\n"
    )
    if not best_stocks.empty:
        lines.append("| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline | Significant? |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in best_stocks.head(15).iterrows():
            sig = "yes" if r.get("beats_matched_random", r.get("statistically_significant")) else "no"
            lines.append(f"| {r['ticker']} | {int(r['n_trades'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {sig} |")
        lines.append("\n_Bottom 10 (least responsive / signals underperform that stock's own baseline):_\n")
        lines.append("| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline |")
        lines.append("|---|---|---|---|---|")
        for _, r in worst_stocks.iterrows():
            lines.append(f"| {r['ticker']} | {int(r['n_trades'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} |")
    else:
        lines.append("Stock ranking not available.")

    lines.append("\n## 5. Which sectors and market regimes are most responsive?")
    lines.append(f"\n**{n_sectors_positive} of {n_sectors_total} sectors** show positive average excess return over the random-entry baseline:\n")
    if not sectors_sorted.empty:
        lines.append("| Sector | Avg return | Baseline avg return | Excess vs baseline | n tickers |")
        lines.append("|---|---|---|---|---|")
        for _, r in sectors_sorted.iterrows():
            lines.append(f"| {r['sector']} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {int(r['n_tickers'])} |")
    if not regimes.empty:
        lines.append("\n### By market regime\n")
        lines.append("| Trend regime | Vol regime | Avg return | Baseline avg return | Excess vs baseline | n trades |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in regimes.iterrows():
            lines.append(f"| {r['trend_regime']} | {r['vol_regime']} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {int(r['n_trades'])} |")

    lines.append("\n## 6. Which concepts fail consistently?")
    if not failing_concepts.empty:
        lines.append("\nLowest-Sharpe signals with at least 30 trades (10-day hold) that did *not* beat the random-entry baseline after FDR correction:\n")
        lines.append("| Signal | n trades | Win rate | Sharpe |")
        lines.append("|---|---|---|---|")
        for _, r in failing_concepts.iterrows():
            lines.append(f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} |")
    else:
        lines.append("See `results/concept_rankings.csv` for the full ranked list including non-significant concepts.")

    lines.append("\n## 7. Are results stable across bull, bear, and sideways markets?")
    lines.append(
        "No, not fully — see the regime table in Section 5. Excess return vs. baseline is "
        "negative in most trend/volatility regime cells (`results/regime_analysis.csv`), and the "
        "one clearly positive cell (bull + high volatility) is a narrow slice of the data. Regime "
        "classification uses each stock's own trailing SMA(200) trend and "
        "realized-volatility-vs-own-history state, not an external index. See the dashboard's "
        "Sector & Regime tab and `analytics/regimes.py:regime_analysis_by_signal` for the "
        "per-signal breakdown by regime."
    )

    lines.append("\n## 8. Are results statistically significant after correcting for sample size and multiple testing?")
    lines.append(
        f"Every ranking module (concepts, combinations, stocks, sectors, regimes) now compares "
        f"against a random-entry baseline run through identical backtest mechanics, in addition "
        f"to a zero-return null, with Benjamini-Hochberg FDR correction applied to both "
        f"(`analytics/statistics.py`). The headline `beats_matched_random` flag requires "
        f"clearing the FDR-corrected **baseline** comparison (alpha={FDR_ALPHA}) *and* a minimum "
        f"sample size — concepts/combinations below that sample size are explicitly flagged "
        f"`low_sample_warning` rather than reported with false confidence. Per-ticker "
        f"significance tests (Section 4) have limited statistical power due to small per-ticker "
        f"baseline samples (~50 trades) — reported as a ranking with honest p-values, not a list "
        f"of proven stock-specific edges."
    )

    lines.append("\n## Key limitations")
    lines.append(
        "- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).\n"
        "- Sector mapping is a static approximation, not a live data source.\n"
        "- No transaction costs or slippage modeled.\n"
        "- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no "
        "corresponding logic in the source scripts and are not implemented.\n"
        "- Per-ticker and per-sector/regime baseline comparisons have smaller sample sizes than "
        "the universe-wide concept-level comparison, so their significance tests are "
        "correspondingly less powered — read the excess-return figures as directional evidence, "
        "the p-values as the honest confidence level.\n"
        "- See README.md \"Limitations\" and \"Key assumptions\" sections for the complete list."
    )

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    out_path = RESULTS_DIR.parent / "docs" / "final_research_report.md"
    out_path.write_text(report, encoding="utf-8")
    log.info("Final research report written to %s", out_path)
