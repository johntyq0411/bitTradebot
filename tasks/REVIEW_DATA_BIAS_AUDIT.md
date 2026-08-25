# Data & Bias Audit — Modest-Bohr

**Role:** Independent Data & Bias Auditor
**Date:** 2026-08-25
**Scope:** Verify the evidence behind three decision-driving conclusions: (1) the FreqAI LightGBM model has no predictive edge, (2) the `custom_stoploss` bug broke the ATR trailing stop, and (3) the V2.1 rule-based strategy is the fallback path. Also verify data-directory resolution, V2.1 lookahead bias, and the ML-001→006 experiment-log record.
**Method:** Read all strategy/config/doc files, inspected the live freqtrade 2026.7 container (API signatures + source), and reconstructed *what actually ran* by extracting strategy code and results from every backtest ZIP (not from disk files, which can drift).

---

## Executive Summary

| # | Question | Verdict |
|---|---|---|
| Q1 | "No predictive edge" supported by calibration evidence? | **UNABLE-TO-VERIFY** (evidence not archived; conclusion independently corroborated) |
| Q2 | `custom_stoploss` bug correctly diagnosed? | **PASS** (confirmed at the code, API, and exit-reason level) |
| Q3 | Data-directory resolution correct? | **PASS** (confirmed in source + live logs) |
| Q4 | V2.1 free of lookahead bias? | **PASS** (verified by independent code inspection) |
| Q5 | ML-001→006 log entries consistent & correctly interpreted? | **FAIL** (log is incomplete and mis-attributes ML-002) |

Key cross-cutting finding: **the project's own post-mortem (RESEARCH_HARNESS.md, REVIEW_ALTERNATIVES.md) is broadly correct, but the primary evidence trail is partly un-archived** — the "calibration ≈ 0" numbers and the "lookahead-analysis has_bias=No" output exist nowhere in the repo as reproducible artifacts. The conclusions survive independent verification via the backtest ZIPs, but the *specific evidence the team cites* is thinner than the narrative implies.

---

## Q1 — Is "the FreqAI LightGBM model has no predictive edge" supported by the calibration evidence?

**Verdict: UNABLE-TO-VERIFY** (the calibration evidence is not reproducible from the repo; the conclusion is nonetheless independently corroborated by the backtest record).

### Evidence

**What the project claims (from docs):**
- `docs/RESEARCH_HARNESS.md:11` — "Prediction→actual correlation was ≈ 0."
- `docs/RESEARCH_HARNESS.md:47` — "verify prediction→actual correlation is meaningfully positive. If ≈ 0, STOP."
- `tasks/REVIEW_ALTERNATIVES.md:72` — "short-horizon direction (3h/12h/24h) is ~unpredictable (correlation ≈ 0), and macro features had ~zero importance *for direction*."

**What actually exists in the repo for the calibration claim:**
1. **Exactly one concrete number, in a code comment.** `FreqaiMultiFactorBtcV6Strategy.py:17` — "3h raw BTC return is pure noise (calibration corr **-0.017**, macro features near-zero importance)."
2. **No 12h or 24h correlation value is documented anywhere.** A repo-wide search for correlation terms (`.corr(`, `corrcoef`, `spearman`, `pearsonr`, `calibrat`) returns *only* the V6 docstring. There is no calibration script, no CSV, no notebook, no JSON output.
3. **No persisted feature-importance artifact.** The configs set `plot_feature_importances: 1` (config_freqai*.json:24), which only generates per-training-window HTML plots under `user_data/models/`; there is no aggregate feature-importance table backing "macro ≈ zero importance."

**The -0.017 number is ambiguous.** The V6 docstring describes it as "3h raw BTC return is pure noise" — i.e. it reads as the *raw-return autocorrelation / noise floor*, not necessarily the *model's* prediction→actual correlation. These are different statistics, and conflating them is itself a bias risk (see Additional Flag #5).

**Independent corroboration (from backtest ZIPs, all extracted & verified):**

| Run | Trades | Net P&L | Win rate | Profit factor |
|---|---|---|---|---|
| ML-001 (3h) | 39 | −25.41% | 64.1% | 0.57 |
| ML-002 (3h) | 3 | +7.50% | 66.7% | 17.57 (noise) |
| ML-003 (3h) | 80 | −31.57% | 41.3% | 0.39 |
| ML-004 (3h) | 44 | −39.85% | 11.4% | 0.20 |
| ML-005 (3h) | 92 | −31.63% | 37.0% | 0.61 |
| ML-006a (12h) | 96 | −48.71% | 63.5% | 0.52 |
| ML-006b (24h) | 96 | −33.92% | 67.7% | 0.68 |

