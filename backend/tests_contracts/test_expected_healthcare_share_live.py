"""Live checks: the healthcare share estimate equals the real charge.

- Legacy: seeded run with a 50% healthcare subsidy and a small treasury, so
  the per-tick subsidy cap runs out, binds partway, and is slack. Every
  payment equals min(requested, budget the estimate reads just before it),
  and the household share it leaves equals the estimate.
- income_first / income_late, patient_pay and covered: every care sale
  committed by settle_payment_care leaves the household the share the
  estimate gave just before it (1.0 and 0.0), with the subsidy lever on.
"""

import contextlib
import io
import random

import numpy as np
import pytest

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


def _seeded_run(sequence, care_mode, ticks, households, firms, setup):
    with use_config(clone_config()):
        random.seed(42)
        np.random.seed(42)
        CONFIG.random_seed = 42
        CONFIG.payment_sequence = sequence
        CONFIG.payment_care_mode = care_mode
        if care_mode == "covered":
            CONFIG.payment_assistance = "care"  # funds the covered-care budget
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms)
            setup(economy)
            for _ in range(ticks):
                economy.step()
    return economy


def _healthcare_subsidy_on(economy):
    economy.government.set_lever("sector_subsidy_target", "healthcare")
    economy.government.set_lever("sector_subsidy_level", 50)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("care_mode,expected", [("patient_pay", 1.0), ("covered", 0.0)])
def test_estimate_equals_settle_payment_care_charge(sequence, care_mode, expected):
    """Payment sequences charge care in settle_payment_care, which ignores the
    sector subsidy lever: the estimate must match its split, not the lever."""
    from payments import PaymentBook

    original = PaymentBook.commit_sale
    seen = []

    def recording(self, household, firm, qty, price, *, public_amount=0.0, bank_amount=0.0, kind="goods"):
        estimate = self.economy.expected_healthcare_household_share(price) if kind == "care" else None
        ok = original(self, household, firm, qty, price, public_amount=public_amount,
                      bank_amount=bank_amount, kind=kind)
        if kind == "care" and ok and price > 0.0:
            seen.append((estimate, (price - public_amount) / price))
        return ok

    PaymentBook.commit_sale = recording
    try:
        _seeded_run(sequence, care_mode, 52, 200, 3, _healthcare_subsidy_on)
    finally:
        PaymentBook.commit_sale = original

    assert seen, "no care visit was charged"
    for estimate, actual in seen:
        assert estimate == expected
        assert actual == pytest.approx(estimate)


def test_estimate_equals_legacy_charge():
    """Legacy: the estimate taken just before each visit's subsidy payment
    equals the household share that payment leaves."""
    original = Economy.apply_sector_subsidy_payment
    seen = []

    def recording(self, requested_share):
        share = self.government.healthcare_visit_subsidy_share()
        price = requested_share / share
        estimate = self.expected_healthcare_household_share(price)
        paid, denied = original(self, requested_share)
        if price > 0.0:
            seen.append((estimate, (price - paid) / price))
        return paid, denied

    def setup(economy):
        _healthcare_subsidy_on(economy)
        economy.government.cash_balance = 100_000.0  # make the cap bind

    Economy.apply_sector_subsidy_payment = recording
    try:
        _seeded_run("legacy", "patient_pay", 104, 400, 6, setup)
    finally:
        Economy.apply_sector_subsidy_payment = original

    assert seen
    assert any(estimate == 1.0 for estimate, _ in seen)  # cap ran out
    assert any(0.5 < estimate < 1.0 for estimate, _ in seen)  # cap bound partway
    assert any(estimate == pytest.approx(0.5) for estimate, _ in seen)  # cap slack
    for estimate, actual in seen:
        assert actual == pytest.approx(estimate)
