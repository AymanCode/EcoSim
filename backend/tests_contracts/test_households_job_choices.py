"""Isolated contracts for optional household job choices and tenure layoffs."""

from types import SimpleNamespace

import pytest

from config import HouseholdBehaviorConfig, SimulationConfig, clone_config, use_config
from payment_payroll import enforce_private_payroll
from tests_contracts.factories import patch_agent_method


@pytest.fixture(autouse=True)
def _income_first_sequence():
    """Every test runs on income_first; legacy is not tested here."""
    config = clone_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        yield


def _plan(worker, *, switching=False, reservation=0.0):
    return {
        "skills_level": worker.skills_level,
        "reservation_wage": reservation,
        "searching_for_job": True,
        "job_switching": switching,
        "medical_only": False,
    }


def _production(hires=0, layoffs=()):
    return {"planned_hires_count": hires, "planned_layoffs_ids": list(layoffs)}


def test_setting_defaults_on_and_requires_a_boolean():
    assert HouseholdBehaviorConfig().job_choices is True
    with pytest.raises(ValueError, match="households.job_choices"):
        SimulationConfig(households=HouseholdBehaviorConfig(job_choices=1))


@pytest.mark.parametrize("matcher", ["_match_labor_fast", "_match_labor"])
@pytest.mark.parametrize("offers,expected", [({1: 40.0, 2: 60.0}, 2), ({1: 60.0, 2: 60.0}, 1)])
def test_best_base_offer_then_firm_id(factory, matcher, offers, expected):
    cfg = clone_config()
    cfg.households.job_choices = True
    with use_config(cfg):
        worker = factory.household(household_id=1, skills_level=0.5)
        firms = [factory.firm(firm_id=fid) for fid in (1, 2)]
        economy = factory.economy(households=[worker], firms=firms)
        production = {fid: _production(hires=1) for fid in offers}
        wages = {fid: {"wage_offer_next": offer} for fid, offer in offers.items()}
        firm_out, household_out = getattr(economy, matcher)(production, wages, {1: _plan(worker)})
        assert household_out[1]["employer_id"] == expected
        assert firm_out[expected]["hired_households_ids"] == [1]


def test_synthetic_vacancies_are_visited_by_offer(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    cfg.labor_market.fix_switcher_vacancies = True
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=40.0,
                                   skills_level=0.5, job_switch_threshold=0.1)
        firms = [factory.firm(firm_id=1, employees=[1], actual_wages={1: 40.0}),
                 factory.firm(firm_id=2, is_baseline=False),
                 factory.firm(firm_id=3, is_baseline=False)]
        economy = factory.economy(households=[worker], firms=firms)
        production = {fid: _production() for fid in (1, 2, 3)}
        wages = {fid: {"wage_offer_next": offer} for fid, offer in ((1, 40.0), (2, 60.0), (3, 80.0))}
        firm_out, household_out = economy._match_labor_fast(production, wages, {1: _plan(worker, switching=True)})
        assert household_out[1]["employer_id"] == 3
        assert firm_out[3]["synthetic_switcher_vacancies"] == 1
        assert firm_out[2]["hired_households_ids"] == []


@pytest.mark.parametrize("offer,accepted", [(80.0, False), (99.0, False), (100.0, True), (110.0, True)])
def test_switcher_must_meet_threshold_with_actual_wage(factory, offer, accepted):
    cfg = clone_config()
    cfg.households.job_choices = True
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0,
                                   skills_level=0.8, job_switch_threshold=0.2,
                                   category_experience={})
        firms = [factory.firm(firm_id=1, employees=[1], actual_wages={1: 100.0}),
                 factory.firm(firm_id=2)]
        economy = factory.economy(households=[worker], firms=firms)
        production = {1: _production(), 2: _production(hires=1)}
        wages = {1: {"wage_offer_next": 40.0}, 2: {"wage_offer_next": offer}}
        firm_out, household_out = economy._match_labor_fast(production, wages, {1: _plan(worker, switching=True)})
        assert (household_out[1]["employer_id"] == 2) is accepted
        if accepted:
            assert household_out[1]["wage"] >= 120.0
            assert firm_out[1]["confirmed_layoffs_ids"] == [1]
        else:
            assert household_out[1]["employer_id"] == 1
            assert household_out[1]["wage"] == 100.0
            assert firm_out[2]["unfilled_vacancies"] == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_pay_cut_switch_is_blocked_only_when_enabled(factory, enabled):
    cfg = clone_config()
    cfg.households.job_choices = enabled
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=200.0,
                                   skills_level=0.5, job_switch_threshold=0.1)
        firms = [factory.firm(firm_id=1, employees=[1], actual_wages={1: 200.0}),
                 factory.firm(firm_id=2)]
        economy = factory.economy(households=[worker], firms=firms)
        _, household_out = economy._match_labor_fast(
            {1: _production(), 2: _production(hires=1)},
            {1: {"wage_offer_next": 40.0}, 2: {"wage_offer_next": 150.0}},
            {1: _plan(worker, switching=True)},
        )
        assert household_out[1]["employer_id"] == (1 if enabled else 2)
        assert household_out[1]["wage"] == pytest.approx(200.0 if enabled else 168.75)


