---
title: "Do Smart Money Concepts Predict Returns? Evidence from 44 Formalised Detectors on S&P 500 Daily Bars, 2010–2026"
author: "Harsha Tangirala"
date: "September 2026"
abstract: |
  Smart Money Concepts (SMC) and Inner Circle Trader (ICT) methods are widely
  taught discretionary trading frameworks with almost no peer-reviewed
  evaluation. We translate two widely used open-source Pine Script
  implementations into 44 formally specified event detectors and test them on
  daily data for 496 S&P 500 constituents from January 2010 to June 2026: 2.20
  million events and 17.6 million simulated trades over eight holding horizons.
  Each trade is measured against its own ticker's unconditional return — a
  composition-matched null — and inference uses calendar-time Newey–West
  standard errors. A calibration study with a known zero edge shows this to be
  the only one of three candidate tests whose size stays near nominal (at most
  6.8% at a nominal 5%) when signals cluster on the same dates or in volatile
  markets. Against a zero-return null, 38 of 44 concepts appear significant.
  Against the matched null, with Benjamini–Hochberg control across all 352
  concept × horizon hypotheses, none beats random entry at any horizon and none
  is significantly worse; an exact rotation test finds no winners either. The
  largest well-measured point estimates, 11–12 basis points over ten days for
  two liquidity-sweep detectors, have p ≥ 0.23. For ten concepts the data
  exclude, at 95% confidence, an edge large enough to cover the lowest modelled
  round-trip cost of 11 bp; the median concept's minimum detectable edge is 45
  bp. Concepts selected on three years of data earn −39 bp out of sample. The
  study is a corrected re-analysis: an earlier version reported 28 of 42
  concepts beating random entry, 27 of which in fact lost to it, and this
  re-analysis's own first draft reported five winners using a variance formula
  that rejects 28–41% of uninformative clustered signals. We document how each
  error manufactures a positive result from the same data.
keywords: [technical analysis, smart money concepts, ICT, market efficiency, multiple testing, calendar-time inference, test calibration, backtest overfitting]
---

# 1. Introduction

Smart Money Concepts (SMC) and the Inner Circle Trader (ICT) methodology are
retail trading frameworks built around the premise that institutional order flow
leaves identifiable footprints in price: order blocks, fair value gaps, liquidity
sweeps, breaks of market structure. They are taught to a very large audience —
the associated TradingView indicators have hundreds of thousands of users — and
they are almost entirely absent from the academic literature.

The gap is partly definitional. SMC/ICT concepts are usually taught by example
rather than by rule, so two practitioners will mark up the same chart
differently, and there is no canonical specification to test. This paper takes a
narrow and tractable version of the question: we test two specific, widely used
open-source implementations, treat their code as the operational definition, and
ask whether the events they detect carry information about subsequent returns.

Our contribution is threefold.

**First, a formalisation.** We translate every detector in the two source scripts
into Python and publish a machine-readable specification for each — a boolean
expression over OHLCV, a stated direction, parameters with defaults and allowed
ranges, and an explicit argument that the detector reads no future bar. Where the
source is ambiguous, we name the ambiguity and justify the reading we chose.

**Second, a benchmark and a calibrated test.** The natural null hypothesis —
"mean forward return is zero" — is nearly uninformative over a 16-year bull
market, because any long-biased signal clears it on market drift alone. We
measure each trade against its own ticker's unconditional forward return, which
holds the ticker mix and per-ticker trade count fixed: a *composition-matched*
null. The harder problem is inference. SMC/ICT events cluster: a broad market
move triggers the same detector on hundreds of tickers on the same day, and many
detectors fire preferentially in turbulent markets. We compare three tests of the
matched excess in a calibration study with a known zero edge and find that only a
calendar-time Newey–West test keeps its size near nominal under both kinds of
clustering.

**Third, an audit.** This study is a corrected re-analysis of an earlier version
of the same pipeline, which reported that 28 of 42 concepts were "significant
versus a random-entry baseline". Twenty-seven of those 28 were significantly
*worse* than random entry — the test was two-sided — and two of the 42 concepts
were computed from up to 60 bars of future data. The re-analysis's own first
draft made two further errors, reporting five winning concepts on the strength of
a variance formula that ignores calendar clustering and an order-block detector
that selected the wrong candle. Section 6 treats all of this as a finding rather
than an erratum: each error is ordinary, and each converts a null result into an
apparently positive one.

The headline result is negative. No concept beats the composition-matched null at
any of eight horizons after multiple-testing control, and none is significantly
worse. We are explicit about power: for ten concepts the data exclude an edge
large enough to cover the lowest modelled trading cost, but for many others an
edge of 10–30 basis points per trade can be neither confirmed nor ruled out.

# 2. Related work

On technical analysis itself, Brock, Lakonishok and LeBaron (1992) find that
simple moving-average and range-breakout rules had predictive content in the Dow
Jones index, and Lo, Mamaysky and Wang (2000) find some statistical content in
classical chart patterns after nonparametric smoothing. Park and Irwin (2007)
survey the broader evidence and conclude that early positive results largely fail
to survive transaction costs, data-snooping adjustments and out-of-sample
testing. SMC/ICT concepts are, operationally, a family of breakout and reversal
patterns defined on swing highs and lows, and our results fit that pattern.

The multiple-testing treatment follows Benjamini and Hochberg (1995). The concern
that backtest results degrade once the number of trials is counted is developed
by White (2000) and by Sullivan, Timmermann and White (1999) for technical
trading rules specifically, and by Harvey, Liu and Zhu (2016) and Bailey and
López de Prado (2014) for the cross-section of reported strategies.

The inferential problem — overlapping *h*-day returns, and events that cluster in
calendar time — is the one the long-horizon event-study literature confronts.
Newey and West (1987) give the HAC estimator; Fama (1998) and Mitchell and
Stafford (2000) argue for calendar-time methods because event returns are
cross-sectionally dependent; Lyon, Barber and Tsai (1999) document how
conventional tests misstate their size in that setting. Loughran and Ritter
(2000) show that calendar-time methods can have low power, which is what our
calibration study finds for dispersed events. Randomization inference goes back
to Fisher (1935); our rotation test is a randomization test that preserves the
cross-sectional structure of each concept's event calendar.

