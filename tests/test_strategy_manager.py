"""
TREDO — Strategy Manager Tests
Tests orchestration, crash isolation, hot reloading, and consensus engines.
"""

import pytest
from typing import Any

from backend.core.event_bus import EventBus
from backend.core.messages import SignalGenerated
from backend.intelligence.models import FeaturesUpdated
from backend.intelligence.feature_store import FeatureStore
from backend.strategy.models import Signal
from backend.strategy.base import BaseStrategy
from backend.strategy.registry import strategy_registry
from backend.strategy.consensus import MajorityVoteConsensus, WeightedVoteConsensus
from backend.strategy.manager import StrategyManager, StrategyMetrics


# ── Mock Strategies ─────────────────────────────────────────────────────────

class BuyStrategy(BaseStrategy):
    NAME = "BUY_STRAT"
    def evaluate(self, snapshot):
        return Signal("BUY_STRAT", self.symbol, "BUY", 0.8, "Buy Reason")

class SellStrategy(BaseStrategy):
    NAME = "SELL_STRAT"
    def evaluate(self, snapshot):
        return Signal("SELL_STRAT", self.symbol, "SELL", 0.9, "Sell Reason")

class NoneStrategy(BaseStrategy):
    NAME = "NONE_STRAT"
    def evaluate(self, snapshot):
        return Signal("NONE_STRAT", self.symbol, "NONE", 0.0, "None Reason")

class CrashStrategy(BaseStrategy):
    NAME = "CRASH_STRAT"
    def evaluate(self, snapshot):
        raise ValueError("Simulated strategy crash")

class SkipStrategy(BaseStrategy):
    NAME = "SKIP_STRAT"
    def evaluate(self, snapshot):
        return None

strategy_registry.register("BUY_STRAT", BuyStrategy)
strategy_registry.register("SELL_STRAT", SellStrategy)
strategy_registry.register("NONE_STRAT", NoneStrategy)
strategy_registry.register("CRASH_STRAT", CrashStrategy)
strategy_registry.register("SKIP_STRAT", SkipStrategy)


# ── Consensus Tests ─────────────────────────────────────────────────────────

def test_majority_consensus_empty():
    engine = MajorityVoteConsensus()
    assert engine.compute([]) is None

def test_majority_consensus_buy_wins():
    engine = MajorityVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "BUY", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "BUY", 0.8, "R2"),
        Signal("S3", "BTC/USDT", "SELL", 0.8, "R3"),
    ]
    res = engine.compute(sigs)
    assert res is not None
    assert res.direction == "BUY"
    assert res.strategy == "CONSENSUS"

def test_majority_consensus_sell_wins():
    engine = MajorityVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "SELL", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "SELL", 0.8, "R2"),
    ]
    res = engine.compute(sigs)
    assert res.direction == "SELL"

def test_majority_consensus_tie_none():
    engine = MajorityVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "BUY", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "SELL", 0.8, "R2"),
    ]
    res = engine.compute(sigs)
    assert res.direction == "NONE"

def test_weighted_consensus_empty():
    engine = WeightedVoteConsensus()
    assert engine.compute([]) is None

def test_weighted_consensus_zero_weights():
    engine = WeightedVoteConsensus()
    sigs = [Signal("S1", "BTC/USDT", "BUY", 0.8, "R1")]
    res = engine.compute(sigs, {"S1": 0.0})
    assert res is None

def test_weighted_consensus_buy_wins():
    engine = WeightedVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "BUY", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "SELL", 0.9, "R2"),
    ]
    weights = {"S1": 2.0, "S2": 1.0}
    # BUY score: 0.8 * 2.0 = 1.6
    # SELL score: 0.9 * 1.0 = 0.9
    res = engine.compute(sigs, weights)
    assert res.direction == "BUY"
    assert res.confidence == 1.6 / 3.0

def test_weighted_consensus_sell_wins():
    engine = WeightedVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "BUY", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "SELL", 0.9, "R2"),
    ]
    weights = {"S1": 1.0, "S2": 2.0}
    # BUY score: 0.8
    # SELL score: 1.8
    res = engine.compute(sigs, weights)
    assert res.direction == "SELL"

def test_weighted_consensus_tie_none():
    engine = WeightedVoteConsensus()
    sigs = [
        Signal("S1", "BTC/USDT", "BUY", 0.8, "R1"),
        Signal("S2", "BTC/USDT", "SELL", 0.8, "R2"),
    ]
    res = engine.compute(sigs, {"S1": 1.0, "S2": 1.0})
    assert res.direction == "NONE"


# ── Metrics Tests ───────────────────────────────────────────────────────────

def test_strategy_metrics_accuracy():
    m = StrategyMetrics()
    assert m.accuracy == 0.0
    m.wins = 1
    assert m.accuracy == 1.0
    m.losses = 1
    assert m.accuracy == 0.5


