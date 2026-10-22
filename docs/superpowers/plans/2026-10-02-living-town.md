# Living Town Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Run screen's flat town drawing with a living isometric diorama per town (plus a Main Street close-up), driven by the data already on the wire, with a hard guarantee that nothing on the Run screen moves when the week changes.

**Architecture:** Pure modules under `frontend-react/src/next/town/` turn an arm (from `data/session.js`) and a tick into a town model; React components draw the model as SVG; one `requestAnimationFrame` hook per scene moves things between weeks by writing to refs and CSS variables. A Playwright test steps the recorded demo through every week at four widths and fails on any layout shift.

**Tech Stack:** React 19, Vite 8, Vitest 4 + jsdom + Testing Library, Playwright (new dev dependency), plain SVG and CSS.

**Spec:** `docs/superpowers/specs/2026-10-02-living-town-design.md`. Visual reference: `docs/superpowers/specs/2026-10-02-mockups/08-diorama-details.html` (open it in a browser; its `<script>` is the drawing reference this plan ports).

## Global Constraints

- Work in the worktree `/Users/aymanislam/EcoSim_v_2/EcoSim/.claude/worktrees/living-town`, branch `feat/living-town`. Never push, never merge, never touch the main checkout at `/Users/aymanislam/EcoSim_v_2/EcoSim`.
- Run Vitest and Vite with Node 22 from `frontend-react`: `npx --yes node@22 node_modules/.bin/vitest run <files>` and `npx --yes node@22 node_modules/.bin/vite build`. The system Node is 20 and jsdom crashes on it. `npm run lint` works on any Node.
- No backend or wire changes. Every figure used is already in the lean frame.
- Do not touch the classic dashboard (`src/App.jsx`, `src/screens/`, `src/charts/`, `src/ui/`).
- Viewer-facing words live in `src/next/catalog.js` `COPY`; plain language for a newcomer ("people out of work", not "unemployment rate").
- The page keeps `next.css` fonts and `--nx-*` tokens. Scene colours come from the mockup palette and live in `town/town.css` and `town/mood.js`.
- New scene CSS classes use the `lt-` prefix and are scoped under `.nx` like the rest of `next.css`.
- Drawings are `aria-hidden`; each town card carries a screen-reader summary list (`.nx-sr`).
- Respect `prefers-reduced-motion: reduce`: states and weather still change, nothing travels or loops.
- Commit after each task with a message like `feat(next): ...` or `test(next): ...` ending in the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `eslint-plugin-react-hooks` 7 enforces the React Compiler rules: no `setState` directly in an effect body, no reading or writing `ref.current` during render. Follow existing patterns (`useHeight` in `RunScreen.jsx` sets state only inside a `ResizeObserver` callback); write DOM styles imperatively inside effects; restructure rather than disabling a rule.
- Every task ends with the full Vitest suite and `npm run lint` passing. From Task 1 on, `npm run test:e2e` (the no-shift test) must pass at the end of every task.

## Review Focus

- One town (sandbox) and three or four towns: the grid must hold (one full-width card; 2 × 2), and motion counts must scale down with more towns. Owning task: Task 5 (grid test), Task 6 (rate test).
- Arms missing curated keys (the older `test/fixtures/session-compare-small.jsonl` lacks `happiness` and the bank figures): mood falls back, bank shows nothing, no crash. Owning task: Task 4 (model test with `fixtureArm()`).
- Scrubbing backwards or jumping weeks: no walkers, floating signs or puffs appear; only a single forward step while playing triggers them. Owning task: Task 6 (stepped-only test).
- Long live runs with more firms than lots: no lot is used by two firms at once, the extra firms are counted, the summary says so. Owning task: Task 3 (overflow and reuse tests).
- Resizing the window or pressing Enlarge, then playing on: reserved heights are re-measured and the no-shift test still holds after the resize. Owning task: Task 1 (StableText re-measure test) and Task 5 (Enlarge then step in e2e).

---

## File Structure

Create:
- `frontend-react/playwright.config.js` – Playwright config with its own Vite server on port 4179.
- `frontend-react/e2e/no-shift.spec.js` – the no-shift test.
- `frontend-react/src/next/components/StableText.jsx` – text box that reserves the height of its tallest candidate.
- `frontend-react/src/next/town/geometry.js` – isometric projection, fixed island layout, painter's order, Main Street layout, person houses.
- `frontend-react/src/next/town/mood.js` – mood, bands, seasons, scene colour ramps.
- `frontend-react/src/next/town/houses.js` – house rank from the seed, house states, weeks in state.
- `frontend-react/src/next/town/lots.js` – stable lot assignment.
- `frontend-react/src/next/town/model.js` – `townAt(arm, tick)`.
- `frontend-react/src/next/town/cards.js` – card contents per place.
- `frontend-react/src/next/town/weather.js` – applies a mood and season to a scene (CSS variables and a few attributes).
- `frontend-react/src/next/town/Diorama.jsx` – the isometric scene.
- `frontend-react/src/next/town/parts.jsx` – SVG parts shared by the scenes (house, tree, shop, hall, bank, signs, pins, figures, cars).
- `frontend-react/src/next/town/TownCard.jsx` – header, diorama, facts, summary, card overlay.
- `frontend-react/src/next/town/Legend.jsx` – one shared legend.
- `frontend-react/src/next/town/useSceneMotion.js` – the per-scene animation loop.
- `frontend-react/src/next/town/motion.js` – pure helpers for the loop (coin budget, picks, routes).
- `frontend-react/src/next/town/PlaceCard.jsx` – hover/click card.
- `frontend-react/src/next/town/MainStreet.jsx`, `frontend-react/src/next/town/MainStreetCard.jsx` – the close-up and its town picker.
- `frontend-react/src/next/town/town.css` – scene styles.
- Tests in `frontend-react/src/next/__tests__/`: `StableText.test.jsx`, `townGeometry.test.js`, `townMood.test.js`, `townLots.test.js`, `townHouses.test.js`, `townModel.test.js`, `townCards.test.js`, `TownCard.test.jsx`, `townMotion.test.js`, `PlaceCard.test.jsx`, `MainStreet.test.jsx`.

Modify:
- `frontend-react/package.json`, `package-lock.json` – `@playwright/test`, script `test:e2e`.
- `frontend-react/vite.config.js` – keep Vitest out of `e2e/`.
- `frontend-react/src/next/data/session.js` – keep `health` and `happiness` on tracked subjects.
- `frontend-react/src/next/data/derive.js` – `eventsAt(arm, tick)`.
- `frontend-react/src/next/catalog.js` – `COPY.diorama`.
- `frontend-react/src/next/RunScreen.jsx` – StableText for lead and verdict, the town grid, Main Street, legend; columns keep Businesses and Households.
- `frontend-react/src/next/next.css` – fixed-size rules for changing text and lists, grid rules.
- `CHANGELOG.md`, `frontend-react/README.md` – Task 9.

Delete (Task 5): `frontend-react/src/next/components/Town.jsx`, `frontend-react/src/next/__tests__/Town.test.jsx`, and the `.nx-town*`/`.nx-house`/`.nx-bldg*`/`.nx-civic` rules in `next.css` that nothing else uses.

---

### Task 1: The no-shift test, and today's Run screen passing it

**Files:**
- Create: `frontend-react/playwright.config.js`, `frontend-react/e2e/no-shift.spec.js`, `frontend-react/src/next/components/StableText.jsx`, `frontend-react/src/next/__tests__/StableText.test.jsx`
- Modify: `frontend-react/package.json`, `frontend-react/package-lock.json`, `frontend-react/vite.config.js`, `frontend-react/src/next/RunScreen.jsx`, `frontend-react/src/next/next.css`, and whichever Run screen components the test shows shifting (expected: `components/Town.jsx` facts, `components/Feed.jsx`, `components/HouseholdCards.jsx`, `components/BusinessList.jsx`)

**Interfaces:**
- Produces: `StableText({ as = 'p', className, texts: string[], stable: string, children })` – renders `<as className data-stable={stable}>` and sets its `style.minHeight` (imperatively, in an effect) to the tallest rendered height of any string in `texts` at the box's current width. The e2e test reads every element with `data-stable`.
- Produces: `npm run test:e2e`.

- [ ] **Step 1: Add Playwright and keep Vitest out of `e2e/`**

```bash
cd frontend-react
npm install --save-dev @playwright/test@^1
npx playwright install chromium
```

In `vite.config.js` add `import { configDefaults } from 'vitest/config'` and in `test` add `exclude: [...configDefaults.exclude, 'e2e/**']`. In `package.json` scripts add `"test:e2e": "playwright test"`. Add `playwright-report/` next to the existing `frontend-react/test-results/` line in the repository `.gitignore`.

`frontend-react/playwright.config.js`:

```js
import { defineConfig, devices } from '@playwright/test'

// The no-shift test runs against its own Vite dev server (Node 22, port 4179)
// and the recorded demo at /?view=next&demo; no backend is needed.
export default defineConfig({
  testDir: './e2e',
  timeout: 300_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:4179' },
  webServer: {
    command: 'npx --yes node@22 node_modules/.bin/vite --port 4179 --strictPort',
    url: 'http://localhost:4179',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
```

- [ ] **Step 2: Write the no-shift test**

`frontend-react/e2e/no-shift.spec.js`:

```js
import { expect, test } from '@playwright/test'

// Changing the week must not move or resize anything on the Run screen (spec
// section 6). For each width, open the recorded demo, step the timeline
// through every week, and compare every watched box with week 1.
const WIDTHS = [390, 489, 1024, 1440]
const TOLERANCE = 0.5

// Every element marked data-stable, every direct child of the Run screen's
// <main>, and every card, keyed so the same element is compared each week.
async function boxes(page) {
  return page.evaluate(() => {
    const out = {}
    const seen = new Set()
    const watched = [
      ...document.querySelectorAll('[data-stable]'),
      ...document.querySelectorAll('main.nx-wrap > *'),
      ...document.querySelectorAll('main.nx-wrap .nx-card'),
    ]
    watched.forEach((el, i) => {
      if (seen.has(el)) return
      seen.add(el)
      const key = el.dataset.stable ? `stable:${el.dataset.stable}` : `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]}#${i}`
      const r = el.getBoundingClientRect()
      out[key] = [r.left, r.top + window.scrollY, r.width, r.height]
    })
    out.__scrollHeight = [0, 0, 0, document.scrollingElement.scrollHeight]
    return out
  })
}

async function goToWeek(page, week) {
  await page.locator('input[type=range]').first().evaluate((input, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input, String(value))
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, week)
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}

function firstDifference(base, now) {
  for (const key of new Set([...Object.keys(base), ...Object.keys(now)])) {
    const a = base[key], b = now[key]
    if (!a || !b) return `${key} ${a ? 'disappeared' : 'appeared'}`
    for (let k = 0; k < 4; k += 1) {
      if (Math.abs(a[k] - b[k]) > TOLERANCE) return `${key} ${['left', 'top', 'width', 'height'][k]} ${a[k].toFixed(1)} → ${b[k].toFixed(1)}`
    }
  }
  return null
}

