"""
IV Rank Calculator and Term Structure Analyzer
Calculates IV Rank from historical data and checks term structure (contango/backwardation)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
import pandas as pd
import numpy as np

from config import IV_RANK_CONFIG


class IVAnalyzer:
    """
    Analyzes implied volatility metrics:
    - IV Rank: Where current IV sits relative to 52-week range
    - Term Structure: Contango (favorable) vs Backwardation (unfavorable)
    """

    def __init__(self, data_fetcher, cache_file: str = None, history_file: str = None):
        """
        Initialize IV Analyzer.

        Args:
            data_fetcher: HybridDataFetcher or MockDataFetcher instance
            cache_file: Path to IV cache file (default from IV_RANK_CONFIG)
            history_file: Path to IV history file (default from IV_RANK_CONFIG).
                Pass a temp path in mock/offline runs so the real history is untouched.
        """
        self.data_fetcher = data_fetcher
        self.cache_file = cache_file or IV_RANK_CONFIG.get(
            "iv_cache_file", "./iv_cache.json"
        )
        self.lookback_days = IV_RANK_CONFIG.get("lookback_days", 252)
        self.cache_expiry_days = IV_RANK_CONFIG.get("cache_expiry_days", 7)
        self.cache = self._load_cache()

        # Real IV history (self-consistent series of daily ATM implied vol per ticker),
        # used to compute a statistically valid IV Percentile. See record_iv_observation.
        self.history_file = history_file or IV_RANK_CONFIG.get(
            "iv_history_file", "./iv_history.json"
        )
        self.min_observations = IV_RANK_CONFIG.get("min_observations", 20)
        self.iv_history = self._load_history()

    def _load_cache(self) -> Dict:
        """Load IV cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save IV cache to file"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save IV cache: {e}")

    def _load_history(self) -> Dict[str, List[Dict]]:
        """Load the persisted daily IV-observation history from file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_history(self):
        """Persist the IV-observation history to file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.iv_history, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save IV history: {e}")

    def record_iv_observation(self, ticker: str, current_iv_decimal: float) -> None:
        """
        Append today's ATM implied vol to the ticker's IV history.

        One observation per ticker per calendar day: a same-day re-run overwrites the
        existing entry rather than appending, so multiple scans in one day do not
        oversample and bias the distribution. The series is capped at ``lookback_days``
        most-recent entries to bound file size.

        Args:
            ticker: Stock ticker
            current_iv_decimal: Current ATM implied volatility as a decimal (e.g. 0.34)

        Edge cases:
            - Ignores None / NaN / non-positive IV (corrupt or unavailable data).
        """
        if (
            current_iv_decimal is None
            or pd.isna(current_iv_decimal)
            or current_iv_decimal <= 0
        ):
            return

        today = datetime.now().strftime("%Y-%m-%d")
        series = self.iv_history.get(ticker, [])
        # Drop any existing observation for today (overwrite, don't duplicate)
        series = [obs for obs in series if obs.get("date") != today]
        series.append({"date": today, "iv": float(current_iv_decimal)})
        # Keep only the most recent lookback_days observations
        self.iv_history[ticker] = series[-self.lookback_days :]
        self._save_history()

    def calculate_iv_percentile(
        self, ticker: str, current_iv_decimal: float
    ) -> Optional[float]:
        """
        IV Percentile: fraction of historical IV observations strictly below current IV.

        IV Percentile = 100 * (# observations < current_iv) / (total observations)

        Preferred over min-max IV Rank because it is robust to single outlier spikes
        (one COVID-style vol spike does not pin the range for a year).

        Statistical assumptions:
            - Each stored point is one daily ATM-IV sample (treated as non-overlapping).
            - Only meaningful once >= min_observations samples exist; the caller is
              responsible for the warm-up fallback.

        Args:
            ticker: Stock ticker
            current_iv_decimal: Current ATM implied volatility as a decimal

        Returns:
            IV Percentile in [0, 100], or None if no history exists.
        """
        series = self.iv_history.get(ticker, [])
        if not series:
            return None

        ivs = [obs["iv"] for obs in series if obs.get("iv") is not None]
        if not ivs:
            return None

        below = sum(1 for iv in ivs if iv < current_iv_decimal)
        return round(100.0 * below / len(ivs), 1)

    def _is_cache_valid(self, ticker: str) -> bool:
        """Check if cached IV data is still valid"""
        if ticker not in self.cache:
            return False

        cached_time = datetime.fromisoformat(
            self.cache[ticker].get("cached_at", "2000-01-01")
        )
        expiry_time = cached_time + timedelta(days=self.cache_expiry_days)

        return datetime.now() < expiry_time

    def calculate_historical_volatility(
        self, ticker: str, window: int = 20
    ) -> Optional[float]:
        """
        Calculate historical (realized) volatility from price data.
        Uses close-to-close returns annualized.

        Args:
            ticker: Stock ticker
            window: Rolling window for volatility calculation

        Returns:
            Annualized historical volatility as decimal (e.g., 0.35 = 35%)
        """
        hist_data = self.data_fetcher.get_historical_data(
            ticker, days=self.lookback_days
        )

        if hist_data is None or len(hist_data) < window + 1:
            return None

        # Calculate log returns
        hist_data["returns"] = np.log(hist_data["close"] / hist_data["close"].shift(1))

        # Current rolling volatility (annualized)
        current_vol = hist_data["returns"].tail(window).std() * np.sqrt(252)

        return float(current_vol)

    def get_iv_range(
        self, ticker: str, use_cache: bool = True
    ) -> Optional[Tuple[float, float]]:
        """
        Get 52-week IV high and low for a ticker.

        Note: MooMoo API doesn't provide historical IV directly.
        We approximate using historical volatility as a proxy for IV range.
        This is not perfect but gives a reasonable estimate.

        Args:
            ticker: Stock ticker
            use_cache: Use cached values if available

        Returns:
            Tuple of (iv_low, iv_high) or None
        """
        # Check cache
        if use_cache and self._is_cache_valid(ticker):
            cached = self.cache[ticker]
            return (cached.get("iv_low"), cached.get("iv_high"))

        # Calculate from historical data
        hist_data = self.data_fetcher.get_historical_data(
            ticker, days=self.lookback_days
        )

        if hist_data is None or len(hist_data) < 30:
            return None

        # Calculate rolling historical volatility
        hist_data["returns"] = np.log(hist_data["close"] / hist_data["close"].shift(1))
        hist_data["hv_20"] = hist_data["returns"].rolling(window=20).std() * np.sqrt(
            252
        )

        # Get range
        hv_series = hist_data["hv_20"].dropna()
        if len(hv_series) < 20:
            return None

        iv_low = float(hv_series.min())
        iv_high = float(hv_series.max())

        # Cache the result
        self.cache[ticker] = {
            "iv_low": iv_low,
            "iv_high": iv_high,
            "cached_at": datetime.now().isoformat(),
            "method": "historical_volatility_proxy",
        }
        self._save_cache()

        return (iv_low, iv_high)

    def calculate_iv_rank(self, ticker: str, current_iv: float) -> Optional[float]:
        """
        Calculate IV Rank for a ticker.

        IV Rank = (Current IV - 52-week Low) / (52-week High - 52-week Low) × 100

        Args:
            ticker: Stock ticker
            current_iv: Current implied volatility (decimal)

        Returns:
            IV Rank as percentage (0-100+) or None
        """
        iv_range = self.get_iv_range(ticker)

        if iv_range is None:
            return None

        iv_low, iv_high = iv_range

        if iv_high == iv_low:
            return 50.0  # Default to middle if no range

        iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
        # IV Rank is bounded [0, 100] by definition. The HV proxy can place current IV
        # outside its historical range, so clamp — never emit impossible values (e.g. 195).
        iv_rank = max(0.0, min(100.0, iv_rank))

        return round(iv_rank, 1)

    def get_current_iv_from_options(
        self, ticker: str, expiration: str
    ) -> Optional[float]:
        """
        Get current ATM implied volatility from options chain.

        Args:
            ticker: Stock ticker
            expiration: Option expiration date

        Returns:
            ATM implied volatility or None
        """
        # Get current stock price
        quote = self.data_fetcher.get_stock_quote(ticker)
        if quote is None:
            return None

        current_price = quote["price"]

        # Get options chain without delta filter to find ATM
        chain = self.data_fetcher.get_options_chain(
            ticker=ticker, expiration=expiration, option_type="PUT"
        )

        if chain is None or chain.empty:
            return None

        # Check what IV column exists (MooMoo uses different names)
        iv_column = None
        possible_iv_columns = [
            "implied_volatility",
            "iv",
            "impliedVolatility",
            "option_iv",
            "option_implied_volatility",
        ]
        for col in possible_iv_columns:
            if col in chain.columns:
                iv_column = col
                break

        if iv_column is None:
            # IV not available in options chain - return None
            # This is expected when market is closed or data is limited
            return None

        # Find ATM option (strike closest to current price)
        chain["strike_diff"] = abs(chain["strike_price"] - current_price)
        atm_option = chain.loc[chain["strike_diff"].idxmin()]

        iv_value = atm_option.get(iv_column)
        if iv_value is not None and pd.notna(iv_value):
            return float(iv_value)
        return None

    def analyze_term_structure(
        self, ticker: str, front_expiration: str, back_expiration: str
    ) -> Tuple[str, float, str]:
        """
        Analyze term structure (contango vs backwardation).

        Contango: Back-month IV > Front-month IV (favorable for selling premium)
        Backwardation: Back-month IV < Front-month IV (unfavorable)

        Args:
            ticker: Stock ticker
            front_expiration: Near-term expiration (30-45 DTE)
            back_expiration: Further expiration (60-75 DTE)

        Returns:
            Tuple of (structure_type, iv_difference, recommendation)
            - structure_type: 'CONTANGO', 'BACKWARDATION', or 'NEUTRAL'
            - iv_difference: Back IV - Front IV
            - recommendation: Action recommendation
        """
        front_iv = self.get_current_iv_from_options(ticker, front_expiration)
        back_iv = self.get_current_iv_from_options(ticker, back_expiration)

        if front_iv is None or back_iv is None:
            return ("UNKNOWN", 0.0, "Could not determine term structure")

        # Chain IVs are already percentages (e.g. 35.2), so the difference is
        # already in percentage points — do NOT multiply by 100 (that pinned
        # every live reading to the CONTANGO/BACKWARDATION extremes).
        iv_diff_pct = back_iv - front_iv

        # Classify term structure
        if iv_diff_pct > 2.0:
            structure = "CONTANGO"
            recommendation = "FAVORABLE - Proceed with trade"
        elif iv_diff_pct < -2.0:
            structure = "BACKWARDATION"
            recommendation = "UNFAVORABLE - Wait or reduce size"
        else:
            structure = "NEUTRAL"
            recommendation = "NEUTRAL - Use other factors to decide"

        return (structure, round(iv_diff_pct, 2), recommendation)

    def get_full_iv_analysis(self, ticker: str, target_expiration: str) -> Dict:
        """
        Get comprehensive IV analysis for a ticker.

        Args:
            ticker: Stock ticker
            target_expiration: Target option expiration

        Returns:
            Dict with IV metrics
        """
        result = {
            "ticker": ticker,
            "expiration": target_expiration,
            "current_iv": None,
            "iv_rank": None,
            "iv_method": None,  # "iv_percentile" once warmed up, else "hv_proxy_provisional"
            "iv_52w_low": None,
            "iv_52w_high": None,
            "hv_20": None,
            "iv_hv_spread": None,
            "term_structure": None,
            "term_structure_diff": None,
            "term_structure_recommendation": None,
        }

        # Get current IV from options
        current_iv = self.get_current_iv_from_options(ticker, target_expiration)
        if current_iv:
            # API returns IV as percentage already, so no need to multiply by 100
            result["current_iv"] = round(current_iv, 1)

        # Get IV range
        iv_range = self.get_iv_range(ticker)
        if iv_range:
            result["iv_52w_low"] = round(iv_range[0] * 100, 1)
            result["iv_52w_high"] = round(iv_range[1] * 100, 1)

        # IV richness metric: record today's observation, then compute a true IV
        # Percentile against the self-consistent IV history. Until enough daily samples
        # have accumulated, fall back to the (clearly labeled) realized-vol proxy so the
        # scanner is functional from day one and self-upgrades over time.
        if current_iv:
            # API returns IV as percentage; store/compute in decimal for consistency.
            current_iv_decimal = current_iv / 100.0
            self.record_iv_observation(ticker, current_iv_decimal)

            history_len = len(self.iv_history.get(ticker, []))
            if history_len >= self.min_observations:
                result["iv_rank"] = self.calculate_iv_percentile(
                    ticker, current_iv_decimal
                )
                result["iv_method"] = "iv_percentile"
            else:
                # Not enough IV history yet. The realized-vol (HV) proxy actively MISLEADS
                # on post-earnings names: realized vol stays high after an earnings move
                # while implied vol has crushed, so the proxy reports a high "rank" on a
                # cheap-premium name. We therefore do NOT emit it as a rank - IV is simply
                # UNKNOWN until warm-up completes. Downstream treats provisional as unusable.
                result["iv_rank"] = None
                result["iv_method"] = "hv_proxy_provisional"

        # Get HV for comparison
        hv_20 = self.calculate_historical_volatility(ticker, window=20)
        if hv_20:
            result["hv_20"] = round(hv_20 * 100, 1)

            # IV-HV spread (positive = IV overpriced = good for selling).
            # current_iv is a percentage, hv_20 a decimal — align units first.
            if current_iv:
                result["iv_hv_spread"] = round(current_iv - hv_20 * 100, 1)

        # Term structure analysis (need to find back-month expiration)
        expirations = self.data_fetcher.get_option_expirations(ticker)
        if expirations:
            # Find expiration ~30 days after target
            target_date = datetime.strptime(target_expiration, "%Y-%m-%d")
            back_month_target = target_date + timedelta(days=30)

            back_expiration = None
            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                if exp_date >= back_month_target:
                    back_expiration = exp
                    break

            if back_expiration:
                structure, diff, rec = self.analyze_term_structure(
                    ticker, target_expiration, back_expiration
                )
                result["term_structure"] = structure
                result["term_structure_diff"] = diff
                result["term_structure_recommendation"] = rec

        return result

    def passes_iv_filter(
        self, ticker: str, expiration: str, min_iv_rank: float
    ) -> Tuple[bool, str]:
        """
        Check if ticker passes IV Rank filter.

        Args:
            ticker: Stock ticker
            expiration: Option expiration
            min_iv_rank: Minimum required IV Rank

        Returns:
            Tuple of (passes, reason)
        """
        analysis = self.get_full_iv_analysis(ticker, expiration)

        iv_rank = analysis.get("iv_rank")

        if iv_rank is None:
            return (True, "IV Rank unavailable - manual check required")

        if iv_rank >= min_iv_rank:
            return (True, f"IV Rank {iv_rank:.1f}% >= {min_iv_rank}% threshold")
        else:
            return (False, f"IV Rank {iv_rank:.1f}% < {min_iv_rank}% threshold")

    def clear_cache(self):
        """Clear the IV cache"""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("IV cache cleared")


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    from data_fetcher import get_data_fetcher

    # Use mock data for testing
    fetcher = get_data_fetcher(use_mock=True)
    analyzer = IVAnalyzer(fetcher)

    print("\n=== Testing IV Analyzer ===\n")

    # Test IV analysis
    expirations = fetcher.get_option_expirations("INTC")
    if expirations:
        exp = expirations[4]  # ~30-35 DTE

        analysis = analyzer.get_full_iv_analysis("INTC", exp)

        print(f"Ticker: {analysis['ticker']}")
        print(f"Expiration: {analysis['expiration']}")
        print(f"Current IV: {analysis['current_iv']}%")
        print(f"IV Rank: {analysis['iv_rank']}%")
        print(
            f"52-week IV Range: {analysis['iv_52w_low']}% - {analysis['iv_52w_high']}%"
        )
        print(f"HV(20): {analysis['hv_20']}%")
        print(f"IV-HV Spread: {analysis['iv_hv_spread']}%")
        print(f"Term Structure: {analysis['term_structure']}")
        print(f"Term Structure Diff: {analysis['term_structure_diff']}%")
        print(f"Recommendation: {analysis['term_structure_recommendation']}")

        # Test filter
        print("\n--- IV Filter Test ---")
        passes, reason = analyzer.passes_iv_filter("INTC", exp, min_iv_rank=30)
        print(f"Passes 30% IV Rank filter: {passes}")
        print(f"Reason: {reason}")
