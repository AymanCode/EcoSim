"""Profit-tax brackets rank firms by taxable profit, not cash.

Before this change ``GovernmentAgent.plan_taxes`` cut the profit-tax brackets
at percentiles of firm cash. On the default ``legacy`` payment sequence the
firm tax snapshot carried no ``cash_balance``, so every firm read cash 0 and
paid the bottom-band rate (0.1915 at the default 0.20 base); on the payment
arms a cash-rich firm with a small profit paid a top-band rate. The tax is on
earnings, so the brackets now rank each tick's positive profits. These tests
check the rates firms end up paying.
"""

import random

import pytest

from agents import GovernmentAgent
from config import CONFIG
from tests_contracts.factories import make_economy, make_firm


def _rates(plan, firms):
    # Rounded so tax / profit float noise does not read as a different rate.
    return {f["firm_id"]: round(plan["profit_taxes"][f["firm_id"]] / f["profit_before_tax"], 10)
            for f in firms if f["profit_before_tax"] > 0}


def test_equal_profit_pays_equal_rate_whatever_the_cash():
    gov = GovernmentAgent(cash_balance=0.0)
    firms = [{"firm_id": i, "profit_before_tax": 100.0 * (1 + i % 10), "cash_balance": 0.0}
             for i in range(1, 41)]
    # Two more firms with the same profit as each other but cash 0 and 10 million.
    firms += [{"firm_id": 41, "profit_before_tax": 550.0, "cash_balance": 0.0},
              {"firm_id": 42, "profit_before_tax": 550.0, "cash_balance": 10_000_000.0}]

    rates = _rates(gov.plan_taxes([], firms), firms)

    assert rates[41] == pytest.approx(rates[42])


def test_higher_profit_never_pays_a_lower_rate():
    rng = random.Random(7)
    for base in (0.05, 0.10, 0.20, 0.35, 0.50):
        gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=base)
        firms = [{"firm_id": i, "profit_before_tax": rng.lognormvariate(6.0, 1.5),
                  "cash_balance": rng.uniform(0.0, 1e6)} for i in range(1, 201)]
        rates = _rates(gov.plan_taxes([], firms), firms)
        by_profit = sorted(firms, key=lambda f: f["profit_before_tax"])
        ordered = [rates[f["firm_id"]] for f in by_profit]
        assert ordered == sorted(ordered), f"rates fall with profit at base {base}"
        assert max(ordered) <= 0.60 + 1e-12


def test_loss_making_firms_pay_nothing_and_do_not_move_the_edges():
    gov = GovernmentAgent(cash_balance=0.0)
    earners = [{"firm_id": i, "profit_before_tax": float(10 * i), "cash_balance": 0.0} for i in range(1, 21)]
    losers = [{"firm_id": 100 + i, "profit_before_tax": -1_000.0, "cash_balance": 0.0} for i in range(30)]

    alone = gov.plan_taxes([], earners)["profit_taxes"]
    mixed = gov.plan_taxes([], earners + losers)["profit_taxes"]

    assert all(mixed[f["firm_id"]] == 0.0 for f in losers)
    assert {f["firm_id"]: mixed[f["firm_id"]] for f in earners} == alone


def test_fewer_than_four_profitable_firms_pay_the_base_rate():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.25)
    firms = [{"firm_id": 1, "profit_before_tax": 10.0}, {"firm_id": 2, "profit_before_tax": 5_000.0},
             {"firm_id": 3, "profit_before_tax": -50.0}]

    plan = gov.plan_taxes([], firms)["profit_taxes"]

    assert plan == {1: pytest.approx(2.5), 2: pytest.approx(1_250.0), 3: 0.0}


def test_legacy_snapshots_now_produce_more_than_one_band(monkeypatch):
    """On main every legacy firm paid 0.1915 because the snapshot had no cash."""
    monkeypatch.setattr(CONFIG, "payment_sequence", "legacy")
    firms = [make_firm(firm_id=i, category="Food", is_baseline=False) for i in range(1, 9)]
    for firm in firms:
        firm.employees = []  # no wage bill: profit equals sales revenue
    economy = make_economy(firms=firms, num_households=0)
    assert economy.payment_sequence == "legacy"
    sales = {f.firm_id: {"revenue": 100.0 * f.firm_id, "units_sold": 10.0} for f in firms}

    snapshots = economy._build_firm_tax_snapshots(sales)
    rates = _rates(economy.government.plan_taxes([], snapshots), snapshots)

    assert len(set(rates.values())) > 1
    assert rates[8] > rates[1]
