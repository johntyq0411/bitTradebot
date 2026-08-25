# RegimeGatedTrendStrategy.py
# ============================================================
# This strategy implements the "Rank 1" evidence-driven approach
# validated by the Null-Entry Control revelation.
#
# Core Philosophy:
# 1. Prediction/entry timing is mostly noise.
# 2. Value comes from identifying the regime (staying out of bears)
#    and letting winners run with structural/trailing exits.
#
# Components:
# - Regime Filter: 4h EMA200 & 1h SMA200 + ADX (Bull market only)
# - Dumb Entry: Minor pullback to a short-term SMA (e.g. SMA20)
# - Exits: Structural (SMA50) + Custom ATR Trailing Stop (3x ATR)
# ============================================================

from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime, timedelta

class RegimeGatedTrendStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False
    
    # Disable standard ROI, but use exit signals
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True
    
    # CRITICAL: We are abandoning the ATR trailing stop entirely.
    # The structural SMA50 + time stop provides all the necessary defense.
    use_custom_stoploss = False
    
    # A wide disaster stop just in case the exchange behaves erratically
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
        # Long term 4h trend filter
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Base Timeframe Indicators (1h)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Regime Gating: Price must be above long-term averages + trend strength
        is_bull_regime = (
            (dataframe['close'] > dataframe['sma_200']) &
            (dataframe['close'] > dataframe['ema_200_4h']) &
            (dataframe['adx'] > 20)
        )
        
        # Dumb Entry: Just buy a simple pullback when the weather is good
        is_pullback = (
            (dataframe['close'] < dataframe['sma_20'])
        )

        dataframe.loc[
            (is_bull_regime & is_pullback),
            'enter_long'
        ] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Structural Exit: Close below the medium-term average (SMA50)
        dataframe.loc[
            (dataframe['close'] < dataframe['sma_50']),
            'exit_long'
        ] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        """
        Time Stop: Exit after 48 candles if we are in a loss.
        """
        if trade.open_date_utc is None:
            return None
            
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
            
        return None
