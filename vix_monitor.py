#!/usr/bin/env python3
"""
VIX Regime Monitor - CSV Logging Version

Tracks VIX history and regime changes for trade journaling.
Appends readings to monthly CSV files for historical analysis.

Regimes:
- LOW (<14): Stop trading - premium too low
- NORMAL (14-18): Standard sizing (100%)
- ELEVATED (18-25): Aggressive deployment (150% sizing)
- HIGH (>25): Maximum opportunity - deploy all capital

Output:
- Monthly CSV: reports/vix/vix_history_YYYY-MM.csv
- Console alerts on regime changes

Usage:
    python vix_monitor.py              # Check VIX and log to CSV
    python vix_monitor.py --status     # Show current regime (no logging)
    python vix_monitor.py --history    # Display last 10 checks
"""

import os
import sys
import logging
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import requests

from config import FMP_API_KEY

# =============================================================================
# CONFIGURATION
# =============================================================================

# Output directory
REPORTS_DIR = Path(__file__).parent / 'reports' / 'vix'

# VIX thresholds
VIX_THRESHOLDS = [14, 18, 25]

# Regime definitions
VIX_REGIMES = {
    'LOW': {'min': 0, 'max': 14, 'action': 'Stop trading - premium too low'},
    'NORMAL': {'min': 14, 'max': 18, 'action': 'Standard sizing (100%)'},
    'ELEVATED': {'min': 18, 'max': 25, 'action': 'Aggressive deployment (150% sizing)'},
    'HIGH': {'min': 25, 'max': 999, 'action': 'Maximum opportunity - deploy all capital'}
}

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# VIX DATA FETCHING
# =============================================================================

def get_vix_from_fmp() -> Optional[float]:
    """
    Fetch current VIX level from FMP stable API.

    Returns:
        VIX value as float, or None if fetch fails
    """
    url = "https://financialmodelingprep.com/stable/quote"
    params = {
        'symbol': '^VIX',
        'apikey': FMP_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            vix = data[0].get('price')
            if vix is not None:
                return float(vix)
        return None

    except Exception as e:
        logger.debug(f"FMP VIX fetch failed: {e}")
        return None


def get_vix_from_yfinance() -> Optional[float]:
    """
    Fetch current VIX level from yfinance (fallback).

    Returns:
        VIX value as float, or None if fetch fails
    """
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")

        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return None

    except ImportError:
        logger.debug("yfinance not installed")
        return None
    except Exception as e:
        logger.debug(f"yfinance VIX fetch failed: {e}")
        return None


def fetch_vix() -> Optional[float]:
    """
    Fetch current VIX (tries FMP first, then yfinance).

    Returns:
        VIX value as float, or None if all sources fail
    """
    # Try FMP first
    vix = get_vix_from_fmp()

    if vix is not None:
        logger.info(f"Fetched VIX from FMP: {vix:.2f}")
        return vix

    # Fallback to yfinance
    logger.info("FMP unavailable, trying yfinance...")
    vix = get_vix_from_yfinance()

    if vix is not None:
        logger.info(f"Fetched VIX from yfinance: {vix:.2f}")
        return vix

    logger.error("Could not fetch VIX from any source")
    return None


# =============================================================================
# REGIME LOGIC
# =============================================================================

def get_regime(vix: float) -> str:
    """
    Determine VIX regime from value.

    Args:
        vix: Current VIX value

    Returns:
        Regime name: LOW, NORMAL, ELEVATED, or HIGH
    """
    if vix < 14:
        return 'LOW'
    elif vix < 18:
        return 'NORMAL'
    elif vix < 25:
        return 'ELEVATED'
    else:
        return 'HIGH'


def detect_crossing(old_vix: Optional[float], new_vix: float) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Detect threshold crossing.

    Args:
        old_vix: Previous VIX value
        new_vix: Current VIX value

    Returns:
        (crossed, threshold, direction)
    """
    if old_vix is None:
        return (False, None, None)

    for threshold in VIX_THRESHOLDS:
        if old_vix < threshold <= new_vix:
            return (True, threshold, 'UP')
        if old_vix >= threshold > new_vix:
            return (True, threshold, 'DOWN')

    return (False, None, None)


# =============================================================================
# CSV LOGGING
# =============================================================================

def get_csv_filepath() -> Path:
    """Get path to current month's CSV file."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    current_month = datetime.now().strftime('%Y-%m')
    return REPORTS_DIR / f"vix_history_{current_month}.csv"


def get_last_reading() -> Optional[Dict]:
    """
    Get most recent VIX reading from current month's CSV.

    Returns:
        Dict with vix, regime, timestamp or None
    """
    csv_file = get_csv_filepath()

    if not csv_file.exists():
        return None

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_row = rows[-1]
                return {
                    'vix': float(last_row['vix']),
                    'regime': last_row['regime'],
                    'timestamp': last_row['timestamp']
                }
    except Exception as e:
        logger.debug(f"Error reading last VIX: {e}")

    return None


def append_to_csv(
    vix: float,
    regime: str,
    regime_change: bool,
    threshold: Optional[int],
    direction: Optional[str],
    notes: str = ''
):
    """
    Append VIX reading to monthly CSV.

    Args:
        vix: Current VIX value
        regime: Current regime name
        regime_change: True if regime changed from last reading
        threshold: Threshold crossed (if any)
        direction: UP or DOWN (if threshold crossed)
        notes: Additional notes
    """
    csv_file = get_csv_filepath()
    file_exists = csv_file.exists()

    row = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'vix': f"{vix:.2f}",
        'regime': regime,
        'regime_change': regime_change,
        'threshold_crossed': threshold if threshold else '',
        'direction': direction if direction else '',
        'notes': notes
    }

    fieldnames = ['timestamp', 'vix', 'regime', 'regime_change', 'threshold_crossed', 'direction', 'notes']

    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)

    logger.info(f"Logged to: {csv_file.name}")


