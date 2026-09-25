"""Payroll, reserved public benefits and protected exit cash in the payment arm."""

import pytest

from config import clone_config, use_config
from payments import PaymentBook
from payments import proportional


def test_current_wages_before_old_claims_and_progressive_tax_on_total_paid(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        workers = [factory.household(household_id=hid, employer_id=1, wage=40.0, cash_balance=0.0)
                   for hid in (1, 2)]
        firm = factory.firm(firm_id=1, employees=[1, 2], actual_wages={1: 40.0, 2: 40.0},
                            cash_balance=60.0, ceo_household_id=None)
        govt = factory.government(cash_balance=0.0, wage_tax_rate=0.0)
        economy = factory.economy(households=workers, firms=[firm], government=govt)
        book = PaymentBook(economy)
        book.settle_income({1: 40.0, 2: 40.0})
        assert firm.cash_balance == pytest.approx(0.0)
        assert [h.cash_balance for h in workers] == pytest.approx([30.0, 30.0])
        assert economy.payment_state["wage_claims"] == pytest.approx({(1, 1): 10.0, (1, 2): 10.0})
        assert [book.unpaid_employed[i]["duration"] for i in (1, 2)] == [1, 1]
        firm.cash_balance = 100.0
        book2 = PaymentBook(economy)
        book2.settle_income({1: 40.0, 2: 40.0})
        assert firm.cash_balance == pytest.approx(0.0)
        assert [h.cash_balance for h in workers] == pytest.approx([80.0, 80.0])
        assert not economy.payment_state["wage_claims"]
        assert not book2.unpaid_employed


def test_benefit_shortage_pro_rata_leaves_denial_without_public_debt(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_late"
    with use_config(cfg):
        people = [factory.household(household_id=hid, employer_id=None, cash_balance=0.0) for hid in (1, 2, 3)]
        govt = factory.government(cash_balance=100.0, unemployment_benefit_level=50.0)
        economy = factory.economy(households=people, firms=[], government=govt)
        govt.unemployment_benefit_level = 50.0
        economy.payment_state["restrictions"]["B"] = 100.0
        book = PaymentBook(economy, timing="income_late")
        book.settle_benefits()
        assert sum(book.benefits.values()) == pytest.approx(100.0)
        assert book.denied_benefits == pytest.approx(50.0)
        assert govt.cash_balance == pytest.approx(0.0)
        assert sum(h.cash_balance for h in people) == 0.0
        book.release_late_income()
        assert sum(h.cash_balance for h in people) == pytest.approx(100.0)
        assert all(h.last_tick_ledger["transfers"] > 0 for h in people)


def test_exit_recovery_stays_protected_until_next_tax_clock(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=30.0, cash_balance=0.0)
        firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 30.0},
                            cash_balance=10.0, zero_cash_streak=100, ceo_household_id=None)
        govt = factory.government(cash_balance=0.0, wage_tax_rate=0.0)
        economy = factory.economy(households=[worker], firms=[firm], government=govt)
        economy.payment_state["wage_claims"][(1, 1)] = 30.0
        economy.payment_book = PaymentBook(economy)
        assert economy._handle_firm_exits() == 1
        assert firm.cash_balance == pytest.approx(0.0)
        assert economy.payment_state["recovery_holds"] == pytest.approx({1: 10.0})
        assert economy.payment_state["wage_claims"] == {}
        assert worker.cash_balance == pytest.approx(0.0)
        assert economy.payment_book.exit_worker_writeoff == pytest.approx(20.0)
        economy.payment_book = PaymentBook(economy)
        economy.payment_book.settle_income({1: 0.0})
        assert worker.cash_balance == pytest.approx(10.0)
        assert economy.payment_state["recovery_holds"] == {}