# 3. Data and concept formalisation

## 3.1 Universe and sample

We use daily open, high, low, close and volume for S&P 500 constituents from
2010-01-01 to 2026-06-13, obtained from Yahoo Finance with split and dividend
adjustment. Of 503 symbols in the constituent list, 498 return data; five (AVB,
EA, EQR, HONA, SATS) are unavailable at this snapshot, which we verified is
permanent rather than transient. Of those, 496 have at least 300 bars and enter
the study.

Median coverage is 4,136 bars against 4,289 business days in the same span; the
shortfall is exactly the US market holiday calendar. Three bars violate the OHLC
invariant materially (APH on 2021-05-05 and 2023-06-05, HUBB on 2021-05-05, all
back-adjustment artefacts of 0.12–0.38% of close); we repair them by clamping
high and low to enclose open and close. A further 1,301 bars carry violations
below 10⁻⁶ of close, which is float representation noise.

**Sectors** are the published GICS classification from a committed constituent
snapshot: eleven sectors, every analysed ticker classified. A hand-curated map
used earlier left 54 constituents unclassified and mis-classified six.

**Survivorship.** The constituent list is a 2026 snapshot applied to 2010–2026.
The snapshot's index-entry dates size the problem: of the 498 constituents with
price data, 265 were index members at the sample start and 233 joined during it,
so at least 235 of the 500 index slots at the start — 47% — were held by firms
that have since been removed and are absent here. Section 5.7 removes
the part of the bias that can be removed (trading a firm before it joined the
index); the removed firms cannot be recovered from free sources.

## 3.2 From Pine Script to formal specifications

The two source indicators are widely used open-source implementations of SMC and
ICT concepts, and we treat their code as the operational definition. Each detector
is published as a specification (`docs/specs/*.yaml`) giving a boolean expression
over OHLCV and derived indicators; a direction, +1 or −1, fixed in advance;
parameters with defaults (the source `input.*` values) and allowed ranges; an
expected minimum occurrence count; and an explicit argument that the detector
reads no bar after the event bar. Continuous-integration checks regenerate the
specifications and fail on drift, and a test asserts that each specification's
direction matches the direction the code trades. Where the source admits more
than one reading, the choice and its rationale are recorded in a disambiguation
register (`docs/disambiguation.md`, 16 entries) with a table of which choices
could move a published number.

## 3.3 Prospective definition and the treatment of confirmation

Several SMC/ICT concepts are conventionally described with hindsight — a
liquidity sweep is "confirmed" when price later reverses; a fair value gap is
"filled" when price later returns to it. A detector written that way cannot be
traded, because its value at the event bar depends on subsequent bars. We enforce
a strict separation. Detection is prospective: an event fires on the bar at which
all its conditions are observable. Confirmation windows become *evaluation
labels*, carried in separate columns and excluded from the tradeable event set.

- **Liquidity sweep.** Penetration of the most recent confirmed swing level by at
  least *X* × ATR, followed by a close back past that level within *Z* bars. The
  event is stamped on the *reclaim* bar, so every input is observable at the
  moment of the trade (*X* = 0.25, *Z* = 3 by default; both are swept in Section
  5.6). The source's own sweep fires when price merely enters a liquidity pool,
  with no rejection leg; it is kept alongside under its original name.
- **Opening gaps.** The source's new-day gap test is true on every bar; a gap
  event requires |open − previous close| ≥ 0.10 × ATR(14), split by direction.
- **Fair value gap fill.** "Filled within *N* bars" is a label, not a signal
  (*N* = 60, the longest horizon we test).
- **Order block mitigation.** A bullish order block *failing* is scored as a
  bearish event, not a bullish one.

## 3.4 Detected events

The 44 detectors produce 2,204,425 events across 496 tickers, every one with a
direction of +1 or −1. Twenty-two concepts are long and twenty-two short. Event
frequency ranges from 1,245 (`smc_swing_bos_bearish`) to 212,461
(`ict_displacement_bullish`). Order blocks follow LuxAlgo's `storeOrdeBlock`
exactly: for a bullish block, the bar with the lowest low between the swing pivot
and the break, removed once mitigated (Section 6.5 describes the translation
error this replaced).

# 4. Methodology

## 4.1 Trade construction

For an event on bar *p* and holding period *h* ∈ {1, 2, 3, 5, 10, 20, 40, 60}:
entry is at `close[p]`, exit at `close[p+h]`, and maximum favourable and adverse
excursion are computed over `high/low[p+1 … p+h]`. Returns are signed by the
event's direction. This yields 17,552,994 trades, 2,198,125 of them at the
primary horizon *h* = 10.

No-look-ahead is enforced mechanically rather than by inspection, by two
independent checks. An index-position audit re-derives the exact bar indices each
trade reads and asserts that every exit and excursion bar is strictly greater
than the entry bar. A truncation-invariance test recomputes every detector on data
cut at bar *i* and requires the value at bar *i* to be unchanged; a detector that
reads a future bar flips. A deliberate canary — the known-leaky fill label —
confirms the probe is sensitive, so a pass is not vacuous.

## 4.2 The composition-matched null

Let trade *i* on ticker *t(i)* have direction *d_i* ∈ {+1, −1} and signed forward
return *r_i* = *d_i* (close[*p*+*h*]/close[*p*] − 1), and let *μ_t* be the mean
of all *h*-day forward returns on ticker *t*. The trade's excess is

$$e_i = r_i - d_i\,\mu_{t(i)},$$

and a concept's excess *ē* is the mean over its *N* trades. Equivalently, *ē* is
the concept's mean return minus the mean return of entering the same tickers the
same number of times on randomly chosen dates, Σ_t n_t d μ_t / N. Mean returns
differ enormously across names over 2010–2026, so a benchmark drawn from a
different ticker mix measures composition as much as signal quality; this one
does not.

