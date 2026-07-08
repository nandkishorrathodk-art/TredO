"""
TREDO — Market Scanner Core
Connects to exchanges, manages websockets, normalizes data, and publishes to Event Bus.
"""

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from backend.core.event_bus import EventBus
from backend.market.cache import MarketCache
from backend.market.events import ConnectionEvent, MarketEvent
from backend.market.normalizer import BinanceNormalizer
from backend.market.subscriptions import SubscriptionManager

logger = logging.getLogger(__name__)


class MarketScanner:
    """
    Ingests live data from exchanges via WebSocket.
    Does NOT calculate indicators. Pure translation layer.
    """
    def __init__(self, bus: EventBus):
        self._bus = bus
        self.cache = MarketCache()
        self.subs = SubscriptionManager()
        self.normalizer = BinanceNormalizer()
        
        self._running = False
        self._ws_task: asyncio.Task | None = None
        
        # We only support Binance WS in V2.1
        self._binance_url = "wss://stream.binance.com:9443/ws"

    async def start(self) -> None:
        """Start the scanner and connection loops."""
        if self._running:
            return
            
        self._running = True
        self._ws_task = asyncio.create_task(self._connection_loop())
        logger.info("Market Scanner started")

    async def stop(self) -> None:
        """Stop the scanner cleanly."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("Market Scanner stopped")

    async def subscribe(self, symbol: str, stream_type: str) -> None:
        """
        Request a subscription (e.g. 'BTC/USDT', 'ticker').
        Scanner will reconnect if necessary to apply it.
        """
        self.subs.subscribe("binance", stream_type, symbol)
        # In a real dynamic system, we'd send a live subscribe command via WS.
        # For simplicity, if we are running, we'll force a reconnect to pick it up.
        # But this is just a naive approach for V2.1.
        if self._running and self._ws_task:
            self._ws_task.cancel()

    async def _connection_loop(self) -> None:
        """Maintains the websocket connection with exponential backoff."""
        backoff = 1.0
        max_backoff = 30.0

        while self._running:
            try:
                payload = self.subs.get_binance_payload()
                if not payload:
                    # No active subs, wait before checking again
                    await asyncio.sleep(1.0)
                    continue

                await self._bus.publish(ConnectionEvent(
                    exchange="binance",
                    status="connecting",
                    message="Connecting to Binance WS",
                    source="scanner"
                ))

                async with websockets.connect(self._binance_url) as ws:
                    logger.info("Connected to Binance WS")
                    await self._bus.publish(ConnectionEvent(
                        exchange="binance",
                        status="connected",
                        message="Connected successfully",
                        source="scanner"
                    ))
                    
                    # Reset backoff on success
                    backoff = 1.0
                    
                    # Subscribe
                    await ws.send(json.dumps(payload))
                    
                    # Read loop
                    async for message in ws:
                        if not self._running:
                            break
                        
                        await self._process_message(message)

            except ConnectionClosed as e:
                logger.warning("Binance WS Closed: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Binance WS Error: %s", e)
            
            if not self._running:
                break
                
            await self._bus.publish(ConnectionEvent(
                exchange="binance",
                status="disconnected",
                reconnect_attempts=int(backoff),
                message=f"Reconnecting in {backoff}s",
                source="scanner"
            ))
            
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    async def _process_message(self, raw_message: str | bytes) -> None:
        """Normalize, cache, and publish."""
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8")
            
        event = self.normalizer.normalize(raw_message)
        if not event:
            return
            
        # OOO check is inside Cache. Update returns None if we shouldn't process it.
        # But wait, cache.update() doesn't return anything. We should check cache manually.
        
        event_type = type(event).__name__
        existing = self.cache.get_latest(event.exchange, event.symbol, event_type)
        if existing and existing.timestamp > event.timestamp:
            # Drop out-of-order stale data
            return
            
        self.cache.update(event)
        await self._bus.publish(event)
