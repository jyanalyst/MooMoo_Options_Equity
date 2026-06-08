#!/usr/bin/env python3
"""
Options Scanner - MooMoo entry point.

Scans for Wheel Strategy candidates using **MooMoo OpenD** for options data
(stock quotes via FMP, history via yfinance). For the IBKR options source use
`main_ibkr.py` instead. The CLI/scan logic is shared — see scanner_app.py.

Usage:
    python main_moomoo.py wheel                  # Run Wheel screener (MooMoo options)
    python main_moomoo.py wheel --capital 6700   # With custom capital limit
    python main_moomoo.py --mock wheel    # Run with mock data (testing)
    python main_moomoo.py --help          # Show help

Requires MooMoo OpenD running and logged in (127.0.0.1:11111) for options data.
"""

from data_fetcher import get_data_fetcher, MOOMOO_AVAILABLE
from config import MOOMOO_HOST, MOOMOO_PORT
from scanner_app import DataSource, run


MOOMOO_SOURCE = DataSource(
    name="MooMoo",
    options_label="Options data via MooMoo API (OPRA)",
    fetcher_factory=get_data_fetcher,
    options_available=MOOMOO_AVAILABLE,
    options_install="pip install moomoo-api",
    connect_fail_lines=[
        f"Make sure MooMoo OpenD is running and logged in at {MOOMOO_HOST}:{MOOMOO_PORT}.",
    ],
    mock_help="Use mock data (for testing without a MooMoo OpenD connection)",
)


def main():
    """Run the Wheel scanner against MooMoo options data."""
    run(MOOMOO_SOURCE)


if __name__ == "__main__":
    main()
