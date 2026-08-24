#!/usr/bin/env python3
"""
factor_collector.py
===================
Ingests:
  1) Alternative.me Fear & Greed Index
  2) Binance BTC Funding Rate, Open Interest, Long/Short Ratio
  3) DefiLlama Total Stablecoin Market Cap
  4) Yahoo Finance DXY (US Dollar Index) and SPY (S&P 500)
"""

import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import pandas as pd
import yfinance as yf

_default_data_dir = Path(__file__).resolve().parent.parent / "data" / "external"
DATA_DIR = Path(os.environ.get("FACTOR_DATA_DIR", str(_default_data_dir)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

LIVE_FILE = DATA_DIR / "market_regime.json"
HIST_FILE = DATA_DIR / "market_regime_history.json"

HTTP_TIMEOUT = 10

def fetch_json(url: str, timeout: int = HTTP_TIMEOUT):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FreqtradeFactorCollector/3.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[WARN] Error fetching {url}: {e}")
        return None

def collect_fear_and_greed():
    url = "https://api.alternative.me/fng/?limit=365"
    data = fetch_json(url)
    history = {}
    live_val = 50
    if data and "data" in data:
        for idx, item in enumerate(data["data"]):
            try:
                ts = int(item["timestamp"])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                val = int(item["value"])
                history[dt.strftime("%Y-%m-%d")] = val
                if idx == 0: live_val = val
            except Exception:
                continue
    return live_val, history

def collect_funding_rate():
    history = {}
    live_val = 0.0001
    url = "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=96"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            live_val = float(data[-1]['fundingRate'])
            for item in data:
                ts_ms = int(item['fundingTime'])
                dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                rate = float(item['fundingRate'])
                if dt_str not in history: history[dt_str] = []
                history[dt_str].append(rate)
            for dt_str in history:
                history[dt_str] = sum(history[dt_str]) / len(history[dt_str])
        except Exception: pass
    return live_val, history

def collect_open_interest():
    history = {}
    live_val = 100000.0
    url = "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=30"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            live_val = float(data[-1]['sumOpenInterestValue'])
            for item in data:
                ts_ms = int(item['timestamp'])
                dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                history[dt_str] = float(item['sumOpenInterestValue'])
        except Exception: pass
    return live_val, history

def collect_long_short_ratio():
    history = {}
    live_val = 1.0
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1d&limit=30"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            live_val = float(data[-1]['longShortRatio'])
            for item in data:
                ts_ms = int(item['timestamp'])
                dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                history[dt_str] = float(item['longShortRatio'])
        except Exception: pass
    return live_val, history

def collect_stablecoin_supply():
    history = {}
    live_val = 150000000000.0
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            live_val = float(data[-1]['totalCirculating']['peggedUSD'])
            # Only keep last 365 days to save space
            for item in data[-365:]:
                ts = int(item['date'])
                dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                history[dt_str] = float(item['totalCirculating'].get('peggedUSD', live_val))
        except Exception: pass
    return live_val, history

def collect_yfinance_macro():
    """
    Downloads DXY and SPY using yfinance for the last 365 days.
    Returns: (live_dxy, dxy_hist, live_spy, spy_hist)
    """
    dxy_hist = {}
    spy_hist = {}
    live_dxy = 100.0
    live_spy = 500.0
    
    try:
        # Download last 6 months
        tickers = yf.Tickers("DX-Y.NYB SPY")
        df = tickers.history(period="6mo")
        if not df.empty and 'Close' in df.columns:
            close_df = df['Close']
            
            if 'DX-Y.NYB' in close_df.columns:
                dxy_series = close_df['DX-Y.NYB'].dropna()
                if not dxy_series.empty:
                    live_dxy = float(dxy_series.iloc[-1])
                    for dt, val in dxy_series.items():
                        dxy_hist[dt.strftime("%Y-%m-%d")] = float(val)
                        
            if 'SPY' in close_df.columns:
                spy_series = close_df['SPY'].dropna()
                if not spy_series.empty:
                    live_spy = float(spy_series.iloc[-1])
                    for dt, val in spy_series.items():
                        spy_hist[dt.strftime("%Y-%m-%d")] = float(val)
    except Exception as e:
        print(f"   [WARN] Failed yfinance download: {e}")
        
    return live_dxy, dxy_hist, live_spy, spy_hist

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running advanced macro factor collection...")

    live_fng, fng_hist = collect_fear_and_greed()
    live_funding, funding_hist = collect_funding_rate()
    live_oi, oi_hist = collect_open_interest()
    live_ls, ls_hist = collect_long_short_ratio()
    live_sc, sc_hist = collect_stablecoin_supply()
    live_dxy, dxy_hist, live_spy, spy_hist = collect_yfinance_macro()

    live_state = {
        "timestamp": int(time.time()),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "fear_and_greed": live_fng,
        "funding_rate": live_funding,
        "open_interest": live_oi,
        "long_short_ratio": live_ls,
        "stablecoin_supply": live_sc,
        "dxy": live_dxy,
        "spy": live_spy
    }

    all_dates = set(
        list(fng_hist.keys()) + list(funding_hist.keys()) + 
        list(oi_hist.keys()) + list(ls_hist.keys()) +
        list(sc_hist.keys()) + list(dxy_hist.keys()) + list(spy_hist.keys())
    )
    
    historical_series = []
    for dt_str in sorted(all_dates):
        historical_series.append({
            "date": dt_str,
            "fear_and_greed": fng_hist.get(dt_str, None),
            "funding_rate": funding_hist.get(dt_str, None),
            "open_interest": oi_hist.get(dt_str, None),
            "long_short_ratio": ls_hist.get(dt_str, None),
            "stablecoin_supply": sc_hist.get(dt_str, None),
            "dxy": dxy_hist.get(dt_str, None),
            "spy": spy_hist.get(dt_str, None)
        })

    # Convert to DataFrame to ffill missing values (like weekends for DXY/SPY)
    df = pd.DataFrame(historical_series).sort_values('date')
    df.ffill(inplace=True)
    df.bfill(inplace=True) # just in case beginning is missing
    
    # Fill any remaining NaNs with live values
    df.fillna({
        'fear_and_greed': 50,
        'funding_rate': 0.0001,
        'open_interest': 100000,
        'long_short_ratio': 1.0,
        'stablecoin_supply': 150000000000,
        'dxy': 100.0,
        'spy': 500.0
    }, inplace=True)

    clean_history = df.to_dict('records')

    with open(LIVE_FILE, "w") as f:
        json.dump(live_state, f, indent=2)
    print(f"   Saved live state -> {LIVE_FILE}")

    with open(HIST_FILE, "w") as f:
        json.dump(clean_history, f, indent=2)
    print(f"   Saved history ({len(clean_history)} days) -> {HIST_FILE}")
    print("[DONE]")

if __name__ == "__main__":
    main()
