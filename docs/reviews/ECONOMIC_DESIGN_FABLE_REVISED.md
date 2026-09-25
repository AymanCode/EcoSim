# Revised EcoSim proposal: corrected mechanisms, policy transmission and individual agents

Prepared by Claude Fable 5.1 (`claude-fable-5-1`), 2026-09-21. This was a read-only pass over the frozen snapshot: baseline `4f693890…` plus the W01–W05 working-tree changes. I ran no code, tests or benchmarks. Every executed result cited here (E01–E10, the counterexample JSON, the 358-test run, the timings) belongs to the coordinator.

**Labels.**
- **[I]** implemented fact, read in current source.
- **[D]** defect shown by source or equation.
- **[M]** model choice.
- **[H]** hypothesis needing measurement.
- **[A]** assumed value, not calibrated.
- **[X]** external evidence (a principle only).
- **[P]** proposed default, chosen by me.

**Process note.** One of my greps this session failed on an unsupported look-ahead. This is the same class of error the audit flagged in my first trace, and I re-ran it without look-around. My reader inventories are careful, not exhaustive.

## 0. Decision summary

1. **I accept D01–D11.** Several of my "A-ready" labels were wrong. The multiplicative tax-expectation rule, the one-float rolling mean, the `deque(maxlen=D)` pipeline and the overdraft "creation" line are withdrawn and replaced in §1.
2. **Many policy-to-behavior links in today's engine are blocked or partial.** These are source facts, not effect estimates:
   - Consumption plans use gross wages.
   - Healthcare requests ignore price.
   - The policy rate reaches only investment and credit formulas.
   - **New, F1 [D, by reading; needs a probe]:** `_build_firm_tax_snapshots` omits the fields `plan_taxes` reads for firm wealth brackets and property tax. In `Economy.step`, profit-tax progressivity therefore appears to collapse to one rate, and property tax appears never to be charged.
3. **Individuality is already substantial for households and shallow for firms.** A household has about 30 persistent traits. However:
   - skill, age and starting cash are deterministic functions of `household_id` [D];
   - several sampled traits have no reader;
   - the traits that would differentiate the response to tax, benefit, healthcare and interest-rate policy do not exist.

   I propose at most four new household traits and two firm traits. Each is tied to one policy question, drawn from stable string keys, stored as arrays, and zero-cost when its flag is off.
4. **Subagents:**
   - (a) Domain coding agents are feasible under the existing contract, with one integration owner.
   - (b) Sampled-case reviewer agents are cheap, useful and read-only.
   - (c) Live LLM decisions per individual are feasible only as a small, cached, replayable research arm. They should never be the default simulator.
5. **Queue:** the diagnostic and metric slices come first. W07 gains subgroup outcomes keyed to pre-policy membership, and a new transmission-probe harness (extension W10-P) follows. W08 and W12 design proceeds in parallel.

---

## 1. Correction disposition

### D01–D11

I found no counterexample to any of these corrections.

**D01: accepted.**
- **Basis.** With signed treasury cash in M, paying 10 to a household while treasury cash moves 0 → −10 leaves ΔM = 0. My extra `gov_overdraft_change = +10` line produced a residual of −10. That was double counting.
- **Replacement rule.** Keep three separate report-only quantities:
  - **Signed settlement checksum** `S_t`: Σ household, firm (active and queued), government **signed** and bank reserve cash, plus `misc_firm_revenue`. ΔS must equal only the named unmatched lines: unfunded entry, exit removal, demand shocks, legacy medical-fallback origination. Overdraft spending never appears as a line.
  - **Gross spendable balances** `G_t = Σ max(cash, 0)` by holder class.
  - **Claims table**: bank and treasury loan claims against the borrower mirrors.
  - `financing_gap_t = max(0, −gov.cash)` stays an analytical stock. It is never added to S and never summed over ticks.
- **Open choice.** Whether to declare a monetary-authority account. Until one exists, nothing is labelled "creation".