for (const width of WIDTHS) {
  test(`nothing moves when the week changes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/?view=next&demo')
    await page.locator('input[type=range]').first().waitFor()
    await page.evaluate(() => document.fonts.ready)
    const max = Number(await page.locator('input[type=range]').first().getAttribute('max'))
    await goToWeek(page, 1)
    const base = await boxes(page)
    const problems = []
    for (let week = 2; week <= max; week += 1) {
      await goToWeek(page, week)
      const diff = firstDifference(base, await boxes(page))
      if (diff) problems.push(`week ${week}: ${diff}`)
    }
    expect(problems, problems.slice(0, 12).join('\n')).toEqual([])
  })
}
```

- [ ] **Step 3: Run it and confirm it fails today**

Run: `cd frontend-react && npm run test:e2e`
Expected: FAIL. At 489 px the lead sentence changes height (the town columns' `top` moves by about 34 px); at 1440 px something lower down changes height. Read every listed key: it tells you which box moves first.

- [ ] **Step 4: Write the StableText test**

`frontend-react/src/next/__tests__/StableText.test.jsx`:

```jsx
import { afterEach, describe, expect, test, vi } from 'vitest'
import { render } from '@testing-library/react'
import StableText from '../components/StableText.jsx'

// jsdom has no layout: fake each element's height from its text length (one
// line per 20 characters, 30 px a line) and its width from a variable.
let width = 400
function fakeLayout() {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function rect() {
    const lines = Math.max(1, Math.ceil((this.textContent ?? '').length / (width / 20)))
    return { width, height: lines * 30, top: 0, left: 0, right: width, bottom: lines * 30, x: 0, y: 0, toJSON() {} }
  })
}
afterEach(() => vi.restoreAllMocks())

describe('StableText', () => {
  test('reserves the height of the longest candidate, not the current text', () => {
    width = 400
    fakeLayout()
    const texts = ['short', 'x'.repeat(70)] // 1 line and 4 lines at 20 chars a line
    const { container } = render(<StableText texts={texts} stable="lead">short</StableText>)
    const box = container.querySelector('[data-stable="lead"]')
    expect(box.style.minHeight).toBe('120px')
    expect(box).toHaveTextContent('short')
  })

  test('measures again when the candidates change', () => {
    width = 400
    fakeLayout()
    const { container, rerender } = render(<StableText texts={['a']} stable="v">a</StableText>)
    rerender(<StableText texts={['a', 'y'.repeat(50)]} stable="v">a</StableText>)
    expect(container.querySelector('[data-stable="v"]').style.minHeight).toBe('90px')
  })
})
```

Width changes reach StableText through a `ResizeObserver`; jsdom has none, so StableText also measures in a layout effect whenever `texts` changes.

- [ ] **Step 5: Run it to see it fail**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/StableText.test.jsx`
Expected: FAIL, `Failed to resolve import "../components/StableText.jsx"`.

- [ ] **Step 6: Write StableText**

`frontend-react/src/next/components/StableText.jsx`:

```jsx
import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'

// Text that changes with the week, in a box as tall as the tallest text it can
// show at its current width, so nothing below it moves when the text changes
// (spec section 6). `texts` are every string the box may show; each is
// measured once per width with a hidden copy of the box, and again after web
// fonts load. The height is written to the box's style, not React state, so a
// measurement never re-renders the page. Pass a memoised `texts` array.
export default function StableText({ as: Tag = 'p', className, texts, stable, children }) {
  const boxRef = useRef(null)
  const heights = useRef(new Map())

  const measure = useCallback(() => {
    const box = boxRef.current
    if (!box || !box.parentNode) return
    const width = Math.round(box.getBoundingClientRect().width)
    const probe = box.cloneNode(false)
    probe.removeAttribute('data-stable')
    Object.assign(probe.style, { position: 'absolute', visibility: 'hidden', left: '-10000px', top: '0', width: `${width}px`, minHeight: '0', height: 'auto' })
    box.parentNode.appendChild(probe)
    let tallest = 0
    for (const text of texts ?? []) {
      const key = `${width}|${text}`
      let height = heights.current.get(key)
      if (height == null) {
        probe.textContent = text
        height = probe.getBoundingClientRect().height
        heights.current.set(key, height)
      }
      if (height > tallest) tallest = height
    }
    probe.remove()
    box.style.minHeight = tallest ? `${Math.ceil(tallest)}px` : ''
  }, [texts])

  useLayoutEffect(() => { measure() }, [measure])

  useEffect(() => {
    const box = boxRef.current
    if (!box || typeof ResizeObserver === 'undefined') return undefined
    let lastWidth = -1
    const observer = new ResizeObserver(() => {
      const width = Math.round(box.getBoundingClientRect().width)
      if (width !== lastWidth) { lastWidth = width; measure() }
    })
    observer.observe(box)
    return () => observer.disconnect()
  }, [measure])

  useEffect(() => {
    let live = true
    document.fonts?.ready?.then(() => { if (live) { heights.current.clear(); measure() } })
    return () => { live = false }
  }, [measure])

  return <Tag ref={boxRef} className={className} data-stable={stable}>{children}</Tag>
}
```

- [ ] **Step 7: Run the StableText test**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/StableText.test.jsx`
Expected: PASS (2 tests).

- [ ] **Step 8: Use StableText for the lead and the verdict**

In `RunScreen.jsx` import `useMemo`, `commonTicks` from `./data/derive.js` and `StableText`. Inside `RunScreen`, with `const ticksKey = arms.map(arm => arm.ticks.length).join(',')`:

```jsx
// Every lead and verdict the towns can show, so their boxes keep one height.
const weeks = useMemo(() => commonTicks(arms), [arms, ticksKey]) // eslint-disable-line react-hooks/exhaustive-deps
const leadTexts = useMemo(() => [...new Set(weeks.map(week => leadSentence(arms, week)))], [arms, weeks])
const verdictTexts = useMemo(() => [...new Set(weeks.map(week => verdict(arms, week)))], [arms, weeks])
```

Replace `<p className="nx-lead"><Lead .../></p>` with `<StableText className="nx-lead" texts={leadTexts} stable="lead"><Lead text={leadSentence(arms, tick)} arms={arms} /></StableText>` and `<p className="nx-verdict">{verdict(arms, tick)}</p>` with `<StableText className="nx-verdict" texts={verdictTexts} stable="verdict">{verdict(arms, tick)}</StableText>`. If the lint rule for exhaustive deps objects, keep `ticksKey` as the dependency the comment explains.

- [ ] **Step 9: Fix every other shift the e2e test reports**

Run `npm run test:e2e`, take the first failing key at each width, fix it with one of these, and repeat until all four widths pass:
- A value that may wrap: `white-space: nowrap` on the value.
- A label that wraps differently week to week: give its row a fixed height of two lines (`min-height: 3em` at `line-height: 1.5`) and clamp to two lines (`display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden`).
- A list whose row count changes with the week: render a fixed number of rows (pad with empty, `aria-hidden` rows), each a fixed height with one or two clamped lines.
- A header whose parts change width: `flex-wrap: nowrap`, fixed `min-width` on chips and buttons, `min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap` on free text.

Add `data-stable="<name>"` to each box you fix (for example `town-facts`, `feed`, `households`, `businesses`) so the test names it. Keep each fix in the component's own CSS block in `next.css`. Do not hide information the viewer needs: clamped text keeps its full wording in a `title` attribute.

- [ ] **Step 10: Run everything**

Run: `npm run test:e2e` → PASS (4 tests).
Run: `npx --yes node@22 node_modules/.bin/vitest run` → all pass (update any assertion that depended on old markup, keeping the behaviour it protected).
Run: `npm run lint` → clean.

- [ ] **Step 11: Commit**

```bash
git add -A frontend-react .gitignore
git commit -m "test(next): no-shift Playwright check; the Run screen keeps its layout as weeks change

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Scene geometry and mood

**Files:**
- Create: `frontend-react/src/next/town/geometry.js`, `frontend-react/src/next/town/mood.js`
- Test: `frontend-react/src/next/__tests__/townGeometry.test.js`, `frontend-react/src/next/__tests__/townMood.test.js`

**Interfaces:**
- Produces (geometry.js): `TILE_W = 36`, `TILE_H = 18`, `GRID = 16`, `ROAD = 7`, `HOUSES = 100`, `LOT_CAPACITY = 50`, `STREET_CAPACITY = 26`, `VIEWBOX = '-302 -50 604 364'`, `iso(gx, gy, z = 0) → [x, y]`, `pts(list) → 'x,y x,y …'`, `mulberry32(seed) → () => number`, `HALL = { gx: 8.1, gy: 8.1, w: 1.55, d: 1.55, h: 24 }`, `BANK = { gx: 5.15, gy: 5.15, w: 1.7, d: 1.7, h: 17 }`, `LAYOUT = { tiles: [{ gx, gy, kind: 'road'|'civic'|'lot'|'grass' }], lots: [{ gx, gy }] (50), houses: [{ gx, gy }] (100), trees: [{ gx, gy, r }] }`, `PAINT_ORDER: [{ kind: 'house'|'tree'|'lot'|'hall'|'bank'|'slot', gx, gy, index? }]`, `personHouses(ids: number[]) → number[]` (distinct house indices), `STREET = { viewBox: '0 0 1200 340', base: 290, hallX: 600, bankX: 712, treasuryX: 524, lots: [{ x, w }] (26), houses: [{ x, y, s }] (100) }`.
- Produces (mood.js): `moodOf({ out, happiness, warmUp }) → number`, `MOOD_KEYS = ['thriving', 'okay', 'struggling', 'hard']`, `moodBand(value) → 'thriving'|'okay'|'struggling'|'hard'`, `seasonOf(tick) → 'spring'|'summer'|'autumn'|'winter'`, `scenePalette(mood, season) → { skyTop, skyBottom, sun, cloudFill, cloudCount, cloudOpacity, rain, snow, shade, grassA, grassB, glow, hillA, hillB, meadow }`.

- [ ] **Step 1: Write the failing tests**

`frontend-react/src/next/__tests__/townGeometry.test.js`:

```js
import { describe, expect, test } from 'vitest'
import { GRID, HOUSES, LAYOUT, LOT_CAPACITY, PAINT_ORDER, ROAD, STREET, STREET_CAPACITY, iso, personHouses } from '../town/geometry.js'

const key = ({ gx, gy }) => `${gx},${gy}`

describe('island layout', () => {
  test('projects tiles isometrically', () => {
    expect(iso(0, 0)).toEqual([0, 0])
    expect(iso(1, 0)).toEqual([18, 9])
    expect(iso(0, 1)).toEqual([-18, 9])
    expect(iso(0, 0, 10)).toEqual([0, -10])
  })

  test('has 50 lots beside the roads, nearest the crossing first', () => {
    expect(LAYOUT.lots).toHaveLength(LOT_CAPACITY)
    for (const lot of LAYOUT.lots) {
      const besideRoad = [ROAD - 1, ROAD + 1].includes(lot.gx) || [ROAD - 1, ROAD + 1].includes(lot.gy)
      expect(besideRoad).toBe(true)
    }
    const distance = lot => Math.abs(lot.gx - ROAD) + Math.abs(lot.gy - ROAD)
    for (let i = 1; i < LAYOUT.lots.length; i += 1) expect(distance(LAYOUT.lots[i])).toBeGreaterThanOrEqual(distance(LAYOUT.lots[i - 1]))
  })

  test('uses every tile once: roads, civic, lots, houses, trees and plain grass', () => {
    expect(LAYOUT.tiles).toHaveLength(GRID * GRID)
    expect(new Set(LAYOUT.tiles.map(key)).size).toBe(GRID * GRID)
    expect(LAYOUT.houses).toHaveLength(HOUSES)
    const taken = [...LAYOUT.lots, ...LAYOUT.houses, ...LAYOUT.trees].map(key)
    expect(new Set(taken).size).toBe(taken.length)
    const kinds = Object.fromEntries(LAYOUT.tiles.map(tile => [key(tile), tile.kind]))
    for (const house of LAYOUT.houses) expect(kinds[key(house)]).toBe('grass')
    for (const lot of LAYOUT.lots) expect(kinds[key(lot)]).toBe('lot')
  })

  test('draws back to front, with a slot after every tile', () => {
    const depth = item => (item.kind === 'hall' ? 18 : item.kind === 'bank' ? 12 : item.gx + item.gy + (item.kind === 'slot' ? 1.5 : 1))
    for (let i = 1; i < PAINT_ORDER.length; i += 1) expect(depth(PAINT_ORDER[i])).toBeGreaterThanOrEqual(depth(PAINT_ORDER[i - 1]))
    expect(PAINT_ORDER.filter(item => item.kind === 'slot')).toHaveLength(GRID * GRID)
    expect(PAINT_ORDER.filter(item => item.kind === 'house')).toHaveLength(HOUSES)
  })

  test('gives followed households distinct houses near the middle, the same ones every time', () => {
    const picked = personHouses([38, 366, 289, 226])
    expect(new Set(picked).size).toBe(4)
    for (const index of picked) expect(index).toBeLessThan(40)
    expect(personHouses([38, 366, 289, 226])).toEqual(picked)
    expect(personHouses([5, 5 + 40])).toHaveLength(2)
    expect(new Set(personHouses([5, 5 + 40])).size).toBe(2)
  })

  test('Main Street has 26 lots and 100 houses on the hill', () => {
    expect(STREET.lots).toHaveLength(STREET_CAPACITY)
    expect(STREET.houses).toHaveLength(HOUSES)
    const xs = STREET.lots.map(lot => lot.x)
    expect(new Set(xs).size).toBe(xs.length)
    for (const lot of STREET.lots) expect(lot.x + lot.w < STREET.hallX - 70 || lot.x > STREET.bankX + 40).toBe(true)
  })
})
```

`frontend-react/src/next/__tests__/townMood.test.js`:

```js
import { describe, expect, test } from 'vitest'
import { moodBand, moodOf, scenePalette, seasonOf } from '../town/mood.js'

describe('mood', () => {
  test('mixes work and happiness', () => {
    expect(moodOf({ out: 5, happiness: 65, warmUp: false })).toBeCloseTo(1)
    expect(moodOf({ out: 45, happiness: 10, warmUp: false })).toBeCloseTo(0)
    expect(moodOf({ out: 25, happiness: 37.5, warmUp: false })).toBeCloseTo(0.55 * 0.5 + 0.45 * 0.5)
  })

  test('is neutral during warm-up and falls back when a figure is missing', () => {
    expect(moodOf({ out: 42, happiness: 69, warmUp: true })).toBe(0.62)
    expect(moodOf({ out: null, happiness: null, warmUp: false })).toBeCloseTo(0.6)
    expect(moodOf({ out: 5, happiness: null, warmUp: false })).toBeCloseTo(0.55 + 0.45 * 0.6)
  })

  test('names the band at its edges', () => {
    expect(moodBand(0.72)).toBe('thriving')
    expect(moodBand(0.7199)).toBe('okay')
    expect(moodBand(0.5)).toBe('okay')
    expect(moodBand(0.4999)).toBe('struggling')
    expect(moodBand(0.3)).toBe('struggling')
    expect(moodBand(0.2999)).toBe('hard')
  })

  test('follows the seasons of a 52-week year', () => {
    expect(seasonOf(1)).toBe('winter')
    expect(seasonOf(9)).toBe('winter')
    expect(seasonOf(10)).toBe('spring')
    expect(seasonOf(22)).toBe('spring')
    expect(seasonOf(23)).toBe('summer')
    expect(seasonOf(36)).toBe('autumn')
    expect(seasonOf(48)).toBe('autumn')
    expect(seasonOf(49)).toBe('winter')
    expect(seasonOf(53)).toBe('winter')
    expect(seasonOf(62)).toBe('spring')
  })

  test('the palette: sun when thriving, rain in hard times, snow in winter, shade capped', () => {
    const good = scenePalette(0.85, 'summer')
    const bad = scenePalette(0.1, 'summer')
    expect(good.sun).toBeGreaterThan(0.9)
    expect(good.rain).toBe(0)
    expect(bad.sun).toBe(0)
    expect(bad.rain).toBeGreaterThan(0.7)
    expect(bad.snow).toBe(false)
    expect(bad.shade).toBeLessThanOrEqual(0.2)
    expect(bad.cloudCount).toBeGreaterThan(good.cloudCount)
    const winter = scenePalette(0.85, 'winter')
    expect(winter.snow).toBe(true)
    expect(winter.rain).toBeGreaterThanOrEqual(0.55)
    expect(good.grassA).toMatch(/^#[0-9a-f]{6}$/i)
  })
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townGeometry.test.js src/next/__tests__/townMood.test.js`
Expected: FAIL, modules not found.

- [ ] **Step 3: Write `town/geometry.js`**

```js
// The diorama's fixed island: 16 × 16 tiles seen from above at an angle, two
// roads crossing at row and column 7, the town hall and the bank beside the
// crossing, 50 shop lots along the roads (nearest the crossing first), the 100
// house tiles nearest the middle and trees on the rest. Nothing here depends
// on a run: the same tile is the same place in every town. Also the Main
// Street layout (a side view) and which house a followed household lives in.

export const TILE_W = 36
export const TILE_H = 18
export const GRID = 16
export const ROAD = 7
export const HOUSES = 100
export const LOT_CAPACITY = 50
export const STREET_CAPACITY = 26
export const VIEWBOX = '-302 -50 604 364'

const round1 = value => Math.round(value * 10) / 10

// Screen position of a point on the island; z lifts it straight up.
export function iso(gx, gy, z = 0) {
  return [round1(((gx - gy) * TILE_W) / 2), round1(((gx + gy) * TILE_H) / 2 - z)]
}

export const pts = list => list.map(([x, y]) => `${round1(x)},${round1(y)}`).join(' ')

export function mulberry32(seed) {
  let a = seed | 0
  return () => {
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const HALL = { gx: 8.1, gy: 8.1, w: 1.55, d: 1.55, h: 24 }
export const BANK = { gx: 5.15, gy: 5.15, w: 1.7, d: 1.7, h: 17 }
const CIVIC = new Set(['8,8', '9,8', '8,9', '9,9', '5,5', '6,5', '5,6', '6,6'])
const isRoad = (x, y) => x === ROAD || y === ROAD
const besideRoad = (x, y) => [ROAD - 1, ROAD + 1].includes(x) || [ROAD - 1, ROAD + 1].includes(y)

export const LAYOUT = (() => {
  const lots = []
  const free = []
  const kind = {}
  for (let x = 0; x < GRID; x += 1) {
    for (let y = 0; y < GRID; y += 1) {
      const key = `${x},${y}`
      if (isRoad(x, y)) kind[key] = 'road'
      else if (CIVIC.has(key)) kind[key] = 'civic'
      else if (besideRoad(x, y)) { kind[key] = 'lot'; lots.push({ gx: x, gy: y, d: Math.abs(x - ROAD) + Math.abs(y - ROAD), s: x - y }) }
      else { kind[key] = 'grass'; free.push({ gx: x, gy: y, d: Math.hypot(x - ROAD, y - ROAD) + (mulberry32(x * 31 + y)() - 0.5) * 1.6 }) }
    }
  }
  lots.sort((a, b) => a.d - b.d || a.s - b.s)
  free.sort((a, b) => a.d - b.d)
  const rand = mulberry32(11)
  const trees = free.slice(HOUSES).map(tile => ({ gx: tile.gx, gy: tile.gy, r: rand() })).filter(tree => tree.r < 0.8)
  const tiles = []
  for (let x = 0; x < GRID; x += 1) for (let y = 0; y < GRID; y += 1) tiles.push({ gx: x, gy: y, kind: kind[`${x},${y}`] })
  return {
    tiles,
    lots: lots.map(({ gx, gy }) => ({ gx, gy })),
    houses: free.slice(0, HOUSES).map(({ gx, gy }) => ({ gx, gy })),
    trees,
  }
})()

// Back to front: a tile's things are drawn before anything nearer the viewer.
// Each tile also gets an empty slot just after it, where moving cars and people
// on that tile are drawn so that buildings in front hide them.
export const PAINT_ORDER = (() => {
  const items = []
  LAYOUT.houses.forEach((tile, index) => items.push({ kind: 'house', index, gx: tile.gx, gy: tile.gy, depth: tile.gx + tile.gy + 1 }))
  LAYOUT.trees.forEach((tile, index) => items.push({ kind: 'tree', index, gx: tile.gx, gy: tile.gy, depth: tile.gx + tile.gy + 1 }))
  LAYOUT.lots.forEach((tile, index) => items.push({ kind: 'lot', index, gx: tile.gx, gy: tile.gy, depth: tile.gx + tile.gy + 1 }))
  items.push({ kind: 'hall', gx: 8, gy: 8, depth: 18 }, { kind: 'bank', gx: 5, gy: 5, depth: 12 })
  for (let x = 0; x < GRID; x += 1) for (let y = 0; y < GRID; y += 1) items.push({ kind: 'slot', gx: x, gy: y, depth: x + y + 1.5 })
  return items.sort((a, b) => a.depth - b.depth || a.gx - b.gx).map(({ depth, ...item }) => item)
})()

// Each followed household lives in one of the 40 houses nearest the middle,
// picked from its id; two households never share a house.
export function personHouses(ids) {
  const used = new Set()
  return ids.map(id => {
    let index = Math.abs(Math.trunc(Number(id) * 7919)) % 40
    while (used.has(index)) index = (index + 1) % 40
    used.add(index)
    return index
  })
}

// Main Street: shops on 26 lots either side of the town hall and bank (lot 0
// nearest the hall, alternating right and left), 100 houses in four terraced
// rows on the hill behind.
export const STREET = (() => {
  const pitch = 35
  const lots = []
  for (let k = 0; k < STREET_CAPACITY; k += 1) {
    const n = Math.floor(k / 2)
    lots.push({ x: k % 2 === 0 ? 755 + n * pitch : 20 + (13 - n) * pitch, w: 30 })
  }
  const rand = mulberry32(5)
  const houses = []
  for (let i = 0; i < HOUSES; i += 1) {
    const row = Math.floor(i / 25)
    const n = i % 25
    houses.push({
      x: round1(26 + n * 46.4 + (row % 2 ? 23 : 0) + (rand() - 0.5) * 5),
      y: round1(94 + row * 32 + Math.sin(n / 3.2 + row) * 3 + (rand() - 0.5) * 2),
      s: round1(0.86 + row * 0.07),
    })
  }
  return { viewBox: '0 0 1200 340', base: 290, hallX: 600, bankX: 712, treasuryX: 524, lots, houses }
})()
```

Note: `iso` rounds to one decimal so tests compare exact numbers.

- [ ] **Step 4: Write `town/mood.js`**

```js
// How a town is doing, as one number from 0 (hard times) to 1 (thriving), and
// the scene colours that follow from it (spec section 5).
import { mulberry32 } from './geometry.js'

export const MOOD_KEYS = ['thriving', 'okay', 'struggling', 'hard']
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const known = value => typeof value === 'number' && Number.isFinite(value)

export function moodOf({ out, happiness, warmUp }) {
  if (warmUp) return 0.62
  const jobs = known(out) ? clamp(1 - (out - 5) / 40, 0, 1) : 0.6
  const happy = known(happiness) ? clamp((happiness - 10) / 55, 0, 1) : 0.6
  return 0.55 * jobs + 0.45 * happy
}

export function moodBand(value) {
  if (value >= 0.72) return 'thriving'
  if (value >= 0.5) return 'okay'
  if (value >= 0.3) return 'struggling'
  return 'hard'
}

export function seasonOf(tick) {
  const week = ((Math.max(1, Math.round(tick)) - 1) % 52) + 1
  if (week <= 9 || week >= 49) return 'winter'
  if (week <= 22) return 'spring'
  if (week <= 35) return 'summer'
  return 'autumn'
}

function hex(colour) {
  const n = parseInt(colour.slice(1), 16)
  return [n >> 16, (n >> 8) & 255, n & 255]
}
export function mix(a, b, t) {
  const A = hex(a)
  const B = hex(b)
  return `#${A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join('')}`
}
// Blend across [value, colour] stops sorted by value.
function ramp(stops, v) {
  if (v <= stops[0][0]) return stops[0][1]
  for (let i = 1; i < stops.length; i += 1) {
    if (v <= stops[i][0]) return mix(stops[i - 1][1], stops[i][1], (v - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]))
  }
  return stops[stops.length - 1][1]
}

export function scenePalette(mood, season) {
  const v = clamp(mood, 0, 1)
  const dry = clamp((0.62 - v) / 0.45, 0, 1)
  const winter = season === 'winter'
  return {
    skyTop: ramp([[0.1, '#9fa9b6'], [0.38, '#d3d6d8'], [0.6, '#f1e6d6'], [0.85, '#fcd9ae']], v),
    skyBottom: ramp([[0.1, '#d7dce2'], [0.38, '#eeede8'], [0.6, '#fbf7f0'], [0.85, '#fcf3e3']], v),
    sun: clamp((v - 0.48) / 0.25, 0, 1),
    cloudFill: ramp([[0.15, '#8c96a4'], [0.45, '#d9dce0'], [0.75, '#ffffff']], v),
    cloudCount: 1 + Math.round(clamp((0.8 - v) / 0.6, 0, 1) * 5),
    cloudOpacity: 0.55 + clamp(0.6 - v, 0, 0.4),
    rain: Math.max(clamp((0.33 - v) / 0.14, 0, 1) * 0.8, winter ? 0.55 : 0),
    snow: winter,
    shade: clamp((0.62 - v) * 0.42, 0, 0.2),
    grassA: mix('#c5d3a6', '#d3c9a0', dry),
    grassB: mix('#bdcc9d', '#c9be91', dry),
    hillA: mix('#daddc4', '#ded6bc', dry),
    hillB: mix('#cbd4b2', '#d4c9a6', dry),
    meadow: mix('#c3cda8', '#cec29c', dry),
    glow: 0.55 + clamp((0.62 - v) * 1.2, 0, 0.45),
  }
}

// Fixed raindrop positions for a scene, so the rain looks the same each load.
export function raindrops(seed, count, box) {
  const rand = mulberry32(seed)
  return Array.from({ length: count }, () => ({ x: box.x + rand() * box.w, y: box.y + rand() * box.h, delay: -rand() * 0.7 }))
}
```

- [ ] **Step 5: Run the tests**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townGeometry.test.js src/next/__tests__/townMood.test.js`
Expected: PASS. If the 50-lot count differs, print the counts by kind and fix the layout, not the test: the spec fixes 50 lots.

- [ ] **Step 6: Full suite, lint, e2e, commit**

Run the full Vitest suite, `npm run lint`, `npm run test:e2e`; all pass.

```bash
git add frontend-react/src/next/town frontend-react/src/next/__tests__/townGeometry.test.js frontend-react/src/next/__tests__/townMood.test.js
git commit -m "feat(next): living-town island layout, mood and scene palette

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Tracked-person fields, this week's events, lots and houses over time

**Files:**
- Modify: `frontend-react/src/next/data/session.js` (`SUBJECT_FIELDS`), `frontend-react/src/next/data/derive.js` (add `eventsAt`)
- Create: `frontend-react/src/next/town/lots.js`, `frontend-react/src/next/town/houses.js`
- Test: `frontend-react/src/next/__tests__/townLots.test.js`, `frontend-react/src/next/__tests__/townHouses.test.js`; extend `session.test.js` and `derive.test.js`

**Interfaces:**
- Consumes: `LOT_CAPACITY`, `HOUSES`, `mulberry32` from `town/geometry.js`.
- Produces: subjects in `arm.snapshots[tick].subjects` carry `health` and `happiness` (0–1, or null). `eventsAt(arm, tick) → event[]` (events recorded for exactly that tick, in arrival order). `lotAssignment(arm, capacity = LOT_CAPACITY) → Map<firmId, lotIndex | null>`. `houseRank(seed) → number[]` (rank per house). `houseStates({ out, homeless, total }, rank) → { states: ('work'|'look'|'home')[], counts: { work, look, home } }`. `houseWeeks(arm, tick, rank) → number[]` (weeks each house has been in its state at `tick`, 1 for a new state).

- [ ] **Step 1: Write the failing tests**

Add to `session.test.js` (keep its existing imports):

```js
test('tracked subjects keep health and happiness', () => {
  const [arm] = demoArms()
  const subjects = arm.snapshots[arm.ticks[60]].subjects
  expect(subjects.length).toBeGreaterThan(0)
  for (const subject of subjects) {
    expect(typeof subject.health).toBe('number')
    expect(typeof subject.happiness).toBe('number')
  }
})
```

Add to `derive.test.js`:

```js
test('eventsAt lists only that week's events', () => {
  const arm = { events: [{ tick: 3, id: 'a' }, { tick: 4, id: 'b' }, { tick: 4, id: 'c' }, { tick: 6, id: 'd' }] }
  expect(eventsAt(arm, 4).map(event => event.id)).toEqual(['b', 'c'])
  expect(eventsAt(arm, 5)).toEqual([])
  expect(eventsAt({}, 1)).toEqual([])
})
```

`frontend-react/src/next/__tests__/townLots.test.js`:

```js
import { describe, expect, test } from 'vitest'
import { lotAssignment } from '../town/lots.js'
import { demoArms } from './fixture.js'

// A tiny arm: firms present per week (open ids, closed ids).
function armOf(weeks) {
  const arm = { ticks: [], snapshots: {} }
  weeks.forEach(([open, closed], i) => {
    const tick = i + 1
    arm.ticks.push(tick)
    arm.snapshots[tick] = { firms: open.map(id => ({ id })), firmsClosed: closed.map(id => ({ id })) }
  })
  return arm
}

describe('lotAssignment', () => {
  test('a firm keeps its lot, nearest-first, while it is open or recently closed', () => {
    const arm = armOf([[[1, 2], []], [[1, 2, 3], []], [[2, 3], [1]]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(2)).toBe(1)
    expect(lots.get(3)).toBe(2)
  })

  test('frees a lot when its firm leaves the closed list, for a later firm', () => {
    const arm = armOf([[[1, 2], []], [[2], [1]], [[2], []], [[2, 4], []]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(4)).toBe(0)
  })

  test('never gives one lot to two firms at the same time, and counts the overflow', () => {
    const arm = armOf([[[1, 2, 3], []], [[1, 2, 3, 4], []]])
    const lots = lotAssignment(arm, 3)
    expect(lots.get(4)).toBeNull()
    expect(new Set([1, 2, 3].map(id => lots.get(id))).size).toBe(3)
  })

  test('extends as weeks arrive without changing earlier answers', () => {
    const arm = armOf([[[1], []], [[1, 2], []]])
    expect(lotAssignment(arm, 4).get(2)).toBe(1)
    arm.ticks.push(3)
    arm.snapshots[3] = { firms: [{ id: 1 }, { id: 2 }, { id: 9 }], firmsClosed: [] }
    const lots = lotAssignment(arm, 4)
    expect(lots.get(2)).toBe(1)
    expect(lots.get(9)).toBe(2)
  })

  test('fits the whole demo without overflow', () => {
    const [a, b] = demoArms()
    for (const arm of [a, b]) {
      const lots = lotAssignment(arm)
      for (const lot of lots.values()) expect(lot).not.toBeNull()
    }
  })
})
```

`frontend-react/src/next/__tests__/townHouses.test.js`:

```js
import { describe, expect, test } from 'vitest'
import { houseRank, houseStates, houseWeeks } from '../town/houses.js'
import { demoArms } from './fixture.js'

describe('houses', () => {
  test('the rank is a fixed shuffle of 0..99 per seed', () => {
    const rank = houseRank(1337)
    expect([...rank].sort((x, y) => x - y)).toEqual(Array.from({ length: 100 }, (_, i) => i))
    expect(houseRank(1337)).toEqual(rank)
    expect(houseRank(7)).not.toEqual(rank)
  })

  test('the lowest ranks lose their homes, the next look for work', () => {
    const rank = houseRank(1)
    const { states, counts } = houseStates({ out: 30, homeless: 10, total: 500 }, rank)
    expect(counts).toEqual({ home: 2, look: 30, work: 68 })
    states.forEach((state, i) => {
      if (rank[i] < 2) expect(state).toBe('home')
      else if (rank[i] < 32) expect(state).toBe('look')
      else expect(state).toBe('work')
    })
  })

  test('missing figures mean everyone works', () => {
    expect(houseStates({ out: null, homeless: null, total: null }, houseRank(1)).counts).toEqual({ home: 0, look: 0, work: 100 })
  })

  test('counts how long each house has been in its state', () => {
    const [arm] = demoArms()
    const rank = houseRank(arm.setup.seed)
    const at40 = houseWeeks(arm, 40, rank)
    const at41 = houseWeeks(arm, 41, rank)
    expect(at40).toHaveLength(100)
    const out40 = houseStates({ out: arm.series.peopleOutOfWorkPer100[arm.ticks.indexOf(40)], homeless: 0, total: 500 }, rank).states
    const out41 = houseStates({ out: arm.series.peopleOutOfWorkPer100[arm.ticks.indexOf(41)], homeless: 0, total: 500 }, rank).states
    for (let h = 0; h < 100; h += 1) expect(at41[h]).toBe(out40[h] === out41[h] ? at40[h] + 1 : 1)
  })
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townLots.test.js src/next/__tests__/townHouses.test.js src/next/__tests__/session.test.js src/next/__tests__/derive.test.js`
Expected: FAIL (missing modules, `eventsAt` not exported, subjects lack `health`).

- [ ] **Step 3: Implement**

`session.js`: append `'health', 'happiness'` to `SUBJECT_FIELDS`.

`derive.js`, after `eventsUpTo`:

```js
// The events recorded for exactly `tick`, in arrival order.
export function eventsAt(arm, tick) {
  const events = arm?.events ?? []
  const out = []
  for (let i = eventIndexAt(arm, tick); i >= 0 && events[i].tick === tick; i -= 1) out.push(events[i])
  return out.reverse()
}
```

`town/lots.js`:

```js
// Where each firm stands on the island. A firm takes the first free lot
// (nearest the crossing first) in the week it is first seen and keeps it until
// it leaves the server's closed list, about a year after closing; the lot is
// then free for a later firm. With every lot taken, a new firm gets null and is
// counted, never drawn on top of another. The answer is replayed over the
// arm's weeks in order and cached on the arm's shared `ticks` array, so new
// weeks extend it and earlier answers never change.
import { LOT_CAPACITY } from './geometry.js'

const cache = new WeakMap()

export function lotAssignment(arm, capacity = LOT_CAPACITY) {
  const ticks = arm?.ticks ?? []
  let state = cache.get(ticks)
  const stale = !state || state.capacity !== capacity || state.done > ticks.length || (state.done > 0 && ticks[state.done - 1] !== state.lastTick)
  if (stale) state = { capacity, done: 0, lastTick: null, lotOf: new Map(), holder: new Array(capacity).fill(null) }
  for (let i = state.done; i < ticks.length; i += 1) {
    const snapshot = arm.snapshots?.[ticks[i]]
    const present = new Set([...(snapshot?.firms ?? []), ...(snapshot?.firmsClosed ?? [])].map(firm => firm.id))
    state.holder.forEach((id, lot) => { if (id != null && !present.has(id)) state.holder[lot] = null })
    for (const id of [...present].sort((a, b) => a - b)) {
      if (state.lotOf.has(id)) continue
      const lot = state.holder.indexOf(null)
      state.lotOf.set(id, lot >= 0 ? lot : null)
      if (lot >= 0) state.holder[lot] = id
    }
    state.done = i + 1
    state.lastTick = ticks[i]
  }
  if (ticks.length) cache.set(ticks, state)
  return state.lotOf
}
```

`town/houses.js`:

```js
// The 100 houses each stand for 1/100 of the town's households. Each house has
// a fixed rank from the town's seed (the same shuffle the old town drawing
// used): the lowest ranks lose their homes first, the next look for work, so
// when a figure moves only the houses at the edge change.
import { valueAt } from '../data/derive.js'
import { HOUSES, mulberry32 } from './geometry.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const ranks = new Map()

export function houseRank(seed) {
  const key = Number(seed) || 0
  if (ranks.has(key)) return ranks.get(key)
  const rand = mulberry32(key)
  const order = Array.from({ length: HOUSES }, (_, i) => i)
  for (let i = HOUSES - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  const rank = new Array(HOUSES)
  order.forEach((house, position) => { rank[house] = position })
  ranks.set(key, rank)
  return rank
}

export function houseStates({ out, homeless, total }, rank) {
  const home = total > 0 ? clamp(Math.round((100 * (homeless ?? 0)) / total), 0, HOUSES) : 0
  const look = clamp(Math.round(out ?? 0), 0, HOUSES - home)
  const states = rank.map(r => (r < home ? 'home' : r < home + look ? 'look' : 'work'))
  return { states, counts: { home, look, work: HOUSES - home - look } }
}

// Weeks each house has been in its current state, per recorded week, cached
// on the arm's shared `ticks` array and extended as weeks arrive.
const runs = new WeakMap()

export function houseWeeks(arm, tick, rank) {
  const ticks = arm?.ticks ?? []
  let state = runs.get(ticks)
  const stale = !state || state.rank !== rank || state.rows.length > ticks.length || (state.rows.length > 0 && ticks[state.rows.length - 1] !== state.lastTick)
  if (stale) state = { rank, rows: [], prev: null, lastTick: null }
  for (let i = state.rows.length; i < ticks.length; i += 1) {
    const at = ticks[i]
    const { states } = houseStates({
      out: valueAt(arm, 'peopleOutOfWorkPer100', at),
      homeless: valueAt(arm, 'homelessHouseholds', at),
      total: valueAt(arm, 'householdsTotal', at),
    }, rank)
    const prevRow = state.rows[i - 1]
    state.rows.push(states.map((s, h) => (state.prev && state.prev[h] === s ? prevRow[h] + 1 : 1)))
    state.prev = states
    state.lastTick = at
  }
  if (ticks.length) runs.set(ticks, state)
  let index = -1
  for (let i = ticks.length - 1; i >= 0; i -= 1) if (ticks[i] <= tick) { index = i; break }
  return index < 0 ? new Array(HOUSES).fill(1) : state.rows[index]
}
```

- [ ] **Step 4: Run the tests**

Run the four test files from Step 2. Expected: PASS.

- [ ] **Step 5: Full suite, lint, e2e, commit**

```bash
git add frontend-react/src/next/data frontend-react/src/next/town frontend-react/src/next/__tests__
git commit -m "feat(next): tracked health and happiness, this week's events, stable shop lots and house history

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The town model and card contents

**Files:**
- Create: `frontend-react/src/next/town/model.js`, `frontend-react/src/next/town/cards.js`
- Modify: `frontend-react/src/next/catalog.js` (add `COPY.diorama`)
- Test: `frontend-react/src/next/__tests__/townModel.test.js`, `frontend-react/src/next/__tests__/townCards.test.js`

**Interfaces:**
- Consumes: `eventsAt`, `snapshotAt`, `valueAt`, `rulesAt`, `rulesDiff` (`data/derive.js`); `firmDisplayName`, `householdName` (`names.js`); `LAYOUT`, `personHouses` (`town/geometry.js`); `moodOf`, `moodBand`, `seasonOf` (`town/mood.js`); `houseRank`, `houseStates`, `houseWeeks` (`town/houses.js`); `lotAssignment` (`town/lots.js`); `WARMUP_TICKS`, `COPY` (`catalog.js`).
- Produces: `townAt(arm, tick) → TownModel` and `placeCard(model, target, total) → Card | null` (`total` = households in the town, for the house card), with:

```text
TownModel = {
  tick, warmUp, mood, band, season,
  houses: [{ state, weeks }] (100), counts: { work, look, home },
  shops: [{ id, name, sector, staff, cash, state: 'steady'|'growing'|'struggling'|'closed', lot, floors,
            age, fresh, isNew, coop, richest, hired, laidOff, closedTick, closedFor }],
  overflow,
  hall: { cash, income, support, queue, banner, changedTick },
  bank: { loans, bad, papers, badNow },
  people: [{ id, name, age, house, working, cash, health, happiness, weeksOut, rentOwed, employer, tone: 'work'|'look'|'low' }],
  flows: { spend, pay, tax, help },
  traffic: { cars, walkers },
  week: { opened: firmId[], closed: firmId[], hires: [firmId, n][], layoffs: [firmId, n][], bad },
  facts: { out, pay, open, struggling, hallCash },
}
target = { kind: 'house'|'shop'|'hall'|'bank'|'person', index?: number, id?: number }
Card = { title, sub, rows: [label, value][], note: string|null, tag: { text, tone: 'good'|'warn'|'bad'|'quiet'|'info' } }
```

- [ ] **Step 1: Add the copy**

In `catalog.js`, inside `COPY`, after `town`:

```js
  // The living-town drawings (town/), their cards, legend and summary.
  diorama: {
    moods: { thriving: 'Thriving', okay: 'Getting by', struggling: 'Struggling', hard: 'Hard times' },
    enlarge: 'Enlarge',
    showAll: n => (n === 2 ? 'Show both' : 'Show all'),
    mainStreet: 'Main Street, up close',
    mainStreetFor: (label, rules) => `${label} · ${rules}`,
    moreLots: n => `+${n} more`,
    signs: { hiring: 'HIRING', sale: 'SALE', closed: 'CLOSED', lease: 'FOR LEASE', fresh: 'NEW', forSale: 'FOR SALE', owes: 'owes', hall: 'TOWN HALL', bank: 'BANK' },
    moments: { closed: 'Closed', opened: 'Opened!', lost: n => `−${n} jobs`, gained: n => `+${n} jobs`, badLoans: amount => `Bad loans ${amount}` },
    banner: {
      minimum_wage_policy: 'NEW MIN. WAGE', benefit_level: 'NEW BENEFITS', wage_tax_rate: 'NEW WAGE TAX', profit_tax_rate: 'NEW PROFIT TAX',
      investment_tax_rate: 'NEW INVEST. TAX', public_works: 'PUBLIC WORKS', sector_subsidy_target: 'SUBSIDIES', sector_subsidy_level: 'SUBSIDIES',
      price_stabilization_target: 'PRICE CONTROLS', price_stabilization_level: 'PRICE CONTROLS', rent_stabilization_level: 'RENT CONTROLS',
      infrastructure_spending: 'NEW SPENDING', technology_spending: 'NEW SPENDING', social_spending: 'NEW SPENDING',
      bailout_policy: 'BAILOUTS', bailout_target: 'BAILOUTS', bailout_budget: 'BAILOUTS', many: 'NEW RULES',
    },
    legend: {
      working: 'lights on: working', looking: 'dark: looking for work', lost: 'lost their home',
      spend: 'spending at shops', pay: 'pay to workers', tax: 'taxes to the town hall', help: 'help from the town hall',
      pins: 'pins: people you follow', perHouse: total => COPY.town.houseScale(total),
    },
    summary: {
      mood: band => ({ thriving: 'The town is thriving.', okay: 'The town is getting by.', struggling: 'The town is struggling.', hard: 'The town is going through hard times.' })[band],
      weather: (season, mood) => `It is ${season}; ${mood === 'hard' ? 'it is raining' : mood === 'struggling' ? 'it is cloudy' : 'the sun is out'}.`,
      overflow: n => `${n} more businesses than lots; they are not drawn.`,
    },
    card: {
      house: { work: 'A working home', look: 'Looking for work', home: 'Lost their home', sub: per => `stands for ${per}` },
      houseWork: weeks => `Lights on: the people here have jobs. Working for ${weeks} week${weeks === 1 ? '' : 's'} in a row.`,
      houseLook: weeks => (weeks >= 12 ? `Lights off: someone here lost their job ${weeks} weeks ago, so the garden has gone to weeds.` : `Lights off: someone here lost their job ${weeks} week${weeks === 1 ? '' : 's'} ago.`),
      houseHome: 'These families could not keep up with rent and had to leave.',
      staff: 'Staff', cash: 'Cash in the bank', coop: 'town co-op', closedOn: 'Closed', closedStaff: 'Staff when it closed',
      closedNote: lease => (lease ? 'Empty and up for lease.' : 'Boarded up. It ran out of cash.'),
      thisWeek: (hired, laid) => `This week: ${[hired ? `hired ${hired}` : '', laid ? `let ${laid} go` : ''].filter(Boolean).join(', ')}.`,
      richest: 'The richest shop in town, not counting the co-ops.',
      states: { building: 'Being built', fresh: 'Just opened', growing: 'Growing, hiring', struggling: 'Struggling to pay its bills', steady: 'Steady', closed: 'Closed' },
      hall: 'Town hall', taxes: 'Taxes in this week', help: 'Help paid to families', saved: 'Saved', owes: 'Owes', queue: n => `${n} people queuing for help.`,
      inDebt: 'In debt', inBlack: 'In the black',
      bank: 'The bank', bankSub: 'lends to shops and families', loans: 'Loans out', bad: 'Gone bad this week', badTag: 'Loans going bad', lending: 'Lending',
      person: 'someone you follow', worksAt: firm => `Works at ${firm}`, outFor: weeks => `Out of work for ${weeks} week${weeks === 1 ? '' : 's'}`,
      savings: 'Savings', health: 'Health', happiness: 'Happiness', rentOwed: 'Rent owed',
      word: value => (value == null ? '–' : value >= 0.66 ? 'good' : value >= 0.33 ? 'so-so' : 'low'),
      working: 'Working', looking: 'Looking for work',
    },
  },
```

`COPY.town.houseScale` already exists; `perHouse` reuses it.

- [ ] **Step 2: Write the failing model tests**

`frontend-react/src/next/__tests__/townModel.test.js`:

```js
import { beforeAll, describe, expect, test } from 'vitest'
import { townAt } from '../town/model.js'
import { demoArms, fixtureArm } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

describe('townAt', () => {
  test('warm-up weeks are neutral and quiet', () => {
    const model = townAt(A, 5)
    expect(model.warmUp).toBe(true)
    expect(model.mood).toBe(0.62)
    expect(model.hall.queue).toBe(0)
    expect(model.traffic.walkers).toBe(4)
  })

  test('houses follow out of work and homeless', () => {
    const model = townAt(A, 70)
    expect(model.houses).toHaveLength(100)
    expect(model.counts.look).toBe(Math.round(model.facts.out))
    expect(model.counts.work + model.counts.look + model.counts.home).toBe(100)
  })

  test('the demo towns part ways in mood by year 2', () => {
    const a = townAt(A, 100), b = townAt(B, 100)
    expect(a.band).toBe('hard')
    expect(b.mood).toBeGreaterThan(a.mood)
  })

  test('shops: one per lot, states, floors, the richest private shop', () => {
    const model = townAt(A, 70)
    const lots = model.shops.map(shop => shop.lot)
    expect(new Set(lots).size).toBe(lots.length)
    for (const shop of model.shops) {
      expect(['steady', 'growing', 'struggling', 'closed']).toContain(shop.state)
      expect(shop.floors).toBeGreaterThanOrEqual(1)
      expect(shop.floors).toBeLessThanOrEqual(6)
      expect(typeof shop.name).toBe('string')
    }
    const richest = model.shops.filter(shop => shop.richest)
    expect(richest).toHaveLength(1)
    const open = model.shops.filter(shop => shop.state !== 'closed' && !shop.coop)
    expect(richest[0].cash).toBe(Math.max(...open.map(shop => shop.cash)))
    expect(richest[0].coop).toBe(false)
  })

  test('a shop that closed at week 70 is closed for 0 weeks then; firms of week 1 are not new', () => {
    const model = townAt(A, 70)
    const closedNow = model.shops.find(shop => shop.state === 'closed' && shop.closedTick === 70)
    expect(closedNow?.closedFor).toBe(0)
    expect(model.week.closed).toContain(closedNow.id)
    for (const shop of townAt(A, 12).shops.filter(s => s.coop)) expect(shop.isNew || shop.fresh).toBe(false)
  })

  test('the bank and the town hall', () => {
    const model = townAt(A, 70)
    expect(model.bank.bad).toBeGreaterThan(19000)
    expect(model.bank.badNow).toBe(true)
    expect(model.bank.papers).toBeGreaterThan(0)
    expect(model.hall.cash).toBeLessThan(0)
    expect(townAt(A, 70).hall.banner).toBeNull()
    expect(townAt(B, 70).hall.banner).toBe('NEW MIN. WAGE')
  })

  test('people: the first four tracked households, each in a distinct house', () => {
    const model = townAt(A, 60)
    expect(model.people).toHaveLength(4)
    expect(new Set(model.people.map(person => person.house)).size).toBe(4)
    const nikhil = model.people.find(person => person.name === 'Nikhil')
    expect(nikhil.working).toBe(false)
    expect(nikhil.weeksOut).toBeGreaterThan(20)
    expect(['look', 'low']).toContain(nikhil.tone)
  })

  test('an arm without happiness or bank figures still builds a model', () => {
    const model = townAt(fixtureArm(), 11)
    expect(Number.isFinite(model.mood)).toBe(true)
    expect(model.bank.papers).toBe(0)
    expect(model.bank.badNow).toBe(false)
  })

  test('traffic and flows follow the money', () => {
    const model = townAt(A, 40)
    expect(model.traffic.cars).toBe(Math.max(0, Math.min(7, Math.round(model.flows.spend / 5000))))
    expect(model.flows.pay).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 3: Write `town/model.js`**

```js
// Everything the drawings need for one town in one week, from the arm alone.
import { COPY, WARMUP_TICKS } from '../catalog.js'
import { eventsAt, rulesAt, rulesDiff, snapshotAt, valueAt } from '../data/derive.js'
import { firmDisplayName, householdName } from '../names.js'
import { personHouses } from './geometry.js'
import { houseRank, houseStates, houseWeeks } from './houses.js'
import { lotAssignment } from './lots.js'
import { moodBand, moodOf, seasonOf } from './mood.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const STATES = new Set(['steady', 'growing', 'struggling'])
export const floorsOf = staff => clamp(Math.ceil(Math.max(1, staff ?? 1) / 9), 1, 6)
export const WEEKS = { fresh: 3, isNew: 9, lease: 8, longOut: 12, pulse: 4 }

// First week each firm appears, cached on the arm's shared `ticks` array.
const firstSeenCache = new WeakMap()
function firstSeen(arm) {
  const ticks = arm?.ticks ?? []
  let state = firstSeenCache.get(ticks)
  if (!state || state.done > ticks.length) state = { done: 0, seen: new Map() }
  for (let i = state.done; i < ticks.length; i += 1) {
    for (const firm of arm.snapshots?.[ticks[i]]?.firms ?? []) if (!state.seen.has(firm.id)) state.seen.set(firm.id, ticks[i])
    state.done = i + 1
  }
  if (ticks.length) firstSeenCache.set(ticks, state)
  return state.seen
}

function bannerFor(diff) {
  const labels = new Set(Object.keys(diff).map(lever => COPY.diorama.banner[lever] ?? COPY.diorama.banner.many))
  if (labels.size === 0) return null
  return labels.size === 1 ? [...labels][0] : COPY.diorama.banner.many
}

function lastChange(arm, tick) {
  const changes = arm?.policyChanges ?? []
  for (let i = changes.length - 1; i >= 0; i -= 1) if (changes[i].tick <= tick) return changes[i].tick > tick - WEEKS.pulse ? changes[i].tick : null
  return null
}

const countBy = (events, type) => {
  const counts = new Map()
  for (const event of events) if (event.type === type && event.firmId != null) counts.set(event.firmId, (counts.get(event.firmId) ?? 0) + 1)
  return counts
}

export function townAt(arm, tick) {
  const warmUp = tick <= WARMUP_TICKS
  const out = valueAt(arm, 'peopleOutOfWorkPer100', tick)
  const total = valueAt(arm, 'householdsTotal', tick)
  const homeless = valueAt(arm, 'homelessHouseholds', tick)
  const pay = valueAt(arm, 'typicalWeeklyPay', tick)
  const rank = houseRank(arm?.setup?.seed)
  const { states, counts } = houseStates({ out, homeless, total }, rank)
  const weeks = houseWeeks(arm, tick, rank)
  const mood = moodOf({ out, happiness: valueAt(arm, 'happiness', tick), warmUp })

  const snapshot = snapshotAt(arm, tick)
  const byId = arm?.firmDirectory?.byId ?? {}
  const byName = arm?.firmDirectory?.byName ?? {}
  const lotOf = lotAssignment(arm)
  const seen = firstSeen(arm)
  const events = eventsAt(arm, tick)
  const hires = countBy(events, 'hired')
  const layoffs = countBy(events, 'laid_off')
  const firstTick = arm?.ticks?.[0] ?? 1

  const shops = []
  let overflow = 0
  for (const firm of snapshot?.firms ?? []) {
    const lot = lotOf.get(firm.id) ?? null
    if (lot == null) { overflow += 1; continue }
    const first = seen.get(firm.id) ?? tick
    const age = first <= firstTick ? Infinity : tick - first
    shops.push({
      id: firm.id, name: firmDisplayName(byId[firm.id] ?? firm), sector: firm.sector ?? byId[firm.id]?.sector ?? null,
      staff: firm.staff ?? 0, cash: firm.cash ?? 0, state: STATES.has(firm.state) ? firm.state : 'steady', lot, floors: floorsOf(firm.staff),
      age, fresh: age < WEEKS.fresh, isNew: age >= WEEKS.fresh && age < WEEKS.isNew, coop: Boolean(firm.isBaseline ?? byId[firm.id]?.isBaseline),
      richest: false, hired: hires.get(firm.id) ?? 0, laidOff: layoffs.get(firm.id) ?? 0, closedTick: null, closedFor: null,
    })
  }
  for (const firm of snapshot?.firmsClosed ?? []) {
    const lot = lotOf.get(firm.id) ?? null
    if (lot == null) { overflow += 1; continue }
    shops.push({
      id: firm.id, name: firmDisplayName(byId[firm.id] ?? firm), sector: firm.sector ?? null, staff: firm.lastStaff ?? 0, cash: null,
      state: 'closed', lot, floors: floorsOf(firm.lastStaff), age: Infinity, fresh: false, isNew: false, coop: Boolean(byId[firm.id]?.isBaseline),
      richest: false, hired: 0, laidOff: 0, closedTick: firm.closedTick, closedFor: tick - firm.closedTick,
    })
  }
  const open = shops.filter(shop => shop.state !== 'closed')
  const contenders = open.filter(shop => !shop.coop)
  if (contenders.length) contenders.reduce((best, shop) => (shop.cash > best.cash ? shop : best)).richest = true

  const support = valueAt(arm, 'familySupportPaid', tick) ?? 0
  const loans = valueAt(arm, 'bankActiveLoans', tick)
  const bad = valueAt(arm, 'bankDefaultAmountThisTick', tick) ?? 0
  const sales = valueAt(arm, 'salesExceptRentThisWeek', tick) ?? 0
  const staffTotal = open.reduce((sum, shop) => sum + shop.staff, 0)

  const subjects = (snapshot?.subjects ?? []).slice(0, 4)
  const houses = personHouses(subjects.map(subject => subject.id))
  const people = subjects.map((subject, i) => ({
    id: subject.id, name: householdName(subject.id), age: subject.age ?? arm?.profiles?.[subject.id]?.age ?? null, house: houses[i],
    working: Boolean(subject.isEmployed), cash: subject.cash ?? null, health: subject.health ?? null, happiness: subject.happiness ?? null,
    weeksOut: subject.unemploymentDuration ?? 0, rentOwed: subject.rentArrears ?? 0,
    employer: subject.isEmployed && subject.employer ? firmDisplayName(byName[subject.employer] ?? { name: subject.employer, sector: subject.employerCategory }) : null,
    tone: subject.isEmployed ? 'work' : (subject.happiness ?? 1) < 0.2 ? 'low' : 'look',
  }))

  return {
    tick, warmUp, mood, band: moodBand(mood), season: seasonOf(tick),
    houses: states.map((state, i) => ({ state, weeks: weeks[i] })), counts,
    shops, overflow,
    hall: {
      cash: valueAt(arm, 'townHallCash', tick), income: valueAt(arm, 'townHallIncome', tick), support,
      queue: warmUp ? 0 : clamp(Math.round(support / 2800), 0, 9),
      banner: bannerFor(rulesDiff(rulesAt(arm, tick))), changedTick: lastChange(arm, tick),
    },
    bank: { loans, bad, papers: clamp(Math.round((loans ?? 0) / 55), 0, 7), badNow: bad >= 500 },
    people,
    flows: { spend: sales, pay: staffTotal * (pay ?? 0), tax: valueAt(arm, 'townHallIncome', tick) ?? 0, help: support },
    traffic: { cars: clamp(Math.round(sales / 5000), 0, 7), walkers: warmUp ? 4 : clamp(Math.round((counts.work / 100) * 14), 1, 14) },
    week: {
      opened: events.filter(event => event.type === 'firm_opened').map(event => event.firmId),
      closed: events.filter(event => event.type === 'firm_closed').map(event => event.firmId),
      hires: [...hires], layoffs: [...layoffs], bad,
    },
    facts: { out, pay, open: open.length, struggling: open.filter(shop => shop.state === 'struggling').length, hallCash: valueAt(arm, 'townHallCash', tick) },
  }
}
```

If the demo's Town B banner test fails because `rulesAt` returns the lever under another name, print `rulesDiff(rulesAt(B, 70))` and map that key in `COPY.diorama.banner`.

- [ ] **Step 4: Write the failing card tests**

`frontend-react/src/next/__tests__/townCards.test.js`:

```js
import { beforeAll, describe, expect, test } from 'vitest'
import { placeCard } from '../town/cards.js'
import { townAt } from '../town/model.js'
import { demoArms } from './fixture.js'

let model
beforeAll(() => { model = townAt(demoArms()[0], 70) })

describe('placeCard', () => {
  test('a dark house says how long it has been dark', () => {
    const index = model.houses.findIndex(house => house.state === 'look')
    const card = placeCard(model, { kind: 'house', index }, 500)
    expect(card.title).toBe('Looking for work')
    expect(card.note).toMatch(/lost their job/)
    expect(card.tag.tone).toBe('warn')
  })

  test('the richest shop says so', () => {
    const shop = model.shops.find(s => s.richest)
    const card = placeCard(model, { kind: 'shop', id: shop.id })
    expect(card.title).toBe(shop.name)
    expect(card.note).toMatch(/richest/)
    expect(card.rows.map(([label]) => label)).toEqual(['Staff', 'Cash in the bank'])
  })

  test('a closed shop names its closing week', () => {
    const shop = model.shops.find(s => s.state === 'closed')
    const card = placeCard(model, { kind: 'shop', id: shop.id })
    expect(card.rows[0][0]).toBe('Closed')
    expect(card.rows[0][1]).toMatch(/Year \d, week \d+/)
  })

  test('the town hall, the bank and a person', () => {
    expect(placeCard(model, { kind: 'hall' }).tag.text).toBe('In debt')
    expect(placeCard(model, { kind: 'bank' }).tag.text).toBe('Loans going bad')
    const person = placeCard(model, { kind: 'person', index: 0 })
    expect(person.sub).toBe('someone you follow')
    expect(person.rows.map(([label]) => label)).toEqual(expect.arrayContaining(['Savings', 'Health', 'Happiness']))
  })

  test('an unknown target gives no card', () => {
    expect(placeCard(model, { kind: 'shop', id: -1 })).toBeNull()
    expect(placeCard(model, { kind: 'nothing' })).toBeNull()
  })
})
```

- [ ] **Step 5: Write `town/cards.js`**

```js
// What a card says about the place under the pointer, for one week's model.
import { COPY, formatMoneyShort, householdsPerHouse, sectorName } from '../catalog.js'
import { weekLabel } from '../narration.js'

const T = COPY.diorama.card

export function placeCard(model, target, total) {
  if (!model || !target) return null
  if (target.kind === 'house') {
    const house = model.houses[target.index]
    if (!house) return null
    const sub = T.house.sub(householdsPerHouse(total))
    if (house.state === 'work') return { title: T.house.work, sub, rows: [], note: T.houseWork(house.weeks), tag: { text: T.working, tone: 'good' } }
    if (house.state === 'look') return { title: T.house.look, sub, rows: [], note: T.houseLook(house.weeks), tag: { text: T.looking, tone: 'warn' } }
    return { title: T.house.home, sub, rows: [], note: T.houseHome, tag: { text: COPY.diorama.legend.lost, tone: 'bad' } }
  }
  if (target.kind === 'shop') {
    const shop = model.shops.find(s => s.id === target.id)
    if (!shop) return null
    const sub = `${sectorName(shop.sector)}${shop.coop ? ` · ${T.coop}` : ''}`
    if (shop.state === 'closed') {
      return {
        title: shop.name, sub, rows: [[T.closedOn, weekLabel(shop.closedTick)], [T.closedStaff, String(shop.staff)]],
        note: T.closedNote(shop.closedFor >= 8), tag: { text: T.states.closed, tone: 'quiet' },
      }
    }
    const notes = []
    if (shop.hired || shop.laidOff) notes.push(T.thisWeek(shop.hired, shop.laidOff))
    if (shop.richest) notes.push(T.richest)
    const state = shop.fresh ? 'building' : shop.isNew ? 'fresh' : shop.state
    const tone = { building: 'info', fresh: 'info', growing: 'good', struggling: 'warn', steady: 'quiet' }[state]
    return {
      title: shop.name, sub, rows: [[T.staff, String(shop.staff)], [T.cash, formatMoneyShort(shop.cash)]],
      note: notes.length ? notes.join(' ') : null, tag: { text: T.states[state], tone },
    }
  }
  if (target.kind === 'hall') {
    const { cash, income, support, queue } = model.hall
    return {
      title: T.hall, sub: null,
      rows: [[T.taxes, formatMoneyShort(income)], [T.help, formatMoneyShort(support)], [cash < 0 ? T.owes : T.saved, formatMoneyShort(Math.abs(cash ?? 0))]],
      note: queue ? T.queue(queue) : null, tag: cash < 0 ? { text: T.inDebt, tone: 'bad' } : { text: T.inBlack, tone: 'good' },
    }
  }
  if (target.kind === 'bank') {
    const { loans, bad, badNow } = model.bank
    return {
      title: T.bank, sub: T.bankSub, rows: [[T.loans, loans == null ? '–' : String(loans)], [T.bad, formatMoneyShort(bad)]],
      note: null, tag: badNow ? { text: T.badTag, tone: 'bad' } : { text: T.lending, tone: 'good' },
    }
  }
  if (target.kind === 'person') {
    const person = model.people[target.index]
    if (!person) return null
    const rows = [[T.savings, formatMoneyShort(person.cash)], [T.health, T.word(person.health)], [T.happiness, T.word(person.happiness)]]
    if (person.rentOwed > 0) rows.push([T.rentOwed, formatMoneyShort(person.rentOwed)])
    return {
      title: person.age == null ? person.name : `${person.name}, ${person.age}`, sub: T.person, rows,
      note: person.working ? T.worksAt(person.employer ?? '') : T.outFor(person.weeksOut),
      tag: person.working ? { text: T.working, tone: 'good' } : { text: T.looking, tone: 'warn' },
    }
  }
  return null
}
```

Check `householdsPerHouse` and `formatMoneyShort` in `catalog.js` before relying on their outputs; if `householdsPerHouse(total)` returns a number, wrap it with the existing `counted(n, 'household')` helper so the sub reads "stands for 5 households".

- [ ] **Step 6: Run the tests**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townModel.test.js src/next/__tests__/townCards.test.js src/next/__tests__/catalog.test.js`
Expected: PASS.

- [ ] **Step 7: Full suite, lint, e2e, commit**

```bash
git add frontend-react/src/next
git commit -m "feat(next): town model for the living-town drawings, and place cards

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The diorama on the Run screen (still pictures)

**Files:**
- Create: `frontend-react/src/next/town/parts.jsx`, `frontend-react/src/next/town/Diorama.jsx`, `frontend-react/src/next/town/weather.js`, `frontend-react/src/next/town/TownCard.jsx`, `frontend-react/src/next/town/Legend.jsx`, `frontend-react/src/next/town/town.css`
- Modify: `frontend-react/src/next/RunScreen.jsx`, `frontend-react/src/next/next.css`, `frontend-react/src/next/__tests__/RunScreen.test.jsx` (and any test that asserted the old town markup)
- Delete: `frontend-react/src/next/components/Town.jsx`, `frontend-react/src/next/__tests__/Town.test.jsx`
- Test: `frontend-react/src/next/__tests__/TownCard.test.jsx`

**Interfaces:**
- Consumes: `townAt`, `placeCard` (Task 4); `LAYOUT`, `PAINT_ORDER`, `VIEWBOX`, `HALL`, `BANK`, `iso`, `pts` (Task 2); `scenePalette`, `raindrops` (Task 2).
- Produces:
  - `Diorama({ model, color, sceneRef })`: `<svg viewBox={VIEWBOX} aria-hidden class="lt-scene season-<season>">`. Every house, shop, the hall, the bank and each pin carries `data-kind` (`house|shop|hall|bank|person`) and `data-index` (house and person index) or `data-id` (shop id) for Task 7. Every tile slot is `<g data-slot="gx,gy">` for Task 6. Named layer groups for Task 6: `<g data-layer="coins">`, `data-layer="pings"`, `data-layer="moments"`, `data-layer="clouds"` (six cloud groups `data-cloud="k"`), `data-layer="rain"`; flash targets `data-flash="bank"`.
  - `applyWeather(svg, palette)` in `weather.js`: sets CSS variables `--lt-sky-top`, `--lt-sky-bottom`, `--lt-sun`, `--lt-cloud-fill`, `--lt-rain`, `--lt-shade`, `--lt-grass-a`, `--lt-grass-b`, `--lt-glow`, `--lt-hill-a`, `--lt-hill-b`, `--lt-meadow` on the `svg` element, sets each `[data-cloud=k]` opacity (`k < cloudCount ? cloudOpacity : 0`) and toggles `is-snow` on `[data-layer=rain]`.
  - `TownCard({ arm, tick, focused, canFocus, onFocus, towns, children })`: `<article class="nx-card lt-card" data-stable="town-<label>">` with header (`lt-head`: colour chip, `<h2>` label, rules text, mood chip `lt-mood is-<band>` with fixed width, Enlarge/Show button when `canFocus`), `<div class="lt-canvas">` holding the Diorama, the facts row (`lt-facts`, four facts with fixed two-line labels), and the `.nx-sr` summary list.
  - `Legend({ arms, tick })`.

- [ ] **Step 1: Write the failing component tests**

`frontend-react/src/next/__tests__/TownCard.test.jsx`:

```jsx
import { beforeAll, describe, expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TownCard from '../town/TownCard.jsx'
import RunScreen from '../RunScreen.jsx'
import { demoArms } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

describe('TownCard', () => {
  test('draws 100 houses in their states and every shop on a lot', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const houses = container.querySelectorAll('[data-kind="house"]')
    expect(houses).toHaveLength(100)
    const dark = [...houses].filter(house => house.classList.contains('is-look'))
    expect(dark.length).toBe(34)
    expect(container.querySelectorAll('[data-kind="shop"]').length).toBeGreaterThan(15)
    expect(container.querySelectorAll('[data-slot]')).toHaveLength(256)
  })

  test('the mood chip and the summary name how the town is doing', () => {
    render(<TownCard arm={A} tick={100} towns={2} />)
    expect(screen.getByText('Hard times')).toBeInTheDocument()
    expect(screen.getByText('The town is going through hard times.')).toBeInTheDocument()
  })

  test('winter puts snow on the roofs, summer does not', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={102} towns={2} />)
    expect(container.querySelector('svg.lt-scene').classList.contains('season-winter')).toBe(true)
    rerender(<TownCard arm={A} tick={80} towns={2} />)
    expect(container.querySelector('svg.lt-scene').classList.contains('season-summer')).toBe(true)
  })

  test('shop signs: CLOSED in the first weeks after closing, a crown on the richest shop', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    expect(container.textContent).toContain('CLOSED')
    expect(container.querySelectorAll('.lt-crown')).toHaveLength(1)
  })

  test('Enlarge asks to focus the town', async () => {
    const calls = []
    render(<TownCard arm={A} tick={70} towns={2} canFocus onFocus={() => calls.push('focus')} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enlarge' }))
    expect(calls).toEqual(['focus'])
  })
})

describe('Run screen towns', () => {
  const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }

  test('one card per town, side by side, with the shared legend', () => {
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    expect(container.querySelectorAll('.lt-card')).toHaveLength(2)
    expect(container.querySelector('.lt-towns').classList.contains('is-2')).toBe(true)
    expect(container.querySelector('.lt-legend')).toBeInTheDocument()
  })

  test('one town fills the row; four towns make a 2 × 2 grid', () => {
    const { container, rerender } = render(<RunScreen arms={[A]} {...props} />)
    expect(container.querySelector('.lt-towns').classList.contains('is-1')).toBe(true)
    const [C, D] = demoArms()
    rerender(<RunScreen arms={[A, B, { ...C, label: 'Town C', color: '#199E70' }, { ...D, label: 'Town D', color: '#9085E9' }]} {...props} />)
    expect(container.querySelector('.lt-towns').classList.contains('is-4')).toBe(true)
  })

  test('Enlarge shows only that town; Show both brings the other back', async () => {
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    await userEvent.click(screen.getAllByRole('button', { name: 'Enlarge' })[1])
    expect(container.querySelectorAll('.lt-card:not([hidden])')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Show both' }))
    expect(container.querySelectorAll('.lt-card:not([hidden])')).toHaveLength(2)
  })

  test('the Businesses and Households panels are still there for each town', () => {
    render(<RunScreen arms={[A, B]} {...props} />)
    expect(screen.getAllByText('Businesses')).toHaveLength(2)
    expect(screen.getAllByText('Households')).toHaveLength(2)
  })
})
```

If `@testing-library/user-event` is not installed, use `fireEvent.click` from `@testing-library/react` instead (check `package.json`; do not add a dependency for this).

- [ ] **Step 2: Run them to see them fail**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/TownCard.test.jsx`
Expected: FAIL, `TownCard.jsx` not found.

- [ ] **Step 3: Port the drawing parts**

`town/parts.jsx` holds one small memoised React component per part, ported from mockup 08's `<script>` (`docs/superpowers/specs/2026-10-02-mockups/08-diorama-details.html`). Use the same coordinates and shapes; replace the mockup's `el()`/`poly()` calls with JSX `<polygon points={pts([...])} />`, and its CSS class names with `lt-` names:

| Mockup function | Component | Props | Notes |
|---|---|---|---|
| `IsoScene.drawHouse` | `House` | `{ index, tile, state, long, smoky, glowLayer? }` | Group `class="lt-house is-<state>{ is-long}{ is-smoky}"`, `data-kind="house" data-index`. Walls `lt-wl/lt-wr`, roof `lt-rf/lt-rb`, gable, chimney `lt-chim`, snow `lt-snow`, window `lt-win`, flowers `lt-flowers`, weeds `lt-weeds`, FOR SALE sign `lt-sale`, smoke `lt-smoke` (3 circles). Smoke on houses where `mulberry32(index * 7 + 3)()` < 0.4 (the mockup's rule). The glow is NOT in the house group (see `Glows`). |
| `IsoScene.drawTree` | `Tree` | `{ tree }` | `class="lt-tree{ is-blossom}"` with `lt-leaf1`, `lt-leaf2`, `lt-branches`, pine `lt-snowtip`. |
| `IsoScene.drawShop` + `drawLotTag` | `Shop` | `{ shop, lot, height }` | Group `class="lt-shop is-<state>"`, `data-kind="shop" data-id`. States, scaffolding (`fresh`), awning, windows by floor, SALE on the façade (`matrix(1 0.5 0 1 x y)` transform), boards and FOR LEASE on the façade after 8 weeks closed, crane when growing, balloons when `isNew`. Sector colours from the mockup's `SECTOR`/`CLOSED` objects; put them in `town/parts.jsx` as `SHOP_COLOURS`. |
| `drawLotTag` | `ShopSign` | `{ shop, lot, height }` | Floating pill above the roof in the top `signs` layer: HIRING (growing), CLOSED (closed, `closedFor < 8`), NEW (`isNew`); the crown `class="lt-crown"` above it for `richest`. |
| `IsoScene.drawHall` | `Hall` | `{ color, banner, changed }` | `data-kind="hall"`; banner on the façade when `banner`; flag in the town colour; the old pulse ring (`lt-hall-ring`, 4 weeks after `changedTick`). |
| treasury code in `apply` | `Treasury` | `{ cash }` | Coin stack or IOU with "owes $Xk" (use `formatMoneyShort`). |
| queue code in `apply` | `Queue` | `{ size }` | Up to 9 figures in front of the hall. |
| `IsoScene.drawBank` + loan papers | `Bank` | `{ papers }` | `data-kind="bank"`; flash overlay polygon `data-flash="bank"` with opacity 0. |
| pins in the constructor | `Pin` | `{ person, index }` | `data-kind="person" data-index`, circle `lt-pin is-<tone>` with the initial. |
| `figure()` | `figureNode(document, shirt, carry)` | — | A DOM builder (not React) used by Task 6. Export it from `parts.jsx`. |
| `carShape()` | `carNode(document, axis, colour)` | — | DOM builder for Task 6. |

Port the mockup's scene CSS (house states, seasons, snow, smoke, flicker, flags, balloons, crane hook, rain and snow keyframes, pings, moments, puffs, flash) into `town/town.css` with `lt-` names, all selectors under `.nx`. Colours that weather changes read CSS variables: sky stops `stop-color: var(--lt-sky-top)`, grass tiles `fill: var(--lt-grass-a)` / `var(--lt-grass-b)`, the shade rect `opacity: var(--lt-shade)`, the sun `opacity: var(--lt-sun)`, cloud groups `fill: var(--lt-cloud-fill)`, the rain layer `opacity: var(--lt-rain)`, glows `.lt-glow.is-on { opacity: var(--lt-glow) }`. Add the `prefers-reduced-motion` block that switches off every animation.

- [ ] **Step 4: Write `Diorama.jsx` and `weather.js`**

`Diorama` renders, in this order: `<defs>` (sky gradient, glow and sun radial gradients, ids made unique with `useId`), the sky rect, sun, `data-layer="clouds"` (six clouds as in the mockup constructor), island shadow, plinth and tiles (grass tiles get `lt-grass is-a|is-b` by `(gx + gy) % 2`), lane dashes, then `PAINT_ORDER` (houses, trees, lot groups with `Shop` at `shop.floors * 8 + 12` height when a shop holds the lot, the `Hall` followed by `Treasury` and `Queue`, the `Bank`, and empty `data-slot` groups), the shade rect, the glows layer (one circle per house at the mockup's glow position, `class="lt-glow{ is-on}"` when the house works), `data-layer="rain"` with `raindrops(id, 90, { x: -290, y: -40, w: 580, h: 330 })`, `data-layer="pings"`, `data-layer="coins"`, the signs layer (`ShopSign` per shop), `data-layer="moments"`, and the pins. When `model.overflow > 0` add a sign at the island's far corner using `COPY.diorama.moreLots(model.overflow)`.

`weather.js`:

```js
// Puts a mood and season on a scene: CSS variables the scene's styles read,
// the cloud count, and rain or snow. Task 6 calls it every frame while the
// mood eases; here it runs once per week change.
import { scenePalette } from './mood.js'

export function applyWeather(svg, mood, season) {
  if (!svg) return
  const p = scenePalette(mood, season)
  const vars = {
    '--lt-sky-top': p.skyTop, '--lt-sky-bottom': p.skyBottom, '--lt-sun': p.sun.toFixed(2), '--lt-cloud-fill': p.cloudFill,
    '--lt-rain': p.rain.toFixed(2), '--lt-shade': p.shade.toFixed(3), '--lt-grass-a': p.grassA, '--lt-grass-b': p.grassB,
    '--lt-glow': p.glow.toFixed(2), '--lt-hill-a': p.hillA, '--lt-hill-b': p.hillB, '--lt-meadow': p.meadow,
  }
  for (const [name, value] of Object.entries(vars)) svg.style.setProperty(name, value)
  svg.querySelectorAll('[data-cloud]').forEach(cloud => {
    cloud.style.opacity = Number(cloud.dataset.cloud) < p.cloudCount ? p.cloudOpacity.toFixed(2) : '0'
  })
  svg.querySelector('[data-layer="rain"]')?.classList.toggle('is-snow', p.snow)
}
```

In `Diorama`, `useLayoutEffect(() => applyWeather(svgRef.current, model.mood, model.season), [model.mood, model.season])`. Accept an optional `sceneRef` and forward the svg element to it.

- [ ] **Step 5: Write `TownCard.jsx`, `Legend.jsx`, and wire the Run screen**

`TownCard`: `const model = useMemo(() => townAt(arm, tick), [arm, tick, arm.ticks.length])`. Header: colour chip, `<h2>` label, rules text `describePolicy(rulesDiff(rulesAt(arm, tick)))` in a span with ellipsis, mood chip (small inline SVG icon per band from the mockup's `MOOD_ICON`, label `COPY.diorama.moods[band]`, fixed `min-width`), the Enlarge button when `canFocus` (label `COPY.diorama.enlarge`, or `COPY.diorama.showAll(towns)` when `focused`). Facts: out of work (`formatMetric('peopleOutOfWorkPer100', …)`), typical weekly pay, shops open with "N struggling" label, town hall money (red when owed) – each value `nowrap`, each label area two lines tall. Summary `.nx-sr` list: the old `COPY.town.altHouses`, `COPY.town.altFirms`, `COPY.diorama.summary.mood(band)`, `COPY.diorama.summary.weather(season, band)`, the overflow line when `model.overflow > 0`, and `COPY.town.hallChanged` while the pulse runs.

`Legend`: one row with the items in `COPY.diorama.legend`, the four sector colours (`sectorName`), and the households-per-house scale of the first arm.

`RunScreen.jsx`:
- Remove the `Town` import and its use in `TownColumn`; the column keeps its head, notice, `BusinessList` and `HouseholdCards` (the `.nx-solo` single-town wrapper keeps the business list beside the households).
- Add above the columns: `<section className={`lt-towns is-${arms.length}`} data-stable="towns">` with one `TownCard` per arm (`canFocus` when there are 2+ arms). Keep the focused town in `useState(null)`; when set, other cards render with the `hidden` attribute and the grid gets `is-focus`.
- After the town grid, `<Legend arms={arms} tick={tick} />`.
- CSS in `next.css` / `town.css`: `.lt-towns.is-1 { grid-template-columns: 1fr }`, `.is-2, .is-3, .is-4 { grid-template-columns: 1fr 1fr }`, `.is-focus { grid-template-columns: 1fr }`, under 1100 px one column. The canvas keeps the SVG aspect ratio (`width: 100%; height: auto`).

Delete `components/Town.jsx` and `__tests__/Town.test.jsx`, then remove the CSS rules only they used (`grep -n "nx-town\|nx-house\|nx-bldg\|nx-civic\|nx-pillar\|nx-street\|nx-lot\|nx-cross\|nx-seek\|nx-lost\|nx-keyhouse\|nx-key\b\|nx-hall-ring\|nx-townhall" src/next` to confirm nothing else uses them).

- [ ] **Step 6: Run the tests, fix, and check e2e**

Run: `npx --yes node@22 node_modules/.bin/vitest run` → all pass (rewrite assertions in other tests that looked for `.nx-house` or the old legend, keeping what they protected).
Run: `npm run test:e2e` → PASS at all four widths. Then add one more case to `e2e/no-shift.spec.js`: at 1440 px, click the second town's Enlarge button, step weeks 2…max, compare with the boxes measured right after the click, and assert no differences.
Run: `npm run lint` → clean.

- [ ] **Step 7: Look at it**

Run the dev server (`cd frontend-react && npx --yes node@22 node_modules/.bin/vite --port 5175`) and open `http://localhost:5175/?view=next&demo` at 1440 and 489 px. Compare a few weeks (11, 40, 70, 102) with mockup 08: houses dark and lit, shops and signs, the treasury, rain at week 100 in Town A, snow at week 102. Fix anything that does not match.

- [ ] **Step 8: Commit**

```bash
git add -A frontend-react
git commit -m "feat(next): living-town dioramas replace the flat town on the Run screen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Motion between weeks

**Files:**
- Create: `frontend-react/src/next/town/motion.js`, `frontend-react/src/next/town/useSceneMotion.js`
- Modify: `frontend-react/src/next/town/Diorama.jsx`, `frontend-react/src/next/town/TownCard.jsx`, `frontend-react/src/next/town/parts.jsx` (shop height easing), `frontend-react/src/next/RunScreen.jsx` (pass `playing`, `speed`)
- Test: `frontend-react/src/next/__tests__/townMotion.test.js`

**Interfaces:**
- Consumes: the Diorama's `data-layer`, `data-slot`, `data-cloud`, `data-flash` hooks (Task 5); `figureNode`, `carNode` (Task 5); `applyWeather` (Task 5); `TownModel` (Task 4); `iso`, `LAYOUT`, `HALL`, `BANK` (Task 2).
- Produces:
  - `motion.js`: `COIN_DOLLARS = 1800`; `coinsDue(debt, flows, dWeeks, speed, towns) → { debt, launches: { spend, pay, tax, help } }` (rate per flow = amount / (COIN_DOLLARS × speed × max(1, towns / 2)) per week, at most 8 per flow per call); `isStep(prevTick, tick, playing) → boolean` (true only when `playing && tick === prevTick + 1`); `weekMoments(model, limit = 4) → [{ kind: 'closed'|'opened'|'lost'|'gained'|'bad', firmId?, n?, amount? }]` (order: closures, openings, layoffs ≥ 2 by size, hires ≥ 2 by size, bad loans; at most `limit`); `weekWalkers(model, limit = 6) → [{ firmId, kind: 'lay'|'hire' }]` (up to 2 per firm); `easeToward(current, target, dt, rate = 1.6) → number`; `arcPath(a, b, h) → t => [x, y]`.
  - `useSceneMotion(svgRef, { model, playing, speed, towns, mode = 'island' })`: runs the loop described in spec section 7. It remembers the last tick it saw (in a ref, inside its week effect) to decide whether a week change is a single forward step. Returns nothing.
  - `TownCard` passes `playing`, `speed` and `towns` to `Diorama`, which calls the hook.

- [ ] **Step 1: Write the failing tests**

`frontend-react/src/next/__tests__/townMotion.test.js`:

```js
import { beforeAll, describe, expect, test } from 'vitest'
import { COIN_DOLLARS, coinsDue, easeToward, isStep, weekMoments, weekWalkers } from '../town/motion.js'
import { townAt } from '../town/model.js'
import { demoArms } from './fixture.js'

let A
beforeAll(() => { [A] = demoArms() })

describe('motion helpers', () => {
  test('coins follow the money and calm down with speed and more towns', () => {
    const flows = { spend: COIN_DOLLARS * 10, pay: 0, tax: 0, help: 0 }
    const one = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 1, 2)
    expect(one.launches.spend).toBe(5)
    const fast = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 4, 2)
    expect(fast.launches.spend).toBe(1)
    const four = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 1, 4)
    expect(four.launches.spend).toBe(2)
    expect(four.debt.spend).toBeCloseTo(0.5)
  })

  test('caps launches per call', () => {
    const flows = { spend: COIN_DOLLARS * 1000, pay: 0, tax: 0, help: 0 }
    expect(coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 1, 1, 1).launches.spend).toBe(8)
  })

  test('only a single forward step while playing counts as a step', () => {
    expect(isStep(40, 41, true)).toBe(true)
    expect(isStep(40, 41, false)).toBe(false)
    expect(isStep(40, 45, true)).toBe(false)
    expect(isStep(41, 40, true)).toBe(false)
    expect(isStep(null, 1, true)).toBe(false)
  })

  test('a closing week pops the closure and the bad loans, within the limit', () => {
    const list = weekMoments(townAt(A, 70))
    expect(list.map(item => item.kind)).toEqual(['closed', 'bad'])
    expect(weekMoments(townAt(A, 70), 1)).toHaveLength(1)
  })

  test('layoff walkers: at most two per firm and six a week', () => {
    const model = { week: { hires: [[1, 5]], layoffs: [[2, 3], [3, 1], [4, 9]], opened: [], closed: [], bad: 0 } }
    const walkers = weekWalkers(model)
    expect(walkers.filter(w => w.firmId === 4)).toHaveLength(2)
    expect(walkers.length).toBeLessThanOrEqual(6)
    expect(walkers[0]).toEqual({ firmId: 4, kind: 'lay' })
  })

  test('easing moves part of the way and settles', () => {
    const next = easeToward(0, 1, 0.1)
    expect(next).toBeGreaterThan(0)
    expect(next).toBeLessThan(1)
    expect(easeToward(0.999, 1, 0.1)).toBe(1)
  })
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townMotion.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Write `town/motion.js`**

```js
// Pure helpers for the scene's animation loop.
export const COIN_DOLLARS = 1800
const FLOWS = ['spend', 'pay', 'tax', 'help']

export function coinsDue(debt, flows, dWeeks, speed, towns) {
  const next = { ...debt }
  const launches = {}
  const calm = COIN_DOLLARS * Math.max(speed, 0.25) * Math.max(1, towns / 2)
  for (const flow of FLOWS) {
    next[flow] = (next[flow] ?? 0) + ((flows?.[flow] ?? 0) / calm) * dWeeks
    let n = 0
    while (next[flow] >= 1 && n < 8) { next[flow] -= 1; n += 1 }
    if (n === 8) next[flow] = Math.min(next[flow], 1)
    launches[flow] = n
  }
  return { debt: next, launches }
}

export const isStep = (prevTick, tick, playing) => Boolean(playing) && prevTick != null && tick === prevTick + 1

export function weekMoments(model, limit = 4) {
  const week = model?.week
  if (!week) return []
  const list = [
    ...week.closed.map(firmId => ({ kind: 'closed', firmId })),
    ...week.opened.map(firmId => ({ kind: 'opened', firmId })),
    ...[...week.layoffs].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([firmId, n]) => ({ kind: 'lost', firmId, n })),
    ...[...week.hires].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([firmId, n]) => ({ kind: 'gained', firmId, n })),
    ...(week.bad >= 500 ? [{ kind: 'bad', amount: week.bad }] : []),
  ]
  return list.slice(0, limit)
}

export function weekWalkers(model, limit = 6) {
  const week = model?.week
  if (!week) return []
  const out = []
  const add = (pairs, kind) => {
    for (const [firmId, n] of [...pairs].sort((a, b) => b[1] - a[1])) {
      for (let k = 0; k < Math.min(n, 2) && out.length < limit; k += 1) out.push({ firmId, kind })
    }
  }
  add(week.layoffs, 'lay')
  add(week.hires, 'hire')
  return out
}

export function easeToward(current, target, dt, rate = 1.6) {
  const next = current + (target - current) * Math.min(1, dt * rate)
  return Math.abs(target - next) < 0.004 ? target : next
}

export const arcPath = (a, b, h) => t => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - h * 4 * t * (1 - t)]
```

- [ ] **Step 4: Run the tests**

Run: `npx --yes node@22 node_modules/.bin/vitest run src/next/__tests__/townMotion.test.js`
Expected: PASS.

- [ ] **Step 5: Write `useSceneMotion.js`**

Port the mockup's `IsoScene.frame`, `Scene.flow`/`launchFlow`/`ping`, `Particles`, `newWalker`/`newCar`/`place`, `onWeek`/`walkTo`/`moment`/`puff`, and `paintMood` into one hook. Structure:

```js
import { useEffect, useLayoutEffect, useRef } from 'react'
// … imports from motion.js, weather.js, geometry.js, parts.jsx

export default function useSceneMotion(svgRef, { model, playing, speed, towns, mode = 'island' }) {
  // The loop reads the latest props from a ref, updated after each render (never during it).
  const live = useRef(null)
  useLayoutEffect(() => { live.current = { model, playing, speed, towns, mode } })
  const state = useRef(null) // { mood, debt, coins: [], cars: [], walkers: [], movers: [], last }
  const lastTick = useRef(null)

  // Set up once per scene: find the layers and slots, start the loop.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    // layers = { coins, pings, moments, rain, clouds: [...] }, slots = Map('gx,gy' → g)
    // state.current = { … }
    let frame = 0
    const tick = now => {
      // 1. ease the mood toward live.current.model.mood; applyWeather when it moved
      // 2. if playing and not reduce: drift clouds, advance cars and walkers (place in slots), launch coins from coinsDue, step coins
      // 3. step movers (hire/layoff walkers); remove finished ones
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [svgRef])

  // Each new week: traffic counts follow the model; a single forward step while
  // playing adds this week's moments and walkers; any other change clears what is moving.
  useEffect(() => {
    const stepped = isStep(lastTick.current, model.tick, playing)
    lastTick.current = model.tick
    // if stepped: weekMoments → floating signs (+ puff for closures, bank flash for bad loans); weekWalkers → movers
    // else: clear coins, movers and floating signs
  }, [model, playing])
}
```

Rules the port must keep:
- No React state updates inside the loop; everything goes through refs, attributes and CSS variables.
- Moving things live in the tile slot under them (`place()`), so buildings in front hide them.
- Coin anchors: house `iso(gx + 0.5, gy + 0.5, 12)`, shop `iso(lot.gx + 0.5, lot.gy + 0.5, floors * 8 + 15)`, hall `iso(8.88, 8.88, 34)`; spending picks a shop weighted by staff; help goes to a dark house; coins pop a ping where they land (at most 16 pings alive).
- Car count and walker count come from `model.traffic`; cars use `carNode`, walkers `figureNode`; at most 160 coins alive.
- With `prefers-reduced-motion: reduce`: weather is applied at once, nothing travels, no floating signs (the cards and summary still say what happened).
- When the tab is hidden the browser pauses `requestAnimationFrame`; clamp `dt` to 0.1 s so nothing jumps on return.

Shop height easing: in `parts.jsx`, `Shop` keeps a displayed height in a ref and eases it toward `floors * 8 + 12` over about 0.4 s with its own `requestAnimationFrame`, writing the polygon `points` directly (no React state per frame). With reduced motion it jumps.

- [ ] **Step 6: Wire it and check**

`Diorama` calls `useSceneMotion(svgRef, { model, playing, speed, towns })`. `RunScreen` passes `playing` and `speed` to each `TownCard`, which passes them on.

Add to `TownCard.test.jsx`:

```jsx
test('scrubbing to another week adds no floating signs', () => {
  const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing={false} speed={1} />)
  rerender(<TownCard arm={A} tick={70} towns={2} playing={false} speed={1} />)
  expect(container.querySelectorAll('[data-layer="moments"] > *')).toHaveLength(0)
})

test('a single forward step while playing pops the week's moments', () => {
  const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing speed={1} />)
  rerender(<TownCard arm={A} tick={70} towns={2} playing speed={1} />)
  expect(container.querySelector('[data-layer="moments"]').textContent).toContain('Closed')
})
```

(If jsdom's `matchMedia` is missing, the hook must treat it as "no preference".)

Run: full Vitest, `npm run lint`, `npm run test:e2e` → all pass. Open the demo in the browser at 1×, 4× and with two and four towns (the four-town case: `?view=next` Set up screen with 4 towns of 200 households is a live run; if no backend is running, check four towns by temporarily rendering `RunScreen` with four demo arms in a scratch test, not in committed code). Watch for a steady frame rate (Chrome performance panel: the loop under 4 ms per frame).

- [ ] **Step 7: Commit**

```bash
git add -A frontend-react
git commit -m "feat(next): living towns move between weeks: weather, money, traffic, hires and layoffs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Place cards

**Files:**
- Create: `frontend-react/src/next/town/PlaceCard.jsx`
- Modify: `frontend-react/src/next/town/TownCard.jsx`, `frontend-react/src/next/town/town.css`
- Test: `frontend-react/src/next/__tests__/PlaceCard.test.jsx`

**Interfaces:**
- Consumes: `placeCard(model, target, total)` (Task 4); the `data-kind`/`data-index`/`data-id` attributes (Task 5).
- Produces: `usePlaceCard(model, total) → { overlay: ReactNode, handlers: { onMouseMove, onMouseLeave, onClick } }` and `PlaceCard({ card, x, y, pinned })`. `TownCard` spreads `handlers` on `.lt-canvas` and renders `overlay` inside it. Task 8 reuses both for Main Street.

- [ ] **Step 1: Write the failing tests**

`frontend-react/src/next/__tests__/PlaceCard.test.jsx`:

```jsx
import { beforeAll, describe, expect, test } from 'vitest'
import { fireEvent, render } from '@testing-library/react'
import TownCard from '../town/TownCard.jsx'
import { demoArms } from './fixture.js'

let A
beforeAll(() => { [A] = demoArms() })

describe('place cards', () => {
  test('pointing at a shop shows its card; leaving hides it', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const shop = container.querySelector('[data-kind="shop"]')
    fireEvent.mouseMove(shop, { clientX: 10, clientY: 10 })
    const card = container.querySelector('.lt-place')
    expect(card).toHaveClass('is-on')
    expect(card).toHaveTextContent('Staff')
    fireEvent.mouseLeave(container.querySelector('.lt-canvas'))
    expect(container.querySelector('.lt-place')).not.toHaveClass('is-on')
  })

  test('clicking keeps the card; clicking the ground closes it', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="hall"]'), { clientX: 20, clientY: 20 })
    fireEvent.mouseLeave(container.querySelector('.lt-canvas'))
    expect(container.querySelector('.lt-place')).toHaveClass('is-on')
    expect(container.querySelector('.lt-place')).toHaveTextContent('Town hall')
    fireEvent.click(container.querySelector('svg.lt-scene'))
    expect(container.querySelector('.lt-place')).not.toHaveClass('is-on')
  })

  test('a kept card follows the week', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="bank"]'), { clientX: 5, clientY: 5 })
    rerender(<TownCard arm={A} tick={70} towns={2} />)
    expect(container.querySelector('.lt-place')).toHaveTextContent('Loans going bad')
  })
})
```

- [ ] **Step 2: Run to see it fail**, then **Step 3: implement** `PlaceCard.jsx`: the hook keeps `{ target, pinned, x, y }` in state; `onMouseMove` reads `event.target.closest('[data-kind]')`, builds `target` from its `data-*` attributes, and positions the card 14 px from the pointer, flipping left or up near the canvas edges (use the canvas `getBoundingClientRect`); `onClick` on a place pins it, on empty ground unpins; the card is `placeCard(model, target, total)` recomputed every render, so it follows the week. The card is an absolutely positioned `div.lt-place` with `pointer-events: none` (except when pinned), styled like the mockup's `.pop` but with `--nx-*` tokens; tag tones map to `--nx-work`, `--nx-look`, `--nx-home`, `--nx-ink3` and the town teal. The overlay is decoration for pointer users (`aria-hidden`); keyboard and screen-reader users have the summary and panels.

- [ ] **Step 4: Run tests, lint, e2e; Step 5: commit**

```bash
git add -A frontend-react
git commit -m "feat(next): point at anything in a living town for its card

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Main Street, up close

**Files:**
- Create: `frontend-react/src/next/town/MainStreet.jsx`, `frontend-react/src/next/town/MainStreetCard.jsx`
- Modify: `frontend-react/src/next/town/useSceneMotion.js` (accept a `street` mode), `frontend-react/src/next/town/parts.jsx` (street parts), `frontend-react/src/next/RunScreen.jsx`, `frontend-react/src/next/town/town.css`
- Test: `frontend-react/src/next/__tests__/MainStreet.test.jsx`

**Interfaces:**
- Consumes: `STREET`, `STREET_CAPACITY` (Task 2); `townAt` (Task 4); `applyWeather` (Task 5); `usePlaceCard` (Task 7); `useSceneMotion` (Task 6).
- Produces: `MainStreetCard({ arms, tick, playing, speed, selected, onSelect })` rendering `<article class="nx-card lt-street" data-stable="main-street">` with the heading `COPY.diorama.mainStreet`, the town and its rules, a segmented town picker (`role="group"`, one `aria-pressed` button per town) when there are 2+ towns, and `MainStreet({ model, color, rules, playing, speed })` – the side view ported from mockup 08's `StreetScene`. Shops on `STREET.lots` are the model's shops whose `lot < STREET_CAPACITY`, at `STREET.lots[shop.lot]`.

- [ ] **Step 1: Write the failing tests**

`frontend-react/src/next/__tests__/MainStreet.test.jsx`:

```jsx
import { beforeAll, describe, expect, test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import MainStreetCard from '../town/MainStreetCard.jsx'
import RunScreen from '../RunScreen.jsx'
import { demoArms } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

describe('Main Street', () => {
  test('shows the shops nearest the crossing with their signs written out', () => {
    const { container } = render(<MainStreetCard arms={[A, B]} tick={70} selected={0} onSelect={() => {}} />)
    expect(container.querySelectorAll('[data-kind="shop"]').length).toBeGreaterThan(10)
    expect(container.textContent).toMatch(/CLOSED|FOR LEASE/)
    expect(container.textContent).toContain('TOWN HALL')
    expect(container.querySelectorAll('[data-kind="house"]')).toHaveLength(100)
  })

  test('the picker switches towns', () => {
    const picks = []
    render(<MainStreetCard arms={[A, B]} tick={70} selected={0} onSelect={n => picks.push(n)} />)
    fireEvent.click(screen.getByRole('button', { name: 'Town B' }))
    expect(picks).toEqual([1])
  })

  test('one town: no picker', () => {
    render(<MainStreetCard arms={[A]} tick={70} selected={0} onSelect={() => {}} />)
    expect(screen.queryByRole('group')).toBeNull()
  })

  test('Enlarge on a town moves Main Street to it', () => {
    const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Enlarge' })[1])
    expect(container.querySelector('.lt-street')).toHaveTextContent('Town B')
  })
})
```

- [ ] **Step 2: Run to see it fail**, then **Step 3: implement.** Port `StreetScene` (constructor, `drawHouse`, `drawHall`, `drawBank`, `drawShop`, `apply`, `frame`) from mockup 08 as React parts plus the shared motion hook in a `street` mode (coins arc between the hill houses and the shop doors; walkers stroll the pavement, one per 15 staff, 2–24; weather sets the sky stops, sun, hills, meadow, shade and rain or snow through `applyWeather`). Shop names show in the place card; signs (HIRING, SALE, CLOSED, FOR LEASE, NEW), the crown, the hall banner, treasury and queue are drawn as in the mockup. `RunScreen` keeps `streetTown` state (default 0), renders `MainStreetCard` after the legend, and sets `streetTown` when a town is focused.

- [ ] **Step 4: Run tests, lint, e2e** (Main Street must not shift either: it has a fixed aspect ratio and a fixed header), **look at it** in the browser, **Step 5: commit**

```bash
git add -A frontend-react
git commit -m "feat(next): Main Street close-up of one town, with a town picker

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Changelog, docs, final checks

**Files:**
- Modify: `CHANGELOG.md`, `frontend-react/README.md`

- [ ] **Step 1: CHANGELOG** – add an entry at the top in the file's existing style, with **Before** and **After** for each change: (1) the Run screen's town drawing (before: a flat grid of 100 small house icons and up to 16 shop rectangles per town, nothing moved between weeks; after: the living-town diorama with weather, seasons, shop and home states, traffic, money, moments, cards, Enlarge, and Main Street), (2) layout shift (before: the page jumped as text changed length, up to 40 px 27 times per demo at 489 px and 23 px 9 times at 1440 px; after: reserved heights, fixed rows and the Playwright no-shift test), (3) data kept from frames (before: tracked subjects dropped health and happiness; after: kept), (4) tooling (`npm run test:e2e`, Playwright, Chromium).

- [ ] **Step 2: README** – in `frontend-react/README.md`, add how to run `npm run test:e2e` (first run: `npx playwright install chromium`; it starts its own Vite server on port 4179 and needs no backend) and one paragraph on `src/next/town/`.

- [ ] **Step 3: Final checks** – `npm run lint`, full Vitest, `npx --yes node@22 node_modules/.bin/vite build`, `npm run test:e2e`. All pass.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md frontend-react/README.md
git commit -m "docs: living town changelog and the no-shift test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
