# Model Scope and Limitations

EcoSim is a local research environment for exploring how policy changes propagate through a synthetic, agent-based economy. Its purpose is to make mechanisms visible, support controlled experiments, and provide a bounded environment for evaluating automated policy agents.

The model is not calibrated to a specific country or historical period. Its outputs describe EcoSim's internal economy, not the real world.

## Appropriate Uses

EcoSim is designed for:

- exploring how a policy lever changes outcomes elsewhere in the simulated system;
- comparing scenarios under the same seed, initial state, and model version;
- studying interactions among households, firms, markets, banking, and government;
- testing whether an LLM can make valid, evidence-grounded decisions within a restricted policy surface;
- benchmarking simulation, data, API, and agent-engineering workflows.

EcoSim is not designed for:

- forecasting real unemployment, inflation, GDP, or public finances;
- estimating the causal effect of a real policy;
- recommending policy for a government, business, or household;
- reproducing national accounts or a particular historical economy;
- proving that one LLM is generally better at governance than another.

## What the Simulation Represents

One tick is approximately one week. Households work, consume, save, borrow, and respond to changing conditions. Firms hire, produce, price, invest, and exit. A bank manages deposits and credit when enabled. Government collects taxes, pays transfers, funds programs, and changes a bounded set of policies.

These components are intentionally connected so that a change in one area can produce second-order effects elsewhere. For example, a wage policy can affect household income, hiring, firm cash, consumption, tax receipts, and fiscal pressure through the same tick lifecycle.

## Important Assumptions

- The population, firms, balance sheets, and shocks are synthetic.
- Behavior is encoded with rules and heuristics rather than estimated from microdata.
- Prices, wages, and currency values are simulation units; they do not map directly to real dollars.
- The economy has a deliberately limited institutional structure and external sector.
- Baseline firms and automatic stabilizers provide safety-net behavior that affects market dynamics.
- Aggregate metrics simplify heterogeneous household and firm experiences.
- Seeded randomness makes a run repeatable, but a single seed is not sufficient evidence for a general result.

## How to Interpret Results

Treat results as conditional statements:

> Under this model version, configuration, seed set, and policy contract, scenario A produced a different simulated outcome than scenario B.

A defensible comparison should:

1. hold the model version and initial conditions fixed;
2. use matched seeds across policy arms;
3. report the number of seeds, households, ticks, and warmup period;
4. distinguish exploratory results from pre-registered or confirmatory runs;
5. include uncertainty or per-seed outcomes instead of relying on one run;
6. preserve the configuration and generated artifacts needed to reproduce the result.

Deterministic replay, contract tests, warehouse records, and matched-seed comparisons strengthen claims about the simulator. They do not establish external validity.

## Known Limitations

- There is no empirical calibration or out-of-sample validation against a real economy.
- Household and firm decisions are heuristic and omit many institutional and behavioral details.
- The banking, monetary, international, demographic, and political systems are simplified.
- Results can be sensitive to seed choice, warmup length, population size, stabilizers, and scenario design.
- The forecasting work predicts future EcoSim state, not real macroeconomic outcomes.
- One distressed-firm edge case remains documented as an expected test failure while the core mechanics are held stable.

## AI Governance Status

The AI Policy Engine is an experimental control layer over a validated, bounded action space. Provider calls happen outside the tick hot path, proposed changes are validated, and accepted actions are applied at safe tick boundaries.

The current LLM comparison demonstrates an evaluation harness, not a mature leaderboard. A stronger benchmark will require repeated seeds, controlled scenario families, fixed prompt and provider metadata, explicit scoring rules, uncertainty estimates, and adversarial or distribution-shift cases. Provider availability and model behavior can also change independently of EcoSim. The planned evaluation contract is documented in the [LLM Economic Governance Eval Protocol](evals/ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md).

## Scope Stability

The economic mechanics are treated as a stable research baseline. Changes to those mechanics should be deliberate, documented, and accompanied by deterministic and matched-seed regression evidence. Current development is focused on AI governance, evaluation quality, observability, and research reproducibility rather than redesigning the economy.

## Deployment Boundary

EcoSim is built for local research use. The API and dashboard do not provide the authentication, authorization, rate limiting, tenant isolation, or operational controls expected of an internet-facing service. Do not expose the default stack directly to the public internet.
