# Review notes for maintainers

Branch: `ssrn-ready/claude-opus-5`

This is a large diff. These notes are ordered so you can stop reading at any
point and still have seen the parts that matter most.

---

## Read these five things first

If you only review five files, make them these. Each one either changed a
published number or prevents a class of error from recurring.

| # | File | Why |
|---|---|---|
| 1 | `analytics/statistics.py` | The one-sided tests, the matched-randomization null, and the calendar-time HAC estimator. Everything downstream depends on these three being right. |
| 2 | `signals/event_engine.py` | The fail-closed `EVENT_REGISTRY`. This is the structural fix for the look-ahead leak. |
| 3 | `tests/test_no_lookahead.py` | The proof, including the canary test that keeps the proof from going vacuous. |
| 4 | `CHANGES.md` | Every change with its rationale and measured impact. |
| 5 | `results/validation_report.md` | What the corrected pipeline actually produced, generated from the artefacts. |

---

## The four numbers that changed, and why

| Claim | Before | After |
|---|---|---|
| Concepts beating the random-entry benchmark | 28 / 42 | **5 / 44** |
| — of those, robust to their own parameters | not tested | **2** |
| Of those, actually better than the benchmark | 1 | 5 |
| Concepts significant vs. a zero-return null | 42 / 42 | 39 / 44 |
| Trades in the backtest | 34.6 M | 17.7 M |

The first row is not a like-for-like comparison and should not be read as one.
The old flag came from a **two-sided** test, so it counted concepts that
significantly *lost* to random entry. The second row is the like-for-like
number: of the 28 previously flagged, exactly one had a positive effect size.

The trade count halves because `ict_ndog_formed` (which fired on every bar,
45% of all events) and the two look-ahead `*_filled` columns were removed from
the tradeable set.

---

## Things I'd push back on if I were reviewing this

I've tried to list the weakest parts of my own work rather than leave you to
find them.

**1. Three of the five surviving concepts are ones I reformulated — and I
tested that directly, with one failing.** `ict_sweep_sellside_bullish`,
`ict_sweep_buyside_bearish` and `ict_nwog_gap_up` clear the bar only in the
corrected forms in this branch. In their original forms they were not testable
events at all (the "sweep" fired when price merely entered a liquidity pool; the
gap fired on every bar), so there was no prior result to preserve — but I chose
the new parameters, so I ran a 36-configuration targeted sweep over exactly
those parameters (`results/sensitivity_targeted_grid.csv`):

| Signal | Configs with positive excess |
|---|---:|
| `ict_sweep_buyside_bearish` | **36 / 36** |
| `ict_sweep_sellside_bullish` | **33 / 36** |
| `ict_nwog_gap_up` | 24 / 36 |

The two sweep detectors hold up, and the default X = 0.25 ATR is *not* the most
favourable setting (X = 0.10 gives a larger excess), so the result is not an
artefact of my choice.

**The gap detector does not hold up, and I withdraw it.** Its mean excess is
+2.6 bp at a 0.05 ATR threshold, **+0.4 bp at my default of 0.10**, and −1.6 bp
at 0.25 — the default sits essentially at the sign change. It clears FDR at one
parameter value and would not at a neighbouring one. The manuscript says so and
counts **two** robust concepts, not three. This is the single change I'd most
want a second opinion on.

**2. The sector and regime comparators changed, which changes those numbers a
lot.** The old sector table compared a roughly half-short signal population
against a long-only benchmark, which measures net directional exposure. That
produced a uniform −0.5 to −1.2 pp across all twelve sectors — a suspiciously
flat result that was an artefact. The new direction-matched comparison gives
−0.08 to −0.21 pp. I believe the new one is right, but it is a judgement call
about what the right comparator is, and it deserves a second opinion.

**3. Survivorship bias is acknowledged, not fixed.** The universe is a 2026
constituent snapshot applied to 2010–2026. I argue it largely cancels in the
matched comparison (the null is drawn from the same survivor-biased tickers),
but a point-in-time universe would be strictly better and I did not build one.
This is the study's largest unaddressed threat to validity.

**4. The bootstrap subsamples above 20,000 observations.** For large concepts
the bootstrap CI is computed on a 20,000-row subsample and is therefore *wider*
than the true CI — conservative, but not the interval a reader might assume.
The `ci_method` column records which path each row took, and the HAC interval
beside it is the one used for inference.