## 4.3 Inference

**Primary: calendar-time Newey–West.** Two dependence structures make an iid test
invalid. *h*-day returns started on consecutive days share *h*−1 days of price
path; and trades entered on the same date across hundreds of tickers share the
market factor, so the effective number of observations is closer to the number of
entry dates than to the number of trades. We collapse trades to a business-day
calendar: with *n_d* trades on date *d* and date-mean excess *ē_d*, let
*x_d* = *n_d*(*ē_d* − *ē*)/*N*, with *x_d* = 0 on dates without trades. The
variance of *ē* is estimated as

$$\widehat{V} = \sum_d x_d^2 + 2\sum_{\ell=1}^{h}\Big(1-\tfrac{\ell}{h+1}\Big)\sum_d x_d\,x_{d-\ell},$$

and the test is one-sided: *p* = 1 − Φ(*ē*/√*V̂*).

**Secondary: exact rotation.** Shift the concept's whole entry calendar by an
offset *o*, the same for every ticker and wrapping circularly, and re-read each
trade's forward return at the shifted date. This preserves the ticker mix, the
per-ticker counts, the spacing of entries and — crucially — which trades share a
date. We evaluate every admissible offset (*o* = *h*+1, …, *T*−*h*−2; 4,014–4,132
offsets per hypothesis) rather than a sample: the rotated mean is a ratio of two
circular cross-correlations, which a fast Fourier transform gives for all offsets
at once. The p-value is (1 + #{*o*: rotated mean ≥ observed}) / (1 + number of
offsets). Enumeration matters: a sampled test with 1,000 rotations cannot produce
a p-value below 1/1001, which is above the smallest Benjamini–Hochberg threshold
of 0.05/352.

**Superseded: the simple-random-sampling variance.** If each concept's null entry
dates were a uniform random subset of each ticker's *N_t* bars, drawn
independently across tickers, the exact variance of the matched null mean would be

$$\operatorname{Var}[\bar r] = \frac{1}{N^2}\sum_t n_t\,\sigma_t^2\,\frac{N_t-n_t}{N_t-1}.$$

The first draft of this re-analysis used it, validated against a simulation that
drew dates the same way. Both treat trades on the same date as independent, and
Section 4.4 shows the consequence. Its p-value is kept in the results table for
comparison only.

**Decision rule.** Tests are one-sided. Benjamini–Hochberg control at α = 0.05 is
applied once across all 352 (concept × horizon) hypotheses. A concept *beats* the
null only if its excess is positive, it survives FDR, and it rests on at least 30
trades. Whether a concept is significantly *worse* than the null is a separate
two-sided family with its own FDR correction.

## 4.4 Calibration of the tests

A test should be judged on the dependence structure of the signals it will be
applied to, not on the one it assumes. We therefore measure the size of each test
in six designs where the true edge is exactly zero (1,000 replications each,
one-sided, nominal 5%; Monte Carlo standard error 0.7 percentage points).

The first three hold 60 real price paths fixed and randomise only the entry
dates: each ticker picks its own 80 dates (*independent*), picks 80 from a shared
pool of 400 (*semi-clustered*), or every ticker fires on the same 150 dates
(*clustered*). The last three redraw a simulated 60-ticker panel on every
replication — a GARCH(1,1) market factor plus GARCH(1,1) idiosyncratic noise with
Student-*t*(5) shocks (Bollerslev 1986), compounded arithmetically so that every
*h*-day forward return has conditional mean exactly zero whatever the past. On it,
entries are *independent*, *clustered*, or *volatility-timed*: each ticker fires on
random dates from its top decile of trailing 20-day volatility, so entries crowd
into turbulent markets, as displacement and structure-break detectors do.

**Table 1.** Rejection rate at a nominal 5%, h = 10. In brackets: the standard
error the test reports divided by the true standard deviation of its estimate
across replications (above 1 is conservative). Figure 7 plots both.

| Design (true edge = 0) | SRS variance (superseded) | Calendar-time (primary) | Exact rotation (secondary) |
|---|---:|---:|---:|
| Real prices, independent | 5.7% (0.98) | 0.0% (1.80) | 5.8% (0.98) |
| Real prices, semi-clustered | **28.1%** (0.50) | 3.5% (1.27) | 7.3% (1.03) |
| Real prices, clustered | **40.6%** (0.24) | 6.8% (1.11) | 6.9% (1.02) |
| Simulated, independent | 5.1% (1.01) | 0.0% (2.02) | 5.0% (1.02) |
| Simulated, clustered | **34.3%** (0.22) | 3.0% (1.10) | 4.4% (0.99) |
| Simulated, volatility-timed | **38.3%** (0.14) | 5.0% (0.87) | **18.8%** (0.45) |

Three results follow.

*The SRS variance is right only when entries are independent.* With clustered or
volatility-timed entries it rejects 28–41% of uninformative signals. Real SMC/ICT
signals are more clustered than any design in the table: across the 352
hypotheses the calendar-time standard error of the matched excess is a median 7.0
times the SRS one (range 1.4–16.2).

*The calendar-time test is conservative when entries are dispersed and close to
nominal otherwise.* With dispersed entries its Newey–West sum picks up the
realised co-movement of overlapping returns on different tickers, which —
because each trade is measured against its own ticker's in-sample mean —
contributes nothing to the true sampling variance; the reported standard error is
roughly double and the test never rejects. Under clustering its size is 3.0–6.8%,
and under volatility timing 5.0%. It is the only one of the three that stays near
nominal in every design in which entries cluster.

*The rotation test is exact for random timing but conditions on the realised
path.* When entries crowd into volatile periods, rotated calendars land mostly in
calm ones, the null distribution is too narrow, and the test rejects 18.8% of
uninformative signals.

We therefore take the calendar-time test as primary and report the rotation test
beside it, reading a rotation rejection that the primary test does not confirm as
uninformative. The price of the choice is power against dispersed signals;
Section 5.3 reports what it means for what the study can exclude.

