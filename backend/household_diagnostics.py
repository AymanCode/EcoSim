"""Tick-local observational counters; none of these functions move money."""


def record_healthcare_support(economy, firm, source, amount):
    """Attribute actual financing or public care payments to their recipient."""
    if (getattr(firm, "good_category", "") or "").lower() != "healthcare" or amount <= 0:
        return
    records = getattr(economy, "healthcare_support_this_tick", None)
    if records is None:
        records = economy.healthcare_support_this_tick = {}
    row = records.setdefault(firm.firm_id, {})
    row[source] = row.get(source, 0.0) + float(amount)
