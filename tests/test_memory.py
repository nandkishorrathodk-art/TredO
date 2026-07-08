"""
TREDO — Memory Engine Tests
Covers all 4 memory types: trades, decisions, risk events, system events.
Plus: cross-type queries, search, stats, edge cases.
"""

import pytest
from pathlib import Path

from backend.memory.journal import Journal
from backend.memory.storage import MemoryStorage
from backend.memory.models import TradeRecord, DecisionRecord, RiskRecord, EventRecord


TEST_DB = Path(__file__).parent / "test_memory.db"


@pytest.fixture
def journal():
    """Create a fresh journal with an in-memory-like test DB."""
    j = Journal(db_path=TEST_DB)
    j.connect()
    yield j
    j.close()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def storage():
    """Create a raw storage instance for low-level tests."""
    s = MemoryStorage(db_path=TEST_DB)
    s.connect()
    yield s
    s.close()
    s.delete_db()


# ══════════════════════════════════════════════════════════
# Storage Layer Tests
# ══════════════════════════════════════════════════════════


class TestStorage:
    def test_connect_creates_db(self, storage: MemoryStorage):
        assert storage.connected is True
        assert storage.db_path.exists()

    def test_schema_creates_tables(self, storage: MemoryStorage):
        tables = storage.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [t["name"] for t in tables]
        assert "trades" in names
        assert "decisions" in names
        assert "risk_events" in names
        assert "events" in names

    def test_not_connected_raises(self):
        s = MemoryStorage(db_path=TEST_DB)
        with pytest.raises(RuntimeError, match="not connected"):
            s.execute("SELECT 1")

    def test_count_empty_table(self, storage: MemoryStorage):
        assert storage.count("trades") == 0
        assert storage.count("events") == 0

    def test_query_one_returns_none(self, storage: MemoryStorage):
        result = storage.query_one("SELECT * FROM trades WHERE id='none'")
        assert result is None

    def test_delete_db(self):
        s = MemoryStorage(db_path=TEST_DB)
        s.connect()
        assert TEST_DB.exists()
        s.delete_db()
        assert not TEST_DB.exists()


# ══════════════════════════════════════════════════════════
# Trade Memory Tests
# ══════════════════════════════════════════════════════════


class TestTradeMemory:
    def test_log_trade(self, journal: Journal):
        trade = journal.log_trade(
            symbol="BTC/USDT", side="buy", quantity=0.01,
            entry_price=71000.0, reason="RSI oversold bounce"
        )
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "buy"
        assert trade.quantity == 0.01
        assert trade.entry_price == 71000.0
        assert trade.status == "open"
        assert trade.reason == "RSI oversold bounce"
        assert trade.id is not None

    def test_get_trade_by_id(self, journal: Journal):
        trade = journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test")
        fetched = journal.get_trade(trade.id)
        assert fetched is not None
        assert fetched.id == trade.id
        assert fetched.symbol == "ETH/USDT"

    def test_get_trade_not_found(self, journal: Journal):
        assert journal.get_trade("nonexistent") is None

    def test_close_trade(self, journal: Journal):
        trade = journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test")
        closed = journal.close_trade(trade.id, exit_price=72000.0, pnl=10.0)
        assert closed is not None
        assert closed.status == "closed"
        assert closed.exit_price == 72000.0
        assert closed.pnl == 10.0
        assert closed.closed_at is not None

    def test_close_nonexistent_trade(self, journal: Journal):
        result = journal.close_trade("fake_id", 72000.0, 10.0)
        assert result is None

    def test_get_trades_all(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test1")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test2")
        journal.log_trade("BTC/USDT", "sell", 0.01, 72000.0, "test3")

        trades = journal.get_trades()
        assert len(trades) == 3

    def test_get_trades_filter_symbol(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test1")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test2")
        journal.log_trade("BTC/USDT", "sell", 0.01, 72000.0, "test3")

        btc_trades = journal.get_trades(symbol="BTC/USDT")
        assert len(btc_trades) == 2
        assert all(t.symbol == "BTC/USDT" for t in btc_trades)

    def test_get_trades_filter_status(self, journal: Journal):
        t1 = journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test")
        journal.close_trade(t1.id, 72000.0, 10.0)

        open_trades = journal.get_trades(status="open")
        assert len(open_trades) == 1

        closed_trades = journal.get_trades(status="closed")
        assert len(closed_trades) == 1

    def test_get_trades_with_limit(self, journal: Journal):
        for i in range(10):
            journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0 + i, f"test{i}")
        trades = journal.get_trades(limit=5)
        assert len(trades) == 5


