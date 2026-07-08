"""
TREDO — Task Scheduler
Simple async scheduler for recurring tasks.
Used for periodic market scans, portfolio checks, risk resets.

Usage:
    scheduler = Scheduler()

    scheduler.add("market_scan", interval_s=1, callback=scan_market)
    scheduler.add("portfolio_check", interval_s=60, callback=check_portfolio)
    scheduler.add("daily_reset", interval_s=86400, callback=daily_reset)

    await scheduler.start()   # starts all tasks
    await scheduler.stop()    # stops all tasks
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

AsyncCallback = Callable[[], Coroutine[Any, Any, None]]


@dataclass
class ScheduledTask:
    """A recurring task definition."""
    name: str
    interval_s: float
    callback: AsyncCallback
    enabled: bool = True
    run_count: int = 0
    last_error: str | None = None
    _task: asyncio.Task[None] | None = None


class Scheduler:
    """
    Async task scheduler. Runs callbacks at specified intervals.
    All tasks run concurrently as asyncio tasks.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def add(
        self,
        name: str,
        interval_s: float,
        callback: AsyncCallback,
        enabled: bool = True,
    ) -> None:
        """Register a recurring task."""
        if name in self._tasks:
            logger.warning("Task '%s' already exists — replacing", name)
        self._tasks[name] = ScheduledTask(
            name=name, interval_s=interval_s,
            callback=callback, enabled=enabled,
        )
        logger.info("Scheduled task: %s (every %.1fs)", name, interval_s)

    def remove(self, name: str) -> None:
        """Remove a scheduled task."""
        task = self._tasks.pop(name, None)
        if task and task._task:
            task._task.cancel()
        logger.info("Removed task: %s", name)

    def enable(self, name: str) -> None:
        """Enable a disabled task."""
        if name in self._tasks:
            self._tasks[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a task without removing it."""
        if name in self._tasks:
            self._tasks[name].enabled = False

    async def start(self) -> None:
        """Start all scheduled tasks."""
        self._running = True
        for name, task in self._tasks.items():
            if task.enabled:
                task._task = asyncio.create_task(
                    self._run_loop(task),
                    name=f"scheduler:{name}",
                )
        logger.info(
            "Scheduler started — %d tasks",
            sum(1 for t in self._tasks.values() if t.enabled),
        )

    async def stop(self) -> None:
        """Stop all scheduled tasks."""
        self._running = False
        for task in self._tasks.values():
            if task._task and not task._task.done():
                task._task.cancel()
                try:
                    await task._task
                except asyncio.CancelledError:
                    pass
        logger.info("Scheduler stopped")

    async def run_once(self, name: str) -> None:
        """Run a task once immediately (useful for testing)."""
        task = self._tasks.get(name)
        if task is None:
            raise KeyError(f"Task '{name}' not found")
        await self._execute(task)

    async def _run_loop(self, task: ScheduledTask) -> None:
        """Internal loop that runs a task at its interval."""
        while self._running and task.enabled:
            try:
                await asyncio.sleep(task.interval_s)
                if self._running and task.enabled:
                    await self._execute(task)
            except asyncio.CancelledError:
                break

    async def _execute(self, task: ScheduledTask) -> None:
        """Execute a single task with error handling."""
        try:
            await task.callback()
            task.run_count += 1
            task.last_error = None
        except Exception as e:
            task.last_error = str(e)
            logger.error("Task '%s' failed: %s", task.name, e)

    def list_tasks(self) -> list[str]:
        """List all task names."""
        return sorted(self._tasks.keys())

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all scheduled tasks."""
        return {
            name: {
                "interval_s": t.interval_s,
                "enabled": t.enabled,
                "run_count": t.run_count,
                "last_error": t.last_error,
                "running": t._task is not None and not t._task.done() if t._task else False,
            }
            for name, t in self._tasks.items()
        }
