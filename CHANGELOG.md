# Changelog

Notable changes and decisions for EcoSim, newest first. The project does not use version tags yet, so entries are grouped by date. Design decisions are logged here alongside code changes so the reasoning survives the conversations that produced it.

## Unreleased

### 2026-09-28: Agents/economy remediation, phase 2 (performance, behavior-preserving)

No simulated number changed. After every commit all three golden compares matched at the default tolerance (1e-6) and the contract suite passed (473 passed, 5 xfailed). Plan: [docs/reviews/2026-09-28-agents-economy-remediation-plan.md](docs/reviews/2026-09-28-agents-economy-remediation-plan.md), phase 2; audit items D40-D49.

- Payment-path golden. `regression_snapshot` takes `--payment-sequence {legacy,income_first,income_late}` (default `legacy`) and runs inside a cloned config context, as `run_newcomer_smoke` does. New golden `benchmarks/results/golden_1500_s42_t80_income_first.json` (1,500 households, seed 42, 80 ticks). It was saved after phase 1, so phase 1's payment-path deletion is covered by the contract suite only.
- Rental market. Before: each renter's firm was found by scanning the housing firms, each homeless household sorted its candidate list, and the homeless count (phase 6.6) and each firm's tenant count (expansion loans) were rescanned over all households per housing firm. Now: a dict of housing firms, `min()` for the cheapest unit (same tie-break as the stable sort), and one count per tick passed to `invest_in_unit_expansion` through a new optional `homeless_count` argument. Golden compares matched.
- Awareness pool. Before: every pool lookup rebuilt a tuple of the pool's firm ids to validate its cached set, and the consumption planner built the set just to test emptiness. Now: the cache is checked by list identity and length, and the planner reads `awareness_pool` directly. Golden compares matched.
- Static household traits. Before: `_batch_plan_consumption` regathered six trait arrays, the category-weights matrix and one fraction dict per household every tick. Now: `Economy._household_static_traits()` builds them once, keyed by the household list's identity and length. Golden compares matched.
- Wage bill. Before: `FirmAgent._current_wage_bill()` summed over all employees on each of about ten calls per firm per tick. Now: the sum is cached with the roster, the wage map and `wage_offer`, and every in-place writer calls `_invalidate_wage_bill_cache()`. A throwaway check over 120 ticks compared every cached value with a fresh sum and found no mismatch. Golden compares matched.
- Metrics. Before: `get_economic_metrics` made five household passes for employment counts, sorted household cash twice in Python and partitioned it twice more in numpy, summed firm revenue twice, and scanned all firms once per category. Now: one counting pass, one `sorted()` reused for the median, Gini, percentiles and shares, one revenue sum, and one grouping pass. Before/after dumps of all metrics at ticks 5 and 50 are identical by `repr`. One pitfall found on the way: builtin `sum()` compensates only for exact floats, so turning the `np.float64` cash values into Python floats changed the Gini in the last bits; the sort keeps the original objects. Golden compares matched.
- Wellbeing gather. The midpoint fallbacks for missing morale parameters are computed once per call instead of once per household. The planned single-pass gather (one row per household, then transpose) was bit-identical but slower (2.92 ms against 2.75 ms per call at 5,000 households), because the cost is attribute access, not the number of passes. It was not adopted, and the `np.fromiter` gathers stay. Golden compares matched.
- Unfilled-vacancy diagnostics. Before: for each firm with open vacancies, `_match_labor_fast` rebuilt the remaining-searcher mask over all households, filtered it and took a median. Now: the pool and one sorted copy are built once, the per-firm count is a `searchsorted` (the threshold is cast to float32 first, matching how numpy compares), and the all-rejected median is computed once. Per-tick diagnostics over 150 ticks are identical to the old code. Golden compares matched.
- Healthcare inventory scan. Before: every tick walked every household's `goods_inventory` to delete healthcare goods. It never found any: healthcare firms have zero inventory before the goods market, and the payment market excludes them. The scan is deleted. Golden compares matched.
- Duplicate per-tick work in `step()`: (a) working-capital candidacy is recorded in the planning loop only when `_issue_working_capital_bridges` will not run, since the bridges overwrite it; (b) `get_minimum_wage()` is read once before the firm planning loop instead of twice per firm; (c) the firm health snapshot dicts are built only when `audit_log_enabled`, their only reader. Golden compares matched after each. The payment path's second `prepare_household_dues` call was left as is: the first call is required (it prepares the due index that consumption planning and care requests read), and the second is a same-tick cache hit that costs nothing.
- Loop fusion. The three phase 2 firm passes (turnover reset, posted-offer pool, offer buckets) are one pass. The four phase 2 household passes (education, job-search cooldown, labor plan, consumption-loan request) are one pass, with the warm-up and bank guards kept inside. Only the cooldown draws from an RNG (its own per-tick `random.Random`, still in household order), and the loan requests are read only by `_offer_consumption_loans`, which stays after consumption planning. Golden compares matched.
- Slots. `AgentMixin` declares `__slots__ = ()`, so `@dataclass(slots=True)` on the household, firm and government agents takes effect and instances no longer carry a `__dict__`. One engine attribute was undeclared and is now a field: `FirmAgent._pending_construction_cost` (default 0.0). Tests that replaced agent methods on instances use a new `tests_contracts.factories.patch_agent_method` helper, and the deposits rent stub keeps its withdrawal counters itself. Golden compares matched.

