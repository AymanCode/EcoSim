"""EcoSim Behavioral Test Suite (Post-Warmup)

Each test:
  1. Restores economy from a warmed-up snapshot (same starting state)
  2. Applies a policy shock or initial condition
  3. Runs N ticks
  4. Checks expected signs vs a no-shock control

Expected signs:
  Taxes:        contractionary for the taxed side
  Subsidies:    support demand / affordability
  Wage floors:  help workers, stress weak firms
  Public works: cut unemployment fast, cost government cash
  High profits: entry should follow
  Oversupply:   prices down, hiring down

Usage:
    python run_behavior_tests.py
    python run_behavior_tests.py --ticks 20 --households 400
    python run_behavior_tests.py --test wage_tax profit_tax   # run subset
"""

import argparse
import pickle
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_large_simulation import create_large_economy

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


# ─────────────────────────────────────────────────────────────────────────────
# Harness
# ─────────────────────────────────────────────────────────────────────────────

def build_snapshot(households: int) -> bytes:
    """Run warmup + settle until private firms spawn, return pickled economy."""
    economy = create_large_economy(num_households=households)
    warmup = economy.warmup_ticks
    print(f"  Warmup: {warmup} ticks...", end=" ", flush=True)
    for _ in range(warmup):
        economy.step()

    for _ in range(20):
        if any(not f.is_baseline for f in economy.firms):
            break
        economy.step()

    private = [f for f in economy.firms if not f.is_baseline]
    print(f"done. tick={economy.current_tick}, "
          f"firms={len(economy.firms)} ({len(private)} private)")
    return pickle.dumps(economy)


def restore(snapshot: bytes):
    return pickle.loads(snapshot)


def run_ticks(economy, n: int) -> list[dict]:
    """Step economy n times, collect metrics each tick."""
    rows = []
    for _ in range(n):
        economy.step()
        m = economy.get_economic_metrics()
        m["_pvt_firms"] = [f for f in economy.firms if not f.is_baseline]
        m["_all_firms"] = economy.firms
        rows.append(m)
    return rows


def avg(rows: list[dict], key: str) -> float:
    vals = [r.get(key, 0) for r in rows]
    return sum(vals) / max(len(vals), 1)


def final(rows: list[dict], key: str) -> float:
    return rows[-1].get(key, 0) if rows else 0


def pvt_avg(rows: list[dict], attr: str) -> float:
    """Average an attribute across private firms, averaged over ticks."""
    totals = []
    for r in rows:
        firms = r["_pvt_firms"]
        if firms:
            totals.append(sum(getattr(f, attr, 0) for f in firms) / len(firms))
    return sum(totals) / max(len(totals), 1)


def check(label: str, shock_val, ctrl_val, expected_sign: str, tolerance: float = 0.0):
    """
    expected_sign: '>' shock should be greater than control
                   '<' shock should be less than control
                   'up' shock[-1] > shock[0] (rising trend)
                   'down' shock[-1] < shock[0] (falling trend)
    """
    if expected_sign == '>':
        ok = shock_val > ctrl_val + tolerance
    elif expected_sign == '<':
        ok = shock_val < ctrl_val - tolerance
    else:
        ok = False
    status = PASS if ok else FAIL
    arrow = "↑" if expected_sign == ">" else "↓"
    print(f"    [{status}] {label}: shock={shock_val:.4g} ctrl={ctrl_val:.4g} "
          f"(expected shock {arrow} ctrl)")
    return status


def section(name: str):
    print(f"\n{'═' * 70}")
    print(f"  TEST: {name}")
    print(f"{'═' * 70}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_wage_tax_shock(snap, ticks):
    section("WAGE TAX SHOCK — raise wage_tax_rate 15% → 45%")
    print("  Expected: household cash growth slows, gov revenue rises, "
          "consumption softens (happiness/morale hit)")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("wage_tax_rate", 0.45)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov revenue (avg)", avg(shock, "gov_revenue_this_tick"),
              avg(ctrl, "gov_revenue_this_tick"), ">"),
        check("Median HH cash (final)", final(shock, "median_household_cash"),
              final(ctrl, "median_household_cash"), "<"),
        check("Mean happiness (final)", final(shock, "mean_happiness"),
              final(ctrl, "mean_happiness"), "<"),
        check("Total HH cash (final)", final(shock, "total_household_cash"),
              final(ctrl, "total_household_cash"), "<"),
    ]
    return results


