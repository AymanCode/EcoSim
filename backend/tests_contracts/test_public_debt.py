"""Round 1 G1: public debt held by the bank.

The treasury borrows its end-of-spending shortfall from the bank when the
bank can lend, pays weekly interest at the bank's rate plus a debt/GDP
premium, and repays from cash above a one-week working balance. When the
bank cannot lend, the shortfall stays as negative treasury cash, as on main.
The flag is off by default; these tests turn it on unless they say otherwise.
"""

import dataclasses
import math

import pytest

from agents import BankAgent, GovernmentAgent
from config import CONFIG, SimulationConfig
from tests_contracts.factories import make_economy


@pytest.fixture(autouse=True)
def _debt_on(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_enabled", True)
    monkeypatch.setattr(CONFIG.government, "public_debt_borrow_target", "zero")


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


def test_default_is_off():
    assert SimulationConfig().government.public_debt_enabled is False
    assert SimulationConfig().government.public_debt_borrow_target == "zero"


def test_flag_off_is_main_behavior(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_enabled", False)
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=100_000.0)
    gov.settle_public_debt(bank)
    assert gov.pay_public_debt_interest(bank, 30_000.0) == 0.0
    assert gov.cash_balance == pytest.approx(-10_000.0)
    assert gov.public_debt == 0.0 and bank.cash_reserves == pytest.approx(100_000.0)


def test_flag_off_mid_run_keeps_servicing_existing_debt(monkeypatch):
    """Turning the flag off stops new borrowing; it does not freeze old debt."""
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=100_000.0)
    gov.settle_public_debt(bank)
    assert gov.public_debt == pytest.approx(10_000.0)
    monkeypatch.setattr(CONFIG.government, "public_debt_enabled", False)
    assert gov.pay_public_debt_interest(bank, 30_000.0) > 0.0  # interest still owed
    gov.cash_balance = -5_000.0
    assert gov.settle_public_debt(bank)["borrowed"] == 0.0  # no new borrowing
    assert gov.cash_balance < -5_000.0 + 1e-9
    gov.cash_balance = 50_000.0
    assert gov.settle_public_debt(bank)["repaid"] == pytest.approx(10_000.0)  # repaid from surplus
    assert gov.public_debt == 0.0 and bank.public_debt_held == 0.0


def test_debt_rate_reads_zero_without_debt():
    gov = GovernmentAgent(cash_balance=50_000.0)
    bank = BankAgent(cash_reserves=100_000.0, base_interest_rate=0.03)
    assert gov.pay_public_debt_interest(bank, 30_000.0) == 0.0
    assert gov.last_tick_debt_rate == 0.0


def test_buffer_target_borrows_up_to_the_working_balance(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_borrow_target", "buffer")
    gov = GovernmentAgent(cash_balance=-10_000.0)
    gov.last_tick_spending = 4_000.0  # one week of spending
    bank = BankAgent(cash_reserves=100_000.0)
    before = _money(gov, bank)
    result = gov.settle_public_debt(bank)
    assert result["borrowed"] == pytest.approx(14_000.0)
    assert gov.cash_balance == pytest.approx(4_000.0) and result["repaid"] == 0.0
    assert _money(gov, bank) == pytest.approx(before)
    # While debt is owed, cash below the buffer is topped up again.
    gov.cash_balance = 1_000.0
    assert gov.settle_public_debt(bank)["borrowed"] == pytest.approx(3_000.0)
    # With no debt and non-negative cash nothing is borrowed (as on main).
    fresh = GovernmentAgent(cash_balance=1_000.0)
    fresh.last_tick_spending = 4_000.0
    assert fresh.settle_public_debt(bank)["borrowed"] == 0.0


@pytest.mark.parametrize("name", ["public_debt_risk_premium", "public_debt_cash_buffer_weeks"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -0.01])
def test_config_rejects_non_finite_or_negative_debt_params(name, bad):
    gov_cfg = dataclasses.replace(SimulationConfig().government, **{name: bad})
    with pytest.raises(ValueError, match=name):
        SimulationConfig(government=gov_cfg)


def test_config_rejects_unknown_borrow_target():
    gov_cfg = dataclasses.replace(SimulationConfig().government, public_debt_borrow_target="max")
    with pytest.raises(ValueError, match="public_debt_borrow_target"):
        SimulationConfig(government=gov_cfg)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1.0])
def test_runtime_debt_params_are_checked_too(monkeypatch, bad):
    gov = GovernmentAgent(cash_balance=0.0)
    gov.public_debt = 10_000.0
    bank = BankAgent(cash_reserves=100_000.0)
    monkeypatch.setattr(CONFIG.government, "public_debt_risk_premium", bad)
    with pytest.raises(ValueError, match="public_debt_risk_premium"):
        gov.pay_public_debt_interest(bank, 30_000.0)


