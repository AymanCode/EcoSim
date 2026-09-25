"""Household information and planning inputs for named payment scenarios.

These helpers never transfer cash.  Beliefs affect desired orders only; actual
payroll and tax records are authoritative for settlement and underwriting.
"""

from __future__ import annotations

import math
from typing import Any


def _finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _state(economy: Any) -> dict:
    state = getattr(economy, "payment_state", None)
    if state is None:
        state = {}
        economy.payment_state = state
    return state


def initialize_tax_beliefs(economy: Any) -> dict[int, float]:
    """Give each current household a bounded headline-rate prior once."""
    state = _state(economy)
    beliefs = state.setdefault("expected_wage_tax_share", {})
    headline = min(1.0, max(0.0, _finite(economy.government.wage_tax_rate, "headline wage tax")))
    for household in economy.households:
        hid = household.household_id
        beliefs.setdefault(hid, headline)
        share = _finite(beliefs[hid], f"household {hid} tax belief")
        if not 0.0 <= share <= 1.0:
            raise ValueError(f"household {hid} tax belief outside [0,1]")
    return beliefs


def observe_settled_tax(economy: Any) -> None:
    """Update from this tick's *ordinary* funded gross and withholding once.

    Call after 5a settlement.  Phase-2 planning has already happened, making
    the observation available only to the next normal planning pass.
    """
    state = _state(economy)
    tick = int(economy.current_tick)
    if state.get("tax_belief_observed_tick") == tick:
        return
    book = getattr(economy, "payment_book", None)
    if book is None:
        raise ValueError("Paid ordinary-income book is required")
    beliefs = initialize_tax_beliefs(economy)
    paid_income = book.paid_income
    updates = {}
    for household in economy.households:
        hid = household.household_id
        record = paid_income.get(hid, {})
        gross = _finite(record.get("gross", 0.0), "ordinary gross")
        tax = _finite(record.get("tax", 0.0), "ordinary withholding")
        if gross < 0 or tax < 0 or tax > gross + 1e-6:
            raise ValueError("Invalid settled ordinary gross/withholding")
        if gross > 1e-6:
            updates[hid] = min(1.0, max(0.0, tax / gross))
    beliefs.update(updates)
    state["tax_belief_observed_tick"] = tick


def planning_inputs(economy: Any) -> tuple[list[float], list[float], dict[int, dict[str, float]]]:
    """Return net wage signals and once-subtracted opening obligation capacity.

    The returned liquidity is a desired-order estimate, not escrow, a loan or
    proof that deposits can be released.  The planner must use it in both its
    savings drawdown and final cash ceiling.
    """
    beliefs = initialize_tax_beliefs(economy)
    book = getattr(economy, "payment_book", None)
    loan_state = getattr(book, "loan_state", {}) if book is not None else {}
    due_by_hid = loan_state.get("household_due_totals", {})
    if loan_state.get("household_due_tick") != int(economy.current_tick):
        raise ValueError("Household due index must be prepared before planning")
    net_wages = []
    available = []
    pressure = {}
    for household in economy.households:
        hid = household.household_id
        wage = max(0.0, _finite(household.wage, "contract wage")) if household.is_employed else 0.0
        net_wages.append(wage * (1.0 - beliefs[hid]))
        cash = _finite(household.cash_balance, "opening cash")
        deposit = max(0.0, _finite(household.bank_deposit, "deposit"))
        # A negative signed cash balance must first be repaired by any deposit
        # release before the remainder can finance an order.
        nominal_access = max(0.0, cash + 0.9 * deposit)
        rent = (
            max(0.0, _finite(household.monthly_rent, "weekly contract rent"))
            if household.renting_from_firm_id is not None else 0.0
        )
        debt = max(0.0, _finite(due_by_hid.get(hid, 0.0), "indexed debt due"))
        obligations = rent + debt
        available.append(max(0.0, nominal_access - obligations))
        pressure[hid] = {
            "rent_due": rent, "loan_due": debt,
            "nominal_access": nominal_access,
            "obligation_pressure": obligations / max(nominal_access, 1.0),
            "estimated_discretionary_liquidity": available[-1],
        }
    if book is not None:
        book.obligation_pressure = pressure
    return net_wages, available, pressure


def diagnose_observed_offer(economy: Any, household_id: int, gross_offer: float, offer_id: Any) -> dict:
    """Record net-gain arithmetic only for an actually accepted matched offer.

    The labor match still uses its existing gross reservation and all its gates.
    The caller must invoke this at a real offer event, never enumerate firms to
    synthesize offers that a household did not see.
    """
    book = getattr(economy, "payment_book", None)
    if book is None:
        raise ValueError("Payment book required for offer diagnostic")
    lookup = getattr(economy, "household_lookup", None)
    if lookup is None:
        lookup = {h.household_id: h for h in economy.households}
    household = lookup[household_id]
    offer = _finite(gross_offer, "observed gross offer")
    if offer < 0:
        raise ValueError("Observed offer cannot be negative")
    beliefs = _state(economy).setdefault("expected_wage_tax_share", {})
    share = beliefs.get(household_id)
    if share is None:
        share = min(1.0, max(0.0, _finite(economy.government.wage_tax_rate, "headline wage tax")))
        beliefs[household_id] = share
    share = _finite(share, "offer tax belief")
    if not 0.0 <= share <= 1.0:
        raise ValueError("Offer tax belief outside [0,1]")
    current = (
        max(0.0, _finite(household.wage, "current gross wage")) * (1.0 - share)
        if household.is_employed
        else max(0.0, _finite(economy.government.get_unemployment_benefit_level(), "announced benefit"))
    )
    row = {
        "tick": int(economy.current_tick),
        "household_id": household_id,
        "offer_id": offer_id,
        "coverage": "observed_accepted_offers_only",
        "gross_offer": offer,
        "estimated_net_offer": offer * (1.0 - share),
        "estimated_net_current": current,
        "estimated_net_gain": offer * (1.0 - share) - current,
    }
    rows = getattr(book, "net_offer_diagnostics", None)
    if rows is None:
        rows = []
        book.net_offer_diagnostics = rows
    rows.append(row)
    return row
