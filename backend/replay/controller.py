"""
TREDO — Replay Controller
Orchestrates data sources, clock, and publishing to the event bus.
"""

import asyncio
import logging
from typing import Sequence

from backend.core.event_bus import EventBus
from backend.market.events import CandleEvent
from backend.replay.models import BaseReplaySource
from backend.replay.clock import ReplayClock

logger = logging.getLogger(__name__)

class ReplayController:
    """
    Acts as the MarketScanner during backtesting.
    Emits CandleEvents precisely according to the ReplayClock.
    """
    def __init__(self, bus: EventBus, sources: Sequence[BaseReplaySource], speed_multiplier: float = 1.0):
        self._bus = bus
        self._sources = sources
        self.clock = ReplayClock(speed_multiplier)
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._stop_event = asyncio.Event()
        self._step_event = asyncio.Event()

    async def _run_loop(self):
        """Main replay loop."""
        try:
            # We need to multiplex all sources chronologically.
            # A simple approach for async streams: pull the next from all, pick earliest.
            # For simplicity, we assume we fetch all into memory or use an async merger.
            # Here we do a simple merger by requesting iterators.
            
            iterators = [src.get_candles() for src in self._sources]
            next_items: list[CandleEvent | None] = [None] * len(iterators)
            
            # Init first items
            for i, it in enumerate(iterators):
                try:
                    next_items[i] = await anext(it)
                except StopAsyncIteration:
                    next_items[i] = None

            while not self._stop_event.is_set():
                # Find earliest candle
                earliest_idx = -1
                earliest_ts = float('inf')
                
                for i, item in enumerate(next_items):
                    if item is not None and item.timestamp < earliest_ts:
                        earliest_ts = item.timestamp
                        earliest_idx = i
                        
                if earliest_idx == -1:
                    # All sources exhausted
                    logger.info("Replay complete. All sources exhausted.")
                    break
                    
                candle = next_items[earliest_idx]
                
                # 1. Wait according to clock
                await self.clock.wait_for(candle.timestamp)
                
                # 2. Publish
                await self._bus.publish(candle)
                
                # If stepping, pause immediately after publishing
                if self._step_event.is_set():
                    self.clock.pause()
                    self._step_event.clear()
                
                # 3. Advance the iterator that won
                try:
                    next_items[earliest_idx] = await anext(iterators[earliest_idx])
                except StopAsyncIteration:
                    next_items[earliest_idx] = None
                    
        except asyncio.CancelledError:
            logger.info("Replay loop cancelled.")
        except Exception as e:
            logger.error("Replay loop crashed: %s", e)
        finally:
            self._is_running = False
            self.clock.reset()

    # ── Controller API ───────────────────────────────────────────────

    def play(self):
        """Start or resume replay."""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._is_running = True
            self.clock.resume()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Replay started.")
        else:
            self.clock.resume()

    def pause(self):
        """Pause the replay."""
        self.clock.pause()

    def stop(self):
        """Stop and reset the replay."""
        self._stop_event.set()
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self.clock.reset()
        logger.info("Replay stopped.")

    def step(self):
        """Process exactly one candle then pause."""
        self._step_event.set()
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._is_running = True
            # Don't resume clock normally, step overrides pause for one tick
            self.clock.resume()
            self._task = asyncio.create_task(self._run_loop())
        else:
            self.clock.resume()

    def set_speed(self, multiplier: float):
        self.clock.set_speed(multiplier)
