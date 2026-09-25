# Economic-agent proposal round 01

**Authorized 2026-09-21. Scope: research and Markdown proposals only.** Ayman asked for Sol at high reasoning, no Astra workers, and no implementation. Six role assignments cover households, firms, government, banking, healthcare and housing. Writers work independently from the same source/rules baseline; the orchestrator audits each against source before comparing dependencies and conflicts.

## What success means

Propose economical abstractions of real economic behavior that improve policy comparisons. Fidelity means representing the relevant decisions, information limits, institutions, resources and feedback—not calculating every detail of real life. Preserve the agents' basic roles, existing useful differences, progressive taxation and practical speed. Bracket redesign is not a priority.

Current code is evidence of the starting point, not proof that a mechanism is realistic. A writer may challenge a weak abstraction or request a shared-rule revision explicitly; preserving the base does not mean defending a known defect. Do not invent another personality field unless it has a decision reader and answers a clear modeling need. Meaningful uniqueness can come from existing persistent traits, resources, skills, histories, expectations and constraints. Agents with different profiles can legitimately make the same choice when constraints bind.

Economic agents pursue plausible local objectives under limited information. Development writers improve model fidelity and evidence; they do not engineer a preferred GDP, tax or ideological result. Describe any eventual economic regime through concrete ownership, control, pricing, access, investment and surplus/loss rules.

## Required inputs

- Read repository `AGENTS.md`; use `openwiki/quickstart.md`, `openwiki/where-to-change-what.md`, then the relevant linked domain page before source investigation.
- Follow [agent rules v1.1](../../ECONOMIC_AGENT_RULES.md), [proposal template](../../ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md) and [working contract](../../ECONOMIC_AGENT_WORKING_CONTRACT.md).
- Check the [readiness register](../../ECONOMIC_WORK_READINESS.md) and [rules-audit disposition](../../reviews/ECONOMIC_AGENT_RULES_REVIEW.md) to avoid reintroducing rejected claims.
- The [round manifest](ROUND_MANIFEST.json) records the current working-tree hashes. HEAD and live origin/main were both verified as `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`; the working tree also includes W01–W05 changes. Cite source symbols and lines from that working tree, not stale commit line ranges.

## Write boundaries

Each writer may create or edit only its assigned Markdown proposal. Read the repository and primary research sources as needed. Do not edit simulation code, tests, scripts, configuration, dependencies, shared rules, another writer's document, or generated wiki pages. Do not run economic simulations or benchmarks, install anything, commit, push, deploy, send messages externally, or launch further agents. Mathematical rules and worked examples in prose are useful; do not produce implementation code.

| Assignment | Output | Initial focus, subject to evidence |
|---|---|---|
| Household | `HOUSEHOLD.md` | Realistic cash/expected income, spending/saving, labor decisions and consequential differences |
| Firm | `FIRM.md` | Demand expectations, prices/wages, investment/entry/survival and heterogeneous business responses |
| Government | `GOVERNMENT.md` | Fiscal financing/revenue use, delivery constraints, credible tax/service/institution comparisons |
| Bank | `BANK.md` | Credit/deposits, contract conventions, risk/liquidity and a bounded monetary transmission path |
| Healthcare | `HEALTHCARE.md` | Patient access, payer/provider contracts, refusal/waiting and scarce workforce/capacity |
| Housing | `HOUSING.md` | Rental decisions/contracts, household/provider differences, maintenance/supply/finance lags |

## Proposal requirements

Use at most three prioritized ideas per role with stable IDs (HH-P01, FIRM-P01, GOV-P01, BANK-P01, CARE-P01, HOUSE-P01). Aim for 1,800–2,800 words per document; completeness matters more than a quota. Open with a short plain-language description of what would change and why. Follow the shared proposal template for each idea, consolidating repeated baseline information where clear.

For every idea:

1. Cite the actual current decision and settlement paths, separating source findings from hypotheses. Explain the existing mechanism before proposing another one.
2. Browse and cite relevant primary evidence (research papers, official research/statistical/institutional sources). Give the setting and finding supported, and what the source does not establish. Do not import a study's numerical estimate as a universal parameter or imply that a source-backed story validates the whole simulator.
3. Specify the smallest useful abstraction, information available at decision time, units, timing, bounded inputs, state versus traits, alternatives and omitted real-world detail. Identify a simpler fallback and why it might suffice.
4. Show at least two contrasting actor profiles and a case where constraints mute the response. Use illustrative values only when clearly labeled uncalibrated; distinguish persistent heterogeneity from transient state and shocks.
5. Trace the policy → direct flow → local decision → counterparty response → later feedback chain. Include who pays, who receives, scarce resources, financing/revenue closure, delay, adverse effects and a blocked-effect case. Label each link existing/proposed/hypothetical.
6. Map changed fields and their writers/readers, counterparties, phases, scalar/batch/cached paths, configuration/metrics/serialization and dependencies on other domains. Explicitly request any shared-rule change. Do not assume another writer's proposal will be accepted.
7. Specify acceptance examples and evidence that could falsify the mechanism, matched comparison assumptions, subgroup/observation definitions and rollback/exclusion. No tests are executed in this round.
8. Estimate time/memory scaling and new persistent state, reuse existing arrays/indexes where plausible, and state measurement needs. No claimed performance result without measurement. The 5% cumulative target is not an allowance per role.
9. Separate priority from readiness. Mark an idea ready for a bounded specification, needing evidence, or requiring a modeling choice; this round selects no implementation.

Mark unknowns precisely. Prefer a modest well-supported mechanism over a broad aspirational feature list. The coordinator will preserve original proposals and record qualifications separately, so independent agreement never substitutes for source or economic evidence.
