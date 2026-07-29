# Full App Evidence Test

## Purpose

Prove the real EcoSim application path: React dashboard, FastAPI server, WebSocket simulation stream, live warehouse writes, and REST readback. This is not a unit-test bundle and not a benchmark suite. It is an evidence-producing system test for claims an engineer can audit.

## Scope

In scope:

- Real backend process: `python -m uvicorn backend.server:app`.
- Real React dashboard process: `npm run dev`.
- Real browser-rendered dashboard.
- Real WebSocket stream from `/ws`.
- No-LLM simulation run with default/rule-based policy behavior.
- Live warehouse persistence enabled during the server tick loop.
- REST readback from the same persisted run.

Out of scope:

- LLM government calls, due to cost/rate limits. Zero LLM decision rows are expected.
- Full offline policy forecasting sweep.
- Synthetic DB rows inserted by test fixtures.
- Frontend click/action latency. The dashboard is mostly a streaming UI; stream health matters more.

## Validity Standard

A claim is defensible only when the evidence comes through the same path as the claim.

- Direct / Strong: browser + real server + real WebSocket + live warehouse + REST readback.
- Direct / Partial: real server/WebSocket, but browser evidence is limited to load/connect/render checks.
- Indirect: direct Python calls into `SimulationManager`, `Economy`, or `DatabaseManager`.
- Synthetic: mocks, monkeypatches, or pre-seeded rows.
- Not proven: no artifact connects the test path to the claim.

## Required Evidence

The harness must write one artifact directory containing:

- Backend log excerpt and process exit status.
- Frontend log excerpt and process exit status.
- Browser console errors/warnings.
- WebSocket frame summary: first tick, last tick, frame count, stream duration, frames/sec.
- WebSocket payload summary: min/p50/p95/max payload bytes and total bytes streamed.
- Stream shape summary: top-level keys observed, tracked subject count, firm count, history sizes when present.
- Warehouse run id and SQLite DB path.
- REST readback counts for runs, tick metrics, summary, decision features, sector metrics, diagnostics, and LLM decisions.
- SQLite table counts for the same run.
- Hash of REST tick metrics rows.
- Duplicate event-key query results for event/audit tables.
- A compact claim ledger.

## Claim Ledger

Each claim must be reported as:

```text
Claim:
Validity:
Evidence:
Artifact:
Still separate or unproven:
```

Minimum claims:

- React dashboard loads and observes the live stream.
- Server runs a real simulation through `/ws`.
- WebSocket stream is measurable and bounded for payload size/count.
- Warehouse rows are written during the live run.
- REST endpoints return persisted data from the same run.
- LLM government is disabled and LLM decision rows are not expected.
- Forecasting remains separate unless it consumes this live-persisted run.

## Recommended Harness

Create one reusable script, preferably `backend/tools/integration/run_full_app_evidence.py`.

The script should:

1. Start backend with `ECOSIM_ENABLE_WAREHOUSE=1`, `ECOSIM_WAREHOUSE_BACKEND=sqlite`, and a temporary SQLite path.
2. Start frontend with `VITE_WS_URL=ws://127.0.0.1:<backend_port>/ws`.
3. Open the dashboard in a browser.
4. Drive the run through the fastest real app-compatible path.
5. Capture WebSocket stream metrics while the browser validates load/connect/render health.
6. Stop the run after a fixed tick target.
7. Read the run back through REST.
8. Query SQLite for table counts and duplicate keys.
9. Write JSON, CSV, logs, and a Markdown evidence ledger.

## Defensible Wording

Good claim:

> The no-LLM EcoSim app path was exercised through a real backend, real React dashboard, real WebSocket tick stream, live SQLite warehouse writes, and REST readback for the same run id.

Bad claim:

> The whole system is fully tested.

The test proves one representative real-use path. It does not prove every policy, every frontend view, LLM behavior, forecasting integration, or Postgres live persistence unless those are added as explicit evidence checks.
