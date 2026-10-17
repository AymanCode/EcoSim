"""Live check of the budget behind the healthcare share estimate.

Seeded run with a 50% healthcare subsidy and a small treasury, so the per-tick
subsidy cap both runs out and binds partway through a visit. Every payment
must equal min(requested, budget the estimate reads just before it).
"""

import contextlib
import io
import random

import numpy as np

from config import CONFIG, clone_config, use_config
from economy import Economy
from tools.runners.run_large_simulation import create_large_economy


def test_budget_estimate_matches_every_live_subsidy_payment():
    original = Economy.apply_sector_subsidy_payment
    calls = []

    def recording(self, requested_share):
        budget = self.sector_subsidy_budget_left() if self._payment_free_treasury_cash() > 0.0 else 0.0
        paid, denied = original(self, requested_share)
        calls.append((max(0.0, float(requested_share or 0.0)), budget, paid))
        return paid, denied

    Economy.apply_sector_subsidy_payment = recording
    try:
        with use_config(clone_config()):
            random.seed(42)
            np.random.seed(42)
            CONFIG.random_seed = 42
            with contextlib.redirect_stdout(io.StringIO()):
                economy = create_large_economy(400, 6)
                economy.government.set_lever("sector_subsidy_target", "healthcare")
                economy.government.set_lever("sector_subsidy_level", 50)
                # A small treasury makes the per-tick cap (2% of cash) bind.
                economy.government.cash_balance = 100_000.0
                for _ in range(104):
                    economy.step()
    finally:
        Economy.apply_sector_subsidy_payment = original

    paid_calls = [c for c in calls if c[0] > 0.0]
    assert paid_calls, "healthcare subsidy never requested"
    assert any(budget == 0.0 for _requested, budget, _paid in paid_calls), "cap never ran out"
    assert any(0.0 < budget < requested for requested, budget, _paid in paid_calls), "cap never bound partway"
    for requested, budget, paid in paid_calls:
        assert paid == min(requested, budget)
