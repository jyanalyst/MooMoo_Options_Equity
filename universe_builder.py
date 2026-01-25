#!/usr/bin/env python3
"""
Bi-Weekly Universe Builder for Wheel Strategy
Fundamental screening and quality scoring for options income strategies.

This script fetches stocks from Financial Modeling Prep (FMP) API,
applies fundamental filters, calculates quality scores, and generates
tier-based watchlists.

MIGRATION: Finviz completely removed, replaced with FMP-only architecture.
FMP provides SEC-sourced fundamental data with higher reliability and
includes forward-looking metrics not available in Finviz.
"""

import argparse
import shutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

import pandas as pd
import numpy as np

# FMP API Integration (replaces Finviz)
from fmp_data_fetcher import create_fetcher


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Setup comprehensive logging for universe builder.

    Args:
        verbose: If True, set DEBUG level logging

    Returns:
        Configured logger instance
    """
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"universe_builder_{timestamp}.log"

    # Create logger
    logger = logging.getLogger('universe_builder')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # File handler (always DEBUG level for full audit trail)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (INFO level unless verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized: {log_file}")

    return logger


# Global logger (initialized in main())
logger = None


# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

# FMP Screening Criteria (applied in fetch_stocks_from_fmp + post-filters)
# These replace the old FINVIZ_FILTERS with FMP-based filtering
FMP_SCREENING_CRITERIA = {
    # FMP Screener filters (applied in fetch_stocks_from_fmp)
    'Market Cap': '>$10B',                           # Tier 1 institutions only
    'Price': '$15-600',                              # Options-friendly (expanded to include MSFT, GOOGL)
    'Average Volume': '>1M shares/day',              # Ensures options liquidity
    'Country': 'USA',                                # US-listed only (FMP default)

    # Post-screening filters (applied client-side after FMP fetch)
    'P/E': '<50',                                    # Allow quality growth (relaxed from <35)
    'Operating Margin': '>2%',                       # Profitable operations (stricter than Finviz >0%)
    'Debt/Equity': '<1.5',                           # Allow stable debt (relaxed from <1.0 for Consumer Defensive)
    'Return on Equity': '>8%',                       # Capital efficiency (relaxed from >10% for utilities)
    'Current Ratio': '>0.6',                         # Banks/staples operate at 0.6-1.0 (relaxed from >1.0)
    'Gross Margin': '>15%',                          # Meaningful pricing power
    'Free Cash Flow': 'Positive with >2% margin',    # Cash generation (NEW - not in Finviz)
}

# Required columns from Finviz (abbreviated names that finviz actually returns)
REQUIRED_COLUMNS = {
    'critical': ['Ticker', 'Company', 'Price', 'Oper M', 'ROE', 'Curr R', 'Debt/Eq'],
    'scoring': ['Oper M', 'ROE', 'Curr R', 'Debt/Eq', 'Gross M', 'Avg Volume'],
    'metadata': ['Sector', 'Industry', 'Market Cap']
}

# Data quality thresholds (conservative validation)
DATA_QUALITY_THRESHOLDS = {
    'max_missing_pct': 0.10,        # Reject if >10% of critical metrics missing
    'outlier_iqr_multiplier': 3.0,  # Flag values beyond Q3 + 3×IQR
    'min_earnings_success_rate': 0.70,  # Require 70% earnings date success (increased from 50%)
}

# REMOVED: TIER_PRICE_RANGES - Single unified universe now (no price segmentation)

QUALITY_WEIGHTS = {
    # Single-universe architecture: Emphasizes business durability
    'debt_equity_inverse': 0.20,  # Balance sheet strength (highest weight)
    'current_ratio': 0.15,        # Liquidity
    'roe_consistency': 0.15,      # 5-year ROE stability (NEW)
    'fcf_margin': 0.15,           # Cash generation
    'revenue_growth_3yr': 0.10,   # Secular growth trend (NEW)
    'gross_margin': 0.10,         # Pricing power
    'operating_margin': 0.10,     # Profitability (reduced from 15%)
    'volume_percentile': 0.05,    # Options liquidity (reduced from 15%)
}

DEFAULT_LIMITS = {
    'universe_size': 32,  # Increased from 30 to include quality stocks at sector limits
}

# Minimum quality score for inclusion in universe
MIN_QUALITY_FLOOR = 48  # Don't include stocks scoring below this threshold

# =============================================================================
# ADVANCED FEATURE THRESHOLDS (Week 2 FMP Integration)
# =============================================================================

ADVANCED_FILTER_THRESHOLDS = {
    # Financial Health (Hard Filters) - Relaxed for broader universe
    'altman_z_min': 2.0,          # Gray zone edge, still safe (relaxed from 2.6)
    'piotroski_min': 5,           # Passing score (relaxed from 6)

    # Analyst Ratings (Hard Filter)
    'analyst_buy_pct_min': 40.0,  # Allow mixed sentiment (relaxed from 50%)

    # Institutional Ownership (Soft Filter - for scoring only)
    'institutional_ownership_min': 20.0,   # Minimum for validation
    'institutional_ownership_max': 90.0,   # Maximum to avoid crowded trades
}

ADVANCED_SCORING_WEIGHTS = {
    # Bonus points for advanced features (add to existing 100-point scale)
    'financial_health_bonus': 5,      # Z > 3.0 AND Piotroski >= 7
    'strong_analyst_buy_bonus': 3,    # Buy% > 70%
    'elite_analyst_buy_bonus': 5,     # Buy% > 80%

    # NOTE: Insider/institutional bonuses disabled - not available on FMP Starter plan
    # 'insider_buying_bonus': 5,        # Net insider buying in 6 months
    # 'institutional_increase_bonus': 5, # Institutional ownership increased
    # 'heavy_insider_selling_penalty': -3,  # Sales > 3x purchases
    # 'crowded_trade_penalty': -2,          # Institutional > 85%
}

# =============================================================================
# SECTOR DIVERSIFICATION (Prevent commodity concentration)
# =============================================================================

CYCLICAL_SECTORS = ['Basic Materials', 'Energy']  # Commodities - apply penalty
CYCLICAL_PENALTY = 0.80  # 20% score reduction for cyclical sectors
CRYPTO_TICKERS = ['COIN', 'MARA', 'RIOT', 'CLSK', 'HUT', 'BITF', 'HOOD']  # Crypto-correlated, treat as cyclical

# Chinese ADRs carry geopolitical risk (delisting, regulation, VIE structure)
CHINA_ADRS = ['PDD', 'BABA', 'JD', 'NIO', 'XPEV', 'LI', 'BIDU', 'TME', 'TCOM', 'FUTU']
GEOPOLITICAL_PENALTY = 0.80  # 20% penalty for China ADRs

# Consumer Cyclical stocks that are actually cyclical (exclude AMZN, COST - they have moats)
CYCLICAL_CONSUMER = ['LULU', 'NKE', 'SBUX', 'MCD', 'HD', 'LOW', 'TJX', 'ROST']

SECTOR_DIVERSITY_CONSTRAINTS = {
    'max_per_sector': 7,           # Increased from 5 to allow deeper quality pools in Tech/Financials
    'max_sector_pct': 0.25,        # No sector >25% of universe (7/32 = 22%, within limit)
    'min_sectors': 5,              # At least 5 different sectors
    'max_cyclical_total': 3,       # Allows 1 energy + 2 materials OR vice versa
    'required_minimum': {          # Hard minimums - must be satisfied
        'Consumer Defensive': 3,   # Ensure staples presence (KO, PG, WMT)
        'Healthcare': 3,           # Ensure healthcare presence (JNJ, MRK, PFE)
        'Financial Services': 2,   # Quality financials (V, SPGI, CME)
    },
    'preferred_sectors': [         # Recession-resistant sectors to prioritize
        'Healthcare',
        'Consumer Defensive',
        'Financial Services',
        'Utilities',
        'Industrials',
    ],
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_banner():
    """Display ASCII art banner."""
    banner = """
================================================================

           WHEEL UNIVERSE BUILDER v1.0 (FMP-Powered)
     Fundamental Screening for Quality Stock Universe

================================================================
    """
    print(banner)


def print_summary(df: pd.DataFrame, universe: List[str],
                 total_screened: int, total_passed: int):
    """Print build summary."""
    print("""
================================================================
                    BUILD COMPLETE
