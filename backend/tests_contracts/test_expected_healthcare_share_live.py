"""Live checks: the estimate a household can read when it budgets matches the real charge.

Each run calls ``Economy.step()``. The estimate is read at the phase a
household budgets in (right after legacy phase 5b, or right after the
payment arms' budget and deposit pass) and compared with what the visit
actually cost when it was charged later in the same tick.

- Legacy: a 50% healthcare subsidy and a small treasury, so the per-tick cap
  runs out, binds partway and is slack. The walked estimate is never below
  the share charged, and equals it except where a refused visit refunded
  subsidy to later visits.
- income_first / income_late, patient_pay and covered: every care sale leaves
  the household the share read at budget time (1.0 or 0.0), with the
  subsidy lever on.
"""

import contextlib
import io
import pytest

from config import CONFIG, clone_config, use_config
from economy import Economy
from tools.benchmarks.regression_snapshot import _set_seed
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
            _set_seed(42)
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
        _set_seed(42)
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


def test_budget_time_estimate_matches_the_legacy_charge():
    """Read after phase 5b (the household's budget decision), checked against
    every visit completed at phase 6.8 of the same tick."""
    original = Economy._settle_legacy_income_and_plan_shopping
    quoted = {}
    budgets = []
    pairs = []

    def observe(self, tick):
        plans = original(self, tick)
        quoted.clear()
        quoted.update(self.expected_healthcare_household_shares())
        budgets.append(self.sector_subsidy_budget_left())
        return plans

    def setup(economy):
        _healthcare_subsidy_on(economy)
        economy.government.cash_balance = 100_000.0  # make the cap bind

    Economy._settle_legacy_income_and_plan_shopping = observe
    try:
        with use_config(clone_config()):
            _set_seed(42)
            with contextlib.redirect_stdout(io.StringIO()):
                economy = create_large_economy(400, 6)
                setup(economy)
                for _ in range(104):
                    economy.step()
                    for event in economy.last_healthcare_events:
                        if event["event_type"] == "visit_completed" and event["visit_price"] > 0.0:
                            estimate = quoted[event["household_id"]]
                            pairs.append((estimate, event["household_cost"] / event["visit_price"]))
    finally:
        Economy._settle_legacy_income_and_plan_shopping = original

    assert len(pairs) > 300
    estimates = [estimate for estimate, _ in pairs]
    assert any(estimate == pytest.approx(1.0) for estimate in estimates)  # cap ran out
    assert any(0.5 + 1e-9 < estimate < 1.0 - 1e-9 for estimate in estimates)  # cap bound partway
    assert any(estimate == pytest.approx(0.5) for estimate in estimates)  # cap slack
    # Never promise more subsidy than the visit got.
    assert all(estimate >= actual - 1e-9 for estimate, actual in pairs)
    exact = sum(1 for estimate, actual in pairs if estimate == pytest.approx(actual))
    assert exact >= 0.98 * len(pairs)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("care_mode,expected", [("patient_pay", 1.0), ("covered", 0.0)])
def test_budget_time_estimate_matches_settle_payment_care(sequence, care_mode, expected):
    """Payment sequences charge care in settle_payment_care, which ignores the
    sector subsidy lever: the estimate read after the budget pass must match
    its split, not the lever."""
    from payments import PaymentBook

    original_withdraw = Economy._payment_withdraw_deposits
    original_commit = PaymentBook.commit_sale
    quoted = {}
    pairs = []

    def observe(self, quotes):
        result = original_withdraw(self, quotes)
        quoted.clear()
        quoted.update(self.expected_healthcare_household_shares())
        return result

    def recording(self, household, firm, qty, price, *, public_amount=0.0, bank_amount=0.0, kind="goods"):
        ok = original_commit(self, household, firm, qty, price, public_amount=public_amount,
                             bank_amount=bank_amount, kind=kind)
        if kind == "care" and ok and price > 0.0:
            pairs.append((quoted.get(household.household_id), (price - public_amount) / price))
        return ok

    Economy._payment_withdraw_deposits = observe
    PaymentBook.commit_sale = recording
    try:
        _seeded_run(sequence, care_mode, 52, 200, 3, _healthcare_subsidy_on)
    finally:
        Economy._payment_withdraw_deposits = original_withdraw
        PaymentBook.commit_sale = original_commit

    assert pairs, "no care visit was charged"
    for estimate, actual in pairs:
        assert estimate == expected
        assert actual == pytest.approx(estimate)
