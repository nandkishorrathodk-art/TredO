"""
TREDO — Strategy Registry
Maintains a dynamic registry of all available quantitative strategies.
"""

from typing import Type
import logging
from backend.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

class StrategyRegistry:
    """Singleton registry for dynamically loading strategy plugins."""
    
    def __init__(self):
        self._strategies: dict[str, Type[BaseStrategy]] = {}

    def register(self, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """Register a new strategy class."""
        if name in self._strategies:
            logger.warning("Strategy %s is already registered. Overwriting.", name)
        self._strategies[name] = strategy_class
        logger.debug("Registered strategy: %s", name)

    def get_class(self, name: str) -> Type[BaseStrategy] | None:
        """Retrieve a strategy class by its registered name."""
        return self._strategies.get(name)

    def get_all(self) -> dict[str, Type[BaseStrategy]]:
        """Retrieve all registered strategies."""
        return dict(self._strategies)


# Singleton instance
strategy_registry = StrategyRegistry()