================================================================
""")
    print(f"\nUniverse refresh complete!")
    print(f"Total quality stocks: {len(universe)}")
    next_refresh = datetime.now() + timedelta(days=14)
    print(f"Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d')}")
    print("\nTo test the new universe:")
    print("  python main.py wheel")
    print("  python main.py wheel --max-capital 10000  # Filter to stocks under $100")


def format_ticker_line(ticker: str, name: str, sector: str, score: float, earnings: str = None) -> str:
    """Format a single ticker line with company info, score, and earnings date."""
    company_short = name[:30] if len(name) > 30 else name

    # Format earnings date if available
    earnings_str = ""
    if earnings is not None and earnings != '' and str(earnings).lower() not in ['nan', 'none', '-']:
        try:
            earnings_clean = str(earnings).strip()

            # Handle YYYY-MM-DD format from yfinance
            if len(earnings_clean) == 10 and earnings_clean.count('-') == 2:
                from datetime import datetime
                dt = datetime.strptime(earnings_clean, '%Y-%m-%d')
                earnings_display = dt.strftime('%b %d')  # Convert to "Feb 19"
            else:
                # Handle other formats (legacy finviz format)
                parts = earnings_clean.split()
                if len(parts) >= 2:
                    earnings_display = f"{parts[0]} {parts[1]}"
                else:
                    earnings_display = earnings_clean

            earnings_str = f" | Earnings: {earnings_display}"

        except Exception as e:
            # Silently skip malformed dates
            pass

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
  python universe_builder.py --universe-size 30 # Custom universe size
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
        '--universe-size',
        type=int,
        default=DEFAULT_LIMITS['universe_size'],
        help=f"Target universe size (default: {DEFAULT_LIMITS['universe_size']})"
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
            print(f"[WARN]  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("[ERROR] CRITICAL: Failed to fetch data after 3 attempts")
                print("   Check internet connection or finviz.com status")
                raise


def test_blue_chip_availability(fetcher) -> tuple:
    """
    Direct test: Can FMP return data for known blue-chip tickers?

    This bypasses the stock screener entirely and fetches stocks directly.
    If this fails, FMP API doesn't have the data at all.
    If this succeeds, the stock screener is filtering them out.

    Returns:
        Tuple of (available, filtered_out, missing) ticker lists
    """
    print("\n" + "="*80)
    print("FMP API BLUE-CHIP AVAILABILITY TEST")
    print("="*80)
    print("Testing if FMP can return data for essential blue-chip stocks...")
    print("Method: Direct ticker lookup (bypassing screener)\n")

    CRITICAL_TICKERS = {
        'KO': 'Coca-Cola',
        'PG': 'Procter & Gamble',
        'WMT': 'Walmart',
        'JNJ': 'Johnson & Johnson',
        'CVS': 'CVS Health',
        'PFE': 'Pfizer',
        'JPM': 'JPMorgan Chase',
        'BAC': 'Bank of America',
        'WFC': 'Wells Fargo',
        'USB': 'US Bancorp',
        'MSFT': 'Microsoft',
        'AAPL': 'Apple',
        'GOOGL': 'Alphabet',
        'SO': 'Southern Company',
        'DUK': 'Duke Energy',
    }

    available = []
    missing = []
    filtered_out = []

    for ticker, name in CRITICAL_TICKERS.items():
        try:
            # Try to fetch company profile directly (returns dict, not list)
            profile = fetcher.get_company_profile(ticker)

            if not profile:
                missing.append(ticker)
                print(f"  [X] {ticker:6s} | {name:30s} | NO DATA FROM FMP")
                continue

            # FMP has the data - extract key info from profile
            price = profile.get('price', 0)
            sector = profile.get('sector', 'Unknown')

            # Fetch fundamental ratios (combined ratios + key metrics TTM)
            try:
                ratios = fetcher.get_fundamental_ratios(ticker)

                if ratios:
                    # FMP uses TTM suffix for most metrics
                    pe = ratios.get('peRatioTTM') or ratios.get('priceToEarningsRatioTTM')
                    roe_raw = ratios.get('returnOnEquityTTM') or 0
                    roe = roe_raw * 100 if roe_raw < 10 else roe_raw  # Handle both decimal and percentage
                    debt_eq = ratios.get('debtEquityRatioTTM') or ratios.get('debtToEquityTTM') or 0
                    curr_ratio = ratios.get('currentRatioTTM') or 0
                    market_cap = ratios.get('marketCapTTM') or ratios.get('marketCap') or 0

                    # Check if it would pass screening filters
                    passes_filters = (
                        market_cap > 10_000_000_000 and  # >$10B
                        price >= 15 and price <= 300 and
                        pe is not None and pe > 0 and pe < 50 and
                        roe > 10 and
                        debt_eq < 1.0 and
                        curr_ratio > 1.0
                    )

                    if passes_filters:
                        available.append(ticker)
                        print(f"  [OK] {ticker:6s} | {name:30s} | ${price:6.0f} | "
                              f"PE: {pe:4.1f} | ROE: {roe:4.1f}% | D/E: {debt_eq:.2f} | "
                              f"SHOULD PASS FILTERS")
                    else:
                        filtered_out.append(ticker)
                        pe_str = f"{pe:.1f}" if pe else "N/A"
                        print(f"  [!!] {ticker:6s} | {name:30s} | ${price:6.0f} | "
                              f"PE: {pe_str:>5} | ROE: {roe:4.1f}% | D/E: {debt_eq:.2f} | "
                              f"FILTERED OUT")

                        # Show why it was filtered
                        failures = []
                        if market_cap <= 10_000_000_000: failures.append(f"MCap ${market_cap/1e9:.1f}B")
                        if not (15 <= price <= 300): failures.append(f"Price ${price:.0f}")
                        if not (pe and 0 < pe < 50): failures.append(f"P/E {pe}")
                        if roe <= 10: failures.append(f"ROE {roe:.1f}%")
                        if debt_eq >= 1.0: failures.append(f"D/E {debt_eq:.2f}")
                        if curr_ratio <= 1.0: failures.append(f"CR {curr_ratio:.2f}")

                        if failures:
                            print(f"         -> Failed: {', '.join(failures)}")
                else:
                    missing.append(ticker)
                    print(f"  [X] {ticker:6s} | {name:30s} | Profile exists but no ratios data")

            except Exception as e:
                missing.append(ticker)
                print(f"  [X] {ticker:6s} | {name:30s} | Error fetching metrics: {str(e)[:50]}")

        except Exception as e:
            missing.append(ticker)
            print(f"  [X] {ticker:6s} | {name:30s} | Error: {str(e)[:50]}")

    # Summary
    print("\n" + "-"*80)
    print("SUMMARY:")
    print("-"*80)
    print(f"[OK] Available and passing filters: {len(available)}/{len(CRITICAL_TICKERS)}")
    if available:
        print(f"     Tickers: {', '.join(available)}")

    print(f"[!!] Available but filtered out: {len(filtered_out)}/{len(CRITICAL_TICKERS)}")
    if filtered_out:
        print(f"     Tickers: {', '.join(filtered_out)}")

    print(f"[X]  Not available in FMP: {len(missing)}/{len(CRITICAL_TICKERS)}")
    if missing:
        print(f"     Tickers: {', '.join(missing)}")

    print("\n" + "="*80)
    print("DIAGNOSIS:")
    print("="*80)

    if len(available) >= 10:
        print("[OK] FMP HAS THE DATA - Stock screener is filtering them out")
        print("     SOLUTION: Relax FMP screener filters, apply strict filters client-side")
        print("     OR: Fetch these tickers directly instead of using screener")
    elif len(available) + len(filtered_out) >= 10:
        print("[!!] FMP HAS THE DATA - But stocks fail quality filters")
        print("     SOLUTION: Review filter criteria (P/E, ROE, Debt/Eq limits may be too strict)")
    else:
        print("[X]  FMP API DOES NOT HAVE COMPLETE DATA")
        print("     SOLUTION: Manual universe override required")
        print("     FMP stock screener is not suitable for blue-chip stock selection")

    print("="*80 + "\n")

    return available, filtered_out, missing


def fetch_blue_chips_directly(fetcher, tickers_list: list) -> pd.DataFrame:
    """
    Fetch specific tickers directly (bypass screener).

    Use when stock screener is unreliable but direct ticker fetch works.

    Args:
        fetcher: FMP data fetcher instance
        tickers_list: List of tickers to fetch directly

    Returns:
        DataFrame with stock data for successfully fetched tickers
    """
    print("\n[DIRECT FETCH] Fetching blue-chip tickers directly...")

    all_stocks = []

    for ticker in tickers_list:
        try:
            # Fetch fundamental data (profile returns dict, not list)
            profile = fetcher.get_company_profile(ticker)
            ratios = fetcher.get_fundamental_ratios(ticker)

            if not profile or not ratios:
                print(f"  [SKIP] {ticker}: Missing profile or ratios")
                continue

            # Extract fields - profile is dict, ratios use TTM suffix
            roe_raw = ratios.get('returnOnEquityTTM') or 0
            roe = roe_raw * 100 if roe_raw < 10 else roe_raw

            oper_m_raw = ratios.get('operatingProfitMarginTTM') or 0
            oper_m = oper_m_raw * 100 if oper_m_raw < 1 else oper_m_raw

            gross_m_raw = ratios.get('grossProfitMarginTTM') or 0
            gross_m = gross_m_raw * 100 if gross_m_raw < 1 else gross_m_raw

            stock_data = {
                'Ticker': ticker,
                'Company': profile.get('companyName', ''),
                'Sector': profile.get('sector', ''),
                'Industry': profile.get('industry', ''),
                'Price': profile.get('price', 0),
                'Market Cap': ratios.get('marketCapTTM') or ratios.get('marketCap') or 0,
                'Avg Volume': profile.get('volAvg', 0),
                'P/E': ratios.get('peRatioTTM') or ratios.get('priceToEarningsRatioTTM'),
                'ROE': roe,
                'Debt/Eq': ratios.get('debtEquityRatioTTM') or ratios.get('debtToEquityTTM') or 0,
                'Curr R': ratios.get('currentRatioTTM') or 0,
                'Oper M': oper_m,
                'Gross M': gross_m,
            }

            # Only add if passes basic quality checks (relaxed for blue chips)
            if (stock_data['Market Cap'] > 10_000_000_000 and
                stock_data['Price'] >= 15 and
                stock_data['ROE'] > 5):  # Relaxed ROE for staples
                all_stocks.append(stock_data)
                print(f"  [OK] {ticker}: ${stock_data['Price']:.0f}, {stock_data['Sector']}")
            else:
                print(f"  [SKIP] {ticker}: Failed basic checks (MCap/Price/ROE)")

        except Exception as e:
            print(f"  [FAIL] {ticker}: {str(e)[:50]}")
            continue

    print(f"\n  Successfully fetched {len(all_stocks)} blue-chip stocks directly")

    return pd.DataFrame(all_stocks)


def fetch_stocks_from_fmp() -> pd.DataFrame:
    """
    Fetch stocks from FMP API using screener + fundamental data.

    REPLACES: fetch_stocks_from_finviz() - complete FMP migration

    Returns:
        DataFrame with screened stocks including financial metrics
    """
    print("[Step 1/7] Fetching stocks from FMP (replaces Finviz)...")

    # Create FMP fetcher
    fetcher = create_fetcher()

    # Fetch universe using FMP screener + fundamentals
    # This replaces Finviz with equivalent FMP filtering
    df = fetcher.fetch_universe_stocks(
        market_cap_min=10e9,        # >$10B (Finviz: '+Large (over $10bln)')
        price_min=15.0,              # >$15 (Finviz: 'Over $15')
        price_max=600.0,             # <$600 (expanded to include MSFT, GOOGL)
        volume_min=1_000_000,        # >1M (Finviz: 'Over 1M')
        limit=500                    # Fetch up to 500 stocks
    )

    if df.empty:
        print("  [ERROR] ERROR: FMP returned no stocks!")
        return df

    print(f"  Stocks fetched from FMP: {len(df)}")

    # Debug: Show fetched columns
    print("\nFetched columns from FMP:")
    for col in df.columns:
        print(f"  * {col}")

    # Diagnostic: Check for key defensive stocks
    DEFENSIVE_TICKERS = ['KO', 'PG', 'WMT', 'JNJ', 'CVS', 'PFE', 'CL', 'COST']
    print("\n[DIAGNOSTIC] Checking for defensive stocks in FMP response:")
    for ticker in DEFENSIVE_TICKERS:
        if ticker in df['Ticker'].values:
            row = df[df['Ticker'] == ticker].iloc[0]
            pe = row.get('P/E', 'N/A')
            de = row.get('Debt/Eq', 'N/A')
            sector = row.get('Sector', 'N/A')
            print(f"  [OK] {ticker}: P/E={pe}, D/E={de}, Sector={sector}")
        else:
            print(f"  [X] {ticker} - NOT in FMP response")

    # ═══════════════════════════════════════════════════════════════
    # CRITICAL DIAGNOSTIC: Blue-Chip Stock Verification
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("DIAGNOSTIC: Blue-Chip Stock Check")
    print("="*70)

    EXPECTED_BLUE_CHIPS = {
        'KO': 'Coca-Cola',
        'PG': 'Procter & Gamble',
        'WMT': 'Walmart',
        'JNJ': 'Johnson & Johnson',
        'CVS': 'CVS Health',
        'PFE': 'Pfizer',
        'JPM': 'JPMorgan Chase',
        'BAC': 'Bank of America',
        'WFC': 'Wells Fargo',
        'USB': 'US Bancorp',
        'MSFT': 'Microsoft',
        'SO': 'Southern Company',
        'DUK': 'Duke Energy',
    }

    found = []
    missing = []

    for ticker, name in EXPECTED_BLUE_CHIPS.items():
        if ticker in df['Ticker'].values:
            row = df[df['Ticker'] == ticker].iloc[0]
            found.append(ticker)
            print(f"  [OK] {ticker:6s} | {name:25s} | Price: ${row.get('Price', 0):.0f} | "
                  f"Sector: {row.get('Sector', 'N/A')}")
        else:
            missing.append(ticker)
            print(f"  [X]  {ticker:6s} | {name:25s} | MISSING")

    print(f"\nFound: {len(found)}/{len(EXPECTED_BLUE_CHIPS)}")
    print(f"Missing: {', '.join(missing) if missing else 'None'}")
    print("="*70 + "\n")

    return df


def fetch_advanced_data_for_top_stocks(df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    """
    Fetch advanced FMP data for top N stocks (by preliminary quality score).

    This is called AFTER basic filtering to limit API usage.
    Only the top candidates get the advanced data treatment.

    Advanced data includes (FMP Starter plan):
    - Financial scores (Altman Z-Score, Piotroski Score)
    - Analyst estimates (forward revenue/EPS)
    - Analyst ratings consensus

    NOTE: Insider trading and institutional ownership require higher FMP tiers
    and are NOT fetched to avoid wasted API calls.

    Also includes top stocks from required sectors to ensure sector diversity.

    Args:
        df: DataFrame with basic fundamental data and preliminary scores
        top_n: Number of top stocks to fetch advanced data for

    Returns:
        DataFrame with advanced data columns added
    """
    print(f"\n[Step 2.5/7] Fetching advanced data for top {top_n} stocks + required sectors...")
    print(f"  (Financial scores, analyst estimates, analyst ratings)")
    print(f"  NOTE: Insider/institutional data skipped (requires higher FMP tier)")

    # Get top N stocks by preliminary Quality_Score
    if 'Quality_Score' not in df.columns:
        print("  WARNING: Quality_Score not found, using all stocks up to limit")
        top_stocks = df.head(top_n)
    else:
        top_stocks = df.nlargest(top_n, 'Quality_Score')

    tickers_to_fetch = set(top_stocks['Ticker'].tolist())

    # Also include top stocks from required sectors to ensure diversity
    required_sectors = SECTOR_DIVERSITY_CONSTRAINTS.get('required_minimum', {})
    for sector, min_count in required_sectors.items():
        sector_stocks = df[df['Sector'] == sector].nlargest(min_count * 2, 'Quality_Score')['Ticker'].tolist()
        added = [t for t in sector_stocks if t not in tickers_to_fetch]
        if added:
            print(f"  Including {len(added)} extra {sector} stocks: {added}")
            tickers_to_fetch.update(added)

    # CRITICAL: Always include essential blue-chip tickers regardless of preliminary score
    # Banks score low on margins (regulated, not growth) but are essential for defensive allocation
    # Note: BAC removed (scores 25.4, legitimately fails quality threshold of 30)
    CRITICAL_BLUE_CHIPS = ['JPM', 'WFC', 'USB', 'PFE', 'WMT', 'AAPL', 'SO', 'DUK']
    critical_in_dataset = [t for t in CRITICAL_BLUE_CHIPS if t in df['Ticker'].values]
    critical_missing = [t for t in CRITICAL_BLUE_CHIPS if t not in df['Ticker'].values]
    critical_added = [t for t in critical_in_dataset if t not in tickers_to_fetch]
    critical_already = [t for t in critical_in_dataset if t in tickers_to_fetch]

    print(f"  [DEBUG] Critical blue-chips in dataset: {critical_in_dataset}")
    print(f"  [DEBUG] Critical blue-chips already fetched: {critical_already}")
    print(f"  [DEBUG] Critical blue-chips missing from dataset: {critical_missing}")

    if critical_added:
        print(f"  Including {len(critical_added)} critical blue-chips: {critical_added}")
        tickers_to_fetch.update(critical_added)

    tickers_to_fetch = list(tickers_to_fetch)
    print(f"  Fetching advanced data for: {len(tickers_to_fetch)} stocks")

    # Create FMP fetcher
    fetcher = create_fetcher()

    # Fetch advanced data for each ticker
    advanced_data = {}
    success_count = 0

    for i, ticker in enumerate(tickers_to_fetch, 1):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(tickers_to_fetch)} stocks...")

        data = fetcher.get_complete_advanced_data(ticker)
        if data:
            advanced_data[ticker] = data
            success_count += 1

    print(f"\n  Advanced data fetched: {success_count}/{len(tickers_to_fetch)} stocks")

    # Add advanced columns to dataframe
    df = df.copy()

    # Initialize new columns with defaults
    advanced_columns = [
        'Altman_Z', 'Piotroski', 'Analyst_Buy_Pct', 'Analyst_Consensus',
        'Insider_Net_Buying', 'Insider_Buy_Ratio',
        'Institutional_Pct', 'Institutional_Change'
    ]

    for col in advanced_columns:
        df[col] = None

    # Populate advanced data
    for ticker, data in advanced_data.items():
        mask = df['Ticker'] == ticker
        df.loc[mask, 'Altman_Z'] = data.get('altman_z_score')
        df.loc[mask, 'Piotroski'] = data.get('piotroski_score')
        df.loc[mask, 'Analyst_Buy_Pct'] = data.get('analyst_buy_pct')
        df.loc[mask, 'Analyst_Consensus'] = data.get('analyst_consensus')
        df.loc[mask, 'Insider_Net_Buying'] = data.get('insider_net_buying')
        df.loc[mask, 'Insider_Buy_Ratio'] = data.get('insider_buy_ratio')
        df.loc[mask, 'Institutional_Pct'] = data.get('institutional_ownership_pct')
        df.loc[mask, 'Institutional_Change'] = data.get('institutional_change')

    return df


# =============================================================================
# DATA VALIDATION FUNCTIONS
# =============================================================================

def validate_schema(df: pd.DataFrame) -> None:
    """
    Validate that all required columns are present in the dataframe.
    Fail loudly if critical columns are missing (no silent failures).

    Args:
        df: DataFrame from finviz

    Raises:
        KeyError: If critical columns are missing
    """
    print("\n[VALIDATION] Schema validation...")

    all_required = []
    for category, cols in REQUIRED_COLUMNS.items():
        all_required.extend(cols)

    missing_cols = [col for col in all_required if col not in df.columns]

    if missing_cols:
        print(f"[ERROR] CRITICAL: Required columns missing from finviz data!")
        print(f"   Missing columns: {missing_cols}")
        print(f"   Available columns: {df.columns.tolist()}")
        raise KeyError(
            f"Finviz schema changed - missing {len(missing_cols)} required columns. "
            f"This likely means finviz changed their column names. "
            f"Update REQUIRED_COLUMNS constant to match new schema."
        )

    print(f"  [OK] All {len(all_required)} required columns present")

    # Schema version tracking (hash of column names for debugging)
    import hashlib
    schema_hash = hashlib.md5(','.join(sorted(df.columns)).encode()).hexdigest()[:8]
    print(f"  Schema version: {schema_hash}")


def validate_data_completeness(df: pd.DataFrame) -> None:
    """
    Validate that critical metrics have sufficient non-null data.
    Reject dataset if >10% of key metrics are missing (conservative threshold).

    Args:
        df: DataFrame with financial metrics

    Raises:
        ValueError: If data completeness is below threshold
    """
    print("\n[VALIDATION] Data completeness check...")

    critical_metrics = REQUIRED_COLUMNS['scoring']
    issues = []

    for col in critical_metrics:
        if col in df.columns:
            null_count = df[col].isna().sum()
            null_pct = null_count / len(df)

            if null_pct > DATA_QUALITY_THRESHOLDS['max_missing_pct']:
                issues.append(f"  [ERROR] {col}: {null_pct:.1%} missing ({null_count}/{len(df)} rows)")
            else:
                print(f"  [OK] {col}: {null_pct:.1%} missing ({null_count}/{len(df)} rows)")

    if issues:
        print(f"\n[ERROR] CRITICAL: Data completeness below threshold!")
        print("\n".join(issues))
        print(f"\nThreshold: {DATA_QUALITY_THRESHOLDS['max_missing_pct']:.0%} maximum missing allowed")
        raise ValueError(
            f"Data quality check failed: {len(issues)} metrics have >10% missing data. "
            f"This may indicate finviz data quality issues or connectivity problems. "
            f"Check finviz.com directly or try again later."
        )

    print(f"  [OK] All metrics meet {DATA_QUALITY_THRESHOLDS['max_missing_pct']:.0%} completeness threshold")


def detect_and_remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and remove outliers using IQR (Interquartile Range) method.
    This prevents finviz data glitches (like P/E = 9999) from corrupting scores.

    Uses 3×IQR rule: Flag values beyond Q1 - 3×IQR or Q3 + 3×IQR

    SECTOR EXEMPTIONS:
    - Financial Services exempt from Curr R and Debt/Eq outlier detection
      (Banks have fundamentally different capital structure - deposits = liabilities)

    Args:
        df: DataFrame with financial metrics

    Returns:
        DataFrame with outliers removed
    """
    print("\n[VALIDATION] Outlier detection (3×IQR method)...")

    df = df.copy()
    numeric_metrics = ['P/E', 'Oper M', 'ROE', 'Curr R', 'Debt/Eq', 'Gross M']

    # Metrics where Financial Services should be exempt (different capital structure)
    financial_exempt_metrics = ['Curr R', 'Debt/Eq']

    outliers_found = []
    total_outliers = 0

    for col in numeric_metrics:
        if col not in df.columns:
            continue

        # For certain metrics, exclude Financial Services from outlier detection
        if col in financial_exempt_metrics and 'Sector' in df.columns:
            # Only apply outlier detection to non-Financial Services
            analysis_mask = df['Sector'] != 'Financial Services'
            analysis_df = df[analysis_mask]
        else:
            analysis_mask = pd.Series(True, index=df.index)
            analysis_df = df

        if len(analysis_df) == 0:
            continue

        # Calculate IQR on the relevant subset
        Q1 = analysis_df[col].quantile(0.25)
        Q3 = analysis_df[col].quantile(0.75)
        IQR = Q3 - Q1

        multiplier = DATA_QUALITY_THRESHOLDS['outlier_iqr_multiplier']
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR

        # Identify outliers (only in the analyzed subset)
        outlier_mask = analysis_mask & ((df[col] < lower_bound) | (df[col] > upper_bound))
        outlier_count = outlier_mask.sum()

        if outlier_count > 0:
            outlier_tickers = df[outlier_mask]['Ticker'].tolist()
            outlier_values = df[outlier_mask][col].tolist()
            outliers_found.append({
                'metric': col,
                'count': outlier_count,
                'tickers': outlier_tickers,
                'values': outlier_values,
                'bounds': (lower_bound, upper_bound)
            })
            total_outliers += outlier_count

            # Remove outliers
            df = df[~outlier_mask]

            print(f"  [WARN]  {col}: Removed {outlier_count} outliers")
            for ticker, value in zip(outlier_tickers[:3], outlier_values[:3]):  # Show first 3
                print(f"      {ticker}: {value:.2f} (bounds: {lower_bound:.2f} to {upper_bound:.2f})")
            if outlier_count > 3:
                print(f"      ... and {outlier_count - 3} more")

    if total_outliers == 0:
        print("  [OK] No outliers detected - data quality looks good")
    else:
        print(f"\n  Total outliers removed: {total_outliers} data points across {len(outliers_found)} metrics")
        print(f"  Remaining stocks: {len(df)}")

    return df


