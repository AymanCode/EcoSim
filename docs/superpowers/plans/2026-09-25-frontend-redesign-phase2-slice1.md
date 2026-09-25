# Frontend Redesign Phase 2, Slice 1: The Run Screen from Recorded Towns

> **For agentic workers:** execute task by task; each task ends in one commit. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A new, newcomer-friendly Run screen that plays two matched towns side by side from recorded sessions: the town drawing, businesses ranked richest first, household cards, an annotated full-horizon story chart, a verdict, stat cards and a plain-language event feed, with play, pause and scrubbing. It works without the Python backend.

**Architecture:** A new app under `frontend-react/src/next/`, opened at `?view=next`; the existing dashboard stays the default until the new one is complete. A pure data layer turns recorded frame-2 sessions (JSON Lines from `frontend-react/scripts/record_session.py`, lean profile) into per-town series and per-tick snapshots; a pure narration layer turns numbers and events into sentences; presentational components port the approved mockups to React.

**Tech Stack:** React 19, Vite 8, Vitest with Testing Library and jsdom, plain CSS scoped under `.nx` (no new dependencies). Node 22 via `npx --yes node@22`.

**Spec:** `docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md` sections 2, 4.2, 7, 8. **Visual source of truth:** `docs/superpowers/specs/2026-09-24-mockups/02-run-compare-policies.html` (layout, CSS, the town SVG, the story chart and card markup are working reference code to port). **Data contract:** `docs/WEBSOCKET_PROTOCOL.md` and the fixture `frontend-react/src/test/fixtures/session-compare-small.jsonl`.

## Global Constraints

