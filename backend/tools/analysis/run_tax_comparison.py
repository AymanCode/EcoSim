from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""Tax Rate Impact Comparison (Post-Warmup, Private Firms Only)

Runs warmup silently, then two identical post-warmup simulations:
  A) Default tax rates (wage=15%, profit=20%, investment=10%)
  B) Max tax rates (wage=50%, profit=50%, investment=30%)

Tax overrides are applied AFTER warmup completes, so both scenarios
start from the same warmed-up economy state. Only private (non-baseline)
firms are measured.

Usage:
    python run_tax_comparison.py
    python run_tax_comparison.py --ticks 60 --households 500
"""

import argparse
import sys
import os
import pickle
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy


def run_warmup(households: int):
    """Run warmup + settle until private firms exist, return ready economy."""
    economy = create_large_economy(num_households=households)
    warmup = economy.warmup_ticks
    print(f"Running {warmup}-tick warmup...", end=" ", flush=True)
    for _ in range(warmup):
        economy.step()
    print(f"done (tick {economy.current_tick}).")

    # Run extra ticks until private firms spawn (queued firms activate gradually)
    settle_ticks = 0
    max_settle = 20
    while settle_ticks < max_settle:
        private_firms = [f for f in economy.firms if not f.is_baseline]
        if private_firms:
            break
        economy.step()
        settle_ticks += 1

    private_firms = [f for f in economy.firms if not f.is_baseline]
    print(f"  Post-warmup settle: {settle_ticks} extra ticks. "
          f"{len(economy.firms)} firms ({len(private_firms)} private), tick {economy.current_tick}")

    if not private_firms:
        print("WARNING: No private firms yet â€” results will only show baseline firms.")

    return economy


def private_firm_stats(economy):
    """Compute stats for private (non-baseline) firms only."""
    private = [f for f in economy.firms if not f.is_baseline]
    if not private:
        return {"count": 0, "median_cash": 0, "mean_profit": 0, "mean_revenue": 0}
    cash_sorted = sorted(f.cash_balance for f in private)
    return {
        "count": len(private),
        "median_cash": cash_sorted[len(cash_sorted) // 2],
        "mean_profit": sum(f.last_profit for f in private) / len(private),
        "mean_revenue": sum(f.last_revenue for f in private) / len(private),
    }


def run_scenario(economy, label: str, tax_overrides: dict, ticks: int):
    """Run post-warmup ticks and collect per-tick metrics."""

    # Apply tax overrides AFTER warmup
    for lever, value in tax_overrides.items():
        economy.government.set_lever(lever, value)

    gov = economy.government
    start_tick = economy.current_tick

    print(f"\n{'=' * 100}")
    print(f"  SCENARIO: {label}")
    print(f"  wage_tax={gov.wage_tax_rate:.0%}  profit_tax={gov.profit_tax_rate:.0%}  "
          f"invest_tax={gov.investment_tax_rate:.0%}")
    print(f"  Starting from tick {start_tick} (post-warmup)")
    print(f"{'=' * 100}")
    print(f"{'Tick':>5} | {'Unemp':>7} | {'GDP':>10} | {'PvtFirms':>8} | "
          f"{'GovCash':>11} | {'PvtMdnCash':>11} | {'PvtMnProfit':>11} | "
          f"{'MdnHHCash':>10} | {'Happy':>5} | {'Morale':>6}")
    print("-" * 115)

    history = []
    for t in range(1, ticks + 1):
        economy.step()
        m = economy.get_economic_metrics()
        pf = private_firm_stats(economy)

        row = {
            "tick": t,
            "real_tick": economy.current_tick,
            "unemployment_rate": m.get("unemployment_rate", 0),
            "gdp": m.get("gdp_this_tick", 0),
            "private_firms": pf["count"],
            "total_firms": m.get("total_firms", 0),
            "gov_cash": m.get("government_cash", 0),
            "pvt_median_cash": pf["median_cash"],
            "pvt_mean_profit": pf["mean_profit"],
            "pvt_mean_revenue": pf["mean_revenue"],
            "median_household_cash": m.get("median_household_cash", 0),
            "mean_happiness": m.get("mean_happiness", 0),
            "mean_morale": m.get("mean_morale", 0),
            "gov_revenue": m.get("gov_revenue_this_tick", 0),
            "gov_spending": m.get("gov_spending_this_tick", 0),
        }
        history.append(row)

        print(f"{t:>5} | {row['unemployment_rate']*100:>6.1f}% | "
              f"${row['gdp']:>9,.0f} | {row['private_firms']:>8} | "
              f"${row['gov_cash']:>10,.0f} | ${row['pvt_median_cash']:>10,.0f} | "
              f"${row['pvt_mean_profit']:>10,.0f} | "
              f"${row['median_household_cash']:>9,.0f} | "
              f"{row['mean_happiness']:>.3f} | {row['mean_morale']:>.4f}")

    return history


def print_diff(default_hist, max_hist, ticks):
    """Print side-by-side diff of key metrics."""
    print(f"\n{'=' * 120}")
    print(f"  COMPARISON: Default Tax vs Max Tax (post-warmup, private firms)")
    print(f"{'=' * 120}")
    print(f"{'Tick':>5} | {'Unemp Def':>9} {'Unemp Max':>9} {'Î”':>7} | "
          f"{'GDP Def':>10} {'GDP Max':>10} {'Î”%':>7} | "
          f"{'PvtFirm D':>9} {'PvtFirm M':>9} | "
          f"{'PvtProfit D':>11} {'PvtProfit M':>11}")
    print("-" * 120)

    for i in range(ticks):
        d = default_hist[i]
        mx = max_hist[i]
        unemp_delta = (mx["unemployment_rate"] - d["unemployment_rate"]) * 100
        gdp_pct = ((mx["gdp"] - d["gdp"]) / max(d["gdp"], 1)) * 100

        print(f"{d['tick']:>5} | "
              f"{d['unemployment_rate']*100:>8.1f}% {mx['unemployment_rate']*100:>8.1f}% {unemp_delta:>+6.1f}% | "
              f"${d['gdp']:>9,.0f} ${mx['gdp']:>9,.0f} {gdp_pct:>+6.1f}% | "
              f"{d['private_firms']:>9} {mx['private_firms']:>9} | "
              f"${d['pvt_mean_profit']:>10,.0f} ${mx['pvt_mean_profit']:>10,.0f}")

    # Summary
    d_final = default_hist[-1]
    mx_final = max_hist[-1]
    d_avg_gdp = sum(r["gdp"] for r in default_hist) / len(default_hist)
    mx_avg_gdp = sum(r["gdp"] for r in max_hist) / len(max_hist)

    print(f"\n{'â”€' * 70}")
    print(f"SUMMARY after {ticks} post-warmup ticks:")
    print(f"  {'Metric':<25} {'Default':>12} {'Max Tax':>12} {'Delta':>12}")
    print(f"  {'â”€'*25} {'â”€'*12} {'â”€'*12} {'â”€'*12}")
    print(f"  {'Unemployment':.<25} {d_final['unemployment_rate']*100:>11.1f}% {mx_final['unemployment_rate']*100:>11.1f}% {(mx_final['unemployment_rate']-d_final['unemployment_rate'])*100:>+11.1f}%")
    print(f"  {'Final GDP':.<25} ${d_final['gdp']:>11,.0f} ${mx_final['gdp']:>11,.0f} ${mx_final['gdp']-d_final['gdp']:>+11,.0f}")
    print(f"  {'Avg GDP':.<25} ${d_avg_gdp:>11,.0f} ${mx_avg_gdp:>11,.0f} ${mx_avg_gdp-d_avg_gdp:>+11,.0f}")
    print(f"  {'Private Firms':.<25} {d_final['private_firms']:>12} {mx_final['private_firms']:>12} {mx_final['private_firms']-d_final['private_firms']:>+12}")
    print(f"  {'Gov Cash':.<25} ${d_final['gov_cash']:>11,.0f} ${mx_final['gov_cash']:>11,.0f} ${mx_final['gov_cash']-d_final['gov_cash']:>+11,.0f}")
    print(f"  {'Median HH Cash':.<25} ${d_final['median_household_cash']:>11,.0f} ${mx_final['median_household_cash']:>11,.0f} ${mx_final['median_household_cash']-d_final['median_household_cash']:>+11,.0f}")
    print(f"  {'Mean Happiness':.<25} {d_final['mean_happiness']:>12.3f} {mx_final['mean_happiness']:>12.3f} {mx_final['mean_happiness']-d_final['mean_happiness']:>+12.3f}")
    print(f"  {'Pvt Median Cash':.<25} ${d_final['pvt_median_cash']:>11,.0f} ${mx_final['pvt_median_cash']:>11,.0f} ${mx_final['pvt_median_cash']-d_final['pvt_median_cash']:>+11,.0f}")
    print(f"  {'Pvt Mean Profit':.<25} ${d_final['pvt_mean_profit']:>11,.0f} ${mx_final['pvt_mean_profit']:>11,.0f} ${mx_final['pvt_mean_profit']-d_final['pvt_mean_profit']:>+11,.0f}")
    print(f"  {'Pvt Mean Revenue':.<25} ${d_final['pvt_mean_revenue']:>11,.0f} ${mx_final['pvt_mean_revenue']:>11,.0f} ${mx_final['pvt_mean_revenue']-d_final['pvt_mean_revenue']:>+11,.0f}")
    print(f"  {'Gov Revenue (final)':.<25} ${d_final['gov_revenue']:>11,.0f} ${mx_final['gov_revenue']:>11,.0f} ${mx_final['gov_revenue']-d_final['gov_revenue']:>+11,.0f}")


def main():
    parser = argparse.ArgumentParser(description="Tax rate impact comparison (post-warmup)")
    parser.add_argument("--ticks", type=int, default=30, help="Post-warmup ticks to compare")
    parser.add_argument("--households", type=int, default=200)
    args = parser.parse_args()

    # Run warmup once, then deep-copy for two scenarios
    import copy
    base_economy = run_warmup(args.households)

    # Deep copy so both scenarios start from identical state
    import pickle
    state = pickle.dumps(base_economy)

    economy_a = pickle.loads(state)
    economy_b = pickle.loads(state)

    # Scenario A: Default tax rates (already set from warmup)
    default_hist = run_scenario(
        economy_a,
        "DEFAULT TAX (wage=15%, profit=20%, invest=10%)",
        {},
        args.ticks,
    )

    # Scenario B: Max tax rates applied post-warmup
    max_hist = run_scenario(
        economy_b,
        "MAX TAX (wage=50%, profit=50%, invest=30%)",
        {"wage_tax_rate": 0.50, "profit_tax_rate": 0.50, "investment_tax_rate": 0.30},
        args.ticks,
    )

    print_diff(default_hist, max_hist, args.ticks)


if __name__ == "__main__":
    main()

