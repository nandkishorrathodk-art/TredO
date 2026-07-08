"""
TREDO — Event Bus
Async pub/sub system for inter-module communication.
Modules publish and subscribe to message types — never call each other directly.

Usage:
    bus = EventBus()

    # Subscribe to a message type
    async def on_signal(msg: SignalGenerated):
        print(f"Got signal: {msg.symbol} {msg.side}")

    bus.subscribe(SignalGenerated, on_signal)

    # Publish a message — all subscribers get notified
    await bus.publish(SignalGenerated(symbol="BTC/USDT", side="buy"))

    # Unsubscribe
    bus.unsubscribe(SignalGenerated, on_signal)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from backend.core.messages import BaseMessage

logger = logging.getLogger(__name__)

# Type for async handler: takes a BaseMessage, returns None
Handler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async publish/subscribe event bus.
    All inter-module communication goes through here.
    No module should directly call another module's methods.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)
        self._history: list[BaseMessage] = []
        self._max_history: int = 1000

    def subscribe(self, message_type: type, handler: Handler) -> None:
        """
        Subscribe a handler to a message type.
        Handler must be an async function that accepts the message.
        """
        if handler not in self._handlers[message_type]:
            self._handlers[message_type].append(handler)
            logger.debug(
                "Subscribed %s to %s",
                handler.__qualname__, message_type.__name__,
            )

    def unsubscribe(self, message_type: type, handler: Handler) -> None:
        """Remove a handler from a message type."""
        handlers = self._handlers[message_type]
        if handler in handlers:
            handlers.remove(handler)
            logger.debug(
                "Unsubscribed %s from %s",
                handler.__qualname__, message_type.__name__,
            )

    async def publish(self, message: BaseMessage) -> int:
        """
        Publish a message to all subscribers of its type.
        Returns the number of handlers that were notified.

        Handlers are called concurrently via asyncio.gather.
        If a handler raises an exception, it's logged but doesn't
        affect other handlers.
        """
        msg_type = type(message)
        handlers = self._handlers.get(msg_type, [])

        # Store in history
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        if not handlers:
            logger.debug("No handlers for %s", msg_type.__name__)
            return 0

        # Run all handlers concurrently
        results = await asyncio.gather(
            *[self._safe_call(h, message) for h in handlers],
            return_exceptions=True,
        )

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Handler %s failed for %s: %s",
                    handlers[i].__qualname__, msg_type.__name__, result,
                )

        notified = sum(1 for r in results if not isinstance(r, Exception))
        logger.debug(
            "Published %s — %d/%d handlers notified",
            msg_type.__name__, notified, len(handlers),
        )
        return notified

    @staticmethod
    async def _safe_call(handler: Handler, message: BaseMessage) -> None:
        """Call a handler, catching and re-raising exceptions for gather."""
        await handler(message)

    def subscriber_count(self, message_type: type) -> int:
        """Get number of subscribers for a message type."""
        return len(self._handlers.get(message_type, []))

    def get_history(self, message_type: type | None = None, limit: int = 50) -> list[BaseMessage]:
        """Get recent message history, optionally filtered by type."""
        if message_type:
            filtered = [m for m in self._history if isinstance(m, message_type)]
        else:
            filtered = self._history
        return filtered[-limit:]

    def clear_history(self) -> None:
        """Clear message history."""
        self._history.clear()

    def clear_all(self) -> None:
        """Remove all subscriptions and history."""
        self._handlers.clear()
        self._history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_subscriptions": sum(len(h) for h in self._handlers.values()),
            "message_types": len(self._handlers),
            "history_size": len(self._history),
            "types": {
                t.__name__: len(h)
                for t, h in self._handlers.items()
                if h
            },
        }
