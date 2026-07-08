"""
TREDO — Strategy Engine
Deterministic, rule-based quantitative strategy engine.
"""

from backend.strategy.models import Signal
from backend.strategy.base import BaseStrategy
from backend.strategy.registry import strategy_registry
from backend.strategy.consensus import BaseConsensus, MajorityVoteConsensus, WeightedVoteConsensus
from backend.strategy.manager import StrategyManager, StrategyMetrics

__all__ = [
    "Signal",
    "BaseStrategy",
    "strategy_registry",
    "BaseConsensus",
    "MajorityVoteConsensus",
    "WeightedVoteConsensus",
    "StrategyManager",
    "StrategyMetrics",
]
