#!/usr/bin/env python3
"""
Universe Builder — Cash-Secured-Put (Wheel) stock universe.

Philosophy (tier-1, simple, robust): a CSP universe needs names you'd be happy to
OWN at the strike, with LIQUID stock/options, sized to your capital. It is NOT a
deep-value equity screen — for $10B+ profitable large caps, bankruptcy/quality
scores (Altman-Z, Piotroski, analyst-buy%) add little signal over a 30-45 day hold
while costing API budget and robustness. Time-varying signals (IV, premium, term
structure, earnings timing) are SCAN-TIME concerns and live in screener_wheel.py /
earnings_checker.py — not here.

Pipeline:
  1. One FMP company-screener call  -> size/price/liquidity candidate pool.
  2. Client-side prune (free)        -> drop ETFs/funds/inactive/biotech, rank by $-volume.
  3. One ratios-ttm call per name    -> margins, leverage, ROE (pool capped for budget).
  4. Minimalist quality gate         -> profitable + solvent leverage + liquidity sanity.
  5. Sector-aware percentile score   -> rank within sector (no cross-sector margin bias).
  6. Sector-diversified selection    -> quality-first greedy fill, dominance cap, no forced fills.
  7. Write universe.py               -> identical public surface (downstream contract).

API budget: ~1 + FUNDAMENTAL_POOL_CAP calls cold; near-zero warm (24h cache). Stays
under the FMP Starter 250/day cap. Fully non-interactive — warnings print and proceed.

Usage:
  python universe_builder.py                    # build & overwrite universe.py
  python universe_builder.py --dry-run          # preview, write nothing
  python universe_builder.py --universe-size 50 # custom target size
  python universe_builder.py --verbose          # show drops & sector histogram
"""

import argparse
import glob
import os
import shutil
import sys
from datetime import datetime

import pandas as pd

from config import FMP_API_KEY
from fmp_data_fetcher import FMPDataFetcher

# =============================================================================
# CONFIG — all tunables in one place, no scattered magic numbers
# =============================================================================

# Stage 1/2: candidate screen (FMP screener filters + client-side prune)
MIN_MARKET_CAP = 10e9  # $10B+ — established, ownable large caps
PRICE_MIN = 15.0  # options-friendly floor
PRICE_MAX = 600.0  # broad: kept wide; capital filtering happens at scan time
MIN_AVG_VOLUME = 1_000_000  # >=1M shares/day — proxy for liquid options
SCREENER_LIMIT = 500  # max rows FMP returns in the single screener call
FUNDAMENTAL_POOL_CAP = (
    200  # API-budget lever: # of top-$-volume names we fetch ratios for
)

# Stage 4: minimalist quality gate.
# Deliberately NOT gating on Debt/Equity or Current Ratio: for $10B+ names these are
# unreliable (buybacks drive book equity negative -> meaningless D/E; cash-efficient
# mega-caps routinely run CR < 1). Hard-cutting on them ejects premier, ownable CSP
# names (ADBE, ORCL, PEP, HD, UNH, CSCO, T, VZ, utilities...). Size + profitability +
# liquidity is the robust gate; leverage is left to trade-time discretion.

# Stage 6: diversification
DEFAULT_TARGET_SIZE = 60  # target universe size (overridable via --universe-size)
MAX_SECTOR_PCT = 0.35  # no sector may exceed 35% of the universe

# Industry classification (FMP industry strings)
EXCLUDE_INDUSTRY_KEYWORDS = (
    "biotech",
)  # binary FDA-catalyst risk — not ownable for CSP

# Sector-aware quality-score weights (sum to 1.0). Pure within-sector ranking.
# Net margin (not ROE) is the 4th dimension: ratios-ttm exposes netProfitMarginTTM in
# the same call, and unlike a computed ROE it isn't distorted by buyback-shrunken book
# equity. Its gap below operating margin also indirectly rewards low interest/tax burden.
SCORE_WEIGHTS = {
    "operating_margin": 0.30,
    "net_margin": 0.25,
    "gross_margin": 0.20,
    "liquidity": 0.25,  # global $-volume percentile (options-liquidity proxy)
}

