"""Verify that the numbers asserted in docs/manuscript.md match the artefacts.

A manuscript is written once and the pipeline is rerun many times. Each claim
below names three things:

* the value the paper states;
* the fact it rests on, recomputed *fresh* from results/ by the functions in
  tools/manuscript_facts.py (not read from a cached JSON);
* the literal text the paper uses for it.

The check fails if a recomputed fact has drifted from the stated value, or if
the text no longer appears in the manuscript. Either a rerun or an edit that
leaves the paper quietly wrong therefore fails CI-style, naming the claim.

Adding a numeric claim to the paper means adding it here.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MANUSCRIPT = ROOT / "docs" / "manuscript.md"


def _fresh_facts() -> dict:
    spec = importlib.util.spec_from_file_location(
        "manuscript_facts", ROOT / "tools" / "manuscript_facts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    F: dict = {"holding_period": mod.H}
    for step in (mod.headline, mod.universe, mod.calibration, mod.rotation,
                 mod.walkforward, mod.costs, mod.sectors_regimes, mod.survivorship,
                 mod.sweeps_mc_combos, mod.previous_version):
        step(F)
    return F


def _get(F: dict, path: str):
    """``a|b|c`` walks nested dicts/lists (keys may contain '.' and ':')."""
    cur = F
    for part in path.split("|"):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _winner(F, signal, key):
    return next(w[key] for w in F["positive_point_estimates"] if w["signal"] == signal)


def _top_se(F, signal, key):
    return next(r[key] for r in F["se_inflation_top5"] if r["signal"] == signal)


def claims(F: dict) -> list[tuple]:
    """(name, stated value, actual value, absolute tolerance, text in the paper)."""
    g = lambda p: _get(F, p)  # noqa: E731
    cal = lambda k: 100 * g(f"calibration|{k}")  # noqa: E731
    rat = lambda k: g(f"calibration_se_ratio|{k}")  # noqa: E731
    C = [
        # --- scope ---------------------------------------------------------
        ("concepts", 44, g("n_concepts"), 0, "44 formally specified"),
        ("hypotheses", 352, g("n_hypotheses"), 0, "all 352"),
        ("registered signals", 46, g("n_registered_signals"), 0, "declares 46 signals"),
        ("registered but never fire", 2, g("n_registered_never_fire"), 0,
         "registered but never fire"),
        ("tickers downloaded", 498, g("n_downloaded"), 0, "498 return data"),
        ("tickers with events", 496, g("n_tickers_with_events"), 0, "across 496 tickers"),
        ("events", 2_204_425, g("n_events"), 0, "2,204,425 events"),
        ("trades", 17_552_994, g("n_trades_total"), 0, "17,552,994 trades"),
        ("trades at h=10", 2_198_125, g("n_trades_at_h"), 0, "2,198,125"),
        ("long concepts", 22, g("n_long_concepts"), 0, "Twenty-two concepts are long"),
        ("tickers starting after 2010", 80, g("n_short_history_after_2010"), 0, None),
        ("material OHLC repairs", 3, len(g("ohlc_material_invalid_bars")), 0, "Three bars"),
        ("float-noise OHLC bars", 1301, g("ohlc_float_noise_bars"), 0, "1,301 bars"),
        # --- headline (Table 3) ----------------------------------------------
        ("beats, primary, h=10", 0, g("n_beats"), 0, "**0 / 44**"),
        ("beats, primary, all horizons", 0, sum(g("beats_by_horizon").values()), 0, "**0 / 352**"),
        ("loses, two-sided family, all", 0, g("n_loses_two_sided_all"), 0, None),
        ("sig vs zero, h=10", 38, g("n_sig_vs_zero"), 0, "38 / 44"),
        ("sig vs zero, all horizons", 268, g("n_sig_vs_zero_all"), 0, "268 / 352"),
        ("SRS beats, h=10", 4, g("n_beats_under_srs_test"), 0, "4 / 44"),
        ("SRS beats, all horizons", 28, g("n_beats_under_srs_all_horizons"), 0, "28 / 352"),
        ("rotation beats, all", 0, g("rot_n_beats"), 0, None),
        ("rotation loses, all", 54, g("rot_n_loses"), 0, "flag 54 hypotheses"),
        ("rotation loses, h=10", 5, g("rot_n_loses_h"), 0, "(5 at h = 10)"),
        ("rotation offsets min", 4014, g("rot_offsets|min"), 0, "4,014–4,132"),
        ("rotation offsets max", 4132, g("rot_offsets|max"), 0, None),
        ("mean excess, all concepts (bp)", -11.0, g("mean_excess_all_bp"), 0.05, "−11.0 bp"),
        ("positive point estimates", 7, g("n_positive_excess_h"), 0, "Seven concepts"),
        ("min one-sided p, all horizons", 0.062, g("min_p_primary_all"), 0.0005, "is 0.062"),
        ("min one-sided p, h=10", 0.229, g("min_p_primary_h"), 0.0005, "it is 0.229"),
        ("min two-sided adjusted p", 0.061, g("min_p_adj_two_sided_all"), 0.0005, "is 0.061"),
        # --- Table 1: calibration --------------------------------------------
        ("cal independent srs", 5.7, cal("independent:srs"), 0.05, "5.7% (0.98)"),
        ("cal independent calendar", 0.0, cal("independent:calendar"), 0.05, "0.0% (1.80)"),
        ("cal independent rotation", 5.8, cal("independent:rotation"), 0.05, "5.8% (0.98)"),
        ("cal semi srs", 28.1, cal("semi:srs"), 0.05, "**28.1%** (0.50)"),
        ("cal semi calendar", 3.5, cal("semi:calendar"), 0.05, "3.5% (1.27)"),
        ("cal semi rotation", 7.3, cal("semi:rotation"), 0.05, "7.3% (1.03)"),
        ("cal clustered srs", 40.6, cal("clustered:srs"), 0.05, "**40.6%** (0.24)"),
        ("cal clustered calendar", 6.8, cal("clustered:calendar"), 0.05, "6.8% (1.11)"),
        ("cal clustered rotation", 6.9, cal("clustered:rotation"), 0.05, "6.9% (1.02)"),
        ("cal sim_independent srs", 5.1, cal("sim_independent:srs"), 0.05, "5.1% (1.01)"),
        ("cal sim_independent calendar", 0.0, cal("sim_independent:calendar"), 0.05, "0.0% (2.02)"),
        ("cal sim_independent rotation", 5.0, cal("sim_independent:rotation"), 0.05, "5.0% (1.02)"),
        ("cal sim_clustered srs", 34.3, cal("sim_clustered:srs"), 0.05, "**34.3%** (0.22)"),
        ("cal sim_clustered calendar", 3.0, cal("sim_clustered:calendar"), 0.05, "3.0% (1.10)"),
        ("cal sim_clustered rotation", 4.4, cal("sim_clustered:rotation"), 0.05, "4.4% (0.99)"),
        ("cal sim_vol_timed srs", 38.3, cal("sim_vol_timed:srs"), 0.05, "**38.3%** (0.14)"),
        ("cal sim_vol_timed calendar", 5.0, cal("sim_vol_timed:calendar"), 0.05, "5.0% (0.87)"),
        ("cal sim_vol_timed rotation", 18.8, cal("sim_vol_timed:rotation"), 0.05, "**18.8%** (0.45)"),
        ("SE ratio vol-timed rotation", 0.45, rat("sim_vol_timed:rotation"), 0.005, None),
        ("calibration reps", 1000, g("calibration_reps|calendar"), 0, "1,000 replications"),
        # --- SE inflation (Table 2) --------------------------------------------
        ("SE inflation vs zero, min", 1.6, g("se_inflation_vs_zero|min"), 0.05, "between 1.6"),
        ("SE inflation vs zero, max", 12.3, g("se_inflation_vs_zero|max"), 0.05, "and 12.3 times"),
        ("SE inflation vs zero, median", 6.2, g("se_inflation_vs_zero|median"), 0.05, "median of 6.2"),
        ("calendar/SRS SE, median", 7.0, g("matched_se_calendar_over_srs|median"), 0.05, "median 7.0"),
        ("calendar/SRS SE, min", 1.4, g("matched_se_calendar_over_srs|min"), 0.05, "range 1.4–16.2"),
        ("calendar/SRS SE, max", 16.2, g("matched_se_calendar_over_srs|max"), 0.05, None),
        ("gap-down effective n", 890,
         _top_se(F, "ict_nwog_gap_down", "n_trades") / _top_se(F, "ict_nwog_gap_down", "ratio") ** 2,
         15, "890 independent observations"),
        ("gap-down entry dates", 851, g("entry_dates_h|ict_nwog_gap_down"), 0, "its 851 distinct"),
        # --- Table 4 -----------------------------------------------------------
        *[(f"excess {s}", v, _winner(F, s, "excess_bp"), 0.05, None) for s, v in [
            ("smc_swing_choch_bearish", 32.5), ("smc_swing_ob_bearish_formed", 19.4),
            ("ict_sweep_sellside_bullish", 11.9), ("ict_sweep_buyside_bearish", 11.4),
            ("ict_liquidity_buyside_pool_formed", 5.8), ("ict_nwog_gap_up", 4.8),
            ("smc_swing_choch_bullish", 3.9)]],
        *[(f"SE {s}", v, _winner(F, s, "se_bp"), 0.05, None) for s, v in [
            ("smc_swing_choch_bearish", 115.3), ("ict_sweep_sellside_bullish", 21.3),
            ("ict_sweep_buyside_bearish", 15.3), ("ict_nwog_gap_up", 17.9)]],
        ("SRS SE ict_nwog_gap_up", 1.5, _winner(F, "ict_nwog_gap_up", "se_srs_bp"), 0.05,
         "standard error of 1.5 bp"),
        ("p sweep buyside", 0.23, _winner(F, "ict_sweep_buyside_bearish", "p"), 0.005, None),
        ("p sweep sellside", 0.29, _winner(F, "ict_sweep_sellside_bullish", "p"), 0.005, None),
        ("rotation p sweep buyside", 0.10, g("rot_h|ict_sweep_buyside_bearish|p"), 0.005, None),
        ("rotation p choch bearish", 0.16, g("rot_h|smc_swing_choch_bearish|p"), 0.005, None),
        # --- power (Table 5) ---------------------------------------------------
        ("median SE (bp)", 18.2, g("power|se_median_bp"), 0.05, "is 18.2 bp"),
        ("median MDE (bp)", 45, g("power|mde_median_bp"), 0.5, "edge is 45"),
        ("best MDE (bp)", 27, g("power|mde_min_bp"), 0.5, "concept's is 27 bp"),
        ("upper bound < 0", 3, g("power|n_upper95_below_0"), 0, "| below 0 bp | 3 |"),
        ("upper bound < 11", 10, g("power|n_upper95_below_11"), 0, "Ten concepts have a bound"),
        ("upper bound < 26", 27, g("power|n_upper95_below_26"), 0, "| 11 to 26 bp | 17 |"),
        ("sweep buyside upper bound", 37, _winner(F, "ict_sweep_buyside_bearish", "upper95_bp"), 0.5,
         "bounds of 37 and 47 bp"),
        ("sweep sellside upper bound", 47, _winner(F, "ict_sweep_sellside_bullish", "upper95_bp"), 0.5,
         None),
        # --- walk-forward (Table 6) -------------------------------------------
        ("walk-forward folds", 13, g("wf_folds"), 0, "13 folds"),
        ("WF in-sample (bp)", 61.3, g("wf_mean_train_excess_selected_bp"), 0.05, "+61.3 bp"),
        ("WF out-of-sample (bp)", -39.3, g("wf_mean_test_excess_selected_bp"), 0.05, "**−39.3 bp**"),
        ("WF all concepts (bp)", -35.0, g("wf_mean_test_excess_all_bp"), 0.05, "−35.0 bp"),
        ("WF positive folds", 5, g("wf_folds_positive_test_excess"), 0, "5 / 13"),
        ("WF hit rate (%)", 36.9, 100 * g("wf_mean_hit_rate"), 0.05, "36.9%"),
        ("WF rank correlation", 0.34, g("wf_mean_rank_corr"), 0.005, "| 0.34 |"),
        ("WF 2013-2020 (bp)", 6.1, g("wf_test_bp_2013_2020"), 0.05, "average +6.1 bp"),
        ("WF 2021-2023 (bp)", -160.6, g("wf_test_bp_2021_2023"), 0.05, "average −160.6 bp"),
        ("WF 2021-2023 train (bp)", 193.1, g("wf_train_bp_2021_2023"), 0.05, "+193.1 bp"),
        ("WF other train (bp)", 21.8, g("wf_train_bp_other"), 0.05, "+21.8 bp"),
        # --- costs ---------------------------------------------------------------
        ("gross break-even > 26", 22, g("be_gross_over_26"), 0, "22 of 44 concepts clear"),
        ("gross break-even > 26, all long", 22, g("be_gross_over_26_n_long"), 0, "exactly the 22 long"),
        ("excess break-even > 11", 4, g("be_excess_over_11"), 0, "4 concepts clear 11 bp"),
        ("excess break-even > 26", 1, g("be_excess_over_26"), 0, "1 clears 26 bp"),
        ("mean gross, long (bp)", 63, g("mean_gross_long_bp"), 0.5, "is 63 bp"),
        ("mean null, long (bp)", 71, g("mean_null_long_bp"), 0.5, "earns 71 bp"),
        # --- sensitivity (Table 7) ----------------------------------------------
        ("broad grid responders", 18, g("broad_grid_signals_responding"), 0, "moves 18 of the"),
        *[(f"sweep positive {s}", v, g(f"sweep|{s}|positive"), 0, None) for s, v in [
            ("ict_sweep_sellside_bullish", 33), ("ict_sweep_buyside_bearish", 36),
            ("ict_nwog_gap_up", 24), ("ict_nwog_gap_down", 0)]],
        *[(f"sweep significant {s}", 0, g(f"sweep|{s}|p_below_05"), 0, None) for s in [
            "ict_sweep_sellside_bullish", "ict_sweep_buyside_bearish",
            "ict_nwog_gap_up", "ict_nwog_gap_down"]],
        ("sweep smallest p", 0.11, g("sweep|ict_sweep_sellside_bullish|min_p"), 0.005,
         "smallest p = 0.11"),
        ("gap excess at 0.05 ATR", 2.6, g("gap_excess_by_threshold_bp|0.05"), 0.05, "+2.6 bp"),
        ("gap excess at 0.10 ATR", 0.4, g("gap_excess_by_threshold_bp|0.1"), 0.05, "+0.4 bp"),
        ("gap excess at 0.25 ATR", -1.6, g("gap_excess_by_threshold_bp|0.25"), 0.05, "−1.6 bp"),
        # --- survivorship (Table 8) ---------------------------------------------
        ("survivorship scope: constituents with data", 498, int(g("surv|current_constituents")), 0,
         "of the 498 constituents with"),
        ("members at start", 265, int(g("surv|in_index_at_sample_start")), 0, "265 were index members"),
        ("joined during sample", 233, int(g("surv|joined_during_sample")), 0, "233 joined"),
        ("removed members missing", 235, int(g("surv|estimated_removed_names_missing")), 0,
         "at least 235 of the 500"),
        ("survivorship gap (%)", 47.0, float(g("surv|estimated_survivorship_gap_pct")), 0.05,
         "— 47% —"),
        ("aware trades", 1_763_667, g("surv_cmp|trades_membership_aware"), 0, "1,763,667"),
        ("trades dropped (%)", 19.8, g("surv_cmp|trades_dropped_pct"), 0.05, "19.8%"),
        ("beats, full", 0, g("surv_cmp|n_beats_full"), 0, None),
        ("beats, aware", 0, g("surv_cmp|n_beats_membership_aware"), 0, None),
        ("sign preserved (%)", 97.7, g("surv_cmp|sign_preserved_pct"), 0.05, "97.7%"),
        ("median shift (bp)", 0.88, g("surv_cmp|median_excess_shift_bps"), 0.005, "0.88 bp"),
        # --- sectors and regimes -------------------------------------------------
        ("sectors", 11, g("n_sectors"), 0, "one of 11 GICS"),
        ("positive sectors", 1, g("n_sectors_positive"), 0, None),
        ("energy excess (bp)", 5.4, g("sector_excess_bp|Energy"), 0.05, "+5.4 bp, 21 tickers"),
        ("energy tickers", 21, g("sector_n_tickers|Energy"), 0, None),
        ("BH-significant sectors", 2, len(g("sectors_significant_bh")), 0, None),
        ("utilities adjusted p", 0.029, g("sector_p_adj|Utilities"), 0.0005, "p = 0.029"),
        ("staples adjusted p", 0.029, g("sector_p_adj|Consumer Staples"), 0.0005, None),
        ("sector MDE min", 14.7, g("sector_mde_bp|min"), 0.05, "14.7 to 57.1 bp"),
        ("sector MDE max", 57.1, g("sector_mde_bp|max"), 0.05, None),
        ("powered sectors", 0, g("n_sectors_powered"), 0, None),
        ("curated map missing", 54, g("curated_map_missing"), 0, "left 54 constituents"),
        ("curated map wrong", 6, g("curated_map_mismatch"), 0, "mis-classified six"),
        # --- the previous version ----------------------------------------------
        ("old concepts", 42, g("old_n_concepts"), 0, "28 of 42"),
        ("old flagged", 28, g("old_n_flagged_vs_baseline"), 0, None),
        ("old flagged, negative", 27, g("old_flagged_with_negative_effect"), 0, "**27 had a negative"),
        ("old look-ahead events", 187_719, g("old_leaky_events"), 0, "187,719"),
        ("old look-ahead trades h=10", 187_374, g("old_leaky_trades_at_h10"), 0, "187,374 trades"),
        ("old events", 4_348_698, g("old_n_events"), 0, "4,348,698-event"),
        ("old NDOG events", 1_946_675, g("old_ndog_events"), 0, "1,946,675 events"),
        ("old NDOG share (%)", 44.8, g("old_ndog_share_pct"), 0.05, "44.8%"),
    ]
    return C


def main() -> int:
    try:
        F = _fresh_facts()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not recompute the facts: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    raw = MANUSCRIPT.read_text(encoding="utf-8")
    # Markdown (and the YAML abstract block, indented two spaces per line)
    # soft-wraps prose at ~80 columns; a single newline inside a paragraph
    # renders as a space, not a line break, in the built PDF/HTML. A snippet
    # check must read the text the way a reader (or the PDF) does, not the way
    # it happens to be wrapped -- and indented -- in the source, or a
    # rewording that merely shifts where a wrap falls produces a false
    # failure with no change in what the paper actually says. De-indent every
    # line first, then collapse intra-paragraph newlines to spaces; blank
    # lines and lines starting a heading/list/table/quote stay as breaks.
    text = re.sub(r"\n[ \t]+", "\n", raw)
    text = re.sub(r"(?<!\n)\n(?![\n#>*\-|])", " ", text)

    failures = []
    for name, stated, actual, tol, snippet in claims(F):
        # Facts are rounded; the margin absorbs binary float error at the boundary
        # (5.4 - 5.35 is 0.0500000000000007, not 0.05).
        ok_value = actual is not None and abs(float(stated) - float(actual)) <= tol + 1e-9
        ok_text = snippet is None or snippet in text
        status = "ok  " if ok_value and ok_text else "FAIL"
        note = "" if ok_text else f"   [text not found: {snippet!r}]"
        print(f"  {status} {name:<38} paper={stated!s:<11} artefact={actual}{note}")
        if not (ok_value and ok_text):
            failures.append(name)

    print()
    if failures:
        print(f"{len(failures)} manuscript claim(s) do not match the artefacts or the text:",
              file=sys.stderr)
        for name in failures:
            print(f"  - {name}", file=sys.stderr)
        return 1
    print(f"All {len(claims(F))} manuscript claims match the artefacts and the text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
