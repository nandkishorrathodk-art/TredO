"""
TREDO — Intelligence Pipeline Tests
Validates the Feature Store and Intelligence Pipeline integration.
"""

import pytest
from backend.core.event_bus import EventBus
from backend.intelligence.feature_store import FeatureStore
from backend.intelligence.pipeline import IntelligencePipeline
from backend.intelligence.models import FeaturesUpdated
from backend.market.events import CandleEvent


@pytest.fixture
def store():
    return FeatureStore()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def pipeline(bus, store):
    return IntelligencePipeline(bus, store)


def test_feature_store(store):
    store.update("BTC/USDT", "TREND.EMA.20", {"name": "EMA", "value": 100.0, "ready": True})
    store.update("BTC/USDT", "MOMENTUM.RSI.14", {"name": "RSI", "value": 55.5, "ready": True})
    
    assert store.get("BTC/USDT", "TREND.EMA.20")["value"] == 100.0
    
    all_features = store.get_all("BTC/USDT")
    assert "TREND.EMA.20" in all_features
    assert "MOMENTUM.RSI.14" in all_features
    
    assert store.get("ETH/USDT", "TREND.EMA.20") is None
    
    store.clear()
    assert store.get("BTC/USDT", "TREND.EMA.20") is None


@pytest.mark.asyncio
async def test_intelligence_pipeline_e2e(bus, pipeline, store):
    # 1. Add some features
    pipeline.add_feature("BTC/USDT", "SMA", 2)
    pipeline.add_feature("BTC/USDT", "OBV", 0)
    
    # Track emitted FeaturesUpdated events
    emitted_events = []
    
    async def capture_features(event: FeaturesUpdated):
        emitted_events.append(event)
        
    bus.subscribe(FeaturesUpdated, capture_features)
    
    # Start the pipeline (subscribes to CandleEvent)
    await pipeline.start()
    
    # 2. Fire first candle (SMA not ready yet, OBV is ready immediately)
    c1 = CandleEvent(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1m",
        timestamp=1000,
        open_price=10.0,
        high_price=12.0,
        low_price=9.0,
        close_price=10.0,
        volume=100.0,
        is_closed=True
    )
    await bus.publish(c1)
    
    # Pipeline should have pushed OBV to store, SMA to store (but not ready)
    assert store.get("BTC/USDT", "VOLUME.OBV")["ready"] is True
    assert store.get("BTC/USDT", "TREND.SMA.2")["ready"] is False
    
    # Only ready features are emitted
    assert len(emitted_events) == 1
    assert "VOLUME.OBV" in emitted_events[0].features
    assert "TREND.SMA.2" not in emitted_events[0].features
    
    # 3. Fire second candle (SMA becomes ready)
    c2 = CandleEvent(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1m",
        timestamp=1060,
        open_price=10.0,
        high_price=15.0,
        low_price=10.0,
        close_price=14.0,
        volume=50.0,
        is_closed=True
    )
    await bus.publish(c2)
    
    # SMA should be ready now: (10 + 14) / 2 = 12
    # OBV should be: 100 + 50 = 150 (since 14 > 10)
    assert store.get("BTC/USDT", "TREND.SMA.2")["ready"] is True
    assert store.get("BTC/USDT", "TREND.SMA.2")["value"] == 12.0
    
    assert store.get("BTC/USDT", "VOLUME.OBV")["value"] == 150.0
    
    assert len(emitted_events) == 2
    assert "VOLUME.OBV" in emitted_events[1].features
    assert "TREND.SMA.2" in emitted_events[1].features
    assert emitted_events[1].features["TREND.SMA.2"] == 12.0
    
    await pipeline.stop()
