# EcoSim LLM Economic Governance Eval Protocol

Date: 2026-06-16

Status: protocol draft. This document separates the eval
protocol from the implementation-readiness audit. It describes what EcoSim is
trying to measure, what can be claimed from a v0 run, and what must exist before
stronger v1 benchmark claims are defensible.

## 1. Overview

EcoSim is an LLM economic-governance evaluation environment. It tests whether a
model, acting through a bounded government-policy interface, can improve
simulated economic outcomes relative to declared baselines under noisy, lagged,
partial observation.

EcoSim is not a real-world policy oracle. Scores measure performance under
EcoSim dynamics. They may be useful for studying long-horizon policy reasoning,
tradeoff management, robustness, and evidence-grounded decision-making, but they
do not validate real-world economic policy.

The central eval question is:

> Can a governance-agent configuration improve declared EcoSim economic outcomes
> relative to specified baselines across seeded simulation worlds?

The eval is deliberately not an answer-key benchmark. Economic policy does not
usually have one exact correct lever. A model should be rewarded for producing
better simulated outcomes under the scenario welfare function, not for matching a
human-written policy script.

## 2. Current Status And Allowed Claims

Current status:

EcoSim is ready for scoped v0 experiments on scenarios whose stressors can be
created from initial conditions and whose scored metrics are emitted by the
headless runner. It is not yet ready for published claims about general
economic-governance ability, typed shock recovery, or calibrated optimal-policy
scores.

Allowed v0 claim:

> A v0 result may claim that a given governance-agent configuration improved
> declared EcoSim economic outcomes relative to specified baselines on specified
> scenarios, under a stated observation model, action space, seed pack, and
> uncertainty interval.

Not allowed v0 claim:

> A v0 result may not claim that the model can govern real economies, that it is
> generally better at policy, that it is robust to arbitrary crises, or that its
> score is calibrated against an optimal policy frontier.

## 3. Unit Under Test

EcoSim evaluates a governance-agent configuration, not a foundation model in
isolation.

A configuration includes:

- model id
- provider
- prompt template
- observation interface
- parsing and retry logic
- policy schema
- temperature, top-p, max tokens, and provider seed where available
- failure-handling policy
- EcoSim code version
- scenario pack and scorer version

Model-only comparisons are valid only when all non-model components are held
fixed. Otherwise, the result should be reported as a full configuration result,
for example:

```text
model + provider + prompt + observation interface + parser + policy schema
```

This matters because changing the wrapper, prompt, or retry policy can change
the measured behavior even when the model name stays the same.

## 4. Episode Protocol

An eval pack contains scenarios. A scenario contains episodes. An episode is one
simulation run for one governance-agent configuration under one scenario and one
world seed.

```text
eval_pack
  scenario
    episode(seed, initial_stressor, optional_shock_profile)
```

Each episode records:

- scenario id
- world seed
- initial conditions
- initial stressor, if any
- shock profile, or `null` for v0 scenarios
- observation configuration
- action schema version
- decision cadence
- total ticks
- warmup ticks
- baseline runs for the same generated conditions
- model decisions and raw responses
- accepted, rejected, and corrected actions
- tick-level metrics
- episode score and gates

Failed API calls, malformed outputs, invalid actions, and timeouts are not
silently replaced. They are recorded according to the predeclared failure policy.
If an episode is rerun, the rerun is logged as an additional sample unless the
manifest explicitly marks the original as invalid infrastructure failure.

## 5. Observation Model

The LLM should not receive raw simulator omniscience. Its core task is policy
decision-making under uncertainty.

The observation report should expose a compact economic state with:

- lagged indicators
- noisy values where configured
- missing or unavailable indicators where configured
- rolling summaries
- current policy settings
- allowed next policy changes
- recent policy memory and rejected changes

Observation settings are part of the eval configuration and must be hashed in the
manifest.

## 6. Baseline Information Parity

