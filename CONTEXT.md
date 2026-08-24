# Strategy Design Context — Modest-Bohr Redesign

**Last updated:** 2026-08-24  
**Status:** Active redesign after Phase 0+1 backtests showed no edge in existing EMA crossover strategy.

---

## Glossary

### Strategy
A callable that takes a DataFrame of OHLCV + indicator columns and produces `enter_long` / `exit_long` signal columns. In Freqtrade, this is a Python class implementing `IStrategy`.

### Regime
A market condition characterized by trend direction (bull/bear/sideways) and volatility level. Classified per-candle using: 200-day SMA slope, price distance from SMA, and realized volatility.

### Edge / Expectancy
Positive statistical expectancy: average trade P&L > 0 over many trades, after costs. Must be demonstrated across multiple regimes and time windows, not a single short backtest.

### Feature
An input column fed to the ML model. Can be technical (RSI, EMA, volatility), macro (Fear & Greed, funding rate, DXY), or microstructure (order book imbalance, volume profile).

### Label / Target
The value the ML model predicts. In current setup: 3-candle-ahead return (`close.shift(-3) / close - 1`). Binary variant: up/down classification.

### Walk-Forward Validation
Training on window N, testing on N+1, then sliding forward. Multiple folds across different market conditions. The gold standard for ML strategy validation — prevents overfitting to a single backtest window.

### Signal
A condition that triggers an action: entry signal (buy), exit signal (sell), or filter (skip trade). Can be rule-based or model-based.

### Cost
Transaction costs: trading fees (0.1% per Freqtrade default), slippage, and opportunity cost of capital locked in trades.

### Sample Size
Number of trades in a backtest or live run. Below ~30 trades, results are statistically inconclusive. Below ~100, confidence is low. The ML strategy has 14 trades — insufficient.

### Overfitting
When a model performs well on training/historical data but poorly on unseen data. Caused by: too many features relative to data points, training on a non-representative window, or tuning parameters to fit noise.

### Underfitting
When a model is too simple to capture the signal. Performs poorly even on training data.

### Regime Filter
A rule that gates strategy activity based on market regime. E.g., "only trade when price is below 200-day SMA and volatility is elevated."

### Baseline Strategy
A simple, non-ML strategy used as a benchmark. If ML can't beat the baseline, the ML is not adding value.

### FreqAI
Freqtrade's ML module. Wraps LightGBM (and other models) with automatic feature engineering, periodic retraining, and backtesting integration.

### LightGBM
Gradient boosting decision tree model. Fast, handles tabular data well, supports categorical features. Current model: 300 trees, learning rate 0.05, min_child_samples=20, trained on 30-day windows.

---

## Redesign Principles

1. **Regime-aware by default.** No single strategy should be expected to work across all regimes. The strategy must either adapt to regime or filter to trade only in favorable regimes.

2. **Signal quality over quantity.** 14 trades with 92.9% win rate is better than 100 trades with 51% win rate — but only if the 14 trades are representative. We need enough trades for statistical confidence, but not at the cost of diluting signal quality.

3. **Simple baseline first.** Before building complex ML, establish what simple rules can achieve. The EMA crossover failed, but that doesn't mean all simple strategies fail — it means *that specific one* fails.

4. **Features must be predictive, not just correlated.** A feature that correlates with past price but doesn't predict future returns is useless. Feature validation (IC, permutation importance, SHAP) is mandatory before including features in the model.

5. **Walk-forward validation is non-negotiable.** Single backtests are insufficient. Every candidate strategy must pass walk-forward validation across multiple folds and regimes before being considered viable.

6. **Costs matter.** A 0.1% fee per trade on a strategy with 1% avg profit means 10% of profits go to fees. Slippage, spread, and opportunity cost add more. Net expectancy must be positive after all costs.

7. **Risk management is part of strategy, not an add-on.** Position sizing, stop placement, and max exposure must be integrated into the strategy design from the start, not bolted on later.

---

## Decisions Needed

These are open questions that the redesign must address. Each requires research and/or testing.

### D1: What is the right prediction target?
Current: 3-candle-ahead return (binary up/down at >1% threshold).  
Alternatives: shorter horizon (1-2 candles for more signals), longer horizon (6-12 candles for trend following), multi-horizon (predict multiple horizons simultaneously), volatility-adjusted target (predict return relative to current volatility).

### D2: What features should the model use?
Current: 38 features across 1h + 4h (RSI, ROC, volume MA, macro).  
Question: which features are actually predictive? Which add noise? What's missing?  
Needed: feature importance analysis, IC study, stability check across regimes.

### D3: What is the right entry threshold?
Current: `do_predict == 1` AND `target > 0.01` (1% expected return).  
Question: is 1% threshold too high (few trades) or too low (noise trades)? Should threshold be adaptive (volatility-adjusted)?

### D4: Should the strategy have a regime filter?
Current: no explicit regime filter — model is expected to learn regime implicitly.  
Question: would an explicit regime filter (only trade in bear/sideways) improve performance? Would it reduce sample size too much?

