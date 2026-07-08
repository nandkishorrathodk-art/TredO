"""
TREDO — Base Strategy Interface
Strict, deterministic interface for all quantitative strategies.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.strategy.models import Signal


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Rules for developers:
    1. NEVER make API calls to exchanges.
    2. NEVER access the database.
    3. NEVER maintain external state outside the class.
    4. Strategies MUST be deterministic — same input, same output.
    """
    
    # Define these in your strategy class
    NAME: str = "UnknownStrategy"
    VERSION: int = 1
    AUTHOR: str = "System"

    def __init__(self, symbol: str, params: dict[str, Any] | None = None):
        self.symbol = symbol
        self.params = params or {}

    @abstractmethod
    def evaluate(self, snapshot: dict[str, dict[str, Any]]) -> Signal | None:
        """
        Evaluate the latest Feature Store snapshot and return a Signal.
        
        Args:
            snapshot: The full dictionary of features for this symbol.
                      Format: {"TREND.EMA.20": {"value": 100.0, "ready": True}, ...}
                      
        Returns:
            Signal object if a trading opportunity is found, otherwise None.
        """
        pass
