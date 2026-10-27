# HOUSEHOLD affordability implementation

Implemented against `3de3f98324c39db2fed25a6792aed6c04a1ac799` (PR66 head
`cca042a` plus the rules/affordable-expansion contract). Fresh `git fetch origin
main` verified authoritative main at `d71485e7276cb2bf988eee6ff8ae9ecada3b73be`;
the isolated branch was **0 behind, 2 ahead**. Rules v1.17 and
`AFFORDABLE_EXPANSION_CONTRACT.md` govern this change. No Services finance,
wage, R&D, loan policy, UI, shared-rule, or shared-contract implementation edits.

## Findings and implemented behavior

1. **The live category allocator did not overspend its declared budget at its
   planning prices.** `_batch_plan_consumption` supplies one monetary budget;
   `_plan_category_purchases` normalizes category shares, deducts allocated
   spending from the remainder, keeps the one-unit Housing limit, and applies
   Food satiation/price adjustments. The tested allocations with both Food-first
   settings and budgets 0, 1, 35, and 500 stay within that budget. This is bounded
   evidence, not a proof for arbitrary malformed snapshots. The good-name
   fallback can use stale price beliefs; subsequent repricing is a forecast error,
   not by itself a duplicated cash flow. No preference, quality, seller-choice,
   awareness, or RNG rule was changed.
2. **The named planner used an opening-stock ceiling for both income timings.**
   With zero opening cash/deposits it emitted no seller basket even when
   `income_first` payroll subsequently paid 100 before shopping. The real
   `Economy.step()` reproduced this in normal and performance modes. The planner
   now includes the existing net-wage belief or announced benefit in the
   *estimated ceiling only for income_first*. Actual wages and benefits still
   have to settle. Expected receipts are not added to the savings stock or its
   drawdown. High-cash households retain the existing drawdown response rather
   than receiving another spending increment on forecast income.
3. **Goods feedback confused raw intentions with capacity demand.** Previously
   `finish()` recorded `wanted - accepted`, including insufficient cash,
   unavailable deposits, exhausted subsidy, changed quotes, and orders whose
   apparent funding was subsequently spent elsewhere. `_buy()` now checks
   affordability **before** the stock test and records the largest cumulative
   quantity fundable at an actual quote. This revalidates cached intentions too.
   Purchases retain their existing sequence and `PaymentBook.commit_sale`
   authority. Once both passes and priority payments have completed, feedback
   allocates the remaining household cash and one shared remaining subsidy pool
   across residual stockouts in existing household/target order. These are
   diagnostic allocations only: failures never reserve, debit, or transfer money.

An early quote is an intention, not an order against firm capacity. A household
can choose sellers from an income estimate before payroll, but no quantity can
become an attempted funded order or a shortage signal just because that income
was expected. A negative opening cash balance is included, signed, before the
estimated receipt repairs it. `income_late` never adds held income to the
shopping ceiling; CEO pay retains its existing late release in both arms.

## Budget and order arithmetic

Let `L = opening_cash + 0.90 * positive_deposit`, `O = indexed_rent + indexed_debt`,
and `E` be the existing take-home wage belief/benefit level for `income_first`, or
zero for `income_late`. These are currency amounts for one tick.

- Savings stock for drawdown: `S = max(0, L - O)`.
- Estimated spending-resource ceiling: `C = max(0, L + E - O)`.
- The existing MPC, personality and emergency rules compute spending using the
  existing income signals and drawdown from `S`, then cap it at `C`.
- The existing queued-care reserve is calculated after minimum Food on `C` and
  caps the budget again. It does not reduce `S` before drawdown. Each indexed
  rent/debt amount is subtracted once.

Deposits remain nominal access estimates until the one withdrawal pass actually
pays them out. At each purchase quote, `_sale_quantity` solves the existing
piecewise household/subsidy affordability limit using **current cash**, immutable
clearing price, subsidy share and actual remaining funded `G` envelope. The
fundable attempted quantity is computed without a stock cap; delivery then caps
it by stock. Paid units alone change inventories, consumption, clearing cash and
seller payables.