# =============================================================================
# GENERATED universe.py TAIL — helpers + EXCLUDED_TICKERS, written VERBATIM.
# This is the downstream public contract (screener_wheel.py, earnings_monitor.py).
# Do not change signatures without updating consumers.
# =============================================================================

UNIVERSE_TAIL = '''
EXCLUDED_TICKERS = [
    # Biotech with pending FDA decisions (add as needed)
    # M&A targets (add as needed)
    # Delisting candidates (add as needed)
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_wheel_universe(max_capital: int = None) -> list:
    """
    Get Wheel universe, optionally filtered by available capital.

    Args:
        max_capital: Maximum capital per position in dollars (optional)
                    e.g., 10000 filters to stocks with price <= $100

    Returns:
        List of tickers affordable within capital constraint

    Examples:
        >>> get_wheel_universe()              # All stocks
        >>> get_wheel_universe(5000)          # Stocks up to $50
        >>> get_wheel_universe(10000)         # Stocks up to $100
        >>> get_wheel_universe(25000)         # Stocks up to $250
    """
    if max_capital is None:
        return WHEEL_UNIVERSE

    return [t for t in WHEEL_UNIVERSE if CAPITAL_REQUIREMENTS.get(t, 0) <= max_capital]


def get_affordable_stocks(max_capital: int) -> list:
    """
    Get stocks affordable within capital constraint with details.

    Args:
        max_capital: Maximum capital per position in dollars

    Returns:
        List of (ticker, capital_required) tuples sorted by capital
    """
    affordable = [
        (t, CAPITAL_REQUIREMENTS[t])
        for t in WHEEL_UNIVERSE
        if CAPITAL_REQUIREMENTS.get(t, 0) <= max_capital
    ]
    return sorted(affordable, key=lambda x: x[1])


def add_to_excluded(ticker: str):
    """Add a ticker to excluded list (runtime only)"""
    if ticker not in EXCLUDED_TICKERS:
        EXCLUDED_TICKERS.append(ticker)


def format_moomoo_symbol(ticker: str) -> str:
    """Convert ticker to MooMoo format (e.g., 'AAPL' -> 'US.AAPL')"""
    if not ticker.startswith("US."):
        return f"US.{ticker}"
    return ticker


def strip_moomoo_prefix(symbol: str) -> str:
    """Convert MooMoo format to plain ticker (e.g., 'US.AAPL' -> 'AAPL')"""
    if symbol.startswith("US."):
        return symbol[3:]
    return symbol


def get_stock_metadata(ticker: str) -> dict:
    """
    Return reporting metadata for a ticker (company, sector, quality_score,
    capital_required). Falls back to safe defaults for unknown tickers so callers
    (e.g. earnings_monitor.py) never KeyError on a name outside the universe.
    """
    return STOCK_METADATA.get(ticker, {
        "company": ticker,
        "sector": "Unknown",
        "quality_score": 0.0,
        "capital_required": CAPITAL_REQUIREMENTS.get(ticker, 0),
    })
'''


# =============================================================================
# STAGE 1+2 — candidate pool (one screener call + free client-side prune)
# =============================================================================


