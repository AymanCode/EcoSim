# Frontend Redesign Phase 2, Slice 2: Set Up and Live Towns

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Execute task by task; each task ends in one commit. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A newcomer can open `?view=next`, pick a question (or just play with one town), press Start, and watch one to four live towns run on the real simulation. While they run, the newcomer can pause, pull levers in a Town hall drawer and see receipts, meet other families, and add a year at the end. The recorded demo stays one click away.

**Architecture:** A framework-free experiment controller (`src/next/live/experiment.js`) opens one WebSocket per town and speaks the frame-2 protocol. It feeds every message into the slice-1 arm model (`createArm`/`ingest`) and publishes a plain state object. A thin hook throttles that state into React. The Setup screen is a pure plan builder plus presentational components. The existing `RunScreen` gains an optional `live` prop, so replay mode is unchanged.

**Tech Stack:** React 19, Vite 8, Vitest with Testing Library and jsdom, plain CSS scoped under `.nx`. No new dependencies. Node 22 via `npx --yes node@22`.

**Spec:** `docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md`, sections 3, 3.1, 4.1, 4.2 and 5. **Visual source:** `docs/superpowers/specs/2026-09-24-mockups/01-setup.html` for Set up, and the slice-1 Run screen for everything else. **Wire contract:** `docs/WEBSOCKET_PROTOCOL.md`; lever values come from `backend/policy_schema.py`; group rules come from `backend/policy_vectors.py:58` (`policy_group_errors`).

## Global Constraints

- **Branch and checks.** Work on branch `feat/frontend-redesign-phase2` and run commands from `frontend-react/`:
  - tests: `npx --yes node@22 node_modules/.bin/vitest run`
  - lint: `npx --yes node@22 node_modules/.bin/eslint src/next`
  - build: `npx --yes node@22 node_modules/.bin/vite build`
  
  All three pass before each commit. Every existing test (253) keeps passing, and a test changes only where this plan says so.
- **Off-limits code.**
  - Do not modify backend code in this slice. If the protocol behaves differently from `docs/WEBSOCKET_PROTOCOL.md`, stop and report it.
  - Do not modify the classic dashboard (`src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/`, `src/charts/`, `src/theme/`) or `src/main.jsx`.
- **Styles.** They live in `src/next/next.css`, scoped under `.nx`, and use only the existing tokens. Every text colour meets the contrast test in `src/next/__tests__/contrast.test.js`; extend that test for any new text token.
- **Copy.** Every viewer-facing string comes from `src/next/catalog.js` (`COPY`, `LEVERS`, `QUESTIONS`) or `src/next/narration.js`.
  - Plain language for a newcomer: "town", "families", "businesses", "town hall", "rules".
  - Seeds are shown only as "Town #48213". A seed field exists only under "Build my own".
- **Motion.** Motion is used only where it shows change, runs 300–500 ms, and is off under `prefers-reduced-motion: reduce`.
- **Accessibility.** Controls are real buttons or inputs with labels. Toggles use `aria-pressed`, the drawer is an `<aside>` with a label, and status and error lines use `role="status"` or `role="alert"`.
- **Sockets.** A socket is opened only by a user action (Start), never in a render or an effect, so React StrictMode cannot double-open one.
- **Commits.** Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Backend not running**, or running on another port. Expected: Start shows "The simulation isn't running on this computer" with the start command and a button to watch the recorded example, and it leaves no sockets open. (Task D test 8, Task F test 3)
2. **StrictMode.** In development React mounts effects twice. Expected: exactly one socket per town. (Task F test 2)
3. **Leaving mid-run.** Choosing "New experiment" while towns run. Expected: every socket closes, and a message that arrives later changes nothing. (Task D test 11)
4. **Too many households after adding a town.** Going from 2 towns at 5,000 households to 3 towns. Expected: households clamp to the new cap (3,300), and the Start estimate updates. (Task E test 3)
5. **A lever change sent while paused.** The server answers `CONFIG_APPLIED` with no `CONFIG_QUEUED`. Expected: the receipt still reads applied. (Task D test 10)

---

### Task D: Live data layer (plan, controller, hook)

**Files:**
- Create:
  - `src/next/live/plan.js`, `src/next/live/endpoint.js`, `src/next/live/experiment.js`, `src/next/live/useExperiment.js`
  - `src/next/__tests__/fakeSocket.js`
  - `src/next/__tests__/plan.test.js`, `src/next/__tests__/experiment.test.js`, `src/next/__tests__/useExperiment.test.jsx`
- Modify:
  - `src/next/data/session.js`: keep `arm.policy` and `arm.receipts`, and export `addPendingConfig`.
  - `src/next/catalog.js`: add `DEFAULT_POLICY` and `LEVER_OPTIONS`.
  - `src/next/__tests__/session.test.js` (additions only).

**Interfaces (produced):**

