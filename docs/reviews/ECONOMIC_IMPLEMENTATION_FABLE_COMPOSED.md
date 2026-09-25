I've finished the source reads (about 48 focused reads across the seven payment modules, the Economy.step call sites, agents, server, run_evidence and the payment tests). Writing the report now.

## Source-audit report: completed payment implementation

**Verdict up front.** Within what I inspected, the wired PS3.1 path still creates no money and settles nothing twice. All eight foundation findings are closed in current source. The new material defects are one credit-gate bypass on the mortgage route, one latent stranded-patient path on provider exit, and a reporting status mismatch. The rest are retained modeling limitations and evidence gaps. I ran nothing.

### Recheck of PF-01 to PF-08

| ID | Status | Evidence anchor |
|---|---|---|
| PF-01 | Closed | `backend/economy.py:4783` emits the five snapshot keys in payment arms; rent and project receipts enter revenue at `economy.py:4750` |
| PF-02 | Closed | `economy.py:1666` calls the requeue before the enqueue; `payment_sectors.py:458` increments arrivals only when not a retry |
| PF-03 | Closed | `economy.py:7986` exports `metrics["payment"]` plus unpaid, denied, exit and claim totals; `server.py:2610` puts the snapshot in the frame |
| PF-04 | Closed | `economy.py:7977` adds recovery holds, clearing cash, CEO holds and late income to money supply |
| PF-05 | Closed | Legacy write-off gated to legacy at `economy.py:5048`; payment exits go through `settle_firm_exit_claim` at `economy.py:4923`, and exited claims are dropped at `economy.py:5054` |
| PF-06 | Closed | Tenants of exiting landlords unlinked at `economy.py:5016` |
| PF-07 | Closed | `payment_loans.py:66` rebuilds the ID set from active loans on every `_ensure_ids` call, which runs each tick via `payment_loans.py:227` |
| PF-08 | Closed | Quotes use the effective market price at `payment_sectors.py:177` |

### Implementation defects

- **FINAL-01, Medium. Mortgage route bypasses every firm credit gate.** `start_payment_mortgage_project` at `backend/payment_projects.py:101` checks DSCR, LTV and bank liquidity only. It never checks `payment_wage_arrears`, never calls `can_underwrite`, and never consults the default cooldown, unlike `_issue_firm_loan` at `economy.py:5423`, the long-term route at `economy.py:5582`, and `can_underwrite` at `payment_loans.py:621`. Trigger: a housing firm with open wage claims, occupancy at or above 0.85, and cash below two quotes. `try_start_self_funded_project` sets the loan flag at `payment_projects.py:95`, and the next 6.6b pass funds a mortgage. Consequence: bank cash flows to the construction sink while workers remain unpaid, the exact "loans before old wages" outcome PS3.1 gates elsewhere, and a firm inside a v2 default cooldown can still borrow. Minimal fix: return False in `start_payment_mortgage_project` when `firm.payment_wage_arrears > EPS` or the cooldown key is active. Discriminating test: housing firm with one wage claim, full occupancy, cash 500, lendable bank; after `step()` no `LoanContract` exists and the misc pool is unchanged.

- **FINAL-02, Low, latent. Provider exit strands queued patients.** The payment-arm exit block at `economy.py:4978` resets nothing on households whose `queued_healthcare_firm_id` is the exiting firm. Both the enqueue at `payment_sectors.py:411` and the requeue at `payment_sectors.py:591` skip any household with a non-None queue id, and settlement iterates only live firms at `payment_sectors.py:474`. Consequence: the patient never requests care again, the due tick ages forever and inflates the 255-plus counter, and the deposit quote drops the care line. Reachability: only non-baseline healthcare firms can exit. The library factory creates none at `tools/runners/run_large_simulation.py:133` and entry never spawns Healthcare, so this is latent in library runs and reachable in composed fixtures. Legacy has the same gap at `economy.py:6822`. Fix: in the exit block, clear the queue id and enter tick and set `payment_care_due_retry` for affected households, keeping the episode. Test: two healthcare firms, one private with a queued patient, forced exit; next tick the patient is requeued at the survivor without a fresh arrival.

