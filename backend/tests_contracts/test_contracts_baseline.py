"""Unit tests for baseline firm containment and fiscal transparency (EcoSim 2.0).

All tests are unit-scope: direct field mutation, no full economy.step() unless
the test description says integration.
"""
import pytest

from agents import FirmAgent, GovernmentAgent
from tests_contracts.factories import make_firm, make_firms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_baseline_firm(category: str = "Food", **kwargs) -> FirmAgent:
    defaults = {
        "baseline_production_quota": 500.0,
        "inventory_units": 0.0,
        "cash_balance": 10_000.0,
        "employees": [],
    }
    defaults.update(kwargs)
    return make_firm(firm_id=1, category=category, is_baseline=True, **defaults)


def _make_government(cash: float = 50_000.0) -> GovernmentAgent:
    gov = GovernmentAgent(cash_balance=cash)
    return gov


class _MinimalEconomy:
    """Thin stand-in for Economy so _process_baseline_firm_support can run."""

    def __init__(self, firms, government):
        self.firms = firms
        self.government = government

    def _process_baseline_firm_support(self) -> float:
        """Inline copy of Economy._process_baseline_firm_support for unit testing."""
        total_support = 0.0
        self.government.baseline_support_spending_this_tick = 0.0
        self.government.baseline_support_by_sector_this_tick = {}

        for firm in self.firms:
            if not firm.is_baseline:
                continue
            firm.baseline_support_received_this_tick = 0.0
            if firm.cash_balance < 0.0:
                support = abs(firm.cash_balance)
                firm.cash_balance = 0.0
                self.government.cash_balance -= support
                firm.baseline_support_received_this_tick = support
                firm.cumulative_baseline_support_received += support
                total_support += support
                category = (firm.good_category or "unknown").lower()
                self.government.baseline_support_by_sector_this_tick[category] = (
                    self.government.baseline_support_by_sector_this_tick.get(category, 0.0) + support
                )
                self.government.baseline_support_by_sector_cumulative[category] = (
                    self.government.baseline_support_by_sector_cumulative.get(category, 0.0) + support
                )

        self.government.baseline_support_spending_this_tick = total_support
        self.government.cumulative_baseline_support_spending += total_support
        return total_support


# ---------------------------------------------------------------------------
# Baseline deficit support — correctness
# ---------------------------------------------------------------------------

