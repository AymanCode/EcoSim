# Economic-agent proposals — cross-role review and Fable audit

**Premise:** make EcoSim more useful for comparing economic policies by giving each change an explicit decision rule, funding source, scarce resource, settlement time and effect on the other actors. The simulator remains an abstraction with distinct households and businesses, progressive taxation and practical computational limits. Agreement between reviewers is a design recommendation, not economic validation.

**Status: design review complete; documents only.** Six Sol/high role reviewers developed all 17 original proposals, exchanged objections and conditional compromises, and reviewed Fable 5.1's first source audit. Fable then completed a second source audit of all six reviews and the actual discussion record. The coordinator checked that synthesis and recorded six qualifications for future specifications. No engine, test, configuration or dependency changes are part of this round.

**Payment-order follow-up:** [PS3: income first, then household payments](PAYMENT_SEQUENCE.md) now specifies the previously deferred C01 sequence, with six focused role replies. It settles paid ordinary wages and funded benefits before Food → rent → care → household debt → remaining purchases. Fable completed the focused audit and a correction recheck; the orchestrator independently audited source and resolved the final wording detail. This is a completed proposed contract, not implemented behavior. Earlier conditional payment comments below describe the original round and are superseded by this completed follow-up.

## Read this first

| Document | What it answers |
|---|---|
| [Independent orchestrator audit](ORCHESTRATOR_PAYMENT_AUDIT.md) | The primary agent's own findings, disagreements with Fable, source checks, paper traces and accepted limits. |
| [Payment audit dispositions](PAYMENT_AUDIT_DISPOSITIONS.md) | Fable findings, exact coordinator choices, actual correction acknowledgments and the final recheck. |
| [Focused income/payment contract](PAYMENT_SEQUENCE.md) | The exact sequence, shortage rules, owners, arithmetic cases and links to the six focused replies; resolves the C01 handoff gap. |
| [Final coordinator dispositions](FINAL_COORDINATOR_REVIEW.md) | The checked result and six qualifications a future implementation agent must carry forward; read alongside Fable's synthesis. |
| [Final Fable synthesis](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_SYNTHESIS.md) | One disposition for every proposal, concrete shared designs, actual negotiation outcomes and a proposed specification sequence. Preserved verbatim. |
| [Discussion and coordinator review](DIALOGUE_REVIEW.md) | What the roles actually told each other, what changed after an objection, which compromises are conditional, and where choices remain. |
| [First Fable audit and candidate designs](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_AUDIT.md) | Source findings FP01–FP18, shared contracts C01–C10 and a candidate card for each of the 17 ideas. Preserved verbatim; some recommendations were challenged in Round 02. |
| [Final Fable assignment](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_SYNTHESIS_PROMPT.md) | Restrictions and exact questions for the second pass, including corrections to the first report. |
| [Negotiation protocol](NEGOTIATION_PROTOCOL.md) | How role LLMs may communicate, assess counterpart costs and record consent or disagreement without editing one another's code. |
| [Original proposal pack](../agent_round_01/README.md) | The unchanged six proposals, primary economic citations and original IR01–IR12 coordinator findings. |
| [Round manifest](ROUND_MANIFEST.json) | Model identities, source/output hashes, assignments and verification record. |

## What became more concrete

| Area and original IDs | Smallest useful candidate | Effects the other roles must account for |
|---|---|---|
| **Household budgets and work** — HH-P01/02/03 | Estimate take-home pay from settled ordinary wages/tax; build one rent/debt planning view; begin net-job-gain changes as an observed-offer diagnostic. | Sellers may receive different demand; rent, food, care and debt compete for actual cash. A forecast wage or nominal deposit is not an early payment. |
| **Firm investment, entry and wages** — FIRM-P01/02/03 | Repair capital-payment accounting, gate investment on a sellable capacity gap, fund entry from a real source, and isolate the imposed benefit-linked wage floor with a scenario switch. | Founders lose usable cash; lenders bear real losses; workers face different offers. No buyers or workers can block returns even when finance is available. |
| **Tax revenue and public work** — GOV-P01/02 | Use a declared share of actual receipts within available prior-close cash; compare one destination with reserve first. A narrow Services project consumes a worker-week before adding a later slot. | Care, rent relief, rebates and projects compete for money. The project reduces current ordinary output and creates no healthcare staff or housing units. |
| **Loans and rate experiments** — BANK-P01/02/03 | Version new loan schedules, underwrite settled repayment capacity, name the actual funder and keep legacy claims distinct. Treat rate changes first as a quote experiment. | Credit rationing can prevent care, entry or construction; defaults create funder losses. Rate quotes do not yet constitute an inflation-control institution. |
| **Healthcare** — CARE-P01/02/03 | Keep illness separate from requesting or funding a visit; one full-price payment buys one qualified completed visit. Correct qualified capacity before adding training or broader triage. | Lower patient charges can increase requests without increasing available visits. Funding denial persists as unmet need and differs from waiting for a doctor; providers still owe payroll. |
| **Housing** — HOUSE-P01/02/03 | Separate contract rent from asking price, record partial rent and paired arrears, and establish a viable funded construction route before comparing delivery delays. | Tenant protection can lower provider cash and increase mortgage misses. Relief uses a separate finite public envelope; unfinished projects create no rent or invented salvage proceeds. |

