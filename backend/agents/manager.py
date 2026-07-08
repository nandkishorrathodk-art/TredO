"""
TREDO — Agent Manager
High-level manager for agents. Orchestrates start, stop, broadcast.
Subscribes to HealthCheckRequest to report all agent states.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.protocol import AgentHealthRequest, AgentHealthResponse, AgentMessage
from backend.agents.registry import AgentRegistry
from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage, HealthCheckRequest, HealthCheckResponse

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages the lifecycle and orchestration of all agents.
    Uses Event Bus for system-wide communication.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._registry = AgentRegistry()
        self._setup_bus_handlers()

    def _setup_bus_handlers(self) -> None:
        """Subscribe to system health and agent health requests."""
        async def on_health_request(msg: HealthCheckRequest) -> None:
            await self._bus.publish(HealthCheckResponse(
                service="agent_manager",
                healthy=True,
                details={"agent_count": len(self._registry.list_agents())},
                source="agent_manager",
            ))

        async def on_agent_health_request(msg: AgentHealthRequest) -> None:
            agents_to_check = []
            if msg.target_agent:
                if self._registry.has(msg.target_agent):
                    agents_to_check.append(self._registry.get(msg.target_agent))
            else:
                agents_to_check = self._registry.list_agents()
            
            for agent in agents_to_check:
                health = agent.health()
                await self._bus.publish(AgentHealthResponse(
                    agent_id=agent.id,
                    agent_type=agent.type_name,
                    state=health["state"],
                    healthy=health["healthy"],
                    details=health,
                    source="agent_manager",
                ))

        self._bus.subscribe(HealthCheckRequest, on_health_request)
        self._bus.subscribe(AgentHealthRequest, on_agent_health_request)

    async def register_and_start(self, agent: BaseAgent) -> None:
        """Register an agent and start it."""
        self._registry.register(agent)
        try:
            await agent.start()
        except Exception as e:
            logger.error("Failed to start agent %s: %s", agent.id, e)
            self._registry.remove(agent.id)
            raise

    async def stop_agent(self, agent_id: str, reason: str = "manager_request") -> None:
        """Stop a specific agent."""
        if self._registry.has(agent_id):
            agent = self._registry.get(agent_id)
            await agent.stop(reason=reason)
            self._registry.remove(agent_id)

    async def stop_all(self, reason: str = "shutdown") -> None:
        """Stop all running agents."""
        agents = self._registry.list_agents()
        if not agents:
            return
        
        await asyncio.gather(
            *(agent.stop(reason=reason) for agent in agents),
            return_exceptions=True
        )
        self._registry.clear()
        logger.info("Stopped all agents")

    async def pause_agent(self, agent_id: str) -> None:
        """Pause a specific agent."""
        if self._registry.has(agent_id):
            agent = self._registry.get(agent_id)
            await agent.pause()

    async def resume_agent(self, agent_id: str) -> None:
        """Resume a specific agent."""
        if self._registry.has(agent_id):
            agent = self._registry.get(agent_id)
            await agent.resume()

    def get_agent(self, agent_id: str) -> BaseAgent:
        """Get an agent by ID."""
        return self._registry.get(agent_id)
    
    def list_agents(self) -> list[BaseAgent]:
        """List all agents."""
        return self._registry.list_agents()

    async def broadcast(self, content: str, data: dict[str, Any] | None = None) -> None:
        """Send a broadcast AgentMessage to all agents."""
        await self._bus.publish(AgentMessage(
            from_agent="manager",
            to_agent="",
            content=content,
            data=data or {},
            source="manager",
        ))
