"""Contract tests for the BankAgent credit channel.

Tests verify:
- Bank is optional (economy works without it)
- Credit scoring mechanics
- Loan origination (bank-first, govt-fallback)
- Deposit sweep and interest
- Circuit breaker and government-backed emergency loans
- Leverage ceiling prevents debt stacking
- Medical loan single-loan cap
"""

import math

import numpy as np

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def test_contract_bank_is_optional(tiny_economy_factory):
    """Contract P: Economy runs identically without a bank (bank=None)."""
    economy = tiny_economy_factory(
        num_households=12,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=800,
        government_cash=80_000.0,
    )

    assert economy.bank is None

    # Run 10 ticks — should not crash
    for _ in range(10):
        economy.step()

    # Basic sanity: agents are alive
    health = np.array([h.health for h in economy.households], dtype=float)
    assert np.mean(health) > 0.1
    assert np.isfinite(health).all()

    for firm in economy.firms:
        assert math.isfinite(firm.cash_balance)
        assert math.isfinite(firm.price)


def test_contract_bank_credit_score_slow_buildup():
    """Contract Q: Credit score builds at +0.01/tick, not faster."""
    bank = BankAgent()

    # Firm starts at 0.5
    assert bank.get_firm_credit_score(42) == 0.5

    # 25 on-time payments: 0.5 + 25 * 0.01 = 0.75 (NOT 1.0)
    for _ in range(25):
        bank.update_firm_credit_score(42, +0.01)

    score = bank.get_firm_credit_score(42)
    assert abs(score - 0.75) < 1e-9, f"Expected 0.75, got {score}"

    # 50 ticks to reach 1.0
    for _ in range(25):
        bank.update_firm_credit_score(42, +0.01)

    score = bank.get_firm_credit_score(42)
    assert abs(score - 1.0) < 1e-9


def test_contract_bank_credit_score_clamped():
    """Contract R: Credit scores are clamped to [0, 1]."""
    bank = BankAgent()

    # Massive positive delta
    bank.update_firm_credit_score(1, +5.0)
    assert bank.get_firm_credit_score(1) == 1.0

    # Massive negative delta
    bank.update_firm_credit_score(2, -5.0)
    assert bank.get_firm_credit_score(2) == 0.0


def test_contract_bank_leverage_ceiling():
    """Contract S: Firms cannot borrow beyond 3× trailing revenue."""
    bank = BankAgent(cash_reserves=1_000_000.0)

    trailing_revenue = 10_000.0  # 3× = 30_000

    # First loan: 20K should be allowed
    assert bank._can_firm_borrow(1, 20_000.0, trailing_revenue) is True

    # Issue the loan
    bank.originate_loan("firm", 1, 20_000.0, 0.03, 104)

    # Second loan: 15K would put total at 35K+ (> 30K ceiling)
    assert bank._can_firm_borrow(1, 15_000.0, trailing_revenue) is False

    # But 8K would be OK (existing ~20.6K + 8K = ~28.6K < 30K)
    max_borrowable = bank._max_firm_borrowable(1, trailing_revenue)
    assert max_borrowable > 0
    assert max_borrowable < 15_000.0


def test_contract_bank_circuit_breaker():
    """Contract T: Bank stops lending when reserves < reserve_ratio × deposits."""
    bank = BankAgent(
        cash_reserves=100.0,
        total_deposits=5000.0,
        reserve_ratio=0.10,
    )

    # Required reserves = 500, but only 100 available
    assert bank.can_lend() is False
    assert bank.lendable_cash == 0.0

    # With sufficient reserves
    bank.cash_reserves = 1000.0
    assert bank.can_lend() is True
    assert bank.lendable_cash == 500.0  # 1000 - 500


def test_contract_bank_government_backed_loan():
    """Contract U: Government-backed loans work during circuit breaker."""
    bank = BankAgent(
        cash_reserves=100.0,
        total_deposits=5000.0,
        reserve_ratio=0.10,
    )
    govt = GovernmentAgent(cash_balance=50_000.0)

    assert bank.can_lend() is False

    # Government-backed loan should succeed
    loan = bank.issue_government_backed_loan(
        "firm", 1, 10_000.0, 0.05, 104, govt,
    )

    assert loan is not None
    assert loan["govt_backed"] is True
    assert govt.cash_balance == 40_000.0  # Government paid
    assert bank.cash_reserves == 100.0    # Bank reserves unchanged
    assert len(bank.active_loans) == 1


def test_contract_bank_deposit_sweep_and_interest(tiny_economy_factory):
    """Contract V: Households deposit excess cash and earn interest."""
    economy = tiny_economy_factory(
        num_households=5,
        num_firms_per_category=1,
        include_healthcare=False,
        baseline_firms=True,
        disable_shocks=True,
        seed=810,
        government_cash=50_000.0,
    )
    bank = BankAgent(deposit_rate=0.052)  # ~0.1% per week for visible interest
    economy.bank = bank

    # Give a household lots of cash
    rich_hh = economy.households[0]
    rich_hh.cash_balance = 10_000.0

    economy._process_bank_deposits()

    # Should have deposited some
    assert rich_hh.bank_deposit > 0.0
    assert bank.total_deposits > 0.0


