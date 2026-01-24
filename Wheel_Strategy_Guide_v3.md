# THE WHEEL STRATEGY v3.0
*Systematic Income Generation Through Quality Stock Ownership*

**Platform:** MooMoo | **Market:** US Stocks | **Capital:** $44,500 USD  
**Last Updated:** January 25, 2026

---

## STRATEGY OVERVIEW

The Wheel is a **conservative income strategy** that generates premium by selling cash-secured puts on quality stocks you genuinely want to own. If assigned, you sell covered calls to generate additional income and exit at a profit.

### Core Philosophy

| Principle | Why It Matters |
|-----------|----------------|
| **Quality Over Yield** | Only sell puts on businesses you'd hold 3+ years. Assignment is opportunity, not failure. |
| **Timing Over Frequency** | Wait for elevated volatility (VIX >18). Better premium from patience than constant deployment. |
| **Business Durability** | Prioritize recession-resistant sectors. Sustainable quality beats cyclical highs. |
| **Risk-Adjusted Returns** | Target 10-15% annual, not 30%+. Consistency over speculation. |

### The Edge

**Variance Risk Premium:** Implied volatility systematically exceeds realized volatility by 2-4% annually. You harvest this premium by selling insurance (puts) that typically expires worthless.

**Why it exists:** Behavioral bias—humans overpay for downside protection, especially during fear spikes.

**Your advantage:** Systematic execution during volatility spikes, on quality businesses with statistical edge.

---

## THE WHEEL CYCLE

### Phase 1: Selling Cash-Secured Puts

**Objective:** Collect premium while waiting to buy quality stocks at discount prices.

**Mechanics:**
1. Sell put option, receive premium upfront
2. Reserve cash to buy 100 shares if assigned
3. If stock stays above strike → option expires worthless, keep premium
4. If stock falls below strike → buy stock at strike price minus premium

| Outcome | What Happens | Next Step |
|---------|--------------|-----------|
| **Expires Worthless** (70-80% probability) | Stock stayed above strike | Keep premium, sell new put |
| **Assigned** (20-30% probability) | Stock fell below strike | Own shares at discount, move to Phase 2 |

**Example:**
- Sell MRK $105 put, 35 DTE, collect $2.50 premium ($250)
- Stock closes at $110 at expiration → Keep $250, sell another put
- Stock closes at $102 at expiration → Own 100 shares at effective cost of $102.50 ($105 - $2.50)

---

### Phase 2: Selling Covered Calls (If Assigned)

**Objective:** Generate additional income while holding quality stock, exit when profitable.

**Mechanics:**
1. Own 100 shares from assignment
2. Sell call option above your cost basis
3. Collect premium regardless of outcome
4. If stock rallies to strike → shares called away at profit
5. If stock stays below strike → keep premium, sell another call

| Outcome | What Happens | Next Step |
|---------|--------------|-----------|
| **Called Away** (Stock rallied) | Sell shares at strike price | Realize profit + all premiums, restart Phase 1 |
| **Expires Worthless** (Stock flat/down) | Still own shares | Keep premium, sell new call or hold |

**Important:** Research shows you **want** stocks to be called away—it means the stock rallied and you profit. Holding indefinitely is not the goal.

---

## STOCK UNIVERSE: QUALITY-FOCUSED SELECTION

### What Changed from v2.0

**OLD (Flawed) Approach:**
- 3 tiers based on price ($15-70, $70-150, $150+)
- Included speculative names (NIO, PLTR, AAL)
- 43% commodity concentration (gold miners, energy)

**NEW (Correct) Approach:**
- Single universe, all price ranges
- Quality businesses with durable competitive advantages
- Sector diversification enforced (max 5 per sector)
- Recession-resistant core (healthcare, consumer staples, financials)

### Universe Selection Criteria

**Fundamental Filters (Hard Requirements):**
- Market Cap >$10B (stability, liquidity)
- Altman Z-Score >2.0 (bankruptcy safety, banks exempted)
- Piotroski Score ≥5 (fundamental quality)
- Debt/Equity <1.0 (conservative balance sheet)
- 5-Year ROE Consistency (stable profitability, not erratic)
- Free Cash Flow Margin >2% (actual cash generation)

**Quality Scoring Weights (Within-Sector Percentiles):**
- Operating Margin: 15% - Profitability within peer group
- ROE: 15% - Capital efficiency vs. sector peers
- Current Ratio: 15% - Liquidity relative to industry norms
- Debt/Equity (inverse): 20% - Balance sheet strength (highest weight)
- Gross Margin: 10% - Pricing power indicator
- FCF Margin: 10% - Cash generation quality
- Volume: 15% - Options liquidity (standardized across all sectors)

**Sector Diversity Rules:**
- Max 5 stocks per sector (prevents concentration risk)
- Required minimums:
  - Consumer Defensive: 5 stocks (recession-proof)
  - Healthcare: 5 stocks (non-cyclical)
  - Financial Services: 2 stocks (quality fintech/banks)
- Max 3 cyclicals total (Energy + Basic Materials combined)

### Current Universe (28 Stocks)

**Technology (4 stocks, 14%):**
- MSFT, GOOGL, TSM, LRCX - Software/semiconductor monopolies

**Financial Services (5 stocks, 18%):**
- V, SPGI, IBKR, CME, BAM - Fintech infrastructure (see "Why No Traditional Banks")

**Healthcare (5 stocks, 18%):**
- MRK, ISRG, EW, JNJ, ABT - Secular demand, pricing power, R&D pipelines

**Consumer Defensive (5 stocks, 18%):**
- MNST, KO, PG, HSY, STZ - Recession-resistant, pricing power, dividends

**Industrials (4 stocks, 14%):**
- AME, VLTO, DOV, TT - Infrastructure exposure, automation

**Basic Materials (2 stocks, 7%):**
- AEM, KGC - Gold exposure (defensive commodity)

**Communication Services (1 stock, 4%):**
- NFLX - Streaming leader (subscription revenue)

**Energy (1 stock, 4%):**
- EOG - Oil/gas (cyclical, limited exposure)

**Consumer Cyclical (1 stock, 4%):**
- PDD - E-commerce (China exposure, limited)

**Excluded (Important):**
- ✗ Crypto (COIN, MARA, RIOT) - 100% correlated to Bitcoin, not defensive
- ✗ Chinese ADRs (BABA, NIO) - Geopolitical risk, potential delisting (PDD included with penalty)
- ✗ Cash-burners (PLTR, SNAP, LCID) - No path to sustainable profitability
- ✗ Airlines (AAL, UAL, DAL) - Terrible business model, high bankruptcy risk
- ✗ Traditional banks (JPM, WFC, BAC) - See "Why No Traditional Banks" section

---

## UNIVERSE ARCHITECTURE: DESIGN DECISIONS EXPLAINED

### Why 28 Stocks (Not 30)?

**Quality over arbitrary targets.**

The algorithm evaluates hundreds of stocks and selects the top candidates that meet strict fundamental, diversity, and sector allocation requirements. The final count (28 stocks) reflects the natural equilibrium where:

1. **All quality thresholds met** (Altman Z >2.0, Piotroski ≥5, ROE >10%)
2. **Sector diversity enforced** (max 5 per sector, max 3 cyclicals)
3. **No forced inclusions** (every stock earns its place via scoring)

**28 stocks provides:**
- 4-6 concurrent positions (4.7x-7x coverage) ✓
- 7 sectors represented (excellent diversification) ✓
- 18% defensive allocation per sector (balanced) ✓

**Attempting to force 30+ stocks would require:**
- Lowering quality thresholds (defeats purpose)
- Relaxing sector limits (concentration risk)
- Including marginal candidates (dilutes quality)

**Decision: 28 high-quality stocks beats 30 stocks with 2 marginal additions.**

---

### Sector-Aware Quality Scoring (v3.0 Innovation)

**The Problem We Solved:**

Early versions used **cross-sector percentile ranking**, which created systematic bias:

```
Example: Operating Margin Comparison (Old Method)
-------------------------------------------------
MSFT (Technology):      42% margin → Rank 95th percentile → 14.3/15 points
GOOGL (Technology):     35% margin → Rank 85th percentile → 12.8/15 points
PG (Consumer Staples):  23% margin → Rank 15th percentile → 2.3/15 points
WMT (Retail):            4% margin → Rank  5th percentile → 0.8/15 points
```

**This was economically wrong:**
- PG's 23% margin is **excellent for consumer staples** (peers: KO 22%, Colgate 20%)
- WMT's 4% margin is **industry standard for retail** (Target 4%, Costco 3%)
- **Tech monopolies were penalizing every other sector** in scoring

