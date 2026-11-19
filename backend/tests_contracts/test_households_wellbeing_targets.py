"""Isolated contracts for opt-in wellbeing targets and payment snapshots."""

import copy
import dataclasses
import hashlib
import json

import pytest

from agents import HouseholdAgent
from config import clone_config, use_config
from economy import _TickScratch
from payments import PaymentBook
from tests_contracts.factories import patch_agent_method


def _world(factory, **overrides):
    values = dict(
        household_id=1, happiness=0.7, morale=0.6, health=0.8,
        health_decay_rate=0.01, employer_id=1, wage=40.0, expected_wage=40.0,
        cash_balance=1300.0, bank_deposit=0.0, min_food_per_tick=5.0,
        food_consumed_this_tick=5.0, met_housing_need=True,
        renting_from_firm_id=2, monthly_rent=50.0,
    )
    values.update(overrides)
    hh = factory.household(**values)
    hh.last_tick_cash_start = hh.cash_balance
    hh.last_tick_deposit_start = hh.bank_deposit
    firms = [factory.firm(firm_id=1, category="Food", price=10.0),
             factory.firm(firm_id=2, category="Housing", price=50.0)]
    return factory.economy(households=[hh], firms=firms), hh


def test_flags_are_off_by_default_and_initialization_keeps_original_traits(factory):
    cfg = clone_config()
    cfg.random_seed = 42
    assert cfg.households.wellbeing_targets is False
    assert cfg.households.fix_wellbeing_cash_snapshot is False
    with use_config(cfg):
        hh = HouseholdAgent(household_id=37, skills_level=0.6, age=35, cash_balance=400.0)
        assert hh.happiness_set_point == hh.happiness
        assert hh.morale_set_point == hh.morale
        # Whole original dataclass state, including all traits sampled before and
        # after happiness and morale; recorded at the unmodified base commit.
        state = dataclasses.asdict(hh)
        state.pop("happiness_set_point")
        state.pop("morale_set_point")
        # Fields added by other household experiments (money lines, dividend
        # timing); they are bookkeeping with zero defaults, not sampled traits.
        state.pop("essential_weekly_cost", None)
        state.pop("dividends_since_last_plan", None)
        digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert digest == "9eb64ffe0600c962be54e1727c0e2034a6c1c79a0e43edd31c6c6e463b57d637"
        supplied = factory.household(happiness=0.31, morale=0.42)
        assert supplied.happiness_set_point == 0.31
        assert supplied.morale_set_point == 0.42
        explicit = factory.household(happiness=0.31, morale=0.42,
                                     happiness_set_point=0.81, morale_set_point=0.72)
        assert explicit.happiness_set_point == 0.81
        assert explicit.morale_set_point == 0.72


@pytest.mark.parametrize(
    "overrides,multiplier,target",
    [
        ({}, 1.0, 0.7),
        ({"employer_id": None}, 1.0, 0.6),
        ({"cash_balance": 0.0}, 1.0, 0.58),
        ({"cash_balance": 0.0, "bank_deposit": 650.0}, 1.0, 0.64),
        ({"food_consumed_this_tick": 2.5}, 1.0, 0.625),
        ({"food_consumed_this_tick": 0.0}, 1.0, 0.55),
        ({"met_housing_need": False}, 1.0, 0.6),
        ({}, 1.10, 0.75),
        ({}, 0.90, 0.65),
    ],
)
def test_happiness_components_are_levels(factory, overrides, multiplier, target):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        e, hh = _world(factory, **overrides)
        e._batch_update_wellbeing(multiplier)
        assert hh.happiness == pytest.approx(0.7 + 0.05 * (target - 0.7))


def test_security_uses_current_food_and_household_rent(factory):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        e, hh = _world(factory, cash_balance=1300.0, monthly_rent=150.0)
        # 5*10 + 150 = 200 per week; 1,300 covers half of 13 weeks.
        e._batch_update_wellbeing(1.0)
        assert hh.happiness == pytest.approx(0.7 - 0.05 * 0.12 * 0.5)
        hh.happiness = 0.7
        hh.renting_from_firm_id = None  # reference rent is 50, not the old contract
        e._batch_update_wellbeing(1.0)
        assert hh.happiness == pytest.approx(0.7)
        hh.happiness = 0.7
        e.firms[0].price = 30.0  # 5*30 + 50 = 200
        e._batch_update_wellbeing(1.0)
        assert hh.happiness == pytest.approx(0.7 - 0.05 * 0.12 * 0.5)


@pytest.mark.parametrize(
    "overrides,target",
    [
        ({}, 0.75),
        ({"wage": 60.0}, 0.75),
        ({"wage": 20.0}, 0.45),
        ({"wage": 0.0}, 0.30),
        ({"employer_id": None, "wage": 0.0}, 0.45),
        ({"met_housing_need": False}, 0.70),
    ],
)
def test_morale_targets_fair_pay_underpay_unemployment_and_housing(factory, overrides, target):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        e, hh = _world(factory, **overrides)
        e._batch_update_wellbeing(1.0)
        assert hh.morale == pytest.approx(0.6 + 0.10 * (target - 0.6))


def test_poor_unemployed_household_converges_to_interior_levels(factory):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        e, hh = _world(factory, cash_balance=0.0, employer_id=None, wage=0.0)
        for _ in range(200):
            e._batch_update_wellbeing(1.0)
        assert hh.happiness == pytest.approx(0.48 + (0.7 - 0.48) * 0.95 ** 200)
        assert hh.morale == pytest.approx(0.45 + (0.6 - 0.45) * 0.90 ** 200)
        assert 0.0 < hh.happiness < 1.0
        assert 0.0 < hh.morale < 1.0


