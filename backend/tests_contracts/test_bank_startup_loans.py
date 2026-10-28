"""Bank startup eligibility and composed entry transactions."""
import asyncio

import pytest
from pydantic import ValidationError

from agents import BankAgent
from config import SimulationConfig, clone_config, use_config
from economy import Economy
from payment_loans import collect_firm_dues, originate_v2
from payments import PaymentBook
from server import SetupConfig, SimulationManager


@pytest.fixture(params=["income_first", "income_late"])
def world(factory, request):
    cfg = clone_config()
    cfg.payment_sequence = request.param
    cfg.payment_bank_startup_loans_enabled = True
    with use_config(cfg):
        hh = factory.household(household_id=1, cash_balance=0.0)
        firm = factory.firm(firm_id=91, category="Food", is_baseline=False, cash_balance=10_000.0)
        bank = BankAgent(cash_reserves=100_000.0)
        ec = Economy([hh], [], factory.government(), bank=bank, queued_firms=[firm])
        ec.payment_book = PaymentBook(ec, timing=request.param)
        ec.current_tick = 11
        ec.in_warmup = False
        yield ec, firm, bank


def test_origination_and_single_use_after_payoff(world):
    ec, firm, bank = world
    treasury = ec.government.cash_balance
    assert ec._fund_private_startup(firm, 25_000, 208)
    assert firm.cash_balance == 35_000
    assert bank.cash_reserves == 75_000
    assert ec.government.cash_balance == treasury
    claim = bank.active_loans[0]
    assert (claim["subtype"], claim["funder"], claim["principal_remaining"]) == ("startup", "bank", 25_000)
    assert firm.startup_loan_originated and not firm.startup_loan_entitled
    assert firm.firm_id not in ec.firm_lookup
    ec.firms.append(firm)
    ec.firm_lookup[firm.firm_id] = firm
    ec.current_tick += 1
    paid = collect_firm_dues(ec)
    interest = 25_000 * claim["rate"] / 52
    assert paid == pytest.approx(claim["payment_per_tick"])
    assert claim["principal_remaining"] == pytest.approx(25_000 - paid + interest)
    claim["principal_remaining"] = claim["remaining"] = 0
    firm.bank_loan_remaining = 0
    assert not ec._fund_private_startup(firm, 1_000, 10)
    assert len(bank.active_loans) == 1


@pytest.mark.parametrize("denial", ["entitlement", "age", "baseline", "registered_baseline", "public", "history", "treasury_debt", "bank_debt", "score", "cooldown", "arrears", "reserves", "limit", "term"])
def test_denials_leave_no_cash_or_claim(world, denial):
    ec, firm, bank = world
    ec.firm_lookup[firm.firm_id] = firm
    firm.startup_loan_entitled = True
    amount, term = 20_000, 156
    if denial == "entitlement": firm.startup_loan_entitled = False
    if denial == "age": firm.age_in_ticks = 1
    if denial == "baseline": firm.is_baseline = True
    if denial == "registered_baseline": ec.government.register_baseline_firm("Food", firm.firm_id)
    if denial == "public": firm.good_category = "PublicWorks"
    if denial == "history": ec.payment_state["prior_settled_firm_operating_cashflow"] = {firm.firm_id: 0.0}
    if denial == "treasury_debt": firm.government_loan_remaining = 1
    if denial == "bank_debt": firm.bank_loan_remaining = 1
    if denial == "score": bank.firm_credit_scores[firm.firm_id] = 0.24
    if denial == "cooldown": ec.payment_state["loan_credit_cooldown_until"] = {("firm", firm.firm_id): 12}
    if denial == "arrears": firm.payment_wage_arrears = 1
    if denial == "reserves": bank.cash_reserves = 10
    if denial == "limit": amount = 30_001
    if denial == "term": term = 209
    before = (firm.cash_balance, bank.cash_reserves, ec.government.cash_balance)
    assert originate_v2(ec, "firm", firm.firm_id, amount, .05, term, "startup") is None
    assert (firm.cash_balance, bank.cash_reserves, ec.government.cash_balance) == before
    assert not bank.active_loans and not firm.startup_loan_originated


