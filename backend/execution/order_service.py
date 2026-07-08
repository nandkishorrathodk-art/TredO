"""
TREDO — Order Service
Orchestrates the full order lifecycle via Event Bus.
Never calls modules directly — publishes events at each step.

Flow:
    OrderSubmitted → Risk Validation → OrderFilled → PositionOpened → MemoryLogged
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage, MemoryEvent, SystemEvent
from backend.execution.models import Order, OrderState, Position
from backend.execution.paper_exchange import PaperExchange
from backend.execution.position_manager import PositionManager
from backend.risk.engine import RiskEngine, TradeRequest

logger = logging.getLogger(__name__)


# ── Order Event Messages ─────────────────────────────────
from dataclasses import dataclass, field
from backend.core.messages import _now


@dataclass
class OrderSubmitted(BaseMessage):
    """An order has been submitted for processing."""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    order_type: str = "market"
    reason: str = ""


@dataclass
class OrderValidated(BaseMessage):
    """Risk engine approved the order."""
    order_id: str = ""
    symbol: str = ""
    approved_size: float = 0.0
    risk_pct: float = 0.0


@dataclass
class OrderRejected(BaseMessage):
    """Risk engine rejected the order."""
    order_id: str = ""
    symbol: str = ""
    reasons: list[str] = field(default_factory=list)


@dataclass
class OrderFilled(BaseMessage):
    """Order has been filled on the exchange."""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    amount: float = 0.0
    fill_price: float = 0.0
    cost: float = 0.0


@dataclass
class OrderCancelled(BaseMessage):
    """Order has been cancelled."""
    order_id: str = ""
    symbol: str = ""
    reason: str = ""


@dataclass
class PositionOpened(BaseMessage):
    """A new position has been opened."""
    position_id: str = ""
    symbol: str = ""
    side: str = ""
    entry_price: float = 0.0
    amount: float = 0.0


@dataclass
class PositionClosed(BaseMessage):
    """A position has been closed."""
    position_id: str = ""
    symbol: str = ""
    exit_price: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class PnLUpdated(BaseMessage):
    """PnL summary has been updated."""
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    balance: float = 0.0


class OrderService:
    """
    Orchestrates the full order lifecycle.
    Uses Event Bus for every state change.

    Flow:
        submit_order() →
            1. Create Order (NEW)
            2. Risk validate → VALIDATED or REJECTED
            3. Execute on exchange → FILLED
            4. Open position
            5. Publish events at every step
    """

    def __init__(
        self,
        bus: EventBus,
        risk: RiskEngine,
        exchange: PaperExchange,
        positions: PositionManager,
        portfolio_value: float = 10_000.0,
    ) -> None:
        self._bus = bus
        self._risk = risk
        self._exchange = exchange
        self._positions = positions
        self._portfolio_value = portfolio_value
        self._orders: dict[str, Order] = {}

    async def submit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        order_type: str = "market",
        reason: str = "",
    ) -> Order:
        """
        Submit a new order through the full lifecycle.
        Returns the order in its final state.
        """
        # 1. Create order
        order = Order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            reason=reason,
        )
        self._orders[order.order_id] = order

        await self._bus.publish(OrderSubmitted(
            order_id=order.order_id,
            symbol=symbol, side=side, amount=amount,
            price=price, order_type=order_type, reason=reason,
            source="order_service",
        ))

        # 2. Risk validation
        trade_req = TradeRequest(
            symbol=symbol, side=side, amount=amount,
            price=price, order_type=order_type, reason=reason,
        )
        open_positions = {
            p.symbol: {"value": p.notional}
            for p in self._positions.get_open_positions()
        }
        verdict = self._risk.validate(
            trade=trade_req,
            portfolio_value=self._portfolio_value,
            open_positions=open_positions,
        )

        if verdict.rejected:
            order.transition(OrderState.REJECTED, reasons=verdict.rejection_reasons)
            await self._bus.publish(OrderRejected(
                order_id=order.order_id, symbol=symbol,
                reasons=verdict.rejection_reasons,
                source="order_service",
            ))
            return order

        # Use risk-approved position size
        order.amount = verdict.position_size
        order.transition(OrderState.VALIDATED)

        await self._bus.publish(OrderValidated(
            order_id=order.order_id, symbol=symbol,
            approved_size=verdict.position_size,
            risk_pct=verdict.risk_pct,
            source="order_service",
        ))

        # 3. Execute on exchange
        order.transition(OrderState.ACCEPTED)
        filled_order = await self._exchange.execute_order(order)

        if filled_order.state == OrderState.REJECTED:
            await self._bus.publish(OrderRejected(
                order_id=order.order_id, symbol=symbol,
                reasons=filled_order.rejection_reasons,
                source="order_service",
            ))
            return filled_order

        await self._bus.publish(OrderFilled(
            order_id=filled_order.order_id,
            symbol=symbol, side=side,
            amount=filled_order.fill_amount,
            fill_price=filled_order.fill_price,
            cost=filled_order.cost,
            source="order_service",
        ))

        # 4. Record the trade in risk engine
        self._risk.record_trade_result(pnl=0.0)  # PnL is 0 at entry

        # 5. Open position
        position = self._positions.open_position(
            symbol=symbol,
            side=side,
            entry_price=filled_order.fill_price,
            amount=filled_order.fill_amount,
        )

        await self._bus.publish(PositionOpened(
            position_id=position.position_id,
            symbol=symbol, side=side,
            entry_price=position.entry_price,
            amount=position.amount,
            source="order_service",
        ))

        # 6. Update portfolio value
        self._portfolio_value = self._exchange.balance

        return filled_order

    async def close_position(
        self,
        position_id: str,
        exit_price: float | None = None,
    ) -> Position:
        """Close a position at exit price (or current market price)."""
        pos = self._positions.get_position(position_id)

        if exit_price is None:
            exit_price = await self._exchange.get_current_price(pos.symbol)

        closed = self._positions.close_position(position_id, exit_price)

        # Update balance — add back the closed value
        if closed.side == "buy":
            self._exchange._balance += exit_price * closed.amount
        else:
            self._exchange._balance -= exit_price * closed.amount

        # Record PnL
        self._risk.record_trade_result(pnl=closed.realized_pnl)

        await self._bus.publish(PositionClosed(
            position_id=closed.position_id,
            symbol=closed.symbol,
            exit_price=exit_price,
            realized_pnl=closed.realized_pnl,
            source="order_service",
        ))

        await self._bus.publish(PnLUpdated(
            realized_pnl=self._positions.total_realized_pnl(),
            unrealized_pnl=self._positions.total_unrealized_pnl(
                {s: p for s, p in self._exchange._prices.items()}
            ),
            balance=self._exchange.balance,
            source="order_service",
        ))

        self._portfolio_value = self._exchange.balance
        return closed

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_all_orders(self) -> list[Order]:
        return list(self._orders.values())

    def get_summary(self) -> dict[str, Any]:
        prices = dict(self._exchange._prices)
        return {
            "total_orders": len(self._orders),
            "balance": self._exchange.balance,
            "positions": self._positions.get_summary(prices),
            "portfolio_value": self._portfolio_value,
        }
