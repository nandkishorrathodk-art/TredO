"""
TREDO — Execution Module Tests
Tests Order models, state machine, PaperExchange, PositionManager,
and OrderService with full integration via Event Bus.
"""

import pytest
from backend.execution.models import (
    Order, OrderState, InvalidOrderTransition,
    Position, PositionState,
)
from backend.execution.paper_exchange import PaperExchange
from backend.execution.position_manager import PositionManager
from backend.execution.order_service import (
    OrderService,
    OrderSubmitted, OrderValidated, OrderRejected,
    OrderFilled, PositionOpened, PositionClosed, PnLUpdated,
)
from backend.core.event_bus import EventBus
from backend.risk.engine import RiskEngine


# ── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def risk():
    r = RiskEngine()
    r.load_rules()
    return r


@pytest.fixture
def exchange():
    ex = PaperExchange(initial_balance=10_000.0)
    ex.set_price("BTC/USDT", 70_000.0)
    ex.set_price("ETH/USDT", 3_500.0)
    return ex


@pytest.fixture
def positions():
    return PositionManager()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def order_service(bus, risk, exchange, positions):
    return OrderService(
        bus=bus, risk=risk, exchange=exchange,
        positions=positions, portfolio_value=10_000.0,
    )


# ══════════════════════════════════════════════════════════
# Order Model Tests
# ══════════════════════════════════════════════════════════


