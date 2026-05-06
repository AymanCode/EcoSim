"""Contract tests for housing mortgage underwriting system (EcoSim 2.0).

Covers:
- PMT formula correctness (amortizing, not simple interest)
- Money conservation: bank reserves → firm cash → misc_firm_revenue
- Per-tick debt service: interest split, principal reduction
- DSCR / LTV rejection gates
- LoanContract appended on approval
"""
import math

import pytest

from agents import BankAgent, LoanContract
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_economy, make_firm, make_household


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOAN_PRINCIPAL = 15_000.0  # realistic single-unit expansion cost


def _pmt(principal: float, annual_rate: float, term_ticks: int) -> float:
    return Economy._compute_housing_pmt(principal, annual_rate, term_ticks)


def _make_bank(**kwargs) -> BankAgent:
    defaults = dict(cash_reserves=500_000.0, base_interest_rate=0.03)
    defaults.update(kwargs)
    return BankAgent(**defaults)


def _arm_firm(firm, *, principal: float = LOAN_PRINCIPAL) -> None:
    """Flag firm for loan-funded expansion with a given principal."""
    firm.needs_housing_expansion_loan = True
    firm.housing_expansion_loan_amount = principal


# ---------------------------------------------------------------------------
# PMT formula
# ---------------------------------------------------------------------------

def test_contract_pmt_formula_total_repayment_exceeds_principal():
    """Total payments over loan life exceed principal (interest charged)."""
    principal = 20_000.0
    annual_rate = 0.03
    term = CONFIG.firms.housing_loan_term_ticks  # 1040
    pmt = _pmt(principal, annual_rate, term)
    assert pmt * term > principal


def test_contract_pmt_formula_zero_rate_equals_principal_over_term():
    """At 0% rate, PMT = principal / term_ticks."""
    principal = 10_000.0
    term = 1040
    pmt = _pmt(principal, 0.0, term)
    assert pmt == pytest.approx(principal / term, rel=1e-6)


def test_contract_pmt_formula_amortizes_correctly():
    """Running the PMT forward manually leaves near-zero balance after term."""
    principal = 10_000.0
    annual_rate = 0.04
    term = 1040
    r = annual_rate / 52.0
    pmt = _pmt(principal, annual_rate, term)
    balance = principal
    for _ in range(term):
        interest = balance * r
        balance -= (pmt - interest)
    assert abs(balance) < 1.0  # residual < $1 (rounding only)


# ---------------------------------------------------------------------------
# Money conservation on loan issuance + builder payment
# ---------------------------------------------------------------------------

def test_contract_loan_issuance_bank_loses_exact_principal():
    """Bank.cash_reserves drops by exactly principal on loan issuance.

    _collect_misc_revenue has a stochastic tax skim (0-20%) so misc_firm_revenue
    gets less than principal; the remainder goes to government.  The bank side is exact.
    """
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=200_000.0)
    eco.bank = bank
    eco.misc_firm_revenue = 0.0

    firm = eco.firms[0]
    assert firm.good_category.lower() == "housing"
    _arm_firm(firm, principal=LOAN_PRINCIPAL)

    bank_before = bank.cash_reserves

    eco._offer_housing_expansion_loans()

    assert bank.cash_reserves == pytest.approx(bank_before - LOAN_PRINCIPAL, rel=1e-6)


def test_contract_money_conserved_bank_loss_equals_economy_gain():
    """Total money conserved: bank loss == misc_firm_revenue + government tax gain."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank
    eco.misc_firm_revenue = 0.0

    firm = eco.firms[0]
    _arm_firm(firm, principal=LOAN_PRINCIPAL)

    bank_before = bank.cash_reserves
    misc_before = eco.misc_firm_revenue
    gov_before = eco.government.cash_balance

    eco._offer_housing_expansion_loans()

    bank_loss = bank_before - bank.cash_reserves
    economy_gain = (eco.misc_firm_revenue - misc_before) + (eco.government.cash_balance - gov_before)
    assert bank_loss == pytest.approx(LOAN_PRINCIPAL, rel=1e-6)
    assert economy_gain == pytest.approx(LOAN_PRINCIPAL, rel=1e-6)


# ---------------------------------------------------------------------------
# Per-tick debt service
# ---------------------------------------------------------------------------

def test_contract_debt_service_reduces_principal():
    """After one service tick, loan principal decreases by principal portion of PMT."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank

    firm = eco.firms[0]
    assert firm.good_category.lower() == "housing"

    annual_rate = 0.03
    term = 1040
    principal = 20_000.0
    r = annual_rate / 52.0
    pmt = _pmt(principal, annual_rate, term)

    loan = LoanContract(
        principal_remaining=principal,
        pmt_per_tick=pmt,
        ticks_remaining=term,
        origination_tick_rate=r,
    )
    firm.housing_active_loans = [loan]
    firm.cash_balance = 50_000.0

    eco._service_housing_mortgage_debt()

    interest = principal * r
    principal_pmt = pmt - interest
    expected_remaining = principal - principal_pmt

    assert firm.housing_active_loans[0].principal_remaining == pytest.approx(expected_remaining, rel=1e-6)
    assert firm.housing_active_loans[0].ticks_remaining == term - 1


