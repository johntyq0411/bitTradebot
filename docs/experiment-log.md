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

## V2-005 — Trend-Following V2 Initial Backtest

**Date:** 2026-08-24  
**Strategy:** `BtcTrendFollowingV2Strategy.py` (V2.0)  
**Config:** config_baseline.json  
**Data:** BTC/USDT 1h, Aug 2024 – Aug 2026 (full 2-year)  
**Timerange:** 2024-09-03 → 2026-08-22 (startup excluded)  

**Parameters:**
- Timeframe: 1h
- Regime: BULL only (SMA200 slope > 0, price > SMA200, ADX > 20)
- Entry: Trend signal score >= 4/6, regime confirmed >= 10 candles
- Exit: Structural (close below SMA50), ATR trailing (1.5× ATR), time stop (48 candles at loss)
- No fixed ROI target
- Max open trades: 1
- Stoploss: -0.99 (emergency only)

**Results:**
| Metric | Value |
|---|---|
| Trades | 66 |
| Total P/L | **+12.23 USDT (+1.22%)** |
| Win rate | 39.4% (26 wins, 40 losses, 0 draws) |
| Avg trade duration | 1d 20:58 |
| Avg winner duration | 2d 16:48 |
| Avg loser duration | 1d 08:04 |
| Max consecutive wins | 5 |
| Max consecutive losses | 6 |
| **Max drawdown** | **28.02% (349 USDT)** ⚠️ EXCEEDS 20% limit |
| Sharpe (daily wallet) | 0.13 ⚠️ Very low |
| Sortino | 0.11 |
| Calmar | 0.12 |
| Min balance | 891.62 USDT |
| Max balance | 1279.26 USDT |
| Drawdown duration | 599 days (out of ~700 days backtested) |
| Days win/draw/lose | 25 / 644 / 38 |

**Observations:**
- **FAILED.** Does not meet any success criteria:
  1. Only 1.22% profit over 2 years — barely above noise, likely below costs
  2. 28% drawdown — exceeds 20% acceptable limit
  3. 39.4% win rate — losing trades outnumber wins 1.5:1
  4. Sharpe 0.13 — essentially random performance
  5. Drawdown lasted 599 days — strategy was underwater almost the entire period
- 66 trades over 2 years = ~3 trades/month — reasonable frequency but poor quality
- The strategy enters too often (any marginal trend signal triggers entry) but exits too slowly (structural exit only triggers on SMA50 cross, which lags significantly)
- ATR trailing stop (1.5×) is too tight — gets stopped out by normal price fluctuation before trend develops
- Bull regime filter works (only trades in bull) but the bull periods themselves don't produce reliable trend signals

**Diagnosis — Why it failed:**
1. **Entry too loose:** Trend signal score >= 4/6 is too easy to achieve. Many false entries during weak trends.
2. **Exit too slow:** Structural exit (SMA50 cross) lags significantly. By the time price crosses below SMA50, most of the drawdown has already happened.
3. **Trailing stop too tight:** 1.5× ATR gets hit by normal volatility before the trend has room to develop.
4. **No profit target:** Letting winners run is good in theory, but without a take-profit mechanism, winners get given back.

**What to try next (V2.1):**
- Tighten entry: require trend signal score >= 5/6, or add volume confirmation requirement
- Faster structural exit: use SMA20 or EMA20 instead of SMA50 for exit trigger
- Wider trailing stop: 2.5-3× ATR instead of 1.5×, or use percentage-based trailing
- Add profit target: take partial profits at 3-5% gain, let remainder run
- Consider only entering on *new* trend starts (price crossing above SMA200), not just being above it

**Verdict:** V2.0 rejected. Proceed to V2.1 with tightened entry, faster exit, and wider stops.

**Artifact:** Backtest result in `user_data/backtest_results/` (timestamped export)

---

## WFA-1Y-ML-001 — FreqAI ML 1-Year Walk-Forward (First Full-Data OOS)

**Date:** 2026-08-25
**Strategy:** `FreqaiMultiFactorBtcStrategy.py` (unchanged)
**Config:** config.json + config_freqai.json, `--freqaimodel LightGBMRegressor`
**Data:** BTC/USDT 1h+4h, **2025-08-26 → 2026-08-24** (1 year, full 4h coverage — 4h data was backfilled to 2yr first)
**Setup:** FreqAI rolling 30d train / 7d test windows (~52 folds), each test window out-of-sample

**Results:**
- 39 trades, **-25.41%** (-254 USDT), win rate 64.1% (25W/14L)
- Profit factor 0.57, expectancy -6.51 USDT/trade, Sharpe -0.47, p=0.164
- Max DD 32.7% (342 USDT), DD duration 228 days
- **Market change over period: -27.9%** (bear regime) — strategy beat buy-and-hold by ~2.5pts

**Exit reasons:** 24 roi, 13 stop_loss, 2 exit_signal
**Win/loss asymmetry:** avg win +1.61% (ROI-capped) vs avg loss -4.84% (full stop) — 64% win rate cannot overcome 1.6:4.8 payoff ratio
**Monthly:** +6.0% Apr, +4.5% Jul, +1.5% Sep/May; crushed -17.8% Jun, -10.4% Feb, -6.7% Nov

**Diagnosis (3 structural problems, not model failure):**
1. Long-only in a -27.9% bear market — no cash filter; strategy still beat buy-and-hold
2. `minimal_roi` (5%/3%/1.5% tiers) caps winners while stop_loss (-5%) runs full — payoff structure destroys a real 64% signal
3. Horizon mismatch: model predicts 3 candles ahead but avg holding is 1d 9h — signal decays ~10× before exit

**Verdict:** ML signal confirmed real (64.1% win vs ~50% random) but wrapper is broken. Iterate to WFA-1Y-ML-002 with: (a) ROI rework → ATR trailing, (b) horizon-aligned exits (3-6h or signal reversal), (c) bear/cash filter when model down-probability high.

**Artifact:** `user_data/backtest_results/backtest-result-2026-08-25_03-03-06.zip`

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

*Last updated: 2026-08-25*
