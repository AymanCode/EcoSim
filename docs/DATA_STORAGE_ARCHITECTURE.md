# EcoSim Data Storage Architecture and Database Plan

This document captures the current storage direction for EcoSim so the project
does not drift into ad hoc telemetry, one-off tables, or frontend-only state.

It answers five questions:

1. Why does EcoSim need a database at all?
2. Which database should be used?
3. What data should be stored, and how often?
4. What should stay in memory versus move into storage?
5. How does this support the frontend, policy logic, and the optional LLM
   government?

## Executive Summary

EcoSim should use `PostgreSQL + TimescaleDB` as its local warehouse.

The database is not meant to replace the live websocket update path. The
simulation should continue to run in memory and stream a compact live payload to
the frontend. The database should act as the durable system of record for run
history, trend analysis, event logs, agent snapshots, and policy decision
context.

This gives EcoSim:

- fast in-memory simulation
- live frontend responsiveness
- historical run analysis
- a clean source of truth for policy agents and run comparison
- durable audit records for policy and LLM decisions

## Design Principles

The storage design should follow these rules:

1. Do not put the hot simulation loop behind database reads.
2. Do not replace live websocket updates with database polling.
3. Store enough detail to explain what happened, but not so much that writes
   become the bottleneck.
4. Prefer append-only metrics and event logs over destructive updates.
5. Separate live decision features from raw historical telemetry.
6. Make the schema understandable enough that a new reader can reason about the
   simulation from the data model alone.

## Why EcoSim Needs a Database

Right now the frontend sees the current state because the backend pushes small
live updates over the websocket. That is useful for visualization, but it does
not give the system durable memory.

Without a database, EcoSim cannot easily answer:

- What changed over the last 50 ticks?
- Which firms were responsible for unemployment spikes?
- How many hires and layoffs happened after a policy change?
- Did healthcare queues worsen before household health collapsed?
- Which policies worked best across runs with different seeds?

This matters for three active product directions:

1. Policy evaluation
2. Government agent / LLM decision-making
3. User-facing analytics and policy advisor features

## Storage Roles: What Lives Where

EcoSim has three distinct data layers.

### 1) In-memory simulation state

This is the source of truth during a tick.

Examples:

- household objects
- firm objects
- government object
- live labor matching state
- healthcare queues
- rolling feature windows used for immediate decisions

Reason:

- lowest latency
- no serialization overhead
- required for tick performance

### 2) Websocket live transport

This is the frontend's live view of the simulation.

Examples:

- current tick
- current macro metrics
- recent chart points
- tracked subjects
- selected firm details

Reason:

- immediate UI updates
- lightweight push model
- should remain compact

### 3) Database warehouse

This is the durable historical record.

Examples:

- runs and configs
- aggregate tick metrics
- sector metrics
- firm snapshots
- sampled household snapshots
- labor and healthcare events
- policy actions
- derived decision features

Reason:

- long-term memory
- SQL analysis
- replay and comparison
- LLM/RAG support

## Recommended Database Choice

Use `PostgreSQL + TimescaleDB`.

### Why this is the best fit

1. The data is relational.
   Households, firms, runs, sectors, policies, and events all relate to each
   other in structured ways.

2. The data is time-series.
   Most analysis depends on ticks, windows, deltas, and trends.

3. SQL is the right language for this workload.
   The project will need grouping, joins, filtering, trend analysis, and run
   comparisons.

4. It works locally.
   This project does not need paid cloud infrastructure to have a serious data
   backend.

5. It keeps the production architecture legible.
   A relational time-series warehouse is easier to operate, validate, and
   explain than ad hoc local files or frontend-only state.

### Why not SQLite as the main target

SQLite is useful for a prototype, but it is not the long-term target because:

- single-writer behavior becomes limiting
- it is less convincing as the main analytics backend
- extension path for heavier time-series workloads is weaker

SQLite can still remain as a development fallback.

