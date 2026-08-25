# Calibration Evidence — FreqAI LightGBM (ML-001 → ML-006)

> Archived 2026-08-25 because the Data/Bias Auditor flagged the calibration
> numbers as "UNABLE-TO-VERIFY" — they existed only in chat + a code comment.
> This file is the durable record. Reproduce by reading
> `user_data/models/<identifier>/backtesting_predictions/*_prediction.feather`,
> merging with price, and computing corr(pred, actual).

## Method

For each model identifier, load all `backtesting_predictions/*.feather`,
filter `do_predict == 1`, merge price via `merge_asof` on `date`, compute
`actual = close.shift(-N)/close - 1` (N = horizon), then `corr(pred, actual)`
and hit-rate by prediction bucket.

## Results

### 3h target (MultiFactorLightGBM-1Year, ML-001 baseline)
- n = 8,723 confident predictions
- **corr(pred, actual) = −0.0174** (≈ zero, slightly negative)
- mean pred −0.00149 vs mean actual −0.00008 (systematic bearish bias)

| pred bucket | n | actual mean | hit(>0) |
|---|---|---|---|
| < 0 | 4,985 | +0.0000 | 49.3% |
| 0 → 0.3% | 1,407 | +0.0001 | 51.7% |
| 0.3% → 0.6% | 1,108 | −0.0005 | 49.2% |
| 0.6% → 1.0% | 855 | −0.0003 | 49.1% |
| > 1.0% (entry threshold) | 367 | −0.0006 | 51.8% |

**No monotonic relationship. Higher predictions do NOT produce higher actual returns.**

### 12h target (MultiFactorLightGBM-12H, ML-006a)
- n = 8,724 · **corr = −0.0196**

### 24h target (MultiFactorLightGBM-24H, ML-006b)
- n = 8,712 · **corr = +0.0103** (marginally positive but statistically indistinguishable from zero)

### Conclusion
**The LightGBM model has no predictive edge for BTC return at 3h/12h/24h with these features.** Correlation ≈ 0 at every horizon. The 64–68% backtest win rates were exit-structure artifacts (ROI banking small wins while stoploss absorbed large losses), NOT model skill.

---

## Feature importance (LGBMRegressor, 38 features)

Top of the list (dominant): `roc-14`, `roc-20`, `rsi-200`, `volume-mean-*` on 1h — all **technical**, importance 330–481.

Bottom (noise): every **macro** feature. `fear_and_greed` ranked **37/38** (13.0 on 1h, 5.0 on 4h); `long_short_ratio` 12–17; `spy` 8–16; `open_interest` 15–21.

**The "multi-factor" model is functionally technical-only** — it learned nothing from macro data.

> ⚠️ Auditor caveat: "macro zero importance" is *partly confounded* by the
> constant-fill of missing early macro data (coverage gap, not informativeness).
> This weakens the "macro is useless" claim specifically — see
> `tasks/REVIEW_DATA_BIAS_AUDIT.md` for the nuance. The directional-ML "no edge"
> conclusion is unaffected.
