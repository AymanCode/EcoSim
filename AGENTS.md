# EcoSim agent instructions

## Source of truth

The current GitHub `main` branch (`origin/main`) is the authoritative EcoSim repository. Do not assume an older local checkout is current. Before repository analysis or change work, verify the checked-out commit and its relationship to `origin/main`; if the checkout is behind, stop and reconcile it with GitHub before relying on local source or generated documentation.

## Required wiki-first navigation

For every task that requires understanding, reviewing, changing, or validating this repository, use `openwiki/` as the navigation layer before broad source exploration.

1. Begin at `openwiki/quickstart.md`.
2. Use `openwiki/where-to-change-what.md` to find owning files, important symbols, coupled surfaces, focused tests, and narrow validation commands.
3. Read the relevant linked architecture, backend, runtime, data, LLM, forecasting, frontend, engineering, or operations page before searching broadly.
4. Follow only the wiki routes relevant to the task; do not preload the whole wiki.
5. Verify important behavior and claims against current source code, tests, configuration, migrations, benchmark evidence, and deployment files. Those files remain authoritative.
6. If the wiki conflicts with current evidence, follow the current evidence and report the documentation drift. Do not hand-edit generated `openwiki/` pages unless the user explicitly asks for that.
7. If a completed change materially affects documented architecture, lifecycle ordering, economic behavior, session ownership, API or WebSocket contracts, policy/LLM behavior, schemas or persistence, forecasting, frontend/backend integration, performance evidence, testing, or deployment, refresh OpenWiki with the approved project tooling before final handoff when available; otherwise report that a wiki refresh remains due.

The managed OpenWiki block below calls the wiki optional just-in-time context. In this repository, “optional” means agents should not load the entire wiki up front; it does not make the wiki-first navigation sequence above optional. This durable policy takes precedence over that wording.

## Economic-agent proposal work

For economic-agent audits, proposals or delegated improvements, read `docs/ECONOMIC_AGENT_RULES.md` after the relevant wiki navigation. Its active version defines the shared tick order, actor/market boundaries, accounting, information and computational rules for this proposal cycle. Use `docs/ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md` for independent proposals and `docs/ECONOMIC_AGENT_WORKING_CONTRACT.md` for eventual implementation tickets. Distinguish binding rules from current behavior and known limitations; proposals do not authorize their own implementation. Shared-rule revisions are coordinated and versioned before dependent work proceeds. These requirements do not apply to unrelated repository work.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
