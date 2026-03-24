"""
Economy Simulation Engine

Implements the main simulation coordinator that orchestrates households,
firms, and government through tick-based cycles. Includes optional
stochastic shocks for scenario variation across runs.

Performance optimizations:
- Caches household/firm lookups for O(1) access
- Uses NumPy vectorization for labor and goods market operations
- Batch operations to minimize Python loop overhead
"""

import logging
import os
import random
from typing import Dict, List, Tuple, Optional

from config import CONFIG
import numpy as np
import math
from agents import HouseholdAgent, FirmAgent, GovernmentAgent, _get_good_category

logger = logging.getLogger(__name__)


class Economy:
    """
    Main simulation coordinator for the economic model.

    Orchestrates all agents through a strict plan/apply cycle with
    deterministic labor and goods market clearing.
    """

    def __init__(
        self,
        households: List[HouseholdAgent],
        firms: List[FirmAgent],
        government: GovernmentAgent,
        queued_firms: Optional[List[FirmAgent]] = None
    ):
        """
        Initialize the economy with pre-constructed agents.

        Args:
            households: List of household agents
            firms: List of firm agents
            government: Government agent instance
        """
        self.households = households
        self.firms = firms
        self.government = government
        self.config = CONFIG
        self.queued_firms: List[FirmAgent] = queued_firms or []
        self.target_total_firms = 0
        self._refresh_target_total_firms()
        self.large_market = len(self.households) >= CONFIG.firms.large_market_household_threshold

        mode_cfg = CONFIG.modes
        self.enable_household_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.household_stabilizers
        self.enable_firm_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.firm_stabilizers
        self.enable_government_stabilizers = mode_cfg.stabilization_enabled and mode_cfg.government_stabilizers

        # Track simulation progression and warm-up period state
        self.current_tick = 0
        self.in_warmup = True
        self.post_warmup_cooldown = 0

        # Performance optimization: Cache lookups for O(1) access
        self.household_lookup: Dict[int, HouseholdAgent] = {h.household_id: h for h in households}
        self.firm_lookup: Dict[int, FirmAgent] = {f.firm_id: f for f in firms}

        # Cache wage percentiles to avoid repeated sorting
        self.cached_wage_percentiles: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # low, mid, high
        self.wage_percentile_cache_tick: int = -1

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
        self.performance_mode = False
        self._cached_consumption_plans: Dict[int, Dict] = {}

        # Set initial defaults
        for firm in firms:
            self.last_tick_sales_units[firm.firm_id] = 0.0
            self.last_tick_revenue[firm.firm_id] = 0.0
            self.last_tick_sell_through_rate[firm.firm_id] = 0.5  # neutral default
            self.last_tick_prices[firm.good_name] = firm.price

        # Misc firm: redistributes investment/R&D spending to random households
        self.misc_firm_revenue: float = 0.0  # Accumulated investment money
        self.misc_firm_beneficiaries: List[int] = []  # household_ids who receive payouts
        self._initialize_misc_firm_beneficiaries()
        self.post_warmup_stimulus_ticks: int = 0
        self.post_warmup_stimulus_duration: int = 0
        self.healthcare_requests_this_tick: float = 0.0
        self.healthcare_attempted_slots_this_tick: float = 0.0
        self.healthcare_completed_visits_this_tick: float = 0.0
        self.healthcare_affordability_rejects_this_tick: float = 0.0
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
        self.last_labor_diagnostics: Dict[str, float] = {}
        self.last_labor_plan_adjustments: Dict[str, float] = {}
        self._labor_compare_mismatch_count = 0
        self._propagate_stabilizer_flags()

    def _propagate_stabilizer_flags(self) -> None:
        """Push stabilizer flags down to agents."""
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
        """Enable or disable stabilizers for each agent type."""
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

    def _batch_plan_consumption(
        self,
        market_prices: Dict[str, float],
        category_market_snapshot: Dict[str, List[Dict[str, float]]],
        good_category_lookup: Optional[Dict[str, str]] = None,
        unemployment_rate: float = 0.0
    ) -> Dict[int, Dict]:
        """
        Vectorized batch consumption planning for all households.

        Replaces 10k individual calls to household.plan_consumption() with NumPy operations.
        Returns identical results to individual calls, but 10-20x faster.
        """
        cat_lk = good_category_lookup or {}
        def is_housing_good(good: str) -> bool:
            return cat_lk.get(good, good.lower()) == "housing"

        # Extract household attributes as NumPy arrays
        cash_balances = np.array([h.cash_balance for h in self.households], dtype=np.float64)
        spending_tendencies = np.array([h.spending_tendency for h in self.households], dtype=np.float64)
        frugalities = np.array([max(h.frugality, 0.1) for h in self.households], dtype=np.float64)
        goods_values = np.array([sum(h.goods_inventory.values()) for h in self.households], dtype=np.float64)
        food_prefs = np.array([h.food_preference for h in self.households], dtype=np.float64)
        housing_prefs = np.array([h.housing_preference for h in self.households], dtype=np.float64)
        services_prefs = np.array([h.services_preference for h in self.households], dtype=np.float64)

        # H2: Subsistence vs discretionary spending with happiness modulation

        # Macro confidence from unemployment
        macro_confidence = max(0.2, 1.0 - 0.6 * unemployment_rate)

        # Micro confidence from happiness (vectorized)
        happiness_arr = np.array([h.happiness for h in self.households], dtype=np.float64)
        micro_confidence = happiness_arr

        # Combined confidence
        confidence = 0.5 * macro_confidence + 0.5 * micro_confidence

        # Base spending rate as function of confidence
        base_spend = 0.5 + 0.3 * confidence  # 0.5-0.8 range

        # H5: Happiness modulates spending (±10% adjustment)
        happiness_multiplier = 0.9 + 0.2 * happiness_arr  # 0.9-1.1 range
        base_spend = base_spend * happiness_multiplier

        # Clamp to configured bounds
        base_spend = np.clip(base_spend, CONFIG.households.min_spend_fraction,
                           CONFIG.households.max_spend_fraction)

        # H3: Wealth and employment affect saving behavior
        net_worth_est = cash_balances + goods_values * 5.0

        # Normalized wealth score [0, 1]
        wealth_scores = np.clip(
            (net_worth_est - CONFIG.households.low_wealth_reference) /
            max(1.0, CONFIG.households.high_wealth_reference - CONFIG.households.low_wealth_reference),
            0.0, 1.0
        )

        # Wealth factor: richer households save more (0.8-1.2x multiplier)
        wealth_factor = 0.8 + 0.4 * wealth_scores

        # Trait factor
        trait_multiplier = np.clip(spending_tendencies / frugalities, 0.6, 1.4)

        # H3: Employment status adjustment
        # Employed: can save more, but also consume more if happy
        # Unemployed: forced dissaving if poor + long-term unemployed
        employment_status = np.array([h.is_employed for h in self.households], dtype=bool)
        unemployment_duration = np.array([h.unemployment_duration for h in self.households], dtype=np.float64)

        # Employed factor: slightly higher spending if happy
        employed_factor = 1.0 + 0.3 * wealth_scores - 0.2 * happiness_arr

        # Unemployed factor: forced dissaving if poor and long-term unemployed
        unemployed_poor = net_worth_est < CONFIG.households.unemployed_forced_dissaving_wealth
        unemployed_longterm = unemployment_duration > CONFIG.households.unemployed_forced_dissaving_duration
        forced_dissaving = unemployed_poor & unemployed_longterm
        unemployed_factor = np.where(forced_dissaving, 1.2, 1.0)  # Spend more when forced

        # Apply employment-specific factors
        employment_factor = np.where(employment_status, employed_factor, unemployed_factor)

        # Final spend fraction
        spend_fraction = base_spend * trait_multiplier * wealth_factor * employment_factor
        spend_fraction = np.clip(spend_fraction, 0.0, 1.0)

        # H2: Subsistence floor (always spend minimum if available)
        subsistence_min = CONFIG.households.subsistence_min_cash
        subsistence = np.minimum(cash_balances, subsistence_min)
        discretionary_cash = np.maximum(0.0, cash_balances - subsistence)
        discretionary_budget = discretionary_cash * spend_fraction
        budgets = subsistence + discretionary_budget

        if not getattr(self, "enable_household_stabilizers", True):
            max_frac = CONFIG.households.max_spend_fraction
            budgets = np.maximum(
                subsistence,
                cash_balances * max_frac
            )

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
        category_array_cache: Dict[str, Dict[str, np.ndarray]] = {}
        for category, options in category_option_cache.items():
            firm_ids = np.array([opt["firm_id"] for opt in options], dtype=np.int32)
            prices = np.array([opt["price"] for opt in options], dtype=np.float64)
            qualities = np.array([opt["quality"] for opt in options], dtype=np.float64)
            if firm_ids.size == 0:
                continue
            category_array_cache[category] = {
                "firm_ids": firm_ids,
                "prices": prices,
                "qualities": qualities,
            }

        standard_categories = ["food", "housing", "services"]
        category_weights_matrix = np.array([
            [household.category_weights.get(cat, 0.0) for cat in standard_categories]
            for household in self.households
        ], dtype=np.float64)
        preference_matrix = np.column_stack((food_prefs, housing_prefs, services_prefs))
        biased_matrix = category_weights_matrix * preference_matrix
        precomputed_fractions = []
        for idx, household in enumerate(self.households):
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

        # Build consumption plans (fallback to Python loop for now due to complex logic)
        household_consumption_plans = {}

        for idx, household in enumerate(self.households):
            budget = budgets[idx]

            if budget <= 0:
                household_consumption_plans[household.household_id] = {
                    "household_id": household.household_id,
                    "category_budgets": {},
                    "planned_purchases": {},
                }
                continue

            # Use category weights if available
            if household.category_weights and sum(household.category_weights.values()) > 0 and category_market_snapshot:
                planned_purchases = household._plan_category_purchases(
                    budget,
                    category_market_snapshot,
                    price_cache,
                    category_fraction_override=precomputed_fractions[idx],
                    category_option_cache=category_option_cache,
                    category_array_cache=category_array_cache
                )
                household_consumption_plans[household.household_id] = {
                    "household_id": household.household_id,
                    "category_budgets": {},
                    "planned_purchases": planned_purchases,
                }
            else:
                # Legacy good-based allocation
                local_beliefs = dict(household.price_beliefs)

                # Update beliefs with market prices
                for good, market_price in market_prices.items():
                    if good in local_beliefs:
                        old_belief = local_beliefs[good]
                        local_beliefs[good] = (
                            household.price_expectation_alpha * market_price +
                            (1.0 - household.price_expectation_alpha) * old_belief
                        )
                    else:
                        local_beliefs[good] = market_price

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
                }

        return household_consumption_plans

    def _apply_cached_consumption_plans(self) -> Dict[int, Dict]:
        """Return cached consumption plans when performance mode is enabled."""
        return self._cached_consumption_plans

    def _batch_apply_household_updates(
        self,
        transfer_plan: Dict[int, float],
        wage_taxes: Dict[int, float],
        per_household_purchases: Dict[int, Dict[str, Tuple[float, float]]],
        good_category_lookup: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Optimized batch update of all household states.

        Combines three separate loops into one for better cache locality.
        Eliminates method call overhead by inlining operations.
        """
        hc = CONFIG.households

        # Process loan repayments first (firms pay government)
        total_loan_repayments = 0.0
        for firm in self.firms:
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
        for firm in self.firms:
            if firm.ceo_household_id is not None and firm.employees:
                wages_list = [firm.actual_wages.get(e_id, firm.wage_offer) for e_id in firm.employees]
                median_wage = float(np.median(wages_list))
                ceo_lookup.setdefault(firm.ceo_household_id, []).append((firm, median_wage))

        # Happiness boost lookup: good_name -> boost_per_unit
        happiness_boost_lookup: Dict[str, float] = {}
        for firm in self.firms:
            if firm.happiness_boost_per_unit > 0:
                happiness_boost_lookup[firm.good_name] = firm.happiness_boost_per_unit

        # Category lookup: use provided or empty dict for direct access
        cat_lookup = good_category_lookup or {}

        # Single pass through all households
        for household in self.households:
            hid = household.household_id
            household.met_housing_need = False

            # H4: Record starting cash for anomaly detection
            household.last_tick_cash_start = household.cash_balance

            # Apply income and taxes
            wage_income = household.wage if household.employer_id is not None else 0.0

            # Add CEO salary if household is a CEO of any firm
            ceo_salary = 0.0
            ceo_entries = ceo_lookup.get(hid)
            if ceo_entries:
                for firm, median_wage in ceo_entries:
                    sal = median_wage * 3.0  # CEO earns 3x median worker
                    ceo_salary += sal
                    firm.cash_balance -= sal

            transfers = transfer_plan.get(hid, 0.0)
            taxes_paid = wage_taxes.get(hid, 0.0)

            # H4: Track income components
            household.last_wage_income = wage_income + ceo_salary
            household.last_transfer_income = transfers
            household.last_other_income = -taxes_paid  # Taxes are negative income
            household.last_dividend_income = 0.0  # Will be set if dividends are distributed

            household.cash_balance += wage_income + ceo_salary + transfers - taxes_paid

            # Process medical loan payments (10% of wage per tick)
            medical_payment = household.make_medical_loan_payment()
            if medical_payment > 0:
                # Medical payments go to government (simplified - could go to healthcare provider)
                self.government.cash_balance += medical_payment

            # Apply purchases
            purchases = per_household_purchases.get(hid, {})
            total_spending = 0.0
            for good, (quantity, price_paid) in purchases.items():
                total_cost = quantity * price_paid
                total_spending += total_cost
                household.cash_balance -= total_cost
                category = cat_lookup.get(good, good.lower())
                if category == "housing" and quantity > 0:
                    household.owns_housing = True
                    household.met_housing_need = True

                # Update inventory
                if good not in household.goods_inventory:
                    household.goods_inventory[good] = 0.0
                household.goods_inventory[good] += quantity

                # Update price beliefs
                if good in household.price_beliefs:
                    old_belief = household.price_beliefs[good]
                    household.price_beliefs[good] = (
                        household.price_expectation_alpha * price_paid +
                        (1.0 - household.price_expectation_alpha) * old_belief
                    )
                else:
                    household.price_beliefs[good] = price_paid

            # Consume goods from inventory and track per-category consumption.
            # Food is perishable — consume most of it each tick (spoilage).
            # Services are experiential — consume quickly.
            # Other goods decay at a slower rate.
            housing_usage = 1.0
            food_consumed = 0.0
            services_consumed = 0.0
            for good in list(household.goods_inventory.keys()):
                if household.goods_inventory[good] > 0:
                    category = cat_lookup.get(good, good.lower())
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
                        # Services are experiential: consume all each tick
                        consumed = current_qty
                        household.goods_inventory[good] = 0.0
                        services_consumed += consumed
                        boost = happiness_boost_lookup.get(good, 0.0)
                        if boost > 0:
                            household.happiness = min(1.0, household.happiness + consumed * boost)
                    else:
                        consumed = current_qty * 0.1
                        household.goods_inventory[good] = max(0.0, current_qty - consumed)

                    if household.goods_inventory[good] < 0.001:
                        del household.goods_inventory[good]

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

    def step(self) -> None:
        """
        Execute one full simulation tick.

        Follows strict phase ordering:
        1. Firms plan production, labor, prices, wages
        2. Households plan labor supply and consumption
        3. Labor market matching
        4. Apply labor outcomes
        5. Firms apply production and costs
        6. Goods market clearing
        7. Government plans taxes
        8. Government plans transfers
        9. Apply sales, profits, taxes to firms
        10. Apply income, taxes, transfers, purchases to households
        11. Apply fiscal results to government
        12. Update world-level statistics
        """
        # Update warm-up flag for this tick (first 52 ticks are warm-up)
        was_in_warmup = self.in_warmup
        self.in_warmup = self.current_tick < 52
        if was_in_warmup and not self.in_warmup:
            self.post_warmup_cooldown = 8
            self.post_warmup_stimulus_ticks = 6
            self.post_warmup_stimulus_duration = 6
            self._sync_warmup_expectations(self.last_tick_prices)
            self._reset_post_warmup_expectations()
        self._refresh_target_total_firms()
        if not self.in_warmup:
            self._activate_queued_firms()
        if self.post_warmup_stimulus_ticks > 0:
            self._apply_post_warmup_stimulus()

        # Random economic shocks (stochastic events)
        self._apply_random_shocks()
        self._reset_healthcare_tick_state()
        self._apply_doctor_health_lock()
        self._enqueue_healthcare_requests()

        (
            good_category_lookup,
            category_market_snapshot,
            housing_private_inventory,
            housing_baseline_inventory,
        ) = self._build_firm_market_views()
        total_households = len(self.households)
        housing_inventory_overhang = housing_private_inventory + housing_baseline_inventory
        unemployed_count = sum(1 for h in self.households if not h.is_employed)
        unemployment_rate = (unemployed_count / total_households) if total_households > 0 else 0.0

        gov_benefit = self.government.get_unemployment_benefit_level()

        if self.enable_government_stabilizers:
            # Update outstanding emergency-loan commitments before offering new aid
            self._update_loan_commitments()
            self._offer_emergency_loans(unemployment_rate)
            self._offer_inventory_liquidation_loans()  # No unemployment trigger
            self._ensure_public_works_capacity(unemployment_rate)

        # Phase 1: Firms plan
        firm_production_plans = {}
        firm_price_plans = {}
        firm_wage_plans = {}

        for firm in self.firms:
            # Plan production and labor
            production_plan = firm.plan_production_and_labor(
                self.last_tick_sales_units.get(firm.firm_id, 0.0),
                in_warmup=self.in_warmup,
                total_households=total_households,
                global_unsold_inventory=housing_inventory_overhang,
                private_housing_inventory=housing_private_inventory,
                large_market=self.large_market,
                post_warmup_cooldown=(self.post_warmup_cooldown > 0)
            )
            firm_production_plans[firm.firm_id] = production_plan

            # Plan pricing
            price_plan = firm.plan_pricing(
                self.last_tick_sell_through_rate.get(firm.firm_id, 0.5),
                unemployment_rate=unemployment_rate,
                in_warmup=self.in_warmup
            )
            firm_price_plans[firm.firm_id] = price_plan

            # Plan wage (pass unemployment rate for wage stabilization)
            wage_plan = firm.plan_wage(
                unemployment_rate=unemployment_rate,
                unemployment_benefit=gov_benefit
            )
            firm_wage_plans[firm.firm_id] = wage_plan

            # Healthcare labor is managed out-of-band from market hiring:
            # one healthcare firm staffed by doctor/resident pool.
            if (firm.good_category or "").lower() == "healthcare":
                production_plan["planned_hires_count"] = 0
                production_plan["planned_layoffs_ids"] = []
                firm.planned_hires_count = 0
                firm.planned_layoffs_ids = []

        # Enforce minimum wage floor (government policy)
        minimum_wage = self.government.get_minimum_wage()
        for wage_plan in firm_wage_plans.values():
            if wage_plan["wage_offer_next"] < minimum_wage:
                wage_plan["wage_offer_next"] = minimum_wage

        # Phase 2: Households plan
        household_labor_plans = {}

        for household in self.households:
            household.maybe_active_education()

        # Labor planning still uses loop (small overhead)
        for household in self.households:
            labor_plan = household.plan_labor_supply(gov_benefit)
            household_labor_plans[household.household_id] = labor_plan
        self._normalize_household_labor_plans(household_labor_plans, firm_wage_plans)

        # Consumption planning now vectorized (major speedup)
        if (not self.performance_mode) or (self.current_tick % 5 == 0):
            household_consumption_plans = self._batch_plan_consumption(
                self.last_tick_prices,
                category_market_snapshot,
                good_category_lookup,
                unemployment_rate
            )
            if self.performance_mode:
                self._cached_consumption_plans = household_consumption_plans
        elif self.performance_mode:
            household_consumption_plans = self._apply_cached_consumption_plans()
        else:
            household_consumption_plans = self._batch_plan_consumption(
                self.last_tick_prices,
                category_market_snapshot,
                good_category_lookup,
                unemployment_rate
            )

        # Phase 3: Labor market matching
        firm_labor_outcomes, household_labor_outcomes = self._run_labor_matching(
            firm_production_plans,
            firm_wage_plans,
            household_labor_plans
        )

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

            household.apply_labor_outcome(
                household_labor_outcomes[household.household_id],
                market_wage_anchor=anchor,
                current_tick=self.current_tick
            )

        # Keep firm-side employee rosters aligned with household employment outcomes.
        # This prevents stale counts in firm telemetry versus unemployment metrics.
        self._sync_firm_employee_rosters()

        # Update wages for continuing employees every 50 ticks (small 2-3% increases)
        if self.current_tick % 50 == 0:
            self._update_continuing_employee_wages()

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
                "other_variable_costs": 0.0
            })

            # Update expectations
            firm.apply_updated_expectations(
                production_plan["updated_expected_sales"]
            )

        # Phase 6: Goods market clearing
        per_household_purchases, per_firm_sales = self._clear_goods_market(
            household_consumption_plans,
            self.firms
        )

        # Phase 6.5: Housing rental market clearing
        self._clear_housing_rental_market()
        self._apply_housing_repairs()

        # Phase 6.6: Housing firms consider unit expansion
        for firm in self.firms:
            if firm.good_category == "Housing":
                firm.invest_in_unit_expansion()

        # Phase 6.7: Misc firm operations
        self._misc_firm_add_beneficiary()  # Add 1 more random beneficiary
        self._misc_firm_redistribute_revenue()  # Pay out all accumulated revenue

        # Phase 6.8: Queue-based healthcare service processing
        self._process_healthcare_services(per_firm_sales)

        # Phase 7: Government plans taxes
        household_tax_snapshots = self._build_household_tax_snapshots()
        firm_tax_snapshots = self._build_firm_tax_snapshots(per_firm_sales)
        price_ceiling_tax_by_firm_id = {
            int(snapshot["firm_id"]): float(snapshot.get("price_ceiling_tax", 0.0))
            for snapshot in firm_tax_snapshots
        }
        total_price_ceiling_taxes = sum(price_ceiling_tax_by_firm_id.values())

        tax_plan = self.government.plan_taxes(
            household_tax_snapshots,
            firm_tax_snapshots
        )

        # Phase 8: Government plans transfers
        household_transfer_snapshots = self._build_household_transfer_snapshots()
        transfer_plan = self.government.plan_transfers(household_transfer_snapshots)

        # Phase 9: Apply sales, profits, taxes to firms
        for firm in self.firms:
            sales_data = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
            profit_tax = tax_plan["profit_taxes"].get(firm.firm_id, 0.0)
            property_tax = tax_plan["property_taxes"].get(firm.firm_id, 0.0)
            price_ceiling_tax = price_ceiling_tax_by_firm_id.get(firm.firm_id, 0.0)

            # Pay property tax if housing firm
            if property_tax > 0:
                firm.cash_balance -= property_tax

            firm.apply_sales_and_profit({
                "units_sold": sales_data["units_sold"],
                "revenue": sales_data["revenue"],
                "profit_taxes_paid": profit_tax + price_ceiling_tax
            })

            # Apply price and wage updates
            firm.apply_price_and_wage_updates(
                firm_price_plans[firm.firm_id],
                firm_wage_plans[firm.firm_id]
            )

        # Phase 10: Apply income, taxes, transfers, purchases to households
        self._batch_apply_household_updates(
            transfer_plan,
            tax_plan["wage_taxes"],
            per_household_purchases,
            good_category_lookup
        )

        # Phase 11: Apply government fiscal results
        total_wage_taxes = sum(tax_plan["wage_taxes"].values())
        total_profit_taxes = sum(tax_plan["profit_taxes"].values())
        total_property_taxes = sum(tax_plan["property_taxes"].values())
        total_transfers = sum(transfer_plan.values())

        self.last_tick_gov_wage_taxes = total_wage_taxes
        self.last_tick_gov_profit_taxes = total_profit_taxes + total_price_ceiling_taxes
        self.last_tick_gov_property_taxes = total_property_taxes
        self.last_tick_gov_transfers = total_transfers

        self.government.apply_fiscal_results(
            total_wage_taxes,
            total_profit_taxes + total_price_ceiling_taxes,  # Include price ceiling tax as profit tax
            total_transfers,
            total_property_taxes
        )

        # Phase 11.5: Government bond purchases with surplus (1 household per tick distribution)
        # Redirect bond spending to Misc firm
        govt_investments = self.government.make_investments()
        
        total_govt_investments = sum(govt_investments.values()) if govt_investments else 0.0
        self.last_tick_gov_investments = total_govt_investments
        
        if govt_investments:
            for amount in govt_investments.values():
                self._collect_misc_revenue(amount)

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

        # Phase 11.75: Update household wellbeing (happiness, morale, health)
        if self.in_warmup:
            current_price_snapshot = {firm.good_name: firm.price for firm in self.firms}
            self._sync_warmup_expectations(current_price_snapshot)
        if (not self.performance_mode) or (self.current_tick % 10 == 0):
            self._batch_update_wellbeing(
                happiness_multiplier=self.government.social_happiness_multiplier
            )
        self._apply_doctor_health_lock()

        # Phase 12: Handle firm bankruptcies and exits
        self._handle_firm_exits()

        # Phase 13: Potentially create new firms
        self._maybe_create_new_firms()

        # Phase 14: Government adjusts policies based on economic conditions
        if self.enable_government_stabilizers:
            self._adjust_government_policy()

        # Phase 15: Update world-level statistics
        self._update_statistics(per_firm_sales)

        # Phase 16: Distribute firm profits to owners (dividend payments)
        # This recycles wealth from firms back to households
        total_dividends_paid = 0.0
        for firm in self.firms:
            dividends = firm.distribute_profits(self.household_lookup)
            total_dividends_paid += dividends

        # Advance simulation clock after completing the tick
        self.current_tick += 1
        if self.post_warmup_cooldown > 0:
            self.post_warmup_cooldown -= 1

    def _normalize_household_labor_plans(
        self,
        household_labor_plans: Dict[int, Dict],
        firm_wage_plans: Dict[int, Dict],
    ) -> None:
        """
        De-risk labor plans before matching.

        - Ensure unemployed households that can work are marked as job seekers.
        - Optionally clamp long-term unemployed reservation wages to observable market offers.
        """
        forced_search = 0
        reservation_clamps = 0

        max_wage_offer = max(
            (float(plan.get("wage_offer_next", 0.0)) for plan in firm_wage_plans.values()),
            default=0.0,
        )
        minimum_wage = float(self.government.get_minimum_wage())
        reservation_cap = max(max_wage_offer, minimum_wage)

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
                "actual_wages": {}
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

                # Update household outcome
                household_labor_outcomes[household_id] = {
                    "employer_id": firm_id,
                    "wage": actual_wage,
                    "employer_category": firm.good_category
                }

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

            # Keep incumbents by default (unless they are in planned layoffs),
            # which matches the legacy behavior and avoids unnecessary churn.
            if household.is_employed and household_id not in planned_layoffs_set:
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
        for firm in self.firms:
            firm_id = firm.firm_id
            production_plan = firm_production_plans[firm_id]
            confirmed_layoffs = production_plan["planned_layoffs_ids"]
            vacancies = int(production_plan["planned_hires_count"])
            is_healthcare_firm = (firm.good_category or "").lower() == "healthcare"

            firm_labor_outcomes[firm_id] = {
                "hired_households_ids": [],
                "confirmed_layoffs_ids": confirmed_layoffs,
                "actual_wages": {}
            }

            if is_healthcare_firm or vacancies <= 0:
                continue
            active_hiring_firm_ids.append(firm_id)

        if not active_hiring_firm_ids:
            return firm_labor_outcomes, household_labor_outcomes

        # One-time active labor pool snapshot for this tick.
        # Only households relevant to non-healthcare market matching are included.
        candidate_mask = (~assigned) & searching & can_work & (~medical_only)
        candidate_indices = np.nonzero(candidate_mask)[0]
        if candidate_indices.size == 0:
            return firm_labor_outcomes, household_labor_outcomes

        candidate_reservations = reservation_wages[candidate_indices]
        # Distinct reservation levels become wage buckets.
        reservation_levels = np.unique(candidate_reservations)
        if reservation_levels.size == 0:
            return firm_labor_outcomes, household_labor_outcomes

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
                household_labor_outcomes[household_id] = {
                    "employer_id": firm_id,
                    "wage": actual_wage,
                    "employer_category": firm.good_category
                }
                assigned[candidate_idx] = True
                vacancies -= 1

        return firm_labor_outcomes, household_labor_outcomes

    def _update_continuing_employee_wages(self) -> None:
        """
        Update wages for continuing employees every 50 ticks.

        Applies a small 2-3% increase to existing employee wages to prevent
        massive wage increases within a single tick. Only updates employees
        who have been with the firm for at least 50 ticks.
        """

        for firm in self.firms:
            if not firm.employees:
                continue

            for employee_id in firm.employees:
                household = self.household_lookup.get(employee_id)
                if household is None:
                    continue

                # Only update if last wage update was at least 50 ticks ago
                if self.current_tick - household.last_wage_update_tick >= 50:
                    current_wage = firm.actual_wages.get(employee_id, firm.wage_offer)

                    # Apply 2-3% increase
                    increase_rate = random.uniform(0.02, 0.03)
                    new_wage = current_wage * (1.0 + increase_rate)

                    # Update the wage
                    firm.actual_wages[employee_id] = new_wage
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
        primary_healthcare_firm = healthcare_firms[0] if healthcare_firms else None
        primary_healthcare_firm_id = primary_healthcare_firm.firm_id if primary_healthcare_firm is not None else None

        for household in self.households:
            household_is_medical_only = household.medical_training_status in {"resident", "doctor"}

            # One-healthcare-firm model: all residents/doctors are attached there.
            if household_is_medical_only:
                if primary_healthcare_firm_id is None or primary_healthcare_firm is None:
                    household.employer_id = None
                    household.wage = 0.0
                    continue

                household.employer_id = primary_healthcare_firm_id
                assigned_wage = primary_healthcare_firm.actual_wages.get(
                    household.household_id,
                    max(primary_healthcare_firm.wage_offer, household.reservation_wage),
                )
                household.wage = max(assigned_wage, 1.0)
                primary_healthcare_firm.actual_wages[household.household_id] = household.wage
                employees_by_firm[primary_healthcare_firm_id].append(household.household_id)
                continue

            employer_id = household.employer_id
            if employer_id is None:
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
                    synced_wages[household_id] = firm.actual_wages.get(household_id, firm.wage_offer)
            firm.actual_wages = synced_wages

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
        """
        per_household_purchases: Dict[int, Dict[str, Tuple[float, float]]] = {}
        per_firm_sales: Dict[int, Dict[str, float]] = {}

        # Firm arrays for fast lookup
        firm_ids = [f.firm_id for f in firms]
        id_to_idx = {fid: idx for idx, fid in enumerate(firm_ids)}
        firm_prices = np.array([f.price for f in firms], dtype=np.float64)
        firm_goods = [f.good_name for f in firms]
        firm_remaining = np.array([f.inventory_units for f in firms], dtype=np.float64)

        for fid in firm_ids:
            per_firm_sales[fid] = {"units_sold": 0.0, "revenue": 0.0}

        # Group firm indices by good_name, sorted by price then id
        goods_to_indices: Dict[str, np.ndarray] = {}
        for idx, firm in enumerate(firms):
            goods_to_indices.setdefault(firm.good_name, []).append(idx)
        for good_name, idx_list in goods_to_indices.items():
            idx_list.sort(key=lambda i: (firm_prices[i], firm_ids[i]))
            goods_to_indices[good_name] = np.array(idx_list, dtype=np.int32)

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
                        continue
                    qty = min(desired_qty, available)
                    if qty <= 0:
                        continue
                    firm_remaining[idx] -= qty
                    fid = firm_ids[idx]
                    price = firm_prices[idx]
                    per_firm_sales[fid]["units_sold"] += qty
                    per_firm_sales[fid]["revenue"] += qty * price

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
                if not idx_list:
                    continue

                remaining = desired_qty
                total_bought = 0.0
                price_sum = 0.0

                for idx in idx_list:
                    if remaining <= 0:
                        break
                    available = firm_remaining[idx]
                    if available <= 0:
                        continue
                    qty = min(remaining, available)
                    firm_remaining[idx] -= qty
                    fid = firm_ids[idx]
                    price = firm_prices[idx]
                    per_firm_sales[fid]["units_sold"] += qty
                    per_firm_sales[fid]["revenue"] += qty * price
                    total_bought += qty
                    price_sum += qty * price
                    remaining -= qty

                if total_bought > 0:
                    per_household_purchases[household_id][good_name] = (
                        total_bought,
                        price_sum / total_bought
                    )

        return per_household_purchases, per_firm_sales

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
                "quality": firm.quality_level,
                "inventory": firm.inventory_units,
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
                "quality": firm.quality_level,
                "inventory": firm.inventory_units,
            })
        return snapshot

    def _build_good_category_lookup(self) -> Dict[str, str]:
        """Map each good_name to its category (lowercased) for quick lookups."""
        return {firm.good_name: firm.good_category.lower() for firm in self.firms}

    def _next_firm_id(self) -> int:
        """Generate a unique firm_id across active and queued firms."""
        existing_ids = set(self.firm_lookup.keys())
        existing_ids.update(f.firm_id for f in self.queued_firms)
        return max(existing_ids) + 1 if existing_ids else 1

    def _refresh_target_total_firms(self) -> None:
        """Recalculate desired firm counts based on current population and pipeline size."""
        households = max(1, len(self.households))
        per_thousand = CONFIG.firms.target_firms_per_1000_households
        dynamic_target = int(math.ceil((households / 1000.0) * per_thousand))
        baseline_count = sum(1 for f in self.firms if f.is_baseline)
        dynamic_target = max(dynamic_target, baseline_count)
        pipeline = len(self.firms) + len(self.queued_firms)
        self.target_total_firms = max(dynamic_target, pipeline, self.target_total_firms)

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

    def _batch_update_wellbeing(self, happiness_multiplier: float) -> None:
        """Vectorized wellbeing update matching per-agent update_wellbeing() logic."""
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
        housing_met = np.fromiter((h.met_housing_need for h in households), dtype=np.bool_, count=n)
        food_consumed = np.fromiter((h.food_consumed_this_tick for h in households), dtype=np.float64, count=n)

        # Per-agent morale parameters (randomized per household)
        morale_emp_boost = np.fromiter(
            (h.morale_employed_boost if h.morale_employed_boost is not None
             else sum(hc.morale_employed_boost_range) / 2.0
             for h in households),
            dtype=np.float64, count=n
        )
        morale_unemp_penalty = np.fromiter(
            (h.morale_unemployed_penalty if h.morale_unemployed_penalty is not None
             else sum(hc.morale_unemployed_penalty_range) / 2.0
             for h in households),
            dtype=np.float64, count=n
        )
        morale_unhoused_penalty = np.fromiter(
            (h.morale_unhoused_penalty if h.morale_unhoused_penalty is not None
             else sum(hc.morale_unhoused_penalty_range) / 2.0
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

        # Mercy floor: no natural decay below threshold
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
        health_positive = np.maximum(0.0, health_food_effect)
        health_negative = np.minimum(0.0, health_food_effect)

        if happiness_multiplier > 1.0:
            health_positive += (happiness_multiplier - 1.0) * hc.government_happiness_scaling

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
            else:
                # Unemployed: Initialize or decay reservation wage
                if household.unemployment_duration == 1:
                    # First tick unemployed: Start 20% above benefits
                    household.reservation_wage = benefit_net * 1.2
                elif household.unemployment_duration > 1:
                    # Decay reservation wage toward 5% above benefits
                    decay_speed = 0.01  # 1% per tick
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

    def _build_household_tax_snapshots(self) -> List[Dict[str, object]]:
        """
        Build snapshots for government tax planning (household part).

        Returns:
            List of dicts with household_id and wage_income
        """
        snapshots = []
        for household in self.households:
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
            units_sold = sales_data["units_sold"]

            # Calculate price ceiling tax
            # If price > $50, firm pays 25% tax on the revenue from those sales
            price_ceiling_tax = 0.0
            if firm.price > PRICE_CEILING and units_sold > 0:
                # Tax applies to revenue from sales above the ceiling
                price_ceiling_tax = revenue * PRICE_CEILING_TAX_RATE

            # Compute costs
            wage_bill = sum(firm.actual_wages.get(e_id, firm.wage_offer) for e_id in firm.employees)

            # Add CEO salary if firm has a CEO (3x median worker wage)
            ceo_salary = 0.0
            if firm.ceo_household_id is not None and firm.employees:
                median_worker_wage = np.median([firm.actual_wages.get(e_id, firm.wage_offer) for e_id in firm.employees])
                ceo_salary = median_worker_wage * 3.0  # CEO earns 3x median worker
                wage_bill += ceo_salary

            # Note: Other variable costs would be included here if tracked

            # Profit = revenue - wage_bill - price_ceiling_tax (simplified)
            profit_before_tax = revenue - wage_bill - price_ceiling_tax

            snapshots.append({
                "firm_id": firm.firm_id,
                "profit_before_tax": profit_before_tax,
                "price_ceiling_tax": price_ceiling_tax
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
        if len(firm.employees) == 0:
            return 0.0

        # Calculate average productivity multiplier for the workforce
        total_productivity_multiplier = 0.0
        for employee_id in firm.employees:
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
        avg_productivity_multiplier = total_productivity_multiplier / len(firm.employees)

        # Apply government infrastructure multiplier
        # Government infrastructure investment boosts all productivity economy-wide
        avg_productivity_multiplier *= self.government.infrastructure_productivity_multiplier

        # Apply to planned production
        # Cap at production capacity
        worker_capacity = firm._capacity_for_workers(len(firm.employees))
        actual_production = min(
            planned_production_units * avg_productivity_multiplier,
            firm.production_capacity_units,
            worker_capacity
        )

        return actual_production

    def _handle_firm_exits(self) -> None:
        """
        Remove bankrupt firms from the economy.

        Firms with negative cash below a threshold are removed.
        Their employees are laid off.

        Mutates state.
        """
        bankruptcy_threshold = CONFIG.market.bankruptcy_threshold
        zero_cash_max_streak = CONFIG.market.zero_cash_max_streak

        firms_to_remove = []
        for firm in self.firms:
            if firm.cash_balance < bankruptcy_threshold or firm.zero_cash_streak >= zero_cash_max_streak:
                # Protect government baseline firms at all times
                if self.government.is_baseline_firm(firm.firm_id):
                    continue

                # Firm is bankrupt - lay off all employees
                for employee_id in firm.employees:
                    # Find household and unemploy them (O(1) lookup via cache)
                    household = self.household_lookup.get(employee_id)
                    if household is not None:
                        household.employer_id = None
                        household.wage = 0.0

                firms_to_remove.append(firm)

        # Remove bankrupt firms
        for firm in firms_to_remove:
            self.firms.remove(firm)

            # Clean up tracking dictionaries
            if firm.firm_id in self.last_tick_sales_units:
                del self.last_tick_sales_units[firm.firm_id]
            if firm.firm_id in self.last_tick_revenue:
                del self.last_tick_revenue[firm.firm_id]
            if firm.firm_id in self.last_tick_sell_through_rate:
                del self.last_tick_sell_through_rate[firm.firm_id]

            # Clean up firm cache
            if firm.firm_id in self.firm_lookup:
                del self.firm_lookup[firm.firm_id]

    def _maybe_create_new_firms(self) -> None:
        """
        Potentially create new firms to replace bankrupt ones.

        New firms are created if:
        1. Total number of firms is below a minimum threshold
        2. There's demand in the economy (some households have cash)

        Mutates state.
        """
        from agents import FirmAgent

        # Warm-up period blocks private firm creation to avoid destabilizing start
        if self.in_warmup:
            return

        # Check if there's economic activity (households have cash)
        total_household_cash = sum(h.cash_balance for h in self.households)
        if total_household_cash < 1000.0:
            return  # Not enough demand to support new firms

        desired_pipeline = int(self.target_total_firms * 1.1) if self.target_total_firms else len(self.firms) + 1
        if len(self.firms) + len(self.queued_firms) >= max(desired_pipeline, self.target_total_firms):
            return

        # Create a new firm
        existing_ids = [f.firm_id for f in self.firms]
        existing_ids.extend(firm.firm_id for firm in self.queued_firms)
        new_firm_id = max(existing_ids, default=0) + 1

        categories = ["Food", "Housing", "Services"]
        total_units = sum(
            f.max_rental_units for f in self.firms
            if f.good_category == "Housing"
        )
        if total_units < len(self.households):
            chosen_category = "Housing"
        else:
            if self.firms:
                category_counts = {}
                for cat in categories:
                    category_counts[cat] = sum(1 for f in self.firms if f.good_category == cat)
                chosen_category = min(category_counts, key=category_counts.get)
            else:
                chosen_category = "Food"

        # Determine firm personality (deterministic based on firm_id)
        # Use modulo to cycle through personalities
        personality_index = new_firm_id % 3
        if personality_index == 0:
            personality = "aggressive"
        elif personality_index == 1:
            personality = "conservative"
        else:
            personality = "moderate"

        # Base quality level affected by government technology investment
        base_quality = 5.0 * self.government.technology_quality_multiplier

        # Determine median quality in category for seeding
        category_qualities = [f.quality_level for f in self.firms if f.good_category == chosen_category]
        median_quality = np.median(category_qualities) if category_qualities else 5.0

        # Government seed loan if available
        seed_cash = min(250000.0, max(50000.0, total_household_cash * 0.02))
        if self.government.cash_balance > seed_cash:
            self.government.cash_balance -= seed_cash
        else:
            seed_cash = 50000.0

        # Assign a random household as CEO owner (after warmup, tick > 52)
        ceo_id = None
        if self.current_tick > 52 and self.households:
            # Pick a random household to be the CEO
            ceo_id = np.random.choice([h.household_id for h in self.households])

        # Housing-specific initialization
        max_rental_units = 0
        property_tax_rate = 0.0
        if chosen_category == "Housing":
            max_rental_units = np.random.randint(0, 51)
            seed_cash = max(50000.0, max_rental_units * 10000.0)
            if self.government.cash_balance > seed_cash:
                self.government.cash_balance -= seed_cash
            else:
                seed_cash = 50000.0
            property_tax_rate = 0.005 * max_rental_units

        # Calculate loan repayment: 1% annual interest, 3-year payment plan
        # Interest rate: 1% per year = 1/52% per week
        # Total amount to repay: principal * (1 + 0.01 * 3) = principal * 1.03
        # Payment per tick: total / (52 weeks * 3 years) = total / 156
        total_repayment = seed_cash * 1.03
        weekly_payment = total_repayment / 156.0

        new_firm = FirmAgent(
            firm_id=new_firm_id,
            good_name=f"{chosen_category}Product{new_firm_id}",
            cash_balance=seed_cash,
            inventory_units=100.0 if chosen_category != "Housing" else 0.0,  # Housing has no inventory
            good_category=chosen_category,
            quality_level=min(10.0, max(1.0, median_quality + np.random.uniform(-1.0, 1.0))),
            wage_offer=35.0,
            price=150.0 if chosen_category == "Housing" else 8.0,  # Rent starts at $150/week
            expected_sales_units=50.0 if chosen_category != "Housing" else float(max_rental_units),
            production_capacity_units=500.0 if chosen_category != "Housing" else float(max_rental_units),
            productivity_per_worker=10.0,
            units_per_worker=18.0,
            personality=personality,
            government_loan_principal=seed_cash,
            government_loan_remaining=total_repayment,
            loan_payment_per_tick=weekly_payment,
            ceo_household_id=ceo_id,
            max_rental_units=max_rental_units,
            property_tax_rate=property_tax_rate
        )

        # Set personality-based behavior parameters
        new_firm.set_personality(personality)

        self.firms.append(new_firm)

        # Initialize tracking for new firm
        self.last_tick_sales_units[new_firm_id] = 0.0
        self.last_tick_revenue[new_firm_id] = 0.0
        self.last_tick_sell_through_rate[new_firm_id] = 0.5
        self.last_tick_prices[new_firm.good_name] = new_firm.price

        # Add to firm cache
        self.firm_lookup[new_firm_id] = new_firm

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

    def _offer_emergency_loans(self, unemployment_rate: float) -> None:
        """
        Provide temporary low-interest loans to cash-strapped firms
        whenever unemployment breaches the configured trigger.
        """
        config = CONFIG.government
        if unemployment_rate < config.emergency_loan_trigger:
            return

        reserve_floor = config.investment_reserve_threshold
        available_cash = self.government.cash_balance - reserve_floor
        if available_cash <= 0:
            return

        per_tick_budget = max(
            config.emergency_loan_amount,
            available_cash * config.emergency_loan_fraction_of_cash
        )
        per_tick_budget = min(per_tick_budget, available_cash)

        candidate_firms = [
            f for f in self.firms
            if (not f.is_baseline) and (
                f.cash_balance < config.emergency_loan_cash_threshold
                or len(f.employees) < config.emergency_loan_min_headcount
            )
        ]
        if not candidate_firms or per_tick_budget <= 0:
            return

        candidate_firms.sort(key=lambda firm: firm.cash_balance)
        term_ticks = max(
            1,
            int(CONFIG.time.ticks_per_year * config.emergency_loan_term_years)
        )
        interest_multiplier = 1.0 + config.emergency_loan_interest

        for firm in candidate_firms:
            if per_tick_budget <= 0 or self.government.cash_balance <= reserve_floor:
                break

            desired = max(
                config.emergency_loan_amount,
                config.emergency_loan_cash_threshold - firm.cash_balance
            )
            capacity = self.government.cash_balance - reserve_floor
            loan_amount = min(desired, per_tick_budget, capacity)
            if loan_amount <= 0:
                continue

            firm.cash_balance += loan_amount
            total_repayment = loan_amount * interest_multiplier
            firm.government_loan_principal += loan_amount
            firm.government_loan_remaining += total_repayment
            firm.loan_payment_per_tick += total_repayment / term_ticks
            enforcement_ticks = max(1, config.emergency_loan_enforcement_ticks)
            required_headcount = max(
                config.emergency_loan_min_headcount,
                int(
                    math.ceil(
                        max(1, len(firm.employees)) *
                        config.emergency_loan_required_headcount_multiplier
                    )
                )
            )
            firm.loan_required_headcount = max(firm.loan_required_headcount, required_headcount)
            firm.loan_support_ticks = max(firm.loan_support_ticks, enforcement_ticks)
            self.government.cash_balance -= loan_amount
            per_tick_budget -= loan_amount

    def _offer_inventory_liquidation_loans(self) -> None:
        """
        Provide loans to firms with poor sales to help with R&D and inventory liquidation.

        Loans are offered to firms where:
        - Items sold < items produced (underselling)
        - Inventory > 2× production rate (inventory buildup)

        Loan amount: 10% of firm's current cash balance (scaled, not fixed)
        Interest rate: 2% annual (2/52 = 0.0385% per tick)
        Term: 3 years (156 ticks)
        """
        # Check government has funds available (minimum 1% reserve)
        min_reserve = self.government.cash_balance * 0.01
        if self.government.cash_balance < min_reserve:
            return

        # Calculate per-tick budget (20% of available cash above reserve)
        available_cash = max(0.0, self.government.cash_balance - min_reserve)
        per_tick_budget = available_cash * 0.2

        # Find candidate firms (poor sales performance)
        candidate_firms = [
            f for f in self.firms
            if (not f.is_baseline) and (
                (f.last_units_produced > 0 and f.last_units_sold < f.last_units_produced)
                or (f.last_units_produced > 0 and f.inventory_units > 2.0 * f.last_units_produced)
            ) and f.cash_balance > 0
        ]

        if not candidate_firms or per_tick_budget <= 0:
            return

        # Prioritize firms with worst sales performance
        candidate_firms.sort(key=lambda f: f.last_units_sold / max(f.last_units_produced, 1.0))

        # Loan parameters
        term_ticks = 156  # 3 years (52 ticks/year × 3)
        annual_interest_rate = 0.02  # 2% annual
        interest_multiplier = 1.0 + annual_interest_rate

        for firm in candidate_firms:
            if per_tick_budget <= 0 or self.government.cash_balance <= min_reserve:
                break

            # Loan amount: 10% of firm's current cash balance (scaled)
            loan_amount = firm.cash_balance * 0.10

            # Don't give loans if firm already has outstanding balance > 50% of cash
            if firm.government_loan_remaining > firm.cash_balance * 0.5:
                continue

            # Cap loan at available budget and government reserves
            actual_loan = min(loan_amount, per_tick_budget, self.government.cash_balance - min_reserve)
            if actual_loan <= 100:  # Minimum viable loan
                continue

            # Grant loan
            firm.cash_balance += actual_loan
            total_repayment = actual_loan * interest_multiplier
            firm.government_loan_principal += actual_loan
            firm.government_loan_remaining += total_repayment
            firm.loan_payment_per_tick += total_repayment / term_ticks

            self.government.cash_balance -= actual_loan
            per_tick_budget -= actual_loan

    def _ensure_public_works_capacity(self, unemployment_rate: float) -> None:
        """Stand up or scale public works firms to absorb excess labor."""
        config = CONFIG.government
        if unemployment_rate < config.public_works_unemployment_threshold:
            return

        target_jobs = max(1, int(len(self.households) * config.public_works_job_fraction))
        public_firms = [f for f in self.firms if f.good_category == "PublicWorks"]

        if not public_firms:
            new_firm_id = self._next_firm_id()
            capacity = float(target_jobs * 2)
            public_firm = FirmAgent(
                firm_id=new_firm_id,
                good_name=f"PublicWorks{new_firm_id}",
                cash_balance=CONFIG.government.public_works_job_fraction * 1_000_000.0,
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
            self.firms.append(public_firm)
            self.firm_lookup[new_firm_id] = public_firm
            self.last_tick_sales_units[new_firm_id] = 0.0
            self.last_tick_revenue[new_firm_id] = 0.0
            self.last_tick_sell_through_rate[new_firm_id] = 0.5
            self.last_tick_prices[public_firm.good_name] = public_firm.price
            public_firms = [public_firm]

        per_firm_quota = max(
            config.emergency_loan_min_headcount,
            int(math.ceil(target_jobs / len(public_firms)))
        )
        for firm in public_firms:
            firm.baseline_production_quota = max(float(per_firm_quota), firm.baseline_production_quota)
            firm.expected_sales_units = max(float(per_firm_quota), firm.expected_sales_units)
            firm.production_capacity_units = max(float(per_firm_quota * 2), firm.production_capacity_units)
            firm.price = config.public_works_price
            firm.wage_offer = config.public_works_wage

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

        # Governments can run deficits; deduct directly from cash balance
        self.government.cash_balance -= total_transfer
        for household in self.households:
            household.cash_balance += per_household_transfer

        self.post_warmup_stimulus_ticks -= 1

    def _apply_random_shocks(self) -> None:
        """
        Apply random economic shocks each tick to introduce stochasticity.

        Shocks include:
        - Demand shocks (random cash injections/withdrawals to households)
        - Supply shocks (temporary productivity changes to random firms)
        - Price shocks (random price pressures on specific goods)

        These shocks ensure that identical policy configurations produce
        different outcomes across runs, enabling statistical analysis.
        """

        # Skip shocks during warm-up period to allow stable initialization
        if self.in_warmup:
            return

        # 1. DEMAND SHOCK (5% chance per tick)
        # Random cash injection or withdrawal affecting 5-15% of households
        if random.random() < 0.05:
            shock_magnitude = random.uniform(-50, 100)  # Asymmetric: more likely positive
            affected_households = random.sample(
                self.households,
                k=min(len(self.households), max(1, int(len(self.households) * random.uniform(0.05, 0.15))))
            )
            for h in affected_households:
                h.cash_balance = max(0, h.cash_balance + shock_magnitude)

        # 2. SUPPLY SHOCK (3% chance per tick)
        # Random productivity change affecting 1-3 firms
        if random.random() < 0.03 and self.firms:
            num_affected = min(len(self.firms), random.randint(1, 3))
            affected_firms = random.sample(self.firms, k=num_affected)
            productivity_change = random.uniform(0.85, 1.15)  # ±15% productivity
            for firm in affected_firms:
                # Temporarily adjust production capacity
                if hasattr(firm, 'last_units_produced') and firm.last_units_produced > 0:
                    firm.last_units_produced = int(firm.last_units_produced * productivity_change)

        # 3. HEALTH SHOCK (2% chance per tick)
        # Random health crisis affecting 1-5% of population
        if random.random() < 0.02:
            health_shock = random.uniform(-0.05, -0.20)  # Health loss
            affected_households = random.sample(
                self.households,
                k=min(len(self.households), max(1, int(len(self.households) * random.uniform(0.01, 0.05))))
            )
            for h in affected_households:
                h.health = max(0.0, min(1.0, h.health + health_shock))

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
        """
        # Get all housing firms
        housing_firms = [f for f in self.firms if f.good_category == "Housing"]

        if not housing_firms:
            return  # No housing available

        rent_share = CONFIG.labor_market.rent_affordability_share

        # Phase 1: Check affordability and evict households who can't pay
        for household in self.households:
            if household.renting_from_firm_id is not None:
                # Find the housing firm
                housing_firm = next((f for f in housing_firms if f.firm_id == household.renting_from_firm_id), None)

                if housing_firm is None:
                    # Firm no longer exists, evict household
                    household.renting_from_firm_id = None
                    household.monthly_rent = 0.0
                    household.owns_housing = False
                    continue

                # Check if household can afford rent (rent <= configured share of earned wage only).
                income = household.wage if household.employer_id is not None else 0.0
                max_affordable_rent = income * rent_share

                if household.monthly_rent > max_affordable_rent or household.cash_balance < household.monthly_rent:
                    # EVICTION: Can't afford rent
                    housing_firm.current_tenants.remove(household.household_id)
                    household.renting_from_firm_id = None
                    household.monthly_rent = 0.0
                    household.owns_housing = False
                    household.happiness = max(0.0, household.happiness - 0.3)  # Happiness penalty for eviction
                else:
                    # Pay rent
                    household.cash_balance -= household.monthly_rent
                    housing_firm.cash_balance += household.monthly_rent
                    household.owns_housing = True

        # Phase 2: Match homeless households with available units
        homeless_households = [h for h in self.households if h.renting_from_firm_id is None]

        # Sort homeless by income (higher income gets priority)
        homeless_households.sort(key=lambda h: h.wage if h.is_employed else 0.0, reverse=True)

        for household in homeless_households:
            income = household.wage if household.employer_id is not None else 0.0
            max_affordable_rent = income * rent_share

            # Find cheapest housing firm with available units that household can afford
            affordable_housing = [
                (f, f.price) for f in housing_firms
                if len(f.current_tenants) < f.max_rental_units and f.price <= max_affordable_rent
            ]

            if affordable_housing:
                # Sort by price (cheapest first)
                affordable_housing.sort(key=lambda x: x[1])
                chosen_firm, rent = affordable_housing[0]

                # Sign rental agreement
                household.renting_from_firm_id = chosen_firm.firm_id
                household.monthly_rent = rent
                household.owns_housing = True
                chosen_firm.current_tenants.append(household.household_id)

                # Pay first month's rent
                household.cash_balance -= rent
                chosen_firm.cash_balance += rent

        total_units = sum(f.max_rental_units for f in housing_firms)
        shortage = total_units < len(self.households)

        # Phase 3: Housing firms adjust rent based on occupancy
        lm = CONFIG.labor_market
        for firm in housing_firms:
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

            firm.price = max(lm.rent_floor, firm.price)

            if shortage and occupancy_rate >= lm.occupancy_high_threshold and self.current_tick % lm.rent_shortage_interval_ticks == 0:
                firm.price *= lm.rent_shortage_multiplier

    def _apply_housing_repairs(self) -> None:
        """Apply random weekly repair costs to housing firms."""
        for firm in self.firms:
            if firm.good_category.lower() != "housing":
                continue
            if firm.max_rental_units <= 0 or firm.price <= 0:
                continue
            repair_rate = np.random.uniform(0.01, 0.05)
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
            num_beneficiaries = np.random.randint(10, 21)
            num_beneficiaries = min(num_beneficiaries, len(self.households))
            self.misc_firm_beneficiaries = np.random.choice(
                [h.household_id for h in self.households],
                size=num_beneficiaries,
                replace=False
            ).tolist()

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
            new_beneficiary = np.random.choice(non_beneficiaries)
            self.misc_firm_beneficiaries.append(new_beneficiary)

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
        tax_rate = random.uniform(0.0, 0.20)
        tax = amount * tax_rate
        net = amount - tax
        if tax > 0:
            self.government.cash_balance += tax
        if net > 0:
            self.misc_firm_revenue += net

    def _reset_healthcare_tick_state(self) -> None:
        """Reset per-tick healthcare counters and clear legacy medical inventory remnants."""
        self.healthcare_requests_this_tick = 0.0
        self.healthcare_attempted_slots_this_tick = 0.0
        self.healthcare_completed_visits_this_tick = 0.0
        self.healthcare_affordability_rejects_this_tick = 0.0

        for household in self.households:
            household.healthcare_consumed_this_tick = 0.0
            for good in list(household.goods_inventory.keys()):
                if _get_good_category(good).lower() == "healthcare":
                    del household.goods_inventory[good]

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
        """
        healthcare_firms = self._healthcare_firms()
        if not healthcare_firms:
            return

        social_scale = 1.0 + (
            max(0.0, self.government.social_happiness_multiplier - 1.0)
            * CONFIG.government.social_program_health_scaling
        )
        subsidy_share = max(0.0, min(1.0, CONFIG.government.healthcare_visit_subsidy_share))

        for firm in healthcare_firms:
            firm.inventory_units = 0.0
            self._prioritize_healthcare_queue(firm)

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

                visit_price = max(0.0, firm.price)
                household_cost = visit_price * (1.0 - subsidy_share)
                government_cost = visit_price - household_cost

                if household.cash_balance + 1e-9 < household_cost:
                    # Cannot afford this tick; keep queued.
                    next_queue.append(household_id)
                    household.queued_healthcare_firm_id = firm.firm_id
                    self.healthcare_affordability_rejects_this_tick += 1.0
                    continue

                if household_cost > 0.0:
                    household.cash_balance -= household_cost
                if government_cost > 0.0:
                    self.government.cash_balance -= government_cost

                per_firm_sales[firm.firm_id]["units_sold"] += 1.0
                per_firm_sales[firm.firm_id]["revenue"] += visit_price
                firm.healthcare_completed_visits_last_tick += 1.0
                self.healthcare_completed_visits_this_tick += 1.0

                heal_delta = household.pending_visit_heal_delta
                if heal_delta <= 0.0:
                    heal_delta = CONFIG.households.healthcare_visit_base_heal * (1.0 - household.health)
                household.pending_visit_heal_delta = 0.0
                household.health = min(1.0, household.health + max(0.0, heal_delta) * social_scale)
                household.healthcare_consumed_this_tick += 1.0
                household.last_checkup_tick = self.current_tick
                household.queued_healthcare_firm_id = None

                completed += 1

            firm.healthcare_queue = next_queue

            if completed > 0:
                firm.healthcare_idle_streak = 0

    def _process_healthcare_and_loans(self) -> None:
        """
        Legacy compatibility shim.

        Healthcare now routes through queue-based services in:
        - _enqueue_healthcare_requests
        - _process_healthcare_services
        """
        return

    def _adjust_government_policy(self) -> None:
        """
        Calculate economic indicators and adjust government policy.

        Mutates state.
        """
        # Calculate unemployment rate
        total_households = len(self.households)
        if total_households == 0:
            return

        unemployed = sum(1 for h in self.households if not h.is_employed)
        unemployment_rate = unemployed / total_households

        inflation_rate = 0.0

        # Calculate deficit ratio
        total_gdp = sum(self.last_tick_revenue.values()) if self.last_tick_revenue else 1.0
        deficit_ratio = abs(self.government.cash_balance) / max(total_gdp, 1.0)

        bankruptcies = sum(1 for f in self.firms if f.cash_balance < 0.0)
        total_tax_revenue = total_gdp * self.government.profit_tax_rate

        self.government.adjust_policies(
            unemployment_rate,
            inflation_rate,
            deficit_ratio,
            num_unemployed=unemployed,
            gdp=total_gdp,
            total_tax_revenue=total_tax_revenue,
            num_bankrupt_firms=bankruptcies
        )

    def _update_statistics(self, per_firm_sales: Dict[int, Dict[str, float]]) -> None:
        """
        Update world-level statistics for next tick.

        Args:
            per_firm_sales: Sales data from this tick
        """
        # Update firm-level stats
        for firm in self.firms:
            sales_data = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})

            self.last_tick_sales_units[firm.firm_id] = sales_data["units_sold"]
            self.last_tick_revenue[firm.firm_id] = sales_data["revenue"]

            # Compute sell-through rate
            units_sold = sales_data["units_sold"]
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
        if not values or len(values) == 0:
            return 0.0

        # Sort values in ascending order
        sorted_values = sorted(values)
        n = len(sorted_values)

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
        """
        metrics = {}

        # Household metrics
        if self.households:
            employed_households = [h for h in self.households if h.is_employed]
            unemployed_households = [h for h in self.households if not h.is_employed]

            metrics["total_households"] = len(self.households)
            metrics["employed_count"] = len(employed_households)
            metrics["unemployed_count"] = len(unemployed_households)
            metrics["unemployment_rate"] = len(unemployed_households) / len(self.households)

            # Wage statistics
            if employed_households:
                wages = [h.wage for h in employed_households]
                metrics["mean_wage"] = sum(wages) / len(wages)
                metrics["median_wage"] = sorted(wages)[len(wages) // 2]
                metrics["min_wage"] = min(wages)
                metrics["max_wage"] = max(wages)
            else:
                metrics["mean_wage"] = 0.0
                metrics["median_wage"] = 0.0
                metrics["min_wage"] = 0.0
                metrics["max_wage"] = 0.0

            # Household cash/wealth
            household_cash = [h.cash_balance for h in self.households]
            metrics["total_household_cash"] = sum(household_cash)
            metrics["mean_household_cash"] = sum(household_cash) / len(household_cash)
            metrics["median_household_cash"] = sorted(household_cash)[len(household_cash) // 2]

            # Wealth inequality - Gini coefficient
            metrics["gini_coefficient"] = self._calculate_gini_coefficient(household_cash)

            # Wealth distribution percentiles
            sorted_cash = sorted(household_cash)
            n = len(sorted_cash)
            metrics["wealth_p10"] = sorted_cash[int(n * 0.1)]  # 10th percentile
            metrics["wealth_p25"] = sorted_cash[int(n * 0.25)]  # 25th percentile
            metrics["wealth_p50"] = sorted_cash[int(n * 0.50)]  # 50th percentile (median)
            metrics["wealth_p75"] = sorted_cash[int(n * 0.75)]  # 75th percentile
            metrics["wealth_p90"] = sorted_cash[int(n * 0.90)]  # 90th percentile
            metrics["wealth_p99"] = sorted_cash[int(n * 0.99)]  # 99th percentile

            # Top vs bottom wealth shares
            total_wealth = sum(household_cash)
            if total_wealth > 0:
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
                "mean_skills": 0.0
            })

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

        # Firm metrics
        if self.firms:
            firm_cash = [f.cash_balance for f in self.firms]
            metrics["total_firms"] = len(self.firms)
            metrics["total_firm_cash"] = sum(firm_cash)
            metrics["mean_firm_cash"] = sum(firm_cash) / len(firm_cash)
            metrics["median_firm_cash"] = sorted(firm_cash)[len(firm_cash) // 2]

            # Inventory
            total_inventory = sum(f.inventory_units for f in self.firms)
            metrics["total_firm_inventory"] = total_inventory

            # Employees
            total_employees = sum(len(f.employees) for f in self.firms)
            metrics["total_employees"] = total_employees

            # Prices
            prices = [f.price for f in self.firms]
            metrics["mean_price"] = sum(prices) / len(prices)
            metrics["median_price"] = sorted(prices)[len(prices) // 2]

            # Quality
            qualities = [f.quality_level for f in self.firms]
            metrics["mean_quality"] = sum(qualities) / len(qualities)
        else:
            metrics.update({
                "total_firms": 0, "total_firm_cash": 0.0, "mean_firm_cash": 0.0,
                "median_firm_cash": 0.0, "total_firm_inventory": 0.0,
                "total_employees": 0, "mean_price": 0.0, "median_price": 0.0,
                "mean_quality": 0.0
            })

        # GDP calculation (sum of all firm revenues this tick)
        metrics["gdp_this_tick"] = sum(self.last_tick_revenue.values())

        # Government metrics
        metrics["government_cash"] = self.government.cash_balance
        metrics["wage_tax_rate"] = self.government.wage_tax_rate
        metrics["profit_tax_rate"] = self.government.profit_tax_rate
        metrics["unemployment_benefit"] = self.government.unemployment_benefit_level
        metrics["transfer_budget"] = self.government.transfer_budget

        # Infrastructure multipliers
        metrics["infrastructure_productivity"] = self.government.infrastructure_productivity_multiplier
        metrics["technology_quality"] = self.government.technology_quality_multiplier
        metrics["social_happiness"] = self.government.social_happiness_multiplier

        # Total wealth in economy
        metrics["total_economy_cash"] = (
            metrics["total_household_cash"] +
            metrics["total_firm_cash"] +
            metrics["government_cash"]
        )

        # Current tick
        metrics["current_tick"] = self.current_tick

        return metrics
