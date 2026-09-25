"""Cash/claim tests for the PS3.1 registered debt owner."""

from types import SimpleNamespace

import pytest

from agents import BankAgent, GovernmentAgent
from payment_loans import (
    can_underwrite,
    collect_firm_dues,
    collect_household_dues,
    firm_exit_claims,
    fund_medical_loan,
    originate_v2,
    preflight_loans,
    prepare_household_dues,
    quote_medical_loan,
    quoted_annual_rate,
    rollback_medical_loan,
    settle_firm_exit_claim,
)


def household(hid, cash=0):
    ledger = []
    return SimpleNamespace(
        household_id=hid, cash_balance=cash,
        medical_loan_principal=0.0, medical_loan_remaining=0.0,
        medical_loan_payment_per_tick=0.0, medical_loan_bank_serviced=False,
        consumption_loan_remaining=0.0, consumption_loan_payment_per_tick=0.0,
        add_ledger_flow=lambda kind, amount: ledger.append((kind, amount)),
        ledger=ledger,
    )


def economy(*households):
    bank = BankAgent(cash_reserves=1000.0)
    government = GovernmentAgent(cash_balance=1000.0)
    return SimpleNamespace(
        current_tick=0, bank=bank, government=government,
        households=list(households), household_lookup={h.household_id: h for h in households},
        firms=[], firm_lookup={}, payment_book=SimpleNamespace(),
        payment_state={"prior_settled_household_net": {h.household_id: 100.0 for h in households}},
    )


def legacy(e, hh, principal, due, *, subtype="consumption", treasury=False):
    if treasury:
        loan = e.bank.issue_government_backed_loan("household", hh.household_id, principal, 0, 10, e.government)
    else:
        loan = e.bank.originate_loan("household", hh.household_id, principal, 0, 10)
    loan["subtype"] = subtype
    loan["payment_per_tick"] = due
    setattr(hh, f"{subtype}_loan_remaining", getattr(hh, f"{subtype}_loan_remaining") + loan["remaining"])
    return loan


def test_indexed_pro_rata_partial_credits_actual_funders_and_keeps_miss():
    hh = household(1, 20)
    e = economy(hh)
    bank_claim = legacy(e, hh, 60, 30)
    treasury_claim = legacy(e, hh, 40, 10, treasury=True)
    preflight_loans(e)
    due = prepare_household_dues(e)
    assert due == {1: 40}
    before_reserves, before_treasury = e.bank.cash_reserves, e.government.cash_balance
    assert collect_household_dues(e) == pytest.approx(20)
    assert hh.cash_balance == pytest.approx(0)
    assert e.bank.cash_reserves - before_reserves == pytest.approx(15)
    assert e.government.cash_balance - before_treasury == pytest.approx(5)
    assert bank_claim["missed_payments"] == treasury_claim["missed_payments"] == 1
    assert hh.consumption_loan_remaining == pytest.approx(80)
    with pytest.raises(ValueError, match="already collected"):
        collect_household_dues(e)


def test_v2_accrues_once_on_principal_and_not_before_next_tick():
    hh = household(1, 100)
    e = economy(hh)
    funded = fund_medical_loan(e, hh, 52)
    assert funded == 52
    claim = e.bank.active_loans[0]
    assert claim["contract_version"] == 2
    assert prepare_household_dues(e) == {}
    assert collect_household_dues(e) == 0
    e.current_tick = 1
    first_due = prepare_household_dues(e)[1]
    assert first_due > 0
    outstanding = e.bank.total_loans_outstanding
    assert prepare_household_dues(e)[1] == first_due
    assert e.bank.total_loans_outstanding == pytest.approx(outstanding)
    interest = 52 * claim["rate"] / 52
    assert claim["accrued_interest"] == pytest.approx(interest)
    paid = collect_household_dues(e)
    assert paid == pytest.approx(first_due)
    assert claim["accrued_interest"] == pytest.approx(0)
    assert claim["principal_remaining"] == pytest.approx(52 - (paid - interest))
    e.current_tick = 2
    prepare_household_dues(e)
    assert claim["accrued_interest"] == pytest.approx(claim["principal_remaining"] * claim["rate"] / 52)