# =============================================================================
# POST-SCREENING FILTERS
# =============================================================================

def apply_post_screening_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply additional filters to FMP data.

    NOTE: FMP already returns numeric data (not strings), so no conversion needed.
    Many filters already applied by FMP screener, these are additional client-side filters.

    Args:
        df: Raw screening results from FMP

    Returns:
        Filtered DataFrame
    """
    print("\n[Step 2/7] Applying post-screening filters...")

    original_count = len(df)
    df = df.copy()

    # FMP returns numeric data already, no string conversion needed!
    # Columns are already: Oper M, ROE, Curr R, Debt/Eq, etc. (numeric percentages)

    # Filter 1: P/E ratio < 50 (profitable, allow quality growth stocks)
    # Exempt healthcare stocks with temporary P/E distortions (e.g., CVS restructuring)
    if 'P/E' in df.columns:
        # Healthcare exception for temporary P/E distortions
        healthcare_exception = (df['Sector'] == 'Healthcare') & (df['P/E'] > 50) & (df['P/E'] < 300)
        pe_mask = (df['P/E'] > 50) & ~healthcare_exception
        df = df[~pe_mask]
        pe_excluded = pe_mask.sum()
        if pe_excluded > 0:
            print(f"  [X] Excluded {pe_excluded} stocks with P/E >50")

    # Filter 2: Operating margin >2% (stricter than FMP screener default)
    if 'Oper M' in df.columns:
        op_margin_mask = df['Oper M'] < 2.0
        df = df[~op_margin_mask]
        op_margin_excluded = op_margin_mask.sum()
        if op_margin_excluded > 0:
            print(f"  [X] Excluded {op_margin_excluded} stocks with operating margin <2%")

    # Filter 3: ROE with sector-aware thresholds
    # Utilities: ROE >8% (regulated, lower returns normal)
    # Others: ROE >10% (standard requirement)
    if 'ROE' in df.columns:
        utilities_low_roe = (df['Sector'] == 'Utilities') & (df['ROE'] < 8.0)
        others_low_roe = (df['Sector'] != 'Utilities') & (df['ROE'] < 10.0)
        roe_mask = utilities_low_roe | others_low_roe
        df = df[~roe_mask]
        roe_excluded = roe_mask.sum()
        if roe_excluded > 0:
            print(f"  [X] Excluded {roe_excluded} stocks with ROE below threshold (utilities >8%, others >10%)")

    # Filter 4: Current ratio with sector exemptions
    # Banks have CR < 0.5 by design (deposits = liabilities, regulated differently)
    # Consumer staples/utilities operate at CR 0.6-1.0 (stable cash flows)
    # FULL exemption: Financial Services (banks use deposits, CR meaningless)
    # PARTIAL exemption: Consumer Defensive, Utilities (allow CR 0.6-1.0)
    if 'Curr R' in df.columns:
        full_exempt_sectors = ['Financial Services']  # Banks - CR not applicable
        partial_exempt_sectors = ['Consumer Defensive', 'Utilities']  # Allow 0.6-1.0

        # Exclude if:
        # - Fully exempt sectors: never exclude (always pass)
        # - Partially exempt sectors: exclude only if CR < 0.6
        # - Others: exclude if CR < 1.0
        curr_ratio_mask = (
            ~df['Sector'].isin(full_exempt_sectors) &  # Not fully exempt
            (
                (df['Curr R'] < 0.6) |  # Below floor for partial exempts
                ((df['Curr R'] < 1.0) & ~df['Sector'].isin(partial_exempt_sectors))  # Below 1.0 for others
            )
        )
        df = df[~curr_ratio_mask]
        curr_excluded = curr_ratio_mask.sum()
        if curr_excluded > 0:
            print(f"  [X] Excluded {curr_excluded} stocks with current ratio <0.6 (or <1.0 for non-exempt sectors)")

    # Filter 5: Debt/Equity with sector exemptions
    # Financial Services: EXEMPT (deposits = liabilities, D/E meaningless for banks)
    # Consumer Defensive: Allow D/E up to 2.0 (staples use debt for buybacks, dividends)
    # Others: D/E <1.0 (conservative)
    if 'Debt/Eq' in df.columns:
        # Fully exempt Financial Services (banks use deposits, D/E ratio doesn't apply)
        full_exempt_sectors = ['Financial Services']
        # Consumer Defensive gets relaxed threshold
        consumer_defensive_high_debt = (df['Sector'] == 'Consumer Defensive') & (df['Debt/Eq'] > 2.0)
        # Others get strict threshold, unless fully exempt
        others_high_debt = (
            ~df['Sector'].isin(full_exempt_sectors) &
            (df['Sector'] != 'Consumer Defensive') &
            (df['Debt/Eq'] > 1.0)
        )
        debt_mask = consumer_defensive_high_debt | others_high_debt
        df = df[~debt_mask]
        debt_excluded = debt_mask.sum()
        if debt_excluded > 0:
            print(f"  [X] Excluded {debt_excluded} stocks with debt/equity above threshold (staples >2.0, others >1.0, financials exempt)")

    # Filter 6: Gross margin >15% (meaningful pricing power)
    if 'Gross M' in df.columns:
        gross_margin_mask = df['Gross M'] < 15.0
        df = df[~gross_margin_mask]
        gross_excluded = gross_margin_mask.sum()
        if gross_excluded > 0:
            print(f"  [X] Excluded {gross_excluded} stocks with gross margin <15%")

    # Filter 7: Biotech exclusion (binary FDA risk)
    if 'Industry' in df.columns and 'Sector' in df.columns:
        biotech_mask = (
            df['Industry'].str.contains('Biotechnology', na=False, case=False) &
            (df['Sector'] == 'Healthcare')
        )
        df = df[~biotech_mask]
        biotech_excluded = biotech_mask.sum()
        if biotech_excluded > 0:
            print(f"  [X] Excluded {biotech_excluded} biotech stocks (binary FDA risk)")

    final_count = len(df)
    print(f"  Quality stocks remaining: {final_count} (filtered {original_count - final_count})")

    # Diagnostic: Track which defensive stocks survived filters
    DEFENSIVE_TICKERS = ['KO', 'PG', 'WMT', 'JNJ', 'CVS', 'PFE', 'CL', 'COST']
    surviving = [t for t in DEFENSIVE_TICKERS if t in df['Ticker'].values]
    print(f"\n[DIAGNOSTIC] Defensive stocks after filters: {surviving if surviving else 'NONE'}")

    return df


def apply_advanced_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply advanced filters based on Tier 1 FMP features.

    Hard filters:
    - Altman Z-Score > 2.0 (bankruptcy safety) - EXEMPT: Financial Services (banks use debt)
    - Piotroski Score >= 4 (fundamental quality) - EXEMPT: Consumer Defensive
    - Analyst Buy% > 40% (reasonable sentiment) - EXEMPT: Consumer Defensive

    Args:
        df: DataFrame with advanced data columns

    Returns:
        Filtered DataFrame (only stocks with advanced data that pass filters)
    """
    print("\n[Step 2.7/7] Applying advanced filters...")

    original_count = len(df)
    df = df.copy()

    # Only filter stocks that have advanced data (top N from previous step)
    # Stocks without advanced data are excluded by default
    has_advanced_data = df['Altman_Z'].notna()
    df_with_data = df[has_advanced_data].copy()
    stocks_without_data = (~has_advanced_data).sum()

    if stocks_without_data > 0:
        print(f"  INFO: {stocks_without_data} stocks excluded (no advanced data)")

    if len(df_with_data) == 0:
        print("  WARNING: No stocks have advanced data, skipping advanced filters")
        return df

    # ═══════════════════════════════════════════════════════════════
    # DIAGNOSTIC: Track blue-chip survival through filtering
    # ═══════════════════════════════════════════════════════════════
    TRACKED_BLUE_CHIPS = ['JPM', 'WFC', 'JNJ', 'WMT', 'USB', 'PFE', 'BAC', 'KO', 'PG']
    print("\n  Blue-chip status before filtering:")
    for ticker in TRACKED_BLUE_CHIPS:
        if ticker in df_with_data['Ticker'].values:
            row = df_with_data[df_with_data['Ticker'] == ticker].iloc[0]
            altman = row.get('Altman_Z', 'N/A')
            piotroski = row.get('Piotroski', 'N/A')
            sector = row.get('Sector', 'N/A')
            print(f"    {ticker:6s} | Z: {altman:>5.1f} | P: {piotroski:>2.0f} | {sector}")

    # Track exclusions
    excluded_z = []
    excluded_p = []
    excluded_buy = []

    # Filter 1: Altman Z-Score > 2.0 (bankruptcy safety)
    # EXEMPT Financial Services - banks structurally have low Altman Z (debt is their business)
    z_min = ADVANCED_FILTER_THRESHOLDS['altman_z_min']
    is_financial = df_with_data['Sector'] == 'Financial Services'
    z_mask = (df_with_data['Altman_Z'] >= z_min) | is_financial
    excluded_z = df_with_data[~z_mask]['Ticker'].tolist()
    if len(excluded_z) > 0:
        print(f"  Excluded {len(excluded_z)} stocks with Altman Z < {z_min}: {excluded_z[:5]}{'...' if len(excluded_z) > 5 else ''}")
    print(f"  [INFO] Financial Services ({is_financial.sum()} stocks) exempted from Altman Z filter")

    # Filter 2: Piotroski Score >= 4 (quality threshold) - Relaxed from 5
    # Exempt Consumer Defensive - stable businesses often score lower due to mature operations
    p_min = 4  # Relaxed from ADVANCED_FILTER_THRESHOLDS['piotroski_min'] (was 5)
    p_mask = (df_with_data['Piotroski'] >= p_min) | (df_with_data['Sector'] == 'Consumer Defensive')
    excluded_p = df_with_data[~p_mask]['Ticker'].tolist()
    if len(excluded_p) > 0:
        print(f"  Excluded {len(excluded_p)} stocks with Piotroski < {p_min}: {excluded_p[:5]}{'...' if len(excluded_p) > 5 else ''}")

    # Filter 3: Analyst Buy% > 40% (reasonable sentiment)
    # Exempt defensive sectors - mature businesses often have conservative analyst ratings
    # Banks, pharma, staples are income/stability plays, not growth → analysts give HOLD ratings
    buy_min = ADVANCED_FILTER_THRESHOLDS['analyst_buy_pct_min']
    analyst_exempt_sectors = ['Financial Services', 'Consumer Defensive', 'Healthcare']
    buy_mask = (df_with_data['Analyst_Buy_Pct'] >= buy_min) | df_with_data['Sector'].isin(analyst_exempt_sectors)
    excluded_buy = df_with_data[~buy_mask]['Ticker'].tolist()
    if len(excluded_buy) > 0:
        print(f"  Excluded {len(excluded_buy)} stocks with Analyst Buy% < {buy_min}%: {excluded_buy[:5]}{'...' if len(excluded_buy) > 5 else ''}")

    # Combine all filters
    combined_mask = z_mask & p_mask & buy_mask
    df_filtered = df_with_data[combined_mask]

    # Diagnostic: Blue-chip survival after filtering
    surviving_blue_chips = [t for t in TRACKED_BLUE_CHIPS if t in df_filtered['Ticker'].values]
    filtered_blue_chips = [t for t in TRACKED_BLUE_CHIPS if t in df_with_data['Ticker'].values and t not in surviving_blue_chips]
    print(f"\n  Blue-chip survival: {len(surviving_blue_chips)}/{len(TRACKED_BLUE_CHIPS)}")
    if surviving_blue_chips:
        print(f"    Survived: {', '.join(surviving_blue_chips)}")
    if filtered_blue_chips:
        print(f"    Filtered: {', '.join(filtered_blue_chips)}")

    final_count = len(df_filtered)
    print(f"\n  Advanced filtering: {original_count} -> {final_count} stocks")
    print(f"  (Excluded {original_count - final_count} stocks failing advanced criteria)")

    return df_filtered


