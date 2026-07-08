"""
TREDO — Strategy Models
Defines the pure Signal object returned by all trading strategies.
"""

from dataclasses import dataclass

@dataclass
class Signal:
    """
    Standardized trading signal.
    Every strategy must return this exact object.
    """
    strategy: str
    symbol: str
    direction: str       # "BUY", "SELL", or "NONE"
    confidence: float    # 0.0 to 1.0
    reason: str | list[str]
    exchange: str = "binance"
    market_type: str = "linear"
    timeframe: str = "1m"
    timestamp: int = 0
