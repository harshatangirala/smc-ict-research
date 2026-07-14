"""Streamlit dashboard entry point.

Same data, same charts, same "nothing recalculated in the UI" rule as
app.py (Gradio) -- both front ends call the identical framework-agnostic
functions in dashboard/analysis.py, so the two dashboards can never disagree
with each other. Run with:

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from dashboard import analysis as dz
from dashboard import data_access as da

st.set_page_config(
    page_title="SMC/ICT Research Dashboard",
    page_icon="📈",
    layout="wide",
)

HOLDING_PERIODS = [1, 2, 3, 5, 10, 20, 40, 60]

st.title("SMC/ICT Statistical Edge Research")

tabs = st.tabs([
    "Home", "Stock Explorer", "Concept Explorer", "Combination Explorer",
    "Rankings", "Sector & Regime", "Validation",
])

# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
with tabs[0]:
    score = dz.home_scoreboard()
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Concepts beating a zero-return null",
        f"{score['n_sig_zero']}/{score['n_concepts']}" if score["n_sig_zero"] is not None else "n/a",
        help="Weak test -- inflated by 16 years of broad market drift.",
    )
    col2.metric(
        "Concepts beating the random-entry baseline",
        f"{score['n_sig_baseline']}/{score['n_concepts']}" if score["n_sig_baseline"] is not None else "n/a",
        help="The test that actually matters: same backtest mechanics, same frequency, random entries.",
    )
    col3.metric(
        "Sectors with positive excess return",
        f"{score['n_sectors_positive']}/{score['n_sectors']}" if score["n_sectors_positive"] is not None else "n/a",
        help="Sectors where the signal population actually beat the baseline, on average.",
    )
    st.markdown(dz.home_markdown())

# ---------------------------------------------------------------------------
# Stock Explorer
# ---------------------------------------------------------------------------
with tabs[1]:
    if da.using_bundled_data():
        st.caption("Chart available for the top 50 S&P 500 constituents by index weight (demo bundle).")
    tickers = da.list_tickers_with_price_history()
    ticker = st.selectbox("Ticker", options=[""] + tickers, index=0, key="stock_ticker")
    if ticker:
        fig, stock_row, signal_counts = dz.stock_view(ticker)
        st.plotly_chart(fig, width="stretch")
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.subheader("Stock performance (10-day hold)")
            st.dataframe(stock_row, width="stretch", hide_index=True)
        with col_b:
            st.subheader("Detected signal counts")
            st.dataframe(signal_counts, width="stretch", hide_index=True, height=350)
    else:
        st.info("Select a ticker to see its detected events and performance.")

# ---------------------------------------------------------------------------
# Concept Explorer
# ---------------------------------------------------------------------------
with tabs[2]:
    if da.using_bundled_data():
        st.caption("Return distribution sampled from 500,000 of the full 34.6M backtested trades (demo bundle).")
    col_a, col_b = st.columns([2, 1])
    with col_a:
        signal_name = st.selectbox("Signal", options=[""] + da.list_signals(), index=0, key="concept_signal")
    with col_b:
        holding_period = st.select_slider("Holding period (days)", options=HOLDING_PERIODS, value=10, key="concept_hp")
    if signal_name:
        hist_fig, row, bar_fig = dz.concept_view(signal_name, holding_period)
        st.dataframe(row, width="stretch", hide_index=True)
        col_c, col_d = st.columns(2)
        with col_c:
            st.plotly_chart(hist_fig, width="stretch")
        with col_d:
            st.plotly_chart(bar_fig, width="stretch")
    else:
        st.info("Select a signal to see its return distribution and per-stock breakdown.")

# ---------------------------------------------------------------------------
# Combination Explorer
# ---------------------------------------------------------------------------
with tabs[3]:
    combo_fig, combo_table = dz.combinations_view()
    st.plotly_chart(combo_fig, width="stretch")
    st.dataframe(combo_table, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------
with tabs[4]:
    rank_hp = st.select_slider("Holding period (days)", options=HOLDING_PERIODS, value=10, key="rank_hp")
    concepts, stocks, combos = dz.rankings_view(rank_hp)
    st.subheader("Concept rankings")
    st.dataframe(concepts, width="stretch", hide_index=True)
    st.subheader("Stock rankings")
    st.dataframe(stocks, width="stretch", hide_index=True)
    st.subheader("Combination rankings")
    st.dataframe(combos, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Sector & Regime
# ---------------------------------------------------------------------------
with tabs[5]:
    sector_fig, sector_table, regime_fig, regime_table = dz.sector_regime_view()
    st.plotly_chart(sector_fig, width="stretch")
    st.dataframe(sector_table, width="stretch", hide_index=True)
    st.plotly_chart(regime_fig, width="stretch")
    st.dataframe(regime_table, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
with tabs[6]:
    summary, flagged = dz.validation_view()
    st.markdown(summary)
    st.subheader("Flagged tickers")
    st.dataframe(flagged, width="stretch", hide_index=True)