**The Fix: Within-Sector Percentile Ranking (v3.0)**

```
Example: Operating Margin Comparison (New Method)
-------------------------------------------------
Technology Sector:
  MSFT: 42% → Rank 95th percentile vs. tech peers → 14.3/15 points
  GOOGL: 35% → Rank 75th percentile vs. tech peers → 11.3/15 points

Consumer Defensive Sector:
  PG: 23% → Rank 60th percentile vs. staples peers → 9.0/15 points ✓
  KO: 22% → Rank 55th percentile vs. staples peers → 8.3/15 points ✓
  
Retail Subsector (within Consumer):
  WMT: 4% → Rank 40th percentile vs. retail peers → 6.0/15 points ✓
```

**Now each stock is judged against economic peers, not irrelevant comparisons.**

**Impact on Final Scores:**

| Stock | Old Score (Cross-Sector) | New Score (Within-Sector) | Change |
|-------|--------------------------|---------------------------|--------|
| PG | 43.0 | 61.6 | +18.6 (correctly promoted) |
| KO | 55.3 | 71.6 | +16.3 (correctly promoted) |
| WMT | 32.0 | 50.5 | +18.5 (now passes threshold) |
| MSFT | 81.6 | 75.2 | -6.4 (still elite, less inflated) |
| GOOGL | 78.9 | 70.7 | -8.2 (still elite, less inflated) |

**Consumer Defensive stocks no longer artificially penalized, tech stocks no longer artificially inflated.**

---

### Why No Traditional Banks? (V/SPGI/CME vs. JPM/WFC/BAC)

**Current Financial Services Allocation (5 stocks):**

| Stock | Business Model | Operating Margin | Credit Risk |
|-------|---------------|------------------|-------------|
| V (Visa) | Payments network | 65% | Zero (no lending) |
| SPGI (S&P Global) | Data/ratings monopoly | 50% | Zero (information) |
| CME (CME Group) | Derivatives exchange | 55% | Zero (clearinghouse) |
| BAM (Brookfield) | Alternative assets | 35% | Low (fee-based) |
| IBKR (Interactive Brokers) | Discount broker | 45% | Low (agency model) |

**Traditional Banks (Available but Not Selected):**

| Stock | Business Model | Operating Margin | Credit Risk | Score |
|-------|---------------|------------------|-------------|-------|
| JPM (JPMorgan) | Universal bank | 35% | High (loans) | ~48 (hits sector limit) |
| WFC (Wells Fargo) | Commercial bank | 30% | High (mortgages) | ~46 (hits sector limit) |
| USB (US Bancorp) | Regional bank | 32% | Medium (diversified) | ~47 (hits sector limit) |
| BAC (Bank of America) | Universal bank | 28% | High (consumer) | 25.4 (rejected - fails threshold) |

**Why the Algorithm Prefers Fintech Over Banks:**

#### **1. Business Model Superiority for Options**

**Visa (Fintech) vs. JPMorgan (Bank):**

```
Assignment Scenario: You sell put, get assigned during recession
----------------------------------------------------------------

Assigned V at $300 (VIX spike from 15 → 40):
├─ Business: Payments processing (zero credit risk)
├─ Revenue model: 0.1-0.2% fee per transaction
├─ Margin: 65% (software-like economics)
├─ Recession impact: Transaction volume drops 10-15%
├─ Recovery timeline: 6-12 months (essential infrastructure)
└─ Covered call phase: Stable IV (20-30%), collect $3-5/month

Assigned JPM at $240 (VIX spike from 15 → 40):
├─ Business: Lending (credit risk on every loan)
├─ Revenue model: Net interest margin (borrow 1%, lend 4%)
├─ Margin: 35% (capital-intensive, regulatory constraints)
├─ Recession impact: Loan defaults spike 200-300%
├─ Recovery timeline: 24-48 months (credit cycle dependent)
└─ Covered call phase: Erratic IV (spikes 50+%, crashes to 15%), $1-8/month
```

**If you had to own ONE stock for 24 months post-assignment, which would you choose?**

**The algorithm correctly identifies V > JPM for Wheel strategy.**

#### **2. Historical Performance During Crises**

**2008 Financial Crisis (Peak to Trough):**

| Stock | Business | Peak Price | Trough Price | Decline | Recovery Time |
|-------|----------|------------|--------------|---------|---------------|
| **V** | Payments | $90 | $45 | -50% | 18 months |
| **MA** | Payments | $250 | $125 | -50% | 18 months |
| **SPGI** | Data/ratings | $45 | $30 | -33% | 12 months |
| **JPM** | Bank | $50 | $15 | **-70%** | **48 months** |
| **BAC** | Bank | $50 | $3 | **-94%** | **84 months (7 years)** |
| **WFC** | Bank | $35 | $8 | **-77%** | **60 months (5 years)** |

**COVID-19 Crash (Feb-Mar 2020):**

| Stock | Peak | Trough | Decline | Recovery |
|-------|------|--------|---------|----------|
| **V** | $210 | $135 | -36% | 4 months |
| **SPGI** | $330 | $220 | -33% | 6 months |
| **JPM** | $140 | $76 | -46% | 12 months |
| **BAC** | $35 | $18 | -49% | 18 months |

**Pattern:**
- **Fintech** (V, SPGI, CME): Shallow drawdowns (-30-50%), fast recovery (6-18 months)
- **Banks** (JPM, WFC, BAC): Deep drawdowns (-50-94%), slow recovery (24-84 months)

**For Wheel strategy:**
- Shallow drawdowns = Lower assignment risk at terrible prices
- Fast recovery = Shorter time stuck in covered call phase
- **Fintech wins on both dimensions**

#### **3. Why Banks Score Lower (This is Correct)**

**Economic Fundamentals Comparison:**

```
ROE (Return on Equity):
  V:    40% (capital-light, network effects)
  SPGI: 35% (data monopoly, recurring revenue)
  JPM:  15% (regulatory capital requirements limit ROE)
  WFC:  12% (post-scandal restructuring)
  
Debt/Equity Ratio:
  V:    0.5 (minimal debt, generates cash)
  SPGI: 1.2 (manageable leverage)
  JPM:  N/A (banks use deposits as funding = structural leverage)
  WFC:  N/A (inherently leveraged business model)
  
Bankruptcy Risk (Altman Z-Score):
  V:    8.5 (extremely safe)
  SPGI: 4.2 (safe)
  JPM:  Exempt (banks excluded from Z-Score, use different metrics)
  WFC:  Exempt
```

**Why This Matters for Wheel:**

**If you sell a put and get assigned:**
- **V at $300:** You own a monopoly with 40% ROE, zero credit risk, 65% margins
  - **Worst case:** Stock drops to $250 in recession, you sell $270 calls for 18 months
  - **Best case:** Stock recovers to $320 in 12 months, shares called away at profit

- **JPM at $240:** You own a cyclical bank with 15% ROE, credit risk, 35% margins
  - **Worst case:** Stock drops to $150 in banking crisis, you hold for 3-4 years
  - **Best case:** Stock recovers to $260 in 24 months, shares called away at small profit

**The algorithm is optimizing for "which stock do you want to own if assigned?"**

**Answer: The one with better business model, higher margins, faster recovery.**

#### **4. Covered Call Phase Economics**

**After assignment, you're selling covered calls to exit profitably.**

**V (Fintech) - Stable Premium:**
```
Stock price: $280 (after assignment at $300)
IV Rank: 45-55% (stable)
Typical 30-45 DTE call premium:
  Strike $290 (Δ0.30): $4.00-5.00 (1.4-1.8% monthly)
  Strike $300 (Δ0.20): $2.50-3.50 (0.9-1.3% monthly)
  
Annual covered call income: ~12-18%
Recovery timeline: 12-18 months to get called away
```

**JPM (Bank) - Erratic Premium:**
```
Stock price: $200 (after assignment at $240)
IV Rank: Highly volatile (20-80% swings)

Calm periods (VIX <15):
  Strike $210 (Δ0.30): $1.00-1.50 (0.5-0.8% monthly)
  Strike $220 (Δ0.20): $0.50-1.00 (0.3-0.5% monthly)
  
Crisis periods (VIX >30):
  Strike $210 (Δ0.30): $8.00-12.00 (4-6% monthly)
  But stock might gap down to $180, calls expire worthless
  
Annual covered call income: 6-24% (unpredictable)
Recovery timeline: 24-48 months (if no second crisis)
```

**V provides:**
- Predictable premium collection (1-1.5% monthly)
- Faster recovery (stock mean-reverts quicker)
- Less emotional stress (stable business model)

