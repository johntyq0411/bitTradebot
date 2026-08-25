# Modest-Bohr — BTC/USDT Multi-Factor Trading Bot

**Project status:** Active research & development — strategy redesign phase (ML path)
**Last updated:** 2026-08-25
**Branch:** `staging` · **Repo:** `johntyq0411/bitTradebot`

> ⚠️ **PAPER TRADING ONLY** — `dry_run: true` is enforced in `user_data/config.json`. No real funds are ever used.

---

## 1. What This Project Is

A fully automated, single-pair crypto trading bot for **BTC/USDT** built on **Freqtrade + FreqAI**, running in Docker, paper-trading on Binance US. The goal: a **trend-following strategy with ML-enhanced signal generation** that produces consistent, secondary-income-grade returns with **max drawdown ≤ 20%**.

The core idea: instead of hard-coded rules (which failed), a **LightGBM model learns** the relationship between technical indicators, macro sentiment (Fear/Greed), and microstructure (funding/OI) to predict short-horizon BTC direction.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌──────────────────────┐      ┌─────────────────────────────┐  │
│  │  freqtrade_btc_bot   │      │  freqtrade_factor_cron      │  │
│  │  (stable_freqai)     │      │  (python:3.11-slim)         │  │
│  │                      │      │                             │  │
│  │  • trades 1h BTC/USDT│      │  • runs factor_collector.py │  │
│  │  • FreqAI LightGBM   │◄────►│    every 3600s              │  │
│  │  • REST API :8080    │  ══  │  • writes market_regime*.json│  │
│  │  • FreqUI web UI     │shared│                             │  │
│  └──────────────────────┘ mount└─────────────────────────────┘  │
│            │                │                                   │
│            │      ./user_data (bind mount)                      │
│            ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  user_data/                                              │   │
│  │  ├── strategies/          (strategy .py files)           │   │
│  │  ├── data/binanceus/      (BTC_USDT-1h/4h.feather)       │   │
│  │  ├── data/external/       (market_regime*.json, macro)   │   │
│  │  ├── models/              (FreqAI trained models)        │   │
│  │  ├── backtest_results/    (backtest exports)             │   │
│  │  ├── logs/                (freqtrade.log)                │   │
│  │  └── scripts/             (factor_collector, backfill,   │   │
│  │                             regime_decompose, etc.)      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Containers

| Container | Image | Role |
|---|---|---|
| `freqtrade_btc_bot` | `freqtradeorg/freqtrade:stable_freqai` | Main bot: trades 1h BTC/USDT, runs FreqAI LightGBM, serves FreqUI on `http://localhost:8080` |
| `freqtrade_factor_cron` | `python:3.11-slim` | Sidecar: refreshes macro factor data (Fear/Greed, funding, OI, DXY, SPY, stablecoins) every hour |

### 2.2 Data Flow

1. **factor_cron** polls external APIs hourly → writes `market_regime.json` (live) + `market_regime_history.json` (rolling 365-day history)
2. **freqtrade bot** reads OHLCV candles (`1h` + `4h` feathers) + macro history
3. **FreqAI** trains a LightGBM model every 24h (30-day train window, 48h model expiration) → predicts direction 3 candles ahead
4. **Strategy** converts model prediction into entry/exit signals
5. **FreqUI** at `:8080` shows live state; logs land in `user_data/logs/`

### 2.3 Key Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions (bot + factor cron) |
| `user_data/config.json` | Main bot config — **dry_run: true enforced** |
| `user_data/config_freqai.json` | FreqAI settings: 30d train / 7d backtest windows, LightGBM params |
| `user_data/strategies/FreqaiMultiFactorBtcStrategy.py` | **Active ML strategy** |
| `user_data/strategies/BtcTrendFollowingV2Strategy.py` | V2.0 trend-following (rejected) |
| `user_data/scripts/factor_collector.py` | Macro data collection (hourly) |
| `user_data/scripts/backfill_macro.py` | 2-year macro history backfill (new) |
| `loop.sh` | Research-loop orchestrator (phases 0–7) |
| `docs/experiment-log.md` | Running experiment log |
| `docs/SPEC_V2.md` | V2 technical design spec |
| `hermes_monitor.sh` | Health watchdog + alerts |