**5. `smc_swing_choch_bearish` should probably not be in the winners table.**
It has the largest excess (+0.33 pp) and the smallest sample (2,653 trades), and
its excess flips sign across horizons (+0.32 pp at h=10, −3.26 pp at h=60). It
clears FDR, so I report it, but I flag it in the manuscript as the least
reliable of the five rather than leading with it.

---

## What to verify, and how

```bash
pytest tests/ -v                          # 89 tests, ~15s, no network
python tools/check_artifacts.py           # acceptance criteria on results/
python tools/check_manuscript_numbers.py  # all 25 paper claims vs artefacts
./run_fast_validation.sh                  # hermetic end-to-end, 2-4 min
```

To confirm the two defects that mattered most, without taking my word for it:

```bash
# 1. The look-ahead was real, and the probe that finds it still works.
pytest tests/test_no_lookahead.py -v
#    test_forward_looking_label_is_correctly_identified_as_leaky is the canary:
#    it FAILS if the probe stops being able to detect a known leak.

# 2. The old baseline was irreproducible. On the previous commit:
git stash && git checkout master
for i in 1 2 3; do python -c "
import pandas as pd, hashlib
from backtest.baselines import random_entry
df = pd.read_parquet('data/bundle/prices/AAPL.parquet').sort_index()
m = random_entry(df, 50)['baseline_random_bullish'].to_numpy()
print(hashlib.md5(m.tobytes()).hexdigest()[:12])"; done
#    -> three different hashes. On this branch -> three identical hashes.
git checkout ssrn-ready/claude-opus-5 && git stash pop
```

---

## Structural changes worth knowing about

**`utils/prices.py` is new and now owns all price loading.** Four modules
previously re-implemented "read parquet, sort, drop duplicate index" inline and
had already drifted — only some deduplicated. They all route through one loader
now, which is what makes the OHLC repair apply everywhere rather than in three
places out of four.

**`analytics/master_stats.py` is new and is the single source of the numbers.**
`concept_ranking.py` is now a view onto `results/statistics_master.csv` rather
than a separate computation, so a ranking and the master table cannot disagree.

**`main.py` gained six stages** (`statistics`, `walkforward`, `costs`,
`montecarlo`, `sensitivity`, `report`) and a `--skip` flag. `all` excludes
`sensitivity`, which re-runs detection per grid point and would dominate
runtime.

**Detector parameters are now resolved at call time, not as default arguments.**
This was a real bug: `def detect(df, length=ICT.ob_swing_len)` freezes the value
at import, so the sensitivity sweep silently produced identical results at every
grid point (`std_excess` was exactly 0.0 for all 44 signals). `tests/
test_pipeline_integrity.py::TestParametersAreLateBound` guards it.

---

## Backwards compatibility

- `concept_rankings.csv` and `combination_rankings.csv` keep a
  `statistically_significant` column so the Gradio and Streamlit dashboards
  still work, **but its meaning changed**: it now requires beating the matched
  null, not merely differing from a pooled baseline in either direction. If you
  have anything else reading that column, check it.
- `ict_fvg_*_top` / `_bottom` are renamed `_lower` / `_upper` (the old names had
  inverted meaning, which is what made BPR unsatisfiable).
- `ict_ndog_formed` / `ict_nwog_formed` are replaced by directional
  `*_gap_up` / `*_gap_down`.
- The old `ict_liquidity_*_swept` columns are **kept** alongside the new
  `ict_sweep_*` ones, deliberately, so the reformulation is visible as a
  comparison rather than a silent substitution.

---

## Not done

- **Point-in-time universe.** See caveat 3 above. This is the one item from the
  brief I could not close: a survivorship-free constituent history is not
  available to this pipeline, and building one is a separate project.
- **The live sector lookup is implemented but not used.**
  `load_sector_map(source="live")` works; every published number uses the static
  map deliberately, because a live lookup would make results depend on when they
  were run. Use the live path to audit or extend `SECTOR_MAP`, not to generate
  results.
- **Launching the UIs.** I exercised all eight view functions in
  `dashboard/analysis.py` programmatically (and added
  `tests/test_pipeline_integrity.py::TestDashboardViews` so they stay
  exercised). `sector_regime_view` was genuinely broken by the column rename and
  is fixed. I have not started the Gradio or Streamlit servers and clicked
  through them, so layout-level problems could remain.
- **`docs/final_research_report.md`** is regenerated and correct, but it is
  superseded by `docs/manuscript.md`. You may want to delete it rather than
  maintain two overlapping documents.