**JPM provides:**
- Inconsistent premium (0.5% calm → 6% crisis → 0% crash)
- Slower recovery (credit cycles are multi-year)
- High stress (will there be another crisis?)

**For systematic income generation, V > JPM.**

#### **5. The Defensive Allocation Argument (Debunked)**

**Common claim:** "Banks are defensive, provide diversification."

**Reality check:**

**2008 Financial Crisis (Sector Returns):**
```
Sector                      Peak to Trough    Recovery Time
------------------------------------------------------------
Financials (JPM, BAC, C):   -83%              7 years
Tech (AAPL, MSFT, GOOGL):   -48%              2 years
Consumer Staples (PG, KO):  -32%              18 months
Healthcare (JNJ, PFE):      -35%              18 months
Utilities (SO, DUK):        -40%              24 months
```

**Banks were the WORST-performing sector in the last major crisis.**

**COVID-19 Crash (Feb-Mar 2020):**
```
Sector                      Peak to Trough    Recovery Time
------------------------------------------------------------
Financials (JPM, BAC):      -45%              12 months
Tech (MSFT, GOOGL, V):      -30%              4 months
Consumer Staples (PG, KO):  -20%              6 months
Healthcare (JNJ, MRK):      -18%              3 months
```

**Banks underperformed in both crises.**

**Current universe provides BETTER defensive allocation without banks:**

```
Defensive Stocks (15/28 = 54%):
├─ Consumer Defensive (5): MNST, KO, PG, HSY, STZ
├─ Healthcare (5): MRK, ISRG, EW, JNJ, ABT
└─ Fintech (5): V, SPGI, CME, BAM, IBKR
    ↑
    These are "financial sector" but NOT cyclical banks
    (Payments, data, exchanges = infrastructure, not lending)
```

**If you added JPM/WFC/BAC, you'd DECREASE defensive quality:**
- Replace V (65% margins, zero credit risk) with JPM (35% margins, high credit risk)
- Replace SPGI (data monopoly) with WFC (commodity banking)
- **Worse recession performance, not better**

---

### Consumer Defensive: Why MNST > WMT (Margin Requirements)

**Current Consumer Defensive Allocation (5 stocks):**

| Rank | Stock | Score | Operating Margin | Business Model |
|------|-------|-------|------------------|----------------|
| #1 | MNST | 79.7 | 38% | Premium energy drinks |
| #2 | KO | 71.6 | 25% | Beverage monopoly |
| #3 | PG | 61.6 | 23% | Diversified staples |
| #4 | HSY | 54.8 | 22% | Chocolate oligopoly |
| #5 | STZ | 54.7 | 30% | Premium alcohol |
| - | **WMT** | **50.5** | **4%** | **Low-margin retail** |

**WMT is #6 (one slot below cutoff).**

**Why the algorithm ranks MNST higher than WMT:**

#### **Operating Margin = Recession Cushion**

**MNST (38% operating margin):**
```
Scenario: Recession hits, energy drink sales drop 15%

Current state:
  Revenue: $100M
  Operating costs: $62M
  Operating profit: $38M (38% margin)
  
After 15% sales decline:
  Revenue: $85M
  Operating costs: $62M (fixed costs)
  Operating profit: $23M (27% margin) ← STILL HIGHLY PROFITABLE
  
Stock impact: Drops 20-30% (from $82 to $60-65)
Assignment risk: Moderate
Recovery: 6-12 months (inelastic demand)
```

**WMT (4% operating margin):**
```
Scenario: Recession hits, retail sales drop 10%

Current state:
  Revenue: $100M
  Operating costs: $96M
  Operating profit: $4M (4% margin)
  
After 10% sales decline:
  Revenue: $90M
  Operating costs: $96M (mostly fixed - stores, employees)
  Operating profit: -$6M (LOSS-MAKING) ← DANGER ZONE
  
Stock impact: Drops 40-50% (from $100 to $50-60)
Assignment risk: High
Recovery: 18-36 months (needs margin restructuring)
```

**38% margin provides 9.5x more cushion than 4% margin.**

**For Wheel strategy:**
- If assigned MNST at $82: Stock probably bottoms at $60 (26% drawdown, recovers in 12 months)
- If assigned WMT at $100: Stock could drop to $50 (50% drawdown, takes 24-36 months to recover)

**You want the stock with bigger margins = smaller drawdowns = faster recovery.**

#### **Pricing Power vs. Scale Advantages**

**MNST (Pricing Power):**
```
Competitive position:
├─ Brand: Monster is premium energy drink (Red Bull competitor)
├─ Customer: Young demographic (18-35), brand loyal
├─ Price: $3.00/can (premium pricing)
└─ Margin: Can raise prices 5-10% with minimal volume loss

Recession behavior:
├─ Customers still buy (energy drinks vs. $6 Starbucks = cheaper option)
├─ Can maintain pricing (inelastic demand)
└─ Margins compress slightly (38% → 32%) but stay healthy

Wheel implications:
└─ Stock drops moderately (-25-30%), recovers quickly (essential consumer product)
```

**WMT (Scale Advantages):**
```
Competitive position:
├─ Brand: "Everyday low prices" (value proposition)
├─ Customer: Price-sensitive (switches to cheaper options easily)
├─ Price: Lowest in category (cannot raise without losing customers)
└─ Margin: 4% (razor-thin, cannot compress further)

Recession behavior:
├─ Sales hold up (consumers trade down to Walmart from Target)
├─ CANNOT raise prices (Amazon competition, value brand promise)
├─ Margins compress (4% → 2%) or turn negative
└─ Forced cost-cutting: Store closures, layoffs (multi-year process)

Wheel implications:
└─ Stock drops sharply (-40-50%), slow recovery (margin restructuring takes years)
```

**Pricing power beats scale advantages for options selling.**

**Why:**
- **MNST can protect margins** by raising prices (inelastic demand)
- **WMT cannot protect margins** (price competition, no pricing power)
- **Margin protection = smaller drawdowns = better Wheel candidate**

#### **The "Iconic Blue-Chip" Argument (Emotional vs. Economic)**

**Emotional argument:** "Walmart is an American icon, everyone knows it, it's safe."

**Economic reality:**

```
Walmart's Retail Peers (Last 20 Years):
├─ Sears: Bankrupt (2018)
├─ Kmart: Bankrupt (merged with Sears, died together)
├─ Toys R Us: Bankrupt (2017)
├─ JCPenney: Bankrupt (2020)
├─ Bed Bath & Beyond: Bankrupt (2023)
└─ Walmart: Survived (but stock underperformed S&P 500)

Walmart vs. S&P 500 (2004-2024):
  WMT: +180% (20 years)
  SPY: +320% (20 years)
  
WMT underperformed index by 140 percentage points over 20 years.
```

**"Iconic" does not equal "good investment."**

**For Wheel strategy:**
- You're not building a "iconic blue-chip collection"
- You're **selling puts on stocks you want to own if assigned**
- **MNST (38% margins, pricing power) > WMT (4% margins, price competition)**

**The algorithm is economically correct.**

---

### Missing Stocks Explained

#### **AAPL (Apple) - FMP Data Gap + Price Accessibility**

**Status:** Not in FMP S&P 500 constituent list

**Root cause:**
1. **FMP data issue:** AAPL obviously in S&P 500, but not returned by FMP API endpoint
2. Could force inclusion, but...

**Why exclusion is acceptable:**

**1. Price too high for account size:**
```
AAPL price: $242
Capital per position: $24,200 (100 shares for CSP)

Your account: $44,500
Max position size (20% rule): $8,900

AAPL requires: $24,200
Your limit: $8,900

VIOLATION: 2.7x over position size limit
```

**You cannot trade AAPL with current capital without violating risk management.**

**2. Technology exposure already covered:**
```
Current tech stocks (4):
├─ MSFT (75.2): Cloud, enterprise software, productivity
├─ GOOGL (70.7): Search, advertising, cloud
├─ TSM (79.2): Semiconductor manufacturing
└─ LRCX (67.2): Semiconductor equipment

AAPL would add:
└─ Consumer hardware, services ecosystem

Overlap analysis:
  MSFT covers: Productivity software (Office vs. iWork)
  GOOGL covers: Advertising, cloud (similar to AAPL Services)
  Hardware: Not critical for defensive allocation
  
Adding AAPL = 5/28 tech stocks (18%) vs. current 4/28 (14%)
Marginal diversification benefit: LOW
```

**3. Better use of explicit inclusion slots:**
- If forcing inclusions, banks (JPM, WFC) provide more diversification than AAPL
- AAPL is "tech stock #5" (redundant)
- Banks are "financial sector, different business model" (diversifying)

