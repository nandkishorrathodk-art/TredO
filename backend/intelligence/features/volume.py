"""
TREDO — Volume Features
On-Balance Volume (OBV), Volume SMA.
"""

from collections import deque
from typing import Any

from backend.intelligence.models import BaseFeature, FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


class OBV(BaseFeature):
    """
    On-Balance Volume.
    Adds volume on up days, subtracts volume on down days.
    No rolling window (cumulative).
    """
    DEFAULT_METADATA = FeatureMetadata(
        name="OBV", version=1, window=0, category="Volume", dependencies=["close", "volume"]
    )

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.previous_close: float | None = None
        self._current_value: float = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        
        if self.previous_close is None:
            # First candle, initialize OBV with its volume (or 0, but convention is usually its volume)
            self._current_value = event.volume
            self._is_ready = True
        else:
            if event.close_price > self.previous_close:
                self._current_value += event.volume
            elif event.close_price < self.previous_close:
                self._current_value -= event.volume
            # If equal, OBV is unchanged.
            
        self.previous_close = event.close_price
        
        return self.value


class VolumeSMA(BaseFeature):
    """
    Simple Moving Average of Volume.
    Useful for comparing current volume against historical relative volume.
    """
    DEFAULT_METADATA = FeatureMetadata(
        name="VOL_SMA", version=1, window=14, category="Volume", dependencies=["volume"]
    )

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.history: deque[float] = deque(maxlen=self.window_size)
        self.sum = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        vol = event.volume
        
        if len(self.history) == self.window_size:
            oldest = self.history[0]
            self.sum -= oldest
            
        self.history.append(vol)
        self.sum += vol
        
        if len(self.history) == self.window_size:
            self._is_ready = True
            self._current_value = self.sum / self.window_size
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


feature_registry.register("OBV", OBV)
feature_registry.register("VOL_SMA", VolumeSMA)
