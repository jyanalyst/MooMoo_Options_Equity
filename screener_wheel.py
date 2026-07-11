"""
Wheel Strategy Screener
Screens for cash-secured put candidates based on Wheel Strategy Guide criteria
"""

from typing import List, Dict
from datetime import datetime
import pandas as pd

from config import WHEEL_CONFIG
from universe import get_wheel_universe
from earnings_checker import EarningsChecker
from iv_analyzer import IVAnalyzer


class WheelScreener:
    """
    Screens stocks for Wheel Strategy (cash-secured puts).

    Hard filters (reject): price $15-200, DTE 30-45, delta 0.20-0.30, earnings
    safety (fail-closed), OI >= open_interest_min, spread <= bid_ask_spread_max_pct,
    premium >= premium_pct_of_strike_min. Missing bid/ask/delta => reject (never
    approximated). Soft (score-only): IV Rank, term structure.
    """

    def __init__(
        self,
        data_fetcher,
        max_capital: int = None,
        allow_unverified: bool = None,
        earnings_checker=None,
        iv_analyzer=None,
    ):
        """
        Initialize Wheel Screener.

        Args:
            data_fetcher: HybridDataFetcher or MockDataFetcher instance
            max_capital: Maximum capital per position in dollars (optional)
                        e.g., 10000 filters to stocks with price <= $100
            allow_unverified: Allow stocks with unverified earnings dates (default: from config)
            earnings_checker: Injectable EarningsChecker (mock runs pass an offline stub)
            iv_analyzer: Injectable IVAnalyzer (mock runs pass one with temp files)
        """
        self.data_fetcher = data_fetcher
        self.max_capital = max_capital
        # Default to config value if not explicitly specified
        self.allow_unverified = (
            allow_unverified
            if allow_unverified is not None
            else WHEEL_CONFIG.get("allow_unverified_earnings", False)
        )

        self.universe = get_wheel_universe(self.max_capital)
        self.earnings_checker = earnings_checker or EarningsChecker()
        self.iv_analyzer = iv_analyzer or IVAnalyzer(data_fetcher)
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
            print(f"\n{'=' * 60}")
            print("WHEEL STRATEGY SCREENER")
            capital_str = (
                f"max ${self.max_capital:,}" if self.max_capital else "all prices"
            )
            print(f"Universe: {len(self.universe)} stocks ({capital_str})")
            print(f"{'=' * 60}\n")

        # Step 1: Get quotes for all stocks
        if verbose:
            print("Step 1: Fetching quotes...")

        quotes = self.data_fetcher.get_batch_quotes(self.universe)

        # Step 2: Filter by price
        if verbose:
            print("Step 2: Filtering by price range...")

        price_filtered = []
        for ticker, quote in quotes.items():
            price = quote.get("price", 0)
            if self.config["price_min"] <= price <= self.config["price_max"]:
                price_filtered.append((ticker, quote))
            else:
                rejected.append(
                    (
                        ticker,
                        f"Price ${price:.2f} outside ${self.config['price_min']}-${self.config['price_max']} range",
                    )
                )

        if verbose:
            print(f"   {len(price_filtered)}/{len(quotes)} passed price filter")

        # Step 3: Process each stock
        for ticker, quote in price_filtered:
            if verbose:
                print(f"\nAnalyzing {ticker} (${quote['price']:.2f})...")

            result = self._analyze_stock(ticker, quote, verbose)

            if result["status"] == "CANDIDATE":
                candidates.append(result)
            else:
                rejected.append((ticker, result["reject_reason"]))

        # Step 4: Sort candidates by quality score
        candidates = sorted(
            candidates, key=lambda x: x.get("quality_score", 0), reverse=True
        )

        # Rejection breakdown - always shown so the candidate count is self-explaining
        # (e.g. a dark FMP earnings feed shows up here as a wall of earnings rejections).
        if rejected:
            from collections import Counter

            cats = Counter(self._reject_category(reason) for _, reason in rejected)
            print(
                f"\nRejection breakdown ({len(candidates)} candidates, {len(rejected)} rejected):"
            )
            for cat, n in cats.most_common():
                print(f"   {n:>3}  {cat}")
            earnings_rejects = cats.get("Earnings unverified/conflict", 0)
            if earnings_rejects >= max(5, len(rejected) // 2):
                print(
                    "   -> Most rejections are earnings (fail-closed). If the FMP feed is "
                    "down/over quota, restore it and re-scan; or use --allow-unverified "
                    "to override (you must verify each name manually)."
                )

        if verbose:
            print(f"\n{'=' * 60}")
            print("SCREENING COMPLETE")
            print(f"Candidates: {len(candidates)}")
            print(f"Rejected: {len(rejected)}")
            print(f"{'=' * 60}")

        return candidates

    def _is_post_earnings_crush(self, last_earnings, iv_method, iv_rank) -> bool:
        """
        True if the name is within the post-earnings IV-crush window WITHOUT confirmed
        elevated IV. Per the strategy guide, a post-earnings entry is valid only if IV
        Rank is still elevated (> post_earnings_min_iv_rank) - and that requires a
        RELIABLE reading (iv_percentile, not warm-up). When IV can't be confirmed, we
        reject conservatively rather than sell into a likely crush.
        """
        if last_earnings is None:
            return False
        days_since = (datetime.now() - last_earnings).days
        if not (0 <= days_since <= self.config["earnings_recency_days"]):
            return False
        iv_confirmed_elevated = (
            iv_method == "iv_percentile"
            and iv_rank is not None
            and iv_rank > self.config["post_earnings_min_iv_rank"]
        )
        return not iv_confirmed_elevated

    @staticmethod
    def _reject_category(reason: str) -> str:
        """Bucket a free-text reject reason into a coarse category for the breakdown."""
        r = (reason or "").lower()
        if "crush" in r:
            return "Post-earnings IV crush"
        if "earnings" in r:
            return "Earnings unverified/conflict"
        if "dte" in r:
            return "No expiration in DTE range"
        if "expiration" in r:
            return "No option expirations"
        if "oi " in r:
            return "Liquidity (OI too low)"
        if "spread" in r:
            return "Spread too wide"
        if "premium" in r:
            return "Premium below floor"
        if "bid" in r or "hard-rejected" in r:
            return "No tradeable contracts"
        if "delta" in r:
            return "No contracts in delta band"
        if "price" in r:
            return "Price out of range"
        return "Other"

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
            "ticker": ticker,
            "price": quote["price"],
            "status": "CANDIDATE",
            "reject_reason": None,
            "options": [],
            "quality_score": 0,
        }

        if verbose:
            print(f"\n   >> DEBUGGING {ticker} (${quote['price']:.2f})")
            print("      Step 1: Getting option expirations...")

        # Get option expirations
        expirations = self.data_fetcher.get_option_expirations(ticker)
        if verbose:
            print(
                f"      -> Expirations found: {len(expirations) if expirations else 0}"
            )
            if expirations:
                print(f"         Sample: {expirations[:3]}...")

        if not expirations:
            result["status"] = "REJECTED"
            result["reject_reason"] = "No option expirations available"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Filter expirations by DTE
        if verbose:
            print(
                f"      Step 2: Filtering by DTE ({self.config['dte_min']}-{self.config['dte_max']} days)..."
            )

        target_expirations = self.data_fetcher.filter_expirations_by_dte(
            expirations, self.config["dte_min"], self.config["dte_max"]
        )

        if verbose:
            print(f"      -> Target expirations: {len(target_expirations)}")
            if target_expirations:
                for exp, dte in target_expirations[:3]:
                    print(f"         {exp} ({dte} DTE)")

        if not target_expirations:
            result["status"] = "REJECTED"
            result["reject_reason"] = (
                f"No expirations in {self.config['dte_min']}-{self.config['dte_max']} DTE range"
            )
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Check earnings for each expiration
        if verbose:
            print(
                f"      Step 3: Checking earnings safety (buffer: {self.config['earnings_buffer_days']} days)..."
            )

        best_expiration = None
        earnings_safe = False

        for exp, dte in target_expirations:
            exp_datetime = datetime.strptime(exp, "%Y-%m-%d")
            is_safe, earnings_date, reason = self.earnings_checker.check_earnings_safe(
                ticker,
                exp_datetime,
                buffer_days=self.config["earnings_buffer_days"],
                allow_unverified=self.allow_unverified,
            )

            if verbose:
                print(f"         {exp}: {reason}")

            if is_safe:
                best_expiration = (exp, dte)
                earnings_safe = True
                result["earnings_status"] = reason
                break

        if not earnings_safe or not best_expiration:
            result["status"] = "REJECTED"
            result["reject_reason"] = "Earnings conflict for all expirations"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        expiration, dte = best_expiration
        result["expiration"] = expiration
        result["dte"] = dte

        if verbose:
            print(f"      [OK] Earnings safe - using {expiration} ({dte} DTE)")
            print("      Step 4: Analyzing IV metrics...")

        # Get IV analysis
        iv_analysis = self.iv_analyzer.get_full_iv_analysis(ticker, expiration)
        result["iv_rank"] = iv_analysis.get("iv_rank")
        result["iv_method"] = iv_analysis.get("iv_method")
        result["current_iv"] = iv_analysis.get("current_iv")
        result["term_structure"] = iv_analysis.get("term_structure")
        result["term_structure_recommendation"] = iv_analysis.get(
            "term_structure_recommendation"
        )

        if verbose:
            print(f"      -> Current IV: {result['current_iv']}%")
            print(f"      -> IV Rank: {result['iv_rank']}% ({result.get('iv_method')})")
            print(
                f"      -> Term Structure: {result['term_structure']} ({result['term_structure_recommendation']})"
            )

        # IV Rank is a SOFT filter - low IV Rank reduces score but doesn't reject.
        # Skip the filter entirely while the metric is provisional (hv_proxy warm-up):
        # an unreliable reading must neither reward nor penalize a candidate.
        iv_warning = None
        iv_reliable = result.get("iv_method") != "hv_proxy_provisional"
        if (
            iv_reliable
            and result["iv_rank"] is not None
            and result["iv_rank"] < self.config["iv_rank_min"]
        ):
            iv_warning = f"Low IV Rank ({result['iv_rank']:.1f}% < {self.config['iv_rank_min']}%)"
            result["iv_warning"] = iv_warning

        if verbose:
            if not iv_reliable:
                print(
                    "      [~] IV Rank PROVISIONAL (warm-up) - unavailable, excluded from scoring"
                )
            elif iv_warning:
                print(
                    f"      [!] IV Rank below threshold ({result['iv_rank']:.1f}%) - will reduce score"
                )
            else:
                print("      [OK] IV Rank filter passed")

        # Post-earnings IV-crush guard. Reject names within the recency window unless IV
        # Rank is CONFIRMED elevated - a 6-day post-earnings name with crushed implied vol
        # (PDD) is selling cheap premium, the opposite of the strategy's edge.
        last_earnings = self.earnings_checker.get_earnings_info(ticker).get(
            "last_earnings"
        )
        if self._is_post_earnings_crush(
            last_earnings, result.get("iv_method"), result.get("iv_rank")
        ):
            days_since = (datetime.now() - last_earnings).days
            result["status"] = "REJECTED"
            result["reject_reason"] = (
                f"Post-earnings IV crush risk ({days_since}d since report; IV Rank "
                f"unconfirmed or <={self.config['post_earnings_min_iv_rank']})"
            )
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        if verbose:
            print(
                f"      Step 5: Getting options chain (PUTs, delta {self.config['delta_min']}-{self.config['delta_max']})..."
            )

        # Get options chain with delta filter
        # MooMoo uses negative delta for puts
        delta_min = -self.config["delta_max"]  # e.g., -0.30
        delta_max = -self.config["delta_min"]  # e.g., -0.20

        # Don't filter by volume here - we want to check both volume AND open interest
        chain = self.data_fetcher.get_options_chain(
            ticker=ticker,
            expiration=expiration,
            option_type="PUT",
            delta_min=delta_min,
            delta_max=delta_max,
            # Removed: volume_min=self.config['volume_min']
        )

        if verbose:
            print(
                f"      -> Chain returned: {len(chain) if chain is not None and not chain.empty else 0} options"
            )
            if chain is not None and not chain.empty:
                print(f"      -> Columns: {chain.columns.tolist()}")
                print("      -> Sample option:")
                sample = chain.iloc[0] if len(chain) > 0 else None
                if sample is not None:
                    print(
                        f"         Strike: ${sample.get('strike_price', 'N/A')}, Delta: {sample.get('delta', 'N/A')}, Bid: ${sample.get('bid', 'N/A')}, Ask: ${sample.get('ask', 'N/A')}, Volume: {sample.get('volume', 'N/A')}"
                    )

        if chain is None or chain.empty:
            result["status"] = "REJECTED"
            result["reject_reason"] = (
                f"No options match delta {self.config['delta_min']}-{self.config['delta_max']}"
            )
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        if verbose:
            print(
                f"      Step 6: Applying hard filters + ranking {len(chain)} options..."
            )

        # Hard-filter each contract, then rank the survivors
        all_options = []
        reject_tally = {}

        for i, (_idx, opt) in enumerate(chain.iterrows()):
            opt_analysis = self._analyze_option(opt, quote["price"], dte)

            reason = opt_analysis["hard_reject"]
            if reason is None:
                all_options.append(opt_analysis)
            else:
                reject_tally[reason] = reject_tally.get(reason, 0) + 1

            if verbose and i < 3:  # Show first 3 options
                if reason:
                    detail = f"HARD REJECT: {reason}"
                elif opt_analysis["warnings"]:
                    detail = f"Score={opt_analysis['quality_score']:.0f} [{', '.join(opt_analysis['warnings'])}]"
                else:
                    detail = f"Score={opt_analysis['quality_score']:.0f}"
                print(
                    f"         Option {i + 1}: ${opt_analysis['strike']} | Bid ${opt_analysis['bid']:.2f} | OI={opt_analysis['open_interest']} | {detail}"
                )

        if verbose:
            print(
                f"      -> Contracts passing hard filters: {len(all_options)}/{len(chain)}"
            )

        if not all_options:
            # Surface the dominant per-contract reject reason at the stock level
            dominant = (
                max(reject_tally, key=reject_tally.get) if reject_tally else "no data"
            )
            result["status"] = "REJECTED"
            result["reject_reason"] = f"All contracts hard-rejected ({dominant})"
            if verbose:
                print(f"      [X] REJECTED: {result['reject_reason']}")
            return result

        # Sort ALL options by quality score and take best
        all_options = sorted(
            all_options, key=lambda x: x["quality_score"], reverse=True
        )
        result["options"] = all_options[:3]  # Top 3 options
        result["best_option"] = all_options[0]

        # Add warnings from best option to result
        result["option_warnings"] = all_options[0].get("warnings", [])

        # Calculate overall quality score
        result["quality_score"] = self._calculate_quality_score(result)

        if verbose:
            warnings = result.get("option_warnings", [])
            status = (
                "[OK] CANDIDATE" if not warnings else "[!] CANDIDATE (with warnings)"
            )
            print(f"      {status}: {ticker}")
            print(f"         Expiration: {expiration} ({dte} DTE)")
            print(f"         IV Rank: {result['iv_rank']}%")
            print(
                f"         Best Strike: ${result['best_option']['strike']} (Score: {result['best_option']['quality_score']:.0f})"
            )
            print(
                f"         Premium: ${result['best_option']['premium']:.2f} "
                f"({result['best_option']['return_pct']:.2f}% raw, "
                f"{result['best_option'].get('annualized_return_pct', 0):.1f}%/yr)"
            )
            if warnings:
                print(f"         Warnings: {', '.join(warnings)}")

        return result

    def _analyze_option(self, option: pd.Series, stock_price: float, dte: int) -> Dict:
        """
        Analyze a single option contract.

        PRODUCTION RULE — no fabricated data: missing bid/ask/delta means the
        contract is hard-rejected, never approximated. Hard rejects also enforce
        execution quality (OI, spread, premium floor) from WHEEL_CONFIG.

        Args:
            option: Option data from chain
            stock_price: Current stock price
            dte: Days to expiration for this contract (used to annualize the yield)

        Returns:
            Option analysis dict. 'hard_reject' is None for tradeable contracts,
            else a short reason string; rejected contracts carry zero scores.
        """

        # Helper to safely get value with fallback
        def safe_get(key, default=0):
            val = option.get(key, default)
            if pd.isna(val):
                return default
            return val

        strike = float(safe_get("strike_price", stock_price))
        delta = abs(float(safe_get("delta", 0)))
        last_price = float(safe_get("last_price", 0))
        bid = float(safe_get("bid", 0))
        ask = float(safe_get("ask", 0))
        volume = int(safe_get("volume", 0))
        oi = int(safe_get("open_interest", 0))

        # IV might be in different column names. Live sources deliver IV as a
        # percentage (e.g. 35.2) — store as-is, do NOT rescale.
        iv = 0
        for iv_col in ["implied_volatility", "iv", "impliedVolatility"]:
            if iv_col in option.index:
                iv_val = option.get(iv_col, 0)
                if pd.notna(iv_val):
                    iv = float(iv_val)
                    break

        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
        spread = ask - bid if mid > 0 else 0
        spread_pct = spread / mid if mid > 0 else 0

        # Premium is what the market pays you NOW: the bid.
        premium = bid
        cash_required = strike * 100
        # Raw premium yield on strike (single-period, for display / cash-flow)
        return_pct = (premium / strike) * 100 if strike > 0 else 0
        # Annualized yield is the cross-stock ranking metric: the same dollar premium
        # is worth more on a shorter-dated contract. Simple linear scaling (x365/DTE)
        # assumes the put is held to expiry; it is a yield comparator, not a compounded
        # return, and ignores assignment (delta already scores assignment risk separately).
        annualized_return_pct = return_pct * (365.0 / dte) if dte > 0 else 0

        # HARD REJECTS (execution quality — checked in escalating order)
        hard_reject = None
        if bid <= 0 or ask <= 0:
            hard_reject = "no valid bid/ask"
        elif delta == 0:
            hard_reject = "missing delta (no Greeks)"
        elif oi < self.config["open_interest_min"]:
            hard_reject = f"OI {oi} < {self.config['open_interest_min']}"
        elif spread_pct > self.config["bid_ask_spread_max_pct"]:
            hard_reject = (
                f"spread {spread_pct * 100:.0f}% > "
                f"{self.config['bid_ask_spread_max_pct'] * 100:.0f}%"
            )
        elif return_pct < self.config["premium_pct_of_strike_min"] * 100:
            hard_reject = (
                f"premium {return_pct:.2f}% < "
                f"{self.config['premium_pct_of_strike_min'] * 100:.1f}% floor"
            )

        result = {
            "code": option.get("code", ""),
            "strike": strike,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "last_price": last_price,
            "mid": round(mid, 2),
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct * 100, 2),
            "premium": premium,
            "cash_required": cash_required,
            "return_pct": round(return_pct, 2),
            "annualized_return_pct": round(annualized_return_pct, 2),
            "volume": volume,
            "open_interest": oi,
            "iv": round(iv, 1),
            "hard_reject": hard_reject,
            "quality_score": 0.0,
            "premium_score": 0.0,
            "liquidity_score": 0.0,
            "spread_score": 0.0,
            "delta_score": 0.0,
            "warnings": [],
        }

        if hard_reject:
            return result

        # SCORING (survivors only; higher = better)

        # Premium score (0-40 points) - most important for wheel strategy.
        # Scored on ANNUALIZED yield (~1 pt per 1% annualized, capped at 40 => 40%/yr)
        # so a 30-DTE and a 45-DTE contract paying the same raw % are ranked correctly.
        premium_score = min(annualized_return_pct, 40)

        # Liquidity score (0-20 points); all survivors have OI >= 100
        liquidity_score = 15
        if oi >= 500:
            liquidity_score = 20
        # Volume bonus
        if volume >= 10:
            liquidity_score = min(liquidity_score + 5, 20)

        # Spread score (0-20 points) - tighter is better; survivors are <= 10%
        if spread_pct <= 0.05:  # 5% or less
            spread_score = 20
        else:
            spread_score = 15

        # Delta score (0-10 points) - prefer 0.25-0.30 range
        delta_score = 0
        if 0.25 <= delta <= 0.30:
            delta_score = 10  # Ideal range
        elif 0.20 <= delta <= 0.35:
            delta_score = 7  # Acceptable range
        elif 0.15 <= delta <= 0.40:
            delta_score = 4  # Edge of range

        # Total option quality score (0-90)
        quality_score = premium_score + liquidity_score + spread_score + delta_score

        # Warnings (informational, not rejections)
        warnings = []
        if volume == 0:
            warnings.append("no volume today")
        if spread_pct > 0.05:
            warnings.append(f"spread {spread_pct * 100:.0f}%")

        result.update(
            {
                "quality_score": round(quality_score, 2),
                "premium_score": round(premium_score, 1),
                "liquidity_score": round(liquidity_score, 1),
                "spread_score": round(spread_score, 1),
                "delta_score": round(delta_score, 1),
                "warnings": warnings,
            }
        )
        return result

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

        # IV Rank contribution (0-30 points). Provisional (hv_proxy warm-up) readings are
        # unreliable, so they contribute ZERO — they can't help a candidate rank.
        if result.get("iv_method") != "hv_proxy_provisional" and result.get("iv_rank"):
            if result["iv_rank"] >= 50:
                score += 30
            elif result["iv_rank"] >= 40:
                score += 20
            elif result["iv_rank"] >= 30:
                score += 10

        # Term structure contribution (0-20 points)
        term = result.get("term_structure")
        if term == "CONTANGO":
            score += 20
        elif term == "NEUTRAL":
            score += 10
        # BACKWARDATION gets 0

        # Best option quality (0-30 points)
        if result.get("best_option"):
            opt = result["best_option"]
            # Return contribution
            # Use annualized yield on the same scale as premium_score (0.3 pt per
            # annualized %, capped at 15 => 50%/yr) so both scoring layers agree.
            score += min(opt.get("annualized_return_pct", opt["return_pct"]) * 0.3, 15)
            # Spread contribution
            if opt["spread_pct"] < 5:
                score += 15
            elif opt["spread_pct"] < 10:
                score += 10

        # DTE contribution (0-10 points) - prefer middle of range
        if result.get("dte"):
            dte = result["dte"]
            if 35 <= dte <= 40:
                score += 10
            elif 30 <= dte <= 45:
                score += 5

        # Earnings safety contribution (0-10 points)
        if result.get("earnings_status"):
            if "SAFE" in result["earnings_status"]:
                score += 10
            elif "UNVERIFIED" in result["earnings_status"]:
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
        opt = candidate.get("best_option", {})

        lines = [
            f"\n{'─' * 50}",
            f"📊 {candidate['ticker']} - ${candidate['price']:.2f}",
            f"{'─' * 50}",
            f"Expiration: {candidate['expiration']} ({candidate['dte']} DTE)",
            f"IV Rank: {candidate.get('iv_rank', 'N/A')}% | Term Structure: {candidate.get('term_structure', 'N/A')}",
            "",
            "RECOMMENDED PUT:",
            f"  Strike: ${opt.get('strike', 0):.2f} (Δ {opt.get('delta', 0):.2f})",
            f"  Premium: ${opt.get('premium', 0):.2f} (Bid ${opt.get('bid', 0):.2f} / Ask ${opt.get('ask', 0):.2f})",
            f"  Return: {opt.get('return_pct', 0):.2f}% on ${opt.get('cash_required', 0):,.0f} capital",
            f"  Spread: ${opt.get('spread', 0):.2f} ({opt.get('spread_pct', 0):.1f}%)",
            f"  Volume: {opt.get('volume', 0):,} | OI: {opt.get('open_interest', 0):,}",
            "",
            f"Quality Score: {candidate.get('quality_score', 0):.1f}/100",
            f"Earnings: {candidate.get('earnings_status', 'Unknown')}",
        ]

        return "\n".join(lines)


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

    print("\n" + "=" * 60)
    print("WHEEL SCREENER TEST (Mock Data)")
    print("=" * 60)

    candidates = screener.screen_candidates(verbose=True)

    print("\n" + "=" * 60)
    print("TOP CANDIDATES")
    print("=" * 60)

    for candidate in candidates[:3]:
        print(screener.format_candidate_summary(candidate))
