"""
TREDO — Paper Exchange
Simulated exchange for paper trading.
Fills orders instantly at current price. No real money.
Tracks simulated balances.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.execution.exchange_interface import ExchangeInterface
from backend.execution.models import Order, OrderState

logger = logging.getLogger(__name__)


class PaperExchange(ExchangeInterface):
    """
    Paper (simulated) exchange.
    - Fills market orders instantly at the set price.
    - Tracks virtual balances.
    - No real money. No network calls.
    """

    def __init__(self, initial_balance: float = 10_000.0) -> None:
        self._balance = initial_balance
        self._initial_balance = initial_balance
        self._prices: dict[str, float] = {}
        self._orders: dict[str, Order] = {}

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def initial_balance(self) -> float:
        return self._initial_balance

    def set_price(self, symbol: str, price: float) -> None:
        """Set the simulated market price for a symbol."""
        self._prices[symbol] = price

    async def get_current_price(self, symbol: str) -> float:
        """Get the simulated market price."""
        if symbol not in self._prices:
            raise ValueError(f"No price set for {symbol}. Call set_price() first.")
        return self._prices[symbol]

    async def execute_order(self, order: Order) -> Order:
        """
        Execute an order on the paper exchange.
        Market orders fill instantly at current price.
        """
        # Get current price
        if order.symbol not in self._prices:
            raise ValueError(f"No price set for {order.symbol}")

        fill_price = self._prices[order.symbol]
        cost = fill_price * order.amount

        # Check balance for buys
        if order.side == "buy":
            if cost > self._balance:
                order.transition(OrderState.REJECTED, reasons=["Insufficient balance"])
                return order
            self._balance -= cost
        else:  # sell
            self._balance += cost

        # Fill the order
        order.transition(OrderState.FILLED, fill_price=fill_price, fill_amount=order.amount)

        # Store
        self._orders[order.order_id] = order

        logger.info(
            "Paper %s %s %.4f @ %.2f (balance: %.2f)",
            order.side.upper(), order.symbol,
            order.amount, fill_price, self._balance,
        )
        return order

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order."""
        order = self._orders.get(order_id)
        if order and not order.is_terminal:
            order.transition(OrderState.CANCELLED)
            return True
        return False

    def get_name(self) -> str:
        return "PaperExchange"

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.get_name(),
            "balance": self._balance,
            "initial_balance": self._initial_balance,
            "pnl": self._balance - self._initial_balance,
            "prices": dict(self._prices),
            "total_orders": len(self._orders),
        }

    def reset(self) -> None:
        """Reset to initial state."""
        self._balance = self._initial_balance
        self._prices.clear()
        self._orders.clear()
