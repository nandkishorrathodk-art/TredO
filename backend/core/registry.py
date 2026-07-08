"""
TREDO — Service Registry
Central dependency container. All services register here.
No module instantiates another module directly.

Usage:
    registry = Registry()
    registry.register("risk", risk_engine)
    registry.register("memory", journal)
    registry.register("exchange", connector)

    # Anywhere in the app:
    risk = registry.get("risk")
    memory = registry.get("memory")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Raised when a registry operation fails."""


class Registry:
    """
    Service registry / dependency container.
    All core services register here at startup.
    Modules get dependencies from here, never by importing each other.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """
        Register a service by name.
        Raises if a service with that name already exists.
        """
        if name in self._services:
            raise RegistryError(
                f"Service '{name}' already registered. "
                f"Use replace() to update."
            )
        self._services[name] = service
        logger.info("Registered service: %s (%s)", name, type(service).__name__)

    def replace(self, name: str, service: Any) -> None:
        """Replace an existing service (for testing / hot reload)."""
        old = self._services.get(name)
        self._services[name] = service
        logger.info(
            "Replaced service: %s (%s → %s)",
            name,
            type(old).__name__ if old else "None",
            type(service).__name__,
        )

    def get(self, name: str) -> Any:
        """
        Get a registered service by name.
        Raises if the service is not found.
        """
        if name not in self._services:
            available = ", ".join(sorted(self._services.keys())) or "(none)"
            raise RegistryError(
                f"Service '{name}' not found. Available: {available}"
            )
        return self._services[name]

    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services

    def remove(self, name: str) -> None:
        """Remove a service from the registry."""
        if name in self._services:
            del self._services[name]
            logger.info("Removed service: %s", name)

    def list_services(self) -> list[str]:
        """List all registered service names."""
        return sorted(self._services.keys())

    def clear(self) -> None:
        """Remove all services. For testing only."""
        self._services.clear()

    def get_status(self) -> dict[str, str]:
        """Get registry status — service names and their types."""
        return {
            name: type(svc).__name__
            for name, svc in sorted(self._services.items())
        }
