# TREDO — V2 Architecture Roadmap

This document tracks the execution of the **V2 Quantitative Engine** leading up to the **V3 AI Layer**.

## Current Status: Building V2.4

```
✅ = Built & Tested
🔄 = In Progress
🔲 = Not Started
```

### V2 Foundation (Quantitative Engine)
* ✅ **V2.1 Market Scanner**: Multi-market WebSocket listener (Binance, Bybit) pushing `CandleEvent`.
* ✅ **V2.2 Market Intelligence (Feature Engine)**: Mathematical pipeline (Trend, Momentum, Volatility, Volume) feeding the O(1) `FeatureStore`.
* ✅ **V2.3 Strategy Engine**:
  * ✅ V2.3.1 Interface & Registry
  * ✅ V2.3.2 Rule-Based Strategies (EMA, RSI, Bollinger)
  * ✅ V2.3.3 Strategy Manager & Consensus Engine
* 🔄 **V2.4 Replay Engine (Time Machine)**: Historical data streaming with strict timing and clock control.
* 🔲 **V2.5 Universal Backtester**: Reporting and evaluation over replay data.
* 🔲 **V2.6 Analytics & Metrics**: Strategy performance tracking.
* 🔲 **V2.7 Optimization**: Parameter tuning.
* 🔲 **V2.8 Walk-forward Validation**: Out-of-sample testing.
* 🔲 **V2.9 Long Paper Trading**: Multi-exchange forward testing.

### V3 Expansion (AI Research Layer)
* 🔲 **V3.1 AI Agents Base**: Integration of LLM for reasoning.
* 🔲 **V3.2 Multi-Agent Organization**: Debate, CEO, Risk AI.
* 🔲 **V3.3 World Model**: Market physics and state predictions.
* 🔲 **V3.x ...**: Autonomous self-improvement and evolution.

## Component Flow

```
Market Scanner (or Replay Engine)
      │
      ▼
Feature Engine
      │
      ▼
Feature Store
      │
      ▼
Strategy Manager
      │
      ▼
Consensus Engine
      │
      ▼
Risk Engine
      │
      ▼
Execution
      │
      ▼
Memory
```
