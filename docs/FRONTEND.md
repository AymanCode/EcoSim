# EcoSim Frontend Dashboard

What the React dashboard displays, how to use it, and how it communicates with the backend.

---

## Neural Visualization Components

The frontend uses three WebGL-canvas-based neural visualization components that render animated 3D wireframe structures representing different agent types. All components use `React`, `useEffect`, and `useRef` to manage canvas rendering with `requestAnimationFrame` for smooth animation.

### NeuralAvatar (`NeuralAvatar.jsx`)

Renders a holographic humanoid figure representing a household agent.

**Props:**
- `active` (bool, default `true`) — Whether the animation is active
- `mood` (string, default `'neutral'`) — Mood state: `'happy'` or `'neutral'`, affects color palette
- `variant` (string, default `'human'`) — Reserved for future variant support

**Structure:**
- Head: 25 points in spherical distribution
- Body: 45 points in cylindrical distribution
- Arms: 2 × ~11 points along Y-axis with X/Z offset
- Legs: 2 × ~10 points along Y-axis with X/Z offset

**Visual:**
- Teal/cyan color palette (`#0d9488`, `#2dd4bf`)
- Connection lines between nearby points (radius: 16 units)
- Rotation speed: 0.008 radians/frame
- Mood affects node glow intensity

---

### NeuralBuilding (`NeuralBuilding.jsx`)

Renders a holographic multi-tier building representing a firm agent.

**Props:**
- `active` (bool, default `true`) — Whether the animation is active
- `activityLevel` (string, default `'normal'`) — Activity level: `'normal'`, `'low'`, or `'high'`
- `tier` (int, default `3`) — Building tier (1–3), affects height and complexity

**Structure (based on tier):**
- Tier 1: Single block, 55 units height
- Tier 2: Two blocks, 90 units height with mid-section
- Tier 3: Three blocks, 150 units height with spire

**Visual:**
- Emerald/green color palette for windows and structure
- Window points on outer surfaces
- Core energy line through center
- Activity level affects animation speed and glow intensity

---

### NeuralGovernment (`NeuralGovernment.jsx`)

Renders a holographic obelisk/monument representing the government agent.

**Props:**
- `active` (bool, default `true`) — Whether the animation is active
- `activityLevel` (string, default `'normal'`) — Activity level: `'normal'` or `'high'` (high when government is in deficit)

**Structure:**
- Base: Stepped platform with wide foundation
- Pillar: Tapering obelisk from base to apex (240 units total height)
- Apex: "Eye" point at the top
- Core: Energy line running through center

**Visual:**
- Indigo/violet color palette (`rgb(139, 92, 246)`)
- Gold/white accents for apex and core
- Core pulses based on activity level
- Monument represents stability and authority

---


## Overview

The frontend is a React + Vite application styled with Tailwind CSS and the "Oberon Command" dark tech theme. It connects to the backend via WebSocket and displays real-time simulation data across 6 views.

### Running

