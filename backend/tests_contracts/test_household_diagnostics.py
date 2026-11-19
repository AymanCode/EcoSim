"""Event diagnostics and revision-5 analysis checks; income_first only."""
import copy
import io
import json
from types import SimpleNamespace

import pytest

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import clone_config, use_config
from economy import Economy
from payment_loans import collect_household_dues, originate_v2, prepare_household_dues
from payment_sectors import enqueue_payment_care_requests, settle_payment_care, settle_payment_rent
from payments import PaymentBook
from tools.analysis import household_experiment as runner
from tools.analysis import household_experiment_summary as summary
from tools.runners.run_large_simulation import create_large_economy


@pytest.fixture(autouse=True)
def income_first():
    config = clone_config()
    config.payment_sequence = "income_first"
    config.payment_care_request_slope = 1.0
    with use_config(config):
        yield config


def make_economy(households, firms, bank=True):
    gov = GovernmentAgent(cash_balance=1_000_000.0)
    eco = Economy(households, firms, gov, bank=BankAgent(cash_reserves=10_000.0) if bank else None)
    eco.payment_book = PaymentBook(eco, "income_first")
    return eco


def household(hid, cash=0):
    return HouseholdAgent(household_id=hid, skills_level=0.6, age=30, cash_balance=cash)


def firm(fid, category, cash=0, price=10):
    return FirmAgent(firm_id=fid, good_name=category, good_category=category,
                     cash_balance=cash, inventory_units=0, price=price)


def test_opened_episode_counts_even_when_deferred_and_retry_admission(monkeypatch):
    patient = household(1)
    patient.health = 0.8
    clinic = firm(8, "Healthcare", price=100)
    eco = make_economy([patient], [clinic])
    monkeypatch.setattr(eco, "_choose_healthcare_provider", lambda h, firms: clinic)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda self, tick, salt: 0.0 if salt == 17 else 0.99)
    before = (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance)
    enqueue_payment_care_requests(eco)
    assert eco.care_episodes_opened_this_tick == 1
    assert eco.care_visits_scheduled_this_tick == patient.pending_healthcare_visits > 0
    assert eco.payment_care_deferrals_this_tick == 1
    assert eco.healthcare_requests_this_tick == eco.care_queue_admissions_retry_this_tick == 0
    assert not clinic.healthcare_queue
    assert (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance) == before

    # A due retry accepted through enqueue is counted separately, not reopened.
    patient.payment_care_due_retry = True
    patient.payment_care_accepted_quote = 100.0
    enqueue_payment_care_requests(eco)
    assert clinic.healthcare_queue == [1]
    assert eco.care_episodes_opened_this_tick == 1
    assert eco.healthcare_requests_this_tick == 0
    assert eco.care_queue_admissions_retry_this_tick == 1
    assert (patient.cash_balance, clinic.cash_balance, eco.bank.cash_reserves, eco.government.cash_balance) == before


def test_completion_and_public_support_are_recorded_only_after_success(monkeypatch):
    patient = household(1)
    patient.health = 0.5
    patient.pending_healthcare_visits = 1
    patient.pending_visit_heal_delta = 0.2
    patient.payment_care_due_tick = 0
    patient.payment_care_accepted_quote = 25.0
    patient.queued_healthcare_firm_id = 8
    clinic = firm(8, "Healthcare", price=25)
    clinic.healthcare_queue = [1]
    eco = make_economy([patient], [clinic])
    eco.payment_care_mode = "covered"
    eco.payment_care_remaining = 25
    eco.payment_state["restrictions"]["care"] = 25
    monkeypatch.setattr("payment_sectors._qualified_capacity", lambda e, f: 1.0)
    monkeypatch.setattr(eco, "_prioritize_healthcare_queue", lambda f: None)
    before = eco.government.cash_balance
    settle_payment_care(eco, eco.payment_book.receipts)
    assert eco.healthcare_completed_visits_this_tick == 1
    assert eco.care_visit_slots_this_tick == 1
    assert eco.healthcare_support_this_tick == {8: {"subsidies": 25}}
    assert eco.government.cash_balance == before - 25
    assert eco.payment_book.clearing_cash == 25
    assert patient.cash_balance == clinic.cash_balance == 0


def test_new_admission_uses_existing_counter(monkeypatch):
    patient = household(1)
    patient.health = 0.2
    clinic = firm(8, "Healthcare", price=25)
    eco = make_economy([patient], [clinic])
    monkeypatch.setattr(eco, "_choose_healthcare_provider", lambda h, firms: clinic)
    monkeypatch.setattr(HouseholdAgent, "_deterministic_unit_random", lambda *args, **kwargs: 0.0)
    enqueue_payment_care_requests(eco)
    assert eco.care_episodes_opened_this_tick == eco.healthcare_requests_this_tick == 1
    assert eco.care_queue_admissions_retry_this_tick == 0
    assert clinic.healthcare_queue == [1]


