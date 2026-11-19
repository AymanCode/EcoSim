"""Isolated checks for the optional household shopping experiment."""

import random
from types import SimpleNamespace

import numpy as np
import pytest

from config import HouseholdBehaviorConfig, clone_config, use_config
from household_shopping import ordered_plans
from payment_loans import prepare_household_dues
from payment_sectors import PaymentGoodsMarket
from payments import PaymentBook


@pytest.fixture(autouse=True)
def _income_first_sequence():
    """Every test runs on income_first; legacy is not tested here."""
    config = clone_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        yield


def _world(factory, cfg, *, cash=100.0, category="Food", stocks=(0.0, 100.0), prices=(10.0, 20.0)):
    hh = factory.household(household_id=1, cash_balance=cash, goods_inventory={},
                           min_food_per_tick=2.0, awareness_pool={category.lower(): [1, 2]},
                           quality_lavishness=1.0, price_sensitivity=1.0)
    firms = [factory.firm(firm_id=i + 1, category=category, good_name=f"{category}{i + 1}",
                          inventory_units=stock, price=price, cash_balance=0.0)
             for i, (stock, price) in enumerate(zip(stocks, prices))]
    for firm, stock in zip(firms, stocks):
        firm.inventory_units = stock  # Stubbed market supply, also for non-storable services.
    economy = factory.economy(households=[hh], firms=firms, government=factory.government(cash_balance=0.0))
    economy._estimated_firm_market_supply = lambda firm, current_tick_capacity: firm.inventory_units
    economy._effective_market_price = lambda firm, available: firm.price
    economy.government._sector_subsidy_rate = 0.0
    if cfg.payment_sequence != "legacy":
        economy.payment_book = PaymentBook(economy, timing=cfg.payment_sequence)
    return economy, hh, firms


def test_experiment_defaults():
    config = HouseholdBehaviorConfig()
    assert config.fix_spending_leak is False
    assert config.fix_food_tracker_lag is True
    assert config.stockout_substitution_share == 0.76


@pytest.mark.parametrize("source", ["fraction", "biased", "traits"])
@pytest.mark.parametrize("fix_food_tracker_lag", [False, True])
def test_housing_removed_before_shifts_and_purchases(factory, source, fix_food_tracker_lag):
    cfg = clone_config()
    cfg.households.fix_spending_leak = True
    cfg.households.fix_food_tracker_lag = fix_food_tracker_lag
    with use_config(cfg):
        hh = factory.household(category_weights={"food": 0.4, "housing": 0.3, "services": 0.3},
                               food_preference=1.0, housing_preference=1.0, services_preference=1.0)
        hh.food_consumed_last_tick = cfg.households.food_health_high_threshold
        hh.food_consumed_this_tick = cfg.households.food_health_high_threshold
        hh.services_consumed_last_tick = hh.min_services_per_tick
        hh.services_consumed_this_tick = hh.min_services_per_tick
        arrays = {category: {"firm_ids": np.array([fid]), "prices": np.array([10.0]),
                             "qualities": np.array([5.0])}
                  for category, fid in (("food", 1), ("housing", 2), ("services", 3))}
        weights = {"food": 0.4, "housing": 0.3, "services": 0.3}
        kwargs = ({"category_fraction_override": weights} if source == "fraction" else
                  {"biased_weights_override": weights} if source == "biased" else {})
        fractions = {}
        prices = {category: (10.0, 10.0, 10.0) for category in arrays}
        purchases = hh._plan_category_purchases(100.0, price_cache=prices, category_array_cache=arrays,
                                                debug_category_fractions=fractions, **kwargs)
        assert fractions == pytest.approx({"food": 4 / 7, "services": 3 / 7})
        assert 2 not in purchases
        cfg.households.fix_spending_leak = False
        old = hh._plan_category_purchases(100.0, price_cache=prices, category_array_cache=arrays, **kwargs)
        assert 2 in old


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_stockout_falls_back_once_across_both_passes_and_conserves_money(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg)
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 10.0}}}, firms)
        initial = hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance
        market.first_pass()
        assert hh.goods_inventory["Food2"] == pytest.approx(0.76)
        assert market.accepted[1][1] == pytest.approx(1.52)
        market.second_pass()
        purchases, sales = market.finish()
        assert purchases[1]["Food2"] == pytest.approx((3.8, 20.0))
        assert sales[2]["revenue"] == pytest.approx(76.0)
        assert market.accepted[1][1] == pytest.approx(7.6)
        assert eco.food_unmet_demand == pytest.approx(2.4)
        assert hh.cash_balance == pytest.approx(24.0)
        for firm in firms:
            eco.payment_book.release_firm_receipts(firm)
        assert hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance == pytest.approx(initial)


