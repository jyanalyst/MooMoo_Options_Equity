---
name: statistical-validation
description: Use when validating statistical assumptions (normality, stationarity, heteroskedasticity), checking a calculation for look-ahead bias, or sanity-checking backtest/strategy results in this quant project.
---
# Statistical Validation

## Before trusting a statistical method
- Returns: check normality (Shapiro-Wilk) and report skew/kurtosis; don't assume Gaussian for tails.
- Time series: check stationarity (ADF) before modelling levels; difference if non-stationary.
- Variance/vol: use Bessel's correction (ddof=1, pandas default). Annualize vol with √252.
- Robust stats over raw means when outliers are present (trimmed mean / winsorize).

## Look-ahead bias (most important failure mode)
- A signal at bar t may use ONLY data available at t's close. No future bars, no full-sample fits.
- Sort by date explicitly before any `.iloc[-1]`/rolling op; never assume input is date-ordered.
- Rolling windows for statistical tests should be non-overlapping when independence is required.

## Backtest sanity ranges (flag anything outside)
- Sharpe roughly -1 to 3 for these strategies; max drawdown < ~50%; win rate 10–90%
  (100% almost always means a look-ahead leak).
- Reconcile against a hand calculation on a small sample period before reporting.

## Edge cases to always test
- Empty input, single data point, all-NaN, extreme values. Statistical functions must degrade
  gracefully (return None + log) rather than emit a plausible-but-wrong number.
