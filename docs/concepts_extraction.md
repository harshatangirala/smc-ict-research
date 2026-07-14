# SMC/ICT Concept Extraction (Requirement 1)

**Status:** Complete for Task 1. This is a specification document, not code. It is the
source-of-truth that Requirement 2 (Python translation) must implement against.

**Sources:**
- `docs/reference/ICT_Concepts_LuxAlgo.pine` — LuxAlgo "ICT Concepts", `@version=5`
- `docs/reference/SMC_Concepts_LuxAlgo.pine` — LuxAlgo "Smart Money Concepts", `@version=5`

Both files are best-effort plain-text transcriptions of the Pine source produced by
extracting text directly from the PDFs supplied by the user (not OCR of images — the PDFs
contained a text layer). Line-wrapping/indentation may differ cosmetically from the original
`.pine` files because the source PDF wrapped long lines across the page width, but no tokens,
operators, or logic were altered or invented. Every claim below cites the exact Pine
identifier(s) it is based on so it can be re-verified against the reference files directly.

---

## 0. How to read this document

For each concept: **Name** → **Pine identifiers** → **Trigger logic** (translated to prose/
pseudocode, preserving exact conditions) → **Parameters** (input, default, constraints) →
**Output artifact** (what it draws — irrelevant for our Python port, noted only for
traceability) → **Signal-relevant fields** (what a Python event detector must actually
compute) → **Notes / ambiguities**.

"Signal-relevant fields" is the important column: it defines what Requirement 3's event
detector needs to output as a column, stripped of all TradingView drawing concerns (boxes,
labels, colors, `xloc.bar_time` vs `xloc.bar_index`, `timenow`, etc.), which are explicitly
out of scope per the project goal ("NOT to replicate TradingView visuals").

---

## 1. ICT Concepts [LuxAlgo] — extracted concepts

### 1.1 Zigzag / swing pivot engine (`aZZ`, `draw()`)

- **Pine identifiers:** `type ZZ`, `var ZZ aZZ`, `draw(left, col)`, `ta.pivothigh(hi, left, 1)`,
  `ta.pivotlow(lo, left, 1)`, input `len` (Market Structure "Length", default 5, min 3, max 10).
- **Trigger logic:** A confirmed pivot high/low with `left = len` bars on the left and exactly
  `1` bar on the right (i.e. a 1-bar-lag confirmation, which is standard `ta.pivothigh/low`
  behavior). Each confirmed pivot flips the running zigzag direction (`aZZ.d`: `1` = up-leg
  from a low, `-1` = down-leg from a high) and either appends a new zigzag vertex or updates
  the current one in place if price extends further in the same direction before reversing.
  `aZZ` stores up to `maxSize = 50` vertices (direction, bar index, price, flag) via a
  fixed-length unshift/pop ring buffer.
- **Signal-relevant fields:** This is not itself a tradeable event — it is the shared pivot
  skeleton that MSS, BOS, and Liquidity below are built on. Python must reproduce this as an
  internal utility (`ict_zigzag`), not a signal column.
- **Notes:** This zigzag is **separate** from the Order Block swing detector (`swings()`,
  §1.3) and uses a different lookback (`len`, default 5) vs. the OB lookback (`length`,
  default 10). Treat as two independent pivot detectors, not one shared structure.

### 1.2 Market Structure Shift (MSS) and Break of Structure (BOS)

- **Pine identifiers:** `type mss`, `var mss MSS`, block inside `draw()` under
  `//Market Structure Shift`, inputs `showMS`, `iMSS`, `iBOS`, `i_mode`.
- **Trigger logic:**
  - `iH = aZZ.d.get(2)==1 ? 2 : 1`, `iL = aZZ.d.get(2)==-1 ? 2 : 1` — selects whichever of the
    last two opposite-direction zigzag vertices represents the most recent confirmed swing
    high (`iH`) / swing low (`iL`).
  - **Bullish MSS:** `close > aZZ.y.get(iH)` and `aZZ.d.get(iH) == 1` and `MSS.dir < 1` →
    flips `MSS.dir = 1`.
  - **Bearish MSS:** `close < aZZ.y.get(iL)` and `aZZ.d.get(iL) == -1` and `MSS.dir > -1` →
    flips `MSS.dir = -1`.
  - **Bullish BOS:** only fires when `MSS.dir == 1` (i.e. after an MSS already flipped bullish)
    and `close > aZZ.y.get(iH)` again on a *later* bar, and the broken level differs from the
    level already recorded as the last BOS/MSS line (de-duplication check against
    `MSS.l_bosBl.get(0).get_y2()` / `MSS.l_mssBl.get(0).get_y2()`). Mirrored for bearish.
  - In `i_mode == 'Present'`, every new MSS clears all previously drawn MSS/BOS lines and
    labels for the current direction change (visual-only; irrelevant to signal detection,
    but implies the "Present" mode is a display-window concept, not a different trading
    rule — the underlying trigger math is identical in both modes).
- **Parameters:** `len` (pivot lookback, shared with §1.1, default 5, 3–10), `iMSS`
  (show/hide MSS, default true — does **not** gate the underlying computation, only display:
  note `if not iMSS: MSS.l_mssBl.get(0).set_color(color(na))...`, i.e. the internal state
  `MSS.dir` still flips even if display is off), `iBOS` (show/hide BOS lines — same
  display-only caveat is NOT present for BOS; the BOS block only executes inside the `switch`
  case guarded by `iBOS`, so **BOS detection itself is gated by the `iBOS` toggle** — this is
  an asymmetry worth flagging: MSS state always updates, BOS events only get evaluated if
  `iBOS` is true).
- **Signal-relevant fields:** `ict_mss_bullish` (bool), `ict_mss_bearish` (bool),
  `ict_bos_bullish` (bool), `ict_bos_bearish` (bool), plus the broken price level and the
  zigzag vertex bar index/time for each event (needed for forward-return anchoring).
- **Notes / ambiguities:** ICT's MSS is conceptually the same idea as SMC's CHoCH (first
  break in the opposite direction of prior trend) and ICT's BOS is conceptually the same idea
  as SMC's BOS (continuation break in the same direction as current trend) — see §3
  reconciliation. They are **not numerically identical** because the pivot-detection methods
  differ (ICT: `ta.pivothigh/low(len,1)` two-sided confirmation; SMC: `leg()` one-sided
  rolling-window confirmation, §2.1). Do not merge into a single "MSS≡CHoCH" column; keep as
  distinct engines (`ict_*` vs `smc_swing_*` / `smc_internal_*` namespaces).

