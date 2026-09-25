# Fable 5.1 audit: `docs/ECONOMIC_AGENT_RULES.md` v1.0

## 1. Verdict

**The rules are usable after specified corrections.** The phase table, market rules and limitations register match the working-tree source closely. The qualifications the brief asked about are already stated correctly:

- the 9.5 loan-before-wage ordering, including the inaccurate nearby comment;
- planners that have side effects;
- dividends paid after the statistics update;
- `govt_backed` meaning treasury-funded rather than a guarantee;
- `is_baseline` not proving treasury ownership;
- the `1 + annual_rate` loan formula;
- the inactive inflation target.

I found no claim that turns a known defect into a permanent law.

The corrections fall into three groups. The rules leave out several current behaviours that matter for the two headline comparisons, progressive tax and healthcare financing (AR-01 to AR-05). Two wording errors misstate source (AR-06, AR-07). Three integration defects affect how the documents fit together (AR-08 to AR-10). None requires restructuring the document.

This is a source reading only; nothing was executed.

## 2. Actionable findings

### AR-01: Tax-to-consumption transmission path is not stated (missing rule, high)

- **Claim:** §3 phase 2 says "Planned wages and observed market signals are not identical to settled wage receipts". M06 and R08 require a transmission chain for tax changes.
- **Evidence:**
  - `backend/economy.py` `_batch_plan_consumption` builds budgets from gross `h.wage` (lines 795 and 833–841). It takes no tax input.
  - Wage tax is debited only in `_batch_apply_household_updates` (line 1212).
  - A tax change therefore reaches consumption only through later cash, the `accessible_liquidity` cap and drawdown (lines 852–867).
  - `docs/ECONOMIC_WORK_READINESS.md` W08 already records this, but the rules do not.
- **Why it matters:** This is the first link in every progressive-tax proposal. Independent household and government writers will otherwise disagree about whether a net-wage response already exists, or double it.
- **Correction:** Add to phase 2 or K03: "Consumption budgets use gross wage, benefit level and last dividend income. Wage tax currently affects spending only via settled cash and liquidity in later ticks. A take-home-income response is a proposed link (W08)."

### AR-02: "Progressive wage taxation" is preserved but never described (missing current behaviour, medium)

- **Claim:** R02 and M06 say "Preserve progressive wage taxation… distinguish headline rate, bracket rules, assessed liability and actual revenue."
- **Evidence:** `GovernmentAgent.plan_taxes` (agents.py 6897–6920):
  - brackets are percentiles of the current tick's wage distribution, which includes zeros for the unemployed;
  - the selected rate applies to the whole wage, not marginally;
  - rate = `wage_tax_rate × wage_bracket_scalers[...]`.
  
  The scalers are not a `POLICY_SCHEMA` lever; `policy_schema.py` `TAX_LIMITS` exposes only three flat rates. The phase-10 debit has no cash check, so assessed and collected wage tax are identical by construction.
- **Why it matters:**
  - A household's rate changes when other households' wages or employment change.
  - Bracket boundaries create notches.
  - Distinguishing "assessed liability and actual revenue" suggests a collection gap that does not exist for wage tax.
  - A "progressivity" comparison has no canonical lever.
- **Correction:** Add two sentences of current behaviour to M06 covering these points. Label notch and relative-threshold effects as a disclosed limitation, not a bracket-redesign mandate.

### AR-03: M03 omits payment and queue facts that healthcare proposals depend on (omitted qualification, medium)

- **Claim:** M03 says "Provider queues, worker visit capacity, payment support and medical lending constrain delivery."
- **Evidence:** `_process_healthcare_services` (economy.py 6243–6422) and `apply_sector_subsidy_payment`:
  - **(a)** Public support equals `_sector_subsidy_rate` only when `sector_subsidy_target == "healthcare"`. Otherwise it is `healthcare_visit_subsidy_share`, which defaults to 0.0 (config.py 668). The baseline is therefore fully patient-paid.
  - **(b)** `apply_sector_subsidy_payment` returns 0 whenever `government.cash_balance <= 0` (economy.py 1061), and it is capped per tick. Transfers can push the treasury negative, so visit support can vanish endogenously.
  - **(c)** An unaffordable visit with no loan drops the patient from the queue (6356–6379). This is refusal, not waiting.
  - **(d)** The scan origin for non-priority patients rotates by `(current_tick + firm_id) % queue_len` (6304). The queue is not first-in-first-out (FIFO).
- **Why it matters:** Point (b) couples the transfer arm to the healthcare arm. Points (c) and (d) change what "waiting time" means in R05 and R09 metrics.
- **Correction:** Add (a) to (d) as current behaviour in M03. In M06, note that the cash-limited items include sector and visit subsidies, not only "some investments".

