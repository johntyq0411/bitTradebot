import json
from pathlib import Path
import pandas as pd

with open('/freqtrade/user_data/config_baseline.json') as f:
    config = json.load(f)

exchange = config.get('exchange', {}).get('name', 'binanceus')
datadir = config.get('datadir', '/freqtrade/user_data/data/binance')
print(f'Exchange: {exchange}')
print(f'datadir: {datadir}')
print()

# Check what data files exist
binance_dir = Path('/freqtrade/user_data/data/binance')
binanceus_dir = Path('/freqtrade/user_data/data/binanceus')

print('=== data/binance/ ===')
for f in sorted(binance_dir.iterdir()):
    sz = f.stat().st_size
    print(f'  {f.name}: {sz/1024:.0f} KB')

print()
print('=== data/binanceus/ ===')
for f in sorted(binanceus_dir.iterdir()):
    sz = f.stat().st_size
    print(f'  {f.name}: {sz/1024:.0f} KB')

# Now check what the backtester actually loads
print()
print('=== Simulating Freqtrade data lookup ===')

# Try loading from datadir directly
pair_file = datadir / 'BTC_USDT-1h.feather'
if pair_file.exists():
    df = pd.read_feather(str(pair_file))
    print(f'Loaded from datadir: {len(df)} rows, {df["date"].min()} to {df["date"].max()}')
else:
    print(f'NOT FOUND in datadir: {pair_file}')

# Check if there's an exchange subdirectory within datadir
exchange_dir = datadir / exchange
if exchange_dir.exists():
    print(f'\nExchange subdir exists: {exchange_dir}')
    for f in sorted(exchange_dir.iterdir()):
        sz = f.stat().st_size
        print(f'  {f.name}: {sz/1024:.0f} KB')
        if '1h' in f.name:
            df2 = pd.read_feather(str(f))
            print(f'    -> {len(df2)} rows, {df2["date"].min()} to {df2["date"].max()}')
else:
    print(f'\nNo exchange subdir: {exchange_dir}')
