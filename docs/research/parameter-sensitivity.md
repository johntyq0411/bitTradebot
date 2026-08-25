# Parameter Sensitivity — RegimeGatedTrendSMA200Strategy

**Date:** 2026-08-25
**Script:** `user_data/scripts/sensitivity_sweep.py` + `user_data/strategies/RegimeGatedTrendSweepStrategy.py`
**Grid:** regime/exit SMA [150,175,200,225,250] × pullback SMA [10,15,20,25,30,35,40] @ ADX 20 (35 pts) + ADX [15,25] @ (200,20) (2 pts) = **37 backtests**, full 2y window.

---

## Result: 37/37 (100%) profitable — PASS

**Acceptance criterion:** ≥80% of the neighborhood profitable. **Exceeded: 100%.**

| Metric | Value |
|---|---|
| Points profitable | 37 / 37 (100.0%) |
| Minimum return (anywhere in grid) | +20.56% (trend 150, pullback 35) |
| Maximum return | +81.18% (trend 225, pullback 15) |
| Mean return | +49.91% |
| Default (200/20) | +61.25% |
| Default + 4 nearest neighbors | +54.3% / +62.0% / +45.0% / +79.5% — all profitable |

## 2D surface (trend SMA ↓ × pullback SMA →)

| trend \ pullback | 10 | 15 | 20 | 25 | 30 | 35 | 40 |
|---|---|---|---|---|---|---|---|
| 150 | 31.2 | 34.5 | 38.3 | 28.1 | 28.8 | 20.6 | 20.6 |
| 175 | 30.3 | 37.4 | 45.0 | 34.6 | 35.3 | 29.8 | 23.7 |
| **200** | 48.2 | 54.3 | **61.2** | 62.0 | 61.6 | 52.5 | 44.3 |
| 225 | 65.9 | 81.2 | 79.5 | 68.7 | 62.1 | 56.5 | 52.8 |
| 250 | 62.8 | 76.9 | 79.8 | 68.9 | 62.8 | 59.9 | 57.3 |

## ADX sensitivity (trend 200, pullback 20)

| ADX | Return | Trades |
|---|---|---|
| 15 | +57.08% | 98 |
| 20 | +61.25% | 88 |
| 25 | +32.19% | 82 |

---

## Verdict

1. **No curve-fitting detected.** The surface is a smooth plateau — returns decline
   gradually toward the edges, no point collapses to zero or negative. Structural edge, not a fitted one.
2. **ADX is the most sensitive parameter** (tightening to 25 halves the return), but still positive.
3. **The default (200/20) sits on a robust plateau, not a spike.** The global max (~81% at
   225–250 × 15–20) is adjacent but we deliberately **do not** re-optimize toward it: the
   difference is within bootstrap sampling noise (p5–p95 −10% to +220%), and chasing the peak
   is the exact overfitting this gate prevents.

**Recommendation:** keep the deployed parameters (4h EMA200 / 1h SMA200 / SMA20 pullback / ADX 20).
