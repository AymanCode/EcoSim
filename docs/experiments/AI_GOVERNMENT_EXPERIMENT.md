# Can an AI run an economy?

I built EcoSim to test a simple question: if you give an LLM the policy controls of a simulated government, can it make coherent decisions and keep an economy running?

For this run I scaled the experiment to **1,000 households** and compared five LLMs, from an 8B model running locally to a 1T model on OpenRouter, against a fixed rule-based baseline. Every run used the same seed, the same simulation length, the same government action schema, and the same decision schedule. The only thing that changed was the policymaker.

**Short version:** yes, in a limited sense. The models read the state, chose valid policies, and produced different measurable outcomes. But "good governance" is not one number. Ring 1T had the strongest overall run. Llama 70B protected the treasury. GPT-OSS 120B reasoned cleanly but nearly bankrupted the government. Granite 8B got stuck in a narrow bailout loop.

What I found more useful than the ranking is that the models had recognizable governing styles, and those styles showed up in GDP, unemployment, government cash, and household wellbeing.

---

## What the simulation does

EcoSim is a turn-based economic simulation. Each tick, three groups act.

**Households** look for work, earn wages or unemployment benefits, pay taxes, and spend on food, housing, healthcare, and services. Health and happiness move with income, prices, employment, and policy.

**Firms** hire workers, set wages and prices, produce goods, sell into markets, pay taxes, and can become distressed. The main sectors are food, housing, services, and healthcare.

**The government** collects taxes and chooses policy. In the baseline run that policy is fixed and rule-based. In the LLM runs, a model reads a compact economic report every 26 ticks and chooses from a constrained policy schema.

The 1,000-household setup also scales the firm side and healthcare staffing with the population. The point was to avoid a run where a large population is squeezed into a small market.

---

## Experiment setup

Every run in the main table uses:

- `1,000` households
- seed `42`
- `10` warmup ticks
- `200` simulation ticks
- first LLM decision at tick `15`
- one LLM decision every `26` ticks after that
- temperature `0.4`, top-p `0.8`, max tokens `2000` for the LLM runs

| Run | Government | Provider |
|---|---|---|
| Baseline | Fixed rule-based government | No LLM |
| 8B | Granite 4.1 8B | Local LM Studio |
| 26B | Gemma 4 26B | Local LM Studio |
| 70B | Llama 3.3 70B | Groq |
| 120B | GPT-OSS 120B | Groq |
| 1T | Ring 2.6 1T | OpenRouter |

---

## LLM harness

I built the government runner with the pieces I would want in a real agent harness rather than as a prompt script.

- Every model has to return JSON policy actions, and every action is validated against `policy_schema.py`.
- Models can only use the known fiscal and market levers. They cannot invent a policy or set impossible values.
- Blank, malformed, or truncated provider responses are retried or repaired before anything touches simulation state.
- The same harness drives OpenRouter, Groq, and local LM Studio models. Swapping models is a config change.
- Economic results are logged separately from behavior metrics like accepted decision rate and evidence match rate.
- Each decision cycle records the prompt context, the raw model plan, accepted changes, rejected changes, the current policy, and state metrics.

The split between economic results and behavior metrics matters more than it looks. A model can cite the economy correctly and still pick bad policy. It can also make a valid policy move for the wrong stated reason. I wanted to be able to tell those apart, so the harness keeps them as separate questions.

---

## What the government can control

The LLM sees a compact economic report and chooses from a fixed policy schema. Every proposed change is validated before it is applied.

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
| Sector subsidy target | Which sector receives subsidies. |
| Sector subsidy level | Subsidy strength. |
| Price stabilization target | Which sector to monitor or control. |
| Price stabilization level | Monitor, soft, or strict price controls. |
| Rent stabilization | Caps rent increases. Helps affordability, reduces housing revenue. |
| Infrastructure spending | Public investment in productivity. Pays off later, costs cash now. |
| Technology spending | Public investment in quality and technical progress. |
| Social spending | Happiness support. Does not directly improve health. |
| Bailout policy, target, and budget | Emergency support for distressed firms. |

</details>

---

## Results

Higher is better for GDP, happiness, health, and government cash. Lower is better for unemployment. "Last 26" is the trailing average at the end of the run, which shows the final operating state better than the lifetime mean.

