---
type: technical guide
title: LLM government
description: Source-grounded guide to LLM government ownership, behavior, invariants, and safe change paths.
tags: [ecosim, repository-navigation]
okf:
  schema: openwiki-fact-v1
  subject: llm-government
  status: integrated-opt-in
  scope: simulator-only
  facts:
    - id: gov.provider
      claim: All government inference depends on the asynchronous LLMProvider complete, health_check, and name contract.
      evidence:
        - backend/tools/llm/llm_provider.py:38-71
        - backend/server.py:1401-1437
      confidence: high
    - id: gov.schedule
      claim: The server deep-copies the economy without its advisor, reasons in an asyncio background task, and applies a completed result only at a later tick boundary.
      evidence:
        - backend/server.py:1439-1484
        - backend/server.py:1486-1571
        - backend/tests_contracts/test_contracts_llm.py:1274-1308
      confidence: high
    - id: gov.observe
      claim: Observation combines current metrics, history, sector diagnostics, policy, fiscal telemetry, regime state, and a dynamically validated action mask; lag, noise, and coverage gaps are deterministic by seed, tick, and indicator.
      evidence:
        - backend/tools/llm/llm_government.py:1506-1586
        - backend/tools/llm/llm_government.py:1589-1620
      confidence: high
    - id: gov.validation
      claim: Changes are normalized and checked per lever and as atomic policy groups, with at most two substantive groups; mechanical corrections and rejection reasons remain distinct.
      evidence:
        - backend/tools/llm/llm_government.py:1993-2090
        - backend/policy_schema.py:1-160
      confidence: high
    - id: gov.telemetry
      claim: Live status and durable decision evidence retain snapshot and apply ticks, provider, model, parse state, latency, accepted and rejected changes, rationale, and evidence audit.
      evidence:
        - backend/server.py:1376-1399
        - backend/server.py:1573-1605
        - backend/server.py:1639-1678
      confidence: high
  gaps:
    - No provider call can make the simulator a model of a real government or justify real-world policy.
    - Deep-copy cost and stale-snapshot policy quality are not benchmarked here.
    - Provider availability and model output are nondeterministic external dependencies.
---

# LLM government

