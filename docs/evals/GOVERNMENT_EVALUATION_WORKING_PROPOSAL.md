# EcoSim government evaluation: working proposal

**Date:** September 10, 2026

**Revised:** September 11, 2026, incorporating both audit passes and source checks of their conclusions.

**Status:** Discussion draft. This revision changes the plan only; it does not authorize implementation, simulations, model runs, score weights, or a final grading formula.

## 1. What this is trying to accomplish

Evaluate how well an LLM governs EcoSim: can its policies improve the economy and the conditions that let households improve their own lives?

The proposed work has three parts:

| Part | Direction under discussion | Purpose |
|---|---|---|
| Model access | An EcoSim MCP interface for Codex and Claude Code, with API access retained for providers such as Groq and OpenRouter. | Compare subscription-backed agents and other hosted models through a common government interface. |
| Policy freedom | Try four policy groups per decision, unrestricted jumps between valid presets, and tax changes anywhere within the permitted range. | Give models room to propose coordinated policies instead of enforcing gradualism in advance. |
| Measurement and grading | Verify existing measurements, preserve missing outcome data, then calculate grades outside the simulation. | Make the evidence reusable while the definition of a good government is still being debated. |

Initial experiments would likely use 1,000–2,000 households. Larger populations can be checked later; population scaling also changes firm composition, so 10,000 households is not simply ten copies of the same smaller economy.

This proposal complements the older [evaluation protocol](ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md). Its fixed weights and scoring gates are not adopted here. This document introduces a direction for review, not a replacement protocol.

The first priority is comparable runs and trustworthy measurements. Exploratory tests of four moves can precede a final grading system; claims about which model governs better require the comparison and measurement conditions below. A new debt model or a particular happiness weight is not a blanket prerequisite for exploration.

## 2. Reasoning behind the direction

- **Indirect influence still creates accountability.** Households already pursue housing, work, consumption, and some education. Government changes the resources and incentives under which they act; outcomes can therefore judge government contribution without requiring direct control over every household.
- **Different policy styles should be able to succeed.** Higher production with lower happiness should not automatically lose to a more balanced result. Equally, higher firm profit does not automatically establish a better economy: profit can increase through redistribution from wages rather than additional production.
- **Production is a promising common comparison.** Skills and wellbeing affect productivity in the code. However, capacity limits can hide their benefits, and aggregate output can overlook hardship among households outside employment.
- **Hardship has duration and severity.** A brief housing interruption differs from sustained homelessness; receiving almost enough food differs from receiving almost none. A final-tick snapshot misses both distinctions.
- **Efficient intervention deserves recognition.** Similar or better outcomes with fewer policy changes can demonstrate effective control. The bonus should not reward inactivity or conceal the cost of one very expensive intervention.
- **Score the simulated decisions, not provider speed.** Token generation speed and subscription interruptions should affect experiment duration, not the number of simulated weeks that pass before a policy takes effect.

## 3. Model access, timing, and independence

### Common interface

Both routes should use the same observation and policy-application logic:

- **MCP:** Codex or Claude Code observes EcoSim and submits policies through tools.
- **API:** An EcoSim controller supplies the same observations to a selected model and submits its response through the same application path.

MCP itself supplies neither inference nor subscription credits. Subscription-authenticated Codex and eligible Claude Code sessions use their included usage; direct provider calls follow that provider's billing or free-tier rules. Each experimental economy should have one active government controller. See [Codex authentication](https://learn.chatgpt.com/docs/auth) and [Claude Code subscription access](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan).

Both routes should receive the same declared observation payload, history window, policy knowledge, and decision opportunities. Apply the same retry and malformed-output rules, and bound tool use and response budgets explicitly. A tool endpoint must expose the allowed report, not the advisor's internal raw state. Archive the actual inputs, responses, attempts, and applied changes.

**Caveat:** a conversational agent is not equivalent to a single API completion. Where possible, compare the same model through both routes before comparing different models across routes. The size of the wrapper effect is unknown; one paired comparison cannot establish it for every model. Report a full agent-configuration comparison wherever model identity, reasoning budget, tools, or history cannot be matched.

### Fixed simulation timing

The standalone government runner already waits for the advisor at each scheduled decision tick. Reuse that pausing loop for the initial MCP route. The live server's background scheduler can skip decision opportunities while inference is pending and should not be reused unchanged for this evaluation.

The proposed initial timing is immediate observation, pause, and application. A fixed simulated delay remains a later experiment:

| Option | Reason to try it | Caveat |
|---|---|---|
| Pause immediately at observation, then apply. | Already supported by the standalone runner and gives a clear initial comparison. | Removes information-to-action delay from the challenge. |
| Apply after a fixed simulated delay. | Tests decisions made using somewhat older information without penalizing slow inference. | Adds difficulty and requires consistent snapshot-based follow-up queries. |