### Why not MongoDB

MongoDB is a weak fit here because:

- the data is not naturally document-first
- time-series plus relational analysis is central to the project
- events, snapshots, and aggregates are easier to reason about in SQL

### Why not DuckDB as the main store

DuckDB is excellent for local analytics, but not ideal as the primary live
application warehouse. It is more compelling later as an export or offline
analysis companion than as the main persistence layer.

## Current State in the Repo

The project already has the beginning of a warehouse layer:

- `backend/data/warehouse_factory.py`
- `backend/data/postgres_manager.py`
- `backend/data/postgres_schema.sql`

Currently implemented table families:

1. `simulation_runs`
2. `tick_metrics`
3. `sector_tick_metrics`
4. `firm_snapshots`
5. `household_snapshots`
6. `tracked_household_history`
7. `labor_events`
8. `healthcare_events`
9. `policy_actions`
10. `decision_features`
11. `tick_diagnostics`
12. `sector_shortage_diagnostics`
13. `regime_events`
14. `llm_government_decisions`
15. `policy_config`

That is enough for current run metadata, aggregate trends, sector trends,
agent snapshots, policy history, compact decision context, explainability
diagnostics, and full LLM government decision audit records. The warehouse is
still intentionally not a full exact-replay engine or BI-grade observability
platform.

## Target Logical Data Model

EcoSim currently uses seven logical data families.

### 1) Run metadata

Purpose:

- define one simulation run
- capture its setup, identity, and final outcome

Tables:

- `simulation_runs`
- `policy_config`

### 2) Aggregate tick metrics

Purpose:

- capture economy-wide behavior every tick
- support charting, trend analysis, and comparisons

Tables:

- `tick_metrics`
- `sector_tick_metrics`

### 3) Firm state

Purpose:

- explain firm-side dynamics over time
- diagnose hiring, pricing, inventory, profitability, and distress

Tables:

- `firm_snapshots`

### 4) Household state

Purpose:

- explain labor, health, and wealth changes at the agent level
- support detailed diagnostics and sampled trajectory analysis

Tables:

- `household_snapshots`
- `tracked_household_history`

### 5) Events

Purpose:

- record meaningful changes rather than only final state
- support causal analysis

Tables:

- `labor_events`
- `healthcare_events`
- `policy_actions`
- optional `firm_events` if firm-level transitions need more detail later

### 6) Derived policy decision context

Purpose:

- provide trend-aware compact features for automated decision-making
- avoid forcing policy agents to read raw tables every tick

Tables:

- `decision_features`

### 7) LLM government decisions

Purpose:

- preserve the full model response and validation outcome
- separate the full decision artifact from per-lever `policy_actions`
- support policy quality analysis, accepted/rejected change review, and provider
  reliability checks

Tables:

- `llm_government_decisions`

## Proposed Tables

The table list below is the current target architecture. It is acceptable to
implement it in phases.

### `simulation_runs`

One row per run.

Core fields:

- `run_id`
- `created_at`
- `ended_at`
- `status`
- `seed`
- `num_households`
- `num_firms`
- `total_ticks`
- `description`
- `tags`
- final summary metrics

### `policy_config`

One row per run.

Core fields:

- tax rates
- minimum wage
- unemployment benefit rate
- UBI
- inflation settings
- agent stabilizer flags
- policy mode flags

### `tick_metrics`

One row per run per tick.

Core fields:

- `run_id`
- `tick`
- `tick_duration_ms`
- `gdp`
- `unemployment_rate`
- `labor_force_participation`
- `mean_wage`
- `median_wage`
- `open_vacancies`
- `total_hires`
- `total_layoffs`
- `avg_happiness`
- `avg_health`
- `avg_morale`
- `total_net_worth`
- `gini_coefficient`
- `top10_wealth_share`
- `bottom50_wealth_share`
- `gov_cash_balance`
- `gov_profit`
- `healthcare_queue_depth`
- `avg_food_price`
- `avg_housing_price`
- `avg_services_price`

