# BtcRegimeGatedTrendStrategy.py — V3.0 (evidence-driven redesign)
# ============================================================
# Built from the null-entry control finding: the ENTRY SIGNAL is worse
# than random (+30.3% null vs -2.83% engineered). The value lives in:
#   1. REGIME FILTER (stay out of bear) — the only entry-side structure worth keeping
#   2. EXITS (SMA50 structural + wide ATR trailing + time stop) — proven to work
#
# So V3.0 is DELIBERATELY DUMB on entry: enter whenever the bull regime
# filter is true (no signal score, no higher-high). Wide 2.5x ATR trailing
# (capped at 2% per Antigravity methodology) lets winners run. Low frequency.
# ============================================================

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade


class BtcRegimeGatedTrendStrategy(IStrategy):
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
    use_custom_stoploss = True

    order_types = {"entry": "limit", "exit": "limit", "stoploss": "market", "stoploss_on_exchange": False}
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        # Trend / regime filter
        df['sma_200'] = ta.SMA(df, timeperiod=200)
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        df['sma_200_slope'] = df['sma_200'] - df['sma_200'].shift(24)
        # Volatility for trailing
        df['atr'] = ta.ATR(df, timeperiod=14)
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SPARSE pullback entry: buy the recovery from a dip to SMA50, in a bull
        # regime. Cross-events are rare → low trade frequency (vs V3.0's dense
        # entry that churned 373 trades). Buys value, not breakout tops.
        dataframe['prev_close'] = dataframe['close'].shift(1)
        dataframe['prev_sma50'] = dataframe['sma_50'].shift(1)
        dataframe.loc[
            (dataframe['close'] > dataframe['sma_200']) &          # bull regime
            (dataframe['sma_200_slope'] > 0) &                     # rising trend
            (dataframe['close'] > dataframe['sma_50']) &           # recovered above 50
            (dataframe['prev_close'] <= dataframe['prev_sma50']),  # was at/below 50 (the dip)
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Structural exit: close below SMA50 (short-term trend broken).
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[dataframe['close'] < dataframe['sma_50'], 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: pd.Timestamp,
                        current_rate: float, current_profit: float, after_fill: bool = False,
                        **kwargs) -> float:
        """
        Wide 2.5x ATR trailing (capped at 2% of price per Antigravity methodology),
        never looser than -5% disaster stop.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or len(dataframe) < 15:
            return -0.05

        df = dataframe.tail(15)
        prev_close = df['close'].shift(1)
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum((df['high'] - prev_close).abs(), (df['low'] - prev_close).abs())
        )
        atr = float(tr.mean())
        # Cap ATR at 2% of price (Antigravity: prevent stop widening in vol spikes)
        atr = min(atr, current_rate * 0.02)
        max_rate = trade.max_rate or 0
        if atr <= 0 or max_rate <= 0:
            return -0.05

        stop_price = max_rate - 2.5 * atr
        if stop_price <= 0:
            return -0.05
        # Bound between 1.5% and 6% (Antigravity)
        sl = max((stop_price / current_rate) - 1, -0.05)
        return max(min(sl, -0.015), -0.06)

    def custom_exit(self, pair: str, trade: Trade, current_time: pd.Timestamp,
                    current_rate: float, current_profit: float, **kwargs):
        # Time stop: exit after 48 candles (2 days) if at a loss.
        if trade.open_date_utc is None:
            return None
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
        return None
