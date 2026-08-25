import pandas as pd, numpy as np, talib.abstract as ta

df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-1h.feather')
df['date'] = pd.to_datetime(df['date'])

print("=== Data overview ===")
print(f"Rows: {len(df)}, Span: {(df['date'].max() - df['date'].min()).days} days")
print(f"Price range: ${df['close'].min():.0f} - ${df['close'].max():.0f}")

# ATR stats
atr = ta.ATR(df, timeperiod=14)
print(f"\n=== ATR stats (14-period) ===")
print(f"ATR: min={atr.min():.2f}, mean={atr.mean():.2f}, median={atr.median():.2f}, max={atr.max():.2f}")
print(f"ATR % of price: mean={atr.mean()/df['close'].mean()*100:.2f}%")

# 3x ATR trailing stop on the actual trade (Sep 2024 - Aug 2026)
print(f"\n=== Simulating 3x ATR trailing stop on Sep2024-Aug2026 ===")
trade_df = df[(df['date'] >= '2024-09-14') & (df['date'] <= '2026-08-24')].copy()
trade_df['atr'] = ta.ATR(trade_df, timeperiod=14)
trade_df['highest_close'] = trade_df['close'].expanding().max()

# Trailing stop price at each point
trade_df['trailing_stop'] = trade_df['highest_close'] - 3.0 * trade_df['atr']
trade_df['stopped_out'] = trade_df['close'] < trade_df['trailing_stop']

stop_triggered = trade_df[trade_df['stopped_out']]
print(f"Stop would have triggered on {len(stop_triggered)} candles")
if len(stop_triggered) > 0:
    first_stop = stop_triggered.iloc[0]
    print(f"First stop: {first_stop['date'].date()} at ${first_stop['close']:.0f} " +
          f"(ATR={first_stop['atr']:.0f}, highest=${first_stop['highest_close']:.0f})")
    print(f"Price % from peak: {(first_stop['close']/first_stop['highest_close'] - 1)*100:.1f}%")

# When did BTC peak?
peak_idx = trade_df['close'].idxmax()
peak_row = trade_df.loc[peak_idx]
print(f"\nBTC peak: {peak_row['date'].date()} at ${peak_row['close']:.0f}")
print(f"Final price: ${trade_df.iloc[-1]['close']:.0f}")
print(f"Drawdown from peak: {(trade_df.iloc[-1]['close']/peak_row['close'] - 1)*100:.1f}%")

# ATR at peak
peak_atr = trade_df.loc[peak_idx, 'atr']
print(f"ATR at peak: ${peak_atr:.0f}")
print(f"3x ATR from peak: ${peak_row['close'] - 3*peak_atr:.0f}")
print(f"Final price vs 3x ATR from peak: ${trade_df.iloc[-1]['close']:.0f} vs ${peak_row['close'] - 3*peak_atr:.0f}")
print(f"Difference: ${trade_df.iloc[-1]['close'] - (peak_row['close'] - 3*peak_atr):.0f}")

# Price when it would have stopped out (3x ATR after peak)
after_peak = trade_df.loc[peak_idx:]
after_peak['hcc'] = after_peak['close'].cummax()
after_peak['ts'] = after_peak['hcc'] - 3*after_peak['atr']
after_peak['exit'] = after_peak['close'] < after_peak['ts']
exit_rows = after_peak[after_peak['exit']]
if len(exit_rows) > 0:
    er = exit_rows.iloc[0]
    print(f"\nWould have exited: {er['date'].date()} at ${er['close']:.0f}")
    print(f"ATR then: ${er['atr']:.0f}, highest: ${er['hcc']:.0f}")
    print(f"Stoploss price: ${er['ts']:.0f}")
    print(f"Profit at exit: {(er['close']/60008 - 1)*100:.1f}%")
