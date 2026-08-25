# Monte Carlo & Slippage Analysis — RegimeGatedTrendSMA200Strategy

**Date:** 2026-08-25
**Script:** `user_data/scripts/monte_carlo_analysis.py` (reproducibility artifact)
**Data:** 88-trade 2y backtest export (`GATE5-CANONICAL-2Y`), 31-trade 1y export
**Seed:** 42 · **Iterations:** 10,000 each

---

## Corrected tearsheet metrics (trade-level, SHA-consistent)

| Window | Net | PF (abs) | Max DD | Trades | Win% | Best / Worst |
|---|---|---|---|---|---|---|
| 2y (2024-08→2026-08) | +61.25% | 1.81 | 10.73% | 88 | 28.4% | +27.09% / −6.34% |
| 1y (2025-08→2026-08) | +20.23% | 1.95 | 10.74% | 31 | 35.5% | +22.83% / −6.34% |

*Note: the previous whitepaper tearsheet conflated SMA50 metrics (PF 1.38, DD 7.66%, PF 2.20) with SMA200 headline returns. The table above is the corrected SMA200-only version.*

Exit-reason audit (2y): `exit_signal` 78 · `time_stop` 9 · `force_exit` 1 · `stop_loss` 0.

---

## Monte Carlo results (2y, 88 trades)

### Permutation MC — drawdown clustering (trade-order shuffle)

| Metric | Value |
|---|---|
| Actual drawdown (backtest order) | 10.8% |
| Expected drawdown (median of 10,000 orderings) | ~15.8% |
| P(drawdown > 20%) | 17.9% |
| P(drawdown > 25%) | 3.3% |
| Worst-case drawdown (max of 10,000) | 36.3% |

**Finding:** the backtest's ~10.8% drawdown is optimistic. Under random ordering the
typical drawdown is ~16%, and there is a ~18% chance of exceeding the 20% target purely
from trade clustering. The ≤20% drawdown goal is **not robustly guaranteed**.

### Bootstrap MC — sampling uncertainty / risk of ruin (resample w/ replacement)

| Metric | Value |
|---|---|
| Mean 2y return | +74.9% |
| Median 2y return | +57.0% |
| 5th percentile return | −10.1% |
| 95th percentile return | +220.7% |
| **P(2y return < 0) — risk of ruin** | **9.7%** |
| DD p95 | 29.8% |

**Finding:** the edge is real (median +57%), but there is a ~10% chance a given 2-year
run loses money due to sampling variance.

---

## Slippage model (0.05% per side = 0.10% round-trip, on top of 0.1% fee)

| Metric | No slippage | With slippage |
|---|---|---|
| 2y net profit | +61.25% | +48.31% |
| Profit factor | 1.81 | 1.70 |
| Max drawdown | 10.73% | 11.45% |
| Win rate | 28.4% | 25.0% |
| Worst trade | −6.34% | −6.44% |
| Risk of ruin (P(return<0)) | 9.7% | 14.9% |

**Finding:** the alpha **survives** the slippage tax (+48.31% still beats buy-and-hold
+36.90%), but tail risk worsens — risk of ruin rises from ~10% to ~15%.

---

## Verdict

The strategy's edge is real and slippage-robust, but **two risk corrections are now quantified**:
1. The ≤20% drawdown target is not robust to trade ordering (18% chance of breach).
2. There is a ~10–15% chance of a losing 2-year run (sampling + slippage).

**Recommendation:** size positions assuming a ~20–25% drawdown (not 10%), and treat the
−15% disaster stop as the binding risk floor rather than the expected drawdown.
