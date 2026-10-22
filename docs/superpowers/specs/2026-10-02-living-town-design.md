# Living town: the diorama Run screen

Date: 2026-10-02. Branch: `feat/living-town` (from `origin/main` at 121428f). Mockups: `2026-10-02-mockups/07-living-town-styles.html` (three drawing styles) and `2026-10-02-mockups/08-diorama-details.html` (the chosen style with every detail). The mockups play the recorded demo; `extract_living_town_data.mjs` rebuilds their data from `frontend-react/public/demo/`.

Status: built on this branch. Where the build differs from the first text of this spec, the line has been edited to say what was built, and "Changes during the build" at the end lists each change with what the line said before.

## 1. Purpose

The new Run screen (`?view=next`, `frontend-react/src/next/`) works but reads as filler: the town is a grid of small icons at the same weight as every list, nothing moves between weeks, and most of what the server sends never reaches the screen. This change makes each town a small living world that a newcomer can read at a glance: who has work, which shops are doing well, how the town feels, where money goes. Numbers stay available, but the picture comes first. The audience and tone rules of `2026-09-24-frontend-learning-redesign-design.md` (newcomer, plain words, few numbers, visuals with stats) still apply.

## 2. Decisions made with Ayman (2026-10-02)

- **Style:** the isometric diorama (mockup 07, option A). The Main Street side view (option B) stays as the close-up of one town. The night map (option C) is dropped.
- **Details:** all 17 numbered details in mockup 08 are approved (section 4).
- **States:** the whole town changes look with how it is doing (weather, light, grass, activity), not only the houses.
- **No layout shift (hard rule):** nothing on the Run screen moves or resizes when the week changes. The mockup and today's Run screen both shift (measured: up to 40 px, 27 times per demo at 489 px wide; 23 px, 9 times at 1440 px). Section 6 defines the rule and its test.
- **Playwright:** approved as a dev dependency for the no-shift test (jsdom cannot measure layout).
- The mockup's "preview a mood" buttons were a review aid; the product shows data only.

## 3. Screen layout

Top to bottom, under the existing timeline bar (`HorizonBar`):

1. The lead sentence and the "What just happened" moments strip (both kept, both fixed-height per section 6).
2. **Town cards**, one per town: header (colour chip, name, rules in force, mood chip, Enlarge button), the diorama, and a facts row (out of work, typical weekly pay, shops open with how many struggling, town hall money). Grid: one town full width; two side by side; three or four in a 2 × 2 grid. Under 1100 px wide the cards stack. **Enlarge** shows only that town at full width and switches Main Street to it; **Show both/all** returns the cards and leaves Main Street on that town.
3. One shared legend for the drawings.
4. **Main Street, up close**, after the legend: the side-view street of one town, with a town picker (segmented control) when there are two or more towns.
5. Per-town columns with the existing **Businesses** list and **Households** cards (kept: they are the browsable, keyboard-reachable panels newcomers liked).
6. The existing story chart, verdict, stat cards, feed and "How to read this", unchanged except for section 6.

The old `components/Town.jsx` drawing is replaced. Its screen-reader summary (`.nx-sr` list) and facts move into the town card. The page keeps the Run screen's existing fonts and `--nx-*` colour tokens (`next.css`); only the drawings use the mockup's scene palette.

## 4. What the drawings show

Every detail is driven by the arm's data at the week on the clock. "This week" means the tick being shown.

### 4.1 The town

1. **Weather follows the mood** (section 5): warm sky and sun when thriving; more and greyer clouds as the mood falls; rain in hard times. In winter the rain is snow, and light snow falls in any mood.
2. **Light and grass**: below "getting by" the scene dims (a plain translucent overlay of `#151E32`, at most 18 % opaque, matched to the multiply blend the mockup used) and the grass dries towards olive; lit windows glow more strongly the darker it gets, so working homes stand out.
3. **Seasons** by week of the year (52-week years): spring weeks 10–22 (some trees blossom), summer 23–35, autumn 36–48 (orange trees), winter 49–52 and 1–9 (bare trees, snow on roofs and pine tips).
4. **Traffic**: cars on the two roads, one per $5,000 of weekly sales (`salesExceptRentThisWeek`), 0–7; people on the pavements in proportion to the share of homes with work, 1–14 (4 during warm-up).
5. **Town hall**: a coin stack sized by `townHallCash` with the amount, or a red IOU slip "owes $Xk" when negative (nothing at all when the figure was not measured, as in an old recording); a queue of people outside, one per $2,800 of `familySupportPaid` this week (0–9); a banner on the façade naming the town's changed rule (short label per lever, "NEW RULES" when several); the existing pulse ring for four weeks after a rule change.
6. **Bank**: a stack of loan papers, one per 55 `bankActiveLoans` (0–7); when `bankDefaultAmountThisTick` is at least $500, the bank flashes red and a "Bad loans $Xk" sign rises.

