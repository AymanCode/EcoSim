"""Bounded demand-responsive Services margin (rule C), flag off by default.

Flag off is main's write-back: the boom price grosses the margin up by the
profit tax, then stores the margin implied by the smoothed price. Flag on
skips that gross-up and stores a margin that steps with sell-through and the
firm's latest unmet share, clamped to [min, max]. The baseline Services firm
is held at 0. These tests call the real pricing rule. The economy test does
not replace it. The direction assertions fail if the step lines are removed.
"""

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from config import (
    FirmBehaviorConfig,
    SimulationConfig,
    clone_config,
    services_demand_margin_enabled,
    use_config,
)
from economy import Economy
from tests_contracts.conftest import total_money_net_of_injections
from tests_contracts.factories import make_firm, make_government, make_households

REPO = Path(__file__).resolve().parents[2]
MAIN_SHA = "82c7cddb1532842eb13188dd14a839e23bdfd60e"
WORKER = REPO / "backend" / "tools" / "benchmarks" / "evidence_panel_worker.py"
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _services_firm(**overrides):
    firm = make_firm(firm_id=1, category="Services", is_baseline=False, seed=7)
    firm.markup = 0.30
    firm.price = 14.0
    firm.min_price = 0.5
    firm.wage_offer = 40.0
    firm.employees = [1, 2, 3, 4]
    firm.actual_wages = {i: 40.0 for i in firm.employees}
    firm.production_capacity_units = 8
    firm.units_per_worker = 4.0
    firm.last_units_produced = 16.0
    firm.last_units_sold = 10.0
    firm.service_unmet_demand_window = [2.0]
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


def _enable():
    from config import CONFIG

    CONFIG.firms.services_demand_margin_enabled = True
    return CONFIG


def test_config_rejects_non_bool_flag_and_bad_bounds():
    for bad in (1, 0, 0.0, "yes", None, float("nan"), float("inf"), float("-inf")):
        firms = FirmBehaviorConfig(services_demand_margin_enabled=bad)
        with pytest.raises(ValueError, match="bool"):
            SimulationConfig(firms=firms)
    for field, bad in (
        ("services_margin_min", 1),
        ("services_margin_min", True),
        ("services_margin_min", float("nan")),
        ("services_margin_min", float("inf")),
        ("services_margin_max", float("-inf")),
        ("services_margin_step", 1),
        ("services_margin_step", 0.0),
        ("services_margin_step", -0.02),
    ):
        firms = FirmBehaviorConfig(**{field: bad})
        with pytest.raises(ValueError, match="services_margin"):
            SimulationConfig(firms=firms)
    with pytest.raises(ValueError, match="0 <= min <= max"):
        SimulationConfig(firms=FirmBehaviorConfig(services_margin_min=-0.01))
    with pytest.raises(ValueError, match="0 <= min <= max"):
        SimulationConfig(firms=FirmBehaviorConfig(services_margin_min=0.50, services_margin_max=0.20))
    defaults = FirmBehaviorConfig()
    assert defaults.services_demand_margin_enabled is False
    assert defaults.services_margin_min == 0.20
    assert defaults.services_margin_max == 1.00
    assert defaults.services_margin_step == 0.02


def test_runtime_reader_rejects_a_mutated_flag_or_bound():
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_demand_margin_enabled = 1
        with pytest.raises(ValueError, match="bool"):
            services_demand_margin_enabled()
        CONFIG.firms.services_demand_margin_enabled = False
        CONFIG.firms.services_margin_min = float("nan")
        with pytest.raises(ValueError, match="finite float"):
            services_demand_margin_enabled()
        CONFIG.firms.services_margin_min = 0.20
        assert services_demand_margin_enabled() is False
        CONFIG.firms.services_demand_margin_enabled = True
        assert services_demand_margin_enabled() is True


def test_flag_off_writes_the_grossed_up_margin_back():
    """Main's ratchet, on the real rule, with the switch off."""
    with use_config(clone_config()):
        firm = _services_firm()
        first = _plan(firm)
        cost = firm.decision_diagnostics["service_total_cost_per_unit"]
        assert cost == pytest.approx(10.0)
        surge = (1.0 - 0.85) * 0.5
        gross = (0.30 + surge) / 0.80
        target = cost * (1.0 + gross)
        assert first["price_next"] == pytest.approx(0.8 * 14.0 + 0.2 * target)
        assert first["price_next"] == pytest.approx(14.1375)
        realized = first["price_next"] / cost - 1.0
        assert first["markup_next"] == pytest.approx(max(0.0, realized))
        assert first["markup_next"] == pytest.approx(0.41375)
        assert first["markup_next"] > firm.markup

        firm.apply_price_and_wage_updates(first, {"wage_offer_next": firm.wage_offer})
        second = _plan(firm)
        second_gross = (firm.markup + surge) / 0.80
        assert second["price_next"] == pytest.approx(
            0.8 * firm.price + 0.2 * cost * (1.0 + second_gross),
            rel=1e-9,
        )


