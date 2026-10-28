# Frontend

The frontend is a React 19 and Vite package in `frontend-react/`. It holds two apps that share one entry point:

| App | Status | Opens at | Source |
|---|---|---|---|
| Town Run screen | Current | `/?view=next` | `src/next/` |
| Classic dashboard | Legacy, frozen | `/` | `src/App.jsx`, `src/screens/`, `src/shell/`, `src/ui/`, `src/charts/`, `src/index.css` |

[`src/main.jsx`](../frontend-react/src/main.jsx) asks [`src/next/pickView.js`](../frontend-react/src/next/pickView.js) which app to open and loads only that app's code, styles and fonts. The classic dashboard is still the URL default but receives no new features. The rest of this page describes the town Run screen.

## Running Locally

Use Node 22.22.2 or newer within the 22.x line. Start the backend, then Vite:

```bash
python -m uvicorn backend.server:app --reload --port 8002
cd frontend-react
npm ci
npm run dev
```

Open `http://localhost:5173/?view=next`. Vite proxies `/ws` and `/health` to the backend on port `8002`. The Docker image serves the production build through Nginx and proxies the same paths.

`/?view=next&demo` plays two recorded towns from `public/demo/` without a backend. The commands that record them are in the [frontend README](../frontend-react/README.md#demo-recordings).

## Screens

| Screen | Purpose |
|---|---|
| Set up | Choose the kind of experiment, a question or custom rules for each town, households per town, run length and town number (seed) |
| Run | Live towns side by side: a headline comparison, a drawn town per arm, key figures, household and business cards, a story chart, and recent events, all on one shared week clock |
| Town hall | A drawer that changes one town's rules during the run; changes take effect from that town's next week |
| All the numbers | A sheet over the Run screen with the short answer, output and wellbeing, and every compared figure with its history |
| End | The verdict at the horizon, with options to add a year or set up another question |

Set up offers three kinds of experiment:

- **Compare policies.** Two to four towns share the same households, seed, horizon and payment sequence, and only their rules differ. Each town gets an equal share of 10,000 households.
- **Free play.** One town with every rule available.
- **Test an AI mayor.** Shown, but disabled until a model is connected.

## Data Flow

```
Set up ──plan──▶ live/plan.js ──SETUP configs──▶ live/experiment.js ──one WebSocket per town──▶ backend
                                                        │
                                       frame-2 messages ▼
                                  data/session.js (one "arm" per town)
                                                        │
                       data/derive.js, narration.js, numbers/compare.js, town/model.js
                                                        │
                                                        ▼
                                          RunScreen, NumbersSheet, TownCard
```

- **Plan to configs.** [`live/plan.js`](../frontend-react/src/next/live/plan.js) turns the Set up plan into one `SETUP` config per town. Every town sends `payment_sequence: "income_first"` and `frame_profile: "lean"`, with the town's 17 policy levers as its initial policy.
- **Live experiment.** [`live/experiment.js`](../frontend-react/src/next/live/experiment.js) opens one WebSocket per town and sends `SETUP`, `START`, `STOP`, `CONFIG`, `TRACK`, `EXTEND` and `FINISH`. It holds faster towns so all towns advance together, and publishes one plain state object (`phase`, `arms`, `liveTick`, `towns`, `error`). [`live/useExperiment.js`](../frontend-react/src/next/live/useExperiment.js) throttles that state into React and opens sockets only from a user action. The message contract is in [WEBSOCKET_PROTOCOL.md](WEBSOCKET_PROTOCOL.md).
- **Arms.** [`data/session.js`](../frontend-react/src/next/data/session.js) copies what the screens read out of each frame into an append-only arm: every curated figure as a series aligned to ticks, the open firms, the tracked households, recent closures, events and policy changes. Raw frames are not kept. Recorded demo sessions go through the same path.
- **Clock.** [`live/useLiveClock.js`](../frontend-react/src/next/live/useLiveClock.js) follows the lowest week every town has reached until the viewer scrubs back; the recorded demo uses [`useReplay.js`](../frontend-react/src/next/useReplay.js).
- **Reading.** [`data/derive.js`](../frontend-react/src/next/data/derive.js) aligns towns by tick and reads values as of a week. [`narration.js`](../frontend-react/src/next/narration.js) turns numbers and events into sentences. [`numbers/compare.js`](../frontend-react/src/next/numbers/compare.js) resolves the compared metrics for the numbers sheet.
- **Rule checks.** [`policyRules.js`](../frontend-react/src/next/policyRules.js) ports the backend's lever group rules, so Set up and the Town hall stop a combination the server would refuse.

## Source Layout

| Path | Owns |
|---|---|
| `NextApp.jsx`, `pickScreen.js` | App shell; opens Set up, or the recorded demo when the query has `demo` |
| `setup/` | Set up screen and its state (`useSetup.js`) |
| `RunScreen.jsx`, `components/` | Run screen: horizon bar, story chart, stat cards, business list, household cards, feed, Town hall, end and lost-connection panels |
| `numbers/` | All the numbers sheet: answer card, number rows with history, wealth ladder, hires and layoffs, openings and closures, loans written off, rules in force |
| `town/` | Town drawings (see below) |
| `live/` | WebSocket experiment, React hooks, endpoint and session ids |
| `data/` | Arm building and read-side helpers |
| `catalog.js` | All user-facing wording and metric definitions |
| `narration.js`, `names.js` | Sentences from numbers and events; stable household names |
| `next.css`, `numbers/*.css`, `town/town.css` | Styles, scoped under `.nx` |

All copy lives in `catalog.js` or `narration.js`, so wording changes do not touch components.

## Town Drawings

`src/next/town/` draws each town as an isometric island (`Diorama.jsx`) or a Main Street side view (`MainStreet.jsx`), in three layers:

- **Model.** Pure modules (`model.js` with `townAt(arm, tick)`, `geometry.js`, `houses.js`, `lots.js`, `mood.js`, `cards.js`) turn one town's recorded weeks into everything a drawing needs for the week on the clock, without touching the DOM.
- **Scenes.** React components draw that model as three stacked SVGs sharing one viewBox: `back` (sky, sun, clouds), `world` (ground, buildings, signs, pins, with no CSS animation) and `motion` (weather, coins, pings, floating signs).
- **Motion.** One `requestAnimationFrame` loop per scene (`useSceneMotion.js`) writes attributes on refs, never sets React state per frame, and sleeps while the run is paused.

The split keeps Chromium's compositor layers low: two towns render with 13 layers and hold 60 fps. More detail is in the [frontend README](../frontend-react/README.md#the-run-screens-towns).

## Checks

```bash
cd frontend-react
npm run lint
npm run test       # Vitest unit and component tests (jsdom)
npm run build
npm run test:e2e   # Playwright in Chromium against the recorded demo
```

The Playwright specs in `e2e/` cover what jsdom cannot measure: no layout shift while stepping through every week at ten widths, place cards, town drawing layers, fonts, and a live review run. See the [frontend README](../frontend-react/README.md#browser-checks).

## Classic Dashboard

The classic dashboard ([`src/App.jsx`](../frontend-react/src/App.jsx)) is a seven-view research console (Config, Command, Population, Markets, Finance, Government, Logs) built with Recharts, Tailwind and the token stylesheet in `src/theme/tokens.css`. It asks for the full `frame_profile: "legacy"` frame. It is kept working but frozen: no new features, panels or rows.
