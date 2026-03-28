# EcoSim 2.0 Healthcare Service Model

This document is the authoritative reference for how healthcare works in EcoSim 2.0.

## Purpose

Healthcare is modeled as a non-storable service, not a tradable inventory good.

- Households request care based on health need.
- Healthcare firms process queued visits up to labor-based capacity.
- Completed visits restore health.
- Firms still hire workers, pay wages, earn revenue, and pay taxes.

## Core Rules

1. No medical inventory.
2. No household shopping basket for healthcare goods.
3. Demand is health-driven (plus preventive checkups and followups).
4. Operational state is backlog/queue, not unsold stock.

## Entity State

### Household state used by healthcare

- `health` in `[0, 1]`
- `care_plan_due_ticks` (scheduled followups)
- `last_checkup_tick`
- `queued_healthcare_firm_id` (prevents duplicate queueing)
- `healthcare_consumed_this_tick` (completed visits counter)
- medical workforce pipeline fields:
  - `medical_training_status` (`none`, `student`, `resident`, `doctor`)
  - `medical_training_start_tick`
  - `medical_school_debt_remaining`
  - `medical_doctor_capacity_cap`
- sampled traits:
  - `healthcare_preference`
  - `healthcare_urgency_threshold`
  - `healthcare_critical_threshold`

### Firm state used by healthcare

- `healthcare_queue` (FIFO list of household ids)
- `employees`
- `healthcare_capacity_per_worker`
- `healthcare_backlog_horizon_ticks`
- `healthcare_arrivals_ema`
- `healthcare_requests_last_tick`
- `healthcare_completed_visits_last_tick`
- `healthcare_idle_streak`
- `healthcare_capacity_carryover` (fractional capacity rollover)

## Tick Lifecycle (Healthcare)

1. Reset per-tick counters and clear any legacy healthcare inventory remnants.
2. Households submit healthcare requests (`_enqueue_healthcare_requests`).
3. Healthcare backlog influences staffing plan (`_plan_healthcare_service_labor`).
4. Medical training pipeline updates:
  - student progression
  - resident progression
  - debt interest accrual
  - throttled new med-school enrollment when shortage persists
5. Goods market runs for food/housing/services only.
6. Healthcare firms process queued visits (`_process_healthcare_services`).
7. Completed visits become firm revenue and household health updates.

Labor matching note:

- Healthcare firms with active backlog are prioritized in hiring order before normal sectors.
- This prevents persistent queue growth when aggregate labor demand is tight.

## Household Care-Seeking Logic

Decision method: `should_request_healthcare_service(current_tick)`.

Households now use annual sampled visit counts (52-tick window), not per-tick urgency draws.

At each annual anchor tick, each household samples visit count from a health-bucket distribution:

- health `>= 0.70`: 30% -> 0 visits, 40% -> 1 visit, 30% -> 2 visits
- health `< 0.70` and `>= 0.30`: 30% -> 1 visit, 40% -> 2 visits, 30% -> 3 visits
- health `< 0.30` and `>= 0.10`: 30% -> 2 visits, 40% -> 3 visits, 30% -> 4 visits
- health `< 0.10`: 50% -> 4 visits, 45% -> 5 visits, 5% -> 6 visits

Sampled visits are scheduled across the annual window and consumed one due-slot at a time.
Sampling is deterministic per household and annual anchor for reproducibility.

## Provider Selection

Provider selection prioritizes wait time:

- score = `queue_pressure + price_term`
- `queue_pressure = queue_len / capacity`
- `price_term` is near-zero for critical households (shortest wait dominates)

This keeps severe cases from delaying for price reasons.

## Queue Processing and Healing

Processing method: `_process_healthcare_services`.

- Effective capacity per tick:
  - `effective_capacity = floor(workers * capacity_per_worker)`
- Service is FIFO up to capacity.
- For each completed visit:
  - clear `queued_healthcare_firm_id`
  - increment `healthcare_consumed_this_tick`
  - apply staged heal amount from the sampled plan:
    - `delta = (1 - health_at_plan_time) / planned_visits`
    - `health = min(1.0, health + delta)`
  - update `last_checkup_tick`
  - no automatic followup generation; annual sampling controls revisit volume

