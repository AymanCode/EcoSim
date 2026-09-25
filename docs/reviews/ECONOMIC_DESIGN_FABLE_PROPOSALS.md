# EcoSim economic model: design proposal for W06–W18

Prepared by Claude Fable 5.1 (`claude-fable-5-1`) on 2026-09-21. This is a read-only design pass over the frozen archive of commit `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`.

**What I did and did not do.**
- I read `AGENTS.md`/`CLAUDE.md`, the proposal, the working contract, the readiness split, the prior Fable audit and the coordinator follow-up.
- I read the openwiki quickstart, where-to-change, tick-lifecycle, public-institutions and forecasting-pipeline pages.
- I inspected `backend/economy.py`, `backend/agents.py`, `backend/config.py`, `backend/policy_schema.py`, `backend/tools/runners/run_large_simulation.py`, and `policy_forecasting/sweep/wrapper.py` and `config.py`.
- I executed no code, tests, probes or benchmarks. E01–E10 are the coordinator's results, not mine.
- Web access worked. I fetched four sources directly and located the rest through search; the catalog marks which is which.
- W01–W05 are in progress elsewhere. Nothing below assumes they are complete.
- Line numbers are supplementary; symbols are the anchors.

**Labels used below.** **[D]** demonstrated defect, from source or a probe. **[M]** model choice. **[H]** hypothesis needing measurement. **[A]** assumed numerical value, not calibrated.

---

## 0. New source findings from this pass

These are not in the prior documents, and each affects the designs below.

| # | Finding | Evidence | Label |
|---|---|---|---|
| N1 | The **household stabilizer toggle is inert**. `HouseholdAgent.stabilization_disabled` is written by `Economy._propagate_stabilizer_flags`, but no code in `backend/*.py` reads it. `enable_household_stabilizers` is likewise only assigned. The household crisis-MPC boost is not gated by it. | Grep of `\.stabilization_disabled` in backend: readers exist only in `FirmAgent` (3781, 4545, 4892) and `GovernmentAgent` (7016, 7100, 7143). | D (same class as the inert inflation target) |
| N2 | **Scalar and batch consumption planning use different saving inputs**, although the batch docstring says "identical results". Batch `_batch_plan_consumption` uses `savings_drawdown_rate` (range 0.01–0.05) as `saving_rates` in the wage-MPC formula. Scalar `HouseholdAgent.plan_consumption` uses `compute_saving_rate()` (range 0–0.15, cash-dependent). | `economy.py` ~796/821–829; `agents.py` ~1593–1595, 1462–1502, 480. | D (parity defect; size not measured) |
| N3 | **Two RNG streams use the same key.** Entrant funding `tier_rng = Random(seed + new_firm_id*7919)` in `_maybe_create_new_firms`. The entrant's `payout_ratio` draw uses `Random(seed + firm_id*7919)` in `FirmAgent.__post_init__`. The first uniform of each stream is therefore the same number. | `economy.py` ~4638; `agents.py` ~2691. | D. This is a concrete case of "prime offsets do not guarantee independence". |
| N4 | **Shock pairing breaks once firm counts diverge.** `_apply_random_shocks` draws the demand, supply and health shocks from one sequential per-tick `Random`. The supply branch calls `_rng.sample(self.firms, …)`. Once two arms have different firm lists, the later health-shock draws are likely to stop matching. | `economy.py` ~5711–5747. | D for structure; H for size |
| N5 | **Engine randomness is stateless.** I found no global `random.*` or `np.random.*` calls in `agents.py` or `economy.py`. Every engine stream is `Random(f(seed, tick/id))`. Global `random` is used only in `create_large_economy`, for owners. | Greps for `random.Random(` and `np.random.`. | D. This makes replay-branching cheap (W10). |
| N6 | **Public-spending budgets are absolute currency per tick and do not scale with population.** Infrastructure is 500/1000/2000 per tick for low/medium/high. The gain is `(I/1000)*0.005*efficiency` per tick with no cap. At full efficiency that is +0.25%, +0.5% and +1.0% per tick for the three levels; "high" adds about +0.52 to the multiplier per year. | `agents.py` `_apply_infrastructure_spending`, `invest_in_infrastructure`. The arithmetic is from source, not a run. | D |
| N7 | **CEO salary (3× median wage) is outside the wage-tax base.** `_build_household_tax_snapshots` uses `household.wage` only. | `economy.py` ~1195–1212, 4343–4357. | D; disclosure item, not a bracket redesign |
| N8 | **All wage bracket rates are proportional to `wage_tax_rate`.** The rule is `rate = wage_tax_rate × scaler`, and the scalers come from a fixed `Random(12345)`. Announcing a new rate therefore maps exactly to the new effective rate for a household that stays in its bracket. | `agents.py` `plan_taxes`, `__post_init__` ~6381–6389. | D; used in W08 |

---

## 1. Decision table W06–W18

"Routine" means an engineering decision I have made. **USER** marks a genuine modeling preference.

| ID | Recommended minimal scope | Main alternative | Readiness after this proposal | Depends on |
|---|---|---|---|---|
| W06 | (a) Report-only per-tick money-flow audit. (b) Flagged household-owner-funded entry that reuses `owners`. (c) An exit waterfall: creditors, then owners, then a declared residual. Record entrant real endowments; do not "fix" them. | Keep unfunded entry but label it a declared `external_equity_inflow`. | (a) is A. (b) and (c) are A once USER confirms owner-funded versus labeled-external as the experiment default. My recommendation: owner-funded, with labeled-external as a sensitivity arm. | W01/W02 for the repayment lines; W05 writer map |
| W07 | Additive `eval_*` metrics computed after ledger finalization: liquid resources, a named *partial* financial position, a fixed real poverty line, a fixed-weight category price index, and constant-price output. | A relative poverty line (50% of median) as a secondary measure; included. | A | W03 manifest; none for code |
| W08 | Per-household expected wage-tax rate. Net wage enters the consumption budget in both the batch and scalar paths. Expectations rescale exactly on a lever change. Behind a flag. | A lagged-tax-only rule with no announcement effect. | A. **USER**: should expectations adjust on announcement (my recommendation) or only after the first settlement? | W07 for evaluation; N2 disclosed |
| W09 | A toggle inventory in docs and the manifest. Legacy toggles stay as they are. Add only the institution switches that have no existing lever. Never gate private decision rules behind a "support" switch. | Split the firm toggle into three rule flags. | A for the inventory, manifest and two switches. The legacy firm toggle is relabeled; retiring it is deferred. | W03, W12 |
| W10 | Replay-branch protocol (two deterministic replays diverging at T0), a fingerprint check at T0−1, purpose-keyed RNG scheme v2 behind a version flag, and a bounded deep-copy diagnostic as an optional optimization. | A deep-copy branch as the primary method. | A for protocol and diagnostic. RNG v2 is A but changes baselines, so it is an intended divergence. | W03 |
| W11 | An aggregate public-capital stock with delivery lag, depreciation, and a bounded concave productivity map. The payment recipient is declared. **Off in the first tax experiment.** | A capital-goods sector (W15). | B→A once parameter ranges are accepted as assumptions with a sensitivity plan. **USER**: recipient rule. | W12 |
| W12 | A named `fiscal_closure` enum: `legacy`, `rebate_per_capita`, `hold`. An explicit end-of-tick financing-gap *stock*. Reserve target = treasury cash at T0. | A spending-adjusts closure (services scale with revenue); needs W11. | A for the mechanism. **USER**: which closure is the headline. My recommendation: `rebate_per_capita` as headline with `hold` as a required sensitivity. | W06a audit, W09 |
| W13 | First comparison: patient-pay (current) versus a public single payer that is free at the point of use, with an administered price and unchanged capacity and queues. | A mandatory flat-premium insurer pool. | C→B. The specification below is enough for a B decision note. | W01/W02, W12, W07 |
| W14 | First comparison: a declared cost shock versus a demand shock, with and without a simple policy-rate rule that moves `BankAgent.base_interest_rate`. Treasury overdraft interest is optional. | An imposed price-path stress test. | C→B after a rate-sensitivity probe. | W04, W07, W10, W12 |
| W15 | Defer. Revisit only if W11's aggregate model cannot answer a selected question. | A single capital-goods firm type. | C | W11 |
| W16 | First comparison: the surplus-recipient dimension only (private owners, public treasury, current workers). Firm decision rules and capabilities stay identical. | Add an administered-price dimension. | C→B | W06, W12, W07, W10 |
| W17 | A domain-of-validity statement, an internal stylized-facts and sensitivity protocol, and a calibration plan conditional on a chosen reference economy. | None; claims stay synthetic. | C. **USER**: reference economy, if any. | W07, W10 |
| W18 | Five independent optional slices, each gated by a named blocked question. | — | C by design | per slice |

