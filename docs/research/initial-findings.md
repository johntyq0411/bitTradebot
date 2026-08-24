# Research Findings — ML for Crypto Trading & Strategy Validation

**Date:** 2026-08-24  
**Purpose:** Inform the Modest-Bohr strategy redesign.  
**Status:** Initial findings — more research needed on specific topics.

---

## 1. Academic Literature: ML for Cryptocurrency Price Prediction

### 1.1 What the literature says

Multiple peer-reviewed papers and arXiv preprints address ML-based crypto price prediction. Key findings:

#### Model architectures tested
- **LSTM / GRU** (recurrent neural networks) — the most commonly tested architecture. Can capture temporal dependencies but prone to overfitting on small datasets.
- **CNN-LSTM hybrids** — convolutional layers extract local patterns, LSTM captures temporal dynamics. One review found "convolutional LSTM with a multivariate approach provides the best prediction accuracy in two major experimental settings" (arXiv:2405.11431).
- **Transformer / Performer / Attention-based** — tested in several papers (arXiv:2403.03606, others). Can capture long-range dependencies but require more data.
- **Ensemble / hybrid models** (Autoencoder-LSTM, CNN+LSTM+Transformer) — can improve prediction accuracy but "deeper hybrid models exhibit pronounced overfitting, despite their architectural sophistication" (DOI:10.1007/s00500-026-11296-w).
- **Temporal Fusion Transformer (TFT)** — proposed as a DL approach for crypto prediction (DOI:10.3390/forecast5010010).

#### Key findings
1. **Multivariate > univariate.** Models using multiple features (price + volume + technical indicators + macro) consistently outperform price-only models.

2. **Model complexity ≠ improved performance.** Deeper architectures (Transformer + Autoencoder + LSTM) can overfit heavily. "Model complexity does not necessarily translate into improved performance in highly volatile cryptocurrency markets."

3. **Prediction accuracy is measured, not trading profitability.** Papers report RMSE, MAPE, R², or directional accuracy (% correct predictions). None report net trading P&L after costs. A model with 70% directional accuracy can still lose money if correct predictions are small and incorrect ones are large.

4. **Sentiment analysis helps.** CryptoBERT-based sentiment improved BTC prediction accuracy by ~19% (IEEE paper, 2025).

5. **Technical indicators as features** are widely used and contribute predictive signal — but papers don't isolate which indicators matter most.

6. **Overfitting is the dominant failure mode.** Multiple papers explicitly warn about it. The small sample size of crypto data (especially at high frequency) makes overfitting easy.

7. **Training/test split matters enormously.** Pre-COVID vs COVID-era data produce very different model performance. Regime shifts break models trained on different conditions.

### 1.2 What the literature does NOT say

- No paper reports net profitability after realistic trading costs (fees, slippage, spread).
- No paper addresses regime-conditional strategy design in a systematic way.
- No paper validates walk-forward across multiple market regimes with trade-level P&L.
- No paper addresses the specific challenges of high-frequency (1h) BTC trading with ML.

### 1.3 Relevant papers identified

| Paper | Key contribution | Caveat |
|---|---|---|
| "Review of deep learning models for crypto price prediction" (arXiv:2405.11431) | Systematic review + evaluation of LSTM/CNN/Transformer variants. ConvLSTM multivariate best. | Prediction accuracy only, no P&L |
| "On Forecasting Cryptocurrency Prices: ML vs DL vs Ensembles" (DOI:10.3390/forecast5010010) | Compares statistical, ML, DL, TFT, and ensembles across 5 cryptos. | Prediction accuracy only |
| "Enhancing Price Prediction with Transformer + Technical Indicators" (arXiv:2403.03606) | Performer + BiLSTM with technical indicators on BTC/ETH/LTC, hourly and daily. | Prediction accuracy only |
| "Cryptocurrency Price Prediction Using LSTM and FEDformer Enhanced by Sentiment" (IEEE, 2025) | Hybrid L-FED model, sentiment analysis (CryptoBERT) improves accuracy 19% for BTC. | Prediction accuracy only |
| "Forecasting bitcoin prices based on hybrid LSTM and DNN" (DOI:10.1007/s00500-026-11296-w) | Autoencoder-LSTM reduces RMSE 9-15% vs LSTM/GRU/RNN, >25% vs ARIMA. Deeper models overfit. | Prediction accuracy only |
| "Deep learning and technical analysis in cryptocurrency market" (Finance Research Letters, 2023) | Goutte et al. — technical analysis + DL. | Academic, but prediction-focused |

