# Disambiguation register

Every point at which the Pine source admits more than one reading, the reading
this study implements, and why. A referee who disagrees with a choice here can
find the affected code and results from the table.

This is the artefact the brief asks for under "auto-generate a disambiguation
… with suggested formalization and rationale". It is maintained by hand rather
than generated, because the useful content is the *argument* for each reading,
which no tool can produce. `tools/reviewer_check.py` links to it, and
`tests/test_pipeline_integrity.py` enforces that every registered signal has a
specification in `docs/specs/`.

Severity is how much the choice could move a published number:
**high** = could change which concepts clear significance;
**medium** = changes event counts materially;
**low** = cosmetic or provably no-effect.

---

## A1 — "IFVG" means the opposite of the standard definition · low

**Ambiguity.** `ICT_Concepts_LuxAlgo.pine` offers an `FVG`/`IFVG` mode. In the
wider ICT literature an *inverse* FVG is a gap that has been filled and then
acts as support/resistance from the other side. In the source, `IFVG` simply
inverts the gap inequality (`low < high[2]` rather than `low > high[2]`), which
detects a *non*-gap.

**Chosen.** Implement the source's literal behaviour, default to `FVG`.

**Rationale.** The study tests these implementations, not the literature. The
source's own default is `FVG`, so no published number depends on this.
**Where:** `signals/ict_signals.py::detect_fvg`, `docs/specs/ict_fvg.yaml`.

## A2 — FVG "fill" is defined with hindsight · high

**Ambiguity.** A gap is conventionally described as *filled* once price later
returns to it. As a detector column that is not a signal, because its value at
the formation bar depends on subsequent bars.

**Chosen.** Detection is prospective; fill is an **outcome label** with an
explicit window `N` (default 60 bars = the longest horizon tested), carried in
a `*_label` column and excluded from `EVENT_REGISTRY`.

**Rationale.** The alternative is a look-ahead signal. The prior version made
exactly this mistake and emitted 187,719 look-ahead events (187,374 trades at
h = 10). Any reported fill rate must state its window, since the rate is
meaningless without one.
**Where:** `signals/ict_signals.py::detect_fvg`, `tests/test_no_lookahead.py`.

## A3 — Premium/Discount range is an all-time expanding extreme · medium

**Ambiguity.** The SMC source computes the premium/discount range from an
all-time expanding high/low. On a 16-year sample that means a level set in 2010
still anchors the 2026 zone, which is unlikely to be the intent.

**Chosen.** Source-faithful expanding extreme as the default, with a
rolling-window variant available (`detect_zones(window=...)`).

**Rationale.** Faithfulness to the tested implementation is the study's
standard. Zones are a *feature*, not a tradeable event, so no significance
result depends on this. **Where:** `signals/smc_signals.py::detect_zones`.

## A4 — Order-block swing tracking: single object or queue · high

**Ambiguity.** Pine's `swings()` holds one `var swing` object per side and
replaces it wholesale — including resetting `.crossed` — whenever a newer swing
confirms. Read as a queue instead, every historical swing stays testable.

**Chosen.** Single most-recent swing per side, matching the source.

**Rationale.** Not a free choice: the queue reading is a bug. It gets stuck
permanently on the first swing that never breaks — AAPL produced *zero* bearish
order blocks across 16 years because the code was still testing its 2010
all-time low. **Where:** `signals/ict_signals.py::detect_order_blocks`,
`tests/test_detector_rules.py::TestOrderBlock`.

## A5 — Order-block *mitigation* direction · high

**Ambiguity.** Is `ict_ob_bullish_mitigated` a bullish or a bearish event? The
name says bullish; the semantics say a bullish order block has just *failed*.

**Chosen.** Mitigation is scored **opposite** to formation: a bullish block
failing is bearish (−1).

**Rationale.** The prior name-substring heuristic assigned +1 because the
string contains "bullish", which inverts the hypothesis. This affects four
registered signals and is a genuine change to what is being tested — a referee
could reasonably prefer to see both directions reported. `EVENT_REGISTRY` makes
the choice explicit rather than emergent.
**Where:** `signals/event_engine.py::EVENT_REGISTRY`.

## A6 — Equal highs / equal lows have no stated direction · high

**Ambiguity.** Neither name encodes a direction, and the source draws them as
levels rather than signals.

**Chosen.** Equal highs = resistance with resting liquidity above → **−1**;
equal lows = support → **+1**.

