# TREDO — API Contract (V1)

> **FROZEN.** Do not change these contracts without updating this document first.
> Frontend (Electron) depends on these exact shapes.

---

## REST Endpoints

### `GET /health`

**Response:**
```json
{
  "status": "ok",
  "uptime_s": 123.45,
  "services": 7,
  "agents": 0
}
```

### `GET /status`

**Response:**
```json
{
  "status": "running",
  "services": [
    {"name": "event_bus", "type": "EventBus", "status": "registered"},
    {"name": "memory", "type": "Journal", "status": "registered"},
    {"name": "risk", "type": "RiskEngine", "status": "registered"},
    {"name": "ai_gateway", "type": "AIGateway", "status": "registered"}
  ],
  "event_bus": {
    "total_subscriptions": 11,
    "message_types": 11,
    "history_size": 1
  },
  "scheduler": {}
}
```

### `GET /services`

**Response:**
```json
{
  "count": 7,
  "services": [
    {"name": "event_bus", "type": "EventBus", "status": "registered"},
    {"name": "memory", "type": "Journal", "status": "registered"}
  ]
}
```

### `POST /event`

**Request:**
```json
{
  "event_type": "system",
  "message": "User action description",
  "severity": "info",
  "details": {}
}
```

**Response:**
```json
{
  "published": true,
  "event_type": "system",
  "handlers_notified": 3
}
```

### `POST /shutdown`

**Request:**
```json
{
  "reason": "user_request"
}
```

**Response:**
```json
{
  "status": "shutting_down",
  "reason": "user_request"
}
```

---

## WebSocket

### `WS /ws`

**Connect:** `ws://localhost:8000/ws`

**Client → Server:**
```json
"ping"
```

**Server → Client (pong):**
```json
{"type": "pong"}
```

**Server → Client (events):**
```json
{
  "type": "SystemEvent",
  "source": "lifespan",
  "timestamp": "2026-07-08T12:00:00+00:00",
  "event_type": "system",
  "message": "TREDO started",
  "severity": "info",
  "details": {}
}
```

### Event Types Streamed via WebSocket

| Type | Description |
|---|---|
| `SystemEvent` | System lifecycle events |
| `SignalGenerated` | Trading signal created |
| `RiskApproved` | Risk engine approved trade |
| `RiskRejected` | Risk engine rejected trade |
| `TradeExecuted` | Trade executed on exchange |
| `MemoryEvent` | Something logged to memory |
| `KillSwitchActivated` | Emergency stop |
| `AgentStarted` | Agent started |
| `AgentStopped` | Agent stopped |
| `AgentFailed` | Agent error |
| `AgentMessage` | Inter-agent message |

---

## Rules

1. Electron calls REST endpoints for actions.
2. Electron receives live updates via WebSocket.
3. Electron never imports Python logic.
4. All events flow: `Electron → REST → Event Bus → Handlers → WebSocket → Electron`
