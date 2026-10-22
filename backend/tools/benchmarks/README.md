# EcoSim Benchmarks

Non-production benchmark CLIs for producing reproducible performance evidence.

Install the benchmark dependencies from the repository root:

```powershell
python -m pip install -c backend/requirements.lock -c backend/requirements-test.lock -e ".[dev,ml,benchmarks]"
```

## Simulation Throughput

```powershell
python -m backend.tools.benchmarks.run_sim_bench --households 1000,5000,10000 --ticks 80 --warmup-ticks 10 --seeds 42,43,44 --profile
```

Measures p50/p95/p99 tick duration, ticks/sec, memory RSS when available, and separates warmup from active private-market ticks.

## Warehouse Ingest

```powershell
python -m backend.tools.benchmarks.run_warehouse_bench --backend sqlite --households 1000,10000 --ticks 200
```

Measures rows/sec, tick-loop write overhead, flush p50/p95/p99 latency, query-suite latency, per-table row counts, SQLite file/WAL size, and database runtime metadata.

For PostgreSQL or TimescaleDB, start the database and set `ECOSIM_WAREHOUSE_DSN`, then use `--backend postgres` or `--backend timescale`.

## Policy Sweep

```powershell
python -m backend.tools.benchmarks.run_policy_sweep --seeds 42,43,44 --policies baseline,tax_grid,benefit_grid
```

Runs non-LLM policy grids and reports average outcomes plus 95% confidence intervals across seeds.

## Evidence Panel (PRs that change economic behavior)

```powershell
python -m backend.tools.benchmarks.run_evidence_panel --arm main --root main ../main --arm off --arm on --set on households.skills_dynamics=True --baseline main --jobs 2 --out benchmarks/results/pr51-panel
```

The standard evidence for a behavior-changing PR, so a reviewer reruns one command instead of rebuilding a study. Defaults use 1,000 households, 5 firms per category, all three payment sequences with `income_first` first, and seeds 42-46. The current town Run screen uses `legacy`; report that sequence first when interpreting user-visible effects. The checklist length is 312 ticks, windows 1-100 (reported, not judged) / 101-200 / 201-312 (judged) / 261-312 (judged). `--weeks 260` still runs; the last window is dropped and 201-312 is clipped to 201-260. A fragile judged result (fewer than 4/5 seeds agree, median and mean disagree in sign, or one seed carries more than half the delta) reruns seeds 47-54. Each arm, sequence and seed runs in its own process (`evidence_panel_worker.py`), built by the same `build_economy_from_setup` the server uses and observed each tick with the dashboard's own metric calls. The command refuses to start outside CPython 3.11 with packages matching `backend/requirements.lock` unless `--allow-nonref` is set, which permits the mismatch and stamps every output as non-reference. Local runs are always labelled non-reference. The reference environment is the GitHub-hosted Linux runner in the full tier, with CPython 3.11 and the runtime lock; the fast tier is CI smoke only. Platform, CPU model and runner image are recorded. **Compare arms within one run only:** absolute levels across runs or machines are not comparable even when version stamps agree.

- `--arm NAME` declares an arm; the first is the baseline unless `--baseline`. `--root ARM PATH` runs an arm from another checkout, such as `main` without the PR's flag.
- `--set ARM section.field=value` overrides a config field before the economy is built (an unknown or mistyped name fails the run). `--set ARM lever.name=value` applies a policy lever after it. `lever.name=value@WEEK` or `@WEEK..WEEK` applies it for that span and then restores the previous value. `--off-set KEY=VALUE` is `--set off`.
- `--sweep ARM section.field` adds arms at 0.5×, 1× and 1.5× the field's default. `--interact a:K=V b:K=V` adds arms a, b and a+b. `--hook ARM k06_hold_pool` keeps the misc pool from paying out.
- `--metrics-plugin FILE` may be repeated (one file per owner). FILE defines `extra_metrics(economy) -> dict[str, float]` and may define `METRICS` and `summarize(runs)`.
- `panel.md` gives, per sequence and window, the baseline level and the paired difference: mean, [min, max], median, and k/n seeds up. `!` marks a mean whose sign flips when one seed is left out. Identity is the per-week state digest of households, firms, government, bank, all bank-loan and housing-mortgage fields, payment-ledger totals, and Python/NumPy global RNG state. This is a diagnostic, not a complete engine checkpoint: ledger allocation identities, per-object RNGs, and some unreported internal state are omitted. income_first and income_late must conserve, including the baseline arm. legacy reports the drift gap and does not fail until #57. A NaN or inf drift always fails. Bounds / non-finite values and the determinism repeat fail the process. `evaluator.json` carries the env, the labour-force unemployment scores, and the panel. The layoffs column is planned layoffs per month.
- `summary.md` is the short CI job/sticky-comment report. Full tables, JSON, CSV and raw runs belong in CI artifacts (14-day retention), not committed evidence bundles.
- `--mutate-root PATH` chooses the candidate checkout for `--mutate` while the evaluator stays on base. Mutation overlays copy files if Windows denies symlinks. Lock hashes normalize CRLF to LF.
- Rerunning the same command reuses finished runs only when their settings, simulation source, measuring code, worker Python and numpy versions, `backend/requirements.lock` and thread settings are all unchanged; changing only `--windows` re-aggregates. Workers run with one numeric-library thread each (`OMP_NUM_THREADS=1` and the like) and refuse to start under a different interpreter than the one planned.

