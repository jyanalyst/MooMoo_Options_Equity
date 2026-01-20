# MOOMOO OPENAPI REFERENCE GUIDE
## For ETF Options Spreads Scanner Project

**Version:** 9.6.5608 (Latest as of Dec 17, 2025)  
**Project:** Automated ETF Bull Put Spreads Scanner  
**Target Markets:** US Options (SPY, QQQ, IWM, Sector ETFs)

---

## TABLE OF CONTENTS

1. [Architecture Overview](#architecture-overview)
2. [Installation & Setup](#installation--setup)
3. [Quote Data Access](#quote-data-access)
4. [Options Chain Retrieval](#options-chain-retrieval)
5. [Greeks & Market Data](#greeks--market-data)
6. [Trading Functions](#trading-functions)
7. [Subscription Quotas & Limits](#subscription-quotas--limits)
8. [Common Errors & Solutions](#common-errors--solutions)
9. [Code Examples](#code-examples)
10. [Best Practices](#best-practices)

---

## ARCHITECTURE OVERVIEW

### Components

**MooMoo OpenD (Gateway Program)**
- Runs locally or on cloud server
- Default host: `127.0.0.1`
- API port: `11111` (TCP protocol)
- WebSocket port: `33333`
- Acts as bridge between your code and MooMoo servers

**MooMoo API SDK**
- Python package: `moomoo-api` (v9.6.5608)
- Languages supported: Python, Java, C#, C++, JavaScript
- Installation: `pip install moomoo-api`

### Connection Flow

```
Your Python Script â†’ OpenQuoteContext/OpenSecTradeContext â†’ OpenD (Port 11111) â†’ MooMoo Servers â†’ Exchange Data
```

---

## INSTALLATION & SETUP

### Step 1: Install OpenD Gateway

**Download:**
- Official site: https://www.moomoo.com/download/OpenAPI
- Supports: Windows, MacOS, CentOS, Ubuntu

**Launch OpenD:**
1. Start OpenD application
2. Login with MooMoo ID and password
3. Verify connection status shows "Connected"
4. Default ports: 11111 (API), 33333 (WebSocket)

### Step 2: Install Python API

```bash
pip install moomoo-api
```

**Dependencies (auto-installed):**
- protobuf==3.20.3
- pandas
- numpy

### Step 3: Verify Connection

```python
from moomoo import *

# Create quote context
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Test connection
ret, data = quote_ctx.get_market_snapshot(['US.SPY'])
if ret == RET_OK:
    print("âœ… Connected successfully")
    print(data)
else:
    print(f"âŒ Error: {data}")

quote_ctx.close()
```

---

## QUOTE DATA ACCESS

### Market Data Authority Requirements

**To access US market data via API, you MUST have:**

1. **US Securities Authority** (Required for underlying stocks/ETFs)
   - Subscribe to "National LV1" ($5/month) via MooMoo app/desktop
   - Covers NYSE, NASDAQ, Arca exchanges
   - Without this: `No right to get the quote for US.SPY` error

2. **US Options Authority** (Required for options data)
   - FREE if total assets > $3,000 USD
   - Otherwise: $2.99/month OPRA Options Real-time
   - Auto-included once US Securities authority is active

### Data Context Types

**OpenQuoteContext** - For market data (read-only)
```python
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
# Use for: prices, options chains, Greeks, historical data
```

**OpenSecTradeContext** - For trading (requires unlock)
```python
trd_ctx = OpenSecTradeContext(filter_trdmarket=TrdMarket.US, 
                               host='127.0.0.1', port=11111)
ret, data = trd_ctx.unlock_trade(pwd='your_trading_password')
# Use for: placing orders, viewing positions, account info
```

### Paper Trading vs Live Data

**Paper Trading Context:**
```python
# Paper trading has FREE full market data access
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
# No additional subscriptions needed for data access
```

**Live Trading Context:**
```python
trd_ctx = OpenSecTradeContext(
    filter_trdmarket=TrdMarket.US,
    host='127.0.0.1', 
    port=11111,
    security_firm=SecurityFirm.MOOMOOSG  # or FUTUSECURITIES
)
ret = trd_ctx.unlock_trade(pwd='123456')
```

---

## OPTIONS CHAIN RETRIEVAL

### Get Option Expiration Dates

**Function:** `get_option_expiration_date(code)`

```python
from moomoo import *

quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Get all expiration dates for SPY
ret, data = quote_ctx.get_option_expiration_date(code='US.SPY')

if ret == RET_OK:
    print(data)
    # Returns DataFrame with columns: strike_time, strike_timestamp
else:
    print(f"Error: {data}")

quote_ctx.close()
```

**Output Example:**
```
  strike_time  strike_timestamp
0  2025-01-10    1736467200
1  2025-01-17    1737072000
2  2025-01-24    1737676800
```

### Get Option Chain

**Function:** `get_option_chain(code, start, end, option_type, data_filter)`

**Parameters:**
- `code` (str): Underlying symbol (e.g., 'US.SPY')
- `start` (str): Start expiration date 'YYYY-MM-DD'
- `end` (str): End expiration date 'YYYY-MM-DD'
- `option_type` (OptionType): `ALL`, `CALL`, or `PUT`
- `data_filter` (OptionDataFilter): Filter by delta, strike, OI, etc.

**OptionDataFilter Fields:**
```python
filter1 = OptionDataFilter()
filter1.delta_min = 0.15       # Minimum delta
filter1.delta_max = 0.25       # Maximum delta
filter1.strike_min = 580.0     # Minimum strike price
filter1.strike_max = 620.0     # Maximum strike price
filter1.vol_min = 1000         # Minimum contract volume
filter1.oi_min = 1000          # Minimum open interest
filter1.implied_volatility_min = 0.1  # Min IV
filter1.implied_volatility_max = 0.5  # Max IV
filter1.in_out_money = OptionCondType.ALL  # ALL, ITM, OTM, ATM
```

**Example: Get PUT options with delta 0.15-0.25**

```python
from moomoo import *
import time

quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Step 1: Get expiration dates
ret1, data1 = quote_ctx.get_option_expiration_date(code='US.SPY')

if ret1 == RET_OK:
    # Step 2: Filter for 30-45 DTE
    expiration_dates = data1['strike_time'].values.tolist()
    target_dates = [d for d in expiration_dates if 30 <= days_to_expiry(d) <= 45]
    
    # Step 3: Set up filter for short put delta
    filter1 = OptionDataFilter()
    filter1.delta_min = -0.25  # PUT deltas are negative
    filter1.delta_max = -0.15
    filter1.vol_min = 1000     # High volume requirement
    filter1.oi_min = 1000      # High OI requirement
    
    for date in target_dates:
        # Step 4: Get PUT options only
        ret2, data2 = quote_ctx.get_option_chain(
            code='US.SPY',
            start=date,
            end=date,
            option_type=OptionType.PUT,
            data_filter=filter1
        )
        
        if ret2 == RET_OK:
            print(f"\n=== Expiration: {date} ===")
            print(data2[['code', 'strike_price', 'delta', 'open_interest', 'volume']])
        else:
            print(f"Error for {date}: {data2}")
        
        time.sleep(3)  # Rate limit: 3 seconds between calls
else:
    print(f"Error: {data1}")

quote_ctx.close()
```

**Output DataFrame Columns:**
```
code                  # Option symbol (e.g., 'US.SPY250117P00580000')
name                  # Full option name
strike_price          # Strike price (e.g., 580.0)
strike_time           # Expiration date 'YYYY-MM-DD'
option_type           # 'PUT' or 'CALL'
delta                 # Delta (PUT: negative, CALL: positive)
gamma                 # Gamma
theta                 # Theta (daily time decay)
vega                  # Vega
rho                   # Rho
implied_volatility    # Implied volatility
open_interest         # Open interest (contracts)
volume                # Daily volume
bid                   # Bid price
ask                   # Ask price
last_price            # Last traded price
```

---

## GREEKS & MARKET DATA

### Get Real-Time Snapshot (Includes Greeks)

**Function:** `get_market_snapshot(code_list)`

```python
from moomoo import *

quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Get snapshot for multiple options
option_codes = [
    'US.SPY250117P00590000',  # SPY $590 PUT Jan 17
    'US.SPY250117P00575000'   # SPY $575 PUT Jan 17
]

ret, data = quote_ctx.get_market_snapshot(option_codes)

if ret == RET_OK:
    print(data[['code', 'last_price', 'bid', 'ask', 
                'delta', 'gamma', 'theta', 'vega',
                'open_interest', 'volume']])
else:
    print(f"Error: {data}")

quote_ctx.close()
```

**Greeks Interpretation:**

| Greek | Meaning | Range | Your Strategy Use |
|-------|---------|-------|-------------------|
| **Delta** | Price change per $1 move in underlying | PUT: 0 to -1<br>CALL: 0 to 1 | Target PUT delta -0.15 to -0.25 for short strike |
| **Gamma** | Rate of delta change | Higher = more risk | Lower gamma = more stable position |
| **Theta** | Daily time decay (your profit source) | Always negative | Higher theta = faster profit on spread |
| **Vega** | Change per 1% IV change | Higher = more volatile | Monitor when VIX changes |
| **Rho** | Change per 1% interest rate change | Less important | Minimal impact on 30-45 DTE |

**For Bull Put Spreads:**
- **Short PUT (higher strike):** Delta -0.15 to -0.25 (you want this close to OTM)
- **Long PUT (lower strike):** Delta -0.10 to -0.15 (protective, 10-15 points below)
- **Net Position:** Positive theta (you profit from time decay)

### Get Historical Price Data

**Function:** `get_history_kline(code, start, end, ktype)`

```python
from moomoo import *

quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Get SPY daily data for regime analysis
ret, data = quote_ctx.get_history_kline(
    code='US.SPY',
    start='2025-01-01',
    end='2025-01-07',
    ktype=KLType.K_DAY,
    autype=AuType.QFQ  # Forward-adjusted
)

if ret == RET_OK:
    print(data[['time_key', 'open', 'high', 'low', 'close', 'volume']])
    # Use to calculate: VWAP, SMA 20, SMA 50
else:
    print(f"Error: {data}")

quote_ctx.close()
```

**K-Line Types:**
- `K_1M`, `K_5M`, `K_15M`, `K_30M`, `K_60M` (intraday)
- `K_DAY` (daily - **use this for regime detection**)
- `K_WEEK`, `K_MON` (longer timeframes)

---

## TRADING FUNCTIONS

### Important: API Cannot Place Multi-Leg Spreads

**âŒ LIMITATION:** MooMoo API's `place_order()` function does NOT support multi-leg options orders (spreads).

**From official documentation:**
> "place_order() only supports single-leg orders. For multi-leg strategies (spreads, straddles, etc.), use the MooMoo app/desktop interface."

**What This Means for Your Strategy:**

**Option A: Hybrid Approach (RECOMMENDED)**
1. Use API to screen and identify best spreads
2. Display top 3-5 spreads with all details (strikes, credit, ROI)
3. Manually execute spreads in MooMoo desktop/mobile app
4. Time cost: ~10 minutes/day

**Option B: Separate Leg Execution (NOT RECOMMENDED)**
1. Place short PUT as separate order via API
2. Immediately place long PUT as separate order
3. Risk: Legs may not fill simultaneously
4. Risk: Slippage between legs
5. Not true spread pricing

**Your Optimal Setup:**
```python
# Scanner outputs best spreads
best_spreads = [
    {
        'underlying': 'SPY',
        'expiration': '2025-01-17',
        'short_put': 590,
        'short_put_code': 'US.SPY250117P00590000',
        'long_put': 575,
        'long_put_code': 'US.SPY250117P00575000',
        'credit': 2.50,
        'max_risk': 12.50,
        'roi': 20.0,
        'delta': -0.18
    }
]

# Display in terminal or export to CSV
print("=== TOP SPY SPREADS ===")
for spread in best_spreads:
    print(f"Sell {spread['short_put']} PUT / Buy {spread['long_put']} PUT")
    print(f"Expiration: {spread['expiration']}")
    print(f"Credit: ${spread['credit']} | ROI: {spread['roi']}%")
    print(f"Max Risk: ${spread['max_risk'] * 100}\n")

# YOU manually execute in MooMoo app
```

### Place Single-Leg Order (Reference Only)

**Function:** `place_order(price, qty, code, trd_side, order_type)`

```python
from moomoo import *

trd_ctx = OpenSecTradeContext(
    filter_trdmarket=TrdMarket.US,
    host='127.0.0.1',
    port=11111
)

# Unlock trading first
ret, data = trd_ctx.unlock_trade(pwd='your_trading_password')

if ret == RET_OK:
    # Example: Sell 1 PUT option (opening short position)
    ret, data = trd_ctx.place_order(
        price=2.50,                      # Limit price
        qty=1,                           # 1 contract
        code='US.SPY250117P00590000',    # Option code
        trd_side=TrdSide.SELL,           # SELL to open short
        order_type=OrderType.NORMAL,     # Limit order
        trd_env=TrdEnv.REAL              # Live trading (use TrdEnv.SIMULATE for paper)
    )
    
    if ret == RET_OK:
        print(f"Order placed: {data}")
    else:
        print(f"Order failed: {data}")
else:
    print(f"Unlock failed: {data}")

trd_ctx.close()
```

**Order Types:**
- `OrderType.NORMAL` - Standard limit order
- `OrderType.MARKET` - Market order (not recommended for options)

**Trade Sides:**
- `TrdSide.BUY` - Buy to open or close short
- `TrdSide.SELL` - Sell to open or close long

---

## SUBSCRIPTION QUOTAS & LIMITS

### Subscription Quota Rules

**What is Subscription Quota?**
- Real-time data subscriptions (e.g., live quotes, order book, tickers)
- Each stock + subscription type = 1 quota used
- Example: SPY quote + QQQ quote = 2 quotas

**Quota Allocation (Based on Account Assets):**

| Total Assets (HKD) | Subscription Quota | Historical Candlestick Quota |
|--------------------|-------------------|------------------------------|
| < 10k | 10 | 50 |
| 10k - 100k | 50 | 200 |
| 100k - 500k | 100 | 500 |
| 500k+ | 200 | 1000 |

**Your Account ($23,538 USD â‰ˆ 183k HKD):**
- Subscription Quota: **100**
- Historical Candlestick Quota: **500** (per 30 days)

**For Your Scanner (Estimated Usage):**
- SPY snapshot: 1 quota
- QQQ snapshot: 1 quota
- IWM snapshot: 1 quota
- VIX snapshot: 1 quota
- SPY historical data: 1 candlestick quota (cached for 30 days)
- **Total: ~4-10 quotas used**

### Rate Limits

**API Request Frequency:**
- **Maximum:** 60 requests per 30 seconds
- **Safe rate:** 1 request every 0.5 seconds
- **If exceeded:** API returns error `RET_ERROR` with "Frequency limitation exceeded"

**For Options Chain Retrieval:**
```python
# BAD: Too fast, will hit rate limit
for exp_date in expiration_dates:
    ret, data = quote_ctx.get_option_chain(code='US.SPY', start=exp_date, end=exp_date)
    # No delay - will fail after ~60 iterations

# GOOD: Respects rate limit
for exp_date in expiration_dates:
    ret, data = quote_ctx.get_option_chain(code='US.SPY', start=exp_date, end=exp_date)
    time.sleep(3)  # 3 second delay between calls
```

**Subscription Duration Requirement:**
- Must keep subscription active for **at least 1 minute**
- Cannot unsubscribe before 1 minute elapses
- Quota released only when ALL connections unsubscribe

---

## COMMON ERRORS & SOLUTIONS

### Error 1: "No right to get the quote for US.SPY"

**Cause:** Missing US Securities quote authority

**Solution:**
1. Open MooMoo app/desktop
2. Go to: **Menu â†’ Market Data â†’ US Market**
3. Subscribe to **"National LV1"** ($5/month)
4. **Restart OpenD completely** (Exit â†’ Reopen)
5. Verify in OpenD: US Securities should show **"LV1"** (not "No Authority")

### Error 2: "Subscription quota exceeded"

**Cause:** Too many simultaneous subscriptions active

**Solution:**
```python
# Check current subscriptions
ret, data = quote_ctx.query_subscription()
if ret == RET_OK:
    print(f"Active subscriptions: {len(data)}")
    print(data)

# Unsubscribe unused tickers
ret, data = quote_ctx.unsubscribe(['US.AAPL'], [SubType.QUOTE])
```

**Prevention:**
- Only subscribe to tickers you actively need
- Unsubscribe when done with analysis
- Use `get_market_snapshot()` instead of subscriptions for one-time queries

### Error 3: "Frequency limitation exceeded"

**Cause:** Making API requests too quickly (>60 per 30 seconds)

**Solution:**
```python
import time

for ticker in tickers:
    ret, data = quote_ctx.get_market_snapshot([ticker])
    time.sleep(0.5)  # Minimum 0.5 second delay
```

### Error 4: "Connection failed" or "InitConnect failed"

**Cause:** OpenD not running or wrong host/port

**Solution:**
1. Verify OpenD is running and logged in
2. Check OpenD settings: Host `127.0.0.1`, Port `11111`
3. Test connection:
```python
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
ret, data = quote_ctx.get_global_state()
if ret == RET_OK:
    print("OpenD connected")
else:
    print(f"Connection failed: {data}")
```

### Error 5: Options chain returns empty DataFrame

**Cause 1:** No options available for specified expiration date
**Solution:** Check if expiration date is valid (not expired, not too far out)

**Cause 2:** Delta filter too restrictive
**Solution:** Widen delta range or remove filter temporarily

**Cause 3:** Insufficient liquidity on that expiration
**Solution:** Move to next weekly or monthly expiration

```python
# Debug: Check what options exist without filters
ret, data = quote_ctx.get_option_chain(
    code='US.SPY',
    start='2025-01-17',
    end='2025-01-17',
    option_type=OptionType.PUT
    # No data_filter - see all options
)

if ret == RET_OK:
    print(f"Total PUT options found: {len(data)}")
    print(data[['strike_price', 'delta', 'open_interest', 'volume']].head(20))
```

---

## CODE EXAMPLES

### Example 1: Complete Spread Screener

```python
from moomoo import *
import pandas as pd
import time
from datetime import datetime, timedelta

class SpreadScanner:
    def __init__(self):
        self.quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
    def calculate_dte(self, expiration_date):
        """Calculate days to expiration"""
        exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
        today = datetime.now()
        return (exp_date - today).days
    
    def get_spy_regime(self):
        """Determine market regime: 1, 2, or 3"""
        # Get SPY daily data for last 60 days
        ret, data = self.quote_ctx.get_history_kline(
            code='US.SPY',
            start=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
            end=datetime.now().strftime('%Y-%m-%d'),
            ktype=KLType.K_DAY
        )
        
        if ret != RET_OK:
            print(f"Error fetching SPY data: {data}")
            return None
        
        # Calculate VWAP anchored to year start (simplified)
        spy_current_price = data.iloc[-1]['close']
        spy_vwap = data['close'].mean()  # Simplified VWAP
        
        # Get VIX
        ret_vix, data_vix = self.quote_ctx.get_market_snapshot(['US.VIX'])
        if ret_vix != RET_OK:
            print(f"Error fetching VIX: {data_vix}")
            return None
        
        vix_level = data_vix.iloc[0]['last_price']
        
        # Determine regime
        if spy_current_price > spy_vwap and vix_level < 18:
            regime = 1  # Clear uptrend
            print(f"âœ… REGIME 1: SPY ${spy_current_price:.2f} > VWAP ${spy_vwap:.2f}, VIX {vix_level:.2f}")
        elif vix_level > 25:
            regime = 3  # Downtrend/High vol
            print(f"âš ï¸ REGIME 3: VIX {vix_level:.2f} elevated")
        else:
            regime = 2  # Choppy
            print(f"âž¡ï¸ REGIME 2: Choppy market, VIX {vix_level:.2f}")
        
        return regime
    
    def scan_spreads(self, underlying='US.SPY', min_dte=30, max_dte=45):
        """Find best bull put spreads"""
        
        # Step 1: Get regime
        regime = self.get_spy_regime()
        if regime is None:
            return []
        
        # Step 2: Set parameters based on regime
        if regime == 1:
            target_delta_min, target_delta_max = -0.20, -0.15
            spread_width = 10
            max_spreads = 4
        elif regime == 2:
            target_delta_min, target_delta_max = -0.25, -0.20
            spread_width = 15
            max_spreads = 2
        else:  # Regime 3
            print("âš ï¸ Regime 3: Avoid trading or max 1 spread")
            return []
        
        # Step 3: Get expiration dates
        ret, exp_data = self.quote_ctx.get_option_expiration_date(code=underlying)
        if ret != RET_OK:
            print(f"Error getting expirations: {exp_data}")
            return []
        
        # Filter for target DTE range
        target_expirations = []
        for exp_date in exp_data['strike_time']:
            dte = self.calculate_dte(exp_date)
            if min_dte <= dte <= max_dte:
                target_expirations.append(exp_date)
        
        print(f"\nTarget expirations (30-45 DTE): {target_expirations}")
        
        # Step 4: Screen options for each expiration
        spreads = []
        
        for exp_date in target_expirations:
            # Set filter for short put
            filter_short = OptionDataFilter()
            filter_short.delta_min = target_delta_min
            filter_short.delta_max = target_delta_max
            filter_short.vol_min = 1000
            filter_short.oi_min = 1000
            
            ret, options = self.quote_ctx.get_option_chain(
                code=underlying,
                start=exp_date,
                end=exp_date,
                option_type=OptionType.PUT,
                data_filter=filter_short
            )
            
            if ret != RET_OK or options.empty:
                print(f"No suitable options for {exp_date}")
                time.sleep(3)
                continue
            
            # Find matching long puts (spread_width below each short put)
            for _, short_put in options.iterrows():
                short_strike = short_put['strike_price']
                long_strike = short_strike - spread_width
                
                # Find the long put
                long_put = options[options['strike_price'] == long_strike]
                
                if not long_put.empty:
                    long_put = long_put.iloc[0]
                    
                    # Calculate spread metrics
                    credit = short_put['bid'] - long_put['ask']  # Assuming bid/ask spread
                    max_risk = spread_width - credit
                    roi = (credit / max_risk) * 100 if max_risk > 0 else 0
                    
                    if roi >= 15:  # Minimum 15% ROI
                        spreads.append({
                            'underlying': underlying,
                            'expiration': exp_date,
                            'dte': self.calculate_dte(exp_date),
                            'short_put_strike': short_strike,
                            'short_put_code': short_put['code'],
                            'short_put_delta': short_put['delta'],
                            'long_put_strike': long_strike,
                            'long_put_code': long_put['code'],
                            'spread_width': spread_width,
                            'credit': round(credit, 2),
                            'max_risk': round(max_risk * 100, 2),  # In dollars
                            'roi': round(roi, 2),
                            'short_oi': short_put['open_interest'],
                            'short_volume': short_put['volume']
                        })
            
            time.sleep(3)  # Rate limit
        
        # Sort by ROI descending
        spreads.sort(key=lambda x: x['roi'], reverse=True)
        
        return spreads[:max_spreads]
    
    def display_spreads(self, spreads):
        """Display top spreads"""
        if not spreads:
            print("\nâŒ No spreads found matching criteria")
            return
        
        print(f"\n{'='*80}")
        print(f"TOP BULL PUT SPREADS")
        print(f"{'='*80}\n")
        
        for i, spread in enumerate(spreads, 1):
            print(f"SPREAD #{i}")
            print(f"  Underlying: {spread['underlying']}")
            print(f"  Expiration: {spread['expiration']} ({spread['dte']} DTE)")
            print(f"  Short PUT:  ${spread['short_put_strike']} (Î” {spread['short_put_delta']:.3f})")
            print(f"  Long PUT:   ${spread['long_put_strike']}")
            print(f"  Spread:     ${spread['spread_width']} wide")
            print(f"  Credit:     ${spread['credit']} (${spread['credit']*100} total)")
            print(f"  Max Risk:   ${spread['max_risk']}")
            print(f"  ROI:        {spread['roi']}%")
            print(f"  Liquidity:  OI {spread['short_oi']:,} | Vol {spread['short_volume']:,}")
            print(f"  Codes:      {spread['short_put_code']} / {spread['long_put_code']}")
            print()
    
    def close(self):
        self.quote_ctx.close()

# Run scanner
if __name__ == "__main__":
    scanner = SpreadScanner()
    
    print("ðŸ” Scanning SPY Bull Put Spreads...\n")
    spreads = scanner.scan_spreads(underlying='US.SPY', min_dte=30, max_dte=45)
    scanner.display_spreads(spreads)
    
    scanner.close()
```

### Example 2: Export Spreads to CSV

```python
import csv

def export_spreads_to_csv(spreads, filename='spreads_output.csv'):
    """Export spreads to CSV for easy review"""
    
    if not spreads:
        print("No spreads to export")
        return
    
    fieldnames = [
        'underlying', 'expiration', 'dte', 
        'short_put_strike', 'short_put_delta', 'short_put_code',
        'long_put_strike', 'long_put_code',
        'spread_width', 'credit', 'max_risk', 'roi',
        'short_oi', 'short_volume'
    ]
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(spreads)
    
    print(f"âœ… Exported {len(spreads)} spreads to {filename}")

# Usage
spreads = scanner.scan_spreads(underlying='US.SPY')
export_spreads_to_csv(spreads, 'spy_spreads_2025-01-07.csv')
```

---

## BEST PRACTICES

### 1. Connection Management

**âœ… DO:**
```python
# Create context once
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# Use for multiple operations
data1 = quote_ctx.get_market_snapshot(['US.SPY'])
data2 = quote_ctx.get_option_chain(...)
data3 = quote_ctx.get_history_kline(...)

# Close when done
quote_ctx.close()
```

**âŒ DON'T:**
```python
# Creating new context for each call (inefficient)
for ticker in tickers:
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    data = quote_ctx.get_market_snapshot([ticker])
    quote_ctx.close()
```

### 2. Rate Limiting

**âœ… DO:**
```python
import time

for exp_date in expirations:
    ret, data = quote_ctx.get_option_chain(...)
    time.sleep(3)  # 3 second buffer
```

**âŒ DON'T:**
```python
# Rapid-fire requests will get blocked
for exp_date in expirations:
    ret, data = quote_ctx.get_option_chain(...)
    # No delay - WILL FAIL
```

### 3. Error Handling

**âœ… DO:**
```python
ret, data = quote_ctx.get_option_chain(code='US.SPY', ...)

if ret == RET_OK:
    # Process data
    if not data.empty:
        print(data)
    else:
        print("No options found matching filters")
else:
    print(f"API Error: {data}")
```

**âŒ DON'T:**
```python
# Assuming success without checking
ret, data = quote_ctx.get_option_chain(...)
print(data['delta'])  # May crash if ret != RET_OK
```

### 4. Data Filtering

**âœ… DO: Filter at API Level**
```python
# Filter via OptionDataFilter (server-side)
filter1 = OptionDataFilter()
filter1.delta_min = -0.25
filter1.delta_max = -0.15
filter1.oi_min = 1000

ret, data = quote_ctx.get_option_chain(..., data_filter=filter1)
# Returns only matching options
```

**âŒ DON'T: Fetch everything then filter**
```python
# Fetches all options (slow, wastes quota)
ret, data = quote_ctx.get_option_chain(...)
filtered = data[(data['delta'] >= -0.25) & (data['delta'] <= -0.15)]
```

### 5. Subscription Management

**âœ… DO: Use Snapshots for One-Time Queries**
```python
# One-time price check - no subscription needed
ret, data = quote_ctx.get_market_snapshot(['US.SPY', 'US.QQQ'])
# Returns immediately, no quota used long-term
```

**âŒ DON'T: Subscribe for One-Time Queries**
```python
# Wastes subscription quota
quote_ctx.subscribe(['US.SPY'], [SubType.QUOTE])
ret, data = quote_ctx.get_stock_quote(['US.SPY'])
quote_ctx.unsubscribe(['US.SPY'], [SubType.QUOTE])
```

### 6. Code Structure for Scanner

```python
# Recommended project structure:

moomoo_etf_scanner/
â”œâ”€â”€ regime_detector.py      # Market regime classification
â”œâ”€â”€ spread_screener.py      # Options chain screening logic
â”œâ”€â”€ spread_calculator.py    # ROI, max risk calculations
â”œâ”€â”€ output_formatter.py     # CSV export, display formatting
â”œâ”€â”€ main.py                 # Orchestrates all modules
â”œâ”€â”€ config.py               # API settings, filter parameters
â””â”€â”€ utils.py                # Helper functions (DTE calc, etc.)
```

### 7. Regime Detection Pattern

```python
def get_market_regime():
    """
    Returns: 1 (aggressive), 2 (standard), 3 (defensive)
    """
    # Get SPY data
    spy_data = get_spy_price_and_indicators()
    
    # Get VIX
    vix_level = get_vix_level()
    
    # Classify
    if spy_above_vwap and vix < 18:
        return 1, {"max_spreads": 4, "delta_range": (0.15, 0.20), "spread_width": 10}
    elif vix > 25 or spy_below_vwap:
        return 3, {"max_spreads": 1, "delta_range": (0.15, 0.15), "spread_width": 15}
    else:
        return 2, {"max_spreads": 2, "delta_range": (0.20, 0.25), "spread_width": 15}
```

---

## QUICK REFERENCE - KEY FUNCTIONS

| Task | Function | Example |
|------|----------|---------|
| **Connect to API** | `OpenQuoteContext(host, port)` | `quote_ctx = OpenQuoteContext('127.0.0.1', 11111)` |
| **Get underlying price** | `get_market_snapshot(code_list)` | `quote_ctx.get_market_snapshot(['US.SPY'])` |
| **Get expiration dates** | `get_option_expiration_date(code)` | `quote_ctx.get_option_expiration_date('US.SPY')` |
| **Get options chain** | `get_option_chain(code, start, end, option_type, data_filter)` | See examples above |
| **Get historical data** | `get_history_kline(code, start, end, ktype)` | `quote_ctx.get_history_kline('US.SPY', ...)` |
| **Check subscription status** | `query_subscription()` | `quote_ctx.query_subscription()` |
| **Close connection** | `close()` | `quote_ctx.close()` |

---

## TROUBLESHOOTING CHECKLIST

**Before running your scanner:**

- [ ] OpenD is running and logged in
- [ ] OpenD shows "Connected" status
- [ ] US Securities authority = **LV1** (not "No Authority")
- [ ] US Options authority = **LV1** (or free if assets > $3k)
- [ ] `moomoo-api` package installed (`pip install moomoo-api`)
- [ ] Test connection script runs successfully
- [ ] Subscription quota available (check via `query_subscription()`)

**If errors occur:**

1. Check OpenD login status
2. Restart OpenD completely
3. Verify quote authority in OpenD interface
4. Check rate limits (add delays between calls)
5. Confirm expiration dates are valid (not expired)
6. Test with simple `get_market_snapshot()` first

---

## OFFICIAL RESOURCES

- **API Documentation:** https://openapi.moomoo.com/moomoo-api-doc/en/
- **Download OpenD:** https://www.moomoo.com/download/OpenAPI
- **Support:** MooMoo app â†’ Me â†’ Help & Support â†’ Live Chat
- **Community Forum:** https://www.moomoo.com/community

---

## PROJECT NEXT STEPS

**Phase 1: Build Scanner (Week 1-2)**
1. âœ… Install OpenD and Python API
2. âœ… Verify connection with test script
3. â¬œ Build `regime_detector.py` (SPY vs VWAP + VIX)
4. â¬œ Build `spread_screener.py` (options chain filtering)
5. â¬œ Build `spread_calculator.py` (credit, ROI, max risk)
6. â¬œ Build `main.py` (orchestrator)

**Phase 2: Testing (Week 3-4)**
1. â¬œ Run scanner daily for 2 weeks
2. â¬œ Validate spread opportunities manually
3. â¬œ Track scanner output vs actual fills
4. â¬œ Refine filters based on real data

**Phase 3: Production Use (Month 2+)**
1. â¬œ Integrate with trading journal
2. â¬œ Track actual P&L vs projected ROI
3. â¬œ Expand to QQQ, IWM, sector ETFs
4. â¬œ Optimize regime thresholds

---

**Document Version:** 1.0  
**Last Updated:** January 7, 2026  
**Created For:** Jeremy's ETF Bull Put Spreads Scanner Project  
**API Version:** MooMoo OpenAPI v9.6.5608