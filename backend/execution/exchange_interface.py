"""
TREDO — Exchange Interface
Abstract interface for execution engines.
Both PaperExchange and live exchange (CCXT) implement this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.execution.models import Order


class ExchangeInterface(ABC):
    """
    Abstract interface for trade execution.
    PaperExchange and LiveExchange both implement this.
    """

    @abstractmethod
    async def execute_order(self, order: Order) -> Order:
        """
        Execute an order and return the filled order.
        Raises on failure.
        """

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if successful."""

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """Get the current market price for a symbol."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this exchange implementation."""