## 4.5 How much the standard errors move

For the test against a zero mean, the calendar-time standard error is between 1.6
and 12.3 times the iid one across the 44 concepts at h = 10, with a median of 6.2
(Table 2). `ict_nwog_gap_down`'s 130,643 trades carry about as much information as
890 independent observations — close to its 851 distinct week-open entry dates.

**Table 2.** Standard-error inflation, test against zero, h = 10: the five largest.

| Signal | n trades | iid SE | Calendar-time SE | Ratio |
|---|---:|---:|---:|---:|
| `smc_internal_ob_bullish_mitigated` | 39,612 | 0.00040 | 0.00494 | 12.3× |
| `ict_nwog_gap_down` | 130,643 | 0.00018 | 0.00220 | 12.1× |
| `smc_fvg_bearish_formed` | 67,673 | 0.00030 | 0.00358 | 12.0× |
| `ict_displacement_bearish` | 190,415 | 0.00015 | 0.00171 | 11.4× |
| `ict_ob_bullish_mitigated` | 20,562 | 0.00061 | 0.00675 | 11.1× |

## 4.6 Costs, out-of-sample evaluation and robustness

**Costs.** A round trip is charged 1 bp fixed plus 5 bp spread plus slippage
drawn from Uniform(5, 20) bp — 11–26 bp in total — with each draw keyed to the
trade's identity so a re-sorted table is charged identically. We report, per
concept, the break-even cost against the gross mean return *and* against the
excess over the matched null; only the second is decision-relevant.

**Walk-forward.** Rolling windows of three training years and one test year,
stepped annually: 13 folds. The five concepts with the highest training-window
excess (minimum 30 trades) are selected. Null pools are rebuilt inside each
window, and training trades whose holding period would cross into the test year
are purged.

**Parameter sensitivity.** A broad grid and a random sweep over structure
parameters on 40 tickers, and a targeted 36-configuration sweep on 30 tickers over
the parameters we chose for the reformulated sweep and gap detectors.

**Survivorship.** A membership-aware re-test drops every trade dated before the
ticker joined the index and restricts the matched-null pools the same way.

**Power.** For each concept, the minimum detectable excess at 80% power (2.49
times its calendar-time standard error) and the one-sided 95% upper confidence
bound on its excess.

# 5. Results

## 5.1 The benchmark and the test determine the conclusion

**Table 3.** Concepts significant at h = 10 (of 44) and hypotheses significant
across all horizons (of 352), by benchmark and test; BH-FDR at α = 0.05 across
all 352.

| Benchmark and test | h = 10 | All horizons |
|---|---:|---:|
| Zero-return null, calendar-time | 38 / 44 | 268 / 352 |
| Matched null, SRS variance (superseded) | 4 / 44 | 28 / 352 |
| Matched null, exact rotation (secondary) | 0 / 44 | 0 / 352 |
| **Matched null, calendar-time (primary)** | **0 / 44** | **0 / 352** |
| Significantly *worse* than the matched null, calendar-time, two-sided | 0 / 44 | 0 / 352 |

On identical data, the count runs from 38 significant concepts to none depending
on the benchmark, and from 4 to none depending on the variance formula used with
the right benchmark. The mean excess over the matched null across all 44 concepts
at h = 10 is −11.0 bp, and 37 of the 44 point estimates are negative (Figure 1).
Nothing clears the primary test at any horizon: the smallest unadjusted one-sided
p-value among all 352 hypotheses is 0.062, and at h = 10 it is 0.229. Nothing
loses to the null either; the smallest adjusted two-sided p-value is 0.061.

The rotation test finds no winners. It does flag 54 hypotheses (5 at h = 10) as
significantly worse than rotated timing, concentrated in the displacement and
break-of-structure detectors, which fire on large-range bars. That is the
volatility-timed case in which Table 1 shows the rotation test rejecting 19% of
uninformative signals, so we do not read it as evidence.

## 5.2 The largest point estimates

**Table 4.** Every concept with a positive excess at h = 10. Returns in basis
points over ten trading days; SE is the calendar-time standard error of the
excess; p-values one-sided and unadjusted.

| Signal | Dir | n trades | Entry dates | Mean | Matched null | Excess | SE | p (primary) | p (rotation) | p (SRS) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `smc_swing_choch_bearish` | −1 | 2,653 | 1,074 | −36.8 | −69.4 | +32.5 | 115.3 | 0.39 | 0.16 | 0.003 |
| `smc_swing_ob_bearish_formed` | −1 | 3,898 | 1,404 | −49.3 | −68.7 | +19.4 | 91.6 | 0.42 | 0.24 | 0.027 |
| `ict_sweep_sellside_bullish` | +1 | 49,304 | 3,919 | +82.2 | +70.2 | +11.9 | 21.3 | 0.29 | 0.18 | <0.0001 |
| `ict_sweep_buyside_bearish` | −1 | 65,448 | 4,002 | −59.2 | −70.6 | +11.4 | 15.3 | 0.23 | 0.10 | <0.0001 |
| `ict_liquidity_buyside_pool_formed` | +1 | 58,941 | 3,921 | +74.3 | +68.5 | +5.8 | 15.1 | 0.35 | 0.20 | 0.008 |
| `ict_nwog_gap_up` | +1 | 147,321 | 852 | +76.7 | +71.9 | +4.8 | 17.9 | 0.39 | 0.26 | 0.001 |
| `smc_swing_choch_bullish` | +1 | 2,699 | 1,484 | +73.4 | +69.5 | +3.9 | 16.9 | 0.41 | 0.42 | 0.37 |

Seven concepts have positive point estimates, and none is close to significant.
The two liquidity-sweep detectors are the best measured of them — tens of
thousands of trades on about 4,000 entry dates each — at +11–12 bp, with
one-sided p-values of 0.23 and 0.29. The two largest estimates belong to
swing-structure concepts with fewer than 4,000 trades concentrated on 1,000–1,400
dates, whose standard errors of 92–115 bp make them uninformative. The SRS column
shows how the superseded variance turned four of these into apparent
discoveries: for `ict_nwog_gap_up`, 147,321 trades on 852 week-open dates, it
reports a standard error of 1.5 bp against the calendar-time 17.9 bp.