This is the primary charting and trend table.

### `sector_tick_metrics`

One row per run per tick per sector.

Purpose:

- preserve sector-level detail without forcing full firm scans for every query

Core fields:

- `run_id`
- `tick`
- `sector`
- `firm_count`
- `employees`
- `vacancies`
- `mean_wage_offer`
- `mean_price`
- `mean_inventory`
- `total_output`
- `total_revenue`
- `total_profit`

### `firm_snapshots`

One row per run per tick per firm.

Purpose:

- diagnose which firms are driving labor and pricing behavior

Core fields:

- `run_id`
- `tick`
- `firm_id`
- `sector`
- `employees`
- `planned_hires`
- `planned_layoffs`
- `wage_offer`
- `price`
- `inventory`
- `cash_balance`
- `revenue`
- `profit`
- `is_struggling`

At 300 to 500 firms, storing this every tick is reasonable.

### `household_snapshots`

One row per sampled run/tick/household.

Purpose:

- preserve agent-level state without requiring event reconstruction only

Core fields:

- `run_id`
- `tick`
- `household_id`
- `state`
- `medical_status`
- `employer_id`
- `is_employed`
- `can_work`
- `cash_balance`
- `wage`
- `last_wage_income`
- `last_transfer_income`
- `last_dividend_income`
- `reservation_wage`
- `expected_wage`
- `skill_level`
- `health`
- `happiness`
- `morale`
- `food_security`
- `housing_security`
- `unemployment_duration`
- `pending_healthcare_visits`

This is the most expensive table and should be sampled carefully.

### `tracked_household_history`

This is a narrower companion table for a small tracked subset of households.

Purpose:

- preserve high-frequency subject trajectories for debugging and demos

Core fields:

- `run_id`
- `tick`
- `household_id`
- `state`
- `medical_status`
- `employer_id`
- `is_employed`
- `can_work`
- `cash_balance`
- `wage`
- `expected_wage`
- `reservation_wage`
- `health`
- `happiness`
- `morale`
- `skill_level`
- `unemployment_duration`
- `pending_healthcare_visits`

### `labor_events`

One row per hire, layoff, or labor state transition.

Purpose:

- reconstruct labor dynamics
- explain unemployment changes without full agent snapshots every tick

Core fields:

- `run_id`
- `tick`
- `household_id`
- `firm_id`
- `event_type` (`hire`, `layoff`, `quit`, `forced_exit`)
- `actual_wage`
- `wage_offer`
- `reservation_wage`
- `skill_level`

### `healthcare_events`

One row per meaningful healthcare interaction.

Purpose:

- diagnose queue pressure and care access

Core fields:

- `run_id`
- `tick`
- `household_id`
- `event_type` (`visit_started`, `visit_completed`, `visit_denied`)
- `queue_wait_ticks`
- `visit_count`
- `health_before`
- `health_after`

### `policy_actions`

One row per policy or government action.

Purpose:

- preserve an auditable policy timeline

Core fields:

- `run_id`
- `tick`
- `actor`
- `action_type`
- `payload_json`
- `reason_summary`

### `decision_features`

One row per run per tick.

Purpose:

- provide compact trend-aware context for policy logic and the LLM government

Core fields:

- `run_id`
- `tick`
- `unemployment_short_ma`
- `unemployment_long_ma`
- `inflation_short_ma`
- `hiring_momentum`
- `layoff_momentum`
- `vacancy_fill_ratio`
- `wage_pressure`
- `healthcare_pressure`
- `consumer_distress_score`
- `fiscal_stress_score`
- `inequality_pressure_score`

This table is for decision support, not raw storage fidelity.

### `llm_government_decisions`

One row per full LLM government decision.

Purpose:

- keep the raw/validated policy decision auditable
- preserve accepted changes, rejected changes, rationale, evidence, provider,
  model, snapshot tick, applied tick, and error state
