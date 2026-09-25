# Coordinated economic implementation: review record

**2026-09-22.** This records actual implementation and its verification separately from the historical proposal rounds. The [execution record](../ECONOMIC_IMPLEMENTATION_EXECUTION.md) describes the implemented mechanisms, selected constants and public access. Sol medium implemented bounded modules in one isolated candidate; Codex reviewed their integration and corrected defects. Claude Fable 5.1 independently inspected two frozen source snapshots with read-only tools. No LLM is invoked for individual simulated agents.

## Independent audits and dispositions

The [foundation audit](ECONOMIC_IMPLEMENTATION_FABLE_FOUNDATION.md) and [composed audit](ECONOMIC_IMPLEMENTATION_FABLE_COMPOSED.md) are preserved verbatim. Their [foundation](evidence/ECONOMIC_IMPLEMENTATION/fable-foundation-manifest.json) and [composed](evidence/ECONOMIC_IMPLEMENTATION/fable-composed-manifest.json) manifests identify source hashes, actual model, tool calls and unchanged audit inputs. Fable did not execute tests. Later corrections below were reviewed and tested by Codex; they are not described as a fresh Fable sign-off.

| Finding | Final disposition / evidence |
|---|---|
| PF-01 firm/property tax inputs | Snapshot includes cash, sector, property rate, capacity and price. Full-step partial-pay test checks ordinary withholding plus actual property-tax receipt. Progressive tax rules remain. |
| PF-02 care retries | Retry is wired before new requests. Unchanged accepted quotes retain the episode without another arrival or request draw; higher prices require new consent. Two-step regression covers the actual hook order. |
| PF-03 shortage reporting | `metrics.payment` exposes actual paid/unpaid income, benefit denials, wage claims, care/rent outcomes, restrictions, loans and projects; websocket frames refresh it. |
| PF-04 recovery hold totals | Cash totals include protected recovery and transient settlement accounts once. Codex also added the carried misc pool and queued-firm cash; deposits remain bank liabilities and are not counted as another cash stock. |
| PF-05 versioned exit claims | The payment exit route settles and writes off the authoritative versioned claim once. Registered claims, direct Treasury debt and mortgages share the creditor waterfall after worker recovery. |
| PF-06 landlord exit | Tenant link, ownership-of-shelter flag, rent, arrears and landlord mirrors are cleared immediately. |
| PF-07 ID-set growth | Rechecked rather than patched: `_ensure_ids` rebuilds its set from active loans each tick. Serial numbers remain monotonic. |
| PF-08 quote mismatch | Services deposit quotes and actual goods clearing use the same effective price floor. |
| FINAL-01 construction credit gate | Housing self-financing and loan routes reject live wage arrears; loan routes also reject an active firm credit cooldown. Existing mortgage DSCR/LTV/reserve conventions remain distinct from registered-loan underwriting. |
| FINAL-02 exiting care provider | The household keeps its episode and becomes eligible for retry at a live provider; the old queue link is cleared. Regression checks a surviving provider and no extra arrival. |
| FINAL-03 project status | Reporter treats only `authorized` and `assigned` Services projects as active. Completion and cancellation are tested. Housing's live dictionary contains only pending projects. |
| FINAL-04 ownerless residual | Residual cash after workers and creditors enters the existing misc recipient pool when no valid owner can receive it. Regression checks treasury plus misc receipts equals the former firm's cash. |
| FINAL-05 mortgage mirrors/exit | Installment mirror includes both mortgages and registered claims. Exit includes only principal and documented unpaid current interest, not another week's interest after payment. |
| FINAL-06 housing shortage blocks entry | In the new scenario, the old shortage branch no longer prevents funded Food/Services entry. Legacy behavior remains selectable. |
| FINAL-07 CEO tax convention | Retained and disclosed: ordinary-worker wage tax excludes separate CEO pay. No claim of a comprehensive personal-income tax is made. |
| FINAL-08 complete currency observation | New-scenario money totals include misc and held cash. Full-step tests independently sum counterparties rather than trusting that metric. |
| Rent monitor | Counterfactual accumulator is initialized so the existing renewal observation can run. It is a diagnostic, not a payment or price change. |

