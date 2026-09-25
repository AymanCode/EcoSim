# Economic-agent proposals — round 01

**Completed: six independent Sol/high proposal writers, 17 ideas, coordinator source review and a separate Sol/high primary-evidence check. No simulation code was written or changed in this round.** Source identity and authorship are recorded in [ROUND_MANIFEST.json](ROUND_MANIFEST.json).

## Premise

Make EcoSim more useful for comparing policies by improving how people, firms and public institutions respond to each other. Model the real-world decisions and constraints that matter for the question, using affordable abstractions. A policy must affect budgets, choices, counterparties and scarce resources through a stated mechanism; it should not receive an unexplained productivity or welfare bonus.

Individuals should differ through persistent preferences and capabilities **and** changing cash, debt, health, jobs, ownership and history. Those differences should affect choices where feasible; people facing the same binding constraint can still make the same decision. Preserve the base actor roles, progressive taxation and a lightweight simulation. These AI workers are development proposal writers, not live LLMs inside each simulated person.

## What each writer proposes

| Actor | Proposed changes | Why they matter |
|---|---|---|
| [Households](HOUSEHOLD.md) | HH-P01 expected take-home income; HH-P02 rent/debt commitments in budgets; HH-P03 compare jobs by expected net gain. | Taxes and unavoidable bills should affect decisions; expected future wages must not become spendable cash early. |
| [Firms](FIRM.md) | FIRM-P01 invest against expected sellable demand; FIRM-P02 explicit entry funding, ownership and exit claims; FIRM-P03 vacancy-driven wages without the automatic benefit multiplier. | Credit or tax changes should propagate through customers, financing, workers and owners rather than mechanical bonuses. |
| [Government](GOVERNMENT.md) | GOV-P01 declare how revenue is retained or spent; GOV-P02 fund a named project that takes time and resources to deliver. | A tax comparison depends on what revenue finances; paying for a service does not instantly create useful capacity. |
| [Bank](BANK.md) | BANK-P01 coherent loan terms and funder claims; BANK-P02 repayment-capacity and withdrawal-liquidity checks; BANK-P03 a bounded new-loan/deposit rate experiment. | Rates, repayment burdens, liquidity and defaults need consistent contracts. The current bank is a prefunded abstraction. |
| [Healthcare](HEALTHCARE.md) | CARE-P01 requests respond to patient charges; CARE-P02 explicit patient/public payer contracts; CARE-P03 qualified capacity and a defined priority rule. | Free access can reduce financial barriers while still facing funding and workforce limits. Requests, denials, waiting and completed care are different outcomes. |
| [Housing](HOUSING.md) | HOUSE-P01 contract rent and renewal; HOUSE-P02 partial payment and bounded arrears; HOUSE-P03 delay between financed construction and usable units. | Rent policy affects incumbent and new tenants differently; a temporary cash shortfall and a physical housing shortage need different mechanisms. |

Each document gives source paths, realistic contrasting profiles, policy transmission, other actors affected, resource/accounting limits, proposed checks, expected computational cost and primary citations. Mechanisms and illustrative values are proposals, not calibrated findings.

## What is concrete and what still needs design

**Concrete source problems to specify first:** conflicting housing price writes, a duplicated mortgage cost signal, an early capital-payment counter reset, inconsistent loan-rate conventions, entry/exit claim ownership and healthcare's nominal capacity fallback. The [coordinator review](INTEGRATION_REVIEW.md#source-corrections-and-qualifications) explains the evidence and limits. The sampled firm R&D trait is also less active than its proposal initially claims.

**Bounded designs with shared decisions:** expected net-income planning, obligations and deposit access, demand-aware investment, fiscal allocation, lease renewal and delayed housing. They need exact timing and ownership of payments, not a larger agent architecture.

**More open institutional or behavioral choices:** healthcare funding and exhaustion, medical demand strength and triage, rent grace/relief rules, labor responses, delivered public projects and the meaning of a rate intervention. Full monetary systems, medical training and economic-regime comparisons remain later work.

Read [INTEGRATION_REVIEW.md](INTEGRATION_REVIEW.md) before treating a role proposal as an implementation brief. It preserves the originals, corrects overstatements, lists cross-agent conflicts and recommends an order. It does **not** approve all 17 ideas for implementation.

## Shared boundaries

- [Assignment](ASSIGNMENT.md): document-only scope, realism, heterogeneity, independent authorship and role ownership.
- [Agent rules v1.1](../../ECONOMIC_AGENT_RULES.md): current sequence, markets, accounting, information and simulation limits. Current defects can be challenged explicitly.
- [Proposal template](../../ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md): auditable mechanism and evidence requirements.
- [Coordinator review](INTEGRATION_REVIEW.md): individual dispositions, corrections, integration contracts and next design sequence.
- [Manifest](ROUND_MANIFEST.json): source and output hashes, model requests and final scope checks.

Runtime effects are unmeasured: the existing cumulative 5% target is a future measurement gate, not a guarantee and not an allowance for every proposal separately. No experiments, benchmarks or engine tests were run for this document round.
