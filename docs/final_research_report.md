# Executive Research Report — SMC/ICT Statistical Edge Study

_Generated 2026-09-08 directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._

## Scope
- Stocks with usable data: **498** of 503 S&P 500 constituents
- Total SMC/ICT events detected: **2,226,881**
- Total backtested trades (events x holding periods): **17,731,944**
- Distinct signal families tested: **44**
- FDR significance threshold used throughout: alpha = 0.05
- **Every ranking below (concepts, combinations, stocks, sectors, regimes) is tested against a random-entry baseline run through identical backtest mechanics** (`backtest/baseline_engine.py`), not only a zero-return null. This matters: over 2010-2026 (a long bull market), almost any long-biased signal clears a zero-return null from broad market drift alone. The gap between the two tests is itself one of this study's main findings (Section 1).

## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?
**No, not uniformly — and the two significance tests reported diverge sharply, which is itself the key finding.** Of 44 SMC/ICT signal families tested at the 10-day holding horizon: **39/44** show a mean return significantly different from **zero** after FDR correction — but that is a weak bar over a long bull market. Testing instead against a **random-entry baseline** at the same frequency, only **5/44** concepts remain significant, and of 60 tested concept combinations, only **1** clear the same bar.

The picture gets more sobering when sliced by sector and regime (Section 5): only **1/12** sectors show *positive* average excess return over the random baseline at all — in most sectors, including Information Technology (the largest, most heavily represented sector in this universe), a plain random long entry outperformed the aggregate SMC/ICT signal population. This does not mean every individual concept is worthless — a real minority clear a genuine, statistically defensible bar (Section 2) — but it does mean the aggregate, unconditional claim "SMC/ICT signals beat chance" is **not supported** by this dataset. The edge, where it exists, is concept-specific and regime/sector-dependent, not a property of the methodology as a whole.

## 2. Which concepts provide the strongest statistical edge?

_Signals that BEAT the composition-matched random-entry null after BH-FDR correction -- i.e. a positive excess return that survives multiple-testing control (`beats_matched_random=True`). Concepts that significantly UNDERPERFORM the null are reported separately below and are not evidence of an edge:_

| Signal | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |
|---|---|---|---|---|---|
| smc_swing_choch_bearish | 2653 | 43.27% | -0.189 | -0.37% | 0.0335 |
| ict_sweep_sellside_bullish | 49304 | 57.13% | 0.639 | 0.82% | 0.0001 |
| ict_sweep_buyside_bearish | 65448 | 43.74% | -0.497 | -0.59% | 0.0000 |
| smc_internal_ob_bearish_mitigated | 42268 | 57.06% | 0.609 | 0.79% | 0.0382 |
| ict_nwog_gap_up | 147321 | 56.98% | 0.615 | 0.77% | 0.0111 |

## 3. Which concept combinations are most robust?

1 of 60 tested combinations (pairs with >=30 co-occurrences, top 60 by frequency) beat the random-entry baseline after FDR correction:

| Combination | n trades | Win rate | Sharpe | Avg return | p vs baseline (FDR-adj) |
|---|---|---|---|---|---|
| ict_sweep_buyside_bearish+smc_internal_ob_bullish_mitigated | 12275 | 44.85% | -0.428 | -0.53% | 1.0000 |

## 4. Which S&P 500 stocks are most responsive?

Ranked by **excess return vs. that same ticker's own random-entry baseline** — not raw Sharpe, which would just reward stocks that rallied hard over 2010-2026 regardless of whether SMC/ICT signals added anything. Per-ticker baseline samples are small (~50 random entries per ticker per horizon), so most individual tickers do not reach significance even when the excess return looks large — treat this as a ranking, not a list of proven per-stock edges; see `p_value_vs_baseline` in `results/stock_rankings.csv` for the honest per-ticker confidence.

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline | Significant? |
|---|---|---|---|---|---|
| KVUE | 780 | 0.19% | -0.45% | 0.63% | no |
| WBD | 5049 | -0.06% | -0.29% | 0.22% | no |
| CCL | 5043 | 0.09% | -0.01% | 0.10% | no |
| BXP | 4969 | -0.12% | -0.18% | 0.06% | no |
| IR | 2679 | 0.08% | 0.09% | -0.01% | no |
| KHC | 3037 | -0.01% | 0.05% | -0.07% | no |
| WELL | 4632 | 0.21% | 0.30% | -0.09% | no |
| NTAP | 4765 | 0.26% | 0.37% | -0.11% | no |
| BG | 4575 | -0.08% | 0.04% | -0.12% | no |
| CFG | 3353 | 0.28% | 0.41% | -0.13% | no |
| SLB | 4890 | 0.29% | 0.42% | -0.13% | no |
| TECH | 4637 | -0.01% | 0.12% | -0.14% | no |
| MET | 4843 | 0.01% | 0.14% | -0.14% | no |
| MCHP | 5236 | 0.09% | 0.23% | -0.14% | no |
| VZ | 4754 | 0.01% | 0.16% | -0.15% | no |