# =============================================================================
# EARNINGS ENRICHMENT FUNCTIONS
# =============================================================================

def enrich_with_next_earnings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch next earnings dates using yfinance.

    Replaces finviz's 'last earnings' with actual 'next earnings'.
    This is critical for forward-looking earnings safety checks.

    Args:
        df: DataFrame with stock data

    Returns:
        DataFrame with 'Next_Earnings' column added
    """
    import yfinance as yf
    from datetime import datetime

    print("\n[Step 2.5/7] Fetching next earnings dates from yfinance...")
    print("  (This may take 30-60 seconds for 15 stocks)")

    df = df.copy()
    df['Next_Earnings'] = None

    success_count = 0

    for idx, row in df.iterrows():
        ticker = row['Ticker']
        try:
            # Fetch stock calendar
            stock = yf.Ticker(ticker)
            calendar = stock.calendar

            # Extract next earnings date
            if calendar is not None:
                if hasattr(calendar, 'get') and 'Earnings Date' in calendar:
                    earnings_dates = calendar['Earnings Date']
                elif hasattr(calendar, 'index') and 'Earnings Date' in calendar.index:
                    earnings_dates = calendar.loc['Earnings Date']
                else:
                    earnings_dates = None

                if earnings_dates is not None and len(earnings_dates) > 0:
                    # First date is next earnings
                    next_earnings = earnings_dates[0] if hasattr(earnings_dates, '__iter__') else earnings_dates

                    # Convert to string format
                    if hasattr(next_earnings, 'strftime'):
                        earnings_str = next_earnings.strftime('%Y-%m-%d')
                        df.at[idx, 'Next_Earnings'] = earnings_str
                        print(f"  [OK] {ticker:8s} -> {next_earnings.strftime('%b %d, %Y')}")
                        success_count += 1
                    else:
                        print(f"  [WARN]  {ticker:8s} -> Unexpected format: {next_earnings}")
                else:
                    print(f"  [WARN]  {ticker:8s} -> No earnings date found")
            else:
                print(f"  [WARN]  {ticker:8s} -> Calendar unavailable")

        except Exception as e:
            print(f"  [ERROR] {ticker:8s} -> Error: {str(e)[:50]}")

    print(f"\n  Next earnings fetched: {success_count}/{len(df)} stocks")

    # IMPROVED: Stricter earnings validation (70% threshold, up from 50%)
    success_rate = success_count / len(df) if len(df) > 0 else 0
    min_rate = DATA_QUALITY_THRESHOLDS['min_earnings_success_rate']

    if success_rate < min_rate:
        print(f"\n  [ERROR] CRITICAL: Earnings fetch success rate too low!")
        print(f"     Success rate: {success_rate:.1%} (minimum required: {min_rate:.0%})")
        print(f"     This may indicate yfinance connectivity issues or data quality problems")
        print(f"     Consider:")
        print(f"       1. Check internet connectivity")
        print(f"       2. Try again in a few minutes")
        print(f"       3. Use manual earnings_calendar.py as fallback")

        response = input(f"\n  Continue with {success_rate:.1%} earnings coverage? (y/n): ")
        if response.lower() != 'y':
            print("  Aborted. Run again when earnings data improves.")
            exit(1)

    return df


def validate_free_cash_flow(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate Free Cash Flow (FCF) for all stocks using yfinance.
    Require FCF > 0 AND FCF margin > 2%.

    This prevents selecting GAAP-profitable but cash-burning companies.

    Args:
        df: DataFrame with stock data

    Returns:
        DataFrame with FCF-validated stocks only
    """
    import yfinance as yf

    print("\n[Step 2.6/7] Validating Free Cash Flow from yfinance...")
    print("  (This may take 60-90 seconds for 15+ stocks)")

    df = df.copy()
    df['FCF'] = None
    df['FCF_Margin'] = None

    passed = []
    failed = []

    for idx, row in df.iterrows():
        ticker = row['Ticker']
        try:
            stock = yf.Ticker(ticker)
            cash_flow = stock.cashflow

            if cash_flow is not None and len(cash_flow) > 0:
                # Free Cash Flow = Operating Cash Flow - Capital Expenditures
                if 'Free Cash Flow' in cash_flow.index:
                    fcf = cash_flow.loc['Free Cash Flow'].iloc[0] if len(cash_flow.loc['Free Cash Flow']) > 0 else None
                elif 'Operating Cash Flow' in cash_flow.index and 'Capital Expenditure' in cash_flow.index:
                    ocf = cash_flow.loc['Operating Cash Flow'].iloc[0]
                    capex = cash_flow.loc['Capital Expenditure'].iloc[0]
                    fcf = ocf + capex  # capex is negative
                else:
                    fcf = None

                if fcf is not None:
                    # Get revenue for FCF margin calculation
                    financials = stock.financials
                    if financials is not None and 'Total Revenue' in financials.index:
                        revenue = financials.loc['Total Revenue'].iloc[0]
                        fcf_margin = (fcf / revenue) * 100 if revenue > 0 else 0

                        df.at[idx, 'FCF'] = fcf
                        df.at[idx, 'FCF_Margin'] = fcf_margin

                        # Conservative validation: FCF > 0 AND margin > 2%
                        if fcf > 0 and fcf_margin > 2.0:
                            passed.append(ticker)
                            print(f"  [OK] {ticker:8s} -> FCF: ${fcf/1e9:.2f}B, Margin: {fcf_margin:.1f}%")
                        else:
                            failed.append((ticker, fcf, fcf_margin))
                            print(f"  [ERROR] {ticker:8s} -> FCF: ${fcf/1e9:.2f}B, Margin: {fcf_margin:.1f}% (FAILED)")
                    else:
                        failed.append((ticker, fcf, None))
                        print(f"  [WARN]  {ticker:8s} -> FCF available but no revenue data")
                else:
                    failed.append((ticker, None, None))
                    print(f"  [WARN]  {ticker:8s} -> No FCF data available")
            else:
                failed.append((ticker, None, None))
                print(f"  [WARN]  {ticker:8s} -> No cash flow data")

        except Exception as e:
            failed.append((ticker, None, None))
            print(f"  [ERROR] {ticker:8s} -> Error: {str(e)[:40]}")

    print(f"\n  FCF Validation Results:")
    print(f"    [OK] Passed: {len(passed)} stocks")
    print(f"    [ERROR] Failed: {len(failed)} stocks")

    if failed:
        print(f"\n  Excluded stocks (negative/low FCF or missing data):")
        for ticker, fcf, margin in failed[:10]:  # Show first 10
            if fcf is not None and margin is not None:
                print(f"    {ticker}: FCF=${fcf/1e9:.2f}B, Margin={margin:.1f}%")
            else:
                print(f"    {ticker}: Missing FCF data")
        if len(failed) > 10:
            print(f"    ... and {len(failed) - 10} more")

    # Filter to only passed stocks
    df_passed = df[df['Ticker'].isin(passed)]

    if len(df_passed) < 15:
        print(f"\n  [WARN]  WARNING: Only {len(df_passed)} stocks passed FCF validation")
        print(f"     This is below minimum of 15 stocks for tier distribution")
        response = input(f"\n  Continue with {len(df_passed)} stocks? (y/n): ")
        if response.lower() != 'y':
            print("  Aborted. Consider relaxing FCF threshold.")
            exit(1)

    return df_passed


# =============================================================================
# QUALITY SCORING FUNCTIONS
# =============================================================================

