# Executive Research Report — SMC/ICT Statistical Edge Study

_Generated 2026-07-14 directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._

## Scope
- Stocks with usable data: **501** of 503 S&P 500 constituents
- Total SMC/ICT events detected: **4,348,698**
- Total backtested trades (events x holding periods): **34,632,327**
- Distinct signal families tested: **42**
- FDR significance threshold used throughout: alpha = 0.05
- **Every ranking below (concepts, combinations, stocks, sectors, regimes) is tested against a random-entry baseline run through identical backtest mechanics** (`backtest/baseline_engine.py`), not only a zero-return null. This matters: over 2010-2026 (a long bull market), almost any long-biased signal clears a zero-return null from broad market drift alone. The gap between the two tests is itself one of this study's main findings (Section 1).

## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?
**No, not uniformly — and the two significance tests reported diverge sharply, which is itself the key finding.** Of 42 SMC/ICT signal families tested at the 10-day holding horizon: **42/42** show a mean return significantly different from **zero** after FDR correction — but that is a weak bar over a long bull market. Testing instead against a **random-entry baseline** at the same frequency, only **28/42** concepts remain significant, and of 60 tested concept combinations, only **44** clear the same bar.

The picture gets more sobering when sliced by sector and regime (Section 5): only **2/12** sectors show *positive* average excess return over the random baseline at all — in most sectors, including Information Technology (the largest, most heavily represented sector in this universe), a plain random long entry outperformed the aggregate SMC/ICT signal population. This does not mean every individual concept is worthless — a real minority clear a genuine, statistically defensible bar (Section 2) — but it does mean the aggregate, unconditional claim "SMC/ICT signals beat chance" is **not supported** by this dataset. The edge, where it exists, is concept-specific and regime/sector-dependent, not a property of the methodology as a whole.

## 2. Which concepts provide the strongest statistical edge?

_Signals that beat the random-entry baseline after FDR correction (`significant_vs_baseline=True`):_

| Signal | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |
|---|---|---|---|---|---|
| ict_ob_bullish_mitigated | 20676 | 58.01% | 0.539 | 0.94% | 0.0008 |
| ict_ob_bullish_formed | 32750 | 56.39% | 0.487 | 0.55% | 0.0088 |
| ict_fvg_bullish_formed | 112764 | 55.91% | 0.478 | 0.56% | 0.0075 |
| ict_displacement_bullish | 213796 | 56.04% | 0.473 | 0.57% | 0.0066 |
| smc_internal_ob_bullish_formed | 58717 | 55.76% | 0.452 | 0.51% | 0.0004 |
| ict_volume_imbalance_bullish | 118438 | 55.42% | 0.421 | 0.49% | 0.0000 |
| ict_bos_bullish | 81274 | 55.14% | 0.393 | 0.43% | 0.0000 |
| smc_internal_bos_bullish | 32142 | 54.93% | 0.384 | 0.42% | 0.0000 |
| ict_fvg_bullish_filled | 101087 | 51.09% | -0.093 | -0.10% | 0.0000 |
| smc_swing_choch_bearish | 2674 | 43.27% | -0.199 | -0.39% | 0.0000 |

## 3. Which concept combinations are most robust?

44 of 60 tested combinations (pairs with >=30 co-occurrences, top 60 by frequency) beat the random-entry baseline after FDR correction:

| Combination | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |
|---|---|---|---|---|---|
| ict_ob_bullish_formed+smc_internal_ob_bullish_formed | 23490 | 56.22% | 0.474 | 0.53% | 0.0064 |
| ict_ob_bullish_formed+smc_internal_bos_bullish | 12623 | 55.64% | 0.454 | 0.49% | 0.0022 |
| ict_displacement_bullish+smc_internal_ob_bullish_formed | 25573 | 55.58% | 0.440 | 0.50% | 0.0008 |
| ict_bos_bullish+ict_displacement_bullish | 34179 | 55.68% | 0.436 | 0.48% | 0.0001 |
| ict_bos_bullish+ict_liquidity_buyside_swept | 8890 | 55.76% | 0.416 | 0.46% | 0.0017 |
| ict_fvg_bullish_formed+ict_volume_imbalance_bullish | 20053 | 55.33% | 0.402 | 0.46% | 0.0001 |
| ict_displacement_bullish+smc_internal_bos_bullish | 13816 | 54.81% | 0.401 | 0.44% | 0.0001 |
| ict_fvg_bullish_formed+smc_internal_ob_bullish_formed | 8953 | 55.69% | 0.390 | 0.45% | 0.0024 |
| smc_internal_bos_bullish+smc_internal_ob_bullish_formed | 32142 | 54.93% | 0.384 | 0.42% | 0.0000 |
| ict_bos_bullish+ict_ob_bullish_formed | 12310 | 55.22% | 0.375 | 0.42% | 0.0000 |

