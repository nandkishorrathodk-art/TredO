"""
TREDO — Market Scanner Subscriptions
Manages active topics/symbols across exchanges.
"""

from typing import Any


class SubscriptionManager:
    """
    Tracks which symbols and streams are currently requested.
    Generates payloads for WebSocket subscribe/unsubscribe commands.
    """
    def __init__(self):
        # exchange -> stream_type -> set of symbols
        # e.g. {"binance": {"ticker": {"BTC/USDT", "ETH/USDT"}}}
        self._subs: dict[str, dict[str, set[str]]] = {}

    def subscribe(self, exchange: str, stream_type: str, symbol: str) -> None:
        if exchange not in self._subs:
            self._subs[exchange] = {}
        if stream_type not in self._subs[exchange]:
            self._subs[exchange][stream_type] = set()
        
        self._subs[exchange][stream_type].add(symbol)

    def unsubscribe(self, exchange: str, stream_type: str, symbol: str) -> None:
        if exchange in self._subs and stream_type in self._subs[exchange]:
            self._subs[exchange][stream_type].discard(symbol)

    def get_symbols(self, exchange: str, stream_type: str) -> list[str]:
        if exchange in self._subs and stream_type in self._subs[exchange]:
            return list(self._subs[exchange][stream_type])
        return []

    def get_binance_payload(self) -> dict[str, Any] | None:
        """
        Builds the raw Binance subscribe payload based on active subs.
        Binance uses streams like 'btcusdt@ticker'.
        """
        if "binance" not in self._subs:
            return None

        streams = []
        
        for stream_type, symbols in self._subs["binance"].items():
            for symbol in symbols:
                # normalize BTC/USDT -> btcusdt
                b_sym = symbol.replace("/", "").lower()
                if stream_type == "ticker":
                    streams.append(f"{b_sym}@ticker")
                elif stream_type == "trade":
                    streams.append(f"{b_sym}@trade")
                elif stream_type.startswith("kline_"):
                    # e.g. kline_1m
                    tf = stream_type.split("_")[1]
                    streams.append(f"{b_sym}@kline_{tf}")

        if not streams:
            return None

        return {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
