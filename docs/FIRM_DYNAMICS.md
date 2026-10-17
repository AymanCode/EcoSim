# Firm Dynamics

How private firms now make labor, wage, and pricing decisions after warmup.

---

## Scope

These rules apply to **private, non-healthcare firms after warmup**.

They do **not** replace the special handling for:

- baseline safety-net firms
- healthcare firms
- loan headcount commitments
- survival-mode internals during acute distress

The goal is to keep the existing firm logic intact while making wage-setting,
hiring, and pricing react to the same view of firm health.

---

## Shared Firm-Health Snapshot

Each private firm now computes one shared health snapshot per tick before
planning labor, prices, and wages.

The snapshot includes:

- `cash_runway_ticks`
- `smoothed_profit_margin`
- `sell_through_rate`
- `inventory_weeks`
- `unfilled_positions_streak`
- `worker_turnover_this_tick`
- `survival_mode`
- `burn_mode`
- `category_wage_anchor_p75`

This matters because the old model let wage planning and labor planning infer
firm health separately. A firm could be hiring off one signal while wages were
being pushed by another. The shared snapshot makes those planners react to the
same conditions.

### Notes on the fields

- `smoothed_profit_margin` is based on short-run EMAs of profit and revenue,
  not a single noisy tick.
- `cash_runway_ticks` promotes runway into first-class state instead of
  recomputing it ad hoc in multiple planners.
- `unfilled_positions_streak` tracks repeated hiring failure rather than one
  bad hiring tick.
- `category_wage_anchor_p75` gives each firm a market wage reference without
  synchronizing the whole economy to one hard ceiling.

---

## Wage Setting

Private post-warmup wage-setting now uses a ratchet off the firm's current
`wage_offer`.

Conceptually:

```python
pressure = compute_wage_pressure(snapshot, firm_traits)
target_wage = current_wage * (1 + pressure * wage_adjustment_rate)
wage_offer = clamp(target_wage, minimum_wage_floor, category_cap)
```

### Upward wage pressure

- persistent unfilled positions
- worker turnover
- very tight sell-through with low inventory

### Downward wage pressure

- negative smoothed profit margin
- short cash runway
- weak sell-through or excess inventory

### Firm uniqueness

The formulas are shared, but the response speed is not. Existing firm traits
such as `risk_tolerance`, `wage_adjustment_rate`, and sampled adjustment ranges
make firms react differently to the same market conditions.

Aggressive firms tolerate risk longer and respond more to hiring difficulty.
Conservative firms protect runway sooner and cap wage growth more tightly.

### Wage cap

The wage cap is not based on one firm's own realized revenue spike. It uses a
category wage anchor:

```python
category_cap = category_wage_anchor_p75 * firm_specific_multiplier
```

That keeps the model from generating one-tick wage explosions while still
preserving firm heterogeneity.

### Emergency wage brake

`adjust_wages_to_revenue_ratio()` still exists, but only as an emergency brake
for private non-healthcare firms. It is no longer the primary wage policy.

Normal wage control should come from the ratchet. The brake only steps in when
wages are far out of line with revenue and the firm is already financially
stressed.

---

## Hiring and Contraction

The labor planner keeps the existing demand, inventory, survival-mode, and
staged-contraction logic. The main addition is an **expansion gate**.

If a private post-warmup firm has:

- negative `smoothed_profit_margin`, and
- `cash_runway_ticks` below its trait-driven threshold

then the firm is prevented from expanding headcount that tick.

That means:

- new hires are blocked
- layoffs and contraction logic still run
- survival-mode and burn-mode behavior remain active

This is intentionally narrower than a full labor-planner rewrite. The existing
contraction tree already knows how to shrink distressed firms. The expansion
gate stops hiring from fighting against that logic.

### Startup bootstrap

Private startups are still allowed to bootstrap from zero workers in a small
way. The expansion gate is aimed at distressed incumbents, not at preventing
new firms from forming.

---

## Pricing

Private pricing now uses the sampled `price_adjustment_rate` and
`target_inventory_weeks` traits rather than hardcoded tiny moves.

The key idea is proportional inventory pressure:

- if inventory is far above target, cut price more aggressively
- if the firm is selling out with low stock, raise price modestly
- if imbalance is mild, moves stay mild

