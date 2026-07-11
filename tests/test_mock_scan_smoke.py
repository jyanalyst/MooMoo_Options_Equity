"""
End-to-end offline smoke test: MockDataFetcher -> WheelScreener -> candidates.

This is the automated gate that replaces a live MooMoo scan in CI: zero network
calls (stub earnings checker, mock chain/quotes/history) and zero repo-root
writes (IV files redirected to tmp_path).
"""

import pandas as pd
import pytest

from data_fetcher import MockDataFetcher
from iv_analyzer import IVAnalyzer
from main import _OfflineEarningsChecker
from screener_wheel import WheelScreener


@pytest.fixture
def screener(tmp_path):
    fetcher = MockDataFetcher()
    s = WheelScreener(
        fetcher,
        max_capital=8900,
        earnings_checker=_OfflineEarningsChecker(),
        iv_analyzer=IVAnalyzer(
            fetcher,
            cache_file=str(tmp_path / "iv_cache.json"),
            history_file=str(tmp_path / "iv_history.json"),
        ),
    )
    s.universe = ["INTC", "AMD", "PLTR", "SOFI", "HOOD"]
    return s


def test_mock_scan_produces_candidates(screener):
    candidates = screener.screen_candidates(verbose=False)
    assert len(candidates) >= 1

    for c in candidates:
        best = c["best_option"]
        # Survivors of the hard filters only
        assert best["hard_reject"] is None
        assert best["open_interest"] >= 100
        assert best["spread_pct"] <= 10.0
        assert best["return_pct"] >= 0.5
        assert best["bid"] > 0 and best["ask"] > 0
        # IV is a sane percentage (the 100x bug would push this to ~3000)
        assert 10.0 <= best["iv"] <= 80.0
        # Delta stayed inside the requested band (mock honors the kwargs)
        assert 0.20 <= best["delta"] <= 0.30


def test_mock_scan_writes_nothing_to_repo_root(screener, tmp_path):
    screener.screen_candidates(verbose=False)
    # IV observations landed in the redirected files, not ./iv_history.json
    assert screener.iv_analyzer.history_file.startswith(str(tmp_path))


def test_mock_chain_respects_delta_band():
    chain = MockDataFetcher().get_options_chain(
        "INTC", "2099-01-15", option_type="PUT", delta_min=-0.30, delta_max=-0.20
    )
    assert isinstance(chain, pd.DataFrame)
    assert not chain.empty
    assert ((chain["delta"] >= -0.30) & (chain["delta"] <= -0.20)).all()
    # Percentage IV convention and production-tight spreads
    assert (
        (chain["implied_volatility"] > 10) & (chain["implied_volatility"] < 80)
    ).all()
    spread_pct = (chain["ask"] - chain["bid"]) / ((chain["ask"] + chain["bid"]) / 2)
    assert (spread_pct <= 0.10).all()
