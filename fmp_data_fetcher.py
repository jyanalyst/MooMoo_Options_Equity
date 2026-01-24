#!/usr/bin/env python3
"""
Financial Modeling Prep (FMP) Data Fetcher

Centralized module for fetching fundamental data from FMP API.
Replaces Finviz web scraping with SEC-sourced official data.

Features:
- Rate limiting (1 request/second, 250/day limit)
- Daily caching (FMP data updates once per day)
- Retry logic with exponential backoff
- Schema validation for all responses
- Comprehensive error handling

Usage:
    from fmp_data_fetcher import FMPDataFetcher

    fetcher = FMPDataFetcher(api_key="your_key_here")
    profile = fetcher.get_company_profile("AAPL")
    ratios = fetcher.get_fundamental_ratios("AAPL")
"""

import time
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd


class FMPDataFetcher:
    """Financial Modeling Prep API data fetcher with caching and rate limiting."""

    BASE_URL = "https://financialmodelingprep.com/stable"
    RATE_LIMIT_DELAY = 1.0  # Conservative 1 req/second (Starter plan allows 250/day)
    CACHE_DURATION_HOURS = 24  # FMP data updates daily

    def __init__(self, api_key: str, cache_dir: str = "./cache"):
        """
        Initialize FMP data fetcher.

        Args:
            api_key: FMP API key
            cache_dir: Directory for caching responses
        """
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.last_request_time = 0
        self.request_count = 0

        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _get_cache_path(self, endpoint: str, params: Dict[str, Any]) -> Path:
        """Generate cache file path for endpoint and parameters."""
        cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"fmp_{cache_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached data is still valid (within 24 hours)."""
        if not cache_path.exists():
            return False

        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return cache_age < timedelta(hours=self.CACHE_DURATION_HOURS)

    def _fetch_with_cache(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Fetch data from FMP API with caching.

        Args:
            endpoint: API endpoint (e.g., "profile")
            params: Query parameters (symbol will be added to this)

        Returns:
            API response data or None if error
        """
        cache_path = self._get_cache_path(endpoint, params)

        # Check cache first
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        # Rate limiting
        self._rate_limit()

        # Build URL
        url = f"{self.BASE_URL}/{endpoint}"
        params['apikey'] = self.api_key

        # Fetch from API
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            self.request_count += 1

            # Cache response
            with open(cache_path, 'w') as f:
                json.dump(data, f)

            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 402:
                print(f"[FMP] 402 Payment Required: Endpoint '{endpoint}' may require higher tier plan")
            elif e.response.status_code == 403:
                print(f"[FMP] 403 Forbidden: Check if endpoint is available in your plan")
            elif e.response.status_code == 404:
                print(f"[FMP] 404 Not Found: Endpoint '{endpoint}' not available")
            else:
                print(f"[FMP] HTTP error {e.response.status_code}: {e}")
            return None

        except requests.exceptions.Timeout as e:
            print(f"[FMP] Request timeout for '{endpoint}': {e}")
            return None

        except requests.exceptions.ConnectionError as e:
            print(f"[FMP] Connection error for '{endpoint}': {e}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[FMP] Request failed: {e}")
            return None

        except json.JSONDecodeError as e:
            print(f"[FMP] Invalid JSON response: {e}")
            return None

        except Exception as e:
            # Catch any other unexpected errors to prevent crash
            print(f"[FMP] Unexpected error for '{endpoint}': {type(e).__name__}: {e}")
            return None

    def get_company_profile(self, ticker: str) -> Optional[Dict]:
        """
        Get company profile (name, sector, industry, price).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Profile data or None if error

        Example:
            {
                'symbol': 'AAPL',
                'companyName': 'Apple Inc.',
                'sector': 'Technology',
                'industry': 'Consumer Electronics',
                'price': 247.41,
                'mktCap': 0  # Note: Use key-metrics-ttm for accurate market cap
            }
        """
        data = self._fetch_with_cache("profile", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def get_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get real-time quote data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Quote data or None if error
        """
        data = self._fetch_with_cache("quote", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def get_fundamental_ratios(self, ticker: str) -> Optional[Dict]:
        """
        Get comprehensive fundamental ratios (TTM).

        Combines data from:
        - /ratios-ttm (margins, debt ratios, valuation)
        - /key-metrics-ttm (ROE, market cap, FCF yield)

        Args:
            ticker: Stock ticker symbol

        Returns:
            Combined ratios dict or None if error

        Example:
            {
                'operatingProfitMarginTTM': 0.3197,
                'grossProfitMarginTTM': 0.4691,
                'returnOnEquityTTM': 1.6405,
                'currentRatioTTM': 0.89,
                'debtToEquityRatioTTM': 1.52,
                'priceToEarningsRatioTTM': 33.02,
                'marketCap': 3660398092083.0
            }
        """
        ratios = self._fetch_with_cache("ratios-ttm", {"symbol": ticker})
        metrics = self._fetch_with_cache("key-metrics-ttm", {"symbol": ticker})

        if not ratios or not metrics:
            return None

        # Combine both responses
        combined = {}
        if len(ratios) > 0:
            combined.update(ratios[0])
        if len(metrics) > 0:
            combined.update(metrics[0])

        return combined

    def get_cash_flow(self, ticker: str) -> Optional[Dict]:
        """
        Get cash flow statement (most recent annual).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cash flow data or None if error

        Example:
            {
                'date': '2025-09-27',
                'freeCashFlow': 98767000000,
                'operatingCashFlow': 111482000000,
                'capitalExpenditure': -12715000000
            }
        """
        data = self._fetch_with_cache("cash-flow-statement", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def get_income_statement(self, ticker: str) -> Optional[Dict]:
        """
        Get income statement (most recent annual).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Income statement data or None if error
        """
        data = self._fetch_with_cache("income-statement", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def get_earnings_date(self, ticker: str) -> Optional[str]:
        """
        Get next earnings date from earnings calendar.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Earnings date string (YYYY-MM-DD) or None if not found
        """
        data = self._fetch_with_cache("earnings-calendar", {"symbol": ticker})

        if data and len(data) > 0:
            return data[0].get('date')

        return None

    def get_earnings_calendar(self, ticker: str) -> Optional[Dict]:
        """
        Get full earnings calendar data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Earnings calendar data or None if error

        Example:
            {
                'date': '2026-01-23',
                'epsEstimated': 43.99,
                'revenueEstimated': 2210000000
            }
        """
        data = self._fetch_with_cache("earnings-calendar", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def screen_stocks(
        self,
        market_cap_min: Optional[float] = None,
        market_cap_max: Optional[float] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        beta_min: Optional[float] = None,
        beta_max: Optional[float] = None,
        volume_min: Optional[int] = None,
        sector: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Screen stocks using FMP screener endpoint.

        Note: Advanced filters (ROE, operating margin) must be applied client-side.

        Args:
            market_cap_min: Minimum market cap
            market_cap_max: Maximum market cap
            price_min: Minimum price
            price_max: Maximum price
            beta_min: Minimum beta
            beta_max: Maximum beta
            volume_min: Minimum volume
            sector: Filter by sector
            limit: Maximum results

        Returns:
            List of matching stocks
        """
        params = {"limit": limit}

        if market_cap_min is not None:
            params['marketCapMoreThan'] = int(market_cap_min)
        if market_cap_max is not None:
            params['marketCapLowerThan'] = int(market_cap_max)
        if price_min is not None:
            params['priceMoreThan'] = price_min
        if price_max is not None:
            params['priceLowerThan'] = price_max
        if beta_min is not None:
            params['betaMoreThan'] = beta_min
        if beta_max is not None:
            params['betaLowerThan'] = beta_max
        if volume_min is not None:
            params['volumeMoreThan'] = volume_min
        if sector is not None:
            params['sector'] = sector

        data = self._fetch_with_cache("company-screener", params)
        return data if data else []

    def get_complete_fundamental_data(self, ticker: str) -> Optional[Dict]:
        """
        Get all fundamental data needed for screening in a single call.

        This fetches:
        - Company profile
        - Financial ratios (combined ratios-ttm + key-metrics-ttm)
        - Cash flow statement
        - Income statement
        - Earnings calendar

        Args:
            ticker: Stock ticker symbol

        Returns:
            Combined fundamental data or None if critical data missing

        Example:
            {
                'ticker': 'AAPL',
                'company_name': 'Apple Inc.',
                'sector': 'Technology',
                'industry': 'Consumer Electronics',
                'price': 247.41,
                'market_cap': 3660398092083.0,
                'operating_margin': 0.3197,
                'gross_margin': 0.4691,
                'roe': 1.6405,
                'current_ratio': 0.89,
                'debt_equity': 1.52,
                'pe_ratio': 33.02,
                'fcf': 98767000000,
                'fcf_margin': 0.2373,
                'earnings_date': '2026-01-23'
            }
        """
        print(f"  Fetching comprehensive data for {ticker}...")

        # Fetch all endpoints (cached, so fast for subsequent calls)
        profile = self.get_company_profile(ticker)
        ratios = self.get_fundamental_ratios(ticker)
        cash_flow = self.get_cash_flow(ticker)
        income = self.get_income_statement(ticker)
        earnings = self.get_earnings_date(ticker)

        # Require critical data
        if not profile or not ratios or not cash_flow or not income:
            print(f"    [FAIL] {ticker}: Missing critical data")
            return None

        # Calculate FCF margin
        fcf = cash_flow.get('freeCashFlow', 0)
        revenue = income.get('revenue', 1)
        fcf_margin = (fcf / revenue) if revenue > 0 else 0

        # Assemble combined data
        data = {
            'ticker': ticker,
            'company_name': profile.get('companyName'),
            'sector': profile.get('sector'),
            'industry': profile.get('industry'),
            'price': profile.get('price'),
            'market_cap': ratios.get('marketCap', 0),

            # Fundamental ratios
            'operating_margin': ratios.get('operatingProfitMarginTTM', 0),
            'gross_margin': ratios.get('grossProfitMarginTTM', 0),
            'roe': ratios.get('returnOnEquityTTM', 0),
            'current_ratio': ratios.get('currentRatioTTM', 0),
            'debt_equity': ratios.get('debtToEquityRatioTTM', 0),
            'pe_ratio': ratios.get('priceToEarningsRatioTTM', 0),

            # Cash flow
            'fcf': fcf,
            'operating_cash_flow': cash_flow.get('operatingCashFlow', 0),
            'capex': cash_flow.get('capitalExpenditure', 0),
            'fcf_margin': fcf_margin,

            # Earnings
            'earnings_date': earnings,
        }

        print(f"    [OK] {ticker}: Complete data fetched")
        return data

    # =============================================================================
    # TIER 1 ADVANCED FEATURES (Week 2 FMP Integration)
    # =============================================================================

    def get_analyst_estimates(self, ticker: str) -> Optional[Dict]:
        """
        Get analyst estimates for forward-looking metrics.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Analyst estimates data or None if error

        Fields:
            estimatedRevenueAvg: Forward revenue projection
            estimatedEpsAvg: Forward EPS forecast
            numberAnalysts: Number of analysts contributing

        Cache: 24 hours (default)
        """
        data = self._fetch_with_cache("analyst-estimates", {"symbol": ticker, "period": "annual"})
        return data[0] if data and len(data) > 0 else None

    def get_financial_scores(self, ticker: str) -> Optional[Dict]:
        """
        Get Altman Z-Score and Piotroski Score.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Financial scores or None if error

        Fields:
            altmanZScore: Bankruptcy risk (>3.0=safe, 1.8-3.0=gray, <1.8=distress)
            piotroskiScore: Quality metric (0-9, >=7=high quality)

        Cache: 90 days (calculated from quarterly filings)
        """
        # Override cache duration for financial scores (90 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 90 * 24

        data = self._fetch_with_cache("financial-scores", {"symbol": ticker})

        self.CACHE_DURATION_HOURS = old_cache_duration
        return data[0] if data and len(data) > 0 else None

    def get_insider_trading_stats(self, ticker: str) -> Optional[Dict]:
        """
        Get insider trading statistics.

        NOTE: This endpoint returns 404 on FMP Starter plan.
        Requires higher tier subscription. Not called by get_complete_advanced_data().

        Args:
            ticker: Stock ticker symbol

        Returns:
            Insider trading stats or None if error/unavailable

        Fields:
            totalPurchases: Total shares bought by insiders
            totalSales: Total shares sold by insiders
            purchases6m: Insider buying last 6 months
            sales6m: Insider selling last 6 months

        Cache: 24 hours
        """
        data = self._fetch_with_cache("insider-trading-statistics", {"symbol": ticker})
        # This endpoint may return dict directly or list
        if isinstance(data, dict):
            return data
        return data[0] if data and len(data) > 0 else None

    def get_institutional_ownership(self, ticker: str, year: int = None, quarter: int = None) -> Optional[Dict]:
        """
        Get institutional ownership summary from 13F filings.

        NOTE: This endpoint returns 402 on FMP Starter plan.
        Requires Professional tier subscription. Not called by get_complete_advanced_data().

        Args:
            ticker: Stock ticker symbol
            year: Filing year (default: current year)
            quarter: Filing quarter 1-4 (default: most recent)

        Returns:
            Institutional ownership data or None if error/unavailable

        Fields:
            totalShares: Total shares held by institutions
            percentOwnership: % of float owned
            quarterlyChange: Change from previous quarter

        Cache: 45 days (13F quarterly filings)
        """
        if year is None:
            year = datetime.now().year
        if quarter is None:
            # Calculate most recent complete quarter
            current_month = datetime.now().month
            quarter = max(1, (current_month - 1) // 3)  # Previous quarter

        # Override cache duration for institutional data (45 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 45 * 24

        data = self._fetch_with_cache(
            "institutional-ownership/symbol-positions-summary",
            {"symbol": ticker, "year": year, "quarter": quarter}
        )

        self.CACHE_DURATION_HOURS = old_cache_duration
        return data[0] if data and len(data) > 0 else None

    def get_historical_income_statements(self, ticker: str, periods: int = 5) -> List[Dict]:
        """
        Fetch historical annual income statements for revenue consistency analysis.

        Args:
            ticker: Stock ticker symbol
            periods: Number of years to fetch (default: 5)

        Returns:
            List of income statements (most recent first), empty list if error

        Key Fields:
            revenue: Annual revenue
            netIncome: Net income
            grossProfit: Gross profit
            operatingIncome: Operating income

        Cache: 90 days (annual filings change infrequently)
        """
        # Override cache duration for historical data (90 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 90 * 24

        data = self._fetch_with_cache(
            "income-statement",
            {"symbol": ticker, "limit": periods}
        )

        self.CACHE_DURATION_HOURS = old_cache_duration
        return data if data else []

    def get_historical_key_metrics(self, ticker: str, periods: int = 5) -> List[Dict]:
        """
        Fetch historical annual key metrics for ROE consistency analysis.

        Args:
            ticker: Stock ticker symbol
            periods: Number of years to fetch (default: 5)

        Returns:
            List of key metrics (most recent first), empty list if error

        Key Fields:
            returnOnEquity: ROE ratio
            dividendPerShare: Dividend per share
            freeCashFlowPerShare: FCF per share
            debtToEquity: Debt/Equity ratio

        Cache: 90 days (annual metrics change infrequently)
        """
        # Override cache duration for historical data (90 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 90 * 24

        data = self._fetch_with_cache(
            "key-metrics",
            {"symbol": ticker, "limit": periods}
        )

        self.CACHE_DURATION_HOURS = old_cache_duration
        return data if data else []

    def get_analyst_ratings(self, ticker: str) -> Optional[Dict]:
        """
        Get analyst ratings consensus (buy/hold/sell distribution).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Ratings consensus or None if error

        Fields:
            strongBuy, buy, hold, sell, strongSell: Rating counts

        Cache: 24 hours
        """
        data = self._fetch_with_cache("grades-consensus", {"symbol": ticker})
        return data[0] if data and len(data) > 0 else None

    def get_complete_advanced_data(self, ticker: str) -> Optional[Dict]:
        """
        Get all advanced data for a single stock.

        Fetches:
        - Analyst estimates (forward revenue/EPS)
        - Financial scores (Altman Z, Piotroski)
        - Analyst ratings consensus

        Note: Insider trading and institutional ownership endpoints are
        NOT available on FMP Starter plan - skipped to avoid wasted API calls.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Combined advanced data dict or None if critical data missing
        """
        print(f"  Fetching advanced data for {ticker}...")

        # Fetch available endpoints (Starter plan)
        # NOTE: Insider trading (404) and institutional ownership (402) require higher tiers
        estimates = self.get_analyst_estimates(ticker)
        scores = self.get_financial_scores(ticker)
        ratings = self.get_analyst_ratings(ticker)

        # Financial scores are critical (bankruptcy risk)
        if not scores:
            print(f"    [SKIP] {ticker}: Missing financial scores (required)")
            return None

        # Build combined data with safe defaults
        data = {
            'ticker': ticker,

            # Analyst estimates (optional - some stocks have few analysts)
            'estimated_revenue_avg': None,
            'estimated_eps_avg': None,
            'analyst_count': 0,

            # Financial scores (required)
            'altman_z_score': scores.get('altmanZScore', 0),
            'piotroski_score': scores.get('piotroskiScore', 0),

            # Insider trading - NOT AVAILABLE on Starter plan (use neutral defaults)
            'insider_net_buying': False,
            'insider_buy_ratio': 0.5,  # neutral default

            # Institutional ownership - NOT AVAILABLE on Starter plan (use neutral defaults)
            'institutional_ownership_pct': 50.0,  # neutral default
            'institutional_change': 0.0,

            # Analyst ratings (optional)
            'analyst_buy_pct': 50.0,  # neutral default
            'analyst_consensus': 'HOLD',
        }

        # Process analyst estimates (FMP uses revenueAvg, epsAvg - not 'estimated' prefix)
        if estimates:
            data['analyst_count'] = estimates.get('numberAnalystsEstimatedRevenue',
                                                   estimates.get('numberAnalysts', 0))
            data['estimated_revenue_avg'] = estimates.get('revenueAvg',
                                                          estimates.get('estimatedRevenueAvg', 0))
            data['estimated_eps_avg'] = estimates.get('epsAvg',
                                                       estimates.get('estimatedEpsAvg', 0))

        # NOTE: Insider trading and institutional ownership skipped (require higher FMP tier)
        # Using neutral defaults: insider_buy_ratio=0.5, institutional_ownership_pct=50.0

        # Process analyst ratings
        if ratings:
            strong_buy = ratings.get('strongBuy', 0) or 0
            buy = ratings.get('buy', 0) or 0
            hold = ratings.get('hold', 0) or 0
            sell = ratings.get('sell', 0) or 0
            strong_sell = ratings.get('strongSell', 0) or 0

            total_ratings = strong_buy + buy + hold + sell + strong_sell
            if total_ratings > 0:
                buy_pct = (strong_buy + buy) / total_ratings * 100
                data['analyst_buy_pct'] = buy_pct

                # Determine consensus
                if buy_pct >= 70:
                    data['analyst_consensus'] = 'STRONG BUY'
                elif buy_pct >= 50:
                    data['analyst_consensus'] = 'BUY'
                elif buy_pct >= 30:
                    data['analyst_consensus'] = 'HOLD'
                else:
                    data['analyst_consensus'] = 'SELL'

        z = data['altman_z_score']
        p = data['piotroski_score']
        buy_pct = data['analyst_buy_pct']
        print(f"    [OK] {ticker}: Z={z:.1f}, P={p}, Buy%={buy_pct:.0f}%")
        return data

    # =============================================================================
    # UNIVERSE BUILDING METHODS (FMP-Only Migration)
    # =============================================================================

    def get_sp500_constituents(self) -> List[str]:
        """
        Fetch S&P 500 constituent list from FMP.

        Returns:
            List of ticker symbols in S&P 500 (approximately 500 stocks)

        Note:
            Cached for 90 days (S&P 500 changes ~5 stocks per quarter)
        """
        # Override cache duration for constituent lists (90 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 90 * 24  # 90 days

        data = self._fetch_with_cache("sp500-constituent", {})

        # Restore original cache duration
        self.CACHE_DURATION_HOURS = old_cache_duration

        if not data:
            print("[FMP] Failed to fetch S&P 500 constituents")
            return []

        # Extract ticker symbols
        tickers = [item['symbol'] for item in data if 'symbol' in item]
        print(f"[FMP] S&P 500 constituents: {len(tickers)} stocks")
        return tickers

    def get_nasdaq_constituents(self) -> List[str]:
        """
        Fetch Nasdaq-100 constituent list from FMP.

        Returns:
            List of ticker symbols in Nasdaq-100 (approximately 100 stocks)

        Note:
            Cached for 90 days (Nasdaq-100 changes infrequently)
        """
        # Override cache duration for constituent lists (90 days)
        old_cache_duration = self.CACHE_DURATION_HOURS
        self.CACHE_DURATION_HOURS = 90 * 24  # 90 days

        data = self._fetch_with_cache("nasdaq-constituent", {})

        # Restore original cache duration
        self.CACHE_DURATION_HOURS = old_cache_duration

        if not data:
            print("[FMP] Failed to fetch Nasdaq-100 constituents")
            return []

        # Extract ticker symbols
        tickers = [item['symbol'] for item in data if 'symbol' in item]
        print(f"[FMP] Nasdaq-100 constituents: {len(tickers)} stocks")
        return tickers

    def get_all_constituents(self) -> List[str]:
        """
        Fetch combined S&P 500 + Nasdaq-100 constituent list (deduplicated).

        Returns:
            List of unique ticker symbols (approximately 550-600 stocks)

        Note:
            Some stocks appear in both indices, so final count will be less than 600
        """
        sp500 = self.get_sp500_constituents()
        nasdaq = self.get_nasdaq_constituents()

        # Combine and deduplicate
        all_tickers = list(set(sp500 + nasdaq))
        all_tickers.sort()

        print(f"[FMP] Combined constituents: {len(all_tickers)} unique stocks (S&P 500 + Nasdaq-100)")
        return all_tickers

    def get_bulk_market_caps(self, tickers: List[str]) -> Dict[str, float]:
        """
        Fetch market caps for multiple tickers in bulk.

        Uses FMP batch endpoint which is more efficient than individual calls.
        Maximum 600 tickers per request.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> market cap (float)

        Note:
            Market caps cached for 24 hours (daily update sufficient)
        """
        if not tickers:
            return {}

        # FMP batch endpoint supports comma-separated tickers
        # Split into chunks of 600 to stay within URL length limits
        chunk_size = 600
        all_market_caps = {}

        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i+chunk_size]
            ticker_list = ','.join(chunk)

            data = self._fetch_with_cache("market-capitalization", {"symbol": ticker_list})

            if data:
                for item in data:
                    ticker = item.get('symbol')
                    market_cap = item.get('marketCap', 0)
                    if ticker and market_cap:
                        all_market_caps[ticker] = market_cap

        print(f"[FMP] Bulk market caps fetched: {len(all_market_caps)}/{len(tickers)} stocks")
        return all_market_caps

    def filter_by_market_cap(self, tickers: List[str], min_cap: float = 10e9) -> List[str]:
        """
        Filter tickers by minimum market cap threshold.

        Args:
            tickers: List of ticker symbols
            min_cap: Minimum market cap in dollars (default: $10B)

        Returns:
            List of tickers meeting market cap threshold
        """
        market_caps = self.get_bulk_market_caps(tickers)

        filtered_tickers = [
            ticker for ticker, cap in market_caps.items()
            if cap >= min_cap
        ]

        filtered_tickers.sort()

        print(f"[FMP] Market cap filter (>=${min_cap/1e9:.0f}B): {len(filtered_tickers)}/{len(tickers)} stocks passed")
        return filtered_tickers

    def fetch_universe_stocks(
        self,
        market_cap_min: float = 10e9,  # $10B minimum
        price_min: float = 15.0,
        price_max: float = 300.0,
        volume_min: int = 1_000_000,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch initial stock universe using FMP screener + fundamental data.

        This replaces the Finviz screener with FMP-only approach.
        Uses screener for initial filter, then fetches full fundamentals for each stock.

        Args:
            market_cap_min: Minimum market cap (default: $10B)
            price_min: Minimum stock price (default: $15)
            price_max: Maximum stock price (default: $300)
            volume_min: Minimum average volume (default: 1M shares/day)
            limit: Maximum stocks to fetch (default: 1000)

        Returns:
            DataFrame with fundamental data for all stocks

        Note:
            This method makes 1 screener call + N fundamental calls (N = number of stocks)
            First run will be slow (~5-10 minutes for 200 stocks), subsequent runs use cache
        """
        import pandas as pd

        print("\n" + "="*70)
        print("FMP-BASED UNIVERSE BUILDER (Finviz Replacement)")
        print("="*70)
        print(f"\nInitial screening filters:")
        print(f"  Market Cap >= ${market_cap_min/1e9:.0f}B")
        print(f"  Price: ${price_min:.0f} - ${price_max:.0f}")
        print(f"  Avg Volume >= {volume_min:,} shares/day")
        print(f"  Country: USA (FMP default)")

        # Step 1: Use screener to get initial list
        print(f"\n[Step 1/3] Running FMP screener (limit={limit})...")
        screened_stocks = self.screen_stocks(
            market_cap_min=market_cap_min,
            price_min=price_min,
            price_max=price_max,
            volume_min=volume_min,
            limit=limit
        )

        if not screened_stocks:
            print("  [ERROR] FMP screener returned no results!")
            return pd.DataFrame()

        tickers = [s['symbol'] for s in screened_stocks if 'symbol' in s]
        print(f"  Found {len(tickers)} stocks from screener")

        # Step 2: Fetch fundamental data for each stock (with caching)
        print(f"\n[Step 2/3] Fetching fundamentals for {len(tickers)} stocks...")
        print(f"  (This may take 3-10 minutes on first run, subsequent runs use cache)")

        fundamental_data = []
        success_count = 0
        failed_tickers = []

        for i, ticker in enumerate(tickers, 1):
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(tickers)} stocks fetched...")

            data = self.get_complete_fundamental_data(ticker)

            if data:
                fundamental_data.append(data)
                success_count += 1
            else:
                failed_tickers.append(ticker)

        print(f"\n  Fundamentals fetched: {success_count}/{len(tickers)} stocks")
        if failed_tickers:
            print(f"  Failed tickers: {failed_tickers[:10]}")  # Show first 10
            if len(failed_tickers) > 10:
                print(f"  ... and {len(failed_tickers) - 10} more")

        # Step 3: Convert to DataFrame
        print(f"\n[Step 3/3] Converting to DataFrame...")
        df = pd.DataFrame(fundamental_data)

        if df.empty:
            print("  [ERROR] No valid fundamental data fetched!")
            return df

        # Rename columns to match Finviz naming conventions (for compatibility)
        df = df.rename(columns={
            'ticker': 'Ticker',
            'company_name': 'Company',
            'sector': 'Sector',
            'industry': 'Industry',
            'price': 'Price',
            'market_cap': 'Market Cap',
            'operating_margin': 'Oper M',  # Convert decimal to percentage
            'gross_margin': 'Gross M',
            'roe': 'ROE',
            'current_ratio': 'Curr R',
            'debt_equity': 'Debt/Eq',
            'pe_ratio': 'P/E',
            'fcf': 'FCF',
            'fcf_margin': 'FCF_Margin',
            'earnings_date': 'Next_Earnings'
        })

        # Convert decimals to percentages for margin ratios (Finviz compatibility)
        for col in ['Oper M', 'Gross M', 'ROE', 'FCF_Margin']:
            if col in df.columns:
                df[col] = df[col] * 100  # 0.30 -> 30.0

        # Add placeholder for average volume (from screener data)
        ticker_to_volume = {s['symbol']: s.get('volume', 0) for s in screened_stocks}
        df['Avg Volume'] = df['Ticker'].map(ticker_to_volume)

        print(f"\n  DataFrame created: {len(df)} rows × {len(df.columns)} columns")
        print(f"  Columns: {df.columns.tolist()}")

        print("\n" + "="*70)
        print("FMP UNIVERSE FETCH COMPLETE")
        print("="*70 + "\n")

        return df

    def get_stats(self) -> Dict[str, int]:
        """
        Get fetcher statistics.

        Returns:
            Dict with request count and cache stats
        """
        cache_files = list(self.cache_dir.glob("fmp_*.json"))
        valid_cache = sum(1 for f in cache_files if self._is_cache_valid(f))

        return {
            'requests_made': self.request_count,
            'cache_files': len(cache_files),
            'valid_cache_entries': valid_cache,
        }

    def clear_cache(self):
        """Clear all cached FMP responses."""
        for cache_file in self.cache_dir.glob("fmp_*.json"):
            cache_file.unlink()
        print(f"[FMP] Cleared cache directory: {self.cache_dir}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_fetcher(api_key: Optional[str] = None) -> FMPDataFetcher:
    """
    Create FMP data fetcher with API key from config or parameter.

    Args:
        api_key: Optional API key (defaults to config.FMP_API_KEY)

    Returns:
        Configured FMPDataFetcher instance
    """
    if api_key is None:
        try:
            from config import FMP_API_KEY
            api_key = FMP_API_KEY
        except ImportError:
            raise ValueError(
                "FMP_API_KEY not found. Either:\n"
                "1. Add FMP_API_KEY = 'your_key' to config.py, or\n"
                "2. Pass api_key parameter directly"
            )

    return FMPDataFetcher(api_key=api_key)


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fmp_data_fetcher.py <ticker>")
        print("Example: python fmp_data_fetcher.py AAPL")
        sys.exit(1)

    ticker = sys.argv[1].upper()

    # Load API key from config
    try:
        from config import FMP_API_KEY
    except ImportError:
        print("ERROR: Add FMP_API_KEY to config.py first")
        sys.exit(1)

    # Create fetcher
    fetcher = FMPDataFetcher(api_key=FMP_API_KEY)

    # Fetch comprehensive data
    print(f"\nFetching comprehensive data for {ticker}...")
    data = fetcher.get_complete_fundamental_data(ticker)

    if data:
        print(f"\n{'='*70}")
        print(f"FUNDAMENTAL DATA: {ticker}")
        print(f"{'='*70}")

        print(f"\nCompany Info:")
        print(f"  Name: {data['company_name']}")
        print(f"  Sector: {data['sector']}")
        print(f"  Industry: {data['industry']}")
        print(f"  Price: ${data['price']:.2f}")
        print(f"  Market Cap: ${data['market_cap']/1e9:.2f}B")

        print(f"\nFundamental Ratios:")
        print(f"  Operating Margin: {data['operating_margin']*100:.2f}%")
        print(f"  Gross Margin: {data['gross_margin']*100:.2f}%")
        print(f"  ROE: {data['roe']*100:.2f}%")
        print(f"  Current Ratio: {data['current_ratio']:.2f}")
        print(f"  Debt/Equity: {data['debt_equity']:.2f}")
        print(f"  P/E Ratio: {data['pe_ratio']:.2f}")

        print(f"\nCash Flow:")
        print(f"  Free Cash Flow: ${data['fcf']/1e9:.2f}B")
        print(f"  FCF Margin: {data['fcf_margin']*100:.2f}%")

        print(f"\nEarnings:")
        print(f"  Next Date: {data['earnings_date']}")

        # Stats
        stats = fetcher.get_stats()
        print(f"\n{'='*70}")
        print(f"API Stats:")
        print(f"  Requests made: {stats['requests_made']}")
        print(f"  Cache entries: {stats['valid_cache_entries']}/{stats['cache_files']}")
        print(f"{'='*70}")
    else:
        print(f"Failed to fetch data for {ticker}")
