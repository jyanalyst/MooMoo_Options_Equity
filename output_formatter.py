"""
Output Formatter
Handles terminal display and CSV export of scan results
"""

import csv
import os
from datetime import datetime
from typing import List, Dict

from config import OUTPUT_CONFIG


class OutputFormatter:
    """
    Formats scan results for terminal display and CSV export.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize Output Formatter.
        
        Args:
            output_dir: Directory for CSV output
        """
        self.output_dir = output_dir or OUTPUT_CONFIG.get('csv_output_dir', './scan_results')
        self.top_n = OUTPUT_CONFIG.get('display_top_n', 10)
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    # =========================================================================
    # TERMINAL DISPLAY
    # =========================================================================
    
    def display_wheel_results(self, candidates: List[Dict], show_all: bool = False):
        """
        Display Wheel scan results in terminal.
        
        Args:
            candidates: List of candidate dicts
            show_all: Show all candidates (vs top N)
        """
        display_list = candidates if show_all else candidates[:self.top_n]
        
        print(f"\n{'='*70}")
        print(f"🎯 WHEEL STRATEGY CANDIDATES - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        if not display_list:
            print("\n  No candidates found matching criteria.\n")
            return
        
        print(f"\nFound {len(candidates)} candidates. Showing top {len(display_list)}:\n")
        
        # Header
        print(f"{'Rank':<5} {'Ticker':<8} {'Price':>8} {'Exp':<12} {'DTE':>4} "
              f"{'Strike':>8} {'Δ':>6} {'Prem':>7} {'Ret%':>6} {'IVR':>5} {'Score':>6}")
        print("-" * 90)
        
        for i, c in enumerate(display_list, 1):
            opt = c.get('best_option', {})
            print(f"{i:<5} {c['ticker']:<8} ${c['price']:>6.2f} {c['expiration']:<12} "
                  f"{c.get('dte', 0):>4} ${opt.get('strike', 0):>6.2f} "
                  f"{opt.get('delta', 0):>5.2f} ${opt.get('premium', 0):>5.2f} "
                  f"{opt.get('return_pct', 0):>5.1f}% {c.get('iv_rank', 0):>4.0f}% "
                  f"{c.get('quality_score', 0):>5.1f}")
        
        print("-" * 90)
        print(f"\n📋 Legend: Δ=Delta, Prem=Premium(bid), Ret%=Return on Capital, IVR=IV Rank\n")
    
    def display_vol_harvest_results(self, candidates: List[Dict], show_all: bool = False):
        """
        Display Vol Harvest scan results in terminal.
        
        Args:
            candidates: List of candidate dicts
            show_all: Show all candidates (vs top N)
        """
        display_list = candidates if show_all else candidates[:self.top_n]
        
        print(f"\n{'='*70}")
        print(f"🔥 VOL HARVEST CANDIDATES (Iron Condors) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        if not display_list:
            print("\n  No candidates found matching criteria.\n")
            return
        
        print(f"\nFound {len(candidates)} candidates. Showing top {len(display_list)}:\n")
        
        # Header
        print(f"{'Rank':<5} {'Ticker':<7} {'Price':>7} {'Exp':<11} {'DTE':>4} "
              f"{'Put Sprd':>10} {'Call Sprd':>11} {'Credit':>7} {'Risk':>7} {'ROI':>6} {'IVR':>5}")
        print("-" * 100)
        
        for i, c in enumerate(display_list, 1):
            ic = c.get('best_condor', {})
            put_spread = f"{ic.get('short_put_strike', 0):.0f}/{ic.get('long_put_strike', 0):.0f}"
            call_spread = f"{ic.get('short_call_strike', 0):.0f}/{ic.get('long_call_strike', 0):.0f}"
            
            print(f"{i:<5} {c['ticker']:<7} ${c['price']:>5.2f} {c['expiration']:<11} "
                  f"{c.get('dte', 0):>4} {put_spread:>10} {call_spread:>11} "
                  f"${ic.get('net_credit', 0):>5.2f} ${ic.get('max_risk', 0):>5.2f} "
                  f"{ic.get('roi_pct', 0):>5.1f}% {c.get('iv_rank', 0):>4.0f}%")
        
        print("-" * 100)
        print(f"\n📋 Legend: Put/Call Sprd=Short/Long strikes, ROI=Return on Risk, IVR=IV Rank")
        print(f"⚠️  Remember: Max 20% capital allocation for Vol Harvest\n")
    
    def display_detailed_candidate(self, candidate: Dict, strategy: str = "wheel"):
        """
        Display detailed view of a single candidate.
        
        Args:
            candidate: Candidate dict
            strategy: 'wheel' or 'vol_harvest'
        """
        if strategy == "wheel":
            self._display_wheel_detail(candidate)
        else:
            self._display_vol_harvest_detail(candidate)
    
    def _display_wheel_detail(self, c: Dict):
        """Display detailed Wheel candidate"""
        opt = c.get('best_option', {})
        
        print(f"\n{'═'*60}")
        print(f"📊 {c['ticker']} - WHEEL CANDIDATE DETAIL")
        print(f"{'═'*60}")
        print(f"Current Price: ${c['price']:.2f}")
        print(f"Expiration:    {c['expiration']} ({c.get('dte', 0)} DTE)")
        print(f"IV Rank:       {c.get('iv_rank', 'N/A')}%")
        print(f"Current IV:    {c.get('current_iv', 'N/A')}%")
        print(f"Term Structure: {c.get('term_structure', 'N/A')}")
        print(f"                {c.get('term_structure_recommendation', '')}")
        print(f"Earnings:      {c.get('earnings_status', 'Unknown')}")
        print()
        print("RECOMMENDED PUT:")
        print(f"  Strike:       ${opt.get('strike', 0):.2f}")
        print(f"  Delta:        {opt.get('delta', 0):.3f}")
        print(f"  Premium:      ${opt.get('premium', 0):.2f} (Bid ${opt.get('bid', 0):.2f} / Ask ${opt.get('ask', 0):.2f})")
        print(f"  Spread:       ${opt.get('spread', 0):.2f} ({opt.get('spread_pct', 0):.1f}%)")
        print(f"  Cash Required: ${opt.get('cash_required', 0):,.0f}")
        print(f"  Return:       {opt.get('return_pct', 0):.2f}%")
        print(f"  Volume:       {opt.get('volume', 0):,}")
        print(f"  Open Interest: {opt.get('open_interest', 0):,}")
        print()
        print(f"Quality Score: {c.get('quality_score', 0):.1f}/100")
        print(f"Option Code:   {opt.get('code', 'N/A')}")
        print(f"{'═'*60}\n")
    
    def _display_vol_harvest_detail(self, c: Dict):
        """Display detailed Vol Harvest candidate"""
        ic = c.get('best_condor', {})
        
        print(f"\n{'═'*60}")
        print(f"🔥 {c['ticker']} - VOL HARVEST CANDIDATE DETAIL")
        print(f"{'═'*60}")
        print(f"Current Price: ${c['price']:.2f}")
        print(f"Expiration:    {c['expiration']} ({c.get('dte', 0)} DTE)")
        print(f"IV Rank:       {c.get('iv_rank', 'N/A')}%")
        print(f"Current IV:    {c.get('current_iv', 'N/A')}%")
        print(f"Earnings:      {c.get('earnings_status', 'Unknown')}")
        print()
        print("IRON CONDOR STRUCTURE:")
        print(f"  PUT SPREAD:")
        print(f"    Sell: ${ic.get('short_put_strike', 0):.2f}P @ ${ic.get('short_put_bid', 0):.2f}")
        print(f"    Buy:  ${ic.get('long_put_strike', 0):.2f}P @ ${ic.get('long_put_ask', 0):.2f}")
        print(f"    Width: ${ic.get('put_spread_width', 0):.2f} | Credit: ${ic.get('put_spread_credit', 0):.2f}")
        print()
        print(f"  CALL SPREAD:")
        print(f"    Sell: ${ic.get('short_call_strike', 0):.2f}C @ ${ic.get('short_call_bid', 0):.2f}")
        print(f"    Buy:  ${ic.get('long_call_strike', 0):.2f}C @ ${ic.get('long_call_ask', 0):.2f}")
        print(f"    Width: ${ic.get('call_spread_width', 0):.2f} | Credit: ${ic.get('call_spread_credit', 0):.2f}")
        print()
        print(f"  NET CREDIT:    ${ic.get('net_credit', 0):.2f} (${ic.get('net_credit', 0)*100:.0f}/contract)")
        print(f"  MAX RISK:      ${ic.get('max_risk', 0):.2f} (${ic.get('max_risk', 0)*100:.0f}/contract)")
        print(f"  ROI:           {ic.get('roi_pct', 0):.1f}%")
        print(f"  Premium/Width: {ic.get('premium_pct_of_width', 0):.1f}%")
        print()
        print(f"  PROFIT ZONE:   ${ic.get('profit_zone_low', 0):.2f} - ${ic.get('profit_zone_high', 0):.2f}")
        print()
        print(f"Quality Score:   {c.get('quality_score', 0):.1f}/100")
        print(f"{'═'*60}")
        print(f"⚠️  Max position: 5% of Vol Harvest capital per condor")
        print(f"{'═'*60}\n")
    
    # =========================================================================
    # CSV EXPORT
    # =========================================================================
    
    def export_wheel_csv(self, candidates: List[Dict], filename: str = None) -> str:
        """
        Export Wheel candidates to CSV.
        
        Args:
            candidates: List of candidate dicts
            filename: Custom filename (optional)
            
        Returns:
            Path to exported file
        """
        if not filename:
            date_str = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"wheel_candidates_{date_str}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        fieldnames = [
            'rank', 'ticker', 'price', 'expiration', 'dte',
            'strike', 'delta', 'premium', 'return_pct', 'cash_required',
            'bid', 'ask', 'spread', 'spread_pct', 'volume', 'open_interest',
            'iv_rank', 'current_iv', 'term_structure',
            'earnings_status', 'quality_score', 'option_code'
        ]
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, c in enumerate(candidates, 1):
                opt = c.get('best_option', {})
                writer.writerow({
                    'rank': i,
                    'ticker': c['ticker'],
                    'price': c['price'],
                    'expiration': c.get('expiration', ''),
                    'dte': c.get('dte', ''),
                    'strike': opt.get('strike', ''),
                    'delta': opt.get('delta', ''),
                    'premium': opt.get('premium', ''),
                    'return_pct': opt.get('return_pct', ''),
                    'cash_required': opt.get('cash_required', ''),
                    'bid': opt.get('bid', ''),
                    'ask': opt.get('ask', ''),
                    'spread': opt.get('spread', ''),
                    'spread_pct': opt.get('spread_pct', ''),
                    'volume': opt.get('volume', ''),
                    'open_interest': opt.get('open_interest', ''),
                    'iv_rank': c.get('iv_rank', ''),
                    'current_iv': c.get('current_iv', ''),
                    'term_structure': c.get('term_structure', ''),
                    'earnings_status': c.get('earnings_status', ''),
                    'quality_score': c.get('quality_score', ''),
                    'option_code': opt.get('code', ''),
                })
        
        print(f"✅ Exported {len(candidates)} Wheel candidates to: {filepath}")
        return filepath
    
    def export_vol_harvest_csv(self, candidates: List[Dict], filename: str = None) -> str:
        """
        Export Vol Harvest candidates to CSV.
        
        Args:
            candidates: List of candidate dicts
            filename: Custom filename (optional)
            
        Returns:
            Path to exported file
        """
        if not filename:
            date_str = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"vol_harvest_candidates_{date_str}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        fieldnames = [
            'rank', 'ticker', 'price', 'expiration', 'dte',
            'short_put', 'long_put', 'put_width', 'put_credit',
            'short_call', 'long_call', 'call_width', 'call_credit',
            'net_credit', 'max_risk', 'roi_pct', 'premium_pct_of_width',
            'profit_zone_low', 'profit_zone_high',
            'iv_rank', 'current_iv', 'earnings_status', 'quality_score'
        ]
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, c in enumerate(candidates, 1):
                ic = c.get('best_condor', {})
                writer.writerow({
                    'rank': i,
                    'ticker': c['ticker'],
                    'price': c['price'],
                    'expiration': c.get('expiration', ''),
                    'dte': c.get('dte', ''),
                    'short_put': ic.get('short_put_strike', ''),
                    'long_put': ic.get('long_put_strike', ''),
                    'put_width': ic.get('put_spread_width', ''),
                    'put_credit': ic.get('put_spread_credit', ''),
                    'short_call': ic.get('short_call_strike', ''),
                    'long_call': ic.get('long_call_strike', ''),
                    'call_width': ic.get('call_spread_width', ''),
                    'call_credit': ic.get('call_spread_credit', ''),
                    'net_credit': ic.get('net_credit', ''),
                    'max_risk': ic.get('max_risk', ''),
                    'roi_pct': ic.get('roi_pct', ''),
                    'premium_pct_of_width': ic.get('premium_pct_of_width', ''),
                    'profit_zone_low': ic.get('profit_zone_low', ''),
                    'profit_zone_high': ic.get('profit_zone_high', ''),
                    'iv_rank': c.get('iv_rank', ''),
                    'current_iv': c.get('current_iv', ''),
                    'earnings_status': c.get('earnings_status', ''),
                    'quality_score': c.get('quality_score', ''),
                })
        
        print(f"✅ Exported {len(candidates)} Vol Harvest candidates to: {filepath}")
        return filepath
    
    # =========================================================================
    # SUMMARY REPORT
    # =========================================================================
    
    def print_scan_summary(
        self, 
        wheel_candidates: List[Dict] = None, 
        vol_harvest_candidates: List[Dict] = None
    ):
        """
        Print summary of scan results.
        
        Args:
            wheel_candidates: Wheel scan results
            vol_harvest_candidates: Vol Harvest scan results
        """
        print(f"\n{'='*60}")
        print(f"📊 SCAN SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        
        if wheel_candidates is not None:
            print(f"\n🎯 WHEEL STRATEGY:")
            print(f"   Candidates found: {len(wheel_candidates)}")
            if wheel_candidates:
                top = wheel_candidates[0]
                print(f"   Top candidate: {top['ticker']} (Score: {top.get('quality_score', 0):.1f})")
        
        if vol_harvest_candidates is not None:
            print(f"\n🔥 VOL HARVEST:")
            print(f"   Candidates found: {len(vol_harvest_candidates)}")
            if vol_harvest_candidates:
                top = vol_harvest_candidates[0]
                print(f"   Top candidate: {top['ticker']} (Score: {top.get('quality_score', 0):.1f})")
        
        print(f"\n{'='*60}\n")


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    # Create sample data for testing
    sample_wheel = [
        {
            'ticker': 'INTC',
            'price': 22.50,
            'expiration': '2025-02-21',
            'dte': 35,
            'iv_rank': 45.0,
            'current_iv': 38.5,
            'term_structure': 'CONTANGO',
            'term_structure_recommendation': 'FAVORABLE',
            'earnings_status': 'SAFE - earnings passed',
            'quality_score': 72.5,
            'best_option': {
                'strike': 21.0,
                'delta': 0.25,
                'premium': 0.45,
                'bid': 0.45,
                'ask': 0.48,
                'spread': 0.03,
                'spread_pct': 6.5,
                'return_pct': 2.14,
                'cash_required': 2100,
                'volume': 2500,
                'open_interest': 15000,
                'code': 'US.INTC250221P00021000',
            }
        },
    ]
    
    sample_vol = [
        {
            'ticker': 'GME',
            'price': 25.00,
            'expiration': '2025-02-07',
            'dte': 28,
            'iv_rank': 95.0,
            'current_iv': 85.0,
            'earnings_status': 'SAFE',
            'quality_score': 68.0,
            'best_condor': {
                'short_put_strike': 22.0,
                'long_put_strike': 19.5,
                'short_call_strike': 28.0,
                'long_call_strike': 30.5,
                'put_spread_width': 2.5,
                'call_spread_width': 2.5,
                'put_spread_credit': 0.45,
                'call_spread_credit': 0.40,
                'net_credit': 0.85,
                'max_risk': 1.65,
                'roi_pct': 51.5,
                'premium_pct_of_width': 34.0,
                'profit_zone_low': 21.15,
                'profit_zone_high': 28.85,
            }
        },
    ]
    
    formatter = OutputFormatter()
    
    print("\n" + "="*60)
    print("OUTPUT FORMATTER TEST")
    print("="*60)
    
    formatter.display_wheel_results(sample_wheel)
    formatter.display_vol_harvest_results(sample_vol)
    formatter.display_detailed_candidate(sample_wheel[0], 'wheel')
    formatter.display_detailed_candidate(sample_vol[0], 'vol_harvest')
    formatter.print_scan_summary(sample_wheel, sample_vol)
