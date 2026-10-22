"""The shared money helper counts the cash the payment sequences hold in transit.

``total_money_net_of_injections`` (``tests_contracts/conftest.py``) is the money
stock the conservation tests and the evidence panel's money check read. Cash a
payment sequence parks in a hold is still money; before the helper counted the
holds, a run that ended with cash in one reported it as a leak.
"""

import pytest

from agents import BankAgent
from config import clone_config, use_config
from payments import PaymentBook
from tests_contracts.conftest import payment_holds, total_money_net_of_injections


def test_income_late_benefits_waiting_for_release_are_still_money(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_late"
    with use_config(cfg):
        people = [factory.household(household_id=hid, employer_id=None, cash_balance=0.0) for hid in (1, 2, 3)]
        govt = factory.government(cash_balance=100.0, unemployment_benefit_level=50.0)
        economy = factory.economy(households=people, firms=[], government=govt)
        govt.unemployment_benefit_level = 50.0
        economy.payment_state["restrictions"]["B"] = 100.0
        book = PaymentBook(economy, timing="income_late")
        economy.payment_book = book
        before = total_money_net_of_injections(economy)

        book.settle_benefits()
        # The treasury has paid; no household holds the money until release.
        assert govt.cash_balance == pytest.approx(0.0)
        assert sum(h.cash_balance for h in people) == 0.0
        assert sum(book.late_income.values()) == pytest.approx(100.0)
        assert total_money_net_of_injections(economy) == pytest.approx(before)

        book.release_late_income()
        assert payment_holds(economy) == pytest.approx(0.0)
        assert total_money_net_of_injections(economy) == pytest.approx(before)


def test_helper_counts_every_hold_total_economy_cash_counts(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        people = [factory.household(household_id=hid, cash_balance=100.0) for hid in (1, 2)]
        firm = factory.firm(firm_id=1, cash_balance=500.0)
        govt = factory.government(cash_balance=1000.0)
        economy = factory.economy(households=people, firms=[firm], government=govt)
        economy.payment_book = PaymentBook(economy)
        book = economy.payment_book
        state = economy.payment_state

        def metrics_gap() -> float:
            metrics = economy.get_economic_metrics()
            helper = total_money_net_of_injections(economy) + float(economy.external_injection_total)
            return metrics["total_economy_cash"] - helper

        start = total_money_net_of_injections(economy)
        assert metrics_gap() == pytest.approx(0.0)

        def hold(source, amount, place):
            source.cash_balance -= amount
            place(amount)
            assert total_money_net_of_injections(economy) == pytest.approx(start)
            assert metrics_gap() == pytest.approx(0.0)

        # A firm exit's recovered wages wait for the next settlement.
        hold(firm, 10.0, lambda amount: state["recovery_holds"].__setitem__(1, amount))
        hold(people[0], 5.0, lambda amount: book.late_income.__setitem__(1, amount))
        hold(people[1], 7.0, lambda amount: setattr(book, "clearing_cash", book.clearing_cash + amount))
        hold(firm, 3.0, lambda amount: state["ceo_holds"].__setitem__(2, amount))
        hold(firm, 11.0, lambda amount: state.__setitem__("housing_equal_distribution_hold", amount))
        hold(govt, 2.0, lambda amount: book.medical_funding_pending.__setitem__(1, amount))

        def route(amount):
            state["capital_routes"] = [{"amount": amount}]
            state["capital_routes_released"] = False

        hold(firm, 13.0, route)
        assert payment_holds(economy) == pytest.approx(51.0)


def test_legacy_has_no_holds(factory):
    economy = factory.economy(households=[factory.household(household_id=1)], firms=[])
    economy.payment_state["recovery_holds"][1] = 99.0
    assert economy.payment_sequence == "legacy"
    assert payment_holds(economy) == 0.0


@pytest.mark.parametrize("target", ["zero", "buffer"])
def test_public_debt_borrow_interest_and_repayment_conserve_shared_money(factory, target):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.government.public_debt_enabled = True
    cfg.government.public_debt_borrow_target = target
    with use_config(cfg):
        govt = factory.government(cash_balance=-10_000.0)
        economy = factory.economy(government=govt)
        bank = economy.bank = BankAgent(cash_reserves=100_000.0, base_interest_rate=0.03)
        govt.last_tick_spending = 4_000.0
        before = total_money_net_of_injections(economy)

        def assert_stock():
            assert total_money_net_of_injections(economy) == pytest.approx(before)
            assert economy.get_economic_metrics()["total_economy_cash"] == pytest.approx(
                before + economy.external_injection_total
            )
            assert govt.public_debt == pytest.approx(bank.public_debt_held)

        result = govt.settle_public_debt(bank)
        assert result["borrowed"] == pytest.approx(14_000.0 if target == "buffer" else 10_000.0)
        assert_stock()
        assert govt.pay_public_debt_interest(bank, 30_000.0) > 0.0
        assert_stock()

        # Supply repayment cash through a transfer, without introducing outside money.
        bank.cash_reserves -= 20_000.0
        govt.cash_balance += 20_000.0
        assert_stock()
        result = govt.settle_public_debt(bank)
        assert result["repaid"] > 0.0
        assert govt.public_debt == pytest.approx(0.0)
        assert_stock()
