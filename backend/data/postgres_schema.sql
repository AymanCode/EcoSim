-- EcoSim PostgreSQL + TimescaleDB Schema
-- Local-first warehouse schema for simulation runs, metrics, snapshots, and events.

-- Enable TimescaleDB if available. This is safe when extension already exists.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================================================
-- Table 1: simulation_runs
-- =============================================================================
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'stopped')) DEFAULT 'running',

    -- Configuration
    seed INTEGER,
    num_households INTEGER,
    num_firms INTEGER,
    total_ticks INTEGER DEFAULT 0,

    -- Final outcomes
    final_gdp DOUBLE PRECISION,
    final_unemployment DOUBLE PRECISION,
    final_gini DOUBLE PRECISION,
    final_avg_happiness DOUBLE PRECISION,
    final_avg_health DOUBLE PRECISION,
    final_gov_balance DOUBLE PRECISION,
    config_json JSONB,
    code_version TEXT,
    schema_version TEXT,
    decision_feature_version TEXT,
    diagnostics_version TEXT,
    last_fully_persisted_tick INTEGER DEFAULT 0,
    analysis_ready BOOLEAN DEFAULT FALSE,
    termination_reason TEXT,

    -- Metadata
    description TEXT,
    tags TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_created ON simulation_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON simulation_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_tags ON simulation_runs(tags);

-- =============================================================================
-- Table 2: tick_metrics
-- =============================================================================
CREATE TABLE IF NOT EXISTS tick_metrics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Economic indicators
    gdp DOUBLE PRECISION,
    unemployment_rate DOUBLE PRECISION,
    mean_wage DOUBLE PRECISION,
    median_wage DOUBLE PRECISION,

    -- Wellbeing
    avg_happiness DOUBLE PRECISION,
    avg_health DOUBLE PRECISION,
    avg_morale DOUBLE PRECISION,

    -- Wealth & inequality
    total_net_worth DOUBLE PRECISION,
    gini_coefficient DOUBLE PRECISION,
    top10_wealth_share DOUBLE PRECISION,
    bottom50_wealth_share DOUBLE PRECISION,

    -- Government
    gov_cash_balance DOUBLE PRECISION,
    gov_profit DOUBLE PRECISION,

    -- Runtime / labor
    tick_duration_ms DOUBLE PRECISION,
    labor_force_participation DOUBLE PRECISION,
    open_vacancies INTEGER,
    total_hires INTEGER,
    total_layoffs INTEGER,
    healthcare_queue_depth INTEGER,

    -- Market
    total_firms INTEGER,
    struggling_firms INTEGER,
    avg_food_price DOUBLE PRECISION,
    avg_housing_price DOUBLE PRECISION,
    avg_services_price DOUBLE PRECISION,

    PRIMARY KEY (run_id, tick),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_metrics_run ON tick_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_metrics_run_tick ON tick_metrics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_metrics_tick ON tick_metrics(tick);

-- =============================================================================
-- Table 2b: sector_tick_metrics
-- =============================================================================
CREATE TABLE IF NOT EXISTS sector_tick_metrics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    sector TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    firm_count INTEGER,
    employees INTEGER,
    vacancies INTEGER,
    mean_wage_offer DOUBLE PRECISION,
    mean_price DOUBLE PRECISION,
    mean_inventory DOUBLE PRECISION,
    total_output DOUBLE PRECISION,
    total_revenue DOUBLE PRECISION,
    total_profit DOUBLE PRECISION,

    PRIMARY KEY (run_id, tick, sector),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_tick ON sector_tick_metrics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_sector_metrics_run_sector_tick ON sector_tick_metrics(run_id, sector, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'sector_tick_metrics',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => 1000
        );
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        NULL;
END $$;

