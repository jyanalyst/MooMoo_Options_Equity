"""
Earnings date checker using FMP API exclusively
Validates that stocks don't have earnings within the trade window

DESIGN PRINCIPLES:
- FMP API is the ONLY data source (no yfinance, no web scraping)
- FAIL-CLOSED by default: missing earnings data => REJECT (never trade blind
  through an unverified earnings window). Override per-run with allow_unverified.
- 12-hour cache to minimize API calls (FMP 250 calls/day limit)
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import json
import os
from config import FMP_API_KEY


class EarningsChecker:
    """
    Check earnings dates using FMP API exclusively.

    FAIL-CLOSED design: if FMP data is unavailable the stock is REJECTED
    (allow_unverified=False default). An UNVERIFIED name must never silently
    look like a confirmed SAFE one.

    Uses the per-symbol /stable/earnings endpoint (the bulk earnings-calendar
    endpoint ignores `symbol` and truncates to 4000 rows — unusable).
    """

    def __init__(
        self, cache_file: str = "./earnings_cache.json", cache_expiry_hours: int = 12
    ):
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

    def _load_cache(self) -> Dict:
        """Load earnings cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save earnings cache to file."""
        try:
            with open(self.cache_file, "w") as f:
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

        cached_time = datetime.fromisoformat(
            self.cache[ticker].get("cached_at", "2000-01-01")
        )
        expiry_time = cached_time + timedelta(hours=self.cache_expiry_hours)

        return datetime.now() < expiry_time

    def _fetch_symbol_earnings(self, ticker: str) -> Dict:
        """
        Fetch a single symbol's earnings via the per-symbol /stable/earnings endpoint.

        This endpoint genuinely filters by `symbol` and returns that ticker's full
        earnings history + estimates. The bulk /earnings-calendar endpoint does NOT
        (it ignores `symbol` and caps at 4000 rows, dropping most names) — that was the
        root cause of the "all UNVERIFIED" dark feed.

        Returns:
            {'last_earnings': datetime|None, 'next_earnings': datetime|None,
             'status': 'found' | 'not_found' | 'error'}
            status='error' on any network/HTTP failure (caller fails closed and does
            NOT cache the result).
        """
        url = f"{self.fmp_base_url}/earnings"
        params = {"symbol": ticker, "apikey": self.fmp_api_key}
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list) or not data:
                return {
                    "last_earnings": None,
                    "next_earnings": None,
                    "status": "not_found",
                }

            today = datetime.now()
            last_earnings = None  # most recent past date
            next_earnings = None  # earliest future date
            for event in data:
                if (
                    event.get("symbol") != ticker
                ):  # defensive; endpoint should pre-filter
                    continue
                date_str = event.get("date")
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                if dt <= today:
                    if last_earnings is None or dt > last_earnings:
                        last_earnings = dt
                else:
                    if next_earnings is None or dt < next_earnings:
                        next_earnings = dt

            return {
                "last_earnings": last_earnings,
                "next_earnings": next_earnings,
                "status": "found",
            }

        except requests.exceptions.HTTPError as e:
            print(f"  [WARN] FMP earnings HTTP {e.response.status_code} for {ticker}")
            return {"last_earnings": None, "next_earnings": None, "status": "error"}
        except Exception as e:
            print(
                f"  [WARN] FMP earnings fetch failed for {ticker}: {type(e).__name__}: {e}"
            )
            return {"last_earnings": None, "next_earnings": None, "status": "error"}

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
                "last_earnings": None,
                "next_earnings": None,
                "status": cached.get("status", "found"),
            }
            if cached.get("last_earnings"):
                result["last_earnings"] = datetime.fromisoformat(
                    cached["last_earnings"]
                )
            if cached.get("next_earnings"):
                result["next_earnings"] = datetime.fromisoformat(
                    cached["next_earnings"]
                )
            return result

        # Fetch this symbol's earnings (per-symbol endpoint actually filters by symbol,
        # unlike the bulk earnings-calendar which ignores `symbol` and truncates to 4000 rows).
        info = self._fetch_symbol_earnings(ticker)

        # Never cache a transient error: a quota/network blip must not stay sticky for
        # the 12h TTL and keep the feed artificially dark.
        if info["status"] != "error":
            self.cache[ticker] = {
                "last_earnings": info["last_earnings"].isoformat()
                if info["last_earnings"]
                else None,
                "next_earnings": info["next_earnings"].isoformat()
                if info["next_earnings"]
                else None,
                "cached_at": datetime.now().isoformat(),
                "source": "FMP",
                "status": info["status"],
            }
            self._save_cache()

        return info

    def get_next_earnings_date(
        self, ticker: str, use_cache: bool = True
    ) -> Optional[datetime]:
        """
        Get the next earnings date for a ticker using FMP API.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            datetime of next earnings, or None if no future date scheduled
        """
        info = self.get_earnings_info(ticker, use_cache)
        return info["next_earnings"]

    def check_earnings_safe(
        self,
        ticker: str,
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = False,  # FAIL-CLOSED: missing data => REJECT (never trade blind)
    ) -> Tuple[bool, Optional[datetime], str]:
        """
        Check if a stock is safe to trade (no earnings within window).

        FAIL-CLOSED by default (allow_unverified=False): missing data = REJECT.
        Pass allow_unverified=True only when every UNVERIFIED name will be
        manually verified before trading.

        Decision Logic:
        1. If FUTURE earnings found and SAFE -> (True, date, "SAFE - earnings on YYYY-MM-DD...")
        2. If FUTURE earnings found and CONFLICT -> (False, date, "REJECT - earnings conflict")
        3. If NO future earnings but RECENT past earnings (within 90 days):
           -> (True, last_date, "SAFE - last earnings on YYYY-MM-DD, next not yet scheduled")
        4. If NO data at all:
           a. allow_unverified=False (default) -> (False, None, "REJECTED - earnings unverified")
           b. allow_unverified=True -> (True, None, "UNVERIFIED - manually check")

        Args:
            ticker: Stock ticker
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration (default: 7)
            allow_unverified: If True, proceed (flagged UNVERIFIED) when FMP data missing

        Returns:
            Tuple of (is_safe, earnings_date, reason)
            - is_safe: True if OK to trade, False if earnings conflict
            - earnings_date: The next earnings date (if found)
            - reason: Human-readable explanation
        """
        info = self.get_earnings_info(ticker)
        last_earnings = info["last_earnings"]
        next_earnings = info["next_earnings"]

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
                    f"REJECT - earnings on {next_earnings.strftime('%Y-%m-%d')} ({days_to_earnings} days away)",
                )

            # Future earnings is outside danger window (SAFE)
            days_after_expiry = (next_earnings - danger_end).days
            return (
                True,
                next_earnings,
                f"SAFE - earnings on {next_earnings.strftime('%Y-%m-%d')} ({days_after_expiry} days after buffer)",
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
                    f"SAFE - last earnings {days_since_last}d ago ({last_earnings.strftime('%Y-%m-%d')}), next not yet scheduled",
                )
            else:
                # Last earnings was >90 days ago - unusual, warn user
                if allow_unverified:
                    return (
                        True,
                        last_earnings,
                        f"UNVERIFIED - last earnings {days_since_last}d ago, manually verify next date",
                    )
                else:
                    return (
                        False,
                        last_earnings,
                        f"REJECTED - last earnings {days_since_last}d ago, no next date (strict mode)",
                    )

        # CASE 3: No data at all
        if allow_unverified:
            return (
                True,
                None,
                "UNVERIFIED - FMP data unavailable, manually verify earnings on Yahoo Finance before trading",
            )
        else:
            return (
                False,
                None,
                "REJECTED - earnings date unavailable (strict mode enabled)",
            )

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

    print(f"\n{'=' * 70}")
    print("FMP EARNINGS CHECKER TEST")
    print(f"Expiration: {exp_date.strftime('%Y-%m-%d')} (35 DTE)")
    print("Buffer: 7 days")
    print(f"{'=' * 70}\n")

    for ticker in test_tickers:
        is_safe, earnings_date, reason = checker.check_earnings_safe(
            ticker, exp_date, buffer_days=7
        )

        status_symbol = "+" if is_safe else "X"
        warning_flag = "[!] " if "UNVERIFIED" in reason else ""

        print(f"[{status_symbol}] {warning_flag}{ticker:6s}: {reason}")

    print(f"\n{'=' * 70}\n")
