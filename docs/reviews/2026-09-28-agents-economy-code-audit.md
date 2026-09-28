# Code audit: backend/agents.py and backend/economy.py

Date: 2026-09-28. Branch `feat/frontend-redesign-phase2` at 17d5c0b, reviewed against the working tree. Review only; no code changed.

Scope: the whole of `backend/agents.py` (7,284 lines) and `backend/economy.py` (about 8,200 lines), read in nine parallel passes by class and line range, with callers checked by grep. Items marked **[verified]** were re-checked by hand in the main session. Others were reported by a reviewer with quoted code and are plausible but not individually re-read.

Caveat: `backend/economy.py` carries a large uncommitted diff (about 366 changed lines) and was edited *while this audit ran*. Line numbers for economy.py are from the file as of roughly 01:46 and may have moved. `Economy.step()` began at line 1586 at the end of the review.

Defaults that matter: `CONFIG.payment_sequence = "legacy"`, `labor_match_mode = "fast"`. Most "legacy" findings below are therefore the live default path.

---

## A. Money conservation bugs (default path)

1. **[verified] Subsidized purchases scaled down after the firm was paid.** `economy.py:1437-1454` calls `settle_capped_subsidized_goods_purchase` (1262-1284), which returns a `scale < 1` when the household cannot afford its share, and the loop does `quantity *= affordability_scale`. But `apply_sales_and_profit` (step line ~2306) already credited the firm the full `qty * price` from clearing (`firm_revenue[idx] += qty * price`, ~4364/4410) and removed the units from inventory. Nothing flows back. Result: `(1 - scale) * total_cost` is created and the matching units vanish. Fix: cap subsidized quantity by cash inside `_clear_goods_market` before revenue is booked, or reconcile units and revenue back to the firm.

2. **[verified] Long-term capital loan principal is wiped.** `_maybe_offer_long_term_capital_loan` (step ~1833) routes the principal to households via `firm.capital_investment_this_tick += ...`. `firm.plan_capital_investment()` runs later in the same loop (step ~1892) and in legacy starts with `self.capital_investment_this_tick = 0.0` (`agents.py:4463`). The bank debited reserves; nobody receives the cash. Fires for services/housing firms when unemployment is at least 10%. Fix: offer the loan after `plan_capital_investment`, or use an accumulator that is not reset.

3. **[verified] Medical-loan fallback creates money with a bank present.** `_issue_medical_loan` (~7632) falls through to `household.take_medical_loan(amount)` whenever both the bank loan and the government-backed loan fail, not only when `self.bank is None`. `take_medical_loan` does `self.cash_balance += loan_amount` (`agents.py:2018`) with no debit; repayment later destroys the cash. Triggers exactly when credit is tight. Fix: gate on `self.bank is None`, or fund from the treasury with a matching repayment recipient.

4. **[verified] Loan interest ignores term length.** `BankAgent.originate_loan` (`agents.py:6060-6065`): `total_repayment = principal * (1 + annual_rate)` regardless of `term_ticks`. A 520-tick loan pays one year's interest over ten years; a 26-tick loan pays a year's interest in six months. `payment_loans.v2_payment` amortizes correctly, so the two arms disagree. Fix: `annual_rate * term_ticks / ticks_per_year`, or reuse the payment-arm formula.

5. Legacy `_maybe_create_new_firms` (~5269-5278, 5400-5443) seeds new firms with `uniform(5000, 30000)` cash and no debit. Documented as known limitation K02, but it is the largest remaining leak in that range. Housing branches after ~5300 are unreachable.

6. Housing expansion mortgages (`_offer_housing_expansion_loans`, ~5974, 6003-6015) debit `bank.cash_reserves` directly instead of `originate_loan`, so they never appear in `active_loans`, `total_loans_outstanding`, or metrics, and exiting firms' mortgages vanish with no write-off. Also `round(principal / 15000)` builds 2 units for the price of 1 once a firm has ~23 units, because the request is `15000 * 1.2**(units/10)` for a single unit (`agents.py:5602`).

7. Legacy `_service_housing_mortgage_debt` (~5896-5925) subtracts the full payment (interest included) from a principal-only balance, overwrites `bank_loan_payment_per_tick` set by investment loans, never clears it after payoff, and charges a full PMT on the final tick.

