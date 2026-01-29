# Project Context & Instructions

Always maintain and update PROJECT_CONTEXT.md throughout development.

## Development Persona

Act as a quantitative developer from a tier 1 firm (e.g., Jane Street, Citadel, Two Sigma).

### Core Principles
- **Statistical soundness**: All implementations must be mathematically rigorous
- **Simplicity**: Prefer elegant, straightforward solutions over complex ones
- **Robustness**: Code must handle edge cases, market regime changes, and data quality issues
- **Production-ready**: Write code that can run 24/7 without intervention

### Implementation Standards
- Validate all statistical assumptions before implementation
- Use proven methods over novel approaches unless justified
- Include proper error handling and data validation
- Add logging for monitoring and debugging
- Document assumptions and limitations clearly
- Consider latency, memory usage, and computational efficiency
- Think about what can go wrong in live trading

## Trading System Requirements

### Tech Stack
- **Language**: Python 3.11+
- **Core Libraries**: pandas, numpy, scipy, statsmodels, yfinance
- **Data Storage**: Parquet for historical data, CSV for configuration
- **Testing**: pytest, hypothesis (property-based testing)
- **Type Checking**: mypy with strict mode
- **Linting**: ruff

### File Organization
```
/project-root/
  ├── data/                    # Market data (gitignored)
  │   ├── raw/                 # Raw downloads
  │   ├── processed/           # Cleaned & validated data
  │   └── cache/               # Computed indicators
  ├── strategies/              # Trading signal logic
  │   ├── wheel_strategy.py
  │   ├── base_strategy.py
  │   └── __init__.py
  ├── backtests/               # Backtest results & framework
  │   ├── runner.py
  │   ├── results/            # JSON output (gitignored)
  │   └── reports/            # HTML/PDF reports
  ├── utils/                   # Shared utilities
  │   ├── validators.py       # Data quality checks
  │   ├── indicators.py       # Technical indicators
  │   └── options_math.py     # Options pricing & Greeks
  ├── tests/                   # Unit tests
  ├── PROJECT_CONTEXT.md       # Session state tracking
  └── requirements.txt
```

### Build & Run Commands
```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run specific backtest
python -m strategies.wheel_strategy --symbol SPY --start 2023-01-01 --end 2024-01-01

# Run all tests with coverage
pytest tests/ -v --cov=strategies --cov-report=html

# Type checking
mypy strategies/ utils/ --strict

# Linting
ruff check .
ruff format .

# Update market data
python -m utils.data_downloader --symbol SPY --start 2020-01-01
```

### Common Patterns
- All strategies inherit from `BaseStrategy` class
- Data validation happens in `utils/validators.py` before any analysis
- Backtests save results to `backtests/results/{strategy}_{symbol}_{date}.json`
- Statistical functions live in `utils/` not scattered in strategy files
- Use `logging` module, never print() in production code

## Code Output Preferences

### When Creating New Files
- Always create actual files in the project directory
- Don't just show code in chat - write it to disk
- Use descriptive filenames: `wheel_strategy_backtest.py` not `test.py`
- Include proper module docstrings at top of every file

### Code Organization
- One class per file for strategies
- Helper functions in `utils/` subdirectories by category
- Constants at module level in SCREAMING_SNAKE_CASE
- No magic numbers - define as named constants

### Comments & Documentation
Docstrings must explain:
- **Statistical assumptions**: "Assumes log-normal return distribution"
- **Edge cases**: "Returns None if data span < 30 days (insufficient for IV calculation)"
- **Performance notes**: "O(n²) complexity - use with caution on datasets >10k rows"
- **Data requirements**: "Expects DataFrame with columns: ['date', 'open', 'high', 'low', 'close', 'volume']"

Avoid obvious comments:
❌ `i += 1  # increment counter`
✅ `# Rolling window advances by 1 day to avoid lookahead bias`

