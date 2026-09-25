# Fable 5.1 audit: active rules for independent economic-agent writers

Ayman requested these common rules before starting a team of economic-agent proposal writers, and then explicitly requested an audit by Fable once the document was ready. Audit the completed document against the supplied repository snapshot. This is a read-only review; do not implement changes, start workers, run commands, publish anything or edit files.

## User intent

EcoSim should support auditable policy comparisons: progressive taxation, healthcare financing/access, inflation mechanisms and eventually explicit ownership/governance arrangements. Preserve basic economic-agent roles, meaningful individual differences and practical speed. Tax-bracket redesign is not a main task. Later independent writers will each produce a proposal; an orchestrator checks each against source and then resolves conflicts before selecting implementation. The current task establishes their shared rules, current sequence and market/actor boundaries, including the constraints of a computer simulation. This is not authorization for live LLM control of all economic actors.

## Source and scope

The snapshot is a copy of the current working tree over commit `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, verified equal to live origin/main by the coordinator. It includes the completed W01–W05 code. It is not a clean release represented by the commit alone. The supplied audit manifest records copied-file SHA-256 hashes. Git history, credentials and environment files are excluded. You have only Read, Grep and Glob within the supplied snapshot; no need to independently fetch GitHub.

Follow the repository's wiki-first navigation: `openwiki/quickstart.md`, relevant entries in `openwiki/where-to-change-what.md`, then the relevant lifecycle/market/institution/policy pages. Current source is authoritative. Read:

1. `docs/ECONOMIC_AGENT_RULES.md` — the main review target, active v1.0.
2. `docs/ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md` and `docs/ECONOMIC_AGENT_WORKING_CONTRACT.md` — check integration and contradictory instructions.
3. `docs/reviews/evidence/ECONOMIC_AGENT_RULES_SOURCE.json` — source identity and owning symbols.
4. Relevant owning source in `backend/economy.py`, `backend/agents.py`, `backend/config.py`, `backend/server.py`, `backend/policy_schema.py` and the large-economy factory.

Other included docs/tests are supporting evidence, not authority over current code. The previous Fable reports are historical proposals; do not assume their conclusions were accepted. The rules' current source claims need your own inspection.

## Audit questions

- Does the major-phase table match actual execution, including conditional operations, side effects during planning, loan/wage ordering, price updates and metric/dividend timing?
- Are household, firm, government, bank, healthcare and housing roles/interactions described accurately enough for independent writers to avoid incompatible assumptions?
- Are market allocation, information availability, units, payment ownership, counterparties and resource limits explicit? Would any purported invariant actually contradict the current engine or freeze a known defect as a permanent law?
- Do the individuality and policy-transmission rules require consequential mechanisms without forcing unique choices, ideal foresight or a preferred policy outcome?
- Are comparison rules, fiscal assumptions, source citations and evidence labels adequate? Flag material overclaims and omitted qualifications.
- Are computational constraints and the cumulative performance target practical and clear about what is chosen, measured and unknown?
- Can writers propose improvements within bounded ownership? Does the orchestrator have a clear way to resolve genuine shared changes without turning every routine choice into a user-approval gate?
- Do the linked template, working contract and scoped AGENTS/CLAUDE pointers consistently implement the rules?

## Output

Return one Markdown audit, ideally 1,200–2,200 words and shorter if there are few findings:

1. Verdict: usable as-is, usable after specified corrections, or not yet usable.
2. Actionable findings, each with a stable `AR-01` style ID, severity, exact document section/claim, repository path + symbol/line evidence, why it matters, and a concrete correction. Distinguish source errors, conflicting requirements, missing rules and optional improvements. Do not invent findings to fill a quota.
3. Coverage table stating the main contracts/paths actually checked and remaining limits. A source inspection is not a passed simulation experiment.
4. Optional refinements, kept separate from blockers.

Do not rewrite the whole document. Do not propose a whole new economic model. Be critical and specific: a statement already carefully qualified should not be reported as unqualified. Cite relevant source locally; no web research is needed for this repository audit. Return the audit as your final response so the coordinator can preserve it verbatim, verify every finding and apply justified corrections.
