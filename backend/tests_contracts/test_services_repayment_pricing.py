"""Existing loan obligations inform asking prices without changing settlement."""
import pytest

from config import clone_config, use_config


def priced_salon(factory, *, bank=0.0, infrastructure=0.0, treasury=0.0, remaining=1000.0):
    firm = factory.firm(firm_id=90, category="Services", is_baseline=False,
        employees=[1, 2], actual_wages={1: 50.0, 2: 50.0}, production_capacity_units=2.0,
        cash_balance=10000.0, owners=[], ceo_household_id=None)
    firm.last_units_produced = 10.0
    firm.price, firm.markup, firm.min_price = 15.0, 0.5, 0.01
    firm.bank_loan_payment_per_tick = bank
    firm.bank_loan_remaining = 1000.0 if bank else 0.0
    firm.service_infrastructure_loan_payment_per_tick = infrastructure
    firm.loan_payment_per_tick = treasury
    firm.government_loan_remaining = remaining if treasury else 0.0
    firm.pricing_profit_tax_rate_known = True
    firm.pricing_profit_tax_rate = 0.2
    return firm


@pytest.mark.parametrize("sequence", ("income_first", "income_late"))
@pytest.mark.parametrize("bank,infrastructure,treasury,remaining,expected", (
    (0.0, 0.0, 0.0, 0.0, 0.0),
    (20.0, 20.0, 0.0, 0.0, 20.0),
    (50.0, 20.0, 30.0, 1000.0, 80.0),
    (0.0, 0.0, 30.0, 1000.0, 30.0),
    (50.0, 20.0, 30.0, 5.0, 55.0),
))
def test_planned_quote_accounts_for_existing_repayments_once(
    factory, sequence, bank, infrastructure, treasury, remaining, expected,
):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = priced_salon(factory, bank=bank, infrastructure=infrastructure,
                            treasury=treasury, remaining=remaining)
        old_finances = (firm.cash_balance, firm.last_profit, firm.government_loan_remaining, firm.bank_loan_remaining)
        plan = firm.plan_pricing(0.85, 0.1)
        cost = (100.0 + expected) / 10.0
        assert plan["price_next"] == pytest.approx(15.0 * 0.8 + cost * 1.625 * 0.2)
        assert plan["service_pricing_cost_basis"] == pytest.approx(cost)
        assert firm.decision_diagnostics["service_debt_service_for_pricing"] == pytest.approx(expected)
        assert (firm.cash_balance, firm.last_profit, firm.government_loan_remaining, firm.bank_loan_remaining) == old_finances


@pytest.mark.parametrize("sequence", ("income_first", "income_late"))
def test_completed_treasury_repayment_stops_affecting_the_quote(factory, sequence):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = priced_salon(factory, treasury=30.0, remaining=5.0)
        economy = factory.economy(households=[], firms=[firm])
        opening = firm.cash_balance + economy.government.cash_balance
        assert economy._payment_collect_direct_firm_loans() == 5.0
        assert firm.government_loan_remaining == 0.0
        assert firm.cash_balance + economy.government.cash_balance == pytest.approx(opening)
        # The existing collection path can retain the old scheduled amount.
        assert firm.loan_payment_per_tick == 30.0
        plan = firm.plan_pricing(0.85, 0.1)
        assert plan["service_pricing_cost_basis"] == 10.0
        assert plan["price_next"] == pytest.approx(15.25)


@pytest.mark.parametrize("sequence", ("income_first", "income_late"))
def test_repayment_target_is_stable_and_does_not_force_a_checkout_price(factory, sequence):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = priced_salon(factory, bank=50.0, infrastructure=20.0, treasury=30.0)
        economy = factory.economy(households=[], firms=[firm])
        # Existing transaction-floor institution only uses infrastructure dues.
        assert economy._effective_market_price(firm, 10.0) == pytest.approx(18.0)
        for _ in range(104):
            plan = firm.plan_pricing(0.85, 0.1)
            firm.apply_price_and_wage_updates(plan, {"wage_offer_next": firm.wage_offer})
        assert firm.price == pytest.approx(29.25, abs=1e-6)
        assert firm.service_target_markup_after_tax == 0.5


def test_final_bank_installment_is_limited_to_remaining_debt(factory):
    firm = priced_salon(factory, bank=50.0, infrastructure=20.0)
    firm.bank_loan_remaining = 7.0
    assert firm.plan_pricing(0.85, 0.1)["service_pricing_cost_basis"] == pytest.approx(10.7)


@pytest.mark.parametrize("sequence", ("income_first", "income_late"))
def test_stabilized_markup_uses_the_repayment_aware_planning_basis(factory, sequence):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = priced_salon(factory, bank=50.0, infrastructure=20.0, treasury=30.0)
        firm.price, firm.unit_cost = 20.0, 1.0
        economy = factory.economy(households=[], firms=[firm])
        economy.government.price_stabilization_target = "Services"
        economy.government.price_stabilization_level = "soft"
        plan = firm.plan_pricing(0.85, 0.1)
        economy._apply_price_stabilization_to_plan(firm, plan)
        assert plan["price_next"] == pytest.approx(20.60)
        assert plan["markup_next"] == pytest.approx(20.60 / 18.0 - 1.0)
        assert firm.service_target_markup_after_tax == 0.5
