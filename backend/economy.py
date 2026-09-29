"""
Economy Simulation Engine

Implements the main simulation coordinator that orchestrates households,
firms, government, and an optional bank through tick-based cycles.
Includes optional stochastic shocks for scenario variation across runs.

Performance optimizations:
- Caches household/firm lookups for O(1) access
- Uses NumPy vectorization for labor and goods market operations
- Batch operations to minimize Python loop overhead
"""

# Navigation Index
# - Imports, module setup, _TickScratch and _update_price_belief: approx. lines 32-128
# - Economy coordinator state and constructor: approx. lines 130-360
# - Stabilization, visibility, audit, and telemetry helpers: approx. lines 362-868
# - Household consumption, subsidies, and batched updates: approx. lines 870-1618
# - Main tick orchestration (step() and the _phase_* methods): approx. lines 1620-2765
# - Firm distress, working capital, and shortage diagnostics: approx. lines 2767-3308
# - Labor market matching and roster synchronization: approx. lines 3310-4343
# - Goods market clearing and firm market views: approx. lines 4345-4794
# - Wellbeing, tax snapshots, production, and firm lifecycle: approx. lines 4796-5696
# - Loan programs and capital financing: approx. lines 5698-6410
# - Bailouts, public works, stimulus, and shocks: approx. lines 6412-6773
# - Housing rentals, repairs, and miscellaneous revenue: approx. lines 6775-7124
# - Healthcare queue and service processing: approx. lines 7126-7447
# - Fiscal pressure, banking, credit, and medical loans: approx. lines 7449-7827
# - Policy adjustment, statistics, and economic metrics: approx. lines 7829-8414

# -----------------------------------------------------------------------------
# Section: Imports and module setup
# -----------------------------------------------------------------------------
import logging
import os
import random
from dataclasses import dataclass, fields
from collections import deque
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

from config import CONFIG, get_config
from fiscal_guards import (
    annualized_debt_to_gdp,
    fiscal_reserve_floor,
    get_sector_subsidy_cap,
    projected_public_works_startup_cost,
    public_works_affordable_budget,
    trailing_gdp,
)
import numpy as np
import math
from agents import (
    HouseholdAgent,
    FirmAgent,
    BankAgent,
    GovernmentAgent,
    FirmHealthSnapshot,
    LoanContract,
    build_awareness_market_views,
)
from utils.category_utils import build_good_category_lookup
from payments import PaymentBook, MONEY_EPS, proportional

if TYPE_CHECKING:  # typing only; the payment arm imports it lazily at run time
    from payment_sectors import PaymentGoodsMarket

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _TickScratch:
    """Values one phase of Economy.step() hands to a later phase of the same tick.

    step() builds one instance at the top of the tick and passes it to every
    phase method; it is never stored on the Economy, so nothing outlives the
    tick. Fields default to None until the phase that produces them runs.
    """

    payment_arm: bool
    audit_firm_states_before: Optional[Dict[int, Dict[str, object]]] = None
    audit_household_states_before: Optional[Dict[int, Dict[str, object]]] = None
    audit_government_state_before: Optional[Dict[str, object]] = None
    good_category_lookup: Optional[Dict[str, str]] = None
    category_market_snapshot: Optional[Dict[str, List[Dict[str, float]]]] = None
    housing_private_inventory: Optional[float] = None
    total_households: Optional[int] = None
    housing_inventory_overhang: Optional[float] = None
    unemployment_rate: Optional[float] = None
    gov_benefit: Optional[float] = None
    firm_production_plans: Optional[Dict[int, Dict]] = None
    firm_price_plans: Optional[Dict[int, Dict]] = None
    firm_wage_plans: Optional[Dict[int, Dict]] = None
    firm_health_snapshots: Optional[Dict[int, Dict[str, object]]] = None
    category_wage_anchor_p75: Optional[Dict[str, float]] = None
    household_labor_plans: Optional[Dict[int, Dict]] = None
    household_consumption_plans: Optional[Dict[int, Dict]] = None
    firm_labor_outcomes: Optional[Dict[int, Dict]] = None
    household_labor_outcomes: Optional[Dict[int, Dict]] = None
    frozen_wages: Optional[Dict[int, float]] = None
    per_household_purchases: Optional[Dict[int, Dict]] = None
    per_firm_sales: Optional[Dict[int, Dict]] = None
    goods_market: Optional["PaymentGoodsMarket"] = None  # payment arm only
    price_ceiling_tax_by_firm_id: Optional[Dict[int, float]] = None
    total_price_ceiling_taxes: Optional[float] = None
    assessed_project_receipts: Optional[Dict[int, float]] = None
    tax_plan: Optional[Dict[str, Dict[int, float]]] = None
    transfer_plan: Optional[Dict[int, float]] = None
    total_wage_taxes: Optional[float] = None
    total_profit_taxes: Optional[float] = None
    total_property_taxes: Optional[float] = None
    total_transfers: Optional[float] = None
    bankruptcies_this_tick: Optional[int] = None
    total_dividends_paid: Optional[float] = None


def _update_price_belief(beliefs: Dict[str, float], good: str, price: float, alpha: float) -> None:
    """Blend an observed price into a household's belief for one good.

    An existing belief moves to ``alpha * price + (1 - alpha) * old``; a good
    with no belief yet adopts the observed price.
    """
    if good in beliefs:
        old_belief = beliefs[good]
        beliefs[good] = (
            alpha * price +
            (1.0 - alpha) * old_belief
        )
    else:
        beliefs[good] = price


# -----------------------------------------------------------------------------
# Section: Economy coordinator state and constructor
# -----------------------------------------------------------------------------
class Economy:
    """
    Main simulation coordinator for the economic model.

    Orchestrates all agents through a strict plan/apply cycle with
    deterministic labor and goods market clearing.

    SOLID Violations:
    - SRP (Single Responsibility Principle) VIOLATION: This class has 5,782 lines
      and handles simulation orchestration, labor market matching, goods market
      clearing, housing rental market, healthcare queue processing, banking
      integration, firm lifecycle management, government policy adjustments,
      and economic metrics calculation. A single class should have only ONE
      reason to change, but this has ~15+ reasons to change.

    - OCP (Open/Closed Principle) VIOLATION: Adding new market types,
      policy levers, or economic shocks requires modifying this class
      directly rather than extending it through plugins or strategy patterns.

    - DIP (Dependency Inversion Principle) VIOLATION: Directly depends on
      concrete agent implementations (HouseholdAgent, FirmAgent, BankAgent,
      GovernmentAgent) rather than abstract interfaces or protocols.
      Should depend on abstractions like IHousehold, IFirm, etc.

    - ISP (Interface Segregation Principle) N/A: Not directly applicable
      as Python doesn't have formal interfaces, but the large number of
      public methods suggests clients may be forced to depend on methods
      they don't use.
    """

    def __init__(
        self,
        households: List[HouseholdAgent],
        firms: List[FirmAgent],
        government: GovernmentAgent,
        queued_firms: Optional[List[FirmAgent]] = None,
        bank: Optional[BankAgent] = None,
    ):
        """
        Initialize the economy with pre-constructed agents.

        Args:
            households: List of household agents participating in the economy
            firms: List of firm agents producing goods and services
            government: Government agent managing taxes, transfers, and policy
            queued_firms: Optional pre-queued firms awaiting market entry
            bank: Optional bank agent for credit channel (None = govt-direct lending)

        Note on SOLID Violations:
            - SRP Violation: This constructor initializes 50+ instance variables
              spanning simulation state, labor markets, goods markets, housing,
              healthcare, banking, diagnostics, and configuration. A class should
              have only ONE reason to change, but this has 15+ reasons.
            - Consider using composition: extracting LaborMarketState, HousingState,
              BankingState, DiagnosticState, etc. into separate classes.
        """
        # SOLID: SRP Violation - Simulation core state
        self.households = households
        self.firms = firms
        self.government = government
        self.bank: Optional[BankAgent] = bank
        self.config = CONFIG
        self.payment_config_snapshot = {
            field.name: getattr(CONFIG, field.name)
            for field in fields(get_config()) if field.name.startswith("payment_")
        }
        self.payment_sequence = str(getattr(CONFIG, "payment_sequence", "legacy"))
        if self.payment_sequence not in {"legacy", "income_first", "income_late"}:
            raise ValueError("unsupported payment sequence")
        self.payment_care_mode = str(getattr(CONFIG, "payment_care_mode", "patient_pay"))
        self.payment_assistance = str(getattr(CONFIG, "payment_assistance", "reserve"))
        self.payment_state = {"wage_claims": {}, "recovery_holds": {}, "ceo_holds": {},
                              "unpaid_streaks": {}, "restrictions": {name: 0.0 for name in ("B", "care", "rent", "G", "withholding", "project")}}
        self.payment_book = None
        self.payment_denied_outlays = {}
        self.payment_rent_monitor_counterfactual = 0.0
        if self.payment_sequence != "legacy":
            for household in self.households:
                if household.renting_from_firm_id is not None:
                    household.payment_pre_policy_liquidity = max(0.0, household.cash_balance) + 0.9 * max(0.0, household.bank_deposit)
        self.queued_firms: List[FirmAgent] = queued_firms or []
        self.target_total_firms = 0
        self._refresh_target_total_firms()
        self.large_market = len(self.households) >= CONFIG.firms.large_market_household_threshold

        # SOLID: SRP Violation - Stabilizer flags should be in a separate config object
        mode_cfg = CONFIG.modes
        self.enable_household_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.household_stabilizers
        self.enable_firm_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.firm_stabilizers
        self.enable_government_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.government_stabilizers

        # SOLID: SRP Violation - Warm-up state should be in a SimulationState class
        # Track simulation progression and warm-up period state
        self.current_tick = 0
        self.warmup_ticks = max(0, int(getattr(CONFIG.time, "warmup_ticks", 52)))
        self.in_warmup = self.current_tick < self.warmup_ticks
        self.post_warmup_cooldown = 0
        rolling_windows = tuple(getattr(CONFIG.llm, "government_rolling_windows_ticks", ()) or ())
        max_rolling_window = max([int(value) for value in rolling_windows], default=0)
        self.metrics_history: deque[Dict[str, object]] = deque(
            maxlen=max(8, int(getattr(CONFIG.llm, "government_impact_horizon", 8)) + 4, max_rolling_window + 4)
        )
        self.llm_government = None
        self.last_llm_government_decision: Optional[Dict[str, object]] = None

        # Performance optimization: Cache lookups for O(1) access
        # SOLID: DIP Violation - Should use abstract interfaces, not concrete types
        self.household_lookup: Dict[int, HouseholdAgent] = {h.household_id: h for h in households}
        self.firm_lookup: Dict[int, FirmAgent] = {f.firm_id: f for f in firms}
        # Static household trait arrays for consumption planning, keyed by the
        # household list object and its length; see _household_static_traits().
        self._household_static_traits_cache: Optional[Tuple[List[HouseholdAgent], int, Dict[str, object]]] = None

        # Cache wage percentiles to avoid repeated sorting
        self.cached_wage_percentiles: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # low, mid, high
        self.wage_percentile_cache_tick: int = -1

        # SOLID: SRP Violation - Metrics tracking should be in a MetricsCollector class
        # Initialize tracking dictionaries with defaults
        self.last_tick_sales_units: Dict[int, float] = {}
        self.last_tick_revenue: Dict[int, float] = {}
        self.last_tick_sell_through_rate: Dict[int, float] = {}
        self.last_tick_prices: Dict[str, float] = {}
        self.last_tick_gov_wage_taxes: float = 0.0
        self.last_tick_gov_profit_taxes: float = 0.0
        self.last_tick_gov_property_taxes: float = 0.0
        self.last_tick_gov_transfers: float = 0.0
        self.last_tick_gov_investments: float = 0.0
        self.last_tick_gov_infrastructure_spending: float = 0.0
        self.last_tick_gov_technology_spending: float = 0.0
        self.last_tick_gov_social_spending: float = 0.0
        self.last_tick_gov_bond_purchases: float = 0.0
        self.last_tick_gov_subsidies: float = 0.0
        self.last_tick_gov_bailouts: float = 0.0
        self.last_tick_gov_public_works_capitalization: float = 0.0
        self.last_tick_gov_public_works_requested_startup: float = 0.0
        self.last_tick_gov_public_works_denied_by_budget: float = 0.0
        self.last_tick_gov_public_works_affordable_budget: float = 0.0
        self.last_tick_gov_public_works_jobs_authorized: int = 0
        self.last_tick_gov_post_warmup_stimulus: float = 0.0
        self.sector_subsidy_cap_this_tick: float = 0.0
        self.sector_subsidy_remaining_this_tick: float = 0.0
        self.last_tick_gov_subsidy_requested: float = 0.0
        self.last_tick_gov_subsidy_denied_by_cap: float = 0.0
        self.last_fiscal_pressure_instant_ratio: float = 0.0
        self.last_fiscal_pressure_denominator_gdp: float = 1.0
        self.bailout_eligible_firms_by_sector: Dict[str, int] = {}
        self.bailout_denied_firms_by_reason: Dict[str, int] = {}
        self.bailout_received_by_firm_id: Dict[int, float] = {}
        self.last_tick_working_capital_budget: float = 0.0
        self.last_tick_working_capital_candidates: int = 0
        self.last_tick_working_capital_issued: float = 0.0
        self.last_tick_working_capital_denied_budget: float = 0.0
        self.price_increase_limited_count: int = 0
        self.rent_increase_limited_count: int = 0
        self.avg_sector_price_to_median_wage: float = 0.0
        self.housing_rent_to_median_wage: float = 0.0
        self.performance_mode = False
        self._cached_consumption_plans: Dict[int, Dict] = {}

        # Set initial defaults
        for firm in firms:
            self.last_tick_sales_units[firm.firm_id] = 0.0
            self.last_tick_revenue[firm.firm_id] = 0.0
            self.last_tick_sell_through_rate[firm.firm_id] = 0.5  # neutral default
            self.last_tick_prices[firm.good_name] = firm.price

        # SOLID: SRP Violation - Misc firm logic should be in a separate RedistributionSystem
        # Misc firm: redistributes investment/R&D spending to random households
        self.misc_firm_revenue: float = 0.0  # Accumulated investment money
        self.misc_firm_beneficiaries: List[int] = []  # household_ids who receive payouts
        self._initialize_misc_firm_beneficiaries()
        self.post_warmup_stimulus_ticks: int = 0
        self.post_warmup_stimulus_duration: int = 0

        # SOLID: SRP Violation - Healthcare state should be in HealthcareSystem class
        self.healthcare_requests_this_tick: float = 0.0
        self.healthcare_attempted_slots_this_tick: float = 0.0
        self.healthcare_completed_visits_this_tick: float = 0.0
        self.healthcare_affordability_rejects_this_tick: float = 0.0

        # SOLID: SRP Violation - Labor market config should be in LaborMarketConfig
        self.last_tick_pre_purchase_deposit_withdrawals: float = 0.0
        self.last_tick_end_tick_deposit_sweeps: float = 0.0
        self.labor_match_mode = os.getenv("ECOSIM_LABOR_MATCH_MODE", "fast").strip().lower()
        if self.labor_match_mode not in {"fast", "legacy"}:
            self.labor_match_mode = "fast"
        self.compare_labor_match = os.getenv("ECOSIM_COMPARE_LABOR_MATCH", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.compare_labor_match_stride = max(1, int(os.getenv("ECOSIM_COMPARE_LABOR_MATCH_STRIDE", "1")))
        self.log_labor_diagnostics = os.getenv("ECOSIM_LABOR_DIAGNOSTICS", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.labor_diagnostics_stride = max(1, int(os.getenv("ECOSIM_LABOR_DIAGNOSTICS_STRIDE", "10")))
        self.force_unemployed_search = os.getenv("ECOSIM_FORCE_UNEMPLOYED_SEARCH", "1").strip().lower() in {"1", "true", "yes", "on"}
        self.clamp_unemployed_reservation = os.getenv("ECOSIM_CLAMP_UNEMPLOYED_RESERVATION", "1").strip().lower() in {"1", "true", "yes", "on"}
        self.unemployed_reservation_clamp_ticks = max(1, int(os.getenv("ECOSIM_UNEMPLOYED_CLAMP_TICKS", "8")))

        # SOLID: SRP Violation - Diagnostics state should be in DiagnosticsCollector class
        self.last_labor_diagnostics: Dict[str, float] = {}
        self.last_labor_plan_adjustments: Dict[str, float] = {}
        self.last_household_labor_plans: Dict[int, Dict[str, object]] = {}
        self.last_health_diagnostics: Dict[str, float] = {}
        self.last_firm_distress_diagnostics: Dict[str, float] = {}
        self.last_housing_diagnostics: Dict[str, float] = {}
        self.last_sector_shortage_diagnostics: List[Dict[str, object]] = []
        self.last_labor_events: List[Dict[str, object]] = []
        self.last_healthcare_events: List[Dict[str, object]] = []
        self.last_regime_events: List[Dict[str, object]] = []
        self._sector_shortage_state: Dict[str, bool] = {}
        self._labor_compare_mismatch_count = 0

        # SOLID: SRP Violation - Demand tracking should be in MarketDemand class
        self.food_unmet_demand: float = 0.0
        self.services_unmet_demand: float = 0.0
        self.services_unmet_demand_by_firm: Dict[int, float] = {}
        self.last_tick_unmet_demand_by_firm: Dict[int, float] = {}
        self.current_tick_unmet_demand_by_firm: Dict[int, float] = {}

        # SOLID: SRP Violation - Unemployment tracking should be in LaborMarketState
        self._unemployment_history: deque = deque(maxlen=CONFIG.firms.unemployment_ma_window)
        self.unemployment_short_ma: float = 0.0

        # SOLID: SRP Violation - Audit state should be in AuditLogger class
        # Audit-mode action log: when enabled, step() stashes all intermediate
        # plans and outcomes so an external audit runner can serialize them.
        self.audit_log_enabled = False
        self._last_tick_audit: Dict[str, object] = {}

        self._refresh_household_visibility_context()
        self._propagate_stabilizer_flags()

    # -------------------------------------------------------------------------
    # Section: Stabilization, visibility, audit, and telemetry helpers
    # -------------------------------------------------------------------------
    def _price_stabilization_multiplier(self, level: str, rent: bool = False) -> float:
        """Return upward price-growth cap for a stabilization level."""
        gov_cfg = CONFIG.government
        level = str(level or "off").lower()
        if level == "strict":
            return float(
                gov_cfg.rent_stabilization_strict_max_increase
                if rent else gov_cfg.price_stabilization_strict_max_increase
            )
        if level == "soft":
            return float(
                gov_cfg.rent_stabilization_soft_max_increase
                if rent else gov_cfg.price_stabilization_soft_max_increase
            )
        return float("inf")

    def _apply_price_stabilization_to_plan(self, firm: FirmAgent, price_plan: Dict[str, float]) -> None:
        """Soft-cap sector price increases selected by government policy."""
        target = str(getattr(self.government, "price_stabilization_target", "none") or "none").lower()
        level = str(getattr(self.government, "price_stabilization_level", "off") or "off").lower()
        category = (getattr(firm, "good_category", "") or "").lower()
        if level not in {"soft", "strict"} or target == "none" or category != target:
            return
        if category == "housing":
            return

        current_price = max(0.0, float(getattr(firm, "price", 0.0) or 0.0))
        proposed = max(float(getattr(firm, "min_price", 0.0) or 0.0), float(price_plan.get("price_next", current_price)))
        unit_cost = max(0.0, float(getattr(firm, "unit_cost", 0.0) or 0.0))
        cost_recovery_floor = max(float(getattr(firm, "min_price", 0.0) or 0.0), unit_cost)
        max_allowed = max(
            float(getattr(firm, "min_price", 0.0) or 0.0),
            current_price * self._price_stabilization_multiplier(level),
        )
        if bool(getattr(firm, "survival_mode", False)) or float(getattr(firm, "cash_balance", 0.0) or 0.0) <= 0.0:
            max_allowed = max(max_allowed, cost_recovery_floor)
        limited = min(proposed, max_allowed)
        if limited + 1e-9 < proposed:
            price_plan["price_next"] = limited
            price_plan["markup_next"] = max(0.0, (limited / unit_cost) - 1.0) if unit_cost > 0 else 0.0
            self.price_increase_limited_count += 1
            firm.decision_diagnostics["price_stabilization_limited"] = True
            firm.decision_diagnostics["price_stabilization_level"] = level
            firm.decision_diagnostics["price_stabilization_uncapped_price"] = proposed
            firm.decision_diagnostics["price_stabilization_capped_price"] = limited

    def _update_affordability_telemetry(self) -> None:
        """Track price/wage ratios for metrics and LLM observation."""
        median_wage = 0.0
        paid_wages = [
            float(wage)
            for firm in self.firms
            for wage in (getattr(firm, "actual_wages", {}) or {}).values()
            if float(wage or 0.0) > 0.0
        ]
        if paid_wages:
            median_wage = float(np.median(np.array(paid_wages, dtype=np.float64)))
        elif self.cached_wage_percentiles[1]:
            median_wage = float(self.cached_wage_percentiles[1])

        target = str(getattr(self.government, "price_stabilization_target", "none") or "none").lower()
        if target != "none":
            sector_prices = [
                float(getattr(firm, "price", 0.0) or 0.0)
                for firm in self.firms
                if (getattr(firm, "good_category", "") or "").lower() == target
            ]
            avg_price = sum(sector_prices) / len(sector_prices) if sector_prices else 0.0
            self.avg_sector_price_to_median_wage = avg_price / max(1.0, median_wage)
        else:
            self.avg_sector_price_to_median_wage = 0.0

        housing_prices = [
            float(getattr(firm, "price", 0.0) or 0.0)
            for firm in self.firms
            if (getattr(firm, "good_category", "") or "").lower() == "housing"
        ]
        avg_rent = sum(housing_prices) / len(housing_prices) if housing_prices else 0.0
        self.housing_rent_to_median_wage = avg_rent / max(1.0, median_wage)

    # SOLID: SRP Violation - This method handles BOTH ownership syncing AND
    # misc beneficiary tracking. Should be split into two methods.
    def _refresh_household_visibility_context(self) -> None:
        """Sync household-side ownership and redistribution context for narration/logging.

        Note:
            This method has two responsibilities: syncing firm ownership data
            to households AND setting misc beneficiary flags. Per Single
            Responsibility Principle, consider splitting into:
            - _sync_household_ownership()
            - _sync_misc_beneficiaries()
        """
        for household in self.households:
            household.owned_firm_ids = []
            household.is_misc_beneficiary = False

        for firm in [*self.firms, *self.queued_firms]:
            for owner_id in getattr(firm, "owners", []):
                household = self.household_lookup.get(owner_id)
                if household is not None:
                    household.owned_firm_ids.append(firm.firm_id)

        for household in self.households:
            household.owned_firm_ids = sorted(set(household.owned_firm_ids))

        for household_id in self.misc_firm_beneficiaries:
            household = self.household_lookup.get(household_id)
            if household is not None:
                household.is_misc_beneficiary = True

    def _reset_household_tick_visibility(self) -> None:
        """Reset per-tick household narration/accounting fields before cash starts moving.

        This method is called at the start of each tick (step) to ensure
        clean state for ledger tracking and diagnostic reporting.
        Resets fields like last_tick_cash_start, consumption tracking,
        and other per-tick counters on all households.
        """
        for household in self.households:
            household.reset_tick_ledger()

    def _payment_free_treasury_cash(self) -> float:
        if self.payment_sequence == "legacy":
            return max(0.0, self.government.cash_balance)
        return max(0.0, self.government.cash_balance - sum(self.payment_state["restrictions"].values()))

    def _payment_sync_restrictions(self) -> None:
        if self.payment_sequence != "legacy":
            self.government.payment_reserved_cash = sum(self.payment_state["restrictions"].values())

    def _payment_spend_restriction(self, name: str, amount: float) -> float:
        from payments import _amount
        amount = _amount(amount)
        restricted = self.payment_state["restrictions"]
        if amount > restricted.get(name, 0.0) + MONEY_EPS:
            raise ValueError(f"insufficient {name} restriction")
        restricted[name] = max(0.0, restricted[name] - amount)
        self.government.cash_balance -= amount
        self._payment_sync_restrictions()
        if name == "G":
            self.sector_subsidy_remaining_this_tick -= amount
            self.last_tick_gov_subsidies += amount
        return amount

    def _payment_fiscal_close(self, tax_base: float = 0.0) -> None:
        """Release unused envelopes and appropriate next week's benefits before care."""
        restricted = self.payment_state["restrictions"]
        if self.payment_state.get("services_project_payables"):
            raise ValueError("unsettled Services project payable at fiscal close")
        for name in restricted:
            restricted[name] = 0.0
        self._payment_sync_restrictions()
        count = sum(h.employer_id is None for h in self.households)
        restricted["B"] = min(self._payment_free_treasury_cash(), max(0.0, self.government.get_unemployment_benefit_level()) * count)
        self._payment_sync_restrictions()
        assistance = min(self._payment_free_treasury_cash(), max(0.0, tax_base) * 0.10)
        if self.payment_assistance == "care":
            restricted["care"] = assistance
        elif self.payment_assistance == "rent":
            restricted["rent"] = assistance
        elif self.payment_assistance == "mixed":
            restricted["care"] = assistance * 0.5
            restricted["rent"] = assistance - restricted["care"]
        self._payment_sync_restrictions()
        if self.config.payment_services_project_enabled:
            from payment_government import reserve_payment_services_project
            reserve_payment_services_project(self)

    def _payment_reserve_subsidy(self) -> None:
        free = self._payment_free_treasury_cash()
        reserve = min(0.05 * max(trailing_gdp(self), 1.0), 0.02 * free, free)
        self.payment_state["restrictions"]["G"] = reserve
        self.sector_subsidy_cap_this_tick = reserve
        self.sector_subsidy_remaining_this_tick = reserve
        self._payment_sync_restrictions()

    def _capture_audit_firm_state(self, firms: Optional[List[FirmAgent]] = None) -> Dict[int, Dict[str, object]]:
        """Capture a compact pre/post state for firm action auditing.

        Creates a snapshot of key firm metrics for audit logging.
        Used by the audit system to track state changes across ticks.

        Args:
            firms: Optional list of firms to snapshot (defaults to self.firms)

        Returns:
            Dictionary mapping firm_id to a dict of firm state values.
            Captures: financials (cash, loans), production (inventory,
            expected sales), employment (count, IDs, planned changes),
            and performance (revenue, profit, quality, capital).

        Note:
            Uses getattr with defaults for forward-compatibility.
            This method is part of the audit system (SRP concern).
        """
        rows: Dict[int, Dict[str, object]] = {}
        source = firms if firms is not None else self.firms
        for firm in source:
            employee_ids = (
                list(firm.employees.keys())
                if isinstance(firm.employees, dict)
                else list(firm.employees)
            )
            rows[int(firm.firm_id)] = {
                "firm_id": int(firm.firm_id),
                "good_name": str(firm.good_name),
                "good_category": str(firm.good_category),
                "is_baseline": bool(firm.is_baseline),
                "cash_balance": float(firm.cash_balance),
                "inventory_units": float(firm.inventory_units),
                "expected_sales_units": float(firm.expected_sales_units),
                "price": float(firm.price),
                "wage_offer": float(firm.wage_offer),
                "employee_count": int(len(employee_ids)),
                "employee_ids": employee_ids,
                "planned_hires_count": int(getattr(firm, "planned_hires_count", 0)),
                "planned_layoffs_count": int(len(getattr(firm, "planned_layoffs_ids", []))),
                "last_tick_actual_hires": int(getattr(firm, "last_tick_actual_hires", 0)),
                "last_units_produced": float(getattr(firm, "last_units_produced", 0.0)),
                "last_units_sold": float(getattr(firm, "last_units_sold", 0.0)),
                "last_revenue": float(getattr(firm, "last_revenue", 0.0)),
                "last_profit": float(getattr(firm, "last_profit", 0.0)),
                "quality_level": float(getattr(firm, "quality_level", 0.0)),
                "capital_stock": float(getattr(firm, "capital_stock", 0.0)),
                "capital_investment_this_tick": float(getattr(firm, "capital_investment_this_tick", 0.0)),
                "needs_investment_loan": bool(getattr(firm, "needs_investment_loan", False)),
                "investment_loan_amount": float(getattr(firm, "investment_loan_amount", 0.0)),
                "bank_loan_remaining": float(getattr(firm, "bank_loan_remaining", 0.0)),
                "government_loan_remaining": float(getattr(firm, "government_loan_remaining", 0.0)),
                "loan_required_headcount": int(getattr(firm, "loan_required_headcount", 0)),
                "burn_mode": bool(getattr(firm, "burn_mode", False)),
                "survival_mode": bool(getattr(firm, "survival_mode", False)),
                "queue_depth": int(len(getattr(firm, "healthcare_queue", []))),
            }
        return rows

    def _capture_audit_household_state(self) -> Dict[int, Dict[str, object]]:
        """Capture a compact pre/post state for household action auditing.

        Creates a snapshot of key household metrics for audit logging.
        Used by the audit system to track state changes across ticks.

        Returns:
            Dictionary mapping household_id to a dict of household state values.
            Captures: employment (status, employer, wage), financials
            (cash, deposits), expectations (reservation, expected wage),
            wellbeing (health, happiness, morale), and service state
            (healthcare queue, housing rental).

        Note:
            This method is part of the audit system (SRP concern).
            Uses getattr with defaults for forward-compatibility.
        """
        rows: Dict[int, Dict[str, object]] = {}
        for household in self.households:
            rows[int(household.household_id)] = {
                "household_id": int(household.household_id),
                "is_employed": bool(household.is_employed),
                "employer_id": int(household.employer_id) if household.employer_id is not None else None,
                "wage": float(household.wage),
                "cash_balance": float(household.cash_balance),
                "bank_deposit": float(household.bank_deposit),
                "reservation_wage": float(household.reservation_wage),
                "expected_wage": float(household.expected_wage),
                "health": float(household.health),
                "happiness": float(household.happiness),
                "morale": float(household.morale),
                "unemployment_duration": int(household.unemployment_duration),
                "pending_healthcare_visits": int(getattr(household, "pending_healthcare_visits", 0)),
                "queued_healthcare_firm_id": (
                    int(household.queued_healthcare_firm_id)
                    if household.queued_healthcare_firm_id is not None
                    else None
                ),
                "renting_from_firm_id": (
                    int(household.renting_from_firm_id)
                    if household.renting_from_firm_id is not None
                    else None
                ),
            }
        return rows

    def _capture_audit_government_state(self) -> Dict[str, object]:
        """Capture the government lever surface for per-tick action diffs.

        Creates a snapshot of all government policy levers and financial state
        for audit logging. Used to track policy changes across ticks.

        Returns:
            Dictionary with government state including:
            - Financial: cash_balance, fiscal_pressure, spending_efficiency
            - Tax policy: wage_tax_rate, profit_tax_rate, investment_tax_rate
            - Spending policy: benefit_level, unemployment_benefit_level
            - Sector policy: public_works_toggle, sector_subsidy_target/level
            - Infrastructure: infrastructure_spending, technology_spending
            - Crisis policy: bailout_policy, bailout_target, bailout_budget

        Note:
            This method is part of the audit system (SRP concern).
            Captures the complete "lever surface" that an LLM government
            or human operator can modify.
        """
        gov = self.government
        return {
            "cash_balance": float(gov.cash_balance),
            "wage_tax_rate": float(gov.wage_tax_rate),
            "profit_tax_rate": float(gov.profit_tax_rate),
            "investment_tax_rate": float(gov.investment_tax_rate),
            "benefit_level": str(gov.benefit_level),
            "unemployment_benefit_level": float(gov.unemployment_benefit_level),
            "public_works_toggle": str(gov.public_works_toggle),
            "minimum_wage_policy": str(gov.minimum_wage_policy),
            "sector_subsidy_target": (
                str(gov.sector_subsidy_target)
                if gov.sector_subsidy_target is not None
                else None
            ),
            "sector_subsidy_level": str(gov.sector_subsidy_level),
            "infrastructure_spending": str(gov.infrastructure_spending),
            "technology_spending": str(gov.technology_spending),
            "social_spending": str(gov.social_spending),
            "bailout_policy": str(gov.bailout_policy),
            "bailout_target": str(gov.bailout_target),
            "bailout_budget": float(gov.bailout_budget),
            "fiscal_pressure": float(gov.fiscal_pressure),
            "spending_efficiency": float(gov.spending_efficiency),
        }

    # SOLID: SRP Violation - This method mixes configuration checking with
    # tick-based scheduling logic. Should be in LLMGovernance class.
    def should_run_llm_government(self) -> bool:
        """Return whether the external LLM government cycle is due this tick.

        The decision itself is executed outside ``step()`` because the server
        loop is already async and provider calls should not be forced through a
        blocking sync wrapper inside the simulation core.

        Returns:
            True if LLM government is enabled in config and the current tick
            falls on the configured decision interval.

        Note:
            This method directly accesses CONFIG.llm, creating tight coupling
            to the configuration structure (Dependency Inversion Principle violation).
        """
        interval = max(1, int(getattr(CONFIG.llm, "government_decision_interval", 26)))
        start_tick = max(
            int(getattr(CONFIG.llm, "government_start_tick", 15)),
            int(getattr(CONFIG.time, "warmup_ticks", getattr(self, "warmup_ticks", 10)))
            + int(getattr(CONFIG.llm, "government_start_after_warmup_ticks", 5)),
        )
        return (
            bool(getattr(CONFIG.llm, "enable_llm_government", False))
            and self.current_tick >= start_tick
            and ((self.current_tick - start_tick) % interval == 0)
        )

    def record_llm_government_decision(self, decision: Dict[str, object]) -> None:
        """Store the latest external LLM government decision for observers.

        Args:
            decision: Dictionary containing the LLM's policy decisions
                      (e.g., tax rates, spending levels, etc.)

        Note:
            This is a simple setter. Consider using an Observer pattern
            or event system for notifying multiple subscribers (SRP).
        """
        self.last_llm_government_decision = dict(decision)

    def append_metrics_snapshot(self, metrics: Dict[str, object], tick: Optional[int] = None) -> None:
        """Persist a compact in-memory metrics snapshot for lagged observation.

        Used by the LLM government to observe economic state with a
        lag (e.g., looking at metrics from 8 ticks ago).

        Args:
            metrics: Dictionary of economic indicators to snapshot
            tick: Optional tick number (defaults to current_tick)

        Note:
            The metrics_history deque has a maxlen set during __init__.
            This is a simple circular buffer implementation.
        """
        self.metrics_history.append(
            {
                "tick": int(self.current_tick if tick is None else tick),
                "metrics": dict(metrics),
            }
        )

    # SOLID: SRP Violation - Event logging should be in a separate EventLogger class.
    # This method is called from many places, mixing event tracking concern
    # into the main Economy class.
    def _append_regime_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        sector: Optional[str] = None,
        reason_code: Optional[str] = None,
        severity: Optional[float] = None,
        metric_value: Optional[float] = None,
        payload: Optional[Dict[str, object]] = None,
    ) -> None:
        """Append one high-value regime/state transition event for this tick.

        Regime events track important state transitions like:
        - Firm distress enter/exit (burn_mode, survival_mode)
        - Failed hiring events
        - Evictions and housing shortages
        - Firm bankruptcies

        Args:
            event_type: Type of event (e.g., "firm_distress_enter", "eviction")
            entity_type: "firm", "household", "sector"
            entity_id: ID of the entity (firm_id, household_id)
            sector: Sector name ("Food", "Housing", etc.)
            reason_code: Why the event occurred (e.g., "burn_mode", "unaffordable")
            severity: Numeric severity level
            metric_value: Related metric value
            payload: Additional event-specific data

        Note:
            Events are stored in last_regime_events and cleared each tick.
            This is part of the diagnostics system (SRP concern).
        """
        self.last_regime_events.append({
            "tick": int(self.current_tick + 1),
            "event_type": str(event_type),
            "entity_type": str(entity_type),
            "entity_id": int(entity_id) if entity_id is not None else None,
            "sector": str(sector) if sector is not None else None,
            "reason_code": str(reason_code) if reason_code is not None else None,
            "severity": float(severity) if severity is not None else None,
            "metric_value": float(metric_value) if metric_value is not None else None,
            "payload": payload or None,
        })

    # SOLID: SRP Violation - Stabilizer management should be in a separate
    # PolicyManager or StabilizerManager class.
    def _propagate_stabilizer_flags(self) -> None:
        """Push stabilizer flags down to agents.

        Note:
            This method iterates over all households and firms to propagate
            flags. For large populations, consider batch updates or
            lazy propagation (SRP - performance concern mixed with policy).
        """
        self.government.stabilization_disabled = not self.enable_government_stabilizers
        for household in self.households:
            household.stabilization_disabled = not self.enable_household_stabilizers
        for firm in self.firms:
            firm.stabilization_disabled = not self.enable_firm_stabilizers
        for firm in self.queued_firms:
            firm.stabilization_disabled = not self.enable_firm_stabilizers

    def configure_stabilizers(
        self,
        households: Optional[bool] = None,
        firms: Optional[bool] = None,
        government: Optional[bool] = None
    ) -> None:
        """Enable or disable stabilizers for each agent type.

        Args:
            households: If not None, set household stabilizers on/off
            firms: If not None, set firm stabilizers on/off
            government: If not None, set government stabilizers on/off

        Note:
            This method modifies multiple subsystem states at once.
            Consider using a Command pattern for undoable changes.
        """
        if households is not None:
            self.enable_household_stabilizers = households
        if firms is not None:
            self.enable_firm_stabilizers = firms
        if government is not None:
            self.enable_government_stabilizers = government
        self._propagate_stabilizer_flags()

    def apply_stabilization_overrides(self, disabled_agents: List[str]) -> None:
        """
        Disable stabilizers for selected agent groups.

        Args:
            disabled_agents: Iterable of agent labels ("households", "firms", "government", "all")

        Note:
            This is a convenience wrapper around configure_stabilizers().
            The string-based agent selection is flexible but error-prone
            (could use an enum or literal types for type safety).
        """
        disabled = {agent.lower() for agent in disabled_agents}
        disable_all = "all" in disabled
        households_enabled = not (disable_all or "households" in disabled)
        firms_enabled = not (disable_all or "firms" in disabled)
        government_enabled = not (disable_all or "government" in disabled)
        self.configure_stabilizers(
            households=households_enabled,
            firms=firms_enabled,
            government=government_enabled
        )

    # -------------------------------------------------------------------------
    # Section: Household consumption, subsidies, and batched updates
    # -------------------------------------------------------------------------
    def _household_static_traits(self) -> Dict[str, object]:
        """Arrays of household traits that are written only at construction.

        spending_tendency, frugality, savings_drawdown_rate, the three
        *_preference values and category_weights are set in
        HouseholdAgent.__post_init__ and never reassigned by the engine, so
        _batch_plan_consumption gathers them once instead of every tick. The
        cache is rebuilt when the household list object or its length changes.
        Callers must not mutate the returned arrays, lists or dicts.
        """
        households = self.households
        cached = self._household_static_traits_cache
        # Holding the list itself (not its id) means a replaced list can never
        # match through a reused id.
        if cached is not None and cached[0] is households and cached[1] == len(households):
            return cached[2]

        spending_tendencies = np.array([h.spending_tendency for h in households], dtype=np.float64)
        frugalities = np.array([max(h.frugality, 0.1) for h in households], dtype=np.float64)
        food_prefs = np.array([h.food_preference for h in households], dtype=np.float64)
        housing_prefs = np.array([h.housing_preference for h in households], dtype=np.float64)
        services_prefs = np.array([h.services_preference for h in households], dtype=np.float64)
        drawdown_rates = np.array([h.savings_drawdown_rate for h in households], dtype=np.float64)

        standard_categories = ["food", "housing", "services"]
        category_weights_matrix = np.array([
            [household.category_weights.get(cat, 0.0) for cat in standard_categories]
            for household in households
        ], dtype=np.float64)
        preference_matrix = np.column_stack((food_prefs, housing_prefs, services_prefs))
        biased_matrix = category_weights_matrix * preference_matrix
        precomputed_fractions = []
        for idx, household in enumerate(households):
            bias: Dict[str, float] = {}
            for cat_idx, cat in enumerate(standard_categories):
                val = biased_matrix[idx, cat_idx]
                if val > 0:
                    bias[cat] = val
            for cat, weight in household.category_weights.items():
                cat_lower = cat.lower()
                if cat_lower not in bias and weight > 0:
                    bias[cat_lower] = weight
            total_bias = sum(bias.values())
            if total_bias <= 0:
                precomputed_fractions.append({})
            else:
                fractions = {cat: weight / total_bias for cat, weight in bias.items() if weight > 0}
                precomputed_fractions.append(fractions)

        traits: Dict[str, object] = {
            "spending_tendencies": spending_tendencies,
            "frugalities": frugalities,
            "drawdown_rates": drawdown_rates,
            "precomputed_fractions": precomputed_fractions,
        }
        self._household_static_traits_cache = (households, len(households), traits)
        return traits

    # SOLID: SRP Violation - This method handles BOTH vectorized computation
    # AND legacy fallback logic. Should be split into:
    # - _compute_batch_consumption_budgets()
    # - _execute_legacy_consumption_planning()
    def _batch_plan_consumption(
        self,
        market_prices: Dict[str, float],
        category_market_snapshot: Dict[str, List[Dict[str, float]]],
        good_category_lookup: Optional[Dict[str, str]] = None,
        unemployment_rate: float = 0.0,
        unemployment_benefit: float = 30.0,
    ) -> Dict[int, Dict]:
        """
        Vectorized batch consumption planning for all households.

        This batch path is the only consumption-planning implementation (the per-agent
        HouseholdAgent.plan_consumption was removed in remediation phase 1).

        Args:
            market_prices: Dictionary mapping good_name to current price
            category_market_snapshot: Per-category list of (firm_id, price, quality)
            good_category_lookup: Optional mapping of good_name to category
            unemployment_rate: Current unemployment rate (0.0-1.0)
            unemployment_benefit: Current unemployment benefit level

        Returns:
            Dictionary mapping household_id to consumption plan:
            {
                household_id: {
                    "household_id": int,
                    "category_budgets": {},
                    "planned_purchases": {good_name: quantity},
                    "budget": float
                }
            }

        Note:
            This method has 200+ lines mixing vectorized NumPy logic with
            legacy Python fallback. Per SRP, consider extracting:
            - Budget calculation (lines ~564-470)
            - Price cache building (lines ~472-498)
            - Category fraction precomputation (lines ~500-523)
            - Legacy planning fallback (lines ~556-615)
        """
        cat_lk = good_category_lookup or {}
        def is_housing_good(good: str) -> bool:
            return cat_lk.get(good, good.lower()) == "housing"

        # Extract household attributes as NumPy arrays
        # SOLID: DIP Violation - Directly accesses household internals
        cash_balances = np.array([h.cash_balance for h in self.households], dtype=np.float64)
        static_traits = self._household_static_traits()
        spending_tendencies = static_traits["spending_tendencies"]
        frugalities = static_traits["frugalities"]

        # FIX E: per-income-source MPC. Each cash inflow type has its own
        # marginal-propensity-to-consume coefficient. Wage and benefit income
        # flow to high-MPC households (poor); dividend income to low-MPC
        # (rich). This produces realistic aggregate saving rates and prevents
        # the panic-spiral the old confidence/panic_factor code created.
        employment_status = np.array([h.is_employed for h in self.households], dtype=bool)
        wages = np.array([h.wage for h in self.households], dtype=np.float64)
        if self.payment_sequence != "legacy":
            from payment_behavior import planning_inputs
            net_wages, payment_liquidity, _pressure = planning_inputs(self)
            wages = np.asarray(net_wages, dtype=np.float64)
        drawdown_rates = static_traits["drawdown_rates"]
        dividend_incomes = np.array(
            [max(0.0, float(h.last_dividend_income)) for h in self.households],
            dtype=np.float64,
        )

        cfg = CONFIG.households
        mpc_wage = cfg.mpc_wage
        mpc_benefit = cfg.mpc_benefit
        mpc_dividend = cfg.mpc_dividend

        # Counter-cyclical anti-paradox-of-thrift: at high unemployment, raise
        # MPCs instead of suppressing them. Old code multiplied spending by
        # (1 - panic_factor), accelerating downturns.
        if unemployment_rate > cfg.crisis_unemployment_threshold:
            boost = cfg.crisis_mpc_boost
            mpc_wage = min(1.0, mpc_wage + boost)
            mpc_benefit = min(1.0, mpc_benefit + boost)
            mpc_dividend = min(1.0, mpc_dividend + boost)

        # Personality-driven saving applies to wage income only AND only outside
        # crisis. During crisis (unemployment > threshold) panic dominates
        # personality and we let MPCs reflect the boosted base. Old dampening
        # was suppressing aggregate spending by 15-20pp despite the per-source
        # MPC fix.
        saving_rates = np.clip(drawdown_rates, 0.0, 1.0)
        in_crisis = unemployment_rate > cfg.crisis_unemployment_threshold
        if in_crisis:
            wage_mpc_personalized = np.full(len(self.households), mpc_wage, dtype=np.float64)
        else:
            wage_mpc_personalized = np.where(
                employment_status,
                np.maximum(0.70, mpc_wage * (1.0 - 0.3 * saving_rates)),
                mpc_wage,
            )

        # Income separation: wage when employed, benefit when unemployed.
        wage_income = np.where(employment_status, wages, 0.0)
        benefit_income = np.where(employment_status, 0.0, unemployment_benefit)

        # Per-source budgets, summed.
        base_budget = (
            wage_income * wage_mpc_personalized
            + benefit_income * mpc_benefit
            + dividend_incomes * mpc_dividend
        )

        # Trait factor still modulates discretionary spend slightly (frugal
        # personalities spend less even on the same income), but bounded
        # tighter than the old [0.6, 1.4] range to avoid undoing the MPC fix.
        trait_multiplier = np.clip(spending_tendencies / frugalities, 0.85, 1.15)
        base_budget = base_budget * trait_multiplier

        # Accessible liquidity: cash + 90% of bank deposits (can be withdrawn pre-purchase)
        bank_deposits = np.array([h.bank_deposit for h in self.households], dtype=np.float64)
        deposit_liquidity = 0.90 * np.maximum(bank_deposits, 0.0)
        accessible_liquidity = np.maximum(cash_balances, 0.0) + deposit_liquidity
        if self.payment_sequence != "legacy":
            accessible_liquidity = np.asarray(payment_liquidity, dtype=np.float64)

        # Savings drawdown: personality-derived fraction of accessible liquidity (slow trickle)
        drawdown = drawdown_rates * accessible_liquidity

        # Desperation mode: when income-based budget < survival minimum, raid savings
        # faster. It raises the drawdown, never lowers it below the normal one (B27).
        subsistence_min = CONFIG.households.subsistence_min_cash
        in_desperation = base_budget < subsistence_min
        emergency_rates = np.minimum(drawdown_rates * 5.0, 0.20)
        desperation_drawdown = np.minimum(
            emergency_rates * accessible_liquidity,
            np.maximum(0.0, subsistence_min - base_budget),
        )
        drawdown = np.where(in_desperation, np.maximum(drawdown, desperation_drawdown), drawdown)

        budgets = np.minimum(base_budget + drawdown, accessible_liquidity)

        # Precompute price caches per category for reuse
        price_cache: Dict[str, tuple] = {}
        category_option_cache: Dict[str, List[Dict[str, float]]] = {}
        for category, options in category_market_snapshot.items():
            affordable_opts = [opt for opt in options if opt.get("price", 0.0) > 0]
            if not affordable_opts:
                continue
            prices = [opt["price"] for opt in affordable_opts]
            if not prices:
                continue
            prices.sort()
            min_price = prices[0]
            max_price = prices[-1]
            median_price = prices[len(prices) // 2]
            price_cache[category] = (min_price, median_price, max_price)
            category_option_cache[category] = affordable_opts
        category_array_cache: Dict[str, Dict[str, object]] = {}
        for category, options in category_option_cache.items():
            firm_ids = np.array([opt["firm_id"] for opt in options], dtype=np.int32)
            prices = np.array([opt["price"] for opt in options], dtype=np.float64)
            qualities = np.array([opt["quality"] for opt in options], dtype=np.float64)
            if firm_ids.size == 0:
                continue
            index_lists_by_firm_id: Dict[int, List[int]] = {}
            for position, firm_id in enumerate(firm_ids.tolist()):
                index_lists_by_firm_id.setdefault(int(firm_id), []).append(position)
            category_array_cache[category] = {
                "firm_ids": firm_ids,
                "prices": prices,
                "qualities": qualities,
                "indices_by_firm_id": {
                    firm_id: tuple(positions)
                    for firm_id, positions in index_lists_by_firm_id.items()
                },
            }

        precomputed_fractions = static_traits["precomputed_fractions"]

        # Build consumption plans (fallback to Python loop for now due to complex logic)
        household_consumption_plans = {}
        awareness_market_views = None
        # (category, lowercase key) for categories with options; the per-household
        # awareness check below only needs to know whether each pool is empty.
        awareness_check_categories = [
            (category, category.lower())
            for category, options in (category_market_snapshot or {}).items()
            if options
        ]

        for idx, household in enumerate(self.households):
            budget = budgets[idx]

            if budget <= 0:
                household_consumption_plans[household.household_id] = {
                    "household_id": household.household_id,
                    "category_budgets": {},
                    "planned_purchases": {},
                    "budget": 0.0,
                }
                continue

            # Use category weights if available
            if household.category_weights and sum(household.category_weights.values()) > 0 and category_market_snapshot:
                awareness_needs_refresh = not household.awareness_pool
                if not awareness_needs_refresh:
                    refresh_interval = max(1, int(CONFIG.households.pool_refresh_interval))
                    awareness_needs_refresh = (
                        self.current_tick - household.last_pool_refresh_tick >= refresh_interval
                    )
                if not awareness_needs_refresh:
                    pools = household.awareness_pool
                    for category, category_key in awareness_check_categories:
                        pool = pools.get(category_key)
                        if pool is None and category != category_key:
                            pool = pools.get(category)
                        if not pool:
                            awareness_needs_refresh = True
                            break
                if awareness_needs_refresh:
                    if awareness_market_views is None:
                        awareness_market_views = build_awareness_market_views(category_market_snapshot)
                    household.refresh_awareness_pool(
                        category_market_snapshot,
                        self.current_tick,
                        awareness_market_views=awareness_market_views,
                    )

                planned_purchases = household._plan_category_purchases(
                    budget,
                    price_cache,
                    category_fraction_override=precomputed_fractions[idx],
                    category_array_cache=category_array_cache
                )
                household_consumption_plans[household.household_id] = {
                    "household_id": household.household_id,
                    "category_budgets": {},
                    "planned_purchases": planned_purchases,
                    "budget": float(budgets[idx]),
                }
            else:
                # Legacy good-based allocation
                local_beliefs = dict(household.price_beliefs)

                # Update beliefs with market prices
                for good, market_price in market_prices.items():
                    _update_price_belief(local_beliefs, good, market_price, household.price_expectation_alpha)

                # Normalize good weights
                total_weight = sum(household.good_weights.values())
                if total_weight <= 0:
                    all_goods = set(local_beliefs.keys()) | set(market_prices.keys())
                    if not all_goods:
                        normalized_weights = {}
                    else:
                        equal_weight = 1.0 / len(all_goods)
                        normalized_weights = {g: equal_weight for g in all_goods}
                else:
                    normalized_weights = {
                        g: w / total_weight for g, w in household.good_weights.items()
                    }

                # Plan purchases for each good
                planned_purchases = {}
                for good, weight in normalized_weights.items():
                    if weight <= 0:
                        continue

                    if good in local_beliefs:
                        expected_price = local_beliefs[good]
                    elif good in market_prices:
                        expected_price = market_prices[good]
                    else:
                        expected_price = household.default_price_level

                    if expected_price <= 0:
                        continue

                    good_budget = budget * weight
                    if is_housing_good(good):
                        planned_quantity = min(1.0, good_budget / expected_price)
                    else:
                        planned_quantity = good_budget / expected_price

                    if planned_quantity > 0:
                        planned_purchases[good] = planned_quantity

                household_consumption_plans[household.household_id] = {
                    "household_id": household.household_id,
                    "category_budgets": {},
                    "planned_purchases": planned_purchases,
                    "budget": float(budgets[idx]),
                }

        return household_consumption_plans

    def _apply_cached_consumption_plans(self) -> Dict[int, Dict]:
        """Return cached consumption plans when performance mode is enabled."""
        return self._cached_consumption_plans

    def apply_sector_subsidy_payment(self, requested_share: float) -> Tuple[float, float]:
        """Pay a sector subsidy request from the shared per-tick subsidy cap.

        Returns:
            (government_paid, denied_by_cap)
        """

        requested_share = max(0.0, float(requested_share or 0.0))
        self.last_tick_gov_subsidy_requested += requested_share
        if requested_share <= 0.0:
            return 0.0, 0.0

        if self.payment_sequence != "legacy":
            funded = min(requested_share, self.payment_state["restrictions"].get("G", 0.0))
            if funded:
                self._payment_spend_restriction("G", funded)
            denied = requested_share - funded
            self.last_tick_gov_subsidy_denied_by_cap += denied
            return funded, denied

        if self._payment_free_treasury_cash() <= 0.0:
            self.last_tick_gov_subsidy_denied_by_cap += requested_share
            return 0.0, requested_share

        available = min(
            max(0.0, self.sector_subsidy_remaining_this_tick),
            self._payment_free_treasury_cash(),
        )
        government_paid = min(requested_share, available)
        denied = requested_share - government_paid

        self.sector_subsidy_remaining_this_tick = max(
            0.0,
            self.sector_subsidy_remaining_this_tick - government_paid,
        )
        self.government.cash_balance -= government_paid
        self.last_tick_gov_subsidies += government_paid
        self.last_tick_gov_subsidy_denied_by_cap += denied
        return government_paid, denied

    def refund_sector_subsidy_payment(self, amount: float) -> None:
        """Undo an unused subsidy payment while preserving requested telemetry."""

        refund = max(0.0, float(amount or 0.0))
        if refund <= 0.0:
            return
        if self.payment_sequence != "legacy":
            self.payment_state["restrictions"]["G"] += refund
            self.government.cash_balance += refund
            self.sector_subsidy_remaining_this_tick += refund
            self.last_tick_gov_subsidies = max(0.0, self.last_tick_gov_subsidies - refund)
            self._payment_sync_restrictions()
            return
        self.sector_subsidy_remaining_this_tick = min(
            self.sector_subsidy_cap_this_tick,
            self.sector_subsidy_remaining_this_tick + refund,
        )
        self.government.cash_balance += refund
        self.last_tick_gov_subsidies = max(0.0, self.last_tick_gov_subsidies - refund)

    def settle_capped_subsidized_goods_purchase(
        self,
        household: HouseholdAgent,
        total_cost: float,
        subsidy_rate: float,
    ) -> Tuple[float, float, float]:
        """Settle a subsidized goods purchase without forcing household cash negative."""

        total_cost = max(0.0, float(total_cost or 0.0))
        requested_government_share = total_cost * max(0.0, float(subsidy_rate or 0.0))
        government_cost, _denied = self.apply_sector_subsidy_payment(requested_government_share)
        household_cost = total_cost - government_cost

        if household_cost <= household.cash_balance + 1e-9:
            return household_cost, government_cost, 1.0

        scale = max(0.0, household.cash_balance / max(household_cost, 1e-9))
        scaled_household_cost = household_cost * scale
        scaled_government_cost = government_cost * scale
        refund = government_cost - scaled_government_cost
        self.refund_sector_subsidy_payment(refund)

        return scaled_household_cost, scaled_government_cost, scale

    # SOLID: SRP Violation - This method handles loan repayments, income application,
    # tax deduction, medical payments, purchase processing, inventory management,
    # consumption tracking, and wellbeing updates ALL in one method.
    # Should be split into: _process_loan_repayments(), _apply_household_income(),
    # _process_medical_payments(), _apply_household_purchases(), etc.
    def _batch_apply_household_updates(
        self,
        transfer_plan: Dict[int, float],
        wage_taxes: Dict[int, float],
        per_household_purchases: Dict[int, Dict[str, Tuple[float, float]]],
        good_category_lookup: Optional[Dict[str, str]] = None,
        frozen_wages: Optional[Dict[int, float]] = None,
        payment_receipt_only: bool = False,
        per_firm_sales: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> None:
        """
        Optimized batch update of all household states.

        Combines three separate loops into one for better cache locality.
        Eliminates method call overhead by inlining operations.

        Args:
            transfer_plan: Dictionary mapping household_id to transfer amount
            wage_taxes: Dictionary mapping household_id to tax amount
            per_household_purchases: Dictionary mapping household_id to
                                {good_name: (quantity, price_paid)}
            good_category_lookup: Optional mapping of good_name to category
            frozen_wages: Optional production-boundary ordinary gross wages in
                          currency per tick, keyed by household ID. Direct calls
                          without it retain the current household-wage behavior.
            per_firm_sales: Optional clearing sales, reduced in place when a
                          subsidized purchase is scaled down (see below).

        Note:
            This method is 200+ lines long with multiple responsibilities.
            Per SRP, consider extracting:
            - Loan repayment processing (lines ~860-872)
            - CEO salary processing (lines ~876-882)
            - Income/tax application (lines ~894-696)
            - Medical loan payments (lines ~698-701)
            - Purchase processing (lines ~704-830+)
            - Inventory consumption (lines ~800-830)
            - Wellbeing tracking (lines ~842-844)
        """
        hc = CONFIG.households

        # SOLID: SRP Violation - Loan repayment logic should be in a
        # LoanService or GovernmentReceivables class
        # Process loan repayments first (firms pay government)
        total_loan_repayments = 0.0
        for firm in ([] if payment_receipt_only else self.firms):
            if firm.government_loan_remaining > 0:
                # Make weekly payment
                payment = min(firm.loan_payment_per_tick, firm.government_loan_remaining, firm.cash_balance)
                if payment > 0:
                    firm.cash_balance -= payment
                    firm.government_loan_remaining -= payment
                    total_loan_repayments += payment

        # Government receives loan repayments
        self.government.cash_balance += total_loan_repayments

        # Pre-build lookup tables to avoid O(HH × firms) nested loops
        # CEO lookup: household_id -> list of (firm, median_wage)
        ceo_lookup: Dict[int, list] = {}
        for firm in ([] if payment_receipt_only else self.firms):
            if firm.ceo_household_id is not None and firm.employees:
                wages_list = [firm.actual_wages.get(e_id, firm.wage_offer) for e_id in firm.employees]
                median_wage = float(np.median(wages_list))
                ceo_lookup.setdefault(firm.ceo_household_id, []).append((firm, median_wage))

        # Category lookup: use provided or empty dict for direct access
        cat_lookup = good_category_lookup or {}
        # Engine good names are unique per firm, so a purchase maps to one seller.
        # The A1 reconciliation below asserts this; _clear_goods_market itself
        # allows several firms per good, and then one purchase has no single seller.
        firm_by_good = {f.good_name: f for f in self.firms}

        # Single pass through all households
        for household in self.households:
            hid = household.household_id
            household.met_housing_need = False

            # H4: Record starting cash for anomaly detection
            if not payment_receipt_only:
                household.last_tick_cash_start = household.cash_balance

            # Apply income and taxes
            if frozen_wages is not None:
                wage_income = frozen_wages.get(hid, 0.0)
            else:
                wage_income = household.wage if household.employer_id is not None else 0.0

            # Add CEO salary if household is a CEO of any firm
            ceo_salary = 0.0
            ceo_entries = ceo_lookup.get(hid)
            if ceo_entries and not payment_receipt_only:
                for firm, median_wage in ceo_entries:
                    sal = median_wage * 3.0  # CEO earns 3x median worker
                    ceo_salary += sal
                    firm.cash_balance -= sal

            transfers = transfer_plan.get(hid, 0.0)
            taxes_paid = wage_taxes.get(hid, 0.0)

            # H4: Track income components
            if not payment_receipt_only:
                household.last_wage_income = wage_income + ceo_salary
                household.last_transfer_income = transfers
                household.last_other_income = -taxes_paid  # Taxes are negative income
                household.cash_balance += wage_income + ceo_salary + transfers - taxes_paid
            ledger = household.last_tick_ledger
            wage_flow = wage_income + ceo_salary
            if abs(wage_flow) > 1e-12 and not payment_receipt_only:
                ledger["wage"] = ledger.get("wage", 0.0) + float(wage_flow)
            if abs(transfers) > 1e-12 and not payment_receipt_only:
                ledger["transfers"] = ledger.get("transfers", 0.0) + float(transfers)
            if abs(taxes_paid) > 1e-12 and not payment_receipt_only:
                ledger["taxes"] = ledger.get("taxes", 0.0) - float(taxes_paid)

            # Only unregistered legacy loans use this path; registered medical
            # loans were already serviced in the bank collection phase.
            medical_payment = 0.0 if payment_receipt_only else household.make_medical_loan_payment()
            if medical_payment > 0:
                # Preserve the legacy fallback's treasury recipient.
                self.government.cash_balance += medical_payment

            # Apply purchases (with sector subsidy if active)
            purchases = per_household_purchases.get(hid, {})
            total_spending = 0.0
            subsidy_target = self.government.sector_subsidy_target
            subsidy_rate = self.government._sector_subsidy_rate
            # Reset per-category receipt fields each tick
            household.last_food_units = 0.0
            household.last_food_spend = 0.0
            household.last_housing_units = 0.0
            household.last_housing_spend = 0.0
            household.last_services_units = 0.0
            household.last_services_spend = 0.0
            services_consumed = 0.0
            healthcare_receipt = {}
            if household.last_healthcare_units > 0.0 or household.last_healthcare_spend > 0.0:
                healthcare_receipt["healthcare"] = {
                    "units": household.last_healthcare_units,
                    "spend": household.last_healthcare_spend,
                    "price_per_unit": (
                        household.last_healthcare_spend / household.last_healthcare_units
                        if household.last_healthcare_units > 0.0
                        else 0.0
                    ),
                    "provider_id": household.last_healthcare_provider_id,
                }
            household.last_purchase_breakdown = healthcare_receipt
            for good, (quantity, price_paid) in purchases.items():
                total_cost = quantity * price_paid
                category = cat_lookup.get(good)
                if category is None:
                    category = good.lower()
                # Sector subsidy: government pays subsidy_rate of cost
                if not payment_receipt_only and subsidy_rate > 0.0 and subsidy_target != "none" and category == subsidy_target:
                    household_cost, _govt_share, affordability_scale = (
                        self.settle_capped_subsidized_goods_purchase(
                            household,
                            total_cost,
                            subsidy_rate,
                        )
                    )
                    if affordability_scale < 1.0:
                        seller = firm_by_good.get(good)
                        assert seller is not None and sum(1 for f in self.firms if f.good_name == good) == 1, (
                            f"A1 reconciliation needs exactly one seller of {good!r}"
                        )
                        # Clearing already paid the seller qty * price and took
                        # the units (audit A1): return the unpaid part and its units.
                        unpaid = total_cost - household_cost - _govt_share
                        unsold = quantity * (1.0 - affordability_scale)
                        seller.cash_balance -= unpaid
                        seller.last_revenue -= unpaid
                        seller.last_profit -= unpaid
                        seller.net_profit -= unpaid
                        seller.last_units_sold -= unsold
                        if not seller._is_generic_services_firm():
                            seller.inventory_units += unsold
                        sales = (per_firm_sales or {}).get(seller.firm_id)
                        if sales is not None:
                            sales["revenue"] -= unpaid
                            sales["units_sold"] -= unsold
                    quantity *= affordability_scale
                else:
                    household_cost = (self.payment_book.household_purchase_cost[hid].get(good, 0.0)
                                      if payment_receipt_only else total_cost)
                if quantity <= 0.0:
                    continue
                total_spending += household_cost
                if not payment_receipt_only:
                    household.cash_balance -= household_cost
                if abs(household_cost) > 1e-12 and not payment_receipt_only:
                    ledger["goods"] = ledger.get("goods", 0.0) - float(household_cost)
                if category == "housing" and quantity > 0:
                    household.owns_housing = True
                    household.met_housing_need = True

                if category == "services":
                    # Generic services are consumed as current-tick capacity, not stocked goods.
                    _update_price_belief(
                        household.price_beliefs, good, price_paid, household.price_expectation_alpha
                    )

                    household.last_purchase_breakdown[good] = {
                        "units": quantity, "spend": household_cost, "price_per_unit": price_paid
                    }
                    household.last_services_units += quantity
                    household.last_services_spend += household_cost
                    services_consumed += quantity
                    continue

                # Update inventory for stored goods.
                if good not in household.goods_inventory:
                    household.goods_inventory[good] = 0.0
                if not payment_receipt_only:
                    household.goods_inventory[good] += quantity

                # Update price beliefs
                _update_price_belief(
                    household.price_beliefs, good, price_paid, household.price_expectation_alpha
                )

                # Record per-category purchase receipt
                household.last_purchase_breakdown[good] = {
                    "units": quantity, "spend": household_cost, "price_per_unit": price_paid
                }
                if category == "food":
                    household.last_food_units += quantity
                    household.last_food_spend += household_cost
                elif category == "housing":
                    household.last_housing_units += quantity
                    household.last_housing_spend += household_cost

            # Consume goods from inventory and track per-category consumption.
            # Food is perishable — consume most of it each tick (spoilage).
            # Services are experiential — consume quickly.
            # Other goods decay at a slower rate.
            housing_usage = 1.0
            food_consumed = 0.0
            for good in list(household.goods_inventory.keys()):
                if household.goods_inventory[good] > 0:
                    category = cat_lookup.get(good)
                    if category is None:
                        category = good.lower()
                    current_qty = household.goods_inventory[good]
                    if category == "housing":
                        household.met_housing_need = household.met_housing_need or current_qty >= housing_usage
                        household.goods_inventory[good] = max(0.0, current_qty - housing_usage)
                        if household.goods_inventory[good] < 0.001 and household.owns_housing:
                            household.owns_housing = False
                    elif category == "food":
                        # Food is perishable: consume up to the health threshold,
                        # spoil 50% of the remainder (can't hoard indefinitely).
                        target = hc.food_health_high_threshold  # 5.0
                        eat = min(current_qty, target)
                        leftover = current_qty - eat
                        spoiled = leftover * 0.5
                        household.goods_inventory[good] = max(0.0, leftover - spoiled)
                        food_consumed += eat
                    elif category == "services":
                        # Legacy cleanup: service purchases no longer enter inventory.
                        consumed = current_qty
                        household.goods_inventory[good] = 0.0
                        services_consumed += consumed
                    else:
                        consumed = current_qty * 0.1
                        household.goods_inventory[good] = max(0.0, current_qty - consumed)

                    if household.goods_inventory[good] < 0.001:
                        del household.goods_inventory[good]

            # A household with an active rental contract has their housing need met,
            # even if they bought no housing goods this tick (rental IS their shelter).
            if household.renting_from_firm_id is not None:
                household.met_housing_need = True

            # Update consumption tracking: this_tick for wellbeing, last_tick for next tick's budget planning
            household.food_consumed_last_tick = household.food_consumed_this_tick
            household.services_consumed_last_tick = household.services_consumed_this_tick
            household.food_consumed_this_tick = food_consumed
            household.services_consumed_this_tick = services_consumed

            # H4: Record consumption spending and detect anomalies
            household.last_consumption_spending = total_spending

            # Anomaly detection: Flag large cash changes
            if CONFIG.debug.log_large_changes:
                net_change = (household.last_wage_income + household.last_transfer_income +
                             household.last_dividend_income + household.last_other_income -
                             household.last_consumption_spending)

                if abs(net_change) > CONFIG.debug.large_household_net_change:
                    print(f"[ANOMALY] HH {hid} tick {self.current_tick}: "
                          f"cash change ${net_change:+,.2f} "
                          f"(wage=${household.last_wage_income:.2f}, "
                          f"transfer=${household.last_transfer_income:.2f}, "
                          f"dividend=${household.last_dividend_income:.2f}, "
                          f"other=${household.last_other_income:.2f}, "
                          f"spending=${household.last_consumption_spending:.2f})")

    # -------------------------------------------------------------------------
    # Section: Main tick orchestration
    # -------------------------------------------------------------------------
    # step() is an ordered list of _phase_* calls that share one per-tick
    # _TickScratch; the per-phase methods follow it in tick order.
    def step(self) -> None:
        """
        Execute one full simulation tick.

        step() runs the phase methods below in a fixed order. Each phase takes
        the tick's ``_TickScratch``, which carries the values one phase hands
        to a later one and is dropped when step() returns. The legacy and the
        named payment pipelines (``payment_sequence``) share this order; each
        phase keeps its own ``payment_arm`` branches.

        1. ``_phase_reset_and_shocks``: payment book (payment arm), warm-up
           flag, per-tick telemetry resets, stimulus and subsidy envelope,
           random shocks, healthcare queue, audit before-state.
        2. ``_phase_pre_plan_state``: market views, unemployment and benefit
           anchors, working-capital budget, loan commitments, bailouts and
           public works.
        3. ``_phase_firm_planning``: health snapshots, long-term capital
           offers, production/labor, pricing, wage and capital plans, then
           working-capital bridges, investment loans and the minimum wage.
        4. ``_phase_household_planning``: posted-offer signals, education,
           job-search cooldowns, labor supply, consumption plans and
           consumption loans.
        5. ``_phase_labor_matching``: labor market resolution and labor events.
        6. ``_phase_apply_labor_outcomes``: firm and household outcomes,
           roster sync, continuing-wage raises.
        7. ``_phase_wage_freeze_and_production``: the ``frozen_wages``
           snapshot of this tick's ordinary earned wages, then production and
           costs.
        8. ``_phase_goods_clearing``: income and benefit settlement (payment
           arm), pre-purchase deposit withdrawals, goods clearing, Services
           slot upgrades (legacy).
        9. ``_phase_housing``: rent, repairs, unit expansion, mortgage
           servicing and origination.
        10. ``_phase_misc_and_healthcare``: misc-firm redistribution and
            healthcare; the payment arm also settles care and household dues
            and runs the residual goods pass here.
        11. ``_phase_fiscal_planning``: tax and transfer plans, capital
            recycling.
        12. ``_phase_firm_settlement``: sales, profits, taxes, prices and next
            wage contracts, mirrored to current workers.
        13. ``_phase_household_and_fiscal_settlement``: loan repayments,
            household income, tax and purchase application, late income
            (payment arm), government fiscal results.
        14. ``_phase_institutional_close``: deposit sweep and interest, credit
            scores, government discretionary spending, firm R&D, budget
            pressure.
        15. Wellbeing (inline): warm-up expectation sync, wellbeing update,
            doctor health lock.
        16. ``_phase_lifecycle_and_statistics``: firm exits and entry, the
            legacy policy chooser, statistics and diagnostics.
        17. ``_phase_dividends``: healthcare bonuses and owner dividends; the
            payment arm's next-tick priors and fiscal close.
        18. ``_phase_finalize``: household ledgers, affordability telemetry,
            audit record.

        Finally ``current_tick`` advances and the post-warm-up cooldown ticks
        down.
        """
        if str(getattr(self.config, "payment_sequence", "legacy")) != self.payment_sequence:
            raise ValueError("payment sequence cannot switch during a run")
        tick = _TickScratch(payment_arm=self.payment_sequence != "legacy")
        self._phase_reset_and_shocks(tick)
        self._phase_pre_plan_state(tick)
        self._phase_firm_planning(tick)
        self._phase_household_planning(tick)
        self._phase_labor_matching(tick)
        self._phase_apply_labor_outcomes(tick)
        self._phase_wage_freeze_and_production(tick)
        self._phase_goods_clearing(tick)
        self._phase_housing(tick)
        self._phase_misc_and_healthcare(tick)
        self._phase_fiscal_planning(tick)
        self._phase_firm_settlement(tick)
        self._phase_household_and_fiscal_settlement(tick)
        self._phase_institutional_close(tick)

        # Phase 11.75: Update household wellbeing (happiness, morale, health)
        if self.in_warmup:
            current_price_snapshot = {firm.good_name: firm.price for firm in self.firms}
            self._sync_warmup_expectations(current_price_snapshot)
        if (not self.performance_mode) or (self.current_tick % 10 == 0):
            self._batch_update_wellbeing(
                happiness_multiplier=self.government.social_happiness_multiplier
            )
        self._apply_doctor_health_lock()

        self._phase_lifecycle_and_statistics(tick)
        self._phase_dividends(tick)
        self._phase_finalize(tick)

        # Advance simulation clock after completing the tick
        self.current_tick += 1
        if self.post_warmup_cooldown > 0:
            self.post_warmup_cooldown -= 1

    def _phase_reset_and_shocks(self, tick: _TickScratch) -> None:
        """Open the tick: payment book, warm-up flag, resets, shocks, care queue, audit before-state."""
        payment_arm = tick.payment_arm
        if payment_arm:
            from payment_loans import preflight_loans
            if self.bank is not None:
                self.bank.payment_current_tick = self.current_tick
            if self.current_tick == 0:
                preflight_loans(self)
                self._payment_fiscal_close()
            self.payment_book = PaymentBook(self, self.payment_sequence)
            if self.config.payment_services_project_enabled:
                from payment_government import activate_payment_services_slots
                activate_payment_services_slots(self)
            self.payment_denied_outlays = {}
            self.payment_care_remaining = self.payment_state["restrictions"]["care"]
            self.payment_rent_relief_remaining = self.payment_state["restrictions"]["rent"]
            self._payment_sync_restrictions()
        # Update warm-up flag for this tick using the configured warm-up horizon.
        # SOLID: SRP Violation - Warm-up logic should be in a SimulationState class
        was_in_warmup = self.in_warmup
        self.in_warmup = self.current_tick < self.warmup_ticks
        if was_in_warmup and not self.in_warmup:
            self.post_warmup_cooldown = 8
            self.post_warmup_stimulus_ticks = 6
            self.post_warmup_stimulus_duration = 6
            self._sync_warmup_expectations(self.last_tick_prices)
            self._reset_post_warmup_expectations()
        self._refresh_target_total_firms()
        self._reset_household_tick_visibility()
        if not self.in_warmup:
            self._activate_queued_firms()

        self.last_regime_events = []
        self.last_health_diagnostics = {}
        self.last_firm_distress_diagnostics = {}
        self.last_housing_diagnostics = {}
        self.last_sector_shortage_diagnostics = []
        self.last_tick_gov_bond_purchases = 0.0
        self.last_tick_gov_subsidies = 0.0
        self.last_tick_gov_bailouts = 0.0
        self.last_tick_gov_infrastructure_spending = 0.0
        self.last_tick_gov_technology_spending = 0.0
        self.last_tick_gov_social_spending = 0.0
        self.last_tick_gov_public_works_capitalization = 0.0
        self.last_tick_gov_public_works_requested_startup = 0.0
        self.last_tick_gov_public_works_denied_by_budget = 0.0
        self.last_tick_gov_public_works_affordable_budget = 0.0
        self.last_tick_gov_public_works_jobs_authorized = 0
        self.last_tick_gov_post_warmup_stimulus = 0.0
        self.last_tick_gov_subsidy_requested = 0.0
        self.last_tick_gov_subsidy_denied_by_cap = 0.0
        self.bailout_eligible_firms_by_sector = {}
        self.bailout_denied_firms_by_reason = {}
        self.bailout_received_by_firm_id = {}
        self.last_tick_working_capital_budget = 0.0
        self.last_tick_working_capital_candidates = 0
        self.last_tick_working_capital_issued = 0.0
        self.last_tick_working_capital_denied_budget = 0.0
        self.price_increase_limited_count = 0
        self.rent_increase_limited_count = 0
        self.avg_sector_price_to_median_wage = 0.0
        self.housing_rent_to_median_wage = 0.0
        for firm in self.firms:
            if payment_arm:
                firm.capital_investment_this_tick = 0.0
                firm.payment_wage_arrears = 0.0
                firm.payment_prior_unmet_units = self.last_tick_unmet_demand_by_firm.get(firm.firm_id, 0.0)
            firm.received_bailout_this_tick = False
            firm.received_working_capital_this_tick = False
            firm.working_capital_loan_received_last_tick = 0.0
            if firm.working_capital_support_ticks > 0:
                firm.working_capital_support_ticks = max(0, int(firm.working_capital_support_ticks) - 1)
            if firm.working_capital_support_ticks <= 0:
                firm.working_capital_hire_budget_workers = 0
        if payment_arm:
            for (fid, _), amount in self.payment_state["wage_claims"].items():
                firm = self.firm_lookup.get(fid)
                if firm is not None:
                    firm.payment_wage_arrears += amount
            self.payment_state["capital_routes"] = []
            self.payment_state["capital_routes_released"] = False
        self.sector_subsidy_cap_this_tick = 0.0
        self.sector_subsidy_remaining_this_tick = 0.0
        self.last_tick_pre_purchase_deposit_withdrawals = 0.0
        self.last_tick_end_tick_deposit_sweeps = 0.0
        self.government.reset_tick_bailout_telemetry()
        self.government.bailout_cycle_ticks += 1

        if self.post_warmup_stimulus_ticks > 0:
            self._apply_post_warmup_stimulus()

        if payment_arm:
            self._payment_reserve_subsidy()
        else:
            recent_gdp = trailing_gdp(self)
            self.sector_subsidy_cap_this_tick = get_sector_subsidy_cap(self.government, recent_gdp)
            self.sector_subsidy_remaining_this_tick = self.sector_subsidy_cap_this_tick

        # Reset bank per-tick telemetry (no-op when bank is None)
        if self.bank is not None:
            self.bank.reset_tick_telemetry()

        self.food_unmet_demand = 0.0
        self.services_unmet_demand = 0.0
        self.services_unmet_demand_by_firm = {}
        self.current_tick_unmet_demand_by_firm = {}

        # Random economic shocks (stochastic events)
        self._apply_random_shocks()
        self._reset_healthcare_tick_state()
        self._apply_doctor_health_lock()
        if payment_arm:
            from payment_loans import prepare_household_dues
            from payment_sectors import enqueue_payment_care_requests, requeue_payment_care_due
            prepare_household_dues(self)
            requeue_payment_care_due(self)
            enqueue_payment_care_requests(self)
        else:
            self._enqueue_healthcare_requests()
        tick.audit_firm_states_before = {}
        tick.audit_household_states_before = {}
        tick.audit_government_state_before = {}
        if self.audit_log_enabled:
            tick.audit_firm_states_before = self._capture_audit_firm_state(self.firms)
            tick.audit_household_states_before = self._capture_audit_household_state()
            tick.audit_government_state_before = self._capture_audit_government_state()

    def _phase_pre_plan_state(self, tick: _TickScratch) -> None:
        """Market views, unemployment and benefit anchors, then stabilizer operations before planning."""
        (
            tick.good_category_lookup,
            tick.category_market_snapshot,
            tick.housing_private_inventory,
            housing_baseline_inventory,
        ) = self._build_firm_market_views()
        tick.total_households = len(self.households)
        tick.housing_inventory_overhang = tick.housing_private_inventory + housing_baseline_inventory
        unemployed_count = sum(1 for h in self.households if not h.is_employed)
        tick.unemployment_rate = (unemployed_count / tick.total_households) if tick.total_households > 0 else 0.0
        self._unemployment_history.append(tick.unemployment_rate)
        self.unemployment_short_ma = sum(self._unemployment_history) / len(self._unemployment_history)

        tick.gov_benefit = self.government.get_unemployment_benefit_level()
        if CONFIG.firms.working_capital_enabled and CONFIG.government.auto_working_capital_backstop:
            self.last_tick_working_capital_budget = self._working_capital_budget_for_tick(tick.unemployment_rate)

        if self.enable_government_stabilizers:
            # Update outstanding emergency-loan commitments before offering new aid
            self._update_loan_commitments()
            self._execute_bailouts()
            if self.government.public_works_toggle == "on":
                self._ensure_public_works_capacity(tick.unemployment_rate)
            else:
                self._deauthorize_public_works_capacity()

    def _phase_firm_planning(self, tick: _TickScratch) -> None:
        """Firms plan production, labor, prices, wages and capital; bridges, investment loans, min wage."""
        unemployment_rate = tick.unemployment_rate
        total_households = tick.total_households
        housing_inventory_overhang = tick.housing_inventory_overhang
        housing_private_inventory = tick.housing_private_inventory
        gov_benefit = tick.gov_benefit
        payment_arm = tick.payment_arm
        # Phase 1: Firms plan
        tick.firm_production_plans = {}
        tick.firm_price_plans = {}
        tick.firm_wage_plans = {}
        tick.firm_health_snapshots = {}
        firm_health_snapshot_objects: Dict[int, object] = {}
        firm_state_before = {
            firm.firm_id: {
                "burn_mode": bool(getattr(firm, "burn_mode", False)),
                "survival_mode": bool(getattr(firm, "survival_mode", False)),
            }
            for firm in self.firms
        }
        current_private_offer_buckets: Dict[str, List[float]] = {}
        for firm in self.firms:
            if firm.is_baseline:
                continue
            category = str(firm.good_category)
            current_private_offer_buckets.setdefault(category, []).append(float(firm.wage_offer))

        tick.category_wage_anchor_p75 = {}
        for category, offers in current_private_offer_buckets.items():
            if offers:
                offers_arr = np.array(offers, dtype=np.float32)
                tick.category_wage_anchor_p75[category] = float(np.percentile(offers_arr, 75))

        # _issue_working_capital_bridges (after this loop) recomputes and stores
        # every firm's working-capital candidacy whenever it gets past its early
        # returns, overwriting all the per-firm fields and the tick counter the
        # in-loop call writes; nothing reads those in between. Record them here
        # only when the bridges will not run.
        wc_cfg = CONFIG.firms
        working_capital_bridges_run = (
            bool(wc_cfg.working_capital_enabled)
            and bool(CONFIG.government.auto_working_capital_backstop)
            and not (unemployment_rate < float(wc_cfg.working_capital_unemployment_trigger))
        )
        # A plain attribute read; only GovernmentAgent.apply_policy_levers changes it.
        planning_minimum_wage = self.government.get_minimum_wage()

        for firm in self.firms:
            firm.clear_planner_diagnostics()
            firm.policy_minimum_wage = planning_minimum_wage
            health_snapshot = firm.refresh_health_snapshot(
                sell_through_rate=self.last_tick_sell_through_rate.get(firm.firm_id, 0.5),
                category_wage_anchor_p75=tick.category_wage_anchor_p75.get(
                    str(firm.good_category),
                    float(firm.wage_offer),
                ),
            )
            firm_health_snapshot_objects[firm.firm_id] = health_snapshot
            if self.audit_log_enabled:
                # Only the end-of-tick audit record reads these dicts.
                tick.firm_health_snapshots[firm.firm_id] = {
                    "cash_runway_ticks": float(health_snapshot.cash_runway_ticks),
                    "smoothed_profit_margin": float(health_snapshot.smoothed_profit_margin),
                    "sell_through_rate": float(health_snapshot.sell_through_rate),
                    "inventory_weeks": float(health_snapshot.inventory_weeks),
                    "unfilled_positions_streak": int(health_snapshot.unfilled_positions_streak),
                    "worker_turnover_this_tick": int(health_snapshot.worker_turnover_this_tick),
                    "survival_mode": bool(health_snapshot.survival_mode),
                    "burn_mode": bool(health_snapshot.burn_mode),
                    "category_wage_anchor_p75": float(health_snapshot.category_wage_anchor_p75),
                }
            # Long-term capital expansion lending — services + housing only.
            # Offered BEFORE production planning so any new capacity (services
            # production_capacity_units or housing max_rental_units) is visible
            # to the same-tick plan.
            if not payment_arm:
                # Legacy plan_capital_investment (below) resets
                # capital_investment_this_tick, which used to drop the recycle
                # units this loan books (audit A2). Clear last tick's value
                # here instead and carry the loan's units across that reset.
                firm.capital_investment_this_tick = 0.0
            self._maybe_offer_long_term_capital_loan(
                firm=firm,
                health_snapshot=health_snapshot,
                unemployment_rate=unemployment_rate,
                total_households=total_households,
            )
            long_term_recycle_units = firm.capital_investment_this_tick
            # Plan production and labor
            production_plan = firm.plan_production_and_labor(
                self.last_tick_sales_units.get(firm.firm_id, 0.0),
                in_warmup=self.in_warmup,
                total_households=total_households,
                global_unsold_inventory=housing_inventory_overhang,
                private_housing_inventory=housing_private_inventory,
                large_market=self.large_market,
                post_warmup_cooldown=(self.post_warmup_cooldown > 0),
                health_snapshot=health_snapshot,
                minimum_wage_floor=planning_minimum_wage,
                last_tick_unmet_units=self.last_tick_unmet_demand_by_firm.get(firm.firm_id, 0.0),
            )
            tick.firm_production_plans[firm.firm_id] = production_plan
            if not working_capital_bridges_run:
                self._record_working_capital_candidate_diagnostics(
                    firm,
                    health_snapshot,
                    unemployment_rate,
                )

            # Plan pricing — pass current profit tax rate so firms inflate gross
            # margins to preserve their targeted after-tax margin.
            price_plan = firm.plan_pricing(
                self.last_tick_sell_through_rate.get(firm.firm_id, 0.5),
                unemployment_rate=unemployment_rate,
                in_warmup=self.in_warmup,
                health_snapshot=health_snapshot,
                profit_tax_rate=float(self.government.profit_tax_rate),
            )
            self._apply_price_stabilization_to_plan(firm, price_plan)
            tick.firm_price_plans[firm.firm_id] = price_plan

            # Plan wage (pass unemployment rate + short-MA for Phillips Curve)
            wage_plan = firm.plan_wage(
                unemployment_rate=unemployment_rate,
                unemployment_benefit=gov_benefit,
                in_warmup=self.in_warmup,
                health_snapshot=health_snapshot,
                unemployment_short_ma=self.unemployment_short_ma,
                minimum_wage_floor=planning_minimum_wage,
            )
            tick.firm_wage_plans[firm.firm_id] = wage_plan

            # Healthcare labor is managed out-of-band from market hiring:
            # one healthcare firm staffed by doctor/resident pool.
            if (firm.good_category or "").lower() == "healthcare":
                production_plan["planned_hires_count"] = 0
                production_plan["planned_layoffs_ids"] = []
                firm.planned_hires_count = 0
                firm.planned_layoffs_ids = []

            # Fix 21: Capital investment decision (may set needs_investment_loan)
            capital_cash_before = firm.cash_balance
            firm.plan_capital_investment(bank=self.bank)
            if not payment_arm:
                firm.capital_investment_this_tick += long_term_recycle_units
            if payment_arm and firm.cash_balance < capital_cash_before - MONEY_EPS:
                self._payment_record_capital_spend(firm, capital_cash_before - firm.cash_balance, "self_financed")

        self._issue_working_capital_bridges(firm_health_snapshot_objects, unemployment_rate)
        self._record_firm_distress_transitions(firm_state_before)

        # Phase 1.5: Process investment loan requests from Phase 1
        if self.bank is not None:
            self._offer_investment_loans()

        # Enforce minimum wage floor (government policy)
        minimum_wage = self.government.get_minimum_wage()
        for wage_plan in tick.firm_wage_plans.values():
            if wage_plan["wage_offer_next"] < minimum_wage:
                wage_plan["wage_offer_next"] = minimum_wage

    def _phase_household_planning(self, tick: _TickScratch) -> None:
        """Households plan: offer signals, education, cooldowns, labor supply, consumption, loans."""
        firm_wage_plans = tick.firm_wage_plans
        firm_production_plans = tick.firm_production_plans
        gov_benefit = tick.gov_benefit
        category_market_snapshot = tick.category_market_snapshot
        good_category_lookup = tick.good_category_lookup
        unemployment_rate = tick.unemployment_rate
        # Phase 2: Households plan
        tick.household_labor_plans = {}

        # One firm pass: reset the per-tick turnover counter, collect the
        # posted-offer pool (private, non-healthcare/housing) and the planned
        # offers by category. No RNG; each list keeps self.firms order.
        active_private_offers = []
        all_private_offers = []
        planned_private_offer_buckets: Dict[str, List[float]] = {}
        for firm in self.firms:
            firm.worker_turnover_this_tick = 0
            if firm.is_baseline or firm.firm_id not in firm_wage_plans:
                continue
            offer = float(firm_wage_plans[firm.firm_id]["wage_offer_next"])
            planned_private_offer_buckets.setdefault(str(firm.good_category), []).append(offer)
            if (firm.good_category or "").lower() in {"healthcare", "housing"}:
                continue

            all_private_offers.append(offer)

            planned_hires = int(
                firm_production_plans.get(firm.firm_id, {}).get("planned_hires_count", 0) or 0
            )
            if planned_hires > 0:
                active_private_offers.append(offer)

        posted_offer_pool = active_private_offers or all_private_offers
        mean_posted_wage = (
            float(np.percentile(posted_offer_pool, CONFIG.households.unemployed_market_anchor_percentile))
            if posted_offer_pool
            else 0.0
        )
        category_posted_wage_signals: Dict[str, float] = {}
        for category, offers in planned_private_offer_buckets.items():
            if offers:
                category_posted_wage_signals[category] = sum(offers) / len(offers)

        # One household pass: education, job-search cooldown (post-warmup only,
        # on-the-job / "newspaper" mechanic), labor plan, consumption-loan
        # request (bank only), in that order per household. Only the cooldown
        # draws from an RNG (_cooldown_rng, in household order as before); each
        # body reads and writes only its own household (plus the bank's credit
        # scores, read-only). Education spending is still summed in household
        # order and routed to the misc pool before plan normalization.
        # The consumption-loan request runs here, before consumption planning, so
        # planning below must not change household cash, wage, expected wage or subsistence.
        total_education_spending = 0.0
        _cooldown_rng = random.Random(int(CONFIG.random_seed) + self.current_tick * 31337)
        tick_cooldowns = not self.in_warmup
        bank = self.bank
        firm_lookup = self.firm_lookup
        for household in self.households:
            total_education_spending += household.maybe_active_education()
            if tick_cooldowns:
                household.tick_job_search_cooldown(_cooldown_rng)
            employer_category = None
            if household.employer_id is not None and household.employer_id in firm_lookup:
                employer_category = firm_lookup[household.employer_id].good_category
            labor_plan = household.plan_labor_supply(
                gov_benefit,
                mean_posted_wage=mean_posted_wage,
                category_posted_wages=category_posted_wage_signals,
                employer_category=employer_category,
            )
            tick.household_labor_plans[household.household_id] = labor_plan
            if bank is not None:
                household.maybe_request_consumption_loan(bank=bank)
        if total_education_spending > 0:
            self._collect_misc_revenue(total_education_spending)
        self._normalize_household_labor_plans(
            tick.household_labor_plans,
            firm_wage_plans,
            market_anchor_wage=mean_posted_wage,
        )
        self.last_household_labor_plans = {
            int(household_id): dict(plan)
            for household_id, plan in tick.household_labor_plans.items()
        }

        # Consumption planning now vectorized (major speedup)
        if (not self.performance_mode) or (self.current_tick % 5 == 0):
            tick.household_consumption_plans = self._batch_plan_consumption(
                self.last_tick_prices,
                category_market_snapshot,
                good_category_lookup,
                unemployment_rate,
                gov_benefit,
            )
            if self.performance_mode:
                self._cached_consumption_plans = tick.household_consumption_plans
        else:
            tick.household_consumption_plans = self._apply_cached_consumption_plans()

        # Phase 2a: Consumption credit (Fix 25) — bridge low-cash households.
        # Requests were flagged in the household pass above; only
        # _offer_consumption_loans reads them, and it must follow consumption
        # planning because disbursal changes cash.
        if self.bank is not None:
            self._offer_consumption_loans()

    def _phase_labor_matching(self, tick: _TickScratch) -> None:
        """Resolve the labor market (with the payment Services-project hire) and record labor events."""
        payment_arm = tick.payment_arm
        firm_production_plans = tick.firm_production_plans
        firm_wage_plans = tick.firm_wage_plans
        household_labor_plans = tick.household_labor_plans
        # Phase 3: Labor market matching
        self.payment_project_baseline_hires = {}
        if payment_arm and self.config.payment_services_project_enabled:
            project = self.payment_state.get("services_project")
            if project and project.get("status") == "authorized" and project.get("work_tick") == self.current_tick:
                fid = project["firm_id"]
                plan = firm_production_plans.get(fid)
                if plan is not None:
                    self.payment_project_baseline_hires[fid] = int(plan.get("planned_hires_count", 0))
                    plan["planned_hires_count"] = int(plan.get("planned_hires_count", 0)) + 1
                    firm = self.firm_lookup.get(fid)
                    if firm is not None:
                        firm.planned_hires_count = int(plan["planned_hires_count"])
        tick.firm_labor_outcomes, tick.household_labor_outcomes = self._run_labor_matching(
            firm_production_plans,
            firm_wage_plans,
            household_labor_plans
        )
        self._record_labor_events(
            firm_labor_outcomes=tick.firm_labor_outcomes,
            firm_wage_plans=firm_wage_plans,
            household_labor_plans=household_labor_plans,
        )
        if payment_arm:
            from payment_behavior import diagnose_observed_offer
            for fid, outcome in tick.firm_labor_outcomes.items():
                for hid in outcome.get("hired_households_ids", []):
                    gross = outcome.get("actual_wages", {}).get(hid)
                    if gross is not None:
                        diagnose_observed_offer(self, hid, float(gross), fid)
        self._record_failed_hiring_events(firm_production_plans, tick.firm_labor_outcomes)

    def _phase_apply_labor_outcomes(self, tick: _TickScratch) -> None:
        """Apply labor outcomes, sync rosters, continuing-wage raises and the payment project worker."""
        firm_labor_outcomes = tick.firm_labor_outcomes
        household_labor_outcomes = tick.household_labor_outcomes
        payment_arm = tick.payment_arm
        # Phase 4: Apply labor outcomes
        # Use cached wage percentiles (update every 5 ticks for performance)
        if self.current_tick - self.wage_percentile_cache_tick >= 5:
            # Collect ALL currently-paid wages (not just new hires) for accurate percentiles.
            market_paid_wages = []
            for firm in self.firms:
                for eid in firm.employees:
                    market_paid_wages.append(firm.actual_wages.get(eid, firm.wage_offer))

            if market_paid_wages:
                # Use NumPy for fast percentile calculation
                wages_arr = np.array(market_paid_wages, dtype=np.float32)
                wage_anchor_low = float(np.percentile(wages_arr, 25))
                wage_anchor_mid = float(np.percentile(wages_arr, 50))
                wage_anchor_high = float(np.percentile(wages_arr, 75))
            else:
                wage_anchor_low = wage_anchor_mid = wage_anchor_high = None

            self.cached_wage_percentiles = (wage_anchor_low, wage_anchor_mid, wage_anchor_high)
            self.wage_percentile_cache_tick = self.current_tick
        else:
            wage_anchor_low, wage_anchor_mid, wage_anchor_high = self.cached_wage_percentiles

        for firm in self.firms:
            firm.apply_labor_outcome(firm_labor_outcomes[firm.firm_id])

        for household in self.households:
            anchor = None
            if household.skills_level < 0.4:
                anchor = wage_anchor_low
            elif household.skills_level > 0.7:
                anchor = wage_anchor_high
            else:
                anchor = wage_anchor_mid

            hh_outcome = household_labor_outcomes[household.household_id]
            new_employer_id = hh_outcome.get("employer_id")
            if new_employer_id is not None and new_employer_id in self.firm_lookup:
                employer_firm = self.firm_lookup[new_employer_id]
                if household.household_id in employer_firm.actual_wages:
                    resolved_wage = employer_firm.actual_wages[household.household_id]
                    if resolved_wage != hh_outcome.get("wage"):
                        hh_outcome = dict(hh_outcome)
                        hh_outcome["wage"] = resolved_wage

            household.apply_labor_outcome(
                hh_outcome,
                market_wage_anchor=anchor,
                current_tick=self.current_tick
            )

        # Keep firm-side employee rosters aligned with household employment outcomes.
        # This prevents stale counts in firm telemetry versus unemployment metrics.
        self._sync_firm_employee_rosters()
        if payment_arm:
            self.payment_project_worker_by_firm = {}
            if self.config.payment_services_project_enabled:
                from payment_government import assign_payment_services_project_worker
                self.payment_project_worker_by_firm = assign_payment_services_project_worker(
                    self, {fid: outcome.get("hired_households_ids", []) for fid, outcome in firm_labor_outcomes.items()},
                    baseline_hire_count=self.payment_project_baseline_hires,
                )

        # Update wages for continuing employees every 50 ticks (small 2-3% increases)
        if self.current_tick % 50 == 0:
            self._update_continuing_employee_wages()
        if payment_arm and self.config.payment_services_project_enabled:
            project = self.payment_state.get("services_project")
            if project and project.get("status") == "assigned":
                firm = self.firm_lookup.get(project["firm_id"])
                if firm is not None:
                    project["frozen_wage_due"] = float(firm.actual_wages.get(project["worker_id"], 0.0))

    def _phase_wage_freeze_and_production(self, tick: _TickScratch) -> None:
        """Freeze this tick's ordinary earned wages, then firms apply production, costs and expectations."""
        firm_production_plans = tick.firm_production_plans
        payment_arm = tick.payment_arm
        # Freeze ordinary earned wages at the production boundary (currency per
        # tick, all households including zero-paid unemployed households).
        tick.frozen_wages = {
            hh.household_id: (hh.wage if hh.is_employed else 0.0)
            for hh in self.households
        }

        # Phase 5: Firms apply production and costs
        for firm in self.firms:
            production_plan = firm_production_plans[firm.firm_id]
            planned_production_units = production_plan["planned_production_units"]

            # Calculate actual production based on workforce experience and skills
            actual_production_units = self._calculate_experience_adjusted_production(
                firm, planned_production_units
            )

            firm.apply_production_and_costs({
                "realized_production_units": actual_production_units,
                "other_variable_costs": 0.0,
                "funded_payroll_book": payment_arm,
                "productive_worker_count": len(firm.employees) - (1 if payment_arm and firm.firm_id in self.payment_project_worker_by_firm else 0),
            })

            # Update expectations
            firm.apply_updated_expectations(
                production_plan["updated_expected_sales"]
            )

    def _phase_goods_clearing(self, tick: _TickScratch) -> None:
        """Settle income (payment arm), withdraw deposits, clear goods; legacy Services slot upgrades."""
        payment_arm = tick.payment_arm
        frozen_wages = tick.frozen_wages
        household_consumption_plans = tick.household_consumption_plans
        # Phase 5b: Pre-purchase deposit withdrawals — move planned-spend shortfall to cash
        if payment_arm:
            from payment_loans import prepare_household_dues
            from payment_sectors import payment_deposit_quotes
            self.payment_book.settle_income(frozen_wages)
            from payment_behavior import observe_settled_tax
            observe_settled_tax(self)
            self.payment_book.settle_benefits()
            self._payment_sync_restrictions()
            due_by_household = prepare_household_dues(self)
            quotes = payment_deposit_quotes(self, household_consumption_plans, due_by_household)
            self._payment_withdraw_deposits(quotes)
        else:
            self._withdraw_deposits_for_planned_consumption(household_consumption_plans)

        # Phase 6: Goods market clearing
        if payment_arm:
            from payment_sectors import PaymentGoodsMarket
            tick.goods_market = PaymentGoodsMarket(self, household_consumption_plans, self.firms)
            tick.goods_market.first_pass()
            tick.per_household_purchases, tick.per_firm_sales = self.payment_book.purchases, self.payment_book.receipts
        else:
            tick.per_household_purchases, tick.per_firm_sales = self._clear_goods_market(
                household_consumption_plans, self.firms
            )

        # Phase 6.1: Services firms expand employee-slot infrastructure only
        # after sustained full current-tick capacity utilization.
        if not payment_arm:
            for firm in self.firms:
                if (firm.good_category or "").lower() == "services":
                    firm.consider_service_infrastructure_upgrade(economy=self)
            if self.bank is not None:
                self._offer_service_infrastructure_loans()

    def _phase_housing(self, tick: _TickScratch) -> None:
        """Housing: rent clearing, repairs, unit expansion, mortgage servicing and origination."""
        payment_arm = tick.payment_arm
        # Phase 6.5: Housing rental market clearing
        if payment_arm:
            from payment_projects import complete_payment_projects
            from payment_sectors import settle_payment_rent
            complete_payment_projects(self)
            settle_payment_rent(self)
        else:
            self._clear_housing_rental_market()
        self._apply_housing_repairs()

        # Phase 6.6: Housing firms consider unit expansion
        if payment_arm:
            from payment_projects import try_start_self_funded_project, start_payment_mortgage_project
            expansion_homeless_count = 0
        else:
            # Nothing in this loop changes tenancy, so one count serves every firm.
            expansion_homeless_count = sum(1 for h in self.households if h.renting_from_firm_id is None)
        for firm in self.firms:
            if firm.good_category.lower() == "housing":
                if payment_arm:
                    try_start_self_funded_project(self, firm)
                else:
                    firm.invest_in_unit_expansion(economy=self, homeless_count=expansion_homeless_count)
                # Route self-financed construction cost into economy (closed-loop)
                pending = getattr(firm, "_pending_construction_cost", 0.0)
                if pending > 0:
                    self._collect_misc_revenue(pending)
                    firm._pending_construction_cost = 0.0

        # Phase 6.6b: Service existing housing mortgages, then originate new ones
        if self.bank is not None:
            self._service_housing_mortgage_debt()
            if payment_arm:
                for firm in self.firms:
                    if (firm.good_category or "").lower() == "housing":
                        start_payment_mortgage_project(self, firm)
            else:
                self._offer_housing_expansion_loans()

    def _phase_misc_and_healthcare(self, tick: _TickScratch) -> None:
        """Misc-firm redistribution and healthcare; the payment arm also clears care, dues and residual goods."""
        payment_arm = tick.payment_arm
        goods_market = tick.goods_market
        # Phase 6.7: Misc firm operations
        if not payment_arm:
            self._misc_firm_add_beneficiary()
            self._misc_firm_redistribute_revenue()

        # Phase 6.8: Queue-based healthcare service processing
        if payment_arm:
            from payment_loans import collect_household_dues
            from payment_sectors import settle_payment_care
            settle_payment_care(self, tick.per_firm_sales)
            collect_household_dues(self)
            goods_market.second_pass()
            goods_market.finish()
            tick.per_household_purchases, tick.per_firm_sales = self.payment_book.purchases, self.payment_book.receipts
            self._misc_firm_add_beneficiary()
            self._misc_firm_redistribute_revenue()
            for firm in self.firms:
                if (firm.good_category or "").lower() == "services":
                    firm.consider_service_infrastructure_upgrade(economy=self, current_units_sold=tick.per_firm_sales.get(firm.firm_id, {}).get("units_sold", 0.0))
            if self.bank is not None:
                self._offer_service_infrastructure_loans()
        else:
            self._process_healthcare_services(tick.per_firm_sales)

    def _phase_fiscal_planning(self, tick: _TickScratch) -> None:
        """Government plans taxes and transfers; capital spending and project proceeds are recycled."""
        payment_arm = tick.payment_arm
        frozen_wages = tick.frozen_wages
        per_firm_sales = tick.per_firm_sales
        # Phase 7: Government plans taxes
        household_tax_snapshots = (
            [] if payment_arm else self._build_household_tax_snapshots(frozen_wages=frozen_wages)
        )
        firm_tax_snapshots = self._build_firm_tax_snapshots(per_firm_sales)
        tick.price_ceiling_tax_by_firm_id = {
            int(snapshot["firm_id"]): float(snapshot.get("price_ceiling_tax", 0.0))
            for snapshot in firm_tax_snapshots
        }
        tick.total_price_ceiling_taxes = sum(tick.price_ceiling_tax_by_firm_id.values())
        tick.assessed_project_receipts = (dict(self.payment_state.get("services_pending_receipts", {}))
                                     if payment_arm else {})

        tick.tax_plan = self.government.plan_taxes(
            household_tax_snapshots,
            firm_tax_snapshots
        )
        if payment_arm:
            tick.tax_plan["wage_taxes"] = dict(self.payment_book.wage_taxes)
            self.payment_state["services_pending_receipts"] = {}

        # Phase 8: Government plans transfers
        if payment_arm:
            tick.transfer_plan = dict(self.payment_book.benefits)
        else:
            household_transfer_snapshots = self._build_household_transfer_snapshots()
            tick.transfer_plan = self.government.plan_transfers(household_transfer_snapshots)

        # Phase 8.5: Recycle capital investment spending to households
        self._recycle_capital_investment()
        if payment_arm:
            from payment_projects import distribute_payment_project_proceeds
            distribute_payment_project_proceeds(self)

    def _phase_firm_settlement(self, tick: _TickScratch) -> None:
        """Firms apply sales, profits, taxes, prices and next wage contracts; contracts mirror to workers."""
        per_firm_sales = tick.per_firm_sales
        tax_plan = tick.tax_plan
        price_ceiling_tax_by_firm_id = tick.price_ceiling_tax_by_firm_id
        payment_arm = tick.payment_arm
        assessed_project_receipts = tick.assessed_project_receipts
        firm_price_plans = tick.firm_price_plans
        firm_wage_plans = tick.firm_wage_plans
        # Phase 9: Apply sales, profits, taxes to firms
        for firm in self.firms:
            sales_data = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
            profit_tax = tax_plan["profit_taxes"].get(firm.firm_id, 0.0)
            property_tax = tax_plan["property_taxes"].get(firm.firm_id, 0.0)
            price_ceiling_tax = price_ceiling_tax_by_firm_id.get(firm.firm_id, 0.0)

            # Pay property tax if housing firm
            if payment_arm:
                self.payment_book.release_firm_receipts(firm)
                available_tax_cash = max(0.0, firm.cash_balance)
                property_tax = min(property_tax, available_tax_cash)
                available_tax_cash -= property_tax
                profit_tax = min(profit_tax, available_tax_cash)
                available_tax_cash -= profit_tax
                price_ceiling_tax = min(price_ceiling_tax, available_tax_cash)
                tax_plan["property_taxes"][firm.firm_id] = property_tax
                tax_plan["profit_taxes"][firm.firm_id] = profit_tax
                price_ceiling_tax_by_firm_id[firm.firm_id] = price_ceiling_tax
            if property_tax > 0:
                firm.cash_balance -= property_tax

            firm.apply_sales_and_profit({
                "units_sold": sales_data["units_sold"],
                "revenue": sales_data["revenue"] + (self.payment_book.rent_receipts.get(firm.firm_id, 0.0)
                                                   + assessed_project_receipts.get(firm.firm_id, 0.0) if payment_arm else 0.0),
                "profit_taxes_paid": profit_tax + price_ceiling_tax,
                "committed_sale_book": payment_arm,
            })

            # Apply price and wage updates
            firm.apply_price_and_wage_updates(
                firm_price_plans[firm.firm_id],
                firm_wage_plans[firm.firm_id]
            )

            # Mirror actual worker contracts to households whose employer still matches
            for worker_id, contract_wage in firm.actual_wages.items():
                worker_hh = self.household_lookup.get(worker_id)
                if worker_hh is not None and worker_hh.employer_id == firm.firm_id:
                    worker_hh.wage = contract_wage
        if payment_arm:
            from payment_sectors import update_payment_housing_asks
            update_payment_housing_asks(self)
            tick.total_price_ceiling_taxes = sum(price_ceiling_tax_by_firm_id.values())

    def _phase_household_and_fiscal_settlement(self, tick: _TickScratch) -> None:
        """Loan repayments, household income/tax/purchase application, late income, fiscal results."""
        payment_arm = tick.payment_arm
        transfer_plan = tick.transfer_plan
        tax_plan = tick.tax_plan
        per_household_purchases = tick.per_household_purchases
        good_category_lookup = tick.good_category_lookup
        frozen_wages = tick.frozen_wages
        total_price_ceiling_taxes = tick.total_price_ceiling_taxes
        # Phase 9.5: Bank loan repayments (firms & households → bank)
        # Runs after wages and sales so borrowers have income before repayment.
        if payment_arm:
            from payment_loans import collect_firm_dues
            collect_firm_dues(self)
        elif self.bank is not None:
            self._collect_bank_loan_repayments()

        # Phase 10: Apply income, taxes, transfers, purchases to households
        if payment_arm:
            self._payment_collect_direct_firm_loans()
        self._batch_apply_household_updates(
            transfer_plan,
            tax_plan["wage_taxes"],
            per_household_purchases,
            good_category_lookup,
            frozen_wages=frozen_wages,
            payment_receipt_only=payment_arm,
            per_firm_sales=tick.per_firm_sales,
        )
        if payment_arm:
            self.payment_book.release_late_income()

        # Phase 11: Apply government fiscal results
        tick.total_wage_taxes = sum(tax_plan["wage_taxes"].values())
        tick.total_profit_taxes = sum(tax_plan["profit_taxes"].values())
        tick.total_property_taxes = sum(tax_plan["property_taxes"].values())
        tick.total_transfers = sum(transfer_plan.values())

        self.last_tick_gov_wage_taxes = tick.total_wage_taxes
        self.last_tick_gov_profit_taxes = tick.total_profit_taxes + total_price_ceiling_taxes
        self.last_tick_gov_property_taxes = tick.total_property_taxes
        self.last_tick_gov_transfers = tick.total_transfers

        self.government.apply_fiscal_results(
            (0.0 if payment_arm else tick.total_wage_taxes),
            tick.total_profit_taxes + total_price_ceiling_taxes,  # Include price ceiling tax as profit tax
            (0.0 if payment_arm else tick.total_transfers),
            tick.total_property_taxes
        )
        if payment_arm:
            self.payment_state["restrictions"]["withholding"] = 0.0
            self._payment_sync_restrictions()

    def _phase_institutional_close(self, tick: _TickScratch) -> None:
        """Bank deposits and credit, government discretionary spending, firm R&D, budget pressure."""
        payment_arm = tick.payment_arm
        per_firm_sales = tick.per_firm_sales
        total_wage_taxes = tick.total_wage_taxes
        total_profit_taxes = tick.total_profit_taxes
        total_price_ceiling_taxes = tick.total_price_ceiling_taxes
        total_property_taxes = tick.total_property_taxes
        total_transfers = tick.total_transfers
        # Phase 11.3: Bank deposit sweep & interest (households → bank)
        if self.bank is not None:
            self.bank.update_deposit_rate()  # Fix 22: adjust rate based on reserve ratio
            self._process_bank_deposits()

        # Phase 11.4: Bank credit scoring update
        if self.bank is not None:
            self._update_credit_scores()
            self.bank.cleanup_settled_loans()

        # Phase 11.5: Government discretionary spending (infrastructure, technology, social, bonds)
        # These investments are "abstract" quality improvements that don't directly go to agents,
        # so we redirect them into the misc firm pool to keep money circulating in the economy.
        infra_spent = self.government.invest_in_infrastructure()
        self.last_tick_gov_infrastructure_spending = infra_spent
        if infra_spent > 0:
            self._collect_misc_revenue(infra_spent)

        tech_spent = self.government.invest_in_technology()
        self.last_tick_gov_technology_spending = tech_spent
        if tech_spent > 0:
            self._collect_misc_revenue(tech_spent)

        social_spent = self.government.invest_in_social_programs()
        self.last_tick_gov_social_spending = social_spent
        if social_spent > 0:
            self._collect_misc_revenue(social_spent)

        # Bond purchases with surplus — redirect to Misc firm
        govt_investments = self.government.make_investments()
        total_bond_purchases = sum(govt_investments.values()) if govt_investments else 0.0

        total_govt_investments = (
            total_bond_purchases
            + infra_spent + tech_spent + social_spent
        )
        self.last_tick_gov_investments = total_govt_investments
        self.last_tick_gov_bond_purchases = total_bond_purchases

        if govt_investments:
            for amount in govt_investments.values():
                self._collect_misc_revenue(amount)
        if payment_arm and self.config.payment_services_project_enabled:
            from payment_government import complete_payment_services_project
            complete_payment_services_project(self)

        # Phase 11.6: Firm R&D spending (tax and redirect to Misc firm)
        total_investment_taxes = 0.0
        for firm in self.firms:
            revenue = per_firm_sales.get(firm.firm_id, {}).get("revenue", 0.0)
            if revenue > 0:
                rd_spending = firm.apply_rd_and_quality_update(revenue)
                # Apply investment tax
                investment_tax = rd_spending * self.government.investment_tax_rate
                after_tax_investment = rd_spending - investment_tax
                total_investment_taxes += investment_tax
                self._collect_misc_revenue(after_tax_investment)

        # Government collects investment taxes
        self.government.cash_balance += total_investment_taxes

        # Phase 11.7: Update budget pressure now that all revenue and spending are known
        # (soft deficit constraint; it runs here rather than at Phase 11.1 so that
        # the Phase 11.5 infrastructure, technology and social spending is included).
        tick_revenue = (
            total_wage_taxes + total_profit_taxes + total_price_ceiling_taxes
            + total_property_taxes + total_investment_taxes
        )
        tick_spending = (
            total_transfers
            + total_govt_investments
            + self.last_tick_gov_subsidies
            + self.last_tick_gov_bailouts
            + self.last_tick_gov_public_works_capitalization
            + self.last_tick_gov_post_warmup_stimulus
        )
        self._update_budget_pressure(tick_revenue, tick_spending)

    def _phase_lifecycle_and_statistics(self, tick: _TickScratch) -> None:
        """Firm exits and entry, legacy policy chooser, statistics and diagnostics."""
        per_firm_sales = tick.per_firm_sales
        firm_production_plans = tick.firm_production_plans
        firm_labor_outcomes = tick.firm_labor_outcomes
        # Phase 12: Handle firm bankruptcies and exits
        tick.bankruptcies_this_tick = self._handle_firm_exits()

        # Phase 13: Potentially create new firms
        self._maybe_create_new_firms()

        # Phase 14: Legacy automatic government policy chooser.
        # When the LLM government is enabled, policy choices must come only
        # from the LLM; deterministic code still executes the chosen levers.
        if self.enable_government_stabilizers and not getattr(CONFIG.llm, "enable_llm_government", False):
            self._adjust_government_policy()

        # Phase 15: Update world-level statistics
        self._update_statistics(per_firm_sales)
        self._update_health_diagnostics()
        self._update_firm_distress_diagnostics(
            firm_production_plans=firm_production_plans,
            firm_labor_outcomes=firm_labor_outcomes,
            bankruptcies_this_tick=tick.bankruptcies_this_tick,
        )
        self._update_sector_shortage_diagnostics()

    def _phase_dividends(self, tick: _TickScratch) -> None:
        """Healthcare bonuses and owner dividends; the payment arm stores next-tick priors and closes fiscally."""
        payment_arm = tick.payment_arm
        total_wage_taxes = tick.total_wage_taxes
        total_profit_taxes = tick.total_profit_taxes
        total_price_ceiling_taxes = tick.total_price_ceiling_taxes
        total_property_taxes = tick.total_property_taxes
        # Phase 16: Distribute firm profits to owners (dividend payments)
        # This recycles wealth from firms back to households
        tick.total_dividends_paid = 0.0
        firms_with_wage_arrears = ({fid for (fid, _), amount in self.payment_state["wage_claims"].items() if amount > MONEY_EPS} if payment_arm else set())
        for firm in self.firms:
            if firm.firm_id in firms_with_wage_arrears:
                continue
            healthcare_bonus = firm.distribute_healthcare_worker_bonus(self.household_lookup)
            tick.total_dividends_paid += healthcare_bonus
            dividends = firm.distribute_profits(self.household_lookup)
            tick.total_dividends_paid += dividends

        if payment_arm:
            self.payment_state["prior_settled_household_net"] = {
                hid: float(row["net"]) for hid, row in self.payment_book.paid_income.items()
            }
            food_names = {firm.good_name for firm in self.firms if firm.good_category == "Food"}
            self.payment_state["prior_essential_food_cost"] = {
                hid: sum(float(cost) for name, cost in costs.items() if name in food_names)
                for hid, costs in self.payment_book.household_purchase_cost.items()
            }
            self.payment_state["prior_settled_firm_operating_cashflow"] = {
                firm.firm_id: (
                    float(self.payment_book.receipts.get(firm.firm_id, {}).get("revenue", 0.0))
                    + float(self.payment_book.rent_receipts.get(firm.firm_id, 0.0))
                    + float(self.payment_state.get("services_pending_receipts", {}).get(firm.firm_id, 0.0))
                    - float(self.payment_book.funded_wages_by_firm.get(firm.firm_id, 0.0))
                    - float(firm.last_tick_operating_cash_cost_nonwage)
                    - float(self.payment_book.funded_ceo.get(firm.firm_id, 0.0))
                ) for firm in self.firms
            }
            self._payment_fiscal_close(
                total_wage_taxes + total_profit_taxes + total_price_ceiling_taxes + total_property_taxes
            )

    def _phase_finalize(self, tick: _TickScratch) -> None:
        """Finalize household ledgers and affordability telemetry; stash the audit record when enabled."""
        firm_production_plans = tick.firm_production_plans
        firm_price_plans = tick.firm_price_plans
        firm_wage_plans = tick.firm_wage_plans
        firm_health_snapshots = tick.firm_health_snapshots
        category_wage_anchor_p75 = tick.category_wage_anchor_p75
        household_labor_plans = tick.household_labor_plans
        household_consumption_plans = tick.household_consumption_plans
        firm_labor_outcomes = tick.firm_labor_outcomes
        household_labor_outcomes = tick.household_labor_outcomes
        per_firm_sales = tick.per_firm_sales
        per_household_purchases = tick.per_household_purchases
        tax_plan = tick.tax_plan
        transfer_plan = tick.transfer_plan
        audit_firm_states_before = tick.audit_firm_states_before
        audit_household_states_before = tick.audit_household_states_before
        audit_government_state_before = tick.audit_government_state_before
        bankruptcies_this_tick = tick.bankruptcies_this_tick
        total_dividends_paid = tick.total_dividends_paid
        unemployment_rate = tick.unemployment_rate
        for household in self.households:
            household.finalize_tick_ledger()
        self._update_affordability_telemetry()

        # ── Audit action log ───────────────────────────────────────────
        # When audit_log_enabled is True, stash all intermediate plans and
        # outcomes so an external audit runner can serialize per-tick actions.
        if self.audit_log_enabled:
            audit_firm_states_after = self._capture_audit_firm_state(self.firms)
            audit_household_states_after = self._capture_audit_household_state()
            audit_government_state_after = self._capture_audit_government_state()
            self._last_tick_audit = {
                "firm_production_plans": firm_production_plans,
                "firm_price_plans": firm_price_plans,
                "firm_wage_plans": firm_wage_plans,
                "firm_health_snapshots": firm_health_snapshots,
                "category_wage_anchor_p75": category_wage_anchor_p75,
                "household_labor_plans": household_labor_plans,
                "household_consumption_plans": household_consumption_plans,
                "firm_labor_outcomes": firm_labor_outcomes,
                "household_labor_outcomes": household_labor_outcomes,
                "per_firm_sales": per_firm_sales,
                "per_household_purchases": per_household_purchases,
                "tax_plan": tax_plan,
                "transfer_plan": transfer_plan,
                "firm_states_before": audit_firm_states_before,
                "firm_states_after": audit_firm_states_after,
                "household_states_before": audit_household_states_before,
                "household_states_after": audit_household_states_after,
                "government_state_before": audit_government_state_before,
                "government_state_after": audit_government_state_after,
                "firm_entries_this_tick": sorted(
                    set(audit_firm_states_after.keys()) - set(audit_firm_states_before.keys())
                ),
                "firm_exits_this_tick": sorted(
                    set(audit_firm_states_before.keys()) - set(audit_firm_states_after.keys())
                ),
                "bankruptcies_this_tick": bankruptcies_this_tick,
                "total_dividends_paid": total_dividends_paid,
                "unemployment_rate": unemployment_rate,
            }

    # -------------------------------------------------------------------------
    # Section: Firm distress, working capital, and shortage diagnostics
    # -------------------------------------------------------------------------
    def _record_firm_distress_transitions(self, firm_state_before: Dict[int, Dict[str, bool]]) -> None:
        """Emit enter/exit events when firms cross into or out of distress modes."""
        for firm in self.firms:
            previous = firm_state_before.get(firm.firm_id, {"burn_mode": False, "survival_mode": False})
            prev_distressed = bool(previous.get("burn_mode")) or bool(previous.get("survival_mode"))
            current_burn = bool(getattr(firm, "burn_mode", False))
            current_survival = bool(getattr(firm, "survival_mode", False))
            current_distressed = current_burn or current_survival

            if current_burn and not bool(previous.get("burn_mode", False)):
                self._append_regime_event(
                    event_type="firm_distress_enter",
                    entity_type="firm",
                    entity_id=firm.firm_id,
                    sector=firm.good_category,
                    reason_code="burn_mode",
                    severity=float(max(getattr(firm, "high_inventory_streak", 0), 1)),
                    metric_value=float(firm.cash_balance),
                )
            if current_survival and not bool(previous.get("survival_mode", False)):
                self._append_regime_event(
                    event_type="firm_distress_enter",
                    entity_type="firm",
                    entity_id=firm.firm_id,
                    sector=firm.good_category,
                    reason_code="survival_mode",
                    severity=1.0,
                    metric_value=float(firm.cash_balance),
                )
            if prev_distressed and not current_distressed:
                exit_reason = "burn_mode" if bool(previous.get("burn_mode", False)) else "survival_mode"
                self._append_regime_event(
                    event_type="firm_distress_exit",
                    entity_type="firm",
                    entity_id=firm.firm_id,
                    sector=firm.good_category,
                    reason_code=exit_reason,
                    severity=0.0,
                    metric_value=float(firm.cash_balance),
                )

    def _record_failed_hiring_events(
        self,
        firm_production_plans: Dict[int, Dict],
        firm_labor_outcomes: Dict[int, Dict[str, object]],
    ) -> None:
        """Emit failed-hiring events when firms leave vacancies unfilled."""
        for firm_id, production_plan in firm_production_plans.items():
            planned_hires = int(production_plan.get("planned_hires_count", 0) or 0)
            if planned_hires <= 0:
                continue

            outcome = firm_labor_outcomes.get(firm_id, {}) or {}
            actual_hires = len(outcome.get("hired_households_ids", []) or [])
            unfilled_roles = int(
                outcome.get("unfilled_vacancies", max(0, planned_hires - actual_hires)) or 0
            )
            if unfilled_roles <= 0:
                continue

            firm = self.firm_lookup.get(firm_id)
            reason = str(outcome.get("failed_match_reason", "unfilled_vacancies") or "unfilled_vacancies")
            self._append_regime_event(
                event_type="failed_hiring",
                entity_type="firm",
                entity_id=firm_id,
                sector=getattr(firm, "good_category", None),
                reason_code=reason,
                severity=float(unfilled_roles),
                metric_value=float(unfilled_roles),
                payload={
                    "planned_hires": planned_hires,
                    "actual_hires": actual_hires,
                    "unfilled_vacancies": int(outcome.get("unfilled_vacancies", unfilled_roles) or unfilled_roles),
                    "reservation_reject_count": int(outcome.get("reservation_reject_count", 0) or 0),
                    "median_rejected_reservation_wage": float(
                        outcome.get("median_rejected_reservation_wage", 0.0) or 0.0
                    ),
                    "synthetic_switcher_vacancies": int(outcome.get("synthetic_switcher_vacancies", 0) or 0),
                },
            )

    def _working_capital_budget_for_tick(self, unemployment_rate: float) -> float:
        """Diagnostics budget envelope for later working-capital bridge credit."""
        cfg = CONFIG.firms
        raw_budget = (
            float(cfg.working_capital_base_budget_per_tick)
            + float(unemployment_rate) * float(cfg.working_capital_budget_per_unemployment_rate)
        )
        return min(
            float(cfg.working_capital_max_budget_per_tick),
            max(0.0, raw_budget),
        )

    def _working_capital_candidate_diagnostics(
        self,
        firm: FirmAgent,
        health_snapshot,
        unemployment_rate: float,
    ) -> Dict[str, object]:
        """Return diagnostics-only bridge-credit candidacy for a private firm."""
        cfg = CONFIG.firms
        result: Dict[str, object] = {
            "candidate": False,
            "denial_reason": "",
            "expected_gap": 0.0,
            "lost_sales": 0.0,
            "sell_through": float(health_snapshot.sell_through_rate),
            "inventory_weeks": float(health_snapshot.inventory_weeks),
            "cash_runway": float(health_snapshot.cash_runway_ticks),
            "profit_margin": float(health_snapshot.smoothed_profit_margin),
            "marginal_revenue": 0.0,
            "marginal_cost": 0.0,
            "marginal_margin": 0.0,
        }

        category = (firm.good_category or "").lower()
        if firm.is_baseline:
            result["denial_reason"] = "baseline_firm"
            return result
        if category in {"housing", "healthcare", "publicworks"}:
            result["denial_reason"] = f"excluded_category_{category}"
            return result
        if unemployment_rate < float(cfg.working_capital_unemployment_trigger):
            result["denial_reason"] = "unemployment_below_trigger"
            return result
        if getattr(firm, "received_bailout_this_tick", False):
            result["denial_reason"] = "already_received_bailout_this_tick"
            return result

        current_capacity = firm._capacity_for_workers(max(1, len(firm.employees)))
        expected_gap = max(0.0, float(firm.expected_sales_units) - current_capacity)
        lost_sales = max(0.0, float(getattr(firm, "last_tick_lost_sales_used_units", 0.0) or 0.0))
        result["expected_gap"] = expected_gap
        result["lost_sales"] = lost_sales

        demand_signal = (
            lost_sales >= float(cfg.working_capital_min_lost_sales_units)
            or expected_gap >= float(cfg.working_capital_min_expected_gap_units)
            or float(health_snapshot.sell_through_rate) >= float(cfg.working_capital_min_sell_through)
        )
        if not demand_signal:
            result["denial_reason"] = "no_validated_demand"
            return result
        if float(health_snapshot.inventory_weeks) > float(cfg.working_capital_max_inventory_weeks):
            result["denial_reason"] = "inventory_too_high"
            return result
        if float(health_snapshot.smoothed_profit_margin) < float(cfg.working_capital_min_profit_margin):
            result["denial_reason"] = "profit_margin_too_low"
            return result

        revenue, cost, margin = firm._marginal_worker_economics()
        result["marginal_revenue"] = revenue
        result["marginal_cost"] = cost
        result["marginal_margin"] = margin

        required_margin = cost * float(cfg.working_capital_min_mrpl_margin)
        if margin < required_margin:
            result["denial_reason"] = "mrpl_margin_too_low"
            return result

        result["candidate"] = True
        result["denial_reason"] = ""
        return result

    def _record_working_capital_candidate_diagnostics(
        self,
        firm: FirmAgent,
        health_snapshot,
        unemployment_rate: float,
    ) -> Dict[str, object]:
        """Store diagnostics-only working-capital candidacy on the firm."""
        diag = self._working_capital_candidate_diagnostics(firm, health_snapshot, unemployment_rate)
        firm.last_working_capital_candidate = bool(diag["candidate"])
        firm.last_working_capital_denial_reason = str(diag["denial_reason"])
        if firm.last_working_capital_candidate:
            self.last_tick_working_capital_candidates += 1
        for key, value in diag.items():
            firm.decision_diagnostics[f"working_capital_{key}"] = value
        return diag

    def _working_capital_priority(
        self,
        firm: FirmAgent,
        health_snapshot,
    ) -> tuple:
        """Lower tuple sorts first for working-capital triage."""
        cash_runway = float(health_snapshot.cash_runway_ticks)
        sell_through = float(health_snapshot.sell_through_rate)
        lost_sales = float(getattr(firm, "last_tick_lost_sales_used_units", 0.0) or 0.0)
        marginal_margin = float(getattr(firm, "last_marginal_worker_margin", 0.0) or 0.0)
        return (
            cash_runway,
            -sell_through,
            -lost_sales,
            -marginal_margin,
            firm.firm_id,
        )

    def _compute_working_capital_amount_and_affordability(
        self,
        firm: FirmAgent,
        health_snapshot,
    ) -> tuple[float, int, float, float]:
        """Return loan amount, supported workers, payment, and net gain."""
        cfg = CONFIG.firms
        current_workers = len(firm.employees)
        target_workers = max(
            current_workers,
            firm._workers_for_sales(float(firm.expected_sales_units)),
        )
        desired_hires = max(0, target_workers - current_workers)
        firm.last_viable_expansion_workers = int(desired_hires)
        if desired_hires <= 0:
            firm.last_working_capital_denial_reason = "no_worker_gap"
            firm.decision_diagnostics["working_capital_denial_reason"] = "no_worker_gap"
            return 0.0, 0, 0.0, 0.0

        hire_budget_workers = min(
            desired_hires,
            int(cfg.working_capital_hire_abs_cap),
            max(
                1,
                int(math.ceil(max(1, current_workers) * float(cfg.working_capital_hire_fraction))),
            ),
        )

        expected_wage_cost = firm._effective_base_wage_cost()
        current_wage_bill = firm._current_wage_bill()
        new_incremental_payroll = expected_wage_cost * hire_budget_workers
        target_cash = (
            current_wage_bill + new_incremental_payroll
        ) * float(cfg.working_capital_support_ticks)
        cash_gap = max(0.0, target_cash - max(0.0, firm.cash_balance))

        amount = min(
            float(cfg.working_capital_max_loan_per_firm),
            max(new_incremental_payroll * 2.0, cash_gap),
        )
        if amount <= 0.0:
            firm.last_working_capital_denial_reason = "no_cash_gap"
            firm.decision_diagnostics["working_capital_denial_reason"] = "no_cash_gap"
            return 0.0, 0, 0.0, 0.0

        conservative_rate = float(cfg.working_capital_govt_rate) + float(cfg.working_capital_spread)
        estimated_payment = firm._estimate_working_capital_payment(
            amount=amount,
            annual_rate=conservative_rate,
            term_ticks=int(cfg.working_capital_term_ticks),
        )
        _, _, marginal_margin = firm._marginal_worker_economics(current_workers)
        gross_gain = hire_budget_workers * marginal_margin
        estimated_net_gain = gross_gain - estimated_payment

        firm.last_working_capital_estimated_payment = estimated_payment
        firm.last_working_capital_estimated_net_gain = estimated_net_gain
        firm.decision_diagnostics["working_capital_estimated_payment"] = float(estimated_payment)
        firm.decision_diagnostics["working_capital_estimated_net_gain"] = float(estimated_net_gain)

        required_payment_coverage = estimated_payment * float(cfg.working_capital_debt_service_coverage)
        if gross_gain < required_payment_coverage:
            firm.last_working_capital_denial_reason = "debt_service_not_covered"
            firm.decision_diagnostics["working_capital_denial_reason"] = "debt_service_not_covered"
            return 0.0, 0, estimated_payment, estimated_net_gain
        if estimated_net_gain < float(cfg.working_capital_min_net_gain_per_tick):
            firm.last_working_capital_denial_reason = "net_gain_too_low_after_debt"
            firm.decision_diagnostics["working_capital_denial_reason"] = "net_gain_too_low_after_debt"
            return 0.0, 0, estimated_payment, estimated_net_gain

        return amount, hire_budget_workers, estimated_payment, estimated_net_gain

    def _working_capital_has_funding_capacity(self, amount: float) -> bool:
        """Return whether existing bank or government cash can fund bridge credit."""
        amount = max(0.0, float(amount))
        bank = self.bank
        if bank is not None and bank.can_lend() and bank.lendable_cash >= amount:
            return True
        reserve_floor = float(CONFIG.government.working_capital_backstop_reserve_floor)
        return self._payment_free_treasury_cash() >= amount + reserve_floor

    def _issue_working_capital_bridges(
        self,
        firm_health_snapshots: Dict[int, object],
        unemployment_rate: float,
    ) -> None:
        """Issue debt-service-safe bridge credit to viable cash-constrained firms."""
        cfg = CONFIG.firms
        if not bool(cfg.working_capital_enabled):
            return
        if not bool(CONFIG.government.auto_working_capital_backstop):
            return
        if unemployment_rate < float(cfg.working_capital_unemployment_trigger):
            return

        budget_remaining = self._working_capital_budget_for_tick(unemployment_rate)
        self.last_tick_working_capital_budget = budget_remaining
        self.last_tick_working_capital_issued = 0.0
        self.last_tick_working_capital_denied_budget = 0.0
        self.last_tick_working_capital_candidates = 0

        candidates: List[tuple[FirmAgent, object]] = []
        for firm in self.firms:
            snapshot = firm_health_snapshots.get(firm.firm_id)
            if snapshot is None:
                continue
            diag = self._record_working_capital_candidate_diagnostics(firm, snapshot, unemployment_rate)
            if bool(diag["candidate"]):
                candidates.append((firm, snapshot))

        candidates.sort(key=lambda pair: self._working_capital_priority(pair[0], pair[1]))

        for firm, snapshot in candidates:
            if budget_remaining <= 0.0:
                firm.last_working_capital_denial_reason = "tick_budget_exhausted"
                firm.decision_diagnostics["working_capital_denial_reason"] = "tick_budget_exhausted"
                self.last_tick_working_capital_denied_budget += 1.0
                continue

            amount, hire_budget_workers, estimated_payment, estimated_net_gain = (
                self._compute_working_capital_amount_and_affordability(firm, snapshot)
            )
            if amount <= 0.0:
                continue

            amount = min(float(amount), float(budget_remaining))
            if not self._working_capital_has_funding_capacity(amount):
                firm.last_working_capital_denial_reason = "no_bank_or_gov_funding_capacity"
                firm.decision_diagnostics["working_capital_denial_reason"] = "no_bank_or_gov_funding_capacity"
                continue

            cash_before = float(firm.cash_balance)
            issued = self._issue_firm_loan(
                firm,
                amount=amount,
                term_ticks=int(cfg.working_capital_term_ticks),
                govt_rate=float(cfg.working_capital_govt_rate),
                spread=float(cfg.working_capital_spread),
                purpose="working_capital",
            )
            actual_issued = max(0.0, float(firm.cash_balance) - cash_before)
            if not issued or actual_issued <= 0.0:
                firm.last_working_capital_denial_reason = "no_bank_or_gov_funding_capacity"
                firm.decision_diagnostics["working_capital_denial_reason"] = "no_bank_or_gov_funding_capacity"
                continue

            budget_remaining = max(0.0, budget_remaining - actual_issued)
            self.last_tick_working_capital_issued += actual_issued
            firm.working_capital_support_ticks = int(cfg.working_capital_support_ticks)
            firm.working_capital_loan_received_last_tick = float(actual_issued)
            firm.working_capital_total_received += float(actual_issued)
            firm.working_capital_hire_budget_workers = int(hire_budget_workers)
            firm.received_working_capital_this_tick = True
            firm.last_working_capital_need = float(actual_issued)
            firm.last_working_capital_estimated_payment = float(estimated_payment)
            firm.last_working_capital_estimated_net_gain = float(estimated_net_gain)
            firm.last_working_capital_denial_reason = ""
            firm.decision_diagnostics["working_capital_issued"] = float(actual_issued)
            firm.decision_diagnostics["working_capital_hire_budget_workers"] = int(hire_budget_workers)
            firm.decision_diagnostics["working_capital_estimated_payment"] = float(estimated_payment)
            firm.decision_diagnostics["working_capital_estimated_net_gain"] = float(estimated_net_gain)
            firm.decision_diagnostics["working_capital_denial_reason"] = ""

    @staticmethod
    def _clamp_pressure(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        """Bound a diagnostic pressure metric to a stable range."""
        return float(max(lower, min(upper, value)))

    def _update_health_diagnostics(self) -> None:
        """Store compact healthcare-side diagnostics for the current tick."""
        healthcare_queue_depth = int(
            sum(
                len(getattr(firm, "healthcare_queue", []))
                for firm in self.firms
                if (firm.good_category or "").lower() == "healthcare"
            )
        )
        self.last_health_diagnostics = {
            "healthcare_queue_depth": float(healthcare_queue_depth),
            "healthcare_completed_count": float(self.healthcare_completed_visits_this_tick),
            "healthcare_denied_count": float(self.healthcare_affordability_rejects_this_tick),
        }

    def _update_firm_distress_diagnostics(
        self,
        firm_production_plans: Dict[int, Dict],
        firm_labor_outcomes: Dict[int, Dict[str, object]],
        bankruptcies_this_tick: int,
    ) -> None:
        """Store compact firm-distress diagnostics for the current tick."""
        burn_mode_firm_count = 0
        survival_mode_firm_count = 0
        zero_cash_firm_count = 0
        weak_demand_firm_count = 0
        inventory_pressure_firm_count = 0
        failed_hiring_firm_count = 0
        failed_hiring_roles_count = 0
        distressed_firm_count = 0
        distressed_sector_counts = {
            "food": 0.0,
            "housing": 0.0,
            "services": 0.0,
            "healthcare": 0.0,
        }

        for firm in self.firms:
            current_burn = bool(getattr(firm, "burn_mode", False))
            current_survival = bool(getattr(firm, "survival_mode", False))
            if current_burn:
                burn_mode_firm_count += 1
            if current_survival:
                survival_mode_firm_count += 1
            if float(getattr(firm, "cash_balance", 0.0)) <= 0.0:
                zero_cash_firm_count += 1
            if float(self.last_tick_sell_through_rate.get(firm.firm_id, 0.5)) < 0.5:
                weak_demand_firm_count += 1
            if int(getattr(firm, "high_inventory_streak", 0)) > 0:
                inventory_pressure_firm_count += 1
            if current_burn or current_survival or float(getattr(firm, "cash_balance", 0.0)) <= 0.0:
                distressed_firm_count += 1
                category = (firm.good_category or "").lower()
                if category in distressed_sector_counts:
                    distressed_sector_counts[category] += 1.0

            planned_hires = int(firm_production_plans.get(firm.firm_id, {}).get("planned_hires_count", 0) or 0)
            actual_hires = len((firm_labor_outcomes.get(firm.firm_id, {}) or {}).get("hired_households_ids", []) or [])
            unfilled_roles = max(0, planned_hires - actual_hires)
            if unfilled_roles > 0:
                failed_hiring_firm_count += 1
                failed_hiring_roles_count += unfilled_roles

        self.last_firm_distress_diagnostics = {
            "burn_mode_firm_count": float(burn_mode_firm_count),
            "survival_mode_firm_count": float(survival_mode_firm_count),
            "zero_cash_firm_count": float(zero_cash_firm_count),
            "weak_demand_firm_count": float(weak_demand_firm_count),
            "inventory_pressure_firm_count": float(inventory_pressure_firm_count),
            "failed_hiring_firm_count": float(failed_hiring_firm_count),
            "failed_hiring_roles_count": float(failed_hiring_roles_count),
            "distressed_firm_count": float(distressed_firm_count),
            "distressed_food_firms": distressed_sector_counts["food"],
            "distressed_housing_firms": distressed_sector_counts["housing"],
            "distressed_services_firms": distressed_sector_counts["services"],
            "distressed_healthcare_firms": distressed_sector_counts["healthcare"],
            "bankruptcy_count": float(bankruptcies_this_tick),
        }

    def _update_sector_shortage_diagnostics(self) -> None:
        """Store compact per-sector shortage diagnostics and emit regime transitions."""
        sector_names = ["Food", "Housing", "Services", "Healthcare"]
        rows: List[Dict[str, object]] = []
        total_households = max(1, len(self.households))
        homeless_households = int(self.last_housing_diagnostics.get("homeless_household_count", 0.0))
        housing_shortage_flag = bool(self.last_housing_diagnostics.get("housing_shortage_flag", 0.0))
        healthcare_denied = float(self.last_health_diagnostics.get("healthcare_denied_count", 0.0))

        for sector in sector_names:
            sector_firms = [firm for firm in self.firms if (firm.good_category or "").lower() == sector.lower()]
            sell_through_values = [float(self.last_tick_sell_through_rate.get(firm.firm_id, 0.0)) for firm in sector_firms]
            mean_sell_through = float(sum(sell_through_values) / len(sell_through_values)) if sell_through_values else 0.0
            total_employees = sum(len(firm.employees) for firm in sector_firms)
            total_vacancies = sum(max(0, int(getattr(firm, "planned_hires_count", 0))) for firm in sector_firms)
            total_inventory = float(sum(max(0.0, float(getattr(firm, "inventory_units", 0.0))) for firm in sector_firms))
            total_units_sold = float(sum(max(0.0, self.last_tick_sales_units.get(firm.firm_id, 0.0)) for firm in sector_firms))
            mean_price = float(sum(float(firm.price) for firm in sector_firms) / len(sector_firms)) if sector_firms else 0.0
            baseline_price = max(1.0, float(CONFIG.baseline_prices.get(sector, mean_price or 1.0)))

            vacancy_pressure = self._clamp_pressure(total_vacancies / max(total_employees, 1))
            inventory_coverage = total_inventory / max(total_units_sold, 1.0)
            inventory_pressure = self._clamp_pressure(1.0 - min(inventory_coverage, 1.0))
            price_pressure = self._clamp_pressure(max(0.0, mean_price / baseline_price - 1.0))
            queue_pressure = 0.0
            occupancy_pressure = 0.0

            if sector.lower() == "healthcare":
                total_queue = float(sum(len(getattr(firm, "healthcare_queue", [])) for firm in sector_firms))
                total_staff = float(sum(max(0, len(firm.employees)) for firm in sector_firms))
                queue_pressure = self._clamp_pressure(total_queue / max(total_staff, 1.0))
                shortage_active = queue_pressure >= 0.75 or healthcare_denied > 0.0
                primary_driver = "affordability" if healthcare_denied > 0.0 and healthcare_denied >= total_queue else "queue"
                shortage_severity = self._clamp_pressure(queue_pressure * 0.7 + self._clamp_pressure(healthcare_denied / max(total_households, 1)) * 0.3) * 100.0
            elif sector.lower() == "housing":
                total_units = float(sum(max(0, int(getattr(firm, "max_rental_units", 0))) for firm in sector_firms))
                total_tenants = float(sum(len(getattr(firm, "current_tenants", [])) for firm in sector_firms))
                occupancy_pressure = self._clamp_pressure(total_tenants / max(total_units, 1.0))
                shortage_active = housing_shortage_flag or homeless_households > 0
                no_supply = float(self.last_housing_diagnostics.get("housing_no_supply_count", 0.0))
                unaffordable = float(self.last_housing_diagnostics.get("housing_unaffordable_count", 0.0))
                primary_driver = "no_supply" if no_supply >= unaffordable else "unaffordable"
                shortage_severity = self._clamp_pressure(
                    occupancy_pressure * 0.5
                    + self._clamp_pressure(homeless_households / max(total_households, 1)) * 0.5
                ) * 100.0
            else:
                shortage_active = mean_sell_through >= 0.85 and (inventory_pressure >= 0.35 or vacancy_pressure >= 0.1)
                driver_components = {
                    "inventory": inventory_pressure,
                    "vacancy": vacancy_pressure,
                    "price": price_pressure,
                }
                primary_driver = max(driver_components, key=driver_components.get) if shortage_active else "stable"
                shortage_severity = self._clamp_pressure(
                    mean_sell_through * 0.4 + inventory_pressure * 0.35 + vacancy_pressure * 0.25
                ) * 100.0

            rows.append({
                "sector": sector,
                "shortage_active": bool(shortage_active),
                "shortage_severity": float(shortage_severity),
                "primary_driver": str(primary_driver),
                "mean_sell_through_rate": float(mean_sell_through),
                "vacancy_pressure": float(vacancy_pressure),
                "inventory_pressure": float(inventory_pressure),
                "price_pressure": float(price_pressure),
                "queue_pressure": float(queue_pressure),
                "occupancy_pressure": float(occupancy_pressure),
            })

            previous_active = bool(self._sector_shortage_state.get(sector, False))
            if shortage_active and not previous_active:
                self._append_regime_event(
                    event_type="shortage_regime_enter",
                    entity_type="sector",
                    sector=sector,
                    reason_code=str(primary_driver),
                    severity=float(shortage_severity),
                    metric_value=float(shortage_severity),
                )
            elif previous_active and not shortage_active:
                self._append_regime_event(
                    event_type="shortage_regime_exit",
                    entity_type="sector",
                    sector=sector,
                    reason_code=str(primary_driver),
                    severity=0.0,
                    metric_value=0.0,
                )
            self._sector_shortage_state[sector] = bool(shortage_active)

        self.last_sector_shortage_diagnostics = rows

    # -------------------------------------------------------------------------
    # Section: Labor market matching and roster synchronization
    # -------------------------------------------------------------------------
    def _normalize_household_labor_plans(
        self,
        household_labor_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
        market_anchor_wage: float = 0.0,
    ) -> None:
        """
        De-risk labor plans before matching.

        - Ensure unemployed households that can work are marked as job seekers.
        - Optionally clamp long-term unemployed reservation wages to observable market offers.
        """
        forced_search = 0
        reservation_clamps = 0

        minimum_wage = float(self.government.get_minimum_wage())
        benefit_floor = (
            float(self.government.get_unemployment_benefit_level())
            * float(CONFIG.households.min_job_premium_over_unemployment)
        )
        if market_anchor_wage > 0.0:
            reservation_cap = max(
                minimum_wage,
                benefit_floor,
                float(market_anchor_wage) * 1.05,
            )
        else:
            max_wage_offer = max(
                (float(plan.get("wage_offer_next", 0.0)) for plan in firm_wage_plans.values()),
                default=0.0,
            )
            reservation_cap = max(max_wage_offer, minimum_wage, benefit_floor)

        for household in self.households:
            household_id = household.household_id
            plan = household_labor_plans.get(household_id)
            if plan is None:
                continue

            if not household.can_work:
                plan["searching_for_job"] = False
                continue

            if self.force_unemployed_search and (not household.is_employed):
                if not bool(plan.get("searching_for_job", False)):
                    plan["searching_for_job"] = True
                    forced_search += 1

            if (
                self.clamp_unemployed_reservation
                and (not household.is_employed)
                and household.unemployment_duration >= self.unemployed_reservation_clamp_ticks
                and reservation_cap > 0.0
            ):
                reservation_wage = float(plan.get("reservation_wage", household.reservation_wage))
                if reservation_wage > reservation_cap:
                    plan["reservation_wage"] = reservation_cap
                    reservation_clamps += 1

        self.last_labor_plan_adjustments = {
            "labor_forced_search_adjustments": float(forced_search),
            "labor_reservation_clamp_adjustments": float(reservation_clamps),
        }

    def _run_labor_matching(
        self,
        firm_production_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
        household_labor_plans: Dict[int, Dict]
    ) -> Tuple[Dict[int, Dict], Dict[int, Dict]]:
        """
        Dispatch labor matching strategy with optional A/B verification.

        - `legacy`: deterministic firm_id order, per-firm candidate scan.
        - `fast`: indexed one-pass labor snapshot (default path for scale).
        - Optional compare mode runs both and logs diffs for de-risking.
        """
        if self.current_tick % self.labor_diagnostics_stride == 0:
            self.last_labor_diagnostics = self._compute_labor_diagnostics(
                household_labor_plans,
                firm_wage_plans,
            )
            if self.last_labor_plan_adjustments:
                self.last_labor_diagnostics.update(self.last_labor_plan_adjustments)
            if self.log_labor_diagnostics:
                logger.info(
                    "Labor diagnostics tick=%s mode=%s unemployed=%s seekers=%s not_searching_unemployed=%s cannot_work=%s wage_ineligible_seekers=%s forced_search_adjustments=%s reservation_clamp_adjustments=%s",
                    self.current_tick,
                    self.labor_match_mode,
                    self.last_labor_diagnostics.get("labor_unemployed_total", 0),
                    self.last_labor_diagnostics.get("labor_seekers_total", 0),
                    self.last_labor_diagnostics.get("labor_unemployed_not_searching", 0),
                    self.last_labor_diagnostics.get("labor_cannot_work", 0),
                    self.last_labor_diagnostics.get("labor_seekers_wage_ineligible", 0),
                    self.last_labor_diagnostics.get("labor_forced_search_adjustments", 0),
                    self.last_labor_diagnostics.get("labor_reservation_clamp_adjustments", 0),
                )

        if self.labor_match_mode == "legacy":
            return self._match_labor(
                firm_production_plans,
                firm_wage_plans,
                household_labor_plans,
            )

        fast_outcomes = self._match_labor_fast(
            firm_production_plans,
            firm_wage_plans,
            household_labor_plans,
        )

        if self.compare_labor_match and (self.current_tick % self.compare_labor_match_stride == 0):
            legacy_outcomes = self._match_labor(
                firm_production_plans,
                firm_wage_plans,
                household_labor_plans,
            )
            self._compare_labor_match_outcomes(fast_outcomes, legacy_outcomes)

        return fast_outcomes

    def _record_labor_events(
        self,
        firm_labor_outcomes: Dict[int, Dict[str, object]],
        firm_wage_plans: Dict[int, Dict[str, float]],
        household_labor_plans: Dict[int, Dict[str, object]],
    ) -> None:
        """Capture exact hire and layoff events before outcomes mutate agents."""
        events: List[Dict[str, object]] = []
        event_tick = int(self.current_tick + 1)

        for firm_id, outcome in firm_labor_outcomes.items():
            firm = self.firm_lookup.get(firm_id)
            if firm is None:
                continue

            wage_offer = float(
                firm_wage_plans.get(firm_id, {}).get(
                    "wage_offer_next",
                    getattr(firm, "wage_offer", 0.0),
                )
            )
            actual_wages = outcome.get("actual_wages", {}) or {}

            for household_id in outcome.get("hired_households_ids", []):
                household = self.household_lookup.get(household_id)
                labor_plan = household_labor_plans.get(household_id, {})
                events.append({
                    "tick": event_tick,
                    "household_id": int(household_id),
                    "firm_id": int(firm_id),
                    "event_type": "hire",
                    "actual_wage": float(actual_wages.get(household_id, wage_offer)),
                    "wage_offer": wage_offer,
                    "reservation_wage": float(
                        labor_plan.get(
                            "reservation_wage",
                            getattr(household, "reservation_wage", 0.0),
                        )
                    ),
                    "skill_level": float(getattr(household, "skills_level", 0.0)),
                })

            for household_id in outcome.get("confirmed_layoffs_ids", []):
                household = self.household_lookup.get(household_id)
                labor_plan = household_labor_plans.get(household_id, {})
                events.append({
                    "tick": event_tick,
                    "household_id": int(household_id),
                    "firm_id": int(firm_id),
                    "event_type": "layoff",
                    "actual_wage": float(
                        firm.actual_wages.get(
                            household_id,
                            getattr(household, "wage", 0.0),
                        )
                    ),
                    "wage_offer": float(getattr(firm, "wage_offer", 0.0)),
                    "reservation_wage": float(
                        labor_plan.get(
                            "reservation_wage",
                            getattr(household, "reservation_wage", 0.0),
                        )
                    ),
                    "skill_level": float(getattr(household, "skills_level", 0.0)),
                })

        self.last_labor_events = events

    def _compute_labor_diagnostics(
        self,
        household_labor_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
    ) -> Dict[str, float]:
        """
        Lightweight diagnostics to explain unemployment/search behavior.
        """
        max_wage_offer = max(
            (float(plan.get("wage_offer_next", 0.0)) for plan in firm_wage_plans.values()),
            default=0.0,
        )

        unemployed_total = 0
        seekers_total = 0
        cannot_work = 0
        unemployed_not_searching = 0
        wage_ineligible_seekers = 0
        medical_only_seekers = 0

        for household in self.households:
            plan = household_labor_plans.get(household.household_id, {})
            searching = bool(plan.get("searching_for_job", False))
            reservation = float(plan.get("reservation_wage", household.reservation_wage))
            medical_only = bool(plan.get("medical_only", False))

            if not household.is_employed:
                unemployed_total += 1
            if not household.can_work:
                cannot_work += 1
            if searching:
                seekers_total += 1
                if medical_only:
                    medical_only_seekers += 1
                if reservation > max_wage_offer + 1e-9:
                    wage_ineligible_seekers += 1
            elif (not household.is_employed) and household.can_work:
                unemployed_not_searching += 1

        return {
            "labor_unemployed_total": float(unemployed_total),
            "labor_seekers_total": float(seekers_total),
            "labor_cannot_work": float(cannot_work),
            "labor_unemployed_not_searching": float(unemployed_not_searching),
            "labor_seekers_wage_ineligible": float(wage_ineligible_seekers),
            "labor_seekers_medical_only": float(medical_only_seekers),
            "labor_max_wage_offer": float(max_wage_offer),
        }

    def _compare_labor_match_outcomes(
        self,
        fast_outcomes: Tuple[Dict[int, Dict], Dict[int, Dict]],
        legacy_outcomes: Tuple[Dict[int, Dict], Dict[int, Dict]],
    ) -> None:
        """
        Compare fast vs legacy matching and log mismatches for de-risking.
        """
        fast_firm, fast_household = fast_outcomes
        legacy_firm, legacy_household = legacy_outcomes
        mismatch_samples: List[str] = []

        for firm_id in sorted(set(fast_firm.keys()) | set(legacy_firm.keys())):
            f_out = fast_firm.get(firm_id)
            l_out = legacy_firm.get(firm_id)
            if f_out is None or l_out is None:
                mismatch_samples.append(f"firm={firm_id}:missing_outcome")
            else:
                if f_out.get("hired_households_ids", []) != l_out.get("hired_households_ids", []):
                    mismatch_samples.append(
                        f"firm={firm_id}:hired_fast={f_out.get('hired_households_ids', [])[:5]} "
                        f"legacy={l_out.get('hired_households_ids', [])[:5]}"
                    )
                elif f_out.get("confirmed_layoffs_ids", []) != l_out.get("confirmed_layoffs_ids", []):
                    mismatch_samples.append(f"firm={firm_id}:layoff_mismatch")
            if len(mismatch_samples) >= 5:
                break

        if len(mismatch_samples) < 5:
            for household_id in sorted(set(fast_household.keys()) | set(legacy_household.keys())):
                f_out = fast_household.get(household_id)
                l_out = legacy_household.get(household_id)
                if f_out is None or l_out is None:
                    mismatch_samples.append(f"household={household_id}:missing_outcome")
                else:
                    wage_equal = abs(float(f_out.get("wage", 0.0)) - float(l_out.get("wage", 0.0))) <= 1e-9
                    if (
                        f_out.get("employer_id") != l_out.get("employer_id")
                        or f_out.get("employer_category") != l_out.get("employer_category")
                        or not wage_equal
                    ):
                        mismatch_samples.append(
                            f"household={household_id}:fast=({f_out.get('employer_id')},{f_out.get('wage', 0.0):.2f}) "
                            f"legacy=({l_out.get('employer_id')},{l_out.get('wage', 0.0):.2f})"
                        )
                if len(mismatch_samples) >= 5:
                    break

        if mismatch_samples:
            self._labor_compare_mismatch_count += 1
            logger.warning(
                "Labor matcher mismatch tick=%s count=%s samples=%s",
                self.current_tick,
                self._labor_compare_mismatch_count,
                "; ".join(mismatch_samples),
            )

    def _match_labor(
        self,
        firm_production_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
        household_labor_plans: Dict[int, Dict]
    ) -> Tuple[Dict[int, Dict], Dict[int, Dict]]:
        """
        Match firms and households in the labor market deterministically.

        Args:
            firm_production_plans: Production plans with hiring needs
            firm_wage_plans: Wage offers from firms
            household_labor_plans: Labor supply from households

        Returns:
            Tuple of (firm_labor_outcomes, household_labor_outcomes)
        """
        firm_labor_outcomes = {}
        household_labor_outcomes = {}
        assigned_households = set()

        # Track current employers to keep existing matches unless layoffs occur
        # Use cached firm_lookup instead of rebuilding
        planned_layoffs_set = set()
        for plan in firm_production_plans.values():
            planned_layoffs_set.update(plan.get("planned_layoffs_ids", []))

        for household in self.households:
            # Check if household is too sick to work (health < 40%)
            if not household.can_work:
                # Force unemployment due to health
                household_labor_outcomes[household.household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }
                continue

            if household.is_employed and household.household_id not in planned_layoffs_set:
                employer_id = household.employer_id
                employer_category = None
                if employer_id is not None and employer_id in self.firm_lookup:
                    employer_category = self.firm_lookup[employer_id].good_category
                household_labor_outcomes[household.household_id] = {
                    "employer_id": employer_id,
                    "wage": household.wage,
                    "employer_category": employer_category
                }
                assigned_households.add(household.household_id)
            else:
                household_labor_outcomes[household.household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }

        # Ensure all households present (even if not explicitly listed above)
        for household_id in household_labor_plans.keys():
            if household_id not in household_labor_outcomes:
                household_labor_outcomes[household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }

        # Sort firms by firm_id for deterministic ordering
        sorted_firms = sorted(self.firms, key=lambda f: f.firm_id)

        for firm in sorted_firms:
            firm_id = firm.firm_id
            production_plan = firm_production_plans[firm_id]
            wage_plan = firm_wage_plans[firm_id]
            is_healthcare_firm = (firm.good_category or "").lower() == "healthcare"

            vacancies = production_plan["planned_hires_count"]
            wage_offer = wage_plan["wage_offer_next"]
            confirmed_layoffs = production_plan["planned_layoffs_ids"]

            # Initialize firm outcome
            firm_labor_outcomes[firm_id] = {
                "hired_households_ids": [],
                "confirmed_layoffs_ids": confirmed_layoffs,
                "actual_wages": {},
                "unfilled_vacancies": 0,
                "failed_match_reason": "",
                "reservation_reject_count": 0,
                "median_rejected_reservation_wage": 0.0,
                "synthetic_switcher_vacancies": 0,
            }

            # Healthcare staffing is managed outside labor-market matching.
            if is_healthcare_firm:
                continue

            if vacancies <= 0:
                continue

            # Find eligible candidates (vectorized filtering)
            # Build arrays for unassigned job seekers
            unassigned_ids = []
            unassigned_skills = []
            unassigned_reservation = []

            for household_id, labor_plan in household_labor_plans.items():
                if household_id not in assigned_households and labor_plan["searching_for_job"]:
                    medical_only = bool(labor_plan.get("medical_only", False))
                    if medical_only and not is_healthcare_firm:
                        continue
                    # Check if household is healthy enough to work
                    household = self.household_lookup.get(household_id)
                    if household and household.can_work:
                        unassigned_ids.append(household_id)
                        unassigned_skills.append(labor_plan["skills_level"])
                        unassigned_reservation.append(labor_plan["reservation_wage"])

            if not unassigned_ids:
                continue

            # Vectorized eligibility check
            unassigned_ids_arr = np.array(unassigned_ids, dtype=np.int32)
            unassigned_skills_arr = np.array(unassigned_skills, dtype=np.float32)
            unassigned_reservation_arr = np.array(unassigned_reservation, dtype=np.float32)

            # Filter by wage offer
            eligible_mask = wage_offer >= unassigned_reservation_arr
            eligible_ids = unassigned_ids_arr[eligible_mask]
            eligible_skills = unassigned_skills_arr[eligible_mask]

            if len(eligible_ids) == 0:
                continue

            # Sort by skills (descending), then by id (ascending)
            sort_keys = np.lexsort((eligible_ids, -eligible_skills))
            eligible_ids = eligible_ids[sort_keys]
            eligible_skills = eligible_skills[sort_keys]

            # Assign up to vacancies
            hired_count = min(vacancies, len(eligible_ids))
            for i in range(hired_count):
                household_id = int(eligible_ids[i])
                skills_level = float(eligible_skills[i])

                # Get household to check experience (O(1) lookup via cache)
                household = self.household_lookup[household_id]

                # Calculate skill premium (25% max for skill level 1.0)
                skill_premium = skills_level * 0.25

                # Calculate experience premium (3% per year, capped at 30%)
                # Assume 52 ticks per year
                experience_ticks = household.category_experience.get(firm.good_category, 0)
                experience_years = experience_ticks / 52.0
                experience_premium = min(experience_years * 0.03, 0.3)

                # Calculate actual wage with premiums
                actual_wage = wage_offer * (1.0 + skill_premium + experience_premium)

                # Record hire
                firm_labor_outcomes[firm_id]["hired_households_ids"].append(household_id)
                firm_labor_outcomes[firm_id]["actual_wages"][household_id] = actual_wage
                assigned_households.add(household_id)

                # Job-switching: track turnover on the old firm
                labor_plan = household_labor_plans.get(household_id, {})
                if labor_plan.get("job_switching") and household.employer_id is not None:
                    old_firm = self.firm_lookup.get(household.employer_id)
                    if old_firm is not None:
                        old_firm.worker_turnover_this_tick += 1
                        old_outcome = firm_labor_outcomes.get(household.employer_id)
                        if old_outcome is not None:
                            old_outcome["confirmed_layoffs_ids"] = list(
                                old_outcome.get("confirmed_layoffs_ids", [])
                            ) + [household_id]

                # Update household outcome
                household_labor_outcomes[household_id] = {
                    "employer_id": firm_id,
                    "wage": actual_wage,
                    "employer_category": firm.good_category
                }

        for firm in sorted_firms:
            firm_id = firm.firm_id
            outcome = firm_labor_outcomes.get(firm_id)
            if outcome is None:
                continue
            original_vacancies = int(firm_production_plans[firm_id].get("planned_hires_count", 0) or 0)
            actual_hires = len(outcome.get("hired_households_ids", []) or [])
            unfilled = max(0, original_vacancies - actual_hires)
            if unfilled <= 0:
                continue

            outcome["unfilled_vacancies"] = int(unfilled)
            wage_offer = float(firm_wage_plans[firm_id].get("wage_offer_next", firm.wage_offer))
            remaining_reservations = []
            for household_id, labor_plan in household_labor_plans.items():
                if household_id in assigned_households:
                    continue
                if not bool(labor_plan.get("searching_for_job", False)):
                    continue
                if bool(labor_plan.get("medical_only", False)):
                    continue
                household = self.household_lookup.get(household_id)
                if household is None or not household.can_work:
                    continue
                remaining_reservations.append(float(labor_plan.get("reservation_wage", household.reservation_wage)))

            if not remaining_reservations:
                outcome["failed_match_reason"] = "no_available_searchers"
                continue

            wage_ineligible = [value for value in remaining_reservations if value > wage_offer + 1e-9]
            if len(wage_ineligible) == len(remaining_reservations):
                outcome["failed_match_reason"] = "reservation_above_wage_offer"
                outcome["reservation_reject_count"] = int(len(wage_ineligible))
                outcome["median_rejected_reservation_wage"] = float(np.median(np.array(wage_ineligible)))
            else:
                outcome["failed_match_reason"] = "eligible_candidates_exhausted"

        return firm_labor_outcomes, household_labor_outcomes

    def _match_labor_fast(
        self,
        firm_production_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
        household_labor_plans: Dict[int, Dict]
    ) -> Tuple[Dict[int, Dict], Dict[int, Dict]]:
        """
        Indexed labor matching for large populations.

        Behavioral intent preserved:
        - incumbent retention unless planned layoff
        - reservation wage eligibility
        - skill-first ranking with household_id tie-break
        - healthcare excluded from market matching

        Performance changes:
        - build active non-healthcare candidate snapshot once per tick
        - index candidates by reservation wage level once
        - query "best available candidate under wage_offer" efficiently
        - process only active hiring firms (planned_hires_count > 0)
        - randomized firm hiring order per tick with deterministic seed

        Matching flow:
        1. Build baseline household outcomes (keep incumbents unless laid off).
        2. Build one active labor pool snapshot:
           searching_for_job and can_work and not medical_only and not assigned.
        3. Bucket pool by reservation wage and sort each bucket by
           (skills desc, household_id asc).
        4. Build prefix-query index (segment tree) across buckets.
        5. Randomize active hiring firm order (seeded by random_seed + tick).
        6. For each firm, repeatedly select the best candidate from all
           reservation_wage <= wage_offer buckets.
        7. Mark hires assigned immediately so candidates cannot be double-hired.

        Important behavior note:
        The selection is "best among all eligible wage buckets", so firms
        naturally fall back to lower-skill candidates after top candidates
        are consumed. This avoids artificial shortages from hard skill buckets.
        """
        firm_labor_outcomes: Dict[int, Dict] = {}
        household_labor_outcomes: Dict[int, Dict] = {}

        planned_layoffs_set = set()
        for plan in firm_production_plans.values():
            planned_layoffs_set.update(plan.get("planned_layoffs_ids", []))

        n_households = len(self.households)
        household_ids = np.empty(n_households, dtype=np.int32)
        skills = np.empty(n_households, dtype=np.float32)
        reservation_wages = np.empty(n_households, dtype=np.float32)
        searching = np.zeros(n_households, dtype=np.bool_)
        can_work = np.zeros(n_households, dtype=np.bool_)
        medical_only = np.zeros(n_households, dtype=np.bool_)
        assigned = np.zeros(n_households, dtype=np.bool_)

        for idx, household in enumerate(self.households):
            household_id = household.household_id
            household_ids[idx] = household_id

            plan = household_labor_plans.get(household_id, {})
            skills[idx] = float(plan.get("skills_level", household.skills_level))
            reservation_wages[idx] = float(plan.get("reservation_wage", household.reservation_wage))
            searching[idx] = bool(plan.get("searching_for_job", False))
            can_work[idx] = household.can_work
            medical_only[idx] = bool(plan.get("medical_only", False))

            if not can_work[idx]:
                household_labor_outcomes[household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }
                continue

            # Keep incumbents by default (unless they are in planned layoffs or
            # actively job-switching — job-switchers re-enter the labor pool).
            is_job_switching = bool(household_labor_plans.get(household_id, {}).get("job_switching", False))
            if household.is_employed and household_id not in planned_layoffs_set and not is_job_switching:
                employer_id = household.employer_id
                employer_category = None
                if employer_id is not None and employer_id in self.firm_lookup:
                    employer_category = self.firm_lookup[employer_id].good_category
                household_labor_outcomes[household_id] = {
                    "employer_id": employer_id,
                    "wage": household.wage,
                    "employer_category": employer_category
                }
                assigned[idx] = True
            else:
                household_labor_outcomes[household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }

        # Maintain behavior for any labor-plan IDs not in self.households.
        for household_id in household_labor_plans.keys():
            if household_id not in household_labor_outcomes:
                household_labor_outcomes[household_id] = {
                    "employer_id": None,
                    "wage": 0.0,
                    "employer_category": None
                }

        # Initialize all firm outcomes up front and collect only firms that
        # are actively hiring in the non-healthcare labor market.
        active_hiring_firm_ids: List[int] = []
        # Track private firms not currently hiring (may absorb job-switchers).
        private_non_hiring_firm_ids: List[int] = []
        original_planned_hires_by_firm: Dict[int, int] = {}
        for firm in self.firms:
            firm_id = firm.firm_id
            production_plan = firm_production_plans[firm_id]
            confirmed_layoffs = production_plan["planned_layoffs_ids"]
            vacancies = int(production_plan["planned_hires_count"])
            original_planned_hires_by_firm[firm_id] = vacancies
            is_healthcare_firm = (firm.good_category or "").lower() == "healthcare"

            firm_labor_outcomes[firm_id] = {
                "hired_households_ids": [],
                "confirmed_layoffs_ids": confirmed_layoffs,
                "actual_wages": {},
                "unfilled_vacancies": 0,
                "failed_match_reason": "",
                "reservation_reject_count": 0,
                "median_rejected_reservation_wage": 0.0,
                "synthetic_switcher_vacancies": 0,
            }

            if is_healthcare_firm:
                continue
            if vacancies > 0:
                active_hiring_firm_ids.append(firm_id)
            elif not firm.is_baseline:
                # Private firm not planning to hire — may still absorb job-switchers
                private_non_hiring_firm_ids.append(firm_id)

        # Count job-switching workers; if any exist, let private non-hiring firms
        # also participate so switchers can reach firms advertising higher wages.
        job_switch_count = sum(
            1 for plan in household_labor_plans.values()
            if plan.get("job_switching")
        )
        if job_switch_count > 0:
            for firm_id in private_non_hiring_firm_ids:
                # Give each private firm up to job_switch_count vacancies so
                # switchers can join; firm production plans expand naturally next tick.
                firm_production_plans[firm_id]["planned_hires_count"] = job_switch_count
                firm_labor_outcomes[firm_id]["synthetic_switcher_vacancies"] = int(job_switch_count)
                active_hiring_firm_ids.append(firm_id)

        if not active_hiring_firm_ids:
            return firm_labor_outcomes, household_labor_outcomes

        # One-time active labor pool snapshot for this tick.
        # Only households relevant to non-healthcare market matching are included.
        candidate_mask = (~assigned) & searching & can_work & (~medical_only)
        candidate_indices = np.nonzero(candidate_mask)[0]
        if candidate_indices.size == 0:
            for firm_id in set(active_hiring_firm_ids):
                outcome = firm_labor_outcomes.get(firm_id, {})
                original_vacancies = int(original_planned_hires_by_firm.get(firm_id, 0))
                actual_hires = len(outcome.get("hired_households_ids", []) or [])
                unfilled = max(0, original_vacancies - actual_hires)
                if unfilled > 0:
                    outcome["unfilled_vacancies"] = int(unfilled)
                    outcome["failed_match_reason"] = "no_available_searchers"
            return firm_labor_outcomes, household_labor_outcomes

        candidate_reservations = reservation_wages[candidate_indices]
        # Distinct reservation levels become wage buckets.
        reservation_levels = np.unique(candidate_reservations)

        # Reservation wage buckets (exact levels): each bucket stores candidates
        # sorted by skill desc, then household_id asc.
        bucket_ids = np.searchsorted(reservation_levels, candidate_reservations, side="left")
        num_buckets = int(reservation_levels.size)
        buckets: List[List[int]] = [[] for _ in range(num_buckets)]
        for local_pos, bucket_id in enumerate(bucket_ids):
            candidate_idx = int(candidate_indices[local_pos])
            buckets[int(bucket_id)].append(candidate_idx)
        for bucket in buckets:
            bucket.sort(key=lambda idx: (-float(skills[idx]), int(household_ids[idx])))

        bucket_positions = np.zeros(num_buckets, dtype=np.int32)
        invalid_best = (-1.0, -1_000_000_000, -1, -1)  # (skill, -household_id, idx, bucket_id)

        def _peek_bucket(bucket_id: int) -> Tuple[float, int, int, int]:
            """Return current best candidate for a reservation bucket."""
            position = int(bucket_positions[bucket_id])
            bucket = buckets[bucket_id]
            while position < len(bucket) and assigned[bucket[position]]:
                position += 1
            bucket_positions[bucket_id] = position
            if position >= len(bucket):
                return invalid_best
            candidate_idx = bucket[position]
            return (
                float(skills[candidate_idx]),
                -int(household_ids[candidate_idx]),
                candidate_idx,
                bucket_id,
            )

        # Segment tree over reservation buckets for fast "best skill in
        # reservation <= wage_offer" prefix queries.
        # Each leaf is the current best candidate of one wage bucket.
        # Internal nodes cache max candidate by (skill, tie-break, index).
        tree_size = 1
        while tree_size < num_buckets:
            tree_size *= 2
        segment_tree: List[Tuple[float, int, int, int]] = [invalid_best] * (2 * tree_size)

        for bucket_id in range(num_buckets):
            segment_tree[tree_size + bucket_id] = _peek_bucket(bucket_id)
        for node in range(tree_size - 1, 0, -1):
            left = segment_tree[2 * node]
            right = segment_tree[2 * node + 1]
            segment_tree[node] = left if left >= right else right

        def _update_bucket(bucket_id: int) -> None:
            node = tree_size + bucket_id
            segment_tree[node] = _peek_bucket(bucket_id)
            node //= 2
            while node > 0:
                left = segment_tree[2 * node]
                right = segment_tree[2 * node + 1]
                segment_tree[node] = left if left >= right else right
                node //= 2

        def _query_best_up_to_bucket(max_bucket: int) -> Tuple[float, int, int, int]:
            if max_bucket < 0:
                return invalid_best
            max_bucket = min(max_bucket, num_buckets - 1)
            left = tree_size
            right = tree_size + max_bucket + 1
            best = invalid_best
            while left < right:
                if left & 1:
                    if segment_tree[left] > best:
                        best = segment_tree[left]
                    left += 1
                if right & 1:
                    right -= 1
                    if segment_tree[right] > best:
                        best = segment_tree[right]
                left //= 2
                right //= 2
            return best

        # Randomize active hiring order per tick to reduce first-mover bias.
        # Seed formula keeps run-to-run reproducibility under same seed.
        shuffle_rng = random.Random(int(CONFIG.random_seed) + self.current_tick * 104729 + 911)
        shuffle_rng.shuffle(active_hiring_firm_ids)

        for firm_id in active_hiring_firm_ids:
            firm = self.firm_lookup.get(firm_id)
            if firm is None:
                continue

            production_plan = firm_production_plans[firm_id]
            wage_plan = firm_wage_plans[firm_id]
            vacancies = int(production_plan["planned_hires_count"])
            wage_offer = float(wage_plan["wage_offer_next"])

            # Reservation eligibility boundary: only reservation_wage <= wage_offer.
            max_bucket = int(np.searchsorted(reservation_levels, wage_offer, side="right") - 1)
            if max_bucket < 0:
                continue

            while vacancies > 0:
                # Select global best candidate among all wage-eligible buckets.
                # If top-skill candidates are exhausted, this naturally falls
                # back to lower-skill candidates before leaving vacancies open.
                _, _, candidate_idx, bucket_id = _query_best_up_to_bucket(max_bucket)
                if candidate_idx < 0 or bucket_id < 0:
                    break

                # Consume this bucket head and refresh tree immediately.
                bucket_positions[bucket_id] += 1
                _update_bucket(bucket_id)

                # Candidate can already be assigned by an earlier firm in this
                # tick; stale entries are skipped lazily.
                if assigned[candidate_idx]:
                    continue

                household_id = int(household_ids[candidate_idx])
                household = self.household_lookup.get(household_id)
                if household is None:
                    continue

                skill_premium = float(skills[candidate_idx]) * 0.25
                experience_ticks = household.category_experience.get(firm.good_category, 0)
                experience_years = experience_ticks / 52.0
                experience_premium = min(experience_years * 0.03, 0.3)
                actual_wage = wage_offer * (1.0 + skill_premium + experience_premium)

                firm_labor_outcomes[firm_id]["hired_households_ids"].append(household_id)
                firm_labor_outcomes[firm_id]["actual_wages"][household_id] = actual_wage

                # Job-switching: if this worker was employed elsewhere, record
                # turnover on the old firm so it raises wages more aggressively.
                labor_plan = household_labor_plans.get(household_id, {})
                if labor_plan.get("job_switching") and household.employer_id is not None:
                    old_firm = self.firm_lookup.get(household.employer_id)
                    if old_firm is not None:
                        old_firm.worker_turnover_this_tick += 1
                        # Remove from old firm's hire list for this tick so they
                        # know they need to backfill (not ghost-employed at two firms).
                        old_outcome = firm_labor_outcomes.get(household.employer_id)
                        if old_outcome is not None:
                            old_outcome["confirmed_layoffs_ids"] = list(
                                old_outcome.get("confirmed_layoffs_ids", [])
                            ) + [household_id]

                household_labor_outcomes[household_id] = {
                    "employer_id": firm_id,
                    "wage": actual_wage,
                    "employer_category": firm.good_category
                }
                assigned[candidate_idx] = True
                vacancies -= 1

        # Unfilled-vacancy diagnostics. Matching is over, so the remaining pool
        # is the same for every firm: build it once, on first need.
        remaining_count = -1
        remaining_reservations = None
        sorted_remaining = None
        remaining_valid_count = 0
        remaining_median: Optional[float] = None
        for firm_id in set(active_hiring_firm_ids):
            firm = self.firm_lookup.get(firm_id)
            if firm is None:
                continue
            outcome = firm_labor_outcomes.get(firm_id, {})
            actual_hires = len(outcome.get("hired_households_ids", []) or [])
            original_vacancies = int(original_planned_hires_by_firm.get(firm_id, 0))
            unfilled = max(0, original_vacancies - actual_hires)
            if unfilled <= 0:
                continue

            outcome["unfilled_vacancies"] = int(unfilled)
            wage_offer = float(firm_wage_plans[firm_id].get("wage_offer_next", firm.wage_offer))
            if remaining_count < 0:
                remaining_mask = (~assigned) & searching & can_work & (~medical_only)
                remaining_indices = np.nonzero(remaining_mask)[0]
                remaining_count = int(remaining_indices.size)
                if remaining_count:
                    remaining_reservations = reservation_wages[remaining_indices]
                    sorted_remaining = np.sort(remaining_reservations)
                    # NaN sorts last and never compares greater, so leave it out of counts.
                    remaining_valid_count = remaining_count - int(
                        np.count_nonzero(np.isnan(remaining_reservations))
                    )

            if remaining_count == 0:
                outcome["failed_match_reason"] = "no_available_searchers"
            else:
                # Same comparison as `reservations > wage_offer + 1e-9`: numpy
                # compares a Python float with the array in the array's dtype
                # (float32 here), so cast the threshold to it before searching.
                threshold = sorted_remaining.dtype.type(wage_offer + 1e-9)
                ineligible_count = remaining_valid_count - int(
                    np.searchsorted(sorted_remaining, threshold, side="right")
                )

                if ineligible_count == remaining_count:
                    # Every remaining searcher is ineligible, so the rejected set
                    # is the whole remaining pool: one median serves all firms.
                    if remaining_median is None:
                        remaining_median = float(np.median(remaining_reservations))
                    outcome["failed_match_reason"] = "reservation_above_wage_offer"
                    outcome["reservation_reject_count"] = int(ineligible_count)
                    outcome["median_rejected_reservation_wage"] = remaining_median
                else:
                    outcome["failed_match_reason"] = "eligible_candidates_exhausted"

        # Job-switchers who didn't land a new job fall back to their old employer.
        # Without this they'd become involuntarily unemployed just for looking.
        for idx, household in enumerate(self.households):
            household_id = household.household_id
            labor_plan = household_labor_plans.get(household_id, {})
            if (labor_plan.get("job_switching")
                    and household_labor_outcomes.get(household_id, {}).get("employer_id") is None
                    and household.employer_id is not None):
                old_firm = self.firm_lookup.get(household.employer_id)
                employer_category = old_firm.good_category if old_firm else None
                household_labor_outcomes[household_id] = {
                    "employer_id": household.employer_id,
                    "wage": household.wage,
                    "employer_category": employer_category,
                }

        return firm_labor_outcomes, household_labor_outcomes

    def _update_continuing_employee_wages(self) -> None:
        """
        Update wages for continuing employees every 50 ticks.

        Applies a small 2-3% increase to existing employee wages to prevent
        massive wage increases within a single tick. Only updates employees
        who have been with the firm for at least 50 ticks.
        """

        _rng = random.Random(CONFIG.random_seed + self.current_tick * 4_001_909)

        for firm in self.firms:
            if not firm.employees:
                continue

            for employee_id in firm.employees:
                household = self.household_lookup.get(employee_id)
                if household is None or household.employer_id != firm.firm_id:
                    continue

                # Only update if last wage update was at least 50 ticks ago
                if self.current_tick - household.last_wage_update_tick >= 50:
                    current_wage = firm.actual_wages.get(employee_id, firm.wage_offer)

                    # Apply 2-3% increase
                    increase_rate = _rng.uniform(0.02, 0.03)
                    new_wage = current_wage * (1.0 + increase_rate)

                    # Update the wage
                    firm.actual_wages[employee_id] = new_wage
                    firm._invalidate_wage_bill_cache()
                    household.wage = new_wage
                    household.last_wage_update_tick = self.current_tick

    def _sync_firm_employee_rosters(self) -> None:
        """
        Rebuild firm employee lists from household employer links.

        This enforces one source of truth (household.employer_id) and avoids
        stale employee records in firm aggregates and frontend telemetry.
        """
        employees_by_firm: Dict[int, List[int]] = {firm.firm_id: [] for firm in self.firms}
        healthcare_firms = sorted(
            [firm for firm in self.firms if (firm.good_category or "").lower() == "healthcare"],
            key=lambda firm: firm.firm_id,
        )
        healthcare_firm_ids = {f.firm_id for f in healthcare_firms}

        for household in self.households:
            household_is_medical_only = household.medical_training_status in {"resident", "doctor"}

            # Doctors and residents can only work at healthcare firms.
            # Honor the household's existing employer_id if it already points to a
            # valid healthcare firm (preserves round-robin seeding and training
            # assignments). If not — e.g. a newly trained doctor who was previously
            # in a non-healthcare job — re-assign to the least-staffed healthcare firm
            # so the doctor pool is spread across all healthcare firms, not just the first.
            if household_is_medical_only:
                if not healthcare_firms:
                    household.employer_id = None
                    household.wage = 0.0
                    continue

                if household.employer_id not in healthcare_firm_ids:
                    # Re-assign to the healthcare firm with the fewest doctors so far
                    # (running count in employees_by_firm, updated as we iterate).
                    target_firm = min(
                        healthcare_firms,
                        key=lambda f: len(employees_by_firm[f.firm_id]),
                    )
                    household.employer_id = target_firm.firm_id

                assigned_firm = self.firm_lookup[household.employer_id]
                assigned_wage = assigned_firm.actual_wages.get(
                    household.household_id,
                    max(assigned_firm.wage_offer, household.reservation_wage),
                )
                household.wage = max(assigned_wage, 1.0)
                assigned_firm.actual_wages[household.household_id] = household.wage
                assigned_firm._invalidate_wage_bill_cache()
                employees_by_firm[household.employer_id].append(household.household_id)
                continue

            employer_id = household.employer_id
            if employer_id is None:
                household.wage = 0.0
                continue
            if employer_id not in self.firm_lookup:
                household.employer_id = None
                household.wage = 0.0
                continue

            employer = self.firm_lookup[employer_id]
            employer_is_healthcare = (employer.good_category or "").lower() == "healthcare"

            # Non-medical workers cannot be employed by healthcare firms.
            if employer_is_healthcare:
                household.employer_id = None
                household.wage = 0.0
                continue

            employees_by_firm[employer_id].append(household.household_id)

        for firm in self.firms:
            roster = employees_by_firm.get(firm.firm_id, [])
            firm.employees = roster

            synced_wages: Dict[int, float] = {}
            for household_id in roster:
                household = self.household_lookup.get(household_id)
                if household is not None and household.wage > 0.0:
                    synced_wages[household_id] = household.wage
                else:
                    fallback_wage = firm.actual_wages.get(household_id, firm.wage_offer)
                    synced_wages[household_id] = fallback_wage
                    if household is not None:
                        household.wage = fallback_wage
            firm.actual_wages = synced_wages
            firm._invalidate_wage_bill_cache()

    # -------------------------------------------------------------------------
    # Section: Goods market clearing and firm market views
    # -------------------------------------------------------------------------
    def _estimated_firm_market_supply(self, firm: FirmAgent, current_tick_capacity: bool = False) -> float:
        """Return shoppable supply without treating Services capacity as inventory."""
        category = (firm.good_category or "").lower()
        if category == "services":
            if current_tick_capacity:
                return max(0.0, float(firm.last_units_produced))
            service_worker_slots = max(0, int(firm.production_capacity_units))
            active_workers = min(len(firm.employees), service_worker_slots)
            return max(0.0, float(firm._capacity_for_workers(active_workers)))
        return max(0.0, float(firm.inventory_units))

    def _effective_market_price(self, firm: FirmAgent, available_supply: float) -> float:
        """Return the price used for market clearing."""
        price = max(0.0, float(firm.price))
        if (firm.good_category or "").lower() != "services" or available_supply <= 0.0:
            return price

        wage_bill = max(0.0, float(firm._current_wage_bill()))
        if wage_bill <= 0.0:
            wage_bill = max(1, len(firm.employees)) * max(0.0, float(firm.wage_offer))
        service_debt_service = max(
            0.0,
            float(getattr(firm, "service_infrastructure_loan_payment_per_tick", 0.0)),
        )
        break_even_price = (wage_bill + service_debt_service) / max(float(available_supply), 1e-6)
        markup = max(0.0, float(getattr(firm, "markup", 0.0)))
        service_floor = break_even_price * (1.0 + markup)
        return max(price, service_floor)

    def _withdraw_deposits_to_cash(self, household: HouseholdAgent, amount: float) -> float:
        """Move up to ``amount`` of deposits to cash through ``bank.withdraw``; record the ledger flow.

        Returns the amount actually withdrawn (the bank may pay less when its
        reserves are short).
        """
        actual = self.bank.withdraw(household.household_id, amount)
        if actual > 0.0:
            household.bank_deposit -= actual
            household.cash_balance += actual
            household.add_ledger_flow("bank", actual)
        return actual

    def _withdraw_deposits_for_planned_consumption(
        self,
        household_consumption_plans: Dict[int, Dict],
    ) -> None:
        """Pre-purchase deposit withdrawal: move planned-spend shortfall from bank to cash.

        Households treat 90% of deposits as accessible liquidity when planning consumption.
        Before market clearing, withdraw only the amount needed to cover planned spend beyond
        current cash. Money-conserving: household.cash ↑, household.bank_deposit ↓,
        bank.cash_reserves ↓ by the same amount.
        """
        if self.bank is None:
            return
        total_withdrawn = 0.0
        for household_id, plan in household_consumption_plans.items():
            household = self.household_lookup.get(household_id)
            if household is None:
                continue
            planned_spend = max(0.0, float(plan.get("budget", 0.0)))
            current_cash = max(0.0, household.cash_balance)
            if planned_spend <= current_cash:
                continue
            needed = planned_spend - current_cash
            max_withdrawable = 0.90 * max(0.0, household.bank_deposit)
            withdraw = min(needed, max_withdrawable)
            if withdraw <= 0.0:
                continue
            actual = self._withdraw_deposits_to_cash(household, withdraw)
            if actual <= 0.0:
                continue
            total_withdrawn += actual
        self.last_tick_pre_purchase_deposit_withdrawals += total_withdrawn

    def _payment_withdraw_deposits(self, quotes: Dict[int, float]) -> None:
        if self.bank is None:
            return
        for hh in self.households:
            needed = max(0.0, float(quotes.get(hh.household_id, 0.0)))
            amount = min(needed, 0.90 * max(0.0, hh.bank_deposit))
            if amount <= MONEY_EPS:
                continue
            actual = self.bank.withdraw(hh.household_id, amount)
            hh.cash_balance += actual
            hh.bank_deposit -= actual
            hh.add_ledger_flow("bank", actual)
            self.last_tick_pre_purchase_deposit_withdrawals += actual

    def _payment_collect_direct_firm_loans(self) -> float:
        """Collect direct treasury claims after registered firm debt, before exits."""
        total = 0.0
        for firm in self.firms:
            if firm.government_loan_remaining <= MONEY_EPS:
                continue
            paid = min(max(0.0, firm.cash_balance), max(0.0, firm.loan_payment_per_tick),
                       max(0.0, firm.government_loan_remaining))
            if paid <= MONEY_EPS:
                continue
            firm.cash_balance -= paid
            firm.government_loan_remaining = max(0.0, firm.government_loan_remaining - paid)
            total += paid
        self.government.cash_balance += total
        return total

    def _clear_goods_market(
        self,
        household_consumption_plans: Dict[int, Dict],
        firms: List[FirmAgent]
    ) -> Tuple[Dict[int, Dict[str, Tuple[float, float]]], Dict[int, Dict[str, float]]]:
        """
        Clear the goods market deterministically.

        Args:
            household_consumption_plans: Desired purchases from households
            firms: List of firm agents with inventory

        Returns:
            Tuple of (per_household_purchases, per_firm_sales)

        Note:
            SOLID VIOLATION - Single Responsibility Principle (SRP):
            This method has multiple responsibilities:
            1. Market clearing logic (matching supply to demand)
            2. Unmet demand tracking by category (food, services)
            3. Price updating for services category firms
            4. Per-household and per-firm sales accumulation
            Consider extracting unmet demand tracking and price updating into separate methods.

            SOLID VIOLATION - Open/Closed Principle (OCP):
            Adding a new purchase target type (beyond direct firm ID and good name)
            requires modifying the if/elif branching logic in the inner loop.
        """
        per_household_purchases: Dict[int, Dict[str, Tuple[float, float]]] = {}
        per_firm_sales: Dict[int, Dict[str, float]] = {}

        # Firm arrays for fast lookup
        firm_ids = [f.firm_id for f in firms]
        id_to_idx = {fid: idx for idx, fid in enumerate(firm_ids)}
        firm_available = [
            self._estimated_firm_market_supply(f, current_tick_capacity=True)
            for f in firms
        ]
        firm_market_prices = []
        for firm, available in zip(firms, firm_available):
            effective_price = self._effective_market_price(firm, available)
            if (firm.good_category or "").lower() == "services" and effective_price > float(firm.price):
                firm.price = effective_price
            firm_market_prices.append(effective_price)

        firm_prices = np.array(firm_market_prices, dtype=np.float64)
        firm_goods = [f.good_name for f in firms]
        firm_remaining = np.array(firm_available, dtype=np.float64)

        # Array accumulators indexed by firm position. Avoids a nested-dict
        # mutation per sale; materialized into per_firm_sales at the end with
        # the same {firm_id: {"units_sold","revenue"}} shape downstream expects.
        n_firms = len(firms)
        firm_units_sold = np.zeros(n_firms, dtype=np.float64)
        firm_revenue = np.zeros(n_firms, dtype=np.float64)

        _good_name_to_cat = {f.good_name: (f.good_category or "").lower() for f in firms}
        # Per-idx category, so unmet-demand branching skips a dict.get per event.
        firm_cat_by_idx = [_good_name_to_cat[g] for g in firm_goods]
        _unmet_food = 0.0
        _unmet_services = 0.0

        # Local binds: hoist attribute lookups out of the per-event hot loop.
        services_unmet_by_firm = self.services_unmet_demand_by_firm
        record_firm_unmet = self._record_firm_unmet_demand

        # Group firm indices by good_name, sorted by price then id. Python int
        # lists (not np arrays) — faster iteration, and a per-good cursor below
        # skips the contiguous sold-out prefix instead of rescanning from 0.
        goods_to_indices: Dict[str, list] = {}
        for idx, firm in enumerate(firms):
            goods_to_indices.setdefault(firm.good_name, []).append(idx)
        for good_name, idx_list in goods_to_indices.items():
            idx_list.sort(key=lambda i: (firm_prices[i], firm_ids[i]))
        # cursor[good] = index into idx_list before which every firm is exhausted.
        # Exhaustion is monotonic within a tick (firm_remaining only decreases),
        # so advancing past a sold-out prefix never skips a firm with stock.
        good_cursor: Dict[str, int] = {}

        # Process households in insertion order. Plans are constructed by household order,
        # so this avoids an O(H log H) sort each tick.
        for household_id, consumption_plan in household_consumption_plans.items():
            per_household_purchases[household_id] = {}
            planned = consumption_plan["planned_purchases"]

            for target, desired_qty in planned.items():
                if desired_qty <= 0:
                    continue

                # Direct firm id target (check for both int and np.integer)
                if isinstance(target, (int, np.integer)):
                    idx = id_to_idx.get(int(target))  # Convert np.int32 to Python int for dict lookup
                    if idx is None:
                        continue
                    available = firm_remaining[idx]
                    if available <= 0:
                        _cat = firm_cat_by_idx[idx]
                        if _cat == "food":
                            _unmet_food += desired_qty
                        elif _cat == "services":
                            _unmet_services += desired_qty
                            _fid = firm_ids[idx]
                            services_unmet_by_firm[_fid] = (
                                services_unmet_by_firm.get(_fid, 0.0) + desired_qty
                            )
                        record_firm_unmet(firm_ids[idx], desired_qty)
                        continue
                    qty = min(desired_qty, available)
                    if qty <= 0:
                        continue
                    _unmet = desired_qty - qty
                    if _unmet > 0:
                        _cat = firm_cat_by_idx[idx]
                        if _cat == "food":
                            _unmet_food += _unmet
                        elif _cat == "services":
                            _unmet_services += _unmet
                            _fid = firm_ids[idx]
                            services_unmet_by_firm[_fid] = (
                                services_unmet_by_firm.get(_fid, 0.0) + _unmet
                            )
                        record_firm_unmet(firm_ids[idx], _unmet)
                    firm_remaining[idx] -= qty
                    price = firm_prices[idx]
                    firm_units_sold[idx] += qty
                    firm_revenue[idx] += qty * price

                    gname = firm_goods[idx]
                    prev_qty, prev_price = per_household_purchases[household_id].get(gname, (0.0, 0.0))
                    total_qty = prev_qty + qty
                    if total_qty > 0:
                        avg_price = ((prev_qty * prev_price) + (qty * price)) / total_qty
                        per_household_purchases[household_id][gname] = (total_qty, avg_price)
                    continue

                # Good-name target: spread across sorted firms
                good_name = target
                idx_list = goods_to_indices.get(good_name)
                if idx_list is None or len(idx_list) == 0:
                    continue

                # Advance the shared cursor past any leading sold-out firms so
                # repeated generic purchases don't rescan the exhausted prefix.
                cursor = good_cursor.get(good_name, 0)
                n_idx = len(idx_list)
                while cursor < n_idx and firm_remaining[idx_list[cursor]] <= 0:
                    cursor += 1
                good_cursor[good_name] = cursor

                remaining = desired_qty
                total_bought = 0.0
                price_sum = 0.0

                for scan in range(cursor, n_idx):
                    if remaining <= 0:
                        break
                    idx = idx_list[scan]
                    available = firm_remaining[idx]
                    if available <= 0:
                        continue
                    qty = min(remaining, available)
                    firm_remaining[idx] -= qty
                    price = firm_prices[idx]
                    firm_units_sold[idx] += qty
                    firm_revenue[idx] += qty * price
                    total_bought += qty
                    price_sum += qty * price
                    remaining -= qty

                if remaining > 0:
                    _cat = _good_name_to_cat.get(good_name, "")
                    if _cat == "food":
                        _unmet_food += remaining
                    elif _cat == "services":
                        _unmet_services += remaining

                if total_bought > 0:
                    per_household_purchases[household_id][good_name] = (
                        total_bought,
                        price_sum / total_bought
                    )

        self.food_unmet_demand += _unmet_food
        self.services_unmet_demand += _unmet_services

        # Materialize array accumulators back into the public per-firm shape.
        for idx, fid in enumerate(firm_ids):
            per_firm_sales[fid] = {
                "units_sold": float(firm_units_sold[idx]),
                "revenue": float(firm_revenue[idx]),
            }

        return per_household_purchases, per_firm_sales

    def _record_firm_unmet_demand(self, firm_id: int, unmet_units: float) -> None:
        unmet_units = max(0.0, float(unmet_units or 0.0))
        if unmet_units <= 0.0:
            return
        fid = int(firm_id)
        self.current_tick_unmet_demand_by_firm[fid] = (
            self.current_tick_unmet_demand_by_firm.get(fid, 0.0) + unmet_units
        )

    def _build_firm_market_views(
        self,
    ) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, float]]], float, float]:
        """
        Build per-tick firm views in one pass.

        Returns:
            good_category_lookup, category_market_snapshot,
            housing_private_inventory, housing_baseline_inventory
        """
        good_category_lookup: Dict[str, str] = {}
        category_market_snapshot: Dict[str, List[Dict[str, float]]] = {}
        housing_private_inventory = 0.0
        housing_baseline_inventory = 0.0

        for firm in self.firms:
            category_key = firm.good_category.lower()
            good_category_lookup[firm.good_name] = category_key

            if category_key == "housing":
                if firm.is_baseline:
                    housing_baseline_inventory += firm.inventory_units
                else:
                    housing_private_inventory += firm.inventory_units

            if category_key == "healthcare":
                # Healthcare is queue-based service throughput, not a shoppable goods category.
                continue

            category_market_snapshot.setdefault(category_key, []).append({
                "firm_id": firm.firm_id,
                "good_name": firm.good_name,
                "price": firm.price,
                "quality": self._effective_firm_quality(firm),
                "inventory": self._estimated_firm_market_supply(firm),
            })

        return (
            good_category_lookup,
            category_market_snapshot,
            housing_private_inventory,
            housing_baseline_inventory,
        )

    def _build_category_market_snapshot(self) -> Dict[str, List[Dict[str, float]]]:
        """Provide firms grouped by category for household consumption planning."""
        snapshot: Dict[str, List[Dict[str, float]]] = {}
        for firm in self.firms:
            category_key = firm.good_category.lower()
            if category_key == "healthcare":
                # Healthcare is queue-based service throughput, not a shoppable goods category.
                continue
            if category_key not in snapshot:
                snapshot[category_key] = []
            snapshot[category_key].append({
                "firm_id": firm.firm_id,
                "good_name": firm.good_name,
                "price": firm.price,
                "quality": self._effective_firm_quality(firm),
                "inventory": self._estimated_firm_market_supply(firm),
            })
        return snapshot

    def _effective_firm_quality(self, firm: FirmAgent) -> float:
        """Return firm quality after economy-wide technology policy effects."""
        return min(
            10.0,
            max(0.0, float(firm.quality_level) * float(self.government.technology_quality_multiplier))
        )

    def _build_good_category_lookup(self) -> Dict[str, str]:
        """Map each good_name to its category (lowercased) for quick lookups."""
        return build_good_category_lookup(self.firms)

    def _next_firm_id(self) -> int:
        """Generate a unique firm_id across active and queued firms."""
        existing_ids = set(self.firm_lookup.keys())
        existing_ids.update(f.firm_id for f in self.queued_firms)
        return max(existing_ids) + 1 if existing_ids else 1

    def _refresh_target_total_firms(self) -> None:
        """Recalculate desired firm count from household-to-firm ratio.

        The target is bidirectional — it can decrease when firms die and demand
        doesn't justify replacements.  The hard floor is the baseline count plus
        a per-sector competition minimum so small simulations always have enough
        private firms to create real price competition.
        """
        households = max(1, len(self.households))
        per_thousand = CONFIG.firms.target_firms_per_1000_households
        demand_target = int(math.ceil((households / 1000.0) * per_thousand))
        baseline_count = sum(1 for f in self.firms if f.is_baseline)
        queued_count = len(self.queued_firms)
        # Competition floor: baselines + minimum private competitors in each
        # spawnable sector (Food + Services).  Prevents permanent monopoly in
        # small sims where demand_target barely exceeds baseline count.
        min_private = CONFIG.firms.min_private_firms_per_competing_sector
        competition_floor = baseline_count + queued_count + min_private * 2
        self.target_total_firms = max(demand_target, competition_floor)

    def _activate_queued_firms(self) -> None:
        """
        Activate queued firms gradually after warm-up (staggered entry).

        Instead of activating all firms at once, only activate up to
        max_new_firms_per_tick firms per tick to prevent labor market shocks.
        """
        if not self.queued_firms:
            return

        if len(self.firms) >= self.target_total_firms * 1.2:
            return

        max_new_firms = CONFIG.firms.max_new_firms_per_tick
        firms_to_activate = min(max_new_firms, len(self.queued_firms))

        allowed = max(0, int(self.target_total_firms * 1.2) - len(self.firms))
        firms_to_activate = min(firms_to_activate, allowed)

        for _ in range(firms_to_activate):
            firm = self.queued_firms.pop(0)
            firm.stabilization_disabled = not self.enable_firm_stabilizers
            self.firms.append(firm)
            self.firm_lookup[firm.firm_id] = firm
            self.last_tick_sales_units[firm.firm_id] = 0.0
            self.last_tick_revenue[firm.firm_id] = 0.0
            self.last_tick_sell_through_rate[firm.firm_id] = 0.5
            self.last_tick_prices[firm.good_name] = firm.price

            # Phase: Startup loan from bank to bootstrap new firms
            if self.bank is not None and firm.cash_balance < 50_000.0:
                startup_amount = 25_000.0
                self._issue_firm_loan(
                    firm,
                    amount=startup_amount,
                    term_ticks=208,  # 4-year repayment period
                    govt_rate=0.03,  # Standard market rate
                    spread=0.00,     # No spread for startups
                )

    # -------------------------------------------------------------------------
    # Section: Wellbeing, tax snapshots, production, and firm lifecycle
    # -------------------------------------------------------------------------
    def _batch_update_wellbeing(self, happiness_multiplier: float) -> None:
        """Vectorized wellbeing update; the only wellbeing implementation (per-agent update_wellbeing was removed)."""
        if not self.households:
            return

        hc = CONFIG.households
        households = self.households
        n = len(households)

        employed = np.fromiter((h.employer_id is not None for h in households), dtype=np.bool_, count=n)
        wages = np.fromiter((h.wage for h in households), dtype=np.float64, count=n)
        expected_wages = np.fromiter((h.expected_wage for h in households), dtype=np.float64, count=n)

        happiness = np.fromiter((h.happiness for h in households), dtype=np.float64, count=n)
        morale = np.fromiter((h.morale for h in households), dtype=np.float64, count=n)
        health = np.fromiter((h.health for h in households), dtype=np.float64, count=n)

        happiness_decay = np.fromiter((h.happiness_decay_rate for h in households), dtype=np.float64, count=n)
        morale_decay = np.fromiter((h.morale_decay_rate for h in households), dtype=np.float64, count=n)
        health_decay = np.fromiter((h.health_decay_rate for h in households), dtype=np.float64, count=n)

        cash_balances = np.fromiter((h.cash_balance for h in households), dtype=np.float64, count=n)
        cash_prev = np.fromiter((h.last_tick_cash_start for h in households), dtype=np.float64, count=n)
        housing_met = np.fromiter((h.met_housing_need for h in households), dtype=np.bool_, count=n)
        food_consumed = np.fromiter((h.food_consumed_this_tick for h in households), dtype=np.float64, count=n)
        min_food = np.fromiter((h.min_food_per_tick for h in households), dtype=np.float64, count=n)
        services_consumed = np.fromiter((h.services_consumed_this_tick for h in households), dtype=np.float64, count=n)

        # Per-agent morale parameters (randomized per household); the midpoint
        # fallbacks are constant, so compute them once rather than per household.
        default_emp_boost = sum(hc.morale_employed_boost_range) / 2.0
        default_unemp_penalty = sum(hc.morale_unemployed_penalty_range) / 2.0
        default_unhoused_penalty = sum(hc.morale_unhoused_penalty_range) / 2.0
        morale_emp_boost = np.fromiter(
            (h.morale_employed_boost if h.morale_employed_boost is not None
             else default_emp_boost
             for h in households),
            dtype=np.float64, count=n
        )
        morale_unemp_penalty = np.fromiter(
            (h.morale_unemployed_penalty if h.morale_unemployed_penalty is not None
             else default_unemp_penalty
             for h in households),
            dtype=np.float64, count=n
        )
        morale_unhoused_penalty = np.fromiter(
            (h.morale_unhoused_penalty if h.morale_unhoused_penalty is not None
             else default_unhoused_penalty
             for h in households),
            dtype=np.float64, count=n
        )

        # --- Happiness ---
        happiness_change = np.zeros(n, dtype=np.float64)

        # Poverty penalties (from config)
        happiness_change -= np.where(cash_balances < hc.extreme_poverty_threshold,
                                     hc.extreme_poverty_penalty, 0.0)
        happiness_change -= np.where(
            (cash_balances >= hc.extreme_poverty_threshold) & (cash_balances < hc.poverty_threshold),
            hc.poverty_penalty, 0.0)

        # Government social programs boost
        if happiness_multiplier > 1.0:
            happiness_change += (happiness_multiplier - 1.0) * hc.government_happiness_scaling

        # --- Positive recovery terms ---
        # These were missing from the batch path, causing happiness to only decay
        # and never recover through normal consumption activity.
        happiness_change += np.where(food_consumed >= min_food, 0.0008, 0.0)      # Fed adequately
        happiness_change += np.where(services_consumed > 0, 0.0005, 0.0)          # Used services
        happiness_change += np.where(housing_met, 0.0007, 0.0)                    # Housing met
        wage_satisfied = employed & (wages >= expected_wages)
        happiness_change += np.where(wage_satisfied, 0.0005, 0.0)                 # Fair wage

        # --- New negative terms ---
        # (a) Unemployment: being jobless hurts happiness independently of poverty
        happiness_change -= np.where(~employed, hc.unemployed_happiness_penalty, 0.0)

        # (b) Relative wealth-loss: losing cash hurts proportionally, not just at thresholds
        has_prior_cash = cash_prev > 1.0
        cash_loss_pct = np.where(
            has_prior_cash,
            np.maximum(0.0, (cash_prev - cash_balances) / np.maximum(cash_prev, 1.0)),
            0.0
        )
        happiness_change -= cash_loss_pct * hc.wealth_loss_happiness_scaling

        # (c) Food shortfall: not meeting minimum food hurts proportionally
        food_shortfall_ratio = np.maximum(0.0, (min_food - food_consumed) / np.maximum(min_food, 0.1))
        happiness_change -= food_shortfall_ratio * hc.food_shortfall_happiness_scaling

        # Mercy floor: natural decay pauses below threshold (penalties still apply)
        effective_decay = np.where(happiness < hc.mercy_floor_threshold, 0.0, happiness_decay)
        happiness_change -= effective_decay
        happiness_next = np.clip(happiness + happiness_change, 0.0, 1.0)

        # --- Morale ---
        morale_change = np.zeros(n, dtype=np.float64)

        # Employed: base boost + wage satisfaction
        morale_change += np.where(employed, morale_emp_boost, 0.0)
        satisfied = employed & (wages >= expected_wages)
        morale_change += np.where(satisfied, hc.wage_satisfaction_boost, 0.0)

        # Underpaid penalty
        underpaid = employed & (wages < expected_wages)
        wage_gap_ratio = np.zeros(n, dtype=np.float64)
        if underpaid.any():
            wage_gap_ratio[underpaid] = (expected_wages[underpaid] - wages[underpaid]) / np.maximum(
                expected_wages[underpaid], 1.0
            )
        morale_change -= wage_gap_ratio * hc.wage_dissatisfaction_scaling

        # Unemployed penalty
        morale_change -= np.where(~employed, morale_unemp_penalty, 0.0)

        # Unhoused penalty
        morale_change -= np.where(~housing_met, morale_unhoused_penalty, 0.0)

        morale_change -= morale_decay
        morale_next = np.clip(morale + morale_change, 0.0, 1.0)

        # --- Health ---
        # Non-linear food→health: harsh penalty for no food, gentle near threshold.
        # Uses ratio^0.6 curve so partial eating is mostly OK but starvation hurts.
        food_threshold = max(0.1, hc.food_health_high_threshold)
        food_ratio = np.minimum(1.0, food_consumed / food_threshold)
        # Curve the ratio: steep near 0 (starvation), gentle near 1 (well-fed)
        curved_ratio = np.power(food_ratio, 0.6)
        # At curved_ratio=0: effect = -starvation_penalty
        # At curved_ratio=1: effect = +high_boost
        health_food_effect = (
            curved_ratio * (hc.food_health_high_boost + hc.food_starvation_penalty)
            - hc.food_starvation_penalty
        )
        positive_food_effect = np.maximum(0.0, health_food_effect)
        food_offset_share = max(0.0, min(1.0, hc.food_health_decay_offset_share))
        food_offset_ratio = np.minimum(1.0, positive_food_effect / max(hc.food_health_high_boost, 1e-9))
        health_positive = health_decay * food_offset_share * food_offset_ratio
        health_negative = np.minimum(0.0, health_food_effect)

        health_change = health_positive + health_negative - health_decay
        health_next = np.clip(health + health_change, 0.0, 1.0)

        # Write back
        for idx, household in enumerate(households):
            household.happiness = float(happiness_next[idx])
            household.morale = float(morale_next[idx])
            household.health = float(health_next[idx])

    def _sync_warmup_expectations(self, current_prices: Dict[str, float]) -> None:
        """During warm-up, force beliefs/expectations to current observed values."""
        for household in self.households:
            if household.is_employed:
                household.expected_wage = household.wage
            for good, price in current_prices.items():
                household.price_beliefs[good] = price

    def _reset_post_warmup_expectations(self) -> None:
        """Reset household wage expectations/reservations to align with post-warmup economy."""
        if not self.households:
            return

        wage_offers = [f.wage_offer for f in self.firms if f.wage_offer > 0]
        if wage_offers:
            wage_anchor = float(np.median(wage_offers))
        else:
            wage_anchor = 30.0

        for household in self.households:
            housing_price = household.price_beliefs.get("housing", household.default_price_level)
            food_price = household.price_beliefs.get("food", household.default_price_level)
            living_cost = 0.3 * housing_price + household.min_food_per_tick * food_price
            living_cost = max(living_cost, 25.0)

            household.expected_wage = wage_anchor

            # H1': Dynamic reservation wage with decay over unemployment duration
            unemployment_benefit = self.government.get_unemployment_benefit_level()
            wage_tax_rate = self.government.wage_tax_rate

            # Net unemployment benefit (after tax)
            benefit_net = unemployment_benefit * (1.0 - wage_tax_rate)

            if household.is_employed:
                # Employed: Update reservation wage toward current net wage
                current_net_wage = household.wage * (1.0 - wage_tax_rate)
                household.reservation_wage = 0.9 * household.reservation_wage + 0.1 * current_net_wage

                # Also ensure minimum wage floor for existing workers
                minimum_wage = self.government.get_minimum_wage()
                household.wage = max(household.wage, living_cost, minimum_wage)
                if household.employer_id is not None and household.employer_id in self.firm_lookup:
                    employer_firm = self.firm_lookup[household.employer_id]
                    employer_firm.actual_wages[household.household_id] = household.wage
                    employer_firm._invalidate_wage_bill_cache()
            else:
                # Unemployed: Initialize or decay reservation wage
                if household.unemployment_duration == 1:
                    # First tick unemployed: Start 20% above benefits
                    household.reservation_wage = benefit_net * 1.2
                elif household.unemployment_duration > 1:
                    # Decay reservation wage toward 5% above benefits.
                    # Homelessness triples the decay rate — unhoused households
                    # are under immediate shelter pressure and lower their standards faster.
                    is_homeless = household.renting_from_firm_id is None
                    decay_speed = 0.03 if is_homeless else 0.01
                    floor_factor = 1.05  # Long-run: 5% above benefits
                    target_reservation = benefit_net * floor_factor

                    household.reservation_wage = (
                        (1.0 - decay_speed) * household.reservation_wage +
                        decay_speed * target_reservation
                    )

                # Never go below living cost
                household.reservation_wage = max(household.reservation_wage, living_cost)

    def _build_household_transfer_snapshots(self) -> List[Dict[str, object]]:
        """
        Build snapshots for government transfer planning.

        Returns:
            List of dicts with household_id, is_employed, cash_balance
        """
        snapshots = []
        for household in self.households:
            snapshots.append({
                "household_id": household.household_id,
                "is_employed": household.is_employed,
                "cash_balance": household.cash_balance
            })
        return snapshots

    def _build_household_tax_snapshots(
        self,
        frozen_wages: Optional[Dict[int, float]] = None
    ) -> List[Dict[str, object]]:
        """
        Build snapshots for government tax planning (household part).

        When supplied, frozen_wages holds this tick's production-boundary
        ordinary gross wages in currency per tick. Direct calls retain the
        household contract wage fallback.

        Returns:
            List of dicts with household_id and wage_income
        """
        snapshots = []
        for household in self.households:
            if frozen_wages is not None:
                wage_income = frozen_wages.get(household.household_id, 0.0)
            else:
                wage_income = household.wage if household.is_employed else 0.0
            snapshots.append({
                "household_id": household.household_id,
                "wage_income": wage_income
            })
        return snapshots

    def _build_firm_tax_snapshots(
        self,
        per_firm_sales: Dict[int, Dict[str, float]]
    ) -> List[Dict[str, object]]:
        """
        Build snapshots for government tax planning (firm part).

        Args:
            per_firm_sales: Sales data from goods market clearing

        Returns:
            List of dicts with firm_id, profit_before_tax, and price_ceiling_tax
        """
        snapshots = []
        PRICE_CEILING = CONFIG.market.price_ceiling
        PRICE_CEILING_TAX_RATE = CONFIG.market.price_ceiling_tax_rate

        for firm in self.firms:
            sales_data = per_firm_sales.get(firm.firm_id, {"revenue": 0.0, "units_sold": 0.0})
            revenue = sales_data["revenue"]
            if self.payment_sequence != "legacy" and self.payment_book is not None:
                revenue += self.payment_book.rent_receipts.get(firm.firm_id, 0.0)
                revenue += self.payment_state.get("services_pending_receipts", {}).get(firm.firm_id, 0.0)
            units_sold = sales_data["units_sold"]

            # Calculate price ceiling tax
            # If price > $50, firm pays 25% tax on the revenue from those sales
            price_ceiling_tax = 0.0
            if firm.price > PRICE_CEILING and units_sold > 0:
                # Tax applies to revenue from sales above the ceiling
                price_ceiling_tax = sales_data["revenue"] * PRICE_CEILING_TAX_RATE

            # Compute costs
            wage_bill = firm._current_wage_bill()

            # Add CEO salary if firm has a CEO (3x median worker wage)
            ceo_salary = 0.0
            if self.payment_sequence != "legacy" and self.payment_book is not None:
                wage_bill += self.payment_book.funded_ceo.get(firm.firm_id, 0.0)
            elif firm.ceo_household_id is not None and firm.employees:
                median_worker_wage = np.median([firm.actual_wages.get(e_id, firm.wage_offer) for e_id in firm.employees])
                ceo_salary = median_worker_wage * 3.0  # CEO earns 3x median worker
                wage_bill += ceo_salary

            # Note: Other variable costs would be included here if tracked

            # Profit = revenue - wage_bill - price_ceiling_tax (simplified)
            profit_before_tax = revenue - wage_bill - price_ceiling_tax

            snapshots.append({
                "firm_id": firm.firm_id,
                "profit_before_tax": profit_before_tax,
                "price_ceiling_tax": price_ceiling_tax,
                **({"cash_balance": float(firm.cash_balance),
                    "good_category": firm.good_category,
                    "property_tax_rate": float(firm.property_tax_rate),
                    "max_rental_units": int(firm.max_rental_units),
                    "price": float(firm.price)} if self.payment_sequence != "legacy" else {}),
            })
        return snapshots

    def _calculate_experience_adjusted_production(
        self, firm: FirmAgent, planned_production_units: float
    ) -> float:
        """
        Calculate actual production based on workforce experience, skills, and wellbeing.

        Workers with more experience in the firm's category produce more.
        Workers with higher happiness/morale/health perform better.
        Government infrastructure investment boosts all productivity.

        Args:
            firm: The firm to calculate production for
            planned_production_units: Planned production from plan_production_and_labor

        Returns:
            Actual production units accounting for experience, wellbeing, and infrastructure
        """
        workers = firm.employees
        if self.payment_sequence != "legacy":
            assigned_id = getattr(self, "payment_project_worker_by_firm", {}).get(firm.firm_id)
            if assigned_id is not None:
                workers = [hid for hid in firm.employees if hid != assigned_id]
        if len(workers) == 0:
            return 0.0

        if firm.good_category.lower() == "services":
            config_low, config_high = CONFIG.firms.services_units_per_worker_range
            if config_high < config_low:
                config_low, config_high = config_high, config_low
            low_units = max(1.0, float(config_low))
            high_units = min(7.0, max(low_units, float(config_high)))

            service_capacity = 0.0
            service_worker_slots = max(0, int(firm.production_capacity_units))
            active_service_workers = list(workers[:service_worker_slots])
            for employee_id in active_service_workers:
                household = self.household_lookup.get(employee_id)
                if household is None:
                    worker_effectiveness = 0.5
                else:
                    skill = max(0.0, min(1.0, float(household.skills_level)))
                    health = max(0.0, min(1.0, float(household.health)))
                    morale = max(0.0, min(1.0, float(household.morale)))
                    happiness = max(0.0, min(1.0, float(household.happiness)))
                    worker_effectiveness = max(
                        0.0,
                        min(1.0, 0.30 * skill + 0.25 * health + 0.25 * morale + 0.20 * happiness),
                    )
                service_capacity += low_units + (high_units - low_units) * worker_effectiveness

            return min(
                max(0.0, float(planned_production_units)),
                service_capacity * firm.supply_shock_multiplier,
            )

        # Calculate average productivity multiplier for the workforce
        total_productivity_multiplier = 0.0
        for employee_id in workers:
            # Find the household
            household = self.household_lookup.get(employee_id)
            if household is None:
                # Employee not found (shouldn't happen, but handle gracefully)
                total_productivity_multiplier += 1.0
                continue

            # Base multiplier is 1.0
            productivity_multiplier = 1.0

            # Add skill bonus (max 25% for skills_level = 1.0)
            skill_bonus = household.skills_level * 0.25

            # Add experience bonus (5% per year, capped at 50%)
            experience_ticks = household.category_experience.get(firm.good_category, 0)
            experience_years = experience_ticks / 52.0
            experience_bonus = min(experience_years * 0.05, 0.5)

            # Add wellbeing performance bonus (happiness/morale/health)
            # Performance multiplier ranges from 0.5x (low wellbeing) to 1.5x (high wellbeing)
            wellbeing_multiplier = household.get_performance_multiplier()

            # Combine all factors
            productivity_multiplier += skill_bonus + experience_bonus
            productivity_multiplier *= wellbeing_multiplier

            total_productivity_multiplier += productivity_multiplier

        # Calculate average productivity multiplier
        avg_productivity_multiplier = total_productivity_multiplier / len(workers)

        # Apply government infrastructure multiplier
        # Government infrastructure investment boosts all productivity economy-wide
        avg_productivity_multiplier *= self.government.infrastructure_productivity_multiplier
        # A random supply shock's temporary productivity change (B26).
        avg_productivity_multiplier *= firm.supply_shock_multiplier

        # Apply to planned production
        # Cap at production capacity
        worker_capacity = firm._capacity_for_workers(len(workers))
        actual_production = min(
            planned_production_units * avg_productivity_multiplier,
            firm.production_capacity_units,
            worker_capacity
        )

        return actual_production

    def _payment_collect_pending_services_exit_tax(self, firm: FirmAgent, amount: float) -> float:
        """Tax a completed project's receipt on exit before paying creditors."""
        snapshot = {"firm_id": firm.firm_id, "profit_before_tax": max(0.0, amount),
                    "cash_balance": max(0.0, firm.cash_balance), "good_category": firm.good_category,
                    "property_tax_rate": 0.0, "max_rental_units": 0, "price": firm.price}
        proposed = self.government.plan_taxes([], [snapshot])["profit_taxes"].get(firm.firm_id, 0.0)
        tax = min(max(0.0, firm.cash_balance), max(0.0, proposed))
        firm.cash_balance -= tax
        self.government.cash_balance += tax
        return tax

    def _payment_settle_exit_creditors(self, firm: FirmAgent, registered: list[dict]) -> None:
        """After worker claims, divide remaining cash among actual funders."""
        from payment_loans import settle_firm_exit_claim
        direct = max(0.0, firm.government_loan_remaining)
        mortgages = list(firm.housing_active_loans)
        claims = [("registered", loan, float(loan.get("remaining", 0.0)))
                  for loan in registered if float(loan.get("remaining", 0.0)) > MONEY_EPS]
        claims += [("mortgage", loan, max(0.0, loan.principal_remaining)
                    + (min(loan.principal_remaining * loan.origination_tick_rate, loan.pmt_per_tick)
                       if loan.last_missed_tick == self.current_tick else 0.0))
                   for loan in mortgages if loan.principal_remaining > MONEY_EPS]
        if direct > MONEY_EPS:
            claims.append(("treasury", None, direct))
        outstanding = sum(due for _, _, due in claims)
        budget = min(max(0.0, firm.cash_balance), outstanding)
        ratio = budget / outstanding if outstanding > MONEY_EPS else 0.0
        for kind, claim, due in claims:
            paid = min(due, due * ratio, max(0.0, firm.cash_balance))
            if kind == "registered":
                settle_firm_exit_claim(self, firm, claim, paid)
            elif kind == "mortgage":
                firm.cash_balance -= paid
                if self.bank is not None:
                    self.bank.cash_reserves += paid
                    self.bank.last_tick_repayments += paid
                    self.bank.loan_loss_provision += max(0.0, due - paid)
                    self.bank.last_tick_defaults += max(0.0, due - paid)
                claim.principal_remaining = 0.0
            else:
                firm.cash_balance -= paid
                self.government.cash_balance += paid
                self.payment_state["direct_treasury_exit_writeoffs"] = (
                    self.payment_state.get("direct_treasury_exit_writeoffs", 0.0) + max(0.0, due - paid))
        firm.government_loan_remaining = 0.0
        firm.loan_payment_per_tick = 0.0
        firm.housing_active_loans = []
        if firm.cash_balance > MONEY_EPS and firm.owners:
            owners = sorted(set(firm.owners))
            owners = [hid for hid in owners if hid in self.household_lookup]
            if owners:
                per_owner = firm.cash_balance / len(owners)
                for hid in owners:
                    self.household_lookup[hid].cash_balance += per_owner
                    self.household_lookup[hid].add_ledger_flow("other", per_owner)
                firm.cash_balance = 0.0
        if firm.cash_balance > MONEY_EPS:
            # Ownerless residual still has a recipient; it cannot vanish on exit.
            residual = firm.cash_balance
            firm.cash_balance = 0.0
            self._collect_misc_revenue(residual)

    def _handle_firm_exits(self) -> int:
        """
        Remove bankrupt firms from the economy.

        Firms with negative cash below a threshold are removed.
        Their employees are laid off.

        Mutates state.
        """
        bankruptcy_threshold = CONFIG.market.bankruptcy_threshold
        zero_cash_max_streak = CONFIG.market.zero_cash_max_streak
        registered_by_firm = {}
        if self.payment_sequence != "legacy" and self.bank is not None:
            for loan in self.bank.active_loans:
                if loan.get("borrower_type") == "firm":
                    registered_by_firm.setdefault(loan["borrower_id"], []).append(loan)
        workers_by_firm = {}
        if self.payment_sequence != "legacy":
            for (fid, hid), amount in self.payment_state["wage_claims"].items():
                workers_by_firm.setdefault(fid, {})[hid] = amount

        firms_to_remove = []
        for firm in self.firms:
            if firm.cash_balance < bankruptcy_threshold or firm.zero_cash_streak >= zero_cash_max_streak:
                # Protect government baseline firms at all times
                if self.government.is_baseline_firm(firm.firm_id):
                    continue

                if self.payment_sequence != "legacy":
                    if self.config.payment_services_project_enabled:
                        from payment_government import settle_payment_services_exit
                        settle_payment_services_exit(self, firm)
                    claims = self.payment_state["wage_claims"]
                    due = workers_by_firm.get(firm.firm_id, {})
                    recovered = proportional(due, max(0.0, firm.cash_balance))
                    for hid, amount in due.items():
                        paid = recovered.get(hid, 0.0)
                        if paid > MONEY_EPS:
                            self.payment_state["recovery_holds"][hid] = self.payment_state["recovery_holds"].get(hid, 0.0) + paid
                        claims.pop((firm.firm_id, hid), None)
                    firm.cash_balance -= sum(recovered.values())
                    self.payment_book.exit_recovery = getattr(self.payment_book, "exit_recovery", 0.0) + sum(recovered.values())
                    self.payment_book.exit_worker_writeoff = getattr(self.payment_book, "exit_worker_writeoff", 0.0) + max(0.0, sum(due.values()) - sum(recovered.values()))
                    self._payment_settle_exit_creditors(firm, registered_by_firm.get(firm.firm_id, []))

                # Firm is bankrupt - lay off all employees
                for employee_id in firm.employees:
                    # Find household and unemploy them (O(1) lookup via cache)
                    household = self.household_lookup.get(employee_id)
                    if household is not None:
                        household.employer_id = None
                        household.wage = 0.0

                firms_to_remove.append(firm)
                self._append_regime_event(
                    event_type="firm_bankrupt",
                    entity_type="firm",
                    entity_id=firm.firm_id,
                    sector=firm.good_category,
                    reason_code="zero_cash_streak" if firm.zero_cash_streak >= zero_cash_max_streak else "cash_threshold",
                    severity=float(max(abs(firm.cash_balance), firm.zero_cash_streak)),
                    metric_value=float(firm.cash_balance),
                )

        # A dead landlord cannot collect a following tick's rent or influence
        # the household's deposit quote and care affordability calculation.
        if self.payment_sequence != "legacy":
            exiting_care = {firm.firm_id for firm in firms_to_remove
                            if (firm.good_category or "").lower() == "healthcare"}
            if exiting_care:
                for household in self.households:
                    if household.queued_healthcare_firm_id in exiting_care:
                        household.queued_healthcare_firm_id = None
                        household.healthcare_queue_enter_tick = -1
                        household.payment_care_due_retry = True
            exiting_housing = {firm.firm_id for firm in firms_to_remove
                               if (firm.good_category or "").lower() == "housing"}
            if exiting_housing:
                for household in self.households:
                    if household.renting_from_firm_id in exiting_housing:
                        household.renting_from_firm_id = None
                        household.owns_housing = False
                        household.monthly_rent = 0.0
                        household.rent_arrears = 0.0
                        household.rent_notice_remaining = 0
                for firm in firms_to_remove:
                    if firm.firm_id in exiting_housing:
                        firm.current_tenants.clear()
                        firm.rent_arrears_receivable_by_tenant.clear()
        # Remove bankrupt firms
        for firm in firms_to_remove:
            if self.payment_sequence != "legacy":
                from payment_projects import cancel_payment_projects_for_exit
                cancel_payment_projects_for_exit(self, firm)
            self.firms.remove(firm)

            # Clean up tracking dictionaries
            if firm.firm_id in self.last_tick_sales_units:
                del self.last_tick_sales_units[firm.firm_id]
            self.last_tick_unmet_demand_by_firm.pop(firm.firm_id, None)
            self.current_tick_unmet_demand_by_firm.pop(firm.firm_id, None)
            if firm.firm_id in self.last_tick_revenue:
                del self.last_tick_revenue[firm.firm_id]
            if firm.firm_id in self.last_tick_sell_through_rate:
                del self.last_tick_sell_through_rate[firm.firm_id]

            # Clean up firm cache
            if firm.firm_id in self.firm_lookup:
                del self.firm_lookup[firm.firm_id]

            # Write off bank loans on bankruptcy
            if self.bank is not None and self.payment_sequence == "legacy":
                for loan in list(self.bank.loans_for("firm", firm.firm_id)):
                    self.bank.write_off_loan(loan)
                    self.bank.update_firm_credit_score(firm.firm_id, -0.20)

        if firms_to_remove and self.bank is not None and self.payment_sequence != "legacy":
            exited_ids = {firm.firm_id for firm in firms_to_remove}
            self.bank.active_loans = [loan for loan in self.bank.active_loans
                                      if not (loan.get("borrower_type") == "firm"
                                              and loan.get("borrower_id") in exited_ids)]

        return len(firms_to_remove)

    def _sector_demand_signal(self, category: str) -> float:
        """Return a [0, 1] demand signal for a sector.

        1.0 = extreme undersupply (all firms selling everything instantly).
        0.0 = glut (firms can't sell anything).
        Based on mean sell-through rate of non-baseline firms in the sector.
        """
        rates = [
            self.last_tick_sell_through_rate.get(f.firm_id, 0.5)
            for f in self.firms
            if f.good_category == category and not f.is_baseline
        ]
        if not rates:
            # No private firms in sector yet — moderate demand assumed
            return 0.6
        return max(0.0, min(1.0, sum(rates) / len(rates)))

    def _maybe_create_new_firms(self) -> None:
        """Create new firms when the economy has room, using a 3-tier funding model.

        Tiers:
          1. Bootstrapped (~65%): small random capital $5K-$30K, no loan.
             Cheap, disposable — market filters winners from losers.
          2. Bank-backed (~25%): seed loan from bank when the sector shows
             unmet demand (high sell-through). Uses credit score + demand signal.
          3. Government-backed (~10%): subsidized loan through bank during
             high unemployment or critical sector undersupply.

        Note:
            SOLID VIOLATION - Single Responsibility Principle (SRP):
            This method has multiple responsibilities (~200 lines):
            1. Sector selection logic (food vs services vs housing)
            2. Firm personality and quality determination
            3. Funding tier selection (3 tiers with different logic each)
            4. Firm creation and initialization
            5. Loan origination through multiple channels
            Consider extracting: _select_sector(), _determine_firm_params(),
            _select_funding_tier(), _create_firm_with_funding().

            SOLID VIOLATION - Open/Closed Principle (OCP):
            Adding a new funding tier requires modifying the if/elif/else chain
            and the tier selection logic. Should use a strategy pattern for tiers.

            SOLID VIOLATION - Dependency Inversion Principle (DIP):
            Direct dependency on BankAgent and GovernmentAgent for loans.
            Should depend on abstractions (e.g., LoanProvider interface).
        """
        if self.in_warmup:
            return

        if len(self.firms) + len(self.queued_firms) >= self.target_total_firms:
            return

        # Only the legacy tiers read total household cash (gate and seed sizes).
        if self.payment_sequence == "legacy":
            total_household_cash = sum(h.cash_balance for h in self.households)
            if total_household_cash < 1000.0:
                return

        # ── choose sector ────────────────────────────────────────────

        existing_ids = [f.firm_id for f in self.firms]
        existing_ids.extend(f.firm_id for f in self.queued_firms)
        new_firm_id = max(existing_ids, default=0) + 1

        # Deterministic RNG for all stochastic choices in firm creation
        tier_rng = random.Random(CONFIG.random_seed + new_firm_id * 7919)

        total_units = sum(
            f.max_rental_units for f in self.firms
            if f.good_category == "Housing"
        )
        if total_units < len(self.households) and self.payment_sequence == "legacy":
            # Single-provider Housing model: expand existing rather than spawn
            housing_firms = [f for f in self.firms if f.good_category == "Housing"]
            if housing_firms:
                expansion = max(50, int(len(self.households) * 0.05))
                housing_firms[0].max_rental_units += expansion
                housing_firms[0].production_capacity_units = float(housing_firms[0].max_rental_units)
                housing_firms[0].expected_sales_units = float(housing_firms[0].max_rental_units)
            return
        else:
            food_unmet = max(0.0, self.food_unmet_demand)
            services_unmet = max(0.0, self.services_unmet_demand)

            # Count private (non-baseline) firms per sector.
            food_private = sum(1 for f in self.firms if f.good_category == "Food" and not f.is_baseline)
            services_private = sum(1 for f in self.firms if f.good_category == "Services" and not f.is_baseline)

            # Boost under-served sectors: a monopoly sector suppresses its own
            # demand signal (high price → nobody buys → unmet_demand ≈ 0), so
            # pure demand weighting never spawns a competitor. Weight each sector
            # by (1 + 1/private_count) so sectors with fewer competitors score
            # higher even when observed demand appears low.
            food_score = food_unmet * (1.0 + 1.0 / max(1, food_private))
            services_score = services_unmet * (1.0 + 1.0 / max(1, services_private))
            total_score = food_score + services_score

            if total_score == 0.0:
                # No demand signal at all — pick the more under-served sector
                chosen_category = "Services" if services_private <= food_private else "Food"
            else:
                food_prob = food_score / total_score
                chosen_category = "Food" if tier_rng.random() < food_prob else "Services"

        # ── personality & quality ────────────────────────────────────

        personality_index = new_firm_id % 3
        personality = ("aggressive", "conservative", "moderate")[personality_index]

        category_qualities = [f.quality_level for f in self.firms if f.good_category == chosen_category]
        median_quality = np.median(category_qualities) if category_qualities else 5.0

        ceo_id = None
        if self.current_tick > self.warmup_ticks and self.households:
            ceo_id = tier_rng.choice([h.household_id for h in self.households])

        max_rental_units = 0
        property_tax_rate = 0.0

        # ── select funding tier ──────────────────────────────────────

        demand_signal = self._sector_demand_signal(chosen_category)
        unemployed_count = sum(1 for h in self.households if not h.is_employed)
        unemployment_rate = unemployed_count / max(1, len(self.households))
        tier_roll = tier_rng.random()  # [0, 1)

        # Shift thresholds based on conditions:
        # High unemployment → more govt-backed (tier 3)
        # High sector demand → more bank-backed (tier 2)
        govt_threshold = 0.05 + min(0.10, unemployment_rate * 0.3)  # 5-15%
        bank_threshold = govt_threshold + 0.15 + min(0.15, demand_signal * 0.2)  # +15-30%
        # Remainder is bootstrapped

        seed_cash = 0.0
        govt_loan_principal = 0.0
        govt_loan_remaining = 0.0
        govt_loan_payment = 0.0
        bank_loan_principal = 0.0
        bank_loan_remaining = 0.0
        bank_loan_payment = 0.0
        seed_term_ticks = 156  # 3 years
        founder_id = None

        if self.payment_sequence != "legacy":
            # Entry has no settled operating cashflow, so the bank's static
            # underwriting gate cannot authorize a new-firm seed claim. A
            # founder pays real equity above next week's known necessities;
            # an authorized Treasury seed remains an actual funded liability.
            requested = (30_000.0 if tier_roll < govt_threshold else
                         20_000.0 if tier_roll < bank_threshold else 5_000.0)
            prior_food = self.payment_state.get("prior_essential_food_cost", {})
            due_index = getattr(self.payment_book, "household_due_index", {})
            eligible = []
            for household in self.households:
                debt_due = due_index.get(household.household_id, 0.0)
                if isinstance(debt_due, list):
                    debt_due = sum(float(row[2]) for row in debt_due)
                reserve = (max(0.0, prior_food.get(household.household_id, 0.0))
                           + max(0.0, household.monthly_rent)
                           + max(0.0, debt_due))
                eligible.append((household, household.cash_balance - reserve))
            if tier_roll < govt_threshold and self._payment_free_treasury_cash() + MONEY_EPS >= requested:
                self.government.cash_balance -= requested
                seed_cash = requested
                govt_loan_principal = requested
                govt_loan_remaining = requested * 1.01
                govt_loan_payment = govt_loan_remaining / seed_term_ticks
            elif (funders := [(household, surplus) for household, surplus in eligible
                              if surplus + MONEY_EPS >= requested or surplus + MONEY_EPS >= 5_000.0]):
                founder, surplus = min(funders, key=lambda item: item[0].household_id)
                requested = requested if surplus + MONEY_EPS >= requested else 5_000.0
                founder_id = founder.household_id
                founder.cash_balance -= requested
                founder.add_ledger_flow("other", -requested)
                seed_cash = requested
            else:
                return
        elif tier_roll < govt_threshold:
            # ── Tier 3: Government-backed ────────────────────────────
            # Subsidized loan through bank or direct from government.
            seed_cash = min(100_000.0, max(30_000.0, total_household_cash * 0.01))
            seed_rate = 0.005  # Subsidized: 0.5% annual

            if self.bank is not None:
                loan = self.bank.issue_government_backed_loan(
                    "firm", new_firm_id, seed_cash, seed_rate,
                    seed_term_ticks, self.government,
                )
                if loan is not None:
                    bank_loan_principal = seed_cash
                    bank_loan_remaining = loan["remaining"]
                    bank_loan_payment = loan["payment_per_tick"]
                else:
                    # Government can't afford it — downgrade to bootstrapped
                    seed_cash = tier_rng.uniform(5_000.0, 30_000.0)
            elif self._payment_free_treasury_cash() > seed_cash:
                # No bank — direct government loan
                self.government.cash_balance -= seed_cash
                from payment_loans import v2_payment
                seed_rate_govt = 0.01
                govt_loan_payment = v2_payment(seed_cash, seed_rate_govt, seed_term_ticks,
                                               int(CONFIG.time.ticks_per_year))
                govt_loan_principal = seed_cash
                govt_loan_remaining = govt_loan_payment * seed_term_ticks
            else:
                # Government broke — downgrade to bootstrapped
                seed_cash = tier_rng.uniform(5_000.0, 30_000.0)

        elif tier_roll < bank_threshold:
            # ── Tier 2: Bank-backed ──────────────────────────────────
            # Bank seed loan based on sector demand + default credit score.
            seed_cash = min(80_000.0, max(20_000.0, total_household_cash * 0.008))

            if self.bank is not None and self.bank.can_lend():
                credit_score = self.bank.get_firm_credit_score(new_firm_id)  # 0.5 default
                # Require minimum demand signal to justify bank lending
                if demand_signal >= 0.4 and self.bank.lendable_cash >= seed_cash:
                    rate = self.bank._risk_adjusted_rate(credit_score, spread=0.04)
                    loan = self.bank.originate_loan("firm", new_firm_id, seed_cash, rate, seed_term_ticks)
                    bank_loan_principal = seed_cash
                    bank_loan_remaining = loan["remaining"]
                    bank_loan_payment = loan["payment_per_tick"]
                else:
                    # Bank won't fund — downgrade to bootstrapped
                    seed_cash = tier_rng.uniform(5_000.0, 30_000.0)
            else:
                # No bank or circuit breaker — bootstrapped
                seed_cash = tier_rng.uniform(5_000.0, 30_000.0)

        else:
            # ── Tier 1: Bootstrapped (majority) ──────────────────────
            seed_cash = tier_rng.uniform(5_000.0, 30_000.0)

        # ── create the firm ──────────────────────────────────────────

        if chosen_category == "Services":
            initial_inventory_units = 0.0
            initial_production_capacity_units = 5.0
            initial_units_per_worker = CONFIG.firms.services_units_per_worker_range[1]
        else:
            initial_inventory_units = 0.0 if chosen_category in {"Housing", "Healthcare"} else 100.0
            initial_production_capacity_units = (
                float(max_rental_units) if chosen_category == "Housing" else 500.0
            )
            initial_units_per_worker = 18.0

        new_firm = FirmAgent(
            firm_id=new_firm_id,
            good_name=f"{chosen_category}Product{new_firm_id}",
            cash_balance=seed_cash,
            inventory_units=initial_inventory_units,
            good_category=chosen_category,
            quality_level=min(10.0, max(1.0, median_quality + tier_rng.uniform(-1.0, 1.0))),
            wage_offer=35.0,
            price=150.0 if chosen_category == "Housing" else 8.0,
            expected_sales_units=50.0 if chosen_category != "Housing" else float(max_rental_units),
            production_capacity_units=initial_production_capacity_units,
            productivity_per_worker=10.0,
            units_per_worker=initial_units_per_worker,
            personality=personality,
            government_loan_principal=govt_loan_principal,
            government_loan_remaining=govt_loan_remaining,
            loan_payment_per_tick=govt_loan_payment,
            bank_loan_principal=bank_loan_principal,
            bank_loan_remaining=bank_loan_remaining,
            bank_loan_payment_per_tick=bank_loan_payment,
            ceo_household_id=ceo_id,
            max_rental_units=max_rental_units,
            property_tax_rate=property_tax_rate,
            # Fix 21: seed new firms with initial capital stock
            capital_stock=float(CONFIG.firms.initial_firm_capital),
            capital_depreciation_rate=CONFIG.firms.capital_depreciation_rate,
            capital_cost_per_unit=CONFIG.firms.capital_cost_per_unit,
        )
        new_firm.set_personality(personality)
        if founder_id is not None:
            new_firm.owners = [founder_id]

        self.firms.append(new_firm)

        self.last_tick_sales_units[new_firm_id] = 0.0
        self.last_tick_revenue[new_firm_id] = 0.0
        self.last_tick_sell_through_rate[new_firm_id] = 0.5
        self.last_tick_unmet_demand_by_firm[new_firm_id] = 0.0
        self.last_tick_prices[new_firm.good_name] = new_firm.price

        self.firm_lookup[new_firm_id] = new_firm

    # -------------------------------------------------------------------------
    # Section: Loan programs and capital financing
    # -------------------------------------------------------------------------
    def _update_loan_commitments(self) -> None:
        """Tick down hiring commitments tied to emergency loans and reclaim aid if ignored."""
        config = CONFIG.government
        for firm in self.firms:
            if firm.loan_required_headcount <= 0:
                continue

            if firm.loan_support_ticks > 0:
                firm.loan_support_ticks = max(0, firm.loan_support_ticks - 1)
                # If the firm has already met the requirement, clear the commitment early
                if len(firm.employees) >= firm.loan_required_headcount:
                    firm.loan_required_headcount = 0
                    firm.loan_support_ticks = 0
                continue

            # Commitment window expired. If requirement still unmet, claw back remaining aid.
            if len(firm.employees) >= firm.loan_required_headcount:
                firm.loan_required_headcount = 0
                firm.loan_support_ticks = 0
                continue

            reclaimable = min(
                firm.cash_balance,
                firm.government_loan_remaining * config.emergency_loan_penalty_reclaim_fraction
            )
            if reclaimable > 0:
                firm.cash_balance -= reclaimable
                firm.government_loan_remaining = max(0.0, firm.government_loan_remaining - reclaimable)
                self.government.cash_balance += reclaimable

            firm.loan_required_headcount = 0
            firm.loan_support_ticks = 0

    def _issue_firm_loan(
        self,
        firm: "FirmAgent",
        amount: float,
        term_ticks: int,
        govt_rate: float,
        spread: float = 0.05,
        collateral_value: Optional[float] = None,
        purpose: str = "investment",
    ) -> float:
        """Try bank first, then government-backed bank loan, then direct government loan.

        Returns the amount credited to the firm (0.0 when no channel lends). A
        legacy bank loan can fund less than ``amount`` (the leverage ceiling).
        This is the central bank-first/govt-fallback pattern used by all loan
        origination methods.

        Args:
            collateral_value: If provided, use LTV-based (asset-backed) lending ceiling
                instead of the default revenue-based leverage ceiling.  Used for housing
                expansion loans where the collateral is the property portfolio, not income.
        """
        bank = self.bank

        if self.payment_sequence != "legacy":
            if firm.payment_wage_arrears > MONEY_EPS and purpose != "working_capital":
                return 0.0
            if bank is not None:
                from payment_loans import originate_v2
                if collateral_value is not None:
                    max_borrowable = max(0.0, 0.80 * collateral_value - bank._firm_existing_debt(firm.firm_id))
                else:
                    max_borrowable = bank._max_firm_borrowable(firm.firm_id, firm.trailing_revenue_12t)
                # Full-purpose funding only; a partial loan cannot authorize
                # the advertised capital purchase or wage cure.
                if max_borrowable + MONEY_EPS >= amount:
                    score = bank.get_firm_credit_score(firm.firm_id)
                    rate = bank._risk_adjusted_rate(score, spread)
                    claim = originate_v2(self, "firm", firm.firm_id, amount, rate,
                                         term_ticks, purpose, funder="bank")
                    if claim is not None:
                        firm.cash_balance += amount
                        return amount
            # Direct treasury claim stays outside the registered bank book.
            if self._payment_free_treasury_cash() + MONEY_EPS < amount:
                return 0.0
            rate = 0.03 if govt_rate is None else govt_rate
            due = amount * (1.0 + rate)
            firm.cash_balance += amount
            firm.government_loan_principal += amount
            firm.government_loan_remaining += due
            firm.loan_payment_per_tick += due / max(1, term_ticks)
            self.government.cash_balance -= amount
            return amount

        if bank is not None:
            credit_score = bank.get_firm_credit_score(firm.firm_id)

            # Leverage ceiling: asset-backed (LTV) or revenue-based
            if collateral_value is not None:
                # Property-backed lending: bank lends up to 80% of collateral value
                ltv = 0.80
                max_borrowable = max(0.0, ltv * collateral_value - bank._firm_existing_debt(firm.firm_id))
            else:
                max_borrowable = bank._max_firm_borrowable(firm.firm_id, firm.trailing_revenue_12t)
            effective_amount = min(amount, max_borrowable)
            if effective_amount <= 0:
                # Over-leveraged — fall through to government
                pass
            elif credit_score < 0.25:
                # Credit too low for bank — fall through to government
                pass
            elif bank.can_lend() and bank.lendable_cash >= effective_amount:
                # Bank can fund it directly
                rate = bank._risk_adjusted_rate(credit_score, spread)
                loan = bank.originate_loan("firm", firm.firm_id, effective_amount, rate, term_ticks)
                firm.cash_balance += effective_amount
                firm.bank_loan_principal += effective_amount
                firm.bank_loan_remaining += loan["remaining"]
                firm.bank_loan_payment_per_tick += loan["payment_per_tick"]
                return effective_amount
            else:
                # Circuit breaker active — try government-backed loan through bank
                rate = bank._risk_adjusted_rate(credit_score, spread)
                loan = bank.issue_government_backed_loan(
                    "firm", firm.firm_id, effective_amount, rate,
                    term_ticks, self.government,
                )
                if loan is not None:
                    firm.cash_balance += effective_amount
                    firm.bank_loan_principal += effective_amount
                    firm.bank_loan_remaining += loan["remaining"]
                    firm.bank_loan_payment_per_tick += loan["payment_per_tick"]
                    return effective_amount

        # Fallback: direct government loan (existing behavior)
        if govt_rate is None:
            govt_rate = 0.03  # Default market rate for government direct loans
        # Government can only lend what it has
        if self._payment_free_treasury_cash() < amount:
            return 0.0
        # Amortized installment over the term, as bank loans charge (v2_payment).
        from payment_loans import v2_payment
        term = max(1, int(term_ticks))
        installment = v2_payment(amount, govt_rate, term, int(CONFIG.time.ticks_per_year))
        firm.cash_balance += amount
        firm.government_loan_principal += amount
        firm.government_loan_remaining += installment * term
        firm.loan_payment_per_tick += installment
        self.government.cash_balance -= amount
        return amount

    def _offer_investment_loans(self) -> None:
        """Phase 1.5: Process firm investment loan requests flagged in Phase 1.

        Firms that set needs_investment_loan=True during plan_capital_investment
        are processed here. On success, capital stock increases and firm cash
        pays for the capital purchase (the loan proceeds are the funding source).
        Recycling to households happens later in _recycle_capital_investment.
        """
        config = CONFIG.firms
        for firm in self.firms:
            if not firm.needs_investment_loan or firm.investment_loan_amount <= 0:
                continue

            loan_amount = firm.investment_loan_amount
            funded = self._issue_firm_loan(
                firm,
                amount=loan_amount,
                term_ticks=104,       # 2-year term
                govt_rate=0.04,
                spread=0.04,
            )
            if funded > 0.0:
                # _issue_firm_loan added the funded amount to firm cash (a
                # legacy bank loan can fund less than requested); spend only that.
                units_gained = funded / config.capital_cost_per_unit
                firm.capital_stock += units_gained
                firm.cash_balance -= funded
                firm.capital_investment_this_tick += units_gained
                if self.payment_sequence != "legacy":
                    self._payment_record_capital_spend(firm, funded, "investment_loan")
                # Record the rate for future MPK calculations
                if self.bank is not None:
                    score = self.bank.get_firm_credit_score(firm.firm_id)
                    firm.current_loan_rate = self.bank._risk_adjusted_rate(score, 0.04)

            firm.needs_investment_loan = False
            firm.investment_loan_amount = 0.0

    def _maybe_offer_long_term_capital_loan(
        self,
        firm: "FirmAgent",
        health_snapshot: "FirmHealthSnapshot",
        unemployment_rate: float,
        total_households: int,
    ) -> bool:
        """Long-term low-interest capital expansion loan for services + housing only.

        Real-economy framing: SBA-style equipment / construction financing. Long
        term so per-tick burden is small. Services firms use it to lift
        production_capacity_units (more workers fit, more output). Housing
        firms use it to add max_rental_units (construction); staff scales
        automatically via the housing branch in plan_production_and_labor.

        Eligibility (services):
          - sustained stockout streak OR sustained high sell-through
          - marginal worker has positive MRPL

        Eligibility (housing):
          - max_rental_units < total_households (real shortage)
          - occupancy >= 80% (proves demand for existing stock)

        Money flow: bank lends; loan amount routed through capital_investment
        recycle so households receive it as construction wages. Conservation
        preserved.
        """
        cfg = CONFIG.firms

        if not bool(getattr(cfg, "long_term_capital_loans_enabled", True)):
            return False
        if firm.is_baseline:
            return False
        if self.payment_sequence != "legacy" and firm.payment_wage_arrears > MONEY_EPS:
            return False
        category = (firm.good_category or "").lower()
        if category not in {"services", "housing"}:
            return False
        if unemployment_rate < float(cfg.long_term_capital_unemployment_trigger):
            return False
        if (int(self.current_tick) - int(firm.last_long_term_loan_tick)) < int(
            cfg.long_term_capital_cooldown_ticks
        ):
            return False

        bank = self.bank
        if bank is None or not bank.can_lend():
            return False

        loan_amount = 0.0
        if category == "services":
            sustained_demand = (
                int(getattr(firm, "lost_sales_streak", 0) or 0) >= 5
                or float(health_snapshot.sell_through_rate) >= 0.85
            )
            if not sustained_demand:
                return False
            # MRPL check — adding capacity must justify wage cost.
            try:
                _, _, margin = firm._marginal_worker_economics()
            except AttributeError:
                marginal_units = max(0.0, float(firm.productivity_per_worker))
                margin = marginal_units * float(firm.price) - float(firm.wage_offer)
            if margin <= 0.0:
                return False
            current_capacity = max(1.0, float(firm.production_capacity_units))
            target_units_added = min(
                current_capacity * 0.5,  # at most 50% expansion at once
                float(cfg.long_term_capital_max_amount) / float(cfg.services_capacity_cost_per_unit),
            )
            loan_amount = max(
                float(cfg.long_term_capital_min_amount),
                target_units_added * float(cfg.services_capacity_cost_per_unit),
            )

        elif category == "housing":
            current_units = int(firm.max_rental_units)
            if total_households > 0 and current_units >= total_households:
                return False  # already enough rental capacity for population
            if current_units > 0:
                occupancy_rate = len(firm.current_tenants) / float(current_units)
                if occupancy_rate < 0.80:
                    return False
            max_units_to_add = min(
                max(1, int(current_units * 0.5)),  # at most 50% expansion
                int(cfg.long_term_capital_max_amount / (
                    CONFIG.payment_construction_unit_cost if self.payment_sequence != "legacy"
                    else cfg.housing_rental_unit_construction_cost)),
            )
            if max_units_to_add < 1:
                return False
            if self.payment_sequence != "legacy":
                from payment_projects import can_start_housing_project, project_quote
                max_units_to_add = min(max_units_to_add, int(CONFIG.payment_construction_project_cap))
                if not can_start_housing_project(self, firm, max_units_to_add, "long_term"):
                    return False
                loan_amount = project_quote(max_units_to_add)
            else:
                loan_amount = max(
                    float(cfg.long_term_capital_min_amount),
                    max_units_to_add * float(cfg.housing_rental_unit_construction_cost),
                )

        if category == "housing" and self.payment_sequence != "legacy":
            if loan_amount > float(cfg.long_term_capital_max_amount):
                return False
        else:
            loan_amount = min(float(cfg.long_term_capital_max_amount), loan_amount)

        if bank.lendable_cash < loan_amount:
            return False

        # Originate the loan.
        score = bank.get_firm_credit_score(firm.firm_id)
        rate = float(cfg.long_term_capital_annual_rate) + (1.0 - score) * 0.02
        if self.payment_sequence != "legacy":
            from payment_loans import originate_v2
            loan = originate_v2(self, "firm", firm.firm_id, loan_amount, rate,
                                int(cfg.long_term_capital_term_ticks), "long_term_capital")
            if loan is None:
                return False
        else:
            loan = bank.originate_loan(
                borrower_type="firm",
                borrower_id=firm.firm_id,
                principal=loan_amount,
                annual_rate=rate,
                term_ticks=int(cfg.long_term_capital_term_ticks),
                govt_backed=False,
            )
            loan["subtype"] = "long_term_capital"
            # Borrower mirrors, as for other legacy bank loans (originate_v2 does this itself).
            firm.bank_loan_principal += loan_amount
            firm.bank_loan_remaining += loan["remaining"]
            firm.bank_loan_payment_per_tick += loan["payment_per_tick"]

        # Apply expansion to the firm's productive capacity.
        if category == "services":
            if self.payment_sequence != "legacy":
                # The registered principal is bank cash until it is delivered
                # to this borrower and spent on this one capital route.
                firm.cash_balance += loan_amount
                firm.cash_balance -= loan_amount
                self._payment_record_capital_spend(firm, loan_amount, "long_term_services")
            capacity_added = loan_amount / float(cfg.services_capacity_cost_per_unit)
            firm.production_capacity_units = float(firm.production_capacity_units) + capacity_added
            firm.capital_stock += capacity_added
        elif category == "housing":
            if self.payment_sequence != "legacy":
                from payment_projects import register_funded_housing_project
                firm.cash_balance += loan_amount
                if not register_funded_housing_project(self, firm, max_units_to_add, "long_term", loan_id=loan.get("claim_id") or f"longterm-{firm.firm_id}-{self.current_tick}"):
                    raise RuntimeError("Funded long-term housing loan could not register project")
            else:
                units_added = int(loan_amount / float(cfg.housing_rental_unit_construction_cost))
                firm.max_rental_units = int(firm.max_rental_units) + units_added

        # Money flow: route loan amount through capital_investment_this_tick so
        # the existing _recycle_capital_investment phase distributes it to
        # households as construction wages. Preserves money conservation.
        capital_units_for_recycle = loan_amount / float(cfg.capital_cost_per_unit)
        if category != "housing" or self.payment_sequence == "legacy":
            firm.capital_investment_this_tick = float(firm.capital_investment_this_tick) + capital_units_for_recycle

        firm.last_long_term_loan_tick = int(self.current_tick)
        firm.total_long_term_loans_received = (
            float(getattr(firm, "total_long_term_loans_received", 0.0)) + loan_amount
        )

        firm.decision_diagnostics["long_term_capital_loan_received"] = float(loan_amount)
        firm.decision_diagnostics["long_term_capital_category"] = category
        firm.decision_diagnostics["long_term_capital_rate"] = float(rate)

        return True

    @staticmethod
    def _compute_housing_pmt(principal: float, annual_rate: float, term_ticks: int) -> float:
        """Amortizing PMT: P * r*(1+r)^N / ((1+r)^N - 1).  r = annual_rate/52."""
        r = annual_rate / 52.0
        if r <= 0.0 or term_ticks <= 0:
            return principal / max(1, term_ticks)
        factor = (1.0 + r) ** term_ticks
        return principal * r * factor / (factor - 1.0)

    def _service_housing_mortgage_debt(self) -> None:
        """Amortizing debt service for housing expansion loans.

        Each tick every active LoanContract on a housing firm pays its PMT.
        Interest portion → bank.last_tick_interest_income; principal portion
        reduces the remaining balance.  Fully amortized contracts are dropped.
        Mirrors firm legacy fields for distress detection compatibility.
        """
        bank = self.bank
        if bank is None:
            return
        registered_by_firm = {}
        if self.payment_sequence != "legacy":
            for loan in bank.active_loans:
                if loan.get("borrower_type") == "firm" and loan.get("remaining", 0.0) > MONEY_EPS:
                    registered_by_firm.setdefault(loan["borrower_id"], []).append(loan)
        for firm in self.firms:
            if not firm.housing_active_loans:
                continue
            surviving: list[LoanContract] = []
            total_pmt = 0.0
            records = ({r["claim_id"]: r for r in bank.loans_for("firm", firm.firm_id)
                        if r.get("subtype") == "housing_mortgage"}
                       if self.payment_sequence == "legacy" else {})
            for loan in firm.housing_active_loans:
                interest_due = min(loan.principal_remaining * loan.origination_tick_rate, loan.pmt_per_tick)
                record = records.get(loan.claim_id) if loan.claim_id else None
                if record is not None:
                    # Legacy mortgage on the bank ledger: pay through the record,
                    # capped at what is owed; mirrors move by what is paid.
                    due = min(loan.pmt_per_tick, record["remaining"])
                    if firm.cash_balance < due:
                        surviving.append(loan)
                        continue
                    paid = bank.collect_repayment(record, due, self.government)
                    firm.cash_balance -= paid
                    firm.bank_loan_remaining = max(0.0, firm.bank_loan_remaining - paid)
                    loan.principal_remaining = max(0.0, loan.principal_remaining - max(0.0, paid - interest_due))
                    loan.ticks_remaining -= 1
                    if record["remaining"] > 1e-6:
                        surviving.append(loan)
                    else:
                        firm.bank_loan_payment_per_tick = max(
                            0.0, firm.bank_loan_payment_per_tick - loan.pmt_per_tick)
                    continue
                actual_due = (min(loan.pmt_per_tick, loan.principal_remaining + interest_due)
                              if self.payment_sequence != "legacy" else loan.pmt_per_tick)
                if firm.cash_balance < actual_due:
                    if self.payment_sequence != "legacy":
                        loan.missed_payments += 1
                        loan.last_missed_tick = self.current_tick
                    surviving.append(loan)
                    continue
                interest = interest_due
                principal_portion = actual_due - interest
                firm.cash_balance -= actual_due
                bank.cash_reserves += actual_due
                bank.last_tick_interest_income += interest
                loan.principal_remaining = max(0.0, loan.principal_remaining - principal_portion)
                loan.ticks_remaining -= 1
                if self.payment_sequence != "legacy":
                    loan.missed_payments = 0
                total_pmt += actual_due
                if loan.ticks_remaining > 0 and loan.principal_remaining > 0.01:
                    surviving.append(loan)
            firm.housing_active_loans = surviving
            # Mirror into legacy fields for distress detection
            total_remaining = sum(l.principal_remaining for l in firm.housing_active_loans)
            total_pmt_tick = sum(l.pmt_per_tick for l in firm.housing_active_loans)
            if self.payment_sequence != "legacy":
                firm.bank_loan_remaining = total_remaining + sum(
                    float(loan.get("remaining", 0.0)) for loan in registered_by_firm.get(firm.firm_id, ()))
            else:
                firm.bank_loan_remaining = max(firm.bank_loan_remaining - total_pmt, 0.0)
            # Legacy never overwrites this mirror: each mortgage adds its
            # installment at origination and removes it when it closes.
            if self.payment_sequence != "legacy" and firm.housing_active_loans:
                firm.bank_loan_payment_per_tick = total_pmt_tick + sum(
                    float(loan["payment_per_tick"]) for loan in registered_by_firm.get(firm.firm_id, ()))
            elif self.payment_sequence != "legacy":
                firm.bank_loan_payment_per_tick = sum(
                    float(loan["payment_per_tick"]) for loan in registered_by_firm.get(firm.firm_id, ())
                )

    def _offer_housing_expansion_loans(self) -> None:
        """Phase 6.6b: DSCR/LTV amortizing mortgage loans for housing unit expansion.

        Dual-path expansion:
        - Path A (self-funded): already handled in Phase 6.6a via invest_in_unit_expansion.
        - Path B (loan-funded): DSCR ≥ 1.20 and LTV ≤ 0.80 gates; amortizing 20-year PMT.
          Loan proceeds flow bank → firm → misc_firm_revenue (construction sink).
        """
        bank = self.bank
        if bank is None:
            return

        cfg = CONFIG.firms
        term_ticks = cfg.housing_loan_term_ticks
        min_dscr = cfg.housing_min_dscr
        max_ltv = cfg.housing_max_ltv
        vacancy_buf = cfg.housing_vacancy_buffer
        max_build = cfg.housing_max_build_per_tick
        unit_market_val = cfg.housing_unit_market_value

        annual_rate = bank.current_annual_rate
        # Tenants per housing firm, counted once on first use; loan issuance
        # below never changes tenancy.
        occupied_by_firm: Optional[Dict[int, int]] = None

        for firm in self.firms:
            if firm.good_category.lower() != "housing":
                continue
            if not firm.needs_housing_expansion_loan or firm.housing_expansion_loan_amount <= 0:
                continue
            if not bank.can_lend():
                firm.needs_housing_expansion_loan = False
                firm.housing_expansion_loan_amount = 0.0
                continue

            principal = firm.housing_expansion_loan_amount
            # Whole units the principal buys on the firm's own cost curve (audit A6);
            # invest_in_unit_expansion's request prices exactly one unit.
            units_to_build, cost = 0, 0.0
            while units_to_build < max_build:
                cost += firm.housing_unit_cost(firm.max_rental_units + units_to_build)
                if cost > principal * (1.0 + 1e-9):
                    break
                units_to_build += 1
            units_to_build = max(1, units_to_build)

            # LTV gate: total_debt / total_assets ≤ max_ltv
            total_assets = (firm.max_rental_units + units_to_build) * unit_market_val + firm.cash_balance
            existing_debt = sum(l.principal_remaining for l in firm.housing_active_loans)
            projected_debt = existing_debt + principal
            if total_assets > 0 and projected_debt / total_assets > max_ltv:
                firm.needs_housing_expansion_loan = False
                firm.housing_expansion_loan_amount = 0.0
                continue

            # DSCR gate: projected_revenue / projected_pmt ≥ min_dscr
            pmt = self._compute_housing_pmt(principal, annual_rate, term_ticks)
            projected_new_pmt = sum(l.pmt_per_tick for l in firm.housing_active_loans) + pmt
            if occupied_by_firm is None:
                occupied_by_firm = {}
                for h in self.households:
                    rid = h.renting_from_firm_id
                    if rid is not None:
                        occupied_by_firm[rid] = occupied_by_firm.get(rid, 0) + 1
            occupied = occupied_by_firm.get(firm.firm_id, 0)
            projected_units = firm.max_rental_units + units_to_build
            projected_rev = firm.price * min(occupied + units_to_build, projected_units) * vacancy_buf
            if projected_new_pmt > 0 and projected_rev / projected_new_pmt < min_dscr:
                firm.needs_housing_expansion_loan = False
                firm.housing_expansion_loan_amount = 0.0
                continue

            if bank.lendable_cash < principal:
                firm.needs_housing_expansion_loan = False
                firm.housing_expansion_loan_amount = 0.0
                continue

            # Issue amortizing mortgage. The bank record is the ledger (active
            # loans, outstanding, telemetry, exit write-off); the LoanContract
            # linked by claim_id services it (audit A6/A7).
            r_tick = annual_rate / 52.0
            record = bank.originate_loan("firm", firm.firm_id, principal, annual_rate, term_ticks)
            record["subtype"] = "housing_mortgage"
            record["claim_id"] = f"legacy-mortgage-{firm.firm_id}-{self.current_tick}"
            firm.cash_balance += principal
            contract = LoanContract(
                principal_remaining=principal,
                pmt_per_tick=record["payment_per_tick"],
                ticks_remaining=term_ticks,
                origination_tick_rate=r_tick,
                claim_id=record["claim_id"],
            )
            firm.housing_active_loans.append(contract)
            # Mirror into legacy distress-detection fields
            firm.bank_loan_principal += principal
            firm.bank_loan_remaining += record["remaining"]
            firm.bank_loan_payment_per_tick += record["payment_per_tick"]

            # Pay construction cost to misc firm (bank → firm → builder)
            firm.cash_balance -= principal
            self._collect_misc_revenue(principal)

            # Execute expansion
            for _ in range(units_to_build):
                firm.max_rental_units += 1
                firm.production_capacity_units += 1.0
                firm.expected_sales_units += 1.0
            # Constant rate once the firm builds; new units grow the taxed base (B29).
            firm.property_tax_rate = max(firm.property_tax_rate, cfg.housing_property_tax_rate)

            firm.needs_housing_expansion_loan = False
            firm.housing_expansion_loan_amount = 0.0

    @staticmethod
    def _service_slot_upgrade_gain(firm: FirmAgent) -> int:
        """Return employee slots gained by a Services infrastructure upgrade."""
        slots = max(1, int(firm.production_capacity_units))
        personality = (firm.personality or "").lower()
        if personality == "aggressive":
            growth_rate = 0.20
        elif personality == "conservative":
            growth_rate = 0.10
        else:
            growth_rate = 0.15
        return max(1, int(slots * growth_rate))

    def _offer_service_infrastructure_loans(self) -> None:
        """Originate bank-financed Services upgrades that add employee slots.

        Services ``production_capacity_units`` is worker slots, so the upgrade
        increases hiring capacity. Service units still come from workers each tick.
        """
        bank = self.bank
        if bank is None:
            return

        term_ticks = 104
        spread = 0.04

        for firm in self.firms:
            if (firm.good_category or "").lower() != "services":
                continue
            if not firm.needs_service_infrastructure_loan or firm.service_infrastructure_loan_amount <= 0.0:
                continue

            principal = float(firm.service_infrastructure_loan_amount)

            def clear_request() -> None:
                firm.needs_service_infrastructure_loan = False
                firm.service_infrastructure_loan_amount = 0.0

            if (
                firm.survival_mode
                or firm.zero_cash_streak > 0
                or firm.service_infrastructure_loan_remaining > 1e-6
                or (self.payment_sequence != "legacy" and firm.payment_wage_arrears > MONEY_EPS)
            ):
                clear_request()
                continue
            if not bank.can_lend() or bank.lendable_cash < principal:
                clear_request()
                continue

            credit_score = bank.get_firm_credit_score(firm.firm_id)
            if credit_score < 0.25:
                clear_request()
                continue

            annual_rate = bank._risk_adjusted_rate(credit_score, spread)
            # The installment the loan below will charge (amortized on both paths).
            from payment_loans import quoted_annual_rate, v2_payment
            quote = annual_rate if self.payment_sequence == "legacy" else quoted_annual_rate(self, annual_rate)
            projected_payment = v2_payment(principal, quote, term_ticks, int(self.config.time.ticks_per_year))
            wage_bill = max(0.0, float(firm._current_wage_bill()))
            rolling_revenue = max(0.0, float(max(firm.last_revenue, firm.revenue_ema)))
            projected_service_cost = wage_bill + firm.service_infrastructure_loan_payment_per_tick + projected_payment
            if rolling_revenue > 0.0 and projected_service_cost > 0.0:
                if rolling_revenue < projected_service_cost * 0.75:
                    clear_request()
                    continue

            if self.payment_sequence != "legacy":
                from payment_loans import originate_v2
                loan = originate_v2(self, "firm", firm.firm_id, principal, annual_rate,
                                    term_ticks, "service_infrastructure")
                if loan is None:
                    clear_request()
                    continue
            else:
                loan = bank.originate_loan(
                    borrower_type="firm",
                    borrower_id=firm.firm_id,
                    principal=principal,
                    annual_rate=annual_rate,
                    term_ticks=term_ticks,
                    govt_backed=False,
                )
                loan["subtype"] = "service_infrastructure"
                firm.bank_loan_principal += principal
                firm.bank_loan_remaining += loan["remaining"]
                firm.bank_loan_payment_per_tick += loan["payment_per_tick"]
                firm.service_infrastructure_loan_remaining += loan["remaining"]
                firm.service_infrastructure_loan_payment_per_tick += loan["payment_per_tick"]
            firm.cash_balance += principal

            firm.cash_balance -= principal
            self._collect_misc_revenue(principal)

            slots_gained = self._service_slot_upgrade_gain(firm)
            firm.production_capacity_units += float(slots_gained)
            firm.inventory_units = 0.0
            firm.service_full_utilization_streak = 0
            firm.decision_diagnostics["service_upgrade_slots_gained"] = slots_gained
            firm.decision_diagnostics["service_upgrade_loan_principal"] = principal
            firm.decision_diagnostics["service_upgrade_debt_service"] = loan["payment_per_tick"]
            clear_request()

    def _payment_record_capital_spend(self, firm: FirmAgent, amount: float, route: str) -> None:
        """Record an actual funded capital debit for its single phase-8.5 recipient."""
        if not math.isfinite(amount) or amount <= 0.0:
            raise ValueError("capital spending must be positive and finite")
        if self.payment_state.get("capital_routes_released", False):
            raise ValueError("capital spending route recorded after release")
        self.payment_state.setdefault("capital_routes", []).append(
            {"firm_id": firm.firm_id, "amount": amount, "route": route, "tick": self.current_tick})

    def _recycle_capital_investment(self) -> None:
        """Phase 8.5: Recycle capital investment spending back to households.

        Capital purchases are treated as payments to an implicit capital-goods
        sector that employs workers. This preserves money conservation: firm
        cash decreased (in plan_capital_investment or _offer_investment_loans),
        and household cash increases by the same aggregate amount.
        """
        if self.payment_sequence != "legacy" and self.payment_state.get("capital_routes_released", False):
            return
        total_investment = (sum(row["amount"] for row in self.payment_state.get("capital_routes", ()))
                            if self.payment_sequence != "legacy" else sum(
                                f.capital_investment_this_tick * CONFIG.firms.capital_cost_per_unit
                                for f in self.firms))
        if self.payment_sequence != "legacy":
            self.payment_state["capital_routes_released"] = True
        if total_investment <= 0.0 or not self.households:
            return
        per_household = total_investment / len(self.households)
        for hh in self.households:
            hh.cash_balance += per_household
            hh.add_ledger_flow("other", per_household)

    def _offer_consumption_loans(self) -> None:
        """Phase 2a: Process household consumption loan requests.

        Households with cash below subsistence set needs_consumption_loan in
        maybe_request_consumption_loan(). This method originates the loan and
        credits the household.
        """
        bank = self.bank
        if bank is None:
            return

        for hh in self.households:
            if not hh.needs_consumption_loan or hh.consumption_loan_amount <= 0:
                continue

            if not bank.can_lend():
                hh.needs_consumption_loan = False
                hh.consumption_loan_amount = 0.0
                continue

            score = bank.get_household_credit_score(hh.household_id)
            if score < 0.4:
                hh.needs_consumption_loan = False
                hh.consumption_loan_amount = 0.0
                continue

            amount = hh.consumption_loan_amount
            rate = bank.base_interest_rate + (1.0 - score) * 0.06
            term_ticks = 26  # 6 months

            if bank.lendable_cash >= amount:
                if self.payment_sequence != "legacy":
                    from payment_loans import originate_v2
                    loan = originate_v2(self, "household", hh.household_id, amount, rate,
                                        term_ticks, "consumption")
                    if loan is not None:
                        hh.cash_balance += amount
                        hh.add_ledger_flow("bank", amount)
                else:
                    loan = bank.originate_loan(
                        borrower_type="household",
                        borrower_id=hh.household_id,
                        principal=amount,
                        annual_rate=rate,
                        term_ticks=term_ticks,
                        govt_backed=False,
                    )
                    loan["subtype"] = "consumption"  # tag for repayment routing
                    hh.cash_balance += amount
                    hh.add_ledger_flow("bank", amount)
                    hh.consumption_loan_remaining += loan["remaining"]
                    hh.consumption_loan_payment_per_tick += loan["payment_per_tick"]

            hh.needs_consumption_loan = False
            hh.consumption_loan_amount = 0.0

    # -------------------------------------------------------------------------
    # Section: Bailouts, public works, stimulus, and shocks
    # -------------------------------------------------------------------------
    def _firm_matches_bailout_policy(self, firm: "FirmAgent") -> bool:
        """Return whether a firm matches the current bailout targeting rule."""
        policy = getattr(self.government, "bailout_policy", "off")
        target = getattr(self.government, "bailout_target", "none")
        category = (firm.good_category or "").lower()
        if policy == "all":
            return True
        if policy == "sector":
            return target != "none" and category == target
        return False

    def _is_bailout_candidate(self, firm: "FirmAgent") -> bool:
        """Return whether a private firm is genuinely distressed."""
        if firm.is_baseline or (firm.good_category or "").lower() == "publicworks":
            return False
        if int(getattr(firm, "age_in_ticks", 0)) < 3:
            return False

        wage_bill = firm._current_wage_bill()
        if wage_bill <= 0.0:
            return False

        payroll_coverage = max(0.0, firm.last_revenue) / max(wage_bill, 1.0)
        cash_runway_ticks = firm.cash_balance / max(wage_bill, 1.0)
        return (
            bool(getattr(firm, "survival_mode", False))
            or bool(getattr(firm, "burn_mode", False))
            or payroll_coverage < 0.75
            or cash_runway_ticks < (CONFIG.firms.survival_mode_runway_weeks * 2.0)
            or int(getattr(firm, "zero_cash_streak", 0)) > 0
        )

    def _bailout_need_amount(self, firm: "FirmAgent") -> float:
        """Estimate a modest bridge-loan amount for one distressed firm."""
        config = CONFIG.government
        wage_bill = firm._current_wage_bill()
        reserve_target = min(
            float(config.emergency_loan_cash_threshold),
            wage_bill * max(1.0, CONFIG.firms.survival_mode_runway_weeks),
        )
        payroll_gap = max(0.0, wage_bill - max(0.0, firm.last_revenue))
        cash_gap = max(0.0, reserve_target - firm.cash_balance)
        return min(float(config.emergency_loan_amount), max(payroll_gap, cash_gap))

    def _execute_bailouts(self) -> None:
        """Execute explicit government bailout loans under the active policy cycle."""
        gov = self.government
        policy = getattr(gov, "bailout_policy", "off")
        if policy == "off":
            self.bailout_denied_firms_by_reason["policy_off"] = self.bailout_denied_firms_by_reason.get("policy_off", 0) + len(self.firms)
            return
        if policy == "sector" and getattr(gov, "bailout_target", "none") == "none":
            self.bailout_denied_firms_by_reason["sector_policy_missing_target"] = (
                self.bailout_denied_firms_by_reason.get("sector_policy_missing_target", 0) + len(self.firms)
            )
            return

        reserve_floor = CONFIG.government.investment_reserve_threshold
        available_cash = max(0.0, self._payment_free_treasury_cash() - reserve_floor)
        available_budget = min(float(getattr(gov, "bailout_budget_remaining", 0.0)), available_cash)
        if available_budget <= 0.0:
            matching_firms = sum(1 for firm in self.firms if self._firm_matches_bailout_policy(firm))
            reason = "no_bailout_budget_remaining" if float(getattr(gov, "bailout_budget_remaining", 0.0)) <= 0.0 else "government_cash_reserve_floor"
            self.bailout_denied_firms_by_reason[reason] = self.bailout_denied_firms_by_reason.get(reason, 0) + matching_firms
            return

        candidate_firms = []
        for firm in self.firms:
            category = (getattr(firm, "good_category", "") or "unknown").lower()
            if not self._firm_matches_bailout_policy(firm):
                self.bailout_denied_firms_by_reason["policy_target_mismatch"] = (
                    self.bailout_denied_firms_by_reason.get("policy_target_mismatch", 0) + 1
                )
                continue
            if getattr(firm, "received_working_capital_this_tick", False):
                self.bailout_denied_firms_by_reason["already_received_working_capital_this_tick"] = (
                    self.bailout_denied_firms_by_reason.get("already_received_working_capital_this_tick", 0) + 1
                )
                continue
            if not self._is_bailout_candidate(firm):
                self.bailout_denied_firms_by_reason["not_distressed_enough"] = (
                    self.bailout_denied_firms_by_reason.get("not_distressed_enough", 0) + 1
                )
                continue
            self.bailout_eligible_firms_by_sector[category] = self.bailout_eligible_firms_by_sector.get(category, 0) + 1
            candidate_firms.append(firm)
        if not candidate_firms:
            return

        def bailout_priority(firm: "FirmAgent") -> tuple:
            wage_bill = firm._current_wage_bill()
            payroll_coverage = max(0.0, firm.last_revenue) / max(wage_bill, 1.0)
            cash_runway_ticks = firm.cash_balance / max(wage_bill, 1.0)
            return (cash_runway_ticks, payroll_coverage, firm.cash_balance)

        candidate_firms.sort(key=bailout_priority)
        term_ticks = max(
            1,
            int(CONFIG.time.ticks_per_year * CONFIG.government.emergency_loan_term_years)
        )
        interest_rate = CONFIG.government.emergency_loan_interest

        for firm in candidate_firms:
            if available_budget <= 0.0 or self._payment_free_treasury_cash() <= reserve_floor:
                break

            desired = self._bailout_need_amount(firm)
            loan_amount = min(desired, available_budget, self._payment_free_treasury_cash() - reserve_floor)
            if loan_amount <= 0.0:
                self.bailout_denied_firms_by_reason["computed_loan_amount_zero"] = (
                    self.bailout_denied_firms_by_reason.get("computed_loan_amount_zero", 0) + 1
                )
                continue

            total_repayment = loan_amount * (1.0 + interest_rate)
            firm.cash_balance += loan_amount
            firm.government_loan_principal += loan_amount
            firm.government_loan_remaining += total_repayment
            firm.loan_payment_per_tick += total_repayment / max(1, term_ticks)
            gov.cash_balance -= loan_amount
            gov.record_bailout(firm.good_category, firm.firm_id, loan_amount)
            firm.received_bailout_this_tick = True
            self.last_tick_gov_bailouts += loan_amount
            self.bailout_received_by_firm_id[int(firm.firm_id)] = (
                self.bailout_received_by_firm_id.get(int(firm.firm_id), 0.0) + float(loan_amount)
            )
            available_budget -= loan_amount

        if available_budget <= 0.0:
            remaining_candidates = max(0, len(candidate_firms) - len(self.bailout_received_by_firm_id))
            if remaining_candidates > 0:
                self.bailout_denied_firms_by_reason["tick_or_cycle_budget_exhausted"] = (
                    self.bailout_denied_firms_by_reason.get("tick_or_cycle_budget_exhausted", 0) + remaining_candidates
                )

    def _deauthorize_public_works_capacity(self) -> None:
        """Wind down existing public works firms when the lever is off."""

        public_firms = [
            firm for firm in self.firms
            if (firm.good_category or "") == "PublicWorks"
        ]
        for firm in public_firms:
            firm.baseline_production_quota = 0.0
            firm.expected_sales_units = 0.0
            firm.planned_hires_count = 0
            firm.last_tick_planned_hires = 0
            if firm.employees:
                layoff_count = min(len(firm.employees), max(1, int(getattr(firm, "max_fires_per_tick", 1) or 1)))
                firm.planned_layoffs_ids = list(firm.employees[:layoff_count])
            else:
                firm.planned_layoffs_ids = []
            firm.decision_diagnostics["public_works_authorized"] = False

    def _ensure_public_works_capacity(self, unemployment_rate: float) -> float:
        """Stand up or scale public works firms to absorb excess labor.

        Gated by the ``public_works`` lever — only runs when the lever
        is set to ``"on"``.  The old unemployment-threshold trigger has
        been removed; the future LLM decides when to toggle this.
        """
        if self.government.public_works_toggle != "on":
            return 0.0
        config = CONFIG.government
        capitalization_outflow = 0.0

        target_jobs = max(1, int(len(self.households) * config.public_works_job_fraction))
        public_firms = [f for f in self.firms if f.good_category == "PublicWorks"]

        if not public_firms:
            recent_gdp = trailing_gdp(self)
            requested_startup = projected_public_works_startup_cost(self.firms)
            affordable_budget = public_works_affordable_budget(self.government, recent_gdp)
            if self.payment_sequence != "legacy":
                affordable_budget = min(affordable_budget, max(0.0, self._payment_free_treasury_cash() - fiscal_reserve_floor(recent_gdp)))
            self.last_tick_gov_public_works_requested_startup += requested_startup
            self.last_tick_gov_public_works_affordable_budget = affordable_budget
            if affordable_budget + 1e-9 < requested_startup:
                self.last_tick_gov_public_works_denied_by_budget += max(0.0, requested_startup - affordable_budget)
                return 0.0
            new_firm_id = self._next_firm_id()
            capacity = float(target_jobs * 2)
            initial_capitalization = requested_startup
            public_firm = FirmAgent(
                firm_id=new_firm_id,
                good_name=f"PublicWorks{new_firm_id}",
                cash_balance=initial_capitalization,
                inventory_units=0.0,
                good_category="PublicWorks",
                quality_level=1.0,
                wage_offer=config.public_works_wage,
                price=config.public_works_price,
                expected_sales_units=float(target_jobs),
                production_capacity_units=capacity,
                units_per_worker=15.0,
                productivity_per_worker=15.0,
                personality="conservative",
                is_baseline=True,
                baseline_production_quota=float(target_jobs)
            )
            public_firm.set_personality("conservative")
            self.government.cash_balance -= initial_capitalization
            capitalization_outflow += initial_capitalization
            self.firms.append(public_firm)
            self.firm_lookup[new_firm_id] = public_firm
            self.last_tick_sales_units[new_firm_id] = 0.0
            self.last_tick_revenue[new_firm_id] = 0.0
            self.last_tick_sell_through_rate[new_firm_id] = 0.5
            self.last_tick_unmet_demand_by_firm[new_firm_id] = 0.0
            self.last_tick_prices[public_firm.good_name] = public_firm.price
            public_firms = [public_firm]

        per_firm_quota = max(
            config.emergency_loan_min_headcount,
            int(math.ceil(target_jobs / len(public_firms)))
        )
        jobs_authorized = 0
        for firm in public_firms:
            firm.baseline_production_quota = max(float(per_firm_quota), firm.baseline_production_quota)
            firm.expected_sales_units = max(float(per_firm_quota), firm.expected_sales_units)
            firm.production_capacity_units = max(float(per_firm_quota * 2), firm.production_capacity_units)
            firm.price = config.public_works_price
            firm.wage_offer = config.public_works_wage
            firm.decision_diagnostics["public_works_authorized"] = True
            jobs_authorized += int(firm.baseline_production_quota)
        self.last_tick_gov_public_works_jobs_authorized = jobs_authorized
        self.last_tick_gov_public_works_capitalization += capitalization_outflow
        return capitalization_outflow

    def _apply_post_warmup_stimulus(self) -> None:
        """
        Temporary demand boost once the market opens to private firms.

        For a few ticks after warm-up the government sends a per-household
        transfer that decays each tick. This keeps demand alive long enough
        for new firms to record sales and justify hiring.
        """
        if self.post_warmup_stimulus_ticks <= 0 or not self.households:
            return

        duration = max(1, self.post_warmup_stimulus_duration)
        decay_ratio = self.post_warmup_stimulus_ticks / duration
        base_transfer = 40.0  # roughly one week of basic goods
        per_household_transfer = base_transfer * decay_ratio
        total_transfer = per_household_transfer * len(self.households)

        if self.payment_sequence != "legacy":
            affordable = self._payment_free_treasury_cash()
            if total_transfer > affordable:
                self.payment_denied_outlays["stimulus"] = total_transfer - affordable
                per_household_transfer = affordable / len(self.households)
                total_transfer = affordable
        # Legacy financing permits deficits; payment arms use the funded amount.
        self.government.cash_balance -= total_transfer
        self.last_tick_gov_post_warmup_stimulus += total_transfer
        for household in self.households:
            household.cash_balance += per_household_transfer
            household.add_ledger_flow("stimulus", per_household_transfer)

        self.post_warmup_stimulus_ticks -= 1

    def _apply_random_shocks(self) -> None:
        """
        Apply random economic shocks each tick to introduce stochasticity.

        Shocks include:
        - Demand shocks (random cash injections/withdrawals to households)
        - Supply shocks (temporary productivity changes to random firms)
        - Health shocks (random health crises affecting population)

        These shocks ensure that identical policy configurations produce
        different outcomes across runs, enabling statistical analysis.
        Uses a seeded RNG for reproducibility under CONFIG.random_seed.
        """

        # Skip shocks during warm-up period to allow stable initialization
        if self.in_warmup:
            return

        # Earlier supply shocks fade toward 1.0 (snapped to 1.0 within 0.001).
        shock_decay = float(CONFIG.firms.supply_shock_decay_per_tick)
        for firm in self.firms:
            if firm.supply_shock_multiplier != 1.0:
                faded = 1.0 + (firm.supply_shock_multiplier - 1.0) * (1.0 - shock_decay)
                firm.supply_shock_multiplier = 1.0 if abs(faded - 1.0) < 1e-3 else faded

        _rng = random.Random(CONFIG.random_seed + self.current_tick * 7_299_133)

        # 1. DEMAND SHOCK (5% chance per tick)
        # Random cash injection or withdrawal affecting 5-15% of households
        if _rng.random() < 0.05:
            shock_magnitude = _rng.uniform(-50, 100)  # Asymmetric: more likely positive
            affected_households = _rng.sample(
                self.households,
                k=min(len(self.households), max(1, int(len(self.households) * _rng.uniform(0.05, 0.15))))
            )
            self._append_regime_event(
                event_type="shock_demand",
                entity_type="economy",
                metric_value=float(shock_magnitude),
                payload={"affected": int(len(affected_households))},
            )
            if self.payment_sequence != "legacy":
                if shock_magnitude >= 0.0:
                    # A household income shock is a funded public outlay, not
                    # an external mint. Preserve protected B/A/project cash.
                    from payments import proportional
                    requested = {h.household_id: shock_magnitude for h in affected_households}
                    funded = proportional(requested, self._payment_free_treasury_cash())
                    total = sum(funded.values())
                    self.government.cash_balance -= total
                    for h in affected_households:
                        amount = funded.get(h.household_id, 0.0)
                        h.cash_balance += amount
                        h.add_ledger_flow("other", amount)
                    self.payment_state["last_positive_shock_funded"] = total
                    self.payment_state["last_positive_shock_denied"] = max(0.0, sum(requested.values()) - total)
                else:
                    extracted = 0.0
                    for h in affected_households:
                        amount = min(max(0.0, h.cash_balance), -shock_magnitude)
                        h.cash_balance -= amount
                        h.add_ledger_flow("other", -amount)
                        extracted += amount
                    self.government.cash_balance += extracted
                    self.payment_state["last_negative_shock_collected"] = extracted
            else:
                for h in affected_households:
                    before_cash = h.cash_balance
                    h.cash_balance = max(0, h.cash_balance + shock_magnitude)
                    realized = h.cash_balance - before_cash
                    h.add_ledger_flow("other", realized)

        # 2. SUPPLY SHOCK (3% chance per tick)
        # Random productivity change affecting 1-3 firms
        if _rng.random() < 0.03 and self.firms:
            num_affected = min(len(self.firms), _rng.randint(1, 3))
            affected_firms = _rng.sample(self.firms, k=num_affected)
            productivity_change = _rng.uniform(0.85, 1.15)  # ±15% productivity
            self._append_regime_event(
                event_type="shock_supply",
                entity_type="economy",
                metric_value=float(productivity_change),
                payload={"affected": int(len(affected_firms))},
            )
            for firm in affected_firms:
                # Production reads this multiplier this tick; it then fades (B26).
                firm.supply_shock_multiplier = productivity_change

        # 3. HEALTH SHOCK (2% chance per tick)
        # Random health crisis affecting 1-5% of population
        if _rng.random() < 0.02:
            health_shock = _rng.uniform(-0.05, -0.20)  # Health loss
            affected_households = _rng.sample(
                self.households,
                k=min(len(self.households), max(1, int(len(self.households) * _rng.uniform(0.01, 0.05))))
            )
            self._append_regime_event(
                event_type="shock_health",
                entity_type="economy",
                metric_value=float(health_shock),
                payload={"affected": int(len(affected_households))},
            )
            for h in affected_households:
                h.health = max(0.0, min(1.0, h.health + health_shock))

    # -------------------------------------------------------------------------
    # Section: Housing rentals, repairs, and miscellaneous revenue
    # -------------------------------------------------------------------------
    def _ensure_cash_for_payment(self, household, amount: float) -> bool:
        """Ensure household.cash_balance >= amount by withdrawing from deposits.

        Withdrawal goes through bank.withdraw() (money-conserving). Up to 90%
        of bank_deposit is accessible. Returns True if cash now covers amount,
        False if liquidity (cash + 90% deposits) is insufficient.
        """
        if amount <= 0.0:
            return True
        if household.cash_balance + 1e-9 >= amount:
            return True
        if self.bank is None or household.bank_deposit <= 0.0:
            return False
        shortfall = amount - household.cash_balance
        max_withdrawable = 0.90 * max(0.0, household.bank_deposit)
        if max_withdrawable <= 0.0:
            return False
        withdraw = min(shortfall, max_withdrawable)
        self._withdraw_deposits_to_cash(household, withdraw)
        return household.cash_balance + 1e-9 >= amount

    def _clear_housing_rental_market(self) -> None:
        """
        Match households with housing firms for rental agreements.

        HOUSING RENTAL RULES:
        1. Each household needs exactly 1 housing rental
        2. Households without housing seek rentals
        3. Housing firms try to fill all units
        4. Rent is paid weekly (not one-time purchase)
        5. Households can be evicted if they can't afford rent
        6. Housing firms adjust rent based on occupancy rate

        Mutates state.

        Note:
            SOLID VIOLATION - Single Responsibility Principle (SRP):
            This method has multiple responsibilities (~200 lines):
            1. Eviction logic (affordability check, liquidity check)
            2. Homeless household matching to available units
            3. Rent payment processing (with deposit withdrawal)
            4. Housing firm rent adjustment based on occupancy
            5. Diagnostic tracking (eviction counts, homelessness stats)
            Consider extracting: _process_evictions(), _match_homeless_to_housing(),
            _adjust_housing_rents(), _collect_rent_payments().

            SOLID VIOLATION - Dependency Inversion Principle (DIP):
            Direct dependency on BankAgent through _ensure_cash_for_payment().
            Housing logic is tightly coupled to banking integration.
        """
        # Get all housing firms
        housing_firms = [f for f in self.firms if f.good_category == "Housing"]
        # First housing firm per id, the same firm next(...) over housing_firms found.
        housing_firm_by_id: Dict[int, FirmAgent] = {}
        for f in housing_firms:
            housing_firm_by_id.setdefault(f.firm_id, f)

        if not housing_firms:
            self.last_housing_diagnostics = {
                "eviction_count": 0.0,
                "housing_failure_count": float(len(self.households)),
                "housing_unaffordable_count": 0.0,
                "housing_no_supply_count": float(len(self.households)),
                "homeless_household_count": float(len(self.households)),
                "housing_shortage_flag": 1.0,
            }
            return  # No housing available

        rent_share = CONFIG.labor_market.rent_affordability_share
        eviction_count = 0
        housing_failure_count = 0
        housing_unaffordable_count = 0
        housing_no_supply_count = 0

        # Phase 1: Check affordability and evict households who can't pay
        for household in self.households:
            if household.renting_from_firm_id is not None:
                # Find the housing firm
                housing_firm = housing_firm_by_id.get(household.renting_from_firm_id)

                if housing_firm is None:
                    # Firm no longer exists, evict household
                    household.renting_from_firm_id = None
                    household.monthly_rent = 0.0
                    household.owns_housing = False
                    eviction_count += 1
                    self._append_regime_event(
                        event_type="eviction",
                        entity_type="household",
                        entity_id=household.household_id,
                        sector="Housing",
                        reason_code="provider_missing",
                        severity=1.0,
                    )
                    continue

                # Affordability: income stream (wage or benefit) + 25% of accessible
                # liquidity (cash + 90% of bank deposits). Households with savings
                # are not evicted just because their cash buffer dipped low.
                income = household.wage if household.employer_id is not None else self.government.get_unemployment_benefit_level()
                income_ceiling = income * rent_share
                accessible_liquidity = household.cash_balance + 0.90 * max(0.0, household.bank_deposit)
                cash_ceiling = accessible_liquidity * 0.25
                max_affordable_rent = income_ceiling + cash_ceiling

                if household.monthly_rent > max_affordable_rent or accessible_liquidity < household.monthly_rent:
                    # EVICTION: Can't afford rent (income gate or insufficient liquidity)
                    housing_firm.current_tenants.remove(household.household_id)
                    household.renting_from_firm_id = None
                    household.monthly_rent = 0.0
                    household.owns_housing = False
                    household.happiness = max(0.0, household.happiness - 0.3)  # Happiness penalty for eviction
                    eviction_count += 1
                    self._append_regime_event(
                        event_type="eviction",
                        entity_type="household",
                        entity_id=household.household_id,
                        sector="Housing",
                        reason_code="unaffordable",
                        severity=1.0,
                        metric_value=float(max(household.monthly_rent - max_affordable_rent, 0.0)),
                    )
                else:
                    # Pay rent: top up cash from deposits if needed (money-conserving).
                    if not self._ensure_cash_for_payment(household, household.monthly_rent):
                        # Rare: liquidity check passed but withdrawal capped (e.g., bank
                        # reserves dry). Treat as eviction for this tick.
                        housing_firm.current_tenants.remove(household.household_id)
                        household.renting_from_firm_id = None
                        household.monthly_rent = 0.0
                        household.owns_housing = False
                        household.happiness = max(0.0, household.happiness - 0.3)
                        eviction_count += 1
                        self._append_regime_event(
                            event_type="eviction",
                            entity_type="household",
                            entity_id=household.household_id,
                            sector="Housing",
                            reason_code="liquidity_drained",
                            severity=1.0,
                        )
                        continue
                    household.cash_balance -= household.monthly_rent
                    household.add_ledger_flow("rent", -household.monthly_rent)
                    housing_firm.cash_balance += household.monthly_rent
                    household.owns_housing = True

        # Phase 2: Match homeless households with available units
        homeless_households = [h for h in self.households if h.renting_from_firm_id is None]

        # Sort homeless by effective income (wage > benefit > 0) so employed get priority
        gov_benefit = self.government.get_unemployment_benefit_level()
        homeless_households.sort(
            key=lambda h: h.wage if h.is_employed else gov_benefit,
            reverse=True,
        )

        for household in homeless_households:
            income = household.wage if household.employer_id is not None else gov_benefit
            income_ceiling = income * rent_share
            accessible_liquidity = household.cash_balance + 0.90 * max(0.0, household.bank_deposit)
            cash_ceiling = accessible_liquidity * 0.25
            max_affordable_rent = income_ceiling + cash_ceiling

            # Find cheapest housing firm with available units that household can afford
            affordable_housing = [
                (f, f.price) for f in housing_firms
                if len(f.current_tenants) < f.max_rental_units and f.price <= max_affordable_rent
                and f.price <= accessible_liquidity
            ]

            if affordable_housing:
                # Cheapest first; min() keeps the first of equal prices, as the
                # stable sort's [0] did.
                chosen_firm, rent = min(affordable_housing, key=lambda x: x[1])

                # Pay first month's rent: top up cash from deposits if needed.
                if not self._ensure_cash_for_payment(household, rent):
                    # Liquidity drained mid-loop; skip onboarding.
                    housing_failure_count += 1
                    continue

                # Sign rental agreement
                household.renting_from_firm_id = chosen_firm.firm_id
                household.monthly_rent = rent
                household.owns_housing = True
                chosen_firm.current_tenants.append(household.household_id)

                household.cash_balance -= rent
                household.add_ledger_flow("rent", -rent)
                chosen_firm.cash_balance += rent
            else:
                housing_failure_count += 1
                any_supply = any(len(f.current_tenants) < f.max_rental_units for f in housing_firms)
                if any_supply:
                    housing_unaffordable_count += 1
                else:
                    housing_no_supply_count += 1

        total_units = sum(f.max_rental_units for f in housing_firms)
        shortage = total_units < len(self.households)

        # Phase 3: Housing firms adjust rent based on occupancy
        lm = CONFIG.labor_market
        # Dynamic rent floor: scales with the 25th-percentile wage so the floor is
        # affordable to low-wage workers early in the simulation. Falls back to the
        # configured absolute minimum if no wage data is available yet.
        wage_p25, _, _ = self.cached_wage_percentiles
        if wage_p25 is not None:
            dynamic_rent_floor = max(lm.rent_floor_absolute_min, wage_p25 * lm.rent_affordability_share)
        else:
            dynamic_rent_floor = lm.rent_floor_absolute_min
        for firm in housing_firms:
            price_before = float(getattr(firm, "price", 0.0) or 0.0)
            occupancy_rate = len(firm.current_tenants) / max(firm.max_rental_units, 1)

            # Seek equilibrium: raise rent if fully occupied, lower if vacant
            if occupancy_rate >= lm.occupancy_high_threshold:
                firm.price *= lm.rent_increase_high_occupancy
            elif occupancy_rate >= lm.occupancy_good_threshold:
                firm.price *= lm.rent_increase_good_occupancy
            elif occupancy_rate < lm.occupancy_low_threshold:
                firm.price *= lm.rent_decrease_high_vacancy
            elif occupancy_rate < lm.occupancy_moderate_threshold:
                firm.price *= lm.rent_decrease_moderate_vacancy

            firm.price = max(dynamic_rent_floor, firm.price)

            if shortage and occupancy_rate >= lm.occupancy_high_threshold and self.current_tick % lm.rent_shortage_interval_ticks == 0:
                firm.price *= lm.rent_shortage_multiplier

            rent_level = str(getattr(self.government, "rent_stabilization_level", "off") or "off").lower()
            if rent_level in {"soft", "strict"} and price_before > 0.0 and firm.price > price_before:
                max_rent = max(dynamic_rent_floor, price_before * self._price_stabilization_multiplier(rent_level, rent=True))
                if max_rent + 1e-9 < firm.price:
                    firm.decision_diagnostics["rent_stabilization_limited"] = True
                    firm.decision_diagnostics["rent_stabilization_level"] = rent_level
                    firm.decision_diagnostics["rent_stabilization_uncapped_rent"] = firm.price
                    firm.decision_diagnostics["rent_stabilization_capped_rent"] = max_rent
                    firm.price = max_rent
                    self.rent_increase_limited_count += 1

        homeless_household_count = sum(1 for household in self.households if household.renting_from_firm_id is None)
        self.last_housing_diagnostics = {
            "eviction_count": float(eviction_count),
            "housing_failure_count": float(housing_failure_count),
            "housing_unaffordable_count": float(housing_unaffordable_count),
            "housing_no_supply_count": float(housing_no_supply_count),
            "homeless_household_count": float(homeless_household_count),
            "housing_shortage_flag": float(1.0 if shortage else 0.0),
        }

    def _apply_housing_repairs(self) -> None:
        """Apply random weekly repair costs to housing firms."""
        _rng = random.Random(CONFIG.random_seed + self.current_tick * 5_308_417)
        for firm in self.firms:
            if firm.good_category.lower() != "housing":
                continue
            if firm.max_rental_units <= 0 or firm.price <= 0:
                continue
            repair_rate = _rng.uniform(0.01, 0.05)
            repair_cost = firm.price * firm.max_rental_units * repair_rate
            if repair_cost <= 0:
                continue
            payment = min(firm.cash_balance, repair_cost)
            if payment <= 0:
                continue
            firm.cash_balance -= payment
            self._collect_misc_revenue(payment)

    def _initialize_misc_firm_beneficiaries(self) -> None:
        """Initialize Misc firm with 10-20 random household beneficiaries."""
        if self.households:
            _rng = random.Random(CONFIG.random_seed + 8_191_003)
            num_beneficiaries = _rng.randint(10, 20)
            num_beneficiaries = min(num_beneficiaries, len(self.households))
            all_ids = [h.household_id for h in self.households]
            self.misc_firm_beneficiaries = _rng.sample(all_ids, num_beneficiaries)

    def _misc_firm_add_beneficiary(self) -> None:
        """Each tick, potentially add 1 more random beneficiary."""
        if not self.households:
            return

        # Don't add if we already have 50+ beneficiaries
        if len(self.misc_firm_beneficiaries) >= 50:
            return

        # Find households not already beneficiaries
        non_beneficiaries = [
            h.household_id for h in self.households
            if h.household_id not in self.misc_firm_beneficiaries
        ]

        if non_beneficiaries:
            _rng = random.Random(CONFIG.random_seed + self.current_tick * 3_500_017)
            new_beneficiary = _rng.choice(non_beneficiaries)
            self.misc_firm_beneficiaries.append(new_beneficiary)
            household = self.household_lookup.get(int(new_beneficiary))
            if household is not None:
                household.is_misc_beneficiary = True

    def _misc_firm_redistribute_revenue(self) -> None:
        """
        Distribute all accumulated Misc firm revenue to beneficiaries.

        The Misc firm collects:
        - R&D spending from firms
        - Investment spending from government
        - Other "dead money" that would leave the economy

        It then redistributes ALL revenue equally to beneficiaries.
        """
        if self.misc_firm_revenue <= 0 or not self.misc_firm_beneficiaries:
            return

        # Distribute equally among beneficiaries
        payout_per_household = self.misc_firm_revenue / len(self.misc_firm_beneficiaries)

        for hid in self.misc_firm_beneficiaries:
            household = self.household_lookup.get(hid)
            if household:
                household.cash_balance += payout_per_household
                household.add_ledger_flow("redistribution", payout_per_household)

        # Reset revenue to 0 after payout
        self.misc_firm_revenue = 0.0

    def _collect_misc_revenue(self, amount: float) -> None:
        """
        Route spending into the misc pool with a variable tax skim.

        A random fraction (0-20%) is collected as tax, the rest
        is accumulated as misc_firm_revenue for redistribution.
        """
        if amount <= 0:
            return

        # Stochastic tax rate on miscellaneous transactions
        _rng = random.Random(CONFIG.random_seed + self.current_tick * 2_038_073 + int(amount * 100))
        tax_rate = _rng.uniform(0.0, 0.20)
        tax = amount * tax_rate
        net = amount - tax
        if tax > 0:
            self.government.cash_balance += tax
        if net > 0:
            self.misc_firm_revenue += net

    # -------------------------------------------------------------------------
    # Section: Healthcare queue and service processing
    # -------------------------------------------------------------------------
    def _reset_healthcare_tick_state(self) -> None:
        """Reset per-tick healthcare counters.

        Healthcare goods never enter household goods_inventory: healthcare
        firms hold no inventory (apply_production_and_costs zeroes it), so the
        legacy goods market cannot sell them, and PaymentGoodsMarket excludes
        them. The per-household inventory scan that used to run here removed
        nothing and was deleted in remediation phase 2.
        """
        self.healthcare_requests_this_tick = 0.0
        self.healthcare_attempted_slots_this_tick = 0.0
        self.healthcare_completed_visits_this_tick = 0.0
        self.healthcare_affordability_rejects_this_tick = 0.0
        self.last_healthcare_events = []

        for household in self.households:
            household.healthcare_consumed_this_tick = 0.0
            household.last_healthcare_units = 0.0
            household.last_healthcare_spend = 0.0
            household.last_healthcare_provider_id = None

        for firm in self.firms:
            if firm.good_category.lower() != "healthcare":
                continue
            firm.inventory_units = 0.0
            firm.healthcare_requests_last_tick = 0.0
            firm.healthcare_completed_visits_last_tick = 0.0

    def _apply_doctor_health_lock(self) -> None:
        """Keep active doctors healthy enough to maintain healthcare supply stability."""
        if not CONFIG.households.doctor_health_lock_enabled:
            return

        lock_value = max(0.0, min(1.0, CONFIG.households.doctor_health_lock_value))
        for household in self.households:
            if household.medical_training_status == "doctor":
                household.health = lock_value

    def _healthcare_firms(self) -> List[FirmAgent]:
        """Return the subset of firms that produce healthcare services."""
        return [f for f in self.firms if f.good_category.lower() == "healthcare"]

    def _choose_healthcare_provider(self, household: HouseholdAgent, firms: List[FirmAgent]) -> Optional[FirmAgent]:
        """
        Choose provider by queue pressure with deterministic tie-breaking.

        Critical patients mostly ignore price and prioritize shortest wait.
        """
        if not firms:
            return None

        baseline_price = max(1.0, CONFIG.baseline_prices.get("Healthcare", 15.0))
        critical_cutoff = household.healthcare_critical_threshold
        if critical_cutoff is None:
            critical_cutoff = sum(CONFIG.households.healthcare_critical_threshold_range) / 2.0

        ranked: List[Tuple[float, int, FirmAgent]] = []
        for firm in firms:
            cap_per_worker = max(0.1, firm.healthcare_capacity_per_worker)
            capacity = max(1.0, len(firm.employees) * cap_per_worker)
            queue_pressure = len(firm.healthcare_queue) / capacity
            if household.health <= critical_cutoff:
                price_term = 0.0
            else:
                price_term = max(0.0, firm.price) / (baseline_price * 100.0)
            ranked.append((queue_pressure + price_term, firm.firm_id, firm))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return ranked[0][2]

    def _enqueue_healthcare_requests(self) -> None:
        """Route healthcare demand into provider queues based on household need plans."""
        healthcare_firms = self._healthcare_firms()
        if not healthcare_firms:
            return

        for household in self.households:
            if household.queued_healthcare_firm_id is not None:
                continue
            if not household.should_request_healthcare_service(self.current_tick):
                continue

            provider = self._choose_healthcare_provider(household, healthcare_firms)
            if provider is None:
                continue

            provider.healthcare_queue.append(household.household_id)
            household.queued_healthcare_firm_id = provider.firm_id
            household.healthcare_queue_enter_tick = self.current_tick
            provider.healthcare_requests_last_tick += 1.0
            self.healthcare_requests_this_tick += 1.0

        alpha = max(0.0, min(1.0, CONFIG.firms.healthcare_arrivals_ema_alpha))
        for firm in healthcare_firms:
            arrivals = max(0.0, firm.healthcare_requests_last_tick)
            firm.healthcare_arrivals_ema = alpha * arrivals + (1.0 - alpha) * max(0.0, firm.healthcare_arrivals_ema)

    def _prioritize_healthcare_queue(self, firm: FirmAgent) -> None:
        """Move sick doctors to the front of a firm's queue while preserving relative order."""
        if firm.good_category.lower() != "healthcare" or not firm.healthcare_queue:
            return

        threshold = CONFIG.households.healthcare_worker_priority_health_threshold
        priority_ids: List[int] = []
        other_ids: List[int] = []

        for household_id in firm.healthcare_queue:
            household = self.household_lookup.get(household_id)
            is_priority = (
                household is not None
                and household.medical_training_status == "doctor"
                and household.health < threshold
            )
            if is_priority:
                priority_ids.append(household_id)
            else:
                other_ids.append(household_id)

        firm.healthcare_queue = priority_ids + other_ids

    def _healthcare_effective_capacity(self, firm: FirmAgent) -> float:
        """
        Effective healthcare visit capacity this tick.

        Uses worker medical skill if available, otherwise falls back to firm-level
        capacity-per-worker for deterministic test scaffolding.
        """
        capacity = 0.0
        known_worker_count = 0
        for employee_id in firm.employees:
            worker = self.household_lookup.get(employee_id)
            if worker is None:
                continue
            known_worker_count += 1
            capacity += max(0.0, worker.medical_visit_capacity())

        if capacity <= 0.0:
            capacity = len(firm.employees) * max(0.1, firm.healthcare_capacity_per_worker)
        elif known_worker_count < len(firm.employees):
            unknown_workers = len(firm.employees) - known_worker_count
            capacity += unknown_workers * max(0.1, firm.healthcare_capacity_per_worker)

        return max(0.0, capacity)

    def _process_healthcare_services(self, per_firm_sales: Dict[int, Dict[str, float]]) -> None:
        """
        Process queued healthcare visits up to capacity.

        Revenue flows to healthcare firms; household health is restored on completed visits.

        Note:
            SOLID VIOLATION - Single Responsibility Principle (SRP):
            This method has multiple responsibilities (~150 lines):
            1. Healthcare queue processing (priority sorting, fair rotation)
            2. Payment processing (household cost, government subsidy)
            3. Deposit withdrawal for unaffordable care
            4. Medical loan origination for unpaid bills
            5. Health updates on completed visits
            6. Event logging for diagnostics
            Consider extracting: _process_single_visit(), _handle_healthcare_payment(),
            _update_health_post_visit(), _log_healthcare_event().

            SOLID VIOLATION - Dependency Inversion Principle (DIP):
            Direct dependency on BankAgent through _issue_medical_loan() and
            _ensure_cash_for_payment() -> bank.withdraw(). Healthcare logic
            is tightly coupled to banking integration.
        """
        healthcare_firms = self._healthcare_firms()
        if not healthcare_firms:
            return

        # Use sector_subsidy lever if targeting healthcare; otherwise fall back to config
        if self.government.sector_subsidy_target == "healthcare" and self.government._sector_subsidy_rate > 0:
            subsidy_share = self.government._sector_subsidy_rate
        else:
            subsidy_share = max(0.0, min(1.0, CONFIG.government.healthcare_visit_subsidy_share))

        for firm in healthcare_firms:
            firm.inventory_units = 0.0
            self._prioritize_healthcare_queue(firm)
            event_tick = int(self.current_tick + 1)

            capacity_float = self._healthcare_effective_capacity(firm)
            capacity_with_carry = capacity_float + max(0.0, firm.healthcare_capacity_carryover)
            slots_to_attempt = int(math.floor(capacity_with_carry + 1e-9))
            firm.healthcare_capacity_carryover = max(0.0, capacity_with_carry - slots_to_attempt)
            self.healthcare_attempted_slots_this_tick += capacity_float

            if slots_to_attempt <= 0 or not firm.healthcare_queue:
                continue

            per_firm_sales.setdefault(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
            queue_ids = firm.healthcare_queue
            queue_len = len(queue_ids)

            # Fairness: rotate queue scan origin each tick for non-priority queues.
            start_idx = 0
            if queue_len > 1:
                lead_household = self.household_lookup.get(queue_ids[0])
                lead_is_priority_doctor = (
                    lead_household is not None
                    and lead_household.medical_training_status == "doctor"
                    and lead_household.health < CONFIG.households.healthcare_worker_priority_health_threshold
                )
                if not lead_is_priority_doctor:
                    start_idx = (self.current_tick + firm.firm_id) % queue_len

            if start_idx > 0:
                ordered_queue = queue_ids[start_idx:] + queue_ids[:start_idx]
            else:
                ordered_queue = list(queue_ids)

            next_queue: List[int] = []
            completed = 0

            for household_id in ordered_queue:
                if completed >= slots_to_attempt:
                    next_queue.append(household_id)
                    continue

                household = self.household_lookup.get(household_id)
                if household is None:
                    continue

                queue_enter_tick = getattr(household, "healthcare_queue_enter_tick", -1)
                queue_wait_ticks = (
                    max(0, self.current_tick - queue_enter_tick)
                    if queue_enter_tick >= 0
                    else 0
                )

                visit_price = max(0.0, firm.price)
                requested_government_cost = visit_price * subsidy_share
                government_cost, _denied_by_cap = self.apply_sector_subsidy_payment(requested_government_cost)
                household_cost = visit_price - government_cost

                if household.cash_balance + 1e-9 < household_cost:
                    # Pay with savings first: withdraw up to 90% of bank deposits
                    # (money-conserving via bank.withdraw) before falling back to a loan.
                    shortfall = household_cost - household.cash_balance
                    max_withdrawable = 0.90 * max(0.0, household.bank_deposit)
                    if max_withdrawable > 0.0 and self.bank is not None:
                        withdraw_amount = min(shortfall, max_withdrawable)
                        self._withdraw_deposits_to_cash(household, withdraw_amount)

                if household.cash_balance + 1e-9 < household_cost:
                    # Still cannot afford — try medical loan (bank-first, then drop)
                    loan_issued = False
                    shortfall = household_cost - household.cash_balance
                    if shortfall > 0 and household.medical_loan_remaining <= 0:
                        loan_issued = self._issue_medical_loan(household, shortfall)

                    if not loan_issued:
                        self.refund_sector_subsidy_payment(government_cost)
                        household_cost = visit_price
                        government_cost = 0.0
                        # Cannot afford and no loan — drop from queue entirely.
                        # Do NOT append to next_queue. Clear queue tracking on
                        # the household so they exit the deadlock and may
                        # re-request later via the normal demand path.
                        household.queued_healthcare_firm_id = None
                        household.healthcare_queue_enter_tick = -1
                        self.healthcare_affordability_rejects_this_tick += 1.0
                        self.last_healthcare_events.append({
                            "tick": event_tick,
                            "household_id": int(household_id),
                            "firm_id": int(firm.firm_id),
                            "event_type": "visit_denied_affordability",
                            "queue_wait_ticks": int(queue_wait_ticks),
                            "visit_price": float(visit_price),
                            "household_cost": float(household_cost),
                            "government_cost": float(government_cost),
                            "health_before": float(household.health),
                            "health_after": float(household.health),
                        })
                        continue
                    # Loan granted — household now has enough cash, fall through to payment

                health_before = float(household.health)
                if household_cost > 0.0:
                    household.cash_balance -= household_cost
                    household.add_ledger_flow("healthcare", -household_cost)

                per_firm_sales[firm.firm_id]["units_sold"] += 1.0
                per_firm_sales[firm.firm_id]["revenue"] += visit_price
                firm.healthcare_completed_visits_last_tick += 1.0
                self.healthcare_completed_visits_this_tick += 1.0

                heal_delta = household.pending_visit_heal_delta
                if heal_delta <= 0.0:
                    heal_delta = CONFIG.households.healthcare_visit_base_heal * (1.0 - household.health)
                household.pending_visit_heal_delta = 0.0
                household.health = min(1.0, household.health + max(0.0, heal_delta))
                household.healthcare_consumed_this_tick += 1.0
                household.last_healthcare_units += 1.0
                household.last_healthcare_spend += household_cost
                household.last_healthcare_provider_id = firm.firm_id
                household.last_checkup_tick = self.current_tick
                household.queued_healthcare_firm_id = None
                household.healthcare_queue_enter_tick = -1
                self.last_healthcare_events.append({
                    "tick": event_tick,
                    "household_id": int(household_id),
                    "firm_id": int(firm.firm_id),
                    "event_type": "visit_completed",
                    "queue_wait_ticks": int(queue_wait_ticks),
                    "visit_price": float(visit_price),
                    "household_cost": float(household_cost),
                    "government_cost": float(government_cost),
                    "health_before": health_before,
                    "health_after": float(household.health),
                })

                completed += 1

            firm.healthcare_queue = next_queue

            if completed > 0:
                firm.healthcare_idle_streak = 0

    # -------------------------------------------------------------------------
    # Section: Fiscal pressure, banking, credit, and medical loans
    # -------------------------------------------------------------------------
    def _fiscal_pressure_denominator_gdp(self) -> float:
        """Return the GDP denominator used for fiscal-pressure ratios."""
        if self.payment_sequence != "legacy" and self.payment_book is not None:
            current_goods_care = sum(row["revenue"] for row in self.payment_book.receipts.values())
            if current_goods_care > 0.0:
                return current_goods_care
            previous_goods_care = sum(float(v) for v in self.last_tick_revenue.values())
            if previous_goods_care > 0.0:
                return previous_goods_care
            for row in reversed(self.metrics_history):
                metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
                history_gdp = float(metrics.get("gdp_this_tick", 0.0) or 0.0)
                if history_gdp > 0.0:
                    return history_gdp
            return 1.0
        current_gdp = sum(
            max(0.0, float(getattr(firm, "last_revenue", 0.0) or 0.0))
            for firm in getattr(self, "firms", []) or []
        )
        if current_gdp > 0.0:
            return current_gdp

        current_gdp = sum(float(value) for value in self.last_tick_revenue.values()) if self.last_tick_revenue else 0.0
        if current_gdp > 0.0:
            return current_gdp

        for row in reversed(getattr(self, "metrics_history", []) or []):
            metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
            try:
                history_gdp = float(metrics.get("gdp_this_tick", 0.0) or 0.0)
            except (TypeError, ValueError):
                history_gdp = 0.0
            if history_gdp > 0.0:
                return history_gdp

        return 1.0

    def _update_budget_pressure(
        self,
        revenue: float,
        spending: float,
    ) -> None:
        """Update the government's soft budget constraint each tick.

        Computes a rolling fiscal-pressure signal (EMA of per-tick deficit / GDP)
        and derives a ``spending_efficiency`` penalty that makes sustained
        large deficits progressively more costly.

        The constraint is *soft* — the government can choose to run
        deficits (e.g. counter-cyclical stimulus), but compounding
        inefficiency creates real tradeoffs that a future LLM must
        learn to navigate.

        Thresholds:
            fiscal_pressure < 0.05 → no penalty (healthy)
            0.05 – 0.15          → mild efficiency loss (crowding out)
            0.15 – 0.30          → forced partial spending cutbacks
            > 0.30               → austerity — discretionary spending halved

        Args:
            revenue: Total government revenue this tick (taxes + loan repayments).
            spending: Total government spending this tick (transfers + investments + subsidies).
        """
        gdp = max(self._fiscal_pressure_denominator_gdp(), 1.0)

        deficit_this_tick = spending - revenue
        instant_ratio = deficit_this_tick / gdp
        self.last_fiscal_pressure_instant_ratio = instant_ratio
        self.last_fiscal_pressure_denominator_gdp = gdp

        # Exponential moving average (α=0.05 → ~20-tick half-life)
        self.government.fiscal_pressure = (
            0.95 * self.government.fiscal_pressure + 0.05 * instant_ratio
        )
        self.government.fiscal_pressure = max(self.government.fiscal_pressure, -0.15)

        # Track for observation
        self.government.last_tick_revenue = revenue
        self.government.last_tick_spending = spending

        # Derive spending efficiency penalty
        dr = self.government.fiscal_pressure
        if dr < 0.05:
            self.government.spending_efficiency = 1.0
        elif dr < 0.15:
            # Linear ramp from 1.0 → 0.8 over the 0.05-0.15 band
            self.government.spending_efficiency = 1.0 - 0.2 * ((dr - 0.05) / 0.10)
        elif dr < 0.30:
            # Further cuts: 0.8 → 0.5
            fraction = (dr - 0.15) / 0.15
            self.government.spending_efficiency = 0.8 - 0.3 * fraction
        else:
            # Austerity: hard floor at 0.5
            self.government.spending_efficiency = 0.5

    # ── Bank integration methods ──────────────────────────────────────

    def _collect_bank_loan_repayments(self) -> None:
        """Phase 9.5: Collect repayments on all active bank loans.

        For each active loan, attempt to collect the scheduled payment from
        the borrower's cash balance. Updates credit scores on payment/miss.
        Falls back gracefully if a borrower can't be found (e.g., exited firm).
        """
        bank = self.bank
        if bank is None:
            return

        for loan in list(bank.active_loans):
            if loan["remaining"] <= 1e-6:
                continue
            if loan.get("subtype") == "housing_mortgage" and loan["borrower_id"] in self.firm_lookup:
                continue  # serviced by its LoanContract in _service_housing_mortgage_debt

            scheduled = loan["payment_per_tick"]
            if loan["borrower_type"] == "firm":
                firm = self.firm_lookup.get(loan["borrower_id"])
                if firm is None:
                    # Firm exited — write off
                    bank.write_off_loan(loan)
                    bank.update_firm_credit_score(loan["borrower_id"], -0.20)
                    continue
                payment = min(scheduled, loan["remaining"], max(0.0, firm.cash_balance))
                if payment > 1e-6:
                    payment = bank.collect_repayment(loan, payment, self.government)
                    firm.cash_balance -= payment
                    firm.bank_loan_remaining = max(0.0, firm.bank_loan_remaining - payment)
                    if loan.get("subtype") == "service_infrastructure":
                        firm.service_infrastructure_loan_remaining = max(
                            0.0,
                            firm.service_infrastructure_loan_remaining - payment,
                        )
                        if loan["remaining"] <= 1e-6 or firm.service_infrastructure_loan_remaining <= 1e-6:
                            firm.service_infrastructure_loan_remaining = 0.0
                            firm.service_infrastructure_loan_payment_per_tick = 0.0
                    elif loan.get("subtype") == "long_term_capital" and loan["remaining"] <= 1e-6:
                        firm.bank_loan_payment_per_tick = max(
                            0.0, firm.bank_loan_payment_per_tick - loan["payment_per_tick"])
                    bank.update_firm_credit_score(firm.firm_id, +0.01)
                else:
                    loan["missed_payments"] = loan.get("missed_payments", 0) + 1
                    bank.update_firm_credit_score(loan["borrower_id"], -0.05)

            elif loan["borrower_type"] == "household":
                hh = self.household_lookup.get(loan["borrower_id"])
                if hh is None:
                    bank.write_off_loan(loan)
                    bank.update_household_credit_score(loan["borrower_id"], -0.20)
                    continue
                payment = min(scheduled, loan["remaining"], max(0.0, hh.cash_balance))
                is_consumption = loan.get("subtype") == "consumption"
                if not is_consumption:
                    # Also recognize legacy registered loans without a subtype.
                    hh.medical_loan_bank_serviced = True
                    hh.medical_loan_remaining = loan["remaining"]
                    hh.medical_loan_payment_per_tick = scheduled
                if payment > 1e-6:
                    payment = bank.collect_repayment(loan, payment, self.government)
                    hh.cash_balance -= payment
                    hh.add_ledger_flow("bank", -payment)
                    if is_consumption:
                        hh.consumption_loan_remaining = max(0.0, hh.consumption_loan_remaining - payment)
                        if hh.consumption_loan_remaining <= 1e-6:
                            hh.consumption_loan_remaining = 0.0
                            hh.consumption_loan_payment_per_tick = 0.0
                    else:
                        # Medical or other household loan
                        hh.medical_loan_remaining = loan["remaining"]
                        if hh.medical_loan_remaining <= 1e-6:
                            hh.medical_loan_remaining = 0.0
                            hh.medical_loan_principal = 0.0
                            hh.medical_loan_payment_per_tick = 0.0
                            hh.medical_loan_bank_serviced = False
                    bank.update_household_credit_score(hh.household_id, +0.01)
                else:
                    loan["missed_payments"] = loan.get("missed_payments", 0) + 1
                    bank.update_household_credit_score(loan["borrower_id"], -0.05)

                    # Household default: 8 consecutive missed payments
                    if loan["missed_payments"] >= 8:
                        bank.write_off_loan(loan)
                        bank.update_household_credit_score(loan["borrower_id"], -0.20)
                        if is_consumption:
                            hh.consumption_loan_remaining = 0.0
                            hh.consumption_loan_payment_per_tick = 0.0
                        else:
                            hh.medical_loan_remaining = 0.0
                            hh.medical_loan_principal = 0.0
                            hh.medical_loan_payment_per_tick = 0.0
                            hh.medical_loan_bank_serviced = False

    def _process_bank_deposits(self) -> None:
        """Phase 11.3: Sweep excess household cash into bank deposits and pay interest.

        Each household has its own ``deposit_buffer_weeks`` (how many weeks of
        expenses to keep liquid) and ``deposit_fraction`` (what share of excess
        to deposit each tick).  Both are derived from the household's
        ``saving_tendency`` at initialization, producing population-level
        heterogeneity that averages to ~6 weeks buffer / ~20% fraction.

        Households can also withdraw from deposits when cash drops below
        their buffer threshold (demand deposits).
        """
        bank = self.bank
        if bank is None:
            return

        min_wage = self.government.get_minimum_wage()

        # Deposit interest must be funded out of loan-interest income earned this
        # tick, after retaining a minimum profit margin. No money is created.
        weekly_rate = bank.deposit_rate / 52.0
        intended_interests: Dict[int, float] = {}
        total_intended = 0.0
        for hh in self.households:
            if hh.bank_deposit > 0.0:
                intended = max(0.0, hh.bank_deposit * weekly_rate)
                if intended > 0.0:
                    intended_interests[hh.household_id] = intended
                    total_intended += intended

        budget_for_interest = max(
            0.0,
            float(bank.last_tick_interest_income) - float(bank.min_profit_margin_per_tick),
        )
        # Cap by what the bank actually has on hand (cannot pay more than reserves).
        budget_for_interest = min(budget_for_interest, max(0.0, float(bank.cash_reserves)))
        if total_intended > 0.0 and budget_for_interest > 0.0:
            payout_factor = min(1.0, budget_for_interest / total_intended)
        else:
            payout_factor = 0.0

        for hh in self.households:
            # Pay interest on existing deposits (income goes to cash, not compounded into deposit)
            intended = intended_interests.get(hh.household_id, 0.0)
            interest = intended * payout_factor
            if interest > 0.0:
                bank.cash_reserves -= interest
                bank.last_tick_deposit_interest_paid += interest
                hh.cash_balance += interest
                hh.add_ledger_flow("bank", interest)

            # Per-household liquidity buffer: buffer_weeks × estimated weekly spending
            weekly_spend = max(hh.last_consumption_spending, min_wage, 50.0)
            liquidity_floor = weekly_spend * hh.deposit_buffer_weeks

            if hh.cash_balance > liquidity_floor:
                # Fix 22: Higher deposit rate → deposit more; lower rate → deposit less
                rate_multiplier = 1.0 + (bank.deposit_rate - 0.01) * 20.0
                rate_multiplier = max(0.5, min(2.0, rate_multiplier))
                adjusted_fraction = hh.deposit_fraction * rate_multiplier

                # Deposit a fraction of excess
                excess = hh.cash_balance - liquidity_floor
                deposit_amount = excess * adjusted_fraction
                if deposit_amount > 1.0:  # Don't bother with dust
                    hh.cash_balance -= deposit_amount
                    hh.bank_deposit += deposit_amount
                    bank.accept_deposit(hh.household_id, deposit_amount)
                    hh.add_ledger_flow("bank", -deposit_amount)
                    self.last_tick_end_tick_deposit_sweeps += deposit_amount
            elif self.payment_sequence == "legacy" and hh.cash_balance < liquidity_floor * 0.5 and hh.bank_deposit > 0.0:
                # Cash critically low — withdraw from deposits
                shortfall = liquidity_floor * 0.5 - hh.cash_balance
                withdraw = min(shortfall, hh.bank_deposit)
                actual = bank.withdraw(hh.household_id, withdraw)
                hh.bank_deposit -= actual
                hh.cash_balance += actual
                hh.add_ledger_flow("bank", actual)
                self.last_tick_pre_purchase_deposit_withdrawals += actual

    def _update_credit_scores(self) -> None:
        """Phase 11.4: Periodic credit score adjustments based on financial health signals.

        Runs once per tick. Supplements the per-repayment score changes with
        broader signals like revenue strength and employment stability.

        Performance: builds a firm-debt lookup once (O(loans)) to avoid
        O(firms × loans) nested scan for leverage checks.
        """
        bank = self.bank
        if bank is None:
            return

        # Pre-build firm debt lookup: O(loans) instead of O(firms × loans)
        firm_debt_map: Dict[int, float] = {}
        for loan in bank.active_loans:
            if loan["borrower_type"] == "firm":
                bid = loan["borrower_id"]
                firm_debt_map[bid] = firm_debt_map.get(bid, 0.0) + loan["remaining"]

        for firm in self.firms:
            fid = firm.firm_id

            # Update trailing revenue EMA (alpha ~= 2/13 for 12-tick window)
            alpha = 2.0 / 13.0
            firm.trailing_revenue_12t = (
                alpha * firm.last_revenue + (1.0 - alpha) * firm.trailing_revenue_12t
            )

            # Revenue health: strong revenue relative to payroll
            total_payroll = sum(firm.actual_wages.values()) if firm.actual_wages else 0.0
            if total_payroll > 0 and firm.last_revenue > 2.0 * total_payroll:
                bank.update_firm_credit_score(fid, +0.01)

            # Zero revenue streak
            if firm.last_revenue <= 0 and firm.zero_cash_streak >= 4:
                bank.update_firm_credit_score(fid, -0.03)

            # High leverage warning (O(1) lookup instead of O(loans) scan)
            existing_debt = firm_debt_map.get(fid, 0.0)
            if existing_debt > 3.0 * max(firm.trailing_revenue_12t, 1.0):
                bank.update_firm_credit_score(fid, -0.02)

        for hh in self.households:
            hid = hh.household_id
            # Employment stability bonus (unemployment_duration == 0 for 8+ ticks
            # is approximated by checking employed + low duration)
            if hh.is_employed and hh.unemployment_duration == 0:
                # Only award every 8th tick to approximate "8+ consecutive ticks"
                if self.current_tick % 8 == 0:
                    bank.update_household_credit_score(hid, +0.01)
            # Unemployment penalty
            if not hh.is_employed and hh.unemployment_duration >= 4:
                bank.update_household_credit_score(hid, -0.01)

    def _issue_medical_loan(self, household: "HouseholdAgent", amount: float) -> bool:
        """Issue bank credit, then treasury-funded credit; the legacy fallback runs only with no bank.

        Only one medical loan can be active at a time (debt stacking prevention).
        Returns True if loan was issued and household now has the cash.
        """
        if household.medical_loan_remaining > 0:
            return False  # Already has an active medical loan

        bank = self.bank
        term_ticks = 52  # 1 year

        if bank is not None:
            credit_score = bank.get_household_credit_score(household.household_id)
            if credit_score < 0.15:
                return False  # Credit too low

            rate = bank._risk_adjusted_rate(credit_score, spread=0.03)
            if bank.can_lend() and bank.lendable_cash >= amount:
                loan = bank.originate_loan(
                    "household", household.household_id, amount, rate, term_ticks,
                )
                loan["subtype"] = "medical"
                household.medical_loan_bank_serviced = True
                household.cash_balance += amount
                household.add_ledger_flow("bank", amount)
                household.medical_loan_principal = amount
                household.medical_loan_remaining = loan["remaining"]
                household.medical_loan_payment_per_tick = loan["payment_per_tick"]
                return True
            else:
                # Circuit breaker — try government-backed through bank
                loan = bank.issue_government_backed_loan(
                    "household", household.household_id, amount, rate,
                    term_ticks, self.government,
                )
                if loan is not None:
                    loan["subtype"] = "medical"
                    household.medical_loan_bank_serviced = True
                    household.cash_balance += amount
                    household.add_ledger_flow("bank", amount)
                    household.medical_loan_principal = amount
                    household.medical_loan_remaining = loan["remaining"]
                    household.medical_loan_payment_per_tick = loan["payment_per_tick"]
                    return True

        # No bank — use household's own take_medical_loan (simple implementation)
        # But only if they're employed (existing guard from the method).
        # take_medical_loan credits cash with no lender debit, so it must not
        # run when a bank exists and declined: the visit is then unfunded.
        if bank is None and household.is_employed:
            household.take_medical_loan(amount)
            return True

        return False

    # -------------------------------------------------------------------------
    # Section: Policy adjustment, statistics, and economic metrics
    # -------------------------------------------------------------------------
    def _adjust_government_policy(self) -> None:
        """
        Size the government's transfer budget from the unemployed count.

        Mutates state.
        """
        if not self.households:
            return

        unemployed = sum(1 for h in self.households if not h.is_employed)
        self.government.adjust_policies(num_unemployed=unemployed)

    def _update_statistics(self, per_firm_sales: Dict[int, Dict[str, float]]) -> None:
        """
        Update world-level statistics for next tick.

        Args:
            per_firm_sales: Sales data from this tick
        """
        self.last_tick_unmet_demand_by_firm = dict(self.current_tick_unmet_demand_by_firm)

        # Update firm-level stats
        for firm in self.firms:
            sales_data = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})

            self.last_tick_sales_units[firm.firm_id] = sales_data["units_sold"]
            self.last_tick_revenue[firm.firm_id] = sales_data["revenue"]

            # Compute sell-through rate
            units_sold = sales_data["units_sold"]
            if (firm.good_category or "").lower() == "services":
                total_available = max(float(firm.last_units_produced), 1.0)
            else:
                ending_inventory = firm.inventory_units
                total_available = max(units_sold + ending_inventory, 1.0)
            sell_through_rate = units_sold / total_available

            self.last_tick_sell_through_rate[firm.firm_id] = sell_through_rate

        # Update prices by good (simple approach: use current firm prices)
        # Could be quantity-weighted if multiple firms per good
        good_prices: Dict[str, List[float]] = {}
        for firm in self.firms:
            if firm.good_name not in good_prices:
                good_prices[firm.good_name] = []
            good_prices[firm.good_name].append(firm.price)

        # Average price per good (deterministic)
        for good_name, prices in good_prices.items():
            self.last_tick_prices[good_name] = sum(prices) / len(prices)

    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate the Gini coefficient for wealth inequality.

        The Gini coefficient ranges from 0 (perfect equality) to 1 (perfect inequality).
        Uses the standard formula: G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n

        Args:
            values: List of wealth values (e.g., household cash balances)

        Returns:
            Gini coefficient between 0.0 and 1.0
        """
        if not values:
            return 0.0

        # Sort values in ascending order
        return self._gini_from_sorted(sorted(values))

    @staticmethod
    def _gini_from_sorted(sorted_values: List[float]) -> float:
        """Gini coefficient of values already sorted ascending (see _calculate_gini_coefficient)."""
        n = len(sorted_values)
        if n == 0:
            return 0.0

        # Handle edge cases
        if n == 1:
            return 0.0

        total_wealth = sum(sorted_values)
        if total_wealth <= 0:
            return 0.0

        # Calculate Gini using the standard formula
        # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
        cumsum = 0.0
        for i, value in enumerate(sorted_values, start=1):
            cumsum += i * value

        gini = (2.0 * cumsum) / (n * total_wealth) - (n + 1.0) / n

        # Clamp to valid range [0, 1]
        return max(0.0, min(1.0, gini))

    def get_economic_metrics(self) -> Dict[str, float]:
        """
        Calculate comprehensive economic metrics for monitoring and display.

        Returns:
            Dictionary with economic indicators including GDP, unemployment,
            wages, firm metrics, household metrics, and government finances.

        Note:
            SOLID VIOLATION - Single Responsibility Principle (SRP):
            This method is ~400 lines and calculates EVERY possible metric:
            1. Household metrics (employment, wages, cash, wealth inequality)
            2. Firm metrics (cash, inventory, employees, prices, quality)
            3. Government metrics (lever settings, budget pressure, finances)
            4. Bank metrics (reserves, deposits, loans, interest rates)
            5. Capital stock and investment metrics
            6. Welfare and wellbeing metrics
            7. Labor market diagnostics
            8. Firm distress diagnostics
            This should be broken into: _calculate_household_metrics(),
            _calculate_firm_metrics(), _calculate_government_metrics(),
            _calculate_bank_metrics(), etc.

            SOLID VIOLATION - Open/Closed Principle (OCP):
            Adding a new metric requires modifying this method. Should use
            a plugin/strategy pattern where metrics are registered.
        """
        metrics = {}

        # Household metrics
        if self.households:
            # One pass for the employment and work-ability counts.
            employed_households = []
            can_work_count = 0
            labor_force_unemployed_count = 0
            for h in self.households:
                is_employed = h.is_employed
                if is_employed:
                    employed_households.append(h)
                if h.can_work:
                    can_work_count += 1
                    if not is_employed:
                        labor_force_unemployed_count += 1
            household_count = len(self.households)
            unemployed_count = household_count - len(employed_households)
            cannot_work_count = household_count - can_work_count

            metrics["total_households"] = household_count
            metrics["employed_count"] = len(employed_households)
            metrics["unemployed_count"] = unemployed_count
            metrics["labor_force_size"] = float(can_work_count)
            metrics["cannot_work_count"] = float(cannot_work_count)
            metrics["cannot_work_rate"] = cannot_work_count / household_count
            labor_force_unemployment_rate = (
                labor_force_unemployed_count / can_work_count
                if can_work_count
                else 0.0
            )
            jobless_rate_total_population = unemployed_count / household_count
            metrics["labor_force_unemployment_rate"] = labor_force_unemployment_rate
            metrics["jobless_rate_total_population"] = jobless_rate_total_population
            metrics["unemployment_rate"] = (
                jobless_rate_total_population
                if bool(CONFIG.government.count_cannot_work_as_unemployed)
                else labor_force_unemployment_rate
            )
            metrics["recession_warning"] = float(
                metrics["labor_force_unemployment_rate"]
                >= float(CONFIG.government.recession_policy_warning_unemployment_threshold)
            )

            # Wage statistics
            if employed_households:
                wages = [h.wage for h in employed_households]
                metrics["mean_wage"] = sum(wages) / len(wages)
                metrics["median_wage"] = float(np.median(wages))
                metrics["min_wage"] = min(wages)
                metrics["max_wage"] = max(wages)
                min_wage_floor = float(self.government.get_minimum_wage())
                floor_bound = sum(1 for h in employed_households if h.wage <= min_wage_floor + 1e-9)
                metrics["wage_floor_binding_share"] = floor_bound / len(employed_households)
            else:
                metrics["mean_wage"] = 0.0
                metrics["median_wage"] = 0.0
                metrics["min_wage"] = 0.0
                metrics["max_wage"] = 0.0
                metrics["wage_floor_binding_share"] = 0.0

            food_spend = [float(getattr(h, "last_food_spend", 0.0) or 0.0) for h in self.households]
            metrics["household_food_spend_total"] = float(sum(food_spend))
            metrics["household_food_spend_mean"] = float(sum(food_spend) / len(food_spend)) if food_spend else 0.0

            # Household cash/wealth. The total is summed in household order as
            # before; one sorted copy serves the median, Gini, percentiles and
            # shares (order statistics do not depend on input order). sorted()
            # keeps the original objects: builtin sum() compensates only for
            # exact floats, so converting np.float64 to float changes its result.
            household_cash = [h.cash_balance for h in self.households]
            total_household_cash = sum(household_cash)
            sorted_cash = sorted(household_cash)
            sorted_cash_arr = np.array(sorted_cash, dtype=np.float64)
            metrics["total_household_cash"] = total_household_cash
            metrics["mean_household_cash"] = total_household_cash / len(household_cash)
            metrics["median_household_cash"] = float(np.median(sorted_cash_arr))

            # Wealth inequality - Gini coefficient
            metrics["gini_coefficient"] = self._gini_from_sorted(sorted_cash)

            # Wealth distribution percentiles
            p10, p25, p50, p75, p90, p99 = np.percentile(sorted_cash_arr, [10, 25, 50, 75, 90, 99])
            metrics["wealth_p10"] = float(p10)
            metrics["wealth_p25"] = float(p25)
            metrics["wealth_p50"] = float(p50)
            metrics["wealth_p75"] = float(p75)
            metrics["wealth_p90"] = float(p90)
            metrics["wealth_p99"] = float(p99)

            # Top vs bottom wealth shares
            total_wealth = total_household_cash
            if total_wealth > 0:
                n = len(sorted_cash)
                top_10_percent = sorted_cash[int(n * 0.9):]
                bottom_50_percent = sorted_cash[:int(n * 0.5)]
                metrics["top_10_percent_share"] = sum(top_10_percent) / total_wealth
                metrics["bottom_50_percent_share"] = sum(bottom_50_percent) / total_wealth
            else:
                metrics["top_10_percent_share"] = 0.0
                metrics["bottom_50_percent_share"] = 0.0

            # Wellbeing metrics
            metrics["mean_happiness"] = sum(h.happiness for h in self.households) / len(self.households)
            metrics["mean_morale"] = sum(h.morale for h in self.households) / len(self.households)
            metrics["mean_health"] = sum(h.health for h in self.households) / len(self.households)

            # Skills
            metrics["mean_skills"] = sum(h.skills_level for h in self.households) / len(self.households)
        else:
            metrics.update({
                "total_households": 0, "employed_count": 0, "unemployed_count": 0,
                "unemployment_rate": 0.0, "mean_wage": 0.0, "median_wage": 0.0,
                "min_wage": 0.0, "max_wage": 0.0, "total_household_cash": 0.0,
                "mean_household_cash": 0.0, "median_household_cash": 0.0,
                "gini_coefficient": 0.0, "wealth_p10": 0.0, "wealth_p25": 0.0,
                "wealth_p50": 0.0, "wealth_p75": 0.0, "wealth_p90": 0.0, "wealth_p99": 0.0,
                "top_10_percent_share": 0.0, "bottom_50_percent_share": 0.0,
                "mean_happiness": 0.0, "mean_morale": 0.0, "mean_health": 0.0,
                "mean_skills": 0.0, "wage_floor_binding_share": 0.0
            })
            metrics["labor_force_size"] = 0.0
            metrics["cannot_work_count"] = 0.0
            metrics["cannot_work_rate"] = 0.0
            metrics["labor_force_unemployment_rate"] = 0.0
            metrics["jobless_rate_total_population"] = 0.0
            metrics["recession_warning"] = 0.0

        metrics["healthcare_queue_depth"] = float(self.last_health_diagnostics.get("healthcare_queue_depth", 0.0))
        metrics["healthcare_completed_count"] = float(self.last_health_diagnostics.get("healthcare_completed_count", 0.0))
        metrics["healthcare_denied_count"] = float(self.last_health_diagnostics.get("healthcare_denied_count", 0.0))
        metrics["housing_unaffordable_count"] = float(self.last_housing_diagnostics.get("housing_unaffordable_count", 0.0))
        metrics["homeless_household_count"] = float(self.last_housing_diagnostics.get("homeless_household_count", 0.0))

        # Optional labor diagnostics to explain unemployment/search dynamics.
        if self.last_labor_diagnostics:
            metrics.update(self.last_labor_diagnostics)
        else:
            metrics.update({
                "labor_unemployed_total": 0.0,
                "labor_seekers_total": 0.0,
                "labor_cannot_work": 0.0,
                "labor_unemployed_not_searching": 0.0,
                "labor_seekers_wage_ineligible": 0.0,
                "labor_seekers_medical_only": 0.0,
                "labor_max_wage_offer": 0.0,
                "labor_forced_search_adjustments": 0.0,
                "labor_reservation_clamp_adjustments": 0.0,
            })
        metrics.setdefault("labor_forced_search_adjustments", 0.0)
        metrics.setdefault("labor_reservation_clamp_adjustments", 0.0)
        if self.last_firm_distress_diagnostics:
            metrics.update(self.last_firm_distress_diagnostics)
        else:
            metrics.update({
                "burn_mode_firm_count": 0.0,
                "survival_mode_firm_count": 0.0,
                "zero_cash_firm_count": 0.0,
                "weak_demand_firm_count": 0.0,
                "inventory_pressure_firm_count": 0.0,
                "failed_hiring_firm_count": 0.0,
                "failed_hiring_roles_count": 0.0,
                "distressed_firm_count": 0.0,
                "distressed_food_firms": 0.0,
                "distressed_housing_firms": 0.0,
                "distressed_services_firms": 0.0,
                "distressed_healthcare_firms": 0.0,
                "bankruptcy_count": 0.0,
            })

        # Firm metrics
        if self.firms:
            firm_cash = [f.cash_balance for f in self.firms]
            metrics["total_firms"] = len(self.firms)
            metrics["total_firm_cash"] = sum(firm_cash)
            metrics["mean_firm_cash"] = sum(firm_cash) / len(firm_cash)
            metrics["median_firm_cash"] = float(np.median(firm_cash))

            # Inventory
            total_inventory = sum(f.inventory_units for f in self.firms)
            metrics["total_firm_inventory"] = total_inventory

            # Employees
            total_employees = sum(len(f.employees) for f in self.firms)
            metrics["total_employees"] = total_employees
            public_works_firms = [f for f in self.firms if (f.good_category or "").lower() == "publicworks"]
            metrics["public_works_firms"] = len(public_works_firms)
            metrics["public_works_jobs"] = sum(len(f.employees) for f in public_works_firms)

            # Prices
            prices = [f.price for f in self.firms]
            metrics["mean_price"] = sum(prices) / len(prices)
            metrics["median_price"] = float(np.median(prices))

            # Quality
            raw_qualities = [f.quality_level for f in self.firms]
            effective_qualities = [self._effective_firm_quality(f) for f in self.firms]
            metrics["mean_quality"] = sum(raw_qualities) / len(raw_qualities)
            metrics["effective_mean_quality"] = sum(effective_qualities) / len(effective_qualities)
        else:
            metrics.update({
                "total_firms": 0, "total_firm_cash": 0.0, "mean_firm_cash": 0.0,
                "median_firm_cash": 0.0, "total_firm_inventory": 0.0,
                "total_employees": 0, "mean_price": 0.0, "median_price": 0.0,
                "mean_quality": 0.0, "effective_mean_quality": 0.0,
                "public_works_firms": 0, "public_works_jobs": 0
            })

        # GDP calculation (sum of all firm revenues this tick)
        gdp_this_tick = sum(self.last_tick_revenue.values())
        metrics["gdp_this_tick"] = gdp_this_tick

        # Government metrics — lever settings (action space)
        gov = self.government
        metrics["gov_investment_tax_rate"] = gov.investment_tax_rate
        metrics["gov_benefit_level"] = gov.benefit_level
        metrics["gov_public_works"] = gov.public_works_toggle
        metrics["gov_minimum_wage_policy"] = gov.minimum_wage_policy
        metrics["gov_sector_subsidy_target"] = gov.sector_subsidy_target
        metrics["gov_sector_subsidy_level"] = gov.sector_subsidy_level
        metrics["gov_infrastructure_spending"] = gov.infrastructure_spending
        metrics["gov_technology_spending"] = gov.technology_spending
        metrics["gov_social_spending"] = gov.social_spending
        metrics["gov_price_stabilization_target"] = gov.price_stabilization_target
        metrics["gov_price_stabilization_level"] = gov.price_stabilization_level
        metrics["gov_rent_stabilization_level"] = gov.rent_stabilization_level
        metrics["gov_bailout_policy"] = gov.bailout_policy
        metrics["gov_bailout_target"] = gov.bailout_target
        metrics["gov_bailout_budget"] = float(gov.bailout_budget)

        # Government metrics — derived numeric parameters
        metrics["government_cash"] = gov.cash_balance
        metrics["wage_tax_rate"] = gov.wage_tax_rate
        metrics["profit_tax_rate"] = gov.profit_tax_rate
        metrics["unemployment_benefit"] = gov.unemployment_benefit_level
        metrics["transfer_budget"] = gov.transfer_budget
        metrics["minimum_wage_floor"] = gov._minimum_wage_floor

        # Government metrics — budget pressure
        metrics["deficit_ratio"] = max(0.0, -gov.cash_balance) / max(metrics["gdp_this_tick"], 1.0)
        metrics["fiscal_pressure"] = gov.fiscal_pressure
        metrics["fiscal_pressure_instant_ratio"] = self.last_fiscal_pressure_instant_ratio
        metrics["fiscal_pressure_denominator_gdp"] = self.last_fiscal_pressure_denominator_gdp
        metrics["spending_efficiency"] = gov.spending_efficiency
        metrics["gov_revenue_this_tick"] = gov.last_tick_revenue
        metrics["gov_spending_this_tick"] = gov.last_tick_spending
        metrics["gov_net_flow_this_tick"] = gov.last_tick_revenue - gov.last_tick_spending
        metrics["gov_transfer_spend_this_tick"] = self.last_tick_gov_transfers
        metrics["gov_infrastructure_spend_this_tick"] = self.last_tick_gov_infrastructure_spending
        metrics["gov_technology_spend_this_tick"] = self.last_tick_gov_technology_spending
        metrics["gov_social_spend_this_tick"] = self.last_tick_gov_social_spending
        metrics["gov_bond_purchases_this_tick"] = self.last_tick_gov_bond_purchases
        metrics["gov_public_works_capitalization_this_tick"] = self.last_tick_gov_public_works_capitalization
        metrics["gov_public_works_requested_startup_this_tick"] = self.last_tick_gov_public_works_requested_startup
        metrics["gov_public_works_denied_by_budget_this_tick"] = self.last_tick_gov_public_works_denied_by_budget
        metrics["gov_public_works_affordable_budget_this_tick"] = self.last_tick_gov_public_works_affordable_budget
        metrics["gov_public_works_jobs_authorized"] = float(self.last_tick_gov_public_works_jobs_authorized)
        metrics["gov_post_warmup_stimulus_this_tick"] = self.last_tick_gov_post_warmup_stimulus
        metrics["gov_subsidy_spend_this_tick"] = self.last_tick_gov_subsidies
        metrics["gov_subsidy_cap_this_tick"] = self.sector_subsidy_cap_this_tick
        metrics["gov_subsidy_remaining_this_tick"] = self.sector_subsidy_remaining_this_tick
        metrics["gov_subsidy_requested_this_tick"] = self.last_tick_gov_subsidy_requested
        metrics["gov_subsidy_denied_by_cap_this_tick"] = self.last_tick_gov_subsidy_denied_by_cap
        metrics["gov_bailout_spend_this_tick"] = self.last_tick_gov_bailouts
        metrics["working_capital_budget_this_tick"] = float(self.last_tick_working_capital_budget)
        metrics["working_capital_candidates_this_tick"] = float(self.last_tick_working_capital_candidates)
        metrics["working_capital_issued_this_tick"] = float(self.last_tick_working_capital_issued)
        metrics["working_capital_denied_budget_this_tick"] = float(self.last_tick_working_capital_denied_budget)
        metrics["price_stabilization_active_sector"] = gov.price_stabilization_target
        metrics["price_stabilization_level"] = gov.price_stabilization_level
        metrics["rent_stabilization_level"] = gov.rent_stabilization_level
        metrics["price_increase_limited_count"] = float(self.price_increase_limited_count)
        metrics["rent_increase_limited_count"] = float(self.rent_increase_limited_count)
        metrics["avg_sector_price_to_median_wage"] = float(self.avg_sector_price_to_median_wage)
        metrics["housing_rent_to_median_wage"] = float(self.housing_rent_to_median_wage)
        recent_gdp = trailing_gdp(self)
        metrics["recent_gdp"] = recent_gdp
        metrics["public_debt"] = float(getattr(gov, "public_debt", 0.0))
        metrics["annualized_debt_to_gdp"] = annualized_debt_to_gdp(gov, recent_gdp)
        metrics["bailout_budget_remaining"] = float(gov.bailout_budget_remaining)
        metrics["bailout_cycle_disbursed"] = float(gov.bailout_cycle_disbursed)
        metrics["bailout_cycle_firms_assisted"] = float(gov.bailout_cycle_firms_assisted)
        metrics["last_cycle_bailout_authorized"] = float(gov.last_cycle_bailout_authorized)
        metrics["last_cycle_bailout_disbursed"] = float(gov.last_cycle_bailout_disbursed)
        metrics["last_cycle_bailout_remaining"] = float(gov.last_cycle_bailout_remaining)
        metrics["last_cycle_bailout_firms_assisted"] = float(gov.last_cycle_bailout_firms_assisted)
        metrics["bailout_eligible_firms_by_sector"] = dict(self.bailout_eligible_firms_by_sector)
        metrics["bailout_denied_firms_by_reason"] = dict(self.bailout_denied_firms_by_reason)
        metrics["bailout_received_by_firm_id"] = {
            str(firm_id): float(amount)
            for firm_id, amount in self.bailout_received_by_firm_id.items()
        }
        metrics["last_tick_bailout_disbursed"] = float(gov.last_tick_bailout_disbursed)
        metrics["last_tick_bailout_firms_assisted"] = float(gov.last_tick_bailout_firms_assisted)
        metrics["last_tick_bailout_sector_spend"] = dict(gov.last_tick_bailout_sector_spend)

        # Infrastructure / technology multipliers
        metrics["infrastructure_productivity"] = gov.infrastructure_productivity_multiplier
        metrics["technology_quality"] = gov.technology_quality_multiplier
        metrics["social_happiness"] = gov.social_happiness_multiplier
        metrics["social_investment_budget"] = gov.social_investment_budget
        metrics["warmup_active"] = 1.0 if self.in_warmup else 0.0
        metrics["warmup_ticks_remaining"] = float(max(0, self.warmup_ticks - self.current_tick))
        metrics["queued_firms_count"] = float(len(self.queued_firms))

        # Bank metrics (optional)
        if self.bank is not None:
            bank = self.bank
            metrics["bank_cash_reserves"] = bank.cash_reserves
            metrics["bank_total_deposits"] = bank.total_deposits
            metrics["bank_total_loans_outstanding"] = bank.total_loans_outstanding
            metrics["bank_base_interest_rate"] = bank.base_interest_rate
            metrics["bank_deposit_rate"] = bank.deposit_rate
            metrics["bank_loan_loss_provision"] = bank.loan_loss_provision
            metrics["bank_active_loan_count"] = len(bank.active_loans)
            metrics["bank_can_lend"] = 1.0 if bank.can_lend() else 0.0
            metrics["bank_lendable_cash"] = bank.lendable_cash
            metrics["bank_new_loans_this_tick"] = bank.last_tick_new_loans
            metrics["bank_defaults_this_tick"] = bank.last_tick_defaults
            metrics["bank_repayments_this_tick"] = bank.last_tick_repayments
            metrics["bank_deposit_interest_this_tick"] = bank.last_tick_deposit_interest_paid
            metrics["bank_interest_income_this_tick"] = bank.last_tick_interest_income
            metrics["bank_reserve_ratio_actual"] = (
                bank.cash_reserves / max(bank.total_deposits, 1.0)
            )
            # Average credit scores
            firm_scores = list(bank.firm_credit_scores.values())
            hh_scores = list(bank.household_credit_scores.values())
            metrics["bank_avg_credit_score_firms"] = (
                sum(firm_scores) / len(firm_scores) if firm_scores else 0.5
            )
            metrics["bank_avg_credit_score_households"] = (
                sum(hh_scores) / len(hh_scores) if hh_scores else 0.5
            )

        # Fix 21: Capital stock metrics
        if self.firms:
            capital_stocks = [f.capital_stock for f in self.firms]
            metrics["total_capital_stock"] = sum(capital_stocks)
            metrics["avg_capital_per_firm"] = sum(capital_stocks) / len(capital_stocks)
            total_invest = sum(f.capital_investment_this_tick for f in self.firms)
            metrics["total_investment_this_tick"] = total_invest
            gdp = metrics.get("gdp_this_tick", 1.0)
            metrics["investment_as_pct_of_gdp"] = (
                total_invest * CONFIG.firms.capital_cost_per_unit / max(gdp, 1.0)
            )
        else:
            metrics["total_capital_stock"] = 0.0
            metrics["avg_capital_per_firm"] = 0.0
            metrics["total_investment_this_tick"] = 0.0
            metrics["investment_as_pct_of_gdp"] = 0.0

        # Fix 23: Firm distress distribution
        if self.firms:
            healthy = sum(1 for f in self.firms if not f.survival_mode and not f.burn_mode)
            metrics["firm_healthy_count"] = healthy
            metrics["firm_survival_mode_count"] = sum(1 for f in self.firms if f.survival_mode)
            metrics["firm_burn_mode_count"] = sum(1 for f in self.firms if f.burn_mode)
            wage_bills = []
            for f in self.firms:
                wb = sum(f.actual_wages.values()) if f.actual_wages else (len(f.employees) * f.wage_offer)
                if wb > 0:
                    wage_bills.append(f.cash_balance / wb)
            metrics["avg_runway_weeks"] = sum(wage_bills) / len(wage_bills) if wage_bills else 0.0

        # Fix 23: Quality by sector
        if self.firms:
            # One grouping pass; firms keep their self.firms order within a category.
            firms_by_category: Dict[str, List[FirmAgent]] = {}
            for f in self.firms:
                firms_by_category.setdefault(f.good_category, []).append(f)
            for cat, cat_firms in firms_by_category.items():
                metrics[f"avg_quality_{cat.lower()}"] = (
                    sum(f.quality_level for f in cat_firms) / len(cat_firms)
                )
            total_rd = sum(getattr(f, "accumulated_rd_investment", 0.0) for f in self.firms)
            metrics["total_rd_spending_lifetime"] = total_rd

        # Fix 23: Wage dynamics
        if self.households:
            employed_hh = [h for h in self.households if h.is_employed and h.wage > 0]
            if employed_hh:
                wages_list = [h.wage for h in employed_hh]
                total_wages = sum(wages_list)
                total_rev = gdp_this_tick
                metrics["labor_share_of_revenue"] = total_wages / max(total_rev, 1.0)
            else:
                metrics["labor_share_of_revenue"] = 0.0

            # Household welfare
            metrics["avg_savings_rate"] = (
                sum(h.savings_rate_target for h in self.households) / len(self.households)
            )
            metrics["total_bank_deposits"] = sum(h.bank_deposit for h in self.households)
            poverty_threshold = gov.min_cash_threshold
            metrics["households_below_poverty"] = sum(
                1 for h in self.households if h.cash_balance < poverty_threshold
            )

        # Money supply and drift (Fix 23: core macro signal)
        bank_reserves = self.bank.cash_reserves if self.bank is not None else 0.0
        metrics["total_economy_cash"] = (
            metrics.get("total_household_cash", 0.0) +
            metrics.get("total_firm_cash", 0.0) +
            metrics["government_cash"] +
            bank_reserves
        )
        if self.payment_sequence != "legacy":
            metrics["total_economy_cash"] += self.misc_firm_revenue + sum(f.cash_balance for f in self.queued_firms)
            metrics["total_economy_cash"] += sum(self.payment_state["recovery_holds"].values())
            metrics["total_economy_cash"] += self.payment_state.get("housing_equal_distribution_hold", 0.0)
            if not self.payment_state.get("capital_routes_released", True):
                metrics["total_economy_cash"] += sum(row["amount"] for row in self.payment_state.get("capital_routes", ()))
            if self.payment_book is not None:
                metrics["total_economy_cash"] += (
                    self.payment_book.clearing_cash
                    + sum(self.payment_state["ceo_holds"].values())
                    + sum(self.payment_book.late_income.values())
                    + sum(self.payment_book.medical_funding_pending.values())
                )
        metrics["money_supply"] = metrics["total_economy_cash"]
        if self.payment_sequence != "legacy" and self.payment_book is not None:
            from payment_reporting import payment_snapshot
            book = self.payment_book
            metrics["payment"] = payment_snapshot(self)
            metrics["payment_unpaid_employed_count"] = len(book.unpaid_employed)
            metrics["payment_unpaid_employed_shortfall"] = sum(
                float(row["shortfall"]) for row in book.unpaid_employed.values())
            metrics["payment_denied_benefits"] = float(book.denied_benefits)
            metrics["payment_denied_outlays"] = sum(
                float(value) for value in self.payment_denied_outlays.values())
            metrics["payment_exit_recovery"] = float(getattr(book, "exit_recovery", 0.0))
            metrics["payment_exit_worker_writeoff"] = float(getattr(book, "exit_worker_writeoff", 0.0))
            metrics["payment_wage_claims_outstanding"] = sum(
                float(value) for value in self.payment_state["wage_claims"].values())

        # Current tick
        metrics["current_tick"] = self.current_tick

        return metrics