def test_many_worker_scarce_payroll_never_makes_negative_residual(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        workers = [factory.household(household_id=hid, employer_id=1, wage=13.7, cash_balance=0.0)
                   for hid in range(1, 1001)]
        firm = factory.firm(firm_id=1, employees=list(range(1, 1001)),
                            actual_wages={hid: 13.7 for hid in range(1, 1001)},
                            cash_balance=17.17, ceo_household_id=None)
        economy = factory.economy(households=workers, firms=[firm],
                                  government=factory.government(cash_balance=0.0, wage_tax_rate=0.0))
        book = PaymentBook(economy)
        book.settle_income({hid: 13.7 for hid in range(1, 1001)})
        assert firm.cash_balance >= -1e-9
        assert sum(book.current_paid_by_firm_worker.values()) <= 17.17 + 1e-9
        assert all(amount >= 0 for amount in book.current_paid_by_firm_worker.values())
        with pytest.raises(ValueError):
            proportional({1: 2.0}, -1e-12)


def test_new_entry_defers_without_real_funding_then_debits_founder_once(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        founder = factory.household(household_id=1, cash_balance=1000.0)
        landlord = factory.firm(firm_id=1, category="Housing", max_rental_units=10)
        economy = factory.economy(households=[founder], firms=[landlord],
                                  government=factory.government(cash_balance=0.0))
        economy.in_warmup = False
        economy.current_tick = economy.warmup_ticks + 1
        economy.target_total_firms = 4
        economy.payment_book = PaymentBook(economy)
        economy._maybe_create_new_firms()
        assert len(economy.firms) == 1
        assert founder.cash_balance == 1000.0
        founder.cash_balance = 6000.0
        economy._maybe_create_new_firms()
        assert len(economy.firms) == 2
        assert economy.firms[-1].cash_balance == 5000.0
        assert economy.firms[-1].owners == [1]
        assert founder.cash_balance == 1000.0


def test_exit_workers_then_actual_lenders_and_landlord_unlink(factory):
    from agents import BankAgent
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, cash_balance=0.0,
                                   renting_from_firm_id=1, monthly_rent=10.0, rent_arrears=5.0)
        owner = factory.household(household_id=2, cash_balance=0.0)
        firm = factory.firm(firm_id=1, category="Housing", is_baseline=False,
                            employees=[1], actual_wages={1: 30.0}, cash_balance=50.0,
                            zero_cash_streak=100, owners=[2], government_loan_remaining=20.0)
        economy = factory.economy(households=[worker, owner], firms=[firm],
                                  government=factory.government(cash_balance=0.0))
        economy.bank = BankAgent(cash_reserves=1000.0)
        economy.payment_book = PaymentBook(economy)
        loan = economy.bank.originate_loan("firm", 1, 80.0, 0.0, 10)
        firm.bank_loan_remaining = loan["remaining"]
        economy.payment_state["wage_claims"][(1, 1)] = 30.0
        from payment_loans import preflight_loans
        preflight_loans(economy)
        bank_before, treasury_before = economy.bank.cash_reserves, economy.government.cash_balance
        assert economy._handle_firm_exits() == 1
        assert economy.payment_state["recovery_holds"][1] == pytest.approx(30.0)
        assert economy.bank.cash_reserves - bank_before == pytest.approx(16.0)
        assert economy.government.cash_balance - treasury_before == pytest.approx(4.0)
        assert economy.bank.loan_loss_provision == pytest.approx(64.0)
        assert economy.payment_state["direct_treasury_exit_writeoffs"] == pytest.approx(16.0)
        assert worker.renting_from_firm_id is None
        assert worker.monthly_rent == 0.0 and worker.rent_arrears == 0.0
        assert not economy.bank.active_loans
        assert owner.cash_balance == 0.0


def test_capital_payout_uses_funded_route_once_and_keeps_cash_conserved(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        worker = factory.household(household_id=1, cash_balance=0.0)
        firm = factory.firm(firm_id=1, cash_balance=100.0)
        economy = factory.economy(households=[worker], firms=[firm],
                                  government=factory.government(cash_balance=0.0))
        firm.cash_balance -= 40.0
        economy._payment_record_capital_spend(firm, 40.0, "self_financed")
        firm.capital_investment_this_tick = 999.0  # Stock intent cannot mint cash.
        economy._recycle_capital_investment()
        economy._recycle_capital_investment()
        assert (firm.cash_balance, worker.cash_balance) == pytest.approx((60.0, 40.0))
        assert worker.last_tick_ledger["other"] == pytest.approx(40.0)


def test_exit_mortgage_after_paid_service_does_not_charge_second_week_interest(factory):
    from agents import BankAgent, LoanContract
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    with use_config(cfg):
        tenant = factory.household(household_id=1, renting_from_firm_id=1,
                                   monthly_rent=15.0, owns_housing=True)
        firm = factory.firm(firm_id=1, category="Housing", is_baseline=False,
                            cash_balance=30.0, zero_cash_streak=100,
                            current_tenants=[1], rent_arrears_receivable_by_tenant={1: 4.0})
        mortgage = LoanContract(principal_remaining=90.0, pmt_per_tick=10.0,
                                ticks_remaining=20, origination_tick_rate=0.01)
        firm.housing_active_loans = [mortgage]
        firm.bank_loan_remaining = 90.0
        economy = factory.economy(households=[tenant], firms=[firm],
                                  government=factory.government(cash_balance=0.0))
        economy.bank = BankAgent(cash_reserves=1000.0)
        economy.payment_book = PaymentBook(economy)
        assert economy._handle_firm_exits() == 1
        assert economy.bank.cash_reserves == pytest.approx(1030.0)
        assert economy.bank.loan_loss_provision == pytest.approx(60.0)
        assert mortgage.principal_remaining == 0.0
        assert firm.current_tenants == [] and firm.rent_arrears_receivable_by_tenant == {}
        assert tenant.renting_from_firm_id is None and not tenant.owns_housing


def test_demand_shock_posts_to_treasury_and_preserves_benefit_restriction(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.random_seed = 42
    with use_config(cfg):
        households = [factory.household(household_id=hid, cash_balance=100.0)
                      for hid in range(1, 101)]
        economy = factory.economy(households=households, firms=[],
                                  government=factory.government(cash_balance=2000.0), seed=42, disable_shocks=False)
        economy.in_warmup = False
        economy.payment_state["restrictions"]["B"] = 1300.0
        before = sum(h.cash_balance for h in households) + economy.government.cash_balance
        economy.current_tick = 27  # Seed 42 positive shock.
        economy._apply_random_shocks()
        after = sum(h.cash_balance for h in households) + economy.government.cash_balance
        assert after == pytest.approx(before)
        assert economy.government.cash_balance >= 1300.0 - 1e-6
        assert economy.payment_state["last_positive_shock_funded"] == pytest.approx(700.0)
        assert economy.payment_state["last_positive_shock_denied"] > 0.0
        economy.current_tick = 34  # Seed 42 negative shock.
        before = after
        economy._apply_random_shocks()
        after = sum(h.cash_balance for h in households) + economy.government.cash_balance
        assert after == pytest.approx(before)
        assert economy.payment_state["last_negative_shock_collected"] > 0.0
