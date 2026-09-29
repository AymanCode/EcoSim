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
    patch_agent_method,
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


def test_a1_subsidized_purchase_scale_down_conserves_money(fixed_seed, monkeypatch):
    economy = _legacy_economy_with_bank(categories=("Food", "Services"))
    economy.government.set_lever("sector_subsidy_target", "food")
    economy.government.set_lever("sector_subsidy_level", 50)
    assert economy.government._sector_subsidy_rate == pytest.approx(0.5)

    food_firm = next(f for f in economy.firms if f.good_category == "Food")
    buyer = economy.households[0]
    buyer_settlements: List[Dict[str, float]] = []

    original_clear = economy._clear_goods_market
    cleared: Dict[str, object] = {}

    def clear_with_oversized_plan(plans, firms):
        # Goods clearing does not check household cash, so a planned food
        # purchase larger than the buyer's cash plus this tick's income clears
        # in full and the firm is credited qty * price. Planning never
        # produces this at tick 0 (budgets are small), so the test forces it:
        # ~$2,400 of food against ~$1,250 of cash plus wage.
        plans[buyer.household_id]["planned_purchases"][food_firm.firm_id] = 300.0
        cleared["inventory"] = food_firm.inventory_units
        purchases, sales = original_clear(plans, firms)
        cleared["units"] = sales[food_firm.firm_id]["units_sold"]
        cleared["sales"] = sales
        return purchases, sales

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

    # Units: the seller books, and loses from inventory, only what households received.
    received = sum(
        h.last_purchase_breakdown.get(food_firm.good_name, {}).get("units", 0.0) for h in economy.households
    )
    assert received < cleared["units"] - 1.0, "precondition: the scale-down returned no units"
    assert food_firm.last_units_sold == pytest.approx(received)
    assert cleared["sales"][food_firm.firm_id]["units_sold"] == pytest.approx(received)
    assert food_firm.inventory_units == pytest.approx(cleared["inventory"] - received)


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
    patch_agent_method(monkeypatch, patient, "take_medical_loan", spy_take)

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


def test_a4_loan_total_repayment_scales_with_term():
    """Audit A4: the legacy loan total follows the payment arm's amortized schedule.

    ``payment_loans.v2_payment`` amortizes at ``annual_rate / ticks_per_year``
    per tick, so the legacy ``originate_loan`` now owes ``payment * term``
    (Phase 0 pinned simple interest pro-rated by term; the adopted formula is
    the payment arm's). The arms agree on the installment and on the total
    paid on schedule. They still differ on interest timing (the payment arm
    accrues on the declining balance; legacy books the total up front and
    splits each payment proportionally), on write-off size, and on early or
    partial payment.
    """
    principal = 10_000.0
    annual_rate = 0.05
    ticks_per_year = CONFIG.time.ticks_per_year
    per_tick_rate = annual_rate / ticks_per_year
    mismatches = []
    for term_ticks in (520, 26):
        bank = BankAgent(cash_reserves=100_000.0)
        loan = bank.originate_loan("firm", 1, principal, annual_rate, term_ticks)
        payment = principal * per_tick_rate / (1.0 - (1.0 + per_tick_rate) ** -term_ticks)
        expected = payment * term_ticks
        if abs(loan["remaining"] - expected) > MONEY_TOL or abs(loan["payment_per_tick"] - payment) > MONEY_TOL:
            mismatches.append(
                f"term {term_ticks}: total_repayment {loan['remaining']:.6f} "
                f"expected {expected:.6f} (diff {loan['remaining'] - expected:+.6f})"
            )
    assert not mismatches, "A4: " + "; ".join(mismatches)