## 5.3 What the data can exclude

A null result is only as informative as the test's power. The median concept's
calendar-time standard error at h = 10 is 18.2 bp, so its minimum detectable
excess at 80% power is 45 bp; the best-measured concept's is 27 bp. Table 5 turns
this around and asks which edges the data rule out.

**Table 5.** One-sided 95% upper confidence bound on each concept's excess at
h = 10, against the modelled 11–26 bp round-trip cost band.

| Upper bound on the excess | Concepts | What the data exclude |
|---|---:|---|
| below 0 bp | 3 | any positive edge (5% level, before adjustment) |
| 0 to 11 bp | 7 | an edge that covers even the lowest round-trip cost |
| 11 to 26 bp | 17 | an edge that covers the highest round-trip cost |
| 26 bp or more | 17 | nothing of economic interest |

Ten concepts have a bound below 11 bp — among them both ICT break-of-structure
detectors, both displacement detectors, and the bullish fair-value-gap,
order-block and volume-imbalance detectors — so the data say, at 95% confidence,
that they carry no edge that pays for trading them. For the 17 concepts in the
last row, including both liquidity-sweep detectors (bounds of 37 and 47 bp), the
data are consistent both with no edge and with an economically meaningful one.

## 5.4 Out-of-sample performance

**Table 6.** Walk-forward evaluation, 13 folds (train 3 years, test 1 year, step
1 year; five concepts selected per fold on training excess). Figure 5.

| Quantity | Value |
|---|---:|
| Mean in-sample excess of selected concepts | +61.3 bp |
| Mean out-of-sample excess of selected concepts | **−39.3 bp** |
| Mean out-of-sample excess of all concepts | −35.0 bp |
| Folds with a positive out-of-sample excess (selected) | 5 / 13 |
| Share of selected concepts positive out of sample | 36.9% |
| Mean train-to-test rank correlation of the concept ordering | 0.34 |

Selection does not carry forward: the concepts ranked best on three years of data
earn −39 bp in the following year, slightly worse than the average concept. The
failure is concentrated. The eight folds testing 2013–2020 average +6.1 bp; the
three testing 2021–2023 average −160.6 bp. Their training windows contain the 2020
crash, and in them the selection rule picked small-sample swing-structure
concepts (`smc_swing_choch_bearish`, `smc_swing_ob_bearish_formed`,
`smc_swing_ob_bullish_mitigated`) whose training excess averaged +193.1 bp against
+21.8 bp in the other folds — the same concepts whose standard errors of around
100 bp say that such excesses are noise.

## 5.5 Costs

Measured against the gross mean return, 22 of 44 concepts clear the top of the
cost band (26 bp) — exactly the 22 long concepts, whose gross return is mostly the
market drift that random entry captures equally. Measured against the excess over
the matched null, 4 concepts clear 11 bp and 1 clears 26 bp
(`smc_swing_choch_bearish`, whose excess carries a 115 bp standard error), and none
of the four has a significant excess (Figure 6).

## 5.6 Parameter sensitivity

Results at the default parameters are not privileged. The broad grid over the
order-block swing lookback and the market-structure pivot length moves 18 of the
44 concepts (Figure 4); the other 26 do not read those parameters, so their
stability there means *untested*, not *robust*.

Because that grid does not touch the parameters of the detectors we reformulated,
a targeted sweep varies exactly those: the sweep penetration threshold
*X* ∈ {0.10, 0.25, 0.50, 1.00} ATR, the confirmation window *Z* ∈ {1, 3, 6} bars,
and the gap materiality threshold ∈ {0.05, 0.10, 0.25} ATR.

**Table 7.** Targeted sweep over the reformulated detectors' own parameters (36
configurations, 30 tickers, h = 10).

| Signal | Configurations positive | Significant (p < 0.05, unadjusted) | Mean excess | Range |
|---|---:|---:|---:|---:|
| `ict_sweep_sellside_bullish` | 33 / 36 | 0 / 36 | +18.5 bp | 29.4 bp |
| `ict_sweep_buyside_bearish` | 36 / 36 | 0 / 36 | +8.4 bp | 28.7 bp |
| `ict_nwog_gap_up` | 24 / 36 | 0 / 36 | +0.5 bp | 4.2 bp |
| `ict_nwog_gap_down` | 0 / 36 | 0 / 36 | −4.7 bp | 2.6 bp |

The sign of the sweep detectors' excess is stable across the parameter space we
chose, so their point estimates in Table 4 are not an artefact of our defaults.
But a stable sign is not significance: no configuration is significant even
before adjustment (smallest p = 0.11). The gap detector shows the opposite hazard.
On the sweep universe its excess is +2.6 bp at a 0.05 ATR materiality threshold,
+0.4 bp at our 0.10 default and −1.6 bp at 0.25 ATR: the threshold decides the
sign. Under the superseded variance `ict_nwog_gap_up` cleared FDR at the default,
so a reported edge would have rested on this choice.

## 5.7 Survivorship

**Table 8.** Membership-aware re-test, h = 10: trades dated before a ticker's
index entry are dropped, and the matched-null pools are restricted the same way.

| | Full universe | Membership-aware |
|---|---:|---:|
| Trades | 2,198,125 | 1,763,667 |
| Concepts beating the matched null | 0 | 0 |
| Concepts whose excess keeps its sign | — | 97.7% |
| Median shift in excess | — | 0.88 bp |

Dropping the 19.8% of trades that precede a ticker's index entry changes almost
nothing. The part of survivorship bias this cannot address is the absent removed
members: survivor bias inflates the signal and the null alike, so it largely
cancels in the excess — unless removed firms, which are disproportionately
distressed, responded to these patterns differently.

