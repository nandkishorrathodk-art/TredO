# 009. Market Intelligence Pipeline & Feature Engine

**Date:** 2026-07-08
**Status:** Accepted

## Context
Following the completion of the Market Scanner (V2.1), we need to compute technical indicators and market features for downstream consumption. 
If strategies compute their own indicators, we violate the single-responsibility principle and create redundant computations across different strategies.

Furthermore, placing all indicators in flat files (`rsi.py`, `ema.py`) becomes unmanageable as the number of features scales to 100+.

## Decision
We will build the **Market Intelligence Pipeline** (V2.2). The first component is the **Feature Engine**, which sits between the Market Scanner and the Strategy Engine.

### 1. Categorization
Features will be strictly grouped by their mathematical domain, not just loosely dumped:
- `trend.py`: SMA, EMA, VWAP, MACD.
- `momentum.py`: RSI, Stochastic, ROC.
- `volatility.py`: ATR, Bollinger Bands, Standard Deviation.
- `volume.py`: OBV, Volume Profile, Volume Delta.
- `market_structure.py`: Swing High/Low, Break of Structure (BOS), Change of Character (CHOCH).

### 2. Feature Store (Separation of Concerns)
- The Strategy Engine is strictly forbidden from computing features.
- The Feature Engine will compute features and maintain a `FeatureStore`.
- Strategies will query the `FeatureStore` (e.g., `features = store.get("BTC/USDT")`).

### 3. Event Chain
The execution flow is strictly event-driven:
1. `Market Scanner` publishes `CandleClosed` (or `CandleEvent(is_closed=True)`).
2. `Feature Engine` consumes `CandleEvent` and updates internal rolling windows.
3. `Feature Engine` computes features and updates the `FeatureStore`.
4. `Feature Engine` publishes `FeaturesUpdated`.
5. `Strategy Engine` consumes `FeaturesUpdated` and queries the `FeatureStore`.
6. `Strategy Engine` publishes `SignalGenerated`.
7. `Risk Engine` intercepts the trade request.
8. `Execution` routes to the Exchange/Paper Exchange.

### 4. Feature Versioning
Every feature will have explicit metadata to allow for easy optimization and backward compatibility (e.g., `Name: RSI, Version: 1, Window: 14`).

## Consequences
- **Positive:** Strategies remain clean, purely focused on logic and rules.
- **Positive:** Computational efficiency. EMA14 is calculated exactly once per tick, even if 10 strategies use it.
- **Positive:** Easy to mock features for backtesting (just inject fake `FeaturesUpdated` events).
- **Negative:** Introduces slight latency overhead due to event bus serialization between Scanner -> Feature -> Strategy, but negligible for our scale.
