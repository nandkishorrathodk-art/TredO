"""
TREDO — Bollinger Bands Reversion Strategy
Evaluates the current price against Bollinger Band bounds.
"""

from typing import Any
from backend.strategy.base import BaseStrategy
from backend.strategy.models import Signal
from backend.strategy.registry import strategy_registry


class BollingerReversionStrategy(BaseStrategy):
    """
    Bollinger Mean Reversion.
    Emits BUY when Close Price < Lower Band.
    Emits SELL when Close Price > Upper Band.
    """
    NAME = "BOLLINGER_REVERSION"
    VERSION = 1
    AUTHOR = "System"

    def __init__(self, symbol: str, params: dict[str, Any] | None = None):
        super().__init__(symbol, params)
        self.window = self.params.get("window", 20)

    def evaluate(self, snapshot: dict[str, dict[str, Any]]) -> Signal | None:
        bb_key = f"VOLATILITY.BB.{self.window}"
        bb_data = snapshot.get(bb_key)
        close_data = snapshot.get("RAW.CLOSE")

        if not bb_data or not bb_data.get("ready") or not close_data:
            return None

        # bb_data["value"] is a dict with upper, middle, lower
        bands = bb_data["value"]
        upper = bands.get("upper", 0)
        lower = bands.get("lower", 0)
        
        close_price = close_data["value"]
        timestamp = bb_data.get("timestamp", 0)

        # To avoid division by zero if bands are flat
        band_width = upper - lower
        if band_width == 0:
            return None

        if close_price < lower:
            direction = "BUY"
            # Confidence scales by how far below the band the price is
            distance_pct = (lower - close_price) / close_price
            confidence = min(1.0, 0.75 + (distance_pct * 10)) 
            reason = f"Price ({close_price:.2f}) < Lower Band ({lower:.2f})"
            
        elif close_price > upper:
            direction = "SELL"
            distance_pct = (close_price - upper) / close_price
            confidence = min(1.0, 0.75 + (distance_pct * 10))
            reason = f"Price ({close_price:.2f}) > Upper Band ({upper:.2f})"
            
        else:
            direction = "NONE"
            confidence = 0.0
            reason = "Price is within Bollinger Bands"

        return Signal(
            strategy=self.NAME,
            symbol=self.symbol,
            direction=direction,
            confidence=confidence,
            reason=reason,
            timestamp=timestamp
        )

# Register the strategy
strategy_registry.register(BollingerReversionStrategy.NAME, BollingerReversionStrategy)
