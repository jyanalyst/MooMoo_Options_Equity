---
globs: ['**/data_fetcher.py', '**/fmp_client.py', '**/earnings_checker.py']
---
# Data Fetching Rules

## FMP API (quotes, fundamentals, earnings, VIX)
- `fmp_client.get_client()` is the ONLY FMP HTTP path — session + retry/backoff, thread-safe
  1 req/s throttle (Starter plan: 250 calls/day), TTL file cache under `cache/`. NEVER add a raw
  `requests.get()` to FMP anywhere else; extend FMPClient instead.
- Errors are never cached (a quota/network blip must not stay sticky for the TTL window).
  Valid-but-empty responses ARE cached (a name with no data is a fact, not an error).
- `ttl_hours=0` bypasses the cache — use for readings that must be live (e.g. VIX regime).
- Some FMP fields return None (especially non-US or thinly-covered names) — handle None explicitly,
  never assume a numeric value. In a DataFrame, None becomes NaN — `pd.isna()` it, comparisons lie.

## MooMoo OpenD (options chains + Greeks)
- Connects to 127.0.0.1:11111; OpenD must be running and logged in. A failed connect is a warning, not
  fatal — degrade gracefully (no options data) rather than crashing.
- Tickers use the `US.` prefix; convert with `format_moomoo_symbol()` / `strip_moomoo_prefix()` in universe.py.
- ~3s between chain calls; expirations are cached class-level for 24h. Don't add redundant chain fetches.

## Earnings (earnings_checker.py)
- Design is FAIL-CLOSED (allow_unverified=False default): when FMP earnings data is missing the
  stock is REJECTED. Never let an UNVERIFIED name look like a confirmed SAFE one, and never flip
  the default to fail-open. earnings_monitor.py consumes EarningsChecker — one fetch, two
  presentation layers; keep it that way.

## Mock mode
- `python main.py --mock wheel` must stay FULLY OFFLINE: zero network calls, zero repo-root writes
  (stub earnings checker + temp IV files are injected in main.run_wheel_scan).

## Secrets
- FMP key: `FMP_API_KEY` env var via gitignored `.env`; config.py carries a legacy fallback literal.
  Do not log it, print it, or copy it into new files.