class TestOrderModel:
    def test_create_order(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        assert order.state == OrderState.NEW
        assert order.order_id.startswith("ORD-")
        assert not order.is_terminal

    def test_valid_transition_new_to_validated(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.VALIDATED)
        assert order.state == OrderState.VALIDATED

    def test_valid_transition_to_filled(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)
        order.transition(OrderState.FILLED, fill_price=69500, fill_amount=0.01)
        assert order.fill_price == 69500
        assert order.fill_amount == 0.01
        assert order.cost == 695.0

    def test_invalid_transition_raises(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        with pytest.raises(InvalidOrderTransition):
            order.transition(OrderState.FILLED)

    def test_rejected_records_reasons(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.REJECTED, reasons=["Too risky"])
        assert order.state == OrderState.REJECTED
        assert order.is_terminal
        assert "Too risky" in order.rejection_reasons

    def test_cancelled_is_terminal(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)
        order.transition(OrderState.CANCELLED)
        assert order.is_terminal

    def test_to_dict(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        d = order.to_dict()
        assert d["symbol"] == "BTC/USDT"
        assert d["state"] == "new"
        assert "order_id" in d

    def test_full_lifecycle(self):
        order = Order(symbol="ETH/USDT", side="sell", amount=1.0, price=3500)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)
        order.transition(OrderState.FILLED, fill_price=3500, fill_amount=1.0)
        order.transition(OrderState.CLOSED)
        assert order.state == OrderState.CLOSED
        assert order.is_terminal

    def test_cannot_transition_from_terminal(self):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.REJECTED, reasons=["nope"])
        with pytest.raises(InvalidOrderTransition):
            order.transition(OrderState.VALIDATED)


# ══════════════════════════════════════════════════════════
# Position Model Tests
# ══════════════════════════════════════════════════════════


class TestPositionModel:
    def test_create_position(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        assert pos.is_open
        assert pos.position_id.startswith("POS-")

    def test_unrealized_pnl_buy(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        assert pos.unrealized_pnl(71000) == 10.0   # +$10
        assert pos.unrealized_pnl(69000) == -10.0   # -$10

    def test_unrealized_pnl_sell(self):
        pos = Position(symbol="BTC/USDT", side="sell", entry_price=70000, amount=0.01)
        assert pos.unrealized_pnl(69000) == 10.0    # +$10 (short)
        assert pos.unrealized_pnl(71000) == -10.0   # -$10 (short)

    def test_close_buy_profit(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        pnl = pos.close(71000)
        assert pnl == 10.0
        assert pos.state == PositionState.CLOSED
        assert pos.realized_pnl == 10.0

    def test_close_buy_loss(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        pnl = pos.close(69000)
        assert pnl == -10.0

    def test_close_sell_profit(self):
        pos = Position(symbol="BTC/USDT", side="sell", entry_price=70000, amount=0.01)
        pnl = pos.close(69000)
        assert pnl == 10.0

    def test_close_already_closed_raises(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        pos.close(71000)
        with pytest.raises(ValueError, match="already"):
            pos.close(72000)

    def test_notional(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        assert pos.notional == 700.0

    def test_to_dict(self):
        pos = Position(symbol="BTC/USDT", side="buy", entry_price=70000, amount=0.01)
        d = pos.to_dict()
        assert d["symbol"] == "BTC/USDT"
        assert d["state"] == "open"


# ══════════════════════════════════════════════════════════
# Paper Exchange Tests
# ══════════════════════════════════════════════════════════


class TestPaperExchange:
    @pytest.mark.asyncio
    async def test_fill_buy_order(self, exchange):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)

        filled = await exchange.execute_order(order)
        assert filled.state == OrderState.FILLED
        assert filled.fill_price == 70000
        assert exchange.balance == 10000 - 700

    @pytest.mark.asyncio
    async def test_fill_sell_order(self, exchange):
        order = Order(symbol="ETH/USDT", side="sell", amount=1.0, price=3500)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)

        filled = await exchange.execute_order(order)
        assert filled.state == OrderState.FILLED
        assert exchange.balance == 10000 + 3500

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, exchange):
        order = Order(symbol="BTC/USDT", side="buy", amount=1.0, price=70000)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)

        result = await exchange.execute_order(order)
        assert result.state == OrderState.REJECTED
        assert "Insufficient balance" in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_no_price_set(self, exchange):
        order = Order(symbol="SOL/USDT", side="buy", amount=1.0, price=100)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)

        with pytest.raises(ValueError, match="No price"):
            await exchange.execute_order(order)

    @pytest.mark.asyncio
    async def test_get_current_price(self, exchange):
        price = await exchange.get_current_price("BTC/USDT")
        assert price == 70000

    @pytest.mark.asyncio
    async def test_get_price_not_set(self, exchange):
        with pytest.raises(ValueError):
            await exchange.get_current_price("DOGE/USDT")

    def test_get_status(self, exchange):
        status = exchange.get_status()
        assert status["name"] == "PaperExchange"
        assert status["balance"] == 10000

    def test_reset(self, exchange):
        exchange._balance = 5000
        exchange.reset()
        assert exchange.balance == 10000
        assert len(exchange._prices) == 0

    @pytest.mark.asyncio
    async def test_cancel_order(self, exchange):
        order = Order(symbol="BTC/USDT", side="buy", amount=0.01, price=70000)
        order.transition(OrderState.VALIDATED)
        order.transition(OrderState.ACCEPTED)
        exchange._orders[order.order_id] = order

        result = await exchange.cancel_order(order.order_id)
        assert result is True
        assert order.state == OrderState.CANCELLED


# ══════════════════════════════════════════════════════════
# Position Manager Tests
# ══════════════════════════════════════════════════════════


class TestPositionManager:
    def test_open_position(self, positions):
        pos = positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        assert pos.is_open
        assert len(positions.get_open_positions()) == 1

    def test_close_position(self, positions):
        pos = positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        closed = positions.close_position(pos.position_id, 71000)
        assert closed.state == PositionState.CLOSED
        assert closed.realized_pnl == 10.0
        assert len(positions.get_open_positions()) == 0
        assert len(positions.get_closed_positions()) == 1

    def test_close_not_found(self, positions):
        with pytest.raises(KeyError):
            positions.close_position("FAKE", 70000)

    def test_get_open_by_symbol(self, positions):
        positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        positions.open_position("ETH/USDT", "buy", 3500, 1.0)

        btc = positions.get_open_positions("BTC/USDT")
        assert len(btc) == 1
        assert btc[0].symbol == "BTC/USDT"

    def test_total_realized_pnl(self, positions):
        p1 = positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        p2 = positions.open_position("ETH/USDT", "buy", 3500, 1.0)
        positions.close_position(p1.position_id, 71000)  # +10
        positions.close_position(p2.position_id, 3600)   # +100
        assert positions.total_realized_pnl() == 110.0

    def test_total_unrealized_pnl(self, positions):
        positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        pnl = positions.total_unrealized_pnl({"BTC/USDT": 71000})
        assert pnl == 10.0

    def test_total_exposure(self, positions):
        positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        positions.open_position("ETH/USDT", "buy", 3500, 1.0)
        assert positions.total_exposure() == 700 + 3500

    def test_get_summary(self, positions):
        positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        summary = positions.get_summary({"BTC/USDT": 71000})
        assert summary["open_count"] == 1
        assert summary["unrealized_pnl"] == 10.0

    def test_clear(self, positions):
        positions.open_position("BTC/USDT", "buy", 70000, 0.01)
        positions.clear()
        assert len(positions.get_open_positions()) == 0


# ══════════════════════════════════════════════════════════
# Order Service Tests — Full Integration
# ══════════════════════════════════════════════════════════


class TestOrderService:
    @pytest.mark.asyncio
    async def test_submit_order_full_flow(self, order_service, bus):
        """Full flow: submit → risk → execute → position → events."""
        events_log = []

        async def capture(msg):
            events_log.append(type(msg).__name__)

        bus.subscribe(OrderSubmitted, capture)
        bus.subscribe(OrderValidated, capture)
        bus.subscribe(OrderFilled, capture)
        bus.subscribe(PositionOpened, capture)

        order = await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="Test buy",
        )

        assert order.state == OrderState.FILLED
        assert "OrderSubmitted" in events_log
        assert "OrderValidated" in events_log
        assert "OrderFilled" in events_log
        assert "PositionOpened" in events_log

    @pytest.mark.asyncio
    async def test_order_rejected_by_risk(self, order_service, bus):
        """Order rejected because no reason provided."""
        rejections = []

        async def on_reject(msg):
            rejections.append(msg)

        bus.subscribe(OrderRejected, on_reject)

        order = await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="",  # Empty reason → rejected by L0
        )

        assert order.state == OrderState.REJECTED
        assert len(rejections) == 1

    @pytest.mark.asyncio
    async def test_close_position_via_service(self, order_service, bus, positions):
        """Close position and verify PnL events."""
        pnl_events = []

        async def on_pnl(msg):
            pnl_events.append(msg)

        bus.subscribe(PnLUpdated, on_pnl)
        bus.subscribe(PositionClosed, on_pnl)

        # Open a position
        await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="Test",
        )
        assert len(positions.get_open_positions()) == 1

        # Price goes up
        order_service._exchange.set_price("BTC/USDT", 71000)

        # Close it
        pos = positions.get_open_positions()[0]
        closed = await order_service.close_position(pos.position_id, 71000)

        assert closed.realized_pnl == 2.0  # (71000-70000) * 0.002
        assert len(pnl_events) == 2  # PositionClosed + PnLUpdated

    @pytest.mark.asyncio
    async def test_multiple_orders(self, order_service, positions, risk):
        """Submit multiple orders and verify positions."""
        await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="Buy BTC",
        )
        # Reset rate limiter for test (min_order_interval_seconds: 5)
        risk._last_order_time = 0

        await order_service.submit_order(
            symbol="ETH/USDT", side="buy", amount=0.04,
            price=3500, reason="Buy ETH",
        )

        assert len(positions.get_open_positions()) == 2
        assert len(order_service.get_all_orders()) == 2

    @pytest.mark.asyncio
    async def test_get_summary(self, order_service):
        await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="Test",
        )
        summary = order_service.get_summary()
        assert summary["total_orders"] == 1
        assert summary["positions"]["open_count"] == 1

    @pytest.mark.asyncio
    async def test_get_order(self, order_service):
        order = await order_service.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70000, reason="Test",
        )
        retrieved = order_service.get_order(order.order_id)
        assert retrieved is not None
        assert retrieved.order_id == order.order_id

    @pytest.mark.asyncio
    async def test_sell_order(self, order_service, exchange):
        """Sell order increases balance."""
        initial = exchange.balance
        await order_service.submit_order(
            symbol="ETH/USDT", side="sell", amount=0.04,
            price=3500, reason="Take profit",
        )
        assert exchange.balance > initial


