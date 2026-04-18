# EcoSim Simulation Guide

How the simulation works — agents, interactions, markets, and the tick lifecycle.

---

## Architecture Overview

EcoSim is a tick-based agent-based model (ABM) with three actor types:

- **Households** — consumers and workers
- **Firms** — producers and employers (Food, Housing, Services, Healthcare)
- **Government** — tax collector, transfer provider, investor

Each tick represents roughly one week (52 ticks = 1 year). The simulation runs deterministically given the same seed and configuration.

### Runtime Stack

```
frontend-react (React + Recharts dashboard)
  → WebSocket (ws://localhost:8002/ws)
backend/server.py (simulation manager, metric streaming)
  → backend/economy.py (tick coordinator, market clearing)
  → backend/agents.py (HouseholdAgent, FirmAgent, GovernmentAgent)
  → backend/config.py (400+ tunable parameters)
```

---

## Agents

### Household Agent

Households are the core economic actors — they work, earn wages, buy goods, consume, and maintain wellbeing.

**Key State:**

| Field | Type | Description |
|-------|------|-------------|
| `cash_balance` | float | Current liquid cash |
| `skills_level` | float (0-1) | Worker skill affecting wages and productivity |
| `is_employed` | bool | Employment status |
| `employer_id` | int/null | Which firm they work at |
| `wage` | float | Current wage earned per tick |
| `health` | float (0-1) | Physical health, decays without food/healthcare |
| `happiness` | float (0-1) | Driven by services consumption and employment |
| `morale` | float (0-1) | Driven by wage satisfaction and job stability |
| `goods_inventory` | dict | `{good_name: quantity}` — pantry of purchased goods |
| `category_experience` | dict | `{category: ticks_worked}` — industry-specific experience |

**Behaviors per tick:**

1. **Labor supply** — Decides whether to seek work, sets reservation wage based on expected wage and skills. Employed households may also search for better-paying jobs via the on-the-job search mechanic (see Labor Market).
2. **Consumption planning** — Allocates budget across food, housing, services, healthcare based on need and preferences. Food and healthcare have satiation caps to prevent hoarding.
3. **Goods consumption** — Eats from pantry each tick (10% depletion rate). Food consumption credits `food_consumed_this_tick`; same for services and healthcare.
4. **Wellbeing update** — Health, happiness, and morale update each tick. All three have natural decay rates. Happiness recovery is driven by consumption events (food, services, housing, fair wages).
5. **Skill growth** — Passive skill improvement while employed (`0.001 * (1 - skills_level)` per tick). Experience accumulates per industry category.

**Key Mechanics:**

- **`can_work` threshold**: Health must be >= 0.10 to participate in labor market. Below this, the household is too sick to work.
- **Performance multiplier**: `0.5 + (morale×0.5 + health×0.3 + happiness×0.2)` — ranges from 0.5x to 1.5x, directly affects production output.
- **Mercy floor**: When happiness drops below 0.25, decay pauses to prevent irreversible death spirals.
- **Wage premiums**: Actual wage = `wage_offer * (1 + skill_premium + experience_premium)`. Skill premium up to 50% at max skill; experience premium 5% per year, capped at 50%.

**Consumption Model:**

Spending is income-anchored, not wealth-liquidating. The budget is computed as:

```
disposable_income = wage            # if employed
                  = benefit_level   # if unemployed
base_budget = spend_fraction * disposable_income
drawdown    = savings_drawdown_rate * cash_balance   # personality-derived, 1–5%/tick
budget      = min(base_budget + drawdown, cash_balance)
```

`spend_fraction` (0.3–0.9) is modulated by macro confidence (unemployment rate), happiness, and employment stability. `savings_drawdown_rate` is personality-derived in `_initialize_personality_preferences`: spenders draw down up to 5%/tick, savers as little as 1%/tick.

**Desperation mode**: When `base_budget < subsistence_min_cash`, the household switches to an emergency drawdown rate (`savings_drawdown_rate × 5`, capped at 20%) to cover survival spending. This represents a household raiding savings when income is insufficient for basics.

**Wellbeing Decay and Recovery:**

| Signal | Decay rate | Recovery (full consumption) |
|--------|-----------|---------------------------|
| Health | 0.5%/tick | Healthcare visits, food above threshold |
| Happiness | 0.2%/tick | +0.08% food, +0.05% services, +0.07% housing, +0.05% fair wage |
| Morale | 2%/tick | Employment, wage satisfaction |

A fully-satisfied household (all needs met, employed, fair wage) recovers happiness at ~0.25%/tick ≈ decay rate → stable. Unmet needs cause net decay.

