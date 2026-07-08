"""
TREDO — Replay Engine Tests
Validates the historical streaming engine, including clock timing, multi-symbol sorting, and pausing.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from backend.core.event_bus import EventBus
from backend.market.events import CandleEvent
from backend.replay.models import BaseReplaySource
from backend.replay.sources import MemoryReplaySource, CSVReplaySource
from backend.replay.clock import ReplayClock
from backend.replay.controller import ReplayController


# ── Clock Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_clock_zero_speed():
    clock = ReplayClock(speed_multiplier=0.0)
    from unittest.mock import AsyncMock
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await clock.wait_for(1000)
        # 0.0 speed calls await asyncio.sleep(0) exactly once
        mock_sleep.assert_called_with(0)

@pytest.mark.asyncio
async def test_replay_clock_normal_speed():
    clock = ReplayClock(speed_multiplier=1.0)
    
    # First call sets the baseline
    with patch("time.monotonic", return_value=100.0):
        await clock.wait_for(1000)
        assert clock._last_event_time == 1000
        
    # Second call calculates diff
    # event diff = 1000ms = 1s
    # target real time = 1s
    # elapsed = 0s
    # sleep = 1s
    with patch("time.monotonic", return_value=100.0):
        with patch("asyncio.sleep") as mock_sleep:
            # Need to mock the pause loop checking to not block forever
            async def fast_sleep(*args, **kwargs):
                pass
            mock_sleep.side_effect = fast_sleep
            
            await clock.wait_for(2000)
            
            # Since sleep chunk is 0.1, it should have slept multiple times, but 
            # with fast_sleep it will loop until sleep_needed <= 0.
            # We just want to ensure sleep was called
            assert mock_sleep.called


# ── Multi-Symbol Sorting ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_multi_symbol_sorting():
    bus = EventBus()
    
    # Source 1: BTC
    src_btc = MemoryReplaySource([
        CandleEvent(symbol="BTC/USDT", timestamp=1000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True),
        CandleEvent(symbol="BTC/USDT", timestamp=3000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True)
    ])
    
    # Source 2: ETH
    src_eth = MemoryReplaySource([
        CandleEvent(symbol="ETH/USDT", timestamp=2000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True),
        CandleEvent(symbol="ETH/USDT", timestamp=4000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True)
    ])
    
    controller = ReplayController(bus, [src_btc, src_eth], speed_multiplier=0.0) # max speed
    
    events = []
    async def capture(evt: CandleEvent):
        events.append(evt)
    bus.subscribe(CandleEvent, capture)
    
    controller.play()
    
    # Wait for completion
    while controller._is_running:
        await asyncio.sleep(0.01)
        
    assert len(events) == 4
    # Ensure strict chronological order
    assert events[0].timestamp == 1000
    assert events[0].symbol == "BTC/USDT"
    
    assert events[1].timestamp == 2000
    assert events[1].symbol == "ETH/USDT"
    
    assert events[2].timestamp == 3000
    assert events[2].symbol == "BTC/USDT"
    
    assert events[3].timestamp == 4000
    assert events[3].symbol == "ETH/USDT"


# ── Pausing & Stepping ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_pause_and_step():
    bus = EventBus()
    
    src = MemoryReplaySource([
        CandleEvent(symbol="BTC/USDT", timestamp=1000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True),
        CandleEvent(symbol="BTC/USDT", timestamp=2000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True),
        CandleEvent(symbol="BTC/USDT", timestamp=3000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True)
    ])
    
    controller = ReplayController(bus, [src], speed_multiplier=0.0)
    
    events = []
    async def capture(evt: CandleEvent):
        events.append(evt)
    bus.subscribe(CandleEvent, capture)
    
    # Step 1
    controller.step()
    await asyncio.sleep(0.2)
    assert len(events) == 1
    assert events[0].timestamp == 1000
    assert controller.clock._paused == True
    
    # Step 2
    controller.step()
    await asyncio.sleep(0.2)
    assert len(events) == 2
    assert events[1].timestamp == 2000
    assert controller.clock._paused == True
    
    # Play remaining
    controller.play()
    await asyncio.sleep(0.2)
    assert len(events) == 3
    assert not controller._is_running


@pytest.mark.asyncio
async def test_replay_stop():
    bus = EventBus()
    
    src = MemoryReplaySource([
        CandleEvent(symbol="BTC/USDT", timestamp=1000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True),
        CandleEvent(symbol="BTC/USDT", timestamp=2000, open_price=1, high_price=1, low_price=1, close_price=1, volume=1, is_closed=True)
    ])
    
    controller = ReplayController(bus, [src], speed_multiplier=0.0)
    controller.pause()  # start paused
    controller.play()
    controller.stop()   # immediately stop
    try:
        if controller._task:
            await controller._task
    except asyncio.CancelledError:
        pass
    
    assert not controller._is_running
    assert not controller.clock._paused


# ── CSV Source Error handling ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_source_error():
    # File doesn't exist
    src = CSVReplaySource("BTC/USDT", "non_existent.csv")
    events = []
    async for c in src.get_candles():
        events.append(c)
        
    assert len(events) == 0  # Should catch error and yield nothing, without crashing