---

## 2. Specifications W06–W12

**Conventions for all specs.**
- Currency is "cu". Flows are cu per tick. One tick is one week (`TimeConfig.ticks_per_year = 52`).
- New config lives in `backend/config.py` and is edited only by the integration owner.
- Every new behavior flag defaults to the current behavior, unless the spec states an intended divergence.
- New metrics are additive keys. No existing key in `get_economic_metrics()` changes.
- `policy_forecasting.config.FEATURE_MANIFEST` and `snapshot_manifest` stay unchanged.

### W06 — Firm entry, ownership, exit, and residual money flows

**Policy question.** When taxes change the rates of firm failure and replacement, which outcome differences come from the policy and which come from cash that appears at entry or disappears at exit?

**Current behavior (verified).**
- `Economy._maybe_create_new_firms` runs at most one entrant per tick, after warmup. In practice it chooses Food or Services; a Housing shortfall expands the existing provider and returns.
- Tier-1 entrants, and every rejected-loan fallback, set `seed_cash = tier_rng.uniform(5_000, 30_000)` with no payer **[D, E03]**.
- The constructor never sets `owners`. `FirmAgent.distribute_profits` returns 0 when `owners` is empty, so entrants never pay dividends **[D]**.
- Entrants get `ceo_household_id`. The CEO draws 3× the median wage from firm cash in `_batch_apply_household_updates`.
- Starter inventory is 100 units for Food only. Services, Housing and Healthcare get 0. `capital_stock = CONFIG.firms.initial_firm_capital` (15) is granted free.
- Initial firms, the four baseline firms included, have 1–3 household owners assigned from global `random` in `create_large_economy` **[D, E09]**.
- `_handle_firm_exits` removes firms with `cash < bankruptcy_threshold` (−1000) or `zero_cash_streak ≥ 12`. Baseline firms are exempt.
  - Bank loans are written off.
  - Remaining cash, positive or negative, goes nowhere, and `government_loan_remaining` is not resolved. Inventory and capital are not resolved either **[D]**.
- `_apply_random_shocks` adds uniform(−50, 100) cu to 5–15% of households with 5% probability per tick, with no counterparty **[D]**.
- `money_supply` omits `misc_firm_revenue` and queued-firm cash **[D]**.

**W06a — report-only flow audit. No behavior change.**

Define end-of-tick modeled cash:

`M_t = Σ household.cash + Σ firm.cash (active and queued) + government.cash + bank.cash_reserves + misc_firm_revenue`

- Deposits are excluded on purpose. A deposit moves household cash into bank reserves, so counting both would double count.
- The new metric key is `eval_modeled_cash`. `money_supply` is untouched.

Accumulate named per-tick lines in `Economy.tick_flow_audit: Dict[str, float]`, reset at the start of the tick:

| Line | Sign | Writer symbol |
|---|---|---|
| `entry_unfunded_cash` | + | `_maybe_create_new_firms`: seed cash not matched by a loan debit |
| `exit_cash_removed` | − if positive cash, + if negative | `_handle_firm_exits` |
| `exit_govt_loan_unresolved` | memo, non-cash | same |
| `demand_shock_net` | ± | `_apply_random_shocks` (the realized sum it already computes per household) |
| `govt_backed_repayment_unreceived` | − | `_collect_bank_loan_repayments` (expected to be 0 after W01) |
| `bank_loan_writeoff` | memo, non-cash | `BankAgent.write_off_loan` call sites |
| `entry_real_endowment_value` | memo, real | inventory × price + capital × `capital_cost_per_unit` |
| `residual` | `ΔM − Σ cash lines` | computed |

**Criterion (bounded diagnostic).**
- Run the first-experiment configuration from §4 for the pilot seeds in normal mode.
- For each line, report the cumulative value over the evaluation horizon divided by mean `M`, and the paired arm difference of that ratio.
- A line becomes a required fix for the tax experiment if its paired arm difference is not within paired seed-to-seed noise. That means the 95% interval of the paired difference excludes 0. It also qualifies if its cumulative magnitude exceeds 1% of mean `M` [A: materiality threshold].
- `residual` must be within floating-point tolerance (|residual| < 1e-6 × M per tick) once all lines are named. A larger residual is an undiscovered path, and the audit is not done.

Cost: a handful of scalar adds per tick, plus one O(households + firms) sum that `get_economic_metrics` already performs.

**W06b — entry funding.**

`CONFIG.firms.entry_funding_mode ∈ {"legacy", "household_owner", "external_labeled"}`, default `"legacy"`.

- `external_labeled` keeps identical behavior. Seed cash is recorded as `external_equity_inflow` in the audit and manifest. This is an honest open-economy inflow whose size depends on policy.
- `household_owner` applies to tier 1 and to every "downgrade to bootstrapped" branch:
  1. `k = owner_rng.randint(1, 3)`, matching the initial convention. `owner_rng` uses the W10 key `(seed, "entry_owners", new_firm_id)`, not `tier_rng`.
  2. Build the candidate set from households with `liquid_i = max(cash,0) + 0.9·max(deposit,0) > 0`, the same accessibility rule as `_ensure_cash_for_payment`. Exclude `medical_training_status ∈ {student, resident}` [A]. Sample up to `4k` candidates and take the top `k` by `liquid_i`. This models entrepreneurs drawn from households with means without scanning and sorting everyone: O(k) sampling plus O(households) list construction, at most once per tick.
  3. Capacity is `c_i = φ · liquid_i`, with `φ = 0.5` [A, config `entry_owner_max_liquid_share`].
  4. `seed_cash_eff = min(seed_draw, Σ c_i)`.
  5. If `seed_cash_eff < entry_min_viable_cash` (default 5,000, the existing lower bound of the draw [A]), there is **no entry this tick**. Increment `entry_blocked_funding_count`. The tier-2 bank path is attempted first when its existing conditions hold.
  6. Each owner pays `seed_cash_eff · c_i/Σc`. Call `_ensure_cash_for_payment(owner, share)`, then `owner.cash_balance -= share` and `owner.add_ledger_flow("other", -share)`. Set `new_firm.owners = [ids]` with equal dividend shares, because the existing `distribute_profits` splits equally. Equity value is **not** added to any wealth metric (see W07).
- Tier 2 and tier 3 keep their loan paths. They also receive `owners` by the same selection with zero contribution, so the dividend channel does not shrink with turnover. A cleaner version makes owners contribute a 10% down payment [A]; do that in a second slice.
- `ceo_household_id` should be `owners[0]` when owners exist, instead of a random household [routine].
- **Timing.** Phase 13, unchanged. Writers: owner `cash_balance` and `bank_deposit` (through `bank.withdraw`), and entrant `cash_balance`. Counterparties: owners to firm. No government or bank involvement.
- **Intended divergence.** Entry rates can fall when households are illiquid. That is the mechanism, not a bug. The experiment must report entry counts and `entry_blocked_funding_count`.
- **Real endowment.** Keep the 100 Food units and the 15 capital units. Record `entry_real_endowment_value`. Expose `CONFIG.firms.entrant_starter_inventory_food` (default 100) for sensitivity. Charging owners for it needs a seller that does not exist yet (W15); inventing one would violate L02 in the other direction.

**W06c — exit waterfall.** `CONFIG.market.exit_resolution ∈ {"legacy","waterfall"}`, default `legacy`. Under `waterfall`, in `_handle_firm_exits` before removal:

1. If `cash > 0`:
   - Pay the bank up to the firm's outstanding bank loan balance, using the W01 repayment helper so that `govt_backed` loans go to government. Do not write a second crediting path.
   - Pay government up to `government_loan_remaining`.
   - Pay the remainder to `owners` equally, with ledger key `dividends` and `last_dividend_income` **not** incremented. It is a liquidation return, not recurring income, and must not feed `mpc_dividend` planning.
   - If there are no owners, the remainder goes to government as escheat, recorded.
