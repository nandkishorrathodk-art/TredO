"""
TREDO — Volatility Features Tests
Validates STDDEV, ATR, and Bollinger Bands.
"""

import pytest
from backend.intelligence.models import FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


def test_stddev_correctness():
    std_cls = feature_registry.get_class("STDDEV")
    assert std_cls is not None
    
    meta = FeatureMetadata(name="STDDEV", version=1, window=3, category="Volatility")
    std = std_cls("BTC/USDT", meta)
    
    assert std.is_ready is False
    
    # Push 3 identical values: variance should be exactly 0
    std.update(CandleEvent(close_price=10.0))
    std.update(CandleEvent(close_price=10.0))
    val = std.update(CandleEvent(close_price=10.0))
    
    assert val["ready"] is True
    assert val["value"] == 0.0
    
    # Push varying values
    # Window will have [10, 10, 13] -> Mean = 11
    # Var = ((10-11)^2 + (10-11)^2 + (13-11)^2) / 3 = (1 + 1 + 4) / 3 = 2
    # StdDev = sqrt(2) ≈ 1.4142
    val2 = std.update(CandleEvent(close_price=13.0))
    assert val2["value"] == pytest.approx(1.4142, 0.001)


def test_atr_correctness():
    atr_cls = feature_registry.get_class("ATR")
    assert atr_cls is not None
    
    meta = FeatureMetadata(name="ATR", version=1, window=3, category="Volatility")
    atr = atr_cls("BTC/USDT", meta)
    
    # 1. First candle (no previous close)
    # TR = High - Low = 12 - 8 = 4
    atr.update(CandleEvent(high_price=12.0, low_price=8.0, close_price=10.0))
    assert atr.is_ready is False
    
    # 2. Second candle (Gap up)
    # High=20, Low=15, prev close=10
    # TR = max(20-15, |20-10|, |15-10|) = max(5, 10, 5) = 10
    atr.update(CandleEvent(high_price=20.0, low_price=15.0, close_price=18.0))
    
    # 3. Third candle
    # High=22, Low=16, prev close=18
    # TR = max(22-16, |22-18|, |16-18|) = max(6, 4, 2) = 6
    val = atr.update(CandleEvent(high_price=22.0, low_price=16.0, close_price=20.0))
    
    # Initial SMA of TR = (4 + 10 + 6) / 3 = 20 / 3 ≈ 6.666
    assert val["ready"] is True
    assert val["value"] == pytest.approx(6.666, 0.001)
    
    # 4. Fourth candle (O(1) smoothing)
    # High=25, Low=21, prev close=20
    # TR = max(4, 5, 1) = 5
    # New ATR = (6.666 * 2 + 5) / 3 = (13.333 + 5) / 3 = 18.333 / 3 = 6.111
    val2 = atr.update(CandleEvent(high_price=25.0, low_price=21.0, close_price=23.0))
    assert val2["value"] == pytest.approx(6.111, 0.001)


def test_bollinger_bands_correctness():
    bb_cls = feature_registry.get_class("BB")
    assert bb_cls is not None
    
    meta = FeatureMetadata(name="BB", version=1, window=3, category="Volatility")
    bb = bb_cls("BTC/USDT", meta)
    
    # Since BB wraps SMA and STDDEV, we just need to verify the outputs are structured and correct
    bb.update(CandleEvent(close_price=10.0))
    bb.update(CandleEvent(close_price=10.0))
    val = bb.update(CandleEvent(close_price=13.0))
    
    # SMA of [10, 10, 13] is 11
    # STDDEV is ~1.4142
    # Upper = 11 + (2 * 1.4142) = 13.8284
    # Lower = 11 - (2 * 1.4142) = 8.1715
    
    assert val["ready"] is True
    assert "upper" in val["value"]
    assert "middle" in val["value"]
    assert "lower" in val["value"]
    
    assert val["value"]["middle"] == 11.0
    assert val["value"]["upper"] == pytest.approx(13.828, 0.001)
    assert val["value"]["lower"] == pytest.approx(8.171, 0.001)
    
    # Verify ID generation works
    assert val["id"] == "VOLATILITY.BB.3"