The [discussion record](DIALOGUE_REVIEW.md) contains one minimum version or fallback for every original ID. Reduced versions are deliberate: a diagnostic can clarify a vague mechanism without silently choosing a new economic institution.

## Examples of actual compromise

- **Household → Bank and Housing:** the household reviewer objected to putting all goods after rent and debt because that includes essential food. Bank and Housing conditionally accepted reserving only actually matched essential Food from available cash. The cost is less cash for rent and debt; this remains a proposed payment order until goods, seller receipts and household debits settle consistently.
- **Household → Healthcare:** an unpaid episode should not disappear simply because a timer runs out. Healthcare adopted one persistent due episode outside the physical queue after funding denial, with separate counts for inability to pay and lack of clinical capacity.
- **Firm ↔ Government:** merely having an employee cannot count as completing a public project. Their candidate consumes an actual worker-week, subtracts the worker's ordinary output and pays for completed work once; delayed tax recognition still needs a shared contract.
- **Firm, Bank, Household and Government → Fable:** repairing a missing capital-payment recipient should not silently change equal-household distribution into a small miscellaneous beneficiary pool. They prefer preserving the intended recipients and treating a different distribution as a separate policy arm.
- **Housing ↔ the other roles:** relief, arrears, mortgage misses and unfinished construction are distinct claims. A landlord's losses cannot disappear into an assumed government guarantee.

These are conditional design positions. The reviewer files distinguish live messages, addressed written replies, missing acknowledgments and unselected assumptions. The coordinator did not infer unanimous approval.

## Role records

| Role | Review | Main interfaces |
|---|---|---|
| Household | [HOUSEHOLD_REVIEW.md](HOUSEHOLD_REVIEW.md) | Tax beliefs, job offers, rent, food, care and loan payments. |
| Firm | [FIRM_REVIEW.md](FIRM_REVIEW.md) | Sellable investment, entry/exit, wages, public projects and supplier payments. |
| Government | [GOVERNMENT_REVIEW.md](GOVERNMENT_REVIEW.md) | Actual receipts, competing envelopes, rebates, relief and project delivery. |
| Bank | [BANK_REVIEW.md](BANK_REVIEW.md) | Withdrawal limits, loan identity, due schedules, underwriting and losses. |
| Healthcare | [HEALTHCARE_REVIEW.md](HEALTHCARE_REVIEW.md) | Need/request/funding stages, qualified capacity and provider receipts. |
| Housing | [HOUSING_REVIEW.md](HOUSING_REVIEW.md) | Rent renewal, arrears, relief, provider debt and funded delayed supply. |

## Boundaries and evidence

Existing traits and changing resources should produce different household/business decisions; new randomness or parameters need a real behavioral purpose and stable reproducibility. Development reviewers communicate outside simulation ticks. The shared rules retain bounded indexed state and one cumulative runtime target; no performance measurement or economic outcome was produced in this round.

Source facts, proposed mechanisms and empirical evidence are separate. The original proposals retain their primary citations; Fable's first report and the additional coverage review checked representative sources. Those studies motivate mechanisms, not the proposed weekly thresholds, parameters or a real-world policy ranking. The final synthesis recommends bounded choices and exposes the unresolved ones; the coordinator's dispositions qualify details that should not be copied directly into implementation.

The first and second Fable runs use read-only source snapshots without credentials: [first run manifest](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_RUN.json) and [synthesis run manifest](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_SYNTHESIS_RUN.json). Original proposals and protected source files remain separate from this review pack.