2. If `cash < 0`:
   - The firm has already paid counterparties money it did not have; this is an implicit overdraft.
   - Record `exit_overdraft_loss = −cash`.
   - Default absorber: the bank, as `bank.cash_reserves -= min(loss, lendable_cash)`, with any remainder charged to government. **[M]** Under W14 this becomes an explicit overdraft facility.
   - Without a bank, government absorbs it.
3. Write off unpaid loan balances as today. Record the unpaid government loan as `exit_govt_loan_loss`.
4. Inventory and capital are written off as real losses, recorded in units and book value. There is no liquidation market; this exclusion is stated.

**Limits.** No equity valuation, share trading or limited-liability modeling beyond this. Owners never pay in at exit.

**Acceptance cases.**
1. An E03-style probe under `household_owner` shows ΔM = 0, owner liquid resources fall by exactly the entrant's cash, and `owners` is non-empty.
2. The same probe with all households at zero liquidity shows no entrant and the counter incremented.
3. An exit with +500 cash and 300 of bank debt gives the bank +300 and owners +200, with ΔM = 0.
4. An exit at −800 reduces bank reserves by 800, with ΔM = 0 across the step.
5. With `legacy` flags, fingerprints over 52 ticks × 2 seeds are identical to the pre-change baseline.
6. With flags on and shocks disabled, the audit `residual` is within tolerance.

**Paths and modes.** No scalar/batch split; entry and exit are scalar and run once per tick. Performance mode is unaffected. **Complexity:** about 150 lines, O(households) once per tick at most. It shares `_handle_firm_exits` and the repayment helper with W01, so **one integration owner handles both**.

### W07 — Household resources, poverty, prices, real output

**Policy question.** Do the arms differ in real resources and deprivation, under definitions that do not themselves move with the policy?

**Current behavior (verified).**
- Gini and `wealth_p*` use `cash_balance` only **[D, E04]**.
- `households_below_poverty` uses `gov.min_cash_threshold`, which the benefit lever sets **[D, E05]**.
- `mean_price` is the unweighted mean of posted firm prices across all categories.
- `gdp_this_tick = Σ last_tick_revenue`.
- `_update_statistics` runs at phase 15, **before** owner dividends at phase 16. `finalize_tick_ledger` runs after dividends.
- Household debts that exist as fields: `medical_loan_remaining`, `consumption_loan_remaining`, `medical_school_debt_remaining`.

**Proposed rules.** Add `Economy._compute_evaluation_metrics()`, called once at the end of `step()` after `finalize_tick_ledger` and before the `current_tick` increment. Store the result in `self.last_evaluation_metrics`. `get_economic_metrics()` merges these keys under the `eval_` prefix. Observation time for every measure is the end of tick *t*, including dividends.

- **Liquid resources (cu, stock).** `L_i = cash_i + bank_deposit_i`. Keys: `eval_liquid_gini` (Gini over `max(L_i, 0)`), `eval_liquid_p10/p50/p90`, `eval_liquid_top10_share`.
- **Partial financial position (cu, stock).** `F_i = L_i − medical_loan_remaining_i − consumption_loan_remaining_i − medical_school_debt_remaining_i`.
  - The key prefix is `eval_partial_fin_position_*`. It must **never** be named net worth.
  - It excludes firm ownership claims, which have no valuation convention, and any bank-ledger-only obligations.
  - Report p10, p50, p90 and `eval_share_negative_position`. Do not report a Gini: it is ill-defined with negative values, and clipping them would hide them, contrary to L08.
  - Until W02 lands, the household medical-loan field and the bank ledger can disagree [D, E07]. The manifest records which one was used; the household field is the default.
- **Disposable income (cu per tick, flow).** From the finalized ledger: `Y_i = wage + transfers + stimulus + redistribution + dividends + taxes`. Taxes are stored as negative values. Exclude `bank`, `other`, and purchases.
  - Keep a 4-tick trailing mean per household [A: window] in one float array of length households, using an O(1) running-mean update.
- **Poverty, absolute real line.** `z_t = z_0 · P_t`, where `z_0 = CONFIG.evaluation.poverty_line_per_tick`.
  - The default for `z_0` is `CONFIG.households.subsistence_min_cash` (50 cu per tick). That is an existing simulator constant, not an empirical poverty line [A].
  - Keys: `eval_income_poverty_rate` (share with the trailing mean of `Y_i` below `z_t`) and `eval_deep_liquid_poverty_rate` (share with `L_i < 4·z_t`).
  - The factor 4 mirrors the `cash_stress` horizon already used in `policy_forecasting` distress [A].
  - The line is independent of `benefit_level` by construction.
- **Poverty, relative (secondary).** `eval_relative_poverty_rate` = share with trailing `Y_i` below 0.5 × the median. This is the OECD convention [S6]. There is no equivalisation, because households have no size.
- **Price index `P_t`.** Fixed-weight Laspeyres over categories `c ∈ {food, housing, services, healthcare}`: `P_t = Σ_c w_c · p_{c,t}/p_{c,ref}`.
  - `p_{c,t}` is the transaction-weighted price, `revenue_c / units_c` from `per_firm_sales`. For housing it is rent paid divided by occupied units.
  - If no units sold in a category this tick, carry forward the last observed transaction price and set `eval_price_carry_flag_c = 1`.
  - Use household-paid prices. Where a subsidy applies, the index uses the consumer price, and a parallel `eval_producer_price_index` uses the full price.
- **Weights `w_c`.** Household expenditure shares summed over the reference window `[T0−R, T0−1]`, with R = 12 ticks [A].
  - In a branch experiment this window precedes the policy, so **both arms share identical weights and reference prices by construction**.
  - Both arrays are stored in the manifest.
  - For non-branch runs the window is the first R post-warmup ticks.
- **Real output (constant-price cu per tick).** `Q_t = Σ_c units_{c,t} · p_{c,ref}`. Key: `eval_real_output`. Also report `eval_real_consumption_per_household`, the same sum over household purchases.
- **Inflation.** `eval_inflation_52 = P_t/P_{t−52} − 1`, and a 4-tick annualized rate. The manifest states that this is *realized* inflation on this basket, not the stored target (W04).

**Limits.**
- No chain-weighting. The fixed basket is declared, and substitution bias is a known limitation [S2, S3].
- Quality change is ignored: `technology_quality_multiplier` raises quality, not units. This is disclosed.

**Compatibility.**
- All existing keys are unchanged, so the forecasting columns are unchanged.
- Warehouse and dashboard are untouched until a consumer wants the new keys. Persisting them is a separate warehouse ticket following the 8-step surface in where-to-change-what.

**Acceptance cases.**
1. E04 replay: `gini_coefficient` stays 0 (legacy), while `eval_liquid_gini` is large.
2. Moving X between one household's cash and deposit leaves every `eval_*` stock unchanged.
3. E05 replay: `households_below_poverty` flips from 0 to 200, while both `eval_*poverty*` keys do not change.
4. Scaling every transaction price by λ with units fixed gives `P` × λ, `Q` unchanged and `gdp_this_tick` × λ.
5. A paying owner's dividend at tick *t* appears in tick *t*'s `eval_` stocks.
6. Fingerprints of all legacy keys are unchanged.

**Modes.** The computation runs every tick in both modes. It is about four O(households) NumPy passes, well below the cost of `_batch_plan_consumption`; that is an estimate, to be benchmarked under the contract. Do not reduce its cadence in performance mode. If cost matters, expose `CONFIG.evaluation.every_n_ticks` explicitly and record it. **Complexity:** about 200 lines plus tests. Owner: integration owner, as the contract already says for metrics.

### W08 — Household response to taxes

**Policy question.** Holding gross wages fixed, does a tax change reach the spending *plan* through expected take-home pay, and not only through later liquidity depletion?

**Current behavior (verified).**
- `_batch_plan_consumption` budgets `wage·mpc_w + benefit·mpc_b + dividends·mpc_d`, times a trait multiplier in [0.85, 1.15], plus drawdown, capped by `cash + 0.9·deposits`. The wage is **gross**.
- `mpc_w` is floored at 0.70 for employed households outside a crisis.
- Wage tax is deducted at settlement in `_batch_apply_household_updates`.
- Taxes therefore already matter, through the liquidity cap and the cash stock **[D; not inert]**. But a household with a buffer plans the same budget at 15% and 40% until its buffer shrinks.
- The batch path is the one `step()` calls. The scalar `plan_consumption` mirrors it, with the N2 discrepancy.
- Performance mode replans only when `tick % 5 == 0` and reuses cached plans otherwise.
- Labor plans (`plan_labor_supply`) use gross wages and benefits. There is no hours margin.

