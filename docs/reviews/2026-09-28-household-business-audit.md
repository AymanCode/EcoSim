# Household and business audit — plain-language first pass

**Port note (2026-09-29):** copied unchanged from the 2026-09-28 session; its observations were measured on `17d5c0b`, before the agents/economy remediation. Fresh scenario results on the remediation code are in `docs/evals/2026-09-28-household-income-timing/scenarios/report-2026-09-29.md`.

**Historical baseline:** this audit records the behavior before the subsequent [income-before-shopping correction](2026-09-28-household-income-timing.md). The saved original observations remain intact. The current default now pays household wages and benefits before planning shopping.

Date: 2026-09-28. Scope: the current default `legacy` payment rules. Simulation behavior was inspected and exercised; this work adds experiments and documentation without changing those rules.

## How a household works

A household is approximately one worker with a wallet, savings, debts, needs and personal preferences. It is not a detailed family model.

Each week it considers work, plans shopping, may request credit, pays obligations and receives income. **The timing matters:** shopping is planned before ordinary wages and benefits arrive. Rent and registered loan payments also happen before ordinary household income is credited. Food, health, housing and employment then affect wellbeing.

| Situation | Current behavior |
| --- | --- |
| Comfortable cash balance and a job | Plans spending from a fraction of expected income plus some savings. It does not spend its whole wallet automatically. Preferences, prices, available sellers and supply affect purchases. |
| Small cash buffer | Shopping is capped by available cash plus 90% of deposits. It can draw down savings faster when its income-based budget is low. |
| Zero cash but bank savings | Plans can use part of those savings. Actual withdrawals still depend on the bank having cash. |
| Zero cash, no savings, payday later | The shopping plan is zero. Our complete-week test receives wages and emergency credit but buys no goods that week. Stored food, if present, could still feed the household. |
| Unemployed | Normally searches for work and can receive the base unemployment benefit. Searching does not guarantee a vacancy, suitable wage or hire. |
| Employed but broke | Being poor does not by itself qualify the household for the unemployment benefit. |
| Needs emergency credit | Low cash can trigger a request. Credit score, existing debt and bank funding can block it. An approved loan increases debt; it is not earned income. The current shopping plan is not rebuilt after the loan arrives. |
| Cannot pay rent | The default rule ends the tenancy immediately. The household can seek an affordable vacant unit in the same week; our one-unit test has no alternative. |
| Can pay only part of a debt bill | The collector takes available cash and leaves the balance outstanding. A positive partial payment currently improves credit just like a full payment. |
| Cannot get enough food | Health deteriorates faster. At health below 0.10, the household cannot search for work. Cash running out does not itself remove the household from the simulation. |
| Needs healthcare | Joins a care queue. Treatment depends on capacity and funding: subsidy, cash, deposit withdrawal or medical credit. Unfunded visits wait. This branch was inspected in source but is not yet a focused scenario in the new runner. |

The spending plan is a ceiling, not a receipt. The cash balance also excludes bank deposits, and the existing itemized cash ledger misses some flows. Actual before/after balances are the stronger evidence when checking a payment.

## How businesses and the other actors interact

| Actor | What it does | What matters when money is tight |
| --- | --- | --- |
| Food business | Uses sales and inventory to plan production, staffing, prices and wages. Production depends on workers and capacity. | In our controlled case, sales dropping from 40 units to zero reduces planned production to zero. Hiring is a separate decision; cash alone does not guarantee expansion. |
| Services business | Sells service capacity supplied by workers. Unsold service capacity is not stored for later sale. | Payroll can continue while demand is weak. The new business demand fixture specifically covers food; services deserve their own case. |
| Landlord | Rents a finite number of units and collects weekly rent. | Default affordability and liquidity checks can evict the household before payday. Rent reaches the landlord when paid. |
| Healthcare business | Serves queued patients subject to staffing/capacity and funding. Completed visits restore health. | Insufficient funding or capacity can delay care, even when the household needs it. |
| Bank | Holds deposits, funds loans, collects repayments and updates credit scores. | Credit is conditional and withdrawals require bank cash. In our tests, low credit, existing debt and an empty bank each independently prevent emergency borrowing. |
| Government | Sets policy, collects taxes, plans unemployment benefits and funds other programs. | In the default transfer planner, base unemployment benefits are not capped by treasury cash. Program-specific funding rules differ; a negative treasury balance is not a fully modeled sovereign debt market. |

Businesses can have negative cash. Our payroll fixture starts a firm at $0, pays two workers $40 each, and leaves the firm at **−$80**. Its cash debit matches the workers' receipts. An unprotected business closes below the configured −$1,000 threshold or after a sustained zero/negative-cash streak; its workers lose their jobs. Registered baseline businesses are protected from that exit rule. The baseline flag does not establish public ownership.

## What the first experiments establish

The [runner guide](../testing/agent-scenarios.md) explains how to rerun individual questions. The [saved observations](../evals/2026-09-28-agent-scenarios/report.md) include exact starting states and results.

The first review priorities are:

1. **Shopping and payment timing.** The full-week zero-cash case confirms that wages and emergency borrowing can arrive without enabling purchases that week.
2. **Rent before payday.** An immediate cash shortfall can cost a household its tenancy even with wages due.
3. **Partial debt payments.** The current credit-score treatment does not distinguish a positive partial payment from a full scheduled payment.
4. **Unfunded payroll.** Default firms can pay workers by going into negative cash. The alternative payment sequences have different funding rules and need separate comparisons.
5. **Incomplete cash explanations.** Consumption-loan proceeds and recycled capital spending are among the default flows omitted from household ledger categories. The runner exposes the difference as `cash_change_not_itemized`.

These are confirmed mechanisms and reporting gaps, not an established explanation for the five-year depression. A small town is useful for tracing behavior; calibration still needs representative populations and multiple seeds after the intended rules are settled.

## Evidence and remaining coverage

The runner contains eleven scenarios, including a complete one-household payday week and a normal 24-household town over 24 weeks. The town starts with four businesses and retains normal warmup, policy, shocks, lending and firm-entry behavior. Tests also check deterministic replay and preservation of the caller's configuration and random state.

Focused cases still needed for a deeper audit: healthcare affordability and queues; applicants versus real vacancies and skills; business borrowing and expansion; service-sector demand; taxes and take-home pay; ownership and dividends; and the `income_first`/`income_late` sequences. No simulation rule was changed to obtain a passing result.

Source owners: `Economy.step`, `_batch_plan_consumption`, `_batch_apply_household_updates`, `_clear_housing_rental_market`, `_process_healthcare_services`, `_collect_bank_loan_repayments`, `_handle_firm_exits` and `_recycle_capital_investment` in `backend/economy.py`; household labor/credit, firm planning/payroll, bank and transfer methods in `backend/agents.py`; payment defaults and exit thresholds in `backend/config.py`.

Validation: the saved seed-1337 run passes all 30 mechanism checks. All 73 focused tests pass across the runner, household behavior, banking, deposits and loan settlement; Ruff is clean. Seeds 7 and 42 also passed the scenario checks during development. The saved evidence includes source hashes, verified against the delivered runner and simulation files. Generated OpenWiki refresh remains deferred until this work reaches `main`, following the current branch handoff.
