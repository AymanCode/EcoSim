"""Lagged information and planning-only household obligations."""

from collections import defaultdict
from types import SimpleNamespace

import pytest

from payment_behavior import (
    diagnose_observed_offer,
    initialize_tax_beliefs,
    observe_settled_tax,
    planning_inputs,
)


def scenario():
    households = [
        SimpleNamespace(household_id=1, wage=100.0, is_employed=True,
                        cash_balance=80.0, bank_deposit=20.0,
                        renting_from_firm_id=2, monthly_rent=40.0,
                        last_wage_income=999.0),
        SimpleNamespace(household_id=2, wage=100.0, is_employed=True,
                        cash_balance=80.0, bank_deposit=20.0,
                        renting_from_firm_id=None, monthly_rent=0.0,
                        last_wage_income=999.0),
    ]
    gov = SimpleNamespace(wage_tax_rate=0.15, get_unemployment_benefit_level=lambda: 20.0)
    book = SimpleNamespace(loan_state={"household_due_tick": 0, "household_due_totals": {1: 10.0, 2: 10.0}},
                           paid_income=defaultdict(dict))
    return SimpleNamespace(current_tick=0, payment_state={}, payment_book=book,
                           government=gov, households=households,
                           household_lookup={h.household_id: h for h in households})


def test_lagged_ordinary_tax_belief_ignores_ceo_and_preserves_zero_income():
    e = scenario()
    assert initialize_tax_beliefs(e) == {1: 0.15, 2: 0.15}
    net_before, _, _ = planning_inputs(e)
    assert net_before == pytest.approx([85, 85])
    e.payment_book.paid_income[1] = {"gross": 100, "tax": 35, "ceo": 500}
    e.payment_book.paid_income[2] = {"gross": 0, "tax": 0, "ceo": 500}
    observe_settled_tax(e)
    assert e.payment_state["expected_wage_tax_share"] == pytest.approx({1: 0.35, 2: 0.15})
    # A second call in the same tick cannot update the belief again.
    e.payment_book.paid_income[1]["tax"] = 70
    observe_settled_tax(e)
    assert e.payment_state["expected_wage_tax_share"][1] == pytest.approx(0.35)
    e.current_tick = 1
    e.payment_book.loan_state["household_due_tick"] = 1
    net_next, _, _ = planning_inputs(e)
    assert net_next == pytest.approx([65, 85])


def test_obligations_subtracted_once_from_liquidity_after_cash_change():
    e = scenario()
    _, liquidity, pressure = planning_inputs(e)
    assert liquidity == pytest.approx([48, 88])  # 80 cash + 18 nominal deposit - rent - debt
    assert pressure[1]["rent_due"] == 40
    assert pressure[1]["loan_due"] == 10
    e.households[0].cash_balance = 30  # e.g. education settled before phase-2 planning
    _, liquidity, _ = planning_inputs(e)
    assert liquidity[0] == pytest.approx(0)
    assert e.payment_book.obligation_pressure[1]["estimated_discretionary_liquidity"] == 0
    e.households[0].cash_balance = -10
    e.households[0].bank_deposit = 100
    _, liquidity, pressure = planning_inputs(e)
    assert pressure[1]["nominal_access"] == pytest.approx(80)
    assert liquidity[0] == pytest.approx(30)  # signed debt cash absorbs 10 of nominal deposit draw


def test_observed_offer_diagnostic_does_not_change_labor_behavior():
    e = scenario()
    hh = e.households[0]
    wage_before = hh.wage
    row = diagnose_observed_offer(e, 1, 110, offer_id="firm-9-offer-1")
    assert row["coverage"] == "observed_accepted_offers_only"
    assert row["estimated_net_gain"] == pytest.approx(8.5)
    assert hh.wage == wage_before
    assert e.payment_book.net_offer_diagnostics == [row]


def test_rejects_missing_current_due_index():
    e = scenario()
    e.payment_book.loan_state["household_due_tick"] = -1
    with pytest.raises(ValueError, match="due index"):
        planning_inputs(e)