**Rationale.** The prior code returned direction 0 and the backtester coerced 0
to +1, so equal highs were traded long — scored with the wrong sign. Some
direction had to be chosen; this is the standard reading. A referee preferring
the opposite convention can flip it in one line and rerun.
**Where:** `signals/event_engine.py::EVENT_REGISTRY`.

## A7 — "Liquidity sweep" has no rejection leg in the source · high

**Ambiguity.** The source fires its sweep when `close > pool_bottom` — price
merely *entering* the pool. Standard ICT teaching requires a stop run **and** a
rejection.

**Chosen.** Implement the standard two-leg rule as a new detector
(`ict_sweep_*`: penetrate by ≥ X·ATR, then close back past the level within Z
bars, stamped on the reclaim bar) and **retain the original columns unchanged**
under their own names.

**Rationale.** Substituting silently would hide the change. Keeping both makes
the reformulation a measurable comparison. The original
`ict_liquidity_buyside_swept` has an excess of −4.5 bp over the matched null.
The reformulated `ict_sweep_*` carry the largest positive point estimates of
any high-sample concept (+11.4 and +11.9 bp at h = 10) but do not beat the null
(p = 0.23 and 0.29 under the calendar-time test). Because we chose X and Z, a
36-configuration targeted sweep varies exactly those parameters: the sign stays
positive in 36/36 and 33/36 configurations, and no configuration is
significant even before multiple-testing correction. An earlier draft of this
re-analysis reported both as surviving; that rested on the anti-conservative
SRS-variance test (`CHANGES.md` §8.1).
**Where:** `docs/specs/ict_liquidity_sweep.yaml`,
`results/sensitivity_targeted_grid.csv`.

## A8 — New Day Opening Gap has no materiality threshold · high

**Ambiguity.** The source's NDOG test amounts to "an open and a prior close
exist", true on every bar. Some threshold is needed for it to be an event.

**Chosen.** `|open − close_prev| ≥ gap_min_atr × ATR(14)_prev`, default 0.10
ATR, with gaps split by direction, and the source's own `ndog_enabled = False`
honoured.

**Rationale.** Without a threshold the concept contributed 1,946,675 events —
44.8% of the entire event table — and dominated every pooled aggregate.
**The threshold sets the sign of the result**: mean excess is +2.6 bp at 0.05
ATR, +0.4 bp at our 0.10 default, and −1.6 bp at 0.25. Under the superseded
SRS-variance test `ict_nwog_gap_up` cleared FDR at the default, so a claimed
edge would have hinged on this choice. Under the calibrated test it is not
significant at any threshold (p = 0.39 at the default), so no conclusion now
depends on it. It remains the clearest illustration in the study of how a
disambiguation choice can decide the sign of a reported effect.
**Where:** `docs/specs/ict_opening_gap.yaml`, manuscript §5.6.

## A9 — Week-open detection across holidays · low

**Ambiguity.** The prior test `dayofweek.diff() > 1` also fires on a mid-week
holiday gap (Mon → Wed), mislabelling it a week open.

**Chosen.** `dayofweek_i ≤ dayofweek_{i-1}` — the calendar week rolled over.

**Rationale.** Robust to Monday holidays and to any weekday gap. No judgement
call; the prior version was simply wrong.
**Where:** `signals/ict_signals.py::detect_nwog_ndog`.

## A10 — Balanced Price Range boundary naming · medium

**Ambiguity.** None, once inspected: for a bullish FVG the region spans
`[high[i−2], low[i]]` with `high[i−2] < low[i]`, so the column named `_top` held
the *lower* edge.

**Chosen.** Rename to `_lower`/`_upper` and use a correct interval-overlap test,
`max(a_lo, b_lo) < min(a_hi, b_hi)`.

**Rationale.** The prior condition reduced to `upper < lower`, unsatisfiable, so
both BPR signals were false for every bar of every ticker and were silently
dropped — "42 concepts tested" was 42 of 44 declared.
**Where:** `docs/specs/ict_bpr.yaml`.

## A11 — Kill zones · low

**Ambiguity.** None. Kill zones are intraday session windows with no meaning on
daily bars.

**Chosen.** Excluded, and stated as a scope limit rather than approximated.

**Rationale.** Any daily-bar proxy would be an invention, not a translation.
This is the single largest limit on the study's external validity, since SMC/ICT
is most often taught on intraday instruments. **Where:** manuscript §7, §8.

## A12 — Rejection Blocks and Optimal Trade Entry · low