# ══════════════════════════════════════════════════════════
# Full Pipeline Integration Test
# ══════════════════════════════════════════════════════════


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_order_to_close_full_loop(self):
        """
        Complete V1 flow:
        Submit → Risk → Fill → Position → Close → PnL
        All via Event Bus.
        """
        bus = EventBus()
        risk = RiskEngine()
        risk.load_rules()
        exchange = PaperExchange(initial_balance=10_000)
        exchange.set_price("BTC/USDT", 70_000)
        positions = PositionManager()

        svc = OrderService(bus, risk, exchange, positions, 10_000)

        # Capture all events
        all_events: list[str] = []

        async def log_event(msg):
            all_events.append(type(msg).__name__)

        bus.subscribe(OrderSubmitted, log_event)
        bus.subscribe(OrderValidated, log_event)
        bus.subscribe(OrderFilled, log_event)
        bus.subscribe(PositionOpened, log_event)
        bus.subscribe(PositionClosed, log_event)
        bus.subscribe(PnLUpdated, log_event)

        # 1. Submit buy order
        order = await svc.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70_000, reason="Bullish breakout",
        )
        assert order.state == OrderState.FILLED

        # 2. Verify position exists
        open_pos = positions.get_open_positions()
        assert len(open_pos) == 1
        pos = open_pos[0]

        # 3. Price goes up
        exchange.set_price("BTC/USDT", 72_000)

        # 4. Close position at profit
        closed = await svc.close_position(pos.position_id, 72_000)
        assert closed.realized_pnl == 4.0  # (72000-70000) * 0.002

        # 5. Verify event sequence
        assert all_events == [
            "OrderSubmitted",
            "OrderValidated",
            "OrderFilled",
            "PositionOpened",
            "PositionClosed",
            "PnLUpdated",
        ]

        # 6. Verify no open positions
        assert len(positions.get_open_positions()) == 0
        assert positions.total_realized_pnl() == 4.0

    @pytest.mark.asyncio
    async def test_kill_switch_blocks_orders(self):
        """Kill switch should prevent new orders."""
        bus = EventBus()
        risk = RiskEngine()
        risk.load_rules()
        risk.activate_kill_switch("emergency test")
        exchange = PaperExchange(initial_balance=10_000)
        exchange.set_price("BTC/USDT", 70_000)
        positions = PositionManager()

        svc = OrderService(bus, risk, exchange, positions, 10_000)

        order = await svc.submit_order(
            symbol="BTC/USDT", side="buy", amount=0.002,
            price=70_000, reason="Should be blocked",
        )
        assert order.state == OrderState.REJECTED
