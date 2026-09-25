# Contract Test Suite

This folder uses a single naming style for readability:

- `test_contracts_invariants.py`: core invariants (accounting, bounds, determinism, uniqueness)
- `test_contracts_behavior.py`: direct behavior contracts (food/health, services, morale, budgeting)
- `test_contracts_healthcare.py`: healthcare service model contracts
- `test_contracts_integration.py`: short deterministic integration sanity checks
- `test_contracts_post_warmup.py`: post-warmup policy sanity checks on a warmed market economy
- `test_contracts_factories.py`: scenario-factory helpers for handcrafted and generated economies

Legacy `test_tier*` alias modules were removed; use the canonical `test_contracts_*` modules directly.

Run stable contract tests:

```bash
python -m pytest backend/tests_contracts
```

Mocked LLM contracts are included in the stable gate and need no provider. To focus on them or run the exploratory research contracts:

```bash
python -m pytest backend/tests_contracts -m llm
python -m pytest backend/tests_contracts -m research
```

Recent coverage added on top of the core suites:

- post-warmup cash-ledger conservation in no-sink economies
- distressed private-firm survival-mode probes, including a documented known-gap check for 3-worker firms that should downsize but currently do not

From the repository root, `python -m pytest` also discovers server and warehouse tests. See [the testing guide](../../docs/testing/README.md) for the complete suite map and known gaps.

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
