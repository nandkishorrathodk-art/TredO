"""
TREDO — API Routes
Minimal REST endpoints. Transport layer ONLY.
Never calls modules directly — always goes through Event Bus.

Endpoints:
    GET  /health     — System health
    GET  /status     — Detailed status
    GET  /services   — Registered services
    POST /event      — Publish event to Event Bus
    POST /shutdown   — Graceful shutdown
    WS   /ws         — Live event stream
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from backend.api.schemas import (
    ErrorResponse,
    EventRequest,
    EventResponse,
    HealthResponse,
    ServiceInfo,
    ServicesResponse,
    ShutdownRequest,
    ShutdownResponse,
    StatusResponse,
)
from backend.core.messages import SystemEvent

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Health ───────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """System health check."""
    registry = request.app.state.registry
    agent_manager = request.app.state.agent_manager
    start_time = request.app.state.start_time

    return HealthResponse(
        status="ok",
        uptime_s=round(time.time() - start_time, 2),
        services=len(registry.list_services()),
        agents=len(agent_manager.list_agents()),
    )


# ── Status ───────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    """Detailed system status."""
    registry = request.app.state.registry
    bus = request.app.state.bus
    scheduler = request.app.state.scheduler

    service_list = [
        ServiceInfo(name=name, type=stype)
        for name, stype in registry.get_status().items()
    ]

    return StatusResponse(
        status="running",
        services=service_list,
        event_bus=bus.get_stats(),
        scheduler=scheduler.get_status(),
    )


# ── Services ─────────────────────────────────────────────

@router.get("/services", response_model=ServicesResponse)
async def services(request: Request) -> ServicesResponse:
    """List all registered services."""
    registry = request.app.state.registry
    service_list = [
        ServiceInfo(name=name, type=stype)
        for name, stype in registry.get_status().items()
    ]
    return ServicesResponse(
        count=len(service_list),
        services=service_list,
    )


# ── Event Publishing ─────────────────────────────────────

@router.post("/event", response_model=EventResponse)
async def publish_event(request: Request, body: EventRequest) -> EventResponse:
    """
    Publish an event to the Event Bus.
    API never processes anything — it just forwards to the bus.
    """
    bus = request.app.state.bus

    event = SystemEvent(
        event_type=body.event_type,
        message=body.message,
        severity=body.severity,
        details=body.details,
        source="api",
    )
    handlers_notified = await bus.publish(event)

    return EventResponse(
        published=True,
        event_type=body.event_type,
        handlers_notified=handlers_notified,
    )


# ── Shutdown ─────────────────────────────────────────────

@router.post("/shutdown", response_model=ShutdownResponse)
async def shutdown(request: Request, body: ShutdownRequest) -> ShutdownResponse:
    """
    Request graceful shutdown.
    Publishes shutdown event, then signals uvicorn to stop.
    """
    bus = request.app.state.bus

    await bus.publish(SystemEvent(
        event_type="system",
        message=f"Shutdown requested: {body.reason}",
        severity="warning",
        source="api",
    ))

    logger.info("Shutdown requested via API: %s", body.reason)

    # Schedule actual shutdown after response is sent
    async def _do_shutdown() -> None:
        await asyncio.sleep(0.5)
        raise SystemExit(0)

    asyncio.create_task(_do_shutdown())

    return ShutdownResponse(
        status="shutting_down",
        reason=body.reason,
    )


# ── WebSocket ────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Live event stream via WebSocket.
    Client connects → receives all Event Bus events as JSON.
    """
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, receive pings/messages from client
            data = await websocket.receive_text()
            # Client can send "ping" to keep alive
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