def test_profit_tax_shock(snap, ticks):
    section("PROFIT TAX SHOCK — raise profit_tax_rate 20% → 48%")
    print("  Expected: firm after-tax cash falls, survival stress rises, "
          "private firm count may fall, entry slows")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("profit_tax_rate", 0.48)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov revenue (avg)", avg(shock, "gov_revenue_this_tick"),
              avg(ctrl, "gov_revenue_this_tick"), ">"),
        check("Pvt median firm cash (final)", final(shock, "median_firm_cash"),
              final(ctrl, "median_firm_cash"), "<"),
        check("Survival mode firms (avg)", avg(shock, "survival_mode_firm_count"),
              avg(ctrl, "survival_mode_firm_count"), ">"),
        check("Mean firm profit (pvt, avg)", pvt_avg(shock, "last_profit"),
              pvt_avg(ctrl, "last_profit"), "<"),
    ]
    return results


def test_benefit_shock(snap, ticks):
    section("UNEMPLOYMENT BENEFIT SHOCK — benefit_level neutral → crisis")
    print("  Expected: household cash improves, gov spending rises, benefit level rises,")
    print("  unemployed-not-searching falls (income support keeps people active in market)")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("benefit_level", "crisis")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov spending (avg)", avg(shock, "gov_spending_this_tick"),
              avg(ctrl, "gov_spending_this_tick"), ">"),
        check("Unemployment benefit (final)", final(shock, "unemployment_benefit"),
              final(ctrl, "unemployment_benefit"), ">"),
        # Higher benefit → people can afford to keep searching rather than give up
        check("Unemployed not searching (avg)", avg(shock, "labor_unemployed_not_searching"),
              avg(ctrl, "labor_unemployed_not_searching"), "<"),
        check("Median HH cash (final)", final(shock, "median_household_cash"),
              final(ctrl, "median_household_cash"), ">"),
    ]
    return results


def test_minimum_wage_binding(snap, ticks):
    section("MINIMUM WAGE BINDING — minimum_wage_policy neutral → high")
    print("  Expected: wage floor binding share rises, low-margin firms stressed, "
          "mean wage rises, failed hiring rises")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("minimum_wage_policy", "high")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Wage floor binding share (avg)", avg(shock, "wage_floor_binding_share"),
              avg(ctrl, "wage_floor_binding_share"), ">"),
        check("Mean wage (avg)", avg(shock, "mean_wage"),
              avg(ctrl, "mean_wage"), ">"),
        check("Minimum wage floor (final)", final(shock, "minimum_wage_floor"),
              final(ctrl, "minimum_wage_floor"), ">"),
        check("Survival mode firms (avg)", avg(shock, "survival_mode_firm_count"),
              avg(ctrl, "survival_mode_firm_count"), ">"),
    ]
    return results


def test_sector_subsidy(snap, ticks):
    section("SECTOR SUBSIDY — food sector at 50%")
    print("  Expected: gov subsidy spend rises, gov cash falls faster, "
          "distressed food firms fall, household happiness improves")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("sector_subsidy_target", "food")
    shock_eco.government.set_lever("sector_subsidy_level", 50)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov subsidy spend (avg)", avg(shock, "gov_subsidy_spend_this_tick"),
              avg(ctrl, "gov_subsidy_spend_this_tick"), ">"),
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
        check("Distressed food firms (avg)", avg(shock, "distressed_food_firms"),
              avg(ctrl, "distressed_food_firms"), "<"),
        check("Mean happiness (final)", final(shock, "mean_happiness"),
              final(ctrl, "mean_happiness"), ">"),
    ]
    return results


