"""
TREDO — Feature Registry
Manages dynamically loading and instantiating features.
"""

from typing import Type
from backend.intelligence.models import BaseFeature


class FeatureRegistry:
    """
    Holds references to all available Feature classes so they 
    can be instantiated by the pipeline dynamically.
    """
    def __init__(self):
        # name -> feature class (e.g. "SMA" -> SMA class)
        self._registry: dict[str, Type[BaseFeature]] = {}

    def register(self, name: str, feature_class: Type[BaseFeature]) -> None:
        """Register a feature class by name."""
        self._registry[name.upper()] = feature_class

    def get_class(self, name: str) -> Type[BaseFeature] | None:
        """Retrieve a feature class by name."""
        return self._registry.get(name.upper())

    def get_by_category(self, category: str) -> list[Type[BaseFeature]]:
        """Retrieve all feature classes that belong to a specific category."""
        return [
            cls for name, cls in self._registry.items()
            if hasattr(cls, "DEFAULT_METADATA") and cls.DEFAULT_METADATA.category.lower() == category.lower()
        ]

    def list_features(self) -> list[str]:
        """List all registered feature names."""
        return list(self._registry.keys())

# Global registry instance for features
feature_registry = FeatureRegistry()