def test_a8_partially_funded_investment_loan_spends_only_funded_amount(fixed_seed, monkeypatch):
    """Audit A8: the bank lends ``min(request, max_borrowable)``; the firm must spend only that."""
    economy = _legacy_economy_with_bank(categories=("Food", "Services"))
    firm = next(f for f in economy.firms if f.good_category == "Food")
    request = 5_000.0
    trailing_revenue = 1_000.0  # leverage ceiling 3x -> the bank can fund at most 3,000

    # Start the firm with no cash (moved to the treasury, so money is unchanged):
    # with the bug, spending the full request pushes it negative.
    economy.government.cash_balance += firm.cash_balance
    firm.cash_balance = 0.0

    original_plan = type(firm).plan_capital_investment

    def plan_then_request_loan(bank=None):
        original_plan(firm, bank=bank)
        firm.trailing_revenue_12t = trailing_revenue
        firm.needs_investment_loan = True
        firm.investment_loan_amount = request

    patch_agent_method(monkeypatch, firm, "plan_capital_investment", plan_then_request_loan)

    funded: List[float] = []
    original_issue = economy._issue_firm_loan

    def spy_issue(target, *args, **kwargs):
        cash_before = target.cash_balance
        result = original_issue(target, *args, **kwargs)
        if target is firm:
            funded.append(target.cash_balance - cash_before)
        return result

    cash_around_offer: List[float] = []
    original_offer = economy._offer_investment_loans

    def spy_offer():
        cash_around_offer.append(firm.cash_balance)
        original_offer()
        cash_around_offer.append(firm.cash_balance)

    monkeypatch.setattr(economy, "_issue_firm_loan", spy_issue)
    monkeypatch.setattr(economy, "_offer_investment_loans", spy_offer)

    before = total_money_with_bank(economy)
    economy.step()
    after = total_money_with_bank(economy)

    assert funded and 0.0 < funded[0] < request - 1.0, (
        f"precondition: the bank should fund part of the request, funded={funded}"
    )
    cash_before_offer, cash_after_offer = cash_around_offer
    assert cash_after_offer >= cash_before_offer - MONEY_TOL, (
        f"A8: firm cash fell from {cash_before_offer:.6f} to {cash_after_offer:.6f} after a loan "
        f"funding {funded[0]:.6f} of a {request:.2f} request"
    )
    assert after == pytest.approx(before, abs=MONEY_TOL), f"A8: money changed by {after - before:+.6f}"


def _ledger_gap(household) -> float:
    ledger = household.last_tick_ledger
    return sum(v for k, v in ledger.items() if k != "net") - ledger["net"]


def _deposit_savings(economy, household, amount: float) -> None:
    household.bank_deposit += amount
    economy.bank.accept_deposit(household.household_id, amount)


def test_a9_deposit_withdrawals_are_recorded_in_household_ledger(fixed_seed, monkeypatch):
    """Audit A9: every deposit withdrawal appears as a ``bank`` ledger flow.

    Over a full tick, rent drawn from deposits (``_ensure_cash_for_payment``)
    must leave the saver's ledger summing to its cash change. The pre-purchase
    withdrawal is then checked directly.
    """
    economy = _legacy_economy_with_bank()
    saver = economy.households[2]
    # Cash at the subsistence floor: rent needs deposits, but no legacy
    # consumption loan fires (keeps this test to the withdrawal alone).
    saver.cash_balance = saver.subsistence_min_cash
    _deposit_savings(economy, saver, 5_000.0)

    rent_withdrawals: List[float] = []
    original_ensure = economy._ensure_cash_for_payment

    def spy_ensure(household, amount):
        deposit_before = household.bank_deposit
        result = original_ensure(household, amount)
        if household is saver:
            rent_withdrawals.append(deposit_before - household.bank_deposit)
        return result

    monkeypatch.setattr(economy, "_ensure_cash_for_payment", spy_ensure)
    economy.step()

    assert sum(rent_withdrawals) > 0.0, "precondition: the saver did not draw on deposits to pay"
    assert abs(_ledger_gap(saver)) <= MONEY_TOL, (
        f"A9: ledger flows miss {_ledger_gap(saver):+.6f} of the saver's cash change "
        f"(withdrawn to pay {sum(rent_withdrawals):.6f}; ledger {saver.last_tick_ledger})"
    )

    shopper = economy.households[4]
    shopper.cash_balance = 0.0
    _deposit_savings(economy, shopper, 1_000.0)
    shopper.reset_tick_ledger()
    economy._withdraw_deposits_for_planned_consumption({shopper.household_id: {"budget": 80.0}})
    shopper.finalize_tick_ledger()
    assert shopper.last_tick_ledger["net"] == pytest.approx(80.0)
    assert abs(_ledger_gap(shopper)) <= MONEY_TOL, (
        f"A9: pre-purchase withdrawal missing from the ledger (gap {_ledger_gap(shopper):+.6f})"
    )


