"""Gradio dashboard entry point (Task 13 / Task 16).

All chart/table logic lives in dashboard/analysis.py, shared with
streamlit_app.py -- this file is purely Gradio layout/wiring.
"""

from __future__ import annotations

import gradio as gr

from dashboard import analysis as dz
from dashboard import data_access as da


def build_app() -> gr.Blocks:
    with gr.Blocks(
        css=".gradio-container { max-width: 1400px !important; margin: auto; }",
        title="SMC/ICT Research Dashboard",
        theme=gr.themes.Soft(),
    ) as demo:
        with gr.Tab("Home"):
            gr.Markdown("# SMC/ICT Statistical Edge Research")
            gr.Markdown(dz.home_markdown())

        with gr.Tab("Stock Explorer"):
            ticker_dd = gr.Dropdown(choices=da.list_tickers(), label="Ticker", value=None)
            chart = gr.Plot()
            stock_stats = gr.Dataframe(label="Stock performance (10-day hold)")
            signal_counts = gr.Dataframe(label="Detected signal counts")
            ticker_dd.change(dz.stock_view, inputs=ticker_dd, outputs=[chart, stock_stats, signal_counts])

        with gr.Tab("Concept Explorer"):
            with gr.Row():
                signal_dd = gr.Dropdown(choices=da.list_signals(), label="Signal")
                hp_dd = gr.Dropdown(choices=[1, 2, 3, 5, 10, 20, 40, 60], value=10, label="Holding period (days)")
            concept_hist = gr.Plot()
            concept_stats = gr.Dataframe(label="Concept statistics")
            concept_bar = gr.Plot()
            signal_dd.change(dz.concept_view, inputs=[signal_dd, hp_dd], outputs=[concept_hist, concept_stats, concept_bar])
            hp_dd.change(dz.concept_view, inputs=[signal_dd, hp_dd], outputs=[concept_hist, concept_stats, concept_bar])

        with gr.Tab("Combination Explorer"):
            combo_btn = gr.Button("Load combination rankings")
            combo_fig = gr.Plot()
            combo_table = gr.Dataframe()
            combo_btn.click(dz.combinations_view, outputs=[combo_fig, combo_table])

        with gr.Tab("Rankings"):
            rank_hp = gr.Dropdown(choices=[1, 2, 3, 5, 10, 20, 40, 60], value=10, label="Holding period (days)")
            gr.Markdown("### Concept rankings")
            concept_rank_table = gr.Dataframe()
            gr.Markdown("### Stock rankings")
            stock_rank_table = gr.Dataframe()
            gr.Markdown("### Combination rankings")
            combo_rank_table = gr.Dataframe()
            rank_hp.change(dz.rankings_view, inputs=rank_hp, outputs=[concept_rank_table, stock_rank_table, combo_rank_table])
            demo.load(dz.rankings_view, inputs=rank_hp, outputs=[concept_rank_table, stock_rank_table, combo_rank_table])

        with gr.Tab("Sector & Regime"):
            sr_btn = gr.Button("Load sector & regime analysis")
            sector_fig = gr.Plot()
            sector_table = gr.Dataframe()
            regime_fig = gr.Plot()
            regime_table = gr.Dataframe()
            sr_btn.click(dz.sector_regime_view, outputs=[sector_fig, sector_table, regime_fig, regime_table])

        with gr.Tab("Validation"):
            val_btn = gr.Button("Load validation report")
            val_md = gr.Markdown()
            val_table = gr.Dataframe(label="Flagged tickers")
            val_btn.click(dz.validation_view, outputs=[val_md, val_table])

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.launch()