def test_housing_subsidy(snap, ticks):
    section("HOUSING SUBSIDY — housing sector at 50%")
    print("  Expected: gov subsidy spend rises, distressed housing firms fall, "
          "morale improves (shelter access), gov cash falls")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("sector_subsidy_target", "housing")
    shock_eco.government.set_lever("sector_subsidy_level", 50)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov subsidy spend (avg)", avg(shock, "gov_subsidy_spend_this_tick"),
              avg(ctrl, "gov_subsidy_spend_this_tick"), ">"),
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
        check("Mean morale (final)", final(shock, "mean_morale"),
              final(ctrl, "mean_morale"), ">"),
    ]
    return results


def test_public_works(snap, ticks):
    section("PUBLIC WORKS — turn on during base conditions")
    print("  Expected: public works jobs > 0, unemployment falls vs control.")
    print("  NOTE: net gov spending may not rise — public works replaces unemployment")
    print("  transfers, so the fiscal cost can offset. Test for jobs and unemployment only.")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("public_works", "on")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Public works jobs (avg)", avg(shock, "public_works_jobs"),
              avg(ctrl, "public_works_jobs"), ">"),
        check("Unemployment rate (avg)", avg(shock, "unemployment_rate"),
              avg(ctrl, "unemployment_rate"), "<"),
        # Public works firms show up in total firm count
        check("Total firms (avg)", avg(shock, "total_firms"),
              avg(ctrl, "total_firms"), ">"),
        # Unemployed total should fall
        check("Unemployed count (avg)", avg(shock, "unemployed_count"),
              avg(ctrl, "unemployed_count"), "<"),
    ]
    return results


def test_infrastructure_lag(snap, ticks):
    section("INFRASTRUCTURE LAG — infrastructure_spending none → high")
    print("  Expected: infrastructure productivity multiplier rises gradually, "
          "NOT a jump in tick 1. Gov cash falls faster.")

    shock_eco = restore(snap)
    shock_eco.government.set_lever("infrastructure_spending", "high")
    shock = run_ticks(shock_eco, ticks)

    tick1_prod = shock[0].get("infrastructure_productivity", 1.0)
    tickN_prod = shock[-1].get("infrastructure_productivity", 1.0)

    ctrl = run_ticks(restore(snap), ticks)

    results = [
        check("Infrastructure productivity rises over time",
              tickN_prod, tick1_prod, ">"),
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
        check("Infrastructure productivity > control (final)",
              final(shock, "infrastructure_productivity"),
              final(ctrl, "infrastructure_productivity"), ">"),
    ]
    # Flag if the jump happened mostly on tick 1
    total_gain = tickN_prod - shock[0].get("infrastructure_productivity", 1.0)
    tick1_gain = shock[1].get("infrastructure_productivity", 1.0) - tick1_prod if len(shock) > 1 else 0
    if total_gain > 0 and tick1_gain / total_gain > 0.8:
        print("    [WARN] >80% of productivity gain happened on tick 1 — lag structure may be too weak")

    return results


def test_technology_lag(snap, ticks):
    section("TECHNOLOGY LAG — technology_spending none → medium")
    print("  Expected: technology quality multiplier rises gradually, "
          "mean quality improves vs control over time.")

    shock_eco = restore(snap)
    shock_eco.government.set_lever("technology_spending", "medium")
    shock = run_ticks(shock_eco, ticks)
    ctrl = run_ticks(restore(snap), ticks)

    tick1_qual = shock[0].get("technology_quality", 1.0)
    tickN_qual = shock[-1].get("technology_quality", 1.0)

    results = [
        check("Tech quality multiplier rises over time", tickN_qual, tick1_qual, ">"),
        check("Tech quality > control (final)",
              final(shock, "technology_quality"),
              final(ctrl, "technology_quality"), ">"),
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
    ]
    return results