- avoid overloading `policy_actions`, which remains the per-applied-lever
  timeline

Current implementation notes:

- moving-average windows are currently `5` ticks (short) and `20` ticks (long)
- `inflation_short_ma` currently uses the percentage change of a simple
  consumer basket built from mean `Food`, `Housing`, and `Services` prices
- `hiring_momentum` and `layoff_momentum` are computed as short minus long
  averages of hires / layoffs per 100 households
- `vacancy_fill_ratio` is current tick `hires / vacancies`, clamped to `[0, 1]`
- `wage_pressure` is the unemployed expected-wage gap relative to current mean
  wage, guarded by the minimum-wage floor to avoid unstable divisions
- `healthcare_pressure` is queue depth per healthcare staff member
- `consumer_distress_score` is a weighted score from unemployment, low cash,
  low health, and low happiness
- `fiscal_stress_score` is a weighted score from negative government cash and
  negative fiscal flow relative to current GDP
- `inequality_pressure_score` combines Gini with the `top10 - bottom50` wealth
  concentration gap

## Concrete Schema Rules

The storage layer should follow a few hard rules from the beginning so the
warehouse does not become slow or inconsistent later.

### Primary key strategy

Use narrow composite keys based on the natural grain of the table.

- `simulation_runs`: `run_id`
- `policy_config`: `run_id`
- `tick_metrics`: `(run_id, tick)`
- `sector_tick_metrics`: `(run_id, tick, sector)`
- `firm_snapshots`: `(run_id, tick, firm_id)`
- `household_snapshots`: `(run_id, tick, household_id)`
- `tracked_household_history`: `(run_id, tick, household_id)`
- `decision_features`: `(run_id, tick)`
- `llm_government_decisions`: `(run_id, snapshot_tick, applied_tick)` plus
  query indexes by run/tick

For event tables, use a surrogate event id plus the natural filtering columns:

- `labor_events`: `event_id BIGSERIAL`
- `healthcare_events`: `event_id BIGSERIAL`
- `policy_actions`: `action_id BIGSERIAL`

Reason:

- snapshot and aggregate tables have a natural grain already
- event tables may have multiple rows per household per tick
- using composite natural keys for snapshots avoids redundant row ids

### Foreign key strategy

All fact tables should reference `simulation_runs(run_id)`.

Do not add heavy foreign keys from every snapshot/event row to firms or
households unless needed for correctness. Those relations are logically real,
but strict FK enforcement on every large fact table can add overhead with little
benefit in a local analytics warehouse.

Working rule:

- hard FK to `simulation_runs`
- soft logical relationships to `firm_id`, `household_id`, and `sector`

### Indexing strategy

Indexes should support the common read paths, not every possible query.

Create these baseline indexes:

- `tick_metrics`: `(run_id, tick)`
- `sector_tick_metrics`: `(run_id, tick)`, `(run_id, sector, tick)`
- `firm_snapshots`: `(run_id, tick)`, `(run_id, firm_id, tick)`, `(run_id, sector, tick)`
- `household_snapshots`: `(run_id, tick)`, `(run_id, household_id, tick)`, `(run_id, state, tick)`
- `tracked_household_history`: `(run_id, household_id, tick)`
- `labor_events`: `(run_id, tick)`, `(run_id, household_id, tick)`, `(run_id, firm_id, tick)`, `(run_id, event_type, tick)`
- `healthcare_events`: `(run_id, tick)`, `(run_id, household_id, tick)`
- `policy_actions`: `(run_id, tick)`, `(run_id, action_type, tick)`
- `decision_features`: `(run_id, tick)`

Do not create indexes on low-value float columns such as wages, prices, or
health metrics unless a specific query pattern proves they are needed.

### Data type strategy

Use:

- `TEXT` for ids and small categorical values
- `INTEGER` for tick counts and ids where applicable
- `DOUBLE PRECISION` for metrics and money-like values
- `BOOLEAN` for flags
- `TIMESTAMPTZ` for wall-clock timestamps
- `JSONB` only for payloads that are naturally semi-structured

Avoid using `JSONB` as a shortcut for core snapshot schema. It is tempting early
on, but it makes indexing, validation, and long-term analysis harder.

Allowed `JSONB` usage:

- `policy_actions.payload_json`
- optional debugging payloads that are not part of the hot query path

### Time-series strategy

Use Timescale hypertables for the largest tick-oriented fact tables:

- `tick_metrics`
- `sector_tick_metrics`
- `firm_snapshots`
- `household_snapshots`
- `tracked_household_history`
- `decision_features`

Event tables can remain standard Postgres tables initially. If event volume
grows enough, they can be converted later.

### Compression and retention strategy

Do not introduce retention deletion policies yet.

This project is still building its core analytical value, so history is more
valuable than aggressive cleanup.

Compression should be considered only after the schema stabilizes and query
patterns are known. The immediate priority is correct grain and clean write
paths.

## Write Cadence Strategy

Not every table should be written at the same frequency.

### Record every tick

- `tick_metrics`
- `sector_tick_metrics`
- `firm_snapshots`
- `decision_features`

Reason:

- high value
- moderate row counts
- critical for trend awareness

### Record every event

- `labor_events`
- `healthcare_events`
- `policy_actions`

Reason:

- sparse compared to snapshots
- high explanatory power

### Record every 5 ticks by default

- `household_snapshots`

Reason:

- 10k households x every tick becomes large quickly
- every 5 ticks still preserves strong analytical value
- cadence can be made configurable

### Record every tick for a small tracked subset

- `tracked_household_history`

Reason:

- supports rich demos and debugging without full-table cost

## Why This Cadence Makes Sense

The most expensive storage choice is full-population household snapshots every
tick.

At 10k households, the data volume grows fast. That does not make it impossible,
but it means household storage needs to be intentional.

The recommended compromise is:

- full macro and firm visibility every tick
- full labor and healthcare events
- full household state every 5 ticks
- tracked household state every tick

If profiling later shows that full household snapshots every tick are affordable,
the cadence can be tightened. The design should make this configurable rather
than hard-coded.

## Read Paths

This architecture works only if reads are cleanly separated.

### Frontend live path

Source:

- websocket

Payload:

- current tick
- current macro metrics
- recent chart deltas
- selected tracked subject data

Why:

- fastest path to the UI

### Frontend historical path

Source:

- REST or query endpoints backed by the database

Payload:

- chart history
- run summaries
- comparisons between runs
- sector views
- selected firm or household history

Why:

- avoids bloating the websocket with unbounded history

### Policy or LLM decision path

Source:

- in-memory rolling features during live execution
- database-backed history when broader context is needed

Why:

- live decisions should not depend on ad hoc raw database scans

## What the Database Should Not Do

The database should not:

- replace the live websocket channel
- become the per-tick source of truth for simulation objects
- force every decision-maker to query raw history tables
- store every possible derived number if it can be cheaply recomputed

The right storage model is "durable telemetry and history", not "database-first
simulation execution".

## Interaction With The LLM Government

The LLM government should not be handed large raw tables directly.

Instead, EcoSim should expose a compact decision context built from:

- current macro metrics
- short and long moving averages
- recent hiring and layoff momentum
- healthcare pressure
- inequality and fiscal stress signals
- the most recent policy actions

Those features are built in memory each tick and optionally persisted to
`decision_features` for analysis and auditability.

This keeps the agent grounded without flooding it with raw data.

Current implementation status:

- a live rolling decision window is maintained in memory by the server
- the same decision layer is persisted to `decision_features` when the
  warehouse is enabled
- the live window is exposed through `SimulationManager.get_live_decision_context()`
  and `GET /decision-context/live?session_id={session_id}`