| Metric | Baseline | Granite 8B | Gemma 26B | Llama 70B | GPT-OSS 120B | Ring 1T |
|---|---:|---:|---:|---:|---:|---:|
| Final government cash | $19,265 | -$16,885 | $23,876 | $75,197 | $14,306 | $58,844 |
| Minimum government cash | $12,102 | -$16,885 | $23,876 | $64,434 | -$44,878 | $58,163 |
| Average GDP | $46,756 | $46,212 | $47,300 | $48,749 | $45,104 | $51,097 |
| Final GDP | $38,396 | $36,442 | $43,072 | $47,971 | $38,715 | $47,252 |
| Last-26 average GDP | $45,869 | $41,207 | $44,537 | $46,323 | $42,230 | $51,329 |
| Average unemployment | 21.96% | 22.57% | 22.37% | 20.04% | 21.41% | 18.34% |
| Final unemployment | 32.99% | 39.04% | 29.71% | 18.77% | 28.15% | 11.09% |
| Last-26 average unemployment | 21.47% | 29.78% | 25.75% | 20.43% | 15.84% | 6.29% |
| Average happiness | 0.288 | 0.292 | 0.291 | 0.235 | 0.298 | 0.300 |
| Final happiness | 0.088 | 0.074 | 0.088 | 0.045 | 0.089 | 0.144 |
| Last-26 average happiness | 0.096 | 0.089 | 0.098 | 0.047 | 0.095 | 0.137 |
| Final health | 0.762 | 0.759 | 0.762 | 0.758 | 0.760 | 0.763 |
| Final fiscal pressure | 0.005 | 0.061 | 0.043 | 0.024 | 0.039 | 0.033 |
| Accepted decision rate | — | 50.0% | 87.5% | 100.0% | 100.0% | 100.0% |
| Evidence match rate | — | 65.6% | 56.2% | 86.7% | 94.4% | 82.5% |

The rule-based baseline does not receive decision-quality scores because it does not call an LLM.

![Per-model governing profile across policy levers](../assets/llm_results_governing_profile.png)
*Governing profiles: each model's characteristic policy mix over the run.*

![Unemployment trajectories by model](../assets/llm_results_unemployment_overlay.png)
*Unemployment over time. Ring 1T drives it down; Granite 8B drifts up.*

![Household happiness trajectories by model](../assets/llm_results_happiness_overlay.png)
*Household happiness over time. Models separate less here than on unemployment or GDP.*

---

## Read this table first

- **Ring 1T was strongest overall.** It had the best average GDP, best average unemployment, best final unemployment, best final happiness, and a strong cash floor.
- **Llama 70B was the fiscal hawk.** It ended with the most government cash, but it also produced the lowest final happiness.
- **GPT-OSS 120B was technically clean but financially risky.** It had the best evidence match rate and 100% accepted decisions, but government cash dropped to -$44,878 mid-run.
- **Gemma 26B was steady but reactive.** It kept cash positive and made mostly valid decisions, but unemployment stayed high.
- **Granite 8B got stuck.** It kept increasing food bailout capacity, stopped making new useful changes, ended cash-negative, and had the worst final unemployment.
- **The baseline was decent.** It did not win, but it also did not collapse. That makes the comparison more useful.

One result I want to flag on its own: at 1,000 households, final happiness was low across the board. The models separated more clearly on unemployment, GDP, and fiscal stability than on household wellbeing. I think that is a finding in itself, and probably a sign that the larger simulation is exposing late-run household stress, but I have not diagnosed it yet.

---

## Model behavior

**Ring 2.6 1T.** Ring had the best overall run. It turned public works on early, used food support, lowered minimum wage pressure when the labor market was strained, raised taxes later for stability, and kept social spending high late in the run. It ended with $58,844 in government cash, a minimum cash floor of $58,163, final unemployment of 11.09%, and the best final happiness score in the group at 0.144. That happiness number is still low in absolute terms, but Ring handled the trade-off better than the other models.

**Llama 3.3 70B.** Llama protected the treasury better than anyone. It cut social spending early, raised wage taxes, and later used targeted support for food and services. Final government cash was $75,197, the best in the table. The downside is clear: final happiness fell to 0.045, the worst result. This is the "balanced books, unhappy households" run.

**GPT-OSS 120B.** GPT-OSS made clean, valid decisions and cited the prompt well. It had the highest evidence match rate at 94.4%. Its policy style was growth-oriented: lower profit taxes, infrastructure spending, wage tax changes, food monitoring, and later food subsidies. The problem was cash discipline. It went as low as -$44,878 before recovering to $14,306 by the end. The model looked technically disciplined while still taking the economy too close to the edge.

