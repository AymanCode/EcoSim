# EcoSim frontend redesign: a learning tool for newcomers

Date: 2026-09-24. Status: approved by Ayman on 2026-09-24 from the one-page overview, after revision for the independent audit. Interim default world: legacy payment rules, 1,000 households per town. Next: implementation plan for phase 1.
Audits: `docs/reviews/2026-09-24-frontend-redesign-spec-audit.md` (Codex, `gpt-6-sol`) and the second pass `docs/reviews/2026-09-24-frontend-redesign-spec-check2.md` (Codex, `gpt-6-astra`). Their findings are folded in below; where this spec and an audit disagree, this spec says why.
One-page summary with diagrams: `docs/superpowers/specs/2026-09-24-mockups/00-overview.html`. Mockups: `docs/superpowers/specs/2026-09-24-mockups/` (open the HTML files in a browser). Their card copy and numbers predate the evidence audit in section 5, which governs. Decision log: `CHANGELOG.md`. Smoke-run evidence: `docs/evals/2026-09-24-newcomer-smoke/`.

## 1. Purpose

Replace the React dashboard in `frontend-react/` with an interface built for people who are new to economics and want to learn by watching. The two activities it supports are comparing economic policies on matched seeds and evaluating a language model acting as government. Both are framed as "two towns that started identical".

The current dashboard is a generic analyst grid. The 2026-09-06 rebuild wrote a style spec banning glow and gauges and still produced a generic result, because the problem is structural: every screen is an equal-weight tile grid, one chart type is used identically about 25 times, and the data pipe is narrow. The tick frame carries about 40 metric keys assembled in the server loop (`backend/server.py:2612`), but only three of the roughly 150 fields computed by `get_economic_metrics()` are among them. Discrete events (labor, healthcare, regime) are kept in per-tick memory and persisted to the warehouse but never sent to the browser; only policy-change records and the latest LLM decision reach it. Firms arrive as two top-twelve leaderboards plus seven tracked firms. There is no time scrubbing and no run comparison. This design fixes the structure and the data pipe. Visual polish is a separate pass at the end.

## 2. Audience and tone

- Primary viewer: a newcomer. They should understand what is on screen without knowing what a Gini coefficient is.
- Every number arrives as a friendly name, a one-sentence meaning, a picture, and the value for each town. More statistics are welcome in that shape; bare numbers are not.
- Browsing is part of the fun: random households and their situations, which businesses are richest and which are struggling. These were the most loved parts of the original frontend and they return as first-class panels.
- The analyst grid is not deleted. It sits behind "Show me all the numbers".
- All viewer-facing strings (metric names, definitions, narration templates, rule sentences) live in one catalog module, not inside components. English only at launch, but the catalog makes translation and copy review possible.

### 2.1 Friendly vocabulary

Each metric in the curated frame is specified with its source, unit, freshness and null behaviour. Freshness is "every tick" unless stated; today several browser metrics are cached for five ticks (`backend/server.py:2135`) and the projection must state per field whether that stride stays.

| On screen | Meaning shown to the viewer | Source | Unit | Notes |
|---|---|---|---|---|
| People out of work | Working-age people who want a job and can't find one, per 100 | `unemployment_rate` | percent, shown as "N in 100" | |
| Typical weekly pay | The middle earner's weekly pay before tax | median wage from `compute_household_stats` | currency per tick | |
| Price of food | What a unit of food costs in the shops this week | mean posted food price (`backend/server.py:785`) | currency per unit | This is the posted price. It does not move under a food subsidy. |
| What households pay for food | What people actually paid after any help from the town hall | new: household out-of-pocket food spend per tick | currency per household | Needed for the food-subsidy question. New metric. |
| Gap between rich and poor | 0 means everyone has the same, 1 means one person has it all | `gini_coefficient` | ratio | Cash-based, as documented. |
| Town hall cash | What the town hall has in the bank; negative means it owes | `GovernmentAgent.cash_balance` | currency, signed | The frame's `govDebt` is the negative part of the same balance (`backend/server.py:2617`) and stays consistent. The internal `public_debt` metric is inert and unused. |
| Homes without a roof | Households that lost their home | housing diagnostics | count | Near zero at 1,000 households in legacy runs. |
| Firms open, struggling, closed | Counts by firm state | firm state snapshot plus closed-firm archive (section 6.4) | counts | "Closed" needs the archive; bankrupt firms leave `economy.firms`. |
| Bank loans and defaults | Active loans and cumulative defaults | `bank_active_loan_count` and default telemetry (`backend/economy.py:7939`) | counts | Not the existing frame field `activeLoans`, which counts firms with government loans. |