No item was reverted for changing behavior.

`run_sim_bench` (seed 42, 80 ticks, one run each; phase 0 baseline at 0561ec1, before at 64ebbfa, after at 96928d4):

| Households | Phase 0 p50 / p95 ms | Before p50 / p95 ms | After p50 / p95 ms | p50 change vs before |
|---:|---:|---:|---:|---:|
| 1,500 | 130.0 / 184.7 | 127.1 / 181.6 | 120.4 / 177.9 | -5.3% |
| 5,000 | 456.3 / 667.5 | 446.3 / 653.8 | 430.2 / 637.6 | -3.6% |

### 2026-09-28: Agents/economy remediation, phase 1 (dead code)

Deletions only; no engine behavior changed. Every symbol below was checked by a repo-wide word grep (excluding `node_modules`, `__pycache__`, `.venv`, `openwiki/`, `docs/`) before removal. Plan: [docs/reviews/2026-09-28-agents-economy-remediation-plan.md](docs/reviews/2026-09-28-agents-economy-remediation-plan.md).

Per-agent household paths replaced by the batch path (audit C33):

- `HouseholdAgent.plan_consumption`: planned a household's budget and purchases; replaced by `Economy._batch_plan_consumption`, no production caller.
- `HouseholdAgent.compute_saving_rate`: wealth-based saving rate used only by `plan_consumption`; the batch path uses `savings_drawdown_rate` instead.
- `HouseholdAgent.apply_income_and_taxes`: added wage and transfers to cash and subtracted taxes; inlined in `_batch_apply_household_updates`.
- `HouseholdAgent.apply_purchases`: debited purchases, stocked inventory and updated price beliefs with asymmetric alphas; inlined (with a single alpha) in `_batch_apply_household_updates`.
- `HouseholdAgent.consume_goods`: consumed 10% of inventory per tick; the batch path's inventory loop (food eaten up to the health threshold, half the rest spoils) replaced it.
- `HouseholdAgent.update_wellbeing`: per-household happiness, morale and health update; replaced by `Economy._batch_update_wellbeing`.

Never-called methods (audit C34):

