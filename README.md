# Freqtrade BTC/USDT Paper Trading Bot

> ⚠️ **PAPER TRADING ONLY** — `dry_run: true` is enforced in `config.json`. No real funds will ever be used.

## Project Structure

```
.
├── docker-compose.yml              # Docker Compose service definition
├── setup.sh                        # One-shot setup + launch script
└── user_data/
    ├── config.json                 # Freqtrade configuration (dry-run enforced)
    ├── strategies/
    │   └── BtcTrendStrategy.py    # EMA20/50 crossover + RSI(14) strategy
    ├── data/
    │   └── binance/               # Downloaded OHLCV candle data
    ├── backtest_results/          # Backtest output JSON files
    └── logs/
        ├── freqtrade.log          # Live bot log
        └── backtest_output.txt    # Backtest terminal output
```

## Quick Start

### Prerequisites
Install **Docker Desktop** for macOS: https://docs.docker.com/desktop/install/mac-install/

### Run Everything (recommended)
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Step-by-Step

```bash
# 1. Pull the Freqtrade image
docker compose pull

# 2. Download 180 days of BTC/USDT 1h data from Binance
docker compose run --rm freqtrade download-data \
    --config /freqtrade/user_data/config.json \
    --pairs BTC/USDT \
    --timeframe 1h \
    --days 180 \
    --exchange binance \
    --datadir /freqtrade/user_data/data/binance

# 3. Run backtest
docker compose run --rm freqtrade backtesting \
    --config /freqtrade/user_data/config.json \
    --strategy BtcTrendStrategy \
    --timeframe 1h \
    --export trades \
    --export-filename /freqtrade/user_data/backtest_results/backtest_results.json

# 4. Launch live paper-trading bot
docker compose up -d

# 5. Stream logs
docker compose logs -f

# 6. Stop bot
docker compose down
```

## Web UI (FreqUI)

After launch, visit **http://localhost:8080**

| Field    | Value        |
|----------|-------------|
| Username | `freqtrader` |
| Password | `freqtrader` |

## Strategy Overview

**File:** `user_data/strategies/BtcTrendStrategy.py`

| Parameter       | Value                                    |
|----------------|------------------------------------------|
| Timeframe      | 1h                                       |
| Indicators     | EMA(20), EMA(50), RSI(14)               |
| Entry          | EMA20 crosses above EMA50 AND 40 ≤ RSI ≤ 65 |
| Exit           | EMA20 crosses below EMA50 OR RSI > 75   |
| Minimal ROI    | 5% @ 0m, 3% @ 120m, 1.5% @ 240m        |
| Stoploss       | -4%                                      |
| Max Open Trades| 1                                        |
| Wallet         | 1000 USDT (simulated)                    |

## Configuration Highlights

| Setting               | Value                          |
|----------------------|-------------------------------|
| `dry_run`            | `true` ✅                     |
| `dry_run_wallet`     | `1000` USDT                   |
| `exchange`           | `binance`                     |
| `api key / secret`   | `""` (blank — paper only)     |
| `pair_whitelist`     | `["BTC/USDT"]`                |
| `stake_amount`       | `"unlimited"`                 |
| `max_open_trades`    | `1`                           |
| Web UI port          | `8080`                        |

## Hyperopt (Optional)

To optimize strategy parameters:
```bash
docker compose run --rm freqtrade hyperopt \
    --config /freqtrade/user_data/config.json \
    --strategy BtcTrendStrategy \
    --hyperopt-loss SharpeHyperOptLoss \
    --epochs 200 \
    --spaces buy sell
```
