#!/usr/bin/env python3
"""
Test script to verify MooMoo API responses for options scanner debugging
"""

from moomoo import *

def test_moomoo_api():
    """Test MooMoo OpenD API responses"""

    print("="*60)
    print("MOOMOO API TEST SCRIPT")
    print("="*60)

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

        # Test 2: Get expirations for INTC
        print("\n3. Testing option expirations (INTC)...")
        symbol = "US.INTC"
        ret, expirations = quote_ctx.get_option_expiration_date(code=symbol)
        print(f"   Expirations API call: {ret}")

        if ret == 0 and not expirations.empty:
            print(f"   ✅ Found {len(expirations)} expirations")
            print(f"   Sample expirations: {expirations['strike_time'].tolist()[:5]}")

            # Get target expiration (~30 DTE)
            if len(expirations) >= 5:
                target_exp = expirations['strike_time'].iloc[4]  # ~30 DTE
                print(f"   Using expiration: {target_exp}")

                # Test 3: Get options chain using updated method (static + snapshot)
                print(f"\n4. Testing updated options chain method...")

                # Import and use our updated data fetcher
                from data_fetcher import get_data_fetcher
                fetcher = get_data_fetcher(use_mock=False)

                if fetcher.connect():
                    print("   Using updated get_options_chain() method...")

                    # This now internally calls get_option_chain() + get_market_snapshot()
                    chain = fetcher.get_options_chain(
                        ticker="INTC",
                        expiration=target_exp,
                        option_type="PUT"
                    )

                    if chain is not None and not chain.empty:
                        print(f"   ✅ Found {len(chain)} PUT options with merged data")
                        print(f"   Columns: {sorted(chain.columns.tolist())}")
                        print("   Sample data:")
                        print(chain.head(3).to_string())

                        # Show what pricing columns we actually got
                        pricing_cols = ['last_price', 'bid', 'ask', 'volume', 'delta', 'implied_volatility', 'open_interest']
                        available_pricing = [col for col in pricing_cols if col in chain.columns]
                        print(f"   Available pricing columns: {available_pricing}")

                        # Check for required columns
                        required_cols = ['strike_price', 'delta', 'bid', 'ask', 'volume', 'open_interest']
                        missing_cols = [col for col in required_cols if col not in chain.columns]
                        if missing_cols:
                            print(f"   ⚠️  Missing columns: {missing_cols}")
                        else:
                            print("   ✅ All required columns present")

                        # Check delta range
                        if 'delta' in chain.columns:
                            deltas = chain['delta'].dropna()
                            if not deltas.empty:
                                print(f"   Delta range: {deltas.min():.3f} to {deltas.max():.3f}")
                                target_deltas = deltas[(deltas >= -0.30) & (deltas <= -0.20)]
                                print(f"   Options in target delta range (-0.20 to -0.30): {len(target_deltas)}")
                            else:
                                print("   ❌ No delta values found")
                        else:
                            print("   ❌ Delta column missing")

                        # Check volume
                        if 'volume' in chain.columns:
                            volumes = chain['volume'].dropna()
                            if not volumes.empty:
                                print(f"   Volume stats: min={volumes.min()}, max={volumes.max()}, mean={volumes.mean():.0f}")
                                high_volume = volumes[volumes >= 100]
                                print(f"   Options with volume >= 100: {len(high_volume)}")
                            else:
                                print("   ❌ No volume values found")
                        else:
                            print("   ❌ Volume column missing")

                    else:
                        print("   ❌ No options data returned from updated method")
                        if chain is not None:
                            print(f"   Chain type: {type(chain)}, Empty: {chain.empty if hasattr(chain, 'empty') else 'N/A'}")
                        else:
                            print("   Chain is None")

                    fetcher.disconnect()
                else:
                    print("   ❌ Could not connect to test updated method")
            else:
                print("   ❌ Not enough expirations to test chain")
        else:
            print("   ❌ No expirations returned")
            if expirations is not None:
                print(f"   Response type: {type(expirations)}, Empty: {expirations.empty if hasattr(expirations, 'empty') else 'N/A'}")
            else:
                print("   Expirations is None")

        # Test 4: Try different stock
        print("\n5. Testing with different stock (AAPL)...")
        symbol2 = "US.AAPL"
        ret3, exp2 = quote_ctx.get_option_expiration_date(code=symbol2)
        print(f"   AAPL expirations: {ret3}")

        if ret3 == 0 and exp2 is not None and not exp2.empty:
            print(f"   ✅ AAPL has {len(exp2)} expirations")
        else:
            print("   ❌ AAPL expirations failed")

        print("\n✅ API Test Complete")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        quote_ctx.close()
        print("\nDisconnected from MooMoo OpenD")

if __name__ == "__main__":
    test_moomoo_api()
