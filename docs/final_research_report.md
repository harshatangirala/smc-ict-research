# Executive Research Report — SMC/ICT Statistical Edge Study

_Generated 2026-09-14 directly from `results/*` — every figure below is read from the pipeline's saved output, not hand-transcribed._

## Scope
- Stocks with usable data: **501** of 503 S&P 500 constituents
- Total SMC/ICT events detected: **4,326,101**
- Total backtested trades (events x holding periods): **34,452,258**
- Distinct signal families tested: **42**
- FDR significance threshold used throughout: alpha = 0.05
- **Every ranking below (concepts, combinations, stocks, sectors, regimes) is tested against a random-entry baseline run through identical backtest mechanics** (`backtest/baseline_engine.py`), not only a zero-return null. This matters: over 2010-2026 (a long bull market), almost any long-biased signal clears a zero-return null from broad market drift alone. The gap between the two tests is itself one of this study's main findings (Section 1).

## 1. Do SMC/ICT concepts outperform random entries and standard technical strategies?
**No — and not narrowly no.** Of 42 SMC/ICT signal families tested at the 10-day holding horizon: **42/42** show a mean return significantly different from **zero** after FDR correction — a weak bar over a long bull market that almost any long-biased signal clears from broad drift alone. Testing instead against a **random-entry baseline**, run through identical backtest mechanics with standard errors clustered by ticker (correcting for the fact that trades on the same stock share overlapping holding windows and are not independent draws), **35/42** concepts differ from the baseline at all after FDR correction — but of those, only **0** are significantly *better* than baseline. The other **35** are significantly *worse*. The same split holds for combinations: of 60 tested, **56** differ from baseline, and only **0** of those are significantly better (56 are significantly worse).

Sliced by sector (Section 5): **0/12** sectors show a positive point-estimate excess return over the random baseline, and of those, **0** are statistically significant after FDR correction. The aggregate, unconditional claim "SMC/ICT signals beat chance" is **not supported** by this dataset — and where the data does distinguish a signal from the baseline at all, it is more often in the *worse* direction than the better one. Where a genuine edge exists (Section 2), it is a narrow, specific exception, not the norm.

## 2. Which concepts provide the strongest statistical edge?

_Signals that beat the random-entry baseline after FDR correction and cluster-robust testing (`beats_baseline=True` — significant AND the excess return is positive):_

No concepts beat the baseline at the current sample/threshold.

_For comparison, the signals significantly **worse** than the baseline — a mean return that looks fine in isolation but underperforms doing nothing at the same frequency:_

| Signal | n trades | Avg return | Excess vs baseline | p vs baseline (FDR-adj) |
|---|---|---|---|---|
| ict_fvg_bearish_filled | 86287 | -1.42% | -2.26% | 0.0000 |
| ict_bos_bearish | 42780 | -1.20% | -2.04% | 0.0000 |
| smc_fvg_bearish_formed | 68062 | -1.09% | -1.93% | 0.0000 |
| smc_internal_bos_bearish | 16686 | -1.03% | -1.87% | 0.0000 |
| ict_volume_imbalance_bearish | 85075 | -0.94% | -1.77% | 0.0000 |
| ict_displacement_bearish | 191659 | -0.90% | -1.74% | 0.0000 |
| ict_mss_bearish | 36776 | -0.85% | -1.69% | 0.0000 |
| ict_fvg_bearish_formed | 91312 | -0.88% | -1.72% | 0.0000 |
| ict_liquidity_sellside_swept | 33142 | -0.88% | -1.72% | 0.0000 |
| ict_liquidity_sellside_pool_formed | 52038 | -0.82% | -1.66% | 0.0000 |

## 3. Which concept combinations are most robust?

0 of 60 tested combinations (pairs with >=30 co-occurrences, top 60 by frequency) beat the random-entry baseline after FDR correction (56 more are significantly worse):

No combinations beat the baseline at the current sample/threshold.

## 4. Which S&P 500 stocks are most responsive?

