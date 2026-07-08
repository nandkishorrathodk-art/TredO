# TREDO Event Catalog

This document defines the complete event catalog for the TREDO Event Bus. The entire architecture is event-driven. Modules communicate exclusively by publishing and subscribing to these events.

## System Events (`SystemEvent`)
Used for infrastructure lifecycle and system-level notifications.

| Event Type | Source | Description |
|------------|--------|-------------|
| `system` | `lifespan` | Application startup and shutdown events. |
| `system` | `api` | API-triggered shutdown request. |

## Execution Events
Represent the full lifecycle of a trade order and position.

| Event Class | Source | Description |
|-------------|--------|-------------|
| `OrderSubmitted` | `order_service` | A new order has been requested by the user/agent. |
| `OrderValidated` | `order_service` | The risk engine approved the order and calculated safe position size. |
| `OrderRejected` | `order_service` | The risk engine or exchange rejected the order. Contains reasons. |
| `OrderFilled` | `order_service` | The order was successfully executed on the exchange. |
| `OrderCancelled` | `order_service` | An open order was cancelled. |
| `PositionOpened` | `order_service` | A filled order resulted in a new open position. |
| `PositionClosed` | `order_service` | An open position was closed, realizing PnL. |
| `PnLUpdated` | `order_service` | Portfolio balance and PnL updated. |

## Risk Events
Triggered by the `RiskEngine` when hard limits are hit.

| Event Class | Source | Description |
|-------------|--------|-------------|
| `RiskApproved` | `risk` | Emitted during trade validation if approved. |
| `RiskRejected` | `risk` | Emitted during trade validation if rejected. |
| `KillSwitchActivated` | `risk` | The global kill switch was activated, preventing all new orders. |

## Memory Events (`MemoryEvent`)
Published when journal entries are stored.

| Event Type | Source | Description |
|------------|--------|-------------|
| `memory` | `journal` | A new memory/journal entry was saved. |

## Agent Events
Events related to the lifecycle and actions of autonomous agents.

| Event Class | Source | Description |
|-------------|--------|-------------|
| `AgentStarted` | `agent_manager` | An agent process has started. |
| `AgentStopped` | `agent_manager` | An agent process has cleanly stopped. |
| `AgentFailed` | `agent_manager` | An agent process crashed with an exception. |
| `AgentMessage` | `agent` | Output or thought process from a running agent. |

## Market Events
Future-proofing for when live data streams are implemented.

| Event Class | Source | Description |
|-------------|--------|-------------|
| `SignalGenerated` | `strategy` | A new trading signal was generated (pre-order). |
| `TradeExecuted` | `connector` | A live trade occurred on the exchange. |

---

*Note: All events must subclass `BaseMessage` and define their schema precisely using dataclasses.*
