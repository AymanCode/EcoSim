"""Isolated illness, recovery, and care checks on the income-first sequence."""

import math
import random
from dataclasses import replace

import numpy as np
import pytest

from agents import HouseholdAgent
from config import HouseholdBehaviorConfig, SimulationConfig, use_config
from economy import Economy, _TickScratch
from household_health import health_condition_step, health_recovery_step
from payment_sectors import settle_payment_care
from tests_contracts.factories import make_firm, make_government, make_household
from tools.benchmarks.panel_money import total_money_net_of_injections


@pytest.fixture
def cfg():
    config = SimulationConfig(
        payment_sequence="income_first",
        households=HouseholdBehaviorConfig(health_episodes=True),
    )
    with use_config(config):
        yield config


def build(patient, *, clinic=False, shocks=False):
    households = [patient]
    firms = []
    if clinic:
        doctor = make_household(
            household_id=2, medical_training_status="doctor", employer_id=8, wage=40.0,
            next_healthcare_request_tick=999,
        )
        households.append(doctor)
        firms.append(make_firm(firm_id=8, category="Healthcare", price=25.0, employees=[2]))
    economy = Economy(households, firms, make_government())
    if not shocks:
        economy._apply_random_shocks = lambda: None
    return economy


def set_conditions(patient, *, food_short, unhoused):
    patient.min_food_per_tick = 2.0
    patient.food_consumed_this_tick = 2.0 * (1.0 - food_short)
    patient.met_housing_need = not unhoused


def open_week(economy):
    economy._phase_reset_and_shocks(_TickScratch(payment_arm=True))


def weeks_to_work(floor, rate):
    health = 0.0
    for week in range(1, 53):
        health = health_recovery_step(health, floor, rate)
        if health >= 0.10:
            return week
    return None


def accepted_boundary_floor():
    # Binary search down to adjacent representable floats.
    lo, hi = 0.10, 0.15
    while math.nextafter(lo, math.inf) < hi:
        mid = (lo + hi) / 2.0
        if weeks_to_work(mid, 0.05) is None:
            lo = mid
        else:
            hi = mid
    return hi


def test_default_is_off():
    # The large flag-off comparison is in health_episodes_identity_check.py.
    assert SimulationConfig(payment_sequence="income_first").households.health_episodes is False


INVALID_SETTINGS = [
    {"health_recovery_floor": 0.10},
    {"health_recovery_floor": 0.41},
    {"health_self_recovery_ceiling": 1.01},
    {"health_self_recovery_rate": 0.0},
    {"health_self_recovery_rate": 1.01},
    {"health_illness_condition_boost": float("inf")},
    {"health_illness_condition_boost": -0.01},
    {"health_condition_rate": float("nan")},
    {"health_condition_rate": -0.01},
    {"health_food_shortfall_weight": 1.01},
    {"health_unhoused_weight": -0.01},
    {"health_illness_base_rate": 1.01},
    {"health_illness_severity_min": -0.01},
    {"health_illness_severity_max": 1.01},
    {"health_illness_severity_min": 0.4},
    {"health_recovery_floor": 0.10000000000000002, "health_self_recovery_rate": 0.05},
    {"health_recovery_floor": 0.125, "health_self_recovery_rate": 0.03047665879890139},
    {"health_recovery_floor": 0.11, "health_self_recovery_rate": 0.045066305381622665},
    {"health_recovery_floor": math.nextafter(accepted_boundary_floor(), -math.inf)},
    {"doctor_health_lock_value": 0.05},
]


@pytest.mark.parametrize("settings", INVALID_SETTINGS)
def test_rejects_at_config_creation_and_after_override(cfg, settings):
    with pytest.raises(ValueError, match="health"):
        replace(cfg, households=replace(cfg.households, **settings))
    for field, value in settings.items():
        setattr(cfg.households, field, value)
    with pytest.raises(ValueError, match="health"):
        build(make_household())


def test_accepts_doctor_lock_at_work_threshold(cfg):
    cfg.households = replace(cfg.households, doctor_health_lock_value=0.10)
    replace(cfg)
    doctor = make_household(medical_training_status="doctor")
    economy = build(doctor)
    open_week(economy)
    assert doctor.health == 0.10
    assert doctor.can_work


def test_scalar_steps_clamp_and_are_monotone():
    floor = 0.10000000000000003
    assert health_condition_step(0.9999999999999999, floor, 1.0) == floor
    assert health_recovery_step(0.005925, 0.15, 1.0) == 0.15

    rng = random.Random(42)
    for _ in range(100_000):
        low, high = sorted((rng.random(), rng.random()))
        rate = rng.random()
        rising = health_recovery_step(low, high, rate)
        falling = health_condition_step(high, low, rate)
        assert low <= rising <= high
        assert low <= falling <= high
        higher_health = rng.uniform(low, high)
        assert rising <= health_recovery_step(higher_health, high, rate)
        assert falling <= health_condition_step(rng.uniform(high, 1.0), low, rate)
        assert rising <= health_recovery_step(low, rng.uniform(high, 1.0), rate)
        assert falling <= health_condition_step(high, higher_health, rate)


