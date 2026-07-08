"""
TREDO — Agent Protocol
Message types specific to agent communication.
Agents never call each other — they publish/subscribe through Event Bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.messages import BaseMessage


@dataclass
class AgentStarted(BaseMessage):
    """An agent has started."""
    agent_id: str = ""
    agent_type: str = ""


@dataclass
class AgentStopped(BaseMessage):
    """An agent has stopped."""
    agent_id: str = ""
    agent_type: str = ""
    reason: str = ""


@dataclass
class AgentFailed(BaseMessage):
    """An agent encountered an error."""
    agent_id: str = ""
    agent_type: str = ""
    error: str = ""


@dataclass
class AgentPaused(BaseMessage):
    """An agent has been paused."""
    agent_id: str = ""
    agent_type: str = ""


@dataclass
class AgentResumed(BaseMessage):
    """An agent has resumed from pause."""
    agent_id: str = ""
    agent_type: str = ""


@dataclass
class AgentMessage(BaseMessage):
    """A generic message sent between agents via Event Bus."""
    from_agent: str = ""
    to_agent: str = ""       # empty = broadcast
    content: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentHealthRequest(BaseMessage):
    """Request health status from a specific agent or all agents."""
    target_agent: str = ""   # empty = all agents


@dataclass
class AgentHealthResponse(BaseMessage):
    """Health status response from an agent."""
    agent_id: str = ""
    agent_type: str = ""
    state: str = ""
    healthy: bool = True
    details: dict[str, Any] = field(default_factory=dict)
