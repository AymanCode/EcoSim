# PR title

Make government surplus distribution an explicit policy choice

# PR body

Government previously sent eligible treasury surplus through Misc automatically. Add a standing `surplus_distribution` government policy, defaulting to `off`, so a validated setup, runtime or LLM decision can turn the existing distribution on or off. An omitted decision retains the selected state. The existing 12% calculation, threshold, reserved-cash, debt and stabilization gates, tax skim, beneficiaries and timing are unchanged. The legacy `bonds` telemetry key remains for compatibility; the transfer creates no bond asset.

The choice applies to `income_first`, `income_late`, and the `legacy` payment sequence. It is included in the policy schema, LLM observations and prompt, live application, snapshots, audit metrics and warehouse policy actions. Under the existing LLM fiscal-stress guard, enabling it counts as an increase in spending. The town has no control for this new lever yet; setup/runtime API and LLM decision surfaces can select it. No UI, benefit eligibility, payout, finance, or other programme changes are included.

## Validation

- Final merge validation: **1,659 passed, eight research tests deselected, one known expected failure, zero skipped** in the complete backend suite (`python -m pytest -ra --durations=10`, exit 0). This used Ubuntu-24.04 / Python 3.11.18, both complete dependency locks, and a native Linux checkout of code commit `0dd951a6cc6b681fb689881a0b792ef9b2b22f13` with normal Git discovery and `PYTHONHASHSEED=0`.
- Ruff, the installable wheel build, four AWS-runner unit tests, committed worker-script Bash syntax, three forecasting-config tests, and `git diff --check` passed. Earlier affected-suite validation passed 125 tests, including actual WebSocket SETUP/CONFIG on all three payment sequences, missing/invalid choices and SQLite reconstruction.
- The debt/spending regression fixtures explicitly select on. The frozen debt prompt's 20-tick economic metrics reproduce current main exactly with on; the reviewed prompt difference is only the two new policy schema/effect lines. The digest is updated to that reviewed prompt.
- Earlier Windows-worktree attempts are retained as failures, not full passes. Direct WSL Git could not resolve the Windows worktree path; global Git path overrides fixed that lookup but invalidated the no-repository provenance test. The final native Linux checkout needs neither workaround and passes the complete suite. No assertions were weakened for these environment problems.
- Reproduce in a native Linux checkout with `python -m pip install -r backend/requirements.lock -r backend/requirements-test.lock -e ".[test,ml]"`, then `PYTHONHASHSEED=0 python -m pytest -ra --durations=10`. Complete logs, environment metadata and the exact runner are retained in `C:/Users/ayman/Documents/ecosim-review/government-surplus-choice-20261028/merge-validation`.
- GitHub's repository Actions setting is `enabled: false`, and no hosted checks ran for this PR. The merge uses the local Ubuntu backend evidence above; frontend, complete forecasting and Docker CI jobs are not claimed. No new economic panel or performance benchmark was run. The approved Actions-based OpenWiki refresh remains due while Actions is disabled.

## Historical exploratory context

Two earlier 1,000-household, 140-week `income_first` seed-4242 no-sweep cases (neutral/high) reused saved startup-loan-enabled sweep-on controls. They predate newer main research changes and are not validation of this patch's new-main trajectories. In weeks 104-140 benefits paid per eligible moved closer to the selected rate and employment fell in both comparisons; GDP and happiness decreased under neutral and increased under high, with mixed wellbeing indicators. These single-seed observations do not establish calibration, causation, or overall welfare improvement. See the contract review note and referenced artifact protocol/results for scope and limitations.
