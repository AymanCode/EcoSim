# Shared contract for economic-agent improvements

**Status: supporting execution contract under active agent rules v1.1, updated 2026-09-21.** Start with the [binding writer rules](ECONOMIC_AGENT_RULES.md) for the current tick sequence, actor/market boundaries, simulation limits and version/change process. This document supplies implementation detail; its shared laws remain binding, while candidate economic mechanisms remain proposals. The separately authorized [W01–W05 package](ECONOMIC_CONCRETE_PACKAGE.md) has used this contract; W06–W18 remain design work subject to the [coordinator audit](reviews/ECONOMIC_DESIGN_COORDINATOR_AUDIT.md).

Read the [economic-model proposal](ECONOMIC_MODEL_PROPOSAL.md) for the premise, workstream IDs, code findings, research, and reproducible probes. The baseline audited there is `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`. Repository instructions in `AGENTS.md` and `CLAUDE.md` continue to apply.

## 1. User constraints and what they mean

| Constraint from Ayman | Operational meaning |
|---|---|
| Eventually delegate an economic agent to each coding agent | Divide responsibility by economic domain, with one integration owner for shared state and cross-domain contracts |
| Coding agents may have limited communication | Give every worker the same versioned contract, baseline, interface definitions, change ticket, and evidence requirements |
| Features should come from realistic scenarios | Name the policy question, real institution or observed behavior, causal mechanism, source, simplifying assumptions, and limits before adding a feature |
| The base of each agent should stay the same | Preserve its economic role, existing useful mechanisms, public identity, and integration contract; extend decisions incrementally instead of replacing the agent wholesale |
| Avoid substantially slowing the simulation | Treat runtime and memory as design constraints; prefer bounded, local computations and existing batch paths |
| Progressive brackets are more realistic than a flat tax | Preserve progressive taxation; bracket redesign is outside the main priorities |
| Account for downstream policy effects and behavioral changes | Trace direct payments, decisions by differently situated agents, effects on counterparties, constraints, delays and feedback; do not assume a policy benefits every actor |
| Each person and business should be individual | Preserve stable per-agent identities, traits, circumstances and experiences through shared behavior code; verify which differences affect decisions, including within each broad type |

Preserving the base does not require preserving a verified accounting error or an inert policy field. Such corrections should be narrow and documented. A change to an agent's role, core interfaces, or the economic meaning of a model run is a separate design decision, not an incidental refactor.

The coding agents are development workers. This plan does not propose calling a language model for every simulated household or firm on every tick.

## 2. Shared laws: accounting, resources, and execution

These are shared requirements for proposed changes, not claims that every existing path satisfies them or that economics has one universally correct behavioral equation. Behavioral responses, institutional choices, and parameter values remain explicit hypotheses subject to evidence and sensitivity analysis. Use the active rules' distinction between binding requirements, current behavior and known limitations.

| ID | Shared rule | Evidence a change must provide |
|---|---|---|
| L01 | Financial flows identify payer, recipient, instrument, and timing. Creation or destruction of money and external inflows require explicit entries and interpretation. | Counterparty reconciliation for purchases, wages, taxes, transfers, deposits, loans, interest, defaults, ownership transfers, and liquidation as affected |
| L02 | Real resources remain scarce. Payment, production, inventory, capacity, and delivery are separate quantities. | No sale or treatment exceeds resolved supply; projects use inputs and deliver capacity through a declared rule; money alone does not instantaneously create workers or equipment |
| L03 | Units and timing are shared. Distinguish currency stocks, currency per tick, real quantities, rates per period, nominal values, and price-adjusted values. | New fields state units, observation time, update phase, and any conversion to annual rates; current configured tick length is respected |
| L04 | Each mutable balance or lifecycle transition has an owning settlement path. Plans and realized outcomes are distinct. | A write map shows which method changes each field and how the other side is settled; no duplicated taxes, wages, loan payments, dividends, or service delivery |
| L05 | Agent and counterparty identities agree. | Household employment matches firm rosters; borrower debt matches lender claims under the chosen valuation convention; ownership, rental, and care records reconcile |
| L06 | Information and randomness are declared. Agents cannot use future outcomes or hidden information without an explicit model assumption. | Decision inputs are documented; runs record seeds and shock specifications; observation/logging does not consume behavioral randomness or alter outcomes |
| L07 | Comparisons change declared policies or institutions with otherwise common capabilities and outcome definitions. | The same units, accounting, information access, and evaluation definitions apply; any intentional capability difference is part of the named intervention |
| L08 | Scarcity and loss remain visible. Defaults, waiting lists, unemployment, insolvency, shortages, and negative net worth are not silently erased to keep a chart attractive. | Each guard identifies whether it protects valid software state or represents an economic institution, who pays, and what happens on exhaustion |
| L09 | Claims are proportional to evidence. A realistic story is not a calibrated magnitude, and repeatability is not external validation. | Mechanism source, chosen simplification, parameter justification, uncertainty, and unsupported claims are separately recorded |
| L10 | Runtime is part of acceptance. New realism must justify its computation and storage costs. | Algorithmic cost estimate and relevant before/after benchmark; aggregate cost is assessed after integration |
| L11 | Policy transmission is explicit and may have competing effects. | A source-backed map names immediate payer/recipient, changed decisions, affected counterparties, delays, constraints and competing effects; separate mechanism checks from whole-economy policy comparisons |
| L12 | Individuality is persistent, consequential and reproducible under the declared model version. | Name traits and actual readers; distinguish fixed traits from changing state, beliefs and shocks; preserve pre-policy profiles across arms; test both unconstrained response differences and legitimate convergence under binding constraints |

