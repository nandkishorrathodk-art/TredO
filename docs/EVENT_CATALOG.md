# TREDO — Event Catalog

This document defines the schema of all events flowing through the `EventBus`.
Refer to `backend/core/messages.py` for Python dataclass implementations.

## Market Events
* `CandleEvent`: A closed OHLCV candle. Emitted by `MarketScanner` or `ReplayEngine`.
* `OrderBookEvent`: L2 orderbook snapshot.
* `TradeEvent`: Public market trade tick.

## Intelligence Events
* `FeaturesUpdated`: Emitted by `FeatureEngine` after math indicators are calculated and updated in the `FeatureStore`. Contains `symbol` and a dictionary of updated feature IDs.

## Strategy Events
* `SignalGenerated`: Emitted by the `StrategyManager`'s Consensus Engine.
  * Fields: `strategy`, `symbol`, `exchange`, `market_type`, `timeframe`, `direction` (BUY/SELL/NONE), `confidence` (0.0 to 1.0), `reason` (list of strings).

## Risk Events
* `RiskCheckRequest`: Explicit request for risk validation.
* `RiskApproved`: Emitted when the Risk Engine allows a trade.
* `RiskRejected`: Emitted when limits or safety rules block a trade.

## Execution Events
* `TradeRequested`: Emitted to signal execution intent.
* `TradeExecuted`: Emitted after successful order fill.
* `TradeClosed`: Emitted when a position is exited.

## System Events
* `SystemEvent`: Generic system notifications.
* `KillSwitchActivated`: Emergency global halt.
* `HealthCheckRequest` & `HealthCheckResponse`: Node health monitoring.
* `MemoryEvent`: Log sent to the Memory engine.