def test_exact_threshold_survives_rounded_base_offer_division(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=39.82916880509813,
                                   skills_level=0.766107439994812,
                                   job_switch_threshold=0.062121550455737064,
                                   category_experience={"Food": 284})
        firms = [factory.firm(firm_id=1, employees=[1], actual_wages={1: worker.wage}),
                 factory.firm(firm_id=2)]
        economy = factory.economy(households=[worker], firms=firms)
        offer = 31.21164291491226
        _, household_out = economy._match_labor_fast(
            {1: _production(), 2: _production(hires=1)},
            {1: {"wage_offer_next": 40.0}, 2: {"wage_offer_next": offer}},
            {1: _plan(worker, switching=True)},
        )
        assert household_out[1]["employer_id"] == 2
        assert household_out[1]["wage"] == worker.wage * (1.0 + worker.job_switch_threshold)


def test_cross_category_guard_keeps_job_and_leaves_slot_open(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0,
                                   skills_level=0.5, job_switch_threshold=0.1,
                                   category_experience={"Food": 520})
        firms = [factory.firm(firm_id=1, category="Food", employees=[1], actual_wages={1: 100.0}),
                 factory.firm(firm_id=2, category="Services"),
                 factory.firm(firm_id=3, category="Food")]
        economy = factory.economy(households=[worker], firms=firms)
        production = {1: _production(), 2: _production(hires=1), 3: _production(hires=1)}
        wages = {1: {"wage_offer_next": 40.0}, 2: {"wage_offer_next": 85.0},
                 3: {"wage_offer_next": 84.0}}
        firm_out, household_out = economy._match_labor_fast(production, wages, {1: _plan(worker, switching=True)})
        # 85 clears the reservation based on Food experience, but 85 * 1.125
        # is below the current wage and the required 110 at Services. The
        # lower offer is not tried.
        assert household_out[1] == {"employer_id": 1, "wage": 100.0, "employer_category": "Food"}
        assert firm_out[2]["hired_households_ids"] == []
        assert firm_out[2]["unfilled_vacancies"] == 1
        assert firm_out[3]["hired_households_ids"] == []
        assert firm_out[1]["confirmed_layoffs_ids"] == []
        assert firms[0].worker_turnover_this_tick == 0


def test_rejected_switch_does_not_undo_a_planned_layoff(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    cfg.labor_market.fix_switcher_vacancies = False
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0,
                                   skills_level=0.5, job_switch_threshold=0.1,
                                   category_experience={"Food": 520})
        firms = [factory.firm(firm_id=1, employees=[1], actual_wages={1: 100.0}),
                 factory.firm(firm_id=2, category="Services")]
        economy = factory.economy(households=[worker], firms=firms)
        production = {1: _production(layoffs=[1]), 2: _production(hires=1)}
        wages = {1: {"wage_offer_next": 40.0}, 2: {"wage_offer_next": 90.0}}
        firm_out, household_out = economy._match_labor_fast(production, wages, {1: _plan(worker, switching=True)})
        assert household_out[1]["employer_id"] is None
        assert firm_out[1]["confirmed_layoffs_ids"] == [1]
        assert firm_out[2]["unfilled_vacancies"] == 1


