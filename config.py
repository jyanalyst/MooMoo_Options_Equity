"""
Configuration settings for Options Scanner
Strategy parameters derived from Wheel Strategy Guide
"""

import platform
import subprocess

# =============================================================================
# FINANCIAL MODELING PREP API SETTINGS
# =============================================================================

FMP_API_KEY = "SUmg1Fkg9IxxPrCGF8HFP3sdLLl35IUk"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

# =============================================================================
# MOOMOO API SETTINGS
# =============================================================================


def _get_wsl2_host_ip() -> str:
    """Resolve the Windows host IP when running inside WSL2.

    OpenD runs on the Windows host, so WSL2 cannot reach it via 127.0.0.1.
    The host IP is the default gateway shown by ``ip route``.
    """
    try:
        result = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "default" in line:
                return line.split()[2]
    except Exception:
        pass
    return "172.24.32.1"  # static fallback


def _get_moomoo_host() -> str:
    """Return the appropriate MooMoo host IP for the current environment."""
    # Inside WSL2 on Linux, resolve the Windows host gateway
    if platform.system() == "Linux":
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return _get_wsl2_host_ip()
        except FileNotFoundError:
            pass
    # Native Windows or other — OpenD is on localhost
    return "127.0.0.1"


MOOMOO_HOST = _get_moomoo_host()
MOOMOO_PORT = 11111

# Rate limiting (MooMoo recommends 3 seconds between option chain calls)
API_DELAY_SECONDS = 3

# =============================================================================
# WHEEL STRATEGY PARAMETERS
# =============================================================================

WHEEL_CONFIG = {
    # Stock filters
    "price_min": 15.0,
    "price_max": 200.0,
    "market_cap_min_billions": 10,  # Pre-filtered in universe.py
    # Options filters
    "iv_rank_min": 30,  # RESTORED: Minimum IV Rank required
    "iv_rank_preferred": 50,
    "delta_min": 0.20,
    "delta_max": 0.30,
    "dte_min": 30,
    "dte_max": 45,
    "volume_min": 1,  # RELAXED: Minimum volume (OR logic with OI) - just needs SOME activity
    "open_interest_min": 10,  # RELAXED: Minimum open interest - wheel positions are held to expiration anyway
    "bid_ask_spread_max_pct": 0.50,  # TEMPORARILY RELAXED FOR DEBUGGING (50% of mid)
    # Premium target
    "premium_pct_of_strike_min": 0.001,  # TEMPORARILY RELAXED FOR DEBUGGING (0.1% minimum)
    # Earnings buffer
    "earnings_buffer_days": 7,
    # Post-earnings IV-crush guard: selling premium just after a report means selling
    # into an IV crush (cheap premium, negative EV). Per the strategy guide, a
    # post-earnings entry is valid ONLY if IV Rank is CONFIRMED elevated (> threshold).
    "earnings_recency_days": 10,  # treat <=N days since last report as crush-risk
    "post_earnings_min_iv_rank": 40,  # required confirmed IV Rank to allow such a name
    # Earnings validation (FAIL-CLOSED by default — never trade blind through earnings).
    # Unverified earnings (FMP returned no date) are REJECTED. Override per-run with
    # --allow-unverified if you will manually verify each name.
    "allow_unverified_earnings": False,
    # Term structure (contango = favorable)
    "term_structure_check": True,
}

# =============================================================================
# EARNINGS CONFIGURATION (FMP-Only)
# =============================================================================

EARNINGS_CONFIG = {
    "data_source": "FMP",  # Only FMP now (yfinance removed)
    "cache_expiry_hours": 12,  # Refresh earnings cache every 12 hours
    "allow_unverified": False,  # Default: fail-closed (reject when no earnings date)
    "buffer_days": 7,  # Buffer days after expiration
}

# =============================================================================
# MANUAL TICKER WHITELIST
# Tickers added here bypass fundamental screening (e.g., ETFs, leveraged products)
# WARNING: These are not quality-screened - understand the risks!
# =============================================================================

MANUAL_TICKERS = [
    "TQQQ",  # 3x Leveraged Nasdaq-100 ETF - HIGH RISK, no earnings
]

# =============================================================================
# POSITION SIZING (Reference only - not used in scanner logic)
# =============================================================================

