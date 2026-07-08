"""
TREDO — Application Settings
Loads configuration from environment variables with safe defaults.
All settings for exchange connectivity, API server, and trading mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass
class Settings:
    """Immutable application settings. Created once at startup."""

    # Identity
    app_name: str = "TREDO"
    version: str = "0.1.0"

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = Path(__file__).parent.parent.parent / "data"

    # Trading
    mode: TradingMode = TradingMode.PAPER
    default_symbol: str = "BTC/USDT"
    watched_symbols: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    initial_capital: float = 10000.0

    # Exchange
    exchange_id: str = "binance"
    exchange_api_key: str = ""
    exchange_api_secret: str = ""
    exchange_testnet: bool = True
    exchange_timeout_ms: int = 30000
    exchange_rate_limit: bool = True

    # API Server
    api_host: str = "127.0.0.1"
    api_port: int = 8420
    api_cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables with safe defaults."""
        return cls(
            mode=TradingMode(os.getenv("TREDO_MODE", "paper")),
            default_symbol=os.getenv("TREDO_SYMBOL", "BTC/USDT"),
            initial_capital=float(os.getenv("TREDO_CAPITAL", "10000")),
            exchange_id=os.getenv("TREDO_EXCHANGE", "binance"),
            exchange_api_key=os.getenv("TREDO_API_KEY", ""),
            exchange_api_secret=os.getenv("TREDO_API_SECRET", ""),
            exchange_testnet=os.getenv("TREDO_TESTNET", "true").lower() == "true",
            api_host=os.getenv("TREDO_HOST", "127.0.0.1"),
            api_port=int(os.getenv("TREDO_PORT", "8420")),
        )

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "trades").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)


# Singleton — import this everywhere
settings = Settings.from_env()