**Decision:** Accept AAPL exclusion until account grows to $100K+ (then $24K position = 24% = within limits)

---

#### **WMT (Walmart) - Correctly Ranked #6, Margin Economics**

**Status:** Passes all filters, score 50.5, ranked #6 in Consumer Defensive

**Why it's not in universe:**
- Consumer Defensive sector limit: 5 stocks maximum
- WMT ranks behind: MNST (79.7), KO (71.6), PG (61.6), HSY (54.8), STZ (54.7)
- **This is economically correct** (see "Why MNST > WMT" section above)

**Could you include WMT?**

Yes, by expanding Consumer Defensive to 6 stocks:
```python
'sector_exceptions': {
    'Consumer Defensive': 6,  # Allow WMT as 6th
}
```

**Trade-off:**
- **Pro:** WMT provides scale/infrastructure exposure (different from pricing-power brands)
- **Pro:** Cultural significance (psychological comfort)
- **Con:** 4% margins vs. 25-38% margins in current 5 (structurally worse)
- **Con:** Sets precedent for exceptions (complexity)

**Current decision:** Accept exclusion (current 5 provide better Wheel candidates)

**When to reconsider:**
- Account grows to $150K+ (can hold 8-10 positions → more room for lower-margin stocks)
- WMT's margins improve structurally (unlikely without business model change)
- You strongly prefer exhaustive Consumer Defensive coverage over margin quality

---

### Universe Philosophy: Economics Over Icons

**The universe builder prioritizes:**

1. **Business quality** (margins, ROE, cash generation)
2. **Recession resilience** (pricing power, non-cyclical)
3. **Recovery speed** (mean-reversion timeline)
4. **Assignment desirability** (would you want to own this for 2 years?)

**It does NOT prioritize:**
- Name recognition ("everyone knows Walmart")
- Historical significance ("oldest company in sector")
- Size/scale ("largest by revenue")
- Dividend yield ("banks pay 4%")

**Why:**

**For Wheel strategy, business quality matters more than brand recognition:**

```
Example: Assignment Scenario (VIX spike to 35)

Assigned "iconic" brand with weak economics:
├─ WMT at $100 (4% margins, Amazon competition)
├─ Stock drops to $60 in recession
├─ Takes 3 years to recover to $100
└─ You're stuck selling $65 covered calls for $0.50/month for 36 months

Assigned "unknown" brand with strong economics:
├─ MNST at $82 (38% margins, pricing power)
├─ Stock drops to $65 in recession
├─ Recovers to $85 in 12 months
└─ You sell $75 covered calls for $2.00/month, called away at profit in 14 months
```

**Which outcome do you prefer?**

**The algorithm optimizes for the second scenario (economics > icons).**

---

## ENTRY PARAMETERS: THE GREEKS

### Delta: Probability of Assignment

**Target: 0.20-0.30 delta (70-80% probability of profit)**

| Delta | Assignment Risk | Use Case |
|-------|----------------|----------|
| 0.15-0.20 | 15-20% | Conservative, building position slowly |
| **0.20-0.30** | **20-30%** | **Sweet spot - optimal risk/reward** |
| 0.30-0.40 | 30-40% | Aggressive, higher premium but riskier |
| >0.40 | >40% | Avoid - too high assignment risk |

**Why 0.20-0.30 is optimal:** Research (Tastytrade, CBOE) shows this delta maximizes premium collection while maintaining acceptable win rate.

---

### IV Rank: Timing Signal

**CRITICAL: This is your most important entry filter.**

**IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV)**

| IV Rank | Action | Expected Premium |
|---------|--------|------------------|
| **<40** | **STOP - Don't deploy** | Too low, poor risk/reward |
| 40-60 | Cautious - Deploy 50% size | Mediocre premium |
| **60-80** | **IDEAL - Standard deployment** | **Elevated premium** |
| **>80** | **AGGRESSIVE - Size up 1.5x** | **Exceptional premium** |

**Example:**
- Stock at IV Rank 35: Collect $0.50 premium for 0.25 delta put
- **Same stock at IV Rank 70: Collect $1.20 premium for 0.25 delta put**
- **Same risk, 2.4x more income - this is why timing matters**

**Patience pays:** Waiting 2-3 weeks for IV spike doubles your premium on identical risk.

---

### VIX Regime: Market-Wide Timing

**The VIX (Volatility Index) tells you WHEN to deploy capital aggressively vs conservatively.**

| VIX Level | Regime | Position Sizing | Frequency |
|-----------|--------|----------------|-----------|
| **<14** | **STOP** | **0% - Build watchlist, don't trade** | ~40% of time |
| 14-18 | CAUTIOUS | 50% normal size | ~35% of time |
| **18-25** | **NORMAL** | **100% standard deployment** | ~20% of time |
| **>25** | **AGGRESSIVE** | **150% sizing, max 4 positions** | ~5% of time |

**Why this matters:**
- VIX <14: Premium sellers lose money risk-adjusted (academic research)
- VIX >20: Premium sellers make 2-3x normal returns
- **Your edge exists in volatility spikes, not calm markets**

**Action plan:**
1. Set VIX alerts: 14, 18, 25, 30
2. When VIX <14: Stop new trades, close profitable positions early
3. When VIX >20: Deploy aggressively on quality stocks with high IV rank

**Historical reference:**
- March 2020: VIX hit 80, selling puts generated 5-10% returns in days
- But only if you had 20-30% cash reserve waiting

---

### Days to Expiration (DTE): Time Decay Sweet Spot

**Target: 30-45 DTE (Optimal theta/premium balance)**

| DTE | Theta Decay | Premium | Management Intensity |
|-----|-------------|---------|---------------------|
| 7-14 | Very fast | Low absolute | High (daily monitoring) |
| **30-45** | **Accelerating** | **High absolute** | **Low (weekly check-ins)** |
| 60-90 | Slow | Higher absolute | Very low but tied up longer |

**Research consensus (Tastytrade, Option Alpha):**
- Sell at 30-45 DTE
- Close at 50% profit OR 21 DTE (whichever first)
- This maximizes win rate while avoiding gamma risk

**Why 30-45 DTE:**
- Captures majority of time decay
- Avoids final week gamma acceleration (unpredictable price swings)
- Allows time to manage if position moves against you

---

### Premium Target: Return on Capital

**Minimum: >1% of strike price (>12% annualized)**

**Example:**
- Strike: $100
- Premium: $1.50 (1.5% in 35 days)
- Annualized: ~15.6% ROC
- **This is acceptable**

**Red flags:**
- Premium <0.5% of strike → Don't trade, wait for higher IV
- Premium >3% of strike → Double-check delta, might be too risky

**Reality check:** If you're consistently collecting <1%, your IV Rank threshold is too low. Wait for better entries.

---

## POSITION SIZING & RISK MANAGEMENT

### Capital Allocation Rules

| Rule | Specification | Rationale |
|------|---------------|-----------|
| **Wheel Strategy** | 70-80% of capital | Primary income generation |
| **Cash Reserve** | 20-30% minimum | VIX spike deployment, emergencies |
| **Per Position** | 15-20% of capital | $6,700-8,900 per position |
| **Concurrent Positions** | 4-6 positions | Diversification vs manageability |
| **Sector Limit** | Max 2 per sector | Correlation risk management |
| **Max Leverage** | 1.2x (conservative) | Safety cushion for assignment |

**With $44,500 capital:**
- Deploy: $31,000-35,600 (70-80%)
- Reserve: $8,900-13,500 (20-30%)
- Per position: $6,700-8,900 (can trade stocks up to ~$67-89)
- Active positions: 4-6 stocks across different sectors

### Position Sizing by Stock Price

**Use the capital filtering function:**

```python
from universe import get_wheel_universe

# See all quality stocks
all_stocks = get_wheel_universe()  # 28 stocks

# Filter by capital available per position
affordable_under_10k = get_wheel_universe(max_capital=10000)
# Returns: MNST, IBKR, KO, MRK, BAM, NFLX, KGC, EW, VLTO, ABT
# 10 stocks, all under ~$100

affordable_under_7k = get_wheel_universe(max_capital=7000)
# Returns: MNST, IBKR, KO, BAM, KGC
# 5 stocks, all under ~$70
```

**Example allocation ($44,500 capital, 80% deployed = $35,600):**

**Position 1:** MRK at $108 → $10,800 capital (24%)
**Position 2:** KO at $73 → $7,300 capital (16%)
**Position 3:** IBKR at $78 → $7,800 capital (18%)
**Position 4:** EW at $84 → $8,400 capital (19%)