**Proposed rule.**
- **State.** `HouseholdAgent.expected_wage_tax_rate: float = 0.0` (dimensionless, in [0, 0.6]). It is serialized in `to_dict`.
- **Learning, at settlement.** In `_batch_apply_household_updates`, after `taxes_paid` is known: if `household.wage > 0` then `τ̂_i ← taxes_paid / household.wage`.
  - The denominator is the taxed base only, per N7.
  - This is exact, not smoothed, because the bracket rule is deterministic given bracket membership.
  - Unemployed households keep their last `τ̂_i`.
- **Announcement.** `GovernmentAgent.set_lever("wage_tax_rate", r_new)` records `self._wage_tax_rescale = r_new / r_old` when `r_old > 0`.
  - At the next planning phase the economy applies `τ̂_i ← min(0.6, τ̂_i · rescale)` once, then clears it.
  - By N8 this equals the new effective rate for anyone who stays in the same bracket.
  - If `r_old == 0`, set `τ̂_i ← r_new`.
  - **[M, USER]** This assumes taxes are salient and known at announcement. The alternative, `tax_expectation_mode="learn_only"`, skips the rescale, so households learn at the first settlement, one tick later. Record which mode is used. In normal mode the two differ by exactly one planning tick, so this choice has low stakes for a 104-tick horizon.
- **Planning.** `wage_income_net = wage · (1 − τ̂_i)` replaces `wage_income` in `base_budget`. Apply the identical edit in **both** `_batch_plan_consumption` and `HouseholdAgent.plan_consumption`. Benefit and dividend terms are unchanged; both are untaxed in source.
- **Flag.** `CONFIG.households.plan_on_net_wage: bool = False`, which is baseline-identical. Both arms of an experiment set it identically (L07).

**Held fixed, declared.**
- MPC values and the 0.70 floor.
- The crisis boost, which N1 shows is not switchable.
- The drawdown rule.
- Reservation wages and search on gross wages.
- No hours choice.
- All firm pricing, wage and investment rules.
- Profit-tax transmission stays as it is today. It reduces firm cash and therefore investment and dividends; that is a liquidity channel, not an expectation channel.

These are disclosed abstractions, not defects. With them fixed, the experiment cannot speak to labor-supply or taxable-income elasticities [S9] and must say so.

**N2 handling.** Do not repair the scalar/batch saving-rate discrepancy inside this ticket. Record it, add a parity test that currently documents the difference, and open a separate ticket. The batch path is authoritative for `step()`.

**Performance mode.** Cached plans are not invalidated on a lever change. The announcement reaches plans at the next `tick % 5 == 0`. This is documented as mode behavior, and comparison claims are normal-mode only.

**Acceptance cases.**
1. Flag off gives identical fingerprints.
2. Flag on, with one employed household holding a large buffer: raising the rate from 0.15 to 0.40 lowers the next normal-mode plan's `base_budget` by `wage·mpc·Δτ̂·trait`. A household at the liquidity cap shows no additional plan change.
3. Batch and scalar return the same `wage_income_net` for the same household.
4. No test asserts a sign or size for aggregate consumption.
5. Performance mode: the plan changes at the next multiple of 5, asserted explicitly.

**Complexity.** One float per household, one array read, one multiply. O(households), and negligible as an estimate.

### W09 — Separate support institutions from agent decision rules

**Policy question.** When "stabilizers off" is compared with "on", what exactly changed?

**Inventory (verified).**

| Switch | What it changes | Class |
|---|---|---|
| `enable_household_stabilizers` / household `stabilization_disabled` | **Nothing (N1).** | Inert control |
| Firm `stabilization_disabled` | Production uses `_destabilized_production_plan`: a 10% hire limit, no layoffs, and a frozen expected-sales value. Pricing: a non-baseline *planned* price of ×1.02 per tick and a baseline price held. **Realized** prices then pass through `_apply_price_stabilization_to_plan`, minimum-price floors, market clearing and index construction; E10 demonstrates the plan only. Wage: `plan_wage` returns the current wage. | **Private decision rules**, not support |
| Government `stabilization_disabled` | `adjust_policies` skips transfer-budget autosizing. `invest_in_social_programs` returns 0 and resets the multiplier to 1.0. `make_investments` returns 0. | Fiscal institutions |
| `enable_government_stabilizers` (economy level) | Skips `_update_loan_commitments`, `_execute_bailouts` and public-works capacity management. Skips the legacy `_adjust_government_policy` chooser, which is also off when LLM government is on. | Support institutions plus a policy chooser |
| Always on, unswitchable | Baseline-firm bankruptcy exemption, the household crisis-MPC boost above 25% unemployment, post-warmup stimulus, the working-capital backstop (own config flags), and the doctor health lock. | Mixed |

**Proposed rules.**
1. **Manifest (with W03).** Record all three legacy toggles, **plus** `household_toggle_effective: false` as an inert-status note like W04's, plus the config flags for the always-on items.
2. **Do not reuse the firm toggle for support comparisons.** Relabel it in the docs and UI description as "alternate firm decision rule (legacy experiment)". Any experiment that uses it must declare that private rules differ between arms, as an L07 intentional capability difference.
3. **Add institution switches only where no lever exists.**
   - Bailouts, public works and social spending already have levers: `bailout_policy`, `public_works`, `social_spending`. Use the levers.
   - New: `CONFIG.government.transfer_budget_autosize: bool = True`.
   - Surplus recycling moves to the W12 closure enum.
   - New: `CONFIG.market.baseline_firm_exit_protection: bool = True`. If it is turned off, W06c's waterfall must be active first, otherwise essential-sector collapse goes unaccounted.
4. **Household crisis boost.** Expose it as what it is, a behavioral assumption. `crisis_mpc_boost` is already configurable. Add it to the sensitivity list, not to a "stabilizer" toggle.
5. **Inert household toggle.** Label it; do not invent a consumer for it. That is a routine decision, the same treatment as W04.

**Acceptance.**
1. A documented table like the one above lives in `docs/` and is checked by a test that greps the readers of `stabilization_disabled`, so that new readers force a docs update.
2. Flipping `transfer_budget_autosize` changes only `transfer_budget` evolution; the fingerprints of firm plans in the first tick after the flip are identical.
3. Manifest fields are present.

No hot-path cost. **Complexity:** small.

### W10 — Matched pre-policy state and paired disturbances

**Policy question.** Is the arm difference caused by the intervention, given a shared history and shared exogenous disturbances?

**Current behavior (verified).**
- `run_single_policy` seeds, builds, applies the policy **before the first step**, then steps. That is a start-regime comparison, not a branch **[D]**.
- Engine RNG is stateless and keyed (N5). Initial ownership uses global `random`, seeded by `set_run_seed` immediately before creation.
- Policy-sensitive or population-sensitive keys:
  - `_collect_misc_revenue` keys on `int(amount*100)`.
  - `take_medical_loan` keys on `int(loan_amount*100)`.
  - Shocks share one sequential stream across types (N4).
  - Entry keys on `new_firm_id`, which depends on history.
- There is no snapshot or restore path in the engine.

**Protocol (primary): replay-branch.**
- For each seed *s*, run **two** complete simulations from construction, arm A and arm B.
- Both use **identical** configuration and baseline levers for ticks `[0, T0)`.
- Arm B calls `government.set_lever(...)` at the boundary before `step()` for tick T0. Arm A makes no call, or a no-op call.
- Determinism plus N5 implies identical pre-T0 states. **Verify, do not assume:** compute the E01-style fingerprint at the end of tick T0−1 in both runs and abort the pair on a mismatch. Fingerprint contents: metrics, household, firm and bank `to_dict`, government `to_dict`, `misc_firm_revenue`, `misc_firm_beneficiaries`, and the queued firms.
- A single run with the policy applied at T is **not** a counterfactual. The counterfactual is the sibling replay.
- Cost: T0 extra ticks per arm. At the proposed scale this is cheaper than building and verifying snapshot machinery.

