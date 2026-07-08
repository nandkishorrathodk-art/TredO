"""
TREDO — Core Kernel Tests
Tests Event Bus, Registry, Scheduler, and Messages.
Plus: integration test for full signal → trade → log flow.
"""

import asyncio
import pytest

from backend.core.event_bus import EventBus
from backend.core.registry import Registry, RegistryError
from backend.core.scheduler import Scheduler
from backend.core.messages import (
    BaseMessage,
    SignalGenerated,
    RiskCheckRequest,
    RiskApproved,
    RiskRejected,
    TradeRequested,
    TradeExecuted,
    TradeClosed,
    MemoryEvent,
    SystemEvent,
    KillSwitchActivated,
    HealthCheckRequest,
    HealthCheckResponse,
)


# ══════════════════════════════════════════════════════════
# Message Tests
# ══════════════════════════════════════════════════════════


class TestMessages:
    def test_base_message_has_timestamp(self):
        msg = BaseMessage()
        assert msg.timestamp is not None
        assert msg.source == "system"
        assert msg.type_name == "BaseMessage"

    def test_signal_generated(self):
        sig = SignalGenerated(
            symbol="BTC/USDT", direction="BUY",
            confidence=0.8, reason="RSI oversold",
            source="scanner",
        )
        assert sig.symbol == "BTC/USDT"
        assert sig.direction == "BUY"
        assert sig.confidence == 0.8
        assert sig.reason == "RSI oversold"
        assert sig.type_name == "SignalGenerated"

    def test_risk_check_request(self):
        req = RiskCheckRequest(
            symbol="BTC/USDT", side="buy",
            amount=0.01, price=71000.0, reason="test",
        )
        assert req.amount == 0.01

    def test_risk_approved(self):
        msg = RiskApproved(symbol="BTC/USDT", approved_amount=0.01, risk_pct=0.71)
        assert msg.approved_amount == 0.01

    def test_risk_rejected(self):
        msg = RiskRejected(symbol="BTC/USDT", reasons=["Too risky"])
        assert len(msg.reasons) == 1

    def test_trade_requested(self):
        msg = TradeRequested(symbol="BTC/USDT", side="buy", amount=0.01, price=71000.0)
        assert msg.order_type == "market"

    def test_trade_executed(self):
        msg = TradeExecuted(trade_id="t123", symbol="BTC/USDT", amount=0.01, price=71000.0)
        assert msg.trade_id == "t123"

    def test_trade_closed(self):
        msg = TradeClosed(trade_id="t123", exit_price=72000.0, pnl=10.0)
        assert msg.pnl == 10.0

    def test_memory_event(self):
        msg = MemoryEvent(memory_type="trade", record_id="t123", summary="logged")
        assert msg.memory_type == "trade"

    def test_system_event(self):
        msg = SystemEvent(event_type="exchange", message="connected", severity="info")
        assert msg.severity == "info"

    def test_kill_switch(self):
        msg = KillSwitchActivated(reason="emergency")
        assert msg.reason == "emergency"

    def test_health_check(self):
        req = HealthCheckRequest()
        resp = HealthCheckResponse(service="exchange", healthy=True)
        assert resp.service == "exchange"


