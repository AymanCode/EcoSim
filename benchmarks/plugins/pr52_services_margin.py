"""Extra Services margin measures for the #52 evidence panel.

Read-only. The panel prefixes these keys with ``x_``.
"""


def extra_metrics(economy):
    svc = [f for f in economy.firms if (f.good_category or "").lower() == "services" and not f.is_baseline]
    base = [f for f in economy.firms if (f.good_category or "").lower() == "services" and f.is_baseline]
    mk = [float(f.markup) for f in svc]
    sold = sum(float(f.last_units_sold) for f in svc)
    soldout = sum(1 for f in svc if f.last_units_produced > 0 and f.last_units_sold >= 0.999 * f.last_units_produced)
    # All Services firms, including the baseline. Not private sales.
    unmet = float(getattr(economy, "services_unmet_demand", 0.0))
    b = base[0] if base else None
    uc = float(getattr(b, "unit_cost", 0.0) or 0.0) if b else 0.0
    return {
        "svc_markup_mean": sum(mk) / len(mk) if mk else 0.0,
        "svc_markup_max": max(mk) if mk else 0.0,
        "svc_soldout_share": soldout / len(svc) if svc else 0.0,
        "all_services_unmet_over_private_sold": unmet / (sold + unmet) if (sold + unmet) > 0 else 0.0,
        "baseline_svc_price_over_cost": (float(b.price) / uc) if (b and uc > 0) else 0.0,
    }
