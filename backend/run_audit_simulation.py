"""EcoSim Full Audit Runner

Runs a simulation and logs EVERY aspect of EVERY agent on EVERY tick
to a structured JSON file for post-hoc analysis by audit agents.

Usage:
    python run_audit_simulation.py
    python run_audit_simulation.py --households 500 --ticks 52
    python run_audit_simulation.py --households 100 --ticks 30 --output audit_run.json
"""

import argparse
import copy
import json
import math
import os
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from run_large_simulation import (
    compute_household_stats,
    compute_sector_tick_rollups,
    create_large_economy,
)


class AuditEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class AuditAnalyticsTracker:
    """Build compact analysis-friendly rollups alongside the raw audit dump."""

    def __init__(self) -> None:
        self.windows: Dict[str, deque[float]] = {
            "unemployment_rate": deque(maxlen=64),
            "price_basket": deque(maxlen=64),
            "inflation_rate": deque(maxlen=64),
            "hires_rate": deque(maxlen=64),
            "layoffs_rate": deque(maxlen=64),
        }
        self.previous_unemployment_rate: Optional[float] = None
        self.previous_avg_health: Optional[float] = None

    @staticmethod
    def _rolling_mean(values: deque[float], window: int) -> float:
        if not values:
            return 0.0
        if len(values) <= window:
            return float(sum(values) / len(values))
        recent = list(values)[-window:]
        return float(sum(recent) / len(recent))

    @staticmethod
    def _safe_pct_change(current: float, previous: float) -> float:
        if abs(previous) <= 1e-9:
            return 0.0
        return float(((current - previous) / previous) * 100.0)

    @staticmethod
    def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
        return float(max(lower, min(upper, value)))

    @staticmethod
    def _dominant_driver(components: Dict[str, float], stable_label: str = "stable") -> str:
        if not components:
            return stable_label
        best_key = max(components, key=components.get)
        if components[best_key] <= 1e-9:
            return stable_label
        return str(best_key)

    @staticmethod
    def _compute_total_net_worth(
        economy: Economy,
        price_by_sector: Dict[str, float],
    ) -> float:
        total_net_worth = 0.0
        for household in economy.households:
            total_net_worth += float(household.cash_balance)
            total_net_worth += float(getattr(household, "bank_deposit", 0.0))
            for good, qty in getattr(household, "goods_inventory", {}).items():
                sector = "Food"
                lower_good = str(good).lower()
                if "housing" in lower_good:
                    sector = "Housing"
                elif "service" in lower_good:
                    sector = "Services"
                elif "health" in lower_good or "medical" in lower_good:
                    sector = "Healthcare"
                total_net_worth += float(qty) * float(price_by_sector.get(sector, 0.0))
        return float(total_net_worth)

    def build(self, economy: Economy, metrics: Dict[str, Any]) -> Dict[str, Any]:
        household_stats = compute_household_stats(economy.households)
        sector_rollups = compute_sector_tick_rollups(economy.firms)
        price_by_sector = {
            str(row.get("sector", "Other")): float(row.get("mean_price", 0.0) or 0.0)
            for row in sector_rollups
        }

        labor_diag = dict(getattr(economy, "last_labor_diagnostics", {}) or {})
        health_diag = dict(getattr(economy, "last_health_diagnostics", {}) or {})
        firm_diag = dict(getattr(economy, "last_firm_distress_diagnostics", {}) or {})
        housing_diag = dict(getattr(economy, "last_housing_diagnostics", {}) or {})
        sector_shortages = list(getattr(economy, "last_sector_shortage_diagnostics", []) or [])

        total_households = max(1.0, float(household_stats.get("total_households", 0.0)))
        employed_count = float(household_stats.get("employed_count", 0.0))
        seeker_count = float(labor_diag.get("labor_seekers_total", 0.0))
        labor_force_participation = min(
            100.0,
            max(0.0, ((employed_count + seeker_count) / total_households) * 100.0),
        )

        open_vacancies = int(sum(max(0, int(row.get("vacancies", 0) or 0)) for row in sector_rollups))
        total_hires = int(
            sum(max(0, int(getattr(firm, "last_tick_actual_hires", 0) or 0)) for firm in economy.firms)
        )
        total_layoffs = int(
            sum(len(getattr(firm, "planned_layoffs_ids", []) or []) for firm in economy.firms)
        )
        healthcare_queue_depth = int(health_diag.get("healthcare_queue_depth", 0.0) or 0)
        struggling_firms = int(sum(1 for firm in economy.firms if float(firm.cash_balance) <= 0.0))
        gdp = float(metrics.get("gdp_this_tick", 0.0) or 0.0)
        fiscal_balance = float(
            getattr(economy.government, "last_tick_revenue", 0.0)
            - getattr(economy.government, "last_tick_spending", 0.0)
        )

        unemployment_rate_pct = float(household_stats.get("unemployment_rate", 0.0) or 0.0) * 100.0
        avg_health_pct = float(household_stats.get("mean_health", 0.0) or 0.0) * 100.0
        top10_share_pct = float(household_stats.get("top10_wealth_share", 0.0) or 0.0) * 100.0
        bottom50_share_pct = float(household_stats.get("bottom50_wealth_share", 0.0) or 0.0) * 100.0

        basket_components = [
            float(price_by_sector.get("Food", 0.0)),
            float(price_by_sector.get("Housing", 0.0)),
            float(price_by_sector.get("Services", 0.0)),
        ]
        nonzero_components = [value for value in basket_components if value > 0.0]
        price_basket = (
            float(sum(nonzero_components) / len(nonzero_components))
            if nonzero_components
            else 0.0
        )
        previous_price_basket = self.windows["price_basket"][-1] if self.windows["price_basket"] else price_basket
        inflation_point = self._safe_pct_change(price_basket, previous_price_basket)

        hires_rate = float(total_hires) / total_households * 100.0
        layoffs_rate = float(total_layoffs) / total_households * 100.0
        self.windows["unemployment_rate"].append(unemployment_rate_pct)
        self.windows["price_basket"].append(price_basket)
        self.windows["inflation_rate"].append(inflation_point)
        self.windows["hires_rate"].append(hires_rate)
        self.windows["layoffs_rate"].append(layoffs_rate)

        unemployment_short_ma = self._rolling_mean(self.windows["unemployment_rate"], 5)
        unemployment_long_ma = self._rolling_mean(self.windows["unemployment_rate"], 20)
        inflation_short_ma = self._rolling_mean(self.windows["inflation_rate"], 5)
        hiring_short = self._rolling_mean(self.windows["hires_rate"], 5)
        hiring_long = self._rolling_mean(self.windows["hires_rate"], 20)
        layoff_short = self._rolling_mean(self.windows["layoffs_rate"], 5)
        layoff_long = self._rolling_mean(self.windows["layoffs_rate"], 20)

        vacancy_fill_ratio = 1.0
        if open_vacancies > 0:
            vacancy_fill_ratio = self._clamp(float(total_hires) / float(open_vacancies), lower=0.0, upper=1.0)

        mean_wage = float(household_stats.get("mean_wage", 0.0) or 0.0)
        mean_unemployed_expected_wage = float(household_stats.get("mean_unemployed_expected_wage", 0.0) or 0.0)
        min_wage_floor = float(getattr(economy.config.labor_market, "minimum_wage_floor", 1.0))
        wage_pressure_denominator = max(1.0, mean_wage, min_wage_floor)
        wage_pressure = (
            (mean_unemployed_expected_wage - mean_wage) / wage_pressure_denominator
        ) * 100.0

        healthcare_staff = 0
        for firm in economy.firms:
            if (firm.good_category or "").lower() == "healthcare":
                healthcare_staff += max(
                    0,
                    int(getattr(firm, "medical_staff_count", len(getattr(firm, "employees", [])))),
                )
        healthcare_pressure = float(healthcare_queue_depth / max(1, healthcare_staff))

        consumer_distress_score = self._clamp(
            unemployment_rate_pct * 0.35
            + float(household_stats.get("cash_below_100_share", 0.0) or 0.0) * 100.0 * 0.25
            + float(household_stats.get("health_below_50_share", 0.0) or 0.0) * 100.0 * 0.20
            + float(household_stats.get("happiness_below_50_share", 0.0) or 0.0) * 100.0 * 0.20
        )

        gdp_denom = max(1.0, gdp)
        negative_cash_pct_gdp = max(0.0, -float(getattr(economy.government, "cash_balance", 0.0))) / gdp_denom * 100.0
        negative_flow_pct_gdp = max(0.0, -fiscal_balance) / gdp_denom * 100.0
        fiscal_stress_score = self._clamp(negative_cash_pct_gdp * 0.6 + negative_flow_pct_gdp * 0.4)
        inequality_pressure_score = self._clamp(
            float(household_stats.get("gini_coefficient", 0.0) or 0.0) * 100.0 * 0.6
            + max(0.0, top10_share_pct - bottom50_share_pct) * 0.4
        )

        unemployment_change_pp = (
            0.0
            if self.previous_unemployment_rate is None
            else unemployment_rate_pct - self.previous_unemployment_rate
        )
        avg_health_change_pp = (
            0.0
            if self.previous_avg_health is None
            else avg_health_pct - self.previous_avg_health
        )
        self.previous_unemployment_rate = unemployment_rate_pct
        self.previous_avg_health = avg_health_pct

        layoffs_count = total_layoffs
        hires_count = total_hires
        failed_hiring_firm_count = int(firm_diag.get("failed_hiring_firm_count", 0.0) or 0)
        failed_hiring_roles_count = int(firm_diag.get("failed_hiring_roles_count", 0.0) or 0)
        wage_mismatch_seeker_count = int(labor_diag.get("labor_seekers_wage_ineligible", 0.0) or 0)
        health_blocked_worker_count = int(labor_diag.get("labor_cannot_work", 0.0) or 0)
        inactive_work_capable_count = int(labor_diag.get("labor_unemployed_not_searching", 0.0) or 0)
        low_health_share = float(household_stats.get("health_below_50_share", 0.0) or 0.0) * 100.0
        food_insecure_share = float(household_stats.get("food_insecure_share", 0.0) or 0.0) * 100.0
        cash_stressed_share = float(household_stats.get("cash_below_100_share", 0.0) or 0.0) * 100.0
        pending_healthcare_visits_total = int(household_stats.get("pending_healthcare_visits_total", 0) or 0)
        healthcare_completed_count = int(health_diag.get("healthcare_completed_count", 0.0) or 0)
        healthcare_denied_count = int(health_diag.get("healthcare_denied_count", 0.0) or 0)
        burn_mode_firm_count = int(firm_diag.get("burn_mode_firm_count", 0.0) or 0)
        survival_mode_firm_count = int(firm_diag.get("survival_mode_firm_count", 0.0) or 0)
        zero_cash_firm_count = int(firm_diag.get("zero_cash_firm_count", 0.0) or 0)
        weak_demand_firm_count = int(firm_diag.get("weak_demand_firm_count", 0.0) or 0)
        inventory_pressure_firm_count = int(firm_diag.get("inventory_pressure_firm_count", 0.0) or 0)
        bankruptcy_count = int(firm_diag.get("bankruptcy_count", 0.0) or 0)
        eviction_count = int(housing_diag.get("eviction_count", 0.0) or 0)
        housing_failure_count = int(housing_diag.get("housing_failure_count", 0.0) or 0)
        housing_unaffordable_count = int(housing_diag.get("housing_unaffordable_count", 0.0) or 0)
        housing_no_supply_count = int(housing_diag.get("housing_no_supply_count", 0.0) or 0)
        homeless_household_count = int(housing_diag.get("homeless_household_count", 0.0) or 0)
        shortage_active_sector_count = int(
            sum(1 for row in sector_shortages if bool(row.get("shortage_active", False)))
        )

        decision_features = {
            "unemployment_short_ma": unemployment_short_ma,
            "unemployment_long_ma": unemployment_long_ma,
            "inflation_short_ma": inflation_short_ma,
            "hiring_momentum": hiring_short - hiring_long,
            "layoff_momentum": layoff_short - layoff_long,
            "vacancy_fill_ratio": vacancy_fill_ratio,
            "wage_pressure": wage_pressure,
            "healthcare_pressure": healthcare_pressure,
            "consumer_distress_score": consumer_distress_score,
            "fiscal_stress_score": fiscal_stress_score,
            "inequality_pressure_score": inequality_pressure_score,
        }

        tick_diagnostics = {
            "unemployment_change_pp": unemployment_change_pp,
            "unemployment_primary_driver": self._dominant_driver(
                {
                    "layoffs": float(layoffs_count),
                    "failed_hiring": float(failed_hiring_roles_count),
                    "wage_mismatch": float(wage_mismatch_seeker_count),
                    "health_block": float(health_blocked_worker_count),
                    "inactive_supply": float(inactive_work_capable_count),
                }
            ),
            "layoffs_count": layoffs_count,
            "hires_count": hires_count,
            "failed_hiring_firm_count": failed_hiring_firm_count,
            "failed_hiring_roles_count": failed_hiring_roles_count,
            "wage_mismatch_seeker_count": wage_mismatch_seeker_count,
            "health_blocked_worker_count": health_blocked_worker_count,
            "inactive_work_capable_count": inactive_work_capable_count,
            "avg_health_change_pp": avg_health_change_pp,
            "health_primary_driver": self._dominant_driver(
                {
                    "food_shortfall": float(food_insecure_share),
                    "healthcare_denial": float(healthcare_denied_count),
                    "healthcare_queue": float(healthcare_queue_depth),
                    "broad_distress": float(cash_stressed_share),
                }
            ),
            "low_health_share": low_health_share,
            "food_insecure_share": food_insecure_share,
            "cash_stressed_share": cash_stressed_share,
            "pending_healthcare_visits_total": pending_healthcare_visits_total,
            "healthcare_queue_depth": healthcare_queue_depth,
            "healthcare_completed_count": healthcare_completed_count,
            "healthcare_denied_count": healthcare_denied_count,
            "firm_distress_primary_driver": self._dominant_driver(
                {
                    "burn_mode": float(burn_mode_firm_count),
                    "survival_mode": float(survival_mode_firm_count),
                    "failed_hiring": float(failed_hiring_firm_count),
                    "weak_demand": float(weak_demand_firm_count),
                    "inventory_pressure": float(inventory_pressure_firm_count),
                }
            ),
            "burn_mode_firm_count": burn_mode_firm_count,
            "survival_mode_firm_count": survival_mode_firm_count,
            "zero_cash_firm_count": zero_cash_firm_count,
            "weak_demand_firm_count": weak_demand_firm_count,
            "inventory_pressure_firm_count": inventory_pressure_firm_count,
            "bankruptcy_count": bankruptcy_count,
            "housing_primary_driver": self._dominant_driver(
                {
                    "unaffordable": float(housing_unaffordable_count),
                    "no_supply": float(housing_no_supply_count),
                    "eviction": float(eviction_count),
                }
            ),
            "eviction_count": eviction_count,
            "housing_failure_count": housing_failure_count,
            "housing_unaffordable_count": housing_unaffordable_count,
            "housing_no_supply_count": housing_no_supply_count,
            "homeless_household_count": homeless_household_count,
            "shortage_active_sector_count": shortage_active_sector_count,
        }

        extended_metrics = {
            "labor_force_participation": labor_force_participation,
            "open_vacancies": open_vacancies,
            "total_hires": total_hires,
            "total_layoffs": total_layoffs,
            "avg_food_price": float(price_by_sector.get("Food", 0.0)),
            "avg_housing_price": float(price_by_sector.get("Housing", 0.0)),
            "avg_services_price": float(price_by_sector.get("Services", 0.0)),
            "struggling_firms": struggling_firms,
            "gov_profit": fiscal_balance,
            "total_net_worth": self._compute_total_net_worth(economy, price_by_sector),
        }

        household_distribution = {
            "mean_expected_wage": float(household_stats.get("mean_expected_wage", 0.0) or 0.0),
            "mean_unemployed_expected_wage": mean_unemployed_expected_wage,
            "cash_below_100_share": float(household_stats.get("cash_below_100_share", 0.0) or 0.0),
            "cash_below_zero_share": float(household_stats.get("cash_below_zero_share", 0.0) or 0.0),
            "health_below_50_share": float(household_stats.get("health_below_50_share", 0.0) or 0.0),
            "happiness_below_50_share": float(household_stats.get("happiness_below_50_share", 0.0) or 0.0),
            "food_insecure_share": float(household_stats.get("food_insecure_share", 0.0) or 0.0),
            "housing_insecure_share": float(household_stats.get("housing_insecure_share", 0.0) or 0.0),
            "homeless_household_count": int(household_stats.get("homeless_household_count", 0) or 0),
            "pending_healthcare_visits_total": pending_healthcare_visits_total,
        }

        return {
            "extended_metrics": extended_metrics,
            "household_distribution": household_distribution,
            "sector_rollups": sector_rollups,
            "decision_features": decision_features,
            "tick_diagnostics": tick_diagnostics,
        }