For feedback, residual quantity is bounded by
`min(desired, largest_cumulative_fundable_quote) - accepted`. Only a depleted
target can generate a capacity signal, and remaining resources are allocated
once across such residuals. First/second pass quantities are not added twice.
Actual purchases and rent/care/debt payments take precedence over hypothetical
failed sales. This deliberately removes a failed first Food target's demand if
the buyer spent the same money at another already-planned seller. It introduces
no substitute search. Good-name targets retain their existing exact-name,
price/ID routing and aggregate-only feedback when several suppliers match.

## Field and timing map

| Field/input (units) | Owner / observation time | Reader / resulting write |
|---|---|---|
| `wage`, employed status, lagged `expected_wage_tax_share` (currency/tick; share) | Employment contract and lagged paid-tax observation; phase-2 planning | `planning_inputs`: net-wage belief; never a payer debit |
| `cash_balance`, `bank_deposit` (currency stocks) | Household/PaymentBook and BankAgent | Opening planning estimate; only actual bank withdrawals become spendable cash |
| rent and `household_due_totals` (currency due this tick) | Existing tenancy; `prepare_household_dues` tick index | Once-subtracted planning obligations; actual rent/debt resolvers retain payment ownership |
| `expected_pre_shopping_income` (currency estimate) | `planning_inputs`, phase 2 | Private book diagnostic and estimated ceiling; zero in `income_late` |
| `estimated_savings_liquidity` (currency stock estimate) | `planning_inputs`, phase 2 | `_household_consumption_budgets`: normal/emergency drawdown; excludes expected receipts |
| `budget`, `planned_purchases` (currency; quantities by existing target) | Live batch/category planner, phase 2 | Five-tick complete-plan cache in named performance mode; copied as intentions into goods book |
| `paid_income`, `late_income`, wage claims (currency) | `PaymentBook.settle_income/settle_benefits`, phase 5b | Early cash or late hold, actual withholding and arrears; no forecast purchase funding |
| `prices`, `remaining`, subsidy share (currency/unit; quantity; share) | Immutable clearing quote/supply book | `_buy`: current-price affordability and stock-limited accepted quantity |
| `considered` (cumulative fundable quote quantity per household/target) | Tick-local goods adapter; existing two buyer passes | Largest unresolved cumulative quote, not a summed duplicate; fully fulfilled records are omitted by the later equivalent optimization, and no firm receives this private field |
| `accepted`, inventory, `services_consumed_this_tick` (quantity) | Existing funded sector delivery | Real household receipts/wellbeing inputs; no false delivery from rejected orders |
| `restrictions["G"]`, `sector_subsidy_remaining_this_tick` (currency) | Funded treasury envelope and PaymentBook settlement | Use the smaller remaining amount for affordability; virtual residual allocation never spends either |
| household cash, `clearing_cash`, `clearing_payables`, sales receipts (currency) | `PaymentBook.commit_sale/release_firm_receipts` | One actual buyer/subsidy payment and one seller release; ownership unchanged |
| Food/Services unmet and firm-specific unmet (quantity) | `PaymentGoodsMarket.finish`, after second pass/priorities | Fundable stockout only; existing next-tick firm demand/staffing/expansion readers |
| actual Food/Services consumption, health/wellbeing | Household apply and existing wellbeing cadence | Missing purchases still produce unmet needs and hardship even when market demand is zero |

## Executed evidence

Used interpreter `C:/Users/ayman/Documents/EcoSim/.venv/Scripts/python.exe` with
the isolated checkout's `backend` inserted first on `sys.path`. Explicitly
imported `backend`, `economy`, `agents`, `payment_sectors`, and `payment_behavior`;
asserted each `__file__` is beneath this checkout. No root-checkout backend was
tested.

Initial regression file on unmodified implementation: **15 failed, 17 passed**.
The original cash probe and planner-through-settlement failures were retained
before implementation; see the complete baseline output in the appendix.

