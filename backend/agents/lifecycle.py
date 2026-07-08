"""
TREDO — Agent Lifecycle
State machine for agent lifecycle management.

States:
    CREATED → INITIALIZED → RUNNING → PAUSED → STOPPED
                                ↓
                              FAILED

Valid transitions:
    CREATED     → INITIALIZED (after setup)
    INITIALIZED → RUNNING     (after start)
    RUNNING     → PAUSED      (user/system pause)
    RUNNING     → STOPPED     (graceful stop)
    RUNNING     → FAILED      (error)
    PAUSED      → RUNNING     (resume)
    PAUSED      → STOPPED     (stop while paused)
    FAILED      → INITIALIZED (restart attempt)
"""

from __future__ import annotations

from enum import Enum


class AgentState(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


# Valid state transitions
TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CREATED: {AgentState.INITIALIZED, AgentState.FAILED},
    AgentState.INITIALIZED: {AgentState.RUNNING, AgentState.FAILED},
    AgentState.RUNNING: {AgentState.PAUSED, AgentState.STOPPED, AgentState.FAILED},
    AgentState.PAUSED: {AgentState.RUNNING, AgentState.STOPPED},
    AgentState.FAILED: {AgentState.INITIALIZED},
    AgentState.STOPPED: set(),
}


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""


class Lifecycle:
    """
    Agent state machine.
    Enforces valid state transitions.
    """

    def __init__(self) -> None:
        self._state = AgentState.CREATED
        self._history: list[AgentState] = [AgentState.CREATED]
        self._error: str | None = None

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def is_running(self) -> bool:
        return self._state == AgentState.RUNNING

    @property
    def is_active(self) -> bool:
        return self._state in (AgentState.RUNNING, AgentState.PAUSED)

    def transition(self, new_state: AgentState, error: str | None = None) -> None:
        """
        Transition to a new state.
        Raises InvalidTransition if the transition is not allowed.
        """
        valid = TRANSITIONS.get(self._state, set())
        if new_state not in valid:
            raise InvalidTransition(
                f"Cannot transition from {self._state.value} to {new_state.value}. "
                f"Valid: {', '.join(s.value for s in valid) or 'none'}"
            )
        self._state = new_state
        self._history.append(new_state)
        if new_state == AgentState.FAILED:
            self._error = error
        elif new_state == AgentState.INITIALIZED:
            self._error = None

    def get_history(self) -> list[str]:
        """Get state transition history."""
        return [s.value for s in self._history]
