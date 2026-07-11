"""
Unit and property tests for the two quant-correctness fixes:

1. Annualized premium yield in ``WheelScreener._analyze_option``.
2. Real IV-history persistence and IV Percentile in ``IVAnalyzer``.

Statistical properties verified:
- IV Percentile is always in [0, 100].
- annualized_return_pct >= return_pct for any 0 < DTE < 365 (and equal at DTE == 365).

These tests use only pandas/numpy (no external data, no network). The IV-history and
cache files are redirected to a pytest ``tmp_path`` so the repo working tree is untouched.
"""

from datetime import datetime

import pandas as pd
import pytest

from iv_analyzer import IVAnalyzer
from screener_wheel import WheelScreener


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
class FakeFetcher:
    """Minimal data_fetcher stub for driving IVAnalyzer end-to-end offline."""

    def __init__(self, atm_iv_pct: float = 35.0):
        self.atm_iv_pct = atm_iv_pct

    def get_stock_quote(self, ticker):
        return {"price": 100.0}

    def get_options_chain(self, ticker, expiration, option_type="PUT", **kwargs):
        return pd.DataFrame(
            {
                "strike_price": [95.0, 100.0, 105.0],
                "implied_volatility": [
                    self.atm_iv_pct - 1,
                    self.atm_iv_pct,
                    self.atm_iv_pct + 1,
                ],
            }
        )

    def get_historical_data(self, ticker, days=252):
        # 60 rows of mildly oscillating closes -> finite, positive HV.
        closes = [100.0 + (i % 5) for i in range(60)]
        return pd.DataFrame({"close": closes})

    def get_option_expirations(self, ticker):
        return []  # skip term-structure branch


@pytest.fixture
def analyzer(tmp_path):
    a = IVAnalyzer(data_fetcher=FakeFetcher())
    a.history_file = str(tmp_path / "iv_history.json")
    a.cache_file = str(tmp_path / "iv_cache.json")
    a.iv_history = {}
    a.cache = {}
    return a


def _option_series(strike=100.0, bid=2.0, ask=2.1, delta=-0.25):
    return pd.Series(
        {
            "strike_price": strike,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "last_price": bid,
            "volume": 100,
            "open_interest": 500,
            # Percentage, matching the live-chain convention (35.0 == 35% vol)
            "implied_volatility": 35.0,
            "code": "TEST",
        }
    )


@pytest.fixture
def screener():
    # data_fetcher is unused by _analyze_option; None is sufficient.
    return WheelScreener(data_fetcher=None)


# --------------------------------------------------------------------------- #
# Fix 1: annualized return
# --------------------------------------------------------------------------- #
def test_annualized_return_scales_with_dte(screener):
    opt = _option_series(strike=100.0, bid=2.0)
    a30 = screener._analyze_option(opt, stock_price=100.0, dte=30)
    a45 = screener._analyze_option(opt, stock_price=100.0, dte=45)

    # Raw yield identical; annualized must rank the shorter-dated contract higher.
    assert a30["return_pct"] == a45["return_pct"] == 2.0
    assert a30["annualized_return_pct"] == round(2.0 * 365 / 30, 2)
    assert a30["annualized_return_pct"] > a45["annualized_return_pct"]


def test_annualized_equals_raw_at_one_year(screener):
    opt = _option_series(strike=50.0, bid=1.0)  # raw return 2.0%
    res = screener._analyze_option(opt, stock_price=50.0, dte=365)
    assert res["annualized_return_pct"] == res["return_pct"]


def test_annualized_zero_dte_safe(screener):
    res = screener._analyze_option(_option_series(), stock_price=100.0, dte=0)
    assert res["annualized_return_pct"] == 0


@pytest.mark.parametrize("dte", [1, 7, 15, 30, 45, 90, 200, 364, 365])
def test_annualized_ge_raw_property(screener, dte):
    res = screener._analyze_option(
        _option_series(strike=100.0, bid=3.0), stock_price=100.0, dte=dte
    )
    assert res["annualized_return_pct"] >= res["return_pct"] >= 0


# --------------------------------------------------------------------------- #
# Fix 2: IV Percentile
# --------------------------------------------------------------------------- #
def test_iv_percentile_known_values(analyzer):
    analyzer.iv_history["XYZ"] = [
        {"date": f"2025-01-0{i + 1}", "iv": v}
        for i, v in enumerate([0.10, 0.20, 0.30, 0.40, 0.50])
    ]
    # 3 of 5 observations (0.10, 0.20, 0.30) are strictly below 0.35.
    assert analyzer.calculate_iv_percentile("XYZ", 0.35) == 60.0
    assert analyzer.calculate_iv_percentile("XYZ", 0.05) == 0.0  # below all
    assert analyzer.calculate_iv_percentile("XYZ", 0.99) == 100.0  # above all