# =============================================================================
# CONSOLE OUTPUT
# =============================================================================

def print_regime_alert(
    vix: float,
    regime: str,
    old_vix: Optional[float],
    old_regime: Optional[str],
    threshold: int,
    direction: str
):
    """Print console alert for regime change."""
    print("\n" + "="*70)
    print("   VIX REGIME CHANGE DETECTED")
    print("="*70)
    print(f"")
    print(f"   Previous VIX:  {old_vix:.2f} ({old_regime})" if old_vix else "   Previous VIX:  N/A")
    print(f"   Current VIX:   {vix:.2f} ({regime})")
    print(f"")
    print(f"   Threshold crossed: {threshold} ({direction})")
    print(f"")
    print(f"   ACTION REQUIRED:")
    print(f"   {VIX_REGIMES[regime]['action']}")
    print("")
    print("="*70 + "\n")


def show_history(n: int = 10):
    """Display last N VIX readings."""
    csv_file = get_csv_filepath()

    if not csv_file.exists():
        print("\n   No history available for current month")
        return

    print(f"\n   Last {n} VIX readings:")
    print("   " + "-"*70)
    print(f"   {'Timestamp':<20} {'VIX':>6} {'Regime':<10} {'Change':<8} {'Notes':<20}")
    print("   " + "-"*70)

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        for row in rows[-n:]:
            change_mark = "  *" if row['regime_change'] == 'True' else "   "
            notes = row.get('notes', '')[:20]
            print(f"   {row['timestamp']:<20} {float(row['vix']):>6.2f} {row['regime']:<10} {change_mark:<8} {notes:<20}")

    print("   " + "-"*70 + "\n")


def show_status(vix: float, regime: str):
    """Display current VIX status."""
    print(f"\n   Current VIX: {vix:.2f}")
    print(f"   Regime: {regime}")
    print(f"   Action: {VIX_REGIMES[regime]['action']}")

    # Distance to thresholds
    print("\n   Distance to thresholds:")
    for t in VIX_THRESHOLDS:
        diff = vix - t
        direction = "above" if diff > 0 else "below"
        print(f"     {t}: {abs(diff):.2f} {direction}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_monitor(status_only: bool = False) -> Dict:
    """
    Run the VIX monitor.

    Args:
        status_only: If True, show status without logging

    Returns:
        Dict with results
    """
    print("\n" + "="*70)
    print(f"VIX REGIME MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Fetch current VIX
    current_vix = fetch_vix()

    if current_vix is None:
        print("\n   Could not fetch VIX - exiting")
        return {'error': 'Failed to fetch VIX'}

    current_regime = get_regime(current_vix)

    # Show status
    show_status(current_vix, current_regime)

    # Status-only mode (no logging)
    if status_only:
        print("\n" + "="*70 + "\n")
        return {
            'vix': current_vix,
            'regime': current_regime
        }

    # Get last reading for comparison
    last_reading = get_last_reading()

    if last_reading:
        old_vix = last_reading['vix']
        old_regime = last_reading['regime']

        print(f"\n   Last reading: {old_vix:.2f} ({old_regime}) at {last_reading['timestamp']}")

        # Detect crossing
        crossed, threshold, direction = detect_crossing(old_vix, current_vix)
        regime_change = (old_regime != current_regime)

        if crossed:
            print_regime_alert(current_vix, current_regime, old_vix, old_regime, threshold, direction)
            notes = f"Crossed {threshold} - {VIX_REGIMES[current_regime]['action']}"
        elif regime_change:
            notes = f"Regime: {old_regime} -> {current_regime}"
        else:
            notes = "Regime stable"

        # Log to CSV
        append_to_csv(current_vix, current_regime, regime_change, threshold, direction, notes)

    else:
        print("\n   First check of the month - establishing baseline")
        append_to_csv(current_vix, current_regime, False, None, None, "Initial reading")

    print("\n" + "="*70 + "\n")

    return {
        'vix': current_vix,
        'regime': current_regime,
        'old_vix': last_reading['vix'] if last_reading else None,
        'old_regime': last_reading['regime'] if last_reading else None
    }


def main():
    """Main entry point with CLI argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description='VIX Regime Monitor - CSV Logging Version'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current regime without logging'
    )
    parser.add_argument(
        '--history',
        action='store_true',
        help='Show last 10 VIX readings'
    )
    parser.add_argument(
        '-n',
        type=int,
        default=10,
        help='Number of history entries to show (default: 10)'
    )

    args = parser.parse_args()

    # Show history mode
    if args.history:
        print("\n" + "="*70)
        print("VIX HISTORY")
        print("="*70)
        show_history(args.n)
        return

    # Run monitor
    result = run_monitor(status_only=args.status)

    # Exit with appropriate code
    if result.get('error'):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
