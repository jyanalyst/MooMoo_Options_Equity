"""
Validation script for TradeJournal module.
Run this to verify the journal works correctly with sample data.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_journal import TradeJournal, classify_vix_regime

def main():
    print("="*60)
    print("TRADE JOURNAL VALIDATION TEST")
    print("="*60)

    # Test VIX regime classification
    print("\n1. Testing VIX regime classification...")
    assert classify_vix_regime(12) == "STOP", "VIX 12 should be STOP"
    assert classify_vix_regime(16) == "CAUTIOUS", "VIX 16 should be CAUTIOUS"
    assert classify_vix_regime(22) == "NORMAL", "VIX 22 should be NORMAL"
    assert classify_vix_regime(30) == "AGGRESSIVE", "VIX 30 should be AGGRESSIVE"
    print("   [OK] VIX regime tests passed")

    # Test TradeJournal initialization
    print("\n2. Initializing TradeJournal...")
    test_path = "test_journal_validation.csv"
    # Clean up any existing test file
    if os.path.exists(test_path):
        os.remove(test_path)

    journal = TradeJournal(journal_path=test_path)
    print("   [OK] Journal initialized")

    # Test log_entry
    print("\n3. Testing log_entry with multiple trades...")

    # Trade 1 - Technology (will close with 50% profit)
    trade_id_1 = journal.log_entry(
        ticker="MSFT",
        strike=450,
        dte=35,
        delta=-0.25,
        iv_rank=55,
        vix=18.5,
        premium=450,
        current_price=466,
        sector="Technology",
        capital_deployed=45000,
        notes="Earnings in 45 days"
    )
    print(f"   [OK] Trade #{trade_id_1} logged: MSFT $450P")

    # Trade 2 - Technology (will close at 21 DTE)
    trade_id_2 = journal.log_entry(
        ticker="AAPL",
        strike=200,
        dte=30,
        delta=-0.22,
        iv_rank=48,
        vix=19.2,
        premium=380,
        current_price=212,
        sector="Technology",
        capital_deployed=20000
    )
    print(f"   [OK] Trade #{trade_id_2} logged: AAPL $200P")

    # Trade 3 - Financials (will close with loss)
    trade_id_3 = journal.log_entry(
        ticker="JPM",
        strike=220,
        dte=42,
        delta=-0.28,
        iv_rank=62,
        vix=22.5,
        premium=520,
        current_price=235,
        sector="Financials",
        capital_deployed=22000
    )
    print(f"   [OK] Trade #{trade_id_3} logged: JPM $220P")

    # Trade 4 - Healthcare (will close with 50% profit, aggressive regime)
    trade_id_4 = journal.log_entry(
        ticker="UNH",
        strike=520,
        dte=38,
        delta=-0.24,
        iv_rank=58,
        vix=26.8,
        premium=680,
        current_price=545,
        sector="Healthcare",
        capital_deployed=52000
    )
    print(f"   [OK] Trade #{trade_id_4} logged: UNH $520P (AGGRESSIVE regime)")

    # Trade 5 - Consumer (stays open)
    trade_id_5 = journal.log_entry(
        ticker="COST",
        strike=900,
        dte=45,
        delta=-0.20,
        iv_rank=42,
        vix=17.5,
        premium=620,
        current_price=935,
        sector="Consumer Staples",
        capital_deployed=90000
    )
    print(f"   [OK] Trade #{trade_id_5} logged: COST $900P (stays open)")

    # Test log_exit
    print("\n4. Testing log_exit...")

    journal.log_exit(trade_id=1, exit_reason="50% profit", pnl=225)
    print("   [OK] Trade #1 closed: 50% profit, P&L: $225")

    journal.log_exit(trade_id=2, exit_reason="21 DTE", pnl=285)
    print("   [OK] Trade #2 closed: 21 DTE, P&L: $285")

    journal.log_exit(trade_id=3, exit_reason="2x loss", pnl=-780)
    print("   [OK] Trade #3 closed: 2x loss, P&L: -$780")

    journal.log_exit(trade_id=4, exit_reason="50% profit", pnl=340)
    print("   [OK] Trade #4 closed: 50% profit, P&L: $340")

    # Test show_stats
    print("\n5. Testing show_stats()...")
    journal.show_stats()

    # Test show_open_positions
    print("\n6. Testing show_open_positions()...")
    journal.show_open_positions()

    # Test get methods
    print("\n7. Testing getter methods...")
    trade = journal.get_trade(1)
    assert trade is not None, "get_trade(1) should return trade"
    assert trade['ticker'] == "MSFT", "Trade 1 should be MSFT"
    print("   [OK] get_trade() works")

    open_trades = journal.get_open_trades()
    assert len(open_trades) == 1, "Should have 1 open trade"
    assert open_trades.iloc[0]['ticker'] == "COST", "Open trade should be COST"
    print(f"   [OK] get_open_trades() returns {len(open_trades)} trade(s)")

    closed_trades = journal.get_closed_trades()
    assert len(closed_trades) == 4, "Should have 4 closed trades"
    print(f"   [OK] get_closed_trades() returns {len(closed_trades)} trade(s)")

    # Clean up test file
    if os.path.exists(test_path):
        os.remove(test_path)
        print(f"\n   [OK] Cleaned up test file: {test_path}")

    print("\n" + "="*60)
    print("ALL VALIDATION TESTS PASSED!")
    print("="*60)
    print("\nThe trade journal is ready for production use.")
    print("See 'Integration Example' section below for usage.\n")

    # Print integration example
    print("-"*60)
    print("INTEGRATION EXAMPLE")
    print("-"*60)
    print("""
# In your screener_wheel.py or trading workflow:

from trade_journal import TradeJournal

# Initialize journal (creates/loads journal_data.csv)
journal = TradeJournal()

# When you identify a trade from the screener:
trade_id = journal.log_entry(
    ticker="MSFT",
    strike=450,
    dte=35,
    delta=-0.25,
    iv_rank=55,
    vix=18.5,              # Check current VIX
    premium=450,           # Premium you'll collect
    current_price=466,     # Stock price at entry
    sector="Technology",
    capital_deployed=45000 # strike * 100
)

# When you close a position:
journal.log_exit(
    trade_id=trade_id,
    exit_reason="50% profit",  # or "21 DTE", "2x loss", "7 DTE", "assignment"
    pnl=225.00
)

# View your performance anytime:
journal.show_stats()

# Check open positions:
journal.show_open_positions()

# CLI commands:
# python trade_journal.py stats
# python trade_journal.py open
""")


if __name__ == "__main__":
    main()