def test_iv_percentile_empty_history_returns_none(analyzer):
    assert analyzer.calculate_iv_percentile("NONE", 0.3) is None


def test_iv_rank_proxy_clamped_to_100(analyzer):
    # Seed a valid HV range in cache; current IV far above the historical max would
    # otherwise yield >100. Must clamp to [0, 100].
    analyzer.cache["XYZ"] = {
        "iv_low": 0.20,
        "iv_high": 0.40,
        "cached_at": datetime.now().isoformat(),
    }
    assert analyzer.calculate_iv_rank("XYZ", 0.90) == 100.0  # would be 350 unclamped
    assert analyzer.calculate_iv_rank("XYZ", 0.05) == 0.0  # would be -75 unclamped


# --------------------------------------------------------------------------- #
# Provisional IV is excluded from scoring; earnings default is fail-closed
# --------------------------------------------------------------------------- #
def test_provisional_iv_contributes_zero_score(screener):
    base = {"iv_rank": 95, "term_structure": "NEUTRAL"}
    provisional = screener._calculate_quality_score(
        {**base, "iv_method": "hv_proxy_provisional"}
    )
    real = screener._calculate_quality_score({**base, "iv_method": "iv_percentile"})
    # Only difference is the IV contribution: 30 pts for a real >=50 reading, 0 when provisional.
    assert real - provisional == 30


def test_earnings_default_is_fail_closed():
    from config import WHEEL_CONFIG

    assert WHEEL_CONFIG["allow_unverified_earnings"] is False


# --------------------------------------------------------------------------- #
# VIX regime (v3.1): correct labels/bands, consistent with trade_journal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "vix,expected",
    [
        (10.0, "STOP"),
        (13.99, "STOP"),
        (14.0, "CAUTIOUS"),
        (15.32, "CAUTIOUS"),  # today's reading the analysis flagged
        (15.91, "CAUTIOUS"),  # the stale-log value mislabeled NORMAL
        (17.99, "CAUTIOUS"),
        (18.0, "NORMAL"),
        (25.0, "NORMAL"),
        (25.01, "AGGRESSIVE"),
        (40.0, "AGGRESSIVE"),
    ],
)
def test_vix_regime_v31(vix, expected):
    import vix_monitor

    assert vix_monitor.get_regime(vix) == expected


def test_vix_monitor_matches_trade_journal():
    import vix_monitor
    import trade_journal

    for vix in [9.5, 14.0, 15.32, 18.0, 22.5, 25.0, 30.0]:
        assert vix_monitor.get_regime(vix) == trade_journal.classify_vix_regime(vix)


# --------------------------------------------------------------------------- #
# Earnings monitor fails closed when FMP returns no date
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Post-earnings IV-crush guard
# --------------------------------------------------------------------------- #
def test_crush_guard_rejects_recent_earnings_when_iv_unconfirmed(screener):
    from datetime import timedelta

    recent = datetime.now() - timedelta(days=6)  # PDD-like: 6 days post-earnings
    # Provisional IV (warm-up) -> cannot confirm elevated -> crush risk -> reject.
    assert (
        screener._is_post_earnings_crush(recent, "hv_proxy_provisional", None) is True
    )
    # Even a high provisional reading must not rescue it (not a reliable method).
    assert (
        screener._is_post_earnings_crush(recent, "hv_proxy_provisional", 86.7) is True
    )


def test_crush_guard_allows_recent_earnings_with_confirmed_high_iv(screener):
    from datetime import timedelta

    recent = datetime.now() - timedelta(days=6)
    # Guide rule: post-earnings entry OK if IV Rank confirmed elevated (>40).
    assert screener._is_post_earnings_crush(recent, "iv_percentile", 55.0) is False
    # Confirmed but low IV -> still a crush -> reject.
    assert screener._is_post_earnings_crush(recent, "iv_percentile", 25.0) is True


def test_crush_guard_ignores_old_or_missing_earnings(screener):
    from datetime import timedelta

    old = datetime.now() - timedelta(days=60)
    assert screener._is_post_earnings_crush(old, "hv_proxy_provisional", None) is False
    assert screener._is_post_earnings_crush(None, "hv_proxy_provisional", None) is False