**Bank Account:**

Each household has a `cash_balance` (liquid) and optionally a `bank_deposit` (savings). These are separate. Spending always draws from `cash_balance` only — the bank deposit cannot be spent directly.

Each tick, the bank sweep runs after consumption:
1. **Interest**: deposit earns interest, credited to both `bank_deposit` and `cash_balance`.
2. **Auto-deposit**: if `cash_balance > liquidity_floor` (3–10 weeks of expenses, personality-derived), a fraction (5–40%) of the excess is swept into the deposit.
3. **Auto-withdraw**: if `cash_balance < 50% of liquidity_floor` and there are deposits, the shortfall is pulled back from savings into cash.

This means the bank account is a passive savings buffer — the household doesn't decide to deposit or withdraw, the mechanic runs automatically based on their saving personality.

### Firm Agent

Firms produce goods, hire workers, set prices, and compete for market share.

**Key State:**

| Field | Type | Description |
|-------|------|-------------|
| `good_category` | str | Food, Housing, Services, or Healthcare |
| `cash_balance` | float | Firm's liquid cash |
| `inventory_units` | float | Current stock on hand |
| `employees` | list | List of employed household IDs |
| `wage_offer` | float | Posted wage for hiring |
| `price` | float | Product price |
| `quality_level` | float (0-10) | Product quality |
| `personality` | str | aggressive, moderate, or conservative |
| `is_baseline` | bool | True for government safety-net firms |

**Behaviors per tick:**

1. **Production and labor planning** — Private firms use a shared firm-health snapshot so staffing, distress response, pricing, and wage logic react to the same conditions. The labor planner still handles demand, inventory pressure, survival mode, burn mode, and staged cuts.
2. **Hiring and contraction** — Distressed private firms can be blocked from expanding when smoothed profit is negative and cash runway is short, while contraction logic remains active.
3. **Pricing** — Private prices react to inventory pressure using each firm's sampled `price_adjustment_rate` and `target_inventory_weeks`. Large gluts create larger cuts; sell-outs with low stock create smaller upward nudges. Baseline and healthcare firms keep category-specific special handling.
4. **Wage setting** — Private post-warmup wages ratchet from the current `wage_offer` rather than being re-anchored to one tick of realized revenue per worker. Pressure comes from hiring failure, turnover, profitability, runway, sell-through, and inventory.

**Firm Personalities and Trait Sampling:**

Each firm still has a broad personality (`aggressive`, `moderate`, `conservative`), but the actual response speeds are sampled per firm rather than hard-coded to one exact number. In practice this means firms share the same decision rules while differing in:

- `risk_tolerance`
- `price_adjustment_rate`
- `wage_adjustment_rate`
- `target_inventory_weeks`
- hire/fire limits
- R&D and investment propensity

**Baseline (Government) Firms:**

- One per category (Food, Housing, Services, Healthcare)
- Act as safety-net providers with lower quality
- During warmup (`CONFIG.time.warmup_ticks`, default 10), hire proportional share of workforce
- After warmup, gradually reduce staff to let private firms take over (support ratios: 1.0 during cooldown, 0.8 after)

**Bankruptcy:**
- Firms with cash below -$1,000 exit the economy
- All employees are laid off
- New firms enter the least-represented category when total firms drop below minimum

### Government Agent

The government collects taxes, provides transfers, makes investments, and adjusts policy.

**Key State:**

| Field | Type | Description |
|-------|------|-------------|
| `cash_balance` | float | Government reserves |
| `wage_tax_rate` | float (0-1) | Tax on household wages |
| `profit_tax_rate` | float (0-1) | Tax on firm profits |
| `unemployment_benefit_level` | float | Per-tick payment to unemployed |
| `fiscal_pressure` | float | Rolling EMA of `(spending - revenue) / GDP`, used for fiscal penalties |
| `spending_efficiency` | float (0.5-1.0) | Soft budget-pressure penalty applied to government discretionary spending |
| `infrastructure_productivity_multiplier` | float | Economy-wide productivity boost |
| `technology_quality_multiplier` | float | Economy-wide quality boost |
| `social_happiness_multiplier` | float | Economy-wide happiness boost |

**Behaviors per tick:**

1. **Tax collection** — Collects wage taxes from households and profit taxes from firms.
2. **Transfers** — Distributes unemployment benefits and other transfers.
3. **Investment** — When cash > $10,000, invests in:
   - Infrastructure (+0.5% productivity per $1,000)
   - Technology (+0.5% quality per $500)
   - Social programs (+0.5% happiness per $750)
