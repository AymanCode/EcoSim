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

1. **Labor supply** — Decides whether to seek work, sets reservation wage based on expected wage and skills.
2. **Consumption planning** — Allocates budget across food, housing, services, healthcare based on need and preferences. Food and healthcare have satiation caps to prevent hoarding.
3. **Goods consumption** — Eats from pantry each tick (10% depletion rate). Food consumption credits `food_consumed_this_tick`; same for services and healthcare.
4. **Wellbeing update** — Health, happiness, and morale update based on consumption, employment, and wages. Each has natural decay rates (health: 0.5%/tick, happiness: 1%/tick, morale: 2%/tick).
5. **Skill growth** — Passive skill improvement while employed (`0.001 * (1 - skills_level)` per tick). Experience accumulates per industry category.

**Key Mechanics:**

- **`can_work` threshold**: Health must be >= 0.10 to participate in labor market. Below this, the household is too sick to work.
- **Performance multiplier**: `0.5 + (morale×0.5 + health×0.3 + happiness×0.2)` — ranges from 0.5x to 1.5x, directly affects production output.
- **Mercy floor**: When happiness drops below 0.25, decay pauses to prevent irreversible death spirals.
- **Wage premiums**: Actual wage = `wage_offer * (1 + skill_premium + experience_premium)`. Skill premium up to 50% at max skill; experience premium 5% per year, capped at 50%.

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

1. **Production planning** — Just-in-time: produce `max(expected_sales, minimum_floor)` rather than targeting inventory levels. Uses Cobb-Douglas production: `output = base_productivity * workers^alpha` (alpha = 0.82).
2. **Labor planning** — Determines headcount needs, posts wage offers. Experienced workers get productivity bonuses.
3. **Pricing** — PID-style inventory controller targeting ~2 weeks of supply buffer. Prices bounded by ±20% change per tick, floored at cost × 1.05.
4. **Wage setting** — Adjusts wage offers based on hiring success, vacancy rates, and personality type.

**Firm Personalities (assigned deterministically by `firm_id % 3`):**

| Personality | Investment | Risk | Price Speed | Wage Bidding | R&D |
|-------------|-----------|------|-------------|--------------|-----|
| Aggressive | 15% | 0.9 | Fast (10%) | Aggressive (15%) | 8% |
| Moderate | 5% | 0.5 | Medium (5%) | Balanced (10%) | 5% |
| Conservative | 2% | 0.2 | Slow (2%) | Cautious (5%) | 2% |

**Baseline (Government) Firms:**

- One per category (Food, Housing, Services, Healthcare)
- Act as safety-net providers with lower quality
- During warmup (first 52 ticks), hire proportional share of workforce
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
4. **Dynamic policy** — Adjusts tax rates and benefits based on unemployment and fiscal balance:
   - High unemployment (>15%): increase benefits 5%, transfers 10%
   - Low unemployment (<3%): reduce benefits 2%
   - Large deficit (<-$10K): raise taxes 2%
   - Large surplus (>$50K): lower taxes 2%

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

The first 52 ticks are a warmup period where baseline (government) firms operate at higher capacity to bootstrap the economy. After warmup, baseline firms gradually reduce their workforce to let private firms compete.

---

## Market Mechanics

### Labor Market

- **Matching**: Firms sorted by `firm_id`; each firm hires from the pool of job-seekers.
- **Priority**: Healthcare firms with active backlogs are prioritized before other sectors.
- **Wage determination**: `actual_wage = wage_offer * (1 + skill_premium + experience_premium)`.
- **Skill premium**: Up to 50% for max skill (0.5 * skills_level).
- **Experience premium**: 5% per year of industry experience, capped at 50%.

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
| `warmup_ticks` | 52 | Duration of government-heavy warmup |
| `food_health_mid_threshold` | 2.0 | Food units for moderate health |
| `food_starvation_penalty` | 0.05 | Health penalty per tick without food |
| `health_recovery_per_medical_unit` | 0.02 | Health restored per medical inventory unit consumed |
| `consumption_rate` | 0.10 | Fraction of inventory consumed per tick (half-life ~7 ticks) |
| `diminishing_returns_exponent` | 0.82 | Cobb-Douglas alpha for production |
| `bankruptcy_threshold` | -1000 | Cash level triggering firm exit |
| `skill_growth_rate` | 0.001 | Passive skill improvement per tick |
| `experience_premium_rate` | 0.05 | Wage premium per year of experience |
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
