# Simulation Guide

This document describes the current runtime behavior of EcoSim as implemented in the Python code.

## Overview

EcoSim is a tick-based agent-based model. One tick is approximately one simulated week, and the default year length is 52 ticks.

Active actors:

- Households: workers, consumers, patients, tenants, savers, borrowers, and firm owners.
- Firms: producers and employers in Food, Housing, Services, Healthcare, and internal/public-work paths.
- Government: tax collector, transfer provider, policy actor, baseline-firm owner, subsidy source, and fiscal-pressure tracker.
- Bank: optional credit and deposit channel. The standard large-economy setup creates a bank; the engine can still run without one.

The default dashboard setup creates households, four baseline safety-net firms, a queue of private firms, a government, and a bank. Baseline firms are active immediately. Private Food and Services firms are queued during warmup and activated afterward; Housing and Healthcare currently use a baseline-led provider model at startup.

## Runtime Stack

```text
frontend-react
  -> WebSocket /ws
backend/server.py
  -> SimulationManager
backend/economy.py
  -> Economy.step()
backend/agents.py
  -> HouseholdAgent, FirmAgent, BankAgent, GovernmentAgent
backend/config.py
  -> SimulationConfig defaults
backend/policy_schema.py
  -> runtime and LLM policy schema
```

## Initialization

The WebSocket `SETUP` command is validated by `SetupConfig` in [`backend/server.py`](../backend/server.py). Supported setup fields are:

- `num_households`: default `1000`, backend-valid range `3` to `100000`
- `num_firms`: default `5`, backend-valid range `1` to `1000`
- `seed`: optional integer seed
- `enable_llm_government`: optional boolean
- `disable_stabilizers`: boolean
- `disabled_agents`: any of `households`, `firms`, `government`, `all`

The large-economy factory lives in [`backend/tools/runners/run_large_simulation.py`](../backend/tools/runners/run_large_simulation.py). It creates:

- four baseline firms, one each for Food, Housing, Services, and Healthcare
- queued private firms, distributed primarily to Food and Services in the current startup model
- households with distributed skills, ages, and starting cash
- seeded initial doctors for the baseline Healthcare firm
- firm ownership links from firms back to households
- a bank with cash reserves scaled by household count
- a government with starting cash scaled by household count

## Tick Lifecycle

The authoritative lifecycle is `Economy.step()` in [`backend/economy.py`](../backend/economy.py). The current sequence is:

1. Refresh warmup state, activate queued firms after warmup, reset per-tick telemetry, apply post-warmup stimulus if active, refresh subsidy caps, reset bank telemetry, apply random shocks, reset healthcare tick state, lock doctor health where configured, and enqueue healthcare requests.
2. Build market views and unemployment statistics.
3. If government stabilizers are enabled, update loan commitments, execute authorized bailouts, and maintain or deauthorize public-works capacity.
4. Firms refresh one shared health snapshot, consider long-term capital loans, plan production/labor, record working-capital diagnostics, plan prices, apply price/rent stabilization caps, plan wages, disable ordinary labor-market hiring for Healthcare, and plan capital investment.
5. Issue working-capital bridge credit where enabled and eligible.
6. Process firm investment loan requests through the bank.
7. Enforce the active minimum-wage floor in firm wage plans.
8. Households update education status, job-search cooldowns tick, labor plans are created, unemployment guardrails normalize search/reservation state, and consumption plans are generated or reused in performance mode.
9. If the bank exists, households may request consumption loans and the bank may originate them.
10. Labor matching runs through the configured matcher, records hire/layoff events, and records failed-hiring regime events.
11. Firms and households apply labor outcomes; firm rosters are synchronized with household employment state.
12. Firms produce goods/services and update expected sales.
13. Households withdraw up to the configured accessible share of deposits to cover planned purchases before market clearing.
14. Food, Services, and tradable goods clear through the goods market.
15. Services firms may expand employee-slot infrastructure; bank-backed service infrastructure loans may be offered.
16. Housing rental market clears, repairs apply, housing firms consider unit expansion, and bank-backed housing expansion loans may be offered.
17. Miscellaneous revenue is redistributed through the internal misc firm path.
18. Healthcare firms process queued visits up to effective capacity; households pay with cash/deposits, subsidies, or medical loans where available.
19. Government plans wage/profit/property/investment-related taxes and transfers.
20. Capital-investment spending is recycled.
21. Firms receive sales revenue, pay taxes, and apply price/wage updates.
22. Bank loan repayments are collected after wages and sales are available.
23. Household wage income, CEO income, transfers, taxes, purchases, medical loan payments, and ledgers are applied.
24. Government fiscal results are applied.
25. Bank deposit rates update, household deposit sweeps/withdrawals run, credit scores update, and settled loans are cleaned up.
26. Government infrastructure, technology, social spending, and bond purchases are applied and routed back into circulation where appropriate.
27. Investment taxes are collected and fiscal pressure/spending efficiency are updated.
28. Household wellbeing updates run, with lower cadence in performance mode.
29. Bankrupt private firms exit and eligible new firms enter under-served sectors.
30. If rule-based government stabilizers are enabled and the LLM government is disabled, automatic government policy adjustment runs.
31. Statistics, health diagnostics, firm-distress diagnostics, and sector-shortage diagnostics update.
32. Firm profits and healthcare worker bonuses are distributed to household owners/workers, household ledgers finalize, affordability telemetry updates, and the simulation clock advances.

