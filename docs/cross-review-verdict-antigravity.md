# Cross-Review Verdict — Antigravity's RegimeGatedTrendStrategy (FINAL)

**Date:** 2026-08-25
**Reviewer:** Hermes (independent re-verification against disk + backtest results)
**Subject:** `user_data/strategies/RegimeGatedTrendStrategy.py` (Antigravity's final work)

---

## Verified results (current code, ATR trailing stop REMOVED)

| Window | Market | Net | PF | Max DD | Trades | Win% |
|---|---|---|---|---|---|---|
| 1y `20250825-20260825` (bear) | −29.02% | **+24.41%** | 2.20 | 7.66% | 28 | 25% |
| 2y `20240801-20260825` (full) | +36.90% | **+26.70%** | 1.38 | — | 86 | — |

1y detail: best trade +19.87%, worst −2.63%, expectancy 0.77R, max consecutive losses 7.

## Robustness (lookahead check)

Ran 1y with `entry_pricing.price_side="other"` + `exit_pricing.price_side="other"` + `use_order_book=false`
(next-candle-open fills). **Result identical: +24.41%, 28 trades, PF 2.20, same fill prices.**
The strategy holds positions for days (avg winner ~3d), so a 1h open-vs-close fill difference is negligible.
**The +24.41% is NOT an artifact of lookahead fill pricing.**

---

## Corrections to Antigravity's self-diagnosis

### 1. The ATR trailing stop was the poison, not the victim
Antigravity concluded "the 3.0× ATR trailing stop is too tight for bull markets — loosen it."
**Wrong remedy.** The correct fix was *removal* (which Antigravity's final file actually did).
The trailing stop reduced returns in *every* window it touched:

| | 1y (bear) | 2y (full) |
|---|---|---|
| With ATR trailing | +6.09% | +1.44% |
| **Without (final)** | **+24.41%** | **+26.70%** |

The "+1.44% 2-year" that made Antigravity panic was the *trailing-enabled* version.
Without it, the strategy does +26.70% over 2 years. The trailing stop was never "choking the bull offense" —
it was suppressing returns in both regimes.

### 2. The "+24.41% god-tier defense" was NOT the ATR stop
It was the *no-trailing* version: regime filter + dumb pullback entry + SMA50 structural exit + time stop.
Antigravity mis-attributed its own best result to the component it then blamed.

### 3. There is NO stop loss active — config `stoploss=-0.99` overrides the strategy's `-0.15`
Trade-level JSON shows `initial_stop_loss_ratio = -0.99` on every trade.
The strategy *declares* `stoploss = -0.15` ("disaster stop") but `config_baseline.json` sets `-0.99`,
and the config value wins. **The entire defense is the SMA50 structural exit + the 48-candle time stop.**
This is *more* impressive for the regime-filter thesis (7.66% DD with zero stop-loss), but it leaves
unaddressed tail risk: a single 1h candle gapping through SMA50 has no stop to catch it (worst 2y trade already −5.07%).

---

## Honest caveats (do not oversell)

- **No stop loss** → gap-through-SMA50 tail risk. Recommend adding a real disaster stop (e.g. −12~15% *that actually applies*) and re-testing.
- **Not statistically significant:** mean-profit p-value 0.3176; 28 trades over 1 year is thin. This is *directional evidence*, not proof of robust edge.
- **Weak per-trade metrics:** Sharpe (closed trades) 0.29, SQN 1.02, win rate 25%. Low win rate is offset by high expectancy (letting winners run), but the closed-trade Sharpe understates a low-frequency defensive strategy.

---

## Verdict

**REAL and the best result this project has produced.** The regime filter + "dumb" pullback entry +
structural SMA50 exit is the edge — independently reached by Antigravity and confirmed by the
null-entry control on the Hermes side. The ATR trailing stop is now falsified *again* (it has damaged
every strategy it touched: ML-002 → V2.1 → this one).

**Recommendation (next steps):**
1. Add a *working* disaster stop (fix the config `-0.99` → `-0.15` or move it into the strategy) and re-verify DD stays ≤ target.
2. Test a wider structural exit (SMA100/200) for bull-market capture — the 2y +26.70% vs market +36.90% gap is the known cost of a defensive-only-long strategy.
3. Run the 7-gate walk-forward protocol (see `docs/RESEARCH_HARNESS.md`) before any live/paper deployment.

*Artifact: this document. Backtest zips in `user_data/backtest_results/` (notes `FINAL-1Y-CLEAN`, `FINAL-2Y-CLEAN`, `LA-CHECK-1Y`).*