def test_switcher_cannot_rehire_themself_at_their_own_firm(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    cfg.labor_market.fix_switcher_vacancies = False
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0,
                                   skills_level=0.5, job_switch_threshold=0.1)
        firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 100.0})
        economy = factory.economy(households=[worker], firms=[firm])
        firm_out, household_out = economy._match_labor_fast(
            {1: _production(hires=1)}, {1: {"wage_offer_next": 150.0}}, {1: _plan(worker, switching=True)}
        )
        assert household_out[1]["employer_id"] == 1
        assert household_out[1]["wage"] == 100.0
        assert firm_out[1]["hired_households_ids"] == []
        assert firm_out[1]["confirmed_layoffs_ids"] == []


@pytest.mark.parametrize("laid_off", [False, True])
def test_switcher_with_no_hiring_firms_keeps_only_an_existing_contract(factory, laid_off):
    cfg = clone_config()
    cfg.households.job_choices = True
    cfg.labor_market.fix_switcher_vacancies = False
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0)
        firm = factory.firm(firm_id=1, employees=[1], actual_wages={1: 100.0})
        economy = factory.economy(households=[worker], firms=[firm])
        production = {1: _production(layoffs=[1] if laid_off else [])}
        _, household_out = economy._match_labor_fast(
            production, {1: {"wage_offer_next": 40.0}}, {1: _plan(worker, switching=True)}
        )
        assert household_out[1]["employer_id"] == (None if laid_off else 1)
        assert household_out[1]["wage"] == (0.0 if laid_off else 100.0)


def test_lifo_layoff_order_uses_wage_then_household_id(factory):
    cfg = clone_config()
    # job_choices: compare the original roster order with the new LIFO order.
    cfg.households.job_choices = False
    firm = factory.firm(firm_id=1, employees=[1, 3, 2, 4],
                        actual_wages={1: 50.0, 2: 40.0, 3: 40.0, 4: 30.0},
                        employee_hire_ticks={1: 1, 2: 5, 3: 5, 4: 5})
    with use_config(cfg):
        assert firm._layoff_candidates(3) == [1, 3, 2]
        cfg.households.job_choices = True
        assert firm._layoff_candidates(4) == [4, 2, 3, 1]
        assert firm._layoff_candidates(2) == [4, 2]
        assert firm.employees == [1, 3, 2, 4]


@pytest.mark.parametrize("enabled,expected", [(False, [1, 2]), (True, [4, 3])])
def test_public_works_layoffs_use_the_selected_order(factory, enabled, expected):
    cfg = clone_config()
    cfg.households.job_choices = enabled
    with use_config(cfg):
        firm = factory.firm(firm_id=1, employees=[1, 2, 3, 4], max_fires_per_tick=2,
                            actual_wages={hid: 40.0 for hid in (1, 2, 3, 4)},
                            employee_hire_ticks={1: 1, 2: 2, 3: 3, 4: 4})
        firm.good_category = "PublicWorks"
        economy = factory.economy(firms=[firm])
        economy._deauthorize_public_works_capacity()
        assert firm.planned_layoffs_ids == expected