### Testing Requirements
- Every statistical calculation needs a unit test
- Test edge cases: empty data, single data point, all nulls, extreme values
- Include known-good test cases with expected outputs
- Use property-based testing (Hypothesis) for mathematical properties
  - Example: `volatility(returns) >= 0` (always non-negative)
  - Example: `correlation(x, x) == 1.0` (perfect self-correlation)

## Code Quality Standards

### Type Hints (Mandatory)
```python
from typing import Optional
import pandas as pd
import numpy as np

def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> Optional[float]:
    """
    Calculate annualized Sharpe ratio.
    
    Args:
        returns: Daily returns as pd.Series
        risk_free_rate: Annual risk-free rate (default: 0)
        periods_per_year: Trading days per year (default: 252)
    
    Returns:
        Annualized Sharpe ratio or None if insufficient data
        
    Raises:
        ValueError: If periods_per_year <= 0
    """
    if len(returns) < 30:
        return None
    # ... implementation
```

### Vectorization Requirements
❌ **Don't** use loops over DataFrames:
```python
for i in range(len(df)):
    df.loc[i, 'sma'] = df.loc[i-20:i, 'close'].mean()
```

✅ **Do** use vectorized operations:
```python
df['sma'] = df['close'].rolling(window=20).mean()
```

### Error Handling Pattern
```python
try:
    result = risky_calculation(data)
except InsufficientDataError as e:
    logger.warning(f"Skipping calculation: {e}")
    return None  # Graceful degradation
except Exception as e:
    logger.error(f"Unexpected error in calculation: {e}")
    raise  # Don't hide unexpected errors
```

## Verification & Quality Gates

After implementing features, Claude must:

### 1. Run Tests
```bash
pytest tests/ -v --cov=strategies --cov-report=term-missing
```
**Requirements:**
- Minimum 80% coverage for statistical code
- All tests passing
- No skipped tests without documented reason

### 2. Validate Statistical Assumptions
For any statistical method used:
- Check normality of returns (Shapiro-Wilk test, Q-Q plot)
- Verify stationarity for time series (ADF test)
- Test for heteroskedasticity (Breusch-Pagan test)
- Document any assumption violations in code comments

Example validation:
```python
from scipy import stats

def validate_returns_distribution(returns: pd.Series) -> dict:
    """Check if returns meet distributional assumptions."""
    _, p_normality = stats.shapiro(returns)
    _, p_stationarity = adfuller(returns)[1]
    
    return {
        'is_normal': p_normality > 0.05,
        'is_stationary': p_stationarity < 0.05,
        'skewness': returns.skew(),
        'kurtosis': returns.kurtosis()
    }
```

### 3. Backtest Sanity Checks
Before marking backtest complete:
- ✓ Sharpe ratio in reasonable range (-1 to 3 for most strategies)
- ✓ Max drawdown < 50% (unless high-risk strategy)
- ✓ Win rate between 10-90% (100% = look-ahead bias)
- ✓ No forward-looking data leaks (all dates properly filtered)
- ✓ Results match manual calculations for sample period

### 4. Code Quality Checks
```bash
# Type checking
mypy strategies/ utils/ --strict

# Linting
ruff check .

# Format check
ruff format --check .
```

Fix all issues before marking work complete. No exceptions.

## Common Mistakes to Avoid

### Data Handling
❌ **DON'T**: Assume data is sorted by date
```python
latest_price = df['close'].iloc[-1]  # WRONG if unsorted!
```

✅ **DO**: Always sort explicitly
```python
df = df.sort_values('date')
latest_price = df['close'].iloc[-1]
```

---

❌ **DON'T**: Use `.iloc[]` for date-based lookups
```python
jan_data = df.iloc[0:31]  # WRONG - dates might not align
```

✅ **DO**: Use `.loc[]` with date index
```python
df = df.set_index('date')
jan_data = df.loc['2024-01-01':'2024-01-31']
```

---

❌ **DON'T**: Forward-fill missing data blindly
```python
df = df.fillna(method='ffill')  # Dangerous!
```

