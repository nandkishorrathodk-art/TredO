"""
TREDO — Market Intelligence Module
V2.2 - Feature Engine and Strategy integration.
"""

from backend.intelligence.models import BaseFeature, FeatureMetadata, FeaturesUpdated
from backend.intelligence.feature_store import FeatureStore
from backend.intelligence.pipeline import IntelligencePipeline
from backend.intelligence.registry import feature_registry

# Import to ensure registry gets populated
import backend.intelligence.features.trend
import backend.intelligence.features.momentum
import backend.intelligence.features.volatility
import backend.intelligence.features.volume

__all__ = [
    "BaseFeature",
    "FeatureMetadata",
    "FeaturesUpdated",
    "FeatureStore",
    "IntelligencePipeline",
    "feature_registry",
]
