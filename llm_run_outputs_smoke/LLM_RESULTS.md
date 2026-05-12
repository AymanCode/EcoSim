# Can an AI run an economy?

That's the question I wanted to answer. I built a small economic simulation, then handed six LLMs ranging from 8B parameters up to 1T the controls usually held by a government. Part of what I wanted to find out: does more parameters and more "thinking power" produce better governance, or is policy a different skill from raw reasoning capacity?

**Short answer:** yes, kind of. The models made coherent policy decisions, the simulated economy responded, and different models produced visibly different governing styles.

**Long answer:** it depends on what you mean by *run*. The sim is a sandbox, not a country. The models I tested are general-purpose, not policy specialists. One seed isn't a benchmark. The more useful reading isn't *which model won*. It's that different models governed differently, and those differences showed up in GDP, jobs, prices, and household wellbeing.

The rest of this doc walks through how the simulation works, what each model did, and where I think the result is interesting versus where it isn't.

---

## The simulation in plain English

EcoSim is a turn-based economic simulation. Each tick, three groups act:

**Households** look for work, earn wages or unemployment benefits, pay taxes, and spend on food, housing, healthcare, and discretionary services. Health and happiness drift with income, prices, employment, and policy.

**Firms** hire workers, set prices and wages, produce, sell, and pay taxes. Four sectors: food, housing, services, healthcare. Firms that run out of cash become distressed and can exit.

**The government** collects taxes and decides how to spend and intervene. In the baseline run, the government is rule-based (a fixed default policy). In the LLM runs, a model reads a structured economy report every 26 ticks and picks what to do next from a constrained action space.

Every run uses the same numbers: 80 households, seed 42, 10 warmup ticks, then 200 simulation ticks. The only thing that changes between runs is who's making the policy calls.

---

## What the government can actually do

The LLM sees a compact economic report and chooses from a fixed schema of policy actions. Every proposed change is validated before it's applied. The model cannot set the wage tax to 800% or invent a new lever.

<details>
<summary><b>Full policy lever reference</b></summary>

| Lever | What it does |
|---|---|
| Wage tax rate | Taxes household wages. Raises revenue, reduces take-home pay. |
| Profit tax rate | Taxes firm profits. Raises revenue, reduces reinvestment. |
| Investment tax rate | Taxes firm investment. Raises revenue, slows expansion. |
| Benefit level | Unemployment benefit size. Supports demand, costs treasury. |
| Public works | Government-backed jobs. Cuts unemployment, costs cash. |
| Minimum wage | Wage floor pressure. Helps workers, can stress weak firms. |
| Sector subsidy target | Which sector receives subsidies (food/housing/services/healthcare/none). |
| Sector subsidy level | Subsidy strength. |
| Price stabilization target | Which sector to monitor or control. |
| Price stabilization level | Monitor, soft, or strict price controls. |
| Rent stabilization | Caps rent increases. Helps affordability, reduces housing revenue. |
| Infrastructure spending | Public investment in productivity. Pays off later, costs now. |
| Technology spending | Public investment in quality/tech. Same trade-off. |
| Social spending | Happiness multiplier. Doesn't directly improve health. |
| Bailout policy/target/budget | Emergency support for distressed firms. |

</details>

---

## Models tested

| Run | Government | Where it runs |
|---|---|---|
| Baseline | Fixed rule-based government | No LLM |
| 8B | Granite 4.1 8B | Local |
| 26B | Gemma 4 26B | Local |
| 70B | Llama 3.3 70B | Groq |
| 120B | GPT-OSS 120B | Groq |
| 1T | Ring 2.6 1T | OpenRouter (experimental) |

---

## Results

Higher is better for GDP, happiness, health, and government cash. Lower is better for unemployment. "Last 26" is the trailing average. It shows what the economy looked like *at the end*, not the lifetime mean.

