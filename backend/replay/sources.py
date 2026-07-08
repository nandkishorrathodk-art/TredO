"""
TREDO — Replay Data Sources
Implementations for reading historical data.
"""

import csv
import logging
from typing import AsyncIterator

from backend.market.events import CandleEvent
from backend.replay.models import BaseReplaySource

logger = logging.getLogger(__name__)


class CSVReplaySource(BaseReplaySource):
    """
    Reads historical candles from a CSV file.
    Expected headers: timestamp, open, high, low, close, volume
    """
    def __init__(self, symbol: str, filepath: str, timeframe: str = "1m", exchange: str = "binance", market_type: str = "linear"):
        self.symbol = symbol
        self.filepath = filepath
        self.timeframe = timeframe
        self.exchange = exchange
        self.market_type = market_type

    async def get_candles(self, start_timestamp: int = 0, end_timestamp: int | None = None) -> AsyncIterator[CandleEvent]:
        try:
            with open(self.filepath, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = int(row["timestamp"])
                    if ts < start_timestamp:
                        continue
                    if end_timestamp and ts > end_timestamp:
                        break
                        
                    yield CandleEvent(
                        symbol=self.symbol,
                        exchange=self.exchange,
                        market_type=self.market_type,
                        timeframe=self.timeframe,
                        timestamp=ts,
                        open_price=float(row["open"]),
                        high_price=float(row["high"]),
                        low_price=float(row["low"]),
                        close_price=float(row["close"]),
                        volume=float(row["volume"]),
                        is_closed=True
                    )
        except Exception as e:
            logger.error("Failed to read CSV source %s: %s", self.filepath, e)


class MemoryReplaySource(BaseReplaySource):
    """
    Mock source for tests, initialized with a pre-loaded list of CandleEvents.
    Must be pre-sorted.
    """
    def __init__(self, candles: list[CandleEvent]):
        self.candles = candles

    async def get_candles(self, start_timestamp: int = 0, end_timestamp: int | None = None) -> AsyncIterator[CandleEvent]:
        for c in self.candles:
            if c.timestamp < start_timestamp:
                continue
            if end_timestamp and c.timestamp > end_timestamp:
                break
            yield c
