# Frontend Redesign Phase 2, Slice 3: Show Me All the Numbers

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development. Execute task by task; each task ends in one commit. Steps use checkbox (`- [ ]`) syntax.

**Goal:** From the Run screen, in replay or live, a newcomer opens "Show me all the numbers". This is a full sheet that follows the same clock. It shows:
- the rules in force in every town;
- an at-a-glance scoreboard;
- six groups of numbers, each drawn with a visual that suits it.

It closes back to the towns.

**Architecture:** The backend adds a few more curated per-tick numbers.
- The pure data layer gains derivation helpers and a numbers catalog.
- Presentational components port the mockup's visuals to React.
- The sheet is an overlay rendered by `RunScreen`, driven by the same `tick` it already receives.

**Tech Stack:** Python (backend curated projection), React 19, Vite 8, Vitest with Testing Library, plain CSS scoped under `.nx`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-24-frontend-learning-redesign-design.md`, sections 2, 2.1, 4, 4.4 and 7.

**Visual source of truth:** `docs/superpowers/specs/2026-09-25-mockups/06-all-the-numbers.html`, which replaces the old dark reference `05-…`. Its CSS, SVG drawing code and copy are working reference code to port. Its "Notes for review" box and "Example" rule-change box are mockup-only.

**Data contract:** `docs/WEBSOCKET_PROTOCOL.md` and `backend/frame_projection.py`.

## Global Constraints

- **Branch and checks.**
  - The branch is `feat/frontend-redesign-phase2`.
  - Frontend commands run from `frontend-react/`: tests `npx --yes node@22 node_modules/.bin/vitest run`, lint `npx --yes node@22 node_modules/.bin/eslint src/next`, build `npx --yes node@22 node_modules/.bin/vite build`.
  - Backend commands run from the repo root: `.venv/bin/python -m pytest -q` and `.venv/bin/python -m ruff check .`.
  - Every check passes before each commit. Existing tests change only where a task says so.
- **Off-limits.**
  - Do not modify the classic dashboard (`src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/`, `src/charts/`, `src/theme/`), `src/main.jsx`, or generated `openwiki/`.
  - Never commit the untracked root files `OrbitControls.js`, `simulation_architecture.html` or `three.min.js`.
  - Do not push.
- **Styles and copy.**
  - Styles live in `src/next/next.css`, scoped under `.nx`, using the existing tokens. New text colours must pass `src/next/__tests__/contrast.test.js`, which you extend for them.
  - Every viewer-facing string comes from `src/next/catalog.js` or `src/next/narration.js`.
- **Truthfulness.** Never claim more than the data shows.
  - **Counted-every-5-weeks numbers** (`gini`, `wealthP10/P50/P90`, `topTenthShare`, `bottomHalfShare`) are drawn only at the weeks they were counted, and their tiles say "Counted every 5 weeks; last count {weekLabel}".
  - **Missing numbers.** A number that is missing, for example in an older recording, gives the tile the sentence "Not measured in this run", never a zero.
  - **Differences** between towns are phrased neutrally ("11 fewer in 100 than Town A"), with no good or bad colouring.
  - **Warm-up weeks** (1 to 10) are shaded as "setting up" on every chart.
- **Motion.** Only where it shows change, 300 to 500 ms, and none under `prefers-reduced-motion: reduce`.
- **Accessibility.**
  - The sheet is a dialog-like region with a heading, focus moves into it on open, Escape closes it, and focus returns to the opener.
  - Every chart has a text alternative: a visually hidden table or sentence.
  - Toggles use `aria-pressed`.
- **Commits.** Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Counted-every-5-weeks numbers during a scrub.** Scrubbing to week 72 must show the week-70 count labelled as such, not an interpolated or fake weekly value. (Task I test, Task J test)
2. **A recording without the new keys**, such as the old fixture. Tiles for the new numbers say "Not measured in this run", and nothing crashes. (Task I test, Task K test)
3. **Four towns at phone width.** The rules table and the at-a-glance scoreboard stay readable at 390px wide with four towns: columns scroll inside their card, and the page never scrolls sideways. (Task J test on the rendered structure; controller visual check)
4. **Warm-up weeks.** At week 5, differences say the towns are still being set up instead of showing numbers built from warm-up values. (Task I test)
5. **A town lost mid-run in live mode.** The sheet keeps that town's last numbers and marks its column "lost its connection in {week}". (Task L test)

---

### Task H: Backend, six more curated numbers and a fresh demo

**Files:**
- Modify: `backend/frame_projection.py` (`build_curated_metrics`) and `backend/server.py`, only if an input is not reachable from `economy` or `econ_metrics`.
- Modify: `docs/WEBSOCKET_PROTOCOL.md`, the curated table.
- Regenerate:
  - `frontend-react/public/demo/town-a.jsonl` and `town-b.jsonl`;
  - `frontend-react/src/test/fixtures/session-compare-small.jsonl`, only if a test needs the new keys.
- Test: `backend/tests_server/test_curated_metrics.py`. Extend it if it exists, otherwise create it next to the existing curated tests (`grep -rln build_curated_metrics backend/tests_*`).

**New curated keys** (camelCase, per tick):

| Key | Meaning | Source (verify in code, cite file:line in your report) | Freshness |
|---|---|---|---|
| `happiness` | average household happiness, 0 to 100 | computed in `build_curated_metrics` from `economy.households` every tick (mean of `h.happiness` × 100) | every tick |
| `salesThisWeek` | everything the town's businesses sold this week, in dollars | the value the frame's `metrics.gdp` is built from (`server.py` ~3024 divides by 1e6; curated carries dollars). If "gdp" is not firm sales, name the key after what it really is and tell the controller | every tick |
| `townHallIncome` | what the town hall took in this week, in dollars | `economy.government.last_tick_revenue` (taxes plus loan repayments; confirm) | every tick |
| `familySupportPaid` | support the town hall paid to households this week, in dollars | `economy.last_tick_gov_transfers` (confirm it is household transfers only) | every tick |
| `topTenthShare` | share of all household wealth held by the richest tenth, percent | `econ_metrics["top_10_percent_share"] × 100` | counted every 5 weeks; `wealthAsOfTick` says when |
| `bottomHalfShare` | share held by the poorer half, percent | `econ_metrics["bottom_50_percent_share"] × 100` | counted every 5 weeks; `wealthAsOfTick` |

- [ ] **Step 1: Write failing tests.** Use a small economy the way the existing curated tests build one.
  - Each new key is present and numeric.
  - `happiness` equals the mean of the households' happiness × 100.
  - `townHallIncome` and `familySupportPaid` equal their sources.
  - `topTenthShare` and `bottomHalfShare` are `null` when `econ_metrics` lacks them, never 0.
- [ ] **Step 2: Run.** Expect failures, then implement until the tests pass. Keep `build_curated_metrics` pure and O(households); no sorting per tick.
- [ ] **Step 3: Update the protocol doc.** In `docs/WEBSOCKET_PROTOCOL.md`, add each key to the curated table with its meaning, unit and freshness.
- [ ] **Step 4: Re-record the demo.** Use the same settings as today, reading the old header with `head -1` to confirm them: 500 households, 104 weeks, seed 1337, lean profile. Town B uses `{"minimum_wage_policy":"high"}`. Use `frontend-react/scripts/record_session.py` with `ECOSIM_ENABLE_WAREHOUSE=0`. This is a light run, two towns one after the other. Check the new files carry the new keys, and that the file sizes stay under 2.5 MB each.
- [ ] **Step 5: Check and commit.** Run the full backend suite once, then ruff, then the full frontend suite (the demo files feed the NextApp tests). Commit `feat(frames): happiness, sales, town hall income and support, wealth shares in the curated frame; demo re-recorded`.

### Task I: Numbers catalog and derivation helpers

**Files:**
- Modify: `src/next/catalog.js`, adding `METRICS` entries and `NUMBER_GROUPS`, plus `COPY.numbers`.
- Modify: `src/next/data/derive.js` and `src/next/narration.js`.
- Tests: `__tests__/numbers.test.js` (new), plus additions to `catalog.test.js` and `derive.test.js`.

**Interfaces (produced):**

```js
// catalog.js
// New METRICS entries, each { name, meaning, format, better }:
//   priceHousing, priceServices, priceHealthcare ('price'), bankDefaultAmountThisTick ('money'),
//   happiness ('outOf100', "How people feel"), salesThisWeek ('money', "Everything sold this week"),
//   townHallIncome ('money'), familySupportPaid ('money'), topTenthShare ('percent'), bottomHalfShare ('percent').
// Formats: formatMetric gains 'outOf100' -> "41 of 100" and 'percent' -> "42%".
//   A negative townHallCash reads "owes $11,276".
COUNTED_EVERY_5 = ['gini', 'wealthP10', 'wealthP50', 'wealthP90', 'topTenthShare', 'bottomHalfShare']
NUMBER_GROUPS = [
  { id: 'work', keys: ['peopleOutOfWorkPer100', 'typicalWeeklyPay', 'publicWorksJobs'], extras: ['hiresAndLayoffs'] },
  { id: 'prices', keys: ['priceFood', 'priceHousing', 'priceServices', 'priceHealthcare', 'foodSpendPerHousehold'] },
  { id: 'richpoor', keys: ['gini', 'topTenthShare', 'bottomHalfShare'], extras: ['wealthLadder'] },
  { id: 'business', keys: ['firmsOpen'], extras: ['firmStates', 'openedClosed'] },
  { id: 'money', keys: ['townHallCash', 'salesThisWeek', 'bankActiveLoans'], extras: ['moneyInOut', 'loansWrittenOff'] },
  { id: 'wellbeing', keys: ['homelessHouseholds', 'careDenials', 'happiness'] },
]   // COPY.numbers.groups[id] = { title, blurb }, taken from the mockup
GLANCE_KEYS = ['peopleOutOfWorkPer100', 'typicalWeeklyPay', 'foodSpendPerHousehold', 'gini', 'townHallCash', 'firmsOpen',
               'happiness', 'salesThisWeek']

