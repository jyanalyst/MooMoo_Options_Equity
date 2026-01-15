#!/usr/bin/env python3
"""
Bi-Weekly Universe Builder for Wheel Strategy
Fundamental screening and quality scoring for options income strategies.

This script fetches stocks from Finviz, applies fundamental filters,
calculates quality scores, and generates tier-based watchlists.
"""

import argparse
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import pandas as pd
import numpy as np

try:
    from finvizfinance.screener.custom import Custom
except ImportError:
    print("❌ ERROR: finvizfinance not installed. Run: pip install finvizfinance")
    exit(1)


# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

FINVIZ_FILTERS = {
    # Primary filters
    'Market Cap.': '+Large (over $10bln)',           # Tier 1 institutions only
    'P/E': 'Profitable (>0)',                        # No unprofitable companies
    'Operating Margin': 'Positive (>0%)',            # Must have operating profit
    'Debt/Equity': 'Under 1',                        # Conservative debt levels
    'Average Volume': 'Over 1M',                     # Ensures options liquidity
    'Country': 'USA',                                # US-listed only
    'Price': 'Over $15',                             # Min price for options

    # Enhanced quality filters
    'Return on Equity': 'Over +10%',                 # Capital efficiency
    'Current Ratio': 'Over 1.5',                     # Short-term liquidity
    'Gross Margin': 'Positive (>0%)',                # Pricing power
    'InstitutionalOwnership': 'Over 20%',            # Smart money validation
}

TIER_PRICE_RANGES = {
    'tier1': {'min': 15.0, 'max': 70.0},
    'tier2': {'min': 70.0, 'max': 150.0},
    'tier3': {'min': 150.0, 'max': float('inf')},
}

QUALITY_WEIGHTS = {
    'operating_margin': 0.30,  # 30%
    'roe': 0.25,               # 25%
    'current_ratio': 0.15,     # 15%
    'debt_equity': 0.10,       # 10% (inverse)
    'volume_percentile': 0.20, # 20%
}

