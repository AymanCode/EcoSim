-- EcoSim Data Warehouse Schema
-- Warehouse schema with run, aggregate, snapshot, event, and policy tables

-- =============================================================================
-- Table 1: simulation_runs
-- Stores metadata for each simulation run
-- =============================================================================
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'stopped')) DEFAULT 'running',

    -- Configuration
    seed INTEGER,
    num_households INTEGER,
    num_firms INTEGER,
    total_ticks INTEGER DEFAULT 0,

    -- Final outcomes (populated when simulation completes)
    final_gdp REAL,
    final_unemployment REAL,
    final_gini REAL,
    final_avg_happiness REAL,
    final_avg_health REAL,
    final_gov_balance REAL,
    config_json TEXT,
    code_version TEXT,
    schema_version TEXT,
    decision_feature_version TEXT,
    diagnostics_version TEXT,
    last_fully_persisted_tick INTEGER DEFAULT 0,
    analysis_ready BOOLEAN DEFAULT 0,
    termination_reason TEXT,

    -- Metadata
    description TEXT,
    tags TEXT  -- Comma-separated tags for categorization
);

CREATE INDEX IF NOT EXISTS idx_runs_created ON simulation_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON simulation_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_tags ON simulation_runs(tags);

-- =============================================================================
-- Table 2: tick_metrics
-- Stores economic metrics at each simulation tick
-- =============================================================================
CREATE TABLE IF NOT EXISTS tick_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Economic indicators
    gdp REAL,
    unemployment_rate REAL,
    mean_wage REAL,
    median_wage REAL,

    -- Wellbeing
    avg_happiness REAL,
    avg_health REAL,
    avg_morale REAL,

    -- Wealth & Inequality
    total_net_worth REAL,
    gini_coefficient REAL,
    top10_wealth_share REAL,
    bottom50_wealth_share REAL,

    -- Government
    gov_cash_balance REAL,
    gov_profit REAL,

    -- Runtime / labor
    tick_duration_ms REAL,
    labor_force_participation REAL,
    open_vacancies INTEGER,
    total_hires INTEGER,
    total_layoffs INTEGER,
    healthcare_queue_depth INTEGER,

    -- Market
    total_firms INTEGER,
    struggling_firms INTEGER,

    -- Prices (averaged across categories)
    avg_food_price REAL,
    avg_housing_price REAL,
    avg_services_price REAL,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, tick)
);

-- Critical indexes for time-series queries
CREATE INDEX IF NOT EXISTS idx_metrics_run ON tick_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_metrics_run_tick ON tick_metrics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_metrics_tick ON tick_metrics(tick);

-- =============================================================================
-- Table 2b: sector_tick_metrics
-- Stores per-sector aggregates at each simulation tick
-- =============================================================================
CREATE TABLE IF NOT EXISTS sector_tick_metrics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    sector TEXT NOT NULL,

    firm_count INTEGER,
    employees INTEGER,
    vacancies INTEGER,
    mean_wage_offer REAL,
    mean_price REAL,
    mean_inventory REAL,
    total_output REAL,
    total_revenue REAL,
    total_profit REAL,

    PRIMARY KEY (run_id, tick, sector),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_tick ON sector_tick_metrics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_sector_tick ON sector_tick_metrics(run_id, sector, tick);