// derive.js
countedAt(arm, key, tick) -> { value, asOfTick } | null   // for COUNTED_EVERY_5 keys: the value at the last tick <= `tick`
                                                          // where it changed or wealthAsOfTick moved, with that tick
rangeSoFar(arms, key, tick) -> { min, max } | null        // over every arm's values up to tick, after warm-up
cumulativeUpTo(arm, key, tick) -> number                  // sum of the series up to tick (loans written off so far)
weeklyCounts(arm, keys, tick, weeks = 26) -> [{ tick, [key]: n }]   // from arm.eventCounts
firmStatesAt(arm, tick) -> { growing, steady, struggling } | null   // from the curated counts
rulesTable(arms, tick) -> [{ group, same: boolean, rows: [{ lever, values: [value per arm], differs, changedAt: tick|null, was }] }]
// Uses rulesAt (derive.js) and LEVER_GROUPS. changedAt and was come from policyChanges <= tick.

// narration.js
differencePhrase(key, value, base) -> string   // neutral: "11 fewer in 100 than Town A", "$12 more than Town A",
                                               // "about the same as Town A" (compare the displayed values);
                                               // "still being set up" during warm-up
countedNote(asOfTick) -> "Counted every 5 weeks; last count Year 2, week 18."
```

- [ ] **Step 1: Write failing tests.**
  - `countedAt` at week 72 returns the week-70 value with `asOfTick` 70. Use the re-recorded demo, or a hand-built arm whose values change at weeks 65 and 70.
  - `rangeSoFar` ignores warm-up weeks.
  - `cumulativeUpTo` sums the series.
  - `weeklyCounts` returns 26 rows ending at the tick.
  - `rulesTable`:
    - collapses a group where the towns agree;
    - flags the minimum-wage row as differing for the demo;
    - reports `changedAt`/`was` after a mid-run change.
  - `differencePhrase`:
    - covers each format;
    - says "about the same" when the displayed values tie;
    - returns the warm-up sentence at week 5.
  - The old fixture, which lacks the new keys, yields `null` for them. It must not throw.
  - Every `NUMBER_GROUPS` and `GLANCE_KEYS` key has a `METRICS` entry.
- [ ] **Step 2: Run, implement, pass.** Then run the full frontend suite, lint and build.
- [ ] **Step 3: Commit.** `feat(next): numbers catalog, counted-every-5-weeks handling and derivation helpers`.

### Task J: The sheet, rules in force, at a glance, and tiles

**Files:**
- Create: `src/next/numbers/NumbersSheet.jsx`, `numbers/RulesInForce.jsx`, `numbers/AtAGlance.jsx`, `numbers/Tile.jsx` and `numbers/SeeItBig.jsx`.
- Tests: `__tests__/NumbersSheet.test.jsx`, `RulesInForce.test.jsx`, `AtAGlance.test.jsx` and `Tile.test.jsx`.
- Modify: `next.css`.

**Interfaces:**

```js
<NumbersSheet arms={arms} tick={tick} onClose={() => ...} live={liveOrUndefined} />
// Parts:
//   - a header with the title, the lead sentence (weekLabel), town chips with describePolicy of rulesAt,
//     and "Back to the towns";
//   - jump chips that scroll to each section, and a chart key;
//   - a sticky back bar once the header scrolls away;
//   - the sections: RulesInForce, AtAGlance, then one card per NUMBER_GROUPS entry.
// Group cards render Tiles for `keys`. Their `extras` slots are filled by Task K; until then an extra renders nothing.
<RulesInForce arms tick />
// A table: towns as columns; groups collapse to "Same in {every town|both towns}: …";
// a "Show"/"Hide" toggle (aria-expanded); differing values in the town's text colour with "different from Town A";
// a mid-run change shows "changed in {weekLabel} (was {value})".
<AtAGlance arms tick />
// Rows from GLANCE_KEYS:
//   - name and meaning;
//   - the value per town;
//   - under each non-first town, differencePhrase against the first town;
//   - a "where this week sits" dot track (rangeSoFar) with one dot per town.
<Tile metricKey arms tick onSeeBig />
// Name, the value per town with colour dots, and a sparkline over the whole horizon:
//   - the warm-up band;
//   - a cursor at tick;
//   - future weeks shaded;
//   - COUNTED_EVERY_5 keys drawn only at counted weeks, with countedNote;
//   - "Not measured in this run" when every value is null.
// Clicking the tile, or pressing Enter on it, calls onSeeBig(metricKey).
<SeeItBig metricKey arms tick onClose />
// StoryChart for any METRICS key. Extend StoryChart with an optional `metricKeys` prop listing its chips,
// defaulting to STORY_METRICS so the Run screen is unchanged.
```

- [ ] **Step 1: Write failing tests.**
  - The sheet renders the six group headings and the two top sections.
  - Escape and "Back to the towns" call `onClose`; focus moves to the heading on open.
  - `RulesInForce` on the demo:
    - Taxes is collapsed with "Same in both towns";
    - the minimum wage row shows "high" for Town B with "different from Town A";
    - "Show" expands a collapsed group.
  - `AtAGlance`:
    - eight rows;
    - Town B's people-out-of-work cell contains a neutral difference sentence;
    - a dot track with two dots.
  - `Tile`:
    - the cursor x matches the tick;
    - the gini tile at week 72 carries "last count Year 2, week 18";
    - a null-only key says "Not measured in this run";
    - Enter calls `onSeeBig`.
  - `SeeItBig` shows `happiness`'s name.
  - With four towns, the rules table and the glance table each sit inside an element with `overflow-x: auto`.
- [ ] **Step 2: Run, implement from the mockup, pass.** Then run the full suite, lint and build.
- [ ] **Step 3: Commit.** `feat(next): numbers sheet with rules in force, at a glance and metric tiles`.

### Task K: The special visuals

**Files:**
- Create in `src/next/numbers/`: `HiresAndLayoffs.jsx` (mirrored bars), `PriceTag.jsx`, `WealthLadder.jsx`, `ShareBars.jsx`, `FirmStates.jsx` (stacked bars), `OpenedClosed.jsx` (week strip), `MoneyInOut.jsx`, `CashChart.jsx` (owes band, the first week below zero ringed) and `FeelMeter.jsx`.
- Tests: `__tests__/numbersVisuals.test.jsx`.
- Modify: `NumbersSheet.jsx`, which fills the group `extras` slots and uses PriceTag for the price keys, CashChart for `townHallCash` and FeelMeter for `happiness`; also `next.css`.

**Behaviour (port from the mockup):**
- **HiresAndLayoffs.** The last 26 weeks per town. Bars above the line are hires and bars below are lay-offs. Include "this week N hired, M laid off", and "in these weeks X hired, Y laid off".
- **PriceTag.** The value per town and a sparkline. When a sector price is identical in every town and unchanged since the end of warm-up, it says "Same in {both|every} town(s), and unchanged since {weekLabel}" instead of drawing a flat line.
- **WealthLadder.** A range bar per town from wealthP10 to wealthP90, with a dot at wealthP50, a shared axis, and `countedNote`.
- **ShareBars.** "Out of every $100 saved": poorest half, the next 40%, richest tenth (100 − topTenthShare − bottomHalfShare). Show "Not measured in this run" when either share is null.
- **FirmStates.** A stacked bar per town: growing, steady, struggling, with counts.
- **OpenedClosed.** A week strip over the last 26 weeks with a mark for each opening and closing, plus the totals.
- **MoneyInOut.** For the last 26 weeks, bars of townHallIncome ("in: taxes and loans paid back") against familySupportPaid ("out: help paid to families"). Add a note that other town hall spending is not included.
- **CashChart.** The last 52 weeks of townHallCash, with a red "owes" band below zero and the first week below zero ringed. If the starting balance would flatten the scale, it becomes a note, not a point.
- **FeelMeter.** A 0-to-100 meter per town, with the meaning sentence.
- **Loans written off so far.** `cumulativeUpTo(arm, 'bankDefaultAmountThisTick', tick)` per town, with a sentence saying the count of loans is not recorded.
- **Empty states.** Show the mockup's sentences when homeless or care-denied is 0 in every town: "Nobody has lost their home in either town so far this week."

- [ ] **Step 1: Write failing tests.** One behavioural assertion per visual, on the demo data at week 72 or on hand-built arms:
  - bar counts and signs;
  - a flat price produces the "unchanged" sentence;
  - the ladder's dot sits between its ends;
  - the shares add to 100;
  - the stacked counts equal firmsOpen;
  - the "owes" band appears only when the cash is negative somewhere in the window;
  - the meter's width follows the value;
  - the empty-state sentence appears.

  Each visual also has its text alternative.
- [ ] **Step 2: Run, implement, pass.** Then run the full suite, lint and build.
- [ ] **Step 3: Commit.** `feat(next): the numbers sheet's special visuals`.

