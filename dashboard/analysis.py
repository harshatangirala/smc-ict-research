"""Framework-agnostic dashboard logic: every chart/table builder used by
BOTH dashboard/app.py (Gradio) and streamlit_app.py (Streamlit).

Every function here only reads from dashboard/data_access.py (which itself
only reads files main.py's pipeline already produced) and returns plain
pandas DataFrames / Plotly figures / strings -- no UI-framework objects, so
either front end can call these directly with zero duplicated calculation,
per the project's "no duplicated functionality" architecture rule
(docs/architecture.md).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard import data_access as da


def empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=16))
    fig.update_layout(xaxis={"visible": False}, yaxis={"visible": False})
    return fig


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
def home_markdown() -> str:
    s = da.summary_stats()
    demo_note = (
        """
> **Running on the bundled demo dataset.** Every ranking, statistic, and significance
> test below is the real output of the full research run (see `docs/final_research_report.md`).
> Two things are trimmed for a fast, git-friendly deploy: the Concept Explorer's return
> histograms sample 500,000 of the full 34.6M backtested trades, and the Stock Explorer's
> price chart is only available for the top 50 S&P 500 constituents by index weight
> (~63% of total weight). Run `python main.py all` locally for the full 501-ticker,
> 34.6M-trade dataset.
"""
        if da.using_bundled_data()
        else ""
    )
    return f"""
A quantitative research platform testing whether **Smart Money Concepts (SMC)** and
**ICT (Inner Circle Trader)** trading concepts -- translated directly from two LuxAlgo
Pine Script indicators -- provide statistically significant, out-of-sample-honest
trading edges on daily S&P 500 data (2010-2026).
{demo_note}
## At a glance

| Metric | Value |
|---|---|
| Stocks analyzed | **{s['total_stocks_analyzed']}** |
| Distinct SMC/ICT signals | **{s['distinct_signals']}** |
| Total events detected | **{s['total_events']:,}** |
| Total backtested trades | **{s['total_trades_backtested']:,}** |
| Years of history covered | **{s['years_covered']}** |

## How to use this dashboard

- **Stock Explorer** -- pick a ticker, see its detected events and performance.
- **Concept Explorer** -- pick a signal (e.g. `ict_bos_bullish`), see its win rate,
  return distribution, and which stocks it works best/worst on.
- **Combination Explorer** -- see which concept *pairs* (e.g. BOS + FVG) outperform
  either concept alone.
- **Rankings** -- top concepts, top stocks, top combinations, all in one place.
- **Sector & Regime** -- does the edge hold up across sectors and bull/bear/sideways
  markets?
- **Validation** -- data quality, statistical significance, and methodology notes.