## 3. Experiment model

An experiment is the unit of work. It is owned by the server as well as the browser.

- **Mode:** `compare` (Compare policies), `ai` (Test an AI mayor), `play` (Just play).
- **Seed:** rolled automatically, shown as "Town #1337" beside the start button with a "different town" link. The same seed and world config always build the same starting town; with the same policy actions at the same ticks the whole run repeats, which tests assert for fixed seed and policy. Newcomers never type the seed; "Build my own" exposes the field.
- **Shared world config:** households per town, firms per sector, stabilizers, payment-sequence settings. Locked at launch and identical across arms, which is what makes the comparison fair.
- **Arms ("towns"):** one to four. Compare mode: each arm is a preset or custom levers from the 17-lever schema in `backend/policy_schema.py` (three taxes, ten ordered levers, four enums). AI mode: one LLM arm with provider and model, plus an optional frozen-policy control. Play mode: one arm. A single arm is the sandbox and must feel first-class.
- **Initial policy:** each arm's lever vector is applied before the first tick through a validated `initial_policy` field on SETUP (section 6.2). Today SETUP applies only two raw tax overrides (`backend/server.py:1873`, `1926`), which is not enough for presets.
- **Household budget:** 10,000 per experiment, split evenly. Max per arm is `floor(10000 / arms)`. Enforced by the server-side experiment record (section 6.1), not by trusting each socket's own claim.
- **Horizon:** fixed at launch, default 5 years (260 ticks), choices 1, 2, 5, 10. The server knows the horizon and pauses each arm when it reaches it (section 6.3). "Extend a year" adds 52 ticks to every arm.
- **Intervening:** levers stay editable per arm mid-run. Every change, human or LLM, becomes a chart marker, a feed item, and a before/after anchor. Human changes are recorded with their tick so a compare-mode experiment can be replayed.
- **Time alignment:** arms are independent sessions and drift. The client keeps them within three ticks by pausing the leading arm until the others catch up. Comparison views draw up to the lowest common tick; the cursor cannot pass it. Twelve-week outcome comparisons are only computed once every arm has reached the end of the window.

### 3.1 Lifecycle and failure rules

States: draft, running, paused, finished, extended, lost.

- **Pause and resume:** the client sends STOP or START to every arm.
- **Finish:** when every arm reports `HORIZON_REACHED`, the client sends FINISH to each. FINISH closes the warehouse run as analysis-ready (today only a completed close sets `analysis_ready`, and no WebSocket command requests it, `backend/server.py:1803`) and keeps the socket open for reading. The results view settles.
- **Extend:** EXTEND with a tick count raises the horizon on every arm and resumes them. If FINISH has already run, the run is reopened and closed again at the new horizon.
- **Reset:** a fresh SETUP with the same seed and config on every arm. The existing RESET command zeroes the tick without rebuilding the economy (`backend/server.py:3266`) and is not used by the new client.
- **Lost arm:** if one arm's socket drops, the client pauses the other arms immediately and shows which town was lost. A manager cannot be resumed after disconnect (`backend/server.py:3286`), so the choice offered is: restart the experiment from the seed, replaying recorded human policy actions at their ticks in compare and play modes, or finish now with a verdict marked incomplete. In AI mode the AI arm cannot be replayed; the restart says so.
- **Message ordering:** every message is keyed by arm and session generation. Messages from a superseded socket are dropped.
- **Second tab:** sessions count against the server cap of eight. A second tab opening the same experiment is rejected by the experiment record; read-only attachment is a later feature.
- **Capacity:** if the server is full it rejects the connection when the socket session opens, before any command (`backend/server.py:3207`). The client shows "the server is full" with the session count rather than a generic error.
- **Action receipts:** every CONFIG that changes levers is answered with a receipt carrying an action id, the accepted values after validation and clamping, and the tick it takes effect. Replay after a lost arm uses receipts, never the original requests, so rejected or clamped values are not replayed as if applied. Today CONFIG has no success acknowledgement (`backend/server.py:2790`, `2831`).