### 4.2 Businesses

Shops stand on the 50 lots along the two roads (nearest the crossing first), coloured by sector, one floor per 9 staff (1–6 floors), height easing to the new value when staff changes.

7. **Growing**: a tower crane on the roof and a HIRING sign.
8. **Struggling**: SALE painted on the shop window, flickering windows, an amber flag.
9. **Closed**: boarded up with a CLOSED sign for 8 weeks, then (from the 8th week closed, on the island and on Main Street alike) FOR LEASE on the front of the building, no floating sign, and a lower one-floor shell; the lot empties when the firm leaves the server's closed list (about a year).
10. **New**: scaffolding for its first 3 weeks, then balloons and a NEW sign until week 9.
11. **A gold crown** on the richest open shop by cash, not counting the town co-ops (`isBaseline`).
12. **Moments in the picture**, only while playing forward one week at a time (never when scrubbing or jumping): a laid-off worker walks from the shop to a dark home carrying a box (up to 2 per shop, 6 per week); a new hire walks from a lit home to the shop; floating signs "Closed" (with a dust puff), "Opened!", "−N jobs" and "+N jobs" (N ≥ 2), and the bad-loans sign, at most 4 per town per week. A scene also holds at most 8 floating signs at once (a newer sign over the same place replaces the older, and a place shows one sign per week), 12 dust puffs and 24 walkers.

### 4.3 Homes and people

The 100 houses each stand for `householdsTotal / 100` households, as today. Each house keeps a fixed spot and a fixed rank from the town's seed, so matched towns line up house for house; the lowest ranks lose their homes first, the next look for work.