DEFAULT_LIMITS = {
    'tier1_limit': 20,
    'tier2_limit': 20,
    'tier3_limit': 20,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_banner():
    """Display ASCII art banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           WHEEL UNIVERSE BUILDER v1.0                        ║
║     Fundamental Screening for Quality Stock Universe         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_summary(df: pd.DataFrame, tiers: Tuple[List[str], List[str], List[str]],
                 total_screened: int, total_passed: int):
    """Print build summary."""
    tier1, tier2, tier3 = tiers

    print("""
╔══════════════════════════════════════════════════════════════╗
║                    BUILD COMPLETE                             ║
╚══════════════════════════════════════════════════════════════╝
""")
    print(f"\nUniverse refresh complete!")
    print(f"Total quality stocks: {len(tier1) + len(tier2) + len(tier3)} (20 per tier)")
    next_refresh = datetime.now() + timedelta(days=14)
    print(f"Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d')}")
    print("\nTo test the new universe:")
    print("  python main.py wheel --tier 1")


def format_ticker_line(ticker: str, name: str, sector: str, score: float, earnings: str = None) -> str:
    """Format a single ticker line with company info, score, and earnings date."""
    company_short = name[:30] if len(name) > 30 else name

    # Format earnings date if available
    earnings_str = ""
    if earnings and earnings != '-':
        # Parse finviz earnings format (could be "Feb 18 AMC" or "2026-02-18")
        try:
            # Clean up finviz format - take first two parts (month day)
            earnings_parts = str(earnings).split()
            if len(earnings_parts) >= 2:
                earnings_clean = f"{earnings_parts[0]} {earnings_parts[1]}"
                earnings_str = f" | Earnings: {earnings_clean}"
        except:
            if earnings and str(earnings).strip():
                earnings_str = f" | Earnings: {str(earnings).strip()}"

    return f'    "{ticker}",  # {company_short} - {sector} | Score: {score:.1f}{earnings_str}'


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Build fundamental quality stock universe for Wheel Strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python universe_builder.py                    # Default run (overwrites universe.py)
  python universe_builder.py --dry-run          # Preview without writing
  python universe_builder.py --output test.py   # Write to test file
  python universe_builder.py --verbose          # Show all tickers considered
  python universe_builder.py --tier1-limit 15   # Custom tier limits
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview results without writing to file'
    )

    parser.add_argument(
        '--output',
        default='universe.py',
        help='Output filename (default: universe.py)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress and all tickers considered'
    )

    parser.add_argument(
        '--tier1-limit',
        type=int,
        default=20,
        help='Max stocks for Tier 1 (default: 20)'
    )

    parser.add_argument(
        '--tier2-limit',
        type=int,
        default=20,
        help='Max stocks for Tier 2 (default: 20)'
    )

    parser.add_argument(
        '--tier3-limit',
        type=int,
        default=20,
        help='Max stocks for Tier 3 (default: 20)'
    )

    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup creation (not recommended)'
    )

    return parser.parse_args()


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_with_retry(screener, columns=None, max_retries: int = 3) -> pd.DataFrame:
    """
    Fetch data from finviz with exponential backoff retry.

    Args:
        screener: Finviz screener instance
        max_retries: Maximum number of retry attempts

    Returns:
        DataFrame with screening results
    """
    for attempt in range(max_retries):
        try:
            if columns:
                df = screener.screener_view(verbose=0, columns=columns)
            else:
                df = screener.screener_view(verbose=0)
            return df
        except Exception as e:
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"⚠️  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("❌ CRITICAL: Failed to fetch data after 3 attempts")
                print("   Check internet connection or finviz.com status")
                raise


def fetch_stocks_from_finviz() -> pd.DataFrame:
    """
    Fetch stocks from Finviz using predefined filters and custom columns.

    Returns:
        DataFrame with screened stocks including financial metrics
    """
    print("[Step 1/7] Fetching stocks from Finviz...")

    screener = Custom()
    screener.set_filter(filters_dict=FINVIZ_FILTERS)

    # Explicitly request financial columns
    # Based on finvizfinance constants, these are the key financial metrics
    columns = [
        0,   # No.
        1,   # Ticker
        2,   # Company
        3,   # Sector
        4,   # Industry
        6,   # Market Cap
        7,   # P/E
        33,  # Return on Equity (ROE)
        35,  # Current Ratio
        38,  # Total Debt/Equity
        39,  # Gross Margin
        40,  # Operating Margin
        63,  # Average Volume
        65,  # Price
        68,  # Earnings Date
    ]

    df = fetch_with_retry(screener, columns=columns)
    print(f"Stocks fetched from Finviz: {len(df)}")

    # Debug: Show applied filters
    print("Applied filters:")
    for key, value in FINVIZ_FILTERS.items():
        print(f"  ✓ {key}: {value}")

    # Debug: Show fetched columns
    print("\nFetched columns:")
    for col in df.columns:
        print(f"  • {col}")

    return df


# =============================================================================
# POST-SCREENING FILTERS
# =============================================================================

def apply_post_screening_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply additional filters that can't be done via Finviz API.

    Args:
        df: Raw screening results

    Returns:
        Filtered DataFrame
    """
    print("\n[Step 2/7] Applying post-screening filters...")

    original_count = len(df)

    # Convert percentage strings to floats for filtering
    df = df.copy()

    # Clean numeric columns - properly handle percentages
    numeric_cols = ['Price', 'Average Volume', 'Market Cap', 'P/E']
    percentage_cols = ['Operating Margin', 'Return on Equity', 'Current Ratio', 'Total Debt/Equity', 'Gross Margin']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('[%,]', '', regex=True),
                                   errors='coerce')

    for col in percentage_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', '', regex=False),
                                   errors='coerce')

    # Biotech exclusion: Industry contains "Biotechnology" AND Sector is "Healthcare"
    biotech_mask = (
        df['Industry'].str.contains('Biotechnology', na=False, case=False) &
        (df['Sector'] == 'Healthcare')
    )
    df = df[~biotech_mask]
    biotech_excluded = biotech_mask.sum()
    if biotech_excluded > 0:
        print(f"  ✗ Excluded {biotech_excluded} biotech stocks (binary FDA risk)")

    # Max price cap: exclude stocks priced > $300
    price_cap_mask = df['Price'] > 300
    df = df[~price_cap_mask]
    price_excluded = price_cap_mask.sum()
    if price_excluded > 0:
        print(f"  ✗ Excluded {price_excluded} stocks priced >$300")

    # IPO filter (optional): exclude stocks with IPO date < 1 year ago
    # This would require yfinance, skipping for now to keep dependencies minimal

    final_count = len(df)
    print(f"Quality stocks remaining: {final_count}")

    return df


