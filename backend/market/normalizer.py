"""
TREDO — Market Scanner Normalizers
Translates exchange-specific JSON into canonical MarketEvents.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from backend.market.events import (
    CandleEvent,
    MarketEvent,
    TickerEvent,
    TradeEvent,
)

logger = logging.getLogger(__name__)


class BaseNormalizer(ABC):
    """Abstract base class for all exchange normalizers."""
    
    @abstractmethod
    def normalize(self, raw_data: str) -> MarketEvent | None:
        """Parse raw JSON string and return canonical MarketEvent."""
        pass


class BinanceNormalizer(BaseNormalizer):
    """Translates Binance WebSocket JSON to TREDO canonical events."""
    
    def normalize(self, raw_data: str) -> MarketEvent | None:
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.error("BinanceNormalizer: Invalid JSON received")
            return None

        # Handle subscription responses / errors
        if "result" in data and "id" in data:
            return None

        event_type = data.get("e")
        if not event_type:
            return None

        receive_time = int(time.time() * 1000)

        # 1. Ticker
        if event_type == "24hrTicker":
            return TickerEvent(
                exchange="binance",
                symbol=self._format_symbol(data.get("s", "")),
                timestamp=int(data.get("E", 0)),
                receive_time=receive_time,
                last_price=float(data.get("c", 0.0)),
                best_bid=float(data.get("b", 0.0)),
                best_ask=float(data.get("a", 0.0)),
                volume_base=float(data.get("v", 0.0)),
                volume_quote=float(data.get("q", 0.0)),
                price_change_pct=float(data.get("P", 0.0)),
                source="binance_scanner",
            )

        # 2. Trade
        if event_type == "trade":
            return TradeEvent(
                exchange="binance",
                symbol=self._format_symbol(data.get("s", "")),
                timestamp=int(data.get("E", 0)),
                receive_time=receive_time,
                trade_id=str(data.get("t", "")),
                price=float(data.get("p", 0.0)),
                amount=float(data.get("q", 0.0)),
                side="sell" if data.get("m", False) else "buy",
                source="binance_scanner",
            )

        # 3. Candle (Kline)
        if event_type == "kline":
            k = data.get("k", {})
            return CandleEvent(
                exchange="binance",
                symbol=self._format_symbol(data.get("s", "")),
                timestamp=int(data.get("E", 0)),
                receive_time=receive_time,
                timeframe=k.get("i", "1m"),
                is_closed=bool(k.get("x", False)),
                open_price=float(k.get("o", 0.0)),
                high_price=float(k.get("h", 0.0)),
                low_price=float(k.get("l", 0.0)),
                close_price=float(k.get("c", 0.0)),
                volume=float(k.get("v", 0.0)),
                source="binance_scanner",
            )

        return None

    def _format_symbol(self, raw_symbol: str) -> str:
        """Basic normalizer for BTCUSDT -> BTC/USDT"""
        if raw_symbol.endswith("USDT"):
            return raw_symbol[:-4] + "/USDT"
        return raw_symbol
