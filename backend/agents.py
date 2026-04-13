"""
EcoSim Agent System

Defines the four core agent types for the economic simulation:
HouseholdAgent, FirmAgent, BankAgent, and GovernmentAgent. Each agent
encapsulates its own decision-making logic for labor, consumption,
production, pricing, credit, and fiscal policy.
"""

import math
import random
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from config import CONFIG


def _get_good_category(good_name: str, good_categories: Optional[Dict[str, str]] = None) -> str:
    """Best-effort inference of a good's category (defaults to lowercased name).

    When *good_categories* is provided (the pre-built lookup from
    ``Economy._build_good_category_lookup``), values are already lowercased so
    we can return directly without extra work.
    """
    if good_categories:
        cat = good_categories.get(good_name)
        if cat:
            return cat  # already lowercased by _build_good_category_lookup

    # Fallback for callers without a lookup (e.g. __post_init__).
    lowered = good_name.lower()
    if "housing" in lowered:
        return "housing"
    return lowered


class AgentMixin:
    """Shared behaviour for all agent types."""

    def apply_overrides(self, overrides: Dict[str, object]) -> None:
        """Apply external overrides to agent state.

        Useful for UI or script-driven state modifications.

        Args:
            overrides: Dictionary of attribute names to new values
        """
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass(slots=True)
class HouseholdAgent(AgentMixin):
    """
    Represents a household in the economic simulation.

    Households work for firms, consume goods, and form expectations
    about prices and wages. Behavior is deterministic when seeded.
    """

    # Identification and traits
    household_id: int
    skills_level: float  # 0.0 to 1.0, used in hiring
    age: int

    # Economic state
    cash_balance: float
    goods_inventory: Dict[str, float] = field(default_factory=dict)
    employer_id: Optional[int] = None
    wage: float = 0.0
    owns_housing: bool = False  # Track if household already owns housing
    renting_from_firm_id: Optional[int] = None  # Firm ID of housing provider (rental)
    monthly_rent: float = 0.0  # Current rent amount paid per tick
    stabilization_disabled: bool = False  # Experiment flag

    # H4: Income breakdown tracking (for debugging and anomaly detection)
    last_wage_income: float = 0.0
    last_transfer_income: float = 0.0
    last_dividend_income: float = 0.0
    last_other_income: float = 0.0
    last_consumption_spending: float = 0.0
    last_tick_cash_start: float = 0.0  # Cash at start of tick for change calculation
    last_tick_ledger: Dict[str, float] = field(default_factory=dict)
    ledger_cash_start: float = 0.0
    last_dividend_firm_ids: List[int] = field(default_factory=list)
    owned_firm_ids: List[int] = field(default_factory=list)
    is_misc_beneficiary: bool = False
    education_active_this_tick: bool = False

    # Per-category purchase receipt — populated by economy after goods market clearing
    last_food_units: float = 0.0        # Units of food purchased this tick
    last_food_spend: float = 0.0        # $ spent on food this tick
    last_housing_units: float = 0.0     # Units of housing purchased this tick
    last_housing_spend: float = 0.0     # $ spent on housing this tick
    last_services_units: float = 0.0    # Units of services purchased this tick
    last_services_spend: float = 0.0    # $ spent on services this tick
    last_healthcare_units: float = 0.0  # Visits completed this tick
    last_healthcare_spend: float = 0.0  # $ paid out of pocket for healthcare this tick
    last_healthcare_provider_id: Optional[int] = None
    last_purchase_breakdown: Dict[str, Any] = field(default_factory=dict)  # good_name -> {units, spend}
    # Preferences and heuristics
    consumption_budget_share: float = 0.7  # Legacy field (overridden by savings_rate_target if set)
    good_weights: Dict[str, float] = field(default_factory=dict)  # DEPRECATED: use category_weights
    category_weights: Dict[str, float] = field(default_factory=dict)  # category -> share of budget
    savings_rate_target: Optional[float] = None  # long-run desired savings share [0,1]
    default_purchase_style: str = "value"
    purchase_styles: Dict[str, str] = field(default_factory=dict)  # category -> cheap/value/quality

    # Quality/price preferences
    quality_preference_weight: float = 1.0  # elasticity for quality in purchase decisions
    price_sensitivity: float = 1.0  # elasticity for price in purchase decisions

    # Experience tracking
    category_experience: Dict[str, int] = field(default_factory=dict)  # category -> ticks worked

    # Expectations and beliefs
    price_beliefs: Dict[str, float] = field(default_factory=dict)
    expected_wage: float = 10.0  # initial default wage expectation
    reservation_wage: float = 8.0  # minimum acceptable wage

    # Config / tuning parameters
    price_expectation_alpha: float = 0.3  # [0,1] for price smoothing
    wage_expectation_alpha: float = 0.2  # [0,1] for wage smoothing
    reservation_markup_over_benefit: float = 1.1  # reservation = benefit * markup
    default_price_level: float = 10.0  # fallback when no price history
    min_cash_for_aggressive_job_search: float = 100.0  # threshold for wage flexibility

    # Skill development
    skill_growth_rate: float = 0.001  # base skill improvement per tick when employed
    education_cost_per_skill_point: float = 1000.0  # cost to improve skill by 0.1
    last_skill_update_tick: int = 0  # Tick when skills were last increased (for rate limiting)
    last_wage_update_tick: int = 0  # Tick when wage premiums were last increased (for rate limiting)

    # Wellbeing and performance factors
    happiness: float = 0.7  # 0-1 scale, affects productivity and consumption
    morale: float = 0.7  # 0-1 scale, affects work performance
    health: float = 1.0  # 0-1 scale, affects productivity and skill development
    unemployment_duration: int = 0  # consecutive ticks without employment

    # Wellbeing dynamics
    happiness_decay_rate: float = 0.002  # Matches config default; was 0.01 (bug)
    morale_decay_rate: float = 0.02  # Morale decays faster than happiness
    health_decay_rate: float = 0.0  # Dynamic per-tick health decay (set in __post_init__)
    health_decay_per_year: float = 0.0  # Annual health decay characteristic (set in __post_init__)

    # Medical loan tracking
    medical_loan_principal: float = 0.0  # Original medical loan amount
    medical_loan_remaining: float = 0.0  # Remaining balance with interest
    medical_loan_payment_per_tick: float = 0.0  # Payment per tick (10% of wage)

    # Bank deposit account (optional — 0.0 when no bank exists)
    bank_deposit: float = 0.0
    deposit_buffer_weeks: float = 6.0   # Weeks of expenses to keep liquid before depositing
    deposit_fraction: float = 0.20      # Fraction of excess cash deposited per tick
    savings_drawdown_rate: float = 0.02  # Fraction of cash savings spent per tick (personality-derived)

    # Fix 25: Consumption credit (small loans to bridge income shocks)
    needs_consumption_loan: bool = False
    consumption_loan_amount: float = 0.0
    consumption_loan_remaining: float = 0.0   # Tracks outstanding consumption debt
    consumption_loan_payment_per_tick: float = 0.0
    subsistence_min_cash: float = 50.0        # Minimum cash needed for subsistence

    # Medical workforce pipeline
    medical_training_status: str = "none"  # one of: none, student, resident, doctor
    medical_training_start_tick: int = -1
    medical_school_debt_principal: float = 0.0
    medical_school_debt_remaining: float = 0.0
    medical_school_annual_interest_rate: float = 0.0
    medical_school_weekly_interest_rate: float = 0.0
    medical_school_payment_per_tick: float = 0.0
    medical_doctor_capacity_cap: float = 2.0
    medical_doctor_expected_wage_anchor: float = 80.0
    medical_doctor_reservation_wage_anchor: float = 55.0

    # On-the-job search ("newspaper" mechanic)
    # Counts down each tick; when 0 an employed worker samples the market.
    # Initialized randomly in __post_init__ so workers are staggered.
    job_search_cooldown: int = 0
    job_switch_threshold: float = 0.15  # switch if new offer > current wage * (1 + threshold)

    # Minimum consumption requirements per tick
    min_food_per_tick: float = 2.0  # Minimum food units needed per tick
    min_services_per_tick: float = 1.0  # Minimum services units needed per tick
    met_housing_need: bool = False  # Track if housing service was consumed this tick
    spending_tendency: float = 1.0  # Multiplier for overall spend appetite
    food_preference: float = 1.0
    services_preference: float = 1.0
    housing_preference: float = 1.0
    quality_lavishness: float = 1.0
    frugality: float = 1.0  # Higher = saves more
    saving_tendency: float = 0.5  # Innate thriftiness [0.0, 1.0], initialized randomly in __post_init__
    household_service_happiness_base_boost: Optional[float] = None
    healthcare_preference: Optional[float] = None
    healthcare_request_base_chance_pct: float = 0.0
    healthcare_urgency_threshold: Optional[float] = None
    healthcare_critical_threshold: Optional[float] = None
    morale_employed_boost: Optional[float] = None
    morale_unemployed_penalty: Optional[float] = None
    morale_unhoused_penalty: Optional[float] = None
    food_consumed_last_tick: float = 0.0
    food_consumed_this_tick: float = 0.0
    services_consumed_last_tick: float = 0.0
    services_consumed_this_tick: float = 0.0
    healthcare_consumed_this_tick: float = 0.0  # Service visits completed this tick
    care_plan_due_ticks: List[int] = field(default_factory=list)
    care_plan_heal_deltas: List[float] = field(default_factory=list)
    care_plan_anchor_tick: int = -1
    pending_visit_heal_delta: float = 0.0
    pending_healthcare_visits: int = 0
    next_healthcare_request_tick: int = 0
    last_checkup_tick: int = -52
    queued_healthcare_firm_id: Optional[int] = None
    healthcare_queue_enter_tick: int = -1

    # Feature 3: Bounded Rationality - Awareness Pool
    awareness_pool: Dict[str, List[int]] = field(default_factory=dict)  # category -> list of firm_ids
    current_primary_firm: Dict[str, Optional[int]] = field(default_factory=dict)  # category -> firm_id
    last_pool_refresh_tick: int = 0  # Last tick when awareness pool was refreshed

    def __post_init__(self):
        """Validate invariants after initialization."""
        if not (0.0 <= self.consumption_budget_share <= 1.0):
            raise ValueError(
                f"consumption_budget_share must be in [0,1], got {self.consumption_budget_share}"
            )
        self._initialize_personality_preferences()
        self.reset_tick_ledger()

        if not (0.0 <= self.savings_rate_target <= 1.0):
            raise ValueError(
                f"savings_rate_target must be in [0,1], got {self.savings_rate_target}"
            )
        if not (0.0 <= self.price_expectation_alpha <= 1.0):
            raise ValueError(
                f"price_expectation_alpha must be in [0,1], got {self.price_expectation_alpha}"
            )
        if not (0.0 <= self.wage_expectation_alpha <= 1.0):
            raise ValueError(
                f"wage_expectation_alpha must be in [0,1], got {self.wage_expectation_alpha}"
            )
        if not (0.0 <= self.skills_level <= 1.0):
            raise ValueError(f"skills_level must be in [0,1], got {self.skills_level}")
        if self.age < 0:
            raise ValueError(f"age cannot be negative, got {self.age}")
        for good, quantity in self.goods_inventory.items():
            if quantity > 0 and _get_good_category(good) == "housing":
                self.owns_housing = True
                break

    def reset_tick_ledger(self) -> None:
        """Reset per-tick cash-flow visibility fields without changing core behavior."""
        self.ledger_cash_start = self.cash_balance
        self.last_tick_ledger = {
            "wage": 0.0,
            "transfers": 0.0,
            "stimulus": 0.0,
            "redistribution": 0.0,
            "dividends": 0.0,
            "goods": 0.0,
            "rent": 0.0,
            "healthcare": 0.0,
            "education": 0.0,
            "taxes": 0.0,
            "bank": 0.0,
            "other": 0.0,
            "net": 0.0,
        }
        self.last_wage_income = 0.0
        self.last_transfer_income = 0.0
        self.last_dividend_income = 0.0
        self.last_other_income = 0.0
        self.last_dividend_firm_ids = []
        self.education_active_this_tick = False

    def add_ledger_flow(self, key: str, amount: float) -> None:
        """Accumulate a signed cash flow into the current tick ledger."""
        if abs(amount) <= 1e-12:
            return
        self.last_tick_ledger[key] = self.last_tick_ledger.get(key, 0.0) + float(amount)

    def finalize_tick_ledger(self) -> None:
        """Finalize the net cash delta for the current tick."""
        self.last_tick_ledger["net"] = float(self.cash_balance - self.ledger_cash_start)

    def _initialize_personality_preferences(self) -> None:
        """Deterministically assign savings, weights, and purchase styles."""
        config = CONFIG.households
        jitter = 1e-6

        def sample_range(value_range: tuple[float, float], clip_min: float = 0.0, clip_max: float = 1.0e9) -> float:
            low, high = value_range
            if high < low:
                low, high = high, low
            sampled = rng.uniform(low, high) + rng.uniform(-jitter, jitter)
            return max(clip_min, min(clip_max, sampled))

        rng = random.Random(CONFIG.random_seed + self.household_id * 9973)

        if self.savings_rate_target is None:
            self.savings_rate_target = sample_range(
                (config.min_savings_rate, config.max_savings_rate),
                clip_min=0.0,
                clip_max=1.0,
            )
        self.savings_rate_target = max(config.min_savings_rate, min(config.max_savings_rate, self.savings_rate_target))

        # Traits: deterministic pseudo-random sampled from config ranges
        self.spending_tendency = sample_range(config.spending_tendency_range, clip_min=0.1, clip_max=5.0)
        self.food_preference = sample_range(config.food_preference_range, clip_min=0.1, clip_max=5.0)
        self.services_preference = sample_range(config.services_preference_range, clip_min=0.1, clip_max=5.0)
        self.housing_preference = sample_range(config.housing_preference_range, clip_min=0.1, clip_max=5.0)
        self.quality_lavishness = sample_range(config.quality_lavishness_range, clip_min=0.1, clip_max=5.0)
        self.frugality = sample_range(config.frugality_range, clip_min=0.1, clip_max=5.0)
        self.saving_tendency = sample_range(config.saving_tendency_range, clip_min=0.0, clip_max=1.0)

        # Bank deposit behavior derived from saving_tendency.
        # saving_tendency ~ [0, 1]:  0 = spendthrift, 1 = extreme saver
        # Population mean saving_tendency ≈ 0.5 → mean buffer ≈ 6 weeks, mean fraction ≈ 0.20
        # Range: buffer 3-10 weeks, fraction 0.05-0.40
        st = self.saving_tendency
        self.deposit_buffer_weeks = 3.0 + 7.0 * st       # [3, 10] weeks
        self.deposit_fraction = 0.05 + 0.35 * st          # [0.05, 0.40]

        # Savings drawdown rate: fraction of cash savings drawn per tick for consumption.
        # Spenders (high spending_tendency, low saving_tendency) draw down faster.
        # Savers (low spending_tendency, high saving_tendency) draw down slowly.
        # spend_norm in [0,1], st in [0,1]: spender_score peaks at spend=max, save=min
        spend_norm = (self.spending_tendency - 0.1) / 4.9  # normalize spending_tendency to [0,1]
        spender_score = spend_norm * (1.0 - st)            # [0,1]: 1 = max spender, 0 = max saver
        self.savings_drawdown_rate = 0.01 + 0.04 * spender_score  # [1%, 5%] per tick

        self.household_service_happiness_base_boost = sample_range(
            config.service_happiness_base_boost_range,
            clip_min=0.0,
            clip_max=1.0,
        )
        self.healthcare_preference = sample_range(config.healthcare_preference_range, clip_min=0.1, clip_max=5.0)
        self.healthcare_request_base_chance_pct = sample_range(
            config.healthcare_request_base_chance_pct_range,
            clip_min=0.0,
            clip_max=50.0,
        )
        self.healthcare_urgency_threshold = sample_range(
            config.healthcare_urgency_threshold_range,
            clip_min=0.05,
            clip_max=0.99,
        )
        self.healthcare_critical_threshold = sample_range(
            config.healthcare_critical_threshold_range,
            clip_min=0.01,
            clip_max=0.95,
        )
        if self.healthcare_critical_threshold >= self.healthcare_urgency_threshold:
            critical_margin = rng.uniform(0.01, 0.05)
            self.healthcare_critical_threshold = max(
                0.01,
                self.healthcare_urgency_threshold - critical_margin + rng.uniform(-jitter, jitter),
            )
        self.morale_employed_boost = sample_range(config.morale_employed_boost_range, clip_min=0.0, clip_max=1.0)
        self.morale_unemployed_penalty = sample_range(config.morale_unemployed_penalty_range, clip_min=0.0, clip_max=1.0)
        self.morale_unhoused_penalty = sample_range(config.morale_unhoused_penalty_range, clip_min=0.0, clip_max=1.0)
        self.medical_doctor_capacity_cap = sample_range(
            config.medical_doctor_capacity_range,
            clip_min=0.5,
            clip_max=5.0,
        )
        self.medical_doctor_expected_wage_anchor = sample_range(
            config.medical_doctor_expected_wage_range,
            clip_min=20.0,
            clip_max=500.0,
        )
        self.medical_doctor_reservation_wage_anchor = sample_range(
            config.medical_doctor_reservation_wage_range,
            clip_min=10.0,
            clip_max=500.0,
        )
        annual_interest = sample_range(
            config.medical_school_interest_rate_range,
            clip_min=0.0,
            clip_max=0.5,
        )
        self.medical_school_annual_interest_rate = annual_interest
        self.medical_school_weekly_interest_rate = annual_interest / max(1.0, float(CONFIG.time.ticks_per_year))

        # Initialize health decay characteristic (annual health loss)
        # Distribution: majority lose 0-20 per year, some 20-30, very few 30-50
        rand_val = rng.random()
        if rand_val < config.health_decay_low_probability:
            self.health_decay_per_year = sample_range(config.health_decay_low_range, clip_min=0.0, clip_max=1.0)
        elif rand_val < config.health_decay_mid_probability:
            self.health_decay_per_year = sample_range(config.health_decay_mid_range, clip_min=0.0, clip_max=1.0)
        else:  # 5% of people: 30-50 health loss per year (chronic conditions)
            self.health_decay_per_year = sample_range(config.health_decay_high_range, clip_min=0.0, clip_max=1.0)

        # Convert annual decay to per-tick decay (52 ticks per year)
        self.health_decay_rate = self.health_decay_per_year / 52.0

        if not self.category_weights:
            self.category_weights = {
                "food": 0.34,
                "housing": 0.33,
                "services": 0.33,
            }
        biased_weights = {
            "food": self.category_weights.get("food", 0.0) * self.food_preference,
            "housing": self.category_weights.get("housing", 0.0) * self.housing_preference,
            "services": self.category_weights.get("services", 0.0) * self.services_preference,
        }
        self.category_weights = self._normalize_category_weights(biased_weights)

        if not self.purchase_styles:
            style_options = ["cheap", "value", "quality"]
            base_offset = self.household_id % len(style_options)
            for idx, category in enumerate(sorted(self.category_weights.keys())):
                style = style_options[(base_offset + idx) % len(style_options)]
                self.purchase_styles[category] = style
        self.purchase_styles = {
            category.lower(): self.purchase_styles[category].lower()
            for category in self.purchase_styles
        }
        self.default_purchase_style = self.default_purchase_style.lower()

        # --- Additional per-household randomized parameters ---
        self.consumption_budget_share = sample_range(config.consumption_budget_share_range, clip_min=0.1, clip_max=1.0)
        self.quality_preference_weight = sample_range(config.quality_preference_weight_range, clip_min=0.1, clip_max=5.0)
        self.price_sensitivity = sample_range(config.price_sensitivity_range, clip_min=0.1, clip_max=5.0)
        self.expected_wage = sample_range(config.expected_wage_range, clip_min=1.0, clip_max=200.0)
        self.reservation_wage = sample_range(config.reservation_wage_range, clip_min=1.0, clip_max=200.0)
        # Ensure reservation_wage < expected_wage
        if self.reservation_wage >= self.expected_wage:
            self.reservation_wage = self.expected_wage * rng.uniform(0.6, 0.9)
        self.price_expectation_alpha = sample_range(config.price_expectation_alpha_range, clip_min=0.01, clip_max=1.0)

        # Stagger on-the-job search cooldowns so not all workers check simultaneously
        self.job_search_cooldown = rng.randint(0, 52)
        self.job_switch_threshold = sample_range((0.10, 0.25), clip_min=0.05, clip_max=0.50)
        self.wage_expectation_alpha = sample_range(config.wage_expectation_alpha_range, clip_min=0.01, clip_max=1.0)
        self.reservation_markup_over_benefit = sample_range(config.reservation_markup_range, clip_min=1.0, clip_max=2.0)
        self.min_cash_for_aggressive_job_search = sample_range(config.min_cash_aggressive_search_range, clip_min=10.0, clip_max=1000.0)
        self.skill_growth_rate = sample_range(config.skill_growth_rate_range, clip_min=0.0, clip_max=0.01)
        self.happiness = sample_range(config.initial_happiness_range, clip_min=0.0, clip_max=1.0)
        self.morale = sample_range(config.initial_morale_range, clip_min=0.0, clip_max=1.0)
        self.happiness_decay_rate = sample_range(config.happiness_decay_rate_range, clip_min=0.0, clip_max=0.1)
        self.morale_decay_rate = sample_range(config.morale_decay_rate_range, clip_min=0.0, clip_max=0.1)
        self.min_food_per_tick = sample_range(config.min_food_per_tick_range, clip_min=0.5, clip_max=10.0)
        self.min_services_per_tick = sample_range(config.min_services_per_tick_range, clip_min=0.1, clip_max=5.0)

    def _normalize_category_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize spending-category budget weights so they sum to 1.0.

        Negative weights are clamped to zero and duplicate category keys
        (differing only in case) are merged.  If every weight is non-positive,
        falls back to an equal split across food / housing / services so the
        household never ends up with a zero-budget plan.

        Args:
            weights: Raw category → weight mapping (may contain mixed-case keys).

        Returns:
            Lowercased category → fraction mapping that sums to 1.0.
        """
        normalized: Dict[str, float] = {}
        total = 0.0
        for category, weight in weights.items():
            weight = max(0.0, weight)
            if weight <= 0:
                continue
            category_key = category.lower()
            normalized[category_key] = normalized.get(category_key, 0.0) + weight
            total += weight

        if total <= 0:
            fallback_categories = ["food", "housing", "services"]
            normalized = {cat: 1.0 / len(fallback_categories) for cat in fallback_categories}
            total = 1.0

        return {category: weight / total for category, weight in normalized.items()}

    def _get_affordability_score(self) -> float:
        """
        Calculate a normalized affordability score based on skills, cash, and wages.

        Returns:
            Float in [0.1, 4.0] representing how flexible the household can be on prices.
        """
        wage_basis = self.wage if self.wage > 0 else self.expected_wage
        skill_component = self.skills_level * 1.5
        cash_component = min(3.0, self.cash_balance / 400.0)
        wage_component = min(3.0, wage_basis / 40.0)

        score = 0.3 * skill_component + 0.35 * cash_component + 0.35 * wage_component
        return max(0.1, min(4.0, score))

    def _get_category_price_cap(
        self,
        category: str,
        options: Optional[List[Dict[str, float]]] = None,
        precomputed_prices: Optional[tuple] = None,
    ) -> float:
        """
        Determine the maximum acceptable price for a category this tick.
        """
        if precomputed_prices:
            min_price, median_price, max_price = precomputed_prices
        else:
            prices = [opt.get("price", 0.0) for opt in options if opt.get("price", 0.0) > 0]
            if not prices:
                return 0.0

            prices.sort()
            min_price = prices[0]
            max_price = prices[-1]
            median_price = prices[len(prices) // 2]

        affordability = self._get_affordability_score()
        wage_basis = self.wage if self.wage > 0 else self.expected_wage
        liquid_cash = max(25.0, self.cash_balance * 0.2 + wage_basis)

        base_cap = min_price * (1.2 + 2.5 * affordability)
        median_cap = median_price * (0.8 + affordability)
        premium_cap = max_price * min(affordability, 2.5)

        price_cap = max(base_cap, median_cap, premium_cap)
        price_cap = min(price_cap, liquid_cash)

        if affordability > 2.0:
            price_cap = max(price_cap, min(liquid_cash * 1.2, max_price))

        price_cap *= self.quality_lavishness

        return max(min_price * 1.1, price_cap)

    def refresh_awareness_pool(
        self,
        category_market_info: Dict[str, List[Dict[str, float]]],
        current_tick: int
    ) -> None:
        """
        Feature 3: Refresh the bounded awareness pool for firm selection.

        Every pool_refresh_interval ticks, drop the lowest-utility firm from each
        category's pool and randomly sample a new firm from the global market to
        simulate organic discovery. Also initializes pools if empty.

        Mutates state: awareness_pool, last_pool_refresh_tick.

        Args:
            category_market_info: category -> list of firm dicts with firm_id, price, quality
            current_tick: Current simulation tick
        """
        config = CONFIG.households
        max_pool = config.awareness_pool_max_size

        for category, all_firms in category_market_info.items():
            if not all_firms:
                continue
            all_firm_ids = [f["firm_id"] for f in all_firms if f.get("price", 0.0) > 0]
            if not all_firm_ids:
                continue

            current_pool = self.awareness_pool.get(category, [])

            # Remove stale firm IDs no longer in the market
            valid_firm_set = set(all_firm_ids)
            current_pool = [fid for fid in current_pool if fid in valid_firm_set]

            if not current_pool:
                # Initialize: sample up to max_pool firms from the market
                sample_size = min(max_pool, len(all_firm_ids))
                current_pool = random.sample(all_firm_ids, sample_size)
            elif len(current_pool) < max_pool:
                # Pool is below capacity — fill up before doing drop/add rotation.
                # This ensures the pool grows when new firms enter the market.
                pool_set = set(current_pool)
                candidates = [fid for fid in all_firm_ids if fid not in pool_set]
                fill_count = min(max_pool - len(current_pool), len(candidates))
                if fill_count > 0 and candidates:
                    current_pool.extend(random.sample(candidates, fill_count))
                self.last_pool_refresh_tick = current_tick
            elif current_tick - self.last_pool_refresh_tick >= config.pool_refresh_interval:
                # Periodic refresh: drop lowest-utility firms, add new random ones
                firm_lookup = {f["firm_id"]: f for f in all_firms}
                # Compute utility for each firm in pool
                pool_utilities = []
                for fid in current_pool:
                    info = firm_lookup.get(fid)
                    if info:
                        utility = (self.quality_lavishness * info.get("quality", 0.0)
                                   - self.price_sensitivity * info.get("price", 0.0))
                        pool_utilities.append((fid, utility))
                    else:
                        pool_utilities.append((fid, -float("inf")))

                # Sort by utility ascending, drop the worst
                pool_utilities.sort(key=lambda x: x[1])
                drop_count = min(config.pool_refresh_drop_count, len(pool_utilities))
                dropped_ids = {pool_utilities[i][0] for i in range(drop_count)}
                current_pool = [fid for fid in current_pool if fid not in dropped_ids]

                # Sample new firms not already in pool
                pool_set = set(current_pool)
                candidates = [fid for fid in all_firm_ids if fid not in pool_set]
                add_count = min(drop_count, len(candidates), max_pool - len(current_pool))
                if add_count > 0 and candidates:
                    current_pool.extend(random.sample(candidates, add_count))

            # Enforce max pool size
            if len(current_pool) > max_pool:
                current_pool = current_pool[:max_pool]

            self.awareness_pool[category] = current_pool

        self.last_pool_refresh_tick = current_tick

    def _get_switching_friction(self, category: str) -> float:
        """Return the switching friction threshold for a given category."""
        config = CONFIG.households
        frictions = {
            "housing": config.switching_friction_housing,
            "food": config.switching_friction_food,
            "services": config.switching_friction_services,
            "healthcare": config.switching_friction_services,
        }
        return frictions.get(category.lower(), config.switching_friction_food)

    def _filter_to_awareness_pool(
        self,
        category: str,
        options: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """
        Feature 3: Filter firm options to only those in this household's awareness pool.

        Falls back to full options list if no pool exists for the category.
        """
        pool = self.awareness_pool.get(category)
        if not pool:
            return options
        pool_set = set(pool)
        filtered = [opt for opt in options if opt.get("firm_id") in pool_set]
        return filtered if filtered else options  # Fallback if pool has no valid firms

    def _apply_switching_friction(
        self,
        category: str,
        best_firm_id: int,
        best_utility: float,
        firm_utilities: Dict[int, float]
    ) -> int:
        """
        Feature 3: Apply switching friction - a new firm must beat the current primary
        firm's utility by a friction threshold to become the new primary target.

        Returns the firm_id to actually purchase from (may be current primary).
        """
        current_primary = self.current_primary_firm.get(category)
        if current_primary is None or current_primary not in firm_utilities:
            # No existing primary, adopt the best
            self.current_primary_firm[category] = best_firm_id
            return best_firm_id

        current_utility = firm_utilities[current_primary]
        friction = self._get_switching_friction(category)

        # New firm must exceed current primary by friction threshold
        if best_utility > current_utility * (1.0 + friction):
            self.current_primary_firm[category] = best_firm_id
            return best_firm_id
        else:
            return current_primary

    def _plan_category_purchases(
        self,
        budget: float,
        firm_market_info: Dict[str, List[Dict[str, float]]],
        price_cache: Optional[Dict[str, tuple]] = None,
        biased_weights_override: Optional[Dict[str, float]] = None,
        category_fraction_override: Optional[Dict[str, float]] = None,
        category_option_cache: Optional[Dict[str, List[Dict[str, float]]]] = None,
        category_array_cache: Optional[Dict[str, Dict[str, np.ndarray]]] = None,
        debug_category_fractions: Optional[Dict[str, float]] = None
    ) -> Dict[int, float]:
        """
        Plan purchases using budget allocations influenced by preferences/traits.
        Feature 3: Softmax utilities only computed on the awareness pool (not all firms).
        """
        planned: Dict[int, float] = {}

        lavishness = self.quality_lavishness
        sensitivity = self.price_sensitivity
        household_cfg = CONFIG.households

        allowed_categories = {"food", "housing", "services"}
        if category_fraction_override is not None:
            fractions = {
                k.lower(): v
                for k, v in category_fraction_override.items()
                if v > 0 and k.lower() in allowed_categories
            }
        elif biased_weights_override is not None:
            biased = {
                k.lower(): v
                for k, v in biased_weights_override.items()
                if k.lower() in allowed_categories
            }
            total_bias = sum(biased.values())
            if total_bias <= 0:
                return planned
            fractions = {cat: weight / total_bias for cat, weight in biased.items() if weight > 0}
        else:
            biased = {
                "food": self.category_weights.get("food", 0.0) * self.food_preference,
                "housing": self.category_weights.get("housing", 0.0) * self.housing_preference,
                "services": self.category_weights.get("services", 0.0) * self.services_preference,
            }
            total_bias = sum(biased.values())
            if total_bias <= 0:
                return planned
            fractions = {cat: weight / total_bias for cat, weight in biased.items() if weight > 0}

        # Proportional food priority: the less food eaten relative to the
        # health-sustaining threshold, the more budget shifts to food from
        # other categories.  At zero food, all discretionary budget goes to food.
        food_target = max(self.min_food_per_tick, household_cfg.food_health_high_threshold)
        if self.food_consumed_last_tick < food_target:
            shortfall = 1.0 - (self.food_consumed_last_tick / max(0.1, food_target))
            # Shift from services first (luxury), then housing (partial)
            services_share = max(0.0, fractions.get("services", 0.0))
            services_shift = shortfall * services_share
            fractions["services"] = services_share - services_shift
            # Also shift from housing when severely short on food
            housing_share = max(0.0, fractions.get("housing", 0.0))
            housing_shift = max(0.0, shortfall - 0.3) * housing_share * 0.5  # kicks in below 70% food
            fractions["housing"] = housing_share - housing_shift
            fractions["food"] = fractions.get("food", 0.0) + services_shift + housing_shift

        # Services comfort floor: if services were under-consumed last tick, pull a
        # moderate share from housing (not food) back into services.
        services_target = max(0.1, self.min_services_per_tick)
        if self.services_consumed_last_tick < services_target:
            shortfall = 1.0 - (self.services_consumed_last_tick / services_target)
            housing_share = max(0.0, fractions.get("housing", 0.0))
            shift = 0.5 * shortfall * housing_share
            fractions["housing"] = housing_share - shift
            fractions["services"] = fractions.get("services", 0.0) + shift

        total_fraction = sum(max(v, 0.0) for v in fractions.values())
        if total_fraction <= 0:
            return planned
        fractions = {cat: max(0.0, share) / total_fraction for cat, share in fractions.items() if share > 0}
        if debug_category_fractions is not None:
            debug_category_fractions.clear()
            debug_category_fractions.update(fractions)

        housing_share = fractions.pop("housing", 0.0)
        housing_budget_cap = max(0.0, budget * housing_share)
        remaining_budget = budget
        housing_qty_remaining = 1.0

        if housing_budget_cap > 0 and remaining_budget > 0:
            h_arrays = category_array_cache.get("housing") if category_array_cache else None
            if h_arrays is not None:
                h_firm_ids = h_arrays["firm_ids"]
                h_prices = h_arrays["prices"]
                h_qualities = h_arrays["qualities"]
                # Awareness pool filter via index mask
                pool = self.awareness_pool.get("housing")
                if pool:
                    pool_set = set(pool)
                    mask = np.array([int(fid) in pool_set for fid in h_firm_ids], dtype=bool)
                    if mask.any():
                        h_firm_ids = h_firm_ids[mask]
                        h_prices = h_prices[mask]
                        h_qualities = h_qualities[mask]

                precomputed = price_cache.get("housing") if price_cache else None
                price_cap = self._get_category_price_cap(
                    "housing", None,
                    precomputed_prices=precomputed,
                )
                if price_cap > 0:
                    value_ratios = h_qualities / np.maximum(h_prices, 1e-9)
                    style = self.purchase_styles.get("housing", self.default_purchase_style)
                    if style == "cheap":
                        chosen_idx = int(h_prices.argmin())
                    elif style == "quality":
                        chosen_idx = int(h_qualities.argmax())
                    else:  # "value" or default
                        chosen_idx = int(value_ratios.argmax())

                    chosen_price = float(h_prices[chosen_idx])
                    if chosen_price > 0:
                        # Switching friction using arrays
                        inv_price_cap = 1.0 / max(price_cap, 1e-6)
                        h_utils = lavishness * h_qualities - sensitivity * (h_prices * inv_price_cap)
                        chosen_fid = int(h_firm_ids[chosen_idx])
                        chosen_util = float(h_utils[chosen_idx])
                        h_util_map = dict(zip(h_firm_ids.tolist(), h_utils.tolist()))
                        target_id = self._apply_switching_friction(
                            "housing", chosen_fid, chosen_util, h_util_map
                        )
                        target_idx_arr = np.where(h_firm_ids == target_id)[0]
                        if target_idx_arr.size > 0:
                            t_idx = int(target_idx_arr[0])
                            price = float(h_prices[t_idx])
                        else:
                            price = chosen_price
                            target_id = chosen_fid
                        allowed_budget = min(remaining_budget, housing_budget_cap)
                        qty = min(housing_qty_remaining, allowed_budget / price)
                        if qty > 0:
                            cost = qty * price
                            remaining_budget = max(0.0, remaining_budget - cost)
                            housing_qty_remaining -= qty
                            planned[target_id] = planned.get(target_id, 0.0) + qty

        total_other_share = sum(fractions.values())
        weights_remaining = total_other_share

        # Precompute food satiation cap once (avg_price is same for all households)
        food_avg_price = 0.0
        food_max_budget_cap = float('inf')
        if category_array_cache and "food" in category_array_cache:
            food_avg_price = float(category_array_cache["food"]["prices"].mean())
            if food_avg_price > 0:
                food_max_budget_cap = household_cfg.food_health_high_threshold * food_avg_price

        for category, share in fractions.items():
            if share <= 0 or remaining_budget <= 0 or weights_remaining <= 0:
                continue

            # Use precomputed arrays from cache
            arrays = category_array_cache.get(category) if category_array_cache else None
            if arrays is None:
                weights_remaining -= share
                continue

            g_firm_ids = arrays["firm_ids"]
            g_prices = arrays["prices"]
            g_qualities = arrays["qualities"]

            # Awareness pool filter via index mask on precomputed arrays
            pool = self.awareness_pool.get(category)
            if pool:
                pool_set = set(pool)
                mask = np.array([int(fid) in pool_set for fid in g_firm_ids], dtype=bool)
                if mask.any():
                    firm_ids = g_firm_ids[mask]
                    prices = g_prices[mask]
                    qualities = g_qualities[mask]
                else:
                    firm_ids = g_firm_ids
                    prices = g_prices
                    qualities = g_qualities
            else:
                firm_ids = g_firm_ids
                prices = g_prices
                qualities = g_qualities

            if firm_ids.size == 0:
                weights_remaining -= share
                continue

            precomputed = price_cache.get(category) if price_cache else None
            price_cap = self._get_category_price_cap(
                category, None,
                precomputed_prices=precomputed,
            )
            if price_cap <= 0:
                weights_remaining -= share
                continue

            category_budget = remaining_budget * (share / weights_remaining)
            weights_remaining -= share
            if category_budget <= 0:
                continue

            # Food satiation cap (precomputed avg_price)
            if category == "food" and food_avg_price > 0:
                category_budget = min(category_budget, food_max_budget_cap)

            # Utilities and softmax weights (only on awareness pool)
            inv_price_cap = 1.0 / max(price_cap, 1e-6)
            utilities = lavishness * qualities - sensitivity * (prices * inv_price_cap)
            # Add deterministic, non-negative seeded noise to break ties in purchasing decisions.
            # Python's built-in hash() can be negative and process-randomized.
            category_seed = zlib.crc32(category.encode("utf-8"))
            tie_break_seed = ((self.household_id * 1_315_423_911) ^ category_seed) & 0xFFFFFFFF
            rng = np.random.default_rng(seed=tie_break_seed)
            utilities += rng.uniform(-0.25, 0.25, size=len(utilities))

            # Switching friction - determine primary firm
            best_idx = int(utilities.argmax())
            best_fid = int(firm_ids[best_idx])
            best_util = float(utilities[best_idx])
            # Build utility map only for switching friction check
            primary = self.current_primary_firm.get(category)
            if primary is not None:
                primary_arr = np.where(firm_ids == primary)[0]
                if primary_arr.size > 0:
                    current_util = float(utilities[int(primary_arr[0])])
                    friction = self._get_switching_friction(category)
                    if best_util > current_util * (1.0 + friction):
                        self.current_primary_firm[category] = best_fid
                        primary_fid = best_fid
                    else:
                        primary_fid = primary
                else:
                    self.current_primary_firm[category] = best_fid
                    primary_fid = best_fid
            else:
                self.current_primary_firm[category] = best_fid
                primary_fid = best_fid

            # Boost the primary firm's weight in the softmax distribution
            primary_mask = firm_ids == primary_fid
            utilities[primary_mask] += 0.5  # Loyalty bonus for primary firm

            max_u = utilities.max()
            weights = np.exp(utilities - max_u)
            weight_sum = weights.sum()
            if weight_sum <= 0:
                continue
            shares = weights / weight_sum

            firm_budgets = category_budget * shares
            quantities = firm_budgets / prices
            cap_ratio = prices / price_cap
            clamped_sensitivity = max(0.2, min(1.5, sensitivity))
            adjustments = np.where(
                cap_ratio > 0.85,
                np.maximum(0.15, 1.0 - clamped_sensitivity * (cap_ratio - 0.85) * 3.0),
                1.0
            )
            quantities *= adjustments
            # Filter to positive quantities and accumulate into planned dict
            pos_mask = quantities > 0
            fids_pos = firm_ids[pos_mask].tolist()
            qtys_pos = quantities[pos_mask].tolist()
            prices_pos = prices[pos_mask]
            spent = float((quantities[pos_mask] * prices_pos).sum())
            for fid, qty in zip(fids_pos, qtys_pos):
                planned[fid] = planned.get(fid, 0.0) + qty
            remaining_budget = max(0.0, remaining_budget - min(spent, remaining_budget))

        return planned

    @property
    def is_employed(self) -> bool:
        """Check if household is currently employed."""
        return self.employer_id is not None

    @property
    def can_work(self) -> bool:
        """
        Check whether the household is healthy enough to participate in labor matching.

        Health below 0.10 means the household is too sick to work this tick.
        The performance multiplier already degrades output for unhealthy workers;
        this threshold only excludes the truly incapacitated.
        """
        if self.medical_training_status == "student":
            return False
        return self.health >= 0.10

    def to_dict(self) -> Dict[str, object]:
        """
        Serialize all fields to basic Python types.

        Returns:
            Dictionary representation of the household state
        """
        return {
            "household_id": self.household_id,
            "skills_level": self.skills_level,
            "age": self.age,
            "cash_balance": self.cash_balance,
            "goods_inventory": dict(self.goods_inventory),
            "employer_id": self.employer_id,
            "wage": self.wage,
            "owns_housing": self.owns_housing,
            "met_housing_need": self.met_housing_need,
            "spending_tendency": self.spending_tendency,
            "food_preference": self.food_preference,
            "services_preference": self.services_preference,
            "housing_preference": self.housing_preference,
            "healthcare_preference": self.healthcare_preference,
            "healthcare_request_base_chance_pct": self.healthcare_request_base_chance_pct,
            "quality_lavishness": self.quality_lavishness,
            "frugality": self.frugality,
            "household_service_happiness_base_boost": self.household_service_happiness_base_boost,
            "healthcare_urgency_threshold": self.healthcare_urgency_threshold,
            "healthcare_critical_threshold": self.healthcare_critical_threshold,
            "morale_employed_boost": self.morale_employed_boost,
            "morale_unemployed_penalty": self.morale_unemployed_penalty,
            "morale_unhoused_penalty": self.morale_unhoused_penalty,
            "food_consumed_this_tick": self.food_consumed_this_tick,
            "services_consumed_this_tick": self.services_consumed_this_tick,
            "healthcare_consumed_this_tick": self.healthcare_consumed_this_tick,
            "care_plan_due_ticks": list(self.care_plan_due_ticks),
            "care_plan_heal_deltas": list(self.care_plan_heal_deltas),
            "care_plan_anchor_tick": self.care_plan_anchor_tick,
            "pending_visit_heal_delta": self.pending_visit_heal_delta,
            "pending_healthcare_visits": self.pending_healthcare_visits,
            "next_healthcare_request_tick": self.next_healthcare_request_tick,
            "last_checkup_tick": self.last_checkup_tick,
            "queued_healthcare_firm_id": self.queued_healthcare_firm_id,
            "healthcare_queue_enter_tick": self.healthcare_queue_enter_tick,
            "consumption_budget_share": self.consumption_budget_share,
            "good_weights": dict(self.good_weights),
            "category_weights": dict(self.category_weights),
            "savings_rate_target": self.savings_rate_target,
            "purchase_styles": dict(self.purchase_styles),
            "quality_preference_weight": self.quality_preference_weight,
            "price_sensitivity": self.price_sensitivity,
            "category_experience": dict(self.category_experience),
            "price_beliefs": dict(self.price_beliefs),
            "expected_wage": self.expected_wage,
            "reservation_wage": self.reservation_wage,
            "price_expectation_alpha": self.price_expectation_alpha,
            "wage_expectation_alpha": self.wage_expectation_alpha,
            "reservation_markup_over_benefit": self.reservation_markup_over_benefit,
            "default_price_level": self.default_price_level,
            "min_cash_for_aggressive_job_search": self.min_cash_for_aggressive_job_search,
            "min_food_per_tick": self.min_food_per_tick,
            "min_services_per_tick": self.min_services_per_tick,
            "medical_training_status": self.medical_training_status,
            "medical_training_start_tick": self.medical_training_start_tick,
            "medical_school_debt_principal": self.medical_school_debt_principal,
            "medical_school_debt_remaining": self.medical_school_debt_remaining,
            "medical_school_payment_per_tick": self.medical_school_payment_per_tick,
            "medical_doctor_capacity_cap": self.medical_doctor_capacity_cap,
            "bank_deposit": self.bank_deposit,
            "medical_loan_principal": self.medical_loan_principal,
            "medical_loan_remaining": self.medical_loan_remaining,
        }

    def plan_labor_supply(
        self,
        unemployment_benefit: float = 0.0,
        mean_posted_wage: float = 0.0,
        category_posted_wages: Optional[Dict[str, float]] = None,
        employer_category: Optional[str] = None,
    ) -> Dict[str, object]:
        """
        Decide whether to search for job and what wage to require.

        Uses the household's reservation_wage field, which is adapted over time
        from realized labor outcomes in apply_labor_outcome().

        Does not mutate state; returns a plan dict.

        Args:
            unemployment_benefit: Government support (unused - kept for API compatibility)
            mean_posted_wage: Mean wage currently being posted by hiring firms.
                Used as a fallback newspaper signal.
            category_posted_wages: Optional per-category posted wage means.
            employer_category: Current employer category for employed workers.

        Returns:
            Dict with household_id, searching_for_job, reservation_wage, skills_level,
            and job_switching (True if an employed worker is actively shopping for better pay)
        """
        # Note: unemployment_benefit parameter kept for backward compatibility but not used.
        # Reservation wage is updated through household expectation dynamics in apply_labor_outcome().
        reservation_wage_for_tick = self.reservation_wage

        # Medical students are in full-time training and cannot join the labor pool.
        if self.medical_training_status == "student":
            return {
                "household_id": self.household_id,
                "searching_for_job": False,
                "reservation_wage": reservation_wage_for_tick,
                "skills_level": self.skills_level,
                "medical_only": False,
            }

        config = CONFIG.households

        # Dynamic living cost based on price beliefs
        expected_housing_price = self.price_beliefs.get("housing", self.default_price_level)
        expected_food_price = self.price_beliefs.get("food", self.default_price_level)
        living_cost = 0.3 * expected_housing_price + self.min_food_per_tick * expected_food_price

        # Desperation scaling: the worse off you are, the lower your standards.
        # Factors: low cash, poor health, long unemployment — each independently
        # pushes the reservation wage down.  A fully desperate agent accepts
        # any positive wage.
        desperation = 0.0

        # Cash desperation: ramps from 0→1 as cash drops below 2× living cost
        cash_threshold = living_cost * 2.0
        if self.cash_balance < cash_threshold:
            desperation += 1.0 - max(0.0, self.cash_balance / max(1.0, cash_threshold))

        # Health desperation: sick people can't be picky
        if self.health < 0.5:
            desperation += (0.5 - self.health) * 2.0  # 0→1 as health 0.5→0

        # Unemployment duration desperation: patience runs out
        hh_config = CONFIG.households
        if self.unemployment_duration > 0:
            desperation += min(1.0, self.unemployment_duration / max(1.0, hh_config.unemployed_forced_dissaving_duration * 0.4))

        # Homelessness desperation: unhoused households accept lower wages faster
        if self.renting_from_firm_id is None:
            desperation += 0.3

        # Clamp total desperation to [0, 1]
        desperation = min(1.0, desperation / 2.0)  # normalize: any 2 of 3 factors → fully desperate

        # Scale reservation wage: at full desperation, accept desperation_wage_discount of normal
        wage_floor_fraction = 1.0 - (1.0 - hh_config.desperation_wage_discount) / hh_config.desperation_wage_discount * desperation
        reservation_wage_for_tick *= wage_floor_fraction

        # Absolute floor: never go below $1 (any job beats no job)
        reservation_wage_for_tick = max(1.0, reservation_wage_for_tick)

        # Search if unemployed or if cash stress is severe.
        searching_for_job = (not self.is_employed) or (self.cash_balance < living_cost)

        posted_wage_signal = mean_posted_wage
        if (
            self.is_employed
            and employer_category is not None
            and category_posted_wages is not None
            and category_posted_wages.get(employer_category, 0.0) > 0.0
        ):
            posted_wage_signal = float(category_posted_wages[employer_category])

        # On-the-job search ("newspaper" mechanic):
        # Employed workers periodically sample the market. If posted wages are
        # meaningfully above their current wage they enter the candidate pool.
        # Medical students/residents/doctors skip — they have a dedicated pipeline.
        job_switching = False
        if (self.is_employed
                and self.can_work
                and self.medical_training_status not in {"student", "resident", "doctor"}
                and self.job_search_cooldown <= 0
                and posted_wage_signal > 0):
            threshold = self.wage * (1.0 + self.job_switch_threshold)
            if posted_wage_signal >= threshold:
                searching_for_job = True
                job_switching = True

        if not self.can_work:
            searching_for_job = False
            job_switching = False

        medical_only = self.medical_training_status in {"resident", "doctor"}

        return {
            "household_id": self.household_id,
            "searching_for_job": searching_for_job,
            "reservation_wage": reservation_wage_for_tick,
            "skills_level": self.skills_level,
            "medical_only": medical_only,
            "job_switching": job_switching,
        }

    def tick_job_search_cooldown(self, rng: "random.Random") -> None:
        """Decrement job search cooldown and reset when it expires.

        Called once per tick by the economy before plan_labor_supply.
        Reset uses 52 ± up to 5 ticks of jitter so workers don't
        synchronise after the first reset.
        """
        if self.job_search_cooldown > 0:
            self.job_search_cooldown -= 1
        else:
            # Reset: will be able to check next year (± jitter)
            self.job_search_cooldown = 52 + rng.randint(-5, 5)

    def compute_saving_rate(self) -> float:
        """
        Compute the saving rate as a fraction of income (0.0 to 0.15).

        The saving rate is based on:
        1. Household's innate saving_tendency (thriftiness)
        2. Current wealth relative to typical wealth range
        3. Very low-wealth households save less (paycheck-to-paycheck)

        Returns:
            Float in [0.0, 0.15] representing fraction of income to save
        """

        # Get wealth reference points from config
        low_w = CONFIG.households.low_wealth_reference
        high_w = CONFIG.households.high_wealth_reference

        # Ensure valid range
        if high_w <= low_w:
            high_w = low_w + 1.0

        # Compute wealth_score in [0, 1]
        # Use cash_balance as a proxy for wealth (could also include goods_inventory value)
        wealth = self.cash_balance
        wealth_score = (wealth - low_w) / (high_w - low_w)
        wealth_score = max(0.0, min(1.0, wealth_score))

        # Combine saving_tendency and wealth_score
        # Thrifty + wealthy households save more
        mix = 0.5 * self.saving_tendency + 0.5 * wealth_score
        raw_saving_share = 0.01 + 0.14 * mix  # Range: 1% to 15%

        # Adjustment: very low-wealth households save even less
        # Poor households are paycheck-to-paycheck, can't afford to save
        adjustment_low_wealth = 1.0 - 0.7 * (1.0 - wealth_score) ** 2
        adjusted_saving_share = raw_saving_share * adjustment_low_wealth

        # Clamp to [0.0, 0.15]
        saving_rate = max(0.0, min(0.15, adjusted_saving_share))

        return saving_rate

    def maybe_request_consumption_loan(self, bank: Optional["BankAgent"] = None) -> None:
        """Fix 25: Request a small consumption loan if cash is critically low.

        Conditions: cash below subsistence, credit score >= 0.4, total
        consumption debt < 4× weekly wage.  Sets needs_consumption_loan and
        consumption_loan_amount flags for processing by the economy.
        """
        self.needs_consumption_loan = False
        self.consumption_loan_amount = 0.0

        if self.cash_balance >= self.subsistence_min_cash:
            return
        if bank is None:
            return

        credit_score = bank.household_credit_scores.get(self.household_id, 0.5)
        if credit_score < 0.4:
            return

        amount = self.subsistence_min_cash * 4.0

        # Leverage check: total consumption debt < 4× weekly income baseline
        weekly_wage = self.wage if self.employer_id is not None else self.expected_wage * 0.5
        income_baseline = max(weekly_wage, self.subsistence_min_cash)
        if self.consumption_loan_remaining + amount > income_baseline * 4.0:
            return

        self.needs_consumption_loan = True
        self.consumption_loan_amount = amount

    def plan_consumption(
        self,
        market_prices: Dict[str, float],
        firm_qualities: Dict[str, float] = None,
        firm_categories: Dict[str, str] = None,
        firm_market_info: Optional[Dict[str, List[Dict[str, float]]]] = None,
        unemployment_rate: float = 0.0,
        unemployment_benefit: float = 30.0,
    ) -> Dict[str, object]:
        """
        Decide desired budget allocation across categories.

        NEW APPROACH: Budget scales with total liquid wealth (cash + this tick's wage).
        - Fraction of wealth spent grows with confidence and wealth
        - High-income households (CEOs) now deploy far more capital each tick

        Does not mutate state; returns a plan dict with category budgets.
        Market clearing will handle firm selection within categories.

        Args:
            market_prices: Current market prices for goods (good_name -> price)
            firm_qualities: Quality levels for goods (good_name -> quality) - optional
            firm_categories: Category mappings (good_name -> category) - optional

        Returns:
            Dict with household_id, category_budgets, and legacy planned_purchases
        """
        config = CONFIG.households
        confidence = 1.0 / (1.0 + max(unemployment_rate, 0.0))

        # Income-anchored consumption: spending driven by current income, not accumulated wealth.
        # Savings provide a slow supplemental drawdown, not a spend-everything pool.
        disposable_income = self.wage if self.is_employed else unemployment_benefit

        spend_fraction = config.min_spend_fraction + (config.confidence_multiplier * confidence)
        if self.is_employed:
            saving_rate = self.compute_saving_rate()
            spend_fraction += 0.1  # Stability bonus for steady income
            spend_fraction *= max(0.5, 1.0 - saving_rate)
        else:
            spend_fraction -= 0.05  # Unemployed households stay cautious

        panic_factor = min(1.0, unemployment_rate * config.unemployment_spend_sensitivity)
        spend_fraction *= max(0.2, 1.0 - panic_factor)
        spend_fraction = max(config.min_spend_fraction, min(config.max_spend_fraction, spend_fraction))

        base_budget = spend_fraction * disposable_income

        # Savings drawdown: personality-derived fraction of accumulated cash (slow trickle)
        drawdown = self.savings_drawdown_rate * max(0.0, self.cash_balance)

        # Desperation mode: when income alone can't cover survival minimum,
        # raid savings aggressively (economically realistic — people burn savings when broke)
        subsistence_min = config.subsistence_min_cash
        if base_budget < subsistence_min and self.cash_balance > 0.0:
            emergency_rate = min(0.20, self.savings_drawdown_rate * 5.0)
            drawdown = min(emergency_rate * self.cash_balance, subsistence_min - base_budget)

        budget = min(base_budget + drawdown, max(0.0, self.cash_balance))

        if budget <= 0:
            return {
                "household_id": self.household_id,
                "category_budgets": {},
                "planned_purchases": {},  # legacy field for backward compatibility
            }

        # Use category weights if available, otherwise fall back to good weights
        if self.category_weights and sum(self.category_weights.values()) > 0 and firm_market_info:
            planned_purchases = self._plan_category_purchases(budget, firm_market_info)
            return {
                "household_id": self.household_id,
                "category_budgets": {},
                "planned_purchases": planned_purchases,
            }
        else:
            # Legacy good-based allocation (backward compatibility)
            # Create local copy of price beliefs for planning (don't mutate state)
            local_beliefs = dict(self.price_beliefs)

            # Update local beliefs with market prices
            for good, market_price in market_prices.items():
                if good in local_beliefs:
                    # Feature 4: Asymmetric smoothing (Prospect Theory)
                    old_belief = local_beliefs[good]
                    if market_price > old_belief:
                        alpha = config.price_alpha_up
                    else:
                        alpha = config.price_alpha_down
                    local_beliefs[good] = alpha * market_price + (1.0 - alpha) * old_belief
                else:
                    # Initialize belief to market price
                    local_beliefs[good] = market_price

            # Normalize good weights
            total_weight = sum(self.good_weights.values())
            if total_weight <= 0:
                # No weights specified: treat all goods equally
                all_goods = set(local_beliefs.keys()) | set(market_prices.keys())
                if not all_goods:
                    # No goods available
                    normalized_weights = {}
                else:
                    equal_weight = 1.0 / len(all_goods)
                    normalized_weights = {g: equal_weight for g in all_goods}
            else:
                normalized_weights = {
                    g: w / total_weight for g, w in self.good_weights.items()
                }

            # Plan purchases for each good
            planned_purchases = {}
            housing_infos = []
            other_infos = []
            for good, weight in normalized_weights.items():
                if weight <= 0:
                    continue
                if good in local_beliefs:
                    expected_price = local_beliefs[good]
                elif good in market_prices:
                    expected_price = market_prices[good]
                else:
                    expected_price = self.default_price_level
                if expected_price <= 0:
                    continue
                category = _get_good_category(good, firm_categories)
                if category == "housing":
                    housing_infos.append((good, weight, expected_price))
                else:
                    other_infos.append((good, weight, expected_price))

            remaining_budget = budget
            housing_needed = 1.0
            housing_infos.sort(key=lambda item: item[2])
            for good, weight, expected_price in housing_infos:
                if remaining_budget <= 0 or housing_needed <= 0:
                    break
                target_budget = budget * weight if weight > 0 else remaining_budget
                allowed_budget = min(remaining_budget, target_budget)
                if allowed_budget <= 0:
                    continue
                qty = min(housing_needed, allowed_budget / expected_price)
                if qty <= 0:
                    continue
                cost = qty * expected_price
                planned_purchases[good] = planned_purchases.get(good, 0.0) + qty
                remaining_budget = max(0.0, remaining_budget - cost)
                housing_needed -= qty

            weights_remaining = sum(weight for _, weight, _ in other_infos if weight > 0)
            for good, weight, expected_price in other_infos:
                if remaining_budget <= 0 or weight <= 0 or weights_remaining <= 0:
                    break
                share = weight / weights_remaining
                weights_remaining -= weight
                good_budget = remaining_budget * share
                if good_budget <= 0:
                    continue
                qty = good_budget / expected_price
                if qty <= 0:
                    continue
                cost = qty * expected_price
                planned_purchases[good] = planned_purchases.get(good, 0.0) + qty
                remaining_budget = max(0.0, remaining_budget - cost)

            return {
                "household_id": self.household_id,
                "category_budgets": {},  # Empty for legacy mode
                "planned_purchases": planned_purchases,
            }

    def _deterministic_unit_random(self, current_tick: int, salt: int = 0) -> float:
        """
        Fast deterministic pseudo-random draw in [0, 1) without object allocation.
        """
        seed = (
            int(CONFIG.random_seed)
            ^ ((self.household_id + 1) * 2_654_435_761)
            ^ ((current_tick + 1) * 2_246_822_519)
            ^ ((salt + 1) * 3_266_489_917)
        ) & 0xFFFFFFFF
        seed = (1_664_525 * seed + 1_013_904_223) & 0xFFFFFFFF
        return seed / 4_294_967_296.0

    def should_request_healthcare_service(self, current_tick: int) -> bool:
        """
        Probabilistic healthcare demand model with follow-up episodes.

        1) Episode trigger probability (annualized):
           base_chance_pct + missing_health_pct
        2) Multi-visit episode size scales with missing health.
        3) Follow-ups are spaced over time so one household does not monopolize care.
        """
        if current_tick < self.next_healthcare_request_tick:
            return False

        if self.pending_healthcare_visits <= 0:
            missing_health_pct = max(0.0, min(100.0, (1.0 - self.health) * 100.0))
            base_chance_pct = max(0.0, min(50.0, float(self.healthcare_request_base_chance_pct)))
            annual_chance_pct = max(0.0, min(100.0, base_chance_pct + missing_health_pct))

            # Spread annual chance across the planning window to keep per-tick load stable.
            demand_window_ticks = max(1, int(CONFIG.households.healthcare_plan_interval_ticks))
            tick_request_probability = annual_chance_pct / (100.0 * demand_window_ticks)

            if self._deterministic_unit_random(current_tick, salt=17) >= tick_request_probability:
                return False

            max_visits = max(1, int(CONFIG.households.healthcare_episode_max_visits))
            additional_visits = int(round((missing_health_pct / 100.0) * max(0, max_visits - 1)))
            self.pending_healthcare_visits = max(1, min(max_visits, 1 + additional_visits))

        visits_remaining = max(1, self.pending_healthcare_visits)
        missing_health = max(0.0, 1.0 - self.health)
        self.pending_visit_heal_delta = missing_health / float(visits_remaining)
        self.pending_healthcare_visits = max(0, self.pending_healthcare_visits - 1)

        max_gap = max(1, int(CONFIG.households.healthcare_followup_gap_max_ticks))
        gap_ticks = 1 + int(self.health * max(0, max_gap - 1))
        self.next_healthcare_request_tick = current_tick + gap_ticks
        return True

    def _healthcare_visit_distribution(self) -> List[tuple[int, float]]:
        """Return annual visit-count distribution by current health bucket."""
        hc = CONFIG.households
        if self.health < 0.10:
            return list(hc.healthcare_visit_distribution_below_10)
        if self.health < 0.30:
            return list(hc.healthcare_visit_distribution_below_30)
        if self.health < 0.70:
            return list(hc.healthcare_visit_distribution_below_70)
        return list(hc.healthcare_visit_distribution_healthy)

    def _sample_annual_visit_count(self, anchor_tick: int) -> int:
        """
        Sample annual visit count from configured distribution.

        Deterministic per household and annual anchor tick for reproducibility.
        """
        distribution = self._healthcare_visit_distribution()
        if not distribution:
            return 0
        total_weight = sum(max(0.0, w) for _, w in distribution)
        if total_weight <= 0.0:
            return 0
        rng = random.Random(CONFIG.random_seed + self.household_id * 9973 + anchor_tick * 37)
        draw = rng.random() * total_weight
        cumulative = 0.0
        for visits, weight in distribution:
            w = max(0.0, weight)
            cumulative += w
            if draw <= cumulative:
                return max(0, int(visits))
        return max(0, int(distribution[-1][0]))

    def _refresh_annual_healthcare_visit_plan(self, current_tick: int) -> None:
        """
        Generate a new annual visit schedule if we entered a new 52-tick window.
        """
        interval = max(1, int(CONFIG.households.healthcare_plan_interval_ticks))
        anchor_tick = (current_tick // interval) * interval
        if self.care_plan_anchor_tick == anchor_tick:
            return

        self.care_plan_anchor_tick = anchor_tick
        self.care_plan_due_ticks = []
        self.care_plan_heal_deltas = []
        self.pending_visit_heal_delta = 0.0

        visits = self._sample_annual_visit_count(anchor_tick)
        if visits <= 0:
            return

        missing_health = max(0.0, 1.0 - self.health)
        heal_per_visit = missing_health / float(visits)
        spacing = interval / float(visits)
        rng = random.Random(
            CONFIG.random_seed + self.household_id * 9973 + anchor_tick * 37 + visits * 193
        )
        due_ticks: List[int] = []
        for idx in range(visits):
            slot_start = idx * spacing
            slot_end = (idx + 1) * spacing
            sampled_offset = rng.uniform(slot_start, max(slot_start, slot_end - 1e-6))
            due_tick = anchor_tick + int(sampled_offset)
            due_tick = max(anchor_tick, min(anchor_tick + interval - 1, due_tick))
            due_ticks.append(due_tick)
        due_ticks.sort()
        self.care_plan_due_ticks = due_ticks
        self.care_plan_heal_deltas = [heal_per_visit for _ in due_ticks]

    def _consume_due_healthcare_slot(self, current_tick: int) -> bool:
        """
        Pop one due healthcare slot and stage its heal amount for the next completed visit.
        """
        for idx, due_tick in enumerate(self.care_plan_due_ticks):
            if due_tick <= current_tick:
                heal_delta = 0.0
                if idx < len(self.care_plan_heal_deltas):
                    heal_delta = max(0.0, self.care_plan_heal_deltas[idx])
                    self.care_plan_heal_deltas.pop(idx)
                self.pending_visit_heal_delta = heal_delta
                self.care_plan_due_ticks.pop(idx)
                return True
        return False

    def start_medical_training(self, current_tick: int) -> bool:
        """
        Enroll household in the medical training pipeline.

        Returns True when enrollment started this tick.
        """
        if self.medical_training_status != "none":
            return False
        self.medical_training_status = "student"
        self.medical_training_start_tick = current_tick
        self.employer_id = None
        self.wage = 0.0
        return True

    def update_medical_training_progress(self, current_tick: int) -> None:
        """Advance student -> resident -> doctor based on elapsed training ticks."""
        if self.medical_training_status not in {"student", "resident"}:
            return

        training_ticks = max(1, int(CONFIG.households.medical_training_ticks))
        elapsed = max(0, current_tick - self.medical_training_start_tick)
        residency_tick = int(training_ticks * CONFIG.households.medical_residency_start_fraction)

        if self.medical_training_status == "student" and elapsed >= residency_tick:
            self.medical_training_status = "resident"
            self.expected_wage = max(self.expected_wage, self.medical_doctor_expected_wage_anchor * 0.6)
            self.reservation_wage = max(self.reservation_wage, self.medical_doctor_reservation_wage_anchor * 0.6)

        if elapsed >= training_ticks:
            self.medical_training_status = "doctor"
            self.expected_wage = max(self.expected_wage, self.medical_doctor_expected_wage_anchor)
            self.reservation_wage = max(self.reservation_wage, self.medical_doctor_reservation_wage_anchor)

    def medical_visit_capacity(self) -> float:
        """
        Visits per tick contributed by this household when employed at healthcare firm.
        """
        if self.medical_training_status == "resident":
            resident_max = max(0.0, CONFIG.households.medical_resident_max_capacity)
            return min(resident_max, resident_max * max(0.25, self.skills_level))
        if self.medical_training_status == "doctor":
            capped = max(0.5, self.medical_doctor_capacity_cap)
            return min(capped, 2.0 + 1.0 * self.skills_level)
        return 0.0

    def accrue_medical_school_interest(self) -> None:
        """Accrue weekly interest on remaining medical school debt."""
        if self.medical_school_debt_remaining <= 0.0:
            return
        self.medical_school_debt_remaining += (
            self.medical_school_debt_remaining * max(0.0, self.medical_school_weekly_interest_rate)
        )

    def make_medical_school_payment(self) -> float:
        """
        Pay down medical school debt from household cash.

        Returns:
            Amount paid this tick.
        """
        if self.medical_school_debt_remaining <= 0.0:
            self.medical_school_payment_per_tick = 0.0
            return 0.0

        cfg = CONFIG.households
        wage_based = self.wage * cfg.medical_school_repayment_share_of_wage if self.is_employed else 0.0
        baseline = cfg.medical_school_min_payment if self.medical_training_status == "doctor" else 0.0
        target_payment = max(baseline, wage_based)
        if target_payment <= 0.0:
            self.medical_school_payment_per_tick = 0.0
            return 0.0

        payment = min(target_payment, self.medical_school_debt_remaining, self.cash_balance)
        if payment <= 0.0:
            self.medical_school_payment_per_tick = 0.0
            return 0.0

        self.cash_balance -= payment
        self.medical_school_debt_remaining -= payment
        self.medical_school_payment_per_tick = payment

        if self.medical_school_debt_remaining <= 1e-6:
            self.medical_school_debt_remaining = 0.0
            self.medical_school_debt_principal = 0.0
            self.medical_school_payment_per_tick = 0.0
        return payment

    def take_medical_loan(self, loan_amount: float) -> None:
        """
        Take out a medical loan to cover healthcare costs.

        Loan terms:
        - Interest rate: 1-3% annually (random, scaled by 52 ticks/year)
        - Repayment: 10% of wage per tick
        - Only available to employed households

        Args:
            loan_amount: Amount to borrow for medical expenses
        """

        # Deterministic interest rate seeded by household and loan amount so runs are reproducible
        _loan_rng = random.Random(CONFIG.random_seed + self.household_id * 6_700_417 + int(loan_amount * 100))
        annual_interest_rate = _loan_rng.uniform(0.01, 0.03)

        # Calculate total repayment with interest (simple interest)
        # Total = principal × (1 + annual_rate)
        total_repayment = loan_amount * (1.0 + annual_interest_rate)

        # Set loan terms
        self.medical_loan_principal = loan_amount
        self.medical_loan_remaining = total_repayment
        self.medical_loan_payment_per_tick = 0.0

        # Grant the loan (add to cash balance)
        self.cash_balance += loan_amount
        self.add_ledger_flow("bank", loan_amount)

    def make_medical_loan_payment(self) -> float:
        """
        Make a medical loan payment based on minimum wage.

        Returns:
            Amount paid toward loan this tick

        Mutates state by deducting payment from cash and reducing loan balance.
        """
        if self.medical_loan_remaining <= 0:
            return 0.0

        min_wage = CONFIG.government.default_unemployment_benefit * CONFIG.government.wage_floor_multiplier
        base_payment = 0.10 * min_wage
        payment_amount = min(base_payment, self.medical_loan_remaining, self.cash_balance)

        if payment_amount <= 0:
            return 0.0

        self.cash_balance -= payment_amount
        self.medical_loan_remaining -= payment_amount
        self.add_ledger_flow("bank", -payment_amount)

        if self.medical_loan_remaining <= 0:
            self.medical_loan_payment_per_tick = 0.0
            self.medical_loan_principal = 0.0

        return payment_amount

    def apply_labor_outcome(
        self,
        outcome: Dict[str, object],
        market_wage_anchor: Optional[float] = None,
        current_tick: int = 0
    ) -> None:
        """
        Update employment status and wage beliefs based on labor market outcome.

        Mutates state.

        Args:
            outcome: Dict with employer_id (int | None), wage (float), and employer_category (str | None)
            market_wage_anchor: Optional market-paid wage to nudge expectations toward
            current_tick: Current simulation tick (for rate-limiting skill/wage growth)
        """
        self.employer_id = outcome["employer_id"]
        self.wage = outcome["wage"]
        employer_category = outcome.get("employer_category", None)

        # Track experience in category (increment by 1 tick if employed)
        if self.is_employed:
            self.unemployment_duration = 0
            if employer_category is not None:
                if employer_category not in self.category_experience:
                    self.category_experience[employer_category] = 0
                self.category_experience[employer_category] += 1

            # Passive skill growth through work experience (diminishing returns)
            # Only update skills once every 52 ticks (yearly)
            if current_tick - self.last_skill_update_tick >= 52:
                skill_improvement = self.skill_growth_rate * (1.0 - self.skills_level)
                # Apply 52 ticks worth of growth at once
                total_improvement = skill_improvement * 52
                self.skills_level = min(1.0, self.skills_level + total_improvement)
                self.last_skill_update_tick = current_tick

        # Update wage expectations
        if self.is_employed and self.wage > 0:
            # Employed: update expected wage toward actual wage
            self.expected_wage = (
                self.wage_expectation_alpha * self.wage +
                (1.0 - self.wage_expectation_alpha) * self.expected_wage
            )
        else:
            self.unemployment_duration += 1

            # Adaptive decay: the more desperate, the faster expectations drop.
            hh_config = CONFIG.households
            duration_pressure = min(
                hh_config.duration_pressure_cap,
                self.unemployment_duration * hh_config.duration_pressure_rate,
            )
            # Cash pressure: broke people adjust fast
            cash_pressure = 0.0
            cash_threshold = hh_config.poverty_threshold
            if self.cash_balance < cash_threshold:
                cash_pressure = min(
                    hh_config.happiness_pressure_cap,
                    (cash_threshold - self.cash_balance) / max(cash_threshold, 1.0) * hh_config.happiness_pressure_cap,
                )
            # Health pressure: sick people take what they can get
            health_pressure = 0.0
            if self.health < hh_config.happiness_threshold:
                health_pressure = min(
                    0.2,
                    (hh_config.happiness_threshold - self.health) * hh_config.happiness_pressure_rate,
                )

            decay_factor = max(
                hh_config.min_decay_factor,
                hh_config.base_wage_decay - duration_pressure - cash_pressure - health_pressure,
            )
            decayed_expectation = max(self.expected_wage * decay_factor, hh_config.wage_floor)

            if market_wage_anchor is not None:
                anchor_weight = hh_config.unemployed_market_anchor_weight
                self.expected_wage = (
                    (1.0 - anchor_weight) * decayed_expectation
                    + anchor_weight * market_wage_anchor
                )
            else:
                self.expected_wage = decayed_expectation

        # Reservation wage tracks expected wage — faster when desperate
        hh_config = CONFIG.households
        if self.unemployment_duration > 5:
            res_rate = hh_config.reservation_adjustment_rate * 3.0
        else:
            res_rate = hh_config.reservation_adjustment_rate * 1.5
        self.reservation_wage = (
            res_rate * self.expected_wage +
            (1.0 - res_rate) * self.reservation_wage
        )

    def apply_income_and_taxes(self, flows: Dict[str, float]) -> None:
        """
        Update cash balance based on income, transfers, and taxes.

        Mutates state.

        Args:
            flows: Dict with wage_income, transfers, and taxes_paid
        """
        wage_income = flows.get("wage_income", 0.0)
        transfers = flows.get("transfers", 0.0)
        taxes_paid = flows.get("taxes_paid", 0.0)

        self.cash_balance += wage_income + transfers - taxes_paid

    def apply_purchases(self, purchases: Dict[str, tuple[float, float]],
                        firm_categories: Optional[Dict[str, str]] = None) -> None:
        """
        Update inventory, cash, and price beliefs based on executed purchases.

        Mutates state.

        Args:
            purchases: Dict mapping good_name -> (quantity, price_paid)
            firm_categories: Optional dict mapping good_name -> category (to detect housing purchases)
        """
        # Pre-check: total purchase cost won't cause catastrophic negative balance
        total_purchase_cost = sum(q * p for q, p in purchases.values())
        if self.cash_balance - total_purchase_cost < CONFIG.households.extreme_negative_cash_threshold:
            raise ValueError(
                f"Household {self.household_id} purchases ({total_purchase_cost:.2f}) would exceed "
                f"catastrophic threshold. Cash: {self.cash_balance:.2f}. Aborting."
            )

        for good, (quantity, price_paid) in purchases.items():
            # Update cash
            total_cost = quantity * price_paid
            self.cash_balance -= total_cost

            # Check if this is a housing purchase
            category = _get_good_category(good, firm_categories)
            if category == "healthcare":
                # Healthcare is service-only and should not enter storable inventory.
                continue
            if category == "services":
                # Services are non-storable household flow consumption.
                self.services_consumed_this_tick += quantity
                continue
            if category == "housing" and quantity > 0:
                self.owns_housing = True
                self.met_housing_need = True

            # Update inventory
            if good not in self.goods_inventory:
                self.goods_inventory[good] = 0.0
            self.goods_inventory[good] += quantity

            # Feature 4: Asymmetric Adaptive Expectations (Prospect Theory)
            # Price increases are absorbed faster (loss aversion) than decreases
            if good in self.price_beliefs:
                old_belief = self.price_beliefs[good]
                config = CONFIG.households
                if price_paid > old_belief:
                    alpha = config.price_alpha_up  # Fast adjustment to inflation
                else:
                    alpha = config.price_alpha_down  # Slow adjustment to deflation
                self.price_beliefs[good] = alpha * price_paid + (1.0 - alpha) * old_belief
            else:
                self.price_beliefs[good] = price_paid

        # Safety check: detect serious bugs
        if self.cash_balance < -1e6:  # Allow some float tolerance but catch serious errors
            raise ValueError(
                f"Household {self.household_id} cash balance became extremely negative: "
                f"{self.cash_balance}. This indicates a configuration or market clearing bug."
            )

    def invest_in_education(self, investment_amount: float) -> bool:
        """
        Invest cash in education to improve skills.

        Returns True if investment was made, False if insufficient cash.

        Args:
            investment_amount: Amount of cash to invest

        Returns:
            bool: True if investment successful, False otherwise
        """
        if self.cash_balance >= investment_amount and investment_amount > 0:
            self.cash_balance -= investment_amount

            # Diminishing returns: harder to improve at higher skill levels
            skill_gain_rate = 0.0001  # 0.1 skill points per $1000 invested at low skills
            skill_gain = investment_amount * skill_gain_rate * (1.0 - self.skills_level)
            self.skills_level = min(1.0, self.skills_level + skill_gain)

            return True
        return False

    def maybe_active_education(self) -> bool:
        """
        Actively invest in education when unemployed and below median skill.

        Trigger: skills < 0.5, cash > 300, unemployed.
        Cost: $100, Skill gain: +0.005
        """
        if self.is_employed:
            return False
        if self.skills_level >= 0.5 or self.cash_balance <= 300.0:
            return False

        cost = 100.0
        if self.cash_balance >= cost:
            self.cash_balance -= cost
            self.skills_level = min(1.0, self.skills_level + 0.005)
            self.education_active_this_tick = True
            self.add_ledger_flow("education", -cost)
            return True
        return False

    def apply_skill_decay(self) -> None:
        """
        Feature 1: Skill Hysteresis - prolonged unemployment degrades skills.

        If unemployed for more than the configured threshold of consecutive ticks,
        skills degrade by a small percentage per tick, bottoming out at a minimum.

        Mutates state: skills_level.
        """
        config = CONFIG.households
        if self.is_employed:
            return
        if self.unemployment_duration <= config.skill_decay_unemployment_threshold:
            return
        # Degrade skills toward the floor
        if self.skills_level > config.skill_decay_floor:
            self.skills_level = max(
                config.skill_decay_floor,
                self.skills_level - config.skill_decay_rate_per_tick
            )

    def consume_goods(self, good_categories: Optional[Dict[str, str]] = None) -> None:
        """
        Consume goods from inventory each tick.

        Households consume a fraction of their goods inventory each tick
        to represent using up food, services, housing, etc.

        Mutates state.
        """
        consumption_rate = 0.1  # Consume 10% of inventory per tick
        housing_usage = 1.0  # Housing treated as a service: consume need each tick
        self.met_housing_need = False

        for good in list(self.goods_inventory.keys()):
            if self.goods_inventory[good] > 0:
                category = _get_good_category(good, good_categories)
                current_qty = self.goods_inventory[good]
                if category == "housing":
                    self.met_housing_need = current_qty >= housing_usage
                    new_qty = max(0.0, current_qty - housing_usage)
                    self.goods_inventory[good] = new_qty
                    if new_qty < 0.001 and self.owns_housing:
                        self.owns_housing = False
                elif category == "services":
                    # Services are non-storable; purge any legacy remnants.
                    self.goods_inventory[good] = 0.0
                elif category == "healthcare":
                    # Healthcare is service-only; purge any legacy inventory remnants.
                    self.goods_inventory[good] = 0.0
                else:
                    consumed = current_qty * consumption_rate
                    self.goods_inventory[good] = max(0.0, current_qty - consumed)

                # Remove from dict if depleted
                if self.goods_inventory[good] < 0.001:
                    del self.goods_inventory[good]

    def update_wellbeing(self, government_happiness_multiplier: float = 1.0) -> None:
        """
        Update happiness, morale, and health for the current tick.

        Uses per-tick consumption counters to avoid sticky wellbeing effects from
        persistent inventory.
        """
        hc = CONFIG.households
        gov_cfg = CONFIG.government

        food_units = self.food_consumed_this_tick

        # --- Happiness ---
        happiness_positive = 0.0
        happiness_negative = 0.0

        if self.cash_balance < hc.extreme_poverty_threshold:
            happiness_negative -= hc.extreme_poverty_penalty
        elif self.cash_balance < hc.poverty_threshold:
            happiness_negative -= hc.poverty_penalty

        if government_happiness_multiplier > 1.0:
            happiness_positive += (government_happiness_multiplier - 1.0) * hc.government_happiness_scaling

        # Consumption satisfaction restores happiness — eating well and using services
        # makes people feel better. Without this, happiness decays monotonically to zero.
        #
        # Calibrated against decay_rate (0.002/tick): a household meeting all four
        # needs (food + services + housing + fair wage) recovers ~0.0025/tick,
        # roughly matching decay so a comfortable household stays roughly stable.
        # Partial need satisfaction produces a small net positive, nudging toward
        # equilibrium rather than zero.
        if food_units >= self.min_food_per_tick:
            happiness_positive += 0.0008  # Fed adequately
        if self.services_consumed_this_tick > 0:
            happiness_positive += 0.0005  # Used services
        if self.met_housing_need:
            happiness_positive += 0.0007  # Housing need met
        if self.is_employed and self.wage >= self.expected_wage:
            happiness_positive += 0.0005  # Earning what you expected

        # (a) Unemployment penalty: being jobless hurts independently of poverty
        if not self.is_employed:
            happiness_negative -= hc.unemployed_happiness_penalty

        # (b) Relative wealth-loss: losing cash hurts proportionally, not just at thresholds
        if self.last_tick_cash_start > 1.0:
            cash_loss_pct = max(0.0, (self.last_tick_cash_start - self.cash_balance) / max(self.last_tick_cash_start, 1.0))
            happiness_negative -= cash_loss_pct * hc.wealth_loss_happiness_scaling

        # (c) Food shortfall: not meeting minimum food hurts proportionally
        food_shortfall_ratio = max(0.0, (self.min_food_per_tick - food_units) / max(self.min_food_per_tick, 0.1))
        happiness_negative -= food_shortfall_ratio * hc.food_shortfall_happiness_scaling

        effective_happiness_decay = 0.0 if self.happiness < hc.mercy_floor_threshold else self.happiness_decay_rate
        happiness_change = happiness_positive + happiness_negative - effective_happiness_decay
        self.happiness = max(0.0, min(1.0, self.happiness + happiness_change))

        # --- Morale ---
        default_morale_employed = sum(hc.morale_employed_boost_range) / 2.0
        default_morale_unemployed = sum(hc.morale_unemployed_penalty_range) / 2.0
        default_morale_unhoused = sum(hc.morale_unhoused_penalty_range) / 2.0
        morale_employed = self.morale_employed_boost if self.morale_employed_boost is not None else default_morale_employed
        morale_unemployed = (
            self.morale_unemployed_penalty if self.morale_unemployed_penalty is not None else default_morale_unemployed
        )
        morale_unhoused = self.morale_unhoused_penalty if self.morale_unhoused_penalty is not None else default_morale_unhoused

        morale_positive = 0.0
        morale_negative = 0.0

        if self.is_employed:
            morale_positive += morale_employed
            if self.wage >= self.expected_wage:
                morale_positive += hc.wage_satisfaction_boost
            else:
                wage_gap_ratio = (self.expected_wage - self.wage) / max(self.expected_wage, 1.0)
                morale_negative -= wage_gap_ratio * hc.wage_dissatisfaction_scaling
        else:
            morale_negative -= morale_unemployed

        if not self.met_housing_need:
            morale_negative -= morale_unhoused

        morale_change = morale_positive + morale_negative - self.morale_decay_rate
        self.morale = max(0.0, min(1.0, self.morale + morale_change))

        # --- Health ---
        # Non-linear food→health: harsh penalty for no food, gentle near threshold.
        # Uses ratio^0.6 curve so partial eating is mostly OK but starvation hurts.
        food_ratio = min(1.0, food_units / max(0.1, hc.food_health_high_threshold))
        curved_ratio = food_ratio ** 0.6
        # At curved_ratio=0 (no food): health_effect = -starvation_penalty
        # At curved_ratio=1 (well fed): health_effect = +high_boost
        health_food_effect = (
            curved_ratio * (hc.food_health_high_boost + hc.food_starvation_penalty)
            - hc.food_starvation_penalty
        )

        health_positive = max(0.0, health_food_effect)
        health_negative = min(0.0, health_food_effect)

        if government_happiness_multiplier > 1.0:
            health_positive += (
                (government_happiness_multiplier - 1.0)
                * hc.government_health_scaling
                * gov_cfg.social_program_health_scaling
            )

        health_change = health_positive + health_negative - self.health_decay_rate
        self.health = max(0.0, min(1.0, self.health + health_change))

    def get_performance_multiplier(self) -> float:
        """
        Calculate overall performance multiplier based on wellbeing.

        Feature 4: Floor raised from 0.5x to 0.75x to prevent doom loop.
        A depressed worker is slower, but not catastrophically unproductive.

        Returns:
            Multiplier in range [0.75, 1.5]
            - Lowest wellbeing  = 0.75x performance
            - Perfect wellbeing = 1.50x performance
        """
        from config import CONFIG
        hc = CONFIG.households

        wellbeing_score = (
            self.morale * hc.performance_morale_weight +
            self.health * hc.performance_health_weight +
            self.happiness * hc.performance_happiness_weight
        )

        # Map [0, 1] wellbeing → [min_mult, max_mult]
        perf_range = hc.performance_max_multiplier - hc.performance_min_multiplier
        performance_multiplier = hc.performance_min_multiplier + (wellbeing_score * perf_range)

        return performance_multiplier


@dataclass(slots=True)
class FirmHealthSnapshot:
    """Shared per-tick firm health inputs used by multiple planners."""

    cash_runway_ticks: float
    smoothed_profit_margin: float
    sell_through_rate: float
    inventory_weeks: float
    unfilled_positions_streak: int
    worker_turnover_this_tick: int
    survival_mode: bool
    burn_mode: bool
    category_wage_anchor_p75: float


@dataclass(slots=True)
class FirmAgent(AgentMixin):
    """Represents a firm in the economic simulation.

    Firms produce goods, hire workers, set prices and wages, and respond
    to market conditions.  Each firm is assigned a personality
    (aggressive / moderate / conservative) that governs its risk tolerance,
    price adjustment speed, and R&D intensity.

    Behavior is deterministic when the simulation RNG is seeded — per-agent
    random draws derive from the firm's ID so that identical seeds produce
    identical trajectories.
    """

    # Identity & product (required fields first)
    firm_id: int
    good_name: str
    cash_balance: float
    inventory_units: float

    # Identity & product (optional fields with defaults)
    good_category: str = "Generic"  # e.g., "Food", "Housing", "Services"
    quality_level: float = 5.0  # 0-10 scale, affects market share
    employees: List[int] = field(default_factory=list)  # household_ids
    owners: List[int] = field(default_factory=list)  # household_ids who own this firm

    # Production & technology
    expected_sales_units: float = 100.0  # moving average
    production_capacity_units: float = 200.0  # max units per tick
    productivity_per_worker: float = 10.0  # units per worker per tick
    units_per_worker: float = 20.0  # hiring heuristic target

    # Labour market state
    wage_offer: float = 50.0
    planned_headcount: int = 0
    planned_hires_count: int = 0
    planned_layoffs_ids: List[int] = field(default_factory=list)
    last_tick_planned_hires: int = 0
    last_tick_actual_hires: int = 0
    unfilled_positions_streak: int = 0

    # Pricing & costs
    unit_cost: float = 5.0  # cost per unit produced
    markup: float = 0.3  # markup over unit_cost
    price: float = 6.5  # current price

    # Quality and R&D
    rd_spending_rate: float = 0.05  # fraction of revenue spent on R&D each tick
    quality_improvement_per_rd_dollar: float = 0.0002  # quality points per $ of R&D (slowed 50x)
    quality_decay_rate: float = 0.0  # quality decay removed
    accumulated_rd_investment: float = 0.0  # total R&D spending lifetime

    # Hidden happiness boost (Services category only) - households don't know this value
    happiness_boost_per_unit: float = 0.0  # 0.0 to 0.05 happiness gain per unit consumed

    # Healthcare service mode (non-storable): queue + visit capacity
    healthcare_queue: List[int] = field(default_factory=list)
    healthcare_capacity_per_worker: float = 0.0
    healthcare_backlog_horizon_ticks: float = 0.0
    healthcare_arrivals_ema: float = 0.0
    healthcare_requests_last_tick: float = 0.0
    healthcare_completed_visits_last_tick: float = 0.0
    healthcare_idle_streak: int = 0
    healthcare_capacity_carryover: float = 0.0

    # Config / tuning
    sales_expectation_alpha: float = 0.3  # [0,1] for smoothing sales
    price_adjustment_rate: float = 0.05  # small positive adjustment rate
    wage_adjustment_rate: float = 0.1  # small positive adjustment rate
    target_inventory_multiplier: float = 1.5  # desired inventory as multiple of expected sales
    min_price: float = 5.0  # hard floor on price
    max_hires_per_tick: int = 2
    max_fires_per_tick: int = 2
    target_inventory_weeks: float = 2.0  # desired weeks of supply buffer
    price_pressure: float = 0.0  # accumulator for pricing control

    # Firm personality & strategy
    # "aggressive": High risk, high reward - invests heavily, adjusts prices aggressively
    # "conservative": Low risk, stable - minimal investment, gradual adjustments
    personality: str = "moderate"  # "aggressive", "moderate", or "conservative"
    investment_propensity: float = 0.05  # Fraction of profits to invest (varies by personality)
    risk_tolerance: float = 0.5  # 0-1 scale, affects pricing and hiring decisions
    is_baseline: bool = False
    baseline_production_quota: float = 500.0
    actual_wages: Dict[int, float] = field(default_factory=dict)
    last_tick_total_costs: float = 0.0  # Track costs for dividend calculation
    payout_ratio: float = 0.0  # Fraction of net profit paid as dividends
    net_profit: float = 0.0  # Track last tick net profit

    # Loan tracking (for government startup loans)
    government_loan_principal: float = 0.0  # Original loan amount
    government_loan_remaining: float = 0.0  # Remaining balance
    loan_payment_per_tick: float = 0.0  # Weekly payment amount
    loan_support_ticks: int = 0  # Ticks remaining to meet hiring commitment
    loan_required_headcount: int = 0  # Target headcount promised when accepting aid
    ceo_household_id: Optional[int] = None  # CEO owner (gets high salary)

    # Housing-specific properties (only for housing firms)
    max_rental_units: int = 0  # Maximum number of tenants (0-50 for housing firms)
    current_tenants: List[int] = field(default_factory=list)  # household_ids renting
    property_tax_rate: float = 0.0  # Annual property tax rate based on units
    age_in_ticks: int = 0
    burn_mode: bool = False
    high_inventory_streak: int = 0
    low_inventory_streak: int = 0
    last_units_sold: float = 0.0
    last_units_produced: float = 0.0  # Track production for pricing decisions
    last_revenue: float = 0.0
    last_profit: float = 0.0
    revenue_ema: float = 0.0
    profit_ema: float = 0.0
    smoothed_profit_margin: float = 0.0
    cash_runway_ticks: float = float("inf")
    last_sell_through_rate: float = 0.5
    inventory_weeks: float = 0.0
    burn_mode_active: bool = False  # Track whether firm is in inventory burn mode
    zero_cash_streak: int = 0  # Consecutive ticks with zero or negative cash
    worker_turnover_this_tick: int = 0  # Workers lost to competitors this tick (on-the-job switching)
    stabilization_disabled: bool = False  # Experiment flag
    survival_mode: bool = False  # Feature 1: Emergency restructuring flag

    # Bank credit tracking (optional — unused when no bank exists)
    bank_loan_principal: float = 0.0       # Sum of active bank loan principals
    bank_loan_remaining: float = 0.0       # Sum of active bank loan remaining balances
    bank_loan_payment_per_tick: float = 0.0  # Total per-tick payment across all bank loans
    trailing_revenue_12t: float = 0.0      # EMA of revenue over ~12 ticks for leverage check

    # Fix 21: Capital stock (two-factor Cobb-Douglas production)
    capital_stock: float = 15.0               # Units of capital (abstract)
    capital_depreciation_rate: float = 0.01   # Fraction depreciated per tick
    capital_cost_per_unit: float = 500.0      # $ per unit of capital
    capital_investment_this_tick: float = 0.0 # Units invested this tick (reset each Phase 1)
    needs_investment_loan: bool = False        # Set in Phase 1; processed in Phase 1.5
    investment_loan_amount: float = 0.0        # $ amount needed from bank
    current_loan_rate: float = 0.05           # Last used lending rate (for MPK calc)

    # Housing expansion loans (for deadlock resolution)
    needs_housing_expansion_loan: bool = False  # Set in Phase 6.6; processed in Phase 6.6b
    housing_expansion_loan_amount: float = 0.0  # $ amount needed from bank for unit expansion

    def __post_init__(self):
        """Validate invariants after initialization."""
        if self.production_capacity_units < 0:
            raise ValueError(
                f"production_capacity_units cannot be negative, got {self.production_capacity_units}"
            )
        if self.productivity_per_worker < 0:
            raise ValueError(
                f"productivity_per_worker cannot be negative, got {self.productivity_per_worker}"
            )
        if not (0.0 <= self.quality_level <= 10.0):
            raise ValueError(f"quality_level must be in [0,10], got {self.quality_level}")
        if not (0.0 <= self.sales_expectation_alpha <= 1.0):
            raise ValueError(
                f"sales_expectation_alpha must be in [0,1], got {self.sales_expectation_alpha}"
            )
        if self.price_adjustment_rate < 0:
            raise ValueError(
                f"price_adjustment_rate must be non-negative, got {self.price_adjustment_rate}"
            )
        if self.wage_adjustment_rate < 0:
            raise ValueError(
                f"wage_adjustment_rate must be non-negative, got {self.wage_adjustment_rate}"
            )
        if self.markup < 0:
            raise ValueError(f"markup cannot be negative, got {self.markup}")
        if self.target_inventory_multiplier < 0:
            raise ValueError(
                f"target_inventory_multiplier cannot be negative, got {self.target_inventory_multiplier}"
            )
        if self.rd_spending_rate < 0:
            raise ValueError(f"rd_spending_rate cannot be negative, got {self.rd_spending_rate}")
        if self.payout_ratio <= 0:
            rng = random.Random(CONFIG.random_seed + self.firm_id * 7919)
            self.payout_ratio = rng.uniform(0.0, 0.5)

        if self.good_category.lower() == "healthcare":
            # Healthcare is non-storable service throughput.
            self.inventory_units = 0.0
            if self.healthcare_capacity_per_worker <= 0.0:
                self.healthcare_capacity_per_worker = CONFIG.firms.healthcare_capacity_per_worker_default
            if self.healthcare_backlog_horizon_ticks <= 0.0:
                self.healthcare_backlog_horizon_ticks = CONFIG.firms.healthcare_backlog_horizon_ticks

        # Sample personality-driven behavioral traits once at initialization.
        self.set_personality(self.personality)

    def to_dict(self) -> Dict[str, object]:
        """
        Serialize all fields to basic Python types.

        Returns:
            Dictionary representation of the firm state
        """
        return {
            "firm_id": self.firm_id,
            "good_name": self.good_name,
            "good_category": self.good_category,
            "quality_level": self.quality_level,
            "cash_balance": self.cash_balance,
            "inventory_units": self.inventory_units,
            "employees": list(self.employees),
            "owners": list(self.owners),
            "expected_sales_units": self.expected_sales_units,
            "production_capacity_units": self.production_capacity_units,
            "productivity_per_worker": self.productivity_per_worker,
            "units_per_worker": self.units_per_worker,
            "wage_offer": self.wage_offer,
            "planned_headcount": self.planned_headcount,
            "planned_hires_count": self.planned_hires_count,
            "planned_layoffs_ids": list(self.planned_layoffs_ids),
            "last_tick_planned_hires": self.last_tick_planned_hires,
            "last_tick_actual_hires": self.last_tick_actual_hires,
            "price": self.price,
            "unit_cost": self.unit_cost,
            "markup": self.markup,
            "min_price": self.min_price,
            "max_hires_per_tick": self.max_hires_per_tick,
            "max_fires_per_tick": self.max_fires_per_tick,
            "is_baseline": self.is_baseline,
            "baseline_production_quota": self.baseline_production_quota,
            "personality": self.personality,
            "investment_propensity": self.investment_propensity,
            "risk_tolerance": self.risk_tolerance,
            "target_inventory_weeks": self.target_inventory_weeks,
            "price_pressure": self.price_pressure,
            "payout_ratio": self.payout_ratio,
            "net_profit": self.net_profit,
            "last_revenue": self.last_revenue,
            "last_profit": self.last_profit,
            "revenue_ema": self.revenue_ema,
            "profit_ema": self.profit_ema,
            "smoothed_profit_margin": self.smoothed_profit_margin,
            "cash_runway_ticks": self.cash_runway_ticks,
            "last_sell_through_rate": self.last_sell_through_rate,
            "inventory_weeks": self.inventory_weeks,
            "unfilled_positions_streak": self.unfilled_positions_streak,
            "last_units_sold": self.last_units_sold,
            "government_loan_remaining": self.government_loan_remaining,
            "loan_payment_per_tick": self.loan_payment_per_tick,
            "bank_loan_principal": self.bank_loan_principal,
            "bank_loan_remaining": self.bank_loan_remaining,
            "bank_loan_payment_per_tick": self.bank_loan_payment_per_tick,
            "trailing_revenue_12t": self.trailing_revenue_12t,
            "age_in_ticks": self.age_in_ticks,
            "burn_mode": self.burn_mode,
            "high_inventory_streak": self.high_inventory_streak,
            "low_inventory_streak": self.low_inventory_streak,
            "survival_mode": self.survival_mode,
            "healthcare_queue": list(self.healthcare_queue),
            "healthcare_capacity_per_worker": self.healthcare_capacity_per_worker,
            "healthcare_backlog_horizon_ticks": self.healthcare_backlog_horizon_ticks,
            "healthcare_arrivals_ema": self.healthcare_arrivals_ema,
            "healthcare_requests_last_tick": self.healthcare_requests_last_tick,
            "healthcare_completed_visits_last_tick": self.healthcare_completed_visits_last_tick,
            "healthcare_capacity_carryover": self.healthcare_capacity_carryover,
        }

    def set_personality(self, personality: str) -> None:
        """
        Set firm personality and adjust behavior parameters accordingly.

        Aggressive firms: High investment, aggressive pricing, higher risk
        Conservative firms: Low investment, gradual pricing, lower risk
        Moderate firms: Balanced approach

        Mutates state.

        Args:
            personality: "aggressive", "conservative", or "moderate"
        """
        self.personality = personality.lower()
        config = CONFIG.firms
        jitter = 1e-6
        seed_offset = {"aggressive": 17, "conservative": 31, "moderate": 53}.get(self.personality, 53)
        rng = random.Random(CONFIG.random_seed + self.firm_id * 10007 + seed_offset)

        def sample_float(value_range: tuple[float, float], clip_min: float = 0.0, clip_max: float = 1.0e9) -> float:
            low, high = value_range
            if high < low:
                low, high = high, low
            value = rng.uniform(low, high) + rng.uniform(-jitter, jitter)
            return max(clip_min, min(clip_max, value))

        def sample_int(value_range: tuple[int, int], clip_min: int = 0, clip_max: int = 1_000_000) -> int:
            low, high = value_range
            if high < low:
                low, high = high, low
            sampled = rng.randint(int(low), int(high))
            return max(clip_min, min(clip_max, sampled))

        if self.personality == "aggressive":
            self.investment_propensity = sample_float(config.aggressive_investment_propensity_range, 0.0, 1.0)
            self.risk_tolerance = sample_float(config.aggressive_risk_tolerance_range, 0.0, 1.0)
            self.price_adjustment_rate = sample_float(config.aggressive_price_adjustment_range, 0.0, 1.0)
            self.wage_adjustment_rate = sample_float(config.aggressive_wage_adjustment_range, 0.0, 1.0)
            self.rd_spending_rate = sample_float(config.aggressive_rd_spending_range, 0.0, 1.0)
            self.max_hires_per_tick = sample_int(config.aggressive_max_hires_range, 1, 10)
            self.max_fires_per_tick = sample_int(config.aggressive_max_fires_range, 1, 10)
            self.units_per_worker = sample_float(config.aggressive_units_per_worker_range, 1.0, 1_000.0)
        elif self.personality == "conservative":
            self.investment_propensity = sample_float(config.conservative_investment_propensity_range, 0.0, 1.0)
            self.risk_tolerance = sample_float(config.conservative_risk_tolerance_range, 0.0, 1.0)
            self.price_adjustment_rate = sample_float(config.conservative_price_adjustment_range, 0.0, 1.0)
            self.wage_adjustment_rate = sample_float(config.conservative_wage_adjustment_range, 0.0, 1.0)
            self.rd_spending_rate = sample_float(config.conservative_rd_spending_range, 0.0, 1.0)
            self.max_hires_per_tick = sample_int(config.conservative_max_hires_range, 1, 10)
            self.max_fires_per_tick = sample_int(config.conservative_max_fires_range, 1, 10)
            self.units_per_worker = sample_float(config.conservative_units_per_worker_range, 1.0, 1_000.0)
        else:
            self.personality = "moderate"
            self.investment_propensity = sample_float(config.moderate_investment_propensity_range, 0.0, 1.0)
            self.risk_tolerance = sample_float(config.moderate_risk_tolerance_range, 0.0, 1.0)
            self.price_adjustment_rate = sample_float(config.moderate_price_adjustment_range, 0.0, 1.0)
            self.wage_adjustment_rate = sample_float(config.moderate_wage_adjustment_range, 0.0, 1.0)
            self.rd_spending_rate = sample_float(config.moderate_rd_spending_range, 0.0, 1.0)
            self.max_hires_per_tick = sample_int(config.moderate_max_hires_range, 1, 10)
            self.max_fires_per_tick = sample_int(config.moderate_max_fires_range, 1, 10)
            self.units_per_worker = sample_float(config.moderate_units_per_worker_range, 1.0, 1_000.0)

        # --- Per-firm randomized behavioral traits (independent of personality) ---
        # Skip for baseline (government safety-net) firms to preserve stable pricing
        if not self.is_baseline:
            self.sales_expectation_alpha = sample_float(config.sales_expectation_alpha_range, 0.01, 1.0)
            self.target_inventory_multiplier = sample_float(config.target_inventory_multiplier_range, 0.5, 10.0)
            self.target_inventory_weeks = sample_float(config.target_inventory_weeks_range, 0.5, 10.0)
            self.min_price = sample_float(config.min_price_range, 0.5, 50.0)
            self.quality_improvement_per_rd_dollar = sample_float(config.quality_improvement_per_rd_dollar_range, 0.0, 0.01)
            self.markup = sample_float(config.markup_range, 0.05, 1.0)
            self.unit_cost = sample_float(config.unit_cost_range, 1.0, 50.0)

    # --- Capacity / productivity helpers ---
    def _firm_config(self):
        """Return the shared ``CONFIG.firms`` dataclass for firm-level tuning knobs."""
        return CONFIG.firms

    def _capacity_for_workers(self, worker_count: float) -> float:
        """Two-factor Cobb-Douglas capacity: TFP * K^alpha_k * N^alpha_n."""
        config = self._firm_config()
        if worker_count <= 0:
            return 0.0
        units = max(self.units_per_worker, config.min_base_productivity)
        K = max(self.capital_stock, 0.01)
        return units * (K ** config.alpha_k) * (worker_count ** config.alpha_n)

    def _productivity_per_worker(self, worker_count: float) -> float:
        """Average worker productivity implied by the frontier."""
        if worker_count <= 0:
            return 0.0
        return self._capacity_for_workers(worker_count) / worker_count

    def _workers_for_sales(self, target_output: float) -> int:
        """Inverse of the two-factor capacity function to meet desired output."""
        config = self._firm_config()
        if target_output <= 0:
            return config.min_target_workers
        units = max(self.units_per_worker, config.min_base_productivity)
        K = max(self.capital_stock, 0.01)
        effective_tfp = units * (K ** config.alpha_k)
        required = (target_output / max(effective_tfp, 1e-6)) ** (1.0 / config.alpha_n)
        return max(config.min_target_workers, math.ceil(required))

    def _expected_skill_premium(self) -> float:
        """Baseline expectation for skill + experience wage premia."""
        return self._firm_config().expected_skill_premium

    def _current_wage_bill(self) -> float:
        """Current payroll burden using actual wages when available."""
        return sum(self.actual_wages.get(employee_id, self.wage_offer) for employee_id in self.employees)

    def _profit_ema_alpha(self) -> float:
        """Approximate 4-tick smoothing window."""
        return 2.0 / 5.0

    def _aggressiveness(self) -> float:
        """Map existing risk tolerance onto a reusable response weight."""
        return max(0.5, min(1.5, 0.7 + 0.8 * self.risk_tolerance))

    def _conservatism(self) -> float:
        """Inverse of aggressiveness so cautious firms protect cash sooner."""
        return max(0.5, min(1.5, 1.5 - 0.8 * self.risk_tolerance))

    def _expansion_runway_gate_ticks(self) -> float:
        """Runway threshold below which firms stop expanding."""
        return max(4.0, min(8.0, 8.0 - 4.0 * self.risk_tolerance))

    def _vacancy_patience_ticks(self) -> int:
        """How long a firm tolerates failed hiring before raising wage pressure."""
        return max(2, min(5, int(round(4.5 - 2.5 * self.risk_tolerance))))

    def _wage_cap_multiplier(self) -> float:
        """Firm-specific cap multiplier to avoid synchronized wage ceilings."""
        return max(1.05, min(1.35, 1.10 + 0.25 * self.risk_tolerance))

    def _stockout_sales_floor_multiplier(self, inventory_weeks: float) -> float:
        """How aggressively a healthy stockout should lift demand expectations."""
        inventory_gap = max(0.0, float(self.target_inventory_weeks) - float(inventory_weeks))
        base = 1.2 + 0.2 * self._aggressiveness()
        return max(1.5, min(2.5, base + 0.25 * inventory_gap))

    def _stockout_hire_growth_rate(self, unfilled_positions_streak: int) -> float:
        """Allow healthy stockout firms to scale faster than the generic 25% cap."""
        base = 1.50 + 0.50 * self._aggressiveness()
        streak_bonus = 0.40 * max(0, int(unfilled_positions_streak))
        return max(1.5, min(4.0, base + streak_bonus))

    def refresh_health_snapshot(
        self,
        sell_through_rate: float = 0.5,
        category_wage_anchor_p75: float = 0.0,
    ) -> FirmHealthSnapshot:
        """Compute and persist the shared firm-health view once for the tick."""
        alpha = self._profit_ema_alpha()
        if self.revenue_ema <= 0.0 and self.profit_ema == 0.0 and self.age_in_ticks <= 1:
            self.revenue_ema = max(0.0, float(self.last_revenue))
            self.profit_ema = float(self.last_profit)
        else:
            self.revenue_ema = (1.0 - alpha) * self.revenue_ema + alpha * max(0.0, float(self.last_revenue))
            self.profit_ema = (1.0 - alpha) * self.profit_ema + alpha * float(self.last_profit)

        if self.revenue_ema > 1e-6:
            self.smoothed_profit_margin = self.profit_ema / self.revenue_ema
        else:
            self.smoothed_profit_margin = -1.0 if self.profit_ema < 0.0 else 0.0

        wage_bill = self._current_wage_bill()
        if wage_bill > 0.0 and self.employees:
            self.cash_runway_ticks = float(self.cash_balance) / max(wage_bill, 1.0)
        else:
            self.cash_runway_ticks = float("inf")

        self.last_sell_through_rate = max(0.0, min(1.5, float(sell_through_rate)))
        self.inventory_weeks = max(0.0, float(self.inventory_units)) / max(1.0, float(self.expected_sales_units))

        hires_shortfall = max(0, int(self.last_tick_planned_hires) - int(self.last_tick_actual_hires))
        if hires_shortfall > 0:
            self.unfilled_positions_streak += 1
        elif self.last_tick_planned_hires > 0 and self.last_tick_actual_hires >= self.last_tick_planned_hires:
            self.unfilled_positions_streak = 0
        else:
            self.unfilled_positions_streak = max(0, self.unfilled_positions_streak - 1)

        return FirmHealthSnapshot(
            cash_runway_ticks=float(self.cash_runway_ticks),
            smoothed_profit_margin=float(self.smoothed_profit_margin),
            sell_through_rate=float(self.last_sell_through_rate),
            inventory_weeks=float(self.inventory_weeks),
            unfilled_positions_streak=int(self.unfilled_positions_streak),
            worker_turnover_this_tick=int(self.worker_turnover_this_tick),
            survival_mode=bool(self.survival_mode),
            burn_mode=bool(self.burn_mode),
            category_wage_anchor_p75=max(0.0, float(category_wage_anchor_p75)),
        )

    def _profit_optimal_workers(
        self,
        current_workers: int,
        expected_sales: float,
        effective_wage_cost: float
    ) -> int:
        """
        Feature 2: Proportional MRPL search for profit-maximizing staffing.

        Instead of a fixed ±2 worker neighborhood, evaluate staffing levels at
        ±5% and ±10% of current workforce (plus the demand-implied target).
        This scales proportionally with firm size.
        """
        config = self._firm_config()
        candidate_workers = set()

        # Proportional search: ±5% and ±10% of current workforce
        for fraction in config.mrpl_search_fractions:
            delta = max(1, int(current_workers * fraction))
            candidate_workers.add(max(config.min_target_workers, current_workers - delta))
            candidate_workers.add(max(config.min_target_workers, current_workers + delta))

        # Always include current level and demand-implied target
        candidate_workers.add(max(config.min_target_workers, current_workers))
        candidate_workers.add(self._workers_for_sales(expected_sales))

        best_workers = max(config.min_target_workers, current_workers)
        best_profit = -float("inf")
        fixed_cost = getattr(self, "fixed_cost", 0.0)
        for workers in sorted(candidate_workers):
            capacity = self._capacity_for_workers(workers)
            expected_output = min(capacity, expected_sales)
            expected_revenue = expected_output * max(self.price, 0.0)
            expected_wage_bill = workers * effective_wage_cost
            expected_profit = expected_revenue - expected_wage_bill - fixed_cost
            if expected_profit > best_profit:
                best_profit = expected_profit
                best_workers = workers
        return best_workers

    def _destabilized_production_plan(self) -> Dict[str, object]:
        """Simplified aggressive plan when stabilizers are disabled."""
        config = self._firm_config()
        current_workers = len(self.employees)
        target_output = max(self.production_capacity_units, self.expected_sales_units)
        target_workers = self._workers_for_sales(target_output)
        hire_limit = max(1, int(math.ceil(max(current_workers, 1) * 0.10)))
        if not self.is_baseline and current_workers == 0:
            target_workers = min(target_workers, 2)
            hire_limit = min(hire_limit, 2)
        planned_hires = min(max(0, target_workers - current_workers), hire_limit)
        planned_production_units = min(
            self._capacity_for_workers(max(current_workers + planned_hires, config.min_target_workers)),
            self.production_capacity_units
        )
        return {
            "firm_id": self.firm_id,
            "planned_production_units": planned_production_units,
            "planned_hires_count": planned_hires,
            "planned_layoffs_ids": [],
            "updated_expected_sales": self.expected_sales_units,
        }

    def _plan_healthcare_service_labor(
        self,
        in_warmup: bool = False,
        total_households: int = 0,
    ) -> Dict[str, object]:
        """
        Backlog-driven staffing plan for healthcare service firms.

        No goods are produced; workers convert directly into visit capacity.
        """
        firm_config = self._firm_config()
        current_workers = len(self.employees)
        backlog = len(self.healthcare_queue)
        capacity_per_worker = max(0.1, self.healthcare_capacity_per_worker)
        horizon = max(1.0, self.healthcare_backlog_horizon_ticks)
        arrivals = max(0.0, self.healthcare_arrivals_ema)

        desired_capacity = arrivals + (backlog / horizon)

        if backlog <= 0 and arrivals < 0.1:
            self.healthcare_idle_streak += 1
        else:
            self.healthcare_idle_streak = 0

        if self.healthcare_idle_streak >= firm_config.healthcare_downsize_idle_ticks:
            desired_capacity *= 0.5

        desired_workers = math.ceil(desired_capacity / capacity_per_worker) if desired_capacity > 0 else 0
        desired_workers = max(firm_config.min_target_workers, desired_workers)
        if total_households > 0:
            population_cap_workers = max(
                1,
                int(math.ceil(total_households * firm_config.healthcare_staff_population_ratio)),
            )
            desired_workers = min(desired_workers, population_cap_workers)
        if self.is_baseline:
            desired_workers = max(desired_workers, firm_config.healthcare_baseline_min_workers)
        if in_warmup and self.is_baseline:
            desired_workers = max(desired_workers, firm_config.healthcare_baseline_min_workers + 2)

        backlog_hire_signal = int(
            math.ceil(
                backlog / max(1.0, horizon * capacity_per_worker)
            )
        ) if backlog > 0 else 0
        hire_limit = max(
            3,
            min(
                firm_config.healthcare_max_hires_per_tick,
                max(int(max(current_workers, 1) * 0.20), backlog_hire_signal)
            )
        )
        layoff_limit = max(1, int(max(current_workers, 1) * 0.05))
        planned_hires = 0
        planned_layoffs: List[int] = []
        delta = desired_workers - current_workers
        if delta > 0:
            planned_hires = min(delta, hire_limit)
        elif delta < 0:
            layoff_count = min(-delta, layoff_limit)
            if layoff_count > 0:
                planned_layoffs = self.employees[:layoff_count]

        self.planned_hires_count = planned_hires
        self.planned_layoffs_ids = planned_layoffs
        self.last_tick_planned_hires = planned_hires
        self.expected_sales_units = max(firm_config.min_expected_sales, desired_capacity)

        return {
            "firm_id": self.firm_id,
            "planned_production_units": 0.0,
            "planned_hires_count": planned_hires,
            "planned_layoffs_ids": planned_layoffs,
            "updated_expected_sales": self.expected_sales_units,
        }

    def plan_production_and_labor(
        self,
        last_tick_sales_units: float,
        in_warmup: bool = False,
        total_households: int = 0,
        global_unsold_inventory: float = 0.0,
        private_housing_inventory: float = 0.0,
        large_market: bool = False,
        post_warmup_cooldown: bool = False,
        health_snapshot: Optional[FirmHealthSnapshot] = None,
    ) -> Dict[str, object]:
        """
        Decide how much to produce and how many workers are needed.

        NEW ECONOMIC LOGIC:
        1. Goal: Sell EVERYTHING (current production + existing inventory)
        2. Hiring decision: Will additional workers generate more revenue than cost?
        3. Pricing: Lower price aggressively to clear inventory
        4. Wage cuts: Only as last resort when revenue can't cover payroll

        FIRM THINKING:
        - "If I hire X more workers, they produce Y more units"
        - "If I sell all Y units at price P, I get revenue R"
        - "Does R > (wage × X)? If yes, hire them!"
        - "I want to sell ALL inventory, not just new production"

        Does not mutate state; returns a plan dict.

        Args:
            last_tick_sales_units: Actual units sold in the previous tick

        Returns:
            Dict with firm_id, planned_production_units, planned_hires_count, planned_layoffs_ids
        """
        firm_config = self._firm_config()
        if health_snapshot is None:
            health_snapshot = self.refresh_health_snapshot(
                sell_through_rate=self.last_sell_through_rate,
                category_wage_anchor_p75=self.wage_offer,
            )
        self.age_in_ticks += 1
        self.last_units_sold = last_tick_sales_units

        smoothed_sales = (
            self.sales_expectation_alpha * last_tick_sales_units +
            (1.0 - self.sales_expectation_alpha) * self.expected_sales_units
        )
        self.expected_sales_units = max(firm_config.min_expected_sales, smoothed_sales)

        if (
            last_tick_sales_units < firm_config.min_expected_sales
            and self.inventory_units < firm_config.inventory_exit_epsilon
        ):
            self.expected_sales_units = max(
                firm_config.min_expected_sales,
                self.expected_sales_units * 0.9
            )

        is_housing_producer = self.good_category.lower() == "housing"
        if is_housing_producer:
            self.expected_sales_units = max(
                firm_config.min_expected_sales,
                float(max(1, self.max_rental_units))
            )
            # Housing firms retain a skeleton crew for property management
            # rather than firing everyone each tick (which causes wasteful churn).
            min_staff = max(firm_config.min_skeleton_workers, firm_config.min_target_workers)
            current_workers = len(self.employees) if self.employees else 0
            planned_layoffs = []
            if current_workers > min_staff:
                excess = current_workers - min_staff
                planned_layoffs = list(self.employees[:excess])
            return {
                "firm_id": self.firm_id,
                "planned_production_units": 0.0,
                "planned_hires_count": max(0, min_staff - current_workers),
                "planned_layoffs_ids": planned_layoffs,
                "updated_expected_sales": self.expected_sales_units,
            }

        if self.good_category.lower() == "healthcare":
            return self._plan_healthcare_service_labor(
                in_warmup=in_warmup,
                total_households=total_households,
            )

        if self.stabilization_disabled:
            return self._destabilized_production_plan()

        housing_market_saturated = False
        if total_households > 0:
            if private_housing_inventory > total_households * firm_config.housing_private_saturation_multiplier:
                firm_high_inventory = self.inventory_units > 2.0 * max(1.0, self.expected_sales_units)
                if firm_high_inventory:
                    housing_market_saturated = True

        expected_baseline = max(firm_config.min_expected_sales, self.expected_sales_units)
        demand_workers = max(
            firm_config.min_target_workers,
            self._workers_for_sales(min(expected_baseline, self.production_capacity_units))
        )

        if large_market:
            high_inventory_factor = firm_config.high_inventory_factor_large * firm_config.large_market_inventory_relief
            trigger_streak_threshold = (
                firm_config.burn_mode_trigger_streak_large +
                firm_config.large_market_burn_mode_buffer
            )
        else:
            high_inventory_factor = firm_config.high_inventory_factor_small
            trigger_streak_threshold = firm_config.burn_mode_trigger_streak_small

        high_inventory = self.inventory_units > high_inventory_factor * expected_baseline
        low_sellthrough = health_snapshot.sell_through_rate < 0.5

        if high_inventory and low_sellthrough:
            self.high_inventory_streak += 1
            self.low_inventory_streak = 0
        else:
            relief = max(1, firm_config.burn_mode_relief_rate)
            self.high_inventory_streak = max(0, self.high_inventory_streak - relief)
            if self.last_units_sold >= 0.8 * expected_baseline:
                self.low_inventory_streak += 1
            else:
                self.low_inventory_streak = max(0, self.low_inventory_streak - relief)

        if (
            not self.burn_mode
            and self.age_in_ticks >= firm_config.burn_mode_grace_period
            and self.high_inventory_streak >= trigger_streak_threshold
        ):
            self.burn_mode = True

        if self.burn_mode and (
            self.low_inventory_streak >= firm_config.burn_mode_exit_streak
            or self.inventory_units < firm_config.inventory_exit_epsilon
        ):
            self.burn_mode = False
            self.high_inventory_streak = 0
            self.low_inventory_streak = 0

        current_workers = len(self.employees)
        planned_hires = 0
        planned_layoffs: List[int] = []
        expected_skill_premium = self._expected_skill_premium()
        effective_wage_cost = self.wage_offer * (1.0 + expected_skill_premium)

        # Feature 1: Emergency Restructuring (Anti-Zombie Firm)
        # Calculate operating run rate and check survival condition
        wage_bill = self._current_wage_bill()
        operating_run_rate = wage_bill  # Per-tick operating cost (labor-only production)
        runway_weeks = firm_config.survival_mode_runway_weeks
        rolling_revenue = max(self.revenue_ema, max(self.last_revenue, 0.0))

        if current_workers > 0 and health_snapshot.cash_runway_ticks < runway_weeks:
            self.survival_mode = True
        elif health_snapshot.cash_runway_ticks >= runway_weeks * 2.0:
            # Exit survival mode once cash reserves are healthy again
            self.survival_mode = False

        if self.survival_mode and not self.is_baseline and current_workers > 0:
            # Bypass normal firing caps. Lay off enough workers to bring
            # operating costs below current rolling revenue.
            if rolling_revenue <= 0:
                # No revenue: lay off down to skeleton crew
                target_workers = max(firm_config.min_skeleton_workers, 1)
            else:
                # Find workforce that brings wage bill below revenue
                avg_wage = wage_bill / current_workers if current_workers > 0 else self.wage_offer
                target_workers = max(
                    firm_config.min_skeleton_workers,
                    int(rolling_revenue / max(avg_wage, 1.0))
                )
            target_workers = min(target_workers, current_workers)
            layoff_count = current_workers - target_workers
            if layoff_count > 0:
                planned_layoffs = self.employees[:layoff_count]
            # Minimal production during survival mode
            planned_production_units = min(
                self._capacity_for_workers(target_workers),
                self.production_capacity_units * 0.1
            )
            self.planned_hires_count = 0
            self.planned_layoffs_ids = planned_layoffs
            self.last_tick_planned_hires = 0
            return {
                "firm_id": self.firm_id,
                "planned_production_units": planned_production_units,
                "planned_hires_count": 0,
                "planned_layoffs_ids": planned_layoffs,
                "updated_expected_sales": self.expected_sales_units,
            }

        healthy_stockout_expansion = (
            current_workers > 0
            and not self.is_baseline
            and self.good_category.lower() != "healthcare"
            and not in_warmup
            and not self.burn_mode
            and not self.survival_mode
            and self.loan_required_headcount <= 0
            and health_snapshot.sell_through_rate >= 0.98
            and health_snapshot.inventory_weeks <= max(0.1, self.target_inventory_weeks * 0.15)
            and health_snapshot.smoothed_profit_margin >= 0.0
            and health_snapshot.cash_runway_ticks >= max(
                self._expansion_runway_gate_ticks(),
                firm_config.survival_mode_runway_weeks * 2.0,
            )
        )
        if healthy_stockout_expansion:
            inventory_gap = max(1.0, float(self.target_inventory_weeks) - float(health_snapshot.inventory_weeks))
            buffer_build_multiplier = 1.0 + min(1.5, 0.30 * inventory_gap)
            stockout_sales_floor = min(
                self.production_capacity_units,
                max(
                    float(self.expected_sales_units) * buffer_build_multiplier,
                    float(last_tick_sales_units) * self._stockout_sales_floor_multiplier(
                        health_snapshot.inventory_weeks
                    ),
                ),
            )
            self.expected_sales_units = max(self.expected_sales_units, stockout_sales_floor)
            expected_baseline = max(firm_config.min_expected_sales, self.expected_sales_units)
            demand_workers = max(
                firm_config.min_target_workers,
                self._workers_for_sales(min(expected_baseline, self.production_capacity_units))
            )

        minimum_private_staff = firm_config.min_target_workers
        if self.is_baseline:
            skeleton_min = max(firm_config.min_skeleton_workers, firm_config.min_target_workers)
        else:
            skeleton_min = (
                0
                if current_workers == 0
                else max(
                    firm_config.min_target_workers,
                    min(current_workers, firm_config.min_skeleton_workers)
                )
            )
        if self.loan_required_headcount > 0:
            minimum_private_staff = max(minimum_private_staff, self.loan_required_headcount)
            skeleton_min = max(skeleton_min, min(self.loan_required_headcount, minimum_private_staff))

        # Hire/fire limits per tick.
        # max_hires_per_tick and max_fires_per_tick are personality traits set in __post_init__
        # (aggressive: 2-4, moderate: 1-3, conservative: 1-2) but were previously ignored.
        # Now they act as a floor so personality matters, with 25/20% growth as the scaling arm.
        if self.is_baseline:
            hire_limit = max(5, int(math.ceil(current_workers * 0.25)))
            fire_limit = max(5, int(math.ceil(current_workers * 0.20)))
        elif current_workers <= 0:
            hire_limit = 2
            fire_limit = 0
        else:
            hire_limit = max(self.max_hires_per_tick, int(math.ceil(current_workers * 0.25)))
            fire_limit = max(self.max_fires_per_tick, int(math.ceil(current_workers * 0.20)))
        if healthy_stockout_expansion and current_workers > 0:
            hire_limit = max(
                hire_limit,
                int(math.ceil(current_workers * self._stockout_hire_growth_rate(
                    health_snapshot.unfilled_positions_streak
                )))
            )
        self.burn_mode_active = self.burn_mode

        target_workers = max(current_workers, firm_config.min_target_workers)
        planned_production_units = 0.0

        bootstrap_target = max(
            firm_config.min_target_workers,
            min(demand_workers, 2),
        )
        bootstrap_cash_needed = effective_wage_cost * bootstrap_target * max(
            1.0, firm_config.survival_mode_runway_weeks
        )
        needs_bootstrap = (
            (not self.is_baseline)
            and current_workers == 0
            and not self.burn_mode
            and self.cash_balance >= bootstrap_cash_needed
            and self.expected_sales_units >= firm_config.min_expected_sales
        )
        if needs_bootstrap:
            target_workers = bootstrap_target
            planned_hires = min(target_workers - current_workers, hire_limit)
            planned_production_units = min(
                self._capacity_for_workers(target_workers),
                self.production_capacity_units
            )
        elif self.burn_mode:
            reduction_factor = firm_config.burn_mode_staff_reduction_factor
            reduced_workers = int(math.ceil(max(1, current_workers) * reduction_factor))
            target_workers = max(skeleton_min, reduced_workers)
            idle_fraction = max(0.0, firm_config.burn_mode_idle_production_fraction)
            if idle_fraction > 0:
                planned_production_units = min(
                    self._capacity_for_workers(target_workers),
                    self.production_capacity_units * idle_fraction
                )
            else:
                planned_production_units = 0.0
        elif housing_market_saturated:
            planned_production_units = 0.0
            target_workers = max(skeleton_min, int(current_workers * 0.5))
        elif self.is_baseline:
            if in_warmup:
                # Food and Services are the only baseline firms that hire
                # during warmup (Housing is rental-only, Healthcare is
                # demand-driven).  Each requests half the labor force so
                # labor matching distributes workers evenly between them.
                estimated_pop = max(100, int(self.baseline_production_quota / 3.0))
                planned_hires = max(int(estimated_pop * 0.50), 50)
                # Cap to half so the first firm in matching order doesn't
                # grab everyone, leaving nothing for the second firm.
                planned_hires = min(planned_hires, int(estimated_pop * 0.50))
                revenue_per_worker = self.price * self.productivity_per_worker
                self.wage_offer = min(revenue_per_worker * 0.95, 40.0)
                planned_production_units = min(
                    self.production_capacity_units,
                    max(self.baseline_production_quota, self.production_capacity_units)
                )
            else:
                support_ratio = 1.0 if post_warmup_cooldown else 0.8
                support_output = self.baseline_production_quota * support_ratio
                target_output = min(
                    self.production_capacity_units,
                    max(support_output, expected_baseline * 0.8)
                )
                target_workers = self._workers_for_sales(target_output)

                delta = target_workers - current_workers
                if delta > 0:
                    planned_hires = min(delta, hire_limit)
                elif delta < 0:
                    layoff_count = min(-delta, fire_limit)
                    if layoff_count > 0:
                        planned_layoffs = self.employees[:layoff_count]

                planned_production_units = min(
                    self._capacity_for_workers(max(target_workers, firm_config.min_target_workers)),
                    target_output
                )
        else:
            additional_output = (
                    self._capacity_for_workers(current_workers + 1) -
                    self._capacity_for_workers(current_workers)
                )
            delta_profit = additional_output * self.price - effective_wage_cost
            demand_target = self._workers_for_sales(min(expected_baseline, self.production_capacity_units))
            profit_target = self._profit_optimal_workers(
                max(current_workers, firm_config.min_target_workers),
                expected_baseline,
                effective_wage_cost
            )
            wage_cost_per_worker = (
                wage_bill / current_workers
                if current_workers > 0 and wage_bill > 0.0
                else effective_wage_cost
            )
            demand_is_tight = health_snapshot.inventory_weeks <= max(0.5, self.target_inventory_weeks * 0.5)
            backlog_signal = (
                health_snapshot.sell_through_rate >= 0.95
                and health_snapshot.inventory_weeks <= max(0.25, self.target_inventory_weeks * 0.5)
            )
            demand_supports_hiring = (
                health_snapshot.sell_through_rate >= 0.65  # was 0.85 — too strict, blocked hiring at moderate inventory
                or demand_is_tight
                or backlog_signal
            )
            # expansion_blocked: only freeze headcount when truly cash-critical (near survival mode),
            # not at the wider 4-8 tick expansion gate. The old gate was firing before firms were
            # in real danger, preventing growth-to-profitability even when cash was adequate.
            expansion_blocked = (
                current_workers > 0
                and (not self.is_baseline)
                and self.good_category.lower() != "healthcare"
                and (not in_warmup)
                and health_snapshot.smoothed_profit_margin < 0.0
                and health_snapshot.cash_runway_ticks < firm_config.survival_mode_runway_weeks
            )

            if current_workers == 0:
                if delta_profit > 0 and demand_supports_hiring:
                    target_workers = min(demand_target, bootstrap_target)
                else:
                    target_workers = 0
            else:
                financially_stressed = (
                    health_snapshot.smoothed_profit_margin < 0.0
                    or health_snapshot.cash_runway_ticks < (firm_config.survival_mode_runway_weeks * 2.0)
                )
                if financially_stressed:
                    supported_workers = skeleton_min
                    if rolling_revenue > 0.0:
                        supported_workers = max(
                            skeleton_min,
                            int(rolling_revenue / max(wage_cost_per_worker, 1.0))
                        )
                    target_workers = min(
                        current_workers,
                        max(skeleton_min, min(profit_target, supported_workers))
                    )
                elif healthy_stockout_expansion and delta_profit > 0 and demand_supports_hiring:
                    target_workers = max(
                        minimum_private_staff,
                        demand_target,
                    )
                elif delta_profit > 0 and demand_supports_hiring:
                    target_workers = max(
                        minimum_private_staff,
                        min(demand_target, profit_target)
                    )
                else:
                    target_workers = min(
                        current_workers,
                        max(minimum_private_staff, profit_target)
                    )

                if expansion_blocked:
                    target_workers = min(target_workers, current_workers)

            planned_production_units = min(
                self._capacity_for_workers(max(current_workers, target_workers)),
                self.production_capacity_units
            )

        if self.is_baseline:
            target_workers = max(target_workers, demand_workers)

        # Feature 3, Stage 1: Volume Cut — reduce labor to slow production when
        # inventory exceeds the moderate threshold, BEFORE resorting to price cuts.
        if not self.burn_mode and not self.is_baseline:
            # Inventory feedback loop: scale production based on excess inventory
            expected_sales = max(1.0, self.expected_sales_units)
            target_inventory = expected_sales * 2.0  # Maintain 2x expected sales as buffer
            inventory_overhang = max(0.0, self.inventory_units - target_inventory)
            correction_speed = 0.5  # Clear 50% of excess per tick
            adjusted_production = max(0.0, expected_sales - (inventory_overhang * correction_speed))
            target_production = max(1.0, adjusted_production)
            if self.inventory_units > firm_config.inventory_stage1_threshold * target_production:
                labor_cut = firm_config.inventory_stage1_labor_cut
                target_workers = max(
                    skeleton_min if current_workers > 0 else 0,
                    int(target_workers * (1.0 - labor_cut))
                )

        if self.loan_required_headcount > 0:
            target_workers = max(target_workers, self.loan_required_headcount)

        if not (self.is_baseline and in_warmup):
            delta = target_workers - current_workers
            if delta > 0:
                planned_hires = min(delta, hire_limit)
            elif delta < 0:
                layoff_count = min(-delta, fire_limit)
                if layoff_count > 0:
                    planned_layoffs = self.employees[:layoff_count]

        self.planned_hires_count = planned_hires
        self.planned_layoffs_ids = planned_layoffs
        self.last_tick_planned_hires = planned_hires

        return {
            "firm_id": self.firm_id,
            "planned_production_units": planned_production_units,
            "planned_hires_count": planned_hires,
            "planned_layoffs_ids": planned_layoffs,
            "updated_expected_sales": self.expected_sales_units,  # include for later apply
        }

    def plan_capital_investment(self, bank: Optional["BankAgent"] = None) -> None:
        """Decide whether to invest in capital this tick.

        Sets capital_stock and cash_balance for self-financed cases, or sets
        needs_investment_loan/investment_loan_amount flags for Phase 1.5
        loan processing. Resets capital_investment_this_tick to 0 first.
        """
        config = self._firm_config()
        self.capital_investment_this_tick = 0.0
        self.needs_investment_loan = False
        self.investment_loan_amount = 0.0

        # Only invest from a position of strength
        if self.survival_mode or self.burn_mode:
            return
        if self.smoothed_profit_margin < 0.10:
            return

        N = max(len(self.employees), 1)
        K = max(self.capital_stock, 0.01)
        units = max(self.units_per_worker, config.min_base_productivity)

        # MPK = TFP * alpha_k * K^(alpha_k-1) * N^alpha_n
        mpk = units * config.alpha_k * (K ** (config.alpha_k - 1.0)) * (N ** config.alpha_n)
        vmpk = mpk * self.price  # value of marginal product of capital

        # Weekly cost of capital: depreciation rate + annualised lending rate / 52
        lending_rate = self.current_loan_rate
        if bank is not None:
            lending_rate = bank.base_interest_rate
        cost_of_capital_weekly = (
            config.capital_depreciation_rate + lending_rate / 52.0
        ) * config.capital_cost_per_unit

        if vmpk <= cost_of_capital_weekly:
            return

        # Invest 1 unit at a time (conservative)
        investment_cost = config.capital_cost_per_unit
        weekly_wage_bill = self._current_wage_bill()

        if self.cash_balance > investment_cost + weekly_wage_bill * 8:
            # Self-finance: pay immediately
            self.capital_stock += 1.0
            self.cash_balance -= investment_cost
            self.capital_investment_this_tick = 1.0
        else:
            # Request investment loan — processed in Phase 1.5
            self.needs_investment_loan = True
            self.investment_loan_amount = investment_cost

    def plan_pricing(
        self,
        sell_through_rate: float,
        unemployment_rate: float,
        in_warmup: bool = False,
        health_snapshot: Optional[FirmHealthSnapshot] = None,
    ) -> Dict[str, float]:
        """
        AGGRESSIVE INVENTORY CLEARANCE PRICING

        NEW PHILOSOPHY:
        1. Goal: Sell ALL inventory, not maintain margins
        2. If inventory isn't selling → lower price aggressively
        3. Keep lowering until everything sells (even down to $0.01)
        4. Only constraint: Must still afford to pay workers
        5. Price floor: wage_bill / total_production (break-even on labor)

        FIRM THINKING:
        - "I have 1000 units sitting unsold"
        - "Lower price 10% → if still unsold → lower 10% more"
        - "Keep going until it all sells"
        - "Better to sell at low margin than not sell at all"
        """
        firm_config = self._firm_config()
        if health_snapshot is None:
            health_snapshot = self.refresh_health_snapshot(
                sell_through_rate=sell_through_rate,
                category_wage_anchor_p75=self.wage_offer,
            )
        if self.is_baseline and in_warmup:
            labor_cost_per_unit = self.wage_offer / max(self.productivity_per_worker, 1.0)
            target_price = labor_cost_per_unit * 1.05
            return {
                "price_next": target_price,
                "markup_next": (target_price / self.unit_cost - 1.0) if self.unit_cost > 0 else self.markup,
            }

        if self.stabilization_disabled:
            price_next = max(self.min_price, self.price)
            if not self.is_baseline:
                price_next = max(self.min_price * 0.5, price_next * 1.02)
            markup_next = (price_next / self.unit_cost - 1.0) if self.unit_cost > 0 else self.markup
            return {"price_next": price_next, "markup_next": markup_next}

        if self.good_category.lower() == "healthcare":
            base_price = CONFIG.baseline_prices.get("Healthcare", max(self.min_price, self.price))
            price_floor = max(self.min_price, base_price * 0.6)
            price_ceiling = max(price_floor, base_price * firm_config.healthcare_price_ceiling_multiplier)

            capacity = max(1.0, len(self.employees) * max(self.healthcare_capacity_per_worker, 0.1))
            horizon = max(1.0, self.healthcare_backlog_horizon_ticks)
            queue_pressure = len(self.healthcare_queue) / capacity
            projected_pressure = (
                self.healthcare_arrivals_ema + len(self.healthcare_queue) / horizon
            ) / capacity
            pressure = max(queue_pressure, projected_pressure)

            target_pressure = max(0.2, firm_config.healthcare_price_pressure_target)
            if pressure > target_pressure:
                excess = min(2.5, pressure - target_pressure)
                price_change = 1.0 + min(0.12, firm_config.healthcare_price_increase_rate * excess)
            elif pressure < 0.3 * target_pressure:
                slack = (0.3 * target_pressure - pressure) / max(0.3 * target_pressure, 1e-6)
                price_change = 1.0 - min(0.08, firm_config.healthcare_price_decrease_rate * slack)
            else:
                price_change = 1.0

            price_next = min(price_ceiling, max(price_floor, self.price * price_change))
            markup_next = (price_next / self.unit_cost - 1.0) if self.unit_cost > 0 else self.markup
            return {"price_next": price_next, "markup_next": markup_next}

        if not self.is_baseline:
            price_next = self.price
            target_weeks = max(0.5, self.target_inventory_weeks)
            inventory_weeks = health_snapshot.inventory_weeks

            if inventory_weeks >= target_weeks * 1.5:
                excess_ratio = inventory_weeks / max(target_weeks, 1e-6)
                severity = min(max(0.0, excess_ratio - 1.0), 2.0)
                price_next = max(self.min_price, self.price * (1.0 - self.price_adjustment_rate * severity))
            elif sell_through_rate >= 0.95 and inventory_weeks < target_weeks * 0.5:
                price_next = max(self.min_price, self.price * (1.0 + self.price_adjustment_rate * 0.5))
            elif self.last_units_produced > 0 and self.last_units_sold < self.last_units_produced:
                price_next = max(self.min_price, self.price * (1.0 - min(0.5, self.price_adjustment_rate)))

            # Cost floor: price must cover unit labor cost + unit depreciation cost
            # Only apply when there's meaningful production to avoid infinite per-unit depreciation
            if self.last_units_produced > 1.0:
                config = self._firm_config()
                unit_depreciation = (
                    self.capital_stock * config.capital_depreciation_rate * config.capital_cost_per_unit
                ) / self.last_units_produced
                cost_floor = (self.unit_cost + unit_depreciation) * 1.05
                price_next = max(price_next, cost_floor)

            markup_next = (price_next / self.unit_cost) - 1.0 if self.unit_cost > 0 else self.markup
            return {
                "price_next": price_next,
                "markup_next": markup_next,
            }

        capacity = self._capacity_for_workers(max(len(self.employees), 1))
        sold_ratio = (self.last_units_sold / capacity) if capacity > 0 else 0.0
        inv_ratio = self.inventory_units / max(1.0, self.expected_sales_units)
        up_factor = max(0.2, 1.0 - unemployment_rate)
        down_factor = 1.0 + unemployment_rate
        price_change = 1.0

        if sold_ratio < 0.3:
            price_change *= (1.0 - 0.03 * down_factor)
        elif sold_ratio > 0.8 and inv_ratio < 0.5:
            price_change *= (1.0 + 0.02 * up_factor)

        price_change = max(0.5, min(1.1, price_change))
        price_next = max(self.min_price, self.price * price_change)

        # Calculate markup
        if self.unit_cost > 0:
            markup_next = (price_next / self.unit_cost) - 1.0
        else:
            markup_next = self.markup

        return {
            "price_next": price_next,
            "markup_next": markup_next,
        }

    def plan_wage(
        self,
        unemployment_rate: float = 0.0,
        unemployment_benefit: float = 0.0,
        in_warmup: bool = False,
        health_snapshot: Optional[FirmHealthSnapshot] = None,
    ) -> Dict[str, float]:
        """Determine the wage offer for the next tick.

        Wage-setting follows a revenue-share model: the firm targets a
        ``target_labor_share`` of realised revenue-per-worker, dampened by
        the current unemployment rate (higher unemployment → less upward
        wage pressure).  The final offer is clamped between ±15 % of the
        current wage and bounded by ``[min_labor_share, max_labor_share]``
        of revenue so the firm never pays more than it earns.

        Special cases:
        - **Baseline (government) firms** cap wages at 150 % of the
          minimum-wage floor — they model stable public-sector employment.
        - **Healthcare firms** respond to queue backlog pressure: wages
          rise faster when patient demand exceeds staff capacity.
        - **Zero-revenue or negative-margin firms** trend wages downward
          toward the fundamental level without sudden drops.

        Args:
            unemployment_rate: Economy-wide unemployment fraction (0-1).
            unemployment_benefit: Current government benefit level, used to
                set the wage floor at 1.5× benefits so employment always
                dominates unemployment income.

        Returns:
            Dict with ``wage_offer_next`` — the wage the firm will post.
        """
        firm_config = self._firm_config()
        if health_snapshot is None:
            health_snapshot = self.refresh_health_snapshot(
                sell_through_rate=self.last_sell_through_rate,
                category_wage_anchor_p75=self.wage_offer,
            )
        if self.is_baseline and self.last_tick_planned_hires >= 1_000_000:
            return {"wage_offer_next": self.wage_offer}

        # Baseline (government) firms pay at most 250% of minimum wage floor (increased from 150%).
        # They act like public-sector jobs: competitive pay to attract workers and resolve gridlock.
        # The cap must exceed the highest household living-cost floor
        # (0.3*housing + max_food*food ≈ $28) so warmup hiring can clear.
        # With deflationary minimum wage ($15), baseline cap is now: $15 × 2.5 = $37.50
        # This allows baseline firms to offer $35-37 wages, beating the $25 typical entry level
        if self.is_baseline:
            baseline_cap = firm_config.minimum_wage_floor * 2.50
            capped = max(firm_config.minimum_wage_floor, min(self.wage_offer, baseline_cap))
            return {"wage_offer_next": capped}

        if self.stabilization_disabled:
            return {"wage_offer_next": self.wage_offer}

        if self.good_category.lower() != "healthcare" and not self.is_baseline and not in_warmup:
            floor_wage = max(firm_config.minimum_wage_floor, unemployment_benefit * 1.5)
            aggressiveness = self._aggressiveness()
            conservatism = self._conservatism()
            pressure = 0.0

            if health_snapshot.unfilled_positions_streak > self._vacancy_patience_ticks():
                pressure += 0.3 * aggressiveness
            if health_snapshot.worker_turnover_this_tick > 0:
                pressure += 0.2 * aggressiveness
            if health_snapshot.smoothed_profit_margin < 0.0:
                pressure -= 0.4 * conservatism
            if health_snapshot.cash_runway_ticks < self._expansion_runway_gate_ticks():
                pressure -= 0.3 * conservatism
            if (
                health_snapshot.sell_through_rate > 0.95
                and health_snapshot.inventory_weeks < max(0.5, self.target_inventory_weeks * 0.5)
            ):
                pressure += 0.1
            elif (
                health_snapshot.sell_through_rate < 0.5
                or health_snapshot.inventory_weeks > self.target_inventory_weeks * 1.5
            ):
                pressure -= 0.2

            hires_shortfall = max(0, int(self.last_tick_planned_hires) - int(self.last_tick_actual_hires))
            external_hiring_constraint = (
                health_snapshot.unfilled_positions_streak > self._vacancy_patience_ticks()
                and hires_shortfall > 0
                and self.wage_offer >= max(
                    floor_wage,
                    float(health_snapshot.category_wage_anchor_p75 or self.wage_offer),
                )
            )
            if external_hiring_constraint and pressure > 0.0:
                pressure = 0.0

            pressure = max(-1.0, min(1.0, pressure))
            target_wage = self.wage_offer * (1.0 + pressure * self.wage_adjustment_rate)
            max_increase = self.wage_offer * firm_config.max_wage_increase_per_tick
            max_decrease = self.wage_offer * firm_config.max_wage_decrease_per_tick
            target_wage = max(max_decrease, min(max_increase, target_wage))

            category_anchor = max(floor_wage, health_snapshot.category_wage_anchor_p75 or self.wage_offer)
            hard_max = max(floor_wage, category_anchor * self._wage_cap_multiplier())
            wage_offer_next = max(floor_wage, min(hard_max, target_wage))
            return {"wage_offer_next": wage_offer_next}

        expected_skill_premium = self._expected_skill_premium()
        current_workers = max(len(self.employees), firm_config.min_target_workers)

        if current_workers > 0 and self.last_revenue > 0:
            realized_rev_per_worker = self.last_revenue / current_workers
        else:
            realized_rev_per_worker = self.price * self._productivity_per_worker(max(current_workers, 1))

        margin = 0.0
        if self.last_revenue > 0:
            margin = self.last_profit / max(1.0, self.last_revenue)

        slack_factor = max(0.2, 1.0 - unemployment_rate)
        fundamental_wage = realized_rev_per_worker * firm_config.target_labor_share * slack_factor
        wage_offer_next = self.wage_offer
        raise_damp = max(0.2, 1.0 - 0.8 * unemployment_rate)
        floor_wage = max(firm_config.minimum_wage_floor, unemployment_benefit * 1.5)

        if self.good_category.lower() == "healthcare":
            backlog = len(self.healthcare_queue)
            projected_workers = max(1, len(self.employees) + max(0, self.planned_hires_count))
            capacity_per_worker = max(0.1, self.healthcare_capacity_per_worker)
            projected_capacity = max(1.0, projected_workers * capacity_per_worker)
            horizon = max(1.0, self.healthcare_backlog_horizon_ticks)
            projected_demand = max(0.0, self.healthcare_arrivals_ema + backlog / horizon)
            projected_visits = min(projected_capacity, backlog + self.healthcare_arrivals_ema)
            projected_revenue_per_worker = (
                projected_visits * max(self.price, self.min_price)
            ) / projected_workers

            # Households' labor reservation floor uses a hard survival floor of 25.0.
            # If healthcare demand is present, match/exceed that floor so hiring can clear backlog.
            demand_floor = max(floor_wage, 25.0 if backlog > 0 else floor_wage)
            demand_target = max(demand_floor, projected_revenue_per_worker * firm_config.target_labor_share)

            if backlog > 0 or projected_demand > 0:
                pressure = projected_demand / projected_capacity
                max_raise = self.wage_offer * (1.0 + min(0.15, 0.04 + 0.02 * min(3.0, pressure)))
                wage_offer_next = max(demand_floor, min(demand_target, max_raise))
            else:
                wage_offer_next = max(demand_floor, self.wage_offer * 0.99)

            if realized_rev_per_worker > 0:
                max_wage = firm_config.max_labor_share * realized_rev_per_worker
                wage_offer_next = min(wage_offer_next, max(max_wage, demand_floor))

            return {"wage_offer_next": wage_offer_next}

        if self.last_revenue <= 1e-3:
            wage_target = min(self.wage_offer, max(floor_wage, fundamental_wage))
            wage_offer_next = 0.9 * self.wage_offer + 0.1 * wage_target
        elif margin <= 0.0:
            wage_target = min(self.wage_offer, fundamental_wage)
            wage_offer_next = 0.9 * self.wage_offer + 0.1 * wage_target
        elif margin < firm_config.margin_low:
            wage_offer_next = 0.95 * self.wage_offer + 0.05 * fundamental_wage
        elif margin < firm_config.margin_high:
            wage_target = 0.9 * self.wage_offer + 0.1 * fundamental_wage
            wage_offer_next = self.wage_offer + (wage_target - self.wage_offer) * raise_damp
        else:
            wage_target = 0.8 * self.wage_offer + 0.2 * fundamental_wage
            wage_offer_next = self.wage_offer + (wage_target - self.wage_offer) * raise_damp

        # Turnover pressure: losing workers to competitors is a stronger signal
        # than merely failing to hire. Each worker lost adds an extra nudge upward.
        if self.worker_turnover_this_tick > 0 and not self.is_baseline:
            turnover_boost = min(0.10, 0.03 * self.worker_turnover_this_tick)
            wage_offer_next = max(wage_offer_next, self.wage_offer * (1.0 + turnover_boost))

        max_increase = self.wage_offer * 1.15
        max_decrease = self.wage_offer * 0.85
        wage_offer_next = max(max_decrease, min(max_increase, wage_offer_next))

        wage_offer_next = max(floor_wage, wage_offer_next)

        if realized_rev_per_worker > 0:
            max_wage = firm_config.max_labor_share * realized_rev_per_worker
            wage_offer_next = min(wage_offer_next, max_wage)

            min_wage = firm_config.min_labor_share * realized_rev_per_worker
            if wage_offer_next < min_wage and margin > firm_config.margin_low:
                wage_offer_next = min(max_wage, max(min_wage, wage_offer_next))

        if self.last_revenue <= 1e-3:
            wage_offer_next = min(wage_offer_next, self.wage_offer)

        if self.cash_balance <= 0.0:
            wage_offer_next = max(floor_wage, wage_offer_next * 0.95)

        if not self.is_baseline and len(self.employees) == 0:
            wage_offer_next = min(wage_offer_next, 40.0)

        return {"wage_offer_next": wage_offer_next}

    def apply_labor_outcome(self, outcome: Dict[str, object]) -> None:
        """
        Update workforce based on labor market outcome.

        Mutates state.

        Args:
            outcome: Dict with hired_households_ids and confirmed_layoffs_ids
        """
        hired_households_ids = outcome.get("hired_households_ids", [])
        confirmed_layoffs_ids = outcome.get("confirmed_layoffs_ids", [])

        wage_map = outcome.get("actual_wages", {})

        # Remove laid-off workers
        for worker_id in confirmed_layoffs_ids:
            if worker_id in self.employees:
                self.employees.remove(worker_id)
            if worker_id in self.actual_wages:
                del self.actual_wages[worker_id]

        # Add new hires (avoid duplicates)
        for worker_id in hired_households_ids:
            if worker_id not in self.employees:
                self.employees.append(worker_id)
            self.actual_wages[worker_id] = wage_map.get(worker_id, self.wage_offer)

        # Ensure existing workers' wages meet minimum wage floor
        # This prevents grandfathering of old low wages
        # Minimum wage is set at firm level via wage_offer enforcement
        # But we also need to ensure actual_wages dict is updated
        for worker_id in self.employees:
            if worker_id in self.actual_wages:
                # Ensure existing workers get at least the current wage_offer
                # (which has minimum wage floor already enforced)
                self.actual_wages[worker_id] = max(self.actual_wages[worker_id], self.wage_offer)

        # Track hiring for next planning cycle
        # Note: These should be set from the plan, but we update actual hires here
        self.last_tick_actual_hires = len(hired_households_ids)

    def apply_production_and_costs(self, result: Dict[str, float]) -> None:
        """
        Update inventory, cash, and costs based on production.

        Mutates state.

        Args:
            result: Dict with realized_production_units and optionally other_variable_costs
        """
        realized_production_units = result.get("realized_production_units", 0.0)
        other_variable_costs = result.get("other_variable_costs", 0.0)

        if self.good_category.lower() == "healthcare":
            # Healthcare is service throughput: no storable production/inventory.
            realized_production_units = 0.0
            self.inventory_units = 0.0

        # Track production for pricing decisions
        self.last_units_produced = realized_production_units

        # Update inventory
        self.inventory_units += realized_production_units

        # Compute wage bill based on actual wages paid
        wage_bill = self._current_wage_bill()

        # Update cash (pay wages and costs — depreciation is non-cash)
        self.cash_balance -= wage_bill
        self.cash_balance -= other_variable_costs

        # Capital depreciation: reduces capital stock; non-cash cost that enters unit cost
        cap_config = self._firm_config()
        depreciation_units = self.capital_stock * cap_config.capital_depreciation_rate
        self.capital_stock = max(0.0, self.capital_stock - depreciation_units)
        depreciation_cost = depreciation_units * cap_config.capital_cost_per_unit

        # Update unit cost (includes non-cash depreciation for pricing accuracy)
        total_production_cost = wage_bill + other_variable_costs + depreciation_cost

        # Track total costs for dividend calculation (wage + cash costs only, not depreciation)
        self.last_tick_total_costs = wage_bill + other_variable_costs

        if realized_production_units > 0:
            self.unit_cost = total_production_cost / realized_production_units
        elif self.good_category.lower() == "healthcare":
            service_capacity = max(1.0, len(self.employees) * max(self.healthcare_capacity_per_worker, 0.1))
            self.unit_cost = total_production_cost / service_capacity
        else:
            # No production - keep previous unit cost or set to a default
            # To avoid division by zero, we keep the existing unit_cost
            pass

    def apply_sales_and_profit(self, result: Dict[str, float]) -> None:
        """
        Update inventory and cash based on sales.

        Mutates state.

        Args:
            result: Dict with units_sold, revenue, and profit_taxes_paid
        """
        units_sold = result.get("units_sold", 0.0)
        revenue = result.get("revenue", 0.0)
        profit_taxes_paid = result.get("profit_taxes_paid", 0.0)

        # Update inventory (clamp at zero)
        self.inventory_units = max(0.0, self.inventory_units - units_sold)

        # Update cash
        self.cash_balance += revenue
        self.cash_balance -= profit_taxes_paid

        self.last_units_sold = units_sold
        self.last_revenue = revenue
        profit = revenue - profit_taxes_paid - self.last_tick_total_costs
        self.last_profit = profit
        # Track net profit for dividend policy
        self.net_profit = profit

        if self.cash_balance <= 0.0:
            self.zero_cash_streak += 1
        else:
            self.zero_cash_streak = 0

        # Adjust wages if they exceed 80% of revenue
        self.adjust_wages_to_revenue_ratio(revenue)

    def adjust_wages_to_revenue_ratio(self, revenue: float) -> None:
        """
        Adjust wages if wage bill exceeds 80% of revenue.

        Firms target 70-80% of revenue as wages. If wages exceed 80% of revenue,
        reduce all wages by 10% (floored at minimum wage of $20).

        Args:
            revenue: Revenue from this tick
        """
        if revenue <= 0 or not self.employees:
            return

        firm_config = self._firm_config()

        # Calculate current wage bill
        wage_bill = self._current_wage_bill()

        # Check if wages exceed configured threshold of revenue
        wage_ratio = wage_bill / max(revenue, 1e-9)
        if not self.is_baseline and self.good_category.lower() != "healthcare":
            if (
                wage_ratio <= firm_config.max_labor_share * 1.25
                or (
                    self.cash_runway_ticks >= max(2.0, self._expansion_runway_gate_ticks() * 0.5)
                    and self.smoothed_profit_margin >= -0.25
                )
            ):
                return

            minimum_wage = firm_config.minimum_wage_floor
            wage_cut = 0.98
            for employee_id in self.employees:
                current_wage = self.actual_wages.get(employee_id, self.wage_offer)
                self.actual_wages[employee_id] = max(current_wage * wage_cut, minimum_wage)

            self.wage_offer = max(self.wage_offer * wage_cut, minimum_wage)
            return

        if wage_ratio > firm_config.max_labor_share:
            # Reduce all wages by 10%, floored at minimum wage
            minimum_wage = firm_config.minimum_wage_floor
            wage_cut = firm_config.max_wage_decrease_per_tick
            for employee_id in self.employees:
                current_wage = self.actual_wages.get(employee_id, self.wage_offer)
                reduced_wage = current_wage * wage_cut
                new_wage = max(reduced_wage, minimum_wage)
                self.actual_wages[employee_id] = new_wage

            # Also reduce wage_offer for new hires
            self.wage_offer = max(self.wage_offer * wage_cut, minimum_wage)

    def apply_price_and_wage_updates(
        self,
        price_plan: Dict[str, float],
        wage_plan: Dict[str, float]
    ) -> None:
        """
        Update price, markup, and wage offer from plans.

        Mutates state.

        Args:
            price_plan: Dict with price_next and markup_next
            wage_plan: Dict with wage_offer_next
        """
        # Update price and markup
        self.price = max(price_plan["price_next"], self.min_price)
        self.markup = max(0.0, price_plan["markup_next"])

        # Update wage offer
        self.wage_offer = wage_plan["wage_offer_next"]

    def apply_updated_expectations(self, updated_expected_sales: float) -> None:
        """
        Update sales expectations from production planning.

        Mutates state.

        Args:
            updated_expected_sales: New expected sales value
        """
        self.expected_sales_units = updated_expected_sales

    def invest_in_unit_expansion(self, economy: Optional["Economy"] = None) -> bool:
        """
        Housing firms can invest in adding more rental units.

        INVESTMENT RULES:
        - Only housing firms can do this
        - Cost increases with each additional unit (diminishing returns)
        - Base cost: $15,000 per unit
        - Cost multiplier: 1.2 ^ (current_units / 10)
        - Self-finance if: cash >= 2x cost
        - Otherwise: request bank expansion loan (will be processed in Phase 6.6b)

        CRISIS TRIGGER:
        - Allow expansion at ANY occupancy if homeless_household_count > 30
        - This resolves the deadlock where zero-unit firms can never reach 85%

        Args:
            economy: Optional reference to Economy for homeless count and bank access

        Returns:
            True if investment was made or loan requested, False otherwise

        Mutates state.
        """
        if self.good_category.lower() != "housing":
            return False

        # Check if we should expand (high occupancy rate OR housing crisis)
        occupancy_rate = len(self.current_tenants) / max(self.max_rental_units, 1)

        # Get homeless count if economy reference available
        homeless_count = economy.homeless_household_count if economy else 0

        # Expansion gates: expand if (1) high occupancy OR (2) housing crisis
        should_consider_expansion = (occupancy_rate >= 0.85) or (homeless_count > 30)

        if not should_consider_expansion:
            return False

        # Calculate cost with diminishing returns
        base_cost = 15000.0
        cost_multiplier = 1.2 ** (self.max_rental_units / 10.0)
        total_cost = base_cost * cost_multiplier

        # Scenario 1: Self-finance if firm has sufficient cash
        if self.cash_balance >= total_cost * 2.0:
            self.cash_balance -= total_cost
            self.max_rental_units += 1
            self.production_capacity_units += 1.0
            self.expected_sales_units += 1.0
            self.property_tax_rate += 0.005  # +0.5% per new unit
            return True

        # Scenario 2: Request bank loan (will be processed in Phase 6.6b)
        if economy is not None:
            self.needs_housing_expansion_loan = True
            self.housing_expansion_loan_amount = total_cost
            return True

        # Cannot expand without cash or bank
        return False

        return True

    def apply_rd_and_quality_update(self, revenue: float) -> float:
        """
        Invest in R&D and update quality level.

        Mutates state.

        Args:
            revenue: Revenue from this tick (used to compute R&D spending)

        Returns:
            Amount spent on R&D (to be redirected to Misc firm)
        """
        firm_config = self._firm_config()

        # Feature 1: No R&D spending during survival mode (preserve cash)
        if self.survival_mode:
            return 0.0

        # Feature 4: Pro-Cyclical R&D — tied to net profit margin
        # Unprofitable firms spend nothing on R&D. Profitable firms scale up
        # R&D with margin, capped at a reasonable maximum.
        if self.net_profit <= 0 or revenue <= 0:
            rd_rate = 0.0
        else:
            net_margin = self.net_profit / revenue
            rd_rate = firm_config.rd_base_rate + firm_config.rd_margin_scaling * net_margin
            rd_rate = min(rd_rate, firm_config.rd_max_rate)

        # Compute R&D spending
        rd_spending = revenue * rd_rate
        self.accumulated_rd_investment += rd_spending

        # Deduct R&D spending from cash
        self.cash_balance -= rd_spending

        # Improve quality based on R&D investment
        quality_gain = rd_spending * self.quality_improvement_per_rd_dollar

        # Apply quality decay (degradation over time)
        quality_loss = self.quality_decay_rate

        # Update quality (clamped to [0, 10])
        self.quality_level = max(
            0.0,
            min(10.0, self.quality_level + quality_gain - quality_loss)
        )

        return rd_spending

    def distribute_profits(self, household_lookup: Dict[int, 'HouseholdAgent']) -> float:
        """
        Distribute excess cash to firm owners as dividends.

        This prevents wealth from accumulating in firms and ensures
        profits flow back to households who own the firms.

        Args:
            household_lookup: Dict mapping household_id -> HouseholdAgent

        Returns:
            Total dividends distributed

        Mutates state:
            - Reduces firm cash_balance
            - Increases owner household cash_balance
        """
        if not self.owners or len(self.owners) == 0:
            return 0.0  # No owners, no dividends

        # Feature 1: No dividends during survival mode (preserve cash)
        if self.survival_mode:
            return 0.0

        if self.net_profit <= 0:
            return 0.0

        target_dividend = self.net_profit * self.payout_ratio

        # Keep six weeks of operating costs as reserve
        safety_buffer = self.last_tick_total_costs * 6.0
        available_cash = self.cash_balance - safety_buffer
        actual_dividend = min(target_dividend, max(0.0, available_cash))

        if actual_dividend <= 0:
            return 0.0

        dividend_per_owner = actual_dividend / len(self.owners)

        total_distributed = 0.0
        for owner_id in self.owners:
            if owner_id in household_lookup:
                household = household_lookup[owner_id]
                household.cash_balance += dividend_per_owner
                household.last_dividend_income += dividend_per_owner
                household.add_ledger_flow("dividends", dividend_per_owner)
                if self.firm_id not in household.last_dividend_firm_ids:
                    household.last_dividend_firm_ids.append(self.firm_id)
                total_distributed += dividend_per_owner

        self.cash_balance -= total_distributed

        return total_distributed


@dataclass(slots=True)
class BankAgent:
    """Central bank agent that provides the economy's credit channel.

    Handles all lending (firm emergency, seed, liquidation, household medical),
    deposit accounts, credit scoring, and interest rate mechanics. Designed as
    an optional add-on: the simulation works without it (all loan paths fall
    back to government direct lending when ``bank is None``).

    Credit scoring uses a [0, 1] scale with slow buildup (+0.01 per on-time
    tick) and meaningful penalties for missed payments and defaults. A circuit
    breaker halts new lending when reserves drop below the reserve ratio, but
    the government can still inject liquidity through
    ``issue_government_backed_loan``.
    """

    bank_id: int = 0
    cash_reserves: float = 500_000.0
    total_deposits: float = 0.0
    total_loans_outstanding: float = 0.0

    # Rate policy
    base_interest_rate: float = 0.03       # 3% annual
    deposit_rate: float = 0.01             # 1% annual on deposits
    reserve_ratio: float = 0.10            # Fraction of deposits held as reserves

    # Loss tracking
    loan_loss_provision: float = 0.0       # Accumulated write-offs from defaults

    # Per-tick telemetry
    last_tick_interest_income: float = 0.0
    last_tick_deposit_interest_paid: float = 0.0
    last_tick_new_loans: float = 0.0
    last_tick_defaults: float = 0.0
    last_tick_repayments: float = 0.0

    # Credit scores: agent_id -> float [0.0, 1.0]
    firm_credit_scores: Dict[int, float] = field(default_factory=dict)
    household_credit_scores: Dict[int, float] = field(default_factory=dict)

    # Active loan ledger: list of dicts tracking each loan
    # Each entry: {borrower_type, borrower_id, principal, remaining, payment_per_tick,
    #              rate, term_remaining, govt_backed}
    active_loans: list = field(default_factory=list)

    # ── helpers ──────────────────────────────────────────────────────

    @property
    def required_reserves(self) -> float:
        """Minimum cash the bank must hold against deposits."""
        return self.total_deposits * self.reserve_ratio

    @property
    def lendable_cash(self) -> float:
        """Cash available for new loans (reserves minus requirement)."""
        return max(0.0, self.cash_reserves - self.required_reserves)

    def can_lend(self) -> bool:
        """Return True if the bank has reserves above the circuit-breaker floor."""
        return self.cash_reserves > self.required_reserves

    # ── credit scoring ───────────────────────────────────────────────

    def get_firm_credit_score(self, firm_id: int) -> float:
        """Return a firm's credit score, initializing to 0.5 if unknown."""
        return self.firm_credit_scores.get(firm_id, 0.5)

    def get_household_credit_score(self, household_id: int) -> float:
        """Return a household's credit score, initializing to 0.5 if unknown."""
        return self.household_credit_scores.get(household_id, 0.5)

    def update_firm_credit_score(self, firm_id: int, delta: float) -> None:
        """Adjust a firm's credit score by *delta*, clamped to [0, 1]."""
        current = self.firm_credit_scores.get(firm_id, 0.5)
        self.firm_credit_scores[firm_id] = max(0.0, min(1.0, current + delta))

    def update_household_credit_score(self, household_id: int, delta: float) -> None:
        """Adjust a household's credit score by *delta*, clamped to [0, 1]."""
        current = self.household_credit_scores.get(household_id, 0.5)
        self.household_credit_scores[household_id] = max(0.0, min(1.0, current + delta))

    # ── lending ──────────────────────────────────────────────────────

    def _risk_adjusted_rate(self, credit_score: float, spread: float = 0.05) -> float:
        """Annual interest rate for a borrower, adding a risk premium to base rate.

        ``spread`` is the maximum additional rate for a score of 0.0.
        """
        return self.base_interest_rate + (1.0 - credit_score) * spread

    def _firm_existing_debt(self, firm_id: int) -> float:
        """Total outstanding debt for a firm. O(n) scan but called rarely per tick."""
        return sum(
            loan["remaining"] for loan in self.active_loans
            if loan["borrower_type"] == "firm" and loan["borrower_id"] == firm_id
        )

    def _can_firm_borrow(self, firm_id: int, amount: float, trailing_revenue: float) -> bool:
        """Check leverage ceiling: total debt + new amount must be < 3× trailing revenue.

        Returns False if the firm would breach the ceiling, preventing debt stacking.
        """
        return (self._firm_existing_debt(firm_id) + amount) < 3.0 * max(trailing_revenue, 1.0)

    def _max_firm_borrowable(self, firm_id: int, trailing_revenue: float) -> float:
        """Maximum additional debt a firm can take before hitting the 3× leverage ceiling."""
        return max(0.0, 3.0 * max(trailing_revenue, 1.0) - self._firm_existing_debt(firm_id))

    def originate_loan(
        self,
        borrower_type: str,
        borrower_id: int,
        principal: float,
        annual_rate: float,
        term_ticks: int,
        govt_backed: bool = False,
    ) -> dict:
        """Create a new loan record and disburse funds from bank reserves.

        If *govt_backed*, the loan is tracked but funds were already drawn
        from government cash (used during circuit-breaker emergencies).

        Returns the loan record dict.
        """
        interest_multiplier = 1.0 + annual_rate
        total_repayment = principal * interest_multiplier
        payment_per_tick = total_repayment / max(1, term_ticks)

        # Interest income the bank earns per tick from this loan
        interest_income_per_tick = (principal * annual_rate) / max(1, term_ticks)

        loan = {
            "borrower_type": borrower_type,
            "borrower_id": borrower_id,
            "principal": principal,
            "remaining": total_repayment,
            "payment_per_tick": payment_per_tick,
            "rate": annual_rate,
            "term_remaining": term_ticks,
            "govt_backed": govt_backed,
            "missed_payments": 0,
            "interest_income_per_tick": interest_income_per_tick,
        }
        self.active_loans.append(loan)
        self.total_loans_outstanding += total_repayment

        if not govt_backed:
            self.cash_reserves -= principal

        self.last_tick_new_loans += principal
        return loan

    def collect_repayment(self, loan: dict, payment: float) -> None:
        """Record a repayment against a loan. Updates bank reserves and totals."""
        loan["remaining"] -= payment
        loan["term_remaining"] = max(0, loan["term_remaining"] - 1)
        loan["missed_payments"] = 0  # Reset miss streak on successful payment
        self.total_loans_outstanding = max(0.0, self.total_loans_outstanding - payment)

        if not loan["govt_backed"]:
            self.cash_reserves += payment
        self.last_tick_repayments += payment
        self.last_tick_interest_income += loan.get("interest_income_per_tick", 0.0)

    def write_off_loan(self, loan: dict) -> None:
        """Write off a defaulted loan. Absorbs loss into provision."""
        remaining = loan["remaining"]
        self.loan_loss_provision += remaining
        self.total_loans_outstanding = max(0.0, self.total_loans_outstanding - remaining)
        self.last_tick_defaults += remaining
        loan["remaining"] = 0.0
        loan["term_remaining"] = 0

    def issue_government_backed_loan(
        self,
        borrower_type: str,
        borrower_id: int,
        principal: float,
        annual_rate: float,
        term_ticks: int,
        govt: "GovernmentAgent",
    ) -> Optional[dict]:
        """Issue a loan funded by government cash when bank reserves are insufficient.

        Used during circuit-breaker situations so emergency lending can continue.
        Returns the loan record, or None if government also can't fund it.
        """
        if govt.cash_balance < principal:
            return None

        govt.cash_balance -= principal
        return self.originate_loan(
            borrower_type=borrower_type,
            borrower_id=borrower_id,
            principal=principal,
            annual_rate=annual_rate,
            term_ticks=term_ticks,
            govt_backed=True,
        )

    # ── deposits ─────────────────────────────────────────────────────

    def accept_deposit(self, household_id: int, amount: float) -> None:
        """Accept a deposit from a household into the bank."""
        self.cash_reserves += amount
        self.total_deposits += amount

    def withdraw(self, household_id: int, amount: float) -> float:
        """Withdraw from a household's deposit. Returns actual amount withdrawn."""
        actual = min(amount, self.cash_reserves)
        self.cash_reserves -= actual
        self.total_deposits = max(0.0, self.total_deposits - actual)
        return actual

    def pay_deposit_interest(self, deposit_amount: float) -> float:
        """Calculate and return weekly interest on a household's deposit balance."""
        weekly_rate = self.deposit_rate / 52.0
        interest = deposit_amount * weekly_rate
        self.cash_reserves -= interest
        self.total_deposits += interest
        self.last_tick_deposit_interest_paid += interest
        return interest

    def update_deposit_rate(self) -> None:
        """Fix 22: Adjust deposit rate based on reserve ratio.

        High reserves → lower rate (don't need more deposits).
        Low reserves → higher rate (need to attract deposits).
        Also caps the rate so it never exceeds what lending income can support.
        """
        if self.total_deposits <= 0:
            self.deposit_rate = 0.02  # Attractive bootstrap rate
            return

        actual_ratio = self.cash_reserves / self.total_deposits
        target = self.reserve_ratio  # 0.10

        if actual_ratio > 0.20:
            # Excess reserves — nudge rate down; floor at 0.5%
            excess = (actual_ratio - 0.20) / 0.20
            self.deposit_rate = max(0.005, 0.01 - 0.005 * min(excess, 1.0))
        elif actual_ratio < target:
            # Below required reserves — raise rate to attract deposits; cap at 3%
            shortage = (target - actual_ratio) / max(target, 1e-6)
            self.deposit_rate = min(0.03, 0.01 + 0.02 * min(shortage, 1.0))
        else:
            # Comfort zone (10–20%)
            self.deposit_rate = 0.01

        # Safety valve: deposit rate can't exceed what lending income can sustain
        if self.last_tick_interest_income > 0 and self.total_deposits > 0:
            max_sustainable = (self.last_tick_interest_income * 52.0) / self.total_deposits
            self.deposit_rate = min(self.deposit_rate, max_sustainable)

    # ── tick reset ───────────────────────────────────────────────────

    def reset_tick_telemetry(self) -> None:
        """Zero out per-tick tracking fields at the start of each tick."""
        self.last_tick_interest_income = 0.0
        self.last_tick_deposit_interest_paid = 0.0
        self.last_tick_new_loans = 0.0
        self.last_tick_defaults = 0.0
        self.last_tick_repayments = 0.0

    def cleanup_settled_loans(self) -> None:
        """Remove fully repaid or written-off loans from the active ledger."""
        self.active_loans = [l for l in self.active_loans if l["remaining"] > 1e-6]

    # ── serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize bank state for frontend / metrics."""
        firm_scores = list(self.firm_credit_scores.values())
        hh_scores = list(self.household_credit_scores.values())
        return {
            "bank_id": self.bank_id,
            "cash_reserves": self.cash_reserves,
            "total_deposits": self.total_deposits,
            "total_loans_outstanding": self.total_loans_outstanding,
            "base_interest_rate": self.base_interest_rate,
            "deposit_rate": self.deposit_rate,
            "reserve_ratio": self.reserve_ratio,
            "reserve_ratio_actual": self.cash_reserves / max(self.total_deposits, 1.0),
            "loan_loss_provision": self.loan_loss_provision,
            "lendable_cash": self.lendable_cash,
            "can_lend": self.can_lend(),
            "active_loan_count": len(self.active_loans),
            "last_tick_new_loans": self.last_tick_new_loans,
            "last_tick_defaults": self.last_tick_defaults,
            "last_tick_repayments": self.last_tick_repayments,
            "last_tick_deposit_interest_paid": self.last_tick_deposit_interest_paid,
            "last_tick_interest_income": self.last_tick_interest_income,
            "avg_credit_score_firms": (
                sum(firm_scores) / len(firm_scores) if firm_scores else 0.5
            ),
            "avg_credit_score_households": (
                sum(hh_scores) / len(hh_scores) if hh_scores else 0.5
            ),
        }