The server applies pending runtime config changes and completed LLM decisions only at safe boundaries around this tick loop.

## Households

Households maintain cash, bank deposits, skills, age, employment state, wage, health, happiness, morale, expectations, preferences, inventory, medical status, debt, and history used by the live UI.

Key current mechanics:

- A household can work only if `health >= 0.10` and it is not in the student phase of medical training.
- Unemployed, work-capable households are normalized into active job search by default through `ECOSIM_FORCE_UNEMPLOYED_SEARCH=1`.
- Long-term unemployed reservation wages are clamped to an observable market anchor by default after `ECOSIM_UNEMPLOYED_CLAMP_TICKS=8`.
- Employed households can perform staggered on-the-job search after warmup. If a switching attempt fails to match, the household keeps its prior employer.
- Matching wage premiums in the current matcher are `25% * skill_level` plus `3%` per year of category experience, capped at `30%`.
- Consumption planning uses wage income, benefit income, dividend income, personality-driven saving behavior, current cash, and accessible deposit liquidity.
- Health, happiness, and morale update from food, housing, services, employment, wage satisfaction, healthcare, poverty stress, and government social multipliers.
- Medical training has student/resident/doctor stages. Residents and doctors add healthcare capacity; doctors are seeded during large-economy initialization.

## Firms

Firms plan before state mutations are applied. The common pattern is:

1. compute a shared health snapshot
2. plan production and labor
3. plan price
4. plan wage
5. apply labor, production, sales, taxes, price, and wage changes later in the tick

The shared firm-health snapshot includes cash runway, smoothed profit margin, sell-through rate, inventory weeks, unfilled-position streak, turnover, survival mode, burn mode, and a category wage anchor.

Private firm behavior includes:

- inventory-aware production and pricing
- sector-specific pricing paths for generic firms, housing, healthcare, baseline firms, and services
- wage planning that uses the active minimum-wage floor, unemployment, benefit levels, firm health, and hiring pressure
- survival and burn modes under distress
- staged layoffs and hiring gates
- capital investment, service infrastructure, housing unit expansion, and bank/government-backed lending paths
- bankruptcy when cash falls below the configured threshold or distress persists through the zero-cash guard
- new firm entry into under-served sectors

Baseline firms are protected from bankruptcy and provide a safety-net floor. Public works can create additional baseline-style capacity when enabled by policy.

## Labor Market

The default matcher is `fast`; the legacy matcher remains available for comparison.

Configuration:

```env
ECOSIM_LABOR_MATCH_MODE=fast
ECOSIM_COMPARE_LABOR_MATCH=0
ECOSIM_COMPARE_LABOR_MATCH_STRIDE=1
ECOSIM_LABOR_DIAGNOSTICS=0
ECOSIM_LABOR_DIAGNOSTICS_STRIDE=10
```

Current matching behavior:

