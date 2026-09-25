# Policy effects, individual differences, and AI development agents

**2026-09-21. Fable revision completed; coordinator disposition: useful proposals with the qualifications below.** Read [Fable's revised proposal](ECONOMIC_DESIGN_FABLE_REVISED.md), preserved verbatim, with this review. Fable accepted all eleven prior corrections and supplied policy-transmission maps, a trait inventory, and staged subagent designs. This extends the existing W06–W18 discussion; it does not implement new economic behavior or authorize a population of live LLM actors. The [assignment](ECONOMIC_DESIGN_FABLE_REVISION_PROMPT.md) and [run manifest](ECONOMIC_DESIGN_FABLE_REVISION_RUN.json) identify the corrected source supplied to Claude Fable 5.1.

**Current coordination rules:** use Ayman's proposal-first approach under the [active agent rules v1.1](../ECONOMIC_AGENT_RULES.md). Each reviewer writes an independent document; the orchestrator verifies it against source, then compares it with all other proposals and publishes one integrated plan. The [proposal template, orchestrator process and conflict register](../ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md) make that workflow concrete. The rules are active; an implementation team has not been launched.

## Disposition of the revised Fable report

Accept its emphasis on policy chains, persistent traits, constrained local decisions, subgroup outcomes, and reviewers before coding. Its D01–D11 retractions address the original conceptual errors. That acceptance does not certify every replacement specification: W08/W12 still need complete decisions and fixtures, and the new traits remain hypotheses.

| ID | Statement or design needing qualification | Coordinator disposition and source |
|---|---|---|
| R01 | No direct tax reference in firm pricing (§2.2) | Incorrect. `Economy.step` passes `profit_tax_rate` into `FirmAgent.plan_pricing`; that function and `_healthcare_labor_price_targets` use it in gross-margin/markup formulas. A new `tax_pass_through` trait could duplicate an existing response. Map these paths before designing another. This concerns profit-tax pricing; a direct wage-tax pricing reader is a separate question. |
| R02 | Deposit sweep is only trait-driven (§2.5) | Incomplete. `Economy._process_bank_deposits` multiplies the household deposit fraction by a bounded function of `bank.deposit_rate`. This is already a rate-sensitive allocation rule, even though it is not a complete intertemporal consumption model. The rate-cost arithmetic alone does not establish a weak aggregate effect: thresholds and financing constraints require measurement. |
| R03 | Firm individuality is “class plus jitter,” with only cash differentiating policy response (§3.3) | Overstated. `FirmAgent.set_personality` draws from ranges within a class, and risk tolerance, expectations, productivity, inventory targets and pricing behavior have readers. The initialization probe confirms distinct within-class profiles. Existing response diversity and actual magnitudes need measurement before adding six traits. ID-structured initial endowments are a disclosed design choice, not automatically a software defect. |
| R04 | Free care cannot change request volume (§2.4) | Only a direct, fixed-state statement is supported. The current request rule lacks a direct price input, but realized care changes health, and future requests read health. Endogenous feedback can therefore alter later request volume. A source-level missing direct price reader is not a claim of no dynamic demand response. |
| R05 | Constraints force identical spending or waiting (§3.6) | Too strong. Require each actor to respect its own budget and resolved supply; different caps, purchase composition, provider choice and queue priority can yield different outcomes. Equal actions are an acceptance case only when the relevant state and constraints have also been equalized. |
| R06 | A runner-only exporter can add exact planning inputs (§4.3) | Not established. End-of-tick `to_dict` values cannot reconstruct all pre-decision inputs, caches or intermediate states. Inventory existing outputs first; any missing observation point needs a bounded instrumentation contract that neither reruns stateful planners nor consumes RNG. |
| R07 | Replay cache separates shock and model variance (§4.4) | Incomplete. New seeds or endogenous trajectories change observation keys and can miss the cache. Freeze sampling settings and action/schema versions as well as model/prompt/observation, and distinguish independent response replications so cache hits do not erase model variability. Recorded replay reproduces that trace; it is not a complete response policy for new states. Use a crossed seed-by-model-replication design with uncertainty intervals. Comparing an effect directly with a variance is not a valid generic interpretation threshold. |
| R08 | Replacement formulas and defaults are ready to code | Keep them at design status. D02 needs a joint bank-liquidity reservation across all contributing owners, not independent checks against the same reserves. D03 still needs startup cut-points and a shared once-per-boundary calculation. The care-cost rule must define zero liquidity and which price is knowable before provider choice. Bounded trait-spread sensitivities must stay within bounds. “Zero-cost when off” and scalar/batch equality require evidence; equivalent helper code does not prove identical call-site inputs or cadence. |

Fable's new F1 finding is supported by source: `_build_firm_tax_snapshots` omits cash and housing/property fields that `GovernmentAgent.plan_taxes` expects. It warrants a bounded path probe. **Correction from the agent-rules source check:** property-tax settlement consumers do exist in `Economy.step`: phase 9 debits firm cash and phase 11 includes the aggregate treasury receipt. The missing inputs are in the snapshot producer; enriching them still needs an executed producer-to-settlement check before calling the path fixed. **The headline profit-tax rate remains active** through settlement and pricing; the concern is collapsed firm-bracket differentiation and the property-tax path, not all business taxation being inert. No bracket redesign is proposed.

This coordinator note was updated when rules v1.0 were established. The original Fable documents and revision-run manifest retain their historical contents and hashes; the [rules source record](evidence/ECONOMIC_AGENT_RULES_SOURCE.json) identifies this later documentation revision.

F2 identifies a reused numerical seed between household traits and annual visit-count sampling when the anchor is zero. Treat this as a structural coupling candidate; mapping a shared underlying draw through different distributions does not make the resulting trait and visit count numerically equal or establish an aggregate effect.

The report's read-only case-review phase can proceed as a design proposal. Diagnostic slices of W06/W07/W09/W10 remain the next bounded implementation candidates if selected. New behavioral traits, closures, healthcare regimes and live LLM actors are not promoted to implementation-ready by this review. The cumulative runtime target is measured against one declared package baseline, not reset separately for each worker or stage.

## What the user wants to preserve

Policy comparisons should explain how changes reach other actors through decisions, prices, jobs, financing, and scarce resources. A policy need not help every group, and its first effect need not have the same sign as its later effects. Here, “trickle down” means these transmission and feedback paths; it does not assume that gains automatically flow from richer to poorer agents.

Each household and firm should have a distinct, persistent profile, while keeping the existing role and shared behavior code. The current `HouseholdAgent` combines individual attributes such as age and employment with a household budget. This is a modeling abstraction; requiring distinguishable agents does not by itself specify family formation, dependents, or multiple people per household.

Preserve progressive brackets, modest runtime costs, and the [shared accounting and integration contract](../ECONOMIC_AGENT_WORKING_CONTRACT.md). New traits, model calls, or coordination machinery must answer a specific question.

## What already exists

The current code already samples continuous traits within household and firm types:

| Actor | Existing differences | Relevant decision readers |
|---|---|---|
| Household spending and saving | Spending tendency, frugality, saving tendency, derived cash drawdown and deposit rules | `Economy._batch_plan_consumption`, `HouseholdAgent.compute_saving_rate`, `Economy._process_bank_deposits` |
| Household purchase and learning | Price sensitivity, category preferences, price beliefs, price-expectation smoothing | `HouseholdAgent._plan_category_purchases`, `Economy._batch_apply_household_updates` |
| Household work | Skills, experience, reservation wages, wage-expectation smoothing, switching threshold | `HouseholdAgent.plan_labor_supply`, `HouseholdAgent.apply_labor_outcome`, `Economy._run_labor_matching` |
| Household health | Health loss rate, care thresholds, medical capacity and wage characteristics | `HouseholdAgent.update_wellbeing`, `Economy._batch_update_wellbeing`, medical request/queue resolution |
| Firms within one personality | Risk tolerance, adjustment speeds, output per worker, sales-expectation smoothing, inventory targets | `FirmAgent.plan_production_and_labor`, `plan_pricing`, `plan_wage` |

Initialization lives in [HouseholdAgent._initialize_personality_preferences](../../backend/agents.py) and `FirmAgent.set_personality`; batch and settlement paths live in [economy.py](../../backend/economy.py). A listed reader identifies a source path, not proof that every trait matters in every state. Caps, survival rules, stabilizers and performance-mode cadence can mute or change the response. The existing scalar/batch saving-input discrepancy remains separately recorded in the earlier audit.

The [bounded initialization probe](verify_behavior_diversity.py) constructed 1,000 households with the same stated age, skill and cash inputs, and 100 non-baseline Food firms sharing the moderate personality and stated financial inputs. All 1,000 household profiles and all 100 firm profiles were distinct on the selected traits, and reconstructing the same IDs with seed 42 reproduced those traits exactly. The [results](evidence/ECONOMIC_BEHAVIOR_DIVERSITY.json) record constructors, selected fields, ranges, counts and source hashes. This is not evidence that every policy produces different choices or that the trait distributions match real populations. No economic ticks or policy effects were measured.

Audit actual readers before adding more personality parameters. For example, `quality_preference_weight` and `investment_propensity` are initialized and serialized in the current core, but the inspected household/firm decision code does not consume those named fields. Similarly, `rd_spending_rate` is sampled and accepted by the experimental firm advisor, while `FirmAgent.apply_rd_and_quality_update` computes expenditure from profit margin and configuration rather than that field. The probe also exercises this method on two identical firm copies: setting that field to 0 or 0.25 yields the same 100 model currency units of spending at revenue 1,000 and profit 100. This is an isolated-method result, not a policy-effect estimate. Other quality and investment mechanisms exist. A field's label or comment alone does not establish its causal role.

## How to make downstream effects auditable

For each policy ticket, record the immediate payer/recipient, the first changed decision, other affected actors, the delay, the budget or capacity that can stop the effect, and a plausible competing effect. Keep existing links separate from proposed ones. Higher take-home pay might increase purchases, reduce debt, or accumulate as deposits; additional sales only lead to more hiring if the firm's demand expectations, capacity, wage costs and financing allow it. The sign and size are experimental outcomes under declared assumptions.

Use two kinds of evidence:

1. **Mechanism checks:** small controlled cases show that a tax, price, wage, loan, or capacity change reaches the intended decision and settles both sides correctly. Freezing a channel here diagnoses the code; it is a different artificial intervention, not an automatic estimate of that channel's share of the total effect.
2. **Composed policy comparisons:** follow the whole economy across time with declared fiscal rules and measured subgroup outcomes. Preserve pre-policy cohort definitions for comparisons; separately report entries, exits and changing group membership so survivor selection does not silently change the sample. Include distributions and transition paths, not only an aggregate ending value.

Do not force distinct actions as a uniqueness requirement. Two different households may both buy only food when their budgets bind. Useful tests should include both a state where the relevant trait changes an unconstrained decision and a state where a common constraint legitimately makes choices coincide.

## A feasible subagent arrangement

There are three separate applications of the idea:

| Application | What the AI does | Recommendation |
|---|---|---|
| Development workers | Propose or implement a bounded household, firm or institutional mechanism | A small team is practical; one coordinator owns shared settlement, state definitions and integration. |
| Reviewers for sampled economic cases | Inspect the information, constraints and choices of one household or firm, and propose missing mechanisms or counterexamples | Useful as a design exercise. Their stories require source checks and executable cases before becoming behavior. |
| Live economic actors | Choose a simulated household's purchases or a firm's offers during the run | A separate research experiment with provider cost, latency and model variability. Begin with one actor and a validated action interface if selected later. |

The existing [household LLM tester](../../backend/tools/llm/run_household_llm_tester.py) narrates decisions already made by the simulator; it does not control them. The [firm advisor](../../backend/tools/llm/llm_firm.py) and [standalone runner](../../backend/tools/llm/run_llm_firm_test.py) support a bounded single-firm intervention. These are useful starting points but are not a live population of household and firm controllers.

For development, a proposed first team is three bounded workers plus one coordinator: household decisions, firm decisions, and institutional/accounting interfaces. During design, the workers can inspect the same frozen baseline. During implementation, assign exact symbols in isolated patches or worktrees, because all four main economic classes share `backend/agents.py` and many decisions also live in `backend/economy.py`. The coordinator merges in dependency order and checks a composed transaction trace and cumulative runtime. Independent successful tests do not establish that the pieces agree on cash, debt, information, or timing.

Sampled reviewers can represent different combinations of liquidity, debt, employment, health, ownership and firm capacity. Choose cases to expose different constraints; do not assign moral or behavioral stereotypes to income groups. They should propose changes to the common behavior model, rather than special-case code for a favorite individual.

**The objective needs precise wording.** Coding agents should improve fidelity, accounting, coverage and evidence. Simulated actors should pursue stated local goals using available information and resources. Giving all simulated people a shared instruction to improve aggregate GDP or make a policy succeed would impose cooperation and foresight that the policy comparison has not established.

For an optional live trial, let the AI propose bounded actions while the engine validates and settles transactions. Freeze observations, model and prompt versions, decision cadence, response logs and fallback rules. Stored-response replay can reproduce a particular trace; rerunning a provider remains a separate variability experiment. Approximate scheduled calls are `controlled actors × decision boundaries × policy arms × shock seeds × model replications`, before retries. This arithmetic explains why a small pilot and the normal deterministic engine should remain separately measured.

## Evidence and interpretation

- [Turrell, Bank of England (2016), Agent-based models: understanding the economy from the bottom up](https://www.bankofengland.co.uk/-/media/boe/files/quarterly-bulletin/2016/agent-based-models-understanding-the-economy-from-the-bottom-up.pdf): supports modeling interactions and heterogeneous actors with relatively simple rules; also explains the difficulty of selecting and validating behavior. It does not validate EcoSim's traits, calibration or policy outcomes. The article was inspected for this review.
- [Horton, Filippas and Manning, Homo Silicus, arXiv v2 (2026)](https://arxiv.org/html/2301.07543v2): explores LLM economic experiments with specified information, endowments and preferences. This supports treating live LLM actors as an experimental approach, not assuming their behavior is a calibrated substitute for a population. Abstract and paper were accessed for this review; no replication was performed.
- [Kaplan, Moll and Violante, Monetary Policy According to HANK](https://www.nber.org/papers/w21897): the indexed primary-source abstract describes consumption responses through both direct and indirect labor-demand channels under that model's assumptions. This motivates tracing downstream channels, not transferring its coefficients or conclusions to EcoSim. Direct NBER page/PDF fetches returned HTTP 403; only the indexed abstract was inspected here.

Fable's output names additional sources without clickable URLs; these are the corresponding primary pages, fetched by the coordinator to make the catalog auditable:

- [Jappelli and Pistaferri, Fiscal Policy and MPC Heterogeneity](https://www.aeaweb.org/articles?id=10.1257/mac.6.4.107): evidence concerning differences in consumption responses; not calibration of EcoSim's new traits.
- [Fuest, Peichl and Siegloch, Do Higher Corporate Taxes Reduce Wages? Micro Evidence from Germany](https://www.aeaweb.org/articles?id=10.1257/aer.20130570): a particular empirical setting for tax incidence; not a general tax pass-through coefficient for this simulator.
- [Park et al., Generative Agents](https://arxiv.org/abs/2304.03442): a demonstration of agents with memory and behavior in a small interactive setting, not validation of macroeconomic accounting or policy effects.
- [NumPy parallel RNG guidance](https://numpy.org/doc/stable/reference/random/parallel.html) and [Python random documentation](https://docs.python.org/3/library/random.html): support deliberate stream construction and documented reproducibility limits. They do not prove this application's stream independence or cross-version replay. Runtime versions remain part of the evidence.

The source review and initialization/isolated-method probes support the current-code statements above. The team size, sampled-case workflow and live-trial sequence are coordinator recommendations. Fable used 29 Read, 18 Grep, one Glob and 10 WebFetch calls; one Grep failed on unsupported look-around, which its report acknowledges. The exact output and source hashes are retained. The coordinator's new probes and latest proposal template were added after Fable's frozen input and must not be attributed to Fable. No new traits, policy mechanisms, policy-effect estimates, real-world calibration or performance results were implemented or established in this review.
