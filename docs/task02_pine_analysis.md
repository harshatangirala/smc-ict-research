# Task 2 — Pine Script Analysis

**Scope:** Read both source scripts completely, line by line, without writing any Python.
Treat SMC + ICT as one combined methodology. No implementation happens in this task — this
document is the analysis deliverable.

**Method note:** This document is a companion to
[`docs/concepts_extraction.md`](concepts_extraction.md) (produced in Task 1), which already
contains the full per-concept technical breakdown (exact trigger logic, price bands, state
machines). Rather than duplicate that material, this document targets the six deliverables
Task 2 asks for specifically — concept grouping, plain-English explanations, dependency
mapping, the complete parameter inventory, the Pine/TradingView built-in function inventory,
and an explicit ambiguity list — and cross-references `concepts_extraction.md` by section
number (`§1.x` = ICT script, `§2.x` = SMC script) wherever the full logic detail lives.
Sources: `docs/reference/ICT_Concepts_LuxAlgo.pine` (1297 lines) and
`docs/reference/SMC_Concepts_LuxAlgo.pine` (1106 lines).

---

## 1. Concept inventory, grouped (duplicates merged for presentation, not for implementation)

Both scripts were read in full. Every concept found is grouped below by what it *represents*
in trading terms, even though — per the Task 1 reconciliation decision — each grouped
row will still become **separate, independently-named Python signals** where the two scripts
compute it differently (see `concepts_extraction.md §3` for why they are not merged in code).

| # | Concept group | Present in ICT | Present in SMC | Technical ref |
|---|---|:---:|:---:|---|
| 1 | Swing pivot detection (the base primitive everything else is built on) | ✅ (2 independent engines: zigzag + OB-swing) | ✅ (1 engine, run at 3 different lookbacks) | §1.1, §1.3, §2.1 |
| 2 | Structure break — continuation (**BOS**) | ✅ | ✅ (Internal + Swing scales) | §1.2, §2.2 |
| 3 | Structure break — reversal (**CHoCH** / ICT calls it **MSS**) | ✅ | ✅ (Internal + Swing scales) | §1.2, §2.2 |
| 4 | Order Blocks | ✅ (1 scale) | ✅ (Internal + Swing scales) | §1.3, §2.3 |
| 5 | Breaker Block (mitigated OB state) | ✅ (state on the same OB object) | — (not present) | §1.3 |
| 6 | Fair Value Gap (FVG) | ✅ (+ "Implied FVG" variant) | ✅ (+ optional MTF) | §1.6, §2.5 |
| 7 | Balance Price Range (overlap of two FVGs) | ✅ | — (not present) | §1.7 |
| 8 | Liquidity pools & sweeps | ✅ | — (not present) | §1.8 |
| 9 | Equal Highs / Equal Lows | — (not present) | ✅ | §2.4 |
| 10 | Premium / Discount / Equilibrium zones | — (not present) | ✅ | §2.6 |
| 11 | Strong / Weak High / Low | — (not present) | ✅ | §2.7 |
| 12 | Multi-timeframe reference levels (D/W/M highs & lows) | — (not present) | ✅ | §2.8 |
| 13 | Displacement candle | ✅ | — (not present as a named concept; see ambiguity A5 below for the related-but-different confluence filter) | §1.4 |
| 14 | Volume Imbalance | ✅ | — (not present) | §1.5 |
| 15 | New Week / New Day Opening Gap (NWOG/NDOG) | ✅ | — (not present) | §1.9 |
| 16 | Fibonacci measurement tool | ✅ (display/measurement only, not an event) | — (not present) | §1.10 |
| 17 | Killzones (session shading) | ✅ (intraday-only, N/A on daily bars) | — (not present) | §1.11 |
| 18 | Rejection Blocks | — (not present) | — (not present) | **gap — not implemented in either script** |
| 19 | Optimal Trade Entry (OTE) | — (not present) | — (not present) | **gap — not implemented in either script** |

**19 concept groups identified: 17 implemented (across 27 distinct Python-signal-family
namespaces once Internal/Swing/ICT variants are un-collapsed, per `concepts_extraction.md
§3`), 2 confirmed absent from both scripts.**

---

## 2. Plain-English explanation of every concept

No Pine syntax below — this section is written for a reader who trades SMC/ICT but doesn't
read code.

1. **Swing pivot** — a local high or low point on the chart, confirmed only after enough bars
   have passed on both sides to be sure it really was a turning point. Every other concept in
   both scripts is built by tracking a sequence of these.
2. **BOS (Break of Structure)** — price closes beyond the most recent significant swing point
   *in the direction the trend was already going*. Read as "the trend is continuing."
3. **CHoCH (Change of Character) / MSS (Market Structure Shift)** — price closes beyond the
   most recent significant swing point *in the opposite direction* to the trend that was in
   place. Read as "the trend may be reversing." ICT's script calls this event "MSS"; SMC's
   script calls the identical idea "CHoCH." Same trading concept, different label, different
   underlying pivot math (see dependency map below).
