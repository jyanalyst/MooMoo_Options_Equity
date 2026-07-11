# Project Context - MooMoo Options Scanner

## Project Overview
Options income scanner for Wheel Strategy and Volatility Harvesting using MooMoo API.
Conservative fundamental screening combined with options-specific technical filters.

## Current Phase
**Universe Builder v3.0 — Minimalist CSP Rewrite (2026-06-13)**

Rebuilt `universe_builder.py` from ~4,200 lines to ~330 as a simple, robust cash-secured-put idea
generator (a CSP universe needs ownable + liquid + affordable names, not a deep-value gauntlet).
Output schema and `universe.py` helper surface are unchanged (downstream contract preserved).

- **Pipeline:** 1 FMP `company-screener` call → free client-side prune (ETF/fund/inactive/biotech,
  rank by dollar volume, cap to `FUNDAMENTAL_POOL_CAP=200`) → 1 `ratios-ttm` call/name → profitability
  gate → sector-aware score → sector-diversified greedy fill → write. **≈160 cold FMP calls, ~0 warm**
  (was 360–1,150, over the 250/day cap). Fully non-interactive — removed all `input()` prompts.
- **Gate simplified to profitability only** (positive TTM operating margin). Dropped the Altman-Z /
  Piotroski / analyst-buy% / FCF / ROE-consistency machinery, AND the Debt/Equity & Current-Ratio hard
  cuts — those are unreliable for mega-caps (buybacks → negative book equity; CR < 1 is normal) and
  were ejecting blue chips (ADBE, ORCL, PEP, HD, UNH, T, VZ, utilities). Bank/staple exemptions are no
  longer needed. Verified: gate keeps 188/200, dropping only genuinely unprofitable names (INTC, BA, SNOW…).