Baselines must be classified by information access.

| Baseline class | Information access | Fair headline use |
|---|---|---|
| Null baseline | No active policy decisions | Lower-bound sanity check |
| Same-information scripted | Same noisy, lagged, partial observation report as the LLM | Fair v0 comparator |
| Direct-metric scripted | Reads current headless metrics directly | Useful comparator, but not same-information |
| Scenario heuristic | Strong hand policy for a scenario, ideally same-information | Stronger comparator if frozen before results |
| Grid frontier | Best found non-LLM policy sweep | Empirical reference anchor |
| Oracle full-state | Reads privileged simulator state | Upper reference only |

Current readiness judgment:

- `no_government` is a null baseline.
- `conservative_scripted` is useful but should be treated as a direct-metric
  scripted comparator unless it is rewritten to consume the same observation
  report as the LLM.
- v0 should report both, but should not imply they are equally fair baselines.
- v1 should add a same-information scripted baseline before claiming that the
  headline comparison measures governance under partial observation.

This distinction is important. If the LLM is evaluated with lagged/noisy data but
the scripted baseline reads current simulator truth, then the comparison mixes
policy skill with information access.

## 7. Action Space And Constraints

The headline v0 eval should use bounded government policy levers. This keeps the
first score comparable, parseable, and auditable.

The action space should include only documented controls such as:

- tax rates inside explicit bounds
- benefit levels
- public works toggles or levels
- sector subsidy target and level
- bailout target and budget
- infrastructure or technology spending levels
- other validated policy levers already supported by EcoSim

Rule compliance is an eligibility gate, not the main construct. A model that
cannot produce parseable valid actions can be capped or invalidated, but a model
does not earn a high score merely by following the schema.

A separate numeric challenge track can be added later. It should not be mixed
with the structured-lever headline score because unrestricted numeric control
tests a different and noisier capability.

## 8. Scenario Cards

Every official scenario should have a scenario card.

Required fields:

| Field | Required content |
|---|---|
| Scenario ID | Stable id, for example `baseline_open_v0` |
| Construct | Capability being tested |
| Initial conditions | Starting economy and policy state |
| Stressor or shock profile | Type, tick, duration, magnitude, affected sectors; `null` for none |
| Observation settings | Lag, noise, coverage, rolling windows |
| Decision cadence | Ticks between decisions |
| Baselines | Null, same-information scripted, reference |
| Primary metrics | Names, direction, units, aggregation window |
| Catastrophe caps | Thresholds and rationale |
| Exclusions | Conditions that invalidate the episode |
| Artifacts | Required traces and manifest fields |
| Claim allowed | What this scenario supports |
| Claim not allowed | What this scenario does not support |

### 8.1 v0 Scenario Card: Baseline Open Economy

| Field | Value |
|---|---|
| Scenario ID | `baseline_open_v0` |
| Construct | General economic stewardship without a forced crisis |
| Initial conditions | Normal EcoSim start |
| Stressor or shock profile | No scheduled shock |
| Observation settings | Standard LLM government observation config |
| Decision cadence | Predeclared in scenario manifest |
| Baselines | `no_government`, `conservative_scripted`; same-information scripted when available |
| Primary metrics | GDP, unemployment, happiness, health, government cash/fiscal stress, distressed firm rate |
| Catastrophe caps | Fiscal collapse, severe welfare collapse, persistent below-baseline performance |
| Exclusions | Infrastructure failure, invalid config, missing scored metric |
| Claim allowed | Model improved normal-start EcoSim outcomes under declared metrics |
| Claim not allowed | Model can handle crises or typed shocks |

### 8.2 v0 Scenario Card: Fiscal Stress Start

