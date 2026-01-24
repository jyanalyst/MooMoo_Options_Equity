"""
Earnings date checker using yfinance
Validates that stocks don't have earnings within the trade window
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import json
import os


class EarningsChecker:
    """
    Check earnings dates for stocks using yfinance.
    Caches results to minimize API calls.
    """
    
    def __init__(self, cache_file: str = "./earnings_cache.json", cache_expiry_hours: int = 12):
        """
        Initialize EarningsChecker.
        
        Args:
            cache_file: Path to cache file for earnings dates
            cache_expiry_hours: Hours before cache entries expire
        """
        self.cache_file = cache_file
        self.cache_expiry_hours = cache_expiry_hours
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load earnings cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_cache(self):
        """Save earnings cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save earnings cache: {e}")
    
    def _is_cache_valid(self, ticker: str) -> bool:
        """Check if cached earnings data is still valid"""
        if ticker not in self.cache:
            return False
        
        cached_time = datetime.fromisoformat(self.cache[ticker].get("cached_at", "2000-01-01"))
        expiry_time = cached_time + timedelta(hours=self.cache_expiry_hours)
        
        return datetime.now() < expiry_time
    
    def get_next_earnings_date(self, ticker: str, use_cache: bool = True) -> Optional[datetime]:
        """
        Get the next earnings date for a ticker.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            use_cache: Whether to use cached data if available
            
        Returns:
            datetime of next earnings, or None if not found
        """
        # Check cache first
        if use_cache and self._is_cache_valid(ticker):
            cached_date = self.cache[ticker].get("next_earnings")
            if cached_date:
                return datetime.fromisoformat(cached_date)
            return None
        
        # Fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            calendar = stock.calendar
            
            # yfinance returns earnings date in different formats depending on version
            earnings_date = None
            
            if calendar is not None:
                # Try to extract earnings date from calendar
                if isinstance(calendar, dict):
                    # Newer yfinance versions return a dict
                    if 'Earnings Date' in calendar:
                        dates = calendar['Earnings Date']
                        if isinstance(dates, list) and len(dates) > 0:
                            earnings_date = dates[0]
                        elif dates is not None:
                            earnings_date = dates
                elif hasattr(calendar, 'iloc'):
                    # Older versions return a DataFrame
                    if 'Earnings Date' in calendar.index:
                        earnings_date = calendar.loc['Earnings Date'].iloc[0]
            
            # Also try earnings_dates attribute
            if earnings_date is None:
                try:
                    earnings_dates = stock.earnings_dates
                    if earnings_dates is not None and len(earnings_dates) > 0:
                        # Get the next upcoming earnings date
                        future_dates = earnings_dates[earnings_dates.index > datetime.now()]
                        if len(future_dates) > 0:
                            earnings_date = future_dates.index[0]
                except Exception:
                    pass
            
            # Convert to datetime if needed
            if earnings_date is not None:
                if isinstance(earnings_date, str):
                    earnings_date = datetime.fromisoformat(earnings_date.replace('Z', '+00:00'))
                elif hasattr(earnings_date, 'to_pydatetime'):
                    earnings_date = earnings_date.to_pydatetime()
                elif not isinstance(earnings_date, datetime):
                    earnings_date = None
            
            # Cache the result
            self.cache[ticker] = {
                "next_earnings": earnings_date.isoformat() if earnings_date else None,
                "cached_at": datetime.now().isoformat()
            }
            self._save_cache()
            
            return earnings_date
            
        except Exception as e:
            print(f"Warning: Could not fetch earnings for {ticker}: {e}")
            # Cache the failure to avoid repeated failed lookups
            self.cache[ticker] = {
                "next_earnings": None,
                "cached_at": datetime.now().isoformat(),
                "error": str(e)
            }
            self._save_cache()
            return None
    
    def check_earnings_safe(
        self,
        ticker: str,
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = False
    ) -> Tuple[bool, Optional[datetime], str]:
        """
        Check if a stock is safe to trade (no earnings within window).

        CONSERVATIVE VALIDATION (UPDATED):
        - By default, rejects stocks where earnings date cannot be verified
        - Set allow_unverified=True to override (manual verification required)

        Args:
            ticker: Stock ticker
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration
            allow_unverified: If False (default), reject stocks with missing earnings data

        Returns:
            Tuple of (is_safe, earnings_date, reason)
            - is_safe: True if OK to trade, False if earnings conflict or unverified
            - earnings_date: The next earnings date (if found)
            - reason: Human-readable explanation
        """
        earnings_date = self.get_next_earnings_date(ticker)

        if earnings_date is None:
            if allow_unverified:
                # OVERRIDE MODE: Allow with warning (requires manual verification)
                return (True, None, "UNVERIFIED (ALLOWED) - earnings date not found, verify manually")
            else:
                # CONSERVATIVE MODE (DEFAULT): Reject for safety
                return (False, None, "REJECTED - earnings date not found (fail-safe mode, use --allow-unverified to override)")
        
        # Calculate the danger window
        today = datetime.now()
        danger_end = expiration_date + timedelta(days=buffer_days)
        
        # Remove timezone info for comparison if present
        if earnings_date.tzinfo is not None:
            earnings_date = earnings_date.replace(tzinfo=None)
        if expiration_date.tzinfo is not None:
            expiration_date = expiration_date.replace(tzinfo=None)
        
        # Check if earnings falls within danger window
        if today <= earnings_date <= danger_end:
            days_to_earnings = (earnings_date - today).days
            return (
                False, 
                earnings_date, 
                f"REJECT - earnings on {earnings_date.strftime('%Y-%m-%d')} ({days_to_earnings} days away)"
            )
        
        # Earnings is outside danger window
        if earnings_date < today:
            return (True, earnings_date, f"SAFE - earnings already passed ({earnings_date.strftime('%Y-%m-%d')})")
        else:
            days_after_expiry = (earnings_date - danger_end).days
            return (
                True, 
                earnings_date, 
                f"SAFE - earnings on {earnings_date.strftime('%Y-%m-%d')} ({days_after_expiry} days after buffer)"
            )
    
    def batch_check_earnings(
        self,
        tickers: list,
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = False
    ) -> Dict[str, Tuple[bool, Optional[datetime], str]]:
        """
        Check earnings safety for multiple tickers.

        Args:
            tickers: List of stock tickers
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration
            allow_unverified: If False (default), reject unverified stocks

        Returns:
            Dict mapping ticker to (is_safe, earnings_date, reason)
        """
        results = {}

        for ticker in tickers:
            results[ticker] = self.check_earnings_safe(ticker, expiration_date, buffer_days, allow_unverified)

        return results
    
    def get_safe_tickers(
        self,
        tickers: list,
        expiration_date: datetime,
        buffer_days: int = 7,
        allow_unverified: bool = False
    ) -> list:
        """
        Filter tickers to only those safe from earnings.

        CONSERVATIVE DEFAULT (UPDATED):
        - By default (allow_unverified=False), rejects stocks with missing earnings data
        - Set allow_unverified=True to include unverified stocks (manual verification required)

        Args:
            tickers: List of stock tickers
            expiration_date: Option expiration date
            buffer_days: Additional buffer days after expiration
            allow_unverified: If False (default), exclude tickers where earnings couldn't be verified

        Returns:
            List of safe tickers
        """
        results = self.batch_check_earnings(tickers, expiration_date, buffer_days, allow_unverified)

        safe_tickers = []
        for ticker, (is_safe, _, reason) in results.items():
            if is_safe:
                safe_tickers.append(ticker)

        return safe_tickers
    
    def clear_cache(self):
        """Clear the earnings cache"""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("Earnings cache cleared")


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    # Test the earnings checker
    checker = EarningsChecker()
    
    test_tickers = ["AAPL", "INTC", "AMD", "TSLA", "GME"]
    
    # Test expiration date (45 days from now)
    exp_date = datetime.now() + timedelta(days=45)
    
    print(f"Checking earnings safety for expiration: {exp_date.strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    for ticker in test_tickers:
        is_safe, earnings_date, reason = checker.check_earnings_safe(ticker, exp_date, buffer_days=7)
        status = "✅" if is_safe else "❌"
        print(f"{status} {ticker}: {reason}")
    
    print("\n" + "=" * 60)
    print("Safe tickers:", checker.get_safe_tickers(test_tickers, exp_date, buffer_days=7))