### 3.2 Backend facts this relies on

Verified 2026-09-24. The server already opens one `SimulationManager` per WebSocket connection, up to `ECOSIM_MAX_SESSIONS` (default 8), with per-session RNG; a server test proves distinct managers for simultaneous connections. All sessions share one Python thread, so N arms each run at roughly 1/N speed. Per-tick loop time, including the per-tick statistics and snapshots but not JSON serialization, sending or the loop's sleep, measured 31 to 39 seconds per arm for 1,000 households over 260 ticks. Two arms therefore take one to two minutes wall-clock; the full path is benchmarked in phase 1 (section 9). Same seed and config produce identical runs, asserted by tests. Enabling the LLM breaks tick-level reproducibility because decisions land when the provider answers; the backend records both the observed tick and the applied tick.

## 4. Screens

Navigation: Set up, Run, Saved (hidden until the warehouse phase). Two overlays: Town hall (levers) and Show me all the numbers.

### 4.1 Set up (`01-setup.html`)

Headline "What do you want to find out?" then four steps:

1. Kind of experiment: Compare policies, Test an AI mayor, Just play.
2. A question: preset cards, each showing the two towns' rules as coloured chips and one sentence on the trade-off, plus "Build my own". Two cards ship at launch (section 5); the mockup shows five candidates. Held cards remain available as named presets inside "Build my own". In AI mode this step becomes a model and provider picker (Ollama, LM Studio, OpenRouter, Groq) with a live reachability check, and a toggle for the frozen control town.
3. Your towns: arm chips with "Edit levers" and "Add a town", which states the household split.
4. The world: households per town with the cap shown, years, and the payment-rules toggle, each with a sentence. Seed is not a field here.

The start button shows a time estimate from the phase-1 benchmark. Setup failures (capacity, invalid policy, provider unreachable) are shown in place with the fix.

### 4.2 Run, Compare policies (`02-run-compare-policies.html`)

Two matching columns so Town A and Town B line up all the way down, then shared story elements.

- **Lead sentence.** Plain-language summary of the divergence so far, generated from deltas by the narration module.
- **Town drawing.** SVG: town hall and bank, a Main street of firm buildings sized by staff with struggling flagged and closed crossed out, and 100 houses each representing a fixed share of households, coloured working, looking for work, lost their home. Three facts under it. The drawing has a text alternative (the same facts and counts as a list) and is not itself interactive; meeting a family happens through the household cards.
- **Businesses.** All open firms ranked richest first: name, sector, cash bar, staff, status tag (Growing, Steady, Struggling). Firms closed within the last year are listed after them from the closed-firm archive, faded.
- **Households.** Four households from the tracked sample as cards: avatar coloured by status, name and age, job, savings, one sentence about what happened to them lately. "Follow" pins one. "Show me four others" draws from the sample. Both are keyboard-reachable buttons.
- **Story chart.** A dedicated StoryChart component (section 7): one metric, x-domain fixed from tick 0 to the horizon with the empty future visible, all arms overlaid in their colours, direct end labels, per-arm policy markers, annotations, a shared cursor. Any stat can be promoted to it.
- **Verdict** in plain words ending in a question, plus four stat cards with tiny trend lines and a line naming more stats that can be opened.
- **What's happening** feed, newest first, town-coloured, including household events. **How to read this** panel beside it.
- **Town hall** drawer: levers for the selected arm, grouped, with a sentence each. Open by default in play mode.

Single-arm play uses the same layout with one column.

### 4.3 Run, Test an AI mayor (`03-run-ai-mayor.html`)

Same shape, with the AI's decisions as the centrepiece between the towns and the story:

- **Decision strip.** One card per decision along the horizon rail: week, one-line summary, status tag (Applied, Partly applied, Rejected), thinking time.
- **Open decision.** Four columns. What it saw: each indicator the model received, with the true value at the indicator's own source tick shown small underneath (section 6.7). What it asked for and what code allowed: each requested change with its outcome and, for capped or rejected items, the rule sentence from the rule catalog, which maps the backend's reason codes to plain language with the real limits (for example, a tax may move at most five percentage points per decision, `backend/policy_schema.py:13`). Why, in its own words: the model's full public rationale, stored as a separate field from phase 3 (section 6.7); until then the card shows the stored excerpt with no claim of more. Figures checked: "N of M figures the model cited matched the town's data". Only citations that parse to a scalar and compare against a labelled reference value count toward M; citations without a value or with dictionary-valued references are excluded, because the current audit can mark those as matched (`backend/tools/llm/llm_government.py:822`). What happened in the next twelve weeks, against the control town, shown only once both arms have passed that window.
- **Chart** with numbered decision dots. **Report card:** decisions, requests, applied/capped/rejected, average thinking time, report-to-action lag, cited figures that matched, four stats against the control, and a verdict ending in "would you re-elect it?"
- **Provider failure:** if the provider is unreachable when the arm starts, the advisor is disabled and the town runs unguided (`backend/server.py:1456`); if a later call fails, that decision is recorded as an error with no change and the advisor tries again next cycle (`backend/server.py:1526`). The client pauses the experiment on the first case by default and relabels the arm "AI offline since week N" if resumed; in the second case the decision card shows the error.
- Businesses and households as in compare mode. Feed marks AI actions in the AI colour.

AI colour is purple (`#6D4AE0`), control is orange (`#E0762C`). Blue and purple failed the colour-blind check and are not paired.

### 4.4 Show me all the numbers (`05-all-the-numbers-reference.html`)

The analyst view: horizon bar with scrubber, hero chart, a metric-by-arm scoreboard, six groups of small multiples. This mockup used the old dark tokens and is a structural reference only; it gets the new theme and reuses `charts/TimeSeries.jsx` with its `alignByTick`.

### 4.5 Saved (later phase)

Lists warehouse runs by experiment id and arm; loads them as arms for comparison, including LLM versus LLM on the same seed. Needs the production Nginx to proxy `/warehouse` (today only `/ws` and `/health`, `frontend-react/nginx.conf`) and queryable experiment columns on the run row. The control arm is deterministic per seed and config, so it can be computed once and reused, giving a live LLM arm the whole household budget.

## 5. Question cards and evidence

Cards were audited against mechanics in `backend/agents.py` and `backend/economy.py` and the checked-in policy sweep in `policy_forecasting/RESULTS.md` (10,000 households, 24 seeds, 80 ticks, effects measured 8 ticks ahead), then smoke-run at newcomer scale (5.1, 5.2). Card copy asks the question and names the trade-off. It never states the expected direction, because the benefits result flips sign between scales. The one exception is a mechanical certainty, such as a higher minimum wage raising the lowest pay.

| Card | Arms | Sweep evidence (10k, 80 ticks) | Verdict | Copy rule |
|---|---|---|---|---|
| What happens if we raise the minimum wage? | baseline vs `minimum_wage_policy=high` | Unemployment −0.021 and distress −0.026, both significant. Wage floor 36 → 50 by construction. | Launch | Name higher pay as the certainty. Treat unemployment, firm stress and prices as things to watch. |
| Do generous benefits keep people out of work? | baseline vs `benefit_level=high` | Unemployment +0.073 significant at 10k over 80 ticks; lower at 1k over 260 ticks (5.1). Distress up at 10k over 80 ticks, down at 1k over 260 ticks. | Launch | Ask, do not answer. Fiscal effect shown as town hall cash. |
| Who really pays when the town hall raises taxes? | `wage_tax_rate=0.30` vs `profit_tax_rate=0.35` | Wage tax: distress +0.040, large. Profit tax: negligible, because firms price it through (`gross_margin = markup / (1 − profit_tax_rate)`). | Hold | Marginal at newcomer scale (5.1). Try the display experiments in 5.3 first. |
| Should the town hall help pay for groceries? | baseline vs `sector_subsidy_target=food`, level 25 | Distress −0.012 significant. Mechanism is a voucher: households pay less, town hall pays the rest, posted price unchanged, firms cash-neutral. | Hold | Nothing visible on posted price (5.1). Needs the out-of-pocket metric from 2.1 before it can ship. |
| Does public works spending create jobs? | baseline vs `public_works=on` | Wired: a public-works firm is created when the lever is on, hiring toward a configured share of the population, gated on treasury cash above a reserve floor. Never run in any sweep. | Hold | Nothing visible on macro outcomes (5.1). Could ship as a "does the public firm survive?" card with jobs and treasury cost as the measures. |

