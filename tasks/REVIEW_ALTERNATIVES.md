# Review Alternatives — Modest-Bohr Strategy Redesign

**Author:** Alternative Generator (independent review subagent)
**Date:** 2026-08-25
**Purpose:** Propose fresh, evidence-grounded strategy designs after the exhaustion of (a) directional ML (7 backtests, all losing; prediction→actual correlation ≈ 0) and (b) rule-based trend-following V2.1 (gross edge +25% destroyed by fee churn; 38.5% drawdown).

**Constraints honored:** BTC/USDT only · spot (Binance US — no shorting) · positive expectancy *after* costs · max drawdown ≤ 20% · secondary-income grade · paper-trading first · implementable in Freqtrade/FreqAI.

---

## 0. The Two Proven Killers (everything below is designed to neutralize them)

Every prior strategy died from one or both of these, so every alternative here is explicitly scored against them.

| # | Killer | Mechanism | Evidence in our log |
|---|---|---|---|
| K1 | **Fee churn (overtrading)** | 0.2% round-trip fee (0.1%/side) + ~0.05% slippage ≈ 0.25% per trade. At 139 trades/yr that is **~28–35% of capital/year**, fully consuming the +25% gross edge. The 406-trade whipsaw run (tight 1.5× ATR trailing) made it far worse. | V2.1: +25% gross → net loss; 139+ trades; 406-trade whipsaw variant |
| K2 | **Long-only drawdown** | Single volatile pair, always-in-market long exposure, no cash filter → full bear-market losses. 38.5% DD vs a 20% ceiling. | V2.1 DD 38.5%; WFA-1Y-ML-001 −25.4% (long-only in a −27.9% bear), DD 32.7% |

**Design axioms derived from the evidence:**

1. **Trade far less.** Fee drag is linear in trade count; gross edge is roughly flat. The single highest-leverage move is cutting trades from 139–406/yr to ~15–40/yr, turning a ~30% drag into a ~4–8% drag while keeping most of the +25% gross edge.
2. **Go to cash in bear regimes.** Without shorting (spot), drawdown control = *not being long*. A flat/cash state is a real position.
3. **Never cap winners while letting losers run.** WFA-1Y-ML-001 proved the killer asymmetry: avg win +1.61% (ROI-capped) vs avg loss −4.84% (full stop). ML-002 proved the fix: removing the ROI cap let one winner run to **+7.43%** and collapsed DD from 32.7% → 0.45%. Wrapper > signal here.
4. **Use macro data for what it is good at (slow regime), not what it failed at (3h direction).** Macro features had ~zero importance for *direction*. That does not prove they are useless for *regime* — that is the untested hypothesis.
5. **Regime is the learnable target; direction is not.** Build systems that route between regime-appropriate engines rather than predict up/down.

---

## 1. Ranking Summary

| Rank | Name | Targets | Primary bet | Fee drag/yr (est.) |
|---|---|---|---|---|
| **1** | Regime-Gated Low-Frequency Trend (RLF-Trend) | K1 + K2 | Keep +25% gross edge, cut trades ~80–90% | ~4–6% |
| **2** | ML Regime-Classifier-as-Switch (no direction) | K1 + K2 + untested ML-regime hypothesis | Regime is learnable; route engines by regime | ~4–8% |
| **3** | Volatility-Adaptive Mean Reversion (sideways-only) | K2 (and the "lost in sideways" gap) | Range-bound BTC mean-reverts; trend lost −7.57% there | ~5–8% |
| **4** | Asymmetric Donchian Breakout (Turtle-style) | payoff asymmetry + K1 | Fix the ROI-cap/stop wrapper; let winners run | ~3–5% |

---

## 2. Alternative 1 — Regime-Gated Low-Frequency Trend (RLF-Trend) — **RANK 1**

**(a) Hypothesis.** The +25% *gross* edge is real — trend-following captures BTC's fat-tailed directional moves — but it lives at the *weekly-to-monthly* horizon, not the hourly one. V2.1 destroyed it by (i) trading 139–406×/yr so fees ate the entire edge, and (ii) using a too-tight 1.5× ATR trailing stop that whipsawed 406 trades. If we keep the *same* entry thesis but (i) drop frequency to ~15–30 trades/yr, (ii) use wide volatility stops (2.5–3× ATR) so normal noise cannot stop us out, (iii) remove the ROI cap so winners run (ML-002 evidence), and (iv) go flat below the macro trend, the gross edge survives net of costs and drawdown collapses.

**(b) Concrete Freqtrade rules.**

