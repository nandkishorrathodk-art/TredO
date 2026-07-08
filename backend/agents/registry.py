"""
TREDO — Agent Registry
A simple container to hold running agents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistryError(Exception):
    """Raised when an agent registry operation fails."""


class AgentRegistry:
    """
    Holds references to instantiated agents.
    Does not manage lifecycle, just storage.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its ID."""
        if agent.id in self._agents:
            raise AgentRegistryError(f"Agent '{agent.id}' already registered.")
        self._agents[agent.id] = agent
        logger.debug("Agent registered: %s", agent.id)

    def get(self, agent_id: str) -> BaseAgent:
        """Get an agent by ID."""
        if agent_id not in self._agents:
            raise AgentRegistryError(f"Agent '{agent_id}' not found.")
        return self._agents[agent_id]

    def has(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        return agent_id in self._agents

    def remove(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.debug("Agent removed: %s", agent_id)

    def list_agents(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def clear(self) -> None:
        """Remove all agents."""
        self._agents.clear()
