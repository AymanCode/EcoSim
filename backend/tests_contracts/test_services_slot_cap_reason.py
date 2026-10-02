"""Services slot cap is a recorded hiring block (2026-10-02, item 3; diagnostics only).

A Services firm with demand (sold out or lost sales) whose worker slots are
all filled plans no hires; `_plan_services_capacity_labor` now records the
reason `services_slot_cap`, as other planners record theirs.
"""

import pytest

from agents import FirmHealthSnapshot
from tests_contracts.factories import make_firm


def _snapshot(sell_through):
    return FirmHealthSnapshot(
        cash_runway_ticks=100.0, smoothed_profit_margin=0.2, sell_through_rate=sell_through,
        inventory_weeks=0.0, unfilled_positions_streak=0, worker_turnover_this_tick=0,
        survival_mode=False, burn_mode=False, category_wage_anchor_p75=40.0,
    )


def _firm(*, slots, workers, lost=0.0):
    firm = make_firm(firm_id=7, category="Services", is_baseline=False, production_capacity_units=float(slots))
    firm.employees = list(range(100, 100 + workers))
    firm.actual_wages = {e: firm.wage_offer for e in firm.employees}
    firm._invalidate_wage_bill_cache()
    firm.last_tick_raw_lost_sales_units = lost
    return firm


@pytest.mark.parametrize("sell_through, lost", [(1.0, 0.0), (0.5, 3.0)])
def test_slot_bound_firm_with_demand_records_slot_cap(sell_through, lost):
    firm = _firm(slots=3, workers=3, lost=lost)
    plan = firm._plan_services_capacity_labor(_snapshot(sell_through))
    assert plan["planned_hires_count"] == 0
    assert firm.decision_diagnostics["hiring_block_reason"] == "services_slot_cap"
    assert firm.last_hiring_block_reason == "services_slot_cap"
    assert firm.decision_diagnostics["hiring_block_worker_slots"] == 3


def test_slot_bound_firm_without_demand_records_no_slot_cap():
    firm = _firm(slots=3, workers=3)
    firm._plan_services_capacity_labor(_snapshot(0.5))
    assert firm.decision_diagnostics.get("hiring_block_reason") != "services_slot_cap"


def test_firm_with_idle_slots_hires_without_block():
    firm = _firm(slots=5, workers=3, lost=3.0)
    plan = firm._plan_services_capacity_labor(_snapshot(1.0))
    assert plan["planned_hires_count"] == 2
    assert firm.decision_diagnostics["hiring_block_reason"] == ""
