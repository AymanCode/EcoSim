# Demand diagnostics: brief for a dedicated thread

Date: 2026-10-09. Owner: Ayman. Purpose: build the tooling to answer "where is demand going, what are households spending on, and why?" for the default EcoSim economy, then run it and report. EcoSim does not have this kind of diagnostic yet; the scenario runners under `backend/tools/checks/` test single mechanisms, not the flow of spending through the whole town.

## Why now

With the job-switcher side door closed, inflation on, income paid before shopping, and bank expansion loans offered only to Services firms with plenty of unmet demand (all owner decisions, see CHANGELOG.md Unreleased entries from 2026-09-28 to 2026-10-02), the default 1,500-household legacy run settles near 40% unemployment after warm-up with the town hall deep in deficit from uncapped unemployment benefits. The owner reads this as a demand trap rather than a bug, and wants to understand demand before deciding on a stimulus lever (the old rule "while unemployment is at least 10%, fund every Services firm to expand" is planned to become an explicit government policy an AI mayor can choose; it is not built yet).

Known facts to start from (diagnostics of 2026-10-02, scripts kept in the session scratchpad, numbers in CHANGELOG and `docs/evals/2026-10-02-seller-concentration/`, `docs/evals/2026-09-29-inflation-port/`, `docs/evals/2026-09-29-remediation-before-after/`):
- Wage rejection is not the cause: posted vacancies fill at 100%; median reservation wage ≈ 28 vs median offer ≈ 53.
- Services firms are sold out and turn away more customers than they serve (ticks 11-100) but are capped at worker slots; slots grow only through bank loans.
- Households now reserve rent, loan installments and minimum food before shopping; preferences split the remainder.
- Baseline (public) Food firms shed ~680 warm-up workers by tick 65.
- Prices roughly double in the first year after warm-up; nominal wages rise ~27% in ticks 41-100 and then only at annual reviews.

## What the diagnostic must answer

For a default legacy run (1,500 households, 10 firms per category, seeds 42/7/11, 300 ticks; build the economy exactly as `backend/tools/benchmarks/regression_snapshot.py` does), by tick windows 11-40, 41-100, 101-200, 201-300:

1. **Where the money comes from.** Household income by source per tick: wages, unemployment benefit, other transfers, dividends/CEO pay, loan proceeds, capital-recycle proceeds. Split by employed / unemployed. (`HouseholdAgent.last_tick_ledger` categories plus the per-tick income application in `Economy._settle_legacy_income_and_plan_shopping` / `_apply_household_income`.)
2. **Where it goes.** Spending per tick by category (food, housing goods, rent, services, healthcare, loan repayments, deposits) and the planned-vs-actual gap: how much of the planned budget was not spent (no stock, price cap, seller not in the household's awareness pool, budget exhausted) — `last_food_spend`, `last_housing_spend`, `last_services_spend`, `last_purchase_breakdown`, and the clearing's unmet-demand records (`services_unmet_by_firm`, `record_firm_unmet`, lost sales fields).
3. **Why.** For the median household, a poor household (p10 cash) and a rich one (p90): the budget derivation each week — income, reserves (rent, installments, minimum food), drawdown from savings, category fractions, the food satiation cap, the seller choice (awareness pool, price, quality, tie-break), and what was actually bought. Produce a readable "week in the life" trace for each archetype at ticks 30, 80, 150, 250.
4. **Demand vs supply by sector.** Per category: units demanded (planned), units sold, units turned away, capacity (Services slots × output per worker; Food inventory + production), posted price, and the share of households that bought anything in the category. Where is unmet demand concentrated (which firms, what prices)?
5. **The trap mechanics.** How much weekly spending the unemployed add versus the employed; what share of Services demand comes from benefit income; how spending would change if 100 unemployed people got jobs at the median offer (a counterfactual computed from the measured propensities, not a new simulation rule).
6. **Money stock.** Where cash accumulates over time (households by decile, firms by category, government, bank reserves) and whether firm cash is idle (not invested, not paid out).

## Deliverables

- `backend/tools/checks/run_demand_diagnostics.py`: a CLI (`--households`, `--ticks`, `--seeds`, `--payment-sequence`, `--out`) that runs the economy, collects the above per tick with no engine changes (wrap or read existing state; if an essential number is not observable without an engine change, add a read-only telemetry field and document it in CHANGELOG with BEFORE/NOW), and writes CSV + a Markdown report with the window tables and the three household traces.
- Contract tests for the collector (small economy, deterministic) under `backend/tests_contracts/`.
- `docs/testing/demand-diagnostics.md` explaining how to run it and read it.
- A first run saved under `docs/evals/<date>-demand-diagnostics/` with a plain-language README answering the six questions.
- A CHANGELOG entry (owner's standing rule: every change states what existed BEFORE and what exists NOW).

## Constraints

- No engine behavior change in this thread. If the diagnostic reveals a defect, write it up with evidence; do not fix it here.
- Runs small and sequential (1,500 households); the owner's laptop is usually busy. Ask before anything larger.
- Keep the three golden snapshots matching (`benchmarks/results/golden_*.json`, compare commands in `backend/tools/benchmarks/regression_snapshot.py` usage); telemetry-only additions must not move them.
- Owner positions to respect: high unemployment is acceptable if it is the economy; firm-entry seed cash and demand shocks are intentional outside money (recorded in `external_injection_total`); the job-switcher fix and inflation stay on.
- Follow `CLAUDE.md`: wiki-first navigation (`openwiki/quickstart.md`, `openwiki/where-to-change-what.md`, `openwiki/backend/agents-and-markets.md`, `openwiki/backend/tick-lifecycle.md`), source authoritative; the generated wiki is stale in places after the recent work.