13. **Working homes**: lit window with a glow, chimney smoke on about 40 % of them, flowers in the garden.
14. **Looking for work**: dark window, greyer walls and roof; after 12 weeks in that state the garden has weeds and the paint fades.
15. **Lost their home**: a dashed red outline with a FOR SALE sign.
16. **People you follow**: a pin over a fixed house (chosen from the household's id, near the middle of town) for each of the first four tracked households, the same four the Households panel shows by default, with the person's initial, coloured green when working, amber when looking, red when they lost their home or are out of work and unhappy (happiness below 0.2), and grey when they cannot work.
17. **Main Street, up close**: the shops on the 26 lots nearest the crossing, at street level with their names on hover, signs written out (HIRING, SALE, CLOSED, FOR LEASE, NEW), the crown, the town hall with its banner, treasury and queue, people walking the pavement (one per 15 staff, 2 to 24, 3 in warm-up weeks; hires and layoffs walk along it too), no cars and no clouds, and the same weather.

Coins show money moving: gold for spending (homes to shops, weighted by staff), green for pay (shops to working homes, estimated as staff × typical weekly pay), purple for taxes (to the town hall, `townHallIncome`), teal for help (town hall to homes looking for work, `familySupportPaid`). One coin per about $1,800 of that flow, counted at a steady notional one week per second rather than on the replay clock (which runs 8 weeks a second at 1× and is unchanged), so the coin stream is the same at every replay speed (0.5× to 4×); the count is divided by the number of towns over two, so busy screens stay calm, and a scene holds at most 160 coins. Floating signs and walkers live about 3 seconds of real time, so at 1× a sign outlasts its week by about 22 weeks of replay.

### 4.4 Cards

Pointing at a house, shop, the town hall, the bank or a pin shows a card; clicking keeps it open; clicking empty ground, or clicking or tapping the kept card itself, closes it (on a 390 px phone the card covers the place that was tapped, so without this nothing under it could be reached). Cards update as the weeks change. Contents follow mockup 08: house (state and weeks in it), shop (sector, co-op, staff, cash, state, this week's hires and layoffs, crown note, closing week), town hall (taxes in, help paid, saved or owed, queue), bank (loans out, gone bad this week), person (job or weeks out of work, savings, health, happiness, rent owed). The drawings are `aria-hidden`; screen-reader and keyboard users get the summary list in each town card plus the existing Businesses and Households panels.

## 5. Mood

`mood = 0.55 × jobs + 0.45 × happy`, where `jobs = clamp(1 − (peopleOutOfWorkPer100 − 5) / 40, 0, 1)` and `happy = clamp((happiness − 10) / 55, 0, 1)` (`happiness` is the curated 0–100 figure). Warm-up weeks (tick ≤ `WARMUP_TICKS`) use 0.62. Bands: **Thriving** ≥ 0.72, **Getting by** ≥ 0.5, **Struggling** ≥ 0.3, else **Hard times**. A missing figure counts as 0.6 for its part (`jobs` or `happy`). The visual mood eases towards its target (about 0.6 s) so weather drifts rather than snaps. The chip and the screen-reader summary name the band.

## 6. No layout shift

**Rule.** While the Run screen shows towns, changing the week (playing, stepping, scrubbing, following a live run) must not change the position or size of any marked box, nor the page's scroll height. Boxes may change only at phase changes: the first live week arriving, the end or lost panel appearing, opening the numbers sheet or Town hall drawer, Enlarge, resizing the window.

**Mechanisms.**
- Text that changes with the week sits in a box whose height is reserved (`StableText`): the lead sentence and the verdict reserve the height of the longest sentence they produce for any recorded week at the current width (measured off-screen with the same markup the box renders, once per text; re-measured on resize, when fonts load and when new weeks arrive). In a live run a later, longer sentence can grow the box once; it never shrinks while the run is shown.
- Labels that change length never change line count: fixed two-line label areas, `nowrap` values, fixed-width chips and buttons, ellipsis for rules text in headers, a timeline clock that keeps the width of the longest week label, and stat cards that reserve the lines their values may need. Where a text may wrap (household news, feed sentences) its line count follows that text's own width (container queries), not the window's, and every clamped text keeps its full wording in a `title`.
- The diorama and Main Street are SVGs with fixed aspect ratios.
- Lists that change with the week (businesses, households, feed, moments) have fixed row counts and fixed-height rows, with empty room held when there are fewer items: the Households panel always holds four card slots, the moments strip holds hidden copies of every row of chips the run produces, and the business list's expanded "See all" state is a fixed-height box that scrolls inside itself.

**Test.** `frontend-react/e2e/no-shift.spec.js` (Playwright, Chromium) opens `/?view=next&demo` and, for widths 390, 489, 560, 592, 600, 700, 768, 1024, 1280 and 1440, steps the scrubber through every recorded week (104), recording the bounding box of every element marked `data-stable`, every direct child of the Run screen's `<main>`, every card, and `document.scrollingElement.scrollHeight`. It fails if any value differs from week 1 by more than 0.5 px, if any text box marked `data-fits` is cut (its `scrollHeight` more than 1 px over its `clientHeight`), or if any box marked `data-reserve` is taller than the room reserved for it. Four more cases step every week at a fixed width: the first town's businesses all shown (1440), the second town enlarged (1440), the second town picked on Main Street (1440), and a place card kept open (390). Run with `npm run test:e2e` (starts its own Vite server on port 4179; first run `npx playwright install chromium`). Not wired into CI in this change.

## 7. Architecture

New code lives in `frontend-react/src/next/town/`, in three steps: pure model modules, React scenes that draw the model, and one motion loop per scene.

**Pure model modules** (no DOM):

- `geometry.js`: the isometric projection, the 16 × 16 tile layout (roads on row and column 7, town hall and bank blocks, shop lots nearest the crossing first, 100 house tiles, trees), painter's-order keys and per-tile slots, car and figure shapes, the Main Street layout and which house a followed household lives in.
- `mood.js`: mood, bands, season, colour ramps for sky, clouds, grass and shade.
- `houses.js`: each house's fixed rank from the town's seed, and every house's state and weeks-in-state for a week.
- `lots.js`: stable lot assignment. Replaying the arm's weeks in order, a newly seen firm takes the first free lot in priority order and keeps it until it leaves the closed list; lots are then reused. More firms than lots shows a "+N more" sign and is counted in the summary. A firm that overflowed stays undrawn for its life.
- `model.js`: `townAt(arm, tick)` builds everything the drawings need for one week from the arm (houses, shops with state, age, closed-for, lot and floors, richest shop, hall, bank, people pins, flows, traffic counts, this week's events, staff of every open firm). `townAt` itself is not memoised: each card computes it once per week with `useMemo` (the town card and Main Street each do), and the lot, house and first-seen caches it reads notice a week rewritten in place. Also `WEEKS` (the 3, 9, 8, 12 and 4 week thresholds of section 4) and `leased(shop)`.
- `cards.js`: card contents for each kind of place, and `cardSpot`, where a card sits beside the pointer.
- `motion.js`: the loop's pure helpers: coin pacing (`coinsDue`), which week changes are steps (`isStep`), this week's signs and walkers, easing, and the poses of smoke, flags, balloons, hooks, flicker, rain, signs and puffs.
- `shopShape.js` and `streetShape.js`: a shop's box and walls on the island and on Main Street (which shops stand on the street, how tall each is), shared by the drawing and by height easing.

**DOM helpers** (not pure; they touch the scene's DOM):

- `weather.js`: puts a mood and season on a scene as CSS variables, on the few parts marked `data-weather` (a variable on the svg root restyled every shape and cost 13 of 18 ms a week change).
- `nodes.js`: the scene colours, and the plain-DOM builders for figures, cars and sign pills that the motion loop adds without React.

**React scenes.** `Diorama.jsx` (the island) and `MainStreet.jsx` (the side view) each draw three stacked SVGs that share one viewBox and one box (`data-layer`):

- `back`: the sky gradient, the sun and the clouds.
- `world`: the ground, houses, trees, shops, town hall, treasury, queue, bank, the 256 per-tile slots that hold cars and walkers (so buildings in front hide them), the shade, window glows, signs and pins. Everything the viewer can point at is here. It carries no CSS animation or transition.
- `motion`: rain or snow, coins, pings and floating moments, above the world.

The back and motion layers are `pointer-events: none`. The parts are small memoised components (`homes.jsx`, `shops.jsx`, `civic.jsx`, `draw.jsx` for the island; `streetParts.jsx` for Main Street) so a week change touches only what changed. `TownCard.jsx` and `MainStreetCard.jsx` wrap the scenes with headers, facts, the screen-reader summary, the Enlarge button and the town picker; `PlaceCard.jsx` with `usePlaceCard.js` is the place card; `Legend.jsx` is the legend; `components/StableText.jsx` is the reserved-height text.

**Motion.** `useSceneMotion.js` runs one `requestAnimationFrame` loop per scene for everything that moves between weeks. It never sets React state per frame; it writes attributes on refs. It asks a `places` object, and nothing else, about where things are in that kind of picture: `islandPlaces.js` for the island, `streetPlaces.js` for Main Street. A `places` object says what to attach to in the drawing, where coins and signs start and land (house, shop door, roof, hall, bank), the traffic to draw, how to move a car or walker, a walking route, how shop heights map to the scene's units, where clouds drift (none on the street) and how coins arc. The loop drives `ambient.js` (clouds, rain or snow in seven groups of drops, chimney smoke, flags, balloons, crane hooks, flickering lights), `coins.js`, `moments.js` (signs, puffs, walkers, the bank flash, the hall ring) and `heights.js` (a shop easing to a new height: walls, scaffold poles, roof, sign, window rows). Between weeks, the mood eases (sky, sun, clouds, rain, shade, grass, glows) only while the run plays, and the world's colours step at most every 250 ms while the sky eases every frame. Paused means everything is still and the loop sleeps, so a paused town does not repaint; a scrub or jump clears what was moving and puts everything at the week drawn. With `prefers-reduced-motion`, weather and states still change but nothing travels, and smoke, flags and lights stand in the pose React drew.

**Why three layers.** Chromium gives every SVG shape with a running CSS animation its own compositor layer, and every shape painted after it that overlaps it needs one more. With smoke, rain, flicker, flags and pulses as CSS inside one svg per town the screen made 566 layers, and building them took 18 to 49 ms of main-thread time a frame. Splitting the scene, writing every movement from the loop and keeping CSS animation out of the world gives 13 layers.

Data changes outside `town/`: `data/session.js` keeps `health` and `happiness` on tracked subjects; `data/derive.js` gains `eventsAt(arm, tick)`, this week's events. No backend or wire change: every figure used is already in the lean frame (`curated`, `firms`, `firmsClosed`, `events`, `metrics.trackedSubjects`, `metrics.governmentPolicy`).

**Performance, measured.** Apple M4, headed Chromium on the GPU, 1440 × 900, production builds, `requestAnimationFrame` intervals over 5 seconds, medians of several runs. Two towns playing at 1× run at 60.0 fps (21.6 fps before the layers) and paused at 60.0 fps with no repaint; two towns plus Main Street at 59.9 to 60.0 fps; four towns at 58.4 fps (7.9 fps before) and four towns plus Main Street at 51.4 fps (the two four-town figures come from different measuring sessions; the street's cost is read only within one session, 54.7 to 51.4 fps); four towns at 4× about 44 fps. The scene loops cost a median 1.2 ms a frame with two towns at 1× and 1.9 ms with four towns at 4× (95th percentile 2.4 ms, largest 4.5 ms), inside the 4 ms budget; a whole-page week change is a median 4.0 ms of main-thread work with two towns and 7.9 ms with four, inside the 16 ms budget. Coin, car and walker counts are capped as above. Other hardware was not measured.

## 8. Testing

- Vitest (jsdom): geometry (lots near roads, no tile used twice, painter order), mood and seasons (band edges, warm-up), lot assignment (stable, reuse after leaving the closed list, overflow), model (house states and weeks-in-state, shop states and ages, richest shop, hall and bank figures, this week's hires and layoffs), cards, the motion helpers and the loop (moves while playing, still when paused, clears on a scrub, reduced motion), and component renders (classes reflect states, summary text, mood chip, enlarge, Main Street picker, place cards). Existing Run screen tests updated for the new markup. The whole-Run-screen test blocks carry a scoped 15 second timeout: they draw three scenes in jsdom and ran into the 5 second default at default parallelism on a loaded machine.
- Playwright (`npm run test:e2e`, 21 specs): the no-shift test above, place cards (every kind of place, by every edge, on Main Street, by click and by tap), and the layer checks (no CSS animation in a world layer while playing; the pointer passes through the back and motion layers).
- Manual: the recorded demo in a browser at desktop and phone widths; a small live run (two towns of 200 households, 30 weeks) to see live frames drive the diorama.

## 9. Out of scope

The night map; mood preview buttons; sound; pan and zoom; the AI mayor screen; backend or wire changes; wiring Playwright into CI; the classic dashboard.

## 10. Risks and open items

- The server keeps only some detailed events per week (`eventCounts.dropped`), so walking hires and layoffs under-show busy weeks. The counts in cards use what was sent.
- Four towns at once is the heaviest case; counts scale down with the number of towns. Four towns at 4× run at about 44 fps on the machine measured.
- At 390 px Main Street is about 358 × 101 px, so its figures are tiny and it reads as a picture only.
- In a live run the reserved height of the lead sentence can grow once when a longer sentence first appears.
- The generated OpenWiki does not cover `frontend-react/src/next/` yet (drift to report; refresh is due after this lands).

## Changes during the build (2026-10-02)

Each item says what this document first said.

- **Main Street comes after the legend (section 3).** First text: Main Street was item 3 and the legend item 4. Built: town cards, legend, Main Street, so the legend sits right under the drawings it explains and Main Street opens the part of the page about one town. Show both / Show all leaves Main Street on the town last chosen.
- **The shade is a plain translucent overlay (section 4.1.2).** First text: "a multiply overlay, at most 20 %". Built: `#151E32` at 0.9 × a shade value that reaches 0.2 (at most 18 % opaque). Mean colour at weeks 70, 100 and 102 is within 0.5/255 of the multiply blend. The blend could not reach the sky once the sky moved to its own layer, and cost nothing measurable either way.
- **A click or tap on a kept card closes it (section 4.4).** First text: only clicking empty ground closed a kept card. On a 390 px phone the card covers the place that was tapped.
- **Unmeasured town hall cash draws nothing (section 4.1.5).** First text: silent; a missing figure would have read as a $0 stack. Built: no stack and no IOU, and the facts row says "not measured".
- **FOR LEASE as built (section 4.2.9).** The text kept its words and was made exact: a closed shop is leased from its 8th week closed, shows FOR LEASE on the front of the building (the floating CLOSED sign stops) and drops to a one-floor shell, on the island (at most 14 units high) and on Main Street (40 units). Mockup 08's street kept closed shops at full height; the spec's "lower shell" was followed. On Main Street HIRING wins over NEW for a new shop that is also growing, since the street has no balloons.
- **Replay speed and pacing (section 4.3).** The demo replay keeps the 8 weeks a second at 1× it had before this work. The mockup played 1 week a second and its coin rate was tuned there, so coins count weeks at a steady notional 1 per second (`COIN_WEEKS_PER_SECOND`) and the stream is the same at every replay speed; counting the replay's own weeks gave about 200 coins a second in each town, always at the cap of 160. Floating signs and walkers keep the mockup's real-time lives (about 2.8 s and 2.6 to 3.2 s), with caps: 8 signs, 12 puffs, 24 walkers, 16 rings.
- **Architecture (section 7).** First text: one `requestAnimationFrame` loop per scene that pauses when the run is paused or scrubbed, and a shorter module list. Built: three stacked layers per scene, a `places` object that each kind of scene (the island, Main Street) plugs into the loop, and the module list now in `town/`, after the first version (one svg per town, movement as CSS animation) ran at 21.6 fps with two towns and 7.9 with four where the old screen ran at 60. Accepted trade-offs: cars, walkers, smoke, flags, balloons, hooks and flicker move by script in place in the world layer so buildings in front still hide them; paused means everything is still (smoke, flags, rain and the rest used to loop as CSS while paused); state changes of houses, glows, snow and leaves are instant instead of fading; a run's last week counts as a step, so its moments are not cut.
- **Main Street's people.** First text: "people walking". Mockup 08's street drew none (a bug left the staff count undefined). Built: strollers on the pavement (one per 15 staff, 2 to 24, 3 in warm-up weeks), and people hired or laid off walk along the pavement from the shop door, at most 120 units, then fade.
- **Pins have a fourth colour (section 4.3.16).** First text: green, amber, red. Built: also grey for a person who cannot work and is doing fine; red covers a lost home and out of work and unhappy.
- **"How to read this" copy (section 3).** First text: the panel is unchanged. Two of its sentences described the deleted flat drawing (amber, red and green houses; a flag and a cross on Main street) and were rewritten for the diorama.
- **No layout shift (section 6).** The rule stands; the mechanisms and test grew as the test found shifts the first text did not list: stat cards at 1280 px, the timeline clock at 700 px, the lead at 592 px (Chromium rounds each inline box's text width to 1/64 px, so the lead is measured with the markup it renders), household news and feed lines at 560 to 600 px (line counts follow the text's own width), the business list with "See all" open, and a Households panel with fewer than four cards. The test widths went from four to ten, and it also checks that no text is cut and no reserved box outgrows its room.
- **Other differences from mockup 08 (sections 4.1 and 4.3).** The treasury amount sits beside the coin stack with a light halo instead of above it, because shops painted in front covered it. The town hall's banner text is fitted to the façade when the label is long. Main Street's sky takes the shared scene palette, so it is slightly cooler than the mockup's own; its shops are spread evenly along the street instead of at a fixed 35-unit pitch; its coin stack has one coin per $10,000 (the island's has one per $12,000); its pins sit on the model's houses rather than the mockup's fixed ones; and its floor windows sit 2 units lower.