### 1.4 Implications for our strategy

- **LightGBM (our current model) is a reasonable choice.** It's not as fancy as Transformer/LSTM hybrids, but those deeper models overfit more easily. LightGBM is robust, fast, handles tabular data well, and gives feature importance.
- **We should not chase model complexity.** More layers ≠ more money. The literature consistently shows diminishing returns and increased overfitting risk with deeper architectures.
- **Multivariate features are essential.** Single-feature strategies don't work. Our 38-feature approach is on the right track, but we need to validate which features actually contribute.
- **Sentiment could be a valuable addition** — CryptoBERT-based sentiment improved predictions. But it adds complexity and data sourcing requirements.
- **We need to measure trading P&L, not just prediction accuracy.** The literature's focus on RMSE/MAPE is useful for model selection but insufficient for strategy validation.

---

## 2. FreqAI / Freqtrade Best Practices

### 2.1 Lookahead bias — the #1 killer

The Freqtrade documentation is explicit and detailed about lookahead bias:

**Why it matters:** Backtesting populates the full dataframe (all candles) at once. If any indicator or signal uses future data, backtests show fake profits. Live/dry runs don't have this data, so the strategy fails.

**Common lookahead mistakes to avoid:**

| Mistake | Why it's lookahead | Fix |
|---|---|---|
| `shift(-1)` or negative shift | Uses future candle data | Use `shift(1)` or positive shifts only |
| `df.iloc[-1]` in populate functions | References last row (future in backtest) | Use rolling calculations or avoid absolute indexing |
| `dataframe['mean_volume'] = dataframe['volume'].mean()` | Mean includes ALL data including future | Use `dataframe['volume'].rolling(window).mean()` |
| `resample('1h')` without `label='right'` | Shifts data to left border of period | Use `resample('1h', label='right')` |
| Plain `merge()` for informative pairs | Can implicitly leak future data via date alignment | Use `merge_informative_pair()` helper |
| Using `df.mean()`, `df.min()`, `df.max()` on full column | Aggregation sees all data including future | Use rolling equivalents |

**Detection tool:** Freqtrade has `lookahead-analysis` command that:
- Runs baseline backtest
- Separately tests each entry/exit signal by masking other signals
- Compares indicator values between baseline and sliced backtests
- Reports which signals/indicators show bias

**Critical note:** FreqAI target indicators (from `set_freqai_targets()`) are flagged as biased by lookahead-analysis but are NOT actually biased — they use `shift(-3)` which is the intended target definition. These can be safely ignored.

### 2.2 FreqAI-specific concerns

1. **Feature engineering is done once on the ENTIRE training timerange.** This means features must not look ahead into the future. If you compute a feature that uses data from later in the timerange, it leaks into earlier predictions.

2. **Backtesting calls `set_freqai_targets()` once per backtest window** (timerange / backtest_period_days). This simulates dry/live behavior without lookahead bias for targets.

3. **FreqAI stores predictions for reuse** across backtests and live runs (using the same `identifier`). This speeds up subsequent backtests but means predictions from a previous run are reused — be aware of this when interpreting results.

4. **Continual learning is experimental and dangerous.** Freqtrade explicitly warns: "high probability of overfitting/getting stuck in local minima while the market moves away from your model." Recommended: keep it disabled for production.

5. **Hyperopt with FreqAI:** Only hyperopt entry/exit thresholds/criteria — NOT feature parameters or FreqAI config. Changing features changes predictions, which breaks the hyperopt's prediction reuse.

6. **Noise injection (`noise_standard_deviation`)** can help prevent overfitting by adding Gaussian noise to training features.

