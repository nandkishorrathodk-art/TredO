"""
TREDO — EMA Cross Strategy
A continuous rule-based strategy that evaluates the Fast vs Slow EMA.
"""

from typing import Any
from backend.strategy.base import BaseStrategy
from backend.strategy.models import Signal
from backend.strategy.registry import strategy_registry


class EMACrossStrategy(BaseStrategy):
    """
    Evaluates whether the Fast EMA is above or below the Slow EMA.
    Emits a BUY if Fast > Slow.
    Emits a SELL if Fast < Slow.
    """
    NAME = "EMA_CROSS"
    VERSION = 1
    AUTHOR = "System"

    def __init__(self, symbol: str, params: dict[str, Any] | None = None):
        super().__init__(symbol, params)
        # Defaults
        self.fast_window = self.params.get("fast_window", 20)
        self.slow_window = self.params.get("slow_window", 50)

    def evaluate(self, snapshot: dict[str, dict[str, Any]]) -> Signal | None:
        fast_key = f"TREND.EMA.{self.fast_window}"
        slow_key = f"TREND.EMA.{self.slow_window}"

        fast_data = snapshot.get(fast_key)
        slow_data = snapshot.get(slow_key)

        if not fast_data or not fast_data.get("ready"):
            return None
        if not slow_data or not slow_data.get("ready"):
            return None

        fast_val = fast_data["value"]
        slow_val = slow_data["value"]

        timestamp = fast_data.get("timestamp", 0)

        # Basic voting logic
        if fast_val > slow_val:
            direction = "BUY"
            confidence = 0.8
            reason = f"EMA{self.fast_window} ({fast_val:.2f}) > EMA{self.slow_window} ({slow_val:.2f})"
        elif fast_val < slow_val:
            direction = "SELL"
            confidence = 0.8
            reason = f"EMA{self.fast_window} ({fast_val:.2f}) < EMA{self.slow_window} ({slow_val:.2f})"
        else:
            direction = "NONE"
            confidence = 0.5
            reason = "EMAs are exactly equal"

        return Signal(
            strategy=self.NAME,
            symbol=self.symbol,
            direction=direction,
            confidence=confidence,
            reason=reason,
            timestamp=timestamp
        )

# Register the strategy
strategy_registry.register(EMACrossStrategy.NAME, EMACrossStrategy)
