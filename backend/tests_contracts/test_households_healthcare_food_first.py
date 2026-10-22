"""Households: food first, then the queued healthcare visit (re-cut of #47).

With ``CONFIG.households.healthcare_food_first_reserve`` on (the default), the weekly budget
claims liquidity in this order on every payment sequence: rent and loan
installments, minimum food, the queued visit's expected out-of-pocket cost
(government's ``expected_healthcare_out_of_pocket_all``, capped at what food
leaves), then the rest. Nothing is charged at budget time.
"""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pytest

from agents import FirmAgent, GovernmentAgent
from config import CONFIG, clone_config, use_config
from economy import Economy
from tests_contracts.factories import make_household

BACKEND = Path(__file__).resolve().parents[1]
for _p in (BACKEND / "tools" / "runners", BACKEND / "tools" / "benchmarks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

VISIT = 60.0
FOOD_PRICE = 4.0


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "healthcare_food_first_reserve", True)


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "healthcare_food_first_reserve", False)


def _firm(firm_id, category, price):
    firm = FirmAgent(
        firm_id=firm_id, good_name=category, cash_balance=20_000.0, inventory_units=100.0,
        good_category=category, quality_level=6.0, wage_offer=40.0, price=price,
        expected_sales_units=100.0, production_capacity_units=500.0,
        productivity_per_worker=12.0, personality="moderate",
    )
    firm.employees = [5001, 5002]
    firm.healthcare_capacity_per_worker = 1.0
    return firm


def _economy(households, *, subsidy_level=0, extra_firms=()):
    clinic, grocer = _firm(900, "Healthcare", VISIT), _firm(901, "Food", FOOD_PRICE)
    government = GovernmentAgent(cash_balance=1_000_000.0)
    if subsidy_level:
        government.set_lever("sector_subsidy_target", "healthcare")
        government.set_lever("sector_subsidy_level", subsidy_level)
    economy = Economy(households=list(households), firms=[clinic, grocer, *extra_firms], government=government)
    economy._apply_random_shocks = lambda: None
    economy.sector_subsidy_remaining_this_tick = 1_000_000.0
    return economy, clinic


def _worker(hid, cash):
    household = make_household(hid, cash_balance=cash, bank_deposit=0.0)
    household.employer_id = 77
    household.wage = 400.0  # income budget far above cash, so the liquidity cap binds
    return household


def _queue(household, clinic):
    household.queued_healthcare_firm_id = clinic.firm_id
    household.healthcare_queue_enter_tick = 0
    clinic.healthcare_queue.append(household.household_id)


def _budgets(economy):
    return economy._household_consumption_budgets(0.05, 30.0)


def test_on_by_default():
    assert CONFIG.households.healthcare_food_first_reserve is True


def test_flag_off_holds_no_reserve_and_never_reads_the_food_cost(off, monkeypatch):
    queued = _worker(1, 100.0)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    monkeypatch.setattr(economy, "_min_food_cost", lambda: pytest.fail("read with the flag off"))
    monkeypatch.setattr(economy, "_healthcare_food_first_reserves", lambda _l: pytest.fail("called with the flag off"))
    assert _budgets(economy)[0] == pytest.approx(100.0)


def test_min_food_cost_reads_min_food_and_highest_food_price():
    h = _worker(1, 100.0)
    economy, _ = _economy([h])
    assert economy._min_food_cost()[0] == pytest.approx(h.min_food_per_tick * FOOD_PRICE)
    economy.firm_lookup[901].price = 0.0
    assert economy._min_food_cost()[0] == 0.0  # no Food price posted: no food claim


def test_stock_less_seller_does_not_set_the_food_cost():
    # Round-2 review 54.2: one $40 seller with no stock raised the claim 6 -> 61.
    h = _worker(1, 100.0)
    empty = _firm(902, "Food", 40.0)
    empty.inventory_units = 0.0
    economy, _ = _economy([h], extra_firms=[empty])
    assert economy._min_food_cost()[0] == pytest.approx(h.min_food_per_tick * FOOD_PRICE)


def test_all_food_sellers_out_of_stock_uses_the_highest_posted_price():
    # Round-4 review B1: income_first and income_late plan before production.
    # A tick that opens with every Food firm sold out still has posted prices.
    h = _worker(1, 100.0)
    empty = _firm(902, "Food", 40.0)
    empty.inventory_units = 0.0
    economy, _ = _economy([h], extra_firms=[empty])
    economy.firm_lookup[901].inventory_units = 0.0
    cost = economy._min_food_cost()
    assert cost[0] == pytest.approx(h.min_food_per_tick * 40.0)
    assert np.all(np.isfinite(cost))
    economy.firms = [firm for firm in economy.firms if (firm.good_category or "").lower() != "food"]
    assert economy._min_food_cost()[0] == 0.0  # no Food firms at all