8. Investment loans in legacy (`_offer_investment_loans` ~5600, 5670-5677): `_issue_firm_loan` lends `min(amount, max_borrowable)` and returns True; the caller then spends and books capital for the full `loan_amount`, pushing the firm negative.

9. Household ledger misses deposit withdrawals in `_ensure_cash_for_payment` (~6589), the healthcare withdrawal (~7175), and the pre-purchase withdrawal (~4182). The per-tick ledger no longer sums to the cash change. The "withdraw up to 90% of deposits" pattern is copied five times (economy 4182, 4199, 6603, 7175; agents 1639).

## B. Behavioral bugs

10. **[verified] Category preferences applied twice.** `HouseholdAgent.__post_init__` (`agents.py:569-574`) stores `category_weights = normalize(base * preference)`. `_batch_plan_consumption` (`economy.py:~1008-1013`) multiplies by `preference_matrix` again. Nothing else writes `category_weights` outside tests. Budget shares scale with preference squared; with `housing_preference_range=(0.4, 1.4)` housing weight spreads 0.16x to 1.96x instead of 0.4x to 1.4x.

11. **[verified] Price beliefs keyed by good name, read by category.** `plan_labor_supply` (`agents.py:1374-1376`) reads `price_beliefs.get("housing")` and `.get("food")`. Every writer keys by `good` (economy 1465-1494, 4745), and good names look like `FoodProduct42`. Both lookups always hit `default_price_level`, so `living_cost` is a constant and the cash-desperation and job-hunt triggers never react to prices. Same broken lookup at economy ~4759.

12. **[verified] Distress wage cut discarded.** `adjust_wages_to_revenue_ratio` (`agents.py:5498-5509`) cuts `wage_offer` and all `actual_wages`. `apply_price_and_wage_updates` (5541) runs nine step-lines later and sets `wage_offer = wage_plan["wage_offer_next"]`, planned pre-cut. Next tick `apply_labor_outcome` (5257) does `actual_wages[w] = max(actual_wages[w], wage_offer)`, undoing the per-worker cut.

13. **[verified] Synthetic job-switcher vacancies.** `_match_labor_fast` (`economy.py:~3765-3778`): if any household is job-switching, every private non-hiring firm (including ones planning layoffs) gets `planned_hires_count = job_switch_count`. Those vacancies are filled from the general `candidate_mask` (3785), which has no switcher filter, so one switcher can make every idle firm hire N unemployed workers. The caller's plan dict is mutated in place, so distress diagnostics report phantom failed hires.

14. Job-switcher fallback (~3992-4006) puts any switcher with no new employer back with the old one without checking `planned_layoffs_set`, silently undoing layoffs via `_sync_firm_employee_rosters`. Also a switcher can be "hired" by their current employer (~3940-3953), inflating turnover.

15. **[verified] `or 999.0` turns zero inventory into 999 weeks.** `_survival_turnaround_gate` (`agents.py:3126-3127`) uses `getattr(snapshot, "inventory_weeks", 999.0) or 999.0`. Services firms always have `inventory_weeks = 0.0` (3305-3307), so the credit-backed turnaround hiring branch (3568-3581) is dead for them, and a 0.0 margin becomes -1.0. Same pattern at 4988.

16. **[verified] Weak-demand streak freezes at 1.** `_refresh_service_weak_demand_streak` (`agents.py:2941-2952`) dedupes across its two per-tick callers by comparing `(units_sold, units_produced, profit)`. A firm in steady weak demand produces the same key every tick, so the streak never reaches the `>= 5` last-resort headcount cut (3553-3562). Fix: dedupe on tick number.

17. **[verified] Infrastructure productivity multiplier unbounded.** `invest_in_infrastructure` (`agents.py:7170`) adds every tick with no cap or decay, while technology is capped at 1.15 and social spending decays. It multiplies all firm output (economy ~4999).

18. Baseline Food liquidation layoffs undone: after shrinking `target_workers` by tier, `if self.is_baseline: target_workers = max(target_workers, demand_workers)` (`agents.py:4323-4324`) raises it back.

