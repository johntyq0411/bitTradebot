"""
BtcMaTrendStrategy — Baseline #4: 200 SMA Trend + Pullback Entry
====================================================================
Only trade in direction of 200 SMA trend. Enter on pullback to EMA20
within an uptrend, exit on breakdown or RSI overbought.
Tests trend-filtered pullback trading.
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BtcMaTrendStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 200

    minimal_roi = {
        "0": 0.04,
        "60": 0.025,
        "120": 0.015,
        "240": 0.01,
    }
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Uptrend: price above 200 SMA, pullback to EMA20, RSI not extreme
        dataframe.loc[
            (dataframe["close"] > dataframe["sma_200"]) &
            (dataframe["close"] <= dataframe["ema_20"] * 1.01) &
            (dataframe["rsi"] >= 40) & (dataframe["rsi"] <= 65) &
            (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["sma_200"]) |
            (dataframe["rsi"] > 75),
            "exit_long",
        ] = 1
        return dataframe