# =============================================================================
# QUALITY SCORING FUNCTIONS
# =============================================================================

def calculate_quality_scores_percentile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate quality scores using percentile ranking within the dataset.
    This automatically creates proper score distribution regardless of cohort size.

    Stocks are ranked relative to each other, not against absolute thresholds.
    This provides differentiation even when all stocks are high quality.

    Args:
        df: DataFrame with financial metrics

    Returns:
        DataFrame with quality scores added
    """
    df = df.copy()

    # Operating Margin: 0-30 points based on percentile rank
    # Finviz returns this as 'Oper M' (abbreviated)
    if 'Oper M' in df.columns:
        df['OM_Score'] = df['Oper M'].rank(pct=True, na_option='bottom') * 30
    else:
        print("  ⚠️  WARNING: 'Oper M' column not found")
        df['OM_Score'] = 0

    # ROE: 0-25 points based on percentile rank
    # Finviz returns this as 'ROE' (matches!)
    if 'ROE' in df.columns:
        df['ROE_Score'] = df['ROE'].rank(pct=True, na_option='bottom') * 25
    else:
        print("  ⚠️  WARNING: 'ROE' column not found")
        df['ROE_Score'] = 0

    # Current Ratio: 0-15 points based on percentile rank
    # Finviz returns this as 'Curr R' (abbreviated)
    if 'Curr R' in df.columns:
        df['CR_Score'] = df['Curr R'].rank(pct=True, na_option='bottom') * 15
    else:
        print("  ⚠️  WARNING: 'Curr R' column not found")
        df['CR_Score'] = 0

    # Debt/Equity: 0-10 points (INVERSE percentile - lower debt = higher score)
    # Finviz returns this as 'Debt/Eq' (abbreviated)
    if 'Debt/Eq' in df.columns:
        df['DE_Score'] = (1 - df['Debt/Eq'].rank(pct=True, na_option='top')) * 10
    else:
        print("  ⚠️  WARNING: 'Debt/Eq' column not found")
        df['DE_Score'] = 0

    # Gross Margin: Bonus 0-5 points based on percentile rank
    # Finviz returns this as 'Gross M' (abbreviated)
    if 'Gross M' in df.columns:
        df['GM_Score'] = df['Gross M'].rank(pct=True, na_option='bottom') * 5
    else:
        print("  ⚠️  WARNING: 'Gross M' column not found")
        df['GM_Score'] = 0

    # Sum all components (max 85 points before volume)
    df['Quality_Score'] = (
        df['OM_Score'].fillna(0) +
        df['ROE_Score'].fillna(0) +
        df['CR_Score'].fillna(0) +
        df['DE_Score'].fillna(0) +
        df['GM_Score'].fillna(0)
    )

    return df


def add_volume_percentile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate volume percentile rank and add to quality score.
    Volume gets 15 points (reduced from 20 to make room for gross margin).
    """
    # Finviz returns this as 'Avg Volume' (abbreviated)
    if 'Avg Volume' in df.columns and len(df) > 0:
        df = df.copy()
        df['Volume_Score'] = df['Avg Volume'].rank(pct=True, na_option='bottom') * 15
        df['Quality_Score'] = df['Quality_Score'] + df['Volume_Score']
    else:
        print("  ⚠️  WARNING: 'Avg Volume' column not found")
        df['Volume_Score'] = 0

    return df


