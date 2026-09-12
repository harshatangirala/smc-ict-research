# Master Summary -- SMC/ICT Statistical Edge Study

*Generated 2026-09-11 13:39 UTC · 352 (signal x horizon) hypotheses · BH-FDR at alpha = 0.05 across the whole family · 10,000 bootstrap iterations*

Full machine-readable table: `results/statistics_master.csv`.

## How to read this

* **Excess vs matched random** is the headline quantity: the concept's mean return minus the mean of entering the *same tickers* the *same number of times* on randomly chosen dates. It removes the ticker-mix confound that a pooled comparison cannot.
* **p (vs zero)** uses a calendar-time Newey-West standard error, not the iid t-test. Forward returns overlap and cluster cross-sectionally; the iid p-values (retained as `p_value_vs_zero_iid`) are far too small.
* **p (vs null)** is a calendar-time Newey-West test on each trade's excess over its ticker's matched mean. The simple-random-sampling version (`p_value_vs_matched_random_srs`) is anti-conservative for signals that fire on shared dates; see `results/test_calibration.csv`.
* **Beats null** requires a positive excess AND survival of BH-FDR at alpha = 0.05 AND an adequate sample. A significant *negative* excess is reported as losing to the null, never as an edge.

---

## 1. All concepts at the primary horizon (h = 10 days)

