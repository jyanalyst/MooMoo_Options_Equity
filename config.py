"""
Configuration settings for Options Scanner
Strategy parameters derived from Wheel Strategy Guide
"""

# =============================================================================
# FINANCIAL MODELING PREP API SETTINGS
# =============================================================================

FMP_API_KEY = "SUmg1Fkg9IxxPrCGF8HFP3sdLLl35IUk"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

# =============================================================================
# MOOMOO API SETTINGS
# =============================================================================

MOOMOO_HOST = "127.0.0.1"
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
    "volume_min": 50,  # ADJUSTED: Minimum volume required (reduced for OR logic with OI)
    "open_interest_min": 500,  # NEW: Alternative liquidity check (Open Interest)
    "bid_ask_spread_max_pct": 0.50,  # TEMPORARILY RELAXED FOR DEBUGGING (50% of mid)
    
    # Premium target
    "premium_pct_of_strike_min": 0.001,  # TEMPORARILY RELAXED FOR DEBUGGING (0.1% minimum)
    
    # Earnings buffer
    "earnings_buffer_days": 7,

    # Earnings validation (CONSERVATIVE MODE - UPDATED)
    "allow_unverified_earnings": False,  # Reject stocks with missing earnings data (fail-safe default)

    # Term structure (contango = favorable)
    "term_structure_check": True,
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
    "max_positions_per_sector": 3,    # 3 active positions max per sector

    # Minimum sector diversity in active portfolio
    # Example: Must have positions in at least 3 different sectors
    "min_active_sectors": 3,          # Must have positions in ≥3 different sectors

    # WARNING THRESHOLDS (trigger alerts but don't block trades)

    # Issue warning when approaching sector exposure limit
    "warn_sector_exposure_pct": 0.35,  # Warn at 35% sector exposure (before hitting 40% limit)

    # Issue warning when approaching position count limit
    "warn_positions_per_sector": 2,    # Warn at 2 positions per sector (before hitting 3-position limit)
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
}
