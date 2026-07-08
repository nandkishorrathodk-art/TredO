"""
TREDO — Strategy Base Tests
Validates the core interfaces of the quantitative Strategy Engine.
"""

from typing import Any

from backend.strategy.models import Signal
from backend.strategy.base import BaseStrategy
from backend.strategy.registry import strategy_registry


class MockStrategy(BaseStrategy):
    """A dummy strategy for testing the registry and interface."""
    NAME = "MOCK_STRATEGY"
    VERSION = 1
    AUTHOR = "Test"

    def evaluate(self, snapshot: dict[str, dict[str, Any]]) -> Signal | None:
        # Dummy logic: If EMA > 100, BUY
        ema_data = snapshot.get("TREND.EMA.20")
        if ema_data and ema_data.get("ready"):
            if ema_data["value"] > 100.0:
                return Signal(
                    strategy=self.NAME,
                    symbol=self.symbol,
                    direction="BUY",
                    confidence=0.8,
                    reason="EMA > 100",
                    exchange="binance",
                    timeframe="1m",
                    timestamp=1000
                )
        return None


def test_strategy_registration():
    strategy_registry.register("MOCK_STRATEGY", MockStrategy)
    
    cls = strategy_registry.get_class("MOCK_STRATEGY")
    assert cls is not None
    assert cls.NAME == "MOCK_STRATEGY"


def test_base_strategy_evaluate():
    strategy = MockStrategy("BTC/USDT")
    
    # Empty snapshot
    assert strategy.evaluate({}) is None
    
    # Snapshot where EMA is not ready
    snapshot_not_ready = {
        "TREND.EMA.20": {"value": 105.0, "ready": False}
    }
    assert strategy.evaluate(snapshot_not_ready) is None
    
    # Snapshot where EMA is ready but <= 100
    snapshot_low = {
        "TREND.EMA.20": {"value": 90.0, "ready": True}
    }
    assert strategy.evaluate(snapshot_low) is None
    
    # Snapshot where EMA is ready and > 100
    snapshot_high = {
        "TREND.EMA.20": {"value": 110.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_high)
    assert sig is not None
    assert sig.direction == "BUY"
    assert sig.confidence == 0.8
    assert sig.strategy == "MOCK_STRATEGY"