- `HouseholdAgent.apply_skill_decay`: lowered skills after long unemployment; no caller, so skills never decayed.
- `HouseholdAgent.invest_in_education`: bought skill with cash; no caller (`maybe_active_education` is the live path).
- `HouseholdAgent.start_medical_training`, `update_medical_training_progress`, `accrue_medical_school_interest`, `make_medical_school_payment`: the medical-school pipeline (enrol, advance student to resident to doctor, accrue and repay school debt); no caller. With them gone nothing sets `medical_training_status` to "student" or "resident", so the student branches in `can_work` and `plan_labor_supply` and the resident branch in `medical_visit_capacity` were removed too. Set-membership reads of those strings (and the server and warehouse labels) are unchanged.
- `HouseholdAgent._healthcare_visit_distribution`, `_sample_annual_visit_count`, `_refresh_annual_healthcare_visit_plan`, `_consume_due_healthcare_slot`: the annual care-plan scheduler; replaced by the episode model in `should_request_healthcare_service`, no caller. The `care_plan_*` fields stay.
- `HouseholdAgent._filter_to_awareness_pool`: filtered firm options to the awareness pool; no caller.
- `FirmAgent._stockout_sales_floor_multiplier`, `FirmAgent._stockout_hire_growth_rate`: stockout demand and hiring multipliers; no caller.
- `AgentMixin.apply_overrides`: generic attribute setter; no caller. The class stays.
- `BankAgent.pay_deposit_interest`: computed weekly deposit interest; no caller.
- `BankAgent.to_dict`: bank serializer; only tests called it, and no frame, metrics or warehouse code reads it.
- Unused parameters: `health_snapshot` of `FirmAgent._bounded_observed_demand_units`, and `firm_market_info` and `category_option_cache` of `HouseholdAgent._plan_category_purchases`. Callers updated; the remaining positional order is unchanged.

Unreachable or no-op code (audit C36, C38 and the FirmAgent dead-code list):

- The payment path built household tax snapshots and then passed `[]` to `plan_taxes`; the build now runs only on the legacy path.
- `elif category == "services"` in the receipt block of `_batch_apply_household_updates` (services `continue` earlier).
- In `_maybe_create_new_firms`, a nested `payment_sequence == "legacy"` check that repeated the outer one, and four `chosen_category == "Housing"` blocks that could not run because the housing path returns first.
- A duplicate `reservation_levels.size == 0` block in `_match_labor_fast`.
- `path_a_approved` in `_offer_housing_expansion_loans`, which only held firms that the loop already skips.
- In `FirmAgent`: the always-zero `fixed_cost` term, three always-true `health_snapshot is not None` checks, a max/min pair on warmup baseline hiring that never bound, a `return True` after `return False`, and a repeated `!= "healthcare"` test.
- In `HouseholdAgent`: an unused `config` local, a second `hh_config` fetch, and a redundant local `from config import CONFIG`.

Tests:

- `test_contracts_behavior.py`: the food-health, mercy-floor and morale contracts now run through `Economy._batch_update_wellbeing`; the services-flow contract runs through `_batch_apply_household_updates`.
- `test_contracts_behavior.py::test_contract_batch_wellbeing_matches_per_agent_update_path` retargeted with pinned values instead of deleted: renamed `test_contract_batch_wellbeing_unemployed_unhoused_wealth_loss_with_social_multiplier`, same setup (unemployed, unhoused, cash 1,000 to 700, multiplier 1.1), asserting the batch outputs recorded at d512de7, where batch and per-agent agreed within 1e-8.
- `test_contracts_deposits.py`: the two deposit-liquidity planning contracts now call `Economy._batch_plan_consumption`.
- `test_contracts_income_perception.py`: the dividend planning contracts call `_batch_plan_consumption`; the services-happiness contract calls `_batch_update_wellbeing`.
- `test_contracts_healthcare.py::test_contract_annual_visit_plan_by_health_bucket_is_deterministic` deleted: it only tested the unused annual care-plan scheduler.
- `test_contracts_bank.py::test_contract_pay_deposit_interest_no_total_deposits_inflation` deleted: it only tested `pay_deposit_interest`.
- `test_loan_settlement.py::test_missing_treasury_recipient_fails_before_mutation` compares a deep copy of the bank dataclass instead of `to_dict()`.
- `test_contracts_behavior.py` and `test_hot_path_optimizations.py` calls to `_plan_category_purchases` updated for the removed parameters.
- `backend/tools/checks/test_household_agent.py` (not in the default suite) now exercises the batch paths.