## 4. Which S&P 500 stocks are most responsive?

Ranked by **excess return vs. that same ticker's own random-entry baseline** — not raw Sharpe, which would just reward stocks that rallied hard over 2010-2026 regardless of whether SMC/ICT signals added anything. Per-ticker baseline samples are small (~50 random entries per ticker per horizon), so most individual tickers do not reach significance even when the excess return looks large — treat this as a ranking, not a list of proven per-stock edges; see `p_value_vs_baseline` in `results/stock_rankings.csv` for the honest per-ticker confidence.

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline | Significant? |
|---|---|---|---|---|---|
| VRT | 4370 | 1.33% | -2.21% | 3.54% | no |
| LVS | 9253 | 0.22% | -1.64% | 1.86% | no |
| MRNA | 4039 | 1.26% | -0.58% | 1.85% | no |
| HAL | 9312 | 0.40% | -1.23% | 1.63% | no |
| DOW | 4016 | 0.21% | -1.24% | 1.45% | no |
| CMI | 9169 | 0.41% | -0.97% | 1.38% | no |
| WDAY | 7652 | 0.19% | -1.14% | 1.33% | no |
| VLO | 9224 | 0.69% | -0.57% | 1.26% | no |
| SLB | 9327 | 0.26% | -0.86% | 1.12% | no |
| FCX | 9206 | 0.58% | -0.54% | 1.12% | no |
| LULU | 9265 | 0.42% | -0.67% | 1.10% | no |
| TRGP | 8541 | 1.03% | -0.01% | 1.04% | no |
| AKAM | 9230 | 0.17% | -0.86% | 1.03% | no |
| CAT | 9319 | 0.57% | -0.44% | 1.01% | no |
| EXPD | 9278 | 0.15% | -0.86% | 1.01% | no |