Other levers: rent stabilization, price stabilization, bailouts, infrastructure, technology and social spending are wired but unmeasured and are candidates for later cards. Wealth tax, UBI, birth rate and target inflation are inert and must not get cards.

### 5.1 Smoke run at newcomer scale (2026-09-24)

Every arm above plus public works was run at 1,000 households, 260 ticks, 5 firms per sector (the dashboard default), seeds 1337 and 7, legacy payment sequence. Each arm took 31 to 39 seconds of loop time including per-tick snapshots. Runner: `backend/tools/benchmarks/run_newcomer_smoke.py`. Data and tables: `docs/evals/2026-09-24-newcomer-smoke/`.

**The baseline town has a lot of motion, and it is not a healthy town.** Across both seeds unemployment swung between 0 and about 49 percent and ended near 35 percent, the town hall's cash fell from about $2.7M to below zero by year 4, and average household distress rose from 0.05 to about 0.4. Firms grew from 4 to about 30 as queued competitors entered over the first year, with 6 to 8 ticks on which the firm count fell (the runner counts declining ticks, not individual closures). Homelessness was almost always zero.

| Arm | Visible to a newcomer? | What separates |
|---|---|---|
| `benefit_high` | Yes | Pay higher by 26 to 60 percent, unemployment lower at all ten checkpoints in both seeds, food price higher by $1 to $2. |
| `min_wage_high` | Yes on pay and town hall cash, marginal on unemployment | Pay consistently higher; the only arm whose town hall cash never goes negative (every arm ends above the baseline, which finishes with the least cash of all seven); unemployment lower on trend but often inside the baseline's own swings. |
| `wage_tax_high` | Marginal | Only town hall cash separates. Distress slightly higher at 9 of 10 checkpoints, small against the baseline's range. |
| `profit_tax_high` | No | Every metric noise-level, sign flips between checkpoints and seeds. Matches the 10,000-household finding. |
| `subsidy_food_25` | No | The posted food price shows no consistent separation from baseline in either seed, as the voucher mechanism predicts. Out-of-pocket spend was not measured. |
| `public_works_on` | No on outcomes | A public-works firm appears at tick 0 with 50 reported jobs, reaching 100 only in seed 1337 during ticks 1 to 9 (the configured target at 1,000 households is 200, `backend/config.py:655`). In seed 1337 it exits at tick 246 and is never recreated because the town hall cannot afford the restart; in seed 7 it never exceeds 50 jobs, falls to 7 and ends at 16. Macro lines are indistinguishable from baseline. |

Two seeds and ten checkpoints establish visibility in those runs, not general reliability. The launch cards get a wider seed check in phase 2 using the checked-in runner.

### 5.2 Follow-up runs (2026-09-24)

| Baseline setting | Unemployment final (max) | Firms final, declining ticks | Town hall cash min | Distress final | Homeless peak | Loop time per arm |
|---|---|---|---|---|---|---|
| Legacy, 1,000 households | 37% (49%) | 30, 6 | −$357K | 0.40 | 22 | 31 s |
| `income_first`, 1,000 households | 39% (48%) | 31, 0 | +$60K | 0.60 | 56 | 40 s |
| Legacy, 5,000 households | 23% (46%) | 150, 60 (97 net firm reductions) | −$399K of $13.5M start | 0.42 | 74 | 170 s |

Under `income_first` (the payment revamp, confirmed active via `metrics.payment.coverage = settled_tick_and_live_claims`) the town hall stays solvent and no firm goes bankrupt, but household distress is half again as high and homelessness is sustained. The two launch cards become far more visible: both bring unemployment under 5 percent by years 4 and 5 against a baseline near 40 percent. The minimum-wage arm's homeless peak reaches 113 households, 11 percent of the town. At 5,000 households under legacy, unemployment ends lower and the businesses panel would have 150 firms of churn to show, at about three minutes of loop time per arm.

None of the three baselines is a functioning economy by year five. All end with unemployment above 20 percent and distress around 0.4 or worse. This is a backend calibration matter at these scales that the frontend cannot fix, only report honestly.