# ══════════════════════════════════════════════════════════
# Decision Memory Tests
# ══════════════════════════════════════════════════════════


class TestDecisionMemory:
    def test_log_decision(self, journal: Journal):
        decision = journal.log_decision(
            decision="BUY BTC",
            confidence=87,
            reasons=["Bullish breakout", "Positive sentiment", "Risk approved"],
            symbol="BTC/USDT",
            source="scanner_agent",
        )
        assert decision.decision == "BUY BTC"
        assert decision.confidence == 87
        assert len(decision.reasons) == 3
        assert "Bullish breakout" in decision.reasons
        assert decision.id is not None

    def test_get_decisions(self, journal: Journal):
        journal.log_decision("BUY BTC", 87, ["reason1"], "BTC/USDT")
        journal.log_decision("SELL ETH", 65, ["reason2"], "ETH/USDT")

        all_decisions = journal.get_decisions()
        assert len(all_decisions) == 2

    def test_get_decisions_filter_symbol(self, journal: Journal):
        journal.log_decision("BUY BTC", 87, ["reason1"], "BTC/USDT")
        journal.log_decision("SELL ETH", 65, ["reason2"], "ETH/USDT")

        btc = journal.get_decisions(symbol="BTC/USDT")
        assert len(btc) == 1
        assert btc[0].decision == "BUY BTC"

    def test_decision_reasons_preserved(self, journal: Journal):
        reasons = ["Reason A", "Reason B", "Reason C"]
        d = journal.log_decision("HOLD", 50, reasons, "BTC/USDT")
        fetched = journal.get_decisions(symbol="BTC/USDT")
        assert fetched[0].reasons == reasons


# ══════════════════════════════════════════════════════════
# Risk Memory Tests
# ══════════════════════════════════════════════════════════


class TestRiskMemory:
    def test_log_risk_rejection(self, journal: Journal):
        risk = journal.log_risk(
            action="rejected",
            reasons=["Daily drawdown exceeded", "Position too large"],
            symbol="BTC/USDT",
            side="buy",
            amount=0.5,
        )
        assert risk.action == "rejected"
        assert len(risk.reasons) == 2
        assert risk.symbol == "BTC/USDT"
        assert risk.id is not None

    def test_log_kill_switch(self, journal: Journal):
        risk = journal.log_risk(
            action="kill_switch",
            reasons=["Manual activation by user"],
        )
        assert risk.action == "kill_switch"

    def test_get_risk_events(self, journal: Journal):
        journal.log_risk("rejected", ["reason1"], "BTC/USDT")
        journal.log_risk("cool_down", ["significant loss"])
        journal.log_risk("rejected", ["reason2"], "ETH/USDT")

        events = journal.get_risk_events()
        assert len(events) == 3

    def test_risk_reasons_preserved(self, journal: Journal):
        reasons = ["Max exposure", "Leverage too high", "Cool-down active"]
        journal.log_risk("rejected", reasons, "SOL/USDT")
        events = journal.get_risk_events()
        assert events[0].reasons == reasons


# ══════════════════════════════════════════════════════════
# Event Memory Tests
# ══════════════════════════════════════════════════════════


