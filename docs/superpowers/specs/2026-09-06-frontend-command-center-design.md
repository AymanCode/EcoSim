# EcoSim frontend: command-center redesign

Date: 2026-09-06. Status: approved by Ayman after an interactive prototype
(`.superpowers/brainstorm/*/content/prototype.html`, ignored by git). The
prototype is the visual reference for every screen; this document is the
contract the implementation is checked against.

## 1. Goal and scope

Rebuild the presentation layer of `frontend-react` so every screen reads as one
command center: dense, data-first, numbers that lead, charts that fill their
box, no template look. The WebSocket protocol, session lifecycle, state shape,
handlers, and reconnect behaviour in `App.jsx` stay as they are. Frontend only:
every panel maps to a field the server already sends (see section 6).

Out of scope: backend telemetry changes, bank/deposit metrics, mobile layouts
below 1024px (the app remains desktop-first), warehouse HTTP routes.

## 2. Decisions made with Ayman

| Decision | Choice |
|---|---|
| Theme | Dark by default: carbon base with an ember (signal orange) accent. Light mode: paper base with the same roles. One token set, two values per token. Cyan, navy and gold are gone. |
| Type | Barlow for everything, Barlow Semi Condensed for hero and tile numerals, JetBrains Mono for tables, axes, tick counter and logs. No Inter. |
| Logo | Supply and demand cross: thin axes, demand curve in ink, supply curve in the accent, equilibrium dot in the accent. One mark, theme-driven. |
| Decoration | The three neural canvases stay as accents in a bounded slot (avatar on Population, building on Markets, obelisk on Government). The finance hologram and config projection are deleted. |
| Motion | Tick-driven count-ups (450ms, ease-out cubic), chart draw-in on first mount, cross-fade on view change. No glow, no pulsing borders, no bounce. `prefers-reduced-motion` disables all of it. |
| Holistic household view | One radar profile of eight dimensions over the population median, with a bars alternative. |
| Government | Policy changes are the dominant element: a timeline of changes with a large effects panel split at the change tick; levers are compact tiles around it; the lever a change moved is highlighted. |
| Slop rules | No glassmorphism, no glow, no colored side rails, no cards nested in cards, no gauges or donuts, no dashed gridlines, no sparkline-as-decoration, radii 5 to 6px, Inter banned. |

## 3. Design tokens

Defined once in `src/theme/tokens.css` on `:root[data-theme="ember"]` and
`:root[data-theme="paper"]`, consumed by Tailwind (`tailwind.config.js` maps
color names to `var(--…)`) and by chart code.

| Token | Ember (dark) | Paper (light) | Role |
|---|---|---|---|
| page | #08090B | #EDE9E0 | app background |
| panel | #111316 | #FBF9F4 | panel surface |
| panel2 / panel3 | #171A1F / #1F232A | #F4F0E8 / #E7E2D7 | raised surfaces, tracks |
| line / line2 | white 8% / 15% | ink 9% / 18% | hairlines |
| ink / ink2 / ink3 / ink4 | #F5F6F7 / #C2C7CF / #8A919C / #5B626C | #14120F / #3E3A33 / #77716A / #A39D92 | text tiers |
| acc | #FF6B1A | #D2491E | identity, primary series, active state |
| good / warn / crit | #34D399 / #FFB020 / #E0245E | #1D8F4E / #A16207 / #9F1239 | status, always with icon or label |
| ai | #C084FC | #7C3AED | anything the AI government did |
| s1..s4 | #3987e5 / #199e70 / #9085e9 / #d55181 | #2a78d6 / #1baf7a / #4a3aa7 / #e87ba4 | Food, Housing, Services, Healthcare |
| grid | #20242B | #DDD7CB | chart gridlines |

Validated with the dataviz palette validator on each surface: sector slots
pass adjacent CVD separation in both modes; critical is a magenta-leaning red
so it never reads as the accent; the light warning shares a hue family with
the accent and therefore always carries an icon and label.

Type scale: hero 48 to 52px, tile value 28px, section title 12px 700, body 13px,
label 11px 600, mono 11 to 12px. Nothing below 10.5px.

## 4. Layout system

- Shell: 76px icon rail (mark, wordmark, seven nav items, ONLINE dot), 54px
  top bar (breadcrumb, tick box, run pill, Suspend, Reset), 30px status strip
  (session, compute ms per tick, households, firms, unemployment, policy mode,
  last policy change), scrolling content area with 20px padding.
- Grid: 12 columns, 10px gaps. Panels are flex columns with 10px 12px padding.
- Fill rule (the rule Ayman asked for): a panel's chart takes the panel's
  remaining height. Any grid inside a panel that holds a chart grows to the
  panel, its cells are flex columns, and the chart is `flex:1`. Tables inside
  panels fill and scroll within the panel. A row's height is set by its
  tallest content, never by a fixed chart height. No panel may show a third of
  itself empty.
