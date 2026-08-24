import logging
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from datetime import datetime, timezone
import json
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

class FreqaiMultiFactorBtcStrategy(IStrategy):
    """
    Predictive Multi-Factor Strategy using FreqAI LightGBM.
    Instead of hard-coded rules, the model learns the relationship between
    technicals (EMA/RSI), macro (Fear/Greed), and microstructure (Funding/OI)
    to predict future price movements.
    """
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count = 200

    stoploss = -0.05
    minimal_roi = {
        "0": 0.05,
        "120": 0.03,
        "240": 0.015
    }

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        """
        Create the features the AI will use to predict the future.
        Called once per period in indicator_periods_candles — include the
        period value in each feature name so multi-period features stack.
        """
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
        Warns if the file is older than 48h — stale macro data silently
        degrades the model's signal and is worse than no macro data.
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
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        enter_long = (
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] > 0.01)
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
