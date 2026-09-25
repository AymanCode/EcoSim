"""Counterparty and single-servicer regressions for W01/W02."""

import copy

import pytest

from agents import BankAgent, GovernmentAgent


@pytest.mark.parametrize("treasury_funded", [False, True])
def test_payment_credits_funder_and_only_earned_interest(treasury_funded):
    bank = BankAgent(cash_reserves=1000.0)
    gov = GovernmentAgent(cash_balance=1000.0)
    loan = (
        bank.issue_government_backed_loan("firm", 1, 100, 0.1, 10, gov)
        if treasury_funded
        else bank.originate_loan("firm", 1, 100, 0.1, 10)
    )
    before = bank.cash_reserves + gov.cash_balance
    assert bank.collect_repayment(loan, 2.75, gov) == 2.75
    assert bank.cash_reserves + gov.cash_balance == pytest.approx(before + 2.75)
    assert loan["remaining"] == pytest.approx(107.25)
    assert bank.total_loans_outstanding == pytest.approx(107.25)
    assert bank.last_tick_repayments == pytest.approx(2.75)
    assert bank.last_tick_interest_income == pytest.approx(0 if treasury_funded else 0.25)
    assert bank.last_tick_government_interest_income == pytest.approx(0.25 if treasury_funded else 0)
    assert bank.last_tick_government_repayments == pytest.approx(2.75 if treasury_funded else 0)
    # Overpayment is capped, zero collection does not count another instalment.
    assert bank.collect_repayment(loan, 1000, gov) == pytest.approx(107.25)
    term = loan["term_remaining"]
    assert bank.collect_repayment(loan, 11, gov) == 0
    assert loan["term_remaining"] == term
    assert bank.total_loans_outstanding == pytest.approx(0)
    assert bank.last_tick_interest_income + bank.last_tick_government_interest_income == pytest.approx(10)
    bank.reset_tick_telemetry()
    assert bank.last_tick_government_repayments == bank.last_tick_government_interest_income == 0


def test_missing_treasury_recipient_fails_before_mutation():
    bank, gov = BankAgent(), GovernmentAgent(cash_balance=1000)
    loan = bank.issue_government_backed_loan("firm", 1, 100, 0.1, 10, gov)
    before = copy.deepcopy((loan, bank.to_dict()))
    with pytest.raises(ValueError, match="recipient"):
        bank.collect_repayment(loan, 11)
    assert (loan, bank.to_dict()) == before


@pytest.mark.parametrize("treasury_funded", [False, True])
def test_firm_repayment_reconciles_cash_and_debt(tiny_economy_factory, treasury_funded):
    eco = tiny_economy_factory(num_households=2)
    eco.bank = BankAgent(cash_reserves=1000)
    firm = eco.firms[0]
    loan = (
        eco.bank.issue_government_backed_loan("firm", firm.firm_id, 100, 0.1, 10, eco.government)
        if treasury_funded
        else eco.bank.originate_loan("firm", firm.firm_id, 100, 0.1, 10)
    )
    firm.cash_balance += 100
    firm.bank_loan_remaining = loan["remaining"]
    before = firm.cash_balance + eco.bank.cash_reserves + eco.government.cash_balance
    eco._collect_bank_loan_repayments()
    assert firm.cash_balance + eco.bank.cash_reserves + eco.government.cash_balance == pytest.approx(before)
    assert firm.bank_loan_remaining == pytest.approx(loan["remaining"])


def medical_economy(factory, treasury_funded):
    eco = factory(num_households=2)
    eco.bank = BankAgent(cash_reserves=0 if treasury_funded else 10000)
    for firm in eco.firms:
        firm.government_loan_remaining = 0
        firm.ceo_household_id = None
    hh = eco.households[0]
    hh.employer_id = None
    hh.wage = 0
    assert eco._issue_medical_loan(hh, 520)
    return eco, hh, eco.bank.active_loans[-1]