L01 allows legitimate deposit-money creation; it does not impose conservation of total money in every institutional setup. L02 does not prohibit technological progress; it requires a specified process. L08 does not require every firm to fail under a loss: a public service obligation can justify support when that support is financed and recorded. These distinctions follow the accounting, fiscal, production, and validation discussion and sources in proposal items P01, P02, P05, P06, and P10.

## 3. Common interface specification before parallel edits

The coordinator should publish the following for the selected work package before workers change coupled behavior:

- A versioned list of state fields: owner, type, units, initial value, allowable range, update phase, and serialization/persistence treatment.
- Decision inputs and outputs: what each agent observes, what it may propose, what can be rejected, and which resolver settles it.
- Transaction definitions: counterparties, amount/quantity, instrument, recognition time, and treatment of cancellation, default, and rounding.
- Tick ordering and information availability: when observations become available, when decisions lock, and when realized outcomes update expectations.
- Compatibility rules: existing public names and defaults retained where feasible; intentional behavior or schema changes explicitly listed; baseline evidence versioned.
- Validation and performance fixtures: shared scenarios, seeds, configurations, metric definitions, and the relevant engine or application execution mode.

This is a design checklist, not a requirement to introduce a heavyweight event bus or store every microtransaction. Start with the narrow typed records/helpers needed by the chosen change. Keep hot-path data compact and batchable; optional diagnostic detail can remain outside the default run.

Current planning is not universally free of side effects, and several balances settle in different phases of `Economy.step()`. The integration owner must map the actual call paths before changing them. Do not infer purity from a method name or independently reorder a tick in one worker's patch. [C-S1]

## 4. Proposed delegation boundaries

Start with independent proposal documents and orchestrator review using the [proposal template and conflict register](ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md). The boundaries below describe eventual implementation ownership; they do not require workers to begin coding before their ideas and shared assumptions have been checked together.

| Owner | Preserve | Candidate initial scope | Required coordination |
|---|---|---|---|
| Household worker | Household identity, employment/search, needs, consumption, health, deposits/debt, and existing heterogeneity | P04: consistent expected disposable income and liquid-resource decisions | Firm wages, government taxes/transfers, bank obligations, and the vectorized consumption/application paths |
| Firm worker | Firm identity, sector role, production, pricing, hiring, capital, and depreciation | Selected P01/P04/P05 fixes for entry financing or decisions | Household owners/workers, bank loans, government support, and entry/exit settlement |
| Government worker | Tax collection, transfers, services, policy application, and progressive taxation | P02: financing and observable budget rules | Treasury/bank claims, household/firm payments, policy schema, fiscal guards, and public providers |
| Banking worker | Deposits, lending, repayment/default tracking, and existing consumer interfaces | Selected P01/P07 accounting or a staged monetary transmission mechanism | Every borrower/depositor and government financial operations; no independent change to the meaning of money |
| Healthcare worker, when selected | Requests, queues, provider capacity, training, and health consequences | P08: payer/coverage contracts with capacity constraints | Household payment, government/insurer financing, provider revenue, medical credit, and workforce |
| Housing worker, when selected | Rental allocation, occupancy, repairs, expansion, and mortgages | Selected X03 improvements for a defined housing comparison | Firm assets, household rent, bank financing, construction inputs, and property taxes |
| Integration owner | `Economy.step()`, shared settlement, market resolution, configuration/public contracts, metrics, and reproducibility | P01/P03/P10 foundations and integration of selected worker changes | All domains; owns contract revisions, merge order, end-to-end reconciliation, and cumulative runtime |