def fetch_candidate_pool(fetcher: FMPDataFetcher, verbose: bool = False) -> list:
    """Screen for large, liquid, optionable names. Returns up to FUNDAMENTAL_POOL_CAP
    screener rows, ranked by dollar volume (price * volume) as an options-liquidity proxy."""
    rows = fetcher.screen_stocks(
        market_cap_min=MIN_MARKET_CAP,
        price_min=PRICE_MIN,
        price_max=PRICE_MAX,
        volume_min=MIN_AVG_VOLUME,
        limit=SCREENER_LIMIT,
    )
    print(f"[1/6] Screener returned {len(rows)} rows")

    pool = []
    dropped = {"etf_fund": 0, "inactive": 0, "biotech": 0, "bad_fields": 0}
    for r in rows:
        ticker = r.get("symbol")
        price = r.get("price")
        volume = r.get("volume")
        sector = r.get("sector") or ""
        industry = (r.get("industry") or "").lower()

        if not ticker or price is None or volume is None or not sector:
            dropped["bad_fields"] += 1
            continue
        if r.get("isEtf") or r.get("isFund"):
            dropped["etf_fund"] += 1
            continue
        if r.get("isActivelyTrading") is False:
            dropped["inactive"] += 1
            continue
        if any(kw in industry for kw in EXCLUDE_INDUSTRY_KEYWORDS):
            dropped["biotech"] += 1
            continue

        pool.append(
            {
                "ticker": ticker,
                "company": (r.get("companyName") or ticker)[:30],
                "sector": sector,
                "industry": r.get("industry") or "",
                "price": float(price),
                "market_cap": float(r.get("marketCap") or 0),
                "dollar_volume": float(price) * float(volume),
            }
        )

    pool.sort(key=lambda x: x["dollar_volume"], reverse=True)
    pool = pool[:FUNDAMENTAL_POOL_CAP]
    print(
        f"[2/6] Pruned to {len(pool)} candidates "
        f"(dropped {dropped}); fundamentals capped at {FUNDAMENTAL_POOL_CAP}"
    )
    if verbose:
        print("      Top 10 by $-volume: " + ", ".join(p["ticker"] for p in pool[:10]))
    return pool


# =============================================================================
# STAGE 3 — per-ticker fundamentals (single ratios-ttm call each, cached)
# =============================================================================


def fetch_fundamentals(
    fetcher: FMPDataFetcher, pool: list, verbose: bool = False
) -> pd.DataFrame:
    """Enrich each candidate with TTM ratios via ONE ratios-ttm call per name."""
    records = []
    for i, p in enumerate(pool, 1):
        data = fetcher._fetch_with_cache("ratios-ttm", {"symbol": p["ticker"]})
        row = data[0] if data else None
        if not row:
            if verbose:
                print(f"      [skip] {p['ticker']}: no ratios-ttm data")
            continue
        records.append(
            {
                **p,
                "operating_margin": row.get("operatingProfitMarginTTM"),
                "gross_margin": row.get("grossProfitMarginTTM"),
                "net_margin": row.get("netProfitMarginTTM"),
            }
        )
        if verbose and i % 25 == 0:
            print(f"      ...fetched fundamentals for {i}/{len(pool)}")

    df = pd.DataFrame(records)
    print(
        f"[3/6] Fundamentals fetched for {len(df)} names "
        f"(~{fetcher.request_count} live FMP calls this run)"
    )
    return df


# =============================================================================
# STAGE 4 — minimalist quality gate (hard filters only)
# =============================================================================


