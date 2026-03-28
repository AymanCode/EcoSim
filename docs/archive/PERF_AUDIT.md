# EcoSim Simulation Performance Audit

This document catalogs likely performance hotspots in the simulation loop and proposes changes grouped by effort. It is meant to be tackled item-by-item.

Scope
- Core simulation runtime: `backend/economy.py` and `backend/agents.py`
- Realtime UI loop: `backend/server.py` (data assembly and history tracking)

Notes
- This audit is based on code inspection, not profiling. A short profiling plan is included so we can validate priorities.
- Suggestions are grouped by effort: Low (small edits, low risk), Medium (localized refactors), High (structural redesign).

---

## Quick Profiling Plan (to validate priorities)

1) Per-tick timing buckets (low effort)
   - Add lightweight timing around major phases in `Economy.step()` and in `SimulationManager.run_loop()`.
   - Goal: identify which phases dominate at 1k, 10k households.

2) cProfile or py-spy run
   - Run a 200-tick sim with 1k households and capture top functions.
   - Confirm which loops (goods market, labor match, metrics, wellbeing) dominate.

---

## Hot Path Walkthrough (Economy.step)

`backend/economy.py` `Economy.step()` performs these major phases per tick:
- Firm planning (production/price/wage)
- Household planning (labor supply, consumption)
- Labor market matching
- Apply labor outcomes
- Apply production/costs
- Goods market clearing
- Government taxes/transfers
- Apply income/purchases
- Wellbeing update
- Firm exits/entry
- Statistics updates

This touches most households and firms multiple times per tick.

---

## Bottlenecks and Recommendations

### 1) Goods market clearing
Location
- `backend/economy.py` `_clear_goods_market()`

Why it is expensive
- Iterates over households and their planned purchases.
- Builds per-household dicts and per-firm sales dicts with Python loops.
- For each planned purchase, it iterates across firms for a good (nested loop).

Low effort
- Reduce number of planned purchases by filtering low-budget households or low-quantity items (config toggle or threshold).
- Lower frequency of the goods market in "realtime UI" mode (e.g., every N ticks) when visualizing.

Medium effort
- Precompute `goods_to_indices` once per tick and reuse across households (already done) but avoid `sorted(household_consumption_plans.items())` when ordering does not affect results.
- Batch per-household result updates to reduce dict churn (e.g., accumulate in lists and only convert to dict at end).
- Skip goods with total inventory == 0 early.

High effort
- Rewrite goods clearing to be vectorized by good category (matrix of household demand vs firm inventory) to reduce Python loops.
- Introduce a "market clearing kernel" that works on NumPy arrays end-to-end.

---

### 2) Labor market matching
Location
- `backend/economy.py` `_match_labor()`

Why it is expensive
- Iterates all households each tick, manages multiple dicts/sets.
- Separate firm/household plans are dict-heavy.

Low effort
- Cache lookups for households and firms (already partly done) but avoid repeated dict accesses in inner loops.
- Skip matching for households already employed when no layoffs are planned (fast path).

Medium effort
- Use arrays for household state (employed, wage, skills) and firm offers; then match in batches.
- Replace Python sorting of candidates with NumPy argsort for skills/wages once per category.

High effort
- Redesign labor matching as a separate module with data-oriented structures (arrays + indices) and minimal Python branching.

---

### 3) Production and productivity calculation
Location
- `backend/economy.py` `_calculate_experience_adjusted_production()`

Why it is expensive
- For each firm, iterates employees and uses `next(...)` to find the household by id (O(employees * households) in worst case).

Low effort
- Replace `next((h for h in self.households ...))` with `self.household_lookup.get(employee_id)`.
  (There is already a lookup dict in Economy.)

Medium effort
- Precompute per-household productivity multipliers once per tick (skills + experience + wellbeing), then aggregate by firm.

High effort
- Maintain firm-level aggregate stats incrementally (sum of multipliers, headcount) updated on labor changes, not recomputed per tick.

---

### 4) Metrics and statistics
Locations
- `backend/economy.py` `_update_statistics()`
- `backend/economy.py` `get_economic_metrics()`
- `backend/server.py` `SimulationManager.run_loop()`

Why it is expensive
- `get_economic_metrics()` does multiple full list constructions, sorting, and percentiles each tick.
- `run_loop()` computes additional aggregates (GDP, net worth, price and supply histories) every tick.
- Duplicate work: both Economy and server compute overlapping metrics.