| Case | Baseline | Intended result / executed guard |
|---|---|---|
| Plan 5, price 10, stock 10, cash 0 | Bought 0, unmet 5 | Bought 0, capacity unmet 0, both named sequences |
| Plan 5, price 10, stock 10, cash 20 | Bought 2, unmet 3 | Bought 2, capacity unmet 0; money/quantity unchanged |
| Plan 5, price 10, stock 2, cash 50 | Bought 2, unmet 3 | Retains bought 2 and fundable stockout 3 |
| Real planner, zero cash, paid early wage 100 | Empty basket / bought 0 in both modes | Existing seller choice yields purchases only when early payroll is actually funded |
| Actual payroll 0 / 20 / 100 against contract 100 | Zero-cash early basket missing | Exact funded gross, remaining claims and late holds reconcile; no unaffordable signal |
| Benefit level 100, funded envelope 0 / 20 | Forecast level not sufficient funding | Only actual early transfer buys; late transfer stays held |
| Deposits 100, actual bank cash 0 / 7 / 100 | Residuals misreported as demand | Only actual withdrawal buys; bank reserves, deposit liability and HH mirror reconcile |
| Cached real basket, price doubles and cash falls to 5, stock 0 | Full desired quantity counted | Only 0.25 fundable quantity; zero after cash is 0; cache remains unchanged |
| Actual Services payroll floor 75 versus planning price 10, cash 20 | Raw cash-limited remainder counted | Buys `20/75`, no shortage; real planner and real effective-price function |
| Real cached intentions, cash 20 plus subsidy 5 | Raw unfilled quantity counted | Delivers 2.5 units at 10; exact 25 seller receipt and exhausted cash/subsidy; unmet 0 |
| Two empty sellers / first and second pass | Same cash could back repeated raw residuals | One residual budget; finish cannot double-publish |
| Two households using funded 50% / 100% subsidy | Shared subsidy could back repeated raw residuals | One global virtual remaining envelope; actual treasury remains untouched by failures |
| Failed Food followed by planned stocked Food/Services | Failure counted after same cash was spent | Accepted purchases unchanged; no residual funded by already-spent cash/subsidy |
| Early Food stockout followed by actual rent 40 and bank installment 60 | Failed intentions could be counted regardless of later obligations | Both settle from cash 100; debt mirror/claim close; no money or capacity signal remains |
| Full public step, normal/performance and both named timings | Funded zero-opening early household still ate nothing | Real planner/settlement, then next tick with payer/cash exhausted; cached choices cannot create demand |
| Unfunded late household, normal mode | Food hardship present | Still zero consumption and declining health despite zero fundable market demand |

The existing subsidy-exhaustion test intentionally changes **only** its unmet
expectation from 3 to 0; its 5 units, 25 revenue, household cash, stock, subsidy
and clearing assertions remain. The existing failed-Food-target test changes
unmet from 2 to 0 after the other target consumes all cash. A focused care test's
mock was updated to supply the new private savings-stock diagnostic; its
Food-before-visit behavior and assertions are unchanged.

Final focused validation: **244 passed in 21.23 seconds**. It covers household affordability, sector/behavior/core
payment tests, composed payment acceptance, registered loans, government,
projects, reporting, Food/care reserve, income timing, shared liquidity, hot-path
optimizations, behavior contracts and wage consistency. The final count and
complete successful output are in the appendix. Ruff on all seven changed
Python files and `git diff --check` pass.

Run from the isolated worktree (prefix the command with the verified local
imports above when using the root interpreter):

```powershell
& C:/Users/ayman/Documents/EcoSim/.venv/Scripts/python.exe -m pytest `
  backend/tests_contracts/test_household_affordability.py `
  backend/tests_contracts/test_payment_sectors.py `
  backend/tests_contracts/test_payment_behavior.py `
  backend/tests_contracts/test_payment_core.py `
  backend/tests_contracts/test_payment_acceptance.py `
  backend/tests_contracts/test_payment_loans.py `
  backend/tests_contracts/test_payment_government.py `
  backend/tests_contracts/test_payment_projects.py `
  backend/tests_contracts/test_payment_reporting.py `
  backend/tests_contracts/test_households_healthcare_food_first.py `
  backend/tests_contracts/test_household_income_timing.py `
  backend/tests_contracts/test_household_liquidity.py `
  backend/tests_contracts/test_hot_path_optimizations.py `
  backend/tests_contracts/test_contracts_behavior.py `
  backend/tests_contracts/test_wage_contract_consistency.py -q -o addopts=
