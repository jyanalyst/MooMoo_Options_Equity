#!/usr/bin/env python3
"""
Test Financial Modeling Prep API
Validate API key and explore data structure
"""

import requests
import json
from typing import Dict, List

# Your FMP API Key
FMP_API_KEY = "SUmg1Fkg9IxxPrCGF8HFP3sdLLl35IUk"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

def test_api_key():
    """Test that API key is valid"""
    print("="*70)
    print("TEST 1: API Key Validation")
    print("="*70)

    url = f"{FMP_BASE_URL}/profile?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        print("[PASS] API Key Valid!")
        data = response.json()
        if data:
            print(f"   Company: {data[0].get('companyName', 'N/A')}")
            print(f"   Sector: {data[0].get('sector', 'N/A')}")
            print(f"   Market Cap: ${data[0].get('mktCap', 0) / 1e9:.2f}B")
        return True
    else:
        print(f"[FAIL] API Key Invalid: {response.status_code}")
        print(f"   Error: {response.text}")
        return False


def test_financial_ratios():
    """Test financial ratios endpoint (key metrics for screening)"""
    print("\n" + "="*70)
    print("TEST 2: Financial Ratios (Your Screening Metrics)")
    print("="*70)

    # Get ratios from two endpoints
    ratios_url = f"{FMP_BASE_URL}/ratios-ttm?symbol=AAPL&apikey={FMP_API_KEY}"
    metrics_url = f"{FMP_BASE_URL}/key-metrics-ttm?symbol=AAPL&apikey={FMP_API_KEY}"

    ratios_response = requests.get(ratios_url)
    metrics_response = requests.get(metrics_url)

    if ratios_response.status_code == 200 and metrics_response.status_code == 200:
        ratios = ratios_response.json()[0]
        metrics = metrics_response.json()[0]

        print(f"[PASS] Ticker: AAPL")
        print(f"   Operating Margin: {ratios.get('operatingProfitMarginTTM', 0) * 100:.2f}%")
        print(f"   ROE: {metrics.get('returnOnEquityTTM', 0) * 100:.2f}%")
        print(f"   Current Ratio: {ratios.get('currentRatioTTM', 0):.2f}")
        print(f"   Debt/Equity: {ratios.get('debtToEquityRatioTTM', 0):.2f}")
        print(f"   Gross Margin: {ratios.get('grossProfitMarginTTM', 0) * 100:.2f}%")
        return True
    else:
        print(f"[FAIL] Failed: ratios={ratios_response.status_code}, metrics={metrics_response.status_code}")
        return False


def test_cash_flow():
    """Test cash flow endpoint (FCF validation)"""
    print("\n" + "="*70)
    print("TEST 3: Cash Flow (Free Cash Flow Validation)")
    print("="*70)

    url = f"{FMP_BASE_URL}/cash-flow-statement?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data:
            cf = data[0]  # Most recent cash flow statement
            fcf = cf.get('freeCashFlow', 0)
            print(f"[PASS] Ticker: AAPL")
            print(f"   Free Cash Flow: ${fcf / 1e9:.2f}B")
            print(f"   Operating Cash Flow: ${cf.get('operatingCashFlow', 0) / 1e9:.2f}B")
            print(f"   Capex: ${cf.get('capitalExpenditure', 0) / 1e9:.2f}B")
            return True
    else:
        print(f"[FAIL] Failed: {response.status_code}")
        return False


def test_earnings_calendar():
    """Test earnings calendar (better than yfinance)"""
    print("\n" + "="*70)
    print("TEST 4: Earnings Calendar (Replaces yfinance)")
    print("="*70)

    url = f"{FMP_BASE_URL}/earnings-calendar?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            latest = data[0]
            print(f"[PASS] Ticker: AAPL")
            print(f"   Next Earnings: {latest.get('date', 'N/A')}")
            print(f"   EPS Estimate: ${latest.get('epsEstimated', 'N/A')}")
            print(f"   Revenue Estimate: ${latest.get('revenueEstimated', 0) / 1e9:.2f}B")
            return True
    else:
        print(f"[FAIL] Failed: {response.status_code}")
        return False


