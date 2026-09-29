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
    # Amortized total (audit A4): 10 installments at 10%/52 per tick.
    total = loan["remaining"]
    interest_share = (total - 100) / total
    before = bank.cash_reserves + gov.cash_balance
    assert bank.collect_repayment(loan, 2.75, gov) == 2.75
    assert bank.cash_reserves + gov.cash_balance == pytest.approx(before + 2.75)
    assert loan["remaining"] == pytest.approx(total - 2.75)
    assert bank.total_loans_outstanding == pytest.approx(total - 2.75)
    assert bank.last_tick_repayments == pytest.approx(2.75)
    assert bank.last_tick_interest_income == pytest.approx(0 if treasury_funded else 2.75 * interest_share)
    assert bank.last_tick_government_interest_income == pytest.approx(2.75 * interest_share if treasury_funded else 0)
    assert bank.last_tick_government_repayments == pytest.approx(2.75 if treasury_funded else 0)
    # Overpayment is capped, zero collection does not count another instalment.
    assert bank.collect_repayment(loan, 1000, gov) == pytest.approx(total - 2.75)
    term = loan["term_remaining"]
    assert bank.collect_repayment(loan, 11, gov) == 0
    assert loan["term_remaining"] == term
    assert bank.total_loans_outstanding == pytest.approx(0)
    assert bank.last_tick_interest_income + bank.last_tick_government_interest_income == pytest.approx(total - 100)
    bank.reset_tick_telemetry()
    assert bank.last_tick_government_repayments == bank.last_tick_government_interest_income == 0


def test_missing_treasury_recipient_fails_before_mutation():
    bank, gov = BankAgent(), GovernmentAgent(cash_balance=1000)
    loan = bank.issue_government_backed_loan("firm", 1, 100, 0.1, 10, gov)
    before = copy.deepcopy((loan, bank))
    with pytest.raises(ValueError, match="recipient"):
        bank.collect_repayment(loan, 11)
    assert (loan, bank) == before


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


def test_legacy_direct_treasury_firm_loan_amortizes_over_its_term():
    """Phase 4 follow-up: the legacy treasury fallback charges the amortized installment."""
    from config import CONFIG
    from payment_loans import v2_payment
    from tests_contracts.factories import make_economy, make_firm

    firm = make_firm(firm_id=5, category="Food", is_baseline=False, cash_balance=0.0)
    economy = make_economy(firms=[firm], num_households=3)
    economy.government.cash_balance = 50_000.0
    assert economy.bank is None and economy.payment_sequence == "legacy"

    funded = economy._issue_firm_loan(firm, amount=10_000.0, term_ticks=104, govt_rate=0.04, spread=0.04)

    installment = v2_payment(10_000.0, 0.04, 104, int(CONFIG.time.ticks_per_year))
    assert funded == 10_000.0
    assert firm.loan_payment_per_tick == pytest.approx(installment)
    assert firm.government_loan_remaining == pytest.approx(installment * 104)


def test_legacy_no_bank_new_firm_treasury_seed_amortizes_over_its_term(monkeypatch):
    """Phase 4 follow-up: the no-bank government-backed entrant seed amortizes over 156 ticks."""
    import random

    import economy as economy_module
    from config import CONFIG
    from payment_loans import v2_payment
    from tests_contracts.factories import make_economy, make_firm, make_households

    firms = [make_firm(firm_id=i, category=c, is_baseline=False)
             for i, c in enumerate(("Housing", "Food", "Services"), start=1)]
    economy = make_economy(households=make_households(5), firms=firms, baseline_firms=False)
    economy.in_warmup = False
    economy.current_tick = 20
    economy.target_total_firms = 100
    economy.government.cash_balance = 500_000.0
    assert economy.bank is None

    class LowRoll(random.Random):
        def random(self):  # every roll picks the government-backed tier
            return 0.0

    monkeypatch.setattr(economy_module.random, "Random", LowRoll)
    economy._maybe_create_new_firms()
    monkeypatch.undo()

    entrant = economy.firms[-1]
    assert entrant.firm_id == 4 and entrant.government_loan_principal > 0.0
    installment = v2_payment(entrant.government_loan_principal, 0.01, 156, int(CONFIG.time.ticks_per_year))
    assert entrant.loan_payment_per_tick == pytest.approx(installment)
    assert entrant.government_loan_remaining == pytest.approx(installment * 156)


def test_legacy_long_term_capital_loan_is_in_firm_loan_mirrors():
    """Phase 4 follow-up: a legacy long-term capital loan is in the firm's bank-loan mirrors
    from origination until its final payment."""
    from agents import BankAgent
    from config import CONFIG
    from tests_contracts.factories import make_economy, make_firm, make_firms, make_government, make_households

    government = make_government()
    firms = make_firms(("Food", "Healthcare"), num_per_category=1, government=government)
    services = make_firm(firm_id=10, category="Services", is_baseline=False)
    services.lost_sales_streak = 5
    firms.append(services)
    economy = make_economy(households=make_households(30, skills_start=0.6, skills_step=0.0),
                           firms=firms, government=government, seed=333)
    economy.bank = BankAgent(cash_reserves=50_000.0)
    assert economy.payment_sequence == "legacy"

    economy.step()

    loans = [loan for loan in economy.bank.loans_for("firm", services.firm_id)
             if loan.get("subtype") == "long_term_capital"]
    assert len(loans) == 1, "precondition: the services firm did not receive a long-term loan"
    loan = loans[0]
    # Originated in firm planning and first serviced in this tick's bank collection.
    assert loan["term_remaining"] == int(CONFIG.firms.long_term_capital_term_ticks) - 1
    assert services.bank_loan_principal == pytest.approx(loan["principal"])
    assert services.bank_loan_remaining == pytest.approx(loan["remaining"])
    assert services.bank_loan_payment_per_tick == pytest.approx(loan["payment_per_tick"])

    # Final installment: the mirrors drop the loan when it is paid off.
    loan["remaining"] = loan["payment_per_tick"]
    services.bank_loan_remaining = loan["remaining"]
    services.cash_balance = 10_000.0
    economy._collect_bank_loan_repayments()
    assert loan["remaining"] == 0.0
    assert services.bank_loan_remaining == pytest.approx(0.0)
    assert services.bank_loan_payment_per_tick == pytest.approx(0.0)