# ══════════════════════════════════════════════════════════
# Event Bus Tests
# ══════════════════════════════════════════════════════════


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        async def handler(msg: SignalGenerated):
            received.append(msg)

        bus.subscribe(SignalGenerated, handler)
        await bus.publish(SignalGenerated(symbol="BTC/USDT", direction="BUY"))

        assert len(received) == 1
        assert received[0].symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = EventBus()
        results = {"a": [], "b": []}

        async def handler_a(msg):
            results["a"].append(msg)

        async def handler_b(msg):
            results["b"].append(msg)

        bus.subscribe(SignalGenerated, handler_a)
        bus.subscribe(SignalGenerated, handler_b)
        count = await bus.publish(SignalGenerated(symbol="ETH/USDT"))

        assert count == 2
        assert len(results["a"]) == 1
        assert len(results["b"]) == 1

    @pytest.mark.asyncio
    async def test_no_subscribers(self):
        bus = EventBus()
        count = await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        assert count == 0

    @pytest.mark.asyncio
    async def test_different_message_types(self):
        bus = EventBus()
        signals = []
        trades = []

        async def on_signal(msg):
            signals.append(msg)

        async def on_trade(msg):
            trades.append(msg)

        bus.subscribe(SignalGenerated, on_signal)
        bus.subscribe(TradeExecuted, on_trade)

        await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        await bus.publish(TradeExecuted(trade_id="t1"))

        assert len(signals) == 1
        assert len(trades) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe(SignalGenerated, handler)
        await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        assert len(received) == 1

        bus.unsubscribe(SignalGenerated, handler)
        await bus.publish(SignalGenerated(symbol="ETH/USDT"))
        assert len(received) == 1  # still 1, not 2

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_break_others(self):
        bus = EventBus()
        results = []

        async def bad_handler(msg):
            raise ValueError("boom")

        async def good_handler(msg):
            results.append(msg)

        bus.subscribe(SignalGenerated, bad_handler)
        bus.subscribe(SignalGenerated, good_handler)

        count = await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        assert count == 1  # only good handler succeeded
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_duplicate_subscribe_ignored(self):
        bus = EventBus()

        async def handler(msg):
            pass

        bus.subscribe(SignalGenerated, handler)
        bus.subscribe(SignalGenerated, handler)

        assert bus.subscriber_count(SignalGenerated) == 1

    @pytest.mark.asyncio
    async def test_history(self):
        bus = EventBus()
        await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        await bus.publish(TradeExecuted(trade_id="t1"))
        await bus.publish(SignalGenerated(symbol="ETH/USDT"))

        all_history = bus.get_history()
        assert len(all_history) == 3

        signal_history = bus.get_history(SignalGenerated)
        assert len(signal_history) == 2

    @pytest.mark.asyncio
    async def test_clear_history(self):
        bus = EventBus()
        await bus.publish(SignalGenerated(symbol="BTC/USDT"))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    @pytest.mark.asyncio
    async def test_clear_all(self):
        bus = EventBus()

        async def handler(msg):
            pass

        bus.subscribe(SignalGenerated, handler)
        await bus.publish(SignalGenerated())
        bus.clear_all()

        assert bus.subscriber_count(SignalGenerated) == 0
        assert len(bus.get_history()) == 0

    @pytest.mark.asyncio
    async def test_stats(self):
        bus = EventBus()

        async def handler(msg):
            pass

        bus.subscribe(SignalGenerated, handler)
        bus.subscribe(TradeExecuted, handler)
        await bus.publish(SignalGenerated())

        stats = bus.get_stats()
        assert stats["total_subscriptions"] == 2
        assert stats["message_types"] == 2
        assert stats["history_size"] == 1


# ══════════════════════════════════════════════════════════
# Registry Tests
# ══════════════════════════════════════════════════════════


class TestRegistry:
    def test_register_and_get(self):
        reg = Registry()
        reg.register("risk", {"type": "risk_engine"})
        assert reg.get("risk") == {"type": "risk_engine"}

    def test_register_duplicate_raises(self):
        reg = Registry()
        reg.register("risk", "engine1")
        with pytest.raises(RegistryError, match="already registered"):
            reg.register("risk", "engine2")

    def test_get_not_found_raises(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="not found"):
            reg.get("nonexistent")

    def test_has_service(self):
        reg = Registry()
        assert reg.has("risk") is False
        reg.register("risk", "engine")
        assert reg.has("risk") is True

    def test_replace_service(self):
        reg = Registry()
        reg.register("risk", "old_engine")
        reg.replace("risk", "new_engine")
        assert reg.get("risk") == "new_engine"

    def test_remove_service(self):
        reg = Registry()
        reg.register("risk", "engine")
        reg.remove("risk")
        assert reg.has("risk") is False

    def test_list_services(self):
        reg = Registry()
        reg.register("exchange", "ex")
        reg.register("risk", "rk")
        reg.register("memory", "mem")
        assert reg.list_services() == ["exchange", "memory", "risk"]

    def test_clear(self):
        reg = Registry()
        reg.register("a", 1)
        reg.register("b", 2)
        reg.clear()
        assert reg.list_services() == []

    def test_get_status(self):
        reg = Registry()
        reg.register("risk", [1, 2, 3])
        status = reg.get_status()
        assert status["risk"] == "list"

    def test_get_not_found_shows_available(self):
        reg = Registry()
        reg.register("exchange", "ex")
        reg.register("risk", "rk")
        with pytest.raises(RegistryError, match="exchange"):
            reg.get("memory")


# ══════════════════════════════════════════════════════════
# Scheduler Tests
# ══════════════════════════════════════════════════════════