def test_stock_screener():
    """Test stock screener endpoint (replaces Finviz filters)"""
    print("\n" + "="*70)
    print("TEST 5: Stock Screener (Replaces Finviz)")
    print("="*70)

    # Screen for: Market Cap >$10B - using company-screener endpoint
    url = f"{FMP_BASE_URL}/company-screener?marketCapMoreThan=10000000000&limit=5&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"[PASS] Found {len(data)} stocks matching criteria")
        print("\n   Top 5 Matches:")
        for stock in data[:5]:
            print(f"   • {stock.get('symbol', 'N/A'):6s} - {stock.get('companyName', 'N/A')[:30]:30s} | "
                  f"Market Cap: ${stock.get('marketCap', 0) / 1e9:.1f}B")
        return True
    else:
        print(f"[FAIL] Failed: {response.status_code}")
        return False


def test_rate_limits():
    """Test multiple rapid calls to check rate limiting"""
    print("\n" + "="*70)
    print("TEST 6: Rate Limiting (Starter Plan)")
    print("="*70)

    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
    success_count = 0

    for ticker in tickers:
        url = f"{FMP_BASE_URL}/profile?symbol={ticker}&apikey={FMP_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            success_count += 1

    print(f"[PASS] {success_count}/{len(tickers)} rapid calls succeeded")
    if success_count == len(tickers):
        print("   Rate limiting looks good for your use case")
    return success_count == len(tickers)


def test_comprehensive_data():
    """Test getting all data needed for one stock (simulate real usage)"""
    print("\n" + "="*70)
    print("TEST 7: Comprehensive Stock Data (Real Usage Simulation)")
    print("="*70)

    ticker = "AAPL"

    # Get company profile
    profile_url = f"{FMP_BASE_URL}/profile?symbol={ticker}&apikey={FMP_API_KEY}"
    profile = requests.get(profile_url).json()[0]

    # Get financial ratios (TTM)
    ratios_url = f"{FMP_BASE_URL}/ratios-ttm?symbol={ticker}&apikey={FMP_API_KEY}"
    ratios = requests.get(ratios_url).json()[0]

    # Get key metrics (TTM) - for ROE
    metrics_url = f"{FMP_BASE_URL}/key-metrics-ttm?symbol={ticker}&apikey={FMP_API_KEY}"
    metrics = requests.get(metrics_url).json()[0]

    # Get cash flow (most recent annual)
    cf_url = f"{FMP_BASE_URL}/cash-flow-statement?symbol={ticker}&apikey={FMP_API_KEY}"
    cash_flow = requests.get(cf_url).json()[0]

    # Get income statement TTM (for revenue to calculate FCF margin)
    income_url = f"{FMP_BASE_URL}/income-statement?symbol={ticker}&apikey={FMP_API_KEY}"
    income = requests.get(income_url).json()[0]

    print(f"[PASS] Complete data for {ticker}:")
    print(f"\n   Company Info:")
    print(f"     Name: {profile.get('companyName', 'N/A')}")
    print(f"     Sector: {profile.get('sector', 'N/A')}")
    print(f"     Industry: {profile.get('industry', 'N/A')}")
    print(f"     Market Cap: ${profile.get('mktCap', 0) / 1e9:.2f}B")
    print(f"     Price: ${profile.get('price', 0):.2f}")

    print(f"\n   Fundamental Ratios:")
    print(f"     Operating Margin: {ratios.get('operatingProfitMarginTTM', 0) * 100:.2f}%")
    print(f"     Gross Margin: {ratios.get('grossProfitMarginTTM', 0) * 100:.2f}%")
    print(f"     ROE: {metrics.get('returnOnEquityTTM', 0) * 100:.2f}%")
    print(f"     Current Ratio: {ratios.get('currentRatioTTM', 0):.2f}")
    print(f"     Debt/Equity: {ratios.get('debtToEquityRatioTTM', 0):.2f}")
    print(f"     P/E Ratio: {ratios.get('priceToEarningsRatioTTM', 0):.2f}")

    fcf = cash_flow.get('freeCashFlow', 0)
    revenue = income.get('revenue', 1)
    fcf_margin = (fcf / revenue) * 100

    print(f"\n   Cash Flow:")
    print(f"     Free Cash Flow: ${fcf / 1e9:.2f}B")
    print(f"     FCF Margin: {fcf_margin:.2f}%")
    print(f"     Revenue: ${revenue / 1e9:.2f}B")

    print(f"\n   Quality Checks:")
    print(f"     {'[PASS]' if ratios.get('operatingProfitMarginTTM', 0) * 100 > 2 else '[FAIL]'} Operating Margin >2%")
    print(f"     {'[PASS]' if ratios.get('grossProfitMarginTTM', 0) * 100 > 15 else '[FAIL]'} Gross Margin >15%")
    print(f"     {'[PASS]' if metrics.get('returnOnEquityTTM', 0) * 100 > 10 else '[FAIL]'} ROE >10%")
    print(f"     {'[PASS]' if ratios.get('currentRatioTTM', 0) > 1.5 else '[FAIL]'} Current Ratio >1.5")
    print(f"     {'[PASS]' if ratios.get('debtToEquityRatioTTM', 0) < 1.0 else '[FAIL]'} Debt/Equity <1.0")
    print(f"     {'[PASS]' if fcf > 0 and fcf_margin > 2 else '[FAIL]'} FCF Positive & Margin >2%")

    return True