- **Timeframes:** 1h primary; 4h (and optionally 1d) informative pair for the macro filter and pullback zone.
- **Macro/regime gate (rule-based, not ML):** on 4h informative — `close_4h > EMA200_4h` AND `EMA50_4h > EMA200_4h` (uptrend). When false → **flat (cash), no entries, exit any open position.** This is the drawdown control; use the 4h EMA200 (≈33 days), *not* the 1h SMA200 that over-filtered in ML-002 (39→3 trades).
- **Entry trigger (pullback, not breakout — do not chase):** with the gate true, enter long on the 1h close when:
  - price is inside the pullback zone `EMA50_4h * 0.995 <= close <= EMA20_4h * 1.005` (per the multifactor skill), **AND**
  - `RSI(14, 1h)` in 45–60 (mid-momentum, not overbought), **AND**
  - volume confirmation: `volume_1h > rolling_mean(volume, 50)`.
- **Exit (let winners run, no ROI cap):**
  - Wide trailing: 2.5× ATR(14) **capped at 2% of current price** (per skill; prevents stop-widening in vol spikes). Bounds `max(min(-2.5*ATR, -2%), -6%)`.
  - Structural exit: `close_1h < EMA50_4h` (trend broken).
  - Time stop: exit after 96 candles (4 days) if still at a loss (dead-capital guard).
  - **No `minimal_roi`** — this is the ML-002 fix that let a winner run +7.43%.
- **Risk:** max 1 open trade; **1% of equity risk per trade** → position size = 1%·equity / stop distance; hard backstop stop −2%; **drawdown circuit breaker**: if equity DD from peak > 15%, go flat and stay flat until price reclaims the macro filter (re-arm).
- **Config hygiene (from skill):** `startup_candle_count = 800` (200 × 4× HTF multiplier); do **not** combine `trailing_stop=True` with `use_custom_stoploss=True`; use `merge_informative_pair()`.

**(c) Why it succeeds where V2.1/ML failed.**
- **K1 (fees):** 15–30 trades/yr ⇒ ~4–6% fee+slippage drag vs ~28–35% before — the +25% gross edge is no longer consumed.
- **K2 (drawdown):** flat-below-EMA200 removes bear exposure (the exact thing that gave ML-001 −25.4% and V2.1 38.5% DD); 1% risk + wide stops end the 406-trade whipsaw; 15% DD breaker hard-caps the tail.
- **Payoff asymmetry:** no ROI cap + wide trailing restores a ≥2:1 reward:risk instead of the 1.6:4.8 ratio that killed ML-001.

**(d) Falsification backtest.** 2-year walk-forward (2024-08 → 2026-08), 0.1% fee + 0.05% slippage. **Fail if any of:** (i) net P&L after costs ≤ 0; (ii) max DD > 20%; (iii) **< 30 trades** (edge statistically indistinguishable from luck — the bar from SPEC_V2 §5); (iv) the gross edge *collapses when trades are reduced* — i.e., if the +25% gross was an artifact of many small lucky trades, not a real trend edge, this test exposes it. **Sensitivity:** perturb ATR multiplier 2.0↔3.5× and EMA periods ±20% — the edge must survive (smooth landscape, not a noise-fit optimum). Must pass `freqtrade lookahead-analysis`.

---

## 3. Alternative 2 — ML Regime-Classifier-as-Switch (no direction) — **RANK 2**

**(a) Hypothesis.** Directional ML failed because short-horizon direction (3h/12h/24h) is ~unpredictable (correlation ≈ 0), and macro features had ~zero importance *for direction*. But **regime (bull/bear/sideways) is a lower-frequency, higher-signal-to-noise label** and is the one target the project has flagged as more-learnable yet never tested as an ML target. The macro features that were useless for direction (fear/greed, funding, OI, long/short ratio, DXY, SPY, stablecoin supply — 755 days now available) may be genuinely informative for *regime* because regime shifts are slow and macro-driven. So: train a LightGBM **classifier** to label the regime, and use it only to **select which of a small set of simple rule engines runs** — never to predict price direction.

**(b) Concrete Freqtrade/FreqAI rules.**

- **Target (FreqAI):** a 7-day-ahead regime label, not a direction. Define label from data: `bull` = `close > EMA200_4h` AND `EMA200_4h` slope > 0 AND `ADX(14) > 20`; `bear` = mirror; `sideways` = otherwise. (Same definitions as `regime_decompose.py`/SPEC_V2 §4.1 — consistent with prior work.)
- **Features:** the 7 macro factors (as z-scores / % changes, loaded from the backfilled `market_regime_history.json` — never live APIs in `populate_indicators`), plus rolling technicals on 4h/1d: realized vol (ATR percentile), drawdown-from-52-week-high, EMA50/200 slope, funding-rate z-score, OI 7d change, stablecoin-supply 30d change.
- **Switch logic (per-candle, 1h):**
  - `P(bull) > θ_bull` → run the **low-frequency trend engine** (Alt 1 rules), size **1.0×**.
  - `P(sideways) > θ_side` → run the **mean-reversion engine** (Alt 3 rules), size **0.5×**.
  - `P(bear) > θ_bear` → **flat (cash)**, size 0×, exit open positions.
  - Below all thresholds → flat (default conservative).
