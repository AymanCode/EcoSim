# Size Services expansion around recent rerouted work

## Problem and decision

Services capacity is installed worker space. Stockout rerouting yields real paid orders at the seller that fills them. A surge from another seller's shortage can be transient. It can also be early evidence of a growing line of business. The previous observation screen at `984316b` evaluated a veto. Three actual projects would have been blocked, and the receiving firms continued serving rerouted work in the observed run. Actual delivered demand after an installation depends on that installation. The screen did not compare the two decisions under identical future conditions.

Use order source to size a permanent investment. A firm with enough demand for its existing expansion criteria can still commit some space when a large project relies on a new rerouting surge. Use the firm's existing size for an ordinary Services space upgrade as the smaller project size. Apply the same economics and credit checks to the actual-sized project. This makes the response gradual without a veto based solely on reroute history. This branch has no new runtime switches.

## Exact rule

Every completed income-first week, store one coherent snapshot for each private generic Services firm while firm-specific fallback is active. Store the tick, sold units `S`, receiver rerouted units `R`, funded own missed-order units `L` from the existing firm-specific map, and realized output capacity `C`. Keep the latest five consecutive observed rerouted quantities, including measured zeros. Use the settled week marker to prevent repeat observations. Clear the rolling sample when stockout fallback is inactive or a completed week is missing. Entrants and older snapshots with no saved history accumulate actual observations. The standalone reporting counter still publishes availability for Services sales in any measured income-first week.

At the private Services long-term capital decision, require the observation's settlement tick to equal `current_tick - 1`. Apply the sizing check when firm-specific fallback is still active, the five-week sample is complete, the previous settlement recorded positive rerouting, and `C > 0`. If fallback turns off before the decision, use the ordinary quote. This reuses the same five weeks as the existing operational eligibility rules. In the formulas below `R_typical` is capped by actual current rerouted work.

```text
D = max(0, S - R)
R_typical = min(R, median(R from the five observed settlements))
supported_volume = D + L + R_typical
depends_on_reroute_surge = R > R_typical + EPS and supported_volume < 0.95 * C

ordinary_cost = existing long-term Services project amount
step_cost = _service_slot_upgrade_gain(firm) * services_capacity_cost_per_unit
project_cost = min(ordinary_cost, step_cost) if depends_on_reroute_surge else ordinary_cost
```

`L` includes funded own orders turned away by the firm even if customers ended up served elsewhere. This accounts for a rerouted order using a slot before a regular customer arrives. The 95% reference, five weeks, personality-based slot increment, and cost per slot all come from existing model rules. The median determines when a surge supports a large capital commitment. It does not discount receipts, remove appointments, or set a labor target. Cash affordability, expected wage margin, reserves, arrears, loan terms, credit and existing cooldown remain part of the decision. Existing staffing after installation uses the new actual slot count.

Retain the ordinary project floor during the ordinary quote. The sized-down private Services project can fall below that floor, since it is a distinct physical scale using the same per-slot cost. The bank's `originate_v2` accepts positive principal and applies normal coverage and credit checks on the same terms. Apply the one final project amount consistently to the cash/loan quote, installed physical slots, capital stock, investment bookkeeping, and the capital transfer to households. Compute the installed slots from final cost divided by per-slot cost, including the existing fractional-capacity treatment of ordinary projects. Debt mirrors use borrowed principal only. A smaller obligation can qualify when a larger one would be denied. Start the ordinary cooldown on any successful installation, including cash-only. A denial posts no debit, claim, installation, capital transfer, or cooldown update. The infrastructure route can still fund its existing project if independently eligible. Later genuine growth can use either route as the ordinary eligibility and cooldown permit.

## Integration

