-- TREDO Memory Engine — SQLite Schema
-- Stores 4 memory types: trades, decisions, risks, events.
-- This is the system's black box recorder.

CREATE TABLE IF NOT EXISTS trades (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity    REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price  REAL,
    pnl         REAL,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at   TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    decision    TEXT NOT NULL,
    confidence  INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    reasons     TEXT NOT NULL DEFAULT '[]',   -- JSON array of strings
    symbol      TEXT,
    source      TEXT NOT NULL DEFAULT 'system',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,               -- 'rejected', 'kill_switch', 'cool_down'
    symbol      TEXT,
    side        TEXT,
    amount      REAL,
    reasons     TEXT NOT NULL DEFAULT '[]',   -- JSON array of rejection reasons
    source      TEXT NOT NULL DEFAULT 'risk_engine',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,               -- 'exchange', 'system', 'config', 'error'
    message     TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}',   -- JSON object with extra info
    severity    TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_created ON risk_events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
