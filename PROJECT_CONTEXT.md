# Project Context - MooMoo Options Scanner

## Project Overview
Options income scanner for Wheel Strategy and Volatility Harvesting using MooMoo API.
Conservative fundamental screening combined with options-specific technical filters.

## Current Phase
**Universe Builder v2.0 Complete (2026-01-25)**

### Recent Session - Sector-Aware Scoring & Filter Exemptions
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