Every number in this dashboard is read directly from the research pipeline's saved
output (`results/`, `exports/`) -- nothing is recalculated live in the UI.
"""


def home_scoreboard() -> dict:
    """Headline zero-vs-baseline numbers for a KPI-style summary strip."""
    concepts = da.get_concept_rankings(holding_period=10)
    sectors = da.get_sector_analysis()
    n_concepts = len(concepts)
    n_sig_zero = int(concepts["significant_vs_zero"].sum()) if "significant_vs_zero" in concepts else None
    n_sig_baseline = int(concepts["statistically_significant"].sum()) if "statistically_significant" in concepts else None
    n_sectors = len(sectors)
    n_sectors_positive = int((sectors["excess_return_vs_baseline"] > 0).sum()) if "excess_return_vs_baseline" in sectors else None
    return {
        "n_concepts": n_concepts,
        "n_sig_zero": n_sig_zero,
        "n_sig_baseline": n_sig_baseline,
        "n_sectors": n_sectors,
        "n_sectors_positive": n_sectors_positive,
    }


# ---------------------------------------------------------------------------
# Stock Explorer
# ---------------------------------------------------------------------------
def stock_view(ticker: str) -> tuple[go.Figure, pd.DataFrame, pd.DataFrame]:
    if not ticker:
        return empty_fig("Select a ticker"), pd.DataFrame(), pd.DataFrame()

    price = da.get_price_history(ticker)
    events = da.get_master_events()
    ticker_events = events[events["ticker"] == ticker] if not events.empty else pd.DataFrame()

    fig = go.Figure()
    if not price.empty:
        fig.add_trace(go.Candlestick(
            x=price.index, open=price["open"], high=price["high"],
            low=price["low"], close=price["close"], name=ticker,
        ))
        if not ticker_events.empty:
            bos = ticker_events[ticker_events["signal"] == "ict_bos_bullish"]
            if not bos.empty:
                fig.add_trace(go.Scatter(
                    x=bos["date"], y=bos["close"], mode="markers", name="ICT BOS bullish",
                    marker=dict(symbol="triangle-up", size=9, color="green"),
                ))
    fig.update_layout(title=f"{ticker} price with ICT bullish BOS markers", xaxis_rangeslider_visible=False, height=500)

    stock_rankings = da.get_stock_rankings()
    stock_row = stock_rankings[stock_rankings["ticker"] == ticker] if not stock_rankings.empty else pd.DataFrame()

    signal_counts = (
        ticker_events["signal"].value_counts().rename_axis("signal").reset_index(name="count")
        if not ticker_events.empty else pd.DataFrame()
    )
    return fig, stock_row, signal_counts


# ---------------------------------------------------------------------------
# Concept Explorer
# ---------------------------------------------------------------------------
def concept_view(signal_name: str, holding_period: int) -> tuple[go.Figure, pd.DataFrame, go.Figure]:
    if not signal_name:
        return empty_fig("Select a concept"), pd.DataFrame(), empty_fig("")

    trades = da.get_trades()
    if trades.empty:
        return empty_fig("No trades computed yet"), pd.DataFrame(), empty_fig("")

    subset = trades[(trades["signal"] == signal_name) & (trades["holding_period"] == holding_period)]

    hist_fig = px.histogram(subset, x="fwd_return", nbins=60, title=f"{signal_name} forward-return distribution ({holding_period}d)")
    hist_fig.add_vline(x=0, line_dash="dash", line_color="gray")

    rankings = da.get_concept_rankings(holding_period=holding_period)
    row = rankings[rankings["signal"] == signal_name] if not rankings.empty else pd.DataFrame()

    by_ticker = subset.groupby("ticker")["fwd_return"].mean().sort_values(ascending=False)
    top_bottom = pd.concat([by_ticker.head(15), by_ticker.tail(15)]).reset_index()
    bar_fig = px.bar(top_bottom, x="ticker", y="fwd_return", title="Best/worst 15 stocks for this concept (mean return)")

    return hist_fig, row, bar_fig


# ---------------------------------------------------------------------------
# Combination Explorer
# ---------------------------------------------------------------------------
def combinations_view() -> tuple[go.Figure, pd.DataFrame]:
    combos = da.get_combination_rankings()
    if combos.empty:
        return empty_fig("No combinations met the minimum-occurrence threshold"), pd.DataFrame()
    top = combos.head(20)
    fig = px.bar(top, x="combination", y="sharpe", color="statistically_significant",
                 title="Top 20 concept combinations by Sharpe (10-day hold)")
    fig.update_xaxes(tickangle=45)
    return fig, combos


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------
def rankings_view(holding_period: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    concepts = da.get_concept_rankings(holding_period=holding_period)
    stocks = da.get_stock_rankings()
    combos = da.get_combination_rankings()
    return concepts, stocks, combos


# ---------------------------------------------------------------------------
# Sector & Regime
# ---------------------------------------------------------------------------
def sector_regime_view() -> tuple[go.Figure, pd.DataFrame, go.Figure, pd.DataFrame]:
    sectors = da.get_sector_analysis()
    regimes = da.get_regime_analysis()

    if not sectors.empty:
        sorted_sectors = sectors.sort_values("excess_return_vs_baseline", ascending=False)
        sector_fig = px.bar(
            sorted_sectors, x="sector", y="excess_return_vs_baseline",
            color=sorted_sectors["excess_return_vs_baseline"] > 0,
            color_discrete_map={True: "#2E6B4F", False: "#9C3B32"},
            title="Excess return vs. random-entry baseline, by sector (10-day hold)",
        )
        sector_fig.update_layout(showlegend=False)
        sector_fig.update_xaxes(tickangle=45)
    else:
        sector_fig = empty_fig("Sector analysis not yet run")

    if not regimes.empty:
        regime_fig = px.density_heatmap(
            regimes, x="trend_regime", y="vol_regime", z="excess_return_vs_baseline",
            histfunc="avg", color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
            title="Excess return vs. baseline by trend x volatility regime (10-day hold)",
        )
    else:
        regime_fig = empty_fig("Regime analysis not yet run")

    return sector_fig, sectors, regime_fig, regimes


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validation_view() -> tuple[str, pd.DataFrame]:
    dq = da.get_data_quality_report()
    if dq.empty:
        return "Data quality report not yet generated.", pd.DataFrame()
    n_ok = (dq["status"] == "OK").sum()
    n_issues = (dq["status"] == "ISSUES_FOUND").sum()
    n_missing = (dq["status"] == "NO_DATA").sum()
    summary = f"""
## Data Quality Summary

- **{n_ok}** tickers clean
- **{n_issues}** tickers flagged with issues (see table below)
- **{n_missing}** tickers with no data at all

## Methodology notes

- No look-ahead bias: every signal only uses bars up to and including its own
  formation bar; every forward return is computed strictly on bars *after* the
  signal bar.
- Statistical significance is tested BOTH against a zero-return null and
  against a random-entry baseline run through identical backtest mechanics
  (`backtest/baseline_engine.py`), with Benjamini-Hochberg FDR correction
  applied to each (see `analytics/statistics.py`). The zero-return test alone
  is misleading over 2010-2026, a long bull market.
- See `docs/concepts_extraction.md` and `docs/task02_pine_analysis.md` for the
  full Pine-to-Python translation spec, including documented assumptions and
  ambiguities resolved during translation.
"""
    return summary, dq[dq["status"] != "OK"]
