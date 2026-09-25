# Claude Fable 5.1 audit brief

## Authorized task

Audit `docs/ECONOMIC_MODEL_PROPOSAL.md` and `docs/ECONOMIC_AGENT_WORKING_CONTRACT.md` using this EcoSim repository as the primary source of truth. This is an independent critical review requested by Ayman. Do not implement changes or edit files. Return the complete review as Markdown; the calling agent will save it as a separate report.

## User intent and constraints

EcoSim is intended to compare policies and economic institutions: lower/higher progressive taxation, healthcare free at the point of use versus private payment/insurance, inflation and policy responses, and eventually different ownership, allocation, and governance arrangements associated with capitalism, socialism, and communism. The purpose is an inspectable comparison of mechanisms, outcomes, winners/losers, costs, and assumptions.

Ayman specifically says progressive tax brackets are more realistic than a flat tax and **bracket redesign must not be a main priority**. He eventually wants separate coding agents responsible for improving different economic agents. Those workers need shared laws and interfaces because they may communicate only sparsely. Additions must be grounded in realistic scenarios, preserve each economic agent's base rather than replace it wholesale, and avoid making the simulation much slower. The contract's 5% performance figure is a proposed engineering threshold, not a number specified by Ayman. Implementation has not been started by this task.

## Repository and access

Repository root: `/Users/aymanislam/EcoSim_v_2/EcoSim`.

The coordinator verified local HEAD, origin/main, and GitHub main as `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46` on 2026-09-21. The cited economic-engine files matched that commit. Unrelated user edits exist in documentation, tests, and packaging. The two proposal documents are new, uncommitted review artifacts. Preserve all working-tree changes.

Follow repository instructions: read `AGENTS.md` and `CLAUDE.md`, then start with `openwiki/quickstart.md`, `openwiki/where-to-change-what.md`, and relevant linked pages. Treat generated wiki text as navigation, not proof. Verify important claims against actual source, including both the agent classes and the effective batch/settlement paths in `Economy`.

Your available tools are read-only repository inspection tools. Do not request secrets, inspect credential files, contact unrelated services, delegate further, or write anything. You can inspect the included reproduction code and its owning source; do not claim you executed a probe if you only read it. The coordinator has rerun the exact snippet and reproduced E01–E05, but that is supplied evidence rather than your independent execution. Research URLs in the proposal were consulted by the coordinator; assess how claims use them, and label source-content checks you cannot independently perform with the available tools.

## What to audit

1. **Claim accuracy.** Check the serious current-code claims and whether citations actually support them. In particular: startup funding, government deficits/debt, cash-only inequality and benefit-linked poverty, consumption/labor timing, stabilizer switches, investment/public spending, inflation target usage, healthcare coverage/capacity, and the experiment wrapper. Look for counterevidence and mechanisms the proposal understates or omits.
2. **Policy-comparison validity.** Are the highest priorities really the most consequential for the stated comparisons? Which gaps bias conclusions, which are deliberate abstractions, and which are optional realism with little payoff? Avoid requiring a full national-economy model before any bounded comparison is useful.
3. **Base preservation and speed.** Could the proposal be achieved through incremental, bounded changes? Identify likely expensive additions, unnecessary architecture, hidden coupling, and ambiguous instructions. Check scalar and vectorized paths, normal/performance mode, units, ownership, transaction timing, configuration, metrics, persistence, and forecasting consumers as relevant.
4. **Parallel-work contract.** Would workers assigned to households, firms, government, and banking integrate successfully with limited communication? Identify missing shared contracts, contradiction risks, shared-file conflicts, dependency sequencing, and gaps in the ticket/handoff. Separate universal accounting/resource constraints from empirically uncertain behavioral assumptions.
5. **Practical next package.** Recommend the smallest coherent first implementation package, its dependencies, acceptance evidence, performance checks, and explicit deferrals. Respect the progressive-tax correction. Do not favor or guarantee a political or economic system's success.

## Required review format

Lead with a candid overall assessment. Then give prioritized, stable findings `F01`, `F02`, and so on. For each finding provide:

- Severity and affected proposal/contract IDs.
- The exact disputed or incomplete claim.
- Repository path, symbol, and verified line numbers; include counterevidence when relevant.
- Why the issue affects the user's goal.
- A concrete correction, narrower claim, or proposed next step.
- Confidence and any validation limit.

Follow with a compact disposition table for P01–P10, the recommended first package, the important deferrals needed to preserve speed and agent identity, and remaining questions that cannot be resolved from repository evidence. Distinguish confirmed mistakes from design opinions. Do not invent findings to fill a quota, and do not treat an old test's expected economic direction as proof of real-world validity.

Keep the review detailed enough to act on, preferably around 2,000–4,000 words. Cite repository evidence throughout. State which checks you actually performed. Conclude with what is ready for planning and what still needs correction; this review is not empirical validation of EcoSim.
