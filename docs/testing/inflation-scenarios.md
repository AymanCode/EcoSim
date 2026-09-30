# Inflation and purchasing power

Run the small, repeatable suite from the repository root:

```bash
.venv/bin/python -m backend.tools.checks.run_inflation_scenarios
```

The runner writes `report.md` and `results.json` under a timestamped `benchmarks/results/inflation-scenarios/` directory. `--seed 7` changes the seed; `--output-dir PATH` selects a directory and overwrites its report and results. It needs no server or LLM.

The whole model is behind one switch, `CONFIG.inflation.enabled` (default `True`, `backend/config.py`). With it `False` the engine keeps the older weekly wage rules and the index is not observed; the runner's market experiments then show an index of 100.

## What is implemented

The engine now measures a synthetic consumer price index at the start of each week after warmup. The first observation is 100. Fixed category weights are Food 35%, Housing 35%, Services 20% and Healthcare 10%; these are configurable modeling assumptions. The index follows price changes at the same sellers, so entering or departing firms do not cause a price jump just because their prices differ. Missing comparisons carry the prior category level and reduce reported coverage.

This is a **posted-price index**, without transaction weighting, quality adjustment, lease cohorts or household-specific consumption baskets. It is a useful consistent price signal, not an empirically calibrated CPI or a full cost-of-living index. Annual inflation is unavailable until 52 weeks separate the relevant observations. `metrics.inflation` in live frames contains the definition, index, weekly/annual rates, category indexes, weights and matched basket coverage. `avgRealWage` divides the displayed average nominal wage by the index relative to 100. The existing dashboard price histories and older server decision statistic retain their definitions; this slice adds no dashboard chart or warehouse schema.

Private Food/Services firms in the default legacy sequence now review pay every 52 weeks from their first post-warmup review anchor. They can match positive observed inflation, up to 10% per review, when previous revenue after debt service and an eight-week payroll cash reserve support it. They can freeze or grant part of a raise. Eight consecutive loss-making weeks with inadequate reserves permit a 2% cut, at most once per 52 weeks. Deflation alone does not cut nominal pay. Existing policy/benefit wage floors still apply. Future contract changes occur after the current week's earned payroll has been settled. Public/specialized firms and named payment scenarios retain their wage rules.

Higher demand triggers production, hiring and investment decisions, with no automatic recruitment raise in this first annual policy. Vacancies can remain unfilled. Inflation does not debit cash or change outstanding nominal loan principal: purchasing power changes because goods cost more. The stored inflation target remains inactive; a monetary-policy institution and its transmission are a separate design.

## What the tests distinguish

| Case | Expected meaning |
|---|---|
| Flat controlled prices | Index stays flat; annual reviews do not invent a raise. |
| Prices rise 5% annually, affordable firm | $40 becomes $42 at week 52 and $44.10 at week 104; purchasing power is restored at review dates. |
| Same prices, insufficient reserves | Nominal wages can stay $40 and real pay declines. |
| Deflation | Nominal wages stay stable absent distress; purchasing power rises. |
| Higher food price, fixed household funds | The real shopping planner purchases fewer units. |
| Temporary demand surge | More requested units reach the real market; output, prices and hiring respond with delays. |
| Temporary supply loss | Lower `units_per_worker` reduces the actual production frontier; the input returns after the shock. |

Controlled price paths isolate measurement and the pay decision. They do not establish that a full economy naturally reaches 5% inflation. Demand and supply cases run 105 real engine weeks for a Food firm and 12 households, with a funded external customer and fixed household health. They establish sector response, not aggregate calibration. All actual market sales remain bounded by customer funds and supply, and recorded payroll is checked against gross worker receipts.

Supply and demand are also directly configurable in the business runner:

```bash
.venv/bin/python -m backend.tools.checks.run_business_scenarios \
  --ticks 105 --cash 50000 --initial-demand 90 --demand 90 \
  --supply-shock-start 13 --supply-shock-weeks 8 --supply-multiplier 0.5
```

The business runner now accepts up to 156 weeks. Demand values are requested units per week; the final value repeats. A supply multiplier changes labor productivity only during its declared window; existing inventory and all other constraints still matter.

Implementation assumptions: [selected model](../reviews/2026-09-28-inflation-model.md). Saved results: [September 28 report](../evals/2026-09-28-inflation/report.md).
