# Changelog

Notable changes and decisions for EcoSim, newest first. The project does not use version tags yet, so entries are grouped by date. Design decisions are logged here alongside code changes so the reasoning survives the conversations that produced it.

## Unreleased

### 2026-09-24: Phase 1 backend widening

Phase 1 backend widening landed: experiment registry, initial policy and receipts, horizon/finish/extend, TRACK, event stream, curated metrics, recorder, concurrent frame bench; gate: fail, bytes p95 186,587 and 188,160 for the two towns (limit 61,440, at two towns of 1,000 households, warehouse off), overhead share 1.9% (limit 10%), equivalence matched at all seven checkpoints. Evidence and the byte breakdown are in `docs/evals/2026-09-24-frame-bench/`.

### 2026-09-24: Frontend redesign, design decisions

Design phase only. No frontend code changed yet. Full design: [docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md](docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md). Approved mockups: [docs/superpowers/specs/2026-09-24-mockups/](docs/superpowers/specs/2026-09-24-mockups/).

Decisions:

- **Audience.** The dashboard is for newcomers learning economics by watching, not an analyst's console. Friendly names ("people out of work", "typical weekly pay", "town hall cash"), one-sentence definitions, a picture beside every number. The dense metric grid survives behind a "Show me all the numbers" link.
- **Unit of work is an experiment**, not a run: a mode, a seed, a shared world config, and one to four arms ("towns"). Arms run as live side-by-side backend sessions in one browser. The household budget is 10,000 per experiment, split evenly across arms. Fixed horizon, default five years, extendable a year at a time.
- **Three modes.** Compare policies (two to four towns, one policy difference each). Test an AI mayor (one LLM-governed town plus an optional frozen-policy control; comparing two LLMs happens later through saved runs). Just play (one town, all levers).
- **Run screen** is two matching columns, Town A and Town B: a live drawing of the town (houses coloured by work status, Main-street buildings sized by staff, struggling and closed flagged), businesses ranked richest-first with status tags, four random households as cards with a follow action, then a shared annotated full-horizon chart, a plain-language verdict ending in a question, four stat cards, an event feed, and a "how to read this" panel. The AI mayor variant adds a decision strip, an expanded decision card (what it saw versus the truth, what it asked for versus what the rules allowed, its reasoning, an evidence check, what happened next) and a report card.
- **Setup screen** leads with "What do you want to find out?": mode cards, question cards backed by simulation evidence, the towns, and shared world settings. Seeds are rolled automatically and hidden from newcomers.
- **Question cards must be evidence-backed.** Audited against mechanics and the checked-in policy sweep: minimum wage, benefits, wage-versus-profit tax, and food subsidy are backed; public works is wired but unmeasured and needs a smoke run before it ships. Two copy errors caught: high benefits raise distress rather than lower it, and a food subsidy is a voucher that lowers what households pay without moving the posted price.
- **Fiscal number.** The UI shows the town hall's cash balance, signed, so "owes" is visible without a separate debt metric. The frame's `govDebt` is derived from that balance and stays consistent; the internal `public_debt` metric is inert and is not used.
- **Backend widening**, not new machinery: experiment id and arm label on SETUP with a server-side household cap, a curated set of about 30 metrics out of the 150 already computed, a discrete event stream in the frame, all firms instead of top twelve, a larger reshufflable household sample with populated recent events, full LLM decision history with the true values stored beside what the model saw, and a run-recording tool for backend-free frontend development.
- **Frontend architecture.** New shell around an experiment store (one socket and full frame history per arm, a derived layer that aligns arms by tick), a single narration module of event templates, replay mode from recorded runs, and the existing token mechanism with new values: light theme, Bricolage Grotesque and Instrument Sans, colour-blind-validated arm and status colours. Keep the current time-series component, its by-tick alignment, and the Government screen's before/after pattern.
- **Why the previous dashboard read as generic.** Structural, not stylistic: every screen was an equal-weight tile grid, one chart type used identically everywhere, three of 150 computed metrics reaching the browser, events warehouse-only, no time scrubbing, no run comparison. The 2026-09-06 spec banned glow and gauges and did not fix this.
- **Second-pass check.** After sign-off, a second Codex pass on `gpt-6-astra` (`docs/reviews/2026-09-24-frontend-redesign-spec-check2.md`) found no design reversal but corrected seven facts (benefits lower distress at newcomer scale, "exits" were declining ticks, food price shows no consistent separation rather than none, capacity is rejected at socket open, tick timing includes snapshots, provider failure has two cases, events and firms already partly reach the browser) and added two requirements: CONFIG action receipts so replay uses applied values, and a separate deterministic RNG for household sampling so browsing cannot change a matched comparison. The one-pager was corrected to say 1,000 households each by default and "about 30" metrics.
- **Signed off 2026-09-24.** Ayman approved the direction from the one-page overview and accepted legacy rules at 1,000 households per town as the interim default world; baseline calibration remains a backend task before phase 2 reaches newcomers.
- **Smoke runs at newcomer scale** (1,000 households, 260 ticks, seeds 1337 and 7): only the minimum-wage and benefits cards separate visibly; taxes, food subsidy and public works do not, so they wait in "Build my own". Every tested baseline world (legacy or `income_first` at 1,000 households, legacy at 5,000) ends five years as a depression, with unemployment 23 to 39 percent. `income_first` keeps the town hall solvent but raises household distress from 0.40 to 0.60 and sustains homelessness. Interim default stays legacy at 1,000 households; baseline calibration is a backend task before phase 2 reaches newcomers. Details in the spec, section 5.
- **Independent audit.** At Ayman's request the spec was audited by Codex (`gpt-6-sol`, high reasoning, read-only); the report is at `docs/reviews/2026-09-24-frontend-redesign-spec-audit.md`. Accepted and folded into the spec: the schema has 17 levers not 16; the frame already carries about 40 metric keys, the gap is which ones; closed firms leave the live collection and need an archive; the household cap must be a server-owned experiment record, not a per-socket claim; presets need a validated `initial_policy` on SETUP; the server needs horizon, FINISH and EXTEND; raw frames must not be retained in the browser; the story chart is a new component rather than the existing time series; the LLM rationale is truncated to 500 characters, rejection reasons are codes, the tax move cap is 5 points not 3, and the evidence audit checks cited figures not prose claims; "a week of groceries" is a posted unit price and the food-subsidy card needs an out-of-pocket metric. Lifecycle failure rules, non-functional requirements and a full-path benchmark were added.
- **Process.** Visual questions get mockups, not prose. Implementation is delegated to Opus 5.5 subagents; Sonnet handles reading and audits. Phases: backend widening and recording, then Setup and the policy Run screen, then the AI mayor screen, then saved experiments.

