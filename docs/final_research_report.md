# Executive Research Report — SMC/ICT Statistical Edge Study

_Generated 2026-07-14 directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._

## Scope
- Stocks with usable data: **501** of 503 S&P 500 constituents
- Total SMC/ICT events detected: **4,348,698**
- Total backtested trades (events x holding periods): **34,632,327**
- Distinct signal families tested: **42**
- FDR significance threshold used throughout: alpha = 0.05

## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?
This is the central question, and the two significance tests reported diverge sharply — which is itself the key finding. Of 42 SMC/ICT signal families tested at the 10-day holding horizon: **42/42** show a mean return significantly different from **zero** after FDR correction (alpha=0.05) — but a zero-return null is a weak bar over 2010-2026, a long bull market, since almost any long-biased signal clears it from broad market drift alone. Testing instead against a **random-entry baseline** run through identical backtest mechanics at the same holding periods (`backtest/baseline_engine.py`), only **28/42** signals remain significant. That is the headline, more honest answer: roughly two-thirds of tested SMC/ICT signals show *some* edge beyond pure chance at the 10-day horizon, but a substantial minority of apparently-strong signals (including several of the highest-Sharpe ones) are statistically indistinguishable from a random long entry at the same frequency once compared properly.

## 2. Which concepts provide the strongest statistical edge?

_Ranked among signals that beat the random-entry baseline (`significant_vs_baseline`), not merely a zero return:_

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

| Combination | n trades | Win rate | Sharpe | Avg return |
|---|---|---|---|---|
| ict_liquidity_buyside_pool_formed+ict_liquidity_buyside_swept | 10282 | 57.86% | 0.672 | 0.76% |
| ict_ndog_formed+smc_equal_highs | 10547 | 57.31% | 0.635 | 0.74% |
| ict_ndog_formed+ict_nwog_formed | 421965 | 56.98% | 0.614 | 0.76% |
| ict_mss_bullish+ict_ob_bullish_formed | 8098 | 56.99% | 0.573 | 0.67% |
| ict_displacement_bullish+ict_liquidity_buyside_swept | 14547 | 57.26% | 0.569 | 0.63% |
| ict_liquidity_buyside_swept+smc_internal_ob_bullish_formed | 8534 | 56.89% | 0.555 | 0.61% |
| ict_mss_bullish+smc_internal_ob_bullish_formed | 16790 | 56.47% | 0.529 | 0.64% |
| ict_mss_bullish+smc_internal_choch_bullish | 12203 | 56.60% | 0.527 | 0.65% |
| smc_internal_choch_bullish+smc_internal_ob_bullish_formed | 26575 | 56.76% | 0.527 | 0.63% |
| ict_ndog_formed+smc_equal_lows | 9388 | 55.14% | 0.508 | 0.60% |

## 4. Which S&P 500 stocks are most responsive?

Top 20 by Sharpe (10-day hold, min 20 trades) — see `results/stock_rankings.csv` for the full ranked list.

| Ticker | n trades | Win rate | Sharpe |
|---|---|---|---|
| SNDK | 698 | 69.91% | 2.476 |
| GEV | 1111 | 60.04% | 1.467 |
| CVNA | 4987 | 55.16% | 0.735 |
| PLTR | 3136 | 53.60% | 0.681 |
| COST | 9159 | 56.68% | 0.651 |
| NVDA | 9368 | 54.73% | 0.644 |
| TPL | 9004 | 53.71% | 0.643 |
| AVGO | 9262 | 56.18% | 0.607 |
| VRT | 4370 | 56.27% | 0.604 |
| STX | 9195 | 54.74% | 0.594 |
| CEG | 2343 | 53.01% | 0.587 |
| DELL | 5492 | 56.94% | 0.582 |
| AAPL | 9300 | 57.29% | 0.578 |
| TSLA | 9237 | 52.05% | 0.571 |
| URI | 9178 | 55.96% | 0.571 |
| DPZ | 8897 | 55.02% | 0.571 |
| APP | 2795 | 55.10% | 0.538 |
| CRWD | 3883 | 55.29% | 0.532 |
| TRGP | 8541 | 56.43% | 0.527 |
| CTAS | 8999 | 56.37% | 0.524 |

## 5. Which sectors and market regimes are most responsive?

| Sector | Sharpe | Win rate | n tickers |
|---|---|---|---|
| Information Technology | 0.350 | 53.99% | 60 |
| Industrials | 0.326 | 54.13% | 65 |
| Financials | 0.272 | 53.90% | 69 |
| Unknown | 0.267 | 53.25% | 48 |
| Consumer Discretionary | 0.266 | 53.22% | 49 |

### By market regime

| Trend regime | Vol regime | Win rate | Avg return | n trades |
|---|---|---|---|---|
| bear | high_vol | 54.24% | 0.77% | 268722 |
| bear | low_vol | 51.82% | 0.23% | 15662 |
| bear | normal_vol | 52.94% | 0.31% | 643111 |
| bull | high_vol | 54.28% | 0.64% | 180610 |
| bull | low_vol | 54.14% | 0.31% | 198660 |
| bull | normal_vol | 53.73% | 0.29% | 2109184 |
| sideways | high_vol | 53.99% | 0.62% | 130204 |
| sideways | low_vol | 52.55% | 0.26% | 27140 |
| sideways | normal_vol | 52.45% | 0.20% | 763918 |

## 6. Which concepts fail consistently?

Lowest-Sharpe signals with at least 30 trades (10-day hold) that did *not* reach FDR-corrected significance:

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
See the regime table above and `results/regime_analysis.csv` / the dashboard's Sector & Regime tab for the full per-signal regime breakdown (`analytics/regimes.py:regime_analysis_by_signal`). Regime classification uses each stock's own trailing SMA(200) trend and realized-volatility-vs-own-history state, not an external index.

## 8. Are results statistically significant after correcting for sample size and multiple testing?
Every concept ranking reports a bootstrap confidence interval, a p-value against a zero-return null, a p-value against a random-entry baseline, and Benjamini-Hochberg FDR-adjusted versions of both (`analytics/statistics.py`). The headline `statistically_significant` flag requires clearing the FDR-corrected **baseline** comparison (alpha=0.05) *and* a minimum sample size of 30 trades — concepts below that sample size are explicitly flagged `low_sample_warning` rather than reported with false confidence. Combination rankings (Section 3) currently apply FDR correction only against the zero-return null, not yet the baseline — see README limitations.

## Key limitations
- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).
- Sector mapping is a static approximation, not a live data source.
- No transaction costs or slippage modeled.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no corresponding logic in the source scripts and are not implemented.
- See README.md "Limitations" and "Key assumptions" sections for the complete list.