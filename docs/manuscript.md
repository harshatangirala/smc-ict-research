---
title: "Do Smart Money Concepts Predict Returns? Evidence from 44 Formalised Detectors on S&P 500 Daily Bars, 2010–2026"
author: "Harsha Tangirala"
date: "September 2026"
abstract: |
  Smart Money Concepts (SMC) and Inner Circle Trader (ICT) methods are among the
  most widely taught discretionary trading frameworks, yet they have almost no
  peer-reviewed empirical evaluation. We translate two widely used open-source
  Pine Script implementations into 44 formally specified, machine-readable event
  detectors and test them on daily OHLCV data for 496 S&P 500 constituents from
  January 2010 to June 2026 — 2.23 million detected events and 17.7 million
  simulated trades across eight holding horizons. Our central methodological
  contribution is the benchmark: rather than testing mean returns against zero,
  we construct a design-based *composition-matched randomization null* that
  holds the ticker mix and per-ticker trade count fixed and asks what returns
  randomly chosen entry dates would have produced. Against a zero-return null,
  39 of 44 concepts appear significant. Against the matched null, with
  Benjamini–Hochberg control across all 352 (concept × horizon) hypotheses, only
  5 survive, and their excess returns are 5–33 basis points over ten trading
  days; a targeted sweep over the parameters we chose reduces that to 2 whose
  edge is robust to its own parameterisation. Because forward returns overlap in time and cluster cross-sectionally,
  conventional iid standard errors understate uncertainty by a median factor of
  5.8 (maximum 11.8) in this sample; we use calendar-time Newey–West standard
  errors throughout. In a 13-fold walk-forward evaluation, concepts selected on
  three years of training data earn a mean out-of-sample excess of −0.16
  percentage points. Modelled round-trip costs of 11–26 basis points exceed the
  matched-null excess of all but one concept. We conclude that these
  implementations of SMC/ICT carry little to no exploitable predictive
  information on daily US equity bars, and we document how three specific
  methodological choices — a two-sided significance test, an unmatched
  benchmark, and iid standard errors — can manufacture the opposite conclusion
  from the same data.
keywords: [technical analysis, smart money concepts, ICT, market efficiency, multiple testing, randomization inference, backtest overfitting]
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

**Second, a benchmark.** The natural null hypothesis — "mean forward return is
zero" — is nearly uninformative over a 16-year bull market, because any
long-biased signal clears it on market drift alone. We instead construct a
*composition-matched randomization null*: hold the concept's ticker mix and
per-ticker trade count fixed, and ask what mean return would arise if the entry
*dates* were chosen at random. This is a design-based test in the sense of
Fisher: the null distribution comes from the sampling design, not from an assumed
return distribution, and it removes the ticker-composition confound that makes a
pooled comparison uninterpretable.

**Third, an audit.** This study is a corrected re-analysis of an earlier version
of the same pipeline. That version reported that 28 of 42 concepts were
"significant versus a random-entry baseline". We show that 27 of those 28 were
significantly *worse* than random entry — the test was two-sided — and that two
of the 42 concepts were computed from up to 60 bars of future data. We document
each defect, its magnitude, and what the corrected analysis shows instead.
Section 6 treats this as a finding rather than an erratum: the three errors
involved are ordinary, and each independently converts a null result into an
apparently positive one.

The headline result is negative. Only 5 of 44 concepts beat the matched null at
the primary horizon; their excess returns are of the same order as trading costs;
and out of sample, concepts selected on past data do not carry their edge
forward.

# 2. Related work

The efficient-market tradition holds that publicly available technical rules
should not generate risk-adjusted profits once data-snooping is accounted for.
The methodological core of this paper follows that literature rather than the
practitioner one.

Our multiple-testing treatment follows Benjamini and Hochberg (1995) for
false-discovery control, and the broader concern that backtest results degrade
once the number of trials is counted is developed by White (2000), Sullivan,
Timmermann and White (1999) for technical trading rules specifically, and by
Harvey, Liu and Zhu (2016) and Bailey and López de Prado (2014) for the
cross-section of reported strategies. The last of these is directly relevant: the
number of configurations one can try on a fixed dataset is large enough that a
Sharpe ratio reported without a trial count is uninterpretable.