# =============================================================================
# TIER ASSIGNMENT FUNCTIONS
# =============================================================================

def assign_tiers(df: pd.DataFrame, limits: Dict[str, int]) -> Tuple[List[str], List[str], List[str]]:
    """
    Assign stocks to tiers based on price ranges and quality scores.

    Args:
        df: DataFrame with quality scores
        limits: Max stocks per tier

    Returns:
        Tuple of (tier1_list, tier2_list, tier3_list)
    """
    print("\n[Step 4/7] Assigning to tiers by price...")

    tier1_candidates = df[
        (df['Price'] >= TIER_PRICE_RANGES['tier1']['min']) &
        (df['Price'] < TIER_PRICE_RANGES['tier1']['max'])
    ].sort_values('Quality_Score', ascending=False)

    tier2_candidates = df[
        (df['Price'] >= TIER_PRICE_RANGES['tier2']['min']) &
        (df['Price'] < TIER_PRICE_RANGES['tier2']['max'])
    ].sort_values('Quality_Score', ascending=False)

    tier3_candidates = df[
        df['Price'] >= TIER_PRICE_RANGES['tier3']['min']
    ].sort_values('Quality_Score', ascending=False)

    print(f"  Candidates per tier (before limiting):")
    print(f"    Tier 1 (${TIER_PRICE_RANGES['tier1']['min']:.0f}-{TIER_PRICE_RANGES['tier1']['max']:.0f}):   {len(tier1_candidates)} stocks → Top {limits['tier1_limit']} selected")
    print(f"    Tier 2 (${TIER_PRICE_RANGES['tier2']['min']:.0f}-{TIER_PRICE_RANGES['tier3']['min']:.0f}):  {len(tier2_candidates)} stocks → Top {limits['tier2_limit']} selected")
    print(f"    Tier 3 (${TIER_PRICE_RANGES['tier3']['min']:.0f}+):    {len(tier3_candidates)} stocks → Top {limits['tier3_limit']} selected")

    # Take top N from each tier
    tier1_tickers = tier1_candidates.head(limits['tier1_limit'])['Ticker'].tolist()
    tier2_tickers = tier2_candidates.head(limits['tier2_limit'])['Ticker'].tolist()
    tier3_tickers = tier3_candidates.head(limits['tier3_limit'])['Ticker'].tolist()

    print("\n  Final tier composition:")
    print(f"    ✓ WHEEL_TIER_1: {len(tier1_tickers)} stocks (avg score: {tier1_candidates.head(limits['tier1_limit'])['Quality_Score'].mean():.1f})")
    print(f"    ✓ WHEEL_TIER_2: {len(tier2_tickers)} stocks (avg score: {tier2_candidates.head(limits['tier2_limit'])['Quality_Score'].mean():.1f})")
    print(f"    ✓ WHEEL_TIER_3: {len(tier3_tickers)} stocks (avg score: {tier3_candidates.head(limits['tier3_limit'])['Quality_Score'].mean():.1f})")

    return tier1_tickers, tier2_tickers, tier3_tickers


# =============================================================================
# FILE MANAGEMENT FUNCTIONS
# =============================================================================


# =============================================================================
# FILE MANAGEMENT FUNCTIONS
# =============================================================================

