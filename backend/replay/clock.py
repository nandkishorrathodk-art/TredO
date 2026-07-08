"""
TREDO — Replay Clock
Controls the simulated progression of time.
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class ReplayClock:
    """
    Manages historical time delays.
    If speed = 1.0, 1 simulated second = 1 real second.
    If speed = 60.0, 1 simulated minute = 1 real second.
    If speed = 0.0, process as fast as the event loop allows (no sleep).
    """
    def __init__(self, speed_multiplier: float = 1.0):
        self.speed_multiplier = speed_multiplier
        self._last_event_time: int | None = None
        self._last_real_time: float | None = None
        self._paused = False

    def set_speed(self, speed: float):
        """Update speed dynamically."""
        self.speed_multiplier = max(0.0, speed)
        # Reset relative timers so speed change applies smoothly
        self._last_event_time = None
        self._last_real_time = None
        logger.info("Replay clock speed set to %sx", speed)

    def pause(self):
        self._paused = True
        logger.info("Replay clock paused.")

    def resume(self):
        self._paused = False
        self._last_event_time = None
        self._last_real_time = None
        logger.info("Replay clock resumed.")
        
    def reset(self):
        self._last_event_time = None
        self._last_real_time = None
        self._paused = False

    async def wait_for(self, event_timestamp: int):
        """
        Wait the appropriate real-world time until the simulated event_timestamp.
        event_timestamp is in milliseconds.
        """
        # Block if paused
        while self._paused:
            await asyncio.sleep(0.1)

        # Max speed, don't sleep at all, just yield control to event loop
        if self.speed_multiplier == 0.0:
            await asyncio.sleep(0)
            return

        now_real = time.monotonic()

        if self._last_event_time is None or self._last_real_time is None:
            self._last_event_time = event_timestamp
            self._last_real_time = now_real
            return

        # Calculate time diff in simulated seconds
        simulated_diff_seconds = (event_timestamp - self._last_event_time) / 1000.0
        
        if simulated_diff_seconds <= 0:
            return

        # Target real time to sleep
        real_diff_seconds = simulated_diff_seconds / self.speed_multiplier
        
        elapsed_real = now_real - self._last_real_time
        sleep_needed = real_diff_seconds - elapsed_real

        if sleep_needed > 0:
            # Sleep in chunks to allow pause/resume to interrupt
            chunk_size = 0.1
            while sleep_needed > 0:
                if self._paused:
                    # If paused during sleep, break out to the top pause loop (or just wait here)
                    while self._paused:
                        await asyncio.sleep(0.1)
                    # Reset timers because real time passed
                    self._last_event_time = event_timestamp
                    self._last_real_time = time.monotonic()
                    return

                sleep_chunk = min(sleep_needed, chunk_size)
                await asyncio.sleep(sleep_chunk)
                sleep_needed -= sleep_chunk

        self._last_event_time = event_timestamp
        self._last_real_time = time.monotonic()
