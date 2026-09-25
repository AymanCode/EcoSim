# Frontend redesign: session summary, 2026-09-24

A plain-language record of how the redesign was decided in one working session, for anyone (or any reviewer) who needs the reasoning without reading the full spec. The spec is `2026-09-24-frontend-learning-redesign-design.md`; the one-page visual is `2026-09-24-mockups/00-overview.html`.

## Starting point

Ayman's complaint: the React dashboard reads as a generic, AI-generated grid built in one pass. Before touching design he wanted three things established: what EcoSim is for, what data it produces, and what the screen should show.

Three read-only audits established the facts. EcoSim is a weekly-tick agent-based economy (households, firms in four sectors, one bank, a government with a 17-lever policy schema) with an optional LLM "government" that sees a lagged, noisy summary and proposes bounded policy changes that code clamps or rejects. The docs disagree about the audience (research tool, portfolio piece, CS-101 primer). The backend computes about 150 metrics per tick and discrete events, but the browser frame carries about 40 metric keys, twelve tracked households, two top-twelve firm leaderboards plus seven tracked firms, policy-change records and the latest LLM decision; the labor, healthcare and regime events never reach it. The old dashboard is generic for structural reasons: equal-weight tile grids, one chart type used identically everywhere, no time scrubbing, no run comparison.

## Decisions, in order

1. **Viewer.** A newcomer learning economics by watching. Ayman rejected a dense 24-chart analyst mockup as "a PhD-level tool". Every number gets a friendly name, a sentence, a picture, and both towns' values. The analyst grid survives behind "Show me all the numbers".
2. **Unit of work.** An experiment: mode, seed, shared world, one to four towns. Towns run as live side-by-side backend sessions. 10,000 households per experiment, split evenly. Fixed horizon, default five years. A single town is the sandbox.
3. **Modes.** Compare policies; Test an AI mayor (one LLM town plus an optional frozen control; LLM versus LLM later through saved runs); Just play.
4. **Screens.** Chosen from three mockup directions, then merged: two matching columns per town (town drawing, businesses ranked richest first, random household cards), then a shared annotated story chart, a verdict ending in a question, four stat cards, an event feed, and a how-to-read panel. The AI mode adds a decision strip and an open decision card (what it saw versus the truth, what it asked versus what the rules allowed, its words, an evidence check, what happened next) and a report card. Set up leads with "What do you want to find out?" and question cards. Seeds are hidden from newcomers.
5. **Approach.** New shell and experiment store, widened backend frame, reuse of the token mechanism, the by-tick alignment helper and the before/after pattern. Light theme, Bricolage Grotesque and Instrument Sans, colour-blind-validated palette. Visual polish is a later pass.
6. **Evidence rule for question cards.** Each card must be backed by mechanism and measured effect. Audit against the code and the checked-in 10,000-household sweep, then a smoke run at newcomer scale (1,000 households, 260 ticks, two seeds) with a checked-in runner. Result: minimum wage and benefits launch; taxes, food subsidy and public works are held. Card copy never promises a direction, because the benefits effect flips sign between scales.
7. **Baseline finding.** Every tested default world ends year five as a depression (23 to 39 percent unemployment). Legacy rules at 1,000 households: insolvent town hall. The new income-first payment rules: solvent town hall, no bankruptcies, but distress 0.60 and sustained homelessness. Legacy at 5,000: the healthiest headline at three minutes per town. Interim default: legacy at 1,000. Baseline calibration is a backend task before phase 2 reaches newcomers.
8. **Independent audits.** At Ayman's request the spec was audited by Codex (`gpt-6-sol`, high reasoning; the bare `astra` slug was rejected by the account, `gpt-6-astra` worked for the second pass). Its findings were folded in: server-owned experiment record for the household cap, a validated initial-policy field on SETUP, horizon/finish/extend commands, closed-firm archive, out-of-pocket food metric, no raw-frame retention in the browser, a new story-chart component, corrected LLM facts (500-character rationale, reason codes, five-point tax cap, cited-figure audit), lifecycle failure rules, non-functional requirements, a full-path benchmark gate. A second pass on `gpt-6-astra` after approval fixed seven factual slips and added action receipts and a separate sampling RNG so browsing households cannot alter a matched comparison.
9. **Sign-off.** Ayman approved the direction from the one-page overview on 2026-09-24.

## Process rules set during the session

- Visual questions get mockups, not prose; Ayman judges layouts by eye.
- Implementation is delegated to Opus 5.5 subagents; Sonnet handles reading and audits; Codex only when Ayman explicitly asks for it, never for implementation.
- Decisions are logged in `CHANGELOG.md` at the repo root.

## Artifacts

- Spec: `docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md`
- One-pager and mockups: `docs/superpowers/specs/2026-09-24-mockups/`
- Audits: `docs/reviews/2026-09-24-frontend-redesign-spec-audit.md` and `docs/reviews/2026-09-24-frontend-redesign-spec-check2.md`
- Smoke runner: `backend/tools/benchmarks/run_newcomer_smoke.py`; evidence: `docs/evals/2026-09-24-newcomer-smoke/`
- Decision log: `CHANGELOG.md`

## Next

Write the phase-1 implementation plan (backend widening: experiment record and cap, initial policy, horizon and finish, curated metric projection, event stream, household sample and TRACK, recording tool, full-path benchmark), then execute it with Opus 5.5 subagents under review.
