"""
TREDO — Strategy Manager
Orchestrator for executing multiple rule-based strategies in parallel,
resolving consensus, and publishing final signals.
"""

import logging
import asyncio
from typing import Any

from backend.core.event_bus import EventBus
from backend.core.messages import SignalGenerated
from backend.intelligence.models import FeaturesUpdated
from backend.intelligence.feature_store import FeatureStore
from backend.strategy.models import Signal
from backend.strategy.base import BaseStrategy
from backend.strategy.registry import strategy_registry
from backend.strategy.consensus import BaseConsensus, WeightedVoteConsensus


logger = logging.getLogger(__name__)


class StrategyMetrics:
    def __init__(self):
        self.signals_generated = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

    @property
    def accuracy(self) -> float:
        total_resolved = self.wins + self.losses
        if total_resolved == 0:
            return 0.0
        return self.wins / total_resolved


class StrategyManager:
    def __init__(self, bus: EventBus, store: FeatureStore):
        self._bus = bus
        self._store = store
        self._running = False
        
        # Default consensus engine
        self.consensus_engine: BaseConsensus = WeightedVoteConsensus()
        
        # symbol -> list of strategy instances
        self._active_strategies: dict[str, list[BaseStrategy]] = {}
        
        # strategy_name -> weight
        self._weights: dict[str, float] = {}
        
        # strategy_name -> StrategyMetrics
        self._metrics: dict[str, StrategyMetrics] = {}

    async def start(self):
        """Start listening for feature updates."""
        if self._running:
            return
        self._bus.subscribe(FeaturesUpdated, self._on_features_updated)
        self._running = True
        logger.info("Strategy Manager started.")

    async def stop(self):
        """Stop processing strategies."""
        if not self._running:
            return
        self._bus.unsubscribe(FeaturesUpdated, self._on_features_updated)
        self._running = False
        logger.info("Strategy Manager stopped.")

    def enable_strategy(self, symbol: str, strategy_name: str, params: dict[str, Any] | None = None, weight: float = 1.0):
        """Initialize and activate a strategy for a specific symbol."""
        cls = strategy_registry.get_class(strategy_name)
        if not cls:
            logger.error("Cannot enable unknown strategy: %s", strategy_name)
            return

        instance = cls(symbol, params)
        
        if symbol not in self._active_strategies:
            self._active_strategies[symbol] = []
            
        # Avoid duplicate registration (could allow multiple instances with different params in future)
        for existing in self._active_strategies[symbol]:
            if existing.NAME == strategy_name:
                logger.warning("Strategy %s is already enabled for %s", strategy_name, symbol)
                return

        self._active_strategies[symbol].append(instance)
        self._weights[strategy_name] = weight
        if strategy_name not in self._metrics:
            self._metrics[strategy_name] = StrategyMetrics()
            
        logger.info("Enabled strategy %s for %s with weight %s", strategy_name, symbol, weight)

    def disable_strategy(self, symbol: str, strategy_name: str):
        """Deactivate a strategy for a symbol."""
        if symbol in self._active_strategies:
            self._active_strategies[symbol] = [
                s for s in self._active_strategies[symbol] if s.NAME != strategy_name
            ]
            logger.info("Disabled strategy %s for %s", strategy_name, symbol)

    def set_weight(self, strategy_name: str, weight: float):
        """Update the voting weight for a strategy."""
        self._weights[strategy_name] = weight
        logger.info("Set weight for %s to %s", strategy_name, weight)

    def get_metrics(self) -> dict[str, dict[str, Any]]:
        """Return memory metrics for all strategies."""
        res = {}
        for name, m in self._metrics.items():
            res[name] = {
                "signals_generated": m.signals_generated,
                "wins": m.wins,
                "losses": m.losses,
                "accuracy": m.accuracy,
                "total_pnl": m.total_pnl
            }
        return res

    async def _on_features_updated(self, event: FeaturesUpdated):
        """
        Triggered whenever the Feature Engine updates the FeatureStore.
        We evaluate all strategies for the symbol in parallel.
        """
        symbol = event.symbol
        strategies = self._active_strategies.get(symbol, [])
        
        if not strategies:
            return

        snapshot = self._store.get_all(symbol)
        
        # We run them in the thread pool because they are CPU-bound deterministic functions,
        # but since they are fast math, asyncio.to_thread or direct execution is fine.
        # Direct execution wrapped in try-except for isolation.
        
        signals: list[Signal] = []
        
        for strategy in strategies:
            try:
                sig = strategy.evaluate(snapshot)
                if sig:
                    signals.append(sig)
                    # Track metrics
                    self._metrics[strategy.NAME].signals_generated += 1
            except Exception as e:
                logger.error("Strategy %s crashed during evaluation on %s: %s", strategy.NAME, symbol, e)
                # Crash isolation - continue to the next strategy

        if not signals:
            return

        # 2. Consensus Engine
        final_signal = self.consensus_engine.compute(signals, self._weights)
        
        if not final_signal or final_signal.direction == "NONE":
            return

        # 3. Publish to Risk Engine
        out_msg = SignalGenerated(
            strategy=final_signal.strategy,
            symbol=final_signal.symbol,
            exchange=final_signal.exchange,
            market_type=final_signal.market_type,
            timeframe=final_signal.timeframe,
            direction=final_signal.direction,
            confidence=final_signal.confidence,
            reason=final_signal.reason
        )
        
        await self._bus.publish(out_msg)
