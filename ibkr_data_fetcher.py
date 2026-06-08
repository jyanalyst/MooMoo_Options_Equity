"""
IBKR Data Fetcher for Options Scanner

Drop-in alternative to HybridDataFetcher (data_fetcher.py) that sources the
OPTIONS CHAIN + Greeks from Interactive Brokers instead of MooMoo. The hybrid
design is preserved otherwise:

- Stock quotes:       FMP API        (inherited from HybridDataFetcher)
- Stock historical:   yfinance       (inherited from HybridDataFetcher)
- Options chains:     IBKR (ib_async) via IB Gateway / TWS  <-- the only change

Why subclass HybridDataFetcher: the screener and IVAnalyzer consume a small,
fixed interface. Only get_option_expirations() and get_options_chain() touch
the broker, so we override exactly those two (plus connect/disconnect) and reuse
everything else (FMP quote caching, yfinance history, DTE helpers) unchanged.

Requirements:
- pip install ib_async
- IB Gateway or TWS running and logged in (default port 4001 = Gateway live).
- OPRA (US options) market-data subscription for live Greeks.
"""

from typing import Optional, List, Dict, Any
import logging
import math

import pandas as pd

from data_fetcher import HybridDataFetcher, MockDataFetcher, YFINANCE_AVAILABLE
from universe import strip_moomoo_prefix
from config import (
    IBKR_HOST,
    IBKR_PORT,
    IBKR_CLIENT_ID,
    IBKR_MARKET_DATA_TYPE,
    IBKR_PUT_STRIKE_BAND,
    IBKR_MAX_STRIKES,
)

# ib_async — the maintained successor to ib_insync
try:
    from ib_async import IB, Stock, Option

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("Warning: ib_async not installed. Run: pip install ib_async")


def _clean(value: Optional[float]) -> Optional[float]:
    """Map IBKR's NaN/sentinel market-data values to None.

    IBKR fills missing fields with float('nan') (and occasionally -1 for size
    fields). Downstream code uses pd.isna(), so returning None keeps the chain
    DataFrame consistent with the MooMoo path.
    """
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except (TypeError, ValueError):
        return None
    if value == -1:  # IBKR size sentinel for "no data"
        return None
    return value


# IBKR error codes meaning "part of the requested market data needs a subscription
# you don't have for the API". We run LIVE-only (no delayed fallback); these are
# surfaced once as a clear diagnostic. In practice 10091 was triggered by the
# underlying-equity generic ticks (104/106), not by OPRA itself — those ticks are
# no longer requested (see _request_chain_data).
#   354   = not subscribed
#   10089 = requires additional subscription for API
#   10090 = part of requested market data is not subscribed
#   10091 = part of requested market data requires additional subscription for API
#   10167 = market data not subscribed; displaying delayed instead
_SUBSCRIPTION_ERROR_CODES = {354, 10089, 10090, 10091, 10167}


