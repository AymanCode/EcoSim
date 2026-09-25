# Audit of `ECONOMIC_MODEL_PROPOSAL.md` and `ECONOMIC_AGENT_WORKING_CONTRACT.md`

Reviewer: Claude Fable 5.1 (`claude-fable-5-1`), 2026-09-21. This was a read-only source inspection at the stated baseline `4f69389`. I did not execute any code, tests, probes, or benchmarks. E01–E05 are treated as coordinator-supplied evidence, which I checked for consistency with source. I could not open the S01–S10 URLs with the tools available, so the use of those sources is assessed only for plausibility.

## Overall assessment

The proposal is more accurate than most documents of its kind. Every current-code claim I checked is correct at the cited lines. Its evidence labels are honest, and it does not smuggle in a preferred policy outcome.

Its weakness is what it leaves out. The first comparison Ayman wants is lower versus higher progressive tax. The mechanisms that bias that comparison most are understated or missing. There are three.

- **A default fiscal closure already exists.** Surplus is recycled to a small household lottery, and deficits on transfers are unfinanced.
- **Money leaks in several places the proposal never mentions.**
- **The firm-stabilizer switch does more than the proposal says.** Turning it off also imposes a 2% price rise per tick.

P01 and P02 are written as broad balance-sheet programmes. Source shows that a handful of narrow fixes, which reuse existing fields, would remove most of the bias.

The working contract is sound in principle. It lacks the artifacts that would actually stop four workers with little communication from colliding. It has no field-level write map, no named owner for `get_economic_metrics` and its downstream consumers, no rule for RNG keys, and no convention for config flags. Its sample benchmark is also too short to exercise the paths a first package would touch.

**Ready for planning:** P10-lite, P03 as additive metrics, and a narrowed P01 and P02.

**Needs correction before worker dispatch:** F01–F05 and F10–F12.

This review does not validate EcoSim's economics against any real economy.

## Checks performed

I read the following files and ranges.

- `AGENTS.md`, `CLAUDE.md`, and both audited documents.
- `openwiki/quickstart.md`, `openwiki/where-to-change-what.md`, `openwiki/backend/tick-lifecycle.md`, and `openwiki/backend/public-institutions.md`.
- `backend/economy.py` ranges 740–980, 1120–1300, 1750–1800, 1996–2110, 4380–4835, 5693–5772, 6028–6098, 6264–6398, 6450–6590, 6727–6779, 6965–7112, and 7285–7313.
- `backend/agents.py` ranges 1963–2020, 3364–3385, 4478–4550, 4886–4893, 5687–5739, 5965–6103, and 6260–6389.
- `backend/agents.py` 6754–7164, covering `plan_transfers`, `plan_taxes`, `apply_fiscal_results`, the investment methods, and `make_investments`.
- `backend/config.py` 19–20, 40–119, and 772–773.
- `backend/server.py` 920–954 and 1322–1336.
- `policy_forecasting/sweep/wrapper.py` 100–250.
- The `argparse` surface of `backend/tools/benchmarks/run_sim_bench.py`.

I ran these greps across `backend/` and the forecasting code:

- `target_inflation_rate`
- `govt_backed`
- `owners`
- `stabilization_disabled`
- `performance_mode`
- `warmup_ticks`

Wiki drift: `openwiki/backend/tick-lifecycle.md` says performance mode caches consumption plans "for four ticks". Source replans when `current_tick % 5 == 0` (`economy.py:1766`). The difference is minor, but it is worth a wiki refresh.

## Findings

### F01. The existing fiscal closure is understated, and it is the largest bias in a tax comparison

**Severity:** High. **Affects:** P02, §6, and the household-worker scope in the contract.

**Disputed claim.** P02 describes `make_investments` only as "the operation called government bond purchases distributes surplus money through the miscellaneous pool." It then says a tax comparison "requires a rule for the use of additional revenue." That wording implies no such rule exists.

**Evidence.** A rule does exist, and it is asymmetric.

- `GovernmentAgent.make_investments` (`agents.py:7122-7164`) spends 12% per tick of cash above a hard-coded 50,000 reserve.
- `Economy.step` routes that amount through `_collect_misc_revenue` (`economy.py:2017-2029`). That method skims a random 0–20% back to the government (`economy.py:6079-6097`).
- The remainder is paid equally to at most 50 randomly chosen households (`economy.py:6030-6077`).
- Transfers are paid with no cash check (`agents.py:6783-6791`, `6996`).
- Infrastructure and technology spending happen only when `cash_balance >= budget` (`agents.py:7043`, `7068`).
- Social spending is capped at `min(cash, budget)` (`agents.py:7110`).