7. **`reverse_train_test_order`** trains on latest data, tests on historical — can reduce overfitting but is "unorthodox" and requires careful understanding.

8. **`early_stopping_patience`** helps prevent overfitting by stopping training when validation loss plateaus.

### 2.3 Validation methodology

From Freqtrade docs + community best practices:

1. **Use `lookahead-analysis` before trusting any backtest.** Non-negotiable. Catches the most common bias.

2. **Use `recursive-analysis`** to determine correct `startup_candle_count`. Ensures indicators are stable from the start.

3. **Walk-forward analysis** (not built-in, must be done manually):
   - Split time into in-sample (IS) and out-of-sample (OOS) windows
   - Train/optimize on IS, test on OOS
   - Roll forward: next IS includes previous OOS, next OOS is further forward
   - Multiple folds required — one lucky window proves nothing
   - OOS retention (OOS performance similar to IS) is a key metric

4. **How many trades needed:**
   - Minimum ~30 trades for statistical sense
   - ~100+ for reasonable confidence
   - Fewer than 10: essentially inconclusive

5. **Cost realism:**
   - Use realistic fees (0.1% per Freqtrade default, or actual exchange fees)
   - Add slippage estimate (0.05-0.1% for BTC on Binance)
   - If edge disappears with realistic costs, it's not real

6. **Parameter stability test:**
   - Perturb optimal parameters slightly (±10-20%)
   - If performance collapses, the "optimum" is a noise fit
   - Real edges have smooth performance landscapes

### 2.4 Implications for our strategy

- Any new strategy MUST pass `lookahead-analysis` before being trusted.
- Our previous backtests did not run lookahead-analysis — we should run it on any candidate strategy.
- FreqAI feature engineering must be carefully designed to avoid lookahead.
- Walk-forward with multiple folds is required, not single backtests.
- Hyperopt (if used) should only tune entry/exit thresholds, not features.

---

## 3. Feature Evidence for BTC

### 3.1 Technical indicators — what works?

From web research (Gate.io analysis, FMZ backtests, trading literature):

| Indicator / Signal | Standalone Win Rate | Notes |
|---|---|---|
| MACD crossover (golden/death cross) | ~40% | Worse than coin flip alone |
| RSI oversold (<30) / overbought (>70) | ~50-55% | Better in range-bound markets |
| RSI + MACD combined | ~77% | Multi-confirmation significantly improves accuracy |
| RSI + MACD + Bollinger Bands | 73-77% | Third confirmation reduces false signals |
| Candlestick patterns | 54-60% | Valid for short-term (≤10 days) only |
| Bollinger Band squeeze | N/A (no direction) | Must confirm direction with other indicators |
| ML + technical indicators | Claims 92%+ | Prediction accuracy, not P&L; requires ML infrastructure |

**Key insight:** No single indicator works well alone. Combination (multi-confirmation) is essential. Even the best combinations (77% win rate) need to be evaluated for expectancy after costs — a 77% win rate with 1:1 risk-reward and 0.1% fees is profitable, but a 77% win rate with poor risk-reward can lose money.

### 3.2 Macro features — what's available and potentially useful?

Our current implementation collects:

| Feature | Source | Frequency | Potential signal |
|---|---|---|---|
| Fear & Greed Index | alternative.me API | Daily | Sentiment extremes may predict reversals |
| Funding Rate | Binance Futures API | 8h | Positive funding = longs pay shorts (crowded longs) |
| Open Interest | Binance Futures API | Daily | Rising OI + price up = trend confirmation |
| Long/Short Ratio | Binance Futures API | Daily | Extreme ratio may signal reversal |
| Stablecoin Supply | DefiLlama API | Daily | Rising supply = buying power entering market |
| DXY (US Dollar Index) | Yahoo Finance | Daily | Inverse correlation with BTC often observed |
| SPY (S&P 500) | Yahoo Finance | Daily | Risk-on/risk-off correlation with BTC |

**Evidence quality:** These features are widely discussed in trading communities but academic evidence for their predictive power at 1h/4h horizon is limited. They're more commonly used for longer-term (daily/weekly) predictions.