class _SubscriptionErrorFilter(logging.Filter):
    """Drop ib_async's per-line subscription-error log spam.

    If IBKR ever denies part of the live feed it logs one message per contract per
    data line — pure noise. We surface a single clear diagnostic via _on_ibkr_error
    and mute the rest here.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(str(code) in msg for code in _SUBSCRIPTION_ERROR_CODES)


class IBKRDataFetcher(HybridDataFetcher):
    """Hybrid fetcher with IBKR (ib_async) as the options-data source."""

    def __init__(
        self,
        host: str = IBKR_HOST,
        port: int = IBKR_PORT,
        client_id: int = IBKR_CLIENT_ID,
    ):
        # Sets up FMP quote cache + yfinance history (and validates yfinance).
        super().__init__()

        self.ib_host = host
        self.ib_port = port
        self.client_id = client_id

        self.ib = None
        self.ibkr_connected = False

        # Market-data type (1=live OPRA). LIVE-ONLY by config — we never fall back
        # to delayed; if the live feed is unavailable a stock is skipped (warned).
        self.market_data_type = IBKR_MARKET_DATA_TYPE
        # Latched by the errorEvent handler so the subscription-denied diagnostic
        # prints at most once per session (it never changes market_data_type).
        self._warned_subscription = False

        # Per-ticker option-definition cache: {symbol: secdef dict}. reqSecDefOptParams
        # is per-underlying, so we cache expirations + strikes for the session.
        self._secdef_cache: Dict[str, Dict] = {}

        if not IB_ASYNC_AVAILABLE:
            print("Warning: ib_async not available - options data will not work")

    # =========================================================================
    # CONNECTION (overrides MooMoo connect/disconnect)
    # =========================================================================

    @property
    def connected(self) -> bool:  # type: ignore[override]
        return self.ibkr_connected

    def connect(self) -> bool:
        """Connect to IB Gateway / TWS for options data.

        Stock quotes (FMP) and history (yfinance) do not need this connection.
        A failed connect degrades gracefully (no options) rather than crashing.
        """
        if not IB_ASYNC_AVAILABLE:
            print("[WARN] ib_async not available - options features disabled")
            return False

        try:
            self.ib = IB()
            # readonly=True: we only pull market data, never place orders.
            self.ib.connect(
                self.ib_host,
                self.ib_port,
                clientId=self.client_id,
                readonly=True,
                timeout=15,
            )
            # Surface "subscription required" errors (10091 etc.) once as a clear
            # diagnostic and mute the per-line spam — no fallback, we stay live.
            self.ib.errorEvent += self._on_ibkr_error
            logging.getLogger("ib_async.wrapper").addFilter(_SubscriptionErrorFilter())

            # LIVE-only (1=live OPRA). We never switch to delayed at runtime; if the
            # live feed yields no Greeks for a stock it is skipped (see _snapshot_options).
            self.ib.reqMarketDataType(self.market_data_type)

            self.ibkr_connected = True
            mode = "LIVE" if self.market_data_type == 1 else "DELAYED ~15min"
            print(f"[OK] Connected to IB Gateway at {self.ib_host}:{self.ib_port}")
            print("     Stock quotes: FMP API (Real-time)")
            print(f"     Options data: IBKR API ({mode})")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to connect to IB Gateway: {e}")
            print(
                "        Options features will not work without IB Gateway/TWS running"
            )
            self.ibkr_connected = False
            return False

    def disconnect(self):
        """Close the IBKR connection."""
        if self.ib is not None and self.ibkr_connected:
            try:
                self.ib.disconnect()
            finally:
                self.ibkr_connected = False
                print("Disconnected from IB Gateway")

    def _ensure_ibkr_connected(self):
        if not self.ibkr_connected:
            if not self.connect():
                raise RuntimeError(
                    "IB Gateway not connected - required for options data"
                )

    def _on_ibkr_error(self, reqId, errorCode, errorString, contract=None):
        """ib_async errorEvent handler: one-time subscription-denied diagnostic.

        We run live-only and never fall back to delayed, so this only surfaces a
        single clear hint (the per-line spam is muted by _SubscriptionErrorFilter).
        It must not change market_data_type.
        """
        if errorCode in _SUBSCRIPTION_ERROR_CODES and not self._warned_subscription:
            self._warned_subscription = True
            print(
                f"[WARN] IBKR denied part of the live feed (Error {errorCode}). "
                "Live Greeks need OPRA enabled for the API; underlying-equity ticks "
                "are not requested, so verify the OPRA-for-API subscription if Greeks "
                "are missing."
            )

    # =========================================================================
    # OPTIONS DATA (overrides MooMoo implementations)
    # =========================================================================

    def _get_secdef(self, symbol: str) -> Optional[Dict]:
        """Fetch (and cache) the option definition for an underlying.

        Returns a dict with sorted expirations ('YYYYMMDD'), sorted strikes,
        tradingClass and multiplier, or None if unavailable.
        """
        if symbol in self._secdef_cache:
            return self._secdef_cache[symbol]

        self._ensure_ibkr_connected()

        try:
            underlying = Stock(symbol, "SMART", "USD")
            qualified = self.ib.qualifyContracts(underlying)
            if not qualified or not qualified[0].conId:
                print(f"Warning: could not qualify underlying {symbol}")
                return None
            underlying = qualified[0]

            chains = self.ib.reqSecDefOptParams(
                underlying.symbol, "", underlying.secType, underlying.conId
            )
            if not chains:
                print(f"Warning: no option parameters for {symbol}")
                return None

            # Prefer the SMART chain; otherwise the one with the most expirations.
            smart = [c for c in chains if c.exchange == "SMART"]
            chain = (smart or sorted(chains, key=lambda c: len(c.expirations)))[
                -1 if not smart else 0
            ]

            secdef = {
                "expirations": sorted(chain.expirations),
                "strikes": sorted(float(s) for s in chain.strikes),
                "trading_class": chain.tradingClass,
                "multiplier": chain.multiplier,
                "con_id": underlying.conId,
            }
            self._secdef_cache[symbol] = secdef
            return secdef

        except Exception as e:
            print(f"Error fetching option definition for {symbol}: {e}")
            return None

    def get_option_expirations(self, ticker: str) -> Optional[List[str]]:
        """Available option expirations as 'YYYY-MM-DD' strings (or None)."""
        symbol = strip_moomoo_prefix(ticker)
        secdef = self._get_secdef(symbol)
        if not secdef or not secdef["expirations"]:
            return None
        # IBKR uses 'YYYYMMDD'; the screener expects 'YYYY-MM-DD'.
        return [f"{e[0:4]}-{e[4:6]}-{e[6:8]}" for e in secdef["expirations"]]

    def _select_contracts(
        self, contracts: list, spot: Optional[float], option_type: str
    ) -> list:
        """Pick a manageable band of contracts near spot to bound market-data lines."""
        if not contracts:
            return []
        if spot is None or spot <= 0:
            return sorted(contracts, key=lambda c: c.strike)[:IBKR_MAX_STRIKES]

        lo_frac, hi_frac = IBKR_PUT_STRIKE_BAND
        if option_type.upper() == "PUT":
            lo, hi = spot * lo_frac, spot * hi_frac
        else:  # mirror the band above spot for calls
            lo, hi = spot * (2 - hi_frac), spot * (2 - lo_frac)

        banded = [c for c in contracts if lo <= c.strike <= hi]
        if not banded:
            banded = contracts
        # Keep the strikes nearest spot if the band is still too wide.
        banded = sorted(banded, key=lambda c: abs(c.strike - spot))[:IBKR_MAX_STRIKES]
        return sorted(banded, key=lambda c: c.strike)

    def _request_chain_data(self, contracts: list) -> list:
        """Open streaming market-data lines for the contracts and return tickers.

        Generic ticks 100 (option volume) + 101 (open interest) are OPRA option
        data. We deliberately do NOT request 104 (historical vol) / 106 (option
        implied vol): those are *underlying-equity* ticks that pull the stock's
        NYSE/Nasdaq feed and trip Error 10091 on an OPRA-only subscription. Greeks
        (delta/gamma/theta/vega + impliedVol) arrive automatically as modelGreeks
        on the option tick — they don't need 104/106.
        """
        return [
            self.ib.reqMktData(c, genericTickList="100,101", snapshot=False)
            for c in contracts
        ]

    def _pump_until_ready(self, tickers: list) -> int:
        """Pump the event loop until Greeks arrive (or we time out).

        Delayed data is slower than live, and illiquid deep-OTM strikes may never
        populate, so we stop once everything that's going to arrive has — not
        strictly all of them. Returns the count of tickers with modelGreeks.
        """
        prev_ready = -1
        stable = 0
        ready = 0
        for _ in range(30):  # ~15s max
            self.ib.sleep(0.5)
            ready = sum(1 for t in tickers if t.modelGreeks is not None)
            if ready == len(tickers):
                break
            # If the ready count stops climbing for ~2s, assume the rest won't come.
            stable = stable + 1 if ready == prev_ready else 0
            if ready > 0 and stable >= 4:
                break
            prev_ready = ready
        return ready

    def _snapshot_options(self, contracts: list, right: str) -> List[Dict]:
        """Stream LIVE market data for the qualified contracts and build chain rows.

        Live-only: if no Greeks arrive (market closed, or a subscription gap), we
        warn and let the caller skip this stock — we never substitute delayed data.
        """
        tickers = self._request_chain_data(contracts)
        ready = self._pump_until_ready(tickers)

        if ready == 0:
            sym = contracts[0].symbol if contracts else "?"
            print(
                f"[WARN] {sym}: no live OPRA Greeks (market closed or subscription) "
                "— skipping."
            )

        rows = []
        for c, t in zip(contracts, tickers):
            greeks = t.modelGreeks
            iv = _clean(greeks.impliedVol) if greeks else None
            oi = t.putOpenInterest if right == "P" else t.callOpenInterest

            rows.append(
                {
                    "code": c.localSymbol
                    or f"{c.symbol}{c.lastTradeDateOrContractMonth}{right}{int(c.strike * 1000):08d}",
                    "strike_price": float(c.strike),
                    "option_type": "PUT" if right == "P" else "CALL",
                    # IBKR put delta is already negative — matches the MooMoo convention.
                    "delta": _clean(greeks.delta) if greeks else None,
                    "gamma": _clean(greeks.gamma) if greeks else None,
                    "theta": _clean(greeks.theta) if greeks else None,
                    "vega": _clean(greeks.vega) if greeks else None,
                    # MooMoo reports IV as a percentage number (e.g. 33.2); ib_async
                    # returns a decimal (0.332). Scale to match so IVAnalyzer is correct.
                    "implied_volatility": round(iv * 100, 4)
                    if iv is not None
                    else None,
                    "open_interest": _clean(oi),
                    "volume": _clean(t.volume),
                    "bid": _clean(t.bid),
                    "ask": _clean(t.ask),
                    "last_price": _clean(t.last),
                }
            )
            self.ib.cancelMktData(c)

        return rows

    def get_options_chain(
        self,
        ticker: str,
        expiration: str,
        option_type: str = "PUT",
        delta_min: Optional[float] = None,
        delta_max: Optional[float] = None,
        volume_min: Optional[int] = None,
        oi_min: Optional[int] = None,
    ) -> Optional[pd.DataFrame]:
        """Options chain with Greeks/pricing for one expiration via IBKR.

        Mirrors HybridDataFetcher.get_options_chain: same args, same returned
        columns (strike_price, delta, bid, ask, last_price, volume,
        open_interest, implied_volatility, code) and same filter semantics.
        """
        self._ensure_ibkr_connected()

        symbol = strip_moomoo_prefix(ticker)
        secdef = self._get_secdef(symbol)
        if not secdef:
            return pd.DataFrame()

        exp_compact = expiration.replace("-", "")
        if exp_compact not in secdef["expirations"]:
            print(f"Warning: {symbol} has no IBKR expiration {expiration}")
            return pd.DataFrame()

        quote = self.get_stock_quote(symbol)
        spot = quote["price"] if quote else None

        right = "P" if option_type.upper() == "PUT" else "C"

        try:
            # Enumerate the REAL contracts for this expiration in one call. Passing a
            # partial Option (no strike) returns every valid, fully-qualified strike,
            # so we never request a non-existent strike (avoids Error 200 noise and
            # the union-of-all-expirations strike-guessing problem).
            spec = Option(
                symbol,
                exp_compact,
                right=right,
                exchange="SMART",
                currency="USD",
                tradingClass=secdef["trading_class"],
            )
            details = self.ib.reqContractDetails(spec)
            if not details:
                return pd.DataFrame()

            contracts = [d.contract for d in details]
            contracts = self._select_contracts(contracts, spot, option_type)
            if not contracts:
                return pd.DataFrame()

            rows = self._snapshot_options(contracts, right)
            df = pd.DataFrame(rows)
            if df.empty:
                return df

            # Apply the same filters as the MooMoo path (None = skip filter).
            if delta_min is not None:
                df = df[df["delta"].notna() & (df["delta"] >= delta_min)]
            if delta_max is not None:
                df = df[df["delta"].notna() & (df["delta"] <= delta_max)]
            if volume_min is not None:
                df = df[df["volume"].notna() & (df["volume"] >= volume_min)]
            if oi_min is not None:
                df = df[df["open_interest"].notna() & (df["open_interest"] >= oi_min)]

            return df.reset_index(drop=True)

        except Exception as e:
            print(f"Error fetching IBKR options chain for {ticker} @ {expiration}: {e}")
            return None

    def clear_cache(self):
        super().clear_cache()
        self._secdef_cache.clear()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def get_ibkr_data_fetcher(use_mock: bool = False) -> Any:
    """Return an IBKRDataFetcher, or MockDataFetcher for testing.

    Args:
        use_mock: Force the mock fetcher (no live connection).
    """
    if use_mock:
        return MockDataFetcher()

    if not YFINANCE_AVAILABLE:
        print("Warning: yfinance not available, using mock data")
        return MockDataFetcher()

    return IBKRDataFetcher()


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("IBKR DATA FETCHER TEST")
    print("Stock quotes: FMP API (Real-time)")
    print("Options data: IBKR API (ib_async)")
    print("=" * 60 + "\n")

    fetcher = get_ibkr_data_fetcher(use_mock=False)

    # Stock quote (FMP — no IBKR needed)
    print("--- Testing Stock Quote (FMP) ---")
    quote = fetcher.get_stock_quote("AAPL")
    print(f"AAPL: ${quote['price']:.2f}" if quote else "Failed to get AAPL quote")

    # Options (IBKR)
    print("\n--- Testing IBKR Connection (Options) ---")
    if fetcher.connect():
        exps = fetcher.get_option_expirations("AAPL")
        if exps:
            print(f"AAPL expirations: {exps[:5]}...")
            target = exps[min(4, len(exps) - 1)]
            chain = fetcher.get_options_chain("AAPL", target, option_type="PUT")
            if chain is not None and not chain.empty:
                print(f"Got {len(chain)} PUT options for AAPL @ {target}")
                cols = ["strike_price", "delta", "bid", "ask", "implied_volatility"]
                print(chain[cols].head())
            else:
                print("No options chain data returned")
        else:
            print("No expirations returned")
        fetcher.disconnect()
    else:
        print("Could not connect to IB Gateway - options test skipped")
