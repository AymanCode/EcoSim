# EcoSim Frontend Dashboard

What the React dashboard displays, how to use it, and how it communicates with the backend.

---

## Overview

The frontend is a React + Vite application styled with Tailwind CSS and the "Oberon Command" dark tech theme. It connects to the backend via WebSocket and displays real-time simulation data across 5 views.

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

The sidebar has 5 views:

| View | Icon | Description | Available |
|------|------|-------------|-----------|
| **Config** | Settings | Set up simulation parameters and initialize | Always |
| **Dashboard** | Activity | Main economic metrics and charts | After init |
| **Subjects** | Users | Individual household inspection | After init |
| **Firms** | Building | Firm analytics and tracked firm detail | After init |
| **Logs** | Terminal | Simulation event log | After init |

The Dashboard, Subjects, Firms, and Logs views are locked until the simulation is initialized.

---

## Config View

**Before initialization** — Set simulation scale and policy:

- **Population Scale**: 100–3,000 households (slider)
- **Market Density**: 1–50 firms per category (slider)
- **Wage Tax Rate**: 0–50% (slider)
- **Corp Profit Tax**: 0–60% (slider)
- **INITIALIZE PROTOCOL** button — sends SETUP command and auto-starts simulation

**After initialization** — Adjust runtime policy:

- **Wage Tax Rate** — live adjustment
- **Corp Profit Tax** — live adjustment
- **Minimum Wage Floor** — $0–$100 (live)
- **Unemployment Benefits** — 0–100% of avg wage (live)

**Stabilization Sandbox:**
- Toggle to disable automatic stabilizers for selected agent types (Households, Firms, Government, or All)
- Useful for observing raw policy effects without safety nets

Config changes are debounced (400ms) before sending to backend.

---

## Dashboard View

The main economic monitoring view with stat tiles and 9 charts.

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

### Wealth Inequality Row (3 tiles)

| Tile | Description |
|------|-------------|
| Gini Coefficient | 0-1 scale, color-coded (green <0.30, red >0.70) |
| Top 10% Wealth Share | Percentage of total wealth held by top 10% |
| Bottom 50% Share | Percentage of total wealth held by bottom 50% |

### Charts (9 panels in the Economic Monitor)

| # | Chart | Data | Colors |
|---|-------|------|--------|
| 1 | GDP Growth | GDP history over time | Sky blue |
| 2 | Wage Trends | Mean wage + Median wage (dual line) | Emerald + Amber |
| 3 | Unemployment Rate | Unemployment % over time | Red |
| 4 | Total Net Worth | Combined net worth over time | Purple |
| 5 | Health Index | Mean health score (0-100) | Pink |
| 6 | Market Prices | Food/Housing/Services/Healthcare prices (4 lines) | Amber/Emerald/Cyan/Rose |
| 7 | Total Supply | Food/Housing/Services/Healthcare inventory (4 lines) | Amber/Emerald/Cyan/Rose |
| 8 | Fiscal Balance | Government profit over time | Violet |
| 9 | Wealth Distribution | Bar chart: Bottom 50% / Mid 40% / Top 10% shares | Gray/Blue/Red |

All charts use Recharts `AreaChart` with gradient fills and auto-scaling Y-axis.

### System Advisory Footer

Shows total firm count and market mood status.

---

## Subjects View

Inspect individual tracked households with a detailed profile.

### Subject Tabs (top)
- Up to 12 tracked households shown as selectable tabs
- Each tab shows: ID, name, state (WORKING/SLEEPING/STRESSED), and a status dot

### Left Column — Bio & Employment
- **Bio-Metric**: Age, health percentage, current status
- **Employment**: Employer name, current wage, shift status (active/off)
- **Skills & Morale**: Competency level bar (0-100%), morale index bar (0-100%)

### Center Column — Neural Avatar
- Animated holographic avatar visualization (`NeuralAvatar` component)
- Mood varies based on happiness level (happy/neutral)
- Header overlay: Name, ID, state
- Bottom gauges: Happiness (circular) and Stress Level (circular, inverse of happiness)

### Right Column — Financials & History
- **Finances**: Liquid cash, net worth, medical debt (if any)
- **Wealth chart**: Cash balance over time (line chart)
- **Wage chart**: Wage over time (line chart)
- **Inventory**: Current food, housing status (yes/no), healthcare units

---

## Firms View

Market analytics and individual firm inspection.

### Top Stat Tiles (4 tiles)
- Total Firms, Total Employees, Avg Wage Offer, Struggling Firms

### Market Mood Panel
- Shows VOLATILE or STABLE based on struggling firm ratio
- Average price and quality displayed
- Animated `NeuralBuilding` holographic visualization
- Activity level varies by market stress

### Sector Breakdown
- Grid showing each category (Food, Housing, Services, Healthcare)
- Per category: firm count, total employees, avg cash, avg price

### Firm Tables
- **Top Cash Positions**: 8 firms sorted by cash balance
- **Top Employers**: 8 firms sorted by employee count
- Columns: Firm name, category, cash, employees, price, wage, profit

### Tracked Firm Detail (right sidebar)
- Select from up to 7 tracked firms
- Detail card: Name, category, state (DISTRESS/SCALING/OPERATING)
- Metrics: Cash, inventory, employees, quality, price, wage offer, revenue, profit
- **Cash History** chart: Cash balance over time
- **Profit History** chart: Profit over time

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