def test_new_tick_resets_diagnostics_before_events(monkeypatch):
    eco = create_large_economy(20, 1)
    names = ("care_episodes_opened_this_tick", "care_visits_scheduled_this_tick",
             "care_queue_admissions_retry_this_tick", "care_visit_slots_this_tick")
    for name in names:
        setattr(eco, name, 999)
    eco.evicted_household_ids_this_tick = [999]
    eco.household_loan_writeoffs_this_tick = {"consumption": 999}
    eco.household_unpaid_dues_this_tick = {999: 999}
    eco.healthcare_support_this_tick = {999: {"bank_loans": 999}}
    observed = []

    def check_reset():
        observed.append(([getattr(eco, name) for name in names], list(eco.evicted_household_ids_this_tick),
                         dict(eco.household_loan_writeoffs_this_tick), dict(eco.household_unpaid_dues_this_tick),
                         dict(eco.healthcare_support_this_tick)))

    monkeypatch.setattr(eco, "_apply_random_shocks", check_reset)
    eco.step()
    assert observed == [([0, 0, 0, 0], [], {}, {}, {})]


def test_both_evictions_capture_ids_without_moving_cash():
    missing, notice = household(1), household(2)
    missing.renting_from_firm_id, missing.monthly_rent = 999, 10
    notice.renting_from_firm_id, notice.monthly_rent = 2, 10
    notice.rent_arrears, notice.rent_notice_remaining = 5, 1
    landlord = firm(2, "Housing", cash=50)
    landlord.max_rental_units = 2
    landlord.current_tenants = [2]
    eco = make_economy([missing, notice], [landlord])
    before = (missing.cash_balance, notice.cash_balance, landlord.cash_balance, eco.government.cash_balance)
    settle_payment_rent(eco)
    assert eco.last_housing_diagnostics["eviction_count"] == 2
    assert eco.evicted_household_ids_this_tick == [1, 2]
    assert (missing.cash_balance, notice.cash_balance, landlord.cash_balance, eco.government.cash_balance) == before


def test_writeoffs_by_subtype_and_unpaid_due_after_partial_collection(monkeypatch):
    partial, default, medical = household(1, 4), household(2, 1), household(3, 0)
    eco = make_economy([partial, default, medical], [])
    monkeypatch.setattr("payment_loans.can_underwrite", lambda *a, **kw: True)
    for h, subtype in ((partial, "consumption"), (default, "consumption"), (medical, "medical")):
        claim = originate_v2(eco, "household", h.household_id, 100, 0, 10, subtype)
        assert claim is not None
        if h is not partial:
            claim["missed_payments"] = 7
    eco.current_tick = 1
    eco.payment_book = PaymentBook(eco, "income_first")
    assert prepare_household_dues(eco) == {1: 10, 2: 10, 3: 10}
    before = eco.bank.cash_reserves
    assert collect_household_dues(eco) == 5
    assert eco.bank.cash_reserves == before + 5
    assert eco.household_loan_writeoffs_this_tick == {"consumption": 1, "medical": 1}
    assert eco.household_unpaid_dues_this_tick == {1: 6}
    assert [h.cash_balance for h in (partial, default, medical)] == [0, 0, 0]


def test_healthcare_financing_at_bank_government_and_bailout_credits(monkeypatch):
    h, clinic = household(1), firm(8, "Healthcare")
    eco = make_economy([h], [clinic])
    monkeypatch.setattr("payment_loans.can_underwrite", lambda *a, **kw: True)
    monkeypatch.setattr(BankAgent, "_max_firm_borrowable", lambda *a: 1000)
    before_bank = eco.bank.cash_reserves
    assert eco._issue_firm_loan(clinic, 10, 52, 0.03) == 10
    assert (eco.bank.cash_reserves, clinic.cash_balance) == (before_bank - 10, 10)
    monkeypatch.setattr(BankAgent, "can_lend", lambda self: False)
    before_gov = eco.government.cash_balance
    assert eco._issue_firm_loan(clinic, 20, 52, 0.03) == 20
    assert (eco.government.cash_balance, clinic.cash_balance) == (before_gov - 20, 30)
    eco.government.bailout_policy = "all"
    eco.government.bailout_budget_remaining = 1000
    monkeypatch.setattr(eco, "_is_bailout_candidate", lambda f: True)
    monkeypatch.setattr(eco, "_bailout_need_amount", lambda f: 30)
    eco._execute_bailouts()
    assert clinic.cash_balance == 60
    assert eco.government.cash_balance == before_gov - 50
    assert eco.healthcare_support_this_tick == {8: {"bank_loans": 10, "government_loans": 20, "bailouts": 30}}


def test_week26_proxy_uses_unpaid_dues_and_funded_income():
    households = [household(1, 12), household(2, 10), household(3, 100)]
    households[0].bank_deposit = 3
    paid = {1: {"net": 10, "benefit": 0}, 2: {"net": 7, "benefit": 3}, 3: {"net": 0, "benefit": 0}}
    assert runner.hand_to_mouth_counts(households, paid, {1: 6}) == {
        "hand_to_mouth": 1, "not_hand_to_mouth": 1, "zero_income": 1}


