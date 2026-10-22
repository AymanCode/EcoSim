"""Wellbeing reads liquid wealth (cash + bank deposits) for poverty and wealth loss.

Before this fix, ``Economy._batch_update_wellbeing`` read ``cash_balance``
only. The weekly deposit sweep therefore counted as a wealth loss, and a
household with savings in the bank counted as poor (PR7 investigation,
item 3). These tests compare two households whose only difference is how
the same money is split between cash and deposits.
"""

import pytest

from agents import GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def _household(hid, *, cash, deposit, cash_start, deposit_start):
    hh = HouseholdAgent(household_id=hid, skills_level=0.6, age=35, cash_balance=cash)
    hh.bank_deposit = deposit
    hh.last_tick_cash_start = cash_start
    hh.last_tick_deposit_start = deposit_start
    hh.happiness = 0.6
    hh.happiness_decay_rate = 0.0
    hh.met_housing_need = True
    hh.employer_id = 1
    hh.wage = hh.expected_wage
    hh.food_consumed_this_tick = hh.min_food_per_tick
    hh.services_consumed_this_tick = 1.0
    return hh


def _wellbeing(*households):
    economy = Economy(households=list(households), firms=[], government=GovernmentAgent(cash_balance=5_000.0))
    economy._batch_update_wellbeing(happiness_multiplier=1.0)


def test_depositing_cash_is_not_a_wealth_loss():
    kept = _household(1, cash=800.0, deposit=0.0, cash_start=800.0, deposit_start=0.0)
    swept = _household(2, cash=500.0, deposit=300.0, cash_start=800.0, deposit_start=0.0)
    _wellbeing(kept, swept)
    assert swept.happiness == pytest.approx(kept.happiness)


def test_withdrawing_is_not_a_gain_or_loss_and_real_spending_still_counts():
    steady = _household(1, cash=800.0, deposit=0.0, cash_start=800.0, deposit_start=0.0)
    withdrew = _household(2, cash=800.0, deposit=0.0, cash_start=500.0, deposit_start=300.0)
    spent = _household(3, cash=500.0, deposit=0.0, cash_start=800.0, deposit_start=0.0)
    _wellbeing(steady, withdrew, spent)
    assert withdrew.happiness == pytest.approx(steady.happiness)
    assert spent.happiness < steady.happiness


def test_savings_in_the_bank_are_not_poverty():
    threshold = CONFIG.households.poverty_threshold
    cash_only = _household(1, cash=threshold + 50.0, deposit=0.0,
                           cash_start=threshold + 50.0, deposit_start=0.0)
    banked = _household(2, cash=threshold * 0.5, deposit=threshold * 0.5 + 50.0,
                        cash_start=threshold * 0.5, deposit_start=threshold * 0.5 + 50.0)
    poor = _household(3, cash=threshold * 0.5, deposit=0.0,
                      cash_start=threshold * 0.5, deposit_start=0.0)
    _wellbeing(cash_only, banked, poor)
    assert banked.happiness == pytest.approx(cash_only.happiness)
    assert poor.happiness < cash_only.happiness


def test_snapshot_at_income_settlement_makes_the_deposit_sweep_neutral():
    """Real phase order: income settlement -> deposit sweep -> wellbeing.

    The saver starts the week with stale ``last_tick_*_start`` values from an
    earlier week (deposits were higher then). Only the snapshot taken in
    ``_apply_household_income`` resets them; without it the saver reads a
    wealth loss. The comparator holds the same liquid wealth all in cash, has
    no deposits and does not sweep.
    """
    from agents import BankAgent

    saver = _household(1, cash=2_000.0, deposit=500.0, cash_start=2_000.0, deposit_start=5_000.0)
    saver.deposit_buffer_weeks = 1.0
    saver.deposit_fraction = 0.5
    cash_only = _household(2, cash=2_500.0, deposit=0.0, cash_start=2_500.0, deposit_start=0.0)
    cash_only.deposit_fraction = 0.0
    economy = Economy(households=[saver, cash_only], firms=[],
                      government=GovernmentAgent(cash_balance=5_000.0),
                      bank=BankAgent(cash_reserves=10_000.0))

    economy._apply_household_income({}, {})
    deposit_before_sweep = saver.bank_deposit
    economy._process_bank_deposits()
    assert saver.bank_deposit > deposit_before_sweep  # the sweep fired
    economy._batch_update_wellbeing(happiness_multiplier=1.0)

    assert saver.happiness == pytest.approx(cash_only.happiness)