def test_zero_benefits(snap, ticks):
    section("ZERO BENEFITS — benefit_level neutral → low")
    print("  Expected: gov spending falls, bottom wealth percentile falls,")
    print("  unemployed-not-searching rises (no income → give up searching), happiness falls")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("benefit_level", "low")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov spending (avg)", avg(shock, "gov_spending_this_tick"),
              avg(ctrl, "gov_spending_this_tick"), "<"),
        # Without support, unemployed give up searching sooner
        check("Unemployed not searching (avg)", avg(shock, "labor_unemployed_not_searching"),
              avg(ctrl, "labor_unemployed_not_searching"), ">"),
        check("Mean happiness (final)", final(shock, "mean_happiness"),
              final(ctrl, "mean_happiness"), "<"),
        # Bottom 10% wealth should be worse off
        check("Wealth p10 (final)", final(shock, "wealth_p10"),
              final(ctrl, "wealth_p10"), "<"),
    ]
    return results


def test_low_tax_revenue_stress(snap, ticks):
    section("LOW TAX — wage_tax 15% → 5%, profit_tax 20% → 5%")
    print("  Expected: gov cash falls faster, gov revenue falls, "
          "HH take-home rises, firm cash rises slightly")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("wage_tax_rate", 0.05)
    shock_eco.government.set_lever("profit_tax_rate", 0.05)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov revenue (avg)", avg(shock, "gov_revenue_this_tick"),
              avg(ctrl, "gov_revenue_this_tick"), "<"),
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
        check("Median HH cash (final)", final(shock, "median_household_cash"),
              final(ctrl, "median_household_cash"), ">"),
        check("Total firm cash (final)", final(shock, "total_firm_cash"),
              final(ctrl, "total_firm_cash"), ">"),
    ]
    return results


def test_healthcare_capacity(snap, ticks):
    section("HEALTHCARE SUBSIDY — subsidize healthcare at 50%")
    print("  Expected: gov subsidy spend rises, mean health improves vs control.")
    print("  NOTE: with 200hh baseline has sufficient capacity so denied_count is 0.")
    print("  Testing health transmission and subsidy flow instead.")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("sector_subsidy_target", "healthcare")
    shock_eco.government.set_lever("sector_subsidy_level", 50)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov subsidy spend (avg)", avg(shock, "gov_subsidy_spend_this_tick"),
              avg(ctrl, "gov_subsidy_spend_this_tick"), ">"),
        check("Mean health (final)", final(shock, "mean_health"),
              final(ctrl, "mean_health"), ">"),
        # Healthcare queue depth should be lower or equal when subsidized
        check("Healthcare queue depth (avg)", avg(shock, "healthcare_queue_depth"),
              avg(ctrl, "healthcare_queue_depth"), "<"),
    ]
    return results


def test_gini_progressive_tax(snap, ticks):
    section("FLAT WAGE TAX REDISTRIBUTION — wage 30% vs wage 15%")
    print("  NOTE: a flat rate hike taxes everyone proportionally. Wealthy households")
    print("  have accumulated savings (non-wage income) so a flat hike may NOT compress")
    print("  Gini. Testing what actually happens — gov revenue rises, total HH cash falls.")
    print("  True redistribution requires bracket shape control, not just rate level.")

    ctrl = run_ticks(restore(snap), ticks)  # 15% wage tax (default)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("wage_tax_rate", 0.30)
    shock = run_ticks(shock_eco, ticks)

    results = [
        # What we CAN assert: gov gets more revenue, total HH cash falls
        check("Gov revenue (avg)", avg(shock, "gov_revenue_this_tick"),
              avg(ctrl, "gov_revenue_this_tick"), ">"),
        check("Total HH cash (final)", final(shock, "total_household_cash"),
              final(ctrl, "total_household_cash"), "<"),
        # Wealth_p90 should fall more than p10 (proportional hit hurts high earners more in abs terms)
        check("Wealth p90 (final)", final(shock, "wealth_p90"),
              final(ctrl, "wealth_p90"), "<"),
    ]
    return results


