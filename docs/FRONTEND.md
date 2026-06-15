# Frontend Dashboard

The EcoSim frontend is a React/Vite dashboard for launching, controlling, and inspecting live simulation runs.

## Stack

- React 19
- Vite
- Recharts
- Tailwind CSS
- lucide-react icons
- Custom canvas-based neural visualizations
- WebSocket transport through `/ws`

The application entry point is [`frontend-react/src/App.jsx`](../frontend-react/src/App.jsx). Vite proxies `/ws` and `/health` to the backend on port `8002` during local development. The production Docker image serves the built app through Nginx and proxies the same paths to the backend service.

## Running Locally

Start the backend first:

```bash
python -m uvicorn backend.server:app --reload --port 8002
```

Then start Vite:

```bash
cd frontend-react
npm install
npm run dev
```

Open `http://localhost:5173`.

For the full Docker stack, run `./start.sh` or `.\start.ps1` from the repository root.

## Views

The sidebar currently exposes seven views:

| View | Route state | Purpose |
|---|---|---|
| Config | `CONFIG` | Launch profile, policy defaults, stabilizer toggles, backend status |
| Command | `DASHBOARD` | Macro metrics, stress signals, sector status, live chart history |
| Population | `SUBJECTS` | Tracked household drill-down, wage reasoning, health, morale, traits, history |
| Markets | `FIRMS` | Sector rollups, tracked firm detail, prices, wages, inventory, revenue, profit |
| Finance | `FINANCE` | Government debt/fiscal balance, bank and government-backed loan telemetry |
| Government | `GOVERNMENT` | Manual policy controls, AI Policy Engine toggle, fiscal flow, decision history |
| Logs | `LOGS` | Buffered event stream with filters and detail inspection |

Only Config is available before initialization. Other views unlock after a successful `SETUP`.

## Config View

Pre-launch controls:

- `Population Scale`: frontend slider range `100` to `10000`; backend accepts `3` to `100000`
- `Policy Assistant`: maps to `enable_llm_government`
- `Wage Tax`: setup `wage_tax`
- `Corporate Profit Tax`: setup `profit_tax`
- `Minimum Wage Floor`: runtime preview mapped to `minimum_wage_policy`
- `Unemployment Benefits`: runtime preview mapped to `benefit_level`
- `Infrastructure` and `Social Spending`
- `Disable automatic stabilizers` with agent options for households, firms, government, or all agents

After initialization, policy controls queue `CONFIG` updates. Changes are debounced client-side and applied by the server at safe tick boundaries.

## Command View

The Command view is the main run monitor. It shows:

- GDP, net worth, fiscal flow, unemployment, employment, wage, happiness, health, and inequality metrics
- population stress and system advisory cards
- sector status and firm pressure
- finance summary, including government-backed loan count
- policy assistant summary
- chart histories for GDP, wages, unemployment, health, happiness, prices, supply, fiscal balance, firm count, net worth, and wealth distribution where available

The server caches some aggregate metrics on a stride for performance, so chart payloads are compact rather than full raw history.

## Population View

The Population view inspects the tracked household subset sent in each tick payload.

Displayed state includes:

- identity, age, health, state, medical status
- employer, wage, expected wage, reservation wage, unemployment duration
- expected-wage reasoning tags and pressure components
- skills, morale, happiness, cash, net worth, medical debt
- food, housing, and healthcare need/status
- personality traits and per-household history charts
- canvas avatar visualization via `NeuralAvatar`

The tracked subset is selected server-side. It is not the full population.

## Markets View

The Markets view displays sector-level and tracked-firm state:

- total firms, employees, average wage offer, struggling firms
- Food, Housing, Services, and Healthcare sector rollups
- top cash positions and top employers
- selected tracked-firm detail
- price, wage offer, inventory, quality, employees, revenue, profit, and history charts
- canvas firm visualization via `NeuralBuilding`

Tracked firms are selected by the server to highlight top private firms plus baseline firms where available.

## Finance View

The Finance view surfaces credit and fiscal telemetry:

- government-backed loan count
- government debt and fiscal balance history
- active loan exposure
- bank/credit related metrics from the backend payload when available
- liquidity visualization through `FinanceLiquidityHologram`

