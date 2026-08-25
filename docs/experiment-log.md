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

## WFA-1Y-ML-002 — Wrapper Fixes (ATR trailing + horizon stop + SMA200 gate)

**Date:** 2026-08-25
**Strategy:** `FreqaiMultiFactorBtcV2Strategy.py` (model/features identical to ML-001; wrapper changed)
**Config:** config.json + config_freqai_v2.json (`MultiFactorLightGBM-1Year-V2`), `--freqaimodel LightGBMRegressor`
**Data:** BTC/USDT 1h+4h, **2025-08-26 → 2026-08-24** (same 1-year window as ML-001)
**Changes vs ML-001:**
1. `minimal_roi` disabled → ATR trailing stop (2× ATR below max_rate, −5% backstop)
2. `custom_exit` horizon stop: exit after 6h if profit < 1%
3. Entry gate: `close > SMA200` (bull regime filter)

**Results:**
- **3 trades only** (vs 39 in ML-001) — SMA200 gate over-filtered in the −26.9% market
- +7.5% total, 66.7% win (2W/1L), avg profit/trade **+2.52%** (vs −0.70% ML-001)
- Max DD **0.45%** (2 days) vs 32.7% (228 days) in ML-001
- Sharpe 1.07, Calmar 7.6, p=0.41

**Trade-level (3 trades):**
- 2026-04-13 → 04-13, horizon_stop, −0.46% (dead signal cut fast ✓)
- 2026-04-13 → 04-21, exit_signal, **+7.43%** (8-day runner — exited on model-signal flip, NOT the ATR trailing)
- 2026-07-20 → 07-20, horizon_stop, +0.60%