def test_fiscal_collapse(snap, ticks):
    section("FISCAL COLLAPSE — max spending, zero tax")
    print("  Expected: gov cash craters, spending_efficiency falls, "
          "eventually transfers get squeezed")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("wage_tax_rate", 0.0)
    shock_eco.government.set_lever("profit_tax_rate", 0.0)
    shock_eco.government.set_lever("benefit_level", "crisis")
    shock_eco.government.set_lever("infrastructure_spending", "high")
    shock_eco.government.set_lever("technology_spending", "medium")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Gov cash (final)", final(shock, "government_cash"),
              final(ctrl, "government_cash"), "<"),
        check("Spending efficiency (final)", final(shock, "spending_efficiency"),
              final(ctrl, "spending_efficiency"), "<"),
        check("Gov revenue (avg)", avg(shock, "gov_revenue_this_tick"),
              avg(ctrl, "gov_revenue_this_tick"), "<"),
    ]
    return results


def test_burn_mode_trigger(snap, ticks):
    section("BURN MODE TRIGGER — profit_tax 48% + no subsidy, watch firm stress")
    print("  Expected: burn_mode_firm_count and survival_mode_firm_count rise, "
          "zero_cash_firm_count rises, bankruptcies may appear")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("profit_tax_rate", 0.48)
    shock_eco.government.set_lever("wage_tax_rate", 0.40)
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Burn mode firms (avg)", avg(shock, "burn_mode_firm_count"),
              avg(ctrl, "burn_mode_firm_count"), ">"),
        check("Survival mode firms (avg)", avg(shock, "survival_mode_firm_count"),
              avg(ctrl, "survival_mode_firm_count"), ">"),
        check("Zero cash firms (avg)", avg(shock, "zero_cash_firm_count"),
              avg(ctrl, "zero_cash_firm_count"), ">"),
    ]
    return results


def test_inventory_pressure(snap, ticks):
    section("INVENTORY PRESSURE — low minimum wage forces weak demand")
    print("  Expected: with low min wage, household spending power falls, "
          "inventory_pressure_firm_count rises, weak_demand_firm_count rises")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("minimum_wage_policy", "low")
    shock_eco.government.set_lever("benefit_level", "low")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Inventory pressure firms (avg)", avg(shock, "inventory_pressure_firm_count"),
              avg(ctrl, "inventory_pressure_firm_count"), ">"),
        check("Weak demand firms (avg)", avg(shock, "weak_demand_firm_count"),
              avg(ctrl, "weak_demand_firm_count"), ">"),
        check("Median HH cash (final)", final(shock, "median_household_cash"),
              final(ctrl, "median_household_cash"), "<"),
    ]
    return results


def test_skills_vs_wages(snap, ticks):
    section("SKILLS TRANSMISSION — technology_spending grows mean_quality")
    print("  Expected: technology spending improves quality_multiplier, "
          "which should feed into effective mean_quality of goods")

    ctrl = run_ticks(restore(snap), ticks)

    shock_eco = restore(snap)
    shock_eco.government.set_lever("technology_spending", "medium")
    shock = run_ticks(shock_eco, ticks)

    results = [
        check("Effective mean quality (final)", final(shock, "effective_mean_quality"),
              final(ctrl, "effective_mean_quality"), ">"),
        check("Technology quality multiplier (final)", final(shock, "technology_quality"),
              final(ctrl, "technology_quality"), ">"),
    ]
    return results


