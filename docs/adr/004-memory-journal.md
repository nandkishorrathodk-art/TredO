# ADR 004: Memory Journal (SQLite)

## Problem
A multi-agent trading system generates a vast amount of data: trades, AI decisions, risk rejections, and system events. This data needs to be logged immutably, queried easily, and remain resilient to system crashes.

## Decision
We implemented the Memory Engine as a "black box recorder" using a local SQLite database (`schema.sql` + `storage.py`), completely avoiding heavy ORMs like SQLAlchemy.

## Alternatives Considered
- **Vector Databases (Chroma, Pinecone):** Great for semantic search, but terrible for structured, time-series trading data (prices, timestamps, strict filtering).
- **PostgreSQL / MySQL:** Requires a separate server daemon, violating the requirement for an easy-to-install, standalone desktop app.
- **Heavy ORMs (SQLAlchemy):** Adds unnecessary complexity and performance overhead for our simple append-heavy, read-light workload.

## Why this approach
- **Self-Contained:** SQLite is built into Python. No external dependencies or servers.
- **Performance:** WAL (Write-Ahead Logging) mode allows high-concurrency writes and reads sufficient for our scale.
- **Simplicity:** Raw SQL with simple dataclass mapping keeps the codebase small and highly readable.

## Consequences
- **Pros:** Zero setup required for the end user; fast and reliable; easy to inspect using standard SQLite tools.
- **Cons:** Lacks semantic search capabilities (which will be needed for true "Agent Memory" in V3, likely requiring a hybrid SQLite + Vector DB approach later).
