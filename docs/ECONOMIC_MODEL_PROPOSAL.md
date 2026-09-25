# EcoSim economic model: premise, audit, and proposed roadmap

**Status: proposal for review.** The changes below are recommendations, not an approved implementation plan or claims about features already delivered.

**Independent review completed:** read the [Fable 5.1 audit](reviews/ECONOMIC_MODEL_FABLE_AUDIT.md) and [coordinator verification and disposition](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md) alongside this original proposal. The follow-up records additional accounting findings, corrections to the review, and a narrower recommended first package. The original review did not change the engine. The later [W01–W05 package](ECONOMIC_CONCRETE_PACKAGE.md) implements the agreed concrete corrections; all findings below retain their original audited-source provenance.

**Work readiness:** the [readiness breakdown](ECONOMIC_WORK_READINESS.md) separates concrete fixes from items needing a focused specification or a fuller economic design, with an action and completion condition for each.

| Provenance | Value |
|---|---|
| Prepared | 2026-09-21 |
| Requested by | Ayman |
| Basis | Economic-logic audit, focused executable probes, and the economic sources cited below |
| Audited repository | AymanCode/EcoSim |
| Audited commit | `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46` |
| Version check | Local HEAD and GitHub main matched on the preparation date |
| Source boundary | The cited economic-engine files matched that commit; unrelated local documentation, test, and packaging edits existed |
| Implementation status | No economic-model changes were made for this document |

## 1. Premise and intended outcome

EcoSim should let a person change economic policies or institutions, observe how households and firms respond, and compare the resulting economy against a clearly defined alternative. Its purpose is to make policy mechanisms and tradeoffs inspectable.

The central questions are:

| Comparison | What the experiment should explain |
|---|---|
| Lower versus higher taxation, including the motivating 15% versus 40% example | How a defined change in tax burden affects disposable income, spending, work, business investment, public services, distribution, and government finances |
| Healthcare free at the point of use versus private payment or insurance | How financing and delivery arrangements affect access, waiting time, treatment, health, medical debt, work, and the total burden on households and government |
| Lower versus higher inflation, and alternative responses to inflation | What causes prices to rise, who gains or loses purchasing power, and how policy affects output, employment, borrowing, and financial stability |
| Different economic systems and governance arrangements | How ownership, production decisions, investment allocation, price setting, surplus distribution, and government decision processes change outcomes |

**Progressive taxation is part of the intended model.** Ayman explicitly prefers different tax brackets to a flat rate and asked that bracket refinements not become a main priority. A tax experiment should record exactly which schedule parameters change and report the resulting effective burdens. This proposal does not prioritize replacing or redesigning the bracket system.

The desired result is a conditional explanation: *under these institutions, behavioral assumptions, initial conditions, and shocks, policy A produced these differences from policy B, through these identifiable mechanisms.* It should be possible to inspect winners, losers, costs, transition effects, and uncertainty without relying on a single headline score.

The current project describes itself as a synthetic research environment without calibration to a particular country. This proposal develops that purpose; it does not establish real-world forecasting accuracy or causal policy estimates. Any later country-specific claim requires additional calibration and validation. [C14]

## 2. How to audit this document

Read sections 1 and 3 for purpose and priorities. Section 4 gives each proposed workstream a stable ID, source evidence, economic rationale, proposed scope, and acceptance criteria. Section 5 covers later extensions. Section 6 defines a reviewable experiment. Sections 7–9 contain the evidence register, executable checks, and source catalog.

Evidence has four different meanings here:

| Label | Meaning |
|---|---|
| Source finding | Behavior verified in the code at the audited commit |
| Probe finding | Behavior reproduced by the bounded checks in section 8 |
| Economic assessment | An interpretation of why a finding matters; open to challenge |
| Proposal | A suggested change or acceptance criterion; not something the cited research necessarily prescribes |

Code references **C01–C20** point to commit-pinned source. Economic references **S01–S10** support the surrounding economic concepts. Probe references **E01–E05** identify reproducible observations. Source comments and generated wiki descriptions are navigation aids; executed code and observed results take precedence when they conflict.

A reviewer can reject an assessment without disputing a source finding. For example, an exogenous financial inflow might be a deliberate modeling choice. It would still need an explicit external-sector or monetary interpretation and experiment controls.

## 3. Proposed priorities

The model already has heterogeneous households, adaptive firms, capital investment and depreciation, credit, rental housing, and healthcare queues and training. Preserve these useful mechanisms while addressing the gaps below. [C04] [C09] [C11] [C18] [C19]

