# EcoSim agent instructions

## Ayman's product intent

Read [product intent](C:/Users/ayman/Documents/ecosim-internal/docs/product-intent.md) (internal documents live outside this repository in `C:/Users/ayman/Documents/ecosim-internal/docs/`) when making product, design, or performance tradeoffs. Explain policy effects at both macro and household/business levels; evaluate GDP alongside wellbeing. Reducing agent logic, decision/update frequency, or modeled behavior for speed requires prior discussion and agreement, including in a labeled quick mode. Discuss/show new UI/UX changes before implementing unless Ayman already explicitly directed them; routine backend improvements preserving agreed behavior are usually fine.

## Source of truth

The current GitHub `main` branch (`origin/main`) is the authoritative EcoSim repository. Do not assume an older local checkout is current. Before repository analysis or change work, verify the checked-out commit and its relationship to `origin/main`; if the checkout is behind, stop and reconcile it with GitHub before relying on local source or generated documentation.

## Current and legacy surfaces

Owner decision (Ayman, 2026-10-22): no new work on the classic dashboard. Agents previewed and changed the wrong frontend because both are on `main`. The generated wiki may still describe the classic dashboard as the app, so trust this section.

- **Current frontend: the town Run screen.** It lives in `frontend-react/src/next/` and opens at `?view=next` (entry `NextApp.jsx`; picked in `next/pickView.js`). Ayman works in it. Put new UI work here, and preview UI changes against it.
- **Legacy frontend: the classic dashboard.** It lives in `frontend-react/src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/` and `src/index.css`, and opens at `/`. It is still the URL default (see the README) but is frozen: no new features, panels or rows unless Ayman asks. Do not use it for mockups of current UI. Both apps share `src/main.jsx`, `src/socketUrl.js` and `src/charts/useMeasured.js`.
- **`income_first` is the norm, and the town runs it.** Owner decision (Ayman, 2026-10-22): `payment_sequence="income_first"` is the reference sequence. The town's SETUP (`next/live/plan.js`, `setupConfigs`) sends it, and so does the classic dashboard. Judge and report results on `income_first` first and `income_late` second. Do not lead with `legacy` results. The server default (`backend/server.py`, `backend/config.py`) is still `"legacy"`, so a client, tool or test that sends no `payment_sequence` runs `legacy`. Behavior that exists only on `legacy` (for example the annual private pay review, rent following the posted price, and the exit-deficit settlement) is a gap on the norm. It is not a reason to judge `legacy`.
- **"legacy" names four different things.** Say which one you mean:
  1. `payment_sequence="legacy"`: the old money and timing path. It is still the server default for clients that send no sequence. The town no longer runs it.
  2. `frame_profile="legacy"`: the classic dashboard's full frame shape. The town asks for `"lean"`.
  3. The classic dashboard UI itself.
  4. Ayman's "legacy firms": the baseline (public warm-up) Food, Housing, Services and Healthcare providers that the factory seeds. Ayman sees them as scaffolding that private firms should replace as the economy grows.

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

For economic-agent audits, proposals or delegated improvements, read `C:/Users/ayman/Documents/ecosim-internal/docs/ECONOMIC_AGENT_RULES.md` after the relevant wiki navigation. Its active version defines the shared tick order, actor/market boundaries, accounting, information and computational rules for this proposal cycle. Use `C:/Users/ayman/Documents/ecosim-internal/docs/ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md` for independent proposals and `C:/Users/ayman/Documents/ecosim-internal/docs/ECONOMIC_AGENT_WORKING_CONTRACT.md` for eventual implementation tickets. Distinguish binding rules from current behavior and known limitations; proposals do not authorize their own implementation. Shared-rule revisions are coordinated and versioned before dependent work proceeds. These requirements do not apply to unrelated repository work.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

The OpenWiki GitHub Actions workflow (run by hand from the Actions tab) refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