def calculate_quality_scores_percentile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate quality scores using WITHIN-SECTOR percentile ranking.

    This prevents tech stocks from dominating scoring vs. consumer staples/banks.
    Each stock is ranked against peers in its sector, not the entire universe.

    Example: PG (Consumer Defensive, 23% operating margin) now ranks against
    KO/STZ/MNST (20-30% margins), not against MSFT/GOOGL (40-50% margins).

    Scoring weights (within-sector percentiles):
    - Operating Margin: 15 points
    - ROE: 15 points
    - Current Ratio: 15 points
    - Debt/Equity (inverse): 20 points
    - Gross Margin: 10 points
    - FCF Margin: 10 points
    Total base score: 85 points (volume adds up to 15 more)

    Args:
        df: DataFrame with financial metrics and Sector column

    Returns:
        DataFrame with quality scores calculated within each sector
    """
    df = df.copy()

    # Define scoring metrics: (column_name, score_col_name, weight, is_inverse)
    metrics = [
        ('Oper M', 'OM_Score', 15, False),      # Operating margin (higher = better)
        ('ROE', 'ROE_Score', 15, False),        # Return on equity (higher = better)
        ('Curr R', 'CR_Score', 15, False),      # Current ratio (higher = better)
        ('Debt/Eq', 'DE_Score', 20, True),      # Debt/equity (LOWER = better, inverse)
        ('Gross M', 'GM_Score', 10, False),     # Gross margin (higher = better)
        ('FCF_Margin', 'FCF_Score', 10, False), # Free cash flow margin (higher = better)
    ]

    print("\n[SCORING] Calculating quality scores using WITHIN-SECTOR percentiles...")
    print("  This ensures Consumer Defensive stocks aren't penalized vs. Tech")

    for metric, score_col, weight, is_inverse in metrics:
        if metric not in df.columns:
            print(f"  [WARN] '{metric}' column not found, setting score to 0")
            df[score_col] = 0
            continue

        if 'Sector' not in df.columns:
            # Fallback to global percentile if no sector data
            print(f"  [WARN] 'Sector' column not found, using global percentile for {metric}")
            df[score_col] = df[metric].rank(
                pct=True,
                ascending=(not is_inverse),
                na_option='bottom'
            ) * weight
            continue

        # Key change: Rank WITHIN SECTOR using groupby
        # Each stock compared only to peers in same sector
        df[score_col] = df.groupby('Sector')[metric].rank(
            pct=True,                    # Percentile ranking (0.0 to 1.0)
            ascending=(not is_inverse),  # Reverse for Debt/Eq (lower is better)
            na_option='bottom'           # Missing values rank at bottom
        ) * weight

        # Handle sectors with only 1 stock (can't rank, give neutral score)
        sector_sizes = df.groupby('Sector').size()
        single_stock_sectors = sector_sizes[sector_sizes == 1].index.tolist()
        for sector in single_stock_sectors:
            sector_mask = df['Sector'] == sector
            df.loc[sector_mask, score_col] = weight * 0.5  # Neutral 50th percentile

    # Sum all components (max 85 points before volume)
    df['Quality_Score'] = (
        df['OM_Score'].fillna(0) +
        df['ROE_Score'].fillna(0) +
        df['CR_Score'].fillna(0) +
        df['DE_Score'].fillna(0) +
        df['GM_Score'].fillna(0) +
        df['FCF_Score'].fillna(0)
    )

    print(f"  Base score range: {df['Quality_Score'].min():.1f} - {df['Quality_Score'].max():.1f}")
    print(f"  (Volume score will add 0-15 points, bringing max to ~100)")

    # Debug: Show example scoring for Consumer Defensive
    if 'PG' in df['Ticker'].values:
        pg_row = df[df['Ticker'] == 'PG'].iloc[0]
        print(f"\n  [DEBUG] PG score breakdown (Consumer Defensive peer group):")
        print(f"    Operating Margin: {pg_row.get('Oper M', 0):.1f}% -> {pg_row['OM_Score']:.1f}/15")
        print(f"    ROE: {pg_row.get('ROE', 0):.1f}% -> {pg_row['ROE_Score']:.1f}/15")
        print(f"    Current Ratio: {pg_row.get('Curr R', 0):.2f} -> {pg_row['CR_Score']:.1f}/15")
        print(f"    Debt/Equity: {pg_row.get('Debt/Eq', 0):.2f} -> {pg_row['DE_Score']:.1f}/20")
        print(f"    Gross Margin: {pg_row.get('Gross M', 0):.1f}% -> {pg_row['GM_Score']:.1f}/10")
        print(f"    FCF Margin: {pg_row.get('FCF_Margin', 0):.1f}% -> {pg_row['FCF_Score']:.1f}/10")
        print(f"    Base Total: {pg_row['Quality_Score']:.1f}/85")

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
        print("  [WARN]  WARNING: 'Avg Volume' column not found")
        df['Volume_Score'] = 0

    return df


def diagnose_missing_blue_chips(df: pd.DataFrame) -> None:
    """
    Diagnostic function to identify why expected blue-chip stocks are missing.

    Checks for common exclusion reasons:
    - Not in FMP dataset
    - Filtered by price/market cap
    - Filtered by fundamental metrics (CR, FCF, etc.)
    - Low quality score

    Args:
        df: DataFrame after initial FMP fetch and post-screening filters
    """
    print("\n" + "="*70)
    print("MISSING BLUE-CHIP DIAGNOSTIC")
    print("="*70)

    EXPECTED_BLUE_CHIPS = {
        'WMT': {'name': 'Walmart', 'sector': 'Consumer Defensive'},
        'AAPL': {'name': 'Apple', 'sector': 'Technology'},
        'CVS': {'name': 'CVS Health', 'sector': 'Healthcare'},
        'SO': {'name': 'Southern Company', 'sector': 'Utilities'},
        'DUK': {'name': 'Duke Energy', 'sector': 'Utilities'},
        'JPM': {'name': 'JPMorgan Chase', 'sector': 'Financial Services'},
        'WFC': {'name': 'Wells Fargo', 'sector': 'Financial Services'},
        'USB': {'name': 'US Bancorp', 'sector': 'Financial Services'},
    }

    present_count = 0
    missing_count = 0

    for ticker, info in EXPECTED_BLUE_CHIPS.items():
        if ticker in df['Ticker'].values:
            present_count += 1
            row = df[df['Ticker'] == ticker].iloc[0]
            print(f"\n[OK] {ticker} ({info['name']}) - PRESENT")
            print(f"  Sector: {row.get('Sector', 'N/A')}")
            print(f"  Price: ${row.get('Price', 0):.2f}")
            cr = row.get('Curr R', None)
            print(f"  Current Ratio: {cr:.2f}" if cr else "  Current Ratio: N/A")
            fcf = row.get('FCF_Margin', None)
            print(f"  FCF Margin: {fcf:.1f}%" if fcf else "  FCF Margin: N/A")
            quality = row.get('Quality_Score', 0)
            print(f"  Quality Score: {quality:.1f}")

            # Check if would pass quality threshold
            if quality < 30:
                print(f"  [WARN] Quality score {quality:.1f} < 30 threshold (would be excluded)")
            else:
                print(f"  [OK] Quality score {quality:.1f} >= 30 (passes threshold)")

        else:
            missing_count += 1
            print(f"\n[X] {ticker} ({info['name']}) - MISSING")
            print(f"  Expected sector: {info['sector']}")
            print(f"  Possible reasons:")
            print(f"    1. Not in FMP S&P 500 constituent list")
            print(f"    2. Filtered by price/market cap in screener")
            print(f"    3. Filtered by fundamental metrics (CR, FCF, ROE, Debt/Eq)")
            print(f"    4. Check FMP data quality for this ticker")

    print("\n" + "="*70)
    print(f"DIAGNOSTIC COMPLETE: {present_count} present, {missing_count} missing")
    print("="*70 + "\n")


def apply_cyclical_penalty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply penalty to cyclical sectors (Basic Materials, Energy) to reduce
    commodity concentration in the universe.

    Cyclical stocks often have inflated margins at commodity cycle peaks,
    which skews quality scoring toward gold miners and oil companies.

    Penalty: 20% score reduction for stocks in CYCLICAL_SECTORS.

    Args:
        df: DataFrame with Quality_Score and Sector columns

    Returns:
        DataFrame with Cyclical_Penalty applied to Quality_Score
    """
    df = df.copy()

    if 'Sector' not in df.columns:
        print("  [WARN] 'Sector' column not found - skipping cyclical penalty")
        return df

    # Store original scores for reporting
    df['Pre_Penalty_Score'] = df['Quality_Score']

    # Identify cyclical stocks (sectors + crypto + cyclical consumer)
    cyclical_mask = (
        df['Sector'].isin(CYCLICAL_SECTORS) |
        df['Ticker'].isin(CRYPTO_TICKERS) |
        df['Ticker'].isin(CYCLICAL_CONSUMER)
    )
    cyclical_count = cyclical_mask.sum()

    # Identify China ADRs (geopolitical risk)
    china_mask = df['Ticker'].isin(CHINA_ADRS)
    china_count = china_mask.sum()

    # Apply 20% penalty to cyclical stocks
    if cyclical_count > 0:
        df.loc[cyclical_mask, 'Quality_Score'] = df.loc[cyclical_mask, 'Quality_Score'] * CYCLICAL_PENALTY
        print(f"  Applied {int((1-CYCLICAL_PENALTY)*100)}% penalty to {cyclical_count} cyclical/crypto/consumer stocks")

    # Apply 20% penalty to China ADRs
    if china_count > 0:
        df.loc[china_mask, 'Quality_Score'] = df.loc[china_mask, 'Quality_Score'] * GEOPOLITICAL_PENALTY
        print(f"  Applied {int((1-GEOPOLITICAL_PENALTY)*100)}% penalty to {china_count} China ADRs")

    # Show top affected stocks (combined)
    all_penalized = cyclical_mask | china_mask
    if all_penalized.sum() > 0:
        affected = df[all_penalized].nlargest(5, 'Pre_Penalty_Score')[['Ticker', 'Sector', 'Pre_Penalty_Score', 'Quality_Score']]
        if not affected.empty:
            print("  Top affected:")
            for _, row in affected.iterrows():
                if row['Ticker'] in CHINA_ADRS:
                    label = 'China ADR'
                elif row['Ticker'] in CRYPTO_TICKERS:
                    label = 'Crypto'
                elif row['Ticker'] in CYCLICAL_CONSUMER:
                    label = 'Cyclical Consumer'
                else:
                    label = row['Sector']
                print(f"    {row['Ticker']}: {row['Pre_Penalty_Score']:.1f} -> {row['Quality_Score']:.1f} ({label})")

    return df


def calculate_revenue_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate 3-year revenue CAGR and volatility to identify secular businesses.

    Secular businesses have:
    - Positive revenue CAGR (growing)
    - Low revenue volatility (<15% std dev of YoY growth)

    This separates durable compounders from cyclical commodity plays.

    Args:
        df: DataFrame with Ticker column

    Returns:
        DataFrame with added columns:
        - Revenue_CAGR: 3-year compound annual growth rate (%)
        - Revenue_Volatility: Std dev of YoY growth rates (%)
        - Revenue_Score: Percentile-based score (0-1)
    """
    print("\n[Step 3.7/7] Calculating revenue consistency (3-year trend)...")

    fetcher = create_fetcher()

    df = df.copy()
    df['Revenue_CAGR'] = np.nan
    df['Revenue_Volatility'] = np.nan
    df['Revenue_Score'] = 0.5  # Neutral default for missing data

    success_count = 0
    for idx, row in df.iterrows():
        ticker = row['Ticker']

        try:
            # Fetch 4 years of income statements (gives 3 YoY growth rates)
            statements = fetcher.get_historical_income_statements(ticker, periods=4)

            if statements and len(statements) >= 3:
                revenues = [s.get('revenue', 0) for s in statements[:4]]
                revenues = [r for r in revenues if r and r > 0]

                if len(revenues) >= 3:
                    # Calculate CAGR: (End/Start)^(1/years) - 1
                    years = len(revenues) - 1
                    start_rev = revenues[-1]  # Oldest
                    end_rev = revenues[0]     # Most recent

                    if start_rev > 0:
                        cagr = ((end_rev / start_rev) ** (1/years) - 1) * 100
                        df.at[idx, 'Revenue_CAGR'] = cagr

                        # Calculate volatility (std dev of YoY growth rates)
                        yoy_growths = []
                        for i in range(len(revenues) - 1):
                            if revenues[i+1] > 0:
                                yoy = (revenues[i] / revenues[i+1] - 1) * 100
                                yoy_growths.append(yoy)

                        if len(yoy_growths) >= 2:
                            volatility = np.std(yoy_growths)
                            df.at[idx, 'Revenue_Volatility'] = volatility

                        success_count += 1

        except Exception as e:
            # Silent fail - some stocks won't have data
            continue

    # Calculate percentile-based score
    # Higher CAGR = better (60% weight), Lower volatility = better (40% weight)
    cagr_pct = df['Revenue_CAGR'].rank(pct=True, na_option='keep').fillna(0.5)
    vol_pct = (1 - df['Revenue_Volatility'].rank(pct=True, na_option='keep').fillna(0.5))
    df['Revenue_Score'] = cagr_pct * 0.6 + vol_pct * 0.4

    # Summary
    secular_count = ((df['Revenue_CAGR'] > 5) & (df['Revenue_Volatility'] < 15)).sum()
    print(f"  Revenue data found: {success_count}/{len(df)} stocks")
    print(f"  Secular businesses (CAGR >5%, volatility <15%): {secular_count}")

    return df


def calculate_roe_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate 5-year ROE average and consistency (standard deviation).

    High quality = high average ROE with low volatility.
    Example:
    - Stock A: ROE = [14%, 15%, 16%, 15%, 14%] -> Consistent (good)
    - Stock B: ROE = [5%, 25%, 8%, 30%, 10%] -> Erratic (bad)

    Args:
        df: DataFrame with Ticker column

    Returns:
        DataFrame with added columns:
        - ROE_Avg_5Y: 5-year average ROE (%)
        - ROE_Std_5Y: Standard deviation of ROE (%)
        - ROE_Consistency_Score: Percentile-based score (0-1)
    """
    print("\n[Step 3.8/7] Calculating ROE consistency (5-year stability)...")

    fetcher = create_fetcher()

    df = df.copy()
    df['ROE_Avg_5Y'] = np.nan
    df['ROE_Std_5Y'] = np.nan
    df['ROE_Consistency_Score'] = 0.5  # Neutral default for missing data

    success_count = 0
    for idx, row in df.iterrows():
        ticker = row['Ticker']

        try:
            # Fetch 5 years of key metrics
            metrics = fetcher.get_historical_key_metrics(ticker, periods=5)

            if metrics and len(metrics) >= 3:
                roes = []
                for m in metrics[:5]:
                    roe = m.get('returnOnEquity')
                    if roe is not None and roe > -1.0:  # Filter invalid (>-100%)
                        roes.append(roe * 100)  # Convert to percentage

                if len(roes) >= 3:
                    avg_roe = np.mean(roes)
                    std_roe = np.std(roes)

                    df.at[idx, 'ROE_Avg_5Y'] = avg_roe
                    df.at[idx, 'ROE_Std_5Y'] = std_roe
                    success_count += 1

        except Exception as e:
            continue

    # Calculate percentile-based score
    # Higher avg ROE = better (70% weight), Lower std dev = better (30% weight)
    roe_avg_pct = df['ROE_Avg_5Y'].rank(pct=True, na_option='keep').fillna(0.5)
    roe_std_pct = (1 - df['ROE_Std_5Y'].rank(pct=True, na_option='keep').fillna(0.5))
    df['ROE_Consistency_Score'] = roe_avg_pct * 0.7 + roe_std_pct * 0.3

    # Summary
    consistent_count = ((df['ROE_Avg_5Y'] > 15) & (df['ROE_Std_5Y'] < 5)).sum()
    print(f"  ROE data found: {success_count}/{len(df)} stocks")
    print(f"  Consistent performers (avg >15%, std <5%): {consistent_count}")

    return df