Low effort
- Compute metrics every N ticks for UI (e.g., every 5–10 ticks) while keeping simulation tick-level data internal.
- Limit history arrays to a fixed window (ring buffer) to prevent unbounded growth in memory.

Medium effort
- Centralize metrics computation in Economy and have server reuse it; avoid recomputing in server.
- Track percentiles with approximate methods (or cache sorted arrays periodically).

High effort
- Introduce a metrics pipeline with incremental updates (online mean/variance, streaming percentiles).

---

### 5) Household consumption and wellbeing
Locations
- `backend/economy.py` `_batch_plan_consumption()`
- `backend/economy.py` `_batch_update_wellbeing()`
- `backend/agents.py` `HouseholdAgent.consume_goods()`

Why it is expensive
- `_batch_plan_consumption()` is vectorized (good), but still reads goods inventory via `sum(h.goods_inventory.values())` for every household.
- `consume_goods()` iterates per household over inventory dict each tick.
- Wellbeing batch uses `sum(h.goods_inventory.values())` again.

Low effort
- Cache household total goods value per tick to avoid multiple `sum(...)` passes.
- Avoid `consume_goods()` for households with empty inventories.

Medium effort
- Maintain `household.total_goods` and update it incrementally in `apply_purchases()` and `consume_goods()`.
- Replace per-household dict iteration for goods consumption with numeric arrays for the core categories.

High effort
- Move to a fixed-size goods vector per household (e.g., food/housing/services arrays), eliminating dict iteration entirely.

---

### 6) Government transfer/tax snapshot building
Locations
- `backend/economy.py` `_build_household_transfer_snapshots()`
- `backend/economy.py` `_build_household_tax_snapshots()`
- `backend/economy.py` `_build_firm_tax_snapshots()`

Why it is expensive
- Builds multiple snapshot lists by looping all households/firms each tick.

Low effort
- Combine snapshot builds into a single pass over households and a single pass over firms.

Medium effort
- Use lightweight namedtuples or arrays; avoid dict creation in inner loops.

High effort
- Rework tax/transfer planning to operate directly on arrays without intermediate snapshots.

---

### 7) Housing system
Location
- `backend/economy.py` `_apply_housing_market()`

Why it is expensive
- For each renting household, it searches housing firms via `next(...)` which scans the list.
- Matching homeless households involves sorting and scanning.

Low effort
- Create a `housing_firm_lookup` dict (firm_id -> firm) at start of tick.

Medium effort
- Maintain occupancy and firm price arrays for faster matching.

High effort
- Separate housing market into its own matching module with precomputed affordability buckets.

---

### 8) Server-side UI payload construction
Location
- `backend/server.py` `SimulationManager.run_loop()`

Why it is expensive
- Every tick builds large payloads (tracked subjects, histories, firm tables) and sends via WS.
- Metrics overlap with Economy’s metrics.

Low effort
- Reduce payload frequency (send every N ticks) and/or reduce fields in payload.
- Cap history arrays (ring buffer of last N ticks) to avoid memory growth.

Medium effort
- Move expensive aggregations into Economy and reuse precomputed metrics.

High effort
- Introduce event-based UI updates (only send deltas or summary) rather than full state every tick.

---

## Effort Tiers Summary

Low effort (1–2 days)
- Replace `next(...)` household lookups with `self.household_lookup.get(...)` in `_calculate_experience_adjusted_production()`.
- Add a ring buffer for histories in `backend/server.py`.
- Compute UI metrics every N ticks rather than every tick.
- Cache household `total_goods` to avoid repeated `sum(goods_inventory)`.

Medium effort (3–7 days)
- Batch or vectorize labor matching and/or goods clearing for the main categories.
- Consolidate metrics computation (single source of truth in Economy).
- Combine snapshot builds (tax/transfers) into single passes.

High effort (1–3 weeks)
- Data-oriented refactor for households/firms (arrays for core attributes).
- Vectorized goods/labor markets end-to-end.
- Separate simulation kernel from UI/transport entirely (event or batch streaming).

---

## Suggested Order of Attack

1) Low-effort quick wins (lookup fixes, history caps, metrics frequency)
2) Profile again and confirm top 2 hotspots
3) Medium-effort batch changes (labor match + goods clearing)
4) Decide if high-effort redesign is worth it for target scale

---

## Open Questions

- What is your target scale for “resume” demos (1k agents vs 100k)?
- Is realtime UI required during large runs, or can we run headless and stream summary snapshots?
- Are we willing to add a “fast mode” that trades accuracy for speed (e.g., aggregated households)?
