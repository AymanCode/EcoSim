# EcoSim Project Architecture Map

## Overview
EcoSim is a multi-agent economic simulation with a React frontend, FastAPI backend, and optional data warehouse (SQLite/TimescaleDB). The system simulates households, firms, and government agents interacting in a virtual economy.

---

## 1. Entry Points

### Frontend Entry Point
- **`frontend-react/src/main.jsx`** — React application entry point
  - Renders `<App />` inside `StrictMode` into the root DOM element
  - Imports `App.jsx` which contains the full UI application

- **`frontend-react/src/App.jsx`** — Main application component
  - Manages WebSocket connection to backend (`ws://localhost:8002/ws`)
  - Implements all UI views: Config, Dashboard, Subjects, Firms, Government, Logs
  - Uses React state (`useState`, `useEffect`, `useRef`) for local state management
  - No external state management library (Redux, etc.) — pure React state

### Backend Entry Point
- **`backend/server.py`** — FastAPI application entry point
  - Creates `FastAPI(title="EcoSim", version="2.0.0")` instance
  - Defines WebSocket endpoint `/ws` for real-time simulation communication
  - Defines REST API endpoints for warehouse queries (`/warehouse/...`)
  - Contains `SimulationManager` class that owns the `Economy` instance and drives the tick loop
  - Health check endpoint: `GET /health`

### Simulation Entry Point
- **`backend/tools/runners/run_large_simulation.py`** — Direct simulation runner (non-WebSocket)
  - `create_large_economy()` function creates all agents (Households, Firms, Government, Bank)
  - Used for batch runs, testing, and analysis without the web frontend

---

## 2. Layer Architecture

### Frontend Layer (`frontend-react/src/`)
**Type**: React 19 + Vite + Tailwind CSS
**State Management**: React hooks (`useState`, `useEffect`, `useRef`)
**Key Files**:
- `App.jsx` — Main application (2204 lines) — **CENTRAL**
- `NeuralAvatar.jsx` — 3D avatar visualization — **PERIPHERAL**
- `NeuralBuilding.jsx` — 3D building visualization — **PERIPHERAL**
- `NeuralGovernment.jsx` — 3D government visualization — **PERIPHERAL**
- `main.jsx` — Entry point — **CENTRAL**
- `App.css`, `index.css` — Styles — **PERIPHERAL**
- `assets/` — Static assets — **PERIPHERAL**

**Dependencies** (from `package.json`):
- `react`, `react-dom` — Core React
- `lucide-react` — Icons
- `recharts` — Charting/visualization

### Backend API Layer (`backend/server.py`)
**Type**: FastAPI + WebSocket
**Key Endpoints**:
- `WebSocket /ws` — Main simulation communication (setup, start, pause, stop, config updates)
- `GET /health` — Health check
- `GET /warehouse/runs` — List simulation runs
- `GET /warehouse/runs/{run_id}/tick-metrics` — Tick metrics history
- `GET /warehouse/runs/{run_id}/decision-features` — Decision context history
- `GET /warehouse/runs/{run_id}/tick-diagnostics` — Per-tick diagnostics
- `GET /warehouse/runs/{run_id}/sector-metrics` — Sector-level metrics
- `GET /warehouse/runs/{run_id}/sector-shortages` — Sector shortage diagnostics
- `GET /warehouse/runs/{run_id}/regime-events` — Regime/state transition events
- `GET /warehouse/runs/{run_id}/policy-context` — Policy decision context
- `GET /warehouse/compare` — Compare multiple simulation runs

### Backend Core Layer (`backend/`)
**Type**: Python simulation engine

#### Agent System (`backend/agents.py` — 5718 lines) — **CENTRAL**
- `HouseholdAgent` (dataclass) — Household agent with consumption, labor supply, wellbeing dynamics
- `FirmAgent` (dataclass) — Firm agent with production, pricing, hiring logic
- `BankAgent` (dataclass) — Banking agent providing credit channel
- `GovernmentAgent` (dataclass) — Government agent with taxation, transfers, policy
- `LoanContract` — Mortgage/hire-purchase contracts
- `FirmHealthSnapshot` — Per-tick firm health metrics

