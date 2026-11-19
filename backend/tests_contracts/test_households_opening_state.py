"""Deterministic opening state for the default population."""

import hashlib
import json

from config import clone_config, use_config
from tests_contracts.conftest import seed_everything
from tools.runners.run_large_simulation import create_large_economy


def opening_payload(economy):
    return {
        "households": [(h.household_id, h.skills_level, h.age, h.cash_balance) for h in economy.households],
        "owners": [(f.firm_id, f.owners) for f in economy.firms + economy.queued_firms],
        "queued": [f.firm_id for f in economy.queued_firms],
    }



def test_seed_42_opening_vectors_ownership_and_queued_firms():
    config = clone_config()
    config.payment_sequence = "income_first"
    config.random_seed = 42
    seed_everything(42)
    with use_config(config):
        economy = create_large_economy(1000, 5)

    assert [(h.skills_level, h.age, h.cash_balance) for h in economy.households] == [
        (min(0.95, 0.2 + (i / 1000) * 0.75), 22 + i % 40, 500.0 + i % 100 * 15.0)
        for i in range(1000)
    ]
    # Digest of the opening vector, ordered owners and queued firm IDs at 5c66095.
    payload = json.dumps(opening_payload(economy), separators=(",", ":"))
    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "77bb0cb35ae0f16e9b137c9d33ab7fcf98e1850a5af9ad6f0efa9d0e866a4735"
    )