---

## 3. The Active Strategy — FreqaiMultiFactorBtcStrategy

### 3.1 Signal Generation (FreqAI LightGBM)

- **Model:** `LightGBMRegressor` (via `--freqaimodel`), identifier `MultiFactorLightGBM-1Year`
- **Target:** binary direction prediction — "price up in 3 candles" (`label_period_candles: 3`, 1h timeframe)
- **Features (~38 total):**
  - *Technicals*: RSI, ROC, volume-mean at periods [14, 20, 50, 200] (1h + 4h timeframes)
  - *Macro*: Fear & Greed, funding rate, open interest, long/short ratio, stablecoin supply, DXY, SPY
- **Training:** rolling 30-day window, retrained every 24h live (`live_retrain_hours: 24`), models expire after 48h

### 3.2 Trade Logic

- **Timeframe:** 1h · **Pair:** BTC/USDT only · **Max open trades:** 1
- **Entry:** model predicts up → buy
- **Exit:** `minimal_roi` tiers (5% at 0m, 3% at 120m, 1.5% at 240m) + stoploss −5%
- **⚠️ Known flaw (being fixed):** ROI tiers cap winners at ~1.5–3% while losses run to −5%; avg hold 1d9h vs 3-candle prediction horizon

---

## 4. Strategy Evolution & Progress

### Phase 1 — Rule-Based Baselines ❌

| Strategy | Result | Verdict |
|---|---|---|
| EMA20/50 Crossover + RSI | **−20.38%** (2yr walk-forward, lost in all 3 regimes) | ❌ Dead |

Simple crossover has no edge on BTC 1h after costs. Killed as baseline.

### Phase 2 — FreqAI LightGBM (ML) ⚠️→✅

| Experiment | Result | Verdict |
|---|---|---|
| V2-004 ML baseline | +14.94%, 92.9% win, 14 trades (bear-only window) | ⚠️ Promising but thin |
| **WFA-1Y-ML-001** (1yr full-data walk-forward) | **−25.41%, 64.1% win, 39 trades, DD 32.7%, market −27.9%** | ❌ Failed as configured |

**The walk-forward verdict (2026-08-25):** the *signal* is real (64.1% win rate vs ~50% random) but the *wrapper* is broken:
1. **Long-only in a bear market** (−27.9% period) — still beat buy-and-hold by ~2.5pts
2. **ROI caps winners** (avg win +1.61%) while stops run full (avg loss −4.84%) — 64% win rate can't overcome 1.6:4.8 payoff
3. **Horizon mismatch** — model predicts 3h ahead, trades held 1d9h

### Phase 3 — V2.0 Trend-Following ❌

| Experiment | Result | Verdict |
|---|---|---|
| V2-005 Trend Following | +1.22%, 28% DD, 66 trades, **p=0.965** | ❌ Noise |

Statistically indistinguishable from random. Also had a code/log mismatch (log said 1.5× ATR + SMA50 exit; code on disk had 3.0× ATR, no structural exit) — unresolved, strategy rejected.

### Where We Are Now

**Decision (2026-08-24): go ML.** The ML path was chosen over further rule-based iteration. Current state:
- ✅ 4h data backfilled to full 2 years (2024-08 → 2026-08)
- ✅ Macro history backfilled to 2 years (5 of 7 factors; OI + L/S ratio limited to 365d by Binance API)
- ✅ First legitimate out-of-sample walk-forward complete (WFA-1Y-ML-001)
- 🎯 Next: **WFA-1Y-ML-002** — fix the wrapper: ATR trailing exits, horizon-aligned time stops, bear/cash filter

---

## 5. Validation Methodology

### 5.1 Walk-Forward Protocol