@pytest.mark.parametrize("targets", [False, True])
def test_fed_and_sheltered_health_holds_at_or_above_ceiling(cfg, targets):
    cfg.households.wellbeing_targets = targets
    households = [make_household(household_id=i, health=health)
                  for i, health in enumerate((0.40, 0.8))]
    economy = Economy(households, [], make_government())
    initial_money = total_money_net_of_injections(economy)
    for patient in households:
        set_conditions(patient, food_short=0.0, unhoused=False)
        assert patient.renting_from_firm_id is None
    for _ in range(52):
        economy._batch_update_wellbeing(1.0)
        economy._apply_health_conditions_weekly()
        assert [patient.health for patient in households] == [0.40, 0.8]
        assert total_money_net_of_injections(economy) == initial_money


@pytest.mark.parametrize(("food_short", "unhoused", "target"), [
    (0.5, False, 0.75), (0.0, True, 0.90), (1.0, True, 0.40),
])
def test_conditions_pull_down_toward_target(cfg, food_short, unhoused, target):
    patient = make_household(health=1.0)
    set_conditions(patient, food_short=food_short, unhoused=unhoused)
    economy = build(patient)
    for _ in range(22):
        previous = patient.health
        economy._apply_health_conditions_weekly()
        assert patient.health == health_condition_step(previous, target, 0.05)
        assert target <= patient.health < previous


@pytest.mark.parametrize(("food_short", "unhoused", "weight", "target"), [
    (0.0, False, 0.5, 0.40), (0.5, False, 0.5, 0.40),
    (0.0, True, 0.5, 0.40), (0.75, True, 1.0, 0.15),
])
def test_self_recovery_from_low_health(cfg, food_short, unhoused, weight, target):
    cfg.households.health_food_shortfall_weight = weight
    patient = make_household(health=0.05)
    set_conditions(patient, food_short=food_short, unhoused=unhoused)
    economy = build(patient)
    for _ in range(22):
        previous = patient.health
        economy._apply_health_conditions_weekly()
        assert patient.health == health_recovery_step(previous, target, 0.05)
        assert previous < patient.health <= target
    assert patient.can_work


@pytest.mark.parametrize(("deprived", "weight", "floor", "rate", "limit"), [
    (False, 0.5, 0.15, 0.05, 22),
    (True, 0.5, 0.15, 0.05, 22),
    (True, 1.0, 0.15, 0.05, 22),
    (True, 1.0, accepted_boundary_floor(), 0.05, 52),
    (True, 1.0, 0.15, 1.0, 1),
])
def test_persistent_funding_denial(cfg, monkeypatch, deprived, weight, floor, rate, limit):
    cfg.households.health_food_shortfall_weight = weight
    cfg.households.health_unhoused_weight = weight
    cfg.households.health_recovery_floor = floor
    cfg.households.health_self_recovery_rate = rate
    cfg.households.health_illness_base_rate = 0.0
    cfg.time.warmup_ticks = 53  # No post-warmup cash transfers in this fixture.
    assert weeks_to_work(floor, rate) == limit
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda *_args, **_kwargs: 0.0)
    patient = make_household(
        health=0.0, cash_balance=0.0, rent_arrears=75.0,
        healthcare_critical_threshold=1.0,
    )
    set_conditions(patient, food_short=float(deprived), unhoused=deprived)
    economy = build(patient, clinic=True)
    # Patient-pay care with no bank denies the medical quote on every retry.
    target = max(floor, min(0.4, 1.0 - 2.0 * weight * deprived))
    for week in range(1, limit + 1):
        assert not patient.can_work
        economy.current_tick = week - 1
        open_week(economy)
        assert economy.health_illnesses_this_tick == 0
        settle_payment_care(economy, economy.payment_book.receipts)
        assert economy.payment_care_funding_denials_this_tick == 1, f"week {week}"
        assert economy.healthcare_completed_visits_this_tick == 0
        assert patient.payment_care_due_retry
        assert patient.payment_care_episode_id == 1
        assert patient.cash_balance == 0.0
        assert patient.rent_arrears == 75.0
        previous = patient.health
        economy._apply_health_conditions_weekly()
        assert patient.health == health_recovery_step(previous, target, rate)
        if patient.can_work:
            break
    assert patient.can_work
    if deprived and weight == 1.0:
        assert week == limit


