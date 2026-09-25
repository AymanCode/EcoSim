# Round 02 — Fable audit, concrete designs and actor negotiation

**Authorization:** Ayman requested Fable to audit the six proposals against the repository, develop vague ideas into workable mechanisms, and have the affected role LLMs exchange pros, cons and viability judgments to find compromises. This supersedes Round 01's independent-drafting restriction for this round. It does not authorize engine implementation.

**Task correction — payment-sequence closure:** Ayman clarified that resolving shared interactions was the purpose of the cross-role discussion. For the household payment-order issue, completion therefore requires one source-grounded proposed sequence, settlement owners, timing, cash/claim/quantity rules, failure cases, and replies from affected roles, followed by Fable review and disposition of its material findings. A list of dependencies or conditional support for an unspecified future resolver does not complete this issue. The coordinator may choose and disclose ordinary design assumptions within that scope; this does not authorize code or reopen the other accepted proposal directions. The focused contract and evidence live in `PAYMENT_SEQUENCE.md` and its linked role replies.

**Focused-round ownership and latest steering:** preserve the six original `*_REVIEW.md` files. For the payment closure, each role writes only its new `PAYMENT_REVIEW_<ROLE>.md`; the coordinator owns `PAYMENT_SEQUENCE.md` and audit dispositions. Ayman's later income-first question requires resolving actual ordinary wage/benefit receipt before the payment window, including counterpart debits, withholding, funding shortfalls and no later duplicate posting. Earlier late-wage PS1/PS2 statements remain authored history, superseded only by the recorded PS3 replies.

**Orchestrator audit responsibility:** Ayman explicitly asked the primary orchestrator to audit alongside Fable, not merely relay messages. The orchestrator owns a source-grounded independent judgment, challenges model fixes when insufficient, records its own findings in `ORCHESTRATOR_PAYMENT_AUDIT.md`, and disposes of material findings in the shared contract. Reviewer consensus does not replace this check.

## Deliverable and sequence

1. Fable 5.1 audits all 17 proposals and the coordinator's IR01–IR12 findings against a frozen source copy, and recommends concrete candidate mechanisms for unresolved ideas.
2. Six Sol/high role reviewers examine those candidates from the household, firm, government, bank, healthcare and housing perspectives. They may prepare independent positions while Fable works, but must incorporate its delivered candidates before finalizing their feedback. They use the common source and rules, read each other's feedback and send direct messages through the collaboration tools. The coordinator schedules turns as execution slots free up.
3. Each reviewer responds to counterpart objections, records benefits, costs, blocked cases and suggested compromises in its own Markdown file, and distinguishes conditional acceptance from disagreement. A role does not acquire write ownership of another role or shared engine code.
4. The coordinator records the exchange and any unresolved contracts. Fable receives all role feedback and the conversation record for final synthesis, checking that any claimed agreement is supported and that the resulting design still fits the whole economy.

No simulation, test, benchmark, code, script, dependency, configuration or shared-rule change is part of this round. Development-reviewer communication occurs outside the simulator and adds no per-tick actor network calls. No proposal is selected for implementation merely because reviewers agree.

## Common context

