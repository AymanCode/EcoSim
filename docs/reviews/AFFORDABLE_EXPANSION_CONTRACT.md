# AFFORDABLE-EXPANSION-01

Owner directions (2026-10-26): exclude households' unaffordable orders from demand; delegate the household planning/math fix to another 6.1 Sol; allow expansion financing and keep its computation efficient. This continues Services pricing -> repayments -> investment -> delivered output. PR66 is preserved separately. Reference baseline is PR66 head cca042a on authoritative main d71485e; rules v1.17 precede implementation.

## Selected behavior and ownership

Two connected changes, measured separately before their combination:

1. **Household affordability (delegated Sol):** trace the live batch budget, forecast and liquidity inputs, allocations and funded named settlement. Correct demonstrated double counting or budget overshoot. Before a purchase can inform a firm, bound it by the household's resources available at that shopping boundary and actual price/subsidy funding. Do not use future funded income, count the same resources against several failed orders, or erase household hardship when no purchase can be funded. A money-limited purchase creates no capacity-shortage signal; an affordable stockout can. Zero opening cash with subsequently funded `income_first` income differs from `income_late` income held until after shopping. Preserve current timing, seller pools, preferences, quality/price response, Food/care/rent/debt priority and no re-shopping. Normal/performance paths must both respect current resources without reducing cadence. Agent uses only declared observations.
2. **Services funding (parent):** retain existing space eligibility, quotes, slot gains, cooldowns and lender policies. Allow available firm cash to contribute to a qualifying named-sequence project while protecting an operating reserve derived from the existing personality-dependent expansion runway, payroll and scheduled debts. Bank finances the remainder, with unchanged underwriting against all existing plus proposed dues. Funding and project delivery are atomic: no partial contribution or space if required financing fails. Credit actual recipients once for the full project cost; book only borrowed principal/interest as debt. Cash funding alone requires no lender claim. Generic capital/R&D, baseline retirement, wages, household choice and general banking redesign remain outside scope.

The $2,000/$5,000 split of a $7,000 project discussed with the owner was illustrative, not a selected fixed fraction. Use arithmetic on existing cash/obligations and existing credit functions; no new random draws or per-household search. Retain the old payment sequence's financing behavior unless a common planning arithmetic defect necessarily applies there, which must be documented separately.

## Writer and resource boundaries

- Household budget and category orders: `Economy._household_consumption_budgets`, `_batch_plan_consumption`, `payment_behavior.planning_inputs`, `HouseholdAgent._plan_category_purchases`. Trace scalar/batch/cache callers before editing.
- Goods acceptance and observable unmet demand: `PaymentGoodsMarket`; `PaymentBook` alone settles customer cash, subsidy, clearing and seller payables. Existing household needs and completed purchases remain authoritative for wellbeing.
- Expansion decision/funding/delivery: `Economy._maybe_offer_long_term_capital_loan`, `_offer_service_infrastructure_loans`, existing capital/misc recipient routing, `FirmAgent._add_service_worker_slots`. One contributor debit, one lender debit for the borrowed part, one recipient credit for the total cost, one capacity update.
- Registered loan underwriting and claims remain owned by `payment_loans`; no relaxation of the 35% rule, hidden new Treasury fallback or invented creditor.
- Parent owns common rule revisions/integration and finance symbols. Child owns household symbols and focused tests in an isolated checkout. Shared-file changes are merged by symbol. Child does not edit shared rules or Services finance symbols.

## Acceptance and evidence

Households: no money/no quantity; partly affordable plans; actual versus forecast wages in both named arms; exhausted/unavailable deposits and subsidies; actual quote above posted quote; stockout with available funds; multiple sellers cannot reuse one budget; priorities and funded payment/claim reconciliation; no new seller search. Trace planner through real settlement, not only hand-built orders.

Finance: fully cash-funded, mixed and loan-only projects; adequate post-purchase reserve; active debt counted once including paid-off/final balance; required-loan rejection leaves all balances and capacity untouched; existing staffed/sustained-demand guards; actual loan principal, funder and recipient totals; installation resets evidence; both named sequences and unchanged old-sequence behavior.

Run focused tests and affected integration tests, then the default backend gate after integration. Compare the household change, financing alone and the combination against the same baseline using matched initialization/seeds in normal mode. Lead with `income_first`, then `income_late`; report paid sales, fundable unmet, slots/jobs, paid income, debts/arrears, prices, wellbeing and nominal GDP. No target GDP or promise of universal firm viability.

Compute budget: reuse existing household/order iteration and per-firm fields; bounded scalars/order-local records, no unbounded history. Measure normal-mode matched 1k/10k workload, median/p95 variability against the shared 5% budget and report memory limits. Existing benchmark modes are not equivalent. Research supports internal/external financing as options (Bank of England 2024 SME investment survey), not a calibrated reserve or investment return. Use existing quoted cost/resource abstraction, not a new supplier market. Refresh OpenWiki using approved tooling if available; otherwise report due. No push, PR amendment or merge in this authorization.
