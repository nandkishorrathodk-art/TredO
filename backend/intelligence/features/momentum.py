"""
TREDO — Momentum Features
RSI, ROC, Stochastic Oscillator
Independent mathematical implementations (no dependencies on Trend features).
"""

from collections import deque
from typing import Any

from backend.intelligence.models import BaseFeature, FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent


class RSI(BaseFeature):
    """
    Relative Strength Index (Wilder's Smoothing).
    O(1) update performance.
    """
    DEFAULT_METADATA = FeatureMetadata(name="RSI", version=1, window=14, category="Momentum", dependencies=["close"])
    
    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        
        self.history: list[float] = []
        self.avg_gain = 0.0
        self.avg_loss = 0.0
        self.last_price = 0.0

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        price = event.close_price
        
        if not self.history:
            self.history.append(price)
            self.last_price = price
            self._is_ready = False
            self._current_value = None
            return self.value
            
        change = price - self.last_price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        
        self.last_price = price
        self.history.append(price)
        
        # Warmup period (first N periods, calculate simple average)
        if len(self.history) <= self.window_size + 1:
            self.avg_gain += gain
            self.avg_loss += loss
            
            # Exactly N periods of changes, seed the SMMA
            if len(self.history) == self.window_size + 1:
                self.avg_gain /= self.window_size
                self.avg_loss /= self.window_size
                
                if self.avg_loss == 0:
                    self._current_value = 100.0
                else:
                    rs = self.avg_gain / self.avg_loss
                    self._current_value = 100.0 - (100.0 / (1.0 + rs))
                self._is_ready = True
            else:
                self._is_ready = False
                self._current_value = None
                
            return self.value

        # Standard O(1) Wilder's Smoothing Update
        self.avg_gain = (self.avg_gain * (self.window_size - 1) + gain) / self.window_size
        self.avg_loss = (self.avg_loss * (self.window_size - 1) + loss) / self.window_size
        
        if self.avg_loss == 0:
            self._current_value = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self._current_value = 100.0 - (100.0 / (1.0 + rs))
            
        return self.value


class ROC(BaseFeature):
    """
    Rate of Change.
    (Current - Past) / Past * 100
    """
    DEFAULT_METADATA = FeatureMetadata(name="ROC", version=1, window=9, category="Momentum", dependencies=["close"])

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        # We need N+1 prices to compare current with N periods ago
        self.history: deque[float] = deque(maxlen=self.window_size + 1)

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        self.history.append(event.close_price)
        
        if len(self.history) == self.window_size + 1:
            self._is_ready = True
            past_price = self.history[0]
            current_price = self.history[-1]
            if past_price != 0:
                self._current_value = ((current_price - past_price) / past_price) * 100.0
            else:
                self._current_value = 0.0
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


class Stochastic(BaseFeature):
    """
    Stochastic Oscillator (%K and %D).
    %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
    %D = 3-period SMA of %K
    """
    DEFAULT_METADATA = FeatureMetadata(name="STOCH", version=1, window=14, category="Momentum", dependencies=["high", "low", "close"])

    def __init__(self, symbol: str, metadata: FeatureMetadata | None = None):
        super().__init__(symbol, metadata or self.DEFAULT_METADATA)
        self.window_size = self.metadata.window
        self.smooth_window = 3
        
        # Deque of (high, low)
        self.history: deque[tuple[float, float]] = deque(maxlen=self.window_size)
        self.k_history: deque[float] = deque(maxlen=self.smooth_window)
        
        # Override _current_value to be a dictionary
        self._current_value: dict[str, float] | None = None

    def update(self, event: CandleEvent) -> dict[str, Any]:
        self._current_timestamp = event.timestamp
        
        self.history.append((event.high_price, event.low_price))
        
        if len(self.history) < self.window_size:
            self._is_ready = False
            self._current_value = None
            return self.value
            
        # N=14 is extremely small, max/min over deque is effectively O(1)
        highest_high = max(x[0] for x in self.history)
        lowest_low = min(x[1] for x in self.history)
        
        if highest_high == lowest_low:
            k = 50.0
        else:
            k = ((event.close_price - lowest_low) / (highest_high - lowest_low)) * 100.0
            
        self.k_history.append(k)
        
        if len(self.k_history) == self.smooth_window:
            self._is_ready = True
            d = sum(self.k_history) / self.smooth_window
            self._current_value = {"k": k, "d": d}
        else:
            self._is_ready = False
            self._current_value = None
            
        return self.value


feature_registry.register("RSI", RSI)
feature_registry.register("ROC", ROC)
feature_registry.register("STOCH", Stochastic)
