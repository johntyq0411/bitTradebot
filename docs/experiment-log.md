# Experiment Log — Modest-Bohr V2

**Purpose:** Track every strategy experiment with enough detail to reproduce and compare results. Every backtest, every parameter set, every observation.

**Format:** Each entry gets a unique ID, date, strategy file, config, data range, parameters, results, observations, and artifact paths.

---

## V2-001 — Initial Data Verification

**Date:** 2026-08-24  
**Strategy:** (data check only)  
**Config:** config_baseline.json  
**Data:** BTC/USDT 1h feather file  
**Purpose:** Verify 2-year data completeness before designing strategy  

**Results:**
- Feather file: `/freqtrade/user_data/data/binance/BTC_USDT-1h.feather`
- 17,534 candles, Aug 24 2024 00:00 → Aug 24 2026 13:00
- ~2.0 years of data ✅
- No gaps detected

**Observations:** Data is complete and clean. Ready for strategy development.

**Artifact:** N/A (data verification only)

---

## V2-002 — Regime Classifier Initial Run

**Date:** 2026-08-24  
**Strategy:** `user_data/scripts/regime_decompose.py`  
**Config:** N/A  
**Data:** BTC/USDT 1h, full 2-year period  

**Results:**
- Regime segments identified across 2-year period
- Bull: intermittent periods totaling ~190 days (2025)
- Bear: Nov 17 2025 → Aug 19 2026 (~275 days)
- Sideways: Aug 24 2024 → Mar 12 2025 (~201 days) + shorter segments
- Regime CSV saved to `/freqtrade/user_data/data/external/regime_classification.csv`

**Observations:**
- 200-period SMA on 1h is ~8 days — may be too short for macro trend detection
- Consider using 4h informative pair with 50-period SMA for ~10-day equivalent
- Regime flips within short periods (1-2 days) — whipsaw possible; need smoothing or minimum regime duration filter

**Artifact:** `/freqtrade/user_data/data/external/regime_classification.csv`

---

## V2-003 — Baseline Trend Strategy (EMA20/50) — Reference Only

**Date:** 2026-08-24  
**Strategy:** `BtcEmaCrossoverStrategy.py`  
**Config:** config_baseline.json  
**Data:** BTC/USDT 1h, full 2-year period  

**Results:**
- 158 trades, -20.38% total P&L, Profit Factor 0.81, Sharpe -0.37
- Lost money in ALL three regimes:
  - Bull (Apr-Oct 2025): 41 trades, -7.09%
  - Bear (Nov 2025-Aug 2026): 60 trades, -4.49%
  - Sideways (Aug 2024-Mar 2025): 38 trades, -7.57%
- Max drawdown: 32.55%
- Verdict: EMA20/50 crossover has NO edge. Drop as baseline.

**Observations:** Simple crossover strategies do not work on BTC 1h. Must add confirmations, regime filtering, and better exit logic.

**Artifact:** `user_data/backtest_results/PHASE0b-EMA-2YR-NOFREQUAI.json` (exported)

---

## V2-004 — ML Baseline (FreqAI LightGBM) — Reference Only

**Date:** 2026-08-24  
**Strategy:** `FreqaiMultiFactorBtcStrategy.py`  
**Config:** config.json + config_freqai.json  
**Data:** BTC/USDT 1h + 4h, full 2-year period  

**Results:**
- 14 trades, +14.94% P&L, 92.9% win rate, max drawdown 5.14%
- Only traded during bear regime (Apr-Aug 2026)
- No trades during bull or sideways
- 4h data only available from Feb 2026 — limits ML for earlier period

**Observations:**
- Promising but statistically inconclusive (14 trades)
- Did not trade during bull run — unclear if correct (no edge) or missed opportunity
- 4h data gap for early period blocks proper walk-forward on ML

**Artifact:** `user_data/backtest_results/PHASE0b-FreqAI-ML-2YR-Fresh.json` (exported)

---

## Future Experiments

Format for new entries:

```
## V2-NNN — [Strategy Name]

**Date:** YYYY-MM-DD
**Strategy:** [filename]
**Config:** [config file]
**Data:** [timeframe(s), date range]
**Parameters:** [key params]
**Results:** [metrics]
**Observations:** [notes]
**Artifact:** [path to export]
```

---

*Last updated: 2026-08-24*
