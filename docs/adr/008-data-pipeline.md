# 008. Data Pipeline & Market Scanner

**Date:** 2026-07-08
**Status:** Accepted

## Context
TREDO V2 begins with the **Market Scanner**, responsible for ingesting live market data and normalizing it for downstream engines (Feature, Strategy, Risk). 

If every downstream module is tightly coupled to Binance or Bybit's specific JSON structure, replacing an exchange becomes a monumental task. Furthermore, mixing data collection with indicator calculation violates the single-responsibility principle and clutters the architecture.

## Decision
We will build a strictly isolated **Market Scanner** module. It acts solely as a translation layer: subscribing to raw exchange WebSockets, normalizing the payloads, and publishing canonical `MarketEvent` instances to the Event Bus.

### 1. Supported Exchanges (Initial)
- **Binance** (via raw WebSocket API `wss://stream.binance.com:9443`) will be the first implementation.

### 2. Mandatory Event Types
The system will recognize explicit event types rather than a generic JSON blob:
- `TickerEvent`: 24hr rolling window stats (Last Price, Best Bid/Ask, Volume).
- `CandleEvent`: OHLCV data for specific timeframes.
- `TradeEvent`: Individual public market trades.
- `OrderBookEvent`: L2 Order Book depth updates.
- `FundingEvent`: Perpetual futures funding rates.
- `OpenInterestEvent`: Perpetual futures open interest.
- `ConnectionEvent`: WebSocket connect, disconnect, and reconnect events.

### 3. Canonical Event Schema
Every event will subclass a base `MarketEvent` containing:
- `exchange` (str): e.g., "binance"
- `symbol` (str): Normalized format (e.g., "BTC/USDT")
- `timestamp` (int): Source exchange timestamp in milliseconds.
- `receive_time` (int): Local machine time in milliseconds when the packet arrived.

### 4. Timestamp Policy
- **Exchange Time is King:** Downstream metrics (like VWAP or OHLCV) must use the `timestamp` provided by the exchange, not the local `receive_time`.
- **Latency Tracking:** The delta between `receive_time` and `timestamp` will be monitored for network lag.
- **Out-of-Order Handling:** The scanner will drop messages if their exchange `timestamp` is older than the previously processed timestamp for that exact symbol and event type (Strictly Monotonically Increasing).

### 5. Reconnection & Dropped Messages
- **Auto-Reconnect:** On disconnect or missed ping/pong, the scanner will immediately attempt reconnection using exponential backoff (1s, 2s, 4s, up to 30s).
- **No Catch-up (No History):** The scanner deals exclusively with the *live edge* of the market. If messages are dropped during a disconnect, they are gone. Downstream feature engines must handle missing data gracefully (e.g., by falling back to REST to fetch missing candles, which is outside the Scanner's scope).

## Consequences
- **Positive:** Downstream engines (Feature, Strategy) are 100% exchange-agnostic.
- **Positive:** Testing the strategy engine becomes trivially easy by mocking the Event Bus with fake `MarketEvent` objects.
- **Negative:** Adding a new exchange requires writing a new normalizer class specifically for that exchange's WS format.
