import pytest

from config import clone_config, use_config
from payment_sectors import PaymentGoodsMarket
from payments import PaymentBook


@pytest.fixture
def checkout(factory):
    config = clone_config()
    config.payment_sequence = "income_first"

    def make(sellers, *, cash=100, subsidy=0, food_credit=0, known=None, warmup=False, target=1):
        # Freeze effective quotes and vary stock directly in the counterfactual.
        household = factory.household(
            household_id=1, cash_balance=cash, min_food_per_tick=1,
            goods_inventory={}, awareness_pool={"services": known or []},
        )
        household.price_sensitivity = 0.0
        household.quality_lavishness = 1.0
        firms = [
            factory.firm(firm_id=fid, category=category, good_name=f"{category} {fid}", price=price,
                         inventory_units=supply, last_units_produced=supply, quality_level=quality)
            for fid, (category, price, supply, quality) in enumerate(sellers, 1)
        ]
        government = factory.government()
        if subsidy:
            government.sector_subsidy_target = "services"
            government._sector_subsidy_rate = 0.4
        ec = factory.economy(households=[household], firms=firms, government=government)
        ec.in_warmup = warmup
        ec.sector_subsidy_remaining_this_tick = subsidy
        ec.payment_state["restrictions"]["G"] = subsidy
        ec.payment_state["food_credit"] = {1: food_credit}
        ec.payment_book = PaymentBook(ec, timing="income_first")
        market = PaymentGoodsMarket(ec, {1: {"planned_purchases": {target: 10.0}}}, firms)
        for fid, (_, price, supply, _) in enumerate(sellers, 1):
            market.prices[fid] = price
            market.remaining[fid] = supply
        market.first_pass()
        market.second_pass()
        market.finish()
        return ec, household, market

    with use_config(config):
        yield make


@pytest.mark.parametrize("alternate_price", [5.0, 20.0])
@pytest.mark.parametrize("subsidy", [0.0, 14.0])
def test_reroute_debits_fit_the_funded_original_order(checkout, alternate_price, subsidy):
    origin = ("Services", 10.0, 2.0, 5)
    alternate = ("Services", alternate_price, 15.0, 5)
    ec, buyer, market = checkout([origin, alternate], cash=34, subsidy=subsidy)
    stock_ec, stock_buyer, stock_market = checkout(
        [("Services", 10.0, 10.0, 5), alternate], cash=34, subsidy=subsidy,
    )
    base_units = stock_market.sales[1]["units_sold"]
    equivalent = (base_units - 2.0) * 0.76
    delivered = equivalent * 10 / alternate_price
    assert market.sales[1]["units_sold"] == pytest.approx(2)
    assert market.sales[2]["units_sold"] == pytest.approx(delivered)
    assert market.paid_inbound_units[2] == pytest.approx(delivered)
    assert market.accepted[1][1] == pytest.approx(2 + equivalent)
    assert market.services_outbound_matches == {1: pytest.approx(equivalent)}
    assert ec.services_unmet_demand == pytest.approx(base_units - 2 - equivalent)
    assert ec.services_unmet_demand_by_firm == {1: pytest.approx(base_units - 2)}
    assert ec.current_tick_unmet_demand_by_firm == {1: pytest.approx(base_units - 2)}
    assert buyer.cash_balance + 1e-6 >= stock_buyer.cash_balance >= 0
    assert ec.payment_state["restrictions"]["G"] + 1e-6 >= stock_ec.payment_state["restrictions"]["G"]
    assert ec.payment_book.clearing_cash == pytest.approx(20 + equivalent * 10)
    assert not stock_market.paid_inbound_units


@pytest.mark.parametrize("higher_quality,paid_units", [(2, 7.0), (3, 7.6)])
def test_mixed_free_and_paid_alternatives_clear_one_order(checkout, higher_quality, paid_units):
    ec, buyer, market = checkout([
        ("Services", 10.0, 0.0, 5),
        ("Services", 0.0, 3.0, 10 if higher_quality == 2 else 1),
        ("Services", 10.0, 12.0, 10 if higher_quality == 3 else 1),
    ], known=[1, 2, 3])
    assert market.accepted[1][1] == pytest.approx(10)
    assert market.sales[2]["units_sold"] == pytest.approx(10 - paid_units)
    assert market.sales[2]["revenue"] == 0
    assert market.paid_inbound_units == {3: pytest.approx(paid_units)}
    assert market.services_outbound_matches == {1: pytest.approx(10)}
    assert buyer.services_consumed_this_tick == pytest.approx(10)
    assert buyer.cash_balance == pytest.approx(100 - paid_units * 10)
    assert ec.services_unmet_demand == pytest.approx(0)
    assert ec.services_unmet_demand_by_firm == {1: pytest.approx(10)}


def test_no_reroute_for_unfunded_order_despite_grocery_credit(checkout):
    ec, buyer, market = checkout(
        [("Services", 10.0, 0.0, 5), ("Services", 10.0, 10.0, 5)], cash=0, food_credit=40,
    )
    assert not market.sales and not market.paid_inbound_units
    assert not ec.services_unmet_demand_by_firm
    assert ec.payment_state["food_credit"][1] == 40 and buyer.cash_balance == 0


@pytest.mark.parametrize("case", ["warmup", "unaware", "category_name", "food"])
def test_rerouting_scope(checkout, case):
    category = "Food" if case == "food" else "Services"
    _, buyer, market = checkout(
        [(category, 10.0, 0.0, 5), (category, 10.0, 10.0, 5)],
        known=[1] if case == "unaware" else None,
        warmup=case == "warmup", target="Services 1" if case == "category_name" else 1,
    )
    assert buyer.cash_balance == 100
    assert not market.sales and not market.paid_inbound_units


def test_rerouting_uses_available_service_units(checkout):
    ec, buyer, market = checkout([
        ("Services", 10.0, 0.0, 5), ("Services", 10.0, 1.0, 5), ("Food", 1.0, 10.0, 5),
    ])
    assert market.paid_inbound_units == {2: 1}
    assert market.remaining[2] == 0 and market.remaining[3] == 10
    assert buyer.cash_balance == 90
    assert ec.services_unmet_demand == 9
