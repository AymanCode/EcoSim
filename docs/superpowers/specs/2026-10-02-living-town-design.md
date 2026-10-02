# Living town: the diorama Run screen

Date: 2026-10-02. Branch: `feat/living-town` (from `origin/main` at 121428f). Mockups: `2026-10-02-mockups/07-living-town-styles.html` (three drawing styles) and `2026-10-02-mockups/08-diorama-details.html` (the chosen style with every detail). The mockups play the recorded demo; `extract_living_town_data.mjs` rebuilds their data from `frontend-react/public/demo/`.

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
2. **Town cards**, one per town: header (colour chip, name, rules in force, mood chip, Enlarge button), the diorama, and a facts row (out of work, typical weekly pay, shops open with how many struggling, town hall money). Grid: one town full width; two side by side; three or four in a 2 × 2 grid. Under 1100 px wide the cards stack. **Enlarge** shows only that town at full width and switches Main Street to it; **Show both/all** returns.
3. **Main Street, up close**: the side-view street of one town, with a town picker (segmented control) when there are two or more towns.
4. One shared legend for the drawings.
5. Per-town columns with the existing **Businesses** list and **Households** cards (kept: they are the browsable, keyboard-reachable panels newcomers liked).
6. The existing story chart, verdict, stat cards, feed and "How to read this", unchanged except for section 6.

The old `components/Town.jsx` drawing is replaced. Its screen-reader summary (`.nx-sr` list) and facts move into the town card. The page keeps the Run screen's existing fonts and `--nx-*` colour tokens (`next.css`); only the drawings use the mockup's scene palette.

## 4. What the drawings show

Every detail is driven by the arm's data at the week on the clock. "This week" means the tick being shown.

### 4.1 The town

1. **Weather follows the mood** (section 5): warm sky and sun when thriving; more and greyer clouds as the mood falls; rain in hard times. In winter the rain is snow, and light snow falls in any mood.
2. **Light and grass**: below "getting by" the scene dims (a multiply overlay, at most 20 %) and the grass dries towards olive; lit windows glow more strongly the darker it gets, so working homes stand out.
3. **Seasons** by week of the year (52-week years): spring weeks 10–22 (some trees blossom), summer 23–35, autumn 36–48 (orange trees), winter 49–52 and 1–9 (bare trees, snow on roofs and pine tips).
4. **Traffic**: cars on the two roads, one per $5,000 of weekly sales (`salesExceptRentThisWeek`), 0–7; people on the pavements in proportion to the share of homes with work, 1–14 (4 during warm-up).
5. **Town hall**: a coin stack sized by `townHallCash` with the amount, or a red IOU slip "owes $Xk" when negative; a queue of people outside, one per $2,800 of `familySupportPaid` this week (0–9); a banner on the façade naming the town's changed rule (short label per lever, "NEW RULES" when several); the existing pulse ring for four weeks after a rule change.
6. **Bank**: a stack of loan papers, one per 55 `bankActiveLoans` (0–7); when `bankDefaultAmountThisTick` is at least $500, the bank flashes red and a "Bad loans $Xk" sign rises.

### 4.2 Businesses

Shops stand on the 50 lots along the two roads (nearest the crossing first), coloured by sector, one floor per 9 staff (1–6 floors), height easing to the new value when staff changes.

7. **Growing**: a tower crane on the roof and a HIRING sign.
8. **Struggling**: SALE painted on the shop window, flickering windows, an amber flag.
9. **Closed**: boarded up with a CLOSED sign for 8 weeks, then a FOR LEASE sign on the building (no floating sign) and a lower shell; the lot empties when the firm leaves the server's closed list (about a year).
10. **New**: scaffolding for its first 3 weeks, then balloons and a NEW sign until week 9.
11. **A gold crown** on the richest open shop by cash, not counting the town co-ops (`isBaseline`).
12. **Moments in the picture**, only while playing forward one week at a time (never when scrubbing or jumping): a laid-off worker walks from the shop to a dark home carrying a box (up to 2 per shop, 6 per week); a new hire walks from a lit home to the shop; floating signs "Closed" (with a dust puff), "Opened!", "−N jobs" and "+N jobs" (N ≥ 2), and the bad-loans sign, at most 4 per town per week.