def enforce_sector_diversity(candidates: List[str], df: pd.DataFrame, tier_size: int = 7) -> List[str]:
    """
    Select stocks while enforcing sector diversity constraints.

    Constraints (from SECTOR_DIVERSITY_CONSTRAINTS):
    - Max 2 stocks per sector
    - Min 3 different sectors
    - Max 2 cyclicals (Energy + Basic Materials combined)

    Algorithm:
    1. Sort by Quality_Score descending
    2. Add stocks if sector_count[sector] < max_per_sector
    3. Skip if adding would exceed cyclical limit
    4. Continue until tier_size reached or candidates exhausted

    Args:
        candidates: List of ticker symbols (pre-sorted by quality)
        df: DataFrame with Ticker, Sector, Quality_Score
        tier_size: Target number of stocks for this tier

    Returns:
        List of selected tickers meeting diversity constraints
    """
    max_per_sector = SECTOR_DIVERSITY_CONSTRAINTS['max_per_sector']
    max_cyclical = SECTOR_DIVERSITY_CONSTRAINTS['max_cyclical_total']

    selected = []
    sector_counts = {}
    cyclical_count = 0

    for ticker in candidates:
        if len(selected) >= tier_size:
            break

        # Get sector for this stock
        stock_row = df[df['Ticker'] == ticker]
        if stock_row.empty:
            continue

        sector = stock_row['Sector'].iloc[0]
        is_cyclical = sector in CYCLICAL_SECTORS or ticker in CRYPTO_TICKERS or ticker in CYCLICAL_CONSUMER

        # Check sector limit
        current_sector_count = sector_counts.get(sector, 0)
        if current_sector_count >= max_per_sector:
            continue

        # Check cyclical limit
        if is_cyclical and cyclical_count >= max_cyclical:
            continue

        # Add stock
        selected.append(ticker)
        sector_counts[sector] = current_sector_count + 1
        if is_cyclical:
            cyclical_count += 1

    return selected


def print_sector_composition(tier_stocks: List[str], df: pd.DataFrame, tier_name: str):
    """
    Print sector breakdown and diversity check results.

    Example output:
    TIER 1 SECTOR COMPOSITION:
    - Healthcare: 2 stocks (28.6%) - CVS, PFE
    - Financial Services: 2 stocks (28.6%) - WFC, USB
    ...

    DIVERSITY CHECKS:
    [OK] Max per sector: 2/2
    [OK] Min sectors: 5/3
    [OK] Max cyclicals: 1/2
    """
    print(f"\n  {tier_name} SECTOR COMPOSITION:")

    if not tier_stocks:
        print("    (empty)")
        return

    # Get sector data
    tier_df = df[df['Ticker'].isin(tier_stocks)][['Ticker', 'Sector', 'Quality_Score']]
    sector_groups = tier_df.groupby('Sector')['Ticker'].apply(list).to_dict()

    # Print breakdown
    total_stocks = len(tier_stocks)
    for sector, tickers in sorted(sector_groups.items(), key=lambda x: -len(x[1])):
        pct = len(tickers) / total_stocks * 100
        ticker_str = ', '.join(tickers[:3])
        if len(tickers) > 3:
            ticker_str += f" +{len(tickers)-3} more"
        print(f"    {sector}: {len(tickers)} ({pct:.0f}%) - {ticker_str}")

    # Diversity checks
    max_per_sector = SECTOR_DIVERSITY_CONSTRAINTS['max_per_sector']
    min_sectors = SECTOR_DIVERSITY_CONSTRAINTS['min_sectors']
    max_cyclical = SECTOR_DIVERSITY_CONSTRAINTS['max_cyclical_total']

    actual_max = max(len(t) for t in sector_groups.values()) if sector_groups else 0
    actual_sectors = len(sector_groups)
    cyclical_tickers = tier_df[tier_df['Sector'].isin(CYCLICAL_SECTORS)]['Ticker'].tolist()
    actual_cyclical = len(cyclical_tickers)

    print(f"\n  DIVERSITY CHECKS:")
    print(f"    {'[OK]' if actual_max <= max_per_sector else '[WARN]'} Max per sector: {actual_max}/{max_per_sector}")
    print(f"    {'[OK]' if actual_sectors >= min_sectors else '[WARN]'} Min sectors: {actual_sectors}/{min_sectors}")
    print(f"    {'[OK]' if actual_cyclical <= max_cyclical else '[WARN]'} Cyclicals: {actual_cyclical}/{max_cyclical}", end="")
    if cyclical_tickers:
        print(f" ({', '.join(cyclical_tickers)})")
    else:
        print()


