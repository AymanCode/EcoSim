# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Verified Non-Obvious Facts

- **warmup_ticks default is 10** (`config.py:16`), not 52 as older docs claim. Fallback of 52 exists in `economy.py:71`.
- **Population scale**: 3-100,000 households (`server.py:147`), not 3,000 as FRONTEND.md states.
- **Test directories**: `backend/tests_contracts/` and `backend/tests_server/` — NOT `backend/data/tests/`.
- **Monolithic files**: `agents.py` (5718 lines) and `economy.py` (5769 lines) are intentionally monolithic — DO NOT split them.
- **Dead frontend scripts**: `frontend-react/fix_nested.py`, `fix_nested_safe.py`, `replace_script.py`, `replace_script2.py`, `update_firms.py`, `update_gov_tab.py`, `update_subjects_tab.py`, `insert_distress_gauge.py` are one-time migration tools — DO NOT use them.
- **Deterministic RNG**: Code uses `random.Random(CONFIG.random_seed + ...)` — behavior IS deterministic with same seed.
- **Good category inference** is duplicated in 3 places: `agents.py:21`, `server.py:414`, `economy.py:2920` — consolidation planned per CLEANUP_AUDIT.md.
- **Shock magic numbers** in `economy.py`: `base_transfer=40.0`, `demand_shock_prob=0.05`, `supply_shock_prob=0.03`, `health_shock_prob=0.02` — moving to config per CLEANUP_AUDIT.md.
- **Frontend JSON**: Backend sends camelCase keys — DO NOT change JSON key naming conventions.
- **`maybe_active_education()`** returns `float` (cost paid), not `bool` as some docs claim.
- **Tick lifecycle**: 16 phases in `economy.py:863-876`, not 15 as SIMULATION.md states.
- **Dynamic attribute anti-pattern**: `server.py:1817` uses `hasattr(self, 'prev_gov_cash')` — initialization fix planned per CLEANUP_AUDIT.md.

## Build/Run Commands (Non-Standard)

- **Local dev**: Run `start.sh` (Linux/Mac) or `start.ps1` (Windows) FROM PROJECT ROOT.
- **Docker (SQLite dev)**: `docker-compose up` — sets `ECOSIM_ENABLE_WAREHOUSE=1` with SQLite backend.
- **Docker (TimescaleDB prod)**: `docker-compose -f ops/docker-compose.timescale.yml up` — requires separate TimescaleDB container.
- **Backend only**: `cd backend && uvicorn server:app --host 0.0.0.0 --port 8002`
- **Frontend only**: `cd frontend-react && npm run dev` (Vite dev server on port 5173)
- **Tests**: `pytest backend/tests_contracts/ -v` and `pytest backend/tests_server/ -v`
- **Code style**: Line length 120 (`pyproject.toml:37`), not standard 88 or 100.

## Architecture Notes

- **WebSocket primary**: Backend uses FastAPI with WebSocket at `/ws` (`server.py:2676`) — not just REST.
- **Optional LLM integration**: `backend/tools/llm/` — opt-in via `config.py` `LLMConfig.enable_llm_government` (default: False).
- **Data warehouse**: Optional persistence layer supporting SQLite (dev) and TimescaleDB/PostgreSQL (prod) via env vars `ECOSIM_ENABLE_WAREHOUSE`, `ECOSIM_WAREHOUSE_BACKEND`.
- **Backend imports**: Uses `sys.path.insert(0, os.path.dirname(...))` hack in `server.py:42` to import backend modules.
- **Config centralization**: All parameters in `backend/config.py` using Pydantic dataclasses — NOT SQLAlchemy models.
