"""
TREDO — Position Manager
Tracks open and closed positions. Calculates PnL.
Minimal: open, close, average price, realized/unrealized PnL.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.execution.models import Position, PositionState

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Manages trading positions.
    - Opens positions from filled orders.
    - Closes positions at exit price.
    - Tracks realized and unrealized PnL.
    """

    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}
        self._closed: list[Position] = []

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        amount: float,
    ) -> Position:
        """Open a new position."""
        pos = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            amount=amount,
        )
        self._positions[pos.position_id] = pos
        logger.info(
            "Position opened: %s %s %s %.4f @ %.2f",
            pos.position_id, side.upper(), symbol, amount, entry_price,
        )
        return pos

    def close_position(self, position_id: str, exit_price: float) -> Position:
        """Close a position and calculate realized PnL."""
        if position_id not in self._positions:
            raise KeyError(f"Position {position_id} not found")

        pos = self._positions[position_id]
        pnl = pos.close(exit_price)

        # Move to closed list
        del self._positions[position_id]
        self._closed.append(pos)

        logger.info(
            "Position closed: %s PnL: %.2f",
            position_id, pnl,
        )
        return pos

    def get_position(self, position_id: str) -> Position:
        """Get an open position by ID."""
        if position_id not in self._positions:
            raise KeyError(f"Position {position_id} not found")
        return self._positions[position_id]

    def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        """Get all open positions, optionally filtered by symbol."""
        positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        return positions

    def get_closed_positions(self, symbol: str | None = None) -> list[Position]:
        """Get all closed positions, optionally filtered by symbol."""
        if symbol:
            return [p for p in self._closed if p.symbol == symbol]
        return list(self._closed)

    def total_realized_pnl(self) -> float:
        """Total realized PnL across all closed positions."""
        return sum(p.realized_pnl for p in self._closed)

    def total_unrealized_pnl(self, prices: dict[str, float]) -> float:
        """Total unrealized PnL at current prices."""
        total = 0.0
        for pos in self._positions.values():
            if pos.symbol in prices:
                total += pos.unrealized_pnl(prices[pos.symbol])
        return total

    def total_exposure(self) -> float:
        """Total notional exposure of open positions."""
        return sum(p.notional for p in self._positions.values())

    def get_summary(self, prices: dict[str, float] | None = None) -> dict[str, Any]:
        """Get position manager summary."""
        return {
            "open_count": len(self._positions),
            "closed_count": len(self._closed),
            "realized_pnl": self.total_realized_pnl(),
            "unrealized_pnl": self.total_unrealized_pnl(prices or {}),
            "total_exposure": self.total_exposure(),
        }

    def clear(self) -> None:
        """Clear all positions. For testing."""
        self._positions.clear()
        self._closed.clear()
