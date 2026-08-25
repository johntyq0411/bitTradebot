# RegimeGatedTrendSMA200Strategy.py
# Variant: widest structural exit (SMA200) for bull-market capture.
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime, timedelta

class RegimeGatedTrendSMA200Strategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True
    use_custom_stoploss = False
    stoploss = -0.15
    trailing_stop = False
    startup_candle_count = 200

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['sma_100'] = ta.SMA(dataframe, timeperiod=100)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_bull_regime = (
            (dataframe['close'] > dataframe['sma_200']) &
            (dataframe['close'] > dataframe['ema_200_4h']) &
            (dataframe['adx'] > 20)
        )
        is_pullback = (dataframe['close'] < dataframe['sma_20'])
        dataframe.loc[(is_bull_regime & is_pullback), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] < dataframe['sma_200']), 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        if trade.open_date_utc is None:
            return None
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
        return None