| Field | Value |
|---|---|
| Scenario ID | `fiscal_stress_v0` |
| Construct | Tradeoff management under limited fiscal room |
| Initial conditions | Government starts with lower cash or tighter fiscal room |
| Stressor or shock profile | Initial-condition stressor only; no scheduled shock |
| Observation settings | Standard LLM government observation config |
| Decision cadence | Predeclared in scenario manifest |
| Baselines | `no_government`, `conservative_scripted`; same-information scripted when available |
| Primary metrics | Government cash/fiscal stress, unemployment, GDP, happiness, health, distressed firm rate |
| Catastrophe caps | Negative cash persistence, welfare collapse, severe unemployment deterioration |
| Exclusions | Missing fiscal metrics, invalid policy schema, infrastructure failure |
| Claim allowed | Model managed an initially fiscally constrained EcoSim economy better than declared baselines |
| Claim not allowed | Model recovered from an exogenous crisis shock |

### 8.3 Designed But Not v0-Scorable: Unemployment Shock

This scenario is a v1 target. It should not enter the headline v0 score until
EcoSim supports typed, scheduled, magnitude-controlled shock injection.

Blocked requirement:

- apply a labor-demand or firm-distress shock at a known tick
- record shock type, duration, magnitude, and affected sectors
- score recovery windows relative to the known shock event

### 8.4 Designed But Not v0-Scorable: Food-Sector Shortage

This scenario is a v1 target. It should not enter the headline v0 score until
EcoSim supports typed food-sector shock injection and the relevant welfare
metrics are emitted by the headless eval runner.

Blocked requirements:

- apply a food-sector supply, productivity, or firm-health shock
- emit food insecurity, unmet food demand, food affordability, and consumer
  distress through the same metric registry used by the scorer
- define cap behavior for severe food access failures

## 9. Metrics And Welfare Function

EcoSim's headline score is a declared simulated welfare function. It is not a
politically or morally neutral definition of good governance.

Each scenario defines metric weights, caps, and failure thresholds. The score is
therefore a score under that declared welfare function, not a universal measure
of good policy.

Required principle:

> A scenario cannot enter an official eval pack unless every scored metric is
> emitted by the headless eval runner, documented with units, directionality,
> aggregation window, missing-data behavior, and cap behavior.

Metric registry fields:

```text
name
source function or artifact field
unit
higher_is_better
aggregation: mean / final / area-under-curve / max / min / recovery-time
normalization mode
absolute target, if any
baseline anchor
reference anchor, if any
catastrophe threshold, if any
missing value behavior
```

Reports should include subscores and, for reportable comparisons, weight
sensitivity checks. If model rankings depend heavily on contested weights, the
summary should say so.

## 10. Scoring And Gates

The mature score uses an outcome-heavy formula:

```text
raw_score =
    0.70 * economic_outcome_quality +
    0.15 * robustness_score +
    0.10 * policy_efficiency_score +
    0.05 * evidence_grounding_score

final_score = min(raw_score, all_applicable_caps)
```

For v0, the score should use absolute targets plus improvement over baseline.
It should not use baseline = 50 and reference = 100 normalization until a
defensible reference frontier exists.

Eligibility gates:

- parse and schema validity
- runtime completion
- required artifact availability
- required metric availability
- failure policy compliance

Catastrophe caps:

- persistent fiscal collapse
- severe health or happiness collapse
- homelessness or food insecurity above scenario ceiling, if those metrics are
  officially available
- worse-than-baseline performance in most episodes
- severe invalid-action rate

Evidence grounding:

The evidence audit measures whether the model cited observations it was actually
shown. It does not prove that the model's causal reasoning was correct.

## 11. Statistical Reporting

EcoSim results are experiments, not single deterministic facts.

Each reported score is estimated over two variance sources:

- simulator/world variance from seeds, initial conditions, and shocks where
  supported
- model-sampling variance from provider/model decoding

For each model configuration and scenario, EcoSim should report:

- mean final score
- 95% confidence interval or bootstrap interval
- median
- p10 or another tail-risk estimate, when sample size supports it
- collapse rate with uncertainty
- paired comparison against the primary baseline where possible
- invalid episode count
- failed-call count
- malformed-output and invalid-action rates

