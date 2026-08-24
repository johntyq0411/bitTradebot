---
name: multifactor_trading
description: Guidelines for implementing Multi-Factor Trading (Macro, Micro, and Technical Analysis) in Freqtrade bots, including the full Antigravity→VS Code (Cline)→GitHub→VPS deployment lifecycle.
---

# Multi-Factor Trading Architecture

This skill defines the professional standard for building algorithmic trading strategies. Relying solely on Technical Analysis (TA) often leads to high win rates in bull markets but catastrophic drawdowns in bear markets.

To build institutional-grade strategies, agents must implement a **Multi-Factor Architecture** AND follow the full **four-phase deployment lifecycle**.

---

## Part 1: The Three Pillars of Multi-Factor Strategy

Every strategy should incorporate conditions from three distinct domains before generating an entry signal.

### A. Macro Analysis (The Environment)
* **Goal**: Establish the broader trend and regime. We do not buy against the Macro trend.
* **Implementation in Freqtrade**:
  * Use **Informative Pairs** to fetch Higher Timeframe (HTF) data (e.g., 4h candles while the main strategy runs on 1h).
  * The 4h EMA200 is the macro filter: `close > ema200_4h`.
  * `startup_candle_count` must be set to `200 × (HTF_multiplier)`. For a 1h strategy with 4h EMA200: `startup_candle_count = 800`.
  * External macro factors (Fear & Greed Index, Funding Rate) must be loaded from a pre-collected historical file to avoid lookahead bias. Do NOT call live APIs inside `populate_indicators`.

### B. Technical Analysis (The Setup)
* **Goal**: Identify a specific momentum setup.
* **Implementation**:
  * EMA20 > EMA50 on the base timeframe (uptrend confirmation).
  * Price must be in a true **pullback zone**: `ema50 * 0.995 <= close <= ema20 * 1.005`. This prevents chasing breakouts.
  * RSI 14 in a mid-momentum range (e.g., 45–60). Not overbought, not oversold.

### C. Micro Analysis (The Trigger)
* **Goal**: Confirm local market structure supports the setup.
* **Implementation**:
  * ATR 14 for dynamic stop-loss sizing (`2.5 × ATR`).
  * Volume check: `volume > 0` (sanity gate; can be extended to volume > rolling mean × 1.5).
  * Funding Rate as momentum quality filter: `0 < funding_rate < 0.001`.

---

## Part 2: Risk Management Rules

* **Never use both `trailing_stop = True` AND `use_custom_stoploss = True`** simultaneously. They conflict. Use only one.
* Always cap ATR in `custom_stoploss` to prevent stoploss widening during volatility spikes: `atr = min(atr, current_rate * 0.02)`.
* Bounds on custom stoploss: `return max(min(atr_stop, -0.015), -0.06)` (between 1.5% and 6%).
* Never swallow exceptions silently in `populate_indicators`. Always log with `logger.warning(...)`.
* Paths to external data files must use `self.config.get('user_data_dir', 'user_data')` — never hardcode absolute Mac/Windows paths.

---

## Part 3: Factor Collector Requirements

A sidecar script (`user_data/scripts/factor_collector.py`) must:
1. Fetch Fear & Greed from `https://api.alternative.me/fng/?limit=180`.
2. Fetch BTC Funding Rate from **Binance US** (primary) or **Coinglass** (fallback). The dYdX v3 API is permanently decommissioned — do not use it.
3. Write `market_regime.json` (live state) and `market_regime_history.json` (180-day series).
4. Support a `FACTOR_DATA_DIR` environment variable for Docker path overrides.
5. Be scheduled to run every 1 hour (Docker sidecar or cron).

---

## Part 4: Four-Phase Deployment Lifecycle

### Phase 1 — Scaffolding (Antigravity)
* Role: Tech Lead / Project Manager
* Deliverables: `docker-compose.yml`, `config.json` (dry_run=true), `factor_collector.py`, strategy skeleton, initial data download.
* Model: Use a deep-reasoning model (Claude Sonnet Thinking) for quantitative design decisions.

### Phase 2 — Precision Engineering (VS Code + Cline)
* Role: Quantitative Developer
* Deliverables: Fine-tuned indicators, verified pullback logic diffs, ATR stop multiplier tuning.
* All code changes must be handled by the Cline extension inside VS Code and reviewed as a line-by-line diff before applying.

### Phase 3 — Version Control (GitHub)
* Repository branches: `staging` (paper trade) → `prod` (live).
* What to commit: `docker-compose.yml`, `*.py` strategies, `config.example.json`, `.env.example`, `hermes_monitor.sh`.
* What never to commit: `user_data/config.json` (has keys), `.env`, `tradesv3.sqlite*`, `user_data/data/`.
* `.gitignore` must explicitly cover all of the above.

### Phase 4 — Autonomous Live Operations (VPS + Hermes)
* Provision a KVM VPS (Ubuntu, Singapore region for low Binance latency).
* Deploy with `docker compose up -d`.
* Start `hermes_monitor.sh` as a background daemon for Discord alerts.
* Emergency kill: `docker compose down` (safe — dry_run=true cannot lose real funds).
* Switch from paper to live: set `"dry_run": false` in `config.json`, inject real API keys, restart Docker.

---

## Part 5: Quantitative Review Checklist

Before deploying any strategy change, invoke a **Quantitative Reviewer Subagent** to check:
1. **Lookahead bias**: No `df['close'].shift(-1)` or future data in `populate_indicators`.
2. **`startup_candle_count` coverage**: Covers all indicator warmup periods on all timeframes.
3. **Stoploss consistency**: Only one stoploss mechanism active (custom OR trailing, not both).
4. **Path portability**: No hardcoded absolute paths; use config-relative or env-var paths.
5. **Pandas index safety**: After `pd.merge`, always use `.values` when assigning back to the original DataFrame.
6. **API endpoint liveness**: All external APIs in the factor collector should be verified reachable.
7. **Funding rate directionality**: The filter `funding_rate > 0` is a bullish condition — ensure it's not inverted.