- `backend/payment_sectors.py` supplies the settled receiver units already introduced on the delivery branch. Do not infer volumes from equivalent amounts at the sold-out seller's price.
- `backend/economy.py` uses the settled Services loop after `PaymentGoodsMarket.finish` to record the sample exactly once. Read it before standard labor planning in `_maybe_offer_long_term_capital_loan`. Scope the size adjustment to the existing income-first Services project path after the standard eligibility and original cost calculation, before funding. Pass the same final quote to the cash/loan split, installed slots, capital route and household distribution. Store the previous quote, changed quote and date in existing audit diagnostics. Retain the ordinary financing routes and the existing same-week prevention of double installations.
- `backend/agents.py` stores only the settled firm data needed by this decision, using defaults/getattr for missing slots on old objects. Do not store household histories. Do not use the result before settlement or read future orders.

The expected cost is one map increment per successful Services fallback, a bounded five-scalar sample per measured eligible firm, and a constant-size calculation only for a qualifying long-term proposal. Food, public projects, housing, normal shopping and access to the existing small infrastructure route use their own rules. The only monetary effects flow through paying for fewer installed slots, funding those costs and the existing household distribution, and the downstream hiring, wages and sales they enable.

## Assess outcomes through the real sequence

Run paired small markets on the comparison commit and the feature commit. Fix opening rosters, available applicants, household cash and orders to primary sellers. Feed those intentions at the ordinary planning boundary. Let checkout determine who reroutes, the effective price, and what the customer can fund. Let actual slot installation, applicant matching, payroll credit and cancellations, production and subsequent cash evolve. Start with a fully staffed private Services firm, a sold-out competitor, and a realistically funded infrastructure balance that keeps the late-week route from consuming the evidence before the first long-term decision. Follow the persistent overflow through at least the first decision plus the existing 26-week cooldown, and record the hiring and settlement after the next financing opportunity. Use the same horizon for the short surge comparison where practical.

- **The overflow goes away.** The feature should install usable space at a lower total cost and preserve funded service to the remaining customers. Trace which worker slots exist and fill, paid deliveries, payroll, idle output, cash and debt.
- **The overflow persists.** The smaller project can miss paid orders the larger one would have filled. Record the tradeoff, subsequent expansion, applicants and realized payroll. A design that leaves the firm with no path to add needed slots or carries unpaid wages is unsuitable. Check the following ordinary funding opportunity rather than only the initial requested amount.
- **Direct orders remain strong.** Repeat with the receiving firm's own orders arriving after inbound fallback fills a slot. Funded own lost orders can support the ordinary project size. Repeat with buyers genuinely short of spendable cash to verify the decision uses funded evidence. Record exact 95% eligibility, a week with zero settled reroutes, repeat measurements, gaps, and the return from entrants or snapshots without five active weeks.

For the surge path, exercise cash-only, mixed, fully borrowed, ordinary-denied/smaller-approved, and smaller-denied funding. Reconcile the cash contribution plus bank debit to the single household capital distribution. Verify full denial leaves financing, slots, and cooldown unchanged. If a later ordinary infrastructure project proceeds, reconcile its cost to the treasury skim and miscellaneous-revenue pool. Trace requested hires, funded headcount and wages, cancellations or layoffs before payday, unfilled work and project debt. A small live scenario establishes the mechanism and tradeoff in the affected state.

Use the published `6d77b4f` delivery base and exact seed-43 setup, `income_first`, 1,000 households, ten warmup weeks and 312 post-activation weeks, with external shocks off and the same household settings as the saved rerouting comparison. Try parity against the cached comparison through the first changed proposal, including active rerouting weeks. Compare ordinary quote, effective funded amount, actual purchase and the precise first economic divergence. If pre-intervention source or output parity cannot be established, run one unmodified control on the same published base with the same observer. Keep at most one paired run per seed and at most two seeds. Use seed 42 before claiming repetition across seeds.