- **Scoring:** sector-aware percentile of operating margin (30%), net margin (25%), gross margin (20%),
  liquidity (25%); single-stock/missing → neutral 0.5. (Net margin, not ROE: ratios-ttm returns it in
  the same single call and it isn't distorted by buyback-shrunken book equity.) **Diversity:** single 35% dominance cap via
  quality-first greedy fill — removed `min N per sector` (force-included low quality) and the crypto
  penalty (MSTR-type proxies kept by user choice; discretion at trade time).
- Verified end-to-end: dry-run (no writes, 0 prompts), real build (60 names, backup created), downstream
  import + capital filter + scanner `--mock` rank, and `pytest` (55 passed / 1 skipped).

### [Superseded by v3.0] v2.0 - Sector-Aware Scoring & Filter Exemptions (2026-01-25)
Fixed universe builder producing 18 stocks instead of 25-30:

1. **Sector-Aware Percentile Scoring** - Stocks now ranked within sector peers
   - PG score improved: 43 → 61.6 (comparing to KO/STZ, not MSFT)
   - Consumer Defensive stocks no longer penalized vs. Tech margins

2. **Financial Services Exemptions** - Banks excluded from irrelevant filters
   - Current Ratio: Banks have CR < 0.5 by design (deposits = liabilities)
   - Debt/Equity: Deposits are "debt", D/E meaningless for banks
   - FCF Validation: Banks don't generate traditional FCF
   - Outlier Detection: Exempted from CR/D/E outlier removal

3. **Consumer Defensive FCF Exemption** - Retailers like WMT operate on thin margins
   - WMT FCF Margin 1.9% now passes (high volume/low margin is their model)

4. **Crypto Penalty** - COIN, MARA, RIOT treated as cyclicals
   - 20% score penalty applied
   - Counts toward cyclical limit (max 3)

### Current Universe Stats
- **28 stocks** (target 25-30)
- **9 sectors** represented (min 5 required)
- **3 cyclicals** (max 3 limit)
- Top Consumer Defensive: MNST (79.7), KO (71.6), PG (61.6), HSY (54.8), STZ (54.7)
- Banks in pool but hit sector limit: JPM (42.3), WFC (40.4), USB (38.6)

## Completed Work

### Quant-Correctness Fixes (2026-06-01)
Fixed two statistically-flawed calculations that were silently misranking candidates
(scope: math correctness only; efficiency/robustness deferred):

1. **IV richness now uses a real IV Percentile** ([iv_analyzer.py](iv_analyzer.py))
   - Old "IV Rank" compared *current implied* vol against the min/max of *20-day realized*
     vol — an apples-to-oranges ratio biased toward 100 by the variance risk premium.
   - Each scan now appends today's ATM implied vol per ticker to `iv_history.json`
     (one obs/ticker/day, capped at 252) and computes IV Percentile against that
     self-consistent series.
   - Graceful warm-up: until `min_observations` (20) daily samples exist, falls back to
     the realized-vol proxy labeled `iv_method = "hv_proxy_provisional"`; switches to
     `iv_percentile` automatically once warmed up. New `iv_method` column in scan CSV.

2. **Premium yield is now annualized** ([screener_wheel.py](screener_wheel.py))
   - Ranking previously used raw `premium/strike`, so a 30-DTE and 45-DTE contract paying
     the same % scored identically. Now scored on `× 365/DTE`. Raw `return_pct` retained
     for display; new `annualized_return_pct` column drives the premium/quality scores.

Tests: [tests/test_quant_fixes.py](tests/test_quant_fixes.py) — 28 passing
(annualization scaling, IV percentile bounds/known-values, same-day overwrite, cap,
invalid-IV guards, warm-up vs. warmed labeling; optional Hypothesis block).

### Core Infrastructure
- **FMP Data Fetcher** ([fmp_data_fetcher.py](fmp_data_fetcher.py))
  - SEC-sourced fundamental data
  - 5 Tier 1 advanced feature endpoints
  - 90-day cache for financial scores

- **Universe Builder** ([universe_builder.py](universe_builder.py))
  - Sector-aware percentile scoring (within-sector ranking)
  - Sector-specific filter exemptions (Financial Services, Consumer Defensive)
  - Crypto ticker penalty system
  - Sector diversity constraints with required minimums
  - Blue-chip diagnostic function

- **Screeners**
  - Wheel Strategy ([screener_wheel.py](screener_wheel.py))

### Filter Exemptions Summary
| Filter | Financial Services | Consumer Defensive |
|--------|-------------------|-------------------|
| Current Ratio | Full exempt | Partial (allow 0.6-1.0) |
| Debt/Equity | Full exempt | Standard (< 1.0) |
| FCF Validation | Full exempt | Full exempt |
| Analyst Buy% | Full exempt | Full exempt |
| Piotroski Score | Standard | Full exempt |
| Outlier Detection | Exempt CR/D/E | Standard |

## Known Limitations

### Missing Blue-Chips
- **AAPL**: Not in FMP S&P 500 constituent list (API issue)
- **WMT**: In pool (score 50.5) but ranked #6 in Consumer Defensive
- **BAC**: Legitimately fails quality threshold (score 25.4 < 30)

### By Design
- Traditional banks (JPM, WFC, USB) in pool but hit sector limit
- V, SPGI, CME selected over traditional banks (better Wheel candidates)
- Cyclical limit of 3 prevents commodity overweight

## Key Architecture Decisions

### IV Percentile over self-consistent IV history; annualized yield for ranking (2026-06-01)
- IV richness measured as IV Percentile against a persisted daily ATM-IV series, not
  against realized vol (which is a different quantity and biases the metric high).
- Cross-stock candidate ranking uses annualized premium yield (`× 365/DTE`) so contracts
  of different DTE are comparable. Raw yield kept only for display.

### Sector-Aware Scoring
- Each metric ranked within sector using percentile
- Single-stock sectors get neutral 50th percentile
- Prevents margin-based metrics from penalizing defensive stocks

### Sector Diversity Constraints
```python
SECTOR_DIVERSITY_CONSTRAINTS = {
    'max_per_sector': 5,
    'max_sector_pct': 0.30,
    'min_sectors': 5,
    'max_cyclical_total': 3,
    'required_minimum': {
        'Consumer Defensive': 2,
        'Healthcare': 2,
        'Financial Services': 1,
    },
}
```

## Next Steps
1. Consider increasing max_per_sector to 6 if more defensive stocks needed
2. Monitor FMP API for AAPL availability
3. Add forward estimates integration for growth scoring

## Performance Notes
- Universe build: ~3-5 minutes (80 advanced data fetches)
- Cache: 90 days for financial scores
- Bi-weekly rebuild recommended

## Contact & Maintenance
- Last update: 2026-01-25 (Sector-aware scoring + exemptions)
- Next review: 2026-02-08 (bi-weekly universe rebuild)