- Branch `feat/frontend-redesign-phase2`. Commands run from `frontend-react/`: tests `npx --yes node@22 node_modules/.bin/vitest run`, lint `npx --yes node@22 node_modules/.bin/eslint src/next`, build `npx --yes node@22 node_modules/.bin/vite build`. All three must pass before each commit; the existing 91 Vitest tests keep passing.
- Do not modify the existing dashboard (`src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/`, `src/charts/`, `src/theme/`) except the one routing line in `src/main.jsx`. Reusing `src/charts/useMeasured.js` by import is allowed.
- All new styles live in `src/next/next.css`, every selector scoped under `.nx`. Tokens from the spec: page `#F3F5F7`, panel `#FFFFFF`, panel2 `#EEF1F4`, ink `#17202B`, ink2 `#3D4753`, ink3 `#6E7A87`, ink4 `#9AA5B1`, line `#E3E7EB`, line2 `#CFD6DD`, town A `#2E6FE0`, town B `#E0762C`, towns C and D `#199E70` and `#9085E9`, working `#2E9E6B`, looking `#C98A1B`, lost home `#D64A5E`, slate `#B6BFC9`, slate2 `#8B96A2`. Typefaces Bricolage Grotesque (display) and Instrument Sans (body) from Google Fonts, loaded by an `@import` at the top of `next.css`.
- Motion only where it shows change (house colours, bar widths, the chart's cursor), 300 to 500 ms, and nothing animates under `prefers-reduced-motion: reduce`.
- Every viewer-facing string for metrics, levers and events comes from `src/next/catalog.js` or `src/next/narration.js`, not from component bodies.
- Accessibility: every control is a real button or input with a label; the town drawing and story chart each have a text alternative (visually hidden list or table).
- Tests read the fixture with `fs.readFileSync(new URL('../../test/fixtures/session-compare-small.jsonl', import.meta.url), 'utf8')` (adjust the relative path to the test file's location).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task A: Data, names, catalog and narration layers

**Files (create):** `src/next/data/session.js`, `src/next/data/derive.js`, `src/next/names.js`, `src/next/catalog.js`, `src/next/narration.js`, tests beside them in `src/next/__tests__/`.

**Interfaces:**

```js
// session.js
parseSession(text) -> { header, messages }          // JSON Lines; messages = message payloads of kind "message", wire order
buildArm(session, { label, color }) -> Arm
// Arm = {
//   label, color,
//   setup: header.setup,                             // includes initial_policy, seed, num_households
//   horizon: number,                                 // SETUP_COMPLETE.config.horizon_ticks, else header.setup.horizon_ticks, else the last tick
//   profiles: { [id]: traits },                      // SETUP_COMPLETE.trackedProfiles merged with every TRACKED.profiles
//   ticks: number[],                                 // tick of each frame, ascending
//   series: { [curatedKey]: (number|null)[] },       // one entry per tick, from frame.curated
//   snapshots: { [tick]: { firms, subjects, firmsClosed, eventCounts } },
//   events: Event[],                                 // frame.events concatenated in order
//   policyChanges: { tick, policy, value }[],        // from events of type policy_changed, text "policy=value"
// }

// derive.js
commonTicks(arms) -> number[]                         // ticks present in every arm, ascending
valueAt(arm, key, tick) -> number|null                // value at the last recorded tick <= tick
snapshotAt(arm, tick) -> snapshot|null                // same rule
seriesUpTo(arm, key, tick) -> { tick, value }[]
compareAt(arms, key, tick) -> { label, color, value, deltaVsFirst }[]   // deltaVsFirst null for the first arm
eventsUpTo(arm, tick, limit) -> Event[]               // newest first

// names.js  (deterministic; the same id gives the same name in every town)
householdName(id) -> string                           // a first name from a fixed list of at least 60, by id
firmDisplayName(firm) -> string                       // firm = { id, name, sector, isBaseline }; baseline -> "Town <Sector> Co-op"; others from a per-sector list of at least 12 names by id

// catalog.js
METRICS = { [curatedKey]: { name, meaning, format: 'per100'|'money'|'price'|'ratio'|'count', better: 'lower'|'higher'|null } }
  // at least: peopleOutOfWorkPer100, typicalWeeklyPay, priceFood, foodSpendPerHousehold, gini, townHallCash,
  // homelessHouseholds, firmsOpen, firmsStruggling, careDenials, bankDefaultsTotal; wording from spec section 2.1
LEVERS = { [lever]: { name, values: { [value]: phrase } } }   // all 17 levers of backend/policy_schema.py
formatMetric(key, value) -> string                    // null -> "not measured"; per100 -> "9 in 100"; money -> "$2,144"; price -> "$4.71"; ratio -> "0.41"; count -> "12"
describePolicy(initialPolicy) -> string               // {} -> "no changes"; {minimum_wage_policy:'high'} -> "a higher minimum wage"; several -> joined with "and"

// narration.js
weekLabel(tick) -> string                             // tick 1 -> "Year 1, week 1"; tick 52 -> "Year 1, week 52"; tick 53 -> "Year 2, week 1"
leadSentence(arms, tick) -> string
verdict(arms, tick) -> string                          // ends with a question mark when there are two or more towns
eventSentence(event, { householdName, firmName }) -> string
```

**Narration rules:** one town: `"<weekLabel>. <per100> people are out of work and typical weekly pay is <money>."` Two or more towns, comparing each town after the first with the first on `peopleOutOfWorkPer100` (lower is better) and `typicalWeeklyPay` (higher is better): `"<Town B> has fewer people out of work than <Town A> (<x> vs <y>) and pays more (<$> vs <$>)."`, using "about the same" when the gap is under 0.5 per 100 or under 1 percent of pay. The verdict names the second town's policy with `describePolicy` and ends `"Would you keep <policy>?"`. Event sentences, one per type, using friendly names: firm_opened "<firm> opened.", firm_closed "<firm> closed.", hired "<household> started work at <firm>.", laid_off "<household> lost their job at <firm>.", care_denied "<household> couldn't afford a doctor.", care_completed "<household> saw a doctor.", policy_changed "The town hall set <lever name> to <value phrase>.", loan_default "A loan went unpaid.", shock by text (`shock_demand` "Households had an unexpected windfall or bill.", `shock_supply` "A supply problem hit some businesses.", `shock_health` "An illness went around."), regime "<text with underscores replaced by spaces, first letter capitalised>.".

- [ ] **Step 1:** write the tests (fixture-based for session and derive; table tests for names, catalog and narration), including: `parseSession` returns the header and 24 frames; `buildArm` has 24 ticks, `series.peopleOutOfWorkPer100.length === 24`, profiles for the tracked ids, and the one `policy_changed` event recorded in the fixture; `valueAt` before the first tick is null; `compareAt` gives `deltaVsFirst` null for the first arm and a number for the second (use the fixture twice with labels "Town A" and "Town B" and a doctored second series); `householdName(7) === householdName(7)` and differs from `householdName(8)`; `formatMetric('peopleOutOfWorkPer100', 9.2) === '9 in 100'`; `formatMetric('typicalWeeklyPay', 2144.4) === '$2,144'`; `formatMetric('gini', null) === 'not measured'`; `describePolicy({minimum_wage_policy: 'high'}) === 'a higher minimum wage'`; `weekLabel` cases above; `verdict` ends with `?` for two towns; one sentence per event type.
- [ ] **Step 2:** run them and see them fail; implement; run them and see them pass; lint; build.
- [ ] **Step 3:** commit `feat(next): data, naming, catalog and narration layers for the new Run screen`.

---

### Task B: Visual components

**Files (create):** `src/next/next.css`, `src/next/components/Town.jsx`, `BusinessList.jsx`, `HouseholdCards.jsx`, `StatCard.jsx`, `Feed.jsx`, `HowToRead.jsx`, tests in `src/next/__tests__/`.

**Port from the mockup** (`02-run-compare-policies.html`): the CSS for `.town`, `.card`, `.legend`, `.facts`, `.biz`, `.brow`, `.tag`, `.hh`, `.hgrid`, `.hc`, `.chip`, `.stat`, `.feed` (renamed under `.nx`), and the `townSVG` drawing.

**Interfaces and behaviour:**
- `<Town arm tick />`: SVG town from the mockup. Houses: 100 icons; lost-home count `round(100 * homelessHouseholds / householdsTotal)`, looking count `round(peopleOutOfWorkPer100)`, the rest working. Assign each house a stable random rank from a seeded generator (mulberry32 seeded with `arm.setup.seed`), give "lost home" to the lowest ranks and "looking" to the next, so when numbers move only a few houses change colour; fill changes transition. Main street: open firms from `snapshotAt(arm, tick).firms` sorted by id (stable positions), height by staff relative to the busiest firm, amber flag when `state === 'struggling'`; firms in `firmsClosed` drawn as dashed crossed-out lots after them; at most 16 buildings, then a "+N more" label. Under the drawing: legend and three facts (people out of work, typical weekly pay, firms open with struggling and closed counts). A visually hidden list repeats the counts.
- `<BusinessList arm tick max={7} />`: open firms richest first with friendly names (`firmDisplayName`), sector, a cash bar scaled to the richest, staff, and a status tag Growing, Steady or Struggling; then firms closed in the last year, faded, tagged Closed. "See all N" toggles showing every firm.
- `<HouseholdCards arm tick />`: four tracked households at a time, avatar initial and colour by state (working if `isEmployed`, looking if `canWork` and not employed, lost home if `housingSecurity === false`), friendly name and age, job line (employer's friendly name or "Looking for work"), savings, and one sentence: the latest event for that household up to `tick` through `eventSentence`, else a state sentence. "Show me four others" cycles through the sample; "Follow" pins a card to the first slot (local state).
- `<StatCard metricKey arms tick />`: catalog name, each town's value with a colour key, a sparkline per town up to `tick` on a shared scale, and the catalog meaning.
- `<Feed arms tick limit={8} />`: newest first across towns, each row coloured by town, week label and sentence.
- `<HowToRead armCount />`: the four first-timer notes from the mockup, adapted when there is one town.

- [ ] **Step 1:** tests render each component with an arm built from the fixture and assert: 100 house shapes and the legend; buildings count ≤ 17 including the "+N" label; business rows sorted by cash descending with friendly names; four household cards and that "Show me four others" changes the first name shown; stat card shows two values for two arms; feed rows are newest first.
- [ ] **Step 2:** red, implement, green, lint, build.
- [ ] **Step 3:** commit `feat(next): town drawing, businesses, households, stat cards and feed`.

---

### Task C: Story chart, replay, Run screen and the two-town demo

**Files (create):** `src/next/components/StoryChart.jsx`, `HorizonBar.jsx`, `src/next/useReplay.js`, `src/next/RunScreen.jsx`, `src/next/NextApp.jsx`, demo recordings in `frontend-react/public/demo/`, tests. **Modify:** `src/main.jsx` (render `NextApp` when `new URLSearchParams(window.location.search).get('view') === 'next'`, else the existing `App`).

**Behaviour:**
- `<StoryChart arms metricKey tick horizon onMetricChange />`: port the mockup's story chart: x from tick 0 to `horizon` with the future beyond `tick` shaded and labelled "the weeks ahead", one line per town up to `tick`, end labels with collision avoidance showing each town's current value, a triangle marker per policy change in the town's colour with a short label, year ticks on the x-axis, "N in 100" or money ticks on the y-axis from the catalog format, and metric chips (people out of work, typical weekly pay, a week of groceries, gap between rich and poor, town hall cash). Width from `useMeasured`. A visually hidden table lists each town's value at every 13th tick.
- `useReplay({ maxTick })` -> `{ tick, playing, play, pause, toggle, scrub(t), speed, setSpeed }`: starts at tick 1 paused; playing advances about 8 ticks per second at speed 1 (speeds 0.5, 1, 2, 4), stops at `maxTick`; `scrub` clamps to 1..maxTick.
- `<HorizonBar tick horizon maxTick playing onToggle onScrub speed onSpeed />`: a labelled range input over 1..maxTick styled as the mockup's horizon bar with year marks, the play/pause button, speed buttons, and the week label.
- `<RunScreen arms />`: the mockup layout: lead sentence; two matching columns (one per town, each with Town, BusinessList, HouseholdCards) or one column for a single town; the story chart with verdict and four stat cards beside it (people out of work, typical weekly pay, a week of groceries, gap between rich and poor); the feed beside HowToRead. The horizon bar sticks to the top.
- `NextApp`: fetches `/demo/town-a.jsonl` and `/demo/town-b.jsonl`, builds two arms (labels "Town A" and "Town B", colours from the tokens), shows a loading state and a plain error message with the fix ("Demo data missing: run the recorder commands in docs/superpowers/plans/2026-09-25-frontend-redesign-phase2-slice1.md"), then renders `RunScreen` under `<div className="nx">`. A small header shows "EcoSim", the experiment question (from `describePolicy` of Town B: "What happens with <policy>?") and a link back to the classic dashboard (`?view=classic`).
- **Demo recordings** (run from the repository root, lean profile is the recorder default):
  - `ECOSIM_ENABLE_WAREHOUSE=0 .venv/bin/python frontend-react/scripts/record_session.py --households 500 --ticks 104 --tracked 12 --seed 1337 --firms 5 --experiment demo-minwage --arm "Town A" --arms 2 --owner demo --out frontend-react/public/demo/town-a.jsonl`
  - the same with `--arm "Town B" --initial-policy '{"minimum_wage_policy":"high"}' --out frontend-react/public/demo/town-b.jsonl`
  - Budget: each file at most 3 MB. If larger, lower `--households` to 300 and re-record; record the final sizes in the task report.

- [ ] **Step 1:** tests: `useReplay` advances with fake timers, clamps scrub, stops at maxTick; `StoryChart` renders one path per town and a marker per policy change; `RunScreen` with two fixture arms renders two town columns, the lead sentence and the verdict, and scrubbing via the range input changes the week label; with one arm it renders one column and no verdict question.
- [ ] **Step 2:** red, implement, green; record the demo files; lint; build; run the dev server once (`npx --yes node@22 node_modules/.bin/vite --port 5199` from `frontend-react/`) and confirm `http://localhost:5199/?view=next` loads the demo without console errors (report what you checked; stop the server afterwards).
- [ ] **Step 3:** commit `feat(next): story chart, replay controls and the two-town Run screen with a recorded demo`.
