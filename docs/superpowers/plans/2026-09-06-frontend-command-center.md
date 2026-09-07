# Frontend Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the EcoSim React dashboard's presentation layer as the command center approved in the spec, screen by screen, without touching the WebSocket protocol or session state.

**Architecture:** `App.jsx` keeps state, handlers, and the protocol client and becomes a thin shell that renders one screen component per view. A token stylesheet plus a small set of UI primitives and chart components (`src/ui`, `src/charts`) replace the inline `techStyles`, the Tailwind class soup, and the gauges. Every screen is a function component fed by `metrics`, `tick`, `firmStats`, `logs`, selection state and handlers, and is tested by rendering the real fixture frame.

**Tech Stack:** React 19, Vite 8, Tailwind 3.4, Recharts 3 (kept for line and bar charts), lucide-react, Vitest 4 + Testing Library + jsdom. Run all node commands with Node 22: `npx --yes node@22 ./node_modules/.bin/vitest run` from `frontend-react/` (the machine's default node is 20).

**Spec:** `docs/superpowers/specs/2026-09-06-frontend-command-center-design.md`. **Visual reference:** `docs/superpowers/specs/2026-09-06-prototype.html` (open it in a browser; its `V.<screen>` functions hold the exact markup of every screen, and its `drawChart`, `drawRadar`, `drawSpark`, `ledgerHTML`, `changeCard`, `leverTile` functions hold the working geometry). **Fixture:** `frontend-react/src/test/fixtures/frame.json`, a real tick 60 frame (12 tracked subjects, 7 tracked firms, `firm_stats`, 3-sample histories, `priceHistory`/`supplyHistory` keyed by sector).

## Global Constraints

- Tokens: exactly the two theme sets from spec section 3, on `:root[data-theme="ember"]` and `:root[data-theme="paper"]`; default `ember`.
- Fonts: Barlow, Barlow Semi Condensed (numerals), JetBrains Mono. No Inter anywhere.
- Radii: panels and tiles 6px, buttons and inputs 5px, pills 999px. No glow, no box-shadow glows, no colored side rails, no cards inside cards, no gauges or donuts, no dashed gridlines.
- Fill rule: charts take their panel's remaining height; grids holding charts grow to the panel; tables fill and scroll inside their panel.
- Text sizes: nothing below 10.5px. Hero 48 to 52px, tile value 28px, body 13px, label 11px.
- Status colours always come with an icon or a label.
- Protocol and lifecycle in `App.jsx` unchanged; `src/App.test.jsx` must pass unmodified at every commit.
- No Codex. Subagents run Sonnet.
- Commit after every task with the `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` trailer.

---

## File structure

```
frontend-react/src/
  theme/tokens.css                 tokens, fonts, base + shell CSS (replaces techStyles)
  format.js                        existing formatters + compactMoney, signedMoney, pct1, dec1, dec3, ms, score
  telemetry.js                     history helpers: series(), latest(), backN(), deltaVs(), derived stress/employment
  ui/Pill.jsx, ui/Chip.jsx, ui/Delta.jsx, ui/KeyValue.jsx, ui/Panel.jsx, ui/SectionTitle.jsx
  ui/PageHeader.jsx, ui/EmptyState.jsx (moved out of primitives.jsx)
  ui/Inputs.jsx                    Slider, Select, Toggle, NumberInput, Search
  ui/StatTile.jsx, ui/ChartTile.jsx, ui/HeroMetric.jsx, ui/useCountUp.js
  charts/useMeasured.js            width/height measurement hook (from MeasuredChart)
  charts/TimeSeries.jsx            the one line chart
  charts/Sparkline.jsx, charts/Meter.jsx, charts/CompositionBar.jsx, charts/Radar.jsx, charts/ProfileBars.jsx, charts/Ledger.jsx
  shell/Rail.jsx, shell/TopBar.jsx, shell/StatusStrip.jsx, shell/Logo.jsx
  screens/Config.jsx, Command.jsx, Population.jsx, Markets.jsx, Finance.jsx, Government.jsx, Logs.jsx
  screens/government/Timeline.jsx, EffectsPanel.jsx, LeverTile.jsx
  test/renderScreen.jsx            test helper: fixture + default props
  App.jsx                          shrinks to state + protocol + shell
```

`ui/primitives.jsx` is deleted at the end of Task 8 once nothing imports it. `GovernmentConsole.jsx` becomes `screens/Government.jsx` in Task 13 with its test moved alongside.

---

### Task 1: Tokens, fonts, theme attribute

**Files:**
- Create: `frontend-react/src/theme/tokens.css`
- Modify: `frontend-react/src/index.css` (import tokens after Tailwind directives)
- Modify: `frontend-react/index.html` (Google Fonts link, remove theme-color meta value `#08111f` → `#08090B`)
- Modify: `frontend-react/tailwind.config.js` (colour aliases to tokens)
- Test: `frontend-react/src/theme/tokens.test.js`

**Interfaces:**
- Produces: CSS custom properties `--page --panel --panel2 --panel3 --line --line2 --ink --ink2 --ink3 --ink4 --acc --acc-ink --acc-soft --good --warn --crit --ai --s1 --s2 --s3 --s4 --grid --font --font-num --mono`; Tailwind colours `page panel panel2 panel3 ink ink2 ink3 ink4 acc good warn crit ai s1 s2 s3 s4` and border colours `line line2`; class names `.panel .tile .pill .chip .delta .lbl .mono .kpi` defined once here.

- [ ] **Step 1: Write the failing test**

```js
// frontend-react/src/theme/tokens.test.js
import { readFileSync } from 'node:fs'
import { describe, expect, test } from 'vitest'

const css = readFileSync(new URL('./tokens.css', import.meta.url), 'utf8')

describe('tokens.css', () => {
  test('defines both themes with the approved accents', () => {
    expect(css).toMatch(/\[data-theme="ember"\][^}]*--acc:\s*#FF6B1A/i)
    expect(css).toMatch(/\[data-theme="paper"\][^}]*--acc:\s*#D2491E/i)
  })
  test('uses Barlow and never Inter', () => {
    expect(css).toMatch(/--font:\s*'Barlow'/)
    expect(css).not.toMatch(/Inter/)
  })
  test('has no glow, dashed grid, or large radius', () => {
    expect(css).not.toMatch(/drop-shadow|0 0 \d+px/)
    expect(css).not.toMatch(/stroke-dasharray/)
    expect(css).not.toMatch(/border-radius:\s*(1[2-9]|[2-9]\d)px/)
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend-react && npx --yes node@22 ./node_modules/.bin/vitest run src/theme`
Expected: FAIL (file not found).

- [ ] **Step 3: Write tokens.css**

Copy the two `[data-theme=…]` blocks from the prototype (`<style>` head, `[data-theme=ember]` and `[data-theme=paper]`) verbatim into `tokens.css`, then add the base and shared class rules. Minimum content:

```css
/* frontend-react/src/theme/tokens.css */
:root[data-theme="ember"]{--page:#08090B;--panel:#111316;--panel2:#171A1F;--panel3:#1F232A;--line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.15);
  --ink:#F5F6F7;--ink2:#C2C7CF;--ink3:#8A919C;--ink4:#5B626C;--acc:#FF6B1A;--acc-ink:#1A0A00;--acc-soft:rgba(255,107,26,.14);
  --good:#34D399;--warn:#FFB020;--crit:#E0245E;--ai:#C084FC;--s1:#3987e5;--s2:#199e70;--s3:#9085e9;--s4:#d55181;--grid:#20242B;
  --font:'Barlow';--font-num:'Barlow Semi Condensed';--mono:'JetBrains Mono'}
:root[data-theme="paper"]{--page:#EDE9E0;--panel:#FBF9F4;--panel2:#F4F0E8;--panel3:#E7E2D7;--line:rgba(20,18,14,.09);--line2:rgba(20,18,14,.18);
  --ink:#14120F;--ink2:#3E3A33;--ink3:#77716A;--ink4:#A39D92;--acc:#D2491E;--acc-ink:#FFFFFF;--acc-soft:rgba(210,73,30,.12);
  --good:#1D8F4E;--warn:#A16207;--crit:#9F1239;--ai:#7C3AED;--s1:#2a78d6;--s2:#1baf7a;--s3:#4a3aa7;--s4:#e87ba4;--grid:#DDD7CB;
  --font:'Barlow';--font-num:'Barlow Semi Condensed';--mono:'JetBrains Mono'}
html,body,#root{height:100%;margin:0;background:var(--page)}
body{color:var(--ink2);font-family:var(--font),system-ui,sans-serif;font-size:13px;line-height:1.45;-webkit-font-smoothing:antialiased}
.mono{font-family:var(--mono),ui-monospace,monospace;font-variant-numeric:tabular-nums}
.num{font-family:var(--font-num),var(--font),sans-serif;font-weight:600}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;min-width:0;display:flex;flex-direction:column}
.panel.hot{border-color:color-mix(in srgb,var(--acc) 45%,transparent)}
.panel > :is(.g4,.g2,.effgrid):has(.chart){flex:1;min-height:0}
.panel > :is(.g4,.g2,.effgrid):has(.chart) > div{display:flex;flex-direction:column;min-height:0}
.panel > :is(.g4,.g2,.effgrid):has(.chart) > div > .chart{flex:1}
.chart{position:relative;width:100%;flex:1;min-height:0}
.tablefill{flex:1;min-height:0;overflow:auto}
.g12{display:grid;grid-template-columns:repeat(12,1fr);gap:10px}.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.s3{grid-column:span 3}.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}.s9{grid-column:span 9}.s12{grid-column:span 12}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
```

Then append, verbatim from the prototype `<style>` blocks, the rules for: `.tile`, `.delta`, `.hero`, `.kpi`, `.pill`, `.chips/.chip`, `.lbl`, `.muted`, `.ttl`, `.axis`, `.endlab`, `.endsub`, `.mk`, `.draw/.fill` keyframes, `.legend`, `.meter`, `.stack`, `.radar`, `.pb`, `.ledger`, `.sig/.sdot`, `.row`, `table/th/td`, `.roster/.r`, `.field/input[type=range]/.select/.toggle/.check`, `.ticker`, `.tl-item`, `.ba`, `.facts/.fact`, `.lv/.lv2`, `.tlc/.tlwrap`, `.effgrid/.effh/.effpane`, `.lgroup/.lgrid`, `.ic`, `.audit`, `.quote`, `.outcomes`, `.ctile`, `.rail/.nav/.online`, `.topbar/.tickbox/.btn/.strip/.view/.ph/.eyebrow`. Skip the `.tray` rules (prototype-only). Rename `.glow` away entirely.

- [ ] **Step 4: Wire the stylesheet, fonts, and Tailwind aliases**

`index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
@import './theme/tokens.css';
```
`index.html` head: add
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Semi+Condensed:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```
and set `<html lang="en" data-theme="ember">`, `theme-color` `#08090B`.
`tailwind.config.js`:
```js
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: {
    colors: { page:'var(--page)', panel:'var(--panel)', panel2:'var(--panel2)', panel3:'var(--panel3)', ink:'var(--ink)', ink2:'var(--ink2)', ink3:'var(--ink3)', ink4:'var(--ink4)', acc:'var(--acc)', good:'var(--good)', warn:'var(--warn)', crit:'var(--crit)', ai:'var(--ai)', s1:'var(--s1)', s2:'var(--s2)', s3:'var(--s3)', s4:'var(--s4)' },
    borderColor: { line:'var(--line)', line2:'var(--line2)' },
    fontFamily: { sans:['Barlow','system-ui','sans-serif'], num:['"Barlow Semi Condensed"','Barlow','sans-serif'], mono:['"JetBrains Mono"','ui-monospace','monospace'] },
  } },
  plugins: [],
}
```

- [ ] **Step 5: Run the test and the whole suite**

Run: `npx --yes node@22 ./node_modules/.bin/vitest run`
Expected: tokens tests PASS; existing 25 tests still PASS (the old `techStyles` is still in App.jsx for now; both stylesheets coexist until Task 8).

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/theme frontend-react/src/index.css frontend-react/index.html frontend-react/tailwind.config.js
git commit -m "feat(frontend): design tokens, fonts, and theme attribute"
```

---

### Task 2: Formatters and telemetry helpers

**Files:**
- Modify: `frontend-react/src/format.js`
- Create: `frontend-react/src/telemetry.js`
- Test: `frontend-react/src/format.test.js`, `frontend-react/src/telemetry.test.js`

**Interfaces:**
- Produces (format.js): `compactMoney(v)` → `$55.1K` / `-$1.55M` / `$914`; `signedMoney(v)` → `+$28.6K` / `-$3.3K`; `pct1(v)` → `28.8%`; `dec1(v)`, `dec3(v)`; `ms(v)` → `25 ms`; `score(v)` → `52`; `FORMATTERS` map keyed by name `{ money, moneyS, usd2, pct1, int, dec1, dec3, ms, score }`.
- Produces (telemetry.js): `series(history)` → `[{tick,value}]` (empty array for missing); `latest(history, fallback=0)`; `backN(history, n)` → value n samples back or the first; `deltaVs(current, history, n=1)` → `{ diff, pct }`; `stress(metrics)` → composite 0..100 (45% unemployment, 40% inverse happiness, 15% `firmDistressPressure`); `employment(metrics)` → `100 - unemployment`; `appendCurrent(history, tick, value)` → history plus a current point if the last sample is older than `tick` (used to keep charts live between 25-tick samples).

- [ ] **Step 1: Write the failing tests**

```js
// frontend-react/src/format.test.js
import { describe, expect, test } from 'vitest'
import { compactMoney, signedMoney, pct1, dec3, ms, score, FORMATTERS } from './format.js'

describe('format', () => {
  test('compactMoney', () => {
    expect(compactMoney(55123)).toBe('$55.1K'); expect(compactMoney(-1547526)).toBe('-$1.55M'); expect(compactMoney(914)).toBe('$914')
  })
  test('signedMoney keeps the sign', () => { expect(signedMoney(28600)).toBe('+$28.6K'); expect(signedMoney(-3300)).toBe('-$3.3K') })
  test('small formatters', () => { expect(pct1(28.83)).toBe('28.8%'); expect(dec3(0.5847)).toBe('0.585'); expect(ms(25.4)).toBe('25 ms'); expect(score(51.7)).toBe('52') })
  test('FORMATTERS map exposes every name', () => { expect(Object.keys(FORMATTERS).sort()).toEqual(['dec1','dec3','int','money','moneyS','ms','pct1','score','usd2']) })
})
```
```js
// frontend-react/src/telemetry.test.js
import { describe, expect, test } from 'vitest'
import frame from './test/fixtures/frame.json'
import { series, latest, backN, deltaVs, stress, employment, appendCurrent } from './telemetry.js'

describe('telemetry', () => {
  const m = frame.metrics
  test('series and latest read histories defensively', () => {
    expect(series(m.gdpHistory).length).toBe(3); expect(series(undefined)).toEqual([]); expect(latest(m.gdpHistory)).toBe(m.gdpHistory[2].value); expect(latest(undefined, 7)).toBe(7)
  })
  test('backN and deltaVs', () => {
    expect(backN(m.gdpHistory, 1)).toBe(m.gdpHistory[1].value)
    const d = deltaVs(10, [{ tick: 1, value: 8 }, { tick: 2, value: 9 }], 1)
    expect(d.diff).toBe(2); expect(d.pct).toBe(25)
  })
  test('derived metrics are bounded', () => {
    expect(stress({ unemployment: 200, happiness: 0, firmDistressPressure: 100 })).toBe(100)
    expect(employment({ unemployment: 28.8 })).toBeCloseTo(71.2)
  })
  test('appendCurrent adds a live point only when newer', () => {
    const h = [{ tick: 25, value: 1 }]
    expect(appendCurrent(h, 30, 2)).toEqual([{ tick: 25, value: 1 }, { tick: 30, value: 2 }])
    expect(appendCurrent(h, 25, 2)).toEqual(h)
  })
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx --yes node@22 ./node_modules/.bin/vitest run src/format.test.js src/telemetry.test.js`
Expected: FAIL (missing exports / module).

- [ ] **Step 3: Implement**

Append to `format.js`:
```js
export const compactMoney = (v) => formatCompactCurrency(v);
export const signedMoney = (v) => `${Number(v) >= 0 ? '+' : ''}${formatCompactCurrency(v)}`;
export const pct1 = (v) => formatPercent(v, 1);
export const dec1 = (v) => formatDecimal(v, 1);
export const dec3 = (v) => formatDecimal(v, 3);
export const ms = (v) => `${Math.round(Number(v) || 0)} ms`;
export const score = (v) => `${Math.round(Number(v) || 0)}`;
export const usd2 = (v) => formatCurrency(v, 2);
export const FORMATTERS = { money: compactMoney, moneyS: signedMoney, usd2, pct1, int: formatInteger, dec1, dec3, ms, score };
```
(`formatCompactCurrency` already rounds to `$55.1K` / `$1.55M`; `signedMoney` must not double a leading minus, so check `formatCompactCurrency(-3300)` returns `-$3.3K` and prepend `+` only for non-negative.)

`telemetry.js`:
```js
export const series = (h) => (Array.isArray(h) ? h : []);
export const latest = (h, fallback = 0) => { const s = series(h); return s.length ? Number(s[s.length - 1].value) : fallback; };
export const backN = (h, n) => { const s = series(h); return s.length ? Number(s[Math.max(0, s.length - 1 - n)].value) : 0; };
export const deltaVs = (current, h, n = 1) => { const base = backN(h, n); const diff = Number(current) - base; return { diff, pct: base ? (diff / Math.abs(base)) * 100 : 0 }; };
export const stress = (m) => Math.min(100, Math.max(0, (m.unemployment || 0) * 0.45 + (100 - (m.happiness || 0)) * 0.4 + (m.firmDistressPressure || 0) * 0.15));
export const employment = (m) => 100 - (m.unemployment || 0);
export const appendCurrent = (h, tick, value) => { const s = series(h); if (!s.length || Number(s[s.length - 1].tick) < Number(tick)) return [...s, { tick, value }]; return s; };
```

- [ ] **Step 4: Run tests**  Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(frontend): formatters and telemetry helpers"` (add the new files first).

---

### Task 3: Small UI primitives and inputs

**Files:**
- Create: `src/ui/Pill.jsx`, `src/ui/Chip.jsx`, `src/ui/Delta.jsx`, `src/ui/KeyValue.jsx`, `src/ui/Panel.jsx`, `src/ui/SectionTitle.jsx`, `src/ui/PageHeader.jsx`, `src/ui/EmptyState.jsx`, `src/ui/Inputs.jsx`
- Test: `src/ui/primitives.test.jsx`

**Interfaces (all default-exported function components, class names from tokens.css):**
- `Pill({ tone: 'good'|'warn'|'crit'|'ai'|'acc'|'muted', children })` → `<span class="pill {tone}"><i/>{children}</span>`
- `Chip({ on, onClick, children })` → `<button class="chip on?">`
- `Delta({ diff, pct, unit: 'pct'|'pts'|'int', upBad=false, vsTick })` → `<span class="delta up|down">▲ 3.2%</span>` (`title="vs tick N"` when given); zero renders `— 0.0%`.
- `KeyValue({ label, value, tone })` → `.row` with `.k` and `.n`
- `Panel({ hot, className, style, children })` → `.panel`
- `SectionTitle({ title, meta, right })` → `.ttl` with `<h4>` and `<small>` or a right slot
- `PageHeader({ eyebrow, title, summary, action })` → `.ph` (port the existing one; class names change to `.eyebrow`, `h3`, `.sum`)
- `EmptyState` → moved unchanged from `primitives.jsx`
- `Inputs.jsx` exports `Slider({ label, value, min, max, step, format, onChange, description })` with `--p` progress on the range input, `Select({ label, value, options, onChange, description })`, `Toggle({ label, description, checked, onChange })`, `NumberInput({ label, value, min, max, step, onChange, description })`, `Search({ value, onChange, placeholder })`. Same props as today's `TechSlider`, `TechSelect`, `TechToggle`, `TechNumberInput` in App.jsx so screens are a rename.

- [ ] **Step 1: Failing tests**

```jsx
// src/ui/primitives.test.jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import Pill from './Pill.jsx'; import Delta from './Delta.jsx'; import KeyValue from './KeyValue.jsx'; import { Slider, Toggle } from './Inputs.jsx'

describe('primitives', () => {
  test('Pill carries a tone class and a dot', () => { const { container } = render(<Pill tone="crit">Critical</Pill>); expect(container.querySelector('.pill.crit i')).toBeTruthy(); expect(screen.getByText('Critical')).toBeInTheDocument() })
  test('Delta direction follows upBad', () => {
    const { container, rerender } = render(<Delta diff={2} pct={3.2} unit="pct" />); expect(container.firstChild).toHaveClass('up'); expect(container.textContent).toBe('▲ 3.2%')
    rerender(<Delta diff={2} pct={3.2} unit="pct" upBad />); expect(container.firstChild).toHaveClass('down')
    rerender(<Delta diff={0} pct={0} unit="pts" />); expect(container.textContent).toBe('— 0.0 pts')
  })
  test('KeyValue renders label and value', () => { render(<KeyValue label="Bonds held" value="$750" />); expect(screen.getByText('Bonds held')).toBeInTheDocument(); expect(screen.getByText('$750')).toBeInTheDocument() })
  test('Slider reports numbers and Toggle flips', () => {
    const onChange = vi.fn(); render(<Slider label="Wage tax" value={0.15} min={0} max={0.5} step={0.01} format={v => `${(v*100).toFixed(0)}%`} onChange={onChange} />)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.2' } }); expect(onChange).toHaveBeenCalledWith(0.2)
    const flip = vi.fn(); render(<Toggle label="AI government" checked={false} onChange={flip} />); fireEvent.click(screen.getByText('AI government')); expect(flip).toHaveBeenCalledWith(true)
  })
})
```

- [ ] **Step 2: Run to verify fail.**  `npx --yes node@22 ./node_modules/.bin/vitest run src/ui`
- [ ] **Step 3: Implement** each file with the markup from the prototype (`pill`, `chip`, `.delta`, `rowKV`, `field`/`sel`/`toggle` helpers). `Delta` text rule: `unit==='pct'` → `${Math.abs(pct).toFixed(1)}%`, `'pts'` → `${Math.abs(diff).toFixed(1)} pts`, `'int'` → `${Math.abs(Math.round(diff))}`; arrow `▲` if `diff>0`, `▼` if `diff<0`, else `—`; class `up` when `(diff>0) !== upBad` and `diff !== 0`, `down` when `diff !== 0` otherwise, none for zero.
- [ ] **Step 4: Run tests.** Expected PASS.
- [ ] **Step 5: Commit** `feat(frontend): ui primitives and inputs`

---

### Task 4: Chart layer, part 1: measurement hook, Sparkline, TimeSeries

**Files:**
- Create: `src/charts/useMeasured.js`, `src/charts/Sparkline.jsx`, `src/charts/TimeSeries.jsx`
- Test: `src/charts/TimeSeries.test.jsx`

**Interfaces:**
- `useMeasured()` → `[ref, { width, height }]` via ResizeObserver (port `useMeasuredWidth` from `ui/primitives.jsx`, add height).
- `Sparkline({ data: number[], tone: 'acc'|'warn'|'crit'|'flat', width=64, height=22 })` → inline SVG, 1.25px line in `var(--ink4)` (tone colour when warn/crit), 2.4px end dot in the tone colour (accent when nominal).
- `TimeSeries({ series: [{ data: [{tick,value}], tone, name }], format, axes=true, endLabel=false, band=[lo,hi], markers=[{tick,label,ai,ok}], split={ tick, color }, n=250, height })` → fills its `.chart` wrapper. Aligns by tick: the x domain is the union of ticks; a series missing a tick is not zero-filled (use Recharts `connectNulls` with `null`). Renders: gradient area (0.14→0), 2px `monotone` line, end dot (r 4.5 with a `var(--panel)` ring r 7), end label text (`format(last)` + name), 3 horizontal hairline grid lines with Y labels, 5 X tick labels `t{tick}`, band as a `ReferenceArea` in `var(--crit)` at 7% opacity, markers as `ReferenceLine`s in `var(--ai)` or `var(--acc)` (dashed `3 3` when `ok===false`, label staggered by index parity, hidden when measured width < 470), tooltip crosshair with `t{tick}` and per-series values. `split` mode: draws the pre-split part of each series as a second `Line` in `var(--ink4)` 1.5px and the post-split part in colour, with a `ReferenceArea` from the split tick to the end in `split.color` at 7% and a `ReferenceLine` at the split tick. Draw-in animation only on first mount (`isAnimationActive` true once, then false).

- [ ] **Step 1: Failing test**

```jsx
// src/charts/TimeSeries.test.jsx
import { render } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import frame from '../test/fixtures/frame.json'
import TimeSeries from './TimeSeries.jsx'

vi.mock('./useMeasured.js', () => ({ default: () => [{ current: null }, { width: 600, height: 200 }] }))

describe('TimeSeries', () => {
  const gdp = { data: frame.metrics.gdpHistory, tone: 'acc', name: 'GDP' }
  test('renders one path per series and an end label', () => {
    const { container } = render(<div style={{ height: 200 }}><TimeSeries series={[gdp]} format={v => `$${v}`} endLabel /></div>)
    expect(container.querySelectorAll('.recharts-area').length).toBe(1)
    expect(container.textContent).toContain('GDP')
  })
  test('split mode adds the pre-change line and the shaded region', () => {
    const { container } = render(<TimeSeries series={[gdp]} format={v => v} split={{ tick: frame.metrics.gdpHistory[1].tick, color: 'var(--ai)' }} />)
    expect(container.querySelectorAll('.recharts-line').length).toBe(1)
    expect(container.querySelector('.recharts-reference-area')).toBeTruthy()
  })
  test('markers render as reference lines with labels', () => {
    const { container } = render(<TimeSeries series={[gdp]} format={v => v} markers={[{ tick: frame.metrics.gdpHistory[1].tick, label: 'Wage tax 15% → 18%', ai: false, ok: true }]} />)
    expect(container.querySelector('.recharts-reference-line')).toBeTruthy()
    expect(container.textContent).toContain('Wage tax')
  })
})
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.** Build the chart data as `ticks.map(t => ({ tick: t, s0: valueAt(series[0], t) ?? null, s1: … }))`; use Recharts `ComposedChart` with `Area` per series (gradient defs keyed by index), `Line` for the pre-split segment (dataKey `pre0`, values null after the split tick), `XAxis dataKey="tick"` with `tickFormatter={t => 't'+t}` and 5 ticks, `YAxis` with 3 ticks and `tickFormatter={format}`, `CartesianGrid` horizontal only with `stroke="var(--grid)"`, `Tooltip` with a custom content component reusing the prototype tooltip markup, `ReferenceArea`/`ReferenceLine` for band, split, and markers. The end dot and label are custom SVG appended with `Customized` or by rendering the last point through `Scatter` with a custom shape. Keep every colour as a `var(--…)` string.
- [ ] **Step 4: Run tests.** PASS.
- [ ] **Step 5: Commit** `feat(frontend): TimeSeries and Sparkline chart components`

---

### Task 5: Chart layer, part 2: Meter, CompositionBar, Radar, ProfileBars, Ledger

**Files:**
- Create: `src/charts/Meter.jsx`, `src/charts/CompositionBar.jsx`, `src/charts/Radar.jsx`, `src/charts/ProfileBars.jsx`, `src/charts/Ledger.jsx`
- Test: `src/charts/small.test.jsx`

**Interfaces:**
- `Meter({ value, zones: [45,70], tones: ['good','warn','crit'] })` → `.meter` track with `.z` ticks at each zone percent and `.fill` width `min(100,value)%` in the tone for the zone the value falls in.
- `CompositionBar({ segments: [{ label, value, tone }] })` → `.stack` (2px gaps, widths in %) plus a `.legend` with swatch, label and `value.toFixed(1)%`.
- `Radar({ dims: [{ label, value: 0..1 }], median: number[] })` → SVG viewBox `0 0 320 248`, port `drawRadar` from the prototype: rings at .25/.5/.75/1, axes, median polygon (ink4, 12% fill), subject polygon (accent, 14% fill, 1.5px), vertex dots (crit <.3, warn <.5, else accent) with a panel ring, labels with value `Math.round(v*100)`, footer "grey = population median". Dims are data-driven (the fixture has needs `food, housing, healthcare`; render whatever is present).
- `ProfileBars({ dims, median })` → `.pb` rows with a median tick.
- `Ledger({ rows: [{ label, value, tone, sign }], net: { label, value } , format })` → `.ledger` rows scaled to the max absolute value; the net row gets class `net` and good/crit colour by sign.

- [ ] **Step 1: Failing tests**

```jsx
// src/charts/small.test.jsx
import { render } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import Meter from './Meter.jsx'; import CompositionBar from './CompositionBar.jsx'; import Radar from './Radar.jsx'; import Ledger from './Ledger.jsx'

describe('small charts', () => {
  test('Meter fills to the value in the zone tone', () => {
    const { container } = render(<Meter value={52} zones={[45, 70]} />)
    const fill = container.querySelector('.meter .fill'); expect(fill.style.width).toBe('52%'); expect(fill.style.background).toContain('--warn'); expect(container.querySelectorAll('.meter .z').length).toBe(2)
  })
  test('CompositionBar widths sum to 100', () => {
    const { container } = render(<CompositionBar segments={[{ label: 'Bottom 50%', value: 6.7, tone: 'ink4' }, { label: 'Middle 40%', value: 46.5, tone: 's1' }, { label: 'Top 10%', value: 46.8, tone: 'acc' }]} />)
    const w = [...container.querySelectorAll('.stack > div')].map(d => parseFloat(d.style.width)); expect(w.reduce((a, b) => a + b)).toBeCloseTo(100, 0)
  })
  test('Radar draws one vertex per dimension', () => {
    const dims = ['Health', 'Happiness', 'Morale', 'Skills', 'Food', 'Housing', 'Healthcare'].map(label => ({ label, value: 0.6 }))
    const { container } = render(<Radar dims={dims} median={dims.map(() => 0.5)} />)
    expect(container.querySelectorAll('circle').length).toBe(dims.length * 2); expect(container.textContent).toContain('Happiness')
  })
  test('Ledger scales rows to the largest and colours the net', () => {
    const { container } = render(<Ledger rows={[{ label: 'Revenue', value: 48200, tone: 'acc', sign: '+' }, { label: 'Transfers', value: 12100, tone: 's1', sign: '−' }]} net={{ label: 'Net flow', value: 28700 }} format={v => `$${Math.round(v / 1000)}K`} />)
    const fills = container.querySelectorAll('.lr .fl'); expect(fills[0].style.width).toBe('100%'); expect(container.querySelector('.lr.net .nv').style.color).toContain('--good')
  })
})
```

- [ ] **Step 2: Run to verify fail.**  - [ ] **Step 3: Implement** by porting `drawGauge`-free code: `drawRadar`, `profileBars`, `ledgerHTML`, the meter markup and `wealthbars` markup from the prototype into JSX (build SVG elements in JSX, not `innerHTML`).  - [ ] **Step 4: Run tests.** PASS.  - [ ] **Step 5: Commit** `feat(frontend): meter, composition bar, radar, profile bars, ledger`

---

### Task 6: StatTile, ChartTile, HeroMetric with count-up

**Files:**
- Create: `src/ui/useCountUp.js`, `src/ui/StatTile.jsx`, `src/ui/ChartTile.jsx`, `src/ui/HeroMetric.jsx`
- Test: `src/ui/tiles.test.jsx`

**Interfaces:**
- `useCountUp(value, { duration=450, fromZero=false })` → the displayed number, eased (cubic out) with `requestAnimationFrame`, cancelling any in-flight animation; progress clamped to [0,1]; honours `prefers-reduced-motion` by snapping.
- `StatTile({ label, value, format, history, tick, tone, upBad, caption, unit })` → `.tile` with `.l` (label + `Delta` vs one sample back of `history`), `.v` (count-up, `num` class, tone colour), `.foot` (caption + `Sparkline` of the last 24 history values, tone colour when warn/crit).
- `ChartTile` → same header, then a `TimeSeries` (`axes=false`, `n=120`) filling the tile (`.tile.ctile`).
- `HeroMetric({ label, value, format, history, tone, pill, children })` → `.hero` with 52px `.v`, `Delta`, `Pill`, then `children` (usually a chart).

- [ ] **Step 1: Failing test**

```jsx
// src/ui/tiles.test.jsx
import { act, render } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, test, vi } from 'vitest'
import StatTile from './StatTile.jsx'

describe('StatTile', () => {
  beforeEach(() => { vi.useFakeTimers(); let t = 0; vi.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => setTimeout(() => cb(t += 100), 16)) })
  afterEach(() => vi.restoreAllMocks())
  test('counts up to the value and shows a delta and sparkline', () => {
    const history = [{ tick: 1, value: 50000 }, { tick: 25, value: 52000 }]
    const { container } = render(<StatTile label="GDP output" value={55100} format={v => `$${(v / 1000).toFixed(1)}K`} history={history} caption="per tick" />)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(container.querySelector('.tile .v').textContent).toBe('$55.1K')
    expect(container.querySelector('.delta').textContent).toMatch(/▲ 6\.0%/)
    expect(container.querySelector('svg path')).toBeTruthy()
  })
  test('tone recolours the tile', () => {
    const { container } = render(<StatTile label="Unemployment" value={28.8} format={v => `${v}%`} tone="warn" upBad />)
    expect(container.querySelector('.tile')).toHaveClass('warn')
  })
})
```

- [ ] **Step 2: Run to verify fail.**  - [ ] **Step 3: Implement** per the prototype's `tile()`, `ctile()`, `animateNum()` (clamp progress, cancel by id).  - [ ] **Step 4: Run tests.** PASS.  - [ ] **Step 5: Commit** `feat(frontend): stat tiles and hero metric with count-up`

---

### Task 7: Test helper for screens

**Files:**
- Create: `src/test/renderScreen.jsx`

**Interfaces:**
- `renderScreen(Screen, overrides={})` → renders `<Screen {...defaultProps} {...overrides} />` where `defaultProps = { metrics: frame.metrics, firmStats: frame.firm_stats, logs: frame.logs, tick: frame.tick, config: DEFAULT_CONFIG, setupConfig: DEFAULT_SETUP, selection: { subjectIndex: 0, firmIndex: 0, logIndex: 0 }, handlers: noop map }` with `DEFAULT_CONFIG` and `DEFAULT_SETUP` copied from the `useState` initialisers in `App.jsx` (lines 720 to 760 area) and `handlers` covering `onConfigChange, onSetupChange, onSelectSubject, onSelectFirm, onSelectLog, onLaunch, onReset, onToggleRun, onStabilizers`. Canvas components are stubbed: `vi.mock('../NeuralAvatar', …)` etc. returning `<div data-canvas />`.

- [ ] **Step 1: Write the helper** (no test of its own; Task 9's test uses it).
- [ ] **Step 2: Commit with Task 9.**

---

### Task 8: Shell: rail, top bar, status strip, theme, App.jsx slimming

**Files:**
- Create: `src/shell/Logo.jsx`, `src/shell/Rail.jsx`, `src/shell/TopBar.jsx`, `src/shell/StatusStrip.jsx`
- Modify: `src/App.jsx` (delete `techStyles`, `CircularProgress`, `NavButton`, `StatTile`, `TechSlider`, `TechNumberInput`, `TechSelect`, `SectionHeader`, `StatusPill`, `FinanceLiquidityHologram`, `LiveRunProjection`, `DetailRow`, `Badge`, `RawJsonBlock`, `SystemDistressGauge`, `WealthDistributionChart`; keep every hook, handler and the `onmessage` merge; render `<Rail/>`, `<TopBar/>`, `<StatusStrip/>` and the screen switch)
- Delete: `src/ui/primitives.jsx` (after the screens in Tasks 9 to 15 no longer import it; do the delete in Task 15)
- Test: `src/shell/shell.test.jsx`; `src/App.test.jsx` unchanged

**Interfaces:**
- `Logo()` → the supply-demand SVG from the prototype's `LOGOS[1]`.
- `Rail({ view, onSelect, enabled, connected })` → seven `NavButton`s (Config always enabled) with lucide icons `Settings, Activity, Users, Building2, Wallet, Landmark, Terminal`, the ONLINE dot bound to `connected`.
- `TopBar({ view, tick, running, initialized, connected, onToggleRun, onReset })` → breadcrumb `EcoSim / <view title>`, tick box (`formatTick`), run pill, Suspend/Resume and Reset buttons (same handlers as today).
- `StatusStrip({ sessionId, metrics, tick, config, policyChanges })` → session, compute ms (`metrics.tickComputeMs`), households (`metrics.trackedSubjects` is only 12; use the setup population from props), firms (`firmStats.total_firms`), unemployment, policy mode (`manual` or `manual + assistant` when `config.enableLlmGovernment`), last change from `policyChanges[0]` via `formatPolicyMessage`.
- Theme: `App.jsx` sets `document.documentElement.dataset.theme` from a `theme` state (`'ember'` default, persisted in `localStorage['ecosim.theme']`, wrapped in try/catch) and passes `onToggleTheme` to `TopBar` (a small sun/moon button).
- App.jsx exposes the view screens through a map `{ CONFIG: Config, DASHBOARD: Command, SUBJECTS: Population, FIRMS: Markets, FINANCE: Finance, GOVERNMENT: Government, LOGS: Logs }`; until each screen exists (Tasks 9 to 15) the old JSX block stays for that view. Do the deletions of old helpers only once no view uses them (final cleanup in Task 15).

- [ ] **Step 1: Failing test**

```jsx
// src/shell/shell.test.jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import Rail from './Rail.jsx'; import TopBar from './TopBar.jsx'

describe('shell', () => {
  test('rail disables non-config views until initialised', () => {
    const onSelect = vi.fn(); render(<Rail view="CONFIG" enabled={false} connected onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Population')); expect(onSelect).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Config')); expect(onSelect).toHaveBeenCalledWith('CONFIG')
  })
  test('top bar shows the tick and the run state', () => {
    render(<TopBar view="DASHBOARD" tick={262} running initialized connected onToggleRun={() => {}} onReset={() => {}} onToggleTheme={() => {}} />)
    expect(screen.getByText('00262')).toBeInTheDocument(); expect(screen.getByText('Running')).toBeInTheDocument(); expect(screen.getByText(/Suspend/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify fail.**  - [ ] **Step 3: Implement** the shell components from the prototype's rail/topbar/strip markup, mount them in `App.jsx` in place of the current `<nav>` and `<header>`, and remove the `<style>{techStyles}</style>` line together with the `techStyles` constant.  - [ ] **Step 4: Run the whole suite**, including `App.test.jsx` (it looks for the Config screen, ONLINE, and the SETUP/START handshake, all preserved).  - [ ] **Step 5: Commit** `feat(frontend): command-center shell and theme switch`

---

### Task 9: Command screen

**Files:**
- Create: `src/screens/Command.jsx`
- Modify: `src/App.jsx` (replace the `DASHBOARD` block with `<Command …/>`)
- Test: `src/screens/Command.test.jsx`

**Interfaces:**
- `Command({ metrics, firmStats, tick, policyChanges, llmGov, latestDecision, llmStatusLabel })`. Layout and content exactly as the prototype's `V.command`: `Ticker` strip; six `StatTile`s (`gdp` money, `unemployment` pct1 tone warn>25 crit>35 upBad, `employment` derived, `avgWage` usd2, stress score tone warn>45 crit>70 upBad, `govProfit` moneyS tone crit<0); GDP `TimeSeries` (`gdpHistory` with `appendCurrent`, markers from `policyChanges` mapped to `{ tick, label: formatPolicyMessage(c), ai: classifyActor(c.reason)==='ai', ok: true }`); population stress panel (`Meter` zones 45/70 + `TimeSeries` of a client-side stress history kept in a ref, max 80 points, plus `happiness` and `healthHistory` tiles); sector prices `.g4` of four `TimeSeries` (`priceHistory[sector]`, tone s1..s4, `endLabel`, `axes=false`); wealth `CompositionBar` (bottom50Share, `100-top10-bottom50`, top10Share) with Gini `KeyValue`, `Delta`, pill (crit >0.6, warn >0.45) and `giniHistory` chart; wages `TimeSeries` (`wageHistory` mean vs `medianWageHistory`); policy assistant panel (`llmStatusLabel`, `latestDecision.rationale`, before→now facts using `backN` on `unemploymentHistory` and `govProfitHistory`); unemployment `TimeSeries` with `band=[25,100]` and markers.

- [ ] **Step 1: Failing test**

```jsx
// src/screens/Command.test.jsx
import { screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { renderScreen } from '../test/renderScreen.jsx'
import Command from './Command.jsx'

describe('Command screen', () => {
  test('renders the six tiles, the GDP chart, the meter and the wealth bar from the fixture', () => {
    const { container } = renderScreen(Command)
    for (const label of ['GDP output', 'Unemployment', 'Employment', 'Average wage', 'Macro stress', 'Fiscal balance']) expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(container.querySelectorAll('.meter').length).toBe(1)
    expect(container.querySelectorAll('.stack > div').length).toBe(3)
    expect(container.querySelectorAll('.chart').length).toBeGreaterThanOrEqual(8)
    expect(container.textContent).toContain('Sector prices')
  })
})
```

- [ ] **Step 2: Run to verify fail.**  - [ ] **Step 3: Implement** the screen; wire it in `App.jsx`; delete the old DASHBOARD JSX.  - [ ] **Step 4: Run the suite.** PASS, `App.test.jsx` included.  - [ ] **Step 5: Commit** `feat(frontend): command screen`

---

### Task 10: Population screen

**Files:** Create `src/screens/Population.jsx`; modify `src/App.jsx` (replace `SUBJECTS`); test `src/screens/Population.test.jsx`.

**Interfaces:** `Population({ metrics, tick, subjectIndex, onSelectSubject, search, onSearch, filter, onFilter })`. Content per `V.population`: header KPIs (employment, at-risk count = unemployed or cash < 150 among tracked subjects, median cash of tracked subjects); roster (`.roster` of `trackedSubjects`: state dot good/warn/crit, name via the existing `readableEntityName` logic moved into `format.js` as `readableName`, employer, `compactMoney(cash)`, `Sparkline(history.cash)`), search box and cohort chips (All, Working, Unemployed, At risk, No housing) using the existing filter logic from App.jsx; hero card (`Panel hot`): identity line, employer + wage, `Pill`s for state and housing security (`housingSecurity`, `hasRental`, `ownsHousing`), `HeroMetric` net worth with delta vs `history.netWorth`, `NeuralAvatar` in a 150px slot, profile head with Radar/Bars chips (local state), `Radar` dims `[health, happiness, morale, skills, ...needs]` against the median of the same dims across all tracked subjects, four `KeyValue`s (expectedWage, reservationWage, monthlyRent, medicalDebt), then a `.g2` with wealth (`history.netWorth`) and wage (`history.wage`) `TimeSeries` filling the card; right column panels: wage drivers (`expectedWageReason` fields via `KeyValue`), housing rows, this-tick `Ledger` (wage +, rent −, spending from `recentEvents` if present else the needs-weighted estimate used in the prototype's `hhLedger`), recent events (`recentEvents` or the prototype's derived list when empty).

- [ ] **Step 1: Failing test** — render with `renderScreen(Population)`; assert the roster has 12 rows (`.r`), the radar has ≥ 5 vertex dots, clicking the third roster row calls `onSelectSubject(2)`, and the hero shows the first subject's name.  - [ ] **Step 2–5:** verify fail, implement, run suite, commit `feat(frontend): population screen`.

---

### Task 11: Markets screen

**Files:** Create `src/screens/Markets.jsx`; modify `src/App.jsx` (replace `FIRMS`); test `src/screens/Markets.test.jsx`.

**Interfaces:** `Markets({ metrics, firmStats, tick, firmIndex, onSelectFirm })`. Per `V.markets`: four `StatTile`s (total_firms, total_employees, avg_wage_offer usd2, struggling_firms tone warn≥3 crit≥6 upBad); sector map `.g4` of hairline-divided cells from `firmStats.categories` (firm_count, total_employees, avg_cash with crit colour < 2000, avg_price, `TimeSeries` of `priceHistory[category]`, pill Distress/Stable); selected firm `Panel hot` with `NeuralBuilding` slot and `KeyValue`s (cash, lastProfit signed, employees, wageOffer, price, inventory, quality); all-firms table: merge `firmStats.top_cash`, `firmStats.top_employers` and `metrics.trackedFirms` by `id`, sortable columns (local state `sortKey`, `sortDir`), inline cash bar scaled to the max, state `Pill`, rows selectable (`onSelectFirm(index in trackedFirms)` when the firm is tracked, otherwise no-op), wrapper class `tablefill`; cash and profit `TimeSeries` from `trackedFirms[firmIndex].history.cash` / `.profit` (`zero` line for profit).

- [ ] **Step 1: Failing test** — table has ≥ 7 rows, clicking a header re-sorts (first row changes), sector map shows the four category names, selected firm panel shows `trackedFirms[0].name`.  - [ ] **Step 2–5:** as above; commit `feat(frontend): markets screen`.

---

### Task 12: Finance screen

**Files:** Create `src/screens/Finance.jsx`; modify `src/App.jsx` (replace `FINANCE`, delete `FinanceLiquidityHologram`); test `src/screens/Finance.test.jsx`.

**Interfaces:** `Finance({ metrics, tick, policyChanges })`. Per `V.finance`: `HeroMetric` net fiscal balance (`govProfit`, history `govProfitHistory`, pill Surplus/Deficit) with a 56px `TimeSeries`; four `ChartTile`s: revenue (`govRevenue`, client-side history ref), transfers + investment (`govTransfers + govInvestments`), bond purchases (`bondPurchases`, tone warn when rising 8 ticks), household net worth (`netWorth`, `netWorthHistory`); fiscal flows `TimeSeries` (revenue and outlays client histories, markers); ledger panel: `Ledger` rows revenue (+, acc), transfers (−, s1), investments (−, s1), bond purchases (−, s1), net (`govProfit`); two tiles under it: `activeLoans` and `govDebt` (tone crit > 0); loans history `TimeSeries` (client history of `activeLoans`, 250 points) and state capacity `KeyValue`s (`govOwnedFirms`, `activeLoans`, `bondPurchases`, `govInvestments`, `govDebt`). Client-side histories: a `useTickHistory(metrics, keys, max=250)` hook in `src/telemetry.js` that appends `{tick, value}` per new tick for the listed keys (used by Command for stress too).

Units: `govProfit`, `govDebt`, `govRevenue`, `govTransfers`, `govInvestments`, `bondPurchases`, `netWorth` are in millions in the frame (see `formatMillionsAdaptive` usage in App.jsx); format with `formatMillionsAdaptive` and `signedMillions` (add `signedMillions` to `format.js` like the console's helper).

- [ ] **Step 1: Failing test** — hero present, four `.ctile`s, ledger has 5 rows with the last one `.net`, no element with text `N/A`, no `Bank inspector`.  - [ ] **Step 2–5:** commit `feat(frontend): finance screen`.

---

### Task 13: Government screen (restyle the console)

**Files:**
- Create: `src/screens/Government.jsx` (from `GovernmentConsole.jsx`), `src/screens/government/Timeline.jsx`, `src/screens/government/EffectsPanel.jsx`, `src/screens/government/LeverTile.jsx`
- Move: `src/GovernmentConsole.test.jsx` → `src/screens/Government.test.jsx` (update the import; it renders `App`, so it keeps passing as long as the screen renders the same texts it asserts on; read the test's assertions first and keep those labels: "Latest decision", "Policy timeline" becomes the timeline's title, lever labels, "Accepted", "Refused")
- Delete: `src/GovernmentConsole.jsx`
- Modify: `src/App.jsx` (`GOVERNMENT` renders `Government` with the same props as today)

**Interfaces:**
- `Government(props)` keeps today's props (`metrics, tick, config, onConfigChange, enumOptions, isAiActive, llmGov, latestDecision, llmStatusLabel, llmActivityLevel, friendlyModelName`) and all `governmentInsights.js` derivations. Layout per `V.government`: top strip (chips, goal headline via `goalHeadline`, subline, facts, `NeuralGovernment` slot, AI `Toggle`); `Panel s8` grid `5.4fr/6.6fr` with `Timeline` (left) and `EffectsPanel` (right); `Panel s4` policy stance of `LeverTile`s grouped by `LEVER_GROUPS`; bottom row `Ledger` (same as Finance), assistant card (`llmGov` counts, `decision.elapsed_ms`, provider, model, `lastError`), state capacity.
- `Timeline({ changes, selected, onSelect, histories })` → `.tlwrap` of `.tlc` cards (`--tlc` actor colour; tick `.tk`, actor `.ac`, headline `leverLabel(key) prev → value`, reason `changeNarrative`, `ImpactChips` from `impactSince`), refused changes from `latestDecision.rejected_changes` rendered as `Refused` cards at `appliedTick`, plus a `This run` summary (`KeyValue`s: AI accepted, AI refused, manual, automatic, next review).
- `EffectsPanel({ change, histories, decision, tick })` → title "Effects since t{tick} · {label}" or "Refused at …"; `.effgrid` of four `TimeSeries` in `split` mode (gdp, unemployment, happiness, fiscal from `histories`, `split.color` by actor) with before→after values in `.effh`; the model's rationale `.quote` and evidence audit rows (`describeEvidenceAudit`) when the change actor is `ai` and it is the latest decision; "Lever moved" pill.
- `LeverTile({ lever, live, isDefault, lastChange, hit, hitColor, onEdit })` → `.lv` with `active` when off default, `hit` ring when `hit`; clicking calls `onEdit(lever)` which opens the existing `LeverControl` inline under the tile (keep `LeverControl` from the console).
- Selected change: local state, default the newest accepted change.

- [ ] **Step 1: Read `src/GovernmentConsole.test.jsx` fully and list the texts it asserts.** Keep them.  - [ ] **Step 2: Move the test, run it, watch it fail on the missing module.**  - [ ] **Step 3: Implement** the four files; keep `AiToggle`, `LeverControl`, `AuditMark`, `OutcomeBox` logic from the console where still used.  - [ ] **Step 4: Run the suite.** PASS, including `governmentInsights.test.js`.  - [ ] **Step 5: Commit** `feat(frontend): government screen around policy changes`

---

### Task 14: Logs screen

**Files:** Create `src/screens/Logs.jsx`; modify `src/App.jsx` (replace `LOGS`, delete `RawJsonBlock` after moving it into the screen); test `src/screens/Logs.test.jsx`.

**Interfaces:** `Logs({ logs, tick, metrics, logIndex, onSelectLog, typeFilter, onTypeFilter, severityFilter, onSeverityFilter, search, onSearch, density, onDensity, autoScroll, onAutoScroll })` using the existing `normalizeLog` (move it to `src/logs.js` with a unit test asserting a `SYS` type maps to `System`/`info` and a message containing `distress` maps to `error`). Per `V.logs`: filter row (type chips with counts, severity chips); tiles (events, warnings, errors, tick time `StatTile` on `metrics.tickComputeMs` with a client history); table with severity dot, `tablefill`, auto-scroll to bottom when `autoScroll`; detail panel with `KeyValue`s, message, raw JSON block, same-entity list (last 6 by `ent`), buffer-by-type bars (`Ledger`-style rows in ink3).

- [ ] **Step 1: Failing test** — chips show counts, table has rows, clicking a type chip calls `onTypeFilter`, detail shows the selected log's message.  - [ ] **Step 2–5:** commit `feat(frontend): logs screen`.

---

### Task 15: Config screen and cleanup

**Files:** Create `src/screens/Config.jsx`; modify `src/App.jsx` (replace `CONFIG`, delete `LiveRunProjection` and every unused helper listed in Task 8, delete `ui/primitives.jsx` and its imports); test `src/screens/Config.test.jsx`.

**Interfaces:** `Config({ setupConfig, onSetupChange, config, onConfigChange, isInitialized, wsConnected, wsEndpoint, sessionId, onLaunch, onResetDefaults, onApply, stabilizerAgentOptions, enumOptions })`. Per `V.config`: header with Launch (`onLaunch`, disabled while initialising or disconnected; when initialised show `Apply changes` calling `onApply` and the reset-defaults button instead); run profile (population `Slider` 100..10000 step 100, seed `NumberInput`), opening policy (wage tax, profit tax `Slider`s bound to `setupConfig` before launch and `config` after, minimum wage, benefit level `Select`), policy assistant `Toggle` (`enable_llm_government`) and stabilizer `Toggle` + agent chips (`disable_stabilizers`, `disabled_agents`), preflight checklist (backend connected = `wsConnected`, session = `sessionId`, profile valid = `num_households >= 3`, warehouse line static "per server config"), "what this run creates" strip, run schedule rows, sectors at launch, assistant setup rows. The offline banner (`Backend telemetry offline. Target: …`) stays, restyled as a `Pill crit` line, because `App.test.jsx` may look for Config content: read the test first and keep every string it asserts on.

- [ ] **Step 1: Read `src/App.test.jsx` and list its asserted strings.**  - [ ] **Step 2: Failing screen test** — launch button calls `onLaunch`, population slider calls `onSetupChange('num_households', 2000)`, checklist shows the session id.  - [ ] **Step 3: Implement**, wire, delete the dead helpers and `primitives.jsx`.  - [ ] **Step 4: Run the full suite, then `npm run lint` and `npm run build`** (`npx --yes node@22 ./node_modules/.bin/eslint .` and `npx --yes node@22 ./node_modules/.bin/vite build` from `frontend-react/`). Expected: 0 lint errors, build emits `charts` and `icons` chunks.  - [ ] **Step 5: Commit** `feat(frontend): config screen; remove legacy dashboard helpers`

---

### Task 16: Visual verification and wiki note

**Files:** none new (screenshots go to the session scratchpad); modify `frontend-react/README.md` (theme switch, fixture script) and `docs/TECHNICAL.md` frontend paragraph if it names components.

- [ ] **Step 1:** Start the backend (`.venv/bin/python -m uvicorn backend.server:app --port 8002`) and the dev server (`npx --yes node@22 ./node_modules/.bin/vite --port 5174`), launch a 1,000-household run, screenshot all seven screens at 1440x960 in both themes, and compare against `docs/superpowers/specs/2026-09-06-prototype.html`. Check the fill rule on every panel: no panel with more than a sliver of empty space under a chart or table.
- [ ] **Step 2:** Fix any deviation in the screen file that owns it; re-run the suite.
- [ ] **Step 3:** Update the README lines and commit `docs(frontend): theme switch and fixture capture`. Report that an OpenWiki refresh is due (screen inventory and component names changed).

---

## Self-review

- Spec coverage: tokens (T1), type (T1), logo (T8), decoration deletions (T12, T15), motion (T6, T1 reduced-motion), radar (T5, T10), Government emphasis (T13), slop rules (T1 test, T8), fill rule (T1 CSS, tested visually in T16), components (T3–T6), every screen (T9–T15), data mapping (each screen task lists its fields), code structure (file structure section), unchanged behaviour (App.test.jsx gate in every task), testing (per-task tests, T16), delivery (header).
- Placeholders: none; screen tasks point at the prototype functions for markup and list fields explicitly.
- Type consistency: `Delta` props `{diff, pct, unit, upBad}` used by `StatTile`; `TimeSeries` props `{series, format, axes, endLabel, band, markers, split, n}` used by every screen; `Ledger` rows `{label, value, tone, sign}` in Finance, Government, Population, Logs; formatter names match `FORMATTERS`.
