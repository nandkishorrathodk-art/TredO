"""
TREDO — Typed Message Objects
Strong typing for all inter-module communication.
No random dicts — every message has a defined shape.

These messages flow through the Event Bus.
Modules publish and subscribe to message types, never call each other directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Base ─────────────────────────────────────────────────

@dataclass
class BaseMessage:
    """Base class for all messages in the system."""
    timestamp: str = field(default_factory=_now)
    source: str = "system"

    @property
    def type_name(self) -> str:
        return self.__class__.__name__


# ── Signal Messages ──────────────────────────────────────

@dataclass
class SignalGenerated(BaseMessage):
    """A trading signal has been generated."""
    symbol: str = ""
    side: str = ""           # "buy" or "sell"
    confidence: int = 0      # 0-100
    reasons: list[str] = field(default_factory=list)


# ── Risk Messages ────────────────────────────────────────

@dataclass
class RiskCheckRequest(BaseMessage):
    """Request risk validation for a proposed trade."""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    reason: str = ""
    leverage: float = 1.0


@dataclass
class RiskApproved(BaseMessage):
    """Risk engine approved the trade."""
    symbol: str = ""
    side: str = ""
    approved_amount: float = 0.0
    price: float = 0.0
    risk_pct: float = 0.0


@dataclass
class RiskRejected(BaseMessage):
    """Risk engine rejected the trade."""
    symbol: str = ""
    side: str = ""
    reasons: list[str] = field(default_factory=list)


# ── Trade Messages ───────────────────────────────────────

@dataclass
class TradeRequested(BaseMessage):
    """A trade has been requested for execution."""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    order_type: str = "market"
    reason: str = ""


@dataclass
class TradeExecuted(BaseMessage):
    """A trade has been executed on the exchange."""
    trade_id: str = ""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    cost: float = 0.0
    status: str = "closed"


@dataclass
class TradeClosed(BaseMessage):
    """A position has been closed."""
    trade_id: str = ""
    symbol: str = ""
    exit_price: float = 0.0
    pnl: float = 0.0


# ── Memory Messages ─────────────────────────────────────

@dataclass
class MemoryEvent(BaseMessage):
    """Something was logged to memory."""
    memory_type: str = ""    # "trade", "decision", "risk", "event"
    record_id: str = ""
    summary: str = ""


# ── System Messages ──────────────────────────────────────

@dataclass
class SystemEvent(BaseMessage):
    """A system-level event."""
    event_type: str = ""     # "exchange", "system", "config", "error"
    message: str = ""
    severity: str = "info"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class KillSwitchActivated(BaseMessage):
    """Emergency stop — all trading halted."""
    reason: str = ""


@dataclass
class HealthCheckRequest(BaseMessage):
    """Request health status from all services."""
    pass


@dataclass
class HealthCheckResponse(BaseMessage):
    """Health status from a service."""
    service: str = ""
    healthy: bool = True
    details: dict[str, Any] = field(default_factory=dict)
