# Business behaviour with controlled demand

Run one business with a small worker pool and set its customer demand directly. This covers the questions Ayman selected: money versus no money, hiring, wage increases and cuts, capacity expansion, and sustained weak demand.

The [saved report](../evals/2026-09-28-business-scenarios/report.md) contains the default 19 runs, with a summary and weekly tables. [Raw results](../evals/2026-09-28-business-scenarios/results.json) include the plans, receipts, starting conditions, config and source hashes.

## Run the preset comparisons

From the repository root:

```bash
.venv/bin/python -m backend.tools.checks.run_business_scenarios
```

This runs 12 weeks per case, stopping early if the business closes, with seed 1337. Reports go to a new directory under `benchmarks/results/business-scenarios/`. No server, browser, LLM or API key is needed.

| Group | Starting conditions and question |
| --- | --- |
| `cash` | Same business with 0, 120 or 10,000 cash; also two startups with no workers, with and without money |
| `hiring` | Strong demand with available applicants, no eligible applicants, or applicants expecting much higher pay |
| `wages` | Sales rising, sales falling, competition for workers, and a Services firm with persistently weak sales |
| `capacity` | Food expansion through capital and workers; Services expansion with a funded bank versus no bank |
| `low_demand` | No sales with a cash buffer or no money, Services with no sales, and a demand crash followed by recovery |

For example:

```bash
.venv/bin/python -m backend.tools.checks.run_business_scenarios --case hiring wages
.venv/bin/python -m backend.tools.checks.run_business_scenarios --case capacity --ticks 20
```

## Set demand yourself

```bash
.venv/bin/python -m backend.tools.checks.run_business_scenarios \
  --case custom --cash 100 --initial-demand 30 \
  --demand 30,30,90,90,0,0 --ticks 6
```

This starts with 100 cash and a previous demand observation of 30 units, then asks for 30, 30, 90, 90, 0 and 0 units in successive weeks. These are orders; the firm still has to employ workers and produce enough to fill them.

- **`--initial-demand`** seeds the opening sales/shortage history and expectation once. Prior sales are limited by the opening productive capacity. It does not credit extra business cash.
- **`--demand`** controls requested units during the experiment. One value stays constant; a list changes by week. The final value repeats through `--ticks`. To make demand temporary, end the list with `0`.
- **No knowledge of future sales:** the business makes this week's production/hiring decisions from its previous observations. Current scripted orders arrive at market clearing and become information for the following week.
- **`--cash`, `--workers`, `--population`, `--job-seekers`** control business funding and labor availability. Population defaults to 12; three people already work at the firm and the other nine are potential applicants. Actual search and matching use the engine's rules.
- **`--wage` and `--reservation-wage`** set the initial posted/contract pay and workers' initial wage expectations. Those expectations can change during the run.
- **`--category Food` or `--category Services`** selects the production model. `--capacity` is an output ceiling for Food and a whole number of worker slots for Services; defaults are 200 and 3 respectively.
- **`--bank-cash 100000`** enables a bank with those initial reserves. The firm still has to pass the existing lending rules. Zero disables the bank.
- **`--buyer-cash`** caps the external customer's total spending for the entire experiment; default 1,000,000. Each filled order debits that balance exactly once and becomes firm revenue through normal settlement.
- **`--seed`, `--ticks`, `--output-dir`** set reproducibility, duration and output location. Existing report files in an explicitly chosen output directory are replaced.

Custom starting flags automatically select the custom run if `--case` is omitted. Combining those flags with preset-only groups is rejected so a requested cash/demand change cannot be silently ignored. Limits are 100 households and 52 weeks; inputs must be finite, nonnegative and within the CLI's small-test limits. `--help` lists all options.

## What the experiment preserves and controls

The test-only `BusinessTestEconomy` inherits the real `Economy.step()`. Firm health assessment, plans, labor matching, production, wages, taxes, investment, credit repayment and exit run in their existing order. The existing audit log supplies intermediate plans and outcomes.

Only household shopping is replaced by one explicitly funded external customer. The normal goods resolver still limits sales by actual supply. Its goods leave the small economy; employees neither pay for nor receive those purchases. This creates an open business experiment, with the customer's opening cash recorded as an external endowment.

To isolate the selected business, the fixture excludes warmup/stimulus transitions, random shocks, new competitors, automatic government support, household shopping and health/wellbeing changes. Worker health and wellbeing start at fixed values; people outside the chosen eligible worker pool start too ill to work. The engine still counts nonemployees in its unemployment measure, which affects wage decisions. The firm has no CEO or owners in this fixture, so CEO pay and dividends are excluded. Benefit payments are set to zero, while the normal minimum wage and tax rules remain. Reported household/aggregate welfare is not a calibration result.

The ordinary application imports none of this test subclass. No firm rule, production tick, runtime setting or API was changed, so this addition introduces no work on the normal simulation path. Both Python and NumPy random states and the caller's configuration are restored after each experiment.

## First observations: seed 1337

These describe the saved controlled cases, not every firm or seed:

1. **No cash does not block payroll in the default model.** A firm can pay wages by going negative, then recover when customers buy. With no cash and no sales, the tested firm closes in week 9; the cash-rich zero-sales firm survives all 12 weeks.
2. **A vacancy is not a hire.** Strong demand produces hires when applicants are available, while the unavailable-worker case leaves requests unfilled. High wage expectations delay hiring and can induce higher offers.
3. **Demand alone does not guarantee wage growth.** Ordinary Food offers in these small towns are often at the policy floor of 36 because unemployment is high. When applicants reject the offered wage, the strong-demand case raises offers temporarily above 70. Posted offers and existing contracts can differ.
4. **Weak Services sales lower posted wages.** With one unit sold per week, the offer falls from 60 to 36 in steps of 3 after the initial delay.
5. **Zero Services sales expose a counter bug.** With repeated identical zero-sales outcomes, the weak-demand counter remains at one and the offer stays at 60. A strict expected-failure test records this finding; the business rule has not been changed.
6. **Capacity depends on the sector and financing.** Food grows capital and productive capacity while its output ceiling remains 200. In the funded Services case, installed worker slots grow from 3 to 14; without a bank they stay at 3 even while the firm spends on capital. Slots alone are insufficient without workers.

The first useful follow-up correction is the zero-sales Services counter, followed by checking whether the current posted-wage cuts should change existing contracts. Those are separate economic changes; this work provides reproducible evidence for deciding them.

## Verification

```bash
.venv/bin/python -m pytest \
  backend/tests_contracts/test_business_scenarios.py \
  backend/tests_contracts/test_agent_scenarios.py -ra
```

The focused suites report **33 passed and 1 expected failure**. The expected failure is the Services counter described above. The default public CLI runs **19 experiments with 152/152 harness/accounting checks**: supply limits, customer funding, receipt equality, payroll, employment links, closure and finite weekly data. These checks do not certify all existing economic rules or economy-wide money conservation.

Additional checks cover demand timing, opening-history injection, both wage directions, capacity versus output, recovery, startup hiring, finite customer budgets, input validation, report generation, failure exit status, repeatability and restoration of config/random state. Infinite diagnostic cash runway when there is no payroll is preserved as the JSON string `Infinity`; it is not substituted into weekly cash or production data.

Source hashes in the saved JSON identify the exact tested engine, including the earlier local household-income fix. Generated OpenWiki refresh remains deferred under the existing branch handoff; this guide is the current source documentation for the new runner.
