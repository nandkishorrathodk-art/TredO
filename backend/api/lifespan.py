"""
TREDO — Application Lifespan
Startup and shutdown orchestration.
Creates all services, registers them, wires up Event Bus,
and tears everything down cleanly on shutdown.

Startup Sequence:
    Load Config → Create Registry → Create Event Bus → Create Memory
    → Create Risk → Create AI Gateway → Register Services
    → Create WebSocket Manager → Wire Events → Start Scheduler → API Ready

Shutdown Sequence:
    Stop Scheduler → Stop Agents → Close WebSockets
    → Close Memory → Shutdown
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI

from backend.agents.manager import AgentManager
from backend.ai.gateway import AIGateway
from backend.api.websocket import WebSocketManager
from backend.core.event_bus import EventBus
from backend.core.messages import BaseMessage, SystemEvent
from backend.core.registry import Registry
from backend.core.scheduler import Scheduler
from backend.market.scanner import MarketScanner
from backend.memory.journal import Journal
from backend.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


async def _wire_ws_events(bus: EventBus, ws_manager: WebSocketManager) -> None:
    """Subscribe WebSocket manager to key event types for live streaming."""
    from backend.agents.protocol import (
        AgentFailed,
        AgentMessage,
        AgentStarted,
        AgentStopped,
    )
    from backend.core.messages import (
        KillSwitchActivated,
        MemoryEvent,
        RiskApproved,
        RiskRejected,
        SignalGenerated,
        TradeExecuted,
    )
    from backend.intelligence.models import FeaturesUpdated

    event_types = [
        SystemEvent, SignalGenerated, RiskApproved, RiskRejected,
        TradeExecuted, MemoryEvent, KillSwitchActivated,
        AgentStarted, AgentStopped, AgentFailed, AgentMessage,
        FeaturesUpdated,
    ]
    
    from backend.market.events import (
        ConnectionEvent, TickerEvent, CandleEvent, TradeEvent,
        OrderBookEvent, FundingEvent, OpenInterestEvent
    )
    
    market_events = [
        ConnectionEvent, TickerEvent, CandleEvent, TradeEvent,
        OrderBookEvent, FundingEvent, OpenInterestEvent
    ]
    
    for etype in event_types + market_events:
        bus.subscribe(etype, ws_manager.broadcast_event)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    Everything starts here, everything stops here.
    """
    start_time = time.time()
    logger.info("═══ TREDO Starting ═══")

    # ── 1. Create core infrastructure ────────────────────
    registry = Registry()
    bus = EventBus()
    scheduler = Scheduler()

    registry.register("event_bus", bus)
    registry.register("scheduler", scheduler)
    logger.info("Core infrastructure created")

    # ── 2. Create services ───────────────────────────────
    memory_db = Path(__file__).parent.parent.parent / "data" / "tredo_memory.db"
    memory = Journal(db_path=memory_db)
    memory.connect()
    registry.register("memory", memory)
    logger.info("Memory journal connected")

    risk = RiskEngine()
    risk.load_rules()
    registry.register("risk", risk)
    logger.info("Risk engine loaded")

    gateway = AIGateway()
    registry.register("ai_gateway", gateway)
    logger.info("AI gateway created")

    # ── 3. Create agent manager ──────────────────────────
    agent_manager = AgentManager(bus)
    registry.register("agent_manager", agent_manager)
    logger.info("Agent manager created")

    # ── 4. WebSocket manager + event wiring ──────────────
    ws_manager = WebSocketManager()
    registry.register("ws_manager", ws_manager)
    await _wire_ws_events(bus, ws_manager)
    logger.info("WebSocket manager wired to Event Bus")

    # ── 4.5 Create Market Scanner ────────────────────────
    scanner = MarketScanner(bus)
    registry.register("market_scanner", scanner)
    await scanner.start()
    logger.info("Market Scanner started")

    # ── 4.6 Create Feature Store & Pipeline ──────────────
    from backend.intelligence.feature_store import FeatureStore
    from backend.intelligence.pipeline import IntelligencePipeline
    
    feature_store = FeatureStore()
    pipeline = IntelligencePipeline(bus, feature_store)
    
    # Default V1 features
    pipeline.add_feature("BTC/USDT", "EMA", 20)
    pipeline.add_feature("BTC/USDT", "RSI", 14)
    pipeline.add_feature("BTC/USDT", "BB", 20)
    
    registry.register("feature_store", feature_store)
    registry.register("intelligence_pipeline", pipeline)
    await pipeline.start()
    logger.info("Intelligence Pipeline started")

    # ── 5. Store references in app state ─────────────────
    app.state.registry = registry
    app.state.bus = bus
    app.state.scheduler = scheduler
    app.state.agent_manager = agent_manager
    app.state.ws_manager = ws_manager
    app.state.scanner = scanner
    app.state.feature_store = feature_store
    app.state.pipeline = pipeline
    app.state.start_time = start_time

    # ── 6. Publish startup event ─────────────────────────
    await bus.publish(SystemEvent(
        event_type="system",
        message="TREDO started",
        severity="info",
        details={"services": registry.list_services()},
        source="lifespan",
    ))
    logger.info("═══ TREDO Ready (%.2fs) ═══", time.time() - start_time)

    yield  # ── App is running ──

    # ══════════ SHUTDOWN ══════════════════════════════════
    logger.info("═══ TREDO Shutting Down ═══")

    await bus.publish(SystemEvent(
        event_type="system",
        message="TREDO shutting down",
        severity="warning",
        source="lifespan",
    ))

    # Stop scheduler
    if scheduler.running:
        await scheduler.stop()
        logger.info("Scheduler stopped")

    # Stop all agents
    await agent_manager.stop_all(reason="application_shutdown")
    logger.info("Agents stopped")

    # Stop market scanner and pipeline
    await pipeline.stop()
    logger.info("Intelligence Pipeline stopped")
    
    await scanner.stop()
    logger.info("Market Scanner stopped")

    # Close WebSockets
    await ws_manager.close_all()
    logger.info("WebSockets closed")

    # Close memory
    memory.close()
    logger.info("Memory journal closed")

    logger.info("═══ TREDO Shutdown Complete ═══")
