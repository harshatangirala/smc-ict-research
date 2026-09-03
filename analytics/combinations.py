"""Combination Analysis (Task 11): evaluate same-direction concept pairs that
co-occur on the same (ticker, date) -- e.g. BOS + FVG, CHoCH + Order Block --
and rank them, with a minimum-occurrence floor and FDR correction applied
across every combination tested to avoid data snooping.
"""

from __future__ import annotations

from itertools import combinations as itertools_combinations

import pandas as pd

from analytics.statistics import (
    apply_fdr_correction,
    build_return_pools,
    matched_randomization_test,
    one_sample_significance,
    two_sample_significance,
)
import numpy as np

from backtest.engine import _compute_trades_for_ticker, _load_price_cache
from backtest.metrics import summarize_returns
from utils.config import (
    HOLDING_PERIODS,
    MAX_COMBOS_TESTED as _MAX_COMBOS_TESTED,
    MIN_COMBO_OCCURRENCES as _MIN_COMBO_OCCURRENCES,
    PRIMARY_HOLDING_PERIOD,
    RESULTS_DIR,
)
from utils.logging_config import get_logger

log = get_logger("analytics.combinations")

# Sourced from utils.config so the bound is visible with the other study
# parameters rather than buried here. Raised from 30 to 100: a 30-trade
# combination cannot support a claim, and admitting them inflated the family
# size that BH-FDR then had to correct across.
MIN_COMBO_OCCURRENCES = _MIN_COMBO_OCCURRENCES
MAX_COMBOS_TESTED = _MAX_COMBOS_TESTED


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def build_combo_events(master_events: pd.DataFrame) -> pd.DataFrame:
    """From the master event table, find same-direction signal pairs that
    fired on the same (ticker, date), and materialize them as synthetic
    "combo" events with the same schema the backtest engine expects.
    """
    grouped = master_events.groupby(["ticker", "date", "direction"])["signal"].apply(list).reset_index()
    grouped = grouped[grouped["signal"].apply(len) >= 2]

    combo_rows = []
    for row in grouped.itertuples(index=False):
        sigs = sorted(set(row.signal))
        for a, b in itertools_combinations(sigs, 2):
            combo_rows.append((row.ticker, row.date, f"{a}+{b}", row.direction))

    combos = pd.DataFrame(combo_rows, columns=["ticker", "date", "signal", "direction"])
    if combos.empty:
        return combos

    counts = combos["signal"].value_counts()
    frequent = counts[counts >= MIN_COMBO_OCCURRENCES].head(MAX_COMBOS_TESTED).index
    log.info("Found %d distinct combos with >=%d occurrences (testing top %d)",
              len(counts[counts >= MIN_COMBO_OCCURRENCES]), MIN_COMBO_OCCURRENCES, len(frequent))
    return combos[combos["signal"].isin(frequent)]


