"""Round 1 G2: flat profit tax on positive profit.

The tax a firm owes depends on its profit and the profit tax lever, not on
how much cash it holds. Losses pay nothing and carry nothing forward. The
older cash-rank brackets stay available behind
``CONFIG.government.flat_profit_tax_enabled = False``.
"""

import pytest

from agents import GovernmentAgent
from config import CONFIG


def _same_profit_different_cash():
    # Five firms with the same $1,000 profit and cash from $100 to $5M,
    # plus one firm with a $2,000 loss.
    firms = [
        {"firm_id": i, "profit_before_tax": 1_000.0, "cash_balance": cash}
        for i, cash in enumerate([100.0, 5_000.0, 50_000.0, 500_000.0, 5_000_000.0])
    ]
    firms.append({"firm_id": 9, "profit_before_tax": -2_000.0, "cash_balance": 1_000.0})
    return firms


def test_flat_tax_is_the_lever_rate_on_profit_whatever_the_cash():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _same_profit_different_cash())["profit_taxes"]
    assert [taxes[i] for i in range(5)] == pytest.approx([200.0] * 5)


def test_a_loss_pays_nothing_and_does_not_reduce_the_next_tax():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    loss_tick = gov.plan_taxes([], [{"firm_id": 1, "profit_before_tax": -5_000.0, "cash_balance": 0.0}])
    profit_tick = gov.plan_taxes([], [{"firm_id": 1, "profit_before_tax": 1_000.0, "cash_balance": 0.0}])
    assert loss_tick["profit_taxes"][1] == 0.0
    assert profit_tick["profit_taxes"][1] == pytest.approx(200.0)  # no loss carryforward


def test_flat_tax_follows_the_profit_tax_lever():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    gov.profit_tax_rate = 0.35
    taxes = gov.plan_taxes([], _same_profit_different_cash())["profit_taxes"]
    assert taxes[0] == pytest.approx(350.0)


def test_cash_rank_brackets_return_with_the_flag_off(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "flat_profit_tax_enabled", False)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _same_profit_different_cash())["profit_taxes"]
    assert taxes[4] > taxes[0]  # the cash-rich firm pays more on the same profit
    assert taxes[9] == 0.0


def test_property_tax_is_unchanged_by_the_flag(monkeypatch):
    housing = {"firm_id": 7, "profit_before_tax": 500.0, "cash_balance": 10_000.0,
               "good_category": "Housing", "property_tax_rate": 0.01, "max_rental_units": 10, "price": 200.0}
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    flat = gov.plan_taxes([], [housing])["property_taxes"][7]
    monkeypatch.setattr(CONFIG.government, "flat_profit_tax_enabled", False)
    legacy = gov.plan_taxes([], [housing])["property_taxes"][7]
    assert flat == legacy == pytest.approx(0.01 * 10 * 200.0)
