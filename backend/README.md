# Backend

The backend contains the simulation engine, FastAPI/WebSocket server, warehouse layer, research tools, and Python test suites.

## Main Modules

| Path | Responsibility |
|---|---|
| [`agents.py`](agents.py) | Household, firm, bank, and government agent state and decision methods |
| [`economy.py`](economy.py) | Tick lifecycle, market clearing, healthcare, banking, diagnostics, firm lifecycle |
| [`server.py`](server.py) | FastAPI app, WebSocket protocol, run manager, live LLM scheduling, warehouse batching |
| [`config.py`](config.py) | Frozen dataclass configuration tree |
| [`policy_schema.py`](policy_schema.py) | Canonical government policy action space used by UI and LLM paths |
| [`data/`](data/README.md) | SQLite/PostgreSQL/Timescale warehouse managers, schemas, migrations, data tests |
| [`tools/`](tools/README.md) | LLM runners, benchmark CLIs, diagnostics, analysis, sample generation |
| [`tests_contracts/`](tests_contracts/README.md) | Contract-style simulation regression tests |
| [`tests_server/`](tests_server) | FastAPI/WebSocket and warehouse API tests |

## Local Server

Run from the repository root:

```bash
python -m uvicorn backend.server:app --reload --port 8002
```

Health check:

```bash
curl http://127.0.0.1:8002/health
```

The dashboard connects to `ws://localhost:8002/ws` through the Vite or Nginx proxy.

## Tests

Stable backend gate:

```bash
python -m pytest backend/tests_contracts backend/tests_server -q -m "not llm and not research"
```

Warehouse/API:

```bash
python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
```

LLM and research-marked contracts:

```bash
python -m pytest backend/tests_contracts -q -m "llm or research"
```

## Runtime Notes

- The live simulation runs in memory; persistence is optional.
- Direct local backend runs use no warehouse unless `ECOSIM_ENABLE_WAREHOUSE=1`.
- Docker Compose enables SQLite warehouse persistence in a runtime volume.
- LLM government provider setup is optional. If no provider is available, the simulation can still run with manual/rule-based policy controls.
