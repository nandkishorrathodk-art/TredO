# ADR 005: Agent Framework (V1)

## Problem
In V2, we will introduce autonomous, highly capable LLM-backed agents (Market, Research, CEO). If we start building intelligence without a standardized lifecycle and communication protocol, agents will become difficult to manage, start/stop cleanly, or monitor for health.

## Decision
We built a strict, dumb Agent Framework foundation (`BaseAgent`, `Lifecycle`, `AgentManager`) before adding any AI intelligence. Agents must adhere to a strict state machine (`CREATED` → `INITIALIZED` → `RUNNING` → `PAUSED` / `STOPPED` / `FAILED`).

## Alternatives Considered
- **LangGraph / AutoGen / CrewAI:** Popular agent frameworks. (Rejected: They dictate heavily how agents reason and interact, are often bloated, and make it very difficult to integrate with our strict deterministic Risk Engine and strict UI requirements).
- **Direct Orchestration:** Writing custom scripts to run specific agents. (Rejected: Not scalable when the number of agents grows).

## Why this approach
- **Total Control:** We own the lifecycle. We can easily pause all agents, kill them via a Kill Switch, or monitor their exact state.
- **Infrastructure First:** By building dummy agents (EchoAgent, LoggerAgent) first, we verified the underlying Event Bus communication without the unpredictability of LLM responses.
- **Standardization:** Every future AI agent will inherit from `BaseAgent`, guaranteeing they plug perfectly into the system and the UI dashboard.

## Consequences
- **Pros:** Highly predictable system behavior; easy to build UI dashboards that track agent states; prevents rogue agents from continuing to operate after a shutdown command.
- **Cons:** Requires boilerplate (subscribing to events, handling state) for simple tasks that might otherwise be a single script.