### CI trust and triggers

Fast panels run only on `pull_request` events against main: 5 seeds, 104 weeks, 3 sequences, main versus the candidate arm. The nightly full tier runs a 13-seed main-only baseline. A manual dispatch can add an on assignment, an off assignment, and seeds; authorized `/eval` comments and the `eval:full` label run the full main-versus-candidate panel. Comments are commands only: no comment content becomes shell input. All panel invocations use at most `--jobs 2`.

A trusted authorization job resolves immutable base/head SHAs before a full job enters its cancellable concurrency group. An unauthorized commenter acquires no group and cannot cancel a collaborator's run. For `/eval`, repository branch activity (including force pushes) reconstructs the head at comment creation; if that cannot be established within the latest 100 branch activities, the workflow fails closed and asks for a fresh `/eval` or the label. A force-pushed or newer head is never silently substituted. Fork activity may be unavailable to the read-only token; use a label whose event already carries the head SHA in that case.

The tool, worker, scoring code and installed locks come from the pinned main/base checkout (`evaluator/`); `candidate/` supplies only the simulation arm. In v2 the worker loads the shared `panel_money.py` beside its evaluator script, never the candidate test helper, so every arm uses the same money measurement. Both checkouts disable persisted credentials. Executing PR code has only `contents: read`, no shared pip cache or referenced secrets. A separate job posts only `summary.md` and the artifact link, checks that the current PR head still matches, and never checks out PR code. Fork PRs retain job summaries/artifacts without attempting a write-token comment.

**Bootstrap for #59:** main has panel v1 until this PR lands. The workflow uses that base version without copying the PR's evaluator over it; the backend CI suite tests v2 independently. The first fast artifact includes `execution.json` with base/head SHAs and host details plus a short v1 summary; v1 does not enforce the new v2 money/bounds gates. Full `/eval`/label triggers activate when the workflow is on main. After merge the base evaluator produces v2 `summary.md`, `evaluator.json`, lock/host stamps and gates. Inspect the evaluator SHA before interpreting a run.

Focused validation:

```powershell
python -m pytest backend/tests_contracts/test_evidence_panel.py backend/tests_contracts/test_money_helper_payment_holds.py -q
python -m ruff check .
```

The two locked-runtime integration tests skip with the mismatched pin names on non-reference machines; refusal behavior is tested separately with controlled inputs. Ubuntu CI is the authoritative full-suite result; Windows has known unrelated SIGALRM/encoding failures.

## Dashboard Probe

Start the backend first:

```powershell
python -m uvicorn backend.server:app --port 8002
python -m backend.tools.benchmarks.run_dashboard_bench --households 1000 --ticks 25
```

Measures WebSocket payload size, message cadence, and backend `tickComputeMs`.

## Frontend Browser

Start the backend and frontend first:

```powershell
python -m uvicorn backend.server:app --port 8002
cd frontend-react
$env:VITE_WS_URL = "ws://127.0.0.1:8002/ws"
npm run dev -- --host 127.0.0.1 --port 5173
cd ..
python -m backend.tools.benchmarks.run_frontend_bench --households 10000 --ticks 100
```

Launches Chrome through the Chrome DevTools Protocol, initializes the simulation through the real React UI, cycles dashboard views, and measures WebSocket payloads, JSON parse time, frame latency, long tasks, LCP, CLS, JS heap, DOM node count, and console errors.

## Outputs

By default, each command writes artifacts under:

```text
benchmarks/results/YYYY-MM-DD-HHMMSS-<benchmark>/
```

Each run includes raw JSON, CSV rows, a Markdown summary, and runtime metadata.
