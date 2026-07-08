"""
TREDO — Agent Framework Tests
Tests Agent Lifecycle, Protocol, Registry, BaseAgent, and Manager.
Plus: Integration test with EchoAgent and LoggerAgent.
"""

import asyncio
import pytest

from backend.agents.base import BaseAgent
from backend.agents.lifecycle import AgentState, Lifecycle, InvalidTransition
from backend.agents.manager import AgentManager
from backend.agents.protocol import (
    AgentFailed,
    AgentHealthRequest,
    AgentHealthResponse,
    AgentMessage,
    AgentPaused,
    AgentResumed,
    AgentStarted,
    AgentStopped,
)
from backend.agents.registry import AgentRegistry, AgentRegistryError
from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage, MemoryEvent, SystemEvent, HealthCheckRequest, HealthCheckResponse


# ══════════════════════════════════════════════════════════
# Lifecycle Tests
# ══════════════════════════════════════════════════════════


class TestLifecycle:
    def test_initial_state(self):
        lc = Lifecycle()
        assert lc.state == AgentState.CREATED
        assert lc.is_running is False
        assert lc.is_active is False
        assert lc.error is None
        assert lc.get_history() == ["created"]

    def test_valid_transitions(self):
        lc = Lifecycle()
        lc.transition(AgentState.INITIALIZED)
        assert lc.state == AgentState.INITIALIZED
        
        lc.transition(AgentState.RUNNING)
        assert lc.state == AgentState.RUNNING
        assert lc.is_running is True
        assert lc.is_active is True
        
        lc.transition(AgentState.PAUSED)
        assert lc.state == AgentState.PAUSED
        assert lc.is_running is False
        assert lc.is_active is True
        
        lc.transition(AgentState.RUNNING)
        assert lc.state == AgentState.RUNNING
        
        lc.transition(AgentState.STOPPED)
        assert lc.state == AgentState.STOPPED
        assert lc.is_active is False

    def test_invalid_transition(self):
        lc = Lifecycle()
        with pytest.raises(InvalidTransition, match="Cannot transition"):
            lc.transition(AgentState.RUNNING)

    def test_failed_state_records_error(self):
        lc = Lifecycle()
        lc.transition(AgentState.INITIALIZED)
        lc.transition(AgentState.RUNNING)
        lc.transition(AgentState.FAILED, error="Connection timeout")
        
        assert lc.state == AgentState.FAILED
        assert lc.error == "Connection timeout"

    def test_restart_clears_error(self):
        lc = Lifecycle()
        lc.transition(AgentState.INITIALIZED)
        lc.transition(AgentState.RUNNING)
        lc.transition(AgentState.FAILED, error="boom")
        lc.transition(AgentState.INITIALIZED)
        
        assert lc.state == AgentState.INITIALIZED
        assert lc.error is None


# ══════════════════════════════════════════════════════════
# Registry Tests
# ══════════════════════════════════════════════════════════


class DummyAgent(BaseAgent):
    """Simple agent for registry/manager testing."""
    async def setup(self) -> None:
        pass
    async def handle(self, message: BaseMessage) -> None:
        pass


class TestRegistry:
    def test_register_and_get(self):
        reg = AgentRegistry()
        agent = DummyAgent("a1", EventBus())
        reg.register(agent)
        
        assert reg.has("a1") is True
        assert reg.get("a1") == agent
        assert len(reg.list_agents()) == 1

    def test_register_duplicate(self):
        reg = AgentRegistry()
        agent = DummyAgent("a1", EventBus())
        reg.register(agent)
        
        with pytest.raises(AgentRegistryError, match="already registered"):
            reg.register(agent)

    def test_get_not_found(self):
        reg = AgentRegistry()
        with pytest.raises(AgentRegistryError, match="not found"):
            reg.get("a1")

    def test_remove(self):
        reg = AgentRegistry()
        agent = DummyAgent("a1", EventBus())
        reg.register(agent)
        reg.remove("a1")
        assert reg.has("a1") is False

    def test_clear(self):
        reg = AgentRegistry()
        reg.register(DummyAgent("a1", EventBus()))
        reg.register(DummyAgent("a2", EventBus()))
        reg.clear()
        assert len(reg.list_agents()) == 0


