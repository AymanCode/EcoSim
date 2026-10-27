# SERVICES-02: repayment-aware planned pricing

Owner authorization: "Try a small fix to account for repayment and check how the simulation works" (2026-10-26). The existing SERVICES-01 working patch is the comparison baseline, not the old recursive-markup main behavior. Rules v1.16 precedes the dependent code change.

The change is limited to `FirmAgent._service_pricing_costs`: use existing scheduled bank installments plus direct Treasury installments, the same two mirrors as `_debt_service_per_tick`, rather than infrastructure installments alone. Each total is capped at its corresponding nonnegative outstanding balance, because the named Treasury collector can retain an old schedule after payoff. Bank installments already contain infrastructure dues. Keep the current wage, throughput, utilization interpolation, target markup, tax gross-up and smoothing logic. No new field, trait, policy, history or random draw is introduced. Planned quotes and their measured-markup denominator share this input. Existing quotes remain plans; customer choice, funded settlement and the existing transaction-floor owner remain unchanged. Repayment is not inserted into accounting/tax profit as a new operating expense. The aggregate bank cap is not a new per-claim amortization engine; existing settlement remains authoritative.

Example: payroll $100 over ten units, bank installments $50 (including $20 infrastructure), Treasury installment $30. The planning cash base is $18/unit, not $12 from infrastructure alone and not $20 from adding infrastructure twice. With an unchanged .5 desired markup, .2 pricing-tax rate and .85 sell-through, the target is $29.25. A current $15 quote moves to $17.85 under the existing 20% smoother; this does not promise customers will buy or that the bank will approve another loan. Under low utilization the existing interpolation can still quote below full cash coverage.

Filled ticket:

```yaml
ticket_id: SERVICES-02
proposal_items: [services_existing_repayment_in_planned_price]
baseline_commit: d71485e7276cb2bf988eee6ff8ae9ecada3b73be
source_snapshot_and_hashes: SERVICES-01 candidate hashes recorded in SERVICES_DECISION_VALIDATION and external sources/P1E1H1
agent_rules_version: '1.16'
applicable_rule_and_limitation_ids: [R01, R03, R04, R05, R06, R07, R08, R09, R10, R11, R12, M01, M05, M06, K06]
shared_contract_version: SERVICES-02/v1
economic_agent_owner: Services FirmAgent
policy_question: Can planned prices account for existing repayment obligations without recursive markup or new information?
real_world_mechanism: Cash budgeting informs cost-based asking prices under uncertain demand
sources: [SERVICES_COMPONENT_RESULTS, Bank of England working paper 395 cited in SERVICES-01]
assumptions_and_simplifications: [existing scheduled-payment mirrors, existing throughput denominator and utilization interpolation, no guarantee of repayment or profitable sales]
preserved_base_behavior: [bank coverage rule, customer choice, transaction floor, 20-percent smoothing, progressive taxes, accounting profit, actual debt settlement, hiring patience and full-space gates]
intended_behavior_changes: [Services planned quote cash base includes all existing scheduled installments once]
owned_files_and_symbols: [backend/agents.py FirmAgent._service_pricing_costs, focused tests, rules and evidence docs]
read_dependencies: [FirmAgent._debt_service_per_tick, Economy._apply_price_stabilization_to_plan, payment_loans debt mirrors and underwriting]
shared_interfaces_consumed: [bank_loan_payment_per_tick, loan_payment_per_tick, production and price plans]
shared_interfaces_proposed: []
scalar_and_batch_paths_touched: [shared Services pricing helper, measured quote-markup readers]
performance_mode_behavior: no cadence or caching changes
config_changes_and_defaults: []
rng_streams_and_keys: no new draws
metrics_and_schema_changes: []
consumers_checked: [plan_pricing, _markup_for_price, price stabilization, effective market price, funded settlement]
baseline_equivalence_or_intended_divergence: no-debt and infrastructure-only consistent states retain behavior; other existing loan installments change intended price
new_state_fields_with_units_and_owner: []
transaction_and_resource_effects: endogenous prices and receipts may change; existing payers, lenders, claims, payment order and resources remain
randomness_and_information_rules: own existing obligations only
acceptance_cases: [direct Treasury debt, bank debt, mixed infrastructure mirror counted once, zero debt, repayment payoff response, no quote-side cash or profit debit, both named sequences, transaction-floor institution unchanged]
policy_transmission_and_competing_effects: [higher requested prices may fund obligations or reduce purchases; credit approval and future jobs remain conditional]
existing_and_proposed_behavior_readers: existing FirmAgent planners and Economy stabilizer
subgroup_definitions_and_observation_times: matched starting towns; completed weeks; Services and household outcomes
trait_persistence_and_paired_initialization: exact shared initial state and RNG fingerprints across arms
performance_workload_and_budget: bounded scalar addition; normal-mode matched 1k three-seed and 10k seed42 panels, with timing uncertainty labeled; no unmeasured 5-percent pass claim
out_of_scope: [customer redesign, new price floor, lending relaxation, loan size or term, other sectors, new patience setting, PR/push/merge]
handoff_commit_or_patch: local SERVICES-01 plus this follow-up working patch
verification_artifacts: SERVICES_REPAYMENT_RESULTS and external services-repayment-experiment
unresolved_contract_requests: none for the selected small change
wiki_refresh_status: approved tooling when available; otherwise report due
```

Validation compares the full current Services package with and without this change: normal `income_first` first, `income_late` second; three seeds at 1,000 households and one seed at 10,000, 80 weekly ticks, warmup 10. Report real service units, jobs, household happiness/health, prices, actual wages, cash, debt/arrears and nominal GDP. Recheck source/profile hashes, funded settlement and cash residuals. Existing baseline endpoints must reproduce the prior panel before effects are interpreted. This is an experiment, not a promise to restore an earlier GDP value.
