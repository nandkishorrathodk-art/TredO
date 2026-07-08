"""
TREDO — Execution Models
Order and Position models with proper state machines.

Order States:
    NEW → VALIDATED → ACCEPTED → FILLED → CLOSED
                                    or
    NEW → REJECTED
    VALIDATED → REJECTED
    ACCEPTED → CANCELLED
    FILLED → CANCELLED (partial)

Position States:
    OPEN → CLOSED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _order_id() -> str:
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


def _position_id() -> str:
    return f"POS-{uuid.uuid4().hex[:12].upper()}"


# ── Order State Machine ──────────────────────────────────

class OrderState(Enum):
    NEW = "new"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    FILLED = "filled"
    CLOSED = "closed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


ORDER_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.NEW: {OrderState.VALIDATED, OrderState.REJECTED},
    OrderState.VALIDATED: {OrderState.ACCEPTED, OrderState.REJECTED},
    OrderState.ACCEPTED: {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED},
    OrderState.FILLED: {OrderState.CLOSED, OrderState.CANCELLED},
    OrderState.CLOSED: set(),
    OrderState.REJECTED: set(),
    OrderState.CANCELLED: set(),
}


class InvalidOrderTransition(Exception):
    """Raised when an invalid order state transition is attempted."""


# ── Order ────────────────────────────────────────────────

@dataclass
class Order:
    """A trading order with full state machine lifecycle."""
    symbol: str
    side: str             # "buy" or "sell"
    amount: float
    price: float
    order_type: str = "market"   # "market" or "limit"
    reason: str = ""

    # Auto-generated
    order_id: str = field(default_factory=_order_id)
    state: OrderState = OrderState.NEW
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    fill_price: float = 0.0
    fill_amount: float = 0.0
    rejection_reasons: list[str] = field(default_factory=list)

    def transition(self, new_state: OrderState, **kwargs: Any) -> None:
        """Transition to a new state with validation."""
        valid = ORDER_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            raise InvalidOrderTransition(
                f"Order {self.order_id}: cannot transition "
                f"{self.state.value} → {new_state.value}"
            )
        self.state = new_state
        self.updated_at = _now()

        if new_state == OrderState.FILLED:
            self.fill_price = kwargs.get("fill_price", self.price)
            self.fill_amount = kwargs.get("fill_amount", self.amount)
        elif new_state == OrderState.REJECTED:
            self.rejection_reasons = kwargs.get("reasons", [])

    @property
    def is_terminal(self) -> bool:
        return self.state in (OrderState.CLOSED, OrderState.REJECTED, OrderState.CANCELLED)

    @property
    def cost(self) -> float:
        return self.fill_price * self.fill_amount

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "price": self.price,
            "order_type": self.order_type,
            "reason": self.reason,
            "state": self.state.value,
            "fill_price": self.fill_price,
            "fill_amount": self.fill_amount,
            "rejection_reasons": self.rejection_reasons,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Position ─────────────────────────────────────────────

class PositionState(Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Position:
    """An open or closed trading position."""
    symbol: str
    side: str
    entry_price: float
    amount: float

    position_id: str = field(default_factory=_position_id)
    state: PositionState = PositionState.OPEN
    opened_at: str = field(default_factory=_now)
    closed_at: str = ""
    exit_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.state == PositionState.OPEN

    @property
    def notional(self) -> float:
        """Current notional value of the position."""
        return self.entry_price * self.amount

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL at a given price."""
        if self.side == "buy":
            return (current_price - self.entry_price) * self.amount
        else:
            return (self.entry_price - current_price) * self.amount

    def close(self, exit_price: float) -> float:
        """Close the position and calculate realized PnL."""
        if self.state != PositionState.OPEN:
            raise ValueError(f"Position {self.position_id} is already {self.state.value}")

        if self.side == "buy":
            self.realized_pnl = (exit_price - self.entry_price) * self.amount
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.amount

        self.exit_price = exit_price
        self.state = PositionState.CLOSED
        self.closed_at = _now()
        return self.realized_pnl

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "amount": self.amount,
            "state": self.state.value,
            "exit_price": self.exit_price,
            "realized_pnl": self.realized_pnl,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
        }