## Firm Staffing (Backlog-Driven)

Healthcare staffing is not inventory-driven.

Core target:

- `desired_capacity = arrivals_ema + backlog / horizon`
- `desired_workers = ceil(desired_capacity / capacity_per_worker)`
- per-firm doctor headcount cap:
  - `max_workers = ceil(population * 0.002)` (0.2% of households)
  - example: 1000 households -> max 2 healthcare employees per healthcare firm

Then friction is applied:

- hires capped per tick
- layoffs capped per tick
- slow downsizing only after sustained idle streak
- baseline firms maintain minimum worker floor

Output per worker:

- Residents contribute up to `0.5` visits/tick.
- Doctors contribute approximately `2.0` to sampled cap `2.0-3.0` visits/tick.
- Fractional capacity carries over between ticks.

## Doctor Training Pipeline

Training length and stages:

- total training duration: `52 * 4 = 208` ticks
- first half (`0-103` ticks): `student`
  - cannot work any job
- second half (`104-207` ticks): `resident`
  - can work only in healthcare firms
  - contributes at most `0.5` visits/tick
- after completion (`208+` ticks): `doctor`
  - can work only in healthcare firms
  - contributes ~2-3 visits/tick depending on sampled cap and skill

Enrollment throttling:

- if active trainees `< 10`: at most 1 enrollment per 52 ticks
- if active trainees `>= 10`: at most 1 enrollment per 104 ticks
- enrollment occurs only when healthcare backlog/capacity shortage signal is high

## Pricing and Payment Flow

Visit price:

- Visit reimbursement uses `firm.price`.
- Baseline healthcare default price comes from `CONFIG.baseline_prices["Healthcare"]` (default `15.0`).
- Private/new firms start from baseline price logic and then use normal firm pricing updates.
- Healthcare pricing is queue-pressure aware: persistent backlog/pressure increases price (bounded), slack pressure lowers it.

Current payer model:

- Households pay for completed visits by default.
- Government subsidy is configurable via `healthcare_visit_subsidy_share` (default `0.0`).

Per tick reimbursement:

- `household_payment = firm.price * (1 - subsidy_share)`
- `government_payment = firm.price * subsidy_share`
- firm revenue per completed visit remains `firm.price`

## Government Involvement

Government affects healthcare through:

1. Optional subsidy funding via `healthcare_visit_subsidy_share` (default off).
2. Social multiplier effect on healing:
   - `social_scale = 1 + (social_happiness_multiplier - 1) * social_program_health_scaling`

Government does not purchase or store healthcare goods.

## Capacity and Market Structure Controls

To keep queues meaningful, healthcare firm count is intentionally sparse.

- `healthcare_households_per_firm_target` controls max healthcare providers relative to population.
- This cap is applied in both:
  - startup private-firm allocation
  - ongoing new firm creation

## Invariants and Guardrails

These should always hold:

1. No positive healthcare inventory.
2. `completed_visits <= total_capacity` each tick.
3. Queue length never negative.
4. Household health remains in `[0, 1]`.
5. Healthcare firms still pay wage costs (prevents free-cash drift).

## Operational Notes

- Healthcare is intentionally excluded from category market snapshots for goods shopping.
- Legacy healthcare-goods paths are compatibility shims and should not drive demand.
- Households are served only if they can afford their required payment at service time; otherwise they remain queued.
- There is no separate behavioral willingness-to-pay cap by default beyond cash affordability.
- Medical students cannot work non-healthcare jobs while in school.
- Residents/doctors are constrained to healthcare labor matching only.
- Sick doctors are prioritized to the front of the queue when doctor health is below 0.60.

## Tuning Cheatsheet

If queues are too long:

- increase `healthcare_capacity_per_worker_default`
- lower `healthcare_households_per_firm_target` (more providers)
- reduce care-seeking intensity via urgency/critical ranges

If healthcare is too subsidized:

- increase baseline healthcare price carefully and/or
- add a household copay split in healthcare service processing

If healthcare demand is too weak:

- increase `healthcare_visit_base_heal` only if needed
- raise preventive checkup probability
- adjust urgency/critical thresholds upward
