"""Money-conservation leak reproductions for the agents/economy audit (Phase 0).

Each ``xfail(strict=True)`` test pins one leak from
``docs/reviews/2026-09-28-agents-economy-code-audit.md`` section A on the
default ``legacy`` payment path. The tests assert the correct behavior, so
they fail today on the conservation (or interest) assertion itself. When a
Phase 4 fix lands, the test starts passing and strict mode turns the stale
marker into a failure so it gets removed.

The control test is not xfail: the same small legacy economy with a bank and
none of the leak triggers must conserve ``total_money_with_bank``.
"""

from typing import Dict, List

import pytest

from agents import BankAgent
from config import CONFIG
from tests_contracts.conftest import total_money_with_bank
from tests_contracts.factories import (
    make_economy,
    make_firm,
    make_firms,
    make_government,
    make_households,
)

MONEY_TOL = 1e-6


def _legacy_economy_with_bank(
    *,
    categories=("Food", "Housing", "Services", "Healthcare"),
    num_households: int = 30,
    bank_reserves: float = 50_000.0,
    government_cash: float = 20_000.0,
    seed: int = 333,
    firms=None,
    government=None,
):
    assert CONFIG.payment_sequence == "legacy", "leak tests target the legacy payment path"
    households = make_households(num_households, skills_start=0.6, skills_step=0.0)
    gov = government or make_government(cash_balance=government_cash)
    economy = make_economy(
        households=households,
        firms=firms,
        government=gov,
        categories=categories,
        num_firms_per_category=2,
        baseline_firms=True,
        disable_shocks=True,
        seed=seed,
    )
    economy.bank = BankAgent(cash_reserves=bank_reserves)
    return economy


def test_control_legacy_economy_with_bank_conserves_money_over_five_ticks(fixed_seed):
    """Control: no subsidy, baseline firms only (no long-term loans), bank able to lend.

    Warmup ticks only: all 5 ticks fall inside the default 10-tick warmup.
    Past warmup this economy drifts from tick 11 as legacy new-firm creation
    seeds cash with no debit (audit A5, known limitation K02), which this
    phase does not pin.
    """
    economy = _legacy_economy_with_bank()
    assert economy.government.sector_subsidy_target == "none"
    assert economy.bank is not None and economy.bank.can_lend()

    initial_total = total_money_with_bank(economy)
    for tick in range(5):
        economy.step()
        observed = total_money_with_bank(economy)
        drift = observed - initial_total
        assert abs(drift) <= MONEY_TOL, f"control drift {drift:+.6f} after tick {tick}"


