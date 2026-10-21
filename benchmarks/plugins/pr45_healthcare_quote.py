"""#45 mechanism metric for the #58 panel: how far the read-only quote is from the charge.

After tick t it stores each queued household's quoted out-of-pocket
(``Economy.expected_healthcare_out_of_pocket_all()``). After tick t+1 it
compares that quote with what the household was actually charged for care
in t+1.

The charge is ``HouseholdAgent.last_healthcare_spend``: dollars paid out of
pocket for healthcare this tick. It is reset in
``Economy._reset_healthcare_tick_state`` and incremented only when a visit
is paid, in ``Economy._process_healthcare_services`` (legacy) and
``payment_sectors.settle_payment_care`` (payment sequences). There is no
``last_tick_healthcare_paid`` attribute.

On main's checkout (no quote method) every metric is 0.
"""

_PREV = {}


def CHARGE_OF(economy, household):  # this tick's out-of-pocket care charge
    return float(getattr(household, "last_healthcare_spend", 0.0) or 0.0)


def extra_metrics(economy):
    global _PREV
    quote_all = getattr(economy, "expected_healthcare_out_of_pocket_all", None)
    if quote_all is None:
        return {"quoted_households": 0.0, "under_quotes": 0.0, "abs_error_mean": 0.0, "quote_mean": 0.0}
    under, errs = 0, []
    lookup = getattr(economy, "household_lookup", {})
    for hid, quoted in _PREV.items():
        h = lookup.get(hid)
        if h is None:
            continue
        charged = CHARGE_OF(economy, h)
        if charged <= 0.0:
            continue  # not served this tick (still waiting, or refused)
        errs.append(abs(charged - quoted))
        if charged > quoted + 1e-6:
            under += 1
    quotes = quote_all() or {}
    _PREV = dict(quotes)
    return {
        "quoted_households": float(len(quotes)),
        "under_quotes": float(under),  # served visits charged more than quoted (expected 0)
        "abs_error_mean": (sum(errs) / len(errs)) if errs else 0.0,
        "quote_mean": (sum(quotes.values()) / len(quotes)) if quotes else 0.0,
    }
