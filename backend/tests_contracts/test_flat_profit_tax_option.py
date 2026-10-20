"""Flat profit-tax option (``government.flat_profit_tax_enabled``, off by default).

Owner decision 2026-10-20: progressive brackets ranked by profit are the
default; a flat rate is a switchable option for comparing the two styles.
With the switch on, every firm with positive profit pays ``profit_tax_rate``
on it; loss-makers pay 0.
"""

import contextlib
import dataclasses
import io
import random

import numpy as np
import pytest

from agents import GovernmentAgent
from config import CONFIG, SimulationConfig, clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy


def test_flat_switch_is_off_by_default():
    assert SimulationConfig().government.flat_profit_tax_enabled is False


def test_flat_switch_rejects_non_bool():
    with pytest.raises(ValueError, match="flat_profit_tax_enabled"):
        SimulationConfig(government=dataclasses.replace(SimulationConfig().government,
                                                        flat_profit_tax_enabled="yes"))


def test_flat_on_every_profitable_firm_pays_the_lever_rate(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "flat_profit_tax_enabled", True)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.25)
    firms = [{"firm_id": i, "profit_before_tax": float(100 * i), "cash_balance": float(10 ** i)}
             for i in range(1, 21)]
    firms.append({"firm_id": 99, "profit_before_tax": -500.0, "cash_balance": 0.0})

    taxes = gov.plan_taxes([], firms)["profit_taxes"]

    assert all(taxes[i] == pytest.approx(0.25 * 100 * i) for i in range(1, 21))
    assert taxes[99] == 0.0


def test_economy_step_with_flat_on_collects_the_lever_rate():
    """Real legacy Economy.step() with the switch on: each profitable firm's
    realized tax (its cash debit) is profit_tax_rate x its profit, and the
    debits sum to the treasury's booked profit tax. Snapshots are only observed."""
    seen = []
    original = GovernmentAgent.plan_taxes

    def observe(self, households, firms):
        if len(firms) >= 4:
            seen.append([dict(f) for f in firms])
        return original(self, households, firms)

    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.government.flat_profit_tax_enabled = True
    cfg.random_seed = 42
    random.seed(42)
    np.random.seed(42)
    with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(100, 3)
        rate = economy.government.profit_tax_rate
        GovernmentAgent.plan_taxes = observe
        try:
            for _ in range(40):
                seen.clear()
                economy.step()
                snaps = seen[-1] if seen else []
                # > 1.0 so a rounding-size profit does not read as a 0 rate
                profits = {s["firm_id"]: s["profit_before_tax"] for s in snaps
                           if s["profit_before_tax"] > 1.0 and s.get("price_ceiling_tax", 0.0) == 0.0}
                if len(profits) >= 8:
                    break
        finally:
            GovernmentAgent.plan_taxes = original
    assert len(profits) >= 8, "no tick with eight profitable firms in 40 weeks"
    firms = {f.firm_id: f for f in economy.firms}
    for firm_id, profit in profits.items():
        firm = firms[firm_id]
        realized = firm.last_revenue - firm.last_profit - firm.last_tick_total_costs
        assert realized == pytest.approx(rate * profit, rel=1e-9, abs=1e-9)
    debits = sum(firms[s["firm_id"]].last_revenue - firms[s["firm_id"]].last_profit
                 - firms[s["firm_id"]].last_tick_total_costs - s.get("price_ceiling_tax", 0.0)
                 for s in snaps if s["firm_id"] in firms)
    assert economy.last_tick_gov_profit_taxes == pytest.approx(debits, rel=1e-9, abs=1e-6)
