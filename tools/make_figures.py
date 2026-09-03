"""Generate every figure the manuscript uses, into results/figures/.

Colour discipline
-----------------
Colours are assigned by the *job* they do, not by taste:

* **Diverging (blue <-> red, neutral grey midpoint)** wherever the quantity has a
  meaningful zero and a sign that matters -- excess return over the matched-random
  null, effect sizes. Sign is the whole point of these figures, so a sequential
  ramp would be wrong and a rainbow would be unreadable.
* **Categorical (blue, orange)** for the two-series train/test comparison, taken
  in fixed slot order.
* Text always wears text ink, never a series colour.

Figures are print-targeted (single light surface) and every one is also emitted
as a CSV beside the PNG, so a reader can check the numbers rather than measure
the pixels.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.config import PRIMARY_HOLDING_PERIOD, RESULTS_DIR  # noqa: E402
from utils.logging_config import get_logger  # noqa: E402

log = get_logger("tools.make_figures")

FIG_DIR = RESULTS_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# --- palette ---------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8880"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
RED = "#e34948"
GREY_MID = "#f0efec"
GRID = "#e4e3df"

DIVERGING = LinearSegmentedColormap.from_list("bl_rd", [RED, GREY_MID, BLUE])

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.frameon": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }
)


def _despine(ax, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def _read(name: str) -> pd.DataFrame | None:
    p = RESULTS_DIR / name
    if not p.exists():
        log.warning("%s not found -- skipping the figure that needs it", name)
        return None
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def _save(fig, stem: str, data: pd.DataFrame | None = None):
    png = FIG_DIR / f"{stem}.png"
    fig.savefig(png)
    plt.close(fig)
    if data is not None:
        data.to_csv(FIG_DIR / f"{stem}.csv", index=False)
    log.info("wrote %s", png)


# ---------------------------------------------------------------------------
# 1. Forest plot -- effect size with 95% bootstrap CI
# ---------------------------------------------------------------------------
def figure_forest(master: pd.DataFrame):
    """Excess over the matched null, with a 95% interval, for every concept.

    Deliberately NOT Cohen's d against zero. That statistic is negative for
    every short signal simply because shorts lose money in a bull market, so a
    forest plot of it separates long from short rather than informative from
    uninformative -- the opposite of the paper's claim. The excess over the
    composition-matched null is the quantity the conclusion rests on, and its
    sign means what a reader expects it to mean.
    """
    m = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD].copy()
    m = m.dropna(subset=["excess_return_vs_matched_random", "matched_null_se"])
    if m.empty:
        return
    m = m.sort_values("excess_return_vs_matched_random")

    y = np.arange(len(m))
    x = m["excess_return_vs_matched_random"].to_numpy() * 10_000  # bps
    se = m["matched_null_se"].to_numpy() * 10_000
    lo, hi = x - 1.959964 * se, x + 1.959964 * se
    beats = m["beats_matched_random"].fillna(False).to_numpy()

    fig, ax = plt.subplots(figsize=(7.4, max(4.5, 0.19 * len(m))))
    ax.axvline(0, color=INK_MUTED, lw=1.0, zorder=1)
    # Modelled round-trip cost band: an edge inside it cannot be traded.
    ax.axvspan(11, 26, color=ORANGE, alpha=0.13, zorder=0)

    colors = [BLUE if b else INK_MUTED for b in beats]
    ax.hlines(y, lo, hi, color=colors, lw=2.0, alpha=0.45, zorder=2)
    ax.scatter(x, y, s=30, c=colors, zorder=3, edgecolor=SURFACE, linewidth=1.2,
               marker="o")
    # Identity is not colour-alone: winners also carry a marker and a bold label.
    ax.scatter(x[beats], y[beats], s=95, facecolor="none", edgecolor=BLUE,
               linewidth=1.3, zorder=4)

    ax.set_yticks(y)
    labels = [
        f"{sig}  ★" if b else sig
        for sig, b in zip(m["signal"], beats)
    ]
    ax.set_yticklabels(labels, fontsize=7)
    for tick, b in zip(ax.get_yticklabels(), beats):
        tick.set_color(INK if b else INK_2)
        if b:
            tick.set_fontweight("bold")

    ax.set_xlabel("excess return over the composition-matched random null (bps, 10-day trade)")
    ax.set_title(
        f"Does each concept beat random entry on the same names? (h = {PRIMARY_HOLDING_PERIOD} days)",
        loc="left", pad=10,
    )
    ax.grid(axis="x", zorder=0)
    ax.set_ylim(-1, len(m))
    _despine(ax)
    ax.text(0.99, 0.015,
            "★ = beats the null after BH-FDR   ·   shaded = 11-26 bp cost band",
            transform=ax.transAxes, ha="right", va="bottom",
            color=INK_MUTED, fontsize=7.5)
    _save(fig, "fig1_concept_forest",
          m[["signal", "direction", "n_trades", "excess_return_vs_matched_random",
             "matched_null_se", "p_adj_vs_matched_random", "beats_matched_random",
             "effect_size_cohens_d", "cohens_d_ci_lower", "cohens_d_ci_upper"]])


# ---------------------------------------------------------------------------
# 2. Sector heatmap -- excess return vs baseline
# ---------------------------------------------------------------------------
def figure_sector_heatmap(sectors: pd.DataFrame):
    col = "excess_return_vs_matched_random"
    if sectors is None or sectors.empty or col not in sectors:
        return
    s = sectors.dropna(subset=[col]).copy()
    s = s.sort_values(col, ascending=False)
    vals = (s[col] * 100).to_numpy()
    if not len(vals):
        return

    lim = max(abs(vals).max(), 1e-9)
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)

    fig, ax = plt.subplots(figsize=(6.4, max(2.6, 0.34 * len(s))))
    im = ax.imshow(vals.reshape(-1, 1), cmap=DIVERGING, norm=norm, aspect="auto")
    ax.set_yticks(np.arange(len(s)))
    ax.set_yticklabels(s["sector"], fontsize=8)
    ax.set_xticks([])
    for i, v in enumerate(vals):
        n = int(s["n_tickers"].iloc[i]) if "n_tickers" in s.columns else 0
        # Direct labels: the cell colour is reinforced, never relied on.
        ax.text(0, i, f"{v:+.2f}%   (n={n})", ha="center", va="center",
                color=INK, fontsize=8)
    ax.set_title("Excess over a direction-matched random-entry null, by sector",
                 loc="left", pad=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
    cb.set_label("excess return (pp)", color=INK_2, fontsize=8)
    cb.outline.set_visible(False)
    _despine(ax, keep=())
    _save(fig, "fig2_sector_heatmap", s)


# ---------------------------------------------------------------------------
# 3. Annotated trade timelines
# ---------------------------------------------------------------------------
def figure_trade_timelines(master: pd.DataFrame, events: pd.DataFrame):
    """One positive, one null, one negative concept, drawn on real price data."""
    if events is None:
        return
    m = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD].copy()
    m = m.dropna(subset=["excess_return_vs_matched_random"])
    if m.empty:
        return

    m = m[m["n_trades"] > 500]
    if len(m) < 3:
        return
    best = m.nlargest(1, "excess_return_vs_matched_random").iloc[0]
    worst = m.nsmallest(1, "excess_return_vs_matched_random").iloc[0]
    null_row = m.iloc[(m["excess_return_vs_matched_random"].abs()).argsort()].iloc[0]
    picks = [("positive", best), ("null", null_row), ("negative", worst)]

    from utils.prices import load_prices

    ticker = "AAPL"
    ppath = ROOT / "data" / "cache" / f"{ticker}.parquet"
    if not ppath.exists():
        cands = sorted((ROOT / "data" / "cache").glob("*.parquet"))
        if not cands:
            return
        ppath = cands[0]
        ticker = ppath.stem
    px = load_prices(ppath)
    window = px.loc["2018-01-01":"2019-12-31"]
    if window.empty:
        window = px.iloc[-500:]

    fig, axes = plt.subplots(3, 1, figsize=(7.6, 8.4), sharex=True)
    for ax, (label, row) in zip(axes, picks):
        ax.plot(window.index, window["close"], color=INK_2, lw=1.2, zorder=2)
        sig = row["signal"]
        ev = events[(events["ticker"] == ticker) & (events["signal"] == sig)]
        ev = ev[(ev["date"] >= window.index[0]) & (ev["date"] <= window.index[-1])]
        direction = int(row.get("direction", 1))
        colour = BLUE if row["excess_return_vs_matched_random"] > 0 else RED
        if label == "null":
            colour = INK_MUTED
        if len(ev):
            yy = window["close"].reindex(pd.to_datetime(ev["date"])).to_numpy()
            ax.scatter(pd.to_datetime(ev["date"]), yy, s=34, marker="^" if direction > 0 else "v",
                       color=colour, zorder=3, edgecolor=SURFACE, linewidth=1.0,
                       label=f"{sig} ({len(ev)} events)")
            ax.legend(loc="upper left", fontsize=7.5, labelcolor=INK_2)
        ax.set_title(
            f"{label.upper()}: {sig} · excess "
            f"{100 * row['excess_return_vs_matched_random']:+.3f}pp · "
            f"n={int(row['n_trades']):,}",
            loc="left", fontsize=9, pad=6,
        )
        ax.grid(axis="y")
        _despine(ax)
    axes[-1].set_xlabel(f"{ticker} close")
    fig.suptitle("Representative concepts on real price data",
                 x=0.005, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    _save(fig, "fig3_trade_timelines",
          pd.DataFrame([{"role": l, **r[["signal", "n_trades",
                                         "excess_return_vs_matched_random"]].to_dict()}
                        for l, r in picks]))


# ---------------------------------------------------------------------------
# 4. Parameter sensitivity heatmap
# ---------------------------------------------------------------------------
def figure_sensitivity(grid: pd.DataFrame):
    if grid is None or grid.empty:
        return
    px, py = "ict.ob_swing_len", "ict.mss_pivot_len"
    if px not in grid.columns or py not in grid.columns:
        return
    piv = grid.pivot_table(index=py, columns=px,
                           values="excess_return_vs_matched_random", aggfunc="mean")
    if piv.empty:
        return
    vals = piv.to_numpy() * 100
    lim = max(np.nanmax(np.abs(vals)), 1e-9)
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    im = ax.imshow(vals, cmap=DIVERGING, norm=norm, aspect="auto")
    ax.set_xticks(range(len(piv.columns)), piv.columns)
    ax.set_yticks(range(len(piv.index)), piv.index)
    ax.set_xlabel("ICT order-block swing lookback")
    ax.set_ylabel("ICT market-structure pivot length")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if np.isfinite(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:+.2f}", ha="center", va="center",
                        color=INK, fontsize=7.5)
    ax.set_title("Mean excess return across the parameter grid", loc="left", pad=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cb.set_label("excess return (pp)", color=INK_2, fontsize=8)
    cb.outline.set_visible(False)
    _despine(ax, keep=())
    _save(fig, "fig4_sensitivity_heatmap", piv.reset_index())


# ---------------------------------------------------------------------------
# 5. Walk-forward performance
# ---------------------------------------------------------------------------
def figure_walkforward(wf: pd.DataFrame):
    if wf is None or wf.empty:
        return
    x = np.arange(len(wf))
    tr = wf["train_excess_selected"].to_numpy() * 100
    te = wf["test_excess_selected"].to_numpy() * 100

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.2, 5.6), sharex=True,
                                  gridspec_kw={"height_ratios": [2, 1]})
    w = 0.38
    # Two series -> categorical slots 1 and 2, legend always present.
    ax.bar(x - w / 2, tr, w, label="in-sample (train)", color=BLUE)
    ax.bar(x + w / 2, te, w, label="out-of-sample (test)", color=ORANGE)
    ax.axhline(0, color=INK_MUTED, lw=1.0)
    ax.set_ylabel("excess return vs matched null (pp)")
    ax.set_title("Walk-forward: selected concepts, in-sample vs out-of-sample",
                 loc="left", pad=10)
    ax.legend(labelcolor=INK_2)
    ax.grid(axis="y")
    _despine(ax)

    rc = wf["rank_correlation"].to_numpy()
    ax2.bar(x, rc, 0.6, color=[BLUE if v > 0 else RED for v in rc])
    ax2.axhline(0, color=INK_MUTED, lw=1.0)
    ax2.set_ylabel("Spearman rho")
    ax2.set_xlabel("fold")
    ax2.set_xticks(x, [f"{r.test_start}" for r in wf.itertuples()], rotation=45,
                   ha="right", fontsize=7)
    ax2.set_title("Train -> test rank correlation of concept ordering",
                  loc="left", fontsize=9, pad=6)
    ax2.grid(axis="y")
    _despine(ax2)
    fig.tight_layout()
    _save(fig, "fig5_walkforward", wf)


# ---------------------------------------------------------------------------
# 6. Break-even cost
# ---------------------------------------------------------------------------
def figure_breakeven(be: pd.DataFrame):
    if be is None or be.empty:
        return
    # The excess measure is the decision-relevant one: gross break-even credits
    # the signal with market drift that random entry would also have captured.
    col = ("breakeven_excess_cost_bps"
           if "breakeven_excess_cost_bps" in be.columns else "breakeven_cost_bps")
    b = be.dropna(subset=[col]).sort_values(col, ascending=True)
    y = np.arange(len(b))
    v = b[col].to_numpy()
    fig, ax = plt.subplots(figsize=(7.0, max(4.0, 0.19 * len(b))))
    ax.barh(y, v, color=[BLUE if x > 0 else RED for x in v], height=0.7)
    ax.axvline(0, color=INK_MUTED, lw=1.0)
    # The modelled cost band is the decision line the reader cares about.
    ax.axvspan(11, 26, color=ORANGE, alpha=0.13, zorder=0)
    ax.text(26, len(b) * 0.02, " modelled cost band (11-26 bps)", color=ORANGE,
            fontsize=7.5, va="bottom")
    ax.set_yticks(y, b["signal"], fontsize=7)
    ax.set_xlabel("break-even round-trip cost on the excess over the matched null (bps)")
    ax.set_title("Cost at which each concept's edge over random entry disappears",
                 loc="left", pad=10)
    ax.grid(axis="x")
    _despine(ax)
    _save(fig, "fig6_breakeven_costs", b)


def main() -> int:
    master = _read("statistics_master.csv")
    if master is None:
        log.error("statistics_master.csv is required for the figures")
        return 1
    figure_forest(master)
    figure_sector_heatmap(_read("sector_analysis.csv"))
    figure_trade_timelines(master, _read("master_events.parquet"))
    figure_sensitivity(_read("sensitivity_grid.csv"))
    figure_walkforward(_read("walkforward_summary.csv"))
    figure_breakeven(_read("breakeven_costs.csv"))
    log.info("Figures written to %s", FIG_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
