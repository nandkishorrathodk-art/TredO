"""
TREDO — Memory Models
Typed dataclasses for all 4 memory types.
No ORM, no SQLAlchemy — just clean Python dataclasses.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    """UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    """Short unique ID for trades."""
    return str(uuid.uuid4())[:12]


@dataclass
class TradeRecord:
    """A single trade record in the journal."""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    reason: str
    id: str = field(default_factory=_uuid)
    exit_price: float | None = None
    pnl: float | None = None
    status: str = "open"
    created_at: str = field(default_factory=_now)
    closed_at: str | None = None

    def to_row(self) -> tuple[Any, ...]:
        """Convert to SQLite row tuple."""
        return (
            self.id, self.symbol, self.side, self.quantity,
            self.entry_price, self.exit_price, self.pnl,
            self.status, self.reason, self.created_at, self.closed_at,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> TradeRecord:
        """Create from SQLite row dict."""
        return cls(
            id=row["id"], symbol=row["symbol"], side=row["side"],
            quantity=row["quantity"], entry_price=row["entry_price"],
            exit_price=row["exit_price"], pnl=row["pnl"],
            status=row["status"], reason=row["reason"],
            created_at=row["created_at"], closed_at=row["closed_at"],
        )


@dataclass
class DecisionRecord:
    """An AI decision record."""
    decision: str
    confidence: int
    reasons: list[str]
    symbol: str | None = None
    source: str = "system"
    id: int | None = None
    created_at: str = field(default_factory=_now)

    def to_row(self) -> tuple[Any, ...]:
        return (
            self.decision, self.confidence, json.dumps(self.reasons),
            self.symbol, self.source, self.created_at,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> DecisionRecord:
        return cls(
            id=row["id"], decision=row["decision"],
            confidence=row["confidence"],
            reasons=json.loads(row["reasons"]),
            symbol=row["symbol"], source=row["source"],
            created_at=row["created_at"],
        )


@dataclass
class RiskRecord:
    """A risk event — rejected trade, kill switch, cool-down."""
    action: str
    reasons: list[str]
    symbol: str | None = None
    side: str | None = None
    amount: float | None = None
    source: str = "risk_engine"
    id: int | None = None
    created_at: str = field(default_factory=_now)

    def to_row(self) -> tuple[Any, ...]:
        return (
            self.action, self.symbol, self.side, self.amount,
            json.dumps(self.reasons), self.source, self.created_at,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> RiskRecord:
        return cls(
            id=row["id"], action=row["action"], symbol=row["symbol"],
            side=row["side"], amount=row["amount"],
            reasons=json.loads(row["reasons"]), source=row["source"],
            created_at=row["created_at"],
        )


@dataclass
class EventRecord:
    """A system event record."""
    event_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    id: int | None = None
    created_at: str = field(default_factory=_now)

    def to_row(self) -> tuple[Any, ...]:
        return (
            self.event_type, self.message,
            json.dumps(self.details), self.severity, self.created_at,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> EventRecord:
        return cls(
            id=row["id"], event_type=row["event_type"],
            message=row["message"],
            details=json.loads(row["details"]),
            severity=row["severity"], created_at=row["created_at"],
        )
