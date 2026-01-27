# Options Income Scanner

Automated screening tool for options income strategies using a **hybrid data approach**:
- **Stock quotes**: yfinance (FREE - no subscription needed)
- **Options data**: MooMoo API (requires OPRA - FREE with $3k+ assets)
- **Fundamentals**: Financial Modeling Prep (FMP) API

This hybrid approach **saves $60/month** by avoiding the Nasdaq Basic OpenAPI subscription.

## Strategies Supported

### 1. Wheel Strategy (Cash-Secured Puts)
- Quality stocks you would own at the strike price
- IV Rank >30%, Delta 0.20-0.30, DTE 30-45
- Earnings avoidance with 14-day buffer
- Term structure analysis (contango preferred)

### 2. Volatility Harvesting (Iron Condors)
- High-IV names for premium harvesting
- IV Rank >80%, Delta 0.15-0.20, DTE 21-35
- Defined risk with capped losses
- Post-squeeze candidates preferred

---

## Complete Trading Workflow

### Weekly Workflow (Sunday)

```
SUNDAY MORNING ROUTINE (~30 minutes)
=====================================

1. REFRESH UNIVERSE (every 2 weeks)
   python universe_builder.py

2. CHECK EARNINGS CALENDAR
   python earnings_monitor.py

   Output: reports/earnings/earnings_calendar_YYYY-MM-DD.csv
   Action: Note AVOID stocks, flag CAUTION stocks for monitoring

3. CHECK VIX REGIME
   python vix_monitor.py --status

   Regimes:
   - LOW (<14): Reduce/pause trading - premium too low
   - NORMAL (14-18): Standard position sizing (100%)
   - ELEVATED (18-25): Aggressive deployment (150% sizing)
   - HIGH (>25): Maximum opportunity - deploy all capital

4. SCAN FOR CANDIDATES
   python main.py wheel --capital 6700    # 15% position sizing

5. REVIEW & PLAN
   - Cross-reference scan results with earnings CSV
   - Only trade stocks with status = SAFE
   - Record VIX regime in trade journal
```

### Daily Workflow (Trading Days)

```
DAILY ROUTINE (~10 minutes)
===========================

MORNING (Before Market Open)
----------------------------
1. Check VIX and log to history
   python vix_monitor.py

2. If VIX regime changed, reassess position sizing

3. Review any positions expiring this week


DURING MARKET HOURS (as needed)
-------------------------------
1. Execute planned trades from Sunday scan

2. If entering a trade, record in journal:
   - VIX level and regime (from vix_monitor.py --status)
   - Earnings status (from earnings CSV)
   - Quality score (from scan results)


END OF DAY
----------
1. Update trade journal with fills
2. Check VIX again if major market move
   python vix_monitor.py
```

### Trade Entry Checklist

Before opening any new position:

```
[ ] Stock status = SAFE (not AVOID/CAUTION) per earnings_monitor.py
[ ] VIX regime noted (LOW/NORMAL/ELEVATED/HIGH)
[ ] Position size adjusted for VIX regime
[ ] Quality score >55 (from universe.py)
[ ] Delta within 0.20-0.30 range
[ ] DTE 30-45 days
[ ] No earnings within DTE + 14 days buffer
```

---

## Installation

```bash
# Clone/copy the scanner files
cd options_scanner

# Install dependencies
pip install -r requirements.txt

# Make sure MooMoo OpenD is running and logged in
```

## Usage

### Main Scanner
```bash
# Scan for Wheel candidates
python main.py wheel

# Scan stocks requiring ≤$6,700/position (15% sizing)
python main.py wheel --capital 6700

# Interactive mode to view candidate details
python main.py wheel -i

# Quiet mode (minimal output)
python main.py wheel --quiet
```

### Earnings Monitor
```bash
# Generate earnings calendar CSV
python earnings_monitor.py

# Console output only (no CSV)
python earnings_monitor.py --console

# Cleanup old reports (>70 days)
python earnings_monitor.py --cleanup
```

### VIX Monitor
```bash
# Check VIX and log to monthly CSV
python vix_monitor.py

# Show current VIX status (no logging)
python vix_monitor.py --status

# View last 10 readings
python vix_monitor.py --history

# View last 20 readings
python vix_monitor.py --history -n 20
```

