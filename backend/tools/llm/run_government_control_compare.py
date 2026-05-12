from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (
    BACKEND_ROOT,
    TOOLS_ROOT,
    TOOLS_ROOT / "analysis",
    TOOLS_ROOT / "checks",
    TOOLS_ROOT / "llm",
    TOOLS_ROOT / "runners",
):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)

import argparse
import contextlib
import copy
import io
import json
import random
import time
from collections import Counter
from typing import Dict, List

import numpy as np

from agents import GovernmentAgent
from config import CONFIG
from run_large_simulation import create_large_economy
from run_llm_government_test import (
    build_firm_financial_rows,
    build_flow_diagnostics,
    build_labor_diagnostics,
    build_unmet_demand_summary,
    build_wage_reservation_summary,
)


SCENARIOS = ("no_government", "conservative_scripted")


def parse_args():
    parser = argparse.ArgumentParser(description="Run non-LLM government control comparisons.")
    parser.add_argument("--ticks", type=int, default=200)
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--interval", type=int, default=4)
    parser.add_argument("--first-decision-tick", type=int, default=15)
    parser.add_argument("--warmup-ticks", type=int, default=10)
    parser.add_argument("--output-json", type=str, default="control_compare_latest.json")
    parser.add_argument("--output-md", type=str, default="control_compare_latest.md")
    return parser.parse_args()