POSITION_SIZING = {
    "total_capital": 44500,  # USD
    "max_per_position_pct": 0.20,
    "target_position_pct_min": 0.10,
    "target_position_pct_max": 0.15,
    "cash_reserve_pct": 0.20,
}

# =============================================================================
# OUTPUT SETTINGS
# =============================================================================

OUTPUT_CONFIG = {
    "csv_output_dir": "./scan_results",
    "csv_filename_wheel": "wheel_candidates_{date}.csv",
    "display_top_n": 10,  # Show top N candidates in terminal
}

# =============================================================================
# POSITION-LEVEL SECTOR CONTROLS (Option B Compromise - Jan 2026)
# =============================================================================
#
# These controls enforce diversification at the PORTFOLIO level (active positions),
# not at the UNIVERSE level (candidate pool).
#
# Key distinction:
# - UNIVERSE: Can have 18 Technology stocks (35% of 60-stock universe)
# - PORTFOLIO: Can only deploy 3 Technology positions (40% of capital max)
#
# This allows:
# ✅ Large universe (more opportunities)
# ✅ Technology overweight in universe (reflects options liquidity reality)
# ✅ Strict risk management in portfolio (prevents concentration)
#
# Example scenario:
# - Universe has 18 Tech stocks, 10 Financial stocks, 8 Healthcare stocks
# - Scan finds 8 Tech candidates with IV Rank >50%
# - You deploy: MSFT, GOOGL, TSM (3 Tech positions = 40% capital)
# - Remaining 5 Tech candidates rejected (hit 3-position limit)
# - Deploy V (Financial), MRK (Healthcare) to diversify
#
# Result: 40% Tech exposure (within limits), but rejected 5 high-IV-Rank
# opportunities due to sector cap. This is INTENTIONAL - risk management
# takes priority over income maximization.
# =============================================================================

POSITION_SECTOR_LIMITS = {
    # STRICT LIMITS (enforced at trade deployment)
    # Maximum sector exposure across all open positions
    # Example: With $47K capital, max $18.8K in Technology sector
    "max_sector_exposure_pct": 0.40,  # 40% of total capital max per sector
    # Maximum number of concurrent positions per sector
    # Example: Can have at most 3 Technology positions open simultaneously
    "max_positions_per_sector": 3,  # 3 active positions max per sector
    # Minimum sector diversity in active portfolio
    # Example: Must have positions in at least 3 different sectors
    "min_active_sectors": 3,  # Must have positions in ≥3 different sectors
    # WARNING THRESHOLDS (trigger alerts but don't block trades)
    # Issue warning when approaching sector exposure limit
    "warn_sector_exposure_pct": 0.35,  # Warn at 35% sector exposure (before hitting 40% limit)
    # Issue warning when approaching position count limit
    "warn_positions_per_sector": 2,  # Warn at 2 positions per sector (before hitting 3-position limit)
}

# Rationale for 40% max sector exposure:
# - Allows deploying 3 positions at 15% each = 45% (slightly over, triggers warning)
# - During high-volatility environments (VIX >25), may temporarily exceed for premium capture
# - Prevents concentration >50% in any single sector
# - Balances opportunity (can take 3 Tech positions if IV Ranks are high) with risk

# Rationale for 3 max positions per sector:
# - With $47K capital and 15% position sizing = $7K per position
# - 3 positions = $21K = 45% sector exposure (manageable, diversified within sector)
# - Prevents over-concentration while allowing multiple high-IV-Rank names
# - Example: Can deploy MSFT, GOOGL, TSM simultaneously if all show >50% IV Rank

# Rationale for min 3 active sectors:
# - Ensures basic diversification even with small portfolio (4-6 positions)
# - Prevents "all Tech" or "all Financial" portfolios
# - Forces capital deployment across uncorrelated sectors

# =============================================================================
# IV RANK CALCULATION
# =============================================================================

IV_RANK_CONFIG = {
    "lookback_days": 252,  # 1 year of trading days
    "cache_expiry_days": 7,  # Refresh IV history weekly
    "iv_cache_file": "./iv_cache.json",
    # Real IV history: each scan appends today's ATM implied vol per ticker, so
    # IV Percentile is computed against a self-consistent IV series (not realized vol).
    "iv_history_file": "./iv_history.json",
    # Minimum daily IV observations before the true IV Percentile is trusted. Below
    # this the scanner falls back to a labeled HV proxy ("hv_proxy_provisional").
    "min_observations": 20,
}