def apply_quality_gate(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """Keep only profitable names (positive TTM operating margin). This is the only
    fundamental hard cut — size/liquidity/biotech/ETF are already handled upstream.
    A None operating margin fails the gate (can't verify => exclude)."""
    if df.empty:
        return df

    dropped_tickers = []
    keep = []
    for _, s in df.iterrows():
        op = s["operating_margin"]
        if op is None or op <= 0:
            dropped_tickers.append(s["ticker"])
            continue
        keep.append(s)

    gated = pd.DataFrame(keep)
    print(
        f"[4/6] Quality gate kept {len(gated)}/{len(df)} "
        f"(dropped {len(dropped_tickers)} unprofitable)"
    )
    if verbose and dropped_tickers:
        print("      Dropped (unprofitable): " + ", ".join(dropped_tickers))
    return gated


# =============================================================================
# STAGE 5 — sector-aware quality score (0-100)
# =============================================================================


def compute_quality_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Percentile-rank each metric WITHIN its sector (so margin-based metrics don't
    penalise low-margin sectors), weight to 0-100. Liquidity ranks globally. Single-
    stock sectors get a neutral 0.5 percentile."""
    if df.empty:
        return df
    df = df.copy()

    # Coerce scoring inputs to numeric. We do NOT median-fill: rank(pct=True) keeps NaN
    # as NaN and sector_pct's fillna(0.5) below maps any missing/sparse metric to a
    # neutral 0.5 percentile — so scoring is correct (and warning-free) even if a field
    # comes back fully empty.
    for col in ("operating_margin", "net_margin", "gross_margin"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    sector_size = df.groupby("sector")["ticker"].transform("size")

    def sector_pct(series: pd.Series) -> pd.Series:
        pct = series.groupby(df["sector"]).rank(pct=True)
        pct = pct.where(sector_size > 1, 0.5)  # neutral for single-stock sectors
        return pct.fillna(
            0.5
        )  # backstop: a missing/fully-empty metric ranks neutral, never NaN

    op_pct = sector_pct(df["operating_margin"])
    nm_pct = sector_pct(df["net_margin"])
    gm_pct = sector_pct(df["gross_margin"])
    liq_pct = df["dollar_volume"].rank(pct=True)  # global liquidity

    df["quality_score"] = (
        SCORE_WEIGHTS["operating_margin"] * op_pct
        + SCORE_WEIGHTS["net_margin"] * nm_pct
        + SCORE_WEIGHTS["gross_margin"] * gm_pct
        + SCORE_WEIGHTS["liquidity"] * liq_pct
    ) * 100
    df["quality_score"] = df["quality_score"].round(1)

    return df.sort_values("quality_score", ascending=False).reset_index(drop=True)


# =============================================================================
# STAGE 6 — sector-diversified selection (quality-first, dominance cap, no forced fills)
# =============================================================================


def diversify(df: pd.DataFrame, target_size: int) -> pd.DataFrame:
    """Greedily admit highest-score names until target_size, skipping a name only if
    its sector already holds the dominance cap (MAX_SECTOR_PCT of target_size)."""
    if df.empty:
        return df
    sector_cap = max(1, int(MAX_SECTOR_PCT * target_size))

    selected, sector_counts = [], {}
    for _, s in df.iterrows():
        if len(selected) >= target_size:
            break
        sec = s["sector"]
        if sector_counts.get(sec, 0) >= sector_cap:
            continue
        selected.append(s)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1

    final = pd.DataFrame(selected).reset_index(drop=True)
    hist = ", ".join(
        f"{k}: {v}" for k, v in sorted(sector_counts.items(), key=lambda x: -x[1])
    )
    print(f"[6/6] Selected {len(final)} names (sector cap {sector_cap}/{target_size})")
    print(f"      Sector histogram: {hist}")
    return final


# =============================================================================
# RENDER + WRITE universe.py
# =============================================================================


def render_universe_file(df: pd.DataFrame, screened: int, gated: int) -> str:
    """Render universe.py with the exact downstream contract: WHEEL_UNIVERSE,
    CAPITAL_REQUIREMENTS, STOCK_METADATA, EXCLUDED_TICKERS + helper functions."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    a = lines.append

    a('"""')
    a("Pre-defined stock universes for Options Scanner")
    a(f"AUTO-GENERATED by universe_builder.py on {timestamp}")
    a("")
    a("CASH-SECURED-PUT (WHEEL) UNIVERSE — quality large caps across all price ranges.")
    a("Filter by capital per position using get_wheel_universe(max_capital).")
    a("")
    a("Minimalist quality gate (hard filters):")
    a(
        f"- Market Cap > ${MIN_MARKET_CAP / 1e9:.0f}B, Price ${PRICE_MIN:.0f}-{PRICE_MAX:.0f}, "
        f"Avg Volume > {MIN_AVG_VOLUME:,}/day"
    )
    a("- Positive TTM operating margin (profitable)")
    a("- Biotech / ETFs / inactive names excluded")
    a("  (D/E & Current Ratio deliberately NOT gated — unreliable for mega-caps)")
    a("")
    a("Sector-aware quality score (within-sector percentile, 0-100):")
    a("- Operating margin 30% | Net margin 25% | Gross margin 20% | Liquidity 25%")
    a(
        f"Sector diversity: no sector > {MAX_SECTOR_PCT:.0%} of universe (quality-first, no forced fills)."
    )
    a("")
    a(
        f"Candidates screened: {screened} | Passed gate: {gated} | Final universe: {len(df)}"
    )
    a('"""')
    a("")
    a("# " + "=" * 77)
    a("# WHEEL STRATEGY UNIVERSE (single quality-focused universe)")
    a("# Quality stocks across all price ranges - filter by capital available")
    a("# " + "=" * 77)
    a("")
    a("WHEEL_UNIVERSE = [")
    for _, s in df.iterrows():
        cap = round(s["price"] * 100)
        a(
            f'    "{s["ticker"]}",  # {s["company"]} | {s["sector"]} | '
            f"${s['price']:.0f} | Capital: ${cap / 1000:.1f}K | Score: {s['quality_score']:.1f}"
        )
    a("]")
    a("")
    a("# Capital requirement per contract (Price x 100 for 1 CSP)")
    a("CAPITAL_REQUIREMENTS = {")
    for _, s in df.iterrows():
        a(f'    "{s["ticker"]}": {round(s["price"] * 100)},')
    a("}")
    a("")
    a("# Per-stock metadata (company, sector, quality score, capital) for reporting.")
    a("# Consumed by earnings_monitor.py via get_stock_metadata().")
    a("STOCK_METADATA = {")
    for _, s in df.iterrows():
        cap = round(s["price"] * 100)
        a(
            f'    "{s["ticker"]}": {{"company": "{s["company"]}", "sector": "{s["sector"]}", '
            f'"quality_score": {s["quality_score"]:.1f}, "capital_required": {cap}}},'
        )
    a("}")
    a(UNIVERSE_TAIL)

    return "\n".join(lines)


def write_universe_file(content: str, output_path: str, backup: bool = True):
    """Write universe file, backing up an existing universe.py first."""
    if backup and output_path == "universe.py":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"universe.py.backup.{timestamp}"
        try:
            shutil.copy2("universe.py", backup_path)
            print(f"[OK] Backup created: {backup_path}")
        except FileNotFoundError:
            print("[WARN] No existing universe.py to backup")

        # Keep only the 2 newest backups (timestamped names sort chronologically)
        for stale in sorted(glob.glob("universe.py.backup.*"))[:-2]:
            try:
                os.remove(stale)
            except OSError:
                pass

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] {output_path} written ({len(content.splitlines())} lines)")


