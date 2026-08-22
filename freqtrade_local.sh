#!/usr/bin/env bash
# =============================================================================
# freqtrade_local.sh — Run Freqtrade commands natively via conda environment
# =============================================================================
# Use this script when Docker is not available.
# Requires: conda, python=3.11, and freqtrade pip-installed in the env.
#
# First-time setup:
#   conda create -n freqtrade-btc python=3.11 -y
#   conda run -n freqtrade-btc pip install freqtrade
#
# Usage:
#   ./freqtrade_local.sh download    # Download 180 days BTC/USDT 1h data
#   ./freqtrade_local.sh backtest    # Run backtest
#   ./freqtrade_local.sh trade       # Start paper trading bot (live)
# =============================================================================

set -euo pipefail

CONDA_ENV="freqtrade-btc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_DATA="$SCRIPT_DIR/user_data"
CONFIG="$USER_DATA/config.json"
STRATEGY="BtcTrendStrategy"

# Re-point paths to local (non-container) paths
LOCAL_CONFIG="$SCRIPT_DIR/user_data/config_local.json"

# Generate a local config that uses host-relative paths (not /freqtrade/...)
python3 - <<'PYEOF'
import json, os

script_dir = os.path.dirname(os.path.abspath("$SCRIPT_DIR" if "$SCRIPT_DIR" else "."))
user_data = os.path.join(os.getcwd(), "user_data")

with open("user_data/config.json") as f:
    cfg = json.load(f)

cfg["datadir"] = os.path.join(user_data, "data", "binance")
cfg["user_data_dir"] = user_data
cfg.pop("strategy_path", None)

with open("user_data/config_local.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("✅ Generated user_data/config_local.json with host-relative paths")
PYEOF

CMD="${1:-help}"

case "$CMD" in
  download)
    echo "📥 Downloading 180 days of BTC/USDT 1h data from Binance ..."
    conda run -n "$CONDA_ENV" freqtrade download-data \
      --config "$LOCAL_CONFIG" \
      --pairs BTC/USDT \
      --timeframe 1h \
      --days 180 \
      --exchange binance \
      --datadir "$USER_DATA/data/binance"
    echo "✅ Data downloaded to user_data/data/binance/"
    ;;

  backtest)
    echo "📊 Running backtest with $STRATEGY ..."
    conda run -n "$CONDA_ENV" freqtrade backtesting \
      --config "$LOCAL_CONFIG" \
      --strategy "$STRATEGY" \
      --strategy-path "$USER_DATA/strategies" \
      --timeframe 1h \
      --export trades \
      --export-filename "$USER_DATA/backtest_results/backtest_results.json" \
      2>&1 | tee "$USER_DATA/logs/backtest_output.txt"
    echo "✅ Backtest complete. Results saved to user_data/backtest_results/"
    ;;

  trade)
    echo "🚀 Starting paper-trading bot (Ctrl+C to stop) ..."
    conda run -n "$CONDA_ENV" freqtrade trade \
      --config "$LOCAL_CONFIG" \
      --strategy "$STRATEGY" \
      --strategy-path "$USER_DATA/strategies" \
      --logfile "$USER_DATA/logs/freqtrade.log"
    ;;

  *)
    echo "Usage: $0 {download|backtest|trade}"
    echo ""
    echo "  download  — Download 180d of BTC/USDT 1h OHLCV data"
    echo "  backtest  — Run backtest with BtcTrendStrategy"
    echo "  trade     — Start paper-trading bot live"
    exit 1
    ;;
esac