**Key concern:** Most macro features are daily or slower. Their predictive value for 1h BTC moves is questionable. They may be more useful as regime filters (e.g., "only trade when Fear & Greed is below 20") than as direct predictors.

### 3.3 What's potentially missing

Features we don't currently use that could be valuable:

| Feature | Source | Potential signal |
|---|---|---|
| Volatility (ATR, realized vol, Bollinger width) | Computed from price | Regime detection, position sizing, stop placement |
| Volume profile / VWAP | Computed from price | Institutional levels, support/resistance |
| Order book imbalance | Binance API (depth) | Short-term price pressure |
| Liquidation data | Binance API / coinglass | Cascading liquidations can drive short-term moves |
| On-chain metrics (exchange flows, whale alerts) | Glassnode, CryptoQuant | Large inflows to exchanges = selling pressure |
| Correlation with other assets (ETH/BTC, equities) | Computed | Diversification signals, regime detection |
| Time features (hour of day, day of week) | Computed | Intraday patterns in crypto |
| Lagged returns (autocorrelation) | Computed | Mean reversion / momentum at different horizons |

### 3.4 Implications for our strategy

- Technical indicators work best in combination, not isolation. Our strategy should use multi-factor confirmation.
- Macro features may be more useful as regime filters than as direct predictors for 1h trading.
- Volatility features are essential and currently underrepresented — critical for regime detection and risk management.
- Adding 4h data (which we have for the recent period) provides higher-timeframe context that can improve signals.
- Feature importance analysis (permutation importance, SHAP) is essential before trusting any feature set.

---

## 4. Open Questions for Further Research

1. **Walk-forward methodology for FreqAI specifically** — how exactly should folds be structured given FreqAI's periodic retraining? How many folds? What IS/OOS ratio?

2. **Regime detection methods** — what indicators robustly classify bull/bear/sideways? How to avoid whipsaw (rapid regime flipping)?

3. **Feature importance methodology** — should we use permutation importance, SHAP, or both? How to assess feature stability across regimes?

4. **Optimal prediction horizon** — is 3-candle (3h) ahead the right target? Would 1h, 6h, or 12h work better? Would multi-horizon prediction help?

5. **Position sizing and risk management** — what's the optimal approach for a single-pair BTC strategy? Volatility-adjusted sizing? Kelly criterion? Fixed fractional?

6. **How to handle the bull market** — our ML strategy didn't trade during the bull run. Is that correct behavior (model correctly identified no edge) or a failure (model should have captured the trend)?

---

## 5. Summary: What We Know and What We Need to Do

### What we know
- ML can predict crypto prices with reasonable accuracy (RMSE/MAPE improvements of 9-19% over baselines), but prediction accuracy ≠ trading profitability.
- Model complexity increases overfitting risk. LightGBM is a reasonable, robust choice.
- Multivariate features (technical + macro) outperform single-feature approaches.
- No single technical indicator works well alone; multi-confirmation is essential.
- Lookahead bias is the most common and most damaging backtesting error.
- Walk-forward validation with multiple folds is required for credible results.
- Minimum ~30 trades for statistical sense; ~100+ for confidence.
- Our current ML strategy (14 trades, +14.94%, 92.9% win rate) is promising but statistically inconclusive.
- Our EMA crossover baseline has no edge — it lost money in all three regimes.

### What we need to do
1. Design the strategy framework (regime → signals → combination → execution → validation).
2. Implement regime detection and validate it.
3. Build 2-3 simple rule-based signal candidates and test them per regime.
4. Build ML strategy with careful feature engineering (no lookahead).
5. Run walk-forward validation across 5+ folds, multiple regimes.
6. Run lookahead-analysis on any candidate strategy.
7. Compare ML vs rule-based baseline.
8. Paper trade the best validated strategy for 30-50+ live trades.
9. Decide: deploy live or iterate.

---

*End of initial research findings. More research needed on specific methodology questions (walk-forward design for FreqAI, regime detection robustness, feature selection protocol).*
