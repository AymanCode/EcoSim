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

### Sticky prices (round 1 PR4a)

With `CONFIG.firms.sticky_prices_enabled` (default on), private Food,
Services and Healthcare firms post a price that changes only at a price
review. The rules above still run every tick, but on a background shadow
price (`FirmAgent.price_shadow`): the price the firm would have reached
repricing weekly. At a review the posted price jumps to the shadow.

```python
hazard = (1 / interval) * (1 + gap / 0.10) * (1 + 1.38 * max(0, inflation - 0.125))
pressure += hazard            # every tick
if pressure >= 1:             # review
    price = shadow; pressure = 0
gap = abs(price / shadow - 1); inflation = CPI 52-week rate
```

- `interval` (calm-market weeks between reviews) is drawn once per firm from
  its category's range: Food 15-39 weeks (Nakamura & Steinsson 2008,
  unprocessed 3.5 / processed 9.0 months), Services 19-34 (Bils & Klenow
  2004, all items 4.3 / services 7.8 months), Healthcare 34-65 (Bils &
  Klenow, services 7.8 / medical care 14.9 months). The draw hashes
  `firm_id`, so no random number is consumed.
- A gap of 10% doubles the hazard: 9.5-11% is the typical size of a regular
  price change in menu-cost data (Golosov & Lucas 2007; Midrigan 2011).
- Inflation above 12.5% a year speeds reviews (Gagnon 2009, Mexico).
- `last_price_review_tick` is the latest review; `next_price_review_tick` is
  the projected next one at the current hazard, always in the future between
  reviews. They are the contract a review-aware price cap reads (the hold
  in #27's `Economy._price_review_due`; #27 was closed and the hold dropped
  on 2026-10-17, so nothing on main reads them yet).
- Not sticky: baseline firms, warm-up, and Housing (settlement resets rent
  from occupancy every tick, which would overwrite a held rent).
- Services: market clearing can still raise a Services price on scarcity
  between reviews (`_effective_market_price`), as on main.

Implementation: `FirmAgent.uses_sticky_prices`, `price_review_interval`,
`price_review_hazard`, `plan_sticky_pricing`; called from
`Economy._phase_firm_planning`. Flag off: every firm reprices every tick,
identical to main.

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
