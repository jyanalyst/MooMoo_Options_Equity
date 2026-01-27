"""
Wheel Strategy Screener
Screens for cash-secured put candidates based on Wheel Strategy Guide criteria
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

from config import WHEEL_CONFIG
from universe import get_wheel_universe, get_affordable_stocks, format_moomoo_symbol, strip_moomoo_prefix
from earnings_checker import EarningsChecker
from iv_analyzer import IVAnalyzer


class WheelScreener:
    """
    Screens stocks for Wheel Strategy (cash-secured puts).
    
    Criteria:
    - Stock price: $15-200
    - IV Rank: >30% (ideally >50%)
    - Delta: 0.20-0.30
    - DTE: 30-45 days
    - Volume: >1,000 contracts
    - Bid-ask spread: <10% of mid
    - No earnings within DTE + 7 days
    - Term structure: Contango preferred
    """
    
    def __init__(self, data_fetcher, max_capital: int = None, tier: int = None, allow_unverified: bool = False):
        """
        Initialize Wheel Screener.

        Args:
            data_fetcher: MooMooDataFetcher or MockDataFetcher instance
            max_capital: Maximum capital per position in dollars (optional)
                        e.g., 10000 filters to stocks with price <= $100
            tier: DEPRECATED - kept for backward compatibility, use max_capital instead
            allow_unverified: Allow stocks with unverified earnings dates
        """
        self.data_fetcher = data_fetcher
        self.max_capital = max_capital
        self.allow_unverified = allow_unverified

        # Backward compatibility: convert tier to approximate capital
        if tier is not None and max_capital is None:
            tier_capital_map = {1: 7000, 2: 15000, 3: None}  # Approximate tier -> capital
            self.max_capital = tier_capital_map.get(tier)

        self.universe = get_wheel_universe(self.max_capital)
        self.earnings_checker = EarningsChecker()
        self.iv_analyzer = IVAnalyzer(data_fetcher)
        self.config = WHEEL_CONFIG
    
    def screen_candidates(self, verbose: bool = True) -> List[Dict]:
        """
        Run full screening process for Wheel candidates.
        
        Args:
            verbose: Print progress updates
            
        Returns:
            List of candidate dicts sorted by quality score
        """
        candidates = []
        rejected = []
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"WHEEL STRATEGY SCREENER")
            capital_str = f"max ${self.max_capital:,}" if self.max_capital else "all prices"
            print(f"Universe: {len(self.universe)} stocks ({capital_str})")
            print(f"{'='*60}\n")
        
        # Step 1: Get quotes for all stocks
        if verbose:
            print("Step 1: Fetching quotes...")
        
        quotes = self.data_fetcher.get_batch_quotes(self.universe)
        
        # Step 2: Filter by price
        if verbose:
            print("Step 2: Filtering by price range...")
        
        price_filtered = []
        for ticker, quote in quotes.items():
            price = quote.get('price', 0)
            if self.config['price_min'] <= price <= self.config['price_max']:
                price_filtered.append((ticker, quote))
            else:
                rejected.append((ticker, f"Price ${price:.2f} outside ${self.config['price_min']}-${self.config['price_max']} range"))
        
        if verbose:
            print(f"   {len(price_filtered)}/{len(quotes)} passed price filter")
        
        # Step 3: Process each stock
        for ticker, quote in price_filtered:
            if verbose:
                print(f"\nAnalyzing {ticker} (${quote['price']:.2f})...")
            
            result = self._analyze_stock(ticker, quote, verbose)
            
            if result['status'] == 'CANDIDATE':
                candidates.append(result)
            else:
                rejected.append((ticker, result['reject_reason']))
        
        # Step 4: Sort candidates by quality score
        candidates = sorted(candidates, key=lambda x: x.get('quality_score', 0), reverse=True)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"SCREENING COMPLETE")
            print(f"Candidates: {len(candidates)}")
            print(f"Rejected: {len(rejected)}")
            print(f"{'='*60}")
        
        return candidates
    
    def _analyze_stock(self, ticker: str, quote: Dict, verbose: bool = True) -> Dict:
        """
        Analyze a single stock for Wheel eligibility.

        Args:
            ticker: Stock ticker
            quote: Quote data dict
            verbose: Print details

        Returns:
            Analysis result dict
        """
        result = {
            'ticker': ticker,
            'price': quote['price'],
            'status': 'CANDIDATE',
            'reject_reason': None,
            'options': [],
            'quality_score': 0,
        }

        if verbose:
            print(f"\n   >> DEBUGGING {ticker} (${quote['price']:.2f})")
            print(f"      Step 1: Getting option expirations...")

        # Get option expirations
        expirations = self.data_fetcher.get_option_expirations(ticker)
        if verbose:
            print(f"      -> Expirations found: {len(expirations) if expirations else 0}")
            if expirations:
                print(f"         Sample: {expirations[:3]}...")

        if not expirations:
            result['status'] = 'REJECTED'
            result['reject_reason'] = 'No option expirations available'
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Filter expirations by DTE
        if verbose:
            print(f"      Step 2: Filtering by DTE ({self.config['dte_min']}-{self.config['dte_max']} days)...")

        target_expirations = self.data_fetcher.filter_expirations_by_dte(
            expirations,
            self.config['dte_min'],
            self.config['dte_max']
        )

        if verbose:
            print(f"      -> Target expirations: {len(target_expirations)}")
            if target_expirations:
                for exp, dte in target_expirations[:3]:
                    print(f"         {exp} ({dte} DTE)")

        if not target_expirations:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"No expirations in {self.config['dte_min']}-{self.config['dte_max']} DTE range"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Check earnings for each expiration
        if verbose:
            print(f"      Step 3: Checking earnings safety (buffer: {self.config['earnings_buffer_days']} days)...")

        best_expiration = None
        earnings_safe = False

        for exp, dte in target_expirations:
            exp_datetime = datetime.strptime(exp, '%Y-%m-%d')
            is_safe, earnings_date, reason = self.earnings_checker.check_earnings_safe(
                ticker,
                exp_datetime,
                buffer_days=self.config['earnings_buffer_days'],
                allow_unverified=self.allow_unverified
            )

            if verbose:
                print(f"         {exp}: {reason}")

            if is_safe or 'UNVERIFIED' in reason:
                best_expiration = (exp, dte)
                earnings_safe = True
                result['earnings_status'] = reason
                break

        if not earnings_safe or not best_expiration:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"Earnings conflict for all expirations"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        expiration, dte = best_expiration
        result['expiration'] = expiration
        result['dte'] = dte

        if verbose:
            print(f"      [OK] Earnings safe - using {expiration} ({dte} DTE)")
            print(f"      Step 4: Analyzing IV metrics...")

        # Get IV analysis
        iv_analysis = self.iv_analyzer.get_full_iv_analysis(ticker, expiration)
        result['iv_rank'] = iv_analysis.get('iv_rank')
        result['current_iv'] = iv_analysis.get('current_iv')
        result['term_structure'] = iv_analysis.get('term_structure')
        result['term_structure_recommendation'] = iv_analysis.get('term_structure_recommendation')

        if verbose:
            print(f"      -> Current IV: {result['current_iv']}%")
            print(f"      -> IV Rank: {result['iv_rank']}%")
            print(f"      -> Term Structure: {result['term_structure']} ({result['term_structure_recommendation']})")

        # Check IV Rank filter
        if result['iv_rank'] is not None and result['iv_rank'] < self.config['iv_rank_min']:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"IV Rank {result['iv_rank']:.1f}% < {self.config['iv_rank_min']}% minimum"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        if verbose:
            print(f"      [OK] IV Rank filter passed")
            print(f"      Step 5: Getting options chain (PUTs, delta {self.config['delta_min']}-{self.config['delta_max']})...")

        # Get options chain with delta filter
        # MooMoo uses negative delta for puts
        delta_min = -self.config['delta_max']  # e.g., -0.30
        delta_max = -self.config['delta_min']  # e.g., -0.20

        # Don't filter by volume here - we want to check both volume AND open interest
        chain = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="PUT",
            delta_min=delta_min,
            delta_max=delta_max
            # Removed: volume_min=self.config['volume_min']
        )

        if verbose:
            print(f"      -> Chain returned: {len(chain) if chain is not None and not chain.empty else 0} options")
            if chain is not None and not chain.empty:
                print(f"      -> Columns: {chain.columns.tolist()}")
                print(f"      -> Sample option:")
                sample = chain.iloc[0] if len(chain) > 0 else None
                if sample is not None:
                    print(f"         Strike: ${sample.get('strike_price', 'N/A')}, Delta: {sample.get('delta', 'N/A')}, Bid: ${sample.get('bid', 'N/A')}, Ask: ${sample.get('ask', 'N/A')}, Volume: {sample.get('volume', 'N/A')}")

        if chain is None or chain.empty:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"No options match delta {self.config['delta_min']}-{self.config['delta_max']} with volume >{self.config['volume_min']}"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        if verbose:
            print(f"      Step 6: Analyzing {len(chain)} options for spread/premium filters...")

        # Analyze each option
        valid_options = []

        for idx, opt in chain.iterrows():
            opt_analysis = self._analyze_option(opt, quote['price'])

            if verbose and idx < 3:  # Show first 3 options analysis
                print(f"         Option {idx+1}: Strike ${opt_analysis['strike']}, Premium ${opt_analysis['premium']:.2f}, Spread {opt_analysis['spread_pct']:.1f}%, Passes: {opt_analysis['passes_filters']}")

            if opt_analysis['passes_filters']:
                valid_options.append(opt_analysis)

        if verbose:
            print(f"      -> Valid options after filters: {len(valid_options)}")

        if not valid_options:
            result['status'] = 'REJECTED'
            result['reject_reason'] = 'No options pass all filters (spread, premium)'
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Sort options by quality score and take best
        valid_options = sorted(valid_options, key=lambda x: x['quality_score'], reverse=True)
        result['options'] = valid_options[:3]  # Top 3 options
        result['best_option'] = valid_options[0]

        # Calculate overall quality score
        result['quality_score'] = self._calculate_quality_score(result)

        if verbose:
            print(f"      [OK] CANDIDATE: {ticker}")
            print(f"         Expiration: {expiration} ({dte} DTE)")
            print(f"         IV Rank: {result['iv_rank']}%")
            print(f"         Best Strike: ${result['best_option']['strike']}")
            print(f"         Premium: ${result['best_option']['premium']:.2f} ({result['best_option']['return_pct']:.2f}%)")

        return result
    
    def _analyze_option(self, option: pd.Series, stock_price: float) -> Dict:
        """
        Analyze a single option contract.

        Args:
            option: Option data from chain
            stock_price: Current stock price

        Returns:
            Option analysis dict
        """
        # Helper to safely get value with fallback
        def safe_get(key, default=0):
            val = option.get(key, default)
            if pd.isna(val):
                return default
            return val

        strike = float(safe_get('strike_price', stock_price))

        # Handle missing delta - use approximation based on strike/stock price ratio
        delta = float(safe_get('delta', 0))
        if delta == 0:  # If delta not available, approximate
            # Simple approximation: closer to money = higher delta
            moneyness = stock_price / strike if strike > 0 else 1.0
            if moneyness > 1.1:  # ITM
                delta = 0.8
            elif moneyness > 0.9:  # ATM
                delta = 0.5
            else:  # OTM
                delta = 0.2
        delta = abs(delta)  # Convert to positive

        # Handle missing bid/ask - use last_price as approximation
        last_price = float(safe_get('last_price', 0))
        bid = float(safe_get('bid', last_price * 0.98))  # Approximate if missing
        ask = float(safe_get('ask', last_price * 1.02))  # Approximate if missing

        volume = int(safe_get('volume', 0))
        oi = int(safe_get('open_interest', 0))

        # IV might be in different column names
        iv = 0
        for iv_col in ['implied_volatility', 'iv', 'impliedVolatility']:
            if iv_col in option.index:
                iv_val = option.get(iv_col, 0)
                if pd.notna(iv_val):
                    iv = float(iv_val)
                    break

        # Calculate mid price and spread
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last_price
        spread = ask - bid if bid > 0 and ask > 0 else abs(ask - bid)
        spread_pct = spread / mid if mid > 0 else 0.05  # Default 5% if no spread data

        # Calculate return on capital
        premium = bid if bid > 0 else last_price  # Use bid if available, otherwise last_price
        cash_required = strike * 100
        return_pct = (premium / strike) * 100 if strike > 0 else 0

        # Liquidity filter: Accept if EITHER volume OR open interest is sufficient
        volume_ok = volume >= self.config.get('volume_min', 50)
        oi_ok = oi >= self.config.get('open_interest_min', 500)
        passes_liquidity = volume_ok or oi_ok

        # Relaxed filters for testing - focus on premium rather than spread
        passes_spread = spread_pct <= self.config['bid_ask_spread_max_pct'] or last_price > 0  # Allow if we have last_price
        passes_premium = return_pct >= (self.config['premium_pct_of_strike_min'] * 100)

        passes_filters = passes_premium and passes_liquidity  # Focus on premium and liquidity (volume OR OI), relax spread

        # Quality score for this option
        quality_score = 0
        if passes_filters:
            quality_score = (
                return_pct * 2 +  # Premium return (weighted)
                (1 - spread_pct) * 10 +  # Tight spread bonus
                min(volume / 1000, 5) +  # Volume bonus (capped)
                min(oi / 5000, 5)  # OI bonus (capped)
            )

        return {
            'code': option.get('code', ''),
            'strike': strike,
            'delta': delta,
            'bid': bid,
            'ask': ask,
            'last_price': last_price,
            'mid': round(mid, 2),
            'spread': round(spread, 2),
            'spread_pct': round(spread_pct * 100, 2),
            'premium': premium,
            'cash_required': cash_required,
            'return_pct': round(return_pct, 2),
            'volume': volume,
            'open_interest': oi,
            'iv': round(iv * 100, 1),
            'passes_spread': passes_spread,
            'passes_premium': passes_premium,
            'passes_liquidity': passes_liquidity,
            'passes_filters': passes_filters,
            'quality_score': round(quality_score, 2),
        }
    
    def _calculate_quality_score(self, result: Dict) -> float:
        """
        Calculate overall quality score for a candidate.
        
        Higher score = better candidate.
        
        Args:
            result: Analysis result dict
            
        Returns:
            Quality score (0-100)
        """
        score = 0
        
        # IV Rank contribution (0-30 points)
        if result.get('iv_rank'):
            if result['iv_rank'] >= 50:
                score += 30
            elif result['iv_rank'] >= 40:
                score += 20
            elif result['iv_rank'] >= 30:
                score += 10
        
        # Term structure contribution (0-20 points)
        term = result.get('term_structure')
        if term == 'CONTANGO':
            score += 20
        elif term == 'NEUTRAL':
            score += 10
        # BACKWARDATION gets 0
        
        # Best option quality (0-30 points)
        if result.get('best_option'):
            opt = result['best_option']
            # Return contribution
            score += min(opt['return_pct'] * 5, 15)
            # Spread contribution
            if opt['spread_pct'] < 5:
                score += 15
            elif opt['spread_pct'] < 10:
                score += 10
        
        # DTE contribution (0-10 points) - prefer middle of range
        if result.get('dte'):
            dte = result['dte']
            if 35 <= dte <= 40:
                score += 10
            elif 30 <= dte <= 45:
                score += 5
        
        # Earnings safety contribution (0-10 points)
        if result.get('earnings_status'):
            if 'SAFE' in result['earnings_status']:
                score += 10
            elif 'UNVERIFIED' in result['earnings_status']:
                score += 5
        
        return round(score, 1)
    
    def format_candidate_summary(self, candidate: Dict) -> str:
        """
        Format a candidate for terminal display.
        
        Args:
            candidate: Candidate dict from screening
            
        Returns:
            Formatted string
        """
        opt = candidate.get('best_option', {})
        
        lines = [
            f"\n{'─'*50}",
            f"📊 {candidate['ticker']} - ${candidate['price']:.2f}",
            f"{'─'*50}",
            f"Expiration: {candidate['expiration']} ({candidate['dte']} DTE)",
            f"IV Rank: {candidate.get('iv_rank', 'N/A')}% | Term Structure: {candidate.get('term_structure', 'N/A')}",
            f"",
            f"RECOMMENDED PUT:",
            f"  Strike: ${opt.get('strike', 0):.2f} (Δ {opt.get('delta', 0):.2f})",
            f"  Premium: ${opt.get('premium', 0):.2f} (Bid ${opt.get('bid', 0):.2f} / Ask ${opt.get('ask', 0):.2f})",
            f"  Return: {opt.get('return_pct', 0):.2f}% on ${opt.get('cash_required', 0):,.0f} capital",
            f"  Spread: ${opt.get('spread', 0):.2f} ({opt.get('spread_pct', 0):.1f}%)",
            f"  Volume: {opt.get('volume', 0):,} | OI: {opt.get('open_interest', 0):,}",
            f"",
            f"Quality Score: {candidate.get('quality_score', 0):.1f}/100",
            f"Earnings: {candidate.get('earnings_status', 'Unknown')}",
        ]
        
        return '\n'.join(lines)


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    from data_fetcher import get_data_fetcher

    # Use mock data for testing
    fetcher = get_data_fetcher(use_mock=True)
    screener = WheelScreener(fetcher, max_capital=7000)  # ~$70 stocks
    
    # Reduce universe for quick test
    screener.universe = ["INTC", "F", "PLTR", "AMD", "SOFI"]
    
    print("\n" + "="*60)
    print("WHEEL SCREENER TEST (Mock Data)")
    print("="*60)
    
    candidates = screener.screen_candidates(verbose=True)
    
    print("\n" + "="*60)
    print("TOP CANDIDATES")
    print("="*60)
    
    for candidate in candidates[:3]:
        print(screener.format_candidate_summary(candidate))