def test_a9_healthcare_deposit_withdrawal_is_recorded_in_household_ledger(fixed_seed, monkeypatch):
    """Audit A9: a visit paid from deposits appears as a ``bank`` ledger flow."""
    economy = _legacy_economy_with_bank(categories=("Food", "Healthcare"))
    healthcare = next(f for f in economy.firms if f.good_category == "Healthcare")
    food = next(f for f in economy.firms if f.good_category == "Food")
    doctor, patient = economy.households[0], economy.households[1]
    doctor.medical_training_status = "doctor"
    doctor.employer_id = healthcare.firm_id
    doctor.wage = healthcare.wage_offer
    healthcare.employees = [doctor.household_id]
    patient.employer_id = food.firm_id
    patient.wage = food.wage_offer
    if patient.household_id not in food.employees:
        food.employees.append(patient.household_id)
    patient.health = 0.25
    patient.pending_healthcare_visits = 2
    patient.next_healthcare_request_tick = 0
    # Cash below the visit price, with savings. A credit score under 0.4 keeps
    # the legacy consumption loan (an unrelated credit) off.
    patient.cash_balance = 5.0
    economy.bank.household_credit_scores[patient.household_id] = 0.3
    _deposit_savings(economy, patient, 5_000.0)

    care_withdrawals: List[float] = []
    original_process = economy._process_healthcare_services

    def spy_process(per_firm_sales):
        deposit_before = patient.bank_deposit
        result = original_process(per_firm_sales)
        care_withdrawals.append(deposit_before - patient.bank_deposit)
        return result

    monkeypatch.setattr(economy, "_process_healthcare_services", spy_process)
    # Keep the pre-purchase withdrawal (checked in the test above) from topping
    # up cash first, so the visit itself has to draw on deposits.
    monkeypatch.setattr(economy, "_withdraw_deposits_for_planned_consumption", lambda plans: None)
    economy.step()

    assert sum(care_withdrawals) > 0.0, "precondition: the visit did not draw on deposits"
    assert abs(_ledger_gap(patient)) <= MONEY_TOL, (
        f"A9: healthcare withdrawal missing from the ledger (gap {_ledger_gap(patient):+.6f}, "
        f"withdrawn {sum(care_withdrawals):.6f})"
    )


def test_capital_recycle_is_recorded_in_household_ledger(fixed_seed, monkeypatch):
    """Phase 4 follow-up: the legacy capital recycle appears in each household's ledger.

    The A2 scenario (a long-term capital loan on tick 1) makes
    ``_recycle_capital_investment`` pay every household. After the tick each
    household's ledger flows must sum to its cash change.
    """
    government = make_government()
    firms = make_firms(("Food", "Healthcare"), num_per_category=1, government=government)
    services = make_firm(firm_id=10, category="Services", is_baseline=False)
    services.lost_sales_streak = 5  # sustained-demand gate
    firms.append(services)
    economy = _legacy_economy_with_bank(firms=firms, government=government)

    recycled: List[float] = []
    original_recycle = economy._recycle_capital_investment

    def spy_recycle():
        cash_before = economy.households[0].cash_balance
        original_recycle()
        recycled.append(economy.households[0].cash_balance - cash_before)

    monkeypatch.setattr(economy, "_recycle_capital_investment", spy_recycle)
    economy.step()

    assert sum(recycled) > 0.0, "precondition: the recycle paid nothing"
    gaps = {h.household_id: _ledger_gap(h) for h in economy.households if abs(_ledger_gap(h)) > MONEY_TOL}
    assert not gaps, (
        f"recycle missing from the ledger: gaps {gaps} (recycled {sum(recycled):.6f} per household)"
    )


def test_legacy_consumption_loan_is_recorded_in_household_ledger(fixed_seed):
    """Phase 4 follow-up: the legacy consumption loan appears as a ``bank`` ledger flow."""
    economy = _legacy_economy_with_bank()
    borrower = economy.households[3]
    # Below the subsistence floor with the default 0.5 credit score: the
    # request in household planning fires and _offer_consumption_loans lends.
    borrower.cash_balance = 0.5 * borrower.subsistence_min_cash
    assert economy.bank.get_household_credit_score(borrower.household_id) >= 0.4
    economy.step()

    assert borrower.consumption_loan_remaining > 0.0, "precondition: no consumption loan was made"
    assert abs(_ledger_gap(borrower)) <= MONEY_TOL, (
        f"consumption loan missing from the ledger: gap {_ledger_gap(borrower):+.6f} "
        f"(ledger {borrower.last_tick_ledger})"
    )
