# Small household and business experiments

Use this runner to ask a concrete question and inspect what the actors do. It needs the normal Python environment and no LLM, API key, server or browser.

From the repository root:

```bash
.venv/bin/python -m backend.tools.checks.run_agent_scenarios
```

It runs eleven scenarios: ten focused household/business cases and a town with **24 households, four initial businesses and 24 weeks**. Firms can enter or close during the town run. Results go to a new timestamped folder under `benchmarks/results/agent-scenarios/`:

- `report.md`: questions, starting conditions, observed results and checks in plain language.
- `results.json`: exact numbers, seed, source hashes and individual household/business records for each town week.

The runner uses the current default `legacy` payment rules. “PASS” means the observed mechanism met the stated check. **It does not mean that the rule is desirable.** Observations needing review are printed separately. A failed check returns exit code 1.

The current default pays wages and benefits before shopping, with approved credit already available. The complete-week payday scenario checks that new money enables purchases immediately. The [September 29 rerun on the remediation code](../evals/2026-09-28-household-income-timing/scenarios/report-2026-09-29.md) and the [September 28 results](../evals/2026-09-28-household-income-timing/scenarios/report.md) (measured on 17d5c0b plus the income-timing change) are kept side by side; the earlier pre-timing audit results were not carried over; see the [timing change](../reviews/2026-09-28-household-income-timing.md) for the correction and performance evidence.

## Start with one question

For deeper business checks with an explicit demand input, use the [controlled business scenarios](business-scenarios.md). That runner follows cash, hiring, wage changes, capacity and low demand over multiple weeks without needing households to create the orders.

```bash
.venv/bin/python -m backend.tools.checks.run_agent_scenarios --case household_budget household_payday
.venv/bin/python -m backend.tools.checks.run_agent_scenarios --case business_demand business_payroll business_exit
.venv/bin/python -m backend.tools.checks.run_agent_scenarios --case small_town --households 40 --ticks 24 --seed 7
```

Use `--output-dir PATH` to choose an output folder; existing report files in that folder are replaced. The town is limited to 12–100 households and 1–52 weeks to keep these experiments small. Use `--help` for all scenario names.

| Scenario | What changes? | What is observed? |
| --- | --- | --- |
| `household_budget` | Cash: $0, $10, $100, $1,000; one savings-only case | Isolated pre-income budgets; the full tick now waits for income |
| `household_credit` | Credit score, existing debt or bank funding | Loan received, resulting debt and budget before/after funding |
| `household_payday` | One worker begins a complete week with zero cash | Wages, credit, actual goods spending and food eaten |
| `household_benefits` | Employment status and savings | Eligibility for the base unemployment benefit |
| `household_rent` | Cash or deposits available for a $20 weekly rent | Payment, withdrawal and whether the tenancy survives |
| `household_debt` | $0, $5 or $20 cash against a $10 payment | Cash taken, debt left and credit-score treatment |
| `household_health` | Food eaten and starting health | Health loss and eligibility to search for work |
| `business_demand` | Last week's sales: zero or 40 units | Expected demand, production, hiring and layoffs |
| `business_payroll` | $0, $40 or $100 cash against $80 payroll | Business cash and wages received by workers |
| `business_exit` | Cash position and baseline protection | Closure and the worker's employment |
| `small_town` | Normal world creation at a small scale | Complete weekly interactions and individual traces |

## How to interpret the results

Most focused cases call individual production methods with explicit starting states. Their tables describe that phase, not an entire week. The payday case and small town call the real `Economy.step()` without replacing its phases. The town retains normal warmup, shocks, government policies, lending and business entry rules.

Each scenario gets an independent config and freshly seeded Python/NumPy random streams. Each isolated variant starts with the same traits. The runner restores the caller's config and random state afterward. The default seed is 1337; another seed is another observation, not proof of a general economic effect.

Household cash and deposits are separate. A planned budget is not an actual purchase, and a loan received is not earned income. The default household ledger omits some movements; `cash_change_not_itemized` in the JSON reports the difference between the actual cash change and the sum of its recorded categories. Use actual balances when checking money movements.

These tiny worlds expose rules and timing. Their unemployment or price levels should not be used to tune the default thousand-household economy. Healthcare funding, job matching, business borrowing, tax changes, ownership/dividends and `income_first`/`income_late` remain useful next focused cases.

## Existing tools

The repository already contains `run_behavior_tests.py` for broader policy comparisons, `test_household_agent.py` for household method checks, and `test_firm_behavior.py` for a 100-household business demonstration. `run_household_behavior_tests.py` follows five household archetypes in a larger shared economy with LLM narration. The new runner provides small explicit starting states and reports both decisions and observed cash movements.

## Verify the runner

```bash
.venv/bin/python -m pytest backend/tests_contracts/test_agent_scenarios.py -q
```

The checks cover repeatability despite unrelated random draws, config/RNG restoration, the complete-week payday behavior, report generation, nonzero exit status on a failed check, and rejection of oversized runs.