**Optional optimization: deep-copy branch. Use it only after this diagnostic passes.**
- Under one `use_config` context, run to T0, take `copy.deepcopy(economy)`, and step the original and the copy N = 26 ticks with no policy change.
- Criterion: all 26 fingerprints are equal, **and** mutating the copy's `government` does not alter the original.
- Known risk points to check:
  - `household_lookup` and `firm_lookup` must reference copied agents.
  - `_cached_consumption_plans`.
  - NumPy caches in awareness pools.
  - Any module-level cache keyed by `id()`.
- If any check fails, stay with replay. I have not run this.

**RNG scheme v2** (`CONFIG.rng_scheme_version: int = 1`; v2 is opt-in and **changes baselines**, which is an intended divergence).
- One helper: `stream(purpose: str, *ids) -> random.Random`, returning `random.Random(f"{seed}|{purpose}|{'|'.join(map(str, ids))}")`.
  - CPython seeds string inputs through SHA-512, independent of `PYTHONHASHSEED`. That is my understanding of `random.seed` version 2; implementers must confirm it in the 3.11 docs.
  - This replaces arithmetic such as `seed + id*prime`. That arithmetic collides when `id_a*p_a = id_b*p_b + const`, and it collides trivially when two purposes share a prime (N3).
- Registry of purposes and key ids:

| Purpose | Key ids |
|---|---|
| `shock_demand` | `tick` |
| `shock_supply` | `tick` |
| `shock_health` | `tick` |
| `misc_skim` | `tick, call_seq` |
| `misc_beneficiary` | `tick` |
| `entry_tier` | `firm_id` |
| `entry_owners` | `firm_id` |
| `firm_payout` | `firm_id` |
| `firm_personality` | `firm_id` |
| `medloan_rate` | `household_id, tick` |
| `hh_traits` | `household_id` |
| `hh_visits` | `household_id, anchor_tick` |
| `labor_shuffle` | `tick` |
| `wage_update` | `tick` |
| `job_cooldown` | `tick` |
| `repairs` | `tick` |
| `initial_owners` | none; also replaces the global `random` use in `create_large_economy` |

- Splitting the shock stream by type fixes N4. Demand and health shocks sample `self.households`, which is constant in size and order, so they remain exactly paired across arms. Supply shocks sample firms by **sorted firm_id** and are paired only while the firm sets coincide; this is documented as partially endogenous.
- The helper is called at most a few times per tick, and per-entity only at creation or annually. Constructing a `Random` from a string costs more than from an int. Benchmark it; if it shows up, cache per-tick streams.

**Shared and allowed to diverge (declared).**
- Shared: the initial population and ownership, all pre-T0 history, demand- and health-shock timing, targets and magnitudes, labor shuffle seeds, and household trait draws.
- May diverge: firm entry and exit and their draws, supply-shock targets, the misc-pool skim (paired by `call_seq` under v2), medical-loan rates, and everything downstream.

**Acceptance.**
1. With identical arms, replay fingerprints are equal for all ticks, over 2 seeds × 80 ticks.
2. The branch pair is equal through T0−1 and differs afterwards.
3. Under v2, a test constructs every registered purpose for ids 0..N and asserts that no two distinct `(purpose, ids)` produce equal first draws. This is a collision smoke test, not proof of independence.
4. With v2 off, the baseline is unchanged.
5. Under v2, a run where arm B removes one firm at T0 shows identical demand and health shock records in both arms.

**Modes.** Hold `performance_mode` fixed within a pair and record it. If performance-mode pairs are ever used, T0 must be a multiple of 10. That aligns with both the 5-tick plan cache and the 10-tick wellbeing cadence, so both arms re-plan on the policy tick. The first experiment is normal mode.

### W11 — A small public-investment delivery model

**Policy question.** If revenue funds public investment, how much productive capacity is delivered, when, and at what diminishing return? This is separate from the question of who receives the payments.

**Current behavior (verified).**
- `invest_in_infrastructure` spends the full lever budget only if `cash ≥ budget`.
- It adds `(I/1000)·0.005·spending_efficiency` to `infrastructure_productivity_multiplier` **instantly, with no cap and no depreciation** (N6). That multiplier scales production in `_calculate_experience_adjusted_production`.
- Technology spending is capped at 1.15.
- Payments go through `_collect_misc_revenue`: a random 0–20% skim returns to government, and the rest is split equally among at most 50 misc beneficiaries at the next redistribution.

**Proposed rule.** `CONFIG.government.public_capital_model ∈ {"legacy","stock"}`, default `legacy`.
- **State on `GovernmentAgent`.** `public_capital: float` (constant-price cu) and `public_pipeline: deque[float]` of fixed length `D`.
- **Each tick**, with spending `I_t` (existing budget and cash rule unchanged): deflate `i_t = I_t / P_t` using W07's index, then `public_pipeline.append(i_t · e_t)`.
  - `e_t = spending_efficiency` is the existing fiscal-pressure penalty.
  - It is now declared as an *administrative-efficiency assumption*, configurable, with `e ≡ 1` as a sensitivity arm [S11 supports that such gaps exist, not this functional form].
- **Delivery and depreciation.** `delivered_t = pipeline.popleft()`, then `K_{t+1} = (1 − δ)·K_t + delivered_t`.
- **Productivity map.** `multiplier_t = 1 + g_max · (1 − exp(−K_t / (κ · N_households)))`. It is bounded by `1 + g_max`, concave, and normalized per household, so results do not depend on the population scale (N6).
- **Parameters, all [A] with mandatory sensitivity ranges.**

| Parameter | Default | Sensitivity range |
|---|---|---|
| `D` (ticks) | 26 | 13–52 |
| `δ` (per tick) | 0.001, about 5% per year | 0.0005–0.002 |
| `g_max` | 0.15, mirroring the existing technology cap | 0.05–0.30 |
| `κ` | chosen so that the "medium" lever reaches half of `g_max` in about 3 years at e = 1 | — |

  None of these is empirically calibrated. A policy ranking that flips within these ranges is reported as unstable.
- **Recipient [M, USER].**
  - Default: keep the misc-pool routing unchanged but *declare* it in the manifest.
  - Alternative: pay pro rata to Services firms as revenue. That is construction-like, but it adds demand without consuming their capacity, which sits uneasily with L02.
  - Alternative: pay as wages to public-works employees when that lever is on.
  - I recommend the default for v0. The first tax experiment sets infrastructure, technology and social spending to `none` in both arms, which takes W11 off its critical path.
- **Maintenance.** Depreciation is the only maintenance concept. Explicit maintenance spending is excluded.

**Acceptance.**
1. `legacy` gives an identical fingerprint.
2. Under `stock`, spending at tick t changes production no earlier than t + D.
3. The multiplier is at most `1 + g_max` for any spending path.
4. With zero spending, K decays geometrically.
5. Doubling households and spending leaves the multiplier path unchanged.

Cost is O(1) per tick. **Complexity:** small. It depends on W07 (deflator) and W12 (what funds it).

### W12 — Fiscal closure for the first tax experiment

**Policy question.** When wage-tax revenue changes, *what else changes*? Without a declared answer, "15% versus 40%" is undefined.

**Current behavior (verified). This is the de facto closure, and it is asymmetric.**
- **Transfers.** Unemployment benefits are paid in full with no cash check. Gap-filling is limited by `transfer_budget`. `apply_fiscal_results` can drive `cash_balance` negative **[D, E02]**.
- **Subsidies.** `apply_sector_subsidy_payment` pays nothing when `cash ≤ 0`.
- **Infrastructure and technology** spend all-or-nothing, only if `cash ≥ budget`. **Social spending** is `min(cash, budget)`.
- **Surplus.** `make_investments` pays `0.12 × (cash − 50,000)` **only when `cash − 50,000 > 10,000`, that is when cash is strictly above 60,000** **[D, E08]**.
  - The payment goes to the misc pool: a 0–20% random skim returns to government, and the rest goes to at most 50 beneficiaries.
  - It is disabled when the government toggle is off.
- **Debt.** There is no debt stock. `annualized_debt_to_gdp` reads an attribute that does not exist.
- **Efficiency penalty.** `fiscal_pressure` is an EMA of (spending − revenue)/GDP and drives `spending_efficiency`. That penalty matters only when infrastructure or technology spending is on.

**Proposed rule.** `CONFIG.government.fiscal_closure ∈ {"legacy","rebate_per_capita","hold"}`, default `legacy`. It is consumed at Phase 11.5 in `Economy.step`, where `make_investments()` is called today; the integration owner owns that call site.

