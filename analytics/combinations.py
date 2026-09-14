"""Combination Analysis (Task 11): evaluate same-direction concept pairs that
co-occur on the same (ticker, date) -- e.g. BOS + FVG, CHoCH + Order Block --
and rank them, with a minimum-occurrence floor and FDR correction applied
across every combination tested to avoid data snooping.
"""

from __future__ import annotations

from itertools import combinations as itertools_combinations

import pandas as pd

from analytics.statistics import apply_fdr_correction, one_sample_significance_clustered, two_sample_significance_clustered
from backtest.engine import _compute_trades_for_ticker, _load_price_cache
from backtest.metrics import summarize_returns
from utils.config import HOLDING_PERIODS, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("analytics.combinations")

MIN_COMBO_OCCURRENCES = 30
MAX_COMBOS_TESTED = 60  # cap the search space -- a deliberate anti-data-snooping bound


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


def rank_combinations(holding_period: int = 10) -> pd.DataFrame:
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

    subset = combo_trades[combo_trades["holding_period"] == holding_period]
    rows = []
    for signal, grp in subset.groupby("signal"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        returns = grp["fwd_return"].to_numpy()
        clusters = grp["ticker"].to_numpy()
        sig = one_sample_significance_clustered(returns, clusters)
        row = {"combination": signal, **metrics, "p_value": sig["p_value"], "effect_size_cohens_d": sig["effect_size_cohens_d"]}
        if baseline_subset is not None and not baseline_subset.empty:
            vs_baseline = two_sample_significance_clustered(
                returns, clusters, baseline_subset["fwd_return"].to_numpy(), baseline_subset["ticker"].to_numpy()
            )
            row["p_value_vs_baseline"] = vs_baseline["p_value"]
            row["effect_size_vs_baseline"] = vs_baseline["effect_size_cohens_d"]
            row["excess_return_vs_baseline"] = vs_baseline["excess_return_vs_baseline"]
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

    ranking["low_sample_warning"] = ranking["n_trades"] < MIN_COMBO_OCCURRENCES

    # See analytics/concept_ranking.py -- `significant_vs_baseline` alone is
    # two-sided ("differs from baseline"); `beats_baseline` additionally
    # requires the excess return to be positive.
    if "excess_return_vs_baseline" in ranking.columns:
        ranking["beats_baseline"] = (
            ranking["significant_vs_baseline"].fillna(False)
            & (ranking["excess_return_vs_baseline"] > 0)
        )
    else:
        ranking["beats_baseline"] = False

    ranking["statistically_significant"] = (
        ranking["significant_vs_baseline"].fillna(ranking["significant_vs_zero"]).fillna(False)
        & ~ranking["low_sample_warning"]
    )

    return ranking.sort_values("sharpe", ascending=False, na_position="last").reset_index(drop=True)