def test_partial_payment_does_not_cure_default_and_writeoff_is_non_cash():
    hh = household(1, 1)
    e = economy(hh)
    claim = legacy(e, hh, 100, 10)
    claim["missed_payments"] = 7
    prepare_household_dues(e)
    reserves = e.bank.cash_reserves
    assert collect_household_dues(e) == pytest.approx(1)
    assert e.bank.cash_reserves == pytest.approx(reserves + 1)
    assert claim["remaining"] == 0
    assert e.bank.loan_loss_provision == pytest.approx(99)
    assert e.bank.last_tick_defaults == pytest.approx(99)
    assert hh.consumption_loan_remaining == 0


def test_medical_credit_is_direct_to_clearing_and_can_roll_back():
    hh = household(1, 0)
    e = economy(hh)
    reserves = e.bank.cash_reserves
    assert quote_medical_loan(e, hh, 25)
    assert fund_medical_loan(e, hh, 25) == 25
    assert hh.cash_balance == 0
    assert e.bank.cash_reserves == pytest.approx(reserves - 25)
    assert hh.medical_loan_remaining == pytest.approx(25)
    assert rollback_medical_loan(e, hh)
    assert e.bank.cash_reserves == pytest.approx(reserves)
    assert e.bank.active_loans == []
    assert hh.medical_loan_remaining == 0


def test_v2_partial_does_not_advance_term_or_clear_miss():
    hh = household(1, 0.5)
    e = economy(hh)
    assert fund_medical_loan(e, hh, 52) == 52
    claim = e.bank.active_loans[0]
    e.current_tick = 1
    assert prepare_household_dues(e)[1] > 0.5
    assert collect_household_dues(e) == pytest.approx(0.5)
    assert claim["term_remaining"] == 52
    assert claim["missed_payments"] == 1


def test_v2_household_miss_accrues_on_principal_only_then_discharge_cools_credit():
    hh = household(1, 0)
    e = economy(hh)
    assert fund_medical_loan(e, hh, 52) == 52
    claim = e.bank.active_loans[0]
    per_tick_interest = 52 * claim["rate"] / claim["ticks_per_year"]
    for tick in range(1, 9):
        e.current_tick = tick
        prepare_household_dues(e)
        assert claim["accrued_interest"] == pytest.approx(tick * per_tick_interest)
        assert collect_household_dues(e) == 0
    assert claim["principal_remaining"] == 0
    assert claim["accrued_interest"] == 0
    assert hh.medical_loan_remaining == 0
    assert e.bank.loan_loss_provision == pytest.approx(52 + 8 * per_tick_interest)
    assert e.payment_state["loan_default_history"][0]["borrower_discharge"] == pytest.approx(52 + 8 * per_tick_interest)
    assert not quote_medical_loan(e, hh, 1)


def test_preflight_rejects_duplicate_ids_and_unregistered_mirror():
    hh = household(1)
    e = economy(hh)
    hh.medical_loan_remaining = 10
    with pytest.raises(ValueError, match="Unregistered"):
        preflight_loans(e)
    hh.medical_loan_remaining = 0
    a = legacy(e, hh, 10, 1)
    b = legacy(e, hh, 10, 1)
    a["claim_id"] = b["claim_id"] = "same"
    with pytest.raises(ValueError, match="Duplicate"):
        preflight_loans(e)


def test_firm_collector_stays_separate_and_preserves_mortgage_mirror():
    e = economy()
    firm = SimpleNamespace(
        firm_id=4, cash_balance=5.0, bank_loan_remaining=0.0,
        bank_loan_payment_per_tick=0.0,
        service_infrastructure_loan_remaining=0.0,
        service_infrastructure_loan_payment_per_tick=0.0,
        housing_active_loans=[SimpleNamespace(principal_remaining=40.0, pmt_per_tick=4.0)],
    )
    e.firms = [firm]
    e.firm_lookup = {4: firm}
    loan = e.bank.originate_loan("firm", 4, 20, 0, 10)
    loan["payment_per_tick"] = 10
    firm.bank_loan_remaining = 60  # registered 20 plus separate mortgage 40
    preflight_loans(e)
    assert collect_firm_dues(e) == pytest.approx(5)
    assert firm.cash_balance == 0
    assert firm.bank_loan_remaining == pytest.approx(55)
    assert firm.bank_loan_payment_per_tick == pytest.approx(14)
    assert loan["missed_payments"] == 1


