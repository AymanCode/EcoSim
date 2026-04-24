# EcoSim

EcoSim is an agent-based macroeconomic simulation with a live dashboard, a
streaming API, and a persistence layer for scenario analysis. It models
households, firms, banks, housing, healthcare, and government policy in a
single closed-loop system.

## Overview

This project is built as a policy sandbox: change taxes, benefits, wage floors,
or spending behavior and watch the economy react over time.

Core capabilities:

- real-time simulation of labor, goods, housing, healthcare, banking, and fiscal policy
- live dashboard with streaming metrics over WebSocket
- one-command Docker startup for the full stack
- warehouse persistence for run history, diagnostics, and comparative analysis
- configurable scenario inputs for experimentation and stress testing

## Stack

| Layer | Technology |
| --- | --- |
| Simulation engine | Python |
| API | FastAPI + WebSocket |
| Frontend | React + Vite |
| Persistence | SQLite or PostgreSQL/Timescale |
| Analytics utilities | NumPy, Pandas |

## Quickstart

The primary path is a single command that starts the full stack and waits for it to become healthy.

macOS/Linux:

```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
./start.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
.\start.ps1
```

Open:

- `http://localhost:5173`

Direct Docker equivalent:

```bash
docker compose up --build -d --wait
```

## Architecture

```text
frontend-react/          live dashboard
    ->
backend/server.py        API + websocket stream + simulation manager
    ->
backend/economy.py       tick orchestration and market clearing
    ->
backend/agents.py        households, firms, bank, and government behavior
    +
backend/config.py        simulation parameter system
    +
backend/data/            warehouse models, schema, migrations, persistence
```

## Engineering Highlights

- The backend keeps simulation execution in memory and streams a compact live view to the frontend.
- Warehouse writes are batched and support richer post-run analysis than the live UI payload.
- The repo includes both contract-style regression tests and API-level tests around persistence and runtime behavior.
- Supplementary runners, diagnostics, and research utilities are separated into `backend/tools/` to keep the main application surface clean.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\Activate.ps1  # Windows PowerShell

pip install -r requirements.txt
python -m uvicorn backend.server:app --reload --port 8002
```

In a second terminal:

```bash
cd frontend-react
npm install
npm run dev
```

## Testing

Stable CI checks:

```bash
pip install -r requirements-dev.txt
python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
python -m pytest backend/tests_contracts -q -m "not llm and not research"
cd frontend-react
npm ci
npm run lint
npm run build
```

Research and local LLM checks are kept in the repo, but are not required for the public CI gate:

```bash
python -m pytest backend/tests_contracts -q -m "llm or research"
```

## Repository Layout

```text
backend/            core simulation engine, API, persistence, and tests
frontend-react/     dashboard application
docs/               active technical documentation
ops/                optional infrastructure files
```

Additional research runners, scenario scripts, and offline analysis helpers live under `backend/tools/`.

Detailed documentation starts at [docs/README.md](docs/README.md).
