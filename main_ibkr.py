#!/usr/bin/env python3
"""
Options Scanner - IBKR entry point.

Scans for Wheel Strategy candidates using **Interactive Brokers** (ib_async via
IB Gateway/TWS) for options data — live OPRA Greeks. Stock quotes come from FMP
and history from yfinance, same as the MooMoo path. For the MooMoo options source
use `main_moomoo.py` instead. The CLI/scan logic is shared — see scanner_app.py.

Usage:
    python main_ibkr.py wheel                  # Run Wheel screener (IBKR options)
    python main_ibkr.py wheel --capital 6700   # With custom capital limit
    python main_ibkr.py --mock wheel           # Run with mock data (testing)
    python main_ibkr.py --help                 # Show help

Requires IB Gateway/TWS running and logged in; API port = config.IBKR_PORT
(default 4001 = Gateway). Runs LIVE-only — see ibkr_data_fetcher.py.
"""

from ibkr_data_fetcher import get_ibkr_data_fetcher, IB_ASYNC_AVAILABLE
from config import IBKR_PORT
from scanner_app import DataSource, run


IBKR_SOURCE = DataSource(
    name="IBKR",
    options_label="Options data via IBKR API (OPRA)",
    fetcher_factory=get_ibkr_data_fetcher,
    options_available=IB_ASYNC_AVAILABLE,
    options_install="pip install ib_async",
    connect_fail_lines=[
        "Make sure IB Gateway/TWS is running, logged in, and the API",
        f"port matches config.IBKR_PORT (default {IBKR_PORT} = Gateway).",
    ],
    mock_help="Use mock data (for testing without an IB Gateway connection)",
)


def main():
    """Run the Wheel scanner against IBKR options data."""
    run(IBKR_SOURCE)


if __name__ == "__main__":
    main()