The only LLM consumer integrated into the live server is the **government advisor**, and it is disabled by default (`enable_llm_government: false`). When enabled, it replaces the legacy automatic policy chooser while deterministic simulator mechanics continue to execute accepted levers. Firm and household LLMs are separate experiments; see [Experiments and evaluation](experiments-and-evaluation.md#consumer-status-matrix).

## Provider boundary

`LLMProvider` exposes `complete(system, user, temperature, top_p, response_format)`, `health_check()`, and `name`. Implementations cover Ollama, LM Studio, OpenRouter, and Groq. `create_provider(config)` performs availability selection; failure changes server status to `provider_unavailable`, disables the feature, detaches the advisor, and leaves ordinary simulation usable. This is graceful feature degradation, not an inference fallback policy.

The role configuration lives in `LLMConfig`: provider endpoints and role models, government start/cadence, sampling, token budget, philosophy, memory window, impact horizon, and rolling windows. The unrelated `enable_llm_agents` flag is explicitly future-facing and has no live firm/household integration.

## Snapshot-to-apply lifecycle

```mermaid
sequenceDiagram
    participant Loop as Simulation loop
    participant SM as SimulationManager
    participant Snap as Frozen economy copy
    participant Adv as LLMGovernmentAdvisor
    participant Prov as LLMProvider
    participant Gov as Live GovernmentAgent
    participant WH as Warehouse buffers
    Loop->>SM: Check decision cadence
    SM->>Snap: Deep copy without advisor
    SM->>Adv: Start background decide
    Adv->>Prov: Complete constrained prompt
    Prov-->>Adv: Raw response
    Adv-->>SM: Validated decision with snapshot tick
    Loop->>SM: Enter next tick boundary
    SM->>Gov: set_lever for accepted changes
    SM->>Gov: begin_decision_cycle
    SM->>WH: Buffer decision and policy actions
```
*Caption: Source-grounded live path from a due tick’s isolated snapshot to non-blocking inference and later boundary application (`server.py:1439-1678`).*

Scheduling refuses a second in-flight task or a second pending result. The copied economy cannot mutate the live one. A completed task moves into a pending slot; task exceptions become a structured no-change/error record. Before the next `Economy.step`, live `GovernmentAgent.set_lever` rechecks each requested value. Consequently `snapshotTick` can precede `appliedTick` (the contract test proves tick 15 observed and tick 16 applied), and the model never receives a direct mutable live-economy reference during inference.

## Constrained observation

`observe_node` collects aggregate metrics and metric history, recent GDP and debt ratios, sector diagnostics, current policy, fiscal/bailout telemetry, warmup regime, and a `data_seen` audit snapshot. `build_allowed_government_actions` tests candidate moves through the same sanitizer used after generation, so the prompt mask describes currently valid moves rather than a static wish list.

`apply_info_constraints_node` then applies per-indicator lag, Gaussian noise, and probabilistic coverage. Its RNG derives from simulation seed, tick, and indicator, making the information impairment repeatable for a fixed simulator state. Missing observations are explicit objects with `status: unavailable` and `last_available_tick`; they are not silently replaced with ground truth. Rolling summaries and bounded decision memory align context with policy cadence.

## Parse, validate, apply

The advisor asks for structured JSON and uses response extraction plus a repair retry before falling back to a no-op state. Parsed actions do **not** become authority:

1. Normalize the current policy against the canonical [policy schema](../backend/configuration-and-policy.md).
2. Validate types, enums, ranges, tax step limits, fiscal constraints, and target existence.
3. Treat bailout, subsidy, price-stabilization, and related multi-lever instruments as groups; reject invalid groups atomically.
4. Admit no more than two substantive instrument groups per cycle.
5. Keep model choices (`accepted_llm_changes`) separate from required `mechanical_corrections`; combine them only in `applied_changes`.
6. Revalidate at the live boundary through `GovernmentAgent.set_lever`; record `live_apply_failed` rather than crashing the loop.

The canonical schema deliberately keeps prompt, sanitizer, server snapshot, and `GovernmentAgent` validation synchronized. Contract coverage checks that correspondence and verifies that enabling LLM government suppresses the legacy chooser.

## Telemetry and persistence

The WebSocket status block exposes enabled/status, provider/model, snapshot/applied ticks, latest decision, last error, and accepted/rejected counts. Runtime states include `disabled`, `provider_unavailable`, `thinking`, `ready`, `applying`, and `error` as assigned by the server; they are operational labels, not a formal persisted state machine.

Each applied lever emits a `government_llm` policy action with before/after values, latency, parse state, rationale, evidence and evidence audit. The full decision row stores raw and normalized response JSON, accepted/rejected JSON, snapshot/apply ticks, provider/model, status, latency, and error. SQLite and Postgres managers persist these rows atomically with policy actions in warehouse flushes; HTTP readback exposes ordered decisions. See [Experiments and evaluation](experiments-and-evaluation.md#evaluation-and-evidence) for artifact-level analysis.

## Validation commands

```bash
pytest -q backend/tests_contracts/test_contracts_llm.py
pytest -q backend/tests_server/test_live_llm_government.py
pytest -q backend/data/tests/test_db_manager.py -k llm
python backend/tools/llm/run_llm_government_test.py --help
python backend/tools/analysis/analyze_llm_government_log.py path/to/llm_government.json
```

Provider-backed runners require the selected local service or API key and incur nondeterministic latency/output. Unit and contract tests use queued or mocked providers and are the appropriate provider-free validation path.

## Known boundaries

- Opt-in integration controls only the simulator’s enumerated fiscal/market levers; it has no shell, database, network-tool, monetary-policy, legal, or real-world execution authority.
- Background reasoning observes a frozen, potentially stale snapshot. Live application catches invalid levers but does not optimize policy against intervening ticks.
- Schema validity and evidence matching measure agent discipline, not welfare, causal correctness, safety, or governance quality.
- The system is an agent-based simulation with omitted institutions and synthetic behavior. All outcomes and claims remain simulator-only.