### 2026-09-24: Phase-1 plan audited and revised

The first draft of `docs/superpowers/plans/2026-09-24-frontend-redesign-phase1-backend.md` was audited by Codex (`gpt-6-astra`, high reasoning) and judged not ready: eight code defects (a dedent instruction that would have broken the server, a failed SETUP leaving a runnable economy, a test that could not pass, FINISH undone by disconnect, closures repeated every tick, off-by-one event ticks, a wrong median, misaligned smoke checkpoints), weak or flaky tests, and a single-socket benchmark that could not prove the gate. Audit saved at `docs/reviews/2026-09-24-phase1-plan-audit.md`. The plan was rewritten: experiment owner and shared-world checks, shared lever validation at runtime, warehouse lifecycle across FINISH/EXTEND/disconnect, identity-keyed events with shock instrumentation, fresh per-tick projection, a recorder that captures commands and errors, and a concurrent multi-arm benchmark with serialization timing and an equivalence assertion against the smoke runner.

### 2026-09-24: Newcomer-scale smoke benchmark

Added `backend/tools/benchmarks/run_newcomer_smoke.py`, a matched-seed policy-arm runner at dashboard defaults (1,000 households, 260 ticks, 5 firms per sector) with `--payment-sequence`, checkpoint deltas and a `summary.md`, plus a fast contract test. Evidence from the 2026-09-24 runs (18 per-tick CSVs, meta, logs, README with verdicts) is under `docs/evals/2026-09-24-newcomer-smoke/`; `.gitignore` gained an exception so `docs/evals/**/data/` is tracked despite the global `data/` rule. Listed in `docs/README.md` and `backend/README.md`. A wiki refresh is due for `openwiki/engineering/testing-performance.md`.

