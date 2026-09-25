# Second-pass check of the 2026-09-24 frontend redesign spec

Produced 2026-09-24 by Codex CLI (`codex exec`, model `gpt-6-astra`, reasoning effort high, read-only sandbox) at Ayman's request, after the spec was revised for the first audit and approved from the one-page overview. Corrections it lists in section E and the sampling-RNG risk in section D were applied to the spec the same day; its section C build order is the input to the phase-1 implementation plan.

---

**Ready to draft a phase-1 plan, but not to execute it without resolving the contract gaps below.** GitHub `main`, cached `origin/main`, and HEAD all match `4f69389`; this review includes the substantial uncommitted working tree. No files were changed or simulations rerun.

### A. Audit follow-through

| Section H item | Status | Spec coverage and remaining gap |
|---|---|---|
| **1. Experiment identity, reservations, cleanup** | **Partly** | §6.1 adds the registry and atomic reservations. Missing: owner credential, shared-config validation, failed-SETUP rollback, and multi-worker policy. |
| **2. Initial policy and 17 levers** | **Resolved** | §§3, 6.2 specify 17 levers and validated grouped initial policies. The acknowledgement sequencing still needs correction, below. |
| **3. Lifecycle and warehouse completion** | **Partly** | §§3.1, 6.3 cover the requested states. FINISH releases reservations, yet EXTEND resumes retained economies; reacquisition, refusal, partial completion, and reopening failures remain undefined. |
| **4. Typed event inventory** | **Partly** | §6.5 names producers, stable IDs, sample filtering and a 50-event cap. Payload schemas, ordering, overflow priorities and count semantics are still unspecified. |
| **5. Compact retention and benchmark** | **Partly** | §§7–10 reject raw-frame retention and introduce budgets. The wire format remains unspecified, and the benchmark matrix conflicts with the household cap and phase boundaries. |
| **6. Metric definitions** | **Partly** | §§2.1, 6.4 distinguish posted price, household spending, cash and bank loans. Null rules, exact field names, classifications and some freshness decisions remain missing. |
| **7. AI audit and truth pairs** | **Partly** | §§4.3, 6.7 correct source-tick truth, five-point limits and rationale truncation. The numeric audit denominator and treatment of valueless citations remain undefined. |
| **8. Smoke evidence and cheaper experiments** | **Partly** | §§5.1–5.3 provide locally present runner/artifacts and neutral card copy. They remain untracked; cheaper experiments are proposed, not completed. Replacement-runner reproduction covers only selected 52-tick runs. |
| **9. Operational and accessibility requirements** | **Partly** | §§2, 4.3, 8 add all requested categories. Most are requirements without explicit phase acceptance checks. |

### B. Overview versus spec

- **Thirty metrics are promised**, twice, but §2.1 specifies nine grouped entries rather than a complete thirty-field inventory. This affects scope and the 60 KB budget. [Overview:127](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/superpowers/specs/2026-09-24-mockups/00-overview.html:127)
- **“10,000 households total, split” sounds like the default**, whereas the approved default is 1,000 per town and 10,000 is a ceiling. Use “up to.” [Overview:74](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/superpowers/specs/2026-09-24-mockups/00-overview.html:74)
- **“Full reasoning stored” overpromises** against §6.7’s full-public-rationale-or-excerpt choice. §10 phase 3 also promises full rationale, so the spec itself needs one decision. [Overview:228](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/superpowers/specs/2026-09-24-mockups/00-overview.html:228)
- **“Held cards stay in Build my own”** promises retained templates; the spec guarantees custom levers but does not explicitly retain those cards. [Overview:217](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/superpowers/specs/2026-09-24-mockups/00-overview.html:217)

The screen structure, launch-card selection and phase sequence otherwise agree.

### C. Readiness for a phase-1 implementation plan

Build in this order. **Open** identifies acceptance that is not yet unambiguous enough to test.

