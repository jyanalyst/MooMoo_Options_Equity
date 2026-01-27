#!/usr/bin/env python3
"""
Earnings Calendar Monitor - CSV Export Version

Generates weekly earnings calendar CSV for trade planning and journaling.
Categorizes WHEEL_UNIVERSE stocks by earnings proximity:
- AVOID: Earnings <14 days away (do not open new CSPs)
- CAUTION: Earnings 14-30 days away (monitor closely)
- SAFE: Earnings >30 days away or no scheduled earnings

Output:
- CSV file: reports/earnings/earnings_calendar_YYYY-MM-DD.csv
- Color-coded console summary

Usage:
    python earnings_monitor.py              # Generate current week's report
    python earnings_monitor.py --cleanup    # Remove reports older than 10 weeks
    python earnings_monitor.py --console    # Console output only (no CSV)
"""

import os
import sys
import logging
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests

# Import universe and config
from universe import WHEEL_UNIVERSE, CAPITAL_REQUIREMENTS, STOCK_METADATA, get_stock_metadata
from config import FMP_API_KEY

# =============================================================================
# CONFIGURATION
# =============================================================================

# Output directory
REPORTS_DIR = Path(__file__).parent / 'reports' / 'earnings'

# Earnings categorization thresholds (days)
AVOID_THRESHOLD = 14    # <14 days = AVOID
CAUTION_THRESHOLD = 30  # 14-30 days = CAUTION
CALENDAR_HORIZON = 45   # Look ahead 45 days

# Retention policy
RETENTION_DAYS = 70  # Keep reports for 10 weeks

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# FMP API FUNCTIONS
# =============================================================================

def fetch_earnings_for_ticker(ticker: str) -> Optional[str]:
    """
    Fetch next FUTURE earnings date for a single ticker using FMP stable API.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Earnings date string (YYYY-MM-DD) or None if not found/no future earnings
    """
    url = "https://financialmodelingprep.com/stable/earnings-calendar"
    params = {
        'symbol': ticker,
        'apikey': FMP_API_KEY
    }

    today = datetime.now().date()

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            # Look for FUTURE earnings dates
            for event in data:
                date_str = event.get('date')
                if date_str:
                    try:
                        earnings_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if earnings_date > today:
                            return date_str
                    except ValueError:
                        continue
            return None
        return None

    except Exception as e:
        logger.debug(f"Error fetching earnings for {ticker}: {e}")
        return None


def fetch_earnings_batch(tickers: List[str], delay: float = 0.5) -> Dict[str, str]:
    """
    Fetch earnings dates for multiple tickers with rate limiting.

    Args:
        tickers: List of ticker symbols
        delay: Delay between API calls (seconds)

    Returns:
        Dict mapping ticker -> earnings date string
    """
    import time

    earnings_map: Dict[str, str] = {}
    total = len(tickers)

    logger.info(f"Fetching earnings for {total} tickers...")

    for i, ticker in enumerate(tickers, 1):
        if i % 10 == 0:
            logger.info(f"  Progress: {i}/{total} tickers")

        date = fetch_earnings_for_ticker(ticker)
        if date:
            earnings_map[ticker] = date

        if i < total:
            time.sleep(delay)

    logger.info(f"Found earnings dates for {len(earnings_map)}/{total} tickers")
    return earnings_map


# =============================================================================
# CATEGORIZATION LOGIC
# =============================================================================

def categorize_earnings(universe: List[str]) -> List[Dict]:
    """
    Categorize all universe stocks by earnings proximity.

    Args:
        universe: List of ticker symbols

    Returns:
        List of dicts with full stock data and earnings status
    """
    today = datetime.now()

    print(f"\n   Scanning earnings from {today.strftime('%Y-%m-%d')} to {(today + timedelta(days=CALENDAR_HORIZON)).strftime('%Y-%m-%d')}...")

    # Fetch earnings for each ticker
    universe_earnings = fetch_earnings_batch(universe, delay=0.5)

    # Build full dataset with metadata
    results = []

    for ticker in sorted(universe):
        metadata = get_stock_metadata(ticker)

        if ticker in universe_earnings:
            date_str = universe_earnings[ticker]
            try:
                earnings_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_away = (earnings_date - today).days

                # Determine status
                if days_away < AVOID_THRESHOLD:
                    status = 'AVOID'
                    notes = 'Earnings within 14-day buffer - DO NOT open new CSPs'
                elif days_away < CAUTION_THRESHOLD:
                    status = 'CAUTION'
                    notes = 'Monitor closely - may enter AVOID zone'
                else:
                    status = 'SAFE'
                    notes = 'Clear to trade'

                results.append({
                    'ticker': ticker,
                    'company': metadata['company'],
                    'sector': metadata['sector'],
                    'quality_score': metadata['quality_score'],
                    'capital_required': metadata['capital_required'],
                    'earnings_date': date_str,
                    'days_away': days_away,
                    'status': status,
                    'notes': notes
                })

            except ValueError:
                results.append({
                    'ticker': ticker,
                    'company': metadata['company'],
                    'sector': metadata['sector'],
                    'quality_score': metadata['quality_score'],
                    'capital_required': metadata['capital_required'],
                    'earnings_date': date_str,
                    'days_away': '',
                    'status': 'SAFE',
                    'notes': f'Invalid date format: {date_str}'
                })
        else:
            # No future earnings found
            results.append({
                'ticker': ticker,
                'company': metadata['company'],
                'sector': metadata['sector'],
                'quality_score': metadata['quality_score'],
                'capital_required': metadata['capital_required'],
                'earnings_date': '',
                'days_away': '',
                'status': 'SAFE',
                'notes': 'No earnings in next 45 days'
            })

    return results


