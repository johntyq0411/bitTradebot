import sys
import json
import math
import pandas as pd
import talib
from pathlib import Path

DATA_FILE = Path("/Users/yuquanjohntan/Documents/antigravity/modest-bohr/user_data/data/binance/BTC_USDT-1h.json")
with open(DATA_FILE) as f:
    raw = json.load(f)

df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.sort_values("date").reset_index(drop=True)

df["ema_20"]  = talib.EMA(df["close"].values, timeperiod=20)
df["ema_50"]  = talib.EMA(df["close"].values, timeperiod=50)
df["rsi"]     = talib.RSI(df["close"].values, timeperiod=14)
df["ema_above"]      = df["ema_20"] > df["ema_50"]
df["ema_cross_above"] = df["ema_above"] & ~df["ema_above"].shift(1).fillna(False)
df["ema_cross_below"] = ~df["ema_above"] & df["ema_above"].shift(1).fillna(True)

def run_backtest(stoploss, min_roi, buy_rsi_lower, buy_rsi_upper, sell_rsi_threshold):
    df_live = df.copy()
    df_live["enter_long"] = (df_live["ema_cross_above"] & df_live["rsi"].between(buy_rsi_lower, buy_rsi_upper) & (df_live["volume"] > 0))
    df_live["exit_long"] = ((df_live["ema_cross_below"] | (df_live["rsi"] > sell_rsi_threshold)) & (df_live["volume"] > 0))
    df_live = df_live.iloc[60:].reset_index(drop=True)

    INITIAL_CAPITAL = 1000.0
    FEE = 0.001
    trades = []
    in_trade = False
    capital = INITIAL_CAPITAL
    
    for i, row in df_live.iterrows():
        if not in_trade:
            if row["enter_long"] and not pd.isna(row["rsi"]):
                in_trade = True
                entry_price = row["close"]
                entry_ts = row["date"]
                entry_idx = i
                stake = capital
        else:
            candles_held = i - entry_idx
            profit_ratio = (row["close"] - entry_price) / entry_price
            exit_reason = None
            exit_price = row["close"]
            
            sl_price = entry_price * (1 + stoploss)
            if row["low"] <= sl_price:
                exit_price = sl_price
                exit_reason = "stop_loss"
            else:
                roi_hit = False
                minutes_held = candles_held * 60
                app_roi = None
                for rm in sorted(min_roi.keys()):
                    if minutes_held >= rm: app_roi = min_roi[rm]
                if app_roi is not None and profit_ratio >= app_roi:
                    roi_hit = True
                if roi_hit:
                    exit_reason = "roi"
                elif row["exit_long"]:
                    exit_reason = "exit_signal"
                    
            if exit_reason:
                gross_profit = stake * ((exit_price - entry_price) / entry_price)
                fees = stake * FEE + (stake + gross_profit) * FEE
                net_profit = gross_profit - fees
                capital += net_profit
                trades.append({
                    "net_profit": net_profit,
                    "profit_ratio": net_profit/stake,
                    "capital": capital,
                    "reason": exit_reason
                })
                in_trade = False
                
    if not trades: return 0, 0, 0, 0, 0, {}
    trade_df = pd.DataFrame(trades)
    winners = trade_df[trade_df["net_profit"] > 0]
    win_rate = len(winners) / len(trades) * 100
    total_profit_pct = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    
    cap_curve = [INITIAL_CAPITAL] + list(trade_df["capital"])
    peak = cap_curve[0]
    max_dd = 0.0
    for cap in cap_curve:
        if cap > peak: peak = cap
        dd = (peak - cap) / peak
        if dd > max_dd: max_dd = dd
        
    exit_counts = trade_df["reason"].value_counts().to_dict()
    return len(trades), win_rate, total_profit_pct, max_dd*100, exit_counts

print("1. Baseline (-4% SL, 5/3/1.5% ROI)")
print(run_backtest(-0.04, {0: 0.05, 120: 0.03, 240: 0.015}, 40, 65, 75))

print("2. 'Never Lose' attempt (-99% SL, 1% ROI, strict entry)")
print(run_backtest(-0.99, {0: 0.01}, 20, 60, 99))

print("3. Ultra safe entry, tiny profit (-99% SL, 0.5% ROI, strict entry)")
print(run_backtest(-0.99, {0: 0.005}, 30, 50, 99))

