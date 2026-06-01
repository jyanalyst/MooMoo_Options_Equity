---
name: options-iv-pricing
description: Use when pricing options, computing or interpreting Greeks (delta/gamma/theta/vega), implied volatility, IV Percentile/Rank, or option term structure (contango/backwardation) in this scanner.
---
# Options, IV & Greeks

## IV richness — use IV Percentile, not realized vol
- Compute IV Percentile against the persisted IV history in `iv_history.json` (one ATM-IV observation
  per ticker per day, capped at 252). See `IVAnalyzer.calculate_iv_percentile` / `record_iv_observation`
  in [iv_analyzer.py](../../../iv_analyzer.py).
- IV Percentile = 100 × (#observations < current IV) / (total observations). Robust to single vol spikes
  (preferred over min-max IV Rank).
- Warm-up: until `min_observations` (config `IV_RANK_CONFIG`, default 20) daily points exist, fall back to
  the realized-vol proxy and label it `iv_method = "hv_proxy_provisional"`. Never present the provisional
  value as a true percentile.
- Do NOT compare current implied vol against the min/max of realized (historical) vol — they are different
  quantities (the variance risk premium biases that ratio high). This was the bug fixed on 2026-06-01.

## Premium yield
- Raw yield = premium / strike. Cross-stock ranking uses ANNUALIZED yield = raw × 365/DTE, which assumes
  the put is held to expiry — state that assumption. It is a comparator, not a compounded return.

## Greeks
- Read delta/gamma/theta/vega from MooMoo OPRA, not a local Black-Scholes model. Recalculate at the
  current spot; never reuse Greeks across a price move. The moneyness-only delta fallback in
  screener_wheel.py is a last resort when OPRA delta is 0 — flag it, don't rank on it.

## Term structure
- Contango (back-month IV > front-month IV) favours premium selling; backwardation is unfavourable.
- Validate IV is sane (0 < IV < ~3.0) before using it; reject/flag outliers.