Report cumulative, early, final-104-week and each final 52-week delivery of Services, unmet Services, total project costs and costs by route, funded payroll and cancellations, food access, household budgets and capital distributions, and money net of injections. In the live pulse case the smaller project must cost less and meet the remaining funded work after the surge fades. In the persistent live case, follow funded orders through the cooldown and later quotes; a path that repeatedly cannot grow into demonstrably funded demand requires revision. For town evidence, flag a capacity bottleneck when lower aggregate Services delivery and higher fundable unmet demand persist in both final 52-week blocks. Investigate sustained payroll losses or deteriorating household food access across both blocks as spillovers. The ledger must conserve and all downstream amounts must reconcile. Early differences and observed tradeoffs receive explanation in the PR. A draft can present the evidence and remaining uncertainty. Adoption requires the completed assessment.

## PR scope and rollback

The published `origin/household-realism` tip `6d77b4f` includes the stockout-routing dependency. The user said that dependency is in the PR process. Stack the narrow feature on that tip and target `household-realism`. Check the three-dot diff and report the exact base and head. State that the rule runs automatically on income-first Services when existing firm-specific fallback is active. Reverting the feature commits returns to ordinary project sizing. Completed installations, loans and payments already entered into a simulation remain booked transactions.

## Matched assessment

The [small live comparison](../../backend/tools/checks/run_services_reroute_capacity_paths.py) runs the same opening state and orders against two checkouts using `--backend`. No new setting selects the feature. The tested control was `6d77b4f` and the feature was `1921d09`. The 22-household cases each follow 36 income-first weeks. Both engines matched through week 5. The runner scripts intended shopping at the original sellers and retains actual checkout, financing, matching, payroll and delivery. The opening infrastructure claim stays active throughout these cases. Later infrastructure funding is measured separately in the town pair.

- After the pulse faded, both engines supplied the receiver's 22 weekly orders. The reference installed ten slots for $5,000 and the feature installed one for $500.
- With persistent overflow, the smaller project initially left more funded orders unfilled. At week 32 the feature funded another ten slots. The firm reached 15 paid workers from an opening five, with no receiver wage arrears. Fundable unmet Services fell from 52.76 units in week 31 to 20.40 in week 32.
- Funded direct orders supported the ordinary $5,000 quote. The same intended orders from a cash-short customer resulted in the $500 quote. The focused financing cases exercised cash, mixed and borrowed funding, an ordinary denial followed by smaller approval, and full denial. The money reconciliation held within $0.000001 in the live cases.

The population pair used seed 43, 1,000 households, the existing rerouting and savings experiment settings, ten warmup weeks and 312 post-activation weeks. It compared the same two commits. Recorded economic outcomes and financing attempts matched through displayed week 17. In week 18 the first changed project at a five-slot firm went from a fully borrowed $5,000 project adding ten slots to a cash-funded $500 project adding one. The firm met repeated infrastructure denials through week 43 and installed ten more slots in week 44. It delivered about 928 units across weeks 18–44 in the feature, versus 2,205 in the comparison, as both staffing and order allocation changed.

| Seed 43 measure | Control | Feature |
| --- | ---: | ---: |
| Delivered Services units, all 312 weeks | 284,736 | 281,185 |
| Fundable unmet Services units, all 312 weeks | 24,978 | 24,333 |
| Funded Services project costs, all 312 weeks | $693,875 | $631,375 |
| Delivered Services units, final 104 weeks | 119,124 | 114,712 |
| Fundable unmet Services units, final 104 weeks | 703 | 227 |
| Unfunded current Services pay, all 312 weeks | $9,835 | $13,728 |
| Private Services payroll layoffs, all 312 weeks | 90 | 57 |

Unfunded pay is summed over all Services firms. The measured private Services firms had zero closing payroll arrears throughout both runs. Aggregate Services delivery declined in both final 52-week blocks. Fundable unmet orders fell in the first of those blocks and rose in the last, so the pair did not show a sustained capacity bottleneck under the predeclared two-block definition. The final block still warrants caution. Money net of injections reconciled and the maximum absolute drift was below $0.00001 in each run.

These results support the smaller project for a transient pulse and reveal a meaningful delay when the extra work persists. The overall comparison shows capital savings alongside lower service delivery and higher unfunded current pay across Services. Keep the PR in draft for review of that tradeoff. This is one matched seed and does not establish a general improvement or an equilibrium.
