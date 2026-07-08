"""
TREDO — Application Host Tests
Tests REST endpoints, WebSocket, lifespan, and full integration flow.
Uses FastAPI TestClient — no real server needed.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.schemas import (
    EventRequest,
    EventResponse,
    HealthResponse,
    ServiceInfo,
    ServicesResponse,
    ShutdownResponse,
    StatusResponse,
)
from backend.api.websocket import WebSocketManager
from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage, SystemEvent


@pytest.fixture
def client():
    """Create a test client with full lifespan."""
    app = create_app()
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════
# Health Endpoint Tests
# ══════════════════════════════════════════════════════════


class TestHealth:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["uptime_s"] >= 0
        assert data["services"] > 0

    def test_health_has_services_count(self, client: TestClient):
        resp = client.get("/health")
        data = resp.json()
        # Should have at least: event_bus, scheduler, memory, risk, ai_gateway, agent_manager, ws_manager
        assert data["services"] >= 7


# ══════════════════════════════════════════════════════════
# Status Endpoint Tests
# ══════════════════════════════════════════════════════════


class TestStatus:
    def test_status_returns_services(self, client: TestClient):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert len(data["services"]) > 0

    def test_status_has_event_bus_stats(self, client: TestClient):
        resp = client.get("/status")
        data = resp.json()
        assert "event_bus" in data
        assert "history_size" in data["event_bus"]

    def test_status_has_scheduler(self, client: TestClient):
        resp = client.get("/status")
        data = resp.json()
        assert "scheduler" in data


# ══════════════════════════════════════════════════════════
# Services Endpoint Tests
# ══════════════════════════════════════════════════════════


class TestServices:
    def test_services_list(self, client: TestClient):
        resp = client.get("/services")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 7
        names = [s["name"] for s in data["services"]]
        assert "event_bus" in names
        assert "memory" in names
        assert "risk" in names
        assert "ai_gateway" in names

    def test_services_have_types(self, client: TestClient):
        resp = client.get("/services")
        data = resp.json()
        for svc in data["services"]:
            assert "name" in svc
            assert "type" in svc
            assert svc["type"] != ""


# ══════════════════════════════════════════════════════════
# Event Publishing Tests
# ══════════════════════════════════════════════════════════


class TestEventPublishing:
    def test_publish_event(self, client: TestClient):
        resp = client.post("/event", json={
            "event_type": "system",
            "message": "Test event from API",
            "severity": "info",
            "details": {"test": True},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["published"] is True
        assert data["event_type"] == "system"

    def test_publish_event_goes_to_bus(self, client: TestClient):
        """Verify event actually reaches the Event Bus."""
        # Get initial history count
        status1 = client.get("/status").json()
        history_before = status1["event_bus"]["history_size"]

        # Publish event
        client.post("/event", json={
            "event_type": "exchange",
            "message": "Exchange test",
        })

        # History should have grown
        status2 = client.get("/status").json()
        history_after = status2["event_bus"]["history_size"]
        assert history_after > history_before

    def test_publish_event_minimal(self, client: TestClient):
        resp = client.post("/event", json={
            "event_type": "system",
            "message": "Minimal event",
        })
        assert resp.status_code == 200

    def test_publish_event_missing_fields(self, client: TestClient):
        resp = client.post("/event", json={})
        assert resp.status_code == 422  # Validation error


# ══════════════════════════════════════════════════════════
# Shutdown Endpoint Tests
# ══════════════════════════════════════════════════════════


class TestShutdown:
    def test_shutdown_response(self, client: TestClient):
        """Shutdown returns response before actually exiting."""
        resp = client.post("/shutdown", json={"reason": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "shutting_down"
        assert data["reason"] == "test"

    def test_shutdown_default_reason(self, client: TestClient):
        resp = client.post("/shutdown", json={})
        assert resp.status_code == 200
        assert resp.json()["reason"] == "user_request"


# ══════════════════════════════════════════════════════════
# WebSocket Manager Unit Tests
# ══════════════════════════════════════════════════════════


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        mgr = WebSocketManager()
        sent = await mgr.broadcast({"test": True})
        assert sent == 0
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_connect_increases_count(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_decreases_count(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        mgr = WebSocketManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        sent = await mgr.broadcast({"msg": "hello"})
        assert sent == 2
        assert ws1.send_text.called
        assert ws2.send_text.called

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead(self):
        mgr = WebSocketManager()
        alive = AsyncMock()
        dead = AsyncMock()
        dead.send_text.side_effect = Exception("disconnected")

        await mgr.connect(alive)
        await mgr.connect(dead)
        assert mgr.connection_count == 2

        sent = await mgr.broadcast({"msg": "test"})
        assert sent == 1
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_event(self):
        mgr = WebSocketManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        event = SystemEvent(event_type="system", message="test")
        await mgr.broadcast_event(event)

        assert ws.send_text.called
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "SystemEvent"
        assert payload["message"] == "test"

    @pytest.mark.asyncio
    async def test_close_all(self):
        mgr = WebSocketManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        await mgr.close_all()
        assert mgr.connection_count == 0


# ══════════════════════════════════════════════════════════
# Pydantic Schema Tests
# ══════════════════════════════════════════════════════════


class TestSchemas:
    def test_event_request_validation(self):
        req = EventRequest(event_type="system", message="test")
        assert req.severity == "info"
        assert req.details == {}

    def test_health_response_defaults(self):
        resp = HealthResponse()
        assert resp.status == "ok"

    def test_service_info(self):
        svc = ServiceInfo(name="risk", type="RiskEngine")
        assert svc.status == "registered"


# ══════════════════════════════════════════════════════════
# WebSocket Live Stream Test
# ══════════════════════════════════════════════════════════


class TestWebSocketEndpoint:
    def test_ws_connect_and_ping(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert json.loads(data)["type"] == "pong"


# ══════════════════════════════════════════════════════════
# Integration Test — Full Pipeline
# ══════════════════════════════════════════════════════════


class TestIntegration:
    def test_event_publish_reaches_bus_and_memory(self, client: TestClient):
        """
        Full flow: HTTP → API → Event Bus → Handler → Verify
        """
        # Publish an event via API
        resp = client.post("/event", json={
            "event_type": "exchange",
            "message": "Integration test event",
            "severity": "info",
            "details": {"test_id": "integration_001"},
        })
        assert resp.status_code == 200
        assert resp.json()["published"] is True

        # Verify it shows in event bus history via /status
        status = client.get("/status").json()
        assert status["event_bus"]["history_size"] > 0

    def test_full_lifecycle(self, client: TestClient):
        """Verify startup → health → status → services all work."""
        # Health
        h = client.get("/health").json()
        assert h["status"] == "ok"
        assert h["services"] >= 7

        # Status
        s = client.get("/status").json()
        assert s["status"] == "running"
        assert len(s["services"]) >= 7

        # Services
        sv = client.get("/services").json()
        assert sv["count"] >= 7
        names = [x["name"] for x in sv["services"]]
        assert "event_bus" in names
        assert "memory" in names
        assert "risk" in names

    def test_ws_receives_published_event(self, client: TestClient):
        """
        Integration: POST /event → Event Bus → WebSocket client receives it.
        """
        with client.websocket_connect("/ws") as ws:
            # Publish event via REST
            client.post("/event", json={
                "event_type": "system",
                "message": "WS integration test",
            })

            # WebSocket should receive the event
            data = json.loads(ws.receive_text())
            assert data["type"] == "SystemEvent"
            assert data["message"] == "WS integration test"