### AR-04: The miscellaneous pool's distributional behaviour is understated (omitted qualification, medium)

- **Claim:** Phase 11.5–11.7 says "Some spending enters an abstract miscellaneous pool"; K06 calls this "aggregate shortcuts".
- **Evidence:**
  - `_collect_misc_revenue` (economy.py 6080+) skims a random 0–20%. Its RNG key includes `int(amount * 100)`, so the key depends on policy.
  - `_misc_firm_redistribute_revenue` pays the whole pool equally to at most 50 randomly chosen beneficiary households (6036–6049, 6069).
  - Inflows include government infrastructure, technology, social and bond spending, firm R&D, education spending and construction cost.
  - `_recycle_capital_investment` (5371–5387) pays firm capital expenditure equally to all households.
- **Why it matters:** Any spending-side or tax-use comparison mechanically moves the inequality metrics in K05 through a handful of households. The amount-keyed draw breaks matched disturbances, which undermines the matched arms R09 requires and adds to the evidence gap in K07.
- **Correction:** Name both facts in K06, or in a new K09. Require proposals that use public spending or R&D to state how they treat these routes.

### AR-05: Performance budget does not disclose that measured noise already exceeds it (unclear decision rule, medium)

- **Claim:** §6 sets "at most 5% added median and p95… Account for measurement variability."
- **Evidence:** `docs/reviews/ECONOMIC_CONCRETE_PERFORMANCE.md` line 27:
  - 1,000-household baseline medians differed by about 6.5% between repetitions;
  - firm counts also diverged between arms.
- **Why it matters:** Under the current protocol, the threshold cannot distinguish a pass from a fail at 1,000 households. Writers' "cost estimate" sections cannot be judged against it.
- **Correction:**
  - State that noise fact in the budget bullet.
  - Add a decision rule. For example, use interleaved paired repeats, make the 10,000-household cell the gating cell, and report the 1,000-household cell as "within noise" unless the increase exceeds the measured repeat range.
  - Keep 5% explicitly labelled as chosen, not measured. That label is already present.

### AR-06: Goods requests are keyed by good name, not category (source error, low–medium)

- **Claim:** M01 says "a category request uses suppliers ordered by price and ID."
- **Evidence:** In `_clear_goods_market`, `goods_to_indices` is keyed by `firm.good_name` (3840–3844). Factory good names are unique per firm (`BaselineFood`, `FoodCo1`…). The executed category planner, `_plan_category_purchases`, emits firm-ID targets. Good-name targets arise only in the legacy fallback.
- **Why it matters:** A firm or household writer may assume category-level price competition happens at clearing. In fact it happens earlier, in household awareness and choice.
- **Correction:** Replace the sentence with: "a good-name request (legacy path) is spread across firms sharing that name, ordered by price and ID; category choice is made earlier in household planning."

### AR-07: The phase-10 "direct government loans" are firm loans (ambiguous source claim, low)

- **Claim:** Phase 10 says "Household update path services direct government loans, then applies household income…"
- **Evidence:** `_batch_apply_household_updates` (1160–1170) services `firm.government_loan_remaining` from firm cash. The same loop also debits CEO salary (3 × median wage) from firm cash with no liquidity check (1199–1202).
- **Correction:** Say "firm direct-government loans". Add that CEO salary is a phase-10 firm debit outside the phase-5 wage bill, although the phase-7 profit snapshot includes it (4392–4397).

### AR-08: ID collision and stale anchors in the working contract (conflicting requirement, medium)

- **Claim:** The template requires "Applicable binding rules (R-IDs)". The contract uses `[R01]`–`[R04]` as source-link labels (§3, §4, §5 and its source anchors).
- **Evidence:**
  - Contract lines 58, 76, 86, 104 and 170–179 define those labels as links.
  - The links pin commit line ranges (`economy.py#L1405-L2160`, `#L789-L864`).
  - The working-tree spans in `ECONOMIC_AGENT_RULES_SOURCE.json` are 1406–2148 and 736–1043.
  - The rules themselves say the commit alone is not the baseline.
- **Why it matters:** "[R01]" in a proposal is ambiguous between the two documents. The anchors point at code other than what writers receive.
- **Correction:** Rename the contract anchors, for example to `[C-S1]`–`[C-S4]`. Point them at symbols plus the JSON index.

### AR-09: Template lacks the fields R08 and R09 require (integration gap, low–medium)

