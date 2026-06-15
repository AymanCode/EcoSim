import numpy as np
import pytest
import zlib

from agents import HouseholdAgent, build_awareness_market_views
from config import CONFIG
from tests_contracts.factories import make_economy, make_firm, make_government, make_household


def test_batch_household_updates_preserve_ledgers_without_method_calls():
    household = make_household(household_id=1, cash_balance=1_000.0)
    household.employer_id = 101
    household.wage = 100.0
    household.reset_tick_ledger()
    firm = make_firm(firm_id=101, category="Food", is_baseline=False)
    economy = make_economy(households=[household], firms=[firm], government=make_government())

    def fail_if_called(key: str, amount: float) -> None:
        raise AssertionError(f"hot batch path should not call add_ledger_flow({key!r}, {amount!r})")

    household.add_ledger_flow = fail_if_called

    economy._batch_apply_household_updates(
        transfer_plan={1: 25.0},
        wage_taxes={1: 15.0},
        per_household_purchases={1: {"FoodFirm101": (2.0, 10.0)}},
        good_category_lookup={"FoodFirm101": "food"},
    )

    assert household.last_tick_ledger["wage"] == pytest.approx(100.0)
    assert household.last_tick_ledger["transfers"] == pytest.approx(25.0)
    assert household.last_tick_ledger["taxes"] == pytest.approx(-15.0)
    assert household.last_tick_ledger["goods"] == pytest.approx(-20.0)
    assert household.cash_balance == pytest.approx(1_090.0)


def test_purchase_tie_break_noise_is_cached_and_matches_existing_seed_formula():
    household = make_household(household_id=17)
    category = "food"
    length = 4
    category_seed = zlib.crc32(category.encode("utf-8"))
    tie_break_seed = ((household.household_id * 1_315_423_911) ^ category_seed) & 0xFFFFFFFF
    expected = np.random.default_rng(seed=tie_break_seed).uniform(-0.25, 0.25, size=length)

    first = household._get_purchase_tie_break_noise(category, length)
    second = household._get_purchase_tie_break_noise(category, length)

    assert first is second
    assert first.flags.writeable is False
    assert np.allclose(first, expected)


def test_purchase_tie_break_noise_reuses_cached_prefix_for_growing_lengths(monkeypatch):
    household = make_household(household_id=18)
    category = "services"
    category_seed = zlib.crc32(category.encode("utf-8"))
    tie_break_seed = ((household.household_id * 1_315_423_911) ^ category_seed) & 0xFFFFFFFF
    expected_two = np.random.default_rng(seed=tie_break_seed).uniform(-0.25, 0.25, size=2)
    expected_ten = np.random.default_rng(seed=tie_break_seed).uniform(-0.25, 0.25, size=10)

    real_default_rng = np.random.default_rng
    rng_calls = 0

    def counting_default_rng(*args, **kwargs):
        nonlocal rng_calls
        rng_calls += 1
        return real_default_rng(*args, **kwargs)

    monkeypatch.setattr(np.random, "default_rng", counting_default_rng)

    first = household._get_purchase_tie_break_noise(category, 1)
    second = household._get_purchase_tie_break_noise(category, 2)
    second_again = household._get_purchase_tie_break_noise(category, 2)
    ten = household._get_purchase_tie_break_noise(category, 10)

    assert rng_calls == 1
    assert second is second_again
    assert first.flags.writeable is False
    assert second.flags.writeable is False
    assert ten.flags.writeable is False
    assert np.allclose(second, expected_two)
    assert np.allclose(ten, expected_ten)


def test_awareness_pool_refresh_populates_cached_membership_sets():
    household = make_household(household_id=22)
    market = {
        "food": [
            {"firm_id": 1, "price": 10.0, "quality": 3.0},
            {"firm_id": 2, "price": 11.0, "quality": 4.0},
            {"firm_id": 3, "price": 12.0, "quality": 5.0},
        ]
    }

    household.refresh_awareness_pool(market, current_tick=0)
    first = household._get_awareness_pool_set("food")
    second = household._get_awareness_pool_set("food")

    assert first is second
    assert first == set(household.awareness_pool["food"])