#### Economy Engine (`backend/economy.py` — 5769 lines) — **CENTRAL**
- `Economy` class — Main simulation coordinator
- Orchestrates 16-phase tick loop:
  1. Firm production/labor planning
  2. Household labor supply planning
  3. Labor market matching
  4. Apply labor outcomes
  5. Firm production/costs application
  6. Goods market clearing
  7. Government tax planning
  8. Government transfer planning
  9. Apply sales/profits/taxes
  10. Apply income/transfers/purchases to households
  11. Apply fiscal results to government
  12. Handle firm bankruptcies
  13. Create new firms
  14. Government policy adjustments
  15. Update world statistics
  16. Distribute dividends

#### Configuration (`backend/config.py` — 768 lines) — **CENTRAL**
- `SimulationConfig` — Master configuration
- `TimeConfig`, `HouseholdBehaviorConfig`, `FirmBehaviorConfig`
- `GovernmentPolicyConfig`, `LaborMarketConfig`, `MarketMechanicsConfig`
- `LLMConfig`, `DebugConfig`, `SimulationModeConfig`
- `CONFIG = SimulationConfig()` — Global instance

### Data Warehouse Layer (`backend/data/`) — **CENTRAL (Optional)**
**Purpose**: Persistent storage for simulation analysis
**Backends Supported**:
- SQLite (default for local development)
- TimescaleDB/PostgreSQL (configured via `docker-compose.timescale.yml`)

**Key Components** (from code references):
- `data/warehouse_factory.py` — `create_warehouse_manager()` factory
- `data/models.py` — Data models: `SimulationRun`, `TickMetrics`, `SectorTickMetrics`, `DecisionFeature`, `FirmSnapshot`, `HouseholdSnapshot`, `TrackedHouseholdHistory`, `LaborEvent`, `HealthcareEvent`, `PolicyAction`, `RegimeEvent`, `TickDiagnostic`, `SectorShortageDiagnostic`
- `data/warehouse_manager.py` — Manager class for DB operations
- `data/schema.sql` — Database schema

**Environment Variables**:
- `ECOSIM_ENABLE_WAREHOUSE` — Enable/disable warehouse (default: "0")
- `ECOSIM_WAREHOUSE_BACKEND` — "sqlite" or "timescaledb" (default: "sqlite")
- `ECOSIM_SQLITE_PATH` — SQLite DB path (default: `/app/runtime/ecosim.db`)

### AI/LLM Layer (`backend/tools/llm/`) — **CENTRAL (Optional)**
**Type**: LLM-driven agent decisions
**Key Files**:
- `llm_provider.py` — Provider abstraction (Ollama, LM Studio, OpenRouter)
- `llm_government.py` — `LLMGovernmentAdvisor` class for policy decisions
- `llm_firm.py` — `LLMFirmAdvisor` for firm decisions
- `run_llm_government_test.py` — Test runner
- `run_llm_firm_test.py` — Test runner
- `run_all_archetypes.py` — Batch testing
- `run_household_llm_tester.py` — Household LLM testing

**Configuration** (in `config.py` `LLMConfig`):
- `provider` — "ollama" | "lmstudio" | "openrouter"
- `government_model` — Default: "microsoft/phi-4-mini-reasoning"
- `enable_llm_government` — Default: `False` (opt-in)
- `government_decision_interval` — Ticks between decisions (default: 4)

### Utility/Tool Layer (`backend/tools/`)
**Type**: Analysis, testing, and runner scripts

