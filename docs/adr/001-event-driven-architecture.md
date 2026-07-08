# ADR 001: Event-Driven Architecture

## Problem
In a complex multi-agent system, modules (Exchange, Risk, Memory, Agents) can quickly become tightly coupled. If Agent A directly calls Agent B, or if Risk Engine directly calls Memory, circular dependencies and spaghetti code emerge, making the project impossible to maintain after reaching 200+ files.

## Decision
We adopted a strictly Event-Driven Architecture (EDA) via a central `EventBus` and strongly-typed `BaseMessage` objects.

## Alternatives Considered
- **Direct Method Calls:** Easier to implement initially, but leads to tight coupling.
- **REST APIs / gRPC:** Too heavy and slow for intra-process communication.
- **Redis Pub/Sub:** Adds an external dependency (Redis) which violates our goal of a lightweight V1 foundation.

## Why this approach
- **Decoupling:** Modules only know about the message schema, not about the existence of other modules.
- **Extensibility:** A new agent can be added by simply subscribing to existing events (e.g., `TradeExecuted`) without changing the core engine.
- **Traceability:** The Event Bus can store a local history of all messages, creating an easy audit trail.

## Consequences
- **Pros:** Zero circular dependencies; highly scalable for adding N number of agents; excellent separation of concerns.
- **Cons:** Flow of execution is harder to trace by simply reading the code top-to-bottom; debugging requires looking at the event history rather than stack traces.
