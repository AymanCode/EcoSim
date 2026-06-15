# EcoSim Dashboard

React/Vite dashboard for the EcoSim simulation.

## Recommended Startup

Run the full stack from the repository root:

```bash
docker compose up --build -d --wait
```

Open `http://localhost:5173`.

## Frontend-Only Development

Start the backend first:

```bash
python -m uvicorn backend.server:app --reload --port 8002
```

Then run Vite:

```bash
cd frontend-react
npm install
npm run dev
```

Vite proxies `/ws` and `/health` to `http://127.0.0.1:8002`.

## Checks

```bash
npm ci
npm run lint
npm run build
```

Dashboard implementation details live in [`../docs/FRONTEND.md`](../docs/FRONTEND.md).
