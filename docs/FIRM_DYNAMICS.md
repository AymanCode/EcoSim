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
