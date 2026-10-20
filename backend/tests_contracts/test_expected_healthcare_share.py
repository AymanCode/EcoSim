"""Read-only estimate of the household's share of a healthcare visit price.

- ``GovernmentAgent.expected_healthcare_household_share`` prices one visit
  against an explicit subsidy budget (the legacy visit rule).
- ``Economy.expected_healthcare_household_shares`` walks the queues in
  service order, so several queued visits share one subsidy cap the way the
  charge in ``Economy._process_healthcare_services`` spends it.
- ``Economy.expected_healthcare_out_of_pocket_all`` turns that one walk into
  dollars for every queued household; ``expected_healthcare_out_of_pocket``
  reads the same map for one household.
- ``payment_sectors.payment_care_covered`` is the one coverage rule on the
  payment sequences.
"""

import math

import pytest

from config import CONFIG
from tests_contracts.factories import make_economy


def _economy(level: int = 0, budget: float = 1_000_000.0, cash: float = 1_000_000.0, households: int = 6):
    economy = make_economy(num_households=households, seed=11)
    gov = economy.government
    if level:
        gov.set_lever("sector_subsidy_target", "healthcare")
        gov.set_lever("sector_subsidy_level", level)
    gov.cash_balance = cash
    economy.sector_subsidy_cap_this_tick = budget
    economy.sector_subsidy_remaining_this_tick = budget
    return economy


def _queue(economy, price: float, n: int, cash: float = 1_000.0):
    """Queue the first n households at the single healthcare firm, with slots for all."""
    firms = economy._healthcare_firms()
    assert len(firms) == 1
    firm = firms[0]
    firm.price = price
    firm.healthcare_capacity_carryover = float(n)
    households = economy.households[:n]
    firm.healthcare_queue = [h.household_id for h in households]
    for household in households:
        household.queued_healthcare_firm_id = firm.firm_id
        household.cash_balance = cash
        household.medical_training_status = "none"
    return firm, households


def _charge(economy):
    economy._process_healthcare_services({})
    return {
        event["household_id"]: event["household_cost"] / event["visit_price"]
        for event in economy.last_healthcare_events
        if event["event_type"] == "visit_completed"
    }


# --- GovernmentAgent: one visit, explicit budget -------------------------------------------


def test_no_subsidy_means_the_household_pays_everything():
    assert CONFIG.government.healthcare_visit_subsidy_share == 0.0
    gov = _economy().government
    assert gov.expected_healthcare_household_share(80.0, subsidy_budget_left=1e6) == 1.0


def test_binding_cap_raises_the_share_with_the_price():
    gov = _economy(level=50).government
    assert gov.expected_healthcare_household_share(80.0, subsidy_budget_left=1e6) == pytest.approx(0.5)
    # The treasury pays at most $10, whatever the price.
    assert gov.expected_healthcare_household_share(100.0, subsidy_budget_left=10.0) == pytest.approx(0.9)
    assert gov.expected_healthcare_household_share(20.0, subsidy_budget_left=10.0) == pytest.approx(0.5)
    assert gov.expected_healthcare_household_share(40.0, subsidy_budget_left=10.0) == pytest.approx(0.75)


def test_budget_is_a_required_keyword():
    gov = _economy(level=50).government
    with pytest.raises(TypeError):
        gov.expected_healthcare_household_share(80.0)
    with pytest.raises(TypeError):
        gov.expected_healthcare_household_share(80.0, 10.0)


@pytest.mark.parametrize(
    "budget,expected",
    [(0.0, 1.0), (-5.0, 1.0), (math.inf, 0.5), (25.0, 0.75)],
)
def test_budget_bounds(budget, expected):
    gov = _economy(level=50).government
    assert gov.expected_healthcare_household_share(100.0, subsidy_budget_left=budget) == pytest.approx(expected)


def test_nan_budget_is_rejected():
    gov = _economy(level=50).government
    with pytest.raises(ValueError):
        gov.expected_healthcare_household_share(100.0, subsidy_budget_left=math.nan)


@pytest.mark.parametrize("price", [math.nan, math.inf, -math.inf, -10.0])
def test_bad_price_is_rejected(price):
    gov = _economy(level=50).government
    with pytest.raises(ValueError):
        gov.expected_healthcare_household_share(price, subsidy_budget_left=10.0)