def test_firm_exit_registered_claim_posts_one_funder_and_one_writeoff():
    e = economy()
    firm = SimpleNamespace(
        firm_id=4, cash_balance=6.0, bank_loan_remaining=30.0,
        bank_loan_payment_per_tick=5.0,
        service_infrastructure_loan_remaining=0.0,
        service_infrastructure_loan_payment_per_tick=0.0,
        housing_active_loans=[SimpleNamespace(principal_remaining=10.0, pmt_per_tick=1.0)],
    )
    e.firms, e.firm_lookup = [firm], {4: firm}
    loan = e.bank.originate_loan("firm", 4, 20, 0, 10)
    loan["payment_per_tick"] = 4.0
    preflight_loans(e)
    assert [(cid, amount) for cid, _, amount in firm_exit_claims(e, firm)] == [(loan["claim_id"], 20.0)]
    reserves = e.bank.cash_reserves
    paid, loss = settle_firm_exit_claim(e, firm, loan, 6.0)
    assert (paid, loss) == pytest.approx((6.0, 14.0))
    assert e.bank.cash_reserves == pytest.approx(reserves + 6.0)
    assert e.bank.loan_loss_provision == pytest.approx(14.0)
    assert e.bank.total_loans_outstanding == pytest.approx(0.0)
    assert firm.bank_loan_remaining == pytest.approx(10.0)  # mortgage remains
    assert firm.bank_loan_payment_per_tick == pytest.approx(1.0)
    with pytest.raises(ValueError, match="already settled"):
        settle_firm_exit_claim(e, firm, loan, 0.0)


def test_firm_exit_treasury_claim_recovers_to_treasury_only():
    e = economy()
    firm = SimpleNamespace(
        firm_id=8, cash_balance=3.0, bank_loan_remaining=10.0,
        bank_loan_payment_per_tick=1.0,
        service_infrastructure_loan_remaining=0.0,
        service_infrastructure_loan_payment_per_tick=0.0,
        housing_active_loans=[],
    )
    e.firms, e.firm_lookup = [firm], {8: firm}
    loan = e.bank.issue_government_backed_loan("firm", 8, 10, 0, 10, e.government)
    loan["payment_per_tick"] = 1.0
    preflight_loans(e)
    before_treasury, before_reserves = e.government.cash_balance, e.bank.cash_reserves
    assert settle_firm_exit_claim(e, firm, loan, 3) == pytest.approx((3, 7))
    assert e.government.cash_balance == pytest.approx(before_treasury + 3)
    assert e.bank.cash_reserves == pytest.approx(before_reserves)
    assert e.bank.government_loan_writeoffs == pytest.approx(7)


def test_new_contract_uses_shifted_fixed_quote_and_existing_fee_remains_frozen():
    hh = household(1)
    e = economy(hh)
    e.config = SimpleNamespace(time=SimpleNamespace(ticks_per_year=26),
                               payment_annual_quote_shift=0.02,
                               payment_debt_service_share=0.35)
    old = legacy(e, hh, 10, 1)
    old_rate, old_remaining = old["rate"], old["remaining"]
    assert quoted_annual_rate(e, 0.03) == pytest.approx(0.05)
    claim = originate_v2(e, "household", 1, 20, 0.03, 26, "consumption")
    assert claim is not None
    assert claim["rate"] == pytest.approx(0.05)
    assert claim["first_due_tick"] == 1
    assert claim["ticks_per_year"] == 26
    assert old["rate"] == old_rate
    assert old["remaining"] == old_remaining
    assert hh.consumption_loan_remaining == pytest.approx(30)
    e.current_tick = 1
    prepare_household_dues(e)
    assert claim["accrued_interest"] == pytest.approx(20 * 0.05 / 26)
    assert old["remaining"] == old_remaining  # v1 fee remains frozen until paid


