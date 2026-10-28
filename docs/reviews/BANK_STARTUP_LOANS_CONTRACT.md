# BANK-STARTUP-01: selected bank startup experiment

Status: selected and authorized by Ayman, 2026-10-27; implementation and local 1,000-household evidence complete; selected for PR publication. Coordinator: Terra/ultra. Baseline `b233cd74fc570ab0b38665fcc94187f6ca37ef27`, frozen zip SHA256 `464295AF64E0768478D38119F6C2557B77F89F24762236F216CBBAA8DAECC9AB`. Agent rules v1.18; R01?R12, M05/M06, K02/K03 and working-contract L01?L12 apply. Role: private firms, bank and integration; no W-ticket implied.

Integration after PR #68: the common rules version is **v1.21**, retaining its research and payroll revisions v1.18-v1.20. The v1.18 above identifies this experiment's original standalone contract; its frozen economic evidence is unchanged. See the [combined integration receipt](PR68_69_INTEGRATION.md) for current validation and the ID-policy regression.

## 1. Problem and evidence

Question: what happens when the bank, rather than Treasury or founder alone, can finance an eligible private entrant under a bounded startup product? Source finding: `Economy._activate_queued_firms` uses `_issue_firm_loan` whose named path applies historical-revenue and settled-cashflow tests and falls back to Treasury. `_maybe_create_new_firms` routes its named Treasury tier to a direct pooled claim, otherwise founder equity; `payment_loans.originate_v2` owns bank claims and funder debit. A startup cannot supply its own operating history. This is a modeling limitation, not measured performance or evidence of a calibrated risk threshold.

