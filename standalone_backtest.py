"""
standalone_backtest.py
======================
Full offline backtesting engine for BtcTrendStrategy (Multi-Factor).
Reads local OHLCV JSON, computes Macro/Micro/Technical indicators, 
and simulates trades exactly like Freqtrade.

Usage:
    conda run -n freqtrade-btc python3 standalone_backtest.py
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import talib

# ── Configuration ─────────────────────────────────────────────────────────────
DATA_FILE       = Path("/Users/yuquanjohntan/Documents/antigravity/modest-bohr/user_data/data/binance/BTC_USDT-1h.json")
RESULTS_DIR     = Path("/Users/yuquanjohntan/Documents/antigravity/modest-bohr/user_data/backtest_results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 1_000.0
STOPLOSS        = -0.05
MINIMAL_ROI     = {0: 0.035, 60: 0.02, 120: 0.01}
TIMEFRAME_MINS  = 60
STARTUP_CANDLES = 60
FEE             = 0.001

TRAILING_STOP = True
TRAILING_STOP_POS = 0.01
TRAILING_STOP_POS_OFFSET = 0.025

# Strategy parameters (Tightened)
BUY_RSI_LOWER       = 45
BUY_RSI_UPPER       = 60
SELL_RSI_THRESHOLD  = 75

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("=" * 68)
print("  BtcTrendStrategy — Standalone Backtest Engine (Multi-Factor)")
print("=" * 68)
with open(DATA_FILE) as f:
    raw = json.load(f)

df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.sort_values("date").reset_index(drop=True)

# ── Compute Indicators ────────────────────────────────────────────────────────
print("\n⚙️  Computing indicators...")

# MACRO (Simulated 1d EMA using 1h data * 24)
df["macro_ema_20"] = talib.EMA(df["close"].values, timeperiod=20 * 24)
df["macro_ema_50"] = talib.EMA(df["close"].values, timeperiod=50 * 24)
df["macro_uptrend"] = df["macro_ema_20"] > df["macro_ema_50"]

# TECHNICAL (1h)
df["ema_20"]  = talib.EMA(df["close"].values, timeperiod=20)
df["ema_50"]  = talib.EMA(df["close"].values, timeperiod=50)
df["rsi"]     = talib.RSI(df["close"].values, timeperiod=14)

df["ema_above"]      = df["ema_20"] > df["ema_50"]
df["ema_cross_above"] = df["ema_above"] & ~df["ema_above"].shift(1).fillna(False)
df["ema_cross_below"] = ~df["ema_above"] & df["ema_above"].shift(1).fillna(True)

# MICRO (Volume Spike)
df["volume_ma_24"] = df["volume"].rolling(24).mean()
df["micro_vol_spike"] = df["volume"] > (df["volume_ma_24"] * 1.5)

# ── Generate Entry / Exit Signals ─────────────────────────────────────────────
df["enter_long"] = (
    df["macro_uptrend"]
    & df["ema_cross_above"]
    & df["rsi"].between(BUY_RSI_LOWER, BUY_RSI_UPPER)
    & df["micro_vol_spike"]
)
df["exit_long"] = (
    (df["ema_cross_below"] | (df["rsi"] > SELL_RSI_THRESHOLD))
    & (df["volume"] > 0)
)

df_live = df.iloc[STARTUP_CANDLES:].reset_index(drop=True)

# ── Helper: ROI check ─────────────────────────────────────────────────────────
def check_roi(profit_ratio: float, candles_held: int) -> bool:
    minutes_held = candles_held * TIMEFRAME_MINS
    applicable_roi = None
    for roi_minutes in sorted(MINIMAL_ROI.keys()):
        if minutes_held >= roi_minutes:
            applicable_roi = MINIMAL_ROI[roi_minutes]
    return applicable_roi is not None and profit_ratio >= applicable_roi

# ── Trade Simulation ──────────────────────────────────────────────────────────
print("\n🔄 Simulating trades...")

trades = []
in_trade        = False
entry_price     = 0.0
entry_ts        = None
entry_idx       = 0
max_price       = 0.0
stake           = INITIAL_CAPITAL
capital         = INITIAL_CAPITAL

for i, row in df_live.iterrows():
    if not in_trade:
        if row["enter_long"] and not pd.isna(row["rsi"]):
            in_trade    = True
            entry_price = row["close"]
            entry_ts    = row["date"]
            entry_idx   = i
            max_price   = row["close"]
            stake       = capital
    else:
        candles_held  = i - entry_idx
        max_price = max(max_price, row["high"])
        max_profit_ratio = (max_price - entry_price) / entry_price
        profit_ratio = (row["close"] - entry_price) / entry_price

        exit_reason = None
        exit_price  = row["close"]

        # Trailing Stop or Hard Stop
        if TRAILING_STOP and max_profit_ratio >= TRAILING_STOP_POS_OFFSET:
            sl_ratio = max_profit_ratio - (TRAILING_STOP_POS_OFFSET - TRAILING_STOP_POS)
            sl_price = entry_price * (1 + sl_ratio)
            stop_type = "trailing_stop"
        else:
            sl_price = entry_price * (1 + STOPLOSS)
            stop_type = "stop_loss"

        if row["low"] <= sl_price:
            exit_price  = sl_price
            exit_reason = stop_type
        elif check_roi(profit_ratio, candles_held):
            exit_reason = "roi"
        elif row["exit_long"]:
            exit_reason = "exit_signal"

        if exit_reason:
            gross_profit = stake * ((exit_price - entry_price) / entry_price)
            fees         = stake * FEE + (stake + gross_profit) * FEE
            net_profit   = gross_profit - fees
            net_ratio    = net_profit / stake
            capital += net_profit

            trades.append({
                "open_date":    entry_ts,
                "close_date":   row["date"],
                "pair":         "BTC/USDT",
                "entry_price":  round(entry_price, 2),
                "exit_price":   round(exit_price, 2),
                "candles_held": candles_held,
                "hours_held":   candles_held,
                "stake":        round(stake, 4),
                "gross_profit": round(gross_profit, 4),
                "net_profit":   round(net_profit, 4),
                "profit_ratio": round(net_ratio * 100, 4),
                "exit_reason":  exit_reason,
                "capital_after":round(capital, 4),
            })
            in_trade = False

# ── Compute Metrics ───────────────────────────────────────────────────────────
total_trades = len(trades)
if total_trades == 0:
    print("\n⚠️  No trades were generated. The filters are too strict!")
else:
    trade_df = pd.DataFrame(trades)
    winners = trade_df[trade_df["net_profit"] > 0]
    losers  = trade_df[trade_df["net_profit"] <= 0]

    win_rate = len(winners) / total_trades * 100
    total_profit_pct = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    capital_curve = [INITIAL_CAPITAL] + list(trade_df["capital_after"])
    peak = capital_curve[0]
    max_dd = 0.0
    for cap in capital_curve:
        if cap > peak: peak = cap
        dd = (peak - cap) / peak
        if dd > max_dd: max_dd = dd

    SEP = "─" * 68
    print(f"\n{SEP}")
    print(f"  {'Total Trades':<30} {total_trades:>10}")
    print(f"  {'Winning Trades':<30} {len(winners):>10}  ({win_rate:.1f}%)")
    print(f"  {'Total Profit':<30} {total_profit_pct:>+10.2f}%")
    print(f"  {'Max Drawdown':<30} {max_dd*100:>10.2f}%")
    print(SEP)
    
    out_json = RESULTS_DIR / "backtest_results.json"
    summary = {
        "strategy": "BtcTrendStrategy (Multi-Factor)",
        "win_rate_pct": round(win_rate, 2),
        "total_profit_pct": round(total_profit_pct, 4),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "trades": trades
    }
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"✅ Full results saved to: {out_json}")
