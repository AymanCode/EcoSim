# GOVERNMENT-SURPLUS-01: selected proposal and field contract

Status: selected by owner direction; contract v1.0, rules v1.22. Author: implementation sub-agent, Codex Terra. Baseline `ec35ee6321f9c0f8910a1c3234fc43c7460d4a72`, clean source; government owner, M06, R01/R02/R03/R06, K06. This is one prioritized change, not an approval of new benefits, financing or UI.

## Proposal and resolution

Current `GovernmentAgent.make_investments` automatically spends 12% of free treasury cash above $50,000 when the surplus strictly exceeds $10,000, after debt settlement, unless stabilization is disabled or public debt remains. It routes to `Economy._collect_misc_revenue`, which returns a deterministic 0-20% tax skim to Treasury and pools the remainder for equal later distribution to existing Misc beneficiaries. No bond asset is acquired. The policy question is whether the government selects that cash distribution. Owner-selected resolution: retain the existing mechanism when on, default off; no autonomous heuristic turns it on. An unconditional sweep and a launch-only experiment flag are rejected as substitutes for a standing policy. This is a simulator mechanism, not calibrated evidence or a real sovereign-bond model.

Example: with $200,000 free cash, no debt and stabilization enabled, on spends $18,000 before the existing Misc tax; off spends $0. Restrictions, outstanding debt, the strict threshold and stabilization gate still apply. Tax and later beneficiary credits remain existing settlement owners. With off, Treasury retains cash for existing obligations and choices; households may receive less from Misc and firms may face different demand later. GDP, unemployment, wellbeing and benefits can move in competing directions; no outcome is guaranteed.

## Bounded field and writer map

| Field | Owner / values / initial | Writers and phase | Readers and persistence |
|---|---|---|---|
| `surplus_distribution` | GovernmentAgent; string `off`/`on`; `off` | Validated `set_lever` at setup/runtime or accepted LLM decision boundary; absent change retains state | phase 11.5 `make_investments`; canonical schema, prompt, current-policy observation, government serialization, audit, session snapshots and policy receipts. The warehouse records the initial value as a tick-zero policy action and later changes as actions. Persistent agent state for the running session; no separate launch flag. |
| treasury cash, reserved cash, public debt | Existing GovernmentAgent; currency stocks | Existing fiscal settlement/debt and distribution paths only | Existing free-cash, debt and stabilizer guards unchanged. |
| `bonds`, `gov_bond_purchases_this_tick`, Misc pool | Existing compatibility names / currency per tick | Existing phase 11.5 and Misc collector; no new asset | Existing telemetry, tax skim, equal-beneficiary distribution and timing unchanged. |

LLM on is a spending increase under the existing fiscal-stress guard; off remains selectable. Invalid values reject without changing state. Setup and runtime canonical policy APIs use their existing validation; no new UI is supplied. All three payment sequences share the same gate and existing timing; named paths protect their existing reservations. No RNG stream or cadence is added. A branch check per tick adds O(1) work and state; performance impact is unmeasured, and no speed claim is made. Historical control artifacts are not new-main validation.

## Acceptance and exclusions

Check default off without cash mutation; on exact amount and reservation, threshold, stabilization and debt guards; existing Misc tax/pool/counterparty path; real structured decision and runtime toggles including missing/invalid changes; schema, observation and snapshot retention. Merge validation adds Linux WebSocket transport checks for all three payment sequences, real SQLite initial-policy persistence, and the backend suite. The public-debt stress fixture explicitly selects on so it still tests the existing debt-before-distribution guard. Benefits, payout rules, labour, startup lending, borrowing, other programmes and UI are excluded. No new simulation panel or performance benchmark is claimed. Refresh OpenWiki through its approved Actions workflow after merge.

## Review note: historical exploratory evidence and limits

The retained NO-SWEEP-01 artifacts at `C:/Users/ayman/.t3/userdata/artifacts/ecosim-no-cash-sweep-20261027-222303` contain exactly two new 1,000-household, 140-week `income_first` seed-4242 no-sweep cases (neutral/high) compared with saved startup-loan-enabled sweep-on controls from `C:/Users/ayman/.t3/userdata/artifacts/ecosim-bank-startup-loans-20261028-034219/candidate-v5`. See `protocol.md`, `result.md`, `verification.json`, `source-hashes.json`, and `summary.json` there. This source predates newer main research work: it is historical exploratory evidence, not a new-main trajectory validation. In weeks 104-140 benefit paid per eligible approached its chosen rate and employment was lower in both comparisons; GDP and happiness fell in neutral and rose in high, with other wellbeing measures mixed. One seed and incomplete treasury-ledger coverage do not establish causation, calibration, welfare superiority, or a general policy recommendation. Benefits Compare remains parked.

Validation commands and results are in the PR description. Initial preparation could not exercise the Windows WebSocket helper because `signal.SIGALRM` is unavailable, and the system Ubuntu Python lacked pytest. Merge validation uses the existing Ubuntu-24.04 Python 3.11 environment at `/tmp/ecosim-quality-validation/bin/python`, including actual WebSocket SETUP/CONFIG receipts, omission retention, invalid-value rejection and explicit toggles on `income_first`, `income_late` and `legacy`. The original preparation failures are preserved below; they are superseded by the Linux transport checks.

The initial full backend log and passing 125-test follow-up, current-main prompt reproduction, candidate-on prompt, exact two-line prompt diff and equal economic-metric hashes are retained in `C:/Users/ayman/Documents/ecosim-review/government-surplus-choice-20261028`. Current main's prompt digest `85129748f287dabd3fcd8f8eab9ee92911210f1ed9076bbbbfd7d8a79097e901` is reproduced before the update. The explicit-on candidate's reviewed digest is `e7254862ef9a651e942e3b07e96279580ab544b5f653282d2a4e32f9aaa1fd4d`. After excluding only the new `gov_surplus_distribution` field, both 20-tick metric documents have SHA-256 `85e971c6862c42b8c7187e81348b1a541163c7ae879cb5eb0b101b2115486b18`; this is bounded metric equality, not hidden-state equivalence or new-default outcome acceptance.

<details><summary>Preserved failed test and fallback output</summary>

```text
F                                                                        [100%]
================================== FAILURES ===================================
_______________ test_surplus_choice_setup_runtime_and_receipts ________________
backend\tests_server\test_initial_policy_and_receipts.py:279: in test_surplus_choice_setup_runtime_and_receipts
    session = _session(ws)
              ^^^^^^^^^^^^
backend\tests_server\test_initial_policy_and_receipts.py:25: in _session
    return until(ws, lambda m: m.get("type") == "SESSION")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests_server\_ws.py:17: in until
    previous_handler = signal.signal(signal.SIGALRM, _timeout)
                                     ^^^^^^^^^^^^^^
E   AttributeError: module 'signal' has no attribute 'SIGALRM'
=========================== short test summary info ===========================
FAILED backend/tests_server/test_initial_policy_and_receipts.py::test_surplus_choice_setup_runtime_and_receipts
```

```text
/mnt/c/Users/ayman/.t3/worktrees/EcoSim/experiment-bank-startup-loans
/usr/bin/python3: No module named pytest
bash: line 1: /tmp/ecosim-services-validation/bin/python: No such file or directory
```
</details>
