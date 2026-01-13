"""
Volatility Harvesting Screener
Screens for iron condor candidates based on Volatility Harvesting Strategy criteria
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

from config import VOL_HARVEST_CONFIG
from universe import get_vol_harvest_universe, format_moomoo_symbol, strip_moomoo_prefix
from earnings_checker import EarningsChecker
from iv_analyzer import IVAnalyzer


class VolHarvestScreener:
    """
    Screens stocks for Volatility Harvesting Strategy (iron condors).
    
    Criteria:
    - Stock price: $5-50
    - IV Rank: >80% (ideally >100%)
    - Short strike delta: 0.15-0.20
    - DTE: 21-35 days
    - Volume: >500 contracts
    - Premium: >33% of wing width
    - No earnings within DTE
    - Post-squeeze preferred (not during active squeeze)
    """
    
    def __init__(self, data_fetcher):
        """
        Initialize Volatility Harvesting Screener.
        
        Args:
            data_fetcher: MooMooDataFetcher or MockDataFetcher instance
        """
        self.data_fetcher = data_fetcher
        self.universe = get_vol_harvest_universe()
        self.earnings_checker = EarningsChecker()
        self.iv_analyzer = IVAnalyzer(data_fetcher)
        self.config = VOL_HARVEST_CONFIG
    
    def screen_candidates(self, verbose: bool = True) -> List[Dict]:
        """
        Run full screening process for Vol Harvest candidates.
        
        Args:
            verbose: Print progress updates
            
        Returns:
            List of candidate dicts sorted by quality score
        """
        candidates = []
        rejected = []
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"VOLATILITY HARVESTING SCREENER (Iron Condors)")
            print(f"Universe: {len(self.universe)} high-IV stocks")
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
        Analyze a single stock for Vol Harvest eligibility.
        
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
            'iron_condors': [],
            'quality_score': 0,
        }
        
        # Get option expirations
        expirations = self.data_fetcher.get_option_expirations(ticker)
        if not expirations:
            result['status'] = 'REJECTED'
            result['reject_reason'] = 'No option expirations available'
            return result
        
        # Filter expirations by DTE
        target_expirations = self.data_fetcher.filter_expirations_by_dte(
            expirations,
            self.config['dte_min'],
            self.config['dte_max']
        )
        
        if not target_expirations:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"No expirations in {self.config['dte_min']}-{self.config['dte_max']} DTE range"
            return result
        
        # Check earnings for each expiration (no buffer for vol harvest)
        best_expiration = None
        
        for exp, dte in target_expirations:
            exp_datetime = datetime.strptime(exp, '%Y-%m-%d')
            is_safe, earnings_date, reason = self.earnings_checker.check_earnings_safe(
                ticker, 
                exp_datetime, 
                buffer_days=self.config['earnings_buffer_days']
            )
            
            if is_safe or 'UNVERIFIED' in reason:
                best_expiration = (exp, dte)
                result['earnings_status'] = reason
                break
        
        if not best_expiration:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"Earnings conflict for all expirations"
            return result
        
        expiration, dte = best_expiration
        result['expiration'] = expiration
        result['dte'] = dte
        
        # Get IV analysis
        iv_analysis = self.iv_analyzer.get_full_iv_analysis(ticker, expiration)
        result['iv_rank'] = iv_analysis.get('iv_rank')
        result['current_iv'] = iv_analysis.get('current_iv')
        
        # Check IV Rank filter (CRITICAL for vol harvest - must be high)
        if result['iv_rank'] is not None and result['iv_rank'] < self.config['iv_rank_min']:
            result['status'] = 'REJECTED'
            result['reject_reason'] = f"IV Rank {result['iv_rank']:.1f}% < {self.config['iv_rank_min']}% minimum (need extreme IV)"
            return result
        
        # Build iron condor candidates
        iron_condors = self._build_iron_condors(ticker, expiration, quote['price'])
        
        if not iron_condors:
            result['status'] = 'REJECTED'
            result['reject_reason'] = 'Could not construct valid iron condor'
            return result
        
        # Sort by quality and take best
        iron_condors = sorted(iron_condors, key=lambda x: x['quality_score'], reverse=True)
        result['iron_condors'] = iron_condors[:3]
        result['best_condor'] = iron_condors[0]
        
        # Calculate overall quality score
        result['quality_score'] = self._calculate_quality_score(result)
        
        if verbose:
            print(f"   ✅ CANDIDATE: {ticker}")
            print(f"      Expiration: {expiration} ({dte} DTE)")
            print(f"      IV Rank: {result['iv_rank']}%")
            ic = result['best_condor']
            print(f"      IC: {ic['short_put_strike']}/{ic['long_put_strike']}P - {ic['short_call_strike']}/{ic['long_call_strike']}C")
            print(f"      Credit: ${ic['net_credit']:.2f} | Max Risk: ${ic['max_risk']:.2f} | ROI: {ic['roi_pct']:.1f}%")
        
        return result
    
    def _build_iron_condors(self, ticker: str, expiration: str, stock_price: float) -> List[Dict]:
        """
        Build iron condor structures for a stock.
        
        Args:
            ticker: Stock ticker
            expiration: Option expiration
            stock_price: Current stock price
            
        Returns:
            List of iron condor structures
        """
        iron_condors = []
        
        # Get PUT options for short and long legs
        # Short put: delta 0.15-0.20
        short_put_delta_min = -self.config['short_delta_max']  # -0.20
        short_put_delta_max = -self.config['short_delta_min']  # -0.15
        
        short_puts = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="PUT",
            delta_min=short_put_delta_min,
            delta_max=short_put_delta_max,
            volume_min=self.config['volume_min']
        )
        
        # Get CALL options for short and long legs
        short_calls = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="CALL",
            delta_min=self.config['short_delta_min'],  # 0.15
            delta_max=self.config['short_delta_max'],  # 0.20
            volume_min=self.config['volume_min']
        )
        
        if short_puts is None or short_puts.empty:
            return []
        if short_calls is None or short_calls.empty:
            return []
        
        # Get all puts and calls for long legs (wings)
        all_puts = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="PUT"
        )
        
        all_calls = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="CALL"
        )
        
        if all_puts is None or all_puts.empty or all_calls is None or all_calls.empty:
            return []
        
        # Build condors
        for _, short_put in short_puts.iterrows():
            for _, short_call in short_calls.iterrows():
                # Find long put (wing below short put)
                target_long_put_strike = short_put['strike_price'] - self.config['wing_width_min']
                long_put_candidates = all_puts[all_puts['strike_price'] <= target_long_put_strike]
                
                if long_put_candidates.empty:
                    continue
                
                # Take the closest strike to target wing width
                long_put = long_put_candidates.iloc[-1]  # Highest strike below target
                
                # Find long call (wing above short call)
                target_long_call_strike = short_call['strike_price'] + self.config['wing_width_min']
                long_call_candidates = all_calls[all_calls['strike_price'] >= target_long_call_strike]
                
                if long_call_candidates.empty:
                    continue
                
                long_call = long_call_candidates.iloc[0]  # Lowest strike above target
                
                # Calculate condor metrics
                condor = self._calculate_condor_metrics(
                    short_put, long_put, short_call, long_call, stock_price
                )
                
                if condor and condor['passes_filters']:
                    iron_condors.append(condor)
        
        return iron_condors
    
    def _calculate_condor_metrics(
        self, 
        short_put: pd.Series, 
        long_put: pd.Series, 
        short_call: pd.Series, 
        long_call: pd.Series,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Calculate iron condor metrics.
        
        Args:
            short_put: Short put option
            long_put: Long put option (wing)
            short_call: Short call option
            long_call: Long call option (wing)
            stock_price: Current stock price
            
        Returns:
            Condor metrics dict or None
        """
        try:
            # Extract values
            sp_strike = float(short_put['strike_price'])
            sp_bid = float(short_put.get('bid', 0))
            sp_delta = abs(float(short_put['delta']))
            
            lp_strike = float(long_put['strike_price'])
            lp_ask = float(long_put.get('ask', 0))
            
            sc_strike = float(short_call['strike_price'])
            sc_bid = float(short_call.get('bid', 0))
            sc_delta = abs(float(short_call['delta']))
            
            lc_strike = float(long_call['strike_price'])
            lc_ask = float(long_call.get('ask', 0))
            
            # Calculate spreads
            put_spread_width = sp_strike - lp_strike
            call_spread_width = lc_strike - sc_strike
            
            # Wing widths should be reasonable
            if put_spread_width < self.config['wing_width_min'] or call_spread_width < self.config['wing_width_min']:
                return None
            if put_spread_width > self.config['wing_width_max'] or call_spread_width > self.config['wing_width_max']:
                return None
            
            # Calculate credits and debits
            put_spread_credit = sp_bid - lp_ask
            call_spread_credit = sc_bid - lc_ask
            net_credit = put_spread_credit + call_spread_credit
            
            # Max risk is the wider wing minus credit
            max_wing = max(put_spread_width, call_spread_width)
            max_risk = max_wing - net_credit
            
            if max_risk <= 0:
                max_risk = 0.01  # Avoid division by zero
            
            # ROI calculation
            roi_pct = (net_credit / max_risk) * 100 if max_risk > 0 else 0
            
            # Premium as percentage of wing width
            premium_pct_of_width = net_credit / max_wing if max_wing > 0 else 0
            
            # Check filters
            passes_premium = premium_pct_of_width >= self.config['premium_pct_of_width_min']
            passes_filters = passes_premium
            
            # Quality score
            quality_score = 0
            if passes_filters:
                quality_score = (
                    roi_pct * 1.5 +  # ROI weighted
                    premium_pct_of_width * 50 +  # Premium % weighted
                    (1 - abs(sp_delta - 0.175) / 0.05) * 10 +  # Delta close to 0.175 ideal
                    (1 - abs(sc_delta - 0.175) / 0.05) * 10
                )
            
            return {
                'short_put_strike': sp_strike,
                'short_put_delta': sp_delta,
                'short_put_bid': sp_bid,
                'short_put_code': short_put.get('code', ''),
                
                'long_put_strike': lp_strike,
                'long_put_ask': lp_ask,
                'long_put_code': long_put.get('code', ''),
                
                'short_call_strike': sc_strike,
                'short_call_delta': sc_delta,
                'short_call_bid': sc_bid,
                'short_call_code': short_call.get('code', ''),
                
                'long_call_strike': lc_strike,
                'long_call_ask': lc_ask,
                'long_call_code': long_call.get('code', ''),
                
                'put_spread_width': put_spread_width,
                'call_spread_width': call_spread_width,
                'put_spread_credit': round(put_spread_credit, 2),
                'call_spread_credit': round(call_spread_credit, 2),
                'net_credit': round(net_credit, 2),
                'max_risk': round(max_risk, 2),
                'roi_pct': round(roi_pct, 1),
                'premium_pct_of_width': round(premium_pct_of_width * 100, 1),
                
                'profit_zone_low': sp_strike - net_credit,
                'profit_zone_high': sc_strike + net_credit,
                'stock_price': stock_price,
                
                'passes_premium': passes_premium,
                'passes_filters': passes_filters,
                'quality_score': round(quality_score, 2),
            }
            
        except Exception as e:
            print(f"Error calculating condor metrics: {e}")
            return None
    
    def _calculate_quality_score(self, result: Dict) -> float:
        """
        Calculate overall quality score for a candidate.
        
        Args:
            result: Analysis result dict
            
        Returns:
            Quality score (0-100)
        """
        score = 0
        
        # IV Rank contribution (0-40 points) - CRITICAL for vol harvest
        if result.get('iv_rank'):
            if result['iv_rank'] >= 100:
                score += 40
            elif result['iv_rank'] >= 90:
                score += 35
            elif result['iv_rank'] >= 80:
                score += 25
        
        # Best condor quality (0-40 points)
        if result.get('best_condor'):
            ic = result['best_condor']
            # ROI contribution
            score += min(ic['roi_pct'] * 0.5, 20)
            # Premium % contribution
            score += min(ic['premium_pct_of_width'] * 0.5, 20)
        
        # DTE contribution (0-10 points) - prefer middle of range
        if result.get('dte'):
            dte = result['dte']
            if 25 <= dte <= 30:
                score += 10
            elif 21 <= dte <= 35:
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
        ic = candidate.get('best_condor', {})
        
        lines = [
            f"\n{'─'*60}",
            f"🔥 {candidate['ticker']} - ${candidate['price']:.2f} (HIGH IV PLAY)",
            f"{'─'*60}",
            f"Expiration: {candidate['expiration']} ({candidate['dte']} DTE)",
            f"IV Rank: {candidate.get('iv_rank', 'N/A')}% | Current IV: {candidate.get('current_iv', 'N/A')}%",
            f"",
            f"IRON CONDOR STRUCTURE:",
            f"  PUT SPREAD:  Sell ${ic.get('short_put_strike', 0):.2f}P / Buy ${ic.get('long_put_strike', 0):.2f}P",
            f"               Width: ${ic.get('put_spread_width', 0):.2f} | Credit: ${ic.get('put_spread_credit', 0):.2f}",
            f"  CALL SPREAD: Sell ${ic.get('short_call_strike', 0):.2f}C / Buy ${ic.get('long_call_strike', 0):.2f}C",
            f"               Width: ${ic.get('call_spread_width', 0):.2f} | Credit: ${ic.get('call_spread_credit', 0):.2f}",
            f"",
            f"  NET CREDIT:  ${ic.get('net_credit', 0):.2f} (${ic.get('net_credit', 0)*100:.0f} per contract)",
            f"  MAX RISK:    ${ic.get('max_risk', 0):.2f} (${ic.get('max_risk', 0)*100:.0f} per contract)",
            f"  ROI:         {ic.get('roi_pct', 0):.1f}%",
            f"  Premium/Width: {ic.get('premium_pct_of_width', 0):.1f}%",
            f"",
            f"  PROFIT ZONE: ${ic.get('profit_zone_low', 0):.2f} - ${ic.get('profit_zone_high', 0):.2f}",
            f"               Stock at ${candidate['price']:.2f} (centered)",
            f"",
            f"Quality Score: {candidate.get('quality_score', 0):.1f}/100",
            f"Earnings: {candidate.get('earnings_status', 'Unknown')}",
            f"",
            f"⚠️  REMINDER: Vol Harvest = max 20% of capital, defined risk only",
        ]
        
        return '\n'.join(lines)


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    from data_fetcher import get_data_fetcher
    
    # Use mock data for testing
    fetcher = get_data_fetcher(use_mock=True)
    screener = VolHarvestScreener(fetcher)
    
    # Reduce universe for quick test
    screener.universe = ["GME", "AMC", "MARA", "HOOD"]
    
    print("\n" + "="*60)
    print("VOL HARVEST SCREENER TEST (Mock Data)")
    print("="*60)
    
    candidates = screener.screen_candidates(verbose=True)
    
    print("\n" + "="*60)
    print("TOP CANDIDATES")
    print("="*60)
    
    for candidate in candidates[:3]:
        print(screener.format_candidate_summary(candidate))