The overlapping-returns problem — that *h*-day forward returns computed on
consecutive bars share *h*−1 days of price path — is treated by Newey and West
(1987) and, in the specific context of calendar-time portfolio tests, by Fama
(1998). Our estimator is the calendar-time variant: collapse trades to the date
level, then apply Newey–West at lag *h*. This handles both the serial overlap and
the cross-sectional correlation induced by a common market factor, and Section
4.4 shows the two together account for a median 5.8× understatement of standard
errors in our sample.

Randomization inference of the kind we use for the matched null goes back to
Fisher (1935); its application here is closest in spirit to the bootstrap
reality-check literature, but exploits an exact finite-population variance rather
than simulation.

On technical analysis itself, Lo, Mamaysky and Wang (2000) find some statistical
content in classical chart patterns after nonparametric smoothing, while Park and
Irwin (2007) survey the broader evidence and conclude that early positive results
largely fail to survive transaction costs and out-of-sample testing. Our result
is consistent with that pattern: the gross returns are real, the excess over a
properly matched benchmark is small, and costs consume most of what remains.

# 3. Data and concept formalisation

## 3.1 Universe and sample

We use daily open, high, low, close and volume for S&P 500 constituents from
2010-01-01 to 2026-06-13, obtained from Yahoo Finance with split and dividend
adjustment. Of 503 symbols in the constituent list, 498 return data; five (AVB,
EA, EQR, HONA, SATS) are unavailable at this snapshot, which we verified is
permanent rather than transient. Of those, 496 have at least 300 bars and enter
the study.

Median coverage is 4,136 bars against 4,289 business days in the same span. The
3.6% shortfall is exactly the US market holiday calendar; no ticker falls below
95% coverage of its own span. Three bars in the entire sample violate the OHLC
invariant (APH on 2023-06-05 and 2021-05-05, HUBB on 2021-05-05, all
back-adjustment artefacts of 0.12–0.38% of close); we repair them by clamping
high and low to enclose open and close, the minimal change that restores the
invariant. A further 1,301 bars carry violations below 10⁻⁶ of close, which is
float representation noise rather than bad data.

**Survivorship bias.** The constituent list is a 2026 snapshot applied
retroactively, so only firms in the index today are tested. Roughly 80 tickers
begin after 2010. This inflates absolute return levels. It does *not* explain our
result, because the matched null is drawn from the same survivor-biased tickers —
the bias inflates the signal and its benchmark equally. It remains the study's
largest unaddressed threat to validity, and we return to it in Section 7.

## 3.2 From Pine Script to formal specifications

The two source indicators are widely used open-source implementations of SMC and
ICT concepts. We treat their code as the operational definition. Each detector is
published as a specification (`docs/specs/*.yaml`) giving:

- a boolean expression over OHLCV and derived indicators;
- a direction, +1 or −1, fixed in advance;
- parameters with defaults (the source `input.*` values) and allowed ranges;
- an expected minimum occurrence count;
- an explicit argument that the detector reads no bar after the event bar.

Continuous-integration checks regenerate the specifications and fail on drift,
and a test asserts that the direction in each specification matches the direction
the code actually trades.

## 3.3 Prospective definition and the treatment of confirmation

Several SMC/ICT concepts are conventionally described with hindsight — a
liquidity sweep is "confirmed" when price later reverses; a fair value gap is
"filled" when price later returns to it. A detector written that way cannot be
traded, because its value at the event bar depends on subsequent bars.

We enforce a strict separation. Detection is prospective: an event fires on the
bar at which all its conditions are observable. Confirmation windows become
*evaluation labels*, carried in separate columns and excluded from the tradeable
event set. Concretely:

- **Liquidity sweep.** Penetration of the most recent confirmed swing level by at
  least *X* × ATR, followed by a close back past that level within *Z* bars. The
  event is stamped on the *reclaim* bar, not on the penetration bar, so every
  input is observable at the moment of the trade. (*X* = 0.25, *Z* = 3 by
  default; both are swept in Section 5.4.)
- **Fair value gap fill.** "Filled within *N* bars" is a label, not a signal
  (*N* = 60, the longest horizon we test).
- **Order block mitigation.** A bullish order block *failing* is scored as a
  bearish event, not a bullish one.

Section 6.1 describes what happened when this discipline was absent.

## 3.4 Detected events

