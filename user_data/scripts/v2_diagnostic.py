#!/usr/bin/env python3
"""
V2.4 Entry Signal Diagnostic
Counts how many candles meet the V2.4 entry criteria over the full 2-year period.
"""
import pandas as pd
import numpy as np
import talib.abstract as ta

df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-1h.feather')
total = len(df)

# Compute indicators
df['sma_200'] = ta.SMA(df, timeperiod=200)
df['sma_200_slope'] = df['sma_200'] - df['sma_200'].shift(24)
df['adx'] = ta.ADX(df, timeperiod=14)
df['atr'] = ta.ATR(df, timeperiod=14)
df['rsi'] = ta.RSI(df, timeperiod=14)
df['roc_24'] = (df['close'] - df['close'].shift(24)) / df['close'].shift(24) * 100
df['volume_sma_50'] = ta.SMA(df, timeperiod=50, price='volume')
df['volume_ratio'] = df['volume'] / df['volume_sma_50']
df['hh_20'] = df['high'].rolling(20).max()
df['is_hh'] = df['close'] > df['hh_20'].shift(1)
df['price_dist_sma200'] = (df['close'] - df['sma_200']) / df['sma_200'] * 100

def classify(row):
    if pd.isna(row['sma_200']) or pd.isna(row['adx']): return 'UNKNOWN'
    td = 1 if row['sma_200_slope'] > 0 else (-1 if row['sma_200_slope'] < 0 else 0)
    pp = row['price_dist_sma200']
    ts = row['adx']
    vol = row['atr'] / row['close'] * 100
    if td > 0 and pp > 2 and ts > 20: return 'BULL'
    if td < 0 and pp < -2 and ts > 20: return 'BEAR'
    if abs(pp) < 3 or ts < 20: return 'SIDEWAYS_LOWVOL' if vol < 2 else 'SIDEWAYS_HIGHVOL'
    return 'TRANSITION'

df['regime'] = df.apply(classify, axis=1)

df['s1'] = (df['close'] > df['sma_200']).astype(int)
df['s2'] = (df['sma_200_slope'] > 0).astype(int)
df['s3'] = (df['adx'] > 20).astype(int)
df['s4'] = (df['volume_ratio'] > 1.0).astype(int)
df['s5'] = (df['is_hh'].rolling(5).sum() >= 3).astype(int)
rsi_r = df['rsi'] > df['rsi'].shift(1)
df['s6'] = (((df['rsi'] > 50) & rsi_r) | (df['roc_24'] > 0)).astype(int)
df['score'] = df['s1'] + df['s2'] + df['s3'] + df['s4'] + df['s5'] + df['s6']

print("=== Regime Distribution ===")
print(df['regime'].value_counts())
print(f"\nTotal: {total} candles")

print(f"\n=== BULL Regime Analysis ===")
bull = df[df['regime'] == 'BULL']
print(f"BULL candles: {len(bull)} ({len(bull)/total*100:.1f}%)")

print(f"\n  Hard requirements in BULL:")
print(f"    s1 (price>SMA200): {(bull['s1']==1).sum()} ({(bull['s1']==1).sum()/len(bull)*100:.1f}%)")
print(f"    s2 (SMA slope>0): {(bull['s2']==1).sum()} ({(bull['s2']==1).sum()/len(bull)*100:.1f}%)")
print(f"    s3 (ADX>20): {(bull['s3']==1).sum()} ({(bull['s3']==1).sum()/len(bull)*100:.1f}%)")
print(f"    ALL 3 hard: {((bull['s1']==1)&(bull['s2']==1)&(bull['s3']==1)).sum()} ({((bull['s1']==1)&(bull['s2']==1)&(bull['s3']==1)).sum()/len(bull)*100:.1f}%)")

print(f"\n  Soft requirements in BULL:")
print(f"    s4 (volume>1.0x): {(bull['s4']==1).sum()} ({(bull['s4']==1).sum()/len(bull)*100:.1f}%)")
print(f"    s5 (higher high): {(bull['s5']==1).sum()} ({(bull['s5']==1).sum()/len(bull)*100:.1f}%)")
print(f"    s6 (momentum): {(bull['s6']==1).sum()} ({(bull['s6']==1).sum()/len(bull)*100:.1f}%)")

print(f"\n  Score distribution in BULL:")
print(bull['score'].value_counts().sort_index())

print(f"\n=== V2.4 Entry Criteria (BULL + all 3 hard + score>=3) ===")
v24_entry = df[(df['regime']=='BULL') & (df['s1']==1) & (df['s2']==1) & (df['s3']==1) & (df['score']>=3)]
print(f"Entry candles: {len(v24_entry)} ({len(v24_entry)/total*100:.2f}%)")

# Count distinct entry clusters (candles 24h apart = same trade opportunity)
if len(v24_entry) > 0:
    dates = v24_entry['date'].sort_values().values
    clusters = []
    current_cluster_start = dates[0]
    for i in range(1, len(dates)):
        gap_hours = (dates[i] - dates[i-1]) / 3600000000000
        if gap_hours >= 24:
            clusters.append(current_cluster_start)
            current_cluster_start = dates[i]
    clusters.append(current_cluster_start)
    print(f"Distinct entry clusters (24h apart): {len(clusters)}")
    print(f"First: {pd.Timestamp(clusters[0]).strftime('%Y-%m-%d %H:%M')}")
    print(f"Last: {pd.Timestamp(clusters[-1]).strftime('%Y-%m-%d %H:%M')}")
    print(f"\n  Cluster dates:")
    for i, c in enumerate(clusters[:30]):
        print(f"    {i+1}. {pd.Timestamp(c).strftime('%Y-%m-%d %H:%M')}")
    if len(clusters) > 30:
        print(f"    ... and {len(clusters)-30} more")

print(f"\n=== V2.5 Diagnostic (BULL + all 3 hard, NO score requirement) ===")
v25_candidate = df[(df['regime']=='BULL') & (df['s1']==1) & (df['s2']==1) & (df['s3']==1)]
print(f"Candles: {len(v25_candidate)} ({len(v25_candidate)/total*100:.2f}%)")
if len(v25_candidate) > 0:
    dates = v25_candidate['date'].sort_values().values
    clusters = []
    current_cluster_start = dates[0]
    for i in range(1, len(dates)):
        gap_hours = (dates[i] - dates[i-1]) / 3600000000000
        if gap_hours >= 24:
            clusters.append(current_cluster_start)
            current_cluster_start = dates[i]
    clusters.append(current_cluster_start)
    print(f"Distinct entry clusters (24h apart): {len(clusters)}")
    for i, c in enumerate(clusters[:20]):
        print(f"    {i+1}. {pd.Timestamp(c).strftime('%Y-%m-%d %H:%M')}")
    if len(clusters) > 20:
        print(f"    ... and {len(clusters)-20} more")