### D5: What timeframe(s) should be used?
Current: 1h primary, 4h informative.  
Question: is 1h the right timeframe for BTC? Would 15m or 4h or 1d work better? Should multiple timeframes be used simultaneously?

### D6: What pairs should be traded?
Current: BTC/USDT only.  
Question: would adding ETH/USDT or other high-cap coins improve diversification and trade count? Would cross-pair features help?

### D7: What is the right risk framework?
Current: fixed -5% stoploss, fixed ROI table, max 1 open trade, unlimited stake.  
Question: should stops be volatility-adjusted (ATR-based)? Should position size scale with conviction? Should max trades be higher?

### D8: How do we validate that the strategy has a real edge?
Current: single backtest windows.  
Question: what is the minimum validation protocol? Walk-forward across N folds, with minimum trade count per fold, tested across multiple regimes, with bootstrap confidence intervals on P&L?

---

## Design Space

### Strategy Archetypes to Explore

1. **Trend-following** — enter in direction of trend, exit on reversal or target. EMA crossover is a simple version. Better versions: ADX-filtered trend, moving average slope, higher-high/lower-low structure.

2. **Mean reversion** — enter against extreme moves, exit on mean return. RSI extremes, Bollinger Bands, volatility contraction/expansion. Failed in our tests, but may work in specific regimes (range-bound).

3. **Momentum** — enter on strong recent moves, exit on momentum decay. Rate of change, volume breakout, relative strength vs benchmark.

4. **Market microstructure** — enter based on order flow, volume profile, bid-ask dynamics. Funding rate, open interest, long/short ratio as proxies.

5. **Macro-informed** — enter based on macro conditions (Fear & Greed, DXY, SPY, stablecoin flow). Our ML strategy already does this.

6. **Hybrid ML** — model combines multiple signal types, learns regime-dependent weights. Our current approach, but needs proper validation.

### Time Horizon Options

| Horizon | Candlestick equivalent | Strategy style | Signal frequency |
|---|---|---|---|
| Intraday (15m) | 15 min | Scalping, microstructure | High (many trades) |
| Short-term (1h) | 1 hour | Swing trading, momentum + reversion | Medium (~100-200 trades/yr) |
| Medium-term (4h) | 4 hours | Swing + trend | Low (~50-100 trades/yr) |
| Daily (1d) | 1 day | Position trading, macro-driven | Very low (~10-30 trades/yr) |

### ML Model Options

| Model | Strengths | Weaknesses |
|---|---|---|
| LightGBM (current) | Fast, handles tabular data, feature importance | Can overfit on small data, needs careful tuning |
| Logistic Regression | Simple, interpretable, calibrates well | Limited expressiveness, needs good features |
| Random Forest | Robust, less overfitting than GBM | Slower, less precise |
| Neural Network | Can capture complex interactions | Requires more data, harder to tune, less interpretable |
| Ensemble (multiple models) | Reduces variance, can combine different signal types | More complex, slower |

---

## Validation Protocol (Proposed)

Minimum bar for a strategy to be considered "has potential":

1. **Walk-forward across 5+ folds** spanning different market regimes
2. **Minimum 30 trades per fold** (or document why fewer)
3. **Positive expectancy after costs** (fees + estimated slippage) in at least 4 of 5 folds
4. **No single fold dominates** the overall result (no lucky window)
5. **Sharpe > 0.5** on walk-forward aggregate
6. **Max drawdown < 20%** (reasonable for a single-pair strategy)
7. **Feature stability check** — feature importance doesn't swing wildly across folds

If a strategy passes this bar, it moves to extended paper trading (Phase 5). If it fails, it goes back to redesign.

---

## Known Unknowns

These are things we need to discover through research/testing:

1. What is the actual predictive power of the macro features (Fear & Greed, funding rate, OI, etc.) on BTC 1h returns?
2. Does the 4h timeframe add signal or noise relative to 1h-only?
3. What is the optimal prediction horizon for this setup?
4. How many trades per year is realistic for a BTC-only 1h strategy with reasonable thresholds?
5. Does the ML model's 92.9% win rate on 14 trades reflect skill or luck?
6. What is the regime-conditional performance of different strategy archetypes?
7. What is the right balance between signal quality and trade frequency?

---

## Implementation Constraints

- **Data:** 2 years of 1h data available, 4h data only for recent ~1 year. Macro data for ~1 year.
- **Platform:** Freqtrade 2026.7 with FreqAI, Docker-based, paper trading only.
- **Compute:** Docker container with ~4GB RAM limit. LightGBM training is fast but walk-forward with many folds takes time.
- **Time:** Backtests take minutes each. Full walk-forward with 5+ folds per strategy candidate could take an hour+.
- **API:** Binance public API for data, no rate limit issues for backtesting.

---

## References

- Phase 0 results: `~/Documents/antigravity/modest-bohr/README.md` + backtest runs
- Phase 1 regime decomposition: `user_data/scripts/regime_decompose.py`
- Freqtrade docs: https://www.freqtrade.io/en/stable/
- FreqAI docs: https://www.freqtrade.io/en/stable/freqai/
- Current strategy files: `user_data/strategies/`
- User profile: John Tan, Malaysian, WhatsApp +60 17-825 7407
