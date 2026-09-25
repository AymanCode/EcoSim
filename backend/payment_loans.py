"""Versioned, cash-backed loan settlement for the PS3.1 payment arm.

The bank ledger is the sole owner of registered claims.  Household and firm
debt fields are compatibility mirrors, never additional creditors.  Housing
``LoanContract`` mortgages and direct firm-to-government loans have different
owners and are deliberately outside this collector.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

TOL = 1e-6


def _finite(value: Any, name: str, *, nonnegative: bool = True) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(number) or (nonnegative and number < -TOL):
        raise ValueError(f"{name} must be finite and nonnegative")
    return max(0.0, number) if nonnegative else number


def _version(loan: dict) -> int:
    version = loan.get("contract_version", 1)
    if version not in (1, 2):
        raise ValueError(f"Unsupported loan contract version: {version!r}")
    return version


def _id(loan: dict) -> str:
    return str(loan["claim_id"])


def _funder(loan: dict) -> str:
    funder = loan.get("funder", "treasury" if loan.get("govt_backed") else "bank")
    if funder not in ("bank", "treasury"):
        raise ValueError(f"Unknown loan funder: {funder!r}")
    if bool(loan.get("govt_backed", False)) != (funder == "treasury"):
        raise ValueError(f"Inconsistent funder for claim {_id(loan)}")
    return funder


def _remaining(loan: dict) -> float:
    if _version(loan) == 1:
        return _finite(loan["remaining"], "legacy remaining")
    return _finite(loan["principal_remaining"], "principal remaining") + _finite(
        loan.get("accrued_interest", 0.0), "accrued interest"
    )


def _claim_state(economy: Any) -> dict:
    state = getattr(economy, "payment_state", None)
    if state is None:
        state = {}
        economy.payment_state = state
    return state


def _ensure_ids(economy: Any) -> None:
    """Assign stable IDs to old contracts, without resetting their due dates."""
    existing = {str(l["claim_id"]) for l in economy.bank.active_loans if l.get("claim_id") is not None}
    state = _claim_state(economy)
    serial = int(state.get("loan_claim_serial", 0))
    for loan in economy.bank.active_loans:
        if loan.get("claim_id") is not None:
            continue
        while True:
            serial += 1
            claim_id = f"legacy-{serial:012d}"
            if claim_id not in existing:
                break
        loan["claim_id"] = claim_id
        existing.add(claim_id)
    state["loan_claim_serial"] = serial
    state["loan_claim_ids"] = existing
    state["loan_ids_initialized"] = True


def _next_id(economy: Any) -> str:
    state = _claim_state(economy)
    if not state.get("loan_ids_initialized"):
        _ensure_ids(economy)
    serial = int(state.get("loan_claim_serial", 0))
    existing = state["loan_claim_ids"]
    while True:
        serial += 1
        claim_id = f"loan-{serial:012d}"
        if claim_id not in existing:
            state["loan_claim_serial"] = serial
            existing.add(claim_id)
            return claim_id


def _book(economy: Any) -> dict:
    book = getattr(economy, "payment_book", None)
    if book is None:
        book = {}
        economy.payment_book = book
    if isinstance(book, dict):
        return book
    state = getattr(book, "loan_state", None)
    if state is None:
        state = {}
        book.loan_state = state
    return state


def preflight_loans(economy: Any) -> None:
    """Validate registered claims and compatibility mirrors before the arm runs."""
    bank = economy.bank
    if bank is None:
        for hh in economy.households:
            if _finite(getattr(hh, "medical_loan_remaining", 0), "medical mirror") > TOL:
                raise ValueError("Unregistered medical loan without a bank")
        return
    _ensure_ids(economy)
    seen: set[str] = set()
    totals: dict[tuple[str, int, str], float] = defaultdict(float)
    portfolio = 0.0
    for loan in bank.active_loans:
        claim_id = _id(loan)
        if claim_id in seen:
            raise ValueError(f"Duplicate loan claim ID {claim_id}")
        seen.add(claim_id)
        version = _version(loan)
        funder = _funder(loan)
        borrower_type = loan.get("borrower_type")
        if borrower_type not in ("household", "firm"):
            raise ValueError(f"Unknown borrower type for claim {claim_id}")
        borrower_id = loan.get("borrower_id")
        if not isinstance(borrower_id, int):
            raise ValueError(f"Invalid borrower ID for claim {claim_id}")
        if funder == "treasury" and getattr(economy, "government", None) is None:
            raise ValueError(f"Treasury funder missing for claim {claim_id}")
        _finite(loan["payment_per_tick"], "scheduled payment")
        _finite(loan.get("rate", 0), "annual rate")
        _finite(loan.get("missed_payments", 0), "missed payments")
        remaining = _remaining(loan)
        portfolio += remaining
        if version == 2:
            if not isinstance(loan.get("ticks_per_year"), int) or loan["ticks_per_year"] <= 0:
                raise ValueError(f"Missing positive ticks_per_year for claim {claim_id}")
            if not isinstance(loan.get("first_due_tick"), int):
                raise ValueError(f"Missing first due tick for claim {claim_id}")
            last = loan.get("last_accrual_tick")
            if last is not None and not isinstance(last, int):
                raise ValueError(f"Invalid accrual tick for claim {claim_id}")
            if abs(_finite(loan.get("remaining", remaining), "remaining mirror") - remaining) > TOL:
                raise ValueError(f"Inconsistent remaining mirror for claim {claim_id}")
        subtype = loan.get("subtype", "medical" if borrower_type == "household" else "general")
        if borrower_type == "household":
            if subtype not in ("medical", "consumption"):
                raise ValueError(f"Unknown household loan subtype for claim {claim_id}")
            totals[(borrower_type, borrower_id, subtype)] += remaining
        else:
            totals[(borrower_type, borrower_id, "registered")] += remaining
    if abs(_finite(bank.total_loans_outstanding, "bank loan total") - portfolio) > TOL:
        raise ValueError("Bank outstanding total disagrees with registered claims")
    hh_lookup = getattr(economy, "household_lookup", None) or {h.household_id: h for h in economy.households}
    for hh in economy.households:
        for subtype in ("medical", "consumption"):
            mirror = _finite(getattr(hh, f"{subtype}_loan_remaining", 0), f"{subtype} mirror")
            actual = totals[("household", hh.household_id, subtype)]
            if abs(mirror - actual) > TOL:
                raise ValueError(f"Unregistered or inconsistent {subtype} loan mirror for household {hh.household_id}")
    for (borrower_type, borrower_id, _subtype), _amount in totals.items():
        if borrower_type == "household" and borrower_id not in hh_lookup:
            raise ValueError(f"Loan borrower household {borrower_id} missing")
    firm_lookup = getattr(economy, "firm_lookup", None) or {f.firm_id: f for f in economy.firms}
    for firm in economy.firms:
        registered = totals[("firm", firm.firm_id, "registered")]
        mortgage = sum(
            _finite(l.principal_remaining, "mortgage principal")
            for l in (getattr(firm, "housing_active_loans", None) or ())
        )
        mirror = _finite(getattr(firm, "bank_loan_remaining", 0), "firm bank mirror")
        if abs(mirror - registered - mortgage) > TOL:
            raise ValueError(f"Inconsistent bank loan mirror for firm {firm.firm_id}")
    for (borrower_type, borrower_id, subtype), amount in totals.items():
        if borrower_type == "firm" and amount > TOL and borrower_id not in firm_lookup:
            raise ValueError(f"Loan borrower firm {borrower_id} missing")


def _accrue(loan: dict, tick: int, bank: Any) -> None:
    if _version(loan) != 2 or _remaining(loan) <= TOL:
        return
    previous = loan.get("last_accrual_tick")
    if previous is None:
        previous = loan.get("origination_tick", tick - 1)
    if previous > tick:
        raise ValueError(f"Future accrual tick for claim {_id(loan)}")
    # No interest on interest: each elapsed tick charges only live principal.
    elapsed = tick - previous
    if elapsed:
        interest = _finite(loan["principal_remaining"], "principal") * _finite(loan.get("rate", 0), "rate") / loan["ticks_per_year"] * elapsed
        loan["accrued_interest"] = _finite(loan.get("accrued_interest", 0), "interest") + interest
        bank.total_loans_outstanding += interest
        loan["last_accrual_tick"] = tick
        loan["remaining"] = _remaining(loan)


def _due(loan: dict, tick: int, bank: Any) -> float:
    if _version(loan) == 2:
        _accrue(loan, tick, bank)
        if tick < loan["first_due_tick"]:
            return 0.0
    elif tick < loan.get("first_due_tick", -10**12):
        return 0.0
    return min(_finite(loan["payment_per_tick"], "payment"), _remaining(loan))


def prepare_household_dues(economy: Any) -> dict[int, float]:
    """Index each live household claim once at 5b; return summed due by ID."""
    book = _book(economy)
    tick = int(economy.current_tick)
    if book.get("household_due_tick") == tick:
        return book["household_due_totals"]
    bank = economy.bank
    by_household: dict[int, list[tuple[str, dict, float]]] = defaultdict(list)
    totals: dict[int, float] = defaultdict(float)
    if bank is not None:
        _ensure_ids(economy)
        for loan in bank.active_loans:
            if loan.get("borrower_type") != "household":
                continue
            due = _due(loan, tick, bank)
            if due > TOL:
                hid = loan["borrower_id"]
                by_household[hid].append((_id(loan), loan, due))
                totals[hid] += due
    for claims in by_household.values():
        claims.sort(key=lambda item: item[0])
    book["household_due_index"] = dict(by_household)
    book["household_due_totals"] = dict(totals)
    book["household_due_tick"] = tick
    book["household_due_collected"] = False
    payment_book = getattr(economy, "payment_book", None)
    if payment_book is not None and not isinstance(payment_book, dict):
        payment_book.household_due_index = book["household_due_index"]
    return book["household_due_totals"]


def _allocate(claims: list[tuple[str, dict, float]], cash: float) -> list[float]:
    total = sum(due for _, _, due in claims)
    budget = min(max(0.0, cash), total)
    if total <= TOL or budget <= TOL:
        return [0.0] * len(claims)
    share = budget / total
    payments = [min(due, due * share) for _, _, due in claims]
    residue = max(0.0, budget - sum(payments))
    for i, (_, _, due) in enumerate(claims):
        extra = min(residue, due - payments[i])
        payments[i] += extra
        residue -= extra
        if residue <= 0:
            break
    return payments


def _post_payment(economy: Any, loan: dict, payment: float) -> float:
    """Post one actual borrower debit to exactly one funder, interest first for v2."""
    bank = economy.bank
    payment = min(_finite(payment, "loan payment"), _remaining(loan))
    if payment <= TOL:
        return 0.0
    if _version(loan) == 2:
        interest = min(payment, loan.get("accrued_interest", 0.0))
        loan["accrued_interest"] = max(0.0, loan.get("accrued_interest", 0.0) - interest)
        loan["principal_remaining"] = max(0.0, loan["principal_remaining"] - (payment - interest))
        loan["remaining"] = _remaining(loan)
    else:
        # Preserve the frozen full-term fee allocation used by v1.
        interest = payment * _finite(loan.get("interest_income_per_tick", 0), "fee") / max(
            _finite(loan["payment_per_tick"], "payment"), TOL
        )
        loan["remaining"] = max(0.0, loan["remaining"] - payment)
    bank.total_loans_outstanding = max(0.0, bank.total_loans_outstanding - payment)
    bank.last_tick_repayments += payment
    if _funder(loan) == "treasury":
        economy.government.cash_balance += payment
        bank.last_tick_government_repayments += payment
        bank.last_tick_government_interest_income += interest
    else:
        bank.cash_reserves += payment
        bank.last_tick_interest_income += interest
    if _version(loan) == 1 and loan.get("term_remaining", 0) > 0:
        loan["term_remaining"] -= 1
    return payment


def _write_off(economy: Any, loan: dict) -> None:
    bank = economy.bank
    amount = _remaining(loan)
    if amount <= TOL:
        return
    if _funder(loan) == "treasury":
        bank.government_loan_writeoffs += amount
        bank.last_tick_government_defaults += amount
    else:
        bank.loan_loss_provision += amount
    bank.last_tick_defaults += amount
    bank.total_loans_outstanding = max(0.0, bank.total_loans_outstanding - amount)
    if _version(loan) == 2:
        state = _claim_state(economy)
        kind, borrower_id = loan["borrower_type"], loan["borrower_id"]
        cooldown = int(getattr(getattr(economy, "config", None), "payment_default_cooldown_ticks", 26))
        history = state.get("loan_default_history")
        if not isinstance(history, deque):
            history = deque(history or (), maxlen=2048)
            state["loan_default_history"] = history
        history.append({
            "tick": int(economy.current_tick), "claim_id": _id(loan),
            "contract_version": 2, "borrower_type": kind,
            "borrower_id": borrower_id, "funder": _funder(loan),
            "written_off": amount, "borrower_discharge": amount,
        })
        state["loan_default_history_total"] = state.get("loan_default_history_total", 0) + 1
        state["loan_default_history_window"] = "latest_2048_claims"
        state.setdefault("loan_credit_cooldown_until", {})[(kind, borrower_id)] = int(economy.current_tick) + cooldown
    loan["remaining"] = 0.0
    if _version(loan) == 2:
        loan["principal_remaining"] = 0.0
        loan["accrued_interest"] = 0.0
    loan["term_remaining"] = 0


def _sync_mirrors(borrower: Any, claims: list[dict], borrower_type: str) -> None:
    if borrower_type == "household":
        for subtype in ("medical", "consumption"):
            matching = [l for l in claims if l.get("subtype", "medical") == subtype and _remaining(l) > TOL]
            setattr(borrower, f"{subtype}_loan_remaining", sum(_remaining(l) for l in matching))
            setattr(borrower, f"{subtype}_loan_payment_per_tick", sum(_finite(l["payment_per_tick"], "payment") for l in matching))
            if subtype == "medical":
                borrower.medical_loan_principal = sum(
                    l.get("principal_remaining", l.get("principal", 0.0)) for l in matching
                )
                borrower.medical_loan_bank_serviced = bool(matching)
    else:
        mortgages = getattr(borrower, "housing_active_loans", ()) or ()
        borrower.bank_loan_remaining = sum(_remaining(l) for l in claims) + sum(
            _finite(l.principal_remaining, "mortgage principal") for l in mortgages
        )
        borrower.bank_loan_payment_per_tick = sum(
            _finite(l["payment_per_tick"], "payment") for l in claims if _remaining(l) > TOL
        ) + sum(_finite(l.pmt_per_tick, "mortgage payment") for l in mortgages)
        infrastructure = [l for l in claims if l.get("subtype") == "service_infrastructure" and _remaining(l) > TOL]
        borrower.service_infrastructure_loan_remaining = sum(_remaining(l) for l in infrastructure)
        borrower.service_infrastructure_loan_payment_per_tick = sum(l["payment_per_tick"] for l in infrastructure)


def collect_household_dues(economy: Any) -> float:
    """Consume the indexed dues at 6.9, pro rata from actual residual cash."""
    book = _book(economy)
    if book.get("household_due_tick") != int(economy.current_tick):
        raise ValueError("Household dues were not prepared for this tick")
    if book.get("household_due_collected"):
        raise ValueError("Household dues already collected this tick")
    book["household_due_collected"] = True
    bank = economy.bank
    if bank is None:
        return 0.0
    lookup = getattr(economy, "household_lookup", None) or {h.household_id: h for h in economy.households}
    all_claims: dict[int, list[dict]] = defaultdict(list)
    for loan in bank.active_loans:
        if loan.get("borrower_type") == "household":
            all_claims[loan["borrower_id"]].append(loan)
    total_paid = 0.0
    for hid, claims in book["household_due_index"].items():
        hh = lookup.get(hid)
        if hh is None:
            for _, loan, _ in claims:
                _write_off(economy, loan)
            bank.update_household_credit_score(hid, -0.20)
            continue
        cash = max(0.0, _finite(hh.cash_balance, "household cash", nonnegative=False))
        for (_, loan, due), amount in zip(claims, _allocate(claims, cash)):
            paid = _post_payment(economy, loan, amount)
            hh.cash_balance -= paid
            if paid > 0:
                hh.add_ledger_flow("bank", -paid)
            total_paid += paid
            if due - paid > TOL:
                loan["missed_payments"] = int(loan.get("missed_payments", 0)) + 1
                bank.update_household_credit_score(hid, -0.05)
                threshold = (int(getattr(getattr(economy, "config", None), "payment_household_default_misses", 8))
                             if _version(loan) == 2 else 8)
                if loan["missed_payments"] >= threshold:
                    _write_off(economy, loan)
                    bank.update_household_credit_score(hid, -0.20)
            else:
                loan["missed_payments"] = 0
                if _version(loan) == 2 and loan.get("term_remaining", 0) > 0:
                    loan["term_remaining"] -= 1
                bank.update_household_credit_score(hid, +0.01)
        _sync_mirrors(hh, all_claims[hid], "household")
    return total_paid


def collect_firm_dues(economy: Any) -> float:
    """Collect registered firm claims at 9.5; housing mortgages stay at 6.6b."""
    bank = economy.bank
    if bank is None:
        return 0.0
    _ensure_ids(economy)
    tick = int(economy.current_tick)
    book = _book(economy)
    if book.get("firm_due_collected_tick") == tick:
        raise ValueError("Firm dues already collected this tick")
    book["firm_due_collected_tick"] = tick
    by_firm: dict[int, list[tuple[str, dict, float]]] = defaultdict(list)
    all_claims: dict[int, list[dict]] = defaultdict(list)
    for loan in bank.active_loans:
        if loan.get("borrower_type") != "firm":
            continue
        fid = loan["borrower_id"]
        all_claims[fid].append(loan)
        due = _due(loan, tick, bank)
        if due > TOL:
            by_firm[fid].append((_id(loan), loan, due))
    lookup = getattr(economy, "firm_lookup", None) or {f.firm_id: f for f in economy.firms}
    total_paid = 0.0
    for fid, claims in by_firm.items():
        claims.sort(key=lambda item: item[0])
        firm = lookup.get(fid)
        if firm is None:
            for _, loan, _ in claims:
                _write_off(economy, loan)
            bank.update_firm_credit_score(fid, -0.20)
            continue
        cash = max(0.0, _finite(firm.cash_balance, "firm cash", nonnegative=False))
        for (_, loan, due), amount in zip(claims, _allocate(claims, cash)):
            paid = _post_payment(economy, loan, amount)
            firm.cash_balance -= paid
            total_paid += paid
            if due - paid > TOL:
                loan["missed_payments"] = int(loan.get("missed_payments", 0)) + 1
                bank.update_firm_credit_score(fid, -0.05)
                if _version(loan) == 2 and loan["missed_payments"] >= int(
                    getattr(getattr(economy, "config", None), "payment_firm_default_misses", 8)
                ):
                    _write_off(economy, loan)
                    bank.update_firm_credit_score(fid, -0.20)
            else:
                loan["missed_payments"] = 0
                if _version(loan) == 2 and loan.get("term_remaining", 0) > 0:
                    loan["term_remaining"] -= 1
                bank.update_firm_credit_score(fid, +0.01)
        _sync_mirrors(firm, all_claims[fid], "firm")
    return total_paid


def firm_exit_claims(economy: Any, firm: Any) -> list[tuple[str, dict, float]]:
    """Registered claims for the shared, post-worker firm-exit waterfall.

    The caller adds direct Treasury and housing mortgage claims to this list's
    amounts before allocating cash.  The portfolio index is built once for all
    exiting firms in this tick, and each amount is the actual unpaid balance.
    """
    book = _book(economy)
    tick = int(economy.current_tick)
    if book.get("firm_exit_claim_tick") != tick:
        by_firm: dict[int, list[tuple[str, dict, float]]] = defaultdict(list)
        by_id: dict[str, dict] = {}
        bank = getattr(economy, "bank", None)
        if bank is not None:
            _ensure_ids(economy)
            for loan in bank.active_loans:
                if loan.get("borrower_type") != "firm":
                    continue
                outstanding = _remaining(loan)
                if outstanding <= TOL:
                    continue
                claim_id = _id(loan)
                by_firm[loan["borrower_id"]].append((claim_id, loan, outstanding))
                by_id[claim_id] = loan
        for claims in by_firm.values():
            claims.sort(key=lambda item: item[0])
        book["firm_exit_claim_index"] = dict(by_firm)
        book["firm_exit_claim_by_id"] = by_id
        book["firm_exit_claim_tick"] = tick
    return book["firm_exit_claim_index"].get(firm.firm_id, [])


def settle_firm_exit_claim(
    economy: Any, firm: Any, loan: dict, allocated_cash: float
) -> tuple[float, float]:
    """Post one registered exit claim's recovery and discharge its shortfall.

    This is deliberately per claim: the exit coordinator must first allocate
    one cash budget across registered loans, direct Treasury debt and mortgages.
    """
    claim_id = _id(loan)
    firm_exit_claims(economy, firm)
    book = _book(economy)
    if book["firm_exit_claim_by_id"].get(claim_id) is not loan or loan["borrower_id"] != firm.firm_id:
        raise ValueError(f"Unregistered exit claim {claim_id} for firm {firm.firm_id}")
    tick = int(economy.current_tick)
    if loan.get("exit_settled_tick") == tick:
        raise ValueError(f"Firm exit claim {claim_id} already settled this tick")
    due = _remaining(loan)
    allocation = _finite(allocated_cash, "firm exit allocation")
    cash = max(0.0, _finite(firm.cash_balance, "firm cash", nonnegative=False))
    if allocation > due + TOL or allocation > cash + TOL:
        raise ValueError(f"Firm exit allocation exceeds cash or claim {claim_id}")
    paid = _post_payment(economy, loan, min(allocation, due, cash))
    firm.cash_balance -= paid
    loss = _remaining(loan)
    _write_off(economy, loan)
    loan["exit_settled_tick"] = tick
    # The registered part of these compatibility mirrors vanishes regardless
    # of how much the funder recovered.  Housing claims remain until their
    # independent settlement in the same creditor rank.
    firm.bank_loan_remaining = max(0.0, _finite(firm.bank_loan_remaining, "firm loan mirror") - due)
    firm.bank_loan_payment_per_tick = max(
        0.0, _finite(firm.bank_loan_payment_per_tick, "firm payment mirror")
        - _finite(loan["payment_per_tick"], "scheduled payment")
    )
    if loan.get("subtype") == "service_infrastructure":
        firm.service_infrastructure_loan_remaining = max(
            0.0, _finite(getattr(firm, "service_infrastructure_loan_remaining", 0.0), "infrastructure mirror") - due
        )
        firm.service_infrastructure_loan_payment_per_tick = max(
            0.0, _finite(getattr(firm, "service_infrastructure_loan_payment_per_tick", 0.0), "infrastructure payment")
            - _finite(loan["payment_per_tick"], "scheduled payment")
        )
    return paid, loss


def quoted_annual_rate(economy: Any, base_annual_rate: float) -> float:
    """Exogenous stress quote for *new* bank contracts only.

    The shift is an annual percentage-point amount, not an inflation rule or
    a repricing instruction for any outstanding fixed-rate claim.
    """
    base = _finite(base_annual_rate, "base annual quote")
    shift = _finite(
        getattr(getattr(economy, "config", None), "payment_annual_quote_shift", 0.0),
        "annual quote shift", nonnegative=False,
    )
    if not -0.05 <= shift <= 0.05:
        raise ValueError("Annual new-loan quote shift must be within [-0.05, 0.05]")
    return max(0.0, base + shift)


def v2_payment(principal: float, annual_rate: float, term_ticks: int, ticks_per_year: int) -> float:
    amount = _finite(principal, "loan principal")
    rate = _finite(annual_rate, "annual rate")
    if not isinstance(term_ticks, int) or term_ticks < 1:
        raise ValueError("Loan term must contain at least one tick")
    if not isinstance(ticks_per_year, int) or ticks_per_year < 1:
        raise ValueError("ticks_per_year must be positive")
    per_tick = rate / ticks_per_year
    return amount * per_tick / (1.0 - (1.0 + per_tick) ** -term_ticks) if per_tick else amount / term_ticks


def _underwriting_due_index(economy: Any) -> dict[tuple[str, int], float]:
    book = _book(economy)
    tick = int(economy.current_tick)
    if book.get("underwriting_due_tick") == tick:
        return book["underwriting_dues"]
    dues: dict[tuple[str, int], float] = defaultdict(float)
    delinquent: set[tuple[str, int]] = set()
    bank = economy.bank
    if bank is not None:
        for loan in bank.active_loans:
            if _remaining(loan) > TOL:
                dues[(loan["borrower_type"], loan["borrower_id"])] += min(
                    _finite(loan["payment_per_tick"], "existing installment"), _remaining(loan)
                )
                if int(loan.get("missed_payments", 0)) > 0:
                    delinquent.add((loan["borrower_type"], loan["borrower_id"]))
    for firm in economy.firms:
        dues[("firm", firm.firm_id)] += min(
            _finite(getattr(firm, "loan_payment_per_tick", 0.0), "direct treasury installment"),
            _finite(getattr(firm, "government_loan_remaining", 0.0), "direct treasury remaining"),
        )
        dues[("firm", firm.firm_id)] += sum(
            _finite(contract.pmt_per_tick, "mortgage installment")
            for contract in (getattr(firm, "housing_active_loans", None) or ())
            if contract.principal_remaining > TOL
        )
    book["underwriting_dues"] = dues
    book["underwriting_delinquent"] = delinquent
    book["underwriting_due_tick"] = tick
    return dues


def can_underwrite(
    economy: Any, borrower_type: str, borrower_id: int, new_pmt: float,
    *, purpose: str | None = None,
) -> bool:
    """Static prior-settled income gate, deducting each existing PMT once."""
    if borrower_type not in ("household", "firm"):
        raise ValueError("Unknown borrower type")
    proposed = _finite(new_pmt, "proposed installment")
    state = _claim_state(economy)
    if int(economy.current_tick) < state.get("loan_credit_cooldown_until", {}).get((borrower_type, borrower_id), -1):
        return False
    key = "prior_settled_household_net" if borrower_type == "household" else "prior_settled_firm_operating_cashflow"
    prior = _finite(state.get(key, {}).get(borrower_id, 0.0), "prior settled repayment income", nonnegative=False)
    existing = _underwriting_due_index(economy).get((borrower_type, borrower_id), 0.0)
    if borrower_type == "household":
        household = getattr(economy, "household_lookup", {}).get(borrower_id)
        if household is None:
            return False
        if _finite(getattr(household, "rent_arrears", 0.0), "rent arrears") > TOL:
            return False
        if (borrower_type, borrower_id) in _book(economy)["underwriting_delinquent"]:
            return False
        food = _finite(state.get("prior_essential_food_cost", {}).get(borrower_id, 0.0), "prior essential food")
        rent = (_finite(getattr(household, "monthly_rent", 0.0), "weekly rent")
                if getattr(household, "renting_from_firm_id", None) is not None else 0.0)
        prior = max(0.0, prior - food - rent)
    else:
        firm = getattr(economy, "firm_lookup", {}).get(borrower_id)
        if firm is None or (
            purpose != "working_capital"
            and _finite(getattr(firm, "payment_wage_arrears", 0.0), "worker arrears") > TOL
        ):
            return False
    max_share = _finite(getattr(getattr(economy, "config", None), "payment_debt_service_share", 0.35), "debt service share")
    if not 0.0 < max_share <= 1.0:
        raise ValueError("Debt service share must be in (0,1]")
    prior = max(0.0, prior)
    return prior > TOL and proposed + existing <= max_share * prior + TOL


def originate_v2(
    economy: Any, borrower_type: str, borrower_id: int, principal: float,
    annual_rate: float, term_ticks: int, subtype: str,
    *, funder: str = "bank", authorized_treasury: bool = False,
) -> dict | None:
    """Issue a full-purpose v2 registered claim and debit its actual funder.

    Returns None on ordinary credit/funding denial.  The caller delivers the
    principal to its declared borrower or supplier exactly once; this helper
    never makes it discretionary household cash by itself.
    """
    bank = economy.bank
    amount = _finite(principal, "loan principal")
    if amount <= TOL or bank is None:
        return None
    if borrower_type not in ("household", "firm") or funder not in ("bank", "treasury"):
        raise ValueError("Invalid borrower or funder")
    if borrower_type == "household":
        borrower = getattr(economy, "household_lookup", {}).get(borrower_id)
        if borrower is None or subtype not in ("medical", "consumption"):
            raise ValueError("Invalid household loan purpose")
        if subtype == "medical" and _finite(borrower.medical_loan_remaining, "medical mirror") > TOL:
            return None
        score_floor = 0.15 if subtype == "medical" else 0.40
        if bank.get_household_credit_score(borrower_id) < score_floor:
            return None
    else:
        borrower = getattr(economy, "firm_lookup", {}).get(borrower_id)
        if borrower is None:
            raise ValueError("Firm borrower missing")
        if bank.get_firm_credit_score(borrower_id) < 0.25:
            return None
    from config import CONFIG
    ticks_per_year = int(getattr(getattr(economy, "config", CONFIG).time, "ticks_per_year"))
    rate = quoted_annual_rate(economy, annual_rate) if funder == "bank" else _finite(annual_rate, "treasury rate")
    payment = v2_payment(amount, rate, int(term_ticks), ticks_per_year)
    if not can_underwrite(economy, borrower_type, borrower_id, payment, purpose=subtype):
        return None
    if funder == "bank":
        if not bank.can_lend() or bank.lendable_cash + TOL < amount:
            return None
    else:
        # Treasury lending is an explicit sensitivity arm, never a reserve or
        # care-funding fallback.  Its owner must authorize free cash first.
        free_cash = getattr(economy, "_payment_free_treasury_cash", None)
        if (
            not authorized_treasury or free_cash is None
            or free_cash() + TOL < amount
            or economy.government.cash_balance + TOL < amount
        ):
            return None
    claim = {
        "claim_id": _next_id(economy), "contract_version": 2,
        "borrower_type": borrower_type, "borrower_id": borrower_id,
        "subtype": subtype, "funder": funder, "govt_backed": funder == "treasury",
        "principal": amount, "principal_remaining": amount,
        "accrued_interest": 0.0, "remaining": amount,
        "payment_per_tick": payment, "rate": rate, "term_remaining": int(term_ticks),
        "ticks_per_year": ticks_per_year,
        "origination_tick": int(economy.current_tick),
        "first_due_tick": int(economy.current_tick) + 1,
        "last_accrual_tick": int(economy.current_tick),
        "missed_payments": 0,
    }
    if funder == "bank":
        bank.cash_reserves -= amount
    else:
        economy.government.cash_balance -= amount
    bank.total_loans_outstanding += amount
    bank.last_tick_new_loans += amount
    bank.active_loans.append(claim)
    due_index = _underwriting_due_index(economy)
    due_index[(borrower_type, borrower_id)] += payment
    if borrower_type == "household":
        setattr(borrower, f"{subtype}_loan_remaining", getattr(borrower, f"{subtype}_loan_remaining", 0.0) + amount)
        setattr(borrower, f"{subtype}_loan_payment_per_tick", getattr(borrower, f"{subtype}_loan_payment_per_tick", 0.0) + payment)
        if subtype == "medical":
            borrower.medical_loan_principal = amount
            borrower.medical_loan_bank_serviced = True
    else:
        borrower.bank_loan_principal = getattr(borrower, "bank_loan_principal", 0.0) + amount
        borrower.bank_loan_remaining = getattr(borrower, "bank_loan_remaining", 0.0) + amount
        borrower.bank_loan_payment_per_tick = getattr(borrower, "bank_loan_payment_per_tick", 0.0) + payment
        if subtype == "service_infrastructure":
            borrower.service_infrastructure_loan_remaining += amount
            borrower.service_infrastructure_loan_payment_per_tick += payment
    return claim


def quote_medical_loan(economy: Any, household: Any, shortfall: float) -> bool:
    """Read-only full-funding check for one patient-pay visit."""
    amount = _finite(shortfall, "medical shortfall")
    bank = economy.bank
    if (
        amount <= TOL or bank is None
        or _finite(household.medical_loan_remaining, "medical mirror") > TOL
        or bank.get_household_credit_score(household.household_id) < 0.15
        or not bank.can_lend() or bank.lendable_cash + TOL < amount
    ):
        return False
    from config import CONFIG
    runtime_config = getattr(economy, "config", CONFIG)
    score = bank.get_household_credit_score(household.household_id)
    rate = quoted_annual_rate(economy, bank._risk_adjusted_rate(score, spread=0.03))
    payment = v2_payment(amount, rate, 52, int(runtime_config.time.ticks_per_year))
    return can_underwrite(economy, "household", household.household_id, payment)


def fund_medical_loan(economy: Any, household: Any, shortfall: float) -> float:
    """Fund an accepted visit directly; caller adds return to care clearing.

    Call only after a provider slot and immutable full-price clearing line are
    accepted.  This function never places principal in discretionary patient cash.
    """
    amount = _finite(shortfall, "medical shortfall")
    if not quote_medical_loan(economy, household, amount):
        return 0.0
    bank = economy.bank
    score = bank.get_household_credit_score(household.household_id)
    rate = bank._risk_adjusted_rate(score, spread=0.03)
    claim = originate_v2(
        economy, "household", household.household_id, amount, rate, 52, "medical"
    )
    if claim is None:
        return 0.0
    book = getattr(economy, "payment_book", None)
    if book is not None and not isinstance(book, dict):
        pending = getattr(book, "medical_funding_pending", None)
        if pending is None:
            pending = {}
            book.medical_funding_pending = pending
        pending[household.household_id] = pending.get(household.household_id, 0.0) + amount
    return amount


def rollback_medical_loan(economy: Any, household: Any) -> bool:
    """Undo this tick's unspent visit credit if care clearing rejects the visit."""
    bank = economy.bank
    if bank is None:
        return False
    for position in range(len(bank.active_loans) - 1, -1, -1):
        claim = bank.active_loans[position]
        if (
            claim.get("borrower_type") != "household"
            or claim.get("borrower_id") != household.household_id
            or claim.get("subtype") != "medical"
            or claim.get("contract_version") != 2
            or claim.get("origination_tick") != int(economy.current_tick)
            or claim.get("first_due_tick") != int(economy.current_tick) + 1
            or abs(claim.get("principal_remaining", 0) - claim.get("principal", 0)) > TOL
            or claim.get("accrued_interest", 0) > TOL
        ):
            continue
        amount = _finite(claim["principal"], "principal")
        book = getattr(economy, "payment_book", None)
        pending = getattr(book, "medical_funding_pending", None) if book is not None and not isinstance(book, dict) else None
        if pending is not None and pending.get(household.household_id, 0.0) + TOL < amount:
            raise ValueError("Cannot roll back medical funding already committed to care")
        bank.cash_reserves += amount
        bank.total_loans_outstanding = max(0.0, bank.total_loans_outstanding - amount)
        bank.last_tick_new_loans = max(0.0, bank.last_tick_new_loans - amount)
        bank.active_loans.pop(position)
        loan_state = _book(economy)
        dues = loan_state.get("underwriting_dues")
        if dues is not None:
            key = ("household", household.household_id)
            dues[key] = max(0.0, dues.get(key, 0.0) - claim["payment_per_tick"])
        if pending is not None:
            current = pending.get(household.household_id, 0.0)
            remaining_pending = max(0.0, current - amount)
            if remaining_pending <= TOL:
                pending.pop(household.household_id, None)
            else:
                pending[household.household_id] = remaining_pending
        _sync_mirrors(
            household,
            [loan for loan in bank.active_loans if loan.get("borrower_type") == "household" and loan.get("borrower_id") == household.household_id],
            "household",
        )
        return True
    return False
