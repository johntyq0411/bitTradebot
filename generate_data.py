import math, json
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

np.random.seed(42)

DAYS        = 180
START_PRICE = 95_000.0
MU_ANNUAL   = 0.30
SIGMA_ANNUAL= 0.80
DT          = 1 / 8760

n        = DAYS * 24
sigma_h  = SIGMA_ANNUAL * math.sqrt(DT)
mu_h     = (MU_ANNUAL - 0.5 * SIGMA_ANNUAL**2) * DT

log_returns = np.random.normal(mu_h, sigma_h, n)
closes      = START_PRICE * np.exp(np.cumsum(log_returns))

end_ts   = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
start_ts = end_ts - timedelta(hours=n)

rows = []
for i in range(n):
    ts    = start_ts + timedelta(hours=i)
    close = float(closes[i])
    wick  = close * abs(float(np.random.normal(0, 0.007)))
    open_ = float(closes[i-1]) if i > 0 else START_PRICE
    high  = round(max(open_, close, close + wick), 2)
    low   = round(min(open_, close, close - wick), 2)
    vol   = round(abs(float(np.random.normal(1200, 400))), 4)
    rows.append([
        int(ts.timestamp() * 1000),
        round(open_, 2),
        high,
        low,
        round(close, 2),
        vol
    ])

out = Path("/Users/yuquanjohntan/Documents/antigravity/modest-bohr/user_data/data/binance/BTC_USDT-1h.json")
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w") as f:
    json.dump(rows, f)

print(f"Written {len(rows)} candles to {out}")
print(f"File size: {out.stat().st_size / 1024:.1f} KB")
print(f"First row: {rows[0]}")
print(f"Last row:  {rows[-1]}")
prices = [r[4] for r in rows]
print(f"Price range: ${min(prices):,.0f} - ${max(prices):,.0f}")
dt_start = datetime.fromtimestamp(rows[0][0]/1000, tz=timezone.utc)
dt_end   = datetime.fromtimestamp(rows[-1][0]/1000, tz=timezone.utc)
print(f"Date range: {dt_start} to {dt_end}")
