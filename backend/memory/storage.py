"""
TREDO — Memory Storage Layer
SQLite-based storage for all 4 memory types.
Handles DB initialization, schema migration, and raw queries.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "tredo_memory.db"


class MemoryStorage:
    """
    SQLite storage backend for the memory engine.
    Manages connection, schema initialization, and CRUD operations.

    Usage:
        storage = MemoryStorage()  # uses default path
        storage.connect()
        storage.execute("INSERT INTO events ...", params)
        rows = storage.query("SELECT * FROM events WHERE ...")
        storage.close()
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB
        self._conn: sqlite3.Connection | None = None

    @property
    def connected(self) -> bool:
        return self._conn is not None

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> None:
        """Open SQLite connection and initialize schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._conn

    def _init_schema(self) -> None:
        """Create tables from schema.sql if they don't exist."""
        conn = self._require_connection()
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
        conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        """Execute a write query. Returns lastrowid for INSERTs."""
        conn = self._require_connection()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid or 0

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute a read query. Returns list of row dicts."""
        conn = self._require_connection()
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute a read query. Returns single row dict or None."""
        conn = self._require_connection()
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def count(self, table: str) -> int:
        """Get total row count for a table."""
        result = self.query_one(f"SELECT COUNT(*) as cnt FROM {table}")
        return result["cnt"] if result else 0

    def delete_db(self) -> None:
        """Delete the database file. For testing only."""
        self.close()
        if self._db_path.exists():
            self._db_path.unlink()
