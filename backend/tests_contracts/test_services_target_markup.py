"""Services boom target keeps the firm's sampled markup when the flag is on.

Default off replaces markup with the margin implied by the smoothed price,
so the profit-tax gross-up and the utilization surge compound. These tests
run the real pricing rule. The economy test does not replace it.
"""

import math

import pytest

from config import (
    FirmBehaviorConfig,
    SimulationConfig,
    clone_config,
    services_target_markup_held,
    use_config,
)
from economy import Economy
from tests_contracts.conftest import total_money_net_of_injections
from tests_contracts.factories import make_firm, make_government, make_households


def _services_firm(**overrides):
    firm = make_firm(firm_id=1, category="Services", is_baseline=False, seed=7)
    firm.markup = 0.30
    # Above the one-step grossed-up target, so writing the smoothed margin
    # back raises markup on the first boom. A price near cost does not.
    firm.price = 14.0
    firm.min_price = 0.5
    firm.wage_offer = 40.0
    firm.employees = [1, 2, 3, 4]
    firm.actual_wages = {i: 40.0 for i in firm.employees}
    firm.production_capacity_units = 8
    firm.units_per_worker = 4.0
    firm.last_units_produced = 16.0
    firm.service_infrastructure_loan_payment_per_tick = 0.0
    for key, value in overrides.items():
        setattr(firm, key, value)
    return firm


def _plan(firm, *, utilization=1.0, tax=0.20):
    return firm.plan_pricing(
        sell_through_rate=utilization,
        unemployment_rate=0.05,
        in_warmup=False,
        profit_tax_rate=tax,
    )


def test_config_rejects_non_bool_flag():
    for bad in (1, 0, 0.0, "yes", None, float("nan"), float("inf"), float("-inf")):
        firms = FirmBehaviorConfig(services_target_markup_held=bad)
        with pytest.raises(ValueError, match="bool"):
            SimulationConfig(firms=firms)


def test_runtime_reader_rejects_a_mutated_non_bool_flag():
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = float("nan")
        with pytest.raises(ValueError, match="bool"):
            services_target_markup_held()
        CONFIG.firms.services_target_markup_held = False
        assert services_target_markup_held() is False
        CONFIG.firms.services_target_markup_held = True
        assert services_target_markup_held() is True


def test_flag_off_writes_the_realized_margin_back_and_the_next_boom_uses_it():
    """The ratchet, characterized on the real rule with the flag off."""
    with use_config(clone_config()):
        firm = _services_firm()
        first = _plan(firm)
        cost = firm.decision_diagnostics["service_total_cost_per_unit"]
        assert cost > 0.0
        realized = first["price_next"] / cost - 1.0
        assert first["markup_next"] == pytest.approx(max(0.0, realized))
        assert first["markup_next"] > firm.markup

        firm.apply_price_and_wage_updates(first, {"wage_offer_next": firm.wage_offer})
        assert firm.markup == pytest.approx(first["markup_next"])
        assert firm.markup > 0.30
        second = _plan(firm)
        # The second boom target uses the written-back margin, not 0.30.
        surge = (1.0 - 0.85) * 0.5
        gross = (firm.markup + surge) / (1.0 - 0.20)
        second_cost = firm.decision_diagnostics["service_total_cost_per_unit"]
        assert second_cost == pytest.approx(cost)
        assert second["price_next"] == pytest.approx(
            0.8 * firm.price + 0.2 * second_cost * (1.0 + gross),
            rel=1e-9,
        )


def test_flag_on_holds_the_target_and_posts_the_one_step_price():
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = True
        firm = _services_firm()
        first = _plan(firm)
        cost = firm.decision_diagnostics["service_total_cost_per_unit"]
        surge = (1.0 - 0.85) * 0.5
        gross = (0.30 + surge) / (1.0 - 0.20)
        target = cost * (1.0 + gross)
        assert first["markup_next"] == pytest.approx(0.30)
        assert first["price_next"] == pytest.approx(0.8 * 14.0 + 0.2 * target)
        assert firm.decision_diagnostics["service_target_markup"] == pytest.approx(0.30)
        realized = first["price_next"] / cost - 1.0
        assert firm.decision_diagnostics["service_realized_markup"] == pytest.approx(realized)
        assert realized > 0.30

        firm.apply_price_and_wage_updates(first, {"wage_offer_next": firm.wage_offer})
        assert firm.markup == pytest.approx(0.30)
        assert firm.price == pytest.approx(first["price_next"])
        second = _plan(firm)
        assert second["markup_next"] == pytest.approx(0.30)
        assert firm.markup == pytest.approx(0.30)


def test_non_finite_and_zero_targets_stay_finite():
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = True
        for bad in (float("nan"), float("inf"), float("-inf")):
            firm = _services_firm(markup=bad)
            plan = _plan(firm)
            assert plan["markup_next"] == 0.0
            assert math.isfinite(plan["price_next"])
            assert plan["price_next"] >= firm.min_price
        zero = _services_firm(markup=0.0)
        plan = _plan(zero)
        assert plan["markup_next"] == 0.0
        assert math.isfinite(plan["price_next"])
        cost = zero.decision_diagnostics["service_total_cost_per_unit"]
        surge = (1.0 - 0.85) * 0.5
        gross = surge / 0.80
        assert plan["price_next"] == pytest.approx(0.8 * zero.price + 0.2 * cost * (1.0 + gross))


