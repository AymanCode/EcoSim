# Tests and startup validation

## Routine checks

Run from the repository root in a Python 3.11 virtual environment:

```bash
python -m pip install -c backend/requirements.lock -e ".[test,ml]"
python -m ruff check .
python -m pytest --durations=10
```

The default pytest configuration runs `backend/tests_contracts`, `backend/tests_server`, and `backend/data/tests` once each. Unknown markers fail collection. `llm` marks deterministic, provider-free tests using mock responses; they run by default. `research` marks exploratory economic-response checks and is excluded by default.

| Suite | Purpose | Focused command |
|---|---|---|
| Simulation contracts | Accounting, agents, markets, policy, institutions, and harness helpers | `python -m pytest backend/tests_contracts` |
| Server | API contracts, session isolation, configuration/RNG ownership, mocked LLM scheduling | `python -m pytest backend/tests_server` |
| Warehouse | SQLite schema, atomic writes, snapshots, and readback | `python -m pytest backend/data/tests` |
| Mocked LLM contracts | Provider request/retry handling, policy schema, prompts, sanitization, scheduling | `python -m pytest -m llm` |
| Exploratory research | Post-warmup policy-response expectations | `python -m pytest -m research` |
| Forecasting | Configuration, dataset, distress, splits, and baseline predictors | `python -m pytest policy_forecasting/tests` |
| Dashboard | Component/session lifecycle, lint, and production build | `cd frontend-react && npm run lint && npm test && npm run build` |

Forecasting CI installs its own frozen `policy_forecasting/requirements.txt` in a separate environment. Frontend CI uses Node 22, installs with `npm ci --no-audit --no-fund`, and runs one explicit high-severity production dependency audit. The general `dev` extra remains available for optional formatter, type-checker, and coverage tools; backend CI uses the smaller `test` extra plus `ml`.

## Fresh Docker startup

CI builds both images and starts the documented Compose stack with a fresh volume. After healthchecks pass, it runs:

```bash
docker compose exec -T backend python -m backend.tools.integration.smoke_startup --url http://frontend --sqlite-path /app/runtime/ecosim.db
```

The probe creates a small 30-household simulation with a unique identifier, checks the HTML and built JavaScript/CSS assets through Nginx, checks the proxied health route, connects through the real WebSocket proxy, observes two advancing ticks, receives STOP and RESET acknowledgements, and reads back that exact run and its saved ticks from SQLite. Reads use SQLite read-only mode. A healthy process alone is insufficient: missing persistence, invalid assets, server errors, or non-advancing ticks fail the probe.

The probe is intended for a disposable validation stack and leaves a small run record. CI prints container diagnostics on failure and removes its own containers and test volume afterward. Ordinary users should use `docker compose down` without `--volumes` to retain saved experiments. `ECOSIM_PORT` changes the host port without changing internal service addresses.

Compose rotates each service's logs at 10 MB with three files retained, preventing unbounded container logs. SQLite experiment history remains persistent and requires an explicit user reset; see the [Docker storage cleanup commands](../../README.md#docker-storage-cleanup).

This is a protocol/deployment smoke check, not a real browser test. The [full-app evidence harness](full_app_evidence_test.md) remains the browser/performance workflow. Neither routine pytest nor the startup probe makes live LLM requests, runs the large research sweeps, or verifies PostgreSQL/TimescaleDB. CI currently validates changes; it does not deploy releases.

## September 2026 review decisions

- Removed the duplicate CI execution of `test_server_api.py`; server and warehouse coverage remain in the default suite.
- Enabled the 52 previously excluded mocked LLM tests after verifying they pass without a provider.
- Removed real retry/shutdown waits from two mocked tests. The retry test still verifies the delay requested and the number of attempts.
- Removed two permanently skipped `TestDynamicDepositRate` tests. Their factory never supplied a bank, and their reserve-driven expectations predated the current floating-spread policy. Five active deposit-rate tests in `test_contracts_bank.py` cover the formula, bootstrap behavior, spread cap, thin loan book, and sustainability limit.
- Removed silent missing-metric fallbacks from policy sweeps and deterministic replay checks, so absent observations can no longer pass as matching zeros.
- Corrected the stale spawning description in `test_contracts_macro_modules.py` to match the tested competitor-entry behavior.
- Retained the strict expected failure for three-worker distressed-firm downsizing; it records an unresolved behavior gap rather than redundant coverage.
- Retained the eight research-marked tests outside the default gate. They passed during review, but exploratory directional expectations still need separate interpretation.
- Retained manual diagnostics under `backend/tools/checks` and `backend/data/test_sample_data.py` outside test discovery. Some are legacy research/data-generation utilities with side effects, not interchangeable pytest suites.

Review baseline: all 323 active non-research backend tests passed before cleanup; two tests skipped and one expected failure remained. The same 323 passed afterward with no skips and the same expected failure. On the review Mac, pytest's reported time fell from 10.04 seconds to 4.50 seconds after eliminating waits; this is a local measurement, not a CI runtime guarantee. The new Docker job adds deployment validation work, so total CI time is not claimed to decrease by that amount.

The dashboard currently has one component test, and forecasting model tests exercise persistence/trend baselines rather than fitting the full model suite. These are coverage limitations, not reasons to delete the existing checks.