- recent policy changes are included alongside the live rolling context
- full accepted/rejected LLM government decisions are persisted to
  `llm_government_decisions` when the warehouse is enabled

## Interaction With A Policy Advisor / RAG Layer

Any policy advisor should read from structured run history, not from
frontend-only state.

Good sources for that system:

- `simulation_runs`
- `policy_config`
- `tick_metrics`
- `sector_tick_metrics`
- `policy_actions`
- selected event tables

This will let the advisor answer questions such as:

- "What happened after unemployment benefits were increased?"
- "Which runs had the lowest unemployment without severe inflation?"
- "How did healthcare queues change after the labor market tightened?"

## Performance Expectations

A database will add some write overhead, but it should not dominate runtime if:

1. writes are batched
2. commits are not done per row
3. full household snapshots are sampled sensibly
4. the simulation continues to compute in memory

The current design already supports batched aggregate writes. The next storage
extensions should follow the same pattern.

## Concrete Migration Plan

This is the recommended migration sequence. The goal is to keep each migration
small, reversible in concept, and easy to validate.

### Migration 003: Expand aggregate warehouse

Goal:

- make the existing aggregate layer more useful without increasing row count too
  aggressively

Changes:

- extend `simulation_runs` with `seed` and optional run metadata fields
- extend `tick_metrics` with:
  - `tick_duration_ms`
  - `labor_force_participation`
  - `open_vacancies`
  - `total_hires`
  - `total_layoffs`
  - `healthcare_queue_depth`
- create `sector_tick_metrics`

Why first:

- highest analytical value per write cost
- directly helps the frontend, debugging, and policy features

### Migration 004: Add event tables

Goal:

- capture meaningful changes without full entity snapshots

Changes:

- create `labor_events`
- create `healthcare_events`
- create `policy_actions`

Why second:

- event logs explain causality well
- much cheaper than immediately storing every household every tick

### Migration 005: Add firm snapshots

Goal:

- give high-resolution firm visibility at low row-count cost

Changes:

- create `firm_snapshots`
- write one analytical row per firm per tick
- keep snapshot batching separate from aggregate batching so hundreds of firm
  rows do not force a database flush every tick

Why third:

- firms are only hundreds of rows per tick
- this is cheap relative to household snapshots

### Migration 006: Add household snapshot layer

Goal:

- preserve population-level state for deeper labor, wealth, and health analysis

Changes:

- create `household_snapshots`
- create `tracked_household_history`

Notes:

- `household_snapshots` should start with a configurable default cadence of
  every 5 ticks
- capture tick `1` as an early baseline, then continue on the configured stride
- `tracked_household_history` should record every tick for a small tracked set

### Migration 007: Add policy decision feature table

Goal:

- persist compact trend-aware features for automated policy logic

Changes:

- create `decision_features`

Why after raw facts:

- derived features should be informed by stable raw telemetry

Implementation note:

- backend scripts `011` (SQLite) and `012` (Postgres) implement this logical phase

### Migration 008: Add diagnostics and regime events

Goal:

- persist compact explanations for changes in unemployment, health, firm
  distress, housing failure, and sector shortages

Changes:

- create `tick_diagnostics`
- create `sector_shortage_diagnostics`
- create `regime_events`

### Migration 009: Add LLM government decision audit table

Goal:

- persist one full audit row per LLM government decision, separate from
  per-lever policy actions

Changes:

- create `llm_government_decisions`
- add read support through `GET /warehouse/runs/{run_id}/llm-government-decisions`

### Migration 010: Add analytical views and query helpers

Goal:

- support frontend history loading and comparison tools cleanly

Changes:

- run comparison views
- sector trend views
- optional decision-context views

## Validation Rules Per Migration

Each migration should be validated on three axes:

1. Schema correctness
- keys and indexes match the intended grain
- no duplicated row grain
- no unnecessary nullable fields in primary facts

