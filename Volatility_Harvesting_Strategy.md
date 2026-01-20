**VOLATILITY HARVESTING STRATEGY**

*Exploiting Overpriced Implied Volatility on High-IV Names*

STRATEGY OVERVIEW

This strategy is separate from your Wheel Strategy. The Wheel targets
quality stocks you want to own; this strategy targets premium harvesting
on volatile names you never want to own. Assignment is failure here, not
opportunity.

  ------------------ ----------------------------------------------------
  **Core Thesis**    Implied volatility consistently overstates realized
                     volatility. On high-IV squeeze candidates, this
                     premium is extreme. Sell overpriced options, profit
                     when IV crushes.

  **Edge Source**    Retail traders overpay for lottery tickets. Market
                     makers price in worst-case scenarios. You collect
                     the fear premium.

  **Key Difference** Wheel = directional income on quality stocks. Vol
                     Harvest = non-directional income on garbage stocks.
                     Never mix them.
  ------------------ ----------------------------------------------------

  -----------------------------------------------------------------------
  **RISK WARNING:** Short volatility strategies have negative skewness,
  high kurtosis, and large drawdowns. One fund lost 89% in two days (Feb
  2018). This strategy uses DEFINED RISK (iron condors) to cap losses,
  but respect the tail risk.

  -----------------------------------------------------------------------

PRIMARY STRATEGY: IRON CONDORS

Iron condors sell both a put spread and call spread around the current
price. You profit if the stock stays within a wide range. Defined risk
means your maximum loss is capped at entry.

Structure

  ----------------- ----------------- ----------------- -----------------
  **Leg**           **Action**        **Delta**         **Purpose**

  Long Put          Buy               0.05-0.10         Caps downside
                                                        loss

  **Short Put**     **Sell**          **0.15-0.20**     **Collects
                                                        premium**

  **Short Call**    **Sell**          **0.15-0.20**     **Collects
                                                        premium**

  Long Call         Buy               0.05-0.10         Caps upside loss
  ----------------- ----------------- ----------------- -----------------

Entry Parameters

  ----------------------- ----------------------- -----------------------
  **Parameter**           **Target**              **Rationale**

  IV Rank                 **\>80 (ideally         Extreme IV = extreme
                          \>100)**                premium

  Short Strike Delta      **0.15-0.20**           15-25 delta has highest
                                                  excess \$ premium
                                                  (OTS4)

  Wing Width              **\$2.50-\$5.00**       Caps max loss; wider =
                                                  less risk

  DTE                     **21-35 days**          Shorter than Wheel
                                                  (faster theta decay)

  Premium Target          **\>33% of width**      \$5 width, collect
                                                  \>\$1.65 (2:1
                                                  risk/reward)

  Options Volume          **\>500/day**           Liquidity for clean
                                                  fills
  ----------------------- ----------------------- -----------------------

POSITION SIZING & RISK MANAGEMENT

This strategy uses remaining capital after Wheel positions. Conservative
sizing is critical because even defined-risk trades can cluster losses.

  ----------------------------------- -----------------------------------
  **Rule**                            **Specification**

  Capital Allocation                  Max 20% of total capital for Vol
                                      Harvest strategy

  Max Per Position                    Max loss per IC = 5% of Vol Harvest
                                      capital (\$445 max loss)

  Concurrent Positions                Maximum 4 iron condors open at once

  Correlation Limit                   No more than 2 positions in same
                                      sector/theme

  Monthly Loss Limit                  Stop trading if down 10% of Vol
                                      Harvest capital in a month
  ----------------------------------- -----------------------------------

Example Position Sizing

Total Capital: \$44,500 USD

Vol Harvest Allocation: 20% = \$8,900

Max Loss Per Position: 5% of \$8,900 = \$445

*With \$5 wide wings, max loss = \$500 - premium. So collect at least
\$55 premium per condor to stay within limits, or use \$2.50 wings.*

Exit Rules

  ----------------------- -----------------------------------------------
  **Condition**           **Action**

  **50% Profit**          Close entire position. Don\'t wait for
                          expiration.

  7 DTE                   Close regardless of P/L. Gamma risk too high.

  **Short strike          Close immediately. Don\'t hope for reversal.
  touched**               

  **200% of premium       Close. If collected \$1.50, close at \$4.50
  loss**                  debit max.

  Trading halt            Close at first opportunity when trading
                          resumes.
  ----------------------- -----------------------------------------------

