"""results/master_summary.md -- the human-readable companion to
results/statistics_master.csv.

Reports, per concept, the full metric set the brief specifies at every horizon:
mean/median/std/skew/kurtosis, win rate, expectancy, profit factor, annualised
Sharpe/Sortino/Calmar, max drawdown, MFE/MAE summaries, the three p-values
(vs zero, vs matched random, vs the pooled baseline), their BH-FDR-adjusted
values, Cohen's d and bootstrap confidence intervals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import (
    BOOTSTRAP_ITERATIONS,
    FDR_ALPHA,
    HOLDING_PERIODS,
    PRIMARY_HOLDING_PERIOD,
    RESULTS_DIR,
)
from utils.logging_config import get_logger

log = get_logger("utils.master_summary")


def _p(x, dp=2):
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.{dp}f}%"


def _f(x, dp=3):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{dp}f}"


def _sci(x):
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.3f}" if x >= 1e-3 else f"{x:.2e}"


def build_master_summary(path: Path | None = None) -> Path:
    path = path or (RESULTS_DIR / "master_summary.md")
    master_path = RESULTS_DIR / "statistics_master.csv"
    if not master_path.exists():
        raise FileNotFoundError(
            f"{master_path} not found -- run `python main.py statistics` first"
        )
    m = pd.read_csv(master_path)

    L: list[str] = [
        "# Master Summary -- SMC/ICT Statistical Edge Study", "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(m)} (signal x horizon) hypotheses · BH-FDR at alpha = {FDR_ALPHA} "
        f"across the whole family · {BOOTSTRAP_ITERATIONS:,} bootstrap iterations*", "",
        "Full machine-readable table: `results/statistics_master.csv`.", "",
        "## How to read this", "",
        "* **Excess vs matched random** is the headline quantity: the concept's "
        "mean return minus the mean of entering the *same tickers* the *same "
        "number of times* on randomly chosen dates. It removes the ticker-mix "
        "confound that a pooled comparison cannot.",
        "* **p (vs zero)** uses a calendar-time Newey-West standard error, not "
        "the iid t-test. Forward returns overlap and cluster cross-sectionally; "
        "the iid p-values (retained as `p_value_vs_zero_iid`) are far too small.",
        "* **Beats null** requires a positive excess AND survival of BH-FDR at "
        f"alpha = {FDR_ALPHA} AND an adequate sample. A significant *negative* "
        "excess is reported as losing to the null, never as an edge.", "",
        "---", "",
    ]

    # ------------------------------------------------------------------
    # Primary horizon table
    # ------------------------------------------------------------------
    prim = m[m["holding_period"] == PRIMARY_HOLDING_PERIOD].sort_values(
        "excess_return_vs_matched_random", ascending=False
    )
    L += [
        f"## 1. All concepts at the primary horizon (h = {PRIMARY_HOLDING_PERIOD} days)", "",
        "| # | Signal | Dir | n | Win rate | Mean | Median | Excess vs null | "
        "p (FDR, vs null) | Cohen's d [95% CI] | Sharpe | Beats null |",
        "|--:|---|--:|--:|--:|--:|--:|--:|--:|---|--:|:--:|",
    ]
    for i, (_, r) in enumerate(prim.iterrows(), 1):
        L.append(
            f"| {i} | `{r['signal']}` | {int(r.get('direction', 0)):+d} | "
            f"{int(r['n_trades']):,} | {_p(r.get('win_rate'))} | "
            f"{_p(r.get('avg_return'))} | {_p(r.get('median_return'))} | "
            f"{_p(r.get('excess_return_vs_matched_random'))} | "
            f"{_sci(r.get('p_adj_vs_matched_random'))} | "
            f"{_f(r.get('effect_size_cohens_d'))} "
            f"[{_f(r.get('cohens_d_ci_lower'))}, {_f(r.get('cohens_d_ci_upper'))}] | "
            f"{_f(r.get('sharpe'), 2)} | "
            f"{'**yes**' if r.get('beats_matched_random') else 'no'} |"
        )
    L.append("")

    # ------------------------------------------------------------------
    # Distributional detail
    # ------------------------------------------------------------------
    L += [
        f"## 2. Distributional and risk detail (h = {PRIMARY_HOLDING_PERIOD})", "",
        "| Signal | Std | Skew | Kurt | Expectancy | Profit factor | Sortino | "
        "Calmar | Max DD | Avg MFE | Avg MAE |", "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for _, r in prim.iterrows():
        L.append(
            f"| `{r['signal']}` | {_p(r.get('std_return'))} | "
            f"{_f(r.get('skewness'), 2)} | {_f(r.get('kurtosis'), 2)} | "
            f"{_p(r.get('expectancy'), 3)} | {_f(r.get('profit_factor'), 2)} | "
            f"{_f(r.get('sortino'), 2)} | {_f(r.get('calmar'), 2)} | "
            f"{_p(r.get('max_drawdown'), 1)} | {_p(r.get('avg_mfe'))} | "
            f"{_p(r.get('avg_mae'))} |"
        )
    L.append("")

    # ------------------------------------------------------------------
    # Horizon sweep
    # ------------------------------------------------------------------
    L += [
        "## 3. Excess return over the matched-random null, by horizon", "",
        "A genuine edge should not appear at one horizon and vanish at the "
        "neighbouring ones.", "",
        "| Signal | " + " | ".join(f"h={h}" for h in HOLDING_PERIODS) + " |",
        "|---" + "|--:" * len(HOLDING_PERIODS) + "|",
    ]
    pivot = m.pivot_table(
        index="signal", columns="holding_period",
        values="excess_return_vs_matched_random", aggfunc="first",
    )
    order = prim["signal"].tolist()
    for sig in order:
        if sig not in pivot.index:
            continue
        cells = " | ".join(_p(pivot.loc[sig].get(h, np.nan)) for h in HOLDING_PERIODS)
        L.append(f"| `{sig}` | {cells} |")
    L.append("")

    # sign-consistency across horizons
    signs = np.sign(pivot[[h for h in HOLDING_PERIODS if h in pivot.columns]])
    consistent = (signs.abs().sum(axis=1) > 0) & (
        signs.sum(axis=1).abs() == signs.abs().sum(axis=1)
    )
    L += [
        f"**{int(consistent.sum())} of {len(pivot)} concepts keep the same sign of "
        "excess return at every horizon.** Sign flips across adjacent horizons are "
        "a symptom of noise rather than of a horizon-specific effect.", "",
    ]

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------
    beats = prim["beats_matched_random"].fillna(False)
    tested = prim[~prim["low_sample_warning"].fillna(True)]
    loses = (
        tested["reject_vs_matched_random"].fillna(False)
        & (tested["excess_return_vs_matched_random"] < 0)
    )
    L += [
        "## 4. Summary counts", "",
        f"At h = {PRIMARY_HOLDING_PERIOD}, of {len(prim)} concepts:", "",
        f"* **{int(beats.sum())}** beat the composition-matched random-entry null "
        f"after BH-FDR at alpha = {FDR_ALPHA};",
        f"* **{int(loses.sum())}** are significantly **worse** than it;",
        f"* **{len(prim) - int(beats.sum()) - int(loses.sum())}** are "
        "statistically indistinguishable from it;",
        f"* {int(prim['reject_vs_zero'].fillna(False).sum())} differ from a "
        "zero-return null -- a weak bar over a 16-year bull market that a "
        "long-biased signal clears on drift alone.", "",
    ]
    if int(beats.sum()):
        L += ["Concepts that clear the bar:", ""]
        for _, r in prim[beats].iterrows():
            L.append(
                f"* `{r['signal']}` -- excess "
                f"{_p(r['excess_return_vs_matched_random'])} over "
                f"{int(r['n_trades']):,} trades, "
                f"p(FDR) = {_sci(r.get('p_adj_vs_matched_random'))}, "
                f"d = {_f(r.get('effect_size_cohens_d'))}"
            )
        L.append("")

    path.write_text("\n".join(L), encoding="utf-8")
    log.info("Master summary written to %s", path)
    return path


if __name__ == "__main__":
    build_master_summary()
