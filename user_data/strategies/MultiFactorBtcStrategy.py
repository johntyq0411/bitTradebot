"""
MultiFactorBtcStrategy
======================
Multi-Factor Layered Bitcoin Trading Strategy for BTC/USDT 1h timeframe.
Combines:
  1) Macro Trend: 4h EMA 200
  2) Technical: 1h EMA 20/50 pullback + RSI 14
  3) Micro Volatility: ATR 14
  4) External factors: Fear & Greed Sentiment + Funding Rate

Fixes applied (2026-08-23):
  - Removed conflicting trailing_stop (ATR custom_stoploss handles trailing)
  - startup_candle_count raised to 800 (covers 4h EMA200 warmup)
  - Path to market_regime_history resolved via self.config (Docker-safe)
  - Pandas merge now uses .values to prevent index misalignment
  - Pullback filter corrected: price must be in EMA50<->EMA20 zone
  - Silent exception replaced with logger.warning
  - ATR expansion capped in custom_stoploss
"""

import logging
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class MultiFactorBtcStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    # 4h EMA200 needs 200 x 4h candles = 800 1h candles for warmup
    startup_candle_count: int = 800

    # Risk settings
    stoploss = -0.04
    use_custom_stoploss = True

    # ROI Targets: aggressive scaling out
    minimal_roi = {
        "0": 0.045,    # 4.5% profit target from start
        "120": 0.025,  # 2.5% after 2 hours
        "240": 0.012   # 1.2% after 4 hours
    }

    # NOTE: trailing_stop is intentionally DISABLED.
    # ATR-based trailing is handled dynamically inside custom_stoploss.
    # Enabling both simultaneously causes two competing stoploss mechanisms.
    trailing_stop = False

    # Hyperopt Parameters
    buy_rsi_lower = IntParameter(40, 50, default=45, space="buy", optimize=True)
    buy_rsi_upper = IntParameter(55, 65, default=60, space="buy", optimize=True)

    def informative_pairs(self):
        """Define 4h timeframe for macro trend alignment."""
        return [("BTC/USDT", "4h")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate indicators on 1h and merge 4h informative data."""
        # 1. Fetch 4h informative timeframe
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe="4h")
        informative['ema200'] = ta.EMA(informative, timeperiod=200)

        # Merge 4h into 1h
        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, "4h", ffill=True
        )

        # 2. Compute 1h Indicators
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 3. Load External Metrics (F&G + Funding Rate) to avoid lookahead bias
        # Defaults: neutral sentiment, slightly positive funding
        dataframe['fear_and_greed'] = 50
        dataframe['funding_rate'] = 0.0001

        # Resolve path via config for Docker-safety (avoids hardcoded Mac paths)
        user_data_dir = Path(self.config.get('user_data_dir', 'user_data'))
        hist_path = user_data_dir / 'data/external/market_regime_history.json'

        if hist_path.exists():
            try:
                with open(hist_path, 'r') as f:
                    hist_data = json.load(f)
                hist_df = pd.DataFrame(hist_data)
                if not hist_df.empty:
                    hist_df['date_key'] = pd.to_datetime(hist_df['date']).dt.date
                    dataframe['date_key'] = dataframe['date'].dt.date
                    merged = pd.merge(
                        dataframe,
                        hist_df[['date_key', 'fear_and_greed', 'funding_rate']],
                        on='date_key',
                        how='left'
                    )
                    # Use .values to prevent pandas index misalignment after merge
                    dataframe['fear_and_greed'] = merged['fear_and_greed'].fillna(50).values
                    dataframe['funding_rate'] = merged['funding_rate'].fillna(0.0001).values
                    dataframe.drop(columns=['date_key'], inplace=True, errors='ignore')
            except Exception as e:
                logger.warning(
                    f"MultiFactorBtcStrategy: Failed to load market regime factors "
                    f"from {hist_path}: {e} — running with neutral defaults."
                )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Multi-Factor Entry Rules:
          - Macro:     Close price must be above 4H EMA 200 (trend alignment)
          - Sentiment: Fear & Greed index between 25 (no capitulation) and 80 (no extreme FOMO)
          - Funding:   Funding rate positive but low (< 0.001) = healthy long momentum
          - Technical: EMA20 > EMA50 (uptrend); price IN pullback zone (between EMA50 and EMA20)
          - RSI:       Momentum confirmed in mid-range (not overbought/oversold extremes)
        """
        dataframe.loc[
            (
                # Macro: above 4h EMA200
                (dataframe['close'] > dataframe['ema200_4h']) &

                # Sentiment: Fear & Greed between 25 and 80
                (dataframe['fear_and_greed'] >= 25) &
                (dataframe['fear_and_greed'] <= 80) &

                # Funding Rate: positive but not overheated
                (dataframe['funding_rate'] > 0) &
                (dataframe['funding_rate'] < 0.001) &

                # Technical: short-term trend is up
                (dataframe['ema20'] > dataframe['ema50']) &

                # Pullback zone: price has pulled back INTO the EMA50<->EMA20 corridor
                # This is a true pullback entry, not a breakout chase
                (dataframe['close'] >= dataframe['ema50'] * 0.995) &
                (dataframe['close'] <= dataframe['ema20'] * 1.005) &

                # RSI confirmation: momentum is building, not overbought
                (dataframe['rsi'] >= self.buy_rsi_lower.value) &
                (dataframe['rsi'] <= self.buy_rsi_upper.value) &

                # Sanity: candle has volume
                (dataframe['volume'] > 0)
            ),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit when 1h EMA20 crosses below EMA50 (momentum reversal) or RSI is overbought."""
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['ema20'], dataframe['ema50']) |
                (dataframe['rsi'] > 80)
            ),
            'exit_long'
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs) -> float:
        """
        Dynamic ATR stoploss: risk 2.5 * ATR from current_rate.
        ATR is capped at 2% of current_rate to prevent stoploss from silently
        widening during high-volatility events (ATR expansion problem).
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=trade.pair, timeframe=self.timeframe)
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            atr = last_candle['atr']
            if atr > 0:
                # Cap ATR at 2% of current price to prevent runaway stoploss widening
                atr_cap = current_rate * 0.02
                atr = min(atr, atr_cap)
                atr_stop = -((2.5 * atr) / current_rate)
                # Bounds: Min 1.5%, Max 6%
                return max(min(atr_stop, -0.015), -0.06)
        return self.stoploss
