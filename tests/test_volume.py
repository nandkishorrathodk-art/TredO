"""
TREDO — Volume Features Tests
Validates OBV and Volume SMA.
"""

import pytest
from backend.intelligence.models import FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


def test_obv_correctness():
    obv_cls = feature_registry.get_class("OBV")
    assert obv_cls is not None
    
    meta = FeatureMetadata(name="OBV", version=1, window=0, category="Volume")
    obv = obv_cls("BTC/USDT", meta)
    
    assert obv.is_ready is False
    
    # 1. First candle initializes OBV with its volume
    val = obv.update(CandleEvent(close_price=10.0, volume=100.0))
    assert val["ready"] is True
    assert val["value"] == 100.0
    
    # 2. Up candle (close > prev) -> OBV increases by volume
    val2 = obv.update(CandleEvent(close_price=12.0, volume=50.0))
    assert val2["value"] == 150.0
    
    # 3. Down candle (close < prev) -> OBV decreases by volume
    val3 = obv.update(CandleEvent(close_price=8.0, volume=75.0))
    assert val3["value"] == 75.0
    
    # 4. Flat candle (close == prev) -> OBV stays same
    val4 = obv.update(CandleEvent(close_price=8.0, volume=200.0))
    assert val4["value"] == 75.0
    
    # Check ID generation (no window)
    assert val4["id"] == "VOLUME.OBV"


def test_volume_sma_correctness():
    vol_sma_cls = feature_registry.get_class("VOL_SMA")
    assert vol_sma_cls is not None
    
    meta = FeatureMetadata(name="VOL_SMA", version=1, window=3, category="Volume")
    vol_sma = vol_sma_cls("BTC/USDT", meta)
    
    assert vol_sma.is_ready is False
    
    vol_sma.update(CandleEvent(close_price=10.0, volume=100.0))
    vol_sma.update(CandleEvent(close_price=12.0, volume=200.0))
    val = vol_sma.update(CandleEvent(close_price=11.0, volume=300.0))
    
    assert val["ready"] is True
    # (100 + 200 + 300) / 3 = 200
    assert val["value"] == 200.0
    
    val2 = vol_sma.update(CandleEvent(close_price=10.0, volume=400.0))
    # Window rolls: (200 + 300 + 400) / 3 = 300
    assert val2["value"] == 300.0