19. Firm code floors wages at `CONFIG.firms.minimum_wage_floor` ($20) instead of `government.get_minimum_wage()` ($25/36/50) at `agents.py:5158-5159, 5466-5470, 5542-5546`; healthcare workers are pinned to $20. `test_contracts_healthcare.py:250` codifies this.

20. Wage offer snaps to the floor in one tick when `unemployment_short_ma > nairu` (`agents.py:5064-5067`), bypassing `max_wage_decrease_per_tick`.

21. Housing branch of `plan_production_and_labor` (`agents.py:3789-3800`) never sets `planned_hires_count`/`last_tick_planned_hires`, so housing vacancies are invisible to the unfilled-vacancy logic.

22. `decision_diagnostics` is never cleared; one-shot flags stay True forever (`agents.py:3104-3110, 3157-3161`).

23. Wage tax percentiles include unemployed households at wage 0 and apply one flat rate to all income (`agents.py:6969-6992`); fixed-seed bracket scalers are out of order (p70 > p90). Profit bracket `very_rich_rate` is uncapped while `top_1_rate` is capped at 0.60 (7012-7017).

24. `set_lever` on a bailout lever calls `sync_bailout_cycle_budget`, which refills the budget and zeroes cycle counters mid-cycle (`agents.py:6584-6585, 6703-6711`).

25. `deficit_ratio = abs(gov.cash_balance) / gdp` (economy ~8004, 7661) reports a surplus as a deficit, and feeds the LLM government's `budget_state`.

26. Random supply shock (~6566) scales `last_units_produced`, which production overwrites the same tick, so it changes nothing real.

27. "Desperation" drawdown replaces rather than raises normal drawdown (`economy.py:~900-910`), so a household just under subsistence can spend less than one just over.

28. New working-tree reuse path (`economy.py:~1184-1193`) applies `_purchase_scale` with no one-unit housing cap, unlike every other planner path. New budget cap in `_clear_goods_market` (~4339-4355) counts budget-limited purchases as unmet demand, which drives firm entry weights.

29. Property tax rate grows by 0.005 per unit built (`agents.py:5614`; also economy ~6026, payment_projects 184) on top of a per-unit tax, so tax grows with units squared.

30. Constructor overrides silently discarded: `_initialize_personality_preferences` (`agents.py:317-335, 473-611`) unconditionally re-samples ~30 init fields including `expected_wage`, `happiness`, `price_expectation_alpha`. Factory overrides in tests are thrown away.

31. Skill growth credited by calendar time not time worked (`agents.py:2086-2091`); job-shopping active during warmup for the ~2% of households whose initial cooldown is 0 (1450-1459).

32. Tie-break noise is indexed by array position, not firm id, and its ±0.25 swing exceeds switching friction, so the primary firm flips on pool reindexing (`agents.py:874-910, 1168`). Switching friction is multiplicative so it inverts for negative utilities (969, 1181).

## C. Dead and drifted code

33. Per-agent `HouseholdAgent.plan_consumption`, `compute_saving_rate`, `apply_income_and_taxes`, `apply_purchases`, `consume_goods`, `update_wellbeing` (`agents.py:1489-1763, 2151-2440`) are not on the live path; economy inlines or batches the same logic and the copies have drifted (saving rate, trait multiplier, asymmetric price alphas, food consumption, housing-need flag). Tests still exercise the dead versions.

34. Never called: `apply_skill_decay`, `invest_in_education` (skills can only rise; `skill_decay_*` config inert), the medical training pipeline (1903-1988; every "student"/"resident" branch unreachable), annual care-plan methods (1819-1901), `_stockout_sales_floor_multiplier`, `_stockout_hire_growth_rate`, `_filter_to_awareness_pool`, `AgentMixin.apply_overrides`, `BankAgent.pay_deposit_interest`, `BankAgent.to_dict`.

35. Legacy labor matcher (~3408-3627) has diverged from fast (ordering, incumbents, synthetic vacancies, fallback), so `ECOSIM_COMPARE_LABOR_MATCH` always reports mismatches.

36. Payment path builds `household_tax_snapshots` (`economy.py:~2254`) and never reads it. **[verified]**

37. Production plans always overwritten by the governor (`agents.py:4355`), making the baseline `support_output` and tier `target_output` computations dead.

