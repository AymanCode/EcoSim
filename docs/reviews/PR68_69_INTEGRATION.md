# Research, payroll and bank-startup integration

Reviewed 2026-10-27 Pacific; final validation completed 2026-10-28 UTC.
Inputs: PR #68 `ff73ddf26ef1884cff26379a4db16b2dc9618bbc` and PR #69
`9ccb6ec0793ae81e4d366f0fe636f824b1d20b7c`, against main `b233cd7`.

Final preparation includes main `65c1806`, including its intervening README/screenshots and town-number-sheet commits `8dc4dff` and `c2f07a4`. Those changes are preserved. The complete backend and Python test configuration match the passing combined source byte for byte; no additional Python validation run is implied by the subsequent merge preparation.

## Integration corrections

- Preserve both configuration validators: supported research models and a strict startup-loan boolean.
- Preserve the research/payroll rules v1.18-v1.20; place the startup product after them as v1.21.
- Exercise research entry after exit with startup loans both enabled and disabled, on both named payment sequences. The enabled route keeps monotonic IDs; rollback retains numeric-ID reuse. Both require a fresh research identity and industry quality that excludes baseline providers.

No additional economic mechanism, default, threshold or agent cadence was changed during integration. The identity regression now has four cases; its original quality and identity assertions remain, with the ID expectation selected explicitly by the startup flag.

## Executed validation

- Complete configured Linux suite: **1,644 passed, two skipped, eight deselected, one expected failure**, 322.72 seconds. Command: `python -m pytest --durations=10 --maxfail=1`; Python 3.11.18, NumPy 2.4.6, `PYTHONHASHSEED=0`, numeric-library threads set to one. Imports and 212 Python/configuration hashes were verified against the integration worktree.
- Targeted identity cases: four passed. Provenance and business-CLI suites: 34 passed. Ruff on all changed Python and diff checks against the current main base passed.
- Two composed engine checks: 1,000 households, five requested firms per category, seed 4242, 60 ticks, normal mode, `project_cash`, startup loans enabled; `income_first` followed by `income_late`. Each executed 26 startup loans totaling 650,000 and completed nine research projects. Startup cash-pair residual was zero. Maximum money residual was below `4.58e-7`, clearing residual below `1.74e-10`, and the funded private wage-claim checks passed on every tick.

The initial combined suite exposed the ID-policy test conflict above. Separate setup failures involved Windows worktree paths in Linux and an overly broad Git environment workaround. A portable relative worktree pointer restored normal repository discovery; the final full suite uses no Git-directory/worktree overrides. Complete failed logs are retained alongside the passing receipt; no assertions were weakened to hide those failures.

## Evidence and limits

Local artifacts: `C:/Users/ayman/Documents/ecosim-review/reports/merge-68-69-20261027/`. This contains `run-validation.sh`, the complete suite logs, `tested-source-manifest.json`, `check-composed-paths.py` and `composed-paths.json`.

- Final suite log SHA-256: `b6a3c07fa2ada69adbd16db315a9fd92be9283f927765a1b1873a28b1d7f7a65`.
- Tested source manifest SHA-256: `2aead32ee2636ff0442666dcf43aa5d6a4ed8411d856e135c28a76fcc42615b2`.
- Composed-check results SHA-256: `a7f6552149f032d0c1ef0536e63b45a4d045d16fa8e91e0d5c8b300de8e233a9`.

The original research, payroll/budget and startup economic reports retain their frozen sources and disclosed tradeoffs. These composed checks are integration/accounting evidence, not a new matched economic panel, calibration, welfare result or formal performance acceptance. Research remains opt-in with `instant` as default; the existing payment-sequence default is unchanged.

No reviews or unresolved review threads were present on either PR. Repository Actions are disabled; no hosted run was requested. OpenWiki refresh remains due because the approved CLI is unavailable locally and Actions remain off. Full parent pstack certification remains outside this integration receipt.