**Ambiguity.** Both appear in ICT teaching but have no corresponding logic in
either source script.

**Chosen.** Not implemented, and not invented.

**Rationale.** The study's operational definition is the source code. Inventing
a detector for a named concept would test our reading of the literature rather
than the implementation. **Where:** `README.md`, manuscript §3.2.

## A13 — SMC FVG percentage scaling · low (no effect)

**Ambiguity.** The implementation divides by `open * 100` where the source uses
`/ open * 100` — a factor of 10⁻⁴.

**Chosen.** Leave as-is and document.

**Rationale.** The threshold is derived from the same quantity, so both sides of
the comparison carry the identical factor and the test is scale-invariant.
Provably no effect on any number; changing it would create diff noise for
nothing. **Where:** `docs/specs/smc_fvg.yaml`.

---

## A14 — Sector classification: current GICS, applied retroactively · medium

**Ambiguity.** Sector membership changes over time. GICS was restructured in
2018, when Communication Services was created and GOOGL, META, NFLX and others
moved into it, and in 2023, when payments firms such as V and MA moved from
Information Technology to Financials. A point-in-time classification would
bucket a 2012 GOOGL trade under Information Technology; the current one puts it
under Communication Services.

**Chosen.** Current GICS sectors from the committed constituent snapshot
(`data/raw/sp500_wikipedia_snapshot.csv`), applied to the whole sample.

**Rationale.** This is the standard choice when no point-in-time sector history
is available, and it is reproducible. It changes only which sector a trade is
attributed to, never a concept-level result. It replaced a hand-curated map that
left 54 constituents unclassified and mis-classified six.
**Where:** `analytics/sectors.py::resolve_sector_map`.

## A15 — "Date added" is the most recent addition · low

**Ambiguity.** A firm that was removed from the index and later re-added carries
only its latest entry date in the published table.

**Chosen.** Treat the firm as a non-member before that date.

**Rationale.** This errs toward dropping data from the membership-aware re-test,
never toward keeping look-ahead. It affects only that robustness check.
**Where:** `utils/universe.py::membership_mask`.

## A16 — Which candle is the order block · high

**Ambiguity.** None in the source, which makes this a translation error rather
than a reading. LuxAlgo's SMC `storeOrdeBlock` scans the bars between the swing
pivot and the break: a **bullish** block is the bar with the lowest parsed low,
a **bearish** block the bar with the highest parsed high, and a block is removed
from the active list once mitigated. The ICT script's loop covers only the bars
strictly between the swing and the break.

**Chosen.** Exactly that.

**Rationale.** The first translation took the opposite extreme (the highest
high for a bullish block, the lowest low for a bearish one) and kept mitigated
blocks active, so every `smc_*_ob_*` signal was computed from the wrong candle;
`smc_internal_ob_bearish_mitigated` was among the concepts flagged under the
superseded test. The ICT loop included the break bar, letting a block be its
own breaking candle. Neither is a defensible alternative reading.
**Where:** `signals/smc_signals.py`, `signals/ict_signals.py::detect_order_blocks`,
`tests/test_ob_fidelity.py`.

---

## Which of these could change a conclusion

| ID | Choice | Could it move a published number? |
|---|---|---|
| A8 | Gap materiality threshold | **Yes — it sets the sign of the gap excess.** Decisive under the superseded test; no significance result depends on it under the calibrated one. |
| A7 | Sweep reformulation | Yes; targeted sweep: sign stable (36/36, 33/36), significant in no configuration |
| A16 | Order-block candle | Yes; the prior translation was a bug, not a reading |
| A5, A6 | Mitigation and equal-H/L directions | Yes; sign of the hypothesis for 6 signals |
| A4, A10 | Swing tracking, BPR overlap | Yes, but the alternatives are bugs, not readings |
| A2 | Fill as a label | Yes; the alternative is look-ahead |
| A3, A9, A11, A12 | Zones, week open, scope | No published significance result depends on these |
| A1, A13 | IFVG mode, FVG scaling | Provably none |
| A14 | Current GICS applied retroactively | Sector attribution only; no concept-level result |
| A15 | Most-recent index-entry date | Only the membership-aware re-test; errs toward dropping data |

Three choices (A5, A6, A7) are genuine judgement calls that a reviewer might
make differently. Each is a one-line change in `EVENT_REGISTRY` or a parameter
in `utils/config.py`, and `./run_full_pipeline.sh` regenerates every number.
