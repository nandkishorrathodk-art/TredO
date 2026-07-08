"""
TREDO — Strategy Engine
Deterministic, rule-based quantitative strategy engine.
"""

from backend.strategy.models import Signal
from backend.strategy.base import BaseStrategy
from backend.strategy.registry import strategy_registry

__all__ = [
    "Signal",
    "BaseStrategy",
    "strategy_registry",
]
