"""
Hybrid Data Fetcher for Options Scanner

HYBRID APPROACH (saves $60/month):
- Stock quotes: yfinance (FREE, no subscription needed)
- Options chains: MooMoo API (requires OPRA subscription, FREE with $3k+ assets)
- Historical data: yfinance (FREE)

This approach avoids the $60/month Nasdaq Basic OpenAPI fee while still
getting real-time options data from MooMoo.
"""

from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
import time
import pandas as pd

# yfinance for stock quotes (free)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not installed. Run: pip install yfinance")

# MooMoo imports - for options data only
try:
    from moomoo import (
        OpenQuoteContext, 
        RET_OK, 
        OptionType, 
        OptionDataFilter,
        OptionCondType,
        KLType,
        AuType
    )
    MOOMOO_AVAILABLE = True
except ImportError:
    MOOMOO_AVAILABLE = False
    print("Warning: moomoo-api not installed. Run: pip install moomoo-api")

from config import MOOMOO_HOST, MOOMOO_PORT, API_DELAY_SECONDS
from universe import format_moomoo_symbol, strip_moomoo_prefix


class HybridDataFetcher:
    """
    Hybrid data fetcher using yfinance for stocks and MooMoo for options.
    
    This saves $60/month by avoiding the Nasdaq Basic OpenAPI subscription
    while still getting real-time options data from MooMoo.
    
    Data Sources:
    - Stock quotes: yfinance (free, ~15 min delayed during market hours)
    - Stock historical: yfinance (free)
    - Options chains: MooMoo API (real-time, requires OPRA - free with $3k+ assets)
    - Options expirations: MooMoo API
    """
    
    def __init__(self, host: str = MOOMOO_HOST, port: int = MOOMOO_PORT):
        """
        Initialize Hybrid data fetcher.
        
        Args:
            host: OpenD host address (for MooMoo options data)
            port: OpenD port number
        """
        self.host = host
        self.port = port
        self.quote_ctx = None
        self.moomoo_connected = False
        self.last_request_time = 0
        
        if not YFINANCE_AVAILABLE:
            raise RuntimeError("yfinance package not installed - required for stock quotes")
        
        if not MOOMOO_AVAILABLE:
            print("Warning: moomoo-api not available - options data will not work")
    
    @property
    def connected(self) -> bool:
        """Backward compatibility property"""
        return self.moomoo_connected
    
    def connect(self) -> bool:
        """
        Establish connection to MooMoo OpenD for options data.
        Stock quotes use yfinance and don't need connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not MOOMOO_AVAILABLE:
            print("⚠️  MooMoo API not available - options features disabled")
            return False
            
        try:
            self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            
            # Test connection
            ret, data = self.quote_ctx.get_global_state()
            
            if ret == RET_OK:
                self.moomoo_connected = True
                print(f"✅ Connected to MooMoo OpenD at {self.host}:{self.port}")
                print(f"   Stock quotes: yfinance (FREE)")
                print(f"   Options data: MooMoo API (OPRA)")
                return True
            else:
                print(f"❌ MooMoo connection test failed: {data}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to connect to MooMoo OpenD: {e}")
            print("   Options features will not work without OpenD running")
            return False
    
    def disconnect(self):
        """Close connection to MooMoo OpenD"""
        if self.quote_ctx:
            self.quote_ctx.close()
            self.moomoo_connected = False
            print("Disconnected from MooMoo OpenD")
    
    def _rate_limit(self):
        """Apply rate limiting between MooMoo API calls"""
        elapsed = time.time() - self.last_request_time
        if elapsed < API_DELAY_SECONDS:
            time.sleep(API_DELAY_SECONDS - elapsed)
        self.last_request_time = time.time()
    
    def _ensure_moomoo_connected(self):
        """Ensure MooMoo connection is active for options data"""
        if not self.moomoo_connected:
            if not self.connect():
                raise RuntimeError("MooMoo OpenD not connected - required for options data")
    
    # =========================================================================
    # STOCK QUOTES - Using yfinance (FREE)
    # =========================================================================
    
    def get_stock_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get current quote for a stock using yfinance (FREE).
        
        Note: During market hours, yfinance data may be ~15 min delayed.
        This is fine for screening purposes.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            
        Returns:
            Dict with quote data or None if failed
        """
        # Strip MooMoo prefix if present
        ticker = strip_moomoo_prefix(ticker)
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info
            
            # Get current price - try multiple attributes
            price = None
            if hasattr(info, 'last_price') and info.last_price:
                price = float(info.last_price)
            elif hasattr(info, 'previous_close') and info.previous_close:
                price = float(info.previous_close)
            
            if price is None:
                # Fallback to history
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
            
            if price is None:
                print(f"Warning: Could not get price for {ticker}")
                return None
            
            return {
                "ticker": ticker,
                "price": price,
                "bid": price * 0.999,  # Approximate - yfinance doesn't always have bid/ask
                "ask": price * 1.001,
                "volume": int(info.last_volume) if hasattr(info, 'last_volume') and info.last_volume else 0,
                "market_cap": float(info.market_cap) if hasattr(info, 'market_cap') and info.market_cap else 0,
                "source": "yfinance"
            }
            
        except Exception as e:
            print(f"Warning: yfinance error for {ticker}: {e}")
            return None
    
    def get_batch_quotes(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Get quotes for multiple stocks using yfinance (FREE).
        
        Args:
            tickers: List of stock tickers
            
        Returns:
            Dict mapping ticker to quote data
        """
        results = {}
        
        # Strip MooMoo prefixes
        clean_tickers = [strip_moomoo_prefix(t) for t in tickers]
        
        print(f"   Fetching {len(clean_tickers)} stock quotes via yfinance (FREE)...")
        
        # yfinance can batch download
        try:
            # Download all at once for efficiency
            data = yf.download(
                clean_tickers, 
                period="1d", 
                progress=False,
                threads=True
            )
            
            if data.empty:
                print("   Warning: yfinance returned no data, trying individually...")
                for ticker in clean_tickers:
                    quote = self.get_stock_quote(ticker)
                    if quote:
                        results[ticker] = quote
            else:
                # Process batch results
                for ticker in clean_tickers:
                    try:
                        if len(clean_tickers) == 1:
                            # Single ticker - data structure is different
                            price = float(data['Close'].iloc[-1])
                            volume = int(data['Volume'].iloc[-1]) if 'Volume' in data else 0
                        else:
                            # Multiple tickers
                            if ticker in data['Close'].columns:
                                price = float(data['Close'][ticker].iloc[-1])
                                volume = int(data['Volume'][ticker].iloc[-1]) if 'Volume' in data else 0
                            else:
                                continue
                        
                        if pd.notna(price):
                            results[ticker] = {
                                "ticker": ticker,
                                "price": price,
                                "bid": price * 0.999,
                                "ask": price * 1.001,
                                "volume": volume,
                                "source": "yfinance"
                            }
                    except Exception as e:
                        print(f"   Warning: Error processing {ticker}: {e}")
                        
        except Exception as e:
            print(f"   Warning: Batch download failed: {e}, trying individually...")
            for ticker in clean_tickers:
                quote = self.get_stock_quote(ticker)
                if quote:
                    results[ticker] = quote
        
        print(f"   Retrieved {len(results)}/{len(clean_tickers)} quotes")
        return results
    
    # =========================================================================
    # OPTIONS DATA - Using MooMoo API (requires OPRA subscription)
    # =========================================================================
    
    def get_option_expirations(self, ticker: str) -> Optional[List[str]]:
        """
        Get available option expiration dates for a stock.
        Uses MooMoo API (requires OPRA subscription).
        
        Args:
            ticker: Stock ticker
            
        Returns:
            List of expiration dates as strings (YYYY-MM-DD) or None
        """
        self._ensure_moomoo_connected()
        self._rate_limit()
        
        symbol = format_moomoo_symbol(ticker)
        
        try:
            ret, data = self.quote_ctx.get_option_expiration_date(code=symbol)
            
            if ret == RET_OK and not data.empty:
                return data['strike_time'].tolist()
            else:
                print(f"Warning: No expirations for {ticker}: {data}")
                return None
                
        except Exception as e:
            print(f"Error fetching expirations for {ticker}: {e}")
            return None
    
    def get_options_chain(
        self,
        ticker: str,
        expiration: str,
        option_type: str = "PUT",
        delta_min: Optional[float] = None,
        delta_max: Optional[float] = None,
        volume_min: Optional[int] = None,
        oi_min: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get options chain with full Greeks and pricing data.

        This requires TWO API calls:
        1. get_option_chain() - gets static info (codes, strikes, expirations)
        2. get_market_snapshot() - gets dynamic info (delta, bid, ask, volume, IV)

        Args:
            ticker: Stock ticker
            expiration: Expiration date (YYYY-MM-DD)
            option_type: 'PUT', 'CALL', or 'ALL'
            delta_min: Minimum delta filter (for PUTs, use negative values)
            delta_max: Maximum delta filter (for PUTs, use negative values)
            volume_min: Minimum volume filter
            oi_min: Minimum open interest filter

        Returns:
            DataFrame with complete options data or None
        """
        self._ensure_moomoo_connected()
        self._rate_limit()

        symbol = format_moomoo_symbol(ticker)

        # Set option type
        if option_type.upper() == "PUT":
            opt_type = OptionType.PUT
        elif option_type.upper() == "CALL":
            opt_type = OptionType.CALL
        else:
            opt_type = OptionType.ALL

        try:
            # Step 1: Get static option data (codes, strikes, expirations)
            ret, static_data = self.quote_ctx.get_option_chain(
                code=symbol,
                start=expiration,
                end=expiration,
                option_type=opt_type
            )

            if ret != RET_OK or static_data is None or static_data.empty:
                return pd.DataFrame()

            # Step 2: Get market snapshot for dynamic pricing data
            option_codes = static_data['code'].tolist()

            if not option_codes:
                return pd.DataFrame()

            # Rate limit between API calls
            self._rate_limit()

            ret2, snapshot_data = self.quote_ctx.get_market_snapshot(option_codes)

            if ret2 != RET_OK or snapshot_data is None or snapshot_data.empty:
                print(f"Warning: Could not get pricing data for {ticker} options - snapshot failed")
                # Return static data only if snapshot fails
                return static_data

            # Step 3: Merge static and dynamic data
            # Snapshot data uses different column names for options
            column_mapping = {
                'last_price': 'last_price',
                'bid': 'bid_price',
                'ask': 'ask_price',
                'volume': 'volume',
                'open_interest': 'option_open_interest',
                'delta': 'option_delta',
                'gamma': 'option_gamma',
                'theta': 'option_theta',
                'vega': 'option_vega',
                'implied_volatility': 'option_implied_volatility'
            }

            # Create pricing DataFrame with standardized column names
            pricing_data = pd.DataFrame(index=snapshot_data.index)
            pricing_data['code'] = snapshot_data['code']

            for standard_col, api_col in column_mapping.items():
                if api_col in snapshot_data.columns:
                    pricing_data[standard_col] = snapshot_data[api_col]
                else:
                    pricing_data[standard_col] = None

            merged = static_data.merge(
                pricing_data,
                on='code',
                how='left'
            )

            # Step 4: Apply filters on the merged data
            if delta_min is not None and 'delta' in merged.columns:
                merged = merged[merged['delta'] >= delta_min]
            if delta_max is not None and 'delta' in merged.columns:
                merged = merged[merged['delta'] <= delta_max]
            if volume_min is not None and 'volume' in merged.columns:
                merged = merged[merged['volume'] >= volume_min]
            if oi_min is not None and 'open_interest' in merged.columns:
                merged = merged[merged['open_interest'] >= oi_min]

            return merged

        except Exception as e:
            print(f"Error fetching options chain for {ticker} @ {expiration}: {e}")
            return None
    
    # =========================================================================
    # HISTORICAL DATA - Using yfinance (FREE)
    # =========================================================================
    
    def get_historical_data(
        self,
        ticker: str,
        days: int = 252,
        ktype: str = "DAY"
    ) -> Optional[pd.DataFrame]:
        """
        Get historical price data for a stock using yfinance (FREE).
        
        Args:
            ticker: Stock ticker
            days: Number of days of history
            ktype: Candlestick type ('DAY', 'WEEK', 'MONTH') - mapped to yfinance intervals
            
        Returns:
            DataFrame with OHLCV data or None
        """
        ticker = strip_moomoo_prefix(ticker)
        
        # Map ktype to yfinance interval
        interval_map = {
            "DAY": "1d",
            "WEEK": "1wk", 
            "MONTH": "1mo",
        }
        interval = interval_map.get(ktype.upper(), "1d")
        
        # Calculate period
        if days <= 7:
            period = "5d"
        elif days <= 30:
            period = "1mo"
        elif days <= 90:
            period = "3mo"
        elif days <= 180:
            period = "6mo"
        elif days <= 365:
            period = "1y"
        elif days <= 730:
            period = "2y"
        else:
            period = "5y"
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            
            if hist.empty:
                print(f"Warning: No historical data for {ticker}")
                return None
            
            # Rename columns to match expected format
            hist = hist.reset_index()
            hist.columns = [c.lower() for c in hist.columns]
            
            # Rename 'date' to 'time_key' for compatibility
            if 'date' in hist.columns:
                hist = hist.rename(columns={'date': 'time_key'})
            elif 'datetime' in hist.columns:
                hist = hist.rename(columns={'datetime': 'time_key'})
            
            return hist
            
        except Exception as e:
            print(f"Error fetching historical data for {ticker}: {e}")
            return None
    
    def calculate_dte(self, expiration: str) -> int:
        """
        Calculate days to expiration.
        
        Args:
            expiration: Expiration date string (YYYY-MM-DD)
            
        Returns:
            Number of days to expiration
        """
        exp_date = datetime.strptime(expiration, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (exp_date - today).days
    
    def filter_expirations_by_dte(
        self, 
        expirations: List[str], 
        dte_min: int, 
        dte_max: int
    ) -> List[Tuple[str, int]]:
        """
        Filter expiration dates by DTE range.
        
        Args:
            expirations: List of expiration dates
            dte_min: Minimum DTE
            dte_max: Maximum DTE
            
        Returns:
            List of (expiration, dte) tuples within range
        """
        filtered = []
        for exp in expirations:
            dte = self.calculate_dte(exp)
            if dte_min <= dte <= dte_max:
                filtered.append((exp, dte))
        return filtered


# =============================================================================
# MOCK DATA FETCHER (for testing without MooMoo connection)
# =============================================================================

class MockDataFetcher:
    """
    Mock data fetcher for testing scanner logic without MooMoo connection.
    Returns realistic sample data.
    """
    
    def __init__(self):
        self.connected = True
        print("⚠️  Using MockDataFetcher - no real market data")
    
    def connect(self) -> bool:
        return True
    
    def disconnect(self):
        pass
    
    def get_stock_quote(self, ticker: str) -> Dict:
        """Return mock quote data"""
        # Sample prices for common tickers
        mock_prices = {
            "INTC": 22.50, "AMD": 125.00, "PLTR": 45.00, "F": 11.00,
            "TSLA": 250.00, "GME": 25.00, "AMC": 5.50, "MARA": 18.00,
            "NVDA": 480.00, "AAPL": 185.00, "SOFI": 12.00, "HOOD": 22.00,
        }
        price = mock_prices.get(ticker, 50.00)
        
        return {
            "ticker": ticker,
            "price": price,
            "bid": price - 0.02,
            "ask": price + 0.02,
            "volume": 1000000,
        }
    
    def get_batch_quotes(self, tickers: List[str]) -> Dict[str, Dict]:
        return {t: self.get_stock_quote(t) for t in tickers}
    
    def get_option_expirations(self, ticker: str) -> List[str]:
        """Return mock expiration dates"""
        today = datetime.now()
        expirations = []
        for weeks in range(1, 12):
            exp_date = today + timedelta(weeks=weeks)
            # Adjust to Friday
            days_until_friday = (4 - exp_date.weekday()) % 7
            exp_date = exp_date + timedelta(days=days_until_friday)
            expirations.append(exp_date.strftime('%Y-%m-%d'))
        return expirations
    
    def get_options_chain(self, ticker: str, expiration: str, **kwargs) -> pd.DataFrame:
        """Return mock options chain"""
        quote = self.get_stock_quote(ticker)
        price = quote['price']
        
        # Generate strikes around current price
        strikes = [price * (1 - i*0.05) for i in range(-3, 8)]
        
        data = []
        for strike in strikes:
            delta = -0.5 * (1 - (price - strike) / price)  # Simplified delta calc
            delta = max(-0.95, min(-0.05, delta))
            
            data.append({
                'code': f"US.{ticker}XXXXP{int(strike*1000):08d}",
                'strike_price': round(strike, 2),
                'strike_time': expiration,
                'option_type': 'PUT',
                'delta': round(delta, 3),
                'gamma': 0.05,
                'theta': -0.03,
                'vega': 0.15,
                'implied_volatility': 0.35,
                'open_interest': 5000,
                'volume': 1500,
                'bid': round(abs(delta) * 3, 2),
                'ask': round(abs(delta) * 3 + 0.10, 2),
                'last_price': round(abs(delta) * 3 + 0.05, 2),
            })
        
        return pd.DataFrame(data)
    
    def get_historical_data(self, ticker: str, days: int = 252, **kwargs) -> pd.DataFrame:
        """Return mock historical data"""
        import numpy as np
        
        quote = self.get_stock_quote(ticker)
        current_price = quote['price']
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        
        # Generate random walk prices
        returns = np.random.normal(0.0002, 0.02, days)
        prices = current_price * np.exp(np.cumsum(returns[::-1]))[::-1]
        
        data = pd.DataFrame({
            'time_key': dates,
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
            'high': prices * (1 + np.random.uniform(0, 0.02, days)),
            'low': prices * (1 - np.random.uniform(0, 0.02, days)),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, days),
        })
        
        return data
    
    def calculate_dte(self, expiration: str) -> int:
        exp_date = datetime.strptime(expiration, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (exp_date - today).days
    
    def filter_expirations_by_dte(self, expirations: List[str], dte_min: int, dte_max: int) -> List[Tuple[str, int]]:
        filtered = []
        for exp in expirations:
            dte = self.calculate_dte(exp)
            if dte_min <= dte <= dte_max:
                filtered.append((exp, dte))
        return filtered


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_data_fetcher(use_mock: bool = False) -> Any:
    """
    Get appropriate data fetcher based on availability.
    
    Args:
        use_mock: Force use of mock data fetcher
        
    Returns:
        HybridDataFetcher or MockDataFetcher instance
    """
    if use_mock:
        return MockDataFetcher()
    
    if not YFINANCE_AVAILABLE:
        print("Warning: yfinance not available, using mock data")
        return MockDataFetcher()
    
    return HybridDataFetcher()


# Backward compatibility alias
MooMooDataFetcher = HybridDataFetcher


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("HYBRID DATA FETCHER TEST")
    print("Stock quotes: yfinance (FREE)")
    print("Options data: MooMoo API (OPRA)")
    print("="*60 + "\n")
    
    fetcher = get_data_fetcher(use_mock=False)
    
    # Test stock quote (yfinance - no MooMoo needed)
    print("--- Testing Stock Quote (yfinance) ---")
    quote = fetcher.get_stock_quote("AAPL")
    if quote:
        print(f"AAPL: ${quote['price']:.2f} (source: {quote.get('source', 'unknown')})")
    else:
        print("Failed to get AAPL quote")
    
    # Test batch quotes (yfinance)
    print("\n--- Testing Batch Quotes (yfinance) ---")
    quotes = fetcher.get_batch_quotes(["INTC", "AMD", "NVDA"])
    for ticker, q in quotes.items():
        print(f"{ticker}: ${q['price']:.2f}")
    
    # Test historical data (yfinance)
    print("\n--- Testing Historical Data (yfinance) ---")
    hist = fetcher.get_historical_data("INTC", days=30)
    if hist is not None:
        print(f"Got {len(hist)} days of history for INTC")
        print(hist[['time_key', 'close']].tail(3))
    
    # Test MooMoo connection for options
    print("\n--- Testing MooMoo Connection (Options) ---")
    if fetcher.connect():
        # Test expirations
        exps = fetcher.get_option_expirations("INTC")
        if exps:
            print(f"INTC expirations: {exps[:5]}...")
            
            # Test options chain
            chain = fetcher.get_options_chain("INTC", exps[4], option_type="PUT")
            if chain is not None and not chain.empty:
                print(f"Got {len(chain)} PUT options for INTC @ {exps[4]}")
                print(chain[['strike_price', 'delta', 'bid', 'ask']].head())
            else:
                print("No options chain data returned")
        else:
            print("No expirations returned")
        
        fetcher.disconnect()
    else:
        print("Could not connect to MooMoo - options test skipped")
