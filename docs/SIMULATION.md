# Simulation Guide

This document describes the current runtime behavior of EcoSim as implemented in the Python code.

## Overview

EcoSim is a tick-based agent-based model. One tick is approximately one simulated week, and the default year length is 52 ticks.

Active actors:

- Households: workers, consumers, patients, tenants, savers, borrowers, and firm owners.
- Firms: producers and employers in Food, Housing, Services, Healthcare, and internal/public-work paths.
- Government: tax collector, transfer provider, policy actor, baseline-firm owner, subsidy source, and fiscal-pressure tracker.
- Bank: optional credit and deposit channel. The standard large-economy setup creates a bank; the engine can still run without one.

The default dashboard setup creates households, four baseline safety-net firms, a queue of private firms, a government, and a bank. Baseline firms are active immediately. Private Food and Services firms are queued during warmup and activated afterward; Housing and Healthcare currently use a baseline-led provider model at startup.

## Runtime Stack

```text
frontend-react
  -> WebSocket /ws
backend/server.py
  -> SimulationManager
backend/economy.py
  -> Economy.step()
backend/agents.py
  -> HouseholdAgent, FirmAgent, BankAgent, GovernmentAgent
backend/config.py
  -> SimulationConfig defaults
backend/policy_schema.py
  -> runtime and LLM policy schema
```

## Initialization

The WebSocket `SETUP` command is validated by `SetupConfig` in [`backend/server.py`](../backend/server.py). Supported setup fields are:

- `num_households`: default `1000`, backend-valid range `3` to `100000`
- `num_firms`: default `5`, backend-valid range `1` to `1000`
- `seed`: optional integer seed
- `enable_llm_government`: optional boolean
- `disable_stabilizers`: boolean
- `disabled_agents`: any of `households`, `firms`, `government`, `all`

The large-economy factory lives in [`backend/tools/runners/run_large_simulation.py`](../backend/tools/runners/run_large_simulation.py). It creates:

- four baseline firms, one each for Food, Housing, Services, and Healthcare
- queued private firms, distributed primarily to Food and Services in the current startup model
- households with distributed skills, ages, and starting cash
- seeded initial doctors for the baseline Healthcare firm
- firm ownership links from firms back to households
- a bank with cash reserves scaled by household count
- a government with starting cash scaled by household count

## Tick Lifecycle

The authoritative lifecycle is `Economy.step()` in [`backend/economy.py`](../backend/economy.py). The default `legacy` sequence is:

1. Refresh warmup state, activate queued firms after warmup, reset per-tick telemetry, apply post-warmup stimulus if active, refresh subsidy caps, reset bank telemetry, apply random shocks, reset healthcare tick state, lock doctor health where configured, and enqueue healthcare requests.
2. Build market views and unemployment statistics.
3. If government stabilizers are enabled, update loan commitments, execute authorized bailouts, and maintain or deauthorize public-works capacity.
4. Firms refresh one shared health snapshot, consider long-term capital loans, plan production/labor, record working-capital diagnostics, plan prices, apply price/rent stabilization caps, plan wages, disable ordinary labor-market hiring for Healthcare, and plan capital investment.
5. Issue working-capital bridge credit where enabled and eligible.
6. Process firm investment loan requests through the bank.
7. Enforce the active minimum-wage floor in firm wage plans, then snapshot the posted offers. `Economy.get_posted_wage_offers()` returns that snapshot (private firms by default; `include_baseline=True` adds government baseline firms), and `FirmAgent.get_wage_offer_floor(benefit)` returns the floor each firm's offer rule applies: `max(minimum wage, 1.5x benefit)` for annual-review firms and private Food-type firms on the weekly rule, the minimum wage alone for baseline, healthcare and weekly-rule Services firms. Neither changes any offer.
8. Households update education status, job-search cooldowns tick, labor plans are created, and unemployment guardrails normalize search/reservation state.
9. If the bank exists, households may request consumption loans and the bank may originate them.
10. Labor matching runs through the configured matcher, records hire/layoff events, and records failed-hiring regime events.
11. Firms and households apply labor outcomes; firm rosters are synchronized with household employment state.
12. Firms produce goods/services and update expected sales.
13. Household wages/CEO pay, progressive wage tax and benefits settle once. Existing capital-investment proceeds reach households. Households plan shopping from actual take-home receipts and current liquidity, then withdraw accessible deposits. Performance mode reuses seller choices while refreshing monetary budgets every week.
14. Food, Services, and tradable goods clear through the goods market.
15. Services firms may expand employee-slot infrastructure; bank-backed service infrastructure loans may be offered.
16. Housing rental market clears, repairs apply, housing firms consider unit expansion, and bank-backed housing expansion loans may be offered.
17. Miscellaneous revenue is redistributed through the internal misc firm path.
18. Healthcare firms process queued visits up to effective capacity; households pay with cash/deposits, subsidies, or medical loans where available. With `CONFIG.households.healthcare_food_first_reserve` (default on; off is main's behavior), a queued household's weekly consumption budget holds back the visit's expected out-of-pocket cost (`Economy.expected_healthcare_out_of_pocket_all()`) after minimum food: the claim order is rent and loan installments, minimum food (priced at the highest posted price among Food sellers with stock, or among all active Food firms when none have stock), the visit (capped at what is left), then the rest, on every payment sequence. The budget is the flag-off budget capped at liquidity less the reserve. Nothing is charged before service.
19. Government assesses firm profit/property taxes from sales. Household tax and benefit totals retain the earlier assessment.
20. Firms receive sales revenue, pay taxes, and apply price/wage updates.
21. Bank loan repayments are collected after wages and sales are available.
22. Household purchases, remaining medical fallback payments and consumption receipts are applied; income already received is skipped.
23. Remaining firm fiscal results settle. Household wage taxes and benefits remain in weekly telemetry without a second cash transfer.
24. The treasury pays a week of interest on public debt to the bank. Bank deposit rates update, household deposit sweeps/withdrawals run, credit scores update, and settled loans are cleaned up.
25. Government infrastructure, technology and social spending are applied and routed back into circulation where appropriate. The treasury then borrows any cash shortfall from the bank or repays debt from cash above its working balance. The misc bond buy runs only while no debt is owed.
26. Investment taxes are collected and fiscal pressure/spending efficiency are updated.
27. Household wellbeing updates run, with lower cadence in performance mode.
28. Bankrupt private firms exit and eligible new firms enter under-served sectors.
29. If rule-based government stabilizers are enabled and the LLM government is disabled, automatic government policy adjustment runs.
30. Statistics, health diagnostics, firm-distress diagnostics, and sector-shortage diagnostics update.
31. Firm profits and healthcare worker bonuses are distributed to household owners/workers, household ledgers finalize, affordability telemetry updates, and the simulation clock advances.

The server applies pending runtime config changes and completed LLM decisions only at safe boundaries around this tick loop.

## Households

Households maintain cash, bank deposits, skills, age, employment state, wage, health, happiness, morale, expectations, preferences, inventory, medical status, debt, and history used by the live UI.

Key current mechanics:

- A household can work only if `health >= 0.10` and it is not in the student phase of medical training.
- Unemployed, work-capable households are normalized into active job search by default through `ECOSIM_FORCE_UNEMPLOYED_SEARCH=1`.
- Long-term unemployed reservation wages are clamped to an observable market anchor by default after `ECOSIM_UNEMPLOYED_CLAMP_TICKS=8`.
- Employed households can perform staggered on-the-job search after warmup. If a switching attempt fails to match, the household keeps its prior employer.
- Matching wage premiums in the current matcher are `25% * skill_level` plus `3%` per year of category experience, capped at `30%`.
- Skill grows on the job once a year: `skill_growth_rate * (1 - skill)` per week worked, credited every 52 ticks. With `CONFIG.households.skills_dynamics` (default on) skill also wears off while out of work, at a fixed `skill_loss_per_year_out_of_work` (default 0.04 skill units per year, applied weekly, `skill = max(floor, skill - a / 52)`), and never below the household's week-1 skill (the floor); paid education raises the floor. `CONFIG.households.skills_weekly_learning` (default off, read only with `skills_dynamics` on) credits learning weekly instead of yearly. With `skills_dynamics` off, skill never falls (as before).
- Default consumption planning uses actual take-home wage/benefit receipts, personality-driven saving behavior, current cash (including approved credit and released capital proceeds), and accessible deposit liquidity. Cash received after shopping, including end-of-week dividends, enters the following week's wallet. See [the timing contract](reviews/2026-09-28-household-income-timing.md) for the default and cached-plan boundaries; named payment experiments retain their specified sequences.
- Health, happiness, and morale update from food, housing, services, employment, wage satisfaction, healthcare, poverty stress, and government social multipliers.
- Medical training has student/resident/doctor stages. Residents and doctors add healthcare capacity; doctors are seeded during large-economy initialization.

## Firms

Firms plan before state mutations are applied. The common pattern is:

1. compute a shared health snapshot
2. plan production and labor
3. plan price
4. plan wage
5. apply labor, production, sales, taxes, price, and wage changes later in the tick

The shared firm-health snapshot includes cash runway, smoothed profit margin, sell-through rate, inventory weeks, unfilled-position streak, turnover, survival mode, burn mode, and a category wage anchor.

Private firm behavior includes:

- inventory-aware production and pricing
- sector-specific pricing paths for generic firms, housing, healthcare, baseline firms, and services
- wage planning that uses the active minimum-wage floor, unemployment, benefit levels, firm health, and hiring pressure
- survival and burn modes under distress
- staged layoffs and hiring gates
- capital investment, service infrastructure, housing unit expansion, and bank/government-backed lending paths
- bankruptcy when cash falls below the configured threshold or distress persists through the zero-cash guard; on the legacy payment sequence a firm can exit overdrawn, and that negative cash is paid before it is removed (a PublicWorks firm's by the treasury, a private firm's by its lenders, the bank only from cash above required reserves; `market.settle_legacy_exit_deficit`, default on)
- new firm entry into under-served sectors

Baseline firms are protected from bankruptcy and provide a safety-net floor. Public works can create additional baseline-style capacity when enabled by policy.

**v1.9 - Legacy exit-deficit accounting (#57 accounting split, 2026-10-22).** Before: removing an overdrawn firm on the legacy payment sequence discarded its negative balance and increased total money by that amount. After: with `market.settle_legacy_exit_deficit=True` (default), its lenders bear the deficit in proportion to their outstanding claims; with no lender the bank bears it, up to cash above required reserves, and the treasury pays the remainder. PublicWorks deficits go entirely to the treasury that capitalized those firms. The treasury share enters the same tick's spending, fiscal balance and budget pressure; contractual loan write-offs remain separate. `False` restores the prior accounting. Exit eligibility stays as on main: all registered baseline providers remain protected, while private Housing and Healthcare firms may exit. There is no recurring provider bailout or baseline retirement in this change. Gradual retirement is separate proposal work, not implemented here.

## Labor Market

The default matcher is `fast`; the legacy matcher remains available for comparison.

Configuration:

```env
ECOSIM_LABOR_MATCH_MODE=fast
ECOSIM_COMPARE_LABOR_MATCH=0
ECOSIM_COMPARE_LABOR_MATCH_STRIDE=1
ECOSIM_LABOR_DIAGNOSTICS=0
ECOSIM_LABOR_DIAGNOSTICS_STRIDE=10
```

Current matching behavior:

- incumbent jobs are retained unless a layoff or successful job switch changes the relationship
- work-ineligible households are excluded
- job seekers are filtered by reservation wage and medical-only status
- candidate priority favors higher skill, with deterministic tie-breaking
- actual wages include skill and category-experience premiums
- unfilled vacancies record diagnostic reasons such as no searchers or reservation wages above offers

The warehouse and metrics path expose labor diagnostics such as unemployed-not-searching, wage-ineligible seekers, forced-search adjustments, and reservation-clamp adjustments.

## Goods, Housing, And Healthcare

Goods market:

- Food and Services clear through the goods-market path.
- Services are treated as current-tick capacity rather than stored household inventory.
- Households use bounded awareness pools, price/quality preferences, and stochastic noise when choosing firms.
- Sector subsidies reduce household payment when the government has remaining subsidy budget.

Housing:

- Housing clears through a rental-market path separate from ordinary goods clearing.
- On the default (legacy) payment path an existing tenant pays the Housing firm's current posted rent each week (`labor_market.rent_tracks_posted_price`, default true), and planning reserves that same amount before shopping. Named payment arms renew leases against the posted ask on a 52-week term instead. On both paths collected rent counts as the Housing firm's revenue for profit tax and dividends (`labor_market.rent_booked_as_revenue` on the legacy path).
- Rent affordability, vacancies, evictions, repairs, occupancy pressure, rent stabilization, and housing expansion are tracked.
- Housing unit expansion can use self-financing or bank loans depending on state.

Healthcare:

- Healthcare is queue-based and non-storable.
- Households enqueue healthcare requests based on health status and planned visit schedules.
- Healthcare firms process visits up to labor-based capacity, with resident/doctor capacity differences.
- Healthcare firms do no R&D (unconditional owner decision). By default, visit pricing uses the doctors' wage bill divided by all visit slots plus a 15% after-tax margin; baseline warmup and capital investment keep their existing rules.
- `CONFIG.firms.fix_healthcare_price_covers_payroll` is an experimental switch, **False by default** in library config and inherited by server sessions and town policy presets. Explicit `True` spreads payroll over smoothed requests capped at slots, limits weekly price changes to 15%, prices visit slots during warmup and excludes healthcare capital purchases. The prior evidence panel found worse household access and wellbeing with this switch on; it is not a household-safe default and adds no subsidy.
- Payment can use cash, accessible deposits, government subsidy, or medical loans.
- Denied visits and completed visits are emitted as healthcare events.

## Government

The government owns the policy surface implemented in [`backend/policy_schema.py`](../backend/policy_schema.py). It collects taxes, applies transfers and subsidies, manages public works, runs fiscal investments, tracks fiscal pressure, applies bailouts, and records policy state for the UI and warehouse.

Policy choices can come from:

- manual runtime controls in the frontend
- automatic rule-based stabilizers
- the live LLM government when enabled
- offline LLM runners and benchmark tools

When the live LLM government is enabled, deterministic rule-based policy adjustment is bypassed so policy choices come from the model plus mechanical validation and application code.

Public debt (`government.public_debt_enabled`, default on; with it off the treasury behaves exactly as before):

- **Borrowing.** After its weekly spending, a treasury with negative cash borrows from the bank, up to the bank's lendable cash (reserves above the reserve requirement), and only when `BankAgent.can_lend()` is true. `public_debt_borrow_target` sets how much: `"buffer"` (default) borrows back to the working balance below, and while debt is owed also tops cash up to it; `"zero"` borrows back to $0 of cash and stays a valid setting. The loan moves bank reserves to the treasury, so no money is created. Any part the bank cannot lend stays as negative treasury cash. Without a bank nothing is borrowed.
- **Legacy only.** The `income_first` and `income_late` sequences ration outlays to free treasury cash, so their treasury never goes negative and never borrows.
- **Interest.** Each week debt is owed, the treasury pays `public_debt` x (the bank's current lending rate + `public_debt_risk_premium` x annualized debt/GDP) / 52 to the bank, before the bank pays deposit interest. Nothing changes the bank's rate during a run yet (3% by default), so the debt rate moves only with debt/GDP. The reported rate is 0 with no debt.
- **Repayment.** While debt is owed, treasury cash above `public_debt_cash_buffer_weeks` (1) weeks of last week's government spending repays principal, and the misc bond buy is skipped. Turning the flag off mid-run stops new borrowing only: existing debt keeps paying interest and is repaid from surplus. Borrowing, interest and repayment also run with `stabilization_disabled`.
- **Bank books.** The loan is the treasury's `public_debt` and the bank's `public_debt_held`; `BankAgent.loan_book`, `total_assets` and `equity` include it. The deposit-rate rule's thin-loan-book test reads `loan_book`, so a bank holding public debt pays a different deposit rate than one with the same reserves and no public debt.
- **Where the interest goes.** The bank pays depositors its deposit rate (a fraction of a percent a year) and has no owner, dividend or expense, so most interest stays in reserves, where it is lent back to the treasury while the deficit lasts.
- **The lending limit.** Loan proceeds are spent and much of the money comes back as deposits, so a bank can lend more over time than its starting reserves; the limit binds only once reserves fall to the reserve requirement. In a long deep-deficit run reserves fall in every seed and the limit can bind (see the CHANGELOG entry).
- **Spending and reporting.** Spending gates still read cash: the LLM government's spending guard (fires on negative cash or debt/GDP >= 1), the sector-subsidy cap (at most 2% of cash), public-works startup affordability and the cash-limited programs. So the government may spend while borrowing. Under `"zero"`, cash is about $0 when the cash-limited programs run, so they spend nothing; under `"buffer"` (the default) the working balance is there for them. The LLM government may also cut wage and profit taxes while borrowing. Spending increases and tax cuts share one guard: an unfunded overdraft (cash below zero after financing) or debt/GDP >= 1. With the flag off that guard is cash below zero, as on main. Reporting reads the net position, cash minus public debt (`fiscal_guards.treasury_net_position`): the dashboard fiscal balance, `deficit_ratio`, the warehouse `fiscal_stress_score`, the LLM government's fiscal mode, its prompt (debt, interest and rate, borrowing and repayment, the 13-week debt trend), its policy memory (change in debt and net position after each decision) and the run summaries. The rule-based comparison government (`run_government_control_compare.py`) reads the net position for its austerity rule and adds no fiscal rule of its own. With the flag off and no debt owed, the prompt, memory and summaries show no debt lines, as on main. Interest moves treasury cash to bank reserves and so to bank equity; it does not remove money from the economy.
- **Town Run screen.** `curated.townHallCash` is treasury cash minus public debt, so the existing red IOU and "owes" amount show a net debt even when borrowed money leaves cash in the bank. With borrowing off and no debt owed it is the same cash projection as main. Fiscal balance is the change in net position, so borrowing and repayment are financing rather than revenue or spending. No classic-dashboard UI or separate financing frame fields are added (owner-approved 2026-10-22).

## Bank And Credit

The standard dashboard economy includes a `BankAgent`. The bank tracks cash reserves, deposits, active loans, lending capacity, credit scores, interest income, deposit interest, defaults, repayments, and loan loss provision.

Current bank-integrated paths include:

- household deposit sweeps and withdrawals
- deposit interest, constrained by bank profitability/reserves
- firm capital loans
- service infrastructure loans
- housing expansion loans
- working-capital bridge credit
- consumption loans
- medical loans
- repayment collection and default handling
- firm and household credit score updates

The engine keeps fallback paths for runs where `bank` is `None`.

## LLM Government

The LLM government observes compact macro, sector, fiscal, shortage, and prior-decision context. It does not receive raw household or firm records. Its proposed changes are validated against `policy_schema.py`, rate-limited, grouped where needed, and separated into accepted/rejected changes.

Default scheduling is configured in `CONFIG.llm`: decisions occur on an interval, after warmup/start gates, and are run outside the tick phase in a background task. Completed decisions are applied before a later tick begins.

## Warehouse And Diagnostics

When persistence is enabled, the server records:

- run metadata and policy config
- tick metrics and sector metrics
- firm snapshots
- sampled household snapshots
- tracked household history
- labor and healthcare events
- policy actions
- decision features
- tick diagnostics
- sector shortage diagnostics
- regime events
- full LLM government decisions

The live decision context is also available in memory through `GET /decision-context/live?session_id={session_id}`, even before warehouse batches flush. The session ID is sent to the WebSocket client in the initial `SESSION` message.

## Important Defaults

| Setting | Current default |
|---|---|
| Tick length | 1 week |
| Ticks per year | 52 |
| Warmup ticks | 10 |
| Setup households | 1000 in frontend/server default |
| Setup private-firms setting | 5 per setup input, redistributed by factory rules |
| Labor matcher | `fast` |
| Household snapshot stride | 5 warehouse ticks |
| Direct local warehouse | disabled unless `ECOSIM_ENABLE_WAREHOUSE=1` |
| Docker warehouse | enabled SQLite runtime volume |
| Live LLM government | disabled by default |
| Tax lever max LLM step | 0.05 per decision |

## Observed inflation and annual private pay

`CONFIG.inflation.enabled` (default `True`) switches the [inflation model](reviews/2026-09-28-inflation-model.md) (rules doc v1.5). When on, the economy observes opening posted prices each post-warm-up week, right after the random shocks and before any firm plans, into a bounded consumer price index (`Economy.consumer_prices`; metrics `consumer_price_index`, `inflation_annual`, `inflation_annual_available`, `mean_real_wage`; live frame `inflation`, `avgRealWage`). Legacy private Food/Services firms (non-baseline, post-warm-up; `FirmAgent.annual_wage_control`) replace the weekly wage rule, the revenue-ratio wage cut and the 50-tick continuing-worker raise with a firm-specific 52-week review (`Economy.wage_reviews`): observed inflation since the last review, capped at 10% and limited by revenue after debt service and an eight-week cash payroll reserve, plus a 2% distress cut at most once a year. Offers keep the policy minimum wage, the config floor and the 1.5x benefit floor. Phase 9 applies the review's contract change to next week's contracts and both employment mirrors; current earned payroll remains frozen. When off, the index stays at 100 (`inflation_observed` 0) and the older weekly rules and the disabled-stabilizer 2%/week price escalator apply. See [the runnable scenarios](testing/inflation-scenarios.md) for definitions, assumptions and limits.