### 1.3 Order Blocks (OB)

- **Pine identifiers:** `swings(len)` (local function, called as `swings(length)` where
  `length` is the "Swing Lookback" input, default 10, min 3), `type ob`, `bullish_ob`,
  `bearish_ob`, inputs `showOB`, `useBody`, `showBull`, `showBear`.
- **Trigger logic:**
  - `swings(length)` independently tracks an `os` (order-block-swing) state flipped when
    `high[len] > ta.highest(len)` (→ `os=0`, bearish-biased) or `low[len] < ta.lowest(len)`
    (→ `os=1`, bullish-biased), recording a `top`/`btm` swing point at
    `high[length]`/`bar_index[length]` (resp. low) the bar the flip occurs. This is a
    **different pivot definition** from both §1.1 (ICT zigzag) and §2.1 (SMC `leg()`).
  - **Bullish OB formation:** when `close` crosses above the last unconsummated swing `top.y`
    (`close > top.y and not top.crossed`), scan backward from the swing's bar (`top.x`) to the
    current bar for the bar with the lowest `min` (=`min(close,open)` if `useBody` else
    `low`); the order block is the candle range `[maxima, minima]` at that extreme bar, where
    `maxima` is that same bar's `max` (=`max(close,open)` if `useBody` else `high`). Stored as
    `ob.new(top=maxima, btm=minima, loc=that bar's time)`, prepended to `bullish_ob`.
  - **Mitigation ("breaker"):** for each stored bullish OB, if
    `math.min(close,open) < ob.btm` → `ob.breaker := true` (price closed back through the
    block — it is "mitigated"/turned into a breaker block). If subsequently `close > ob.top`,
    the OB is fully invalidated and removed from the array.
  - Bearish OB is the exact mirror using `btm` (swing low) and the opposite scan/inequality.
  - `showBull`/`showBear` (default 1 each) only cap **how many** are displayed on the chart —
    not how many are detected/stored; the internal arrays keep growing (bounded implicitly by
    memory, not an explicit cap in this script, unlike SMC's OB arrays which cap at 100).
- **Parameters:** `length` (swing lookback, default 10, min 3), `useBody` (default true — use
  candle body vs wick for OB extremes), `showBull`/`showBear` (display count, default 1,
  min 0).
- **Signal-relevant fields:** `ict_bullish_ob_formed` (bool, at formation bar with
  `ob_top`/`ob_btm`/`ob_loc`), `ict_bullish_ob_mitigated` (bool, "breaker" transition),
  `ict_bullish_ob_invalidated` (bool, full removal), mirrored bearish. For backtesting we
  primarily need the **formation** event (entry signal) and its `top`/`btm` band plus the
  mitigation/invalidation bar (defines the natural stop-out condition for a trade taken at the
  OB).
- **Notes:** The "OB → breaker block" transition described here is exactly what other ICT
  literature calls a **Breaker Block** — LuxAlgo does not use a separate `breaker` concept
  name, it's a state (`ob.breaker=true`) of the same object. Document this explicitly:
  **"Breaker Block" = an ICT Order Block whose `.btm`/`.top` has been closed through once.**
  There is no separate "Mitigation Block" or "Rejection Block" object anywhere in either
  script — those ICT-literature terms are **not implemented** by LuxAlgo and will need to be
  defined independently in Requirement 2 if we want to test them (flagged as a gap, not
  invented here).

### 1.4 Displacement

- **Pine identifiers:** `perc_Body = 0.36` (hard-coded, not a live input — the input line is
  commented out in source: `// input.int(36,...)`), `meanBody = ta.sma(body, len)`, `L_body`,
  `L_bodyUP`, `L_bodyDN`, input `sDispl` (default **false**).
- **Trigger logic:** A bar qualifies as "clean body" (`L_body`) if both wicks are small
  relative to the body: `high - mx < body*0.36` and `mn - low < body*0.36` (`mx`/`mn` =
  `max/min(close,open)`). `L_bodyUP = body > meanBody and L_body and close > open` (bullish
  displacement candle: above-average range, clean body, bullish close). `L_bodyDN` mirrored.
- **Parameters:** `len` (shared MSS length, controls the SMA window for `meanBody`), fixed
  `perc_Body=0.36` (not user-configurable in this build despite the commented-out input).
- **Signal-relevant fields:** `ict_displacement_bullish` (bool), `ict_displacement_bearish`
  (bool).
- **Notes:** Only plotted as a shape when `sDispl=true`, but the underlying `L_bodyUP`/
  `L_bodyDN` booleans are computed unconditionally every bar (used elsewhere for FVG
  imbalance gating, §1.6, and `lwst`/`hgst` tracking) — so this is a first-class always-on
  signal for our purposes regardless of the display toggle.

### 1.5 Volume Imbalance (VI)

- **Pine identifiers:** `vImb_Bl`, `vImb_Br`, `type _2ln_lb`, `var Vimbal`, inputs `sVimbl`
  (default true), `visVim` (default 2, kept-count only).
- **Trigger logic (bullish):** `open > close[1] and high[1] > low and close > close[1] and
  open > open[1] and high[1] < mn` where `mn = min(close,open)` of the current bar. In prose:
  the current bar gapped up on open relative to the prior close, the prior bar's high stayed
  below the current bar's body low — i.e. there is a body-to-body gap between bar `[1]` and
  the current bar even though the wicks technically overlapped the *range* (this is what
  separates "Volume Imbalance" from a plain FVG, which requires the wicks to gap too).
  Bearish is the mirror.
- **Signal-relevant fields:** `ict_volume_imbalance_bullish` (bool), `ict_volume_imbalance_bearish`
  (bool), with the two price bands recorded (`[mx[1], mn]` bull / `[mn[1], mx]` bear) for
  fill-tracking.
- **Notes:** Distinct from FVG (§1.6) — do not conflate. `visVim` (max kept = 2 by default) is
  a display cap only; detection is unconditional given `sVimbl`.

### 1.6 Fair Value Gap (FVG) / Implied FVG (IFVG)

- **Pine identifiers:** `imbalanceUP`, `imbalanceDN`, `type FVG`, `bFVG_UP`, `bFVG_DN`,
  inputs `shwFVG` (default true), `i_FVG` (`'FVG'` or `'IFVG'`, default `'FVG'`), `visBxs`
  (display cap, default 2), `i_BPR` (Balance Price Range toggle, default false).
- **Trigger logic:**
  - `imbalanceUP = L_bodyUP[1] and (i_FVG=='FVG' ? low > high[2] : low < high[2])` — a 3-candle
    gap: the bar 1-back was a displacement-up candle (§1.4) and the current bar's low is above
    the high from 2 bars back (classic 3-candle FVG), **or**, if mode is `'IFVG'`
    (Implied FVG), the *inverse* inequality (`low < high[2]`) is used instead — i.e. IFVG mode
    detects the wick *overlapping* rather than gapping, which is LuxAlgo's specific definition
    of "Implied FVG" here (not the more common "inverted FVG after mitigation" definition used
    elsewhere in ICT literature — **document as a LuxAlgo-specific convention**).
  - `imbalanceDN` is the exact mirror.
  - The FVG box spans price `[low, high[2]]` (bull) or `[low[2], high]` (bear) and time
    `n-2 .. n` at formation, then is fill-tracked bar-by-bar: `border_style=dashed` once price
    has touched the top of a bullish gap (`low < box.top`), fully invalidated
    (`active := false`) once price closes through the bottom (`low < box.bottom`). Mirrored
    for bearish using `high`.
- **Parameters:** `i_FVG` (FVG vs IFVG mode), `visBxs` (display-only cap).
- **Signal-relevant fields:** `ict_fvg_bullish_formed`, `ict_fvg_bearish_formed` (with
  `top`/`bottom` band), `ict_fvg_bullish_filled`, `ict_fvg_bearish_filled` (bar the gap fully
  closed) — and a `partially_touched` intermediate state if useful for MFE/MAE analysis.
- **Notes:** LuxAlgo's ICT FVG definition requires the *middle* candle to first qualify as a
  displacement candle (`L_body`, clean-wick, above-average-range) — this is stricter than the
  textbook "any 3-candle gap" FVG definition used in the SMC script (§2.5), which has no
  displacement pre-filter but instead uses a statistical auto-threshold on bar-to-bar % move.
  **These are two different FVG definitions and must be kept as separate signal families**
  (`ict_fvg_*` vs `smc_fvg_*`), not merged.

### 1.7 Balance Price Range (BPR)

- **Pine identifiers:** `bBPR_UP`, `bBPR_DN`, input `i_BPR` (default false).
- **Trigger logic:** Overlap of the most recent bullish FVG box and most recent bearish FVG
  box: `bxUPbtm < bxDNtop and bxDNbtm < bxUPbtm` (bullish-biased BPR) or the mirrored
  condition for bearish-biased BPR. The BPR box spans `[left,right]` = union of both boxes'
  time range and `[bxDNtop, bxUPbtm]` (or mirrored) in price, with a `pos` bias field set by
  where price closed relative to the boundaries (`close > bxUPbtm ? 1 : close < bxDNtop ? -1 :
  0`).
- **Signal-relevant fields:** `ict_bpr_formed` (bool, bias direction, price band). Only
  computed at all when `i_BPR=true` (off by default) — note this is an input-gated feature,
  not always-on like FVG.
- **Notes:** BPR is inherently *derived from* the FVG engine (§1.6) — it is not an independent
  pattern detector; treat as a downstream composite feature in the same module.

### 1.8 Liquidity Pools (Buyside/Sellside) & Liquidity Sweep

- **Pine identifiers:** inside `draw()`, `//liquidity` and `//Liquidity` blocks, `type liq`,
  `b_liq_B`, `b_liq_S`, inputs `showLq` (default true), `a = 10/margin` (`margin` input,
  default 4 → `a=2.5`), `visLiq` (display cap, default 2).
- **Trigger logic:**
  - On each newly confirmed swing high (`ph` from `ta.pivothigh(hi,left,1)` inside `draw()`),
    scan the last `min(sz,50)` zigzag vertices of the **same direction** (`aZZ.d.get(i)==1`,
    i.e. prior swing highs) that fall within `±(atr(10)/a)` of the new pivot's price (a
    proximity/equal-highs cluster test). If `count > 2` (more than two prior highs cluster
    near this level → a liquidity pool of resting buy-stops), draw/update a "Buyside
    liquidity" box spanning `[avg(minP,maxP)-atr/a, avg(minP,maxP)+atr/a]`. Mirrored for swing
    lows → "Sellside liquidity" (`aZZ.d.get(i)==-1`).
  - **Sweep/break tracking:** each liquidity box tracks `brokenTop`/`brokenBtm` — for buyside
    boxes, `close > box.top` sets `brokenTop`, `close > box.bottom` sets `brokenBtm`; once
    `brokenBtm` the box is shaded (partially swept) and once *both* → `broken=true` (fully
    consumed, box right-edge frozen). Mirrored (inverted comparisons) for sellside.
