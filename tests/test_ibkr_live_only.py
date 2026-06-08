"""
Unit tests for IBKRDataFetcher's LIVE-only market-data behavior.

The scanner runs live OPRA data only and must NEVER fall back to delayed (stale
after-hours quotes produce junk candidates — $0.01 bids, 100%+ spreads). These
tests drive ``_snapshot_options`` / ``_request_chain_data`` with a fake ``ib``
object (no network, no broker) to verify:

  1. The chain request asks for OPRA option ticks only (100,101) — NOT the
     underlying-equity ticks 104/106 that trip Error 10091.
  2. A 10091 error never switches the session to delayed (market_data_type stays
     1; reqMarketDataType(3) is never issued); whatever live Greeks arrived are
     still returned.
  3. When no live Greeks arrive, rows come back Greek-less (caller skips the stock)
     and we still don't switch to delayed.
  4. A healthy live feed builds full rows on type 1.
  5. _on_ibkr_error latches a one-time diagnostic and leaves market_data_type alone.

See ibkr_data_fetcher.py: _request_chain_data / _snapshot_options / _on_ibkr_error.
"""

import pytest

from ibkr_data_fetcher import IBKRDataFetcher


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _Event:
    """Minimal stand-in for ib_async's errorEvent (supports += and emit)."""

    def __init__(self):
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def emit(self, *args):
        for h in self._handlers:
            h(*args)


class _Greeks:
    impliedVol = 0.25
    delta = -0.25
    gamma = 0.01
    theta = -0.02
    vega = 0.10


class _Ticker:
    def __init__(self, greeks):
        self.modelGreeks = greeks
        self.putOpenInterest = 100
        self.callOpenInterest = 100
        self.volume = 10
        self.bid = 1.0
        self.ask = 1.1
        self.last = 1.05


class _Contract:
    def __init__(self, strike):
        self.strike = float(strike)
        self.localSymbol = f"TEST{strike}"
        self.symbol = "TEST"
        self.lastTradeDateOrContractMonth = "20260717"


class FakeIB:
    """Configurable fake IB. ``deny`` emits 10091 on the first sleep; ``greeks``
    controls whether live tickers populate modelGreeks. Records every
    genericTickList and reqMarketDataType call for assertions."""

    def __init__(self, deny=False, greeks=True):
        self.errorEvent = _Event()
        self.deny = deny
        self.greeks = greeks
        self.mkt_type_calls = []
        self.tick_lists = []
        self._emitted = False

    def reqMarketDataType(self, t):
        self.mkt_type_calls.append(t)

    def reqMktData(self, c, genericTickList=None, snapshot=False):
        self.tick_lists.append(genericTickList)
        return _Ticker(_Greeks() if self.greeks else None)

    def cancelMktData(self, c):
        pass

    def sleep(self, _secs):
        if self.deny and not self._emitted:
            self._emitted = True
            self.errorEvent.emit(11, 10091, "requires additional subscription", None)


def _make_fetcher(ib):
    """Build an IBKRDataFetcher without running __init__ (no FMP/yfinance setup)."""
    f = object.__new__(IBKRDataFetcher)
    f.market_data_type = 1
    f._warned_subscription = False
    f.ib = ib
    ib.errorEvent += f._on_ibkr_error
    return f


_CONTRACTS = [_Contract(s) for s in (70, 72, 74, 76)]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_request_uses_opra_ticks_only():
    # Must NOT request 104/106 (underlying-equity ticks that trip Error 10091).
    ib = FakeIB(greeks=True)
    f = _make_fetcher(ib)

    f._request_chain_data(_CONTRACTS)

    assert ib.tick_lists, "expected reqMktData to be called"
    assert all(tl == "100,101" for tl in ib.tick_lists)
    assert all("104" not in tl and "106" not in tl for tl in ib.tick_lists)


def test_10091_never_switches_to_delayed():
    # Live feed partially denied (10091) but Greeks arrive — stay LIVE, no flip.
    ib = FakeIB(deny=True, greeks=True)
    f = _make_fetcher(ib)

    rows = f._snapshot_options(_CONTRACTS, "P")

    assert f.market_data_type == 1  # never changed
    assert 3 not in ib.mkt_type_calls  # reqMarketDataType(3) never issued
    assert f._warned_subscription is True  # one-time diagnostic latched
    assert all(r["delta"] is not None for r in rows)


def test_no_live_greeks_returns_greekless_rows_no_delayed():
    # Market closed / subscription gap: no Greeks. Caller skips the stock; we must
    # NOT substitute delayed data.
    ib = FakeIB(deny=False, greeks=False)
    f = _make_fetcher(ib)

    rows = f._snapshot_options(_CONTRACTS, "P")

    assert f.market_data_type == 1
    assert 3 not in ib.mkt_type_calls
    assert all(r["delta"] is None for r in rows)  # Greek-less -> screener drops them


def test_healthy_live_builds_full_rows():
    ib = FakeIB(deny=False, greeks=True)
    f = _make_fetcher(ib)

    rows = f._snapshot_options(_CONTRACTS, "P")

    assert f.market_data_type == 1
    assert 3 not in ib.mkt_type_calls
    assert all(r["delta"] is not None for r in rows)
    assert all(r["implied_volatility"] is not None for r in rows)


@pytest.mark.parametrize(
    "code,expected",
    [(10091, True), (10089, True), (354, True), (200, False), (2104, False)],
)
def test_error_handler_latches_once_and_keeps_live(code, expected):
    ib = FakeIB()
    f = _make_fetcher(ib)
    f._on_ibkr_error(11, code, "msg", None)
    assert f._warned_subscription is expected
    assert f.market_data_type == 1  # diagnostic only — never mutates data type
