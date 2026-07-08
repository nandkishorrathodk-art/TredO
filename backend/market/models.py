"""
TREDO — Market Scanner Models
Enums and basic data structures for the Market module.
"""

from enum import Enum


class MarketType(str, Enum):
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