#### Analysis Tools (`backend/tools/analysis/`) — **PERIPHERAL**
- `audit_digest.py` — Generate audit digest
- `generate_sample_data.py` — Export simulation data
- `generate_training_data.py` — Create ML training datasets
- `train_ml_model.py` — Train ML models
- `run_tax_comparison.py` — Compare tax policies
- `demo_skill_experience.py` — Skill system demo

#### Runner Tools (`backend/tools/runners/`) — **PERIPHERAL**
- `run_large_simulation.py` — Main batch simulation runner (CENTRAL for non-UI runs)
- `run_audit_simulation.py` — Audit simulation runner
- `run_bank_simulation.py` — Bank-specific simulation
- `run_diagnostic.py` — Diagnostic runner
- `run_firm_tracker.py` — Firm tracking utility

#### Check Tools (`backend/tools/checks/`) — **PERIPHERAL**
- `run_behavior_tests.py` — Behavior regression tests
- `run_household_behavior_tests.py` — Household-specific tests
- `test_firm_behavior.py` — Firm behavior tests
- `test_government_behavior.py` — Government behavior tests
- `test_household_agent.py` — Household agent unit tests
- `test_stochastic.py` — Stochastic behavior tests
- `test_training_setup.py` — Training setup validation

---

## 3. Main Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                          │
│  App.jsx (WebSocket Client)                              │
│  - Connects to ws://localhost:8002/ws                    │
│  - Sends: SETUP, START, STOP, RESET, CONFIG commands      │
│  - Receives: tick, metrics, firm_stats, logs                    │
└────────────────────────────┬────────────────────────────────┘
                             │ WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                              │