# =============================================================================
# ORCHESTRATION
# =============================================================================


def build_universe(args) -> str:
    fetcher = FMPDataFetcher(api_key=FMP_API_KEY)

    pool = fetch_candidate_pool(fetcher, args.verbose)
    if not pool:
        print(
            "[ERROR] Screener returned no candidates — aborting (universe.py unchanged)."
        )
        sys.exit(1)
    screened = len(pool)

    df = fetch_fundamentals(fetcher, pool, args.verbose)
    df = apply_quality_gate(df, args.verbose)
    gated = len(df)
    if gated < 15:
        print(
            f"[WARN] Only {gated} names passed the quality gate (expected 15+). "
            "Proceeding with a thin universe — review filters if this persists."
        )

    df = compute_quality_scores(df)
    print("[5/6] Quality scores computed (sector-aware percentile, 0-100)")

    df = diversify(df, args.universe_size)
    return render_universe_file(df, screened, gated)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Build the cash-secured-put (Wheel) stock universe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python universe_builder.py                    # build & overwrite universe.py
  python universe_builder.py --dry-run          # preview without writing
  python universe_builder.py --output test.py   # write to a test file
  python universe_builder.py --verbose          # show drops & sector histogram
  python universe_builder.py --universe-size 50 # custom universe size
        """,
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview results without writing to file"
    )
    parser.add_argument(
        "--output", default="universe.py", help="Output filename (default: universe.py)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed drops and the sector histogram",
    )
    parser.add_argument(
        "--universe-size",
        type=int,
        default=DEFAULT_TARGET_SIZE,
        help=f"Target universe size (default: {DEFAULT_TARGET_SIZE})",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (not recommended)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    print("=" * 79)
    print("UNIVERSE BUILDER — Cash-Secured-Put (Wheel) universe")
    print(
        f"Target size: {args.universe_size} | Output: {args.output}"
        f"{' | DRY RUN' if args.dry_run else ''}"
    )
    print("=" * 79)

    content = build_universe(args)

    if args.dry_run:
        print("\n[OK] Dry run complete — no files written.")
        print(f"     Would write {len(content.splitlines())} lines to {args.output}")
    else:
        write_universe_file(content, args.output, backup=not args.no_backup)
        print("\n[OK] Universe build complete.")


if __name__ == "__main__":
    main()