## Coordinator findings beyond the external audit

- Payroll validates the complete population withholding plan before payer/claim mutation. Scarce-payroll floating-point residuals are bounded without accepting invalid negative inputs.
- The settled operating-cashflow signal uses actual paid payroll and operating cash outlays. Negative business cashflow denies credit; it is not a fatal data error.
- Durable per-tick capital-payment records survive later planning calls and pay their original recipient route once. A long-term Services loan explicitly goes from bank to firm to its capital recipient.
- Configured parameters are captured when every Economy is initialized, including library use, so later reporting does not inherit another session's context.
- Fable reviewed a temporary old-arrears-only relief change. Codex rejected it against PS3.1 and restored the requirement for a verified current rent shortfall. Historical audit inputs stay unchanged.
- Two aggregate cash changes were traced to the legacy random household cash-injection/withdrawal routine. The new scenario now explicitly models these as cash-limited Treasury transfers or collections, respecting reserved funds. Legacy still has its original exogenous cash shocks. This is a selected fiscal-shock abstraction, not a calibrated monetary institution.
- The goods adapter now reads the authoritative receipt and purchase book directly, removing redundant copies and repeated per-line policy/target lookup while preserving settlement order.

## What the evidence establishes

Focused tests cover actual payroll and withholding, held CEO pay, partial rent and notices, effective deposit quotes, covered and bank-funded care, versioned loan schedules/defaults, worker-first exits, whole funded housing projects, public project worker/capacity timing and launch-only configuration. Composed tests run real bank economies for 60 ticks in both timing arms and both execution modes. They reconcile every household ledger, registered debt mirrors, clearing balances and aggregate currency on every tick.

The development UI was exercised in Chrome: selecting income-first, publicly covered care and mixed receipt use launches the run, ticks advance, and the three convention selectors lock while ordinary policy controls remain available. The final results below were collected against the integrated source.

## Final verification and integration

The reviewed implementation is integrated into `/Users/aymanislam/EcoSim_v_2/EcoSim`. The original 435-file working baseline was checked before copying; existing local work was preserved. HEAD and freshly fetched `origin/main` were both `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`. No commit or push was made. The [integration manifest](evidence/ECONOMIC_IMPLEMENTATION/integration-manifest.json) identifies copied files and their before/after hashes; backend hashes also match the unchanged benchmark candidate.

| Check | Result and limits |
|---|---|
| Original-checkout backend suite | **440 passed, 8 research tests deselected, 1 expected failure**, 7.41 seconds. Command: `.venv/bin/python -m pytest`; [complete output](evidence/ECONOMIC_IMPLEMENTATION/backend-pytest.txt). |
| Backend static checks | `.venv/bin/python -m ruff check backend`: passed. |
| Frontend | 91 tests across 20 files passed; Vite production build passed on the identical candidate frontend source. |
| Actual browser | Fresh original-checkout backend; Chrome launch with 100 households, early income, covered care and mixed receipts reached tick 164. All three scenario selectors locked, ordinary policy controls remained available, suspend worked, and captured warning/error logs were empty. Final control layout was visually inspected. |
| Composed accounting | Real 100-household bank economies over 60 ticks, both timing arms and execution modes, reconcile household cash ledgers, debt mirrors, clearing and aggregate currency each tick. Included in the suite above. |
| Public project reachability | Unmocked planner and labor matcher, seed 42, 100 households, 40 ticks: 30/28 completions in early normal/cached mode and 31/30 in late normal/cached mode. Each observed completion had the full quoted payment and one slot. [Evidence and reproduction recipe](evidence/ECONOMIC_IMPLEMENTATION/natural-project-smoke.json). Targeted tests separately verify delayed activation and exclusion from ordinary output. |
| Scenario comparisons | Four cases × two seeds × two modes, 60 ticks, plus replay. Selected initial actor hashes match within each seed/mode; replay's selected final state and outcomes match. [Raw conditions/outcomes](evidence/ECONOMIC_IMPLEMENTATION/comparisons.json); [runner](run_economic_comparisons.py). |