- **Parameters:** `margin` input (default 4, range 2–7, inversely controls cluster tightness
  via `a=10/margin`), `visLiq` (display cap, default 2, applies independently per side).
- **Signal-relevant fields:** `ict_liquidity_pool_buyside_formed` /
  `_sellside_formed` (bool, price band, cluster count), `ict_liquidity_swept_buyside` /
  `_sellside` (bool, at the bar `brokenTop`/`brokenBtm` — as appropriate — first flips true;
  this is the event ICT calls a **"liquidity sweep" / "stop hunt"**, since price runs through
  a resting-liquidity cluster). Both formation and sweep should be separate boolean columns.
- **Notes:** This is the closest concept in either script to "Liquidity Sweep" as commonly
  described in ICT material; LuxAlgo does not use that exact term, it calls the underlying
  objects "Buyside liquidity" / "Sellside liquidity" and treats the sweep as a state
  transition (`broken`, `brokenTop`, `brokenBtm`) rather than a named event — Python must
  synthesize the explicit sweep-event boolean from these state transitions.

### 1.9 New Week Opening Gap (NWOG) & New Day Opening Gap (NDOG)

- **Pine identifiers:** `friCp/friCi`, `monOp/monOi`, `bl_NWOG`, inputs `iNWOG` (default true),
  `maxNWOG` (default 3); `prDCp/prDCi`, `cuDOp/cuDOi`, `bl_NDOG`, inputs `iNDOG` (default
  **false**), `maxNDOG` (default 1).