Ranked by **excess return vs. that same ticker's own random-entry baseline** — not raw Sharpe, which would just reward stocks that rallied hard over 2010-2026 regardless of whether SMC/ICT signals added anything. Per-ticker baseline samples are small (~50 random entries per ticker per horizon), so most individual tickers do not reach significance even when the excess return looks large — treat this as a ranking, not a list of proven per-stock edges; see `p_value_vs_baseline` in `results/stock_rankings.csv` for the honest per-ticker confidence.

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline | Significant? |
|---|---|---|---|---|---|
| GL | 9176 | 0.37% | -1.88% | 2.25% | no |
| DVN | 9401 | 0.14% | -2.11% | 2.25% | no |
| GE | 9223 | 0.38% | -1.74% | 2.12% | no |
| XYZ | 5902 | 0.62% | -1.30% | 1.91% | no |
| SMCI | 9089 | 0.91% | -0.88% | 1.80% | no |
| FISV | 9044 | 0.16% | -1.52% | 1.68% | no |
| KHC | 6036 | -0.08% | -1.73% | 1.65% | no |
| TTD | 5275 | 0.65% | -0.95% | 1.60% | no |
| ARE | 9274 | 0.14% | -1.45% | 1.59% | no |
| LULU | 9225 | 0.41% | -1.09% | 1.50% | no |
| EXPD | 9230 | 0.17% | -1.32% | 1.49% | no |
| MCO | 9086 | 0.43% | -1.05% | 1.48% | no |
| KVUE | 1621 | -0.13% | -1.54% | 1.41% | no |
| TPR | 9204 | 0.31% | -1.07% | 1.39% | no |
| DLTR | 9054 | 0.37% | -0.98% | 1.34% | no |