def backtest_combos(combo_events: pd.DataFrame) -> pd.DataFrame:
    prices = _load_price_cache()
    frames = []
    for ticker, grp in combo_events.groupby("ticker"):
        if ticker not in prices:
            continue
        frames.append(_compute_trades_for_ticker(ticker, prices[ticker], grp, HOLDING_PERIODS))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def rank_combinations(holding_period: int = PRIMARY_HOLDING_PERIOD) -> pd.DataFrame:
    """Rank co-occurring same-direction concept pairs against a matched null."""
    master_events = pd.read_parquet(RESULTS_DIR / "master_events.parquet")
    combo_events = build_combo_events(master_events)
    if combo_events.empty:
        log.warning("No combinations met the minimum-occurrence threshold")
        return pd.DataFrame()

    combo_trades = backtest_combos(combo_events)
    combo_trades.to_parquet(RESULTS_DIR / "combo_trades.parquet")

    baseline_trades = _load_baseline_trades()
    baseline_subset = (
        baseline_trades[baseline_trades["holding_period"] == holding_period] if baseline_trades is not None else None
    )

    pools = None
    try:
        prices = {t: df.set_index("date") for t, df in _load_price_cache().items()}
        pools = build_return_pools(prices, [holding_period])
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not build matched-null pools for combinations: %s", exc)

    subset = combo_trades[combo_trades["holding_period"] == holding_period]
    rows = []
    for signal, grp in subset.groupby("signal"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        sig = one_sample_significance(grp["fwd_return"].to_numpy())
        row = {"combination": signal, **metrics, "p_value": sig["p_value"], "effect_size_cohens_d": sig["effect_size_cohens_d"]}
        if baseline_subset is not None and not baseline_subset.empty:
            vs_baseline = two_sample_significance(
                grp["fwd_return"].to_numpy(),
                baseline_subset["fwd_return"].to_numpy(),
                alternative="greater",
            )
            row["p_value_vs_baseline"] = vs_baseline["p_value"]
            row["effect_size_vs_baseline"] = vs_baseline["effect_size_cohens_d"]
        # Composition-matched null, as used for individual concepts.
        if pools is not None:
            mr = matched_randomization_test(
                grp.groupby("ticker").size().to_dict(),
                float(grp["fwd_return"].mean()),
                int(grp["direction"].iloc[0]),
                pools,
                holding_period,
            )
            row["matched_null_mean"] = mr["null_mean"]
            row["excess_return_vs_matched_random"] = mr["excess_return"]
            row["p_value_vs_matched_random"] = mr["p_value"]
        rows.append(row)

    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking

    # Same two-test framework as analytics/concept_ranking.py: significance
    # vs. a zero-return null is a weak test over a long bull market; the
    # headline `statistically_significant` flag requires clearing FDR vs.
    # the random-entry baseline where available.
    fdr_zero = apply_fdr_correction(ranking.set_index("combination")["p_value"])
    ranking = ranking.merge(
        fdr_zero[["p_adjusted", "reject_null"]].rename(columns={"p_adjusted": "p_adjusted_vs_zero", "reject_null": "significant_vs_zero"}),
        left_on="combination", right_index=True, how="left",
    )

    if "p_value_vs_baseline" in ranking.columns:
        fdr_baseline = apply_fdr_correction(ranking.set_index("combination")["p_value_vs_baseline"])
        ranking = ranking.merge(
            fdr_baseline[["p_adjusted", "reject_null"]].rename(columns={"p_adjusted": "p_adjusted_vs_baseline", "reject_null": "significant_vs_baseline"}),
            left_on="combination", right_index=True, how="left",
        )
    else:
        ranking["significant_vs_baseline"] = pd.NA

    if "p_value_vs_matched_random" in ranking.columns:
        fdr_matched = apply_fdr_correction(
            ranking.set_index("combination")["p_value_vs_matched_random"]
        )
        ranking = ranking.merge(
            fdr_matched[["p_adjusted", "reject_null"]].rename(
                columns={"p_adjusted": "p_adj_vs_matched_random",
                         "reject_null": "reject_vs_matched_random"}),
            left_on="combination", right_index=True, how="left",
        )

    ranking["low_sample_warning"] = ranking["n_trades"] < MIN_COMBO_OCCURRENCES

    # Headline flag: a positive excess over the composition-matched null that
    # survives FDR, on an adequate sample. The previous definition accepted a
    # two-sided result against a pooled baseline, so a combination that
    # significantly LOST to random entry was reported as significant.
    if "reject_vs_matched_random" in ranking.columns:
        ranking["beats_matched_random"] = (
            ranking["reject_vs_matched_random"].fillna(False).astype(bool)
            & (ranking["excess_return_vs_matched_random"].fillna(-np.inf) > 0)
            & ~ranking["low_sample_warning"]
        )
    else:
        ranking["beats_matched_random"] = False
    ranking["statistically_significant"] = ranking["beats_matched_random"]

    sort_key = (
        "excess_return_vs_matched_random"
        if "excess_return_vs_matched_random" in ranking.columns else "sharpe"
    )
    return ranking.sort_values(sort_key, ascending=False, na_position="last").reset_index(drop=True)