# =============================================================================
# CSV EXPORT
# =============================================================================

def export_to_csv(data: List[Dict], report_date: str) -> Path:
    """
    Export earnings data to CSV.

    Args:
        data: List of stock data dicts
        report_date: Date string for filename (YYYY-MM-DD)

    Returns:
        Path to created CSV file
    """
    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"earnings_calendar_{report_date}.csv"
    filepath = REPORTS_DIR / filename

    fieldnames = [
        'ticker',
        'company',
        'sector',
        'quality_score',
        'capital_required',
        'earnings_date',
        'days_away',
        'status',
        'notes'
    ]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    logger.info(f"Exported to: {filepath}")
    return filepath


# =============================================================================
# CONSOLE OUTPUT
# =============================================================================

def print_summary(data: List[Dict]):
    """
    Print color-coded console summary.
    """
    avoid = [d for d in data if d['status'] == 'AVOID']
    caution = [d for d in data if d['status'] == 'CAUTION']
    safe = [d for d in data if d['status'] == 'SAFE']

    print("\n" + "="*70)
    print("EARNINGS CALENDAR SUMMARY")
    print("="*70)

    # AVOID section
    print(f"\n   AVOID NEW CSPs ({len(avoid)} stocks)")
    if avoid:
        print("   " + "-"*50)
        print(f"   {'Ticker':<8} {'Date':<12} {'Days':>5}  {'Sector':<20}")
        print("   " + "-"*50)
        for stock in sorted(avoid, key=lambda x: x.get('days_away', 999)):
            days = stock.get('days_away', 'N/A')
            print(f"   {stock['ticker']:<8} {stock['earnings_date']:<12} {days:>5}  {stock['sector']:<20}")
    else:
        print("   All clear - no earnings <14 days!")

    # CAUTION section
    print(f"\n   CAUTION ({len(caution)} stocks)")
    if caution:
        print("   " + "-"*50)
        print(f"   {'Ticker':<8} {'Date':<12} {'Days':>5}  {'Sector':<20}")
        print("   " + "-"*50)
        for stock in sorted(caution, key=lambda x: x.get('days_away', 999)):
            days = stock.get('days_away', 'N/A')
            print(f"   {stock['ticker']:<8} {stock['earnings_date']:<12} {days:>5}  {stock['sector']:<20}")
    else:
        print("   None")

    # SAFE section
    print(f"\n   SAFE TO TRADE ({len(safe)} stocks)")
    safe_tickers = [s['ticker'] for s in safe]
    # Print in rows of 10
    for i in range(0, len(safe_tickers), 10):
        print(f"   {', '.join(safe_tickers[i:i+10])}")

    print("\n" + "="*70)


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup_old_reports():
    """
    Remove reports older than RETENTION_DAYS.

    Returns:
        Number of files deleted
    """
    if not REPORTS_DIR.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0

    for filepath in REPORTS_DIR.glob('earnings_calendar_*.csv'):
        try:
            # Parse date from filename: earnings_calendar_YYYY-MM-DD.csv
            date_str = filepath.stem.replace('earnings_calendar_', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')

            if file_date < cutoff_date:
                filepath.unlink()
                deleted_count += 1
                logger.info(f"Deleted old report: {filepath.name}")

        except (ValueError, IndexError):
            continue

    if deleted_count > 0:
        print(f"\n   Cleaned up {deleted_count} old reports (>{RETENTION_DAYS} days)")

    return deleted_count


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_monitor(console_only: bool = False) -> Dict:
    """
    Run the earnings monitor.

    Args:
        console_only: If True, skip CSV export

    Returns:
        Dict with results
    """
    report_date = datetime.now().strftime('%Y-%m-%d')

    print("\n" + "="*70)
    print(f"EARNINGS CALENDAR MONITOR - {report_date}")
    print(f"Universe: {len(WHEEL_UNIVERSE)} stocks")
    print("="*70)

    # Categorize earnings
    data = categorize_earnings(WHEEL_UNIVERSE)

    # Export to CSV
    filepath = None
    if not console_only:
        filepath = export_to_csv(data, report_date)

    # Print summary
    print_summary(data)

    # Cleanup old files
    cleanup_old_reports()

    if filepath:
        print(f"\n   Report saved: {filepath}")
        print(f"   Use this file when journaling trades to document earnings proximity")

    print("\n" + "="*70 + "\n")

    return {
        'data': data,
        'filepath': filepath,
        'avoid_count': len([d for d in data if d['status'] == 'AVOID']),
        'caution_count': len([d for d in data if d['status'] == 'CAUTION']),
        'safe_count': len([d for d in data if d['status'] == 'SAFE'])
    }


def main():
    """Main entry point with CLI argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Earnings Calendar Monitor - CSV Export Version'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove old reports only (no new report generated)'
    )
    parser.add_argument(
        '--console',
        action='store_true',
        help='Console output only (no CSV export)'
    )

    args = parser.parse_args()

    # Handle cleanup-only mode
    if args.cleanup:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        deleted = cleanup_old_reports()
        if deleted == 0:
            print("No old reports to clean up.")
        return

    # Run monitor
    result = run_monitor(console_only=args.console)

    # Exit with appropriate code
    sys.exit(0)


if __name__ == "__main__":
    main()