| Metric | Baseline | Granite 8B | Gemma 26B | Llama 70B | GPT-OSS 120B |
|---|---:|---:|---:|---:|---:|
| Final government cash | $58,043 | $36,678 | $55,286 | $58,727 | $4,077 |
| Minimum government cash | $51,984 | $20,678 | $41,897 | $55,834 | $133 |
| Average GDP | $4,042 | $5,061 | $4,276 | $4,067 | $4,286 |
| Final GDP | $3,592 | $6,333 | $4,832 | $3,660 | $4,091 |
| Last-26 average GDP | $3,792 | $6,580 | $4,940 | $3,768 | $4,286 |
| Average unemployment | 4.03% | 6.33% | 3.46% | 2.60% | 3.06% |
| Final unemployment | 9.21% | 0.00% | 2.60% | 1.32% | 9.09% |
| Last-26 average unemployment | 5.93% | 0.92% | 1.77% | 0.65% | 2.54% |
| Average happiness | 0.602 | 0.679 | 0.616 | 0.525 | 0.640 |
| Final happiness | 0.478 | 0.697 | 0.524 | 0.356 | 0.525 |
| Last-26 average happiness | 0.495 | 0.694 | 0.523 | 0.383 | 0.533 |
| Final health | 0.770 | 0.760 | 0.777 | 0.757 | 0.762 |
| Final fiscal pressure | 0.075 | -0.012 | 0.053 | 0.152 | 0.058 |
| Accepted decision rate | N/A | 25.0% | 100.0% | 100.0% | 100.0% |
| Evidence match rate | N/A | 75.7% | 55.2% | 96.0% | 94.6% |

A few things jump out before reading any further:

- **Granite 8B leads on average GDP and happiness** despite being the smallest model in the field.
- **Llama 70B is the cash hawk.** Best treasury, best unemployment, worst final happiness. Optimized one set of metrics and let another slide.
- **GPT-OSS 120B nearly went broke.** Minimum cash of $133 is one bad tick from insolvency.
- **Gemma 26B improved every dimension over the no-AI baseline.** Quietly the most consistent run.
- **The baseline** isn't best or worst on any single column. That's the point of having one.

Two metrics about model behavior, not policy quality:
- **Accepted decision rate** = share of LLM decision cycles where at least one proposed change passed validation and was applied. Granite at 25% means three out of four of its proposed plans were rejected by the schema. It kept trying things outside the lever set.
- **Evidence match rate** = share of the model's cited evidence strings that matched real values in the prompt. A model can have a high evidence match rate and still pick bad policy. It's a citation-discipline metric, not a policy-quality metric.

---

## How each model governed

The runs read like personalities when you go tick by tick.

**Granite 4.1 8B, narrow but lucky on this seed.** Picked food subsidies early, ratcheted them up, then mostly held the line. It worked: highest GDP, highest happiness. But the policy surface it explored is thin, and 25% accepted-decision rate is rough. Most of what it wanted to do, the schema wouldn't let it do. I wouldn't bet on Granite repeating this on a different seed.

**Gemma 4 26B, sector firefighter.** Reached for bailouts and sector subsidies whenever a firm went distressed, mostly food and services. Less dramatic than Granite, but it pulled every dimension up versus the no-AI baseline. The most boring run in the best way.

**Llama 3.3 70B, fiscal conservative.** Protected cash aggressively. Cut social spending. Supported services. The result: best cash buffer in the field, lowest unemployment, and the worst final happiness (0.356). A government that runs the books well and leaves households measurably worse off than doing nothing.

**GPT-OSS 120B, growth manager.** Cut taxes, spent on infrastructure and tech, used subsidies, used bailouts. Drove decent GDP and happiness. Also drove minimum treasury to $133. Closer to crisis than anything else here. Active policy isn't free.

**Ring 2.6 1T (experimental).** The first run hit a parser miss: one decision came back with blank content instead of JSON, which I traced to a harness/provider issue rather than a bad economic call. I hardened the retry path (treat blank OpenRouter content as retryable, give Ring a JSON-repair retry on malformed first responses) and reran twice. Once at temperature 0.1 for a clean strict-instruction baseline, once at 0.4 for an apples-to-apples comparison with the other models.