def test_first_pass_counts_alternative_food_in_real_units(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg)
        third = factory.firm(firm_id=3, category="Food", good_name="Food3", inventory_units=100, price=10)
        firms.append(third)
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 2.0, 3: 5.0}}}, firms)
        market.first_pass()
        assert hh.goods_inventory["Food2"] == pytest.approx(0.76)
        assert hh.goods_inventory["Food3"] == pytest.approx(1.24)


def test_preference_pool_and_no_pool_price_order(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, stocks=(0, 100), prices=(10, 10))
        third = factory.firm(firm_id=3, category="Food", good_name="Food3", inventory_units=100,
                             price=5, quality_level=1)
        firms.append(third)
        eco._effective_firm_quality = lambda firm: {1: 1, 2: 10, 3: 1}[firm.firm_id]
        hh.awareness_pool["food"] = [1, 2, 3]
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 2}}}, firms)
        market.first_pass()
        assert "Food2" in hh.goods_inventory and "Food3" not in hh.goods_inventory

        eco, hh, firms = _world(factory, cfg, stocks=(0, 100), prices=(10, 10))
        third = factory.firm(firm_id=3, category="Food", good_name="Food3", inventory_units=100, price=5)
        firms.append(third)
        hh.awareness_pool = {}
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 2}}}, firms)
        market.first_pass()
        assert "Food3" in hh.goods_inventory and "Food2" not in hh.goods_inventory


def test_services_substitution_uses_multiple_pool_sellers_and_id_ties(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, category="Services", stocks=(0, 0.5), prices=(10, 10))
        third = factory.firm(firm_id=3, category="Services", good_name="Services3",
                             inventory_units=100, price=10)
        outside_pool = factory.firm(firm_id=4, category="Services", good_name="Services4",
                                    inventory_units=100, price=1)
        third.inventory_units = outside_pool.inventory_units = 100
        firms.extend([third, outside_pool])
        hh.awareness_pool["services"] = [1, 3, 2]
        eco._effective_firm_quality = lambda firm: 5.0
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 5}}}, firms)
        market.first_pass()
        market.second_pass()
        purchases, sales = market.finish()
        assert purchases[1]["Services2"] == pytest.approx((0.5, 10))
        assert purchases[1]["Services3"] == pytest.approx((3.3, 10))
        assert "Services4" not in purchases[1]
        assert hh.services_consumed_this_tick == pytest.approx(3.8)
        assert sum(item["revenue"] for item in sales.values()) == pytest.approx(38)
        # Household unmet demand is what found no seller; the sold-out seller's
        # own lost-sales signal is its full shortfall (1.2 unserved + 3.8 redirected).
        assert eco.services_unmet_demand == pytest.approx(1.2)
        assert eco.services_unmet_demand_by_firm[1] == pytest.approx(5.0)
        assert eco.current_tick_unmet_demand_by_firm[1] == pytest.approx(5.0)


def test_no_substitution_for_a_cash_shortfall(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=5, stocks=(100, 100))
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 10}}}, firms)
        market.first_pass()
        market.second_pass()
        market.finish()
        assert hh.goods_inventory == {"Food1": pytest.approx(0.5)}
        assert eco.food_unmet_demand == 0


def test_zero_price_alternative_is_bounded_and_does_not_spend_the_budget(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, stocks=(0, 1), prices=(10, 0))
        third = factory.firm(firm_id=3, category="Food", good_name="Food3", inventory_units=100, price=10)
        firms.append(third)
        hh.awareness_pool = {}  # The free seller comes before the paid seller.
        plans = {1: {"planned_purchases": {1: 4}, "budget": 40}}
        market = PaymentGoodsMarket(eco, plans, firms)
        market.first_pass()
        market.second_pass()
        purchases, sales = market.finish()
        assert market.accepted[1][1] == pytest.approx(3.04)
        assert purchases[1]["Food2"] == pytest.approx((1, 0))
        assert sales[3]["revenue"] == pytest.approx(30.4)


def test_substitution_uses_funded_subsidy_and_conserves_money(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=10, stocks=(0, 100), prices=(10, 10))
        eco.government.cash_balance = 10
        eco.government.sector_subsidy_target = "food"
        eco.government._sector_subsidy_rate = 0.5
        eco.sector_subsidy_remaining_this_tick = 10
        eco.payment_state["restrictions"]["G"] = 10
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 4}}}, firms)
        market.first_pass()
        market.second_pass()
        purchases, sales = market.finish()
        assert purchases[1]["Food2"][0] == pytest.approx(1.52)
        assert sales[2]["revenue"] == pytest.approx(15.2)
        assert hh.cash_balance == pytest.approx(2.4)
        assert eco.government.cash_balance == pytest.approx(2.4)
        eco.payment_book.release_firm_receipts(firms[1])
        assert hh.cash_balance + eco.government.cash_balance + firms[1].cash_balance == pytest.approx(20)