**Gemma 4 26B.** Gemma governed like a sector firefighter. It started with food bailouts, moved to all-sector bailouts, raised profit taxes when cash got tighter, monitored healthcare prices, and added food subsidies. It completed the run with positive cash at $23,876, but final unemployment stayed high at 29.71%. One decision at tick 171 came back as nested grouped actions (`group sector_subsidy`, `group bailout`) instead of valid policy keys. The schema rejected those changes and the run continued safely.

**Granite 4.1 8B.** Granite was coherent but narrow. It kept focusing on food bailouts and raised bailout capacity from $5,000 to $10,000 to $25,000 to $50,000. After that, half of the decision cycles produced no new accepted change because the model was repeating policy that was already active. It ended with -$16,885 in government cash, 39.04% final unemployment, and final happiness of 0.074. The smaller model did not fail because it wrote nonsense. It failed because it got stuck on one play.

**Baseline.** The rule-based government matters here. It ended cash-positive at $19,265 and landed near Gemma and GPT-OSS on final happiness, but unemployment finished at 32.99%. It is not a great government, but it gives a useful floor. The LLMs had to beat something that at least stays solvent.

---

## Engineering takeaways

The validation did real work. Gemma's malformed grouped action at tick 171 did not break the run, because a policy change has to pass the schema before it touches state.

Provider reliability is its own problem. The same harness ran local LM Studio models, Groq models, and OpenRouter models, which is what makes the comparison practical, but it also means the runner has to handle each provider's response quirks.

Decision quality is not policy quality. GPT-OSS had the strongest evidence discipline and every one of its decisions passed validation. It still drove government cash negative. Clean agent behavior is useful, but it is not the same thing as good governance.

Scale made weak strategies easier to see. At 1,000 households, Granite's narrow bailout loop and Llama's happiness trade-off both stand out clearly.

The best model did not optimize everything. Ring won the main comparison, but even Ring ended with low absolute happiness. The run says "best in this setup," not "solved governance."

---

## What this says about model size

This is not a clean parameter-count benchmark. The models differ by training, provider, serving stack, latency, response format, and policy instincts. Still, the result is useful.

The 1T model did the best in this run, but bigger was not automatically cleaner. GPT-OSS 120B reasoned well and still went cash-negative. Llama 70B had strong fiscal instincts and still crushed happiness. Gemma 26B was steady but reactive. Granite 8B was simple and got trapped.

The more useful question is not "which model is biggest?" It is "which governing style survives different seeds, shocks, and action spaces?"

---

## So can an AI govern?

Inside this sandbox, yes. The models read the economy, chose policies, and the economy moved in response. They were not random. They had styles: growth manager, cash hawk, sector firefighter, bailout loop, and balanced active manager.

Outside the sandbox, I would not make a claim that strong. Real economies have central banks, debt markets, politics, trade, expectations, regional differences, shocks, legal constraints, and people who react to policy before it lands. EcoSim is a controlled environment for testing agentic policy behavior, not a country.

The takeaway I would actually stand behind is practical: an LLM can be put behind a constrained action schema, observed, scored, retried, audited, and compared across providers. That is useful beyond this economic sandbox.

---

## Limitations

- One seed. Rankings can change under different random seeds.
- One scale point. This doc reports the 1,000-household run, not a distribution across population sizes.
- Fiscal policy only. There is no central bank, debt issuance, exchange rate, or monetary policy.
- The action space is small compared with real fiscal policy.
- The LLM sees aggregate metrics, not individual household stories.
- Evidence match rate measures citation discipline, not wisdom.
- Happiness is low across all 1,000-household runs, which needs more diagnosis before overinterpreting welfare results.

---

## What I would try next

- Run every model across 20+ seeds and report distributions instead of one table.
- Add shocks: productivity drop, demand collapse, housing shortage, healthcare overload, or food-sector failure.
- Add a monetary authority and test whether one model can coordinate fiscal and monetary policy.
- Fine-tune a small model on EcoSim transcripts and compare it against the general-purpose models.
- Add a human-in-the-loop mode where the model proposes policy and a person approves it.
- Build a scoring view that separates "solvent government," "low unemployment," "stable prices," and "household wellbeing" instead of pretending one score captures governance.

---

## Reproducing this

The simulation, policy schema, and LLM harness are all in this repo. The same seed gives the same baseline run. Pointing the runner at a different model swaps the policymaker without changing the simulation.

Raw per-run artifacts are generated by `backend/tools/llm/run_llm_government_test.py` and intentionally left out of the public repository. Each run writes its prompt context, policy choices, accepted and rejected changes, final metrics, and firm-level financials locally for post-run analysis. The curated table above keeps the public result readable without publishing every generated JSON and Markdown output file.

For the broader project, see the [project README](../../README.md).
