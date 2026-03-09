import numpy as np
import pytest

from agents import FirmAgent, HouseholdAgent
from tests_contracts.conftest import seed_everything, total_money


def test_contract_accounting_conservation_over_short_horizon(tiny_economy_factory):
    """Contract A: Core cash-transfer plumbing conserves total money."""
    economy = tiny_economy_factory(
        num_households=5,
        num_firms_per_category=1,
        include_housing=False,
        include_services=False,
        include_healthcare=False,
        baseline_firms=False,
        disable_shocks=True,
        government_cash=5_000.0,
        seed=111,
    )
    food_firm = next(f for f in economy.firms if f.good_category.lower() == "food")
    for household in economy.households:
        household.employer_id = None
        household.wage = 0.0
        household.category_weights = {"food": 1.0}
        household.goods_inventory.clear()

    initial_total = total_money(economy)
    for _ in range(3):
        plans = {
            household.household_id: {
                "household_id": household.household_id,
                "category_budgets": {},
                "planned_purchases": {food_firm.firm_id: 1.0},
            }
            for household in economy.households
        }
        per_household_purchases, per_firm_sales = economy._clear_goods_market(plans, economy.firms)

        for firm in economy.firms:
            sales = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
            firm.apply_sales_and_profit(
                {
                    "units_sold": sales["units_sold"],
                    "revenue": sales["revenue"],
                    "profit_taxes_paid": 0.0,
                }
            )

        economy._batch_apply_household_updates(
            transfer_plan={},
            wage_taxes={},
            per_household_purchases=per_household_purchases,
            good_category_lookup=economy._build_good_category_lookup(),
        )
    final_total = total_money(economy)

    assert final_total == pytest.approx(initial_total, abs=1e-4)


def test_contract_non_negativity_and_valid_ranges(tiny_economy_factory):
    """Contract B: Inventories, prices, wages, and bounded wellbeing stay valid."""
    economy = tiny_economy_factory(
        num_households=10,
        num_firms_per_category=1,
        baseline_firms=True,
        disable_shocks=True,
        government_cash=15_000.0,
        seed=222,
    )

    for _ in range(5):
        economy.step()

    for firm in economy.firms:
        assert firm.inventory_units >= -1e-9
        assert firm.price > 0.0
        assert firm.wage_offer >= 0.0
        assert np.isfinite(firm.cash_balance)
        if firm.good_category.lower() == "healthcare":
            # Healthcare is service-only: no storable inventory accumulation.
            assert firm.inventory_units == pytest.approx(0.0, abs=1e-8)
            assert len(firm.healthcare_queue) >= 0
            max_capacity = len(firm.employees) * max(firm.healthcare_capacity_per_worker, 0.0)
            assert firm.healthcare_completed_visits_last_tick <= max_capacity + 1e-8

    for household in economy.households:
        assert household.cash_balance >= -1e-6
        assert 0.0 <= household.health <= 1.0
        assert 0.0 <= household.happiness <= 1.0
        assert 0.0 <= household.morale <= 1.0
        assert np.isfinite(household.cash_balance)


def _snapshot(economy):
    metrics = economy.get_economic_metrics()
    household_sample = sorted(
        [
            (
                h.household_id,
                round(h.cash_balance, 6),
                round(h.health, 6),
                round(h.happiness, 6),
                round(h.morale, 6),
                h.employer_id,
            )
            for h in economy.households[:5]
        ],
        key=lambda x: x[0],
    )
    firm_sample = sorted(
        [
            (
                f.firm_id,
                round(f.cash_balance, 6),
                round(f.inventory_units, 6),
                round(f.price, 6),
                round(f.wage_offer, 6),
                len(f.employees),
            )
            for f in economy.firms
        ],
        key=lambda x: x[0],
    )
    return {
        "unemployment_rate": round(metrics["unemployment_rate"], 8),
        "mean_wage": round(metrics["mean_wage"], 6),
        "gov_cash": round(economy.government.cash_balance, 6),
        "households": household_sample,
        "firms": firm_sample,
    }


def test_contract_determinism_with_seed(tiny_economy_factory, fixed_seed):
    """Contract C: Same seed and initial state should yield same one-tick result."""
    economy_a = tiny_economy_factory(
        num_households=8,
        num_firms_per_category=1,
        baseline_firms=True,
        disable_shocks=False,
        seed=fixed_seed,
    )
    economy_a.step()
    snapshot_a = _snapshot(economy_a)

    economy_b = tiny_economy_factory(
        num_households=8,
        num_firms_per_category=1,
        baseline_firms=True,
        disable_shocks=False,
        seed=fixed_seed,
    )
    economy_b.step()
    snapshot_b = _snapshot(economy_b)

    assert snapshot_a == snapshot_b


def test_contract_uniqueness_of_sampled_household_and_firm_traits(fixed_seed):
    """Contract D: Per-entity sampled trait tuples should be unique."""
    seed_everything(fixed_seed)
    households = [
        HouseholdAgent(
            household_id=i + 1,
            skills_level=0.5,
            age=30,
            cash_balance=1000.0,
        )
        for i in range(40)
    ]

    household_traits = [
        (
            round(h.healthcare_preference, 8),
            round(h.healthcare_urgency_threshold, 8),
            round(h.healthcare_critical_threshold, 8),
            round(h.morale_employed_boost, 8),
            round(h.morale_unemployed_penalty, 8),
            round(h.morale_unhoused_penalty, 8),
            round(h.household_service_happiness_base_boost, 8),
        )
        for h in households
    ]
    assert len(set(household_traits)) == len(household_traits)

    firms = []
    for firm_id in range(1, 41):
        firm = FirmAgent(
            firm_id=firm_id,
            good_name=f"Firm{firm_id}",
            cash_balance=10_000.0,
            inventory_units=100.0,
            good_category="Services",
            quality_level=5.0,
            wage_offer=40.0,
            price=10.0,
            expected_sales_units=50.0,
            production_capacity_units=200.0,
            productivity_per_worker=12.0,
            personality="moderate",
        )
        firms.append(firm)

    firm_traits = [
        (
            round(f.investment_propensity, 8),
            round(f.risk_tolerance, 8),
            round(f.price_adjustment_rate, 8),
            round(f.wage_adjustment_rate, 8),
            round(f.rd_spending_rate, 8),
            f.max_hires_per_tick,
            f.max_fires_per_tick,
            round(f.units_per_worker, 8),
        )
        for f in firms
    ]
    assert len(set(firm_traits)) == len(firm_traits)