```js
// catalog.js
DEFAULT_POLICY = { wage_tax_rate: 0.15, profit_tax_rate: 0.2, investment_tax_rate: 0.1, benefit_level: 'neutral',
  public_works: 'off', minimum_wage_policy: 'neutral', sector_subsidy_target: 'none', sector_subsidy_level: 0,
  infrastructure_spending: 'none', technology_spending: 'none', social_spending: 'medium',
  price_stabilization_target: 'none', price_stabilization_level: 'off', rent_stabilization_level: 'off',
  bailout_policy: 'off', bailout_target: 'none', bailout_budget: 0 }   // the tick-1 governmentPolicy of an unchanged town
LEVER_OPTIONS = {                         // copied exactly from backend/policy_schema.py; numbers stay numbers
  wage_tax_rate: { min: 0, max: 0.5 }, profit_tax_rate: { min: 0, max: 0.5 }, investment_tax_rate: { min: 0, max: 0.3 },
  benefit_level: ['low', 'neutral', 'high', 'crisis'], minimum_wage_policy: ['low', 'neutral', 'high'],
  sector_subsidy_level: [0, 10, 25, 50], infrastructure_spending: ['none', 'low', 'medium', 'high'],
  technology_spending: ['none', 'low', 'medium', 'high'], social_spending: ['none', 'low', 'medium', 'high'],
  price_stabilization_level: ['off', 'monitor', 'soft', 'strict'], rent_stabilization_level: ['off', 'monitor', 'soft', 'strict'],
  bailout_policy: ['off', 'sector', 'all'], bailout_budget: [0, 5000, 10000, 25000, 50000], public_works: ['off', 'on'],
  sector_subsidy_target: ['none', 'food', 'housing', 'services', 'healthcare'],
  price_stabilization_target: ['none', 'food', 'services', 'healthcare'],
  bailout_target: ['none', 'food', 'housing', 'services', 'healthcare'] }

// session.js (additions)
// arm.policy: null | the latest frame's metrics.governmentPolicy (all 17 levers)
// arm.receipts: Receipt[] in send order
// Receipt = { actionId: string|null, status: 'sending'|'queued'|'applied'|'failed', requested: {}, applied: {},
//             rejected: { [lever]: reason }, effectiveTick: number|null, message: string|null }
addPendingConfig(arm, levers) -> Receipt            // pushes { status: 'sending', requested: levers, ... }
// ingest handles CONFIG_QUEUED and CONFIG_APPLIED: match by actionId; if no receipt has that actionId,
// adopt the oldest 'sending' receipt; if there is none, create one. QUEUED -> status 'queued';
// APPLIED -> status 'applied' with applied, rejected, effectiveTick.
failPendingConfig(arm, message) -> Receipt|null     // oldest 'sending' receipt -> 'failed' with message

// live/plan.js
TOWN_LABELS = ['Town A', 'Town B', 'Town C', 'Town D']
YEARS = [1, 2, 5, 10]
HOUSEHOLD_STEP = 100
householdCap(townCount) -> number                   // floor(10000 / n / 100) * 100: 1->10000, 2->5000, 3->3300, 4->2500
estimateSeconds({ households, towns, years }) -> number
                                                    // 51.6 * (households * towns / 2000) * (years * 52 / 260)
                                                    // (frame bench, 2 x 1,000 households x 260 weeks = 51.6 s)
estimatePhrase(seconds) -> string                   // < 40 'Under a minute.'; < 90 'About a minute.'; else `About ${Math.round(s / 60)} minutes.`
rollSeed(random = Math.random) -> number            // integer in 1..99999
policyChanges(vector) -> {}                         // only the levers whose value differs from DEFAULT_POLICY
// Plan = { mode: 'compare'|'play', questionId: string|null, towns: [{ label, color, policy /* full vector */ }],
//          households, years, seed }
setupConfigs(plan, { experimentId, owner }) -> config[]   // one per town, in order:
  // { num_households, seed, horizon_ticks: years * 52, initial_policy: policyChanges(town.policy),
  //   frame_profile: 'lean', enable_llm_government: false,
  //   experiment_id, arm_label: town.label, arm_count: towns.length, experiment_owner: owner }

// live/endpoint.js
resolveSocketUrl(env = import.meta.env, location = window.location) -> string
                                                    // env.VITE_WS_URL trimmed if set; else `${wss|ws}://${host}/ws`; else 'ws://localhost:8002/ws'
newExperimentId(now = Date.now(), random = Math.random) -> string   // `exp-${now.toString(36)}-${Math.floor(random() * 36 ** 6).toString(36).padStart(6, '0')}`
ownerId() -> string                                 // stable per tab: sessionStorage 'ecosim-owner' (try/catch), else a module-level random id

// live/experiment.js
LEAD_PAUSE = 3      // a town this many weeks ahead of the slowest running town gets STOP
LEAD_RESUME = 0     // and START again once the slowest has caught up
createExperiment({ plan, url, experimentId, owner, WebSocketImpl, onChange }) -> Controller
// Controller:
//   connect()                  opens one socket per town. On SESSION it sends that town's SETUP.
//                              Once every town has SETUP_COMPLETE it sends START to every town.
//   pause() / resume()         pause sends STOP to running towns. resume sends START to towns that are
//                              not held and not at the horizon, then re-checks alignment.
//   extend(weeks)              EXTEND { ticks: weeks } to every town.
//   configure(index, levers)   addPendingConfig on that arm, then CONFIG { config: levers } to that town.
//   track(index, action, householdId)   TRACK { action, householdId } to that town.
//   close()                    closes every socket (code 1000); every later message and event is ignored.
//   getState() -> State
// State = { experimentId, phase, arms, liveTick, towns, error }
//   phase: 'connecting' | 'running' | 'paused' | 'horizon' | 'finished' | 'lost' | 'failed' | 'closed'
//   arms: a NEW array of shallow arm copies ({ ...arm }) on every publish, so memoised children see a change
//   liveTick: the lowest latest tick over the towns (0 before any frame)
//   towns: [{ label, status: 'connecting'|'ready'|'running'|'held'|'stopped'|'horizon'|'finished'|'lost',
//             lastTick, notice: string|null }]
//   error: null | { kind: 'full'|'unreachable'|'setup'|'lost', town: label|null, message: string }
// onChange(state) is called synchronously after every handled message and after every command.

