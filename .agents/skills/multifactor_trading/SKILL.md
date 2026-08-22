---
name: multifactor_trading
description: Guidelines for implementing Multi-Factor Trading (Macro, Micro, and Technical Analysis) in Freqtrade bots.
---

# Multi-Factor Trading Architecture

This skill defines the professional standard for building algorithmic trading strategies. Relying solely on Technical Analysis (TA) often leads to high win rates in bull markets but catastrophic drawdowns in bear markets. 

To build institutional-grade strategies, agents must implement a **Multi-Factor Architecture**.

## 1. The Three Pillars

Every strategy should incorporate conditions from three distinct domains before generating an entry signal:

### A. Macro Analysis (The Environment)
* **Goal**: Establish the broader trend and regime. We do not buy against the Macro trend.
* **Implementation in Freqtrade**: 
  * Use **Informative Pairs** to fetch Higher Timeframe (HTF) data (e.g., 1-day or 1-week candles while the main strategy runs on 1-hour).
  * Check if HTF EMA is trending up (EMA20 > EMA50 on the 1d chart).
  * Alternatively, fetch external macro indicators (SPY, DXY) if the environment supports real-time API calls. For strict backtesting environments, HTF crypto trends are the safest proxy.

### B. Technical Analysis (The Setup)
* **Goal**: Identify the specific setup or momentum shift.
* **Implementation**:
  * Moving Average crossovers (EMA20 crossing EMA50).
  * Momentum oscillators (RSI, MACD) on the base timeframe (e.g., 1h).

### C. Micro Analysis (The Trigger / Confirmation)
* **Goal**: Confirm that local market structure supports the setup. Look for anomalous volume or volatility contraction.
* **Implementation**:
  * **Volume Spikes**: `volume > volume.rolling(24).mean() * 1.5`
  * **Volatility**: ATR (Average True Range) checking for volatility expansion or contraction before entry.
  * **VWAP**: Ensure price is anchored favorably relative to intraday/intrawork VWAP.

## 2. Risk Management (The Foundation)

Even with multi-factor entries, the "Win Rate Fallacy" applies: trying to achieve a 100% win rate by removing stop-losses guarantees a total portfolio wipeout.

* **Stop-Loss**: Always use a hard stop-loss (e.g., -5%).
* **Trailing Stop**: Strongly recommended to lock in gains if a trade fails to reach the ROI target.
* **ROI Table**: Take partial profits aggressively.

## 3. Professional Review Process

Before deploying a multi-factor strategy, the AI should invoke a **Quantitative Reviewer Subagent** to audit the logic.
* **Criteria**: The reviewer must check for lookahead bias (e.g., using `df['close'].shift(-1)`), overfitting (hyper-specific parameters), and catastrophic downside risk in the backtest results.