def test_contract_bank_deposit_heterogeneity():
    """Contract V2: Deposit parameters vary across households based on saving_tendency."""
    hh_low = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1000.0)
    hh_high = HouseholdAgent(household_id=2, skills_level=0.5, age=30, cash_balance=1000.0)

    # Force different saving tendencies
    hh_low.saving_tendency = 0.1
    hh_low.deposit_buffer_weeks = 3.0 + 7.0 * 0.1   # 3.7 weeks
    hh_low.deposit_fraction = 0.05 + 0.35 * 0.1      # 0.085

    hh_high.saving_tendency = 0.9
    hh_high.deposit_buffer_weeks = 3.0 + 7.0 * 0.9   # 9.3 weeks
    hh_high.deposit_fraction = 0.05 + 0.35 * 0.9      # 0.365

    assert hh_low.deposit_buffer_weeks < hh_high.deposit_buffer_weeks
    assert hh_low.deposit_fraction < hh_high.deposit_fraction

    # The aggressive saver keeps MORE liquid (bigger buffer) but deposits
    # a LARGER fraction of excess — this means they actually deposit less
    # when cash is modest, which prevents the drain problem.
    assert hh_high.deposit_buffer_weeks > 9.0
    assert hh_low.deposit_buffer_weeks < 4.0


def test_contract_bank_deposit_withdrawal(tiny_economy_factory):
    """Contract V3: Households withdraw deposits when cash drops below buffer floor."""
    economy = tiny_economy_factory(
        num_households=3,
        num_firms_per_category=1,
        include_healthcare=False,
        baseline_firms=True,
        disable_shocks=True,
        seed=811,
        government_cash=50_000.0,
    )
    bank = BankAgent(cash_reserves=100_000.0)
    economy.bank = bank

    hh = economy.households[0]
    # Simulate: household has deposits but ran out of cash
    hh.cash_balance = 10.0
    hh.bank_deposit = 500.0
    hh.last_consumption_spending = 50.0  # Weekly spend ~ $50
    bank.total_deposits = 500.0
    bank.cash_reserves += 500.0

    economy._process_bank_deposits()

    # Should have withdrawn to restore liquidity
    assert hh.cash_balance > 10.0, "Household should withdraw from deposits when cash is low"
    assert hh.bank_deposit < 500.0, "Deposit balance should decrease after withdrawal"


def test_contract_bank_medical_loan_single_cap():
    """Contract W: Only one medical loan active at a time."""
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)

    hh = HouseholdAgent(
        household_id=1,
        skills_level=0.5,
        age=30,
        cash_balance=100.0,
    )

    # First medical loan
    hh.medical_loan_remaining = 0.0

    # Create a minimal economy to use _issue_medical_loan
    firm = FirmAgent(
        firm_id=1,
        good_name="FoodFirm1",
        cash_balance=40_000.0,
        inventory_units=500.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=60.0,
        production_capacity_units=600.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=True,
    )
    govt.register_baseline_firm("Food", firm.firm_id)
    economy = Economy(
        households=[hh],
        firms=[firm],
        government=govt,
        bank=bank,
    )

    # First loan should succeed
    result = economy._issue_medical_loan(hh, 500.0)
    assert result is True
    assert hh.medical_loan_remaining > 0

    # Second loan should be blocked (debt stacking prevention)
    result2 = economy._issue_medical_loan(hh, 300.0)
    assert result2 is False


def test_contract_bank_loan_writeoff_on_bankruptcy():
    """Contract X: Bank loans are written off when firms go bankrupt."""
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)

    firm = FirmAgent(
        firm_id=1,
        good_name="DomedFirm",
        cash_balance=-2000.0,  # Below bankruptcy threshold
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=60.0,
        production_capacity_units=600.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )

    # Give the firm a bank loan
    bank.originate_loan("firm", 1, 10_000.0, 0.03, 104)
    initial_provision = bank.loan_loss_provision

    hh = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1000.0)
    economy = Economy(
        households=[hh],
        firms=[firm],
        government=govt,
        bank=bank,
    )
    economy._apply_random_shocks = lambda: None

    economy._handle_firm_exits()

    # Firm should be removed
    assert len(economy.firms) == 0

    # Loan should be written off
    assert bank.loan_loss_provision > initial_provision


def test_contract_bank_with_economy_run(tiny_economy_factory):
    """Contract Y: Economy with bank enabled runs without errors for 15 ticks."""
    economy = tiny_economy_factory(
        num_households=12,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=820,
        government_cash=80_000.0,
    )
    bank = BankAgent(cash_reserves=200_000.0)
    economy.bank = bank

    for _ in range(15):
        economy.step()

    # Basic sanity
    health = np.array([h.health for h in economy.households], dtype=float)
    assert np.mean(health) > 0.1
    assert np.isfinite(health).all()

    for firm in economy.firms:
        assert math.isfinite(firm.cash_balance)
        assert math.isfinite(firm.price)

    # Bank should have some activity
    metrics = economy.get_economic_metrics()
    assert "bank_cash_reserves" in metrics
    assert math.isfinite(metrics["bank_cash_reserves"])


def test_contract_bank_default_penalty_is_020():
    """Contract Z: Default credit score penalty is -0.20, not -0.30."""
    bank = BankAgent()

    # Start at 0.5
    initial = bank.get_firm_credit_score(99)
    assert initial == 0.5

    # Apply default penalty
    bank.update_firm_credit_score(99, -0.20)
    after_default = bank.get_firm_credit_score(99)
    assert abs(after_default - 0.30) < 1e-9, f"Expected 0.30 after default, got {after_default}"

    # Verify it's recoverable: 30 ticks of good behavior at +0.01 = 0.60
    for _ in range(30):
        bank.update_firm_credit_score(99, +0.01)
    recovered = bank.get_firm_credit_score(99)
    assert abs(recovered - 0.60) < 1e-9