// live/useExperiment.js
useExperiment({ WebSocketImpl = globalThis.WebSocket, url } = {}) -> {
  state,                         // State | null before start
  start(plan), pause(), resume(), extend(weeks), configure(index, levers), track(index, action, id),
  leave(),                       // controller.close(); state -> null
}
// Publishes controller state at most once per 100 ms (leading and trailing: the newest state always arrives).
// Closes the controller on unmount.
```

**Controller rules (exact):**
- **Message routing.** Every message goes to that town's arm through `ingest`. A message with `error` and no `type` is routed by its prefix:
  - Before `SESSION`: the town fails with kind `full` when the text contains `Maximum active simulation sessions`, otherwise with the raw text as kind `unreachable`.
  - `SETUP failed: <reason>`: kind `setup`, with the message `<reason>`.
  - `CONFIG failed: <reason>`: `failPendingConfig(arm, reason)`.
  - Anything else: sets `towns[i].notice`.
- **Failure while connecting.** Any failure during `connecting` (an error, or a socket `close`/`error` event before `SETUP_COMPLETE`) closes every socket, which releases the server's household reservations, and sets phase `failed`. A close before `SESSION` with no error text is kind `unreachable` with the message `''`.
- **Unexpected close after `SETUP_COMPLETE`.** That town becomes `lost` and the error is `{ kind: 'lost', town: label, message: '' }`. STOP goes to every other running town, and the phase becomes `lost`.
- **Alignment.** After each frame, `slowest` is the minimum `lastTick` over towns whose status is `running` or `held`.
  - A `running` town with `lastTick - slowest >= LEAD_PAUSE` gets STOP and status `held`.
  - A `held` town with `lastTick - slowest <= LEAD_RESUME` gets START and status `running`, unless the user paused.
- **Horizon.** `HORIZON_REACHED` sets status `horizon`. When every town is at `horizon`, FINISH goes to each town once and the phase becomes `horizon`. `FINISHED` sets status `finished`, and phase `finished` follows once every town is finished. `EXTENDED` sets status `running`, clears the user pause and makes the phase `running`.
- **Phase precedence.** `failed` > `closed` > `lost` > `finished` > `horizon` > `connecting` (until START is sent) > `paused` (user paused) > `running`.

- [ ] **Step 1: Write the fake socket** (`__tests__/fakeSocket.js`):

```js
// A WebSocket stand-in: tests push server messages and read what the client sent.
export function fakeSocketFactory() {
  const sockets = []
  class FakeSocket {
    constructor(url) { this.url = url; this.sent = []; this.readyState = 0; this.closedWith = null; sockets.push(this) }
    send(text) { this.sent.push(JSON.parse(text)) }
    close(code = 1000) { if (this.readyState === 3) return; this.readyState = 3; this.closedWith = code; this.onclose?.({ code }) }
    // test helpers
    open() { this.readyState = 1; this.onopen?.({}) }
    receive(message) { this.onmessage?.({ data: JSON.stringify(message) }) }
    serverClose(code = 1006) { this.readyState = 3; this.onclose?.({ code }) }
    fail() { this.onerror?.({}); this.serverClose(1006) }
    commands() { return this.sent.map(message => message.command) }
  }
  return { FakeSocket, sockets }
}
```

- [ ] **Step 2: Write the failing tests.** In `plan.test.js`:
  - `householdCap` for 1 to 4 towns.
  - `estimatePhrase(estimateSeconds({ households: 1000, towns: 2, years: 5 }))` is `'About a minute.'`.
  - One town of 500 households for one year is `'Under a minute.'`.
  - Four towns of 2,500 households for ten years is `'About 9 minutes.'` (516 s).
  - `policyChanges({ ...DEFAULT_POLICY, minimum_wage_policy: 'high' })` deep-equals `{ minimum_wage_policy: 'high' }`.
  - `setupConfigs` for a two-town plan returns exactly the two configs described above.
  - `newExperimentId(0, () => 0.5)` is `'exp-0-i00000'`.

  `experiment.test.js` covers the numbered cases below, each with `fakeSocketFactory`:

```js
import { describe, expect, it } from 'vitest'
import { createExperiment } from '../live/experiment.js'
import { DEFAULT_POLICY } from '../catalog.js'
import { fakeSocketFactory } from './fakeSocket.js'

const plan = {
  mode: 'compare', questionId: 'minimum-wage', households: 200, years: 1, seed: 4242,
  towns: [
    { label: 'Town A', color: '#2E6FE0', policy: { ...DEFAULT_POLICY } },
    { label: 'Town B', color: '#E0762C', policy: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } },
  ],
}
const frame = (tick, extra = {}) => ({ tick, metrics: { trackedSubjects: [], governmentPolicy: DEFAULT_POLICY }, curated: {}, firms: [], events: [], ...extra })

function boot() {
  const { FakeSocket, sockets } = fakeSocketFactory()
  const states = []
  const exp = createExperiment({ plan, url: 'ws://test/ws', experimentId: 'exp-t', owner: 'me', WebSocketImpl: FakeSocket, onChange: s => states.push(s) })
  exp.connect()
  sockets.forEach(s => s.open())
  return { exp, sockets, states }
}
function ready({ sockets }) {
  sockets.forEach((s, i) => { s.receive({ type: 'SESSION', sessionId: `s${i}` }); s.receive({ type: 'SETUP_COMPLETE', config: {} }) })
}

