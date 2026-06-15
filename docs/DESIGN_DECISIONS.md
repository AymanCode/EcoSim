# Design Decisions

This document records deliberate engineering choices in the current EcoSim codebase. It is intended to make the architecture defensible without requiring a reader to reconstruct the reasoning from implementation details.

## Plan/Apply Split

**Decision.** Agent decisions are generally planned first and applied later. Firm production/labor, pricing, wages, household labor, consumption, taxes, transfers, and market outcomes are staged before mutating state in the main tick.

**Code.** [`backend/economy.py`](../backend/economy.py), [`backend/agents.py`](../backend/agents.py)

**Alternative.** Let each agent mutate state inside its own decision method.

**Reason.** Planning against a consistent pre-application state prevents one firm or household from observing another actor's partially applied decision in the same tick. It also makes individual planning functions easier to test.

## Central Tick Coordinator

**Decision.** `Economy.step()` remains the central coordinator for labor, production, goods, housing, healthcare, banking, government, firm lifecycle, and diagnostics.

**Code.** [`backend/economy.py`](../backend/economy.py)

**Alternative.** Split every tick phase into separate subsystem services immediately.

**Reason.** The model is still evolving quickly, and phase ordering is load-bearing. Keeping the coordinator explicit makes ordering changes visible. Stable seams have been pulled out where they are already clear: policy schema, warehouse persistence, LLM providers, benchmark tooling, and utility helpers.

## Sector-Specific Firm Behavior

**Decision.** Pricing and capacity logic branch by sector instead of forcing Food, Housing, Services, Healthcare, baseline firms, and public works through one generic rule.

**Code.** [`backend/agents.py`](../backend/agents.py)

**Alternative.** One generic inventory/pricing formula with different parameters per sector.

**Reason.** The sectors fail in different ways. Housing needs occupancy, rent, unit expansion, and debt-service logic. Healthcare needs queue/capacity pricing and non-storable service processing. Services are current-tick capacity. Baseline firms serve as safety-net providers. A single pricing rule produced worse edge cases than explicit sector branches.

## Shared Firm-Health Snapshot

**Decision.** Private firms compute a shared health snapshot before planning labor, price, and wage changes.

**Code.** [`docs/FIRM_DYNAMICS.md`](FIRM_DYNAMICS.md), [`backend/agents.py`](../backend/agents.py)

**Alternative.** Let each planner infer firm health independently.

**Reason.** Wage, pricing, and hiring decisions should respond to the same view of cash runway, profit margin, sell-through, inventory, unfilled positions, turnover, survival mode, burn mode, and category wage anchors. The shared snapshot reduces contradictory behavior.

## Fast Labor Matcher With Legacy Comparison Path

**Decision.** The default labor matcher is the optimized `fast` path, with a `legacy` path and optional comparison logging retained for de-risking.

**Code.** [`backend/economy.py`](../backend/economy.py), [`docs/HOUSEHOLD_LABOR_DERISKING.md`](HOUSEHOLD_LABOR_DERISKING.md)

**Alternative.** Keep only the original per-firm candidate scan.

**Reason.** Larger runs need a cheaper matching path, but labor matching is high-risk behavior. Keeping the legacy path available through `ECOSIM_LABOR_MATCH_MODE` and `ECOSIM_COMPARE_LABOR_MATCH` makes it possible to compare outcomes while continuing to use the faster default.

## Unemployment Guardrails

**Decision.** Work-capable unemployed households are normalized into active search by default, and long-term unemployed reservation wages can be clamped to observable market offers.

**Code.** [`backend/economy.py`](../backend/economy.py), [`docs/HOUSEHOLD_LABOR_DERISKING.md`](HOUSEHOLD_LABOR_DERISKING.md)

**Alternative.** Trust each household's labor plan without correction.

**Reason.** At scale, artificial unemployment can come from stale search flags or reservation wages detached from available jobs. The guardrails are configurable and instrumented, so they can be disabled or compared without removing the path.

## Bounded Household Awareness

**Decision.** Households choose firms through bounded per-category awareness pools rather than scanning every firm globally every tick.

**Code.** [`backend/agents.py`](../backend/agents.py)

**Alternative.** Global utility maximization across all firms every purchase.

**Reason.** Global visibility creates instant winner-take-all markets and grows selection cost with firm count. Bounded awareness keeps consumer choice plausible and keeps purchase planning cheaper.

## Optional Bank As Credit Channel

**Decision.** `BankAgent` handles deposits, interest, credit scoring, loan origination, repayment, defaults, and lending constraints, while the economy keeps fallback paths for runs without a bank.

**Code.** [`docs/BANKING_SYSTEM.md`](BANKING_SYSTEM.md), [`backend/agents.py`](../backend/agents.py), [`backend/economy.py`](../backend/economy.py)

**Alternative.** Let government lending cover all credit behavior, or build a full multi-bank model.

**Reason.** A single optional bank is enough to introduce delayed credit-channel effects without turning the project into a banking simulator. It also keeps bank failures from making the rest of the model unusable.

## Policy Schema As Contract

**Decision.** [`backend/policy_schema.py`](../backend/policy_schema.py) is the canonical policy action space for manual runtime controls, LLM prompts, validation, and policy action persistence.

**Alternative.** Let the frontend, server, government agent, and LLM harness each define their own policy vocabulary.

**Reason.** Policy drift is easy and expensive. A pure shared schema keeps lever names, limits, enums, grouping, and per-decision constraints in one importable module with no simulation import cycle.

## Background LLM Decisions

**Decision.** The live LLM government runs provider calls in a background task and applies completed validated changes only at tick boundaries.

**Code.** [`backend/server.py`](../backend/server.py), [`backend/tools/llm/llm_government.py`](../backend/tools/llm/llm_government.py)

**Alternative.** Block the simulation loop while the model thinks, or let provider callbacks mutate state immediately.

**Reason.** Provider latency should not freeze the live dashboard, and policy application must not mutate state mid-phase. Snapshot-then-apply preserves responsiveness and tick consistency.

## Compact Decision Context

**Decision.** LLM and policy-context surfaces use aggregate, sector, diagnostic, fiscal, and prior-policy summaries rather than raw household and firm records.

**Code.** [`backend/server.py`](../backend/server.py), [`backend/tools/llm/llm_government.py`](../backend/tools/llm/llm_government.py), [`backend/data/README.md`](../backend/data/README.md)

**Alternative.** Feed an LLM raw per-agent state or require policy logic to query raw warehouse tables.

**Reason.** Raw microdata is noisy, large, and not how a policy actor should observe the economy. Compact decision features and diagnostics keep the model grounded while preserving context budget and auditability.

## Warehouse Outside The Hot Loop

**Decision.** The simulation runs in memory and writes warehouse data in batches. The warehouse is the durable analytical record, not the per-tick source of truth.

**Code.** [`docs/DATA_STORAGE_ARCHITECTURE.md`](DATA_STORAGE_ARCHITECTURE.md), [`backend/data/README.md`](../backend/data/README.md), [`backend/server.py`](../backend/server.py)

**Alternative.** Query and update the database directly throughout simulation execution.

**Reason.** The hot loop needs predictable latency. Batched persistence provides run history, comparisons, diagnostics, and LLM audit data without putting SQL on the critical path.