For a delayed application, a fast response waits for the boundary and a slow response pauses simulation progress there. The “quarter-way” idea remains unresolved; neither a quarter-period delay nor a delayed start is agreed.

Record provider interruptions separately from policy outcomes, and retain malformed decisions and invalid actions under a declared failure rule. Never silently replace failed trials: a rerun is an additional sample unless the original is explicitly classified as an infrastructure failure. Token speed affects wall-clock duration, not simulated decision opportunities or the economic grade.

### Independent runs

Disable cross-run memory reading/writing and other-chat retrieval for evaluation sessions. A fresh chat alone does not ensure this: Codex has local memory controls, and Claude Code can share project memory across worktrees. Preserve a declared history within each run so models can respond to their own earlier decisions. See [Codex memories](https://learn.chatgpt.com/docs/customization/memories) and [Claude Code memory](https://code.claude.com/docs/en/memory).

Use a fresh working directory and enforce access restrictions on source code, prior-result files, persistent instructions, other-chat tools, and unrelated services. An empty directory alone does not prevent access elsewhere. Give every controller the same policy reference; unrestricted repository access would also expose hidden mechanics and previous experiments. Record effective permissions and memory settings rather than relying only on “ignore previous runs.”

## 4. Policy freedom to try

| Candidate change | Why | What remains to review |
|---|---|---|
| Two to four substantive policy groups per decision. | Allows coordinated revenue, support, and investment decisions. | Four is still arbitrary; compare with unlimited later. Linked bailout fields count as one group. |
| Allow any valid preset destination. | Permits a direct response such as low benefits to crisis benefits. | Larger jumps may destabilize the economy; that consequence can be part of the experiment. |
| Remove the five-percentage-point tax movement limit. | Lets the model choose the scale of its response. | Final tax bounds remain a separate decision. |
| Reconsider fiscal-stress and unemployment vetoes. | These currently make economic judgments before the model can act. | Which vetoes to remove has not been decided. Funding mechanics and valid accounting are distinct from policy advice. |
| Later: numerical amounts instead of presets. | Allows precise benefit amounts, budgets, and wage floors. | Larger refactor: preset translation currently owns those values and can overwrite direct changes. |

Keep valid types, real targets, coherent linked settings, and auditable execution. Apply a policy package together; avoid quietly evaluating an unintended partial package. The movement restrictions live in the prompt, sanitizer, and suggested-action mask, with shared constants in the policy schema. `set_lever` checks final ranges and valid options, not movement size. Widening moves is therefore smaller work than replacing the lever system; package consistency and application logging still need verification.

Start exploratory comparisons with the fiscal veto held constant while testing two versus four groups and preset/tax jumps as declared variants. Removing fiscal or unemployment vetoes is a separate experiment, so its effects are distinguishable from additional moves. Fiscal conclusions remain limited by the current financing model.

## 5. What could count toward a grade

### Production and GDP

| Measurement | Why it matters | Limitation |
|---|---|---|
| Nominal GDP | Shows production valued at current prices. | Inflation can resemble growth; the current revenue sum is not complete GDP accounting. |
| Real output per household | Compares production across policies and population sizes using consistent prices. | Different sectors need common valuation; raw food units and medical visits cannot simply be added. |
| Net domestic product | Deducts depreciation to expose gains achieved by wearing down capital. | Depends on credible depreciation and capital accounting. |
| Production, expenditure, and income accounting | These should reconcile and can reveal missing or duplicated flows. | They describe the same activity, so are not three independent scoring rewards. |

Transfers, loans, and financial-asset purchases are not themselves new production. Legitimate investment and inventory changes belong in accounting, but unwanted stockpiles should not automatically win the benchmark. A fixed-price output index is a practical first measurement; full GDP reconciliation is a separate project. [BEA accounting framework](https://www.bea.gov/resources/methodologies/nipa-handbook/pdf/chapter-02.pdf)

Existing sector records contain output units and mean prices, but those fields do not yet define comparable activity across sectors. Healthcare's generic production field is zero, while services production can represent unused capacity. Reuse recorded quantities where their meaning is valid; use completed visits for healthcare and verify occupied housing services and delivered services separately. Keep production, consumption, inventory changes, and unused capacity distinguishable. Freeze reference prices from a common scenario reference before comparing policies, rather than choosing a separate base for each model.

Do not subtract all government-funded revenue. A $100 visit paid with $80 from a household and $20 from government is still one delivered service; the current healthcare settlement records the visit price once. Audit each flow for actual activity and double counting. Also avoid treating the legacy chooser's hardcoded zero `inflation_rate` as measured price stability.

### Household outcomes and tradeoffs

| Measurement | Why it matters | Limitation |
|---|---|---|
| Homeless exposure and consecutive duration | Housing failure should count against outcomes; duration captures persistence. | Retain affordability versus unavailable-supply diagnostics and compare matched scenarios. |
| Food shortfall | Captures both the prevalence and depth of inadequate consumption. | Subsistence and health-supporting food thresholds differ. |
| Poverty rate, gap, and duration | Measures how many households cannot cover essentials, how far short they are, and for how long. | The basket and resource definition remain open; distinguish income inadequacy from lack of savings. |
| Gini and bottom-group purchasing power | Shows who receives gains and whether disadvantaged households improve. | Gini is not poverty. Current Gini uses cash only; distinguish income inequality from financial wealth, and declare treatment of deposits, debt, and negative balances. |
| Employment, skills, health, happiness | Shows whether households can improve and sustain productive activity. | These overlap with production and each other; avoid automatic double rewards. Unemployment definitions must distinguish inability to work. |
| Fiscal condition and capital | Helps assess whether gains can continue after the scoring window. | Current deficit penalties do not model debt repayment. Treasury cash and a zero debt indicator cannot establish sustainability. |
| Policy-change count | Can recognize effective governance with fewer interventions. | Compare outcomes first and record resource cost separately; counting MCP calls would be misleading. |

The basket should be independent of policy choices. A starting possibility is fixed food requirements plus housing access/cost; healthcare should reflect actual need rather than an identical visit allowance for everyone. Gini supplements this assessment rather than replacing it. [World Bank poverty and inequality concepts](https://datatopics.worldbank.org/world-development-indicators/themes/poverty-and-inequality.html)

No final tradeoff weights are selected. If one government produces more but leaves greater deprivation, a single ranking will express chosen priorities. “Balanced” is not automatically better. Whether happiness gets independent weight or primarily matters through other outcomes is explicitly open.

Social spending buys a capped, decaying happiness benefit and routes its spending through the Misc redistribution pool, after a tax skim. Its effects therefore include cash reaching a small beneficiary group. Audit both effects, their costs, and overlap with productivity; direct policy influence is not automatically an exploit, and choosing production alone would also impose a grading preference.

### Fiscal interpretation still to choose

`public_debt` has no tracked balance. The fiscal-pressure penalty scales infrastructure and technology gains only, down to a floor of 0.5; those outlays, social spending, and bond purchases require cash. Flat unemployment benefits can continue despite negative cash. They are not the only ungated outlay: the temporary post-warmup stimulus also deducts cash without a treasury check. These mechanisms do not establish a borrowing or repayment system.

Threshold top-ups require unused transfer budget. That budget starts at zero in the default standalone runs, and its sizing routine is disabled in the LLM and control arms, so those runs pay no threshold top-ups. Changing `benefit_level` still changes the flat payment and the reported poverty threshold. A controller taking over a run with a pre-existing budget may behave differently; record the starting budget as well as the policy settings.

Automatic bond purchases divert a fraction of treasury surplus into the same redistribution pool. They reduce cash retention but do not make accumulation impossible. Interpret cash and inequality alongside this automatic rule, its returned tax skim, and actual recipient flows; match the rule across comparison arms. The labels “bonds” and “Misc firm” alone do not establish conventional asset or production accounting.

Initial exploration can retain those mechanics and report cash, flows, fiscal pressure, and unmet spending separately, without claiming realistic debt sustainability. Before a sustainability grade or a strong claim about unrestricted deficit spending, choose an explicit interpretation: retain the simplified model with limited claims, add financing/repayment mechanics, or evaluate a declared terminal fiscal adjustment. Each choice changes incentives and needs sensitivity checks. Adding interest alone would not solve unlimited unpaid financing if interest can also accumulate without consequence.

## 6. Minimal additions to collect useful evidence

First map each required quantity to its current field, meaning, tick boundary, and persistence path. Then extend a common completed-tick export only where evidence is missing; grade afterward. Existing warehouse rows are reusable infrastructure, but the selected standalone/MCP runner must actually export them.

| Addition | Preserve | Why add it / caveat to audit |
|---|---|---|
| Hardship histories | Household ID, rental status, food consumed and requirements, healthcare need/access, work status. | Enables exposure, severity, transitions, and consecutive spells. Resolve differences between existing housing flags and align current/previous-tick food fields. |
| Household resource records | Wages, benefits, stimulus, `redistribution`, other ledger flows, cash, deposits, debt balances/payments, taxes, rent, essential purchases, and beneficiary membership. | Keep redistribution distinct and record its receipt tick. It mixes several funding sources; a ledger total alone cannot identify bond-funded income. Reconcile bank/other entries; borrowing and withdrawals are not income. |
| Output and use | Sector production, sales, inventories, food consumed, housing services, completed healthcare and services. | Separates real activity from prices and unused supply. Capacity, production, and delivered services need explicit definitions. |
| Household progress | Skills, health, work and resource measures for the same IDs over time. | Household IDs/population are already fixed. Freeze membership only for derived starting groups, such as the initial bottom quintile, when measuring mobility. |
| Existing fiscal and policy evidence | Requested, rejected, corrected and applied changes; spending by source, cash, capital, transfer budget, bond purchases, Misc tax skim/pool balance, timing, and grounding. | Reconcile gross outlays, tax returned to treasury, and later payouts. Preserve the pending pool at the run boundary. Keep unavailable debt distinct from zero and grounding as a diagnostic. |
| Run and measurement manifest | Code/config versions, seed, population, baseline, model, permissions, memory settings, observation rules, timing, reference prices and metric definitions. | Makes comparisons and later regrading interpretable. A seed alone does not freeze the entire experiment. |

Existing household snapshots normally record tick 1 and every fifth tick. `TrackedHouseholdHistory` already captures a narrower subset every tick; extending that pattern to all evaluation households is a candidate, with missing hardship/resource fields added. Reuse sector, firm, healthcare-event, and decision records where suitable. Batch writes and measure overhead later; cost at 1,000–2,000 households is unmeasured. Recording must not change random draws, household behavior, or simulation ordering.

For example:

`homeless exposure = sum of homeless households over scored ticks / total household-ticks`

Ten households homeless throughout 100 ticks in a 1,000-household run gives 1% exposure. Tracking individual spells distinguishes this from the same exposure spread across short episodes. Declared warmup and scoring windows determine which ticks count.

These records would support many new grades, not every future question. New baskets or GDP methods may still require quantities or flows that were not captured.

## 7. Revised work plan

These are proposed future steps, not authorization to implement or run them.

| Order | Work | Why / completion evidence |
|---|---|---|
| 1 | Define comparable runs: one controller, shared mechanics, common observation/history, retries, timing, starting policies, and transfer budget. Specify unchanged-policy and same-information scripted arms. | Declare backstop, stimulus, stabilizers, transfer-budget sizing, automatic bond purchases, and beneficiary selection/growth for every arm. A controller flag must not silently select different benefit administration. |
| 2 | Audit existing metric definitions and exports. Resolve poverty thresholds, cash-only inequality, output versus delivered services, and misleading debt/inflation labels. | A column's name does not establish its meaning. Produce a field map identifying what can already be graded and what remains unavailable. |
| 3 | Add only missing completed-tick evidence, starting with household hardship and resources. | Reuse existing records before building new machinery. Check tick alignment, accounting, export coverage, and later measure overhead. |
| 4 | Add MCP around the pausing loop and retain the API route through the same contract. Give both the same accurate policy reference, then pilot the same model through both where feasible. | Explain whether top-ups operate, how bonds/redistribution work, and how spending affects capacity. Verify timing, isolation, and budgets; report remaining wrapper differences without assuming their size. |
| 5 | Explore four groups and larger valid jumps against the existing restrictions, initially holding fiscal vetoes constant. | Separate freedom changes from changes to fiscal mechanics. Inspect outcome paths, failures, and actual policy changes; these are exploratory comparisons. |
| 6 | Use development runs to evaluate baskets, fiscal interpretations, happiness tradeoffs, and an intervention-efficiency bonus. | Compare alternative weights and definitions before choosing a headline grade. Freeze the chosen scorer and failure rules before held-out evaluation. |
| 7 | Evaluate on held-out scenarios with predeclared seeds, repeats, run lengths, and uncertainty reporting. | Repeated model trials and matched scenarios support stronger claims. Insufficient replication remains exploratory; any later scorer revision needs a new confirmatory evaluation. |

An unchanged-policy arm holds the starting settings while retaining the same execution mechanics. A scripted comparator should consume the same allowed observations at the same decision cadence and use the same action contract. A direct-metric script and the existing `no_government` scenario can remain separately labeled diagnostics. Preserve the older protocol's information-access classification and failure provenance without adopting its score weights.

Keep automatic stimulus, bond purchases, and other support rules identical across comparable arms. A common pre-control warmup can include these flows, or the relevant mechanism can be disabled in every arm. Merely excluding the payout ticks from scoring does not remove later effects. Retain full-population inequality and report beneficiary/non-beneficiary outcomes separately; deleting recipients or subtracting their receipts does not reconstruct a world without the transfers.

Decide whether threshold top-ups are part of the intended benefit system. If so, run transfer-budget sizing independently of controller identity in every comparison arm. Despite its name, the current `_adjust_government_policy` path only calls that sizing routine; it does not choose taxes or benefit presets. Disabling it to prevent a second policymaker currently disables administration instead. Sections 9.1 and 9.6 retain the source evidence.

At tick 15 followed by 26-tick intervals, a 200-tick run offers eight decisions. Intervention counts are coarse, and long-term consequences need a declared follow-up window. At `high`, each funded infrastructure outlay adds 0.01 times spending efficiency to its multiplier; this is an additive gain, not guaranteed 1% output growth. Grade realized activity rather than the uncapped multiplier, and inspect capacity limits. Specify seeds, repeats, ticks, and usage/response budgets before results; subscription capacity is provider-dependent.

Compare paths and ending states. With a matched household list, firm sampling can change the subsequent health draws on supply-shock ticks when firm counts differ. The stream resets each tick; its 3% supply-shock probability is an opportunity for this divergence, not a measured divergence rate or a bound on outcome differences. Identical draws can still cause different realized cash/health changes through clipping, and changed states persist. Keep shock-stream isolation optional until exact draw matching is needed. Initial scenarios can vary supported configuration and seeds; a typed scheduled-shock layer would be additional work.

## 8. Questions for the caveat audit

- What exact minimum basket represents deprivation, and which resources can satisfy it?
- Should happiness matter independently of production, health, and access to essentials?
- How much extra production can compensate for additional hardship, if any?
- Which quantities can support a credible real-output index today, and what GDP flows are missing?
- What fiscal claims are meaningful under the existing model, and would a financing model or terminal adjustment improve the experiment?
- Should every arm receive threshold-budget sizing and automatic bond purchases, and how should redistribution outcomes be reported?
- Which policy restrictions are experimental choices, and which are necessary execution mechanics?
- How much credit should fewer moves earn without rewarding inactivity or excessive resource use?
- What delay, run length, and scoring window give policies enough time to show consequences?
- Can the selected clients be isolated from other runs while receiving comparable within-run history?

## 9. Caveat audit findings and disposition

**Audit and revision date:** September 11, 2026. Source checks against `origin/main` at `4f69389`; no simulation or model run. The findings below incorporate corrections to the initial audit and a second source pass recorded in 9.6. They distinguish conditions for credible comparisons from optional changes to economic behavior; not every issue blocks exploratory policy-freedom tests.

### 9.1 Confirmed comparison and measurement gaps

| Finding | Plan response | Evidence |
|---|---|---|
| The poverty count uses the threshold set by the benefit preset. | Define scored deprivation independently of benefit policy. In default standalone LLM runs, threshold top-ups are inactive, but changing the preset still changes the flat payment and the count's threshold (9.6). | [Benefit mapping](../../backend/agents.py#L6470), [poverty count](../../backend/economy.py#L7295) |
| `public_debt` defaults to zero without an underlying tracked debt balance. Transfers can still drive cash negative. | Correct or mark unavailable the debt observation; retain cash/flow diagnostics. Choose fiscal interpretation before claiming sustainability. | [Transfers](../../backend/agents.py#L6754), [debt guard](../../backend/fiscal_guards.py#L42) |
| The path labeled “legacy chooser” currently only sizes transfer budgets. Its controller/stabilizer gate disables sizing under LLM control; bonds depend on the stabilizer flag. | Separate controller selection from benefit administration and surplus routing. Declare their effective rules across arms rather than suppressing the routine based on its name. | [Gate](../../backend/economy.py#L2080), [routine](../../backend/economy.py#L6784), [sizing](../../backend/agents.py#L6998), [bonds](../../backend/agents.py#L7122) |
| JSON repair retries depend on provider-name prefixes. | Use a common attempt/failure policy and archive every attempt before model ranking. | [Repair path](../../backend/tools/llm/llm_government.py#L2348) |
| Cash-only Gini omits deposits and debt. | Define income and financial-wealth measures separately. Cash plus deposits minus debt is a candidate financial balance, not complete household wealth; negative values need explicit handling. | [Distribution metrics](../../backend/economy.py#L6980) |
| Infrastructure, technology, social spending, bonds, and after-tax firm R&D enter a pool after a further 0–20% tax skim. Its net balance is paid equally to a small beneficiary set. Automatic bonds divert part of surplus when eligible. | Record redistribution, funding sources, skim, and payout timing. Match bond rules across arms; neither impossible treasury accumulation nor dominance of inequality has been established. Detail in 9.6. | [Routing](../../backend/economy.py#L1998), [payout and skim](../../backend/economy.py#L6053), [bond rule](../../backend/agents.py#L7122) |
| Transfer-budget sizing lives only in the gated legacy path, default standalone runs start at zero, and gap-filling is budget-capped. Top-ups therefore do not occur in those LLM/control runs. | Decide whether every arm receives sizing. Record initial budget; a takeover after earlier sizing can retain top-ups. With zero budget, `high`/`crisis` change flat payments but do not top up cash to their thresholds. | [Sizing call](../../backend/economy.py#L6807), [budget cap](../../backend/agents.py#L6811), [runner init](../../backend/tools/runners/run_large_simulation.py#L58) |

### 9.2 Existing controls are different experiments

| Arm | Verified behavior | Consequence |
|---|---|---|
| `no_government` | Zeroes major taxes and benefits; disables government stabilizers, backstop, and stimulus, so no bond purchases and no gap-filling. Its preset still sets a low minimum-wage floor, and baseline firms remain. | A reduced-government control, not unchanged starting policy or literal removal of every government mechanism. |
| `conservative_scripted` | Changes policies using current metrics and unmet-demand diagnostics; disables government stabilizers and the backstop, but retains stimulus. Never gap-fills to the benefit threshold and never buys bonds. | A direct-information scripted controller, not a fixed policy or the proposed same-information comparator. |
| LLM runner defaults | Retain the working-capital backstop, government execution mechanisms (bailouts, social programs, automatic bond purchases), and post-warmup stimulus. Gap-filling still never occurs because budget sizing is suppressed with the legacy chooser. | Backstop, stabilizer, and bond differences affect comparison with both controls; stimulus differs from `no_government` only. |

Evidence: [Control setup and policy rules](../../backend/tools/llm/run_government_control_compare.py#L101), [backstop default](../../backend/config.py#L700), [stimulus](../../backend/economy.py#L5667). Section 7 adds the missing unchanged-policy and same-information arms and requires matching effective mechanical settings. Omitting stimulus ticks alone does not remove the treatment difference. Identical lever settings do not imply identical benefit or surplus mechanics across arms; see 9.6.

### 9.3 MCP and reusable infrastructure

- **Observations and history:** lag/noise/coverage rules are a module constant. Repeated reads of the same tick do not provide fresh noise, but additional historical observations can improve inference. Version the rules, limit permitted history consistently, and expose the same allowed report through both routes. [Observation logic](../../backend/tools/llm/llm_government.py#L1589)
- **Isolation and budgets:** enforce memory, file, and tool permissions, not only a fresh directory. The API's 1,200-token default and a richer agent session are different configurations until budgets and access are declared; their relative effect is unmeasured. [API configuration](../../backend/config.py#L831)
- **Timing:** reuse the standalone runner's existing wait. The live scheduler needs adaptation before it can guarantee the same decision opportunities. [Standalone loop](../../backend/tools/llm/run_llm_government_test.py#L944), [live scheduler](../../backend/server.py#L1463)
- **Recording:** extend existing household trajectories and ledger categories, and reuse sector/firm/healthcare/decision rows. Verify coverage in the chosen runner rather than assuming an existing schema is already exported there. Keep the `redistribution` ledger category distinct from wages, benefits, and stimulus. [Warehouse models](../../backend/data/models.py), [household ledger](../../backend/agents.py#L369)
- **Policy freedom:** movement limits need coordinated prompt/sanitizer/mask updates; final-value validation already permits the wider destinations. Household IDs are fixed, so cohort freezing applies to derived groups only. [Lever validation](../../backend/agents.py#L6412)

### 9.4 Corrections to the initial audit's conclusions

| Initial conclusion (superseded) | Source-supported interpretation |
|---|---|
| Deficit spending has no cost; higher transfers necessarily improve all household outcomes. | The penalty scales infrastructure/technology gains only, with a floor of 0.5; those outlays, social spending, and bonds require cash. Flat benefits and temporary stimulus have no treasury gate; top-ups are budget-capped and inactive in the default runs. Financing and repayment remain missing; outcome improvements are not guaranteed. [Penalty](../../backend/economy.py#L6450), [investment](../../backend/agents.py#L7030), [transfers](../../backend/agents.py#L6754), [stimulus](../../backend/economy.py#L5667) |
| An independent happiness weight rewards an exploit. | Social spending has a cash cost and a capped, decaying benefit. Its valuation and realism remain choices; direct policy influence alone does not invalidate the outcome. Social spending is also a cash transfer to the beneficiary set through the Misc firm, not only a happiness multiplier (9.6). [Social programs](../../backend/agents.py#L7090) |
| Net all government-funded revenue out of the production measure. | Subsidized delivery can be real activity. Healthcare records the full visit price once; removing the subsidy share would discard part of that payment. Audit flows and quantity definitions instead. [Settlement](../../backend/economy.py#L6381) |
| Persisted sector output already supplies a complete fixed-price index. | The generic output field excludes healthcare throughput and can count unused service capacity. Existing records reduce implementation work but still require sector-specific interpretation. [Rollups](../../backend/tools/runners/run_large_simulation.py#L585), [production fields](../../backend/agents.py#L5235) |
| Household health shocks are policy-invariant with matched seeds. | Firm sampling can alter same-tick health draws when supply shocks fire and firm counts differ. Reseeding prevents random-stream carryover, not lasting state changes. Cash/health clipping can produce different realized effects even on ticks with identical draws; 3% is not a bound on those effects. [Shock sequence](../../backend/economy.py#L5711) |

### 9.5 Threats to validity to retain

- **Measurement incentives:** changing a poverty threshold, moving savings outside a cash-only measure, increasing unused capacity, or grading an uncapped multiplier such as `infrastructure_productivity` can improve a proxy without improving the intended outcome. Preserve underlying quantities so definitions can be challenged.
- **Limited fiscal horizon:** transfers and depleted capital may produce gains whose later consequences are absent or outside the scored window. Report those limits; choosing a fiscal adjustment changes the benchmark.
- **Information and wrapper differences:** extra source access, history, retries, tools, or reasoning budget can confound a model comparison. Disabling chat memory alone does not solve this.
- **Sampling and grading choices:** a few decisions/seeds give weak evidence about long-term control. Select weights on development runs, retain failures and grounding diagnostics, and freeze the evaluation protocol before held-out results.
- **Simulator dependence:** outcomes reflect coded household behavior and production limits. Efficient use of a legitimate mechanism can demonstrate control skill, while metric manipulation may reveal a faulty grader. Neither establishes real-world governing ability.

### 9.6 Second-pass findings

**Date:** September 11, 2026. Same commit; findings checked against source and incorporated into sections 5–7. No simulation or model run.

#### Misc-firm redistribution and automatic bond purchases

Infrastructure, technology, social spending, government bond purchases, and firm R&D after investment tax enter the Misc pool ([routing](../../backend/economy.py#L1998)). Each collection returns a seeded 0–20% tax skim to treasury; the remaining pool is paid equally as `redistribution` ([collection and payout](../../backend/economy.py#L6053)). Other flows, including housing repairs/construction, also enter the pool, so receipts are not all government-funded.

The beneficiary set is seeded at start and grows by one household per tick up to its cap ([selection](../../backend/economy.py#L6021), [growth](../../backend/economy.py#L6030)). Payout occurs before that tick's discretionary spending and R&D, so those later collections normally reach households the next tick. Preserve the pending pool at the scoring boundary. [Tick ordering](../../backend/economy.py#L1903)

With government stabilizers on, bond purchases automatically spend a fraction of eligible surplus each tick, including during warmup. [Bond rule](../../backend/agents.py#L7122)

| Quantity | Value |
|---|---|
| Starting treasury in the standalone runner | 3,000 per household |
| Automatic bond purchase | 12% of surplus above 50,000, per tick, once surplus exceeds 10,000 |
| Beneficiary households | 10 to 20 at start, plus one per tick, capped at 50 |
| Misc tax skim | 0–20% of each collected amount returns to treasury before redistribution |

At 1,000 households, starting treasury is 3 million. Applying the rule to that balance gives a 354,000 gross bond purchase; this is arithmetic at a hypothetical decision point, not a measured first-tick payment. Actual balances, taxes, other outlays, and the skim affect the path. Neither the amount paid over twenty ticks nor dominance of Gini is established by source review.

- The rule reduces cash retention, but revenue can still build treasury cash. Record the rule and flows rather than treating cash as non-accumulable.
- The beneficiary transfer can substantially change distribution. Both controls disable automatic bonds, though other Misc funding remains. The fixed reserve and beneficiary cap also scale differently from population-based starting treasury.
- Gross bond purchases enter fiscal-pressure spending. Reconcile the returned Misc tax skim with recorded revenue before interpreting this ratio as an exact deficit measure; its effect on early decisions is unmeasured. [Spending sum](../../backend/economy.py#L2051)
- The model sees a bond-purchases diagnostic, but the shared policy reference should explain the automatic rule, recipients, and payout timing. [Observation](../../backend/tools/llm/llm_government.py#L852)

Disposition: sections 6–7 now track redistribution and declare bond mechanics per arm. Keep full-population outcomes and add recipient-group diagnostics. Do not automatically exclude windfalls from inequality grading; removing recorded receipts is not a counterfactual because they also affect spending and later outcomes. Compare separately versioned scenarios if the mechanism itself is changed.

#### Transfer-budget sizing and inert thresholds

`adjust_policies` currently only sizes the transfer budget; its only production call is inside `_adjust_government_policy`. Despite the “legacy chooser” label, this path does not select tax or benefit settings. [Call](../../backend/economy.py#L6807), [implementation](../../backend/agents.py#L6998)

The LLM flag suppresses that call, and both controls disable government stabilizers. The standalone factory starts the budget at zero; top-ups require budget remaining after flat benefits, so they are inactive in these default runs. A nonzero budget inherited from an earlier controller is an exception. [Gate](../../backend/economy.py#L2080), [initialization](../../backend/tools/runners/run_large_simulation.py#L58), [cap](../../backend/agents.py#L6811)

- A higher preset still raises flat unemployment payments and reservation wages. Its higher threshold changes the poverty definition without activating top-ups in the default runs; “transfers do not change” would be incorrect.
- The current prompt says higher benefits raise income, reservation wages, and fiscal cost; that statement is consistent with flat payments. It does not explicitly promise threshold top-ups. The shared reference should additionally state whether top-ups are enabled. [Prompt](../../backend/tools/llm/llm_government.py#L376)
- Comparisons need the same budget-sizing rule and initial budget, not merely the same benefit label. If sizing is intended benefit administration, separate it from controller selection before comparing arms.

Disposition: section 7 step 1 now makes this an explicit mechanical choice. Implementing it remains future work.

#### Infrastructure multiplier

Each funded `high` outlay adds `0.01 × spending_efficiency` to the uncapped multiplier: 1.00 → 1.01 → 1.02 at full efficiency. This is additive accumulation, not compounding 1% output growth. Cash constraints can stop further investment. [Gain](../../backend/agents.py#L7050)

Production in the affected branch is capped by firm and worker capacity; the generic-services branch returns before this multiplier is applied. Grade measured activity rather than `infrastructure_productivity` itself. The gain can start promptly, but its realized benefit and saturation depend on the state. [Production branches](../../backend/economy.py#L4435)

#### Shock-stream divergence and its limits

Reseeding each tick limits the identified random-stream effect to the same tick: with matched household lists, supply-shock sampling can alter subsequent health draws when firm counts differ. The 3% supply-shock probability is an opportunity rate, not measured divergence frequency. Not every such tick must produce different draws. [Sequence](../../backend/economy.py#L5711)

Outside those events, identical draws do not guarantee identical realized effects: a cash loss is clipped at zero, health losses are bounded, and changed economic states persist. Consequently 3% is not a bound on affected outcomes or later trajectory differences. Section 7 retains this limitation while leaving shock isolation optional.

#### Integration into the plan

- Section 5 now specifies the limited efficiency penalty, inactive default top-ups, and automatic surplus routing; temporary stimulus is retained as another ungated outlay.
- Section 6 explicitly preserves redistribution, membership, source outlays, the tax skim, payout timing, and the pending pool.
- Section 7 now declares transfer-budget sizing and automatic bonds per arm and calls for a common policy reference describing their actual behavior.
- Prompt/code changes remain planned only. The reference should explain benefit administration and correct the incomplete “happiness-only” description of social spending when that work is authorized.

## Source anchors

Only this proposal was revised; no simulation or LLM experiment was run. Repository HEAD matched freshly fetched `origin/main` at `4f693890b5f133c2c6c1dcbec9b1ec91ced97b46` on September 11, 2026; existing working-tree changes were present. Source line links refer to that revision. External documentation was checked during this discussion on September 10, 2026.

| Source | Relevant evidence |
|---|---|
| [Policy schema](../../backend/policy_schema.py) | Two-group cap, tax limits, ordered settings and linked groups. |
| [Government LLM](../../backend/tools/llm/llm_government.py) | Prompt restrictions, sanitizer, suggested actions, observations and decisions. |
| [Agents](../../backend/agents.py) | Household receipts, education and wellbeing; government preset translation. |
| [Economy](../../backend/economy.py) | Rental allocation, production, fiscal mechanics and current metric definitions. |
| [Server](../../backend/server.py) | Background LLM application, exact aggregates and household snapshot cadence. |
| [Warehouse models](../../backend/data/models.py) | Existing persisted household, sector, diagnostic, policy and decision records. |
| [Shared runner helpers](../../backend/tools/runners/run_large_simulation.py) | Population initialization, food/housing statistics and sector rollups. |

Known definition issues to revisit: current GDP is a revenue sum; Gini uses household cash; the current poverty count uses a threshold derived from benefit policy. Correct grading requires explicit definitions rather than relying on these labels.