it('1. sends each town its SETUP after SESSION and STARTs only when every town is set up', () => {
  const t = boot()
  expect(t.sockets).toHaveLength(2)
  t.sockets[0].receive({ type: 'SESSION', sessionId: 'a' })
  expect(t.sockets[0].sent[0]).toEqual({ command: 'SETUP', config: expect.objectContaining({ arm_label: 'Town A', arm_count: 2, experiment_id: 'exp-t', frame_profile: 'lean', initial_policy: {} }) })
  t.sockets[0].receive({ type: 'SETUP_COMPLETE', config: {} })
  expect(t.sockets[0].commands()).not.toContain('START')
  t.sockets[1].receive({ type: 'SESSION', sessionId: 'b' })
  expect(t.sockets[1].sent[0].config.initial_policy).toEqual({ minimum_wage_policy: 'high' })
  t.sockets[1].receive({ type: 'SETUP_COMPLETE', config: {} })
  expect(t.sockets.map(s => s.commands().at(-1))).toEqual(['START', 'START'])
  expect(t.exp.getState().phase).toBe('running')
})
```

  Write the remaining cases in the same style:
  2. **Frames.** Frames reach the arms, `liveTick` is the lower of the two last ticks, and `arm.policy` is the frame's `governmentPolicy`.
  3. **Alignment.**
     - Town A at tick 4 and Town B at 1: A gets STOP and status `held`.
     - B reaches 4: A gets START and status `running`.
     - A town 2 weeks ahead is not held.
  4. **Pause and resume.**
     - `pause()` sends STOP to both towns.
     - `resume()` sends START to both, except a town at `horizon`, which gets nothing.
     - While paused, a held town that is caught up does not get START.
  5. **Horizon.**
     - Only one town sends `HORIZON_REACHED`: no FINISH.
     - Both towns send it: exactly one FINISH each, and the phase is `horizon`.
     - `FINISHED` from both: phase `finished`.
     - `extend(52)` sends `{ command: 'EXTEND', ticks: 52 }` to both towns.
     - `EXTENDED` from both: phase `running`.
  6. **Full server.**
     - Before `SESSION`, socket 0 receives `{ error: 'Maximum active simulation sessions reached (8)' }` and then `serverClose(1013)`.
     - Result: phase `failed`, error kind `full`, and every socket's `readyState` is 3.
  7. **Failed SETUP.**
     - After `SESSION`, socket 1 receives `{ error: 'SETUP failed: 6000 households exceeds the per-arm cap of 5000 for 2 arms' }`.
     - Result: phase `failed`, kind `setup`, a message starting with `6000 households`, and every socket closed.
  8. **Unreachable.**
     - `sockets[0].fail()` before `SESSION`.
     - Result: phase `failed`, kind `unreachable`, and every socket closed.
  9. **Lost.**
     - After running, `sockets[1].serverClose()`.
     - Result: phase `lost`, error `{ kind: 'lost', town: 'Town B' }`, and socket 0's last command is STOP.
  10. **Receipts.**
      - `configure(1, { minimum_wage_policy: 'low' })` sends CONFIG and adds a `sending` receipt.
      - `CONFIG_QUEUED { actionId: 'x1' }` makes it `queued`.
      - `CONFIG_APPLIED { actionId: 'x1', applied: {...}, rejected: {}, effectiveTick: 7 }` makes it `applied`.
      - While paused, `CONFIG_APPLIED { actionId: 'x2' }` alone adopts the new `sending` receipt and marks it `applied`.
      - `{ error: 'CONFIG failed: the run is finished; ...' }` marks the oldest `sending` receipt `failed`.
  11. **Leaving.**
      - `close()` closes every socket with code 1000 and sets phase `closed`.
      - A frame received afterwards changes neither `liveTick` nor the arms.
      - `onChange` is not called again.
  12. **Track.** `track(0, 'reshuffle')` sends `{ command: 'TRACK', action: 'reshuffle' }`. `track(0, 'pin', 17)` sends `{ command: 'TRACK', action: 'pin', householdId: 17 }`.

  `useExperiment.test.jsx`: with fake timers and a test component, 20 frames within 50 ms produce at most two renders. The final render shows the last tick. Unmounting closes every socket.

  `session.test.js`, additions:
  - `arm.policy` follows the latest frame.
  - The receipt matching described in Interfaces.
  - The existing fixture still builds the same arms, with `receipts` empty.

- [ ] **Step 3: Run the tests.** Run `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/plan.test.js src/next/__tests__/experiment.test.js src/next/__tests__/useExperiment.test.jsx src/next/__tests__/session.test.js` and expect failures: the modules are missing.
- [ ] **Step 4: Implement.** Write `plan.js`, `endpoint.js`, `experiment.js`, `useExperiment.js` and the `session.js`/`catalog.js` additions until every test passes. Keep `experiment.js` free of React.
- [ ] **Step 5: Check.** Run the full suite, lint and build.
- [ ] **Step 6: Commit.** Message: `feat(next): live experiment controller, setup plan and receipts in the arm model`.

---

### Task E: Lever editor and the Set up screen

**Files:**
- Create:
  - `src/next/policyRules.js`
  - `src/next/components/LeverEditor.jsx`
  - `src/next/setup/SetupScreen.jsx`
  - `src/next/setup/useSetup.js`
  - `src/next/__tests__/policyRules.test.js`, `LeverEditor.test.jsx`, `SetupScreen.test.jsx`
- Modify: `src/next/catalog.js` (adds `LEVER_GROUPS`, `QUESTIONS`, `COPY.setup`, `COPY.levers`, and a `help` sentence on each `LEVERS` entry), `src/next/next.css`, `src/next/__tests__/catalog.test.js`.

**Interfaces:**
- **Consumes:**
  - From `plan.js`: `TOWN_LABELS`, `YEARS`, `HOUSEHOLD_STEP`, `householdCap`, `estimateSeconds`, `estimatePhrase` and `rollSeed`.
  - From `catalog.js`: `DEFAULT_POLICY`, `LEVER_OPTIONS`, `LEVERS`, `describePolicy` and `TOWN_COLORS`.
- **Produces:**

```js
// catalog.js
LEVER_GROUPS = [
  { id: 'taxes', levers: ['wage_tax_rate', 'profit_tax_rate', 'investment_tax_rate'] },
  { id: 'people', levers: ['minimum_wage_policy', 'benefit_level', 'social_spending'] },
  { id: 'spending', levers: ['public_works', 'infrastructure_spending', 'technology_spending'] },
  { id: 'business', levers: ['sector_subsidy_target', 'sector_subsidy_level', 'bailout_policy', 'bailout_target', 'bailout_budget'] },
  { id: 'prices', levers: ['price_stabilization_target', 'price_stabilization_level', 'rent_stabilization_level'] },
]   // with COPY.levers.groups[id] = { title, blurb }; every one of the 17 levers appears exactly once
QUESTIONS = [
  { id: 'minimum-wage', title: 'What happens if we raise the minimum wage?',
    blurb: 'Higher pay for the lowest earners, higher costs for firms. Which wins?', towns: [{}, { minimum_wage_policy: 'high' }] },
  { id: 'benefits', title: 'Do generous benefits keep people out of work?',
    blurb: 'More money for people without a job. Does it help them or make work less tempting?', towns: [{}, { benefit_level: 'high' }] },
]   // the two launch cards the smoke evidence supports; the other mockup cards stay out (spec 5.1)
// LEVERS[lever].help: one sentence on what the town hall directly does with this lever, checked against the
// backend code that reads it (grep the lever name in backend/agents.py and backend/economy.py). Describe the mechanism,
// never the outcome: e.g. "Sets how much every paycheque is taxed." not "Reduces inequality."

