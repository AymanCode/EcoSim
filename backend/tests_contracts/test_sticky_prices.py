"""Contracts for sticky prices (round 1 PR4a).

Requirements (Ayman, 2026-10-17): private firms hold their posted price
between reviews; the existing per-tick rule keeps running on a background
shadow price, and a review jumps the posted price to it; a bigger gap brings
the review sooner, and so does inflation above Gagnon's knee; the calm
interval is drawn per firm from a sourced range; both review fields are set
so a review-aware price cap (#27's ``Economy._price_review_due``; #27 is
closed, the check is kept as the contract) can tell review ticks from hold
ticks; with the flag off nothing changes. Food,
Services and Healthcare go through it; Housing and baseline firms do not.
"""

import random
from contextlib import contextmanager

import pytest

from config import CONFIG, clone_config, use_config
from agents import FirmAgent
from tests_contracts.factories import make_firm


@contextmanager
def sticky(enabled=True, **firm_overrides):
    with use_config(clone_config()):
        CONFIG.firms.sticky_prices_enabled = enabled
        for key, value in firm_overrides.items():
            setattr(CONFIG.firms, key, value)
        yield


def private(category="Food", firm_id=7, price=10.0):
    return make_firm(firm_id=firm_id, category=category, is_baseline=False, price=price)


def rule_raises(monkeypatch, step):
    """Replace the per-tick rule with 'raise the price it is given by step'."""
    def plan_pricing(self, sell_through_rate, unemployment_rate, in_warmup=False,
                     health_snapshot=None, profit_tax_rate=0.0):
        return {"price_next": float(self.price) * (1.0 + step), "markup_next": 0.0}
    monkeypatch.setattr(FirmAgent, "plan_pricing", plan_pricing)


def plan(firm, tick, inflation=0.0):
    return firm.plan_sticky_pricing(tick, inflation, 0.5, unemployment_rate=0.1)


def review_due(firm, now):
    """#27's check, restated (#27 closed): a review tick, or no hold in force."""
    if firm.last_price_review_tick is not None and firm.last_price_review_tick == now:
        return True
    return firm.next_price_review_tick is None or firm.next_price_review_tick <= now


# --- holding and jumping -------------------------------------------------------

def test_posted_price_holds_while_shadow_follows_the_rule_then_jumps_at_review(monkeypatch):
    with sticky():
        firm = private()
        rule_raises(monkeypatch, 0.01)
        posted = []
        for tick in range(1, 80):
            p = plan(firm, tick)
            firm.price = p["price_next"]
            posted.append((tick, firm.price, p["price_review"], p["price_shadow"]))
        reviews = [row for row in posted if row[2]]
        assert reviews, "a firm must review eventually"
        first = reviews[0][0]
        # Before the first review the posted price never moved.
        assert all(price == pytest.approx(10.0) for tick, price, _, _ in posted if tick < first)
        # At the review it jumps to the price weekly repricing would have reached.
        tick, price, _, shadow = reviews[0]
        assert price == pytest.approx(shadow)
        assert price == pytest.approx(10.0 * 1.01 ** tick)


def test_first_sticky_tick_seeds_the_shadow_with_the_posted_price(monkeypatch):
    with sticky():
        firm = private(price=12.5)
        rule_raises(monkeypatch, 0.0)
        p = plan(firm, 30)
        assert p["price_shadow"] == pytest.approx(12.5)
        assert p["price_next"] == pytest.approx(12.5)


def test_bigger_gap_brings_the_review_sooner(monkeypatch):
    def weeks_to_first_review(step):
        firm = private()
        rule_raises(monkeypatch, step)
        for tick in range(1, 200):
            p = plan(firm, tick)
            firm.price = p["price_next"]
            if p["price_review"]:
                return tick
        return None

    with sticky():
        calm = weeks_to_first_review(0.0)
        drifting = weeks_to_first_review(0.02)
        racing = weeks_to_first_review(0.10)
    assert calm is not None and drifting is not None and racing is not None
    assert racing < drifting < calm
    # With no gap the firm reviews on its calm-market interval.
    assert calm == pytest.approx(private().price_review_interval(), abs=1.0)


def test_hazard_doubles_when_the_gap_equals_the_gap_scale():
    with sticky():
        firm = private()
        base = firm.price_review_hazard(10.0, 10.0, 0.0)
        at_scale = firm.price_review_hazard(10.0 * (1 + CONFIG.firms.price_review_gap_scale), 10.0, 0.0)
        assert at_scale == pytest.approx(2.0 * base)
        assert base == pytest.approx(1.0 / firm.price_review_interval())


def test_inflation_speeds_reviews_only_above_the_knee():
    with sticky():
        firm = private()
        knee = CONFIG.firms.price_review_inflation_knee
        base = firm.price_review_hazard(10.0, 10.0, 0.0)
        assert firm.price_review_hazard(10.0, 10.0, knee) == pytest.approx(base)
        assert firm.price_review_hazard(10.0, 10.0, -0.3) == pytest.approx(base)
        high = firm.price_review_hazard(10.0, 10.0, knee + 0.5)
        assert high == pytest.approx(base * (1 + CONFIG.firms.price_review_inflation_slope * 0.5))


