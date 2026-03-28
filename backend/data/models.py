"""Typed warehouse row models for EcoSim persistence backends."""

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class SimulationRun:
    """Represents one simulation run."""
    run_id: str
    status: str = "running"
    seed: Optional[int] = None
    num_households: int = 0
    num_firms: int = 0
    total_ticks: int = 0
    created_at: Optional[str] = None
    ended_at: Optional[str] = None
    final_gdp: Optional[float] = None
    final_unemployment: Optional[float] = None
    final_gini: Optional[float] = None
    final_avg_happiness: Optional[float] = None
    final_avg_health: Optional[float] = None
    final_gov_balance: Optional[float] = None
    config_json: Optional[str] = None
    code_version: Optional[str] = None
    schema_version: Optional[str] = None
    decision_feature_version: Optional[str] = None
    diagnostics_version: Optional[str] = None
    last_fully_persisted_tick: int = 0
    analysis_ready: bool = False
    termination_reason: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TickMetrics:
    """Represents aggregate metrics for a single tick."""
    run_id: str
    tick: int
    gdp: float
    unemployment_rate: float
    mean_wage: float
    median_wage: float
    avg_happiness: float
    avg_health: float
    avg_morale: float
    total_net_worth: float
    gini_coefficient: float
    top10_wealth_share: float
    bottom50_wealth_share: float
    gov_cash_balance: float
    gov_profit: float
    total_firms: int
    struggling_firms: int
    tick_duration_ms: Optional[float] = None
    labor_force_participation: Optional[float] = None
    open_vacancies: Optional[int] = None
    total_hires: Optional[int] = None
    total_layoffs: Optional[int] = None
    healthcare_queue_depth: Optional[int] = None
    avg_food_price: Optional[float] = None
    avg_housing_price: Optional[float] = None
    avg_services_price: Optional[float] = None


@dataclass
class SectorTickMetrics:
    """Represents per-sector aggregates for a single tick."""
    run_id: str
    tick: int
    sector: str
    firm_count: int
    employees: int
    vacancies: int
    mean_wage_offer: float
    mean_price: float
    mean_inventory: float
    total_output: float
    total_revenue: float
    total_profit: float


@dataclass
class FirmSnapshot:
    """Represents one firm's analytical state at a single tick."""
    run_id: str
    tick: int
    firm_id: int
    firm_name: str
    sector: str
    is_baseline: bool
    employee_count: int
    doctor_employee_count: int
    medical_employee_count: int
    planned_hires_count: int
    planned_layoffs_count: int
    actual_hires_count: int
    wage_offer: float
    price: float
    inventory_units: float
    output_units: float
    cash_balance: float
    revenue: float
    profit: float
    quality_level: float
    queue_depth: int
    visits_completed: float
    burn_mode: bool
    zero_cash_streak: int


@dataclass
class HouseholdSnapshot:
    """Represents one sampled household-state row."""
    run_id: str
    tick: int
    household_id: int
    state: str
    medical_status: str
    employer_id: Optional[int]
    is_employed: bool
    can_work: bool
    cash_balance: float
    wage: float
    last_wage_income: float
    last_transfer_income: float
    last_dividend_income: float
    reservation_wage: float
    expected_wage: float
    skill_level: float
    health: float
    happiness: float
    morale: float
    food_security: float
    housing_security: bool
    unemployment_duration: int
    pending_healthcare_visits: int


@dataclass
class TrackedHouseholdHistory:
    """Represents one tracked-household row captured every tick."""
    run_id: str
    tick: int
    household_id: int
    state: str
    medical_status: str
    employer_id: Optional[int]
    is_employed: bool
    can_work: bool
    cash_balance: float
    wage: float
    expected_wage: float
    reservation_wage: float
    health: float
    happiness: float
    morale: float
    skill_level: float
    unemployment_duration: int
    pending_healthcare_visits: int


