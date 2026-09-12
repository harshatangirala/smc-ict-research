# Review notes for maintainers

Branch: `ssrn-ready/claude-opus-5`

This is a large diff. These notes are ordered so you can stop reading at any
point and still have seen the parts that matter most.

---

## Read these five things first

| # | File | Why |
|---|---|---|
| 1 | `analytics/statistics.py` | The composition-matched excess and `matched_excess_calendar_test`, which every headline count uses. |
| 2 | `tools/calibration_study.py` and `results/test_calibration.csv` | Why that test, and not the other two. |
| 3 | `signals/event_engine.py` | The fail-closed `EVENT_REGISTRY` — the structural fix for the look-ahead leak. |
| 4 | `tests/test_no_lookahead.py`, `tests/test_ob_fidelity.py` | The proofs, including the canary that keeps the look-ahead proof from going vacuous. |
| 5 | `CHANGES.md` §1 and §8 | Every defect, in the original pipeline and in this branch's own first draft, with measured impact. |

---

## The numbers that changed, and why

| Claim | Original | First draft of this branch | Now |
|---|---:|---:|---:|
| Concepts beating the random-entry benchmark (h = 10) | 28 / 42 | 5 / 44 | **0 / 44** |
| — of those, actually better than the benchmark | 1 | 5 | 0 |
| Hypotheses beating it, all horizons | — | — | 0 / 352 |
| Concepts significant against a zero-return null (h = 10) | 42 / 42 | 39 / 44 | 38 / 44 |
| Events | 4,348,698 | 2,226,881 | 2,204,425 |
| Trades | 34.6 M | 17.7 M | 17.6 M |

The first row is not a like-for-like comparison. The original flag came from a
**two-sided** test, so it counted concepts that significantly *lost* to random
entry: of its 28, exactly one had a positive effect size.

The first draft's 5 came from a variance formula that is exact only when entry
dates are independent (CHANGES §8.1) — on the corrected data it still reports 4
winners, against none from the calendar-time test — plus an order-block
detector that selected the wrong candle (§8.2).

The event and trade counts fell because `ict_ndog_formed` (which fired on every
bar, 45% of all events) and the two look-ahead `*_filled` columns left the
tradeable set; the order-block fix moved the count again slightly.

---

## Things I'd push back on if I were reviewing this

I've tried to list the weakest parts of my own work rather than leave you to
find them.

**1. I changed the primary test after seeing results.** The switch from the
SRS variance to the calendar-time test came after the first draft had reported
five winners. I think it is right — the calibration study shows the SRS variance
rejecting 28–41% of uninformative clustered signals, and it was validated only by
a simulation that shared its assumption — but it is a forking path, and you
should hear it from me. What limits the damage: the switch moved toward *fewer*
rejections, which cannot manufacture a null result; all three tests' p-values are
in `statistics_master.csv` and `rotation_null_all.csv`; and the calibration study
is deterministic and reproducible. The simulated designs, including the
volatility-timed one that decides between calendar-time and rotation, were fixed
before the full-universe rotation results were seen.

**2. The primary test is conservative when signals are dispersed.** It rejects
0% of uninformative signals whose entries are spread independently across
dates, because its Newey–West sum counts cross-ticker co-movement that does not
enter the true variance. I chose it anyway because it is the only one of the
three tests that stays near nominal when entries cluster or crowd into volatile
periods — which is how these signals behave. The cost is power, and the paper
leads with what the data can and cannot exclude (manuscript Table 5) rather than
letting "no concept beats the null" be read as "no concept has an edge".

**3. The rotation test flags 54 hypotheses as significantly worse than rotated
timing; the primary test flags none.** They are mostly displacement and
break-of-structure detectors, which fire on large-range bars. I discount the
rotation result because the calibration study shows it rejecting 19% of
uninformative volatility-timed signals. That is a judgement. If those negative
excesses are real — short-term reversal would predict them — the paper
understates a negative finding. It does not affect the headline.

**4. Survivorship is only partly fixed.** Trading a firm before it joined the
index is removed exactly by the membership-aware re-test (no concept beats the
null either way). The at least 235 since-removed members cannot be recovered
from free sources.