38. `elif category == "services"` at economy ~1506 unreachable; `_reset_healthcare_tick_state` (~6951) scans every household inventory for healthcare goods that can never be there.

## D. Performance and structure

39. `Economy.step()` is ~1,000 lines with two pipelines (legacy/payment) interleaved through ~30 `if payment_arm:` branches. Inside `step()` alone: ~12 full passes over households and ~22 over firms; file-wide, 63 household passes and 85 firm passes. Four consecutive household passes (education, cooldown, labor plan, consumption loan) and three consecutive firm passes (turnover reset, offer pool, offer buckets) can each be one loop.

40. `_batch_update_wellbeing` (~4591-4736) does ~20 `np.fromiter(generator over households)` passes; only the arithmetic is vectorized.

41. `_batch_plan_consumption` regathers ~14 static trait arrays (preferences, frugality, drawdown rate, category weights) every tick; they are only written at init.

42. Awareness-pool "cache" (`agents.py:854-872`) rebuilds a tuple signature on every lookup (5-6 per household per tick); measured 4x slower than `set(pool)`. Purchase planning (1066-1222) runs numpy ops on arrays of ≤10 elements; ~49 µs per household, ~0.25 s per tick at 5k households.

43. `_current_wage_bill()` walks every employee and is called ~10 times per firm per tick across agents.py and economy.py.

44. `_clear_housing_rental_market` (~6613-6838) uses `next(f for f in housing_firms if f.firm_id == ...)` per renter instead of `firm_lookup`, rebuilds and sorts `affordable_housing` per homeless household, and recounts homelessness per housing firm (`agents.py:5590-5593`).

45. `_match_labor_fast` unfilled-vacancy diagnostics (~3963-3990) recompute the same mask and median over all households per firm.

46. `get_economic_metrics` (~7754-8203) sorts household cash four times and makes ~15 household passes; called every 5 ticks and on every LLM decision.

47. Working-capital candidate diagnostics run twice per firm per tick (step ~1771 and `_issue_working_capital_bridges` ~2875), each calling `_marginal_worker_economics()`. `prepare_household_dues` runs twice on the payment path. `get_minimum_wage()` called twice per firm in the planning loop. Firm health snapshot dicts built every tick but only read by the audit log.

48. `_maybe_create_new_firms` sums all household cash before the cheap firm-cap early return; always picks the lowest-ID household as founder (`min(funders, key=household_id)`).

49. `@dataclass(slots=True)` on Household/Firm is defeated because `AgentMixin` has no `__slots__`, so every instance still carries a `__dict__`.

50. Loan ledger is a flat list; every per-borrower lookup and firm-exit write-off scans all loans (`agents.py:5928, 6026-6042`).

## E. Duplicated logic worth consolidating

- Preference weighting: agents 569-574, agents 1017-1025, economy ~1008-1032.
- Price-belief update: economy ~1089, ~1463, ~1487; agents 2211-2219.
- Debt-service sum: agents 4628-4635, 5049-5053, 5134-5138 (they disagree on which loans to include).
- Survival hysteresis and turnaround hire formula each appear twice in FirmAgent planning.
- Plan-dict return plus state stamping hand-written ~8 times in `plan_production_and_labor` (root cause of item 21).
- `payment_loans._post_payment`/`_write_off` duplicate `collect_repayment`/`write_off_loan`.
- Healthcare episode trigger: agents 1794-1807 and payment_sectors 420-430.
- Housing unit base cost `15000` hardcoded in agents 5602 and economy ~5974.
- `_build_category_market_snapshot` and `_build_good_category_lookup` duplicate halves of `_build_firm_market_views`.

## Suggested order of work

1. Money leaks A1-A4 (each is a small, local fix; add a conservation assertion to `test_contracts_invariants.py` that would have caught them).
2. B10-B13 (preference squared, price-belief keys, wage-cut overwrite, synthetic vacancies): each changes macro behavior materially.
3. Delete dead per-agent household methods (C33-34) and retarget their tests to the batch path, so future drift is impossible.
4. Split `step()` into per-phase methods with a legacy/payment strategy each; fuse adjacent passes; cache static trait arrays.