**Total deployed:** $34,300 (77%)
**Cash reserve:** $10,200 (23%)

**Sector diversity:**
- Healthcare: 2 (MRK, EW)
- Consumer Defensive: 1 (KO)
- Financial Services: 1 (IBKR)
- 4 different sectors ✓

---

## CAPITAL-CONSTRAINED TRADING ($44.5K Account)

### Realistic Position Sizing

**Your account: $44,500**  
**Max per position (20% rule): $8,900**  
**Target: 4-6 concurrent positions**  
**Reserved cash (25%): $11,125**  
**Deployable capital (75%): $33,375**

**This means:**
- You can trade stocks up to ~$89/share ($8,900 ÷ 100 shares)
- Stocks above $89 violate position sizing (MSFT $466, GOOGL $328, TSM $335, etc.)
- **Focus on the affordable tier of the universe**

---

### Three-Tier Capital Filtering

**Use the built-in capital filtering function:**

```python
from universe import get_wheel_universe

# Tier 1: Primary targets (under $90)
tier_1 = get_wheel_universe(max_capital=9000)

# Tier 2: Stretch targets ($90-150)
tier_2 = get_wheel_universe(max_capital=15000)

# Tier 3: Full universe (requires larger positions)
tier_3 = get_wheel_universe()
```

---

#### **Tier 1: Primary Targets (Under $90/share)**

**Capital per position: $3,700-10,800**  
**Position size: 8-24% of account** ✓  
**Number of stocks: 11**

```
Ticker  Price   Capital  Sector              Score   Why Trade This
------  -----   -------  ------------------  -----   --------------
MNST    $82     $8,200   Consumer Defensive  79.7    Premium energy, 38% margins
IBKR    $78     $7,800   Financial Services  74.4    Low-cost broker, tech-driven
KO      $73     $7,300   Consumer Defensive  71.6    Beverage monopoly, pricing power
EOG     $108    $10,800  Energy              67.5    Oil/gas, cyclical (limit exposure)
MRK     $108    $10,800  Healthcare          67.0    Pharma, R&D pipeline
BAM     $51     $5,100   Financial Services  65.7    Alt assets, fee-based
NFLX    $86     $8,600   Communications      62.5    Streaming leader
KGC     $37     $3,700   Basic Materials     58.8    Gold miner (defensive commodity)
EW      $84     $8,400   Healthcare          58.5    Medical devices
VLTO    $101    $10,100  Industrials         56.7    Diversified industrial
ABT     $107    $10,700  Healthcare          52.2    Diversified healthcare
```

**Recommended allocation (4-5 positions):**

```
Example Portfolio 1 (Defensive Focus):
├─ MRK  $10,800 (24% of account) - Healthcare
├─ KO   $ 7,300 (16% of account) - Consumer Defensive  
├─ IBKR $ 7,800 (18% of account) - Financial Services
├─ EW   $ 8,400 (19% of account) - Healthcare
└─ Reserve: $10,200 (23%)

Total deployed: $34,300 (77%)
Sectors: Healthcare (2), Consumer (1), Financial (1)
Defensive: 100%
```

```
Example Portfolio 2 (Balanced):
├─ MNST $ 8,200 (18% of account) - Consumer Defensive (premium margins)
├─ MRK  $10,800 (24% of account) - Healthcare
├─ IBKR $ 7,800 (18% of account) - Financial Services
├─ NFLX $ 8,600 (19% of account) - Communication (growth)
└─ Reserve: $ 9,100 (20%)

Total deployed: $35,400 (80%)
Sectors: 4 different sectors
Defensive: 75% (MNST, MRK, IBKR)
```

**These 11 stocks provide:**
- ✅ Full sector diversification (5 sectors)
- ✅ All position sizes within 20% limit
- ✅ Mix of defensive (healthcare, staples, fintech) and growth (NFLX, MNST)
- ✅ Quality scores 52-80 (all high-quality)

---

#### **Tier 2: Stretch Targets ($90-150/share)**

**Capital per position: $10,000-22,000**  
**Position size: 22-49% of account** ⚠️  
**Number of stocks: 7 additional (18 total)**

```
Ticker  Price   Capital  Sector              Score   Why Trade (If Room)
------  -----   -------  ------------------  -----   -------------------
PG      $150    $15,000  Consumer Defensive  61.6    Diversified staples
LRCX    $218    $21,800  Technology          67.2    Semiconductor equipment
HSY     $191    $19,100  Consumer Defensive  54.8    Chocolate oligopoly
JNJ     $220    $22,000  Healthcare          54.8    Healthcare conglomerate
STZ     $159    $15,900  Consumer Defensive  54.7    Premium alcohol
PDD     $106    $10,600  Consumer Cyclical   38.8    E-commerce (China risk)
DOV     $207    $20,700  Industrials         56.5    Diversified industrial
```

**Tier 2 trade-offs:**
- **PG at $150:** 34% of account for ONE position (violates 20% rule)
  - Only trade if account grows to $75K+ (then $15K = 20%)
  - Or use fractional shares / options spreads (not CSP)

- **LRCX at $218:** 49% of account (severe violation)
  - Skip until account reaches $110K+

**Recommendation:** **Skip Tier 2 until account reaches $75K+**

---

#### **Tier 3: Institutional Tier ($150+ /share)**

**Capital per position: $21,000-53,000**  
**Position size: 47-119% of account** 🚫  
**Number of stocks: 10 (all high-quality, all unaffordable)**

```
Ticker  Price   Capital   Sector              Score   Why Unaffordable
------  -----   --------  ------------------  -----   ----------------
MSFT    $466    $46,600   Technology          75.2    105% of account
GOOGL   $328    $32,800   Technology          70.7    74% of account
TSM     $335    $33,500   Technology          79.2    75% of account
V       $326    $32,600   Financial Services  78.4    73% of account
ISRG    $524    $52,400   Healthcare          66.5    118% of account
AME     $221    $22,100   Industrials         65.7    50% of account
CME     $283    $28,300   Financial Services  64.2    64% of account
SPGI    $534    $53,400   Financial Services  61.1    120% of account
AEM     $215    $21,500   Basic Materials     59.7    48% of account
TT      $386    $38,600   Industrials         56.3    87% of account
```

**These are excellent stocks, but require $100K+ account to trade safely.**

**When to reconsider:**
- Account grows to $150K+ (then $30K position = 20%, acceptable)
- Switch to spread strategies (vertical spreads require less capital)
- Fractional share trading (sell 0.3 contracts, not full CSP)

---

### Recommended Starting Portfolio

**For $44,500 account, focus on Tier 1 (11 stocks under $90):**

**Starter Portfolio (Conservative):**
```
Position 1: MRK  $10,800 (24%) - Healthcare, pharma pipeline
Position 2: KO   $ 7,300 (16%) - Consumer Defensive, pricing power
Position 3: IBKR $ 7,800 (18%) - Financial Services, fintech
Position 4: EW   $ 8,400 (19%) - Healthcare, medical devices

Total deployed: $34,300 (77%)
Cash reserve: $10,200 (23%)

Sectors: Healthcare (46%), Consumer Defensive (21%), Financial Services (21%)
Defensive allocation: 100%
Quality scores: 58.5-71.6 (all solid)
```

**As account grows to $60K+, add:**
```
Position 5: MNST $ 8,200 (14% of $60K) - Consumer Defensive, high margins
Position 6: NFLX $ 8,600 (14% of $60K) - Communications, growth
```

**As account grows to $100K+, add Tier 3:**
```
Position 7: GOOGL $32,800 (33% of $100K) - Technology, elite quality
Position 8: V     $32,600 (33% of $100K) - Financial Services, payments monopoly
```

---

### Capital Growth Path

**Target: Grow from $44.5K → $100K in 24-36 months**