- **Every horizon lost money.** Critically, the horizon test (the experiment designed to test "is the signal learnable at a longer horizon?") got *worse* at 12h (−48.71%) and 24h (−33.92%) than at 3h. This is consistent with "no learnable directional edge at any horizon."
- **The high win rates (64–68%) are consistent with an exit-structure artifact, not skill.** ML-001 exit reasons: 24 ROI (avg +1.67%, capped) vs 13 stop_loss (avg −5.19%, full). A model with zero linear correlation but a +1% entry threshold and a capped-ROI/uncapped-stop wrapper produces exactly this pattern: many small winners, few large losers. So "correlation ≈ 0" and "64% win rate" are not in contradiction — the win rate was never evidence of edge.

**Assessment:** The *conclusion* ("no predictive edge") is well-supported by the 7-run backtest record, especially the horizon test. But the *calibration evidence cited for it* (correlation ≈ 0 at 3h/12h/24h; macro near-zero importance) is not archived: only one ambiguous number (−0.017) survives, in a comment. A skeptical auditor cannot reproduce the calibration from the repo. This is a documentation/integrity gap, not a demonstrated error — but the team is making a capital decision ("abandon directional ML") partly on numbers that aren't on disk.

---

## Q2 — Was the `custom_stoploss` bug correctly diagnosed?

**Verdict: PASS** (confirmed at four independent levels: API signature, API source, the code that actually ran, and exit-reason evidence).

### Evidence

**1. The API claim is correct (verified in the live freqtrade 2026.7 container):**
```
DataProvider.ohlcv(pair, timeframe, ...)            -> pandas.DataFrame
DataProvider.get_analyzed_dataframe(pair, timeframe) -> tuple[DataFrame, datetime]
```
And `ohlcv()`'s source shows that **in backtest mode it returns an empty `DataFrame()`** (`return DataFrame()` for non-dry-run/non-live runmodes). So in a backtest, `dataframe, _ = self.dp.ohlcv(...)` iterates a zero-column DataFrame and raises `ValueError: not enough values to unpack (expected 2, got 0)`.

**2. The failure is silently swallowed (verified in container source).** Freqtrade wraps strategy callbacks in `strategy_safe_wrapper` (`strategy/strategy_wrapper.py:31`), which catches the exception, logs a warning, and returns `default_retval` — for `custom_stoploss` that default is the strategy's static stoploss. The backtest completes with no error; the ATR trailing stop simply never produces an exit. ("Silently" is slightly imprecise — it *is* logged as a warning — but it is silent from the result's perspective, which is what mattered.)

**3. The buggy line was in the code that actually ran (extracted from the ZIPs, not disk):**

| ZIP (run) | Strategy line found in ZIP |
|---|---|
| `backtest-result-…_06-16-46` (ML-002) | `126: dataframe, _ = self.dp.ohlcv(pair, self.timeframe)` ❌ |
| `backtest-result-…_06-17-50` (ML-003) | `123: dataframe, _ = self.dp.ohlcv(pair, self.timeframe)` ❌ |
| `backtest-result-…_06-19-51` (ML-004) | `123: dataframe, _ = self.dp.ohlcv(pair, self.timeframe)` ❌ |
| `backtest-result-…_07-15-15` (V2.1 first run) | `167: dataframe, _ = self.dp.ohlcv(pair, self.timeframe)` ❌ |
| `backtest-result-…_07-18-56` (V2.1 fixed run) | `167: dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)` ✅ |

