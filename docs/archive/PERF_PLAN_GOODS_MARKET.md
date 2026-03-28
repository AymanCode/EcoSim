# Goods Market Clearing Performance Plan

Scope
- Target: `backend/economy.py` `_clear_goods_market()`
- Goal: reduce per-tick CPU time and Python object churn without changing simulation outcomes.

Baseline summary (current behavior)
- For each household (sorted by id), iterate planned purchases.
- For each purchase, distribute demand across eligible firms sorted by price (and id).
- Track per-household purchases and per-firm sales.
- Uses Python dicts for plans and results; nested loops over households and firms.

Key risks
- Changing ordering can change allocations (and therefore economics).
- Floating point changes can change outcomes slightly.
- Any batching that changes per-household priority could alter fairness.

Desired invariants (must keep)
- Household processing order remains `sorted(household_consumption_plans.items(), key=id)` unless explicitly approved.
- Firm selection order per good remains sorted by price then firm id.
- Per-household purchase totals and per-firm sales match current logic to within floating-point tolerance.

---

## Plan A (low risk, minimal behavior changes)

Objective
- Reduce Python overhead while preserving exact ordering and allocation.

Steps
1) Precompute and reuse stable arrays:
   - `firm_ids`, `firm_prices`, `firm_goods`, `firm_remaining` already exist.
   - Add `firm_category` or other frequently accessed arrays only if needed.
2) Reduce per-household dict churn:
   - Avoid per-household dict creation for households with empty `planned_purchases`.
   - Pre-initialize `per_household_purchases` only when the household actually buys something.
3) Skip early:
   - If `desired_qty <= 0` or no firm inventory remains for the good, skip quickly.
4) Keep ordering:
   - Keep household order as-is.
   - Keep `goods_to_indices` sorted by price then id.

Expected impact
- 10–25% reduction in CPU time in this phase (mostly reduced Python overhead).

Risk level
- Low. No logic changes to allocation or ordering.

Validation
- Run a small deterministic run (seeded or fixed) and compare:
  - Per-firm sales (units, revenue) for a fixed tick.
  - Per-household purchases for a sample of households.
  - Aggregated metrics (GDP, unemployment) unchanged.

---

## Plan B (medium risk, still preserves ordering)

Objective
- Reduce inner-loop work by batching demand per good and applying in a single pass per good.

Steps
1) Transform household plans to per-good demand lists while preserving household order:
   - For each good, keep a list of `(household_id, desired_qty)`.
2) For each good:
   - Iterate the sorted firms list once, and allocate to households in order.
3) Store results:
   - Update per-firm sales and per-household purchase dicts as allocations occur.

Expected impact
- 25–45% reduction in CPU time for market clearing (fewer nested loops).

Risk level
- Medium. Allocation order must exactly mirror the current per-household loop to avoid outcome changes.

Validation
- Same as Plan A, plus:
  - Verify per-household purchase totals match exactly for a fixed seed.

---

## Plan C (high risk, larger refactor)

Objective
- Vectorized allocation by good category using NumPy arrays.

Approach
- Build a demand vector and inventory vector for each good.
- Allocate in bulk, possibly with cumulative sums and clipping.

Expected impact
- 2x–5x speedup in market clearing for large runs.

Risk level
- High. Vectorization likely changes allocation order unless carefully constrained.

Validation
- Extensive diff tests across multiple ticks and seeds.
- Performance profiling to verify gains.

---

## Recommendation

Start with Plan A. If performance is still insufficient, move to Plan B after adding a small golden test for allocations.

---

## Proposed acceptance criteria

- No change in household or firm counts or in aggregate metrics over a 100–200 tick test run at 1k households.
- For Plan A/B: per-firm sales and per-household purchases match baseline (within floating-point tolerance).