def test_rejects_treasury_and_nonfinite(world):
    ec, firm, _ = world
    ec.firm_lookup[firm.firm_id] = firm
    firm.startup_loan_entitled = True
    with pytest.raises(ValueError):
        originate_v2(ec, "firm", firm.firm_id, 100, .03, 10, "startup", funder="treasury", authorized_treasury=True)
    with pytest.raises(ValueError):
        originate_v2(ec, "firm", firm.firm_id, float("nan"), .03, 10, "startup")
    assert not ec.bank.active_loans


def test_queued_activation_refusal_keeps_endowment_without_treasury(world):
    ec, firm, bank = world
    bank.cash_reserves = 0
    ec.target_total_firms = 10
    treasury = ec.government.cash_balance
    ec._activate_queued_firms()
    assert firm in ec.firms and firm.cash_balance == 10_000
    assert ec.government.cash_balance == treasury
    assert not bank.active_loans and not firm.startup_loan_originated


def test_queued_activation_funds_once(world):
    ec, firm, bank = world
    ec.target_total_firms = 10
    ec._activate_queued_firms()
    assert firm in ec.firms and firm.cash_balance == 35_000
    assert bank.cash_reserves == 75_000 and len(bank.active_loans) == 1


def test_setup_bool_lock_and_snapshot():
    with pytest.raises(ValidationError): SetupConfig(payment_bank_startup_loans_enabled="false")
    with pytest.raises(ValueError): SimulationConfig(payment_bank_startup_loans_enabled=1)
    first, second = SimulationManager(session_id="startup-1"), SimulationManager(session_id="startup-2")
    first.initialize({"num_households": 3, "num_firms": 1, "payment_sequence": "income_first", "payment_bank_startup_loans_enabled": False})
    second.initialize({"num_households": 3, "num_firms": 1, "payment_sequence": "income_late"})
    assert not first.economy.payment_config_snapshot["payment_bank_startup_loans_enabled"]
    assert second.economy.payment_config_snapshot["payment_bank_startup_loans_enabled"]
    with pytest.raises(ValueError, match="fixed at SETUP"):
        asyncio.run(first.update_config({"payment_bank_startup_loans_enabled": True}))

class FixedTier:
    def __init__(self, roll):
        self.roll = roll
    def random(self):
        return self.roll
    def choice(self, values):
        return values[0]
    def randint(self, low, high):
        return low
    def uniform(self, low, high):
        return (low + high) / 2


@pytest.mark.parametrize("roll,principal", [(0.01, 30_000), (0.20, 20_000), (0.99, 0)])
def test_recurring_entry_bank_and_founder_routes(world, monkeypatch, roll, principal):
    ec, _, bank = world
    monkeypatch.setattr("economy.random.Random", lambda _: FixedTier(roll))
    ec.queued_firms.clear()
    ec.target_total_firms = 10
    ec.households[0].cash_balance = 40_000
    before = ec.households[0].cash_balance
    ec._maybe_create_new_firms()
    firm = ec.firms[0]
    if principal:
        assert firm.cash_balance == principal
        assert bank.cash_reserves == 100_000 - principal
        assert before == ec.households[0].cash_balance
        assert bank.active_loans[0]["principal"] == principal
    else:
        assert firm.cash_balance == 5_000
        assert before - ec.households[0].cash_balance == 5_000
        assert firm.owners == [1]
        assert not bank.active_loans


def test_failed_recurring_entry_is_atomic_and_id_not_consumed(world, monkeypatch):
    ec, _, bank = world
    monkeypatch.setattr("economy.random.Random", lambda _: FixedTier(.01))
    ec.queued_firms.clear()
    ec.target_total_firms = 10
    bank.cash_reserves = 0
    before_id = ec._next_private_firm_id
    treasury = ec.government.cash_balance
    ec._maybe_create_new_firms()
    assert not ec.firms and not ec.firm_lookup and not bank.active_loans
    assert ec._next_private_firm_id == before_id
    assert ec.government.cash_balance == treasury and ec.households[0].cash_balance == 0
    ec.households[0].cash_balance = 6_000
    ec._maybe_create_new_firms()
    assert ec.firms[0].firm_id == before_id
    assert ec.firms[0].cash_balance == 5_000 and ec.households[0].cash_balance == 1_000
    assert ec.firms[0].owners == [1]


