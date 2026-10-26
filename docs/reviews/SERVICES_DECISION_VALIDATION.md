# SERVICES-01 validation

Implementation validated before PR publication on `codex/services-decision-coherence`, based on authoritative `origin/main` d71485e7276cb2bf988eee6ff8ae9ecada3b73be. Contract: [SERVICES-01](SERVICES_DECISION_CONTRACT.md), rules v1.15. The owner subsequently authorized a PR containing SERVICES-01 and the SERVICES-02 repayment follow-up. No merge or UI change is authorized. [Compact published evidence](evidence/services/README.md) accompanies the original external raw artifacts.

## Functional result

- 38 new Services regressions passed under Windows/Python 3.11. They exercise price/markup stability, correct stabilization cost basis without changing its distress exception, both loan routes and both named sequences, retained staffing and three-observation recovery, actual matcher behavior, public installation and recovery-evidence reset.
- Two controlled `Economy.step()` cases under each named sequence fix household shopping intentions and disable unrelated entry, then use real matching, production and funded settlement. They prove recovery observations reach a matched, paid trial hire and completed market observations precede an actual infrastructure loan and evidence reset. This is composed mechanism evidence, not a calibrated household experiment.
- Final complete default backend suite: **1204 passed, 2 skipped, 8 research tests deselected, 1 xfailed**, with one third-party deprecation warning. Executed in Ubuntu 24.04/WSL, Python 3.12.3, using the project's supported Python >=3.11 range and dependencies installed into an isolated temporary environment with `backend/requirements.lock` constraints. Imports point to this worktree. No provider calls or external database services were used.
- Changed Python files passed Ruff and `git diff --check`.
- Three Sol medium review rounds: two initial defects and a later counter-overlap defect were corrected and covered by regressions; final review found no unresolved selected-scope issue. Luna's proposed coding task was cancelled before it wrote a file after the owner's model preference was clarified. Implementation and regressions were written by the parent Sol agent; Luna was used only for read-only navigation/scouting.

Reproduction of the default functional suite: from this checkout, run `python -m pytest -m 'not research' -q -o addopts= --tb=short`. On Windows, the repository's server-test timeout helper uses unavailable `signal.SIGALRM`; use Linux for the complete server gate. The Linux environment used real Windows Git through an external bridge because this Windows-created worktree's `.git` pointer contains an absolute Windows path. The bridge translates the current working directory and calls Windows Git; it does not invent a revision or replace simulator behavior. The final log is `services-implementation-linux-final-tests.log` in the external evidence folder below.

## Failures encountered and disposition

The first broad Windows run included research checks because its command overrode the default marker expression. It recorded 76 failures: 68 from the pre-existing Unix-only timeout helper; three from default Windows text encoding in an existing report writer; three loan-test preconditions missing the newly required sustained-space evidence; one historical economic prompt digest; and one exploratory minimum-wage effect-size assertion. No claim is made that the research panel passed. The final suite restores the project's `not research` selection. The effect-size failure remains an exploratory model-comparison observation, not a reason to overwrite aggregate outcomes.

Loan fixtures now explicitly supply fully staffed sustained-demand history before testing funding/accounting. The original prompt digest was reproduced unchanged on main, and both old/new prompt bundles were saved before updating the economic trajectory reference. Prompt templates and public-debt behavior were not edited; corrected Services choices change the economy described in the prompt. Paired prompt artifacts and their textual diff are retained.

An intermediate Linux run had four Git-metadata failures because Linux Git cannot resolve the Windows absolute worktree pointer. The real-Git bridge resolved these; the final full run above passed. A new focused integration fixture initially failed to mirror last-period sales into Economy's own sales map and allowed unrelated entrants to recruit its workers; those fixture assumptions were corrected while preserving real matching, production and funded purchases. No product behavior was relaxed to make the integration assertion pass.

## Performance and outcome experiment

Status: **48/48 normal-mode runs completed** with 80 ticks each (3,840 successful ticks), six matched pairs per cell. The candidate is within the integrated 5% working latency budget in all four measured cells under the specified three-seed bootstrap. This is a performance result, not acceptance of the adverse economic outcomes below or proof that decision logic alone is faster.

Method: the existing `run_sim_bench` engine harness, 80 weekly ticks, warmup 10, factory firms-per-category argument 10; 1,000 and 10,000 households; `income_first` first, then `income_late`; seeds 42, 43 and 44, each repeated twice. Baseline/candidate order alternated. The comparison fixes post-warmup ticks 40-79 with private firms active, rather than selecting a different outcome-dependent horizon in each arm. All 24 baseline/candidate pairs had identical initial-profile hashes, and each seed's repeats had the same profile. The three measured production-file hashes stayed fixed within every run, across each arm and against the final on-disk sources. Every case's 80 manifest tick rows match its raw benchmark JSON, all run rows completed 80 ticks without exceptions, and the largest absolute final clearing-cash residue was $1.53e-8 (floating-point scale). No additional repeat was needed because no interval crossed 1.05.

Candidate/baseline ratios use each run's late-window p50 or p95, then the geometric mean of the six paired ratios. The 95% intervals resample **three seed clusters**, retaining the two timing repeats within each seed. A cell is within budget only if its interval upper bound is at most 1.05. Three clusters give limited uncertainty resolution, and two repeats of one seed do not create two independent economic trajectories.

