"""
TREDO — Trend Features
SMA, EMA, VWAP
"""

from collections import deque
from typing import Any
from backend.intelligence.models import BaseFeature, FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


class SMA(BaseFeature):
    """Simple Moving Average."""
    DEFAULT_METADATA = FeatureMetadata(name="SMA", version=1, window=14, category="Trend", dependencies=["close"])
    
    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.history: deque[float] = deque(maxlen=self.window_size)
        self.sum = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        price = event.close_price
        
        if len(self.history) == self.window_size:
            oldest = self.history[0]
            self.sum -= oldest
            
        self.history.append(price)
        self.sum += price
        
        if len(self.history) == self.window_size:
            self._is_ready = True
            self._current_value = self.sum / self.window_size
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


class EMA(BaseFeature):
    """Exponential Moving Average."""
    DEFAULT_METADATA = FeatureMetadata(name="EMA", version=1, window=14, category="Trend", dependencies=["close"])
    
    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.multiplier = 2.0 / (self.window_size + 1.0)
        self.history: deque[float] = deque(maxlen=self.window_size)

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        price = event.close_price
        self.history.append(price)
        
        if len(self.history) < self.window_size:
            self._is_ready = False
            self._current_value = None
            return self.value
            
        if not self._is_ready:
            # Initialize EMA with SMA of the first N periods
            sma = sum(self.history) / self.window_size
            self._current_value = sma
            self._is_ready = True
        else:
            # Standard EMA formula
            if self._current_value is not None:
                self._current_value = (price - self._current_value) * self.multiplier + self._current_value
                
        return self.value


class VWAP(BaseFeature):
    """
    Volume Weighted Average Price.
    Normally resets daily, but for this generic version we'll track a rolling window.
    """
    DEFAULT_METADATA = FeatureMetadata(name="VWAP", version=1, window=14, category="Trend", dependencies=["high", "low", "close", "volume"])
    
    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        # Deque of (typical_price * volume, volume)
        self.history: deque[tuple[float, float]] = deque(maxlen=self.window_size)
        self.cumulative_pv = 0.0
        self.cumulative_v = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        typical_price = (event.high_price + event.low_price + event.close_price) / 3.0
        pv = typical_price * event.volume
        v = event.volume
        
        if len(self.history) == self.window_size:
            old_pv, old_v = self.history[0]
            self.cumulative_pv -= old_pv
            self.cumulative_v -= old_v
            
        self.history.append((pv, v))
        self.cumulative_pv += pv
        self.cumulative_v += v
        
        if len(self.history) == self.window_size:
            self._is_ready = True
            if self.cumulative_v > 0:
                self._current_value = self.cumulative_pv / self.cumulative_v
            else:
                self._current_value = typical_price
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


# Register features
feature_registry.register("SMA", SMA)
feature_registry.register("EMA", EMA)
feature_registry.register("VWAP", VWAP)