Suggested run tiers:

| Eval type | World seeds | Model samples per seed | Use |
|---|---:|---:|---|
| Smoke | 1-3 | 1 | Debugging only |
| Development | 3-5 | 1-3 | Internal iteration |
| Internal comparison | 5-10 | 3 | Preliminary comparisons |
| Publishable | 20+ | 5+ | Reportable result |

If budget constraints prevent enough repeats for stable tail estimates, tail
metrics must be labeled exploratory.

Multiple-comparison rule:

Only the overall score versus the primary same-information baseline is treated
as the primary comparison. Scenario subscores, metric-level differences, and
pairwise model rankings are exploratory unless the manifest predeclares them as
confirmatory and applies an appropriate correction.

## 12. Artifacts And Reproducibility

Every eval run should write:

```text
manifest.json
scores.json
episodes.csv
scenario_summary.csv
decision_records.jsonl
raw_model_responses.jsonl
tick_metrics.parquet or tick_metrics.csv
summary.md
```

The manifest should include:

- repo commit SHA
- environment or container hash, if available
- scenario manifest hash
- seed pack hash
- scorer version
- prompt template hash
- observation config hash
- action schema version
- exact model id reported by provider
- provider name
- inference parameters
- provider seed where supported
- provider response metadata where available
- run date
- failed-call policy
- raw trace paths
- normalization mode per metric
- baseline information-access class

Raw model responses should be stored. Provider-hosted models can change over
time, and aggregate scores alone are not enough to debug surprising results.

## 13. Readiness Table

| Component | Status | Meaning |
|---|---|---|
| Bounded action space | Ready | Can constrain and validate policy choices |
| Partial observation | Ready | LLM path can use lagged/noisy/coverage-limited observations |
| Null baseline | Ready | `no_government` can act as lower-bound sanity check |
| Scripted comparator | Partially ready | `conservative_scripted` exists, but is not same-information |
| Evidence audit | Ready | Can check citation grounding, not causal reasoning quality |
| Scenario shocks | Not ready | No official typed scheduled shock layer for v0 |
| Reference frontier | Not ready | No calibrated 100-point reference anchor |
| Statistical protocol | Partially ready | Protocol is defined here; runner still needs aggregation implementation |
| Metrics unification | Partially ready | Some welfare metrics need headless runner exposure |
| Same-information baseline | Not ready | Needed for stronger v1 fairness claim |

## 14. Threats To Validity

Simulator validity:

EcoSim is a model of an economy, not an economy. Scores transfer only to the
extent EcoSim dynamics capture relevant policy tradeoffs.

Baseline validity:

Scores are meaningful only relative to the strength and information access of
the baselines. Beating a null or weak scripted policy is not equivalent to
strong governance.

Metric validity:

The headline score reflects a declared welfare function. Different weights may
imply different rankings, so reports should expose subscores and sensitivity
analysis.

Sampling validity:

LLM outputs are stochastic. Single-run results are not stable capability claims.

Reward hacking:

Outcome-based scoring can reward simulator exploitation. EcoSim mitigates this
through welfare baskets, catastrophe caps, trace inspection, and failure-mode
analysis, but it cannot eliminate the risk.

Contamination and overfitting:

Public scenario packs are suitable for development and transparency. Hidden,
rotated, or held-out packs are required before leaderboard-style claims.

## 15. Related Work Positioning

EcoSim should be positioned as distinct, not unprecedented.

Prior work has used AI or LLM agents as households, firms, workers, planners, or
mechanism designers in economic simulations. EcoSim's narrower contribution is
to evaluate an LLM as a bounded central-government policy actor, with noisy
partial observation, explicit baseline-relative outcome scoring, uncertainty
reporting, and reproducible episode artifacts.

Relevant adjacent work includes:

