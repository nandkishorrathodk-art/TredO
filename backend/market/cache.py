"""
TREDO — Market Scanner Cache
In-memory storage of the *latest snapshot* only.
No historical data is kept here.
"""

from typing import Any
from backend.market.events import MarketEvent


class MarketCache:
    """
    Stores the absolute latest snapshot for any symbol/event_type.
    Used by engines to ask "what is the current state" without waiting
    for the next WebSocket tick.
    """
    def __init__(self):
        # exchange -> symbol -> event_type -> MarketEvent
        self._store: dict[str, dict[str, dict[str, MarketEvent]]] = {}

    def update(self, event: MarketEvent) -> None:
        if event.exchange not in self._store:
            self._store[event.exchange] = {}
        if event.symbol not in self._store[event.exchange]:
            self._store[event.exchange][event.symbol] = {}
            
        event_type = type(event).__name__
        
        # OOO check (Strictly Monotonically Increasing Timestamp)
        existing = self._store[event.exchange][event.symbol].get(event_type)
        if existing and existing.timestamp > event.timestamp:
            return  # Ignore out-of-order stale data
            
        self._store[event.exchange][event.symbol][event_type] = event

    def get_latest(self, exchange: str, symbol: str, event_type: str) -> MarketEvent | None:
        try:
            return self._store[exchange][symbol][event_type]
        except KeyError:
            return None

    def clear(self) -> None:
        self._store.clear()