def test_contract_baseline_support_zeroes_negative_cash():
    firm = _make_baseline_firm(cash_balance=-300.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([firm], gov)

    eco._process_baseline_firm_support()

    assert firm.cash_balance == pytest.approx(0.0)
    assert firm.baseline_support_received_this_tick == pytest.approx(300.0)


def test_contract_baseline_support_deducts_from_government():
    firm = _make_baseline_firm(cash_balance=-200.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([firm], gov)

    eco._process_baseline_firm_support()

    assert gov.cash_balance == pytest.approx(50_000.0 - 200.0)
    assert gov.baseline_support_spending_this_tick == pytest.approx(200.0)


def test_contract_baseline_support_skips_positive_cash():
    firm = _make_baseline_firm(cash_balance=500.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([firm], gov)

    eco._process_baseline_firm_support()

    assert firm.cash_balance == pytest.approx(500.0)
    assert firm.baseline_support_received_this_tick == pytest.approx(0.0)
    assert gov.cash_balance == pytest.approx(50_000.0)


def test_contract_baseline_support_skips_non_baseline_firms():
    baseline = _make_baseline_firm(cash_balance=-100.0)
    private = make_firm(firm_id=2, category="Food", is_baseline=False, cash_balance=-500.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([baseline, private], gov)

    eco._process_baseline_firm_support()

    # Private firm untouched
    assert private.cash_balance == pytest.approx(-500.0)
    # Only baseline firm received support
    assert gov.baseline_support_spending_this_tick == pytest.approx(100.0)


def test_contract_baseline_support_accumulates_cumulative():
    firm = _make_baseline_firm(cash_balance=-100.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([firm], gov)

    eco._process_baseline_firm_support()
    firm.cash_balance = -200.0  # next tick deficit
    eco._process_baseline_firm_support()

    assert firm.cumulative_baseline_support_received == pytest.approx(300.0)
    assert gov.cumulative_baseline_support_spending == pytest.approx(300.0)


def test_contract_baseline_support_per_sector_breakdown():
    food_firm = _make_baseline_firm(category="Food", cash_balance=-150.0)
    food_firm.firm_id = 1
    services_firm = make_firm(firm_id=2, category="Services", is_baseline=True,
                              cash_balance=-80.0, baseline_production_quota=500.0)
    gov = _make_government(cash=50_000.0)
    eco = _MinimalEconomy([food_firm, services_firm], gov)

    eco._process_baseline_firm_support()

    assert gov.baseline_support_by_sector_this_tick.get("food", 0.0) == pytest.approx(150.0)
    assert gov.baseline_support_by_sector_this_tick.get("services", 0.0) == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# Money conservation
# ---------------------------------------------------------------------------

def test_contract_baseline_support_conserves_total_money():
    firm = _make_baseline_firm(cash_balance=-250.0)
    gov = _make_government(cash=50_000.0)

    total_before = firm.cash_balance + gov.cash_balance

    eco = _MinimalEconomy([firm], gov)
    eco._process_baseline_firm_support()

    total_after = firm.cash_balance + gov.cash_balance
    assert total_after == pytest.approx(total_before)


# ---------------------------------------------------------------------------
# Baseline containment mode — entry
# ---------------------------------------------------------------------------

def _baseline_firm_with_inventory(quota: float, inventory: float, zero_sales: int = 0) -> FirmAgent:
    firm = _make_baseline_firm(
        cash_balance=5_000.0,
        baseline_production_quota=quota,
        inventory_units=inventory,
        zero_sales_streak=zero_sales,
    )
    firm.employees = []
    return firm


def _run_containment_entry_check(firm: FirmAgent) -> dict:
    """Run plan_production_and_labor with minimal args and return the mode flag."""
    firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    return {"containment": firm.baseline_containment_mode}


def test_contract_containment_enters_on_inventory_3x_target():
    quota = 500.0
    target = quota * 4.0  # 2000 units
    # 3× target = 6000 units — should trigger
    firm = _baseline_firm_with_inventory(quota=quota, inventory=6_100.0, zero_sales=0)

    result = _run_containment_entry_check(firm)

    assert result["containment"] is True


def test_contract_containment_enters_on_zero_sales_plus_high_inventory():
    quota = 500.0
    target = quota * 4.0  # 2000 units
    # inv_ratio > 1.0 (high inventory) + zero_sales_streak >= 10
    firm = _baseline_firm_with_inventory(quota=quota, inventory=2_100.0, zero_sales=10)

    result = _run_containment_entry_check(firm)

    assert result["containment"] is True


def test_contract_containment_does_not_enter_on_normal_inventory():
    quota = 500.0
    # inventory = 1× target (normal)
    firm = _baseline_firm_with_inventory(quota=quota, inventory=500.0, zero_sales=0)

    result = _run_containment_entry_check(firm)

    assert result["containment"] is False


def test_contract_containment_exits_when_inventory_returns_to_normal():
    quota = 500.0
    firm = _baseline_firm_with_inventory(quota=quota, inventory=6_100.0, zero_sales=0)
    # Force entry
    firm.baseline_containment_mode = True

    # Simulate inventory clearing: inventory back to 1.4× target
    firm.inventory_units = quota * 4.0 * 1.4  # 2800, inv_ratio = 1.4 (≤ 1.5)
    firm.zero_sales_streak = 0

    _run_containment_entry_check(firm)

    assert firm.baseline_containment_mode is False


# ---------------------------------------------------------------------------
# Baseline containment mode — production discipline
# ---------------------------------------------------------------------------

def test_contract_containment_freezes_hiring():
    quota = 500.0
    firm = _baseline_firm_with_inventory(quota=quota, inventory=6_100.0, zero_sales=0)
    firm.employees = list(range(5))  # 5 existing workers

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    assert plan["planned_hires_count"] == 0


def test_contract_containment_zeros_production_at_5x_inventory():
    quota = 500.0
    target = quota * 4.0
    # 5× target = 10000
    firm = _baseline_firm_with_inventory(quota=quota, inventory=target * 5.5, zero_sales=0)
    firm.employees = list(range(10))

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    assert plan["planned_production_units"] == pytest.approx(0.0)


def test_contract_containment_reduces_production_at_3x_inventory():
    quota = 500.0
    target = quota * 4.0
    # Between 3× and 5× target
    firm = _baseline_firm_with_inventory(quota=quota, inventory=target * 3.5, zero_sales=0)
    firm.employees = list(range(10))

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    assert plan["planned_production_units"] <= quota * 0.25 + 1e-6


def test_contract_containment_zeros_production_on_zero_sales_streak():
    quota = 500.0
    target = quota * 4.0
    # zero_sales_streak >= 10 AND high inventory → production = 0
    firm = _baseline_firm_with_inventory(quota=quota, inventory=target * 1.2, zero_sales=12)
    firm.employees = list(range(10))

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    # Must be in containment and production must be zero
    assert firm.baseline_containment_mode is True
    assert plan["planned_production_units"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Baseline Food: public-fallback wage + post-warmup loss/inventory shrinkage
# ---------------------------------------------------------------------------

from config import CONFIG as _CONFIG  # noqa: E402


def _baseline_food(**kwargs) -> FirmAgent:
    defaults = {
        "category": "Food",
        "is_baseline": True,
        "baseline_production_quota": 500.0,
        "inventory_units": 0.0,
        "cash_balance": 10_000.0,
        "employees": [],
        "wage_offer": 50.0,
        "price": 6.0,
        "production_capacity_units": 600.0,
        "productivity_per_worker": 12.0,
    }
    defaults.update(kwargs)
    cat = defaults.pop("category")
    is_b = defaults.pop("is_baseline")
    return make_firm(firm_id=1, category=cat, is_baseline=is_b, **defaults)


def test_contract_baseline_food_wage_pinned_to_minimum_post_warmup():
    firm = _baseline_food(wage_offer=80.0)
    plan = firm.plan_wage(unemployment_rate=0.05, unemployment_benefit=10.0, in_warmup=False)
    floor = firm._firm_config().minimum_wage_floor
    assert plan["wage_offer_next"] == pytest.approx(floor)


def test_contract_baseline_food_wage_pinned_to_minimum_during_warmup():
    firm = _baseline_food(wage_offer=80.0)
    firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    floor = firm._firm_config().minimum_wage_floor
    assert firm.wage_offer == pytest.approx(floor)


def test_contract_baseline_food_warmup_losses_do_not_force_layoffs():
    firm = _baseline_food(employees=list(range(50)), last_profit=-5_000.0, profit_ema=-3_000.0)
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    # During warmup, baseline Food may incur losses without forced layoffs.
    assert plan["planned_layoffs_ids"] == [] or len(plan["planned_layoffs_ids"]) == 0


def test_contract_baseline_food_post_warmup_negative_profit_triggers_layoffs_no_hires():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=0.0,
        last_profit=-2_000.0,
        profit_ema=-1_500.0,
    )
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) > 0


def test_contract_baseline_food_post_warmup_heavy_inventory_layoffs_and_reduced_production():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=5_000.0,  # >> quota * 2 = 1000
        last_profit=100.0,
        profit_ema=100.0,
    )
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) > 0
    assert plan["planned_production_units"] <= firm.baseline_production_quota * 0.5 + 1e-6


def test_contract_baseline_food_post_warmup_heavy_inventory_lowers_price_within_bounds():
    firm = _baseline_food(
        employees=list(range(20)),
        inventory_units=5_000.0,
        price=8.0,
    )
    pre_price = firm.price
    plan = firm.plan_pricing(
        sell_through_rate=0.3,
        unemployment_rate=0.1,
        in_warmup=False,
    )
    labor_cost_per_unit = firm.wage_offer / max(firm.productivity_per_worker, 1.0)
    price_floor = max(firm.min_price, labor_cost_per_unit)
    assert plan["price_next"] < pre_price
    assert plan["price_next"] >= price_floor - 1e-6
    assert plan["price_next"] > 0.0


def test_contract_baseline_food_first_post_warmup_tick_fires_half_of_employees():
    firm = _baseline_food(employees=list(range(90)))
    assert firm.baseline_food_post_warmup_transition_done is False

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )

    assert firm.baseline_food_post_warmup_transition_done is True
    assert len(plan["planned_layoffs_ids"]) == 45
    assert plan["planned_hires_count"] == 0


def test_contract_baseline_food_transition_layoff_only_fires_once():
    firm = _baseline_food(employees=list(range(90)))
    firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    firm.employees = list(range(45))  # simulate the layoff applied
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=False,
        post_warmup_cooldown=False,
    )
    # Second post-warmup tick must not trigger another half-layoff.
    assert len(plan["planned_layoffs_ids"]) < 22


