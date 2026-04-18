"""Single Private Firm Tracker (Post-Warmup)

Runs warmup silently, then tracks one private (non-baseline) firm's
complete tick-by-tick state:
  revenue, wage bill, tax paid, profit after tax, cash balance,
  employees, and the hire/fire/hold decision each tick.

Shows whether the firm ever hits a decision boundary or just
accumulates cash forever.

Usage:
    python run_firm_tracker.py
    python run_firm_tracker.py --ticks 30 --firm-index 0
    python run_firm_tracker.py --profit-tax 0.50   # stress test
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy


def main():
    parser = argparse.ArgumentParser(description="Single private firm tracker (post-warmup)")
    parser.add_argument("--ticks", type=int, default=20, help="Post-warmup ticks to track")
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--firm-index", type=int, default=0,
                        help="Index into private firms list (default: 0 = first private firm)")
    parser.add_argument("--wage-tax", type=float, default=None)
    parser.add_argument("--profit-tax", type=float, default=None)
    parser.add_argument("--investment-tax", type=float, default=None)
    args = parser.parse_args()

    economy = create_large_economy(num_households=args.households)

    # Run warmup + let private firms spawn
    warmup = economy.warmup_ticks
    print(f"Running {warmup}-tick warmup...", end=" ", flush=True)
    for _ in range(warmup):
        economy.step()
    print(f"done (tick {economy.current_tick}).")

    # Run extra ticks until private firms exist (queued firms activate gradually post-warmup)
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
        print("ERROR: No private firms spawned within {max_settle} ticks post-warmup!")
        return

    # Apply tax overrides AFTER warmup
    if args.wage_tax is not None:
        economy.government.set_lever("wage_tax_rate", args.wage_tax)
    if args.profit_tax is not None:
        economy.government.set_lever("profit_tax_rate", args.profit_tax)
    if args.investment_tax is not None:
        economy.government.set_lever("investment_tax_rate", args.investment_tax)

    # Pick the private firm to track
    idx = min(args.firm_index, len(private_firms) - 1)
    firm = private_firms[idx]
    firm_id = firm.firm_id
    gov = economy.government

    print(f"\n{'=' * 120}")
    print(f"  TRACKING PRIVATE FIRM #{firm_id}: {firm.good_name} ({firm.good_category})")
    print(f"  Starting cash: ${firm.cash_balance:,.0f} | Wage offer: ${firm.wage_offer:.1f} | "
          f"Price: ${firm.price:.2f} | Employees: {len(firm.employees)}")
    print(f"  Tax rates: wage={gov.wage_tax_rate:.0%} profit={gov.profit_tax_rate:.0%} "
          f"invest={gov.investment_tax_rate:.0%}")
    print(f"  Post-warmup start: tick {economy.current_tick}")
    print(f"{'=' * 120}")

    header = (f"{'Tick':>4} | {'Revenue':>9} | {'WageBill':>9} | {'TaxPaid':>8} | "
              f"{'Profit':>9} | {'Cash':>11} | {'Empl':>4} | {'Δ':>4} | "
              f"{'Decision':>10} | {'Inv':>6} | {'Sold':>6} | {'Price':>7} | "
              f"{'Surv':>4} | {'Margin':>7}")
    print(header)
    print("-" * len(header))

    for t in range(1, args.ticks + 1):
        empl_before = 0
        for f in economy.firms:
            if f.firm_id == firm_id:
                empl_before = len(f.employees)
                break

        economy.step()

        # Find tracked firm
        tracked = None
        for f in economy.firms:
            if f.firm_id == firm_id:
                tracked = f
                break

        if tracked is None:
            print(f"{t:>4} | {'--- FIRM DIED ---':^100}")
            m = economy.get_economic_metrics()
            print(f"\n  Economy after death: {m.get('total_firms', 0)} firms, "
                  f"{m.get('unemployment_rate', 0)*100:.1f}% unemployment")
            break

        firm = tracked
        empl_after = len(firm.employees)
        delta = empl_after - empl_before

        wage_bill = sum(firm.actual_wages.get(eid, firm.wage_offer) for eid in firm.employees)
        revenue = firm.last_revenue
        profit = firm.last_profit
        costs = firm.last_tick_total_costs
        tax_paid = max(0, revenue - costs - profit)

        if delta > 0:
            decision = f"HIRE +{delta}"
        elif delta < 0:
            decision = f"FIRE {delta}"
        else:
            decision = "HOLD"

        survival = "!!" if firm.survival_mode else ""
        margin = (profit / revenue * 100) if revenue > 0 else 0

        print(f"{t:>4} | ${revenue:>8,.0f} | ${wage_bill:>8,.0f} | ${tax_paid:>7,.0f} | "
              f"${profit:>8,.0f} | ${firm.cash_balance:>10,.0f} | {empl_after:>4} | "
              f"{delta:>+4} | {decision:>10} | {firm.inventory_units:>5.0f} | "
              f"{firm.last_units_sold:>5.0f} | ${firm.price:>6.2f} | "
              f"{survival:>4} | {margin:>6.1f}%")

    # Final analysis
    if tracked is not None:
        print(f"\n{'─' * 70}")
        print(f"FIRM #{firm_id} ANALYSIS:")
        print(f"  Cash balance:     ${firm.cash_balance:>12,.0f}")
        print(f"  Employees:        {len(firm.employees):>12}")
        print(f"  Wage offer:       ${firm.wage_offer:>12.2f}")
        print(f"  Price:            ${firm.price:>12.2f}")
        print(f"  Inventory:        {firm.inventory_units:>12.0f} units")
        print(f"  Last revenue:     ${firm.last_revenue:>12,.0f}")
        print(f"  Last profit:      ${firm.last_profit:>12,.0f}")
        print(f"  Survival mode:    {firm.survival_mode}")
        print(f"  Burn mode:        {firm.burn_mode}")
        print(f"  Zero cash streak: {firm.zero_cash_streak}")

        if firm.last_revenue > 0:
            eff_tax = tax_paid / firm.last_revenue
            margin = firm.last_profit / firm.last_revenue
            rev_per_empl = firm.last_revenue / max(len(firm.employees), 1)
            cost_per_empl = wage_bill / max(len(firm.employees), 1)
            print(f"\n  Effective tax rate:  {eff_tax:.1%}")
            print(f"  Profit margin:      {margin:.1%}")
            print(f"  Revenue/employee:   ${rev_per_empl:,.0f}")
            print(f"  Wage cost/employee: ${cost_per_empl:,.0f}")
            print(f"  Cash runway:        {firm.cash_balance / max(wage_bill, 1):.1f} ticks of wages")


if __name__ == "__main__":
    main()