@dataclass
class DecisionFeature:
    """Represents one per-tick compact decision-context row."""
    run_id: str
    tick: int
    unemployment_short_ma: float
    unemployment_long_ma: float
    inflation_short_ma: float
    hiring_momentum: float
    layoff_momentum: float
    vacancy_fill_ratio: float
    wage_pressure: float
    healthcare_pressure: float
    consumer_distress_score: float
    fiscal_stress_score: float
    inequality_pressure_score: float


@dataclass
class TickDiagnostic:
    """Represents one compact, policy-relevant explanation row per tick."""
    run_id: str
    tick: int
    unemployment_change_pp: float
    unemployment_primary_driver: str
    layoffs_count: int
    hires_count: int
    failed_hiring_firm_count: int
    failed_hiring_roles_count: int
    wage_mismatch_seeker_count: int
    health_blocked_worker_count: int
    inactive_work_capable_count: int
    avg_health_change_pp: float
    health_primary_driver: str
    low_health_share: float
    food_insecure_share: float
    cash_stressed_share: float
    pending_healthcare_visits_total: int
    healthcare_queue_depth: int
    healthcare_completed_count: int
    healthcare_denied_count: int
    firm_distress_primary_driver: str
    burn_mode_firm_count: int
    survival_mode_firm_count: int
    zero_cash_firm_count: int
    weak_demand_firm_count: int
    inventory_pressure_firm_count: int
    bankruptcy_count: int
    housing_primary_driver: str
    eviction_count: int
    housing_failure_count: int
    housing_unaffordable_count: int
    housing_no_supply_count: int
    homeless_household_count: int
    shortage_active_sector_count: int


@dataclass
class SectorShortageDiagnostic:
    """Represents one sector-level shortage pressure row for a tick."""
    run_id: str
    tick: int
    sector: str
    shortage_active: bool
    shortage_severity: float
    primary_driver: str
    mean_sell_through_rate: float
    vacancy_pressure: float
    inventory_pressure: float
    price_pressure: float
    queue_pressure: float
    occupancy_pressure: float


@dataclass
class RegimeEvent:
    """Represents a high-value regime/state transition event."""
    run_id: str
    tick: int
    event_type: str
    entity_type: str
    entity_id: Optional[int] = None
    sector: Optional[str] = None
    reason_code: Optional[str] = None
    severity: Optional[float] = None
    metric_value: Optional[float] = None
    payload_json: Optional[str] = None
    event_key: Optional[str] = None


@dataclass
class LaborEvent:
    """Represents a labor-market event."""
    run_id: str
    tick: int
    household_id: int
    firm_id: int
    event_type: str
    actual_wage: Optional[float] = None
    wage_offer: Optional[float] = None
    reservation_wage: Optional[float] = None
    skill_level: Optional[float] = None
    event_key: Optional[str] = None


@dataclass
class HealthcareEvent:
    """Represents a healthcare service event."""
    run_id: str
    tick: int
    household_id: int
    firm_id: int
    event_type: str
    queue_wait_ticks: Optional[int] = None
    visit_price: Optional[float] = None
    household_cost: Optional[float] = None
    government_cost: Optional[float] = None
    health_before: Optional[float] = None
    health_after: Optional[float] = None
    event_key: Optional[str] = None


@dataclass
class PolicyAction:
    """Represents a user-driven or automatic policy change."""
    run_id: str
    tick: int
    actor: str
    action_type: str
    payload_json: str
    reason_summary: Optional[str] = None
    event_key: Optional[str] = None


@dataclass
class PolicyConfig:
    """Represents policy configuration."""
    run_id: str
    wage_tax: float
    profit_tax: float
    wealth_tax_rate: float
    wealth_tax_threshold: float
    universal_basic_income: float
    unemployment_benefit_rate: float
    minimum_wage: float
    inflation_rate: float
    birth_rate: float
    agent_stabilizers_enabled: bool = False