def _dist(values: List[float]) -> Dict[str, float]:
    values = [float(value) for value in values if value is not None]
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    arr = np.asarray(values, dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "median": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def _avg(rows: List[Dict[str, object]], key: str) -> float:
    values = [float(row.get(key, 0.0) or 0.0) for row in rows]
    return sum(values) / max(1, len(values))


def _min(rows: List[Dict[str, object]], key: str) -> float:
    values = [float(row.get(key, 0.0) or 0.0) for row in rows]
    return min(values) if values else 0.0


def _max(rows: List[Dict[str, object]], key: str) -> float:
    values = [float(row.get(key, 0.0) or 0.0) for row in rows]
    return max(values) if values else 0.0


def _set_government_to_noop(government: GovernmentAgent) -> None:
    government.wage_tax_rate = 0.0
    government.profit_tax_rate = 0.0
    government.investment_tax_rate = 0.0
    government.benefit_level = "low"
    government.unemployment_benefit_level = 0.0
    government.transfer_budget = 0.0
    government.public_works_toggle = "off"
    government.minimum_wage_policy = "low"
    government.sector_subsidy_target = "none"
    government.sector_subsidy_level = 0
    government.infrastructure_spending = "none"
    government.technology_spending = "none"
    government.bailout_policy = "off"
    government.bailout_target = "none"
    government.bailout_budget = 0.0
    government.apply_policy_levers()
    # apply_policy_levers derives benefit/min-cash from benefit_level; force the
    # no-government control back to zero after derived policy fields are updated.
    government.unemployment_benefit_level = 0.0
    government.min_cash_threshold = 0.0


def _configure_economy_for_scenario(economy, scenario: str) -> None:
    CONFIG.llm.enable_llm_government = False
    economy.configure_stabilizers(government=False)

    if scenario == "no_government":
        _set_government_to_noop(economy.government)
        CONFIG.government.auto_working_capital_backstop = False
        for firm in economy.firms:
            if hasattr(firm, "property_tax_rate"):
                firm.property_tax_rate = 0.0
        for firm in economy.queued_firms:
            if hasattr(firm, "property_tax_rate"):
                firm.property_tax_rate = 0.0
        economy.post_warmup_stimulus_ticks = 0
        economy.post_warmup_stimulus_duration = 0

        def _disabled_post_warmup_stimulus():
            economy.last_tick_gov_post_warmup_stimulus = 0.0
            economy.post_warmup_stimulus_ticks = 0

        economy._apply_post_warmup_stimulus = _disabled_post_warmup_stimulus
        return

    if scenario == "conservative_scripted":
        CONFIG.government.auto_working_capital_backstop = False
        economy.government.public_works_toggle = "off"
        economy.government.sector_subsidy_target = "none"
        economy.government.sector_subsidy_level = 0
        economy.government.bailout_policy = "off"
        economy.government.bailout_target = "none"
        economy.government.bailout_budget = 0.0
        economy.government.infrastructure_spending = "none"
        economy.government.technology_spending = "none"
        economy.government.benefit_level = "neutral"
        economy.government.apply_policy_levers()
        return

    raise ValueError(f"Unknown scenario: {scenario}")


def _largest_explicit_unmet_sector(unmet_summary: Dict[str, object]) -> str:
    explicit = dict(unmet_summary.get("explicit_goods_unmet", {}) or {})
    candidates = {
        str(key).lower(): float(value or 0.0)
        for key, value in explicit.items()
        if str(key).lower() in {"food", "services"}
    }
    housing_failures = float(unmet_summary.get("housing_failure_count", 0.0) or 0.0)
    healthcare_queue = float(unmet_summary.get("healthcare_queue_depth", 0.0) or 0.0)
    candidates["housing"] = housing_failures
    candidates["healthcare"] = healthcare_queue
    sector, value = max(candidates.items(), key=lambda item: item[1])
    return sector if value > 0.0 else "none"


def _apply_conservative_policy(economy, metrics: Dict[str, object]) -> Dict[str, object]:
    gov = economy.government
    cash = float(metrics.get("government_cash", gov.cash_balance) or gov.cash_balance)
    unemployment = float(metrics.get("labor_force_unemployment_rate", metrics.get("unemployment_rate", 0.0)) or 0.0)
    gdp = float(metrics.get("gdp_this_tick", 0.0) or 0.0)
    unmet = build_unmet_demand_summary(economy)
    target_sector = _largest_explicit_unmet_sector(unmet)

    before = gov.to_dict()

    # Default to no discretionary spending unless a rule below authorizes it.
    gov.public_works_toggle = "off"
    gov.infrastructure_spending = "none"
    gov.technology_spending = "none"
    gov.bailout_policy = "off"
    gov.bailout_target = "none"
    gov.bailout_budget = 0.0

    if cash < 0.0:
        gov.benefit_level = "low"
        gov.sector_subsidy_target = "none"
        gov.sector_subsidy_level = 0
        gov.wage_tax_rate = min(0.20, max(float(gov.wage_tax_rate), 0.15))
        gov.profit_tax_rate = min(0.25, max(float(gov.profit_tax_rate), 0.20))
        reason = "cash_negative_austerity"
    elif cash < 10_000.0:
        gov.benefit_level = "neutral"
        gov.sector_subsidy_target = "none"
        gov.sector_subsidy_level = 0
        gov.wage_tax_rate = min(0.15, float(gov.wage_tax_rate))
        gov.profit_tax_rate = min(0.20, float(gov.profit_tax_rate))
        reason = "low_cash_hold"
    elif unemployment >= 0.30 and cash > max(50_000.0, 5.0 * max(gdp, 1.0)):
        gov.benefit_level = "high"
        if target_sector in {"food", "housing", "healthcare"}:
            gov.sector_subsidy_target = target_sector
            gov.sector_subsidy_level = 10
        else:
            gov.sector_subsidy_target = "none"
            gov.sector_subsidy_level = 0
        gov.wage_tax_rate = min(0.10, float(gov.wage_tax_rate))
        gov.profit_tax_rate = min(0.15, float(gov.profit_tax_rate))
        reason = "high_unemployment_targeted_support"
    elif unemployment >= 0.20 and cash > 25_000.0:
        gov.benefit_level = "neutral"
        if target_sector in {"food", "housing", "healthcare"}:
            gov.sector_subsidy_target = target_sector
            gov.sector_subsidy_level = 10
        else:
            gov.sector_subsidy_target = "none"
            gov.sector_subsidy_level = 0
        gov.wage_tax_rate = min(0.12, float(gov.wage_tax_rate))
        gov.profit_tax_rate = min(0.18, float(gov.profit_tax_rate))
        reason = "warning_unemployment_modest_support"
    else:
        gov.benefit_level = "neutral"
        gov.sector_subsidy_target = "none"
        gov.sector_subsidy_level = 0
        gov.wage_tax_rate = min(0.15, float(gov.wage_tax_rate))
        gov.profit_tax_rate = min(0.20, float(gov.profit_tax_rate))
        reason = "normal_hold"

    gov.minimum_wage_policy = "neutral"
    gov.apply_policy_levers()
    after = gov.to_dict()
    changes = {
        key: after.get(key)
        for key, old_value in before.items()
        if after.get(key) != old_value
    }
    return {
        "tick": int(economy.current_tick),
        "reason": reason,
        "target_sector": target_sector,
        "cash": cash,
        "gdp": gdp,
        "unemployment": unemployment,
        "changes": changes,
    }


def _collect_final_summary(economy, rows: List[Dict[str, object]], decisions: List[Dict[str, object]]) -> Dict[str, object]:
    final = rows[-1] if rows else {}
    private_real_firms = [
        firm for firm in economy.firms
        if not bool(getattr(firm, "is_baseline", False))
        and (getattr(firm, "good_category", "") or "").lower() in {"food", "services"}
    ]
    firms = list(getattr(economy, "firms", []) or [])
    households = list(getattr(economy, "households", []) or [])
    can_work = [h for h in households if bool(getattr(h, "can_work", True))]
    employed = [h for h in households if bool(getattr(h, "is_employed", False))]
    unemployed_can_work = [
        h for h in households
        if not bool(getattr(h, "is_employed", False)) and bool(getattr(h, "can_work", True))
    ]

    firm_financial_rows = build_firm_financial_rows(economy)
    unmet_summary = build_unmet_demand_summary(economy)
    wage_summary = build_wage_reservation_summary(economy)
    flow = build_flow_diagnostics(economy)
    labor = build_labor_diagnostics(economy, final)

    max_expected_to_observed = max(
        (
            float(getattr(firm, "expected_sales_units", 0.0) or 0.0)
            / max(1.0, float(getattr(firm, "last_tick_observed_demand_units", 0.0) or 0.0))
            for firm in private_real_firms
        ),
        default=0.0,
    )
    negative_counts = {
        "cash": sum(1 for row in firm_financial_rows if row["negative_cash"]),
        "profit": sum(1 for row in firm_financial_rows if row["negative_profit"]),
        "net_worth": sum(1 for row in firm_financial_rows if row["negative_net_worth"]),
    }
    working_capital_denials = Counter(
        getattr(firm, "last_working_capital_denial_reason", "") or "candidate"
        for firm in private_real_firms
    )
    hiring_block_reasons = Counter(
        getattr(firm, "last_hiring_block_reason", "") or "planned_hires_positive"
        for firm in private_real_firms
    )

    return {
        "final": {
            "tick": int(economy.current_tick),
            "government_cash": float(final.get("government_cash", 0.0) or 0.0),
            "gdp": float(final.get("gdp_this_tick", 0.0) or 0.0),
            "unemployment_rate": float(final.get("unemployment_rate", 0.0) or 0.0),
            "labor_force_unemployment_rate": float(final.get("labor_force_unemployment_rate", 0.0) or 0.0),
            "jobless_rate_total_population": float(final.get("jobless_rate_total_population", 0.0) or 0.0),
            "cannot_work_rate": float(final.get("cannot_work_rate", 0.0) or 0.0),
            "cannot_work_count": int(final.get("cannot_work_count", 0.0) or 0),
            "mean_health": float(final.get("mean_health", 0.0) or 0.0),
            "mean_happiness": float(final.get("mean_happiness", 0.0) or 0.0),
            "mean_morale": float(final.get("mean_morale", 0.0) or 0.0),
            "mean_wage": float(final.get("mean_wage", 0.0) or 0.0),
            "median_household_cash": float(final.get("median_household_cash", 0.0) or 0.0),
            "total_firms": int(final.get("total_firms", 0.0) or 0),
            "survival_mode_firms": int(final.get("survival_mode_firm_count", 0.0) or 0),
            "burn_mode_firms": int(final.get("burn_mode_firm_count", 0.0) or 0),
        },
        "averages": {
            "government_cash": _avg(rows, "government_cash"),
            "gdp": _avg(rows, "gdp_this_tick"),
            "unemployment_rate": _avg(rows, "unemployment_rate"),
            "labor_force_unemployment_rate": _avg(rows, "labor_force_unemployment_rate"),
            "jobless_rate_total_population": _avg(rows, "jobless_rate_total_population"),
            "cannot_work_rate": _avg(rows, "cannot_work_rate"),
            "mean_health": _avg(rows, "mean_health"),
            "mean_happiness": _avg(rows, "mean_happiness"),
            "mean_morale": _avg(rows, "mean_morale"),
            "mean_wage": _avg(rows, "mean_wage"),
        },
        "mins": {
            "government_cash": _min(rows, "government_cash"),
            "gdp": _min(rows, "gdp_this_tick"),
            "mean_health": _min(rows, "mean_health"),
            "mean_happiness": _min(rows, "mean_happiness"),
        },
        "maxes": {
            "unemployment_rate": _max(rows, "unemployment_rate"),
            "jobless_rate_total_population": _max(rows, "jobless_rate_total_population"),
            "cannot_work_rate": _max(rows, "cannot_work_rate"),
            "private_expected_sales": max(
                (float(getattr(firm, "expected_sales_units", 0.0) or 0.0) for firm in private_real_firms),
                default=0.0,
            ),
            "private_expected_to_observed": max_expected_to_observed,
        },
        "population": {
            "households": len(households),
            "can_work": len(can_work),
            "employed": len(employed),
            "unemployed_can_work": len(unemployed_can_work),
        },
        "labor": labor,
        "flow": flow,
        "wage_reservation": wage_summary,
        "unmet_demand": unmet_summary,
        "firm_financials": firm_financial_rows,
        "firm_negative_counts": negative_counts,
        "working_capital": {
            "budget": float(final.get("working_capital_budget_this_tick", 0.0) or 0.0),
            "candidates": sum(
                bool(getattr(firm, "last_working_capital_candidate", False))
                for firm in private_real_firms
            ),
            "issued": float(final.get("working_capital_issued_this_tick", 0.0) or 0.0),
            "denial_reasons": dict(working_capital_denials),
        },
        "hiring_block_reasons": dict(hiring_block_reasons),
        "final_policy": economy.government.to_dict(),
        "decisions": decisions,
        "tick_metrics": rows,
    }


def run_scenario(args, scenario: str) -> Dict[str, object]:
    CONFIG.random_seed = args.seed
    CONFIG.time.warmup_ticks = max(0, int(args.warmup_ticks))
    random.seed(CONFIG.random_seed)
    np.random.seed(CONFIG.random_seed)

    # create_large_economy is intentionally chatty; keep the JSON runner quiet.
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(
            num_households=args.households,
            num_firms_per_category=2,
        )
    _configure_economy_for_scenario(economy, scenario)

    first_decision_tick = max(CONFIG.time.warmup_ticks + 1, args.first_decision_tick)
    decision_ticks = {
        tick_n for tick_n in range(first_decision_tick, args.ticks + 1)
        if (tick_n - first_decision_tick) % max(1, args.interval) == 0
    }
    decisions: List[Dict[str, object]] = []
    rows: List[Dict[str, object]] = []
    started = time.perf_counter()
    for _ in range(args.ticks):
        economy.step()
        metrics = economy.get_economic_metrics()
        economy.append_metrics_snapshot(metrics, tick=economy.current_tick)
        rows.append(dict(metrics))

        if scenario == "conservative_scripted" and economy.current_tick in decision_ticks:
            decisions.append(_apply_conservative_policy(economy, metrics))

    result = _collect_final_summary(economy, rows, decisions)
    result["scenario"] = scenario
    result["runtime_seconds"] = time.perf_counter() - started
    result["config"] = {
        "ticks": int(args.ticks),
        "households": int(args.households),
        "seed": int(args.seed),
        "warmup_ticks": int(args.warmup_ticks),
        "interval": int(args.interval),
        "first_decision_tick": int(first_decision_tick),
        "llm_enabled": False,
        "legacy_government_stabilizers": False,
        "auto_working_capital_backstop": bool(CONFIG.government.auto_working_capital_backstop),
    }
    return result


def _money(value: float) -> str:
    return f"${float(value):,.0f}"


def write_markdown(path: Path, results: Dict[str, object]) -> None:
    scenarios = results["scenarios"]
    lines = [
        "# Government Control Comparison",
        "",
        f"- ticks: {results['config']['ticks']}",
        f"- households: {results['config']['households']}",
        f"- seed: {results['config']['seed']}",
        "",
        "## Summary Table",
        "",
        "| Scenario | Final Gov Cash | Min Gov Cash | Avg GDP | Final GDP | Avg Unemp | Final Unemp | Jobless Pop | Cannot Work | Avg Health | Final Health | Avg Happy | Final Happy | Neg Cash Firms | Neg Net Worth Firms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in SCENARIOS:
        run = scenarios[name]
        final = run["final"]
        avg = run["averages"]
        mins = run["mins"]
        neg = run["firm_negative_counts"]
        lines.append(
            f"| {name} | {_money(final['government_cash'])} | {_money(mins['government_cash'])} | "
            f"{_money(avg['gdp'])} | {_money(final['gdp'])} | "
            f"{avg['unemployment_rate'] * 100.0:.1f}% | {final['unemployment_rate'] * 100.0:.1f}% | "
            f"{final['jobless_rate_total_population'] * 100.0:.1f}% | {final['cannot_work_rate'] * 100.0:.1f}% | "
            f"{avg['mean_health']:.3f} | {final['mean_health']:.3f} | "
            f"{avg['mean_happiness']:.3f} | {final['mean_happiness']:.3f} | "
            f"{neg['cash']} | {neg['net_worth']} |"
        )

    for name in SCENARIOS:
        run = scenarios[name]
        lines.extend([
            "",
            f"## {name}",
            "",
            "### Wage and Reservation",
        ])
        wage = run["wage_reservation"]
        for label, key in (
            ("employed actual wages", "employed_wages"),
            ("all firm wage offers", "all_firm_offers"),
            ("private firm wage offers", "private_firm_offers"),
            ("active hiring private offers", "active_private_firm_offers"),
            ("baseline firm wage offers", "baseline_firm_offers"),
            ("unemployed stored reservation wages", "unemployed_reservations"),
            ("unemployed tick-match reservations", "unemployed_tick_reservations"),
            ("unemployed expected wages", "unemployed_expected_wages"),
            ("cannot-work reservation wages", "cannot_work_reservations"),
        ):
            dist = wage[key]
            lines.append(
                f"- {label}: n={dist['count']}, mean={dist['mean']:.1f}, "
                f"p10/p25/median/p75/p90={dist['p10']:.1f}/{dist['p25']:.1f}/{dist['median']:.1f}/{dist['p75']:.1f}/{dist['p90']:.1f}, "
                f"min/max={dist['min']:.1f}/{dist['max']:.1f}"
            )
        lines.extend([
            "",
            "### Unmet Demand",
            f"- total goods unmet units: {run['unmet_demand']['total_goods_unmet']:,.1f}",
            f"- explicit goods unmet: {run['unmet_demand']['explicit_goods_unmet']}",
            f"- firm-level unmet by sector: {run['unmet_demand']['firm_level_unmet_by_sector']}",
            f"- baseline unmet by sector: {run['unmet_demand']['baseline_unmet_by_sector']}",
            f"- private unmet by sector: {run['unmet_demand']['private_unmet_by_sector']}",
            "",
            "### Firm Financials",
            "",
            "| firm | sector | base | emp | wage offer | avg wage | price | cash | debt | net worth | revenue | profit | margin | flags |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        for row in run["firm_financials"]:
            flags = []
            if row["negative_cash"]:
                flags.append("neg_cash")
            if row["negative_profit"]:
                flags.append("neg_profit")
            if row["negative_net_worth"]:
                flags.append("neg_net_worth")
            if row["survival"]:
                flags.append("survival")
            if row["burn"]:
                flags.append("burn")
            lines.append(
                f"| {row['firm_id']} | {row['sector']} | {str(row['baseline'])} | {row['employees']} | "
                f"{_money(row['wage_offer'])} | {_money(row['avg_actual_wage'])} | {_money(row['price'])} | "
                f"{_money(row['cash'])} | {_money(row['debt'])} | {_money(row['net_worth'])} | "
                f"{_money(row['last_revenue'])} | {_money(row['last_profit'])} | {row['profit_margin']:.3f} | "
                f"{','.join(flags) if flags else 'ok'} |"
            )
        if run["decisions"]:
            lines.extend(["", "### Conservative Decisions"])
            for decision in run["decisions"]:
                lines.append(
                    f"- tick {decision['tick']}: {decision['reason']} target={decision['target_sector']} changes={decision['changes']}"
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()

    original_config = copy.deepcopy(CONFIG)
    scenario_results = {}
    try:
        for scenario in SCENARIOS:
            # Restore mutable global config before each run so scenarios differ only by their explicit mode.
            CONFIG.__dict__.update(copy.deepcopy(original_config).__dict__)
            scenario_results[scenario] = run_scenario(args, scenario)
    finally:
        CONFIG.__dict__.update(original_config.__dict__)

    results = {
        "config": {
            "ticks": int(args.ticks),
            "households": int(args.households),
            "seed": int(args.seed),
            "warmup_ticks": int(args.warmup_ticks),
            "interval": int(args.interval),
            "first_decision_tick": int(args.first_decision_tick),
        },
        "scenarios": scenario_results,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(output_md, results)

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    for scenario in SCENARIOS:
        run = scenario_results[scenario]
        final = run["final"]
        avg = run["averages"]
        print(
            f"{scenario}: final_gdp={_money(final['gdp'])}, "
            f"avg_gdp={_money(avg['gdp'])}, "
            f"final_unemp={final['unemployment_rate'] * 100.0:.1f}%, "
            f"final_jobless={final['jobless_rate_total_population'] * 100.0:.1f}%, "
            f"final_happy={final['mean_happiness']:.3f}, "
            f"final_gov_cash={_money(final['government_cash'])}"
        )


if __name__ == "__main__":
    main()