## 5.8 Sectors and regimes

Pooling all concepts, each trade against its own direction-matched null, Energy
is the only one of 11 GICS sectors with a positive excess (+5.4 bp, 21 tickers);
the others range from −8.6 to −22.7 bp (Figure 2). Two, Utilities and Consumer
Staples, are significantly negative after BH correction across sectors (adjusted
p = 0.029 for both). No sector is powered to detect a 10 bp effect — minimum
detectable effects run from 14.7 to 57.1 bp — and a pooled mixed-direction excess
is hard to interpret, so we treat sector results as descriptive. Across nine
trend × volatility regimes the excess is positive in three — bear/low volatility
(+26.0 bp, n = 7,645), sideways/low volatility (+12.8 bp, n = 13,549) and
bear/normal volatility (+1.5 bp) — and most negative in bear/high volatility
(−53.3 bp, n = 142,878). The two largest positive buckets are the two smallest.

# 6. What ordinary errors did to the same data

An earlier version of this pipeline concluded that 28 of 42 concepts were
"significant versus a random-entry baseline". The first draft of this
re-analysis concluded that 5 of 44 beat the matched null and that 2 of those were
robust. Both conclusions are wrong, for reasons that are ordinary, mechanical and,
we suspect, common.

## 6.1 Look-ahead through an outcome label

`ict_fvg_bullish_filled` and `ict_fvg_bearish_filled` recorded whether a fair
value gap was later filled, and stamped the answer **on the formation bar**. The
event-melting step selected every boolean column as a tradeable signal, so both
became entry signals whose value depended on up to 60 subsequent bars: 187,719
events, 4.3% of the 4,348,698-event table, which became 187,374 trades at h = 10.
They occupied both extremes of the concept ranking; `ict_fvg_bearish_filled` had
the single most negative effect size in the study.

The route matters more than the leak: the selection rule was fail-open. Any new
boolean column became tradeable by default, guarded only by a hand-maintained
deny-list. The corrected pipeline requires explicit registration with a declared
direction and raises on anything unregistered.

## 6.2 A two-sided test behind a directional claim

The significance flag came from a two-sided Welch test. A concept whose mean
return was significantly *worse* than random entry set the flag exactly as one
that was better. Of the 28 concepts flagged, **27 had a negative effect size**:
they lost to random entry, and were then listed under the heading "Signals that
beat the random-entry baseline", including entries with a Sharpe ratio of −0.199
and a mean return of −0.39%.

## 6.3 An irreproducible benchmark

The random-entry baseline seeded its generator from `hash()` applied to a string.
Python salts string hashing per process, so every run drew a different baseline;
running the original function in three interpreters produces three disjoint
entry sets. Since that baseline was the comparator behind every significance
flag, the published counts could not be reproduced.

## 6.4 Two further distortions

`ict_ndog_formed` was true whenever the open and prior close were both non-null —
on essentially every bar — contributing 1,946,675 events, 44.8% of the event
table, and dominating every pooled aggregate. Separately, `ict_bpr_bullish` and
`ict_bpr_bearish` were computed from a condition that reduces to
`upper < lower`, unsatisfiable by construction; both were false everywhere, and
the melting step drops all-false columns silently, so "42 concepts tested" was 42
of 44 declared detectors.

## 6.5 Two errors in this re-analysis's own first draft

**A variance that assumed independent entries.** The first draft tested the
matched excess with the SRS variance of Section 4.3. It is exact for independent
entry dates, and it passed the check we gave it — a 2,000-run simulation that
agreed to five decimal places — but that simulation drew dates independently per
ticker, so it shared the formula's blind spot. Table 1 shows the consequence:
28–41% false rejections under clustering. On the corrected data the SRS variance
still reports 4 winning concepts at h = 10 and 28 winning hypotheses across
horizons; the calendar-time test reports none. The same variance underlay the
first draft's sector power analysis, which found every sector adequately powered
(minimum detectable effects of 1.8–4.5 bp, against 14.7–57.1 bp from the
calendar-time standard error). A test validated by a simulation that makes the
test's own assumptions has not been validated.

**An order block taken from the wrong candle.** LuxAlgo's `storeOrdeBlock` takes,
for a bullish block, the bar with the lowest low between the swing pivot and the
break, and removes a block once it is mitigated. The first translation took the
opposite extreme and kept mitigated blocks active, so a block's mitigation could
be reported again and again. `smc_internal_ob_bearish_mitigated`, one of the first
draft's five winners, loses 4,147 of its trades under the corrected detector, and
its excess moves from +8 bp to −1 bp.

## 6.6 The joint effect

These are not exotic mistakes. A fail-open column selector, a default-argument
two-sided test, a salted hash, an unguarded boolean, a silently dropped column, a
variance formula validated against its own assumptions and an inverted `argmin`
are each a line or two of code. On the same data they move the conclusion from
"no concept beats random entry" to "28 of 42 beat random entry" or, with only the
last two, to "5 of 44 beat it". The mechanical checks of Section 4.1 — truncation
invariance, an index-position audit, a fail-closed registry and a pinned seed
derivation — and a calibration study against the dependence structure of the
actual signals are cheap enough to be worth adopting as routine.

# 7. Discussion

**What the evidence supports.** On daily bars, for large-cap US equities over
2010–2026, none of these 44 implementations of SMC/ICT concepts produces returns
distinguishable from entering the same stocks the same number of times on random
dates. For ten of them the data exclude an edge large enough to pay the lowest
modelled trading cost. The concepts that look best on past data do worse than
average out of sample.

**What it does not support.** It does not show that SMC/ICT concepts carry no
information. Three limits matter. These are two specific implementations, not the
methodology as a discretionary practice, in which a trader applies context,
confluence and judgement that no detector captures. The daily-bar restriction is
severe: the framework is most often taught on intraday FX and futures, where the
microstructure it appeals to — stop runs, resting liquidity — is more plausible.
And power is limited. The primary test, chosen because it keeps its size when
signals cluster, is conservative when they do not, and for 17 concepts —
including the two liquidity-sweep detectors with the largest well-measured point
estimates — the data cannot distinguish no edge from an edge of 30–50 bp.

