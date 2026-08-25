# AUM Capacity Audit — RegimeGatedTrendSMA200Strategy

**Date:** 2026-08-25
**Script:** `user_data/scripts/capacity_audit.py` (reproducibility artifact)
**Model:** square-root law of market impact — `impact = κ · σ_daily · √(Q/V)`, target ≤ 0.1% move.

---

## Venue liquidity (binanceus BTC/USDT, 1h, 2024-08 → 2026-08)

| Metric | Value |
|---|---|
| ADV (mean daily USD volume) | $782.4M/day |
| Median daily volume | $149.6M/day |
| **Median hourly volume** | **$3.4M/hour** |
| Mean hourly volume | $32.6M/hour (spike-dominated) |
| Hours with < $1M volume | 50% |
| Max single-hour volume | $2.6B (outlier spike) |
| Daily volatility (σ) | 2.32% (44% annualized) |

**The venue is heavily skewed:** mean hourly volume is ~10× the median, and half of all
hours trade under $1M. An ADV-based capacity estimate is therefore misleading.

---

## Capacity (square-root impact ≤ 0.1% price move)

| Volume reference | κ=0.1 | κ=0.3 | κ=1.0 |
|---|---|---|---|
| ADV (naive, spike-inflated) | $145.5M | $16.2M | $1.5M |
| Median daily volume | $27.8M | $3.1M | $278k |
| **Median hourly (realistic)** | **$631k** | **$70k** | **$6k** |

## Entry-time liquidity

The strategy's pullback entries land in the **thinnest** hours: median entry-hour volume
$0.11M vs $3.4M market median (**0.03×**). Half the entries occur in hours with under ~$110k
of volume — the strategy trades exactly when the book is least able to absorb size.

---

## Verdict

**Realistic deployable capital is ~$100k–$1M**, not the tens of millions naive ADV math
implies. Three factors shape this:

1. **Passive execution** — entries/exits use *limit (maker)* orders, so real market impact
   sits below the model bound (the model assumes market orders).
2. **The only market order is the −15% disaster stop**, which fired 0 times in 2 years.
3. **The binding constraint is fill probability**, not impact — on a thin venue, a large
   limit order simply won't fill at a good price.

**Scaling path:** to deploy beyond ~$1M, migrate to global Binance (or another deep venue),
which is ~10–100× more liquid than Binance.US. Within the current venue, this is correctly
positioned as a **personal / secondary-income strategy**, not an institutional one.