```

## Cost, interpretation, and integration follow-up

Shared-law evidence: L01/L04 are exercised by payroll/arrears, actual subsidy,
deposit, rent/debt and seller-clearing reconciliation with unchanged settlement
owners. L02 is exercised by stock/flow-limited delivery. L06 is preserved by
using the existing observed sellers, quotes and randomness, with no private
cause field supplied to firms. L08 is exercised by the food/health hardship
check when fundable demand is zero. L10 has the bounded cost analysis below;
its representative runtime acceptance remains the parent's integration gate.

Let `H` be households, `F` active firms and `O` existing household/order-candidate
visits. Planning adds constant arithmetic/private diagnostics per household and
one `H`-element float array for the separate savings stock. The goods adapter
adds an affordability calculation on existing visits (including empty targets),
one maximum fundable quantity per household/target, and a constant-time money
allocation per existing residual candidate. Added time is **O(H + O)**, added
tick-local state **O(H + O)**. Firm-ID targets have one candidate; exact-good-name
targets retain their existing bounded-by-matching-suppliers traversal. No new
household-by-firm scan, history, network call, seller discovery, combinatorial
planning, or changed normal/performance cadence is introduced. The complete
named performance basket remains cached for five ticks; actual affordability is
checked every shopping pass. Wellbeing cadence remains unchanged.

No representative 1k/10k matched performance matrix, full backend suite or
long-run macro experiment was run here: the parent owns those integrated checks
and concurrent heavy runs were explicitly excluded. This report does **not**
claim the shared 5% performance budget or economic acceptance. Executed unit and
small integrated cases establish mechanisms, not prevalence or calibration.

For households, timely funded early income can now support purchases that the
old opening-only cap suppressed. Unfunded households retain need and wellbeing
loss. For firms, capacity feedback excludes poverty/credit/subsidy exhaustion
and can reduce previously exaggerated shortage signals. That can reduce hiring
or expansion; paid early purchases can separately increase sales. Final nominal
GDP, jobs, prices, arrears, debt, cash and wellbeing must be compared together
in the parent's matched runs. No universal GDP or wellbeing improvement is
asserted.

Conservative feedback allocation gives all actual purchases and priority
payments precedence, then uses the existing order sequence to allocate funds
among residual stockouts. It is not a new rationing rule for accepted sales.
Needs beyond a desired basket, no observed seller, or an empty cached basket
remain unmet needs rather than invented orders. A newly hired worker with no
prior income forecast and no seller basket still follows the existing seller
refresh schedule; this change does not discover sellers after matching. Price
and income forecast errors remain possible and are rechecked at settlement.

Coordinator follow-up, without a new owner policy question:

- Preserve the common contract; update descriptive K03/timing and named-demand
  documentation to describe the early estimated ceiling, separate savings stock,
  and fundable feedback after the implementation is integrated.
- Refresh OpenWiki using the approved workflow. The local `openwiki` command is
  unavailable; the documented GitHub workflow requires its configured provider
  credentials and creates a wiki PR. No generated wiki was hand-edited and no
  workflow/PR was triggered. **Wiki refresh remains due.**
- Run the parent-coordinated backend gate and matched normal-mode household-only,
  financing-only, and combined 1k/10k comparisons. Keep Services finance and PR66
  commits separate. This child neither pushes nor opens/amends/merges a PR.

## Raw execution output

<!-- Baseline and final command output are appended below. -->

<details>
<summary>Unmodified implementation baseline (first 32 regression cases)</summary>

```text
backend=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\__init__.py
economy=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\economy.py
agents=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\agents.py
payment_sectors=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\payment_sectors.py
payment_behavior=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\payment_behavior.py
FFFF..F.F.F.FFFF..FF........F.F.                                         [100%]
================================== FAILURES ===================================
__ test_actual_cash_bounds_quote_and_capacity_signal[0-10-0-0-income_first] ___
backend\tests_contracts\test_household_affordability.py:60: in test_actual_cash_bounds_quote_and_capacity_signal
    assert e.food_unmet_demand == pytest.approx(unmet)
