import pandas as pd, numpy as np, talib.abstract as ta

df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-1h.feather')
df['date'] = pd.to_datetime(df['date'])

print("=== 1h Data Overview ===")
print("Rows:", len(df))
print("Start:", df['date'].min().date())
print("End:", df['date'].max().date())
print("Span:", (df['date'].max() - df['date'].min()).days, "days")

df['h'] = df['date'].diff().dt.total_seconds() / 3600
gaps = df[df['h'] > 1.5]
print("\nGaps > 1.5h:", len(gaps))

df['sma200'] = ta.SMA(df, timeperiod=200)
df['sma200_sl'] = df['sma200'] - df['sma200'].shift(24)
df['adx'] = ta.ADX(df, timeperiod=14)
df['dist'] = (df['close'] - df['sma200']) / df['sma200'] * 100

valid = df['sma200'].notna() & df['adx'].notna()
df_v = df[valid]

bull = ((df_v['sma200_sl'].astype(float) > 0) & (df_v['adx'].astype(float) >= 20) & (df_v['dist'].astype(float) > 2))
print("\n=== BULL Regime ===")
print("Candles:", bull.sum(), "/", len(df_v), "(", round(bull.sum()/len(df_v)*100,1), "%)")

bull_s = bull.astype(int).values.copy()
bull_s = np.concatenate([[0], bull_s, [0]])
diff = np.diff(bull_s)
starts = np.where(diff == 1)[0]
ends = np.where(diff == -1)[0]

print("\nBULL periods:", len(starts))
for i in range(min(10, len(starts), len(ends))):
    s = df_v.iloc[starts[i]]
    e = df_v.iloc[ends[i]-1]
    print(f"  {i+1}. {s['date'].date()} -> {e['date'].date()} ({(e['date']-s['date']).days}d)")
if len(starts) > 10:
    print(f"  ... and {len(starts)-10} more")
