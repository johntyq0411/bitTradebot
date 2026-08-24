#!/usr/bin/env python3
"""
Phase 1: Regime Decomposition for BTC/USDT 1h data
====================================================
Classifies market regimes (Bull / Bear / Sideways) using:
  - 200-period SMA slope (trend direction)
  - Price position relative to SMA (above/below)
  - Realized volatility (high = trending, low = sideways)

Outputs regime segments with date ranges for backtesting.
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timezone

# Load the full 2-year data
df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-1h.feather')
df = df.sort_values('date').reset_index(drop=True)

print(f"Data: {len(df)} candles, {df['date'].min()} to {df['date'].max()}")
print()

# ---- Regime Classification ----

# 1. 200-period SMA (on 1h data = ~8 days, too short for macro regime)
# Use 200-day equivalent: 200 * 24 = 4800 candles
sma_period = 4800  # ~200 days on 1h data
df['sma_200d'] = df['close'].rolling(sma_period).mean()

# 2. SMA slope: compare SMA now vs SMA 24h ago (1 day)
df['sma_slope'] = df['sma_200d'] - df['sma_200d'].shift(24)

# 3. Price distance from SMA (percentage)
df['price_dist'] = (df['close'] - df['sma_200d']) / df['sma_200d'] * 100

# 4. Realized volatility: std of returns over 24h rolling window
df['returns'] = df['close'].pct_change()
df['vol_24h'] = df['returns'].rolling(24).std() * np.sqrt(24)  # annualized-ish

# 5. Classify regime per candle
def classify_regime(row):
    if pd.isna(row['sma_200d']) or pd.isna(row['sma_slope']):
        return 'UNKNOWN'
    
    # Trend direction
    if row['sma_slope'] > 0:
        trend = 'BULL'
    elif row['sma_slope'] < 0:
        trend = 'BEAR'
    else:
        trend = 'FLAT'
    
    # Price position
    dist = row['price_dist']
    
    # Volatility
    vol = row['vol_24h'] if not pd.isna(row['vol_24h']) else 0
    
    # Combined classification
    if trend == 'BULL' and dist > 5:
        return 'BULL_STRONG'
    elif trend == 'BULL' and dist > 0:
        return 'BULL_WEAK'
    elif trend == 'BEAR' and dist < -5:
        return 'BEAR_STRONG'
    elif trend == 'BEAR' and dist < 0:
        return 'BEAR_WEAK'
    elif abs(dist) < 3 and vol < 0.02:
        return 'SIDEWAYS'
    elif trend == 'FLAT':
        return 'SIDEWAYS'
    else:
        return 'TRANSITION'

df['regime'] = df.apply(classify_regime, axis=1)

# ---- Consolidate to simpler regimes ----
regime_map = {
    'BULL_STRONG': 'BULL',
    'BULL_WEAK': 'BULL',
    'BEAR_STRONG': 'BEAR',
    'BEAR_WEAK': 'BEAR',
    'SIDEWAYS': 'SIDEWAYS',
    'TRANSITION': 'SIDEWAYS',
    'UNKNOWN': 'SIDEWAYS',
}
df['regime_simple'] = df['regime'].map(regime_map)

# ---- Find regime segments (consecutive runs) ----
df['regime_change'] = df['regime_simple'] != df['regime_simple'].shift(1)
df['segment_id'] = df['regime_change'].cumsum()

segments = df.groupby(['segment_id', 'regime_simple']).agg(
    start=('date', 'min'),
    end=('date', 'max'),
    candles=('date', 'count'),
    start_price=('close', 'first'),
    end_price=('close', 'last'),
).reset_index()

segments['return_pct'] = (segments['end_price'] - segments['start_price']) / segments['start_price'] * 100
segments = segments.sort_values('start')

print("=" * 80)
print("REGIME SEGMENTS (consecutive runs)")
print("=" * 80)
print()

for _, seg in segments.iterrows():
    # Skip tiny segments (< 24 candles = 1 day)
    if seg['candles'] < 24:
        continue
    print(f"{seg['regime_simple']:12s} | {seg['start']} → {seg['end']} | "
          f"{seg['candles']:5d} candles ({seg['candles']/24:.1f} days) | "
          f"{seg['return_pct']:+.2f}%")

print()
print("=" * 80)
print("REGIME SUMMARY (aggregated)")
print("=" * 80)

regime_summary = segments.groupby('regime_simple').agg(
    total_candles=('candles', 'sum'),
    total_days=('candles', lambda x: x.sum() / 24),
    total_return=('return_pct', 'sum'),
    num_segments=('segment_id', 'count'),
).sort_values('total_candles', ascending=False)

for regime, row in regime_summary.iterrows():
    pct = row['total_candles'] / len(df) * 100
    candles = int(row['total_candles'])
    days = int(row['total_days'])
    print(f"{regime:12s} | {candles:5d} candles ({days} days, {pct:.1f}%) | "
          f"{int(row['num_segments'])} segments | Cumulative return: {row['total_return']:+.2f}%")

print()
print("=" * 80)
print("REGIME BREAKDOWN BY YEAR")
print("=" * 80)

df['year'] = df['date'].dt.year
year_regime = df.groupby(['year', 'regime_simple']).size().unstack(fill_value=0)
for year in sorted(df['year'].unique()):
    print(f"\n{year}:")
    row = year_regime.loc[year]
    total = row.sum()
    for regime in ['BULL', 'BEAR', 'SIDEWAYS']:
        if regime in row:
            pct = row[regime] / total * 100
            print(f"  {regime:12s}: {row[regime]:5d} candles ({pct:.1f}%)")

# ---- Save regime mapping for backtesting ----
# Create a CSV with date, regime for each candle
regime_csv = df[['date', 'regime_simple', 'sma_200d', 'price_dist', 'vol_24h']].copy()
regime_csv.to_csv('/freqtrade/user_data/data/external/regime_classification.csv', index=False)
print()
print(f"Saved regime classification to: /freqtrade/user_data/data/external/regime_classification.csv")
print()

# ---- Identify key date ranges for backtesting ----
print("=" * 80)
print("KEY REGIME PERIODS FOR BACKTESTING")
print("=" * 80)

# Group consecutive same-regime periods
def get_periods(regime_name):
    mask = df['regime_simple'] == regime_name
    groups = df[mask].groupby((~mask).cumsum())  # not quite right, use segment approach
    return []

# Instead, use the segments we already found
for regime in ['BULL', 'BEAR', 'SIDEWAYS']:
    regime_segs = segments[segments['regime_simple'] == regime]
    regime_segs = regime_segs[regime_segs['candles'] >= 24]  # >= 1 day
    
    if len(regime_segs) == 0:
        print(f"\n{regime}: No significant periods found")
        continue
    
    print(f"\n{regime} periods:")
    for _, seg in regime_segs.iterrows():
        print(f"  {seg['start']} → {seg['end']} ({seg['candles']/24:.0f} days, {seg['return_pct']:+.2f}%)")