-- =============================================================================
-- Table 3: firm_snapshots
-- Stores one analytical firm-state row per tick
-- =============================================================================
CREATE TABLE IF NOT EXISTS firm_snapshots (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,
    firm_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    is_baseline BOOLEAN DEFAULT 0,
    employee_count INTEGER,
    doctor_employee_count INTEGER,
    medical_employee_count INTEGER,
    planned_hires_count INTEGER,
    planned_layoffs_count INTEGER,
    actual_hires_count INTEGER,
    wage_offer REAL,
    price REAL,
    inventory_units REAL,
    output_units REAL,
    cash_balance REAL,
    revenue REAL,
    profit REAL,
    quality_level REAL,
    queue_depth INTEGER,
    visits_completed REAL,
    burn_mode BOOLEAN DEFAULT 0,
    zero_cash_streak INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (run_id, tick, firm_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_tick ON firm_snapshots(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_firm_tick ON firm_snapshots(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_sector_tick ON firm_snapshots(run_id, sector, tick);

-- =============================================================================
-- Table 4: household_snapshots
-- Stores sampled household-state rows (default cadence: every 5 ticks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS household_snapshots (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    household_id INTEGER NOT NULL,
    state TEXT NOT NULL,
    medical_status TEXT NOT NULL,
    employer_id INTEGER,
    is_employed BOOLEAN DEFAULT 0,
    can_work BOOLEAN DEFAULT 0,
    cash_balance REAL,
    wage REAL,
    last_wage_income REAL,
    last_transfer_income REAL,
    last_dividend_income REAL,
    reservation_wage REAL,
    expected_wage REAL,
    skill_level REAL,
    health REAL,
    happiness REAL,
    morale REAL,
    food_security REAL,
    housing_security BOOLEAN DEFAULT 0,
    unemployment_duration INTEGER,
    pending_healthcare_visits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (run_id, tick, household_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_tick ON household_snapshots(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_household_tick ON household_snapshots(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_state_tick ON household_snapshots(run_id, state, tick);

-- =============================================================================
-- Table 5: tracked_household_history
-- Stores every-tick rows for the small tracked-household subset
-- =============================================================================
CREATE TABLE IF NOT EXISTS tracked_household_history (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    household_id INTEGER NOT NULL,
    state TEXT NOT NULL,
    medical_status TEXT NOT NULL,
    employer_id INTEGER,
    is_employed BOOLEAN DEFAULT 0,
    can_work BOOLEAN DEFAULT 0,
    cash_balance REAL,
    wage REAL,
    expected_wage REAL,
    reservation_wage REAL,
    health REAL,
    happiness REAL,
    morale REAL,
    skill_level REAL,
    unemployment_duration INTEGER,
    pending_healthcare_visits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (run_id, tick, household_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tracked_household_history_run_tick ON tracked_household_history(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_tracked_household_history_run_household_tick ON tracked_household_history(run_id, household_id, tick);

-- =============================================================================
-- Table 6: labor_events
-- Stores append-only labor market events
-- =============================================================================
CREATE TABLE IF NOT EXISTS labor_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL,
    household_id INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actual_wage REAL,
    wage_offer REAL,
    reservation_wage REAL,
    skill_level REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_labor_events_run_tick ON labor_events(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_labor_events_run_event_key ON labor_events(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_household_tick ON labor_events(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_firm_tick ON labor_events(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_type_tick ON labor_events(run_id, event_type, tick);

-- =============================================================================
-- Table 7: healthcare_events
-- Stores append-only healthcare service events
-- =============================================================================
CREATE TABLE IF NOT EXISTS healthcare_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL,
    household_id INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    queue_wait_ticks INTEGER,
    visit_price REAL,
    household_cost REAL,
    government_cost REAL,
    health_before REAL,
    health_after REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_tick ON healthcare_events(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_healthcare_events_run_event_key ON healthcare_events(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_household_tick ON healthcare_events(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_firm_tick ON healthcare_events(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_type_tick ON healthcare_events(run_id, event_type, tick);

-- =============================================================================
-- Table 8: policy_actions
-- Stores append-only policy changes and decisions
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL,
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    reason_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_actions_run_tick ON policy_actions(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_policy_actions_run_event_key ON policy_actions(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_policy_actions_run_type_tick ON policy_actions(run_id, action_type, tick);

-- =============================================================================
-- Table 9: decision_features
-- Stores compact per-tick decision context for policy / LLM use
-- =============================================================================
CREATE TABLE IF NOT EXISTS decision_features (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    unemployment_short_ma REAL NOT NULL,
    unemployment_long_ma REAL NOT NULL,
    inflation_short_ma REAL NOT NULL,
    hiring_momentum REAL NOT NULL,
    layoff_momentum REAL NOT NULL,
    vacancy_fill_ratio REAL NOT NULL,
    wage_pressure REAL NOT NULL,
    healthcare_pressure REAL NOT NULL,
    consumer_distress_score REAL NOT NULL,
    fiscal_stress_score REAL NOT NULL,
    inequality_pressure_score REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, tick),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decision_features_run_tick ON decision_features(run_id, tick);

-- =============================================================================
-- Table 10: tick_diagnostics
-- Stores compact per-tick diagnostic explanations for policy/debug use
-- =============================================================================
CREATE TABLE IF NOT EXISTS tick_diagnostics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    unemployment_change_pp REAL NOT NULL,
    unemployment_primary_driver TEXT NOT NULL,
    layoffs_count INTEGER NOT NULL,
    hires_count INTEGER NOT NULL,
    failed_hiring_firm_count INTEGER NOT NULL,
    failed_hiring_roles_count INTEGER NOT NULL,
    wage_mismatch_seeker_count INTEGER NOT NULL,
    health_blocked_worker_count INTEGER NOT NULL,
    inactive_work_capable_count INTEGER NOT NULL,
    avg_health_change_pp REAL NOT NULL,
    health_primary_driver TEXT NOT NULL,
    low_health_share REAL NOT NULL,
    food_insecure_share REAL NOT NULL,
    cash_stressed_share REAL NOT NULL,
    pending_healthcare_visits_total INTEGER NOT NULL,
    healthcare_queue_depth INTEGER NOT NULL,
    healthcare_completed_count INTEGER NOT NULL,
    healthcare_denied_count INTEGER NOT NULL,
    firm_distress_primary_driver TEXT NOT NULL,
    burn_mode_firm_count INTEGER NOT NULL,
    survival_mode_firm_count INTEGER NOT NULL,
    zero_cash_firm_count INTEGER NOT NULL,
    weak_demand_firm_count INTEGER NOT NULL,
    inventory_pressure_firm_count INTEGER NOT NULL,
    bankruptcy_count INTEGER NOT NULL,
    housing_primary_driver TEXT NOT NULL,
    eviction_count INTEGER NOT NULL,
    housing_failure_count INTEGER NOT NULL,
    housing_unaffordable_count INTEGER NOT NULL,
    housing_no_supply_count INTEGER NOT NULL,
    homeless_household_count INTEGER NOT NULL,
    shortage_active_sector_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, tick),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tick_diagnostics_run_tick ON tick_diagnostics(run_id, tick);

-- =============================================================================
-- Table 11: sector_shortage_diagnostics
-- Stores compact per-sector shortage pressure rows
-- =============================================================================
CREATE TABLE IF NOT EXISTS sector_shortage_diagnostics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    sector TEXT NOT NULL,
    shortage_active BOOLEAN NOT NULL,
    shortage_severity REAL NOT NULL,
    primary_driver TEXT NOT NULL,
    mean_sell_through_rate REAL NOT NULL,
    vacancy_pressure REAL NOT NULL,
    inventory_pressure REAL NOT NULL,
    price_pressure REAL NOT NULL,
    queue_pressure REAL NOT NULL,
    occupancy_pressure REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, tick, sector),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_tick ON sector_shortage_diagnostics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_sector_tick ON sector_shortage_diagnostics(run_id, sector, tick);

-- =============================================================================
-- Table 12: regime_events
-- Stores high-value regime/state transition events
-- =============================================================================
CREATE TABLE IF NOT EXISTS regime_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    sector TEXT,
    reason_code TEXT,
    severity REAL,
    metric_value REAL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_regime_events_run_tick ON regime_events(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_regime_events_run_event_key ON regime_events(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_regime_events_run_type_tick ON regime_events(run_id, event_type, tick);
CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_type_tick ON regime_events(run_id, entity_type, tick);
CREATE INDEX IF NOT EXISTS idx_regime_events_run_entity_tick ON regime_events(run_id, entity_type, entity_id, tick);
CREATE INDEX IF NOT EXISTS idx_regime_events_run_sector_tick ON regime_events(run_id, sector, tick);

-- =============================================================================
-- Table 13: policy_config
-- Stores policy configuration for each simulation run
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,

    -- Tax policies
    wage_tax REAL,
    profit_tax REAL,
    wealth_tax_rate REAL,
    wealth_tax_threshold REAL,

    -- Social programs
    universal_basic_income REAL,
    unemployment_benefit_rate REAL,

    -- Labor policies
    minimum_wage REAL,

    -- Economic parameters
    inflation_rate REAL,
    birth_rate REAL,

    -- Agent stabilization
    agent_stabilizers_enabled BOOLEAN DEFAULT 0,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_run ON policy_config(run_id);
CREATE INDEX IF NOT EXISTS idx_policy_ubi ON policy_config(universal_basic_income);
CREATE INDEX IF NOT EXISTS idx_policy_min_wage ON policy_config(minimum_wage);

-- =============================================================================
-- Views for common queries
-- =============================================================================

-- Summary view: Run with final outcomes and policy
CREATE VIEW IF NOT EXISTS run_summary AS
SELECT
    r.run_id,
    r.created_at,
    r.status,
    r.seed,
    r.total_ticks,
    r.final_gdp,
    r.final_unemployment,
    r.final_gini,
    p.universal_basic_income as ubi,
    p.minimum_wage,
    p.wage_tax,
    p.profit_tax
FROM simulation_runs r
LEFT JOIN policy_config p ON r.run_id = p.run_id;

-- Average metrics view: Aggregate statistics per run
CREATE VIEW IF NOT EXISTS run_averages AS
SELECT
    run_id,
    COUNT(*) as tick_count,
    AVG(gdp) as avg_gdp,
    AVG(unemployment_rate) as avg_unemployment,
    AVG(gini_coefficient) as avg_gini,
    AVG(avg_happiness) as avg_happiness,
    AVG(tick_duration_ms) as avg_tick_duration_ms,
    AVG(labor_force_participation) as avg_labor_force_participation,
    AVG(open_vacancies) as avg_open_vacancies,
    MAX(gdp) as peak_gdp,
    MIN(unemployment_rate) as min_unemployment,
    MAX(gini_coefficient) as peak_gini
FROM tick_metrics
GROUP BY run_id;
