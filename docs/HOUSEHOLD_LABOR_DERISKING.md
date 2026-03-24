# Household Labor De-Risking Notes

This document explains the household-side labor updates added for the de-risk rollout.

## Why This Was Added

At higher scale (for example, 10k households), unemployment can persist for two avoidable reasons:

1. Some unemployed households are not marked as active job seekers.
2. Some long-term unemployed households keep reservation wages above current market offers.

These changes add guardrails for both cases while keeping behavior configurable and reversible.

## What Changed

### 1) Household labor plan now always searches when unemployed

In `HouseholdAgent.plan_labor_supply`, job-search intent is now:

- `searching_for_job = (not self.is_employed) or (self.cash_balance < living_cost)`
- If household cannot work this tick (`not self.can_work`), search is forced to `False`.

Code reference:
- `backend/agents.py` (`plan_labor_supply`)

Effect:
- Removes the "unemployed but idle" state for work-capable households.
- Keeps incapacity behavior intact (sick/in-training households do not enter matching).

### 2) Economy-side labor plan normalization (pre-matching)

A new pass runs after all household labor plans are generated and before labor matching:

- Method: `_normalize_household_labor_plans(...)`
- File: `backend/economy.py`

Normalization rules:

1. If a household cannot work, set `searching_for_job = False`.
2. If `ECOSIM_FORCE_UNEMPLOYED_SEARCH=1` and household is unemployed+can_work, set `searching_for_job = True`.
3. If `ECOSIM_CLAMP_UNEMPLOYED_RESERVATION=1` and unemployment duration exceeds threshold, cap reservation wage to:
   - `max(max_wage_offer_next_tick, government_minimum_wage)`

This pass is called in `Economy.step()` right after household labor planning.

## New Runtime Flags

Configured in `Economy.__init__` (env vars):

- `ECOSIM_FORCE_UNEMPLOYED_SEARCH` (default `1`)
- `ECOSIM_CLAMP_UNEMPLOYED_RESERVATION` (default `1`)
- `ECOSIM_UNEMPLOYED_CLAMP_TICKS` (default `8`)

Related diagnostics/matcher flags:

- `ECOSIM_LABOR_MATCH_MODE` (`fast`/`legacy`)
- `ECOSIM_COMPARE_LABOR_MATCH`
- `ECOSIM_LABOR_DIAGNOSTICS`

All are documented in `.env.example`.

## New Diagnostics You Can Watch

Two new metrics were added to economy metrics output:

- `labor_forced_search_adjustments`
- `labor_reservation_clamp_adjustments`

Interpretation:

- `labor_forced_search_adjustments > 0`: households were corrected from non-searching to searching.
- `labor_reservation_clamp_adjustments > 0`: long-term unemployed reservation wages were above market and got capped.

These are exported with other labor diagnostics (for example, `labor_unemployed_not_searching`, `labor_seekers_wage_ineligible`).

## Behavior and Tradeoffs

Benefits:

- Reduces artificial unemployment from search-state drift.
- Helps long-term unemployed re-enter when market wages are below stale expectations.
- Keeps changes reversible via env flags.

Risks:

- Reservation clamping can reduce wage selectivity realism if set too aggressively.
- Forced search may increase labor supply pressure and temporarily lower accepted wages.

Mitigation:

- Tune `ECOSIM_UNEMPLOYED_CLAMP_TICKS` upward if you want slower intervention.
- Disable clamp or forced search independently for A/B runs.

## Suggested Validation Checks

After enabling these changes, check these trends over 100-300 ticks:

1. `labor_unemployed_not_searching` should be near zero for work-capable households.
2. `labor_seekers_wage_ineligible` should fall versus baseline.
3. Unemployment should improve without collapsing mean wage.
4. Tick duration should stay similar (normalization is O(households) and lightweight).

## Interview Talk Track (Short)

"I added a de-risk labor normalization layer between household planning and matching. It guarantees unemployed, work-capable agents are discoverable by the matcher and adds a configurable market-aware reservation wage clamp for long-term unemployment. I instrumented it with explicit correction metrics so we can quantify intervention frequency and run A/B validation against legacy behavior."
