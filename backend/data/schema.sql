-- EcoSim Data Warehouse Schema
-- Minimal design: 3 tables for core analytics

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
-- Table 3: policy_config
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
    MAX(gdp) as peak_gdp,
    MIN(unemployment_rate) as min_unemployment,
    MAX(gini_coefficient) as peak_gini
FROM tick_metrics
GROUP BY run_id;