**On the negative estimates.** Thirty-seven of 44 point estimates are negative,
and the ten concepts whose bounds exclude a cost-covering edge are
break-of-structure, displacement, gap and order-block-formation detectors —
concepts that in effect bet on continuation after a sharp move. That pattern is
consistent with the short-term reversal in individual stock returns documented by
Jegadeesh (1990) and Lehmann (1990). We do not claim it: no negative excess
survives the primary test's two-sided family, and the rotation test that flags
several of these concepts is the one Table 1 shows to over-reject for
volatility-timed signals.

**Interpretation.** Gross returns are large while excess returns are not. The
long concepts' average gross return at h = 10 is 63 bp; entering the same stocks
on random dates earns 71 bp. These detectors do fire, and positions opened on them
made money over 2010–2026, but that is compensation for being long a rising
market, which random entry captures equally well. The framework's error is not
that it identifies nothing; it is that it takes credit for market drift.

**Methodological lessons.** The benchmark decides whether 38 concepts are
significant or none; the variance formula decides whether 4 are or none; and the
test direction decided, in the prior version, whether 27 concepts that lost to
random entry were reported as winners. None of these is a technicality here. Our
own first draft adds one lesson: validate a test on the dependence structure of
the data it will be applied to — clustering in calendar time and clustering in
volatility — not on the structure the test assumes.

# 8. Limitations

1. **Power.** The median concept's minimum detectable excess is 45 bp (27 bp at
   best), and the primary test is conservative for dispersed signals (Table 1).
   Edges of 10–30 bp cannot be excluded for most concepts (Section 5.3).
2. **Survivorship, partly corrected.** At least 235 since-removed index members
   are absent. Look-ahead membership is removed exactly (Section 5.7); the absent
   firms are not recovered.
3. **Daily bars only.** Kill zones and all intraday structure are out of scope.
4. **Two implementations**, not SMC/ICT as a discretionary practice.
5. **Symmetric short mechanics.** Short signals are the negation of the forward
   return, with no borrow cost or availability constraint.
6. **Path-dependent metrics are descriptive.** Sharpe, Calmar and maximum
   drawdown are computed over an overlapping, cross-sectional trade sequence that
   is not an attainable equity curve; inference uses the calendar-time estimator.
7. **Single market, single period.** No other asset class, market or timeframe is
   tested.
8. **Sector and regime results are descriptive.** No sector is powered for a
   10 bp effect, and sectors are current GICS labels applied retroactively.
9. **The targeted sweep uses 30 tickers**, so its significance statements are
   weaker than the full-universe results.
10. **No economic mechanism** is proposed; this is an evaluation of indicator
    logic, not a theory paper.

# 9. Conclusion

We formalise 44 SMC/ICT detectors from two widely used open-source
implementations and test them on 496 S&P 500 constituents over 2010–2026. None
beats composition-matched random entry at any of eight horizons after
multiple-testing control, none is significantly worse, and the concepts that look
best in one window do worse than average in the next. For ten concepts the data
rule out an edge that would cover even the lowest modelled trading cost, and for
seventeen more an edge that would cover the highest; for the remaining seventeen
they are uninformative about an edge of a size that would matter.

The methodological result may be the more useful one. On identical data a
zero-return null admits 38 of 44 concepts and a composition-matched null admits
none; a variance formula that ignores calendar clustering admits 4 while
rejecting 28–41% of uninformative clustered signals in a calibration study; and a
two-sided test presented as a directional claim reversed the sign of the finding
for 27 of 28 concepts in the prior version of this analysis. Benchmark,
dependence structure, test direction and test calibration each decide the
reported conclusion in this setting.

Code, data-preparation instructions, machine-readable concept specifications,
the disambiguation register, the full statistics table and a replication package
are available in the repository.

# References

Bailey, D. H., and López de Prado, M. (2014). The deflated Sharpe ratio:
correcting for selection bias, backtest overfitting, and non-normality. *Journal
of Portfolio Management*, 40(5), 94–107.

Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a
practical and powerful approach to multiple testing. *Journal of the Royal
Statistical Society, Series B*, 57(1), 289–300.

Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity.
*Journal of Econometrics*, 31(3), 307–327.

Brock, W., Lakonishok, J., and LeBaron, B. (1992). Simple technical trading rules
and the stochastic properties of stock returns. *Journal of Finance*, 47(5),
1731–1764.

Fama, E. F. (1998). Market efficiency, long-term returns, and behavioral finance.
*Journal of Financial Economics*, 49(3), 283–306.

Fisher, R. A. (1935). *The Design of Experiments*. Oliver and Boyd.

Harvey, C. R., Liu, Y., and Zhu, H. (2016). …and the cross-section of expected
returns. *Review of Financial Studies*, 29(1), 5–68.

Jegadeesh, N. (1990). Evidence of predictable behavior of security returns.
*Journal of Finance*, 45(3), 881–898.

Lehmann, B. N. (1990). Fads, martingales, and market efficiency. *Quarterly
Journal of Economics*, 105(1), 1–28.

Lo, A. W., Mamaysky, H., and Wang, J. (2000). Foundations of technical analysis:
computational algorithms, statistical inference, and empirical implementation.
*Journal of Finance*, 55(4), 1705–1765.

Loughran, T., and Ritter, J. R. (2000). Uniformly least powerful tests of market
efficiency. *Journal of Financial Economics*, 55(3), 361–389.

Lyon, J. D., Barber, B. M., and Tsai, C.-L. (1999). Improved methods for tests of
long-run abnormal stock returns. *Journal of Finance*, 54(1), 165–201.

Mitchell, M. L., and Stafford, E. (2000). Managerial decisions and long-term stock
price performance. *Journal of Business*, 73(3), 287–329.

Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite,
heteroskedasticity and autocorrelation consistent covariance matrix.
*Econometrica*, 55(3), 703–708.

