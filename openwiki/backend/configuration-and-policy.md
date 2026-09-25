---
type: reference
description: Configuration ownership, canonical government action space, manual-control translation, fiscal guards, and safe extension seams.
tags: [ecosim, repository-navigation]
title: Configuration and policy
summary: Configuration ownership, canonical government action space, manual-control translation, fiscal guards, and safe extension seams.
kind: reference
sources:
  - backend/config.py
  - backend/policy_schema.py
  - backend/fiscal_guards.py
  - backend/agents.py
  - backend/server.py
  - backend/tests_contracts/test_contracts_llm.py
  - backend/tests_server/test_server_sessions.py
related:
  - ../backend/tick-lifecycle.md
  - ../runtime/sessions-and-websocket.md
  - ../llm/government.md
  - ../frontend/dashboard.md
---

# Configuration and policy

EcoSim has two deliberately different control surfaces. `backend/config.py` is the full mechanics configuration tree read throughout the simulator. `backend/policy_schema.py` is the much smaller, canonical government action space shared by runtime validation and the LLM prompt. A dashboard `CONFIG` message translates UI keys into that action space or into five legacy direct policy attributes; it does **not** expose arbitrary `SimulationConfig` fields.

## Configuration tree and ownership

`SimulationConfig` composes these dataclasses: `time: TimeConfig`, `households: HouseholdBehaviorConfig`, `firms: FirmBehaviorConfig`, `government: GovernmentPolicyConfig`, `labor_market: LaborMarketConfig`, `market: MarketMechanicsConfig`, `debug: DebugConfig`, `modes: SimulationModeConfig`, and `llm: LLMConfig`. Its root also owns legacy scale/distribution fields, `random_seed`, and baseline prices. Defaults are the dataclass declarations—the effective source of truth—not UI defaults. `__post_init__` checks positive time, non-negative warmup and elasticities, savings bounds/order, and selected range ordering; most hundreds of tuning fields have no generic validation.

`_DEFAULT_CONFIG` serves command-line code. `_ACTIVE_CONFIG` is a `ContextVar`; `get_config()` chooses active or default, `clone_config()` deep-copies a complete tree, and `use_config()` sets and reliably resets the context token. `CONFIG` is `_ContextLocalConfig`, a compatibility proxy including legacy `CONFIG.__dict__.update(...)`. Module aliasing makes `config` and `backend.config` share one proxy. Each WebSocket manager clones the tree and enters `use_config(self.config)` for initialization and every tick, as described in [sessions and WebSocket](../runtime/sessions-and-websocket.md). This preserves old imports while isolating sessions.

Key effective roots are `ticks_per_year=52`, `warmup_ticks=10`, root `num_households=10000`, `num_firms=100`, `random_seed=42`; server setup instead defaults to 1,000 households and 5 firms per category. LLM government is opt-in, starts no earlier than tick 15 and five ticks after warmup, and has a 26-tick decision interval. See [government LLM](../llm/government.md) for provider behavior and [tick lifecycle](../backend/tick-lifecycle.md) for consumers of mechanics settings.

## Canonical government action space

| Kind | Levers and exact values |
|---|---|
| Bounded float | `wage_tax_rate` 0–0.50, `profit_tax_rate` 0–0.50, `investment_tax_rate` 0–0.30; each has maximum change 0.05 per decision |
| Ordered | `benefit_level`: low, neutral, high, crisis; `minimum_wage_policy`: low, neutral, high; `sector_subsidy_level`: 0, 10, 25, 50; `infrastructure_spending`, `technology_spending`, `social_spending`: none, low, medium, high; `price_stabilization_level`, `rent_stabilization_level`: off, monitor, soft, strict; `bailout_policy`: off, sector, all; `bailout_budget`: 0, 5000, 10000, 25000, 50000 |
| Enum | `public_works`: off, on; `sector_subsidy_target`: none, food, housing, services, healthcare; `price_stabilization_target`: none, food, services, healthcare; `bailout_target`: none, food, housing, services, healthcare |