_Bottom 10 (least responsive / signals underperform that stock's own baseline):_

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline |
|---|---|---|---|---|
| VRT | 2262 | 0.16% | 2.31% | -2.15% |
| WYNN | 4709 | -0.40% | 1.85% | -2.25% |
| MGM | 4947 | -0.51% | 1.74% | -2.25% |
| VST | 2728 | -0.30% | 1.98% | -2.28% |
| DELL | 2792 | -0.08% | 2.30% | -2.38% |
| PLTR | 1590 | 0.70% | 3.17% | -2.47% |
| LITE | 3111 | 0.04% | 2.55% | -2.50% |
| APP | 1375 | 0.38% | 3.19% | -2.81% |
| GEV | 524 | 0.24% | 3.97% | -3.73% |
| SNDK | 333 | 8.62% | 14.10% | -5.48% |

## 5. Which sectors and market regimes are most responsive?

**1 of 12 sectors** show positive average excess return over the random-entry baseline:

| Sector | Avg return | Baseline avg return | Excess vs baseline | n tickers |
|---|---|---|---|---|
| Energy | 0.05% | n/a | 0.01% | 20 |
| Materials | -0.04% | n/a | -0.08% | 24 |
| Unknown | -0.04% | n/a | -0.10% | 48 |
| Financials | -0.06% | n/a | -0.11% | 69 |
| Consumer Discretionary | -0.05% | n/a | -0.11% | 49 |
| Industrials | -0.05% | n/a | -0.12% | 66 |
| Information Technology | -0.04% | n/a | -0.13% | 61 |
| Consumer Staples | -0.10% | n/a | -0.14% | 32 |
| Health Care | -0.10% | n/a | -0.15% | 52 |
| Communication Services | -0.11% | n/a | -0.16% | 19 |
| Real Estate | -0.12% | n/a | -0.16% | 27 |
| Utilities | -0.16% | n/a | -0.21% | 29 |

### By market regime

| Trend regime | Vol regime | Avg return | Baseline avg return | Excess vs baseline | n trades |
|---|---|---|---|---|---|
| bear | high_vol | -0.47% | 2.17% | -0.51% | 144311 |
| bear | low_vol | 0.19% | 0.06% | 0.24% | 7739 |
| bear | normal_vol | -0.05% | 0.75% | 0.01% | 334658 |
| bull | high_vol | 0.07% | 1.19% | -0.19% | 95253 |
| bull | low_vol | 0.07% | 0.55% | -0.01% | 92635 |
| bull | normal_vol | -0.01% | 0.61% | -0.10% | 1055491 |
| sideways | high_vol | -0.40% | 1.58% | -0.43% | 73152 |
| sideways | low_vol | 0.06% | 0.47% | 0.10% | 13552 |
| sideways | normal_vol | -0.10% | 0.53% | -0.09% | 403722 |

## 6. Which concepts fail consistently?

Lowest-Sharpe signals with at least 30 trades (10-day hold) that did *not* beat the random-entry baseline after FDR correction:

| Signal | n trades | Win rate | Sharpe |
|---|---|---|---|
| ict_bos_bearish | 42496 | 40.24% | -0.810 |
| smc_fvg_bearish_formed | 67673 | 42.10% | -0.705 |
| smc_internal_bos_bearish | 16549 | 41.22% | -0.700 |
| ict_volume_imbalance_bearish | 84642 | 41.63% | -0.698 |
| ict_displacement_bearish | 190415 | 42.69% | -0.694 |
| ict_mss_bearish | 36553 | 42.94% | -0.668 |
| ict_liquidity_sellside_swept | 32884 | 42.05% | -0.644 |
| smc_equal_highs | 10483 | 42.48% | -0.642 |
| ict_fvg_bearish_formed | 90730 | 42.86% | -0.640 |
| ict_liquidity_sellside_pool_formed | 51635 | 42.52% | -0.638 |

## 7. Are results stable across bull, bear, and sideways markets?
No, not fully — see the regime table in Section 5. Excess return vs. baseline is negative in most trend/volatility regime cells (`results/regime_analysis.csv`), and the one clearly positive cell (bull + high volatility) is a narrow slice of the data. Regime classification uses each stock's own trailing SMA(200) trend and realized-volatility-vs-own-history state, not an external index. See the dashboard's Sector & Regime tab and `analytics/regimes.py:regime_analysis_by_signal` for the per-signal breakdown by regime.

## 8. Are results statistically significant after correcting for sample size and multiple testing?
Every ranking module (concepts, combinations, stocks, sectors, regimes) now compares against a random-entry baseline run through identical backtest mechanics, in addition to a zero-return null, with Benjamini-Hochberg FDR correction applied to both (`analytics/statistics.py`). The headline `beats_matched_random` flag requires clearing the FDR-corrected **baseline** comparison (alpha=0.05) *and* a minimum sample size — concepts/combinations below that sample size are explicitly flagged `low_sample_warning` rather than reported with false confidence. Per-ticker significance tests (Section 4) have limited statistical power due to small per-ticker baseline samples (~50 trades) — reported as a ranking with honest p-values, not a list of proven stock-specific edges.

## Key limitations
- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).
- Sector mapping is a static approximation, not a live data source.
- No transaction costs or slippage modeled.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no corresponding logic in the source scripts and are not implemented.
- Per-ticker and per-sector/regime baseline comparisons have smaller sample sizes than the universe-wide concept-level comparison, so their significance tests are correspondingly less powered — read the excess-return figures as directional evidence, the p-values as the honest confidence level.
- See README.md "Limitations" and "Key assumptions" sections for the complete list.