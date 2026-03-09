"""
EcoSim 250-tick diagnostic run.
Prints key economic metrics every 25 ticks and a final summary.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import time
import numpy as np
from run_large_simulation import create_large_economy

NUM_TICKS = 250
SNAPSHOT_INTERVAL = 25
NUM_HOUSEHOLDS = 1000  # Smaller for speed

print("=" * 70)
print(f"EcoSim Diagnostic Run: {NUM_TICKS} ticks, {NUM_HOUSEHOLDS} households")
print("=" * 70)

economy = create_large_economy(num_households=NUM_HOUSEHOLDS)

# Storage for time series
history = []

t0 = time.time()
for tick in range(NUM_TICKS):
    economy.step()

    # Collect metrics every tick
    metrics = economy.get_economic_metrics()

    # Add extra detail
    households = economy.households
    firms = economy.firms

    employed = [h for h in households if h.is_employed]
    unemployed = [h for h in households if not h.is_employed]

    total_goods_per_hh = [sum(h.goods_inventory.values()) for h in households]
    food_per_hh = []
    service_per_hh = []
    for h in households:
        food = sum(qty for good, qty in h.goods_inventory.items()
                   if "food" in good.lower())
        svc = sum(qty for good, qty in h.goods_inventory.items()
                  if "service" in good.lower())
        food_per_hh.append(food)
        service_per_hh.append(svc)

    cash_arr = np.array([h.cash_balance for h in households])
    happiness_arr = np.array([h.happiness for h in households])
    morale_arr = np.array([h.morale for h in households])
    health_arr = np.array([h.health for h in households])

    firm_cash = [f.cash_balance for f in firms]
    firm_inv = [f.inventory_units for f in firms]
    firm_employees = [len(f.employees) for f in firms]

    snapshot = {
        "tick": economy.current_tick,
        "unemployment_rate": metrics.get("unemployment_rate", 0),
        "mean_happiness": float(happiness_arr.mean()),
        "median_happiness": float(np.median(happiness_arr)),
        "min_happiness": float(happiness_arr.min()),
        "happiness_below_25": int((happiness_arr < 0.25).sum()),
        "happiness_below_10": int((happiness_arr < 0.10).sum()),
        "mean_morale": float(morale_arr.mean()),
        "mean_health": float(health_arr.mean()),
        "median_health": float(np.median(health_arr)),
        "health_below_70": int((health_arr < 0.70).sum()),
        "health_below_30": int((health_arr < 0.30).sum()),
        "mean_cash": float(cash_arr.mean()),
        "median_cash": float(np.median(cash_arr)),
        "cash_below_100": int((cash_arr < 100).sum()),
        "cash_below_0": int((cash_arr < 0).sum()),
        "mean_goods": float(np.mean(total_goods_per_hh)),
        "mean_food": float(np.mean(food_per_hh)),
        "mean_services": float(np.mean(service_per_hh)),
        "total_firms": len(firms),
        "mean_firm_cash": float(np.mean(firm_cash)) if firm_cash else 0,
        "total_firm_inventory": float(sum(firm_inv)),
        "mean_firm_employees": float(np.mean(firm_employees)) if firm_employees else 0,
        "gdp_this_tick": metrics.get("gdp_this_tick", 0),
        "gini": metrics.get("gini_coefficient", 0),
        "govt_cash": metrics.get("government_cash", 0),
        "social_multiplier": economy.government.social_happiness_multiplier,
        "mean_wage": metrics.get("mean_wage", 0),
        "employed_count": len(employed),
        "num_bankrupt_firms": 0,  # tracked below
    }
    history.append(snapshot)

    if (tick + 1) % SNAPSHOT_INTERVAL == 0:
        s = snapshot
        elapsed = time.time() - t0
        print(f"\n--- Tick {s['tick']} ({elapsed:.1f}s) ---")
        print(f"  Employment:   {s['employed_count']}/{NUM_HOUSEHOLDS} "
              f"(unemp={s['unemployment_rate']:.1%})")
        print(f"  Happiness:    mean={s['mean_happiness']:.3f}  "
              f"median={s['median_happiness']:.3f}  "
              f"<0.25={s['happiness_below_25']}  <0.10={s['happiness_below_10']}")
        print(f"  Morale:       mean={s['mean_morale']:.3f}")
        print(f"  Health:       mean={s['mean_health']:.3f}  "
              f"median={s['median_health']:.3f}  "
              f"<0.70={s['health_below_70']}  <0.30={s['health_below_30']}")
        print(f"  Cash:         mean=${s['mean_cash']:.0f}  "
              f"median=${s['median_cash']:.0f}  "
              f"<$100={s['cash_below_100']}  <$0={s['cash_below_0']}")
        print(f"  Goods:        mean={s['mean_goods']:.1f}  "
              f"food={s['mean_food']:.1f}  services={s['mean_services']:.1f}")
        print(f"  Firms:        {s['total_firms']} active  "
              f"avg_emp={s['mean_firm_employees']:.1f}  "
              f"avg_cash=${s['mean_firm_cash']:.0f}")
        print(f"  Inventory:    {s['total_firm_inventory']:.0f} total units")
        print(f"  GDP/tick:     ${s['gdp_this_tick']:.0f}  "
              f"Gini={s['gini']:.3f}  "
              f"Wage=${s['mean_wage']:.1f}")
        print(f"  Government:   cash=${s['govt_cash']:.0f}  "
              f"social_mult={s['social_multiplier']:.4f}")

elapsed = time.time() - t0
print(f"\n{'=' * 70}")
print(f"SIMULATION COMPLETE: {NUM_TICKS} ticks in {elapsed:.1f}s")
print(f"{'=' * 70}")

# Final analysis
print("\n## TREND ANALYSIS ##\n")

# Compare first 25 ticks vs last 25 ticks
early = history[:25]
late = history[-25:]

def avg(lst, key):
    return sum(s[key] for s in lst) / len(lst)

metrics_to_compare = [
    ("Unemployment Rate", "unemployment_rate", ".1%"),
    ("Mean Happiness", "mean_happiness", ".3f"),
    ("Mean Morale", "mean_morale", ".3f"),
    ("Mean Health", "mean_health", ".3f"),
    ("Mean Cash", "mean_cash", ",.0f"),
    ("GDP/tick", "gdp_this_tick", ",.0f"),
    ("Gini", "gini", ".3f"),
    ("Mean Food Inventory", "mean_food", ".1f"),
    ("Mean Services Inventory", "mean_services", ".1f"),
    ("Households <$100", "cash_below_100", ".0f"),
    ("Happiness <0.25", "happiness_below_25", ".0f"),
    ("Health <0.70", "health_below_70", ".0f"),
    ("Total Firms", "total_firms", ".0f"),
    ("Gov Cash", "govt_cash", ",.0f"),
    ("Social Multiplier", "social_multiplier", ".4f"),
]

print(f"{'Metric':<25} {'Ticks 1-25':>14} {'Ticks 226-250':>14} {'Delta':>10}")
print("-" * 65)
for label, key, fmt in metrics_to_compare:
    e = avg(early, key)
    l = avg(late, key)
    delta = l - e
    if fmt == ".1%":
        print(f"{label:<25} {e:>14.1%} {l:>14.1%} {delta:>+10.1%}")
    else:
        e_str = f"{e:{fmt}}"
        l_str = f"{l:{fmt}}"
        d_str = f"{delta:+{fmt}}"
        print(f"{label:<25} {e_str:>14} {l_str:>14} {d_str:>10}")

# Identify problems
print("\n## IDENTIFIED ISSUES ##\n")

final = history[-1]
issues = []

if final["unemployment_rate"] > 0.15:
    issues.append(f"HIGH UNEMPLOYMENT: {final['unemployment_rate']:.1%} at end of sim")
if final["mean_happiness"] < 0.4:
    issues.append(f"LOW HAPPINESS: mean={final['mean_happiness']:.3f} at end of sim")
if final["happiness_below_25"] > NUM_HOUSEHOLDS * 0.1:
    issues.append(f"HAPPINESS CRISIS: {final['happiness_below_25']} households below 0.25")
if final["mean_morale"] < 0.3:
    issues.append(f"LOW MORALE: mean={final['mean_morale']:.3f}")
if final["mean_health"] < 0.5:
    issues.append(f"HEALTH CRISIS: mean={final['mean_health']:.3f}")
if final["health_below_70"] > NUM_HOUSEHOLDS * 0.5:
    issues.append(f"WIDESPREAD ILL HEALTH: {final['health_below_70']} households below 0.70")
if final["cash_below_100"] > NUM_HOUSEHOLDS * 0.3:
    issues.append(f"MASS POVERTY: {final['cash_below_100']} households below $100")
if final["mean_food"] < 2.0:
    issues.append(f"FOOD SHORTAGE: mean food inventory={final['mean_food']:.1f}")
if final["gini"] > 0.6:
    issues.append(f"HIGH INEQUALITY: Gini={final['gini']:.3f}")
if final["total_firms"] < 5:
    issues.append(f"FIRM COLLAPSE: only {final['total_firms']} firms remaining")
if avg(late, "gdp_this_tick") < avg(early, "gdp_this_tick") * 0.5:
    issues.append(f"GDP COLLAPSED: dropped >50% from early to late sim")

# Check for death spirals
happiness_trend = [s["mean_happiness"] for s in history]
if len(happiness_trend) > 50:
    first_50 = np.mean(happiness_trend[:50])
    last_50 = np.mean(happiness_trend[-50:])
    if last_50 < first_50 * 0.7:
        issues.append(f"HAPPINESS DEATH SPIRAL: dropped from {first_50:.3f} to {last_50:.3f}")

health_trend = [s["mean_health"] for s in history]
if len(health_trend) > 50:
    first_50 = np.mean(health_trend[:50])
    last_50 = np.mean(health_trend[-50:])
    if last_50 < first_50 * 0.7:
        issues.append(f"HEALTH DEATH SPIRAL: dropped from {first_50:.3f} to {last_50:.3f}")

morale_trend = [s["mean_morale"] for s in history]
if len(morale_trend) > 50:
    first_50 = np.mean(morale_trend[:50])
    last_50 = np.mean(morale_trend[-50:])
    if last_50 < first_50 * 0.5:
        issues.append(f"MORALE DEATH SPIRAL: dropped from {first_50:.3f} to {last_50:.3f}")

# Check firm inventory glut
inv_trend = [s["total_firm_inventory"] for s in history]
if len(inv_trend) > 50:
    last_inv = np.mean(inv_trend[-25:])
    early_inv = np.mean(inv_trend[:25])
    if last_inv > early_inv * 3:
        issues.append(f"INVENTORY GLUT: firm inventory grew {last_inv/max(early_inv,1):.1f}x")

# Check government cash drain
govt_trend = [s["govt_cash"] for s in history]
if govt_trend[-1] < 0:
    issues.append(f"GOVERNMENT BANKRUPT: cash=${govt_trend[-1]:,.0f}")
elif govt_trend[-1] < govt_trend[0] * 0.1:
    issues.append(f"GOVERNMENT CASH CRISIS: dropped to ${govt_trend[-1]:,.0f}")

if not issues:
    issues.append("No critical issues detected!")

for i, issue in enumerate(issues, 1):
    print(f"  {i}. {issue}")

print(f"\nDone.")