def test_underwriting_deducts_existing_scheduled_payment_once_and_uses_prior_net():
    hh = household(1, cash=1000)
    e = economy(hh)
    existing = legacy(e, hh, 100, 30)
    assert existing["payment_per_tick"] == 30
    # Prior settled net 100, 35% debt-service ceiling: 30 + 5 is allowed.
    assert can_underwrite(e, "household", 1, 5)
    assert not can_underwrite(e, "household", 1, 6)
    # Current cash and future/contract wage never replace missing prior net.
    e.payment_state["prior_settled_household_net"][1] = 0
    assert not can_underwrite(e, "household", 1, 1)


def test_negative_prior_firm_operating_cashflow_denies_without_crashing():
    e = economy()
    firm = SimpleNamespace(firm_id=4, cash_balance=500.0, payment_wage_arrears=0.0,
                           loan_payment_per_tick=0.0, government_loan_remaining=0.0,
                           housing_active_loans=[])
    e.firms = [firm]
    e.firm_lookup = {4: firm}
    e.payment_state["prior_settled_firm_operating_cashflow"] = {4: -175.0}
    assert not can_underwrite(e, "firm", 4, 1.0)


def test_direct_treasury_due_is_counted_once_and_worker_arrears_block_discretionary_credit():
    e = economy()
    firm = SimpleNamespace(firm_id=4, cash_balance=500.0, payment_wage_arrears=0.0,
                           loan_payment_per_tick=20.0, government_loan_remaining=100.0,
                           housing_active_loans=[])
    e.firms = [firm]
    e.firm_lookup = {4: firm}
    e.payment_state["prior_settled_firm_operating_cashflow"] = {4: 100.0}
    assert can_underwrite(e, "firm", 4, 15.0)
    assert not can_underwrite(e, "firm", 4, 16.0)
    firm.payment_wage_arrears = 10.0
    assert not can_underwrite(e, "firm", 4, 1.0, purpose="investment")
    assert can_underwrite(e, "firm", 4, 1.0, purpose="working_capital")


def test_rent_arrears_or_recent_loan_miss_blocks_new_household_credit():
    hh = household(1)
    e = economy(hh)
    hh.rent_arrears = 2.0
    assert not can_underwrite(e, "household", 1, 1.0)
    hh.rent_arrears = 0.0
    old = legacy(e, hh, 20, 2)
    old["missed_payments"] = 1
    e.payment_book.loan_state = {}
    assert not can_underwrite(e, "household", 1, 1.0)


@pytest.mark.parametrize("threshold", [4, 8, 12])
def test_v2_firm_default_history_discharge_and_cooldown(threshold):
    e = economy()
    e.config = SimpleNamespace(time=SimpleNamespace(ticks_per_year=52),
                               payment_annual_quote_shift=0.0,
                               payment_debt_service_share=0.35,
                               payment_firm_default_misses=threshold,
                               payment_default_cooldown_ticks=26)
    firm = SimpleNamespace(firm_id=4, cash_balance=0.0, bank_loan_principal=0.0,
                           bank_loan_remaining=0.0, bank_loan_payment_per_tick=0.0,
                           service_infrastructure_loan_remaining=0.0,
                           service_infrastructure_loan_payment_per_tick=0.0,
                           housing_active_loans=[])
    e.firms = [firm]
    e.firm_lookup = {4: firm}
    e.payment_state["prior_settled_firm_operating_cashflow"] = {4: 1000.0}
    claim = originate_v2(e, "firm", 4, 52, 0.05, 52, "working_capital")
    assert claim is not None
    for tick in range(1, threshold + 1):
        e.current_tick = tick
        assert collect_firm_dues(e) == 0
    assert claim["remaining"] == 0
    assert firm.bank_loan_remaining == 0
    history = e.payment_state["loan_default_history"]
    assert len(history) == 1
    assert history[0]["contract_version"] == 2
    assert history[0]["borrower_discharge"] == pytest.approx(history[0]["written_off"])
    assert not can_underwrite(e, "firm", 4, 0.1)
    e.current_tick = threshold + 26
    assert can_underwrite(e, "firm", 4, 0.1)
    originate_v2,
    quoted_annual_rate,