def test_awareness_pool_grows_to_cap_then_rotates_one_firm(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "awareness_pool_initial_size", 7)
    monkeypatch.setattr(CONFIG.households, "awareness_pool_max_size", 10)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_interval", 4)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_drop_count", 1)

    household = make_household(household_id=31)
    market = {
        "food": [
            {"firm_id": firm_id, "price": 8.0 + firm_id, "quality": 2.0 + (firm_id % 5)}
            for firm_id in range(1, 21)
        ]
    }

    household.refresh_awareness_pool(market, current_tick=0)
    initial_pool = list(household.awareness_pool["food"])
    assert len(initial_pool) == 7

    household.refresh_awareness_pool(market, current_tick=4)
    assert len(household.awareness_pool["food"]) == 8

    household.refresh_awareness_pool(market, current_tick=8)
    assert len(household.awareness_pool["food"]) == 9

    household.refresh_awareness_pool(market, current_tick=12)
    full_pool = list(household.awareness_pool["food"])
    assert len(full_pool) == 10
    assert set(initial_pool).issubset(set(full_pool))

    household.current_primary_firm["food"] = full_pool[0]
    household.refresh_awareness_pool(market, current_tick=16)
    rotated_pool = list(household.awareness_pool["food"])

    assert len(rotated_pool) == 10
    assert full_pool[0] in rotated_pool
    assert set(rotated_pool) != set(full_pool)
    assert len(set(rotated_pool)) == len(rotated_pool)


def test_precomputed_awareness_market_views_preserve_refresh_behavior(monkeypatch):
    monkeypatch.setattr(CONFIG, "random_seed", 42)
    monkeypatch.setattr(CONFIG.households, "awareness_pool_initial_size", 7)
    monkeypatch.setattr(CONFIG.households, "awareness_pool_max_size", 10)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_interval", 4)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_drop_count", 1)

    market = {
        "Food": [
            {"firm_id": firm_id, "price": 8.0 + firm_id, "quality": 2.0 + (firm_id % 5)}
            for firm_id in range(1, 21)
        ] + [
            {"firm_id": 99, "price": 0.0, "quality": 99.0},
        ],
        "services": [
            {"firm_id": firm_id, "price": 6.0 + firm_id / 10.0, "quality": 3.0 + (firm_id % 7)}
            for firm_id in range(101, 121)
        ],
    }
    baseline = make_household(household_id=51)
    optimized = make_household(household_id=51)
    views = build_awareness_market_views(market)

    for tick in (0, 4, 8, 12):
        baseline.refresh_awareness_pool(market, current_tick=tick)
        optimized.refresh_awareness_pool(
            market,
            current_tick=tick,
            awareness_market_views=views,
        )
        assert optimized.awareness_pool == baseline.awareness_pool
        assert optimized.last_pool_refresh_tick == baseline.last_pool_refresh_tick

    baseline.current_primary_firm["food"] = baseline.awareness_pool["food"][0]
    optimized.current_primary_firm["food"] = optimized.awareness_pool["food"][0]
    baseline.refresh_awareness_pool(market, current_tick=16)
    optimized.refresh_awareness_pool(
        market,
        current_tick=16,
        awareness_market_views=views,
    )

    assert optimized.awareness_pool == baseline.awareness_pool
    assert optimized.last_pool_refresh_tick == baseline.last_pool_refresh_tick
    assert 99 not in optimized.awareness_pool["food"]
    assert optimized._get_awareness_pool_set("food") == baseline._get_awareness_pool_set("food")
    assert optimized._get_awareness_pool_set("services") == baseline._get_awareness_pool_set("services")