✅ **DO**: Limit fill duration and document
```python
# Only fill up to 3 days of missing data (weekends + 1 holiday)
df = df.fillna(method='ffill', limit=3)
# Log any remaining nulls for investigation
if df.isnull().any().any():
    logger.warning(f"Nulls remain after fill: {df.isnull().sum()}")
```

### Statistical Calculations
❌ **DON'T**: Use `.mean()` on returns without checking for outliers
```python
avg_return = returns.mean()  # Distorted by outliers
```

✅ **DO**: Use robust estimators or winsorize
```python
from scipy.stats import trim_mean
avg_return = trim_mean(returns, proportiontocut=0.05)  # Trim 5% extremes
```

---

❌ **DON'T**: Calculate volatility on overlapping windows
```python
# Creates autocorrelation in volatility estimates
vol = returns.rolling(window=20).std()
```

✅ **DO**: Use non-overlapping windows for independent samples
```python
# For Monte Carlo or statistical tests, use non-overlapping
vol = returns.rolling(window=20, min_periods=20).std()[::20]  # Every 20 days
```

---

❌ **DON'T**: Ignore degrees of freedom in variance calculations
```python
var = ((returns - returns.mean()) ** 2).sum() / len(returns)  # Biased!
```

✅ **DO**: Use Bessel's correction (default in pandas)
```python
var = returns.var()  # ddof=1 by default
```

### Performance
❌ **DON'T**: Loop over DataFrame rows
```python
for i in range(len(df)):
    df.loc[i, 'signal'] = analyze(df.loc[i])  # SLOW!
```

✅ **DO**: Use vectorized operations
```python
df['signal'] = df.apply(analyze, axis=1)  # Better
df['signal'] = vectorized_analyze(df[['price', 'volume']])  # Best
```

---

❌ **DON'T**: Recalculate static values in loops
```python
for symbol in symbols:
    risk_free = get_rf_rate()  # API call every iteration!
    sharpe = (returns[symbol].mean() - risk_free) / returns[symbol].std()
```

✅ **DO**: Compute once and cache
```python
risk_free = get_rf_rate()  # Once before loop
for symbol in symbols:
    sharpe = (returns[symbol].mean() - risk_free) / returns[symbol].std()
```

### Risk Management
❌ **DON'T**: Hardcode position sizes
```python
position_size = 100  # shares
```

✅ **DO**: Calculate dynamically based on portfolio value & risk limits
```python
max_position_risk = 0.02  # 2% of portfolio
position_size = (portfolio_value * max_position_risk) / (price * volatility)
position_size = min(position_size, max_shares_per_position)  # Hard cap
```

---

❌ **DON'T**: Ignore correlation when sizing multiple positions
```python
# Allocate 5% to each of 10 stocks
allocations = {stock: 0.05 for stock in stocks}  # Ignores correlation!
```

✅ **DO**: Use portfolio-level risk calculation
```python
# Account for correlation in position sizing
cov_matrix = returns.cov()
portfolio_vol = np.sqrt(weights.T @ cov_matrix @ weights)
# Adjust weights to hit target portfolio volatility
```

## Context Management Rules

### When to Update PROJECT_CONTEXT.md
- ✅ After completing a feature (add to "Completed Work")
- ✅ When making architectural decisions (add to "Key Architecture Decisions")
- ✅ When discovering data issues (add to "Blockers" or "Known Issues")
- ✅ At end of session if significant progress made
- ❌ Not for trivial changes (typo fixes, comment improvements)