TARGET UNIVERSE

These are NOT quality stocks. They are volatility vehicles. You don\'t
care about fundamentals; you care about overpriced options.

Screening Criteria

  ----------------------- ----------------------- -----------------------
  **Filter**              **Requirement**         **Why**

  Stock Price             \$5-\$50                Affordable wings, still
                                                  liquid

  IV Rank                 **\>80%**               Must be elevated to
                                                  harvest

  Options Volume          \>500/day               Liquidity for exits

  Bid-Ask Spread          \<15% of mid            Wider spreads
                                                  acceptable here

  Recent Catalyst         Squeeze/news in past 5  IV elevated post-event
                          days                    
  ----------------------- ----------------------- -----------------------

Typical Target Characteristics

Meme stocks post-squeeze (GME, AMC when IV spikes)

Heavily shorted names after failed squeeze (like the SXTC example)

Biotech after binary event (FDA decision passed)

SPAC/de-SPAC names with elevated IV

EV/speculative tech with high short interest

Avoid

+-----------------------------------------------------------------------+
| Stocks with earnings within DTE (IV will spike more, not crush)       |
|                                                                       |
| Stocks in active squeeze (wait for exhaustion)                        |
|                                                                       |
| Sub-\$5 stocks (illiquid options, wide spreads)                       |
|                                                                       |
| Pending M&A or buyout (binary outcome)                                |
+-----------------------------------------------------------------------+

EXECUTION WORKFLOW

Pre-Trade Checklist

  ------- -----------------------------------------------------------------
  **1**   Identify high-IV candidate from screener or news (IV Rank \>80%)

  **2**   Check earnings calendar - reject if earnings within DTE

  **3**   Verify squeeze/spike has exhausted (not entering during the move)

  **4**   Check options volume \>500/day at target strikes

  **5**   Calculate max loss vs position size limit (must be \<5% of Vol
          Harvest capital)

  **6**   Verify premium collected \>33% of wing width

  **7**   Execute as single order (4-leg iron condor) at mid price

  **8**   Set alerts: 50% profit, short strike price, 7 DTE
  ------- -----------------------------------------------------------------

Example Trade: Post-Squeeze Play

*Scenario: SXTC squeezed from \$1 to \$5, now trading at \$2.50. IV Rank
150%+. Squeeze exhausted.*

  ----------------------------------- -----------------------------------
  Buy \$1 Put                         Pay \$0.10

  **Sell \$1.50 Put**                 **Collect \$0.35**

  **Sell \$3.50 Call**                **Collect \$0.40**

  Buy \$4 Call                        Pay \$0.15

  **Net Credit**                      **\$0.50 (\$50 per contract)**

  Max Loss                            \$0.50 width - \$0.50 credit = \$0
                                      (breakeven worst case)

  Profit Zone                         Stock between \$1.50 and \$3.50 at
                                      expiration
  ----------------------------------- -----------------------------------

KEY DIFFERENCES FROM WHEEL STRATEGY

  ----------------------- ----------------------- -----------------------
  **Aspect**              **Wheel Strategy**      **Vol Harvest**

  Underlying Quality      Quality stocks you\'d   Garbage you never want
                          own                     

  Assignment              Opportunity (own at     Failure (never want
                          discount)               shares)

  Risk Type               Undefined (CSP)         Defined (IC wings)

  IV Target               \>30 IV Rank            \>80 IV Rank

  DTE                     30-45 days              21-35 days

  Directional Bias        Bullish (want stock     Neutral (want
                          higher)                 range-bound)

  Capital Use             80% of portfolio        20% max

  Profit Source           Theta + stock           IV crush + Theta
                          appreciation            
  ----------------------- ----------------------- -----------------------

RULES NEVER TO BREAK

  ------- -----------------------------------------------------------------
  **1**   Never exceed 20% of capital in Vol Harvest strategy

  **2**   Never sell naked options on these names (always use defined risk)

  **3**   Never hold through earnings

  **4**   Never enter during active squeeze (wait for exhaustion)

  **5**   Always close at 50% profit or 7 DTE (whichever first)

  **6**   Close immediately if short strike touched

  **7**   Stop trading if down 10% of Vol Harvest capital in a month

  **8**   Never mix Vol Harvest and Wheel on the same underlying
  ------- -----------------------------------------------------------------

*Document Version: 1.0 \| Strategy: Separate from Wheel \| Capital
Allocation: Max 20%*