- `legacy`: exactly today's behavior.
- `hold`: no surplus recycling. Treasury cash absorbs all differences. *Interpretation:* extra revenue retires or avoids the overdraft; lost revenue draws on it.
- `rebate_per_capita`:
  - With reserve target `B*`, compute `R_t = ρ · max(0, cash_t − B*)`.
  - Pay `R_t / N` to **every** household directly: `cash_balance += r`, `add_ledger_flow("transfers", r)`, and a separate `last_rebate_income` field. W07's `Y_i` then includes it, and `plan_transfers` gap logic is unaffected.
  - No misc pool and no skim.
  - `ρ = 0.12` per tick retains the existing speed [A].
  - **`B*` = treasury cash at the end of tick T0−1**, recorded in the manifest. It is identical across arms under W10 and replaces the hard-coded 50,000 and the 10,000 dead-band, so it is scale-free.
  - *Interpretation:* marginal revenue above the pre-policy position returns as an equal lump sum. This is the standard device for separating a tax's distributional and behavioral effects from a spending programme.
- **Deficits under all closures.** Transfers remain unconditional.
- **Financing-gap stock.** `financing_gap_t = max(0, −government.cash_balance_t)`, observed once at the end of the tick. Key: `eval_gov_financing_gap`. Also report `eval_gov_net_cash = cash_balance` and the per-tick primary balance.
  - **Never sum the gap over ticks.** It is already a stock; summing repeats the same shortfall.
- **Counterparty convention [M].** Negative treasury cash is an interest-free overdraft at an implicit monetary authority. It is money creation, and W06a's audit logs it on the line `gov_overdraft_change`. This is an explicit L01 entry, not a hidden one. Interest-bearing debt with holders is W14 and is not needed here.
- In W12 the `annualized_debt_to_gdp` helper is left as it is, and its result is documented as not meaningful.
- **Asymmetry disclosure.** Subsidies stop at `cash ≤ 0` while transfers do not. The first experiment runs with `sector_subsidy_level = 0` and discretionary spending at `none`, so neither asymmetry bites.

**Closures to compare [USER decides the headline; mechanism ready either way].**
- I recommend `rebate_per_capita` as the headline and `hold` as a mandatory sensitivity. Report whether the sign and ordering of each outcome survive the switch.
- A third option, "services adjust", is deferred until W11 exists.
- `legacy` is run once as a reference, so we can measure how much the old lottery closure mattered. Audit finding F01 conjectured that this was large, and its size is unmeasured.

**Acceptance.**
1. `legacy` gives an identical fingerprint.
2. E08 replay under `hold` gives payments of 0, 0 and 0.
3. `rebate` with cash = B* + 1000 pays 120 in total, each household receives 120/N, and ΔM = 0.
4. E02 replay gives `eval_gov_financing_gap = 1000` at that tick and still 1000 one tick later if nothing changes; it is not 2000.
5. `misc_firm_revenue` receives nothing from the closure under `rebate` or `hold`.

**Modes.** Scalar, O(households) for the rebate loop. Vectorize it if it shows up in benchmarks. **Complexity:** small.

---

## 3. W13–W17: first comparisons, and W18

### W13 — Healthcare financing

**First comparison.** Hold capacity, training, queue priority and healing constant, and compare two payer rules.
- **(A) Patient-pay.** Today's `_process_healthcare_services` with `subsidy_share = 0`: deposits first, then a medical loan, then a drop from the queue on unaffordability.
- **(B) Public single payer, free at the point of use.**
  - `household_cost = 0` for every completed visit.
  - Government pays `visit_price` to the provider per *completed* visit, from treasury cash. This bypasses `apply_sector_subsidy_payment`, whose cap and `cash ≤ 0` cutoff would silently re-bill patients.
  - No medical loans are originated.
  - Rationing is the existing capacity queue only.
  - Financing: a declared wage-tax increment Δr under the W12 closure. Δr is set so that the pre-policy expected cost is covered; this is a simple static calculation recorded in the manifest, not a guarantee of balance.

**Coherence assumptions.**
- **The provider price is administered** in (B): frozen at the T0 level and indexed to W07's `P_t`.
  - **[H]** The firm pricing rule, facing a payer with no price sensitivity, could ratchet upward. Test this with a 52-tick probe before choosing between administered and negotiated prices.
- Demand generation (`should_request_healthcare_service`) is unchanged. Moral hazard or cost-sharing demand responses [S8] are *excluded* in v0 and listed as a sensitivity, not assumed away.

**Interface.** `healthcare_payer_rule(visit_price, household, government) -> (patient_cost, payer_cost, payer_id)`, a pure function selected by `CONFIG.government.healthcare_payer ∈ {"patient_capped_subsidy","public_single_payer"}`.

**Exclusions.**
- Private insurers, premiums and risk pooling. The alternative second slice is a mandatory flat-premium pool per WHO's pooling function [S4].
- Provider ownership changes.
- The acute versus chronic distinction.

**Dependencies.** W01/W02 (without them, the medical-debt outcomes in arm A are wrong), W12, W07 and W10. Matched health shocks need RNG v2.

**Evidence before broader claims.**
- Provider solvency, under-utilisation and queue length under (B).
- Treasury path.
- Sensitivity to the demand response and to price administration.
- No claim about real systems without W17.

### W14 — Inflation, monetary policy and public financing

**First comparison.** A 2×2 design.
- *Shock type:* a declared cost shock (a multiplicative productivity loss to Food for K ticks, through an explicit shock schedule recorded in the manifest) versus a demand shock (a one-off per-capita transfer funded by overdraft).
- *Policy regime:* a fixed rate versus a simple rule `i_t = i* + φ_π·(π_t − π*)`, applied every 4 ticks to `BankAgent.base_interest_rate`.
  - `π_t` is W07's `eval_inflation_52`.
  - `π*` is the stored target, which finally gets a consumer.
  - The form follows [S10]. `φ_π` is [A] and is swept.

This makes the target active **only** in the rule arm. W04's "inactive" label stays true everywhere else.

**Prerequisite probe [H].**
- Before building, perturb `base_interest_rate` by ±300 bp in a replay-branch and measure the change in loan origination, firm investment and consumption-loan uptake.
- If those responses are within seed noise, the rule has no transmission. The work then shifts to the credit-demand side (W08-style expectations for firms) before any inflation claim.
- A quick grep suggests `base_interest_rate` reaches mortgages and risk-adjusted firm rates. Implementers must map every reader.

**Balance-sheet conventions.**
- The bank stays a reserve-constrained lender. This is a declared simplification relative to [S1].
- The treasury overdraft from W12 optionally accrues `i_t/52` per tick, paid to the monetary authority. It is a sink, logged.

**Exclusions.**
- A bond market, deposit-creation banking and the exchange rate.
- The "stabilizers off, +2% planned price" rule is **not** an inflation mechanism and must not be used as one.
- An imposed price-path stress test remains a separately labeled alternative.

### W15 — Capital goods and production networks

- Defer this item.
- **Trigger:** a selected question that depends on input scarcity or procurement competition, and W11 sensitivity showing that the aggregate abstraction drives the ranking.
- **First slice if triggered:** one capital-goods category whose buyers are `plan_capital_investment`, `invest_in_unit_expansion` and W11's pipeline.
  - It replaces `_recycle_capital_investment` and the misc-pool routing for those flows.
  - It has capacity-limited delivery.
  - It needs a cost estimate first: one more category in goods clearing.
- A full input-output structure [proposal S10] is excluded.

### W16 — Ownership and governance institutions

**First comparison.** One dimension only, the **surplus recipient**, with identical firms, decision rules and initial state.
- (i) Private: current `owners`.
- (ii) Public: `distribute_profits` pays the treasury, and those funds are recycled under the *same* W12 closure.
- (iii) Worker: paid equally to current `employees`.

**Implementation.**
- A `surplus_recipient_rule(firm) -> List[(payee, share)]` consumed by `distribute_profits`, selected per firm by `firm.ownership_form`.
- At T0 the branch applies a declared ownership *transfer*. The manifest records whether it is compensated or uncompensated. If compensated, it is funded by overdraft and logged.

