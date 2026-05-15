# AGENTS.md

High-density guidance for AI agents working in EcoSim.

## Repository Identity

EcoSim is an agent-based macroeconomic simulation with a Python/FastAPI backend, a persistent WebSocket dashboard, optional warehouse persistence, and an async LLM/LangGraph government advisor.

Core path:

```text
frontend-react/         React + Vite live dashboard
backend/server.py       FastAPI app, WebSocket protocol, SimulationManager
backend/economy.py      canonical tick engine and market clearing
backend/agents.py       household, firm, bank, government agent behavior
backend/config.py       Pydantic dataclass configuration surface
backend/tools/llm/      async LLM government and firm experiments
backend/tests_contracts contract/invariant simulation tests
backend/tests_server    API/server tests
```

## Non-Obvious Source Of Truth

- `backend/economy.py::Economy.step()` is the executable tick lifecycle. Treat docs as secondary when they disagree.
- `docs/SIMULATION.md` describes a 21-row lifecycle, but current code implements 16 numbered main phases with subphases. Do not rewrite code to match the doc table unless the task explicitly includes a lifecycle migration and full regression testing.
- `backend/agents.py` and `backend/economy.py` are intentionally large monoliths. Do not split them as cleanup.
- Frontend payloads use camelCase JSON keys. Do not rename the WebSocket/API contract to snake_case.
- `CONFIG.time.warmup_ticks` defaults to `10`; an older fallback of `52` still exists in `economy.py`.
- Runtime setup allows `3` to `100_000` households via `SetupConfig` in `server.py`; default config is `10_000`.
- Randomness is intended to be deterministic when seeded. Preserve `CONFIG.random_seed`, `random.Random(CONFIG.random_seed + ...)`, and NumPy seeding patterns.
- `maybe_active_education()` returns a `float` cost paid, not a boolean.
- Good/category inference is still duplicated across backend modules. Avoid one-off partial consolidation unless that is the task.
- Dead one-time frontend migration scripts are not part of the active app: `frontend-react/fix_nested.py`, `fix_nested_safe.py`, `replace_script.py`, `replace_script2.py`, `update_firms.py`, `update_gov_tab.py`, `update_subjects_tab.py`, `insert_distress_gauge.py`.

## Build, Run, Test

Run commands from repository root unless noted.

```bash
# Full Docker stack, preferred quickstart
./start.sh
```

```powershell
# Windows full Docker stack
.\start.ps1
```

```bash
# Backend only
python -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8002

# Alternate when cwd is backend/
cd backend
uvicorn server:app --host 0.0.0.0 --port 8002
```

```bash
# Frontend only
cd frontend-react
npm install
npm run dev
```

```bash
# Stable backend tests
python -m pytest backend/tests_contracts backend/tests_server -q
python -m pytest backend/tests_contracts -q -m "not llm and not research"

# Frontend checks
cd frontend-react
npm ci
npm run lint
npm run build

# Local research/LLM contracts, not stable CI gate
python -m pytest backend/tests_contracts -q -m "llm or research"
```

Docker variants:

```bash
docker compose up --build -d --wait
docker compose up
docker compose -f ops/docker-compose.timescale.yml up
```

## Coding Standards

Python:

- Requires Python `>=3.11`.
- Use NumPy for population-scale math and statistics on hot simulation paths. Prefer array operations, masks, `np.percentile`, `np.minimum/maximum`, and batched transforms over per-agent Python loops when behavior is vectorizable.
- Python loops are acceptable when stateful agent behavior, ordered matching, side effects, audit trails, or deterministic tie-breaking require them. Do not replace deterministic matching loops with unordered/vectorized code unless tests prove identical semantics.
- Formatting follows Black/isort with line length `120` from `pyproject.toml`.
- Keep config centralized in `backend/config.py`; do not add new magic numbers in the tick engine.
- Use structured config/dataclasses and existing helper APIs rather than ad hoc dict/string conventions.

React:

- The frontend is plain JavaScript/JSX, not TypeScript.
- Vite + React 19, ESM modules, `lucide-react` icons, Recharts, Tailwind utility classes plus inline themed CSS in `App.jsx`.
- ESLint scans `**/*.{js,jsx}` with React Hooks and React Refresh rules. Unused variables are errors except names matching `^[A-Z_]`.
- Preserve the existing WebSocket-first architecture in `App.jsx`; avoid replacing streaming state with REST polling.

## Tick Engine Guardrails

`Economy.step()` is a strict staged state transition. Preserve ordering and do not introduce async work inside it.

Current canonical sequence:

```text
prelude  warmup flags, queued firms, telemetry resets, shocks, healthcare queues, market views
1        firm production/labor/price/wage planning; capital investment intent
1.5      investment loan offers
2        household education, labor planning, consumption planning
2a       household consumption credit
3        labor market matching
4        apply labor outcomes and synchronize firm rosters
5        apply firm production and costs
5b       withdraw deposits for planned consumption shortfall
6        goods market clearing
6.1      service infrastructure expansion
6.5      housing rental clearing and repairs
6.6      housing unit expansion
6.6b     housing mortgage service/origination
6.7      misc firm beneficiary/revenue redistribution
6.8      queue-based healthcare processing
7        government tax planning
8        government transfer planning
8.5      recycle capital investment spending
9        apply firm sales, profits, taxes, price/wage updates
9.5      bank loan repayments
10       apply household income, taxes, transfers, purchases
11       apply government fiscal results
11.3     bank deposit sweep and interest
11.4     bank credit scoring and cleanup
11.5     government discretionary spending
11.6     firm R&D spending and investment tax
11.7     final budget-pressure update
11.75    household wellbeing update
12       firm bankruptcies/exits
13       firm entry
14       legacy automatic government policy, disabled when LLM government is enabled
15       world statistics and diagnostics
16       dividends, household ledger finalization, affordability telemetry, audit snapshot, clock increment
```

Race-condition rules:

- Plans are computed before outcomes are applied. Keep planning dicts immutable in spirit after their phase unless a later phase explicitly owns adjustment.
- Do not let WebSocket config updates mutate economy internals mid-phase. `SimulationManager.run_loop()` applies pending config updates before `economy.step()`.
- Do not advance `current_tick` until all phase work, audit capture, ledgers, dividends, and telemetry finish.
- Any new state that is read by later phases must be initialized/reset in the prelude or constructor, not via opportunistic `hasattr`.
- Preserve deterministic ordering in labor matching, firm iteration, household IDs, and tie-breaks.

## Market-Clearing Guardrails

- `Economy._clear_goods_market()` is a core invariant surface. Changes require full regression tests over contract tests and at least one deterministic integration run.
- Do not modify allocation, supply caps, effective prices, unmet demand accounting, or per-firm/per-household sales schemas without tests covering cash conservation, inventory bounds, unmet demand, and deterministic replay.
- Keep market-clearing math vectorized where possible, but do not sacrifice deterministic first/ordered semantics where the model depends on them.
- No changes to a market-clearing matrix/allocation algorithm without comparing before/after outputs using fixed `CONFIG.random_seed`.

## LLM And LangGraph Guardrails

- LLM government is opt-in via `CONFIG.llm.enable_llm_government`; deterministic government policy still applies when LLM is disabled.
- `backend/tools/llm/llm_government.py` uses async provider calls and `graph.ainvoke()` when LangGraph is installed; fallback follows the same explicit node sequence.
- Any policy-system change must be audited for async consistency: no un-awaited provider calls, no blocking network calls inside the event loop, no background mutation of economy state after `decide()` returns.
- Policy decisions must flow through observe -> constrain -> decide -> apply/fallback -> log semantics and preserve `current_policy_before`, `current_policy_after`, allowed action masks, rejected changes, and decision history.
- Update `backend/policy_schema.py` when adding/removing policy levers, and keep prompt schema, runtime normalization, warehouse policy actions, and UI labels consistent.
- LLM policy must not bypass fiscal guardrails, bailout constraints, or warmup/start-tick gating.

## WebSocket/API Contract

- Primary live protocol is FastAPI WebSocket `/ws`.
- Client commands include setup/start/stop/reset/config update patterns handled in `server.py`.
- Server emits compact live tick state and keeps richer exact rows for warehouse persistence.
- Keep payload names camelCase for frontend compatibility.
- Validate setup/config inputs through existing Pydantic models and manager methods.

## Testing Expectations By Change Type

- Tick ordering, accounting, market clearing, banking, housing, healthcare, or government fiscal changes: run `python -m pytest backend/tests_contracts backend/tests_server -q`.
- LLM/policy changes: run stable tests plus targeted `backend/tests_contracts/test_contracts_llm.py` when applicable; use `backend/tools/llm/run_llm_government_test.py` for manual deterministic smoke checks.
- Frontend changes: run `npm run lint` and `npm run build` in `frontend-react`.
- Performance-sensitive simulation changes: test at small deterministic scale first, then run a larger fixed-seed scenario with `backend/tools/runners/run_large_simulation.py` or the relevant runner.

## Agent Operating Rules

- Read the code before editing; this repository has stale docs and deliberate monoliths.
- Keep changes scoped. Avoid opportunistic refactors in `agents.py`, `economy.py`, or `App.jsx`.
- Preserve deterministic seeds and ordered outcomes.
- Prefer vectorized NumPy on hot paths, but preserve model semantics over cosmetic vectorization.
- Add regression coverage when touching shared simulation behavior.
- Do not change public JSON shape, config names, or warehouse row schemas casually.
- Do not introduce new dependencies unless they are necessary and fit the existing Python/FastAPI or Vite/React stack.