**Why it matters.** Under these rules a 40% arm mostly turns extra revenue into lump sums for 50 or fewer households. A 15% arm may silently lose infrastructure and technology spending once cash falls below the budget, while transfers continue unfunded. A difference in reported output or Gini between those arms would mostly measure the recycling rule, not the taxes.

**Correction.** Restate P02's current evidence to describe this default closure. The first P02 step should be narrow: make the closure an explicit, named, configurable rule, with the current behaviour as the default. That step needs no bond market. Debt issuance, maturities, and debt holders can be deferred.

**Confidence:** High on source. The size of the effect is unmeasured.

### F02. P01 names one money source and misses several sources and sinks

**Severity:** High. **Affects:** P01, L01, L04, and E03.

**Incomplete claim.** P01's current evidence covers only entrant seed cash, which is correct at `economy.py:4739`, `4750`, `4772`, `4775`, and `4779`. By reading source I found six more non-conserving paths.

- **Firm exit.** `_handle_firm_exits` (`economy.py:4547-4570`) removes a firm and its cash, whether that cash is positive or as low as −1,000 (`config.py:772`). Nothing receives the balance. Inventory and capital vanish as well.
- **Repayments on government-backed loans.** `_collect_bank_loan_repayments` debits the borrower (`economy.py:6535`, `6560`). `BankAgent.collect_repayment` credits reserves only when the loan is not `govt_backed` (`agents.py:6016-6017`). A grep finds no other place where the government is credited. Tier-3 entrants and emergency medical loans therefore repay into nothing.
- **Double servicing of bank medical loans.**
  - `_issue_medical_loan` creates a bank loan and also sets `household.medical_loan_remaining` (`economy.py:6746-6755`).
  - The bank then collects its scheduled payment (`economy.py:6557-6574`).
  - `make_medical_loan_payment` separately collects 10% of the minimum wage and pays it to the **government** (`economy.py:1223-1226`, `agents.py:1993-2020`).
  - The bank's `loan["remaining"]` is unaffected by the government leg. The household therefore overpays, and the treasury receives revenue for a debt it never funded. This matters directly for medical-debt outcomes under P08.
- **Demand shocks.** `_apply_random_shocks` adds uniform(−50, 100) to 5–15% of households with 5% probability per tick (`economy.py:5713-5725`). Nothing funds this, and the mean is positive.
- **Entrant real assets.** New firms receive 100 units of inventory and `initial_firm_capital` at no cost (`economy.py:4791`, `4821`).
- **The `money_supply` metric.** The existing metric (`economy.py:7300-7308`) omits `misc_firm_revenue` and queued firms. Government investment and R&D enter the pool after that tick's payout (collection at `2001-2041`, payout at `1905`). Its drift is therefore noisy.

**Why it matters.** Policies change the rates of exit, entry, and emergency lending. Entry injections and exit or repayment leaks partly offset each other, and the offset depends on the policy. Fixing entry alone could move aggregate money drift in the wrong direction.

**Correction.** Add these paths to P01's evidence. Split P01 into two parts. P01a is a per-tick reconciliation identity that names every source and sink. It reports and does not yet change behaviour. P01b is a set of narrow fixes. I have not executed the medical-loan path. A small probe should confirm it before ticketing.

**Confidence:** High for exit, the government-backed loan sink, and shocks. Medium-high for the double-servicing arithmetic.

### F03. P01's scope ignores the existing `owners` base and misses a related bias

**Severity:** Medium-high. **Affects:** P01, P05, P09, and the contract's "preserve the base" requirement.

**Evidence.** Ownership already exists in source.

- `FirmAgent.owners` exists (`agents.py:2481`) and is serialized (`agents.py:2724`).
- It drives `distribute_profits` (`agents.py:5704-5737`).
- `create_large_economy` gives every initial firm 1–3 random household owners. That includes the government baseline firms (`run_large_simulation.py:250-260`).
- `_maybe_create_new_firms` never sets `owners`. Entrants therefore never pay dividends. They pay only a CEO salary equal to three times the median wage (`economy.py:4685-4687`, `1195-1202`).

