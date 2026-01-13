#!/usr/bin/env python3
"""
Test script to check what get_market_snapshot() returns for options
This will determine if OPRA subscription is required for Greeks
"""

from moomoo import *

def test_market_snapshot():
    """Test get_market_snapshot for individual options to see what data is available"""

    print("="*70)
    print("MOOMOO API: MARKET SNAPSHOT TEST FOR GREEKS")
    print("="*70)

    # Initialize connection
    print("\n1. Connecting to MooMoo OpenD...")
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

    try:
        # Test 1: Connection health
        print("\n2. Testing connection...")
        ret, data = quote_ctx.get_global_state()
        print(f"   Connection test: {ret} - {data}")

        if ret != 0:
            print("❌ Connection failed!")
            return

        print("✅ Connection successful")

        # Test 2: Get option chain to find option codes
        print("\n3. Getting INTC option chain...")
        symbol = "US.INTC"
        expiration = "2026-02-13"  # ~30 DTE

        ret, chain = quote_ctx.get_option_chain(
            code=symbol,
            start=expiration,
            end=expiration,
            option_type=OptionType.PUT
        )

        print(f"   Option chain API call: {ret}")

        if ret != 0 or chain is None or chain.empty:
            print("❌ Failed to get option chain")
            return

        print(f"   ✅ Found {len(chain)} PUT options for {symbol} @ {expiration}")
        print(f"   Chain columns: {chain.columns.tolist()}")

        # Find a mid-strike option (around current price)
        # Assume INTC around $47 based on previous tests
        current_price = 47.0
        chain_copy = chain.copy()
        chain_copy['distance'] = abs(chain_copy['strike_price'] - current_price)
        mid_strike_option = chain_copy.loc[chain_copy['distance'].idxmin()]

        option_code = mid_strike_option['code']
        strike_price = mid_strike_option['strike_price']

        print(f"\n4. Testing market snapshot for: {option_code} (Strike: ${strike_price})")

        # Test 3: Get market snapshot for this specific option
        ret2, snapshot = quote_ctx.get_market_snapshot([option_code])

        print(f"   Market snapshot API call: {ret2}")

        if ret2 == 0 and snapshot is not None and not snapshot.empty:
            print("   ✅ Market snapshot successful")
            print(f"   Snapshot shape: {snapshot.shape}")
            print(f"   Snapshot columns: {snapshot.columns.tolist()}")

            # Show all data for this option
            print(f"\n   FULL SNAPSHOT DATA for {option_code}:")
            print("="*50)
            for col in snapshot.columns:
                value = snapshot[col].iloc[0]
                print(f"   {col:<20}: {value}")

            # Check specifically for Greeks and pricing
            print("\n   GREEKS CHECK:")
            greek_cols = ['delta', 'gamma', 'theta', 'vega', 'implied_volatility']
            available_greeks = [col for col in greek_cols if col in snapshot.columns]
            missing_greeks = [col for col in greek_cols if col not in snapshot.columns]

            if available_greeks:
                print(f"   ✅ Available Greeks: {available_greeks}")
                for col in available_greeks:
                    value = snapshot[col].iloc[0]
                    print(f"      {col}: {value}")
            else:
                print("   ❌ No Greeks available")

            if missing_greeks:
                print(f"   ❌ Missing Greeks: {missing_greeks}")

            print("\n   PRICING CHECK:")
            price_cols = ['bid', 'ask', 'last_price', 'volume', 'open_interest']
            available_prices = [col for col in price_cols if col in snapshot.columns]
            missing_prices = [col for col in price_cols if col not in snapshot.columns]

            if available_prices:
                print(f"   ✅ Available pricing: {available_prices}")
                for col in available_prices:
                    value = snapshot[col].iloc[0]
                    print(f"      {col}: {value}")
            else:
                print("   ❌ No pricing data available")

            if missing_prices:
                print(f"   ❌ Missing pricing: {missing_prices}")

        else:
            print("   ❌ Market snapshot failed")
            if snapshot is not None:
                print(f"   Snapshot type: {type(snapshot)}, Empty: {snapshot.empty if hasattr(snapshot, 'empty') else 'N/A'}")
            else:
                print("   Snapshot is None")

        # Test 4: Try a different option (higher strike)
        print("\n5. Testing different option (higher strike)...")
        high_strike_option = chain.loc[chain['strike_price'].idxmax()]
        high_option_code = high_strike_option['code']
        high_strike_price = high_strike_option['strike_price']

        print(f"   Testing: {high_option_code} (Strike: ${high_strike_price})")

        ret3, high_snapshot = quote_ctx.get_market_snapshot([high_option_code])

        if ret3 == 0 and high_snapshot is not None and not high_snapshot.empty:
            delta_available = 'delta' in high_snapshot.columns
            bid_available = 'bid' in high_snapshot.columns
            print(f"   Greeks available: {delta_available}")
            print(f"   Bid/Ask available: {bid_available}")

            if delta_available:
                delta_value = high_snapshot['delta'].iloc[0]
                print(f"   Delta value: {delta_value}")

        print("\n6. CONCLUSION:")
        print("   Based on this test, determine if OPRA subscription is needed for Greeks")
        print("   If Greeks are missing, approximations will be used in scanner")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        quote_ctx.close()
        print("\nDisconnected from MooMoo OpenD")

if __name__ == "__main__":
    test_market_snapshot()