@dataclass(slots=True)
class GovernmentAgent(AgentMixin):
    """Represents the government in the economic simulation.

    The government is a policy actor that controls 13 policy levers:
    wage_tax_rate, profit_tax_rate, investment_tax_rate, benefit_level,
    public_works, minimum_wage_policy, sector_subsidy_target,
    sector_subsidy_level, infrastructure_spending, technology_spending,
    bailout_policy, bailout_target, and bailout_budget.

    Each lever translates to concrete numeric parameters that affect
    the economy.  A future LLM agent will choose lever settings each
    tick; until then, all levers use defaults that replicate the
    current automatic stabiliser behaviour.

    Mechanical operations (tax collection, benefit disbursement,
    fiscal accounting) remain automatic — they execute whatever the
    current lever settings dictate.
    """

    # ── Financial state ──────────────────────────────────────────────
    cash_balance: float = 0.0

    # ── Policy lever settings (v1 action space) ──────────────────────
    # Each lever is a string key into a fixed option set.
    # Defaults replicate current automatic behaviour.
    # Tax rates — continuous levers set directly by LLM or UI
    wage_tax_rate: float = 0.15               # [0.0, 0.50] — fraction of wages taxed
    profit_tax_rate: float = 0.20             # [0.0, 0.50] — fraction of firm profits taxed
    investment_tax_rate: float = 0.10         # [0.0, 0.30] — fraction of R&D/investment taxed
    benefit_level: str = "neutral"            # {low, neutral, high, crisis}
    public_works_toggle: str = "off"          # {off, on}
    minimum_wage_policy: str = "neutral"      # {low, neutral, high}
    sector_subsidy_target: str = "none"       # {none, food, housing, services, healthcare}
    sector_subsidy_level: int = 0             # {0, 10, 25, 50} — percent of price govt pays
    infrastructure_spending: str = "none"     # {none, low, medium, high}
    technology_spending: str = "none"         # {none, low, medium, high}
    bailout_policy: str = "off"               # {off, sector, all}
    bailout_target: str = "none"              # {none, food, housing, services, healthcare}
    bailout_budget: int = 0                   # {0, 5000, 10000, 25000, 50000} per decision cycle

    # ── Derived numeric parameters (set by apply_policy_levers) ──────
    unemployment_benefit_level: float = 30.0  # per-tick payment to unemployed
    min_cash_threshold: float = 100.0         # safety net threshold
    transfer_budget: float = 10000.0          # max total transfers per tick
    _minimum_wage_floor: float = 36.0         # set by minimum_wage_policy lever
    _sector_subsidy_rate: float = 0.0         # set by sector_subsidy_level lever
    _transfer_budget_buffer: float = 1.5      # multiplier for sizing transfer_budget

    # ── Budget tracking (soft constraint) ────────────────────────────
    fiscal_pressure: float = 0.0              # EMA of (spending - revenue) / GDP, with a small surplus floor
    spending_efficiency: float = 1.0          # 0.0-1.0, penalty from sustained deficits
    last_tick_revenue: float = 0.0            # total tax revenue last tick
    last_tick_spending: float = 0.0           # total govt spending last tick

    # ── Legacy fields (kept for compatibility) ───────────────────────
    ubi_amount: float = 0.0
    wealth_tax_threshold: float = 1_000_000.0
    wealth_tax_rate: float = 0.0
    target_inflation_rate: float = 0.02
    birth_rate: float = 0.0

    # Government baseline firm tracking (category -> firm_id)
    baseline_firm_ids: Dict[str, int] = field(default_factory=dict)

    # Government investment capabilities
    infrastructure_investment_budget: float = 0.0   # Set by infrastructure_spending lever
    technology_investment_budget: float = 0.0        # Set by technology_spending lever
    social_investment_budget: float = 750.0          # Legacy — social programs
    stabilization_disabled: bool = False

    # Bailout cycle accounting
    bailout_budget_remaining: float = 0.0
    bailout_cycle_authorized: float = 0.0
    bailout_cycle_disbursed: float = 0.0
    bailout_cycle_firms_assisted: int = 0
    bailout_cycle_sector_spend: Dict[str, float] = field(default_factory=dict)
    bailout_cycle_assisted_firms: Dict[int, float] = field(default_factory=dict)
    last_cycle_bailout_authorized: float = 0.0
    last_cycle_bailout_disbursed: float = 0.0
    last_cycle_bailout_remaining: float = 0.0
    last_cycle_bailout_firms_assisted: int = 0
    last_cycle_bailout_sector_spend: Dict[str, float] = field(default_factory=dict)
    last_tick_bailout_disbursed: float = 0.0
    last_tick_bailout_firms_assisted: int = 0
    last_tick_bailout_sector_spend: Dict[str, float] = field(default_factory=dict)

    # Economic multipliers from government investment
    infrastructure_productivity_multiplier: float = 1.0  # Affects all worker productivity
    technology_quality_multiplier: float = 1.0            # Affects all firm quality
    social_happiness_multiplier: float = 1.0              # Affects worker happiness/performance
    wage_bracket_scalers: Dict[str, float] = field(default_factory=dict)

    # ── Valid options / ranges for each lever (class-level constants) ─
    VALID_TAX_RATE_RANGE = (0.0, 0.50)       # min, max for wage/profit tax
    VALID_INVESTMENT_TAX_RANGE = (0.0, 0.30) # min, max for investment tax
    VALID_BENEFIT_LEVELS = {"low", "neutral", "high", "crisis"}
    VALID_PUBLIC_WORKS = {"off", "on"}
    VALID_MIN_WAGE_POLICIES = {"low", "neutral", "high"}
    VALID_SUBSIDY_TARGETS = {"none", "food", "housing", "services", "healthcare"}
    VALID_SUBSIDY_LEVELS = {0, 10, 25, 50}
    VALID_INFRA_SPENDING = {"none", "low", "medium", "high"}
    VALID_TECH_SPENDING = {"none", "low", "medium", "high"}
    VALID_BAILOUT_POLICIES = {"off", "sector", "all"}
    VALID_BAILOUT_TARGETS = {"none", "food", "housing", "services", "healthcare"}
    VALID_BAILOUT_BUDGETS = {0, 5000, 10000, 25000, 50000}

    def __post_init__(self):
        """Validate invariants and apply initial lever settings."""
        if not (0.0 <= self.wage_tax_rate <= 0.50):
            raise ValueError(f"wage_tax_rate must be in [0,0.50], got {self.wage_tax_rate}")
        if not (0.0 <= self.profit_tax_rate <= 0.50):
            raise ValueError(f"profit_tax_rate must be in [0,0.50], got {self.profit_tax_rate}")
        if not (0.0 <= self.investment_tax_rate <= 0.30):
            raise ValueError(f"investment_tax_rate must be in [0,0.30], got {self.investment_tax_rate}")
        if self.unemployment_benefit_level < 0:
            raise ValueError(
                f"unemployment_benefit_level cannot be negative, got {self.unemployment_benefit_level}"
            )
        if self.min_cash_threshold < 0:
            raise ValueError(
                f"min_cash_threshold cannot be negative, got {self.min_cash_threshold}"
            )
        if self.transfer_budget < 0:
            raise ValueError(f"transfer_budget cannot be negative, got {self.transfer_budget}")
        if not self.wage_bracket_scalers:
            rng = random.Random(12345)
            self.wage_bracket_scalers = {
                "low": rng.uniform(0.5, 0.9),
                "median": 1.0,
                "p60": rng.uniform(1.05, 1.15),
                "p70": rng.uniform(1.10, 1.20),
                "p90": rng.uniform(1.15, 1.25),
            }
        # Apply lever defaults so derived fields are consistent
        self.apply_policy_levers()
        self.begin_decision_cycle(initial=True)

    # ── Lever → numeric parameter translation ────────────────────────

    def apply_policy_levers(self) -> None:
        """Translate all lever settings into concrete numeric parameters.

        Called once at init and again whenever a lever is changed (by the
        future LLM agent, by the UI, or by ``set_lever``).  This is the
        single source of truth for how lever options map to numbers.
        """
        # Tax rates are now set directly — no translation needed
        self._apply_benefit_level()
        self._apply_minimum_wage_policy()
        self._apply_sector_subsidy()
        self._apply_infrastructure_spending()
        self._apply_technology_spending()
        # public_works_toggle is read directly by Economy — no derived field needed

    def set_lever(self, lever: str, value) -> None:
        """Set a single policy lever and re-derive numeric parameters.

        Args:
            lever: Lever name (e.g. ``"wage_tax_rate"``, ``"benefit_level"``).
            value: Option value or numeric rate.

        Raises:
            ValueError: If *lever* is unknown or *value* is out of range/invalid.
        """
        # Continuous levers (numeric ranges)
        continuous_map = {
            "wage_tax_rate": ("wage_tax_rate", self.VALID_TAX_RATE_RANGE),
            "profit_tax_rate": ("profit_tax_rate", self.VALID_TAX_RATE_RANGE),
            "investment_tax_rate": ("investment_tax_rate", self.VALID_INVESTMENT_TAX_RANGE),
        }
        # Discrete levers (fixed option sets)
        discrete_map = {
            "benefit_level": ("benefit_level", self.VALID_BENEFIT_LEVELS),
            "public_works": ("public_works_toggle", self.VALID_PUBLIC_WORKS),
            "minimum_wage_policy": ("minimum_wage_policy", self.VALID_MIN_WAGE_POLICIES),
            "sector_subsidy_target": ("sector_subsidy_target", self.VALID_SUBSIDY_TARGETS),
            "sector_subsidy_level": ("sector_subsidy_level", self.VALID_SUBSIDY_LEVELS),
            "infrastructure_spending": ("infrastructure_spending", self.VALID_INFRA_SPENDING),
            "technology_spending": ("technology_spending", self.VALID_TECH_SPENDING),
            "bailout_policy": ("bailout_policy", self.VALID_BAILOUT_POLICIES),
            "bailout_target": ("bailout_target", self.VALID_BAILOUT_TARGETS),
            "bailout_budget": ("bailout_budget", self.VALID_BAILOUT_BUDGETS),
        }

        if lever in continuous_map:
            field_name, (lo, hi) = continuous_map[lever]
            try:
                numeric_value = round(float(value), 4)
            except (TypeError, ValueError):
                raise ValueError(f"Lever '{lever}' requires a number, got '{value}'")
            if not (lo <= numeric_value <= hi):
                raise ValueError(
                    f"Value {numeric_value} for lever '{lever}' out of range [{lo}, {hi}]"
                )
            setattr(self, field_name, numeric_value)
            self.apply_policy_levers()
        elif lever in discrete_map:
            field_name, valid_options = discrete_map[lever]
            if value not in valid_options:
                raise ValueError(f"Invalid value '{value}' for lever '{lever}'. Valid: {valid_options}")
            setattr(self, field_name, value)
            self.apply_policy_levers()
            if lever in {"bailout_policy", "bailout_target", "bailout_budget"}:
                self.sync_bailout_cycle_budget()
        else:
            all_levers = list(continuous_map.keys()) + list(discrete_map.keys())
            raise ValueError(f"Unknown lever '{lever}'. Valid: {all_levers}")

    def _apply_benefit_level(self) -> None:
        """Set unemployment benefit and transfer parameters from ``benefit_level`` lever.

        ``neutral`` matches current defaults ($30 benefit, $100 threshold).
        Transfer budget is recalculated each tick by Economy based on
        actual unemployment count × benefit × buffer multiplier.
        """
        table = {
            "low":     (15.0, 50.0,  1.3),
            "neutral": (30.0, 100.0, 1.5),
            "high":    (45.0, 150.0, 1.5),
            "crisis":  (60.0, 200.0, 2.0),
        }
        benefit, threshold, _buffer = table.get(self.benefit_level, table["neutral"])
        self.unemployment_benefit_level = benefit
        self.min_cash_threshold = threshold
        # _transfer_budget_buffer is used by Economy when sizing transfer_budget
        self._transfer_budget_buffer = _buffer

    def _apply_minimum_wage_policy(self) -> None:
        """Set minimum wage floor from ``minimum_wage_policy`` lever.

        Decoupled from benefit_level so the two can be set independently.
        ``neutral`` ($36) matches current behaviour (benefit $30 × 1.2).
        """
        table = {
            "low":     25.0,
            "neutral": 36.0,
            "high":    50.0,
        }
        self._minimum_wage_floor = table.get(self.minimum_wage_policy, 36.0)

    def _apply_sector_subsidy(self) -> None:
        """Set subsidy rate from ``sector_subsidy_level`` lever."""
        self._sector_subsidy_rate = self.sector_subsidy_level / 100.0

    def _apply_infrastructure_spending(self) -> None:
        """Set infrastructure budget from ``infrastructure_spending`` lever.

        Budget is per-tick spending.  Actual productivity gain is applied
        by ``invest_in_infrastructure()`` and scaled by
        ``spending_efficiency`` (budget pressure).
        """
        table = {
            "none":   0.0,
            "low":    500.0,
            "medium": 1000.0,
            "high":   2000.0,
        }
        self.infrastructure_investment_budget = table.get(
            self.infrastructure_spending, 0.0
        )

    def _apply_technology_spending(self) -> None:
        """Set technology budget from ``technology_spending`` lever.

        Budget is per-tick spending.  Quality gain is applied by
        ``invest_in_technology()`` and scaled by ``spending_efficiency``.
        """
        table = {
            "none":   0.0,
            "low":    250.0,
            "medium": 500.0,
            "high":   1000.0,
        }
        self.technology_investment_budget = table.get(
            self.technology_spending, 0.0
        )

    def begin_decision_cycle(self, initial: bool = False) -> None:
        """Roll bailout accounting forward and reset the cycle budget."""
        if not initial:
            self.last_cycle_bailout_authorized = float(self.bailout_cycle_authorized)
            self.last_cycle_bailout_disbursed = float(self.bailout_cycle_disbursed)
            self.last_cycle_bailout_remaining = float(self.bailout_budget_remaining)
            self.last_cycle_bailout_firms_assisted = int(self.bailout_cycle_firms_assisted)
            self.last_cycle_bailout_sector_spend = dict(self.bailout_cycle_sector_spend)
        else:
            self.last_cycle_bailout_authorized = float(self.bailout_budget)
            self.last_cycle_bailout_disbursed = 0.0
            self.last_cycle_bailout_remaining = float(self.bailout_budget)
            self.last_cycle_bailout_firms_assisted = 0
            self.last_cycle_bailout_sector_spend = {}

        self.bailout_cycle_authorized = float(self.bailout_budget)
        self.bailout_budget_remaining = float(self.bailout_budget)
        self.bailout_cycle_disbursed = 0.0
        self.bailout_cycle_firms_assisted = 0
        self.bailout_cycle_sector_spend = {}
        self.bailout_cycle_assisted_firms = {}
        self.reset_tick_bailout_telemetry()

    def reset_tick_bailout_telemetry(self) -> None:
        """Reset per-tick bailout telemetry before a new tick."""
        self.last_tick_bailout_disbursed = 0.0
        self.last_tick_bailout_firms_assisted = 0
        self.last_tick_bailout_sector_spend = {}

    def sync_bailout_cycle_budget(self) -> None:
        """Refresh the active bailout cycle after a manual policy change."""
        self.bailout_cycle_authorized = float(self.bailout_budget)
        self.bailout_budget_remaining = float(self.bailout_budget)
        self.bailout_cycle_disbursed = 0.0
        self.bailout_cycle_firms_assisted = 0
        self.bailout_cycle_sector_spend = {}
        self.bailout_cycle_assisted_firms = {}
        self.reset_tick_bailout_telemetry()

    def record_bailout(self, category: str, firm_id: int, amount: float) -> None:
        """Record one bailout disbursement against the active decision cycle."""
        normalized_category = (category or "unknown").lower()
        amount = float(max(0.0, amount))
        if amount <= 0.0:
            return

        self.bailout_budget_remaining = max(0.0, self.bailout_budget_remaining - amount)
        self.bailout_cycle_disbursed += amount
        if firm_id not in self.bailout_cycle_assisted_firms:
            self.bailout_cycle_assisted_firms[firm_id] = 0.0
            self.bailout_cycle_firms_assisted += 1
        self.bailout_cycle_assisted_firms[firm_id] += amount
        self.bailout_cycle_sector_spend[normalized_category] = (
            self.bailout_cycle_sector_spend.get(normalized_category, 0.0) + amount
        )

        self.last_tick_bailout_disbursed += amount
        self.last_tick_bailout_sector_spend[normalized_category] = (
            self.last_tick_bailout_sector_spend.get(normalized_category, 0.0) + amount
        )
        self.last_tick_bailout_firms_assisted = len(self.bailout_cycle_assisted_firms)

    def to_dict(self) -> Dict[str, object]:
        """Serialize government state to a flat dictionary.

        Includes both policy lever settings (what the LLM chose) and
        derived numeric parameters (what those choices produce), plus
        budget-pressure diagnostics.

        Returns:
            Dictionary suitable for JSON serialisation and LLM observation.
        """
        return {
            # Lever settings (action space)
            "wage_tax_rate": self.wage_tax_rate,
            "profit_tax_rate": self.profit_tax_rate,
            "investment_tax_rate": self.investment_tax_rate,
            "benefit_level": self.benefit_level,
            "public_works": self.public_works_toggle,
            "minimum_wage_policy": self.minimum_wage_policy,
            "sector_subsidy_target": self.sector_subsidy_target,
            "sector_subsidy_level": self.sector_subsidy_level,
            "infrastructure_spending": self.infrastructure_spending,
            "technology_spending": self.technology_spending,
            "bailout_policy": self.bailout_policy,
            "bailout_target": self.bailout_target,
            "bailout_budget": self.bailout_budget,
            # Derived numeric parameters
            "cash_balance": self.cash_balance,
            "unemployment_benefit_level": self.unemployment_benefit_level,
            "min_cash_threshold": self.min_cash_threshold,
            "transfer_budget": self.transfer_budget,
            "minimum_wage_floor": self._minimum_wage_floor,
            "sector_subsidy_rate": self._sector_subsidy_rate,
            "infrastructure_investment_budget": self.infrastructure_investment_budget,
            "technology_investment_budget": self.technology_investment_budget,
            "bailout_budget_remaining": self.bailout_budget_remaining,
            "bailout_cycle_authorized": self.bailout_cycle_authorized,
            "bailout_cycle_disbursed": self.bailout_cycle_disbursed,
            "bailout_cycle_firms_assisted": self.bailout_cycle_firms_assisted,
            "bailout_cycle_sector_spend": dict(self.bailout_cycle_sector_spend),
            "last_cycle_bailout_authorized": self.last_cycle_bailout_authorized,
            "last_cycle_bailout_disbursed": self.last_cycle_bailout_disbursed,
            "last_cycle_bailout_remaining": self.last_cycle_bailout_remaining,
            "last_cycle_bailout_firms_assisted": self.last_cycle_bailout_firms_assisted,
            "last_cycle_bailout_sector_spend": dict(self.last_cycle_bailout_sector_spend),
            "last_tick_bailout_disbursed": self.last_tick_bailout_disbursed,
            "last_tick_bailout_firms_assisted": self.last_tick_bailout_firms_assisted,
            "last_tick_bailout_sector_spend": dict(self.last_tick_bailout_sector_spend),
            # Budget pressure
            "fiscal_pressure": self.fiscal_pressure,
            "spending_efficiency": self.spending_efficiency,
            "last_tick_revenue": self.last_tick_revenue,
            "last_tick_spending": self.last_tick_spending,
            # Multipliers
            "infrastructure_productivity_multiplier": self.infrastructure_productivity_multiplier,
            "technology_quality_multiplier": self.technology_quality_multiplier,
            "social_happiness_multiplier": self.social_happiness_multiplier,
            # Legacy
            "baseline_firm_ids": dict(self.baseline_firm_ids),
        }

    def register_baseline_firm(self, category: str, firm_id: int) -> None:
        """Record the firm id for a government baseline firm."""
        self.baseline_firm_ids[category.lower()] = firm_id

    def is_baseline_firm(self, firm_id: int) -> bool:
        """Check if a firm belongs to the government baseline set."""
        return firm_id in self.baseline_firm_ids.values()

    def get_unemployment_benefit_level(self) -> float:
        """
        Get the current unemployment benefit level.

        This is used by households to anchor their reservation wage.

        Returns:
            Unemployment benefit amount per tick
        """
        return self.unemployment_benefit_level

    def get_minimum_wage(self) -> float:
        """Return the minimum wage floor set by the ``minimum_wage_policy`` lever.

        Decoupled from ``benefit_level`` so the two can be tuned
        independently.  The floor is set in ``_apply_minimum_wage_policy``.

        Returns:
            Minimum wage that firms must pay per tick.
        """
        return self._minimum_wage_floor

    def plan_transfers(self, households: List[Dict[str, object]]) -> Dict[int, float]:
        """
        Plan transfers to unemployed households and those below cash threshold.

        REALISTIC GOVERNMENT BEHAVIOR:
        - Governments can run deficits (borrow money) to fund transfers during recessions
        - Transfer budget is dynamic, not a hard cap
        - During high unemployment, governments increase spending (counter-cyclical policy)

        Does not mutate state; returns a plan dict.

        Args:
            households: List of dicts with household_id, is_employed, cash_balance

        Returns:
            Dict mapping household_id -> transfer_amount
        """
        # Explicitly disable unemployment transfers when benefit policy is zeroed out.
        if self.unemployment_benefit_level <= 0.0:
            return {}

        transfers = {}

        # First pass: baseline unemployment benefits
        unemployed_households = [
            h for h in households
            if not h.get("is_employed", False)
        ]

        # REALISTIC: Governments pay full unemployment benefits even if it creates deficits
        # The transfer_budget is more of a soft constraint than a hard cap
        # In real life, governments borrow during recessions to fund unemployment insurance
        baseline_transfers_total = 0.0
        for household in unemployed_households:
            household_id = household["household_id"]
            baseline_transfer = self.unemployment_benefit_level
            transfers[household_id] = baseline_transfer
            baseline_transfers_total += baseline_transfer

        # Second pass: additional gap-filling for households below min_cash_threshold
        # Calculate gaps for all unemployed households
        gaps = {}
        total_gap = 0.0

        for household in unemployed_households:
            household_id = household["household_id"]
            cash_balance = household.get("cash_balance", 0.0)

            # Gap after receiving baseline transfer
            future_cash = cash_balance + transfers[household_id]
            gap = max(self.min_cash_threshold - future_cash, 0.0)

            if gap > 0:
                gaps[household_id] = gap
                total_gap += gap

        # Allocate additional transfers to close gaps, subject to budget
        remaining_budget = max(self.transfer_budget - baseline_transfers_total, 0.0)

        if total_gap > 0 and remaining_budget > 0:
            # Determine how much we can afford to close gaps
            if total_gap <= remaining_budget:
                # Can fully close all gaps
                scale_factor = 1.0
            else:
                # Must scale down gap-filling to fit budget
                scale_factor = remaining_budget / total_gap

            # Add gap-filling transfers
            for household_id, gap in gaps.items():
                additional_transfer = gap * scale_factor
                transfers[household_id] += additional_transfer

        return transfers

    def plan_taxes(
        self,
        households: List[Dict[str, object]],
        firms: List[Dict[str, object]]
    ) -> Dict[str, Dict[int, float]]:
        """
        Plan taxes on wages and profits.

        Does not mutate state; returns a plan dict.

        Args:
            households: List of dicts with household_id and wage_income
            firms: List of dicts with firm_id and profit_before_tax

        Returns:
            Dict with "wage_taxes" and "profit_taxes", each mapping ID -> tax amount
        """
        wage_taxes: Dict[int, float] = {}
        profit_taxes: Dict[int, float] = {}

        wages = [h.get("wage_income", 0.0) for h in households]
        if wages:
            p25, p50, p60, p70, p90 = np.percentile(wages, [25, 50, 60, 70, 90])
        else:
            p25 = p50 = p60 = p70 = p90 = 0.0

        for household in households:
            household_id = household["household_id"]
            wage_income = household.get("wage_income", 0.0)

            if wage_income <= p25:
                rate = self.wage_tax_rate * self.wage_bracket_scalers.get("low", 0.8)
            elif wage_income <= p50:
                rate = self.wage_tax_rate * self.wage_bracket_scalers.get("median", 1.0)
            elif wage_income <= p60:
                rate = self.wage_tax_rate * self.wage_bracket_scalers.get("p60", 1.1)
            elif wage_income <= p70:
                rate = self.wage_tax_rate * self.wage_bracket_scalers.get("p70", 1.15)
            elif wage_income <= p90:
                rate = self.wage_tax_rate * self.wage_bracket_scalers.get("p90", 1.2)
            else:
                rate = self.wage_tax_rate * (self.wage_bracket_scalers.get("p90", 1.2) + 0.03)

            wage_taxes[household_id] = max(wage_income * rate, 0.0)

        # WEALTH-BASED PROGRESSIVE TAXATION FOR FIRMS
        # Use quartiles of firm cash balance to determine tax brackets
        # This ensures consistent progressive taxation regardless of absolute wealth levels

        firm_cash = [f.get("cash_balance", 0.0) for f in firms]

        if firm_cash and len(firm_cash) >= 4:
            # Calculate percentile thresholds
            q1, q2, q3, p90, p99 = np.percentile(firm_cash, [25, 50, 75, 90, 99])  # poor / average / rich / very rich / ultra rich

            # Initialize tax rate modifiers (deterministic per simulation)
            rng = random.Random(54321)  # Fixed seed for consistency

            # Base profit tax rate (for average firms in Q2-Q3 range)
            base_rate = self.profit_tax_rate

            # Random additional tax for each bracket
            # Top 1%: base + (20-35% extra) - MASSIVE wealth tax on ultra-rich
            top_1_extra = rng.uniform(0.20, 0.35)
            top_1_rate = min(0.60, base_rate + top_1_extra)  # Cap at 60%

            # Very rich (top 10%): base + (10-20% extra)
            very_rich_extra = rng.uniform(0.10, 0.20)
            very_rich_rate = base_rate + very_rich_extra

            # Rich (top 25%): base + (5% to very_rich_extra - 1%)
            rich_extra = rng.uniform(0.05, max(0.06, very_rich_extra - 0.01))
            rich_rate = base_rate + rich_extra

            # Average: base rate (Q2-Q3)
            average_rate = base_rate

            # Poor: base - (0-5%)
            poor_discount = rng.uniform(0.0, 0.05)
            poor_rate = max(0.01, base_rate - poor_discount)
        else:
            # Not enough firms for quartiles, use base rate
            q1 = q2 = q3 = p90 = p99 = 0.0
            poor_rate = average_rate = rich_rate = very_rich_rate = top_1_rate = self.profit_tax_rate

        # Apply wealth-based tax rates to each firm
        for firm in firms:
            firm_id = firm["firm_id"]
            profit_before_tax = firm.get("profit_before_tax", 0.0)
            cash_balance = firm.get("cash_balance", 0.0)

            # Determine tax rate based on wealth percentile
            if cash_balance <= q1:
                # Poor firms (bottom 25%)
                rate = poor_rate
            elif cash_balance <= q2:
                # Below average firms (25-50%)
                rate = average_rate * 0.9  # Slight discount
            elif cash_balance <= q3:
                # Above average firms (50-75%)
                rate = average_rate
            elif cash_balance <= p90:
                # Rich firms (75-90%)
                rate = rich_rate
            elif cash_balance <= p99:
                # Very rich firms (90-99%)
                rate = very_rich_rate
            else:
                # TOP 1% - Ultra rich firms get hit with massive wealth tax
                rate = top_1_rate

            # Calculate total profit tax
            profit_taxes[firm_id] = max(profit_before_tax * rate, 0.0)

        # Calculate property taxes for housing firms
        property_taxes = {}
        for firm in firms:
            firm_id = firm["firm_id"]
            if firm.get("good_category") == "Housing" and firm.get("property_tax_rate", 0.0) > 0:
                # Property tax based on assessed property value (rent × units), not cash balance.
                # Annual rate divided by 52 for weekly payment.
                rental_units = firm.get("max_rental_units", 0)
                rent_per_unit = firm.get("price", 0.0)
                assessed_property_value = rental_units * rent_per_unit * 52.0  # annualized rental income as proxy
                weekly_property_tax = firm["property_tax_rate"] * assessed_property_value / 52.0
                property_taxes[firm_id] = max(weekly_property_tax, 0.0)

        return {
            "wage_taxes": wage_taxes,
            "profit_taxes": profit_taxes,
            "property_taxes": property_taxes,
        }

    def apply_fiscal_results(
        self,
        total_wage_taxes: float,
        total_profit_taxes: float,
        total_transfers: float,
        total_property_taxes: float = 0.0
    ) -> None:
        """
        Update government cash based on fiscal operations.

        Mutates state.

        Args:
            total_wage_taxes: Sum of all wage taxes collected
            total_profit_taxes: Sum of all profit taxes collected
            total_transfers: Sum of all transfers paid out
            total_property_taxes: Sum of all property taxes collected (from housing firms)
        """
        # Collect taxes
        self.cash_balance += total_wage_taxes
        self.cash_balance += total_profit_taxes
        self.cash_balance += total_property_taxes

        # Pay transfers
        self.cash_balance -= total_transfers

    def adjust_policies(self, unemployment_rate: float, inflation_rate: float, deficit_ratio: float, num_unemployed: int = 0, gdp: float = 0.0, total_tax_revenue: float = 0.0, num_bankrupt_firms: int = 0) -> None:
        """Perform mechanical per-tick policy housekeeping.

        This method no longer contains counter-cyclical auto-stabilisers.
        Tax rates and benefit levels are now set by the 7 policy levers
        (via ``apply_policy_levers``).  The only remaining automatic
        operation is sizing the transfer budget to match actual
        unemployment counts — this is execution, not decision-making.

        Args:
            unemployment_rate: Current unemployment rate (0-1).
            inflation_rate: Current inflation rate (unused, kept for API compat).
            deficit_ratio: Government deficit ratio (unused, kept for API compat).
            num_unemployed: Actual count of unemployed households.
            gdp: Economy-wide GDP estimate.
            total_tax_revenue: Total tax revenue (unused, kept for API compat).
            num_bankrupt_firms: Count of bankrupt firms (unused, kept for API compat).
        """
        if self.stabilization_disabled:
            return

        # Mechanical: size transfer_budget to cover actual unemployment
        # using the buffer multiplier from the benefit_level lever.
        if num_unemployed > 0:
            expected_baseline = num_unemployed * self.unemployment_benefit_level
            self.transfer_budget = expected_baseline * self._transfer_budget_buffer
        else:
            self.transfer_budget = max(0.0, self.transfer_budget)

    def invest_in_infrastructure(self) -> float:
        """Spend the infrastructure budget to boost economy-wide productivity.

        The actual productivity gain is scaled by ``spending_efficiency``
        so that sustained deficits reduce the effectiveness of spending
        (crowding-out / bureaucratic drag).

        Only spends if the lever is not ``"none"`` (budget > 0) and the
        treasury can cover the outlay.

        Returns:
            Amount actually invested (0.0 if skipped).
        """
        if self.infrastructure_investment_budget <= 0.0:
            return 0.0

        if self.cash_balance >= self.infrastructure_investment_budget:
            investment = self.infrastructure_investment_budget
            self.cash_balance -= investment

            # Each $1000 invested → +0.5% productivity, scaled by efficiency
            base_gain = (investment / 1000.0) * 0.005
            effective_gain = base_gain * self.spending_efficiency
            self.infrastructure_productivity_multiplier += effective_gain

            return investment
        return 0.0

    def invest_in_technology(self) -> float:
        """Spend the technology budget to boost economy-wide product quality.

        Gain is scaled by ``spending_efficiency``.  Capped at 1.15
        (15 % max quality improvement) so the lever has meaningful
        differentiation between ``low`` and ``medium`` over longer runs.

        Returns:
            Amount actually invested (0.0 if skipped).
        """
        if self.technology_investment_budget <= 0.0:
            return 0.0

        if self.cash_balance >= self.technology_investment_budget:
            investment = self.technology_investment_budget
            self.cash_balance -= investment

            # Each $500 invested → +0.5% quality, scaled by efficiency
            base_gain = (investment / 500.0) * 0.005
            effective_gain = base_gain * self.spending_efficiency

            self.technology_quality_multiplier = min(
                1.15,
                self.technology_quality_multiplier + effective_gain
            )

            return investment
        return 0.0

    def invest_in_social_programs(self) -> float:
        """
        Government invests in social programs to improve happiness.

        Social investment increases healthcare, amenities, and other
        quality-of-life factors that boost worker happiness and performance.

        Mutates state.

        Returns:
            Amount invested in social programs
        """
        if self.stabilization_disabled:
            self.social_happiness_multiplier = 1.0
            return 0.0

        investment = min(self.cash_balance, self.social_investment_budget)
        if investment <= 0:
            self.social_happiness_multiplier = 1.0
            return 0.0

        self.cash_balance -= investment
        divisor = max(CONFIG.government.social_gain_divisor, 1.0)
        self.social_happiness_multiplier = 1.0 + (investment / divisor)
        return investment

    def make_investments(self) -> Dict[str, float]:
        """
        Government bond purchases with surplus funds (removed infrastructure/social programs).

        When government has surplus, it purchases bonds from Misc firm,
        which distributes the money to households (1 person per tick).

        Mutates state.

        Returns:
            Dict with "bonds" key containing amount spent on bond purchases
        """
        investments = {"bonds": 0.0}

        if self.stabilization_disabled:
            return investments

        # Define surplus threshold as percentage of cash balance
        surplus_threshold_pct = 0.20  # Consider 20%+ above baseline as surplus
        baseline_reserve = 50000.0  # Minimum reserve to maintain

        # Calculate surplus (scaled, not fixed)
        if self.cash_balance < baseline_reserve:
            return investments

        surplus = max(0.0, self.cash_balance - baseline_reserve)

        # Spend 10-15% of surplus on bonds each tick (scaled)
        if surplus > baseline_reserve * surplus_threshold_pct:
            bond_purchase_rate = 0.12  # 12% of surplus per tick
            bond_spend = surplus * bond_purchase_rate

            self.cash_balance -= bond_spend
            investments["bonds"] = bond_spend

        return investments

