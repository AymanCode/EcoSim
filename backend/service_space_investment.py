"""Operating forecasts for Services space supported by recurring overflow."""

from statistics import median


SERVICE_INFRASTRUCTURE_TERM_TICKS = 104


def _added_units(demand, base_output, added_output):
    return min(added_output, max(0.0, demand - base_output))


def evaluate_recurring_overflow(
    rows, *, n, k, y, w, project_cost, annual_rate, term_ticks, depreciation_rate,
):
    """Score one whole quote on five already-validated settlements."""
    from payment_loans import v2_payment

    rows = [dict(row) for row in rows]
    for row in rows:
        # Keep rounding-sized excesses from becoming negative own work.
        row["S"] = min(row["S"], row["Q"])
        row["R"] = min(row["R"], row["S"])
        row["O"] = min(row["O"], row["L"])
        direct = row["S"] - row["R"]
        refill = min(row["L"], max(0.0, row["Q"] - direct)) if row["R"] else 0.0
        row.update(D=direct, F=refill, adjusted_sales=direct + refill,
                   adjusted_lost_orders=row["L"] - refill)

    qualifies = (
        all(row["adjusted_sales"] / row["Q"] >= 0.95 for row in rows)
        and sum(row["adjusted_lost_orders"] > 1e-9 for row in rows) >= 2
    )
    if qualifies:
        return True, {
            "rows": rows, "reason": "qualifies_without_inbound",
            "qualification_after_removal": True,
        }

    newest_price = rows[-1]["g"]
    newest_net_price = rows[-1]["p"]
    for row in rows:
        row["price_quantity_factor"] = min(1.0, row["g"] / newest_price) if newest_price > 0.0 else 0.0
        row["price_adjusted_inbound"] = row["price_quantity_factor"] * row["R"]
    supported_inbound = sorted(row["price_adjusted_inbound"] for row in rows)[1]
    repeat_inbound_cap = min(rows[-1]["price_adjusted_inbound"], supported_inbound)

    added_output = k * y
    staff_cost = k * w
    for row in rows:
        # Paid overflow can keep existing output occupied. New work comes
        # from the seller's own funded orders that remained unserved.
        own_demand = row["price_quantity_factor"] * (row["D"] + row["L"] - row["O"])
        repeat_inbound = min(row["price_adjusted_inbound"], repeat_inbound_cap)
        base_output = max(row["Q"], n * y)
        capped_price = min(row["p"], newest_net_price) if newest_price > 0.0 else 0.0
        incremental_cost = staff_cost + added_output * row["c"]
        demand = own_demand + repeat_inbound
        units = _added_units(demand, base_output, added_output)
        row.update(
            B=repeat_inbound, H=demand, u=units, capped_price=capped_price,
            contribution=units * capped_price - incremental_cost,
            no_inbound_contribution=(
                _added_units(own_demand, base_output, added_output) * capped_price - incremental_cost
            ),
            all_observed_inbound_contribution=(
                _added_units(own_demand + row["price_adjusted_inbound"], base_output, added_output)
                * capped_price - incremental_cost
            ),
            full_sale_contribution=added_output * capped_price - incremental_cost,
        )

    contributions = [row["contribution"] for row in rows]
    contribution = median(contributions)
    capital_hurdle = project_cost * annual_rate / 52.0
    apply = contribution >= capital_hurdle
    return apply, {
        "rows": rows,
        "reason": "covers_opportunity_cost" if apply else "below_opportunity_cost",
        "qualification_after_removal": False,
        "repeat_inbound_cap": repeat_inbound_cap,
        "weekly_contributions": contributions,
        "median_contribution": contribution,
        "median_projected_units": median(row["u"] for row in rows),
        "capital_hurdle": capital_hurdle,
        "equipment_hurdle": project_cost * (depreciation_rate + annual_rate / 52.0),
        "route_term_hurdle": v2_payment(project_cost, annual_rate, term_ticks, 52),
        "contribution_per_dollar": contribution / project_cost,
        "simple_recovery_weeks": project_cost / contribution if contribution > 0.0 else None,
        "no_inbound_median_contribution": median(row["no_inbound_contribution"] for row in rows),
        "all_observed_inbound_median_contribution": median(
            row["all_observed_inbound_contribution"] for row in rows
        ),
        "full_sale_median_contribution": median(row["full_sale_contribution"] for row in rows),
    }
