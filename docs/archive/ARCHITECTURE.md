# Architecture

## Overview

EcoSim is an agent-based simulation with three primary actor types:

- Households
- Firms
- Government

The system runs as a tick-based loop and can be observed in real time through a React dashboard connected to a FastAPI WebSocket stream.

## Runtime Topology

```text
frontend-react (UI)
    -> WebSocket
backend/server.py (simulation manager + stream emitter)
    ->
backend/economy.py (tick coordinator)
    ->
backend/agents.py (HouseholdAgent, FirmAgent, GovernmentAgent)
    +
backend/config.py (tunable simulation parameters)
```

## Core Responsibilities

### `backend/server.py`

- Starts, stops, and resets simulations
- Accepts runtime configuration updates
- Streams aggregate and sampled entity metrics to the frontend

### `backend/economy.py`

- Owns the simulation tick lifecycle
- Coordinates interactions between households, firms, and government
- Maintains performance-oriented lookup structures

### `backend/agents.py`

- Implements behavior and state transitions for each actor type
- Encapsulates labor, production, pricing, wellbeing, and policy behavior

### `backend/config.py`

- Centralized simulation tuning via hierarchical config objects
- Allows feature and policy behavior changes without rewriting core logic

## Tick Lifecycle (Conceptual)

Each tick executes a fixed sequence of phases. At a high level:

1. Planning: labor, production, and household demand intents
2. Matching/Clearing: labor allocation and goods purchases
3. Accounting: wages, cash flows, taxation, and transfers
4. Dynamics: wellbeing updates, firm entry/exit, policy adjustments
5. Metrics: aggregate values emitted for charts and analysis

See `backend/economy.py` for exact phase order and implementation details.

## Data Flow

### Real-time flow

1. Frontend sends commands/config changes over WebSocket
2. Server applies updates and advances ticks
3. Server emits metrics snapshots each update cycle
4. Frontend renders charts, KPIs, and event logs

### Batch flow

- `backend/generate_sample_data.py` creates SQLite outputs for analysis and demos
- `backend/generate_training_data.py` creates policy/outcome datasets
- `backend/train_ml_model.py` trains models against generated datasets

## Performance Notes

- Simulation is designed for deterministic phase ordering per tick
- Large runs rely on cached lookups and controlled recomputation
- Streaming paths prioritize responsiveness while simulation is running

## Design Principles

- Keep policy and behavior explicit in code/config
- Prefer transparent simulation steps over hidden side effects
- Separate simulation core from UI concerns
- Treat generated artifacts as local outputs, not source files