def test_stock_present_keeps_the_in_stock_price():
    # The no-stock fallback does not change the price when anyone has stock.
    h = _worker(1, 100.0)
    empty = _firm(902, "Food", 40.0)
    empty.inventory_units = 0.0
    economy, _ = _economy([h], extra_firms=[empty])
    with_stock = economy._min_food_cost()[0]
    assert with_stock == pytest.approx(h.min_food_per_tick * FOOD_PRICE)
    economy.firm_lookup[901].inventory_units = 0.0
    assert economy._min_food_cost()[0] == pytest.approx(h.min_food_per_tick * 40.0)
    assert economy._min_food_cost()[0] != pytest.approx(with_stock)


def test_income_first_sold_out_food_is_not_spent_on_the_visit(on, monkeypatch):
    # Behavior: under income_first, every Food firm at inventory 0 with a
    # posted price, the queued household's food claim is still positive and
    # the visit reserve does not spend the money needed for minimum food.
    queued = _worker(1, 0.0)
    posted = 9.0
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.healthcare_food_first_reserve = True
    with use_config(cfg):
        economy, clinic = _economy([queued], extra_firms=[_firm(902, "Food", posted)])
        _queue(queued, clinic)
        for firm in economy.firms:
            if (firm.good_category or "").lower() == "food":
                firm.inventory_units = 0.0
        food = float(economy._min_food_cost()[0])
        assert food == pytest.approx(queued.min_food_per_tick * posted)
        assert food > 0.0
        queued.cash_balance = food

        def planning_inputs(economy_arg):
            wages = [h.wage if h.is_employed else 0.0 for h in economy_arg.households]
            liquidity = [max(0.0, h.cash_balance) for h in economy_arg.households]
            return wages, liquidity, {}

        monkeypatch.setattr("payment_behavior.planning_inputs", planning_inputs)
        assert economy.payment_sequence == "income_first"
        reserve = float(economy._healthcare_food_first_reserves(np.array([food]))[0])
        budget = _budgets(economy)[0]
    assert reserve == pytest.approx(0.0)
    assert budget == pytest.approx(food)


def test_one_high_price_seller_with_one_unit_sets_the_food_cost():
    # Business review: the max over in-stock sellers lets one fringe seller
    # (high price, a single unit) set every household's food claim. The claim
    # goes up, so the visit reserve goes down; food is not under-claimed.
    # Recorded here as the current rule (Q6-B); hardening it (option D) is a
    # follow-up.
    h = _worker(1, 100.0)
    pricey = _firm(902, "Food", 12.0)
    pricey.inventory_units = 1.0
    economy, _ = _economy([h], extra_firms=[pricey])
    assert economy._min_food_cost()[0] == pytest.approx(h.min_food_per_tick * 12.0)


@pytest.mark.parametrize("cash", [500.0, 70.0, 10.0, 0.0])
def test_claim_order_food_then_visit_then_rest(on, cash):
    queued = _worker(1, cash)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    food = float(economy._min_food_cost()[0])
    oop = economy.expected_healthcare_out_of_pocket(1)
    assert oop == pytest.approx(VISIT)  # no subsidy: the patient pays all
    reserve = min(oop, max(0.0, cash - food))
    assert economy._healthcare_food_first_reserves(np.array([cash]))[0] == pytest.approx(reserve)
    budget = _budgets(economy)[0]
    assert budget <= cash - reserve + 1e-9  # the reserve is held back from the cap
    if cash <= 70.0:
        assert budget == pytest.approx(cash - reserve)  # liquidity cap binds
    assert budget >= min(cash, food) - 1e-9  # the visit never takes food money


def test_low_cash_household_keeps_its_food_money(on):
    # The case #47 got wrong: cash below food + visit.
    queued = _worker(1, 15.0)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    food = float(economy._min_food_cost()[0])
    assert 0 < food < 15.0
    assert _budgets(economy)[0] == pytest.approx(food)


def _budget_with_flag(economy, flag, monkeypatch, **kwargs):
    monkeypatch.setattr(CONFIG.households, "healthcare_food_first_reserve", flag)
    return economy._household_consumption_budgets(0.05, 30.0, **kwargs)