def test_contract_debt_service_interest_credited_to_bank():
    """Interest portion of PMT goes to bank.last_tick_interest_income."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    bank.last_tick_interest_income = 0.0
    eco.bank = bank

    firm = eco.firms[0]
    annual_rate = 0.03
    r = annual_rate / 52.0
    principal = 10_000.0
    term = 1040
    pmt = _pmt(principal, annual_rate, term)

    firm.housing_active_loans = [LoanContract(
        principal_remaining=principal,
        pmt_per_tick=pmt,
        ticks_remaining=term,
        origination_tick_rate=r,
    )]
    firm.cash_balance = 50_000.0

    eco._service_housing_mortgage_debt()

    expected_interest = principal * r
    assert bank.last_tick_interest_income == pytest.approx(expected_interest, rel=1e-6)


def test_contract_debt_service_conserves_money():
    """Firm cash decrease == bank cash_reserves increase (full PMT)."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=100_000.0)
    eco.bank = bank

    firm = eco.firms[0]
    annual_rate = 0.03
    r = annual_rate / 52.0
    principal = 15_000.0
    term = 1040
    pmt = _pmt(principal, annual_rate, term)

    firm.housing_active_loans = [LoanContract(
        principal_remaining=principal,
        pmt_per_tick=pmt,
        ticks_remaining=term,
        origination_tick_rate=r,
    )]
    firm.cash_balance = 50_000.0
    firm_cash_before = firm.cash_balance
    bank_reserves_before = bank.cash_reserves

    eco._service_housing_mortgage_debt()

    assert (firm_cash_before - firm.cash_balance) == pytest.approx(
        bank.cash_reserves - bank_reserves_before, rel=1e-6
    )


def test_contract_paid_off_loans_pruned():
    """Loan with ticks_remaining=1 is removed after service."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank

    firm = eco.firms[0]
    principal = 500.0
    pmt = 500.0  # single-tick payoff
    r = 0.0
    firm.housing_active_loans = [LoanContract(
        principal_remaining=principal,
        pmt_per_tick=pmt,
        ticks_remaining=1,
        origination_tick_rate=r,
    )]
    firm.cash_balance = 10_000.0

    eco._service_housing_mortgage_debt()

    assert len(firm.housing_active_loans) == 0


# ---------------------------------------------------------------------------
# Underwriting gates
# ---------------------------------------------------------------------------

def test_contract_dscr_insufficient_blocks_loan():
    """DSCR < MIN_DSCR prevents loan origination.

    Set firm rent price near-zero so projected revenue << projected PMT.
    """
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank
    eco.misc_firm_revenue = 0.0

    firm = eco.firms[0]
    firm.price = 0.01       # near-zero rent → projected revenue ≈ 0 → DSCR fails
    _arm_firm(firm, principal=LOAN_PRINCIPAL)

    eco._offer_housing_expansion_loans()

    assert len(firm.housing_active_loans) == 0  # loan rejected


def test_contract_ltv_exceeded_blocks_loan():
    """LTV > MAX_LTV prevents loan origination even with adequate DSCR.

    Existing debt is loaded so projected_debt / total_assets > 0.80.
    PMT on existing debt is set tiny so DSCR would otherwise pass.
    """
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank

    firm = eco.firms[0]
    # total_assets ≈ (20 + 1) * 20_000 + 40_000 = 460_000
    # existing_debt set at 400_000 → projected_debt = 415_000 → LTV ≈ 0.90 > 0.80
    firm.housing_active_loans = [LoanContract(
        principal_remaining=400_000.0,
        pmt_per_tick=0.001,   # tiny PMT: doesn't trigger DSCR failure
        ticks_remaining=1040,
        origination_tick_rate=0.0,
    )]
    _arm_firm(firm, principal=LOAN_PRINCIPAL)

    eco._offer_housing_expansion_loans()

    # Still only the one pre-existing loan: new loan was rejected (LTV gate)
    assert len(firm.housing_active_loans) == 1


def test_contract_approval_appends_loan_contract():
    """Successful underwriting appends a LoanContract to housing_active_loans."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank
    eco.misc_firm_revenue = 0.0

    firm = eco.firms[0]
    _arm_firm(firm, principal=LOAN_PRINCIPAL)
    assert len(firm.housing_active_loans) == 0

    eco._offer_housing_expansion_loans()

    assert len(firm.housing_active_loans) == 1
    loan = firm.housing_active_loans[0]
    assert loan.principal_remaining == pytest.approx(LOAN_PRINCIPAL)
    assert loan.pmt_per_tick > 0.0
    assert loan.ticks_remaining == CONFIG.firms.housing_loan_term_ticks


def test_contract_approval_increments_capacity():
    """Approved loan adds units to max_rental_units."""
    eco = make_economy(categories=("Housing",), num_households=5)
    bank = _make_bank(cash_reserves=500_000.0)
    eco.bank = bank
    eco.misc_firm_revenue = 0.0

    firm = eco.firms[0]
    _arm_firm(firm, principal=LOAN_PRINCIPAL)
    before = firm.max_rental_units

    eco._offer_housing_expansion_loans()

    # units_to_build = min(housing_max_build_per_tick, max(1, round(15000/15000))) = 1
    assert firm.max_rental_units == before + 1
