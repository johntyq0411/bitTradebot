#!/usr/bin/env python3
"""
factor_collector.py
===================
Ingests:
  1) Alternative.me Fear & Greed Index (Live + 180 days history)
  2) Coinglass / Binance US BTC Funding Rate (as macro pressure signal)
     NOTE: dYdX v3 API was permanently decommissioned in 2024. Replaced here.

Outputs structured metrics:
  - user_data/data/external/market_regime.json  (live state, consumed by live bot)
  - user_data/data/external/market_regime_history.json (180-day series for backtest)

Environment:
  FACTOR_DATA_DIR env var overrides the output path (useful in Docker).

Schedule:
  Run every 1 hour via cron or Docker sidecar.
  Example cron: 0 * * * * /usr/bin/python3 /freqtrade/user_data/scripts/factor_collector.py
"""

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import os

# Config: allow DATA_DIR override for Docker environments
_default_data_dir = Path(__file__).resolve().parent.parent / "data" / "external"
DATA_DIR = Path(os.environ.get("FACTOR_DATA_DIR", str(_default_data_dir)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

LIVE_FILE = DATA_DIR / "market_regime.json"
HIST_FILE = DATA_DIR / "market_regime_history.json"

HTTP_TIMEOUT = 10


def fetch_json(url: str, timeout: int = HTTP_TIMEOUT):
    """Safe HTTP GET wrapper returning parsed JSON or None on failure."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FreqtradeFactorCollector/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[WARN] Error fetching {url}: {e}")
        return None


def collect_fear_and_greed():
    """
    Fetches Fear & Greed daily index and 180-day history from Alternative.me.
    Returns: (live_value: int, history: dict[str, int])
    """
    url = "https://api.alternative.me/fng/?limit=180"
    data = fetch_json(url)
    history = {}
    live_val = 50  # Neutral fallback

    if data and "data" in data:
        for idx, item in enumerate(data["data"]):
            try:
                ts = int(item["timestamp"])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                val = int(item["value"])
                history[dt.strftime("%Y-%m-%d")] = val
                if idx == 0:
                    live_val = val
            except Exception:
                continue
    return live_val, history


def collect_funding_rate():
    """
    Fetches BTC perpetual funding rate. Tries Binance US first, then Coinglass.
    Returns: (live_value: float, history: dict[str, float])
    """
    history = {}
    live_val = 0.0001  # Neutral fallback (0.01% per 8h)

    # Attempt 1: Binance US Funding Rate (public, no auth)
    url_binance = "https://api.binance.us/fapi/v1/fundingRate?symbol=BTCUSDT&limit=96"
    data = fetch_json(url_binance)

    if data and isinstance(data, list) and len(data) > 0:
        try:
            live_val = float(data[-1]['fundingRate'])
            for item in data:
                try:
                    ts_ms = int(item['fundingTime'])
                    dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    rate = float(item['fundingRate'])
                    if dt_str not in history:
                        history[dt_str] = []
                    history[dt_str].append(rate)
                except Exception:
                    continue
            for dt_str in history:
                history[dt_str] = sum(history[dt_str]) / len(history[dt_str])
            print(f"   [OK] Binance US funding rate: {live_val:.6f}")
            return live_val, history
        except Exception as e:
            print(f"   [WARN] Failed parsing Binance US funding data: {e}")

    # Attempt 2: Coinglass BTC funding rate proxy
    url_cg = "https://open-api.coinglass.com/public/v2/funding?symbol=BTC&interval=h8&limit=96"
    data = fetch_json(url_cg)

    if data and data.get("code") == "0" and data.get("data"):
        try:
            rates = data["data"]
            live_val = float(rates[0]['fundingRate']) if rates else live_val
            for item in rates:
                try:
                    ts_ms = int(item['createTime'])
                    dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    rate = float(item['fundingRate'])
                    if dt_str not in history:
                        history[dt_str] = []
                    history[dt_str].append(rate)
                except Exception:
                    continue
            for dt_str in history:
                history[dt_str] = sum(history[dt_str]) / len(history[dt_str])
            print(f"   [OK] Coinglass funding rate: {live_val:.6f}")
            return live_val, history
        except Exception as e:
            print(f"   [WARN] Failed parsing Coinglass data: {e}")

    print(f"   [WARN] All funding sources failed. Using neutral fallback: {live_val}")
    return live_val, history


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running factor collection...")

    live_fng, fng_hist = collect_fear_and_greed()
    print(f"   Fear & Greed (Live): {live_fng} ({len(fng_hist)} historical records)")

    live_funding, funding_hist = collect_funding_rate()
    print(f"   Funding Rate (Live): {live_funding:.6f} ({len(funding_hist)} daily records)")

    live_state = {
        "timestamp": int(time.time()),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "fear_and_greed": live_fng,
        "funding_rate": live_funding
    }

    all_dates = set(list(fng_hist.keys()) + list(funding_hist.keys()))
    historical_series = [
        {
            "date": dt_str,
            "fear_and_greed": fng_hist.get(dt_str, 50),
            "funding_rate": funding_hist.get(dt_str, 0.0001)
        }
        for dt_str in sorted(all_dates)
    ]

    with open(LIVE_FILE, "w") as f:
        json.dump(live_state, f, indent=2)
    print(f"   Saved live state -> {LIVE_FILE}")

    with open(HIST_FILE, "w") as f:
        json.dump(historical_series, f, indent=2)
    print(f"   Saved history ({len(historical_series)} days) -> {HIST_FILE}")
    print("[DONE]")


if __name__ == "__main__":
    main()