- Source baseline: HEAD/live main `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, including the working-tree changes captured for the Fable run in [its manifest](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_RUN.json).
- [Original proposal pack](../agent_round_01/README.md), including all six author documents, [assignment](../agent_round_01/ASSIGNMENT.md), [coordinator review](../agent_round_01/INTEGRATION_REVIEW.md) and [source manifest](../agent_round_01/ROUND_MANIFEST.json). Preserve those originals.
- [Rules v1.1](../../ECONOMIC_AGENT_RULES.md), [proposal template](../../ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md), [working contract](../../ECONOMIC_AGENT_WORKING_CONTRACT.md) and [readiness register](../../ECONOMIC_WORK_READINESS.md). Wiki is navigation; executable source is current behavior. Earlier model agreement is not proof.
- [Fable assignment](../../reviews/ECONOMIC_AGENT_PROPOSALS_FABLE_PROMPT.md) and its initial audit/design report when delivered. Address the report's proposal and shared-contract IDs precisely.

## Role ownership and communication

| Role | Agent name | Sole writable feedback file | Main affected counterparts |
|---|---|---|---|
| Household | `/root/round2_household` | `HOUSEHOLD_REVIEW.md` | Housing, healthcare, bank, government, firm |
| Firm | `/root/round2_firm` | `FIRM_REVIEW.md` | Household, bank, government, specialist providers |
| Government | `/root/round2_government` | `GOVERNMENT_REVIEW.md` | Healthcare, housing, bank, household, firm |
| Bank | `/root/round2_bank` | `BANK_REVIEW.md` | Household, firm, housing, healthcare, government |
| Healthcare | `/root/round2_healthcare` | `HEALTHCARE_REVIEW.md` | Household, government, bank, firm |
| Housing | `/root/round2_housing` | `HOUSING_REVIEW.md` | Household, bank, government, firm |

Agents may read any supplied proposal/review/source needed for an affected interface. Each may write only its own Markdown feedback file and may send direct messages to other existing role agents. Do not launch more agents or trigger another agent's turn yourself; the coordinator schedules follow-ups within the shared concurrency limit. If a counterpart has not been started, record the addressed question in the file for the coordinator to deliver. An idle agent can receive a message and answer when scheduled; lack of a reply is not assent.

Use stable message IDs, for example `R2-HOUSE-HH-01`. A message must name the shared-contract/proposal ID, proposed concrete rule, what changes for the recipient, the requested viability judgment, and one candidate compromise. Keep messages concise enough to answer. Log sent/received IDs and the reply in your file; distinguish actual received replies from your prediction of what a counterpart might think.

**Observed runtime qualification:** some direct deliveries to idle reviewers hit the four-slot agent limit. The coordinator therefore schedules reciprocal groups and relays the exact addressed message from its author's file; failed attempts remain labeled failed until receipt. This is scheduling outside the simulator, not a new simulation messaging system. Early Household and Housing messages both used `HOUSE` prefixes, so identify them by **sender role + review file + message ID**; later messages use `HH` and `HOUSING` to distinguish those roles.

## What every reviewer must determine

- **Benefit and burden:** what the candidate improves for the role, what it costs, and which other actors pay or lose access. A good local outcome cannot justify an unexplained loss elsewhere.
- **Feasible behavior:** decision input, state/units, trigger, settlement phase and information boundary. Expected wages or tax receipts do not become spendable cash early. Use existing live traits and states before proposing new parameters.
- **Claims and resources:** named payer/recipient/funder, actual withdrawals, one settlement owner, finite supply and the behavior under denial, partial payment, cap exhaustion, default, exit or unfinished delivery.
- **Concrete alternatives:** propose the smallest implementable specification and a simpler fallback. Recommend a candidate for an open institution and explain its alternative; do not report that recommendation as user approval or as a calibrated fact.
- **Counterexamples:** cash-poor and cash-rich households, constrained and unconstrained firms/providers, scarce bank/treasury cash and unavailable labor/units/visits. Identify when the intended transmission stops or reverses.
- **Economy-wide compatibility:** check shared treasury allocations, household payment priority, loan mirrors, wage/benefit response, price writers, capital routes and exit claims. Reuse the existing tick and market boundaries unless requesting an explicit coordinated revision.
- **Evidence and cost:** source-backed versus hypothetical statements; primary evidence supports only its studied mechanism. Estimate added state and loop complexity; no measured speed claim. Preserve the single cumulative performance target and existing mode/cadence distinctions.

## Feedback file format

Start with role, Sol/high identity, source version, round scope and review status. Keep the initial review around 900–1,500 words if possible; prioritize consequential issues and append concise exchanges rather than duplicating the entire proposal pack.

1. A short verdict and concrete candidate rules for the role's unresolved proposal IDs.
2. A table of shared-contract IDs: benefit, objection, minimal compromise, source/phase and status (`proposed`, `conditionally acceptable`, `objected`, `deferred`).
3. Outgoing questions and incoming responses with message IDs, named peers and what changed after the response.
4. Remaining disagreement or empirical/user choices; a later discriminating test and computational limit for each consequential unresolved mechanism.

A returned response must explicitly say whether the peer's proposal is viable for this role, under what constraints, and what must change. “Looks good” or merely repeating the other writer is insufficient. Agreement after a reply remains a candidate shared design until the final source/evidence audit. Never manufacture consensus; unresolved differences are a useful result.