// policyRules.js (a port of backend/policy_vectors.py:58, same checks in the same order)
policyProblems(vector) -> { [group]: text }     // group 'sector_subsidy' | 'bailout'; text is newcomer copy from COPY.levers.rules

// LeverEditor.jsx
<LeverEditor value={vector} base={vector} onChange={next => ...} idPrefix="town-b" />
// Renders LEVER_GROUPS as fieldsets with legends. Each lever shows a label (LEVERS name, capitalised), its help
// sentence, and a control:
//   - rates: a range input, step 0.01, min/max from LEVER_OPTIONS, with the value shown as a percentage;
//   - ordered and plain enums with 5 or fewer options: a segmented group of aria-pressed buttons
//     (labels from LEVERS[lever].values, else the raw value);
//   - more options: a select.
// A lever whose value differs from `base` gets a "changed" dot and a visually hidden "(changed)".
// policyProblems messages render in role="alert" under the group they belong to.
// onChange always receives a full 17-lever vector, with numeric levers kept as numbers.

// setup/useSetup.js
useSetup({ random = Math.random } = {}) -> { state, actions, plan }
// state: { mode: 'compare'|'play', questionId: 'minimum-wage'|'benefits'|'custom', towns: [{ label, color, policy }],
//          households, years, seed, editing: index|null }
// Defaults: compare, 'minimum-wage', the card's two towns, households 1000, years 5, seed rollSeed(random).
// Actions:
//   setMode('play')      -> one town with DEFAULT_POLICY, questionId null, households min(current, 10000)
//   setMode('compare')   -> the minimum-wage card again
//   pickQuestion(id)     -> towns from that card (each: DEFAULT_POLICY merged with the card's levers);
//                           'custom' keeps the current towns
//   addTown()            -> at most 4; the new town copies Town A's policy
//   removeTown(i)        -> never below 2 in compare mode; labels and colours reassign in order
//   editTown(i) / closeEditor()
//   setTownPolicy(i, vector) -> in compare mode, questionId becomes 'custom'
//   setHouseholds(n)     -> clamped to [HOUSEHOLD_STEP, householdCap(towns.length)], rounded to HOUSEHOLD_STEP
//   setYears(y)
//   rerollSeed()
//   setSeed(n)           -> clamped to 0..2147483647
// Every action that changes the town count clamps households to the new cap.
// plan: the Plan object of Task D, built from state.

