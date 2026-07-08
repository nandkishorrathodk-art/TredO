"""
TREDO — Exchange Connector Tests
Tests the CCXT exchange connector with mocked exchange responses.
No real API calls — all exchange methods are mocked.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config.settings import Settings, TradingMode
from backend.exchange.connector import ExchangeConnector, ExchangeError


@pytest.fixture
def paper_settings() -> Settings:
    """Create test settings for paper trading."""
    return Settings(
        exchange_id="binance",
        exchange_testnet=True,
        mode=TradingMode.PAPER,
        initial_capital=10000.0,
    )


@pytest.fixture
def mock_exchange():
    """Create a mock CCXT exchange instance."""
    exchange = AsyncMock()
    exchange.markets = {"BTC/USDT": {}, "ETH/USDT": {}}
    exchange.timeframes = {"1m": "1m", "5m": "5m", "1h": "1h", "1d": "1d"}
    exchange.market = MagicMock(return_value={
        "symbol": "BTC/USDT",
        "base": "BTC",
        "quote": "USDT",
        "active": True,
        "limits": {
            "amount": {"min": 0.00001},
            "cost": {"min": 10.0},
        },
        "precision": {"price": 2, "amount": 5},
    })
    return exchange


@pytest.fixture
def connector(paper_settings, mock_exchange):
    """Create a connector with a mocked exchange already connected."""
    conn = ExchangeConnector(paper_settings)
    conn._exchange = mock_exchange
    conn._connected = True
    return conn


# ── Connection Tests ─────────────────────────────────────


class TestConnection:
    def test_initial_state(self, paper_settings):
        conn = ExchangeConnector(paper_settings)
        assert conn.connected is False
        assert conn.is_paper is True
        assert conn.exchange_name == "binance"

    @pytest.mark.asyncio
    async def test_connect_success(self, paper_settings):
        with patch("backend.exchange.connector.ccxt") as mock_ccxt:
            mock_ex = AsyncMock()
            mock_ex.markets = {"BTC/USDT": {}}
            mock_ccxt.binance = MagicMock(return_value=mock_ex)

            conn = ExchangeConnector(paper_settings)
            await conn.connect()

            assert conn.connected is True
            mock_ex.set_sandbox_mode.assert_called_once_with(True)
            mock_ex.load_markets.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_invalid_exchange(self, paper_settings):
        paper_settings.exchange_id = "fake_exchange_xyz"
        conn = ExchangeConnector(paper_settings)
        with pytest.raises(ExchangeError, match="not supported"):
            await conn.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, connector, mock_exchange):
        await connector.disconnect()
        assert connector.connected is False
        mock_exchange.close.assert_awaited_once()

    def test_require_connection_when_disconnected(self, paper_settings):
        conn = ExchangeConnector(paper_settings)
        with pytest.raises(ExchangeError, match="Not connected"):
            conn._require_connection()


# ── Market Data Tests ────────────────────────────────────


class TestMarketData:
    @pytest.mark.asyncio
    async def test_get_ticker(self, connector, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(return_value={
            "symbol": "BTC/USDT",
            "last": 71200.0,
            "bid": 71190.0,
            "ask": 71210.0,
            "high": 72000.0,
            "low": 70000.0,
            "baseVolume": 15000.0,
            "quoteVolume": 1068000000.0,
            "percentage": 1.5,
            "timestamp": 1720000000000,
            "datetime": "2026-07-08T12:00:00Z",
        })

        ticker = await connector.get_ticker("BTC/USDT")

        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] == 71200.0
        assert ticker["bid"] == 71190.0
        assert ticker["ask"] == 71210.0
        assert ticker["volume"] == 15000.0
        assert ticker["change_pct"] == 1.5

    @pytest.mark.asyncio
    async def test_get_tickers_multiple(self, connector, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(side_effect=[
            {
                "symbol": "BTC/USDT", "last": 71200.0, "bid": 71190.0,
                "ask": 71210.0, "high": 72000.0, "low": 70000.0,
                "baseVolume": 15000.0, "quoteVolume": 1e9,
                "percentage": 1.5, "timestamp": 1720000000000,
                "datetime": "2026-07-08T12:00:00Z",
            },
            {
                "symbol": "ETH/USDT", "last": 3800.0, "bid": 3799.0,
                "ask": 3801.0, "high": 3900.0, "low": 3700.0,
                "baseVolume": 50000.0, "quoteVolume": 1.9e8,
                "percentage": 2.1, "timestamp": 1720000000000,
                "datetime": "2026-07-08T12:00:00Z",
            },
        ])

        tickers = await connector.get_tickers(["BTC/USDT", "ETH/USDT"])

        assert len(tickers) == 2
        assert tickers["BTC/USDT"]["last"] == 71200.0
        assert tickers["ETH/USDT"]["last"] == 3800.0

    @pytest.mark.asyncio
    async def test_get_orderbook(self, connector, mock_exchange):
        mock_exchange.fetch_order_book = AsyncMock(return_value={
            "bids": [[71190.0, 1.5], [71180.0, 2.3], [71170.0, 0.8]],
            "asks": [[71210.0, 1.2], [71220.0, 3.1], [71230.0, 0.5]],
            "timestamp": 1720000000000,
        })

        ob = await connector.get_orderbook("BTC/USDT", limit=3)

        assert len(ob["bids"]) == 3
        assert len(ob["asks"]) == 3
        assert ob["bids"][0] == [71190.0, 1.5]
        assert ob["bid_total"] == pytest.approx(4.6)
        assert ob["ask_total"] == pytest.approx(4.8)

    @pytest.mark.asyncio
    async def test_get_candles(self, connector, mock_exchange):
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[
            [1720000000000, 71000.0, 71500.0, 70800.0, 71200.0, 500.0],
            [1720003600000, 71200.0, 71800.0, 71100.0, 71600.0, 450.0],
        ])

        candles = await connector.get_candles("BTC/USDT", "1h", limit=2)

        assert len(candles) == 2
        assert candles[0]["open"] == 71000.0
        assert candles[0]["close"] == 71200.0
        assert candles[0]["volume"] == 500.0
        assert "datetime" in candles[0]
        assert candles[1]["high"] == 71800.0


# ── Trading Tests ────────────────────────────────────────


class TestTrading:
    @pytest.mark.asyncio
    async def test_get_balance(self, connector, mock_exchange):
        mock_exchange.fetch_balance = AsyncMock(return_value={
            "total": {"USDT": 10000.0, "BTC": 0.15, "ETH": 0.0},
            "free": {"USDT": 8000.0, "BTC": 0.10, "ETH": 0.0},
            "used": {"USDT": 2000.0, "BTC": 0.05, "ETH": 0.0},
        })

        balance = await connector.get_balance()

        assert "USDT" in balance
        assert "BTC" in balance
        assert "ETH" not in balance  # Zero balance filtered out
        assert balance["USDT"]["free"] == 8000.0
        assert balance["BTC"]["total"] == 0.15

    @pytest.mark.asyncio
    async def test_place_market_order(self, connector, mock_exchange):
        mock_exchange.create_order = AsyncMock(return_value={
            "id": "order_123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "amount": 0.01,
            "price": None,
            "average": 71200.0,
            "cost": 712.0,
            "filled": 0.01,
            "status": "closed",
            "timestamp": 1720000000000,
        })

        order = await connector.place_order("BTC/USDT", "buy", 0.01)

        assert order["id"] == "order_123"
        assert order["side"] == "buy"
        assert order["price"] == 71200.0
        assert order["status"] == "closed"

    @pytest.mark.asyncio
    async def test_place_limit_order(self, connector, mock_exchange):
        mock_exchange.create_order = AsyncMock(return_value={
            "id": "order_456",
            "symbol": "BTC/USDT",
            "side": "sell",
            "type": "limit",
            "amount": 0.05,
            "price": 75000.0,
            "average": None,
            "cost": None,
            "filled": 0.0,
            "status": "open",
            "timestamp": 1720000000000,
        })

        order = await connector.place_order(
            "BTC/USDT", "sell", 0.05, order_type="limit", price=75000.0
        )

        assert order["type"] == "limit"
        assert order["price"] == 75000.0
        assert order["status"] == "open"

    @pytest.mark.asyncio
    async def test_place_limit_without_price_fails(self, connector):
        with pytest.raises(ExchangeError, match="Price required"):
            await connector.place_order(
                "BTC/USDT", "buy", 0.01, order_type="limit"
            )

    @pytest.mark.asyncio
    async def test_invalid_side_fails(self, connector):
        with pytest.raises(ExchangeError, match="Invalid side"):
            await connector.place_order("BTC/USDT", "short", 0.01)

    @pytest.mark.asyncio
    async def test_cancel_order(self, connector, mock_exchange):
        mock_exchange.cancel_order = AsyncMock(return_value={
            "id": "order_456",
            "status": "cancelled",
        })

        result = await connector.cancel_order("order_456", "BTC/USDT")
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_open_orders(self, connector, mock_exchange):
        mock_exchange.fetch_open_orders = AsyncMock(return_value=[
            {
                "id": "order_789",
                "symbol": "BTC/USDT",
                "side": "sell",
                "type": "limit",
                "amount": 0.1,
                "price": 80000.0,
                "filled": 0.0,
                "status": "open",
                "timestamp": 1720000000000,
            }
        ])

        orders = await connector.get_open_orders("BTC/USDT")
        assert len(orders) == 1
        assert orders[0]["price"] == 80000.0


# ── Utility Tests ────────────────────────────────────────


class TestUtility:
    def test_get_supported_timeframes(self, connector):
        tf = connector.get_supported_timeframes()
        assert "1h" in tf
        assert "1d" in tf

    def test_get_market_info(self, connector):
        info = connector.get_market_info("BTC/USDT")
        assert info["base"] == "BTC"
        assert info["quote"] == "USDT"
        assert info["min_amount"] == 0.00001

    def test_get_status(self, connector):
        status = connector.get_status()
        assert status["connected"] is True
        assert status["exchange"] == "binance"
        assert status["testnet"] is True
        assert status["mode"] == "paper"
        assert status["markets_loaded"] == 2