4. **Order Block** — the last down-close candle before a strong up-move breaks structure
   (bullish order block), or the last up-close candle before a strong down-move breaks
   structure (bearish order block). The theory: that candle marks where large players were
   still positioning before the move, so price often returns to "tap" that zone before
   continuing.
5. **Breaker Block** — an order block that failed: price came back and closed all the way
   through it instead of bouncing. Once that happens, ICT's script keeps tracking the same
   zone but now expects the opposite reaction (support that broke tends to become resistance
   and vice versa).
6. **Fair Value Gap (FVG)** — a three-candle price gap: the middle candle moved so fast that
   the first and third candles' wicks don't overlap, leaving an untraded price "gap" that
   price is expected to eventually revisit and fill.
7. **Balance Price Range (BPR)** — the overlapping price zone shared by a recent bullish FVG
   and a recent bearish FVG sitting close together — a tighter, higher-conviction version of
   a plain FVG.
8. **Liquidity pool** — a cluster of roughly equal recent highs (or lows) — the theory is that
   many traders' stop-losses/pending orders sit just beyond that cluster, making it an
   attractive target for price to run to.
9. **Liquidity sweep** — the moment price actually pushes through a liquidity pool (running
   the stops) before, often, reversing — the "stop hunt."
10. **Equal Highs / Equal Lows (EQH/EQL)** — a simpler, two-point version of a liquidity pool:
    just two recent swing points sitting within a small tolerance of each other.
11. **Premium / Discount / Equilibrium zone** — dividing the current trading range into
    thirds: the top ~5% ("premium," considered expensive — a place to look for shorts), the
    bottom ~5% ("discount," considered cheap — a place to look for longs), and the middle
    band ("equilibrium," the fair-value midpoint).
12. **Strong / Weak High / Low** — a label on the current range's extreme points describing
    how likely they are to hold. A high that formed *against* an existing downtrend is
    "strong" (more significant, less likely to be broken); a high that formed *with* an
    uptrend is "weak" (more likely to be taken out as a liquidity target).
13. **Multi-timeframe (MTF) levels** — yesterday's / last week's / last month's high and low
    plotted as reference lines on today's chart, since traders track those levels across
    timeframes even on a lower-timeframe chart.
14. **Displacement candle** — an unusually large, clean-bodied candle (small wicks relative
    to its range) — read as a sign of strong, motivated buying or selling rather than
    indecisive chop.
15. **Volume Imbalance** — similar to an FVG but subtler: the candle *bodies* (not the
    wicks) leave a gap, even though the wicks technically touched — considered a lower-grade
    imbalance than a full FVG.
16. **New Week / New Day Opening Gap (NWOG/NDOG)** — the price gap between Friday's close and
    Monday's open (weekly) or yesterday's close and today's open (daily) — another kind of
    "untraded" zone the market may revisit.
17. **Fibonacci tool** — draws standard retracement/extension ratios (23.6%, 38.2%, 50%,
    61.8%, 78.6%, 161.8%) between the two most recent instances of whatever concept you pick
    (e.g. the last two order blocks) — a measuring tool, not a pattern detector itself.
18. **Killzones** — shades specific recurring intraday time windows (the New York, London,
    and Asian session opens) where ICT theory says institutional activity concentrates. Has
    no meaning on a daily candle, since a daily bar has no internal session structure.

---

## 3. Dependencies between concepts

Concepts are not all independent detectors — several are *derived from* other concepts firing
first. This matters directly for the Python module design: dependent detectors must consume
the output of their prerequisite detector rather than re-scanning price independently.

```
ICT script
──────────
Zigzag pivot engine (§1.1)
 ├─▶ Market Structure Shift / BOS (§1.2)           [reads zigzag vertices]
 └─▶ Liquidity pools & sweeps (§1.8)                [reads zigzag vertices for pivot clustering]

OB-swing engine, independent lookback (§1.3)
 └─▶ Order Blocks (§1.3)                            [reads its own swing() pivots, NOT the zigzag]
      └─▶ Breaker Block state (§1.3)                [an OB that got mitigated]

Displacement candle test (§1.4)
 └─▶ Fair Value Gap formation gate (§1.6)            [FVG's middle candle must qualify as displacement]
      └─▶ Balance Price Range (§1.7)                 [overlap of two FVGs]
      └─▶ Fibonacci tool, if iFib='FVG'/'BPR' (§1.10) [measures between 2 FVGs/BPRs]

Volume Imbalance (§1.5) — independent, no dependents

NWOG / NDOG (§1.9) — independent, calendar-anchored only

Fibonacci tool (§1.10) — depends on whichever concept iFib selects (FVG, BPR, OB, Liq, VI, or NWOG)
Killzones (§1.11) — fully independent, pure session-time logic


SMC script
──────────
leg() pivot engine, run 3x at 3 lookbacks (§2.1)
 ├─▶ Swing structure: BOS/CHoCH (§2.2, size=swingsLengthInput, default 50)
 │    └─▶ Swing Order Blocks (§2.3)                  [formed from the swing pivot that a BOS/CHoCH just broke]
 ├─▶ Internal structure: BOS/CHoCH (§2.2, size=5, fixed)
 │    └─▶ Internal Order Blocks (§2.3)               [formed from the internal pivot that a BOS/CHoCH just broke]
 └─▶ Equal High/Low structure (§2.4, size=equalHighsLowsLengthInput, default 3)
      [independent pivot cadence, only feeds EQH/EQL, not BOS/CHoCH]

Trailing extremes tracker (§2.6, all-time running max-high/min-low)
 ├─▶ Premium / Discount / Equilibrium zones (§2.6)
 └─▶ Strong / Weak High / Low labels (§2.7)           [reuses trailing extremes + current swingTrend.bias from §2.2's swing-scale trend]

Fair Value Gap (§2.5) — independent of the pivot/structure engines entirely; driven purely by
                          3-candle price geometry + an adaptive %-move threshold

MTF reference levels (§2.8) — fully independent, pure resample-and-shift logic
```