- Every screen has the same spine: page header (eyebrow, title, one-sentence
  summary), a strip of stat tiles, one dominant visual, supporting panels.

## 5. Components (`src/ui/`)

| Component | Contract |
|---|---|
| `StatTile` | label, value (formatter), delta vs 25 ticks ago (chip, direction-aware colour), caption, 24-point sparkline in ink4 with the live end dot in the accent; `tone` recolours value and border (warn, crit). |
| `ChartTile` | StatTile whose sparkline is a full `TimeSeries` that fills the tile. |
| `HeroMetric` | 48 to 52px value with delta chip and status pill; optional chart below. |
| `TimeSeries` | 2px line, 14% to 0 gradient wash, live end dot with surface ring, optional end label, sparse Y ticks and X tick labels in ticks, threshold band, policy-change markers (accent or ai, dashed when refused, labels staggered, hidden under 470px width), crosshair tooltip on hover, `split` mode drawing before-change in ink4 and after-change in colour with a shaded region. Series align by tick. |
| `Meter` | zoned horizontal meter (ticks at thresholds, fill in the state colour) with a value beside it; replaces every gauge. |
| `CompositionBar` | stacked horizontal bar with 2px gaps and a legend with values; used for wealth shares. |
| `Radar` | One axis per dimension the frame carries (health, happiness, morale, skills plus every key of `needs`; seven with today's server, which sends food, housing and healthcare), hairline rings, median polygon in ink4, subject polygon in the accent, vertex dots coloured by threshold, labels with values. |
| `ProfileBars` | the bars alternative: thin tracks with a median tick. |
| `Ledger` | rows of label, bar on a shared scale, signed mono value; net row separated by a hairline. |
| `Timeline` | change cards on a spine: tick large in mono, actor label, headline, reason, impact chips; selected card tinted in the actor colour. |
| `LeverTile` | compact lever: label, live value, actor and tick of last change; `active` (off default) accent border; `hit` ring in the actor colour when the selected change moved it. |
| `Pill`, `Chip`, `Delta`, `KeyValue`, `SectionTitle`, `PageHeader`, `Ticker` | as in the prototype. |
| Inputs | `Slider` (accent progress track), `Select`, `Toggle`, `NumberInput`, `Search`. |

Formatters live in `src/format.js` (already present) plus `compact money`,
`signed money`, `pct1`, `dec1`, `dec3`, `ms`, `score`.

## 6. Screens and data mapping

All fields are from the WebSocket tick frame: `metrics.*`, `firm_stats.*`,
`logs`, `tick`. Derived values are computed client-side and labelled as such.
No static text from the prototype may stand in for a frame field: a number,
cadence, threshold, or claim that the frame does not carry is either derived
from the frame, taken from one named constant that mirrors backend
configuration, or left out.

**Config (Preflight).** Run profile (population, firms per sector, seed),
opening policy (wage tax, profit tax, minimum wage, benefit level), policy
assistant and stabilizer toggles, preflight checklist (backend connected,
session id, profile valid, warehouse), "what this run creates" strip, run
schedule (tick, metrics stride 5, history sample 25, assistant cadence,
warehouse flush), sectors at launch, assistant setup. Launch button sends SETUP.

**Command.** Ticker strip (10 live metrics with direction). Tiles: gdp,
unemployment, employment (100 minus unemployment), avgWage, macro stress
(45% unemployment, 40% inverse happiness, 15% firm pressure, derived),
govProfit. Dominant: GDP `TimeSeries` with policy markers from
`policyChanges`. Population stress panel: `Meter` with zones 45 and 70 plus an
80-tick stress history, happiness and health tiles. Sector prices as four
small multiples from `priceHistory`. Wealth distribution as `CompositionBar`
(bottom50Share, derived middle, top10Share) with Gini value and `giniHistory`.
Wages mean vs median. Policy assistant card from `llmGovernment`. Unemployment
`TimeSeries` with the 25% band and markers.

**Population.** Header KPIs (employment, at-risk count, median cash of tracked
subjects). Roster of `trackedSubjects` with state dot, employer, cash and cash
sparkline from `history`; search and cohort chips. Hero card: identity,
employer and wage, state and housing pills, net worth `HeroMetric`, avatar
canvas slot, `Radar` over health, happiness, morale, skills and every `needs` key the
frame carries against a population median (median of tracked subjects), expected and
reservation wage, rent, medical debt, wealth and wage `TimeSeries` filling the
card. Right column: wage drivers (`expectedWageReason`), housing rows. There are no per-household event panels: the frame carries no
household events, and an estimate may not stand in for them.

**Markets.** Tiles: total_firms, total_employees, avg_wage_offer,
struggling_firms. Sector map: four hairline-divided cells with firm count,
employees, avg cash, price, and a price small multiple. Selected firm card with
building canvas slot and key values. All-firms table (top_cash merged with
top_employers and trackedFirms, deduplicated by id) sortable, filling its panel
and scrolling. Cash and profit `TimeSeries` for the selected firm from
`trackedFirms[].history`.

**Finance.** Hero net fiscal balance (govProfit) with delta and surplus pill
and a 56px history. Chart tiles: govRevenue, govTransfers plus govInvestments,
bondPurchases, netWorth. Fiscal flows `TimeSeries` (revenue vs outlays) with
markers. Fiscal ledger for the tick (revenue, transfers, investments, bonds,
net) with loans and treasury debt tiles. Government-backed loans history (from
per-tick client accumulation of activeLoans) and state capacity rows
(govOwnedFirms, activeLoans, bondPurchases, govInvestments, govDebt). No
panel for a series that is flat at zero.

**Government.** Keeps the orientation and derivations of the committed
`GovernmentConsole.jsx` and `governmentInsights.js`, restyled and re-weighted:
- Top strip: chips (AI government and model, fiscal mode, goal), goal headline,
  observed to applied ticks, latency, accepted and refused counts, active
  interventions of 17, obelisk canvas slot, AI toggle.
- Policy changes panel (8 columns): `Timeline` of `policyChanges` (actor from
  `classifyActor`, previous value from `parsePreviousValue`, impact chips from
  `impactSince`) beside the effects panel for the selected change: four
  `TimeSeries` in `split` mode (gdpHistory, unemploymentHistory,
  happinessHistory, govProfitHistory) with before and after values, the
  model's rationale and audited evidence (`describeEvidenceAudit`) when the
  change was the AI's, the lever moved as a pill. A refused change shows as
  blocked with no effects.
- Policy stance (4 columns): `LeverTile` grid from `LEVER_GROUPS`, live values
  from `governmentPolicy`, last mover from `latestChangeByLever`; clicking a
  tile opens its control inline. The selected change's lever gets the ring.
- Bottom row: fiscal ledger, assistant card (decision count, accepted and
  refused totals, parse status, latency, next review, provider, model, last
  error), state capacity.

**Logs.** One filter row (type chips with counts, severity chips) above stats
tiles (events, warnings, errors, tick time with sparkline) and the table with a
severity dot per row, filling and scrolling; detail panel with the event, raw
JSON, the same entity's recent events, and buffer-by-type bars.

## 7. Code structure

```
frontend-react/src/
  App.jsx                 state, protocol client, handlers, shell composition (shrinks)
  theme/tokens.css        the token sets above, fonts, base styles
  format.js               formatters (extended)
  governmentInsights.js   unchanged
  ui/primitives.jsx       split into ui/{StatTile,HeroMetric,Pill,Inputs,...}.jsx
  charts/TimeSeries.jsx   Recharts-based series with the contract in section 5
  charts/{Meter,CompositionBar,Radar,ProfileBars,Ledger}.jsx
  screens/{Config,Command,Population,Markets,Finance,Government,Logs}.jsx
  GovernmentConsole.jsx   becomes screens/Government.jsx (keeps its logic)
  Neural*.jsx             unchanged
```

Each screen is a function component receiving `metrics`, `tick`, `firmStats`,
`logs`, selection state and handlers from `App.jsx`. Recharts stays for the
line and bar charts so the `charts` and `icons` chunks in `vite.config.js` are
untouched. Tailwind stays; `techStyles` and the inline `<style>` blocks are
replaced by `tokens.css`.

## 8. Behaviour that must not change

Setup, START, STOP, RESET, CONFIG (changed keys only), STABILIZERS commands;
`SESSION`, `SETUP_COMPLETE`, `STARTED`, `STOPPED`, `RESET`,
`STABILIZERS_UPDATED` handling; telemetry merge with the defensive history
preservation; 400ms config coalescing; 1.2s reconnect; navigation disabled
until initialised; `App.test.jsx` passes unmodified.

## 9. Testing and validation

- `App.test.jsx` unchanged and green.
- One render test per screen using a fixture frame captured from a real run
  (`src/test/fixtures/frame.json`, shape as captured on 2026-09-04).
- `governmentInsights.test.js` and `GovernmentConsole.test.jsx` keep passing
  (the console test is moved with the component).
- `npm run lint`, `npm run build` (chunks unchanged).
- Screenshot pass of all seven screens at 1440x960 in both themes against the
  prototype, checking the fill rule on every panel.

## 10. Delivery

Ayman's rule from 2026-09-06: no Codex. The main session writes tokens,
components and the chart layer, then hands each screen to a Sonnet subagent
with this spec, the prototype file, the fixture, and acceptance criteria; the
main session reviews every screen against the prototype screenshots. A wiki
refresh is due after merge because the dashboard page's screen inventory and
component names change.