2. Write-path cost
- batch inserts still work
- no per-row commits
- no accidental synchronous query-backs in the hot path

3. Query usefulness
- at least one real query or UI/API use case should justify the new table

If a table does not yet support a real query or product need, it should not be
added just because it "might be useful later".

## Anti-Patterns To Avoid

These are the patterns most likely to create slow or messy storage later.

Do not:

- store the full household object as a JSON blob each tick
- create one table per agent instance or one schema per agent type
- index every numeric field "just in case"
- force live simulation decisions to query the warehouse
- write one row at a time with its own commit
- make websocket payload shape the same thing as warehouse row shape

The warehouse should be designed for analytical clarity, not for mirroring raw
Python objects.

## Immediate Implementation Scope

The current implemented storage baseline includes:

1. `Migration 003`: aggregate expansion
2. `Migration 004` logically: event logging
3. `Migration 005` logically: firm snapshots
4. `Migration 006` logically: household snapshots + tracked-household history
5. `Migration 007` logically: compact decision features
6. `Migration 008` logically: diagnostics + regime events
7. LLM government decision persistence

Note:

- the backend scripts are numbered separately by backend (`005` for SQLite,
  `006` for Postgres) but they both implement the same logical event phase
- firm snapshots follow the same pattern with backend scripts `007` (SQLite)
  and `008` (Postgres)
- household snapshots follow the same pattern with backend scripts `009`
  (SQLite) and `010` (Postgres)
- decision features follow the same pattern with backend scripts `011`
  (SQLite) and `012` (Postgres)
- diagnostics/regime events follow the same pattern with backend scripts `015`
  (SQLite) and `016` (Postgres)
- full LLM government decisions follow the backend-specific migration pattern
  with scripts `017` (SQLite) and `018` (Postgres)

That means the next actual code changes should focus on:

1. validating write cost of the diagnostics layer alongside aggregates and events
2. keeping diagnostic definitions stable enough for policy comparisons
3. exposing only the smallest read/query surface needed by real product/debug use cases
4. keeping any new tables narrower than the snapshot layers unless there is a clear need

This preserves the incremental path: useful aggregates first, then
explainability via events, then heavier snapshot layers only when justified.

## Current Reliability Baseline

The warehouse now has a minimum hardening pass that is specifically aimed at
simulation debugging, policy analysis, and LLM-government work.

Implemented:

1. atomic flush bundles
- buffered rows across aggregates, decision features, snapshots, events, and the run watermark are committed in one transaction
- a failure mid-flush rolls the entire bundle back instead of leaving partial per-table commits

2. persisted run durability markers
- `simulation_runs.last_fully_persisted_tick`
- `simulation_runs.analysis_ready`
- `simulation_runs.termination_reason`

3. idempotent event writes
- `labor_events`, `healthcare_events`, and `policy_actions` now carry deterministic `event_key`
- retries use conflict-ignore semantics instead of duplicating append-only rows

4. minimal replay/debug manifest
- `seed`
- `config_json`
- `code_version`
- `schema_version`
- `decision_feature_version`

What this does not try to solve yet:

- full exact replay across every stochastic path
- full diagnostics / trace-mode coverage for every mechanic
- BI-grade warehouse semantics

That remains intentionally out of scope for this phase.

## Current Explainability Baseline

The warehouse now also has a compact explainability layer aimed at policy
debugging, not dashboard sprawl.

Implemented:

1. per-tick diagnostics
- `tick_diagnostics` stores compact explanations for changes in unemployment,
  health, firm distress, housing failure, and shortage breadth

2. sector shortage diagnostics
- `sector_shortage_diagnostics` stores one row per run/tick/sector
- each row carries a stable shortage flag, severity, and primary driver

3. high-value regime events
- `regime_events` stores sparse explicit transitions instead of forcing later
  inference from snapshots