**5. I chose the parameters of the reformulated detectors.** The sweep and gap
detectors had to be reformulated to be testable at all, which means I picked X,
Z and the gap threshold. The targeted sweep shows the sweep detectors' sign is
stable across that space (36/36 and 33/36) but never significant, and that the
gap threshold decides the gap detector's sign. It runs on 30 tickers.

**6. The bootstrap subsamples above 20,000 observations.** Large concepts get a
bootstrap CI from a 20,000-row subsample — wider than the true CI, so
conservative, but not what a reader might assume. `ci_method` records which path
each row took; inference uses the calendar-time standard error, not the bootstrap.

---

## What to verify, and how

```bash
pytest tests/ -v                          # 121 tests, ~30 s, no network
python tools/check_artifacts.py           # acceptance criteria on results/
python tools/check_manuscript_numbers.py  # every paper number vs artefacts and text
python tools/calibration_study.py         # Table 1 of the paper, ~20 min on 6 cores
./run_fast_validation.sh                  # hermetic end-to-end, 2-4 min
```

To confirm the defects that mattered most without taking my word for it:

```bash
# 1. The look-ahead was real, and the probe that finds it still works.
pytest tests/test_no_lookahead.py -v
#    test_forward_looking_label_is_correctly_identified_as_leaky is the canary.

# 2. The SRS variance is anti-conservative for clustered signals.
pytest tests/test_audit_regressions.py -v -k calibration

# 3. The order block is the Pine source's candle, not its mirror image.
pytest tests/test_ob_fidelity.py -v
```

---

## Structural changes worth knowing about

**`analytics/master_stats.py` is the single source of the numbers.** Concept
rankings are views onto `results/statistics_master.csv`, so a ranking and the
master table cannot disagree. It now also carries the SRS p-value (for
comparison) and a separate two-sided family (`loses_to_matched_random`).

**`tools/manuscript_facts.py` computes every number the paper quotes**, and
`tools/check_manuscript_numbers.py` recomputes them fresh and checks that each
still appears in the manuscript text.

**`analytics/montecarlo.py::rotation_null_exact`** enumerates every rotation by
FFT; `main.py montecarlo` runs it for all 352 hypotheses in about a minute.

**`utils/universe.py`** owns sector labels (GICS) and index-entry dates, from a
committed snapshot that the pipeline never refreshes on its own.

**Detector parameters are resolved at call time, not as default arguments.**
`def detect(df, length=ICT.ob_swing_len)` froze the value at import, so the
sensitivity sweep silently produced identical results at every grid point.
`tests/test_pipeline_integrity.py::TestParametersAreLateBound` guards it.

---

## Backwards compatibility

- `concept_rankings.csv` and `combination_rankings.csv` keep a
  `statistically_significant` column for the dashboards, **but its meaning
  changed**: it now requires beating the matched null under the calendar-time
  test. Anything else reading that column should be checked.
- Sector names are now GICS; `Unknown` no longer appears.
- `monte_carlo.csv` rotation columns are exact (all offsets), not sampled.
- `ict_fvg_*_top` / `_bottom` are renamed `_lower` / `_upper`;
  `ict_ndog_formed` / `ict_nwog_formed` are replaced by directional
  `*_gap_up` / `*_gap_down`; the old `ict_liquidity_*_swept` columns are kept
  beside the new `ict_sweep_*` ones, deliberately.

---

## Not done

- **A point-in-time universe.** See item 4 above.
- **An independent audit.** Auditor subagents were requested for this work; every
  launch failed on a session rate limit. The audit in `CHANGES.md` §8 was done
  directly, by the same process that wrote the code, and is not an independent
  review.
- **Launching the UIs.** All eight view functions in `dashboard/analysis.py` are
  exercised programmatically (`TestDashboardViews`); the Gradio and Streamlit
  servers have not been clicked through.
- **`docs/final_research_report.md`** is regenerated from the artefacts but is
  superseded by `docs/manuscript.md`; consider deleting it.