**Default world for launch.** Interim default is the legacy sequence at 1,000 households per town: fastest, most motion per second, and the setting the checked-in sweep validated. Baseline calibration at 1,000 households is a backend task to complete before phase 2 reaches newcomers. If `income_first` becomes the default after calibration, the launch cards get more dramatic and the copy must warn about the homelessness side effect.

### 5.3 Cheaper visibility experiments before calibration

To be run with the checked-in runner before any economic-model change, each recorded as matched-seed evidence:

- Food subsidy measured on household out-of-pocket food spend and distress instead of posted price.
- Public works measured on public-works jobs and treasury cost over a two-year horizon.
- Tax cards with fewer starting firms per sector, a shorter horizon, or the strongest values the schema allows.

## 6. Backend changes

Effort ratings come from the audit and were checked against the cited code. These are not all "widenings": items 1, 2, 3 and 6 add protocol and behaviour.

### 6.1 Experiment record and household cap (large)

A server-side experiment registry alongside `SessionRegistry` (`backend/server.py:2865`). SETUP carries `experiment_id`, `arm_label`, `arm_count`, `horizon_tick` and `initial_policy`. The first SETUP for an id creates the record with the arm count and budget; each arm reserves its households atomically; the server rejects a SETUP that would exceed 10,000 in total or duplicate an arm label; reservations are released on disconnect, FINISH or a new SETUP. The record owns the experiment: a second owner is rejected. In phase 1 the run row carries experiment id and arm label inside its existing `tags` and `config_json`; queryable columns (a `SimulationRun` model change in `backend/data/models.py`, migrations for SQLite and Postgres, warehouse manager and integration-test updates) arrive with the Saved phase. Reservations are released on disconnect or a new SETUP, not on FINISH, so EXTEND can resume the retained economy. Failed SETUP rolls the reservation back. The registry assumes a single server worker; a multi-worker deployment needs a shared store and is out of scope.

### 6.2 Initial policy (medium)

`initial_policy` is a lever vector validated by `backend/policy_schema.py` and applied through `GovernmentAgent.set_lever` before the first tick, replacing the two raw tax overrides in `SimulationManager.initialize`. Grouped levers (subsidy target and level, bailout policy, target and budget) validate together. The server acknowledges the applied vector in the SETUP_COMPLETE reply (SESSION is sent when the socket opens, before SETUP, `backend/server.py:3217`, `3246`) so the client can show what actually took effect. Omitted levers keep the schema defaults; the same validation limits apply at start and at runtime.

### 6.3 Horizon, FINISH and EXTEND (medium)

The loop stops at `horizon_tick` and emits `HORIZON_REACHED`. FINISH closes the warehouse run as analysis-ready and keeps the socket. EXTEND raises the horizon and resumes. `STOP` and `START` keep their meanings.

### 6.4 Curated metric projection, all firms, closed-firm archive (medium)

A typed frame projection built once per tick from `econ_metrics`, household stats, prices, diagnostics, government and bank (`backend/server.py:2135`, `2612`), with the fields, units and freshness in section 2.1, plus the new out-of-pocket food metric. The full open-firm list replaces the top-twelve leaderboards; the seven tracked firms stay until the old consumers are gone. Bankrupt firms are removed from `economy.firms` (`backend/economy.py:4964`), so the projection keeps a closed-firm archive with a one-year window (name, sector, closed tick, last staff). `tickComputeMs` today covers the per-tick loop including statistics and tracked-state construction (`backend/server.py:2113`, `2525`) but not serialization; the projection records serialization time separately so the budget in section 8 can be measured.

### 6.5 Event stream (large)

A per-tick `events` array with a typed inventory. Producers that exist today: labor events, healthcare events, regime events (`Economy` per-tick memory, `backend/server.py:1733`), policy actions, LLM decisions, payment loan defaults (`backend/payment_loans.py:308`). Producers to add: firm opened (from tick audit entry ids, `backend/economy.py:2463`), firm closed (from the exit path), shocks (from `_apply_random_shocks`). Each event has a stable id, tick, type, arm-agnostic subject ids and the numbers a template needs. Household-level events are emitted only for the tracked sample; everyone else is counted. Per-tick detail is capped (50 detailed events plus counts) so the projection cannot dominate tick time. The warehouse buffers are not reused as the source because they exist only when the warehouse is enabled (`backend/server.py:1642`).

