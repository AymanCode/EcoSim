"""Services expansion loans follow firm demand, not economy-wide unemployment (2026-10-02, item 2).

Owner: Services slot capacity grows through bank loans for firms with plenty
of demand over their supply. Before, `_maybe_offer_long_term_capital_loan`
offered the loan only while unemployment was at least
`long_term_capital_unemployment_trigger` (0.10). On legacy a Services firm
now qualifies when it is slot-bound and its unmet demand over the last
five weeks (`service_unmet_demand_window`) is at least
`services_expansion_min_excess_demand_ratio` (0.25) of its output over the
same weeks; the other gates and the bank checks are unchanged. Housing keeps
the unemployment trigger.
"""

from types import SimpleNamespace

import pytest

from tools.checks.run_agent_scenarios import isolated_run, small_world


def _services_firm(*, slots, unmet_per_week, produced=12.0):
    economy = small_world(1337, category="Services")
    economy.current_tick = 40
    economy.in_warmup = False
    firm = economy.firms[0]
    firm.production_capacity_units = float(slots)  # Services capacity = worker slots
    firm.last_units_produced = produced
    firm.last_units_sold = produced  # sold out
    firm.lost_sales_streak = 5
    firm.price = 20.0  # the marginal worker pays (the unchanged MRPL gate)
    firm.service_unmet_demand_window = [unmet_per_week] * 5
    return economy, firm


def _offer(economy, firm, unemployment_rate):
    capacity_before = float(firm.production_capacity_units)
    economy._maybe_offer_long_term_capital_loan(
        firm=firm,
        health_snapshot=SimpleNamespace(sell_through_rate=1.0),
        unemployment_rate=unemployment_rate,
        total_households=len(economy.households),
    )
    loans = [loan for loan in economy.bank.loans_for("firm", firm.firm_id)
             if loan.get("subtype") == "long_term_capital"]
    return bool(loans), float(firm.production_capacity_units) - capacity_before


def test_sold_out_slot_bound_services_firm_gets_loan_at_low_unemployment():
    with isolated_run(1337):
        economy, firm = _services_firm(slots=1, unmet_per_week=12.0)
        granted, added = _offer(economy, firm, unemployment_rate=0.05)
        assert granted
        assert added > 0
        assert firm.last_long_term_loan_tick == economy.current_tick


def test_services_firm_with_idle_slots_gets_no_loan_even_at_high_unemployment():
    with isolated_run(1337):
        economy, firm = _services_firm(slots=10, unmet_per_week=12.0)  # one worker, ten slots
        granted, added = _offer(economy, firm, unemployment_rate=0.30)
        assert not granted
        assert added == 0


@pytest.mark.parametrize("ratio_of_output, expected", [(0.24, False), (0.25, True), (0.50, True)])
def test_excess_demand_ratio_gate(ratio_of_output, expected):
    with isolated_run(1337):
        economy, firm = _services_firm(slots=1, unmet_per_week=12.0 * ratio_of_output)
        granted, _ = _offer(economy, firm, unemployment_rate=0.05)
        assert granted is expected


def test_cooldown_still_applies():
    with isolated_run(1337):
        economy, firm = _services_firm(slots=1, unmet_per_week=12.0)
        firm.last_long_term_loan_tick = economy.current_tick - 10
        granted, _ = _offer(economy, firm, unemployment_rate=0.05)
        assert not granted


def test_housing_keeps_unemployment_trigger():
    with isolated_run(1337):
        economy = small_world(1337, category="Housing")
        economy.current_tick = 40
        firm = economy.firms[0]
        firm.current_tenants = [1]  # one unit, full
        snapshot = SimpleNamespace(sell_through_rate=1.0)
        economy._maybe_offer_long_term_capital_loan(firm, snapshot, 0.05, 100)
        assert firm.max_rental_units == 1
        economy._maybe_offer_long_term_capital_loan(firm, snapshot, 0.12, 100)
        assert firm.max_rental_units > 1


def test_excess_demand_ratio_is_validated():
    from config import SimulationConfig
    config = SimulationConfig()
    config.firms.services_expansion_min_excess_demand_ratio = -0.1
    with pytest.raises(ValueError):
        config.__post_init__()