### 4.3 Homes and people

The 100 houses each stand for `householdsTotal / 100` households, as today. Each house keeps a fixed spot and a fixed rank from the town's seed, so matched towns line up house for house; the lowest ranks lose their homes first, the next look for work.

13. **Working homes**: lit window with a glow, chimney smoke on about 40 % of them, flowers in the garden.
14. **Looking for work**: dark window, greyer walls and roof; after 12 weeks in that state the garden has weeds and the paint fades.
15. **Lost their home**: a dashed red outline with a FOR SALE sign.
16. **People you follow**: a pin over a fixed house (chosen from the household's id, near the middle of town) for each of the first four tracked households, the same four the Households panel shows by default, with the person's initial, coloured green when working, amber when looking, red when also unhappy (happiness below 0.2).
17. **Main Street, up close**: the shops on the 26 lots nearest the crossing, at street level with their names on hover, signs written out (HIRING, SALE, CLOSED, FOR LEASE, NEW), the crown, the town hall with its banner, treasury and queue, people walking, and the same weather.

Coins show money moving: gold for spending (homes to shops, weighted by staff), green for pay (shops to working homes, estimated as staff × typical weekly pay), purple for taxes (to the town hall, `townHallIncome`), teal for help (town hall to homes looking for work, `familySupportPaid`). One coin per about $1,800 at 1× speed; the rate is divided by the speed and by the number of towns over two, so busy screens stay calm.

### 4.4 Cards

Pointing at a house, shop, the town hall, the bank or a pin shows a card; clicking keeps it open; clicking empty ground closes it. Cards update as the weeks change. Contents follow mockup 08: house (state and weeks in it), shop (sector, co-op, staff, cash, state, this week's hires and layoffs, crown note, closing week), town hall (taxes in, help paid, saved or owed, queue), bank (loans out, gone bad this week), person (job or weeks out of work, savings, health, happiness, rent owed). The drawings are `aria-hidden`; screen-reader and keyboard users get the summary list in each town card plus the existing Businesses and Households panels.

## 5. Mood

`mood = 0.55 × jobs + 0.45 × happy`, where `jobs = clamp(1 − (peopleOutOfWorkPer100 − 5) / 40, 0, 1)` and `happy = clamp((happiness − 10) / 55, 0, 1)` (`happiness` is the curated 0–100 figure). Warm-up weeks (tick ≤ `WARMUP_TICKS`) use 0.62. Bands: **Thriving** ≥ 0.72, **Getting by** ≥ 0.5, **Struggling** ≥ 0.3, else **Hard times**. A missing figure counts as 0.6 for its part (`jobs` or `happy`). The visual mood eases towards its target (about 0.6 s) so weather drifts rather than snaps. The chip and the screen-reader summary name the band.

## 6. No layout shift

**Rule.** While the Run screen shows towns, changing the week (playing, stepping, scrubbing, following a live run) must not change the position or size of any marked box, nor the page's scroll height. Boxes may change only at phase changes: the first live week arriving, the end or lost panel appearing, opening the numbers sheet or Town hall drawer, Enlarge, resizing the window.

**Mechanisms.**
- Text that changes with the week sits in a box whose height is reserved: the lead sentence and the verdict reserve the height of the longest sentence they produce for any recorded week at the current width (measured off-screen; re-measured on resize and when new weeks arrive). In a live run a later, longer sentence can grow the box once; it never shrinks while the run is shown.
- Labels that change length never change line count: fixed two-line label areas, `nowrap` values, fixed-width chips and buttons, ellipsis for rules text in headers.
- The diorama and Main Street are SVGs with fixed aspect ratios.
- Lists that change with the week (businesses, households, feed) have fixed row counts and single-line rows (ellipsis), with empty rows held when there are fewer items.

**Test.** `frontend-react/e2e/no-shift.spec.js` (Playwright, Chromium) opens `/?view=next&demo`, pauses, and for widths 390, 489, 1024 and 1440 steps the scrubber through every recorded week, recording the bounding box of every element marked `data-stable` and `document.scrollingElement.scrollHeight`. It fails if any value differs from week 1 by more than 0.5 px. Run with `npm run test:e2e` (starts its own Vite server). Not wired into CI in this change.

## 7. Architecture

New code lives in `frontend-react/src/next/town/`:

- `geometry.js`: the isometric projection, the 16 × 16 tile layout (roads on row and column 7, town hall and bank blocks, shop lots nearest the crossing first, 100 house tiles, trees), painter's-order keys and per-tile slots, car and figure shapes, the Main Street layout. Pure.
- `mood.js`: mood, bands, season, colour ramps for sky, clouds, grass and shade. Pure.
- `model.js`: `townAt(arm, tick)` builds everything the drawings need for one week from the arm (houses with state and weeks-in-state, shops with state, age, closed-for, lot and floors, richest shop, hall, bank, people pins, flows, traffic counts, this week's events). Memoised per arm and tick. Pure.
- `lots.js`: stable lot assignment. Replaying the arm's weeks in order, a newly seen firm takes the first free lot in priority order and keeps it until it leaves the closed list; lots are then reused. More firms than lots shows a "+N more" sign and is counted in the summary.
- `cards.js`: card contents for each kind of place. Pure.
- `Diorama.jsx`, `MainStreet.jsx`: React render the structure (ground, houses, trees, shops, civic buildings, signs, pins), memoised so a week change touches only what changed.
- `useSceneMotion.js`: one `requestAnimationFrame` loop per scene for things that move between weeks: mood easing (sky, sun, clouds, rain or snow, shade, grass, glows), shop height easing, coins, cars and walkers (moved between per-tile slot groups so buildings in front hide them), hire and layoff walkers, floating signs, puffs and flashes. It writes to refs; it never sets React state per frame. It pauses when the run is paused or scrubbed and when `prefers-reduced-motion` is set (then weather and states still change, but nothing travels).
- `TownCard.jsx`, `MainStreetCard.jsx`, `PlaceCard.jsx`, `StableText.jsx` (reserved-height text), `Legend.jsx`.

Data changes outside `town/`: `data/session.js` keeps `health` and `happiness` on tracked subjects; `data/derive.js` gains small helpers for this week's events and per-firm hire and layoff counts if they do not exist. No backend or wire change: every figure used is already in the lean frame (`curated`, `firms`, `firmsClosed`, `events`, `metrics.trackedSubjects`, `metrics.governmentPolicy`).

Performance budget: with four towns at 4× on a laptop, the motion loop stays under 4 ms per frame and a week change under 16 ms. Coin, car and walker counts are capped as above.

## 8. Testing

- Vitest (jsdom): geometry (lots near roads, no tile used twice, painter order), mood and seasons (band edges, warm-up), lot assignment (stable, reuse after leaving the closed list, overflow), model (house states and weeks-in-state, shop states and ages, richest shop, hall and bank figures, this week's hires and layoffs), cards, and component renders (classes reflect states, summary text, mood chip, enlarge, Main Street picker). Existing Run screen tests updated for the new markup.
- Playwright: the no-shift test above.
- Manual: the recorded demo in a browser at desktop and phone widths; a small live run (two towns of 200 households, 30 weeks) to see live frames drive the diorama.

## 9. Out of scope

The night map; mood preview buttons; sound; pan and zoom; the AI mayor screen; backend or wire changes; wiring Playwright into CI; the classic dashboard.

## 10. Risks and open items

- The server keeps only some detailed events per week (`eventCounts.dropped`), so walking hires and layoffs under-show busy weeks. The counts in cards use what was sent.
- Four towns at once is the heaviest case; counts scale down with the number of towns.
- In a live run the reserved height of the lead sentence can grow once when a longer sentence first appears.
- The generated OpenWiki does not cover `frontend-react/src/next/` yet (drift to report; refresh is due after this lands).
