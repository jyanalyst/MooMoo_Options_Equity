#!/usr/bin/env python3
"""
Options Scanner - Main Entry Point
Scans for Wheel Strategy and Volatility Harvesting candidates using MooMoo API

Usage:
    python main.py wheel          # Run Wheel screener
    python main.py vol            # Run Vol Harvest screener  
    python main.py both           # Run both screeners
    python main.py --mock wheel   # Run with mock data (testing)
    python main.py --help         # Show help
"""

import argparse
import sys
from datetime import datetime

from data_fetcher import get_data_fetcher, MOOMOO_AVAILABLE
from screener_wheel import WheelScreener
from screener_vol_harvest import VolHarvestScreener
from output_formatter import OutputFormatter


def print_banner():
    """Print scanner banner"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ██████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗    ║
║  ██╔═══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝    ║
║  ██║   ██║██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║███████╗    ║
║  ██║   ██║██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║╚════██║    ║
║  ╚██████╔╝██║        ██║   ██║╚██████╔╝██║ ╚████║███████║    ║
║   ╚═════╝ ╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝    ║
║                                                               ║
║                  INCOME SCANNER v1.1                          ║
║            Wheel Strategy | Vol Harvesting                    ║
║                                                               ║
║  HYBRID MODE: Stock quotes via yfinance (FREE)                ║
║               Options data via MooMoo API (OPRA)              ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


def run_wheel_scan(fetcher, max_capital: int = 8900, export_csv: bool = True, verbose: bool = True):
    """
    Run Wheel Strategy screening.

    Args:
        fetcher: Data fetcher instance
        max_capital: Maximum capital per position in USD (default: 8900 = 20% of $44,500 account)
        export_csv: Export results to CSV
        verbose: Print verbose output

    Returns:
        List of candidates
    """
    print(f"\n{'═'*60}")
    print(f"🎯 WHEEL STRATEGY SCAN")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Max Capital/Position: ${max_capital:,}")
    print(f"{'═'*60}")

    screener = WheelScreener(fetcher, max_capital=max_capital)
    candidates = screener.screen_candidates(verbose=verbose)
    
    formatter = OutputFormatter()
    formatter.display_wheel_results(candidates)
    
    if export_csv and candidates:
        formatter.export_wheel_csv(candidates)
    
    return candidates


def run_vol_harvest_scan(fetcher, export_csv: bool = True, verbose: bool = True):
    """
    Run Volatility Harvesting screening.
    
    Args:
        fetcher: Data fetcher instance
        export_csv: Export results to CSV
        verbose: Print verbose output
        
    Returns:
        List of candidates
    """
    print(f"\n{'═'*60}")
    print(f"🔥 VOLATILITY HARVESTING SCAN (Iron Condors)")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")
    
    screener = VolHarvestScreener(fetcher)
    candidates = screener.screen_candidates(verbose=verbose)
    
    formatter = OutputFormatter()
    formatter.display_vol_harvest_results(candidates)
    
    if export_csv and candidates:
        formatter.export_vol_harvest_csv(candidates)
    
    return candidates


def interactive_detail(wheel_candidates, vol_candidates):
    """
    Interactive mode to view candidate details.
    
    Args:
        wheel_candidates: Wheel scan results
        vol_candidates: Vol Harvest scan results
    """
    formatter = OutputFormatter()
    
    while True:
        print("\n" + "─"*40)
        print("View detailed candidate (or 'q' to quit):")
        print("  w<N> - Wheel candidate N (e.g., w1)")
        print("  v<N> - Vol Harvest candidate N (e.g., v1)")
        print("─"*40)
        
        choice = input("Choice: ").strip().lower()
        
        if choice == 'q' or choice == 'quit':
            break
        
        try:
            if choice.startswith('w') and wheel_candidates:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(wheel_candidates):
                    formatter.display_detailed_candidate(wheel_candidates[idx], 'wheel')
                else:
                    print(f"Invalid index. Valid range: w1-w{len(wheel_candidates)}")
            
            elif choice.startswith('v') and vol_candidates:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(vol_candidates):
                    formatter.display_detailed_candidate(vol_candidates[idx], 'vol_harvest')
                else:
                    print(f"Invalid index. Valid range: v1-v{len(vol_candidates)}")
            
            else:
                print("Invalid choice. Use w<N> or v<N>.")
        
        except (ValueError, IndexError):
            print("Invalid input. Try again.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Options Income Scanner - Wheel Strategy & Vol Harvesting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py wheel              # Scan for Wheel candidates (default $8,900 max capital)
  python main.py vol                # Scan for Vol Harvest candidates
  python main.py both               # Run both scans
  python main.py --mock wheel       # Test with mock data
  python main.py wheel --capital 6700  # Scan stocks requiring ≤$6,700/position (15% sizing)
  python main.py wheel --capital 8900  # Scan stocks requiring ≤$8,900/position (20% sizing)
  python main.py both --no-csv      # Scan without CSV export
        """
    )
    
    parser.add_argument(
        'strategy',
        choices=['wheel', 'vol', 'both'],
        help='Strategy to scan: wheel, vol, or both'
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
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Check availability
    if not args.mock:
        from data_fetcher import YFINANCE_AVAILABLE, MOOMOO_AVAILABLE
        if not YFINANCE_AVAILABLE:
            print("❌ yfinance not available. Install with: pip install yfinance")
            sys.exit(1)
        if not MOOMOO_AVAILABLE:
            print("⚠️  MooMoo API not available - options features will not work")
            print("   Install with: pip install moomoo-api")
    
    # Initialize data fetcher
    print(f"\n📡 Initializing data connection...")
    
    try:
        fetcher = get_data_fetcher(use_mock=args.mock)
        
        if not args.mock:
            # Connect to MooMoo for options data
            if not fetcher.connect():
                print("\n⚠️  Could not connect to MooMoo OpenD.")
                print("   Options data will not be available.")
                print("   Make sure OpenD is running and you have OPRA subscription.")
                print("\n   Stock quotes will still work via yfinance (FREE)")
                # Don't exit - we can still get stock quotes
        else:
            print("   Using mock data (no live market connection)")
        
    except Exception as e:
        print(f"\n❌ Error initializing data fetcher: {e}")
        sys.exit(1)
    
    # Run scans
    wheel_candidates = None
    vol_candidates = None
    export_csv = not args.no_csv
    verbose = not args.quiet
    
    try:
        if args.strategy in ['wheel', 'both']:
            wheel_candidates = run_wheel_scan(
                fetcher,
                max_capital=args.capital,
                export_csv=export_csv,
                verbose=verbose
            )
        
        if args.strategy in ['vol', 'both']:
            vol_candidates = run_vol_harvest_scan(
                fetcher,
                export_csv=export_csv,
                verbose=verbose
            )
        
        # Print summary
        formatter = OutputFormatter()
        formatter.print_scan_summary(wheel_candidates, vol_candidates)
        
        # Interactive mode
        if args.interactive and (wheel_candidates or vol_candidates):
            interactive_detail(wheel_candidates or [], vol_candidates or [])
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user.")
    
    except Exception as e:
        print(f"\n❌ Error during scan: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if not args.mock and hasattr(fetcher, 'disconnect'):
            fetcher.disconnect()
    
    print("\n✅ Scan complete.\n")


if __name__ == "__main__":
    main()