- **Risk:** same 1% per-trade risk, 15% DD circuit breaker, max 1 open trade. Thresholds θ set on a held-out calibration fold, then frozen (no re-tuning on test folds).

**(c) Why it succeeds where directional ML failed.**
- It **never predicts direction** — it predicts the one thing the evidence says may be learnable (regime), sidestepping the correlation≈0 problem entirely.
- It **repurposes the macro data for what it is actually good at**: slow regime shifts, not 3h direction (which is exactly why macro importance was ~0 before).
- **Drawdown is controlled by construction** — bear → flat — directly removing the long-only-in-bear killer.
- It is genuinely **novel and untested** in this project, so it is the highest-information-value experiment.

**(d) Falsification backtest — two-stage.**
1. **Classifier gate (before any P&L):** on a strict out-of-sample split, the regime classifier must beat a naive baseline (e.g., "regime persists" / "yesterday's label") on AUC or balanced accuracy. **If it cannot beat persistence, the switch adds nothing → fail immediately** (cheap, decisive).
2. **Composite walk-forward:** the regime-switched composite must beat the best *single* engine (Alt 1 alone) **net of costs**, with DD ≤ 20% and ≥ 50 trades across folds. **If switching adds no value over "always run the trend engine with a rule gate," fail.** Pass `lookahead-analysis`; confirm the classifier isn't leaking future regime labels.

---

## 4. Alternative 3 — Volatility-Adaptive Mean Reversion (sideways-only) — **RANK 3**

**(a) Hypothesis.** The 2-year window was dominated by non-trending chop: ~201 days sideways (Aug 2024–Mar 2025) plus a ~275-day bear with significant range periods. In range-bound conditions BTC 1h shows short-horizon **mean reversion** (RSI/Bollinger overbought/oversold → snap back to the mean), which the initial-findings research scored at ~50–55% standalone, *better in range-bound markets*. Trend-following lost −7.57% in the sideways regime precisely because it is the wrong tool there. This design is the *complement* to Alt 1: it harvests the regime Alt 1 (correctly) avoids.

**(b) Concrete Freqtrade rules.**

