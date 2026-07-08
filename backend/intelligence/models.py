"""
TREDO — Market Intelligence Models
Defines base feature classes and intelligence events.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.core.messages import BaseMessage
from backend.market.events import CandleEvent


@dataclass
class FeaturesUpdated(BaseMessage):
    """
    Published by Feature Engine when new indicators are computed.
    Strategy Engine consumes this.
    """
    symbol: str = ""
    timestamp: int = 0
    features: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureMetadata:
    """Metadata for feature versioning and tracking."""
    name: str
    version: int
    window: int
    category: str
    dependencies: list[str] = field(default_factory=list)


class BaseFeature(ABC):
    """
    Abstract base class for all technical indicators and features.
    Maintains its own state/rolling window if necessary.
    """
    
    def __init__(self, symbol: str, metadata: FeatureMetadata):
        self.symbol = symbol
        self.metadata = metadata
        self._is_ready = False
        self._current_value: Any = None
        self._current_timestamp: int = 0

    @abstractmethod
    def update(self, event: CandleEvent) -> dict[str, Any]:
        """
        Ingests a new CandleEvent, updates internal state,
        and returns the newly computed structured feature value.
        """
        pass

    @property
    def is_ready(self) -> bool:
        """True if the feature has enough historical data to be valid."""
        return self._is_ready

    @property
    def id(self) -> str:
        """Unique ID for this feature (e.g. VOLATILITY.ATR.14)."""
        if self.metadata.window > 0:
            return f"{self.metadata.category}.{self.metadata.name}.{self.metadata.window}".upper()
        return f"{self.metadata.category}.{self.metadata.name}".upper()

    @property
    def value(self) -> dict[str, Any]:
        """The most recently computed structured value."""
        return {
            "id": self.id,
            "name": self.metadata.name,
            "value": self._current_value,
            "ready": self._is_ready,
            "timestamp": self._current_timestamp,
            "version": self.metadata.version,
        }
