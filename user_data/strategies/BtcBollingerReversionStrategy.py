"""
BtcBollingerReversionStrategy — Baseline #3: Bollinger Band Reversion
========================================================================
Buy when price dips below lower Bollinger Band (20, 2), exit when
price returns toward middle band. Tests mean reversion to volatility bands.
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class BtcBollingerReversionStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 30

    minimal_roi = {
        "0": 0.035,
        "60": 0.02,
        "120": 0.01,
    }
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bband = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bband["lowerband"]
        dataframe["bb_middle"] = bband["middleband"]
        dataframe["bb_upper"] = bband["upperband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["bb_lower"]) & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["bb_middle"]) & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        return dataframe