# ══════════════════════════════════════════════════════════
# BaseAgent Tests
# ══════════════════════════════════════════════════════════


class FailingAgent(BaseAgent):
    async def setup(self) -> None:
        raise RuntimeError("setup failed")
    async def handle(self, message: BaseMessage) -> None:
        pass


class TestBaseAgent:
    @pytest.mark.asyncio
    async def test_start_success(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        
        events = []
        async def on_start(msg: AgentStarted):
            events.append(msg)
        bus.subscribe(AgentStarted, on_start)
        
        await agent.start()
        
        assert agent.is_running is True
        assert len(events) == 1
        assert events[0].agent_id == "a1"

    @pytest.mark.asyncio
    async def test_start_failure(self):
        bus = EventBus()
        agent = FailingAgent("bad1", bus)
        
        events = []
        async def on_fail(msg: AgentFailed):
            events.append(msg)
        bus.subscribe(AgentFailed, on_fail)
        
        with pytest.raises(RuntimeError, match="setup failed"):
            await agent.start()
            
        assert agent.state == AgentState.FAILED
        assert len(events) == 1
        assert events[0].error == "setup failed"

    @pytest.mark.asyncio
    async def test_stop(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        await agent.start()
        
        events = []
        async def on_stop(msg: AgentStopped):
            events.append(msg)
        bus.subscribe(AgentStopped, on_stop)
        
        await agent.stop(reason="test")
        
        assert agent.is_running is False
        assert agent.state == AgentState.STOPPED
        assert len(events) == 1
        assert events[0].reason == "test"

    @pytest.mark.asyncio
    async def test_stop_inactive_ignored(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        # Never started
        await agent.stop()
        assert agent.state == AgentState.CREATED

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        await agent.start()
        
        await agent.pause()
        assert agent.state == AgentState.PAUSED
        
        await agent.resume()
        assert agent.state == AgentState.RUNNING

    @pytest.mark.asyncio
    async def test_subscription(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        
        received = []
        # Override handle for this test
        async def handle(msg):
            received.append(msg)
        agent.handle = handle
        
        agent.subscribe_to(SystemEvent)
        await agent.start()
        
        await bus.publish(SystemEvent(message="test"))
        assert len(received) == 1
        
        await agent.stop()
        await bus.publish(SystemEvent(message="test2"))
        assert len(received) == 1  # Unsubscribed on stop

    @pytest.mark.asyncio
    async def test_send_and_publish(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        
        msgs = []
        async def on_msg(m):
            msgs.append(m)
        bus.subscribe(AgentMessage, on_msg)
        
        await agent.send("hello", {"k": "v"})
        assert len(msgs) == 1
        assert msgs[0].content == "hello"
        assert msgs[0].data["k"] == "v"

    def test_health(self):
        bus = EventBus()
        agent = DummyAgent("a1", bus)
        
        health = agent.health()
        assert health["agent_id"] == "a1"
        assert health["state"] == "created"
        assert health["healthy"] is False


# ══════════════════════════════════════════════════════════
# Manager Tests
# ══════════════════════════════════════════════════════════


class TestManager:
    @pytest.mark.asyncio
    async def test_register_and_start(self):
        bus = EventBus()
        manager = AgentManager(bus)
        agent = DummyAgent("a1", bus)
        
        await manager.register_and_start(agent)
        
        assert manager.get_agent("a1") == agent
        assert agent.is_running is True

    @pytest.mark.asyncio
    async def test_stop_agent(self):
        bus = EventBus()
        manager = AgentManager(bus)
        agent = DummyAgent("a1", bus)
        
        await manager.register_and_start(agent)
        await manager.stop_agent("a1")
        
        assert agent.state == AgentState.STOPPED
        with pytest.raises(AgentRegistryError):
            manager.get_agent("a1")

    @pytest.mark.asyncio
    async def test_stop_all(self):
        bus = EventBus()
        manager = AgentManager(bus)
        a1 = DummyAgent("a1", bus)
        a2 = DummyAgent("a2", bus)
        
        await manager.register_and_start(a1)
        await manager.register_and_start(a2)
        
        await manager.stop_all()
        
        assert a1.state == AgentState.STOPPED
        assert a2.state == AgentState.STOPPED
        assert len(manager.list_agents()) == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        bus = EventBus()
        manager = AgentManager(bus)
        
        msgs = []
        async def on_msg(m):
            msgs.append(m)
        bus.subscribe(AgentMessage, on_msg)
        
        await manager.broadcast("alert")
        
        assert len(msgs) == 1
        assert msgs[0].from_agent == "manager"
        assert msgs[0].content == "alert"

    @pytest.mark.asyncio
    async def test_health_checks(self):
        bus = EventBus()
        manager = AgentManager(bus)
        
        responses = []
        async def on_resp(m):
            responses.append(m)
        bus.subscribe(HealthCheckResponse, on_resp)
        bus.subscribe(AgentHealthResponse, on_resp)
        
        await bus.publish(HealthCheckRequest())
        await bus.publish(AgentHealthRequest())
        
        # Should get 1 system health response, 0 agent responses (none registered)
        assert len(responses) == 1
        assert responses[0].service == "agent_manager"


# ══════════════════════════════════════════════════════════
# Integration Test — Dummy Agents
# ══════════════════════════════════════════════════════════


class EchoAgent(BaseAgent):
    """Subscribes to SystemEvent, replies with AgentMessage."""
    async def setup(self) -> None:
        self.subscribe_to(SystemEvent)

    async def handle(self, message: BaseMessage) -> None:
        if isinstance(message, SystemEvent):
            await self.send(f"Echoing: {message.message}")


class LoggerAgent(BaseAgent):
    """Subscribes to AgentMessage, publishes MemoryEvent."""
    async def setup(self) -> None:
        self.subscribe_to(AgentMessage)
        
    async def handle(self, message: BaseMessage) -> None:
        if isinstance(message, AgentMessage):
            await self.publish(MemoryEvent(
                memory_type="event",
                record_id="msg123",
                summary=message.content,
            ))


class TestIntegration:
    @pytest.mark.asyncio
    async def test_echo_and_logger_flow(self):
        """
        Flow:
        1. Publish SystemEvent
        2. EchoAgent receives SystemEvent, publishes AgentMessage
        3. LoggerAgent receives AgentMessage, publishes MemoryEvent
        """
        bus = EventBus()
        manager = AgentManager(bus)
        
        echo = EchoAgent("echo_1", bus)
        logger_agent = LoggerAgent("logger_1", bus)
        
        await manager.register_and_start(echo)
        await manager.register_and_start(logger_agent)
        
        # Track memory events
        memories = []
        async def on_memory(msg: MemoryEvent):
            memories.append(msg)
        bus.subscribe(MemoryEvent, on_memory)
        
        # Publish initial event
        await bus.publish(SystemEvent(message="Hello world"))
        
        # Verify flow
        assert len(memories) == 1
        assert memories[0].summary == "Echoing: Hello world"
        
        # Verify history
        history = bus.get_history()
        types = [type(m).__name__ for m in history]
        
        # Should contain: SystemEvent, AgentMessage, MemoryEvent, plus AgentStarted
        assert "SystemEvent" in types
        assert "AgentMessage" in types
        assert "MemoryEvent" in types
        assert "AgentStarted" in types
        
        await manager.stop_all()
