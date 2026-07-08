"""
TREDO — Replay Models
Data structures and interfaces for the Time Machine.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from backend.market.events import CandleEvent


class BaseReplaySource(ABC):
    """
    Abstract interface for all replay data sources (CSV, Parquet, DB, etc).
    A source must yield CandleEvents in strictly chronological order.
    """
    
    @abstractmethod
    async def get_candles(self, start_timestamp: int = 0, end_timestamp: int | None = None) -> AsyncIterator[CandleEvent]:
        """
        Yields historical CandleEvents.
        Must guarantee chronological order.
        """
        pass
        # async for candle in something:
        #     yield candle