**Rules of the comparison.**
- No productivity, competence or corruption modifiers attach to any label.
- Record that baseline firms are privately owned today (E09).
- A preset "public baseline providers" is just (ii) restricted to `is_baseline`.
- Presets named capitalism, socialism and so on are deferred until at least the allocation and investment dimensions exist. Until then, arms are named by mechanism, for example "private-dividend" or "public-dividend+rebate".

**Exclusions.**
- Control rights, objectives other than the current firm rules, planning, administered prices and governance delay.
- Each of these is a later single-dimension slice [S5 for the dimensional framing].

**Evidence needed.** W06 owner-funded entry, otherwise entrants have no surplus recipient at all; and sensitivity to `payout_ratio` and `mpc_dividend`.

### W17 — Calibration and validation

**Domain of validity now.** A closed, single-region, weekly, synthetic economy with no demographics. Claims are conditional within-model comparisons.

**First affordable step: internal validation.**
- (a) Stylized-fact checks on W07 measures, as screens only: positive unemployment–vacancy co-movement, right-skewed liquid wealth, and pro-cyclical entry.
- (b) One-at-a-time sensitivity on the [A] parameters flagged in this document, reporting rank stability.
- (c) Structural sensitivity: W12 closure, W08 mode and W06 entry mode.

[S7] and [S12] support separating these three validation activities.

**External calibration.** Proceed only after **USER** names a reference economy and horizon. Then:
- map a tick to one week;
- choose moments: wage distribution, unemployment rate, consumption share by category, and effective tax rates by quantile;
- hold out at least one moment family and one policy episode.

No numeric target is proposed here, because none has been sourced.

### W18 — Optional slices

Each slice is opened only by a named blocked question.

| Slice | Opens when | Preserve | First bounded step |
|---|---|---|---|
| X01 Demographics | Pension or aging question | The `age` field and `can_work` | Deterministic aging and a retirement flag; no births or deaths |
| X02 External sector | Imported-inflation or tariff question | Closed accounting | One external account as counterparty. This also gives W06's `external_labeled` mode a home. |
| X03 Housing and land | Rent-control or supply question | The rental, mortgage and repair mechanics | A completion lag on `invest_in_unit_expansion` |
| X04 Labor institutions | Hours or bargaining question | Matching | An hours margin on the W08 net-wage signal |
| X05 Environment | Carbon-price question | — | Requires W15 inputs first |

---

## 4. Dependency-ordered first tax experiment

**Order.**
1. W03 manifest and W05 map (coordinator).
2. W10 replay-branch protocol and fingerprint helper.
3. W07 metrics.
4. W06a audit.
5. W12 closures.
6. W09 manifest fields.
7. W08 flag.
8. Pilot.
9. W06b/c only if the audit criterion triggers, then a rerun.
10. Main runs.

W01/W02 should land before step 8, because emergency and medical loans occur in these runs. If they have not landed, report the audit's `govt_backed_repayment_unreceived` line as a known contaminant.

| Element | Specification | Status |
|---|---|---|
| Schedules | Arm L: `wage_tax_rate = 0.15`. Arm H: `wage_tax_rate = 0.40`. | 0.15 is the baseline in `policy_forecasting.config.BASELINE_LEVERS`. Both lie inside the schema bounds 0–0.50. 0.40 is the user's motivating value. |
| What stays fixed | Bracket scalers unchanged (`Random(12345)`). Effective rates are `r × scaler`, with the top bracket at `r × (p90_scaler + 0.03)`, so the top rate is at most 0.40 × 1.28 ≈ 0.51. Profit, investment and property taxes are held. | The manifest reports realized effective rates by wage quantile per tick, the N7 CEO-salary exclusion, and the fact that brackets are percentiles of current wages including zeros. |
| Other levers | `benefit_level` at the baseline value. Infrastructure, technology and social spending at `none`. Subsidy 0. Public works and bailouts at baseline values, identical in both arms. All three legacy stabilizer toggles on. LLM government off. | — |
| Closure | Headline `rebate_per_capita` with `B*` = cash at T0−1. Sensitivity: `hold`. Reference: `legacy` for arm pairs on the pilot seeds only. | USER confirms the headline. |
| Behavior | Headline `plan_on_net_wage = True` with announcement mode. Sensitivity: `False` (current behavior). | [M] |
| Entry | Headline per the W06a criterion. Sensitivity: the other entry mode. | — |
| Timing | Warmup 10 ticks (the config default). T0 = 62, which is 52 post-warmup ticks of shared history [A]. Horizon: 104 ticks after T0 [A]. Windows: transition t ∈ [T0, T0+25]; medium [T0+26, T0+77]; late [T0+78, T0+103]. | Rationale: the fiscal-pressure EMA has a roughly 20-tick memory by construction; firm exit needs a streak of 12 or more ticks; seed loans run 156 ticks. 104 ticks captures exit and entry turnover but **not** full loan cycles, and this is a stated limitation. Before the main runs, check on the pilot that arm-L outcomes are not still trending at T0. If they are, lengthen the pre-period. |
| Scale and mode | 1,000 households, 10 firms per category, normal mode [A]. | This matches an existing benchmark scale and keeps 2 arms × closures × seeds affordable. No timing claim is made. |
| Pairing | W10 replay-branch per seed, with the fingerprint gate at T0−1. RNG scheme v2 if it has landed; otherwise v1, with N4 and the amount-keyed skim disclosed as residual unpaired noise. | — |
| Replications | Pilot: 8 seeds. Compute the paired-difference standard deviation for each primary outcome. Choose N so that the 95% half-width of the mean paired difference is at most a pre-declared fraction of the arm-L level. 10% is a placeholder [A]; USER or integration owner sets it **before** looking at signs. Floor 24 seeds, matching the existing `CONFIRM_SEEDS` convention; cap 64. | No N is asserted to be sufficient in advance. |
| Primary outcomes (W07, window means) | `eval_real_output` per household; `eval_real_consumption_per_household`; employment rate; `eval_income_poverty_rate`; `eval_liquid_gini` and p10/p50/p90; mean disposable income by pre-T0 wage quartile, with membership fixed at T0−1 to avoid a changing sample population; treasury net cash and `eval_gov_financing_gap` at the end of each window; firm count and entry/exit counts; `P_t`. | — |
| Diagnostics | W06a audit lines per arm. Rebate paid per household. Share of households at the liquidity cap, which identifies the W08 channel against the liquidity channel. | — |
| Analysis | Per-seed paired differences H−L. Mean, bootstrap CI and sign consistency across seeds, per window. A closure × behavior × entry sensitivity grid reported as a table of signs. Any outcome whose sign flips across the grid is labeled "closure- or assumption-dependent". No composite welfare score. | The existing `matched_treatment_effects` machinery can be reused offline without touching frozen columns. |
| Interpretation guard | Results describe this synthetic economy with no hours margin, no avoidance and no taxable-income response [S9]. Neither arm is a preferred outcome. | — |

---

## 5. Source catalog

Repository citations above support facts about this code only. The economics sources support principles, never the [A] coefficients.