_Bottom 10 (least responsive / signals underperform that stock's own baseline):_

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline |
|---|---|---|---|---|
| FSLR | 9205 | 0.23% | 2.51% | -2.28% |
| TTD | 5304 | 0.65% | 3.00% | -2.35% |
| HWM | 5283 | 0.86% | 3.22% | -2.36% |
| NFLX | 9008 | 0.91% | 3.39% | -2.48% |
| BLDR | 8962 | 0.87% | 3.46% | -2.59% |
| FANG | 7610 | 0.55% | 3.15% | -2.60% |
| CRWD | 3883 | 1.21% | 3.98% | -2.77% |
| COIN | 2982 | 0.39% | 3.18% | -2.79% |
| LITE | 6077 | 1.05% | 4.13% | -3.07% |
| TSLA | 9237 | 1.36% | 4.68% | -3.33% |

## 5. Which sectors and market regimes are most responsive?

**2 of 12 sectors** show positive average excess return over the random-entry baseline:

| Sector | Avg return | Baseline avg return | Excess vs baseline | n tickers |
|---|---|---|---|---|
| Energy | 0.34% | 0.08% | 0.26% | 20 |
| Materials | 0.28% | 0.20% | 0.08% | 24 |
| Consumer Staples | 0.21% | 0.35% | -0.14% | 32 |
| Industrials | 0.37% | 0.55% | -0.18% | 65 |
| Financials | 0.31% | 0.63% | -0.32% | 69 |
| Utilities | 0.20% | 0.56% | -0.35% | 29 |
| Consumer Discretionary | 0.40% | 0.75% | -0.35% | 49 |
| Health Care | 0.29% | 0.68% | -0.39% | 53 |
| Communication Services | 0.28% | 0.75% | -0.48% | 20 |
| Real Estate | 0.20% | 0.70% | -0.50% | 30 |
| Unknown | 0.36% | 0.86% | -0.50% | 48 |
| Information Technology | 0.53% | 1.31% | -0.79% | 60 |

### By market regime

| Trend regime | Vol regime | Avg return | Baseline avg return | Excess vs baseline | n trades |
|---|---|---|---|---|---|
| bear | high_vol | 0.77% | 1.31% | -0.54% | 268722 |
| bear | low_vol | 0.23% | 1.51% | -1.27% | 15662 |
| bear | normal_vol | 0.31% | 0.91% | -0.61% | 643111 |
| bull | high_vol | 0.64% | 0.56% | 0.08% | 180610 |
| bull | low_vol | 0.31% | 0.65% | -0.34% | 198660 |
| bull | normal_vol | 0.29% | 0.49% | -0.20% | 2109184 |
| sideways | high_vol | 0.62% | 1.94% | -1.32% | 130204 |
| sideways | low_vol | 0.26% | 0.74% | -0.48% | 27140 |
| sideways | normal_vol | 0.20% | 0.74% | -0.54% | 763918 |

## 6. Which concepts fail consistently?

Lowest-Sharpe signals with at least 30 trades (10-day hold) that did *not* beat the random-entry baseline after FDR correction:

| Signal | n trades | Win rate | Sharpe |
|---|---|---|---|
| smc_fvg_bullish_formed | 68299 | 55.58% | 0.496 |
| smc_swing_ob_bullish_mitigated | 6820 | 56.94% | 0.498 |
| smc_equal_lows | 9388 | 55.14% | 0.508 |
| smc_internal_choch_bullish | 26575 | 56.76% | 0.527 |
| smc_internal_ob_bullish_mitigated | 54395 | 56.41% | 0.547 |
| ict_mss_bullish | 36729 | 56.60% | 0.549 |
| ict_liquidity_buyside_swept | 44563 | 57.02% | 0.574 |
| ict_ndog_formed | 1941685 | 56.55% | 0.584 |
| smc_swing_bos_bullish | 4598 | 56.87% | 0.607 |
| ict_nwog_formed | 421965 | 56.98% | 0.614 |

## 7. Are results stable across bull, bear, and sideways markets?
No, not fully — see the regime table in Section 5. Excess return vs. baseline is negative in most trend/volatility regime cells (`results/regime_analysis.csv`), and the one clearly positive cell (bull + high volatility) is a narrow slice of the data. Regime classification uses each stock's own trailing SMA(200) trend and realized-volatility-vs-own-history state, not an external index. See the dashboard's Sector & Regime tab and `analytics/regimes.py:regime_analysis_by_signal` for the per-signal breakdown by regime.

## 8. Are results statistically significant after correcting for sample size and multiple testing?
Every ranking module (concepts, combinations, stocks, sectors, regimes) now compares against a random-entry baseline run through identical backtest mechanics, in addition to a zero-return null, with Benjamini-Hochberg FDR correction applied to both (`analytics/statistics.py`). The headline `statistically_significant` flag requires clearing the FDR-corrected **baseline** comparison (alpha=0.05) *and* a minimum sample size — concepts/combinations below that sample size are explicitly flagged `low_sample_warning` rather than reported with false confidence. Per-ticker significance tests (Section 4) have limited statistical power due to small per-ticker baseline samples (~50 trades) — reported as a ranking with honest p-values, not a list of proven stock-specific edges.

## Key limitations
- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).
- Sector mapping is a static approximation, not a live data source.
- No transaction costs or slippage modeled.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no corresponding logic in the source scripts and are not implemented.
- Per-ticker and per-sector/regime baseline comparisons have smaller sample sizes than the universe-wide concept-level comparison, so their significance tests are correspondingly less powered — read the excess-return figures as directional evidence, the p-values as the honest confidence level.
- See README.md "Limitations" and "Key assumptions" sections for the complete list.