def test_seeded_rationing_uses_private_rng_and_changes_each_tick(factory):
    cfg = clone_config()
    cfg.households.fix_spending_leak = True
    cfg.random_seed = 42
    with use_config(cfg):
        plans = {i: {} for i in reversed(range(1, 21))}
        state = random.getstate()
        orders = []
        for tick in (10, 10, 11):
            observed = [hid for hid, _ in ordered_plans(plans, tick, 4)]
            expected = sorted(plans)
            random.Random((42 * 1_000_003 + tick * 7_919 + 4) & 0xFFFFFFFF).shuffle(expected)
            assert observed == expected
            orders.append(observed)
        assert orders[0] == orders[1] != orders[2]
        assert random.getstate() == state
        cfg.households.fix_spending_leak = False
        assert [hid for hid, _ in ordered_plans(plans, 10, 4)] == list(plans)


def test_payment_passes_and_unmet_use_their_own_seeded_orders(factory, monkeypatch):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        households = [factory.household(household_id=i, min_food_per_tick=1,
                                         awareness_pool={"food": [i]}) for i in range(1, 12)]
        firms = [factory.firm(firm_id=i, category="Food", inventory_units=0, price=10)
                 for i in range(1, 12)]
        eco = factory.economy(households=households, firms=firms)
        eco.current_tick = 9
        eco._estimated_firm_market_supply = lambda firm, current_tick_capacity: firm.inventory_units
        eco._effective_market_price = lambda firm, available: firm.price
        eco.government._sector_subsidy_rate = 0.0
        eco.payment_book = PaymentBook(eco)
        plans = {h.household_id: {"planned_purchases": {h.household_id: 1}}
                 for h in reversed(households)}
        market = PaymentGoodsMarket(eco, plans, firms)
        order = []
        original = PaymentGoodsMarket._buy
        def record_buy(self, household, target, wanted):
            order.append(household.household_id)
            return original(self, household, target, wanted)
        monkeypatch.setattr(PaymentGoodsMarket, "_buy", record_buy)
        market.first_pass()
        assert order == [hid for hid, _ in ordered_plans(plans, 9, 1)]
        order.clear()
        market.second_pass()
        assert order == [hid for hid, _ in ordered_plans(plans, 9, 2)]
        order.clear()
        eco._record_firm_unmet_demand = lambda fid, qty: order.append(fid)
        market.finish()
        assert order == [hid for hid, _ in ordered_plans(plans, 9, 3)]


def test_zero_share_fundable_stockout_keeps_full_lost_sales_and_moves_no_money(factory):
    # income_first: with redirection off, a fully fundable stockout is the
    # sold-out seller's full lost sale, also household unmet demand, and nothing is bought elsewhere.
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    cfg.households.stockout_substitution_share = 0.0
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=100.0, stocks=(0.0, 100.0), prices=(10.0, 20.0))
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 10.0}}}, firms)
        market.first_pass()
        market.second_pass()
        purchases, _sales = market.finish()
        assert "Food2" not in purchases.get(1, {})
        assert eco.food_unmet_demand == pytest.approx(10.0)
        assert eco.current_tick_unmet_demand_by_firm[1] == pytest.approx(10.0)
        assert hh.cash_balance == pytest.approx(100.0)
        assert firms[1].cash_balance == pytest.approx(0.0)


def test_zero_share_lost_sales_are_credited_by_remaining_affordability(factory):
    # finish() credits a stockout only up to what the household can still
    # fund after its other purchases; a later purchase that uses all the cash leaves none.
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    cfg.households.stockout_substitution_share = 0.0
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=100.0, stocks=(0.0, 100.0), prices=(10.0, 20.0))
        services = factory.firm(firm_id=3, category="Services", good_name="Services3",
                                inventory_units=100, price=10.0, cash_balance=0.0)
        services.inventory_units = 100
        firms.append(services)
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 10.0, 3: 10.0}}}, firms)
        market.first_pass()
        market.second_pass()
        purchases, _sales = market.finish()
        assert purchases[1]["Services3"] == pytest.approx((10.0, 10.0))
        assert hh.cash_balance == pytest.approx(0.0)
        assert eco.food_unmet_demand == pytest.approx(0.0)
        assert eco.current_tick_unmet_demand_by_firm.get(1, 0.0) == pytest.approx(0.0)


