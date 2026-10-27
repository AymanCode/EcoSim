# SERVICES-01: implementation contract

Status: selected by the owner on 2026-10-26; implementation and evidence recorded separately below. Baseline: d71485e7276cb2bf988eee6ff8ae9ecada3b73be. Rules: v1.15; shared working contract L01-L12. Proposal context: the October 2026 business audit, with three selected priorities. This document records the existing authorization rather than supplying its own approval.

## Selected behavior

1. Services has a persistent desired after-tax markup, initialized lazily once from its current sampled/intended markup. Existing tax gross-up, utilization surge and 20% smoothing form quotes; quote-implied markup is measured state and never becomes the target. With cost $10, target .5 and tax .2, the high-utilization target is $16.25, not a recurring 5% markup increase. Stabilization uses the Services cost basis for measured markup; the current market cost floor retains its own owner and phase.
2. Both bank-funded Services expansion routes require full installed staffing plus five fully staffed observations with at least 95% sell-through and at least two positive unmet-demand observations in the latest five. These are noisy existing sales/order signals, not private customer motives. Current eligibility is rechecked at origination. Existing credit/funding, distress, cooldown and sequence-specific gates remain. Installed slots reset the space-shortage evidence and permit filling the newly financed slots.
3. Private Services normally starts by targeting its installed slots. A demand-driven or emergency planned reduction retains the lower intended staffing target. Profits recovering at unchanged weak sales do not restore it. Three consecutive observations of at least 90% sell-through, with the current target actually staffed, permit one trial target increase; the counter restarts. Missing employees from failed recruitment may be replaced up to the existing target without restarting business expansion. Normal five-observation weak-loss and wage-floor cut gates, baseline staffing regime, and emergency liquidity rules remain. Synthetic switcher vacancies cannot bypass the target.

Recovery/expansion thresholds reuse existing utilization concepts. The owner explicitly chose three strong-sales weeks for the first hiring-recovery experiment. These are model settings, not estimates of real salon behavior. No hard price cap or desired aggregate outcome is added. Installation updates retained staffing intent and restarts recovery evidence, including skipping the next planning observation because its production predates installation. The optional public installation route shares that lifecycle; its funding and project rules remain unchanged.

## Filled change ticket

