#!/usr/bin/env python3
"""
Shared CLI core for the Options Income Scanner.

The scan logic (argparse, banner, Wheel screening, CSV export, interactive mode)
is identical regardless of where the options chain comes from — only the data
source differs. Each entry point supplies a `DataSource` describing its options
backend and calls `run(source)`:

    main_moomoo.py -> MooMoo OpenD   (see DataSource in main_moomoo.py)
    main_ibkr.py   -> IBKR Gateway   (see DataSource in main_ibkr.py)

Stock quotes (FMP) and history (yfinance) are the same on both paths; only the
options chain + Greeks come from the source's fetcher.
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List

from data_fetcher import YFINANCE_AVAILABLE
from screener_wheel import WheelScreener
from output_formatter import OutputFormatter
from config import WHEEL_CONFIG


@dataclass
class DataSource:
    """Describes an options-data backend for the scanner CLI."""

    name: str  # short label, e.g. "MooMoo" / "IBKR"
    options_label: str  # banner line, e.g. "Options data via IBKR API (OPRA)"
    fetcher_factory: Callable[..., Any]  # (use_mock: bool) -> fetcher
    options_available: bool  # is the options library importable?
    options_install: str  # pip hint when the library is missing
    connect_fail_lines: List[str] = field(default_factory=list)  # connect() hints
    mock_help: str = "Use mock data (for testing without a live connection)"


def print_banner(source: "DataSource"):
    """Print the scanner banner for the given data source."""
    print(f"""
+===============================================================+
|                                                               |
|                     OPTIONS                                   |
|                  INCOME SCANNER v2.1                          |
|                   Wheel Strategy                              |
|                                                               |
|  PRO MODE: Stock quotes via FMP API (Real-time)               |
|            {source.options_label:<51}|
|                                                               |
+===============================================================+
    """)


def run_wheel_scan(
    fetcher,
    max_capital: int = 8900,
    export_csv: bool = True,
    verbose: bool = True,
    allow_unverified: bool = None,
    liquid_only: bool = False,
):
    """
    Run Wheel Strategy screening.

    Args:
        fetcher: Data fetcher instance
        max_capital: Maximum capital per position in USD (default: 8900 = 20% of $44,500 account)
        export_csv: Export results to CSV
        verbose: Print verbose output
        allow_unverified: Allow stocks with unverified earnings dates
        liquid_only: Scan only high-liquidity stocks with tight spreads

    Returns:
        List of candidates
    """
    # Default to config value if not explicitly specified
    if allow_unverified is None:
        allow_unverified = WHEEL_CONFIG.get("allow_unverified_earnings", False)

    print(f"\n{'=' * 60}")
    print(">>> WHEEL STRATEGY SCAN")
    if liquid_only:
        print("    Mode: HIGH-LIQUIDITY ONLY")
        print("    Expected: Tight spreads (<20%), fast execution")
    print(f"    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Max Capital/Position: ${max_capital:,}")
    if allow_unverified:
        print("    [!] Allow Unverified: ON (manual earnings check required)")
    print(f"{'=' * 60}")

    screener = WheelScreener(
        fetcher, max_capital=max_capital, allow_unverified=allow_unverified
    )

    # Override universe if liquid-only mode
    if liquid_only:
        from universe import get_liquid_wheel_universe

        screener.universe = get_liquid_wheel_universe(max_capital)
        print(
            f"\n[LIQUID MODE] Scanning {len(screener.universe)} high-liquidity stocks"
        )
        print("   Expected spreads: <20% (vs. 50%+ for full universe)")
        tickers_preview = ", ".join(screener.universe[:10])
        if len(screener.universe) > 10:
            tickers_preview += "..."
        print(f"   Tickers: {tickers_preview}\n")

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
        print("\n" + "-" * 40)
        print("View detailed candidate (or 'q' to quit):")
        print(f"  Enter 1-{len(candidates)} to view candidate details")
        print("-" * 40)

        choice = input("Choice: ").strip().lower()

        if choice == "q" or choice == "quit":
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                formatter.display_detailed_candidate(candidates[idx], "wheel")
            else:
                print(f"Invalid index. Valid range: 1-{len(candidates)}")
        except (ValueError, IndexError):
            print("Invalid input. Try again.")


def _build_parser(source: "DataSource") -> argparse.ArgumentParser:
    prog = "main_moomoo.py" if source.name == "MooMoo" else "main_ibkr.py"
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"Options Income Scanner - Wheel Strategy ({source.name} options)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python {prog} wheel                          # Scan full universe (~40 stocks)
  python {prog} wheel --liquid-only            # Scan liquid names only (~15 stocks, faster)
  python {prog} wheel --capital 6700           # Scan stocks requiring <=$6,700/position
  python {prog} wheel --liquid-only --capital 20000  # Liquid names under $20k
  python {prog} --mock wheel                   # Test with mock data
  python {prog} wheel --no-csv                 # Scan without CSV export
        """,
    )

    parser.add_argument(
        "strategy",
        choices=["wheel"],
        nargs="?",
        default="wheel",
        help="Strategy to scan (default: wheel)",
    )
    parser.add_argument("--mock", action="store_true", help=source.mock_help)
    parser.add_argument(
        "--capital",
        type=int,
        default=8900,
        help="Maximum capital per position in USD (default: 8900 = 20%% of $44,500 account). Use 6700 for 15%% sizing.",
    )
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (suppress verbose screening details)",
    )
    parser.add_argument(
        "--liquid-only",
        action="store_true",
        help="Scan only high-liquidity stocks with tight spreads (<20%%). "
        "Faster scans, better execution, smaller universe (~15 stocks vs 40). "
        "Ideal for trading during US market hours or when prioritizing fill quality.",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Enter interactive mode after scan to view details",
    )
    parser.add_argument(
        "--allow-unverified",
        action="store_const",
        const=True,
        default=None,  # None = use config value, True = force allow
        help="Allow stocks with unverified earnings dates (requires manual verification)",
    )
    parser.add_argument(
        "--strict-earnings",
        action="store_const",
        const=False,
        dest="allow_unverified",  # Sets allow_unverified to False
        help="Reject stocks with unverified earnings (overrides config)",
    )
    return parser


def run(source: "DataSource"):
    """Entry point: parse args and run a Wheel scan against `source`'s options data."""
    parser = _build_parser(source)
    args = parser.parse_args()

    print_banner(source)

    # Check availability
    if not args.mock:
        if not YFINANCE_AVAILABLE:
            print("[ERROR] yfinance not available. Install with: pip install yfinance")
            sys.exit(1)
        if not source.options_available:
            print(
                f"[WARN] {source.name} options library not available - options "
                "features will not work"
            )
            print(f"       Install with: {source.options_install}")

    # Initialize data fetcher
    print("\n[*] Initializing data connection...")

    try:
        fetcher = source.fetcher_factory(use_mock=args.mock)

        if not args.mock:
            if not fetcher.connect():
                print(f"\n[WARN] Could not connect to {source.name}.")
                print("       Options data will not be available.")
                for line in source.connect_fail_lines:
                    print(f"       {line}")
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
            allow_unverified=args.allow_unverified,
            liquid_only=args.liquid_only,
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
        if not args.mock and hasattr(fetcher, "disconnect"):
            fetcher.disconnect()

    print("\n[OK] Scan complete.\n")