@pytest.mark.parametrize("budget", [0.0, math.inf])
def test_price_zero_returns_the_uncapped_share(budget):
    gov = _economy(level=50).government
    assert gov.expected_healthcare_household_share(0.0, subsidy_budget_left=budget) == pytest.approx(0.5)


# --- Economy: queues walked in service order -----------------------------------------------


def test_three_visits_share_one_cap_like_the_charge():
    """$110 of subsidy budget, three $100 visits at 50%: two get $50 each and
    the third gets the $10 left. Each visit is quoted that, not 0.5 each."""
    economy = _economy(level=50, budget=110.0)
    _firm, households = _queue(economy, price=100.0, n=3)
    estimate = economy.expected_healthcare_household_shares()
    charged = _charge(economy)
    ids = [h.household_id for h in households]
    assert set(estimate) == set(ids) == set(charged)
    assert sorted(estimate.values()) == pytest.approx([0.5, 0.5, 0.9])
    for household_id in ids:
        assert estimate[household_id] == pytest.approx(charged[household_id])


def test_households_past_the_slots_are_quoted_against_what_is_left():
    """A household the charge will not reach this tick is quoted against the
    budget left after the visits that are served (the conservative choice)."""
    economy = _economy(level=50, budget=60.0)
    firm, households = _queue(economy, price=100.0, n=3)
    firm.healthcare_capacity_carryover = 1.0
    slots = int(math.floor(economy._healthcare_effective_capacity(firm) + 1.0 + 1e-9))
    assert 1 <= slots < 3, f"fixture needs 1-2 slots, got {slots}"
    estimate = economy.expected_healthcare_household_shares()
    economy._process_healthcare_services({})
    served = {e["household_id"]: e for e in economy.last_healthcare_events if e["event_type"] == "visit_completed"}
    assert len(served) == slots
    left = 60.0 - sum(e["government_cost"] for e in served.values())
    for household in households:
        if household.household_id in served:
            event = served[household.household_id]
            assert estimate[household.household_id] == pytest.approx(event["household_cost"] / 100.0)
        else:
            expected = economy.government.expected_healthcare_household_share(100.0, subsidy_budget_left=left)
            assert estimate[household.household_id] == pytest.approx(expected)


def test_the_walk_changes_nothing():
    economy = _economy(level=50, budget=110.0)
    firm, _households = _queue(economy, price=100.0, n=3)
    economy.current_tick = 7
    gov = economy.government

    def snapshot():
        return (
            list(firm.healthcare_queue), firm.healthcare_capacity_carryover,
            economy.sector_subsidy_remaining_this_tick, gov.cash_balance,
            economy.last_tick_gov_subsidy_requested, economy.last_tick_gov_subsidies,
            economy.last_tick_gov_subsidy_denied_by_cap, economy.healthcare_attempted_slots_this_tick,
        )

    before = snapshot()
    for _ in range(3):
        economy.expected_healthcare_household_shares()
        economy.expected_healthcare_out_of_pocket_all()
        for household in economy.households:
            economy.expected_healthcare_out_of_pocket(household.household_id)
    assert snapshot() == before


def test_empty_queues_give_an_empty_map():
    economy = _economy(level=50)
    for firm in economy._healthcare_firms():
        firm.healthcare_queue = []
    assert economy.expected_healthcare_household_shares() == {}


@pytest.mark.parametrize("price", [math.nan, math.inf])
def test_bad_provider_price_is_rejected(price):
    economy = _economy(level=50)
    _queue(economy, price=price, n=1)
    with pytest.raises(ValueError):
        economy.expected_healthcare_household_shares()


def test_negative_provider_price_reads_as_free_like_the_charge():
    economy = _economy(level=50)
    _firm, households = _queue(economy, price=-5.0, n=1)
    assert economy.expected_healthcare_household_shares()[households[0].household_id] == pytest.approx(0.5)
    assert economy.expected_healthcare_out_of_pocket(households[0].household_id) == 0.0