@pytest.mark.xfail(
    strict=True,
    reason="audit A1: subsidized purchase is scaled down after the firm was paid in full",
)
def test_a1_subsidized_purchase_scale_down_conserves_money(fixed_seed, monkeypatch):
    economy = _legacy_economy_with_bank(categories=("Food", "Services"))
    economy.government.set_lever("sector_subsidy_target", "food")
    economy.government.set_lever("sector_subsidy_level", 50)
    assert economy.government._sector_subsidy_rate == pytest.approx(0.5)

    food_firm = next(f for f in economy.firms if f.good_category == "Food")
    buyer = economy.households[0]
    buyer_settlements: List[Dict[str, float]] = []

    original_clear = economy._clear_goods_market

    def clear_with_oversized_plan(plans, firms):
        # Goods clearing does not check household cash, so a planned food
        # purchase larger than the buyer's cash plus this tick's income clears
        # in full and the firm is credited qty * price. Planning never
        # produces this at tick 0 (budgets are small), so the test forces it:
        # ~$2,400 of food against ~$1,250 of cash plus wage.
        plans[buyer.household_id]["planned_purchases"][food_firm.firm_id] = 300.0
        return original_clear(plans, firms)

    original_settle = economy.settle_capped_subsidized_goods_purchase

    def spy_settle(household, total_cost, subsidy_rate):
        result = original_settle(household, total_cost, subsidy_rate)
        if household is buyer:
            buyer_settlements.append({"total_cost": float(total_cost), "scale": float(result[2])})
        return result

    monkeypatch.setattr(economy, "_clear_goods_market", clear_with_oversized_plan)
    monkeypatch.setattr(economy, "settle_capped_subsidized_goods_purchase", spy_settle)

    before = total_money_with_bank(economy)
    economy.step()
    after = total_money_with_bank(economy)

    # Precondition checks the trigger, not the bug, so a fix that caps the
    # quantity during clearing still reaches the conservation assertion.
    assert buyer_settlements, "precondition: the buyer's food purchase was not settled as subsidized"
    expected_leak = sum((1.0 - s["scale"]) * s["total_cost"] for s in buyer_settlements)
    assert after == pytest.approx(before, abs=MONEY_TOL), (
        f"A1 leak: money changed by {after - before:+.6f} in one tick; "
        f"sum((1 - scale) * total_cost) over the buyer's subsidized settlements = {expected_leak:.6f}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="audit A2: long-term capital loan principal is reset by plan_capital_investment",
)
def test_a2_long_term_capital_loan_conserves_money(fixed_seed):
    government = make_government()
    firms = make_firms(("Food", "Healthcare"), num_per_category=1, government=government)
    services = make_firm(firm_id=10, category="Services", is_baseline=False)
    services.lost_sales_streak = 5  # sustained-demand gate
    firms.append(services)
    economy = _legacy_economy_with_bank(firms=firms, government=government)
    # Every household starts unemployed, so the 10% trigger is met on tick 0.
    unemployed = sum(1 for h in economy.households if not h.is_employed)
    assert unemployed / len(economy.households) >= CONFIG.firms.long_term_capital_unemployment_trigger

    before = total_money_with_bank(economy)
    economy.step()
    after = total_money_with_bank(economy)

    principal = float(getattr(services, "total_long_term_loans_received", 0.0))
    assert principal > 0.0, "precondition: the services firm did not receive a long-term loan"
    assert after == pytest.approx(before, abs=MONEY_TOL), (
        f"A2 leak: money changed by {after - before:+.6f} in one tick; "
        f"long-term loan principal = {principal:.6f}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="audit A3: medical-loan fallback creates money when a bank is present but cannot lend",
)
def test_a3_medical_loan_fallback_with_bank_conserves_money(fixed_seed, monkeypatch):
    # Bank with zero reserves cannot lend; treasury with zero cash cannot back a loan.
    economy = _legacy_economy_with_bank(
        categories=("Food", "Healthcare"),
        bank_reserves=0.0,
        government_cash=0.0,
    )
    bank = economy.bank
    assert not bank.can_lend()

    healthcare = next(f for f in economy.firms if f.good_category == "Healthcare")
    food = next(f for f in economy.firms if f.good_category == "Food")
    doctor, patient = economy.households[0], economy.households[1]
    doctor.medical_training_status = "doctor"
    doctor.employer_id = healthcare.firm_id
    doctor.wage = healthcare.wage_offer
    healthcare.employees = [doctor.household_id]

    patient.employer_id = food.firm_id  # fallback requires an employed household
    patient.wage = food.wage_offer
    if patient.household_id not in food.employees:
        food.employees.append(patient.household_id)
    patient.health = 0.25
    patient.pending_healthcare_visits = 2
    patient.next_healthcare_request_tick = 0
    patient.cash_balance = 0.0

    medical_loan_requests: List[float] = []
    fallback_loans: List[float] = []
    original_issue = economy._issue_medical_loan
    original_take = patient.take_medical_loan

    def spy_issue(household, amount):
        if household is patient:
            medical_loan_requests.append(float(amount))
        return original_issue(household, amount)

    def spy_take(amount):
        fallback_loans.append(float(amount))
        return original_take(amount)

    monkeypatch.setattr(economy, "_issue_medical_loan", spy_issue)
    monkeypatch.setattr(patient, "take_medical_loan", spy_take)

    before = total_money_with_bank(economy)
    economy.step()
    after = total_money_with_bank(economy)

    # Precondition checks the trigger (an unaffordable visit reached the loan
    # path), not the bug, so a fix that gates the fallback on ``bank is None``
    # still reaches the conservation assertion.
    assert medical_loan_requests, "precondition: the patient's unaffordable visit never requested a medical loan"
    assert after == pytest.approx(before, abs=MONEY_TOL), (
        f"A3 leak: money changed by {after - before:+.6f} in one tick; "
        f"fallback medical loans = {sum(fallback_loans):.6f}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="audit A4: originate_loan charges one year of interest regardless of term",
)
def test_a4_loan_total_repayment_scales_with_term():
    principal = 10_000.0
    annual_rate = 0.05
    ticks_per_year = CONFIG.time.ticks_per_year
    mismatches = []
    for term_ticks in (520, 26):
        bank = BankAgent(cash_reserves=100_000.0)
        loan = bank.originate_loan("firm", 1, principal, annual_rate, term_ticks)
        expected = principal * (1.0 + annual_rate * term_ticks / ticks_per_year)
        if abs(loan["remaining"] - expected) > MONEY_TOL:
            mismatches.append(
                f"term {term_ticks}: total_repayment {loan['remaining']:.6f} "
                f"expected {expected:.6f} (diff {loan['remaining'] - expected:+.6f})"
            )
    assert not mismatches, "A4: " + "; ".join(mismatches)
