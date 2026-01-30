"""
Earnings date checker using FMP API exclusively
Validates that stocks don't have earnings within the trade window

DESIGN PRINCIPLES:
- FMP API is the ONLY data source (no yfinance, no web scraping)
- Missing earnings data triggers WARNING, not rejection
- User is responsible for manual verification when data unavailable
- 12-hour cache to minimize API calls (FMP 250 calls/day limit)
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
import json
import os
from config import FMP_API_KEY


class EarningsChecker:
    """
    Check earnings dates using FMP API exclusively.

    Fail-open design: If FMP data unavailable, allows trade with warning
    rather than rejecting (user must manually verify).

    Note: FMP's earnings-calendar endpoint returns ALL stocks' earnings.
    We fetch the full calendar once and cache it, then filter locally by ticker.
    """

    def __init__(self, cache_file: str = "./earnings_cache.json", cache_expiry_hours: int = 12):
        """
        Initialize EarningsChecker with FMP API configuration.

        Args:
            cache_file: Path to cache file for earnings dates
            cache_expiry_hours: Hours before cache entries expire (default: 12)
        """
        self.cache_file = cache_file
        self.cache_expiry_hours = cache_expiry_hours
        self.cache = self._load_cache()
        self.fmp_api_key = FMP_API_KEY
        self.fmp_base_url = "https://financialmodelingprep.com/stable"

        # Full calendar cache (separate from per-ticker cache)
        self._calendar_cache = None
        self._calendar_fetched_at = None

    def _load_cache(self) -> Dict:
        """Load earnings cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save earnings cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save earnings cache: {e}")

    def _is_cache_valid(self, ticker: str) -> bool:
        """
        Check if cached earnings data is still valid (not expired).

        Args:
            ticker: Stock ticker

        Returns:
            True if cache exists and is <12 hours old
        """
        if ticker not in self.cache:
            return False

        cached_time = datetime.fromisoformat(self.cache[ticker].get("cached_at", "2000-01-01"))
        expiry_time = cached_time + timedelta(hours=self.cache_expiry_hours)

        return datetime.now() < expiry_time

    def _fetch_full_calendar(self) -> Dict[str, Dict]:
        """
        Fetch the full earnings calendar from FMP and index by ticker.

        FMP's earnings-calendar endpoint returns all stocks' earnings (past and future).
        We fetch once and cache in memory, then look up individual tickers.

        Returns:
            Dict mapping ticker -> {
                'last_earnings': datetime or None (most recent past date),
                'next_earnings': datetime or None (earliest future date)
            }
        """
        # Check if we have a recent calendar in memory
        if self._calendar_cache is not None and self._calendar_fetched_at is not None:
            age = datetime.now() - self._calendar_fetched_at
            if age < timedelta(hours=self.cache_expiry_hours):
                return self._calendar_cache

        print("  [FMP] Fetching full earnings calendar...")

        try:
            # Fetch without date filter to get both past and future earnings
            url = f"{self.fmp_base_url}/earnings-calendar"
            params = {
                'apikey': self.fmp_api_key
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data or not isinstance(data, list):
                print("  [WARN] FMP returned empty earnings calendar")
                self._calendar_cache = {}
                self._calendar_fetched_at = datetime.now()
                return {}

            # Index by ticker - track both past and future dates
            calendar = {}
            today_date = datetime.now().date()

            for event in data:
                ticker = event.get('symbol')
                date_str = event.get('date')

                if not ticker or not date_str:
                    continue

                try:
                    earnings_dt = datetime.strptime(date_str, '%Y-%m-%d')

                    if ticker not in calendar:
                        calendar[ticker] = {
                            'last_earnings': None,
                            'next_earnings': None
                        }

                    if earnings_dt.date() <= today_date:
                        # Past earnings - keep most recent
                        if (calendar[ticker]['last_earnings'] is None or
                            earnings_dt > calendar[ticker]['last_earnings']):
                            calendar[ticker]['last_earnings'] = earnings_dt
                    else:
                        # Future earnings - keep earliest
                        if (calendar[ticker]['next_earnings'] is None or
                            earnings_dt < calendar[ticker]['next_earnings']):
                            calendar[ticker]['next_earnings'] = earnings_dt

                except ValueError:
                    continue

            print(f"  [FMP] Indexed earnings for {len(calendar)} stocks")

            self._calendar_cache = calendar
            self._calendar_fetched_at = datetime.now()
            return calendar

        except requests.exceptions.HTTPError as e:
            print(f"  [WARN] FMP HTTP error fetching calendar: {e.response.status_code}")
            return {}
        except requests.exceptions.Timeout:
            print("  [WARN] FMP calendar fetch timeout")
            return {}
        except Exception as e:
            print(f"  [ERROR] FMP calendar fetch failed: {type(e).__name__}: {e}")
            return {}

    def get_earnings_info(self, ticker: str, use_cache: bool = True) -> Dict:
        """
        Get earnings information for a ticker using FMP API.

        Returns both last and next earnings dates when available.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            Dict with:
            - 'last_earnings': datetime or None (most recent past date)
            - 'next_earnings': datetime or None (earliest future date)
            - 'status': 'found', 'not_found', or 'error'
        """
        # Check per-ticker cache first
        if use_cache and self._is_cache_valid(ticker):
            cached = self.cache[ticker]
            result = {
                'last_earnings': None,
                'next_earnings': None,
                'status': cached.get('status', 'found')
            }
            if cached.get('last_earnings'):
                result['last_earnings'] = datetime.fromisoformat(cached['last_earnings'])
            if cached.get('next_earnings'):
                result['next_earnings'] = datetime.fromisoformat(cached['next_earnings'])
            return result

        # Look up in full calendar
        calendar = self._fetch_full_calendar()

        if ticker in calendar:
            info = calendar[ticker]

            # Cache successful result
            self.cache[ticker] = {
                "last_earnings": info['last_earnings'].isoformat() if info['last_earnings'] else None,
                "next_earnings": info['next_earnings'].isoformat() if info['next_earnings'] else None,
                "cached_at": datetime.now().isoformat(),
                "source": "FMP",
                "status": "found"
            }
            self._save_cache()

            return {
                'last_earnings': info['last_earnings'],
                'next_earnings': info['next_earnings'],
                'status': 'found'
            }

        # Ticker not in calendar
        self.cache[ticker] = {
            "last_earnings": None,
            "next_earnings": None,
            "cached_at": datetime.now().isoformat(),
            "source": "FMP",
            "status": "not_found"
        }
        self._save_cache()

        return {
            'last_earnings': None,
            'next_earnings': None,
            'status': 'not_found'
        }

    def get_next_earnings_date(self, ticker: str, use_cache: bool = True) -> Optional[datetime]:
        """
        Get the next earnings date for a ticker using FMP API.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            datetime of next earnings, or None if no future date scheduled
        """
        info = self.get_earnings_info(ticker, use_cache)
        return info['next_earnings']

    def check_earnings_safe(
        self,
        ticker: str,
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = True  # CRITICAL: Default changed to True (fail-open)
    ) -> Tuple[bool, Optional[datetime], str]:
        """
        Check if a stock is safe to trade (no earnings within window).

        CRITICAL DESIGN CHANGE:
        - Default behavior (allow_unverified=True): Missing data = PROCEED with warning
        - Conservative mode (allow_unverified=False): Missing data = REJECT

        Decision Logic:
        1. If FUTURE earnings found and SAFE -> (True, date, "SAFE - earnings on YYYY-MM-DD...")
        2. If FUTURE earnings found and CONFLICT -> (False, date, "REJECT - earnings conflict")
        3. If NO future earnings but RECENT past earnings (within 90 days):
           -> (True, last_date, "SAFE - last earnings on YYYY-MM-DD, next not yet scheduled")
        4. If NO data at all:
           a. allow_unverified=True -> (True, None, "UNVERIFIED - manually check")
           b. allow_unverified=False -> (False, None, "REJECTED - earnings unverified")

        Args:
            ticker: Stock ticker
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration (default: 7)
            allow_unverified: If True (default), proceed when FMP data missing

        Returns:
            Tuple of (is_safe, earnings_date, reason)
            - is_safe: True if OK to trade, False if earnings conflict
            - earnings_date: The next earnings date (if found)
            - reason: Human-readable explanation

        Examples:
            (True, datetime(...), "SAFE - earnings on 2026-05-01 (20 days after buffer)")
            (False, datetime(...), "REJECT - earnings on 2026-03-10 (5 days before exp)")
            (True, datetime(...), "SAFE - last earnings on 2026-01-29, next not yet scheduled")
            (True, None, "UNVERIFIED - FMP data unavailable, verify manually on Yahoo Finance")
        """
        # Check if this is a manual/ETF ticker (no earnings to check)
        try:
            from universe import is_manual_ticker
            if is_manual_ticker(ticker):
                return (True, None, "SAFE - ETF/manual ticker (no earnings)")
        except ImportError:
            pass

        info = self.get_earnings_info(ticker)
        last_earnings = info['last_earnings']
        next_earnings = info['next_earnings']
        status = info['status']

        today = datetime.now()
        danger_end = expiration_date + timedelta(days=buffer_days)

        # Remove timezone info for comparison if present
        if expiration_date.tzinfo is not None:
            expiration_date = expiration_date.replace(tzinfo=None)

        # CASE 1: Future earnings date exists - check for conflicts
        if next_earnings is not None:
            if next_earnings.tzinfo is not None:
                next_earnings = next_earnings.replace(tzinfo=None)

            # Check if earnings falls within danger window
            if today <= next_earnings <= danger_end:
                days_to_earnings = (next_earnings - today).days
                return (
                    False,
                    next_earnings,
                    f"REJECT - earnings on {next_earnings.strftime('%Y-%m-%d')} ({days_to_earnings} days away)"
                )

            # Future earnings is outside danger window (SAFE)
            days_after_expiry = (next_earnings - danger_end).days
            return (
                True,
                next_earnings,
                f"SAFE - earnings on {next_earnings.strftime('%Y-%m-%d')} ({days_after_expiry} days after buffer)"
            )

        # CASE 2: No future earnings, but we have recent past earnings
        # This means the company just reported and next date isn't scheduled yet
        if last_earnings is not None:
            if last_earnings.tzinfo is not None:
                last_earnings = last_earnings.replace(tzinfo=None)

            days_since_last = (today - last_earnings).days

            # If last earnings was within 90 days, they're likely safe
            # (Most companies report quarterly, so next is ~90 days out)
            if days_since_last <= 90:
                return (
                    True,
                    last_earnings,
                    f"SAFE - last earnings {days_since_last}d ago ({last_earnings.strftime('%Y-%m-%d')}), next not yet scheduled"
                )
            else:
                # Last earnings was >90 days ago - unusual, warn user
                if allow_unverified:
                    return (
                        True,
                        last_earnings,
                        f"UNVERIFIED - last earnings {days_since_last}d ago, manually verify next date"
                    )
                else:
                    return (
                        False,
                        last_earnings,
                        f"REJECTED - last earnings {days_since_last}d ago, no next date (strict mode)"
                    )

        # CASE 3: No data at all
        if allow_unverified:
            return (
                True,
                None,
                "UNVERIFIED - FMP data unavailable, manually verify earnings on Yahoo Finance before trading"
            )
        else:
            return (
                False,
                None,
                "REJECTED - earnings date unavailable (strict mode enabled)"
            )

    def batch_check_earnings(
        self,
        tickers: List[str],
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = True
    ) -> Dict[str, Tuple[bool, Optional[datetime], str]]:
        """
        Check earnings safety for multiple tickers.

        Args:
            tickers: List of stock tickers
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration
            allow_unverified: If True (default), include unverified stocks

        Returns:
            Dict mapping ticker to (is_safe, earnings_date, reason)
        """
        results = {}
        for ticker in tickers:
            results[ticker] = self.check_earnings_safe(
                ticker, expiration_date, buffer_days, allow_unverified
            )
        return results

    def get_safe_tickers(
        self,
        tickers: List[str],
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = True
    ) -> List[str]:
        """
        Filter tickers to only those safe from earnings.

        Args:
            tickers: List of stock tickers
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration
            allow_unverified: If True (default), include unverified stocks

        Returns:
            List of safe tickers
        """
        results = self.batch_check_earnings(
            tickers, expiration_date, buffer_days, allow_unverified
        )
        return [ticker for ticker, (is_safe, _, _) in results.items() if is_safe]

    def clear_cache(self):
        """Clear the earnings cache."""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("Earnings cache cleared")


# =============================================================================
# STANDALONE USAGE FOR TESTING
# =============================================================================

if __name__ == "__main__":
    # Test the earnings checker
    checker = EarningsChecker()

    test_tickers = ["AAPL", "INTC", "AMD", "TSLA", "KO", "PG", "NFLX"]

    # Test expiration date (35 days from now - typical DTE)
    exp_date = datetime.now() + timedelta(days=35)

    print(f"\n{'='*70}")
    print(f"FMP EARNINGS CHECKER TEST")
    print(f"Expiration: {exp_date.strftime('%Y-%m-%d')} (35 DTE)")
    print(f"Buffer: 7 days")
    print(f"{'='*70}\n")

    for ticker in test_tickers:
        is_safe, earnings_date, reason = checker.check_earnings_safe(
            ticker, exp_date, buffer_days=7, allow_unverified=True
        )

        status_symbol = "+" if is_safe else "X"
        warning_flag = "[!] " if "UNVERIFIED" in reason else ""

        print(f"[{status_symbol}] {warning_flag}{ticker:6s}: {reason}")

    print(f"\n{'='*70}")
    safe = checker.get_safe_tickers(test_tickers, exp_date, buffer_days=7, allow_unverified=True)
    print(f"Safe tickers: {', '.join(safe)}")
    print(f"{'='*70}\n")
