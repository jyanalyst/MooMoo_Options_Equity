"""
Test script for MooMoo CSV import functionality.
Creates sample CSV data and tests the parsing logic.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_journal import parse_moomoo_symbol, parse_moomoo_value, TradeJournal


def test_symbol_parsing():
    """Test MooMoo symbol parsing."""
    print("="*60)
    print("TEST: Symbol Parsing")
    print("="*60)

    test_cases = [
        ("A260220P130000", {"ticker": "A", "strike": 130.0, "option_type": "Put"}),
        ("ANET260220P120000", {"ticker": "ANET", "strike": 120.0, "option_type": "Put"}),
        ("MSFT260117C400000", {"ticker": "MSFT", "strike": 400.0, "option_type": "Call"}),
        ("AAPL260321P200000", {"ticker": "AAPL", "strike": 200.0, "option_type": "Put"}),
        ("GOOGL260515P175000", {"ticker": "GOOGL", "strike": 175.0, "option_type": "Put"}),
        ("V260220P350000", {"ticker": "V", "strike": 350.0, "option_type": "Put"}),
        # Edge case: low strike
        ("F260220P7500", {"ticker": "F", "strike": 7.5, "option_type": "Put"}),
    ]

    all_passed = True
    for symbol, expected in test_cases:
        result = parse_moomoo_symbol(symbol)

        if result is None:
            print(f"  [FAIL] {symbol} -> None (expected {expected})")
            all_passed = False
            continue

        ticker_match = result['ticker'] == expected['ticker']
        strike_match = abs(result['strike'] - expected['strike']) < 0.01
        type_match = result['option_type'] == expected['option_type']

        if ticker_match and strike_match and type_match:
            print(f"  [OK] {symbol} -> {result['ticker']} ${result['strike']} {result['option_type']}")
        else:
            print(f"  [FAIL] {symbol}")
            print(f"         Got: {result['ticker']} ${result['strike']} {result['option_type']}")
            print(f"         Expected: {expected['ticker']} ${expected['strike']} {expected['option_type']}")
            all_passed = False

    # Test spread (should return None)
    spread_result = parse_moomoo_symbol("MSFT260117P400000/MSFT260117P380000")
    if spread_result is None:
        print(f"  [OK] Spread symbol correctly returns None")
    else:
        print(f"  [FAIL] Spread should return None, got {spread_result}")
        all_passed = False

    return all_passed


def test_value_parsing():
    """Test MooMoo value parsing."""
    print("\n" + "="*60)
    print("TEST: Value Parsing")
    print("="*60)

    test_cases = [
        ("+10.00%", 10.0),
        ("-29.87%", -29.87),
        ("$1,234.56", 1234.56),
        ("1.58", 1.58),
        ("-500.00", -500.0),
        ("+17.50", 17.5),
        ("--", 0.0),
        ("", 0.0),
    ]

    all_passed = True
    for value, expected in test_cases:
        result = parse_moomoo_value(value)
        if abs(result - expected) < 0.01:
            print(f"  [OK] '{value}' -> {result}")
        else:
            print(f"  [FAIL] '{value}' -> {result} (expected {expected})")
            all_passed = False

    return all_passed


def test_csv_import():
    """Test CSV import with sample data."""
    print("\n" + "="*60)
    print("TEST: CSV Import (Non-Interactive)")
    print("="*60)

    # Create sample CSV
    sample_csv = '''Symbol,Name,Quantity,Current price,Average Cost,Market Value,% Unrealized P/L,Total P/L,Unrealized P/L,Realized P/L,Today's P/L,% of Portfolio,Currency,Today's Turnover,Today's Purchase@Avg Price,Today's Sales@Avg Price,Initial Margin,Delta,Gamma (options only),Vega (options only),Theta (options only),Rho (options only),IV (options only),Intrinsic Value (options only),Extrinsic Value (options only)
"A260220P130000","A 260220 130.00P","-1","1.58","1.75","-157.50","+10.00%","+17.50","+17.50","0.00","+70.00","-0.68%","USD","0.00","0 @ $0.00","0 @ $0.00","13000.00","-0.22","0.01","0.15","-0.05","-0.02","35.5%","0.00","1.58"
"ANET260220P120000","ANET 260220 120.00P","-1","5.00","3.85","-500.00","-29.87%","-115.00","-115.00","0.00","+49.70","-2.15%","USD","0.00","0 @ $0.00","0 @ $0.00","12000.00","-0.28","0.02","0.22","-0.08","-0.03","42.1%","0.00","5.00"
"MSFT260117C400000","MSFT 260117 400.00C","1","15.00","12.00","1500.00","+25.00%","300.00","300.00","0.00","+50.00","6.45%","USD","0.00","0 @ $0.00","0 @ $0.00","0.00","0.55","0.03","0.35","-0.12","-0.05","28.3%","5.00","10.00"
'''

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(sample_csv)
        temp_csv_path = f.name

    # Create temp journal
    temp_journal_path = tempfile.mktemp(suffix='.csv')

    try:
        journal = TradeJournal(journal_path=temp_journal_path)

        # Import with non-interactive mode
        results = journal.import_from_moomoo(temp_csv_path, vix=19.5, interactive=False)

        # Verify results
        print(f"\n  Results: {results}")

        # Should have 2 new positions (only puts with negative quantity)
        # MSFT call should be skipped, A and ANET puts should be added
        if len(results['new']) == 2:
            print(f"  [OK] Found 2 new put positions")
        else:
            print(f"  [FAIL] Expected 2 new positions, got {len(results['new'])}")
            return False

        # Check journal state
        open_positions = journal.get_open_trades()
        print(f"  [OK] Journal has {len(open_positions)} open positions")

        for _, pos in open_positions.iterrows():
            print(f"       - {pos['ticker']} ${pos['strike']}P | Premium: ${pos['premium']:.2f} | "
                  f"P/L: ${pos['unrealized_pnl']:.2f}")

        # Verify A position
        a_trade = open_positions[open_positions['ticker'] == 'A'].iloc[0]
        assert a_trade['strike'] == 130.0, f"A strike should be 130, got {a_trade['strike']}"
        assert a_trade['premium'] == 175.0, f"A premium should be 175, got {a_trade['premium']}"
        assert a_trade['unrealized_pnl'] == 17.50, f"A P/L should be 17.50, got {a_trade['unrealized_pnl']}"
        print(f"  [OK] A position data verified")

        # Verify ANET position
        anet_trade = open_positions[open_positions['ticker'] == 'ANET'].iloc[0]
        assert anet_trade['strike'] == 120.0, f"ANET strike should be 120, got {anet_trade['strike']}"
        assert anet_trade['premium'] == 385.0, f"ANET premium should be 385, got {anet_trade['premium']}"
        assert anet_trade['unrealized_pnl'] == -115.0, f"ANET P/L should be -115, got {anet_trade['unrealized_pnl']}"
        print(f"  [OK] ANET position data verified")

        return True

    finally:
        # Cleanup
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        if os.path.exists(temp_journal_path):
            os.remove(temp_journal_path)


def test_position_update():
    """Test position update from subsequent CSV import."""
    print("\n" + "="*60)
    print("TEST: Position Update")
    print("="*60)

    # Initial CSV
    csv1 = '''Symbol,Name,Quantity,Current price,Average Cost,Market Value,% Unrealized P/L,Total P/L,Unrealized P/L,Realized P/L,Today's P/L,% of Portfolio,Currency,Today's Turnover,Today's Purchase@Avg Price,Today's Sales@Avg Price,Initial Margin,Delta,Gamma (options only),Vega (options only),Theta (options only),Rho (options only),IV (options only),Intrinsic Value (options only),Extrinsic Value (options only)
"TSLA260220P250000","TSLA 260220 250.00P","-1","8.00","10.00","-800.00","+20.00%","+200.00","+200.00","0.00","+50.00","-3.45%","USD","0.00","0 @ $0.00","0 @ $0.00","25000.00","-0.25","0.02","0.30","-0.10","-0.04","45.0%","0.00","8.00"
'''

    # Updated CSV (P/L changed)
    csv2 = '''Symbol,Name,Quantity,Current price,Average Cost,Market Value,% Unrealized P/L,Total P/L,Unrealized P/L,Realized P/L,Today's P/L,% of Portfolio,Currency,Today's Turnover,Today's Purchase@Avg Price,Today's Sales@Avg Price,Initial Margin,Delta,Gamma (options only),Vega (options only),Theta (options only),Rho (options only),IV (options only),Intrinsic Value (options only),Extrinsic Value (options only)
"TSLA260220P250000","TSLA 260220 250.00P","-1","5.00","10.00","-500.00","+50.00%","+500.00","+500.00","0.00","+100.00","-2.15%","USD","0.00","0 @ $0.00","0 @ $0.00","25000.00","-0.18","0.01","0.20","-0.06","-0.03","38.0%","0.00","5.00"
'''

    temp_csv1 = tempfile.mktemp(suffix='.csv')
    temp_csv2 = tempfile.mktemp(suffix='.csv')
    temp_journal = tempfile.mktemp(suffix='.csv')

    try:
        with open(temp_csv1, 'w') as f:
            f.write(csv1)
        with open(temp_csv2, 'w') as f:
            f.write(csv2)

        journal = TradeJournal(journal_path=temp_journal)

        # First import
        results1 = journal.import_from_moomoo(temp_csv1, vix=20.0, interactive=False)
        assert len(results1['new']) == 1, "Should have 1 new position"

        # Check initial P/L
        pos = journal.get_open_trades().iloc[0]
        assert pos['unrealized_pnl'] == 200.0, f"Initial P/L should be 200, got {pos['unrealized_pnl']}"
        print(f"  [OK] Initial import: TSLA P/L = ${pos['unrealized_pnl']:.2f}")

        # Second import (update)
        results2 = journal.import_from_moomoo(temp_csv2, vix=20.0, interactive=False)
        assert len(results2['updated']) == 1, "Should have 1 updated position"
        assert len(results2['new']) == 0, "Should have 0 new positions"

        # Check updated P/L
        pos = journal.get_open_trades().iloc[0]
        assert pos['unrealized_pnl'] == 500.0, f"Updated P/L should be 500, got {pos['unrealized_pnl']}"
        assert pos['current_option_price'] == 5.0, f"Option price should be 5.0, got {pos['current_option_price']}"
        print(f"  [OK] Updated: TSLA P/L = ${pos['unrealized_pnl']:.2f}, Option = ${pos['current_option_price']:.2f}")

        return True

    finally:
        for f in [temp_csv1, temp_csv2, temp_journal]:
            if os.path.exists(f):
                os.remove(f)


def main():
    print("\n" + "="*60)
    print("MOOMOO IMPORT VALIDATION TESTS")
    print("="*60)

    results = []

    results.append(("Symbol Parsing", test_symbol_parsing()))
    results.append(("Value Parsing", test_value_parsing()))
    results.append(("CSV Import", test_csv_import()))
    results.append(("Position Update", test_position_update()))

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\nAll tests passed! MooMoo import is ready for production use.")
    else:
        print("\nSome tests failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
