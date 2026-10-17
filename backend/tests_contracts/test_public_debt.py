"""Round 1 G1: public debt held by the bank.

The treasury borrows its end-of-spending shortfall from the bank when the
bank can lend, pays weekly interest at the bank's rate plus a debt/GDP
premium, and repays from cash above a one-week working balance. When the
bank cannot lend, the shortfall stays as negative treasury cash, as on main.
"""

import pytest

from agents import BankAgent, GovernmentAgent
from config import CONFIG
from tests_contracts.factories import make_economy


def _money(gov: GovernmentAgent, bank: BankAgent) -> float:
    return gov.cash_balance + bank.cash_reserves


def test_shortfall_is_borrowed_and_money_is_conserved():
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=100_000.0)
    before = _money(gov, bank)
    result = gov.settle_public_debt(bank)
    assert result["borrowed"] == pytest.approx(10_000.0)
    assert gov.cash_balance == pytest.approx(0.0)
    assert gov.public_debt == pytest.approx(10_000.0)
    assert _money(gov, bank) == pytest.approx(before)


def test_bank_lends_only_its_lendable_cash():
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=14_000.0, total_deposits=100_000.0)  # requirement 10,000
    result = gov.settle_public_debt(bank)
    assert result["borrowed"] == pytest.approx(4_000.0)
    assert result["unfunded"] == pytest.approx(6_000.0)
    assert gov.cash_balance == pytest.approx(-6_000.0)  # the rest stays negative, as on main
    assert bank.cash_reserves == pytest.approx(bank.required_reserves)


def test_no_lending_when_the_bank_cannot_lend():
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=5_000.0, total_deposits=100_000.0)  # below requirement
    assert not bank.can_lend()
    result = gov.settle_public_debt(bank)
    assert result["borrowed"] == 0.0 and result["unfunded"] == pytest.approx(10_000.0)
    assert gov.cash_balance == pytest.approx(-10_000.0)
    assert gov.public_debt == 0.0
    assert bank.cash_reserves == pytest.approx(5_000.0)


def test_no_bank_means_main_behavior():
    gov = GovernmentAgent(cash_balance=-10_000.0)
    gov.settle_public_debt(None)
    assert gov.pay_public_debt_interest(None, 30_000.0) == 0.0
    assert gov.cash_balance == pytest.approx(-10_000.0) and gov.public_debt == 0.0


def test_interest_is_bank_rate_plus_debt_to_gdp_premium_and_reaches_the_bank():
    gov = GovernmentAgent(cash_balance=50_000.0)
    gov.public_debt = 156_000.0
    bank = BankAgent(cash_reserves=100_000.0, base_interest_rate=0.03)
    weekly_gdp = 30_000.0  # annual 1.56M, so debt/GDP = 0.10
    before = _money(gov, bank)
    interest = gov.pay_public_debt_interest(bank, weekly_gdp)
    expected_rate = 0.03 + CONFIG.government.public_debt_risk_premium * 0.10
    assert gov.last_tick_debt_rate == pytest.approx(expected_rate)
    assert interest == pytest.approx(156_000.0 * expected_rate / 52.0)
    assert bank.last_tick_interest_income == pytest.approx(interest)
    assert _money(gov, bank) == pytest.approx(before)


def test_interest_follows_the_bank_rate_when_it_changes():
    gov = GovernmentAgent(cash_balance=50_000.0)
    gov.public_debt = 52_000.0
    bank = BankAgent(cash_reserves=100_000.0, base_interest_rate=0.03)
    low = gov.pay_public_debt_interest(bank, 1e9)
    bank.base_interest_rate = 0.06
    high = gov.pay_public_debt_interest(bank, 1e9)
    assert high == pytest.approx(2.0 * low, rel=1e-6)


def test_surplus_above_one_week_of_spending_repays_debt():
    gov = GovernmentAgent(cash_balance=30_000.0)
    gov.public_debt = 50_000.0
    gov.last_tick_spending = 12_000.0  # working balance 12,000
    bank = BankAgent(cash_reserves=100_000.0)
    result = gov.settle_public_debt(bank)
    assert result["repaid"] == pytest.approx(18_000.0)
    assert gov.cash_balance == pytest.approx(12_000.0)
    assert gov.public_debt == pytest.approx(32_000.0)


def test_no_bond_buy_while_debt_is_owed_and_main_bond_buy_without_debt():
    gov = GovernmentAgent(cash_balance=200_000.0)
    gov.public_debt = 1_000.0
    assert gov.make_investments()["bonds"] == 0.0
    gov.public_debt = 0.0
    # main's rule: 12% of cash above $50k once that surplus passes $10k
    assert gov.make_investments()["bonds"] == pytest.approx(0.12 * 150_000.0)


def test_flag_off_is_main_behavior(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_enabled", False)
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=100_000.0)
    gov.settle_public_debt(bank)
    assert gov.pay_public_debt_interest(bank, 30_000.0) == 0.0
    assert gov.cash_balance == pytest.approx(-10_000.0)
    assert gov.public_debt == 0.0 and bank.cash_reserves == pytest.approx(100_000.0)


def test_a_tick_that_starts_in_deficit_borrows_and_reports_debt_metrics():
    economy = make_economy(num_households=20, seed=7)
    economy.bank = BankAgent(cash_reserves=1_000_000.0)
    economy.government.cash_balance = -50_000.0
    economy.step()
    gov = economy.government
    assert gov.last_tick_debt_borrowed > 0.0
    assert gov.public_debt > 0.0
    metrics = economy.get_economic_metrics()
    assert metrics["public_debt"] == pytest.approx(gov.public_debt)
    assert metrics["annualized_debt_to_gdp"] > 0.0
    assert metrics["gov_debt_borrowed_this_tick"] == pytest.approx(gov.last_tick_debt_borrowed)
