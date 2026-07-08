"""
TREDO — Intelligence Pipeline (Feature Engine)
Orchestrates listening to CandleEvents, updating mathematical features,
writing to the FeatureStore, and publishing FeaturesUpdated events.
"""

import logging
from typing import Type

from backend.core.event_bus import EventBus
from backend.intelligence.feature_store import FeatureStore
from backend.intelligence.models import BaseFeature, FeaturesUpdated, FeatureMetadata
from backend.intelligence.registry import feature_registry
from backend.market.events import CandleEvent

logger = logging.getLogger(__name__)


class IntelligencePipeline:
    """
    Subscribes to Market Scanner (CandleEvent).
    Updates all instantiated features.
    Pushes state to Feature Store.
    Publishes FeaturesUpdated for Strategy Engine.
    """
    def __init__(self, bus: EventBus, store: FeatureStore):
        self._bus = bus
        self._store = store
        # symbol -> list of feature instances
        self._features: dict[str, list[BaseFeature]] = {}
        self._running = False

    def add_feature(self, symbol: str, feature_name: str, window: int | None = None) -> None:
        """
        Dynamically load a feature by name from the registry, configure its window, 
        and attach it to a symbol.
        """
        feature_class = feature_registry.get_class(feature_name)
        if not feature_class:
            logger.error("Feature %s not found in registry.", feature_name)
            return

        # Clone default metadata and override window if provided
        meta = feature_class.DEFAULT_METADATA
        new_meta = FeatureMetadata(
            name=meta.name,
            version=meta.version,
            window=window if window is not None else meta.window,
            category=meta.category,
            dependencies=meta.dependencies
        )
        
        instance = feature_class(symbol, new_meta)
        
        if symbol not in self._features:
            self._features[symbol] = []
        self._features[symbol].append(instance)
        logger.info("Added feature %s to %s", instance.id, symbol)

    async def start(self) -> None:
        """Subscribe to Event Bus."""
        if self._running:
            return
        self._bus.subscribe(CandleEvent, self._handle_candle)
        self._running = True
        logger.info("Intelligence Pipeline started")

    async def stop(self) -> None:
        """Unsubscribe from Event Bus."""
        if not self._running:
            return
        self._bus.unsubscribe(CandleEvent, self._handle_candle)
        self._running = False
        logger.info("Intelligence Pipeline stopped")

    async def _handle_candle(self, event: CandleEvent) -> None:
        """
        Callback triggered by the Event Bus when a CandleEvent arrives.
        Only trigger on closed candles (or all, depending on configuration).
        Normally, features only compute on closed candles.
        """
        if not event.is_closed:
            # Most indicators are calculated on closed candles to avoid repainting
            return
            
        symbol = event.symbol
        instances = self._features.get(symbol, [])
        
        if not instances:
            return

        # Store raw price for strategies that need it (like Bollinger Reversion)
        self._store.update(symbol, "RAW.CLOSE", {
            "name": "CLOSE",
            "value": event.close_price,
            "ready": True,
            "timestamp": event.timestamp
        })

        updated_values = {}
        
        for feature in instances:
            # 1. Update the math
            feature_out = feature.update(event)
            
            # 2. Write to state manager (Feature Store)
            self._store.update(symbol, feature.id, feature_out)
            
            # Add to local payload if ready
            if feature_out["ready"]:
                updated_values[feature.id] = feature_out["value"]

        # 3. Publish to Strategy Engine if we updated anything
        if updated_values:
            out_event = FeaturesUpdated(
                symbol=symbol,
                timestamp=event.timestamp,
                features=updated_values
            )
            await self._bus.publish(out_event)
