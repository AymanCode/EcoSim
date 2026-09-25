# Independent economic-agent proposals and orchestrator review

**Status: active proposal workflow under agent rules v1.1, 2026-09-21.** Reviewers first write independent proposals; an orchestrator checks their evidence and compatibility before selecting any implementation. This document does not launch coding agents or authorize the proposed economic changes.

Start with the [binding agent rules](ECONOMIC_AGENT_RULES.md), including the current sequence, market boundaries and simulation limits. Use the [shared contract](ECONOMIC_AGENT_WORKING_CONTRACT.md) and [current behavior/design review](reviews/ECONOMIC_BEHAVIOR_AND_DELEGATION_REVIEW.md) for supporting detail. An assignment may cover an economic role or a sampled individual case. A sampled-case reviewer still proposes a general mechanism or a diagnostic, not special privileges for that one ID.

## Assignment given to every reviewer

Provide the same source snapshot/version, rules version, policy question, configuration and evidence definitions. Include working-tree source hashes when the commit does not contain every relevant change. Name the assigned role/case, accessible observations, owned scope, and excluded changes. Reviewers read the relevant source and write a document; they do not edit the simulation in this stage. Independent means they do not need to see each other's conclusions while drafting, not that they can ignore shared rules or counterparties.

Limit the initial proposal to three prioritized changes. Preserve each author's original document. Use a stable ID such as `HH-P01`, `FIRM-P01`, or `BANK-P01`, and map it to the existing W06–W18 queue when applicable.

## Proposal template

```markdown
# <proposal ID>: <concrete mechanism or diagnostic>

Status: proposed / revised
Author and model:
Source commit, working-tree snapshot and relevant file hashes:
Agent rules version: 1.1
Applicable binding rules (R-IDs), market rules (M-IDs) and limitations (K-IDs):
Assigned economic role or sampled case:
Related W-IDs:

## 1. Problem and evidence
Policy question:
Current behavior, with path + symbol:
Observed failure, limitation, or missing behavior:
Evidence type: executed result / source finding / hypothesis / model choice
Relevant primary economic source and what it does not establish:

## 2. Proposed behavior
Before/after example with units:
Decision inputs and information available at that time:
Exact proposed rule, bounds, default and timing:
Persistent traits versus changing state and shocks:
Existing behavior preserved:
Alternative and reason for the recommendation:

## 3. Effects on the rest of the economy
Immediate payer, recipient, resource and constraint:
Fiscal/financing closure: what adjusts when revenue or spending changes?
Other affected households, firms, bank or government:
Next decisions and delayed feedback:
Possible adverse/competing effect:
Case where the effect is blocked or absent:
Existing versus proposed versus hypothetical links:
Subgroups and when their membership is defined:

## 4. Shared interfaces and dependencies
Fields read and written; owner, units and update phase:
Cash, debt, ownership or resource counterparties:
Scalar, batch and performance-mode paths:
Configuration, metrics, serialization and other consumers:
Dependency on another proposal or unresolved assumption:
Requested shared-contract change:

| Rule ID | Compliance evidence or requested revision | Affected roles/phases | Dependency/status |
|---|---|---|---|
| <R/M/K ID> | <source path + symbol and proposed treatment> | <owners and timing> | <preserved / requested / unresolved> |

## 5. Verification and cost
Minimal example that distinguishes correct from incorrect behavior:
Accounting/resource checks:
Trait-response check and binding-constraint case:
Replay and baseline-compatibility check:
Execution mode, refresh cadence and intervention boundary in each arm:
Metric definitions, subgroup populations and exact observation phases:
Expected runtime/memory cost and how it will be measured:
Rollback or exclusion from the package:

## 6. Recommendation and limits
Priority and readiness, stated separately:
Smallest useful deliverable:
Unresolved choices:
Claims this proposal cannot support:
```

An unmeasured quantity stays labeled unmeasured. A narrative that sounds realistic is a reason to investigate, not proof. Improving the model is judged by coherent mechanisms and evidence; preferred GDP, tax or regime outcomes are not acceptance criteria.

## Orchestrator process

1. **Review each document independently against the repository and active rules version.** Verify its source snapshot, rule-compliance evidence, actual readers and settlement paths, evidence strength, preserved roles, information limits and feasibility. Record a disposition before comparing it with the other documents, so agreement between authors does not replace evidence.
2. **Normalize the proposals into one dependency and conflict register.** Match differently named fields and assumptions that refer to the same balance or mechanism. Inspect all affected counterparties, including those that received no reviewer.
3. **Resolve conflicts explicitly.** Return a precise revision request to the relevant authors, or select a documented common rule. Version any revision to the active shared rules before dependent implementation. Do not silently blend incompatible models. Retain a record of the rejected alternative and reason when it materially affects the comparison.
4. **Publish one integrated plan.** It names accepted slices, unresolved choices, shared field ownership and timing, dependencies, implementation order, combined acceptance cases and the cumulative performance budget. Compatible ideas can still be deferred because they are unnecessary or expensive.
5. **Implement only a selected package.** After its interface contract is fixed, use bounded tickets and isolated patches/worktrees. The integration owner checks composed behavior and both sides of transactions; the document review alone cannot prove integration works.

The orchestrator's decision vocabulary is **accept as specified**, **revise**, **needs evidence**, **defer**, or **reject**, with a reason and next owner. “Accept” means ready for selection, not already implemented or empirically validated.

## Conflict register

| Proposal IDs | Shared field/mechanism | Conflict or dependency | Evidence | Resolution/status | Owner |
|---|---|---|---|---|---|
| `<IDs>` | `<state/rule>` | `<specific disagreement>` | `<source/probe>` | `<decision>` | `<owner>` |

Check more than file overlap:

- **Accounting:** two agents debit the same tax, disagree on a loan's funder, or count an overdraft twice.
- **Timing/information:** a household plans around a rebate before the government has announced or funded it; a firm uses a wage that only settles later.
- **Behavior:** two changes separately compensate for the same tax or price signal, so integration doubles the response.
- **Institutions/resources:** one design promises unlimited care while another keeps a binding provider budget or capacity limit without a rationing rule.
- **Measurement/causality:** one design changes a metric or cohort definition between arms, or bundles payer and pricing changes while claiming a payer-only effect.
- **Performance:** individually small overheads exceed the package budget when combined.

For the first trial, a few role reviewers or sampled cases are enough. The orchestrator should evaluate each independently, then compare proposals together. No separate source implementation is needed for every simulated person, and no continuous conversation between all reviewers is required.
