# Backend

The backend is split into three layers:

- `agents.py`, `economy.py`, `config.py`, `server.py`: the live simulation engine and API surface
- `data/`: warehouse persistence, schema, and migration logic
- `tests_contracts/`, `tests_server/`: automated regression coverage

Supplementary runners, analysis helpers, and experiment-oriented utilities live in [`tools/`](tools/README.md) so the main backend surface stays focused on production code.