4. **Soft fiscal constraint** — Tracks two different budget metrics:
   - `deficit_ratio`: snapshot-style treasury stress, computed from government cash relative to current GDP
   - `fiscal_pressure`: rolling EMA of per-tick deficit flow, used to degrade `spending_efficiency`

### Fiscal Pressure and Spending Efficiency

- `fiscal_pressure` is the control signal the simulator uses for budget pressure.
- It is updated from per-tick `(spending - revenue) / GDP` and clamped to a floor of `-0.15`, so long surplus periods create only a modest fiscal buffer rather than an unrecoverable negative well.
- `spending_efficiency` is derived from `fiscal_pressure`:
  - below `0.05`: no penalty
  - `0.05-0.15`: mild efficiency loss
  - `0.15-0.30`: stronger penalty
  - above `0.30`: hard floor at `0.5`
- Treasury outflows counted in this pressure path include transfers, infrastructure spending, technology spending, sector subsidies, bailout disbursements, bond purchases, and public-works capitalization.

---

## Healthcare System

Healthcare is modeled as a **non-storable service**, not a tradable inventory good.

### How It Works

1. **Demand**: Households request care based on health level. At each annual anchor tick, they sample a visit count from a health-bucket distribution (healthy → 0-2 visits/year; critically ill → 4-6 visits/year).
2. **Queueing**: Requests go into firm-specific FIFO queues. Households pick providers by queue pressure (shortest wait) with minimal price weighting for critical cases.
3. **Processing**: Healthcare firms process queued visits up to labor-based capacity each tick. `effective_capacity = floor(workers * capacity_per_worker)`.
4. **Healing**: Each completed visit restores health: `delta = (1 - health_at_plan_time) / planned_visits`.
5. **Payment**: Households pay for completed visits. Government subsidy is configurable via `healthcare_visit_subsidy_share`.

### Doctor Training Pipeline

- Total training: 208 ticks (4 years)
- First half (ticks 0-103): Student — cannot work
- Second half (ticks 104-207): Resident — can work in healthcare at 0.5 visits/tick
- After completion: Doctor — contributes 2-3 visits/tick
- Enrollment throttled based on active trainees and healthcare backlog signals

### Healthcare Staffing

- Backlog-driven: `desired_workers = ceil((arrivals_ema + backlog/horizon) / capacity_per_worker)`
- Per-firm doctor cap: `ceil(population * 0.002)` (0.2% of households)
- Healthcare firms prioritized in hiring order before other sectors

---

## Tick Lifecycle

Each tick executes these phases in order:

| Phase | What Happens |
|-------|-------------|
| 1. Reset counters | Clear per-tick consumption counters, legacy remnants |
| 2. Firm planning | Each firm plans production, labor needs, prices, wages |
| 3. Household planning | Each household plans labor supply and consumption budget |
| 4. Healthcare requests | Households submit healthcare service requests to queues |
| 5. Healthcare staffing | Backlog influences healthcare firm hiring plans |
| 6. Medical training | Student/resident progression, debt accrual, enrollment |
| 7. Labor matching | Bilateral matching: firms sorted by ID, workers matched by skills. Healthcare firms with backlog prioritized |
| 8. Apply labor | Wages paid, skill growth applied, experience accumulated |
| 9. Production | Firms produce goods using Cobb-Douglas function with wellbeing and infrastructure multipliers |
| 10. Goods market | First-come-first-served clearing by household ID. Food/housing/services only (not healthcare) |
| 11. Healthcare processing | Healthcare firms process queued visits up to capacity |
| 12. Government taxes | Wage and profit tax collection |
| 13. Government transfers | Unemployment benefits, social transfers |
| 14. Apply purchases | Household cash debited, firm revenue credited |
| 15. Inventory consumption | Households consume 10% of pantry per tick; counters credited |
| 16. Government investment | Infrastructure, technology, social program spending |
| 17. Wellbeing update | Health, happiness, morale recalculated for all households |
| 18. Firm exits | Bankrupt firms removed, employees laid off |
| 19. Firm entry | New firms created in under-served categories |
| 20. Policy adjustment | Government adjusts tax rates, benefits based on conditions |
| 21. Statistics | Aggregate metrics computed and emitted |

### Warmup Period

The first `CONFIG.time.warmup_ticks` ticks are a warmup period where baseline
(government) firms operate at higher capacity to bootstrap the economy. The
default is currently 10 ticks, but it is configuration-driven rather than
hard-coded. After warmup, baseline firms gradually reduce their workforce to let
private firms compete.

---

## Market Mechanics

### Labor Market