def test_empty_treasury_means_no_subsidy():
    economy = _economy(level=50, cash=0.0)
    _firm, households = _queue(economy, price=80.0, n=2)
    assert set(economy.expected_healthcare_household_shares().values()) == {1.0}


# --- Economy: dollars for one household ----------------------------------------------------


def test_out_of_pocket_is_price_times_the_walked_share():
    economy = _economy(level=50, budget=110.0)
    _firm, households = _queue(economy, price=100.0, n=3)
    shares = economy.expected_healthcare_household_shares()
    for household in households:
        assert economy.expected_healthcare_out_of_pocket(household.household_id) == pytest.approx(
            100.0 * shares[household.household_id]
        )


def test_out_of_pocket_all_is_one_walk_and_matches_the_single_getter():
    economy = _economy(level=50, budget=110.0)
    _firm, households = _queue(economy, price=100.0, n=3)
    shares = economy.expected_healthcare_household_shares()
    dollars = economy.expected_healthcare_out_of_pocket_all()
    assert dollars == {h.household_id: pytest.approx(100.0 * shares[h.household_id]) for h in households}
    assert sorted(dollars.values()) == pytest.approx([50.0, 50.0, 90.0])
    for household in economy.households:
        assert economy.expected_healthcare_out_of_pocket(household.household_id) == dollars.get(
            household.household_id, 0.0
        )


def test_stale_queue_id_pointing_at_a_food_firm_reserves_nothing():
    """Households' repro: a queue id reused by a Food firm reserved $5. The
    government side checks the id names an existing Healthcare firm."""
    economy = _economy(level=50)
    _firm, households = _queue(economy, price=100.0, n=1)
    stale = economy.households[3]
    food = next(f for f in economy.firms if f.good_category.lower() == "food")
    food.price = 5.0
    stale.queued_healthcare_firm_id = food.firm_id
    assert stale.household_id not in economy.expected_healthcare_out_of_pocket_all()
    assert economy.expected_healthcare_out_of_pocket(stale.household_id) == 0.0
    # Even if it also sits in a healthcare queue, a non-healthcare id is refused.
    economy._healthcare_firms()[0].healthcare_queue.append(stale.household_id)
    assert stale.household_id not in economy.expected_healthcare_out_of_pocket_all()
    assert economy.expected_healthcare_out_of_pocket(stale.household_id) == 0.0


def test_out_of_pocket_is_zero_when_nothing_is_queued():
    economy = _economy(level=50)
    firm, households = _queue(economy, price=100.0, n=1)
    other = economy.households[3]
    assert economy.expected_healthcare_out_of_pocket(10_000_000) == 0.0  # unknown household
    other.queued_healthcare_firm_id = None
    assert economy.expected_healthcare_out_of_pocket(other.household_id) == 0.0  # not queued
    other.queued_healthcare_firm_id = firm.firm_id  # stale id: not in the queue
    assert economy.expected_healthcare_out_of_pocket(other.household_id) == 0.0
    other.queued_healthcare_firm_id = 10_000_000  # firm gone
    assert economy.expected_healthcare_out_of_pocket(other.household_id) == 0.0


def test_out_of_pocket_all_is_empty_without_queues():
    economy = _economy(level=50)
    for firm in economy._healthcare_firms():
        firm.healthcare_queue = []
    assert economy.expected_healthcare_out_of_pocket_all() == {}


# --- Payment sequences ---------------------------------------------------------------------


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("care_mode,covered,expected", [("patient_pay", False, 1.0), ("covered", True, 0.0)])
def test_payment_sequences_follow_the_care_mode_not_the_subsidy_lever(sequence, care_mode, covered, expected):
    from payment_sectors import payment_care_covered

    economy = _economy(level=50, budget=10.0)
    _firm, households = _queue(economy, price=19.43, n=3)
    economy.payment_sequence = sequence
    economy.payment_care_mode = care_mode
    assert payment_care_covered(economy) is covered
    shares = economy.expected_healthcare_household_shares()
    assert shares == {h.household_id: expected for h in households}
    assert economy.expected_healthcare_out_of_pocket_all() == {
        h.household_id: pytest.approx(19.43 * expected) for h in households
    }
    assert economy.expected_healthcare_out_of_pocket(households[0].household_id) == pytest.approx(19.43 * expected)