- incumbent jobs are retained unless a layoff or successful job switch changes the relationship
- work-ineligible households are excluded
- job seekers are filtered by reservation wage and medical-only status
- candidate priority favors higher skill, with deterministic tie-breaking
- actual wages include skill and category-experience premiums
- unfilled vacancies record diagnostic reasons such as no searchers or reservation wages above offers

The warehouse and metrics path expose labor diagnostics such as unemployed-not-searching, wage-ineligible seekers, forced-search adjustments, and reservation-clamp adjustments.

## Goods, Housing, And Healthcare

Goods market:

- Food and Services clear through the goods-market path.
- Services are treated as current-tick capacity rather than stored household inventory.
- Households use bounded awareness pools, price/quality preferences, and stochastic noise when choosing firms.
- Sector subsidies reduce household payment when the government has remaining subsidy budget.

Housing:

- Housing clears through a rental-market path separate from ordinary goods clearing.
- Rent affordability, vacancies, evictions, repairs, occupancy pressure, rent stabilization, and housing expansion are tracked.
- Housing unit expansion can use self-financing or bank loans depending on state.

Healthcare:

- Healthcare is queue-based and non-storable.
- Households enqueue healthcare requests based on health status and planned visit schedules.
- Healthcare firms process visits up to labor-based capacity, with resident/doctor capacity differences.
- Payment can use cash, accessible deposits, government subsidy, or medical loans.
- Denied visits and completed visits are emitted as healthcare events.

## Government

The government owns the policy surface implemented in [`backend/policy_schema.py`](../backend/policy_schema.py). It collects taxes, applies transfers and subsidies, manages public works, runs fiscal investments, tracks fiscal pressure, applies bailouts, and records policy state for the UI and warehouse.

Policy choices can come from:

- manual runtime controls in the frontend
- automatic rule-based stabilizers
- the live LLM government when enabled
- offline LLM runners and benchmark tools

When the live LLM government is enabled, deterministic rule-based policy adjustment is bypassed so policy choices come from the model plus mechanical validation and application code.

## Bank And Credit

The standard dashboard economy includes a `BankAgent`. The bank tracks cash reserves, deposits, active loans, lending capacity, credit scores, interest income, deposit interest, defaults, repayments, and loan loss provision.

Current bank-integrated paths include:

- household deposit sweeps and withdrawals
- deposit interest, constrained by bank profitability/reserves
- firm capital loans
- service infrastructure loans
- housing expansion loans
- working-capital bridge credit
- consumption loans
- medical loans
- repayment collection and default handling
- firm and household credit score updates

The engine keeps fallback paths for runs where `bank` is `None`.

## LLM Government

The LLM government observes compact macro, sector, fiscal, shortage, and prior-decision context. It does not receive raw household or firm records. Its proposed changes are validated against `policy_schema.py`, rate-limited, grouped where needed, and separated into accepted/rejected changes.

Default scheduling is configured in `CONFIG.llm`: decisions occur on an interval, after warmup/start gates, and are run outside the tick phase in a background task. Completed decisions are applied before a later tick begins.

## Warehouse And Diagnostics

When persistence is enabled, the server records:

- run metadata and policy config
- tick metrics and sector metrics
- firm snapshots
- sampled household snapshots
- tracked household history
- labor and healthcare events
- policy actions
- decision features
- tick diagnostics
- sector shortage diagnostics
- regime events
- full LLM government decisions

The live decision context is also available in memory through `GET /decision-context/live?session_id={session_id}`, even before warehouse batches flush. The session ID is sent to the WebSocket client in the initial `SESSION` message.

## Important Defaults

| Setting | Current default |
|---|---|
| Tick length | 1 week |
| Ticks per year | 52 |
| Warmup ticks | 10 |
| Setup households | 1000 in frontend/server default |
| Setup private-firms setting | 5 per setup input, redistributed by factory rules |
| Labor matcher | `fast` |
| Household snapshot stride | 5 warehouse ticks |
| Direct local warehouse | disabled unless `ECOSIM_ENABLE_WAREHOUSE=1` |
| Docker warehouse | enabled SQLite runtime volume |
| Live LLM government | disabled by default |
| Tax lever max LLM step | 0.05 per decision |