def test_step_up_down_and_hold_and_the_revert_fails_without_the_step():
    """Exact ±step. Deleting either step line makes this fail."""
    with use_config(clone_config()):
        _enable()
        up = _plan(_services_firm(), utilization=0.95)
        assert up["markup_next"] == pytest.approx(0.32)
        # Share exactly 0.05 does not step up, and an empty window is unmet 0.
        hold_share = _plan(
            _services_firm(last_units_sold=19.0, service_unmet_demand_window=[1.0]),
            utilization=1.0,
        )
        assert hold_share["markup_next"] == pytest.approx(0.30)
        empty = _plan(_services_firm(service_unmet_demand_window=[]), utilization=1.0)
        assert empty["markup_next"] == pytest.approx(0.30)
        # Between 0.85 and 0.95 the margin does not move, including the edges of the gap.
        for utilization in (0.85, 0.90, 0.9499):
            held = _plan(_services_firm(), utilization=utilization)
            assert held["markup_next"] == pytest.approx(0.30)
        down = _plan(_services_firm(), utilization=0.8499)
        assert down["markup_next"] == pytest.approx(0.28)
        # The boom price that week is the current margin plus the surge, with no tax gross-up.
        cost = 10.0
        surge = (0.95 - 0.85) * 0.5
        assert up["price_next"] == pytest.approx(0.8 * 14.0 + 0.2 * cost * (1.0 + 0.30 + surge))
        assert up["price_next"] == pytest.approx(13.9)


def test_margin_clamps_to_the_configured_bounds():
    with use_config(clone_config()):
        _enable()
        ceiling = _plan(_services_firm(markup=0.99), utilization=1.0)
        assert ceiling["markup_next"] == pytest.approx(1.00)
        floor = _plan(_services_firm(markup=0.21), utilization=0.50)
        assert floor["markup_next"] == pytest.approx(0.20)
        # A margin already outside the band is clamped even when the step does not fire.
        parked = _plan(_services_firm(markup=1.50), utilization=0.90)
        assert parked["markup_next"] == pytest.approx(1.00)
        low = _plan(_services_firm(markup=0.05), utilization=0.90)
        assert low["markup_next"] == pytest.approx(0.20)
        for bad in (float("nan"), float("inf"), float("-inf")):
            finite = _plan(_services_firm(markup=bad), utilization=0.90)
            assert finite["markup_next"] == pytest.approx(0.20)
            assert math.isfinite(finite["price_next"])


def test_baseline_margin_stays_at_cost_recovery_when_the_switch_is_on():
    firm = make_firm(firm_id=3, category="Services", is_baseline=True, seed=3)
    firm.markup = 0.30
    firm.price = 14.0
    firm.min_price = 0.5
    firm.wage_offer = 40.0
    firm.employees = [1, 2, 3, 4]
    firm.actual_wages = {i: 40.0 for i in firm.employees}
    firm.last_units_produced = 16.0
    firm.service_infrastructure_loan_payment_per_tick = 0.0
    with use_config(clone_config()):
        _enable()
        plan = _plan(firm)
        assert plan["markup_next"] == 0.0
        # Price uses a zero base margin plus the utilization surge, and no tax divisor.
        cost = firm.decision_diagnostics["service_total_cost_per_unit"]
        surge = (1.0 - 0.85) * 0.5
        assert plan["price_next"] == pytest.approx(0.8 * 14.0 + 0.2 * cost * (1.0 + surge))
        slump = _plan(firm, utilization=0.40)
        assert slump["markup_next"] == 0.0


def test_warmup_price_is_unchanged_and_a_baseline_target_is_zero_when_on():
    firm = make_firm(firm_id=3, category="Services", is_baseline=True, seed=3)
    firm.markup = 0.30
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_demand_margin_enabled = False
        off = firm.plan_pricing(1.0, unemployment_rate=0.0, in_warmup=True, profit_tax_rate=0.20)
        CONFIG.firms.services_demand_margin_enabled = True
        on = firm.plan_pricing(1.0, unemployment_rate=0.0, in_warmup=True, profit_tax_rate=0.20)
    assert on["price_next"] == pytest.approx(off["price_next"])
    assert on["markup_next"] == 0.0
    assert off["markup_next"] == pytest.approx(firm._markup_for_price(off["price_next"]))