def test_drawdown_is_computed_before_the_reserve(monkeypatch):
    # Round-2 review 54.1: a queued household whose income budget is below its
    # food cost, with liquidity just above food + visit. The savings drawdown
    # must come from its full liquidity, so its budget is not pushed below food.
    queued = _worker(1, 0.0)
    queued.employer_id, queued.wage = None, 0.0
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    food = float(economy._min_food_cost()[0])
    queued.cash_balance = food + VISIT + 1.0
    off_budget = _budget_with_flag(economy, False, monkeypatch)[0]
    on_budget = _budget_with_flag(economy, True, monkeypatch)[0]
    reserve = min(VISIT, queued.cash_balance - food)
    assert on_budget == pytest.approx(min(off_budget, queued.cash_balance - reserve))
    assert on_budget >= min(off_budget, food) - 1e-9


def test_property_budget_is_flag_off_budget_capped_at_liquidity_less_reserve(monkeypatch):
    rng = np.random.default_rng(54)
    for _ in range(200):
        cash = float(rng.uniform(0.0, 300.0))
        employed = bool(rng.integers(0, 2))
        queued = _worker(1, cash)
        queued.employer_id = 77 if employed else None
        queued.wage = float(rng.uniform(0.0, 120.0)) if employed else 0.0
        economy, clinic = _economy([queued])
        economy.firm_lookup[900].price = float(rng.uniform(0.0, 150.0))
        economy.firm_lookup[901].price = float(rng.uniform(0.5, 10.0))
        _queue(queued, clinic)
        food = float(economy._min_food_cost()[0])
        oop = economy.expected_healthcare_out_of_pocket(1)
        off_budget = _budget_with_flag(economy, False, monkeypatch)[0]
        on_budget = _budget_with_flag(economy, True, monkeypatch)[0]
        reserve = min(oop, max(0.0, cash - food))
        assert on_budget == pytest.approx(min(off_budget, cash - reserve), abs=1e-9)
        assert on_budget >= min(off_budget, food) - 1e-9
        assert on_budget <= off_budget + 1e-12


def test_unqueued_household_unaffected_and_subsidy_lowers_reserve(on):
    queued, free = _worker(1, 200.0), _worker(2, 200.0)
    economy, clinic = _economy([queued, free], subsidy_level=50)
    _queue(queued, clinic)
    budgets = _budgets(economy)
    assert budgets[1] == pytest.approx(200.0)
    assert budgets[0] == pytest.approx(200.0 - VISIT * 0.5)


def test_rent_and_loans_come_before_food(on, monkeypatch):
    queued = _worker(1, 80.0)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    monkeypatch.setattr(economy, "_legacy_obligations_due", lambda: np.array([50.0]))
    food = float(economy._min_food_cost()[0])
    budget = economy._household_consumption_budgets(0.05, 30.0, settled_income=True)[0]
    left = 80.0 - 50.0
    reserve = min(VISIT, max(0.0, left - food))
    assert budget <= left - reserve + 1e-9


def test_reserve_lapses_once_served(on):
    queued = _worker(1, 200.0)
    economy, clinic = _economy([queued])
    _queue(queued, clinic)
    assert _budgets(economy)[0] == pytest.approx(200.0 - VISIT)
    economy._process_healthcare_services({})
    assert queued.queued_healthcare_firm_id is None
    assert _budgets(economy)[0] == pytest.approx(queued.cash_balance)


def test_bad_inputs_and_edges(on):
    h = _worker(1, 100.0)
    economy, _ = _economy([h])
    # Not queued: government returns nothing, reserve is 0.
    assert economy._healthcare_food_first_reserves(np.array([100.0]))[0] == 0.0
    # Negative liquidity never makes a negative reserve.
    economy2, clinic2 = _economy([_worker(2, 100.0)])
    _queue(economy2.households[0], clinic2)
    assert economy2._healthcare_food_first_reserves(np.array([-5.0]))[0] == 0.0
    economy2.firm_lookup[901].price = float("nan")
    assert economy2._min_food_cost()[0] == 0.0  # non-finite Food price ignored