E   assert 5.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0 � 1.0e-12
___ test_actual_cash_bounds_quote_and_capacity_signal[0-10-0-0-income_late] ___
backend\tests_contracts\test_household_affordability.py:60: in test_actual_cash_bounds_quote_and_capacity_signal
    assert e.food_unmet_demand == pytest.approx(unmet)
E   assert 5.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0 � 1.0e-12
__ test_actual_cash_bounds_quote_and_capacity_signal[20-10-2-0-income_first] __
backend\tests_contracts\test_household_affordability.py:60: in test_actual_cash_bounds_quote_and_capacity_signal
    assert e.food_unmet_demand == pytest.approx(unmet)
E   assert 3.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 3.0
E     Expected: 0 � 1.0e-12
__ test_actual_cash_bounds_quote_and_capacity_signal[20-10-2-0-income_late] ___
backend\tests_contracts\test_household_affordability.py:60: in test_actual_cash_bounds_quote_and_capacity_signal
    assert e.food_unmet_demand == pytest.approx(unmet)
E   assert 3.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 3.0
E     Expected: 0 � 1.0e-12
_ test_planner_zero_opening_cash_uses_only_income_available_at_shopping[0.0-income_first] _
backend\tests_contracts\test_household_affordability.py:77: in test_planner_zero_opening_cash_uses_only_income_available_at_shopping
    assert bool(plans[1]["planned_purchases"]) == (timing == "income_first")
E   AssertionError: assert False == ('income_first' == 'income_first'
E    +  where False = bool({})
E
E       income_first)
_ test_planner_zero_opening_cash_uses_only_income_available_at_shopping[20.0-income_first] _
backend\tests_contracts\test_household_affordability.py:77: in test_planner_zero_opening_cash_uses_only_income_available_at_shopping
    assert bool(plans[1]["planned_purchases"]) == (timing == "income_first")
E   AssertionError: assert False == ('income_first' == 'income_first'
E    +  where False = bool({})
E
E       income_first)
_ test_planner_zero_opening_cash_uses_only_income_available_at_shopping[100.0-income_first] _
backend\tests_contracts\test_household_affordability.py:77: in test_planner_zero_opening_cash_uses_only_income_available_at_shopping
    assert bool(plans[1]["planned_purchases"]) == (timing == "income_first")
E   AssertionError: assert False == ('income_first' == 'income_first'
E    +  where False = bool({})
E
E       income_first)
_ test_planned_deposits_are_not_cash_until_actual_withdrawal[0.0-income_first] _
backend\tests_contracts\test_household_affordability.py:115: in test_planned_deposits_are_not_cash_until_actual_withdrawal
    assert e.food_unmet_demand == pytest.approx(0)
E   assert 5.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0 � 1.0e-12
_ test_planned_deposits_are_not_cash_until_actual_withdrawal[0.0-income_late] _
backend\tests_contracts\test_household_affordability.py:115: in test_planned_deposits_are_not_cash_until_actual_withdrawal
    assert e.food_unmet_demand == pytest.approx(0)
E   assert 5.0 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0 � 1.0e-12
_ test_planned_deposits_are_not_cash_until_actual_withdrawal[7.0-income_first] _
backend\tests_contracts\test_household_affordability.py:115: in test_planned_deposits_are_not_cash_until_actual_withdrawal
    assert e.food_unmet_demand == pytest.approx(0)
E   assert 4.3 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 4.3
E     Expected: 0 � 1.0e-12
_ test_planned_deposits_are_not_cash_until_actual_withdrawal[7.0-income_late] _
backend\tests_contracts\test_household_affordability.py:115: in test_planned_deposits_are_not_cash_until_actual_withdrawal
    assert e.food_unmet_demand == pytest.approx(0)
