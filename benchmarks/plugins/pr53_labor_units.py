"""Mechanism metrics for the effective-labour evidence panel.

``food_labor_units_per_head`` and ``services_labor_units_per_head`` divide
full labour units by employed heads at private firms. A checkout without
``_labor_units_for_headcount`` (current main) counts each head as 1, which is
also what that method returns when weights are unbound.
"""


def extra_metrics(economy):
    out = {}
    for cat in ("food", "services"):
        firms = [
            firm for firm in economy.firms
            if (firm.good_category or "").lower() == cat and not firm.is_baseline and firm.employees
        ]
        heads = sum(len(firm.employees) for firm in firms)
        units = 0.0
        for firm in firms:
            measure = getattr(firm, "_labor_units_for_headcount", None)
            if measure is None:
                units += float(len(firm.employees))
            else:
                units += float(measure(float(len(firm.employees)), skill_only=False))
        out[f"{cat}_labor_units_per_head"] = units / heads if heads else 0.0
    food = [
        firm for firm in economy.firms
        if (firm.good_category or "").lower() == "food" and not firm.is_baseline
    ]
    out["food_private_capital"] = sum(float(firm.capital_stock) for firm in food)
    out["food_zero_inventory_share"] = (
        sum(1 for firm in food if firm.inventory_units <= 1e-9) / len(food)
    ) if food else 0.0
    out["anchor_skill"] = float(getattr(economy, "effective_labor_anchor_skill", 0.0) or 0.0)
    return out