| ID | Source | Supports | Limitation | Access this session |
|---|---|---|---|---|
| S1 | [McLeay, Radia & Thomas, *Money creation in the modern economy*, Bank of England Quarterly Bulletin 2014 Q1](https://www.bankofengland.co.uk/quarterly-bulletin/2014/q1/money-creation-in-the-modern-economy) | Loans create deposits, so EcoSim's reserve-constrained bank is a declared simplification (W14). Money creation has matching claims (W06, W12). | Concerns the UK institutional setting and gives no modeling recipe. | Fetched |
| S2 | [BEA, chained-dollar FAQ](https://www.bea.gov/help/faq/79) | Separating price change from quantity change. W07 uses a simpler fixed-weight form. | Official practice is chain-weighted; ours is not. | Cited from the proposal; not re-fetched |
| S3 | [BLS, CPI Questions and Answers](https://www.bls.gov/cpi/questions-and-answers.htm) | The basket is built from expenditure data; the index reflects the average household's experience, not any individual's (W07). | US urban consumers. | Fetched |
| S4 | [WHO, Health financing](https://www.who.int/health-topics/health-financing) | The functions of revenue raising, pooling and purchasing; cost as an access barrier (W13). | Normative toward universal health coverage. It is used for structure, not as the outcome to reproduce. | Fetched |
| S5 | [Jahan & Mahmud, *What Is Capitalism?*, IMF Finance & Development](https://www.imf.org/en/publications/fandd/issues/series/back-to-basics/capitalism) | Treating ownership, profit and markets as separable dimensions (W16). | An introductory explainer. | Cited from the proposal; not re-fetched |
| S6 | [OECD, Poverty rate indicator](https://www.oecd.org/en/data/indicators/poverty-rate.html); [US Census, poverty measures](https://www.census.gov/topics/income-poverty/poverty/guidance/poverty-measures.html) | A relative line at 50% of median income. Absolute thresholds are updated by CPI and do not depend on programme parameters (W07). | Both are equivalised or vary by family size, and EcoSim households have no size. The Census page I fetched did not cover the Supplemental Poverty Measure. | OECD found by search; Census fetched |
| S7 | [Caiani et al., *Agent based-stock flow consistent macroeconomics: Towards a benchmark model*, JEDC 69 (2016)](https://www.sciencedirect.com/science/article/abs/pii/S0165188915301020) ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2664125)) | The discipline that every flow has a counterparty and every stock a holder in an ABM (W06a, W12). | A full SFC matrix is more than is proposed here. | Located by search; abstract only |
| S8 | [Brook et al., *The Health Insurance Experiment*, RAND RB-9174 (2006)](https://www.rand.org/pubs/research_briefs/RB9174.html) | Cost sharing reduces use of both effective and less effective care. Motivates the excluded demand-response sensitivity in W13. | US data from 1974–82. No elasticity is imported into the model. | Located by search; snippet only |
| S9 | [Saez, Slemrod & Giertz, *The Elasticity of Taxable Income…*, JEL 50(1) 2012](https://www.aeaweb.org/articles?id=10.1257/jel.50.1.3) | Behavioral margins of taxation beyond liquidity exist and are contested. Justifies the W08 and §4 disclaimers. | No elasticity is adopted. | Located by search |
| S10 | [Taylor, *Discretion versus policy rules in practice*, Carnegie-Rochester 39 (1993)](https://web.stanford.edu/~johntayl/Onlinepaperscombinedbyyear/1993/Discretion_versus_Policy_Rules_in_Practice.pdf) | The form of a simple interest-rate rule (W14). | The coefficients describe the US in 1987–92; ours are [A] and swept. | Located by search |
| S11 | [IMF, *Making Public Investment More Efficient* (2015)](https://www.imf.org/external/np/pp/eng/2015/061115.pdf); [IMF Fiscal Rules Dataset](https://www.imf.org/en/topics/fiscal-policies/fiscal-rules-dataset) | Spending and delivered capital differ; the search snippet quotes an average inefficiency of "around 30 percent". Fiscal rules come in distinct types: balance, debt, expenditure and revenue (W11, W12). | Cross-country averages. This does **not** validate `spending_efficiency`'s functional form or our `e_t`. | Located by search; snippet only |
| S12 | [Fagiolo et al., *Validation of Agent-Based Models in Economics and Finance* (2019)](https://link.springer.com/chapter/10.1007/978-3-319-70766-2_31); Tieleman (2022), in the proposal as S06 | Separates input calibration, output validation and parameter-space exploration (W17). | A methodological survey. | Located by search |
| — | Kaplan, Violante & Weidner (proposal S09); Tenreyro (S07); IMF fiscal policy (S08) | As stated in the proposal. | **Not re-verified by me.** | Unverified this session |

Two technical claims also need implementer verification, because I did not fetch the Python documentation: `random.Random(str)` seeding by SHA-512, and the variable draw consumption of `random.sample`.

---

## 6. Shared interfaces and unresolved decisions

**Interfaces.** Publish these as contract v2 before delegating. Every symbol below touches `Economy.step`, `_batch_apply_household_updates`, `get_economic_metrics`, `to_dict` or `config.py`, and all of those are edited by the **integration owner**. Workers deliver pure helpers plus call-site requests.

| Interface | Signature / fields | Writer | Phase | Consumers |
|---|---|---|---|---|
| `Economy.tick_flow_audit` | `Dict[str, float]`, cu per tick, reset at tick start | Named call sites (W06a table) | various; finalized at the end of the step | Manifest, `eval_` metrics |
| `Economy.last_evaluation_metrics` | `Dict[str, float]`, `eval_*` keys with the units in W07 | `_compute_evaluation_metrics` | after `finalize_tick_ledger` | `get_economic_metrics` (merge), experiment runner. **Not** `FEATURE_MANIFEST`. |
| `rng.stream(purpose, *ids)` | returns `random.Random`; purpose registry in one module | integration owner | any | all stochastic code under scheme v2 |
| `HouseholdAgent.expected_wage_tax_rate` | float in [0, 0.6] | settlement (learn); planning pre-step (rescale) | 10 / 2 | batch and scalar consumption planning |
| `fiscal_closure(government, households, B_star) -> Dict` | returns `{"rebate_total", "per_household"}`; pure planning, with settlement done by the caller | government worker | 11.5 | household cash, ledger, audit |
| `GovernmentAgent.public_capital`, `public_pipeline` | constant-price cu; `deque(maxlen=D)` | `invest_in_infrastructure` | 11.5 | production multiplier |
| `healthcare_payer_rule(price, hh, gov)` | returns `(patient_cost, payer_cost, payer_id)` | healthcare worker | 6 | `_process_healthcare_services` |
| `surplus_recipient_rule(firm)` | returns `List[(payee_kind, payee_id, share)]` | firm worker | 16 | `distribute_profits` |
| Entry and exit helpers | `select_entry_owners(...)`, `resolve_exit(firm) -> flows` | firm worker (pure); integration owner settles | 12–13 | W01 repayment helper (shared) |
| Branch manifest additions | `T0`, `B_star`, `price_ref`, `basket_weights`, fingerprint at T0−1, `rng_scheme_version`, closure, entry mode, tax-expectation mode, effective rates by quantile, toggle inventory | experiment runner | — | W03 manifest (additive) |

**Coupling that forbids parallel edits.**
- W06c and W01 share the repayment and exit code.
- W08 and W12 both touch `_batch_apply_household_updates` and Phase 11.5.
- W07 and W06a both add end-of-step hooks.

Sequence these through one owner. W09 documentation, W10 RNG registry design, the W11 helper and the W13/W16 pure rules can be drafted in parallel as helpers.

**Unresolved decisions, genuinely USER.**
1. Headline fiscal closure: `rebate_per_capita` (recommended) or `hold`.
2. Entry funding default: `household_owner` (recommended) or `external_labeled`.
3. Tax salience: announcement rescale (recommended) or learn-only.
4. Who absorbs exit overdrafts: bank then government (recommended) or government only.
5. Recipient of public-investment payments (W11).
6. The precision target for replications, to be set before the pilot results are inspected.
7. Whether baseline firms should be *made* publicly owned as a preset (W16-ii on `is_baseline`), given that they are privately owned today.
8. The reference economy for W17, if any.

**Unresolved, technical (no user input needed).**
- Deep-copy safety (the W10 diagnostic).
- Interest-rate transmission strength (the W14 probe).
- Provider price behavior under a price-insensitive payer (the W13 probe).
- The cost of string-seeded RNG construction.
- The separate ticket for the N2 scalar/batch saving-rate parity.
- The size of each W06a line.

**Criticisms from the original proposal that still hold.** These are justified by source.
- Unfunded entry (P01).
- No debt stock behind deficits (P02).
- Cash-only inequality and policy-linked poverty (P03).
- Gross-wage planning (P04).
- The stabilizer toggle changes private rules (P05); N1 adds that one of those toggles does nothing at all.
- Instant, unbounded infrastructure gains (P06; N6 quantifies the arithmetic).
- The inert inflation target (P07).
- A capped subsidy is not free-at-use coverage (P08).

**Where I depart from the proposal.**
- P02 scope: the W12 overdraft convention suffices for the first experiment; bonds are deferred.
- P06 scope: W11's aggregate stock comes first, and a sector is built only on a demonstrated need.

**Wiki drift to report; do not hand-edit.**
- `tick-lifecycle.md` should mention the inert household toggle (N1).
- "Cached for four ticks" is compatible with source, which replans every fifth tick and reuses the plan for the four ticks between. It could state the `tick % 5` rule explicitly.
- `agents-and-markets` or the forecasting page should note the N2 parity gap once it is confirmed by a test.
- A wiki refresh will be due after any of W06–W12 lands.