Do not start all of these together. For the first implementation package, select a small, connected change whose shared contracts are understood. The ten proposal workstreams are a roadmap, not ten independent coding jobs.

Household, firm, bank, and government classes all live in `backend/agents.py`; many effective behaviors live in `backend/economy.py`, including batch paths that can bypass scalar agent methods. An assignment to a class is not complete ownership of its behavior. [C-S1] [C-S2]

Use isolated worktrees or isolated patches from the same baseline for concurrent implementation. Assign exact symbols and integration points; workers must not simultaneously edit the same shared working-tree file. A worker needing a shared schema or another owner's behavior produces a contract-change request. The coordinator resolves it and publishes a revised contract before dependent work proceeds. Shared-file extraction is optional and should not become a prerequisite rewrite without evidence that it pays for itself.

Before dispatching a selected package, fill the field-level writer map required by L04. Reserve shared orchestration and settlement symbols, metric definitions, serialization contracts, and shared configuration for the integration owner; workers provide interface/call-site requests for changes outside their assignment. Register RNG streams by stable purpose and entity/tick identity as appropriate. Document policy-dependent keys and global RNG use; do not assume arbitrary seed offsets alone prevent collisions or ensure suitable scenario pairing.

## 5. Lightweight implementation and performance policy

Prefer additions that reuse existing observations, shared market arrays, indexes, caches, and batch settlement. Avoid a full household-by-firm scan per decision, unbounded search, per-agent network calls, unnecessary per-tick object allocation, or a full historical ledger in memory when a compact current balance and optional evidence stream suffice. Cache invalidation and update cadence must preserve the declared economics.

The existing performance mode changes consumption-plan reuse and wellbeing update cadence. It is a different execution configuration, not automatic proof of equivalent economic results. Hold it fixed within a comparison and label it in evidence. Do not make a new feature appear cheap by quietly evaluating it less often. [C-S1] [C-S3]

**Default engineering threshold under rules v1.1:** target no more than a 5% increase in median and p95 engine tick time for the selected integrated package on a matched workload, and report memory growth. This operationalizes Ayman's speed constraint; it is not a number he supplied or a measured guarantee. Establish measurement variability first. If that threshold is too noisy or unsuitable, record a revised threshold with its reason before interpreting results. A feature with a material cost should be simplified, made an explicit optional module, or presented as a cost/benefit decision. Do not silently give every worker a separate 5% allowance; the cost is cumulative.

For an implemented change that touches per-tick work:

1. Save the baseline commit, complete configuration, hardware/runtime versions, execution mode, active population/firm counts, phase labels, and workload before edits.
2. Run the existing engine harness on baseline and candidate under the same conditions, without concurrent coding agents or other heavy benchmarks competing for resources. Include a representative developed private economy, not just warmup.
3. Record repeated timing distributions and inspect both end-to-end time and cost at comparable active agent counts. A policy that changes the number of surviving firms can change workload as well as algorithm cost.
4. Use the relevant behavior and reconciliation checks alongside timing. Preserve exact baseline semantics for a refactor; document intentional divergences for an economic correction instead of forcing the old wrong result.
5. Benchmark the integrated package. Run the real application harness only when making application-level performance claims or changing that boundary.

The existing engine CLI is a starting point, not a benchmark result for this proposal:

```bash
python3 -m backend.tools.benchmarks.run_sim_bench --households 1000,10000 --ticks 80 --warmup-ticks 10 --seeds 42,43,44 --output-root /tmp/ecosim-agent-benchmarks
```

The harness writes a run directory containing its output. Capture any material configuration not included by the harness in the change's manifest. Adjust run length when the reported phases show the workload has not reached the regime needed for the claim. Existing snapshot comparison covers selected state, not every internal field. [C-S3] [C-S4]

## 6. Required change ticket and handoff

Every worker receives a filled ticket before implementation. Empty fields below are placeholders, not permission to invent requirements.

