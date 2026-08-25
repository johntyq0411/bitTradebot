# Strategy Critique — Modest-Bohr V2.2 Direction

**Role:** Independent Strategy Critic (skeptic)
**Date:** 2026-08-25
**Subject:** Proposed V2.2 changes to `BtcTrendFollowingV21Strategy.py`
**Verdict up front:** ❌ **Do NOT proceed with V2.2 as specified.** Both proposed changes address *symptoms* (trade count, whipsaw) while leaving the *disease* (a statistically non-existent entry edge) untouched — and both push drawdown in the wrong direction, directly against the stated `DD ≤ 20%` goal.

---

## TL;DR

| Claim in V2.2 proposal | Skeptic's assessment |
|---|---|
| "Fee churn is the problem" | Fee drag is *real* (139 × 0.2% = 27.8%) but it is a **symptom**, not the disease. A strategy with zero edge loses money to *any* cost. |
| "Widen SMA50 → SMA100 to reduce churn" | ❌ **Wrong fix.** Converts churn into larger per-trade drawdowns. DD is already 38.5%; widening the structural exit makes it worse. |
| "Drop the 1.5× ATR trailing stop entirely" | ⚠️ **Half right, half wrong.** Delete the *1.5× ATR* (it is inside noise — 0.5–0.7% of price) but **replace** it with 2.5–3× ATR (capped at 2% per Antigravity), don't delete trailing entirely. |
| "Keep bull gate + score ≥4/6 + higher-high entry" | ❌ **This is the actual failure.** Win rate 25%, PF 0.98, p=0.93 = the entry is a coin flip. No exit tuning fixes a non-existent entry edge. |
| "This reaches positive expectancy + DD ≤ 20%" | ❌ **No.** It lost −2.83% in a +33% market. A trend-follower that can't profit in a 2-year +33% window has a broken premise. |

---

## Q1 — Is "fee churn" the dominant problem, or a symptom of a deeper entry-timing flaw?

**Answer: It is a symptom. The disease is a zero-edge entry, and the team is optimizing the wrong variable.**

The arithmetic that looks like "fee churn" is actually "no edge × any cost":

- **Fee model is confirmed, not exaggerated:** 139 round-trips × 0.2% (0.1% per side) = **27.8%** fee drag, exactly matching the reported figure. Add the ~0.05–0.1% slippage from SPEC_V2 §6.1 and the true per-trade breakeven threshold is **~0.25–0.3%**.
- **But the strategy's pre-cost expectancy is ~zero.** Profit Factor 0.98 means gross profit ≈ gross loss *before* fees. A coin-flip strategy is mathematically guaranteed to bleed out under any positive cost — the cost isn't the problem, the absence of edge is. If the entry had real predictive power, 139 trades would be *harvesting*, not "churn."
- **The win/loss decomposition confirms the entry is the failure, not the exits:**
  - 25% win rate (35/139) with a **3.03:1 payoff ratio** (avg win +3.30% ÷ avg loss −1.09%).
  - Breakeven at 25% win rate requires exactly 3:1 payoff. The strategy sits *precisely* on the breakeven line: `0.25 × 3.30 − 0.75 × 1.09 = +0.0075%/trade ≈ 0`.
  - The payoff ratio (3:1) is actually **good** — it proves the *exits* do their job (cut losses near −1%, let winners run to +3.3%). The entire deficit is that **75% of entries are wrong.** The exits are not the problem; the entries are.
- **Why the entry is structurally late:** the higher-high breakout + "score ≥ 4/6 in a bull regime" is *buy strength after the move has already happened.* In BTC's choppy 1h price action, a higher-high trigger means buying the top of each micro-swing, then getting stopped on the pullback — the textbook "buy high, sell low" pattern that produces a 25% win rate.

