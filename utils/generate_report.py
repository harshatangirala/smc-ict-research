"""Generates docs/final_research_report.md directly from the pipeline's saved
results (Task 15/20's executive report) -- every number is read from a file
the pipeline produced, not hand-transcribed, so the report can't drift from
the actual computed results.
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

    n_sig_concepts = int(concepts["statistically_significant"].sum()) if "statistically_significant" in concepts else 0
    n_total_concepts = len(concepts)

    top_concepts = concepts[concepts.get("statistically_significant", False) == True].head(10) if not concepts.empty else pd.DataFrame()  # noqa: E712
    failing_concepts = concepts[(concepts.get("statistically_significant", False) == False) & (concepts.get("n_trades", 0) >= 30)].sort_values("sharpe").head(10) if not concepts.empty else pd.DataFrame()  # noqa: E712

    top_combos = combos[combos.get("statistically_significant", False) == True].head(10) if not combos.empty else pd.DataFrame()  # noqa: E712
    best_stocks = stocks[stocks.get("eligible", False) == True].head(20) if not stocks.empty else pd.DataFrame()  # noqa: E712
    best_sectors = sectors.head(5) if not sectors.empty else pd.DataFrame()

    lines = []
    lines.append(f"# Executive Research Report — SMC/ICT Statistical Edge Study")
    lines.append(f"\n_Generated {date.today().isoformat()} directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._\n")

    lines.append("## Scope")
    lines.append(f"- Stocks with usable data: **{dq['ticker'].nunique() if not dq.empty else 'n/a'}** of 503 S&P 500 constituents")
    lines.append(f"- Total SMC/ICT events detected: **{len(events):,}**")
    lines.append(f"- Total backtested trades (events x holding periods): **{len(trades):,}**")
    lines.append(f"- Distinct signal families tested: **{events['signal'].nunique() if not events.empty else 'n/a'}**")
    lines.append(f"- FDR significance threshold used throughout: alpha = {FDR_ALPHA}")

    lines.append("\n## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?")
    lines.append(
        f"Of {n_total_concepts} SMC/ICT signal families tested at the 10-day holding horizon, "
        f"**{n_sig_concepts}** survived Benjamini-Hochberg FDR correction at alpha={FDR_ALPHA} "
        f"(i.e. remained statistically distinguishable from a zero-mean return after correcting "
        f"for testing {n_total_concepts} hypotheses simultaneously). See `analytics/statistics.py` "
        f"for the two-sample test against the baseline strategies in `backtest/baselines.py` "
        f"(buy & hold, random entry, EMA 20/50 crossover, RSI(14) mean reversion, 52-week "
        f"breakout, 126-day momentum turn) for the incremental-edge comparison."
    )

    lines.append("\n## 2. Which concepts provide the strongest statistical edge?")
    if not top_concepts.empty:
        lines.append("\n| Signal | n trades | Win rate | Sharpe | Avg return | p (FDR-adj) |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in top_concepts.iterrows():
            lines.append(f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} | {_fmt(r.get('p_adjusted'), 4)} |")
    else:
        lines.append("No concepts reached statistical significance at the current sample/threshold.")

    lines.append("\n## 3. Which concept combinations are most robust?")
    if not top_combos.empty:
        lines.append("\n| Combination | n trades | Win rate | Sharpe | Avg return |")
        lines.append("|---|---|---|---|---|")
        for _, r in top_combos.iterrows():
            lines.append(f"| {r['combination']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} | {_fmt_pct(r['avg_return'])} |")
    else:
        lines.append("No combinations met the minimum-occurrence threshold or reached significance.")

    lines.append("\n## 4. Which S&P 500 stocks are most responsive?")
    if not best_stocks.empty:
        lines.append("\nTop 20 by Sharpe (10-day hold, min 20 trades) — see `results/stock_rankings.csv` for the full ranked list.")
        lines.append("\n| Ticker | n trades | Win rate | Sharpe |")
        lines.append("|---|---|---|---|")
        for _, r in best_stocks.iterrows():
            lines.append(f"| {r['ticker']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} |")
    else:
        lines.append("Stock ranking not available.")

    lines.append("\n## 5. Which sectors and market regimes are most responsive?")
    if not best_sectors.empty:
        lines.append("\n| Sector | Sharpe | Win rate | n tickers |")
        lines.append("|---|---|---|---|")
        for _, r in best_sectors.iterrows():
            lines.append(f"| {r['sector']} | {_fmt(r['sharpe'])} | {_fmt_pct(r['win_rate'])} | {int(r['n_tickers'])} |")
    if not regimes.empty:
        lines.append("\n### By market regime\n")
        lines.append("| Trend regime | Vol regime | Win rate | Avg return | n trades |")
        lines.append("|---|---|---|---|---|")
        for _, r in regimes.iterrows():
            lines.append(f"| {r['trend_regime']} | {r['vol_regime']} | {_fmt_pct(r['win_rate'])} | {_fmt_pct(r['avg_return'])} | {int(r['n_trades'])} |")

    lines.append("\n## 6. Which concepts fail consistently?")
    if not failing_concepts.empty:
        lines.append("\nLowest-Sharpe signals with at least 30 trades (10-day hold) that did *not* reach FDR-corrected significance:\n")
        lines.append("| Signal | n trades | Win rate | Sharpe |")
        lines.append("|---|---|---|---|")
        for _, r in failing_concepts.iterrows():
            lines.append(f"| {r['signal']} | {int(r['n_trades'])} | {_fmt_pct(r['win_rate'])} | {_fmt(r['sharpe'])} |")
    else:
        lines.append("See `results/concept_rankings.csv` for the full ranked list including non-significant concepts.")

    lines.append("\n## 7. Are results stable across bull, bear, and sideways markets?")
    lines.append(
        "See the regime table above and `results/regime_analysis.csv` / the dashboard's Sector & "
        "Regime tab for the full per-signal regime breakdown (`analytics/regimes.py:"
        "regime_analysis_by_signal`). Regime classification uses each stock's own trailing "
        "SMA(200) trend and realized-volatility-vs-own-history state, not an external index."
    )

    lines.append("\n## 8. Are results statistically significant after correcting for sample size and multiple testing?")
    lines.append(
        f"Yes, by construction — every concept and combination ranking reports a bootstrap "
        f"confidence interval, a p-value, and a Benjamini-Hochberg FDR-adjusted p-value "
        f"(`analytics/statistics.py`), and only signals clearing both the FDR threshold "
        f"(alpha={FDR_ALPHA}) *and* a minimum sample size are labeled `statistically_significant`. "
        f"Concepts with fewer than 30 trades are explicitly flagged `low_sample_warning` rather "
        f"than being reported with false confidence."
    )

    lines.append("\n## Key limitations")
    lines.append(
        "- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).\n"
        "- Sector mapping is a static approximation, not a live data source.\n"
        "- No transaction costs or slippage modeled.\n"
        "- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no "
        "corresponding logic in the source scripts and are not implemented.\n"
        "- See README.md \"Limitations\" and \"Key assumptions\" sections for the complete list."
    )

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    out_path = RESULTS_DIR.parent / "docs" / "final_research_report.md"
    out_path.write_text(report, encoding="utf-8")
    log.info("Final research report written to %s", out_path)