def test_illness_and_multi_visit_trace(cfg, monkeypatch):
    hc = cfg.households
    hc.health_illness_base_rate = 1.0
    hc.health_illness_severity_min = hc.health_illness_severity_max = 0.2
    hc.healthcare_followup_gap_max_ticks = 1
    monkeypatch.setattr(HouseholdAgent, "_mixed_unit_random",
                        lambda _self, tick, salt: 0.0 if tick in (0, 1) else 1.0)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda *_args, **_kwargs: 0.0)
    patient = make_household(health=0.8)
    set_conditions(patient, food_short=0.0, unhoused=False)
    economy = build(patient, clinic=True)
    stored_heal = None  # set at tick 0, checked from tick 1
    for tick in range(4):
        economy.current_tick = tick
        if tick == 1:
            # Opening a second illness while the first visit is still waiting.
            assert patient.pending_healthcare_visits == 3
            assert patient.pending_visit_heal_delta == stored_heal
        initial_health = patient.health
        open_week(economy)
        assert economy.health_illnesses_this_tick == int(tick < 2)
        assert patient.payment_care_episode_id == 1
        assert patient.pending_healthcare_visits == (3 if tick == 0 else 4 - tick)
        # The separate diagnostics branch exposes these counts after integration.
        if hasattr(economy, "care_episodes_opened_this_tick"):
            assert economy.care_episodes_opened_this_tick == int(tick == 0)
            assert economy.care_visits_scheduled_this_tick == (3 if tick == 0 else 0)
        if tick == 0:
            assert patient.health == 0.8 - 0.2
            stored_heal = (1.0 - patient.health) / 3
            assert patient.pending_visit_heal_delta == stored_heal
            # One opening admission, then one visit on each following tick.
            assert economy.healthcare_requests_this_tick == 1
            continue
        expected_before = initial_health - 0.2 if tick == 1 else initial_health
        assert patient.health == expected_before
        assert patient.pending_visit_heal_delta == (stored_heal if tick == 1 else 0.0)
        heal = stored_heal if tick == 1 else 0.18 * (1.0 - patient.health)
        settle_payment_care(economy, economy.payment_book.receipts)
        assert patient.health == expected_before + heal
        assert patient.pending_visit_heal_delta == 0.0
        assert economy.healthcare_completed_visits_this_tick == 1
        if hasattr(economy, "care_visits_completed_this_tick"):
            assert economy.care_visits_completed_this_tick == 1
        assert patient.pending_healthcare_visits == 3 - tick
        economy._apply_health_conditions_weekly()
        assert patient.health == expected_before + heal


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("shocks", [False, True])
def test_doctor_lock_and_external_shocks(cfg, monkeypatch, locked, shocks):
    cfg.households.doctor_health_lock_enabled = locked
    cfg.households.health_illness_base_rate = 1.0
    cfg.households.health_illness_severity_min = cfg.households.health_illness_severity_max = 0.2
    if shocks:
        cfg.time.warmup_ticks = 0

        class HealthShockDraws:
            draws = iter((1.0, 1.0, 0.0))

            def random(self):
                return next(self.draws)

            def uniform(self, a, b):
                return a

            def sample(self, population, k):
                return population[:k]

    monkeypatch.setattr(HouseholdAgent, "_mixed_unit_random", lambda *_: 0.0)
    doctor = make_household(health=0.8, medical_training_status="doctor")
    set_conditions(doctor, food_short=1.0, unhoused=True)
    economy = build(doctor, shocks=shocks)
    if shocks:
        monkeypatch.setattr("economy.random.Random", lambda _seed: HealthShockDraws())
    open_week(economy)
    assert economy.health_illnesses_this_tick == int(not locked)
    assert doctor.health == (1.0 if locked else (0.8 - (0.05 if shocks else 0.0)) - 0.2)
    prior = doctor.health
    economy._apply_health_conditions_weekly()
    if locked:
        assert doctor.health == 1.0
        doctor.health = 0.5  # Simulate a change before the existing closing lock.
        economy._apply_doctor_health_lock()
        assert doctor.health == 1.0
    else:
        target = 1.0 - 0.5 - 0.1
        assert doctor.health == health_condition_step(prior, target, 0.05)


def test_illness_uses_previous_observations_and_zero_mean_frailty(cfg, monkeypatch):
    cfg.households.health_illness_base_rate = 0.2
    cfg.households.health_illness_severity_min = cfg.households.health_illness_severity_max = 0.2
    monkeypatch.setattr(HouseholdAgent, "_mixed_unit_random", lambda *_: 0.45)
    patient = make_household(health=0.8, health_decay_per_year=0.0)
    set_conditions(patient, food_short=0.5, unhoused=True)
    economy = build(patient)
    open_week(economy)
    assert patient.health == 0.8  # Tick zero ignores initial food and shelter.
    assert economy.health_illnesses_this_tick == 0
    economy.current_tick += 1
    open_week(economy)
    assert patient.health == 0.8 - 0.2  # 0.2 * (1 + 0.5 + 1) == 0.5
    assert economy.health_illnesses_this_tick == 1
    economy.current_tick += 1
    set_conditions(patient, food_short=0.5, unhoused=False)
    assert patient.renting_from_firm_id is None
    open_week(economy)
    assert economy.health_illnesses_this_tick == 0


