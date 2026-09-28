# Remediation plan: agents.py and economy.py audit

Date: 2026-09-28. Companion to `2026-09-28-agents-economy-code-audit.md` (item numbers below refer to it). Goal: fix what the audit found while changing simulation behavior as little as possible at each step, ordered from least to most risky.

## Principles

- **One finding per commit.** Never mix a behavior-preserving refactor with a behavior fix in the same commit or PR.
- **Golden gate for phases 1-3.** `regression_snapshot.py --compare` must match to `1e-6` after every commit. If it does not, the change was not behavior-preserving and gets reverted or reclassified into a later phase.
- **Test-first for leaks.** Each money leak gets a failing conservation test before the fix, so the fix is provably the thing that closed it.
- **Flag-gated for macro changes.** Phase 6 items ship behind a config flag defaulting to today's behavior. The default flips only after a side-by-side comparison, and the flag is removed one release later.
- **Branch off `main`**, not the frontend branch. Land the in-flight `economy.py` consumption refactor (or stash it) before starting; the file was still changing during the audit.
- **Delegation.** Phases 1-3 are mechanical and self-contained: hand to subagents with the golden command as the acceptance check. Phases 4-7 stay in the main session.

## Phase 0: freeze and instrument (no behavior change)

1. Land or shelve the uncommitted `economy.py` diff. Nothing else starts on a moving file.
2. Save golden snapshots and commit them under `benchmarks/results/`:
   ```bash
   python -m backend.tools.benchmarks.regression_snapshot --households 1500 --seed 42 --ticks 80 --snap-ticks 1,10,80 --save benchmarks/results/golden_1500_s42.json
   python -m backend.tools.benchmarks.regression_snapshot --households 1500 --seed 7 --ticks 300 --snap-ticks 1,80,200,300 --save benchmarks/results/golden_1500_s7_long.json
   ```
   The long run matters: several bugs only show post-warmup.
3. Record a perf baseline with `run_sim_bench.py` (households 1500 and 5000, a few seeds). Keep the JSON.
4. Add conservation tests that reproduce each leak in A1-A4, marked `xfail(strict=True)`: subsidy active with an unaffordable household; a services firm offered a long-term loan at 10% unemployment; a household whose bank medical loan is declined; a 520-tick loan's total repayment versus rate × term. Extend `total_money` in `tests_contracts/conftest.py` if it does not already include bank reserves and payment-book balances.
5. Add a per-tick money-supply diagnostic (log only, off by default) so the current leak size per tick is known before anything changes.

Exit: everything green, goldens and perf baseline committed.

## Phase 1: dead code removal (identical behavior by construction)

Items C33-C38.

- Delete never-called methods: `apply_skill_decay`, `invest_in_education`, the medical-training pipeline and its unreachable student/resident branches, the annual care-plan methods, `_stockout_*`, `_filter_to_awareness_pool`, `AgentMixin.apply_overrides`, `BankAgent.pay_deposit_interest`, `BankAgent.to_dict`. Remove their config fields and `to_dict` keys. Do **not** wire any of them in; wiring is a behavior change and belongs in Phase 6 if wanted at all.
- Delete the per-agent `HouseholdAgent` consumption/purchase/wellbeing methods that the batch path has replaced. Retarget the tests that call them (`test_contracts_deposits.py`, `test_contracts_behavior.py:499`, `tools/checks/test_household_agent.py`) at the batch functions, or delete tests that only tested dead code.
- Remove the unused payment-path `household_tax_snapshots` build (economy ~2254). The builder has no side effects.
- Remove unreachable branches: `elif category == "services"` after a `continue`, the always-true `health_snapshot is not None` checks, the duplicate `reservation_levels.size == 0` block, the `return True` after `return False`, the dead Housing branches in `_maybe_create_new_firms`.

Exit: golden exact on both snapshots. Test count may drop; that is expected and should be listed in the PR.

## Phase 2: behavior-preserving performance (golden exact)

Items D40-D50, in this order. Pure lookups first, loop fusion last, because fusion is where RNG draw order can change.

1. `firm_lookup.get()` instead of `next(f for f in housing_firms ...)` in the rental market; `len(firm.current_tenants)` instead of scanning households.
2. Awareness pool: return the cached set directly, drop the tuple signature; test emptiness with `awareness_pool.get(cat)`.
3. Cache static household trait arrays on `Economy` (preferences, frugality, drawdown rate, category weights); invalidate when the household list changes.
4. `_current_wage_bill` computed once per tick in `refresh_health_snapshot`, reused everywhere.
5. `get_economic_metrics`: one sorted cash array, derive median, percentiles, Gini and shares from it.
6. `_batch_update_wellbeing`: single gather pass instead of ~20 `np.fromiter` generators.
7. Unfilled-vacancy diagnostics: compute the remaining mask and sorted reservations once, `searchsorted` per firm.
8. Delete the per-tick healthcare inventory scan in `_reset_healthcare_tick_state`.
9. Working-capital candidate diagnostics computed once, not twice; `get_minimum_wage()` read once per loop; health snapshot dicts only when audit log is on.
10. **Loop fusion in `step()`**, only where the fused loops consume no RNG or consume it in the same household order: education + cooldown + labor plan + consumption loan; turnover reset + offer pool + offer buckets. Verify against both goldens.
11. Add `__slots__ = ()` to `AgentMixin`.

Exit: golden exact; `run_sim_bench` p50 tick time versus Phase 0 recorded in the PR.

