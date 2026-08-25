#!/usr/bin/env python3
"""
backfill_macro.py
=================
Backfills 2 years of macro factors (2024-08-01 → today) to extend
market_regime_history.json beyond its current 365-day window.

IMPORTANT: writes to market_regime_history_2yr.json — a SEPARATE file —
so it never disturbs a running backtest that reads market_regime_history.json.
Swap it in after the in-flight experiment completes.

Coverage per factor:
  - fear_and_greed     : alternative.me API — FULL history (2018+) ✅
  - funding_rate       : Binance fapi paginated — FULL history ✅
  - stablecoin_supply  : DefiLlama — FULL history ✅
  - dxy / spy          : yfinance start=2024-08-01 — FULL ✅
  - open_interest      : Binance futures/data — rolling 30d only ⚠️ (kept from existing file / neutral)
  - long_short_ratio   : Binance futures/data — rolling 30d only ⚠️ (kept from existing file / neutral)
"""

import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "external"
EXISTING_FILE = DATA_DIR / "market_regime_history.json"
OUT_FILE = DATA_DIR / "market_regime_history_2yr.json"

START_DATE = "2024-08-01"  # matches the 2-year backtest window
HTTP_TIMEOUT = 15


def fetch_json(url: str, timeout: int = HTTP_TIMEOUT):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FreqtradeFactorCollector/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[WARN] Error fetching {url}: {e}")
        return None


def backfill_fear_and_greed():
    """alternative.me FNG — full history, paginated."""
    history = {}
    url = "https://api.alternative.me/fng/?limit=0&format=json"
    data = fetch_json(url)
    if data and "data" in data:
        for item in data["data"]:
            try:
                ts = int(item["timestamp"])
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                if dt.strftime("%Y-%m-%d") >= START_DATE:
                    history[dt.strftime("%Y-%m-%d")] = int(item["value"])
            except Exception:
                continue
    print(f"   fear_and_greed: {len(history)} days ({min(history) if history else '-'} → {max(history) if history else '-'})")
    return history


def backfill_funding_rate():
    """Binance fapi fundingRate — paginate startTime/endTime in 90-day chunks."""
    history = {}
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int(datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
    chunk_ms = 90 * 24 * 3600 * 1000
    cursor = start_ms
    while cursor < end_ms:
        url = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT"
               f"&startTime={cursor}&endTime={min(cursor + chunk_ms, end_ms)}&limit=1000")
        data = fetch_json(url)
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for item in data:
            ts_ms = int(item["fundingTime"])
            dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            rate = float(item["fundingRate"])
            history.setdefault(dt_str, []).append(rate)
        last_ts = data[-1]["fundingTime"]
        cursor = int(last_ts) + 1
        time.sleep(0.3)  # be gentle with the API
    history = {k: (sum(v) / len(v)) for k, v in history.items()}
    print(f"   funding_rate: {len(history)} days ({min(history) if history else '-'} → {max(history) if history else '-'})")
    return history


def backfill_stablecoin_supply():
    """DefiLlama stablecoin charts — full history."""
    history = {}
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    data = fetch_json(url)
    if data and isinstance(data, list) and len(data) > 0:
        for item in data:
            try:
                ts = int(item["date"])
                dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                if dt_str >= START_DATE:
                    val = float(item["totalCirculating"].get("peggedUSD", 0))
                    if val > 0:
                        history[dt_str] = val
            except Exception:
                continue
    print(f"   stablecoin_supply: {len(history)} days ({min(history) if history else '-'} → {max(history) if history else '-'})")
    return history


def backfill_yfinance():
    """DXY + SPY from yfinance, full 2-year window."""
    dxy_hist, spy_hist = {}, {}
    try:
        tickers = yf.Tickers("DX-Y.NYB SPY")
        df = tickers.history(start=START_DATE)
        if not df.empty and "Close" in df.columns:
            close_df = df["Close"]
            if "DX-Y.NYB" in close_df.columns:
                for dt, val in close_df["DX-Y.NYB"].dropna().items():
                    dxy_hist[dt.strftime("%Y-%m-%d")] = float(val)
            if "SPY" in close_df.columns:
                for dt, val in close_df["SPY"].dropna().items():
                    spy_hist[dt.strftime("%Y-%m-%d")] = float(val)
    except Exception as e:
        print(f"   [WARN] yfinance failed: {e}")
    print(f"   dxy: {len(dxy_hist)} days | spy: {len(spy_hist)} days")
    return dxy_hist, spy_hist


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Backfilling macro factors from {START_DATE}...")

    fng = backfill_fear_and_greed()
    funding = backfill_funding_rate()
    sc = backfill_stablecoin_supply()
    dxy, spy = backfill_yfinance()

    # Open interest & long/short: NOT backfillable (rolling 30d API).
    # Carry over whatever the existing history file has; gaps fall through to neutral fill.
    existing = {}
    if EXISTING_FILE.exists():
        with open(EXISTING_FILE) as f:
            for rec in json.load(f):
                existing[rec["date"]] = rec
    oi_hist = {d: r.get("open_interest") for d, r in existing.items() if r.get("open_interest")}
    ls_hist = {d: r.get("long_short_ratio") for d, r in existing.items() if r.get("long_short_ratio")}
    print(f"   open_interest: {len(oi_hist)} days (existing only — API rolling 30d) ⚠️")
    print(f"   long_short_ratio: {len(ls_hist)} days (existing only — API rolling 30d) ⚠️")

    all_dates = set(
        list(fng.keys()) + list(funding.keys()) + list(sc.keys())
        + list(dxy.keys()) + list(spy.keys()) + list(oi_hist.keys()) + list(ls_hist.keys())
    )
    all_dates = {d for d in all_dates if d >= START_DATE}

    rows = []
    for dt_str in sorted(all_dates):
        rows.append({
            "date": dt_str,
            "fear_and_greed": fng.get(dt_str),
            "funding_rate": funding.get(dt_str),
            "open_interest": oi_hist.get(dt_str),
            "long_short_ratio": ls_hist.get(dt_str),
            "stablecoin_supply": sc.get(dt_str),
            "dxy": dxy.get(dt_str),
            "spy": spy.get(dt_str),
        })

    df = pd.DataFrame(rows).sort_values("date")
    df.ffill(inplace=True)
    df.bfill(inplace=True)
    df.fillna({
        "fear_and_greed": 50, "funding_rate": 0.0001, "open_interest": 100000,
        "long_short_ratio": 1.0, "stablecoin_supply": 150000000000, "dxy": 100.0, "spy": 500.0,
    }, inplace=True)

    clean = df.to_dict("records")
    with open(OUT_FILE, "w") as f:
        json.dump(clean, f, indent=2)
    print(f"Saved {len(clean)} days -> {OUT_FILE}")
    print(f"Range: {clean[0]['date']} → {clean[-1]['date']}")
    print("[DONE]")


if __name__ == "__main__":
    main()
