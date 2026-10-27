# Services component results

The pricing package is the dominant cause of the earlier difference in this screen. Expansion restrictions and hiring patience have smaller effects. This identifies a pricing/financing interaction to examine; it does not establish that removing recursive markup was wrong, or that the bank should approve an unaffordable loan.

Scope: [experiment contract](SERVICES_COMPONENT_EXPERIMENT.md). No production code, economic setting, policy, household behavior or patience threshold changed during this investigation. This experiment preceded the owner-authorized PR publication of SERVICES-01/02. [Compact aggregate data and source hashes](evidence/services/README.md) are included for review; external raw artifacts remain separately retained.

## Completed comparisons

24 normal-mode runs: all eight combinations of P (stable pricing), E (staffed sustained-demand expansion) and H (retained staffing/three-observation recovery), seeds 42/43/44, 1,000 households, 80 ticks, warmup 10, `income_first`. Each mean represents three independent seeded trajectories, with no timing repeats counted as additional economic samples. Two additional seed-42 replays observe the existing loan-return branches; there are 26 completed diagnostic runs in total.

P comprises both persistent markup intent and the consistent measured-markup denominator. These data do not isolate those two coupled pricing changes. E includes the two loan routes; H includes the matcher safeguard and funded installation's staffing lifecycle. No parameter search was performed.

Tick-80 means:

| Selected mechanisms | Services units sold | Services workers | All employed households | Mean happiness | Mean health |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original main | 808.5 | 208.0 | 510.7 | .502 | .727 |
| Hiring patience only | 763.6 | 198.7 | 508.3 | .495 | .721 |
| Expansion gate only | 782.0 | 202.7 | 506.3 | .501 | .726 |
| Expansion + hiring | 728.6 | 193.3 | 502.3 | .493 | .720 |
| Pricing only | 229.2 | 63.3 | 290.3 | .398 | .584 |
| Pricing + hiring | 230.2 | 62.7 | 288.0 | .397 | .576 |
| Pricing + expansion | 229.8 | 63.7 | 287.7 | .398 | .585 |
| All three | 230.4 | 63.0 | 290.3 | .396 | .580 |

Across the last 40 completed weeks, mean weekly household gross wage receipts were $22,107 on main, $21,920 with E alone, $21,438 with H alone, $15,884 with P alone and $15,793 with all three. These are funded completed household ledger receipts, including any wage arrears/recovery; they are not posted contracts or a Services-only wage measure. Household wellbeing and actual service quantities fall together with the pricing package, so the GDP difference is not solely a lower nominal price.

The full factorial decomposition is in `analysis.json`. Interactions matter: the effects of E and H measured against main cannot simply be added to P's effect. P alone produces almost the same endpoint as the complete package. An all-order Shapley attribution allocates about 93% of the Services quantity difference to P, but that allocation is an explicit convention, not a unique causal partition. The simpler and more robust comparison is the directly executed P-only versus complete-package result.

## What changes first

The earlier description of a 72% decline was a comparison with the original version at week 80, not proof that the corrected economy's Services sales fell 72% over time.

In the paired seed-42 town, private Services sold about 220 units at week 40 in both versions. With P alone they still sold about 218 at week 80, with 60 installed worker slots. Main instead expanded from 60 to 203 private slots and sold about 816 units by week 80. Baseline Services is excluded from these particular counts. Thus much of the difference is growth in the old arm, rather than an immediate loss of existing customer purchases in the corrected arm.

The paired replay confirms that existing long-term financing is part of that divergence. During ticks 40-79:

| Seed-42 long-term Services route | Original main | Pricing only |
| --- | ---: | ---: |
| Planner calls, including cooldown/ineligible cases | 480 | 480 |
| Actual loan approvals | 13 | 0 |
| Calls refused at the bank origination step | 177 | 440 |

For each counted origination refusal/approval, the synchronous trace links the outer long-term planner return to its immediately preceding origination and underwriting returns with matching tick and firm. All linked rejections failed the existing debt-coverage inequality. Other traced private Services loan purposes are excluded from these long-term-route counts; the raw nested-function totals are not a count of long-term denials.

Concrete case, firm 25 at tick 40 with five workers in five slots:

- Pricing-only quote: $11.42; positive estimated marginal-worker contribution: $14.88.
- Prior settled operating cash flow used by the bank: $85.61.
- Existing weekly debt installments: $123.80; proposed $5,000 expansion adds $11.40 a week.
- The bank permits total installments up to 35% of that prior cash flow: $29.96. The $135.20 total obligation therefore fails.
- The original version at the same tick also refuses this firm's loan. Its higher pricing supports larger cash flow later, and some firms subsequently qualify. This is not an immediate yes/no difference at tick 40.

Source explains the existing obligation and cost boundary. Queued entry attempts a $25,000, 208-week startup loan; its named-sequence direct-Treasury fallback gives a $123.798 weekly installment. The underwriter includes direct Treasury installments as well as registered bank dues. The Services quote, however, uses payroll plus Services-infrastructure installments; it does not explicitly budget startup Treasury debt. The bank's prior operating-cash-flow measure excludes debt payments, so this observation is not evidence of subtracting that same repayment twice.

Relevant current source: `Economy._activate_queued_firms`, `_issue_firm_loan`, `_phase_dividends`; `FirmAgent._service_pricing_costs`, `plan_pricing`; `payment_loans._underwriting_due_index` and `can_underwrite`.

The observed financing refusal is consistent with the current bank rule. It does not prove the rule is economically wrong. Nor does one replay apportion every household or sector feedback. The source/trace establish a concrete compatibility question between the startup obligation, ordinary operating earnings and expansion finance. They do not justify restoring runaway pricing or guaranteeing expansion for every firm.

## One bounded next decision

Hold the selected three-week recovery and full-space expansion rules fixed. Examine only **Services operating cash flow versus startup repayment and expansion affordability**, using the five-worker salon as the example. Determine whether ordinary earnings and the financing obligation are mutually coherent before selecting a change. Any later choice about pricing, loan size/term or underwriting needs an explicit business rationale and customer/worker effects; this report does not authorize changing all of them or targeting a desired GDP result.

Food strategy, R&D, quality, baseline retirement, household shopping and general banking redesign remain outside this follow-up.

## Integrity and limits

- Authoritative main was fetched and verified equal to HEAD at d71485e before this investigation. The three production hashes remain those of the preceding SERVICES-01 validation.
- All 24 cases have identical common initial dataclass state, tracked profile and random-state fingerprints within each seed. No new initialization draw or customer information was introduced.
- All six all-off/all-on cases reproduce the preceding panel's corresponding endpoints exactly. Both loan replays reproduce their screen endpoints and final RNG fingerprints exactly.
- All 1,920 screen ticks completed without exceptions. Maximum absolute completed clearing residue was $4.70e-10. Maximum absolute injection-adjusted cash-stock residual was $1.49e-6 using the existing bank/holds-inclusive money helper. These checks cover that measurement perimeter, not every resource constraint.
- Firm identity epochs prevent joining a replacement's completed state to a predecessor's plan. Two independent Sol medium source-review rounds checked treatment partition and observer neutrality; review 2 inspected 22 cases, and the parent executed the final 24-case integrity/analysis checks.
- Initial observer-version-1 pilot files were preserved and excluded after the identity/wage-label corrections. Observer-version-2 pre-payroll book counters were sampled before actual payroll settlement; those zero fields are explicitly excluded from analysis. Actual completed household wage ledgers are used instead. The separately labeled post-tick Services-employer subgroup is not an earning-employer attribution.
- This screen is only 1,000 households, `income_first`, three seeds, 80 ticks. It does not establish generalization to `income_late`, 10,000 households or longer horizons. It does not establish a calibrated real-world effect, a pure demand elasticity or that pricing alone has a particular runtime cost.
- Snapshot generation and observers are external research instrumentation. No production switch, actor information, update cadence or permanent customer tracking was added. The existing functional suite was not rerun because no production/test code changed in this follow-up. Generated wiki refresh for SERVICES-01 remains due as previously documented.

Evidence: `C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/services-component-experiment/` contains frozen sources and selections, all case manifests/raw benchmark JSON, `analysis.json`, the two replay cases, raw `loan-events.json` and filtered `loan-summary.json`. Reproduction scripts are `services_component_experiment.py`, `services_component_analysis.py` and `services_loan_trace.py` in the parent evidence directory. The filtered loan summary additionally checks the synchronous event linkage; nested totals must not be relabeled as route-specific counts.