def test_earnings_monitor_fails_closed(monkeypatch):
    import earnings_monitor

    # Simulate a dark FMP feed: every per-ticker fetch returns None.
    monkeypatch.setattr(earnings_monitor, "fetch_earnings_for_ticker", lambda t: None)
    rows = earnings_monitor.categorize_earnings(["V", "KO"])
    assert rows, "expected rows for the given universe"
    assert all(r["status"] == "UNVERIFIED" for r in rows)  # never fabricated SAFE
    assert all(r["earnings_date"] == "" for r in rows)


@pytest.mark.parametrize("current", [0.0, 0.05, 0.25, 0.35, 0.6, 1.5])
def test_iv_percentile_bounded(analyzer, current):
    analyzer.iv_history["XYZ"] = [
        {"date": f"2025-02-{i + 1:02d}", "iv": 0.1 + 0.05 * i} for i in range(10)
    ]
    pct = analyzer.calculate_iv_percentile("XYZ", current)
    assert 0.0 <= pct <= 100.0


# --------------------------------------------------------------------------- #
# Fix 2: history recording (overwrite, cap, validation)
# --------------------------------------------------------------------------- #
def test_record_overwrites_same_day(analyzer):
    analyzer.record_iv_observation("AAA", 0.30)
    analyzer.record_iv_observation("AAA", 0.40)
    series = analyzer.iv_history["AAA"]
    assert len(series) == 1  # same calendar day -> overwrite, not append
    assert series[-1]["iv"] == 0.40


def test_record_caps_to_lookback(analyzer):
    analyzer.lookback_days = 3
    analyzer.iv_history["AAA"] = [
        {"date": f"2025-01-0{i + 1}", "iv": 0.2} for i in range(3)
    ]
    analyzer.record_iv_observation("AAA", 0.31)  # today, distinct date
    assert len(analyzer.iv_history["AAA"]) == 3
    assert analyzer.iv_history["AAA"][-1]["iv"] == 0.31


@pytest.mark.parametrize("bad", [None, 0.0, -0.2, float("nan")])
def test_record_ignores_invalid_iv(analyzer, bad):
    analyzer.record_iv_observation("AAA", bad)
    assert "AAA" not in analyzer.iv_history


# --------------------------------------------------------------------------- #
# Fix 2: warm-up fallback labeling via get_full_iv_analysis
# --------------------------------------------------------------------------- #
def test_method_is_provisional_before_warmup(analyzer):
    res = analyzer.get_full_iv_analysis("AAA", "2025-03-21")
    assert res["iv_method"] == "hv_proxy_provisional"
    # During warm-up IV is UNKNOWN - the misleading HV proxy is no longer emitted as a rank.
    assert res["iv_rank"] is None


def test_method_is_percentile_after_warmup(analyzer):
    analyzer.min_observations = 20
    analyzer.iv_history["AAA"] = [
        {"date": f"2024-12-{i + 1:02d}", "iv": 0.20 + 0.005 * i} for i in range(25)
    ]
    res = analyzer.get_full_iv_analysis("AAA", "2025-03-21")
    assert res["iv_method"] == "iv_percentile"
    assert 0.0 <= res["iv_rank"] <= 100.0


# --------------------------------------------------------------------------- #
# Optional Hypothesis property tests (skipped if hypothesis isn't installed)
# --------------------------------------------------------------------------- #
def test_hypothesis_properties(analyzer, screener):
    hyp = pytest.importorskip("hypothesis")
    from hypothesis import given, strategies as st

    @given(
        ivs=st.lists(st.floats(min_value=0.01, max_value=3.0), min_size=1, max_size=50),
        current=st.floats(min_value=0.0, max_value=5.0),
    )
    def _percentile_bounded(ivs, current):
        analyzer.iv_history["H"] = [
            {"date": f"d{i}", "iv": v} for i, v in enumerate(ivs)
        ]
        pct = analyzer.calculate_iv_percentile("H", current)
        assert 0.0 <= pct <= 100.0

    @given(
        bid=st.floats(min_value=0.01, max_value=50.0),
        strike=st.floats(min_value=5.0, max_value=500.0),
        dte=st.integers(min_value=1, max_value=364),
    )
    def _annualized_ge_raw(bid, strike, dte):
        opt = _option_series(strike=strike, bid=bid, ask=bid * 1.05)
        res = screener._analyze_option(opt, stock_price=strike, dte=dte)
        assert res["annualized_return_pct"] >= res["return_pct"] >= 0

    _percentile_bounded()
    _annualized_ge_raw()