Park, C.-H., and Irwin, S. H. (2007). What do we know about the profitability of
technical analysis? *Journal of Economic Surveys*, 21(4), 786–826.

Sullivan, R., Timmermann, A., and White, H. (1999). Data-snooping, technical
trading rule performance, and the bootstrap. *Journal of Finance*, 54(5),
1647–1691.

White, H. (2000). A reality check for data snooping. *Econometrica*, 68(5),
1097–1126.

---

# Appendix A. Figures

| Figure | File | Content |
|---|---|---|
| 1 | `results/figures/fig1_concept_forest.png` | Excess over the matched null with 95% calendar-time confidence intervals, all 44 concepts at h = 10 |
| 2 | `results/figures/fig2_sector_heatmap.png` | Excess over the direction-matched null by GICS sector |
| 3 | `results/figures/fig3_trade_timelines.png` | Events of three large-sample concepts on AAPL, 2018–2019, chosen by point estimate |
| 4 | `results/figures/fig4_sensitivity_heatmap.png` | Mean excess across the broad parameter grid |
| 5 | `results/figures/fig5_walkforward.png` | In-sample versus out-of-sample excess by fold, and train-to-test rank correlation |
| 6 | `results/figures/fig6_breakeven_costs.png` | Break-even round-trip cost on the excess, against the modelled cost band |
| 7 | `results/figures/fig7_calibration.png` | Size and standard-error honesty of the three tests in six zero-edge designs |

Each figure has a CSV of its underlying values beside it, so every plotted number
can be checked rather than measured off the image. The PDF reproduces all seven
as plates in Appendix D.

# Appendix B. Pseudocode

Full machine-readable specifications are in `docs/specs/*.yaml`.

**B.1 Liquidity sweep** (`ict_sweep_buyside_bearish`)

```
L ← most recent CONFIRMED swing high      # carries its confirmation lag
for each bar i:
    # reclaim leg, evaluated before levels refresh
    if armed and (i − j) > Z:      disarm
    elif armed and close[i] < L_j − Y·ATR[i]:
        emit ict_sweep_buyside_bearish at bar i ; disarm
    # penetration leg
    if high[i] > L + X·ATR[i]:     arm with j ← i, L_j ← L
    # refresh
    if a swing high is confirmed at i:   L ← that swing's price
```
Defaults X = 0.25 ATR, Y = 0, Z = 3 bars, ATR length 14, swing lookback 10.
Every input is from bars ≤ *i*.

**B.2 Fair value gap** (`ict_fvg_bullish_formed`)

```
bullish_i ← displacement_bullish[i−1] AND low[i] > high[i−2]
gap region ← [high[i−2], low[i]]
# OUTCOME LABEL, not an entry signal:
filled_i ← ∃ k ∈ (i, i+N] : low[k] < high[i−2]
```

**B.3 Primary test: calendar-time Newey–West on the matched excess**

```
for each trade i:  e_i ← r_i − d_i·μ_t(i)     # μ_t: mean of ALL h-day returns on ticker t
ē ← mean(e);  N ← number of trades
for each business day d from the first to the last entry date:
    x_d ← Σ_{trades i on d} (e_i − ē) / N      # 0 on dates without trades
V ← Σ_d x_d² + 2 Σ_{ℓ=1..h} (1 − ℓ/(h+1)) Σ_d x_d·x_{d−ℓ}
z ← ē / √V ;  p ← 1 − Φ(z)                     # one-sided
```

**B.4 Secondary test: exact rotation**

```
F[k, s] ← h-day forward return of ticker k at calendar position s (NaN if absent)
W[k, s] ← Σ d_i over the concept's trades on ticker k at s ;  C[k, s] ← their count
G ← F with NaN → 0 ;  A ← 1 where F is finite, else 0
num(o) ← Σ_k IFFT( conj(FFT(W_k)) · FFT(G_k) )[o]    # = Σ_i d_i·G[k_i, (s_i+o) mod T]
den(o) ← Σ_k IFFT( conj(FFT(C_k)) · FFT(A_k) )[o]
S(o) ← num(o) / den(o)   for o = h+1 … T−h−2
p ← (1 + #{o : S(o) ≥ S(0)}) / (1 + number of offsets)
```

# Appendix C. Complete results

| Table | File |
|---|---|
| All 352 (concept × horizon) hypotheses: every metric, p-value (primary, SRS, two-sided), FDR-adjusted p-value, effect size and confidence interval | `results/statistics_master.csv` |
| Exact rotation test, all 352 hypotheses | `results/rotation_null_all.csv` |
| Calibration study (Table 1) | `results/test_calibration.csv` |
| Every number quoted in this paper, computed in one place | `results/manuscript_facts.json` |
| Human-readable per-concept summary at every horizon | `results/master_summary.md` |
| Pipeline validation, data quality and regression against the prior version | `results/validation_report.md` |
| Adversarial pre-read of likely referee objections | `results/reviewer_report.md` |
| Walk-forward, per fold and per concept | `results/walkforward_{summary,detail}.csv` |
| Break-even and net-of-cost tables | `results/breakeven_costs.csv`, `results/net_of_cost_rankings.csv` |
| Resampling-scheme comparison | `results/monte_carlo.csv` |
| Sector, sector power and regime breakdowns | `results/sector_analysis.csv`, `results/sector_power.csv`, `results/regime_analysis.csv` |
| Survivorship sizing and membership-aware re-test | `results/survivorship_summary.csv`, `results/survivorship_membership_aware.csv`, `results/survivorship_comparison.json` |
| Parameter sweeps (broad, random, targeted) | `results/sensitivity_{grid,random,stability}.csv`, `results/sensitivity_targeted_{grid,stability}.csv` |
| Every ambiguous reading of the source, with the choice made | `docs/disambiguation.md` |
| Every code, data and parameter change from the prior version, with rationale | `CHANGES.md` |

Reproduction: `./run_full_pipeline.sh` (see `docs/replication_guide.md`).