| ID | Proposed workstream | Why it matters first | Main dependency | Status |
|---|---|---|---|---|
| [P01](#p01-money-and-ownership-accounting) | Money and ownership accounting | Unfunded firm entry can alter policy outcomes | None | Proposed |
| [P02](#p02-government-financing-and-fiscal-rules) | Government financing and fiscal rules | Tax-and-spending comparisons need an explicit financing response | P01 | Proposed |
| [P03](#p03-comparable-measures-of-output-and-household-welfare) | Comparable output and welfare measures | Current measures can report misleading policy differences | P01 for comprehensive net worth | Proposed |
| [P04](#p04-household-and-firm-responses-to-policy) | Household and firm responses to policy | Policies need to act through decisions as well as cash constraints | P02–P03 for consistent inputs and evaluation | Proposed |
| [P05](#p05-explicit-economic-stabilizers-and-common-agent-capabilities) | Explicit stabilizers and common agent capabilities | Support-policy comparisons currently risk changing private decision rules too | Start with P10 experiment controls | Proposed |
| [P06](#p06-production-inputs-and-delivery-of-public-investment) | Production inputs and public-investment delivery | Spending should use resources and deliver identifiable output | P01–P03 | Proposed |
| [P07](#p07-inflation-and-monetary-policy) | Inflation and monetary policy | The inflation target currently has no economic effect | P01–P03; connect P04 and P06 | Proposed |
| [P08](#p08-healthcare-financing-and-provider-arrangements) | Healthcare financing and provider arrangements | A capped subsidy does not represent a complete healthcare system | P02–P04; retain existing care capacity | Proposed |
| [P09](#p09-economic-institutions-and-governance) | Economic institutions and governance | System labels need different operating mechanisms | P01–P06 and P10; sector modules as used | Proposed |
| [P10](#p10-controlled-experiments-calibration-and-validation) | Experiments, calibration, and validation | Every later claim needs an inspectable evidence trail | Begin immediately and extend throughout | Proposed |

Suggested sequence: establish the experiment contract and fix accounting/measurement first; improve agent responses, stabilizers, and investment delivery next; develop healthcare or monetary policy according to the next comparison selected; then assemble institutional scenarios. Calibration and validation accompany every stage.

## 4. Proposed workstreams

### P01 Money and ownership accounting

**Classification:** source and probe finding; foundational correction.

**Current evidence.** The new-firm creation routine assigns random startup cash to the bootstrapped funding path and to some rejected-loan fallback paths. Those paths do not deduct the cash from an owner or create an associated loan. In E03, with government and bank cash set to zero, one entrant received 20,041.424449 currency units and aggregate modeled cash increased by the same amount. Household cash did not fall and the entrant received no bank or government debt. This is an isolated entry-mechanism probe, not a whole-economy policy experiment. [C01]

**Why it matters.** A policy that changes the rate of firm failure or replacement can change the amount of this newly introduced money. Recovery, consumption, or competition could then partly reflect the entry-financing shortcut. The modeled economy needs consistent financial claims, even where money creation is legitimate. Commercial-bank lending can create deposit money; that creation has a matching loan asset and deposit liability. [S01]

**Proposed scope.** Record household assets and debts, firm ownership and financing, bank assets/liabilities/equity, and government financial positions. Each startup should be funded by an identified owner contribution, investor, loan, grant, or explicit external inflow. Record new physical assets separately from the financial transaction financing them. Reconcile deposits, repayments, defaults, liquidations, and dividends across counterparties.

**Acceptance criteria.**

- An owner-funded startup reduces the owner's liquid assets and gives the owner an equity claim; it does not silently add aggregate cash.
- A loan-funded startup produces consistent lender and borrower entries under the chosen banking model.
- Explicit money creation, external inflows, asset revaluation, and production are separately identifiable; a fixed total-money invariant is not imposed on all scenarios.
- A firm exit resolves or records residual assets, equity losses, creditor losses, and outstanding liabilities.

### P02 Government financing and fiscal rules

**Classification:** source and probe finding; missing institutional mechanism.

**Current evidence.** Government transfers can reduce treasury cash below zero. GovernmentAgent has no public_debt balance at the audited commit, while the debt-to-GDP helper reads that attribute with a zero fallback. E02 produces treasury cash of −1,000 and a reported annualized debt-to-GDP ratio of zero. A separate formula maps recent fiscal deficits into a spending-efficiency penalty. The operation called government bond purchases distributes surplus money through the miscellaneous pool rather than maintaining a bond asset with an issuer and repayment terms. [C02] [C07]

**Why it matters.** A tax comparison also requires a rule for the use of additional revenue or the financing of lost revenue. Holding expenditure fixed, expanding services, and reducing borrowing are different experiments. Fiscal effects also depend on economic capacity and financing conditions; a preset efficiency penalty cannot by itself establish those mechanisms. [S08]

**Proposed scope.** Specify whether the government issues its own currency or operates under another monetary constraint. Represent taxes, transfers, purchases, debt issuance, debt holders, interest, maturity, and any central-bank financing. Give scenarios an explicit fiscal rule, such as fixed services with borrowing, a spending envelope linked to revenue, or a declared debt-management rule. Represent implementation capacity directly if it is a policy dimension.

**Acceptance criteria.**

- A deficit reconciles to a financing transaction or a clearly specified monetary operation; it does not disappear behind a zero debt metric.
- Debt stocks, interest payments, treasury cash, and budget flows reconcile, with weekly and annual units documented.
- A tax experiment identifies what adjusts when revenue changes and holds that rule constant across paired runs.
- Any administrative-efficiency assumptions are visible, separately configurable, and tested for their effect on policy rankings.

### P03 Comparable measures of output and household welfare

**Classification:** source and probe finding; measurement correction.

**Current evidence.** Household wealth percentiles and the reported Gini use cash balances, excluding bank deposits, ownership claims, and debts. E04 holds every household's cash at 100 and places a million in one household's deposits; reported Gini remains zero. The poverty count uses the government's benefit-linked minimum-cash threshold. E05 changes the benefit preset without advancing time and changes the poverty count from 0 to 200 with no household-finance change. GDP sums firm revenues; the core mean-price measure averages posted firm prices. The server's inflation feature uses a simple average of nonzero food, housing, and services category prices. [C03] [C10]

**Why it matters.** A policy ranking is unreliable if its outcome measures change definition between scenarios or confuse prices with quantities. Real output measures remove price changes. Consumer price indexes track a defined basket with expenditure weights; household inflation experiences can differ. [S02] [S03]

**Proposed scope.** Publish separate measures of nominal output, real output, household disposable income, liquid resources, net worth, consumption, unmet needs, health, and fiscal position. Use a declared consumer basket and period convention for inflation. Keep poverty eligibility rules separate from evaluation thresholds; support a predeclared real poverty line and, where useful, a consistently computed relative-income measure. Show distributions and group outcomes alongside means. State the treatment of negative net worth and avoid hiding it through arbitrary rescaling.

**Acceptance criteria.**

- Transferring funds between a household's cash and deposit account leaves its net worth unchanged.
- A policy change alone cannot change measured poverty unless it changes resources, prices under a declared real threshold, or an explicitly declared relative benchmark.
- Scaling all transaction prices with quantities fixed changes nominal output but leaves the corresponding real-output measure unchanged.
- Financial transfers are not counted as newly produced output; intermediate purchases are handled consistently once P06 introduces them.
- Headline outcomes can be reconciled to agent records and inspected by income group, employment status, borrower/saver status, and health need.

### P04 Household and firm responses to policy

**Classification:** source finding and economic assessment; behavioral-model improvement.

**Current evidence.** Ongoing household consumption budgets begin with gross wages, benefit income, and dividends; wage taxes are applied in later settlement. Taxes affect eventual liquidity, so they are not economically inert, but expected disposable income is not consistently used by the main spending plan. Main labor plans cover search, reservation wages, and switching, without a work-hours choice. A post-warmup reset does use a simplified net-wage calculation; this proposal does not claim all tax awareness is absent. Default spending propensities are 0.85 for wage income, 0.95 for benefits, and 0.40 for dividends, with an automatic increase during high unemployment. [C04]

**Why it matters.** Redistribution and tax results depend on who changes spending, why, and by how much. Research on households with low liquid wealth shows why substantial illiquid assets do not necessarily imply a weak spending response to an income change. Income source alone is therefore a limited guide to behavior. [S09]

**Proposed scope.** Use consistent expected take-home income, accessible savings, debt obligations, essential costs, and job/income risk in decisions. Add work-hours, training, or entrepreneurship choices when the relevant experiment needs them. Connect firm investment to expected demand and returns after applicable taxes, while preserving existing capital and credit mechanics. Estimate or justify behavioral parameters and document plausible alternatives.

**Acceptance criteria.**

- Holding gross wages and initial assets constant, a tax change reaches expected disposable income and can affect a household plan before its savings are exhausted.
- The timing of income, taxes, borrowing, purchases, and expectations is consistent across planning and settlement.
- An unconstrained household is allowed to smooth consumption; no test requires every tax change to cause the same immediate spending response.
- Policy rankings are checked under alternative plausible saving, labor, expectation, and investment responses; a desired ideological result is never an acceptance criterion.

### P05 Explicit economic stabilizers and common agent capabilities

**Classification:** source finding; experiment-design and model-boundary correction.

**Current evidence.** Registered government baseline firms are exempt from the normal bankruptcy removal path. Disabling firm stabilizers switches production planning to a separate, simplified rule and makes wage planning retain the existing wage. Therefore the switch changes private adaptation as well as support behavior. The household crisis spending boost is another stabilizing assumption and is not simply a fiscal program. [C05] [C04]

**Why it matters.** A comparison should identify which institution changed. If one scenario also gets a different private decision algorithm, the resulting difference cannot be attributed solely to the support policy. Public fallback providers can be a valid institution, but their survival and funding conditions need to be represented.

**Proposed scope.** Inventory each safeguard and classify it as a software invariant, a behavioral assumption, or an economic institution. Keep basic agent capabilities and information rules consistent across paired runs. Expose public ownership, insurance, bailouts, entry support, and other institutions individually. Measure their cost and activity. Test the sensitivity of results to recovery-oriented behavioral assumptions. This follows the broader need to validate mechanisms as well as aggregate patterns. [S06]

**Acceptance criteria.**

- Disabling a bailout changes support eligibility or financing without silently freezing private wage adjustment.
- Baseline providers have explicit ownership, financing, service obligations, and loss-resolution rules.
- Every experimental toggle states the equations or decisions it changes, and its activation is observable in run evidence.
- Software invariants protect valid state; they do not silently supply demand, money, or policy success.

### P06 Production inputs and delivery of public investment

**Classification:** source finding; missing real-resource mechanism.

**Current evidence.** Firms already have capital, production functions, investment, and depreciation. However, the main production phase passes zero other-variable-costs. Public infrastructure spending directly increases a productivity multiplier. Investment/R&D payments are routed through a miscellaneous pool, which distributes revenue to selected households and limits its beneficiary list to 50; those payments do not arise from a corresponding construction or equipment-producing market. [C06] [C18]

**Why it matters.** Government and private buyers can compete for labor, materials, equipment, and production capacity. Money spent, resources purchased, and productive capacity delivered are distinct events. Input-output accounts explicitly describe production relationships between industries and commodities; EcoSim can begin with a much smaller version of that structure. [S10]

**Proposed scope.** Introduce a minimal capital-goods/construction sector and a small set of inputs, such as equipment and energy. Represent procurement, production limits, completion delays, project failures, maintenance, and depreciation. Pay identifiable suppliers and workers. Let public investment affect productivity through delivered assets or services, with uncertain or diminishing returns where justified. Apply the same accounting to private investment and R&D.

**Acceptance criteria.**

- An order creates a payment/obligation and supplier demand; it creates productive capacity only when delivery occurs.
- With spare resources, additional orders can expand activity. With constrained resources, they can increase delays or input costs. The result is not forced to have one sign.
- Public and private projects use the declared resource markets and their payments reconcile.
- Investment benefits, maintenance costs, implementation lags, and distribution of payments can be audited separately.

### P07 Inflation and monetary policy

**Classification:** source and probe finding; missing policy transmission.

**Current evidence.** The server stores an inflation target on GovernmentAgent, but the inspected economic engine does not consume it as a policy rule. E01 compares targets of 0.02 and 0.15 for 200 households over 52 ticks under seeds 42 and 77. Every recorded economic-state fingerprint matches within each seed. Prices do still respond to firm rules; this finding concerns the unused target. The bank lends against available reserves rather than representing a distinct commercial-bank deposit-creation process and central-bank policy authority. [C08] [C09]

**Why it matters.** Higher inflation can result from different causes. A supply disturbance and a demand expansion need not have the same output effects or policy tradeoffs. Monetary transmission also involves interest rates, expectations, and credit, rather than a label on a government object. [S01] [S07]

**Proposed scope.** Separate the central-bank policy rule from commercial lending. Connect rates, bank balance sheets, credit demand and supply, price expectations, and wage adjustment. Use P03's price index and distinguish nominal contracts from real purchasing power. Define reproducible demand, productivity, and input-cost shocks. A user-selected exogenous inflation path may remain useful as a separate stress test, with its imposed nature made explicit.

**Acceptance criteria.**

- Changing a target changes the declared policy rule under conditions that call for a response; a target is not interpreted as guaranteed realized inflation.
- A monetary-policy change has traceable effects on borrowing terms, decisions, and outcomes, with reported timing.
- Fixed nominal debts and contracts change real burden consistently as the price level changes.
- A cost shock and a demand shock can be studied separately, using the same measurement definitions and paired shock histories.
- E01 is superseded by evidence of the implemented transmission path; its current equality result is not preserved as desired behavior.

### P08 Healthcare financing and provider arrangements

**Classification:** source finding; institutional extension of an existing service model.

**Current evidence.** Healthcare already includes requests, queues, doctor/resident capacity, medical training, affordability checks, loans, and healing from completed visits. The canonical subsidy levels are 0%, 10%, 25%, and 50%. A lower-level configuration can request a larger share, but payments still pass through the subsidy cap and the remainder becomes the patient's cost. These mechanics do not establish universal free-at-use coverage or insurance risk pooling. [C11]

**Why it matters.** Financing systems differ in revenue raising, pooling, purchasing, coverage, and cost sharing. Service capacity also matters: changing the payer does not create clinicians immediately. WHO explicitly recommends examining these financing functions rather than inferring system behavior from labels alone. [S04]

**Proposed scope.** Model patient payment, private insurance, pooled public financing, and mixed arrangements as distinct payer contracts. Keep payer type separate from provider ownership. Specify benefits, premiums or taxes, copayments, provider payment rules, and coverage during unemployment. Preserve capacity constraints and connect their expansion to training and investment. Distinguish acute/chronic need or preventive care where that distinction is needed for the comparison.

**Acceptance criteria.**

- A covered free-at-use visit charges the patient zero; the provider's funding and resource cost remain accounted for.
- A capacity shortage produces an explicit queue or other declared rationing outcome rather than silently reverting to an unexpected patient bill.
- Matched scenarios share the starting population and underlying health shocks; care delivered may diverge because the systems respond differently.
- Outcomes include coverage, unmet need, waits, health, medical debt, taxes/premiums, provider finances, and work lost to illness.
- Workforce expansions respect training/completion lags; healthcare funding is evaluated together with its financing rule.

### P09 Economic institutions and governance

**Classification:** source finding and proposed model architecture; future extension.

**Current evidence.** The policy schema changes taxes, benefits, public works, subsidies, spending, price/rent restrictions, and bailouts. It does not define alternative ownership regimes, cooperative objectives, general production planning, or allocation institutions. Existing private ownership and public baseline providers are useful starting components. [C12] [C05]

**Why it matters.** Taxation and welfare spending do not alone determine who owns productive assets or allocates investment. The economic-system comparison needs operational definitions. Private ownership, market allocation, government provision, and nonmarket coordination can coexist in different combinations. [S05]

**Proposed scope.** Build explicit institutional dimensions, then create named scenario presets from them. The table lists candidate dimensions, not a declaration that every option has been selected for implementation.

| Dimension | Candidate alternatives | What must change in the model |
|---|---|---|
| Ownership | Private investors, worker cooperatives, public enterprises, mixed ownership | Control rights, asset claims, losses, and recipient of surplus |
| Enterprise objective | Profit, member income, service targets, production plans | Production, staffing, investment, and distribution decisions |
| Allocation | Market purchases, public provision, administered prices, rationing | Access rules and resolution of excess demand |
| Investment | Private finance, public funds, planned budgets | Project selection, financing constraints, and allocation of equipment/labor |
| Labor institutions | Individual bargaining, collective bargaining, job guarantees | Wage setting, job access, and program obligations |
| Surplus | Dividends, worker distributions, public revenue, retained investment | Payments and ownership accounting |
| Governance | Different decision delays, information quality, accountability, administrative capacity | Policy observation, implementation, and correction processes |

Use the labels capitalism, socialism, and communism only with an attached definition of the represented institutions. If a scenario represents a historically centralized planned economy, state that explicitly rather than claiming it exhausts every meaning of communism. Keep political governance and economic ownership as separate dimensions. Assign no automatic productivity, benevolence, corruption, or competence bonus based on a label.

**Acceptance criteria.**

- Every preset expands into a saved, inspectable institution configuration.
- Ownership and objective changes alter the appropriate decisions and financial claims, not just chart labels.
- Common initial resources, agent capabilities, and shock assumptions are documented; transition experiments also account for transfers of existing ownership.
- Scarcity, gains, losses, and distribution remain measurable under each allocation system.
- Comparative conclusions report assumptions and group outcomes rather than declaring a universally superior ideology.

### P10 Controlled experiments, calibration, and validation

**Classification:** existing capability to extend; evidence gap.

**Current evidence.** The forecasting wrapper constructs seeded economies, applies policy before the first step, and records trajectories. That supports comparisons of different starting regimes. It does not implement a branch from a common developed pre-policy economy. The project's model-scope document explicitly records the absence of empirical calibration and out-of-sample validation against a real economy. [C13] [C14]

**Why it matters.** Repeatability establishes what this program does under a configuration. Calibration, independent validation, and sensitivity analysis address whether its mechanisms and results support the intended economic interpretation. Mechanism validation and matching aggregate patterns are related but distinct tasks. [S06]

**Proposed scope.** Support both starting-regime experiments and interventions from a shared pre-policy snapshot. Pair exogenous disturbances across scenarios using recorded shock schedules or independently keyed random streams where appropriate. Record endogenous events separately: those are allowed to differ as policy changes the economy. Run multiple seeds and initial states; vary plausible behavioral and institutional assumptions. Choose reference data and validation targets for each claimed domain, reserving independent periods, statistics, or interventions for validation.

**Acceptance criteria.**

- An experiment saves model commit, configuration, initial state, policy change, timing, shock specification, execution mode, outcomes, and failures.
- Branches share the same recorded pre-intervention economy. Same-seed initialization is not mislabeled as snapshot branching.
- Reports show per-run differences, uncertainty, and distributional effects, with short-run and longer-run windows chosen for the mechanism being studied.
- Sensitivity results distinguish random-run variation from uncertainty about behavioral assumptions and model structure.
- A policy ranking that changes under reasonable assumptions is reported as conditional or unstable.
- Forecasting or LLM success inside EcoSim is evaluated separately from the economic validity of EcoSim itself.

## 5. Later extensions tied to specific questions

These are candidates for later work, not prerequisites for every experiment. They need their own scoped research and calibration before implementation claims are made.

| ID | Candidate addition | Relevant gap or boundary | Question it would enable | Verification direction |
|---|---|---|---|---|
| X01 | Demographics and household composition | Age exists as a field, but the inspected tick lifecycle does not model population aging, births, deaths, household formation, or retirement; birth_rate is a legacy stored field. [C15] | Aging populations, pensions, childcare, and long-run healthcare financing | Reconcile population flows, dependents, participation, income, and program costs; define mortality and health outcomes before using them |
| X02 | Trade, imported inputs, and external finance | The core model is a small domestic sector structure without a developed external-sector account. [C14] [C18] | Imported inflation, tariffs, industrial policy, supply disruption, and capital flows | Identify external counterparties; reconcile imports/exports and financial flows; connect input prices to production. [S10] |
| X03 | Housing delivery, land constraints, and regional access | Rentals, repairs, expansion, and mortgages already exist; these do not establish a calibrated land/planning or regional housing model. [C19] | Rent regulation, construction subsidies, zoning, commuting, and housing access | Compare declared supply constraints and completion lags; report rents, displacement, vacancies, construction, and access |
| X04 | Broader labor institutions | Job matching and medical training exist; the core household labor plan has no general hours choice or collective-bargaining institution. [C04] | Working-time policy, childcare-related participation, bargaining, and job guarantees | Track hours, participation, take-home income, employer costs, and job quality consistently |
| X05 | Environmental costs and resource limits | The proposed input sector in P06 creates a place to represent energy/resource use; environmental outcomes are not established by current model evidence | Carbon pricing, energy transitions, pollution-health effects, and resource scarcity | Add explicit physical quantities, damages, abatement costs, and lagged effects, with dedicated empirical sources |

For X01–X05, the economic question motivates the extension; this table does not assert a particular real-world effect size or policy direction.

## 6. What a reviewable policy experiment should contain

Before a comparison is run, record the following in its scenario definition:

| Field | Required explanation |
|---|---|
| Question | The specific policy or institution being compared |
| Baseline | Tax schedule, benefits, institutions, financing rules, monetary setup, and service arrangements |
| Intervention | Exact parameters/rules changed, effective date, and whether changes are temporary or permanent |
| Starting conditions | Snapshot or initialization recipe, population, firms, ownership, balance sheets, and pre-policy history |
| Common conditions | What is held fixed, including agent capabilities and exogenous shocks |
| Allowed responses | Which prices, wages, budgets, financing flows, quantities, and decisions may adjust |
| Horizon | Tick length, warmup, transition window, and evaluation windows appropriate to the mechanism |
| Outcomes | Real output/income, distribution, unmet needs, health, employment/hours, fiscal and financial outcomes |
| Uncertainty | Seeds, initial-state variation, behavioral parameter ranges, and alternative institutional assumptions |
| Evidence | Commit, full configuration, execution mode, environment versions, raw trajectories, failures, and analysis code |
| Interpretation | Which findings are robust within the model, which are assumption-sensitive, and which external claims remain unsupported |

For the motivating tax comparison, retain progressive taxation and define the lower- and higher-tax schedules, then state whether extra revenue funds services, reduces debt, or follows another specified rule. For healthcare, include total household financing burdens and provider capacity. For inflation, distinguish an imposed price-path stress test from a target pursued through monetary policy. For system comparisons, publish the full institution configuration.

An optional overall welfare score must show its weights and allow readers to inspect its component outcomes. A score's ethical or distributional weights are part of the evaluation choice, not a discovered economic fact.

## 7. Reproduced evidence register

These are bounded diagnostics of the audited implementation. They are not estimates of policy efficacy. The supplied probes reproduce current problems; after a correction, their expected observations should be re-audited rather than preserved as desired regression behavior.

| ID | Setup | Recorded observation | Supported conclusion | Does not establish |
|---|---|---|---|---|
| E01 | Existing large-economy factory; 200 households; 2 requested firms per category; 52 ticks; seeds 42 and 77; targets 0.02 versus 0.15; LLM control disabled | 52/52 observed-state fingerprints identical for each paired seed | No effect of changing this target on the recorded state in these runs; consistent with source finding C08 | That prices never change, all internal state was compared, or a functioning monetary policy would be ineffective |
| E02 | New government with cash 0; fiscal settlement pays transfers of 1,000 with zero tax receipts | Cash −1,000; public_debt attribute absent; annualized debt/GDP helper returns 0 | Deficit settlement and the public-debt helper are not connected by a debt stock | That every treasury deficit must use bond financing |
| E03 | Seed 42; 200-household economy; directly enable one entry opportunity after warmup; treasury and bank cash 0 | One entrant; cash 20,041.424449; aggregate cash rises equally; household cash unchanged; no entrant bank/government debt | The fallback startup path can introduce unfunded cash | How large its contribution is in a typical full policy run |
| E04 | 200 households each with cash 100; one holds deposit 1,000,000; bank liability and cash set consistently | Reported Gini 0; reported wealth p99 100 | The reported wealth measures ignore those deposits | That the synthetic setup is an empirical wealth distribution |
| E05 | Same fixed household cash of 100; change benefit preset low to high without a tick | Poverty threshold 50 → 150; poverty count 0 → 200 | The poverty measure's definition changes with the benefit preset | That the higher benefit worsens anyone's actual resources |

The E01 fingerprints include economic metrics and serialized household, firm, and bank records. They deliberately exclude the government configuration object containing the changed target. Diagnostic infinities are normalized to strings for stable comparison. Direct inspection of C08 supplies the separate source evidence for the missing consumer.

## 8. Reproduce the focused checks

Run this from the repository root in an environment with the project's backend dependencies installed. The checks use Python 3.11 and were verified with NumPy 2.3.5. They run in memory, make no LLM/provider calls, and do not edit the economic engine or write a warehouse. Python's `-B` option suppresses bytecode writes.

First inspect the version rather than overwriting any working tree:

```bash
git rev-parse HEAD
git diff -- backend/agents.py backend/economy.py backend/config.py backend/server.py backend/fiscal_guards.py backend/tools/runners/run_large_simulation.py
```

If the relevant source differs from the audited commit, record that difference and treat the observations as requiring a new audit. The following code prints JSON records and checks the five observations; it is an audit reproduction snippet, not a proposed production test suite.

```bash
PYTHONPATH=backend python3 -B - <<'PY'
import contextlib
import hashlib
import io
import json
import math
import platform
import random

import numpy as np

from agents import GovernmentAgent
from config import clone_config, use_config
from fiscal_guards import annualized_debt_to_gdp
from tools.runners.run_large_simulation import create_large_economy


def normalized(value):
    if isinstance(value, dict):
        return {str(k): normalized(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def replay(seed, inflation_target):
    cfg = clone_config()
    cfg.random_seed = seed
    cfg.llm.enable_llm_government = False
    with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        np.random.seed(seed)
        eco = create_large_economy(200, 2)
        eco.government.target_inflation_rate = inflation_target
        fingerprints = []
        for _ in range(52):
            eco.step()
            observed_state = {
                "metrics": eco.get_economic_metrics(),
                "households": [h.to_dict() for h in eco.households],
                "firms": [f.to_dict() for f in eco.firms],
                "bank": eco.bank.to_dict() if eco.bank else None,
            }
            encoded = json.dumps(
                normalized(observed_state), sort_keys=True,
                default=str, allow_nan=False,
            ).encode()
            fingerprints.append(hashlib.sha256(encoded).hexdigest())
        return fingerprints


print(json.dumps({"environment": {
    "python": platform.python_version(), "numpy": np.__version__,
}}), flush=True)

for seed in (42, 77):
    low, high = replay(seed, 0.02), replay(seed, 0.15)
    equal_ticks = sum(a == b for a, b in zip(low, high))
    print(json.dumps({
        "evidence": "E01", "seed": seed, "ticks": 52,
        "identical_observed_ticks": equal_ticks,
    }), flush=True)
    assert low == high, "E01 changed: re-audit inflation transmission"

gov = GovernmentAgent(cash_balance=0.0)
gov.apply_fiscal_results(0.0, 0.0, 1000.0)
debt_ratio = annualized_debt_to_gdp(gov, 1000.0)
print(json.dumps({
    "evidence": "E02", "government_cash": gov.cash_balance,
    "public_debt_attribute_exists": hasattr(gov, "public_debt"),
    "annualized_debt_to_gdp": debt_ratio,
}), flush=True)
assert gov.cash_balance == -1000.0
assert not hasattr(gov, "public_debt") and debt_ratio == 0.0

cfg = clone_config()
cfg.random_seed = 42
cfg.llm.enable_llm_government = False
with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
    random.seed(42)
    np.random.seed(42)
    eco = create_large_economy(200, 2)
    eco.in_warmup = False
    eco.current_tick = 20
    eco.target_total_firms = len(eco.firms) + len(eco.queued_firms) + 1
    eco.government.cash_balance = 0.0
    eco.bank.cash_reserves = 0.0

    def cash_total():
        return (
            sum(h.cash_balance for h in eco.households)
            + sum(f.cash_balance for f in eco.firms + eco.queued_firms)
            + eco.government.cash_balance + eco.bank.cash_reserves
            + eco.misc_firm_revenue
        )

    before = cash_total()
    firm_count_before = len(eco.firms)
    household_cash_before = sum(h.cash_balance for h in eco.households)
    eco._maybe_create_new_firms()
    entrant = eco.firms[-1]
    cash_increase = cash_total() - before
    household_change = (
        sum(h.cash_balance for h in eco.households) - household_cash_before
    )
    entry_record = {
        "evidence": "E03", "new_firms": len(eco.firms) - firm_count_before,
        "new_firm_cash": round(entrant.cash_balance, 6),
        "aggregate_cash_increase": round(cash_increase, 6),
        "household_cash_change": household_change,
        "government_cash": eco.government.cash_balance,
        "bank_cash": eco.bank.cash_reserves,
        "new_firm_bank_debt": entrant.bank_loan_remaining,
        "new_firm_government_debt": entrant.government_loan_remaining,
    }
    assert len(eco.firms) - firm_count_before == 1
    assert entrant.cash_balance > 0.0
    assert math.isclose(cash_increase, entrant.cash_balance, abs_tol=1e-6)
    assert household_change == 0.0
    assert eco.government.cash_balance == eco.bank.cash_reserves == 0.0
    assert entrant.bank_loan_remaining == entrant.government_loan_remaining == 0.0

    for household in eco.households:
        household.cash_balance = 100.0
        household.bank_deposit = 0.0
    eco.households[0].bank_deposit = 1_000_000.0
    eco.bank.total_deposits = 1_000_000.0
    eco.bank.cash_reserves = 1_000_000.0
    metrics = eco.get_economic_metrics()
    inequality_record = {
        "evidence": "E04", "households": len(eco.households),
        "equal_cash_balance": 100.0, "one_household_deposit": 1_000_000.0,
        "reported_gini": metrics["gini_coefficient"],
        "reported_wealth_p99": metrics["wealth_p99"],
    }
    assert metrics["gini_coefficient"] == 0.0
    assert metrics["wealth_p99"] == 100.0

    poverty = {}
    for level in ("low", "high"):
        eco.government.set_lever("benefit_level", level)
        metrics = eco.get_economic_metrics()
        poverty[level] = {
            "threshold": eco.government.min_cash_threshold,
            "households_below_poverty": metrics["households_below_poverty"],
        }
    assert poverty["low"]["households_below_poverty"] == 0
    assert poverty["high"]["households_below_poverty"] == 200
    assert all(h.cash_balance == 100.0 for h in eco.households)

print(json.dumps(entry_record), flush=True)
print(json.dumps(inequality_record), flush=True)
print(json.dumps({"evidence": "E05", "results": poverty}), flush=True)
PY
```

## 9. Source catalog

### Economic references

Sources were consulted on 2026-09-21. Their role is stated below so that a reviewer can distinguish economic support from the particular implementation proposed here. No source establishes that EcoSim's current numerical parameters are calibrated.

| ID | Source | What it supports here |
|---|---|---|
| S01 | [McLeay, Radia, and Thomas, Bank of England, *Money creation in the modern economy* (2014)][S01] | The distinction between deposit money, lending, balance-sheet claims, and central-bank policy; not a requirement to impose fixed aggregate money |
| S02 | [U.S. BEA, *How do I use chain-type indexes or chained-dollar measures?*][S02] | Separating changes in real activity from price changes |
| S03 | [U.S. BLS, *Consumer Price Index Frequently Asked Questions*][S03] | Defined consumer baskets, expenditure weights, and differences in household inflation experience |
| S04 | [WHO, *Health financing*][S04] | Revenue raising, pooling, purchasing, coverage, cost sharing, and workforce capacity as distinct health-system functions |
| S05 | [Jahan and Mahmud, IMF Finance & Development, *What Is Capitalism?*][S05] | Ownership, profit, markets, and institutional variation; used for distinctions, not as a predetermined ranking of systems |
| S06 | [Tieleman, *Towards a Validation Methodology for Macroeconomic Agent-Based Models*, published online 2021, journal volume 2022][S06] | Distinguishing mechanism validation, aggregate targets, calibration, and sensitivity to assumptions |
| S07 | [Tenreyro, *Monetary policy in the face of supply shocks: the role of inflation expectations*, ECB Forum paper (2023)][S07] | Why shock type, persistence, expectations, and second-round effects matter to monetary-policy assessment |
| S08 | [Horton and El-Ganainy, IMF Finance & Development, *Fiscal Policy: Taking and Giving Away*][S08] | Spending/tax composition, financing constraints, economic capacity, and fiscal tradeoffs |
| S09 | [Kaplan, Violante, and Weidner, *The Wealthy Hand-to-Mouth*, Brookings Papers on Economic Activity (2014)][S09] | Why liquid resources and illiquid wealth must be distinguished when modeling consumption responses |
| S10 | [U.S. BEA, *Input-Output Accounts*][S10] | Production relationships among industries and commodities; a reference structure for a deliberately smaller simulated production network |

### Commit-pinned code references

Paths and symbols make the evidence searchable locally. Links identify the audited version rather than a moving main branch. Recheck symbols and call sites before implementing against a newer version.

| ID | File and owning behavior | Evidence link |
|---|---|---|
| C01 | backend/economy.py — _maybe_create_new_firms, funding selection and entrant creation | [Pinned source][C01] |
| C02 | backend/agents.py — GovernmentAgent fields and apply_fiscal_results; backend/fiscal_guards.py — annualized_debt_to_gdp | [Government fields][C02], [settlement][C02a], [debt helper][C02b] |
| C03 | backend/economy.py — get_economic_metrics, cash-only wealth, prices, GDP, and benefit-linked poverty | [Wealth][C03], [prices/output][C03a], [poverty][C03b] |
| C04 | backend/economy.py — _batch_plan_consumption and household settlement; backend/agents.py — plan_labor_supply; backend/config.py — income-source spending parameters | [Consumption][C04], [settlement][C04a], [labor][C04b], [parameters][C04c], [warmup net-wage calculation][C04d] |
| C05 | backend/economy.py — _handle_firm_exits; backend/agents.py — _destabilized_production_plan and plan_wage | [Baseline protection][C05], [production switch][C05a], [wage switch][C05b] |
| C06 | backend/agents.py — invest_in_infrastructure; backend/economy.py — production costs and miscellaneous spending distribution | [Infrastructure][C06], [production costs][C06a], [payment distribution][C06b] |
| C07 | backend/economy.py — _update_budget_pressure; backend/agents.py — make_investments | [Fiscal penalty][C07], [operation called bond purchases][C07a] |
| C08 | backend/agents.py — target_inflation_rate legacy field; backend/server.py — inflationRate assignment; backend/economy.py — policy-update path | [Stored field][C08], [server assignment][C08a], [policy path][C08b] |
| C09 | backend/agents.py — BankAgent, lendable_cash, originate_loan, collect_repayment | [Bank and reserve constraint][C09], [loan accounting][C09a] |
| C10 | backend/server.py — decision-feature price basket and inflation calculation | [Pinned source][C10] |
| C11 | backend/economy.py — _process_healthcare_services; backend/policy_schema.py — subsidy levels | [Healthcare processing][C11], [subsidy options][C11a] |
| C12 | backend/policy_schema.py — government action surface | [Pinned source][C12] |
| C13 | policy_forecasting/sweep/wrapper.py — run_single_policy and policy timing | [Pinned source][C13] |
| C14 | docs/MODEL_SCOPE.md — intended use, empirical limitations, and scope stability | [Pinned source][C14] |
| C15 | backend/agents.py — household age/can_work and legacy birth_rate; backend/economy.py — Economy.step lifecycle | [Household fields][C15], [work eligibility][C15a], [legacy fields][C08], [tick lifecycle][C15b] |
| C16 | backend/tools/runners/run_large_simulation.py — create_large_economy used by the probes | [Pinned source][C16] |
| C17 | backend/config.py — configuration defaults used by the audited model | [Pinned source][C17] |
| C18 | backend/agents.py — _capacity_for_workers, plan_capital_investment, apply_production_and_costs | [Production function][C18], [investment][C18a], [depreciation][C18b] |
| C19 | backend/economy.py — rental clearing and housing mortgage/expansion finance | [Rental market][C19], [housing finance][C19a] |
| C20 | docs/DESIGN_DECISIONS.md — existing architectural reasons to preserve or deliberately revisit | [Pinned source][C20] |

## 10. Review and maintenance contract

For the proposed later phase of delegating different economic agents to separate coding agents, use the [shared economic-agent working contract](ECONOMIC_AGENT_WORKING_CONTRACT.md). It records Ayman's requirements to preserve each agent's base, ground additions in realistic scenarios, and avoid substantial simulation slowdown, together with proposed accounting laws, integration ownership, worker handoffs, and performance checks.

For each P or X item, a reviewer should record: **accept, revise, defer, or reject**, with the item ID, reason, and any conflicting evidence. The immediate review decisions are which comparison to implement first, which financing/institutional choices it requires, and which outcomes would make that comparison useful. Unsettled choices are not permission to invent a policy winner.

When work is later authorized, keep each change tied to a selected item and its acceptance criteria. Capture baseline evidence first, update the affected model/consumer surfaces, and record the new commit and verification results. Preserve the original observation as history and mark it superseded when the mechanism changes.

This proposal does not override the existing decision to keep the economic baseline stable. Acceptance of a workstream and authorization to implement it should be recorded explicitly in the development task. Existing design choices should be revisited with their original rationale in view. [C14] [C20]

[S01]: https://www.bankofengland.co.uk/quarterly-bulletin/2014/q1/money-creation-in-the-modern-economy
[S02]: https://www.bea.gov/help/faq/79
[S03]: https://www.bls.gov/cpi/questions-and-answers.htm
[S04]: https://www.who.int/health-topics/health-financing
[S05]: https://www.imf.org/en/publications/fandd/issues/series/back-to-basics/capitalism
[S06]: https://link.springer.com/article/10.1007/s10614-021-10191-w
[S07]: https://www.ecb.europa.eu/press/conferences/ecbforum/shared/pdf/2023/Tenreyro_paper.pdf
[S08]: https://www.imf.org/en/publications/fandd/issues/series/back-to-basics/fiscal-policy
[S09]: https://www.brookings.edu/articles/the-wealthy-hand-to-mouth/
[S10]: https://www.bea.gov/data/industries/input-output-accounts-data
[C01]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L4591-L4835
[C02]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L6268-L6343
[C02a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L6962-L6996
[C02b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/fiscal_guards.py#L42-L48
[C03]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6973-L7003
[C03a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L7092-L7112
[C03b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L7294-L7298
[C04]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L789-L864
[C04a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L1192-L1220
[C04b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L1304-L1447
[C04c]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/config.py#L62-L75
[C04d]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L4271-L4325
[C05]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L4518-L4526
[C05a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L3364-L3385
[C05b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L4892-L4893
[C06]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L7027-L7053
[C06a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L1855-L1860
[C06b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6030-L6097
[C07]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6450-L6506
[C07a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L7122-L7164
[C08]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L6307-L6312
[C08a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/server.py#L2741-L2744
[C08b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6790-L6815
[C09]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L5801-L5870
[C09a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L5970-L6019
[C10]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/server.py#L923-L949
[C11]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L6242-L6418
[C11a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/policy_schema.py#L22-L32
[C12]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/policy_schema.py#L16-L40
[C13]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/policy_forecasting/sweep/wrapper.py#L180-L224
[C14]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/docs/MODEL_SCOPE.md
[C15]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L109-L136
[C15a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L1219-L1230
[C15b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L1405-L2110
[C16]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/tools/runners/run_large_simulation.py#L38-L286
[C17]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/config.py
[C18]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L2923-L2952
[C18a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L4419-L4469
[C18b]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/agents.py#L5215-L5276
[C19]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L5780-L6027
[C19a]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/backend/economy.py#L5134-L5250
[C20]: https://github.com/AymanCode/EcoSim/blob/4f693890b5f133c2c6c1dcbec9b1ec91ced97b46/docs/DESIGN_DECISIONS.md
