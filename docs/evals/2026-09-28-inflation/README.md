# Inflation and annual pay: implementation evidence

> Port note (2026-09-29): this folder is the 2026-09-28 session's evidence, copied unchanged apart from this note. Every number here was measured on `17d5c0b` plus that session's changes, not on the remediation code. The port puts the model behind `CONFIG.inflation.enabled` (default on); its measured effect on this code is in [docs/evals/2026-09-29-inflation-port/](../2026-09-29-inflation-port/README.md).

September 28, 2026. Local working tree over `17d5c0b`, including the earlier household income timing change. Ayman selected prices emerging from firm decisions, with controlled shocks for behavior tests.

## Findings

- The engine now measures a fixed, synthetic consumer basket from matched sellers' posted prices. It discloses missing coverage and waits a full 52-week interval before reporting annual inflation. Measurement does not move money.
- Private Food/Services firms in the default legacy sequence review pay every 52 weeks. A positive inflation adjustment requires revenue and cash reserves; demand alone does not trigger a raise. Persistent distress cuts require eight weeks of losses and inadequate reserves, with a 52-week cooldown. Existing benefit/policy wage floors remain binding.
- With an imposed 5% annual price path, an affordable $40 contract becomes $42 at the first review and $44.10 at the second. With insufficient reserves it stays $40, worth $36.28 in initial purchasing power after two years. Flat prices and deflation do not themselves cut nominal pay.
- In a real one-firm, 12-household sector experiment, doubling demand or halving labor productivity during weeks 13–20 produces higher prices than the unchanged control. At week 20: control $4.91, demand shock $8.13, supply shock $7.47. All three finish at $4.71 in this seed. These are Food-sector responses, not a calibrated aggregate inflation path.
- The existing household shopping planner halves purchased quantity when price doubles and the budget is fixed. New full-step tests also verify that a review changes the next payday once, while current earned payroll remains unchanged in both execution modes.

Read the [scenario report](report.md), [usage guide](../../testing/inflation-scenarios.md), [selected model](../../reviews/2026-09-28-inflation-model.md) and [performance evidence](performance.md).

## Final verification

| Check | Result |
|---|---|
| Public inflation runner, seed 1337 | 8/8 checks; three market cases complete 105 weeks |
| Inflation contract tests, including seed 7 CLI | 27 passed |
| Full selected backend suite | 685 passed, 8 deselected, 2 expected failures |
| Frontend consumer regression suite | 583 passed across 57 files |
| Repository Ruff and `git diff --check` | Passed |
| 1k/10k households, normal/performance | All median and p95 upper bootstrap intervals below the 5% runtime budget |

The two expected backend failures are existing behavior gaps: repeated identical zero-sales observations can stall the Services weak-demand counter, and the three-worker survival floor can block layoffs at a distressed private firm. The eight deselected tests are outside the default selected suite. They are not counted as passes.

Commands used from the repository root:

```bash
.venv/bin/python -m backend.tools.checks.run_inflation_scenarios \
  --output-dir docs/evals/2026-09-28-inflation
.venv/bin/python -m pytest backend/tests_contracts/test_inflation.py -ra
.venv/bin/python -m pytest -ra
.venv/bin/python -m ruff check .
git diff --check
npm --prefix frontend-react test
```

The exact scenario source hashes are in [results.json](results.json); benchmark source hashes, configuration and all timing samples are in [benchmark.json](benchmark.json). Test output is saved in [backend-tests.log](backend-tests.log) and [frontend-tests.log](frontend-tests.log). Performance reproduction includes the pre-inflation baseline patch and keeps earlier-revision timing evidence separately.

## Remaining scope

This implementation provides a price signal and its first explicit pay-policy consumer. The stored inflation target still has no controller. Public/specialized pay and named payment experiments retain their wage institutions. Benefits, loan contracts and tax rules are not indexed. Live frames expose the new index and real wage, but no dashboard chart or warehouse migration was added. Basket weights and review limits are chosen assumptions. Baseline calibration and long-run economy-wide behavior remain open; the small scenario results do not resolve them. An OpenWiki refresh remains due when the feature branch reaches main.