def test_batch_consumption_reuses_precomputed_awareness_market_views(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "awareness_pool_initial_size", 7)
    monkeypatch.setattr(CONFIG.households, "awareness_pool_max_size", 10)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_interval", 4)

    households = [
        make_household(household_id=61, cash_balance=5_000.0),
        make_household(household_id=62, cash_balance=5_000.0),
    ]
    for household in households:
        household.category_weights = {"food": 0.5, "services": 0.5}
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        household.services_consumed_last_tick = household.min_services_per_tick

    firms = [
        make_firm(firm_id=idx, category="Food", is_baseline=False)
        for idx in range(1, 21)
    ] + [
        make_firm(firm_id=idx, category="Services", is_baseline=False)
        for idx in range(101, 121)
    ]
    economy = make_economy(households=households, firms=firms, government=make_government())
    good_category_lookup, category_market_snapshot, _, _ = economy._build_firm_market_views()

    original_refresh = HouseholdAgent.refresh_awareness_pool
    view_ids = []

    def spy_refresh(self, category_market_info, current_tick, awareness_market_views=None):
        view_ids.append(id(awareness_market_views))
        return original_refresh(
            self,
            category_market_info,
            current_tick,
            awareness_market_views=awareness_market_views,
        )

    monkeypatch.setattr(HouseholdAgent, "refresh_awareness_pool", spy_refresh)

    economy._batch_plan_consumption(
        market_prices={firm.good_name: firm.price for firm in firms},
        category_market_snapshot=category_market_snapshot,
        good_category_lookup=good_category_lookup,
        unemployment_rate=0.0,
        unemployment_benefit=0.0,
    )

    assert len(view_ids) == len(households)
    assert None not in view_ids
    assert len(set(view_ids)) == 1


def test_batch_consumption_precomputes_awareness_array_indices(monkeypatch):
    household = make_household(household_id=71, cash_balance=5_000.0)
    household.category_weights = {"food": 1.0}
    household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
    firms = [
        make_firm(firm_id=idx, category="Food", is_baseline=False)
        for idx in (11, 12, 13, 14)
    ]
    economy = make_economy(households=[household], firms=firms, government=make_government())
    good_category_lookup, category_market_snapshot, _, _ = economy._build_firm_market_views()
    captured_cache = {}

    def capture_cache(
        self,
        budget,
        firm_market_info,
        price_cache=None,
        biased_weights_override=None,
        category_fraction_override=None,
        category_option_cache=None,
        category_array_cache=None,
        debug_category_fractions=None,
    ):
        captured_cache.update(category_array_cache or {})
        return {}

    monkeypatch.setattr(HouseholdAgent, "_plan_category_purchases", capture_cache)

    economy._batch_plan_consumption(
        market_prices={firm.good_name: firm.price for firm in firms},
        category_market_snapshot=category_market_snapshot,
        good_category_lookup=good_category_lookup,
        unemployment_rate=0.0,
        unemployment_benefit=0.0,
    )

    indices_by_firm_id = captured_cache["food"]["indices_by_firm_id"]

    assert indices_by_firm_id == {
        11: (0,),
        12: (1,),
        13: (2,),
        14: (3,),
    }


def test_awareness_array_index_filter_preserves_market_order_and_empty_result():
    household = make_household(household_id=72)
    arrays = {
        "firm_ids": np.array([5, 2, 7, 3], dtype=np.int32),
        "prices": np.array([50.0, 20.0, 70.0, 30.0], dtype=np.float64),
        "qualities": np.array([5.0, 2.0, 7.0, 3.0], dtype=np.float64),
        "indices_by_firm_id": {
            5: (0,),
            2: (1,),
            7: (2,),
            3: (3,),
        },
    }
    household.awareness_pool["food"] = [3, 5]
    household._cache_awareness_pool_set("food", household.awareness_pool["food"])

    firm_ids, prices, qualities = household._filter_category_arrays_to_awareness_pool("food", arrays)

    assert firm_ids.tolist() == [5, 3]
    assert prices.tolist() == [50.0, 30.0]
    assert qualities.tolist() == [5.0, 3.0]

    household.awareness_pool["services"] = [99]
    household._cache_awareness_pool_set("services", household.awareness_pool["services"])

    empty_ids, empty_prices, empty_qualities = household._filter_category_arrays_to_awareness_pool(
        "services",
        arrays,
    )

    assert empty_ids.size == 0
    assert empty_prices.size == 0
    assert empty_qualities.size == 0


