"""
TREDO — Memory Journal
Public API for logging and querying all 4 memory types.
This is the ONLY interface other modules should use.

API:
    journal.log_trade(...)       → TradeRecord
    journal.log_decision(...)    → DecisionRecord
    journal.log_risk(...)        → RiskRecord
    journal.log_event(...)       → EventRecord
    journal.get_trade(id)        → TradeRecord | None
    journal.close_trade(id, ...) → TradeRecord
    journal.get_recent(limit)    → list of mixed records
    journal.search(symbol, ...)  → list of TradeRecords
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.memory.models import (
    DecisionRecord,
    EventRecord,
    RiskRecord,
    TradeRecord,
)
from backend.memory.storage import MemoryStorage

logger = logging.getLogger(__name__)


class Journal:
    """
    TREDO's black box recorder.
    Logs trades, decisions, risk events, and system events to SQLite.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._storage = MemoryStorage(db_path)

    @property
    def connected(self) -> bool:
        return self._storage.connected

    def connect(self) -> None:
        """Open the journal database."""
        self._storage.connect()
        logger.info("Journal connected: %s", self._storage.db_path)

    def close(self) -> None:
        """Close the journal database."""
        self._storage.close()

    # ── Trade Memory ─────────────────────────────────────────

    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        reason: str,
    ) -> TradeRecord:
        """Log a new trade entry."""
        record = TradeRecord(
            symbol=symbol, side=side, quantity=quantity,
            entry_price=entry_price, reason=reason,
        )
        self._storage.execute(
            "INSERT INTO trades (id, symbol, side, quantity, entry_price, "
            "exit_price, pnl, status, reason, created_at, closed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            record.to_row(),
        )
        logger.info("Trade logged: %s %s %s @ %s", side, quantity, symbol, entry_price)
        return record

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
    ) -> TradeRecord | None:
        """Close an open trade with exit price and P&L."""
        from backend.memory.models import _now
        now = _now()

        self._storage.execute(
            "UPDATE trades SET exit_price=?, pnl=?, status='closed', closed_at=? "
            "WHERE id=? AND status='open'",
            (exit_price, pnl, now, trade_id),
        )

        row = self._storage.query_one("SELECT * FROM trades WHERE id=?", (trade_id,))
        if row is None:
            return None

        record = TradeRecord.from_row(row)
        logger.info("Trade closed: %s — PnL: $%.2f", trade_id, pnl)
        return record

    def get_trade(self, trade_id: str) -> TradeRecord | None:
        """Get a single trade by ID."""
        row = self._storage.query_one("SELECT * FROM trades WHERE id=?", (trade_id,))
        return TradeRecord.from_row(row) if row else None

    def get_trades(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[TradeRecord]:
        """Get trades with optional filters."""
        sql = "SELECT * FROM trades WHERE 1=1"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        if status:
            sql += " AND status=?"
            params.append(status)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._storage.query(sql, tuple(params))
        return [TradeRecord.from_row(r) for r in rows]

    # ── Decision Memory ──────────────────────────────────────

    def log_decision(
        self,
        decision: str,
        confidence: int,
        reasons: list[str],
        symbol: str | None = None,
        source: str = "system",
    ) -> DecisionRecord:
        """Log an AI decision."""
        record = DecisionRecord(
            decision=decision, confidence=confidence,
            reasons=reasons, symbol=symbol, source=source,
        )
        row_id = self._storage.execute(
            "INSERT INTO decisions (decision, confidence, reasons, symbol, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            record.to_row(),
        )
        record.id = row_id
        logger.info("Decision logged: %s (confidence: %d%%)", decision, confidence)
        return record

    def get_decisions(
        self,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[DecisionRecord]:
        """Get recent decisions."""
        sql = "SELECT * FROM decisions WHERE 1=1"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._storage.query(sql, tuple(params))
        return [DecisionRecord.from_row(r) for r in rows]

    # ── Risk Memory ──────────────────────────────────────────

    def log_risk(
        self,
        action: str,
        reasons: list[str],
        symbol: str | None = None,
        side: str | None = None,
        amount: float | None = None,
        source: str = "risk_engine",
    ) -> RiskRecord:
        """Log a risk event (rejection, kill switch, cool-down)."""
        record = RiskRecord(
            action=action, reasons=reasons, symbol=symbol,
            side=side, amount=amount, source=source,
        )
        row_id = self._storage.execute(
            "INSERT INTO risk_events (action, symbol, side, amount, reasons, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            record.to_row(),
        )
        record.id = row_id
        logger.info("Risk event logged: %s — %s", action, symbol or "system")
        return record

    def get_risk_events(self, limit: int = 50) -> list[RiskRecord]:
        """Get recent risk events."""
        rows = self._storage.query(
            "SELECT * FROM risk_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [RiskRecord.from_row(r) for r in rows]

    # ── Event Memory ─────────────────────────────────────────

    def log_event(
        self,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        severity: str = "info",
    ) -> EventRecord:
        """Log a system event."""
        record = EventRecord(
            event_type=event_type, message=message,
            details=details or {}, severity=severity,
        )
        row_id = self._storage.execute(
            "INSERT INTO events (event_type, message, details, severity, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            record.to_row(),
        )
        record.id = row_id
        logger.info("Event logged: [%s] %s", event_type, message)
        return record

    def get_events(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[EventRecord]:
        """Get recent events with optional filters."""
        sql = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []

        if event_type:
            sql += " AND event_type=?"
            params.append(event_type)
        if severity:
            sql += " AND severity=?"
            params.append(severity)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._storage.query(sql, tuple(params))
        return [EventRecord.from_row(r) for r in rows]

    # ── Cross-Type Queries ───────────────────────────────────

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent entries from ALL memory types, sorted by time."""
        results: list[dict[str, Any]] = []

        for trade in self.get_trades(limit=limit):
            results.append({"type": "trade", "time": trade.created_at, "data": trade})

        for decision in self.get_decisions(limit=limit):
            results.append({"type": "decision", "time": decision.created_at, "data": decision})

        for risk in self.get_risk_events(limit=limit):
            results.append({"type": "risk", "time": risk.created_at, "data": risk})

        for event in self.get_events(limit=limit):
            results.append({"type": "event", "time": event.created_at, "data": event})

        results.sort(key=lambda x: x["time"], reverse=True)
        return results[:limit]

    def search(
        self,
        symbol: str | None = None,
        side: str | None = None,
        limit: int = 50,
    ) -> list[TradeRecord]:
        """Search trades by symbol and/or side."""
        sql = "SELECT * FROM trades WHERE 1=1"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol LIKE ?"
            params.append(f"%{symbol}%")
        if side:
            sql += " AND side=?"
            params.append(side)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._storage.query(sql, tuple(params))
        return [TradeRecord.from_row(r) for r in rows]

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, int]:
        """Get record counts for all memory types."""
        return {
            "trades": self._storage.count("trades"),
            "decisions": self._storage.count("decisions"),
            "risk_events": self._storage.count("risk_events"),
            "events": self._storage.count("events"),
        }