Conceptually:

```python
inventory_weeks = inventory / expected_sales

if inventory_weeks >= target_inventory_weeks * 1.5:
    severity = min(inventory_weeks / target_inventory_weeks - 1.0, 2.0)
    price *= (1 - price_adjustment_rate * severity)
elif sell_through_rate >= 0.95 and inventory_weeks < target_inventory_weeks * 0.5:
    price *= (1 + price_adjustment_rate * 0.5)
```

This creates visible market signals during real gluts or shortages while still
letting different firms react at different speeds.

### What stays special-cased

- baseline firms during warmup still use their safety-net pricing rules
- healthcare keeps queue-pressure-aware pricing

---

## Worker Effectiveness

Since round 1 PR2, every producing firm (goods and Services) turns a worker
into output with one rule, `worker_effectiveness(skill, health, morale,
happiness)` in `backend/worker_effectiveness.py`:

```
output per worker = units per worker               (the firm)
                  x (1 + 0.25*skill [+ experience]) (skill factor)
                  x (1 + 0.12*(morale + happiness - 1))  (effort)
                  x (1 - absence(health))           (hours present)
absence(h) = 1.1% * (1 + 1.2*(1 - h)) / (1 + 1.2*(1 - 0.77))
```

The three worker factors multiply, so none can make up for another.

- Skill factor: kept from main's goods path (+25% at skill 1.0). It equals
  the skill pay premium firms pay at hire, so productivity and pay rise
  together (Hellerstein, Neumark & Troske 1999). The 0.25 has no external
  source of its own. Goods firms add the category-experience bonus (5% a
  year, capped at 50%), as before.
- Effort: efficiency-wage effort (Akerlof & Yellen 1990). Morale is the
  fair-treatment state, happiness the broader mood; they share drivers, so
  effort reads their mean. 0.88x at a mean of 0, 1.0x at 0.5, 1.12x at 1
  (Oswald, Proto & Sgroi 2015: ~12%; Bellet, De Neve & Ward 2024: ~13%).
- Hours present: sickness absence. 1.1% of hours at EcoSim's average
  employed health (BLS CPS Table 47, own illness/injury/medical lost-worktime
  rate), linear in health, 2.2x higher at health 0 than at health 1
  (Halford et al. 2012). Range about 98.1-99.1%. Workers under health 0.10
  are already out of the labor market (`can_work`).
- Goods: the firm's average multiplier scales its planned output, then the
  infrastructure and supply-shock multipliers apply, and output stays capped
  by capacity.
- Services: each worker supplies `units_per_worker x multiplier`, clipped to
  `services_units_per_worker_range` (1-7).

`HouseholdAgent.get_performance_multiplier()` returns effort x hours present
(the skill-free part) for diagnostics.

Labor demand does not read the multiplier. `_workers_for_sales`,
`_capacity_for_workers` and `_profit_optimal_workers` plan headcount from the
firm's frontier (`units_per_worker`, capital); the multiplier only scales the
realized output afterwards. Wage offers do not read it either, and layoffs
take the roster front (`employees[:n]`), not the least effective worker.

Config (all in `CONFIG.firms`): `worker_effort_range` (0.12),
`worker_absence_reference_rate` (0.011), `worker_absence_reference_health`
(0.77), `worker_absence_sick_ratio` (2.2). See `config.py` for units and
valid ranges and `backend/worker_effectiveness.py` for the derivations.

---

## Labor-Market Signals

The household "newspaper" mechanic is now more local.

Employed workers compare their current wage against the posted wages in their
own employer's category when that category signal is available:

- Food workers compare against Food postings
- Housing workers compare against Housing postings
- Services workers compare against Services postings

If no category-specific signal is available, the simulation falls back to the
global mean posted wage.

This matters because a single economy-wide mean can synchronize every worker to
one number even when sector conditions are very different.

---

## Design Intent

The system is trying to create a cleaner feedback loop:

1. Distressed firms stop expanding.
2. Wage offers adjust gradually instead of spiking off one revenue event.
3. Inventory gluts produce visible price cuts.
4. Workers compare themselves to relevant sector wages, not a single economy-wide average.

The result should be a labor market and goods market that clear through
incremental local feedback rather than through one-off jumps.