def test_indexed_awareness_filter_preserves_purchase_plan_vs_legacy_mask():
    legacy = make_household(household_id=73, cash_balance=5_000.0)
    indexed = make_household(household_id=73, cash_balance=5_000.0)
    for household in (legacy, indexed):
        household.category_weights = {"food": 0.5, "services": 0.5}
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        household.services_consumed_last_tick = household.min_services_per_tick
        household.awareness_pool["food"] = [5, 1, 3]
        household.awareness_pool["services"] = [104, 101, 103]
        household._cache_awareness_pool_set("food", household.awareness_pool["food"])
        household._cache_awareness_pool_set("services", household.awareness_pool["services"])

    category_arrays = {
        "food": {
            "firm_ids": np.array([1, 2, 3, 4, 5], dtype=np.int32),
            "prices": np.array([10.0, 11.0, 12.0, 13.0, 14.0], dtype=np.float64),
            "qualities": np.array([5.0, 4.0, 6.0, 3.0, 7.0], dtype=np.float64),
        },
        "services": {
            "firm_ids": np.array([101, 102, 103, 104, 105], dtype=np.int32),
            "prices": np.array([8.0, 9.0, 10.0, 11.0, 12.0], dtype=np.float64),
            "qualities": np.array([4.0, 5.0, 7.0, 6.0, 3.0], dtype=np.float64),
        },
    }
    indexed_arrays = {}
    for category, arrays in category_arrays.items():
        indexed_arrays[category] = dict(arrays)
        indexed_arrays[category]["indices_by_firm_id"] = {
            int(fid): (idx,)
            for idx, fid in enumerate(arrays["firm_ids"].tolist())
        }
    price_cache = {
        "food": (10.0, 12.0, 14.0),
        "services": (8.0, 10.0, 12.0),
    }

    legacy_plan = legacy._plan_category_purchases(
        250.0,
        {},
        price_cache=price_cache,
        category_fraction_override={"food": 0.5, "services": 0.5},
        category_array_cache=category_arrays,
    )
    indexed_plan = indexed._plan_category_purchases(
        250.0,
        {},
        price_cache=price_cache,
        category_fraction_override={"food": 0.5, "services": 0.5},
        category_array_cache=indexed_arrays,
    )

    assert indexed_plan.keys() == legacy_plan.keys()
    for firm_id, quantity in legacy_plan.items():
        assert indexed_plan[firm_id] == pytest.approx(quantity)
    assert indexed.current_primary_firm == legacy.current_primary_firm


def test_batch_consumption_uses_bounded_awareness_pool(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "awareness_pool_initial_size", 7)
    monkeypatch.setattr(CONFIG.households, "awareness_pool_max_size", 10)
    monkeypatch.setattr(CONFIG.households, "pool_refresh_interval", 4)

    household = make_household(household_id=41, cash_balance=5_000.0)
    household.category_weights = {"food": 0.5, "services": 0.5}
    household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
    household.services_consumed_last_tick = household.min_services_per_tick
    firms = [
        make_firm(firm_id=idx, category="Food", is_baseline=False)
        for idx in range(1, 21)
    ] + [
        make_firm(firm_id=idx, category="Services", is_baseline=False)
        for idx in range(101, 121)
    ]
    economy = make_economy(households=[household], firms=firms, government=make_government())
    good_category_lookup, category_market_snapshot, _, _ = economy._build_firm_market_views()

    plan = economy._batch_plan_consumption(
        market_prices={firm.good_name: firm.price for firm in firms},
        category_market_snapshot=category_market_snapshot,
        good_category_lookup=good_category_lookup,
        unemployment_rate=0.0,
        unemployment_benefit=0.0,
    )[household.household_id]

    assert len(household.awareness_pool["food"]) == 7
    assert len(household.awareness_pool["services"]) == 7
    assert len(plan["planned_purchases"]) <= 14
    assert set(plan["planned_purchases"]).issubset(
        set(household.awareness_pool["food"]) | set(household.awareness_pool["services"])
    )