```bash
# Backend (must be running first)
python -m uvicorn backend.server:app --reload --port 8002

# Frontend
cd frontend-react
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Navigation

The sidebar has 6 views:

| View | Icon | Description | Available |
|------|------|-------------|-----------|
| **Config** | Settings | Set up simulation parameters and initialize | Always |
| **Dashboard** | Activity | Main economic metrics and charts | After init |
| **Subjects** | Users | Individual household inspection | After init |
| **Firms** | Building | Firm analytics and tracked firm detail | After init |
| **Gov** | Landmark | Government policy and fiscal overview | After init |
| **Logs** | Terminal | Simulation event log | After init |

The Dashboard, Subjects, Firms, Government, and Logs views are locked until the simulation is initialized.

---

## Config View

**Before initialization** — Set simulation scale and policy:

- **Population Scale**: 100–10,000 households (slider) — backend supports up to 100,000
- **Wage Tax Rate**: 0–50% (slider)
- **Corp Profit Tax**: 0–60% (slider)
- **INITIALIZE PROTOCOL** button — sends SETUP command and auto-starts simulation

**After initialization** — Adjust runtime policy:

- **Wage Tax Rate** — live adjustment (0–50%)
- **Corp Profit Tax** — live adjustment (0–60%)
- **Wealth Tax Rate** — live adjustment (0–10%)
- **Minimum Wage Floor** — $0–$100 (live)
- **Unemployment Benefits** — 0–100% of avg wage (live)

**Stabilization Sandbox:**
- Toggle to disable automatic stabilizers for selected agent types (Households, Firms, Government, or All)
- Useful for observing raw policy effects without safety nets

Config changes are debounced (400ms) before sending to backend.

---

## Dashboard View

The main economic monitoring view with 11 stat tiles and 9 charts.

### Top Stat Tiles (8 tiles)

| Tile | Value | Format |
|------|-------|--------|
| GDP Output | Total GDP | Adaptive ($K/$M/$B/$T) |
| Net Worth | Total household + firm net worth | Adaptive |
| Gov Profit | Government fiscal profit | Adaptive |
| Gov Debt | Government debt | Adaptive |
| Unemployment | Unemployment rate | Percentage |
| Employment | Employment rate | Percentage |
| Avg Wage | Mean wage across employed | Dollar |
| Happiness | Mean happiness score | 0-100 scale |

### Wealth Inequality Row (3 tiles below charts)

| Tile | Description |
|------|-------------|
| Gini Coefficient | 0-1 scale, color-coded (green <0.30, red >0.70) |
| Top 10% Wealth Share | Percentage of total wealth held by top 10% |
| Bottom 50% Share | Percentage of total wealth held by bottom 50% |

### System Distress Gauge

- Visual gauge showing unemployment vs happiness levels
- Appears between top tiles and charts

### Charts (9 panels in the Economic Monitor)

| # | Chart | Type | Data | Colors |
|---|-------|------|------|--------|
| 1 | GDP Growth | Line | GDP history over time | Sky blue |
| 2 | Wage Trends | Line (dual) | Mean wage + Median wage | Emerald + Amber |
| 3 | Unemployment Rate | Line | Unemployment % over time | Red |
| 4 | Total Net Worth | Line | Combined net worth over time | Purple |
| 5 | Health Index | Line | Mean health score (0-100) | Pink |
| 6 | Market Prices | Line (4 lines) | Food/Housing/Services/Healthcare prices | Amber/Emerald/Cyan/Rose |
| 7 | Total Supply | Line (4 lines) | Food/Housing/Services/Healthcare inventory | Amber/Emerald/Cyan/Rose |
| 8 | Fiscal Balance | Line | Government profit over time | Violet |
| 9 | Wealth Distribution | Bar | Bottom 50% / Mid 40% / Top 10% shares | Gray/Blue/Red |

Charts use Recharts `LineChart` (1-8) and `BarChart` (9) with gradient fills and auto-scaling Y-axis.

### System Advisory Footer

- Displays system warning message ("Monitor inflation risk. Supply chain nominal.")
- Shows total firm count
- Appears at bottom of Dashboard view

---

## Subjects View

Inspect individual tracked households with a detailed profile.

### Subject Tabs (top)
- All tracked households shown as selectable tabs
- Each tab shows: ID, name, state (WORKING → "ACTIVE", MED_SCHOOL → "TRAINING", UNEMPLOYED), and a status dot
- Status dot colors: WORKING (green), MED_SCHOOL (violet), UNEMPLOYED (red)

### Left Column — Bio & Employment
- **Bio-Metric**: Age, health percentage, current status, medical status
- **Employment**: Employer name, current wage, shift status (ACTIVE/OFF)
- **Expected Wage**: Shows expected wage with reasoning (mode, reservation wage, gap to current)
- **Unemployment Info**: Duration and pressure factors (duration, cash, health, decay)
- **Skills & Morale**: Competency level bar (0-100%), morale index bar (0-100%)
- **Traits**: Spending tendency, frugality, saving tendency, price sensitivity, quality lavishness, skill growth rate, health decay, healthcare seek rate, min food/services per tick

### Center Column — Neural Avatar
- Animated holographic avatar visualization (`NeuralAvatar` component)
- Mood varies based on happiness level (happy/neutral)
- Header overlay: Name, ID, state
- Bottom gauges: Happiness (circular) and Stress Level (circular, inverse of happiness)

### Right Column — Financials & History
- **Finances**: Liquid cash, net worth, medical debt (if any)
- **Wealth chart**: Cash balance over time (line chart)
- **Wage chart**: Wage over time (line chart)
- **Needs**: Food units, housing status (yes/no), healthcare units
- **Traits Summary**: Compact view of household behavioral traits

---

## Firms View

Market analytics and individual firm inspection.

### Top Stat Tiles (4 tiles)
- Total Firms, Total Employees, Avg Wage Offer, Struggling Firms (with distress gauge)

### Market Mood Panel
- Shows VOLATILE or STABLE based on struggling firm ratio (>15% struggling = VOLATILE)
- Average price and quality displayed
- Market sentiment text (e.g., "Calm winds")
- Animated `NeuralBuilding` holographic visualization
- Activity level varies by market stress

### Sector Breakdown
- Grid showing each category (Food, Housing, Services, Healthcare)
- Per category: firm count, total employees, avg cash, avg price
- Healthcare category also shows: doctor employees, visit revenue

### Firm Tables
- **Top Cash Positions**: 8 firms sorted by cash balance
- **Top Employers**: 8 firms sorted by employee count
- Columns: Firm name, category, cash, employees, price, wage, profit

### Tracked Firm Detail (right sidebar)
- Select from up to 7 tracked firms
- Detail card: Name, category, state (DISTRESS/SCALING/OPERATING)
- Metrics: Cash, inventory, employees, quality, price, wage offer, revenue, profit
- **Cash History** chart: Cash balance over time (line chart)
- **Profit History** chart: Profit over time (line chart)

---

## Government View

Government policy controls and fiscal monitoring with neural monument visualization.

### Left Column — Policy Overrides & State Capacity

**Policy Overrides:**
- **Income Tax (Wage)** — live adjustment (0–50%)
- **Corporate Tax** — live adjustment (0–60%)
- **Wealth Tax** — live adjustment (0–10%)
- **Unemployment Benefits** — 0–100% of avg wage (live)
- **Minimum Wage** — $0–$100 (live)

**State Capacity:**
- **Gov Owned Firms** count
- **Active Loans** amount
- **Bond Purchases** amount

### Center Column — Neural Government

- Animated holographic obelisk/monument visualization (`NeuralGovernment` component)
- Activity level varies based on government fiscal status (normal when profitable, high when in deficit)
- Header overlay: "GOVERNMENT CORE" with AI Advisor status indicator
- Monument structure with base steps, tapering pillar, and apex "eye"
- Core energy line runs through the center of the monument

### Right Column — Fiscal Monitoring

- **Gov Cash**, **Gov Debt**, **Gov Profit** stat tiles
- **National Debt History** chart (line chart)
- AI Advisor status indicator (always online)

---

## Logs View

Terminal-style event log showing simulation events.

- Path displayed as `/var/logs/ecosim_events.log`
- Auto-scroll enabled
- Each log entry: tick number, type tag, message text
- Type colors: WARN (amber), ECO (emerald), GOV (purple), SYS (white)
- Keeps last ~20 events from backend plus boot sequence messages

---

## WebSocket Protocol

### Connection

```
ws://localhost:8002/ws
```

Auto-reconnects on disconnect (1.2s delay).

### Commands (Frontend → Backend)

| Command | Payload | Description |
|---------|---------|-------------|
| `SETUP` | `{ command: "SETUP", config: { num_households, num_firms, wage_tax, profit_tax, disable_stabilizers, disabled_agents } }` | Initialize simulation |
| `START` | `{ command: "START" }` | Begin/resume tick execution |
| `STOP` | `{ command: "STOP" }` | Pause simulation |
| `RESET` | `{ command: "RESET" }` | Reset to pre-initialization state |
| `CONFIG` | `{ command: "CONFIG", config: { wageTax, profitTax, minimumWage, unemploymentBenefitRate } }` | Update runtime policy |
| `STABILIZERS` | `{ command: "STABILIZERS", disable_stabilizers: bool, disabled_agents: [...] }` | Toggle agent stabilizers |

### Messages (Backend → Frontend)

| Type | Description |
|------|-------------|
| `SETUP_COMPLETE` | Simulation initialized, switch to dashboard |
| `STARTED` | Simulation resumed |
| `STOPPED` | Simulation paused |
| `RESET` | Simulation reset, return to config view |
| `STABILIZERS_UPDATED` | Stabilizer settings confirmed |
| Tick data | `{ tick, metrics: {...}, firm_stats: {...}, logs: [...] }` |

### Tick Metrics Payload

The main data message sent each tick includes:

```json
{
  "tick": 150,
  "metrics": {
    "unemployment": 5.2,
    "gdp": 8.45,
    "govDebt": 0,
    "govProfit": 1200,
    "happiness": 72.5,
    "avgWage": 45.30,
    "netWorth": 12.5,
    "giniCoefficient": 0.35,
    "top10Share": 45.2,
    "bottom50Share": 12.8,
    "gdpHistory": [{"value": 8.1}, {"value": 8.3}, ...],
    "unemploymentHistory": [{"value": 6.0}, ...],
    "wageHistory": [{"value": 42.0}, ...],
    "medianWageHistory": [{"value": 40.0}, ...],
    "happinessHistory": [{"value": 70.0}, ...],
    "healthHistory": [{"value": 85.0}, ...],
    "govProfitHistory": [{"value": 1000}, ...],
    "netWorthHistory": [{"value": 12.0}, ...],
    "firmCountHistory": [{"value": 33}, ...],
    "giniHistory": [{"value": 0.34}, ...],
    "priceHistory": {
      "food": [{"value": 12.5}, ...],
      "housing": [{"value": 25.0}, ...],
      "services": [{"value": 8.0}, ...],
      "healthcare": [{"value": 15.0}, ...]
    },
    "supplyHistory": {
      "food": [{"value": 5000}, ...],
      "housing": [{"value": 2000}, ...],
      "services": [{"value": 3000}, ...],
      "healthcare": [{"value": 1000}, ...]
    },
    "trackedSubjects": [
      {
        "id": 42,
        "name": "Household_42",
        "state": "WORKING",
        "age": 35,
        "health": 0.92,
        "happiness": 0.75,
        "morale": 0.80,
        "skills": 0.65,
        "cash": 1250,
        "netWorth": 1500,
        "medicalDebt": 0,
        "wage": 55.00,
        "employer": "FoodCo_7",
        "needs": { "food": 10.5, "housing": true, "healthcare": 2.0 },
        "history": {
          "cash": [{"value": 1000}, {"value": 1100}, ...],
          "wage": [{"value": 50}, {"value": 52}, ...]
        }
      }
    ],
    "trackedFirms": [
      {
        "id": 7,
        "name": "FoodCo_7",
        "category": "Food",
        "state": "OPERATING",
        "cash": 5000,
        "inventory": 150.5,
        "employees": 12,
        "quality": 6.5,
        "price": 12.50,
        "wageOffer": 55.00,
        "lastRevenue": 1500,
        "lastProfit": 200,
        "history": {
          "cash": [{"value": 4800}, {"value": 5000}, ...],
          "profit": [{"value": 180}, {"value": 200}, ...]
        }
      }
    ]
  },
  "firm_stats": {
    "total_firms": 33,
    "total_employees": 850,
    "avg_wage_offer": 45.30,
    "avg_price": 15.20,
    "avg_quality": 5.5,
    "struggling_firms": 2,
    "market_sentiment": "Calm winds",
    "categories": [
      { "category": "Food", "firm_count": 11, "total_employees": 300, "avg_cash": 4500, "avg_price": 12.50 },
      { "category": "Housing", "firm_count": 8, "total_employees": 200, "avg_cash": 5200, "avg_price": 25.00 },
      { "category": "Services", "firm_count": 10, "total_employees": 250, "avg_cash": 3800, "avg_price": 8.00 },
      { "category": "Healthcare", "firm_count": 4, "total_employees": 100, "avg_cash": 6000, "avg_price": 15.00 }
    ],
    "top_cash": [...],
    "top_employers": [...]
  },
  "logs": [
    { "tick": 150, "type": "ECO", "txt": "Private firm created in Services" }
  ]
}
```

### Currency Formatting

GDP, net worth, and government values use adaptive formatting:
- Below $1K: `$500`
- $1K–$1M: `$45.2K`
- $1M–$1B: `$8.45M`
- $1B–$1T: `$2.30B`
- Above $1T: `$1.50T`

Values are sent from the backend in millions and converted client-side.
