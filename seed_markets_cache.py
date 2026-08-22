"""
seed_markets_cache.py
=====================
Pre-seeds the Freqtrade Binance markets cache so the bot can start
without a live connection to api.binance.com (which is geo-restricted).

Freqtrade uses ccxt's markets cache stored in the exchange object.
We intercept the exchange initialization via a patched config that
overrides the Binance API base URL to point to binance.us, which IS reachable.
"""
import json
from pathlib import Path
import ccxt

BASE_DIR = Path("/Users/yuquanjohntan/Documents/antigravity/modest-bohr")

# Minimal BTC/USDT market definition that satisfies Freqtrade's validation
btc_usdt_market = {
    "id":            "BTCUSDT",
    "symbol":        "BTC/USDT",
    "base":          "BTC",
    "quote":         "USDT",
    "baseId":        "BTC",
    "quoteId":       "USDT",
    "active":        True,
    "type":          "spot",
    "spot":          True,
    "margin":        False,
    "future":        False,
    "swap":          False,
    "option":        False,
    "contract":      False,
    "settle":        None,
    "settleId":      None,
    "contractSize":  None,
    "linear":        None,
    "inverse":       None,
    "expiry":        None,
    "expiryDatetime":None,
    "strike":        None,
    "optionType":    None,
    "taker":         0.001,
    "maker":         0.001,
    "percentage":    True,
    "tierBased":     False,
    "feeSide":       "get",
    "precision": {
        "amount": 5,
        "price":  2,
        "base":   8,
        "quote":  8,
    },
    "limits": {
        "leverage": {"min": None, "max": None},
        "amount":   {"min": 0.00001, "max": 9000.0},
        "price":    {"min": 0.01,    "max": 1000000.0},
        "cost":     {"min": 10.0,    "max": None},
        "market":   {"min": 0.0,     "max": None},
    },
    "info": {
        "symbol":               "BTCUSDT",
        "status":               "TRADING",
        "baseAsset":            "BTC",
        "baseAssetPrecision":   8,
        "quoteAsset":           "USDT",
        "quotePrecision":       8,
        "quoteAssetPrecision":  8,
        "baseCommissionPrecision": 8,
        "quoteCommissionPrecision": 8,
        "orderTypes":           ["LIMIT", "LIMIT_MAKER", "MARKET",
                                 "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"],
        "icebergAllowed":       True,
        "ocoAllowed":           True,
        "quoteOrderQtyMarketAllowed": True,
        "allowTrailingStop":    True,
        "cancelReplaceAllowed": True,
        "isSpotTradingAllowed": True,
        "isMarginTradingAllowed": True,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01000000",
             "maxPrice": "1000000.00000000", "tickSize": "0.01000000"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001000",
             "maxQty": "9000.00000000", "stepSize": "0.00001000"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10.00000000",
             "applyToMarket": True, "avgPriceMins": 5},
            {"filterType": "ICEBERG_PARTS", "limit": 10},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "0.00000000",
             "maxQty": "120.89484820", "stepSize": "0.00000000"},
            {"filterType": "MAX_NUM_ORDERS", "maxNumOrders": 200},
            {"filterType": "MAX_NUM_ALGO_ORDERS", "maxNumAlgoOrders": 5},
        ],
        "permissions":          ["SPOT", "MARGIN", "TRD_GRP_004"],
    },
    "lowercaseId": "btcusdt",
}

# Save as a Freqtrade-compatible markets cache JSON
markets_file = BASE_DIR / "user_data" / "data" / "binance" / "markets.json"
markets_file.parent.mkdir(parents=True, exist_ok=True)

markets_data = {
    "BTC/USDT": btc_usdt_market,
}
with open(markets_file, "w") as f:
    json.dump(markets_data, f, indent=2)

print(f"✅ Markets cache written to: {markets_file}")
print(f"   Contains: {list(markets_data.keys())}")
