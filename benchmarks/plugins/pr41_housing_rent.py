"""#41 housing metrics for the evidence panel: who pays what rent, and why.

Read after each ``step()``, from state both ``main`` and the PR hold, so a
checkout without the rent rule reports the same quantities and the panel's
off == main fingerprint check covers these columns too. Read-only.

- ``posted_rent_mean``: mean posted rent (``price``) over Housing firms.
- ``posted_rent_max_weekly_rise``: largest one-week rise of any Housing
  firm's posted rent, as a fraction (0.2 = +20%); 0 when none rose.
- ``rent_paid_mean``: mean rent paid this tick by households that paid any
  (``last_tick_ledger["rent"]``, both the legacy housing phase and
  ``payment_sectors.settle_payment_rent`` write it).
- ``rent_to_wage_employed``: rent paid by employed payers over their weekly
  contract wages.
- ``homeless`` / ``evictions``: ``last_housing_diagnostics`` (evictions are
  this tick's).
- ``rent_cap_binds``: ``rent_increase_limited_count``, reset every tick, so
  this is the number of Housing firms the rent-stabilization cap limited.
- ``rent_floor``: ``max(rent_floor_absolute_min, p25 wage x
  rent_affordability_share)`` from the cached wage percentiles (refreshed in
  the labor-outcome phase, before any rent write).
- ``wage_p25`` / ``wage_mean_employed``: the cached 25th-percentile wage and
  the mean contract wage of employed households.
- ``housing_profit``: summed ``last_profit`` of Housing firms.
"""

_PREVIOUS_RENT = {}


def extra_metrics(economy):
    from config import CONFIG

    lm = CONFIG.labor_market
    housing = [f for f in economy.firms if f.good_category == "Housing"]
    rents = {f.firm_id: float(f.price) for f in housing}
    rises = [rent / _PREVIOUS_RENT[fid] - 1.0 for fid, rent in rents.items() if _PREVIOUS_RENT.get(fid, 0.0) > 0.0]
    _PREVIOUS_RENT.clear()
    _PREVIOUS_RENT.update(rents)

    paid = []
    employed_rent = employed_wage = 0.0
    wages = []
    for household in economy.households:
        rent = -float((household.last_tick_ledger or {}).get("rent", 0.0))
        employed = household.employer_id is not None
        if employed:
            wages.append(float(household.wage))
        if rent > 0.0:
            paid.append(rent)
            if employed:
                employed_rent += rent
                employed_wage += float(household.wage)

    diagnostics = getattr(economy, "last_housing_diagnostics", None) or {}
    wage_p25 = economy.cached_wage_percentiles[0]
    floor = lm.rent_floor_absolute_min if wage_p25 is None else max(
        lm.rent_floor_absolute_min, wage_p25 * lm.rent_affordability_share
    )
    return {
        "posted_rent_mean": sum(rents.values()) / len(rents) if rents else 0.0,
        "posted_rent_max_weekly_rise": max([0.0, *rises]),
        "rent_paid_mean": sum(paid) / len(paid) if paid else 0.0,
        "rent_to_wage_employed": employed_rent / employed_wage if employed_wage > 0.0 else 0.0,
        "homeless": float(diagnostics.get("homeless_household_count", 0.0)),
        "evictions": float(diagnostics.get("eviction_count", 0.0)),
        "rent_cap_binds": float(getattr(economy, "rent_increase_limited_count", 0)),
        "rent_floor": float(floor),
        "wage_p25": float(wage_p25 or 0.0),
        "wage_mean_employed": sum(wages) / len(wages) if wages else 0.0,
        "housing_profit": float(sum(float(getattr(f, "last_profit", 0.0)) for f in housing)),
    }