## Phase 3: structural (mechanical extraction, golden exact)

Item D39.

- Extract each `step()` phase into its own method by cut and paste, keeping the legacy/payment branches inside each. No reordering, no merging of the two pipelines yet.
- Consolidate duplicated helpers **only where the copies are currently identical**: plan-dict stamping in `plan_production_and_labor`, the price-belief update, the dividend-crediting loop, the markup formula. Where copies disagree (debt-service sum, effective wage cost, healthcare min-wage pin), leave both and list them under Phase 5.

Exit: golden exact; `step()` under ~150 lines.

## Phase 4: accounting fixes (behavior changes only on the leaking path)

Items A1-A4, then A6-A9. Ordered by how many runs they touch. Each flips its Phase 0 `xfail` to pass, then re-baselines the goldens with a one-table summary of GDP, unemployment, Gini and money supply before and after.

1. **Medical fallback** (A3): reachable only when `self.bank is None`. Touches only households whose bank loan was declined.
2. **Long-term loan wipe** (A2): move the offer after `plan_capital_investment`, or accumulate separately. Touches only services/housing firms at 10%+ unemployment.
3. **Subsidized purchase** (A1): cap quantity by cash inside `_clear_goods_market` before revenue is booked. Touches only runs with a sector subsidy active.
4. **Investment loan partial funding** (A8): spend only the funded amount.
5. **Household ledger** (A9): one withdrawal helper that records the flow. Telemetry only.
6. **Loan interest** (A4): term-aware total, matching `payment_loans.v2_payment`. This touches every loan, so it goes last in this phase and gets its own before/after comparison.
7. Mortgage bookkeeping (A6, A7): register through `originate_loan`, fix the legacy servicing fields. Housing-only.

Exit: conservation tests pass with sink mechanics enabled, not just disabled; new goldens committed.

## Phase 5: local behavioral bugs (one subsystem each)

Items B15-B26, B29-B31. Each is verified with the agent-scenario harness (`backend/tools/checks/run_agent_scenarios.py`) and the behavior contract tests, then re-goldened.

Safe first, since they are inert at defaults or telemetry-only:
- Infrastructure multiplier cap and decay (B17). Default budget is 0, so no default-run change.
- `deficit_ratio` sign (B25). Metrics and LLM input only.
- Clear `decision_diagnostics` per tick (B22). Telemetry only.
- Constructor overrides honored (B30). Affects tests and tools, not default runs, since defaults sample the same way.

Then single-subsystem fixes:
- `or 999.0` on real zeros → direct field reads (B15). Services survival hiring.
- Weak-demand streak keyed by tick (B16). Services headcount.
- Housing branch stamps `planned_hires_count` (B21). Housing vacancies.
- Baseline liquidation floor skipped when tier is not normal (B18). Baseline Food only.
- Wage floor uses policy minimum (B19). Healthcare wages; update `test_contracts_healthcare.py:250`.
- Wage snap above NAIRU → decay at `max_wage_decrease_per_tick` (B20).
- Desperation drawdown as a max, not a replacement (B27). Households just under subsistence.
- Property tax rate constant, assessed value scales (B29). Housing firms.
- Skill growth by ticks worked; job-search cooldown starts at 1 (B31).

Exit: scenarios pass, goldens re-baselined, each PR carries a one-paragraph note of what moved.

## Phase 6: macro behavior fixes (flag-gated, one at a time)

Items B10-B14, B32. Each one shifts the whole economy, so each ships behind a config flag defaulting to current behavior, with a side-by-side run (same seeds, flag off versus on) attached to the PR. Per `CLAUDE.md`, these are economic-agent changes and go through `docs/ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md`.

Order, smallest blast radius first:
1. **Distress wage cut survives the tick** (B12). Only firms above `max_labor_share`.
2. **Synthetic switcher vacancies** (B13, B14): switcher-only pool, per-firm cap, skip firms with layoffs, don't mutate the caller's plans. Labor market only.
3. **Price beliefs keyed by category** (B11). Changes living cost, so reservation wages and job-search triggers for everyone.
4. **Tie-break noise per firm, additive friction** (B32). Seller choice for everyone.
5. **Preferences applied once** (B10). Changes every household's budget shares. Choose the fix that keeps the *effective* distribution closest to today (for example, keep the constructor bias and drop the second multiplication, then check whether preference ranges need re-tuning so the median category shares do not move).

Exit per item: flag on and off both pass contracts; comparison table reviewed; default flipped in a follow-up commit; flag removed one release later.

## Phase 7: model redesigns (separate proposals, most disruptive)

Items B23, B24, A5, C35, B28.

- Marginal tax brackets over positive wages; ordered bracket scalers.
- Bailout lever change preserves disbursed amount instead of refilling.
- New-firm seed funding from a named source (known limitation K02).
- Delete the legacy labor matcher and compare harness, or bring it to parity.
- Decide the new working-tree `_purchase_scale` semantics (housing cap, unmet-demand accounting) with whoever owns that refactor.

Each is its own proposal and its own calibration pass. None starts until Phases 0-6 are merged.

## What "not disrupting behavior" means per phase

| Phase | Golden | Expected macro change |
|---|---|---|
| 0-3 | exact, 1e-6 | none |
| 4 | re-baselined | money supply stops drifting; small local shifts |
| 5 | re-baselined | one subsystem per PR, documented |
| 6 | flag off: exact; flag on: compared | whole-economy, reviewed before default flips |
| 7 | new proposal each | model change by design |