def synthetic_run(ticks=52):
    firms = {"8": {key: 0 for key in summary.REQUIRED_FIRM}}
    firms["8"].update(active=True, cash=100)
    row = {key: 0 for key in summary.REQUIRED_ROWS}
    row.update(healthcare_firms=firms, evicted_household_ids=[], household_loan_writeoffs={},
               household_unpaid_dues={str(i): 0 for i in range(200)})
    return {"schema_version": summary.SCHEMA_VERSION, "opening": {"household_cash_total": 1,
            "cash_gini": 0, "cash_median": 0, "cash_below_40_share": 0,
            "id_skill_spearman": 0, "doctor_opening_capacity": 1, "healthcare_firms": {}},
            "health_spells": [], "hand_to_mouth_week_26": {"hand_to_mouth": 0, "not_hand_to_mouth": 0, "zero_income": 200},
            "money_tick0": 1, "seed": 42, "sequence": "income_first", "households": 200, "ticks": ticks,
            "arm": "control", "overrides": {}, "levers": {},
            "rows": [dict(copy.deepcopy(row), t=i) for i in range(1, ticks + 1)]}


def write(path, run):
    path.write_text(json.dumps(run), encoding="utf-8")


def test_cache_reuses_only_valid_current_complete_outputs(tmp_path, monkeypatch):
    output, plan = tmp_path / "cached.json", tmp_path / "plan.json"
    job = {"out": str(output), "seed": 42, "arm": "control"}
    args = SimpleNamespace(plan=str(plan), backend="unused", jobs=1, households=200)
    write(plan, {"ticks": 2, "jobs": [job]})
    run = synthetic_run(2)
    write(output, run)
    calls = []

    class FakeProcess:
        returncode = 0
        stdout = io.StringIO("done\n")
        def __init__(self, *args, **kwargs):
            calls.append(args[0])
        def poll(self):
            return 0

    monkeypatch.setattr(runner.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    runner.batch(args)
    assert calls == []
    assert not runner._cache_valid(output, ticks=2, households=201, job=job)
    monkeypatch.setattr(summary, "EXP", tmp_path)
    with pytest.raises(ValueError, match="weekly rows"):
        summary.load("cached")  # The standard summary requires 312 weeks.
    variants = [dict(run, schema_version=0), dict(run, rows=run["rows"][:-1]),
                dict(run, rows=[dict(run["rows"][0], t=2), run["rows"][1]])]
    missing = copy.deepcopy(run)
    del missing["rows"][0]["care_queue_admissions_retry"]
    variants.append(missing)
    missing_firm = copy.deepcopy(run)
    del missing_firm["rows"][0]["healthcare_firms"]["8"]["subsidies"]
    variants.append(missing_firm)
    for invalid in variants:
        write(output, invalid)
        with pytest.raises(ValueError):
            summary.read_run(output, expected_ticks=2)
        runner.batch(args)
    assert len(calls) == len(variants)


@pytest.mark.parametrize("control,treatment,threshold,halt", [
    (0, 5, "c=0", False), (0, 6, "c=0", True),
    (10, 20, "2c", False), (10, 21, "2c", True),
    (100, 150, "excess", False), (100, 151, "excess", True),
])
@pytest.mark.parametrize("rule", ["eviction_events", "evicted_households", "consumption_loan_defaults:consumption"])
def test_count_halt_rules(tmp_path, rule, control, treatment, threshold, halt):
    runs = [synthetic_run(), synthetic_run()]
    for data, value in zip(runs, (control, treatment)):
        if rule.startswith("evict"):
            data["rows"][0]["evictions"] = value
            data["rows"][0]["evicted_household_ids"] = list(range(value))
        else:
            data["rows"][0]["household_loan_writeoffs"] = {"consumption": value}
    control_path, treatment_path = tmp_path / "control.json", tmp_path / "treatment.json"
    write(control_path, runs[0])
    write(treatment_path, runs[1])
    result = summary.evaluate_plan2_halt_rules(treatment_path, control_path)["rules"][rule]
    assert (result["treatment"], result["control"], result["threshold"], result["halt"]) == (treatment, control, threshold, halt)
    assert result["reason"]


def test_healthcare_and_unemployment_halt_rules(tmp_path):
    control, treatment = synthetic_run(), synthetic_run()
    treatment["rows"][5]["healthcare_firms"]["8"]["cash"] = -0.01
    for row in treatment["rows"][26:]:
        row["u"] = 0.101
    cp, tp = tmp_path / "control.json", tmp_path / "treatment.json"
    write(cp, control)
    write(tp, treatment)
    result = summary.evaluate_plan2_halt_rules(tp, cp)
    assert result["halt"]
    assert set(result["reasons"]) == {"healthcare_cash", "unemployment"}
    for name in ("healthcare_cash", "unemployment"):
        assert result["rules"][name]["threshold"] and result["rules"][name]["reason"]
