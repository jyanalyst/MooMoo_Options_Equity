# Options Income Scanner

Wheel-strategy (cash-secured put) scanner for US equities. **Hybrid data approach**:
- **Stock quotes**: FMP API (real-time, via the shared `fmp_client.py`)
- **Options chains + Greeks**: MooMoo OpenD (OPRA — free with a $3k+ MooMoo balance)
- **Historical prices / IV**: yfinance (free)
- **Fundamentals / earnings / VIX**: FMP API

One entry point: `python main.py wheel`. **Trades are placed manually on MooMoo**;
the scanner is read-only market data, decoupled from order placement.

## Strategy: Wheel (Cash-Secured Puts)

- Quality stocks you would own at the strike price
- Delta 0.20–0.30, DTE 30–45, earnings avoidance with 7-day buffer
- IV Rank (percentile vs persisted IV history) and term structure score the ranking
- **Hard execution-quality filters** (never approximated, never softened):
  - Open interest ≥ 100
  - Bid-ask spread ≤ 10% of mid
  - Premium ≥ 0.5% of strike
  - Missing bid/ask or Greeks ⇒ contract rejected (no fabricated quotes)
- Earnings checking is **fail-closed**: an unverifiable earnings date rejects the
  stock unless you explicitly pass `--allow-unverified`

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

   Regimes (v3.1):
   - STOP (<14): No new trades — premium too low risk-adjusted
   - CAUTIOUS (14-18): Reduced deployment — 50% normal size
   - NORMAL (18-25): Standard deployment — 100% size
   - AGGRESSIVE (>25): 150% size, max 4 positions

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
1. Execute planned trades from Sunday scan (manually, on MooMoo)

2. If entering a trade, import/update the journal:
   python trade_journal.py import <MooMoo positions CSV>


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
[ ] VIX regime noted (STOP/CAUTIOUS/NORMAL/AGGRESSIVE) — no new trades in STOP
[ ] Position size adjusted for VIX regime
[ ] Quality score >55 (from universe.py)
[ ] Delta within 0.20-0.30 range
[ ] DTE 30-45 days
[ ] No earnings within DTE + buffer
[ ] OI >= 100 and spread <= 10% (enforced by the scanner's hard filters)
```

---

## Installation

```bash
pip install -r requirements.txt

# FMP API key (Starter plan sufficient): put it in .env at the repo root
echo FMP_API_KEY=your_key_here > .env

# Make sure MooMoo OpenD is running and logged in (127.0.0.1:11111)
```

## Usage

### Main Scanner
```bash
python main.py wheel                    # Scan for Wheel candidates
python main.py wheel --capital 6700     # Stocks requiring <=$6,700/position
python main.py wheel -i                 # Interactive candidate details
python main.py wheel --quiet            # Minimal output
python main.py --mock wheel             # Offline test run (no network, no writes)
```

### Earnings Monitor
```bash
python earnings_monitor.py              # Generate earnings calendar CSV
python earnings_monitor.py --console    # Console output only
python earnings_monitor.py --cleanup    # Remove reports older than 70 days
```

### VIX Monitor
```bash
python vix_monitor.py                   # Check VIX and log to monthly CSV
python vix_monitor.py --status          # Current regime (no logging)
python vix_monitor.py --history         # Last 10 readings
python vix_monitor.py --history -n 20   # Last 20 readings
```

### Universe Builder
```bash
python universe_builder.py              # Refresh universe (every 2 weeks)
python universe_builder.py --dry-run    # Preview without writing
git diff universe.py                    # Review changes
```

### Trade Journal
```bash
python trade_journal.py import <csv>    # Import MooMoo positions export
python trade_journal.py stats           # Performance dashboard
python trade_journal.py open            # Open positions
python trade_journal.py sector          # Sector exposure report
```

### Tests
```bash
python -m pytest tests/ -v              # Full suite (offline — mock is the CI gate)
```

---

## Output Files

### Scan Results
- `scan_results/wheel_candidates_YYYY-MM-DD.csv`

### Earnings Calendar
- `reports/earnings/earnings_calendar_YYYY-MM-DD.csv`
- Status values: SAFE, CAUTION (<30 days), AVOID (<14 days), UNVERIFIED

### VIX History
- `reports/vix/vix_history_YYYY-MM.csv` (monthly append-only)

---

## Configuration

- `.env` — `FMP_API_KEY=...` (gitignored; the env var wins over any fallback)
- `config.py` — strategy parameters (delta/DTE ranges, hard-filter thresholds,
  earnings buffers, IV-rank settings)
- `universe.py` — **auto-generated** by universe_builder.py; never hand-edit

---

## Architecture

```
options_scanner/
├── main.py                 # Entry point (MooMoo options source)
├── config.py               # Strategy parameters + .env loading
├── universe.py             # Stock universe + metadata (AUTO-GENERATED)
├── universe_builder.py     # Bi-weekly universe refresh
│
├── fmp_client.py           # THE single FMP HTTP path (cache + throttle + retry)
├── data_fetcher.py         # MooMoo options + FMP quotes + yfinance history
├── iv_analyzer.py          # IV Percentile & term structure
├── earnings_checker.py     # Scan-time earnings validation (fail-closed)
├── screener_wheel.py       # Wheel screening + hard filters + scoring
├── output_formatter.py     # Terminal display + CSV export
│
├── earnings_monitor.py     # Weekly earnings calendar CSV
├── vix_monitor.py          # VIX regime tracking (canonical regime source)
├── trade_journal.py        # MooMoo CSV import + performance analytics
│
├── tests/                  # Offline test suite (~90 tests)
├── docs/                   # Strategy guides + reference docs
├── reports/                # earnings/ + vix/ CSVs
├── scan_results/           # Scanner output CSVs
└── requirements.txt
```

Data-flow rule: **every FMP request goes through `fmp_client.get_client()`** —
one shared session, retry/backoff, a thread-safe 1 req/s throttle (Starter plan),
and a TTL file cache under `cache/` (errors are never cached).

---

## VIX Regime Guide (v3.1)

| VIX Level | Regime | Position Sizing | Action |
|-----------|--------|-----------------|--------|
| <14 | STOP | 0% | No new trades — premium too low risk-adjusted |
| 14-18 | CAUTIOUS | 50% | Reduced deployment |
| 18-25 | NORMAL | 100% | Standard deployment |
| >25 | AGGRESSIVE | 150% | Max opportunity, max 4 positions |

**Threshold alerts**: vix_monitor.py alerts when crossing 14, 18, or 25.
`vix_monitor.get_regime()` is the single source of truth for these bands.

---

## Strategy Rules Reference

### Wheel Strategy
- Max 80% capital allocation
- Max 20% per position (adjust by VIX regime)
- 6-8 concurrent positions
- 50% profit target, 21 DTE exit
- Never trade through earnings (+ buffer)

---

## Requirements

- **Python 3.11+**
- **FMP API key** — quotes, fundamentals, earnings, VIX (Starter plan: 250 calls/day, 1 req/s)
- **MooMoo OpenD** — running and logged in locally for options data
- **OPRA data on MooMoo** — free with a $3k+ account balance
- **yfinance** — historical prices / IV (free)

**Note**: Trades are placed manually on MooMoo; the scanner only reads market data.

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
python trade_journal.py stats       # Journal check

# Verification
python -m pytest tests/ -v          # Offline test suite
python main.py --mock wheel         # Offline end-to-end smoke
```

---

## Disclaimer

This scanner is for educational purposes. Always verify candidates manually before
trading. Past performance does not guarantee future results. Options trading involves
significant risk of loss.