```yaml
ticket_id: null
proposal_items: []
baseline_commit: null
source_snapshot_and_hashes: null
agent_rules_version: "1.1"
applicable_rule_and_limitation_ids: []
shared_contract_version: null
economic_agent_owner: null
policy_question: null
real_world_mechanism: null
sources: []
assumptions_and_simplifications: []
preserved_base_behavior: []
intended_behavior_changes: []
owned_files_and_symbols: []
read_dependencies: []
shared_interfaces_consumed: []
shared_interfaces_proposed: []
scalar_and_batch_paths_touched: []
performance_mode_behavior: null
config_changes_and_defaults: []
rng_streams_and_keys: []
metrics_and_schema_changes: []
consumers_checked: []
baseline_equivalence_or_intended_divergence: null
new_state_fields_with_units_and_owner: []
transaction_and_resource_effects: []
randomness_and_information_rules: []
acceptance_cases: []
policy_transmission_and_competing_effects: []
existing_and_proposed_behavior_readers: []
subgroup_definitions_and_observation_times: []
trait_persistence_and_paired_initialization: null
performance_workload_and_budget: null
out_of_scope: []
handoff_commit_or_patch: null
verification_artifacts: []
unresolved_contract_requests: []
wiki_refresh_status: null
```

The worker's final handoff must explain the before/after mechanism, exact files and symbols changed, which shared laws were exercised, tests and observed results, runtime evidence where needed, intentional baseline differences, and unresolved concerns. Include one traceable economic example spanning the affected counterparties. A list of added fields is not sufficient.

The integration owner checks both sides of each changed contract, then performs a small composed experiment. Independent worker test passes do not prove that a household, firm, government, and bank agree on one transaction or on one tick's timing.

Coding agents improve the simulator's mechanisms and evidence; simulated actors pursue declared local objectives within their information and resource limits. A shared instruction for every simulated actor to raise GDP or make a policy successful would introduce a new cooperation assumption. Sampled household/firm reviewers may propose missing behavior or counterexamples, but their narrative is not evidence that a mechanism is realistic or correctly implemented. A live LLM actor trial, if later selected, is a separate experiment requiring bounded actions, engine settlement, recorded observations/responses, replay, fallback, and provider-cost measurements. See the [behavior and delegation review](reviews/ECONOMIC_BEHAVIOR_AND_DELEGATION_REVIEW.md).

## 7. First audit and subsequent use

The requested first external-model review is Claude Fable 5.1 auditing the proposal and this contract against the repository. Its task is to challenge incorrect source claims, missing mechanisms, priorities, scope, and integration risks. Keep its findings separate from the proposal, record the model and input versions, and reconcile accepted corrections against source evidence.

**Current review status: complete.** Read the [Fable 5.1 report](reviews/ECONOMIC_MODEL_FABLE_AUDIT.md) together with the [coordinator verification and disposition](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md). The [audit brief](reviews/ECONOMIC_MODEL_FABLE_AUDIT_PROMPT.md) and [run manifest](reviews/ECONOMIC_MODEL_FABLE_AUDIT_RUN.json) record the assignment, model, and input versions. Authentication was renewed after the initial failed attempt. The successful review inspected the repository without executing code or editing files; the coordinator separately ran five additional probes and incorporated the ticket/coordination clarifications above.

The subsequent W01–W05 package is complete. The current proposal-writing cycle uses the [active rules](ECONOMIC_AGENT_RULES.md), their [Fable audit](reviews/ECONOMIC_AGENT_RULES_FABLE_AUDIT.md) and [coordinator disposition](reviews/ECONOMIC_AGENT_RULES_REVIEW.md). Future mechanisms still require a bounded selected package; establishing the rules does not launch implementation.

## Source anchors

The economic rationale and primary research are cataloged in the [model proposal](ECONOMIC_MODEL_PROPOSAL.md#9-source-catalog). These current local references support the implementation and performance boundaries in this contract. The [source hash and symbol index](reviews/evidence/ECONOMIC_AGENT_RULES_SOURCE.json) identifies the supplied working-tree version. C-S labels are source references; R-IDs belong to the binding agent rules.

- [C-S1: `Economy.step()` and surrounding current lifecycle][C-S1].
- [C-S2: current household batch consumption planning][C-S2].
- [C-S3: current engine benchmark implementation and CLI][C-S3].
- [C-S4: current regression-snapshot implementation][C-S4].
- [Current focused test and performance navigation](../openwiki/engineering/testing-performance.md), which must be checked against current source before use.

[C-S1]: ../backend/economy.py
[C-S2]: ../backend/economy.py
[C-S3]: ../backend/tools/benchmarks/run_sim_bench.py
[C-S4]: ../backend/tools/benchmarks/regression_snapshot.py