def test_committed_private_id_not_reused_after_exit(world, monkeypatch):
    ec, _, bank = world
    monkeypatch.setattr("economy.random.Random", lambda _: FixedTier(.01))
    ec.queued_firms.clear()
    ec.target_total_firms = 10
    ec._maybe_create_new_firms()
    old = ec.firms.pop()
    del ec.firm_lookup[old.firm_id]
    bank.firm_credit_scores[old.firm_id] = 0
    ec.payment_state["loan_credit_cooldown_until"] = {("firm", old.firm_id): 999}
    ec._maybe_create_new_firms()
    assert ec.firms[0].firm_id > old.firm_id
    assert ec.firms[0].startup_loan_originated


def test_partial_then_default_writes_off_without_extra_cash(world):
    ec, firm, bank = world
    assert ec._fund_private_startup(firm, 20_000, 156)
    ec.firms.append(firm)
    ec.firm_lookup[firm.firm_id] = firm
    firm.cash_balance = 1
    claim = bank.active_loans[0]
    ec.current_tick += 1
    reserves = bank.cash_reserves
    assert collect_firm_dues(ec) == pytest.approx(1)
    assert bank.cash_reserves == pytest.approx(reserves + 1)
    assert claim["missed_payments"] == 1 and claim["term_remaining"] == 156
    for _ in range(7):
        ec.current_tick += 1
        collect_firm_dues(ec)
    assert claim["principal_remaining"] == 0
    assert bank.cash_reserves == pytest.approx(reserves + 1)
    assert bank.loan_loss_provision > 0



def test_ordinary_product_still_requires_history(world):
    ec, firm, bank = world
    ec.firm_lookup[firm.firm_id] = firm
    firm.startup_loan_entitled = True
    assert originate_v2(ec, "firm", firm.firm_id, 1_000, .05, 52, "investment") is None
    assert not bank.active_loans


def test_no_bank_fallback_to_founder(world, monkeypatch):
    ec, _, _ = world
    monkeypatch.setattr("economy.random.Random", lambda _: FixedTier(.01))
    ec.queued_firms.clear()
    ec.target_total_firms = 10
    ec.bank = None
    ec.households[0].cash_balance = 40_000
    treasury = ec.government.cash_balance
    ec._maybe_create_new_firms()
    assert ec.firms[0].cash_balance == 30_000
    assert ec.households[0].cash_balance == 10_000
    assert ec.government.cash_balance == treasury


@pytest.mark.parametrize("sequence,enabled", [("income_first", False), ("income_late", False), ("legacy", True)])
def test_old_queued_route_when_disabled_or_legacy(factory, sequence, enabled, monkeypatch):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    cfg.payment_bank_startup_loans_enabled = enabled
    with use_config(cfg):
        firm = factory.firm(firm_id=91, category="Food", is_baseline=False, cash_balance=10_000)
        ec = Economy([factory.household(household_id=1)], [], factory.government(),
                     bank=BankAgent(cash_reserves=100_000), queued_firms=[firm])
        ec.target_total_firms = 10
        calls = []
        monkeypatch.setattr(ec, "_issue_firm_loan", lambda *args, **kwargs: calls.append((args, kwargs)))
        ec._activate_queued_firms()
        assert len(calls) == 1 and calls[0][1]["amount"] == 25_000
        assert not firm.startup_loan_originated

@pytest.mark.parametrize("amount,term", [(0, 10), (30_001, 10), (100, 0), (100, 209), (100, 1.5), (100, True)])
def test_startup_amount_and_term_bounds(world, amount, term):
    ec, firm, bank = world
    ec.firm_lookup[firm.firm_id] = firm
    firm.startup_loan_entitled = True
    assert originate_v2(ec, "firm", firm.firm_id, amount, .05, term, "startup") is None
    assert not bank.active_loans


def test_can_lend_circuit_breaker_denies(world, monkeypatch):
    ec, firm, bank = world
    monkeypatch.setattr(BankAgent, "can_lend", lambda self: False)
    assert not ec._fund_private_startup(firm, 20_000, 156)
    assert firm.cash_balance == 10_000 and bank.cash_reserves == 100_000



def test_startup_full_principal_must_fit_lendable_reserves_even_below_tolerance(world):
    ec, firm, bank = world
    bank.cash_reserves = 20_000 - 0.0000005
    assert not ec._fund_private_startup(firm, 20_000, 156)
    assert bank.cash_reserves == 20_000 - 0.0000005
    assert firm.cash_balance == 10_000 and not bank.active_loans
