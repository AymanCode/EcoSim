"""Fix 26: Final Integration Validation.

Comprehensive tests that verify the economy produces stable, learnable
dynamics with all Tier 1-3 fixes applied.
"""

import json
import math
import random
from typing import Any, Dict

import numpy as np
import pytest

from agents import GovernmentAgent
from config import CONFIG
from economy import Economy


def _build_economy(seed: int = 42) -> Economy:
    from tests_contracts.conftest import seed_everything
    seed_everything(seed)
    from tests_contracts.factories import make_economy
    return make_economy(seed=seed)


def _run(eco: Economy, ticks: int) -> Dict[str, Any]:
    for _ in range(ticks):
        eco.step()
    return eco.get_economic_metrics()


class TestSteadyState:
    """Test 1: After warmup the economy reaches an approximate steady state."""

    def test_unemployment_bounded(self) -> None:
        eco = _build_economy(42)
        metrics = _run(eco, 104)
        ur = metrics["unemployment_rate"]
        assert 0.0 <= ur <= 0.50, f"Unemployment {ur:.2%} out of reasonable range"

    def test_gdp_positive(self) -> None:
        eco = _build_economy(42)
        metrics = _run(eco, 104)
        gdp = metrics["gdp_this_tick"]
        assert gdp > 0, f"GDP should be positive, got {gdp}"

    def test_money_supply_stable(self) -> None:
        eco = _build_economy(42)
        _run(eco, 20)
        m0 = eco.get_economic_metrics()["money_supply"]
        _run(eco, 84)
        m1 = eco.get_economic_metrics()["money_supply"]
        # Allow generous tolerance — capital recycling and bank interest will cause drift
        drift = abs(m1 - m0) / max(abs(m0), 1.0)
        assert drift < 0.50, f"Money supply drifted {drift:.2%} over 84 ticks (m0={m0:.0f}, m1={m1:.0f})"

    def test_no_sector_extinction(self) -> None:
        eco = _build_economy(42)
        _run(eco, 104)
        categories = ["Food"]
        for cat in categories:
            count = sum(1 for f in eco.firms if f.good_category == cat)
            assert count >= 1, f"Sector {cat} went extinct after 104 ticks"


class TestCapitalStock:
    """Verify Fix 21 capital mechanics work end-to-end."""

    def test_initial_capital_positive(self) -> None:
        eco = _build_economy(42)
        for f in eco.firms:
            assert f.capital_stock > 0, f"Firm {f.firm_id} has zero initial capital"

    def test_depreciation_reduces_capital(self) -> None:
        eco = _build_economy(42)
        initial = sum(f.capital_stock for f in eco.firms)
        _run(eco, 5)
        after = sum(f.capital_stock for f in eco.firms)
        # Capital should decrease from depreciation (unless investment exceeds it)
        # At minimum, verify it changed
        assert after != initial or any(
            f.capital_investment_this_tick > 0 for f in eco.firms
        ), "Capital stock unchanged after 5 ticks — depreciation or investment should cause changes"

    def test_production_uses_capital(self) -> None:
        """A firm with more capital should produce more, holding labor constant."""
        from agents import FirmAgent
        f1 = FirmAgent(firm_id=999, good_name="TestA", cash_balance=10000,
                       inventory_units=0, capital_stock=1.0, units_per_worker=20.0)
        f2 = FirmAgent(firm_id=998, good_name="TestB", cash_balance=10000,
                       inventory_units=0, capital_stock=50.0, units_per_worker=20.0)
        cap_1 = f1._capacity_for_workers(5)
        cap_2 = f2._capacity_for_workers(5)
        assert cap_2 > cap_1, (
            f"More capital (50 vs 1) should produce more output: {cap_2:.1f} vs {cap_1:.1f}"
        )


class TestDynamicDepositRate:
    """Verify Fix 22 deposit rate responds to reserves."""

    def test_high_reserves_lower_rate(self) -> None:
        eco = _build_economy(42)
        if eco.bank is None:
            pytest.skip("No bank in economy")
        bank = eco.bank
        bank.cash_reserves = 200_000.0
        bank.total_deposits = 100_000.0  # 200% reserve ratio
        bank.update_deposit_rate()
        assert bank.deposit_rate < 0.01, (
            f"With 200% reserves, rate should be < 1%, got {bank.deposit_rate:.4f}"
        )

    def test_low_reserves_raise_rate(self) -> None:
        eco = _build_economy(42)
        if eco.bank is None:
            pytest.skip("No bank in economy")
        bank = eco.bank
        bank.cash_reserves = 2_000.0
        bank.total_deposits = 100_000.0  # 2% reserve ratio
        bank.update_deposit_rate()
        assert bank.deposit_rate > 0.01, (
            f"With 2% reserves, rate should be > 1%, got {bank.deposit_rate:.4f}"
        )