**Why it matters.**

- The dividend channel shrinks as incumbents are replaced. Dividends carry a 0.40 spending propensity, so the way profits are distributed drifts with firm turnover.
- The "public" baseline firms pay dividends to private households. P05 and P09 assume a public-ownership starting point that does not exist.
- The ownership assignment comment says "No seed". In practice it depends on the global `random` state.

**Correction.** The smallest P01b fix picks owners with the existing `tier_rng`. It debits their cash or deposits through `_ensure_cash_for_payment` and `bank.withdraw`. It sets `owners` on the entrant and skips entry if the owners cannot fund it. That adds no new class and no ledger, and it runs at most once per tick. Note the baseline-firm ownership anomaly under P05.

**Confidence:** High.

### F04. P05 omits that disabling firm stabilizers imposes 2% price inflation per tick

**Severity:** High for experiment validity. **Affects:** P05 and P07.

**Incomplete claim.** P05 lists the production and wage switches. Both are verified (`agents.py:3364-3385`, `3781-3782`, `4892-4893`). It omits two others.

- **Pricing.** In `plan_pricing`, when `stabilization_disabled` is set, non-baseline firms set `price_next = price * 1.02` unconditionally (`agents.py:4545-4550`). That compounds to roughly 180% a year.
- **Government switch.** The same flag on the government object disables transfer-budget sizing (`agents.py:7016`), social spending (`7100-7102`), and the surplus recycling described in F01 (`7143`). It also disables the legacy policy chooser (`economy.py:2080`).

**Why it matters.** A "stabilizers off" arm is really a bundle. It imposes inflation, freezes wages, and changes the fiscal closure, all at once. An experiment that reads it as the absence of support is confounded.

**Correction.** Add both switches to P05. The first action is documentation plus a P10 manifest field that records the three switches. The longer-term action is to split the toggles.

**Confidence:** High.

### F05. P10 understates the pairing that exists and overlooks seeding gaps that weaken E01-style runs

**Severity:** Medium. **Affects:** P10, L06, and E01.

**Evidence.**

- Shocks, misc beneficiaries, the misc tax skim, entry, and medical-loan rates all use RNGs keyed by `CONFIG.random_seed` plus the tick or an id (`economy.py:5711`, `6046`, `6090`, `4638`; `agents.py:1977`). Exogenous shock timing and magnitude are therefore already paired across arms that share a seed.
- The misc skim key includes `int(amount*100)` (`economy.py:6090`), so its randomness depends on policy.
- `random.sample` over `self.firms` (`economy.py:5731`) diverges once the firm list diverges.
- Initial ownership uses the global `random` state (`run_large_simulation.py:253-260`).
- The wrapper's `set_run_seed` (`wrapper.py:192`) and the probe's `random.seed` call cover this only if nothing consumes global RNG differently beforehand.
- There is no snapshot or restore path. A grep of `economy.py` for `deepcopy`, `snapshot`, `from_dict`, and `pickle` found nothing. The proposal's branching claim is correct.

**Correction.** Reword P10 to "keyed streams largely exist; audit the policy-dependent keys." Take the cheapest route to a common pre-policy state first. Run one process to tick T and apply the policy at T, because `set_lever` already works at runtime. The alternative is to `copy.deepcopy(economy)` once at T. Full serialization can be deferred. Deep-copy safety is unverified. It needs a check that a copied economy produces an identical fingerprint for N ticks.

**Confidence:** High on source. Medium on the deep-copy suggestion.

### F06. P03 is correct, but redefining metrics in place would break downstream consumers

**Severity:** Medium. **Affects:** P03, contract §3, and the integration owner.

**Evidence.** The claims hold. Gini and wealth percentiles use cash only (`economy.py:6974-7003`). GDP is the sum of revenue (`economy.py:7112`). Poverty uses `gov.min_cash_threshold` (`economy.py:7295-7298`). The server price basket is at `server.py:926-939`.

There are three consumers to protect.

- The forecasting wrapper reads `gdp_this_tick`, `mean_price` as `price_index`, and `fiscal_pressure` into a frozen `FEATURE_MANIFEST` (`wrapper.py:114-172`).
- The warehouse and the dashboard also read these names.
- Statistics run before dividends are paid (`economy.py:2084` versus `2093-2100`), so cash-based measures lag by one tick.
- "GDP" as summed revenue double-counts nothing today, because there are no intermediate inputs. It does include rent and the subsidised share of purchases.

