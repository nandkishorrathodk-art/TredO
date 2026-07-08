"""
TREDO — Strategies Package
Loads and exposes all registered strategies for the engine.
"""

import backend.strategies.trend.ema_cross
import backend.strategies.momentum.rsi_reversion
import backend.strategies.volatility.bollinger_reversion

# Adding empty init makes it a valid python package,
# and these imports ensure that the classes register themselves 
# into the strategy_registry when the package is imported.