def test_settled_reroutes_use_receiver_units_and_reset_on_zero(factory):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, category="Services", stocks=(2, 0.5), prices=(10, 16))
        third = factory.firm(firm_id=3, category="Services", good_name="Services3", price=20)
        third.inventory_units = 10
        firms.append(third)
        hh.awareness_pool = {}
        for firm in firms:
            firm.last_units_produced = firm.inventory_units
        initial = hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance
        eco.current_tick = 10
        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {1: 7, 3: 0.75}}}, firms)
        market.first_pass()
        tick = SimpleNamespace(payment_arm=True, goods_market=market, per_firm_sales=market.sales)
        prepare_household_dues(eco)
        eco._phase_misc_and_healthcare(tick)

        assert market.rerouted_service_units_by_firm == pytest.approx({2: 0.5, 3: 1.5})
        assert market.substituted[1][1] == pytest.approx(3.8)
        rerouted_revenue = sum(market.prices[fid] * qty for fid, qty in market.rerouted_service_units_by_firm.items())
        assert rerouted_revenue == pytest.approx(market.substituted[1][1] * market.prices[1], abs=1e-6)
        assert eco.services_unmet_demand_by_firm == pytest.approx({1: 5})
        assert eco.services_unmet_demand == pytest.approx(1.2)
        assert tick.per_household_purchases[1] == {"Services1": (2, 10), "Services2": (0.5, 16),
                                                  "Services3": (2.25, 20)}
        assert [market.remaining[f.firm_id] for f in firms] == pytest.approx([0, 0, 7.75])
        assert [f.inventory_units for f in firms] == [2, 0.5, 10]
        assert hh.services_consumed_this_tick == pytest.approx(4.75)
        assert hh.cash_balance == pytest.approx(27)
        for firm in firms:
            eco.payment_book.release_firm_receipts(firm)
        assert eco.payment_book.clearing_cash == pytest.approx(0)
        assert hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance == pytest.approx(initial)
        audit = eco._capture_audit_firm_state()
        assert audit[1]["last_rerouted_service_units"] == 0
        assert audit[2]["last_rerouted_service_units"] == pytest.approx(0.5)
        assert audit[3]["last_rerouted_service_units"] == pytest.approx(1.5)

        eco.current_tick += 1
        for firm in firms:
            firm.age_in_ticks += 1
        eco.services_unmet_demand_by_firm.clear()
        eco.payment_book = PaymentBook(eco, timing="income_first")
        market = PaymentGoodsMarket(eco, {}, firms)
        market.first_pass()
        prepare_household_dues(eco)
        eco._phase_misc_and_healthcare(SimpleNamespace(payment_arm=True, goods_market=market, per_firm_sales=market.sales))
        assert third.last_rerouted_service_units == 0


@pytest.mark.parametrize("scenario", ["rejected", "free", "subsidized", "good_name", "off"])
def test_only_committed_stockout_alternatives_count(factory, monkeypatch, scenario):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.households.fix_spending_leak = scenario != "off"
    with use_config(cfg):
        price = 0 if scenario == "free" else 20
        origin_stock = 1 if scenario == "good_name" else 0
        eco, hh, (origin, receiver) = _world(factory, cfg, category="Services", stocks=(origin_stock, 10),
                                              prices=(10, price))
        target = origin.firm_id
        if scenario == "good_name":
            origin.good_name = receiver.good_name = target = "Same service"
        if scenario == "rejected":
            monkeypatch.setattr(PaymentBook, "commit_sale", lambda *args, **kwargs: False)
        if scenario == "subsidized":
            eco.government.sector_subsidy_target = "Services"
            eco.government._sector_subsidy_rate = 0.5
            eco.government.cash_balance = 20
            eco.payment_state["restrictions"]["G"] = 20
            eco.sector_subsidy_remaining_this_tick = 20

        market = PaymentGoodsMarket(eco, {1: {"planned_purchases": {target: 4}}}, [origin, receiver])
        market.first_pass()
        market.second_pass()
        _, sales = market.finish()

        expected = {"rejected": 0, "free": 4, "subsidized": 1.52, "good_name": 0, "off": 0}[scenario]
        expected_sold = 3 if scenario == "good_name" else expected
        assert market.rerouted_service_units_by_firm.get(receiver.firm_id, 0) == pytest.approx(expected)
        assert sales.get(receiver.firm_id, {}).get("units_sold", 0) == pytest.approx(expected_sold)
        if scenario == "subsidized":
            assert hh.cash_balance == pytest.approx(84.8)
            assert eco.government.cash_balance == pytest.approx(4.8)
            assert eco.payment_state["restrictions"]["G"] == pytest.approx(4.8)
            assert eco.payment_book.release_firm_receipts(receiver) == pytest.approx(30.4)