class RunAuditSummarizer:
    """Aggregate compact end-of-run summaries for short audit windows."""

    def __init__(self, config_record: Dict[str, Any]) -> None:
        self.config_record = dict(config_record)
        self.initial_record: Optional[Dict[str, Any]] = None
        self.final_record: Optional[Dict[str, Any]] = None
        self.peaks: Dict[str, Dict[str, Any]] = {}
        self.tick_highlights: List[Dict[str, Any]] = []
        self.sector_stats: Dict[str, Dict[str, Any]] = {}
        self.firm_stats: Dict[int, Dict[str, Any]] = {}
        self.policy_changes: List[Dict[str, Any]] = []

    def _update_peak(self, name: str, value: Any, tick: int) -> None:
        value_num = float(value or 0.0)
        current = self.peaks.get(name)
        if current is None or value_num > float(current.get("value", 0.0)):
            self.peaks[name] = {"tick": int(tick), "value": _r(value_num)}

    def ingest(self, record: Dict[str, Any]) -> None:
        if self.initial_record is None:
            self.initial_record = record
        self.final_record = record

        tick = int(record.get("tick", 0) or 0)
        metrics = record.get("metrics", {}) or {}
        analysis = record.get("analysis", {}) or {}
        diagnostics = record.get("diagnostics", {}) or {}
        decision = analysis.get("decision_features", {}) or {}
        tick_diag = diagnostics.get("tick_diagnostics", {}) or {}

        self._update_peak("unemployment_rate", metrics.get("unemployment_rate", 0.0), tick)
        self._update_peak("consumer_distress_score", decision.get("consumer_distress_score", 0.0), tick)
        self._update_peak("healthcare_pressure", decision.get("healthcare_pressure", 0.0), tick)
        self._update_peak("inequality_pressure_score", decision.get("inequality_pressure_score", 0.0), tick)
        self._update_peak("shortage_active_sector_count", tick_diag.get("shortage_active_sector_count", 0), tick)
        self._update_peak("failed_hiring_roles_count", tick_diag.get("failed_hiring_roles_count", 0), tick)
        self._update_peak("burn_mode_firm_count", tick_diag.get("burn_mode_firm_count", 0), tick)
        self._update_peak("survival_mode_firm_count", tick_diag.get("survival_mode_firm_count", 0), tick)
        self._update_peak("bankruptcy_count", tick_diag.get("bankruptcy_count", 0), tick)
        self._update_peak("food_insecure_share", tick_diag.get("food_insecure_share", 0.0), tick)
        self._update_peak("cash_stressed_share", tick_diag.get("cash_stressed_share", 0.0), tick)

        consumer_distress = float(decision.get("consumer_distress_score", 0.0) or 0.0)
        healthcare_pressure = float(decision.get("healthcare_pressure", 0.0) or 0.0)
        shortage_count = float(tick_diag.get("shortage_active_sector_count", 0.0) or 0.0)
        failed_hiring_roles = float(tick_diag.get("failed_hiring_roles_count", 0.0) or 0.0)
        burn_mode_firms = float(tick_diag.get("burn_mode_firm_count", 0.0) or 0.0)
        survival_mode_firms = float(tick_diag.get("survival_mode_firm_count", 0.0) or 0.0)
        bankruptcies = float(tick_diag.get("bankruptcy_count", 0.0) or 0.0)
        food_insecure_share = float(tick_diag.get("food_insecure_share", 0.0) or 0.0)
        cash_stressed_share = float(tick_diag.get("cash_stressed_share", 0.0) or 0.0)
        severity_score = (
            consumer_distress
            + healthcare_pressure * 5.0
            + shortage_count * 7.0
            + failed_hiring_roles * 3.0
            + burn_mode_firms * 8.0
            + survival_mode_firms * 6.0
            + bankruptcies * 12.0
            + food_insecure_share * 0.5
            + cash_stressed_share * 0.35
        )
        self.tick_highlights.append(
            {
                "tick": tick,
                "severity_score": _r(severity_score),
                "unemployment_rate": _r(metrics.get("unemployment_rate")),
                "consumer_distress_score": _r(consumer_distress),
                "healthcare_pressure": _r(healthcare_pressure),
                "shortage_active_sector_count": int(shortage_count),
                "failed_hiring_roles_count": int(failed_hiring_roles),
                "burn_mode_firm_count": int(burn_mode_firms),
                "survival_mode_firm_count": int(survival_mode_firms),
                "bankruptcy_count": int(bankruptcies),
                "food_insecure_share": _r(food_insecure_share),
                "cash_stressed_share": _r(cash_stressed_share),
                "unemployment_primary_driver": tick_diag.get("unemployment_primary_driver"),
                "health_primary_driver": tick_diag.get("health_primary_driver"),
                "firm_distress_primary_driver": tick_diag.get("firm_distress_primary_driver"),
                "housing_primary_driver": tick_diag.get("housing_primary_driver"),
                "labor_event_count": len(record.get("events", {}).get("labor_events", []) or []),
                "healthcare_event_count": len(record.get("events", {}).get("healthcare_events", []) or []),
                "regime_event_count": len(record.get("events", {}).get("regime_events", []) or []),
                "firm_entries_this_tick": list(record.get("actions", {}).get("firm_entries_this_tick", []) or []),
                "firm_exits_this_tick": list(record.get("actions", {}).get("firm_exits_this_tick", []) or []),
            }
        )

        shortage_by_sector = {
            str(row.get("sector", "Other")): row
            for row in diagnostics.get("sector_shortages", []) or []
        }
        for row in analysis.get("sector_rollups", []) or []:
            sector = str(row.get("sector", "Other"))
            shortage = shortage_by_sector.get(sector, {})
            acc = self.sector_stats.setdefault(
                sector,
                {
                    "sector": sector,
                    "ticks_observed": 0,
                    "mean_price_sum": 0.0,
                    "vacancies_sum": 0.0,
                    "employees_sum": 0.0,
                    "total_revenue_sum": 0.0,
                    "total_output_sum": 0.0,
                    "shortage_active_ticks": 0,
                    "max_shortage_severity": 0.0,
                    "driver_counts": {},
                },
            )
            acc["ticks_observed"] += 1
            acc["mean_price_sum"] += float(row.get("mean_price", 0.0) or 0.0)
            acc["vacancies_sum"] += float(row.get("vacancies", 0.0) or 0.0)
            acc["employees_sum"] += float(row.get("employees", 0.0) or 0.0)
            acc["total_revenue_sum"] += float(row.get("total_revenue", 0.0) or 0.0)
            acc["total_output_sum"] += float(row.get("total_output", 0.0) or 0.0)
            if shortage.get("shortage_active"):
                acc["shortage_active_ticks"] += 1
            severity = float(shortage.get("shortage_severity", 0.0) or 0.0)
            acc["max_shortage_severity"] = max(float(acc["max_shortage_severity"]), severity)
            driver = str(shortage.get("primary_driver", "stable"))
            acc["driver_counts"][driver] = int(acc["driver_counts"].get(driver, 0)) + 1

        firm_state_map = {
            int(firm["firm_id"]): firm for firm in record.get("firms", []) or []
        }
        for action in record.get("actions", {}).get("firm_actions", []) or []:
            firm_id = int(action.get("firm_id", -1))
            firm_state = firm_state_map.get(firm_id, {})
            acc = self.firm_stats.setdefault(
                firm_id,
                {
                    "firm_id": firm_id,
                    "good_name": firm_state.get("good_name"),
                    "good_category": firm_state.get("good_category"),
                    "is_baseline": bool(firm_state.get("is_baseline", False)),
                    "ticks_observed": 0,
                    "move_counts": {},
                    "entered_ticks": [],
                    "exited_ticks": [],
                    "total_hires": 0,
                    "total_layoffs": 0,
                    "planned_hires_total": 0,
                    "failed_hiring_roles": 0,
                    "total_revenue": 0.0,
                    "total_units_sold": 0.0,
                    "total_profit": 0.0,
                    "cash_balance_sum": 0.0,
                    "sell_through_sum": 0.0,
                    "inventory_weeks_sum": 0.0,
                    "profit_margin_sum": 0.0,
                    "burn_ticks": 0,
                    "survival_ticks": 0,
                    "final_cash_balance": 0.0,
                    "move_timeline": [],
                },
            )
            acc["good_name"] = acc.get("good_name") or firm_state.get("good_name")
            acc["good_category"] = acc.get("good_category") or firm_state.get("good_category")
            acc["ticks_observed"] += 1
            for move in action.get("move_types", []) or []:
                acc["move_counts"][move] = int(acc["move_counts"].get(move, 0)) + 1
            if action.get("entered_market"):
                acc["entered_ticks"].append(tick)
            if action.get("exited_market"):
                acc["exited_ticks"].append(tick)

            planned_hires = int(action.get("planned_hires_count", 0) or 0)
            actual_hires = int(action.get("actual_hires_count", 0) or 0)
            acc["planned_hires_total"] += planned_hires
            acc["total_hires"] += actual_hires
            acc["total_layoffs"] += int(action.get("actual_layoffs_count", 0) or 0)
            acc["failed_hiring_roles"] += max(0, planned_hires - actual_hires)
            acc["total_revenue"] += float(action.get("revenue", 0.0) or 0.0)
            acc["total_units_sold"] += float(action.get("units_sold", 0.0) or 0.0)
            acc["total_profit"] += float(firm_state.get("last_profit", 0.0) or 0.0)

            after = action.get("after", {}) or {}
            health = action.get("health_snapshot", {}) or {}
            acc["cash_balance_sum"] += float(after.get("cash_balance", 0.0) or 0.0)
            acc["sell_through_sum"] += float(health.get("sell_through_rate", 0.0) or 0.0)
            acc["inventory_weeks_sum"] += float(health.get("inventory_weeks", 0.0) or 0.0)
            acc["profit_margin_sum"] += float(health.get("smoothed_profit_margin", 0.0) or 0.0)
            acc["burn_ticks"] += 1 if bool(after.get("burn_mode", False)) else 0
            acc["survival_ticks"] += 1 if bool(after.get("survival_mode", False)) else 0
            acc["final_cash_balance"] = float(after.get("cash_balance", 0.0) or 0.0)
            acc["move_timeline"].append(
                {
                    "tick": tick,
                    "move_types": list(action.get("move_types", []) or []),
                    "entered_market": bool(action.get("entered_market", False)),
                    "exited_market": bool(action.get("exited_market", False)),
                    "actual_hires_count": actual_hires,
                    "actual_layoffs_count": int(action.get("actual_layoffs_count", 0) or 0),
                    "planned_hires_count": planned_hires,
                    "price": _r(after.get("price")),
                    "wage_offer": _r(after.get("wage_offer")),
                    "employee_count": after.get("employee_count"),
                    "cash_balance": _r(after.get("cash_balance")),
                    "inventory_units": _r(after.get("inventory_units")),
                    "sell_through_rate": _r(health.get("sell_through_rate")),
                    "inventory_weeks": _r(health.get("inventory_weeks")),
                    "profit_margin": _r(health.get("smoothed_profit_margin")),
                    "burn_mode": bool(after.get("burn_mode", False)),
                    "survival_mode": bool(after.get("survival_mode", False)),
                    "units_sold": _r(action.get("units_sold")),
                    "revenue": _r(action.get("revenue")),
                }
            )

        for change in record.get("events", {}).get("policy_actions", []) or []:
            self.policy_changes.append(dict(change))

    def _firm_issue_flags(self, row: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        ticks = max(1, int(row.get("ticks_observed", 0) or 0))
        avg_sell_through = float(row.get("avg_sell_through", 0.0) or 0.0)
        avg_inventory_weeks = float(row.get("avg_inventory_weeks", 0.0) or 0.0)
        avg_profit_margin = float(row.get("avg_profit_margin", 0.0) or 0.0)
        move_counts = row.get("move_counts", {}) or {}

        if int(row.get("burn_ticks", 0) or 0) > 0 or int(row.get("survival_ticks", 0) or 0) > 0:
            flags.append("distress_mode_seen")
        if int(row.get("failed_hiring_roles", 0) or 0) >= max(3, int(row.get("total_hires", 0) or 0)):
            flags.append("repeated_failed_hiring")
        if avg_sell_through < 0.5:
            flags.append("weak_demand")
        if avg_inventory_weeks > 4.0:
            flags.append("inventory_glut")
        if avg_profit_margin < 0.0:
            flags.append("negative_smoothed_profit")
        if int(move_counts.get("cut_price", 0)) > 0 and avg_sell_through < 0.5:
            flags.append("price_cuts_not_clearing_inventory")
        if int(move_counts.get("plan_hiring", 0)) > 0 and int(move_counts.get("raise_wage", 0)) == 0:
            flags.append("vacancies_without_wage_adjustment")
        if row.get("exited_ticks"):
            flags.append("market_exit")
        return flags

    def finalize(self) -> Dict[str, Any]:
        if self.initial_record is None or self.final_record is None:
            return {"type": "run_summary", "summary_schema_version": 1, "status": "empty"}

        initial_metrics = self.initial_record.get("metrics", {}) or {}
        final_metrics = self.final_record.get("metrics", {}) or {}
        initial_money = float((self.initial_record.get("money_audit", {}) or {}).get("total_money", 0.0) or 0.0)
        final_money = float((self.final_record.get("money_audit", {}) or {}).get("total_money", 0.0) or 0.0)
        money_drift = final_money - initial_money
        money_drift_pct = (money_drift / initial_money * 100.0) if abs(initial_money) > 1e-9 else 0.0

        sector_summary: List[Dict[str, Any]] = []
        for sector, acc in sorted(self.sector_stats.items()):
            ticks = max(1, int(acc.get("ticks_observed", 0) or 0))
            driver_counts = acc.get("driver_counts", {}) or {}
            dominant_driver = max(driver_counts, key=driver_counts.get) if driver_counts else "stable"
            sector_summary.append(
                {
                    "sector": sector,
                    "ticks_observed": ticks,
                    "avg_price": _r(acc["mean_price_sum"] / ticks),
                    "avg_vacancies": _r(acc["vacancies_sum"] / ticks),
                    "avg_employees": _r(acc["employees_sum"] / ticks),
                    "total_revenue": _r(acc["total_revenue_sum"]),
                    "total_output": _r(acc["total_output_sum"]),
                    "shortage_active_ticks": acc["shortage_active_ticks"],
                    "max_shortage_severity": _r(acc["max_shortage_severity"]),
                    "dominant_shortage_driver": dominant_driver,
                }
            )

        firm_dossiers: List[Dict[str, Any]] = []
        for firm_id, acc in sorted(self.firm_stats.items()):
            ticks = max(1, int(acc.get("ticks_observed", 0) or 0))
            row = {
                "firm_id": firm_id,
                "good_name": acc.get("good_name"),
                "good_category": acc.get("good_category"),
                "is_baseline": bool(acc.get("is_baseline", False)),
                "ticks_observed": ticks,
                "entered_ticks": acc.get("entered_ticks", []),
                "exited_ticks": acc.get("exited_ticks", []),
                "total_hires": int(acc.get("total_hires", 0) or 0),
                "total_layoffs": int(acc.get("total_layoffs", 0) or 0),
                "planned_hires_total": int(acc.get("planned_hires_total", 0) or 0),
                "failed_hiring_roles": int(acc.get("failed_hiring_roles", 0) or 0),
                "total_revenue": _r(acc.get("total_revenue", 0.0)),
                "total_units_sold": _r(acc.get("total_units_sold", 0.0)),
                "total_profit": _r(acc.get("total_profit", 0.0)),
                "avg_cash_balance": _r(acc.get("cash_balance_sum", 0.0) / ticks),
                "final_cash_balance": _r(acc.get("final_cash_balance", 0.0)),
                "avg_sell_through": _r(acc.get("sell_through_sum", 0.0) / ticks),
                "avg_inventory_weeks": _r(acc.get("inventory_weeks_sum", 0.0) / ticks),
                "avg_profit_margin": _r(acc.get("profit_margin_sum", 0.0) / ticks),
                "burn_ticks": int(acc.get("burn_ticks", 0) or 0),
                "survival_ticks": int(acc.get("survival_ticks", 0) or 0),
                "move_counts": acc.get("move_counts", {}),
                "move_timeline": acc.get("move_timeline", []),
            }
            row["issue_flags"] = self._firm_issue_flags(row)
            row["severity_score"] = (
                float(row["failed_hiring_roles"]) * 2.0
                + float(row["burn_ticks"]) * 8.0
                + float(row["survival_ticks"]) * 6.0
                + (20.0 if "inventory_glut" in row["issue_flags"] else 0.0)
                + (20.0 if "weak_demand" in row["issue_flags"] else 0.0)
                + (15.0 if row["exited_ticks"] else 0.0)
            )
            firm_dossiers.append(row)

        firm_dossiers.sort(key=lambda row: (-float(row["severity_score"]), row["firm_id"]))
        critical_ticks = sorted(
            self.tick_highlights,
            key=lambda row: (-float(row.get("severity_score", 0.0) or 0.0), int(row.get("tick", 0) or 0)),
        )[: min(10, len(self.tick_highlights))]

        issues: List[Dict[str, Any]] = []
        peak_failed_hiring = float((self.peaks.get("failed_hiring_roles_count") or {}).get("value", 0.0) or 0.0)
        peak_unemployment = float((self.peaks.get("unemployment_rate") or {}).get("value", 0.0) or 0.0)
        peak_food_insecurity = float((self.peaks.get("food_insecure_share") or {}).get("value", 0.0) or 0.0)
        peak_shortage_count = float((self.peaks.get("shortage_active_sector_count") or {}).get("value", 0.0) or 0.0)
        peak_burn = float((self.peaks.get("burn_mode_firm_count") or {}).get("value", 0.0) or 0.0)
        peak_survival = float((self.peaks.get("survival_mode_firm_count") or {}).get("value", 0.0) or 0.0)
        peak_distress = peak_burn + peak_survival

        if peak_failed_hiring > 0 and peak_unemployment > 0:
            issues.append(
                {
                    "issue_code": "labor_mismatch",
                    "severity": _r(peak_failed_hiring + peak_unemployment),
                    "evidence": {
                        "peak_failed_hiring_roles_count": self.peaks.get("failed_hiring_roles_count"),
                        "peak_unemployment_rate": self.peaks.get("unemployment_rate"),
                    },
                }
            )
        if peak_food_insecurity > 0:
            issues.append(
                {
                    "issue_code": "basic_needs_shortfall",
                    "severity": _r(peak_food_insecurity),
                    "evidence": {"peak_food_insecure_share": self.peaks.get("food_insecure_share")},
                }
            )
        if peak_shortage_count > 0:
            issues.append(
                {
                    "issue_code": "sector_shortage",
                    "severity": _r(peak_shortage_count),
                    "evidence": {"peak_shortage_active_sector_count": self.peaks.get("shortage_active_sector_count")},
                }
            )
        if peak_distress > 0:
            issues.append(
                {
                    "issue_code": "firm_distress",
                    "severity": _r(peak_distress),
                    "evidence": {
                        "peak_burn_mode_firm_count": self.peaks.get("burn_mode_firm_count"),
                        "peak_survival_mode_firm_count": self.peaks.get("survival_mode_firm_count"),
                    },
                }
            )
        if abs(money_drift_pct) > 0.1:
            issues.append(
                {
                    "issue_code": "money_drift",
                    "severity": _r(abs(money_drift_pct)),
                    "evidence": {
                        "initial_money": _r(initial_money),
                        "final_money": _r(final_money),
                        "money_drift": _r(money_drift),
                        "money_drift_pct": _r(money_drift_pct),
                    },
                }
            )

        return {
            "type": "run_summary",
            "summary_schema_version": 1,
            "config": self.config_record,
            "tick_range": {
                "start_tick": int(self.initial_record.get("tick", 0) or 0),
                "end_tick": int(self.final_record.get("tick", 0) or 0),
                "observed_ticks": int((self.final_record.get("tick", 0) or 0) - (self.initial_record.get("tick", 0) or 0) + 1),
            },
            "macro_summary": {
                "initial": {
                    "unemployment_rate": _r(initial_metrics.get("unemployment_rate")),
                    "gdp_this_tick": _r(initial_metrics.get("gdp_this_tick")),
                    "mean_wage": _r(initial_metrics.get("mean_wage")),
                    "government_cash": _r(initial_metrics.get("government_cash")),
                    "total_firms": initial_metrics.get("total_firms"),
                    "total_employees": initial_metrics.get("total_employees"),
                    "mean_health": _r(initial_metrics.get("mean_health")),
                    "mean_happiness": _r(initial_metrics.get("mean_happiness")),
                },
                "final": {
                    "unemployment_rate": _r(final_metrics.get("unemployment_rate")),
                    "gdp_this_tick": _r(final_metrics.get("gdp_this_tick")),
                    "mean_wage": _r(final_metrics.get("mean_wage")),
                    "government_cash": _r(final_metrics.get("government_cash")),
                    "total_firms": final_metrics.get("total_firms"),
                    "total_employees": final_metrics.get("total_employees"),
                    "mean_health": _r(final_metrics.get("mean_health")),
                    "mean_happiness": _r(final_metrics.get("mean_happiness")),
                },
                "deltas": {
                    "unemployment_rate_change": _r((final_metrics.get("unemployment_rate") or 0.0) - (initial_metrics.get("unemployment_rate") or 0.0)),
                    "gdp_change": _r((final_metrics.get("gdp_this_tick") or 0.0) - (initial_metrics.get("gdp_this_tick") or 0.0)),
                    "mean_wage_change": _r((final_metrics.get("mean_wage") or 0.0) - (initial_metrics.get("mean_wage") or 0.0)),
                    "government_cash_change": _r((final_metrics.get("government_cash") or 0.0) - (initial_metrics.get("government_cash") or 0.0)),
                    "employee_change": (final_metrics.get("total_employees") or 0) - (initial_metrics.get("total_employees") or 0),
                    "money_drift": _r(money_drift),
                    "money_drift_pct": _r(money_drift_pct),
                },
            },
            "peak_signals": self.peaks,
            "critical_ticks": critical_ticks,
            "issue_candidates": issues,
            "sector_summary": sector_summary,
            "firm_dossiers": firm_dossiers,
            "policy_changes": self.policy_changes,
            "analysis_questions": [
                "Which firm actions consistently preceded distress, layoffs, or failed hiring?",
                "Did sectors fail because of low demand, shortages, wage mismatch, or price pressure?",
                "Which firms kept cutting price or holding wages while their sell-through stayed weak?",
                "Which specific ticks concentrated the most distress, and what drivers dominated those moments?",
                "What policy lever changes, if any, aligned with better or worse decision-feature scores?",
            ],
        }


# ── Serializers ──────────────────────────────────────────────────────

def serialize_household(hh: HouseholdAgent) -> Dict[str, Any]:
    """Capture every readable field on a household."""
    ledger = copy.deepcopy(getattr(hh, "last_tick_ledger", {}) or {})
    purchases = copy.deepcopy(getattr(hh, "last_purchase_breakdown", {}) or {})
    return {
        # Identity
        "household_id": hh.household_id,
        "age": hh.age,
        "skills_level": round(hh.skills_level, 4),

        # Financial
        "cash_balance": round(hh.cash_balance, 2),
        "bank_deposit": round(hh.bank_deposit, 2),
        "medical_loan_remaining": round(hh.medical_loan_remaining, 2),
        "medical_loan_payment_per_tick": round(hh.medical_loan_payment_per_tick, 2),
        "consumption_loan_remaining": round(hh.consumption_loan_remaining, 2),
        "consumption_loan_payment_per_tick": round(hh.consumption_loan_payment_per_tick, 2),

        # Employment
        "is_employed": hh.is_employed,
        "employer_id": hh.employer_id,
        "wage": round(hh.wage, 2),
        "expected_wage": round(hh.expected_wage, 2),
        "reservation_wage": round(hh.reservation_wage, 2),
        "unemployment_duration": hh.unemployment_duration,
        "job_search_cooldown": hh.job_search_cooldown,

        # Income this tick
        "last_wage_income": round(hh.last_wage_income, 2),
        "last_transfer_income": round(hh.last_transfer_income, 2),
        "last_dividend_income": round(hh.last_dividend_income, 2),
        "last_other_income": round(hh.last_other_income, 2),
        "last_consumption_spending": round(hh.last_consumption_spending, 2),
        "ledger": {k: round(v, 2) if isinstance(v, float) else v for k, v in ledger.items()},

        # Consumption
        "last_food_units": round(hh.last_food_units, 2),
        "last_food_spend": round(hh.last_food_spend, 2),
        "last_housing_units": round(hh.last_housing_units, 2),
        "last_housing_spend": round(hh.last_housing_spend, 2),
        "last_services_units": round(hh.last_services_units, 2),
        "last_services_spend": round(hh.last_services_spend, 2),
        "last_healthcare_units": round(hh.last_healthcare_units, 2),
        "last_healthcare_spend": round(hh.last_healthcare_spend, 2),
        "food_consumed_this_tick": round(hh.food_consumed_this_tick, 2),
        "min_food_per_tick": round(hh.min_food_per_tick, 2),
        "purchase_breakdown": purchases,

        # Wellbeing
        "health": round(hh.health, 4),
        "happiness": round(hh.happiness, 4),
        "morale": round(hh.morale, 4),

        # Housing
        "owns_housing": hh.owns_housing,
        "met_housing_need": hh.met_housing_need,
        "monthly_rent": round(hh.monthly_rent, 2),
        "renting_from_firm_id": hh.renting_from_firm_id,

        # Personality (stable but useful for audit)
        "saving_tendency": round(hh.saving_tendency, 3),
        "spending_tendency": round(hh.spending_tendency, 3),
        "frugality": round(hh.frugality, 3),
        "price_sensitivity": round(hh.price_sensitivity, 3),
        "food_preference": round(hh.food_preference, 3),
        "housing_preference": round(hh.housing_preference, 3),
        "services_preference": round(hh.services_preference, 3),
        "deposit_buffer_weeks": round(hh.deposit_buffer_weeks, 2),
        "deposit_fraction": round(hh.deposit_fraction, 3),
        "savings_drawdown_rate": round(hh.savings_drawdown_rate, 4),
        "subsistence_min_cash": round(hh.subsistence_min_cash, 2),

        # Ownership
        "owned_firm_ids": list(getattr(hh, "owned_firm_ids", []) or []),
        "is_ceo": bool(getattr(hh, "is_ceo", False)),

        # Medical
        "medical_training_status": str(hh.medical_training_status),
        "pending_healthcare_visits": hh.pending_healthcare_visits,
        "queued_healthcare_firm_id": hh.queued_healthcare_firm_id,
    }


def serialize_firm(firm: FirmAgent) -> Dict[str, Any]:
    """Capture every readable field on a firm."""
    return {
        # Identity
        "firm_id": firm.firm_id,
        "good_name": firm.good_name,
        "good_category": firm.good_category,
        "is_baseline": firm.is_baseline,
        "personality": firm.personality,

        # Financial
        "cash_balance": round(firm.cash_balance, 2),
        "last_revenue": round(getattr(firm, "last_revenue", 0.0), 2),
        "last_profit": round(getattr(firm, "last_profit", 0.0), 2),
        "trailing_revenue_12t": round(firm.trailing_revenue_12t, 2),
        "profit_margin": round(getattr(firm, "profit_margin", 0.0), 4),
        "revenue_ema": _r(getattr(firm, "revenue_ema", 0.0)),
        "profit_ema": _r(getattr(firm, "profit_ema", 0.0)),

        # Production
        "production_capacity_units": round(firm.production_capacity_units, 2),
        "last_units_produced": round(firm.last_units_produced, 2),
        "units_per_worker": round(firm.units_per_worker, 2),
        "productivity_per_worker": round(firm.productivity_per_worker, 2),
        "age_in_ticks": getattr(firm, "age_in_ticks", 0),

        # Inventory & Sales
        "inventory_units": round(firm.inventory_units, 2),
        "expected_sales_units": round(firm.expected_sales_units, 2),
        "target_inventory_weeks": round(firm.target_inventory_weeks, 2),
        "last_units_sold": round(firm.last_units_sold, 2),
        "last_sell_through_rate": _r(getattr(firm, "last_sell_through_rate", 0.0)),
        "inventory_weeks": _r(getattr(firm, "inventory_weeks", 0.0)),
        "high_inventory_streak": getattr(firm, "high_inventory_streak", 0),
        "low_inventory_streak": getattr(firm, "low_inventory_streak", 0),

        # Pricing
        "price": round(firm.price, 4),
        "min_price": round(firm.min_price, 4),
        "unit_cost": round(firm.unit_cost, 4),
        "markup": round(firm.markup, 4),

        # Labor
        "wage_offer": round(firm.wage_offer, 2),
        "employee_count": len(firm.employees),
        "employee_ids": list(firm.employees.keys()) if isinstance(firm.employees, dict) else list(firm.employees),
        "planned_hires_count": firm.planned_hires_count,
        "planned_layoffs_ids": list(firm.planned_layoffs_ids),
        "last_tick_planned_hires": firm.last_tick_planned_hires,
        "last_tick_actual_hires": getattr(firm, "last_tick_actual_hires", 0),
        "unfilled_positions_streak": getattr(firm, "unfilled_positions_streak", 0),
        "worker_turnover_this_tick": getattr(firm, "worker_turnover_this_tick", 0),
        "loan_required_headcount": getattr(firm, "loan_required_headcount", 0),
        "max_hires_per_tick": firm.max_hires_per_tick,
        "max_fires_per_tick": firm.max_fires_per_tick,

        # Capital (Fix 21)
        "capital_stock": round(firm.capital_stock, 2),
        "capital_investment_this_tick": round(firm.capital_investment_this_tick, 2),
        "needs_investment_loan": firm.needs_investment_loan,
        "investment_loan_amount": _r(getattr(firm, "investment_loan_amount", 0.0)),
        "current_loan_rate": round(firm.current_loan_rate, 4),

        # Quality & R&D
        "quality_level": round(firm.quality_level, 4),
        "rd_spending_rate": round(firm.rd_spending_rate, 4),
        "accumulated_rd_investment": round(firm.accumulated_rd_investment, 2),

        # Distress
        "survival_mode": firm.survival_mode,
        "burn_mode": firm.burn_mode,
        "cash_runway_ticks": _r(getattr(firm, "cash_runway_ticks", 0.0)),
        "smoothed_profit_margin": _r(getattr(firm, "smoothed_profit_margin", 0.0)),
        "zero_cash_streak": getattr(firm, "zero_cash_streak", 0),

        # Loans
        "bank_loan_remaining": round(firm.bank_loan_remaining, 2),
        "bank_loan_payment_per_tick": round(firm.bank_loan_payment_per_tick, 2),
        "bank_loan_principal": _r(getattr(firm, "bank_loan_principal", 0.0)),
        "government_loan_remaining": round(firm.government_loan_remaining, 2),
        "loan_payment_per_tick": round(firm.loan_payment_per_tick, 2),

        # CEO
        "ceo_household_id": firm.ceo_household_id,

        # Housing (if applicable)
        "max_rental_units": getattr(firm, "max_rental_units", 0),
        "occupied_units": getattr(firm, "occupied_units", 0),

        # Healthcare / services
        "healthcare_queue_depth": len(getattr(firm, "healthcare_queue", []) or []),
        "healthcare_arrivals_ema": _r(getattr(firm, "healthcare_arrivals_ema", 0.0)),
        "healthcare_requests_last_tick": _r(getattr(firm, "healthcare_requests_last_tick", 0.0)),
        "healthcare_completed_visits_last_tick": _r(
            getattr(firm, "healthcare_completed_visits_last_tick", 0.0)
        ),
    }


def serialize_government(gov: GovernmentAgent) -> Dict[str, Any]:
    """Capture full government state."""
    return {
        "cash_balance": round(gov.cash_balance, 2),

        # Policy levers
        "wage_tax_rate": round(gov.wage_tax_rate, 4),
        "profit_tax_rate": round(gov.profit_tax_rate, 4),
        "investment_tax_rate": round(gov.investment_tax_rate, 4),
        "wealth_tax_rate": _r(getattr(gov, "wealth_tax_rate", 0.0)),
        "wealth_tax_threshold": _r(getattr(gov, "wealth_tax_threshold", 0.0)),
        "ubi_amount": _r(getattr(gov, "ubi_amount", 0.0)),
        "target_inflation_rate": _r(getattr(gov, "target_inflation_rate", 0.0)),
        "birth_rate": _r(getattr(gov, "birth_rate", 0.0)),
        "benefit_level": gov.benefit_level,
        "public_works_toggle": gov.public_works_toggle,
        "minimum_wage_policy": gov.minimum_wage_policy,
        "sector_subsidy_target": gov.sector_subsidy_target,
        "sector_subsidy_level": gov.sector_subsidy_level,
        "infrastructure_spending": gov.infrastructure_spending,
        "technology_spending": gov.technology_spending,
        "bailout_policy": gov.bailout_policy,
        "bailout_target": gov.bailout_target,
        "bailout_budget": gov.bailout_budget,

        # Derived
        "unemployment_benefit_level": round(gov.unemployment_benefit_level, 2),
        "min_cash_threshold": round(gov.min_cash_threshold, 2),
        "transfer_budget": round(gov.transfer_budget, 2),
        "_minimum_wage_floor": round(gov._minimum_wage_floor, 2),
        "_sector_subsidy_rate": round(gov._sector_subsidy_rate, 4),

        # Budget
        "fiscal_pressure": round(gov.fiscal_pressure, 4),
        "spending_efficiency": round(gov.spending_efficiency, 4),
        "last_tick_revenue": round(gov.last_tick_revenue, 2),
        "last_tick_spending": round(gov.last_tick_spending, 2),

        # Multipliers
        "infrastructure_productivity_multiplier": round(gov.infrastructure_productivity_multiplier, 4),
        "technology_quality_multiplier": round(gov.technology_quality_multiplier, 4),
        "social_happiness_multiplier": round(gov.social_happiness_multiplier, 4),

        # Investment budgets
        "infrastructure_investment_budget": round(gov.infrastructure_investment_budget, 2),
        "technology_investment_budget": round(gov.technology_investment_budget, 2),

        # Bailout cycle
        "bailout_budget_remaining": round(gov.bailout_budget_remaining, 2),
        "bailout_cycle_disbursed": round(gov.bailout_cycle_disbursed, 2),
        "bailout_cycle_firms_assisted": gov.bailout_cycle_firms_assisted,

        # Baseline firms
        "baseline_firm_ids": dict(gov.baseline_firm_ids),
    }


def serialize_bank(bank: Optional[BankAgent]) -> Optional[Dict[str, Any]]:
    """Capture full bank state."""
    if bank is None:
        return None
    firm_scores = dict(bank.firm_credit_scores)
    hh_scores = dict(bank.household_credit_scores)
    loans = []
    for loan in bank.active_loans:
        loans.append({
            "borrower_type": loan.get("borrower_type"),
            "borrower_id": loan.get("borrower_id"),
            "principal": round(loan.get("principal", 0), 2),
            "remaining": round(loan.get("remaining", 0), 2),
            "payment_per_tick": round(loan.get("payment_per_tick", 0), 2),
            "rate": round(loan.get("annual_rate", loan.get("rate", 0)), 4),
            "term_ticks": loan.get("term_ticks", 0),
            "missed_payments": loan.get("missed_payments", 0),
            "subtype": loan.get("subtype", "standard"),
            "govt_backed": loan.get("govt_backed", False),
        })
    return {
        "cash_reserves": round(bank.cash_reserves, 2),
        "total_deposits": round(bank.total_deposits, 2),
        "total_loans_outstanding": round(bank.total_loans_outstanding, 2),
        "base_interest_rate": round(bank.base_interest_rate, 4),
        "deposit_rate": round(bank.deposit_rate, 4),
        "reserve_ratio": round(bank.reserve_ratio, 4),
        "reserve_ratio_actual": round(bank.cash_reserves / max(bank.total_deposits, 1.0), 4),
        "loan_loss_provision": round(bank.loan_loss_provision, 2),
        "lendable_cash": round(bank.lendable_cash, 2),
        "can_lend": bank.can_lend(),

        # Per-tick telemetry
        "last_tick_new_loans": round(bank.last_tick_new_loans, 2),
        "last_tick_defaults": round(bank.last_tick_defaults, 2),
        "last_tick_repayments": round(bank.last_tick_repayments, 2),
        "last_tick_deposit_interest_paid": round(bank.last_tick_deposit_interest_paid, 2),
        "last_tick_interest_income": round(bank.last_tick_interest_income, 2),

        # Credit scores
        "firm_credit_scores": {str(k): round(v, 3) for k, v in firm_scores.items()},
        "household_credit_scores_summary": {
            "count": len(hh_scores),
            "mean": round(sum(hh_scores.values()) / max(len(hh_scores), 1), 3),
            "min": round(min(hh_scores.values()) if hh_scores else 0.5, 3),
            "max": round(max(hh_scores.values()) if hh_scores else 0.5, 3),
        },

        # Active loans
        "active_loan_count": len(loans),
        "active_loans": loans,
    }


def _diff_scalar_fields(
    before: Dict[str, Any],
    after: Dict[str, Any],
    fields: List[str],
) -> List[Dict[str, Any]]:
    """Return scalar field deltas for a compact action/change log."""
    changes: List[Dict[str, Any]] = []
    for field in fields:
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value == after_value:
            continue
        changes.append({
            "field": field,
            "before": _r(before_value),
            "after": _r(after_value),
        })
    return changes


def _policy_change_set(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return government lever changes that happened inside this tick."""
    before = audit.get("government_state_before", {}) or {}
    after = audit.get("government_state_after", {}) or {}
    policy_fields = [
        "wage_tax_rate",
        "profit_tax_rate",
        "investment_tax_rate",
        "benefit_level",
        "unemployment_benefit_level",
        "public_works_toggle",
        "minimum_wage_policy",
        "sector_subsidy_target",
        "sector_subsidy_level",
        "infrastructure_spending",
        "technology_spending",
        "bailout_policy",
        "bailout_target",
        "bailout_budget",
    ]
    return _diff_scalar_fields(before, after, policy_fields)


def _infer_firm_move_types(
    before: Dict[str, Any],
    after: Dict[str, Any],
    production_plan: Dict[str, Any],
    price_plan: Dict[str, Any],
    wage_plan: Dict[str, Any],
    labor_outcome: Dict[str, Any],
    entered: bool,
    exited: bool,
) -> List[str]:
    """Convert low-level plan/outcome deltas into move labels per firm."""
    moves: List[str] = []
    if entered:
        moves.append("entered_market")
    if exited:
        moves.append("exited_market")

    price_before = float(before.get("price", 0.0) or 0.0)
    price_next = float(price_plan.get("price_next", price_before) or 0.0)
    wage_before = float(before.get("wage_offer", 0.0) or 0.0)
    wage_next = float(wage_plan.get("wage_offer_next", wage_before) or 0.0)

    if price_next > price_before + 1e-9:
        moves.append("raise_price")
    elif price_next < price_before - 1e-9:
        moves.append("cut_price")

    if wage_next > wage_before + 1e-9:
        moves.append("raise_wage")
    elif wage_next < wage_before - 1e-9:
        moves.append("cut_wage")

    if int(production_plan.get("planned_hires_count", 0) or 0) > 0:
        moves.append("plan_hiring")
    if labor_outcome.get("hired_households_ids"):
        moves.append("hire")
    if production_plan.get("planned_layoffs_ids"):
        moves.append("plan_layoffs")
    if labor_outcome.get("confirmed_layoffs_ids"):
        moves.append("layoff")

    if float(production_plan.get("planned_production_units", 0.0) or 0.0) > 0.0:
        moves.append("produce")
    if float(after.get("last_units_sold", 0.0) or 0.0) > 0.0:
        moves.append("sell")

    if bool(before.get("survival_mode", False)) != bool(after.get("survival_mode", False)):
        moves.append("enter_survival_mode" if after.get("survival_mode") else "exit_survival_mode")
    if bool(before.get("burn_mode", False)) != bool(after.get("burn_mode", False)):
        moves.append("enter_burn_mode" if after.get("burn_mode") else "exit_burn_mode")

    capital_before = float(before.get("capital_stock", 0.0) or 0.0)
    capital_after = float(after.get("capital_stock", 0.0) or 0.0)
    capital_investment = float(after.get("capital_investment_this_tick", 0.0) or 0.0)
    if capital_investment > 0.0 or capital_after > capital_before + 1e-9:
        moves.append("invest_capital")

    loan_before = float(before.get("bank_loan_remaining", 0.0) or 0.0)
    loan_after = float(after.get("bank_loan_remaining", 0.0) or 0.0)
    if loan_after > loan_before + 1e-9:
        moves.append("take_bank_credit")

    queue_before = int(before.get("queue_depth", 0) or 0)
    queue_after = int(after.get("queue_depth", 0) or 0)
    if queue_after != queue_before:
        moves.append("queue_change")

    deduped: List[str] = []
    for move in moves:
        if move not in deduped:
            deduped.append(move)
    return deduped


def serialize_firm_actions(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Serialize what each firm DID this tick: plans, decisions, outcomes."""
    prod_plans = audit.get("firm_production_plans", {})
    price_plans = audit.get("firm_price_plans", {})
    wage_plans = audit.get("firm_wage_plans", {})
    health = audit.get("firm_health_snapshots", {})
    labor_out = audit.get("firm_labor_outcomes", {})
    sales = audit.get("per_firm_sales", {})
    before_states = audit.get("firm_states_before", {})
    after_states = audit.get("firm_states_after", {})
    entered_ids = set(audit.get("firm_entries_this_tick", []) or [])
    exited_ids = set(audit.get("firm_exits_this_tick", []) or [])
    results = []
    all_ids = (
        set(prod_plans)
        | set(price_plans)
        | set(wage_plans)
        | set(before_states)
        | set(after_states)
    )
    for fid in sorted(all_ids):
        pp = prod_plans.get(fid, {})
        pr = price_plans.get(fid, {})
        wp = wage_plans.get(fid, {})
        hs = health.get(fid, {})
        lo = labor_out.get(fid, {})
        sl = sales.get(fid, {})
        before = before_states.get(fid, {})
        after = after_states.get(fid, {})
        entered = fid in entered_ids
        exited = fid in exited_ids
        hired_ids = list(lo.get("hired_households_ids", []) or [])
        laid_off_ids = list(lo.get("confirmed_layoffs_ids", []) or [])
        actual_wages = {
            str(hid): _r(wage)
            for hid, wage in (lo.get("actual_wages", {}) or {}).items()
        }
        move_types = _infer_firm_move_types(before, after, pp, pr, wp, lo, entered, exited)
        results.append({
            "firm_id": fid,
            "entered_market": entered,
            "exited_market": exited,
            "move_types": move_types,

            # Shared planning context
            "health_snapshot": {
                "cash_runway_ticks": _r(hs.get("cash_runway_ticks")),
                "smoothed_profit_margin": _r(hs.get("smoothed_profit_margin")),
                "sell_through_rate": _r(hs.get("sell_through_rate")),
                "inventory_weeks": _r(hs.get("inventory_weeks")),
                "unfilled_positions_streak": hs.get("unfilled_positions_streak", 0),
                "worker_turnover_this_tick": hs.get("worker_turnover_this_tick", 0),
                "survival_mode": hs.get("survival_mode", False),
                "burn_mode": hs.get("burn_mode", False),
                "category_wage_anchor_p75": _r(hs.get("category_wage_anchor_p75")),
            },

            # Production / labor plans
            "planned_production_units": _r(pp.get("planned_production_units")),
            "planned_hires_count": pp.get("planned_hires_count", 0),
            "planned_layoffs_ids": pp.get("planned_layoffs_ids", []),
            "updated_expected_sales": _r(pp.get("updated_expected_sales")),
            "price_next": _r(pr.get("price_next")),
            "markup_next": _r(pr.get("markup_next")),
            "wage_offer_next": _r(wp.get("wage_offer_next")),
            "loan_required_headcount_after": after.get("loan_required_headcount"),

            # Labor outcomes
            "hired_households_ids": hired_ids,
            "confirmed_layoffs_ids": laid_off_ids,
            "actual_hires_count": len(hired_ids),
            "actual_layoffs_count": len(laid_off_ids),
            "actual_wages": actual_wages,

            # Market outcomes
            "units_sold": _r(sl.get("units_sold")),
            "revenue": _r(sl.get("revenue")),

            # Before/after state deltas
            "before": {
                "price": _r(before.get("price")),
                "wage_offer": _r(before.get("wage_offer")),
                "employee_count": before.get("employee_count"),
                "employee_ids": before.get("employee_ids", []),
                "cash_balance": _r(before.get("cash_balance")),
                "inventory_units": _r(before.get("inventory_units")),
                "expected_sales_units": _r(before.get("expected_sales_units")),
                "burn_mode": before.get("burn_mode"),
                "survival_mode": before.get("survival_mode"),
                "queue_depth": before.get("queue_depth"),
            },
            "after": {
                "price": _r(after.get("price")),
                "wage_offer": _r(after.get("wage_offer")),
                "employee_count": after.get("employee_count"),
                "employee_ids": after.get("employee_ids", []),
                "cash_balance": _r(after.get("cash_balance")),
                "inventory_units": _r(after.get("inventory_units")),
                "expected_sales_units": _r(after.get("expected_sales_units")),
                "capital_stock": _r(after.get("capital_stock")),
                "capital_investment_this_tick": _r(after.get("capital_investment_this_tick")),
                "bank_loan_remaining": _r(after.get("bank_loan_remaining")),
                "government_loan_remaining": _r(after.get("government_loan_remaining")),
                "burn_mode": after.get("burn_mode"),
                "survival_mode": after.get("survival_mode"),
                "queue_depth": after.get("queue_depth"),
            },
            "deltas": {
                "price_change": _r((after.get("price") or 0.0) - (before.get("price") or 0.0)),
                "wage_offer_change": _r((after.get("wage_offer") or 0.0) - (before.get("wage_offer") or 0.0)),
                "employee_count_change": (
                    (after.get("employee_count") if after.get("employee_count") is not None else 0)
                    - (before.get("employee_count") if before.get("employee_count") is not None else 0)
                ),
                "cash_balance_change": _r((after.get("cash_balance") or 0.0) - (before.get("cash_balance") or 0.0)),
                "inventory_change": _r((after.get("inventory_units") or 0.0) - (before.get("inventory_units") or 0.0)),
                "capital_stock_change": _r((after.get("capital_stock") or 0.0) - (before.get("capital_stock") or 0.0)),
                "bank_loan_change": _r((after.get("bank_loan_remaining") or 0.0) - (before.get("bank_loan_remaining") or 0.0)),
            },
        })
    return results


def serialize_household_actions(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Serialize what each household DID this tick: job search, spending, purchases."""
    labor_plans = audit.get("household_labor_plans", {})
    cons_plans = audit.get("household_consumption_plans", {})
    labor_out = audit.get("household_labor_outcomes", {})
    purchases = audit.get("per_household_purchases", {})
    transfers = audit.get("transfer_plan", {})
    wage_taxes = audit.get("tax_plan", {}).get("wage_taxes", {})
    before_states = audit.get("household_states_before", {})
    after_states = audit.get("household_states_after", {})
    results = []
    all_ids = set(labor_plans) | set(cons_plans) | set(before_states) | set(after_states)
    for hid in sorted(all_ids):
        lp = labor_plans.get(hid, {})
        cp = cons_plans.get(hid, {})
        lo = labor_out.get(hid, {})
        pu = purchases.get(hid, {})
        before = before_states.get(hid, {})
        after = after_states.get(hid, {})
        planned_purchases = cp.get("planned_purchases", {})
        planned_budget = cp.get("budget")
        if planned_budget is None:
            category_budgets = cp.get("category_budgets", {}) or {}
            planned_budget = sum(category_budgets.values()) if category_budgets else None
        # Flatten planned purchases to serializable form
        pp_serial = {}
        for target, qty in planned_purchases.items():
            pp_serial[str(target)] = _r(qty)
        # Flatten actual purchases
        pu_serial = {}
        for good_name, val in pu.items():
            if isinstance(val, (tuple, list)) and len(val) == 2:
                pu_serial[str(good_name)] = {"qty": _r(val[0]), "avg_price": _r(val[1])}
            else:
                pu_serial[str(good_name)] = val
        employer_before = before.get("employer_id")
        employer_after = lo.get("employer_id", after.get("employer_id"))
        employed_before = bool(before.get("is_employed", False))
        employed_after = bool(after.get("is_employed", False))
        got_hired = (not employed_before) and employed_after
        got_fired = employed_before and (not employed_after)
        job_switched = (
            employed_before
            and employed_after
            and employer_before is not None
            and employer_after is not None
            and employer_before != employer_after
        )
        if got_hired:
            job_transition = "hire"
        elif got_fired:
            job_transition = "layoff_or_exit"
        elif job_switched:
            job_transition = "job_switch"
        elif employed_after:
            job_transition = "retained"
        else:
            job_transition = "unemployed"
        results.append({
            "household_id": hid,
            # Labor plan
            "searching_for_job": lp.get("searching_for_job", False),
            "reservation_wage": _r(lp.get("reservation_wage")),
            "job_switching": lp.get("job_switching", False),
            "medical_only_search": lp.get("medical_only", False),
            # Labor outcome
            "job_transition": job_transition,
            "got_hired": got_hired,
            "got_fired": got_fired,
            "job_switched": job_switched,
            "employer_id_before": employer_before,
            "employer_id_after": employer_after,
            "wage_before": _r(before.get("wage")),
            "wage_after": _r(lo.get("wage", after.get("wage"))),
            "cash_before": _r(before.get("cash_balance")),
            "cash_after": _r(after.get("cash_balance")),
            # Consumption plan
            "planned_budget": _r(planned_budget),
            "planned_purchases": pp_serial,
            # Actual purchases
            "actual_purchases": pu_serial,
            # Government
            "transfer_received": _r(transfers.get(hid, 0)),
            "wage_tax_paid": _r(wage_taxes.get(hid, 0)),
            # Healthcare / welfare transitions
            "pending_healthcare_visits_before": before.get("pending_healthcare_visits"),
            "pending_healthcare_visits_after": after.get("pending_healthcare_visits"),
            "queued_healthcare_firm_before": before.get("queued_healthcare_firm_id"),
            "queued_healthcare_firm_after": after.get("queued_healthcare_firm_id"),
            "health_before": _r(before.get("health")),
            "health_after": _r(after.get("health")),
            "happiness_before": _r(before.get("happiness")),
            "happiness_after": _r(after.get("happiness")),
            "morale_before": _r(before.get("morale")),
            "morale_after": _r(after.get("morale")),
        })
    return results


def serialize_government_actions(audit: Dict[str, Any], economy: Economy) -> Dict[str, Any]:
    """Serialize what the government DID this tick: taxes, transfers, spending."""
    gov = economy.government
    tax_plan = audit.get("tax_plan", {})
    transfer_plan = audit.get("transfer_plan", {})
    return {
        "total_wage_taxes": _r(sum(tax_plan.get("wage_taxes", {}).values())),
        "total_profit_taxes": _r(sum(tax_plan.get("profit_taxes", {}).values())),
        "total_property_taxes": _r(sum(tax_plan.get("property_taxes", {}).values())),
        "total_transfers": _r(sum(transfer_plan.values())),
        "transfer_recipients": len([v for v in transfer_plan.values() if v > 0]),
        "wage_tax_payers": len([v for v in tax_plan.get("wage_taxes", {}).values() if v > 0]),
        "profit_tax_payers": len([v for v in tax_plan.get("profit_taxes", {}).values() if v > 0]),
        "bailout_disbursed": _r(getattr(gov, "bailout_cycle_disbursed", 0)),
        "bailout_firms_assisted": getattr(gov, "bailout_cycle_firms_assisted", 0),
        "bond_purchases_this_tick": _r(getattr(economy, "last_tick_gov_bond_purchases", 0.0)),
        "subsidy_spend_this_tick": _r(getattr(economy, "last_tick_gov_subsidies", 0.0)),
        "bailout_spend_this_tick": _r(getattr(economy, "last_tick_gov_bailouts", 0.0)),
        "public_works_capitalization_this_tick": _r(
            getattr(economy, "last_tick_gov_public_works_capitalization", 0.0)
        ),
        "policy_changes": _policy_change_set(audit),
        "state_changes": _diff_scalar_fields(
            audit.get("government_state_before", {}) or {},
            audit.get("government_state_after", {}) or {},
            ["cash_balance", "fiscal_pressure", "spending_efficiency"],
        ),
    }


def serialize_bank_actions(economy: Economy) -> Optional[Dict[str, Any]]:
    """Serialize what the bank DID this tick: loans, repayments, defaults."""
    bank = economy.bank
    if bank is None:
        return None
    return {
        "new_loans_issued": _r(bank.last_tick_new_loans),
        "loan_repayments_collected": _r(bank.last_tick_repayments),
        "loan_defaults": _r(bank.last_tick_defaults),
        "deposit_interest_paid": _r(bank.last_tick_deposit_interest_paid),
        "interest_income_earned": _r(bank.last_tick_interest_income),
        "current_deposit_rate": _r(bank.deposit_rate),
        "active_loan_count": len(bank.active_loans),
        "can_lend": bank.can_lend(),
        "lendable_cash": _r(bank.lendable_cash),
    }


def _r(v, decimals=4):
    """Round a value if it's a float, otherwise return as-is."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (float, np.floating)):
        value = float(v)
        if not math.isfinite(value):
            return None
        return round(value, decimals)
    return v


def _round_shallow_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Round only the scalar values of a flat mapping."""
    return {key: _r(value) for key, value in row.items()}


def serialize_tick(
    economy: Economy,
    tick: int,
    elapsed_ms: float,
    analytics_tracker: Optional[AuditAnalyticsTracker] = None,
) -> Dict[str, Any]:
    """Capture the full state AND actions of the simulation at one tick."""
    metrics = economy.get_economic_metrics()
    analytics = (analytics_tracker or AuditAnalyticsTracker()).build(economy, metrics)
    metrics.update(analytics["extended_metrics"])
    metrics_serialized = {k: _r(v) for k, v in metrics.items()}

    # Money conservation check
    hh_cash = sum(h.cash_balance for h in economy.households)
    hh_deposits = sum(h.bank_deposit for h in economy.households)
    firm_cash = sum(f.cash_balance for f in economy.firms)
    queued_cash = sum(f.cash_balance for f in getattr(economy, "queued_firms", []))
    gov_cash = economy.government.cash_balance
    bank_reserves = economy.bank.cash_reserves if economy.bank else 0.0
    misc_pool = getattr(economy, "misc_firm_revenue", 0.0)
    total_money = hh_cash + firm_cash + queued_cash + gov_cash + bank_reserves + misc_pool

    record = {
        "tick": tick,
        "elapsed_ms": round(elapsed_ms, 1),
        "in_warmup": bool(getattr(economy, "in_warmup", False)),

        # Economy-wide metrics
        "metrics": metrics_serialized,

        # Money conservation
        "money_audit": {
            "household_cash": round(hh_cash, 2),
            "household_deposits": round(hh_deposits, 2),
            "firm_cash": round(firm_cash, 2),
            "queued_firm_cash": round(queued_cash, 2),
            "government_cash": round(gov_cash, 2),
            "bank_reserves": round(bank_reserves, 2),
            "misc_pool": round(misc_pool, 2),
            "total_money": round(total_money, 2),
        },

        # Regime events (bankruptcies, distress transitions, etc.)
        "regime_events": list(getattr(economy, "last_regime_events", [])),
        "labor_diagnostics": dict(getattr(economy, "last_labor_diagnostics", {})),
        "analysis": {
            "decision_features": _round_shallow_dict(analytics["decision_features"]),
            "household_distribution": _round_shallow_dict(analytics["household_distribution"]),
            "sector_rollups": [
                _round_shallow_dict(row) for row in analytics["sector_rollups"]
            ],
        },
        "diagnostics": {
            "tick_diagnostics": _round_shallow_dict(analytics["tick_diagnostics"]),
            "labor": _round_shallow_dict(dict(getattr(economy, "last_labor_diagnostics", {}) or {})),
            "health": _round_shallow_dict(dict(getattr(economy, "last_health_diagnostics", {}) or {})),
            "housing": _round_shallow_dict(dict(getattr(economy, "last_housing_diagnostics", {}) or {})),
            "firm_distress": _round_shallow_dict(
                dict(getattr(economy, "last_firm_distress_diagnostics", {}) or {})
            ),
            "sector_shortages": [
                _round_shallow_dict(row)
                for row in list(getattr(economy, "last_sector_shortage_diagnostics", []) or [])
            ],
        },
        "events": {
            "labor_events": list(getattr(economy, "last_labor_events", []) or []),
            "healthcare_events": list(getattr(economy, "last_healthcare_events", []) or []),
            "regime_events": list(getattr(economy, "last_regime_events", []) or []),
            "policy_actions": [],
        },

        # Agent states
        "government": serialize_government(economy.government),
        "bank": serialize_bank(economy.bank),
        "firms": [serialize_firm(f) for f in economy.firms],
        "queued_firms": [serialize_firm(f) for f in getattr(economy, "queued_firms", [])],
        "households": [serialize_household(h) for h in economy.households],
    }

    # Per-tick ACTIONS (what agents decided and did)
    audit = getattr(economy, "_last_tick_audit", {})
    if audit:
        policy_changes = _policy_change_set(audit)
        if policy_changes:
            record["events"]["policy_actions"] = [
                {"tick": tick, **change} for change in policy_changes
            ]
        record["actions"] = {
            "firm_actions": serialize_firm_actions(audit),
            "household_actions": serialize_household_actions(audit),
            "government_actions": serialize_government_actions(audit, economy),
            "bank_actions": serialize_bank_actions(economy),
            "firm_entries_this_tick": audit.get("firm_entries_this_tick", []),
            "firm_exits_this_tick": audit.get("firm_exits_this_tick", []),
            "bankruptcies_this_tick": audit.get("bankruptcies_this_tick", 0),
            "total_dividends_paid": _r(audit.get("total_dividends_paid", 0)),
            "unemployment_rate": _r(audit.get("unemployment_rate", 0)),
        }

    return record


# ── Main ─────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="EcoSim Full Audit Runner")
    p.add_argument("--households", type=int, default=100, help="Number of households (default: 100)")
    p.add_argument("--firms-per-category", type=int, default=2, help="Firms per category (default: 2)")
    p.add_argument("--ticks", type=int, default=52, help="Ticks to simulate (default: 52)")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--output", type=str, default="audit_full_dump.jsonl",
                    help="Output file (default: audit_full_dump.jsonl)")
    p.add_argument("--no-shocks", action="store_true", help="Disable random economic shocks")
    p.add_argument("--no-digest", action="store_true",
                    help="Skip generating the compact LLM-ready digest (.md)")
    return p.parse_args()


def main():
    args = parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print("=" * 80)
    print("  EcoSim Full Audit Runner")
    print(f"  Households: {args.households} | Ticks: {args.ticks} | Seed: {args.seed}")
    print(f"  Output: {args.output}")
    print("=" * 80)

    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households,
        num_firms_per_category=args.firms_per_category,
    )
    # Enable audit action logging — captures all plans/outcomes per tick
    economy.audit_log_enabled = True

    if args.no_shocks:
        economy._apply_random_shocks = lambda: None

    n_firms = len(economy.firms)
    n_queued = len(economy.queued_firms)
    has_bank = economy.bank is not None
    analytics_tracker = AuditAnalyticsTracker()
    print(f"done ({args.households} HH, {n_firms} firms, {n_queued} queued, bank={'yes' if has_bank else 'no'})")

    # Write header
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config as first line
    config_record = {
        "type": "config",
        "seed": args.seed,
        "households": args.households,
        "firms_per_category": args.firms_per_category,
        "ticks": args.ticks,
        "warmup_ticks": CONFIG.time.warmup_ticks,
        "audit_schema_version": 2,
        "has_bank": has_bank,
        "initial_firms": n_firms,
        "initial_queued": n_queued,
        "no_shocks": args.no_shocks,
    }
    run_summarizer = RunAuditSummarizer(config_record)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(config_record, cls=AuditEncoder) + "\n")

    # Initial state (tick 0)
    initial = serialize_tick(economy, 0, 0.0, analytics_tracker)
    run_summarizer.ingest(initial)
    initial_money = initial["money_audit"]["total_money"]
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "tick", **initial}, cls=AuditEncoder) + "\n")

    print(f"\nInitial money supply: ${initial_money:,.0f}")
    print(f"Writing JSONL (one line per tick) to {out_path}\n")

    print("-" * 80)
    print(f" {'Tick':>4} | {'Unemp':>6} | {'GDP':>9} | {'Firms':>5} | "
          f"{'HH Cash':>10} | {'Gov Cash':>10} | {'Money':>12} | {'Drift':>8} | {'ms':>6}")
    print("-" * 80)

    sim_start = time.perf_counter()
    drift = 0.0

    for t in range(1, args.ticks + 1):
        t0 = time.perf_counter()
        economy.step()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        tick_data = serialize_tick(economy, t, elapsed_ms, analytics_tracker)
        run_summarizer.ingest(tick_data)
        current_money = tick_data["money_audit"]["total_money"]
        drift = current_money - initial_money

        # Append to file
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "tick", **tick_data}, cls=AuditEncoder) + "\n")

        # Console summary
        m = tick_data["metrics"]
        unemp = m.get("unemployment_rate", 0) * 100
        gdp = m.get("gdp_this_tick", 0)
        firms = m.get("total_firms", 0)
        hh_cash = tick_data["money_audit"]["household_cash"]
        gov_cash = tick_data["money_audit"]["government_cash"]

        print(
            f" {t:>4} | {unemp:>5.1f}% | ${gdp:>8,.0f} | {firms:>5} | "
            f"${hh_cash:>9,.0f} | ${gov_cash:>9,.0f} | ${current_money:>11,.0f} | "
            f"{'%+.0f' % drift:>8} | {elapsed_ms:>5.0f}",
            flush=True,
        )

    summary_record = run_summarizer.finalize()
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary_record, cls=AuditEncoder) + "\n")

    total_time = time.perf_counter() - sim_start
    file_size = out_path.stat().st_size

    print("-" * 80)
    print(f"\nDone in {total_time:.1f}s ({total_time / args.ticks * 1000:.0f}ms/tick)")
    print(f"Output: {out_path} ({file_size / 1024 / 1024:.1f} MB)")
    print(f"Final money drift: ${drift:+,.2f} ({drift / initial_money * 100:+.4f}%)")
    print(f"Lines: {args.ticks + 3} (1 config + 1 initial + {args.ticks} ticks + 1 run_summary)")

    # ── Auto-generate compact LLM digest ───────────────────────────────
    if not args.no_digest:
        from audit_digest import build_digest, estimate_tokens, load_audit

        digest_path = out_path.with_suffix(".md")
        print(f"\nGenerating LLM digest...", end=" ", flush=True)
        d_config, d_ticks = load_audit(str(out_path))
        digest_text = build_digest(d_config, d_ticks)
        token_est = estimate_tokens(digest_text)
        digest_path.write_text(digest_text, encoding="utf-8")
        digest_size = digest_path.stat().st_size
        print(f"done")
        print(f"Digest: {digest_path} ({digest_size / 1024:.1f} KB, ~{token_est:,} tokens)")


if __name__ == "__main__":
    main()