**Correction.** P03 should be strictly additive. Add the following new keys:

- `net_worth_gini`
- a fixed-line poverty count
- a fixed-basket price index
- real output

Leave the old keys unchanged and mark them deprecated in the documentation. A fixed real poverty line is one config constant. Net worth is cash plus deposits minus medical and consumption loan balances. It is one extra array pass, in the same order of cost as the current metrics.

**Confidence:** High.

### F07. P04 is accurate, but it should be narrowed and sequenced after F01, and the scalar and batch paths must both be named

**Severity:** Medium. **Affects:** P04 and the household worker.

**Evidence.**

- The budget uses gross `h.wage` and the scalar `unemployment_benefit`, not realised transfers (`economy.py:795`, `833-841`).
- The budget is capped by accessible liquidity (`economy.py:867`).
- Taxes settle at `economy.py:1204-1212`.
- The wage propensity has a floor of 0.70 (`economy.py:828`).
- At a 40% base rate, the bracket scalers at `agents.py:6383-6388` give top effective rates near 50%. The planned wage-funded budget of at least 0.70 × gross can then exceed net pay. The liquidity cap absorbs the difference.
- The tax response is therefore delayed and depends on the household's cash buffer. The proposal's wording ("not economically inert") is fair.

There are three things to watch in any change.

- The docstring says the batch path "returns identical results" to the scalar `plan_consumption`. Any change must touch both paths or retire one.
- Performance mode reuses plans for five ticks, so a tax change takes effect later in that mode.
- Brackets are percentiles of the current wage distribution, zeros included (`agents.py:6849-6851`). With high unemployment, p25 can be zero.

**Correction.** Respect the bracket instruction. Report effective rates per bracket in the manifest, and do not redesign the brackets. The minimal P04 change replaces `wage_income` with `wage_income − last tick's taxes paid`. That value is already stored as `−last_other_income` (`economy.py:1210`). It costs one extra array read. An hours-worked choice should be deferred. Its absence is a deliberate abstraction that should be disclosed, not a bug.

**Confidence:** High.

### F08. P06 is the most expensive item, and its ranking overstates its payoff for the stated comparisons

**Severity:** Medium. This is a design opinion. **Affects:** P06, L02, and L10.

**Evidence.** The claims hold.

- `other_variable_costs` is 0.0 (`economy.py:1859`).
- Infrastructure converts cash directly into a productivity multiplier with no cap (`agents.py:7047-7050`). The technology multiplier is capped at 1.15 (`agents.py:7076-7079`).
- All of that spending goes to the misc pool (`economy.py:2001-2041`).

A capital-goods sector with procurement, delays, failures, and input markets would be new firms, new markets, and new clearing in the hot path. For tax and healthcare comparisons, the bias that matters is not the missing sector. It is two things. First, public investment money reaches 50 or fewer households. Second, the productivity gain is instant and unbounded.

**Correction.** Defer the sector. The interim fix adds a cap and diminishing returns to infrastructure as config parameters, a fixed delivery lag held in a small queue, and a broader or declared recipient rule for the misc pool. Those are scalar operations with negligible cost.

**Confidence:** Medium. This is a judgement about priority.

### F09. The P07 and P08 claims are verified, with small additions

**Severity:** Low. **Affects:** P07 and P08.

**Evidence.**

- A grep finds no engine consumer of `target_inflation_rate`. It appears only in server assignment, policy snapshots, and warehouse rows (`server.py:564`, `1334`, `2742`), in the audit runner, and in the legacy ML feature generators at `generate_training_data.py:114` and `train_ml_model.py:62`.
- P07 omits that last point. An inert field is being used as a training feature and saved as policy evidence.
- The healthcare claims match source. The subsidy share passes through the cap (`economy.py:6330-6332`). A household that cannot afford the visit is dropped from the queue (`economy.py:6355-6378`). A `subsidy_share` of 1.0 still bills the patient once the cap binds.

**Correction.** For P07, the cheap interim step is to mark the field inert in the UI and warehouse, or remove it from the manifest. A central-bank rule can be deferred.

For P08, a free-at-use mode is feasible as a payer flag inside `_process_healthcare_services`. It should bypass `apply_sector_subsidy_payment` and bill the government directly. It depends on F01, because otherwise it is financed by unbounded negative cash. It also depends on the F02 medical-loan fix.