- current focus:
  - `firm_distress_enter`
  - `firm_distress_exit`
  - `firm_bankrupt`
  - `failed_hiring`
  - `eviction`
  - `shortage_regime_enter`
  - `shortage_regime_exit`

Design constraints preserved:

- always-on and cheap
- no giant tracing subsystem
- no full per-agent reasoning logs
- compact enough to support policy/LLM context without drowning it in raw rows

## Implementation Phases

This should be delivered incrementally.

### Phase 1: strengthen aggregate history

Keep and extend:

- `simulation_runs`
- `policy_config`
- `tick_metrics`

Add:

- more macro metrics
- tick duration
- sector-level aggregates

### Phase 2: add event logging

Add:

- `labor_events`
- `healthcare_events`
- `policy_actions`

This gives strong explainability with modest write cost.

Status:

- implemented as the current event layer

### Phase 3: add state snapshots

Add:

- `firm_snapshots`
- `household_snapshots`
- `tracked_household_history`

Start with:

- every tick for firms
- every 5 ticks for households

### Phase 4: add decision context

Add:

- `decision_features`

This is the bridge between raw telemetry and policy-agent context.

Status:

- implemented as the current compact decision-context layer

### Phase 4b: add explainability diagnostics

Add:

- `tick_diagnostics`
- `sector_shortage_diagnostics`
- `regime_events`

This is the bridge between raw telemetry and policy explanation.

Status:

- implemented as the current compact explainability layer

### Phase 5: add product-facing query APIs

Add endpoints for:

- run history
- chart ranges
- run comparison
- sector drill-down
- firm and household timelines

Status:

- partially implemented with:
  - `GET /warehouse/runs`
  - `GET /warehouse/compare`
  - `GET /warehouse/runs/{run_id}/policy-context`
  - `GET /warehouse/runs/{run_id}/summary`
  - `GET /warehouse/runs/{run_id}/tick-metrics`
  - `GET /warehouse/runs/{run_id}/decision-features`
  - `GET /warehouse/runs/{run_id}/tick-diagnostics`
  - `GET /warehouse/runs/{run_id}/sector-metrics`
  - `GET /warehouse/runs/{run_id}/sector-shortages`
  - `GET /warehouse/runs/{run_id}/regime-events`
  - `GET /warehouse/runs/{run_id}/llm-government-decisions`

The `policy-context` surface is the compact read model intended for
government-agent and policy-analysis use. It keeps the interface small:

- rolling windows for macro metrics, decision features, and diagnostics
- current shortage state
- recent regime events
- recent policy actions with compact observed post-action deltas
- reconstructed current policy state from `policy_config + policy_actions`

## Architecture Value

This architecture keeps the system practical to operate:

1. The hot simulation path is separated from the persistence path.
2. Run history is durable and queryable without bloating websocket payloads.
3. State snapshots and event logs support causal analysis from different grains.
4. PostgreSQL plus TimescaleDB remains the target for time-series simulation metrics.
5. Policy-agent context uses compact derived features and full decision audit
   records rather than raw table dumps.

## Open Decisions

These are the main storage questions still worth validating with profiling:

1. Should `household_snapshots` default to every 1, 2, or 5 ticks?
2. Which household fields are essential versus recomputable?
3. Which sector metrics belong in `sector_tick_metrics` versus on-demand
   aggregation?
4. How much history should be streamed live to the frontend versus fetched on
   demand?
5. Which decision features should be computed in the simulation loop versus in
   offline SQL views?

## Current Working Decision

Until profiling proves otherwise, the project should proceed with this storage
policy:

- Database: `PostgreSQL + TimescaleDB`
- Simulation execution: in memory
- Live UI updates: websocket
- Durable history: database
- Tick metrics cadence: every tick
- Firm snapshot cadence: every tick
- Household snapshot cadence: every 5 ticks
- Event logging cadence: every event
- Policy/LLM context: compact rolling decision features

This is the current holistic storage plan for EcoSim.
