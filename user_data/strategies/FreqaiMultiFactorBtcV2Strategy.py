import logging
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from datetime import datetime, timezone
import json
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class FreqaiMultiFactorBtcV2Strategy(IStrategy):
    """
    WFA-1Y-ML-002 — Wrapper fixes on top of FreqaiMultiFactorBtcStrategy.
    Model/features IDENTICAL to ML-001; only the trade wrapper changed:

    FIX 1 (win/loss asymmetry): minimal_roi disabled ({}), replaced by
        ATR-based trailing stop via custom_stoploss (2x ATR below max_rate).
        Winners can run; stoploss stays at -5% as disaster backstop.
    FIX 2 (horizon mismatch): custom_exit forces exit after 6h (2x the 3h
        prediction horizon) if profit < 1% — the signal has expired.
    FIX 3 (bear bleed): entry requires price > SMA200 (structural bull
        filter, independent of model features) — sits in cash in bear.
    """
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count = 200
    process_only_new_candles = True

    stoploss = -0.05
    minimal_roi = {}                      # FIX 1: disable ROI caps
    use_custom_stoploss = True            # FIX 1: ATR trailing instead
    use_exit_signal = True

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        """Create the features the AI will use to predict the future."""
        # Proper RSI (Wilder-style smoothing via ewm)
        delta = dataframe['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('inf'))
        dataframe[f'%-rsi-{period}'] = 100 - (100 / (1 + rs))

        dataframe[f'%-roc-{period}'] = dataframe['close'].pct_change(period)
        dataframe[f'%-volume-mean-{period}'] = dataframe['volume'].rolling(period).mean()
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Add external factors as features.
        Reads market_regime_history.json produced by factor_collector.py.
        """
        user_data_dir = Path(self.config.get('user_data_dir', 'user_data'))
        hist_path = user_data_dir / 'data/external/market_regime_history.json'

        if hist_path.exists():
            try:
                hist_stat = hist_path.stat()
                age_hours = (datetime.now(timezone.utc).timestamp() - hist_stat.st_mtime) / 3600
                if age_hours > 48:
                    logger.warning(
                        f"market_regime_history.json is {age_hours:.0f}h old — "
                        f"macro features will use stale/fill values. "
                        f"Ensure factor_collector.py is running or refresh the file."
                    )
                with open(hist_path, 'r') as f:
                    hist_data = json.load(f)
                hist_df = pd.DataFrame(hist_data)
                if not hist_df.empty:
                    hist_df['date_key'] = pd.to_datetime(hist_df['date']).dt.date
                    dataframe['date_key'] = dataframe['date'].dt.date
                    merged = pd.merge(dataframe, hist_df, on='date_key', how='left')

                    dataframe['%-fear_and_greed'] = merged['fear_and_greed'].fillna(50).values
                    dataframe['%-funding_rate'] = merged['funding_rate'].fillna(0.0001).values
                    dataframe['%-open_interest'] = merged['open_interest'].fillna(0).values
                    dataframe['%-long_short_ratio'] = merged['long_short_ratio'].fillna(1.0).values
                    dataframe['%-stablecoin_supply'] = merged['stablecoin_supply'].fillna(150000000000).values
                    dataframe['%-dxy'] = merged['dxy'].fillna(100.0).values
                    dataframe['%-spy'] = merged['spy'].fillna(500.0).values
                    dataframe.drop(columns=['date_key'], inplace=True, errors='ignore')
            except Exception as e:
                logger.warning(f"Failed to load external factors: {e}")

        return dataframe

    def feature_engineering_standardizes(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe['&s-up_or_down'] = dataframe['close'].shift(-3) / dataframe['close'] - 1
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FIX 3: structural regime filter — SMA200, independent of model features
        dataframe['sma200'] = dataframe['close'].rolling(200).mean()
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        enter_long = (
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] > 0.01) &
            (dataframe['close'] > dataframe['sma200'])          # FIX 3: bull filter
        )
        dataframe.loc[enter_long, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_long = (
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] < -0.01)
        )
        dataframe.loc[exit_long, 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time: datetime, current_rate: float,
                        current_profit: float, after_fill: bool = False, **kwargs) -> float:
        """
        FIX 1: ATR-based trailing stop.
        Trail 2x ATR below the highest price seen since entry (trade.max_rate).
        Never looser than the hard -5% stoploss.
        """
        dataframe, _ = self.dp.ohlcv(pair, self.timeframe)
        if dataframe is None or dataframe.empty or len(dataframe) < 15:
            return -0.05

        df = dataframe.tail(15)
        prev_close = df['close'].shift(1)
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                (df['high'] - prev_close).abs(),
                (df['low'] - prev_close).abs()
            )
        )
        atr = float(tr.mean())
        if atr <= 0 or trade.max_rate <= 0:
            return -0.05

        stop_price = trade.max_rate - 2 * atr
        if stop_price <= 0:
            return -0.05
        return max((stop_price / current_rate) - 1, -0.05)

    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        """
        FIX 2: horizon-aligned time stop.
        Model predicts 3 candles ahead (3h). After 6h (2x horizon), if the
        predicted move hasn't materialized (profit < 1%), the signal is dead —
        exit instead of holding for days.
        """
        hours_held = (current_time - trade.open_date_utc).total_seconds() / 3600
        if hours_held >= 6 and current_profit < 0.01:
            return 'horizon_stop'
        return None