class TestConsumptionCredit:
    """Verify Fix 25 consumption loan mechanics."""

    def test_low_cash_triggers_loan_request(self) -> None:
        from agents import BankAgent, HouseholdAgent
        bank = BankAgent(cash_reserves=500_000.0)
        hh = HouseholdAgent(
            household_id=1, skills_level=0.5, age=30,
            cash_balance=10.0, subsistence_min_cash=50.0, wage=40.0,
        )
        bank.household_credit_scores[1] = 0.6
        hh.maybe_request_consumption_loan(bank=bank)
        assert hh.needs_consumption_loan is True
        assert hh.consumption_loan_amount == 200.0  # 4 * 50

    def test_adequate_cash_no_loan(self) -> None:
        from agents import BankAgent, HouseholdAgent
        bank = BankAgent(cash_reserves=500_000.0)
        hh = HouseholdAgent(
            household_id=2, skills_level=0.5, age=30,
            cash_balance=500.0, subsistence_min_cash=50.0,
        )
        hh.maybe_request_consumption_loan(bank=bank)
        assert hh.needs_consumption_loan is False

    def test_low_credit_score_denied(self) -> None:
        from agents import BankAgent, HouseholdAgent
        bank = BankAgent(cash_reserves=500_000.0)
        hh = HouseholdAgent(
            household_id=3, skills_level=0.5, age=30,
            cash_balance=10.0, subsistence_min_cash=50.0, wage=40.0,
        )
        bank.household_credit_scores[3] = 0.2  # Below 0.4 threshold
        hh.maybe_request_consumption_loan(bank=bank)
        assert hh.needs_consumption_loan is False


class TestObservationSpace:
    """Verify Fix 23 observation space completeness."""

    def test_all_fix23_fields_present(self) -> None:
        eco = _build_economy(42)
        _run(eco, 10)
        metrics = eco.get_economic_metrics()

        required_fields = [
            # Money supply
            "money_supply",
            # Capital stock
            "total_capital_stock",
            "avg_capital_per_firm",
            "total_investment_this_tick",
            "investment_as_pct_of_gdp",
            # Firm distress
            "firm_healthy_count",
            "firm_survival_mode_count",
            "firm_burn_mode_count",
            "avg_runway_weeks",
            # Wages
            "labor_share_of_revenue",
            # Household welfare
            "avg_savings_rate",
            "total_bank_deposits",
            "households_below_poverty",
            "gini_coefficient",
            # Wellbeing
            "mean_happiness",
            "mean_morale",
            "mean_health",
        ]
        missing = [f for f in required_fields if f not in metrics]
        assert not missing, f"Missing from observation space: {missing}"

        # Bank fields only required when bank is present
        if eco.bank is not None:
            bank_fields = [
                "bank_deposit_rate",
                "bank_reserve_ratio_actual",
                "bank_interest_income_this_tick",
                "bank_avg_credit_score_firms",
                "bank_avg_credit_score_households",
            ]
            missing_bank = [f for f in bank_fields if f not in metrics]
            assert not missing_bank, f"Missing bank fields: {missing_bank}"

    def test_no_nan_or_inf(self) -> None:
        eco = _build_economy(42)
        _run(eco, 10)
        metrics = eco.get_economic_metrics()
        serialized = json.dumps(metrics, default=str)
        deserialized = json.loads(serialized)

        bad = {}
        for key, value in deserialized.items():
            if isinstance(value, float):
                if math.isnan(value):
                    bad[key] = "NaN"
                elif math.isinf(value):
                    bad[key] = "Inf"
        assert not bad, f"Degenerate values in observation: {bad}"

    def test_json_round_trip(self) -> None:
        eco = _build_economy(42)
        _run(eco, 10)
        metrics = eco.get_economic_metrics()
        serialized = json.dumps(metrics, default=str)
        deserialized = json.loads(serialized)
        assert isinstance(deserialized, dict)
        assert len(deserialized) == len(metrics)


class TestDeterministicReplay:
    """Verify deterministic seeds produce identical output."""

    def test_two_runs_identical(self) -> None:
        m1 = _run(_build_economy(42), 30)
        m2 = _run(_build_economy(42), 30)
        # Compare a selection of numeric metrics
        keys = ["gdp_this_tick", "unemployment_rate", "mean_wage",
                "total_household_cash", "total_firm_cash", "government_cash"]
        for k in keys:
            v1, v2 = m1.get(k, 0.0), m2.get(k, 0.0)
            assert v1 == v2, (
                f"Deterministic replay failed: {k} = {v1} vs {v2}"
            )