// setup/SetupScreen.jsx  (NextApp owns useSetup so the plan survives a trip to the Run screen and back)
<SetupScreen setup={setup} onStart={plan => ...} onWatchExample={() => ...} busy={bool} problem={{ kind, message }|null} />
```

**Screen content** (port the layout and CSS of `01-setup.html`; copy in `COPY.setup`):
- **Lead.**
  - An `<h1>` "What do you want to find out?".
  - The mockup's subhead.
  - A quiet link "Or watch a recorded example first", which calls `onWatchExample`.
- **Step 1, "Pick a kind of experiment".** Three mode cards with the mockup's copy.
  - "Test an AI mayor" is a disabled button carrying a "Coming soon" tag.
- **Step 2, "Choose a question".** Compare mode only.
  - The two `QUESTIONS` cards. Each shows the two towns' rules as coloured chips (`describePolicy` of the card's levers, capitalised, or "No changes") and its blurb.
  - A dashed "Build my own" card: "Pick every rule for every town".
  - The selected card has `aria-pressed="true"`.
- **Step 3.** Titled "Your towns", or "Your town" in play mode.
  - One tile per town: colour dot, label, and a policy sentence ("No changes. The control." for an empty diff, else `describePolicy`, capitalised).
  - Each tile has a "Change rules" button that opens a `LeverEditor` for that town in a panel below the tiles, with Done.
  - Compare mode adds "Add a town" (hidden at 4 towns) and "Remove" on towns C and D.
- **Step 4, "The world".**
  - **Households per town.** A range input from `HOUSEHOLD_STEP` to the cap, labelled with the value and "up to 5,000 with 2 towns".
  - **How long.** 1/2/5/10-year segmented buttons.
  - **Which town.** "Town #4242", plus a "Try a different town" button that rerolls. A number input for the seed appears only when `questionId === 'custom'` (Build my own), labelled "Town number".
  - The mockup's "Money rules" toggle is left out. The world keeps the server's default payment rules until the baseline calibration decision (spec 5.2).
- **Footer.**
  - A "Start the experiment" button; "Start playing" in play mode.
  - The estimate sentence, for example "Two towns, 1,000 households each, five years. About a minute. You can pause, change the rules, or stop at any time."
  - When `busy`, the button is disabled and reads "Building the towns…".
  - When `problem` is set, a `role="alert"` block above the button shows `COPY.setup.problems[kind]`. Kind `unreachable` adds the command `python -m uvicorn backend.server:app --port 8002` in a `<code>` and a button "Watch the recorded example instead", which calls `onWatchExample`.
- **Start is disabled** when any town's `policyProblems` is non-empty.

- [ ] **Step 1: Write the failing tests.**
  - **`policyRules.test.js`:**
    - A level of 10 with target `none` gives the sector_subsidy problem.
    - `bailout_policy: 'sector'` with target `none` gives the target problem. With a target and budget 0, it gives the budget problem instead (the same order as the backend).
    - `DEFAULT_POLICY` gives `{}`.
  - **`catalog.test.js`:**
    - Every lever appears exactly once across `LEVER_GROUPS`.
    - Every `LEVERS` entry has a non-empty `help` string.
    - `QUESTIONS` has two cards whose levers pass `policyProblems`.
  - **`LeverEditor.test.jsx`:**
    - All 17 levers render inside 5 fieldsets.
    - Moving the wage tax slider to 0.2 calls `onChange` with `wage_tax_rate: 0.2` and the other 16 levers unchanged.
    - Pressing "high" on the minimum wage group calls `onChange` with `minimum_wage_policy: 'high'`.
    - `sector_subsidy_level` stays a number after a change.
    - A vector with `sector_subsidy_level: 10` shows a `role="alert"` message.
    - A lever that differs from `base` has the hidden "(changed)" text.
  - **`SetupScreen.test.jsx`:**
    1. **Defaults:** the minimum wage card is pressed, two tiles, "No changes. The control.", "A higher minimum wage" (or the catalog's phrase, capitalised), households 1000, 5 years pressed, "About a minute." and no seed input.
    2. **Just play:** one tile, no question step, a households maximum of 10,000, and a "Start playing" button.
    3. **Adding a town clamps households:** at households 5,000 with two towns, "Add a town" gives three tiles, a households value of 3,300 and a maximum of 3,300.
    4. **Build my own** shows the "Town number" input. "Try a different town" changes the town number, using an injected `random` sequence.
    5. **Changing rules makes the question custom:** changing Town B's rules in the editor makes "Build my own" pressed.
    6. **Start sends the plan:** Start calls `onStart` with a plan that deep-equals the expected object.
    7. **Unreachable problem:** it shows the command and the "Watch the recorded example instead" button.
    8. **The AI mayor card** is disabled.
- [ ] **Step 2: Run the new test files.** Expect failures.
- [ ] **Step 3: Implement** the components, catalog additions and CSS. Read `01-setup.html` for markup and spacing. Use the Run screen's tokens and type scale so both screens feel like one app.
- [ ] **Step 4: Check.** Run the full suite, lint and build. Extend the contrast test for any new text colour.
- [ ] **Step 5: Commit.** Message: `feat(next): set up screen with question cards, towns, world and a lever editor`.

---

### Task F: Live Run screen, Town hall drawer and app routing

**Files:**
- Create:
  - `src/next/live/useLiveClock.js`
  - `src/next/components/TownHall.jsx`, `src/next/components/EndPanel.jsx`, `src/next/components/LostPanel.jsx`
  - `src/next/pickScreen.js`
  - tests: `useLiveClock.test.js`, `TownHall.test.jsx`, `EndPanel.test.jsx`, `pickScreen.test.js`, `LiveRun.test.jsx`
- Modify:
  - `src/next/NextApp.jsx`, `src/next/RunScreen.jsx`
  - `src/next/components/HorizonBar.jsx`, `src/next/components/HouseholdCards.jsx`
  - `src/next/catalog.js` (adds `COPY.live`, `COPY.hall`, `COPY.end`)
  - `src/next/next.css`
  - `src/next/__tests__/NextApp.test.jsx`: it now reaches the demo through `?view=next&demo`; its assertions stay the same.

**Interfaces:**
- **Consumes:**
  - From Task D: `useExperiment`, `State` and `Receipt`.
  - From Task E: `SetupScreen`, `useSetup`, `LeverEditor` and `policyProblems`.
- **Produces:**

```js
// pickScreen.js
pickScreen(search) -> 'demo' | 'setup'          // 'demo' when the query has a `demo` key, else 'setup'

