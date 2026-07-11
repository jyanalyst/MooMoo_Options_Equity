"""
Tests for FMPClient — the single FMP HTTP path.

Covers: TTL cache honored, ttl=0 bypass, errors returned as None and never
cached, 1 req/s throttle spacing, and the module singleton. No network: the
session is replaced with fakes.
"""

import json
import time

import pytest

import fmp_client
from fmp_client import FMPClient, get_client


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return self._payload


class FakeSession:
    """Counts calls; returns a queued payload or raises."""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


@pytest.fixture
def client(tmp_path):
    c = FMPClient(api_key="test-key", cache_dir=str(tmp_path), min_interval_s=0.0)
    c._session = FakeSession(payload=[{"symbol": "AAPL", "price": 190.0}])
    return c


def test_fresh_cache_prevents_http(client, tmp_path):
    first = client.get("quote", {"symbol": "AAPL"}, ttl_hours=1)
    assert first[0]["price"] == 190.0
    assert client._session.calls == 1

    # Second call within TTL: served from file cache, no HTTP
    second = client.get("quote", {"symbol": "AAPL"}, ttl_hours=1)
    assert second == first
    assert client._session.calls == 1


def test_ttl_zero_bypasses_cache(client):
    client.get("quote", {"symbol": "AAPL"}, ttl_hours=1)
    client.get("quote", {"symbol": "AAPL"}, ttl_hours=0)
    assert client._session.calls == 2


def test_expired_cache_refetches(client, tmp_path):
    client.get("quote", {"symbol": "AAPL"}, ttl_hours=1)
    # Age the cache entry beyond the TTL by rewriting fetched_at
    cache_file = next(tmp_path.glob("fmp_*.json"))
    entry = json.loads(cache_file.read_text())
    entry["fetched_at"] = "2020-01-01T00:00:00"
    cache_file.write_text(json.dumps(entry))

    client.get("quote", {"symbol": "AAPL"}, ttl_hours=1)
    assert client._session.calls == 2


def test_errors_return_none_and_are_not_cached(tmp_path):
    import requests

    c = FMPClient(api_key="k", cache_dir=str(tmp_path), min_interval_s=0.0)
    c._session = FakeSession(error=requests.exceptions.ConnectionError("down"))

    assert c.get("earnings", {"symbol": "AAPL"}, ttl_hours=12) is None
    assert list(tmp_path.glob("fmp_*.json")) == []  # error never cached

    # Feed recovers -> next call fetches live and succeeds
    c._session = FakeSession(payload=[{"date": "2026-08-01"}])
    assert c.get("earnings", {"symbol": "AAPL"}, ttl_hours=12) is not None


def test_rate_limit_spacing(tmp_path):
    c = FMPClient(api_key="k", cache_dir=str(tmp_path), min_interval_s=0.2)
    c._session = FakeSession(payload=[])

    start = time.monotonic()
    c.get("quote", {"symbol": "A"}, ttl_hours=0)
    c.get("quote", {"symbol": "B"}, ttl_hours=0)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2  # second live call waited for the throttle window


def test_cache_key_ignores_apikey_but_not_params(client):
    path_a = client._cache_path("quote", {"symbol": "AAPL", "apikey": "x"})
    path_a2 = client._cache_path("quote", {"symbol": "AAPL", "apikey": "y"})
    path_b = client._cache_path("quote", {"symbol": "MSFT"})
    assert path_a == path_a2
    assert path_a != path_b


def test_singleton_identity():
    fmp_client._client = None  # reset for a clean check
    assert get_client() is get_client()
    fmp_client._client = None
