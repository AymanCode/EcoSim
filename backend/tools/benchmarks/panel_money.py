"""Shared money-stock measurement; imports no simulator or test modules.

The evidence worker loads this file from its own evaluator checkout, so every
arm uses one measurement definition even when its test helpers differ.
"""

from typing import Any


def payment_holds(economy: Any) -> float:
    """Cash the income_first / income_late sequences hold outside every balance.

    These are the hold terms ``Economy.get_economic_metrics`` adds to
    ``total_economy_cash`` (``backend/economy.py``, "Money supply and drift").
    A firm that exits with wage arrears moves the recovered gross into
    ``recovery_holds`` and the next tick's settlement pays it out, so a run
    that ends on that tick is short by the held amount unless it is counted
    here. Legacy has no holds.
    """
    if getattr(economy, "payment_sequence", "legacy") == "legacy":
        return 0.0
    state = getattr(economy, "payment_state", None) or {}
    held = sum((state.get("recovery_holds") or {}).values())
    held += float(state.get("housing_equal_distribution_hold", 0.0))
    if not state.get("capital_routes_released", True):
        held += sum(row["amount"] for row in state.get("capital_routes", ()))
    book = getattr(economy, "payment_book", None)
    if book is not None:
        held += (
            book.clearing_cash
            + sum((state.get("ceo_holds") or {}).values())
            + sum(book.late_income.values())
            + sum(book.medical_funding_pending.values())
        )
    return float(held)


def total_money(economy: Any) -> float:
    household_cash = sum(h.cash_balance for h in economy.households)
    firm_cash = sum(f.cash_balance for f in economy.firms)
    queued_firm_cash = sum(f.cash_balance for f in getattr(economy, "queued_firms", []))
    government_cash = economy.government.cash_balance
    misc_pool = getattr(economy, "misc_firm_revenue", 0.0)
    return household_cash + firm_cash + queued_firm_cash + government_cash + misc_pool + payment_holds(economy)


def total_money_with_bank(economy: Any) -> float:
    """``total_money`` plus the bank's cash reserves, when a bank exists.

    Household deposits are NOT added. A deposit moves cash into the bank:
    ``Economy._process_bank_deposits`` subtracts it from ``hh.cash_balance``
    and ``BankAgent.accept_deposit`` does ``self.cash_reserves += amount``
    (``backend/agents.py``); ``BankAgent.withdraw`` does the reverse. So the
    deposited money is already inside ``cash_reserves``, and
    ``hh.bank_deposit`` / ``bank.total_deposits`` are the claim on it.
    Adding them would count the same money twice.
    """
    bank = getattr(economy, "bank", None)
    bank_reserves = float(bank.cash_reserves) if bank is not None else 0.0
    return total_money(economy) + bank_reserves


def total_money_net_of_injections(economy: Any) -> float:
    """``total_money_with_bank`` minus the recorded external injections.

    Legacy new-firm seed cash and the legacy demand shock are intentional
    outside money (owner decision 2026-09-29, rules doc K02). The economy
    records them in ``external_injection_total`` (signed), so a conserving
    economy keeps this value constant.
    """
    return total_money_with_bank(economy) - float(getattr(economy, "external_injection_total", 0.0))