class TestScheduler:
    def test_add_task(self):
        sched = Scheduler()

        async def noop():
            pass

        sched.add("test", 10.0, noop)
        assert "test" in sched.list_tasks()

    def test_remove_task(self):
        sched = Scheduler()

        async def noop():
            pass

        sched.add("test", 10.0, noop)
        sched.remove("test")
        assert "test" not in sched.list_tasks()

    @pytest.mark.asyncio
    async def test_run_once(self):
        sched = Scheduler()
        count = {"value": 0}

        async def increment():
            count["value"] += 1

        sched.add("counter", 10.0, increment)
        await sched.run_once("counter")
        assert count["value"] == 1

    @pytest.mark.asyncio
    async def test_run_once_not_found(self):
        sched = Scheduler()
        with pytest.raises(KeyError, match="not found"):
            await sched.run_once("fake")

    @pytest.mark.asyncio
    async def test_task_error_is_captured(self):
        sched = Scheduler()

        async def failing():
            raise RuntimeError("boom")

        sched.add("bad_task", 10.0, failing)
        await sched.run_once("bad_task")

        status = sched.get_status()
        assert status["bad_task"]["last_error"] == "boom"

    def test_enable_disable(self):
        sched = Scheduler()

        async def noop():
            pass

        sched.add("test", 10.0, noop)
        sched.disable("test")
        status = sched.get_status()
        assert status["test"]["enabled"] is False

        sched.enable("test")
        status = sched.get_status()
        assert status["test"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_start_stop(self):
        sched = Scheduler()
        count = {"value": 0}

        async def fast_task():
            count["value"] += 1

        sched.add("fast", 0.05, fast_task)
        await sched.start()
        assert sched.running is True

        await asyncio.sleep(0.2)
        await sched.stop()
        assert sched.running is False
        assert count["value"] >= 1

    def test_get_status(self):
        sched = Scheduler()

        async def noop():
            pass

        sched.add("test", 60.0, noop)
        status = sched.get_status()
        assert "test" in status
        assert status["test"]["interval_s"] == 60.0
        assert status["test"]["run_count"] == 0


# ══════════════════════════════════════════════════════════
# Integration Test — Full Flow
# ══════════════════════════════════════════════════════════


class TestIntegrationFlow:
    """
    Test the full flow: Signal → Risk → Trade → Memory
    All connected via Event Bus. No direct calls.
    """

    @pytest.mark.asyncio
    async def test_signal_to_trade_flow(self):
        """End-to-end: signal generates → risk checks → trade executes → memory logs."""
        bus = EventBus()
        registry = Registry()
        flow_log: list[str] = []

        # Simulate risk check handler
        async def risk_handler(msg: SignalGenerated):
            flow_log.append(f"risk_check:{msg.symbol}")
            # Simulate approval
            await bus.publish(RiskApproved(
                symbol=msg.symbol, side=msg.direction,
                approved_amount=0.01, risk_pct=0.71,
                source="risk_engine",
            ))

        # Simulate trade execution handler
        async def trade_handler(msg: RiskApproved):
            flow_log.append(f"trade_execute:{msg.symbol}")
            await bus.publish(TradeExecuted(
                trade_id="t001", symbol=msg.symbol,
                side=msg.side, amount=msg.approved_amount,
                price=71000.0, source="executor",
            ))

        # Simulate memory logging handler
        async def memory_handler(msg: TradeExecuted):
            flow_log.append(f"memory_log:{msg.trade_id}")
            await bus.publish(MemoryEvent(
                memory_type="trade", record_id=msg.trade_id,
                summary=f"Logged trade {msg.trade_id}",
            ))

        # Simulate notification handler
        async def notify_handler(msg: MemoryEvent):
            flow_log.append(f"notified:{msg.record_id}")

        # Wire up the event flow
        bus.subscribe(SignalGenerated, risk_handler)
        bus.subscribe(RiskApproved, trade_handler)
        bus.subscribe(TradeExecuted, memory_handler)
        bus.subscribe(MemoryEvent, notify_handler)

        # Trigger the flow with a signal
        await bus.publish(SignalGenerated(
            symbol="BTC/USDT", direction="BUY",
            confidence=0.8, reason="RSI oversold",
            source="scanner",
        ))

        # Verify the entire flow executed in order
        assert flow_log == [
            "risk_check:BTC/USDT",
            "trade_execute:BTC/USDT",
            "memory_log:t001",
            "notified:t001",
        ]

        # Verify message history
        history = bus.get_history()
        assert len(history) == 4  # signal + approved + executed + memoryevent
        types = [type(m).__name__ for m in history]
        assert "SignalGenerated" in types
        assert "RiskApproved" in types
        assert "TradeExecuted" in types
        assert "MemoryEvent" in types

    @pytest.mark.asyncio
    async def test_kill_switch_stops_flow(self):
        """Kill switch should prevent trading."""
        bus = EventBus()
        trades_executed = []

        async def trade_handler(msg: RiskApproved):
            trades_executed.append(msg)

        async def kill_handler(msg: KillSwitchActivated):
            # In real system, this would set kill switch on risk engine
            bus.unsubscribe(RiskApproved, trade_handler)

        bus.subscribe(RiskApproved, trade_handler)
        bus.subscribe(KillSwitchActivated, kill_handler)

        # Activate kill switch
        await bus.publish(KillSwitchActivated(reason="test"))

        # Try to execute a trade — should not reach trade_handler
        await bus.publish(RiskApproved(symbol="BTC/USDT", approved_amount=0.01))

        assert len(trades_executed) == 0

    @pytest.mark.asyncio
    async def test_registry_with_event_bus(self):
        """Registry + EventBus working together."""
        bus = EventBus()
        registry = Registry()
        registry.register("event_bus", bus)

        # Get bus from registry
        retrieved_bus = registry.get("event_bus")
        received = []

        async def handler(msg):
            received.append(msg)

        retrieved_bus.subscribe(SystemEvent, handler)
        await retrieved_bus.publish(SystemEvent(
            event_type="system", message="Started",
        ))

        assert len(received) == 1
