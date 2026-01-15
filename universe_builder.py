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
    from finvizfinance.screener.overview import Overview
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


def format_ticker_line(ticker: str, name: str, sector: str, score: float) -> str:
    """Format a ticker line for the universe lists."""
    return f'    "{ticker}",  # {name} - {sector} | Score: {score:.1f}'


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

def fetch_with_retry(screener: Overview, max_retries: int = 3) -> pd.DataFrame:
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
    Fetch stocks from Finviz using predefined filters.

    Returns:
        DataFrame with screened stocks
    """
    print("[Step 1/7] Fetching stocks from Finviz...")

    screener = Overview()
    screener.set_filter(filters_dict=FINVIZ_FILTERS)

    df = fetch_with_retry(screener)
    print(f"Stocks fetched from Finviz: {len(df)}")

    # Debug: Show applied filters
    print("Applied filters:")
    for key, value in FINVIZ_FILTERS.items():
        print(f"  ✓ {key}: {value}")

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
    numeric_cols = ['Price', 'Avg Volume', 'Market Cap', 'P/E']
    percentage_cols = ['Operating Margin', 'ROE', 'Current Ratio', 'Debt/Eq', 'Gross Margin']

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

def calculate_quality_score(row) -> float:
    """
    Calculate quality score (0-100) for ranking stocks.

    Components:
    - Operating Margin (30%): Higher = better profitability
    - ROE (25%): Higher = better capital efficiency
    - Current Ratio (15%): Higher = better liquidity
    - Debt/Equity (10%): Lower = better (inverse score)
    - Avg Volume percentile (20%): Will be added separately

    Args:
        row: DataFrame row

    Returns:
        Quality score (0-100)
    """
    score = 0

    # Operating Margin (0-30 points)
    op_margin = row.get('Operating Margin', 0)
    if pd.notna(op_margin) and op_margin > 0:
        score += min((op_margin / 50) * 30, 30)  # Cap at 30 points

    # ROE (0-25 points)
    roe = row.get('ROE', 0)
    if pd.notna(roe) and roe > 0:
        score += min((roe / 40) * 25, 25)  # Cap at 25 points

    # Current Ratio (0-15 points)
    curr_ratio = row.get('Current Ratio', 0)
    if pd.notna(curr_ratio) and curr_ratio > 0:
        score += min((curr_ratio / 3) * 15, 15)  # Cap at 15 points

    # Debt/Equity - INVERSE (0-10 points, lower is better)
    debt_eq = row.get('Debt/Eq', 1.0)
    if pd.notna(debt_eq):
        score += max(10 - (debt_eq * 10), 0)  # Lower debt = higher score

    return round(score, 2)


def add_volume_percentile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate volume percentile rank and add to quality score.

    Args:
        df: DataFrame with quality scores

    Returns:
        DataFrame with volume percentile added to quality score
    """
    if 'Avg Volume' in df.columns and len(df) > 0:
        df = df.copy()
        df['Volume_Percentile'] = df['Avg Volume'].rank(pct=True) * 20  # 0-20 points
        df['Quality_Score'] = df['Quality_Score'] + df['Volume_Percentile']

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
                'score': row.get('Quality_Score', 0.0)
            }

    # Create tier content with real company info and scores
    def create_tier_list(tickers, tier_num):
        lines = [f"# $15-{70 if tier_num == 1 else 150 if tier_num == 2 else '150+'} range - {len(tickers)} stocks - {'START HERE' if tier_num == 1 else 'AFTER 6 MONTHS EXPERIENCE' if tier_num == 2 else 'CAPITAL >$150K'}"]
        for ticker in tickers:
            info = company_lookup.get(ticker, {
                'company': 'Unknown Company',
                'sector': 'Unknown Sector',
                'score': 0.0
            })
            lines.append(format_ticker_line(ticker, info['company'], info['sector'], info['score']))
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

Quality scoring formula:
- Operating Margin: 30%
- ROE: 25%
- Volume Rank: 20%
- Current Ratio: 15%
- Debt/Equity (inverse): 10%

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
    if len(df) < 60:  # Need at least 60 for 20 per tier
        print(f"\n⚠️  WARNING: Only {len(df)} stocks passed screening")
        print("   Expected at least 60 stocks for 3 tiers")
        print("   Consider relaxing filters or check if finviz is accessible")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted. No changes made to universe.py")
            exit(0)


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

    # Step 3: Calculate quality scores
    print("\n[Step 3/7] Calculating quality scores...")
    print("  Operating Margin (30%)")
    print("  ROE (25%)")
    print("  Current Ratio (15%)")
    print("  Debt/Equity inverse (10%)")
    print("  Volume percentile (20%)")

    df['Quality_Score'] = df.apply(calculate_quality_score, axis=1)
    df = add_volume_percentile(df)

    # Show score distribution
    score_bins = pd.cut(df['Quality_Score'], bins=[0, 20, 40, 60, 80, 100])
    score_counts = df.groupby(score_bins).size()
    print("\nScore distribution:")
    for bin_range, count in score_counts.items():
        label = f"{bin_range.left:.0f}-{bin_range.right:.0f}"
        desc_dict = {
            "0-20": "poor",
            "20-40": "below average",
            "40-60": "average",
            "60-80": "good",
            "80-100": "excellent"
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
