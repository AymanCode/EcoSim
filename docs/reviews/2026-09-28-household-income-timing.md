# Household income before shopping

> Port note (2026-09-29): written against `17d5c0b`; ported onto the remediation code on 2026-09-29 (CHANGELOG "Household income before shopping, legacy (ported from the 2026-09-28 session)"). The "v1.3 timing supplement" named below is recorded in `docs/ECONOMIC_AGENT_RULES.md` as version 1.5 (main had already used 1.3 and 1.4). In the ported code the steps run in `_settle_legacy_income_and_plan_shopping` inside `_phase_goods_clearing`; the cached-plan path also keeps the planner's one-unit housing cap and stops scanning sellers once the budget is spent (audit B28). The evidence figures below were measured on `17d5c0b` plus this change, not on the ported code.

## Selected change

Ayman requested that household decisions use new wages and extra money within the same week, with simulation speed the priority. The zero-cash audit case previously received wages and a loan after making an empty shopping plan. The selected correction moves the existing default shopping decision after income and credit; it does not add repeated shopping rounds.

Baseline: `17d5c0b`, with the local scenario runner/audit additions. Core source was copied and hashed before editing. Shared rules: v1.3 timing supplement to v1.2. Owner: the current integration task; no delegated writers. Scope: `Economy.step`, household income application, batch budgets, the cached-plan path and its goods resolver. No new policy lever, persisted household field or API schema.

## Weekly boundary and counterparties

For `legacy`:

1. Firm/labor planning, approved consumption loans, labor matching and production proceed first. Ordinary wages are frozen from the production-boundary contracts and debited from the employer as before.
2. Assess household progressive wage tax and unemployment transfers. Credit household take-home wages, CEO pay and transfers once. Debit CEO pay from its employer and settle the matching treasury tax/transfer totals immediately.
3. Release the existing household proceeds of firm capital spending already made earlier in the tick.
4. Make one shopping decision from current cash, deposits and actual net wage/benefit receipts. Then withdraw needed deposits and resolve the goods market.
5. Rent, care, household debt and firm sales/profit-tax settlement follow. Household purchase/food/receipt application skips income already paid. Fiscal close skips the wage tax/transfers already settled.

Extra cash received before shopping is part of the current wallet; a loan is still debt and is not counted as wage income. Actual net receipts replace gross wage assumptions in the executed default spending budget. Bracket formulas, spending traits and source-specific spending fractions are retained. Transfers are assessed at this earlier pre-shopping cash position, so means-tested top-ups can differ from the old after-rent assessment. CEO pay now uses production-boundary contracts instead of future contracts updated after sales.

Cash arriving after shopping, such as end-of-week dividends, contributes to the following week's wallet. There is one declared shopping boundary, rather than an unbounded loop after every cash movement. The `income_first` and `income_late` experiments keep their existing payment timing and funding rules.

This does not turn legacy into a fully funded settlement model. It retains the existing ability of wages/base benefits to overdraw the payer, and goods are allocated before later bills and purchase settlement. Those legacy accounting limitations remain separate review items; timing tests must not claim universal nonnegative balances.

## Bounded work and state

Normal mode calls the category/seller planner once each week. Performance mode keeps seller choices for five ticks and recalculates only monetary budgets between choice refreshes. A previously empty basket gets new choices when it gains funding. Scalar market buffers replace NumPy scalar indexing in the existing resolver; allocation order and supply accounting stay the same.

The cached plan owns three temporary fields, discarded with its normal refresh:

| Field | Meaning | Writer / reader |
| --- | --- | --- |
| `_reference_budget` | Currency budget associated with the cached unscaled quantities; nonnegative | `_plan_legacy_consumption_after_income` |
| `_purchase_scale` | Current budget / reference budget; finite, nonnegative, zero when unfunded | Budget refresh / `_clear_goods_market` |
| `_food_budget_cap` | Current food spending ceiling in currency for the cached basket | Budget refresh / `_clear_goods_market` |

The market applies the scale in its existing purchase loop, caps cached purchases by current cash and budget, and preserves the full planner's food spending ceiling. Cached quantities are reference choices; their scale is part of the internal plan. No household-by-all-firms search, unbounded history or new random draw is added. Added cache state is O(households); ordinary budget computation is O(households), and scaling is folded into the existing O(planned purchases) clearing pass.

## Acceptance and evidence

Behavior checks cover same-week wage-only, loan-only and benefit-only funding in both execution modes; an empty cached basket recovering; cash shrinking; retaining cached seller choices; single wage/tax/transfer payment; progressive/frozen-wage consistency; and existing named payment acceptance tests. The older audit/result files preserve the pre-change observation and are historical evidence.

The performance method was recorded before edits: 1,000 and 10,000 households, normal and performance modes, baseline-developed state at week 40, twelve measured ticks, five interleaved baseline/candidate pairs per cell, seed 1337. Each subprocess develops the same baseline world before switching to the candidate class. Record median/p95, paired bootstrap 95% ranges, active firms and peak process RSS. The project budget is at most 5% overhead; uncertainty crossing that threshold requires more repeats or simplification. Measurements concern the engine, not browser rendering.

The first 1,000-household pilot found roughly flat normal-mode time but about 12% extra median time in performance mode. That version was simplified before acceptance: cached baskets now scale inside the existing market pass, and scalar buffers avoid repeated NumPy boxing.

Final verification: **633 backend tests passed, 8 research checks were deselected by the normal suite, and 1 known pre-existing layoff issue was expected to fail.** All 30 public scenario checks passed. Six complete-week tests isolate wage-only, loan-only and benefit-only funding across both execution modes; the loan fixture makes capital purchases unprofitable so investment proceeds cannot masquerade as the funding under test. Additional checks cover cached price changes, food caps, scarcity, declining cash and actual paid income versus future wage contracts. Ruff and `git diff --check` passed.

The [saved evidence](../evals/2026-09-28-household-income-timing/README.md) includes all benchmark samples, source/dependency hashes, the uncertainty method, a fixed-state diagnostic and the current small-town report. All four primary workload cells were within the 5% median/p95 budget including their 95% ranges. The noisy 1,000-household performance cell was extended from five to nine pairs without dropping samples. At 10,000 households, median tick time was 954.69 → 886.39 ms in normal mode and 345.26 → 342.19 ms in performance mode; peak RSS increased by about 9.36 and 4.81 MiB respectively.

The complete-week payday example now spends 24.18 on goods and eats 2.42 food units, compared with zero before. It contains both wages/credit and existing capital proceeds; the isolated tests establish each individual funding path. Changed business survival in the larger runs still needs economic calibration. Runtime acceptance is not validation of the resulting economy.

Generated OpenWiki refresh remains deferred under the branch handoff; the source lifecycle and shared economic rules were updated directly. This correction is local and has not been pushed or merged.