1. **Experiment registry and persistence identity (§6.1).** Define registration before implementing dependent commands. **Open:** ownership, equal household allocations, shared seed/config enforcement, atomic rollback and the single-worker assumption. Resolve whether queryable columns ship here or in phase 4; §§6.1 and 10 disagree.
2. **Initial policies (§6.2), dependent on registration.** Validate the whole vector before mutation, including grouped instruments. **Open:** defaults for omitted levers and initial-versus-runtime limits. Acknowledge through `SETUP_COMPLETE`; the existing `SESSION` precedes SETUP. [server.py:3217](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:3217), [server.py:3246](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:3246)
3. **Horizon, FINISH and EXTEND (§6.3), dependent on identity.** Include EXTEND although phase 1’s list omits its name. **Open:** idempotency, incomplete finishes, reservation reacquisition and reopening the same run. Current close clears its run ID and watermark. [server.py:1830](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:1830)
4. **Sample and TRACK (§6.6), before event filtering.** **Open:** whether following an outsider evicts another member, maximum pins, all-pinned reshuffles, small populations and command replies.
5. **Event producers and stream (§6.5), dependent on tracked membership.** Capture openings, closures, shocks and applied policy actions before projection. **Open:** payloads, IDs, ordering and overflow rules.
6. **Metric projection, food spending and closure archive (§6.4), using those producers.** **Open:** complete field inventory, nulls, freshness, spending denominator, firm-status classification and cumulative-default definition. Fix wire-history retention explicitly.
7. **Recording tool and fresh fixtures (§6.8), after contracts stabilize.** Cover compare/play lifecycle, errors and policy edits; use scripted AI fixtures. Record TRACK and EXTEND as well as SETUP/CONFIG. Defer actual §6.7 decision-history/truth-pair implementation to phase 3.
8. **Full-path benchmark (§§8–10), using the final projection.** **Open:** measurement hardware, percentiles and browser harness. Four towns × 5,000 households violates the cap; four-town heap and StoryChart interaction gates require phase-2 components, whereas phase 1 specifies two-town acceptance.

### D. Remaining risks, ranked

1. **Matched comparisons could change when someone browses households.** Current sampling consumes the same session RNG stream used by simulation. Cheapest mitigation: give sampling a separate deterministic RNG and assert identical economics with versus without TRACK activity. [server.py:1850](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:1850), [server.py:1988](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:1988)
2. **Restart replay could reproduce requests rather than applied policies.** CONFIG has no success acknowledgement, and rejected values can still enter policy-change records. Cheapest mitigation: emit an authoritative action receipt containing accepted values, action ID and effective tick. [server.py:2790](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:2790), [server.py:2831](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:2831)
3. **The baseline and launch-card evidence may not transfer to the new live path.** Cheapest mitigation: run the existing matched-seed checks through the completed session path before changing calibration; preserve the exact source revision and settings.
4. **The AI score can imply verification it did not perform.** Valueless citations and dictionary-valued references can count as matches. Cheapest mitigation: count only explicitly parsed scalar comparisons and label their reference source. [llm_government.py:822](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/tools/llm/llm_government.py:822)

### E. Factual corrections against source and evidence

- **Benefits distress:** §5’s “Distress up in both” is wrong. The newcomer CSVs show lower distress at all ten checkpoints; the evidence table reports −0.089 to −0.002. [Evidence README:128](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/evals/2026-09-24-newcomer-smoke/README.md:128)
- **Closures:** §§5.1–5.2 call 6, 8 and 60 firm-count declines “exits.” The runner counts **ticks with net declines**, not closures. The 5k CSV has 60 declining ticks totaling 97 net firm reductions. [run_newcomer_smoke.py:284](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/tools/benchmarks/run_newcomer_smoke.py:284)
- **Food price:** §5.1’s “does not move in either seed” is false literally. Subsidy-arm prices differ from baseline; the defensible claim is no consistent separation. The voucher changes payment allocation, not posted price directly. [Evidence README:132](/Users/aymanislam/EcoSim_v_2/EcoSim/docs/evals/2026-09-24-newcomer-smoke/README.md:132), [economy.py:1198](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/economy.py:1198)
- **Capacity:** §3.1 says capacity rejects SETUP. Rejection occurs when opening the socket session, before receiving commands. [server.py:3207](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:3207)
- **Timing:** §6.4 says `tickComputeMs` stops at engine time. It includes pre-step work, statistics and tracked-state construction. Smoke timing likewise includes per-tick snapshots, not engine execution alone. [server.py:2113](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:2113), [server.py:2525](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:2525), [run_newcomer_smoke.py:222](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/tools/benchmarks/run_newcomer_smoke.py:222)
- **Provider failure:** §4.3 cites initialization failure as general outage behavior. Later task failures instead produce an error/no-change result; disabling is not universal. [server.py:1456](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:1456), [server.py:1526](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:1526)
- **Summary coverage:** “Events never reach [the browser]” overlooks policy-change records and LLM decisions already sent. “Twelve firms” conflates two top-12 leaderboards with seven tracked firms. [server.py:2626](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:2626), [server.py:363](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/server.py:363), [run_large_simulation.py:840](/Users/aymanislam/EcoSim_v_2/EcoSim/backend/tools/runners/run_large_simulation.py:840)