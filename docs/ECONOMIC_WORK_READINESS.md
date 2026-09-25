# Economic-model work: what is concrete and what needs design

**Prepared: 2026-09-21; implementation follow-through 2026-09-22.** W01–W05 remain implemented. The selected minimum versions of the later agent proposals now have [actual implementations and acceptance evidence](reviews/ECONOMIC_IMPLEMENTATION_REVIEW.md). The tables below preserve the original readiness map; they are not a current claim that every later item is unimplemented or that the complete long-term W06–W18 goals are fulfilled.

**Implementation follow-up:** Sol medium implemented the shared payment and agent modules with independent Codex review and Fable source audits. The [execution record](ECONOMIC_IMPLEMENTATION_EXECUTION.md) distinguishes actual behavior, diagnostic-only experiments, chosen constants and unfinished institution designs. Full inflation control, regime presets, comprehensive national accounts and external calibration remain future work.

This divides the [economic-model proposal](ECONOMIC_MODEL_PROPOSAL.md) into actionable pieces using the [independent Fable review](reviews/ECONOMIC_MODEL_FABLE_AUDIT.md) and [verified follow-up](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md). The original audit used commit `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, checked against GitHub main. The working tree now includes the [concrete package](ECONOMIC_CONCRETE_PACKAGE.md). [Fable’s design proposal](reviews/ECONOMIC_DESIGN_FABLE_PROPOSALS.md) and the [coordinator audit](reviews/ECONOMIC_DESIGN_COORDINATOR_AUDIT.md#3-revised-readiness-after-this-audit) provide the current next slices; some of Fable’s claimed-ready designs still need corrections.

**Latest follow-up:** [Fable's corrected-source revision and coordinator disposition](reviews/ECONOMIC_BEHAVIOR_AND_DELEGATION_REVIEW.md) add transmission chains, behavioral individuality and proposal-first orchestration. Read the revised report with that disposition; its new claims and trait formulas are not automatically implementation-ready. Future reviewers must use the [active agent rules v1.2](ECONOMIC_AGENT_RULES.md) and [independent proposal template and conflict register](ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md). Establishing these common rules does not change the readiness of W06–W18.

The distinction is **how clearly the correct behavior is specified**. A confirmed problem can still have several reasonable remedies. Readiness is separate from priority, implementation effort, and evidence of a real-world effect.

| Group | Meaning | Next action |
|---|---|---|
| A — Concrete, bounded work | The desired correction or evidence artifact is clear enough to write a small implementation ticket | Specify touched fields/call sites, implement the selected item, and verify it |
| B — Known issue, needs a focused specification or check | The problem or objective is clear, but a rule, definition, or technical feasibility question remains | Produce a short decision note or diagnostic, then move the resolved slice to A |
| C — Economic model design | There are materially different plausible systems to represent; the feature is not adequately defined yet | Define the policy question, institutions, assumptions, scenarios, evidence, and cost before implementation |

One domain can appear in several groups. Fixing medical-loan repayment is A; choosing healthcare financing institutions is C. The original P01–P10 workstreams are too broad to assign one readiness label each.

## A. Completed concrete work

All five items below are complete; the “Done when” column retains their acceptance requirements. See the package record for tests, actual comparison exports, browser verification and performance evidence. These items do not need a new theory of household behavior or a choice between economic systems. They still require the normal integration and validation work described in the [shared contract](ECONOMIC_AGENT_WORKING_CONTRACT.md).

| ID | Item | Why it is concrete | Done when |
|---|---|---|---|
| W01 | Repair repayment accounting for government-funded bank loans | E06 shows a payment reducing borrower cash without crediting either government or bank; the funding source is already identified. P01; F02. | Each payment credits its contractual recipient, reduces the correct debt/receivable, and reconciles relevant telemetry. Any interest or servicing-fee treatment is explicit. Ordinary bank-funded loans continue to reconcile. |
| W02 | Give bank medical loans one authoritative repayment path | E07 shows bank collection followed by an additional treasury payment and mismatched loan balances. P01/P08; F02. | A registered bank medical loan has one servicing path and consistent borrower/lender balances. Partial payment, payoff, and default cases are covered; the separate no-bank fallback is handled deliberately. |
| W03 | Record the conditions of each comparison | Seed, effective configuration, policy timing, stabilizer settings, execution mode, model version, and metric definitions are identifiable technical facts. P10; F05/F11. | Paired runs have a readable, versioned manifest with actual applied settings and failures. Existing forecasting manifests remain compatible; recording evidence does not alter outcomes. |
| W04 | Make current control capabilities explicit | E01 and source inspection establish that the stored inflation target has no current engine response. P07; F09. | The relevant control description and run evidence accurately identify its inactive status. Realized inflation remains a separate measured quantity. This item does not implement monetary policy. |
| W05 | Prepare the shared ownership map and performance baseline | Existing writers, settlement phases, consumers, and runtimes can be inspected/measured. This is preparation for safe work, not a new economic institution. F10–F12. | The selected package has named field/symbol owners, counterparties, affected consumers, and a measured baseline with configuration, workload phases, and variability. Runtime limits are recorded as explicit decisions. |

Evidence for W01/W02 is in [E06/E07 and their results](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md#additional-checks-performed-by-codex). Evidence for W04 is in the [original probe register](ECONOMIC_MODEL_PROPOSAL.md#7-reproduced-evidence-register). W03 and W05 are concrete engineering deliverables, not claims that an existing component is entirely absent.

## B. Known issues needing a focused specification or check

These should become small investigations or decision notes, not open-ended rewrites. Some require a modeling choice; others can be resolved by inspecting or testing the implementation.

| ID | Item | What is established | What must be settled before the implementation slice moves to A |
|---|---|---|---|
| W06 | Firm entry, ownership, exit, and remaining money-flow discrepancies | Entrant cash can lack a funding counterparty; initial baseline firms have household owners; new entrants do not receive owners in the inspected constructor. Other source/sink paths are recorded in F02/F03. P01/P09. | Trace and measure the affected flows. Specify permitted funding sources, ownership claims, treatment of initial real assets, and resolution of residual cash/debts at exit. A missing counterparty is concrete; choosing owner funding versus a loan or grant is a model choice. |
| W07 | Poverty, household resources, prices, and real output | Current inequality omits deposits; the poverty threshold changes with the benefit preset; price/output measures have interpretation limits. E04/E05; P03; F06. | Define each new measure, units, timing, price basket, and compatibility plan. Distinguish liquid resources from comprehensive net worth; decide asset valuation and debt coverage. Choose a poverty standard independently of benefit eligibility. |
| W08 | Household response to taxes and firm decision inputs | Main consumption planning uses gross wages; later settlement and liquidity transmit taxes. Scalar/batch paths and execution modes differ. P04; F07. | Specify expected take-home income and when policy changes affect expectations. Decide what stays fixed in saving, search, pricing, and investment rules. Previous taxes paid are a candidate input, not a complete specification. |
| W09 | Separate economic support from agent decision rules | Firm stabilizer settings change production, wages, and planned prices; government settings change several fiscal operations. E10; P05; F04. | Inventory each switch. Define exactly which support institution each replacement toggle controls and which private decision capabilities remain common across compared scenarios. |
| W10 | Match the pre-policy state and external disturbances | Seeded runs and keyed randomness exist; complete intervention branching has not been established. P10; F05. | Verify identical pre-policy replay or safe state copying, including configuration and RNG state. Audit policy-sensitive keys and changing sample populations. Specify which disturbances are shared and which endogenous outcomes may diverge. |
| W11 | A small public-investment delivery model | Spending currently changes productivity through direct formulas and routes payments through the miscellaneous pool. P06; F08. | Specify the minimal project/output, recipient, delay, capacity/return rule, maintenance if relevant, and plausible parameter ranges. Determine whether a small aggregate abstraction answers the chosen question. |
| W12 | Financing and use of revenue in the first tax experiment | The current fiscal closure is asymmetric and includes surplus recycling, cash-limited investment, and transfers that can make treasury cash negative. E02/E08; P02; F01. | State what adjusts when tax revenue changes: services, rebates, borrowing, or another declared rule. Define the financing-gap stock and counterparties. Select the closures to compare; do not equate repeated negative cash observations with newly issued debt. |

The [follow-up disposition table](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md#disposition-of-fables-findings) records which observations are verified and which proposed remedies remain judgments. Economic research supporting the original concerns is in the [source catalog](ECONOMIC_MODEL_PROPOSAL.md#9-source-catalog).

## C. Features requiring economic model design

These are substantial goals, not ready implementation tickets. Their design can proceed alongside A, and a well-defined small part can move into B without waiting for the entire long-term model.

| ID | Feature | Main questions to flesh out | Required design output |
|---|---|---|---|
| W13 | Healthcare systems | Who is covered, who pays, how are providers paid, what services are covered, and what happens when capacity or budgets run out? How does insurance differ from a subsidy? | Two explicit payer/provider scenarios with funding, coverage, waiting/affordability rules, outcomes, and preserved training/capacity mechanics. P08. |
| W14 | Monetary policy, banking institutions, and public financing | Is inflation imposed as a stress test or generated by shocks and responses? Who creates money, what constrains lending/government finance, and how do rates affect decisions? | A coherent monetary/financial setup, balance-sheet conventions, policy transmission path, shock types, units, and evaluation scenarios. P01/P02/P07. |
| W15 | Capital goods and production networks | Which missing input relationships matter for the chosen comparison? Are new firms/markets necessary, or would W11's aggregate abstraction suffice? | A minimal resource and supplier network with prices, capacity, delivery, depreciation, accounting, and computational cost. P06. |
| W16 | Capitalism, socialism, communism, and governance variants | Who owns assets, controls enterprises, allocates investment, sets prices/access, bears losses, and receives surplus? Which governance characteristics change information or implementation? | Named presets that expand into explicit institutions and transition rules, without automatic success/failure bonuses. P09. |
| W17 | External calibration and validation | Which real economy or empirical mechanisms are represented, over what horizon, using which data? Which observations are reserved for independent validation? | A stated domain of validity, data/source plan, parameter strategy, validation targets, sensitivity plan, and limits on claims. P10. |
| W18 | Later demographics, trade, housing/land, labor, and environmental extensions | Which specific comparison is materially blocked by each missing mechanism? What existing behavior should be preserved? | A separate scoped design only when the question calls for it. These are the optional X01–X05 extensions, not prerequisites for every experiment. |

## Original sequence and next work

1. **Completed: W05 map/baseline and W01/W02 loan corrections.** One integration owner should handle their shared settlement code. These are the clearest behavior corrections supported by executable evidence.
2. **Completed: W03 comparison evidence and W04 capability labeling.** Their deliverables help prevent misleading interpretation while larger features are still being designed.
3. **Flesh out W06, W07, W10, and W12 for the first tax comparison.** These settle money-flow boundaries, outcome definitions, pairing, and fiscal assumptions. Define W08 before claiming a richer behavioral tax response. Record current stabilizer settings and resolve W09 before attributing a toggle comparison to support alone.
4. **Choose the next institution comparison and develop its C item.** Healthcare, inflation, and ownership/governance do not all need to be implemented together. W11/W15 depend on whether the chosen question needs investment delivery or input scarcity.

W17 becomes a requirement for the external claims it is meant to support. It does not prevent clearly labeled, controlled experiments inside the synthetic model from being useful earlier.

## How an item becomes ready

For a B or C slice to move into A, save a short note stating:

- The exact question and resulting behavior, with one before/after example.
- The rule or institution selected, alternatives considered, supporting sources, and explicit assumptions.
- Inputs, outputs, state owners, units, timing, counterparties, affected consumers, and dependencies.
- Acceptance cases that test correctness without demanding a preferred ideological outcome.
- Expected computational cost and the validation/benchmark needed to assess it.

Use the [existing change-ticket template](ECONOMIC_AGENT_WORKING_CONTRACT.md#6-required-change-ticket-and-handoff). Record whether the remaining choice needs Ayman's modeling preference or can be resolved through source inspection and a focused technical check. Do not dispatch overlapping implementation workers before their common interfaces are settled.

## Scope retained from the conversation

Preserve each agent's base and existing useful mechanisms. Keep additions grounded in realistic scenarios, keep runtime costs visible, and retain progressive taxation. Tax-bracket redesign is not a main priority. Ayman authorized Group A in this session; its five items are complete. W06–W18 remain proposed work, with the audited narrower slices described above.
