"""MONEY-P01: discretionary R&D follows settled cash on named payment arms."""

import random

import pytest

from agents import BankAgent
from config import clone_config, use_config
from tests_contracts.factories import patch_agent_method
from tools.benchmarks.panel_money import total_money_net_of_injections


@pytest.mark.parametrize(
    "cash,budget,revenue,profit,survival,category,spent,decays",
    [
        (0.0, 0.0, 100.0, 100.0, False, "Food", 0.0, True),
        (0.5, 0.5, 100.0, 100.0, False, "Food", 0.5, True),
        (100.0, 100.0, 100.0, 100.0, False, "Food", 10.0, True),
        (100.0, 100.0, 0.0, 0.0, False, "Food", 0.0, True),
        (100.0, 100.0, 100.0, -1.0, False, "Food", 0.0, True),
        (100.0, 100.0, 100.0, 0.0, False, "Food", 0.0, True),
        (100.0, 100.0, 100.0, 100.0, True, "Food", 0.0, False),
        (100.0, 100.0, 100.0, 100.0, False, "Healthcare", 0.0, False),
        (-1.0, 0.0, 100.0, 100.0, False, "Services", 0.0, True),
    ],
)
def test_rd_uses_funded_amount_for_every_write(
    factory, cash, budget, revenue, profit, survival, category, spent, decays
):
    firm = factory.firm(
        category=category, cash_balance=cash, net_profit=profit,
        survival_mode=survival, quality_level=4.0,
        accumulated_rd_investment=3.0, quality_improvement_per_rd_dollar=0.02,
        quality_decay_rate=0.01,
    )
    actual = firm.apply_rd_and_quality_update(revenue, available_cash=budget)
    assert actual == pytest.approx(spent)
    assert firm.cash_balance == pytest.approx(cash - spent)
    assert firm.accumulated_rd_investment == pytest.approx(3.0 + spent)
    assert firm.quality_level == pytest.approx(4.0 + spent * 0.02 - (0.01 if decays else 0.0))