**Diagnosis (decomposition):**
- Fix 2 (horizon stop) WORKED: dead signals cut at 6h, DD collapsed 32.7% → 0.45%
- **Fix 1 (ATR trailing) NEVER FIRED** — `self.dp.ohlcv()` returned a DataFrame unpacked as a tuple → ValueError → silent fallback to static stop. Discovered later; see ML-003/004 audit. The +7.43% winner exited via exit_signal, not trailing.
- Fix 3 (SMA200) FAILED as designed: 39 → 3 trades, killed the profitable bear-bounce trades (Apr/Jul were ML-001's best months, all below SMA200)
- 3 trades = statistically meaningless → iterate to ML-003

**Verdict:** Keep horizon stop, drop Fix 3, FIX the trailing (unbeknownst). ML-003 = exit fixes only.

**Artifact:** `user_data/backtest_results/backtest-result-2026-08-25_06-16-46.zip`

---

## WFA-1Y-ML-003 — Exit fixes only (2× ATR trailing + 6h stop, no SMA200)

**Date:** 2026-08-25 · **Strategy:** `FreqaiMultiFactorBtcV3Strategy.py`
**Config:** config_freqai_v2.json · **Window:** 2025-08-26 → 2026-08-24

**Results:** 80 trades, **−31.57%**, win 41.2% (33W/47L), DD 31.75%, avg duration 11h
**Exit reasons:** horizon_stop 75, stop_loss 3, exit_signal 2
- Wins avg +0.74% / losses avg −1.31% (loss-cutter worked) BUT win rate halved (64%→41%) and trades doubled (39→80, ~16% fee drag).

**Diagnosis:** 6h horizon stop too tight — strangled developing winners AND removed the `max_open_trades=1` slot as a natural filter (fast exits → constant re-entry on marginal signals).

## WFA-1Y-ML-004 — Retuned wrapper (3× ATR, 24h stop, −3% hard stop)

**Date:** 2026-08-25 · **Strategy:** `FreqaiMultiFactorBtcV4Strategy.py`
**Results:** 44 trades, **−39.85%**, win **11.4%** (5W/39L), DD 42.3%
**Exit reasons:** horizon_stop 24, stop_loss 15, exit_signal 5
**Diagnosis:** 24h horizon stop strangled 24 would-be winners into losses. Confirms: any horizon-stop-on-the-model approach destroys the win side.

## WFA-1Y-ML-005 — Stop-loss test (stoploss −5% → −1.5%, everything else = ML-001)

**Date:** 2026-08-25 · **Strategy:** `FreqaiMultiFactorBtcV5Strategy.py`
**Results:** 92 trades, **−31.63%**, win 37.0% (34W/58L), p=**0.024**, DD 33.3%
**Exit reasons:** stop_loss 58, roi 34
**Diagnosis:** The −1.5% stop **falsified the "cut losers tighter" hypothesis.** 64%→37% win rate = whipsaw: 1h BTC dips >1.5% inside noise before the predicted move plays out. Also doubled trade count (39→92) → ~18.4% fee drag. Statistically significant (p=0.024) but *negative*.

## WFA-1Y-ML-006a/006b — Target-horizon test (12h & 24h)

**Date:** 2026-08-25 · **Strategy:** `FreqaiMultiFactorBtcV6Strategy.py` (12h) / `V7` (24h)
**Results:**
- 12h: 96 trades, −48.71%, win 63.5%, p=0.016
- 24h: 96 trades, −33.92%, win 67.7%, p=0.139

**Calibration (the decisive check — see `docs/research/calibration-evidence.md`):**
- 12h corr(pred,actual) = −0.020 · 24h = +0.010 · (3h baseline = −0.017)
- **Correlation ≈ 0 at every horizon.** Higher predictions never produce higher returns. Win rates were exit-structure artifacts.

**Verdict: directional ML abandoned.** The model has no predictive edge at any horizon.

---

## V2.1 — Faithful SPEC_V2 implementation (rule-based trend-following)

**Date:** 2026-08-25 · **Strategy:** `BtcTrendFollowingV21Strategy.py`
**Config:** config_baseline.json · **Window:** 2024-09-01 → 2026-08-24 (2yr, +33% bull market)

**Result A (structural exit only — `ohlcv` bug meant trailing never fired):**
- 139 trades, **−2.83% net**, win 25.2% (35W/104L), PF **0.976**, p=**0.933**, DD 38.5%
- Wins avg +3.30% (held 2d15h) vs losses avg −1.09% (held 14h) — 3.03:1 payoff, exactly the 3:1 a 25% win rate needs to break even.

**Result B (1.5× ATR trailing actually firing):**
- 406 trades, **−82.95%**, avg duration 2h27m — 1.5× ATR ≈ 0.5–0.7% is inside 1h noise → pure whipsaw. (Fees: 406 × 0.2% ≈ 81% ≈ the loss.)

**⚠️ Correction (from cross-review):** the earlier "gross +25% edge consumed by 27.8% fees" claim was **wrong** — freqtrade already models fees in each trade's P&L, so PF 0.976 is the true gross: the entry is a coin-flip (p=0.93), not an edge being fee'd away. **There is no gross edge to rescue.** The 3.03:1 payoff with 25% win rate = precisely breakeven.

**Verdict:** entry has no statistical edge. V2.2 (widen exit + drop trailing) would be the 3rd exit-tuning iteration polishing a zero-edge entry — **abandoned on cross-review.**

---

## NULL-ENTRY-CONTROL — the decisive falsification

**Date:** 2026-08-25 · **Strategy:** `NullEntryControlStrategy.py`
**Design:** identical exits to V2.1 (SMA50 structural + 48c time stop, no trailing), but entry = unconditional every 126 candles (zero market info).

**Results:**
- 81 trades, **+30.32%**, PF **1.51**, win 27.2%, **DD 15.1%**, Sharpe 0.80, p=0.33
- vs V2.1 real entry: 139 trades, −2.83%, PF 0.976, DD 38.5%
- vs buy-and-hold: +33.3%

**The entry signal is WORSE than random.** Entering with zero information beat the engineered entry (regime gate + 4/6 score + higher-high) by 33 points with half the drawdown. The exits were doing all the value preservation; the entries were subtracting.

**Conclusion:** the edge (if any) lives in *regime filtering + letting winners run*, NOT in entry timing. This validates the Alternative Generator's Rank 1 (regime-gated low-frequency trend) — "dumb" cadence/pullback entries inside a trend filter, wide stops, structural exits.

**Next:** implement a regime-gated low-frequency strategy (macro/trend filter → simple entry → SMA structural exit + wide ATR stop), NOT another entry-signal refinement.

---

## Cross-Review Verdict — Antigravity RegimeGatedTrendStrategy (2026-08-25)

Verified Antigravity's final strategy independently. **Real and best result to date.**

- 1y bear (mkt −29.02%): **+24.41%**, PF 2.20, DD 7.66%, 28 trades
- 2y full (mkt +36.90%): **+26.70%**, PF 1.38, 86 trades
- Lookahead check (`price_side="other"`): identical result → NOT lookahead-driven.

**Corrections to Antigravity's diagnosis:**
1. ATR trailing stop was the poison, not the victim — removal (already in final file) is the fix, not loosening. With trailing: 1y +6.09% / 2y +1.44%. Without: +24.41% / +26.70%.
2. The "+24.41% defense" was the *no-trailing* version, not the ATR stop.
3. **No stop loss is active:** config `stoploss=-0.99` overrides strategy `-0.15`. Defense = SMA50 exit + time stop only.

**Caveats:** not statistically significant (p=0.3176, 28 trades); no stop-loss → gap tail risk (worst −5.07%).

Full verdict: `docs/cross-review-verdict-antigravity.md`

---

## Fix Verification — Wider Exit + Disaster Stop (2026-08-25)

| Exit | 1y (mkt −29.02%) | 2y (mkt +36.90%) |
|---|---|---|
| SMA50 | +24.41% (DD 7.66%) | +26.70% (DD 12.49%) |
| SMA100 | +14.39% | +40.11% (dominated — dropped) |
| **SMA200** | +20.23% (DD 10.74%) | **+61.25% (DD 10.73%)** |

- **Disaster stop fixed:** config `stoploss` −0.99 → −0.15 (was silently disabling all stops). Never triggers in backtest (worst trade −6.34% > −15%) → free tail insurance.
- **SMA200 exit wins:** beats buy-and-hold over 2y (+61.25% vs +36.90%), retains positive bear defense.
- **Adopt** `RegimeGatedTrendSMA200Strategy` as canonical.

See `docs/cross-review-verdict-antigravity.md` § "Fix Verification".

---

## 7-Gate Validation — RegimeGatedTrendSMA200Strategy (2026-08-25)

- **Gate 1 (data):** 1h 17,548 candles (2024-08-24→2026-08-25), 4h 4,525 (2024-08-01→2026-08-25) — full 2y coverage. Macro N/A (price-based regime only).
- **Gate 2 (config):** `binanceus` authoritative (datadir key ignored — known quirk). ✓
- **Gate 3 (smoke):** 5-day run clean, 1 trade, no errors. ✓
- **Gate 4 (calibration):** N/A (rule-based).
- **Gate 5 (full):** 2y +61.25%, PF 1.81, DD 10.73%, 88 trades. ✓
- **Gate 6 (exit audit):** exit_signal 78 · time_stop 9 · force_exit 1 · **stop_loss 0** (disaster stop −0.15 active, never fires). Mechanisms verified, no silent failure. ✓
- **Gate 7 (immutability):** SHA pinned at commit of this entry.

**Walk-forward (4 × ~6mo):**

| Window | Market | Net | PF | Trades |
|---|---|---|---|---|
| 2024-08→2025-02 | +75.81% | +17.31% | 1.59 | 26 |
| 2025-02→2025-08 | +12.59% | +12.93% | 1.90 | 26 |
| 2025-08→2026-02 | −31.58% | +1.63% | 1.21 | 14 |
| 2026-02→2026-08 | +1.07% | +17.65% | 2.16 | 23 |

**All 4 windows positive.** Bear survival: +1.63% vs −31.58% market. Alpha signal: +17.65% in a +1.07% flat market. No negative regime. **PASS.**

**Action:** switched config `strategy` → `RegimeGatedTrendSMA200Strategy` (was stale `BtcEmaCrossoverStrategy`).

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
