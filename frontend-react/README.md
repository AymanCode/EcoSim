# EcoSim Dashboard

This frontend is the main dashboard for the EcoSim simulation.

## Recommended Startup

Run the stack from the repository root:

```bash
./start.sh
```

Windows PowerShell:

```powershell
.\start.ps1
```

That starts the backend and dashboard together through Docker. Open:

- `http://localhost:5173`

## Local Frontend-Only Development

If you are iterating on the UI and want Vite hot reload:

```bash
cd frontend-react
npm install
npm run dev
```

The app will connect to the backend WebSocket automatically from the current host by default. To override it, set `VITE_WS_URL` before building or running the frontend.