**Conclusion:** Fee churn is the *downstream symptom* of (a) a coin-flip entry that fires too often and (b) exits that cycle positions quickly. Reducing trade count (V2.2's stated goal) treats the *count*, not the *quality*. Fewer trades × zero edge = slower bleed, not profit.

---

## Q2 — Is widening SMA50 → SMA100 the right fix, or does it convert churn into larger drawdowns?

**Answer: It converts churn into larger drawdowns. It is the wrong fix and actively contradicts the DD ≤ 20% goal.**

- **The structural exit is the strategy's last defense against trend reversals.** Widening it from SMA50 (~2 days) to SMA100 (~4 days) means riding deeper into every adverse move before the exit fires. The losing trades currently averaging −1.09% will get *larger*, not smaller.
- **Max drawdown is already 38.5%** — nearly 2× the 20% target. The single change most likely to push it higher is a *slower structural exit*. V2.2 is choosing the one knob that moves DD in the wrong direction.
- **The V2.0 post-mortem already diagnosed this:** experiment-log V2-005 explicitly noted the structural exit "lags significantly — by the time price crosses below SMA50, most of the drawdown has already happened." Widening the period makes the lag *worse*.
- **What actually happens in practice:** with SMA100, the binding exits on losers become the 48-candle time stop and the −5% disaster stop, not the structural exit. V2.2 effectively redefines the strategy as "hold losers up to 48 candles or −5%." That is *worse* risk management, not better.
- **Widening the exit does nothing to the entry.** The proposal treats 139 trades as the problem, but the problem is that those 139 trades have no edge. Fewer trades with the same edge is just a slower version of the same −2.83% (likely landing near −1% to −2%, still negative, with higher DD).

**Conclusion:** No. SMA100 trades fee churn for tail risk. Expected outcome: modestly lower churn, *higher* max drawdown, still-negative expectancy. This is swapping one failure mode for another, and it directly violates the project's own risk bar.

---

## Q3 — Should the trailing stop be dropped entirely, or retuned (2.5–3× ATR, or ATR capped at 2%)?

**Answer: Retune, don't delete. Dropping the 1.5× ATR is correct; dropping trailing entirely is an overcorrection.**

- **Deleting 1.5× ATR is correct** — and the team's own diagnosis is right that it was "inside noise." 1.5× ATR on 1h BTC ≈ **0.5–0.7% of price**, which is a single normal hourly wiggle. It should never have been a stop. The 406-trade / −82.95% result is the expected outcome of a stop that fires on every candle.
- **But the −82.95% result is *not* evidence that trailing stops are bad.** It is evidence that *a misconfigured stop* is bad. The team is committing a classic overcorrection: "the stop was too tight, so remove stops entirely" instead of "the stop was too tight, so widen it."
- **Two additional confounders the team should separate before blaming "trailing":**
  1. **Re-entry churn:** 406 trades over ~2 years ≈ 0.56/day strongly suggests stop-out → immediate re-entry into the same trend (no cooldown, no re-entry filter). Many of those 406 trades are the *same signal re-entering*, not 406 independent signals. The real fix is a re-entry cooldown, not deleting the stop.
  2. **Winner protection:** the trailing stop is the *only* mechanism that lets the +3.30% avg win / +7.43% ML runner happen. Without *any* trailing, winners are protected only by the lagging structural exit and the −5% backstop — open profit gets given back on the structural-exit lag.
- **What the Antigravity / multifactor methodology actually prescribes (and what V2.2 should adopt):**
  - **2.5× ATR** dynamic stop (SKILL §B/C): on 1h BTC this is ≈ **1.2–1.8% of price**, outside noise, and — notably — closely matches the strategy's own observed avg loss of −1.09%. It is the natural width for this market.
  - **Cap ATR at `min(atr, current_rate × 0.02)`** so the stop can't widen during volatility spikes (SKILL Part 2).
  - **Bound the stop to `max(min(atr_stop, −0.015), −0.06)`** — i.e., between 1.5% and 6%.
  - **Hard rule:** never run `trailing_stop = True` and `use_custom_stoploss = True` simultaneously (SKILL Part 2). V2.1 uses a manual ATR trail in `custom_stoploss`, which is fine, but the team should be aware of the conflict if they reintroduce any trailing.

**Conclusion:** Delete 1.5× ATR *as configured*, but replace it with a **2.5–3× ATR trailing stop capped at 2% of price**, plus a re-entry cooldown. Dropping trailing entirely sacrifices the strategy's single genuinely-good property (3:1 payoff via "let winners run") and is not justified by the evidence.

---

## Q4 — What does 25% WR, PF 0.98, and p = 0.93 tell us about whether the entry edge is real?

**Answer: The entry edge is statistically indistinguishable from zero. It is not "weak," it is absent.**

- **p = 0.93 is essentially the null hypothesis.** It means: *if the strategy had no edge whatsoever*, the probability of observing this result (or better) is 93%. You cannot reject "this is random" at any meaningful threshold. Trading requires p < 0.05 (arguably p < 0.01 given multiple-testing); p = 0.93 is about as null as a result can be. Note that V2.0's earlier run was p = 0.965 — the team has now produced *two consecutive* results indistinguishable from noise.
- **PF 0.98 ≈ 1.0 confirms breakeven-before-costs.** Profit factor must be meaningfully > 1.0 *after* costs to be deployable (typically ≥ 1.3–1.5). At PF 0.98 pre-cost, the strategy is a guaranteed post-cost loser by construction.
- **25% WR is not disqualifying on its own** — legitimate trend-followers run 30–40% WR with big payoff ratios. But 25% WR is only viable at ≥ 3:1 payoff, and the strategy's payoff is **exactly 3.03:1** — the internal numbers are self-consistent and they all land *precisely on the breakeven line*. There is zero margin for the 0.2%+ costs, which is exactly why the net is negative.
- **The deeper read:** the only *good* property of this strategy — the 3:1 payoff asymmetry — is an artifact of the **exits** (cut at −1%, run to +3.3%), not the **entries**. The entries carry no information (p=0.93). This is the single most important conclusion for the team: **no amount of exit tuning can rescue an entry with no edge.** V2.2 is, in its entirety, exit tuning.
- **Not a sample-size problem:** 139 trades with p=0.93 is not "we need more data" — more trades from the same entry logic will simply converge toward breakeven-minus-costs. The signal has no information, not insufficient information.

**Conclusion:** The entry edge is not real. PF 0.98 (breakeven) and p=0.93 (null) are two ways of saying the same thing. V2.2 changes exits, which cannot fix this.

---

## Q5 — Given it lost in a +33% bull market, is there ANY scenario where this design reaches the goal (positive expectancy, DD ≤ 20%)?

**Answer: With the current entry logic unchanged — no. V2.2 as proposed has no path to the goal. A different *entry* design might, but that is a redesign, not V2.2.**

- **The broken premise:** the 2-year window delivered +33% net BTC appreciation, and the strategy lost −2.83% in it. Trend following only earns in trends; if the *strongest 2-year window available* can't produce a profit, the entry/exit logic fundamentally cannot capture trends. This is not a parameter problem — it's a premise problem.
- **The bull-regime gate doesn't save it.** V2-002 shows the bull regime spans only ~190 days of the 2 years, and even those segments are too choppy on 1h for a breakout-chaser. The "higher-high" entry buys the top of each micro-swing, so the few genuine trends are entered late and given back.
- **There is a structural tension the design cannot resolve:** the exits that *reduce* DD (fast structural exits) are the same ones that *increase* churn (fees), and the exits that *reduce* churn (SMA100) are the same ones that *increase* DD. With a zero-edge entry, the strategy cannot win on both axes simultaneously. You cannot tune exits into profitability.
- **The one honest scenario that *could* reach the goal is a different entry hypothesis**, not V2.2:
  1. **Pullback-zone entries instead of breakout entries** (Antigravity: `ema50×0.995 ≤ close ≤ ema20×1.005` inside an uptrend, RSI 45–60) — buy the *dip*, not the top. This directly attacks the 75%-wrong-entry problem.
  2. **A true higher-timeframe macro filter** (4h EMA200) instead of the 1h SMA200. The project's own V2-002 note already flagged that "200-period SMA on 1h is ~8 days — may be too short for macro trend detection." V2.2 keeps the 1h SMA200 — a known weakness it declines to fix.
  3. **2.5× ATR capped stops** to keep DD within 20% while still letting winners run.
  - But note: this is the *multifactor_trading* strategy, not V2.2. It is a rewrite of the entry layer, which is precisely what V2.2 refuses to touch.

**Conclusion:** No scenario reaches the goal with V2.2's two changes. The only viable path is replacing the entry model (pullback-in-uptrend + HTF macro filter), which is a different strategy — and even that should be validated against a null control before trust is extended.

---

## Critique of V2.2 Against the Antigravity / `multifactor_trading` Methodology

The project already owns a documented, institutional-grade methodology (`.agents/skills/multifactor_trading/SKILL.md`), and V2.2 is moving **away from it** on every axis that matters:

| Antigravity prescription | V2.1 / V2.2 reality | Verdict |
|---|---|---|
| **4h EMA200 macro filter** (`close > ema200_4h`), `startup_candle_count = 800` | 1h SMA200 (~8-day) bull gate; no HTF layer | ❌ V2.2 keeps the known-too-short 1h filter |
| **Pullback-zone entry** (`ema50×0.995 ≤ close ≤ ema20×1.005`) — *don't chase breakouts* | Higher-high breakout entry (chases breakouts) | ❌ V2.2 keeps the exact entry Antigravity warns against |
| **2.5× ATR stop, capped at 2% of price**, bounded [−1.5%, −6%] | 1.5× ATR (broken) → V2.2 deletes trailing entirely | ❌ Wrong direction — retune, don't delete |
| **Macro → TA (setup) → Micro (trigger)** layering | Everything collapsed into one 1h signal score | ❌ All trigger, no setup layer |
| **Funding-rate quality filter** (`0 < funding < 0.001`) | Not used | ⚠️ Missed, minor |
| **Never `trailing_stop` + `custom_stoploss` together** | custom_stoploss manual ATR trail (OK) | ⚠️ Watch if trailing reintroduced |

**The single most important divergence:** Antigravity's core TA insight is *"price in a pullback zone … prevents chasing breakouts."* V2.1/V2.2 does the **opposite** — it *only* enters on breakouts (higher-high). Given that the observed failure is a 25% win rate driven by late, wrong entries, the methodology's central warning is the most plausible explanation of the failure, and V2.2 does nothing about it.

---

## Data-Integrity Flags (things the team should reconcile before spending another iteration)

As the skeptic, I flag three inconsistencies in the numbers as presented — they matter because the team is making decisions on them:

1. **The headline P&L does not reconcile.** "+25% gross" vs. the stated decomposition `35 × +3.30% − 104 × −1.09% = +2.1%` — these do not agree (even compounding the sequence lands near ~0, not +25%). One of these figures is wrong, or the "+25% gross" is measured on a different basis than the per-trade averages. **The team should reconcile this before it drives another design decision.**
2. **The 406-trade / −82.95% result likely double-counts re-entry churn.** ~0.56 trades/day over 2 years is consistent with stop-out → immediate re-entry into the same trend, not 406 independent signals. Concluding "trailing stops are bad" from this is unsafe; the confounder is *no re-entry cooldown*.
3. **The ML narrative is internally inconsistent with the pivot.** The experiment log (WFA-1Y-ML-001/002) records a *"real"* 64.1% win-rate signal with a broken wrapper, while the project overview now states directional ML was "proven to have no predictive edge (calibration ~0)." Both cannot be cleanly true. **Before abandoning ML for rule-based V2.2, the team should resolve which claim is correct** — if the 64% signal was real, the wrapper fixes (ML-002/003) are a strictly better investment than V2.2.

---

## Final Recommendation

**Abandon V2.2 as specified. Do not spend a backtest on it.**

The two changes (widen SMA50→SMA100; delete the trailing stop) are cosmetic — they adjust trade count and stop placement while leaving the entry, the only thing that determines whether this strategy can ever be profitable, untouched. The evidence says the entry has **no edge** (p = 0.93, PF 0.98, −2.83% in a +33% market), and both changes push drawdown further from the 20% target.

Concrete path forward, in order:

1. **Stop iterating exits. Prove or disprove the entry edge first.** Run a **null-entry control**: same exits, random entries at the same frequency, over the same window. If the real entry cannot beat the random entry, the entry has no edge and no exit work will ever matter. This is one cheap backtest that settles the entire rule-based line.
2. **If rule-based continues, replace the entry — don't tune it.** Adopt the Antigravity pullback-zone entry (`ema50×0.995 ≤ close ≤ ema20×1.005`, RSI 45–60) under a **4h EMA200** macro filter, with a **2.5× ATR stop capped at 2% of price** and a **re-entry cooldown**. This is a *different strategy*, not V2.2 — and it directly attacks the 25%-win-rate root cause instead of the trade count.
3. **Resolve the ML contradiction before choosing sides.** Reconcile "ML signal real (64% win)" vs. "ML proven no edge (calibration ~0)." If the 64% signal survives scrutiny, the wrapper-fixed ML path (ML-002/003) is a better allocation of effort than any further rule-based iteration.
4. **Set a hard kill criterion and honor it.** If, after the entry redesign, the strategy cannot (a) beat a random-entry control *and* (b) keep max DD ≤ 20% in walk-forward, shut down the rule-based trend-following line permanently. Two consecutive p > 0.9 results (V2.0: 0.965, V2.1: 0.93) are already a strong signal that this family of breakout-chasing rules has no exploitable information in this market.

**Bottom line:** V2.2 would be the third consecutive iteration that optimizes exits while the entry — a coin flip — goes unexamined. The honest, evidence-based move is to either prove the entry is worthless (null control) or replace it outright; not to ship V2.2.