# --- per-firm intervals -----------------------------------------------------------

@pytest.mark.parametrize("category,key", [
    ("Food", "price_review_weeks_food"),
    ("Services", "price_review_weeks_services"),
    ("Healthcare", "price_review_weeks_healthcare"),
])
def test_interval_is_drawn_per_firm_inside_the_category_range(category, key):
    low, high = getattr(CONFIG.firms, key)
    intervals = [private(category, firm_id=i).price_review_interval() for i in range(1, 60)]
    assert all(low <= x <= high for x in intervals)
    assert len({round(x, 6) for x in intervals}) > 50  # firms differ
    assert private(category, firm_id=5).price_review_interval() == private(category, firm_id=5).price_review_interval()


def test_drawing_intervals_consumes_no_random_numbers():
    state = random.getstate()
    for i in range(20):
        private(firm_id=i).price_review_interval()
    assert random.getstate() == state


# --- review fields for a review-aware price cap (#27's check) -------------------------

def test_review_fields_mark_review_ticks_and_hold_ticks(monkeypatch):
    with sticky():
        firm = private()
        rule_raises(monkeypatch, 0.03)
        saw_review = saw_hold = False
        for tick in range(1, 60):
            p = plan(firm, tick)
            firm.price = p["price_next"]
            assert firm.next_price_review_tick is not None and firm.next_price_review_tick > tick
            if p["price_review"]:
                saw_review = True
                assert firm.last_price_review_tick == tick
                assert review_due(firm, tick)
            else:
                saw_hold = True
                assert firm.last_price_review_tick != tick
                assert not review_due(firm, tick)
        assert saw_review and saw_hold


# --- which firms are sticky -----------------------------------------------------------

@pytest.mark.parametrize("category", ["Food", "Services", "Healthcare"])
def test_private_food_services_and_healthcare_firms_are_sticky_after_warmup(category):
    with sticky():
        firm = private(category)
        assert firm.uses_sticky_prices(in_warmup=False)
        assert not firm.uses_sticky_prices(in_warmup=True)


def test_housing_and_baseline_firms_reprice_every_tick():
    with sticky():
        assert not private("Housing").uses_sticky_prices(in_warmup=False)
        baseline = make_firm(firm_id=3, category="Food", is_baseline=True)
        assert not baseline.uses_sticky_prices(in_warmup=False)


def test_flag_off_means_no_firm_is_sticky():
    with sticky(enabled=False):
        for category in ("Food", "Services", "Healthcare"):
            assert not private(category).uses_sticky_prices(in_warmup=False)


@pytest.mark.parametrize("category", ["Services", "Healthcare"])
def test_shadow_follows_the_real_category_rule_and_the_posted_price_holds(category):
    """The category's own plan_pricing drives the shadow; posting waits for a review."""
    with sticky():
        firm = private(category, price=50.0)
        firm.employees = [1, 2, 3]
        firm.actual_wages = {1: 40.0, 2: 40.0, 3: 40.0}
        flexible = firm.plan_pricing(0.5, unemployment_rate=0.1)["price_next"]
        assert flexible != pytest.approx(50.0)  # the rule wants to move
        p = plan(firm, 30)
        assert p["price_shadow"] == pytest.approx(max(firm.min_price, flexible))
        if not p["price_review"]:
            assert p["price_next"] == pytest.approx(50.0)
        else:
            assert p["price_next"] == pytest.approx(p["price_shadow"])


# --- economy wiring -----------------------------------------------------------------

def test_flag_off_economy_never_sets_review_fields(tiny_economy_factory):
    with sticky(enabled=False):
        economy = tiny_economy_factory(num_households=30, num_firms_per_category=2, baseline_firms=False)
        for _ in range(40):
            economy.step()
        for firm in economy.firms:
            assert firm.price_shadow is None
            assert firm.last_price_review_tick is None
            assert firm.next_price_review_tick is None


def test_flag_on_economy_holds_private_prices_between_reviews(tiny_economy_factory):
    with sticky(enabled=True):
        economy = tiny_economy_factory(num_households=30, num_firms_per_category=2, baseline_firms=False)
        held = changed_off_review = 0
        prev = {}
        for _ in range(60):
            economy.step()
            for firm in economy.firms:
                if not firm.uses_sticky_prices(economy.in_warmup) or firm.price_shadow is None:
                    continue
                if (firm.good_category or "").lower() == "services":
                    continue  # clearing may raise a Services price on scarcity (documented)
                old = prev.get(firm.firm_id)
                reviewed = firm.decision_diagnostics.get("price_review", False)
                if old is not None and not reviewed:
                    held += 1
                    if abs(firm.price - old) > 1e-9 * max(old, 1.0):
                        changed_off_review += 1
            prev = {f.firm_id: f.price for f in economy.firms}
    assert held > 0
    assert changed_off_review == 0