def test_zero_params_are_valid_edges(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_debt_risk_premium", 0.0)
    monkeypatch.setattr(CONFIG.government, "public_debt_cash_buffer_weeks", 0.0)
    gov = GovernmentAgent(cash_balance=5_000.0)
    gov.public_debt = 52_000.0
    gov.last_tick_spending = 9_999.0
    bank = BankAgent(cash_reserves=100_000.0, base_interest_rate=0.03)
    assert gov.pay_public_debt_interest(bank, 1_000.0) == pytest.approx(52_000.0 * 0.03 / 52)
    assert gov.settle_public_debt(bank)["repaid"] == pytest.approx(gov.cash_balance + gov.last_tick_debt_repaid)


def test_a_tick_that_starts_in_deficit_borrows_and_reports_debt_metrics():
    """Economy.step() with the flag on: the loan is realized on both books."""
    economy = make_economy(num_households=20, seed=7)
    economy.bank = BankAgent(cash_reserves=1_000_000.0)
    economy.government.cash_balance = -50_000.0
    economy.step()
    gov, bank = economy.government, economy.bank
    assert gov.last_tick_debt_borrowed > 0.0
    assert gov.public_debt == pytest.approx(gov.last_tick_debt_borrowed)
    assert bank.public_debt_held == pytest.approx(gov.public_debt)
    assert gov.cash_balance >= -1e-6  # the deficit was financed, not left as overdraft
    # The next tick pays interest to the bank on that debt.
    debt = gov.public_debt
    economy.step()
    assert gov.last_tick_debt_interest == pytest.approx(debt * gov.last_tick_debt_rate / 52.0)
    assert gov.last_tick_debt_interest > 0.0
    assert bank.last_tick_interest_income >= gov.last_tick_debt_interest - 1e-9
    metrics = economy.get_economic_metrics()
    assert metrics["public_debt"] == pytest.approx(gov.public_debt)
    assert metrics["annualized_debt_to_gdp"] > 0.0
    assert metrics["gov_debt_borrowed_this_tick"] == pytest.approx(gov.last_tick_debt_borrowed)


def test_bank_books_record_public_debt_as_an_asset():
    gov = GovernmentAgent(cash_balance=-10_000.0)
    bank = BankAgent(cash_reserves=100_000.0, total_deposits=80_000.0)
    equity_before = bank.equity
    gov.settle_public_debt(bank)
    assert bank.public_debt_held == pytest.approx(gov.public_debt) == pytest.approx(10_000.0)
    assert bank.loan_book == pytest.approx(bank.total_loans_outstanding + 10_000.0)
    assert bank.total_assets == pytest.approx(100_000.0)  # reserves turned into a claim
    assert bank.equity == pytest.approx(equity_before)  # lending does not make the bank poorer
    gov.cash_balance = 100_000.0
    gov.settle_public_debt(bank)
    assert gov.public_debt == 0.0 and bank.public_debt_held == 0.0
    assert bank.equity == pytest.approx(equity_before)


def test_bank_equity_grows_by_the_interest_it_earns():
    gov = GovernmentAgent(cash_balance=50_000.0)
    bank = BankAgent(cash_reserves=100_000.0, total_deposits=80_000.0, base_interest_rate=0.03)
    gov.public_debt = bank.public_debt_held = 52_000.0
    before = bank.equity
    interest = gov.pay_public_debt_interest(bank, 1e9)
    assert bank.equity == pytest.approx(before + interest)


def test_public_debt_counts_in_the_thin_loan_book_check():
    bank = BankAgent(cash_reserves=100_000.0, total_deposits=100_000.0)
    bank.last_tick_interest_income = 1e6  # keep the sustainability cap out of the way
    bank.update_deposit_rate()
    thin = bank.deposit_rate
    bank.public_debt_held = 10_000.0  # loan/deposit 0.10, above the 0.05 thin-book line
    bank.update_deposit_rate()
    assert bank.deposit_rate == pytest.approx(4.0 * thin)


def test_seeded_run_keeps_bank_and_treasury_books_in_step():
    economy = make_economy(num_households=30, seed=5)
    economy.bank = BankAgent(cash_reserves=500_000.0)
    economy.government.cash_balance = -50_000.0
    peak = 0.0
    for _ in range(6):
        economy.step()
        assert economy.bank.public_debt_held == pytest.approx(economy.government.public_debt)
        peak = max(peak, economy.government.public_debt)
    assert peak > 0.0
    metrics = economy.get_economic_metrics()
    assert metrics["bank_public_debt_held"] == pytest.approx(economy.government.public_debt)
    assert metrics["bank_equity"] == pytest.approx(economy.bank.equity)
