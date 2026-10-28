# PR title

Make government surplus distribution an explicit policy choice

# PR body

Government previously sent eligible treasury surplus through Misc automatically. Add a standing `surplus_distribution` government policy, defaulting to `off`, so a validated setup, runtime or LLM decision can turn the existing distribution on or off. An omitted decision retains the selected state. The existing 12% calculation, threshold, reserved-cash, debt and stabilization gates, tax skim, beneficiaries and timing are unchanged. The legacy `bonds` telemetry key remains for compatibility; the transfer creates no bond asset.

The choice applies to `income_first`, `income_late`, and the `legacy` payment sequence. It is included in the policy schema, LLM observations and prompt, live application, snapshots, audit metrics and warehouse policy actions. Under the existing LLM fiscal-stress guard, enabling it counts as an increase in spending. The town has no control for this new lever yet; setup/runtime API and LLM decision surfaces can select it. No UI, benefit eligibility, payout, finance, or other programme changes are included.

## Validation

- Ubuntu-24.04 / Python 3.11.18: **125 passed** across the affected government, debt, structured LLM, server and SQLite suites, including actual WebSocket SETUP/CONFIG on all three payment sequences, missing/invalid choices and warehouse reconstruction. Ruff and `git diff --check` passed.
- The debt/spending regression fixtures explicitly select on. The frozen debt prompt's 20-tick economic metrics reproduce current main exactly with on; the reviewed prompt difference is only the two new policy schema/effect lines. The digest is updated to that reviewed prompt.
- The initial full backend run recorded 1,651 passed, six failed, two skipped and one expected failure. Four failures were WSL Git's inability to resolve this Windows worktree path; two were the automatic-payout fixtures above. All six are included in the passing 125-test follow-up, using process-local `GIT_DIR` and `GIT_WORK_TREE`. Hosted full CI is the remaining merge gate; the first local run is not reported as a full pass.
- Reproduce the main affected suites with `python -m pytest backend/tests_contracts/test_government_surplus_choice.py backend/tests_contracts/test_public_debt.py backend/tests_contracts/test_contracts_llm.py backend/tests_server/test_initial_policy_and_receipts.py backend/tests_server/test_live_llm_government.py backend/data/tests/test_warehouse_integration.py -ra`; the follow-up also selects the reviewed debt prompt, bond-spending integration and four Git-provenance regressions.
- No new simulation panel or performance benchmark was run. OpenWiki refresh follows merge through the approved Actions workflow.

## Historical exploratory context

Two earlier 1,000-household, 140-week `income_first` seed-4242 no-sweep cases (neutral/high) reused saved startup-loan-enabled sweep-on controls. They predate newer main research changes and are not validation of this patch's new-main trajectories. In weeks 104-140 benefits paid per eligible moved closer to the selected rate and employment fell in both comparisons; GDP and happiness decreased under neutral and increased under high, with mixed wellbeing indicators. These single-seed observations do not establish calibration, causation, or overall welfare improvement. See the contract review note and referenced artifact protocol/results for scope and limitations.
