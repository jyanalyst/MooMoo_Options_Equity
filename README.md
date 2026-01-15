# Options Income Scanner

Automated screening tool for options income strategies using a **hybrid data approach**:
- **Stock quotes**: yfinance (FREE - no subscription needed)
- **Options data**: MooMoo API (requires OPRA - FREE with $3k+ assets)

This hybrid approach **saves $60/month** by avoiding the Nasdaq Basic OpenAPI subscription.

## Strategies Supported

### 1. Wheel Strategy (Cash-Secured Puts)
- Quality stocks you would own at the strike price
- IV Rank >30%, Delta 0.20-0.30, DTE 30-45
- Earnings avoidance with 7-day buffer
- Term structure analysis (contango preferred)

### 2. Volatility Harvesting (Iron Condors)
- High-IV names for premium harvesting
- IV Rank >80%, Delta 0.15-0.20, DTE 21-35
- Defined risk with capped losses
- Post-squeeze candidates preferred

## Installation

```bash
# Clone/copy the scanner files
cd options_scanner

# Install dependencies
pip install -r requirements.txt

# Make sure MooMoo OpenD is running and logged in
```

## Usage

```bash
# Scan for Wheel candidates
python main.py wheel

# Scan for Vol Harvest candidates
python main.py vol

# Run both scans
python main.py both

# Test with mock data (no MooMoo connection needed)
python main.py --mock wheel

# Scan Tier 1 stocks only ($15-70)
python main.py wheel --tier 1

# Interactive mode to view candidate details
python main.py both -i

# Quiet mode (minimal output)
python main.py wheel --quiet

# Skip CSV export
python main.py both --no-csv
```

## Refreshing Stock Universe (Every 2 Weeks)

The stock universe should be refreshed bi-weekly to ensure you're trading current quality names:

```bash
# Run universe builder to refresh fundamental screening
python universe_builder.py

# Review changes (optional)
git diff universe.py

# Test with wheel scanner
python main.py wheel --tier 1
```

**Recommended schedule:** Every other Sunday during weekly review
**What it does:** Screens 300+ stocks, scores by fundamental quality, selects top 20 per tier
**Backup:** Automatically creates timestamped backup before overwriting

## Output

### Terminal Display
- Summary table of top candidates
- Quality scores for ranking
- Key metrics (delta, premium, IV rank, etc.)

### CSV Export
- Detailed data for trade journaling
- Saved to `./scan_results/` directory
- Timestamped filenames

## Configuration

Edit `config.py` to adjust:
- Strategy parameters (delta range, DTE, IV thresholds)
- Position sizing rules
- Output settings

Edit `universe.py` to customize:
- Wheel stock watchlists (Tier 1/2/3)
- Vol Harvest candidates
- Excluded tickers

## Requirements

- **Python 3.8+**
- **yfinance** - For stock quotes (FREE)
- **MooMoo OpenD** - Running locally for options data
- **OPRA subscription** - FREE with $3k+ assets in MooMoo account

**Note**: You do NOT need the $60/month Nasdaq Basic OpenAPI subscription. Stock quotes come from yfinance for free.

## Architecture

```
options_scanner/
├── main.py               # CLI entry point
├── config.py             # Strategy parameters
├── universe.py           # Stock watchlists
├── data_fetcher.py       # MooMoo API wrapper
├── iv_analyzer.py        # IV Rank & term structure
├── earnings_checker.py   # Earnings date validation (yfinance)
├── screener_wheel.py     # Wheel strategy logic
├── screener_vol_harvest.py # Vol Harvest strategy logic
├── output_formatter.py   # Display & CSV export
└── requirements.txt      # Dependencies
```

## Strategy Rules Reference

### Wheel Strategy
- Max 80% capital allocation
- Max 20% per position
- 6-8 concurrent positions
- 50% profit target, 21 DTE exit
- Never trade through earnings (+7 day buffer)

### Vol Harvest Strategy
- Max 20% capital allocation
- Defined risk only (iron condors)
- Premium >33% of wing width
- 50% profit target, 7 DTE exit
- Never during active squeeze

## Disclaimer

This scanner is for educational purposes. Always verify candidates manually before trading. Past performance does not guarantee future results. Options trading involves significant risk of loss.
