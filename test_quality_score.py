#!/usr/bin/env python3
"""
Test script for quality score calculation.

Tests the updated _calculate_quality_score() method with real FMP API data.
"""

from trade_journal import TradeJournal

def test_quality_score():
    """Test quality score calculation for various tickers."""
    print("\n" + "="*70)
    print("QUALITY SCORE CALCULATION TEST")
    print("="*70)

    # Initialize journal (will auto-create FMP fetcher)
    print("\nInitializing TradeJournal...")
    journal = TradeJournal()

    # Test tickers: mix of high-quality, medium-quality, and ETFs
    test_tickers = [
        # High-quality tech stocks
        ("MSFT", "Expected: 70-85 (High quality tech)"),
        ("AAPL", "Expected: 65-80 (High quality tech)"),
        ("ANET", "Expected: 70-85 (High quality networking)"),

        # Healthcare/Medical
        ("A", "Expected: 50-65 (Medium quality healthcare)"),

        # Consumer defensive
        ("KO", "Expected: 55-70 (Stable consumer staples)"),
        ("PG", "Expected: 55-70 (Stable consumer staples)"),

        # Financials (different metrics)
        ("JPM", "Expected: 40-60 (Financial sector)"),

        # Industrials
        ("CAT", "Expected: 50-65 (Cyclical industrial)"),

        # Auto (lower quality typically)
        ("F", "Expected: 30-50 (Cyclical auto)"),

        # ETFs (should return None)
        ("SPY", "Expected: None (ETF)"),
        ("QQQ", "Expected: None (ETF)"),
    ]

    print("\n" + "-"*70)
    print("TESTING INDIVIDUAL TICKERS")
    print("-"*70)

    results = []
    for ticker, expected in test_tickers:
        print(f"\n{'='*50}")
        print(f"Testing: {ticker}")
        print(f"{'='*50}")
        print(f"  {expected}")
        print()

        score = journal._calculate_quality_score(ticker)

        if score is not None:
            bucket = "High" if score >= 70 else ("Medium" if score >= 50 else "Low")
            print(f"\n  RESULT: Quality Score = {score:.1f} ({bucket})")
        else:
            print(f"\n  RESULT: Quality Score = None")

        results.append((ticker, score, expected))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n{'Ticker':<10} {'Score':<10} {'Bucket':<10} Expected")
    print("-"*70)

    for ticker, score, expected in results:
        if score is not None:
            bucket = "High" if score >= 70 else ("Medium" if score >= 50 else "Low")
            print(f"{ticker:<10} {score:<10.1f} {bucket:<10} {expected}")
        else:
            print(f"{ticker:<10} {'None':<10} {'N/A':<10} {expected}")

    # Validation checks
    print("\n" + "="*70)
    print("VALIDATION")
    print("="*70)

    # Check no scores are 95-100 (the bug we're fixing)
    high_scores = [(t, s) for t, s, _ in results if s is not None and s >= 90]
    if high_scores:
        print(f"\n[!] WARNING: {len(high_scores)} stocks have scores >= 90:")
        for t, s in high_scores:
            print(f"    {t}: {s:.1f}")
        print("    This might indicate a scoring issue - verify the metrics!")
    else:
        print("\n[+] PASS: No unrealistically high scores (>=90)")

    # Check ETFs return None
    etf_scores = [(t, s) for t, s, _ in results if t in ['SPY', 'QQQ'] and s is not None]
    if etf_scores:
        print(f"\n[!] WARNING: ETFs should return None:")
        for t, s in etf_scores:
            print(f"    {t}: {s:.1f}")
    else:
        print("[+] PASS: ETFs correctly return None")

    # Check scores are in reasonable range
    valid_scores = [s for _, s, _ in results if s is not None]
    if valid_scores:
        avg_score = sum(valid_scores) / len(valid_scores)
        print(f"\n[INFO] Average quality score: {avg_score:.1f}")
        print(f"[INFO] Score range: {min(valid_scores):.1f} - {max(valid_scores):.1f}")

        if 40 <= avg_score <= 75:
            print("[+] PASS: Average score is in expected range (40-75)")
        else:
            print(f"[!] WARNING: Average score {avg_score:.1f} may be unexpected")

    print("\n" + "="*70)


if __name__ == "__main__":
    test_quality_score()
