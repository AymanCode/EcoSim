# EcoSim Dashboard

React/Vite frontends for the EcoSim simulation. This package holds two apps:

- **Town Run screen (current).** `src/next/`, opened at `/?view=next`. New UI work goes here.
- **Classic dashboard (legacy, frozen).** `src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/`, `src/index.css`, opened at `/`. It is still the URL default, but it gets no new features unless the owner asks.

`src/next/pickView.js` picks the app. See "Current and legacy surfaces" in the repository's `AGENTS.md`.

## Recommended Startup

Run the full stack from the repository root:

```bash
docker compose up --build -d --wait
```

Open `http://localhost:5173`.

## Frontend-Only Development

Use Node.js 22.22.2 or newer within the 22.x release line. Docker and CI both use Node 22.

Start the backend first:

```bash
python -m uvicorn backend.server:app --reload --port 8002
```

Then run Vite:

```bash
cd frontend-react
npm ci
npm run dev
```

Vite proxies `/ws` and `/health` to `http://127.0.0.1:8002`.

## Demo Recordings

**Watch the example** and `/?view=next&demo` play two recorded towns from `public/demo/town-a.jsonl` and `public/demo/town-b.jsonl`, with no backend. To record them again, run from the repository root:

```bash
ECOSIM_ENABLE_WAREHOUSE=0 python frontend-react/scripts/record_session.py --households 500 --ticks 104 --tracked 12 --seed 1337 --firms 5 --experiment demo-minwage --arm "Town A" --arms 2 --owner demo --out frontend-react/public/demo/town-a.jsonl
ECOSIM_ENABLE_WAREHOUSE=0 python frontend-react/scripts/record_session.py --households 500 --ticks 104 --tracked 12 --seed 1337 --firms 5 --experiment demo-minwage --arm "Town B" --arms 2 --owner demo --initial-policy '{"minimum_wage_policy":"high"}' --out frontend-react/public/demo/town-b.jsonl
```

Keep each file under 3 MB; if one is larger, lower `--households` to 300.

## Checks

```bash
npm ci
npm run lint
npm run test
npm run build
```

Implementation details for the Run screen live in [`../docs/FRONTEND.md`](../docs/FRONTEND.md).

## Browser Checks

```bash
npx playwright install chromium   # first run on a machine only
npm run test:e2e
```

`npm run test:e2e` runs the Playwright specs in `e2e/` in Chromium, one worker, in about two minutes. It starts its own Vite dev server on port 4179 (through `npx --yes node@22`, so it follows the Node 22 rule above) and plays the recorded demo at `/?view=next&demo`, so it needs no backend and no other server running. It does need the network: the Run screen's two fonts come from Google Fonts, and every spec waits until both are loaded before measuring (`e2e/fonts.js`), failing after 30 s if they never arrive, because a font that lands in the middle of a check reflows text. `npm run test` skips `e2e/`. The specs check what jsdom cannot measure:

- `no-shift.spec.js`: stepping through every week of the demo at ten widths from 390 to 1440 px, plus a few extra cases (all businesses shown, a town enlarged, a Main Street town picked, a place card kept open), no marked box moves or resizes and the page height stays put (0.5 px tolerance), no clamped text is cut, and no reserved-height box outgrows its reservation. This is the Run screen's no-layout-shift rule.
- `place-cards.spec.js`: pointing at or tapping each kind of place shows an overlay card that takes no layout space. On phones, place cards may overhang below the drawing.
- `live-review.spec.js`: incremental frames and command-error notices through the real live controller, scrubbing across a historical policy change, and three-/four-town stat cards with the Town hall drawer open. It mocks the sockets, so it needs no backend.
- `town-layers.spec.js`: the town drawings' world layers run no CSS animation while the demo plays, and the pointer passes through the sky and motion layers to the world.
- `fonts.spec.js`: with every Google Fonts request held back 1.5 s, the shared font wait still returns only once every face of the Run screen's two fonts is loaded.

It is not wired into CI. It prints a plain list of results; a failing run leaves its artifacts in `test-results/`, which is gitignored.

## The Run Screen's Towns

The new Run screen's town drawings (`?view=next`) live in `src/next/town/`, in three steps. Pure model modules (`geometry.js`, `mood.js`, `houses.js`, `lots.js`, `model.js` with `townAt(arm, tick)`, `cards.js`, `motion.js`, `streetShape.js`) turn one town's recorded weeks into everything a drawing needs for the week on the clock, without touching the DOM. React scenes (`Diorama.jsx` for the island, `MainStreet.jsx` for the side view, with their parts in `homes.jsx`, `shops.jsx`, `civic.jsx` and `streetParts.jsx`, inside `TownCard.jsx` and `MainStreetCard.jsx`) draw that model as three stacked SVGs that share one viewBox: `back` (sky, sun, clouds), `world` (ground, buildings, signs, pins, with no CSS animation or transition) and `motion` (rain or snow, coins, pings, floating signs). Anything that moves between weeks is written by one `requestAnimationFrame` loop per scene (`useSceneMotion.js`, with `ambient.js`, `coins.js`, `moments.js` and `heights.js`), which asks a `places` object (`islandPlaces.js` or `streetPlaces.js`) where things are, writes attributes on refs, never sets React state per frame, and sleeps while the run is paused. The layers exist because Chromium gives every SVG shape with a running CSS animation a compositor layer of its own: with the motion inside one SVG per town the screen made 566 layers and ran at about 22 fps with two towns, and split this way it makes 13 and holds 60. Boxes that must not change size as the week changes carry `data-stable` so the e2e test watches them.
