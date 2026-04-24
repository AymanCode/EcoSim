# Contract Test Suite

This folder uses a single naming style for readability:

- `test_contracts_invariants.py`: core invariants (accounting, bounds, determinism, uniqueness)
- `test_contracts_behavior.py`: direct behavior contracts (food/health, services, morale, budgeting)
- `test_contracts_healthcare.py`: healthcare service model contracts
- `test_contracts_integration.py`: short deterministic integration sanity checks
- `test_contracts_post_warmup.py`: post-warmup policy sanity checks on a warmed market economy
- `test_contracts_factories.py`: scenario-factory helpers for handcrafted and generated economies

Legacy files with `test_tier*` names are kept only as aliases and are skipped at collection time.

Run stable contract tests:

```bash
python -m pytest backend/tests_contracts -q -m "not llm and not research"
```

Run in-progress LLM and research contracts locally:

```bash
python -m pytest backend/tests_contracts -q -m "llm or research"
```

Recent coverage added on top of the core suites:

- post-warmup cash-ledger conservation in no-sink economies
- distressed private-firm survival-mode probes, including a documented known-gap check for 3-worker firms that should downsize but currently do not

## Scenario Factories

Use the `factory` fixture (from `conftest.py`) to handcraft scenarios:

```python
def test_example(factory):
    gov = factory.government(cash_balance=10_000.0)
    hh = factory.household(household_id=1, health=0.4)
    firm = factory.firm(firm_id=1, category="Services", price=12.0)
    eco = factory.economy(households=[hh], firms=[firm], government=gov)
```

Use `economy_factory` for one-call generated tiny economies:

```python
def test_generated(economy_factory):
    eco = economy_factory(num_households=12, categories=("Food", "Services"), num_firms_per_category=2)
```