│  server.py: SimulationManager                              │
│  - Receives WebSocket commands                             │
│  - Manages Economy instance                                │
│  - Runs tick loop (run_tick())                              │
│  - Broadcasts tick data to frontend                         │
│  - Optional: Warehouse persistence (SQLite/TimescaleDB)      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SIMULATION ENGINE (Python)                       │
│  economy.py: Economy.step() — 16-phase tick loop             │
│                                                               │
│  Phase 1:  Firms plan production, pricing, wages              │
│  Phase 2:  Households plan labor supply & consumption       │
│  Phase 3:  Labor market matching                          │
│  Phase 4:  Apply labor outcomes                          │
│  Phase 5:  Firms apply production & costs                 │
│  Phase 6:  Goods market clearing                        │
│  Phase 7:  Government plans taxes                       │
│  Phase 8:  Government plans transfers                    │
│  Phase 9:  Apply sales, profits, taxes                  │
│  Phase 10: Apply income, taxes, transfers to households    │
│  Phase 11: Apply fiscal results to government           │
│  Phase 12: Handle firm bankruptcies                    │
│  Phase 13: Create new firms                          │
│  Phase 14: Government policy adjustments              │
│  Phase 15: Update world statistics                   │
│  Phase 16: Distribute dividends                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AGENT LAYER (agents.py)                         │
│  HouseholdAgent: Consumption, labor supply, wellbeing          │
│  FirmAgent: Production, pricing, hiring, investment          │
│  GovernmentAgent: Taxation, transfers, policy                  │
│  BankAgent: Credit, loans, deposits                         │
└─────────────────────────────────────────────────────────────────────┘
```

### WebSocket Message Protocol (`backend/server.py`)
**Client → Server**:
- `{"command": "SETUP", "config": {...}}` — Initialize economy
- `{"command": "START"}` — Begin tick loop
- `{"command": "STOP"}` — Pause tick loop
- `{"command": "RESET"}` — Reset economy
- `{"command": "CONFIG", "config": {...}}` — Update runtime config
- `{"command": "STABILIZERS", "disable_stabilizers": bool, "disabled_agents": [...]}` — Toggle stabilizers

**Server → Client**:
- `{"type": "SETUP_COMPLETE"}` — Economy ready
- `{"type": "TICK", "tick": N, "metrics": {...}, "firm_stats": {...}, "logs": [...]}` — Tick data
- `{"type": "STARTED"}` — Simulation started
- `{"type": "STOPPED"}` — Simulation stopped
- `{"type": "RESET"}` — Economy reset

---

## 4. File Classification

### CENTRAL (Core to Application Functionality)

| File | Layer | Description |
|-----|-------|-------------|
| `frontend-react/src/App.jsx` | Frontend | Main React application with all UI views |
| `frontend-react/src/main.jsx` | Frontend | React entry point |
| `backend/server.py` | Backend API | FastAPI + WebSocket server, SimulationManager |
| `backend/economy.py` | Backend Core | 16-phase simulation engine (5769 lines) |
| `backend/agents.py` | Backend Core | Agent definitions: Household, Firm, Government, Bank (5718 lines) |
| `backend/config.py` | Backend Core | All simulation configuration (768 lines) |
| `backend/tools/runners/run_large_simulation.py` | Utility | Batch simulation runner, `create_large_economy()` |

### CENTRAL (Optional Features)

| File | Layer | Description |
|-----|-------|-------------|
| `backend/tools/llm/llm_provider.py` | AI/LLM | Provider abstraction (Ollama, LM Studio, OpenRouter) |
| `backend/tools/llm/llm_government.py` | AI/LLM | LLM-driven government policy advisor |
| `backend/tools/llm/llm_firm.py` | AI/LLM | LLM-driven firm advisor |
| `backend/data/warehouse_factory.py` | Database | Warehouse manager factory |
| `backend/data/models.py` | Database | Data models for persistence |
| `backend/data/warehouse_manager.py` | Database | DB operations manager |

### PERIPHERAL (Tools, Tests, Docs, Config)

| File | Layer | Description |
|-----|-------|-------------|
| `frontend-react/src/NeuralAvatar.jsx` | Frontend | 3D avatar visualization |
| `frontend-react/src/NeuralBuilding.jsx` | Frontend | 3D building visualization |
| `frontend-react/src/NeuralGovernment.jsx` | Frontend | 3D government visualization |
| `backend/tools/analysis/*.py` | Utility | Analysis and ML training scripts |
| `backend/tools/runners/run_*_simulation.py` | Utility | Specialized simulation runners |
| `backend/tools/checks/*.py` | Utility | Behavior tests and validation |
| `backend/tests_contracts/` | Testing | Contract-style regression tests |
| `backend/tests_server/` | Testing | Server API tests |
| `docs/` | Documentation | Project documentation |
| `docs/archive/` | Documentation | Historical documentation |
| `docker-compose.yml` | Deployment | Docker compose for backend + frontend |
| `ops/docker-compose.timescale.yml` | Deployment | TimescaleDB Docker config |
| `start.sh`, `start.ps1` | Deployment | Startup scripts |
| `pyproject.toml`, `requirements.txt`, `requirements-dev.txt` | Config | Python dependencies |
| `frontend-react/package.json` | Config | Node.js dependencies |

---

## 5. Deployment Architecture

### Docker Deployment (`docker-compose.yml`)
```
┌──────────────────────────────────────────────────────────────┐
│                      DOCKER COMPOSE                              │
│                                                              │
│  ┌─────────────────┐      ┌─────────────────┐       │
│  │  ecosim-backend  │      │ ecosim-frontend │       │
│  │  (FastAPI:8002)  │◄────►│  (Nginx:80)     │       │
│  │                  │      │                  │       │
│  │  ECOSIM_ENABLE_  │      │  Depends on      │       │
│  │  WAREHOUSE=1     │      │  backend health  │       │
│  │  WAREHOUSE_BACKEND │      └─────────────────┘       │
│  │  =sqlite          │                                │
│  └─────────────────┘                                │
│         │                                                │
│         ▼                                                │
│  ┌─────────────────┐                                │
│  │  ecosim_runtime  │ (Docker volume)                  │
│  │  /app/runtime/  │                                │
│  │  ecosim.db      │                                │
│  └─────────────────┘                                │
└──────────────────────────────────────────────────────────────┘
```

### Local Development
- **Backend**: `cd backend && pip install -r requirements.txt && python server.py`
- **Frontend**: `cd frontend-react && npm install && npm run dev` (Vite dev server on port 5173)
- **WebSocket URL**: Configured via `VITE_WS_URL` env var or auto-detects `ws://localhost:8002/ws`

---

## 6. Key Design Patterns

### 1. Plan/Apply Cycle (Economy)
The simulation uses a strict plan/apply cycle where agents first plan their actions, then outcomes are applied:
- Firms plan production, labor, pricing → outcomes applied
- Households plan labor supply, consumption → outcomes applied
- Government plans taxes, transfers → outcomes applied

### 2. Optional Feature Gating
Major features are opt-in with graceful degradation:
- LLM agents: `config.llm.enable_llm_government = False` (default)
- Warehouse persistence: `ECOSIM_ENABLE_WAREHOUSE=0` (default)
- When disabled, code paths use fallback logic (e.g., live metrics vs. warehouse queries)

### 3. Vectorized Operations (Performance)
- `economy.py` uses NumPy for batch operations (household consumption planning, wage percentile calculation)
- `agents.py` uses Python dataclasses with `__slots__` for memory efficiency

### 4. WebSocket Real-Time Communication
- Single `/ws` endpoint handles all simulation control and data streaming
- JSON messages with `type` field for routing
- Server pushes `tick` messages with full metrics payload

---

## 7. Directory Structure Summary

```
EcoSim/
├── backend/
│   ├── agents.py              # Agent definitions (CENTRAL)
│   ├── economy.py             # Simulation engine (CENTRAL)
│   ├── config.py               # Configuration (CENTRAL)
│   ├── server.py               # FastAPI + WebSocket (CENTRAL)
│   ├── backend/                # (empty or sub-modules)
│   ├── data/                   # Warehouse layer (CENTRAL optional)
│   ├── tools/
│   │   ├── analysis/          # Analysis scripts (PERIPHERAL)
│   │   ├── checks/            # Behavior tests (PERIPHERAL)
│   │   ├── llm/               # AI/LLM layer (CENTRAL optional)
│   │   └── runners/           # Simulation runners (PERIPHERAL)
│   ├── tests_contracts/        # Contract tests (PERIPHERAL)
│   └── tests_server/           # API tests (PERIPHERAL)
├── frontend-react/
│   ├── src/
│   │   ├── App.jsx           # Main UI (CENTRAL)
│   │   ├── main.jsx          # Entry point (CENTRAL)
│   │   ├── NeuralAvatar.jsx   # 3D avatar (PERIPHERAL)
│   │   ├── NeuralBuilding.jsx # 3D building (PERIPHERAL)
│   │   └── NeuralGovernment.jsx # 3D gov (PERIPHERAL)
│   └── package.json
├── docs/                       # Documentation (PERIPHERAL)
├── ops/                        # Operations configs (PERIPHERAL)
├── docker-compose.yml           # Docker setup (PERIPHERAL)
├── pyproject.toml              # Python config (PERIPHERAL)
├── requirements.txt             # Python deps (PERIPHERAL)
└── docs/internal/PROJECT_MAP.md # This file
```

---

## 8. Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | Python 3, FastAPI, WebSocket, NumPy |
| Simulation | Custom multi-agent engine, dataclasses, asyncio |
| Database | SQLite (dev), PostgreSQL + TimescaleDB (prod) |
| AI/LLM | Ollama, LM Studio, OpenRouter (optional) |
| Deployment | Docker, Docker Compose, Nginx |
| Testing | pytest, contract-style tests |

---

*Generated: 2026-05-04*
*Based on analysis of: backend/server.py, backend/economy.py, backend/agents.py, backend/config.py, frontend-react/src/App.jsx, docker-compose.yml, and related files.*