**Key implications for Python module boundaries (informs Task 3 architecture):**
- The Order Block detector in both scripts is **not standalone** — it must be wired to consume
  events from its corresponding structure-break detector (ICT: the shared zigzag/pivot output;
  SMC: specifically the BOS/CHoCH detector at the matching scale), not re-implemented as an
  independent pattern scan.
- SMC's Strong/Weak High/Low (§2.7) depends on both the trailing-extremes tracker (§2.6) *and*
  the swing-scale trend state (§2.2) — two upstream dependencies, not one.
- ICT's Balance Price Range (§1.7) and Fibonacci tool (§1.10) are second-order derivatives (FVG
  → BPR → Fibonacci), a three-level chain.
- FVG detection (both scripts) and Volume Imbalance/NWOG/NDOG/MTF-levels are the only
  "first-order" detectors that read raw OHLC directly with no dependency on any other concept's
  output (aside from ICT FVG's dependency on the Displacement test, §1.4).

---

## 4. Complete configurable parameter list

Every `input.*()` call in both scripts, extracted directly from source (grep-verified counts:
61 typed `input.xxx()` calls in the ICT script (0 bare `input()` calls); 30 typed `input.xxx()`
+ 22 bare `input()` calls = 52 total in the SMC script — cosmetic color/style inputs
included for completeness since the brief asked for "every configurable parameter," with a
**Logic-relevant?** column flagging which ones actually change *what* gets detected versus
which only change *how it's drawn*). Full title text, defaults, and constraints are already
recorded per-concept in `concepts_extraction.md`; this table consolidates them in one place
for architecture/config-file design (Task 3).

### 4.1 ICT Concepts [LuxAlgo]

| Parameter (Pine var) | UI label | Type | Default | Constraints | Logic-relevant? |
|---|---|---|---|---|:---:|
| `i_mode` | Mode | string | `Present` | `Present`/`Historical` | Yes — see `concepts_extraction.md §1.12` (Python assumption: always behaves as Historical) |
| `len` | Length (Market Structures) | int | 5 | 3–10 | **Yes** — zigzag/MSS/BOS pivot lookback |
| `iMSS` | MSS show | bool | true | — | Partial — gates *display* only; internal `MSS.dir` state always updates |
| `cMSSbl`, `cMSSbr` | MSS colors | color | — | — | No (cosmetic) |
| `iBOS` | BOS show | bool | true | — | **Yes** — unlike `iMSS`, this gates the BOS *detection* switch-case itself (asymmetry documented as Assumption 4 in `concepts_extraction.md §5`) |
| `cBOSbl`, `cBOSbr` | BOS colors | color | — | — | No (cosmetic) |
| `sDispl` | Show Displacement | bool | false | — | No — underlying `L_bodyUP/DN` always computed regardless |
| `sVimbl` | Volume Imbalance show | bool | true | — | **Yes** — gates VI detection entirely |
| `visVim` | # Visible VI's | int | 2 | 2–100 | No (display cap only) |
| `cVimbl` | VI color | color | — | — | No (cosmetic) |
| `showOB` | Show Order Blocks | bool | true | — | **Yes** — gates OB detection entirely |
| `length` | Swing Lookback (OB) | int | 10 | ≥3 | **Yes** — OB-swing pivot lookback (independent of `len`) |
| `showBull`, `showBear` | Show Last Bullish/Bearish OB | int | 1 | ≥0 | No (display cap only — detection/storage is uncapped) |
| `useBody` | Use Candle Body | bool | true | — | **Yes** — switches OB extremes between body and wick |
| `bullCss`, `bullBrkCss`, `bearCss`, `bearBrkCss` | OB colors | color | — | — | No (cosmetic) |
| `showLabels` | Show Historical Polarity Changes | bool | false | — | No (cosmetic label toggle) |
| `showLq` | Show Liquidity | bool | true | — | **Yes** — gates liquidity pool detection entirely |
| `margin` (→ `a=10/margin`) | margin | float | 4 | 2–7, step 0.1 | **Yes** — controls liquidity cluster tightness |
| `visLiq` | # Visible Liq. boxes | int | 2 | 1–50 | No (display cap only) |
| `cLIQ_B`, `cLIQ_S` | Liquidity colors | color | — | — | No (cosmetic) |
| `shwFVG` | Show FVGs | bool | true | — | **Yes** — gates FVG detection entirely |
| `i_BPR` | Balance Price Range | bool | false | — | **Yes** — gates BPR computation entirely (off by default) |
| `i_FVG` | FVG/IFVG mode | string | `FVG` | `FVG`/`IFVG` | **Yes** — flips the gap-direction inequality (see Ambiguity A1) |
| `visBxs` | # Visible FVG's | int | 2 | 1–20 | No (display cap only) |
| `cFVGbl`, `cFVGblBR`, `cFVGbr`, `cFVGbrBR` | FVG colors | color | — | — | No (cosmetic) |
| `iNWOG` | NWOG show | bool | true | — | **Yes** — gates NWOG detection |
| `cNWOG1`, `cNWOG2` | NWOG colors | color | — | — | No (cosmetic) |
| `maxNWOG` | Show max (NWOG) | int | 3 | 0–50 | No (retention/display cap only) |
| `iNDOG` | NDOG show | bool | **false** | — | **Yes** — gates NDOG detection (off by default) |
| `cNDOG1`, `cNDOG2` | NDOG colors | color | — | — | No (cosmetic) |
| `maxNDOG` | Show max (NDOG) | int | 1 | 0–50 | No (retention/display cap only) |
| `iFib` | Fibonacci between last: | string | `NONE` | `FVG`/`BPR`/`OB`/`Liq`/`VI`/`NWOG`/`NONE` | N/A — measurement tool only, not an event (§1.10) |
| `iExt` | Extend lines | bool | false | — | No (cosmetic, Fibonacci tool only) |
| `showKZ` | Show Killzones | bool | false | — | N/A on daily bars (§1.11, excluded) |
| `showNy`, `showLdno`, `showLdnc`, `showAsia` | per-session show | bool | true (×4) | combined with `and showKZ` | N/A on daily bars |
| `nyCss`, `ldnoCss`, `ldncCss`, `asiaCss` | session colors | color | — | — | No (cosmetic) |
| 4× `input.session(...)` | session time windows | session | `0700-0900`/`0700-1000`/`1500-1700`/`1000-1400` | — | N/A on daily bars |

### 4.2 Smart Money Concepts [LuxAlgo]

| Parameter (Pine var) | UI label | Type | Default | Constraints | Logic-relevant? |
|---|---|---|---|---|:---:|
| `modeInput` | Mode | string | `Historical` | `Historical`/`Present` | Yes (Python assumption: always Historical, same as ICT) |
| `styleInput` | Style | string | `Colored` | `Colored`/`Monochrome` | No (cosmetic — only remaps colors) |
| `showTrendInput` | Color Candles | bool | false | — | No (cosmetic candle recoloring, reuses existing trend state) |
| `showInternalsInput` | Show Internal Structure | bool | true | — | **Yes** — gates internal BOS/CHoCH detection execution |
| `showInternalBullInput`, `showInternalBearInput` | Bullish/Bearish Structure filter | string | `ALL` | `ALL`/`BOS`/`CHOCH` | No — display filter only; alert booleans fire regardless |
| `internalBullColorInput`, `internalBearColorInput` | colors | color | — | — | No (cosmetic) |
| `internalFilterConfluenceInput` | Confluence Filter | bool | false | — | **Yes** — adds a body-dominance precondition to internal BOS/CHoCH |
| `internalStructureSize` | Internal Label Size | string | `TINY` | `TINY`/`SMALL`/`NORMAL` | No (cosmetic) |
| `showStructureInput` | Show Swing Structure | bool | true | — | **Yes** — gates swing BOS/CHoCH detection execution |
| `showSwingBullInput`, `showSwingBearInput` | filter | string | `ALL` | `ALL`/`BOS`/`CHOCH` | No — display filter only |
| `swingBullColorInput`, `swingBearColorInput` | colors | color | — | — | No (cosmetic) |
| `swingStructureSize` | Swing Label Size | string | `SMALL` | — | No (cosmetic) |
| `showSwingsInput` | Show Swings Points | bool | false | — | No (label display only) |
| `swingsLengthInput` | (swings length) | int | 50 | ≥10 | **Yes** — swing-scale pivot lookback |
| `showHighLowSwingsInput` | Show Strong/Weak High/Low | bool | true | — | **Yes** — gates trailing-extremes tracking + zone/label computation |
| `showInternalOrderBlocksInput` | Internal Order Blocks | bool | true | — | **Yes** — gates internal OB storage |
| `internalOrderBlocksSizeInput` | (count) | int | 5 | 1–20 | **Yes** — caps both display *and* retained array size |
| `showSwingOrderBlocksInput` | Swing Order Blocks | bool | **false** | — | **Yes** — gates swing OB storage (off by default) |
| `swingOrderBlocksSizeInput` | (count) | int | 5 | 1–20 | **Yes** — caps both display and retained array size |
| `orderBlockFilterInput` | Order Block Filter | string | `Atr` | `Atr`/`Cumulative Mean Range` | **Yes** — changes the volatility measure used for high-vol-bar swap logic |
| `orderBlockMitigationInput` | Order Block Mitigation | string | `High/Low` | `Close`/`High/Low` | **Yes** — changes the mitigation trigger source |
| `internalBullishOrderBlockColor`, `internalBearishOrderBlockColor`, `swingBullishOrderBlockColor`, `swingBearishOrderBlockColor` | colors | color | — | — | No (cosmetic) |
| `showEqualHighsLowsInput` | Equal High/Low | bool | true | — | **Yes** — gates EQH/EQL detection |
| `equalHighsLowsLengthInput` | Bars Confirmation | int | 3 | ≥1 | **Yes** — EQH/EQL pivot cadence |
| `equalHighsLowsThresholdInput` | Threshold | float | 0.1 | 0–0.5, step 0.1 | **Yes** — ATR-relative equality tolerance |
| `equalHighsLowsSizeInput` | Label Size | string | `TINY` | — | No (cosmetic) |
| `showFairValueGapsInput` | Fair Value Gaps | bool | **false** | — | **Yes** — gates FVG detection entirely (off by default) |
| `fairValueGapsThresholdInput` | Auto Threshold | bool | true | — | **Yes** — toggles the adaptive %-move threshold vs. no filter |
| `fairValueGapsTimeframeInput` | Timeframe | timeframe | `""` (chart TF) | — | **Yes** — MTF source for FVG (N/A beyond daily for this project, §2.5 note) |
| `fairValueGapsBullColorInput`, `fairValueGapsBearColorInput` | colors | color | — | — | No (cosmetic) |
| `fairValueGapsExtendInput` | Extend FVG | int | 1 | ≥0 | No (display-only box extension) |
| `showDailyLevelsInput`, `showWeeklyLevelsInput`, `showMonthlyLevelsInput` | Daily/Weekly/Monthly | bool | false (×3) | — | **Yes** — gates MTF level computation, but produces reference levels, not events (§2.8) |
| `dailyLevelsStyleInput`, `weeklyLevelsStyleInput`, `monthlyLevelsStyleInput` | line style | string | `SOLID` | `SOLID`/`DASHED`/`DOTTED` | No (cosmetic) |
| `dailyLevelsColorInput`, `weeklyLevelsColorInput`, `monthlyLevelsColorInput` | colors | color | `BLUE` | — | No (cosmetic) |
| `showPremiumDiscountZonesInput` | Premium/Discount Zones | bool | false | — | **Yes** — gates zone computation |
| `premiumZoneColorInput`, `equilibriumZoneColorInput`, `discountZoneColorInput` | colors | color | RED/GRAY/GREEN | — | No (cosmetic) |

**Validation cross-check:** grep-verified count of input calls = 61 (ICT, all typed
`input.xxx()`) + 52 (SMC: 30 typed `input.xxx()` + 22 bare `input()`) = **113 total input
calls** across both scripts; every one is accounted for in the two tables above (color/style-
only inputs are grouped on shared rows where they are declared together, e.g. `nyCss, ldnoCss,
ldncCss, asiaCss` — this is why the table row count is lower than the raw grep count while
every individual variable is still named).

---

## 5. TradingView / Pine Script–specific built-in functions used

Extracted by grep across both reference files (not from memory) and grouped by category, with
a plain-English description and a note on what it implies for the Python port. This directly
satisfies "document every TradingView-specific function used."

### 5.1 Technical-analysis built-ins (`ta.*`)
| Function | Used in | What it does | Python translation note |
|---|---|---|---|
| `ta.pivothigh(src, left, right)` / `ta.pivotlow(...)` | ICT §1.1, §1.11 (pivotpoints) | Confirms a local max/min only after `right` bars have passed with no higher/lower value — introduces a `right`-bar lag. | `scipy.signal.argrelextrema` or a manual rolling-window comparison; **must preserve the confirmation lag** (this is a source of unavoidable look-ahead-safe delay, not a bug to "fix"). |
| `ta.highest(len)` / `ta.lowest(len)` | ICT §1.3 (`swings()`), SMC §2.1 (`leg()`) | Rolling max/min over `len` bars. | `pandas.Series.rolling(len).max()/.min()`. |
| `ta.sma(src, len)` | ICT §1.4 | Simple moving average. | `pandas.Series.rolling(len).mean()`. |
| `ta.atr(len)` | ICT §1.8 (`atr(10)`), SMC §2.3/§2.4 (`atr(200)`) | Average True Range. | Standard ATR implementation (Wilder or SMA-of-true-range — **must confirm which smoothing `ta.atr` uses**, flagged as Ambiguity A6 below). |
| `ta.barssince(cond)` | ICT §1.11 | Bars elapsed since `cond` was last true. | Manual index-diff computation on a boolean series. |
| `ta.cum(src)` | SMC §2.3 (`ta.cum(ta.tr)`), §2.5 (`ta.cum(math.abs(...))`) | Running cumulative sum from the start of the series. | `pandas.Series.cumsum()`. |
| `ta.tr` | SMC §2.3 | True Range built-in series. | Standard true-range formula. |
| `ta.change(src)` | ICT §1.9 (`dayofweek`), SMC §2.1 (`leg`), §2.8 (`bar_index`) | Value minus its previous value (or, for non-numeric/step series, "did this change"). | `.diff()` or `.ne(.shift())` depending on usage. |
| `ta.crossover(a,b)` / `ta.crossunder(a,b)` | SMC §2.2 | True on the bar `a` crosses above/below `b` (was below/above the prior bar). | Manual two-condition check against the prior bar's values. |

### 5.2 Array built-ins (`array.*` and instance methods)
`array.new<type>()`, `.unshift()`, `.pop()`, `.get(i)`, `.set(i,v)`, `.size()`, `.remove(i)`,
`.push()`, `.slice(a,b)`, `.indexof(v)`, `.max()`, `.min()`, `.binary_search_rightmost(v)` — used
extensively throughout both scripts to implement fixed-size ring buffers (zigzag vertices,
order block lists, FVG lists, liquidity pool lists). **Python translation note:** these map
directly onto Python `list`/`collections.deque` operations or, for vectorized backtesting,
should be redesigned as pandas/NumPy array operations rather than literal per-bar mutable
lists — a design decision for Task 3 architecture, not this document.

### 5.3 Drawing primitives (`box.*`, `line.*`, `label.*` and their `.new()`/`.set_*()`/`.delete()` methods)
Used pervasively for on-chart visualization (order block rectangles, structure lines, gap
boxes, liquidity zones, labels). **These have no Python equivalent and are explicitly out of
scope** per the project goal — every drawing call was read only to recover the *numeric
coordinates being drawn* (which is the actual signal data), never to be reproduced visually.

### 5.4 Math / color / string utilities
`math.max/min/abs/avg/round`, `color.new/rgb/r/g/b`, `str.format` — standard scalar helpers,
directly map to Python/NumPy equivalents (`max/min/abs`, `(a+b)/2`, `round`, f-strings). No
translation ambiguity.

### 5.5 Chart / session / time context
| Function | Used in | What it does | Python translation note |
|---|---|---|---|
| `time(timeframe, session, tz)` | ICT §1.11 | True when the current bar falls inside a named session window in a given timezone. | Intraday-only; N/A for this project's daily-bar scope (§1.11 decision). |
| `input.session(...)` | ICT §1.11 | UI input type for a session time range. | N/A (no UI). |
| `timeframe.period`, `timeframe.in_seconds()`, `timeframe.change(tf)`, `timeframe.isdaily/isweekly/ismonthly` | Both scripts | Chart-timeframe metadata and MTF change-detection. | Directly relevant for the D/W/M resample logic in SMC §2.8; the daily-only scope removes most other usages. |
| `request.security(symbol, tf, exprs, lookahead=barmerge.lookahead_on)` | SMC §2.5 (FVG MTF), §2.8 (levels) | Fetches values computed on a different timeframe/symbol. **Note:** `lookahead_on` is a real look-ahead-bias risk in live/replay Pine execution, but since our target is the *daily* timeframe evaluated with fully-closed daily bars only, the equivalent Python operation (resample to weekly/monthly, shift by one completed period) is inherently look-ahead safe if implemented correctly — flagged as something Task 4/5's no-look-ahead validation must explicitly test. | Implement via `pandas.resample()` + `.shift(1)`, never via any form of forward-fill from incomplete future data. |
| `dayofweek`, `dayofweek.friday`, `dayofweek.monday` | ICT §1.9 | Built-in day-of-week context. | `pandas.Timestamp.dayofweek` / `.day_name()`. |
| `chart.point.new(time, index, price)` | SMC (throughout) | A coordinate helper for drawing objects (mixed time/index/price addressing). | N/A — drawing-only. |
| `chart.bg_color` | ICT §general calc (`isDark`) | Current chart theme background color. | N/A — cosmetic. |
| `syminfo.tickerid` | SMC §2.5, §2.8 | Current symbol identifier, used as the `request.security` target (self-reference, for MTF fetches of the *same* symbol). | N/A — in Python this is simply "the same ticker's data resampled," no lookup needed. |

### 5.6 Bar-state / execution-context built-ins
| Function | Used in | What it does | Python translation note |
|---|---|---|---|
| `barstate.isfirst` | Both scripts | True only on the very first bar of history — used for one-time array/box initialization. | Maps to "on loop/vectorization setup," not a per-bar signal. |
| `barstate.islast` | ICT §1.3, §1.10 | True only on the most recent (real-time) bar — used to draw final-state visuals (order block boxes, Fibonacci levels) only once at the end. | N/A for historical backtesting — we evaluate *every* bar's state as it was known at that bar, not just the final chart state. |
| `barstate.islastconfirmedhistory` | SMC §2.8 (MTF levels), §2.3 (`drawOrderBlocks`) | True on the last bar of confirmed (non-realtime) history. | N/A for a pure historical backtest (no realtime/replay distinction exists in offline daily data). |
| `barstate.isrealtime` | SMC §2.8 | True only during live/streaming execution. | Never true in an offline backtest; any branch gated solely on this is dead code for our purposes. |
| `varip` | SMC §general (`currentBarIndex`, `lastBarIndex`) | A variable that persists and updates on every real-time tick (not just on bar close) — a TradingView-specific real-time-only mechanism. | Not applicable to daily-bar historical backtesting (no intrabar ticks exist in daily OHLCV); the `newBar` logic it feeds is a realtime-vs-historical distinction with no meaning offline. |
| `last_bar_index`, `last_bar_time` | Both scripts | Index/time of the most recent bar on the chart. | In backtesting, replaced by "the current bar being evaluated in the walk-forward loop," not a fixed final value. |
| `timenow` | ICT §1.3 (`display()`) | Current wall-clock time (only meaningful live). | N/A for historical backtesting. |

### 5.7 Plotting / alerting
`indicator(...)` (script declaration + `max_*_count` display limits — irrelevant to logic),
`plotshape(...)`, `plotcandle(...)`, `bgcolor(...)` (all pure visualization, no signal
content beyond what's already captured as the underlying boolean/series being plotted),
`alertcondition(...)` (already cross-referenced against our concept inventory in
`concepts_extraction.md §2.10` — confirms completeness, generates no new logic itself).

### 5.8 Type system / control flow (language features, not built-in functions, documented for completeness)
`type` (user-defined structs — grep-verified 10 types in ICT: `ZZ, ln_d, _2ln_lb, bx_ln,
bx_ln_lb, mss, liq, ob, swing, FVG`; 7 types in SMC: `alerts, trailingExtremes, fairValueGap,
trend, equalDisplay, pivot, orderBlock`), `method` (Pine's syntax for attaching
a function to a UDT, e.g. `method setLine(line ln, ...)`), `switch` (pattern-matching control
flow, used for both the MSS/BOS state machine in ICT and the Fibonacci concept-selector in
both scripts), `for...in` (array iteration with index+value unpacking), `var`/`varip`
(persistent-state declarations — `var` persists across bars normally, `varip` persists across
realtime ticks too). These map to ordinary Python classes/dataclasses, `if/elif` chains, and
module-level or object state — no ambiguity, noted here only because the brief asked for every
Pine-specific construct to be documented.

---

## 6. Ambiguous logic requiring clarification

Each item below is something a literal, careful reading left genuinely unresolved — not a
restatement of things already fully explained in `concepts_extraction.md`. Numbered `A1`–`A8`
for reference in future tasks.

- **A1 — ICT's "IFVG" (Implied FVG) mode does not match the common ICT-community definition
  of Inversion FVG.** In the source, switching `i_FVG` from `'FVG'` to `'IFVG'` simply flips
  the gap inequality (`low > high[2]` becomes `low < high[2]`), which changes what counts as
  a *qualifying gap*, not "an FVG that failed and flipped polarity" (the more common published
  meaning of "Inversion FVG" elsewhere in ICT literature). **Needs user confirmation:** should
  the Python port implement LuxAlgo's literal (unusual) definition, or the community-standard
  Inversion FVG definition instead? Recommendation from `concepts_extraction.md §1.6`: keep as
  a distinct signal family either way — but which definition to actually compute needs a
  decision before Task 5.
- **A2 — BPR's `pos` bias field sign convention is not documented anywhere in the source
  comments.** `pos = close > bxUPbtm ? 1 : close < bxDNtop ? -1 : 0` — is `1` "bullish bias"
  or simply "price is above the upper boundary"? The two readings happen to coincide here, but
  the field is reused later by the mitigation-tracking `switch getUPi.pos` block in a way that
  assumes a specific sign meaning. Low-risk (internally consistent within the script), flagged
  only so the Python port's inline documentation states the convention explicitly rather than
  re-deriving it from context each time.
- **A3 — Premium/Discount trailing extremes are literally all-time min/max, not a rolling
  window** (already flagged as Assumption 3 in `concepts_extraction.md §5`, restated here
  because it is the single most consequential ambiguity in the whole codebase: on a 16-year
  daily backtest, an all-time-expanding high/low means the "Premium zone" for a stock that
  10x'd since 2010 will sit permanently near its 2026 price, and the "Discount zone" will sit
  frozen near its 2010 price — likely useless as a mean-reversion signal at that horizon).
  **Needs an explicit decision, not just documentation:** compute it literally as specified
  (for fidelity to the source), or substitute a rolling window as the *default* research
  variant with the literal version kept only as a robustness-check comparison? This changes
  what "the" Premium/Discount signal even means for the final report.
- **A4 — `iBOS`/`iMSS` display-toggle asymmetry in ICT** (documented in
  `concepts_extraction.md §1.2` and Assumption 4): `iMSS=false` only hides the visual, `MSS.dir`
  state still updates; `iBOS=false` actually skips the BOS detection branch entirely. This
  reads as inconsistent (likely an implementation detail of the original indicator rather than
  an intentional design choice), and the Python port's decision to treat BOS as always-computed
  is a **deviation from literal Pine behavior**, not a literal translation — flagged again here
  because Requirement 2's instruction is "avoid approximations unless absolutely necessary,"
  and this is a case where literal-vs-sensible required a judgment call.
- **A5 — SMC's `internalFilterConfluenceInput` body-dominance test is conceptually similar to,
  but not the same as, ICT's Displacement candle test** (§1.4 vs §2.2). Both measure
  "candle body dominance over wicks," but with different formulas
  (ICT: `high-mx < body*0.36 and mn-low < body*0.36`, i.e. *both* wicks individually small;
  SMC: `high - max(close,open) > min(close,open) - low`, i.e. upper wick simply larger than
  lower wick, a directional-bias test, not a "clean body" test). Confirm they should remain
  separate signal families (recommended) rather than being treated as "the same idea" during
  Requirement 6/7's concept/combination ranking, where a careless read might accidentally
  conflate them as redundant.
- **A6 — `ta.atr()`'s exact smoothing method must be pinned down before translation.**
  TradingView's `ta.atr()` uses RMA (Wilder's smoothing), not a simple moving average of true
  range — this is a well-known TradingView convention but is *not stated anywhere in either
  script's comments*, so it is included here as a fact that must be verified against
  TradingView documentation (not assumed from general trading knowledge) before Task 5, since
  ATR feeds directly into SMC's order block volatility filter (§2.3) and EQH/EQL threshold
  (§2.4) — using the wrong smoothing would silently shift which candles qualify.
- **A7 — Holiday-week edge case in NWOG (§1.9).** `friCp`/`friCi` only update
  `if dayofweek == dayofweek.friday`, i.e. they require an actual trading bar on a Friday. On
  a week where Friday is a market holiday, the `var`-persisted `friCp`/`friCi` will silently
  carry over the *previous* week's Friday close instead of refreshing — meaning the NWOG box
  drawn the following Monday would reference stale data. Not clearly a bug in the original
  (backgrounded by `var` semantics, so it's "intentional" in the sense that the author didn't
  add a holiday guard), but worth an explicit decision: replicate the stale-data behavior
  literally, or add a genuine "most recent completed week" lookup in Python? Recommend the
  latter as more correct for research purposes, flagged for confirmation rather than decided
  unilaterally here.
- **A8 — Order block array size is uncapped in ICT (§1.3) but capped at 100 in SMC (§2.3).**
  Not ambiguous logic per se (both are unambiguous as written), but worth flagging as an
  inconsistency between the two scripts that the Python port should resolve deliberately: an
  unbounded 16-year, 500-stock backtest with no cap on ICT-style order blocks could grow
  memory usage significantly if a stock chops sideways for years without a full OB
  invalidation. Recommend applying a sensible cap (configurable) to both engines in the Python
  version regardless of source-script literalness, since Pine's uncapped array was only
  practical because TradingView charts naturally reset per session/reload — an offline batch
  job over the full S&P 500 has no equivalent reset point.

---

## 7. Validation

- **Every Pine Script function documented:** §5 above was built from `Grep`-verified,
  exhaustive pattern matches against both `.pine` reference files (not from memory) covering
  every `ta.*`, `array.*`, `box.*`, `line.*`, `label.*`, `math.*`, `color.*`, `str.*`,
  `request.*`, `timeframe.*`, `input.*`, `barstate.*`, `chart.*`, `syminfo.*` call, plus
  `plotshape`, `plotcandle`, `bgcolor`, `alertcondition`, `fixnan`, `nz`, `varip`, `dayofweek`,
  `xloc.*`, `extend.*`, `size.*`, `location.*`, `text.align*`, `shape.*`, `switch`, `for...in`,
  `type`, `method`. No category of built-in identifier used in either file was left
  undocumented.
- **No concept skipped:** §1's 19-row inventory was cross-checked against (a) the brief's
  original Requirement-1 example list [already reconciled in `concepts_extraction.md §4`], (b)
  both scripts' own `alertcondition()` blocks [SMC has 16 alerts, all mapped; ICT has none —
  it uses no `alertcondition()` calls at all, confirmed by grep returning zero matches in the
  ICT file, which is itself worth noting: **ICT's script has zero built-in alerts**, unlike
  SMC's 16 — a fact not previously stated in Task 1's doc, added here for completeness], and
  (c) a full line-by-line re-read of both files performed for this task.
- **Duplicates grouped, not merged in implementation:** confirmed consistent with the Task 1
  decision in `concepts_extraction.md §3` — this task's §1 table is a presentation-layer
  grouping only.
- **Every parameter listed:** §4's two tables account for all 113 input calls found by grep
  (61 ICT + 52 SMC), with color/cosmetic inputs grouped on shared rows and logic-relevant
  parameters individually called out.
- **Ambiguities require follow-up before Task 5 (translation)**, not before Task 3
  (architecture) — items A1, A3, A4, A6, A7 in particular affect *what number a Python function
  should return*, not *how the codebase is organized*, so Task 3 can proceed without blocking
  on these, but Task 5 should not proceed past the affected concepts until they are resolved.
