"""Gradio dashboard entry point (Task 13 / Task 16).

Every figure/table below reads from files already produced by main.py's
pipeline stages (dashboard/data_access.py) -- no statistic is recomputed in
the UI layer, per the Task 13 validation gate.
"""

from __future__ import annotations

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard import data_access as da

CUSTOM_CSS = """
.gradio-container { max-width: 1400px !important; margin: auto; }
"""


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=16))
    fig.update_layout(xaxis={"visible": False}, yaxis={"visible": False})
    return fig


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
def render_home() -> str:
    s = da.summary_stats()
    return f"""
# SMC/ICT Statistical Edge Research

A quantitative research platform testing whether **Smart Money Concepts (SMC)** and
**ICT (Inner Circle Trader)** trading concepts -- translated directly from two LuxAlgo
Pine Script indicators -- provide statistically significant, out-of-sample-honest
trading edges on daily S&P 500 data (2010-2026).

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


# ---------------------------------------------------------------------------
# Stock Explorer
# ---------------------------------------------------------------------------
def render_stock(ticker: str):
    if not ticker:
        return _empty_fig("Select a ticker"), pd.DataFrame(), pd.DataFrame()

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
def render_concept(signal_name: str, holding_period: int):
    if not signal_name:
        return _empty_fig("Select a concept"), pd.DataFrame(), _empty_fig("")

    trades = da.get_trades()
    if trades.empty:
        return _empty_fig("No trades computed yet"), pd.DataFrame(), _empty_fig("")

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
def render_combinations():
    combos = da.get_combination_rankings()
    if combos.empty:
        return _empty_fig("No combinations met the minimum-occurrence threshold"), pd.DataFrame()
    top = combos.head(20)
    fig = px.bar(top, x="combination", y="sharpe", color="statistically_significant",
                 title="Top 20 concept combinations by Sharpe (10-day hold)")
    fig.update_xaxes(tickangle=45)
    return fig, combos


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------
def render_rankings(holding_period: int):
    concepts = da.get_concept_rankings(holding_period=holding_period)
    stocks = da.get_stock_rankings()
    combos = da.get_combination_rankings()
    return concepts, stocks, combos


# ---------------------------------------------------------------------------
# Sector & Regime
# ---------------------------------------------------------------------------
def render_sector_regime():
    sectors = da.get_sector_analysis()
    regimes = da.get_regime_analysis()

    sector_fig = (
        px.bar(sectors, x="sector", y="sharpe", title="Sharpe by sector (10-day hold)")
        if not sectors.empty else _empty_fig("Sector analysis not yet run")
    )
    regime_fig = (
        px.bar(regimes, x="trend_regime", y="win_rate", color="vol_regime", barmode="group",
               title="Win rate by trend/volatility regime (10-day hold)")
        if not regimes.empty else _empty_fig("Regime analysis not yet run")
    )
    return sector_fig, sectors, regime_fig, regimes


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def render_validation():
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
- Statistical significance uses bootstrap confidence intervals + one-sample
  t-tests, with Benjamini-Hochberg FDR correction applied across every
  concept/combination tested (see `analytics/statistics.py`).
- See `docs/concepts_extraction.md` and `docs/task02_pine_analysis.md` for the
  full Pine-to-Python translation spec, including documented assumptions and
  ambiguities resolved during translation.
"""
    return summary, dq[dq["status"] != "OK"]


def build_app() -> gr.Blocks:
    with gr.Blocks(css=CUSTOM_CSS, title="SMC/ICT Research Dashboard", theme=gr.themes.Soft()) as demo:
        with gr.Tab("Home"):
            gr.Markdown(render_home())

        with gr.Tab("Stock Explorer"):
            ticker_dd = gr.Dropdown(choices=da.list_tickers(), label="Ticker", value=None)
            chart = gr.Plot()
            stock_stats = gr.Dataframe(label="Stock performance (10-day hold)")
            signal_counts = gr.Dataframe(label="Detected signal counts")
            ticker_dd.change(render_stock, inputs=ticker_dd, outputs=[chart, stock_stats, signal_counts])

        with gr.Tab("Concept Explorer"):
            with gr.Row():
                signal_dd = gr.Dropdown(choices=da.list_signals(), label="Signal")
                hp_dd = gr.Dropdown(choices=[1, 2, 3, 5, 10, 20, 40, 60], value=10, label="Holding period (days)")
            concept_hist = gr.Plot()
            concept_stats = gr.Dataframe(label="Concept statistics")
            concept_bar = gr.Plot()
            signal_dd.change(render_concept, inputs=[signal_dd, hp_dd], outputs=[concept_hist, concept_stats, concept_bar])
            hp_dd.change(render_concept, inputs=[signal_dd, hp_dd], outputs=[concept_hist, concept_stats, concept_bar])

        with gr.Tab("Combination Explorer"):
            combo_btn = gr.Button("Load combination rankings")
            combo_fig = gr.Plot()
            combo_table = gr.Dataframe()
            combo_btn.click(render_combinations, outputs=[combo_fig, combo_table])

        with gr.Tab("Rankings"):
            rank_hp = gr.Dropdown(choices=[1, 2, 3, 5, 10, 20, 40, 60], value=10, label="Holding period (days)")
            gr.Markdown("### Concept rankings")
            concept_rank_table = gr.Dataframe()
            gr.Markdown("### Stock rankings")
            stock_rank_table = gr.Dataframe()
            gr.Markdown("### Combination rankings")
            combo_rank_table = gr.Dataframe()
            rank_hp.change(render_rankings, inputs=rank_hp, outputs=[concept_rank_table, stock_rank_table, combo_rank_table])
            demo.load(render_rankings, inputs=rank_hp, outputs=[concept_rank_table, stock_rank_table, combo_rank_table])

        with gr.Tab("Sector & Regime"):
            sr_btn = gr.Button("Load sector & regime analysis")
            sector_fig = gr.Plot()
            sector_table = gr.Dataframe()
            regime_fig = gr.Plot()
            regime_table = gr.Dataframe()
            sr_btn.click(render_sector_regime, outputs=[sector_fig, sector_table, regime_fig, regime_table])

        with gr.Tab("Validation"):
            val_btn = gr.Button("Load validation report")
            val_md = gr.Markdown()
            val_table = gr.Dataframe(label="Flagged tickers")
            val_btn.click(render_validation, outputs=[val_md, val_table])

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.launch()
