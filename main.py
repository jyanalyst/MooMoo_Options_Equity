#!/usr/bin/env python3
"""
Options Scanner - Main Entry Point
Scans for Wheel Strategy candidates using MooMoo API

Usage:
    python main.py wheel              # Run Wheel screener
    python main.py wheel --capital 6700  # With custom capital limit
    python main.py --mock wheel       # Run with mock data (testing)
    python main.py --help             # Show help
"""

import argparse
import sys
from datetime import datetime

from data_fetcher import get_data_fetcher, MOOMOO_AVAILABLE
from screener_wheel import WheelScreener
from output_formatter import OutputFormatter
from config import WHEEL_CONFIG


def print_banner():
    """Print scanner banner"""
    print("""
+===============================================================+
|                                                               |
|                     OPTIONS                                   |
|                  INCOME SCANNER v2.1                          |
|                   Wheel Strategy                              |
|                                                               |
|  PRO MODE: Stock quotes via FMP API (Real-time)               |
|            Options data via MooMoo API (OPRA)                 |
|                                                               |
+===============================================================+
    """)


def run_wheel_scan(fetcher, max_capital: int = 8900, export_csv: bool = True, verbose: bool = True, allow_unverified: bool = None):
    """
    Run Wheel Strategy screening.

    Args:
        fetcher: Data fetcher instance
        max_capital: Maximum capital per position in USD (default: 8900 = 20% of $44,500 account)
        export_csv: Export results to CSV
        verbose: Print verbose output
        allow_unverified: Allow stocks with unverified earnings dates

    Returns:
        List of candidates
    """
    # Default to config value if not explicitly specified
    if allow_unverified is None:
        allow_unverified = WHEEL_CONFIG.get("allow_unverified_earnings", True)

    print(f"\n{'='*60}")
    print(f">>> WHEEL STRATEGY SCAN")
    print(f"    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Max Capital/Position: ${max_capital:,}")
    if allow_unverified:
        print(f"    [!] Allow Unverified: ON (manual earnings check required)")
    print(f"{'='*60}")

    screener = WheelScreener(fetcher, max_capital=max_capital, allow_unverified=allow_unverified)
    candidates = screener.screen_candidates(verbose=verbose)

    formatter = OutputFormatter()
    formatter.display_wheel_results(candidates)

    if export_csv and candidates:
        formatter.export_wheel_csv(candidates)

    return candidates


def interactive_detail(candidates):
    """
    Interactive mode to view candidate details.

    Args:
        candidates: Wheel scan results
    """
    formatter = OutputFormatter()

    while True:
        print("\n" + "-"*40)
        print("View detailed candidate (or 'q' to quit):")
        print(f"  Enter 1-{len(candidates)} to view candidate details")
        print("-"*40)

        choice = input("Choice: ").strip().lower()

        if choice == 'q' or choice == 'quit':
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                formatter.display_detailed_candidate(candidates[idx], 'wheel')
            else:
                print(f"Invalid index. Valid range: 1-{len(candidates)}")
        except (ValueError, IndexError):
            print("Invalid input. Try again.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Options Income Scanner - Wheel Strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py wheel              # Scan for Wheel candidates (default $8,900 max capital)
  python main.py wheel --capital 6700  # Scan stocks requiring <=$6,700/position (15% sizing)
  python main.py wheel --capital 8900  # Scan stocks requiring <=$8,900/position (20% sizing)
  python main.py wheel --capital 15000 # Scan stocks requiring <=$15,000/position
  python main.py --mock wheel       # Test with mock data
  python main.py wheel --no-csv     # Scan without CSV export
        """
    )

    parser.add_argument(
        'strategy',
        choices=['wheel'],
        nargs='?',
        default='wheel',
        help='Strategy to scan (default: wheel)'
    )

    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock data (for testing without MooMoo connection)'
    )

    parser.add_argument(
        '--capital',
        type=int,
        default=8900,
        help='Maximum capital per position in USD (default: 8900 = 20%% of $44,500 account). Use 6700 for 15%% sizing.'
    )

    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='Skip CSV export'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output (suppress verbose screening details)'
    )

    parser.add_argument(
        '--interactive',
        '-i',
        action='store_true',
        help='Enter interactive mode after scan to view details'
    )

    parser.add_argument(
        '--allow-unverified',
        action='store_const',
        const=True,
        default=None,  # None = use config value, True = force allow
        help='Allow stocks with unverified earnings dates (requires manual verification)'
    )

    parser.add_argument(
        '--strict-earnings',
        action='store_const',
        const=False,
        dest='allow_unverified',  # Sets allow_unverified to False
        help='Reject stocks with unverified earnings (overrides config)'
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Check availability
    if not args.mock:
        from data_fetcher import YFINANCE_AVAILABLE, MOOMOO_AVAILABLE
        if not YFINANCE_AVAILABLE:
            print("[ERROR] yfinance not available. Install with: pip install yfinance")
            sys.exit(1)
        if not MOOMOO_AVAILABLE:
            print("[WARN] MooMoo API not available - options features will not work")
            print("       Install with: pip install moomoo-api")

    # Initialize data fetcher
    print(f"\n[*] Initializing data connection...")

    try:
        fetcher = get_data_fetcher(use_mock=args.mock)

        if not args.mock:
            # Connect to MooMoo for options data
            if not fetcher.connect():
                print("\n[WARN] Could not connect to MooMoo OpenD.")
                print("       Options data will not be available.")
                print("       Make sure OpenD is running and you have OPRA subscription.")
                print("\n       Stock quotes will still work via FMP API")
                # Don't exit - we can still get stock quotes
        else:
            print("    Using mock data (no live market connection)")

    except Exception as e:
        print(f"\n[ERROR] Error initializing data fetcher: {e}")
        sys.exit(1)

    # Run scan
    candidates = None
    export_csv = not args.no_csv
    verbose = not args.quiet

    try:
        candidates = run_wheel_scan(
            fetcher,
            max_capital=args.capital,
            export_csv=export_csv,
            verbose=verbose,
            allow_unverified=args.allow_unverified
        )

        # Print summary
        formatter = OutputFormatter()
        formatter.print_scan_summary(candidates)

        # Interactive mode
        if args.interactive and candidates:
            interactive_detail(candidates)

    except KeyboardInterrupt:
        print("\n\n[WARN] Scan interrupted by user.")

    except Exception as e:
        print(f"\n[ERROR] Error during scan: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if not args.mock and hasattr(fetcher, 'disconnect'):
            fetcher.disconnect()

    print("\n[OK] Scan complete.\n")


if __name__ == "__main__":
    main()