| Sequence | Households | p50 ratio (95% seed-cluster interval) | p95 ratio (95% seed-cluster interval) | Working-budget classification |
| --- | ---: | ---: | ---: | --- |
| `income_first` | 1,000 | 0.954 (0.934-0.976) | 0.968 (0.951-1.000) | Within, both percentiles |
| `income_first` | 10,000 | 1.002 (0.984-1.035) | 0.993 (0.964-1.043) | Within, both percentiles |
| `income_late` | 1,000 | 0.943 (0.937-0.954) | 0.940 (0.930-0.953) | Within, both percentiles |
| `income_late` | 10,000 | 0.991 (0.987-0.998) | 1.018 (1.002-1.038) | Within, both percentiles |

Late-window active/private/queued firm counts were **36/32/9** at 1,000 households and **301/297/0** at 10,000, identical between arms for every matched tick. The 1,000-household queue had not emptied; the 10,000-household queue had. Worker counts and other economic work nevertheless changed substantially, so these integrated ratios cannot isolate constant-time Services decision overhead. The five new `FirmAgent` slots add 40 bytes to a sampled instance (1,280 to 1,320 bytes); per-process final RSS snapshots were lower for the candidate but are noisy and do not prove a general memory saving.

Final-tick means below are across six runs per arm, but represent **three distinct seeded economic trajectories**. GDP is nominal; Services units are real quantities. The candidate reduced both, rather than merely lowering the price component of GDP.

| Sequence | Households | Nominal GDP, baseline -> candidate | Services units, baseline -> candidate | Services workers, baseline -> candidate | Employed households, baseline -> candidate | Mean happiness / health, baseline -> candidate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `income_first` | 1,000 | $59.1k -> $17.3k | 809 -> 230 | 208 -> 63 | 511 -> 290 | .502/.727 -> .396/.580 |
| `income_first` | 10,000 | $928k -> $674k | 10,006 -> 7,727 | 2,676 -> 1,980 | 5,883 -> 5,075 | .418/.637 -> .406/.633 |
| `income_late` | 1,000 | $57.8k -> $18.3k | 793 -> 249 | 214 -> 66 | 522 -> 297 | .495/.729 -> .401/.596 |
| `income_late` | 10,000 | $933k -> $671k | 10,022 -> 7,727 | 2,674 -> 1,984 | 5,947 -> 5,101 | .404/.624 -> .389/.616 |

For `income_first`, mean posted Services price fell $38.20 -> $20.98 at 1,000 and $82.83 -> $74.62 at 10,000. At the same endpoints Services cash fell $510k -> $320k and $1.99m -> $1.78m; wage arrears fell $143 -> $0 and $472k -> $384k; bank debt fell $108k -> $1.5k and $1.46m -> $1.06m. Household cash moved $176k -> $164k and $2.668m -> $2.683m; Treasury cash fell $67.8k -> $9.1k and $1.367m -> $556k. `income_late` shows the same broad direction, with its exact paired means in `analysis.json`. Lower arrears/debt accompany much lower jobs, real service provision and household wellbeing; neither is an unqualified improvement. The three-seed, 80-tick synthetic panel cannot establish calibrated welfare effects or causally apportion the decline among the selected price, staffing and loan gates.

The money helper includes bank cash reserves and named-sequence payment holds. `currency_change` is the change in this measured cash stock, not an injection-adjusted conservation test; the manifest does not separately record external injections. Near-zero clearing residue alone therefore does not prove money conservation. The benchmark excludes browser, WebSocket and warehouse cost. One original parent process stopped after 40 manifests and left raw output for an incomplete case; that orphan raw run was excluded, and the resumable script reran only the missing case onward with the specified root Python. `progress.json` and `summary.json` now both reflect 48 completed cases.

External evidence directory:
`C:/Users/ayman/Documents/ecosim-review/reports/business-map-20261025/`

Relevant artifacts: `services_performance_probe.py`, `services_performance_analysis.py`, `services-implementation-performance/summary.json`, `analysis.json`, all case manifests/raw JSON, the resume log, final functional log, paired prompt files, the three `sol_review*-result.md` files, and baseline mechanism probes.

## Documentation and remaining boundary

The subsequent [bounded component experiment](SERVICES_COMPONENT_RESULTS.md) isolates the three mechanisms in 24 matched 1,000-household `income_first` runs, plus two loan-return replays. Pricing alone reproduces nearly all of the complete package's Services quantity difference in that screen. The replay identifies an existing startup-debt/operating-cash-flow constraint on expansion. This narrows the next design question; it does not change the selected production rules or generalize the component attribution to the 10,000-household or `income_late` cells above.

CHANGELOG and active rules/contract are updated. Generated OpenWiki refresh is due: the approved workflow uses OpenWiki 0.3.0 with an OpenRouter key; neither the local command nor the key is available in this environment. Generated wiki pages were not hand-edited.

The existing planned-price cap versus effective transaction-floor exception, noisy unmet-demand signal, construction-recipient abstraction, baseline retirement, broader wage/R&D rules, and unused personality-price response remain outside this selected patch. Existing lending/underwriting gates can still refuse an otherwise supported expansion. Three strong-sales weeks is the owner's first experiment setting, not a claim that it is the correct calibrated patience for every business.
