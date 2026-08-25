# Modest-Bohr Research Harness

> **North star:** every backtest number must be traceable to *(code SHA, config, data coverage, exit-reason evidence)*. Never trust a result without verifying what produced it. We paid 7 losing ML backtests and 3 rule-based iterations to learn this.

---

## 0. The three meta-failures (watch for these above all)

| # | Meta-failure | How it appeared | Where it bit |
|---|---|---|---|
| 1 | **Trusting win rate without checking calibration** | Assumed 64% win rate = model skill; it was an exit-structure artifact. Prediction→actual correlation was ≈ 0. | All of ML-001→006 |
| 2 | **Trusting a backtest without knowing which code produced it** | V2.0 log said 1.5× ATR + SMA50 exit; disk code had 3.0× ATR + no exit; backtested version was a third thing. | V2.0, "failed" at p=0.965 |
| 3 | **Trusting a stoploss without verifying it fired** | `self.dp.ohlcv()` returns a DataFrame, unpacked as a tuple → ValueError → freqtrade silently fell back to static stop. The ATR trailing "worked" for 3 experiments but never actually ran. | ML-002/003/004, V2.1 first run |

---

## 1. The 7 Gates (run in order, every experiment)

### Gate 1 — Data coverage
Every timeframe/feature must cover the FULL backtest window before running.

```bash
docker exec freqtrade_btc_bot python3 -c "
import pandas as pd
for d in ['binanceus']:
  for tf in ['1h','4h']:
    df = pd.read_feather(f'/freqtrade/user_data/data/{d}/BTC_USDT-{tf}.feather')
    print(f'{tf}: {len(df)} candles, {df[\"date\"].min()} -> {df[\"date\"].max()}')
"
```

Plus macro: `user_data/data/external/market_regime_history.json` date range. **Fail if any feature starts after the backtest timerange start.**

### Gate 2 — Config resolution
Verify what freqtrade *actually* reads, not what the config *says*.

```bash
docker exec freqtrade_btc_bot freqtrade list-data --config /freqtrade/user_data/config.json
```

**Gotcha:** `datadir` is IGNORED — freqtrade resolves the data dir from `exchange.name`. `binanceus` → `data/binanceus/`. The `data/binance/` dir is a stale orphan.

### Gate 3 — Smoke test
Run a 1-day timerange first. Catches config/flag errors in seconds instead of after 40 minutes.

### Gate 4 — Calibration (ML only, non-negotiable)
Before any full backtest of an ML strategy, verify prediction→actual correlation is meaningfully positive. If ≈ 0, STOP — no wrapper can rescue a signal that doesn't exist. (See skill pitfall P13.)

### Gate 5 — Full backtest
Canonical command (tested, working):

```bash
# Rule-based
docker exec freqtrade_btc_bot freqtrade backtesting \
  --config /freqtrade/user_data/config_baseline.json \
  --strategy BtcTrendFollowingV21Strategy \
  --timerange 20240901-20260824 --export trades --cache none \
  --notes "V2.2-xxx"

# ML (FreqAI) — NOTE --freqaimodel is REQUIRED in 2026.7
docker exec freqtrade_btc_bot freqtrade backtesting \
  --config /freqtrade/user_data/config.json \
  --config /freqtrade/user_data/config_freqai.json \
  --freqaimodel LightGBMRegressor \
  --strategy FreqaiMultiFactorBtcStrategy \
  --timerange 20250826-20260825 --export trades --cache none \
  --notes "WFA-xxx"
```

### Gate 6 — Exit-reason audit (mandatory after every run)
Pull the backtest zip and print the exit_reason distribution. **If a mechanism you expect to fire doesn't appear, it silently didn't fire.** Specifically: expect `trailing_stop_loss`/`stop_loss` when a trailing stop is configured; expect `roi` only when ROI is enabled; expect `exit_signal` only when `use_exit_signal=True`.

### Gate 7 — Reconciliation + immutability
- The freqtrade zip ALREADY contains `_config.json` + `_<Strategy>.py`. **Reconstruct "what we actually tested" from the zip, never from disk.**
- Pin `git rev-parse HEAD` to every experiment-log entry.
- After editing config via sed/scripts, `grep` the result back — we once produced an identifier `MultiFactorLightGBM-V3` out of nowhere.

---

## 2. Known API gotchas (already cost us — do not re-learn)