Config fields now unused, kept for compatibility: `households.skill_decay_unemployment_threshold`, `skill_decay_rate_per_tick`, `skill_decay_floor`, `low_wealth_reference`, `high_wealth_reference`, `price_alpha_up`, `price_alpha_down`, `extreme_negative_cash_threshold`, `medical_training_ticks`, `medical_residency_start_fraction`, `medical_resident_max_capacity`, `medical_school_min_payment`, `medical_school_repayment_share_of_wage`, `healthcare_visit_distribution_below_10`, `healthcare_visit_distribution_below_30`, `healthcare_visit_distribution_below_70`, `healthcare_visit_distribution_healthy`.

Both golden compares (`golden_1500_s42_t80.json`, `golden_1500_s7_t300.json`) matched after each commit. Contract suite: 473 passed, 5 xfailed (was 475 passed, 5 xfailed; two tests deleted as listed above).

### 2026-09-28: Agents/economy remediation, phase 0 (instrumentation)

No engine behavior changed; both golden compares match. Audit: [docs/reviews/2026-09-28-agents-economy-code-audit.md](docs/reviews/2026-09-28-agents-economy-code-audit.md). Plan: [docs/reviews/2026-09-28-agents-economy-remediation-plan.md](docs/reviews/2026-09-28-agents-economy-remediation-plan.md).

Before:

- One multi-tick conservation contract (`test_contract_accounting_conservation_across_post_warmup_steps_without_cash_sinks`), run with sink mechanics disabled and no bank.
- `total_money` in `backend/tests_contracts/conftest.py` left out bank reserves, so bank lending leaks could not be seen.
- No golden snapshots committed; `benchmarks/results/` is gitignored.
- No tool to measure per-tick money drift.

Now:

- `total_money_with_bank` in `backend/tests_contracts/conftest.py` adds `bank.cash_reserves`. Household deposits are not added separately: `BankAgent.accept_deposit` moves the cash into `cash_reserves`, so the deposit balance is a claim on money already counted.
- `backend/tests_contracts/test_conservation_leaks.py`: four `xfail(strict=True)` tests, one per audit item A1-A4, each failing today on its own conservation or interest assertion (A1 +1,144.45 created by a scaled-down subsidized food purchase; A2 -25,000.00 when a long-term capital loan is wiped; A3 +15.00 from the medical-loan fallback with a bank that cannot lend; A4 a 520-tick loan owes 10,500 instead of 15,000 and a 26-tick loan 10,500 instead of 10,250). A passing control test steps the same small legacy economy with a bank for 5 ticks and conserves money exactly; these are warmup ticks only, because past warmup the same economy drifts from tick 11 as legacy new-firm creation seeds cash (audit A5). When a Phase 4 fix lands, strict mode fails on the stale marker so it gets removed.
- `backend/tools/checks/money_supply_drift.py` prints total money with bank per tick for the same seeded economy as the regression snapshot tool.
- Goldens committed: `benchmarks/results/golden_1500_s42_t80.json` and `benchmarks/results/golden_1500_s7_t300.json`.

Measured drift (defaults: 1,500 households, 10 firms per category, seed 42, 120 ticks, legacy): total money starts at 9,063,750.00 and ends at 9,025,047.44, a net change of -38,702.56 (-0.43%). Gross absolute drift is 681,124.05 over 51 of 120 ticks; the first nonzero tick is 14. Largest single ticks: -60,000.00 (ticks 21 and 102), +29,070.57 (tick 65), +28,006.47 (tick 60), +27,792.22 (tick 38). In one comparison run with long-term capital loans disabled, the round negative steps (-5,000 to -60,000) disappear, which points at A2. The large positive steps (about 16,000 to 30,000) fall in the 5,000-30,000 range of legacy new-firm seeding (audit A5); the small positive and non-round negative steps are unattributed. That comparison run ended at a net +312,971.50, about 8 times the size of the headline net -38,702.56, which suggests money creation is much larger than the headline shows and A2's destruction is masking most of it. The comparison run's trajectory also diverges, so this attribution and the masking estimate are leads, not measurements.

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

### 2026-09-25: Bailout rule made consistent

