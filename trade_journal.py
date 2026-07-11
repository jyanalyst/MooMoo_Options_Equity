"""
Trade Journaling System for Wheel Strategy with MooMoo CSV Import

A production-ready trade journal for tracking cash-secured put trades,
importing positions directly from MooMoo CSV exports, analyzing performance
by VIX regime, and validating exit discipline.

Statistical Assumptions:
- Win rate calculations assume independent trials (trades)
- Expectancy assumes normally distributed returns (verify with >30 trades)
- VIX regime classification uses fixed thresholds (may need adjustment)

Data Requirements:
- All monetary values in USD
- Dates in ISO format (YYYY-MM-DD)
- MooMoo CSV exports in standard format

Author: Quantitative Trading System
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Dict, List, Tuple, Any

import pandas as pd

# Optional imports for IV calculation
try:
    from iv_analyzer import IVAnalyzer

    IV_ANALYZER_AVAILABLE = True
except ImportError:
    IV_ANALYZER_AVAILABLE = False

try:
    from data_fetcher import get_data_fetcher

    DATA_FETCHER_AVAILABLE = True
except ImportError:
    DATA_FETCHER_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Account Configuration
TOTAL_CAPITAL: float = 44_500.0

# Exit Rule Categories
EXIT_REASONS = Literal[
    "50% profit", "21 DTE", "2x loss", "7 DTE", "assignment", "other"
]

VALID_EXIT_REASONS = ["50% profit", "21 DTE", "2x loss", "7 DTE", "assignment", "other"]

# Valid Sectors
VALID_SECTORS = [
    "Technology",
    "Healthcare",
    "Financials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Industrials",
    "Materials",
    "Real Estate",
    "Utilities",
    "Communication Services",
    "ETF",
]

# Sector shortcuts for quick input
SECTOR_SHORTCUTS = {
    "tech": "Technology",
    "health": "Healthcare",
    "fin": "Financials",
    "disc": "Consumer Discretionary",
    "staples": "Consumer Staples",
    "energy": "Energy",
    "ind": "Industrials",
    "mat": "Materials",
    "re": "Real Estate",
    "util": "Utilities",
    "comm": "Communication Services",
    "etf": "ETF",
}

# Data Schema - Extended for MooMoo import
JOURNAL_COLUMNS = [
    # Entry data
    "trade_id",
    "entry_date",
    "ticker",
    "strike",
    "expiry_date",
    "dte",
    "delta",
    "iv",
    "iv_rank",  # IV from CSV, IV Rank calculated from IV
    "vix",
    "premium",
    "capital_deployed",
    "sector",
    "quality_score",  # Quality score from universe.py (0-100)
    "position_size_pct",
    "vix_regime",
    "stock_price_at_entry",
    "notes",
    "moomoo_symbol",  # Original MooMoo symbol for matching
    # Live tracking (updated from CSV imports)
    "current_option_price",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "last_updated",
    # Exit data (empty until closed)
    "exit_date",
    "exit_reason",
    "pnl",
    "pnl_pct",
    "days_held",
    "status",
]

# Default file path
DEFAULT_JOURNAL_PATH = Path("journal_data.csv")


# =============================================================================
# VIX REGIME CLASSIFICATION
# =============================================================================


def classify_vix_regime(vix: float) -> str:
    """
    Classify VIX into trading regime categories.

    Thin wrapper: vix_monitor.get_regime is the SINGLE source of truth for
    the regime bands (STOP <14, CAUTIOUS 14-18, NORMAL 18-25, AGGRESSIVE >25).

    Args:
        vix: Current VIX value

    Returns:
        Regime classification string
    """
    from vix_monitor import get_regime

    return get_regime(vix)


# =============================================================================
# SECTOR LOOKUP FROM UNIVERSE.PY
# =============================================================================


def _parse_universe_sectors() -> Dict[str, str]:
    """
    Parse sector information from universe.py comments.

    Format in universe.py:
    "MSFT",  # Microsoft Corporation | Technology | $466 | ...

    Returns:
        Dictionary mapping ticker to sector
    """
    sectors = {}
    universe_path = Path(__file__).parent / "universe.py"

    if not universe_path.exists():
        logger.warning("universe.py not found - sector auto-detection disabled")
        return sectors

    try:
        with open(universe_path, "r") as f:
            content = f.read()

        # Pattern: "TICKER",  # Name | Sector | $Price | ...
        pattern = r'"([A-Z]+)",\s*#[^|]+\|\s*([^|]+)\s*\|'
        matches = re.findall(pattern, content)

        for ticker, sector in matches:
            sectors[ticker.strip()] = sector.strip()

        logger.debug(f"Parsed {len(sectors)} sectors from universe.py")

    except Exception as e:
        logger.warning(f"Error parsing universe.py for sectors: {e}")

    return sectors


# Cache sector lookup at module load
_UNIVERSE_SECTORS: Dict[str, str] = {}


def get_sector_from_universe(ticker: str) -> Optional[str]:
    """
    Look up sector for a ticker from universe.py.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Sector string or None if not found
    """
    global _UNIVERSE_SECTORS

    # Lazy load sectors
    if not _UNIVERSE_SECTORS:
        _UNIVERSE_SECTORS = _parse_universe_sectors()

    return _UNIVERSE_SECTORS.get(ticker.upper())


# =============================================================================
# QUALITY SCORE LOOKUP FROM UNIVERSE.PY
# =============================================================================


def _parse_universe_quality_scores() -> Dict[str, float]:
    """
    Parse quality scores from universe.py comments.

    Format in universe.py:
    "MSFT",  # Microsoft Corporation | Technology | $466 | Capital: $46.6K | Score: 75.2 | Earnings: ...

    Returns:
        Dictionary mapping ticker to quality score
    """
    scores = {}
    universe_path = Path(__file__).parent / "universe.py"

    if not universe_path.exists():
        logger.warning("universe.py not found - quality score lookup disabled")
        return scores

    try:
        with open(universe_path, "r") as f:
            content = f.read()

        # Pattern: "TICKER",  # ... | Score: XX.X | ...
        pattern = r'"([A-Z]+)",.*?Score:\s*(\d+\.?\d*)'
        matches = re.findall(pattern, content)

        for ticker, score in matches:
            scores[ticker.strip()] = float(score)

        logger.debug(f"Parsed {len(scores)} quality scores from universe.py")

    except Exception as e:
        logger.warning(f"Error parsing universe.py for quality scores: {e}")

    return scores


# Cache quality score lookup at module load
_UNIVERSE_QUALITY_SCORES: Dict[str, float] = {}


def get_quality_score_from_universe(ticker: str) -> Optional[float]:
    """
    Look up quality score for a ticker from universe.py.

    Quality scores are derived from fundamental analysis:
    - High Quality (70-100): Elite fundamentals
    - Medium Quality (50-70): Above average fundamentals
    - Low Quality (<50): Below universe standards

    Args:
        ticker: Stock ticker symbol

    Returns:
        Quality score (0-100) or None if not found
    """
    global _UNIVERSE_QUALITY_SCORES

    # Lazy load quality scores
    if not _UNIVERSE_QUALITY_SCORES:
        _UNIVERSE_QUALITY_SCORES = _parse_universe_quality_scores()

    return _UNIVERSE_QUALITY_SCORES.get(ticker.upper())


def classify_quality_bucket(score: Optional[float]) -> str:
    """
    Classify quality score into bucket categories.

    Args:
        score: Quality score (0-100) or None

    Returns:
        Bucket classification string
    """
    if score is None:
        return "Unknown"
    elif score >= 70:
        return "High"
    elif score >= 50:
        return "Medium"
    else:
        return "Low"


# =============================================================================
# MOOMOO SYMBOL PARSING
# =============================================================================


def parse_moomoo_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Parse MooMoo option symbol format into components.

    MooMoo format: TICKER + YYMMDD + P/C + STRIKE (in cents/10)
    Examples:
        - "A260220P130000" -> A, 2026-02-20, Put, 130.00
        - "ANET260220P120000" -> ANET, 2026-02-20, Put, 120.00
        - "MSFT260117C400000" -> MSFT, 2026-01-17, Call, 400.00

    Args:
        symbol: MooMoo option symbol string

    Returns:
        Dictionary with ticker, expiry_date, option_type, strike
        or None if parsing fails
    """
    # Skip complex spreads (contain "/")
    if "/" in symbol:
        logger.debug(f"Skipping spread symbol: {symbol}")
        return None

    # Pattern: 1-5 letter ticker + 6 digit date + P or C + strike
    # Strike is in format where 130000 = $130.00
    pattern = r"^([A-Z]{1,5})(\d{6})([PC])(\d+)$"
    match = re.match(pattern, symbol.upper())

    if not match:
        logger.warning(f"Could not parse symbol: {symbol}")
        return None

    ticker = match.group(1)
    date_str = match.group(2)  # YYMMDD
    option_type = "Put" if match.group(3) == "P" else "Call"
    strike_raw = int(match.group(4))

    # Parse date (YYMMDD -> datetime)
    try:
        year = 2000 + int(date_str[0:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry_date = datetime(year, month, day)
    except ValueError as e:
        logger.warning(f"Invalid date in symbol {symbol}: {e}")
        return None

    # Convert strike: 130000 -> 130.00, 7500 -> 7.50
    # MooMoo uses strike * 1000 format
    strike = strike_raw / 1000.0

    return {
        "ticker": ticker,
        "expiry_date": expiry_date,
        "option_type": option_type,
        "strike": strike,
        "moomoo_symbol": symbol.upper(),
    }


def parse_moomoo_value(value: str) -> float:
    """
    Parse MooMoo formatted value strings to float.

    Handles formats like:
    - "+10.00%" -> 10.00
    - "-29.87%" -> -29.87
    - "$1,234.56" -> 1234.56
    - "1.58" -> 1.58

    Args:
        value: String value from MooMoo CSV

    Returns:
        Float value
    """
    if pd.isna(value) or value == "" or value == "--":
        return 0.0

    # Convert to string if not already
    value_str = str(value)

    # Remove common formatting characters
    cleaned = (
        value_str.replace("$", "").replace(",", "").replace("%", "").replace("+", "")
    )

    try:
        return float(cleaned)
    except ValueError:
        logger.warning(f"Could not parse value: {value}")
        return 0.0


# =============================================================================
# TRADE JOURNAL CLASS
# =============================================================================


class TradeJournal:
    """
    Trade journaling system for Wheel Strategy options trading.

    Supports direct import from MooMoo CSV position exports.
    Tracks trade entries, exits, and provides performance analytics
    segmented by VIX regime and exit reason.

    Attributes:
        journal_path: Path to CSV file for persistence
        df: DataFrame containing all trade records
        total_capital: Account capital for position sizing calculations

    Example:
        >>> journal = TradeJournal()
        >>> journal.import_from_moomoo("Positions-2026-01-22.csv")
        >>> journal.show_open_positions()
        >>> journal.show_stats()
    """

    def __init__(
        self,
        journal_path: Path = DEFAULT_JOURNAL_PATH,
        total_capital: float = TOTAL_CAPITAL,
        data_fetcher: Any = None,
    ) -> None:
        """
        Initialize the trade journal.

        Args:
            journal_path: Path to CSV file for data persistence
            total_capital: Account capital for position sizing (default: $44,500)
            data_fetcher: Optional data fetcher for IV Rank calculations.
                         If not provided, will create one automatically if available.
        """
        self.journal_path = Path(journal_path)
        self.total_capital = total_capital
        self.data_fetcher = data_fetcher
        self.iv_analyzer = None

        # Initialize IV Analyzer if data_fetcher available
        if data_fetcher is not None and IV_ANALYZER_AVAILABLE:
            self.iv_analyzer = IVAnalyzer(data_fetcher)
            logger.info("IV Analyzer initialized for auto IV Rank calculation")
        elif data_fetcher is None and IV_ANALYZER_AVAILABLE and DATA_FETCHER_AVAILABLE:
            # Auto-create data fetcher
            try:
                self.data_fetcher = get_data_fetcher(use_mock=False)
                self.iv_analyzer = IVAnalyzer(self.data_fetcher)
                logger.info("Auto-created data fetcher and IV Analyzer")
            except Exception as e:
                logger.warning(f"Could not auto-create data fetcher: {e}")
        else:
            logger.warning(
                "IV Analyzer not available - IV Rank must be entered manually"
            )

        self.df = self._load_or_create_journal()
        logger.info(f"TradeJournal initialized with {len(self.df)} existing trades")

    def _load_or_create_journal(self) -> pd.DataFrame:
        """Load existing journal or create new empty DataFrame."""
        if self.journal_path.exists():
            try:
                df = pd.read_csv(
                    self.journal_path,
                    parse_dates=[
                        "entry_date",
                        "exit_date",
                        "expiry_date",
                        "last_updated",
                    ],
                )
                logger.info(f"Loaded journal from {self.journal_path}")
                return df
            except Exception as e:
                logger.error(f"Error loading journal: {e}. Creating new journal.")

        # Create empty DataFrame with explicit dtypes
        return pd.DataFrame(
            {
                "trade_id": pd.Series(dtype="int64"),
                "entry_date": pd.Series(dtype="object"),
                "ticker": pd.Series(dtype="str"),
                "strike": pd.Series(dtype="float64"),
                "expiry_date": pd.Series(dtype="object"),
                "dte": pd.Series(dtype="int64"),
                "delta": pd.Series(dtype="float64"),
                "iv": pd.Series(dtype="float64"),  # Current IV from MooMoo CSV
                "iv_rank": pd.Series(dtype="float64"),  # Calculated IV Rank
                "vix": pd.Series(dtype="float64"),
                "premium": pd.Series(dtype="float64"),
                "capital_deployed": pd.Series(dtype="float64"),
                "sector": pd.Series(dtype="str"),
                "quality_score": pd.Series(
                    dtype="float64"
                ),  # Quality score from universe.py
                "position_size_pct": pd.Series(dtype="float64"),
                "vix_regime": pd.Series(dtype="str"),
                "stock_price_at_entry": pd.Series(dtype="float64"),
                "notes": pd.Series(dtype="str"),
                "moomoo_symbol": pd.Series(dtype="str"),
                "current_option_price": pd.Series(dtype="float64"),
                "unrealized_pnl": pd.Series(dtype="float64"),
                "unrealized_pnl_pct": pd.Series(dtype="float64"),
                "last_updated": pd.Series(dtype="object"),
                "exit_date": pd.Series(dtype="object"),
                "exit_reason": pd.Series(dtype="str"),
                "pnl": pd.Series(dtype="float64"),
                "pnl_pct": pd.Series(dtype="float64"),
                "days_held": pd.Series(dtype="float64"),
                "status": pd.Series(dtype="str"),
            }
        )

    def _save_journal(self) -> None:
        """Persist journal to CSV file."""
        self.df.to_csv(self.journal_path, index=False)
        logger.debug(f"Journal saved to {self.journal_path}")

    def _get_next_trade_id(self) -> int:
        """Generate next sequential trade ID."""
        if self.df.empty:
            return 1
        return int(self.df["trade_id"].max()) + 1

    # =========================================================================
    # SPREAD DETECTION
    # =========================================================================

    def _detect_spread_legs(self, moomoo_df: pd.DataFrame) -> set:
        """
        Identify spread legs by finding paired long/short positions.

        A spread consists of:
        - Same underlying ticker
        - Same expiration date
        - Same option type (both puts or both calls)
        - Different strikes
        - One long (+1) and one short (-1) position

        Args:
            moomoo_df: DataFrame of positions from MooMoo CSV

        Returns:
            Set of symbols that are spread legs (to skip)
        """
        spread_legs = set()
        parsed_positions = []

        # First pass: Parse all positions and mark explicit spreads
        for idx, row in moomoo_df.iterrows():
            symbol = str(row["Symbol"]).strip().strip('"')
            quantity = int(row["Quantity"])

            # Explicit spread symbols (contain "/")
            if "/" in symbol:
                spread_legs.add(symbol)
                print(f"  [SPREAD] {symbol} - Spread summary line (contains '/')")
                continue

            # Try to parse the symbol
            parsed = parse_moomoo_symbol(symbol)
            if parsed:
                parsed_positions.append(
                    {
                        "symbol": symbol,
                        "ticker": parsed["ticker"],
                        "expiry": parsed["expiry_date"],
                        "option_type": parsed["option_type"],
                        "strike": parsed["strike"],
                        "quantity": quantity,
                    }
                )

        # Second pass: Find paired positions (same ticker/expiry/type, different strikes, opposite qty)
        for i, pos1 in enumerate(parsed_positions):
            if pos1["symbol"] in spread_legs:
                continue

            for pos2 in parsed_positions[i + 1 :]:
                if pos2["symbol"] in spread_legs:
                    continue

                # Check if these form a spread pair
                is_spread_pair = (
                    pos1["ticker"] == pos2["ticker"]
                    and pos1["expiry"] == pos2["expiry"]
                    and pos1["option_type"] == pos2["option_type"]
                    and pos1["strike"] != pos2["strike"]
                    and pos1["quantity"] + pos2["quantity"] == 0  # Opposite quantities
                )

                if is_spread_pair:
                    spread_legs.add(pos1["symbol"])
                    spread_legs.add(pos2["symbol"])
                    strikes = sorted([pos1["strike"], pos2["strike"]])
                    print(
                        f"  [SPREAD] {pos1['ticker']} {pos1['expiry'].strftime('%y%m%d')} "
                        f"${strikes[0]}/${strikes[1]} {pos1['option_type']} spread detected"
                    )

        return spread_legs

    # =========================================================================
    # MOOMOO CSV IMPORT
    # =========================================================================

    def import_from_moomoo(
        self, csv_path: str, vix: Optional[float] = None, interactive: bool = True
    ) -> Dict[str, List[str]]:
        """
        Import positions from MooMoo CSV export.

        Parses the CSV, identifies new positions, detects closed positions,
        and updates live P/L for existing positions.

        Args:
            csv_path: Path to MooMoo positions CSV file
            vix: Current VIX value (required for new positions)
            interactive: If True, prompts for missing data (IV rank, sector)

        Returns:
            Dictionary with 'new', 'updated', 'closed' lists of symbols

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        print(f"\n{'=' * 60}")
        print(f"IMPORTING FROM: {csv_path.name}")
        print(f"{'=' * 60}")

        # Load MooMoo CSV
        try:
            moomoo_df = pd.read_csv(csv_path)
        except Exception as e:
            raise ValueError(f"Error reading CSV: {e}")

        # Validate required columns
        required_cols = [
            "Symbol",
            "Quantity",
            "Average Cost",
            "Current price",
            "Unrealized P/L",
            "% Unrealized P/L",
        ]
        missing_cols = [c for c in required_cols if c not in moomoo_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Detect spread positions before processing
        print(f"\n{'-' * 40}")
        print("SPREAD DETECTION")
        print(f"{'-' * 40}")
        spread_legs = self._detect_spread_legs(moomoo_df)
        if spread_legs:
            print(f"  Found {len(spread_legs)} spread-related positions to skip")
        else:
            print("  No spreads detected - all positions are naked")

        results = {"new": [], "updated": [], "closed": [], "skipped_spreads": []}

        # Parse each position
        current_symbols = set()
        positions_to_add = []

        for _, row in moomoo_df.iterrows():
            symbol = str(row["Symbol"]).strip().strip('"')
            quantity = int(row["Quantity"])

            # Skip spread legs
            if symbol in spread_legs:
                results["skipped_spreads"].append(symbol)
                continue

            # Skip non-short puts (long positions, quantity >= 0)
            if quantity >= 0:
                continue  # Only process short positions (sold puts)

            # Parse symbol
            parsed = parse_moomoo_symbol(symbol)
            if not parsed:
                continue

            # Only process puts
            if parsed["option_type"] != "Put":
                continue

            current_symbols.add(parsed["moomoo_symbol"])

            # Extract position data
            avg_cost = parse_moomoo_value(row["Average Cost"])
            current_price = parse_moomoo_value(row["Current price"])
            unrealized_pnl = parse_moomoo_value(row["Unrealized P/L"])
            unrealized_pnl_pct = parse_moomoo_value(row["% Unrealized P/L"])

            # Get delta if available
            delta = 0.0
            if "Delta" in moomoo_df.columns:
                delta = parse_moomoo_value(row["Delta"])

            # Get IV (implied volatility) if available
            # MooMoo column: "IV (options only)" - value is decimal (e.g., 0.2952 = 29.52%)
            current_iv = None
            for iv_col in ["IV (options only)", "IV", "Implied Volatility"]:
                if iv_col in moomoo_df.columns:
                    iv_val = row[iv_col]
                    if pd.notna(iv_val) and str(iv_val) != "" and str(iv_val) != "--":
                        current_iv = parse_moomoo_value(iv_val)
                        break

            # Get margin/capital deployed
            capital_deployed = parsed["strike"] * 100 * abs(quantity)
            if "Initial Margin" in moomoo_df.columns:
                margin = parse_moomoo_value(row["Initial Margin"])
                if margin > 0:
                    capital_deployed = margin

            # Calculate premium (avg cost * 100 per contract * quantity)
            premium = avg_cost * 100 * abs(quantity)

            # Calculate DTE
            today = datetime.now()
            dte = (parsed["expiry_date"] - today).days

            position_data = {
                "moomoo_symbol": parsed["moomoo_symbol"],
                "ticker": parsed["ticker"],
                "strike": parsed["strike"],
                "expiry_date": parsed["expiry_date"],
                "dte": dte,
                "delta": delta,
                "current_iv": current_iv,  # IV from CSV for IV Rank calculation
                "premium": premium,
                "capital_deployed": capital_deployed,
                "current_option_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct,
            }

            # Check if position exists in journal
            existing = self.df[
                (self.df["moomoo_symbol"] == parsed["moomoo_symbol"])
                & (self.df["status"] == "OPEN")
            ]

            if existing.empty:
                # New position
                positions_to_add.append(position_data)
            else:
                # Update existing position
                self._update_position_from_csv(parsed["moomoo_symbol"], position_data)
                results["updated"].append(
                    f"{parsed['ticker']} {parsed['expiry_date'].strftime('%y%m%d')} ${parsed['strike']}P"
                )

        # Detect closed positions (in journal but not in CSV)
        open_positions = self.df[self.df["status"] == "OPEN"]
        for _, trade in open_positions.iterrows():
            if (
                pd.notna(trade["moomoo_symbol"])
                and trade["moomoo_symbol"] not in current_symbols
            ):
                results["closed"].append(trade["moomoo_symbol"])

        # Process closed positions
        if results["closed"] and interactive:
            print(f"\n{'-' * 40}")
            print("CLOSED POSITIONS DETECTED")
            print(f"{'-' * 40}")
            for symbol in results["closed"]:
                self._process_closed_position(symbol)

        # Process new positions
        if positions_to_add:
            print(f"\n{'-' * 40}")
            print(f"NEW POSITIONS FOUND: {len(positions_to_add)}")
            print(f"{'-' * 40}")

            # Get VIX if not provided
            if vix is None and interactive:
                vix = self._prompt_for_vix()
            elif vix is None:
                vix = 18.0  # Default to normal regime
                logger.warning("VIX not provided, defaulting to 18.0")

            for pos_data in positions_to_add:
                if interactive:
                    self._add_position_interactive(pos_data, vix)
                else:
                    self._add_position_default(pos_data, vix)
                results["new"].append(
                    f"{pos_data['ticker']} {pos_data['expiry_date'].strftime('%y%m%d')} ${pos_data['strike']}P"
                )

        # Save changes
        self._save_journal()

        # Print summary
        print(f"\n{'=' * 60}")
        print("IMPORT SUMMARY")
        print(f"{'=' * 60}")
        print(f"  New positions:     {len(results['new'])}")
        print(f"  Updated positions: {len(results['updated'])}")
        print(f"  Closed positions:  {len(results['closed'])}")
        if results["skipped_spreads"]:
            print(f"  Skipped spreads:   {len(results['skipped_spreads'])}")

        # Capital validation warning
        open_trades = self.df[self.df["status"] == "OPEN"]
        if not open_trades.empty:
            total_capital_deployed = open_trades["capital_deployed"].sum()
            capital_pct = (total_capital_deployed / self.total_capital) * 100
            if capital_pct > 100:
                print(f"\n  [WARN] Capital deployed ({capital_pct:.1f}%) exceeds 100%")
                print("         This may indicate spreads were not properly filtered.")
                print("         Check journal entries and delete if needed.")

        print(f"{'=' * 60}\n")

        return results

    def _calculate_iv_rank(
        self, ticker: str, current_iv: float
    ) -> Tuple[Optional[float], str]:
        """
        Calculate IV Rank automatically using IVAnalyzer.

        Args:
            ticker: Stock ticker
            current_iv: Current IV as decimal (e.g., 0.2952 for 29.52%)

        Returns:
            Tuple of (iv_rank, status_message)
            iv_rank is None if calculation failed
        """
        if self.iv_analyzer is None:
            return None, "IV Analyzer not available"

        try:
            iv_rank = self.iv_analyzer.calculate_iv_rank(ticker, current_iv)

            if iv_rank is not None:
                return (
                    iv_rank,
                    f"IV Rank {iv_rank:.1f}% (from IV {current_iv * 100:.2f}%)",
                )
            else:
                return None, "Could not calculate IV Rank - no historical data"

        except Exception as e:
            logger.warning(f"IV Rank calculation error for {ticker}: {e}")
            return None, f"Calculation error: {e}"

    def _prompt_for_vix(self) -> float:
        """Prompt user for current VIX value."""
        while True:
            try:
                vix_input = input("\nEnter current VIX value: ").strip()
                vix = float(vix_input)
                if vix < 0 or vix > 100:
                    print("  VIX should be between 0 and 100")
                    continue
                regime = classify_vix_regime(vix)
                print(f"  VIX Regime: {regime}")
                return vix
            except ValueError:
                print("  Invalid input. Please enter a number.")

    def _prompt_for_iv_rank(self, ticker: str) -> float:
        """Prompt user for IV rank."""
        while True:
            try:
                iv_input = input(f"  Enter IV Rank for {ticker} (0-100): ").strip()
                iv_rank = float(iv_input)
                if iv_rank < 0 or iv_rank > 100:
                    print("    IV Rank must be 0-100")
                    continue
                return iv_rank
            except ValueError:
                print("    Invalid input. Please enter a number.")

    def _prompt_for_sector(self, ticker: str) -> str:
        """Prompt user for sector."""
        print(f"  Select sector for {ticker}:")
        print(f"    Shortcuts: {', '.join(SECTOR_SHORTCUTS.keys())}")
        print(f"    Full names: {', '.join(VALID_SECTORS)}")

        while True:
            sector_input = input("  Sector: ").strip().lower()

            # Check shortcuts
            if sector_input in SECTOR_SHORTCUTS:
                return SECTOR_SHORTCUTS[sector_input]

            # Check full names (case-insensitive)
            for s in VALID_SECTORS:
                if sector_input == s.lower():
                    return s

            print("    Unknown sector. Use a shortcut or full name.")

    def _prompt_for_exit_reason(self, symbol: str, ticker: str) -> str:
        """Prompt user for exit reason."""
        print(f"\n  Position closed: {ticker}")
        print(f"    Exit reasons: {', '.join(VALID_EXIT_REASONS)}")

        while True:
            reason = input("  Exit reason: ").strip()
            if reason in VALID_EXIT_REASONS:
                return reason
            # Partial match
            matches = [r for r in VALID_EXIT_REASONS if reason.lower() in r.lower()]
            if len(matches) == 1:
                return matches[0]
            print(f"    Invalid. Choose from: {', '.join(VALID_EXIT_REASONS)}")

    def _add_position_interactive(self, pos_data: Dict, vix: float) -> int:
        """Add a new position with interactive prompts for missing data."""
        ticker = pos_data["ticker"]
        strike = pos_data["strike"]
        expiry = pos_data["expiry_date"].strftime("%Y-%m-%d")

        print(f"\n  NEW: {ticker} ${strike}P exp {expiry}")
        print(
            f"    Premium: ${pos_data['premium']:.2f} | DTE: {pos_data['dte']} | Delta: {pos_data['delta']:.2f}"
        )

        # AUTO-CALCULATE IV Rank from CSV IV data
        iv_rank = None
        current_iv = pos_data.get("current_iv")

        if current_iv is not None and current_iv > 0:
            print(f"    Current IV: {current_iv * 100:.2f}%")
            iv_rank, iv_status = self._calculate_iv_rank(ticker, current_iv)

            if iv_rank is not None:
                print(f"    [AUTO] {iv_status}")

                # Warning if IV Rank is below threshold
                if iv_rank < 50:
                    print(f"    [WARN] IV Rank {iv_rank:.1f}% is below 50% threshold")
            else:
                print(f"    [WARN] {iv_status}")
        else:
            print("    [WARN] No IV data in CSV - manual entry required")

        # Fallback to manual entry if auto-calculation failed
        if iv_rank is None:
            while True:
                iv_input = input(
                    f"    Enter IV Rank for {ticker} (0-100, or Enter to skip): "
                ).strip()
                if iv_input == "":
                    print("    [WARN] IV Rank skipped - update manually later")
                    break
                try:
                    iv_rank = float(iv_input)
                    if 0 <= iv_rank <= 100:
                        break
                    print("      IV Rank must be 0-100")
                except ValueError:
                    print("      Invalid input. Enter a number or press Enter to skip.")

        # AUTO-DETECT sector from universe.py; off-universe names are manual
        sector = get_sector_from_universe(ticker)
        if sector:
            print(f"    [AUTO] Sector: {sector} (from universe.py)")
        else:
            print("    [INFO] Sector not in universe.py - manual entry required")
            sector = self._prompt_for_sector(ticker)

        # AUTO-DETECT quality score from universe.py (off-universe names have none)
        quality_score = get_quality_score_from_universe(ticker)
        if quality_score is not None:
            quality_bucket = classify_quality_bucket(quality_score)
            print(
                f"    [AUTO] Quality Score: {quality_score:.1f} ({quality_bucket}) (from universe.py)"
            )
            if quality_score < 50:
                print("    [WARN] Low quality stock - consider position size carefully")
        else:
            print(
                "    [INFO] Quality Score: N/A (not in universe.py - off-universe trade)"
            )

        notes = input("  Notes (optional): ").strip()

        return self._create_trade_entry(
            pos_data, vix, iv_rank, sector, notes, quality_score
        )

    def _add_position_default(self, pos_data: Dict, vix: float) -> int:
        """Add a new position with default values (non-interactive mode)."""
        ticker = pos_data["ticker"]

        # Try auto-calculating IV Rank
        iv_rank = None
        current_iv = pos_data.get("current_iv")
        if current_iv is not None and current_iv > 0:
            iv_rank, _ = self._calculate_iv_rank(ticker, current_iv)

        # Fallback to default if calculation failed
        if iv_rank is None:
            iv_rank = 50.0
            logger.warning(f"IV Rank defaulted to 50.0 for {ticker}")

        # Auto-detect sector from universe.py (off-universe => Unknown)
        sector = get_sector_from_universe(ticker)
        if sector is None:
            sector = "Unknown"
            logger.warning(f"Sector defaulted to Unknown for {ticker}")

        # Quality score comes from universe.py only (None for off-universe names)
        quality_score = get_quality_score_from_universe(ticker)

        return self._create_trade_entry(
            pos_data,
            vix,
            iv_rank=iv_rank,
            sector=sector,
            notes="Auto-imported",
            quality_score=quality_score,
        )

    def _create_trade_entry(
        self,
        pos_data: Dict,
        vix: float,
        iv_rank: Optional[float],
        sector: str,
        notes: str,
        quality_score: Optional[float] = None,
    ) -> int:
        """Create a new trade entry in the journal."""
        trade_id = self._get_next_trade_id()
        vix_regime = classify_vix_regime(vix)
        position_size_pct = (pos_data["capital_deployed"] / self.total_capital) * 100

        # Extract IV from position data (stored for reference)
        current_iv = pos_data.get("current_iv")

        # Auto-lookup quality score if not provided
        ticker = pos_data["ticker"]
        if quality_score is None:
            quality_score = get_quality_score_from_universe(ticker)

        new_trade = {
            "trade_id": trade_id,
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": ticker,
            "strike": pos_data["strike"],
            "expiry_date": pos_data["expiry_date"].strftime("%Y-%m-%d"),
            "dte": pos_data["dte"],
            "delta": pos_data["delta"],
            "iv": current_iv,  # Store raw IV from CSV
            "iv_rank": iv_rank,  # Calculated IV Rank
            "vix": vix,
            "premium": pos_data["premium"],
            "capital_deployed": pos_data["capital_deployed"],
            "sector": sector,
            "quality_score": quality_score,  # Quality score from universe.py
            "position_size_pct": round(position_size_pct, 2),
            "vix_regime": vix_regime,
            "stock_price_at_entry": None,  # Not available from options CSV
            "notes": notes,
            "moomoo_symbol": pos_data["moomoo_symbol"],
            "current_option_price": pos_data["current_option_price"],
            "unrealized_pnl": pos_data["unrealized_pnl"],
            "unrealized_pnl_pct": pos_data["unrealized_pnl_pct"],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "exit_date": None,
            "exit_reason": None,
            "pnl": None,
            "pnl_pct": None,
            "days_held": None,
            "status": "OPEN",
        }

        self.df = pd.concat([self.df, pd.DataFrame([new_trade])], ignore_index=True)

        logger.info(
            f"Trade #{trade_id} OPENED: {pos_data['ticker']} ${pos_data['strike']}P | "
            f"DTE: {pos_data['dte']} | Premium: ${pos_data['premium']:.2f} | "
            f"VIX Regime: {vix_regime}"
        )

        return trade_id

    def _update_position_from_csv(self, moomoo_symbol: str, pos_data: Dict) -> None:
        """Update existing position with latest data from CSV."""
        mask = (self.df["moomoo_symbol"] == moomoo_symbol) & (
            self.df["status"] == "OPEN"
        )

        self.df.loc[mask, "current_option_price"] = pos_data["current_option_price"]
        self.df.loc[mask, "unrealized_pnl"] = pos_data["unrealized_pnl"]
        self.df.loc[mask, "unrealized_pnl_pct"] = pos_data["unrealized_pnl_pct"]
        self.df.loc[mask, "dte"] = pos_data["dte"]
        self.df.loc[mask, "delta"] = pos_data["delta"]
        self.df.loc[mask, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _process_closed_position(self, moomoo_symbol: str) -> None:
        """Process a position that was closed (not in current CSV)."""
        mask = (self.df["moomoo_symbol"] == moomoo_symbol) & (
            self.df["status"] == "OPEN"
        )
        trade = self.df.loc[mask].iloc[0]

        ticker = trade["ticker"]
        strike = trade["strike"]
        premium = trade["premium"]

        # Get exit reason from user
        exit_reason = self._prompt_for_exit_reason(
            moomoo_symbol, f"{ticker} ${strike}P"
        )

        # Calculate P&L (use last known unrealized P&L as final)
        # For more accuracy, user could input actual closing P&L
        pnl = trade["unrealized_pnl"] if pd.notna(trade["unrealized_pnl"]) else 0

        # Allow override
        pnl_input = input(f"  Final P&L (press Enter for ${pnl:.2f}): ").strip()
        if pnl_input:
            try:
                pnl = float(pnl_input)
            except ValueError:
                pass

        # Calculate metrics
        pnl_pct = (pnl / premium) * 100 if premium > 0 else 0
        entry_date = pd.to_datetime(trade["entry_date"])
        days_held = (datetime.now() - entry_date).days

        # Update record
        self.df.loc[mask, "exit_date"] = datetime.now().strftime("%Y-%m-%d")
        self.df.loc[mask, "exit_reason"] = exit_reason
        self.df.loc[mask, "pnl"] = pnl
        self.df.loc[mask, "pnl_pct"] = round(pnl_pct, 2)
        self.df.loc[mask, "days_held"] = days_held
        self.df.loc[mask, "status"] = "CLOSED"

        outcome = "WIN" if pnl > 0 else "LOSS"
        print(f"    {outcome}: P&L ${pnl:.2f} ({pnl_pct:+.1f}%) | Days: {days_held}")

        logger.info(
            f"Trade CLOSED: {ticker} ${strike}P | {outcome} | "
            f"P&L: ${pnl:.2f} ({pnl_pct:+.1f}%) | Exit: {exit_reason}"
        )

    # =========================================================================
    # PERFORMANCE ANALYTICS
    # =========================================================================

    def show_stats(self) -> None:
        """Display comprehensive performance dashboard."""
        closed = self.df[self.df["status"] == "CLOSED"].copy()

        if closed.empty:
            print("\n" + "=" * 60)
            print("TRADE JOURNAL - PERFORMANCE DASHBOARD")
            print("=" * 60)
            print("\n[!] No closed trades to analyze yet.\n")
            return

        print("\n" + "=" * 60)
        print("TRADE JOURNAL - PERFORMANCE DASHBOARD")
        print("=" * 60)

        # Overall metrics
        total_trades = len(closed)
        winners = closed[closed["pnl"] > 0]
        losers = closed[closed["pnl"] <= 0]

        win_rate = len(winners) / total_trades * 100
        avg_win = winners["pnl"].mean() if len(winners) > 0 else 0
        avg_loss = abs(losers["pnl"].mean()) if len(losers) > 0 else 0
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

        total_pnl = closed["pnl"].sum()
        total_return_pct = (total_pnl / self.total_capital) * 100

        print(f"\n{'-' * 40}")
        print("OVERALL PERFORMANCE")
        print(f"{'-' * 40}")
        print(f"  Total Trades:      {total_trades}")
        print(f"  Win Rate:          {win_rate:.1f}%")
        print(f"  Avg Win:           ${avg_win:.2f}")
        print(f"  Avg Loss:          ${avg_loss:.2f}")
        print(
            f"  Win/Loss Ratio:    {avg_win / avg_loss:.2f}x"
            if avg_loss > 0
            else "  Win/Loss Ratio:    N/A"
        )
        print(f"  Expectancy:        ${expectancy:.2f} per trade")
        print(f"  Total P&L:         ${total_pnl:,.2f}")
        print(f"  Return on Capital: {total_return_pct:+.2f}%")

        # VIX Regime Analysis
        print(f"\n{'-' * 40}")
        print("PERFORMANCE BY VIX REGIME")
        print(f"{'-' * 40}")

        for regime in ["STOP", "CAUTIOUS", "NORMAL", "AGGRESSIVE"]:
            regime_trades = closed[closed["vix_regime"] == regime]
            if len(regime_trades) > 0:
                regime_wins = len(regime_trades[regime_trades["pnl"] > 0])
                regime_wr = regime_wins / len(regime_trades) * 100
                regime_pnl = regime_trades["pnl"].sum()
                marker = (
                    "[X]"
                    if regime == "STOP"
                    else "[!]"
                    if regime == "CAUTIOUS"
                    else "[+]"
                    if regime == "NORMAL"
                    else "[*]"
                )
                print(
                    f"  {marker} {regime:12} | Trades: {len(regime_trades):3} | "
                    f"Win Rate: {regime_wr:5.1f}% | P&L: ${regime_pnl:>8,.2f}"
                )
            else:
                print(f"      {regime:12} | No trades")

        # Exit Reason Analysis
        print(f"\n{'-' * 40}")
        print("EXIT REASON ANALYSIS")
        print(f"{'-' * 40}")

        for reason in closed["exit_reason"].dropna().unique():
            reason_trades = closed[closed["exit_reason"] == reason]
            reason_wins = len(reason_trades[reason_trades["pnl"] > 0])
            reason_wr = reason_wins / len(reason_trades) * 100
            reason_pnl = reason_trades["pnl"].sum()
            avg_days = reason_trades["days_held"].mean()
            print(
                f"  {reason:12} | Trades: {len(reason_trades):3} | "
                f"Win Rate: {reason_wr:5.1f}% | P&L: ${reason_pnl:>8,.2f} | "
                f"Avg Days: {avg_days:.0f}"
            )

        # Sector Attribution
        print(f"\n{'-' * 40}")
        print("SECTOR ATTRIBUTION")
        print(f"{'-' * 40}")

        sector_stats = (
            closed.groupby("sector")
            .agg({"trade_id": "count", "pnl": "sum"})
            .sort_values("pnl", ascending=False)
        )

        for sector in sector_stats.index:
            sector_trades = closed[closed["sector"] == sector]
            sector_wins = len(sector_trades[sector_trades["pnl"] > 0])
            sector_wr = (
                sector_wins / len(sector_trades) * 100 if len(sector_trades) > 0 else 0
            )
            sector_pnl = sector_trades["pnl"].sum()
            print(
                f"  {sector:22} | Trades: {len(sector_trades):3} | "
                f"Win Rate: {sector_wr:5.1f}% | P&L: ${sector_pnl:>8,.2f}"
            )

        # IV Rank Analysis
        print(f"\n{'-' * 40}")
        print("IV RANK ANALYSIS")
        print(f"{'-' * 40}")

        # Filter trades with IV Rank data
        iv_rank_trades = closed[closed["iv_rank"].notna()].copy()

        if len(iv_rank_trades) > 0:
            # Bucket analysis: <50, 50-70, >70
            iv_rank_trades["iv_bucket"] = pd.cut(
                iv_rank_trades["iv_rank"],
                bins=[0, 50, 70, 200],
                labels=["<50 (Low)", "50-70 (Medium)", ">70 (High)"],
            )

            for bucket in ["<50 (Low)", "50-70 (Medium)", ">70 (High)"]:
                bucket_trades = iv_rank_trades[iv_rank_trades["iv_bucket"] == bucket]
                if len(bucket_trades) > 0:
                    bucket_wins = len(bucket_trades[bucket_trades["pnl"] > 0])
                    bucket_wr = bucket_wins / len(bucket_trades) * 100
                    bucket_pnl = bucket_trades["pnl"].sum()

                    # Warning for low IV Rank trades
                    warning = ""
                    if bucket == "<50 (Low)":
                        warning = " [WARN: Below recommended]"

                    print(
                        f"  IV Rank {bucket:14} | Trades: {len(bucket_trades):3} | "
                        f"Win Rate: {bucket_wr:5.1f}% | P&L: ${bucket_pnl:>8,.2f}{warning}"
                    )
                else:
                    print(f"  IV Rank {bucket:14} | No trades")

            # Summary stats
            avg_iv_rank_all = iv_rank_trades["iv_rank"].mean()
            winning_iv_rank = (
                iv_rank_trades[iv_rank_trades["pnl"] > 0]["iv_rank"].mean()
                if len(iv_rank_trades[iv_rank_trades["pnl"] > 0]) > 0
                else 0
            )
            losing_iv_rank = (
                iv_rank_trades[iv_rank_trades["pnl"] <= 0]["iv_rank"].mean()
                if len(iv_rank_trades[iv_rank_trades["pnl"] <= 0]) > 0
                else 0
            )

            print(f"\n  Avg IV Rank (all trades): {avg_iv_rank_all:.1f}%")
            print(f"  Avg IV Rank (winners):    {winning_iv_rank:.1f}%")
            print(f"  Avg IV Rank (losers):     {losing_iv_rank:.1f}%")
        else:
            print("  No trades with IV Rank data")

        # Quality Score Analysis
        print(f"\n{'-' * 40}")
        print("QUALITY SCORE ANALYSIS")
        print(f"{'-' * 40}")

        # Filter trades - separate known quality scores from unknown
        quality_known = closed[closed["quality_score"].notna()].copy()
        quality_unknown = closed[closed["quality_score"].isna()]

        if len(quality_known) > 0:
            # Bucket analysis: High (>=70), Medium (50-70), Low (<50)
            quality_known["quality_bucket"] = quality_known["quality_score"].apply(
                lambda x: (
                    "High (70-100)"
                    if x >= 70
                    else ("Medium (50-70)" if x >= 50 else "Low (<50)")
                )
            )

            for bucket in ["High (70-100)", "Medium (50-70)", "Low (<50)"]:
                bucket_trades = quality_known[quality_known["quality_bucket"] == bucket]
                if len(bucket_trades) > 0:
                    bucket_wins = len(bucket_trades[bucket_trades["pnl"] > 0])
                    bucket_wr = bucket_wins / len(bucket_trades) * 100
                    bucket_pnl = bucket_trades["pnl"].sum()

                    # Warning for low quality trades
                    warning = ""
                    if bucket == "Low (<50)":
                        warning = " [WARN: Below threshold]"

                    print(
                        f"  Quality {bucket:14} | Trades: {len(bucket_trades):3} | "
                        f"Win Rate: {bucket_wr:5.1f}% | P&L: ${bucket_pnl:>8,.2f}{warning}"
                    )
                else:
                    print(f"  Quality {bucket:14} | No trades")

            # Summary stats
            avg_quality_all = quality_known["quality_score"].mean()
            winning_quality = (
                quality_known[quality_known["pnl"] > 0]["quality_score"].mean()
                if len(quality_known[quality_known["pnl"] > 0]) > 0
                else 0
            )
            losing_quality = (
                quality_known[quality_known["pnl"] <= 0]["quality_score"].mean()
                if len(quality_known[quality_known["pnl"] <= 0]) > 0
                else 0
            )

            print(f"\n  Avg Quality (all trades): {avg_quality_all:.1f}")
            print(f"  Avg Quality (winners):    {winning_quality:.1f}")
            print(f"  Avg Quality (losers):     {losing_quality:.1f}")

            # Quality vs returns insight
            if winning_quality > losing_quality:
                print("\n  [+] Higher quality stocks outperforming")
            elif losing_quality > winning_quality:
                print("\n  [!] Lower quality stocks outperforming - unusual pattern")
        else:
            print("  No trades with Quality Score data")

        # Unknown quality (off-universe trades)
        if len(quality_unknown) > 0:
            unknown_wins = len(quality_unknown[quality_unknown["pnl"] > 0])
            unknown_wr = (
                unknown_wins / len(quality_unknown) * 100
                if len(quality_unknown) > 0
                else 0
            )
            unknown_pnl = quality_unknown["pnl"].sum()
            print(
                f"\n  Off-Universe Trades    | Trades: {len(quality_unknown):3} | "
                f"Win Rate: {unknown_wr:5.1f}% | P&L: ${unknown_pnl:>8,.2f}"
            )
            print(
                f"  [INFO] Off-universe tickers: {', '.join(quality_unknown['ticker'].unique())}"
            )

        # Delta Analysis
        print(f"\n{'-' * 40}")
        print("DELTA RANGE ANALYSIS")
        print(f"{'-' * 40}")

        closed["delta_abs"] = closed["delta"].abs()
        bins = [0, 0.15, 0.20, 0.25, 0.30, 0.35, 1.0]
        labels = ["<0.15", "0.15-0.20", "0.20-0.25", "0.25-0.30", "0.30-0.35", ">0.35"]
        closed["delta_range"] = pd.cut(closed["delta_abs"], bins=bins, labels=labels)

        for delta_range in labels:
            delta_trades = closed[closed["delta_range"] == delta_range]
            if len(delta_trades) > 0:
                delta_wins = len(delta_trades[delta_trades["pnl"] > 0])
                delta_wr = delta_wins / len(delta_trades) * 100
                delta_pnl = delta_trades["pnl"].sum()
                print(
                    f"  Delta {delta_range:10} | Trades: {len(delta_trades):3} | "
                    f"Win Rate: {delta_wr:5.1f}% | P&L: ${delta_pnl:>8,.2f}"
                )

        print(f"\n{'=' * 60}\n")

    def show_open_positions(self) -> None:
        """Display all open positions with live P/L from MooMoo imports."""
        open_trades = self.df[self.df["status"] == "OPEN"].copy()

        print("\n" + "=" * 60)
        print("OPEN POSITIONS")
        print("=" * 60)

        if open_trades.empty:
            print("\n  No open positions.\n")
            return

        today = datetime.now()
        total_unrealized_pnl = 0

        for _, trade in open_trades.iterrows():
            entry_date = pd.to_datetime(trade["entry_date"])
            days_held = (today - entry_date).days

            # Calculate current DTE from expiry date if available
            if pd.notna(trade["expiry_date"]):
                expiry = pd.to_datetime(trade["expiry_date"])
                current_dte = (expiry - today).days
            else:
                current_dte = max(0, trade["dte"] - days_held)

            # Warnings
            warnings = []
            if current_dte <= 7:
                warnings.append("[!] 7 DTE RULE - CLOSE NOW")
            elif current_dte <= 21:
                warnings.append("[*] 21 DTE approaching")

            # Check for 50% profit
            if pd.notna(trade["unrealized_pnl"]) and trade["premium"] > 0:
                profit_pct = (trade["unrealized_pnl"] / trade["premium"]) * 100
                if profit_pct >= 50:
                    warnings.append("[$$] 50% PROFIT TARGET HIT")

            warning_str = " | ".join(warnings) if warnings else ""

            # Display position
            print(
                f"\n  Trade #{int(trade['trade_id'])}: {trade['ticker']} ${trade['strike']}P"
            )

            # Show expiry if available
            expiry_str = ""
            if pd.notna(trade["expiry_date"]):
                expiry_str = f" (exp {trade['expiry_date']})"

            print(f"    Entry: {trade['entry_date']}{expiry_str}")
            print(
                f"    Premium: ${trade['premium']:.2f} | DTE: {current_dte} | Days Held: {days_held}"
            )

            # Show live P/L if available
            if pd.notna(trade["unrealized_pnl"]):
                pnl = trade["unrealized_pnl"]
                pnl_pct = trade["unrealized_pnl_pct"]
                total_unrealized_pnl += pnl
                pnl_indicator = "+" if pnl >= 0 else ""
                print(
                    f"    Live P/L: {pnl_indicator}${pnl:.2f} ({pnl_pct:+.1f}%) | "
                    f"Option Price: ${trade['current_option_price']:.2f}"
                )
            else:
                print("    [No live P/L data - import MooMoo CSV to update]")

            # Display IV Rank and Quality Score (handle None values)
            iv_rank_str = (
                f"{trade['iv_rank']:.0f}%" if pd.notna(trade["iv_rank"]) else "N/A"
            )
            delta_str = f"{trade['delta']:.2f}" if pd.notna(trade["delta"]) else "N/A"

            # Quality score display
            if pd.notna(trade.get("quality_score")):
                quality_bucket = classify_quality_bucket(trade["quality_score"])
                quality_str = f"{trade['quality_score']:.1f} ({quality_bucket})"
            else:
                quality_str = "N/A (off-universe)"

            print(
                f"    Delta: {delta_str} | IV Rank: {iv_rank_str} | "
                f"Sector: {trade['sector']}"
            )
            print(
                f"    Quality: {quality_str} | VIX Regime: {trade['vix_regime']} (Entry VIX: {trade['vix']:.1f})"
            )

            if warning_str:
                print(f"    >>> {warning_str}")

        # Summary
        total_premium = open_trades["premium"].sum()
        total_capital = open_trades["capital_deployed"].sum()

        print(f"\n{'-' * 40}")
        print(f"  Total Open Positions: {len(open_trades)}")
        print(f"  Total Premium Collected: ${total_premium:,.2f}")
        print(f"  Total Unrealized P/L: ${total_unrealized_pnl:,.2f}")
        print(
            f"  Total Capital Deployed: ${total_capital:,.2f} ({total_capital / self.total_capital * 100:.1f}%)"
        )

        if open_trades["last_updated"].notna().any():
            last_update = open_trades["last_updated"].dropna().max()
            print(f"  Last Updated: {last_update}")

        print("=" * 60 + "\n")

    def get_open_trades(self) -> pd.DataFrame:
        """Return DataFrame of all open positions."""
        return self.df[self.df["status"] == "OPEN"].copy()

    def get_closed_trades(self) -> pd.DataFrame:
        """Return DataFrame of all closed positions."""
        return self.df[self.df["status"] == "CLOSED"].copy()

    def export_to_csv(self, filepath: str) -> None:
        """Export journal to specified CSV path."""
        self.df.to_csv(filepath, index=False)
        logger.info(f"Journal exported to {filepath}")

    # =========================================================================
    # SECTOR EXPOSURE TRACKING (Option B Compromise - Jan 2026)
    # =========================================================================

    def get_sector_exposure(self) -> Dict[str, Dict]:
        """
        Calculate current sector exposure across all open positions.

        Returns:
            Dict mapping sector to exposure metrics:
            {
                'Technology': {
                    'positions': 2,
                    'capital_deployed': 14500,
                    'pct_of_capital': 32.6,
                    'tickers': ['MSFT', 'GOOGL']
                },
                'Financial Services': {
                    'positions': 1,
                    'capital_deployed': 7000,
                    'pct_of_capital': 15.7,
                    'tickers': ['V']
                },
                ...
            }

        Example usage:
            exposure = journal.get_sector_exposure()
            tech_pct = exposure.get('Technology', {}).get('pct_of_capital', 0)
            if tech_pct > 40:
                print("Warning: Tech exposure above 40%")
        """
        open_trades = self.df[self.df["status"] == "OPEN"]

        if open_trades.empty:
            return {}

        sector_exposure = {}

        # Group by sector and calculate metrics
        for sector in open_trades["sector"].unique():
            sector_trades = open_trades[open_trades["sector"] == sector]

            total_capital = sector_trades["capital_deployed"].sum()
            pct_of_capital = (total_capital / self.total_capital) * 100

            sector_exposure[sector] = {
                "positions": len(sector_trades),
                "capital_deployed": float(total_capital),
                "pct_of_capital": round(float(pct_of_capital), 1),
                "tickers": sector_trades["ticker"].tolist(),
            }

        return sector_exposure

    def check_sector_limits(
        self, new_ticker: str, new_sector: str, new_capital: float
    ) -> Tuple[bool, str]:
        """
        Check if adding a new position would violate sector exposure limits.

        Enforces POSITION_SECTOR_LIMITS from config.py:
        - Max 40% capital per sector
        - Max 3 positions per sector

        Args:
            new_ticker: Ticker symbol for proposed trade
            new_sector: Sector of proposed trade (e.g., 'Technology')
            new_capital: Capital required for proposed trade (strike × 100)

        Returns:
            Tuple of (can_deploy, reason)
            - can_deploy: True if within limits, False if violation
            - reason: Human-readable explanation

        Example:
            can_deploy, reason = journal.check_sector_limits('NVDA', 'Technology', 7000)
            if not can_deploy:
                print(f"Cannot deploy: {reason}")
        """
        try:
            from config import POSITION_SECTOR_LIMITS
        except ImportError:
            # If config doesn't have POSITION_SECTOR_LIMITS, use defaults
            POSITION_SECTOR_LIMITS = {
                "max_sector_exposure_pct": 0.40,
                "max_positions_per_sector": 3,
                "warn_sector_exposure_pct": 0.35,
                "warn_positions_per_sector": 2,
            }

        # Get current sector exposure
        sector_exposure = self.get_sector_exposure()

        # Extract limits
        max_positions = POSITION_SECTOR_LIMITS.get("max_positions_per_sector", 3)
        warn_positions = POSITION_SECTOR_LIMITS.get("warn_positions_per_sector", 2)
        max_exposure_pct = POSITION_SECTOR_LIMITS.get("max_sector_exposure_pct", 0.40)
        warn_exposure_pct = POSITION_SECTOR_LIMITS.get("warn_sector_exposure_pct", 0.35)

        # Check 1: Position count limit
        current_positions = sector_exposure.get(new_sector, {}).get("positions", 0)

        if current_positions >= max_positions:
            return (
                False,
                f"REJECTED: Already have {current_positions} {new_sector} positions (max {max_positions})",
            )

        # Check 2: Capital exposure limit
        current_capital = sector_exposure.get(new_sector, {}).get("capital_deployed", 0)
        new_total_capital = current_capital + new_capital
        new_exposure_pct = new_total_capital / self.total_capital

        if new_exposure_pct > max_exposure_pct:
            current_pct = (current_capital / self.total_capital) * 100
            new_pct = new_exposure_pct * 100
            return (
                False,
                f"REJECTED: Would create {new_pct:.1f}% {new_sector} exposure "
                f"(current: {current_pct:.1f}%, max: {max_exposure_pct * 100:.0f}%)",
            )

        # Passed all checks - generate status message
        warnings = []

        # Warning: Approaching position limit
        if current_positions + 1 >= warn_positions:
            warnings.append(
                f"WARN: Will have {current_positions + 1} {new_sector} positions"
            )

        # Warning: Approaching exposure limit
        if new_exposure_pct >= warn_exposure_pct:
            warnings.append(
                f"WARN: {new_sector} exposure will be {new_exposure_pct * 100:.1f}% "
                f"(approaching {max_exposure_pct * 100:.0f}% limit)"
            )

        # Return with appropriate message
        if warnings:
            return (True, " | ".join(warnings))
        else:
            return (
                True,
                f"OK: {new_sector} exposure will be {new_exposure_pct * 100:.1f}% "
                f"({current_positions + 1} position{'s' if current_positions + 1 > 1 else ''})",
            )

    def print_sector_exposure_report(self) -> None:
        """
        Print formatted report of current sector exposure.

        Displays:
        - Sector-by-sector breakdown (positions, capital, % of portfolio)
        - Tickers in each sector
        - Visual flags for limits/warnings (LIMIT, WARN)
        - Total deployed capital
        - Sector diversity check

        Example output:
        ======================================================================
        SECTOR EXPOSURE REPORT
        ======================================================================
        Sector                    Positions    Capital         % of Capital
        ----------------------------------------------------------------------
        Technology                3            $21,000         44.7%   WARN
          -> MSFT, GOOGL, TSM
        Financial Services        1            $ 7,000         14.9%
          -> V
        ----------------------------------------------------------------------
        TOTAL DEPLOYED            4            $28,000         59.6%

        Active sectors: 2   (min 3 required)
        ======================================================================
        """
        try:
            from config import POSITION_SECTOR_LIMITS
        except ImportError:
            POSITION_SECTOR_LIMITS = {
                "max_sector_exposure_pct": 0.40,
                "max_positions_per_sector": 3,
                "warn_sector_exposure_pct": 0.35,
                "min_active_sectors": 3,
            }

        sector_exposure = self.get_sector_exposure()

        if not sector_exposure:
            print("\n  No open positions - sector exposure: 0%")
            return

        # Extract limits
        max_exposure_pct = POSITION_SECTOR_LIMITS.get("max_sector_exposure_pct", 0.40)
        warn_exposure_pct = POSITION_SECTOR_LIMITS.get("warn_sector_exposure_pct", 0.35)
        max_positions = POSITION_SECTOR_LIMITS.get("max_positions_per_sector", 3)
        min_sectors = POSITION_SECTOR_LIMITS.get("min_active_sectors", 3)

        # Print header
        print(f"\n{'=' * 70}")
        print("SECTOR EXPOSURE REPORT (Option B Compromise)")
        print(f"{'=' * 70}")
        print(f"{'Sector':<25} {'Positions':<12} {'Capital':<15} {'% of Capital':<15}")
        print(f"{'-' * 70}")

        # Sort by capital deployed (descending)
        sorted_sectors = sorted(
            sector_exposure.items(),
            key=lambda x: x[1]["capital_deployed"],
            reverse=True,
        )

        # Print each sector
        for sector, metrics in sorted_sectors:
            positions = metrics["positions"]
            capital = metrics["capital_deployed"]
            pct = metrics["pct_of_capital"]
            tickers = ", ".join(metrics["tickers"])

            # Determine status flag
            flag = ""
            if pct >= max_exposure_pct * 100:
                flag = "[LIMIT]"
            elif pct >= warn_exposure_pct * 100:
                flag = "[WARN]"
            elif positions >= max_positions:
                flag = "[MAX POS]"

            # Print sector summary
            print(
                f"{sector:<25} {positions:<12} ${capital:>13,.0f} {pct:>13.1f}%  {flag}"
            )

            # Print tickers (indented)
            print(f"  -> {tickers}")

        # Print totals
        print(f"{'-' * 70}")

        total_capital = sum(m["capital_deployed"] for m in sector_exposure.values())
        total_positions = sum(m["positions"] for m in sector_exposure.values())
        total_pct = (total_capital / self.total_capital) * 100

        print(
            f"{'TOTAL DEPLOYED':<25} {total_positions:<12} ${total_capital:>13,.0f} {total_pct:>13.1f}%"
        )

        # Sector diversity check
        active_sectors = len(sector_exposure)
        print(f"\nActive sectors: {active_sectors} ", end="")

        if active_sectors < min_sectors:
            print(f"[WARN] (min {min_sectors} required)")
        else:
            print(f"[OK] (min {min_sectors})")

        print(f"{'=' * 70}\n")


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main() -> None:
    """CLI for trade journal operations."""
    import sys

    journal = TradeJournal()

    if len(sys.argv) < 2:
        print("Usage: python trade_journal.py [command]")
        print("\nCommands:")
        print("  stats              - Show performance dashboard")
        print("  open               - Show open positions")
        print("  sector             - Show sector exposure report (Option B)")
        print("  import <csv_path>  - Import from MooMoo CSV")
        print("  export <filepath>  - Export journal to CSV")
        return

    command = sys.argv[1].lower()

    if command == "stats":
        journal.show_stats()
    elif command == "open":
        journal.show_open_positions()
    elif command == "sector":
        journal.print_sector_exposure_report()
    elif command == "import":
        if len(sys.argv) < 3:
            print("Usage: python trade_journal.py import <csv_path>")
            return
        csv_path = sys.argv[2]
        journal.import_from_moomoo(csv_path)
    elif command == "export":
        filepath = sys.argv[2] if len(sys.argv) > 2 else "journal_export.csv"
        journal.export_to_csv(filepath)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