-- =============================================================================
-- Table 3: firm_snapshots
-- =============================================================================
CREATE TABLE IF NOT EXISTS firm_snapshots (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    firm_id INTEGER NOT NULL,
    firm_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    is_baseline BOOLEAN DEFAULT FALSE,
    employee_count INTEGER,
    doctor_employee_count INTEGER,
    medical_employee_count INTEGER,
    planned_hires_count INTEGER,
    planned_layoffs_count INTEGER,
    actual_hires_count INTEGER,
    wage_offer DOUBLE PRECISION,
    price DOUBLE PRECISION,
    inventory_units DOUBLE PRECISION,
    output_units DOUBLE PRECISION,
    cash_balance DOUBLE PRECISION,
    revenue DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    quality_level DOUBLE PRECISION,
    queue_depth INTEGER,
    visits_completed DOUBLE PRECISION,
    burn_mode BOOLEAN DEFAULT FALSE,
    zero_cash_streak INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (run_id, tick, firm_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_tick ON firm_snapshots(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_firm_tick ON firm_snapshots(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_firm_snapshots_run_sector_tick ON firm_snapshots(run_id, sector, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'firm_snapshots',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => 1000
        );
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        NULL;
END $$;

-- Convert to hypertable when TimescaleDB functions are available.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'tick_metrics',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => 1000
        );
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        NULL;
END $$;

-- =============================================================================
-- Table 4: household_snapshots
-- =============================================================================
CREATE TABLE IF NOT EXISTS household_snapshots (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    household_id INTEGER NOT NULL,
    state TEXT NOT NULL,
    medical_status TEXT NOT NULL,
    employer_id INTEGER,
    is_employed BOOLEAN DEFAULT FALSE,
    can_work BOOLEAN DEFAULT FALSE,
    cash_balance DOUBLE PRECISION,
    wage DOUBLE PRECISION,
    last_wage_income DOUBLE PRECISION,
    last_transfer_income DOUBLE PRECISION,
    last_dividend_income DOUBLE PRECISION,
    reservation_wage DOUBLE PRECISION,
    expected_wage DOUBLE PRECISION,
    skill_level DOUBLE PRECISION,
    health DOUBLE PRECISION,
    happiness DOUBLE PRECISION,
    morale DOUBLE PRECISION,
    food_security DOUBLE PRECISION,
    housing_security BOOLEAN DEFAULT FALSE,
    unemployment_duration INTEGER,
    pending_healthcare_visits INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (run_id, tick, household_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_tick ON household_snapshots(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_household_tick ON household_snapshots(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_household_snapshots_run_state_tick ON household_snapshots(run_id, state, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'household_snapshots',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => 1000
        );
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        NULL;
END $$;

-- =============================================================================
-- Table 5: tracked_household_history
-- =============================================================================
CREATE TABLE IF NOT EXISTS tracked_household_history (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    household_id INTEGER NOT NULL,
    state TEXT NOT NULL,
    medical_status TEXT NOT NULL,
    employer_id INTEGER,
    is_employed BOOLEAN DEFAULT FALSE,
    can_work BOOLEAN DEFAULT FALSE,
    cash_balance DOUBLE PRECISION,
    wage DOUBLE PRECISION,
    expected_wage DOUBLE PRECISION,
    reservation_wage DOUBLE PRECISION,
    health DOUBLE PRECISION,
    happiness DOUBLE PRECISION,
    morale DOUBLE PRECISION,
    skill_level DOUBLE PRECISION,
    unemployment_duration INTEGER,
    pending_healthcare_visits INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (run_id, tick, household_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tracked_household_history_run_tick ON tracked_household_history(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_tracked_household_history_run_household_tick ON tracked_household_history(run_id, household_id, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'tracked_household_history',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE,
            chunk_time_interval => 1000
        );
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        NULL;
END $$;

-- =============================================================================
-- Table 6: labor_events
-- =============================================================================
CREATE TABLE IF NOT EXISTS labor_events (
    event_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    household_id INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actual_wage DOUBLE PRECISION,
    wage_offer DOUBLE PRECISION,
    reservation_wage DOUBLE PRECISION,
    skill_level DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_labor_events_run_tick ON labor_events(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_labor_events_run_event_key ON labor_events(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_household_tick ON labor_events(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_firm_tick ON labor_events(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_labor_events_run_type_tick ON labor_events(run_id, event_type, tick);

-- =============================================================================
-- Table 7: healthcare_events
-- =============================================================================
CREATE TABLE IF NOT EXISTS healthcare_events (
    event_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    household_id INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    queue_wait_ticks INTEGER,
    visit_price DOUBLE PRECISION,
    household_cost DOUBLE PRECISION,
    government_cost DOUBLE PRECISION,
    health_before DOUBLE PRECISION,
    health_after DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_tick ON healthcare_events(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_healthcare_events_run_event_key ON healthcare_events(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_household_tick ON healthcare_events(run_id, household_id, tick);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_firm_tick ON healthcare_events(run_id, firm_id, tick);
CREATE INDEX IF NOT EXISTS idx_healthcare_events_run_type_tick ON healthcare_events(run_id, event_type, tick);

-- =============================================================================
-- Table 8: policy_actions
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_actions (
    action_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    reason_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_actions_run_tick ON policy_actions(run_id, tick);
CREATE UNIQUE INDEX IF NOT EXISTS ux_policy_actions_run_event_key ON policy_actions(run_id, event_key);
CREATE INDEX IF NOT EXISTS idx_policy_actions_run_type_tick ON policy_actions(run_id, action_type, tick);

-- =============================================================================
-- Table 9: decision_features
-- =============================================================================
CREATE TABLE IF NOT EXISTS decision_features (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    unemployment_short_ma DOUBLE PRECISION NOT NULL,
    unemployment_long_ma DOUBLE PRECISION NOT NULL,
    inflation_short_ma DOUBLE PRECISION NOT NULL,
    hiring_momentum DOUBLE PRECISION NOT NULL,
    layoff_momentum DOUBLE PRECISION NOT NULL,
    vacancy_fill_ratio DOUBLE PRECISION NOT NULL,
    wage_pressure DOUBLE PRECISION NOT NULL,
    healthcare_pressure DOUBLE PRECISION NOT NULL,
    consumer_distress_score DOUBLE PRECISION NOT NULL,
    fiscal_stress_score DOUBLE PRECISION NOT NULL,
    inequality_pressure_score DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (run_id, tick),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decision_features_run_tick ON decision_features(run_id, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'decision_features',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    END IF;
EXCEPTION WHEN undefined_function THEN
    NULL;
END $$;

-- =============================================================================
-- Table 10: tick_diagnostics
-- =============================================================================
CREATE TABLE IF NOT EXISTS tick_diagnostics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    unemployment_change_pp DOUBLE PRECISION NOT NULL,
    unemployment_primary_driver TEXT NOT NULL,
    layoffs_count INTEGER NOT NULL,
    hires_count INTEGER NOT NULL,
    failed_hiring_firm_count INTEGER NOT NULL,
    failed_hiring_roles_count INTEGER NOT NULL,
    wage_mismatch_seeker_count INTEGER NOT NULL,
    health_blocked_worker_count INTEGER NOT NULL,
    inactive_work_capable_count INTEGER NOT NULL,
    avg_health_change_pp DOUBLE PRECISION NOT NULL,
    health_primary_driver TEXT NOT NULL,
    low_health_share DOUBLE PRECISION NOT NULL,
    food_insecure_share DOUBLE PRECISION NOT NULL,
    cash_stressed_share DOUBLE PRECISION NOT NULL,
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (run_id, tick),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tick_diagnostics_run_tick ON tick_diagnostics(run_id, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'tick_diagnostics',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    END IF;
EXCEPTION WHEN undefined_function THEN
    NULL;
END $$;

-- =============================================================================
-- Table 11: sector_shortage_diagnostics
-- =============================================================================
CREATE TABLE IF NOT EXISTS sector_shortage_diagnostics (
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    sector TEXT NOT NULL,
    shortage_active BOOLEAN NOT NULL,
    shortage_severity DOUBLE PRECISION NOT NULL,
    primary_driver TEXT NOT NULL,
    mean_sell_through_rate DOUBLE PRECISION NOT NULL,
    vacancy_pressure DOUBLE PRECISION NOT NULL,
    inventory_pressure DOUBLE PRECISION NOT NULL,
    price_pressure DOUBLE PRECISION NOT NULL,
    queue_pressure DOUBLE PRECISION NOT NULL,
    occupancy_pressure DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (run_id, tick, sector),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_tick ON sector_shortage_diagnostics(run_id, tick);
CREATE INDEX IF NOT EXISTS idx_sector_shortage_run_sector_tick ON sector_shortage_diagnostics(run_id, sector, tick);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'sector_shortage_diagnostics',
            'tick',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    END IF;
EXCEPTION WHEN undefined_function THEN
    NULL;
END $$;

-- =============================================================================
-- Table 12: regime_events
-- =============================================================================
CREATE TABLE IF NOT EXISTS regime_events (
    event_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    tick INTEGER NOT NULL CHECK (tick >= 0),
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    sector TEXT,
    reason_code TEXT,
    severity DOUBLE PRECISION,
    metric_value DOUBLE PRECISION,
    payload_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
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
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_config (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,

    wage_tax DOUBLE PRECISION,
    profit_tax DOUBLE PRECISION,
    wealth_tax_rate DOUBLE PRECISION,
    wealth_tax_threshold DOUBLE PRECISION,
    universal_basic_income DOUBLE PRECISION,
    unemployment_benefit_rate DOUBLE PRECISION,
    minimum_wage DOUBLE PRECISION,
    inflation_rate DOUBLE PRECISION,
    birth_rate DOUBLE PRECISION,
    agent_stabilizers_enabled BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_run ON policy_config(run_id);
CREATE INDEX IF NOT EXISTS idx_policy_ubi ON policy_config(universal_basic_income);
CREATE INDEX IF NOT EXISTS idx_policy_min_wage ON policy_config(minimum_wage);

-- =============================================================================
-- Views for common analytical queries
-- =============================================================================
CREATE OR REPLACE VIEW run_summary AS
SELECT
    r.run_id,
    r.created_at,
    r.status,
    r.seed,
    r.total_ticks,
    r.final_gdp,
    r.final_unemployment,
    r.final_gini,
    p.universal_basic_income AS ubi,
    p.minimum_wage,
    p.wage_tax,
    p.profit_tax
FROM simulation_runs r
LEFT JOIN policy_config p ON r.run_id = p.run_id;

CREATE OR REPLACE VIEW run_averages AS
SELECT
    run_id,
    COUNT(*) AS tick_count,
    AVG(gdp) AS avg_gdp,
    AVG(unemployment_rate) AS avg_unemployment,
    AVG(gini_coefficient) AS avg_gini,
    AVG(avg_happiness) AS avg_happiness,
    AVG(tick_duration_ms) AS avg_tick_duration_ms,
    AVG(labor_force_participation) AS avg_labor_force_participation,
    AVG(open_vacancies) AS avg_open_vacancies,
    MAX(gdp) AS peak_gdp,
    MIN(unemployment_rate) AS min_unemployment,
    MAX(gini_coefficient) AS peak_gini
FROM tick_metrics
GROUP BY run_id;
