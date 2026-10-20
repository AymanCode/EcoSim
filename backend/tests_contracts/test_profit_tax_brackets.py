"""Profit-tax brackets rank firms by taxable profit, not cash.

Before this change ``GovernmentAgent.plan_taxes`` cut the profit-tax brackets
at percentiles of firm cash. On the default ``legacy`` payment sequence the
firm tax snapshot carried no ``cash_balance``, so every firm read cash 0 and
paid the bottom-band rate (0.1915 at the default 0.20 base); on the payment
arms a cash-rich firm with a small profit paid a top-band rate. The tax is on
earnings, so the brackets now rank each tick's positive profits. These tests
check the rates firms end up paying.
"""

import contextlib
import io
import math
import random

import numpy as np
import pytest

from agents import GovernmentAgent
from config import CONFIG, clone_config, use_config
from tests_contracts.factories import make_economy, make_firm
from tools.runners.run_large_simulation import create_large_economy


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


def test_no_profitable_firm_owes_nothing_and_one_pays_the_base_rate():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    losers = [{"firm_id": i, "profit_before_tax": -10.0 * i} for i in range(1, 6)]
    assert gov._profit_tax_brackets([]) == {}
    assert gov._profit_tax_brackets(losers) == {}
    assert all(v == 0.0 for v in gov.plan_taxes([], losers)["profit_taxes"].values())
    one = losers + [{"firm_id": 9, "profit_before_tax": 500.0}]
    assert gov._profit_tax_brackets(one) == {9: ("base", 0.20)}


def test_tied_profits_share_one_band():
    gov = GovernmentAgent(cash_balance=0.0)
    firms = [{"firm_id": i, "profit_before_tax": 250.0} for i in range(1, 21)]
    assert {band for band, _rate in gov._profit_tax_brackets(firms).values()} == {"bottom"}


def test_non_finite_profit_does_not_move_the_edges():
    gov = GovernmentAgent(cash_balance=0.0)
    firms = [{"firm_id": i, "profit_before_tax": float(10 * i)} for i in range(1, 21)]
    clean = gov._profit_tax_brackets(firms)
    for bad in (math.nan, math.inf):
        dirty = gov._profit_tax_brackets(firms + [{"firm_id": 99, "profit_before_tax": bad}])
        assert 99 not in dirty
        assert dirty == clean


def test_economy_step_on_legacy_collects_profit_ranked_taxes():
    """Real Economy.step() on legacy: firms' realized profit tax (their cash
    debit) rises with profit, takes more than one rate, and sums to the
    treasury's recognized profit tax. Nothing in the tax path is patched; the
    snapshots are only observed on their way into plan_taxes."""
    seen = []
    original = GovernmentAgent.plan_taxes

    def observe(self, households, firms):
        if len(firms) >= 4:
            seen.append([dict(f) for f in firms])
        return original(self, households, firms)

    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.random_seed = 42
    random.seed(42)
    np.random.seed(42)
    with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(100, 3)
        GovernmentAgent.plan_taxes = observe
        try:
            for _ in range(40):
                seen.clear()
                economy.step()
                snaps = seen[-1] if seen else []
                profits = {s["firm_id"]: s["profit_before_tax"] for s in snaps
                           # > 1.0 so a rounding-size profit does not read as a 0 rate
                           if s["profit_before_tax"] > 1.0 and s.get("price_ceiling_tax", 0.0) == 0.0}
                if len(profits) >= 8:
                    break
        finally:
            GovernmentAgent.plan_taxes = original
    assert len(profits) >= 8, "no tick with eight profitable firms in 40 weeks"
    firms = {f.firm_id: f for f in economy.firms}
    realized = {}
    for firm_id, profit in profits.items():
        firm = firms[firm_id]
        # apply_sales_and_profit books profit = revenue - taxes paid - costs.
        realized[firm_id] = firm.last_revenue - firm.last_profit - firm.last_tick_total_costs
    rates = {fid: round(realized[fid] / profits[fid], 6) for fid in profits}
    ordered = [rates[fid] for fid in sorted(profits, key=profits.get)]
    assert ordered == sorted(ordered)
    assert len(set(ordered)) > 1
    # Every firm's debit, net of its price-ceiling tax, is what the treasury books as profit tax.
    debits = sum(firms[s["firm_id"]].last_revenue - firms[s["firm_id"]].last_profit
                 - firms[s["firm_id"]].last_tick_total_costs - s.get("price_ceiling_tax", 0.0)
                 for s in snaps if s["firm_id"] in firms)
    assert economy.last_tick_gov_profit_taxes == pytest.approx(debits, rel=1e-9, abs=1e-6)
