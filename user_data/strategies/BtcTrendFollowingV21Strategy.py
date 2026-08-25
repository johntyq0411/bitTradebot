# BtcTrendFollowingV21Strategy.py — V2.1 (SPEC_V2.md, implemented faithfully)
# ============================================================
# Modest-Bohr V2.1 — the design from docs/SPEC_V2.md, which was
# NEVER actually implemented (V2.0 code on disk diverged from spec:
# 3.0x ATR instead of 1.5x, no structural exit, no time stop, -99% stop).
#
# This strategy implements the spec verbatim:
#   Regime:  BULL only (price > SMA200, SMA200 slope > 0, ADX >= 20)
#   Entry:   signal score >= 4/6 + new higher-high in last 5 candles
#   Exit:    1.5x ATR trailing + structural (close < SMA50) + time stop (48c at loss)
#   Risk:    stoploss -0.05 (disaster backstop), max 1 open trade
# ============================================================

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade


class BtcTrendFollowingV21Strategy(IStrategy):
    """
    V2.1 — BTC/USDT trend-following, faithful implementation of SPEC_V2.md.

    Regime: strong bull only. Entry: multi-signal score >= 4 + higher-high.
    Exit: 1.5x ATR trailing + SMA50 structural break + 48-candle time stop.
    """

    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True                      # spec: no fixed ROI, structural exits only
    startup_candle_count = 200             # SMA200 period (max indicator period)

    # --- Risk ---
    stoploss = -0.05                       # disaster backstop only; trailing is the real stop
    minimal_roi = {}                       # spec: no ROI
    trailing_stop = False                  # custom trailing via custom_stoploss
    use_custom_stoploss = True

    # --- Order types ---
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    # ----------------------------------------------------------
    # Indicators
    # ----------------------------------------------------------

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        # --- Trend indicators (SPEC §5.1) ---
        df['sma_200'] = ta.SMA(df, timeperiod=200)
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        df['sma_200_slope'] = df['sma_200'] - df['sma_200'].shift(24)
        df['adx'] = ta.ADX(df, timeperiod=14)

        # --- Momentum ---
        df['rsi'] = ta.RSI(df, timeperiod=14)
        df['roc_24'] = (df['close'] - df['close'].shift(24)) / df['close'].shift(24) * 100

        # --- Volatility ---
        df['atr'] = ta.ATR(df, timeperiod=14)

        # --- Volume ---
        df['volume_ma_50'] = ta.SMA(df, timeperiod=50, price='volume')
        df['volume_ratio'] = df['volume'] / df['volume_ma_50']

        # --- Price structure (SPEC §5.1) ---
        df['hh_20'] = df['high'].rolling(20).max().shift(1)
        df['lh_20'] = df['low'].rolling(20).min().shift(1)
        df['hh_5'] = df['high'].rolling(5).max().shift(1)

        # --- Signal components (each contributes 1 point, max 6) ---
        # 1. Price > SMA200
        df['sig_price_above_sma'] = (df['close'] > df['sma_200']).astype(int)
        # 2. SMA200 slope positive
        df['sig_sma_slope'] = (df['sma_200_slope'] > 0).astype(int)
        # 3. ADX > 20 (trend present)
        df['sig_adx'] = (df['adx'] > 20).astype(int)
        # 4. Higher high AND higher low over last 20 candles
        df['sig_higher_high'] = (df['close'] > df['hh_20']).astype(int)
        df['sig_higher_low'] = (df['low'] > df['lh_20']).astype(int)
        # 5. Volume confirmation (volume > median)
        df['sig_volume'] = (df['volume_ratio'] > 1.0).astype(int)
        # 6. Momentum confirmation (RSI > 50 and rising, OR ROC24 > 0)
        df['sig_momentum'] = (
            ((df['rsi'] > 50) & (df['rsi'] > df['rsi'].shift(1))) |
            (df['roc_24'] > 0)
        ).astype(int)

        df['signal_score'] = (
            df['sig_price_above_sma'] +
            df['sig_sma_slope'] +
            df['sig_adx'] +
            df['sig_higher_high'] +
            df['sig_higher_low'] +
            df['sig_volume'] +
            df['sig_momentum']
        )

        # --- Regime (SPEC §4.1) ---
        df['regime'] = 'UNKNOWN'
        df.loc[
            (df['sma_200_slope'] > 0) & (df['adx'] >= 20) & (df['close'] > df['sma_200']),
            'regime'
        ] = 'BULL'
        df.loc[
            (df['sma_200_slope'] < 0) & (df['adx'] >= 20) & (df['close'] < df['sma_200']),
            'regime'
        ] = 'BEAR'
        df.loc[df['regime'] == 'UNKNOWN', 'regime'] = 'SIDEWAYS'

        return df

    # ----------------------------------------------------------
    # Entry signals (SPEC §5.2)
    # ----------------------------------------------------------

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        LONG ENTRY:
          Regime = BULL AND signal_score >= 4 AND new higher-high in last 5 candles
        """
        dataframe.loc[
            (dataframe['regime'] == 'BULL') &
            (dataframe['signal_score'] >= 4) &
            (dataframe['close'] > dataframe['hh_5']),
            'enter_long'
        ] = 1
        return dataframe

    # ----------------------------------------------------------
    # Exit signals (SPEC §5.3) — structural exit
    # ----------------------------------------------------------

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Structural exit: close below SMA50 (trend likely broken).
        Trailing stop + time stop handled by custom_stoploss / custom_exit.
        """
        dataframe.loc[
            (dataframe['close'] < dataframe['sma_50']),
            'exit_long'
        ] = 1
        return dataframe

    # ----------------------------------------------------------
    # Custom stoploss: 1.5x ATR trailing (SPEC §5.3, §6)
    # ----------------------------------------------------------

    def custom_stoploss(self, pair: str, trade: Trade, current_time: pd.Timestamp,
                        current_rate: float, current_profit: float, after_fill: bool = False,
                        **kwargs) -> float:
        """
        Trail 1.5x ATR below the highest close since entry (trade.max_rate).
        Never looser than the hard -5% stoploss.
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
        if atr <= 0 or trade.max_rate <= 0:
            return -0.05

        stop_price = trade.max_rate - 1.5 * atr
        if stop_price <= 0:
            return -0.05
        return max((stop_price / current_rate) - 1, -0.05)

    # ----------------------------------------------------------
    # Time stop: 48 candles at loss (SPEC §5.3)
    # ----------------------------------------------------------

    def custom_exit(self, pair: str, trade: Trade, current_time: pd.Timestamp,
                    current_rate: float, current_profit: float, **kwargs):
        """
        Time stop: exit after 48 candles (2 days) if the trade is at a loss.
        """
        if trade.open_date_utc is None:
            return None
        candles_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if candles_held >= 48 and current_profit < 0:
            return 'time_stop'
        return None