| # | Signal | Dir | n | Win rate | Mean | Median | Excess vs null | p (FDR, vs null) | Cohen's d [95% CI] | Sharpe | Beats null |
|--:|---|--:|--:|--:|--:|--:|--:|--:|---|--:|:--:|
| 1 | `smc_swing_choch_bearish` | -1 | 2,653 | 43.27% | -0.37% | -1.14% | 0.33% | 1.000 | -0.038 [-0.077, -0.001] | -0.19 | no |
| 2 | `smc_swing_ob_bearish_formed` | -1 | 3,898 | 43.41% | -0.49% | -1.11% | 0.19% | 1.000 | -0.052 [-0.084, -0.020] | -0.26 | no |
| 3 | `ict_sweep_sellside_bullish` | +1 | 49,304 | 57.13% | 0.82% | 0.86% | 0.12% | 1.000 | 0.125 [0.110, 0.139] | 0.64 | no |
| 4 | `ict_sweep_buyside_bearish` | -1 | 65,448 | 43.74% | -0.59% | -0.70% | 0.11% | 1.000 | -0.101 [-0.115, -0.088] | -0.50 | no |
| 5 | `ict_liquidity_buyside_pool_formed` | +1 | 58,941 | 57.16% | 0.74% | 0.82% | 0.06% | 1.000 | 0.118 [0.104, 0.132] | 0.63 | no |
| 6 | `ict_nwog_gap_up` | +1 | 147,321 | 56.98% | 0.77% | 0.77% | 0.05% | 1.000 | 0.121 [0.107, 0.135] | 0.61 | no |
| 7 | `smc_swing_choch_bullish` | +1 | 2,699 | 56.95% | 0.73% | 0.67% | 0.04% | 1.000 | 0.134 [0.097, 0.170] | 0.67 | no |
| 8 | `smc_internal_ob_bearish_mitigated` | +1 | 38,121 | 56.83% | 0.70% | 0.73% | -0.01% | 1.000 | 0.122 [0.108, 0.135] | 0.61 | no |
| 9 | `ict_nwog_gap_down` | -1 | 130,643 | 42.81% | -0.73% | -0.83% | -0.02% | 1.000 | -0.103 [-0.118, -0.089] | -0.56 | no |
| 10 | `ict_ob_bearish_mitigated` | +1 | 20,124 | 56.57% | 0.68% | 0.67% | -0.02% | 1.000 | 0.122 [0.108, 0.135] | 0.62 | no |
| 11 | `ict_mss_bullish` | +1 | 36,506 | 56.62% | 0.68% | 0.76% | -0.04% | 1.000 | 0.107 [0.094, 0.121] | 0.55 | no |
| 12 | `ict_liquidity_buyside_swept` | +1 | 44,261 | 57.06% | 0.64% | 0.73% | -0.05% | 1.000 | 0.103 [0.090, 0.117] | 0.58 | no |
| 13 | `smc_swing_ob_bearish_mitigated` | +1 | 3,356 | 55.07% | 0.65% | 0.51% | -0.05% | 1.000 | 0.121 [0.088, 0.155] | 0.61 | no |
| 14 | `smc_swing_ob_bullish_formed` | +1 | 7,275 | 56.96% | 0.66% | 0.64% | -0.06% | 1.000 | 0.127 [0.105, 0.150] | 0.64 | no |
| 15 | `smc_equal_highs` | -1 | 10,483 | 42.48% | -0.75% | -0.80% | -0.06% | 1.000 | -0.128 [-0.148, -0.109] | -0.64 | no |
| 16 | `smc_internal_choch_bearish` | -1 | 26,315 | 43.64% | -0.77% | -0.75% | -0.06% | 1.000 | -0.115 [-0.129, -0.101] | -0.59 | no |
| 17 | `smc_fvg_bullish_formed` | +1 | 68,004 | 55.59% | 0.65% | 0.66% | -0.06% | 1.000 | 0.090 [0.077, 0.104] | 0.50 | no |
| 18 | `smc_internal_choch_bullish` | +1 | 26,396 | 56.79% | 0.64% | 0.76% | -0.07% | 1.000 | 0.105 [0.091, 0.119] | 0.53 | no |
| 19 | `ict_bpr_bearish` | -1 | 26,182 | 43.97% | -0.79% | -0.75% | -0.07% | 1.000 | -0.124 [-0.137, -0.110] | -0.61 | no |
| 20 | `smc_swing_bos_bearish` | -1 | 1,245 | 43.69% | -0.76% | -0.93% | -0.09% | 1.000 | -0.085 [-0.144, -0.029] | -0.43 | no |
| 21 | `smc_internal_ob_bullish_mitigated` | -1 | 39,612 | 42.76% | -0.79% | -0.97% | -0.09% | 1.000 | -0.105 [-0.120, -0.091] | -0.50 | no |
| 22 | `smc_equal_lows` | +1 | 9,341 | 55.11% | 0.60% | 0.57% | -0.10% | 1.000 | 0.101 [0.081, 0.121] | 0.51 | no |
| 23 | `ict_bpr_bullish` | +1 | 26,830 | 55.96% | 0.62% | 0.68% | -0.10% | 1.000 | 0.098 [0.084, 0.112] | 0.50 | no |
| 24 | `smc_swing_bos_bullish` | +1 | 4,576 | 56.97% | 0.61% | 0.62% | -0.11% | 1.000 | 0.123 [0.095, 0.151] | 0.62 | no |
| 25 | `ict_liquidity_sellside_pool_formed` | -1 | 51,635 | 42.52% | -0.82% | -0.90% | -0.13% | 1.000 | -0.126 [-0.140, -0.112] | -0.64 | no |
| 26 | `ict_mss_bearish` | -1 | 36,553 | 42.94% | -0.85% | -0.84% | -0.14% | 1.000 | -0.128 [-0.142, -0.114] | -0.67 | no |
| 27 | `ict_displacement_bullish` | +1 | 212,461 | 56.04% | 0.57% | 0.65% | -0.16% | 1.000 | 0.091 [0.077, 0.105] | 0.47 | no |
| 28 | `ict_fvg_bullish_formed` | +1 | 112,181 | 55.90% | 0.56% | 0.63% | -0.16% | 1.000 | 0.093 [0.079, 0.107] | 0.48 | no |
| 29 | `smc_internal_ob_bearish_formed` | -1 | 42,864 | 42.70% | -0.87% | -0.90% | -0.16% | 1.000 | -0.110 [-0.124, -0.096] | -0.63 | no |
| 30 | `ict_ob_bearish_formed` | -1 | 22,431 | 42.78% | -0.87% | -0.90% | -0.16% | 1.000 | -0.123 [-0.137, -0.108] | -0.61 | no |
| 31 | `ict_fvg_bearish_formed` | -1 | 90,730 | 42.86% | -0.88% | -0.87% | -0.17% | 1.000 | -0.120 [-0.134, -0.106] | -0.64 | no |
| 32 | `ict_ob_bullish_formed` | +1 | 32,541 | 56.45% | 0.55% | 0.65% | -0.17% | 1.000 | 0.102 [0.088, 0.115] | 0.49 | no |
| 33 | `ict_displacement_bearish` | -1 | 190,415 | 42.69% | -0.90% | -0.85% | -0.19% | 1.000 | -0.140 [-0.154, -0.126] | -0.69 | no |
| 34 | `ict_liquidity_sellside_swept` | -1 | 32,884 | 42.05% | -0.88% | -0.96% | -0.20% | 1.000 | -0.120 [-0.135, -0.105] | -0.64 | no |
| 35 | `smc_internal_ob_bullish_formed` | +1 | 58,340 | 55.80% | 0.52% | 0.59% | -0.20% | 1.000 | 0.095 [0.082, 0.109] | 0.46 | no |
| 36 | `ict_volume_imbalance_bullish` | +1 | 117,546 | 55.51% | 0.50% | 0.57% | -0.21% | 1.000 | 0.089 [0.075, 0.103] | 0.43 | no |
| 37 | `ict_volume_imbalance_bearish` | -1 | 84,642 | 41.63% | -0.94% | -1.00% | -0.23% | 1.000 | -0.136 [-0.150, -0.121] | -0.70 | no |
| 38 | `ict_ob_bullish_mitigated` | -1 | 20,562 | 41.86% | -0.94% | -1.14% | -0.24% | 1.000 | -0.107 [-0.122, -0.093] | -0.54 | no |
| 39 | `ict_bos_bullish` | +1 | 80,739 | 55.20% | 0.44% | 0.50% | -0.29% | 1.000 | 0.085 [0.071, 0.098] | 0.40 | no |
| 40 | `smc_internal_bos_bullish` | +1 | 31,944 | 54.98% | 0.42% | 0.47% | -0.31% | 1.000 | 0.078 [0.064, 0.092] | 0.39 | no |
| 41 | `smc_internal_bos_bearish` | -1 | 16,549 | 41.22% | -1.03% | -1.12% | -0.33% | 1.000 | -0.139 [-0.155, -0.123] | -0.70 | no |
| 42 | `smc_swing_ob_bullish_mitigated` | -1 | 3,405 | 39.97% | -1.05% | -1.68% | -0.38% | 1.000 | -0.091 [-0.126, -0.056] | -0.46 | no |
| 43 | `smc_fvg_bearish_formed` | -1 | 67,673 | 42.10% | -1.09% | -1.06% | -0.39% | 1.000 | -0.141 [-0.156, -0.127] | -0.70 | no |
| 44 | `ict_bos_bearish` | -1 | 42,496 | 40.24% | -1.20% | -1.23% | -0.49% | 1.000 | -0.155 [-0.170, -0.141] | -0.81 | no |

