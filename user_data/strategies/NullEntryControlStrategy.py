# NullEntryControlStrategy.py — the coin-flip test
# ============================================================
# Isolates the ENTRY signal by holding the exit machinery fixed.
#
# V2.1 (BtcTrendFollowingV21Strategy) result A: 139 trades, PF 0.976, p=0.93.
# Its entry = regime BULL + signal_score>=4 + higher-high. Its exits =
# SMA50 structural + 48-candle time stop (no trailing, -5% disaster stop).
#
# THIS strategy keeps IDENTICAL exits but replaces the entry with a
# NULL signal: enter every N candles unconditionally (zero market info).
# If null-entry PF ≈ 0.976 (or the null entry does no worse), the V2.1
# entry carries no information — it's a coin flip, not an edge.
# ============================================================

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade


class NullEntryControlStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True
    startup_candle_count = 200

    stoploss = -0.05
    minimal_roi = {}
    trailing_stop = False

    # Entry cadence in candles. 126 candles ≈ 5.25 days → ~139 trades over
    # the 2-year window, matching V2.1's trade count for a clean comparison.
    ENTRY_CADENCE = 126

    order_types = {"entry": "limit", "exit": "limit", "stoploss": "market", "stoploss_on_exchange": False}
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # NULL entry: every ENTRY_CADENCE candles, unconditional. No regime, no score.
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[dataframe.index % self.ENTRY_CADENCE == 0, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # IDENTICAL structural exit to V2.1: close below SMA50.
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[dataframe['close'] < dataframe['sma_50'], 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: pd.Timestamp,
                    current_rate: float, current_profit: float, **kwargs):
        # IDENTICAL time stop to V2.1: exit after 48 candles if at a loss.
        if trade.open_date_utc is None:
            return None
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
        return None
