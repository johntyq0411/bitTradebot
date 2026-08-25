# BtcTrendFollowingV2Strategy.py
# ============================================================
# Modest-Bohr V2 — Trend-following strategy for BTC/USDT
# Freqtrade IStrategy implementation
#
# Design:
#   - Regime-aware: only trade during Bull Trending regime
#   - Multi-component trend signal: MA position, slope, ADX, structure, momentum
#   - Long-only (no shorts in V2)
#   - ATR-based trailing stop, structural exit, time stop
#   - No fixed ROI target — let winners run
#
# Validation protocol: see docs/SPEC_V2.md Section 7
# ============================================================

from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade

from functools import reduce

# -----------------------------------------------------------
# Configuration
# -----------------------------------------------------------

class BtcTrendFollowingV2Strategy(IStrategy):
    """
    V2 Trend-Following Strategy for BTC/USDT (1h timeframe)
    
    Regime-aware trend-following with multi-component signal confirmation.
    Only enters long positions during confirmed bull trends.
    Uses ATR-based trailing stops and structural exits.
    """
    
    # --- Basic config ---
    timeframe = '1h'
    can_short = False  # Long-only in V2
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi = True  # No fixed ROI — structural/trailing exits only
    
    # --- Risk parameters ---
    minimal_roi = {
        "0": 1  # Effectively disabled — we use structural/trailing exits
    }
    stoploss = -0.99  # Emergency stop only — real stops are trailing/structural
    
    # --- Exit configuration ---
    exit_rewards = {
        "simple_trailing_convergence": True
    }
    
    # Startup candle count — enough for 200 SMA + ADX + indicators
    startup_candle_count = 250
    
    # --- Stake settings (from config, not hardcoded) ---
    # stake_currency and stake_amount are in config.json
    
    # --- Order types ---
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC",
    }
    
    # --- Protection (optional, may enable later) ---
    # protections are not used in V2 initially
    
    # -----------------------------------------------------------
    # Indicator population
    # -----------------------------------------------------------
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all indicators needed for signal generation.
        Uses vectorized operations — no loops, no lookahead.
        """
        df = dataframe.copy()
        
        # -----------------------------------------------------------
        # Trend indicators
        # -----------------------------------------------------------
        
        # SMA 200 (1h) — ~8 days trend baseline
        # Note: 200 on 1h is relatively short. Consider using 4h informative
        # pair with SMA 50 for ~10-day equivalent in V2.1
        df['sma_200'] = ta.SMA(df, timeperiod=200)
        
        # SMA 50 (1h) — medium-term trend / structural exit level
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        
        # SMA slope — trend direction confirmation
        df['sma_200_slope'] = df['sma_200'] - df['sma_200'].shift(24)  # 24h = 1 day
        
        # ADX 14 — trend strength indicator
        df['adx'] = ta.ADX(df, timeperiod=14)
        
        # -----------------------------------------------------------
        # Momentum indicators
        # -----------------------------------------------------------
        
        # RSI 14
        df['rsi'] = ta.RSI(df, timeperiod=14)
        
        # Rate of change (24h = 1 day)
        df['roc_24'] = (df['close'] - df['close'].shift(24)) / df['close'].shift(24) * 100
        
        # ROC 48h (2 days) — medium-term momentum
        df['roc_48'] = (df['close'] - df['close'].shift(48)) / df['close'].shift(48) * 100
        
        # -----------------------------------------------------------
        # Volatility indicators
        # -----------------------------------------------------------
        
        # ATR 14 (absolute)
        df['atr'] = ta.ATR(df, timeperiod=14)
        
        # ATR as % of price — for relative volatility comparison
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # Bollinger Bands (20, 2) — for volatility regime and squeeze detection
        bb = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        df['bb_upper'] = bb['upperband']
        df['bb_middle'] = bb['middleband']
        df['bb_lower'] = bb['lowerband']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        
        # Realized volatility (24h rolling std annualized)
        df['returns'] = df['close'].pct_change()
        df['realized_vol_24h'] = df['returns'].rolling(24).std() * np.sqrt(24) * 100
        
        # -----------------------------------------------------------
        # Volume indicators
        # -----------------------------------------------------------
        
        # Volume SMA 50
        df['volume_sma_50'] = ta.SMA(df, timeperiod=50, price='volume')
        
        # Volume ratio (current / average)
        df['volume_ratio'] = df['volume'] / df['volume_sma_50']
        
        # Volume-weighted momentum (VWAP-like, 24h)
        df['vwap_24h'] = (df['close'] * df['volume']).rolling(24).sum() / df['volume'].rolling(24).sum()
        
        # -----------------------------------------------------------
        # Price structure indicators
        # -----------------------------------------------------------
        
        # Higher high / higher low detection (20 candle lookback)
        df['hh_20'] = df['high'].rolling(20).max()
        df['lh_20'] = df['low'].rolling(20).min()
        
        # Current candle is a higher high if close > previous 20-candle high
        # (shifted by 1 to avoid lookahead — we compare to past highs)
        df['is_hh'] = df['close'] > df['hh_20'].shift(1)
        
        # Higher low: current low > previous 20-candle low
        df['is_hl'] = df['low'] > df['lh_20'].shift(1)
        
        # Price distance from SMA 200 (%)
        df['price_dist_sma200'] = (df['close'] - df['sma_200']) / df['sma_200'] * 100
        
        # -----------------------------------------------------------
        # Regime classification (per candle)
        # -----------------------------------------------------------
        
        # Regime is computed from trend + volatility indicators
        # This is the regime gate — only trade when regime is favorable
        
        def classify_regime(row):
            """
            Classify market regime per candle.
            Uses price vs SMA200, SMA slope, ADX, and volatility.
            """
            if pd.isna(row['sma_200']) or pd.isna(row['adx']):
                return 'UNKNOWN'
            
            trend_direction = 1 if row['sma_200_slope'] > 0 else (-1 if row['sma_200_slope'] < 0 else 0)
            price_position = row['price_dist_sma200']
            trend_strength = row['adx']
            volatility = row['atr_pct']
            
            # Bull trending: price above SMA, SMA rising, ADX confirms trend
            if trend_direction > 0 and price_position > 2 and trend_strength > 20:
                return 'BULL'
            
            # Bear trending: price below SMA, SMA falling, ADX confirms trend
            if trend_direction < 0 and price_position < -2 and trend_strength > 20:
                return 'BEAR'
            
            # Sideways: price near SMA, low ADX, or low volatility
            if abs(price_position) < 3 or trend_strength < 20:
                if volatility < 2:  # Low volatility
                    return 'SIDEWAYS_LOWVOL'
                else:
                    return 'SIDEWAYS_HIGHVOL'
            
            # Transition: mixed signals
            return 'TRANSITION'
        
        df['regime'] = df.apply(classify_regime, axis=1)
        
        # Regime smoothing: require regime to persist for N candles to avoid whipsaw
        # For V2, we require at least 10 consecutive candles (10h) in same regime
        # before considering it "confirmed"
        df['regime_change'] = df['regime'] != df['regime'].shift(1)
        df['regime_streak'] = df['regime_change'].cumsum()
        
        # Count consecutive same-regime candles
        df['regime_duration'] = df.groupby('regime_streak').cumcount() + 1
        
        # Regime is "confirmed" if duration >= 10
        df['regime_confirmed'] = df['regime_duration'] >= 10
        
        # -----------------------------------------------------------
        # Signal components
        # -----------------------------------------------------------
        
        # Trend signal components (each is 0 or 1)
        
        # 1. Price above SMA200
        df['signal_price_above_sma'] = (df['close'] > df['sma_200']).astype(int)
        
        # 2. SMA200 slope positive
        df['signal_sma_slope'] = (df['sma_200_slope'] > 0).astype(int)
        
        # 3. ADX > 20 (trend strength)
        df['signal_adx'] = (df['adx'] > 20).astype(int)
        
        # 4. Price structure: higher high OR higher low (via is_hh / is_hl)
        # Use a rolling lookback: at least 3 of last 5 candles show higher high
        df['signal_structure'] = (
            df['is_hh'].rolling(5).sum() >= 3
        ).astype(int)
        
        # 5. Momentum confirmation: RSI > 50 AND rising, OR ROC > 0
        rsi_rising = df['rsi'] > df['rsi'].shift(1)
        df['signal_momentum'] = (
            ((df['rsi'] > 50) & rsi_rising) |
            (df['roc_24'] > 0)
        ).astype(int)
        
        # 6. Volume confirmation: volume > median of last 50 candles
        df['signal_volume'] = (
            df['volume_ratio'] > 1.0
        ).astype(int)
        
        # Combined trend signal score (0-6)
        df['trend_signal_score'] = (
            df['signal_price_above_sma'] +
            df['signal_sma_slope'] +
            df['signal_adx'] +
            df['signal_structure'] +
            df['signal_momentum'] +
            df['signal_volume']
        )
        
        # -----------------------------------------------------------
        # Entry / Exit signals
        # -----------------------------------------------------------
        
        # LONG ENTRY conditions:
        # - Regime is BULL AND regime is confirmed (>=10 candles)
        # - Trend signal score >= 4 (out of 6)
        # - No open trade
        # - Price is at or near current close (limit order at close)
        
        df['enter_long'] = 0
        
        long_conditions = (
            (df['regime'] == 'BULL') &
            (df['regime_confirmed'] == True) &
            (df['trend_signal_score'] >= 4) &
            (df['signal_price_above_sma'] == 1) &  # Hard requirement
            (df['signal_sma_slope'] == 1) &        # Hard requirement
            (df['signal_adx'] == 1)                # Hard requirement
        )
        
        df.loc[long_conditions, 'enter_long'] = 1
        
        # LONG EXIT conditions:
        # - Structural exit: close below SMA50 (trend broken)
        # - Trailing stop: price drops below highest close since entry minus ATR trailing
        # - Time stop: no profit after 48 candles (handled in check_exit_signal)
        
        df['exit_long'] = 0
        
        # Structural exit: price closed below SMA50 while in a trade
        df.loc[
            (df['close'] < df['sma_50']) &
            (df['close'].shift(1) >= df['sma_50'].shift(1))  # Triggered on cross, not already below
        , 'exit_long'] = 1
        
        # -----------------------------------------------------------
        # ATR trailing stop reference (calculated per candle)
        # This is used by check_exit_signal to determine if trailing stop is hit
        # -----------------------------------------------------------
        
        # Highest close since entry (approximated by rolling max)
        # For trailing stop: highest_close - (ATR * multiplier)
        # We store the reference so check_exit_signal can use it
        df['trailing_stop_ref'] = df['close'] - (df['atr'] * 1.5)
        
        return df
    
    # -----------------------------------------------------------
    # Entry signal
    # -----------------------------------------------------------
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signals are set in populate_indicators.
        This method is here for Freqtrade compatibility.
        """
        return dataframe
    
    # -----------------------------------------------------------
    # Exit signal
    # -----------------------------------------------------------
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals are set in populate_indicators.
        Structural exits are here; trailing stops handled in check_exit_signal.
        """
        return dataframe
    
    # -----------------------------------------------------------
    # Custom exit logic — trailing stop + time stop
    # -----------------------------------------------------------
    
    def check_exit_signal(
        self,
        dataframe: DataFrame,
        metadata: dict,
        current_time: pd.Timestamp,
        current_rate: float,
        current_profit: float,
        trade: Trade,
        **kwargs,
    ) -> bool:
        """
        Custom exit logic beyond structural exits:
        1. ATR-based trailing stop
        2. Time stop (exit if no profit after N candles)
        """
        # Get the stop loss from the trade
        if trade is None:
            return False
        
        # -----------------------------------------------------------
        # 1. ATR Trailing Stop
        # -----------------------------------------------------------
        # Trail stop at: highest_close_since_entry - (ATR * 1.5)
        # highest_close is approximated by tracking trade.open_rate and using
        # the dataframe to find the max close since entry
        
        entry_time = trade.open_date_utc
        entry_candle_idx = dataframe[dataframe['date'] == entry_time].index
        
        if len(entry_candle_idx) == 0:
            # Entry time not in this dataframe window — skip
            return False
        
        entry_idx = entry_candle_idx[0]
        current_idx = dataframe.index[-1]
        
        if current_idx < entry_idx:
            return False
        
        # Get the slice from entry to current
        trade_slice = dataframe.loc[entry_idx:current_idx]
        
        if len(trade_slice) == 0:
            return False
        
        # Highest close since entry
        highest_close = trade_slice['close'].max()
        
        # ATR at the current candle
        current_atr = trade_slice['atr'].iloc[-1]
        
        if pd.isna(current_atr) or current_atr <= 0:
            return False
        
        # Trailing stop level
        trailing_stop = highest_close - (current_atr * 1.5)
        
        # Check if current close is below trailing stop
        if current_rate < trailing_stop:
            self.logger.info(
                f"Trailing stop triggered for {trade.pair}: "
                f"current={current_rate:.2f}, trailing_stop={trailing_stop:.2f}, "
                f"highest={highest_close:.2f}, atr={current_atr:.2f}"
            )
            return True
        
        # -----------------------------------------------------------
        # 2. Time Stop — exit if no profit after 48 candles (2 days)
        # -----------------------------------------------------------
        trade_duration_candles = current_idx - entry_idx
        
        if trade_duration_candles >= 48 and current_profit < 0:
            self.logger.info(
                f"Time stop triggered for {trade.pair}: "
                f"duration={trade_duration_candles} candles, "
                f"profit={current_profit:.4f}"
            )
            return True
        
        return False
    
    # -----------------------------------------------------------
    # Custom stoploss (emergency only — real stops are trailing/structural)
    # -----------------------------------------------------------
    
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: pd.Timestamp,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Emergency stoploss — only used if trailing/structural exits fail.
        Return -0.99 (effectively disabled) — real risk management is in
        check_exit_signal and populate_exit_trend.
        """
        return -0.99
    
    # -----------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------
    
    def custom_network(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Placeholder helper method — returns dataframe unchanged."""