`POLICY_SCHEMA` and `VALID_LEVERS` are derived from those declarations. `PROMPT_POLICY_LEVERS` fixes prompt order. `normalize_current_policy()` accepts the old `public_works_toggle`, coerces integer levels/budgets and taxes, while `policy_value_set()`, `is_ordered_increase()`, `is_spending_increase()`, and `is_tax_decrease()` support validation and fiscal reasoning. `POLICY_GROUPS` defines atomic groups: price stabilization target+level, rent stabilization level, bailout policy+target+budget, and subsidy target+level. The LLM sanitizer additionally limits substantive changes to two; grouped changes count and apply together. Contract tests explicitly cover atomic price-stabilization and bailout proposals.

`GovernmentAgent.set_lever()` is the final runtime validator/applicator. Therefore adding a schema constant alone is insufficient: the agent must store and consume the lever in the economic lifecycle, and both manual and LLM paths must reach it.

## Dashboard/manual translation

`SimulationManager._normalize_runtime_policy_updates()` maps exact camel-case keys:

- taxes: `wageTax`, `profitTax`, `investmentTax`;
- discrete levers: `benefitLevel`, `publicWorks`, `minimumWagePolicy`, `sectorSubsidyTarget`, `sectorSubsidyLevel`, `infrastructureSpending`, `technologySpending`, `socialSpending`, `priceStabilizationTarget`, `priceStabilizationLevel`, `rentStabilizationLevel`, `bailoutPolicy`, `bailoutTarget`, `bailoutBudget`;
- compatibility sliders: `unemploymentBenefitRate` maps to low ≤0.25, neutral ≤0.55, high ≤0.85, otherwise crisis; `minimumWage` maps to low ≤30, high ≥45, otherwise neutral.

Boolean `publicWorks` becomes on/off; integer levers snap to the nearest allowed value; taxes are float-coerced. `set_lever()` failures are logged and skipped. A minimum-wage policy immediately raises below-floor firm offers, yielding every 100 firms. Direct legacy keys are `universalBasicIncome`, `wealthTaxThreshold`, `wealthTaxRate`, `inflationRate`, and `birthRate`; `enableLlmGovernment` toggles LLM scheduling. Accepted changes become UI records and warehouse policy actions. The dashboard relationship is documented in [dashboard](../frontend/dashboard.md).

Running updates merge into `pending_config_updates` and apply immediately before the next economy step; paused updates apply immediately. This safe-boundary relationship is part of [tick lifecycle](../backend/tick-lifecycle.md). There is no success acknowledgement for `CONFIG`, and unknown keys are silently ignored.

## Fiscal guards

`backend/fiscal_guards.py` is economy-agnostic. `trailing_gdp()` searches metrics history using four GDP aliases, then last revenue, then `max(1, households × 25)`. Debt/GDP annualizes tick GDP with configured ticks/year. The treasury reserve floor is `max(50,000, 5 × recent GDP)`. Public works cannot charge startup capitalization (`government.public_works_job_fraction × 1,000,000`) twice and must retain that reserve. Per-tick sector subsidy payout is capped at the lesser of 5% of recent GDP and 2% of positive government cash. These guards inspect duck-typed objects and read the active context-local `CONFIG`.

## Extension checklist

1. Add mechanics tuning to the owning dataclass; add `SimulationConfig.__post_init__` validation when invalid values could corrupt a run.
2. For a government action, update the canonical schema/order/group declarations and prompt order together.
3. Implement storage, validation, and economic consumption in `GovernmentAgent.set_lever()` and the appropriate phase of `Economy.step()`.
4. If manually controllable, add the UI key mapping and dashboard control; do not bypass `set_lever()` for canonical levers.
5. If grouped, update `POLICY_GROUPS` so sanitizer/apply remains atomic. If spending-affecting, update `SPENDING_LEVERS` and fiscal checks.
6. Persist and reconstruct it if policy evidence must appear in the [warehouse](../data/warehouse.md) and HTTP policy context.
7. Test bounds, max step, grouped atomicity, manual translation, safe-boundary application, prompt rendering, and actual behavioral consumption.

## Focused validation

```bash
python -m pytest backend/tests_contracts/test_contracts_llm.py -q
python -m pytest backend/tests_server/test_server_sessions.py -q
python -m pytest backend/tests_server/test_live_llm_government.py -q
```

The repository's configured default `pytest` path is only `backend/tests_contracts`; server tests must be named explicitly.