```yaml
ticket_id: SERVICES-01
proposal_items: [stable_service_markup, staffed_space_expansion, patient_staffing_recovery]
baseline_commit: d71485e7276cb2bf988eee6ff8ae9ecada3b73be
source_snapshot_and_hashes: external services-decision-probes.json records baseline owning-file hashes
agent_rules_version: '1.15'
applicable_rule_and_limitation_ids: [R01, R03, R04, R05, R06, R07, R08, R09, R10, R11, R12, M01, M02, M05, M06, K06, K08]
shared_contract_version: SERVICES-01/v1
economic_agent_owner: Services firm, with Economy coordinating labor and funding
policy_question: Do local Services choices respect price intent, usable space, and persistent sales evidence?
real_world_mechanism: Cost-markup pricing and adjustment under uncertain demand with costly workforce/capacity changes
sources: [Bank of England working paper 395 (2010), Bloom/Bond/Van Reenen NBER w12383 (abstract only), current source and controlled probes]
assumptions_and_simplifications: [existing noisy unmet-order measure retained, no new customer observations, owner-selected three-observation recovery experiment]
preserved_base_behavior: [customer choice and quantities, initial slot filling, Food/Housing/Healthcare logic, 20-percent price smoothing, progressive taxes, funded settlement, existing loan products]
intended_behavior_changes: [stable desired markup, staffed sustained space gate on both loans, retained staffing target and patient recovery]
owned_files_and_symbols: [backend/agents.py FirmAgent Services state/planning, backend/economy.py stabilization/labor/capacity loans, backend/payment_government.py installed-slot activation, focused tests and documentation]
read_dependencies: [backend/payment_sectors.py market quotes, backend/payment_loans.py underwriting, backend/config.py existing defaults]
shared_interfaces_consumed: [production and price plan dictionaries, actual employee rosters, bank claims, settled sales]
shared_interfaces_proposed: [Services pricing cost basis in price plan, bounded firm target/evidence state, pure common space eligibility]
scalar_and_batch_paths_touched: [firm planners, fast labor synthetic vacancies, sequence-specific completed goods sales]
performance_mode_behavior: no cadence or customer plan-cache change
config_changes_and_defaults: no new policy lever or sequence default; recovery uses three strong observations
rng_streams_and_keys: no new draws or altered initialization sampling
metrics_and_schema_changes: additive firm state serialization only; no warehouse/API schema change
consumers_checked: [firm to_dict, price stabilizer, market floor, labor matchers, both space-loan routes, funded payroll]
baseline_equivalence_or_intended_divergence: economic divergence is intentional; accounting and unaffected actors retain their contracts
new_state_fields_with_units_and_owner: [service_target_markup_after_tax optional dimensionless target, service_staffing_target optional worker count, service_staffing_recovery_streak bounded observation count, service_staffing_recovery_counted_tick planning age, service_capacity_observation_tick planning age]
transaction_and_resource_effects: existing loan funders/claims/recipients unchanged; additional slots require the physical and sales gates; jobs still require matching
randomness_and_information_rules: use existing own state and sales/unmet aggregates only; observer diagnostics do not become customer knowledge
acceptance_cases: [fixed-input price stability and cost/tax/utilization response, stabilized markup basis, both named sequences, both loan origins require staffed sustained demand, profitable cut does not refill, three strong observations permit one hire, synthetic vacancy respects target, cash emergency and roster/payroll invariants]
policy_transmission_and_competing_effects: [prices affect access/receipts, staffing persistence affects churn/jobs/demand, expansion patience can reduce idle debt or delay supply]
existing_and_proposed_behavior_readers: existing planners and resolvers consume the new bounded state; no household reader added
subgroup_definitions_and_observation_times: compare pre-change firm identities and initial traits; completed ticks; entry/exit reported separately
trait_persistence_and_paired_initialization: preserve sampled profiles and caller-managed Python/NumPy RNG state across arms
performance_workload_and_budget: repeated matched normal-mode 1k/10k runs including developed private firms; integrated five-percent working budget with uncertainty disclosed
out_of_scope: [new customer tracking, quality/R&D changes, baseline retirement, Food strategy, loan-size redesign, binding price-control redesign, UI, PR/push/merge]
handoff_commit_or_patch: isolated codex/services-decision-coherence working-tree patch
verification_artifacts: recorded in the final evidence report
unresolved_contract_requests: none for the selected behavior; broader model questions remain out of scope
wiki_refresh_status: use approved refresh tooling when available; otherwise explicitly report due
```

## Accounting, evidence and limits

These rules affect desired prices and employment/capacity decisions, not the frozen wages already earned. Sales receipts remain funded household/clearing transfers, loans remain lender cash and borrower claims, and original capital-recipient abstractions remain visible. Less expansion can preserve lender funds and firm liquidity while delaying jobs and output. Staffing patience can reduce churn while slowing employment recovery. Nominal GDP must be read alongside service quantities/access, household wellbeing, jobs, actual payroll, firm cash, arrears and debt.

[Greenslade and Parker (2010)](https://www.bankofengland.co.uk/working-paper/2010/new-insights-into-price-setting-behaviour-in-the-uk) supports cost-based and demand-responsive pricing with sector variation. [Bloom, Bond and Van Reenen](https://www.nber.org/papers/w12383) supports the relevance of uncertainty and adjustment costs; only its indexed abstract was accessible during the audit. Neither source calibrates these thresholds or validates the simulator. Exact executed proofs and measured computation cost must be reported separately from these mechanisms.
