-- EcoSim PostgreSQL + TimescaleDB Schema
-- Local-first warehouse schema for simulation runs and tick metrics.

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
-- Table 3: policy_config
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
    MAX(gdp) AS peak_gdp,
    MIN(unemployment_rate) AS min_unemployment,
    MAX(gini_coefficient) AS peak_gini
FROM tick_metrics
GROUP BY run_id;
