# Banking System

EcoSim's bank is an optional credit and deposit channel implemented by `BankAgent` in [`backend/agents.py`](../backend/agents.py) and integrated by `Economy.step()` in [`backend/economy.py`](../backend/economy.py).

## Purpose

The bank adds delayed financial transmission to the simulation:

- households can hold deposits, earn limited interest, withdraw savings for planned spending, and borrow for consumption or medical needs
- firms can borrow for capital, service infrastructure, housing expansion, and working-capital bridges
- credit scores, repayments, defaults, reserves, and lending capacity affect whether credit reaches the real economy
- government policy decisions can affect firms through cash flow, demand, subsidies, minimum wages, and backstop programs rather than direct grants alone

The bank is intentionally not a full banking-sector model. There is one bank, one reserve constraint, simple loan products, simple credit scores, and no interbank market.

## Design Rules

1. The simulation must remain runnable when `bank is None`.
2. Bank lending augments cash-constrained decisions; it is not required for ordinary firm or household behavior.
3. Government can authorize/backstop some credit paths, but the bank owns ordinary deposit, repayment, and credit-score mechanics.
4. The hot simulation path stays in memory. Bank state is regular agent state, not a database dependency.

## Bank State

Current bank telemetry includes:

- `cash_reserves`
- `total_deposits`
- `total_loans_outstanding`
- `base_interest_rate`
- `deposit_rate`
- `reserve_ratio`
- `loan_loss_provision`
- per-tick interest income, deposit interest paid, new loans, defaults, and repayments
- firm and household credit-score maps
- active loan records

These values are exposed through economy metrics when a bank exists.

## Household Deposits

Households have `cash_balance` and `bank_deposit`. The bank deposit is a savings buffer, not a separate simulation object.

Deposit behavior:

- households can sweep excess cash into deposits near the end of the tick
- deposit behavior varies by household saving tendency
- the bank pays deposit interest only within profitability/reserve constraints
- if cash falls below the household liquidity floor, deposits can be withdrawn back to cash
- before goods and healthcare purchases, the economy can withdraw a configured accessible share of deposits to cover planned spending shortfalls

The current accessible deposit share is configured by `CONFIG.households.household_deposit_access_rate` and is `0.90` by default.

## Loan Products

The current code supports several bank-integrated credit paths.

| Path | Borrower | Purpose |
|---|---|---|
| Capital investment loans | Firms | Fund productive capital when a firm plans investment and lacks cash |
| Service infrastructure loans | Services firms | Expand service employee-slot capacity after sustained utilization |
| Housing expansion loans | Housing firms | Finance additional rental units |
| Working-capital bridges | Viable private firms | Fund short-term payroll/hiring support when demand exists and unemployment is high |
| Consumption loans | Households | Bridge low-cash household consumption needs |
| Medical loans | Households | Pay for healthcare or medical education paths where cash/deposits are insufficient |
| Government-backed loans | Firms or households depending on path | Fallback/backstop credit when policy or circuit-breaker logic routes risk through government support |

Loan terms use simple repayment logic over tick-based terms. This is deliberate; the goal is economic feedback, not amortization fidelity.

## Credit Scores

The bank keeps separate firm and household credit-score maps, initialized around a neutral score for new borrowers.

Score changes are intentionally asymmetric:

- successful repayments improve scores slowly
- missed payments and defaults reduce scores faster
- firm revenue/payroll health can improve or weaken scores
- unemployment can weaken household credit
- persistent default writes down loan value through loan-loss provision

Credit scores feed into approval and risk-adjusted rate decisions.

## Reserves And Lending Capacity

`BankAgent` enforces a reserve-ratio concept through `required_reserves`, `lendable_cash`, and `can_lend`.

The bank may stop ordinary lending when reserves are insufficient. Some government-backed paths can still route support through government cash rather than bank reserves. That prevents a hard credit stop from making every crisis unrecoverable while preserving a real lending constraint for ordinary credit.

## Tick Integration

Banking touches multiple parts of the tick:

- early firm planning can mark capital or infrastructure loan needs
- the economy originates eligible firm loans before same-tick capacity decisions where applicable
- consumption loans can be offered after household consumption planning
- deposit withdrawals can happen before market clearing
- healthcare can use deposits or medical loans when cash is insufficient
- loan repayments run after firms and households have income from wages and sales
- deposit sweeps and interest run after household income, taxes, purchases, and transfers
- credit scores and settled loans update near the end of the fiscal section

This ordering is important. Repayments occur after wages and sales so the bank does not drain borrowers before they receive same-tick income.

## Government Boundary

The government remains responsible for:

- taxes
- unemployment benefits and transfers
- sector subsidies
- public works
- infrastructure, technology, and social spending
- bailout policy and bailout budget
- fiscal pressure and spending efficiency

The bank remains responsible for:

- deposits
- loan origination where funding and credit checks pass
- repayments and defaults
- credit scores
- reserve-limited ordinary lending

Some paths use government cash or guarantees as a backstop, but the bank does not set policy and the government does not replace ordinary deposit accounting.

## Observability

Economy metrics expose bank-related values such as:

- `bank_cash_reserves`
- `bank_total_deposits`
- `bank_total_loans_outstanding`
- `bank_base_interest_rate`
- `bank_deposit_rate`
- `bank_loan_loss_provision`
- `bank_active_loan_count`
- `bank_can_lend`
- `bank_lendable_cash`
- `bank_new_loans_this_tick`
- `bank_defaults_this_tick`
- `bank_repayments_this_tick`
- `bank_deposit_interest_this_tick`
- `bank_interest_income_this_tick`
- `bank_reserve_ratio_actual`
- average firm and household credit scores

The frontend currently surfaces selected finance and government-backed-loan telemetry, not raw loan tables.

## Scope Boundaries

Implemented:

- one bank
- household deposits and interest
- reserve-aware lending capacity
- firm and household credit scores
- multiple simulation-specific loan paths
- repayment/default handling
- bank metrics in the live economy payload

Not implemented:

- multiple banks
- interbank lending
- central-bank policy rate controls as a live government lever
- deposit insurance
- mortgages for households
- credit cards or general consumer-finance products beyond the current consumption/medical paths
- exact amortization schedules

These boundaries are intentional for the current release. The bank is a practical credit channel, not the core subject of the simulator.