The 44 detectors produce 2,226,881 events across 496 tickers. Every event carries
a direction of +1 or −1; none is direction-less. Event frequency ranges from
1,245 (`smc_swing_bos_bearish`) to 212,461 (`ict_displacement_bullish`).

# 4. Methodology

## 4.1 Trade construction

For an event on bar *p* and holding period *h* ∈ {1, 2, 3, 5, 10, 20, 40, 60}:
entry is at `close[p]`, exit at `close[p+h]`, and maximum favourable and adverse
excursion are computed over `high/low[p+1 … p+h]`. Returns are signed by the
event's direction. This yields 17,731,944 trades.

No-look-ahead is enforced mechanically rather than by inspection, by two
independent checks. First, an index-position audit re-derives the exact bar
indices each trade reads and asserts that every exit and excursion bar is
strictly greater than the entry bar. Second, a truncation-invariance test
recomputes every detector on data cut at bar *i* and requires the value at bar
*i* to be unchanged; a detector that reads a future bar flips. A deliberate
canary — the known-leaky fill label — confirms the probe is sensitive, so a pass
is not vacuous.

## 4.2 The composition-matched randomization null

Let a concept *c* generate *n_t* trades on ticker *t*, with *N_t* the number of
eligible bars for that ticker and horizon. Under the null that entry dates carry
no information, the *n_t* entries are a uniform random subset of the *N_t* bars.
Sampling without replacement gives, for the pooled mean,

$$\mathbb{E}[\bar{r}] = \frac{1}{N}\sum_t n_t \, d \, \mu_t, \qquad
\operatorname{Var}[\bar{r}] = \frac{1}{N^2}\sum_t n_t \, \sigma_t^2 \, \frac{N_t - n_t}{N_t - 1},$$

where *μ_t* and *σ_t²* are the mean and variance of all *h*-day forward returns
on ticker *t*, *d* ∈ {+1, −1} is the concept's direction, and *N* = Σ *n_t*.

This is exact under the sampling design. It assumes nothing about how returns are
distributed or correlated in time — only that the null entry dates are drawn
uniformly. Critically, it holds the ticker mix fixed, which a pooled comparison
against a separately generated benchmark does not: mean returns differ enormously
across names over this period, so a benchmark drawn from a different mix measures
composition as much as signal quality.

We validate the analytic moments against a 2,000-run simulation across horizons
and directions: null means agree to five decimal places and standard-error ratios
fall in 0.99–1.04.

## 4.3 Significance testing

Three tests are reported per (concept, horizon):

1. **Versus zero.** Is the mean forward return different from zero? Reported, but
   weak — over 2010–2026 a long-biased signal clears it on drift.
2. **Versus the matched null.** The primary test, one-sided: is the concept
   *better* than composition-matched random entry?
3. **Versus a pooled random-entry baseline.** A one-sided Welch test, retained
   for continuity with prior work; superseded by (2) because it does not control
   ticker mix.

All tests are one-sided with the direction stated. Benjamini–Hochberg control at
α = 0.05 is applied once across the entire family of 352 (concept × horizon)
hypotheses, not within slices. A concept is recorded as beating the null only if
its excess is positive, it survives FDR, and it rests on at least 30 trades. A
significant *negative* excess is reported in its own count, never folded into a
"significant" total.

## 4.4 Standard errors under overlap and cross-sectional correlation

Two dependence structures make the iid t-test invalid here. *h*-day forward
returns started on consecutive days overlap by *h*−1 days; and trades entered on
the same date across hundreds of tickers share the market factor, so on a large
up day nearly every long trade wins together. The effective number of independent
observations is closer to the number of entry *dates* than to the number of
trades.