def test_price_cap_limits_the_posted_price_and_keeps_a_stepped_margin():
    with use_config(clone_config()):
        from config import CONFIG

        firm = _services_firm()
        government = make_government()
        government.price_stabilization_target = "services"
        government.price_stabilization_level = "strict"
        economy = Economy(households=[], firms=[firm], government=government)
        plan = {"price_next": firm.price * 2.0, "markup_next": 0.32}
        CONFIG.firms.services_demand_margin_enabled = False
        economy._apply_price_stabilization_to_plan(firm, plan)
        assert plan["price_next"] == pytest.approx(firm.price * 1.01)
        assert plan["markup_next"] != pytest.approx(0.32)

        plan = {"price_next": firm.price * 2.0, "markup_next": 0.32}
        CONFIG.firms.services_demand_margin_enabled = True
        economy._apply_price_stabilization_to_plan(firm, plan)
        assert plan["price_next"] == pytest.approx(firm.price * 1.01)
        assert plan["markup_next"] == pytest.approx(0.32)


def test_food_pricing_is_not_the_services_margin():
    food = make_firm(firm_id=2, category="Food", is_baseline=False, seed=2)
    food.markup = 0.30
    food.last_units_sold = 10.0
    food.service_unmet_demand_window = [2.0]
    with use_config(clone_config()):
        _enable()
        assert food._services_demand_markup_next(1.0) is None


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
    services.last_units_sold = 10.0
    services.service_unmet_demand_window = [2.0]
    baseline = make_firm(firm_id=3, category="Services", is_baseline=True, seed=11)
    baseline.markup = 0.30
    baseline.price = 8.0
    baseline.wage_offer = 25.0
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
    economy = Economy(
        households=households,
        firms=[services, baseline, food],
        government=government,
    )
    economy._apply_random_shocks = lambda: None
    economy.last_tick_sell_through_rate[services.firm_id] = 1.0
    economy.last_tick_sell_through_rate[baseline.firm_id] = 1.0
    return economy, services, baseline


def test_economy_step_stores_the_stepped_margin_and_holds_baseline_at_zero():
    """The step reaches firm.markup through Economy.step. plan_pricing is not replaced."""
    with use_config(clone_config()):
        from config import CONFIG

        CONFIG.firms.services_demand_margin_enabled = True
        CONFIG.time.warmup_ticks = 0
        economy, services, baseline = _live_services_economy()
        economy.step()
        assert services.markup == pytest.approx(0.32)
        assert baseline.markup == pytest.approx(0.0)
        assert math.isfinite(services.price) and services.price >= services.min_price
        assert float(services.last_units_sold) > 0.0 or float(services.last_revenue) >= 0.0


def test_flag_on_matches_flag_off_money_on_a_short_run():
    """No new cash flow. Net of recorded injections, both arms stay within a cent."""

    def _drift(flag: bool) -> float:
        with use_config(clone_config()):
            from config import CONFIG

            CONFIG.firms.services_demand_margin_enabled = flag
            CONFIG.time.warmup_ticks = 0
            economy, _services, _baseline = _live_services_economy()
            before = total_money_net_of_injections(economy)
            for _ in range(4):
                economy.step()
            return total_money_net_of_injections(economy) - before

    off = _drift(False)
    on = _drift(True)
    assert math.isfinite(off) and math.isfinite(on)
    assert abs(off) < 0.01
    assert abs(on) < 0.01


def _panel_fingerprint(root: Path, sequence: str, overrides: dict) -> str:
    spec = {
        "root": str(root),
        "payment_sequence": sequence,
        "seed": 42,
        "households": 100,
        "firms_per_category": 2,
        "ticks": 60,
        "config_overrides": overrides,
    }
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "spec.json"
        out_path = Path(tmp) / "out.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = "0"
        for name in THREAD_ENV:
            env[name] = "1"
        completed = subprocess.run(
            [os.environ.get("ECOSIM_PYTHON", sys.executable), str(WORKER), str(spec_path), str(out_path)],
            check=False,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"panel worker failed for {root} {sequence}:\n{completed.stderr}\n{completed.stdout}"
            )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    return payload["fingerprint"]


def _main_worktree() -> Path:
    path = Path("/tmp/ecosim-main-82c7cdd")
    economy = path / "backend" / "economy.py"
    if economy.exists():
        head = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if head == MAIN_SHA:
            return path
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(REPO), "worktree", "add", "--detach", str(path), MAIN_SHA],
        check=True,
    )
    return path


@pytest.mark.parametrize("sequence", ["income_first", "legacy"])
def test_flag_off_fingerprint_matches_main_over_60_ticks(sequence):
    main = _main_worktree()
    off = _panel_fingerprint(REPO, sequence, {"firms.services_demand_margin_enabled": "False"})
    baseline = _panel_fingerprint(main, sequence, {})
    assert off == baseline