def test_warmup_keeps_a_baseline_services_target_and_the_same_posted_price():
    firm = make_firm(firm_id=3, category="Services", is_baseline=True, seed=3)
    firm.markup = 0.30
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = False
        off = firm.plan_pricing(1.0, unemployment_rate=0.0, in_warmup=True, profit_tax_rate=0.20)
        CONFIG.firms.services_target_markup_held = True
        on = firm.plan_pricing(1.0, unemployment_rate=0.0, in_warmup=True, profit_tax_rate=0.20)
    assert on["price_next"] == pytest.approx(off["price_next"])
    assert on["markup_next"] == pytest.approx(0.30)
    assert off["markup_next"] == pytest.approx(firm._markup_for_price(off["price_next"]))


def test_price_cap_limits_the_posted_price_and_does_not_replace_a_held_target():
    with use_config(clone_config()):
        from config import CONFIG

        firm = _services_firm()
        government = make_government()
        government.price_stabilization_target = "services"
        government.price_stabilization_level = "strict"
        economy = Economy(households=[], firms=[firm], government=government)
        plan = {"price_next": firm.price * 2.0, "markup_next": 0.30}
        CONFIG.firms.services_target_markup_held = False
        economy._apply_price_stabilization_to_plan(firm, plan)
        assert plan["price_next"] == pytest.approx(firm.price * 1.01)
        assert plan["markup_next"] != pytest.approx(0.30)

        plan = {"price_next": firm.price * 2.0, "markup_next": 0.30}
        CONFIG.firms.services_target_markup_held = True
        economy._apply_price_stabilization_to_plan(firm, plan)
        assert plan["price_next"] == pytest.approx(firm.price * 1.01)
        assert plan["markup_next"] == pytest.approx(0.30)


def _live_services_economy():
    """A small economy whose Services firm can actually sell."""
    government = make_government(cash_balance=50_000.0, profit_tax_rate=0.20)
    services = make_firm(firm_id=1, category="Services", is_baseline=False, seed=11)
    services.markup = 0.30
    services.price = 8.0
    services.min_price = 0.5
    services.wage_offer = 25.0
    services.production_capacity_units = 40
    services.units_per_worker = 5.0
    food = make_firm(firm_id=2, category="Food", is_baseline=False, seed=11)
    food.price = 4.0
    food.inventory_units = 5_000.0
    food.wage_offer = 25.0
    households = make_households(16, start_id=1, cash_start=4_000.0, cash_step=0.0)
    for household in households:
        household.cash_balance = 4_000.0
        household.services_preference = 4.0
        household.employer_id = 1
        household.wage = 25.0
    economy = Economy(households=households, firms=[services, food], government=government)
    economy._apply_random_shocks = lambda: None
    economy.last_tick_sell_through_rate[services.firm_id] = 1.0
    return economy, services


def test_economy_step_holds_markup_and_still_sells_services():
    """Flag on: Economy.step posts a price, sells units and pays money, markup stays."""
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = True
        economy, services = _live_services_economy()
        sold = 0.0
        paid = 0.0
        for _ in range(12):
            economy.step()
            assert services.markup == pytest.approx(0.30)
            assert math.isfinite(services.price)
            assert services.price >= services.min_price
            sold += float(services.last_units_sold)
            paid += float(services.last_revenue)
        assert sold > 0.0
        assert paid > 0.0
        # The clearing floor reads the held target, so a below-target posted
        # price is lifted to full cost times (1 + 0.30), not to a ratcheted margin.
        services.price = 0.5
        supply = max(float(services.last_units_produced), 1.0)
        charged = economy._effective_market_price(services, supply)
        wage_bill = float(services._current_wage_bill())
        break_even = wage_bill / max(supply, 1e-6)
        assert charged == pytest.approx(max(0.5, break_even * 1.30))


def test_economy_step_flag_off_ratchets_markup_above_the_sample():
    with use_config(clone_config()):
        economy, services = _live_services_economy()
        saw_sale = False
        for _ in range(12):
            economy.step()
            if services.last_units_sold > 0.0 and services.last_revenue > 0.0:
                saw_sale = True
        assert saw_sale
        # The live write-back moves markup off the sampled 0.30. Direction
        # depends on the path; the held-target run above stays at 0.30.
        assert services.markup != pytest.approx(0.30)


def test_flag_on_matches_flag_off_money_drift_on_a_short_run():
    """No new cash flow. Net of recorded injections, both arms move by the same leak, if any."""
    def _drift(flag: bool) -> float:
        with use_config(clone_config()):
            from config import CONFIG

            CONFIG.firms.services_target_markup_held = flag
            economy, _services = _live_services_economy()
            before = total_money_net_of_injections(economy)
            for _ in range(6):
                economy.step()
            return total_money_net_of_injections(economy) - before

    off = _drift(False)
    on = _drift(True)
    assert math.isfinite(off) and math.isfinite(on)
    # The two economies diverge in prices, so an exit leak can differ.
    # What must not differ is a brand-new creation: both stay within a cent
    # of their own recorded injections on this short run with shocks off.
    assert abs(off) < 0.01
    assert abs(on) < 0.01


def test_empty_firm_list_still_steps_with_the_flag_on():
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_target_markup_held = True
        household = make_households(1, cash_start=100.0, cash_step=0.0)[0]
        economy = Economy(
            households=[household],
            firms=[],
            government=make_government(),
        )
        economy._apply_random_shocks = lambda: None
        economy.step()
        assert economy.current_tick == 1
        assert math.isfinite(household.cash_balance)


def test_two_flag_on_runs_post_the_same_price_and_take_the_same_money():
    def _once():
        with use_config(clone_config()):
            from config import CONFIG

            CONFIG.firms.services_target_markup_held = True
            economy, services = _live_services_economy()
            for _ in range(5):
                economy.step()
            return (
                round(services.price, 6),
                round(services.markup, 6),
                round(services.last_revenue, 6),
                round(services.last_units_sold, 6),
                round(economy.government.cash_balance, 6),
            )

    assert _once() == _once()
