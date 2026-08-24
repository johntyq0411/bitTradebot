"""
BtcRsiMeanReversionStrategy — Baseline #2: RSI Mean Reversion
================================================================
Buy when RSI is oversold (< 35), sell when overbought (> 65).
No trend filter — pure contrarian mean reversion.
Tests whether RSI extremes have predictive power on BTC/USDT 1h.
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class BtcRsiMeanReversionStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 30

    minimal_roi = {
        "0": 0.03,
        "60": 0.02,
        "120": 0.01,
    }
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi"] < 35) & (dataframe["close"] > dataframe["ema_200"]),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > 65),
            "exit_long",
        ] = 1
        return dataframe
