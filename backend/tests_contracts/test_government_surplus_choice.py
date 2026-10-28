"""The standing surplus policy gates the existing Treasury-to-Misc flow."""

import pytest

from agents import GovernmentAgent
from config import clone_config, use_config
from tests_contracts.factories import make_economy


def test_default_off_and_explicit_on_preserve_amount_and_guards():
    gov = GovernmentAgent(cash_balance=200_000.0, payment_reserved_cash=20_000.0)
    assert gov.surplus_distribution == "off"
    assert gov.make_investments() == {"bonds": 0.0}
    assert gov.cash_balance == 200_000.0
    gov.set_lever("surplus_distribution", "on")
    assert gov.make_investments()["bonds"] == pytest.approx(15_600.0)
    assert gov.cash_balance == pytest.approx(184_400.0)

    for cash, reserved, debt, disabled in [
        (60_000.0, 0.0, 0.0, False),  # strict $10k threshold
        (80_000.0, 20_000.0, 0.0, False),
        (200_000.0, 0.0, 1.0, False),
        (200_000.0, 0.0, 0.0, True),
    ]:
        gov.cash_balance, gov.payment_reserved_cash = cash, reserved
        gov.public_debt, gov.stabilization_disabled = debt, disabled
        assert gov.make_investments()["bonds"] == 0.0
        assert gov.cash_balance == cash
    with pytest.raises(ValueError):
        gov.set_lever("surplus_distribution", "sometimes")
    assert gov.surplus_distribution == "on"
    gov.set_lever("surplus_distribution", "off")
    assert gov.make_investments()["bonds"] == 0.0


@pytest.mark.parametrize("sequence", ["income_first", "income_late", "legacy"])
def test_tick_routes_selected_payout_to_existing_misc_collector(sequence, monkeypatch):
    config = clone_config()
    config.payment_sequence = sequence
    with use_config(config):
        eco = make_economy(num_households=12, num_firms_per_category=1, disable_shocks=True, seed=71)
        eco.government.cash_balance = 1_000_000.0
        calls = []
        original = eco._collect_misc_revenue
        def collect(amount):
            calls.append(amount)
            original(amount)
        monkeypatch.setattr(eco, "_collect_misc_revenue", collect)
        eco.step()
        assert eco.last_tick_gov_bond_purchases == 0.0
        eco.government.set_lever("surplus_distribution", "on")
        calls.clear()
        eco.step()
        payout = eco.last_tick_gov_bond_purchases
        assert payout > 0.0
        assert payout in calls
        assert eco._capture_audit_government_state()["surplus_distribution"] == "on"
        assert eco.get_economic_metrics()["gov_surplus_distribution"] == "on"
        eco.government.set_lever("surplus_distribution", "off")
        eco.step()
        assert eco.last_tick_gov_bond_purchases == 0.0


def test_misc_tax_and_household_counterparties():
    eco = make_economy(num_households=12, num_firms_per_category=1, disable_shocks=True, seed=72)
    gov = eco.government
    gov.cash_balance = 200_000.0
    gov.set_lever("surplus_distribution", "on")
    beneficiary = eco.households[0]
    eco.misc_firm_beneficiaries = [beneficiary.household_id]
    eco.misc_firm_revenue = 0.0
    before = beneficiary.cash_balance
    amount = gov.make_investments()["bonds"]
    eco._collect_misc_revenue(amount)
    tax = gov.cash_balance - (200_000.0 - amount)
    assert 0 <= tax <= 0.2 * amount
    assert eco.misc_firm_revenue == pytest.approx(amount - tax)
    eco._misc_firm_redistribute_revenue()
    assert beneficiary.cash_balance - before == pytest.approx(amount - tax)
    assert gov.cash_balance + beneficiary.cash_balance - before == pytest.approx(200_000.0)