@pytest.mark.parametrize("high", [False, True])
def test_targets_are_clipped_before_adjustment(factory, high):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        if high:
            e, hh = _world(factory, happiness_set_point=0.95, morale_set_point=0.95)
            multiplier, target = 2.0, 1.0
        else:
            e, hh = _world(factory, happiness_set_point=0.05, morale_set_point=0.05,
                           employer_id=None, cash_balance=0.0, met_housing_need=False,
                           food_consumed_this_tick=0.0)
            multiplier, target = 1.0, 0.0
        e._batch_update_wellbeing(multiplier)
        assert hh.happiness == pytest.approx(0.7 + 0.05 * (target - 0.7))
        assert hh.morale == pytest.approx(0.6 + 0.10 * (target - 0.6))


def test_transfer_between_cash_and_deposits_is_not_a_wealth_loss(factory):
    cfg = clone_config()
    cfg.households.wellbeing_targets = True
    with use_config(cfg):
        e, hh = _world(factory, cash_balance=500.0, bank_deposit=800.0)
        hh.last_tick_cash_start = 1000.0
        hh.last_tick_deposit_start = 300.0
        e._batch_update_wellbeing(1.0)
        assert hh.happiness == pytest.approx(0.7)


@pytest.mark.parametrize("food", [0.0, 2.5, 5.0, 8.0])
def test_targets_do_not_change_health_update(factory, food):
    cfg = clone_config()
    with use_config(cfg):
        e, hh = _world(factory, food_consumed_this_tick=food)
        comparison = copy.deepcopy(hh)
        e.households.append(comparison)
        e._batch_update_wellbeing(1.0)
        health_off = hh.health
        hh.health = comparison.health = 0.8
        cfg.households.wellbeing_targets = True
        e._batch_update_wellbeing(1.0)
        assert hh.health == pytest.approx(health_off)
        assert comparison.health == pytest.approx(health_off)


@pytest.mark.parametrize("timing", ["income_first", "income_late"])
@pytest.mark.parametrize("targets", [False, True])
@pytest.mark.parametrize("fix", [False, True])
def test_payment_snapshot_precedes_wages_and_records_real_wealth_loss(factory, monkeypatch, timing, targets, fix):
    cfg = clone_config()
    cfg.payment_sequence = timing
    cfg.households.wellbeing_targets = targets
    cfg.households.fix_wellbeing_cash_snapshot = fix
    with use_config(cfg):
        e, hh = _world(factory, cash_balance=100.0, bank_deposit=200.0)
        hh.last_tick_cash_start = hh.last_tick_deposit_start = 0.0
        peer = factory.household(household_id=2, cash_balance=12.0, bank_deposit=88.0)
        e.households.append(peer)
        e.household_lookup[peer.household_id] = peer
        firm = e.firms[0]
        firm.employees = [hh.household_id]
        firm.actual_wages = {hh.household_id: 40.0}
        firm.cash_balance = 100.0
        firm.ceo_household_id = None
        patch_agent_method(monkeypatch, e.government, "plan_taxes", lambda *_: {"wage_taxes": {}})
        e.payment_book = PaymentBook(e, timing)
        monkeypatch.setattr(e, "_plan_payment_consumption", lambda *_args, **_kwargs: None)
        original = PaymentBook.settle_income
        observed = []

        def observe(book, wages):
            observed.append((hh.cash_balance, hh.bank_deposit,
                             hh.last_tick_cash_start, hh.last_tick_deposit_start,
                             peer.last_tick_cash_start, peer.last_tick_deposit_start))
            return original(book, wages)

        monkeypatch.setattr(PaymentBook, "settle_income", observe)
        tick = _TickScratch(payment_arm=True, frozen_wages={1: 40.0},
                            household_consumption_plans={1: {"planned_purchases": {}},
                                                         2: {"planned_purchases": {}}})
        e._phase_goods_clearing(tick)
        assert observed == [(100.0, 200.0, 100.0 if fix else 0.0, 200.0 if fix else 0.0,
                             12.0 if fix else 0.0, 88.0 if fix else 0.0)]
        assert hh.cash_balance == pytest.approx(140.0 if timing == "income_first" else 100.0)
        e.payment_book.release_late_income()
        hh.cash_balance -= 90.0  # Real spending: liquid wealth falls from 300 to 250.
        e._batch_update_wellbeing(1.0)
        with_loss = hh.happiness
        hh.happiness = 0.7
        hh.last_tick_cash_start = hh.last_tick_deposit_start = 0.0
        e._batch_update_wellbeing(1.0)
        assert hh.happiness - with_loss == pytest.approx(
            cfg.households.wealth_loss_happiness_scaling * 50.0 / 300.0 if fix else 0.0
        )


@pytest.mark.parametrize("fix", [False, True])
def test_snapshot_flag_does_not_change_legacy_income(factory, fix):
    cfg = clone_config()
    cfg.payment_sequence = "legacy"
    cfg.households.fix_wellbeing_cash_snapshot = fix
    with use_config(cfg):
        e, hh = _world(factory, cash_balance=100.0, bank_deposit=200.0)
        hh.last_tick_cash_start = hh.last_tick_deposit_start = 0.0
        e._apply_household_income({}, {})
        assert hh.last_tick_cash_start == 100.0
        assert hh.last_tick_deposit_start == 200.0
        assert hh.cash_balance == 140.0
