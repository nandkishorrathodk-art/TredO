"""
TREDO — Volatility Features
Standard Deviation, ATR, Bollinger Bands.
"""

import math
from collections import deque
from typing import Any

from backend.intelligence.models import BaseFeature, FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent

# Need these for Bollinger Bands composition
from backend.intelligence.features.trend import SMA


class STDDEV(BaseFeature):
    """
    Standard Deviation over a rolling window.
    O(N) calculation, but with N typical = 20, it is extremely fast.
    """
    DEFAULT_METADATA = FeatureMetadata(
        name="STDDEV", version=1, window=20, category="Volatility", dependencies=["close"]
    )

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.history: deque[float] = deque(maxlen=self.window_size)

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        self.history.append(event.close_price)
        
        if len(self.history) == self.window_size:
            self._is_ready = True
            
            # Calculate mean
            mean = sum(self.history) / self.window_size
            
            # Calculate variance (population standard deviation)
            variance = sum((x - mean) ** 2 for x in self.history) / self.window_size
            self._current_value = math.sqrt(variance)
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


class ATR(BaseFeature):
    """
    Average True Range.
    Uses Wilder's Smoothing on the True Range.
    """
    DEFAULT_METADATA = FeatureMetadata(
        name="ATR", version=1, window=14, category="Volatility", dependencies=["high", "low", "close"]
    )

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        
        self.history: list[float] = [] # stores true range values
        self.previous_close: float | None = None
        self._current_atr: float = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        
        # Calculate True Range
        if self.previous_close is None:
            tr = event.high_price - event.low_price
        else:
            tr = max(
                event.high_price - event.low_price,
                abs(event.high_price - self.previous_close),
                abs(event.low_price - self.previous_close)
            )
            
        self.previous_close = event.close_price
        
        # Wilder's Smoothing Logic
        if len(self.history) < self.window_size:
            self.history.append(tr)
            self._is_ready = False
            self._current_value = None
            
            if len(self.history) == self.window_size:
                # Seed with simple average
                self._current_atr = sum(self.history) / self.window_size
                self._current_value = self._current_atr
                self._is_ready = True
                
            return self.value
            
        # Standard O(1) Wilder's smoothing
        self._current_atr = (self._current_atr * (self.window_size - 1) + tr) / self.window_size
        self._current_value = self._current_atr
        
        return self.value


class BollingerBands(BaseFeature):
    """
    Bollinger Bands.
    Combines an internal SMA and internal STDDEV.
    """
    DEFAULT_METADATA = FeatureMetadata(
        name="BB", version=1, window=20, category="Volatility", dependencies=["close"]
    )

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.multiplier = 2.0
        
        # Override output to dictionary
        self._current_value: dict[str, float] | None = None
        
        # Compose sub-features with the same window
        sma_meta = FeatureMetadata(name="SMA", version=1, window=self.window_size, category="Trend")
        std_meta = FeatureMetadata(name="STDDEV", version=1, window=self.window_size, category="Volatility")
        
        self.sma = SMA(symbol, sma_meta)
        self.stddev = STDDEV(symbol, std_meta)

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        
        sma_out = self.sma.update(event)
        std_out = self.stddev.update(event)
        
        if sma_out["ready"] and std_out["ready"]:
            self._is_ready = True
            middle = sma_out["value"]
            std = std_out["value"]
            
            self._current_value = {
                "upper": middle + (self.multiplier * std),
                "middle": middle,
                "lower": middle - (self.multiplier * std)
            }
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


feature_registry.register("STDDEV", STDDEV)
feature_registry.register("ATR", ATR)
feature_registry.register("BB", BollingerBands)
