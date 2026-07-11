"""
Trade-journal unit tests: MooMoo symbol/value parsing and the single
VIX-regime source of truth (vix_monitor.get_regime, wrapped by trade_journal).
"""

import pytest

import vix_monitor
from trade_journal import classify_vix_regime, parse_moomoo_symbol, parse_moomoo_value


# --------------------------------------------------------------------------- #
# parse_moomoo_symbol
# --------------------------------------------------------------------------- #
def test_parse_single_letter_ticker_put():
    r = parse_moomoo_symbol("A260220P130000")
    assert r["ticker"] == "A"
    assert r["expiry_date"].strftime("%Y-%m-%d") == "2026-02-20"
    assert r["option_type"] == "Put"
    assert r["strike"] == 130.00


def test_parse_multi_letter_ticker_call():
    r = parse_moomoo_symbol("MSFT260117C400000")
    assert r["ticker"] == "MSFT"
    assert r["expiry_date"].strftime("%Y-%m-%d") == "2026-01-17"
    assert r["option_type"] == "Call"
    assert r["strike"] == 400.00


def test_parse_fractional_strike():
    r = parse_moomoo_symbol("F260320P7500")
    assert r["strike"] == 7.50


def test_parse_lowercase_normalized():
    r = parse_moomoo_symbol("anet260220p120000")
    assert r["ticker"] == "ANET"
    assert r["moomoo_symbol"] == "ANET260220P120000"


def test_spread_leg_symbol_skipped():
    assert parse_moomoo_symbol("AMD260117P120000/AMD260117P110000") is None


def test_garbage_symbol_returns_none():
    assert parse_moomoo_symbol("NOT A SYMBOL") is None
    assert parse_moomoo_symbol("TOOLONGTICKER260117P1000") is None


def test_invalid_date_returns_none():
    assert parse_moomoo_symbol("MSFT261345P100000") is None  # month 13, day 45


# --------------------------------------------------------------------------- #
# parse_moomoo_value
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+10.00%", 10.00),
        ("-29.87%", -29.87),
        ("$1,234.56", 1234.56),
        ("1.58", 1.58),
    ],
)
def test_parse_moomoo_value(raw, expected):
    assert parse_moomoo_value(raw) == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# VIX regime: one source of truth
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vix", [5, 13.99, 14, 17.99, 18, 25, 25.01, 40])
def test_regime_single_source_of_truth(vix):
    assert classify_vix_regime(vix) == vix_monitor.get_regime(vix)


def test_regime_bands_v31():
    assert vix_monitor.get_regime(13.9) == "STOP"
    assert vix_monitor.get_regime(16.0) == "CAUTIOUS"
    assert vix_monitor.get_regime(20.0) == "NORMAL"
    assert vix_monitor.get_regime(26.0) == "AGGRESSIVE"
