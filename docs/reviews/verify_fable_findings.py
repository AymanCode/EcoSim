"""Bounded audit probes for the September 2026 Fable review.

Run from the repository root:
    PYTHONPATH=backend python3 -B docs/reviews/verify_fable_findings.py

By default these assertions verify W01/W02 corrections and retain E08–E10.
Use --expect-baseline-bugs only with the archived source at commit 4f69389.
Historical pre-fix results remain in ECONOMIC_MODEL_AUDIT_PROBE_RESULTS.json.
No provider calls, persisted simulation runs, or economic-source edits occur.
"""

import argparse
import contextlib
import io
import json
import math
import random

import numpy as np

from agents import GovernmentAgent
from config import clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy


def economy():
    random.seed(42)
    np.random.seed(42)
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(200, 2)


def emit(evidence, **values):
    print(json.dumps({"evidence": evidence, **values}), flush=True)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--expect-baseline-bugs", action="store_true")
expect_bugs = parser.parse_args().expect_baseline_bugs

cfg = clone_config()
cfg.random_seed = 42
cfg.llm.enable_llm_government = False

with use_config(cfg):
    # E06: a repayment reduces borrower cash without crediting its funder.
    eco = economy()
    bank, gov, firm = eco.bank, eco.government, eco.firms[0]
    bank.active_loans.clear()
    bank.total_loans_outstanding = 0.0
    gov.cash_balance = 5000.0
    firm.cash_balance = 1000.0
    loan = bank.issue_government_backed_loan(
        "firm", firm.firm_id, 100.0, 0.10, 10, gov
    )
    assert loan is not None
    firm.cash_balance += 100.0
    firm.bank_loan_remaining = loan["remaining"]
    before = (firm.cash_balance, bank.cash_reserves, gov.cash_balance)
    eco._collect_bank_loan_repayments()
    after = (firm.cash_balance, bank.cash_reserves, gov.cash_balance)
    assert math.isclose(before[0] - after[0], 11.0)
    assert after[1] == before[1]
    assert math.isclose(after[2] - before[2], 0.0 if expect_bugs else 11.0, abs_tol=1e-9)
    emit("E06", borrower_cash_decrease=before[0] - after[0],
         bank_cash_change=after[1] - before[1],
         government_cash_change=after[2] - before[2],
         loan_remaining=loan["remaining"])

    # E07: one bank medical loan is serviced through two settlement paths.
    eco = economy()
    bank, gov, household = eco.bank, eco.government, eco.households[0]
    bank.active_loans.clear()
    bank.total_loans_outstanding = 0.0
    bank.cash_reserves = 1_000_000.0
    bank.total_deposits = 0.0
    household.cash_balance = 1000.0
    household.employer_id = None
    household.wage = 0.0
    household.medical_loan_remaining = 0.0
    for firm in eco.firms:
        firm.government_loan_remaining = 0.0
        firm.ceo_household_id = None
    assert eco._issue_medical_loan(household, 520.0)
    loan = bank.active_loans[-1]
    original_remaining = loan["remaining"]
    cash_before = household.cash_balance
    bank_before = bank.cash_reserves
    gov_before = gov.cash_balance
    eco._collect_bank_loan_repayments()
    scheduled_payment = cash_before - household.cash_balance
    bank_loan_after_first_path = loan["remaining"]
    eco._batch_apply_household_updates({}, {}, {})
    extra_payment = gov.cash_balance - gov_before
    assert scheduled_payment > 0.0
    assert extra_payment > 0.0 if expect_bugs else math.isclose(extra_payment, 0.0, abs_tol=1e-9)
    assert math.isclose(bank.cash_reserves - bank_before, scheduled_payment)
    assert loan["remaining"] == bank_loan_after_first_path
    assert math.isclose(loan["remaining"] - household.medical_loan_remaining,
                        extra_payment)
    assert math.isclose(cash_before - household.cash_balance,
                        scheduled_payment + extra_payment)
    emit("E07", original_loan_remaining=original_remaining,
         scheduled_bank_payment=scheduled_payment,
         additional_treasury_payment=extra_payment,
         bank_loan_remaining=loan["remaining"],
         household_loan_remaining=household.medical_loan_remaining)

    # E08: check the surplus threshold precisely, not just its reserve value.
    payouts = {}
    for balance in (55000.0, 60000.0, 65000.0):
        payouts[str(int(balance))] = GovernmentAgent(
            cash_balance=balance
        ).make_investments()["bonds"]
    assert list(payouts.values()) == [0.0, 0.0, 1800.0]
    emit("E08", surplus_payout_by_starting_treasury_cash=payouts)

    # E09: baseline providers receive private household owner IDs in this factory.
    eco = economy()
    baseline = [firm for firm in eco.firms if firm.is_baseline]
    assert baseline and all(firm.owners for firm in baseline)
    assert all(owner in eco.household_lookup
               for firm in baseline for owner in firm.owners)
    emit("E09", baseline_firms=len(baseline),
         baseline_firms_with_household_owners=len(baseline))

    # E10: this is a price plan, not a measurement of realized CPI inflation.
    firm = next(firm for firm in eco.queued_firms if not firm.is_baseline)
    firm.price = 100.0
    firm.stabilization_disabled = True
    plan = firm.plan_pricing(0.5, 0.1, in_warmup=False)
    assert math.isclose(plan["price_next"], 102.0)
    emit("E10", current_price=100.0, planned_next_price=plan["price_next"])