// live/useLiveClock.js
useLiveClock(liveTick) -> { tick, following, scrub(value), follow() }
// following: tick === liveTick. scrub(v) sets tick v and following = v >= liveTick. follow() resumes following.

// NextApp.jsx
<NextApp search={window.location.search} WebSocketImpl={globalThis.WebSocket} />
// screen state: 'setup' | 'live' | 'demo', initial pickScreen(search)
// setup: SetupScreen. onStart(plan) calls experiment.start(plan) and switches to 'live'. If the state
//        turns 'failed' while connecting, it returns to 'setup' with problem = state.error (the plan is kept).
// live:  RunScreen with the controller's arms and the live clock, plus the `live` prop.
// demo:  today's recorded demo, unchanged. The demo files load only when this screen opens.
// Appbar:
//   - brand, the question h1 (live and demo only), a "Set up" button (live: "New experiment", which calls
//     leave() and returns to setup with the same plan), "Watch the example" (hidden on demo), and the classic link.

// RunScreen.jsx: a new optional prop
live = {
  phase, towns, error, following, onFollow,
  hallOpen, onHall(open),                       // the drawer, open by default when plan.mode === 'play'
  onConfigure(index, levers), onTrack(index, action, householdId),
  onExtend(weeks), onRestart(), onNewExperiment(),
}
// Without `live`, RunScreen renders exactly as today.

// HorizonBar.jsx: new optional props `live` and `following`, plus onFollow.
//   - When speed/onSpeed are undefined, the speed group is not rendered.
//   - In live mode the toggle reads "Pause"/"Resume", never "Play again".
//   - A "Back to live" button (onFollow) shows while !following.
//   - A "Town hall" toggle button (aria-pressed) sits at the right when live.hallOpen is defined.

// TownHall.jsx
<TownHall arms={arms} onConfigure={(index, levers) => ...} onClose={() => ...} tick={tick} />
// An <aside aria-label="Town hall">, fixed to the right (380px wide; full width under 720px) with a close button.
//   - Tabs: one aria-pressed button per town, in its colour.
//   - Current rules: arm.policy ?? DEFAULT_POLICY. Draft: per-town overrides.
//   - LeverEditor gets value = { ...current, ...draft } and base = current.
//   - "Change from next week" is enabled when the draft differs and policyProblems is empty. It calls
//     onConfigure(index, changedLevers only) and clears that town's draft.
//   - Receipts: the arm's receipts, newest first, at most 5:
//       sending/queued: "Waiting for next week…"
//       applied: "{weekLabel(effectiveTick)}: {describePolicy(applied), capitalised}."
//       each rejected lever: "{LEVERS name, capitalised} was not changed: {reason}"
//       failed: "Couldn't change the rules: {message}"
//   - A one-line note under the tabs: "Changes start at the next week. The other towns keep their own rules."

// EndPanel.jsx: shown in live mode when phase is 'horizon' or 'finished'
//   - "{years} years are up." (from the horizon)
//   - the verdict for the latest tick
//   - "Add a year" -> onExtend(52); disabled while phase is 'horizon' and not yet 'finished'
//   - "Try another question" -> onNewExperiment
// LostPanel.jsx: shown when phase is 'lost'
//   - "{town} lost its connection to the simulation in {weekLabel}. The other towns are paused."
//   - "Start these towns again" -> onRestart: a fresh start with the same plan, seed included
//   - "Set up something new" -> onNewExperiment
//   Replaying the lever changes into a restarted run is deferred (note it in the report).

