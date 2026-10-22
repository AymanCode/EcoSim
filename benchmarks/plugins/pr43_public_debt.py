"""#43 mechanism metrics for the #58 evidence panel (--metrics-plugin).
Called after every tick. Uses getattr defaults so main's checkout (no public debt) reports 0."""


def _borrowing_enabled() -> bool:
    """True when this arm's session is allowed to borrow.

    The panel worker calls this inside ``use_config`` with the arm's backend
    on ``sys.path``. Main has no ``public_debt_enabled`` field, so this stays
    false there.
    """
    try:
        from config import CONFIG
    except ImportError:
        return False
    government = getattr(CONFIG, "government", None)
    return bool(getattr(government, "public_debt_enabled", False))


def extra_metrics(economy):
    g = economy.government
    bank = getattr(economy, "bank", None)
    debt = float(getattr(g, "public_debt", 0.0) or 0.0)
    cash = float(g.cash_balance)
    bond = float(getattr(economy, "last_tick_gov_bond_purchases", 0.0) or 0.0)
    unfunded = float(getattr(g, "last_tick_debt_unfunded", 0.0) or 0.0)
    return {
        "public_debt": debt,
        "net_position": cash - debt,
        "interest_paid": float(getattr(g, "last_tick_debt_interest", 0.0) or 0.0),
        "borrowed": float(getattr(g, "last_tick_debt_borrowed", 0.0) or 0.0),
        "repaid": float(getattr(g, "last_tick_debt_repaid", 0.0) or 0.0),
        # Share of weeks the bank could not lend the whole shortfall.
        # With borrowing off, negative cash is main's overdraft. The field is
        # still filled in, and counting it would make flag-off differ from main.
        "unfunded_week": 1.0 if _borrowing_enabled() and unfunded > 0.0 else 0.0,
        # Must be 0 on every week: no bond buy (K06) while debt is owed.
        "bond_buy_while_debt": bond if debt > 0.0 else 0.0,
        # What approved cash-gated programs actually spent (checklist sec 4, fiscal).
        "program_spend": float(getattr(economy, "last_tick_gov_infrastructure_spending", 0.0) or 0.0)
        + float(getattr(economy, "last_tick_gov_technology_spending", 0.0) or 0.0)
        + float(getattr(economy, "last_tick_gov_social_spending", 0.0) or 0.0),
        "bank_lendable": float(getattr(bank, "lendable_cash", 0.0) or 0.0) if bank is not None else 0.0,
        "bank_new_loans": float(getattr(bank, "last_tick_new_loans", 0.0) or 0.0) if bank is not None else 0.0,
        "bank_public_debt_held": float(getattr(bank, "public_debt_held", 0.0) or 0.0) if bank is not None else 0.0,
    }