- **Matching**: Firms sorted by `firm_id`; each firm hires from the pool of job-seekers.
- **Priority**: Healthcare firms with active backlogs are prioritized before other sectors.
- **Wage determination**: `actual_wage = wage_offer * (1 + skill_premium + experience_premium)`.
- **Skill premium**: Up to 50% for max skill (0.5 * skills_level).
- **Experience premium**: 5% per year of industry experience, capped at 50%.

**Firm hiring throughput:**

Firms can hire up to `max(max_hires_per_tick, ceil(workers * 0.25))` workers per tick. The `max_hires_per_tick` trait (1–4 workers depending on personality: conservative, moderate, aggressive) ensures even small/zero-worker firms can hire. The 25% scaling ensures growing firms can actually catch up to demand. Contraction is similarly bounded by `max(max_fires_per_tick, ceil(workers * 0.20))`.

Hiring intent is gated by two conditions: sell-through rate ≥ 65% (firm is selling most of what it produces) and cash runway above the survival-mode threshold (2 ticks). A firm with adequate demand but short runway does not hire; a firm with good runway but poor sell-through does not hire. Both gates must pass for expansion to proceed.

**On-the-Job Search (Newspaper Mechanic):**

Employed households periodically check whether another firm is offering
significantly better wages. The check is staggered by a cooldown so workers do
not all sample the market at once. When possible, the comparison uses the
posted wage signal from the worker's current employer category rather than one
economy-wide average. Job-switchers enter the labor pool as active candidates
that tick.

- Category-level posted wages are computed from private firms' planned wage offers.
- If no category-specific signal is available, the household falls back to the global mean posted wage.
- If a job-switcher fails to match with a new employer during that tick's matching phase, they fall back to their previous employer rather than becoming unemployed. Voluntary job search cannot create accidental layoffs.
- This mechanic creates competitive wage pressure on firms from employed workers, not just from the unemployed pool.

### Goods Market

- **Clearing**: First-come-first-served by `household_id` order.
- **Selection**: Households choose firms based on price, quality, and stochastic noise.
- **Price elasticity**: Food is inelastic (0.5), services somewhat elastic (0.8), housing elastic (1.5).
- **Satiation caps**: Food purchases capped at ~3 units/tick; healthcare at 5 units/tick to prevent hoarding.

### Production

- **Cobb-Douglas**: `output = units_per_worker * workers^alpha` (alpha = 0.82, diminishing returns).
- **Productivity multipliers**: Infrastructure investment, worker experience, worker wellbeing all multiply base output.
- **Just-in-time**: Firms produce to replace sales, not to build inventory.

---

## Key Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `warmup_ticks` | 10 | Duration of government-heavy warmup (reduced from 52; override with `--warmup-ticks`) |
| `food_health_mid_threshold` | 2.0 | Food units for moderate health |
| `food_starvation_penalty` | 0.05 | Health penalty per tick without food |
| `health_recovery_per_medical_unit` | 0.02 | Health restored per medical inventory unit consumed |
| `consumption_rate` | 0.10 | Fraction of inventory consumed per tick (half-life ~7 ticks) |
| `diminishing_returns_exponent` | 0.82 | Cobb-Douglas alpha for production |
| `bankruptcy_threshold` | -1000 | Cash level triggering firm exit |
| `skill_growth_rate` | 0.001 | Passive skill improvement per tick |
| `experience_premium_rate` | 0.05 | Wage premium per year of experience |
| `subsistence_min_cash` | 50.0 | Budget threshold that triggers desperation savings drawdown |
| `savings_drawdown_rate` | 1–5% | Per-household, personality-derived fraction of cash savings spent per tick |
| `healthcare_capacity_per_worker_default` | 2.0 | Visits per healthcare worker per tick |

For the full 400+ parameter reference, see `backend/config.py`.

---

## Economic Dynamics

### What Creates Growth
- Employment → wages → consumption → firm revenue → more hiring
- Government infrastructure investment compounds productivity over time
- Skill and experience accumulation increase worker output
- Private firms outcompete baseline firms on quality

### What Causes Recessions
- Food shortage → health drops → can't work → no income → deeper poverty
- Firm bankruptcy cascades → mass layoffs → demand collapse
- Government deficit → reduced transfers → weaker safety net
- Wellbeing death spiral: unhappy → unproductive → lower output → unhappier

### Built-in Stabilizers
- Government counter-cyclical policy (automatic tax/benefit adjustments)
- Baseline firms as employer of last resort
- Mercy floor on happiness decay (below 0.25)
- Minimum health threshold (0.10) for labor participation
- New firm creation when market has too few competitors