def test_deficit_ratio(snap, ticks):
    section("DEFICIT TRACKING — high spending vs high tax")
    print("  Expected: deficit_ratio rises under spend-heavy policy, "
          "falls under high-tax policy vs control")

    # High spend scenario
    spend_eco = restore(snap)
    spend_eco.government.set_lever("benefit_level", "crisis")
    spend_eco.government.set_lever("infrastructure_spending", "high")
    spend_eco.government.set_lever("wage_tax_rate", 0.05)
    spend = run_ticks(spend_eco, ticks)

    # High tax scenario
    tax_eco = restore(snap)
    tax_eco.government.set_lever("wage_tax_rate", 0.40)
    tax_eco.government.set_lever("profit_tax_rate", 0.40)
    tax = run_ticks(tax_eco, ticks)

    results = [
        check("Deficit ratio: spend > tax (final)",
              final(spend, "deficit_ratio"), final(tax, "deficit_ratio"), ">"),
        check("Spending efficiency: tax > spend (final)",
              final(tax, "spending_efficiency"), final(spend, "spending_efficiency"), ">"),
    ]
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Registry — (function, min_ticks)
# min_ticks: minimum ticks needed to see the effect. --ticks is floored to this.
# ─────────────────────────────────────────────────────────────────────────────

ALL_TESTS = {
    # name:             (function,                    min_ticks)
    "wage_tax":         (test_wage_tax_shock,         20),
    "profit_tax":       (test_profit_tax_shock,       40),  # survival mode needs time to erode cash reserves
    "benefit":          (test_benefit_shock,          20),
    "min_wage":         (test_minimum_wage_binding,   40),  # survival mode same issue
    "food_subsidy":     (test_sector_subsidy,         20),
    "housing_subsidy":  (test_housing_subsidy,        20),
    "public_works":     (test_public_works,           20),
    "infra_lag":        (test_infrastructure_lag,     20),
    "tech_lag":         (test_technology_lag,         20),
    "zero_benefits":    (test_zero_benefits,          20),
    "low_tax":          (test_low_tax_revenue_stress, 20),
    "healthcare":       (test_healthcare_capacity,    20),
    "gini_progressive": (test_gini_progressive_tax,  20),
    "fiscal_collapse":  (test_fiscal_collapse,        50),  # fiscal pressure is rolling, so give it time
    "burn_mode":        (test_burn_mode_trigger,      50),  # firms are cash-rich post-warmup
    "inventory":        (test_inventory_pressure,     20),
    "skills":           (test_skills_vs_wages,        20),
    "deficit":          (test_deficit_ratio,          50),  # fiscal pressure is rolling, so give it time
}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EcoSim behavioral test suite")
    parser.add_argument("--ticks", type=int, default=20,
                        help="Baseline ticks per test. Tests with min_ticks > this use their minimum (default 20)")
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--test", nargs="*", choices=list(ALL_TESTS.keys()),
                        help="Run specific tests (default: all)")
    args = parser.parse_args()

    tests_to_run = args.test or list(ALL_TESTS.keys())

    print(f"\nEcoSim Behavioral Test Suite")
    print(f"  households={args.households}, baseline_ticks={args.ticks} (some tests use more)")
    print(f"  tests={tests_to_run}")

    print(f"\nBuilding warmed-up snapshot...")
    snap = build_snapshot(args.households)

    summary = {}
    for name in tests_to_run:
        fn, min_ticks = ALL_TESTS[name]
        ticks = max(args.ticks, min_ticks)
        if ticks > args.ticks:
            print(f"\n  (Using {ticks} ticks for '{name}' — needs at least {min_ticks})")
        results = fn(snap, ticks)
        passed = sum(1 for r in results if r == PASS)
        total = len(results)
        summary[name] = (passed, total, ticks)

    # Final scoreboard
    print(f"\n{'═' * 70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'═' * 70}")
    total_pass = 0
    total_checks = 0
    for name, (passed, total, ticks) in summary.items():
        bar = "█" * passed + "░" * (total - passed)
        label = PASS if passed == total else FAIL
        print(f"  [{label}] {name:<20} {passed}/{total}  {bar}  ({ticks}t)")
        total_pass += passed
        total_checks += total

    print(f"\n  Overall: {total_pass}/{total_checks} checks passed")
    if total_pass == total_checks:
        print("  Economy mechanics look correct.")
    elif total_pass / max(total_checks, 1) >= 0.75:
        print("  Most mechanics working — review FAILs above.")
    else:
        print("  Several mechanics not responding as expected — investigate FAILs.")


if __name__ == "__main__":
    main()