1. **`--freqaimodel` required** — freqtrade 2026.7 fails with "No freqaimodel set" unless `--freqaimodel LightGBMRegressor` is on the CLI. It is NOT read from config.
2. **Timerange format** — must be `YYYYMMDD-YYYYMMDD` (e.g. `20240801-20260825`). ISO/dash forms (`2024-08-01-`, `2024-08-01-2026-08-25`) are rejected.
3. **`self.dp.ohlcv()` returns a DataFrame, NOT a tuple.** Use `self.dp.get_analyzed_dataframe(pair, timeframe)` → `(DataFrame, datetime)` in `custom_stoploss`/`custom_exit`. Wrong usage throws and silently falls back to the static stoploss.
4. **`datadir` is ignored** — resolves from `exchange.name`.
5. **Lookahead-analysis** needs `entry_pricing.price_side = "other"` — pass `--config` override with `{"entry_pricing":{"price_side":"other"},"exit_pricing":{"price_side":"other"}}`.
6. **`minimal_roi = {}`** truly disables ROI; `{"0": 1}` does NOT (fires at +100%).

---

## 3. Experiment discipline

1. **One variable at a time.** ML-002 changed 3 things at once (trailing + horizon stop + SMA200 gate) and we couldn't attribute the result. Decompose via successive single-variable runs (the ML-002→003→004→005 sequence).
2. **Parameter sensitivity is a gate, not a nice-to-have.** SPEC_V2 §7.2 Stage 5 says perturb ±10-20%. We never did it — and 1.5× ATR was catastrophically wrong (inside noise band on 1h BTC). A sensitivity sweep would have caught it.
3. **Trade count is a hard floor.** <10 trades = meaningless; <30 = inconclusive. Never present a 3-trade result as a finding.
4. **Cost model is the first thing to check on a negative result.** 139 trades × 0.2% round-trip = 27.8% drag. 406 trades × 0.2% = 81% — the −82.95% run literally paid its wallet in fees.

---

## 5. Recommended skills (load these, they encode lessons we paid for)

| Skill | What it contributes to the harness | Where it would have saved us |
|---|---|---|
| **`systematic-debugging`** | *Iron Law* (no fixes without root cause), *Rule of Three* (≥3 failed fixes → question the architecture, don't iterate again) | ML-002→003→004→005 was 4 wrapper iterations on a dead model. The Rule of Three says we should have stopped at 003 and questioned the *model*, not the wrapper. Its Phase-1 "build a tight feedback loop" = Gate 3 + Gate 6. |
| **`spike`** | Throwaway experiment to falsify before build; **INVALIDATED is a successful spike** | The calibration check (corr ≈ 0) was a *successful spike* that killed the ML idea for ~free — we should have run it as the FIRST spike, before 7 backtests. Gate 4 IS a spike. Its "order by risk, most-likely-to-kill first" is the whole point. |
| **`sdlc-review`** | **Vary review lenses per round** (Artifact / Execution / Contract) — identical briefs produce correlated verdicts and duplicate findings | Our 3-reviewer dispatch used decorrelated roles (auditor/critic/alternatives), which is right — but this skill formalizes it: always give parallel reviewers *different* lenses, not the same brief. Also: reviewer must NOT edit the implementation. |
| **`test-driven-development`** | Write the falsification test *before* the build | Gate 4 calibration check and Gate 6 exit-reason audit are both "tests first". A strategy is "RED" until calibration is positive and the exit-reason audit shows the expected mechanism firing. |

**Rule of thumb:** Gate 4 = `spike` (falsify cheap). Gate 6 = `systematic-debugging` (verify what actually ran). Cross-review = `sdlc-review` (decorrelated lenses). Any "should I tweak and re-run?" after 3 failed iterations = `systematic-debugging` Rule of Three → question the architecture, not the parameters.

---

## 6. What changes in V2.2 (and all future work)

1. Gates 1–7 run before/after every experiment; exit-reason audit is mandatory.
2. Every experiment-log entry carries `git SHA` + config identifier + data coverage.
3. ML calibration check (Gate 4) is a hard stop before any ML backtest.
4. A sensitivity sweep accompanies any parameter change (stop distances, MA periods, thresholds).
5. Single source of truth for "what was tested" = the freqtrade backtest zip.

---

*Last updated: 2026-08-25. Extend with reviewer findings when the cross-review lands.*
