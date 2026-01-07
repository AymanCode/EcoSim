# Consumption Planning Optimization Plan

Scope
- Target functions:
  - `backend/agents.py` `_plan_category_purchases()`
  - `backend/economy.py` `_batch_plan_consumption()`
- Goal: reduce time in `firm_selection` and `quantity_calc` while preserving outcomes.

Instrumentation summary (10K households, 10 ticks)
- Total time in consumption planning (inside category purchases):
  - `firm_selection`: ~4.18s
  - `quantity_calc`: ~3.16s
  - `price_cap`: ~0.75s
  - `affordability`: ~0.29s
- Calls: 300k per category per 10 ticks.
- Conclusion: focus on `firm_selection` and `quantity_calc` paths.

Key invariants to preserve
- Allocation order and stochastic noise behavior stays the same.
- Same per-household purchase outputs for identical random seeds.
- Same price caps and affordability logic.

---

## Plan A (low risk, minimal behavior changes)

Objective
- Reduce Python overhead per category by cutting redundant allocations and list conversions.

Steps
1) Reuse NumPy arrays across categories where possible:
   - Precompute per-category arrays of firm_ids, prices, qualities once per tick in `_batch_plan_consumption()`.
   - Pass those arrays into `_plan_category_purchases()` instead of rebuilding them per household.
2) Remove redundant local list creation:
   - Today `affordable_options` is already filtered; keep array creation only once per category.
3) Minimize dict lookups inside inner loops:
   - Use local variables for `self.quality_lavishness`, `self.price_sensitivity`, and `price_cap`.

Expected impact
- 15–30% reduction in `firm_selection` + `quantity_calc`.

Risk level
- Low. No changes in allocation logic or ordering.

Validation
- Compare per-firm sales and per-household purchases on a small seeded run (1k, 50 ticks).
- Ensure aggregate metrics remain the same.

---

## Plan B (medium risk, bounded refactor)

Objective
- Precompute category firm arrays and cache per-category stochastic noise per tick to avoid repeated list comprehensions.

Steps
1) In `_batch_plan_consumption()`, build per-category:
   - `firm_ids`, `prices`, `qualities`, and `valid_mask` arrays.
2) Pass these arrays to `_plan_category_purchases()` and skip rebuilding them per household.
3) Generate noise vectors per category per household in a single NumPy call (still random, same distribution).

Expected impact
- 30–50% reduction in `firm_selection`.

Risk level
- Medium. Noise generation may shift stochastic properties if done differently.

Validation
- Verify distributional behavior (mean/variance of utilities) across sample runs.
- Confirm output changes are within expected stochastic variation.

---

## Plan C (high risk, algorithmic change)

Objective
- Move firm selection to a vectorized, per-category batch with all households at once.

Approach
- Compute utilities and softmax across all households in one batch per category.
- Allocate budgets in a batched matrix form.

Expected impact
- 2x+ speedup for consumption planning at scale.

Risk level
- High. Likely changes allocation order and stochastic outcomes.

Validation
- Use statistical comparison across multiple seeds.
- Ensure macro metrics distributions remain stable.

---

## Recommendation

Start with Plan A. If profiling still shows `firm_selection` dominating, move to Plan B with a narrow controlled change.

---

## Acceptance criteria

- No structural changes to simulation output on small seeded runs (Plan A).
- Clear, measurable reduction in total runtime per tick on 10K agents.