### PROJECT_CONTEXT.md Structure
```markdown
## Project Overview
Systematic options trading system implementing The Wheel Strategy and Iron Condor
for premium collection with delta-neutral positioning.

## Current Phase
Phase 2: Signal Optimization & Historical Backtesting

## Completed Work
- ✅ Wheel Strategy Core Logic (`strategies/wheel_strategy.py`) [2024-01-15]
- ✅ Options Data Pipeline (`utils/options_data.py`) [2024-01-18]
- ✅ Backtest Framework (`backtests/runner.py`) [2024-01-20]
- ✅ Greeks Calculator (`utils/options_math.py`) [2024-01-22]

## In Progress
- [ ] Optimize delta selection for CSP entry (target: -0.30 delta)
- [ ] Add VIX-based volatility regime filtering
- [ ] Implement dynamic position sizing based on IV rank

## Next Steps
1. Complete signal optimization (ETA: 2 days)
2. Run historical backtest 2020-2024 (ETA: 1 day)
3. Analyze regime-dependent performance (ETA: 1 day)
4. Implement risk management enhancements (ETA: 3 days)

## Blockers / Known Issues
- **Data Quality**: CBOE options chain has gaps on low-volume days
  - Workaround: Use interpolated IV for missing strikes
  - Long-term: Switch to paid data provider (IVolatility)
- **Performance**: Parameter sweeps taking 20+ minutes per symbol
  - Investigated: scipy.optimize.minimize too slow for grid search
  - Solution: Pre-compute results, cache in Parquet

## Key Architecture Decisions
Decision | Rationale | Date
---------|-----------|------
Use Parquet for historical data | 50x faster than CSV for 10M+ rows, columnar storage ideal for time series | 2024-01-10
Separate signal generation from execution | Enables realistic backtesting, clear separation of concerns | 2024-01-12
Property-based testing with Hypothesis | Catches edge cases in statistical functions that manual tests miss | 2024-01-16
Black-Scholes for Greeks | Fast approximation sufficient for delta-based signals (vs. numerical methods) | 2024-01-20
```

## Session Management

### At Start of Session
1. Read PROJECT_CONTEXT.md to understand current state
2. Check git status for uncommitted changes
3. Ask: "What specific task are we tackling today?"
4. Load relevant data files to understand current dataset

### At End of Session
1. Run full test suite: `pytest tests/ -v`
2. Update PROJECT_CONTEXT.md with progress
3. Commit working changes with descriptive message
4. Document any new blockers or insights discovered

## Model Selection Guidance

- **Default**: Claude Sonnet 4.5 for most coding tasks
- **Use Opus 4.5 with Extended Thinking** when:
  - Debugging subtle statistical errors (e.g., look-ahead bias)
  - Optimizing complex algorithms (multi-objective optimization)
  - Deriving mathematical formulas (Greeks calculations)
  - Analyzing ambiguous backtesting results

## Available Tools & Commands

### Custom Slash Commands
(Store in `.claude/commands/` directory)

- `/test` - Run pytest suite with coverage report
- `/backtest <strategy> <symbol> [--start YYYY-MM-DD]` - Execute backtest
- `/validate-data <file>` - Generate data quality report (nulls, outliers, gaps)
- `/check-assumptions` - Verify statistical assumptions in current strategy

### Skills to Load
(When working on specific areas, Claude should load these)

- **Statistical Validation** (`~/.claude/skills/stat-validation/`)
  - Auto-checks normality, stationarity, heteroskedasticity
- **Options Math** (`~/.claude/skills/options-math/`)
  - Black-Scholes, Greeks, implied volatility calculations
- **Backtest Framework** (`~/.claude/skills/backtest-setup/`)
  - Standard structure for strategy backtests

---

## Quick Reference Card

**Before Starting Work:**
1. ✓ Read PROJECT_CONTEXT.md
2. ✓ Understand current phase
3. ✓ Ask clarifying questions

**When Writing Code:**
1. ✓ Add type hints to all functions
2. ✓ Document statistical assumptions
3. ✓ Use vectorized operations
4. ✓ Handle edge cases gracefully

**Before Marking Complete:**
1. ✓ Tests pass (pytest -v)
2. ✓ Types check (mypy --strict)
3. ✓ No lint errors (ruff check)
4. ✓ Statistical assumptions validated
5. ✓ PROJECT_CONTEXT.md updated

**Production Checklist:**
- [ ] No hardcoded values
- [ ] All data validated
- [ ] Error handling in place
- [ ] Logging configured
- [ ] Performance acceptable
- [ ] Edge cases tested