"""
TREDO — API Pydantic Schemas
Request/Response models for the REST API.
These are separate from internal models — API never exposes internals.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────

class EventRequest(BaseModel):
    """POST /event — publish an event to the Event Bus."""
    event_type: str = Field(..., description="Event type: exchange, system, config, error")
    message: str = Field(..., description="Human-readable message")
    severity: str = Field(default="info", description="debug, info, warning, error, critical")
    details: dict = Field(default_factory=dict, description="Extra data")


class ShutdownRequest(BaseModel):
    """POST /shutdown — graceful shutdown."""
    reason: str = Field(default="user_request", description="Shutdown reason")


# ── Responses ────────────────────────────────────────────

class HealthResponse(BaseModel):
    """GET /health"""
    status: str = "ok"
    uptime_s: float = 0.0
    services: int = 0
    agents: int = 0


class ServiceInfo(BaseModel):
    """Single service entry in /services response."""
    name: str
    type: str
    status: str = "registered"


class StatusResponse(BaseModel):
    """GET /status"""
    status: str = "running"
    services: list[ServiceInfo] = []
    event_bus: dict = {}
    scheduler: dict = {}


class ServicesResponse(BaseModel):
    """GET /services"""
    count: int = 0
    services: list[ServiceInfo] = []


class EventResponse(BaseModel):
    """POST /event response."""
    published: bool = True
    event_type: str = ""
    handlers_notified: int = 0


class ShutdownResponse(BaseModel):
    """POST /shutdown response."""
    status: str = "shutting_down"
    reason: str = ""


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    detail: str = ""