- **The disagreement.** Three places read `bailout_policy: 'all'` differently. The economy ignores the target and lends to any distressed private firm. The AI mayor's prompt asks for target `none`. The SETUP and lean CONFIG check (`policy_group_errors`, a phase-1 mistake) asked for a real target under any policy other than `off`, and the new frontend mirrored it. This resolves the slice-2 note above.
- **The rule, everywhere.** `off` needs target `none` and budget 0. `sector` needs a target of food, housing, services or healthcare and a budget above 0. `all` needs target `none` and a budget above 0. The target is checked before the budget, with one reason per group. SETUP's `initial_policy`, lean CONFIG and the new frontend's editor all use it, and `docs/WEBSOCKET_PROTOCOL.md` states it, including that SETUP holds `initial_policy` to the group rules under both profiles.
- **AI mayor.** Its live path (`sanitize_llm_government_changes_detailed`, through `_validate_group_invariants`) already enforced the rule, clearing a sector sent with `all`; a contract test now pins that. The older helper `_enforce_cross_lever_consistency` got the `all` branch as briefed, but it is unreachable (`_validate_decisions` returns before calling it and has no caller). It does not state the whole rule either: it never requires a budget for `sector` or `all`, and it drops an `off` change instead of fixing it. A separate cleanup will remove it.
- **Set up and Town hall.** Choosing "off" also clears the sector and budget, and choosing "any business" clears the sector. The sector choice shows only for bailouts for one sector, the budget only while bailouts are on. Rules read "bailouts for any business with a $10,000 budget". The story chart draws one marker per town per week of change, reading the levers of that week as one rule, as the Moments strip already did.
- **Unaffected.** The classic dashboard runs the `legacy` profile, where CONFIG applies levers one by one without group rules, and it sends no `initial_policy`.

### 2026-09-25: Phase 2, slice 3 (Show me all the numbers)

- **The numbers sheet.** Rules in force, eight numbers at a glance, and six groups: work and pay, prices, rich and poor, businesses, money, and wellbeing. Hires and lay-offs, price tags, the savings ladder, share bars, business states, town hall cash and flows, and the feel meter give the numbers pictures. The sheet follows the Run screen's clock, opens from its timeline or the line under the stat cards, and closes with Escape or a sticky "Back to the towns". The demo opens directly on it at `?view=next&demo&numbers`.
- **Six new curated numbers.** Happiness is measured every week; sales exclude rent; town hall income means four named taxes collected; help paid to families includes the six-week welcome payment; the richest tenth's and poorest half's wealth shares are counted every 5 weeks and labelled with their last count. The recorded demo now includes all six. Missing measurements stay missing, and comparisons remain neutral, including when both towns owe money.
- **Review.** Every task had an Opus review and a fix round, followed by Codex's remaining Task L fixes and review of those fixes and the whole slice. No new Critical or Important source issue was found. The final browser checks needed no further source fixes.
- **Checks.** 583 frontend tests pass; 609 backend tests pass with one expected failure. ESLint, Vite build and Ruff pass. Browser checks covered the sheet, Run, Set up and classic dashboard at 1280px and 390px, plus four-town tables at 390px with scrolling confined to each card. A real two-town run with 200 households each completed one year, extended another year, updated the open sheet, paused for a Town B rule change, and showed it from the next week. No browser errors or live-backend errors; one development-proxy `EPIPE` occurred on the classic dashboard's opening connection. Details and mockup notes: [browser verification](docs/reviews/2026-09-25-frontend-redesign-slice3-browser-check.md).
- **Parked and deferred.** K-M9: `homelessHouseholds` reads 0.0 when housing diagnostics are absent, so an unusual run could falsely say nobody lost their home; a backend null-when-absent change remains outside this slice. K-M7: the neutral grey money-in/out key and blank space under the cash card at 1280px remain cosmetic follow-ups. The tile cache still assumes append-only ticks; a repeated week in a legacy RESET recording can leave its scale stale until the next week. Earlier slice-2 deferrals remain parked, including the AI mayor and making the new frontend the default.
- **OpenWiki.** A refresh is due once this branch reaches `main`; generated pages were not edited.

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
