"""
Pre-defined stock universes for Options Scanner
Curated lists of liquid US stocks pre-vetted for fundamental quality (Wheel) 
or high-IV characteristics (Vol Harvest)

These lists bypass the need for API-based fundamental screening.
Edit these lists to add/remove tickers based on your analysis.
"""

# =============================================================================
# WHEEL STRATEGY UNIVERSE
# Quality stocks you would genuinely own at the strike price
# Pre-screened for: Market Cap >$10B, profitable or path to profit, liquid options
# =============================================================================

WHEEL_TIER_1 = [
    # $15-70 range - Start here
    # Tech
    "INTC",   # Intel - turnaround play, foundry story
    "PLTR",   # Palantir - AI/government contracts
    "SNAP",   # Snap - social media, advertising recovery
    "HOOD",   # Robinhood - retail trading platform
    "SOFI",   # SoFi - fintech, banking charter
    "PATH",   # UiPath - automation software
    "RBLX",   # Roblox - gaming platform
    
    # Consumer/Retail
    "F",      # Ford - EV transition, dividends
    "GM",     # GM - EV transition
    "AAL",    # American Airlines - travel recovery
    "DAL",    # Delta Airlines - premium carrier
    "UAL",    # United Airlines
    "CCL",    # Carnival - cruise recovery
    "RCL",    # Royal Caribbean
    "NIO",    # NIO - Chinese EV
    "RIVN",   # Rivian - EV trucks
    "LCID",   # Lucid - luxury EV
    
    # Financials
    "C",      # Citigroup - major bank
    "WFC",    # Wells Fargo
    "BAC",    # Bank of America
    "SCHW",   # Schwab - brokerage
    
    # Energy/Materials
    "CLF",    # Cleveland-Cliffs - steel
    "FCX",    # Freeport-McMoRan - copper
    
    # Healthcare
    "PFE",    # Pfizer
]

WHEEL_TIER_2 = [
    # $70-150 range - After 6 months experience
    # Tech
    "AMD",    # AMD - AI/datacenter chips
    "UBER",   # Uber - mobility/delivery
    "LYFT",   # Lyft - rideshare
    "PYPL",   # PayPal - fintech
    "XYZ",    # Block (formerly Square) - fintech
    "ABNB",   # Airbnb - travel platform
    "SHOP",   # Shopify - e-commerce
    "CRWD",   # CrowdStrike - cybersecurity
    "ZS",     # Zscaler - cybersecurity
    "DDOG",   # Datadog - observability
    "NET",    # Cloudflare - edge computing
    "MDB",    # MongoDB - database
    "SNOW",   # Snowflake - data cloud
    
    # Consumer
    "DIS",    # Disney - entertainment
    "SBUX",   # Starbucks
    "NKE",    # Nike
    "TGT",    # Target
    
    # Crypto-adjacent
    "COIN",   # Coinbase - crypto exchange
    "MSTR",   # MicroStrategy - Bitcoin treasury
]

WHEEL_TIER_3 = [
    # $150+ range - Capital >$150K
    # Mega-cap tech
    "TSLA",   # Tesla - EV/energy
    "META",   # Meta - social media/metaverse
    "NVDA",   # Nvidia - AI chips
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NFLX",   # Netflix
    "AVGO",   # Broadcom - semiconductors
    "CRM",    # Salesforce
]

# Combined Wheel universe - use based on your capital tier
WHEEL_UNIVERSE = WHEEL_TIER_1 + WHEEL_TIER_2  # Tier 3 excluded by default (capital intensive)


# =============================================================================
# VOLATILITY HARVESTING UNIVERSE
# High-IV names for iron condors - you NEVER want to own these
# Pre-screened for: History of IV spikes, squeeze candidates, meme potential
# =============================================================================

VOL_HARVEST_UNIVERSE = [
    # Meme stocks / high retail interest
    "GME",    # GameStop - original meme stock
    "AMC",    # AMC Entertainment - meme stock
    "KOSS",   # Koss - headphones, squeeze history
    
    # Crypto miners / high correlation to BTC
    "MARA",   # Marathon Digital - Bitcoin miner
    "RIOT",   # Riot Platforms - Bitcoin miner
    "CLSK",   # CleanSpark - Bitcoin miner
    "HUT",    # Hut 8 Mining
    "BITF",   # Bitfarms
    
    # High short interest / squeeze potential
    "CVNA",   # Carvana - high short interest
    "UPST",   # Upstart - AI lending, volatile
    "AFRM",   # Affirm - BNPL, volatile
    "PLUG",   # Plug Power - hydrogen
    "FCEL",   # FuelCell Energy
    
    # Other high-IV names
    "HOOD",   # Robinhood (appears in both - context dependent)
    "CLOV",   # Clover Health
    "IONQ",   # IonQ - quantum computing
    "SMCI",   # Super Micro Computer - AI servers
]


# =============================================================================
# EXCLUDED TICKERS
# Never trade these - binary risk, illiquid, or structural issues
# =============================================================================

EXCLUDED_TICKERS = [
    # Biotech with pending FDA decisions (add as needed)
    # M&A targets (add as needed)
    # Delisting candidates (add as needed)
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_wheel_universe(tier: int = 2) -> list:
    """
    Get Wheel universe based on capital tier
    Tier 1: $15-70 stocks only
    Tier 2: $15-150 stocks (Tier 1 + Tier 2)
    Tier 3: All stocks including $150+ (requires >$150K capital)
    """
    if tier == 1:
        return WHEEL_TIER_1
    elif tier == 2:
        return WHEEL_TIER_1 + WHEEL_TIER_2
    elif tier == 3:
        return WHEEL_TIER_1 + WHEEL_TIER_2 + WHEEL_TIER_3
    else:
        return WHEEL_TIER_1 + WHEEL_TIER_2


def get_vol_harvest_universe() -> list:
    """Get Volatility Harvesting universe"""
    return [t for t in VOL_HARVEST_UNIVERSE if t not in EXCLUDED_TICKERS]


def add_to_excluded(ticker: str):
    """Add a ticker to excluded list (runtime only)"""
    if ticker not in EXCLUDED_TICKERS:
        EXCLUDED_TICKERS.append(ticker)


def format_moomoo_symbol(ticker: str) -> str:
    """Convert ticker to MooMoo format (e.g., 'AAPL' -> 'US.AAPL')"""
    if not ticker.startswith("US."):
        return f"US.{ticker}"
    return ticker


def strip_moomoo_prefix(symbol: str) -> str:
    """Convert MooMoo format to plain ticker (e.g., 'US.AAPL' -> 'AAPL')"""
    if symbol.startswith("US."):
        return symbol[3:]
    return symbol