- The template has no line for financing or revenue closure. It has none for execution mode and observation time. It has no "hypothetical" link label, only "Existing versus proposed links".
- R01 and the template mention sampled-case reviewers, but the §7 assignment table has no sampled-case row.
- **Correction:**
  - Add three template lines under §3 and §5.
  - Add the "hypothetical" label.
  - Add a sampled-case row to §7 of the rules. Its scope is a general mechanism or counterexample. It reads the same counterparties as its role.

### AR-10: Global-RNG dependence of initial ownership is not disclosed (omitted qualification, low)

- **Evidence:** `create_large_economy` assigns owners with unseeded module-level `random.randint` and `random.sample` (run_large_simulation.py 253–260). Reproducibility depends on the caller seeding the global state. The server restores a session state (server.py 1854), and the benchmark tools call `random.seed`.
- **Why it matters:** §6 says "must not reseed global RNGs", and R09 says "hold initialization common". A direct-library comparison that skips the caller's seeding gets different owners, and therefore different dividend income, in each arm.
- **Correction:** Add one sentence to the §2 factory paragraph and to K07.

No blocker was found in the change-control design. "Routine in-scope choices" versus "material new modeling preference" is workable. One illustrative example of each would make escalation more consistent. This is optional.

## 3. Coverage

| Contract / path | Checked | Result |
|---|---|---|
| `Economy.step` 1406–2148, every row of the §3 table | Read in full | Order, conditionals, 5/10/50-tick cadences and the audit start all match. The setup row understates one thing: bailouts and public works execute in setup when stabilizers are on. They are not just "budgets". |
| `_batch_plan_consumption`, scalar `plan_consumption` | Read | K03 confirmed: the scalar path uses `compute_saving_rate()`, the batch path uses `savings_drawdown_rate`. See AR-01. |
| `_batch_apply_household_updates`, `_collect_bank_loan_repayments`, `_process_bank_deposits` | Read | The phase 9.5 and 10 claims, the single path for registered medical loans, and the rate-sensitive deposit sweep are confirmed. See AR-07. |
| `_clear_goods_market` | Read | Sequential allocation confirmed. No cash debit at clearing. The service effective-price write happens during clearing. See AR-06. |
| `plan_taxes`, `plan_transfers`, `adjust_policies`, `_build_firm_tax_snapshots` | Read | K01 is accurate. With no `cash_balance` in the snapshot, every firm falls into the "poor" bracket. With no `good_category`, property tax is always empty, although the consumers exist. See AR-02. |
| Healthcare enqueue, prioritisation and processing | Read | M03 is accurate as far as it goes. See AR-03. |
| `BankAgent` lending, repayment, write-off and deposits | Read | M05 and the reserve-constrained lending claim are confirmed. `lendable_cash` checks appear at the origination sites. |
| `policy_schema.py`, `server.py` `update_config`, `_apply_config_updates`, `_normalize_runtime_policy_updates` | Read | Paused updates apply immediately and running updates are buffered, as the rules say. `update_config` is the owning symbol but is missing from the JSON index. |
| `create_large_economy` | Read | §2 factory paragraph confirmed. See AR-10. |
| JSON symbol spans | Spot-checked 16 | All match. **SHA-256 hashes were not verified**, because no execution tools were available. |
| Template, contract, `AGENTS.md`/`CLAUDE.md`, `docs/README.md` | Read, except `CLAUDE.md`, where only the matching section heading was seen | Version, 3-change limit, decision vocabulary and 5% text are consistent across the documents read. `AGENTS.md` pointer confirmed. `CLAUDE.md` equality rests on the manifest's identical-hash claim, which I could not verify. See AR-08 and AR-09. |

Not inspected:

- the housing routines;
- `_run_labor_matching` internals and `plan_wage`/`plan_pricing` bodies;
- firm entry and exit, `get_economic_metrics`, `run_evidence.py`, the tests, and the S7/S8 design documents.

M02, M04, K02, K05, K07 and K08 are therefore unverified by me.

The OpenWiki refresh is recorded as pending. The tick-lifecycle page I sampled agrees with source on 9.5 and dividends.

## 4. Optional refinements

- Entry/setup row: say "execute eligible bailouts/public-works authorization (stabilizer-conditional)".
- R06: extend the `plan` warning to predicates. `should_request_healthcare_service` mutates its episode state (agents.py 1782–1791).
- §6 "Finite valid state": note that household cash can also go negative. Unsubsidized goods are debited in phase 10 without a cash check, after 9.5 repayments and care payments. The signed-balance caveat is therefore not treasury-only.
- Add `update_config`, `apply_sector_subsidy_payment`, `_collect_misc_revenue` and `_withdraw_deposits_for_planned_consumption` to the JSON symbol index.
- The §2 Government row could note that the factory starts with `unemployment_benefit_level=0.0` and `transfer_budget=0.0`. Transfers are then nil until a lever sets them.