## 2. Distributional and risk detail (h = 10)

| Signal | Std | Skew | Kurt | Expectancy | Profit factor | Sortino | Calmar | Max DD | Avg MFE | Avg MAE |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `smc_swing_choch_bearish` | 9.77% | 1.20 | 6.50 | -0.368% | 0.89 | -0.33 | -0.19 | -100.0% | 6.86% | -6.28% |
| `smc_swing_ob_bearish_formed` | 9.50% | 1.08 | 6.52 | -0.493% | 0.86 | -0.44 | -0.21 | -100.0% | 6.51% | -6.32% |
| `ict_sweep_sellside_bullish` | 6.46% | -0.09 | 5.06 | 0.822% | 1.43 | 0.89 | 0.17 | -97.7% | 4.81% | -4.22% |
| `ict_sweep_buyside_bearish` | 5.98% | -0.13 | 6.74 | -0.592% | 0.76 | -0.71 | -0.18 | -100.0% | 3.95% | -4.45% |
| `ict_liquidity_buyside_pool_formed` | 5.89% | 0.32 | 7.94 | 0.743% | 1.42 | 0.92 | 0.16 | -97.4% | 4.45% | -3.84% |
| `ict_nwog_gap_up` | 6.26% | 0.27 | 9.17 | 0.767% | 1.42 | 0.87 | 0.16 | -97.8% | 4.61% | -3.97% |
| `smc_swing_choch_bullish` | 5.48% | 0.72 | 6.09 | 0.734% | 1.46 | 1.09 | 0.19 | -83.2% | 4.26% | -3.65% |
| `smc_internal_ob_bearish_mitigated` | 5.75% | 0.43 | 6.08 | 0.701% | 1.41 | 0.91 | 0.15 | -96.4% | 4.36% | -3.78% |
| `ict_nwog_gap_down` | 6.56% | 0.06 | 7.91 | -0.731% | 0.73 | -0.79 | -0.22 | -100.0% | 4.13% | -4.78% |
| `ict_ob_bearish_mitigated` | 5.57% | 0.45 | 5.79 | 0.684% | 1.42 | 0.92 | 0.15 | -92.9% | 4.26% | -3.69% |
| `ict_mss_bullish` | 6.14% | 0.44 | 7.16 | 0.676% | 1.36 | 0.81 | 0.14 | -90.3% | 4.49% | -3.98% |
| `ict_liquidity_buyside_swept` | 5.59% | 0.42 | 7.64 | 0.642% | 1.38 | 0.85 | 0.14 | -92.5% | 4.24% | -3.73% |
| `smc_swing_ob_bearish_mitigated` | 5.42% | 0.36 | 3.38 | 0.655% | 1.40 | 0.95 | 0.21 | -66.5% | 4.24% | -3.77% |
| `smc_swing_ob_bullish_formed` | 5.17% | 0.65 | 7.20 | 0.657% | 1.44 | 0.98 | 0.20 | -70.7% | 3.94% | -3.38% |
| `smc_equal_highs` | 5.89% | -0.50 | 8.71 | -0.753% | 0.70 | -0.87 | -0.21 | -100.0% | 3.73% | -4.45% |
| `smc_internal_choch_bearish` | 6.51% | 0.02 | 6.29 | -0.767% | 0.72 | -0.84 | -0.22 | -100.0% | 4.30% | -4.87% |
| `smc_fvg_bullish_formed` | 6.63% | 0.44 | 8.33 | 0.653% | 1.33 | 0.72 | 0.12 | -99.2% | 4.96% | -4.45% |
| `smc_internal_choch_bullish` | 6.04% | 0.33 | 6.49 | 0.640% | 1.35 | 0.76 | 0.14 | -87.4% | 4.47% | -3.94% |
| `ict_bpr_bearish` | 6.50% | -0.31 | 6.54 | -0.785% | 0.71 | -0.83 | -0.23 | -100.0% | 4.25% | -4.96% |
| `smc_swing_bos_bearish` | 8.89% | 0.71 | 6.28 | -0.759% | 0.78 | -0.65 | -0.25 | -100.0% | 5.78% | -6.40% |
| `smc_internal_ob_bullish_mitigated` | 8.01% | 0.61 | 7.69 | -0.792% | 0.75 | -0.74 | -0.25 | -100.0% | 5.28% | -5.70% |
| `smc_equal_lows` | 5.89% | 0.28 | 6.87 | 0.597% | 1.33 | 0.74 | 0.12 | -92.3% | 4.36% | -3.84% |
| `ict_bpr_bullish` | 6.27% | 0.14 | 5.08 | 0.619% | 1.32 | 0.71 | 0.12 | -94.4% | 4.64% | -4.14% |
| `smc_swing_bos_bullish` | 4.97% | 0.59 | 8.00 | 0.612% | 1.42 | 0.91 | 0.20 | -67.2% | 3.75% | -3.22% |
| `ict_liquidity_sellside_pool_formed` | 6.47% | 0.21 | 7.68 | -0.823% | 0.70 | -0.93 | -0.24 | -100.0% | 4.19% | -4.89% |
| `ict_mss_bearish` | 6.36% | -0.09 | 6.29 | -0.846% | 0.69 | -0.94 | -0.23 | -100.0% | 4.19% | -4.82% |
| `ict_displacement_bullish` | 6.01% | 0.26 | 8.32 | 0.566% | 1.31 | 0.67 | 0.10 | -99.8% | 4.40% | -3.99% |
| `ict_fvg_bullish_formed` | 5.91% | 0.48 | 9.02 | 0.564% | 1.31 | 0.69 | 0.11 | -97.7% | 4.35% | -3.92% |
| `smc_internal_ob_bearish_formed` | 6.88% | 0.21 | 6.12 | -0.870% | 0.70 | -0.92 | -0.25 | -100.0% | 4.50% | -5.13% |
| `ict_ob_bearish_formed` | 7.08% | 0.27 | 6.20 | -0.867% | 0.71 | -0.89 | -0.25 | -100.0% | 4.70% | -5.23% |
| `ict_fvg_bearish_formed` | 6.88% | 0.05 | 8.50 | -0.878% | 0.69 | -0.89 | -0.25 | -100.0% | 4.36% | -5.13% |
| `ict_ob_bullish_formed` | 5.64% | 0.46 | 8.34 | 0.553% | 1.32 | 0.71 | 0.11 | -91.3% | 4.16% | -3.71% |
| `ict_displacement_bearish` | 6.53% | -0.16 | 9.45 | -0.902% | 0.67 | -0.95 | -0.25 | -100.0% | 4.16% | -4.93% |
| `ict_liquidity_sellside_swept` | 6.90% | 0.47 | 6.32 | -0.885% | 0.69 | -0.96 | -0.25 | -100.0% | 4.53% | -5.14% |
| `smc_internal_ob_bullish_formed` | 5.72% | 0.51 | 7.85 | 0.520% | 1.30 | 0.67 | 0.10 | -92.7% | 4.19% | -3.80% |
| `ict_volume_imbalance_bullish` | 5.88% | 0.31 | 10.68 | 0.501% | 1.28 | 0.60 | 0.09 | -98.7% | 4.22% | -3.93% |
| `ict_volume_imbalance_bearish` | 6.75% | 0.01 | 9.28 | -0.940% | 0.67 | -0.98 | -0.26 | -100.0% | 4.23% | -5.05% |
| `ict_ob_bullish_mitigated` | 8.72% | 0.69 | 7.36 | -0.939% | 0.73 | -0.81 | -0.28 | -100.0% | 5.75% | -6.21% |
| `ict_bos_bullish` | 5.46% | 0.70 | 10.26 | 0.435% | 1.26 | 0.59 | 0.08 | -97.0% | 3.96% | -3.69% |
| `smc_internal_bos_bullish` | 5.44% | 0.71 | 9.32 | 0.421% | 1.25 | 0.58 | 0.08 | -85.1% | 3.96% | -3.68% |
| `smc_internal_bos_bearish` | 7.42% | 0.43 | 5.70 | -1.035% | 0.67 | -1.05 | -0.28 | -100.0% | 4.81% | -5.54% |
| `smc_swing_ob_bullish_mitigated` | 11.59% | 1.00 | 6.10 | -1.052% | 0.76 | -0.74 | -0.35 | -100.0% | 8.28% | -8.21% |
| `smc_fvg_bearish_formed` | 7.76% | 0.02 | 8.29 | -1.090% | 0.66 | -0.97 | -0.30 | -100.0% | 4.92% | -5.86% |
| `ict_bos_bearish` | 7.43% | 0.32 | 10.27 | -1.199% | 0.62 | -1.17 | -0.32 | -100.0% | 4.68% | -5.54% |

