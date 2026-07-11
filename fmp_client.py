"""
FMPClient — the ONLY FMP HTTP path in this project.

Every FMP request goes through FMPClient.get(): one shared requests.Session with
retry/backoff, a thread-safe 1 req/s throttle (FMP Starter plan limit), and a
TTL file cache under ./cache so repeat scans cost zero quota. Errors are NEVER
cached (a quota/network blip must not stay sticky for the TTL window).

Do not add raw requests.get() calls to FMP anywhere else — extend this client.
"""

import hashlib
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import FMP_API_KEY


class FMPClient:
    BASE = "https://financialmodelingprep.com/stable"

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = "./cache",
        min_interval_s: float = 1.0,
    ):
        self.api_key = api_key or FMP_API_KEY
        self.cache_dir = cache_dir
        self.min_interval_s = min_interval_s
        self.request_count = 0  # live (non-cached) HTTP calls this process

        self._lock = threading.Lock()
        self._last_request_time = 0.0

        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

        os.makedirs(self.cache_dir, exist_ok=True)

    # ------------------------------------------------------------------ core
    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        *,
        ttl_hours: float = 24.0,
    ) -> Optional[Any]:
        """
        File-cached GET of /stable/{endpoint}.

        Args:
            endpoint: path after /stable/, e.g. "quote", "earnings"
            params: query params (apikey is added automatically)
            ttl_hours: cache freshness window; 0 bypasses the cache entirely

        Returns:
            Parsed JSON (list or dict), or None on any error. Errors are never
            written to the cache.
        """
        params = dict(params or {})
        cache_path = self._cache_path(endpoint, params)

        if ttl_hours > 0:
            cached = self._read_cache(cache_path, ttl_hours)
            if cached is not None:
                return cached

        data = self._fetch(endpoint, params)
        if data is not None and ttl_hours > 0:
            self._write_cache(cache_path, data)
        return data

    def _fetch(self, endpoint: str, params: dict) -> Optional[Any]:
        # Thread-safe 1 req/s throttle (FMP Starter: 1 request/second)
        with self._lock:
            wait = self.min_interval_s - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)
            self._last_request_time = time.monotonic()

        try:
            response = self._session.get(
                f"{self.BASE}/{endpoint}",
                params={**params, "apikey": self.api_key},
                timeout=30,
            )
            self.request_count += 1
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"  [WARN] FMP HTTP {e.response.status_code} on /{endpoint}")
            return None
        except Exception as e:
            print(
                f"  [WARN] FMP request failed on /{endpoint}: {type(e).__name__}: {e}"
            )
            return None

    # ----------------------------------------------------------------- cache
    def _cache_path(self, endpoint: str, params: dict) -> str:
        key_params = {k: v for k, v in sorted(params.items()) if k != "apikey"}
        digest = hashlib.md5(
            f"{endpoint}?{json.dumps(key_params, sort_keys=True)}".encode()
        ).hexdigest()
        return os.path.join(self.cache_dir, f"fmp_{digest}.json")

    def _read_cache(self, path: str, ttl_hours: float) -> Optional[Any]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
            age_hours = (datetime.now() - fetched_at).total_seconds() / 3600.0
            if age_hours < ttl_hours:
                return entry["data"]
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass
        return None

    def _write_cache(self, path: str, data: Any) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"fetched_at": datetime.now().isoformat(), "data": data}, f)
        except OSError as e:
            print(f"  [WARN] Could not write FMP cache {path}: {e}")

    # --------------------------------------------------- typed endpoint sugar
    def quote(self, symbol: str, ttl_hours: float = 0.25) -> Optional[list]:
        """Real-time quote; 15-min cache by default."""
        return self.get("quote", {"symbol": symbol}, ttl_hours=ttl_hours)

    def earnings(self, symbol: str, ttl_hours: float = 12.0) -> Optional[list]:
        """Per-symbol earnings history + estimates; 12h cache."""
        return self.get("earnings", {"symbol": symbol}, ttl_hours=ttl_hours)

    def ratios_ttm(self, symbol: str, ttl_hours: float = 24.0) -> Optional[list]:
        """TTM ratios (margins etc.); 24h cache."""
        return self.get("ratios-ttm", {"symbol": symbol}, ttl_hours=ttl_hours)

    def company_screener(self, ttl_hours: float = 24.0, **filters) -> Optional[list]:
        """Company screener; 24h cache. Pass FMP filter params as kwargs."""
        return self.get("company-screener", filters, ttl_hours=ttl_hours)


_client: Optional[FMPClient] = None
_client_lock = threading.Lock()


def get_client() -> FMPClient:
    """Module-level singleton — share one throttle/session across the process."""
    global _client
    with _client_lock:
        if _client is None:
            _client = FMPClient()
        return _client
