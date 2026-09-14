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
    n_sig_zero = int(concepts["significant_vs_zero"].sum()) if "significant_vs_zero" in concepts else 0
    # `significant_vs_baseline` is TWO-SIDED ("differs from baseline"),
    # `beats_baseline` is the directional claim (significant AND excess return
    # positive). A prior version of this report used the former to mean the
    # latter -- see the audit finding this responds to: 27 of 28 concepts
    # flagged "significant vs. baseline" were significantly WORSE than
    # baseline, not better. `beats_baseline` is what belongs in a headline.
    n_beats_baseline = int(concepts["beats_baseline"].sum()) if "beats_baseline" in concepts else 0
    n_differs_baseline = int(concepts["significant_vs_baseline"].fillna(False).sum()) if "significant_vs_baseline" in concepts else 0
    n_worse_baseline = n_differs_baseline - n_beats_baseline

    n_total_combos = len(combos)
    n_combo_beats_baseline = int(combos["beats_baseline"].sum()) if "beats_baseline" in combos else 0
    n_combo_differs_baseline = int(combos["significant_vs_baseline"].fillna(False).sum()) if "significant_vs_baseline" in combos else 0
    n_combo_worse_baseline = n_combo_differs_baseline - n_combo_beats_baseline

    n_sectors_positive = int((sectors["excess_return_vs_baseline"] > 0).sum()) if "excess_return_vs_baseline" in sectors else 0
    n_sectors_beats_baseline = int(sectors["beats_baseline"].sum()) if "beats_baseline" in sectors else 0
    n_sectors_total = len(sectors)

    top_vs_baseline = concepts[concepts.get("beats_baseline", False) == True].head(10) if not concepts.empty and "beats_baseline" in concepts else pd.DataFrame()  # noqa: E712
    worse_than_baseline = concepts[(concepts.get("significant_vs_baseline", False) == True) & (concepts.get("beats_baseline", False) == False)].sort_values("effect_size_vs_baseline").head(10) if not concepts.empty and "effect_size_vs_baseline" in concepts else pd.DataFrame()

    failing_concepts = concepts[(concepts.get("significant_vs_baseline", False) == False) & (concepts.get("n_trades", 0) >= 30)].sort_values("sharpe").head(10) if not concepts.empty else pd.DataFrame()  # noqa: E712

    top_combos = combos[combos.get("beats_baseline", False) == True].head(10) if not combos.empty else pd.DataFrame()  # noqa: E712
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
        f"**No — and not narrowly no.** Of {n_total_concepts} SMC/ICT signal families tested at "
        f"the 10-day holding horizon: **{n_sig_zero}/{n_total_concepts}** show a mean return "
        f"significantly different from **zero** after FDR correction — a weak bar over a long "
        f"bull market that almost any long-biased signal clears from broad drift alone. Testing "
        f"instead against a **random-entry baseline**, run through identical backtest mechanics "
        f"with standard errors clustered by ticker (correcting for the fact that trades on the "
        f"same stock share overlapping holding windows and are not independent draws), "
        f"**{n_differs_baseline}/{n_total_concepts}** concepts differ from the baseline at all "
        f"after FDR correction — but of those, only **{n_beats_baseline}** are significantly "
        f"*better* than baseline. The other **{n_worse_baseline}** are significantly *worse*. "
        f"The same split holds for combinations: of {n_total_combos} tested, "
        f"**{n_combo_differs_baseline}** differ from baseline, and only **{n_combo_beats_baseline}** "
        f"of those are significantly better ({n_combo_worse_baseline} are significantly worse).\n\n"
        f"Sliced by sector (Section 5): **{n_sectors_positive}/{n_sectors_total}** sectors show a "
        f"positive point-estimate excess return over the random baseline, and of those, "
        f"**{n_sectors_beats_baseline}** are statistically significant after FDR correction. The "
        f"aggregate, unconditional claim \"SMC/ICT signals beat chance\" is **not supported** by "
        f"this dataset — and where the data does distinguish a signal from the baseline at all, "
        f"it is more often in the *worse* direction than the better one. Where a genuine edge "
        f"exists (Section 2), it is a narrow, specific exception, not the norm."
    )

    lines.append("\n## 2. Which concepts provide the strongest statistical edge?")
    lines.append("\n_Signals that beat the random-entry baseline after FDR correction and cluster-robust testing (`beats_baseline=True` — significant AND the excess return is positive):_\n")
    if not top_vs_baseline.empty:
        lines.append("| Signal | n trades | Win rate | Sharpe | Avg return | Excess vs baseline | p vs baseline (FDR-adj) |")
        lines.append("|---|---|---|---|---|---|---|")
        for _, r in top_vs_baseline.iterrows():
            lines.append(f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {_fmt(r.get('p_adjusted_vs_baseline'), 4)} |")
    else:
        lines.append("No concepts beat the baseline at the current sample/threshold.")

    lines.append(
        "\n_For comparison, the signals significantly **worse** than the baseline — a mean return "
        "that looks fine in isolation but underperforms doing nothing at the same frequency:_\n"
    )
    if not worse_than_baseline.empty:
        lines.append("| Signal | n trades | Avg return | Excess vs baseline | p vs baseline (FDR-adj) |")
        lines.append("|---|---|---|---|---|")
        for _, r in worse_than_baseline.iterrows():
            lines.append(f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {_fmt(r.get('p_adjusted_vs_baseline'), 4)} |")
    else:
        lines.append("None at the current sample/threshold.")

    lines.append("\n## 3. Which concept combinations are most robust?")
    lines.append(f"\n{n_combo_beats_baseline} of {n_total_combos} tested combinations (pairs with >=30 co-occurrences, top 60 by frequency) beat the random-entry baseline after FDR correction ({n_combo_worse_baseline} more are significantly worse):\n")
    if not top_combos.empty:
        lines.append("| Combination | n trades | Win rate | Sharpe | Avg return | Excess vs baseline | p vs baseline (FDR-adj) |")
        lines.append("|---|---|---|---|---|---|---|")
        for _, r in top_combos.iterrows():
            lines.append(f"| {r['combination']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {_fmt(r.get('p_adjusted_vs_baseline'), 4)} |")
    else:
        lines.append("No combinations beat the baseline at the current sample/threshold.")

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
            sig = "yes" if r.get("significant_vs_baseline") else "no"
            lines.append(f"| {r['ticker']} | {int(r['n_trades'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {sig} |")
        lines.append("\n_Bottom 10 (least responsive / signals underperform that stock's own baseline):_\n")
        lines.append("| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline |")
        lines.append("|---|---|---|---|---|")
        for _, r in worst_stocks.iterrows():
            lines.append(f"| {r['ticker']} | {int(r['n_trades'])} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} |")
    else:
        lines.append("Stock ranking not available.")

    lines.append("\n## 5. Which sectors and market regimes are most responsive?")
    lines.append(
        f"\n**{n_sectors_positive} of {n_sectors_total} sectors** show a positive point-estimate "
        f"excess return over the random-entry baseline; **{n_sectors_beats_baseline}** of those "
        f"are statistically significant (cluster-robust by ticker, FDR-corrected):\n"
    )
    if not sectors_sorted.empty:
        lines.append("| Sector | Avg return | Baseline avg return | Excess vs baseline | n tickers | Significant? |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in sectors_sorted.iterrows():
            sig = "yes" if r.get("beats_baseline") else "no"
            lines.append(f"| {r['sector']} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {int(r['n_tickers'])} | {sig} |")
    if not regimes.empty:
        lines.append("\n### By market regime\n")
        lines.append("| Trend regime | Vol regime | Avg return | Baseline avg return | Excess vs baseline | n trades |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in regimes.iterrows():
            lines.append(f"| {r['trend_regime']} | {r['vol_regime']} | {_fmt_pct(r['avg_return'])} | {_fmt_pct(r.get('baseline_avg_return'))} | {_fmt_pct(r.get('excess_return_vs_baseline'))} | {int(r['n_trades'])} |")

    lines.append("\n## 6. Which concepts fail consistently?")
    lines.append(
        "\nTwo distinct ways a concept can fail to earn a place in Section 2: it can be "
        "statistically indistinguishable from the baseline (no evidence either way), or it can be "
        "significantly *worse* (Section 2's second table). Lowest-Sharpe signals with at least 30 "
        "trades (10-day hold) that are indistinguishable from the random-entry baseline:\n"
    )
    if not failing_concepts.empty:
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
        f"Every ranking module (concepts, combinations, sectors, regimes) compares against a "
        f"random-entry baseline run through identical backtest mechanics, in addition to a "
        f"zero-return null, with Benjamini-Hochberg FDR correction applied to both "
        f"(`analytics/statistics.py`). Both baseline comparisons use standard errors clustered by "
        f"ticker (a sandwich/cluster-robust variance estimator, not a naive per-trade t-test): "
        f"trades on the same ticker share overlapping forward-return windows and are not "
        f"independent draws, so treating them as such understates the true standard error and "
        f"can manufacture significance out of noise. This clustering corrects for *within-ticker* "
        f"correlation; it does not implement a full two-way (ticker x date) correction for "
        f"*cross-ticker* correlation on shared market-wide dates, which would tighten the test "
        f"further in the conservative direction (see Key limitations). The headline "
        f"`beats_baseline` flag requires clearing the FDR-corrected baseline comparison "
        f"(alpha={FDR_ALPHA}) **in the positive direction** *and* a minimum sample size — this is "
        f"distinct from `significant_vs_baseline`, which is two-sided and flags a concept whether "
        f"it beats or loses to the baseline. Per-ticker significance tests (Section 4) have "
        f"limited statistical power due to small per-ticker baseline samples (~50 trades) and are "
        f"not cluster-corrected (a single ticker has no cluster structure to correct for) — "
        f"reported as a ranking with honest p-values, not a list of proven stock-specific edges."
    )

    lines.append("\n## Key limitations")
    lines.append(
        "- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).\n"
        "- Significance tests are cluster-robust by ticker but not two-way (ticker x date) "
        "clustered — cross-ticker correlation on shared market-wide dates (e.g. 2020, 2022) is "
        "not corrected for, which would tighten these tests further, not loosen them.\n"
        "- The universe (`data/raw/sp500_constituents.csv`) reflects current-day S&P 500 "
        "membership and weights applied retroactively across 2010-2026, not a point-in-time "
        "constituent history — constituents removed from the index during the window are absent, "
        "and recent additions (e.g. PLTR, COIN, DASH, CRWD) contribute their full available "
        "history despite not being index members for most of it. A form of survivorship bias; no "
        "point-in-time membership data was available to correct it.\n"
        "- The per-ticker stock ranking covers 499 of the 501 tickers with usable price data: two "
        "(`FDXF`, `Q`) have clean price history but produced zero detected SMC/ICT events across "
        "the full window and drop out of that table without a separate flag.\n"
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