def test_frailty_uses_all_households_and_severity_uses_its_own_draw(cfg, monkeypatch):
    cfg.households.health_illness_base_rate = 0.4
    def draw(_self, tick, salt):
        if salt == 601:
            return (0.65, 0.5)[tick]
        return 0.75

    monkeypatch.setattr(HouseholdAgent, "_mixed_unit_random", draw)
    robust = make_household(household_id=1, health=0.8, health_decay_per_year=0.1)
    frail = make_household(household_id=2, health=0.8, health_decay_per_year=0.5)
    doctor = make_household(household_id=3, medical_training_status="doctor", health_decay_per_year=0.4)
    economy = Economy([robust, frail, doctor], [], make_government())
    starting_money = total_money_net_of_injections(economy)
    economy._apply_health_illnesses_weekly()
    # Mean decay including the doctor is 1/3, so 0.65 exceeds the frail
    # household's 0.60 probability. Without the doctor it would be about 0.67.
    assert economy.health_illnesses_this_tick == 0
    for household in economy.households:
        set_conditions(household, food_short=0.0, unhoused=False)
    economy.current_tick = 1
    economy._apply_health_illnesses_weekly()
    assert robust.health == 0.8
    assert frail.health == 0.8 - (0.10 + (0.30 - 0.10) * 0.75)
    assert economy.health_illnesses_this_tick == 1
    assert total_money_net_of_injections(economy) == starting_money


@pytest.mark.parametrize(("seed", "hid", "tick", "salt", "numerator"), [
    (42, 0, 0, 601, 4656611711015616),
    (42, 0, 0, 602, 8671514245056567),
    (43, 999, 311, 601, 5146932487509730),
])
def test_fixed_draws(cfg, seed, hid, tick, salt, numerator):
    cfg.random_seed = seed
    patient = make_household(household_id=hid)
    assert patient._mixed_unit_random(tick, salt) == numerator / (1 << 53)
    assert patient._mixed_unit_random(tick, salt) == numerator / (1 << 53)


def test_draw_independence_and_rng_state(cfg):
    households = [make_household(household_id=i) for i in range(50)]
    old_random = random.getstate()
    old_numpy = np.random.get_state()

    def draws(seed, salt):
        cfg.random_seed = seed
        return [h._mixed_unit_random(tick, salt) for tick in range(200) for h in households]

    occurrence = draws(42, 601)
    for series in (draws(42, 602), draws(43, 601)):
        assert abs(np.corrcoef(occurrence, series)[0, 1]) < 0.05
    assert random.getstate() == old_random
    new_numpy = np.random.get_state()
    np.testing.assert_array_equal(new_numpy[1], old_numpy[1])
    assert (new_numpy[0], new_numpy[2:]) == (old_numpy[0], old_numpy[2:])


def test_weekly_trace_matches_performance_mode(cfg, monkeypatch):
    cfg.households.health_illness_base_rate = 1.0
    cfg.households.health_illness_severity_min = cfg.households.health_illness_severity_max = 0.2

    monkeypatch.setattr(HouseholdAgent, "_mixed_unit_random",
                        lambda _self, tick, salt: 0.0 if tick in (0, 9) else 1.0)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda *_args, **_kwargs: 0.0)

    def trace(performance_mode):
        patient = make_household(health=0.8, next_healthcare_request_tick=5)
        economy = build(patient, clinic=True)
        economy.performance_mode = performance_mode

        # Exercise the normal opening and wellbeing call sites, with a controlled
        # week of care and a controlled change in observed shelter.
        def care(_tick):
            if economy.current_tick == 5:
                settle_payment_care(economy, economy.payment_book.receipts)

        def consume(_tick):
            set_conditions(patient, food_short=0.5, unhoused=economy.current_tick >= 6)

        for name in dir(economy):
            if name.startswith("_phase_") and name != "_phase_reset_and_shocks":
                monkeypatch.setattr(economy, name, lambda _tick: None)
        economy._phase_misc_and_healthcare = care
        economy._phase_household_and_fiscal_settlement = consume

        observations = []
        for _ in range(11):
            economy.step()
            observations.append((patient.health, economy.health_illnesses_this_tick,
                                 economy.healthcare_completed_visits_this_tick))
        return observations

    normal = trace(False)
    assert trace(True) == normal
    assert normal[0] == (0.8 - 0.2, 1, 0)
    assert normal[5][2] == 1
    assert normal[5][0] > normal[4][0]
    assert normal[6][0] < normal[5][0]
    assert normal[9][1] == 1
    assert normal[10][1] == 0
