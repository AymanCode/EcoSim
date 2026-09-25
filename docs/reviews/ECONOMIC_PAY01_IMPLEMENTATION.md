# PAY-01: wage contracts and earned pay

**2026-09-21 — integrated and functionally verified.** This is the first narrow implementation in the [staged implementation plan](../ECONOMIC_IMPLEMENTATION_PLAN.md). It implements the wage-consistency part of [PS3.1 / OA01](../proposals/agent_round_02/ORCHESTRATOR_PAYMENT_AUDIT.md); the full income-first payment system is not enabled.

## Changed behavior

A worker's household and employer now retain the same ordinary wage contract after the existing wage writers run. The explicit incumbent offer floor, scheduled continuing-worker raise, late wage cut, healthcare base reset and warmup floor no longer leave different contract values on the two sides. A stale former employer cannot grant a raise or consume the worker's raise timestamp. Roster fallback and layoffs reconcile their wage records.

`Economy.step` also freezes ordinary gross earnings at the production boundary. The tax snapshot and household receipt use that same tick-local record. A late cut changes the future contract without reducing wages already earned: earning 100 and then receiving a future contract of 90 still produces current ordinary income/tax assessment on 100. A later legitimate wage decision can change the next contract again. Existing tax formulas, cash-payment phases, financing conventions, CEO/bonus mechanics, actor identities and execution cadence stay as before.

The source change is confined to [economy.py](../../backend/economy.py). The new [regression tests](../../backend/tests_contracts/test_wage_contract_consistency.py) exercise the real step boundary and direct-call compatibility. There is one temporary O(H) earned-wage map, plus bounded worker lookups in existing passes; no persistent wage history, new dependency, all-pairs search or per-actor model call.

## Authorship and independent judgment

Ayman first selected AGY Gemini 3.8 Flash High. The CLI reached that exact model, but its trial needed repeated intervention for workspace access, repeated reads, an invalid patch and incorrect test assumptions. Codex rejected the first draft and specified concrete corrections. After Ayman authorized a switch, **Sol (`gpt-5.6-sol`) on medium** reviewed and completed the resulting candidate, documented the new inputs and wrote the final regression suite. Codex independently reviewed the diff, ran the verification below and copied only the verified engine/test files into the original checkout after checking original-file hashes.

The [trial record](evidence/PAY01/gemini-trial-summary.json) preserves model and execution status without publishing private model reasoning. No CLI success label was treated as proof that edits or tests succeeded. All seven temporary AGY access rules were removed, preserving existing permissions. No commit or push was made.

## Executed verification

| Check | Before | After |
|---|---:|---:|
| Default backend test suite | 346 passed | 358 passed |
| Existing excluded / expected-failure cases | 8 deselected / 1 expected failure | Same |
| New wage regression cases | Absent | 12 passed |
| Normal-mode contract mismatches in the independent probe | 2,478 | 0 |
| Performance-mode contract mismatches in the independent probe | 2,390 | 0 |
| Normal-mode production-wage / ordinary-receipt mismatches | 34 | 0 |
| Performance-mode production-wage / ordinary-receipt mismatches | 26 | 0 |

The [independent probe](evidence/PAY01/probe_tick_wages.py) runs 60 households for 55 ticks in each mode, crossing the continuing-wage update boundary. Counts are household-tick mismatches in this fixture, not unique people or population estimates. The pre-change single-worker probe also demonstrated a raise from 100 to 102.74134488827902 being erased to 100 by roster synchronization. The new tests cover normal/performance modes, real fast/legacy matching, current earnings versus late contracts, switches, stale rosters, layoffs, fallback wages, warmup floors, healthcare reset paths and direct helper callers.

Codex independently ran the full suite in the candidate, then ran all 12 new cases and the public `Economy.step` probe again in the original checkout after copying the verified files. The final original-checkout probe also reported zero mismatches in both modes. These are software/accounting checks, not evidence of a preferred economic-policy outcome.

## Early runtime evidence and remaining gate

Eight engine runs used 1,000 households, seed 42, 100 ticks, 10 warmup ticks and 10 initial firms per category. Each mode used baseline→candidate, then candidate→baseline; no coding worker or heavy test run competed with these timing windows. [Raw runs, configurations and summaries](evidence/PAY01/timing_summary.json) are retained.

| Mode | Median tick-time change across the two pairs | p95 change across the two pairs |
|---|---:|---:|
| Normal | −0.40% to +1.09% | −1.08% to +1.22% |
| Performance | −5.66% to −5.05% | −3.64% to −2.33% |

This is an early check, **not acceptance of the full 5% cumulative budget**. Two pairs at one population/seed are insufficient for that claim. The correction also changes the economic workload: final active firms were 36 versus 30 in normal mode, and 35 versus 30 in performance mode. The normal baseline remained in private-firm ramp while the candidate reached full-private-market ticks. Faster observations therefore do not isolate implementation cost. Peak process RSS across these runs was about 73.3–75.3 MiB; that is a process high-water reading, not a long-horizon memory bound. Representative repeated 10,000-household runs, matched workload analysis and the integrated payment-package measurement remain PAY-05 work.

## Source and reproduction

The commit baseline was `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46`, equal to freshly fetched `origin/main`, plus the actual local W01–W05 work. The [baseline manifest](evidence/PAY01/baseline_manifest.json) identifies 417 supplied files. [Baseline source](evidence/PAY01/baseline_source.zip) and [candidate source](evidence/PAY01/candidate_source.zip) preserve the exact benchmark inputs; the candidate adds the wage tests. [Implementation metadata](evidence/PAY01/implementation.json) records final source hashes and status.

Extract each source archive into its own directory. Use the existing [benchmark wrapper](benchmark_concrete_package.py) with that directory as `--source-root`, matching `--households 1000 --seeds 42 --ticks 100 --repeats 1` and adding `--performance-mode` for that mode. Interleave the two variants as described above. The retained runner is historical execution code with its original work-directory assumptions; the source archives and explicit wrapper arguments are the portable reproduction route.

For functional checks in the project environment:

```bash
.venv/bin/python -m pytest backend/tests_contracts/test_wage_contract_consistency.py -q
.venv/bin/python -m pytest --durations=5
.venv/bin/python docs/reviews/evidence/PAY01/probe_tick_wages.py /absolute/path/to/EcoSim
```

The broader PS3.1 funding, treasury restrictions, two-pass goods settlement, rent/care/debt priorities, wage arrears and exit-recovery clock remain unimplemented. Generated OpenWiki refresh is tracked in the implementation metadata; historical proposal/audit records remain unchanged.