[Robb and Robinson, The Capital Structure Decisions of New Firms, NBER working paper 16272](https://www.nber.org/papers/w16272) documents external debt including bank finance among new firms. It does not calibrate these amounts, rates, terms, default risk or aggregate effects. The product is an explicit bounded simulator institution.

## 2. Selected priorities and behavior

1. **Startup product:** named sequences only, one bank-funded v2 `startup` claim per entitled pre-operating private firm, principal finite and positive up to 30,000, integer term 1?208 ticks. Replace only ordinary historical revenue and prior operating cashflow/coverage gates. Keep score >= 0.25, cooldown, wage arrears, can-lend, full lendable reserves, finite and quote controls. Quote uses existing risk-adjusted annual rate and new-loan shift, with no extra premium or random draw. Treasury funding is rejected. The existing v2 ledger refuses principal at or below its 1e-6 currency tolerance; all selected routes are much larger, so the exact mathematical positive interval is not fully supported. Age zero, no operating history, no existing registered, direct Treasury or mortgage debt, no baseline/public fallback/PublicWorks, and an Economy-granted transient entitlement are required. Persistent successful-origination marker survives payoff; denial does not set it. Bank amortizing interest differs from the old direct Treasury pooled total due.
2. **Atomic entry:** queued activation keeps its 10,000 opening endowment and requests 25,000/208; refusal leaves the firm active without Treasury fallback. Recurring entry retains tier and sector draws, thresholds and amounts: former Treasury tier 30,000/156; former bank tier 20,000/156; bootstrap 5,000 founder equity. Both credit tiers are bank-only; on refusal/no bank select existing founder and reserves, requested amount then 5,000 fallback. When founder-equity fallback is required, no eligible founder means no entrant; an approved bank-funded entrant keeps the existing ownerless behavior (owner clarification, 2026-10-27). Prepare nonfinancial candidate before committing funding, credit principal once, publish only on funded success, and leave no claim, reserve/owner debit, lookup/list entry or consumed ID on failure. Retain trait and quote draw order where possible. Enabled named entries use a monotonic private-ID counter reconciled with active/queued maxima and incremented only on commit; other allocation remains unchanged, so global entity ID reuse outside this route remains a limitation.
3. **Bounded comparison:** freeze sources and common evaluator, pair initial profiles and RNG, and run the predeclared 1,000-household panel in normal mode, LLM off, standard stabilizers. Report both benefit denominators, business/bank/household effects and accounting, not a calibrated welfare or 5% performance acceptance claim. Owner explicitly overrides the general 10,000-household performance gate for this experiment.

Example: a qualifying candidate requests 20,000 and a bank with sufficient free reserves transfers exactly 20,000 to its cash, registers one 20,000 principal claim, and later receives principal and amortizing interest through existing v2 servicing. Insufficient reserves deny the entire request. Founder equity, if available, is an actual household-to-firm transfer, not created money. No automatic refinancing or retry is added.

## 3. Transmission and tradeoffs

Bank reserves fund entrant cash; the firm can plan, hire and supply under existing physical and labor rules. Repayment returns principal and interest to the bank; defaults reduce its claim without a second cash payment. Treasury avoids prior startup outflows, while bank capacity for other credit can fall, entrants can fail, and founder resources can decline on fallback. Credit does not create real supply, jobs or household wellbeing by itself. No bank, eligible entrant, score, reserves, or founder can stop the chain. Observed effects after entry are hypotheses until the paired panel. Initial nonworking and low-cash subgroup IDs are frozen before the first step; flows and state transitions are reported separately.

## 4. Rule and field map

| Rule | Prior -> selected behavior; reason/source | Roles, phases, fields | Accounting, compatibility, cost and verification |
|---|---|---|---|
| M05/M06; R03?R06 | Ordinary named entry lacks settled history and may use Treasury -> entitled startup bypasses only history/coverage, bank only. `payment_loans.originate_v2`, `Economy._issue_firm_loan` | Economy grants/clears entitlement at entry; bank checks score/cooldown/arrears/liquidity and registers claim | One bank debit, one firm credit, one claim; v2 repayment/default; existing other products and named no-government-borrowing unchanged; O(1) checks plus existing indexes; transaction/refusal tests |
| R07/R12 | Active maximum can recycle IDs -> monotonic committed private IDs on enabled named entry | Economy owns counter, reconciles active/queued maximum; firm owns boolean entitlement (transient, false) and successful marker (persistent, false) | No ID consumed on refusal; other entity allocation unchanged; bounded counter plus two booleans per firm; exit/reentry and stale key regression |
| R09?R11 | Existing snapshots do not prove paired pre-step initialization -> common frozen evaluator captures full config, profiles and RNG immediately after setup | Read-only wrappers observe original settlement exactly once; no additional decisions or RNG | 24 primary cases plus old replay and candidate flag-off control; 60?80 and 104?140 inclusive; <=2 workers; descriptive runtime/memory, no 5% or 10k claim |
| R08/R10 | Source supports external debt mechanism, not parameters -> retain bounded simulator choice and competing effects | Firm, household founder, bank, Treasury; current entry phase and v2 servicing | Distinguish credit, GDP, fiscal transfers and opening endowments; compare subgroup needs/wellbeing, prices and physical output; no causal real-world claim |

`payment_bank_startup_loans_enabled`: boolean launch-only, experiment default true; copied into session config and immutable payment snapshot, validated and locked as existing payment options. False restores old named entry/activation; legacy sequence ignores flag. Entitlement is granted only around legitimate entry attempt and cleared in `finally`; marker is written only on successful claim. No schema/database persistence outside existing snapshot mechanisms. New checks must not expose future observations or add new random draws. Normal and performance modes retain their existing cadence; experiments use normal mode.

## 5. Filled working-contract ticket

```yaml
ticket_id: BANK-STARTUP-01
proposal_items: [startup product, atomic private entry, bounded comparative verification]
baseline_commit: b233cd74fc570ab0b38665fcc94187f6ca37ef27
source_snapshot_and_hashes: baseline-b233cd7.zip SHA256 464295AF64E0768478D38119F6C2557B77F89F24762236F216CBBAA8DAECC9AB; candidate manifest after checks
agent_rules_version: '1.18'
applicable_rule_and_limitation_ids: [R01-R12, M05, M06, K02, K03, L01-L12]
shared_contract_version: BANK-STARTUP-01
economic_agent_owner: firm-bank-integration
policy_question: effects of bounded bank-only private startup finance
real_world_mechanism: external bank debt finances some new firms
sources: [https://www.nber.org/papers/w16272]
assumptions_and_simplifications: [bounded uncalibrated product, existing score and quote, no future income forecast]
preserved_base_behavior: [other products, sectors, physical capacity, labor, benefit and fiscal policy, legacy sequence]
intended_behavior_changes: [named startup bank product and funded entry routing]
owned_files_and_symbols: [backend/payment_loans.py, backend/economy.py, backend/agents.py, backend/config.py, backend/server.py, focused tests, evidence harness and review docs]
read_dependencies: [PaymentBook, bank reserves and claim servicing, founder reserves, factory queues, setup snapshot]
shared_interfaces_consumed: [originate_v2, v2 servicing, firm lookup, session payment config]
shared_interfaces_proposed: [startup entitlement and successful marker, private ID counter, launch flag]
scalar_and_batch_paths_touched: [private entry, queued activation, v2 underwriting]
performance_mode_behavior: existing cadence unchanged
config_changes_and_defaults: [payment_bank_startup_loans_enabled true on experiment branch; false rollback]
rng_streams_and_keys: [existing global RNG and ID-seeded tier RNG; no new draws; monotonic IDs may alter subsequent entrant draws]
metrics_and_schema_changes: [existing payment snapshot parameter; offline diagnostic evidence only]
consumers_checked: [server setup validation and lock, payment snapshot, claims and firm mirrors]
baseline_equivalence_or_intended_divergence: flag-off named and legacy replay; enabled funding and interest intentionally diverge
new_state_fields_with_units_and_owner: [firm transient entitlement bool, firm successful marker bool, economy next private ID integer, config launch bool]
transaction_and_resource_effects: [bank reserves to firm cash and registered principal, or founder cash to firm cash; repayment and writeoff existing owners]
randomness_and_information_rules: no extra draw or future knowledge
acceptance_cases: [entitlement and gates, atomic denial and fallback, exact repayment and writeoff, identity reuse, setup isolation, rollback]
policy_transmission_and_competing_effects: bank liquidity and firm entry; opportunity cost to credit, founder resources and defaults
existing_and_proposed_behavior_readers: [Economy entry, BankAgent scores, v2 claims and due index, payment snapshot]
subgroup_definitions_and_observation_times: initial nonworking and low cash before first step; weeks 60-80 and 104-140 inclusive
trait_persistence_and_paired_initialization: compare full pre-step profiles and RNG; IDs frozen before outcomes
performance_workload_and_budget: 1000 households, 140 ticks, 10 warmup, normal, max two workers; descriptive only
out_of_scope: [benefits changes, labor, food floors, Misc payout, public debt, publicworks, baseline endowments, taxes, other credit, UI, 10000-household runs]
handoff_commit_or_patch: uncommitted patch and hash
verification_artifacts: external artifacts root with logs, source manifests, weekly rows and summaries
unresolved_contract_requests: none selected; material extensions return to parent
wiki_refresh_status: due; manual GitHub Actions prohibited for this task
```

## 6. Verification, rollback and limits

Test full origination and lender/borrower pair, partial installments, interest and default/writeoff; explicit refusal gates and all excluded actors; single-use after payoff; queued activation and recurring founder/bootstrap atomicity; stale score/cooldown identity; setup validation and session locking. Run named-sequence existing payment and server suites, integration smoke, Ruff and diff checks before freezing. Preserve complete logs and diagnose baseline-versus-candidate residuals; a focused pass alone is not global conservation. Flag off restores named old behavior; `legacy` ignores flag. No change to the parked benefits Compare question is authorized. The report must disclose initialization limits, each seed and both windows, accounting tolerances, any failed checks and the pending wiki refresh.