def test_omitted_budget_retains_legacy_overdraft_and_exact_arithmetic(factory):
    firm = factory.firm(
        cash_balance=0.0, net_profit=2.968160338415606,
        quality_level=4.0, accumulated_rd_investment=3.0,
    )
    revenue = firm.net_profit
    cfg = firm._firm_config()
    desired = revenue * min(cfg.rd_base_rate + cfg.rd_margin_scaling, cfg.rd_max_rate)
    expected_quality = max(0.0, min(10.0, 4.0 + desired * firm.quality_improvement_per_rd_dollar - firm.quality_decay_rate))
    assert firm.apply_rd_and_quality_update(revenue) == desired
    assert firm.cash_balance == -desired
    assert firm.accumulated_rd_investment == 3.0 + desired
    assert firm.quality_level == expected_quality


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("performance_mode", [False, True])
@pytest.mark.parametrize("route", ["direct_treasury", "bank"])
@pytest.mark.parametrize("remainder", [0.0, 0.5])
def test_step_debt_then_funded_rd_reconciles_through_exit(
    factory, monkeypatch, sequence, performance_mode, route, remainder
):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        buyer = factory.household(household_id=1, cash_balance=100.0, goods_inventory={})
        firm = factory.firm(
            firm_id=1, category="Food", is_baseline=False,
            cash_balance=1000.0, price=10.0, inventory_units=100.0,
            employees=[], actual_wages={}, ceo_household_id=None, owners=[],
        )
        gov = factory.government(
            cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0,
            unemployment_benefit_level=0.0, transfer_budget=0.0,
            infrastructure_spending=0.0, technology_spending=0.0,
            social_spending=0.0, investment_tax_rate=0.1,
        )
        economy = factory.economy(households=[buyer], firms=[firm], government=gov)
        economy.current_tick = 5
        economy.warmup_ticks = 100
        economy.performance_mode = performance_mode
        economy.configure_stabilizers(households=False, firms=False, government=False)
        economy.misc_firm_beneficiaries = [buyer.household_id]
        # The first sale is $20 profit, with no labor/input costs. Debt takes
        # all but the selected R&D budget; no further sale follows.
        due = 1020.0 - remainder
        if route == "direct_treasury":
            firm.government_loan_remaining = 10000.0
            firm.loan_payment_per_tick = due
        else:
            economy.bank = BankAgent(cash_reserves=20000.0)
            loan = economy.bank.originate_loan("firm", firm.firm_id, 10000.0, 0.0, 100)
            loan["payment_per_tick"] = due
            firm.bank_loan_remaining = loan["remaining"]
            firm.bank_loan_payment_per_tick = due
        monkeypatch.setattr(economy, "_run_labor_matching", lambda *_: (
            {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}}},
            {1: {"employer_id": None, "wage": 0.0}},
        ))
        monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *_: {
            1: {"planned_purchases": {1: 2.0} if economy.current_tick == 5 else {},
                "budget": 20.0 if economy.current_tick == 5 else 0.0}
        })
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: 0)
        monkeypatch.setattr(economy, "_enqueue_healthcare_requests", lambda: None)

        rd = []
        original_rd = firm.apply_rd_and_quality_update

        def observe_rd(revenue, **kwargs):
            before = (firm.cash_balance, firm.accumulated_rd_investment, firm.quality_level)
            assert firm.net_profit == pytest.approx(20.0)
            assert not firm.survival_mode
            actual = original_rd(revenue, **kwargs)
            rd.append((before, kwargs, actual))
            return actual

        patch_agent_method(monkeypatch, firm, "apply_rd_and_quality_update", observe_rd)
        close = []
        original_close = economy._phase_institutional_close

        def observe_close(tick):
            before = (gov.cash_balance, economy.misc_firm_revenue)
            original_close(tick)
            close.append((gov.cash_balance - before[0], economy.misc_firm_revenue - before[1]))

        monkeypatch.setattr(economy, "_phase_institutional_close", observe_close)
        opening = total_money_net_of_injections(economy)
        creditor_before = gov.cash_balance if route == "direct_treasury" else economy.bank.cash_reserves
        economy.step()
        assert len(rd) == 1
        (cash, accumulated, quality), kwargs, actual = rd[0]
        assert cash == pytest.approx(remainder)
        assert kwargs == {"available_cash": cash}
        assert actual == pytest.approx(remainder)
        assert firm.cash_balance == pytest.approx(0.0, abs=1e-10)
        assert firm.accumulated_rd_investment == pytest.approx(accumulated + actual)
        assert firm.quality_level == pytest.approx(quality + actual * firm.quality_improvement_per_rd_dollar - firm.quality_decay_rate)
        investment_tax = actual * gov.investment_tax_rate
        after_tax = actual - investment_tax
        rate = random.Random(cfg.random_seed + 5 * 2_038_073 + int(after_tax * 100)).uniform(0.0, 0.20)
        misc_tax = after_tax * rate
        pool = after_tax - misc_tax
        assert close[0] == pytest.approx((investment_tax + misc_tax, pool), abs=1e-10)
        creditor_after = gov.cash_balance if route == "direct_treasury" else economy.bank.cash_reserves
        assert creditor_after - creditor_before == pytest.approx(due + (close[0][0] if route == "direct_treasury" else 0.0))
        assert total_money_net_of_injections(economy) == pytest.approx(opening, abs=1e-9, rel=0)

        # Real zero-cash-streak updates and real exit settlement, with all
        # holds/pool/outside injections included at every completed boundary.
        # Performance mode retains the first basket for its existing five-tick
        # cache interval, so the last sale can be four ticks later.
        for offset in range(cfg.market.zero_cash_max_streak + 4):
            economy.step()
            if offset == 0:
                assert buyer.last_tick_ledger.get("redistribution", 0.0) == pytest.approx(pool)
            assert firm.cash_balance >= -1e-10
            assert total_money_net_of_injections(economy) == pytest.approx(opening, abs=1e-9, rel=0)
        assert firm not in economy.firms
        assert firm.zero_cash_streak == cfg.market.zero_cash_max_streak
        assert buyer.last_tick_ledger.get("redistribution", 0.0) == 0.0
        assert economy.misc_firm_revenue == pytest.approx(0.0, abs=1e-10)