# =============================================================================
# TIER 1 ADVANCED FEATURE TESTS (Week 2 FMP Integration)
# =============================================================================

def test_analyst_estimates():
    """Test analyst estimates endpoint (forward-looking metrics)"""
    print("\n" + "="*70)
    print("TEST 8: Analyst Estimates (Forward Revenue/EPS)")
    print("="*70)

    url = f"{FMP_BASE_URL}/analyst-estimates?symbol=AAPL&period=annual&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            est = data[0]
            print(f"[PASS] Analyst Estimates for AAPL:")
            # FMP uses revenueAvg, epsAvg (without 'estimated' prefix)
            rev = est.get('revenueAvg', est.get('estimatedRevenueAvg', 0))
            eps = est.get('epsAvg', est.get('estimatedEpsAvg', 0))
            analysts = est.get('numberAnalystsEstimatedRevenue', est.get('numberAnalysts', 0))
            print(f"   Est. Revenue: ${rev / 1e9:.2f}B" if rev else "   Est. Revenue: N/A")
            print(f"   Est. EPS: ${eps:.2f}" if eps else "   Est. EPS: N/A")
            print(f"   # Analysts: {analysts}")
            print(f"   Response keys: {list(est.keys())}")
            return True
        else:
            print("[FAIL] Empty response")
            return False
    else:
        print(f"[FAIL] Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False


def test_financial_scores():
    """Test financial scores (Altman Z + Piotroski)"""
    print("\n" + "="*70)
    print("TEST 9: Financial Scores (Altman Z + Piotroski)")
    print("="*70)

    url = f"{FMP_BASE_URL}/financial-scores?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            scores = data[0]
            z = scores.get('altmanZScore', 0)
            p = scores.get('piotroskiScore', 0)
            print(f"[PASS] Financial Scores for AAPL:")
            print(f"   Altman Z-Score: {z:.2f} ({'SAFE' if z > 3 else 'GRAY ZONE' if z > 1.8 else 'DISTRESS'})")
            print(f"   Piotroski Score: {p}/9 ({'HIGH QUALITY' if p >= 7 else 'MODERATE' if p >= 5 else 'LOW'})")
            print(f"   Response keys: {list(scores.keys())}")
            return True
        else:
            print("[FAIL] Empty response")
            return False
    else:
        print(f"[FAIL] Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False


def test_insider_trading():
    """Test insider trading statistics (OPTIONAL - may require higher tier)"""
    print("\n" + "="*70)
    print("TEST 10: Insider Trading Statistics (Optional Feature)")
    print("="*70)

    url = f"{FMP_BASE_URL}/insider-trading-statistics?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            print(f"[PASS] Insider Trading for AAPL:")
            insider = data[0] if isinstance(data, list) else data
            print(f"   Response keys: {list(insider.keys())}")
            return True
        else:
            print("[SKIP] Insider Trading: Empty response (endpoint may require higher tier)")
            print("   This feature is OPTIONAL - scoring will use neutral defaults")
            return True  # Not a failure, just not available
    elif response.status_code in [402, 403, 404]:
        print(f"[SKIP] Insider Trading: Not available on current plan (status {response.status_code})")
        print("   This feature is OPTIONAL - scoring will use neutral defaults")
        return True  # Not a failure, just not available
    else:
        print(f"[FAIL] Status: {response.status_code}")
        return False


def test_institutional_ownership():
    """Test institutional ownership (OPTIONAL - requires Professional tier)"""
    print("\n" + "="*70)
    print("TEST 11: Institutional Ownership (Optional Feature)")
    print("="*70)

    from datetime import datetime
    year = datetime.now().year
    quarter = max(1, (datetime.now().month - 1) // 3)

    url = f"{FMP_BASE_URL}/institutional-ownership/symbol-positions-summary?symbol=AAPL&year={year}&quarter={quarter}&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            print(f"[PASS] Institutional Ownership for AAPL (Q{quarter} {year}):")
            inst = data[0]
            print(f"   Response keys: {list(inst.keys())}")
            return True
        else:
            print("[SKIP] Institutional Ownership: Empty response")
            return True
    elif response.status_code in [402, 403]:
        print(f"[SKIP] Institutional Ownership: Requires Professional tier (status {response.status_code})")
        print("   This feature is OPTIONAL - scoring will use neutral defaults")
        return True  # Not a failure, just not available on Starter plan
    else:
        print(f"[FAIL] Status: {response.status_code}")
        return False


def test_analyst_ratings():
    """Test analyst ratings consensus"""
    print("\n" + "="*70)
    print("TEST 12: Analyst Ratings Consensus")
    print("="*70)

    url = f"{FMP_BASE_URL}/grades-consensus?symbol=AAPL&apikey={FMP_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            ratings = data[0]
            strong_buy = ratings.get('strongBuy', 0) or 0
            buy = ratings.get('buy', 0) or 0
            hold = ratings.get('hold', 0) or 0
            sell = ratings.get('sell', 0) or 0
            strong_sell = ratings.get('strongSell', 0) or 0
            total = strong_buy + buy + hold + sell + strong_sell
            buy_pct = (strong_buy + buy) / total * 100 if total > 0 else 0

            print(f"[PASS] Analyst Ratings for AAPL:")
            print(f"   Strong Buy: {strong_buy}")
            print(f"   Buy: {buy}")
            print(f"   Hold: {hold}")
            print(f"   Sell: {sell}")
            print(f"   Strong Sell: {strong_sell}")
            print(f"   Buy%: {buy_pct:.1f}%")
            print(f"   Response keys: {list(ratings.keys())}")
            return True
        else:
            print("[FAIL] Empty response")
            return False
    else:
        print(f"[FAIL] Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False


def main():
    """Run all tests"""
    print("\nFMP API Testing Suite")
    print("Testing Financial Modeling Prep integration for MooMoo Options Scanner\n")

    tests = [
        ("API Key Validation", test_api_key),
        ("Financial Ratios", test_financial_ratios),
        ("Cash Flow Data", test_cash_flow),
        ("Earnings Calendar", test_earnings_calendar),
        ("Stock Screener", test_stock_screener),
        ("Rate Limiting", test_rate_limits),
        ("Comprehensive Data", test_comprehensive_data),
        # Week 2 Advanced Features
        ("Analyst Estimates", test_analyst_estimates),
        ("Financial Scores", test_financial_scores),
        ("Insider Trading", test_insider_trading),
        ("Institutional Ownership", test_institutional_ownership),
        ("Analyst Ratings", test_analyst_ratings),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] ERROR in {test_name}: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS] PASS" if result else "[FAIL] FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! FMP API is ready to use.")
        print("\nNext Steps:")
        print("1. Review test output above")
        print("2. Proceed to Phase 2: Parallel data collection")
        print("3. Run: python compare_data_sources.py")
    else:
        print("\nSome tests failed. Review errors above.")


if __name__ == "__main__":
    main()