### Task L: Opening it from the Run screen, in replay and live

**Files:**
- Modify: `src/next/RunScreen.jsx`, which owns the `numbersOpen` state, renders `NumbersSheet` over the columns and keeps the HorizonBar above it.
- Modify: `src/next/components/HorizonBar.jsx` for a "Show me all the numbers" button, and `src/next/NextApp.jsx` for the deep link `?view=next&demo&numbers`, which opens the sheet on the demo.
- Modify: `catalog.js`, `next.css` and the tests `RunScreen.test.jsx` and `LiveRun.test.jsx`.

**Behaviour:**
- **Entry points.** Under the stat cards, a line naming more stats: "Also: prices in every shop, savings, businesses opening and closing, the town hall's money. Show me all the numbers." The spec section 4.2 wants a line naming more stats. There is also a HorizonBar button.
- **Clock.** The same clock drives it: scrubbing and play update the sheet.
- **Live.** A lost town's column is marked "lost its connection in {weekLabel}". The Town hall drawer and the sheet can't both be open: opening one closes the other.
- **Closing.** The sheet closes on Escape, on "Back to the towns", and when a new experiment starts.

- [ ] **Step 1: Write failing tests.**
  - `RunScreen`: the link opens the sheet and focus moves into it. Closing returns focus to the link. Scrubbing while it is open changes a tile's value.
  - `NextApp`: `?view=next&demo&numbers` opens on the sheet.
  - `LiveRun`: with a lost town, its column says "lost its connection".
  - Opening the Town hall closes the sheet.
- [ ] **Step 2: Run, implement, pass.** Then run the full suite, lint and build. Run the dev server once and check `?view=next&demo&numbers` in a browser, with no console errors.
- [ ] **Step 3: Commit.** `feat(next): open all the numbers from the Run screen, in replay and live`.

---

## After the tasks (controller)

1. Run one Opus review of the whole slice on top of the per-task reviews. Then do a visual check against the mockup at 1280px and 390px, and a live run on the real backend: 2 towns × 200 households × 1 year.
2. Record the work:
   - the CHANGELOG entry;
   - the memory note;
   - pushing the branch, which is the approved backup;
   - a report to Ayman.