- FreqAI **rolling 30d train / 7d test** windows over the full timerange (~52 folds/year)
- Every test window is **out-of-sample** — the model never sees it during training
- **Pass bar:** ≥70% of folds profitable after costs, 50+ total trades, max DD < 20%, lookahead-analysis clean, no single fold dominates

### 5.2 Pass/Fail Gates (per trading-strategy skill)

| Criterion | Critical | Current |
|---|---|---|
| Walk-forward ≥70% folds profitable | ✅ | ❌ (WFA-1Y-ML-001 failed) |
| >100 trades across folds | ✅ | ❌ (39) |
| Max DD < 20% | ✅ | ❌ (32.7%) |
| Lookahead-analysis passed | ✅ | ⚠️ not run on FreqAI |
| Realistic costs | ✅ | ✅ (0.1% fee) |

**Result:** NOT ready for paper-trading validation until wrapper fixes land and re-validation passes.

---

## 6. Known Data & Tooling Constraints

| Constraint | Detail |
|---|---|
| **4h data** | Only ~6 months existed until 2026-08-25 — **now backfilled to 2 years** (2024-08-01 → 2026-08-24) via `--prepend` |
| **Macro data** | Only 365 days existed — **now backfilled to 755 days** via `backfill_macro.py` (OI + L/S ratio can't be backfilled: Binance rolling-30d API) |
| **Macro freshness** | Strategy warns if `market_regime_history.json` > 48h old — stale macro silently degrades the model |
| **`--freqaimodel` required** | freqtrade 2026.7 fails with "No freqaimodel set" unless `--freqaimodel LightGBMRegressor` passed on CLI (not in config) |
| **Timerange syntax** | Must be `YYYYMMDD-YYYYMMDD` (e.g. `20240801-20260825`); ISO/dash formats rejected |
| **Models dir** | Clean before fresh backtests (`user_data/models/`) |

---

## 7. How to Run

```bash
# Start the bot (paper trading)
docker compose up -d
# FreqUI: http://localhost:8080

# Stream logs
docker compose logs -f freqtrade

# Download data (note YYYYMMDD format)
docker exec freqtrade_btc_bot freqtrade download-data \
  --config /freqtrade/user_data/config.json \
  --pairs BTC/USDT --timeframe 4h \
  --timerange 20240801-20260825 --prepend

# Run the 1-year ML walk-forward
docker exec freqtrade_btc_bot freqtrade backtesting \
  --config /freqtrade/user_data/config.json \
  --config /freqtrade/user_data/config_freqai.json \
  --freqaimodel LightGBMRegressor \
  --strategy FreqaiMultiFactorBtcStrategy \
  --timerange 20250826-20260825 \
  --export trades --cache none \
  --notes "WFA-1Y-ML-001"

# Refresh macro factors
docker exec freqtrade_factor_cron python /freqtrade/user_data/scripts/factor_collector.py

# Research loop orchestrator
./loop.sh all
```

---

## 8. Next Steps (Roadmap)

1. **WFA-1Y-ML-002** — wrapper fixes on the ML strategy:
   - Replace `minimal_roi` tiers with ATR trailing stop (winners run)
   - Horizon-aligned exit (~6h = 2× prediction horizon) or signal-reversal exit
   - Bear/cash filter: skip entries when model down-probability high
2. **Decompose fold-by-fold** which fix actually earns the change (avoid V2.0-style blind iteration)
3. **Re-run 1-year walk-forward** → compare against WFA-1Y-ML-001 fold-by-fold
4. **If passes:** extend to 2-year walk-forward (macro backfill already in place, minus OI/LS)
5. **Lookahead-analysis** on final strategy before paper-trading sign-off
6. **Paper trading** — verify live behavior matches backtest (30–50 live trades)

---

## 9. Reference Links

- Experiment log: `docs/experiment-log.md`
- V2 design spec: `docs/SPEC_V2.md`
- Research notes: `docs/research/initial-findings.md`
- Freqtrade docs: https://www.freqtrade.io/en/stable/
- FreqAI docs: https://www.freqtrade.io/en/stable/freqai/
