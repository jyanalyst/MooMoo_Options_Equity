---
globs: ['**/data_fetcher.py', '**/fmp_data_fetcher.py', '**/earnings_checker.py']
---
# Data Fetching Rules

## FMP API (quotes, fundamentals, earnings, VIX)
- Starter plan = 250 calls/day, 1 request/second (`_rate_limit` in fmp_data_fetcher.py). Stay under it.
- Cache every response with a TTL; never re-fetch within the TTL window. Prefer one bulk call over a
  per-ticker loop where an endpoint supports it.
- Some FMP fields return None (especially non-US or thinly-covered names) — handle None explicitly,
  never assume a numeric value.

## MooMoo OpenD (options chains + Greeks)
- Connects to 127.0.0.1:11111; OpenD must be running and logged in. A failed connect is a warning, not
  fatal — degrade gracefully (no options data) rather than crashing.
- Tickers use the `US.` prefix; convert with `format_moomoo_symbol()` / `strip_moomoo_prefix()` in universe.py.
- ~3s between chain calls; expirations are cached class-level for 24h. Don't add redundant chain fetches.

## Earnings (earnings_checker.py)
- Design is fail-open: when FMP earnings data is missing it returns UNVERIFIED and the scan PROCEEDS.
  Surface that clearly; never let an UNVERIFIED name look like a confirmed SAFE one.

## Secrets
- The FMP key is currently hardcoded in config.py — do not log it, print it, or copy it into new files.