- **Gate (sideways only):** on 4h informative — `|close - EMA200_4h| / EMA200_4h < 3%` AND `ADX(14) < 20` AND `ATR(14) < rolling_median(ATR, 100)` (low vol). (Matches SPEC_V2 §4.1 "Sideways Low-Vol".) If gate false → flat.
- **Entry (long, contrarian confluence — rare by design):** `RSI(14, 1h) < 30` AND `close < lower Bollinger(20, 2σ)` AND a bullish reversal candle (close > open and close in the lower half of the prior candle's range). Optional contrarian confirm: fear/greed < 20 (from macro history).
- **Exit (mean target, tight):**
  - Take profit: `close > SMA20_1h` (middle Bollinger) **OR** `RSI(14) > 55`.
  - Stop: 1.5× ATR(14) **capped at 1.5%**, hard floor −1.5%.
  - Time stop: 24 candles (1 day) flat.
- **Risk:** **0.5× position size** (half the trend engine), max 1 open trade, 15% DD circuit breaker.

**(c) Why it succeeds where prior failed.**
- It targets the exact regime where prior strategies **lost money** (sideways −7.57%), with the strategy type actually suited to it, instead of forcing trend-following everywhere.
- **K2:** 0.5× size + tight 1.5% stops + low-vol-only gate = bounded, short-holding exposure (not "long-only in a volatile market").
- **K1:** the RSI<30 **and** lower-Bollinger **and** reversal-candle confluence is rare (~1–2 signals/month in true sideways), so it avoids the 406-trade whipsaw trap and stays ~15–25 trades/yr, keeping fee drag ~5–8%.

**(d) Falsification backtest.** Restrict the 2-year window to sideways sub-periods (from `regime_classification.csv`). **Fail if:** (i) net P&L after costs ≤ 0 in sideways periods; (ii) signals fire > 80/yr (fee churn reappears — the confluence isn't tight enough); (iii) DD > 20%; (iv) **the payoff is negative-skewed** — mean reversion that wins small 80% of the time but occasionally eats a full −1.5% gap stop can still be net-negative; expectancy must be positive *including* those gap losses. Confirm the "win rate" isn't another exit-structure artifact (the exact trap the log warns about).

---

## 5. Alternative 4 — Asymmetric Donchian Breakout (Turtle-style) — **RANK 4**

**(a) Hypothesis.** The most damning result in the log is the *payoff asymmetry*, not the signal: ML-001 winners were capped at +1.61% by `minimal_roi` while losers ran to −4.84%. ML-002 proved the fix — removing the ROI cap let a winner run +7.43% and cut DD 32.7% → 0.45%. A Donchian channel breakout (20-day-high entry / 10-day-low exit) is the canonical *low-frequency* trend system that structurally produces a positive payoff ratio: it trades rarely (breakouts are scarce), cuts losers small, and lets winners run to +5–10% with a wide trailing — no ROI cap, no tight trailing.

**(b) Concrete Freqtrade rules.**

- **Timeframes:** 1h primary; 4h informative for the Donchian channel (55 bars on 4h ≈ 20 days) and macro gate.
- **Macro gate:** `close_4h > EMA200_4h` (uptrend) — else flat (same drawdown control as Alt 1).
- **Entry:** `close_1h` closes above the 55-bar high of the 4h channel (Donchian upper band). Optional add-on: pyramid +0.5× at each +2× ATR(14) gain, max 2 units total.
- **Exit:** `close_1h < 20-bar low of the 4h channel` (trend broken) **OR** wide trailing 3× ATR(14) capped 3%, hard backstop −2.5%. **No `minimal_roi`** (this is the explicit payoff-asymmetry fix).
- **Risk:** 1% initial risk per trade; max 2 units; 15% DD circuit breaker.

**(c) Why it succeeds where ML-001/V2.1 failed.**
- **Payoff asymmetry:** wide trailing + no ROI cap restores ≥2:1 reward:risk — the exact structural fix ML-002 validated (the +7.43% runner).
- **K1:** breakouts are rare → ~15–25 trades/yr, ~3–5% fee drag, vs 139–406 trades before.
- **K2:** flat-below-EMA200 + wide stop + 15% breaker caps the tail drawdown.
- It is a **wrapper/sizing fix on a known-good gross edge**, not a bet on a new signal — the highest-conviction change with the clearest causal story.

**(d) Falsification backtest.** 2-year walk-forward (0.1% fee + 0.05% slippage). **Fail if:** (i) < 20 trades (edge untestable — a real risk for low-frequency breakouts); (ii) net P&L after costs ≤ 0; (iii) DD > 20%; (iv) the +7.43%-style runners do **not** recur often enough to overcome many small −2.5% stops (expectancy < 0). **Sensitivity:** Donchian entry {40, 55, 80} × exit {15, 20, 25} must not collapse the edge. Pass `lookahead-analysis`.

---

## 6. How the Alternatives Map to the Killers (at a glance)

| Alternative | K1 fee churn | K2 drawdown | Payoff asymmetry |
|---|---|---|---|
| 1. RLF-Trend | 139→~20 trades | flat-below-EMA200 + 1% risk + 15% breaker | no ROI cap + wide trailing |
| 2. Regime-switch | per-regime engines, ~20–30 trades | bear→flat by construction | regime-appropriate exits |
| 3. Mean reversion | strict confluence, ~15–25 trades | 0.5× size + 1.5% stops + low-vol gate | tight target vs tight stop |
| 4. Donchian breakout | ~15–25 trades | flat-below-EMA200 + wide stop | no ROI cap + 3× ATR trail |

---

## 7. Recommended Next Steps (falsification-first, cheapest → dearest)

1. **Alt 1 first.** It is the lowest-risk, highest-confidence move: it reuses the already-proven +25% gross edge and only changes *frequency, stop width, and the cash filter*. If Alt 1's walk-forward passes (net > 0, DD ≤ 20%, ≥ 30 trades), paper-trade it immediately.
2. **Alt 2's classifier gate in parallel** (cheap, decisive): run the classifier-vs-persistence test *before* building the full composite. If regime isn't learnable, kill Alt 2 in a day.
3. **Alt 4 as the wrapper fallback** if Alt 1's wide-trend variant underperforms the breakout variant.
4. **Alt 3 only if** the sideways sub-periods are confirmed (via `regime_classification.csv`) to be large enough to be worth harvesting, and only at 0.5× size.
5. Every candidate must pass `lookahead-analysis` and a parameter-sensitivity perturbation before paper-trading sign-off (SPEC_V2 §7.2).

---

*Generated as an independent review; none of these designs defends the existing ML or V2.1 approach. All are long-only (spot constraint) with drawdown controlled by cash-flat states and position sizing, and all explicitly cut trade frequency to defeat the fee-churn killer.*
