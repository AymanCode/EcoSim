# Design Decisions

A consolidated record of deliberate engineering choices in EcoSim. Each entry names the decision, the alternative that was on the table, and the practical reason the current path won out. Code pointers are given where they help.

This is not a postmortem. Many of these were judgment calls made under a moving target. The goal is to make them defensible in conversation rather than buried in inline comments.

---

### Plan and apply split for agent decisions

**Decision.** Agent methods are split into pure `plan_*` functions that return a decision dict and `apply_*` functions that mutate state. See [agents.py](backend/agents.py) `plan_pricing` (~L4274), `plan_wage` (~L4637), `plan_labor_supply` (~L1127), `plan_consumption` (~L1357), and `apply_labor_outcome` / `apply_price_and_wage_updates` (~L5239). The tick coordinator in [economy.py](backend/economy.py) (~L1576) calls plan across all agents first, then applies outcomes.
**Alternative considered.** Letting each agent mutate state inline during its own decision step, the way most agent-based models start out.
**Why this one.** Reads of macro state during planning stay consistent across agents within one tick, so firm A's wage decision is not contaminated by firm B's already-applied wage change. It also makes the planning functions cheap to unit test without spinning up a full economy. The cost is more bookkeeping and two passes per tick.

### Pricing branches by sector instead of one shared rule

**Decision.** `plan_pricing` in [agents.py](backend/agents.py) (~L4274) routes through sector-specific branches: baseline Food liquidation tiers, Housing rent that targets wage bill plus debt service, Healthcare wage-anchored pricing, and a generic markup path for everything else.
**Alternative considered.** A single inventory-clearance pricing rule applied uniformly to every firm, with parameters tuned per sector.
**Why this one.** The sectors had genuinely different failure modes during testing. Housing as a monopoly landlord needed explicit obligation coverage to stop defaults; baseline Food needed below-cost liquidation tiers to drain stuck inventory; private firms needed standard markup. One unified rule kept producing pathological edge cases in at least one sector. The tradeoff is a `plan_pricing` method that has grown long and is hard to skim.

### Wage setting with three paths

**Decision.** `plan_wage` in [agents.py](backend/agents.py) (~L4637) has three main paths. Baseline (public) firms pin to a multiple of the minimum wage floor. Private non-healthcare firms in normal operation run a Phillips-curve branch with a revenue ceiling (~L4780) that returns the floor wage above the NAIRU and bumps wages on hire failure below it. The remaining path uses a target-labor-share fundamental wage dampened by current unemployment (~L4880).
**Alternative considered.** A single revenue-share rule for everyone, with policy floors layered on top.
**Why this one.** Public firms exist to be a wage floor, not to compete, so they need a hard cap rule. Private firms in tight labor markets needed a faster pass-through than a slow revenue-share rule could give without overshooting affordability. The revenue ceiling and the per-tick clamps stop the Phillips path from spiraling. The cost is three code paths to keep coherent.

### Firm spawning weights underserved sectors

**Decision.** `_maybe_create_new_firms` in [economy.py](backend/economy.py) (~L4562) scores each spawnable sector as `unmet_demand * (1 + 1 / max(1, private_count))`. Sectors with fewer private competitors get an explicit boost on top of their raw demand signal.
**Alternative considered.** Weight purely by observed unmet demand.
**Why this one.** A monopoly sector suppresses its own demand signal. The single seller raises price, households stop buying, and recorded unmet demand falls toward zero. Pure demand weighting then never spawns a competitor, so the monopoly is self-reinforcing. The `(1 + 1/n)` term is a cheap, deliberate hack that decays as the sector gets more entrants. It is not derived from anything; it just breaks the trap.

### Stochastic shuffle on hiring order

**Decision.** Each tick the hiring loop in [economy.py](backend/economy.py) (~L3400) reshuffles the active hiring firm IDs using a per-tick seeded RNG (`random_seed + tick * 104729 + 911`) before iterating. This is the only ordering jitter in the tick; consumption and most other phases use NumPy batching or fixed iteration order.
**Alternative considered.** Iterate firms in a fixed order (creation order or firm ID) every tick.
**Why this one.** Without the shuffle, the same firms always get first pick of available labor, which compounds across ticks into a persistent first-mover advantage that has nothing to do with the firms' actual offers. Reseeding from `random_seed + tick * ...` keeps runs reproducible. The cost is one shuffle per tick, which is negligible.

