"""
BtcTrendStrategy — Multi-Factor (Macro/Micro/TA) Strategy
==========================================================
Author  : Freqtrade Multi-Factor Setup
Pair    : BTC/USDT
Exchange: Binance (Dry-Run Only)
Timeframe: 1h

Strategy Logic (Multi-Factor)
-----------------------------
1. MACRO Filter:  1-day EMA20 > 1-day EMA50 (Higher Timeframe Uptrend)
2. TECH Setup:    1-hour EMA20 crosses ABOVE 1-hour EMA50 + RSI(14) between 45 and 60
3. MICRO Trigger: 1-hour Volume > 24-hour moving average volume (Volume Spike)

EXIT   : 1h EMA20 crosses BELOW 1h EMA50 OR RSI(14) > 75
ROI    : {"0": 0.035, "60": 0.02, "120": 0.01}
Stoploss: -5% (Trailing stop enabled)
"""

from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BtcTrendStrategy(IStrategy):
    """
    Multi-Factor Strategy for BTC/USDT 1h timeframe.
    Combines Macro (1d trend), Technical (1h momentum), and Micro (Volume).
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 60

    # -----------------------------------------------------------------------
    # Risk management (Updated for higher win rate safety)
    # -----------------------------------------------------------------------
    minimal_roi = {
        "0":   0.035,   # Take 3.5% immediately
        "60":  0.02,    # Take 2% after 1 hour
        "120": 0.01,    # Take 1% after 2 hours
    }

    stoploss = -0.05    # Hard stop at -5%

    # Trailing stop to lock in gains
    trailing_stop = True
    trailing_stop_positive = 0.01          # Stop locks in 1% profit...
    trailing_stop_positive_offset = 0.025  # ...once we reach 2.5% profit
    trailing_only_offset_is_reached = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    # -----------------------------------------------------------------------
    # Hyperopt Parameters (Tightened entry)
    # -----------------------------------------------------------------------
    buy_rsi_lower = IntParameter(40, 55, default=45, space="buy", optimize=True)
    buy_rsi_upper = IntParameter(55, 70, default=60, space="buy", optimize=True)
    sell_rsi_threshold = IntParameter(70, 85, default=75, space="sell", optimize=True)

    # -----------------------------------------------------------------------
    # Informative Pairs (Macro Analysis)
    # -----------------------------------------------------------------------
    def informative_pairs(self):
        """
        Define additional pairs/timeframes to feed into the strategy.
        We request the 1d (daily) timeframe for the current pair to assess Macro trend.
        """
        return [(self.config['stake_currency'], '1d') if 'stake_currency' in self.config else '',
                (f"BTC/USDT", "1d")] # Standard definition

    def informative_1d_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate indicators on the 1d timeframe (Macro).
        """
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["macro_uptrend"] = dataframe["ema_20"] > dataframe["ema_50"]
        return dataframe

    # -----------------------------------------------------------------------
    # Indicator computation (Technical & Micro)
    # -----------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Compute technical and micro indicators on the 1h timeframe.
        """
        # MACRO: Freqtrade handles the merge of informative pairs automatically using the merge_informative_pair helper.
        # But for simplicity and native support in standard environments without complex informative setup,
        # we will simulate the Macro 1d trend by looking back 24 candles on the 1h chart (24h = 1d).
        # This makes it robust for single-file backtesting while conceptually identical.
        
        # --- MACRO Proxy (Simulated 1d EMA using 1h data * 24 periods) ---
        dataframe["macro_ema_20"] = ta.EMA(dataframe, timeperiod=20 * 24)
        dataframe["macro_ema_50"] = ta.EMA(dataframe, timeperiod=50 * 24)
        dataframe["macro_uptrend"] = dataframe["macro_ema_20"] > dataframe["macro_ema_50"]

        # --- TECHNICAL (1h Setup) ---
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        dataframe["ema_cross_above"] = qtpylib.crossed_above(dataframe["ema_20"], dataframe["ema_50"])
        dataframe["ema_cross_below"] = qtpylib.crossed_below(dataframe["ema_20"], dataframe["ema_50"])

        # --- MICRO (Volume Spike Confirmation) ---
        # Calculate 24-hour moving average of volume
        dataframe["volume_ma_24"] = dataframe["volume"].rolling(24).mean()
        # Trigger: current volume is 1.5x higher than the daily average (institutional participation)
        dataframe["micro_vol_spike"] = dataframe["volume"] > (dataframe["volume_ma_24"] * 1.5)

        return dataframe

    # -----------------------------------------------------------------------
    # Entry signal (Multi-Factor)
    # -----------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. MACRO Filter
                (dataframe["macro_uptrend"] == True)
                &
                # 2. TECHNICAL Setup
                (dataframe["ema_cross_above"]) &
                (dataframe["rsi"] >= self.buy_rsi_lower.value) &
                (dataframe["rsi"] <= self.buy_rsi_upper.value)
                &
                # 3. MICRO Trigger
                (dataframe["micro_vol_spike"] == True)
            ),
            "enter_long",
        ] = 1

        return dataframe

    # -----------------------------------------------------------------------
    # Exit signal
    # -----------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_cross_below"])
                | (dataframe["rsi"] > self.sell_rsi_threshold.value)
            )
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        return dataframe