### Universe Builder
```bash
# Refresh stock universe (run every 2 weeks)
python universe_builder.py

# Review changes
git diff universe.py
```

---

## Output Files

### Scan Results
- `scan_results/wheel_candidates_YYYY-MM-DD.csv`
- Detailed options data for trade execution

### Earnings Calendar
- `reports/earnings/earnings_calendar_YYYY-MM-DD.csv`
- Columns: ticker, company, sector, quality_score, capital_required, earnings_date, days_away, status, notes
- Status values: SAFE, CAUTION (<30 days), AVOID (<14 days)

### VIX History
- `reports/vix/vix_history_YYYY-MM.csv`
- Monthly append-only file
- Columns: timestamp, vix, regime, regime_change, threshold_crossed, direction, notes

---

## Configuration

Edit `config.py` to adjust:
- Strategy parameters (delta range, DTE, IV thresholds)
- Position sizing rules
- Output settings

Edit `universe.py` to customize:
- Wheel stock universe (filtered by capital via get_wheel_universe)
- Stock metadata (quality scores, sectors)
- Excluded tickers

---

## Architecture

```
options_scanner/
├── main.py                 # CLI entry point for scanning
├── config.py               # Strategy parameters
├── universe.py             # Stock universe + metadata
├── universe_builder.py     # Bi-weekly universe refresh
│
├── earnings_monitor.py     # Weekly earnings calendar CSV
├── vix_monitor.py          # VIX regime tracking CSV
│
├── data_fetcher.py         # MooMoo API wrapper
├── fmp_data_fetcher.py     # FMP API for fundamentals
├── iv_analyzer.py          # IV Rank & term structure
├── earnings_checker.py     # Earnings date validation
│
├── trade_journal.py        # Trade logging utilities
│
├── reports/
│   ├── earnings/           # Weekly earnings CSVs
│   └── vix/                # Monthly VIX history CSVs
│
├── scan_results/           # Scanner output CSVs
└── requirements.txt        # Dependencies
```

---

## VIX Regime Guide

| VIX Level | Regime | Position Sizing | Action |
|-----------|--------|-----------------|--------|
| <14 | LOW | 50% or pause | Premium too low, wait for better conditions |
| 14-18 | NORMAL | 100% | Standard deployment |
| 18-25 | ELEVATED | 150% | Favorable conditions, increase exposure |
| >25 | HIGH | 200% | Maximum opportunity, deploy aggressively |

**Threshold alerts**: vix_monitor.py alerts when crossing 14, 18, or 25

---

## Strategy Rules Reference

### Wheel Strategy
- Max 80% capital allocation
- Max 20% per position (adjust by VIX regime)
- 6-8 concurrent positions
- 50% profit target, 21 DTE exit
- Never trade through earnings (+14 day buffer)

### Position Sizing by VIX
| VIX Regime | Target Position Size | Max Positions |
|------------|---------------------|---------------|
| LOW | 10% | 4-5 |
| NORMAL | 15% | 6-8 |
| ELEVATED | 20% | 8-10 |
| HIGH | 25% | 10+ |

---

## Requirements

- **Python 3.8+**
- **yfinance** - For stock quotes (FREE)
- **MooMoo OpenD** - Running locally for options data
- **OPRA subscription** - FREE with $3k+ assets in MooMoo account
- **FMP API key** - For fundamental data (Starter plan sufficient)

**Note**: You do NOT need the $60/month Nasdaq Basic OpenAPI subscription.

---

## Quick Reference Commands

```bash
# Sunday workflow
python universe_builder.py          # Every 2 weeks
python earnings_monitor.py          # Check earnings
python vix_monitor.py --status      # Check VIX regime
python main.py wheel --capital 6700 # Scan candidates

# Daily workflow
python vix_monitor.py               # Log VIX (morning)
python vix_monitor.py --status      # Quick check (anytime)
python vix_monitor.py --history     # Review history

# Utilities
python earnings_monitor.py --cleanup  # Remove old reports
python vix_monitor.py --history -n 20 # Extended history
```

---

## Disclaimer

This scanner is for educational purposes. Always verify candidates manually before trading. Past performance does not guarantee future results. Options trading involves significant risk of loss.
