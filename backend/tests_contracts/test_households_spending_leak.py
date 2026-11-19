"""Isolated checks for the optional household shopping experiment."""

import random

import numpy as np
import pytest

from config import HouseholdBehaviorConfig, clone_config, use_config
from household_shopping import ordered_plans
from payment_sectors import PaymentGoodsMarket
from payments import PaymentBook


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


@pytest.mark.parametrize("timing", ["income_first", "legacy"])
def test_zero_price_alternative_is_bounded_and_does_not_spend_the_budget(factory, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, stocks=(0, 1), prices=(10, 0))
        third = factory.firm(firm_id=3, category="Food", good_name="Food3", inventory_units=100, price=10)
        firms.append(third)
        hh.awareness_pool = {}  # The free seller comes before the paid seller.
        plans = {1: {"planned_purchases": {1: 4}, "budget": 40}}
        if timing == "legacy":
            purchases, sales = eco._clear_goods_market(plans, firms)
        else:
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


@pytest.mark.parametrize("scaled", [False, True])
def test_legacy_household_unmet_uses_unsatisfied_money_and_seller_keeps_lost_sales(factory, scaled):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, stocks=(1, 100), prices=(10, 20))
        plan = {"planned_purchases": {1: 10.0}, "budget": 100.0}
        if scaled:
            plan.update(_purchase_scale=1.0, _food_budget_cap=100.0)
        purchases, sales = eco._clear_goods_market({1: plan}, firms)
        assert purchases[1]["Food1"] == pytest.approx((1.0, 10.0))
        assert purchases[1]["Food2"] == pytest.approx((3.42, 20.0))
        assert sum(s["revenue"] for s in sales.values()) == pytest.approx(78.4)
        assert eco.food_unmet_demand == pytest.approx(2.16)
        # The sold-out seller lost 9 units of sales even though 6.84 were bought elsewhere.
        assert eco.current_tick_unmet_demand_by_firm[1] == pytest.approx(9.0)
        initial = hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance
        # Legacy settlement credits sellers first and charges the household at
        # the later household update boundary.
        for firm in firms:
            firm.cash_balance += sales[firm.firm_id]["revenue"]
        eco._batch_apply_household_updates({}, {}, purchases,
                                           good_category_lookup={f.good_name: "food" for f in firms},
                                           income_already_settled=True, per_firm_sales=sales)
        assert hh.cash_balance + sum(f.cash_balance for f in firms) + eco.government.cash_balance == pytest.approx(initial)


def test_legacy_stockout_does_not_create_demand_for_unaffordable_goods(factory):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=0)
        purchases, _ = eco._clear_goods_market({1: {"planned_purchases": {1: 10}, "budget": 100}}, firms)
        assert purchases[1] == {}
        assert eco.food_unmet_demand == 0


def test_legacy_substitution_respects_the_subsidy_on_settlement(factory):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        eco, hh, firms = _world(factory, cfg, cash=10, stocks=(0, 100), prices=(10, 10))
        eco.government.cash_balance = 10
        eco.government.sector_subsidy_target = "food"
        eco.government._sector_subsidy_rate = 0.5
        eco.sector_subsidy_cap_this_tick = 10
        eco.sector_subsidy_remaining_this_tick = 10
        purchases, sales = eco._clear_goods_market({1: {"planned_purchases": {1: 4}, "budget": 40}}, firms)
        assert purchases[1]["Food2"] == pytest.approx((1.52, 10))
        for firm in firms:
            firm.cash_balance += sales[firm.firm_id]["revenue"]
        eco._batch_apply_household_updates({}, {}, purchases, income_already_settled=True,
                                           per_firm_sales=sales,
                                           good_category_lookup={f.good_name: "food" for f in firms})
        assert hh.cash_balance == pytest.approx(2.4)
        assert eco.government.cash_balance == pytest.approx(2.4)
        assert hh.cash_balance + eco.government.cash_balance + sum(f.cash_balance for f in firms) == pytest.approx(20)


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


def test_legacy_clearing_uses_its_seeded_order(factory):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_spending_leak = True
    with use_config(cfg):
        households = [factory.household(household_id=i) for i in range(1, 12)]
        firm = factory.firm(firm_id=1, category="Food", inventory_units=0, price=10)
        eco = factory.economy(households=households, firms=[firm])
        eco.current_tick = 9
        plans = {h.household_id: {"planned_purchases": {1: 1}, "budget": 10} for h in households}
        purchases, _ = eco._clear_goods_market(plans, [firm])
        assert list(purchases) == [hid for hid, _ in ordered_plans(plans, 9, 4)]


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
    # Plan 3 [A-3], income_first: with redirection off, a fully fundable stockout is the
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
    # Plan 3 [A-3]: finish() credits a stockout only up to what the household can still
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
