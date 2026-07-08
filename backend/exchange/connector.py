"""
TREDO — Exchange Connector
Unified interface to crypto exchanges via CCXT.
Supports paper trading (testnet) and live trading.

Features:
- Connect to any CCXT-supported exchange
- Fetch ticker, orderbook, OHLCV candles
- Place, cancel, and track orders
- Paper trading via exchange testnet
- Rate limiting and error handling built-in
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import ccxt.async_support as ccxt

from backend.config.settings import Settings, TradingMode

logger = logging.getLogger(__name__)


class ExchangeError(Exception):
    """Raised when an exchange operation fails."""


class ExchangeConnector:
    """
    Async exchange connector wrapping CCXT.

    Usage:
        connector = ExchangeConnector(settings)
        await connector.connect()

        ticker = await connector.get_ticker("BTC/USDT")
        print(ticker["last"])  # Current price

        candles = await connector.get_candles("BTC/USDT", "1h", limit=100)

        order = await connector.place_order(
            symbol="BTC/USDT", side="buy", amount=0.001
        )

        await connector.disconnect()
    """

    def __init__(self, config: Settings) -> None:
        self._config = config
        self._exchange: ccxt.Exchange | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def is_paper(self) -> bool:
        return self._config.mode == TradingMode.PAPER

    @property
    def exchange_name(self) -> str:
        return self._config.exchange_id

    async def connect(self) -> None:
        """Initialize connection to the exchange."""
        exchange_class = getattr(ccxt, self._config.exchange_id, None)
        if exchange_class is None:
            raise ExchangeError(
                f"Exchange '{self._config.exchange_id}' not supported by CCXT"
            )

        params: dict[str, Any] = {
            "enableRateLimit": self._config.exchange_rate_limit,
            "timeout": self._config.exchange_timeout_ms,
        }

        # Add API keys only if provided
        if self._config.exchange_api_key:
            params["apiKey"] = self._config.exchange_api_key
            params["secret"] = self._config.exchange_api_secret

        self._exchange = exchange_class(params)

        # Use testnet if paper trading
        if self._config.exchange_testnet:
            self._exchange.set_sandbox_mode(True)

        try:
            await self._exchange.load_markets()
            self._connected = True
            mode = "TESTNET" if self._config.exchange_testnet else "LIVE"
            logger.info(
                "Connected to %s (%s) — %d markets loaded",
                self._config.exchange_id.upper(),
                mode,
                len(self._exchange.markets),
            )
        except Exception as e:
            self._connected = False
            raise ExchangeError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """Close the exchange connection and free resources."""
        if self._exchange:
            await self._exchange.close()
            self._connected = False
            logger.info("Disconnected from %s", self._config.exchange_id.upper())

    def _require_connection(self) -> ccxt.Exchange:
        """Raise if not connected, otherwise return the exchange instance."""
        if not self._connected or self._exchange is None:
            raise ExchangeError("Not connected. Call connect() first.")
        return self._exchange

    # ── Market Data ──────────────────────────────────────────

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Get current ticker for a symbol.

        Returns dict with keys: symbol, last, bid, ask, high, low,
        volume, timestamp, datetime.
        """
        exchange = self._require_connection()
        try:
            raw = await exchange.fetch_ticker(symbol)
            return {
                "symbol": raw["symbol"],
                "last": raw["last"],
                "bid": raw["bid"],
                "ask": raw["ask"],
                "high": raw["high"],
                "low": raw["low"],
                "volume": raw["baseVolume"],
                "quote_volume": raw["quoteVolume"],
                "change_pct": raw.get("percentage"),
                "timestamp": raw["timestamp"],
                "datetime": raw["datetime"],
            }
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch ticker for {symbol}: {e}") from e

    async def get_tickers(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """Get tickers for multiple symbols. If None, uses watched_symbols."""
        targets = symbols or list(self._config.watched_symbols)
        tasks = [self.get_ticker(s) for s in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tickers = {}
        for symbol, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.warning("Failed to fetch %s: %s", symbol, result)
            else:
                tickers[symbol] = result
        return tickers

    async def get_orderbook(
        self, symbol: str, limit: int = 20
    ) -> dict[str, Any]:
        """
        Get order book for a symbol.

        Returns dict with: bids (list of [price, amount]),
        asks (list of [price, amount]), timestamp.
        """
        exchange = self._require_connection()
        try:
            raw = await exchange.fetch_order_book(symbol, limit=limit)
            return {
                "symbol": symbol,
                "bids": raw["bids"][:limit],
                "asks": raw["asks"][:limit],
                "timestamp": raw.get("timestamp"),
                "bid_total": sum(b[1] for b in raw["bids"][:limit]),
                "ask_total": sum(a[1] for a in raw["asks"][:limit]),
            }
        except ccxt.BaseError as e:
            raise ExchangeError(
                f"Failed to fetch orderbook for {symbol}: {e}"
            ) from e

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get OHLCV candles.

        Args:
            symbol: Trading pair (e.g. "BTC/USDT")
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "4h", "1d")
            limit: Number of candles (max varies by exchange)
            since: Start timestamp in ms (optional)

        Returns list of dicts with: timestamp, open, high, low, close, volume.
        """
        exchange = self._require_connection()
        try:
            raw = await exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=limit, since=since
            )
            return [
                {
                    "timestamp": c[0],
                    "datetime": datetime.fromtimestamp(
                        c[0] / 1000, tz=timezone.utc
                    ).isoformat(),
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5],
                }
                for c in raw
            ]
        except ccxt.BaseError as e:
            raise ExchangeError(
                f"Failed to fetch candles for {symbol}: {e}"
            ) from e

    # ── Trading ──────────────────────────────────────────────

    async def get_balance(self) -> dict[str, Any]:
        """
        Get account balances.

        Returns dict with: total (all assets), free (available),
        used (in orders).
        """
        exchange = self._require_connection()
        try:
            raw = await exchange.fetch_balance()
            # Filter out zero balances
            non_zero = {
                asset: {
                    "free": raw["free"].get(asset, 0),
                    "used": raw["used"].get(asset, 0),
                    "total": raw["total"].get(asset, 0),
                }
                for asset in raw["total"]
                if raw["total"][asset] and raw["total"][asset] > 0
            }
            return non_zero
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch balance: {e}") from e

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Place an order on the exchange.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Quantity in base currency
            order_type: "market" or "limit"
            price: Required for limit orders

        Returns dict with: id, symbol, side, type, amount, price, status, timestamp.
        """
        exchange = self._require_connection()

        if side not in ("buy", "sell"):
            raise ExchangeError(f"Invalid side: {side}. Must be 'buy' or 'sell'")

        if order_type == "limit" and price is None:
            raise ExchangeError("Price required for limit orders")

        try:
            raw = await exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
            )
            order = {
                "id": raw["id"],
                "symbol": raw["symbol"],
                "side": raw["side"],
                "type": raw["type"],
                "amount": raw["amount"],
                "price": raw.get("price") or raw.get("average"),
                "cost": raw.get("cost"),
                "filled": raw.get("filled"),
                "status": raw["status"],
                "timestamp": raw["timestamp"],
            }
            logger.info(
                "Order placed: %s %s %s @ %s — ID: %s",
                side.upper(),
                amount,
                symbol,
                order["price"],
                order["id"],
            )
            return order
        except ccxt.InsufficientFunds as e:
            raise ExchangeError(f"Insufficient funds: {e}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to place order: {e}") from e

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an open order by ID."""
        exchange = self._require_connection()
        try:
            raw = await exchange.cancel_order(order_id, symbol)
            logger.info("Order cancelled: %s", order_id)
            return {"id": raw["id"], "status": raw.get("status", "cancelled")}
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to cancel order {order_id}: {e}") from e

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol."""
        exchange = self._require_connection()
        try:
            raw = await exchange.fetch_open_orders(symbol)
            return [
                {
                    "id": o["id"],
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "type": o["type"],
                    "amount": o["amount"],
                    "price": o["price"],
                    "filled": o.get("filled"),
                    "status": o["status"],
                    "timestamp": o["timestamp"],
                }
                for o in raw
            ]
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch open orders: {e}") from e

    # ── Utility ──────────────────────────────────────────────

    def get_supported_timeframes(self) -> list[str]:
        """Return list of supported candle timeframes for this exchange."""
        exchange = self._require_connection()
        return list(exchange.timeframes.keys()) if exchange.timeframes else []

    def get_market_info(self, symbol: str) -> dict[str, Any] | None:
        """Get market info (min order size, price precision, etc.)."""
        exchange = self._require_connection()
        market = exchange.market(symbol)
        if not market:
            return None
        return {
            "symbol": market["symbol"],
            "base": market["base"],
            "quote": market["quote"],
            "active": market["active"],
            "min_amount": market.get("limits", {}).get("amount", {}).get("min"),
            "min_cost": market.get("limits", {}).get("cost", {}).get("min"),
            "price_precision": market.get("precision", {}).get("price"),
            "amount_precision": market.get("precision", {}).get("amount"),
        }

    def get_status(self) -> dict[str, Any]:
        """Get connector status for dashboard display."""
        return {
            "connected": self._connected,
            "exchange": self._config.exchange_id,
            "testnet": self._config.exchange_testnet,
            "mode": self._config.mode.value,
            "markets_loaded": (
                len(self._exchange.markets) if self._exchange and self._connected else 0
            ),
        }