- **Trigger logic:** `friCp`/`friCi` latch on `dayofweek == dayofweek.friday` (last known
  Friday close price/index, updated every Friday bar). On the next `ta.change(dayofweek)` that
  lands on Monday, if `iNWOG`, draw a box from `[friCi, max(friCp,monOp)]` to
  `[monOi, min(friCp,monOp)]` — the gap between Friday's close and Monday's open. NDOG is the
  daily analogue: every day change, box between `prDCp=close[1]` (previous day's close) and
  `cuDOp=open` (today's open).
- **Parameters:** `maxNWOG`/`maxNDOG` control how many historical gap boxes are retained
  (display + memory cap, default 3 / 1 respectively).
- **Signal-relevant fields:** `ict_nwog_formed` (Monday bars only, price band
  `[min(friCp,monOp), max(friCp,monOp)]`), `ict_ndog_formed` (every day, if `iNDOG` enabled;
  **off by default** — note for daily-bar backtesting, NDOG reduces to "today's open vs.
  yesterday's close gap," which on a *daily* timeframe (our target granularity) is simply
  every day's opening gap, so this concept is directly and trivially computable on daily OHLC
  without any special session/weekday logic beyond what pandas gives for free.
- **Notes:** On **daily bars** (Requirement's target timeframe), NWOG only applies at the
  Friday→Monday boundary; NDOG applies to every single day. Since we are backtesting daily
  bars only (no intraday), both reduce to simple "did today's open gap away from the
  relevant prior close" checks — no session/timezone handling needed unlike the Killzones
  concept below, which is intraday-only and therefore **not applicable to a daily-bar
  backtest** (see §1.11).

### 1.10 Fibonacci retracement/extension between concept-pairs

- **Pine identifiers:** input `iFib` (`'FVG'|'BPR'|'OB'|'Liq'|'VI'|'NWOG'|'NONE'`, default
  `'NONE'`), `iExt`, the `_diag/_vert/_zero/_0236/.../_1618` line objects.
- **Trigger logic:** Purely a **display/measurement tool** drawn between the two most recent
  instances of whichever concept is selected — it does not generate any new detectable
  price-action event, it only computes retracement ratios (0, 0.236, 0.382, 0.5, 0.618, 0.786,
  1, 1.618) between two already-detected concept instances.
- **Signal-relevant fields:** **None as a standalone event.** May be useful later as a
  *feature* (e.g., "is price currently trading inside the 0.618–0.786 zone between the last
  two order blocks") but this is explicitly out of scope for Requirement 1's event inventory —
  flagged here as a **possible future feature engineering idea**, not a Requirement-3 event.

### 1.11 Killzones (session highlighting)

- **Pine identifiers:** `showKZ` (master toggle, default **false**), `showNy`/`ny`
  (`0700-0900 America/New_York`), `showLdno`/`ldn_open` (`0700-1000 Europe/London`),
  `showLdnc`/`ldn_close` (`1500-1700 Europe/London`), `showAsia`/`asian`
  (`1000-1400 Asia/Tokyo`), all via `time(timeframe.period, input.session(...), tz)`.
- **Trigger logic:** Pure background-shading during the named intraday session windows.
- **Signal-relevant fields:** **Not applicable to daily-bar research.** Killzones are an
  intraday session-timing concept with no meaning on a daily candle (a daily bar has no
  "New York session" sub-window). **Explicit decision: Killzones are excluded from the daily
  event detector** (Requirement 3) because the project's data is daily OHLCV only per the
  spec. If intraday data is ever added in a future iteration this concept becomes relevant
  again; documented here so it is not silently forgotten.

### 1.12 Present vs Historical mode (`i_mode`)

- **Pine identifiers:** `i_mode`, `per = i_mode=='Present' ? last_bar_index-bar_index<=500 :
  true`.
- **Trigger logic:** A display/lookback-window gate that limits *where on the chart* objects
  are drawn/evaluated (last 500 bars) vs. the full history. Several detectors (Liquidity, FVG,
  Order Block display) are wrapped in `if ... and per`.
- **Signal-relevant fields:** None directly — for a full-history vectorized backtest we always
  want "Historical" behavior (evaluate every bar of the full 2010–2026 series), so **Python
  translation should behave as `i_mode == 'Historical'` unconditionally** (i.e. drop the `per`
  gate entirely) since limiting event detection to the last 500 bars has no meaning for offline
  research. Documented as an explicit assumption.

### 1.13 Miscellaneous non-signal utilities

- `isDark` (chart background theme detection) — cosmetic only, irrelevant.
- `notransp()` — strips transparency from a color for label text — cosmetic only.
- `xloc`/`plus`/`ext` — coordinate-system helpers for the Fibonacci tool (§1.10) — cosmetic
  only.

---

## 2. Smart Money Concepts [LuxAlgo] — extracted concepts

### 2.1 Leg / pivot detection (`leg()`, "Internal" vs "Swing" structure)

- **Pine identifiers:** `leg(int size)`, `BULLISH_LEG=1`, `BEARISH_LEG=0`,
  `startOfNewLeg()`, `startOfBullishLeg()`, `startOfBearishLeg()`.
- **Trigger logic:** `newLegHigh = high[size] > ta.highest(size)`,
  `newLegLow = low[size] < ta.lowest(size)`. `leg` flips to `BEARISH_LEG` on `newLegHigh`, to
  `BULLISH_LEG` on `newLegLow` (state persists otherwise, `var`). A "new leg" starts whenever
  `leg` changes value (`ta.change(leg) != 0`). This is a **rolling max/min breakout pivot**,
  distinct in method from both ICT pivot detectors (§1.1, §1.3) — it looks `size` bars back
  and confirms a swing point only in retrospect (`size` bars of confirmation delay).
- **Two independent instantiations in the script:**
  - **Swing structure:** `getCurrentStructure(swingsLengthInput, false)` — uses
    `swingsLengthInput` (default 50, min 10) as `size`. This is the *larger*, structurally
    significant swing detector.
  - **Internal structure:** `getCurrentStructure(5, false, true)` — hard-coded `size=5`. This
    is the *smaller*, intrabar-noise-level swing detector, always using length 5 regardless of
    user input.
  - **Equal Highs/Lows structure:** `getCurrentStructure(equalHighsLowsLengthInput, true)` —
    uses `equalHighsLowsLengthInput` (default 3, min 1) as `size`, a third independent
    pivot cadence purely for EQH/EQL detection (§2.4).
- **Notes:** SMC therefore runs **three parallel pivot detectors at three different
  lookbacks** (50 / 5 / 3 by default) rather than one shared structure. This is a key
  architectural fact for the Python port: `smc_swing_*`, `smc_internal_*`, and
  `smc_eqhl_*` signal families are computed from three separately-parameterized pivot streams,
  not one.

### 2.2 BOS vs CHoCH (both Internal and Swing variants)

- **Pine identifiers:** `displayStructure(bool internal)`, `type trend`, `swingTrend`,
  `internalTrend`, constants `BOS='BOS'`, `CHOCH='CHoCH'`.
- **Trigger logic:**
  - Bullish break: `ta.crossover(close, pivot.currentLevel) and not pivot.crossed and
    extraCondition` where `pivot` is the relevant high-pivot (`internalHigh` or `swingHigh`).
    `tag = trend.bias == BEARISH ? CHOCH : BOS` — i.e. if the *prior* trend bias was bearish,
    a bullish break of structure is classified as a reversal (**CHoCH**); if prior trend was
    already bullish (or neutral/`0`), it's classified as trend-continuation (**BOS**). After
    the break, `trend.bias := BULLISH` and `pivot.crossed := true` (each pivot level fires at
    most once).
  - Bearish break mirrors this with `ta.crossunder` against the low-pivot.
  - `extraCondition` for **internal** structure additionally requires
    `internalHigh.currentLevel != swingHigh.currentLevel` (the internal pivot must be at a
    genuinely different level than the current swing pivot — prevents double-counting the
    same level as both an internal and a swing break) **and**, if
    `internalFilterConfluenceInput` is enabled, a body-dominance filter:
    `bullishBar := high - max(close,open) > min(close,open) - low` (upper wick smaller than
    lower wick, i.e. bullish-biased bar) must also hold, mirrored for bearish. Swing structure
    has `extraCondition = true` unconditionally (no confluence filter applied at the swing
    level in this script).
- **Parameters:** `showInternalBullInput`/`showInternalBearInput`/`showSwingBullInput`/
  `showSwingBearInput` (`ALL`/`BOS`/`CHOCH` filters — display-only, do not gate the underlying
  alert booleans which always fire regardless of this display filter — confirm in code:
  `currentAlerts.internalBullishCHoCH := tag==CHOCH` is set unconditionally above the
  `displayCondition` check), `internalFilterConfluenceInput` (default false).
- **Signal-relevant fields:** `smc_internal_bos_bullish`, `smc_internal_bos_bearish`,
  `smc_internal_choch_bullish`, `smc_internal_choch_bearish`, and the Swing-level equivalents
  `smc_swing_bos_bullish/bearish`, `smc_swing_choch_bullish/bearish` — eight boolean columns
  total, each carrying the broken price level and the originating pivot bar for
  return-anchoring.
- **Notes:** This is the SMC analogue of ICT's MSS/BOS (§1.2) but built on a structurally
  different pivot engine (§2.1 rolling-window `leg()` vs §1.1 `ta.pivothigh/low`), and SMC
  additionally distinguishes *two separate scales* (internal vs swing) where ICT has only one.
  Namespacing plan (§3) keeps all of these distinct.

### 2.3 Order Blocks (Internal & Swing)

- **Pine identifiers:** `storeOrdeBlock()`, `deleteOrderBlocks()`, `drawOrderBlocks()`,
  `type orderBlock`, `internalOrderBlocks`, `swingOrderBlocks`, inputs
  `showInternalOrderBlocksInput` (default true, count `internalOrderBlocksSizeInput`=5),
  `showSwingOrderBlocksInput` (default **false**, count `swingOrderBlocksSizeInput`=5),
  `orderBlockFilterInput` (`'Atr'` default, alt `'Cumulative Mean Range'`),
  `orderBlockMitigationInput` (`'High/Low'` default, alt `'Close'`).
- **Trigger logic:**
  - **Volatility-adjusted high/low parsing:** `highVolatilityBar = (high-low) >= 2 *
    volatilityMeasure` where `volatilityMeasure = ATR(200)` (default filter) or
    `cum(true_range)/bar_index` (cumulative mean range alternative). On a high-volatility bar,
    `parsedHigh/parsedLow` are **swapped** (`parsedHigh := low`, `parsedLow := high`) — an
    outlier-dampening trick so a single huge-range bar doesn't get selected as "the" order
    block candle purely because of its range.
  - **Formation:** triggered *inside* `displayStructure()` immediately after a BOS/CHoCH event
    (§2.2) fires, via `storeOrdeBlock(p_ivot, internal, BULLISH/BEARISH)`. For a bullish break,
    scan `parsedLows.slice(pivot.barIndex, bar_index)` for its **minimum**, and the order
    block is the bar at that minimum's index (`barHigh=parsedHighs[idx]`,
    `barLow=parsedLows[idx]`, `barTime`, `bias=BULLISH`) — i.e. **the most extreme down-close
    candle between the structural pivot and the breakout bar becomes the bullish order
    block**. Bearish is the mirror (scans `parsedHighs` for its maximum).
  - **Mitigation:** an order block is removed from its array when price closes/wicks (per
    `orderBlockMitigationInput`) back through its origin: bearish OB removed when
    `bearishOrderBlockMitigationSource > ob.barHigh` (mitigation source = `close` or `high`
    depending on setting); bullish OB removed when
    `bullishOrderBlockMitigationSource < ob.barLow` (source = `close` or `low`).
  - Both `internalOrderBlocks` and `swingOrderBlocks` arrays cap at 100 entries
    (`if orderBlocks.size() >= 100: orderBlocks.pop()` before each `unshift`) — unlike ICT's
    OB arrays (§1.3) which have no explicit cap.
- **Signal-relevant fields:** `smc_internal_ob_bullish_formed` / `_bearish_formed` (with
  `barHigh`/`barLow`/`barTime`), `smc_internal_ob_bullish_mitigated` / `_bearish_mitigated`,
  and the Swing-level equivalents (`smc_swing_ob_*`).
- **Notes:** Because OB formation is *derived from* a BOS/CHoCH event (it always needs a
  structure break to be created), SMC order blocks are structurally dependent on §2.2 —
  document this dependency explicitly in the Python module design (OB detector consumes
  BOS/CHoCH detector output, not an independent scan).

### 2.4 Equal Highs / Equal Lows (EQH/EQL)

- **Pine identifiers:** `drawEqualHighLow()`, called from `getCurrentStructure(...,
  equalHighLow=true)`, inputs `showEqualHighsLowsInput` (default true),
  `equalHighsLowsLengthInput` (default 3, "Bars Confirmation"), `equalHighsLowsThresholdInput`
  (default 0.1, range 0–0.5, step 0.1).
- **Trigger logic:** Using the dedicated `size=equalHighsLowsLengthInput` leg detector (§2.1,
  third instantiation), whenever a new pivot low/high of that cadence forms, compare its level
  to the **previous** `equalLow`/`equalHigh` pivot: if
  `abs(newLevel - previousLevel) < equalHighsLowsThresholdInput * ATR(200)`, it is flagged as
  an Equal Low (`EQL`) / Equal High (`EQH`) pair.
- **Signal-relevant fields:** `smc_equal_highs` (bool, both bar indices + price level),
  `smc_equal_lows` (bool, same).
- **Notes:** Threshold is expressed as a fraction of `ATR(200)`, not a fixed price/percent —
  must carry `ATR(200)` computation into the Python port exactly as specified (200-period ATR,
  not the shorter windows used elsewhere).

### 2.5 Fair Value Gap (FVG) — SMC definition

- **Pine identifiers:** `drawFairValueGaps()`, `deleteFairValueGaps()`, `type fairValueGap`,
  inputs `showFairValueGapsInput` (default **false**), `fairValueGapsThresholdInput` ("Auto
  Threshold", default true), `fairValueGapsTimeframeInput` (default `''` = chart timeframe),
  `fairValueGapsExtendInput` (default 1, bars to extend display).
- **Trigger logic:**
  - `barDeltaPercent = (lastClose - lastOpen) / (lastOpen * 100)` — the prior bar's % move.
  - `threshold = fairValueGapsThresholdInput ? cum(abs(barDeltaPercent)) / bar_index * 2 : 0`
    — an **adaptive** threshold equal to twice the running mean absolute daily % move (or `0`,
    i.e. no filter, if auto-threshold is disabled).
  - `bullishFairValueGap = currentLow > last2High and lastClose > last2High and
    barDeltaPercent > threshold` (three-candle gap **and** the middle candle's % move exceeded
    the adaptive threshold — no displacement/wick-cleanliness pre-filter unlike ICT §1.6, just
    a raw % move filter). Mirrored bearish using `-barDeltaPercent > threshold`.
  - Can be computed on a *different* timeframe than the chart via
    `request.security(..., fairValueGapsTimeframeInput, ...)` — for our daily-bars-only
    project this parameter should always resolve to the daily timeframe itself (no MTF
    fetching needed/possible without intraday data).
  - **Fill/deletion:** a stored gap is removed once `low < gap.bottom` (bullish) or
    `high > gap.top` (bearish) — i.e. **any** wick fully closing the gap invalidates it (no
    partial-fill dashed state unlike ICT's FVG, which has an intermediate "touched" state).
- **Signal-relevant fields:** `smc_fvg_bullish_formed` / `smc_fvg_bearish_formed` (band +
  threshold-passed magnitude), `smc_fvg_bullish_filled` / `smc_fvg_bearish_filled`.
- **Notes:** Reiterating §1.6 — **do not merge with ICT's FVG.** Different gap definition
  (adaptive %-move threshold vs. displacement-candle prequalification), different fill rule
  (immediate full-close removal vs. dashed/dotted partial-fill states). Namespace as
  `smc_fvg_*` vs `ict_fvg_*`.

### 2.6 Premium / Discount / Equilibrium Zones

- **Pine identifiers:** `drawPremiumDiscountZones()`, `drawZone()`, `trailingExtremes`,
  `updateTrailingExtremes()`, input `showPremiumDiscountZonesInput` (default false),
  `premiumZoneColorInput`/`equilibriumZoneColorInput`/`discountZoneColorInput` (cosmetic).
- **Trigger logic:** `trailing.top`/`trailing.bottom` are running max-high/min-low tracked
  every bar since the **last swing structural reset** (updated inside `updateTrailingExtremes
  ()`, which itself only runs when `showHighLowSwingsInput or
  showPremiumDiscountZonesInput`). Zones are simple fixed fractions of the current
  `[trailing.bottom, trailing.top]` range:
  - **Premium zone:** top 5% band, `[0.95*top + 0.05*bottom, top]`.
  - **Discount zone:** bottom 5% band, `[bottom, 0.95*bottom + 0.05*top]`.
  - **Equilibrium zone:** a band centered on the midpoint,
    `[0.525*bottom + 0.475*top, 0.525*top + 0.475*bottom]` (i.e. roughly the middle ~5% of the
    range, computed from both sides symmetrically).
- **Signal-relevant fields:** Not an "event" in the BOS/FVG sense — it's a **continuous
  price-zone classifier**. Signal-relevant output should be a categorical column per bar/day:
  `smc_zone ∈ {premium, discount, equilibrium, neither}`, computed from the daily close (or
  high/low) relative to the trailing range. Useful as a **conditioning feature** for
  combination analysis (Requirement 7, e.g. "FVG + Discount Zone") rather than a standalone
  backtestable event.
- **Notes:** `trailing.top`/`bottom` reset behavior in the Pine source is tied to
  `updateTrailingExtremes()` running every bar unconditionally once enabled (it's a simple
  running max/min, **not** reset on every new swing — re-read carefully: there is no explicit
  reset call anywhere in the script; `trailing.top`/`bottom` only ever move via `math.max`/
  `math.min` against the running high/low, so in practice this is a monotonically-expanding
  all-time high/low tracker unless the *entire* indicator state resets (it doesn't, `var`
  persists for the life of the chart). **This is worth flagging as a likely unintended-looking
  but literal behavior**: the Premium/Discount zone in this script is anchored to the
  **all-time high/low since the first bar**, not a rolling recent range. Python must replicate
  this literally (expanding min/max from series start) rather than "fixing" it to a rolling
  window, since Requirement 2 says to avoid approximations — but flag it prominently in the
  validation report as a design quirk worth testing both ways in Requirement 9/22 robustness
  analysis.

### 2.7 Strong / Weak High / Low labels

- **Pine identifiers:** `drawHighLowSwings()`, uses `trailing.top`/`trailing.bottom` and
  `swingTrend.bias`.
- **Trigger logic:** Purely a labeling convention on top of §2.6's trailing extremes: the
  current trailing high is labeled "Strong High" if `swingTrend.bias == BEARISH`, else "Weak
  High"; the trailing low is labeled "Strong Low" if `swingTrend.bias == BULLISH`, else "Weak
  Low." ("Strong" = a high/low that formed against the prevailing trend and is therefore
  considered more significant/likely to hold or be targeted as liquidity; "Weak" = formed with
  the trend, considered more likely to be taken out.)
- **Signal-relevant fields:** `smc_strong_high` / `smc_weak_high` / `smc_strong_low` /
  `smc_weak_low` — categorical labels attached to the same trailing-extreme points from §2.6,
  re-evaluated each bar based on current `swingTrend.bias`.
- **Notes:** Directly reuses §2.6's (all-time, non-rolling) trailing extremes — same caveat
  applies.

### 2.8 Multi-timeframe Highs & Lows (Daily/Weekly/Monthly levels)

- **Pine identifiers:** `drawLevels()`, inputs `showDailyLevelsInput`/`showWeeklyLevelsInput`/
  `showMonthlyLevelsInput` (all default false), `higherTimeframe()`.
- **Trigger logic:** Fetches the prior period's high/low via `request.security(...,
  timeframe, [high[1], low[1], ...])`, only evaluated `if not higherTimeframe(timeframe)`
  (i.e. only meaningful if the current chart timeframe is *lower than or equal to* the target
  level's timeframe).
- **Signal-relevant fields:** On a **daily chart** (our target), "Daily levels" (prior day's
  H/L) reduce to `high.shift(1)`/`low.shift(1)` — directly computable, no MTF fetch needed.
  "Weekly levels" (prior week's H/L) and "Monthly levels" (prior month's H/L) are genuine MTF
  concepts and require resampling the daily series to W/M before shifting.
  `smc_prior_day_high`/`_low`, `smc_prior_week_high`/`_low`, `smc_prior_month_high`/`_low` —
  continuous reference levels, not discrete events; useful as boundary levels for
  breakout/liquidity-style event definitions (e.g. "close > prior week high" could itself be
  turned into a derived breakout event during Requirement 3 design, though it is not an
  explicit named event in the Pine source itself — it is only ever drawn as a line).
- **Notes:** No signal/alert is actually generated by this feature in the Pine script (no
  `alertcondition` references it) — it is display-only. Treat as reference levels available to
  the feature-engineering layer, not a first-class event.

### 2.9 Trend-colored candles / Style theme / Confluence filter

- **Pine identifiers:** `showTrendInput`, `styleInput` (`COLORED`/`MONOCHROME`),
  `internalFilterConfluenceInput` (already covered under §2.2).
- **Trigger logic:** `showTrendInput` recolors candles by `internalTrend.bias` — purely
  cosmetic, no new information beyond what §2.2's internal trend state already provides.
  `styleInput` only remaps colors — no logic difference. `internalFilterConfluenceInput`
  is a real logic toggle already documented in §2.2.
- **Signal-relevant fields:** None beyond what's already captured in §2.2.

### 2.10 Alerts inventory (ground truth for "every event type" the author considered first-class)

The script's own `alertcondition()` block (bottom of file) is a useful cross-check of which
booleans LuxAlgo itself considered significant enough to alert on. It confirms our event list
above is complete and adds no new concepts: Internal Bullish/Bearish BOS, Internal
Bullish/Bearish CHoCH, Swing Bullish/Bearish BOS, Swing Bullish/Bearish CHoCH, Internal
Bullish/Bearish OB Breakout (mitigation), Swing Bullish/Bearish OB Breakout (mitigation),
Equal Highs, Equal Lows, Bullish FVG, Bearish FVG — 16 alerts, all already covered in §2.2–2.5.

---

## 3. Cross-script reconciliation ("one combined methodology")

The two scripts use **overlapping vocabulary for structurally different computations**. The
project brief says to treat them as one combined methodology without collapsing distinct
implementations — so the plan is a **shared event-table schema with vendor-prefixed signal
families**, not a forced 1:1 merge. Summary of overlaps and how each will be namespaced in the
Requirement 3 event dataframe:

| Concept (colloquial) | ICT engine (this doc) | SMC engine (this doc) | Python namespace(s) |
|---|---|---|---|
| Structure break, continuation | §1.2 MSS→BOS (single scale, `ta.pivothigh/low` pivots) | §2.2 BOS (two scales: internal + swing, `leg()` pivots) | `ict_bos_*`, `smc_internal_bos_*`, `smc_swing_bos_*` |
| Structure break, reversal | §1.2 "MSS" (ICT's own term for the *first* reversal break) | §2.2 CHoCH | `ict_mss_*`, `smc_internal_choch_*`, `smc_swing_choch_*` |
| Order Block | §1.3 (single scale, formed at scanned extreme between swing & breakout) | §2.3 (two scales: internal + swing, formed at parsed-volatility extreme between pivot & breakout, derived from §2.2's BOS/CHoCH) | `ict_ob_bullish/bearish_*`, `smc_internal_ob_*`, `smc_swing_ob_*` |
| Breaker Block | §1.3 (`ob.breaker` state on an ICT OB) | *not present as a distinct concept in SMC script* | `ict_ob_breaker_*` only |
| Fair Value Gap | §1.6 (displacement-prequalified 3-candle gap; FVG/IFVG variants) | §2.5 (adaptive %-move-threshold 3-candle gap; single-timeframe or MTF) | `ict_fvg_*`, `smc_fvg_*` |
| Liquidity pool / sweep | §1.8 (explicit clustered-pivot pools with sweep state machine) | *no direct equivalent — SMC has no liquidity-pool concept at all* | `ict_liquidity_*` only |
| Equal Highs/Lows | *not present in ICT script* | §2.4 (`ATR`-relative threshold on dedicated pivot cadence) | `smc_equal_highs/lows` only |
| Premium/Discount/Equilibrium | *not present in ICT script* | §2.6 (fixed % bands on all-time trailing range) | `smc_zone` only |
| Opening gaps | §1.9 NWOG/NDOG (calendar-anchored: Fri→Mon, prior day→today) | *not present in SMC script* | `ict_nwog_*`, `ict_ndog_*` only |
| MTF reference levels | *not present in ICT script* | §2.8 (prior D/W/M high-low) | `smc_prior_*` only |
| Displacement | §1.4 (clean-body, above-average-range candle) | *not present as a named concept, though the confluence filter in §2.2 is a related but different body-dominance test* | `ict_displacement_*` only |
| Volume Imbalance | §1.5 | *not present in SMC script* | `ict_volume_imbalance_*` only |

**Decision:** every concept becomes its own column(s) in the master event dataframe
(Requirement 3), vendor/scale-prefixed as shown above. No concept is silently dropped, and no
two differently-computed concepts are collapsed under one shared column name, even when the
colloquial trading term is identical (e.g. "BOS" appears three times with three different,
independently-testable definitions). This lets Requirement 6 (Concept Ranking) and Requirement
7 (Combination Analysis) treat `ict_bos_bullish` and `smc_swing_bos_bullish` as two separate,
independently-scored hypotheses, which directly serves the research question ("do these
concepts work" — plural, precisely because they are not the same signal).

---

## 4. Concept inventory checklist (cross-reference against the brief's example list)

| Requirement-1 example term | Covered by | Status |
|---|---|---|
| Market Structure Break | §1.2, §2.2 | ✅ |
| Break of Structure (BOS) | §1.2, §2.2 | ✅ |
| Change of Character (CHoCH) | §2.2 (`MSS` in ICT is the equivalent first-reversal-break concept) | ✅ |
| Order Blocks | §1.3, §2.3 | ✅ |
| Fair Value Gaps | §1.6, §2.5 | ✅ |
| Liquidity Sweeps | §1.8 | ✅ (ICT only) |
| Liquidity Pools | §1.8 | ✅ (ICT only) |
| Equal Highs | §2.4 | ✅ (SMC only) |
| Equal Lows | §2.4 | ✅ (SMC only) |
| Premium / Discount Zones | §2.6 | ✅ (SMC only) |
| Mitigation Blocks | §1.3, §2.3 (`.breaker` / mitigation removal logic) | ✅ — no separately-named object, it's a *state*, documented |
| Breaker Blocks | §1.3 | ✅ (ICT only; SMC has no equivalent) |
| Rejection Blocks | — | ❌ **Not implemented in either script.** No Pine logic corresponds to this term. Documented as a gap, not fabricated. |
| Displacement | §1.4 | ✅ (ICT only) |
| Imbalance | §1.5 (Volume Imbalance), §1.6/§2.5 (FVG = price imbalance) | ✅ |
| Swing High | §1.1, §1.3, §2.1 | ✅ (three different pivot engines) |
| Swing Low | §1.1, §1.3, §2.1 | ✅ |
| Internal Structure | §2.1, §2.2, §2.3 | ✅ (SMC only) |
| External Structure | §2.1, §2.2, §2.3 (SMC calls this "Swing" structure, not "External" — same concept, different name) | ✅ — terminology note added |
| Optimal Trade Entry (OTE) | — | ❌ **Not implemented in either script.** No Fibonacci-retracement-based entry-zone logic keyed to a specific 0.62–0.79 band exists; §1.10's generic Fibonacci tool is a display measurement between arbitrary concept pairs, not an OTE rule. Documented as a gap. |
| Kill Zones | §1.11 | ✅ (ICT only; explicitly excluded from daily-bar signal detection, see §1.11) |
| NWOG / NDOG | §1.9 | ✅ (ICT only; not in original brief list but present in source, included per "do not skip anything") |
| Balance Price Range (BPR) | §1.7 | ✅ (ICT only; not in original brief list but present in source, included) |
| Volume Imbalance (VI) | §1.5 | ✅ (ICT only; not in original brief list but present in source, included) |
| Strong/Weak High/Low | §2.7 | ✅ (SMC only; not in original brief list but present in source, included) |
| MTF Highs & Lows | §2.8 | ✅ (SMC only; not in original brief list but present in source, included) |

**Two gaps found and explicitly flagged (not silently invented):** *Rejection Blocks* and
*Optimal Trade Entry* are named in the brief's example list but have no corresponding Pine
logic in either supplied script. Per Requirement 2 ("If any TradingView-specific functionality
exists, recreate equivalent logic... avoid approximations unless absolutely necessary,
document any assumptions"), these two will **not** be implemented as invented logic. If the
user wants them tested, that requires either (a) a definition provided by the user, or (b) an
explicit, separately-flagged design decision to adopt a common published definition — to be
raised as a question before Requirement 3, not decided unilaterally here.

---

## 5. Assumptions log (for Requirement 2 carry-forward)

1. **Daily bars only, no intraday.** Killzones (§1.11) are excluded entirely; NWOG/NDOG
   (§1.9) reduce to simple prior-close/open gap checks; "MTF" concepts (§2.8) reduce to
   resample-and-shift operations.
2. **"Historical" mode semantics, not "Present."** The `per` display-window gate (§1.12) is
   dropped; every bar in the full history is eligible for event detection.
3. **Trailing extremes in §2.6/§2.7 are literally all-time expanding min/max**, not a rolling
   window, per a direct reading of the Pine source (no reset logic found). This will be
   validated in Requirement 22 and explicitly re-tested with a rolling-window variant as a
   robustness check, but the *default* Python behavior will match the literal Pine logic.
4. **BOS detection in ICT is gated by the `iBOS` display input** in the source (an asymmetry
   vs. MSS, which always updates internal state regardless of `iMSS`) — Python will treat BOS
   as always-computed (equivalent to `iBOS=true`), since a research framework should not
   silently disable signal computation based on what was a display toggle in the original
   indicator. Documented as a deliberate deviation, not an oversight.
5. **Two FVG definitions, two Liquidity definitions' worth of asymmetry, etc. are preserved
   as separate signal families** (§3 table) rather than merged — this is the single biggest
   design decision in this document and is restated here for visibility.
6. **"Rejection Blocks" and "Optimal Trade Entry"** are not implemented (§4) pending user
   input.
7. **Tickers with punctuation** (`BRK.B`, `BF.B`) in `data/raw/sp500_constituents.csv` will
   need `.`→`-` conversion for yfinance (`BRK-B`, `BF-B`) during data ingestion (Requirement 3
   prep) — noted here, to be handled in the ingestion module, not this document.
8. Several tickers in the constituents list appear to be recent spin-offs/renames with
   possibly short price histories on Yahoo Finance relative to the requested 2010–2026 window
   (e.g. `GEV`, `SOLV`, `VLTO`, `SW`, `PSKY`, `HONA`, `FDXF`, `Q`, `SNDK`) — data availability
   for these will be assessed and reported in the Data Quality Validation stage (Requirement
   22), not assumed here.

---

## 6. What this document is NOT

- It is not Python code. No signal detection logic has been implemented yet (that is
  Requirement 2, a separate approved task).
- It does not decide backtesting mechanics (entry timing, holding periods, transaction costs)
  — that is Requirement 4.
- It does not finalize the exact column names/schema for the master event dataframe — the
  namespace *prefixes* are fixed here (§3) but exact schema (data types, index structure) will
  be finalized when Requirement 3 is scoped and approved.