@pytest.mark.parametrize("treasury_funded", [False, True])
@pytest.mark.parametrize("cash", [2.0, 10000.0])
def test_medical_collection_then_household_settlement_is_single_payment(tiny_economy_factory, treasury_funded, cash):
    eco, hh, loan = medical_economy(tiny_economy_factory, treasury_funded)
    hh.cash_balance = cash
    initial = loan["remaining"]
    payment = min(cash, loan["payment_per_tick"])
    before = hh.cash_balance + eco.bank.cash_reserves + eco.government.cash_balance
    eco._collect_bank_loan_repayments()
    eco._batch_apply_household_updates({}, {}, {})
    assert hh.cash_balance == pytest.approx(cash - payment)
    assert hh.medical_loan_remaining == pytest.approx(initial - payment)
    assert hh.medical_loan_remaining == pytest.approx(loan["remaining"])
    assert hh.cash_balance + eco.bank.cash_reserves + eco.government.cash_balance == pytest.approx(before)
    assert hh.make_medical_loan_payment() == 0  # Scalar fallback also respects the servicer.


@pytest.mark.parametrize("treasury_funded", [False, True])
def test_medical_payoff_and_default_clear_both_claims(tiny_economy_factory, treasury_funded):
    eco, hh, loan = medical_economy(tiny_economy_factory, treasury_funded)
    hh.cash_balance = 10000
    for _ in range(52):
        eco._collect_bank_loan_repayments()
        eco._batch_apply_household_updates({}, {}, {})
    assert hh.medical_loan_remaining == 0
    assert hh.medical_loan_principal == hh.medical_loan_payment_per_tick == 0
    assert not hh.medical_loan_bank_serviced
    eco.bank.cleanup_settled_loans()
    assert eco.bank.active_loans == []
    assert eco._issue_medical_loan(hh, 100)
    loan = eco.bank.active_loans[-1]
    # Force the desired funder for the second origination by using a fresh economy.
    eco, hh, loan = medical_economy(tiny_economy_factory, treasury_funded)
    remaining = loan["remaining"]
    hh.cash_balance = 0
    before = eco.bank.cash_reserves + eco.government.cash_balance
    for _ in range(8):
        eco._collect_bank_loan_repayments()
        eco._batch_apply_household_updates({}, {}, {})
    assert hh.medical_loan_remaining == loan["remaining"] == 0
    assert hh.medical_loan_principal == hh.medical_loan_payment_per_tick == 0
    assert not hh.medical_loan_bank_serviced
    assert eco.bank.total_loans_outstanding == pytest.approx(0)
    assert eco.bank.cash_reserves + eco.government.cash_balance == before
    assert eco.bank.loan_loss_provision == pytest.approx(0 if treasury_funded else remaining)
    assert eco.bank.government_loan_writeoffs == pytest.approx(remaining if treasury_funded else 0)


def test_legacy_medical_fallback_still_pays_treasury(tiny_economy_factory):
    eco = tiny_economy_factory(num_households=2)
    hh = eco.households[0]
    hh.employer_id = eco.firms[0].firm_id
    hh.wage = 0
    assert eco.bank is None
    assert eco._issue_medical_loan(hh, 100)
    assert not hh.medical_loan_bank_serviced
    cash, debt, gov = hh.cash_balance, hh.medical_loan_remaining, eco.government.cash_balance
    eco._batch_apply_household_updates({}, {}, {})
    paid = cash - hh.cash_balance
    assert paid > 0
    assert hh.medical_loan_remaining == pytest.approx(debt - paid)
    assert eco.government.cash_balance == pytest.approx(gov + paid)


@pytest.mark.parametrize("performance_mode", [False, True])
def test_full_tick_keeps_registered_medical_balances_in_sync(tiny_economy_factory, performance_mode):
    eco, hh, loan = medical_economy(tiny_economy_factory, False)
    eco.performance_mode = performance_mode
    for _ in range(12):
        eco.step()
        assert hh.medical_loan_remaining == pytest.approx(loan["remaining"], abs=1e-6)


def test_consumption_default_does_not_clear_live_medical_schedule(tiny_economy_factory):
    eco, hh, medical = medical_economy(tiny_economy_factory, False)
    consumption = eco.bank.originate_loan("household", hh.household_id, 50, 0.1, 10)
    consumption.update(subtype="consumption", missed_payments=7)
    hh.consumption_loan_remaining = consumption["remaining"]
    hh.cash_balance = 0
    eco._collect_bank_loan_repayments()
    assert consumption["remaining"] == 0
    assert hh.consumption_loan_remaining == 0
    assert hh.medical_loan_payment_per_tick == medical["payment_per_tick"]
    assert hh.medical_loan_bank_serviced
