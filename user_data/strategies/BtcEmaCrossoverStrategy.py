"""
BtcEmaCrossoverStrategy — Baseline #1: EMA20/50 Crossover
==========================================================
Pure trend-following baseline. No ML, no macro, no volume filter.
Tests whether simple EMA crossover has any edge on BTC/USDT 1h.
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BtcEmaCrossoverStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 60

    minimal_roi = {
        "0": 0.04,
        "60": 0.025,
        "120": 0.015,
        "240": 0.01,
    }
    stoploss = -0.06

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
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_cross_above"] = qtpylib.crossed_above(
            dataframe["ema_20"], dataframe["ema_50"]
        )
        dataframe["ema_cross_below"] = qtpylib.crossed_below(
            dataframe["ema_20"], dataframe["ema_50"]
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe["ema_cross_above"],
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe["ema_cross_below"],
            "exit_long",
        ] = 1
        return dataframe
