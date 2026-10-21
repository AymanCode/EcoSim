"""#48 mechanism metrics for the #58 panel (--metrics-plugin).
Reads the per-firm fields that round 3 adds for effective-rate pricing (48-4):
  firm.last_taxable_profit   (positive profit before tax this tick, 0 on a loss)
  firm.last_profit_tax_paid  (profit tax owed this tick)
On main's checkout these fields don't exist, so the plugin falls back to the economy totals
(rate = last_tick_gov_profit_taxes / taxable profit unknown -> 0) and reports zeros for per-firm rows."""


def extra_metrics(economy):
    g = economy.government
    lever = float(getattr(g, "profit_tax_rate", 0.0) or 0.0)
    rows = []
    for f in economy.firms:
        p = getattr(f, "last_taxable_profit", None)
        t = getattr(f, "last_profit_tax_paid", None)
        if p is None or t is None or p <= 0.0:
            continue
        rows.append((float(p), float(t)))
    taxed_profit = sum(p for p, _ in rows)
    tax = sum(t for _, t in rows)
    # Notch check: pairs where the higher pre-tax earner keeps less after tax.
    rows.sort()
    inversions = 0
    best_after = float("-inf")
    for p, t in rows:
        after = p - t
        if after < best_after - 1e-9:
            inversions += 1
        best_after = max(best_after, after)
    rates = [t / p for p, t in rows]
    pricing = [float(getattr(f, "pricing_profit_tax_rate", lever)) for f in economy.firms if not getattr(f, "is_baseline", False)]
    return {
        "profit_tax_paid": tax,
        "taxable_profit": taxed_profit,
        "avg_rate_on_taxed_profit": (tax / taxed_profit) if taxed_profit > 0 else 0.0,
        "max_firm_rate": max(rates) if rates else 0.0,
        "firms_taxed": float(len(rows)),
        "after_tax_inversions": float(inversions),
        # Gap between the rate firms gross prices up by and the lever (48-4 wedge).
        "pricing_rate_minus_lever": (sum(pricing) / len(pricing) - lever) if pricing else 0.0,
    }
