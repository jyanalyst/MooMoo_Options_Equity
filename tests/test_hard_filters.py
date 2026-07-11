"""
Hard-filter enforcement tests for WheelScreener._analyze_option.

Production rule: a contract with missing bid/ask/delta, thin OI, a wide spread,
or a premium below the floor is HARD-REJECTED (hard_reject set, zero scores) —
never approximated, never ranked. One test per reject reason plus a passing
contract, and assertions that config carries the production thresholds.
"""

import pandas as pd
import pytest

from config import WHEEL_CONFIG
from screener_wheel import WheelScreener


@pytest.fixture
def screener():
    return WheelScreener(data_fetcher=None)


def _put(
    strike=100.0,
    bid=1.5,
    ask=1.56,
    delta=-0.25,
    volume=200,
    open_interest=500,
    iv=35.0,
):
    return pd.Series(
        {
            "strike_price": strike,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "last_price": bid,
            "volume": volume,
            "open_interest": open_interest,
            "implied_volatility": iv,
            "code": "TEST",
        }
    )


def test_config_carries_production_thresholds():
    assert WHEEL_CONFIG["open_interest_min"] >= 100
    assert WHEEL_CONFIG["bid_ask_spread_max_pct"] <= 0.10
    assert WHEEL_CONFIG["premium_pct_of_strike_min"] >= 0.005
    # The relaxed volume knob is gone: OI is the wheel liquidity gate.
    assert "volume_min" not in WHEEL_CONFIG


def test_clean_contract_passes(screener):
    res = screener._analyze_option(_put(), stock_price=100.0, dte=35)
    assert res["hard_reject"] is None
    assert res["quality_score"] > 0


def test_missing_bid_rejected_not_fabricated(screener):
    res = screener._analyze_option(_put(bid=0.0, ask=1.6), stock_price=100.0, dte=35)
    assert res["hard_reject"] == "no valid bid/ask"
    assert res["quality_score"] == 0
    # No last_price*0.98 fabrication: bid stays exactly what the market showed.
    assert res["bid"] == 0.0


def test_missing_ask_rejected(screener):
    res = screener._analyze_option(_put(ask=0.0), stock_price=100.0, dte=35)
    assert res["hard_reject"] == "no valid bid/ask"


def test_missing_delta_rejected_not_approximated(screener):
    res = screener._analyze_option(_put(delta=None), stock_price=100.0, dte=35)
    assert res["hard_reject"] == "missing delta (no Greeks)"
    # The old moneyness approximation must not resurrect a fake delta.
    assert res["delta"] == 0.0


def test_low_open_interest_rejected(screener):
    thin = WHEEL_CONFIG["open_interest_min"] - 1
    res = screener._analyze_option(_put(open_interest=thin), stock_price=100.0, dte=35)
    assert res["hard_reject"] is not None
    assert "OI" in res["hard_reject"]


def test_wide_spread_rejected(screener):
    # bid 1.00 / ask 1.20 => spread ~18.2% of mid, over the 10% cap
    res = screener._analyze_option(_put(bid=1.00, ask=1.20), stock_price=100.0, dte=35)
    assert res["hard_reject"] is not None
    assert "spread" in res["hard_reject"]


def test_premium_below_floor_rejected(screener):
    # 0.30 on a 100 strike = 0.30% < 0.5% floor (spread kept tight to isolate)
    res = screener._analyze_option(_put(bid=0.30, ask=0.31), stock_price=100.0, dte=35)
    assert res["hard_reject"] is not None
    assert "premium" in res["hard_reject"]


def test_iv_stored_as_percentage_not_rescaled(screener):
    res = screener._analyze_option(_put(iv=42.7), stock_price=100.0, dte=35)
    assert res["iv"] == 42.7  # not 4270 (the old x100 bug)


def test_rejected_contract_still_reports_yields(screener):
    """Yield fields stay populated on rejects so diagnostics remain readable."""
    res = screener._analyze_option(_put(open_interest=1), stock_price=100.0, dte=36)
    assert res["hard_reject"] is not None
    assert res["return_pct"] == pytest.approx(1.5)
    assert res["annualized_return_pct"] == pytest.approx(1.5 * 365 / 36, rel=1e-3)