**D02: accepted.**
- **Basis.** Charging an exiting firm's negative cash to bank reserves invents a bank liability. Equal dividends after unequal contributions shift value between owners. `_ensure_cash_for_payment` can return False after a partial withdrawal [I].
- **Replacement rule.**
  - Entry funding uses **equal committed contributions**. Preflight each candidate's `max(cash,0) + min(0.9·deposit, the bank's actually withdrawable reserves)`. Settle all-or-nothing: compute, verify, then mutate. If any step fails, roll back withdrawals in reverse order.
  - Owners of loan-funded entrants pay a down-payment. No free shares.
  - Exit with cash < 0: book to a declared `legacy_resolution_account`, a report-only sink. An identified overdraft creditor comes later if W14 adds one.
  - Exit with cash > 0: waterfall through W01's funder-aware helper.
- **Open choices.** Weighted shares versus equal commitments [P: equal]. Whether the resolution account is fiscal.

**D03: accepted.** I withdraw the ratio rule.
- **Basis.** τ̂ = 0 stays 0 under multiplication. The zero-rate fallback ignores the bracket scalers. 0.15 → 0.20 → 0.40 before planning leaves a factor of 2, not 8/3. `plan_taxes` brackets are percentiles of **current** wages, so membership moves [I].
- **Replacement rule.** A pure helper `expected_wage_tax(wage, wages_sorted_snapshot, rate, scalers) -> tax` reproduces the `plan_taxes` bracket logic exactly and is called **once per planning boundary**.
  - Information set [M]: the current announced `wage_tax_rate` and scalers, plus **last tick's** wage percentile cut-points. The lag is declared under L06.
  - `announce` mode uses the current lever at the planning boundary. It is idempotent, so repeated setter calls cannot matter.
  - `learn_only` mode uses the rate in force at the last settlement.
  - Cases (acceptance tests in §5): startup before any settlement; unemployed (wage 0 → tax 0, no stale rate); re-employed (computed from the new wage); zero rate (exactly 0); cut-point ties use the same `<=` as source.
  - Scalar and batch planners call the same helper. The N2 saving discrepancy is untouched and documented.

**D04: accepted.**
- **Replacement rule.** A ring buffer `income_hist[4, N]` plus a running sum, recording `coverage_i = min(ticks_observed, 4)`. Rates are reported only over households with coverage = 4.
- The income definition is deferred until ledger keys are split. Liquidation payments must leave `dividends`, and deposit interest must be separated from principal inside `bank`.
- **Ready slice.** Liquid-resource stocks only.
- **Open choice.** Whether a new ledger key such as `capital_distribution` may be added, since it touches serialization consumers.

**D05: accepted.**
- **Basis.** In healthcare, `per_firm_sales.revenue += visit_price` includes the subsidy [I]; the household pays `household_cost`.
- **Replacement rule.** Three series per category: household payments (`last_*_spend`), provider receipts (`per_firm_sales.revenue`) and physical quantities (units, visits, occupied units).
  - The consumer-cost index uses household payments per quantity, and zero is a valid value.
  - The producer price uses receipts per quantity.
  - Constant-price output uses frozen **positive reference producer** prices.
  - A category with no reference-window transactions is excluded from the index with a flag. No price is invented for it.
- **Open choice.** Reference-window length [A: 12 ticks].

**D06: accepted.** My earlier N5 was wrong.
- **Basis.** `_get_purchase_tie_break_noise` uses `np.random.default_rng` with cached read-only arrays. `_deterministic_unit_random` is a third RNG surface. `to_dict` omits caches and internal fields [I].
- **Replacement rule.** The first diagnostic is two isolated replays, each inside its own `use_config` context. The fingerprint is a declared field list plus metrics, and its limits are stated. RNG keys are tested **structurally** (purpose and id tuples are unique) and not by comparing first draws. Runtime is recorded. No RNG migration happens in this slice.
- **Open choice.** Which internal fields join the fingerprint.

**D07: accepted.**
- **Basis.** `deque(maxlen=D)` silently drops the oldest element when appended to while full.
- **Replacement rule.** Due-date slots, `pipeline: Dict[int, float]` keyed by delivery tick. Spend at tick t in phase 11.5, then `pipeline[t+D] += amount`. At the start of phase 11.5 of tick t+D, `K += pipeline.pop(t+D, 0)`. Production first sees K in tick t+D+1's planning.
  - The deflator is a declared investment-price assumption [M]: constant 1.0 as the default, with the producer index as a sensitivity. It is not consumer CPI.
  - The supply side is a labelled reduced form: "no input competition". If the question needs input competition, the work becomes W15.
- **Open choices.** The payment recipient and the capacity abstraction. These keep W11 at B.

**D08: accepted.**
- **Replacement rule.** One atomic function:

  ```
  pay_rebate(total):
      gov.cash -= total
      for each household: cash += r; ledger "transfers" += r
  ```

  - `last_tick_gov_rebate` is added to `tick_spending` before `_update_budget_pressure` (see `Economy.step`, phase 11.7).
  - `R = ρ · max(0, cash − max(B*, 0))`, and nothing is paid when cash ≤ 0 [P]. Borrowing therefore never finances a rebate, which resolves the negative-B* case.
  - The planner reads the rebate through an explicit term `rebate_income · mpc_benefit` [M], fed by a one-tick-lagged `last_rebate_income`. A variant without this reader must be labelled "liquidity-only".
  - The rebate is untaxed, consistent with transfers.
- **Open choice.** Whether to use a rebate closure at all. `hold` stays the co-equal alternative.

**D09: accepted.**
- **Replacement rule.** A 2×2 factorial: payer {patient, public} × provider pricing {existing firm rule, administered}. The headline payer-only contrast uses the **existing firm pricing in both arms**. Administered prices, if used, index to a lagged index that excludes healthcare.
  - The patient-pay arm must assert both `healthcare_visit_subsidy_share == 0` and that the healthcare sector-subsidy lever is off. Both are read in `_process_healthcare_services` [I].
- **Open choice.** Whether the package comparison is also wanted.

**D10: accepted.** The sign I gave was wrong.
- **Replacement rule.** Report the unemployment–vacancy correlation and the scatter plot as a diagnostic. The conventional relationship is inverse. Shifts are possible. No pass/fail is attached.

**D11: accepted.**
- **Replacement rule.** Two separate gates.
  - *Exactness:* each transaction has |payer Δ + recipient Δ| ≤ 1e-9·max(1, |amount|). The aggregate unexplained ΔS is ≤ 1e-6 absolute plus 1e-12·ΣG per tick.
  - *Materiality:* used only to rank which **named** abstractions to fix first. Statistical insignificance never excuses an unexplained transfer.

### N1–N8, with the audit's qualifications

- **N1: stands.** The household stabilizer flag has no reader. The W03 manifest does not yet declare it inert. The labelling slice is W09.
- **N2: stands as an input difference only.** Batch planning reads `savings_drawdown_rate` at `economy.py:796–829`. Scalar planning reads `compute_saving_rate()`. The magnitude is unmeasured. The saving model must not be altered inside W08.
- **N3: narrowed.** The seed reuse is real (`seed + id*7919`). My claim that the two streams yield "the same first number" is withdrawn, because sector and CEO draws can precede the tier draw. The correlation is unmeasured.
- **N4: stands structurally.** I add that realized effects can still differ across arms under identical draws, because clipping depends on each arm's state.
- **N5: retracted** (see D06).
  - **New, F2 [D, structural]:** `_sample_annual_visit_count` seeds `seed + id*9973 + anchor*37`. At `anchor_tick = 0` this equals the household trait seed at `agents.py:448`, so the first visit draw equals the trait stream's first uniform (the savings-target draw). The size is unmeasured. It is a second concrete argument for purpose-keyed streams.
- **N6: stands,** corrected to "an additive increment to a multiplier", not a compound growth rate.
- **N7: stands.** Changing the tax base needs its own specification.
- **N8: stands only for a fixed bracket and fixed scalers.** It does not rescue W08.

On W09 wording, I accept that `adjust_policies` only sizes the transfer budget. I also accept that a source-grep test does not establish capability preservation, and I replace it with behavior checks.

### New finding F1 (needs a coordinator probe)

**Source reading.**
- `plan_taxes` reads `cash_balance`, `good_category`, `property_tax_rate`, `max_rental_units` and `price` from each firm dict (`agents.py:6926–7002`).
- `_build_firm_tax_snapshots` (`economy.py:4360–4409`) emits only `firm_id`, `profit_before_tax` and `price_ceiling_tax`.

**Consequence in `step()`.**
- Every `cash_balance` defaults to 0, so all percentiles are 0.
- Every firm then satisfies `cash <= q1` and gets `poor_rate = max(0.01, base − fixed discount)`, where the discount comes from `Random(54321)`.
- `property_taxes` stays empty.

**Probe.** One tick with firms of very different cash, plus a Housing firm with `property_tax_rate > 0`. Assert the realized profit-tax rates and that property tax is positive. I found no test covering this.

**Status.** Until the probe runs, treat "progressive business tax" and "property tax" as possibly inactive in the engine path. They must not be used as interventions.

---

## 2. Policy transmission map

**Reading rules.**
- Each link is marked **E** (existing in source), **P** (proposed) or **M** (missing).
- Mechanism-isolation probes change one link with everything else pinned. They answer "does this channel transmit, and with what sign, in this model". They are **not** total policy effects.
- A total-effect run needs a declared fiscal closure, all channels active together, paired seeds and subgroup outcomes.
- An inactive lever (the inflation target, the household stabilizer, and possibly F1) must never serve as an arm.

**Common assumptions for all comparisons.**
- Closure is `hold` and `rebate` per the corrected D08, with `legacy` as a reference only.
- Transfers remain unconditional and may drive the treasury negative [I, E02].
- Capacity is whatever labor, capital and queue constraints the engine already has.
- There is no hours margin, avoidance or migration.
- All signs below are **model-internal possibilities**, not predictions.

### 2.1 Progressive wage tax (headline rate inside the existing brackets)

**Immediate payer, recipient and constraint.**
- Employed households pay at phase 10. The treasury receives at phase 11 (E: `_batch_apply_household_updates`, `apply_fiscal_results`).
- The base is `household.wage` only. CEO pay is excluded (N7).
- Brackets are percentiles of current wages **including zeros** (E: `plan_taxes`). Cut-points therefore move with unemployment.

**Differentiated household and firm decisions.**
- E: the liquidity cap `budgets = min(base + drawdown, cash + 0.9·deposits)` binds for low-buffer households first.
- E: drawdown varies by `savings_drawdown_rate`.
- M → P (W08): net-wage planning.
- M: labor supply. `plan_labor_supply` reservation wages use gross wages.
- M: no firm sees tax directly.

**Other actors and markets.**
- E: lower purchases reduce firm `expected_sales_units`, which feeds hiring and layoffs (`plan_production_and_labor`), which feeds the wage bill and unemployment, which feeds benefits.
- E: deposits fall, so the bank's lendable reserves fall.

**Delayed feedback.**
- E: exit needs 12 or more zero-cash ticks; entry is limited to one firm per tick.
- E: the tax base shrinks with employment.
- E: the crisis-MPC boost switches on when unemployment exceeds 25%.
- Depends on the closure: a rebate raises the cash of low-wage and unemployed households.

**Outcomes to measure, by pre-T0 wage quartile and buffer tercile.**
- Consumption units, liquid p10/p50/p90, share of households at the liquidity cap, firm counts, employment, treasury signed cash.

**Opposite sign is possible.**
- Under `rebate`, per-capita recycling to high-MPC households can **raise** aggregate spending, given `mpc_benefit` versus the floored `mpc_wage`.
- Under `hold`, the effect is contractionary through liquidity.

**Adverse or unintended effects.**
- Percentile brackets mean a layoff wave re-brackets survivors upward. This is a rate increase with no policy change.
- The exclusion of CEO pay favors owner-managers.

**Blocked or incomplete cases.**
- A buffered household's plan is unchanged today. **This is a modeling gap, not evidence of a zero tax effect.**
- In performance mode, plans refresh only at `tick % 5 == 0`.

### 2.2 Business taxes (profit, investment, property)

**Immediate payer, recipient and constraint.**
- E: the profit tax reduces firm cash at phase 9 through `apply_sales_and_profit`.
- E: the investment tax is a share of R&D spending (phase 11.6).
- **F1: bracket progressivity and property tax appear blocked in the `step()` path.**

**Differentiated decisions.**
- E: firm cash drives the self-finance test in `plan_capital_investment` (`cash > cost + 8 weeks of wages`), the `survival_mode` flag, and dividends through `payout_ratio` in `distribute_profits`.
- M: no after-tax return enters the MPK-versus-cost rule, because `vmpk` is pre-tax.
- M: there is no price pass-through rule that references tax.

**Other actors and markets.**
- E: owners' `last_dividend_income` feeds `mpc_dividend` spending.
- E: workers are affected through hiring and wage plans when firm cash is stressed.
- E: the bank is affected through investment-loan demand.
- E: the R&D remainder goes to the misc pool and then to at most 50 beneficiaries.

**Delayed feedback.**
- E: `capital_stock` affects output later.
- E: exit leads to write-offs (W01 paths).
- E: entrants have no owners, so the dividend channel shrinks with turnover.

**Outcomes to measure.**
- Investment units, firm cash distribution, exits by sector, dividend recipients' consumption, wage offers.
- An incidence split: owners versus workers versus customers.

**Opposite sign is possible.**
- Higher revenue under `rebate` could lift demand enough to offset the cash drain for consumer-facing firms but not for others.

**Adverse or unintended effects.**
- Thin-cash firms cross into `survival_mode` and lay off workers.
- The burden lands on workers through the existing wage and hiring rules, with no explicit incidence rule. External evidence says the worker share can be large and unequal [X: Fuest, Peichl and Siegloch]. The model has no such rule, so any worker incidence here emerges from, or is limited by, the liquidity rules.

**Blocked or incomplete cases.**
- F1.
- Baseline firms are exempt from exit.
- The investment tax touches R&D only, not capital purchases.

### 2.3 Benefits and transfers

**Immediate payer, recipient and constraint.**
- E: the treasury pays unemployed households with **no cash check**. Gap-filling is limited by `transfer_budget`.

**Differentiated decisions.**
- E: recipients spend through `mpc_benefit`.
- E: the unemployed reservation path uses `benefit × min_job_premium_over_unemployment` (`agents.py:1388`).
- E: **firms' wage floor is `max(min wage, benefit × 1.5)`** in `plan_wage` (`agents.py:4907, 5093`), so the benefit level is also a wage-floor policy.
- E (N1-adjacent): the sampled `reservation_markup_over_benefit` trait has no reader outside `to_dict`.

**Other actors and markets.**
- E: a higher floor raises wage bills, which feeds hiring plans and prices through unit cost.
- E: recipients' spending goes to Food, Services and Housing firms.

**Delayed feedback.**
- E: the treasury deficit raises `fiscal_pressure`, which lowers `spending_efficiency`. That matters only if infrastructure or technology spending is on.
- E: `min_cash_threshold` moves the legacy poverty metric (E05).

**Outcomes to measure.**
- Unemployment duration distribution, accepted wages, vacancy fill, wage-floor-bound firms, recipients' liquid p10.

**Opposite sign is possible.**
- Demand support can raise hiring, while the floor can reduce it.

**Adverse or unintended effects.**
- A benefit change silently moves every firm's wage floor. A "benefit" arm is therefore a **package** with the wage floor unless the 1.5× link is pinned by a declared flag [P: expose `wage_floor_benefit_multiple`, default 1.5].

**Blocked or incomplete cases.**
- There is no benefit duration limit, no eligibility rule beyond non-employment, and no taper.
- Market-anchoring erodes reservation wages with duration regardless of benefit.

### 2.4 Patient-pay versus public payer

**Immediate payer, recipient and constraint.**
- E: the patient pays `visit_price − subsidy`. The subsidy path stops when `gov.cash ≤ 0` and is capped per tick (`apply_sector_subsidy_payment`).
- P: a public payer pays the provider per **completed** visit.
- E: capacity comes from staff and the queue.

**Differentiated decisions.**
- E: **requests do not depend on price or cost**; `should_request_healthcare_service` reads health and traits only.
- E: provider choice has a small price term.
- E: affordability shows up only at service: deposits first, then a loan, then a drop from the queue.
- P (§3): cost-sensitive deferral.

**Other actors and markets.**
- E: provider revenue feeds hiring and the doctor-training pipeline.
- E: medical loans run through the bank or treasury (W01/W02).
- E: health affects productivity and wellbeing.

**Delayed feedback.**
- E: fewer affordability drops mean a longer queue and longer waits.
- E: debt service disappears, so more cash is available for goods.
- P: tax financing sends the effect back through §2.1.

**Outcomes to measure, by health tercile and buffer tercile.**
- Completed visits (**quantities**), household out-of-pocket spending, provider receipts, waits, affordability rejects, medical debt, health, treasury cash.

**Opposite sign is possible.**
- If capacity binds, free care can lower completed care for some patients through longer waits, while raising it for those previously dropped.

**Adverse or unintended effects.**
- A price-insensitive payer combined with the existing firm pricing rule could ratchet prices [H]. This is a treasury drain, not a patient burden.

**Blocked or incomplete cases.**
- Without a demand response, free care can change **only** drops, loans and cash. It cannot change request volume. This must be stated.
- At zero out-of-pocket cost the consumer price is 0 while the provider price is positive (D05).

### 2.5 Interest-rate and inflation scenarios

**Immediate payer, recipient and constraint.**
- E: `BankAgent.base_interest_rate` feeds `_risk_adjusted_rate`, consumption-loan rates (`economy.py:5416`) and the deposit rate (`update_deposit_rate`).
- E: the treasury pays no interest.

**Differentiated decisions.**
- E: the firm cost of capital is `(δ + rate/52) · capital_cost` in `plan_capital_investment`. With δ = 0.01 per tick, a 3-point annual rate change is about 0.0006 per tick, so this channel is **numerically weak by construction [D, arithmetic]**.
- E: the loan repayment convention is principal × (1 + rate).
- M: there is no household intertemporal response to deposit rates. The deposit sweep is trait-driven.

**Other actors and markets.**
- E: bank interest income funds deposit interest, which reaches depositor cash.
- E: borrower burden feeds defaults and then provisions.

**Delayed feedback.**
- M: there is no price-setting link to rates or expectations.
- E: the inflation target is inactive (W04).

**Outcomes to measure.**
- Originations, investment units, default counts, deposit interest by wealth tercile, realized price indices (after W07/D05).

**Opposite sign is possible.**
- Higher rates raise depositor income (high-buffer households) while raising borrower costs (low-buffer households). The net demand sign is ambiguous.

**Adverse or unintended effects.**
- The rule-driven rate lands mostly on distressed borrowers.

**Blocked or incomplete cases.**
- There is no inflation-generating mechanism beyond shocks and firm pricing rules. A "monetary policy" arm today would mostly be a credit-cost redistribution. The W14 probe comes first.

### 2.6 Public investment

**Immediate payer, recipient and constraint.**
- E: all-or-nothing spending when `cash ≥ budget`.
- E: payment goes through `_collect_misc_revenue`, where a random 0–20% skim returns to government and the rest goes to at most 50 beneficiaries.
- E: the instant additive multiplier increment (N6).

**Differentiated decisions.**
- E: the multiplier is uniform across all firms in `_calculate_experience_adjusted_production`. There is no differential exposure.
- P (§3): a firm `public_capital_exposure` trait.

**Other actors and markets.**
- E: higher output at given labor leads to inventory build-up and then, through the price and production rules, to possibly **fewer hires**.

**Delayed feedback.**
- P: due-date delivery and depreciation (D07).

**Outcomes to measure.**
- Units per worker, employment, prices, beneficiaries' cash concentration, treasury.

**Opposite sign is possible.**
- A productivity gain with unchanged demand can reduce employment in this model.

**Adverse or unintended effects.**
- Beneficiary concentration is a distributional artifact of routing, not of "investment".

**Blocked or incomplete cases.**
- When the treasury is short, spending is zero, which makes a step function.
- There is no input use (L02 abstraction).

### 2.7 Ownership, surplus and governance

**Immediate payer, recipient and constraint.**
- E: `distribute_profits` pays `owners` equally. Entrants have no owners.
- P: recipient rules: private, treasury, workers.

**Differentiated decisions.**
- E: owner spending through `mpc_dividend`.
- P: a worker recipient raises wage-earner cash.
- M: there are no control rights and no objective changes.

**Other actors and markets.**
- The demand composition shifts.
- The public-recipient arm runs through the closure.

**Delayed feedback.**
- Employment churn changes who receives the worker surplus.
- Loss bearing is undefined (D02).

**Outcomes to measure.**
- Dividend incidence, liquid distribution, firm retained cash, investment.

**Opposite sign is possible.**
- Worker payout at firms with volatile employment concentrates gains among stable-firm workers.

**Adverse or unintended effects.**
- Retained cash falls equally in all arms only if `payout_ratio` is held. Otherwise this is a package.

**Blocked or incomplete cases.**
- A no-owner or no-worker firm gives no transmission at all.
- Surplus recipient alone is not an "economic system".

**Probe harness (extension W10-P, new).** For each link marked E:
- Build a one-to-five-tick fixture with two isolated replays differing in a single input.
- Assert the *existence and direction of the mechanical link* at the actor level. Example: "a household at the liquidity cap reduces purchases when tax rises; a buffered one does not".
- Make no aggregate assertion.

These probes are what make later total-effect results interpretable.

---

## 3. Affordable individual differences

### 3.1 What "every person and business individual" requires

**Households.**
- `HouseholdAgent` is a **household unit**. It carries one `age`, one `skills_level`, one job and no size field.
- The user's wording ("every simulated person and business meaningfully individual") is satisfied by making each *simulated decision-making unit* persistently distinct in ways that alter its responses.
- It does **not** require splitting households into persons. That would be a demographic rewrite (X01) affecting labor matching, taxes, equivalisation and performance.
- Recommendation: no rewrite. State in the documentation that the unit is a single-earner household, and that poverty measures are unequivalised.

**Firms.** Each firm is already a unit.

### 3.2 Existing household heterogeneity and its actual readers [I]

**Persistent preferences.** Drawn in `_initialize_personality_preferences` from `Random(seed + id*9973)`.
- `spending_tendency` and `frugality`: read by the batch planner as a trait multiplier clipped to [0.85, 1.15].
- Category preferences, which set `category_weights`.
- `quality_lavishness` and `price_sensitivity`: read in firm choice (`agents.py:684, 780, 981`).
- `saving_tendency`, which sets the deposit buffer and fraction.
- `savings_drawdown_rate`: drives batch drawdown **and** the wage-MPC (N2).
- Healthcare thresholds and base chance.
- Morale parameters.
- `price_expectation_alpha` and `wage_expectation_alpha`.
- `job_switch_threshold`.

**Sampled but with no behavioral reader found.**
- `consumption_budget_share`, `quality_preference_weight` and `reservation_markup_over_benefit`: beyond validation, I found `to_dict` only.
- `savings_rate_target`: read only by a metrics mean (`economy.py:7302`). I have not read `compute_saving_rate`, which may read it in the scalar path.
- These should be declared alongside N1 or wired deliberately. Not every sampled field is live heterogeneity.

**Structured by ID [D]** (`create_large_economy`, lines 184–199).
- `skills = 0.2 + 0.75·i/N`.
- `age = 22 + i % 40`.
- `cash = 500 + 15·(i % 100)`.
- Skill is perfectly rank-ordered by ID. Age and cash are periodic. There is no sampling noise and no joint distribution.
- `purchase_styles` derive from `id % 3`.

**Technology and constraints.**
- `health_decay_per_year`, a three-tier mixture.
- Doctor capacity and wage anchors.

**Changing state.** Cash, deposits, debts, employment and duration, health, the care plan, the awareness pool, tenancy.

**Expectations and learning.** `price_beliefs` and `expected_wage` (EMAs).

**Networks.**
- The awareness pool (household to firm).
- Owner, employer and landlord links.
- There are no household-to-household links.

**Shocks.** `_apply_random_shocks`, and `_deterministic_unit_random` for care demand.

### 3.3 Existing firm heterogeneity [I]

- A three-class `personality` sets `investment_propensity`, `risk_tolerance`, the price, wage and R&D adjustment rates, and hire and fire limits.
  - `risk_tolerance` is read at `agents.py:3174–3190`.
  - I found **no reader** for `investment_propensity` beyond `to_dict`.
- `payout_ratio` ~ U(0, 0.5).
- For non-baseline firms: markup, unit cost and inventory targets.
- Sector, quality, capital and the loan stack.

Firm individuality is mostly *class plus jitter*. Nothing differentiates firms' response to tax, credit or public-capital policy except their cash state.

### 3.4 Why IDs or fresh per-tick noise are not enough

- A unique ID changes nothing that an actor *does*.
- Per-tick noise averages out and creates no persistent type. A household that is "cautious" this tick and "bold" the next is not an individual.
- Per-tick noise also damages arm pairing.
- Individuality means **persistent parameters that enter decision rules**, plus path-dependent state.
- Conversely, uniqueness must **not force outcomes apart**. If two households are both at the liquidity cap, both must spend exactly their cap whatever their traits. If the queue is full, both wait.
- Traits shape *desired* actions. Constraints and settlement determine *realized* ones. The acceptance test for this is in §3.6.

### 3.5 Smallest additional traits

Each trait answers one policy question. All are **[A, H]**: uncalibrated hypotheses with mandatory sensitivity.

**Household traits.**

1. **`tax_salience` λ_i** (W08 extension)
   - **Policy question.** Do tax changes reach plans unevenly?
   - **Units and bounds.** Dimensionless, [0, 1].
   - **Response rule.** Planned wage income is `wage − λ_i · expected_tax_i`.
   - **Default.** λ ≡ 1, equal to W08. A heterogeneity arm uses Beta(4, 2) rescaled [A].
2. **`buffer_target_weeks` b_i**
   - **Policy question.** Who cuts spending first under a tax or benefit change?
   - **Units and bounds.** Weeks, [1, 12].
   - **Response rule.** When liquid resources fall below `b_i × last spending`, scale the *discretionary* part of `base_budget` by `liquid / (b_i · spend)` with a floor of 0.7 [A]. Above the target there is no change.
   - **Default.** Reuse `deposit_buffer_weeks` (3–10). **No new draw**; it is a new reader only.
3. **`care_cost_sensitivity` κ_i** (W13 sensitivity only)
   - **Policy question.** Does out-of-pocket price defer non-urgent care?
   - **Units and bounds.** Dimensionless, [0, 1].
   - **Response rule.** When health is above `healthcare_urgency_threshold`, multiply the request probability by `1 − κ_i · min(1, oop_cost / (0.25 · liquid))`. There is no effect when the out-of-pocket cost is 0 or the case is urgent.
   - **Default.** κ ≡ 0 (current behavior). The arm uses U(0, 0.6) [A].
4. **`benefit_reservation_weight`**
   - **Policy question.** Do benefits shape job acceptance heterogeneously?
   - **Response rule.** Give the already-sampled `reservation_markup_over_benefit` its documented reader: `reservation ≥ benefit × markup_i` for the first `unemployed_market_anchor_ticks`.
   - **Default.** Off, which equals current behavior.

**Firm traits.**

5. **`tax_pass_through` θ_f**
   - **Policy question.** Who bears business tax?
   - **Units and bounds.** Dimensionless, [0, 1].
   - **Response rule.** The target markup is raised by `θ_f · (profit_tax_paid / revenue)`, smoothed by the firm's own `price_adjustment_rate`. The increase is still subject to the existing floors and price stabilization.
   - **Default.** θ ≡ 0. The arm uses U(0, 0.5) [A].
6. **`public_capital_exposure` e_f** (W11 only)
   - **Policy question.** Which firms gain from public investment?
   - **Units and bounds.** Dimensionless, [0.5, 1.5], with sector mean 1.
   - **Response rule.** `multiplier_f = 1 + e_f · (M − 1)`.
   - **Default.** e ≡ 1.

Traits 2 and 4 add no new randomness. With traits 1, 3, 5 and 6 at their defaults, behavior is unchanged. That gives baseline-identical fingerprints with all flags off.

**Distributions and correlations [P].**
- The draws are independent of `household_id` order, skill, age and initial cash by default.
- A sensitivity arm tests a declared rank correlation ρ ∈ {−0.3, 0, +0.3} between `b_i` and initial cash. This is imposed by a Gaussian copula on keyed uniforms.
- **No trait is hard-wired to income, age or any protected characteristic.** There is within-group variation at every income level by construction. Reports show outcomes by trait tercile *within* wage quartile.

**Optional remedy for ID-structured endowments [P, flagged, off by default].**
- `CONFIG.households.endowment_scheme = "legacy" | "keyed"`.
- Under `keyed`, skill, age and cash are permuted by a keyed shuffle. The marginal distributions are unchanged, and the ID–skill monotonicity is broken.
- This changes baselines, so it must be declared as an intended divergence.

**Initialization.**
- `u = Random(f"{seed}|trait|{name}|{kind}|{entity_id}").random()`.
- String seeds use all bits under seeding version 2 [X: Python docs, fetched].
- Never use `hash()`, which is process-salted for `str`.
- Arithmetic seed offsets are an anti-pattern [X: NumPy docs, fetched; F2 and N3 are local instances].
- Draw each trait once at construction, or at entry for new firms, keyed by `firm_id`.

**Persistence.**
- Add the fields to `to_dict` and the manifest, recording the distribution name, its parameters and the scheme version.
- Traits never change after T0, so both arms share them. That is pre-policy pairing by construction.
- The fingerprint includes the trait arrays.

**Scalar, batch and performance-mode behavior.**
- One helper per rule takes arrays, and the scalar path calls it with length-1 arrays. This guarantees parity by construction.
- Performance mode applies the traits whenever plans are recomputed (`tick % 5`). This is documented, and the feature's cadence is not reduced to make it look cheap.

**Cost estimate (not a benchmark).**
- One float64 array per trait: 80 kB per trait at 10,000 households.
- One or two vector operations per planning pass.
- No per-agent Python objects, classes or calls.
- One behavior function per *rule*, never per individual.
- To be measured against the 5% budget.

### 3.6 Acceptance and sensitivity

1. Flags off gives identical legacy fingerprints.
2. Trait draws are equal across processes and across `PYTHONHASHSEED` values.
3. **Constraint dominance.** Two households with different traits, both at the liquidity cap, have identical realized spending. Two patients behind a full queue wait equally.
4. Batch equals scalar for each helper.
5. **Sensitivity.** Run each trait's spread at {0, default, 2×}. Report whether the subgroup sign pattern survives. A result that exists only under one spread is labelled trait-dependent.

Behavioral diversity is a hypothesis under test. Its presence does not make the model more realistic. The direction "MPC varies with liquid resources" has external support [X: Jappelli and Pistaferri, fetched abstract]. None of the numbers above do.

---

## 4. Subagent feasibility and boundaries

### 4.1 What existing LLM code does [I]

- **`llm_government.py` and its server scheduling.** This is the only live integration. It works from a frozen snapshot, with one decision in flight, a canonical schema sanitizer and safe-boundary application (per wiki and source layout).
- **`run_household_llm_tester.py`.** It **observes only**. One shadowed household is narrated each tick at temperature 0.75–0.8, and "the simulation makes all decisions". It produces prose and periodic "beta feedback". It has no actions, no cache and no replay.
- **`llm_firm.py` (`LLMFirmAdvisor`).**
  - It handles a single firm. It computes a heuristic baseline plan on a clone and asks for a small JSON override restricted to `ALLOWED_DECISION_FIELDS`: price, wage offer, expected sales, R&D rate and inventory weeks.
  - It validates the numeric type and holds a decision for several ticks.
  - **Qualification.** I read only `_validate_decisions`, which checks field whitelist and numeric type. Bounds and clamping, if any, happen elsewhere, and I did not verify them.
- **`run_all_archetypes.py`.** Archetype selection: frugal, spendthrift or average, chosen by trait medians.

None of these is a population mechanism.

### 4.2 Assessment of the three options

**(a) Development-time coding agents per mechanism domain.**
- **Feasibility.** High. The contract, the ticket template and the ownership map already exist.
- **Coordination difficulty.** **Moderate to high.** All the classes live in `agents.py`, and the effective behavior lives in `economy.py` batch paths. The risk is shared-file collisions and two-sided contracts.
- **Recommendation.** Proceed, in stages. Workers deliver pure helpers plus call-site requests. One integration owner edits `Economy.step`, the settlement paths, config, metrics and `to_dict`.

**(b) Development-time agents representing sampled individual cases, as adversarial reviewers.**
- **Feasibility.** High, and read-only.
- **Coordination difficulty.** Low. The agents never edit code. They output findings against trace files.
- **Recommendation.** Proceed first. It is the cheapest option and directly serves the "individual" goal.

**(c) Live LLMs deciding for one simulated individual.**
- **Feasibility.** Technically feasible for tens of agents.
- **Coordination difficulty.** High: nondeterminism, latency, prompt and version drift, action validity, and information leakage (L06).
- **Recommendation.** Run only as an optional research arm under the protocol in §4.4. Never use it as the default.

### 4.3 Staged trial

**Stage 0: shared artifacts, produced by the integration owner.**
- Contract v2 containing the corrected §1 rules.
- A trace exporter, which is a **runner-side** script and needs no engine change. For K sampled entities it dumps the per-tick `to_dict` ledger and state rows, and adds one new field, `decision_inputs`, holding the inputs to the planning call.

**Stage 1: case reviewers under option (b).** There are eight read-only agents. Each receives one entity's trace from a baseline run and from a 15% versus 40% start-regime pair. The entities are sampled by stratum, not cherry-picked:
- two households at the liquidity cap;
- two buffered households;
- one chronic-illness household, from the high decay tier;
- one owner or CEO household;
- one thin-cash private firm;
- one baseline firm.

*Task for each reviewer.*
- Given only what this actor could observe, list decisions that are implausible, inert traits, and information the rule used that the actor could not have known.
- Cite `path:symbol` for every claim.
- Propose at most three changes, each with its affected counterparties.

*Guardrails.*
- Reviewers see no aggregate outcomes beyond what the actor observes.
- They have no policy goal.
- They must report harms to counterparties from their own proposals.

*Output.* A findings table. The coordinator triages the findings into existing W-IDs.

**Stage 2: two coding agents under option (a), sequential.**
- A household worker implements the W08 `expected_wage_tax` helper and the §3.5 trait helpers, as a pure module plus tests.
- A government worker implements the D08 `pay_rebate` planner and the F1 probe, with a fix proposal.

*Exact bounds.*
- Each worker's owned symbols are new pure functions in a new module.
- Read dependencies are listed in the ticket.
- Call-site edits are **requests** to the owner.

*Integration order.*
1. F1 probe.
2. W08 helper.
3. Closure.
4. Traits.

After each step the owner runs:
- the D11 exactness gates;
- the W10-P link probes;
- a **counterparty regression check**: subgroup outcomes for *other* actor classes must be reported, so that no locally better household rule silently worsens firm solvency or treasury accounting;
- the performance budget.

**Stage 3: bank and healthcare workers.** These are dispatched only after Stage 2 closes cleanly.

**Rules against local gaming.**
- A ticket's acceptance cases never include a preferred aggregate sign.
- Workers are judged on fidelity (mechanism, source, accounting, parity, runtime), never on GDP, Gini or any policy score.
- No worker may change a metric definition.
- A change that improves its own actor's outcomes must show the other-side ledger.

**Performance budget and rollback.**
- The cumulative 5% median and p95 budget applies to each integrated stage. This is the contract's engineering target.
- Everything sits behind default-off flags.
- Rollback means turning the flag off and reverting an isolated patch.
- Fingerprints with flags off must equal the pre-stage baseline.

### 4.4 Optional live-LLM micro-trial under option (c), if wanted later

**Actors and information.**
- n ≤ 20 households, sampled by stratum.
- The simulated actors pursue **local** goals ("meet needs, keep a buffer, keep your job") under their own budget and information constraints.
- The prompt contains only what the actor can observe: own ledger, own prices paid, posted offers in its awareness pool, and announced policy.
- The prompt contains no aggregates beyond public ones, no GDP, no instruction about policy desirability, and no contact with other agents.

**Actions.**
- A restricted JSON:
  - `spend_scale` ∈ [0.7, 1.3], applied to the rule-based budget;
  - `accept_min_wage_scale` ∈ [0.8, 1.2];
  - `seek_care_now` ∈ {true, false}, for non-urgent care only.
- The engine clamps and validates the JSON. **Settlement is unchanged**: the liquidity caps, queues and matching still bind.
- An invalid response or a timeout triggers the **deterministic rule-based fallback**, and the event is logged.

**Freezing and replay.**
- The model ID, the prompt hash, temperature and sampling parameters are recorded in the evidence file.
- The cadence is every c = 4 ticks, with decisions held in between.
- Responses are cached by `sha256(model | prompt_version | observation_json)`. Every analysis run is a **replay from the cache**, so results are reproducible and free to re-run.
- Calls happen between ticks, as `llm_firm.py` already does, and never inside `step()`.

**Variance decomposition.**
- For a fixed seed, draw R ≥ 5 independent response sets, giving the **model variance**.
- For a fixed cached response policy, vary the seeds, giving the **shock variance**.
- Report both. The LLM-versus-rule difference is interpretable only if it exceeds the model variance.

**Call count.**
- `calls ≈ n_agents × ceil(T_post_warmup / c) × R_resamples × arms × seeds × (1 − cache_hit_rate)`.
- Example of the formula only: 20 × 26 × 5 × 2 × 4 ≈ 20,800 uncached calls.
- This count scales linearly in every factor, which is why thousands of concurrent agents as a default is rejected.
- I make no claim about cost or latency.

**Limits on interpretation.**
- LLM choices are a behavioral *hypothesis generator*. They are not validated human behavior [X: Horton et al., fetched abstract, reporting qualitative replication and conceptual caveats; Park et al., fetched abstract, 25 agents, a believability focus, no accounting constraints].
- Findings feed §3 rule proposals, which are then tested cheaply.

---

## 5. Revised queue

None of this is approved. The proposed extensions are marked **ext** in the item descriptions below. The order evaluates downstream and subgroup effects early.

**Step 1. W10 diagnostic: ready.**
- *Scope.* Two isolated replays. A declared fingerprint covering metrics, the four `to_dict` families, the misc pool, queued firms and trait arrays. An RNG-surface inventory that includes the NumPy tie-break cache, `_deterministic_unit_random`, F2 and N3.
- *Acceptance.*
  - Identical arms give equal fingerprints at every tick (2 seeds × 80 ticks).
  - A pair with a lever change at T0 is equal through T0−1.
  - Runtime is recorded.
  - The limits statement says that `to_dict` is not restart state.
- *Depends on.* W03.

**Step 2. F1 probe (ext of W06/W09): ready.**
- *Scope.* One-tick fixture for firm profit-tax rates and property tax in the `step()` path.
- *Acceptance.* The realized rates per firm are printed. The probe asserts whether the brackets differ and whether property tax is positive. The **decision** to fix goes to the coordinator.
- *Depends on.* Nothing.

**Step 3. W06a cash and claim inventory: ready.**
- *Scope.* Report-only `S_t`, `G_t` and the claims table per D01, with the D11 gates.
- *Acceptance.*
  - A transfer paid from 0 to −10 leaves ΔS = 0 with **no overdraft line**.
  - E03-style unfunded entry shows up as exactly one named line.
  - The shocks line equals the realized sum.
  - The unexplained residual stays within the absolute tolerance every tick.
  - A deliberately injected unmatched +1 is detected.
- *Depends on.* W01/W02, which are done.

**Step 4. W07a liquid and partial-position percentiles, with subgroups (ext): ready.**
- *Scope.* `eval_liquid_*` and `eval_partial_fin_position_*`, observed after `finalize_tick_ledger`. The debt list is named, and the measure is never called net worth.
- *Subgroup keys (ext).* Membership is frozen at T0−1: wage quartile, buffer tercile, employment status, owner flag, health tercile.
- *Acceptance.*
  - The E04 replay.
  - A shift between cash and deposits leaves the stocks invariant.
  - Membership is unchanged after T0.
  - Legacy keys and the forecasting columns are untouched.
- *Depends on.* W03.

**Step 5. W09 inventory and labels: ready.**
- *Scope.* Declare the household toggle inert in `CONTROL_CAPABILITIES`. Declare the unread traits listed in §3.2. Declare the benefit-to-wage-floor link. The UI text follows the W04 treatment.
- *Acceptance.*
  - Behavior check: flipping the household toggle leaves the fingerprints equal.
  - The evidence file lists the statuses.
- *Depends on.* W03.

**Step 6. W10-P transmission probes (ext): ready after step 1.**
- *Scope.* The §2 link fixtures.
- *Acceptance.*
  - For each E link there is one actor-level directional assertion.
  - For each M link there is a test documenting *no response*. Example: a buffered household's plan is equal at 15% and 40%.
  - There are no aggregate assertions.
- *Depends on.* Step 1.

**Step 7. W08 specification, then helper: B.**
- *Scope.* The `expected_wage_tax` pure function. Announce and learn-only modes.
- *Acceptance.*
  - (a) Startup: before any settlement the plan uses the computed tax, not 0.
  - (b) Rate 0 gives exactly 0, and 0 → 0.2 gives the bracketed value.
  - (c) 0.15 → 0.20 → 0.40 before one planning boundary equals a single 0.40 computation.
  - (d) Moving bracket: a household with a fixed wage crosses p50 after others' wages change, and its expected tax follows last tick's cut-points.
  - (e) Unemployed gives 0. Re-employed gives the new-wage value.
  - (f) Batch equals scalar for this signal, with the N2 test documenting the unchanged saving gap.
  - (g) Performance mode changes at the next `%5` tick.
  - (h) Flag off gives an identical fingerprint.
  - (i) No aggregate sign test.
- *Depends on.* Steps 4 and 6.

**Step 8. W12 specification: B.**
- *Scope.* `hold`, and `rebate` per D08.
- *Acceptance.*
  - Rebate tick: treasury Δ = −R, Σ household Δ = +R, ΔS = 0, and R is inside `tick_spending`.
  - Cash ≤ 0 gives R = 0.
  - Negative B* is handled by `max(B*, 0)`.
  - The planner term reads the lagged rebate, and the "liquidity-only" variant is labelled.
  - `hold` gives E08 payments of 0.
  - The financing gap is reported as a stock, never summed, and never added to S.
- *Depends on.* Step 3.

**Step 9. W07b income, poverty, price and output: B.**
- *Scope.* The ring buffer, the ledger split and the three price and quantity series per D04/D05.
- *Acceptance.*
  - The ring buffer equals a brute-force four-tick mean, including the startup coverage flags.
  - Liquidation and loan or deposit principal are excluded.
  - A free-care tick gives a consumer healthcare price of 0, a positive producer price and unchanged visits.
  - An absent reference category is flagged, not imputed.
- *Depends on.* Step 4, and the ledger-key decision.

**Step 10. §3 trait helpers (ext of W08 and W13): B.**
- *Scope.* Traits 2 and 4 (readers only) first. Then λ, κ and θ behind flags.
- *Acceptance.* §3.6 items 1–5.
- *Depends on.* Steps 7 and 1.

**Step 11. First tax comparison: after steps 1–8.**
- *Scope.* 15% versus 40% headline rates inside the existing brackets, under `hold` and `rebate`. Subgroup tables. Primary outcomes and the stopping rule fixed before unblinding.
- *Acceptance.*
  - Paired differences with both absolute and relative tolerances.
  - A sign table across closure × W08 mode × trait spread.
  - "Assumption-dependent" labels where signs flip.
  - No composite winner.
- *Depends on.* Steps 1–8.

**Step 12. W06b/c: B.**
- *Scope.* Atomic equal-commitment entry. The exit waterfall through the W01 helper. The resolution account.
- *Acceptance.*
  - Preflight failure leaves **zero** mutations, tested with a bank that cannot honor the withdrawal.
  - A treasury-funded loan at exit is repaid to the treasury.
  - Negative-cash exit is booked to the declared account, not to the bank.
- *Depends on.* Step 3, and a user choice.

**Step 13. W13: C→B.**
- *Scope.* The 2×2 payer × pricing design per D09, with κ as a sensitivity.
- *Acceptance.*
  - The patient-pay arm asserts both subsidy settings are off.
  - Completed visits, out-of-pocket spending and provider receipts are reported separately.
  - Queue and capacity behavior is unchanged.
- *Depends on.* Steps 8, 9 and 10.

**Step 14. W14: C→B.**
- *Scope.* A map of every reader of the rate. A ± rate probe through W10-P before any controller. The lag, the bounds and the units: annual rate divided by 52 per tick.
- *Acceptance.* The probe reports originations, investment and defaults by subgroup. If the link proves weak, that is documented rather than "fixed" to get an effect.
- *Depends on.* Steps 6 and 9.

**Step 15. W11: B/C.**
- *Scope.* Due-date slots per D07, and `e_f` exposure.
- *Acceptance.*
  - Spending at t first affects production planning at t+D+1.
  - The cohort sum is conserved: Σ delivered equals Σ spent × efficiency.
  - Spending for longer than D ticks loses no cohorts.
- *Depends on.* Step 8.

**Step 16. W16: C→B.**
- *Scope.* Recipient rules with the no-owner, no-worker, entrant and loss-bearing cases defined.
- *Acceptance.* Identical firm rules across arms, asserted through the plan fingerprints at T0.
- *Depends on.* Steps 12 and 8.

**Step 17. W17, W15 and W18: C.**
- *Scope.* Unchanged from the audit. W17 adds interaction (factorial or Latin-hypercube) sensitivity on top of one-at-a-time. The Beveridge relationship is treated as a diagnostic only.

Steps 1–6 can overlap in design. Code that touches `Economy.step`, the metrics or the evidence file is serialized through the integration owner.

---

## 6. Evidence catalog and limits

### Current-source citations used

All marked [I] or [D] from reading. Line numbers are approximate; symbols are authoritative.

- `backend/agents.py`:
  - `HouseholdAgent._initialize_personality_preferences`
  - `_get_purchase_tie_break_noise`
  - `_deterministic_unit_random`
  - `should_request_healthcare_service`
  - `_sample_annual_visit_count`
  - `plan_labor_supply`
  - `FirmAgent.__post_init__` and `set_personality`
  - `plan_capital_investment`
  - `plan_wage` (wage floor)
  - `GovernmentAgent.plan_taxes` and `apply_fiscal_results`
  - `BankAgent.base_interest_rate` readers
- `backend/economy.py`:
  - `_batch_plan_consumption`
  - `apply_sector_subsidy_payment`
  - `_build_firm_tax_snapshots`
  - `Economy.step` phases 7–11.7
  - `_choose_healthcare_provider`
  - `_process_healthcare_services`
- `backend/policy_schema.py`
- `backend/run_evidence.py`, read at symbol level only
- `backend/tools/runners/run_large_simulation.py::create_large_economy`
- `backend/tools/llm/{llm_firm.py, run_household_llm_tester.py}`

**Wiki drift to report.** The where-to-change page does not mention `run_evidence.py`, F1, or the benefit-to-wage-floor coupling.

### External sources

- **NumPy, "Parallel random number generation": fetched this session.**
  - Supports: seed + id offsets are flagged unsafe; keyed sequences are preferred.
  - Does not support: the independence of EcoSim's purposes.
- **Python `random` documentation: fetched this session.**
  - Supports: string seeds under version 2 use all bits; the reproducibility guarantee covers `random()`.
  - Limitation: the page is silent on `hash()` salting. The salting claim comes from general Python knowledge and was not fetched.
- **Jappelli and Pistaferri, AEJ: Macro 2014: abstract fetched.**
  - Supports: MPC is heterogeneous and higher at low cash-on-hand.
  - Does not support: any EcoSim MPC value or the design of the traits.
- **Fuest, Peichl and Siegloch, AER 2018: abstract fetched.**
  - Supports: workers can bear a material share of business tax, unequally.
  - Does not support: θ_f values, or any sign in this model.
- **Horton, Filippas and Manning, arXiv 2301.07543: abstract fetched.**
  - Supports: LLMs as *exploratory* simulated agents, with conceptual caveats.
  - Does not support: validity as human behavior.
- **Park et al., arXiv 2304.03442: abstract fetched.**
  - Supports: generative-agent architecture demonstrated at 25 agents.
  - Does not support: economic accounting fidelity or behavior at scale.
- **BLS Beveridge curve page: fetched, data table only.**
  - Supports: the series exist.
  - Limitation: the page gave no interpretive text. For the sign I rely on the audit's S5.
- **RAND HIE brief RB-9174 and the CBO distribution report: inaccessible this session (HTTP 403).**
  - Cited only through the audit's S4.
  - Any elasticity: none is used.
- **Bank of England money creation, BLS CPI, BEA, OECD and WHO: not re-fetched this session.**
  - Supports: as characterized in audit S1–S4.

Sources support principles only. They do not validate any coefficient, threshold, sign or real-world prediction in this document.

### Unresolved genuine modeling choices (user)

1. Whether to declare a monetary-authority account, or to keep a signed treasury with no "creation" label (D01).
2. Entry equity rights and the fiscal status of the exit-loss resolution account (D02).
3. Tax information mode: announce or learn-only. Whether rebate income enters plans (D03, D08).
4. Headline closure: `hold` or `rebate`. Both are reported.
5. Whether the benefit-to-firm-wage-floor coupling (×1.5) stays bundled, or is pinned in benefit experiments.
6. Whether to fix F1 so that progressive business tax becomes real, or to label it inactive.
7. The healthcare design: the payer-only contrast or the package. Whether a demand response (κ) is admissible.
8. Whether to adopt `endowment_scheme = "keyed"`, which changes baselines, or to keep the ID-structured endowments as disclosed.
9. A reference economy for W17, if any.

### Engineering defaults I selected [P]

- Equal-commitment owners.
- A due-date dictionary for the pipeline.
- A four-slot ring buffer.
- Absolute plus relative tolerances.
- String-keyed trait streams.
- Traits stored as arrays with default-off flags.
- Reviewer agents before coding agents.
- A live LLM only through a cached replay arm.

### Limits of this proposal

- Nothing here was executed.
- F1, F2 and the unread-trait list come from source reading with incomplete greps, and they need coordinator probes.
- W01–W05 do not establish full stock-flow consistency, a correct CPI, monetary policy, healthcare regimes or intervention branching.
- Nothing above should be read as claiming otherwise.