### 6.6 Household sample and TRACK (large)

Tracked households become a sample of 40 chosen at SETUP, with a TRACK command: `pin` keeps a household and its history across reshuffles; `reshuffle` replaces unpinned members with new random ones whose history starts at the current tick; `follow id` adds a household outside the sample. `recentEvents` is populated from the event stream for tracked households; today the list is initialised and never filled (`backend/server.py:1992`, `2383`). Payment fields (rent arrears, lease renewal) get explicit wire names and are null under the legacy sequence. Sampling and reshuffling draw from a dedicated deterministic RNG, never the session RNG the simulation uses (today tracked-subject selection consumes the same stream, `backend/server.py:1850`, `1988`), and a contract test asserts that a run's economics are identical with and without TRACK activity. Otherwise browsing households would silently change a matched comparison. `follow id` on a full sample evicts the oldest unpinned member; at most eight pins. Tracked-history warehouse row counts and snapshot tests change accordingly.

### 6.7 LLM decision history and truth pairs (large)

A live decision list beside `latest_government_decision` (`backend/server.py:429`). For each indicator the model received, store the indicator name, its source tick, the value shown to the model, the true value at that source tick, and whether it was available, captured where the information constraints are applied (`backend/tools/llm/llm_government.py:129`, `1603`). Rejection and clamp reasons stay machine codes on the wire; the client's rule catalog turns them into sentences. The public rationale is truncated to 500 characters today (`backend/tools/llm/llm_government.py:2399`); phase 3 stores the full public rationale as a separate field and keeps the excerpt for the strip. Contract, live-server and warehouse tests for the LLM path are updated.

### 6.8 Recording tool (medium)

