# TREDO V3 — Target Architecture (ROADMAP)

> ⚠️ This is the DESTINATION, not what we build today.
> We build towards this one working component at a time.

## Current Progress

```
✅ = Built & Tested
🔲 = Not yet built
```

```
tredo/
│
├── electron-app/                              # 💎 Desktop Frontend
│   ├── src/
│   │   ├── main/
│   │   │   ├── index.ts                       # 🔲 Electron entry
│   │   │   ├── python-bridge.ts               # 🔲 Python process management
│   │   │   ├── ipc-handlers.ts                # 🔲 IPC routing
│   │   │   └── auto-updater.ts                # 🔲
│   │   ├── renderer/
│   │   │   ├── App.tsx                        # 🔲
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx              # 🔲 Main command center
│   │   │   │   ├── WorldModel.tsx             # 🔲 World model + physics viz
│   │   │   │   ├── Organization.tsx           # 🔲 Org chart + dept status
│   │   │   │   ├── DebateRoom.tsx             # 🔲 Live 8-agent debate
│   │   │   │   ├── ReasoningTree.tsx          # 🔲 Explainable AI decisions
│   │   │   │   ├── Scientists.tsx             # 🔲 Research lab + papers
│   │   │   │   ├── Tournament.tsx             # 🔲 Strategy evolution live
│   │   │   │   ├── DigitalUniverse.tsx        # 🔲 Simulation controls
│   │   │   │   ├── DigitalTwins.tsx           # 🔲 Shadow trade analysis
│   │   │   │   ├── KnowledgeGraph.tsx         # 🔲 Interactive graph (D3)
│   │   │   │   ├── EconomicSim.tsx            # 🔲 Macro ripple simulator
│   │   │   │   ├── MemoryExplorer.tsx         # 🔲 Searchable memory
│   │   │   │   ├── BrainVersions.tsx          # 🔲 Brain timeline
│   │   │   │   ├── MetaIntelligence.tsx       # 🔲 Self-evaluation dashboard
│   │   │   │   ├── ModelLab.tsx               # 🔲 Model training status
│   │   │   │   ├── DataFactory.tsx            # 🔲 Data pipeline monitor
│   │   │   │   ├── Portfolio.tsx              # 🔲 Multi-objective portfolio
│   │   │   │   ├── Predictions.tsx            # 🔲 Multi-future scenarios
│   │   │   │   ├── Plugins.tsx                # 🔲 Plugin manager
│   │   │   │   ├── InternalPapers.tsx         # 🔲 Research paper browser
│   │   │   │   └── Settings.tsx               # 🔲 Configuration
│   │   │   ├── components/
│   │   │   │   ├── charts/                    # 🔲 TradingView integration
│   │   │   │   ├── agents/                    # 🔲 Agent cards + status
│   │   │   │   ├── org/                       # 🔲 Organization tree
│   │   │   │   ├── physics/                   # 🔲 Force visualizations
│   │   │   │   ├── genome/                    # 🔲 Strategy DNA viewer
│   │   │   │   ├── debate/                    # 🔲 Debate UI
│   │   │   │   ├── reasoning/                 # 🔲 Decision tree renderer
│   │   │   │   ├── graph/                     # 🔲 D3 knowledge graph
│   │   │   │   ├── portfolio/                 # 🔲 Holdings, P&L
│   │   │   │   ├── controls/                  # 🔲 Kill switch, mode toggle
│   │   │   │   └── shared/                    # 🔲 Buttons, cards, modals
│   │   │   ├── hooks/                         # 🔲
│   │   │   ├── stores/                        # 🔲
│   │   │   └── styles/                        # 🔲
│   │   └── shared/
│   │       └── types.ts                       # 🔲
│   ├── package.json                           # 🔲
│   └── electron-builder.yml                   # 🔲
│
├── tredo-core/                                # 🧠 Python AI Engine
│   │
│   ├── kernel/                                # 💻 Market OS Kernel
│   │   ├── os.py                              # 🔲 Kernel bootstrap
│   │   ├── engine_registry.py                 # 🔲 Engine registration
│   │   ├── event_bus.py                       # 🔲 Inter-engine messaging
│   │   ├── scheduler.py                       # 🔲 Task scheduling
│   │   └── config.py                          # ✅ (backend/config/settings.py)
│   │
│   ├── organization/                          # 🏛️ AI Organization
│   │   ├── board.py                           # 🔲 Board of Directors AI
│   │   ├── ceo.py                             # 🔲 Chief Executive AI
│   │   ├── c_suite/                           # 🔲
│   │   ├── protocol.py                        # 🔲 Agent communication
│   │   ├── kpi_tracker.py                     # 🔲
│   │   └── budget.py                          # 🔲
│   │
│   ├── research/                              # 🔬 Research Department
│   │   ├── scientists/                        # 🔲 6 scientist types
│   │   ├── experiment/                        # 🔲
│   │   ├── papers/                            # 🔲
│   │   ├── data_science/                      # 🔲
│   │   └── labs/                              # 🔲
│   │
│   ├── trading/                               # 📈 Trading Department
│   │   ├── portfolio_manager.py               # 🔲
│   │   ├── timeframe_ais/                     # 🔲 5 timeframe AIs
│   │   ├── execution/
│   │   │   ├── executor.py                    # 🔲
│   │   │   ├── paper_trading.py               # 🔲
│   │   │   └── ...                            # 🔲
│   │   ├── debate/                            # 🔲 8-agent debate
│   │   └── reasoning/                         # 🔲
│   │
│   ├── risk/                                  # 🛡️ Risk Department
│   │   ├── safety.py                          # ✅ (backend/risk/engine.py)
│   │   ├── limits.py                          # ✅ (inside engine.py)
│   │   ├── killswitch.py                      # ✅ (inside engine.py)
│   │   ├── compliance.py                      # 🔲
│   │   ├── drift_detector.py                  # 🔲
│   │   └── var_engine.py                      # 🔲
│   │
│   ├── engineering/                           # 🔲 Engineering Department
│   ├── world_model/                           # 🔲 World Model
│   ├── intelligence/                          # 🔲 Intelligence Core
│   ├── memory/                                # 🔲 Long-Term Memory
│   ├── evolution/                             # 🔲 Evolution Engine
│   ├── simulation/                            # 🔲 Market Digital Universe
│   ├── models/                                # 🔲 Self-Built AI Models
│   ├── data_factory/                          # 🔲 Data Factory
│   │
│   ├── data/                                  # 📡 Data Feeds
│   │   ├── exchange.py                        # ✅ (backend/exchange/connector.py)
│   │   ├── feeds/                             # 🔲
│   │   └── historical.py                      # 🔲
│   │
│   ├── portfolio/                             # 🔲 Portfolio Engine
│   ├── plugins/                               # 🔲 Plugin System
│   ├── distributed/                           # 🔲 Distributed Execution
│   │
│   ├── api/                                   # 🔲 API Server
│   │   ├── server.py                          # 🔲
│   │   ├── routes/                            # 🔲
│   │   ├── websocket.py                       # 🔲
│   │   └── schemas.py                         # 🔲
│   │
│   ├── config/
│   │   ├── settings.py                        # ✅
│   │   └── meta_rules.yaml                   # ✅
│   │
│   └── requirements.txt                       # ✅ (pyproject.toml)
│
├── data/                                      # 🔲 Local Storage
├── plugins/                                   # 🔲
├── tests/                                     # ✅ (52 tests passing)
├── docs/                                      # 🔲
├── .gitignore                                 # 🔲
├── README.md                                  # 🔲
├── docker-compose.yml                         # 🔲
├── Makefile                                   # 🔲
└── pyproject.toml                             # ✅
```