### 2026-09-25: History cleanup and phase 2, slice 1 (the new Run screen)

- **History.** The payment revamp moved to its own branch, `feat/payment-settlement-book`, as three verified commits (agent and wiki tooling; the payment settlement book with its tests and evidence; docs and CI). `feat/frontend-redesign-phase1` was rebuilt on top of it as one commit per task with fix rounds folded in; its final code is unchanged. The previous history is kept under `backup/` branches.
- **Phase 1 close-out.** A final Opus review found that new defaults froze the classic dashboard at week 260 and that group lever rules broke its controls. Task 9 added a `frame_profile` SETUP option: `legacy` (default) keeps the classic dashboard's keys and defaults; `lean` drops per-frame household detail except for pinned households and sends traits out of band. The phase-1 gate passes under lean: frame bytes p95 about 44 to 45 KB against 60 KB, overhead 0.7 percent, equivalence 7 of 7.
- **Phase 2, slice 1** on `feat/frontend-redesign-phase2`, opened at `?view=next` (the classic dashboard stays the default): a pure data layer over recorded frame-2 sessions with incremental ingest, friendly names for residents and firms, a metric and lever catalog, and narration; the town drawing, businesses ranked richest first, household cards, stat cards, an event feed, an annotated story chart with the warm-up shaded, play and scrub controls, and a two-town demo recorded at 500 households over two years (a higher minimum wage against no change). An Opus review led to one fix round focused on truthfulness (eviction wording, tracked-versus-town-wide counts, rounding ties, a three-month verdict window), contrast to 4.5:1, and a shape cue so houses are not distinguished by colour alone. 253 frontend tests pass.

### 2026-09-25: Phase 2, slice 2 (Set up and live towns)

- **Backup.** With Ayman's approval, the three feature branches were pushed to GitHub as a backup: `feat/payment-settlement-book`, `feat/frontend-redesign-phase1` and `feat/frontend-redesign-phase2`. `main` is untouched, and nothing was merged.
- **Set up screen** at `?view=next`, from the approved mockup:
  - three kinds of experiment: Compare policies, Just play, and Test an AI mayor (shown as "coming soon");
  - the two evidence-backed question cards (minimum wage, benefits) plus "Build my own";
  - one to four towns, each with a rules editor covering all 17 levers in five plain-language groups, with one checked sentence per lever and the backend's group rules mirrored;
  - households per town capped at an even share of 10,000;
  - 1, 2, 5 or 10 years, and a town number ("Town #48213") instead of a seed; the number field appears only under "Build my own";
  - a time estimate taken from the phase-1 benchmark;
  - problems shown in place, including "the simulation isn't running" with the start command and a link to the recorded example.
- **Live towns.** A framework-free controller opens one WebSocket per town, lean profile, with a shared experiment id and owner.
  - **Start.** Each town gets its SETUP once the server sends SESSION, and every town starts only after all of them are set up.
  - **Keeping pace.** A town more than three weeks ahead of the slowest is paused until the others catch up.
  - **The end.** FINISH goes to every town once all of them reach the horizon, and "Add a year" sends EXTEND.
  - **Leaving.** "New experiment", unmount and any failure close every socket, which releases the household budget.
  - **Errors.** A full server, an unreachable server, a failed SETUP, a lost town or a crashed server loop each get plain copy and a way forward.
- **Run screen, live.** The slice-1 Run screen now plays live:
  - a live clock with "Back to live" after scrubbing;
  - a Town hall drawer that changes one town's rules from the next week and shows receipts, including rejected levers;
  - an end panel with the verdict, which collapses to a slim bar when you scrub back;
  - a lost-town panel with a restart;
  - "Meet other families" and Follow, both backed by TRACK.
  
  Column heads, the verdict and "How to read this" describe the rules in force in the week on screen, including changes made mid-run.
