"""#45 mechanism metric for the #58 panel: how far the read-only quote is from the charge.

The quote is read during the tick, at the household's budget phase: after
``Economy._settle_legacy_income_and_plan_shopping`` on legacy, and after
``Economy._payment_withdraw_deposits`` on the payment sequences. A queued
visit is usually served in that same tick, so reading
``expected_healthcare_out_of_pocket_all()`` after ``step()`` sees an empty
queue and reports no households. The hooks only call that read-only getter.

The charge is ``HouseholdAgent.last_healthcare_spend``: dollars paid out of
pocket for healthcare this tick. It is reset in
``Economy._reset_healthcare_tick_state`` and incremented only when a visit
is paid, in ``Economy._process_healthcare_services`` (legacy) and
``payment_sectors.settle_payment_care`` (payment sequences). There is no
``last_tick_healthcare_paid`` attribute.

On main's checkout (no quote method) every metric is 0.
"""

_QUOTED = {}


def _capture(economy):
    global _QUOTED
    quote_all = getattr(economy, "expected_healthcare_out_of_pocket_all", None)
    _QUOTED = dict(quote_all() or {}) if quote_all is not None else {}


def _install():
    """Observe the budget-phase quote. Read-only: the getter charges nothing."""
    import economy as economy_mod

    Economy = economy_mod.Economy
    if getattr(Economy, "_pr45_quote_observed", False):
        return
    Economy._pr45_quote_observed = True
    orig_step = Economy.step
    orig_legacy = Economy._settle_legacy_income_and_plan_shopping
    orig_payment = Economy._payment_withdraw_deposits

    def step(self):
        global _QUOTED
        _QUOTED = {}
        orig_step(self)

    def settle_legacy(self, tick):
        plans = orig_legacy(self, tick)
        _capture(self)
        return plans

    def withdraw(self, quotes):
        orig_payment(self, quotes)
        _capture(self)

    Economy.step = step
    Economy._settle_legacy_income_and_plan_shopping = settle_legacy
    Economy._payment_withdraw_deposits = withdraw


_install()


def CHARGE_OF(economy, household):  # this tick's out-of-pocket care charge
    return float(getattr(household, "last_healthcare_spend", 0.0) or 0.0)


def extra_metrics(economy):
    _install()
    quote_all = getattr(economy, "expected_healthcare_out_of_pocket_all", None)
    if quote_all is None:
        return {"quoted_households": 0.0, "under_quotes": 0.0, "abs_error_mean": 0.0, "quote_mean": 0.0}
    under, errs = 0, []
    lookup = getattr(economy, "household_lookup", {})
    for hid, quoted in _QUOTED.items():
        household = lookup.get(hid)
        if household is None:
            continue
        charged = CHARGE_OF(economy, household)
        if charged <= 0.0:
            continue  # not served this tick (still waiting, or refused)
        errs.append(abs(charged - quoted))
        if charged > quoted + 1e-6:
            under += 1
    quotes = _QUOTED
    return {
        "quoted_households": float(len(quotes)),
        "under_quotes": float(under),  # served visits charged more than quoted (expected 0)
        "abs_error_mean": (sum(errs) / len(errs)) if errs else 0.0,
        "quote_mean": (sum(quotes.values()) / len(quotes)) if quotes else 0.0,
    }
