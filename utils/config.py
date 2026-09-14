"""Central configuration for the SMC/ICT research pipeline.

Single source of truth for paths, date ranges, and every concept parameter
that was extracted from the two Pine scripts in docs/concepts_extraction.md
and docs/task02_pine_analysis.md. Defaults mirror the Pine `input.*` defaults
unless explicitly noted otherwise (see ASSUMPTIONS below).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_CACHE_DIR = PROJECT_ROOT / "data" / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
EXPORTS_DIR = PROJECT_ROOT / "exports"
LOGS_DIR = PROJECT_ROOT / "logs"

SP500_CONSTITUENTS_CSV = DATA_RAW_DIR / "sp500_constituents.csv"

for _dir in (DATA_CACHE_DIR, RESULTS_DIR, EXPORTS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Data window
# ---------------------------------------------------------------------------
DATA_START = "2010-01-01"
DATA_END = "2026-06-13"

# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------
HOLDING_PERIODS: list[int] = [1, 2, 3, 5, 10, 20, 40, 60]
PRIMARY_HOLDING_PERIOD = 10  # horizon used for the headline ranking tables

# ---------------------------------------------------------------------------
# Statistical configuration
# ---------------------------------------------------------------------------
# Two bootstrap budgets: FAST for iteration/CI, FINAL for the published run.
# Select with SMC_ICT_PROFILE=fast|final (default: final).
BOOTSTRAP_ITERATIONS_FAST = 5_000
BOOTSTRAP_ITERATIONS_FINAL = 10_000

_PROFILE = os.environ.get("SMC_ICT_PROFILE", "final").strip().lower()
PROFILE = _PROFILE if _PROFILE in ("fast", "final") else "final"
BOOTSTRAP_ITERATIONS = (
    BOOTSTRAP_ITERATIONS_FAST if PROFILE == "fast" else BOOTSTRAP_ITERATIONS_FINAL
)

FDR_ALPHA = 0.05  # Benjamini-Hochberg false discovery rate threshold
ALPHA = 0.05      # nominal per-test significance level

# Master seed. Every stochastic component derives a *stable* child seed from
# this via utils.rng.derive_seed (NOT Python's salted hash()), so a run is
# byte-reproducible across processes and machines. See results/seed.txt.
RANDOM_SEED = 42

# Minimum trades before a bucket's statistics are trusted rather than flagged.
MIN_SAMPLE_SIZE = 30

# Newey-West lag for the overlapping-window HAC standard errors used by the
# significance tests. Forward returns over h days computed on consecutive bars
# overlap by construction, so plain iid standard errors are far too small.
HAC_MAX_LAG_MULTIPLIER = 1  # lag = multiplier * holding_period

# ---------------------------------------------------------------------------
# Transaction costs (backtest/engine_tc.py)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CostParams:
    """Round-trip trading frictions applied to every simulated trade."""

    fixed_bps: float = 1.0          # per-trade fixed cost, basis points of notional
    spread_bps: float = 5.0         # proportional (half-spread paid twice), bps
    slippage_bps_low: float = 5.0   # slippage lower bound, bps (0.05%)
    slippage_bps_high: float = 20.0  # slippage upper bound, bps (0.20%)


COSTS = CostParams()

# ---------------------------------------------------------------------------
# Walk-forward evaluation
# ---------------------------------------------------------------------------
WALK_FORWARD_TRAIN_YEARS = 3
WALK_FORWARD_TEST_YEARS = 1
WALK_FORWARD_STEP_YEARS = 1

# ---------------------------------------------------------------------------
# Combination search bounds (anti data-snooping)
# ---------------------------------------------------------------------------
MIN_COMBO_OCCURRENCES = 100
MAX_COMBOS_TESTED = 60

# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------
MONTE_CARLO_RUNS = 1_000

# ---------------------------------------------------------------------------
# Data-quality gates
# ---------------------------------------------------------------------------
MIN_BARS_FOR_DETECTION = 300   # below this a ticker is skipped by the engine
MIN_COVERAGE_RATIO = 0.95      # vs. the universe's own modal trading calendar
REPAIR_INVALID_OHLC = True     # clamp high/low to enclose open/close (see data_quality)

# ---------------------------------------------------------------------------
# Concept parameters (mirrors Pine `input.*` defaults; see
# docs/task02_pine_analysis.md Section 4 for the full traceable mapping)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ICTParams:
    """Defaults sourced from ICT_Concepts_LuxAlgo.pine (docs/task02 Section 4.1)."""

    mss_pivot_len: int = 5            # `len` (Market Structures length, 3-10)
    ob_swing_len: int = 10            # `length` (Order Block swing lookback, >=3)
    ob_use_body: bool = True          # `useBody`
    displacement_perc_body: float = 0.36  # hard-coded `perc_Body` in source
    liquidity_margin: float = 4.0     # `margin` input -> a = 10/margin
    liquidity_atr_len: int = 10       # `ta.atr(10)` used by liquidity clustering
    liquidity_min_cluster: int = 2    # `count > 2` required to form a pool
    fvg_mode: str = "FVG"             # 'FVG' or 'IFVG' (see Ambiguity A1)
    nwog_enabled: bool = True
    ndog_enabled: bool = False        # off by default in source
    # OB array retention cap -- source is uncapped; capped here for a 500-stock,
    # 16-year batch run (Ambiguity A8 in docs/task02_pine_analysis.md).
    ob_max_retained: int = 200

    # --- Liquidity sweep, formalised (docs/specs/ict_liquidity_sweep.yaml) ---
    # A sweep is a two-part, strictly prospective event:
    #   (X) price must exceed the reference swing level by at least
    #       `sweep_penetration_atr` * ATR(sweep_atr_len)  -- the stop-run leg;
    #   (Y) price must then CLOSE back past `sweep_reclaim_frac` * ATR beyond
    #       the level -- the rejection leg;
    #   (Z) within `sweep_confirm_bars` bars of the penetration.
    # The event is stamped on the *reclaim* bar, so no future data is used.
    sweep_penetration_atr: float = 0.25
    sweep_reclaim_frac: float = 0.0
    sweep_confirm_bars: int = 3
    sweep_atr_len: int = 14
    sweep_swing_len: int = 10

    # --- Opening gaps, formalised (docs/specs/ict_opening_gap.yaml) ---
    # A gap must be MATERIAL to be an event. The original detector emitted
    # `ict_ndog_formed = True` on literally every bar (1.95M events = 45% of
    # the entire event table), which is not a signal at all.
    gap_min_atr: float = 0.10
    gap_atr_len: int = 14


@dataclass(frozen=True)
class SMCParams:
    """Defaults sourced from SMC_Concepts_LuxAlgo.pine (docs/task02 Section 4.2)."""

    swing_len: int = 50               # `swingsLengthInput`, >=10
    internal_len: int = 5             # hard-coded in getCurrentStructure(5, ...)
    equal_hl_len: int = 3             # `equalHighsLowsLengthInput`, >=1
    equal_hl_threshold: float = 0.1   # fraction of ATR(200)
    equal_hl_atr_len: int = 200
    ob_atr_len: int = 200             # `ta.atr(200)` volatility measure
    ob_filter_mode: str = "Atr"       # 'Atr' or 'Cumulative Mean Range'
    ob_mitigation_mode: str = "High/Low"  # 'Close' or 'High/Low'
    ob_max_retained: int = 100        # matches source array cap
    internal_filter_confluence: bool = False
    fvg_auto_threshold: bool = True
    fvg_extend_bars: int = 1
    premium_discount_band: float = 0.05  # top/bottom 5% bands


ICT = ICTParams()
SMC = SMCParams()

# ---------------------------------------------------------------------------
# Ticker normalization
# ---------------------------------------------------------------------------
# yfinance uses '-' where the constituents list uses '.' (e.g. BRK.B -> BRK-B).
TICKER_SYMBOL_OVERRIDES: dict[str, str] = {
    "BRK.B": "BRK-B",
    "BF.B": "BF-B",
}

# ---------------------------------------------------------------------------
# Assumptions carried from Task 1/2 docs (see docs/concepts_extraction.md
# Section 5 and docs/task02_pine_analysis.md Section 6 for full rationale)
# ---------------------------------------------------------------------------
ASSUMPTIONS = {
    "mode": "Historical mode only (Pine 'Present' 500-bar display window dropped).",
    "bos_gating": "BOS treated as always-computed regardless of Pine's iBOS toggle.",
    "premium_discount_range": (
        "Computed BOTH as literal all-time expanding min/max (source-faithful "
        "default) AND as a rolling-window variant for robustness comparison "
        "(see analytics/regimes.py)."
    ),
    "atr_smoothing": "ta.atr replicated via Wilder's RMA smoothing (TradingView convention).",
    "nwog_holiday_edge_case": (
        "Python NWOG uses the most recent completed trading week's Friday close, "
        "not a literal var-persisted stale carry-over."
    ),
    "killzones": "Excluded entirely -- intraday-only concept, no meaning on daily bars.",
    "rejection_blocks_ote": "Not implemented -- no corresponding logic in either source script.",
}