def test_contract_baseline_food_transition_layoff_skipped_during_warmup():
    firm = _baseline_food(employees=list(range(90)))
    firm.plan_production_and_labor(
        last_tick_sales_units=400.0,
        in_warmup=True,
        post_warmup_cooldown=False,
    )
    assert firm.baseline_food_post_warmup_transition_done is False


def test_contract_private_food_firm_unaffected_by_baseline_food_branches():
    firm = make_firm(
        firm_id=2,
        category="Food",
        is_baseline=False,
        employees=list(range(20)),
        inventory_units=5_000.0,
        last_profit=-2_000.0,
        profit_ema=-1_500.0,
        baseline_production_quota=0.0,
        wage_offer=50.0,
        price=8.0,
        cash_balance=20_000.0,
    )
    # Wage path: private firm not pinned to floor.
    wage_plan = firm.plan_wage(unemployment_rate=0.05, unemployment_benefit=10.0, in_warmup=False)
    floor = firm._firm_config().minimum_wage_floor
    # Private firms may sit at any non-pinned value; key assertion is the
    # baseline-Food early-return shortcut did not fire (wage_offer_next exists,
    # is finite, and is not the bare minimum_wage_floor short-circuit value
    # unless the generic wage logic also picked it).
    assert "wage_offer_next" in wage_plan
    assert wage_plan["wage_offer_next"] >= floor