def read_existing_universe() -> Dict[str, str]:
    """
    Read existing universe.py and extract sections to preserve.

    Returns:
        Dict with preserved content sections
    """
    try:
        with open('universe.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("⚠️  universe.py not found, will create from scratch")
        return {}

    preserved = {}

    # Extract VOL_HARVEST_UNIVERSE
    start = content.find('VOL_HARVEST_UNIVERSE = [')
    if start != -1:
        end = content.find(']', start) + 1
        preserved['vol_harvest'] = content[start:end]

    # Extract EXCLUDED_TICKERS
    start = content.find('EXCLUDED_TICKERS = [')
    if start != -1:
        end = content.find(']', start) + 1
        preserved['excluded'] = content[start:end]

    # Extract helper functions
    functions_start = content.find('# =============================================================================\n# HELPER FUNCTIONS\n# =============================================================================')
    if functions_start != -1:
        preserved['functions'] = content[functions_start:]

    return preserved


def generate_universe_content(tiers: Tuple[List[str], List[str], List[str]],
                            preserved: Dict[str, str], stats: Dict[str, int],
                            df: pd.DataFrame) -> str:
    """
    Generate the complete universe.py content.

    Args:
        tiers: Tuple of (tier1, tier2, tier3) ticker lists
        preserved: Dict of content to preserve
        stats: Statistics for header

    Returns:
        Complete file content as string
    """
    tier1, tier2, tier3 = tiers
    now = datetime.now()
    next_refresh = now + timedelta(days=14)

    # Create lookup dict for company info
    company_lookup = {}
    for _, row in df.iterrows():
        ticker = row.get('Ticker', '')
        if ticker:
            company_lookup[ticker] = {
                'company': row.get('Company', 'Unknown Company'),
                'sector': row.get('Sector', 'Unknown Sector'),
                'score': row.get('Quality_Score', 0.0),
                'earnings': row.get('Earnings Date', None)  # Fixed column name
            }

    # Create tier content with real company info and scores
    def create_tier_list(tickers, tier_num):
        lines = [f"# $15-{70 if tier_num == 1 else 150 if tier_num == 2 else '150+'} range - {len(tickers)} stocks - {'START HERE' if tier_num == 1 else 'AFTER 6 MONTHS EXPERIENCE' if tier_num == 2 else 'CAPITAL >$150K'}"]
        for ticker in tickers:
            info = company_lookup.get(ticker, {
                'company': 'Unknown Company',
                'sector': 'Unknown Sector',
                'score': 0.0,
                'earnings': None
            })
            lines.append(format_ticker_line(
                ticker,
                info['company'],
                info['sector'],
                info['score'],
                info.get('earnings')  # ← ADD THIS
            ))
        return '\n'.join(lines)

    content = f'''"""
Pre-defined stock universes for Options Scanner
AUTO-GENERATED by universe_builder.py on {now.strftime('%Y-%m-%d %H:%M:%S')}
Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d')}

Fundamental screening criteria applied:
- Market Cap >$10B
- P/E >0 (Profitable)
- Operating Margin >0%
- Debt/Equity <1.0
- ROE >10%
- Current Ratio >1.5
- Gross Margin >0%
- Institutional Ownership >20%
- Avg Volume >1M shares/day
- Excluded: Biotech stocks

Quality scoring method: PERCENTILE-BASED RANKING
Stocks ranked relative to each other within filtered cohort:
- Operating Margin: 30% weight (percentile rank)
- ROE: 25% weight (percentile rank)
- Volume: 15% weight (percentile rank)
- Current Ratio: 15% weight (percentile rank)
- Debt/Equity: 10% weight (inverse percentile - lower is better)
- Gross Margin: 5% weight (percentile rank bonus)
Total possible: 100 points

Stocks screened: {stats['screened']}
Quality stocks found: {stats['passed']}
Top 20 selected per tier by quality score
"""

# =============================================================================
# WHEEL STRATEGY UNIVERSE
# Quality stocks you would genuinely own at the strike price
# Pre-screened for: Market Cap >$10B, profitable, strong fundamentals
# =============================================================================

WHEEL_TIER_1 = [
{create_tier_list(tier1, 1)}
]

WHEEL_TIER_2 = [
{create_tier_list(tier2, 2)}
]

WHEEL_TIER_3 = [
{create_tier_list(tier3, 3)}
]

# Combined Wheel universe - use based on your capital tier
WHEEL_UNIVERSE = WHEEL_TIER_1 + WHEEL_TIER_2  # Tier 3 excluded by default (capital intensive)


# =============================================================================
# VOLATILITY HARVESTING UNIVERSE
# [PRESERVED FROM EXISTING FILE - DO NOT MODIFY]
# =============================================================================

{preserved.get('vol_harvest', 'VOL_HARVEST_UNIVERSE = [\n    # Add your vol harvest stocks here\n]')}


# =============================================================================
# EXCLUDED TICKERS
# [PRESERVED FROM EXISTING FILE - DO NOT MODIFY]
# =============================================================================

{preserved.get('excluded', 'EXCLUDED_TICKERS = [\n    # Biotech with pending FDA decisions (add as needed)\n    # M&A targets (add as needed)\n    # Delisting candidates (add as needed)\n]')}


# =============================================================================
# HELPER FUNCTIONS
# [PRESERVED FROM EXISTING FILE - DO NOT MODIFY]
# =============================================================================

{preserved.get('functions', '''
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
''')}
'''

    return content


def write_universe_file(content: str, output_path: str, backup: bool = True):
    """
    Write content to universe file with optional backup.

    Args:
        content: File content to write
        output_path: Path to write file
        backup: Whether to create backup
    """
    if backup and output_path == 'universe.py':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'universe.py.backup.{timestamp}'
        try:
            shutil.copy2('universe.py', backup_path)
            print(f"✓ Backup created: {backup_path}")
        except FileNotFoundError:
            print("⚠️  No existing universe.py to backup")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ {output_path} written ({len(content.splitlines())} lines)")


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_results(tier1: List[str], tier2: List[str], tier3: List[str]) -> bool:
    """
    Validate tier results before writing.

    Args:
        tier1, tier2, tier3: Ticker lists

    Returns:
        True if validation passes
    """
    print("\n[Step 5/7] Validation checks...")

    issues = []

    if len(tier1) < 10:
        issues.append(f"⚠️  Tier 1 only has {len(tier1)} stocks (expected 20)")

    if len(tier2) < 10:
        issues.append(f"⚠️  Tier 2 only has {len(tier2)} stocks (expected 20)")

    if len(tier3) < 5:
        issues.append(f"⚠️  Tier 3 only has {len(tier3)} stocks (expected 20)")

    # Check for duplicates across tiers
    all_tickers = tier1 + tier2 + tier3
    if len(all_tickers) != len(set(all_tickers)):
        issues.append("❌ CRITICAL: Duplicate tickers found across tiers!")

    if issues:
        print("\n".join(issues))
        response = input("\nProceed anyway? (y/n): ")
        return response.lower() == 'y'

    print("  ✓ All tiers meet minimum thresholds")
    print("  ✓ No duplicate tickers found")
    print("  ✓ All tickers have valid scores")
    return True


def check_minimum_results(df: pd.DataFrame):
    """
    Warn if screening returns too few results.

    Args:
        df: Filtered results
    """
    if len(df) < 15:  # Reduced from 60 - need at least 5 per tier
        print(f"\n⚠️  WARNING: Only {len(df)} stocks passed screening")
        print("   Expected at least 15 stocks minimum (5 per tier)")
        print("   Consider relaxing filters or check if finviz is accessible")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted. No changes made to universe.py")
            exit(0)
    elif len(df) < 60:
        print(f"\n⚠️  NOTE: {len(df)} stocks passed screening (target: 60)")
        print("   This may result in fewer than 20 stocks per tier")
        print("   Consider relaxing filters in FINVIZ_FILTERS if more stocks needed")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main execution function."""
    args = parse_arguments()
    print_banner()

    # Step 1: Fetch data
    df = fetch_stocks_from_finviz()
    total_screened = len(df)

    # Step 2: Apply post-screening filters
    df = apply_post_screening_filters(df)
    total_passed = len(df)

    check_minimum_results(df)

    # Add numeric market cap column for percentile calculations
    df['Market Cap Numeric'] = df['Market Cap'].apply(lambda x: float(x.replace('B', '')) * 1000 if isinstance(x, str) and 'B' in x else (float(x.replace('M', '')) if isinstance(x, str) and 'M' in x else float(x)))

    # Step 3: Calculate quality scores using percentile ranking
    print("\n[Step 3/7] Calculating quality scores (percentile-based)...")
    print("  Operating Margin (30% weight)")
    print("  ROE (25% weight)")
    print("  Current Ratio (15% weight)")
    print("  Volume (15% weight)")
    print("  Debt/Equity inverse (10% weight)")
    print("  Gross Margin bonus (5% weight)")
    print("\n  Note: Stocks ranked relative to each other, not absolute thresholds")

    # Calculate scores based on percentile rankings
    df = calculate_quality_scores_percentile(df)
    df = add_volume_percentile(df)

    # Debug: Show sample scores and underlying metrics
    if len(df) >= 3:
        print("\n[DEBUG] Sample stocks with financial metrics:")
        # Use abbreviated column names that finviz actually returns
        debug_cols = ['Ticker', 'Oper M', 'ROE', 'Curr R', 'Debt/Eq', 'Quality_Score']
        available_cols = [col for col in debug_cols if col in df.columns]
        print(df[available_cols].head(3).to_string(index=False))

    # Debug: Show earnings dates if available
    if 'Earnings Date' in df.columns:
        print("\n[DEBUG] Upcoming earnings:")
        earnings_df = df[['Ticker', 'Earnings Date']].copy()
        earnings_df = earnings_df[earnings_df['Earnings Date'].notna()]
        earnings_df = earnings_df[earnings_df['Earnings Date'] != '-']
        if len(earnings_df) > 0:
            print(earnings_df.to_string(index=False))
        else:
            print("  No earnings dates found in data")

    # Show score distribution with more granular bins
    score_bins = pd.cut(df['Quality_Score'], bins=[0, 40, 50, 60, 70, 80, 90, 100])
    score_counts = df.groupby(score_bins).size()
    print("\nScore distribution:")
    for bin_range, count in score_counts.items():
        label = f"{bin_range.left:.0f}-{bin_range.right:.0f}"
        desc_dict = {
            "0-40": "below average",
            "40-50": "average",
            "50-60": "above average",
            "60-70": "good",
            "70-80": "very good",
            "80-90": "excellent",
            "90-100": "elite"
        }
        desc = desc_dict.get(label, "")
        print(f"  {label}: {count} stocks ({desc})")

    # Step 4: Assign tiers
    limits = {
        'tier1_limit': args.tier1_limit,
        'tier2_limit': args.tier2_limit,
        'tier3_limit': args.tier3_limit,
    }
    tiers = assign_tiers(df, limits)

    # Step 5: Validate
    if not validate_results(*tiers):
        print("Validation failed. Aborting.")
        exit(1)

    # Step 6: Preserve existing content
    print("\n[Step 6/7] Preserving existing content...")
    preserved = read_existing_universe()
    print(f"  ✓ VOL_HARVEST_UNIVERSE ({len(preserved.get('vol_harvest', '').split(',')) if 'vol_harvest' in preserved else 0} stocks)")
    print(f"  ✓ EXCLUDED_TICKERS ({len(preserved.get('excluded', '').split(',')) if 'excluded' in preserved else 0} stocks)")
    print(f"  ✓ Helper functions ({len([line for line in preserved.get('functions', '').splitlines() if line.strip().startswith('def ')]) if 'functions' in preserved else 0} functions)")

    # Step 7: Generate and write file
    print("\n[Step 7/7] Writing to universe.py...")
    stats = {'screened': total_screened, 'passed': total_passed}
    content = generate_universe_content(tiers, preserved, stats, df)

    if not args.dry_run:
        write_universe_file(content, args.output, backup=not args.no_backup)
    else:
        print("✓ Dry run complete - no files written")

    # Summary
    print_summary(df, tiers, total_screened, total_passed)


if __name__ == "__main__":
    main()
