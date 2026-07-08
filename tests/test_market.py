"""
TREDO — Market Scanner Tests
Validates Binance JSON normalization, out-of-order rejection,
cache logic, subscriptions, and scanner websocket mock.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.core.event_bus import EventBus
from backend.market.cache import MarketCache
from backend.market.events import (
    CandleEvent,
    ConnectionEvent,
    MarketEvent,
    TickerEvent,
    TradeEvent,
)
from backend.market.normalizer import BinanceNormalizer
from backend.market.scanner import MarketScanner
from backend.market.subscriptions import SubscriptionManager


# ── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def scanner(bus):
    return MarketScanner(bus)


@pytest.fixture
def cache():
    return MarketCache()


@pytest.fixture
def normalizer():
    return BinanceNormalizer()


@pytest.fixture
def subs():
    return SubscriptionManager()


# ── Normalizer Tests ─────────────────────────────────────

class TestBinanceNormalizer:
    def test_invalid_json(self, normalizer):
        assert normalizer.normalize("NOT_JSON") is None

    def test_ignore_subscription_response(self, normalizer):
        payload = '{"result": null, "id": 1}'
        assert normalizer.normalize(payload) is None

    def test_normalize_ticker(self, normalizer):
        payload = json.dumps({
            "e": "24hrTicker",
            "E": 123456789,
            "s": "BTCUSDT",
            "c": "70000.50",
            "b": "70000.00",
            "a": "70001.00",
            "v": "100.5",
            "q": "7035050.25",
            "P": "1.5"
        })
        event = normalizer.normalize(payload)
        assert isinstance(event, TickerEvent)
        assert event.exchange == "binance"
        assert event.symbol == "BTC/USDT"
        assert event.timestamp == 123456789
        assert event.last_price == 70000.50
        assert event.price_change_pct == 1.5

    def test_normalize_trade(self, normalizer):
        payload = json.dumps({
            "e": "trade",
            "E": 123456799,
            "s": "ETHUSDT",
            "t": 98765,
            "p": "3500.25",
            "q": "1.5",
            "m": True
        })
        event = normalizer.normalize(payload)
        assert isinstance(event, TradeEvent)
        assert event.symbol == "ETH/USDT"
        assert event.price == 3500.25
        assert event.amount == 1.5
        assert event.side == "sell"  # m=True means market maker was buyer

    def test_normalize_kline(self, normalizer):
        payload = json.dumps({
            "e": "kline",
            "E": 123456800,
            "s": "SOLUSDT",
            "k": {
                "i": "1m",
                "x": True,
                "o": "100.0",
                "h": "105.0",
                "l": "99.0",
                "c": "104.0",
                "v": "500.0"
            }
        })
        event = normalizer.normalize(payload)
        assert isinstance(event, CandleEvent)
        assert event.symbol == "SOL/USDT"
        assert event.timeframe == "1m"
        assert event.is_closed is True
        assert event.open_price == 100.0
        assert event.close_price == 104.0


# ── Cache Tests ──────────────────────────────────────────

class TestMarketCache:
    def test_update_inserts_new(self, cache):
        event = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=100)
        cache.update(event)
        retrieved = cache.get_latest("binance", "BTC/USDT", "TickerEvent")
        assert retrieved == event

    def test_update_overwrites_older(self, cache):
        event1 = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=100, last_price=1.0)
        event2 = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=200, last_price=2.0)
        
        cache.update(event1)
        cache.update(event2)
        
        retrieved = cache.get_latest("binance", "BTC/USDT", "TickerEvent")
        assert retrieved.last_price == 2.0

    def test_update_ignores_out_of_order(self, cache):
        event_new = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=200, last_price=2.0)
        event_old = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=100, last_price=1.0)
        
        cache.update(event_new)
        cache.update(event_old)
        
        retrieved = cache.get_latest("binance", "BTC/USDT", "TickerEvent")
        # Should retain the newer timestamp
        assert retrieved.last_price == 2.0

    def test_clear_cache(self, cache):
        event = TickerEvent(exchange="binance", symbol="BTC/USDT", timestamp=100)
        cache.update(event)
        cache.clear()
        assert cache.get_latest("binance", "BTC/USDT", "TickerEvent") is None


# ── Subscription Manager Tests ───────────────────────────

class TestSubscriptions:
    def test_subscribe(self, subs):
        subs.subscribe("binance", "ticker", "BTC/USDT")
        assert "BTC/USDT" in subs.get_symbols("binance", "ticker")

    def test_unsubscribe(self, subs):
        subs.subscribe("binance", "ticker", "BTC/USDT")
        subs.unsubscribe("binance", "ticker", "BTC/USDT")
        assert "BTC/USDT" not in subs.get_symbols("binance", "ticker")

    def test_binance_payload_generation(self, subs):
        subs.subscribe("binance", "ticker", "BTC/USDT")
        subs.subscribe("binance", "kline_1m", "ETH/USDT")
        
        payload = subs.get_binance_payload()
        assert payload["method"] == "SUBSCRIBE"
        # The exact order in the list might vary due to set iteration, so we check inclusion
        assert "btcusdt@ticker" in payload["params"]
        assert "ethusdt@kline_1m" in payload["params"]

    def test_empty_payload(self, subs):
        assert subs.get_binance_payload() is None


# ── Scanner Integration Tests ────────────────────────────

class TestMarketScanner:
    @pytest.mark.asyncio
    async def test_process_message_publishes(self, scanner, bus):
        received = []
        async def on_event(msg):
            received.append(msg)
            
        bus.subscribe(TickerEvent, on_event)
        
        payload = json.dumps({
            "e": "24hrTicker",
            "E": 1000,
            "s": "BTCUSDT",
            "c": "70000.0"
        })
        
        await scanner._process_message(payload)
        
        assert len(received) == 1
        assert received[0].symbol == "BTC/USDT"
        
        # Verify cache was updated
        cached = scanner.cache.get_latest("binance", "BTC/USDT", "TickerEvent")
        assert cached is not None
        assert cached.last_price == 70000.0

    @pytest.mark.asyncio
    async def test_process_out_of_order_is_ignored(self, scanner, bus):
        """Older timestamps should not be published or cached."""
        received = []
        async def on_event(msg):
            received.append(msg)
            
        bus.subscribe(TickerEvent, on_event)
        
        # 1. Newest payload
        await scanner._process_message(json.dumps({
            "e": "24hrTicker", "E": 2000, "s": "BTCUSDT", "c": "70000.0"
        }))
        
        # 2. Older payload (arrived late)
        await scanner._process_message(json.dumps({
            "e": "24hrTicker", "E": 1000, "s": "BTCUSDT", "c": "69000.0"
        }))
        
        # Only the first one should be published
        assert len(received) == 1
        assert received[0].timestamp == 2000
        
        # Cache should retain newest
        assert scanner.cache.get_latest("binance", "BTC/USDT", "TickerEvent").timestamp == 2000

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, scanner):
        await scanner.start()
        assert scanner._running is True
        assert scanner._ws_task is not None
        
        await scanner.stop()
        assert scanner._running is False
        assert scanner._ws_task.done()

    @pytest.mark.asyncio
    async def test_subscribe_restarts_loop(self, scanner):
        await scanner.start()
        
        old_task = scanner._ws_task
        
        # Adding a sub should cancel the old task so it reconnects to get the new stream
        await scanner.subscribe("BTC/USDT", "ticker")
        
        await asyncio.sleep(0.01)
        assert old_task.cancelled() or old_task.done()
        
        await scanner.stop()