**Confidence:** High.

### F10. Contract: no field-level write map, and no owner for the metrics and consumer surface

**Severity:** High for parallel work. **Affects:** contract §3, §4, and L04.

**Gap.** L04 requires a write map, but the contract does not supply one. Source shows `cash_balance` is mutated from dozens of places in `economy.py`. Examples:

- direct government cash edits at `economy.py:1170`, `1226`, `2044`, `4742`, and `6095`
- the bank's `govt.cash_balance -= principal` at `agents.py:6047`

Household, government, and bank workers will all edit `_batch_apply_household_updates` and the block at `economy.py:1978-2059`. Assigning exact symbols does not resolve overlap inside a single function.

**Correction.** Before dispatch, the integration owner should publish four things.

- A table of mutable balance, writer symbols, and phase for `cash_balance` across the four agent types, `bank_deposit`, `total_deposits`, `cash_reserves`, `misc_firm_revenue`, and the loan fields.
- A rule that `Economy.step`, `_batch_apply_household_updates`, `get_economic_metrics`, `to_dict`, and `config.py` are edited only by the integration owner. Workers deliver pure helper functions plus a call-site request.
- A config convention: every behaviour change sits behind a named flag whose default preserves baseline fingerprints.
- An RNG convention: new randomness uses `random.Random(seed + id*prime)` with a registered prime and never the global `random`.

**Confidence:** High.

### F11. Contract: the ticket lacks consumer-impact, mode-parity, and fingerprint fields

**Severity:** Medium. **Affects:** contract §6.

The following ticket fields are missing.

- `scalar_and_batch_paths_touched`
- `performance_mode_behavior`
- `config_flag_and_default`
- `rng_keys_registered`
- `metrics_keys_added` (additive only)
- `consumers_checked` (warehouse, WebSocket frame, forecasting manifest, LLM observation)
- `baseline_fingerprint_with_flag_off`, stating whether it must be identical
- `wiki_refresh_due`

That last field, the wiki refresh, is required by `AGENTS.md` §7.

The handoff should require an E01-style SHA fingerprint showing the flag-off run is unchanged. That is the cheapest integration guard available, and the proposal already contains the code for it.

**Confidence:** High.

### F12. Contract: the benchmark recipe under-exercises the affected paths, and the 5% threshold is unanchored

**Severity:** Medium. **Affects:** contract §5 and L10.

**Evidence.**

- The CLI flags in the sample command exist (`run_sim_bench.py:226-234`).
- The harness sets `economy.warmup_ticks` itself (`run_sim_bench.py:103`).
- It has no performance-mode option. A grep found none in `backend/tools/benchmarks`.
- Entry, exit, government-backed loans, and surplus recycling occur only after warmup and mostly after firms start to fail. Eighty ticks may barely reach that regime.
- The 5% figure is correctly labelled as not Ayman's. Tick-time noise has not yet been measured.

**Correction.** Measure baseline variance first, using five or more repeats. Set the threshold at the larger of 5% and two times the observed coefficient of variation. Use at least 200 ticks for packages that touch entry, exit, or fiscal code. Add `--profile` deltas by function. Either add a performance-mode switch to the harness or state that claims apply to normal mode only. The first package recommended below is O(households) array work plus O(1) scalar work. It should be well inside any reasonable threshold. That is an estimate, not a measurement.

**Confidence:** High on source. Medium on the recommended numbers.

### F13. Minor wording issues

**Severity:** Low. **Affects:** P02 and P04.

- P02 says "GovernmentAgent has no public_debt balance." That is true. Note also that the `apply_fiscal_results` docstring claims it updates `fiscal_pressure` and `spending_efficiency` (`agents.py:6985-6988`). The body does not (`agents.py:6990-6996`). `_update_budget_pressure` does that work. This is documentation drift inside source.
- The profit-tax brackets are keyed on firm **cash** percentiles, with seeded random surcharges of up to 35 points (`agents.py:6878-6941`). A study of tax and investment should disclose this. Under Ayman's instruction it is a disclosure item, not a redesign item.

## Disposition table

