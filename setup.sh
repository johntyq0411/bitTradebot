#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-shot setup, data download, backtest & launch script
# =============================================================================
# This script:
#   1. Verifies Docker is installed
#   2. Downloads 180 days of BTC/USDT 1h candles from Binance
#   3. Runs a backtest with BtcTrendStrategy
#   4. Launches the Freqtrade dry-run bot in the background
#   5. Tails the logs for 30 seconds to confirm healthy startup
#
# SAFETY: dry_run is enforced in config.json — no real funds are used.
# =============================================================================

set -euo pipefail

COMPOSE_CMD=""
if command -v docker &>/dev/null; then
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    fi
fi

if [[ -z "$COMPOSE_CMD" ]]; then
    echo "❌ Docker / Docker Compose not found."
    echo ""
    echo "Please install Docker Desktop for macOS from:"
    echo "  https://docs.docker.com/desktop/install/mac-install/"
    echo ""
    echo "After installation, re-run this script."
    exit 1
fi

echo "✅ Docker found. Using: $COMPOSE_CMD"
echo ""

# Pull the latest stable Freqtrade image
echo "📦 Pulling freqtradeorg/freqtrade:stable ..."
$COMPOSE_CMD pull

echo ""
echo "📥 Downloading 180 days of BTC/USDT 1h candle data from Binance ..."
$COMPOSE_CMD run --rm freqtrade download-data \
    --config /freqtrade/user_data/config.json \
    --pairs BTC/USDT \
    --timeframe 1h \
    --days 180 \
    --exchange binance \
    --datadir /freqtrade/user_data/data/binance

echo ""
echo "📊 Running backtest (BtcTrendStrategy, last 180 days) ..."
$COMPOSE_CMD run --rm freqtrade backtesting \
    --config /freqtrade/user_data/config.json \
    --strategy BtcTrendStrategy \
    --timeframe 1h \
    --export trades \
    --export-filename /freqtrade/user_data/backtest_results/backtest_results.json \
    2>&1 | tee user_data/logs/backtest_output.txt

echo ""
echo "🚀 Starting Freqtrade paper-trading bot in background ..."
$COMPOSE_CMD up -d

echo ""
echo "📋 Streaming logs for 30 seconds to verify healthy startup ..."
$COMPOSE_CMD logs -f --tail=50 &
LOGS_PID=$!
sleep 30
kill $LOGS_PID 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✅  Freqtrade BTC/USDT Paper Trading Bot is RUNNING"
echo "═══════════════════════════════════════════════════════════"
echo "  Web UI  : http://localhost:8080"
echo "  Login   : freqtrader / freqtrader"
echo "  Logs    : docker compose logs -f"
echo "  Stop    : docker compose down"
echo "  SAFETY  : dry_run=true enforced — NO real funds at risk"
echo "═══════════════════════════════════════════════════════════"
