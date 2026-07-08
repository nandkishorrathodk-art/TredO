# TREDO — System Architecture

TREDO is built on a strictly decoupled, event-driven architecture using an asynchronous Event Bus. Modules do not call each other directly; they communicate by publishing and subscribing to typed message objects.

## Core Principles
1. **Event-Driven**: All inter-module communication happens via `EventBus`.
2. **Deterministic Trading**: Strategy signals are derived from pure mathematical indicators (Feature Engine) and aggregated via a Consensus Engine. No non-deterministic (LLM) logic is allowed in the execution path.
3. **Risk First**: Every execution intent must be cleared by the Risk Engine.
4. **Time Agnostic**: The system processes data whether it's arriving live from an exchange or being streamed from a CSV by the Replay Engine.

## Modules

### 1. Market Scanner (`backend.market`)
Connects to multiple exchanges via WebSocket (Binance, Bybit) and normalizes live data into `CandleEvent` objects.

### 2. Feature Engine (`backend.intelligence`)
Subscribes to `CandleEvent` and computes pure math indicators (Trend, Momentum, Volatility, Volume). 
Updates the `FeatureStore` which acts as an O(1) in-memory snapshot of the entire market state.

### 3. Strategy Engine (`backend.strategy`)
- **Strategy Manager**: Listens to `FeaturesUpdated`, loads the latest snapshot from `FeatureStore`, and evaluates all active rule-based strategies in parallel.
- **Consensus Engine**: Aggregates signals from multiple strategies into a unified, weighted decision (the final `SignalGenerated`).

### 4. Risk Engine (`backend.risk`)
Subscribes to `SignalGenerated`. Evaluates available capital, position limits, leverage, and global safety killswitches. If approved, publishes `RiskApproved`.

### 5. Execution Engine (`backend.execution`)
Subscribes to `RiskApproved` and executes trades either on Paper or Live exchanges.

### 6. Replay Engine (`backend.replay`) *(In Progress)*
Replaces the Market Scanner during backtesting. Emits `CandleEvent` from historical data files (CSV/Parquet) governed by a controllable `ReplayClock`.