This matches the claim exactly: **the bug was present in ML-002, ML-003, ML-004, and the first V2.1 run** (and was fixed before the second V2.1 run). ML-005/V6/V7 have no `custom_stoploss` at all (they revert to ML-001's ROI+static-stop wrapper), so they are not affected — consistent with "ML-002 through ML-004."

**4. Exit-reason evidence confirms the trailing stop never fired:**
- ML-002: exits = 1 `exit_signal` + 2 `horizon_stop`; **0 `trailing_stop_loss`.**
- ML-003: 75 `horizon_stop` + 3 `stop_loss` + 2 `exit_signal`; **0 `trailing_stop_loss`.**
- ML-004: 24 `horizon_stop` + 15 `stop_loss` + 5 `exit_signal`; **0 `trailing_stop_loss`.**
- V2.1 first run (broken): **139 `exit_signal` (structural), 0 trailing** → −2.83%.
- V2.1 fixed run: **389 `trailing_stop_loss`** + 17 `exit_signal` → −82.95% (the 1.5× ATR now actually fires and whipsaws 406 trades).

The contrast between the two V2.1 runs (0 vs 389 trailing exits) is the cleanest possible demonstration: the fix changed the exit mechanism from "never fires" to "fires 389 times."

**Assessment:** The diagnosis is technically precise and empirically proven. The only nitpick is "silently" (it logs a warning), and a note that the diagnosis was already self-documented by the team in `RESEARCH_HARNESS.md:13` (meta-failure #3) and API gotcha #3 (line 84) — this audit independently confirms it.

---

## Q3 — Is the data-directory resolution correct?

**Verdict: PASS** (confirmed in freqtrade source and in the live logs).

### Evidence

**Config on disk:**
- `config.json:36` — `"exchange": {"name": "binanceus"}`
- `config.json:79` — `"datadir": "/freqtrade/user_data/data/binance"`

**How freqtrade 2026.7 actually resolves the data dir (container source, `configuration/directory_operations.py:create_datadir`):**
```python
def create_datadir(config, datadir=None):
    folder = Path(datadir) if datadir else Path(f"{config['user_data_dir']}/data")
    if not datadir:
        exchange_name = config.get("exchange", {}).get("name", "").lower()
        folder = folder.joinpath(exchange_name)
    ...
```
And the caller (`configuration.py:212`): `create_datadir(config, self.args.get("datadir"))` — it passes the **CLI `--datadir` flag**, *not* the config file's `datadir` key. The backtest commands in `PROJECT_OVERVIEW.md` §7 do **not** pass `--datadir`, so the flag is `None`, the exchange-name branch runs, and the effective data dir is `user_data_dir/data/binanceus`.

**Live confirmation:** `user_data/logs/freqtrade.log*` shows `Using data directory: /freqtrade/user_data/data/binanceus ...` for every recent run (08-23 through 08-25). No run resolved to `…/binance`.

**The two directories:**
- `data/binance/` — 1h feather 516,618 B (08-24 23:37), 4h 142,250 B (08-25 01:13), plus a stale `markets.json` (08-22).
- `data/binanceus/` — 1h feather 517,026 B (08-25 12:21), 4h 145,234 B (08-25 12:21).

`binanceus/` is newer and slightly larger (more candles) in both timeframes. `binance/` is a **stale orphan** — last written ~11h before the authoritative dir, with fewer candles.

**One precision note on the claim's mechanism:** freqtrade does *not* "append the exchange name to the configured `datadir`." It **ignores the config `datadir` key entirely** and appends the exchange name to `user_data_dir/data` (the default). The *conclusion* is identical either way — `binanceus/` is authoritative, `binance/` is stale, and the config `datadir` setting is dead. But the precise cause is worth stating correctly, because someone may later "fix" the config `datadir` key and be surprised it still does nothing. The correct fix is to pass `--datadir` explicitly or keep the default (exchange-name-resolved) path.

---

## Q4 — Is the V2.1 strategy free of lookahead bias?

**Verdict: PASS** (verified independently by reading `BtcTrendFollowingV21Strategy.py`).

### Evidence (line-by-line inspection)

**No forward-shift anywhere.** There is no `shift(-N)` in the file. Every structural/rolling computation is backward-looking or explicitly `shift(1)`-deferred:

- `sma_200_slope = sma_200 - sma_200.shift(24)` (L63) — compares current SMA to 24 candles ago. ✅
- `roc_24 = (close - close.shift(24)) / close.shift(24)` (L68) — trailing. ✅
- `hh_20 = high.rolling(20).max().shift(1)`; `lh_20 = low.rolling(20).min().shift(1)`; `hh_5 = high.rolling(5).max().shift(1)` (L78–80) — the "prior N candles, excluding current" is done correctly via `.shift(1)`. ✅
- `sig_higher_high = close > hh_20` (L90) — compares current close to the *prior* 20-bar high, not the current bar's high. ✅
- `sig_momentum` uses `rsi > rsi.shift(1)` (L96) — trailing. ✅
- Entry breakout `close > hh_5` (L136) uses the already-shifted `hh_5`. ✅
- `custom_stoploss` uses `get_analyzed_dataframe(...).tail(15)` (L167) — during backtesting this returns only data up to the current candle. ✅
- `custom_exit` uses `trade.open_date_utc` and `current_time` (L197) — no future data. ✅

**None of the classic lookahead patterns are present:** no `df.iloc[-1]` in populate functions, no full-column `df.mean()/min()/max()`, no `resample`, no plain `merge()` for informative pairs (there is no informative pair here), no `merge_informative_pair()` misuse.

**Caveat on the "tool reported has_bias=No" claim:** I could **not** independently verify that the lookahead-analysis tool was run. The string `has_bias` appears **nowhere** in the repo, and `freqtrade.log*` contains no lookahead-analysis run. (Freqtrade's built-in `lookahead-analysis` was also flagged in RESEARCH_HARNESS.md:86 as requiring a config override the team may or may not have applied.) The *claim* that the tool reported "No" is therefore unverified; however, the *substantive question* — is the strategy free of lookahead bias — is answered **yes** by direct code inspection, which is the more reliable test for this simple rule-based strategy.

---

## Q5 — Are the ML-001 through ML-006 experiment-log entries internally consistent and correctly interpreted?

**Verdict: FAIL** — the log is **incomplete** (only ML-001 and ML-002 are logged) and contains a **material mis-attribution** for ML-002.

### Evidence

**1. The log is missing five of seven runs.** `docs/experiment-log.md` ends at `WFA-1Y-ML-002` (line 223). ML-003, ML-004, ML-005, ML-006a, and ML-006b are **not logged at all**, despite all five having strategy files (V3–V7) and backtest ZIPs on disk. A reader of the log alone would believe only two ML experiments ever ran. (Their results live only in the ZIPs and in passing mentions in the post-mortem docs.)

**2. ML-001 numbers are internally consistent; its interpretation is stale.** The log's ML-001 entry (39 trades, −25.41%, 64.1% win, exits 24 roi / 13 stop_loss / 2 exit_signal, avg win +1.61% vs avg loss −4.84%) reconciles exactly with the ZIP (avg win +1.67%, avg loss −5.19%). But the log's verdict — *"ML signal confirmed real (64.1% win vs ~50% random)"* (line 187) — was **never corrected in place** after the calibration showed ≈0 correlation. A reader trusting `experiment-log.md` reaches the *opposite* conclusion from the project's current position. This contradiction was independently flagged by the sibling review `REVIEW_STRATEGY_CRITIQUE.md:127` ("The ML narrative is internally inconsistent with the pivot").

**3. ML-002 mis-attributes its result to a fix that never ran.** The log (lines 215–217) states: *"Fixes 1+2 WORK: winner ran to +7.43% — ATR trailing let it run."* But the ZIP's exit reasons show the +7.43% winner exited via **`exit_signal`** (held 7d 20h), and ML-002 produced **zero `trailing_stop_loss` exits** (see Q2). The winner ran because `minimal_roi = {}` was disabled and the exit signal fired late — **not** because the ATR trailing stop worked. Fix 1 (ATR trailing) was therefore *not* validated by ML-002; it was broken in that run. The correct reading is: "Fix 2 (horizon stop) and disabling ROI worked; Fix 1 remains unvalidated (broken)."

**4. ML-002's Sharpe/Calmar in the log do not reconcile with the ZIP.** The log reports "Sharpe 1.07, Calmar 7.6." The ZIP's TOTAL row reports Sharpe **0.1145** and Calmar **86.97**. (Max DD 0.45% and p=0.41 do reconcile.) The ~10× Sharpe gap is unreconciled — likely a different Sharpe definition, but it is not documented, and on a 3-trade sample any of these numbers is meaningless.

**5. "7 ML backtests, all losing" is imprecise.** `REVIEW_ALTERNATIVES.md:5` and `RESEARCH_HARNESS.md:3` assert all 7 lost money. ML-002 was nominally **+7.50%** (on 3 trades). The honest phrasing is "6 of 7 lost money; ML-002 was nominally positive on 3 trades (statistically meaningless)." The imprecision matters because ML-002 is repeatedly cited as proof that "wrapper fixes work," when it proves almost nothing at n=3.

---

## Additional Data-Integrity & Bias Flags

**F1 — The "macro ≈ zero importance" finding is likely confounded by constant-fill.** All macro features are merged on a daily `date_key` and missing values are replaced with *constants* (`FreqaiMultiFactorBtcStrategy.py:76-82`): `fear_and_greed→50`, `funding_rate→0.0001`, `open_interest→0`, `long_short_ratio→1.0`, `stablecoin_supply→150e9`, `dxy→100`, `spy→500`. Since macro data was only backfilled to 755 days (and OI + L/S to 365 days per `PROJECT_OVERVIEW.md` §6), the earlier training windows contain **zero-variance constant macro features**, which mechanically produce near-zero feature importance for those periods. "Macro features have no predictive value" may really be "macro features are missing for the early data and were filled with constants." This matters directly for the team's decision to repurpose macro for regime classification — that hypothesis is *not* refuted by the direction-model importance result.

**F2 — Same-day macro applied to all 24 hourly candles (minor intraday lookahead).** The merge joins macro on `date` (daily). A day's macro value is applied to *every* hourly candle of that day, including the 00:00 candle. If `market_regime_history.json` holds end-of-day values, the earliest candles of each day use a same-day (slightly future) value. Low materiality at daily frequency, but it should be documented before the regime-classifier path reuses the same merge.

**F3 — Diagnostic scripts hardcode the orphan data path.** `user_data/scripts/v2_diagnostic.py:10` and `scripts/ATR_simulation.py:3` read `/freqtrade/user_data/data/binance/BTC_USDT-1h.feather` — the **stale** dir — not `binanceus/`. Any conclusion drawn from those scripts (e.g., ATR sizing, entry-candidate counts) used older data.

**F4 — The "+25% gross edge" figure does not reconcile with V2.1's own numbers.** `REVIEW_ALTERNATIVES.md:5,17` cites a "+25% gross" edge destroyed by fees. The V2.1 Stage-1 ZIP shows Profit Factor **0.976** (gross ≈ breakeven) and a decomposition of 35 wins × +3.30% − 104 losses × −1.09% ≈ +0.2%, not +25%. This was already flagged by the sibling `REVIEW_STRATEGY_CRITIQUE.md:125`; it remains unreconciled and is being used to justify "cut trade frequency to preserve the +25% edge."

**F5 — The −0.017 calibration number is ambiguous and possibly misread.** It is phrased as "3h raw BTC return is pure noise" — i.e., consistent with a *raw-return autocorrelation / noise-floor* measurement, not a *prediction→actual* correlation. "Raw 3h returns are unpredictable" and "the model's 3h predictions carry no information" are different claims with different implications for the regime-classifier pivot. The team should archive the actual calibration computation (script + output CSV) so the number can be audited.

**F6 — The experiment log has no `git SHA` / config-identifier pinning.** RESEARCH_HARNESS.md §4.2 mandates it; the actual `experiment-log.md` entries carry no SHA. Combined with the disk-vs-ZIP code drift this audit exposed (the V2.1 file on disk was edited after the first run), the log cannot currently be used to reconstruct "what was tested."

---

## Conclusion

The three headline conclusions driving the team's decision are **defensible but unevenly evidenced**:

1. **"No predictive edge"** — *Supported by the 7-run backtest record and the horizon test*, but the specific "calibration ≈ 0" evidence is **not archived** (one ambiguous −0.017 number in a comment; no 12h/24h values; no feature-importance artifact). Marking Q1 UNABLE-TO-VERIFY is a call to archive the computation, not a claim the conclusion is wrong.
2. **`custom_stoploss` bug** — **Fully confirmed** (API signature, API source, ZIP'd code, and exit-reason counts all agree). This is the most rigorously supported finding in the project.
3. **Data-directory resolution** — **Confirmed** (source + live logs + file timestamps/sizes). `binance/` is a stale orphan; `binanceus/` is authoritative.

The weakest link is **Q5**: the experiment log is incomplete (5 of 7 ML runs missing) and mis-attributes ML-002's +7.43% winner to an ATR trailing stop that never fired. Before the team finalizes the "abandon directional ML / go regime-classification" decision, it should (a) archive the calibration computation, (b) correct the ML-001 and ML-002 log entries, and (c) reconcile the "+25% gross" and Sharpe/Calmar figures — because several of the numbers currently in circulation are either un-sourced or contradicted by the backtest ZIPs.

---

*Audit produced from: strategy sources, config files, docs, freqtrade 2026.7 container introspection (`DataProvider` API + `create_datadir` + `strategy_safe_wrapper`), live freqtrade logs, and the extracted contents of all 9 relevant backtest ZIPs (ML-001/002/003/004/005/006a/006b + V2.1 Stage-1/fixed).*