The bank itself remains a backend simulation actor; the frontend displays selected aggregate signals rather than raw loan records.

## Government View

The Government view is the live policy console.

Controls include:

- AI Policy Engine toggle
- wage tax and profit tax
- benefit level
- minimum wage policy
- public works
- sector subsidy target and level
- infrastructure, technology, and social spending
- price stabilization target and level
- rent stabilization level
- bailout policy, target, and budget

The view also shows:

- current GDP, unemployment, happiness, and net fiscal flow
- fiscal revenue, transfers, investments, active loans, government cash, and debt
- current LLM status, provider/model where available, snapshot tick, applied tick, accepted/rejected changes
- recent manual and LLM policy actions
- canvas government visualization via `NeuralGovernment`

Manual controls remain available when the AI Policy Engine is inactive or provider setup is missing.

## Logs View

The Logs view presents the rolling log buffer from server tick payloads plus frontend lifecycle events.

Features:

- auto-scroll toggle
- severity/type filters
- event count and error count
- selected event detail
- buffered list capped client-side

## WebSocket Contract

Endpoint:

```text
ws://localhost:8002/ws
```

Commands sent by the frontend:

| Command | Payload shape |
|---|---|
| `SETUP` | `{ command: "SETUP", config: { num_households, num_firms, wage_tax, profit_tax, enable_llm_government, disable_stabilizers, disabled_agents } }` |
| `START` | `{ command: "START" }` |
| `STOP` | `{ command: "STOP" }` |
| `RESET` | `{ command: "RESET" }` |
| `CONFIG` | `{ command: "CONFIG", config: { ...runtimeControls } }` |
| `STABILIZERS` | `{ command: "STABILIZERS", disable_stabilizers, disabled_agents }` |

Important server messages:

| Message | Meaning |
|---|---|
| `SETUP_COMPLETE` | Economy initialized |
| `STARTED` | Tick loop running |
| `STOPPED` | Tick loop paused |
| `RESET` | Run reset to pre-initialization state |
| `STABILIZERS_UPDATED` | Stabilizer state acknowledged |
| Tick payload | Object with `tick`, `metrics`, `firm_stats`, and `logs` |

## Runtime Config Mapping

The frontend sends camelCase runtime fields. The server maps them to policy-schema fields before applying:

| Frontend field | Backend policy field |
|---|---|
| `wageTax` | `wage_tax_rate` |
| `profitTax` | `profit_tax_rate` |
| `investmentTax` | `investment_tax_rate` |
| `benefitLevel` | `benefit_level` |
| `publicWorks` | `public_works` |
| `minimumWagePolicy` | `minimum_wage_policy` |
| `minimumWage` | mapped to `minimum_wage_policy` |
| `unemploymentBenefitRate` | mapped to `benefit_level` |
| `sectorSubsidyTarget` | `sector_subsidy_target` |
| `sectorSubsidyLevel` | `sector_subsidy_level` |
| `infrastructureSpending` | `infrastructure_spending` |
| `technologySpending` | `technology_spending` |
| `socialSpending` | `social_spending` |
| `priceStabilizationTarget` | `price_stabilization_target` |
| `priceStabilizationLevel` | `price_stabilization_level` |
| `rentStabilizationLevel` | `rent_stabilization_level` |
| `bailoutPolicy` | `bailout_policy` |
| `bailoutTarget` | `bailout_target` |
| `bailoutBudget` | `bailout_budget` |

Legacy-style UI fields for UBI, wealth tax, target inflation, and birth rate are still accepted by the server as direct government fields and recorded as policy actions when changed.

## Visual Components

| Component | File | Represents |
|---|---|---|
| `NeuralAvatar` | [`src/NeuralAvatar.jsx`](../frontend-react/src/NeuralAvatar.jsx) | Household agent state |
| `NeuralBuilding` | [`src/NeuralBuilding.jsx`](../frontend-react/src/NeuralBuilding.jsx) | Firm and market state |
| `NeuralGovernment` | [`src/NeuralGovernment.jsx`](../frontend-react/src/NeuralGovernment.jsx) | Government and policy engine state |

These are canvas animations managed with React effects and refs. They are presentation components only; simulation state comes from the WebSocket payload.

## Build Checks

```bash
cd frontend-react
npm ci
npm run lint
npm run build
```