def calculate_advanced_scoring_bonus(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add bonus/penalty points based on advanced features.

    Bonuses (available on FMP Starter plan):
    +5 Financial health (Z > 3.0 AND Piotroski >= 7)
    +3 Strong analyst buy (Buy% > 70%)
    +5 Elite analyst buy (Buy% > 80%)

    NOTE: Insider/institutional bonuses disabled - endpoints not available on Starter plan.

    Args:
        df: DataFrame with advanced data and base Quality_Score

    Returns:
        DataFrame with Advanced_Bonus column and updated Quality_Score
    """
    print("\n[Step 3.5/7] Calculating advanced scoring bonuses...")

    df = df.copy()
    df['Advanced_Bonus'] = 0.0

    # Only process stocks with advanced data
    has_data = df['Altman_Z'].notna()

    if has_data.sum() == 0:
        print("  No stocks with advanced data, skipping bonuses")
        return df

    for idx in df[has_data].index:
        bonus = 0

        # Financial health bonus
        z_score = df.loc[idx, 'Altman_Z']
        piotroski = df.loc[idx, 'Piotroski']
        if z_score is not None and piotroski is not None:
            if z_score > 3.0 and piotroski >= 7:
                bonus += ADVANCED_SCORING_WEIGHTS['financial_health_bonus']

        # NOTE: Insider trading bonuses/penalties skipped (FMP Starter plan limitation)
        # NOTE: Institutional ownership bonuses/penalties skipped (FMP Starter plan limitation)

        # Analyst rating bonuses (available on Starter plan)
        buy_pct = df.loc[idx, 'Analyst_Buy_Pct']
        if buy_pct is not None:
            if buy_pct > 80:
                bonus += ADVANCED_SCORING_WEIGHTS['elite_analyst_buy_bonus']
            elif buy_pct > 70:
                bonus += ADVANCED_SCORING_WEIGHTS['strong_analyst_buy_bonus']

        df.loc[idx, 'Advanced_Bonus'] = bonus

    # Add bonus to Quality_Score
    df['Quality_Score'] = df['Quality_Score'] + df['Advanced_Bonus']

    # Summary statistics
    bonus_stats = df[has_data]['Advanced_Bonus'].describe()
    print(f"  Bonus distribution: min={bonus_stats['min']:.0f}, max={bonus_stats['max']:.0f}, mean={bonus_stats['mean']:.1f}")

    positive_bonus = (df['Advanced_Bonus'] > 0).sum()
    neutral = (df['Advanced_Bonus'] == 0).sum()
    print(f"  Stocks with positive bonus: {positive_bonus}")
    print(f"  Stocks with neutral bonus: {neutral}")

    return df


# =============================================================================
# SINGLE UNIVERSE ASSIGNMENT (Replaces Tier-Based Assignment)
# =============================================================================

def assign_single_universe(df: pd.DataFrame, limit: int = 25) -> List[str]:
    """
    Select top N quality-ranked stocks for single unified universe.
    No price segmentation - quality is the sole ranking criterion.

    Enforces sector diversity:
    - Max 3 stocks per sector
    - No sector >30% of universe
    - Max 2 cyclicals (Energy + Basic Materials)
    - Min 4 different sectors

    Args:
        df: DataFrame with Quality_Score and Sector columns
        limit: Target universe size (default: 25)

    Returns:
        List of selected ticker symbols
    """
    print(f"\n[Step 4/7] Building single quality universe (target: {limit} stocks)...")

    # Sort all stocks by quality score (descending)
    candidates = df.sort_values('Quality_Score', ascending=False)['Ticker'].tolist()

    print(f"  Total candidates: {len(candidates)} stocks")
    print(f"  Price range: ${df['Price'].min():.0f} - ${df['Price'].max():.0f}")

    # === DEBUG: Track blue-chip positions in candidate pool ===
    BLUE_CHIP_TICKERS = ['KO', 'PG', 'WMT', 'JNJ', 'PFE', 'CVS', 'JPM', 'WFC', 'BAC', 'USB',
                        'MSFT', 'AAPL', 'GOOGL', 'V', 'MA', 'UNH', 'MRK', 'ABBV']
    print(f"\n  === DEBUG: Blue-chip positions in candidate pool (by Quality_Score) ===")
    for bc in BLUE_CHIP_TICKERS:
        if bc in candidates:
            pos = candidates.index(bc) + 1
            score = df[df['Ticker'] == bc]['Quality_Score'].iloc[0]
            sector = df[df['Ticker'] == bc]['Sector'].iloc[0]
            print(f"    #{pos:3d}: {bc:5s} (Score: {score:5.1f}, Sector: {sector})")
        else:
            print(f"    [X] {bc} - NOT in candidate pool (filtered out earlier)")

    # === DEBUG: Show top 35 candidates ===
    print(f"\n  === DEBUG: Top 35 candidates by Quality_Score ===")
    for i, ticker in enumerate(candidates[:35], 1):
        row = df[df['Ticker'] == ticker].iloc[0]
        score = row['Quality_Score']
        sector = row['Sector']
        is_cyclical = sector in CYCLICAL_SECTORS or ticker in CRYPTO_TICKERS or ticker in CYCLICAL_CONSUMER
        cyc_flag = " [CYCLICAL]" if is_cyclical else ""
        print(f"    #{i:2d}: {ticker:5s} Score={score:5.1f} Sector={sector}{cyc_flag}")

    # Apply enhanced sector diversity constraints
    max_per_sector = SECTOR_DIVERSITY_CONSTRAINTS['max_per_sector']
    max_sector_pct = SECTOR_DIVERSITY_CONSTRAINTS.get('max_sector_pct', 0.30)
    max_cyclical = SECTOR_DIVERSITY_CONSTRAINTS['max_cyclical_total']

    selected = []
    sector_counts = {}
    cyclical_count = 0
    MIN_QUALITY_THRESHOLD = MIN_QUALITY_FLOOR  # Use global quality floor (48)

    # === DEBUG: Track rejections ===
    rejections = {
        'quality_threshold': [],
        'sector_limit': [],
        'cyclical_limit': [],
    }

    print(f"\n  === DEBUG: Selection loop (max_per_sector={max_per_sector}, max_cyclical={max_cyclical}) ===")

    for ticker in candidates:
        if len(selected) >= limit:
            break

        stock_row = df[df['Ticker'] == ticker]
        if stock_row.empty:
            continue

        quality_score = stock_row['Quality_Score'].iloc[0]
        sector = stock_row['Sector'].iloc[0]
        is_cyclical = sector in CYCLICAL_SECTORS or ticker in CRYPTO_TICKERS or ticker in CYCLICAL_CONSUMER

        # Check minimum quality threshold
        if quality_score < MIN_QUALITY_THRESHOLD:
            rejections['quality_threshold'].append((ticker, quality_score, sector))
            continue

        current_sector_count = sector_counts.get(sector, 0)
        # Dynamic max: either max_per_sector or max_sector_pct of target, whichever is smaller
        max_for_sector = min(max_per_sector, int(limit * max_sector_pct))

        # Check sector limits
        if current_sector_count >= max_for_sector:
            rejections['sector_limit'].append((ticker, quality_score, sector, current_sector_count))
            continue

        # Check cyclical limit
        if is_cyclical and cyclical_count >= max_cyclical:
            rejections['cyclical_limit'].append((ticker, quality_score, sector))
            continue

        selected.append(ticker)
        sector_counts[sector] = current_sector_count + 1
        if is_cyclical:
            cyclical_count += 1

    # === DEBUG: Print rejection summary ===
    print(f"\n  === DEBUG: Rejection Summary ===")
    print(f"    Selected in main loop: {len(selected)} stocks")
    print(f"    Rejected for quality < {MIN_QUALITY_THRESHOLD}: {len(rejections['quality_threshold'])}")
    print(f"    Rejected for sector limit: {len(rejections['sector_limit'])}")
    print(f"    Rejected for cyclical limit: {len(rejections['cyclical_limit'])}")

    # Show sector limit rejections (these are likely the cause of 18 stocks)
    if rejections['sector_limit']:
        print(f"\n  === DEBUG: Stocks rejected due to SECTOR LIMIT (first 20) ===")
        for ticker, score, sector, count in rejections['sector_limit'][:20]:
            print(f"    {ticker:5s} Score={score:5.1f} Sector={sector} (already had {count}/{max_for_sector})")

    # Show cyclical rejections
    if rejections['cyclical_limit']:
        print(f"\n  === DEBUG: Stocks rejected due to CYCLICAL LIMIT ===")
        for ticker, score, sector in rejections['cyclical_limit'][:10]:
            print(f"    {ticker:5s} Score={score:5.1f} Sector={sector}")

    # Show quality rejections if any blue-chips are there
    blue_chip_quality_rejects = [(t, s, sec) for t, s, sec in rejections['quality_threshold'] if t in BLUE_CHIP_TICKERS]
    if blue_chip_quality_rejects:
        print(f"\n  === DEBUG: BLUE-CHIPS rejected for quality ===")
        for ticker, score, sector in blue_chip_quality_rejects:
            print(f"    {ticker:5s} Score={score:5.1f} Sector={sector} (below {MIN_QUALITY_THRESHOLD})")

    # Enforce required sector minimums
    required = SECTOR_DIVERSITY_CONSTRAINTS.get('required_minimum', {})
    if required:
        print("\n  Enforcing required sector minimums...")
        for req_sector, min_count in required.items():
            current = sector_counts.get(req_sector, 0)
            if current < min_count:
                shortage = min_count - current
                print(f"    {req_sector}: {current}/{min_count} - need {shortage} more")

                # Find best candidates from required sector not yet selected (with quality threshold)
                # For Financial Services, exclude crypto tickers (they count as cyclical, not real financials)
                base_filter = (
                    (df['Sector'] == req_sector) &
                    (~df['Ticker'].isin(selected)) &
                    (df['Quality_Score'] >= MIN_QUALITY_THRESHOLD)
                )
                if req_sector == 'Financial Services':
                    base_filter = base_filter & (~df['Ticker'].isin(CRYPTO_TICKERS))

                sector_candidates = df[base_filter].nlargest(shortage, 'Quality_Score')['Ticker'].tolist()

                if len(sector_candidates) == 0:
                    print(f"      [WARN] No quality candidates (score >= {MIN_QUALITY_THRESHOLD}) for {req_sector}")
                    continue

                # Add or swap to meet requirement
                for new_ticker in sector_candidates:
                    if len(selected) >= limit:
                        # Need to swap - find lowest score from non-required sector
                        swap_candidates = [
                            t for t in selected
                            if df[df['Ticker'] == t]['Sector'].iloc[0] not in required
                        ]
                        if swap_candidates:
                            scores = {t: df[df['Ticker'] == t]['Quality_Score'].iloc[0]
                                      for t in swap_candidates}
                            to_remove = min(scores, key=scores.get)
                            old_sector = df[df['Ticker'] == to_remove]['Sector'].iloc[0]

                            print(f"      Swap: {to_remove} ({old_sector}) -> {new_ticker}")
                            selected.remove(to_remove)
                            sector_counts[old_sector] -= 1

                    selected.append(new_ticker)
                    sector_counts[req_sector] = sector_counts.get(req_sector, 0) + 1

    # Fallback if still under target size (respect all constraints including quality)
    if len(selected) < limit:
        shortage = limit - len(selected)
        print(f"\n  [WARN] Only {len(selected)}/{limit} stocks - adding up to {shortage} more")

        remaining = [t for t in candidates if t not in selected]
        for ticker in remaining:
            if len(selected) >= limit:
                break
            stock_row = df[df['Ticker'] == ticker]
            if not stock_row.empty:
                quality_score = stock_row['Quality_Score'].iloc[0]
                sector = stock_row['Sector'].iloc[0]
                is_cyclical = sector in CYCLICAL_SECTORS or ticker in CRYPTO_TICKERS or ticker in CYCLICAL_CONSUMER
                current_sector_count = sector_counts.get(sector, 0)

                # Skip if below quality threshold
                if quality_score < MIN_QUALITY_THRESHOLD:
                    continue

                # Skip if adding would exceed sector limit
                if current_sector_count >= max_for_sector:
                    continue

                # Skip if adding would exceed cyclical limit
                if is_cyclical and cyclical_count >= max_cyclical:
                    continue

                selected.append(ticker)
                sector_counts[sector] = current_sector_count + 1
                if is_cyclical:
                    cyclical_count += 1
                print(f"    Added: {ticker} ({sector})")

    # Remove duplicate share classes (keep higher volume/primary ticker)
    SHARE_CLASS_DUPLICATES = {
        'GOOGL': 'GOOG',  # Keep GOOGL (Class A), remove GOOG (Class C)
        # Add others if needed: 'BRK.B': 'BRK.A', etc.
    }

    for primary, duplicate in SHARE_CLASS_DUPLICATES.items():
        if primary in selected and duplicate in selected:
            selected.remove(duplicate)
            # Update sector count
            dup_sector = df[df['Ticker'] == duplicate]['Sector'].iloc[0]
            sector_counts[dup_sector] = sector_counts.get(dup_sector, 1) - 1
            print(f"\n  Removed duplicate: {duplicate} (keeping {primary})")

    # Calculate statistics for selected universe
    universe_df = df[df['Ticker'].isin(selected)]
    avg_score = universe_df['Quality_Score'].mean()
    min_price = universe_df['Price'].min()
    max_price = universe_df['Price'].max()
    median_price = universe_df['Price'].median()

    print(f"\n  WHEEL_UNIVERSE: {len(selected)} stocks")
    print(f"  Average Quality Score: {avg_score:.1f}")
    print(f"  Price range: ${min_price:.0f} - ${max_price:.0f} (median: ${median_price:.0f})")

    # Print sector composition
    print_sector_composition(selected, df, "WHEEL_UNIVERSE")

    # Print capital requirements by price bracket
    print("\n  Capital requirements per position (Price × 100):")
    price_brackets = [
        (0, 50, "Under $50"),
        (50, 100, "$50-100"),
        (100, 150, "$100-150"),
        (150, 300, "$150-300"),
        (300, float('inf'), "$300+")
    ]

    for min_p, max_p, label in price_brackets:
        bracket_df = universe_df[(universe_df['Price'] >= min_p) & (universe_df['Price'] < max_p)]
        count = len(bracket_df)
        if count > 0:
            tickers = bracket_df['Ticker'].tolist()
            capital_range = f"${int(min_p * 100):,} - ${int(min(max_p, 300) * 100):,}"
            print(f"    {label}: {count} stocks ({capital_range}) - {', '.join(tickers[:5])}")

    return selected


def validate_single_universe(universe: List[str], df: pd.DataFrame) -> bool:
    """
    Validate single universe meets quality and diversity requirements.

    Checks:
    - Minimum size (15 stocks)
    - Sector diversity (min 4 sectors)
    - Max cyclicals (≤2)
    - No single sector >30%

    Args:
        universe: List of selected ticker symbols
        df: Full DataFrame with stock metadata

    Returns:
        True if validation passes, False otherwise
    """
    print("\n[Step 5/7] Validating universe...")

    issues = []

    # Check minimum size
    if len(universe) < 15:
        issues.append(f"  [WARN] Universe only has {len(universe)} stocks (minimum: 15)")

    # Get universe data
    universe_df = df[df['Ticker'].isin(universe)]

    # Check sector diversity
    sector_counts = universe_df['Sector'].value_counts()
    num_sectors = len(sector_counts)

    if num_sectors < 4:
        issues.append(f"  [WARN] Only {num_sectors} sectors represented (minimum: 4)")

    # Check sector concentration
    if len(universe) > 0:
        max_sector_pct = sector_counts.max() / len(universe)
        if max_sector_pct > 0.30:
            top_sector = sector_counts.idxmax()
            issues.append(f"  [WARN] {top_sector} is {max_sector_pct:.0%} of universe (max: 30%)")

    # Check cyclicals
    cyclical_count = universe_df[universe_df['Sector'].isin(CYCLICAL_SECTORS)].shape[0]
    if cyclical_count > 2:
        issues.append(f"  [WARN] {cyclical_count} cyclical stocks (max: 2)")

    if issues:
        print("\n".join(issues))
        try:
            response = input("\nProceed anyway? (y/n): ")
            return response.lower() == 'y'
        except EOFError:
            print("   Non-interactive mode: Proceeding with warnings...")
            return True

    print(f"  [OK] Universe size: {len(universe)} stocks")
    print(f"  [OK] Sectors: {num_sectors}")
    print(f"  [OK] Max sector concentration: {sector_counts.max()}/{len(universe)} ({sector_counts.max()/len(universe):.0%})")
    print(f"  [OK] Cyclicals: {cyclical_count}/2")

    return True


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
        print("[WARN]  universe.py not found, will create from scratch")
        return {}

    preserved = {}

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


def generate_universe_content(universe: List[str], preserved: Dict[str, str],
                             stats: Dict[str, int], df: pd.DataFrame) -> str:
    """
    Generate universe.py with single unified universe.

    Args:
        universe: List of selected ticker symbols
        preserved: Dict of preserved content (vol_harvest, excluded, functions)
        stats: Statistics for header (screened, passed)
        df: Full DataFrame with stock metadata

    Returns:
        Complete file content as string
    """
    now = datetime.now()
    next_refresh = now + timedelta(days=14)

    # Create lookup dict for company info with capital requirements
    company_lookup = {}
    for _, row in df.iterrows():
        ticker = row.get('Ticker', '')
        if ticker:
            price = row.get('Price', 0)
            company_lookup[ticker] = {
                'company': row.get('Company', 'Unknown Company'),
                'sector': row.get('Sector', 'Unknown Sector'),
                'score': row.get('Quality_Score', 0.0),
                'price': price,
                'capital': int(price * 100),
                'earnings': row.get('Next_Earnings', None)
            }

    # Format ticker lines with capital requirement
    def format_universe_entry(ticker):
        info = company_lookup.get(ticker, {
            'company': 'Unknown',
            'sector': 'Unknown',
            'score': 0.0,
            'price': 0,
            'capital': 0,
            'earnings': None
        })
        company = info['company'][:30]
        earnings_str = f" | Earnings: {info['earnings']}" if info.get('earnings') else ""
        capital_k = info['capital'] / 1000
        return f'    "{ticker}",  # {company} | {info["sector"]} | ${info["price"]:.0f} | Capital: ${capital_k:.1f}K | Score: {info["score"]:.1f}{earnings_str}'

    universe_entries = '\n'.join([format_universe_entry(t) for t in universe])

    # Generate CAPITAL_REQUIREMENTS dict entries
    capital_entries = '\n'.join([
        f'    "{t}": {company_lookup.get(t, {}).get("capital", 0)},'
        for t in universe
    ])

    content = f'''"""
Pre-defined stock universes for Options Scanner
AUTO-GENERATED by universe_builder.py on {now.strftime('%Y-%m-%d %H:%M:%S')}
Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d')}

SINGLE UNIVERSE ARCHITECTURE
Quality-ranked stocks across all price ranges. No artificial tier segmentation.
Filter by available capital per position using get_wheel_universe(max_capital).

Fundamental screening criteria:
- Market Cap >$10B
- Altman Z-Score >2.0 (bankruptcy safety)
- Piotroski Score >=5 (fundamental quality)
- Debt/Equity <1.0
- ROE >10%
- Current Ratio >1.0
- FCF Margin >2%

Quality scoring (percentile-based):
- Debt/Equity (inverse): 20% weight
- Current Ratio: 15% weight
- ROE Consistency (5yr): 15% weight
- FCF Margin: 15% weight
- Revenue Growth (3yr): 10% weight
- Gross Margin: 10% weight
- Operating Margin: 10% weight
- Volume: 5% weight

Sector diversity enforced:
- Max 3 stocks per sector
- No sector >30% of universe
- Max 2 cyclicals (Energy + Basic Materials)
- Min 4 sectors

Stocks screened: {stats['screened']}
Quality stocks found: {stats['passed']}
Final universe: {len(universe)} stocks
"""

# =============================================================================
# WHEEL STRATEGY UNIVERSE (Single Quality-Focused Universe)
# Quality stocks across all price ranges - filter by capital available
# =============================================================================

WHEEL_UNIVERSE = [
{universe_entries}
]

# Capital requirement per contract (Price x 100 for 1 CSP)
CAPITAL_REQUIREMENTS = {{
{capital_entries}
}}

# =============================================================================
# EXCLUDED TICKERS
# [PRESERVED FROM EXISTING FILE - DO NOT MODIFY]
# =============================================================================

{preserved.get('excluded', 'EXCLUDED_TICKERS = [\\n    # Biotech with pending FDA decisions (add as needed)\\n    # M&A targets (add as needed)\\n    # Delisting candidates (add as needed)\\n]')}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_wheel_universe(max_capital: int = None) -> list:
    \"\"\"
    Get Wheel universe, optionally filtered by available capital.

    Args:
        max_capital: Maximum capital per position in dollars (optional)
                    e.g., 10000 filters to stocks with price <= $100

    Returns:
        List of tickers affordable within capital constraint

    Examples:
        >>> get_wheel_universe()              # All stocks
        >>> get_wheel_universe(5000)          # Stocks up to $50
        >>> get_wheel_universe(10000)         # Stocks up to $100
        >>> get_wheel_universe(25000)         # Stocks up to $250
    \"\"\"
    if max_capital is None:
        return WHEEL_UNIVERSE

    return [t for t in WHEEL_UNIVERSE if CAPITAL_REQUIREMENTS.get(t, 0) <= max_capital]


def get_affordable_stocks(max_capital: int) -> list:
    \"\"\"
    Get stocks affordable within capital constraint with details.

    Args:
        max_capital: Maximum capital per position in dollars

    Returns:
        List of (ticker, capital_required) tuples sorted by capital
    \"\"\"
    affordable = [
        (t, CAPITAL_REQUIREMENTS[t])
        for t in WHEEL_UNIVERSE
        if CAPITAL_REQUIREMENTS.get(t, 0) <= max_capital
    ]
    return sorted(affordable, key=lambda x: x[1])


def add_to_excluded(ticker: str):
    \"\"\"Add a ticker to excluded list (runtime only)\"\"\"
    if ticker not in EXCLUDED_TICKERS:
        EXCLUDED_TICKERS.append(ticker)


def format_moomoo_symbol(ticker: str) -> str:
    \"\"\"Convert ticker to MooMoo format (e.g., 'AAPL' -> 'US.AAPL')\"\"\"
    if not ticker.startswith("US."):
        return f"US.{{ticker}}"
    return ticker


def strip_moomoo_prefix(symbol: str) -> str:
    \"\"\"Convert MooMoo format to plain ticker (e.g., 'US.AAPL' -> 'AAPL')\"\"\"
    if symbol.startswith("US."):
        return symbol[3:]
    return symbol
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
            print(f"[OK] Backup created: {backup_path}")
        except FileNotFoundError:
            print("[WARN]  No existing universe.py to backup")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] {output_path} written ({len(content.splitlines())} lines)")


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

# NOTE: validate_results() removed - replaced by validate_single_universe()
# which is defined in the SINGLE UNIVERSE ASSIGNMENT section above.


def check_minimum_results(df: pd.DataFrame):
    """
    Warn if screening returns too few results.

    Args:
        df: Filtered results
    """
    if len(df) < 15:  # Reduced from 60 - need at least 5 per tier
        print(f"\n[WARN]  WARNING: Only {len(df)} stocks passed screening")
        print("   Expected at least 15 stocks minimum (5 per tier)")
        print("   Consider relaxing filters or check if finviz is accessible")
        # Try to get user input, but continue if non-interactive
        try:
            response = input("\nContinue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborted. No changes made to universe.py")
                exit(0)
        except EOFError:
            print("\n   Non-interactive mode: Continuing with limited universe...")
    elif len(df) < 60:
        print(f"\n[WARN]  NOTE: {len(df)} stocks passed screening (target: 60)")
        print("   This may result in fewer than 20 stocks per tier")
        print("   Consider relaxing filters in FINVIZ_FILTERS if more stocks needed")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main execution function."""
    global logger

    args = parse_arguments()
    print_banner()

    # Initialize logging
    logger = setup_logging(verbose=args.verbose)
    logger.info("="*70)
    logger.info("Universe Builder Starting")
    logger.info("="*70)
    logger.info(f"Arguments: {vars(args)}")

    validation_summary = {
        'schema_check': 'PENDING',
        'completeness_check': 'PENDING',
        'outlier_detection': 'PENDING',
        'earnings_validation': 'PENDING',
        'fcf_validation': 'PENDING',
    }

    try:
        # =====================================================================
        # DIAGNOSTIC: Run blue-chip availability test FIRST
        # =====================================================================
        print("\n" + "="*80)
        print("STARTING DIAGNOSTIC MODE")
        print("="*80)

        fetcher = create_fetcher()
        available, filtered_out, missing = test_blue_chip_availability(fetcher)

        # Decision point based on results
        use_direct_fetch = False
        if len(available) >= 10:
            print("\n[RECOMMENDATION] FMP has blue-chip data")
            print("                 Proceeding with standard screener")
        elif len(available) + len(filtered_out) >= 10:
            print("\n[RECOMMENDATION] FMP has data but filters too strict")
            print("                 Will fetch blue-chips directly and merge with screener")
            use_direct_fetch = True
        else:
            print("\n[CRITICAL] FMP missing too much data")
            print("           Proceeding with available stocks only")

        # Step 1: Fetch data from FMP (replaces Finviz)
        df = fetch_stocks_from_fmp()

        # If blue-chips were filtered out, fetch them directly and merge
        if use_direct_fetch and (available or filtered_out):
            blue_chip_tickers = available + filtered_out
            df_blue_chips = fetch_blue_chips_directly(fetcher, blue_chip_tickers)

            if not df_blue_chips.empty:
                # Merge with screener results, avoiding duplicates
                existing_tickers = set(df['Ticker'].values)
                new_blue_chips = df_blue_chips[~df_blue_chips['Ticker'].isin(existing_tickers)]

                if not new_blue_chips.empty:
                    print(f"\n[MERGE] Adding {len(new_blue_chips)} blue-chip stocks not in screener")
                    df = pd.concat([df, new_blue_chips], ignore_index=True)
                    print(f"        Total stocks after merge: {len(df)}")

        total_screened = len(df)

        # VALIDATION STEP 1: Schema validation (fail loudly if finviz changed columns)
        validate_schema(df)
        validation_summary['schema_check'] = 'PASSED'

        # Step 2: Apply post-screening filters
        df = apply_post_screening_filters(df)

        # Diagnostic: Check why expected blue-chip stocks might be missing
        diagnose_missing_blue_chips(df)

        # VALIDATION STEP 2: Data completeness check (fail if >10% missing)
        validate_data_completeness(df)
        validation_summary['completeness_check'] = 'PASSED'

        # VALIDATION STEP 3: Outlier detection (remove finviz glitches)
        df = detect_and_remove_outliers(df)
        validation_summary['outlier_detection'] = 'PASSED'

        total_passed = len(df)

        # NOTE: FMP already provides earnings dates in Next_Earnings column
        # No need for yfinance enrichment - skip enrich_with_next_earnings()
        earnings_count = df['Next_Earnings'].notna().sum() if 'Next_Earnings' in df.columns else 0
        earnings_rate = earnings_count / len(df) if len(df) > 0 else 0
        print(f"\n[VALIDATION] Earnings dates from FMP: {earnings_count}/{len(df)} ({earnings_rate:.1%})")
        validation_summary['earnings_validation'] = 'PASSED'

        # NOTE: FMP already provides FCF data in FCF and FCF_Margin columns
        # No need for yfinance FCF validation - skip validate_free_cash_flow()
        # Apply FCF filter as post-screening filter instead
        # EXEMPT Financial Services: Banks don't have traditional FCF (deposits/lending based)
        # EXEMPT Consumer Defensive: Retailers (WMT, COST) operate on thin margins by design
        #                            High volume / low margin is their business model
        if 'FCF' in df.columns and 'FCF_Margin' in df.columns:
            fcf_exempt_sectors = ['Financial Services', 'Consumer Defensive']
            is_exempt = df['Sector'].isin(fcf_exempt_sectors)
            # For non-exempt sectors: require FCF > 0 AND margin > 2%
            fcf_mask = is_exempt | ((df['FCF'] > 0) & (df['FCF_Margin'] > 2.0))
            fcf_passed = fcf_mask.sum()
            fcf_exempt_count = is_exempt.sum()
            df = df[fcf_mask]
            print(f"\n[VALIDATION] FCF validation (FCF >0 AND margin >2%): {fcf_passed}/{len(df) + (len(df) == 0)} passed ({fcf_exempt_count} exempt: Financial Services, Consumer Defensive)")
        validation_summary['fcf_validation'] = 'PASSED'

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

        # ═══════════════════════════════════════════════════════════════
        # WEEK 2 ADVANCED FEATURES INTEGRATION
        # ═══════════════════════════════════════════════════════════════

        # Fetch advanced data for top 80 candidates (increased from 50)
        # Utilities and banks score lower on margins but are critical for defensive allocation
        df = fetch_advanced_data_for_top_stocks(df, top_n=80)

        # Apply advanced filters (Altman Z, Piotroski, Analyst Buy%)
        df = apply_advanced_filters(df)

        # Check we still have enough stocks after advanced filtering
        check_minimum_results(df)

        # Recalculate quality scores for filtered dataset
        print("\n[Step 3.5/7] Recalculating quality scores with advanced bonuses...")
        df = calculate_quality_scores_percentile(df)
        df = add_volume_percentile(df)

        # Add advanced scoring bonuses
        df = calculate_advanced_scoring_bonus(df)

        # Apply cyclical sector penalty (reduce commodity concentration)
        print("\n[Step 3.6/7] Applying cyclical sector penalty...")
        df = apply_cyclical_penalty(df)

        # === DEBUG: PG-specific metric analysis ===
        PG_DIAGNOSTIC_TICKERS = ['PG', 'KO', 'WMT', 'JNJ', 'JPM', 'WFC']
        print("\n  === DEBUG: Key blue-chip score breakdown ===")
        for ticker in PG_DIAGNOSTIC_TICKERS:
            if ticker in df['Ticker'].values:
                row = df[df['Ticker'] == ticker].iloc[0]
                print(f"\n    {ticker} ({row.get('Sector', 'N/A')}) - Total Score: {row.get('Quality_Score', 0):.1f}")
                print(f"      Raw Metrics:")
                print(f"        Oper M: {row.get('Oper M', 'N/A')}")
                print(f"        ROE: {row.get('ROE', 'N/A')}")
                print(f"        Curr R: {row.get('Curr R', 'N/A')}")
                print(f"        Debt/Eq: {row.get('Debt/Eq', 'N/A')}")
                print(f"        Gross M: {row.get('Gross M', 'N/A')}")
                print(f"        FCF_Margin: {row.get('FCF_Margin', 'N/A')}")
                print(f"      Component Scores:")
                print(f"        OM_Score: {row.get('OM_Score', 0):.1f}/15")
                print(f"        ROE_Score: {row.get('ROE_Score', 0):.1f}/15")
                print(f"        CR_Score: {row.get('CR_Score', 0):.1f}/15")
                print(f"        DE_Score: {row.get('DE_Score', 0):.1f}/20")
                print(f"        GM_Score: {row.get('GM_Score', 0):.1f}/10")
                print(f"        FCF_Score: {row.get('FCF_Score', 0):.1f}/10")
                print(f"        Volume_Score: {row.get('Volume_Score', 0):.1f}/15")
            else:
                print(f"\n    {ticker} - NOT in dataset (filtered out)")

        # Calculate business durability metrics (revenue/ROE consistency)
        df = calculate_revenue_consistency(df)
        df = calculate_roe_consistency(df)

        # ═══════════════════════════════════════════════════════════════

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

        # ═══════════════════════════════════════════════════════════════
        # DIAGNOSTIC: Earnings Column in Final DataFrame
        # ═══════════════════════════════════════════════════════════════
        print("\n[DIAGNOSTIC] Checking earnings in final dataframe...")

        # Find earnings column
        earnings_col = None
        for col in df.columns:
            if 'earn' in col.lower():
                earnings_col = col
                break

        if earnings_col:
            print(f"[OK] Found earnings column: '{earnings_col}'")

            # Show earnings data
            print("\n[DEBUG] Upcoming earnings:")
            earnings_display = df[['Ticker', earnings_col]].copy()

            # Filter to non-null, non-empty, non-dash values
            mask = (
                earnings_display[earnings_col].notna() &
                (earnings_display[earnings_col] != '') &
                (earnings_display[earnings_col] != '-') &
                (earnings_display[earnings_col].astype(str).str.lower() != 'nan')
            )
            earnings_display = earnings_display[mask]

            if len(earnings_display) > 0:
                print(earnings_display.to_string(index=False))
                print(f"\nTotal stocks with earnings data: {len(earnings_display)}/{len(df)}")
            else:
                print("  [WARN]  WARNING: No valid earnings dates found!")
                print(f"  All values in '{earnings_col}':")
                print(df[['Ticker', earnings_col]].to_string(index=False))
        else:
            print("[ERROR] CRITICAL: No earnings column found in final dataframe!")
            print(f"Available columns: {df.columns.tolist()}")
        # ═══════════════════════════════════════════════════════════════

        # Step 4: Assign to single quality-focused universe
        universe_size = args.universe_size if hasattr(args, 'universe_size') else DEFAULT_LIMITS['universe_size']
        universe = assign_single_universe(df, limit=universe_size)

        # Step 5: Validate
        if not validate_single_universe(universe, df):
            print("Validation failed. Aborting.")
            exit(1)

        # Step 6: Preserve existing content
        print("\n[Step 6/7] Preserving existing content...")
        preserved = read_existing_universe()
        print(f"  [OK] EXCLUDED_TICKERS ({len(preserved.get('excluded', '').split(',')) if 'excluded' in preserved else 0} stocks)")
        print(f"  [OK] Helper functions ({len([line for line in preserved.get('functions', '').splitlines() if line.strip().startswith('def ')]) if 'functions' in preserved else 0} functions)")

        # Step 7: Generate and write file
        print("\n[Step 7/7] Writing to universe.py...")
        stats = {'screened': total_screened, 'passed': total_passed}
        content = generate_universe_content(universe, preserved, stats, df)

        if not args.dry_run:
            write_universe_file(content, args.output, backup=not args.no_backup)
        else:
            print("[OK] Dry run complete - no files written")

        # Summary
        print_summary(df, universe, total_screened, total_passed)

        # Log successful completion
        logger.info("="*70)
        logger.info("VALIDATION SUMMARY:")
        for check, status in validation_summary.items():
            logger.info(f"  {check:25s}: {status}")
        logger.info("="*70)
        logger.info("Universe Builder Completed Successfully")
        logger.info("="*70)

    except KeyError as e:
        logger.error(f"Schema validation failed: {e}")
        logger.error("This likely means Finviz changed their column names.")
        logger.error("Update REQUIRED_COLUMNS constant to match new schema.")
        raise

    except ValueError as e:
        logger.error(f"Data quality validation failed: {e}")
        logger.error("This likely means data completeness or FCF validation failed.")
        logger.error("Check finviz.com directly or try again later.")
        raise

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        logger.error("="*70)
        logger.error("VALIDATION SUMMARY (FAILED):")
        for check, status in validation_summary.items():
            logger.error(f"  {check:25s}: {status}")
        logger.error("="*70)
        raise

    finally:
        if logger:
            logger.info("Universe Builder session ended")


if __name__ == "__main__":
    main()