@pytest.mark.parametrize("enabled,expected", [(False, [1, 2, 3, 4, 5]), (True, [6, 5, 4, 3, 2])])
def test_housing_planner_applies_the_selected_layoff_order(factory, enabled, expected):
    cfg = clone_config()
    cfg.households.job_choices = enabled
    cfg.firms.min_skeleton_workers = 1
    cfg.firms.min_target_workers = 1
    with use_config(cfg):
        firm = factory.firm(firm_id=1, category="Housing", max_rental_units=1,
                            employees=[1, 2, 3, 4, 5, 6],
                            actual_wages={hid: 40.0 for hid in range(1, 7)},
                            employee_hire_ticks={hid: hid for hid in range(1, 7)})
        plan = firm.plan_production_and_labor(0.0, total_households=10)
        assert plan["planned_layoffs_ids"] == expected


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("enabled,expected", [(False, [2, 3]), (True, [1, 3])])
def test_payroll_cancels_hires_before_ordering_incumbent_layoffs(factory, timing, enabled, expected):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.job_choices = enabled
    cfg.firms.working_capital_enabled = False
    with use_config(cfg):
        workers = [factory.household(household_id=hid, employer_id=1, wage=100.0) for hid in (1, 2, 3, 4)]
        firm = factory.firm(firm_id=1, category="Food", is_baseline=False, cash_balance=200.0,
                            employees=[1, 2, 3, 4], actual_wages={hid: 100.0 for hid in (1, 2, 3, 4)},
                            employee_hire_ticks={1: 1, 2: 10, 3: 3, 4: 12})
        economy = factory.economy(households=workers, firms=[firm])
        economy.bank = None
        economy.current_tick = 12
        economy.payment_book = SimpleNamespace(funded_payroll_firms=set(), net_offer_diagnostics=[])
        outcome = {1: {"hired_households_ids": [4], "confirmed_layoffs_ids": [],
                       "actual_wages": {4: 100.0}, "unfilled_vacancies": 0}}
        household_out = {hid: {"employer_id": 1, "wage": 100.0} for hid in (1, 2, 3, 4)}
        enforce_private_payroll(economy, outcome, household_out)
        assert firm.employees == expected
        assert 4 not in firm.employee_hire_ticks
        assert set(firm.employee_hire_ticks) == set(expected)
        assert outcome[1]["hired_households_ids"] == []
        assert outcome[1]["confirmed_layoffs_ids"] == ([1] if not enabled else [2])


def test_hire_ticks_follow_hires_layoffs_and_roster_sync(factory):
    cfg = clone_config()
    cfg.households.job_choices = True
    with use_config(cfg):
        firm = factory.firm(firm_id=1, employees=[1, 2], actual_wages={1: 40.0, 2: 40.0},
                            employee_hire_ticks={1: 1, 2: 3})
        firm.apply_labor_outcome({"hired_households_ids": [3], "confirmed_layoffs_ids": [2],
                                  "actual_wages": {3: 50.0}}, current_tick=7)
        assert firm.employee_hire_ticks == {1: 1, 3: 7}
        workers = [factory.household(household_id=hid, employer_id=1, wage=50.0)
                   for hid in (1, 3, 4)]
        other = factory.firm(firm_id=2)
        economy = factory.economy(households=workers, firms=[firm, other])
        firm.employee_hire_ticks[99] = 0
        economy.current_tick = 10
        economy._sync_firm_employee_rosters()
        assert firm.employee_hire_ticks == {1: 1, 3: 7, 4: 10}
        workers[0].employer_id = 2
        economy.current_tick = 12
        economy._sync_firm_employee_rosters()
        assert firm.employee_hire_ticks == {3: 7, 4: 10}
        assert other.employee_hire_ticks == {1: 12}


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
def test_full_tick_records_switch_tenure_in_each_payment_sequence(factory, monkeypatch, timing):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.job_choices = True
    with use_config(cfg):
        worker = factory.household(household_id=1, employer_id=1, wage=100.0,
                                   skills_level=0.5, job_switch_threshold=0.1,
                                   medical_training_status="none")
        old = factory.firm(firm_id=1, employees=[1], actual_wages={1: 100.0},
                           employee_hire_ticks={1: 2})
        new = factory.firm(firm_id=2)
        economy = factory.economy(households=[worker], firms=[old, new])
        economy.current_tick = 7
        economy.warmup_ticks = 100
        economy.configure_stabilizers(households=False, firms=False, government=False)
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: 0)
        monkeypatch.setattr(economy, "_enqueue_healthcare_requests", lambda: None)
        for firm, hires, offer in ((old, 0, 40.0), (new, 1, 150.0)):
            patch_agent_method(monkeypatch, firm, "plan_production_and_labor",
                               lambda *args, firm=firm, hires=hires, **kwargs: firm._stamp_labor_plan(0.0, hires, []))
            patch_agent_method(monkeypatch, firm, "plan_wage",
                               lambda *args, offer=offer, **kwargs: {"wage_offer_next": offer})
            patch_agent_method(monkeypatch, firm, "plan_capital_investment", lambda *args, **kwargs: None)
        patch_agent_method(monkeypatch, worker, "plan_labor_supply",
                           lambda *args, **kwargs: _plan(worker, switching=True))
        economy.step()
        assert worker.employer_id == 2
        assert worker.wage >= 110.0
        assert old.employee_hire_ticks == {}
        assert new.employee_hire_ticks == {1: 7}