- AI Economist: AI-driven tax policy in simulated economies.
- EconAgent: LLM-powered household agents in macroeconomic simulation.
- EcoGym: long-horizon LLM agents in interactive economies.
- LLM Economist: mechanism design and large-population generative simulacra.
- HELM-style benchmark design: scenario and metric taxonomies, transparency,
  and multi-metric reporting.
- Construct-valid benchmark guidance: define the phenomenon, keep tasks
  representative, account for contamination and uncertainty, perform error
  analysis, and justify validity.

The defensible claim is not "nobody has evaluated AI in economies." The
defensible claim is:

> EcoSim evaluates LLM government-policy control in a dynamic simulated economy
> with bounded actions, partial observation, baseline-relative outcome scoring,
> uncertainty reporting, and audit-ready artifacts.

## 16. v0 Implementation Slice

A credible v0 should implement:

1. `baseline_open_v0` and `fiscal_stress_v0` scenario manifests.
2. Seed-pack generation for randomized and frozen comparison modes.
3. Baseline runs for `no_government` and `conservative_scripted`.
4. A same-information scripted baseline if feasible; otherwise label the gap.
5. Absolute-target and improvement-over-baseline scoring.
6. Metric registry for every scored metric.
7. Repeat-run aggregation and confidence intervals.
8. Artifact writing for manifests, scores, episodes, decisions, raw responses,
   tick metrics, and summaries.
9. Focused tests for scoring math, gates, seed generation, aggregation, and
   missing-metric behavior.

v0 should exclude:

- scheduled unemployment shock
- food-sector shortage headline score
- baseline/reference 50/100 normalization
- claims of optimality
- claims of real-world policy validity

## 17. v1 Graduation Criteria

EcoSim can graduate from v0 to v1 after:

1. Typed, scheduled, magnitude-controlled shock injection exists.
2. Food and household-distress metrics are available in the headless metric
   registry.
3. A same-information scripted baseline exists.
4. Stronger scenario heuristics or policy-grid reference frontiers are frozen
   before model evaluation.
5. Statistical aggregation is implemented and used in reportable outputs.
6. Scenario cards and metric registry entries are complete for every official
   scenario.
7. The manifest contains enough hashes and raw traces to reproduce or audit a
   result.

Only then should EcoSim publish a stronger claim such as:

> This governance-agent configuration generalizes across typed EcoSim economic
> scenarios and seeded shocks better than specified same-information baselines,
> with uncertainty reported.

## 18. Code Grounding Snapshot

This section is intentionally brief. It records the repo facts behind the current
readiness claims without turning the protocol into an implementation audit.

Current LLM observation path:

- The LLM government prompt is built in `backend/tools/llm/llm_government.py`.
- The observation pipeline applies lag, noise, coverage gaps, rolling summaries,
  policy memory, and allowed action masks before the model decides.
- This supports the claim that EcoSim can test policy decisions under partial
  observation.

Current baseline runner:

- The existing government-control comparator is in
  `backend/tools/llm/run_government_control_compare.py`.
- It supports `no_government` and `conservative_scripted`.
- The conservative scripted policy reads current metrics and unmet-demand
  diagnostics directly, so it should be classified as direct-metric scripted
  rather than same-information scripted.

Current shock readiness:

- EcoSim has seeded ambient randomness inside the economy.
- It does not yet expose an official scenario layer for typed, scheduled,
  magnitude-controlled shock injection.
- Therefore unemployment-shock and food-shortage scenarios should remain v1
  targets until that layer exists.

Current metric readiness:

- `backend/economy.py` exposes many headless metrics through
  `get_economic_metrics()`, including major macro, labor, health, happiness,
  housing, healthcare, fiscal, and firm-distress signals.
- Some welfare signals needed by food and consumer-distress scenarios are
  currently not unified into the same headless scorer-facing metric registry.
- A metric should not enter an official score until it is emitted consistently
  in eval artifacts.
