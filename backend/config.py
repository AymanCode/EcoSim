"""
Simulation Configuration

Centralizes all tunable parameters for the economic simulation.
This replaces scattered "magic numbers" throughout the codebase.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class TimeConfig:
    """Time-related constants."""
    ticks_per_year: int = 52  # One tick = one week
    warmup_ticks: int = 10  # Short warmup to initialize prices and wages


@dataclass
class HouseholdBehaviorConfig:
    """Household behavioral parameters."""

    # Consumption & Savings
    min_savings_rate: float = 0.1  # 10% minimum savings
    max_savings_rate: float = 0.6  # 60% maximum savings
    personality_buckets: int = 6  # Number of savings personality types
    unemployment_spend_sensitivity: float = 0.8

    # Per-household trait ranges (sampled once at initialization)
    spending_tendency_range: Tuple[float, float] = (0.1, 5.0)  # Widened from (0.7,1.3) to match normalization range
    food_preference_range: Tuple[float, float] = (0.8, 1.2)
    services_preference_range: Tuple[float, float] = (0.8, 1.2)
    housing_preference_range: Tuple[float, float] = (0.4, 1.4)
    quality_lavishness_range: Tuple[float, float] = (0.8, 1.3)
    frugality_range: Tuple[float, float] = (0.7, 1.3)
    saving_tendency_range: Tuple[float, float] = (0.0, 1.0)
    health_decay_low_probability: float = 0.60
    health_decay_mid_probability: float = 0.90
    health_decay_low_range: Tuple[float, float] = (0.02, 0.25)
    health_decay_mid_range: Tuple[float, float] = (0.25, 0.45)
    health_decay_high_range: Tuple[float, float] = (0.45, 0.70)

    # Wealth-based Saving Rate (NEW - for compute_saving_rate method)
    low_wealth_reference: float = 0.0  # Minimum wealth for saving calculation
    high_wealth_reference: float = 10000.0  # Typical high wealth (e.g., 90th percentile)

    # Unemployment-based spending (NEW)
    min_spend_fraction: float = 0.3  # Spend 30% when scared
    confidence_multiplier: float = 0.5  # Up to 80% when confident

    # Subsistence spending floor (prevents hoarding during crisis)
    subsistence_min_cash: float = 50.0  # Always spend at least this much if available
    max_spend_fraction: float = 0.9  # Upper bound on discretionary spending fraction

    # Job acceptance (H1 - no job worse than benefits)
    min_job_premium_over_unemployment: float = 1.05  # Jobs must pay 5% more than unemployment benefits

    # Marginal propensity to consume by income source. Real-economy data:
    # bottom-quintile MPC ~0.95, top-quintile ~0.40. Wage and benefit income
    # flow disproportionately to high-MPC households; dividend income flows
    # to low-MPC households. Splitting prevents the simulation's aggregate
    # saving rate from drifting toward panic-mode (~33% leakage observed).
    mpc_wage: float = 0.85          # earned income — high MPC
    mpc_benefit: float = 0.95       # safety-net income — near-100% MPC (income-targeted welfare)
    mpc_dividend: float = 0.40      # capital income — low MPC (saved/reinvested)

    # Counter-cyclical anti-paradox-of-thrift nudge. When unemployment crosses
    # the crisis threshold, MPC for every income source is bumped up so the
    # simulation does not amplify a downturn via panic-saving.
    crisis_unemployment_threshold: float = 0.25
    crisis_mpc_boost: float = 0.10

    # Legacy aliases retained for reference; not currently consumed.
    mpc_from_wages_employed: float = 0.6  # superseded by mpc_wage
    mpc_from_transfers_unemployed: float = 0.8  # superseded by mpc_benefit

    # Saving behavior (H3 - employed vs unemployed)
    max_saving_rate_absolute: float = 0.2  # Hard cap on saving rate
    unemployed_forced_dissaving_wealth: float = 1000.0  # Below this, long-term unemployed can't save
    unemployed_forced_dissaving_duration: float = 50.0  # Ticks before forced dissaving kicks in

    # Job search intensity (H5 - happiness link)
    base_search_intensity: float = 1.0  # Baseline job search effort
    min_search_intensity: float = 0.5  # Minimum (happy & comfortable)
    max_search_intensity: float = 2.0  # Maximum (desperate)

    # Price Elasticity (NEW - Prompt 4)
    food_elasticity: float = 0.5  # Inelastic (necessity)
    services_elasticity: float = 0.8  # Somewhat elastic
    housing_elasticity: float = 1.5  # Elastic (luxury)

    # Substitution Effect (NEW - Prompt 4)
    max_food_budget_share: float = 0.6  # Can use 60% of budget for food if needed

    # Minimum Consumption (Base needs before elasticity)
    min_food_per_tick: float = 2.0
    min_services_per_tick: float = 1.0
    min_food_per_tick_range: Tuple[float, float] = (1.5, 2.5)
    min_services_per_tick_range: Tuple[float, float] = (0.5, 2.0)

    # Price/Wage Expectations
    initial_expected_wage: float = 10.0
    initial_reservation_wage: float = 8.0
    price_expectation_alpha: float = 0.3  # Price belief smoothing
    wage_expectation_alpha: float = 0.2  # Wage belief smoothing
    reservation_markup_over_benefit: float = 1.1  # Reservation = benefit * 1.1
    default_price_level: float = 10.0  # Fallback when no price history
    min_cash_for_aggressive_job_search: float = 100.0  # Desperation threshold

    # Per-household randomized ranges for expectations and behaviors
    consumption_budget_share_range: Tuple[float, float] = (0.60, 0.80)
    quality_preference_weight_range: Tuple[float, float] = (0.6, 1.5)
    price_sensitivity_range: Tuple[float, float] = (0.6, 1.5)
    expected_wage_range: Tuple[float, float] = (7.0, 15.0)
    reservation_wage_range: Tuple[float, float] = (5.0, 12.0)
    price_expectation_alpha_range: Tuple[float, float] = (0.20, 0.45)
    wage_expectation_alpha_range: Tuple[float, float] = (0.12, 0.35)
    reservation_markup_range: Tuple[float, float] = (1.02, 1.20)
    min_cash_aggressive_search_range: Tuple[float, float] = (60.0, 180.0)
    skill_growth_rate_range: Tuple[float, float] = (0.0005, 0.002)
    initial_happiness_range: Tuple[float, float] = (0.60, 0.80)
    initial_morale_range: Tuple[float, float] = (0.60, 0.80)
    happiness_decay_rate_range: Tuple[float, float] = (0.0015, 0.0025)
    morale_decay_rate_range: Tuple[float, float] = (0.015, 0.025)

    # Labor Supply Planning
    desperate_wage_adjustment: float = 0.85  # Accept 15% less when desperate
    comfortable_reservation_mix_baseline: float = 0.7
    comfortable_reservation_mix_expected: float = 0.3

    # Wage Expectation Decay (Unemployed)
    duration_pressure_cap: float = 0.35
    duration_pressure_rate: float = 0.01
    happiness_pressure_cap: float = 0.3
    happiness_pressure_rate: float = 0.5
    happiness_threshold: float = 0.7
    base_wage_decay: float = 0.97
    min_decay_factor: float = 0.5
    wage_floor: float = 10.0
    unemployed_market_anchor_weight: float = 0.4
    unemployed_market_anchor_ticks: int = 8
    unemployed_market_anchor_offer_fraction: float = 0.98
    unemployed_market_anchor_percentile: float = 50.0
    reservation_adjustment_rate: float = 0.1

    # Skill Development
    skill_growth_rate: float = 0.001  # Passive improvement per tick
    education_cost_per_skill_point: float = 1000.0
    education_skill_gain_rate: float = 0.0001  # 0.1 skill per $1000

    # Affordability Scoring
    affordability_skill_component: float = 1.5
    affordability_cash_divisor: float = 400.0
    affordability_wage_divisor: float = 40.0
    affordability_skill_weight: float = 0.3
    affordability_cash_weight: float = 0.35
    affordability_wage_weight: float = 0.35
    affordability_min_score: float = 0.1
    affordability_max_score: float = 4.0

    # Price Cap Calculation
    min_liquid_cash: float = 25.0
    cash_liquidity_factor: float = 0.2
    base_cap_multiplier_1: float = 1.2
    base_cap_multiplier_2: float = 2.5
    median_cap_factor: float = 0.8
    affordability_premium_threshold: float = 2.0
    premium_liquid_multiplier: float = 1.2
    min_price_cap_buffer: float = 1.1

    # Consumption Adjustment
    price_cap_threshold: float = 0.85
    min_price_sensitivity: float = 0.2
    max_price_sensitivity: float = 1.5
    cap_ratio_scaling: float = 3.0
    min_quantity_scale: float = 0.15

    # Wellbeing Dynamics
    happiness_decay_rate: float = 0.002  # Reduced from 0.01 to prevent 0% happiness
    morale_decay_rate: float = 0.02
    health_decay_rate: float = 0.005

    # Wellbeing Updates - Employment (Feature 2: symmetric labor effects)
    employed_happiness_boost: float = 0.03   # Was 0.02; symmetric with unemployment
    unemployed_happiness_penalty: float = 0.003  # Per-tick penalty for unemployment (was 0.03 — unused; now used)

    # Wellbeing Updates - Relative wealth loss and food shortfall
    # Relative wealth-loss: losing X% of cash hurts regardless of absolute level
    wealth_loss_happiness_scaling: float = 0.01   # 10% cash loss → 0.001 happiness loss per tick
    # Food shortfall: not meeting minimum food requirement hurts proportionally
    food_shortfall_happiness_scaling: float = 0.003  # 100% food shortfall → 0.003 happiness loss per tick

    # Wellbeing Updates - Consumption (food/services/healthcare)
    food_health_high_threshold: float = 5.0
    food_health_mid_threshold: float = 2.0
    food_health_high_boost: float = 0.03
    food_health_mid_boost: float = 0.01
    food_starvation_penalty: float = 0.03
    food_health_decay_offset_share: float = 0.40
    service_happiness_base_boost_range: Tuple[float, float] = (0.006, 0.014)
    healthcare_preference_range: Tuple[float, float] = (0.8, 1.2)
    # Healthcare is modeled as a non-storable service (visits), not an inventory good.
    health_recovery_per_medical_unit: float = 0.02  # Legacy fallback for old paths
    healthcare_visit_base_heal: float = 0.18
    # Probabilistic healthcare demand:
    # annual chance = base_chance_pct + missing_health_pct, then spread over interval ticks.
    healthcare_request_base_chance_pct_range: Tuple[float, float] = (0.0, 50.0)
    healthcare_episode_max_visits: int = 6
    healthcare_followup_gap_max_ticks: int = 3
    healthcare_plan_interval_ticks: int = 52
    healthcare_visit_distribution_healthy: Tuple[Tuple[int, float], ...] = (
        (0, 0.30),
        (1, 0.40),
        (2, 0.30),
    )
    healthcare_visit_distribution_below_70: Tuple[Tuple[int, float], ...] = (
        (1, 0.30),
        (2, 0.40),
        (3, 0.30),
    )
    healthcare_visit_distribution_below_30: Tuple[Tuple[int, float], ...] = (
        (2, 0.30),
        (3, 0.40),
        (4, 0.30),
    )
    healthcare_visit_distribution_below_10: Tuple[Tuple[int, float], ...] = (
        (4, 0.50),
        (5, 0.45),
        (6, 0.05),
    )
    healthcare_worker_priority_health_threshold: float = 0.60
    medical_training_ticks: int = 52 * 4
    medical_residency_start_fraction: float = 0.5
    medical_resident_max_capacity: float = 0.5
    medical_doctor_capacity_range: Tuple[float, float] = (2.0, 3.0)
    medical_doctor_expected_wage_range: Tuple[float, float] = (70.0, 110.0)
    medical_doctor_reservation_wage_range: Tuple[float, float] = (45.0, 85.0)
    medical_school_total_cost: float = 220000.0
    medical_school_interest_rate_range: Tuple[float, float] = (0.04, 0.08)
    medical_school_repayment_share_of_wage: float = 0.12
    medical_school_min_payment: float = 5.0
    # Policy toggle: doctors self-stabilize health before shifts via peer consult.
    doctor_health_lock_enabled: bool = True
    doctor_health_lock_value: float = 1.0
    preventive_checkup_probability: float = 0.03
    followup_health_threshold: float = 0.75
    max_followup_visits: int = 3
    followup_interval_ticks: int = 2
    healthcare_urgency_threshold_range: Tuple[float, float] = (0.60, 0.80)
    healthcare_critical_threshold_range: Tuple[float, float] = (0.30, 0.50)
    morale_employed_boost_range: Tuple[float, float] = (0.02, 0.05)
    morale_unemployed_penalty_range: Tuple[float, float] = (0.02, 0.05)
    morale_unhoused_penalty_range: Tuple[float, float] = (0.02, 0.05)

    # Wellbeing Updates - Housing (Feature 2: reduced ongoing penalty)
    unhoused_happiness_penalty: float = 0.02  # Was 0.05; one-time eviction shock is separate

    # Wellbeing Updates - Poverty (Feature 1: exclusive if/elif, no stacking)
    extreme_poverty_threshold: float = 100.0
    extreme_poverty_penalty: float = 0.05
    poverty_threshold: float = 200.0
    poverty_penalty: float = 0.03

    # Wellbeing Updates - Government
    government_happiness_scaling: float = 0.05
    government_health_scaling: float = 0.03

    # Wellbeing Updates - Morale
    wage_satisfaction_boost: float = 0.03
    wage_dissatisfaction_scaling: float = 0.05
    unemployment_morale_penalty: float = 0.05

    # Wellbeing Updates - Health
    health_high_goods_threshold: float = 15.0
    health_low_goods_threshold: float = 5.0
    health_high_goods_boost: float = 0.01
    health_low_goods_penalty: float = 0.02

    # Feature 3: Mercy Floor
    mercy_floor_threshold: float = 0.25     # Below this, natural decay pauses

    # Performance Multiplier (Feature 4: raised floor from 0.5 to 0.75)
    performance_morale_weight: float = 0.5
    performance_health_weight: float = 0.3
    performance_happiness_weight: float = 0.2
    performance_min_multiplier: float = 0.75  # Was 0.5; prevents doom loop
    performance_max_multiplier: float = 1.5

    # Goods Consumption
    consumption_rate: float = 0.1  # 10% per tick
    housing_maintenance_rate: float = 0.01  # 1% per tick (10x faster - fixes housing glut)
    inventory_depletion_threshold: float = 0.001

    # Feature 1: Dynamic Desperation & Skill Hysteresis
    desperation_living_cost_buffer: float = 1.5  # Trigger desperation when cash < living_cost_floor * this
    desperation_wage_discount: float = 0.85  # Accept wages 15% lower when desperate
    skill_decay_unemployment_threshold: int = 26  # Ticks unemployed before skill decay starts (~6 months)
    skill_decay_rate_per_tick: float = 0.002  # Skill loss per tick when decaying
    skill_decay_floor: float = 0.1  # Minimum skill level (never decay below this)

    # Feature 2: Buffer-Stock Consumption Model
    target_wealth_income_ratio_base: float = 4.0  # Base target ratio (modified by thriftiness)
    buffer_stock_save_penalty: float = 0.6  # Spend fraction penalty when below target ratio
    buffer_stock_spend_bonus: float = 1.3  # Spend fraction multiplier when above target ratio

    # Feature 3: Bounded Rationality (Awareness Pool)
    awareness_pool_initial_size: int = 7  # Firms seen per category before organic discovery expands the pool
    awareness_pool_max_size: int = 10  # Max firms per category in awareness pool after discovery growth
    switching_friction_housing: float = 0.15  # 15% utility advantage needed to switch housing firm
    switching_friction_food: float = 0.02  # 2% utility advantage needed to switch food firm
    switching_friction_services: float = 0.05  # 5% utility advantage for services
    pool_refresh_interval: int = 4  # Refresh awareness pool every N ticks
    pool_refresh_drop_count: int = 1  # Number of lowest-utility firms to drop per refresh

    # Feature 4: Asymmetric Adaptive Expectations (Prospect Theory)
    price_alpha_up: float = 0.4  # Fast adjustment to price increases (loss aversion)
    price_alpha_down: float = 0.1  # Slow adjustment to price decreases

    # Deposit liquidity: fraction of bank_deposit treated as accessible for consumption planning
    household_deposit_access_rate: float = 0.90

    # Safety Checks
    extreme_negative_cash_threshold: float = -1e6


@dataclass
class FirmBehaviorConfig:
    """Firm behavioral parameters."""

    # Production & Technology
    default_expected_sales: float = 100.0
    default_production_capacity: float = 200.0
    default_productivity_per_worker: float = 10.0
    default_units_per_worker: float = 20.0
    services_units_per_worker_range: Tuple[float, float] = (1.0, 7.0)

    # Diminishing Returns / Productivity
    production_scaling_exponent: float = 0.9  # Legacy exponent (deprecated)
    diminishing_returns_exponent: float = 0.82  # Unified exponent for capacity/productivity (0.80-0.85)
    min_base_productivity: float = 1.0
    min_target_workers: int = 1
    expected_skill_premium: float = 0.3  # Anticipated wage premium over offer
    min_skeleton_workers: int = 3
    minimum_wage_floor: float = 20.0
    min_labor_share: float = 0.5
    max_labor_share: float = 0.8
    burn_mode_grace_period: int = 15
    high_inventory_factor_small: float = 1.5
    high_inventory_factor_large: float = 2.5
    burn_mode_trigger_streak_small: int = 5
    burn_mode_trigger_streak_large: int = 15
    burn_mode_exit_streak: int = 2
    inventory_exit_epsilon: float = 5.0
    min_expected_sales: float = 10.0
    large_market_inventory_relief: float = 1.3
    large_market_burn_mode_buffer: int = 5
    burn_mode_relief_rate: int = 2
    burn_mode_staff_reduction_factor: float = 0.65
    burn_mode_idle_production_fraction: float = 0.05
    target_labor_share: float = 0.65
    margin_low: float = 0.05
    margin_high: float = 0.20
    target_firms_per_1000_households: int = 30
    max_new_firms_per_tick: int = 10
    large_market_household_threshold: int = 2000
    housing_private_saturation_multiplier: float = 3.0
    min_private_firms_per_competing_sector: int = 2  # floor for food + services; prevents monopoly in small sims

    # Pricing & Costs
    default_unit_cost: float = 5.0
    default_markup: float = 0.3
    default_price: float = 6.5
    default_min_price: float = 5.0

    # PID Pricing (NEW - Prompt 3)
    target_inventory_weeks: float = 2.0  # Target weeks of supply
    days_per_week: float = 7.0
    pid_pressure_decay: float = 0.7  # Integral decay
    pid_integral_gain: float = 0.1  # Integral coefficient
    pid_control_scaling: float = 0.05  # Overall gain
    pid_adjustment_min: float = 0.80  # Max -20% price change
    pid_adjustment_max: float = 1.20  # Max +20% price change
    pid_min_margin: float = 1.05  # 5% above cost minimum
    pid_safety_epsilon: float = 1e-3

    # R&D and Quality
    default_rd_spending_rate: float = 0.05  # 5% of revenue
    quality_improvement_per_rd_dollar: float = 0.0002  # Slowed down 50x (was 0.01)
    quality_decay_rate: float = 0.0  # Quality decay removed
    quality_min: float = 0.0
    quality_max: float = 10.0

    # Adjustment Rates
    sales_expectation_alpha: float = 0.3
    price_adjustment_rate: float = 0.05
    wage_adjustment_rate: float = 0.1
    target_inventory_multiplier: float = 1.5

    # Lost-sales expectation controls. Lost sales are a real demand signal,
    # but noisy and capacity-constrained.
    lost_sales_expectation_weight: float = 0.65
    lost_sales_sustained_weight: float = 0.80
    lost_sales_sustained_ticks: int = 3
    lost_sales_completed_sales_cap: float = 1.50
    lost_sales_near_term_capacity_cap: float = 1.25

    # Expected-sales growth/decay controls. Prevent stockout feedback from
    # compounding expectations indefinitely.
    expected_sales_rising_alpha: float = 0.55
    expected_sales_growth_cap_per_tick: float = 1.25
    expected_sales_stockout_growth_cap_per_tick: float = 1.60
    expected_sales_sustained_stockout_growth_cap_per_tick: float = 2.00
    expected_sales_decay_floor_per_tick: float = 0.70

    # Market-size sanity caps. These scale with population, so they bound
    # impossible interpretations without injecting fake demand.
    expected_sales_observed_ratio_cap: float = 5.0
    expected_sales_market_cap_buffer: float = 1.50
    food_expected_units_per_household_cap: float = 8.0
    services_expected_units_per_household_cap: float = 4.0
    generic_expected_units_per_household_cap: float = 8.0

    # Adaptive hiring throughput, used only when demand is validated.
    adaptive_hiring_enabled: bool = True
    adaptive_hire_growth_fraction: float = 0.12
    adaptive_stockout_hire_growth_fraction: float = 0.20
    adaptive_hire_abs_cap: int = 12
    adaptive_stockout_min_hires: int = 4
    adaptive_hiring_min_cash_runway_ticks: float = 3.0

    # Wage-clearing response when planned vacancies fail because reservations
    # exceed offers.
    reservation_gap_raise_pass_through: float = 0.50
    reservation_gap_min_reject_count: int = 2
    reservation_gap_demand_sellthrough_floor: float = 0.80
    reservation_gap_inventory_weeks_ceiling: float = 2.0
    reservation_gap_max_wage_increase_per_tick: float = 1.25

    # Working-capital diagnostics and bridge credit.
    working_capital_enabled: bool = True
    working_capital_unemployment_trigger: float = 0.20
    working_capital_base_budget_per_tick: float = 15_000.0
    working_capital_budget_per_unemployment_rate: float = 70_000.0
    working_capital_max_budget_per_tick: float = 50_000.0
    working_capital_max_loan_per_firm: float = 12_000.0
    working_capital_min_lost_sales_units: float = 5.0
    working_capital_min_expected_gap_units: float = 10.0
    working_capital_min_sell_through: float = 0.65
    working_capital_max_inventory_weeks: float = 3.0
    working_capital_min_profit_margin: float = -0.10
    working_capital_min_mrpl_margin: float = 0.08
    working_capital_min_net_gain_per_tick: float = 25.0
    working_capital_debt_service_coverage: float = 1.25
    working_capital_term_ticks: int = 52
    working_capital_govt_rate: float = 0.02
    working_capital_spread: float = 0.03
    working_capital_support_ticks: int = 8
    working_capital_hire_fraction: float = 0.15
    working_capital_hire_abs_cap: int = 8
    working_capital_requires_existing_funding_capacity: bool = True

    # Survival-mode turnaround hiring. Disabled unless later credit-backed.
    survival_turnaround_enabled: bool = True
    survival_turnaround_min_lost_sales_units: float = 5.0
    survival_turnaround_min_sell_through: float = 0.70
    survival_turnaround_max_inventory_weeks: float = 2.5
    survival_turnaround_min_profit_margin: float = -0.05
    survival_turnaround_hire_abs_cap: int = 4

    # Hiring/Firing Constraints
    default_max_hires_per_tick: int = 2
    default_max_fires_per_tick: int = 2

    # Production Planning
    housing_saturation_threshold: float = 0.2  # 20% of households
    small_positive_production_floor: float = 10.0

    # Wage Planning
    hiring_success_threshold: float = 1.0
    successful_hiring_wage_reduction: float = 0.05
    no_pressure_wage_drift: float = 0.02
    minimum_wage: float = 1.0

    # Wage Stabilization (prevent explosive wage growth)
    max_wage_increase_per_tick: float = 1.15  # Max +15% per tick
    max_wage_decrease_per_tick: float = 0.85  # Max -15% per tick
    unemployment_damping_min: float = 0.3  # Minimum damping factor at high unemployment
    unemployment_damping_rate: float = 0.8  # How much unemployment reduces wage pressure

    # Dividend Distribution
    dividend_cost_reserve_ticks: float = 3.0  # Retain 3 ticks of costs
    dividend_min_safety_reserve: float = 10000.0

    # Feature 1: Emergency Restructuring (Anti-Zombie Firm)
    survival_mode_runway_weeks: float = 2.0  # Trigger survival mode when cash < run_rate * this
    survival_mode_min_layoff_fraction: float = 0.0  # No floor on layoffs in survival mode

    # Feature 2: Scalable Hiring (Proportional MRPL Search)
    mrpl_search_fractions: tuple = (0.05, 0.10)  # Search ±5% and ±10% of current workforce

    # Feature 3: Two-Stage Inventory Defense
    inventory_stage1_threshold: float = 1.5  # Stage 1 (cut production) at inventory > this × target
    inventory_stage1_labor_cut: float = 0.07  # Cut labor by 7% in Stage 1
    inventory_stage2_threshold: float = 3.0  # Stage 2 (cut price) at inventory > this × target
    inventory_stage2_price_cut_min: float = 0.05  # Min price cut in Stage 2
    inventory_stage2_price_cut_max: float = 0.10  # Max price cut in Stage 2

    # Healthcare service mode (queue + capacity, no inventory goods)
    healthcare_capacity_per_worker_default: float = 2.2
    healthcare_backlog_horizon_ticks: float = 6.0
    healthcare_arrivals_ema_alpha: float = 0.2
    healthcare_downsize_idle_ticks: int = 12
    healthcare_baseline_min_workers: int = 2
    healthcare_max_hires_per_tick: int = 6
    healthcare_price_pressure_target: float = 1.0
    healthcare_price_increase_rate: float = 0.06
    healthcare_price_decrease_rate: float = 0.03
    healthcare_price_ceiling_multiplier: float = 6.0
    healthcare_target_profit_margin: float = 0.15
    healthcare_staff_population_ratio: float = 0.02   # 2% of households are doctors (economy-wide)
    healthcare_training_enrollment_interval_ticks: int = 52
    healthcare_training_enrollment_interval_after_cap_ticks: int = 104
    healthcare_training_fast_track_cap: int = 10
    # Keep healthcare provider count intentionally sparse so queue/backlog dynamics stay meaningful.
    healthcare_households_per_firm_target: int = 800

    # Fix 21: Capital Stock (two-factor Cobb-Douglas production)
    initial_firm_capital: float = 15.0        # Starting capital units per firm
    capital_depreciation_rate: float = 0.01   # 1% per tick (~70-tick half-life)
    capital_cost_per_unit: float = 500.0      # $ per unit of capital
    alpha_k: float = 0.25                     # Capital share exponent
    alpha_n: float = 0.65                     # Labor share exponent

    # Long-term capital expansion loans (services + housing only).
    # Real-economy framing: SBA-style equipment / real-estate financing. Long
    # term so per-tick payment is small (does not crush operating cash flow),
    # low interest because bank is putting excess reserves to work. Services
    # use the loan to lift production_capacity_units (more workers fit, more
    # output). Housing use the loan to add max_rental_units (construction)
    # which then requires proportionally more property managers.
    long_term_capital_loans_enabled: bool = True
    long_term_capital_term_ticks: int = 520           # ~10 years
    long_term_capital_annual_rate: float = 0.025      # 2.5% baseline
    long_term_capital_min_amount: float = 5_000.0
    long_term_capital_max_amount: float = 25_000.0
    long_term_capital_unemployment_trigger: float = 0.10
    long_term_capital_cooldown_ticks: int = 26        # 6-month cooldown per firm
    services_capacity_cost_per_unit: float = 500.0    # services: $500 per capacity unit
    housing_rental_unit_construction_cost: float = 2_000.0  # housing: $2k per unit
    housing_units_per_property_manager: int = 20       # 1 PM per 20 rental units

    # Feature 4: Pro-Cyclical R&D Strategy
    rd_base_rate: float = 0.05  # Base R&D spending as fraction of revenue
    rd_max_rate: float = 0.10  # Maximum R&D spending rate at high margins
    rd_margin_scaling: float = 0.5  # How much margin boosts R&D above base

    # Per-firm randomized ranges for behavioral traits (sampled once at init)
    sales_expectation_alpha_range: Tuple[float, float] = (0.20, 0.40)
    target_inventory_multiplier_range: Tuple[float, float] = (1.2, 1.8)
    target_inventory_weeks_range: Tuple[float, float] = (1.5, 3.0)
    min_price_range: Tuple[float, float] = (3.0, 6.0)
    quality_improvement_per_rd_dollar_range: Tuple[float, float] = (0.0001, 0.0004)
    markup_range: Tuple[float, float] = (0.20, 0.40)
    unit_cost_range: Tuple[float, float] = (4.0, 6.5)

    # Personality trait ranges (sampled once per firm at initialization)
    aggressive_investment_propensity_range: Tuple[float, float] = (0.12, 0.18)
    aggressive_risk_tolerance_range: Tuple[float, float] = (0.82, 0.95)
    aggressive_price_adjustment_range: Tuple[float, float] = (0.08, 0.12)
    aggressive_wage_adjustment_range: Tuple[float, float] = (0.12, 0.18)
    aggressive_rd_spending_range: Tuple[float, float] = (0.06, 0.10)
    aggressive_max_hires_range: Tuple[int, int] = (3, 3)
    aggressive_max_fires_range: Tuple[int, int] = (3, 3)
    aggressive_units_per_worker_range: Tuple[float, float] = (16.0, 20.0)

    conservative_investment_propensity_range: Tuple[float, float] = (0.01, 0.04)
    conservative_risk_tolerance_range: Tuple[float, float] = (0.10, 0.30)
    conservative_price_adjustment_range: Tuple[float, float] = (0.01, 0.04)
    conservative_wage_adjustment_range: Tuple[float, float] = (0.04, 0.07)
    conservative_rd_spending_range: Tuple[float, float] = (0.01, 0.04)
    conservative_max_hires_range: Tuple[int, int] = (1, 1)
    conservative_max_fires_range: Tuple[int, int] = (1, 1)
    conservative_units_per_worker_range: Tuple[float, float] = (23.0, 27.0)

    moderate_investment_propensity_range: Tuple[float, float] = (0.04, 0.07)
    moderate_risk_tolerance_range: Tuple[float, float] = (0.40, 0.60)
    moderate_price_adjustment_range: Tuple[float, float] = (0.04, 0.07)
    moderate_wage_adjustment_range: Tuple[float, float] = (0.08, 0.12)
    moderate_rd_spending_range: Tuple[float, float] = (0.04, 0.07)
    moderate_max_hires_range: Tuple[int, int] = (2, 2)
    moderate_max_fires_range: Tuple[int, int] = (2, 2)
    moderate_units_per_worker_range: Tuple[float, float] = (19.0, 22.0)

    # Housing mortgage underwriting (DSCR/LTV amortizing loan system)
    housing_loan_term_ticks: int = 1040        # 20 years × 52 ticks/year
    housing_min_dscr: float = 1.20             # Minimum debt-service coverage ratio
    housing_max_ltv: float = 0.80              # Maximum loan-to-value ratio
    housing_vacancy_buffer: float = 0.95       # Revenue projection conservatism factor
    housing_max_build_per_tick: int = 2        # Max units built per tick via loan
    housing_unit_market_value: float = 20_000.0  # Collateral value per rental unit

    # Phillips Curve wage algorithm
    nairu_threshold: float = 0.05       # Unemployment rate below which labor is scarce
    unemployment_ma_window: int = 4     # Ticks in short-term unemployment moving average


@dataclass
class GovernmentPolicyConfig:
    """Government policy parameters."""

    # Tax & Transfer Rates
    default_wage_tax_rate: float = 0.15
    default_profit_tax_rate: float = 0.20
    default_investment_tax_rate: float = 0.10  # Tax on R&D and capital investments
    default_unemployment_benefit: float = 15.0  # Reduced from 30.0 to incentivize work over welfare
    default_min_cash_threshold: float = 100.0
    default_transfer_budget: float = 10000.0

    # Wage Floor Policy (minimum wage tied to unemployment benefit)
    wage_floor_multiplier: float = 1.0  # Minimum wage = unemployment_benefit × 1.0 (reduced from 1.2)

    # Investment Budgets
    # Infrastructure and technology investment disabled — additional production
    # capacity just creates unsold stockpiles without demand-side support.
    infrastructure_investment_budget: float = 0.0
    technology_investment_budget: float = 0.0
    social_investment_budget: float = 750.0
    investment_reserve_threshold: float = 10000.0  # Don't invest below this

    # Economic Multipliers (Initial)
    initial_infrastructure_multiplier: float = 1.0
    initial_technology_multiplier: float = 1.0
    initial_social_multiplier: float = 1.0
    infra_multiplier_target: float = 1.5
    social_multiplier_target: float = 1.5
    infra_multiplier_hard_cap: float = 2.0
    social_multiplier_hard_cap: float = 2.0
    investment_speed: float = 0.02
    unemployment_cutoff_for_investment: float = 0.3
    emergency_loan_trigger: float = 0.08
    emergency_loan_amount: float = 75000.0
    emergency_loan_cash_threshold: float = 40000.0
    emergency_loan_interest: float = 0.01
    emergency_loan_fraction_of_cash: float = 0.05
    emergency_loan_term_years: float = 2.0
    emergency_loan_required_headcount_multiplier: float = 1.3
    emergency_loan_min_headcount: int = 12
    emergency_loan_enforcement_ticks: int = 26
    emergency_loan_penalty_reclaim_fraction: float = 1.0
    public_works_unemployment_threshold: float = 0.25
    public_works_job_fraction: float = 0.2
    public_works_wage: float = 45.0
    public_works_price: float = 1.0

    # Investment Effects
    infrastructure_gain_divisor: float = 1000.0  # $1000 → 0.5% productivity
    infrastructure_gain_rate: float = 0.005
    technology_gain_divisor: float = 500.0  # $500 → 0.5% quality
    technology_gain_rate: float = 0.005
    technology_max_multiplier: float = 1.05  # Cap at 5% improvement
    social_gain_divisor: float = 15000.0
    social_gain_rate: float = 0.005
    social_program_health_scaling: float = 1.0
    healthcare_visit_subsidy_share: float = 0.0

    # Policy Adjustment - Unemployment Thresholds
    high_unemployment_threshold: float = 0.15  # 15%
    low_unemployment_threshold: float = 0.03  # 3%
    high_unemployment_benefit_max: float = 50.0
    high_unemployment_transfer_max: float = 20000.0
    high_unemployment_benefit_increase: float = 1.05
    high_unemployment_transfer_increase: float = 1.1
    low_unemployment_benefit_min: float = 20.0
    low_unemployment_benefit_decrease: float = 0.98

    # Policy Adjustment - Deficit Thresholds
    large_deficit_threshold: float = -10000.0
    large_surplus_threshold: float = 50000.0
    deficit_wage_tax_max: float = 0.30
    deficit_profit_tax_max: float = 0.35
    deficit_tax_increase: float = 1.02
    surplus_wage_tax_min: float = 0.05
    surplus_profit_tax_min: float = 0.10
    surplus_tax_decrease: float = 0.98

    # Policy Adjustment - Counter-Cyclical Transfers
    recession_unemployment_threshold: float = 0.10
    recession_transfer_max: float = 30000.0
    recession_transfer_increase: float = 1.05
    boom_unemployment_threshold: float = 0.05
    boom_cash_threshold: float = 20000.0
    boom_transfer_min: float = 5000.0
    boom_transfer_decrease: float = 0.98

    # Working-capital backstop diagnostics. This is not deficit financing.
    auto_working_capital_backstop: bool = True
    working_capital_backstop_reserve_floor: float = 5_000.0

    # Recession guardrails; warning is observation-only, floor can be enforced later.
    recession_policy_floor_unemployment_threshold: float = 0.30
    recession_policy_warning_unemployment_threshold: float = 0.20

    # Labor-force accounting.
    count_cannot_work_as_unemployed: bool = False

    # Off until diagnostics show health is the blocker.
    health_recovery_stabilizer_enabled: bool = False

    # Soft price stabilization. These cap upward movement only; they are not
    # hard price ceilings and never force below current cost/minimum floors.
    price_stabilization_soft_max_increase: float = 1.03
    price_stabilization_strict_max_increase: float = 1.01
    rent_stabilization_soft_max_increase: float = 1.02
    rent_stabilization_strict_max_increase: float = 1.005


@dataclass
class LaborMarketConfig:
    """Labor market matching parameters."""

    # Wage Percentile Caching
    wage_percentile_cache_interval: int = 5  # Refresh every 5 ticks
    wage_percentile_low: int = 25
    wage_percentile_mid: int = 50
    wage_percentile_high: int = 75

    # Skill-Based Wage Anchoring
    low_skill_threshold: float = 0.4
    high_skill_threshold: float = 0.7

    # Experience & Skill Premiums
    max_skill_premium: float = 0.5  # 50% max for skills
    max_experience_premium: float = 0.5  # 50% max for experience
    experience_premium_per_year: float = 0.05  # 5% per year

    # Production Experience Bonuses
    max_skill_bonus: float = 0.25  # 25% productivity from skills
    experience_bonus_per_year: float = 0.05  # 5% per year

    # Regulatory
    minimum_wage_floor: float = 20.0

    # Housing Market
    rent_affordability_share: float = 0.30  # Max share of income for rent
    rent_floor: float = 50.0  # Kept for backward compatibility — not used in equilibrium logic
    rent_floor_absolute_min: float = 10.0  # Hard floor; dynamic floor = p25_wage * rent_affordability_share
    rent_increase_high_occupancy: float = 1.02  # Rent change when >95% occupied
    rent_increase_good_occupancy: float = 1.01  # Rent change when 80-95% occupied
    rent_decrease_moderate_vacancy: float = 0.98  # Rent change when 50-70% occupied
    rent_decrease_high_vacancy: float = 0.95  # Rent change when <50% occupied
    occupancy_high_threshold: float = 0.95
    occupancy_good_threshold: float = 0.80
    occupancy_moderate_threshold: float = 0.70
    occupancy_low_threshold: float = 0.50
    rent_shortage_multiplier: float = 1.05  # Extra increase during housing shortage
    rent_shortage_interval_ticks: int = 13  # How often shortage premium applies


@dataclass
class MarketMechanicsConfig:
    """Market clearing and pricing mechanisms."""

    # Price Ceiling Tax
    price_ceiling: float = 50.0
    price_ceiling_tax_rate: float = 0.25  # 25% on excess revenue

    # Firm Exit/Entry
    bankruptcy_threshold: float = -1000.0
    zero_cash_max_streak: int = 12  # Ticks at zero/negative cash before exit
    max_private_competitors: int = 5
    new_firm_demand_threshold: float = 1000.0  # Min household cash

    # New Firm Initialization
    new_firm_initial_cash: float = 2000.0
    new_firm_initial_inventory: float = 25.0
    new_firm_initial_wage: float = 35.0
    new_firm_initial_price: float = 8.0
    new_firm_initial_expected_sales: float = 20.0
    new_firm_initial_capacity: float = 200.0
    new_firm_initial_productivity: float = 8.0
    new_firm_initial_units_per_worker: float = 15.0


@dataclass
class DebugConfig:
    """Debug and anomaly detection settings."""

    # H4: Household income anomaly detection
    large_household_net_change: float = 10000.0  # Flag cash changes above this threshold
    enable_income_tracking: bool = True  # Track wage/transfer/dividend breakdown
    log_large_changes: bool = False  # Log anomalous household income changes


@dataclass
class SimulationModeConfig:
    """Feature toggles for experimentation."""
    stabilization_enabled: bool = True
    household_stabilizers: bool = True
    firm_stabilizers: bool = True
    government_stabilizers: bool = True


@dataclass
class LLMConfig:
    """LLM integration settings for AI-driven agents."""

    # Provider selection
    provider: str = "lmstudio"  # "ollama" | "lmstudio" | "openrouter" | "groq"
    ollama_base_url: str = "http://localhost:11434"
    # Any OpenAI-compatible local chat server, including LM Studio or llama.cpp.
    lmstudio_base_url: str = "http://127.0.0.1:8080"

    # Model selection per role
    government_model: str = "microsoft/phi-4-mini-reasoning"
    rag_model: str = "microsoft/phi-4-mini-reasoning"
    agent_model: str = "microsoft/phi-4-mini-reasoning"
    openrouter_model: str = "nvidia/nemotron-nano-9b-v2:free"
    groq_model: str = "llama-3.3-70b-versatile"

    # Government LLM agent
    enable_llm_government: bool = False  # opt-in, simulation works without
    government_start_tick: int = 15
    government_start_after_warmup_ticks: int = 5
    government_decision_interval: int = 26
    government_temperature: float = 0.1
    government_top_p: float = 0.8
    government_max_tokens: int = 1200
    government_philosophy: str = "capitalist"  # system prompt flavor
    government_history_window: int = 6  # recent decision cycles shown to the model
    government_impact_horizon: int = 26  # ticks used to evaluate post-policy changes
    government_rolling_windows_ticks: Tuple[int, ...] = (13, 26, 52)

    # Future: LLM-controlled household/firm agents
    enable_llm_agents: bool = False


@dataclass
class SimulationConfig:
    """Master configuration for the entire simulation."""

    # Sub-configurations
    time: TimeConfig = field(default_factory=TimeConfig)
    households: HouseholdBehaviorConfig = field(default_factory=HouseholdBehaviorConfig)
    firms: FirmBehaviorConfig = field(default_factory=FirmBehaviorConfig)
    government: GovernmentPolicyConfig = field(default_factory=GovernmentPolicyConfig)
    labor_market: LaborMarketConfig = field(default_factory=LaborMarketConfig)
    market: MarketMechanicsConfig = field(default_factory=MarketMechanicsConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    modes: SimulationModeConfig = field(default_factory=SimulationModeConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Simulation Scale (Legacy - kept for backward compatibility)
    num_households: int = 10000
    num_firms: int = 100
    random_seed: int = 42
    baseline_prices: Dict[str, float] = field(default_factory=lambda: {
        "Food": 8.0,
        "Housing": 20.0,
        "Services": 10.0,
        "Healthcare": 15.0,
    })

    # Initial Distributions (Legacy)
    initial_cash_min: float = 1000.0
    initial_cash_max: float = 2000.0
    initial_skills_min: float = 0.1
    initial_skills_max: float = 0.9

    def __post_init__(self):
        """Validation and derived values."""
        # Validate time parameters
        if self.time.ticks_per_year <= 0:
            raise ValueError("ticks_per_year must be positive")
        if self.time.warmup_ticks < 0:
            raise ValueError("warmup_ticks cannot be negative")

        # Validate bounds
        if not (0.0 <= self.households.min_savings_rate <= 1.0):
            raise ValueError("min_savings_rate must be in [0, 1]")
        if not (0.0 <= self.households.max_savings_rate <= 1.0):
            raise ValueError("max_savings_rate must be in [0, 1]")
        if self.households.min_savings_rate > self.households.max_savings_rate:
            raise ValueError("min_savings_rate must be <= max_savings_rate")

        # Validate elasticities (should be positive)
        if self.households.food_elasticity < 0:
            raise ValueError("food_elasticity must be non-negative")
        if self.households.services_elasticity < 0:
            raise ValueError("services_elasticity must be non-negative")

        # Validate range tuples (low <= high)
        for name, (lo, hi) in [
            ("spending_tendency_range", self.households.spending_tendency_range),
            ("frugality_range", self.households.frugality_range),
            ("health_decay_low_range", self.households.health_decay_low_range),
            ("health_decay_mid_range", self.households.health_decay_mid_range),
            ("health_decay_high_range", self.households.health_decay_high_range),
        ]:
            if lo > hi:
                raise ValueError(f"{name} low ({lo}) must be <= high ({hi})")


# Global configuration instance
CONFIG = SimulationConfig()
