"""
TREDO — Feature Store
In-memory state manager for all market intelligence features.
"""

from typing import Any

class FeatureStore:
    """
    Centralized store holding the latest computed values for all features across all symbols.
    Structure: {symbol: {feature_id: {feature_data}}}
    """
    def __init__(self):
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def update(self, symbol: str, feature_id: str, value: dict[str, Any]) -> None:
        """Update a specific feature's latest value for a symbol."""
        if symbol not in self._store:
            self._store[symbol] = {}
        self._store[symbol][feature_id] = value

    def get(self, symbol: str, feature_id: str) -> dict[str, Any] | None:
        """Retrieve the latest value of a specific feature for a symbol."""
        return self._store.get(symbol, {}).get(feature_id)

    def get_all(self, symbol: str) -> dict[str, dict[str, Any]]:
        """Retrieve all features and their latest values for a symbol."""
        return self._store.get(symbol, {})

    def clear(self) -> None:
        """Clear the entire store (useful for testing or hard resets)."""
        self._store.clear()