### Bounded awareness pool for household firm selection

**Decision.** Each household keeps a small per-category `awareness_pool` of firm IDs, capped at `awareness_pool_max_size` (default 7). `refresh_awareness_pool` in [agents.py](backend/agents.py) (~L622) periodically drops the lowest-utility firms and samples new candidates from the global market.
**Alternative considered.** Let every household see every firm every tick and pick the global utility-maximizing option.
**Why this one.** Global visibility produces an unrealistic instant-winner-takes-all market and is also expensive. A bounded pool with periodic refresh approximates limited consumer awareness, gives new entrants a real chance to be discovered, and keeps selection cost roughly constant in firm count. It is bounded random sampling with utility-based replacement, not a true social graph.

### Bank as an optional credit channel

**Decision.** [BankAgent](backend/agents.py) (~L5599) handles firm loans (emergency, seed, liquidation), household medical and consumption loans, deposit accounts, credit scoring, and a reserve-ratio circuit breaker. It is explicitly designed as optional: every loan path falls back to direct government lending when `bank is None`.
**Alternative considered.** Build a full multi-bank interbank market with maturity transformation, or skip a banking layer entirely and only model government lending.
**Why this one.** A real banking sector mattered for credit-driven dynamics (defaults, credit scores affecting spawning, deposit interest) but a full interbank system was out of scope for one author. Making the bank optional kept the rest of the simulation runnable while the credit channel was being added, and it keeps tests cheap. The cost is two parallel lending paths to keep in sync.

### LLM government sees aggregated and lagged macro indicators

**Decision.** The LLM government tool in [llm_government.py](backend/tools/llm/llm_government.py) (~L7, L1262) is built around macro indicators that are explicitly described to the model as "lagged, noisy, unavailable, or averaged." `_lookup_lagged_metric` (~L1344) resolves named indicators against historical snapshots rather than current per-agent state. The prompt never receives raw household or firm records.
**Alternative considered.** Hand the LLM the full current-tick state of every household and firm and let it reason directly from microdata.
**Why this one.** Real governments do not have real-time per-agent visibility. Feeding the model microdata also blows past context limits and lets it overfit to noise that no real policymaker would see. Aggregated, lagged indicators force the LLM to make decisions on the kind of signal an actual policy team works from. It also makes the prompt small enough to be cacheable.

### Warmup gate before the LLM government activates

**Decision.** The LLM government does not run until `max(government_start_tick, warmup_ticks + government_start_after_warmup_ticks)`. See [llm_government.py](backend/tools/llm/llm_government.py) (~L2598) and the warmup wiring in [economy.py](backend/economy.py) (~L113, L1385). During warmup the simulation runs with deterministic baseline rules.
**Alternative considered.** Let the LLM make decisions from tick 0.
**Why this one.** Tick-0 macro indicators are garbage: nobody has earned a wage yet, nobody has bought anything, employment is still being assigned. Asking the model to set tax rates against that state produces nonsense decisions that then have to be unwound. Letting the economy reach a steady-ish baseline first gives the model a stateful starting point and isolates "what did the model change" from "what was the model reacting to noise."

### policy_schema.py as the action-space source of truth

**Decision.** [policy_schema.py](backend/policy_schema.py) holds the canonical lever names, ordered levels, enum values, tax limits, and per-tick change caps. It is intentionally a pure module that does not import `GovernmentAgent` or `Economy`. The runtime path in [server.py](backend/server.py) (~L52, L2654) and the LLM sanitizer in [llm_government.py](backend/tools/llm/llm_government.py) both import from it.
**Alternative considered.** Let each consumer (UI handler, LLM prompt, agent validator) define its own copy of the lever vocabulary, or pull values from `CONFIG` directly.
**Why this one.** Keeping the action space in one importable module means the LLM prompt, the rule-based UI path, and the in-economy validator cannot drift on lever names or allowed values without somebody noticing at import time. Making it pure was deliberate so it has no circular import risk and the LLM tooling can import it without dragging the simulation in.

---

## Future direction

When the core model stabilizes, the next safe refactor is to extract pure helpers and stable subsystems first (pricing tier rules, wage path branches, spawn scoring), then split agent classes and tick phases only after contract tests cover the behavior.