- **FINAL-03, Low. Project status names disagree with the reporter.** `payment_reporting.py:118` treats a Services project as active unless its status is "complete" or "cancelled". Actual statuses are "completed", "cancelled_unpaid_worker", "cancelled_provider_exit", "expired_unworked" and "payable_unfunded" at `payment_government.py:33`, `:108`, `:127` and `:164`. So `services_active` reads True after completion. `housing_by_status` at `payment_reporting.py:117` always reports "active" because housing projects carry no status key. Fix: define active as status in {authorized, assigned}. Test: after `complete_payment_services_project`, the snapshot reports `services_active` False.

- **FINAL-04, Low. Ownerless exit residual leaves the money supply.** The Services receipt is credited at 11.5 (`payment_government.py:118`) and exits run at 12. `_payment_settle_exit_creditors` at `economy.py:4940` pays any residual to owners only when `firm.owners` is non-empty, and owners are empty for every firm except founder-funded entrants (`agents.py:2512`, `economy.py:5350`). Reachability is narrow: the provider must pass the paid-week check and still meet the zero-cash streak. It is the only post-phase-9 credit that makes a positive residual possible. Fix: route ownerless residual to the misc pool. Test: completion and forced exit in one tick; cash plus misc pool unchanged.

- **FINAL-05, Low, telemetry. Mortgage mirrors and exit telemetry drift.** `economy.py:5781` sets `bank_loan_payment_per_tick` to mortgage PMT only when a housing firm also has registered claims; `_sync_mirrors` at `payment_loans.py:348` corrects it only for firms with a due that tick. At exit, `economy.py:4913` sizes the mortgage claim with one tick of interest, so loss provision and defaults overstate by principal times rate. Neither moves cash.

### Retained modeling limitations

- **FINAL-06. Entry is frozen during any housing shortage.** `_maybe_create_new_firms` at `economy.py:5132` returns before creating any Food or Services firm whenever housing units are below households. The legacy instant expansion is correctly disabled in payment arms at `economy.py:5136`, but the early return remains and funded construction is at most 4 units per firm per 4-tick project. Latent in library runs, which seed housing units equal to households at `run_large_simulation.py:78` and have no births.
- **FINAL-07. CEO pay is untaxed and outside ordinary income.** Holds release at `payments.py:198` with no withholding and never enter `paid_income.gross`, so tax beliefs and underwriting exclude it. Legacy also did not tax it (`economy.py:1294` with a wage-only snapshot). The "progressive taxes" claim therefore covers worker pay only.
- **FINAL-08. No full conservation metric.** `money_supply` excludes the misc pool carried across ticks in both arms. `conftest.total_money` includes it but excludes bank reserves, deposits and holds.
- Direct-treasury seeds at `economy.py:5226` and the exit tax before worker recovery at `economy.py:4981` are choices consistent with the accepted queue, not defects.

### Evidence gaps

- No test asserts money conservation through `step()` in a payment arm. The acceptance tests at `test_payment_acceptance.py:161` and `:205` check only clearing zero, empty holds and restrictions not exceeding cash.
- No full-step test proves a Services project completes without monkeypatched labor matching. `test_payment_government.py:117` asserts on completion events only if they appear.
- The mortgage route is tested in isolation only (`test_payment_projects.py:110`). No test runs a firm exit with registered v2 claims, a mortgage and unpaid workers through `step()`.
- The "monitor" rent counterfactual at `payment_sectors.py:355` is a silent no-op because the attribute is never initialized on `Economy`.
- Benchmarks are outside this audit. I make no performance claim.

### Verified correct in current source

Per-session config isolation via the ContextVar proxy with `use_config` on setup and step (`server.py:367`, `:1850`, `:2093`) and the switch guard at `economy.py:1552`. Treasury debits guarded by free cash, including entry seeds and stimulus. Services project: restriction reserved after B and assistance, incremental hire via the plan increment at `economy.py:1937`, paid-week check, receipt taxed next tick once, slot next tick, exit assessment before creditors. Care retry keeps the episode and adds no arrival. Capital recycling reads a single route list in payment arms at `economy.py:6007`. Exit waterfall runs workers, then pro-rata creditors, then owners. One deposit pass, cash-capped progressive taxes, and no accidental quadratic loops. The audit is bounded to the files and line ranges cited above.