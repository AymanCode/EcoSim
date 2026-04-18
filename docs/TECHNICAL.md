## File Structure

```text
EcoSim/
|-- backend/
|   |-- agents.py              core agent behavior
|   |-- economy.py             tick coordinator and market logic
|   |-- config.py              simulation parameters
|   |-- server.py              FastAPI + WebSocket entrypoint
|   |-- data/                  warehouse schema, models, migrations
|   |-- tests_contracts/       contract-style regression tests
|   |-- tests_server/          API and persistence tests
|   `-- tools/                 supplementary runners, checks, and analysis helpers
|-- frontend-react/            dashboard application
|-- docs/                      active technical documentation
`-- ops/                       optional infrastructure files
```