| Metric | Ring, temp 0.4 (first) | Ring, temp 0.1 (clean) | Ring, temp 0.4 (fairness) |
|---|---:|---:|---:|
| Final government cash | $42,450 | $65,775 | $60,033 |
| Minimum government cash | $42,450 | $56,992 | $58,633 |
| Average GDP | $9,702 | $11,625 | $10,963 |
| Final GDP | $6,622 | $15,695 | $10,913 |
| Average unemployment | 15.4% | 15.6% | 13.8% |
| Final unemployment | 5.9% | 1.1% | 0.0% |
| Average happiness | 0.350 | 0.330 | 0.383 |
| Final health | 0.732 | 0.747 | 0.731 |
| Accepted decision rate | 87.5% | 100.0% | 100.0% |
| Evidence match rate | 68.6% | 65.0% | 92.5% |
| Parse misses | 1/8 | 0/8 | 0/8 |

The two clean Ring runs governed differently. At temperature 0.1, Ring played crisis manager: cut social spending under cash stress, monitored food prices, raised wage taxes, subsidized services and food, used food bailouts, then restored social spending once happiness collapsed. At temperature 0.4, it was more aggressive: cut wage taxes first to fight unemployment, raised them back later for cash stability, rotated bailouts from food to services, lowered minimum wage pressure, ramped social spending late in the run, and ended with rent monitoring. Different temperatures, same model, recognizably different style.

Ring's GDP numbers are roughly 2x the other models in absolute terms, a side effect of how aggressively it leans on active fiscal policy in this setup. Unemployment averages are also higher, partly because of churn from those policy shifts. Both are real and both came from the same lever set the smaller models had.

That raises a harder question: what counts as good governance in the first place? If "good" means low unemployment and high GDP, the 1T run is the obvious winner. 0% final unemployment, GDP roughly 2x the others. But happiness in the Ring runs sits around 0.35, the lowest in the entire field, while Granite hit the same 0% unemployment with happiness over 0.69. Same headline number, very different country. Being result-oriented gets you elite numbers on a few axes. A country still has to keep its people functional, not just its spreadsheet.

---

## A note on "bigger model, better government"

I set this experiment up partly to see how model size scales as a policymaker. It's not a clean comparison and I want to be honest about that.

The models here differ on a lot more than parameter count. Granite 8B is rule-oriented and conservative by training disposition. It tends to pick one lever and stay with it. Ring 1T spends most of its decision budget thinking before it commits, then operates inside the constraints it just reasoned about. Gemma and Llama sit somewhere in between, with different priors about which sector to defend first when things go sideways. So when Granite outscores Llama 70B on average GDP, that isn't really evidence that "8B beats 70B at governing." It's evidence that *this 8B model's instincts* happened to line up with *this seed's incentives*.

The thing I'd commit to from these runs: bigger models did more elaborate reasoning, and that didn't reliably translate into better economic outcomes. Scale bought me richer policy plans. It didn't buy me cleaner ones. On a different seed, or with a different action space, the ranking could easily flip. The more interesting question becomes which *style* of governing holds up across conditions, not which model wins on one run.

---

## So can an AI govern?

**Yes signals.** The models read the economy report, picked policies, and the economy moved in response. Each one produced a recognizable governing style: fiscal hawk, growth manager, sector firefighter, crisis operator. That coherence isn't trivial. None of these models were fine-tuned for economic policy. They reasoned about it from general training and a structured prompt, and the results weren't random.

**But the simulation is an abstraction.** Real economies have orders of magnitude more variables, longer horizons, political constraints, geopolitical exposure, financial intermediation, and expectational dynamics than EcoSim has. There's no central bank here, no trade, no expectations channel, no labor mobility across regions, no shocks the model didn't already see in warmup. Whatever the models did here, they did inside a small box.

**And the models weren't built for this.** None were post-trained on macro data, historical policy responses, or counterfactual outcomes. A specialist model, fine-tuned on policy episodes paired with their results, would presumably make better technical decisions than a general 8B or 70B. That's the obvious next experiment.

