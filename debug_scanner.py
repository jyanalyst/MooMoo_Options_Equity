#!/usr/bin/env python3
"""
Debug script to test scanner with real data
"""

from data_fetcher import get_data_fetcher
from screener_wheel import WheelScreener

def test_scanner():
    fetcher = get_data_fetcher(use_mock=False)
    # Test with stocks requiring ≤$7,000 capital (~$70/share)
    screener = WheelScreener(fetcher, max_capital=7000)
    screener.universe = ['PLTR', 'INTC', 'AMD', 'SOFI']  # Test multiple stocks

    print('Testing INTC with full debugging...')
    candidates = screener.screen_candidates(verbose=True)
    print(f'\nFound {len(candidates)} candidates')

    if candidates:
        print('\nCANDIDATE DETAILS:')
        for cand in candidates:
            print(f"Ticker: {cand['ticker']}")
            print(f"Price: ${cand['price']:.2f}")
            print(f"Strike: ${cand['best_option']['strike']:.2f}")
            print(f"Premium: ${cand['best_option']['premium']:.2f}")
            print(f"Return: {cand['best_option']['return_pct']:.2f}%")

if __name__ == "__main__":
    test_scanner()
