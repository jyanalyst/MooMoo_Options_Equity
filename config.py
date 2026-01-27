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
# IV RANK CALCULATION
# =============================================================================

IV_RANK_CONFIG = {
    "lookback_days": 252,  # 1 year of trading days
    "cache_expiry_days": 7,  # Refresh IV history weekly
    "iv_cache_file": "./iv_cache.json",
}