## Build Order (SpaceX Style)

| # | Milestone | Maps to V3 Target | Status |
|---|---|---|---|
| 1 | Exchange Connector | `tredo-core/data/exchange.py` | ✅ |
| 2 | Risk Engine | `tredo-core/risk/safety.py + killswitch.py` | ✅ |
| 3 | Memory / Trade Journal | `tredo-core/memory/episodic.py` | 🔲 |
| 4 | LLM Provider | (Custom addition) | 🔲 |
| 5 | Agent Base System | `tredo-core/organization/protocol.py` | 🔲 |
| 6 | FastAPI + WebSocket | `tredo-core/api/server.py` | 🔲 |
| 7 | Electron Shell | `electron-app/` | 🔲 |
| 8 | Dashboard | `electron-app/pages/Dashboard.tsx` | 🔲 |
| 9-10 | TA + Sentiment Agents | Agents using base system | 🔲 |
| 11-15 | World Model | `tredo-core/world_model/` | 🔲 |
| 16-20 | Debate + Reasoning | `tredo-core/trading/debate/` | 🔲 |
| 21-30 | Knowledge Graph | `tredo-core/intelligence/` | 🔲 |
| 31-40 | Evolution | `tredo-core/evolution/` | 🔲 |
| 41-50 | Scientists + Research | `tredo-core/research/` | 🔲 |
| 51+ | Organization + Meta | `tredo-core/organization/` | 🔲 |

> When V1 backend/ is stable, we'll restructure into tredo-core/ to match V3 target.