Extend `frontend-react/scripts/capture_fixture.py` to record the whole session: lifecycle messages, SETUP, CONFIG and their receipts, TRACK and EXTEND, schema version, arm identity, every tick frame in order, and error frames. AI fixtures come from a scripted provider (the test suite's `QueueProvider`) or a pinned captured artifact, never a live provider.

## 7. Frontend architecture

- **Experiment store.** One experiment object; per arm a socket, a session generation, connection state and projected facts. Raw frames are not retained: each frame repeats growing history arrays (`backend/server.py:2374`, `2639`) and four arms over 520 ticks of raw frames would run to tens of megabytes. On arrival a frame is projected into per-tick series (one array per metric), a bounded event list, the latest firm and household snapshots and the decision list, then discarded. A derived layer aligns arms by tick, computes deltas against arm one and exposes the cursor. Screens read the derived layer through one adapter, so a backend field rename breaks one place.
- **Reconnect.** A dropped socket marks the arm lost and follows section 3.1. Messages from a previous generation are ignored.
- **Narration module.** Event-to-sentence templates, verdict sentences from deltas and the rule catalog for LLM reason codes, in the string catalog, unit-tested.
- **StoryChart.** A new component: fixed x-domain from tick 0 to the horizon, per-arm colours and markers, end labels with collision avoidance, annotations, shared cursor, empty-future region. `charts/TimeSeries.jsx` cannot do this unchanged: it defaults to the last 250 points and takes its domain from the data (`TimeSeries.jsx:30`, `69`, `179`). Its `alignByTick` helper is reused; the component itself serves only "Show me all the numbers".
- **Components.** Town (with text alternative), StoryChart, StatCard, BusinessList, HouseholdCards, Feed, HowToRead, DecisionStrip, DecisionCard, ReportCard, LeversDrawer, SetupSteps, AllTheNumbers.
- **Replay mode.** Load a recorded session instead of opening sockets. Used for development, tests and demos.
- **Theme.** Keep the CSS-variable and `data-theme` mechanism from `theme/tokens.css`; replace the values. Light default: page `#F3F5F7`, panel `#FFFFFF`, ink `#17202B`. Typefaces Bricolage Grotesque (display) and Instrument Sans (body). Arm colours blue `#2E6FE0` and orange `#E0762C`; AI purple `#6D4AE0`; status green `#2E9E6B`, amber `#C98A1B`, rose `#D64A5E`. All pairs validated with the dataviz palette checker. A dark variant can return later.
- **Keep** the by-tick alignment helper, the Government screen's before/after split pattern (generalised into the decision card and policy markers), and the reduced-motion gating. **Drop** the neural canvases and the ticker.

## 8. Non-functional requirements

- **States.** Setup failure, server full, provider unreachable, arm lost, stale data (no frame for five seconds), empty feed, no firms, incomplete verdict. Each has copy in the catalog that says what happened and what to do.
- **Accessibility.** Keyboard access to every control including the scrubber and drawer; text alternatives for the town drawing and the story chart (a table view); colour never the only carrier of arm or status identity; reduced motion honoured; contrast validated.
- **Performance budget.** Backend, measured in phase 1 with the warehouse on and off at two towns of 1,000 (the gate), two of 5,000 and four of 2,500 households, on the development laptop, reporting p50 and p95: frame size at 1,000 households with 40 tracked households and all firms at most 60 KB; projection and serialization at most 10 percent of loop tick time. Browser, measured in phase 2 with the real store: retained heap for four arms over 520 ticks at most 150 MB; chart re-render on cursor move under 16 ms.
- **Telemetry.** Experiment and arm ids, policy action ids, frame schema version, connection loss and completion status recorded on the run so a verdict and a saved comparison can be traced to their inputs.
- **Deployment.** Nginx proxies `/warehouse` before the Saved phase ships.

## 9. Testing

- Component tests in Vitest against recorded sessions, one per mode.
- A contract test that reads the recorded frame and asserts every field the adapter expects is present with the right type and unit, so backend and frontend cannot drift silently.
- Narration templates and the rule catalog tested as pure functions.
- Backend contract tests for the experiment registry (cap, duplicate arm, release on disconnect), initial policy validation, horizon and FINISH, the event inventory and the TRACK command.
- A benchmark script for the full path (engine plus projection plus send) at 1,000 and 5,000 households with two and four arms, run in phase 1 and recorded under `docs/evals/`.
- The existing browser-driven evidence runner (`backend/tools/integration/run_full_app_evidence.py`) covers the live socket path.

## 10. Phasing

1. Backend, in dependency order: experiment registry and cap; initial policy with SETUP_COMPLETE acknowledgement and CONFIG receipts; horizon, FINISH and EXTEND; household sample and TRACK with the separate RNG; event producers and stream; metric projection with the closed-firm archive and out-of-pocket food; recording tool and fresh fixtures; full-path benchmark. Also: run the existing matched-seed checks through the completed session path so the smoke evidence is known to transfer. Gate: backend budgets in section 8 met at 1,000 households with two arms.
2. Frontend: Set up, the Compare policies Run screen including single-town play, the Town hall drawer, Show me all the numbers, replay mode. Also: baseline calibration decision (5.2) and the wider seed check for the launch cards (5.1).
3. AI mayor: decision history and truth pairs, full rationale storage, provider-failure handling, the AI screen.
4. Saved experiments: queryable experiment columns, `/warehouse` proxy, the Saved screen.

Implementation is delegated to Opus 5.5 subagents from a written plan; Sonnet handles reading and audits. Codex is used only when asked.

## 11. Risks and open items

- Every tested default world ends five years as a depression (sections 5.1 and 5.2): 23 to 39 percent unemployment, distress 0.4 to 0.6, and either an insolvent town hall or sustained homelessness. The newcomer's first impression of an untouched town depends on backend calibration that this design does not own. Decide the default world and calibrate the baseline before phase 2 reaches newcomers. The data-driven lead and verdict sentences keep the screen honest in the meantime.
- The `income_first` payment sequence trades government solvency for household distress. Whether that is intended is a question for the economic-model owner, outside this design.
- The internal `public_debt` metric used by `fiscal_guards.py` and `get_economic_metrics()` is inert, so debt-to-GDP style guards see zero debt. Backend concern outside this design.
- LLM mode needs a reachable provider. The evidence audit checks cited figures, not reasoning quality; the report card must not imply more.
- `openwiki/frontend/dashboard.md` describes the pre-rebuild monolith and `docs/MODEL_SCOPE.md` says the economy is not being redesigned. Both are stale; a wiki refresh is due after implementation.
- `docs/superpowers/specs/2026-09-06-frontend-command-center-design.md` is superseded by this document.