// HouseholdCards.jsx: new optional prop onTrack(action, householdId).
//   - With it, a "Meet other families" button sends reshuffle.
//   - Follow also sends pin or unpin.
//   - Without it, exactly today's behaviour.
```

- [ ] **Step 1: Write the failing tests.**
  - **`pickScreen`:** check both results.
  - **`useLiveClock`:**
    - It follows `liveTick` as it rises.
    - A scrub to 5 at `liveTick` 20 holds at 5 while live rises.
    - A scrub to 20 follows again.
    - `follow()` jumps to live.
  - **`TownHall`:**
    - It opens on Town A with current rules from `arm.policy`.
    - Changing the minimum wage and pressing "Change from next week" calls `onConfigure(0, { minimum_wage_policy: 'high' })`.
    - A queued receipt reads "Waiting for next week…".
    - An applied receipt at tick 60 reads "Year 2, week 8: …".
    - A rejected lever shows its reason.
    - The button is disabled when nothing changed or `policyProblems` is non-empty.
  - **`EndPanel`:** "Add a year" is disabled in `horizon` and enabled in `finished`, where it calls `onExtend(52)`.
  - **`LiveRun.test.jsx`** (render `NextApp` with the fake socket factory from Task D):
    1. **Start opens one socket per town** (not before). Feeding `SESSION`, `SETUP_COMPLETE` and 12 fixture frames to both sockets shows two town columns and the lead sentence. The HorizonBar has no speed group.
    2. **StrictMode.** Wrapped in `<StrictMode>`, Start opens exactly 2 sockets.
    3. **Unreachable.** A socket `fail()` before `SESSION` returns to Set up, shows the unreachable problem and leaves no socket open.
    4. **Town hall.** Open the drawer, change Town B's minimum wage, apply. Socket 1 received CONFIG, and after `CONFIG_APPLIED` the receipt shows.
    5. **Horizon.** `HORIZON_REACHED` on both sends FINISH on both. `FINISHED` on both shows the EndPanel, and "Add a year" sends EXTEND 52 on both.
    6. **New experiment** closes both sockets and shows Set up with the same towns.
    7. **Lost.** Closing socket 1 after running shows the LostPanel, naming Town B.
    8. **Just play** opens the Town hall by default and shows one column.
- [ ] **Step 2: Run the new test files.** Expect failures.
- [ ] **Step 3: Implement.**
  - The live clock's `tick` drives every panel. `maxTick` for the HorizonBar is `liveTick`, and the horizon is the largest `arm.horizon`.
  - Before the first frame, show a `role="status"` "Building the towns…" instead of the columns.
  - Show a town's `notice` under its column head in small ink3 text.
- [ ] **Step 4: Check.** Run the full suite, lint and build. Then run the dev server once and confirm `?view=next` shows Set up, `?view=next&demo` plays the demo, and `/` still renders the classic dashboard, with no console errors.
- [ ] **Step 5: Commit.** Message: `feat(next): live towns on the Run screen with a Town hall drawer, end and lost panels, and app routing`.

---

### Task G: Moments (make the numbers feel alive)

The newcomer should notice when something happens without reading a chart. This covers the "fun" views Ayman asked to bring back: which business is richest, and what the town hall just did.

**Files:**
- Create: `src/next/components/Moments.jsx` and tests `Moments.test.jsx`, `moments.test.js`.
- Modify: `src/next/narration.js` (adds `moments`), `src/next/components/Town.jsx` (town hall pulse), `src/next/RunScreen.jsx` (renders `Moments` under the lead), `src/next/catalog.js` (adds `COPY.moments`), `src/next/next.css`.

**Interfaces:**

```js
// narration.js
moments(arms, tick) -> Moment[]     // newest first, at most 3
// Moment = { id, kind: 'rule'|'richest'|'milestone', label, color, tick, text }
// kinds (each only after WARMUP_TICKS, never from warm-up weeks):
//   rule:      a policyChanges entry with tick in (tick - 6, tick].
//              "Town B's town hall brought in a higher minimum wage." (describePolicy of { [policy]: value })
//   richest:   the richest open firm (by cash) at `tick` differs from the richest at tick - 4 (both snapshots exist).
//              "{firmDisplayName} is now Town A's richest business."
//   milestone: people out of work per 100 (curated peopleOutOfWorkPer100) crossed 10, 20 or 30, up or down,
//              between tick - 4 and tick.
//              "Town A passed 20 in 100 people out of work." / "Town A fell below 20 in 100 people out of work."
// id is stable: `${kind}:${label}:${tickOfTheChange}`, so React keys and the fade-in stay put across weeks.

// Moments.jsx
<Moments arms={arms} tick={tick} />
//   - A role="status" list of up to 3 chips, each with the town's colour dot and text.
//   - A chip fades in once (300 ms, none under reduced motion).
//   - Nothing renders when the list is empty.

// Town.jsx
//   - The town hall building gets class `is-changed` and a ring (an SVG circle, stroke in the town colour,
//     pulsing 2 times, 500 ms each; a static ring under reduced motion) when that arm has a policy change
//     in (tick - 4, tick].
//   - Its <title> reads "Town hall: new rules this month".
```

- [ ] **Step 1: Write the failing tests.**
  - **`moments.test.js`**, with hand-built arms using `createArm` and `ingest` of small frames:
    - A policy change at tick 20 gives a rule moment at ticks 20–25 and none at 26.
    - A policy change at tick 5 (warm-up) gives none.
    - When the richest firm changes between ticks 30 and 34, there is a richest moment at 34.
    - 19 → 21 in 100 gives "passed 20", and 21 → 19 gives "fell below 20".
    - There are at most 3, newest first.
    - Ids are stable across ticks.
  - **`Moments.test.jsx`:**
    - It renders the chips with town colours.
    - It renders nothing for an empty list.
  - **`Town.test.jsx`** addition: the hall has `is-changed` two weeks after a change, and not six weeks after.
- [ ] **Step 2: Run the new test files.** Expect failures.
- [ ] **Step 3: Implement.** Moments work the same in replay and live.
- [ ] **Step 4: Check.** Run the full suite, lint and build.
- [ ] **Step 5: Commit.** Message: `feat(next): moments strip and a town hall pulse when the rules change`.

---

## After the tasks (controller)

1. **Review.** One Opus review of the whole slice, then a fix round if the review finds anything Important.
2. **Live check.** Run the real backend (`.claude/launch.json` config `backend`) and `frontend-dev`, and run one small experiment in the browser: 2 towns × 200 households × 1 year.
   - Check that frames arrive, a Town hall change gets a receipt, and the end panel appears.
   - Check that "Add a year" works and that there are no console errors.
   - Screenshot the Set up and live Run screens.
3. **Records.** Add a CHANGELOG entry, including the deferrals: replaying lever changes on restart, the money-rules toggle, and the AI mayor card. Update the memory note, push the branch (approved as a backup) and report.