# ── Manager Basic Flow Tests ────────────────────────────────────────────────

@pytest.fixture
def bus():
    return EventBus()

@pytest.fixture
def store():
    return FeatureStore()

@pytest.fixture
def manager(bus, store):
    return StrategyManager(bus, store)

@pytest.mark.asyncio
async def test_manager_start_stop(manager):
    assert not manager._running
    await manager.start()
    assert manager._running
    await manager.start() # idempotency
    assert manager._running
    await manager.stop()
    assert not manager._running
    await manager.stop() # idempotency
    assert not manager._running

def test_manager_enable_unknown(manager, caplog):
    manager.enable_strategy("BTC/USDT", "FAKE")
    assert "Cannot enable unknown strategy" in caplog.text

def test_manager_enable_duplicate(manager, caplog):
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    assert "already enabled" in caplog.text

def test_manager_disable(manager):
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    assert len(manager._active_strategies["BTC/USDT"]) == 1
    manager.disable_strategy("BTC/USDT", "BUY_STRAT")
    assert len(manager._active_strategies["BTC/USDT"]) == 0

def test_manager_disable_unknown(manager):
    manager.disable_strategy("BTC/USDT", "FAKE")
    # should not crash

def test_manager_set_weight(manager):
    manager.set_weight("BUY_STRAT", 2.5)
    assert manager._weights["BUY_STRAT"] == 2.5

def test_manager_get_metrics(manager):
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    manager._metrics["BUY_STRAT"].wins = 5
    metrics = manager.get_metrics()
    assert "BUY_STRAT" in metrics
    assert metrics["BUY_STRAT"]["wins"] == 5

# ── Integration & Flow Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_flow_no_strategies(manager, bus):
    await manager.start()
    # No strategies enabled. Should just return silently.
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))

@pytest.mark.asyncio
async def test_manager_flow_all_skip(manager, bus):
    manager.enable_strategy("BTC/USDT", "SKIP_STRAT")
    await manager.start()
    
    signals = []
    async def capture(msg: SignalGenerated):
        signals.append(msg)
    bus.subscribe(SignalGenerated, capture)
    
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))
    assert len(signals) == 0

@pytest.mark.asyncio
async def test_manager_flow_none_wins(manager, bus):
    manager.enable_strategy("BTC/USDT", "NONE_STRAT")
    await manager.start()
    
    signals = []
    async def capture(msg: SignalGenerated):
        signals.append(msg)
    bus.subscribe(SignalGenerated, capture)
    
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))
    # Consensus None -> no event published
    assert len(signals) == 0

@pytest.mark.asyncio
async def test_manager_crash_isolation(manager, bus, caplog):
    """Ensure that one crashing strategy doesn't kill the manager, and others succeed."""
    manager.enable_strategy("BTC/USDT", "CRASH_STRAT")
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    await manager.start()
    
    signals = []
    async def capture(msg: SignalGenerated):
        signals.append(msg)
    bus.subscribe(SignalGenerated, capture)
    
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))
    
    # CRASH_STRAT crashed, logged error
    assert "crashed during evaluation" in caplog.text
    
    # But BUY_STRAT succeeded, so Consensus engine should output BUY
    assert len(signals) == 1
    assert signals[0].direction == "BUY"
    assert signals[0].strategy == "CONSENSUS"

@pytest.mark.asyncio
async def test_manager_multi_symbol_isolation(manager, bus):
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    manager.enable_strategy("ETH/USDT", "SELL_STRAT")
    await manager.start()
    
    signals = []
    async def capture(msg: SignalGenerated):
        signals.append(msg)
    bus.subscribe(SignalGenerated, capture)
    
    # Trigger ETH
    await bus.publish(FeaturesUpdated(symbol="ETH/USDT", features={"a": 1}))
    assert len(signals) == 1
    assert signals[0].symbol == "ETH/USDT"
    assert signals[0].direction == "SELL"

@pytest.mark.asyncio
async def test_manager_weights_applied(manager, bus):
    manager.enable_strategy("BTC/USDT", "BUY_STRAT")
    manager.enable_strategy("BTC/USDT", "SELL_STRAT")
    
    # Give SELL a massive weight
    manager.set_weight("BUY_STRAT", 1.0)
    manager.set_weight("SELL_STRAT", 10.0)
    
    await manager.start()
    
    signals = []
    async def capture(msg: SignalGenerated):
        signals.append(msg)
    bus.subscribe(SignalGenerated, capture)
    
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))
    assert len(signals) == 1
    assert signals[0].direction == "SELL"
    
    # Now flip the weight
    manager.set_weight("BUY_STRAT", 100.0)
    
    signals.clear()
    await bus.publish(FeaturesUpdated(symbol="BTC/USDT", features={"a": 1}))
    assert len(signals) == 1
    assert signals[0].direction == "BUY"