**But there's a counterargument to specialization.** A model trained narrowly on "what worked technically in past economies" inherits the biases of past economies. It also inherits the assumption that governing is a technical optimization problem. It isn't. Cutting social spending to balance the books, like Llama did, is technically fine and politically explosive. A model that only sees metrics will optimize metrics, and break things humans care about that aren't metrics. The general-purpose models in this experiment at least carry a coarse model of what people care about in their training. That might end up mattering more than a tighter loss on GDP.

So: can an AI govern? On the technical layer of a constrained problem, yes, and the experiment above is evidence of it. *Should* it? That's not a model-quality question. That's about what governance is for, and that part doesn't compress into a metric.

---

## Limitations

- One seed. The numbers will move under different RNG and the model rankings might reshuffle. Multi-seed runs are the obvious next step.
- The action space is narrow. Real fiscal policy has more dimensions than 15 levers.
- Fiscal only. No monetary policy, no central bank, no exchange rate, no debt issuance.
- Evidence match rate tracks citation discipline, not policy quality. A model can cite everything correctly and still make a bad call.
- The LLM is consulted every 26 ticks. Higher-frequency decisions might change strategy meaningfully.
- The "AI government" doesn't see real households. It sees an aggregated report. That's a limitation, but it's also realistic: human governments don't see real households either.

---

## What I'd try next

- Run every model across 20+ seeds and report distributions instead of point estimates. Replace "Granite won" with "Granite wins X% of seeds."
- Fine-tune a small model on EcoSim transcripts paired with outcome metrics, then put it head-to-head against the general-purpose models. See whether specialization actually wins, or whether it overfits to the simulator's quirks.
- Add a monetary authority and test whether the same LLM can coordinate fiscal and monetary policy without conflicting itself.
- Introduce shocks the warmup doesn't include (productivity drop, demand collapse, sector failure) and see which governing style survives.
- Add a "human-in-the-loop" mode where the model proposes and a person ratifies. Compare to fully autonomous.

---

## Reproducing this

The simulation, the government action schema, and the LLM harness are all in this repo. Same seed gives the same baseline run. Pointing the LLM government runner at a different model swaps the policymaker without changing anything else.

Per-run summaries (model, decisions, policy timeline, final metrics):

| Run | Report |
|---|---|
| Baseline (no LLM) | [no_llm_conservative_seed42_ticks200_20260510_234545](../llm_run_outputs_smoke/no_llm_conservative_seed42_ticks200_20260510_234545.json) |
| Granite 4.1 8B | [llm_government_seed42_ticks200_20260511_001301.md](llm_government_seed42_ticks200_20260511_001301.md) |
| Gemma 4 26B | [llm_government_seed42_ticks200_20260511_000251.md](llm_government_seed42_ticks200_20260511_000251.md) |
| Llama 3.3 70B | [llm_government_seed42_ticks200_20260511_004841.md](llm_government_seed42_ticks200_20260511_004841.md) |
| GPT-OSS 120B | [llm_government_seed42_ticks200_20260511_203344.md](llm_government_seed42_ticks200_20260511_203344.md) |
| Ring 2.6 1T (first run, temp 0.4) | [llm_government_seed42_ticks200_20260511_211800.md](../llm_run_outputs/llm_government_seed42_ticks200_20260511_211800.md) |
| Ring 2.6 1T (clean, temp 0.1) | [llm_government_seed42_ticks200_20260511_212851.md](../llm_run_outputs/llm_government_seed42_ticks200_20260511_212851.md) |
| Ring 2.6 1T (fairness, temp 0.4) | [llm_government_seed42_ticks200_20260511_213704.md](../llm_run_outputs/llm_government_seed42_ticks200_20260511_213704.md) |

Each per-run report contains the model identifier, every decision the LLM made with timestamps and reasoning, and the final-state economic summary.

Baseline run is JSON-only (no LLM decisions to log). The seven LLM runs each include the per-decision report linked above.

---

For context on what EcoSim is and how the simulation is built, see the [project README](../README.md).