- **Moments.** A strip under the lead sentence calls out a town hall rule change, a new richest business, or unemployment crossing 10, 20 or 30 in 100. The last one ignores flips back and forth near the mark. The town hall in the drawing pulses for a few weeks after its rules change. Warm-up weeks are skipped.
- **Review.** Four Opus implementers built the slice, one per task. One Opus review of the whole slice found 6 Important and 10 Minor issues. The main ones:
  - rules in the Town hall snapped back after a change;
  - rule labels ignored changes made mid-run;
  - raw server errors showed on screen;
  - a crashed server loop froze the experiment;
  - the drawer's focus order;
  - the moments strip shifted the page.
  
  One fix wave addressed all of them. A scoped re-review confirmed 15 of 15. One timing difference was accepted: while paused, an applied change shows in the Town hall at once but in the column head only from the next week, which is when it takes effect.
- **Checks.** 412 frontend tests pass, and lint and build are clean. Two small live runs on the real backend exercised every step: two towns of 200 households for one year, then Add a year, pause, a Town hall change and its receipt, resume, the end panel, moments, scrubbing back, and Just play. No console errors.
- **Deferred:**
  - replaying the lever changes when a lost town is restarted (the restart says they are not repeated);
  - the spec's "finish now, marked incomplete" option;
  - the mockup's "Money rules" toggle, which waits for the baseline calibration decision;
  - the AI mayor screen;
  - "Show me all the numbers";
  - making `?view=next` the default.
- **For Ayman (backend, not changed):** `backend/policy_vectors.py:65-67` requires a bailout target even for `bailout_policy: 'all'`, but `backend/economy.py:6116-6122` ignores the target in that case. The frontend mirrors the backend rule for now.
- **OpenWiki.** A refresh is due. This slice adds a second WebSocket client and a new Set up to Run flow; the scheduled workflow will pick it up once the branch reaches `main`.

### 2026-09-24: Phase 1 branch status

Branch `feat/frontend-redesign-phase1` holds the eight phase-1 tasks, each implemented by an Opus 5.5 subagent and reviewed per commit (Codex Astra for Tasks 1 to 8, with fix rounds until clean). The phase gate at two towns of 1,000 households passes overhead (1.9 percent) and live-versus-headless equivalence (7 of 7 checkpoints) and fails frame size (p95 about 187 KB against 60 KB) because the 40 tracked households carry per-frame history, traits, wage-reasoning and recent events. That contract change is deferred to phase 2's first task, to be built with the new client adapter. The final whole-branch review is deferred to a later session; the branch is unmerged. An OpenWiki refresh is due for the new commands and frame keys. On 2026-09-25 the deferred contract change landed as the SETUP option `frame_profile` (`legacy` by default, with the pre-branch defaults of no horizon and 12 tracked households; `lean` for the new client), and the same gate command under `lean` passes with exit code 0: bytes p95 43,876 and 45,379 (was 186,587 and 188,160), overhead 0.7 percent, equivalence 7 of 7.

Shock events are also written to the warehouse `regime_events` table (`entity_type` `economy`). Session results for a given seed differ from pre-branch runs because household sampling no longer draws from the session RNG, so seed-level comparison with older warehouse runs is not valid.

### In progress: payment settlement book (PS3.1)

Uncommitted in the working tree: `backend/payments.py`, `backend/payment_*.py`, and matching tests introduce a versioned settlement book so every dollar has an owner and a funding source (wages, rent, loans, care, housing projects settled in order each tick). See `docs/ECONOMIC_IMPLEMENTATION_PLAN.md` and `docs/ECONOMIC_MODEL_PROPOSAL.md`. The new `metrics.payment` block reaches the frame only when `payment_sequence` is not `legacy`.

## 2026-09-07

- Rebuild the React dashboard as a command center (`4f69389`). Split the monolithic app into screens, charts, UI primitives, and a token stylesheet. Superseded in direction by the 2026-09-24 decisions above.

## 2026-09-03

- Restructure the README for a neutral, reader-first presentation (`70a26d0`).
- Rewrite the AI government overview in the author's voice (`c19388f`).

## 2026-08-05

- Dependency bumps for the frontend and Python groups, CI on Node 22 with pyarrow capped below 25, and a Vite `manualChunks` fix (`ffe54a3` through `49acde3`).