E   assert 4.3 == 0 � 1.0e-12
E
E     comparison failed
E     Obtained: 4.3
E     Expected: 0 � 1.0e-12
_ test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache[income_first] _
backend\tests_contracts\test_household_affordability.py:131: in test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache
    assert e.food_unmet_demand == pytest.approx(0.25)
E   assert 5.0 == 0.25 � 2.5e-07
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0.25 � 2.5e-07
_ test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache[income_late] _
backend\tests_contracts\test_household_affordability.py:131: in test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache
    assert e.food_unmet_demand == pytest.approx(0.25)
E   assert 5.0 == 0.25 � 2.5e-07
E
E     comparison failed
E     Obtained: 5.0
E     Expected: 0.25 � 2.5e-07
_ test_public_step_real_planner_preserves_income_timing_and_hardship[False-income_first] _
backend\tests_contracts\test_household_affordability.py:179: in test_public_step_real_planner_preserves_income_timing_and_hardship
    assert (hh.last_food_units > 0) == (timing == "income_first")
E   AssertionError: assert (0.0 > 0) == ('income_first' == 'income_first'
E    +  where 0.0 = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=100.0, goods_inventory={}, employer_id=1, wage=1...are_firm_id=None, healthcare_queue_enter_tick=-1, awareness_pool={}, current_primary_firm={}, last_pool_refresh_tick=0).last_food_units
E
E       income_first)
_ test_public_step_real_planner_preserves_income_timing_and_hardship[True-income_first] _
backend\tests_contracts\test_household_affordability.py:179: in test_public_step_real_planner_preserves_income_timing_and_hardship
    assert (hh.last_food_units > 0) == (timing == "income_first")
E   AssertionError: assert (0.0 > 0) == ('income_first' == 'income_first'
E    +  where 0.0 = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=100.0, goods_inventory={}, employer_id=1, wage=1...are_firm_id=None, healthcare_queue_enter_tick=-1, awareness_pool={}, current_primary_firm={}, last_pool_refresh_tick=0).last_food_units
E
E       income_first)
=========================== short test summary info ===========================
FAILED backend/tests_contracts/test_household_affordability.py::test_actual_cash_bounds_quote_and_capacity_signal[0-10-0-0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_actual_cash_bounds_quote_and_capacity_signal[0-10-0-0-income_late]
FAILED backend/tests_contracts/test_household_affordability.py::test_actual_cash_bounds_quote_and_capacity_signal[20-10-2-0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_actual_cash_bounds_quote_and_capacity_signal[20-10-2-0-income_late]
FAILED backend/tests_contracts/test_household_affordability.py::test_planner_zero_opening_cash_uses_only_income_available_at_shopping[0.0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_planner_zero_opening_cash_uses_only_income_available_at_shopping[20.0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_planner_zero_opening_cash_uses_only_income_available_at_shopping[100.0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_planned_deposits_are_not_cash_until_actual_withdrawal[0.0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_planned_deposits_are_not_cash_until_actual_withdrawal[0.0-income_late]
FAILED backend/tests_contracts/test_household_affordability.py::test_planned_deposits_are_not_cash_until_actual_withdrawal[7.0-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_planned_deposits_are_not_cash_until_actual_withdrawal[7.0-income_late]
FAILED backend/tests_contracts/test_household_affordability.py::test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache[income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_cached_choices_recheck_cash_and_actual_quote_without_mutating_cache[income_late]
FAILED backend/tests_contracts/test_household_affordability.py::test_public_step_real_planner_preserves_income_timing_and_hardship[False-income_first]
FAILED backend/tests_contracts/test_household_affordability.py::test_public_step_real_planner_preserves_income_timing_and_hardship[True-income_first]
```

</details>

<details>
<summary>Final focused validation</summary>

```text
backend=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\__init__.py
economy=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\economy.py
agents=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\agents.py
payment_sectors=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\payment_sectors.py
payment_behavior=C:\Users\ayman\.t3\worktrees\EcoSim\t3-2cde3782\backend\payment_behavior.py
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 88%]
............................                                             [100%]
244 passed in 21.23s
```

</details>
