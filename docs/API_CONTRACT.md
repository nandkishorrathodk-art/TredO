# TREDO — API Contract

This document lists the WebSocket and REST API endpoints used to control the Python Backend from the Electron Frontend.

## Replay Controller API (V2.4+)

**Prefix**: `/api/v1/replay`

| Endpoint | Method | Description | Payload Example |
|---|---|---|---|
| `/play` | POST | Starts or resumes the replay clock. | `{}` |
| `/pause` | POST | Halts the replay clock immediately. | `{}` |
| `/stop` | POST | Halts and resets the clock to the beginning. | `{}` |
| `/step` | POST | Emits exactly one candle then pauses. | `{}` |
| `/speed` | POST | Sets the replay multiplier. | `{"speed_multiplier": 10.0}` |
| `/seek` | POST | Jumps to a specific timestamp in the source. | `{"timestamp": 1718000000}` |

## Strategy Engine API

**Prefix**: `/api/v1/strategy`

| Endpoint | Method | Description | Payload Example |
|---|---|---|---|
| `/enable` | POST | Enables a strategy. | `{"symbol": "BTC/USDT", "strategy": "EMA_CROSS", "weight": 1.0}` |
| `/disable` | POST | Disables a strategy. | `{"symbol": "BTC/USDT", "strategy": "EMA_CROSS"}` |
| `/metrics` | GET | Retrieves memory metrics for strategies. | None |