The comparison cases are the existing wage-tax parameter at 15% versus 40% with progressive rules preserved, early versus late availability of paid income, and patient-funded/reserved receipts versus public coverage/care earmarking. The coverage case changes both payer and receipt use, so it is not a pure one-parameter treatment. These small runs establish working, reproducible comparisons, not calibrated policy rankings. The actor hash covers the listed balances, employment/contracts, health and capacity; it does not certify every hidden field or identical endogenous shocks.

## Measured runtime: target not met for the new scenario

The [benchmark runner](benchmark_economic_implementation.py) ran 48 fresh processes: 1,000/10,000 households, normal/cached mode, two seeds, two repeats, and three interleaved arms. Each run had 40 ticks; the first ten were excluded from timing summaries. The frozen baseline includes the prior local changes and PAY-01. Baseline and candidate backend hashes remained unchanged during measurement. [Raw ticks, workload counts, memory and source manifest](evidence/ECONOMIC_IMPLEMENTATION/timing/manifest.json) accompany the [complete summary](evidence/ECONOMIC_IMPLEMENTATION/timing/summary.json).

Percent changes below are the median of four paired changes against baseline legacy. Parentheses show the observed minimum/maximum paired change, not a confidence interval. Absolute time is the median of the four run medians; percentage calculations use unrounded values.

| Households | Mode | Candidate scenario | Median tick | Median change (range) | P95 change | Peak RSS change |
|---|---|---|---|---|---|---|
| 1,000 | normal | legacy | 79.7 ms | +1.2% (+0.6 to +1.5%) | +0.6% | -0.5% |
| 1,000 | normal | income_first | 104.5 ms | +32.0% (+30.6 to +33.0%) | +21.2% | +12.4% |
| 1,000 | performance | legacy | 25.7 ms | +2.1% (-4.6 to +4.1%) | +0.4% | +0.5% |
| 1,000 | performance | income_first | 44.6 ms | +76.7% (+66.6 to +80.3%) | +19.7% | +10.8% |
| 10,000 | normal | legacy | 830.8 ms | +1.2% (+0.1 to +1.7%) | +0.6% | +0.4% |
| 10,000 | normal | income_first | 1064.3 ms | +29.1% (+27.8 to +30.2%) | +20.1% | +15.9% |
| 10,000 | performance | legacy | 280.8 ms | +0.8% (-1.0 to +2.3%) | +0.0% | -0.0% |
| 10,000 | performance | income_first | 506.9 ms | +83.1% (+70.1 to +87.9%) | +17.1% | +16.6% |

**The new scenario fails the 5% cumulative median/p95 target.** At 10,000 households, its median tick is about 1.06 seconds normally and 0.51 seconds with cached decisions. Cached mode remains faster in absolute time, but its percentage increase is larger because the new settlement still executes every tick. All measured legacy pairs stayed within 5%; this is evidence for these workloads, not a universal bound. New economic behavior can change firm counts, employment, queues and claims, so the new-arm difference is total observed cost rather than an isolated algorithm comparison. The duplicate goods-book optimization is already included. Performance optimization remains open; correctness tests do not close this gate.

Generated lifecycle and public-institution Wiki pages were refreshed through the approved OpenWiki tool. Historical proposals and Fable snapshots remain unchanged. Inflation institutions, economic-system presets, full empirical calibration and checkpoint restore remain outside this implemented minimum package.

## Interpretation limits

These changes make mechanisms and constraints more explicit. They do not calibrate the economy to a country, turn nominal sales into real GDP, implement a CPI/central-bank rule, or supply capitalism/socialism/communism presets. New-loan quote stress is a separately named experiment. Medical qualification remains simplified, construction retains implicit recipients, mortgages retain their own underwriting/payment convention, and rent relief has the specified initial-tenancy eligibility boundary. A common seed is reproducible initialization, not proof that all endogenous disturbances match across policy paths. No complete mid-run save/restore is claimed.

The 5% cumulative median/p95 speed target is a separate engineering gate. Correct settlement and passing tests do not imply that target was met; the timing table must be read with workload and variability.