| ID | Disposition | Note |
|---|---|---|
| P01 | Revise | Add the F02 and F03 paths. Split into P01a reconciliation and P01b narrow fixes that reuse `owners`. |
| P02 | Revise | Lead with the existing closure (F01). First step is an explicit, configurable closure. Defer bonds and debt holders. |
| P03 | Accept, additive only | New keys only. Protect the forecasting and warehouse consumers (F06). |
| P04 | Accept, narrowed | Lagged net wage in the batch and scalar paths. Defer hours and entrepreneurship (F07). |
| P05 | Revise | Add the pricing drift and the government-switch bundle (F04). Record the switches in the manifest now. |
| P06 | Defer | Interim cap, lag, and recipient rule only (F08). |
| P07 | Defer the mechanism | Mark the field inert now (F09). |
| P08 | Accept as the second package | Needs the F01 closure and the F02 medical-loan fix first. |
| P09 | Defer | Depends on P01–P05. Note the baseline-firm owner anomaly (F03). |
| P10 | Accept as a lite version, start first | Manifest, fingerprint, apply-at-tick branching, and an RNG-key audit (F05). |

## Recommended first package, "Comparable tax experiment v0"

The integration owner does all of this work, and no parallel workers are involved yet. Steps 1–3 are purely additive and carry no behavioural risk, which makes them the natural starting point.

1. **P10-lite.**
   - Add a run manifest with commit, full config, seed, mode, the three stabilizer switches, and effective tax rates per bracket.
   - Promote the E01 fingerprint to a helper.
   - Apply the policy at tick T in a single run, with a deep copy at T if verified.
2. **P01a.** Compute a per-tick money reconciliation with named sources and sinks: entry, exit, government-backed repayments, shocks, and the misc pool balance. It is reported only.
3. **P03 additive metrics.** Add net-worth Gini and percentiles, a fixed-line poverty count, a fixed-basket price index, and real output.
4. **P01b, flag-gated with the default off.**
   - Owner-funded entry that sets `owners`.
   - Exit residual paid to owners or creditors, or to an explicit write-off account.
   - Government-backed repayments credited to the government.
   - Medical-loan servicing limited to a single path.
5. **P02-lite, flag-gated.** Add a named fiscal-closure parameter. The default is the current behaviour. The alternatives are to hold cash, to give a per-capita rebate, or to cut discretionary spending when cash goes negative. Report cumulative negative cash explicitly as `implied_public_debt`.

**Acceptance evidence.**

- Flag-off fingerprints are identical to baseline across two seeds and 52 ticks.
- With the flags on, the reconciliation residual is approximately zero once demand shocks are disabled, under a documented tolerance.
- E03-, E04-, and E05-style probes show the new behaviour and the new keys, and the old keys are unchanged.
- The benchmark follows F12.
- `pytest backend/tests_contracts/test_contracts_invariants.py`, `test_contracts_bank.py`, `test_hot_path_optimizations.py`, and `policy_forecasting/tests` all pass.

After that, run the 15% versus 40% comparison under at least two closure rules. Report whether the ranking depends on the closure.

## Deferrals that preserve speed and agent identity

- A full double-entry ledger or event store.
- A bond market, debt maturities, and debt holders.
- A central-bank rule and deposit-creation banking.
- A capital-goods or input-output sector.
- An hours-worked choice.
- Demographics.
- Insurance risk pooling beyond a single payer flag.
- Ownership regimes under P09.
- Any redesign of tax brackets.
- A refactor that splits `agents.py`.

## Questions the repository cannot answer

1. Which fiscal closure does Ayman regard as the fair default for the tax comparison: a rebate, fixed services with debt, or debt reduction?
2. Are the baseline firms meant to be publicly owned? Source gives them private owners.
3. Is the demand-shock injection an intended external sector, or an artifact?
4. Is performance mode in scope for comparison claims, or is it a display mode only?
5. What is the actual tick-time variance on Ayman's hardware, which is needed to set the threshold?
6. What are the real magnitudes of F01 and F02 in a typical run? Measuring them requires P01a.
7. Do sources S01–S10 say what the proposal attributes to them? I could not check. The attributions are conventional and the proposal itself hedges them.

## Conclusion

| Category | Items |
|---|---|
| Confirmed mistakes or omissions | F01, F02, F03, F04, F05 (partly), F09 (the ML feature), F13 |
| Design opinions | F06, F07, F08, F12 (the numbers) |
| Contract gaps | F10, F11, F12 |

The proposal's cited facts are reliable. Its priorities and scope need the corrections above before tickets are written. The first package can then proceed incrementally, without replacing any agent's base.