_Bottom 10 (least responsive / signals underperform that stock's own baseline):_

| Ticker | n trades | Avg return | Baseline avg return | Excess vs baseline |
|---|---|---|---|---|
| RVTY | 9298 | 0.27% | 3.28% | -3.01% |
| DECK | 9026 | 0.43% | 3.57% | -3.14% |
| UBER | 3850 | 0.31% | 3.52% | -3.21% |
| FDX | 9367 | 0.27% | 3.64% | -3.37% |
| PLTR | 3111 | 2.02% | 5.63% | -3.61% |
| ANET | 6648 | 0.71% | 4.39% | -3.68% |
| DDOG | 3681 | 0.82% | 4.64% | -3.82% |
| NOW | 7722 | 0.39% | 4.24% | -3.85% |
| MGM | 9358 | 0.09% | 4.01% | -3.92% |
| NFLX | 8941 | 0.88% | 5.37% | -4.50% |

## 5. Which sectors and market regimes are most responsive?

**0 of 12 sectors** show a positive point-estimate excess return over the random-entry baseline; **0** of those are statistically significant (cluster-robust by ticker, FDR-corrected):

| Sector | Avg return | Baseline avg return | Excess vs baseline | n tickers | Significant? |
|---|---|---|---|---|---|
| Consumer Staples | 0.21% | 0.42% | -0.20% | 32 | no |
| Unknown | 0.36% | 0.60% | -0.24% | 48 | no |
| Utilities | 0.21% | 0.50% | -0.29% | 29 | no |
| Financials | 0.31% | 0.64% | -0.33% | 69 | no |
| Materials | 0.28% | 0.64% | -0.37% | 24 | no |
| Real Estate | 0.21% | 0.63% | -0.43% | 30 | no |
| Industrials | 0.37% | 0.81% | -0.45% | 65 | no |
| Energy | 0.33% | 0.83% | -0.50% | 20 | no |
| Consumer Discretionary | 0.40% | 1.00% | -0.60% | 49 | no |
| Communication Services | 0.28% | 0.91% | -0.64% | 20 | no |
| Health Care | 0.30% | 1.05% | -0.75% | 53 | no |
| Information Technology | 0.53% | 1.52% | -0.99% | 60 | no |

### By market regime

| Trend regime | Vol regime | Avg return | Baseline avg return | Excess vs baseline | n trades |
|---|---|---|---|---|---|
| bear | high_vol | 0.80% | 2.26% | -1.46% | 267281 |
| bear | low_vol | 0.23% | 0.14% | 0.09% | 15569 |
| bear | normal_vol | 0.31% | 0.87% | -0.56% | 639992 |
| bull | high_vol | 0.63% | 1.39% | -0.76% | 179596 |
| bull | low_vol | 0.31% | 0.48% | -0.17% | 197103 |
| bull | normal_vol | 0.29% | 0.67% | -0.38% | 2094334 |
| sideways | high_vol | 0.63% | 1.95% | -1.32% | 130283 |
| sideways | low_vol | 0.25% | 1.11% | -0.86% | 27139 |
| sideways | normal_vol | 0.20% | 0.61% | -0.41% | 763386 |

## 6. Which concepts fail consistently?

Two distinct ways a concept can fail to earn a place in Section 2: it can be statistically indistinguishable from the baseline (no evidence either way), or it can be significantly *worse* (Section 2's second table). Lowest-Sharpe signals with at least 30 trades (10-day hold) that are indistinguishable from the random-entry baseline:

| Signal | n trades | Win rate | Sharpe |
|---|---|---|---|
| smc_swing_ob_bullish_mitigated | 3421 | 60.07% | 0.465 |
| smc_internal_ob_bullish_mitigated | 39894 | 57.14% | 0.499 |
| ict_ob_bullish_mitigated | 20705 | 58.02% | 0.538 |
| ict_nwog_formed | 421965 | 56.98% | 0.614 |
| ict_liquidity_buyside_pool_formed | 59340 | 57.13% | 0.631 |
| smc_equal_highs | 10547 | 57.31% | 0.635 |
| smc_swing_choch_bullish | 2721 | 56.85% | 0.671 |

## 7. Are results stable across bull, bear, and sideways markets?
No, not fully — see the regime table in Section 5. Excess return vs. baseline is negative in most trend/volatility regime cells (`results/regime_analysis.csv`), and the one clearly positive cell (bull + high volatility) is a narrow slice of the data. Regime classification uses each stock's own trailing SMA(200) trend and realized-volatility-vs-own-history state, not an external index. See the dashboard's Sector & Regime tab and `analytics/regimes.py:regime_analysis_by_signal` for the per-signal breakdown by regime.

## 8. Are results statistically significant after correcting for sample size and multiple testing?
Every ranking module (concepts, combinations, sectors, regimes) compares against a random-entry baseline run through identical backtest mechanics, in addition to a zero-return null, with Benjamini-Hochberg FDR correction applied to both (`analytics/statistics.py`). Both baseline comparisons use standard errors clustered by ticker (a sandwich/cluster-robust variance estimator, not a naive per-trade t-test): trades on the same ticker share overlapping forward-return windows and are not independent draws, so treating them as such understates the true standard error and can manufacture significance out of noise. This clustering corrects for *within-ticker* correlation; it does not implement a full two-way (ticker x date) correction for *cross-ticker* correlation on shared market-wide dates, which would tighten the test further in the conservative direction (see Key limitations). The headline `beats_baseline` flag requires clearing the FDR-corrected baseline comparison (alpha=0.05) **in the positive direction** *and* a minimum sample size — this is distinct from `significant_vs_baseline`, which is two-sided and flags a concept whether it beats or loses to the baseline. Per-ticker significance tests (Section 4) have limited statistical power due to small per-ticker baseline samples (~50 trades) and are not cluster-corrected (a single ticker has no cluster structure to correct for) — reported as a ranking with honest p-values, not a list of proven stock-specific edges.

## Key limitations
- In-sample results across the full 2010-2026 window (no held-out walk-forward split yet — see README Future Improvements).
- Significance tests are cluster-robust by ticker but not two-way (ticker x date) clustered — cross-ticker correlation on shared market-wide dates (e.g. 2020, 2022) is not corrected for, which would tighten these tests further, not loosen them.
- The universe (`data/raw/sp500_constituents.csv`) reflects current-day S&P 500 membership and weights applied retroactively across 2010-2026, not a point-in-time constituent history — constituents removed from the index during the window are absent, and recent additions (e.g. PLTR, COIN, DASH, CRWD) contribute their full available history despite not being index members for most of it. A form of survivorship bias; no point-in-time membership data was available to correct it.
- The per-ticker stock ranking covers 499 of the 501 tickers with usable price data: two (`FDXF`, `Q`) have clean price history but produced zero detected SMC/ICT events across the full window and drop out of that table without a separate flag.
- Sector mapping is a static approximation, not a live data source.
- No transaction costs or slippage modeled.
- Two ICT-literature concepts (Rejection Blocks, Optimal Trade Entry) have no corresponding logic in the source scripts and are not implemented.
- Per-ticker and per-sector/regime baseline comparisons have smaller sample sizes than the universe-wide concept-level comparison, so their significance tests are correspondingly less powered — read the excess-return figures as directional evidence, the p-values as the honest confidence level.
- See README.md "Limitations" and "Key assumptions" sections for the complete list.