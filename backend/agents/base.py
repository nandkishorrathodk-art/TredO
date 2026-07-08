"""
TREDO — Base Agent
Abstract base class for all agents in the system.
Every agent has: start, stop, pause, resume, handle.
Every agent communicates ONLY through the Event Bus.

This is infrastructure. No intelligence here.
Intelligence comes from subclasses in V2+.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from backend.agents.lifecycle import AgentState, Lifecycle
from backend.agents.protocol import (
    AgentFailed,
    AgentMessage,
    AgentPaused,
    AgentResumed,
    AgentStarted,
    AgentStopped,
)
from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all TREDO agents.

    Subclasses must implement:
    - setup()   → one-time initialization
    - handle()  → process incoming messages
    - cleanup() → teardown resources

    Agents never call each other. They publish/subscribe via Event Bus.
    """

    def __init__(self, agent_id: str, event_bus: EventBus) -> None:
        self._id = agent_id
        self._bus = event_bus
        self._lifecycle = Lifecycle()
        self._subscriptions: list[tuple[type, Any]] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> AgentState:
        return self._lifecycle.state

    @property
    def is_running(self) -> bool:
        return self._lifecycle.is_running

    @property
    def type_name(self) -> str:
        return self.__class__.__name__

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the agent."""
        try:
            self._lifecycle.transition(AgentState.INITIALIZED)
            await self.setup()
            self._lifecycle.transition(AgentState.RUNNING)
            await self._bus.publish(AgentStarted(
                agent_id=self._id, agent_type=self.type_name,
                source=self._id,
            ))
            logger.info("Agent started: %s (%s)", self._id, self.type_name)
        except Exception as e:
            self._lifecycle.transition(AgentState.FAILED, error=str(e))
            await self._bus.publish(AgentFailed(
                agent_id=self._id, agent_type=self.type_name,
                error=str(e), source=self._id,
            ))
            raise

    async def stop(self, reason: str = "shutdown") -> None:
        """Stop the agent and cleanup resources."""
        if not self._lifecycle.is_active:
            return
        try:
            if self.state == AgentState.PAUSED:
                self._lifecycle.transition(AgentState.STOPPED)
            else:
                self._lifecycle.transition(AgentState.STOPPED)
            self._unsubscribe_all()
            await self.cleanup()
            await self._bus.publish(AgentStopped(
                agent_id=self._id, agent_type=self.type_name,
                reason=reason, source=self._id,
            ))
            logger.info("Agent stopped: %s (reason: %s)", self._id, reason)
        except Exception as e:
            logger.error("Error stopping agent %s: %s", self._id, e)

    async def pause(self) -> None:
        """Pause the agent. It stops processing but stays alive."""
        self._lifecycle.transition(AgentState.PAUSED)
        await self._bus.publish(AgentPaused(
            agent_id=self._id, agent_type=self.type_name,
            source=self._id,
        ))
        logger.info("Agent paused: %s", self._id)

    async def resume(self) -> None:
        """Resume a paused agent."""
        self._lifecycle.transition(AgentState.RUNNING)
        await self._bus.publish(AgentResumed(
            agent_id=self._id, agent_type=self.type_name,
            source=self._id,
        ))
        logger.info("Agent resumed: %s", self._id)

    # ── Message Handling ─────────────────────────────────────

    def subscribe_to(self, message_type: type) -> None:
        """Subscribe this agent to a message type on the Event Bus."""
        async def _wrapper(msg: BaseMessage) -> None:
            if self.is_running:
                await self.handle(msg)

        self._bus.subscribe(message_type, _wrapper)
        self._subscriptions.append((message_type, _wrapper))

    def _unsubscribe_all(self) -> None:
        """Remove all subscriptions."""
        for msg_type, handler in self._subscriptions:
            self._bus.unsubscribe(msg_type, handler)
        self._subscriptions.clear()

    async def publish(self, message: BaseMessage) -> None:
        """Publish a message to the Event Bus."""
        await self._bus.publish(message)

    async def send(self, content: str, data: dict[str, Any] | None = None) -> None:
        """Send an AgentMessage through the Event Bus."""
        await self._bus.publish(AgentMessage(
            from_agent=self._id,
            content=content,
            data=data or {},
            source=self._id,
        ))

    # ── Health ───────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Return health status of this agent."""
        return {
            "agent_id": self._id,
            "type": self.type_name,
            "state": self.state.value,
            "healthy": self.is_running,
            "error": self._lifecycle.error,
        }

    # ── Abstract Methods (subclasses implement these) ────────

    @abstractmethod
    async def setup(self) -> None:
        """One-time initialization. Subscribe to message types here."""

    @abstractmethod
    async def handle(self, message: BaseMessage) -> None:
        """Process an incoming message from the Event Bus."""

    async def cleanup(self) -> None:
        """Teardown resources. Override if needed."""
        pass