class TestEventMemory:
    def test_log_event(self, journal: Journal):
        event = journal.log_event(
            event_type="exchange",
            message="Connected to Binance testnet",
            details={"exchange": "binance", "testnet": True},
        )
        assert event.event_type == "exchange"
        assert event.message == "Connected to Binance testnet"
        assert event.details["exchange"] == "binance"
        assert event.severity == "info"
        assert event.id is not None

    def test_log_error_event(self, journal: Journal):
        event = journal.log_event(
            event_type="error",
            message="WebSocket connection lost",
            severity="error",
        )
        assert event.severity == "error"

    def test_get_events(self, journal: Journal):
        journal.log_event("exchange", "Connected")
        journal.log_event("system", "Paper trading enabled")
        journal.log_event("config", "Settings changed")

        all_events = journal.get_events()
        assert len(all_events) == 3

    def test_get_events_filter_type(self, journal: Journal):
        journal.log_event("exchange", "Connected")
        journal.log_event("system", "Started")
        journal.log_event("exchange", "Disconnected")

        exchange = journal.get_events(event_type="exchange")
        assert len(exchange) == 2

    def test_get_events_filter_severity(self, journal: Journal):
        journal.log_event("system", "Info message", severity="info")
        journal.log_event("error", "Error occurred", severity="error")
        journal.log_event("system", "Warning", severity="warning")

        errors = journal.get_events(severity="error")
        assert len(errors) == 1


# ══════════════════════════════════════════════════════════
# Cross-Type Query Tests
# ══════════════════════════════════════════════════════════


class TestCrossTypeQueries:
    def test_get_recent_mixed(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test")
        journal.log_decision("BUY", 80, ["reason"], "BTC/USDT")
        journal.log_risk("rejected", ["limit"], "ETH/USDT")
        journal.log_event("system", "Started")

        recent = journal.get_recent(limit=10)
        assert len(recent) == 4
        types = {r["type"] for r in recent}
        assert types == {"trade", "decision", "risk", "event"}

    def test_get_recent_respects_limit(self, journal: Journal):
        for i in range(10):
            journal.log_event("system", f"Event {i}")
        recent = journal.get_recent(limit=5)
        assert len(recent) == 5

    def test_search_by_symbol(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test1")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test2")
        journal.log_trade("BTC/USDT", "sell", 0.01, 72000.0, "test3")

        results = journal.search(symbol="BTC")
        assert len(results) == 2

    def test_search_by_side(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test1")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test2")
        journal.log_trade("BTC/USDT", "buy", 0.02, 71500.0, "test3")

        buys = journal.search(side="buy")
        assert len(buys) == 2

    def test_search_combined_filters(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test1")
        journal.log_trade("BTC/USDT", "sell", 0.01, 72000.0, "test2")
        journal.log_trade("ETH/USDT", "buy", 0.5, 3800.0, "test3")

        results = journal.search(symbol="BTC", side="buy")
        assert len(results) == 1
        assert results[0].side == "buy"
        assert results[0].symbol == "BTC/USDT"


# ══════════════════════════════════════════════════════════
# Stats Tests
# ══════════════════════════════════════════════════════════


class TestStats:
    def test_stats_empty(self, journal: Journal):
        stats = journal.get_stats()
        assert stats == {
            "trades": 0, "decisions": 0,
            "risk_events": 0, "events": 0,
        }

    def test_stats_after_logging(self, journal: Journal):
        journal.log_trade("BTC/USDT", "buy", 0.01, 71000.0, "test")
        journal.log_trade("ETH/USDT", "sell", 0.5, 3800.0, "test")
        journal.log_decision("BUY", 80, ["reason"])
        journal.log_risk("rejected", ["limit"])
        journal.log_event("system", "Started")
        journal.log_event("exchange", "Connected")

        stats = journal.get_stats()
        assert stats["trades"] == 2
        assert stats["decisions"] == 1
        assert stats["risk_events"] == 1
        assert stats["events"] == 2


# ══════════════════════════════════════════════════════════
# Model Serialization Tests
# ══════════════════════════════════════════════════════════


class TestModels:
    def test_trade_record_fields(self):
        t = TradeRecord("BTC/USDT", "buy", 0.01, 71000.0, "test")
        assert t.status == "open"
        assert t.exit_price is None
        assert t.pnl is None

    def test_decision_record_fields(self):
        d = DecisionRecord("BUY", 90, ["a", "b"])
        assert d.confidence == 90
        assert len(d.reasons) == 2

    def test_risk_record_fields(self):
        r = RiskRecord("rejected", ["limit exceeded"])
        assert r.action == "rejected"

    def test_event_record_fields(self):
        e = EventRecord("system", "test message")
        assert e.severity == "info"
        assert e.details == {}