We use the calendar-time treatment: collapse trades to date level, then apply
Newey–West with Bartlett weights at lag *h*. With *n_d* trades on date *d* and
date mean *r̄_d*, writing *x_d* = *n_d*(*r̄_d* − *μ*)/*N*, the HAC variance of the
pooled mean is Σ *x_d*² + 2 Σ_lag *w_lag* Σ_d *x_d x_{d−lag}*.

The correction is large. Across the 44 concepts the ratio of the calendar-time
standard error to the iid one ranges from **1.5× to 11.8×, with a median of
5.8×** (Table 1). On synthetic data with a pure common market factor and no true
signal, the iid test returns *t* = −48.3 where the calendar-time estimator
returns *t* = −3.0.

**Table 1.** Standard-error inflation, selected concepts (h = 10).

| Signal | n trades | iid SE | HAC SE | Ratio |
|---|---:|---:|---:|---:|
| `ict_nwog_gap_down` | 130,643 | 0.000182 | 0.002140 | 11.8× |
| `smc_fvg_bearish_formed` | 67,673 | 0.000298 | 0.003368 | 11.3× |
| `ict_displacement_bearish` | 190,415 | 0.000150 | 0.001607 | 10.7× |
| `ict_nwog_gap_up` | 147,321 | 0.000163 | 0.001739 | 10.7× |
| `ict_displacement_bullish` | 212,461 | 0.000130 | 0.001262 | 9.7× |

This is the mechanism by which a large trade count converts into a spuriously
tiny p-value. Many p-values in the uncorrected analysis were reported as exactly
0.000; several are not significant once the panel structure is respected.

## 4.5 Costs, out-of-sample evaluation, and robustness

**Costs.** A round trip is charged 1 bp fixed plus 5 bp spread plus slippage
drawn from Uniform(5, 20) bp, giving 11–26 bp. We report, per concept, the
break-even cost against the gross mean return *and* against the excess over the
matched null. Only the second is decision-relevant.

**Walk-forward.** Rolling windows of three training years, one test year, stepped
one year, giving 13 folds. Concepts are ranked on the training window only, and
the null pools are rebuilt inside each window so the training null never sees
test prices.

**Monte Carlo.** Three resampling schemes: matched random re-entry, iid trade
shuffling, and a circular block bootstrap with 21-bar blocks that preserves
serial dependence.

**Parameter sensitivity.** Grid and randomised sweeps re-run detection under
varied parameters, reporting the sign-consistency of each concept's excess across
configurations.

# 5. Results

## 5.1 The benchmark determines the conclusion

**Table 2.** Concept counts at h = 10, by benchmark (44 concepts, BH-FDR across
352 hypotheses).

| Benchmark | Significant |
|---|---:|
| Zero-return null | **39 / 44** |
| Composition-matched random entry | **5 / 44** |
| — of which significantly worse | 0 / 44 |
| — statistically indistinguishable | 39 / 44 |

The two rows differ by a factor of nearly eight on identical data. This is the
paper's first substantive finding: against a zero-return null almost everything
looks significant, and the number reported depends almost entirely on the
benchmark chosen. The mean excess over the matched null across all 44 concepts is
−0.10 percentage points.

## 5.2 The five concepts that clear the bar

**Table 3.** Concepts beating the composition-matched null at h = 10.

| Signal | Dir | n trades | Mean | Matched null | Excess | p (FDR) | Cohen's d [95% CI] |
|---|---:|---:|---:|---:|---:|---:|---|
| `smc_swing_choch_bearish` | −1 | 2,653 | −0.37% | −0.69% | **+0.33%** | 0.033 | −0.038 [−0.077, −0.001] |
| `ict_sweep_sellside_bullish` | +1 | 49,304 | 0.82% | 0.70% | **+0.12%** | 0.0001 | 0.125 [0.110, 0.139] |
| `ict_sweep_buyside_bearish` | −1 | 65,448 | −0.59% | −0.71% | **+0.11%** | <0.0001 | −0.101 [−0.115, −0.088] |
| `smc_internal_ob_bearish_mitigated` | +1 | 42,268 | 0.79% | 0.71% | **+0.08%** | 0.038 | 0.133 [0.119, 0.148] |
| `ict_nwog_gap_up` | +1 | 147,321 | 0.77% | 0.72% | **+0.05%** | 0.011 | 0.121 [0.107, 0.135] |

Three observations.

*The magnitudes are small.* Excess returns of 5–33 basis points over ten trading
days, on effect sizes around |d| ≈ 0.1, are at the edge of economic relevance
before costs.

*The largest excess is the least reliable.* `smc_swing_choch_bearish` has the
biggest excess (+0.33%) and the smallest sample (2,653 trades). Its excess
changes sign across horizons — +0.32% at h = 10 but −3.26% at h = 60 — which is
the signature of noise rather than of a horizon-specific effect. The four
higher-*n* concepts, by contrast, show excess returns that *grow* monotonically
with horizon, reaching 27–61 bp at h = 40–60.

*Three of the five are concepts we had to reformulate.* The two sweep detectors
and the gap detector clear the bar in their corrected forms. In their original
forms they did not exist as testable events: the "sweep" fired when price merely
entered a liquidity pool, with no rejection leg, making it a near-duplicate of
pool formation; and the gap detector fired on every bar. The corresponding
original column `ict_liquidity_buyside_swept` (excess −0.045%) does not clear the
bar. Section 5.4 tests whether this reflects a real effect the loose definitions
obscured or a fortunate specification choice, by sweeping the parameters we
chose. The two sweep detectors survive that test; the gap detector does not, and
we withdraw it.

## 5.3 Out-of-sample performance

**Table 4.** Walk-forward evaluation, 13 folds (train 3y / test 1y / step 1y).

| | Selected concepts | All concepts |
|---|---:|---:|
| Mean in-sample excess | +0.65% | — |
| Mean out-of-sample excess | **−0.16%** | −0.28% |
| Mean hit rate (folds with positive OOS excess) | 53.8% | — |
| Mean train→test rank correlation | 0.387 | — |

Concepts chosen on three years of history earn a mean out-of-sample excess of
−0.16 percentage points. The train-to-test rank correlation of 0.387 says the
ordering of concepts carries some signal — better-performing concepts do tend to
rank higher next year — but the level does not survive: in-sample excess of
+0.65% becomes −0.16% out of sample, a shrinkage of more than 100%.

The failure is concentrated. Folds 1–7 (test years 2013–2019) average +0.17%; the
four folds testing 2020–2023 average −1.03%, with train-to-test rank correlations
turning negative. The in-sample excess in those folds' training windows is also
anomalously high (+1.6% to +2.4% versus +0.3% elsewhere), consistent with the
2020–2021 volatility regime inflating in-sample fit and then reversing.

## 5.4 Costs, sectors, regimes and parameter sensitivity

**Costs.** The distinction between gross and excess break-even is decisive.

**Table 5.** Break-even round-trip cost, two measures (h = 10).

| Measure | Concepts clearing 11 bp | Concepts clearing 26 bp |
|---|---:|---:|
| Against gross mean return | 22 / 44 | 22 / 44 |
| **Against excess over matched null** | **4 / 44** | **1 / 44** |

A concept with a gross mean of 82 bp looks comfortably tradeable. But random
entry on the same tickers earns 70 bp of that; the part attributable to the
signal is 12 bp, which sits inside the modelled 11–26 bp cost band. On the
decision-relevant measure only `ict_sweep_sellside_bullish` clears the upper
bound, and only four concepts clear the lower one. This is the study's central
economic finding: **the returns are real, but they are not attributable to the
signals, and the part that is does not reliably cover the cost of trading.**

**Sectors.** Compared against a direction-matched null, only Energy shows a
positive excess (+0.011 pp); the remaining eleven sectors range from −0.077 to
−0.213 pp. We note that the comparison used in the prior version — a mixed
long/short signal population against a long-only benchmark — measures net
directional exposure rather than signal quality, and produced a uniform −0.5 to
−1.2 pp across every sector, an artefact of that mismatch rather than a finding.

**Regimes.** Two of nine trend × volatility buckets show a positive excess:
bear/low-volatility (+0.24 pp, n = 7,739) and sideways/low-volatility (+0.10 pp,
n = 13,552). The worst is bear/high-volatility (−0.51 pp, n = 144,311). The
positive buckets are the two smallest, and we do not treat them as evidence.

**Parameter sensitivity.** Results at the default parameters are not
privileged. Two sweeps are reported. A broad grid over the order-block swing
lookback and the market-structure pivot length moves 18 of the 44 concepts; the
other 26 do not read those parameters at all, so their zero variance there means
*untested*, not *robust* — `responds_to_sweep` in
`results/sensitivity_stability.csv` marks the distinction.

Because that grid does not touch the parameters governing the three concepts we
reformulated, a second, targeted sweep varies exactly those: the sweep
penetration threshold *X* ∈ {0.10, 0.25, 0.50, 1.00} ATR, the confirmation
window *Z* ∈ {1, 3, 6} bars, and the gap materiality threshold ∈ {0.05, 0.10,
0.25} ATR — 36 configurations. This is the direct test of whether our
specification choices drive the positive result.

**Table 6.** Targeted sweep over the reformulated concepts' own parameters
(36 configurations).

| Signal | Mean excess | Range (bp) | Configs with positive excess |
|---|---:|---:|---:|
| `ict_sweep_sellside_bullish` | +18.5 bp | 29.4 | **33 / 36** |
| `ict_sweep_buyside_bearish` | +8.4 bp | 28.7 | **36 / 36** |
| `ict_nwog_gap_up` | +0.5 bp | 4.2 | 24 / 36 |
| `ict_nwog_gap_down` | −4.7 bp | 2.6 | 0 / 36 |

The two sweep detectors survive. `ict_sweep_buyside_bearish` is positive in
every configuration tested, and `ict_sweep_sellside_bullish` in all but the
three using an extreme *X* = 1.00 ATR penetration threshold, which admits too
few events to estimate. Notably the default *X* = 0.25 is not the most
favourable setting: at *X* = 0.10 the sell-side excess is 24 bp against 20 bp at
the default, so the chosen value is conservative rather than cherry-picked.

**The gap detector does not survive**, and its failure mode is instructive: its
sign is determined by the materiality threshold we chose. Mean excess is +2.6 bp
at 0.05 ATR, **+0.4 bp at our default of 0.10**, and −1.6 bp at 0.25 ATR. The
default sits almost exactly at the sign change. We therefore withdraw
`ict_nwog_gap_up` as evidence of an edge: it clears the significance bar at one
parameter value and would not at a neighbouring one, which is the definition of
a result that has not been established. That leaves **two** concepts — both
liquidity sweeps — with an edge that is robust to its own parameterisation.

# 6. What three ordinary errors did to the same data

An earlier version of this pipeline concluded that 28 of 42 concepts were
"significant versus a random-entry baseline". Every defect below is ordinary, and
each independently converts a null result into an apparently positive one. We
report them because the failure modes are more transferable than our estimates.

## 6.1 Look-ahead through an outcome label

`ict_fvg_bullish_filled` and `ict_fvg_bearish_filled` recorded whether a fair
value gap was later filled, and stamped the answer **on the formation bar**. The
event-melting step selected every boolean column as a tradeable signal, so both
became entry signals whose value depended on up to 60 subsequent bars. They
contributed 187,719 trades (4.3% of all events) and occupied both extremes of the
concept ranking; `ict_fvg_bearish_filled` had the single most negative effect size
in the study.

The mechanism worth noting is not the leak itself but its route: the selection
rule was fail-open. Any new boolean column became tradeable by default, guarded
only by a hand-maintained deny-list. The corrected pipeline requires explicit
registration with a declared direction and raises on anything unregistered.

## 6.2 A two-sided test behind a directional claim

The significance flag came from a two-sided Welch test. A concept whose mean
return was significantly *worse* than random entry set the flag exactly as one
that was better. Of the 28 concepts flagged, **27 had a negative effect size**:
they lost to random entry, and were then listed in the report under the heading
"Signals that beat the random-entry baseline", including entries with Sharpe
−0.199 and mean return −0.39%.

## 6.3 An irreproducible benchmark

The random-entry baseline seeded its generator from `hash()` applied to a string.
Python salts string hashing per process, so every run drew a different baseline.
Running the original function in three separate interpreters produces three
disjoint entry sets. Since that baseline is the comparator behind every
significance flag, the published counts could not be reproduced by rerunning the
pipeline — a failure that no test caught because no test compared two runs.

## 6.4 Two further distortions

`ict_ndog_formed` was true whenever the open and prior close were both non-null —
i.e. on essentially every bar — contributing 1,946,675 events, 44.8% of the
entire event population, and dominating every pooled aggregate. Separately,
`ict_bpr_bullish` and `ict_bpr_bearish` were computed from a condition that
reduces to `upper < lower`, unsatisfiable by construction; both were false
everywhere, and the melting step drops all-false columns silently, so two
concepts vanished from the study with no error. The "42 concepts tested" headline
was 42 of 44 declared detectors.

## 6.5 The joint effect

These are not exotic mistakes. A fail-open column selector, a default-argument
two-sided test, a salted hash, an unguarded boolean, and a silently-dropped
column are each a single line. Together they moved the study's conclusion from "5
of 44 concepts show a small edge that costs mostly consume" to "28 of 42 concepts
beat random entry". We suggest that the mechanical checks in Section 4.1 —
truncation invariance, an index-position audit, a fail-closed registry, and a
pinned seed derivation — are cheap enough to be worth adopting as routine in
backtest code.

# 7. Discussion

**What the evidence supports.** On daily bars, for large-cap US equities, over
2010–2026, these implementations of SMC/ICT do not carry economically meaningful
predictive information. Thirty-nine of 44 concepts are statistically
indistinguishable from entering the same names the same number of times on random
dates. The five that are distinguishable have excess returns of 5–33 bp per
ten-day trade, do not carry that edge out of sample, and — with one exception —
do not clear a realistic cost band.

**What it does not support.** It does not show that SMC/ICT is worthless as
taught. Three limits matter. These are two specific implementations, not the
methodology as a discretionary practice: a human applying these concepts uses
context, confluence and discretion that a mechanical detector does not capture.
The daily-bar restriction is severe, since SMC/ICT is most often taught on
intraday FX and futures, where the microstructure the framework appeals to — stop
runs, liquidity pools — is far more plausible. And a null result is a statement
about power as much as about truth: our confidence intervals on Cohen's *d* are
roughly ±0.015 at the largest sample sizes, so we can exclude effects larger than
about *d* = 0.15, but not small ones.

**On the three reformulated concepts.** These clear the bar only in the
corrected, prospective forms we wrote, which is the weakest part of our positive
result, so we tested it directly. The two liquidity-sweep detectors are positive
across essentially the whole parameter space we swept (36/36 and 33/36
configurations), and the default *X* = 0.25 ATR is not the most favourable
setting available — the result is not an artefact of our choice. The gap
detector is: its sign turns over between 0.05 and 0.25 ATR with our default
sitting at the crossing, so we withdraw it. A reader should treat the two
surviving sweep results as the only positive findings in this paper, and even
those as small: 8–19 basis points, inside or barely above the modelled cost
band.

**Interpretation.** That gross returns are large (65–82 bp) while excess returns
are small (4–12 bp) is the cleanest summary. These detectors do fire, and
positions opened on them do make money over 2010–2026. Nearly all of that is
compensation for being long a rising market, which random entry captures equally
well. The framework's error is not that it identifies nothing; it is that it
takes credit for market drift.

# 8. Limitations

1. **Survivorship bias.** The universe is a 2026 snapshot applied to 2010–2026.
   This inflates return levels for signals and benchmarks alike and largely
   cancels in the matched comparison, but a point-in-time constituent history
   would be strictly better and is not available to this pipeline.
2. **Daily bars only.** Kill zones and all intraday structure are out of scope.
3. **Symmetric short mechanics.** Short signals are the negation of the forward
   return, with no borrow cost or availability constraint.
4. **No economic mechanism.** This is an evaluation of indicator logic, not a
   theory paper; we propose no risk-based or behavioural model for why these
   patterns would or would not predict returns.
5. **Path-dependent metrics are descriptive.** Sharpe, Calmar and maximum
   drawdown are computed over an overlapping, cross-sectional trade sequence that
   is not an attainable account equity curve. Inference uses the calendar-time
   estimator instead.
6. **Single market, single period.** No other asset class, market or timeframe is
   tested.
7. **Sector results are descriptive.** Several sectors rest on fewer than 25
   tickers; we report counts alongside every sector figure and do not treat
   sector differences as tested hypotheses.

# 9. Conclusion

We formalise 44 SMC/ICT detectors, test them on 496 S&P 500 constituents over
2010–2026, and find that 39 are statistically indistinguishable from
composition-matched random entry. The five that are distinguishable carry excess
returns of 5–33 basis points per ten-day trade, fail to carry that edge into a
13-fold walk-forward evaluation, and — with one exception — do not clear a
modelled 11–26 basis-point cost band once the excess rather than the gross return
is measured against it. A targeted parameter sweep further reduces the five to
**two** — both liquidity sweeps — whose edge survives variation in the
parameters we ourselves chose.

The methodological result may be the more useful one. On identical data, a
zero-return null admits 39 of 44 concepts and a composition-matched null admits
5; iid standard errors understate uncertainty by a median factor of 5.8; and a
two-sided test presented as a directional claim reversed the sign of the finding
for 27 of 28 concepts in the prior version of this analysis. Benchmark choice,
dependence structure and test direction are not technicalities in this setting —
each is capable of determining the sign of the reported conclusion.

Code, data-preparation instructions, machine-readable concept specifications, the
full statistics table and a replication package are available in the repository.

# References

Bailey, D. H., and López de Prado, M. (2014). The deflated Sharpe ratio:
correcting for selection bias, backtest overfitting, and non-normality. *Journal
of Portfolio Management*, 40(5), 94–107.

Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a
practical and powerful approach to multiple testing. *Journal of the Royal
Statistical Society, Series B*, 57(1), 289–300.

Fama, E. F. (1998). Market efficiency, long-term returns, and behavioral finance.
*Journal of Financial Economics*, 49(3), 283–306.

Fisher, R. A. (1935). *The Design of Experiments*. Oliver and Boyd.

Harvey, C. R., Liu, Y., and Zhu, H. (2016). ...and the cross-section of expected
returns. *Review of Financial Studies*, 29(1), 5–68.

Lo, A. W., Mamaysky, H., and Wang, J. (2000). Foundations of technical analysis:
computational algorithms, statistical inference, and empirical implementation.
*Journal of Finance*, 55(4), 1705–1765.

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
| 1 | `results/figures/fig1_concept_forest.png` | Concept effect sizes with 95% bootstrap confidence intervals, all 44 concepts at h = 10 |
| 2 | `results/figures/fig2_sector_heatmap.png` | Excess return over the direction-matched null, by sector |
| 3 | `results/figures/fig3_trade_timelines.png` | Annotated price series for a positive, a null and a negative concept |
| 4 | `results/figures/fig4_sensitivity_heatmap.png` | Mean excess return across the parameter grid |
| 5 | `results/figures/fig5_walkforward.png` | In-sample versus out-of-sample excess by fold, and train→test rank correlation |
| 6 | `results/figures/fig6_breakeven_costs.png` | Break-even round-trip cost on the excess over the matched null, against the modelled cost band |

Each figure is accompanied by a CSV of its underlying values, so every plotted
number can be checked rather than measured off the image.

# Appendix B. Detector pseudocode

Full machine-readable specifications are in `docs/specs/*.yaml`. Three
representative detectors follow.

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

**B.3 Composition-matched randomization test**

```
for each ticker t in the concept's trades:
    n_t ← trades on t;  N_t, μ_t, σ²_t ← pool of all h-day forward returns on t
    fpc ← (N_t − n_t)/(N_t − 1)
    accumulate:  mean_num += n_t·d·μ_t ;  var_num += n_t·σ²_t·fpc
null_mean ← mean_num / N ;  null_se ← sqrt(var_num) / N
z ← (observed_mean − null_mean) / null_se ;  p ← 1 − Φ(z)      # one-sided
```

# Appendix C. Complete results

| Table | File |
|---|---|
| All 352 (concept × horizon) hypotheses with every metric, p-value, FDR-adjusted p-value, effect size and confidence interval | `results/statistics_master.csv` |
| Human-readable per-concept summary at every horizon | `results/master_summary.md` |
| Pipeline validation, data quality, and regression against the prior version | `results/validation_report.md` |
| Adversarial pre-read of likely referee objections | `results/reviewer_report.md` |
| Walk-forward, per fold and per concept | `results/walkforward_{summary,detail}.csv` |
| Break-even and net-of-cost tables | `results/breakeven_costs.csv`, `results/net_of_cost_rankings.csv` |
| Monte Carlo | `results/monte_carlo.csv` |
| Sector and regime breakdowns | `results/sector_analysis.csv`, `results/regime_analysis.csv` |
| Parameter sweeps (broad) | `results/sensitivity_{grid,random,stability}.csv` |
| Parameter sweep (targeted at the reformulated concepts) | `results/sensitivity_targeted_{grid,stability}.csv` |
| Every code, data and parameter change from the prior version, with rationale | `CHANGES.md` |

Reproduction: `./run_full_pipeline.sh` (see `docs/replication_guide.md`).
