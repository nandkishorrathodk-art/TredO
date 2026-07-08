"""
TREDO — Strategies Tests
Validates the logic for all rule-based quantitative strategies.
"""

import pytest

from backend.strategy.registry import strategy_registry
import backend.strategies  # This runs the __init__ which registers them

def test_ema_cross_strategy():
    cls = strategy_registry.get_class("EMA_CROSS")
    assert cls is not None
    strategy = cls("BTC/USDT", {"fast_window": 20, "slow_window": 50})

    # Missing data
    assert strategy.evaluate({}) is None

    # Fast > Slow -> BUY
    snapshot_buy = {
        "TREND.EMA.20": {"value": 105.0, "ready": True},
        "TREND.EMA.50": {"value": 100.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_buy)
    assert sig is not None
    assert sig.direction == "BUY"
    assert sig.strategy == "EMA_CROSS"

    # Fast < Slow -> SELL
    snapshot_sell = {
        "TREND.EMA.20": {"value": 95.0, "ready": True},
        "TREND.EMA.50": {"value": 100.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_sell)
    assert sig is not None
    assert sig.direction == "SELL"

def test_rsi_reversion_strategy():
    cls = strategy_registry.get_class("RSI_REVERSION")
    assert cls is not None
    strategy = cls("BTC/USDT", {"window": 14, "oversold": 30.0, "overbought": 70.0})

    # Oversold -> BUY
    snapshot_buy = {
        "MOMENTUM.RSI.14": {"value": 25.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_buy)
    assert sig is not None
    assert sig.direction == "BUY"
    assert sig.confidence > 0.75  # Scaling works

    # Overbought -> SELL
    snapshot_sell = {
        "MOMENTUM.RSI.14": {"value": 75.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_sell)
    assert sig is not None
    assert sig.direction == "SELL"

    # Neutral -> NONE
    snapshot_none = {
        "MOMENTUM.RSI.14": {"value": 50.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_none)
    assert sig is not None
    assert sig.direction == "NONE"


def test_bollinger_reversion_strategy():
    cls = strategy_registry.get_class("BOLLINGER_REVERSION")
    assert cls is not None
    strategy = cls("BTC/USDT", {"window": 20})

    # Missing close price -> None
    assert strategy.evaluate({"VOLATILITY.BB.20": {"value": {"upper": 120, "lower": 80}, "ready": True}}) is None

    # Price below lower band -> BUY
    snapshot_buy = {
        "VOLATILITY.BB.20": {"value": {"upper": 120, "lower": 80}, "ready": True},
        "RAW.CLOSE": {"value": 75.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_buy)
    assert sig is not None
    assert sig.direction == "BUY"

    # Price above upper band -> SELL
    snapshot_sell = {
        "VOLATILITY.BB.20": {"value": {"upper": 120, "lower": 80}, "ready": True},
        "RAW.CLOSE": {"value": 125.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_sell)
    assert sig is not None
    assert sig.direction == "SELL"

    # Price inside bands -> NONE
    snapshot_none = {
        "VOLATILITY.BB.20": {"value": {"upper": 120, "lower": 80}, "ready": True},
        "RAW.CLOSE": {"value": 100.0, "ready": True}
    }
    sig = strategy.evaluate(snapshot_none)
    assert sig is not None
    assert sig.direction == "NONE"
