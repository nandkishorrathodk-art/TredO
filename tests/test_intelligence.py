"""
TREDO — Market Intelligence Tests
Validates feature registration, structural output, category filtering,
and correctness of Trend and Momentum indicators.
"""

import pytest

from backend.intelligence.models import FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


# ── Registry Tests ───────────────────────────────────────

def test_feature_registration():
    """Ensure features are registered correctly."""
    features = feature_registry.list_features()
    assert "SMA" in features
    assert "RSI" in features
    
    # Test Category filtering
    trend_features = feature_registry.get_by_category("Trend")
    trend_names = [cls.__name__ for cls in trend_features]
    assert "SMA" in trend_names
    assert "RSI" not in trend_names
    
    momentum_features = feature_registry.get_by_category("Momentum")
    mom_names = [cls.__name__ for cls in momentum_features]
    assert "RSI" in mom_names
    assert "SMA" not in mom_names


# ── Trend Tests ──────────────────────────────────────────

def test_sma_correctness():
    sma_cls = feature_registry.get_class("SMA")
    meta = FeatureMetadata(name="SMA", version=1, window=3, category="Trend")
    sma = sma_cls("BTC/USDT", meta)
    
    assert sma.is_ready is False
    assert sma.value["ready"] is False
    
    sma.update(CandleEvent(close_price=10.0, timestamp=100))
    sma.update(CandleEvent(close_price=20.0, timestamp=200))
    val = sma.update(CandleEvent(close_price=30.0, timestamp=300))
    
    assert sma.is_ready is True
    assert val["ready"] is True
    assert val["value"] == 20.0
    assert val["timestamp"] == 300
    
    val2 = sma.update(CandleEvent(close_price=40.0, timestamp=400))
    assert val2["value"] == 30.0


# ── EMA Tests ────────────────────────────────────────────

def test_ema_correctness():
    ema_cls = feature_registry.get_class("EMA")
    meta = FeatureMetadata(name="EMA", version=1, window=3, category="Trend")
    ema = ema_cls("BTC/USDT", meta)
    
    assert ema.is_ready is False
    
    # Push first 3 to init SMA seed
    ema.update(CandleEvent(close_price=10.0))
    ema.update(CandleEvent(close_price=20.0))
    val1 = ema.update(CandleEvent(close_price=30.0))
    
    # Initial SMA = (10+20+30)/3 = 20.0
    assert val1["ready"] is True
    assert val1["value"] == 20.0
    
    # Next price is 40. Multiplier for window 3 is 2 / (3 + 1) = 0.5
    # EMA = (40 - 20) * 0.5 + 20 = 10 + 20 = 30.0
    val2 = ema.update(CandleEvent(close_price=40.0))
    assert val2["value"] == 30.0


# ── VWAP Tests ───────────────────────────────────────────

def test_vwap_correctness():
    vwap_cls = feature_registry.get_class("VWAP")
    meta = FeatureMetadata(name="VWAP", version=1, window=2, category="Trend")
    vwap = vwap_cls("BTC/USDT", meta)
    
    assert vwap.is_ready is False
    
    vwap.update(CandleEvent(high_price=10.0, low_price=8.0, close_price=9.0, volume=100.0))
    val = vwap.update(CandleEvent(high_price=12.0, low_price=10.0, close_price=11.0, volume=200.0))
    
    assert val["ready"] is True
    assert pytest.approx(val["value"], 0.001) == 10.333
    
    val2 = vwap.update(CandleEvent(high_price=15.0, low_price=13.0, close_price=14.0, volume=50.0))
    assert pytest.approx(val2["value"], 0.001) == 11.6


# ── Momentum Tests ───────────────────────────────────────

def test_rsi_correctness():
    rsi_cls = feature_registry.get_class("RSI")
    meta = FeatureMetadata(name="RSI", version=1, window=3, category="Momentum")
    rsi = rsi_cls("BTC/USDT", meta)
    
    # Uptrend
    rsi.update(CandleEvent(close_price=10.0))  # seed
    rsi.update(CandleEvent(close_price=12.0))  # +2
    rsi.update(CandleEvent(close_price=14.0))  # +2
    val = rsi.update(CandleEvent(close_price=16.0))  # +2 (Now it's seeded: length 4)
    
    assert val["ready"] is True
    assert val["value"] == 100.0  # Pure uptrend = 100 RSI
    
    # Downtrend
    rsi2 = rsi_cls("ETH/USDT", meta)
    rsi2.update(CandleEvent(close_price=20.0))
    rsi2.update(CandleEvent(close_price=18.0))
    rsi2.update(CandleEvent(close_price=16.0))
    val2 = rsi2.update(CandleEvent(close_price=14.0))
    
    assert val2["ready"] is True
    assert val2["value"] == 0.0  # Pure downtrend = 0 RSI


def test_roc_correctness():
    roc_cls = feature_registry.get_class("ROC")
    meta = FeatureMetadata(name="ROC", version=1, window=2, category="Momentum")
    roc = roc_cls("BTC/USDT", meta)
    
    roc.update(CandleEvent(close_price=100.0))
    roc.update(CandleEvent(close_price=110.0))
    val = roc.update(CandleEvent(close_price=120.0)) # window = 2, compares 120 with 100
    
    assert val["ready"] is True
    assert val["value"] == 20.0  # (120 - 100) / 100 * 100


def test_stochastic_correctness():
    stoch_cls = feature_registry.get_class("STOCH")
    meta = FeatureMetadata(name="STOCH", version=1, window=3, category="Momentum")
    stoch = stoch_cls("BTC/USDT", meta)
    
    # Highs: 15, 20, 25 (Highest = 25)
    # Lows:  5,  10, 15 (Lowest = 5)
    # Closes: 10, 15, 20
    # For candle 3: K = (20 - 5) / (25 - 5) * 100 = 15 / 20 * 100 = 75
    
    stoch.update(CandleEvent(high_price=15.0, low_price=5.0, close_price=10.0))
    stoch.update(CandleEvent(high_price=20.0, low_price=10.0, close_price=15.0))
    val = stoch.update(CandleEvent(high_price=25.0, low_price=15.0, close_price=20.0))
    
    # Wait, Stoch smoothing is 3, so we need 3 K-values to get a ready state.
    assert val["ready"] is False  # we only have 1 K value so far
    
    stoch.update(CandleEvent(high_price=30.0, low_price=20.0, close_price=25.0)) # K2
    val2 = stoch.update(CandleEvent(high_price=35.0, low_price=25.0, close_price=30.0)) # K3
    
    assert val2["ready"] is True
    # K should be calculated correctly, and D should be the avg.
    assert "k" in val2["value"]
    assert "d" in val2["value"]