def _two_clinics(bad_price):
    """Household 1 queued at the $60 clinic, household 2 at a clinic posting ``bad_price``."""
    fine, stuck = _worker(1, 200.0), _worker(2, 200.0)
    bad = _firm(902, "Healthcare", VISIT)
    economy, clinic = _economy([stuck, fine], extra_firms=[bad])
    economy.firms = [bad, clinic, *[f for f in economy.firms if f not in (bad, clinic)]]
    _queue(fine, clinic)
    _queue(stuck, bad)
    bad.price = bad_price
    return economy


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf")])
def test_non_finite_clinic_price_reserves_nothing_on_legacy(on, bad_price):
    # #45's quote walk raises on a NaN or infinite provider price. The budget
    # pass skips that one provider instead, so it cannot fail every tick: its
    # household reserves $0 (the legacy charge reads a NaN price as
    # max(0, nan) = 0), and the other clinic's household keeps its reserve.
    economy = _two_clinics(bad_price)
    budgets = _budgets(economy)
    assert budgets[0] == pytest.approx(200.0)  # at the bad clinic: no reserve
    assert budgets[1] == pytest.approx(200.0 - VISIT)  # at the $60 clinic: reserve kept
    assert economy._healthcare_food_first_ids == frozenset({1})
    with pytest.raises(ValueError):
        economy.expected_healthcare_out_of_pocket_all()  # the public getter still raises


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf")])
def test_non_finite_clinic_price_reserves_nothing_on_payment_sequences(bad_price):
    # The payment-sequence walk has no price check, so the public getter
    # returns inf (or 0 for NaN) for that household. The budget pass leaves
    # the provider out: no inf reserve.
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.healthcare_food_first_reserve = True
    with use_config(cfg):
        economy = _two_clinics(bad_price)
        reserves = economy._healthcare_food_first_reserves(np.array([200.0, 200.0]))
    assert reserves[0] == 0.0
    assert reserves[1] == pytest.approx(VISIT)
    assert economy._healthcare_food_first_ids == frozenset({1})


def _live(sequence, ticks, flag, *, covered=False, seed=42):
    from regression_snapshot import _set_seed
    from run_large_simulation import create_large_economy

    cfg = clone_config()
    cfg.payment_sequence = sequence
    cfg.households.healthcare_food_first_reserve = flag
    if covered:
        cfg.payment_care_mode = "covered"
    with use_config(cfg):
        _set_seed(seed)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=150, num_firms_per_category=3)
        seen = []
        original = economy._healthcare_food_first_reserves

        def watch(liquidity):
            reserves = original(liquidity)
            food = economy._min_food_cost()
            oop = economy.expected_healthcare_out_of_pocket_all()
            seen.append((np.asarray(liquidity).copy(), food, reserves.copy(),
                         np.array([oop.get(h.household_id, 0.0) for h in economy.households])))
            return reserves

        economy._healthcare_food_first_reserves = watch
        for _ in range(ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
    return economy, seen


@pytest.mark.parametrize("sequence", ["legacy", "income_first", "income_late"])
def test_step_reserve_respects_the_claim_order(sequence):
    economy, seen = _live(sequence, 40, True)
    assert seen, "the reserve must run inside Economy.step()"
    any_reserve = False
    for liquidity, food, reserves, oop in seen:
        assert np.all(reserves >= 0.0)
        assert np.all(reserves <= oop + 1e-9)
        assert np.all(reserves <= np.maximum(liquidity - food, 0.0) + 1e-9)
        any_reserve |= bool((reserves > 0).any())
    assert any_reserve, "some queued household must hold a reserve in 40 live ticks"


def test_step_covered_care_is_a_no_op():
    _economy_on, seen = _live("income_first", 20, True, covered=True)
    assert all(not (reserves > 0).any() for _l, _f, reserves, _o in seen)


def test_step_queued_households_plan_minimum_food_first_on_payment_sequences(monkeypatch):
    # The payment-sequence planner otherwise splits the budget by preference,
    # so a budget held at the food cost would still buy too little food.
    from agents import HouseholdAgent

    calls = []
    original = HouseholdAgent._plan_category_purchases

    def record(self, budget, *args, **kwargs):
        calls.append((self.household_id, bool(kwargs.get("min_food_first"))))
        return original(self, budget, *args, **kwargs)

    monkeypatch.setattr(HouseholdAgent, "_plan_category_purchases", record)
    economy, seen = _live("income_first", 40, True)
    flagged = [hid for hid, first in calls if first]
    assert flagged, "queued households with a visit to pay for must plan food first"
    assert economy._healthcare_food_first_ids <= {h.household_id for h in economy.households}


def test_flag_off_never_plans_food_first_on_payment_sequences(monkeypatch):
    from agents import HouseholdAgent

    calls = []
    original = HouseholdAgent._plan_category_purchases

    def record(self, budget, *args, **kwargs):
        calls.append(bool(kwargs.get("min_food_first")))
        return original(self, budget, *args, **kwargs)

    monkeypatch.setattr(HouseholdAgent, "_plan_category_purchases", record)
    _live("income_first", 20, False)
    assert calls and not any(calls)  # main's payment-sequence planner, unchanged
