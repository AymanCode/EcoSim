## File Structure

```text
EcoSim/
|-- backend/
|   |-- agents.py              core agent behavior
|   |-- economy.py             tick coordinator and market logic
|   |-- config.py              simulation parameters
|   |-- server.py              FastAPI + WebSocket entrypoint
|   |-- tools/                 supplementary runners, checks, and analysis helpers
|   |   |-- analysis/           audit digest and data generation scripts
|   |   |-- checks/             behavioral test runners
|   |   |-- llm/                 LLM integration (firm, government)
|   |   `-- runners/             simulation runners and diagnostics
|   |-- tests_contracts/       contract-style regression tests
|   |   `-- conftest.py         test fixtures (make_economy, make_household, etc.)
|   `-- tests_server/          API and persistence tests
|-- frontend-react/            dashboard application
|-- docs/                      active technical documentation
`-- ops/                       optional infrastructure files
```