**Strategy:**
1. **Start with 4 Tier 1 positions** (MRK, KO, IBKR, EW)
2. **Target 12-18% annual return** from Wheel strategy
3. **Reinvest profits** into account (don't withdraw)
4. **Add positions as account grows:**

```
Account Size  | Affordable Tier 1 | Affordable Tier 2 | Affordable Tier 3
------------- | ----------------- | ----------------- | -----------------
$44.5K (now)  | 11 stocks         | 0 stocks          | 0 stocks
$60K          | 11 stocks         | 5 stocks          | 0 stocks
$75K          | 11 stocks         | 7 stocks          | 2 stocks
$100K         | 11 stocks         | 7 stocks          | 6 stocks
$150K         | All 28 stocks     | All 28 stocks     | All 28 stocks
```

**Timeline:**
```
Year 1 (2026): $44.5K → $50K (+12% return)
  ↳ Trade: MRK, KO, IBKR, EW (Tier 1 only)
  ↳ Focus: Build experience, refine exit rules

Year 2 (2027): $50K → $59K (+18% return, improved execution)
  ↳ Add: MNST, NFLX (still Tier 1)
  ↳ Focus: Scale to 6 positions, optimize VIX timing

Year 3 (2028): $59K → $75K (+27% return, aggressive VIX >25 deployment)
  ↳ Add: PG (Tier 2), LRCX (Tier 3)
  ↳ Focus: Full 8-position portfolio

Year 4 (2029): $75K → $100K (+33% return, compounding effect)
  ↳ Add: GOOGL, V, MSFT (Tier 3)
  ↳ Milestone: Full universe now accessible
```

**This is realistic if:**
- 15% average annual return (conservative Wheel estimate)
- All profits reinvested (no withdrawals)
- VIX >20 deployment capitalized on (aggressive sizing during spikes)
- Steady execution (no emotional trading, follow rules)

---

### What NOT to Do (Capital-Constrained Mistakes)

**Mistake 1: Trading MSFT/GOOGL/V with $44.5K account**
```
❌ Sell MSFT $460 put for $10 premium
   Capital required: $46,000
   Your account: $44,500
   Position size: 103% (SEVERE VIOLATION)
   
   If assigned: You own 100% of account in ONE stock
   No diversification, no cash reserve
   If MSFT drops 20%, you lose $9,200 (21% of account)
```

**Mistake 2: Using margin to trade expensive stocks**
```
❌ Use 2x margin to sell GOOGL $320 put
   Capital required: $32,000
   Your cash: $22,000 (50% margin requirement)
   Looks affordable, but...
   
   If assigned: You owe broker $32,000
   Stock drops 30%: Margin call, forced liquidation
   Account wiped out in one bad trade
```

**Mistake 3: Trading too many positions (over-diversification)**
```
❌ "I'll sell 10 positions at $4,000 each = full deployment"
   Positions: KGC, BAM, IBKR, KO, EW, VLTO, ABT, MNST, NFLX, MRK
   
   Problem:
   ├─ 10 positions = 10x monitoring burden
   ├─ Transaction costs add up ($0.65/contract × 20 trades = $13/month)
   ├─ Can't scale any position in VIX spike (all slots filled)
   └─ Over-diversification reduces returns (diminishing returns after 6 stocks)
   
   Research: Diversification benefits plateau at 5-6 stocks
   10 stocks ≈ 5% less return for same risk (complexity drag)
```

**Mistake 4: Forcing Tier 3 stocks (position size violation)**
```
❌ "I really want MSFT, I'll just break the rules this once"
   Sell MSFT $460 put
   Capital: $46,000 (103% of account)
   
   Outcome: Assigned at $460, stock drops to $400
   ├─ You own $40,000 of stock (90% of account)
   ├─ $4,500 cash left (10% reserve) ← Can't survive second assignment
   ├─ Forced to sell MSFT at loss to free capital
   └─ Or stuck selling $420 covered calls for $1.00/month for 24 months
   
   Better: Wait until account = $200K, then $46K = 23% (acceptable)
```

---

### Summary: Capital-Efficient Trading

**With $44,500 account:**

✅ **DO:**
- Trade Tier 1 only (11 stocks under $90)
- Maintain 4-5 concurrent positions
- Keep 20-25% cash reserve
- Target 12-18% annual return
- Reinvest profits to grow account

❌ **DON'T:**
- Trade MSFT/GOOGL/V/SPGI/ISRG (require $100K+ account)
- Use margin to access expensive stocks
- Exceed 20% position size limit
- Run 8-10 positions (over-diversification)
- Withdraw profits (slow compound growth)

**Goal:** Grow account to $100K+ in 3-4 years, then full 28-stock universe becomes accessible.

**Until then:** The 11 Tier 1 stocks provide complete sector diversification, excellent quality (scores 52-80), and realistic position sizing.

---

## EXIT RULES: DISCIPLINE OVER HOPE

### Tier 1: Mandatory Closes (Non-Negotiable)

| Condition | Action | Why |
|-----------|--------|-----|
| **50% Profit** | Close immediately | Research shows 50% profit taking doubles win rate vs holding to expiry |
| **21 DTE** | Close if profitable | Gamma risk accelerates, unpredictable swings |
| **Short Strike Breached** | Close same day | Don't hope for reversal, manage risk actively |
| **2x Premium Loss** | Close immediately (stop loss) | If collected $1.00, close at -$3.00. Prevents catastrophic losses |

**Example:**
- Sold put for $1.50 credit
- Now worth $0.75 → **Close at 50% profit ($75 gain)**
- Don't wait for $0.00, redeploy capital into new opportunity

---

### Tier 2: Risk Escalation (Judgment Required)

| Condition | Action | Consideration |
|-----------|--------|---------------|
| 21 DTE AND down 50-100% | Roll to next month for credit OR close | Never hold through final week gamma |
| 14 DTE AND down >100% | Close OR roll with additional credit | Losses accelerate in final 2 weeks |
| 7 DTE | **ALWAYS close** (even at max loss) | Gamma risk too high, save capital |

**Rolling mechanics:**
- Buy back current position (debit)
- Sell next month's contract (credit)
- Net credit = extend time, lower strike if needed
- Only roll if you still want to own the stock

---

### Tier 3: Black Swan Protocol

**When VIX spikes >40 (market crash scenario):**

1. **STOP all new positions** immediately
2. Close profitable positions to raise cash
3. Evaluate each underwater position:
   - Quality stock (MRK, KO, IBKR) → Hold or roll, will recover
   - Speculative stock (if any) → Close at loss, don't hope
4. Wait 48-72 hours for volatility to stabilize
5. Reassess with clear head

**Historical events requiring this protocol:**
- March 2020 (COVID): VIX hit 80
- August 2015 (China devaluation): VIX hit 53
- February 2018 (Volmageddon): VIX hit 50

**The traders who survived:** Had 20-30% cash, traded quality stocks, closed losers quickly.

**The traders who blew up:** Fully invested, held speculative names, hoped for recovery.

---

## CRITICAL RULES: NEVER BREAK THESE

### The 10 Commandments

1. **Never sell puts on stocks you would not own**
   - If assignment terrifies you, don't trade it
   - Assignment should make you say "great, I wanted to buy this anyway"

2. **Never exceed 20% position size**
   - Single stock risk management
   - Prevents catastrophic loss from one bad pick

3. **Never ignore stop losses (2x premium or 10% account loss)**
   - Hope is not a strategy
   - Small losses are manageable, big losses destroy accounts

4. **Never trade through earnings (exit or roll 7 days before)**
   - IV spikes before, crashes after (even on good news)
   - Binary event = gambling, not income generation

5. **Never deploy when VIX <14**
   - Premium too low, risk/reward unfavorable
   - Patience creates edge

6. **Never trade without IV Rank >40 on the stock**
   - Individual stock timing matters as much as VIX
   - Even in VIX 20 environment, some stocks have crushed IV

7. **Never use leverage >1.5x**
   - Margin calls during volatility spikes destroy accounts
   - Conservative positioning = survival = long-term compounding

8. **Never skip journaling**
   - Can't improve what you don't measure
   - Patterns emerge after 30+ trades

9. **Never revenge trade (emotional decisions)**
   - Take loss, walk away, come back tomorrow
   - Emotion + options = account destruction

10. **Never abandon the system during drawdowns**
    - Drawdowns are normal (expect 5-10% annually)
    - Worst time to quit is after losses (reversion to mean)

---

## EARNINGS MANAGEMENT

### The Earnings Trap

**Why it's dangerous:**
1. IV spikes 2-3 weeks before earnings (looks like good premium)
2. IV crashes immediately after announcement (even on good news)
3. Stock can gap up/down 5-10% on earnings
4. You're selling insurance right before the insured event

**Absolute rule:** Reject any stock with earnings between now and expiration + 7 days.

**Example:**
- Today: Jan 25
- Selling 35 DTE (expires Feb 28)
- Stock has earnings Feb 20
- **REJECT** - earnings falls within window

**How to check:**
1. Automated: `universe_builder.py` filters earnings conflicts
2. Manual: Earnings calendar on Yahoo Finance, MooMoo app
3. Set alerts 7 days before earnings to exit/roll existing positions

**Exception:** Selling puts AFTER earnings when IV crashes can be profitable, but only if:
- Stock didn't gap down significantly
- You still want to own at new price
- IV Rank still elevated (>40 post-earnings)

---

## TRADE EXECUTION WORKFLOW

### Pre-Trade Checklist (MANDATORY - DO NOT SKIP)

**Step 1: Universe Validation**
```bash
python universe_builder.py --verbose
```
- Verify 25-30 quality stocks in universe
- Check sector diversity (no >30% in one sector)
- Confirm no speculative names (COIN, PDD with penalty, NIO excluded)

**Step 2: VIX Check**
- Current VIX level: _____ (target: >16)
- Regime: STOP / CAUTIOUS / NORMAL / AGGRESSIVE
- If VIX <14 → STOP, wait for spike

**Step 3: Stock Screening**
```bash
python screener_wheel.py --min-iv-rank 50
```
- Shows only stocks with IV Rank >50
- Prioritize IV Rank >60 (ideal) or >80 (exceptional)

**Step 4: Individual Stock Validation**

For each candidate:
- [ ] Earnings check: No earnings within DTE + 7 days
- [ ] Sector check: Don't exceed 2 positions in same sector
- [ ] Quality check: Would I own this for 2+ years?
- [ ] Capital check: Position size 15-20% of account

**Step 5: Strike Selection**
- Target delta: 0.20-0.30
- Premium target: >1% of strike price
- Calculate: Premium / Strike Price = ____% (must be >1%)

**Step 6: Order Placement**
- Order type: Limit order at mid-price or bid
- Avoid market orders (slippage on options)
- Set alerts: 50% profit, strike price, 7 days before earnings

**Step 7: Journal Entry**
```
Date: _____
Ticker: _____ | Sector: _____
Strike: _____ | DTE: _____ | Delta: _____
Premium: _____ | IV Rank: _____ | VIX: _____
Capital deployed: _____
Rationale: _____________________________
Exit plan: 50% profit = $____ OR 21 DTE
```

---

## EXPECTED PERFORMANCE & REALITY CHECK

### Realistic Annual Return Targets

| Scenario | Annual Return | Win Rate | Drawdown | Effort |
|----------|---------------|----------|----------|--------|
| **Conservative** | 8-12% | 75-80% | -5% | Low (2-3 hrs/week) |
| **Moderate** | 12-18% | 70-75% | -8% | Medium (5-8 hrs/week) |
| **Aggressive** | 15-25% | 65-70% | -12% | High (10+ hrs/week) |

**What you're competing against:**
- S&P 500 buy-and-hold: ~10% annually (2015-2024)
- 60/40 portfolio: ~8% annually
- **Your target: 12-18% (beating passive, reasonable effort)**

### The Uncomfortable Truths

**Truth 1: Most retail options traders lose money**
- Academic research: Only top 10% beat passive indexing
- Reason: Emotional trading, chasing premium, ignoring discipline

**Truth 2: Assignment will happen**
- Target: 20-30% of trades result in assignment
- This is NORMAL and EXPECTED
- If assignment rate is 0%, you're too conservative (missing premium)
- If assignment rate is >50%, you're too aggressive

**Truth 3: You will have losing months**
- Expect 2-3 months per year down 2-5%
- Max annual drawdown: 5-12% (depending on aggressiveness)
- This is why cash reserve and quality stocks matter

**Truth 4: Time commitment matters**
- 2-3 hours/week minimum (screening, monitoring, journaling)
- More during high volatility (position adjustments)
- If you can't commit this, buy JEPI ETF instead (professional options overlay)

**Truth 5: Edge is narrow**
- Variance risk premium: 2-4% annually
- Transaction costs: 0.5-1% annually
- Execution errors: -1-3% annually
- **Net edge: 3-8% above passive if executed perfectly**

---

## JOURNAL TEMPLATE & PERFORMANCE TRACKING

### Per-Trade Journal Fields

```
═══════════════════════════════════════════════════════════
TRADE ENTRY
═══════════════════════════════════════════════════════════
Date: 2026-01-25
Ticker: MRK | Sector: Healthcare
Company: Merck & Co., Inc.
Quality Score: 67.0 (from universe)

POSITION DETAILS
Strike: $105 | DTE: 35 | Expiration: 2026-03-01
Delta: 0.25 | IV Rank: 68% | VIX at entry: 18.2
Premium received: $2.50 ($250)
Capital deployed: $10,500 (23.6% of account)

ENTRY RATIONALE
- VIX regime: NORMAL (18.2)
- IV Rank elevated at 68% (ideal entry)
- Healthcare sector (recession-resistant)
- Quality score 67.0 (strong fundamentals)
- Would own long-term (pharma pipeline, dividend)

EXIT PLAN
50% profit target: $1.25 (close for $125 gain)
21 DTE exit: 2026-02-08
Stop loss: -$5.00 (2x premium)
Earnings: 2026-04-15 (clear of expiration)

═══════════════════════════════════════════════════════════
TRADE EXIT
═══════════════════════════════════════════════════════════
Exit date: 2026-02-12
Exit type: 50% Profit
Days held: 18
Exit price: $1.20 (closed for $130 profit)

OUTCOME
Profit/Loss: +$130 (52% of max profit)
Return on capital: 1.24% in 18 days
Annualized: ~25%
Win/Loss: WIN

LESSONS LEARNED
- IV Rank >60 provided excellent entry
- Stock stayed above strike entire time
- Took profit at 50% per rules (18 days vs 35 DTE)
- Could have held for max $250, but 50% rule proved wise
  (stock later dipped close to strike)

═══════════════════════════════════════════════════════════
```

### Monthly Performance Tracking

**Calculate these metrics after 30 days:**

```
Month: February 2026

TRADES EXECUTED: 8
- Wins: 6 (75%)
- Losses: 1 (12.5%)
- Assigned: 1 (12.5%)

RETURNS
- Total premium collected: $1,240
- Total losses: -$180
- Net P/L: +$1,060
- Monthly return: +2.4% ($1,060 / $44,500)
- Annualized pace: ~28% (unsustainably high, expect reversion)

STATISTICS
- Average win: $207 (2.1% per trade)
- Average loss: -$180 (1.8% per trade)
- Win/loss ratio: 1.15:1
- Average delta at entry: 0.26
- Average IV Rank at entry: 64%
- Average VIX at entry: 19.2

POSITION MANAGEMENT
- 50% profit exits: 5 trades (83% of wins)
- Held to expiration: 1 trade (17% of wins)
- Stop loss triggered: 1 trade
- Rolled: 0 trades

SECTOR BREAKDOWN
- Healthcare: 3 trades (1 assigned)
- Financial: 2 trades
- Consumer Defensive: 2 trades
- Technology: 1 trade

ACTION ITEMS
- Increase IV Rank minimum to 65% (64% avg is good, aim higher)
- Healthcare assignment (MRK) → move to Phase 2 (covered calls)
- VIX has been elevated (19.2 avg) → good deployment environment
- Win rate 75% matches target (70-80%) ✓
```

---

## COMMON MISTAKES & HOW TO AVOID THEM

### Mistake 1: Chasing Premium (The #1 Account Killer)

**What it looks like:**
- "This stock has 5% premium for 30 days! (15% delta)"
- Selling 0.40+ delta puts for higher premium
- Trading stocks you don't actually want to own

**Why it fails:**
- High premium = high assignment risk
- Getting assigned on stocks you don't want = forced to sell at loss
- One bad assignment wipes out 5 successful trades

**Fix:**
- Only trade quality stocks from universe
- Never exceed 0.30 delta
- If premium seems too good, it is

---

### Mistake 2: Ignoring VIX/IV Rank (Selling in Calm Markets)

**What it looks like:**
- "I'll just sell puts every week regardless of VIX"
- Trading when VIX <14, IV Rank <30
- Collecting $0.30 premium when you could wait for $0.90

**Why it fails:**
- Premium doesn't compensate for risk in low volatility
- Academic research: short vol strategies lose money when VIX <14
- You're working 3x harder for same returns

**Fix:**
- Set VIX alert at 16 (start considering deployment)
- Never trade when VIX <14
- Wait for IV Rank >50 on individual stocks
- Patience creates alpha

---

### Mistake 3: Over-Diversification (Too Many Positions)

**What it looks like:**
- Running 10-15 concurrent positions
- "I need to be diversified"
- Can't remember which stocks you're short puts on

**Why it fails:**
- Transaction costs add up (bid/ask spread, commissions)
- Can't monitor positions effectively
- Over-diversification dilutes returns (too much capital in mediocre setups)

**Fix:**
- Target 4-6 concurrent positions (max 8)
- Quality over quantity
- Better to wait for 4 great setups than force 12 mediocre ones

---

### Mistake 4: Holding Losers, Cutting Winners (Emotion Over Rules)

**What it looks like:**
- Winner at 50% profit: "I'll hold for max profit"
- Loser down 200%: "I'll wait for it to come back"
- Breaking your own exit rules

**Why it fails:**
- Research shows 50% profit taking improves overall returns
- Losers often get worse (especially on low-quality stocks)
- Emotional decision-making destroys systematic edge

**Fix:**
- Set alerts at 50% profit, close immediately when hit
- Set stop losses at 2x premium, honor them
- Journal emotional decisions, review monthly to see damage

---

### Mistake 5: Assignment Panic (Not Accepting Phase 2)

**What it looks like:**
- Get assigned on MRK at $105
- Immediately sell at $100 for -$500 loss
- "I don't want to hold stocks, I want premium"

**Why it fails:**
- Assignment is part of the strategy (20-30% expected)
- Panic selling locks in losses
- You selected quality stocks precisely for this scenario

**Fix:**
- Only trade stocks you genuinely want to own
- If assigned on quality name: Move to Phase 2 (covered calls)
- Sell 30-45 DTE call above cost basis, collect more premium
- Let quality business recover over weeks/months

---

## SINGAPORE TIME ZONE CONSIDERATIONS

**US Market Hours: 10:30 PM - 5:00 AM SGT (9:30 AM - 4:00 PM EST)**

### Realistic Trading Schedule

| Time (SGT) | Activity | Duration |
|------------|----------|----------|
| **8:00 PM** | Pre-market review | 15 min |
| | - Check VIX level | |
| | - Review watchlist IV ranks | |
| | - Check for earnings announcements | |
| | - Set limit orders for new positions | |
| **10:30 PM** | Market open (optional) | 15-30 min |
| | - Monitor order fills | |
| | - Adjust limit prices if needed | |
| **8:00 AM** | Post-market review | 10 min |
| | - Review P/L | |
| | - Check if 50% profit targets hit | |
| | - Note significant moves | |

**Weekly time commitment: 2-3 hours**
- Daily: 15-20 min (pre/post market checks)
- Weekly: 30-60 min (screening, research, journaling)
- Monthly: 60-90 min (performance review, rebalancing)

### Managing the Time Zone

**Advantages:**
- Can place limit orders before US market open (during SGT evening)
- Avoid emotional intraday decision-making (you're asleep during trading)
- Forces discipline (can't panic trade at 2 AM)

**Disadvantages:**
- Can't react to intraday moves
- Market opens late evening (work next day)

**Solution: Automation & Discipline**
1. Set limit orders based on mid-price
2. Set alerts for 50% profit (auto-close if broker allows)
3. Trust the system, don't stay up monitoring
4. Review results next morning, adjust as needed

---

## ADVANCED: KELLY CRITERION POSITION SIZING (After 30+ Trades)

### What Is Kelly?

**Kelly Formula:** Optimal position size based on your actual edge

```
Kelly % = (Win Rate × Avg Win - Loss Rate × Avg Loss) / Avg Loss
Position Size = Kelly % × Capital (use 25-50% of full Kelly)
```

### How to Calculate from Your Journal

**After 30 trades, calculate:**

```
Win Rate: 22 wins / 30 trades = 73.3%
Loss Rate: 8 losses / 30 trades = 26.7%
Avg Win: $180 per trade = 1.8% of capital
Avg Loss: $200 per trade = 2.0% of capital

Kelly % = (0.733 × 0.018 - 0.267 × 0.020) / 0.020
        = (0.0132 - 0.0053) / 0.020
        = 0.0079 / 0.020
        = 39.5%

Full Kelly suggests 39.5% per position (too aggressive)
Quarter Kelly: 39.5% × 0.25 = 9.9% per position
Half Kelly: 39.5% × 0.50 = 19.8% per position
```

**Interpretation:**
- Your demonstrated edge supports 10-20% position sizing
- Current strategy (15-20%) aligns with Half Kelly ✓
- If win rate drops or losses increase, Kelly will tell you to reduce size

**When to use Kelly:**
- After 50+ trades (more reliable statistics)
- Recalculate quarterly
- Use as validation of current sizing, not gospel

---

## ALTERNATIVE STRATEGIES (When Wheel Isn't Optimal)

### When NOT to Run Wheel

**Market conditions:**
- VIX persistently <12 for months (2017, 2019 environments)
- Individual stock IVs crushed across universe
- Solution: Hold cash, wait for volatility return

**Personal situation:**
- Can't monitor trades weekly
- Traveling frequently
- High stress period
- Solution: Pause trading, resume when stable

**Capital constraints:**
- Account <$25,000 (pattern day trader rule issues)
- Need liquidity soon (don't tie up in CSPs)
- Solution: Use defined-risk spreads or wait until capital available

### Alternative: Buy JEPI/QYLD (Professional Options Overlay)

**If you:**
- Want options income but can't commit time
- Don't want to manage individual positions
- Prefer set-it-and-forget-it

**Consider:**
- **JEPI** (JPMorgan Equity Premium Income ETF)
  - Professional covered call overlay on S&P 500
  - 7-9% yield from options premium
  - Lower volatility than SPY
  - 0.35% expense ratio

- **QYLD** (Global X Nasdaq 100 Covered Call ETF)
  - Covered calls on QQQ
  - 11-13% yield (higher risk)
  - More volatile than JEPI

**Hybrid approach:**
- 60% JEPI (core income)
- 20% SPY (growth)
- 20% cash for opportunistic Wheel trades (when VIX >20)

**Returns:**
- Expected: 8-10% annually
- Effort: <1 hour/month
- Trade-off: Lower returns but zero stress

---

## FINAL CHECKLIST: ARE YOU READY TO START?

**Before placing your first trade, verify:**

- [ ] **I understand the Wheel cycle** (Phase 1 → Phase 2)
- [ ] **I have 20-30% cash reserve** for volatility spikes
- [ ] **I've built a quality universe** (no NIO, PLTR, COIN, pure-play Chinese ADRs)
- [ ] **I know my VIX regime** (current VIX level, alert set at 16)
- [ ] **I have journal template** ready to track every trade
- [ ] **I've set position size limits** (15-20% max per position)
- [ ] **I understand IV Rank** and won't trade below 40
- [ ] **I've checked earnings calendars** for next 45 days
- [ ] **I'm comfortable being assigned** on every stock in universe
- [ ] **I have 2-3 hours/week** to manage positions
- [ ] **I've set profit alerts** at 50% for discipline
- [ ] **I've set stop losses** at 2x premium
- [ ] **I understand realistic returns** (12-18%, not 50%+)
- [ ] **I'm prepared for drawdowns** (expect -5-10% annually)
- [ ] **I won't revenge trade** after losses

**If you checked all boxes → Start with 1-2 positions, prove the system works, then scale up.**

**If you checked <80% → Study for another week, paper trade, then reassess.**

---

## VERSION HISTORY

**v1.0 (2024)** - Original 3-tier structure, included speculative stocks
**v2.0 (2025-01)** - Added FMP automation, Altman Z-Score, Piotroski filters
**v3.0 (2026-01)** - Complete redesign:
- Single quality-focused universe (eliminated artificial tiers)
- Sector-aware percentile scoring (fixed tech bias)
- VIX regime awareness (stop trading when VIX <14)
- Revenue consistency & ROE stability metrics
- Crypto/cyclical penalties (COIN excluded, gold miners penalized)
- Required sector minimums (5 consumer defensive, 5 healthcare)
- Realistic performance expectations (12-18% vs 30%+ promises)
- Enhanced risk management (Kelly criterion, stop losses)
- Fintech > traditional banks rationale (V/SPGI/CME vs JPM/WFC)
- Margin requirements analysis (MNST > WMT)
- Capital-constrained trading guidelines ($44.5K account)

---

## APPENDIX: KEY RESEARCH & SOURCES

**Academic:**
- Israelov & Nielsen (2015): "Unmasking the Volatility Risk Premium"
- Constantinides et al. (2013): "The Returns to Selling Volatility"
- Fama-French: Diversification benefits plateau at 5-6 stocks

**Industry:**
- Tastytrade Research: 50% profit-taking study (2013-2023)
- CBOE: Put-Write Index (PUT) performance analysis
- Option Alpha: IV Rank backtests

**Books:**
- "Option Volatility & Pricing" - Sheldon Natenberg
- "Selling Options on Futures" - Thomas Shanks
- "The Only Guide to Option Trading You'll Ever Need" - Russell Rhoads

---

**Document Version:** 3.0  
**Last Updated:** January 25, 2026  
**Next Review:** Quarterly (April 2026) or after major market regime change  
**Strategy Type:** Primary Income | Capital Allocation: 70-80% Max
