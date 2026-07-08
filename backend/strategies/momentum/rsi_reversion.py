"""
TREDO — RSI Reversion Strategy
Evaluates the standard Relative Strength Index to find overbought/oversold conditions.
"""

from typing import Any
from backend.strategy.base import BaseStrategy
from backend.strategy.models import Signal
from backend.strategy.registry import strategy_registry


class RSIReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion.
    Emits BUY when RSI < Oversold threshold.
    Emits SELL when RSI > Overbought threshold.
    Emits NONE when RSI is neutral.
    """
    NAME = "RSI_REVERSION"
    VERSION = 1
    AUTHOR = "System"

    def __init__(self, symbol: str, params: dict[str, Any] | None = None):
        super().__init__(symbol, params)
        self.window = self.params.get("window", 14)
        self.oversold = self.params.get("oversold", 30.0)
        self.overbought = self.params.get("overbought", 70.0)

    def evaluate(self, snapshot: dict[str, dict[str, Any]]) -> Signal | None:
        key = f"MOMENTUM.RSI.{self.window}"
        data = snapshot.get(key)

        if not data or not data.get("ready"):
            return None

        rsi = data["value"]
        timestamp = data.get("timestamp", 0)

        if rsi < self.oversold:
            direction = "BUY"
            confidence = 0.75 + (0.25 * ((self.oversold - rsi) / self.oversold)) # Scales up as RSI drops
            reason = f"RSI ({rsi:.1f}) < Oversold ({self.oversold})"
        elif rsi > self.overbought:
            direction = "SELL"
            confidence = 0.75 + (0.25 * ((rsi - self.overbought) / (100 - self.overbought)))
            reason = f"RSI ({rsi:.1f}) > Overbought ({self.overbought})"
        else:
            direction = "NONE"
            confidence = 0.0
            reason = f"RSI ({rsi:.1f}) is neutral"

        return Signal(
            strategy=self.NAME,
            symbol=self.symbol,
            direction=direction,
            confidence=min(1.0, confidence),
            reason=reason,
            timestamp=timestamp
        )

# Register the strategy
strategy_registry.register(RSIReversionStrategy.NAME, RSIReversionStrategy)
