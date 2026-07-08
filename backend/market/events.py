"""
TREDO — Market Scanner Events
Canonical schemas for normalized market data.
Every exchange payload is converted to one of these types.
"""

from dataclasses import dataclass
from backend.core.messages import BaseMessage


@dataclass
class MarketEvent(BaseMessage):
    """Base class for all normalized market data."""
    exchange: str = ""
    symbol: str = ""
    timestamp: int = 0
    receive_time: int = 0


@dataclass
class ConnectionEvent(MarketEvent):
    """WebSocket connection state changes."""
    status: str = "connected"  # connected, disconnected, error
    reconnect_attempts: int = 0
    message: str = ""


@dataclass
class TickerEvent(MarketEvent):
    """24hr rolling window ticker data."""
    last_price: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    volume_base: float = 0.0
    volume_quote: float = 0.0
    price_change_pct: float = 0.0


@dataclass
class CandleEvent(MarketEvent):
    """OHLCV data for a specific timeframe."""
    timeframe: str = "1m"
    is_closed: bool = False
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: float = 0.0


@dataclass
class TradeEvent(MarketEvent):
    """Individual public market trade."""
    trade_id: str = ""
    price: float = 0.0
    amount: float = 0.0
    side: str = "buy"


@dataclass
class OrderBookEvent(MarketEvent):
    """L2 Order book snapshot or update."""
    bids: list[tuple[float, float]] = None  # [(price, amount), ...]
    asks: list[tuple[float, float]] = None
    is_snapshot: bool = False

    def __post_init__(self):
        if self.bids is None:
            self.bids = []
        if self.asks is None:
            self.asks = []


@dataclass
class FundingEvent(MarketEvent):
    """Perpetual futures funding rate."""
    funding_rate: float = 0.0
    next_funding_time: int = 0


@dataclass
class OpenInterestEvent(MarketEvent):
    """Perpetual futures open interest."""
    open_interest: float = 0.0
    value_quote: float = 0.0
