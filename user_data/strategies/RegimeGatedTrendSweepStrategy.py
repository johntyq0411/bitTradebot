# RegimeGatedTrendSweepStrategy.py
# Parameterized copy of RegimeGatedTrendSMA200Strategy for sensitivity analysis.
# Parameters are read from config (sweep_trend_sma, sweep_pullback_sma, sweep_adx)
# so a driver can sweep them WITHOUT regenerating strategy files.
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime


class RegimeGatedTrendSweepStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True
    use_custom_stoploss = False
    stoploss = -0.15
    trailing_stop = False
    startup_candle_count = 250

    order_types = {"entry": "limit", "exit": "limit",
                   "stoploss": "market", "stoploss_on_exchange": False}
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def _params(self):
        c = getattr(self, 'config', {}) or {}
        return (
            int(c.get('sweep_trend_sma', 200)),
            int(c.get('sweep_pullback_sma', 20)),
            float(c.get('sweep_adx', 20)),
        )

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_sma, pullback_sma, adx_thr = self._params()
        dataframe['trend_sma'] = ta.SMA(dataframe, timeperiod=trend_sma)
        dataframe['pullback_sma'] = ta.SMA(dataframe, timeperiod=pullback_sma)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_sma, pullback_sma, adx_thr = self._params()
        is_bull = (
            (dataframe['close'] > dataframe['trend_sma']) &
            (dataframe['close'] > dataframe['ema_200_4h']) &
            (dataframe['adx'] > adx_thr)
        )
        is_pullback = dataframe['close'] < dataframe['pullback_sma']
        dataframe.loc[(is_bull & is_pullback), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] < dataframe['trend_sma']), 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        if trade.open_date_utc is None:
            return None
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
        return None