## 3. Excess return over the matched-random null, by horizon

A genuine edge should not appear at one horizon and vanish at the neighbouring ones.

| Signal | h=1 | h=2 | h=3 | h=5 | h=10 | h=20 | h=40 | h=60 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `smc_swing_choch_bearish` | -0.33% | 0.35% | 0.18% | 0.39% | 0.33% | -0.92% | -1.17% | -3.26% |
| `smc_swing_ob_bearish_formed` | -0.26% | 0.30% | 0.11% | 0.18% | 0.19% | -0.81% | -1.20% | -3.05% |
| `ict_sweep_sellside_bullish` | -0.01% | 0.04% | 0.03% | 0.01% | 0.12% | 0.49% | 0.47% | 0.61% |
| `ict_sweep_buyside_bearish` | -0.00% | -0.00% | -0.01% | -0.03% | 0.11% | 0.28% | 0.48% | 0.41% |
| `ict_liquidity_buyside_pool_formed` | 0.00% | -0.04% | -0.02% | 0.01% | 0.06% | 0.03% | 0.11% | 0.18% |
| `ict_nwog_gap_up` | 0.01% | 0.05% | 0.05% | 0.00% | 0.05% | 0.22% | 0.32% | 0.27% |
| `smc_swing_choch_bullish` | 0.03% | -0.05% | -0.11% | -0.04% | 0.04% | -0.20% | -0.21% | 0.06% |
| `smc_internal_ob_bearish_mitigated` | -0.02% | -0.05% | -0.07% | -0.08% | -0.01% | -0.11% | -0.43% | -0.46% |
| `ict_nwog_gap_down` | -0.09% | -0.05% | -0.01% | -0.03% | -0.02% | 0.07% | -0.04% | -0.24% |
| `ict_ob_bearish_mitigated` | -0.01% | -0.04% | -0.05% | -0.05% | -0.02% | -0.15% | -0.58% | -0.64% |
| `ict_mss_bullish` | -0.04% | -0.05% | -0.10% | -0.10% | -0.04% | 0.00% | -0.07% | -0.28% |
| `ict_liquidity_buyside_swept` | -0.01% | -0.03% | -0.05% | -0.05% | -0.05% | -0.10% | -0.16% | -0.16% |
| `smc_swing_ob_bearish_mitigated` | -0.05% | -0.13% | -0.15% | -0.12% | -0.05% | -0.03% | 0.14% | 0.40% |
| `smc_swing_ob_bullish_formed` | 0.01% | -0.02% | -0.02% | -0.04% | -0.06% | -0.25% | -0.69% | -0.72% |
| `smc_equal_highs` | -0.01% | -0.04% | -0.08% | -0.08% | -0.06% | -0.11% | -0.15% | 0.17% |
| `smc_internal_choch_bearish` | 0.03% | -0.00% | -0.07% | -0.14% | -0.06% | -0.11% | -0.09% | -0.23% |
| `smc_fvg_bullish_formed` | -0.00% | -0.05% | -0.10% | -0.17% | -0.06% | -0.01% | 0.15% | 0.11% |
| `smc_internal_choch_bullish` | -0.01% | -0.02% | -0.05% | -0.12% | -0.07% | 0.02% | -0.16% | -0.40% |
| `ict_bpr_bearish` | 0.02% | -0.05% | -0.17% | -0.19% | -0.07% | 0.07% | -0.18% | -0.30% |
| `smc_swing_bos_bearish` | -0.10% | 0.18% | -0.03% | -0.27% | -0.09% | -0.58% | -1.26% | -2.60% |
| `smc_internal_ob_bullish_mitigated` | -0.04% | 0.06% | -0.05% | -0.15% | -0.09% | -0.54% | -0.72% | -1.87% |
| `smc_equal_lows` | 0.02% | 0.01% | -0.06% | -0.13% | -0.10% | -0.05% | -0.14% | -0.60% |
| `ict_bpr_bullish` | 0.01% | -0.03% | -0.04% | -0.09% | -0.10% | -0.03% | 0.06% | -0.16% |
| `smc_swing_bos_bullish` | -0.00% | -0.01% | 0.04% | -0.04% | -0.11% | -0.28% | -0.97% | -1.17% |
| `ict_liquidity_sellside_pool_formed` | -0.01% | -0.06% | -0.10% | -0.11% | -0.13% | -0.35% | -0.52% | -0.77% |
| `ict_mss_bearish` | 0.07% | 0.04% | -0.01% | -0.13% | -0.14% | -0.16% | -0.17% | -0.30% |
| `ict_displacement_bullish` | -0.03% | -0.05% | -0.08% | -0.14% | -0.16% | -0.18% | -0.25% | -0.38% |
| `ict_fvg_bullish_formed` | -0.02% | -0.07% | -0.10% | -0.16% | -0.16% | -0.25% | -0.40% | -0.60% |
| `smc_internal_ob_bearish_formed` | 0.01% | 0.01% | -0.03% | -0.14% | -0.16% | -0.39% | -0.53% | -0.76% |
| `ict_ob_bearish_formed` | 0.05% | 0.08% | -0.02% | -0.12% | -0.16% | -0.41% | -0.65% | -1.03% |
| `ict_fvg_bearish_formed` | 0.01% | -0.04% | -0.15% | -0.24% | -0.17% | -0.16% | -0.35% | -0.72% |
| `ict_ob_bullish_formed` | -0.03% | -0.07% | -0.12% | -0.13% | -0.17% | -0.25% | -0.67% | -0.87% |
| `ict_displacement_bearish` | -0.04% | -0.04% | -0.08% | -0.13% | -0.19% | -0.24% | -0.28% | -0.40% |
| `ict_liquidity_sellside_swept` | -0.02% | 0.02% | -0.02% | -0.08% | -0.20% | -0.55% | -0.84% | -1.32% |
| `smc_internal_ob_bullish_formed` | -0.04% | -0.07% | -0.11% | -0.18% | -0.20% | -0.22% | -0.52% | -0.73% |
| `ict_volume_imbalance_bullish` | -0.09% | -0.10% | -0.13% | -0.18% | -0.21% | -0.21% | -0.43% | -0.55% |
| `ict_volume_imbalance_bearish` | -0.07% | -0.07% | -0.14% | -0.23% | -0.23% | -0.27% | -0.56% | -0.73% |
| `ict_ob_bullish_mitigated` | -0.25% | 0.04% | -0.16% | -0.24% | -0.24% | -0.96% | -1.14% | -2.85% |
| `ict_bos_bullish` | -0.04% | -0.10% | -0.14% | -0.21% | -0.29% | -0.51% | -0.84% | -0.99% |
| `smc_internal_bos_bullish` | -0.05% | -0.11% | -0.15% | -0.23% | -0.31% | -0.43% | -0.81% | -1.00% |
| `smc_internal_bos_bearish` | -0.02% | 0.04% | 0.03% | -0.14% | -0.33% | -0.84% | -1.23% | -1.61% |
| `smc_swing_ob_bullish_mitigated` | -0.52% | 0.34% | 0.16% | -0.08% | -0.38% | -2.40% | -3.32% | -7.30% |
| `smc_fvg_bearish_formed` | 0.01% | -0.09% | -0.28% | -0.45% | -0.39% | -0.62% | -1.12% | -1.99% |
| `ict_bos_bearish` | -0.08% | 0.01% | -0.05% | -0.16% | -0.49% | -0.88% | -1.10% | -1.67% |

**14 of 44 concepts keep the same sign of excess return at every horizon.** Sign flips across adjacent horizons are a symptom of noise rather than of a horizon-specific effect.

## 4. Summary counts

At h = 10, of 44 concepts:

* **0** beat the composition-matched random-entry null after BH-FDR at alpha = 0.05;
* **0** are significantly **worse** than it (two-sided family, BH-FDR);
* **44** are statistically indistinguishable from it;
* 38 differ from a zero-return null -- a weak bar over a 16-year bull market that a long-biased signal clears on drift alone.
