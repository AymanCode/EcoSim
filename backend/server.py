import asyncio
import json
import logging
import logging.handlers
import sys
import os
import time
import uuid

# Add current directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from config import CONFIG
from run_large_simulation import create_large_economy, compute_household_stats, compute_firm_stats

_WAREHOUSE_IMPORT_ERROR = None
try:
    from data.db_manager import SimulationRun, TickMetrics, PolicyConfig
    from data.warehouse_factory import create_warehouse_manager
except Exception as exc:  # pragma: no cover - best-effort optional dependency
    _WAREHOUSE_IMPORT_ERROR = exc
    SimulationRun = None
    TickMetrics = None
    PolicyConfig = None
    create_warehouse_manager = None

# Setup logging with rotation
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "ecosim.log"),
            maxBytes=10_485_760,  # 10 MB
            backupCount=5,
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="EcoSim", version="2.0.0")

# CORS: restrict to known development origins; override via CORS_ORIGINS env var
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# --- Input validation models ---

class SetupConfig(BaseModel):
    """Validated setup configuration from WebSocket."""
    num_households: int = Field(default=1000, ge=3, le=100_000)
    num_firms: int = Field(default=5, ge=1, le=1_000)
    disable_stabilizers: bool = False
    disabled_agents: List[str] = Field(default_factory=list)

    @field_validator("disabled_agents", mode="before")
    @classmethod
    def validate_agent_names(cls, v):
        valid = {"households", "firms", "government", "all"}
        for name in v:
            if name not in valid:
                raise ValueError(f"Invalid agent name '{name}'. Must be one of {valid}")
        return v


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "version": "2.0.0"}

class SimulationManager:
    def __init__(self):
        self.economy = None
        self.is_running = False
        self.tick = 0
        self.logs = []
        self.active_websocket = None
        self.tracked_household_ids: List[int] = []
        self.tracked_firm_ids: List[int] = []
        self.subject_histories: Dict[int, Dict[str, List[Dict[str, float]]]] = {}
        self.firm_histories: Dict[int, Dict[str, List[Dict[str, float]]]] = {}
        self.stabilizer_state = {
            "households": True,
            "firms": True,
            "government": True
        }
        self.pending_config_updates: Dict[str, Any] | None = None
        self.metrics_stride = 5
        self.policy_changes = []
        self.cached_stats = None
        self.cached_firm_stats = None
        self.cached_econ_metrics = None
        self.cached_mean_prices = None
        self.cached_supplies = None
        self.cached_total_net_worth = None
        self.enable_warehouse = os.getenv("ECOSIM_ENABLE_WAREHOUSE", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.warehouse_backend = os.getenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite").strip().lower()
        self.warehouse_manager = None
        self.warehouse_run_id: Optional[str] = None
        self.tick_metrics_batch: List[Any] = []
        self.tick_metrics_batch_size = max(1, int(os.getenv("ECOSIM_TICK_BATCH_SIZE", "50")))

    def _open_warehouse_run(self, config: Dict[str, Any], num_households: int, num_firms: int):
        """Initialize persistence backend and create a new run record."""
        if not self.enable_warehouse:
            return

        if create_warehouse_manager is None or SimulationRun is None:
            logger.warning(
                "Warehouse disabled: import failed (%s).",
                _WAREHOUSE_IMPORT_ERROR,
            )
            self.enable_warehouse = False
            return

        if self.warehouse_manager is None:
            try:
                self.warehouse_manager = create_warehouse_manager()
                logger.info("Warehouse backend initialized (%s).", self.warehouse_backend)
            except Exception as exc:
                logger.error("Warehouse initialization failed: %s", exc)
                self.enable_warehouse = False
                return

        # Close any previous active run before opening a new one.
        self._close_warehouse_run("stopped")

        self.warehouse_run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.tick_metrics_batch = []

        try:
            run = SimulationRun(
                run_id=self.warehouse_run_id,
                status="running",
                num_households=num_households,
                num_firms=num_firms,
                description="Live websocket simulation run",
                tags=f"backend={self.warehouse_backend}",
            )
            self.warehouse_manager.create_run(run)

            gov = self.economy.government if self.economy else None
            policy = PolicyConfig(
                run_id=self.warehouse_run_id,
                wage_tax=float(config.get("wage_tax", getattr(gov, "wage_tax_rate", 0.0))),
                profit_tax=float(config.get("profit_tax", getattr(gov, "profit_tax_rate", 0.0))),
                wealth_tax_rate=float(config.get("wealthTaxRate", getattr(gov, "wealth_tax_rate", 0.0))),
                wealth_tax_threshold=float(config.get("wealthTaxThreshold", getattr(gov, "wealth_tax_threshold", 0.0))),
                universal_basic_income=float(config.get("universalBasicIncome", getattr(gov, "ubi_amount", 0.0))),
                unemployment_benefit_rate=float(config.get("unemploymentBenefitRate", 0.0)),
                minimum_wage=float(config.get("minimumWage", getattr(self.economy.config.labor_market, "minimum_wage_floor", 0.0))),
                inflation_rate=float(config.get("inflationRate", getattr(gov, "target_inflation_rate", 0.0))),
                birth_rate=float(config.get("birthRate", getattr(gov, "birth_rate", 0.0))),
                agent_stabilizers_enabled=all(self.stabilizer_state.values()),
            )
            self.warehouse_manager.insert_policy_config(policy)
            logger.info("Opened warehouse run %s", self.warehouse_run_id)
        except Exception as exc:
            logger.error("Failed to create warehouse run metadata: %s", exc)
            self.warehouse_run_id = None
            self.tick_metrics_batch = []

    def _flush_tick_metrics_batch(self):
        """Persist buffered tick metrics in one batch write."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
            or not self.tick_metrics_batch
        ):
            return

        try:
            self.warehouse_manager.insert_tick_metrics(self.tick_metrics_batch)
            self.tick_metrics_batch = []
        except Exception as exc:
            logger.error("Tick metrics flush failed: %s", exc)

    def _collect_final_metrics(self) -> Dict[str, float]:
        """Collect final aggregate values for run status update."""
        if not self.economy:
            return {}

        econ_metrics = self.economy.get_economic_metrics()
        stats = compute_household_stats(self.economy.households)
        final_gdp = sum(self.economy.last_tick_revenue.values())
        return {
            "gdp": float(final_gdp),
            "unemployment_rate": float(stats.get("unemployment_rate", 0.0) * 100.0),
            "gini_coefficient": float(econ_metrics.get("gini_coefficient", 0.0)),
            "avg_happiness": float(stats.get("mean_happiness", 0.0) * 100.0),
            "avg_health": float(stats.get("mean_health", 0.0) * 100.0),
            "gov_cash_balance": float(self.economy.government.cash_balance),
        }

    def _close_warehouse_run(self, status: str):
        """Finalize active run and clear in-memory buffering state."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
        ):
            return

        try:
            self._flush_tick_metrics_batch()
            self.warehouse_manager.update_run_status(
                self.warehouse_run_id,
                status=status,
                total_ticks=self.tick,
                final_metrics=self._collect_final_metrics(),
            )
            logger.info("Closed warehouse run %s (%s)", self.warehouse_run_id, status)
        except Exception as exc:
            logger.error("Failed to close warehouse run %s: %s", self.warehouse_run_id, exc)
        finally:
            self.warehouse_run_id = None
            self.tick_metrics_batch = []

    def initialize(self, config: Dict[str, Any] = None):
        if config is None:
            config = {}

        # Validate config through pydantic model
        validated = SetupConfig(**config)
        num_households = validated.num_households
        num_firms = validated.num_firms
        
        logger.info(f"Initializing economy with {num_households} households and {num_firms} firms/cat...")
        self.economy = create_large_economy(
            num_households=num_households, 
            num_firms_per_category=num_firms
        )

        disabled_agents: List[str] = []
        if validated.disable_stabilizers:
            disabled_agents = validated.disabled_agents
            if not disabled_agents:
                disabled_agents = ["households", "firms", "government"]
        elif validated.disabled_agents:
            disabled_agents = validated.disabled_agents

        if disabled_agents:
            self.economy.apply_stabilization_overrides(disabled_agents)
            households = not ("all" in disabled_agents or "households" in disabled_agents)
            firms = not ("all" in disabled_agents or "firms" in disabled_agents)
            government = not ("all" in disabled_agents or "government" in disabled_agents)
            self.stabilizer_state = {
                "households": households,
                "firms": firms,
                "government": government
            }
        else:
            self.economy.configure_stabilizers(
                households=True,
                firms=True,
                government=True
            )
            self.stabilizer_state = {
                "households": True,
                "firms": True,
                "government": True
            }
        
        # Apply initial tax rates if provided
        if "wage_tax" in config:
            self.economy.government.wage_tax_rate = config["wage_tax"]
        if "profit_tax" in config:
            self.economy.government.profit_tax_rate = config["profit_tax"]
            
        self.tick = 0
        self.logs = []
        self.gdp_history = [] 
        self.unemployment_history = []
        self.wage_history = []
        self.median_wage_history = []
        self.happiness_history = []
        self.health_history = []
        self.gov_debt_history = []
        self.gov_profit_history = []
        self.firm_count_history = []
        self.net_worth_history = []
        self.gini_history = []
        self.top10_share_history = []
        self.bottom50_share_history = []
        
        # Consolidated histories
        self.price_history = {"food": [], "housing": [], "services": [], "healthcare": []}
        self.supply_history = {"food": [], "housing": [], "services": [], "healthcare": []}
        self.cached_stats = None
        self.cached_firm_stats = None
        self.cached_econ_metrics = None
        self.cached_mean_prices = None
        self.cached_supplies = None
        self.cached_total_net_worth = None

        # Select 12 random households to track (more diverse sample)
        import random
        if self.economy.households:
            self.tracked_household_ids = [h.household_id for h in random.sample(self.economy.households, min(12, len(self.economy.households)))]
        else:
            self.tracked_household_ids = []

        # Track historical data for each subject
        self.subject_histories = {hid: {
            "cash": [],
            "wage": [],
            "happiness": [],
            "health": [],
            "netWorth": [],
            "events": []  # Life events (job changes, medical, etc.)
        } for hid in self.tracked_household_ids}

        # Initialize tracked firms (filled below)
        self.tracked_firm_ids = []
        self.firm_histories = {}
        self._select_tracked_firms()
        self._open_warehouse_run(config=config, num_households=num_households, num_firms=num_firms)
            
        logger.info("Economy initialized")

    def update_stabilizers(self, disable_flag: bool, disabled_agents: List[str]):
        if not self.economy:
            return

        if not disable_flag:
            self.economy.configure_stabilizers(True, True, True)
            self.stabilizer_state = {
                "households": True,
                "firms": True,
                "government": True
            }
            return

        disabled = {agent.lower() for agent in disabled_agents}
        if not disabled:
            disabled = {"all"}
        disable_all = "all" in disabled
        households_enabled = not (disable_all or "households" in disabled)
        firms_enabled = not (disable_all or "firms" in disabled)
        government_enabled = not (disable_all or "government" in disabled)
        self.economy.configure_stabilizers(
            households=households_enabled,
            firms=firms_enabled,
            government=government_enabled
        )
        self.stabilizer_state = {
            "households": households_enabled,
            "firms": firms_enabled,
            "government": government_enabled
        }

    def _select_tracked_firms(self):
        """Ensure tracked firm list highlights top private performers plus baselines."""
        firms = getattr(self.economy, "firms", [])
        if not firms:
            self.tracked_firm_ids = []
            self.firm_histories = {}
            return

        private_firms = [f for f in firms if not getattr(f, "is_baseline", False)]
        baseline_firms = [f for f in firms if getattr(f, "is_baseline", False)]

        private_firms.sort(key=lambda f: f.cash_balance, reverse=True)
        baseline_firms.sort(key=lambda f: f.cash_balance, reverse=True)

        selected = []
        for f in private_firms[:5]:
            selected.append(f.firm_id)
        for f in baseline_firms[:2]:
            if f.firm_id not in selected:
                selected.append(f.firm_id)

        # Fallback to additional private firms if we still have slots
        if len(selected) < 7:
            extra = [f.firm_id for f in private_firms[5:]] + [f.firm_id for f in baseline_firms[2:]]
            for fid in extra:
                if fid not in selected:
                    selected.append(fid)
                if len(selected) >= 7:
                    break

        selected = selected[:7]
        self.tracked_firm_ids = selected

        # Ensure histories exist for new selections
        for fid in selected:
            if fid not in self.firm_histories:
                self.firm_histories[fid] = {
                    "cash": [],
                    "price": [],
                    "wageOffer": [],
                    "inventory": [],
                    "employees": [],
                    "profit": [],
                    "revenue": [],
                    "events": []
                }

    async def run_loop(self):
        if not self.economy:
            logger.warning("Attempted to run loop without economy. Waiting for SETUP.")
            return

        logger.info("Starting simulation loop")
        try:
            history_stride = 25
            while self.is_running and self.active_websocket:
                start_time = asyncio.get_event_loop().time()

                # Apply any pending config updates from the client
                if self.pending_config_updates:
                    await self._apply_config_updates(self.pending_config_updates)
                    self.pending_config_updates = None

                # Run one step
                self.economy.step()
                self.tick += 1
                sample_history = (self.tick == 1) or (self.tick % history_stride == 0)
                
                recompute_metrics = (self.tick % self.metrics_stride == 0) or self.cached_stats is None
                if recompute_metrics:
                    econ_metrics = self.economy.get_economic_metrics()
                    stats = compute_household_stats(self.economy.households)
                    firm_stats = compute_firm_stats(
                        self.economy.firms,
                        household_lookup=self.economy.household_lookup
                    )
                    self.cached_econ_metrics = econ_metrics
                    self.cached_stats = stats
                    self.cached_firm_stats = firm_stats
                else:
                    econ_metrics = self.cached_econ_metrics or {}
                    stats = self.cached_stats or {}
                    firm_stats = self.cached_firm_stats or {}

                # Calculate GDP (sum of revenue)
                gdp = sum(self.economy.last_tick_revenue.values())
                
                # Calculate Fiscal Balance (Gov Profit)
                current_gov_cash = self.economy.government.cash_balance
                if not hasattr(self, 'prev_gov_cash'):
                    self.prev_gov_cash = current_gov_cash
                fiscal_balance = current_gov_cash - self.prev_gov_cash
                self.prev_gov_cash = current_gov_cash
                
                # Fetch detailed government budget from economy
                gov_revenue = self.economy.last_tick_gov_wage_taxes + self.economy.last_tick_gov_profit_taxes + self.economy.last_tick_gov_property_taxes
                gov_transfers = self.economy.last_tick_gov_transfers
                gov_investments = self.economy.last_tick_gov_investments
                gov_owned_firms = sum(1 for f in self.economy.firms if f.is_baseline)
                active_loans = sum(1 for f in self.economy.firms if getattr(f, "government_loan_remaining", 0) > 0)
                
                if recompute_metrics:
                    # Market Metrics (Prices & Supply)
                    prices = {"Food": [], "Housing": [], "Services": [], "Healthcare": []}
                    supplies = {"Food": 0.0, "Housing": 0.0, "Services": 0.0, "Healthcare": 0.0}

                    for f in self.economy.firms:
                        if f.good_category in prices:
                            prices[f.good_category].append(f.price)
                            supplies[f.good_category] += f.inventory_units
                            # Add tenants to housing supply (occupied units)
                            if f.good_category == "Housing":
                                supplies["Housing"] += len(f.current_tenants)

                    # Add household owned housing to supply
                    for h in self.economy.households:
                        for good, qty in h.goods_inventory.items():
                            if "housing" in good.lower():
                                supplies["Housing"] += qty

                    mean_prices = {
                        k: sum(v) / len(v) if v else 0.0 for k, v in prices.items()
                    }

                    # Calculate Total Net Worth (Cash + Inventory Value)
                    total_net_worth = 0.0
                    for h in self.economy.households:
                        total_net_worth += h.cash_balance
                        for good, qty in h.goods_inventory.items():
                            # Infer category to get price
                            cat = "Food"  # Default
                            lower_good = good.lower()
                            if "housing" in lower_good:
                                cat = "Housing"
                            elif "service" in lower_good:
                                cat = "Services"
                            elif "health" in lower_good or "medical" in lower_good:
                                cat = "Healthcare"

                            price = mean_prices.get(cat, 0.0)
                            total_net_worth += qty * price

                    self.cached_mean_prices = mean_prices
                    self.cached_supplies = supplies
                    self.cached_total_net_worth = total_net_worth
                else:
                    mean_prices = self.cached_mean_prices or {"Food": 0.0, "Housing": 0.0, "Services": 0.0, "Healthcare": 0.0}
                    supplies = self.cached_supplies or {"Food": 0.0, "Housing": 0.0, "Services": 0.0, "Healthcare": 0.0}
                    total_net_worth = self.cached_total_net_worth or 0.0

                if (
                    self.enable_warehouse
                    and self.warehouse_manager is not None
                    and self.warehouse_run_id is not None
                    and TickMetrics is not None
                ):
                    tick_metric = TickMetrics(
                        run_id=self.warehouse_run_id,
                        tick=self.tick,
                        gdp=float(gdp),
                        unemployment_rate=float(stats["unemployment_rate"] * 100.0),
                        mean_wage=float(stats["mean_wage"]),
                        median_wage=float(stats["median_wage"]),
                        avg_happiness=float(stats["mean_happiness"] * 100.0),
                        avg_health=float(stats["mean_health"] * 100.0),
                        avg_morale=float(stats["mean_morale"] * 100.0),
                        total_net_worth=float(total_net_worth),
                        gini_coefficient=float(econ_metrics.get("gini_coefficient", 0.0)),
                        top10_wealth_share=float(econ_metrics.get("top_10_percent_share", 0.0) * 100.0),
                        bottom50_wealth_share=float(econ_metrics.get("bottom_50_percent_share", 0.0) * 100.0),
                        gov_cash_balance=float(current_gov_cash),
                        gov_profit=float(fiscal_balance),
                        total_firms=int(len(self.economy.firms)),
                        struggling_firms=int(firm_stats.get("struggling_firms", 0)),
                        avg_food_price=float(mean_prices["Food"]),
                        avg_housing_price=float(mean_prices["Housing"]),
                        avg_services_price=float(mean_prices["Services"]),
                    )
                    self.tick_metrics_batch.append(tick_metric)
                    if len(self.tick_metrics_batch) >= self.tick_metrics_batch_size:
                        self._flush_tick_metrics_batch()

                # Gather Tracked Subjects Data
                self._select_tracked_firms()

                tracked_subjects = []
                hh_cfg = CONFIG.households
                wage_anchor_low, wage_anchor_mid, wage_anchor_high = getattr(
                    self.economy, "cached_wage_percentiles", (0.0, 0.0, 0.0)
                )
                # Fall back to mean wage if percentiles haven't been computed yet.
                if wage_anchor_mid is None or wage_anchor_mid == 0.0:
                    fallback_wage = stats.get("mean_wage", 0.0)
                    wage_anchor_low = wage_anchor_low or fallback_wage
                    wage_anchor_mid = wage_anchor_mid or fallback_wage
                    wage_anchor_high = wage_anchor_high or fallback_wage
                for hid in self.tracked_household_ids:
                    h = self.economy.household_lookup.get(hid)
                    if h:
                        medical_status = (h.medical_training_status or "none").lower()

                        # Infer State (explicitly separate unemployed vs medical training).
                        if medical_status == "student":
                            state = "MED_SCHOOL"
                        elif h.employer_id:
                            state = "WORKING"
                        else:
                            state = "UNEMPLOYED"

                        # Get Employer Name & Category
                        employer_name = "Unemployed"
                        employer_category = None
                        if h.employer_id:
                            employer = self.economy.firm_lookup.get(h.employer_id)
                            if employer:
                                employer_name = employer.good_name
                                employer_category = employer.good_category
                        elif medical_status == "student":
                            employer_name = "Medical School"
                            employer_category = "Healthcare Training"

                        # Calculate Personal Net Worth
                        personal_net_worth = h.cash_balance
                        for good, qty in h.goods_inventory.items():
                            cat = "Food"
                            lower_good = good.lower()
                            if "housing" in lower_good:
                                cat = "Housing"
                            elif "service" in lower_good:
                                cat = "Services"
                            elif "health" in lower_good or "medical" in lower_good:
                                cat = "Healthcare"
                            personal_net_worth += qty * mean_prices.get(cat, 0.0)

                        # Explain expected wage dynamics for UI transparency.
                        if h.skills_level < 0.4:
                            market_anchor_estimate = wage_anchor_low
                        elif h.skills_level > 0.7:
                            market_anchor_estimate = wage_anchor_high
                        else:
                            market_anchor_estimate = wage_anchor_mid
                        market_anchor_estimate_value = (
                            float(market_anchor_estimate)
                            if market_anchor_estimate is not None
                            else None
                        )

                        duration_pressure = min(
                            hh_cfg.duration_pressure_cap,
                            h.unemployment_duration * hh_cfg.duration_pressure_rate,
                        )
                        cash_pressure = 0.0
                        poverty_threshold = max(1.0, float(hh_cfg.poverty_threshold))
                        if h.cash_balance < poverty_threshold:
                            cash_pressure = min(
                                hh_cfg.happiness_pressure_cap,
                                (poverty_threshold - h.cash_balance)
                                / max(poverty_threshold, 1.0)
                                * hh_cfg.happiness_pressure_cap,
                            )
                        health_pressure = 0.0
                        if h.health < hh_cfg.happiness_threshold:
                            health_pressure = min(
                                0.2,
                                (hh_cfg.happiness_threshold - h.health)
                                * hh_cfg.happiness_pressure_rate,
                            )
                        decay_factor = max(
                            hh_cfg.min_decay_factor,
                            hh_cfg.base_wage_decay
                            - duration_pressure
                            - cash_pressure
                            - health_pressure,
                        )

                        if h.is_employed:
                            expectation_mode = "EMPLOYED_ANCHOR"
                        elif state == "MED_SCHOOL":
                            expectation_mode = "TRAINING_TRACK"
                        else:
                            expectation_mode = "UNEMPLOYED_DECAY"

                        expectation_tags: List[str] = []
                        if h.is_employed:
                            expectation_tags.append("current_wage_anchor")
                        if h.unemployment_duration > 0:
                            expectation_tags.append("unemployment_duration_pressure")
                        if cash_pressure > 0.0:
                            expectation_tags.append("cash_stress_pressure")
                        if health_pressure > 0.0:
                            expectation_tags.append("health_stress_pressure")
                        if medical_status in {"resident", "doctor"}:
                            expectation_tags.append("medical_track_wage_anchor")
                        if medical_status == "student":
                            expectation_tags.append("in_training_not_searching")

                        # Force JSON-safe primitives for frontend transport.
                        expected_wage_reason = {
                            "mode": str(expectation_mode),
                            "gapToCurrentWage": float(h.expected_wage - h.wage),
                            "wageExpectationAlpha": float(h.wage_expectation_alpha),
                            "durationPressure": float(duration_pressure),
                            "cashPressure": float(cash_pressure),
                            "healthPressure": float(health_pressure),
                            "decayFactor": float(decay_factor),
                            "marketAnchorEstimate": market_anchor_estimate_value,
                            "unemploymentDuration": int(h.unemployment_duration),
                            "tags": [str(tag) for tag in expectation_tags],
                        }

                        traits = {
                            "spendingTendency": float(h.spending_tendency),
                            "frugality": float(h.frugality),
                            "savingTendency": float(h.saving_tendency),
                            "qualityLavishness": float(h.quality_lavishness),
                            "priceSensitivity": float(h.price_sensitivity),
                            "skillGrowthRate": float(h.skill_growth_rate),
                            "healthDecayPerYear": float(h.health_decay_per_year),
                            "healthcareSeekBasePct": float(h.healthcare_request_base_chance_pct),
                            "minFoodPerTick": float(h.min_food_per_tick),
                            "minServicesPerTick": float(h.min_services_per_tick),
                        }

                        # Track history at startup and then every history_stride ticks.
                        if sample_history:
                            if hid in self.subject_histories:
                                self.subject_histories[hid]["cash"].append({"tick": self.tick, "value": h.cash_balance})
                                self.subject_histories[hid]["wage"].append({"tick": self.tick, "value": h.wage})
                                self.subject_histories[hid]["happiness"].append({"tick": self.tick, "value": h.happiness * 100})
                                self.subject_histories[hid]["health"].append({"tick": self.tick, "value": h.health * 100})
                                self.subject_histories[hid]["netWorth"].append({"tick": self.tick, "value": personal_net_worth})

                        # Get recent events
                        recent_events = self.subject_histories.get(hid, {}).get("events", [])[-5:] if hid in self.subject_histories else []

                        tracked_subjects.append({
                            "id": h.household_id,
                            "name": f"Subject-{h.household_id}",
                            "age": h.age,
                            "state": state,
                            "medicalStatus": medical_status,
                            "employer": employer_name,
                            "employerCategory": employer_category,
                            "wage": h.wage,
                            "expectedWage": h.expected_wage,
                            "reservationWage": h.reservation_wage,
                            "isEmployed": h.is_employed,
                            "cash": h.cash_balance,
                            "netWorth": personal_net_worth,
                            "happiness": h.happiness,
                            "health": h.health,
                            "morale": h.morale,
                            "skills": h.skills_level,
                            "medicalDebt": h.medical_loan_remaining,
                            "unemploymentDuration": int(h.unemployment_duration),
                            "canWork": bool(h.can_work),
                            "needs": {
                                "food": h.goods_inventory.get("Food", 0) + h.goods_inventory.get("food", 0),
                                "housing": 1 if h.owns_housing or h.renting_from_firm_id else 0,
                                "healthcare": h.goods_inventory.get("Healthcare", 0) + h.goods_inventory.get("healthcare", 0),
                            },
                            "expectedWageReason": expected_wage_reason,
                            "traits": traits,
                            "history": {
                                "cash": self.subject_histories.get(hid, {}).get("cash", []),
                                "wage": self.subject_histories.get(hid, {}).get("wage", []),
                                "happiness": self.subject_histories.get(hid, {}).get("happiness", []),
                                "health": self.subject_histories.get(hid, {}).get("health", []),
                                "netWorth": self.subject_histories.get(hid, {}).get("netWorth", [])
                            },
                            "recentEvents": recent_events
                        })

                tracked_firms = []
                for fid in self.tracked_firm_ids:
                    firm = self.economy.firm_lookup.get(fid)
                    if not firm:
                        continue

                    if firm.cash_balance <= 0 or getattr(firm, "zero_cash_streak", 0) > 2:
                        firm_state = "DISTRESS"
                    elif getattr(firm, "burn_mode", False):
                        firm_state = "BURN"
                    elif firm.planned_hires_count > 0:
                        firm_state = "SCALING"
                    else:
                        firm_state = "STABLE"

                    revenue = getattr(firm, "last_revenue", 0.0)
                    profit = getattr(firm, "last_profit", 0.0)
                    is_healthcare_firm = (firm.good_category or "").lower() == "healthcare"
                    visits_completed = float(getattr(firm, "healthcare_completed_visits_last_tick", 0.0))
                    visit_revenue = float(revenue if is_healthcare_firm else 0.0)
                    doctor_employees = 0
                    medical_employees = 0
                    if is_healthcare_firm and firm.employees:
                        for employee_id in firm.employees:
                            worker = self.economy.household_lookup.get(employee_id)
                            if worker is None:
                                continue
                            if worker.medical_training_status == "doctor":
                                doctor_employees += 1
                                medical_employees += 1
                            elif worker.medical_training_status == "resident":
                                medical_employees += 1

                    if sample_history and fid in self.firm_histories:
                        history = self.firm_histories[fid]
                        history["cash"].append({"tick": self.tick, "value": firm.cash_balance})
                        history["price"].append({"tick": self.tick, "value": firm.price})
                        history["wageOffer"].append({"tick": self.tick, "value": firm.wage_offer})
                        history["inventory"].append({"tick": self.tick, "value": firm.inventory_units})
                        history["employees"].append({"tick": self.tick, "value": len(firm.employees)})
                        history["profit"].append({"tick": self.tick, "value": profit})
                        history["revenue"].append({"tick": self.tick, "value": revenue})

                    tracked_firms.append({
                        "id": firm.firm_id,
                        "name": firm.good_name,
                        "category": firm.good_category,
                        "cash": firm.cash_balance,
                        "inventory": firm.inventory_units,
                        "employees": len(firm.employees),
                        "doctorEmployees": doctor_employees,
                        "medicalEmployees": medical_employees,
                        "visitsCompleted": visits_completed,
                        "visitRevenue": visit_revenue,
                        "price": firm.price,
                        "wageOffer": firm.wage_offer,
                        "quality": firm.quality_level,
                        "lastRevenue": revenue,
                        "lastProfit": profit,
                        "state": firm_state,
                        "history": self.firm_histories.get(fid, {})
                    })

                # Update history at startup and then every history_stride ticks.
                if sample_history:
                    self.gdp_history.append({"tick": self.tick, "value": gdp / 1000000.0})
                    self.unemployment_history.append({"tick": self.tick, "value": stats["unemployment_rate"] * 100})
                    self.wage_history.append({"tick": self.tick, "value": stats["mean_wage"]})
                    self.median_wage_history.append({"tick": self.tick, "value": stats["median_wage"]})
                    self.happiness_history.append({"tick": self.tick, "value": stats["mean_happiness"] * 100})
                    self.health_history.append({"tick": self.tick, "value": stats["mean_health"] * 100})
                    self.gov_profit_history.append({"tick": self.tick, "value": fiscal_balance / 1000000.0})
                    self.gov_debt_history.append({"tick": self.tick, "value": -current_gov_cash / 1000000.0 if current_gov_cash < 0 else 0})
                    self.firm_count_history.append({"tick": self.tick, "value": len(self.economy.firms)})
                    self.net_worth_history.append({"tick": self.tick, "value": total_net_worth / 1000000.0})

                    # Wealth inequality metrics
                    self.gini_history.append({"tick": self.tick, "value": econ_metrics.get("gini_coefficient", 0.0)})
                    self.top10_share_history.append({"tick": self.tick, "value": econ_metrics.get("top_10_percent_share", 0.0) * 100})
                    self.bottom50_share_history.append({"tick": self.tick, "value": econ_metrics.get("bottom_50_percent_share", 0.0) * 100})
                    
                    # Consolidated Histories
                    self.price_history["food"].append({"tick": self.tick, "value": mean_prices["Food"]})
                    self.price_history["housing"].append({"tick": self.tick, "value": mean_prices["Housing"]})
                    self.price_history["services"].append({"tick": self.tick, "value": mean_prices["Services"]})
                    self.price_history["healthcare"].append({"tick": self.tick, "value": mean_prices["Healthcare"]})

                    self.supply_history["food"].append({"tick": self.tick, "value": supplies["Food"]})
                    self.supply_history["housing"].append({"tick": self.tick, "value": supplies["Housing"]})
                    self.supply_history["services"].append({"tick": self.tick, "value": supplies["Services"]})
                    self.supply_history["healthcare"].append({"tick": self.tick, "value": supplies["Healthcare"]})
                
                # Generate per-tick timing logs for frontend observability.
                tick_compute_ms = (asyncio.get_event_loop().time() - start_time) * 1000.0
                new_logs = [{
                    "tick": self.tick,
                    "type": "SYS",
                    "txt": f"Tick {self.tick} completed in {tick_compute_ms / 1000.0:.2f}s ({tick_compute_ms:.0f} ms)."
                }]
                
                # Construct state update
                state = {
                    "tick": self.tick,
                    "metrics": {
                        "unemployment": stats["unemployment_rate"] * 100,
                        "gdp": gdp / 1000000.0,
                        "govDebt": -self.economy.government.cash_balance / 1000000.0 if self.economy.government.cash_balance < 0 else 0,
                        "govProfit": fiscal_balance / 1000000.0,
                        "govRevenue": gov_revenue / 1000000.0,
                        "govTransfers": gov_transfers / 1000000.0,
                        "govInvestments": gov_investments / 1000000.0,
                        "govOwnedFirms": gov_owned_firms,
                        "activeLoans": active_loans,
                        "bondPurchases": gov_investments / 1000000.0,  # Proxy bond purchases as govt investments
                        "policyChanges": self.policy_changes,
                        "happiness": stats["mean_happiness"] * 100,
                        "avgWage": stats["mean_wage"],
                        "avgExpectedWage": stats.get("mean_expected_wage", 0.0),
                        "avgExpectedWageUnemployed": stats.get("mean_unemployed_expected_wage", 0.0),
                        "netWorth": total_net_worth / 1000000.0,
                        "giniCoefficient": econ_metrics.get("gini_coefficient", 0.0),
                        "top10Share": econ_metrics.get("top_10_percent_share", 0.0) * 100,
                        "bottom50Share": econ_metrics.get("bottom_50_percent_share", 0.0) * 100,
                        "tickComputeMs": tick_compute_ms,
                        "gdpHistory": self.gdp_history,
                        "unemploymentHistory": self.unemployment_history,
                        "wageHistory": self.wage_history,
                        "medianWageHistory": self.median_wage_history,
                        "happinessHistory": self.happiness_history,
                        "healthHistory": self.health_history,
                        "govProfitHistory": self.gov_profit_history,
                        "govDebtHistory": self.gov_debt_history,
                        "firmCountHistory": self.firm_count_history,
                        "netWorthHistory": self.net_worth_history,
                        "giniHistory": self.gini_history,
                        "top10ShareHistory": self.top10_share_history,
                        "bottom50ShareHistory": self.bottom50_share_history,
                        "priceHistory": self.price_history,
                        "supplyHistory": self.supply_history,
                        "trackedSubjects": tracked_subjects,
                        "trackedFirms": tracked_firms
                    },
                    "logs": new_logs,
                    "firm_stats": firm_stats
                }
                
                # Send update
                await self.active_websocket.send_json(state)
                
                # Throttle
                elapsed = asyncio.get_event_loop().time() - start_time
                await asyncio.sleep(max(0.05, 0.1 - elapsed)) # Slightly faster updates
                
        except Exception as e:
            logger.error(f"Simulation loop error: {e}")
            self.is_running = False
            self._close_warehouse_run("failed")
            if self.active_websocket:
                await self.active_websocket.send_json({"error": str(e)})

    async def _apply_config_updates(self, config_data: Dict[str, Any]):
        if not self.economy or not config_data:
            return

        if "wageTax" in config_data:
            self.economy.government.wage_tax_rate = config_data["wageTax"]
        if "profitTax" in config_data:
            self.economy.government.profit_tax_rate = config_data["profitTax"]

        if "minimumWage" in config_data:
            min_wage = config_data["minimumWage"]
            self.economy.config.labor_market.minimum_wage_floor = min_wage
            # Update firms in batches to avoid blocking
            for i, firm in enumerate(self.economy.firms):
                if firm.wage_offer < min_wage:
                    firm.wage_offer = min_wage
                # Yield control every 100 firms to prevent blocking
                if i % 100 == 0:
                    await asyncio.sleep(0)

        if "unemploymentBenefitRate" in config_data:
            rate = config_data["unemploymentBenefitRate"]
            # Calculate in batches to avoid blocking
            total_wages = 0
            employed_count = 0
            for i, h in enumerate(self.economy.households):
                if h.is_employed:
                    total_wages += h.wage
                    employed_count += 1
                # Yield control every 200 households to prevent blocking
                if i % 200 == 0:
                    await asyncio.sleep(0)
            avg_wage = total_wages / employed_count if employed_count > 0 else 30.0
            self.economy.government.unemployment_benefit_level = avg_wage * rate

        if "universalBasicIncome" in config_data:
            self.economy.government.ubi_amount = config_data["universalBasicIncome"]

        if "wealthTaxThreshold" in config_data:
            self.economy.government.wealth_tax_threshold = config_data["wealthTaxThreshold"]
        if "wealthTaxRate" in config_data:
            self.economy.government.wealth_tax_rate = config_data["wealthTaxRate"]

        if "inflationRate" in config_data:
            self.economy.government.target_inflation_rate = config_data["inflationRate"]
        if "birthRate" in config_data:
            self.economy.government.birth_rate = config_data["birthRate"]
            
        # Log policy changes
        for key, value in config_data.items():
            if key in ["wageTax", "profitTax", "minimumWage", "unemploymentBenefitRate", "universalBasicIncome", "wealthTaxRate"]:
                change_record = {
                    "tick": self.tick,
                    "policy": key,
                    "value": value,
                    "reason": f"User updated {key} to {value}"
                }
                self.policy_changes.insert(0, change_record)
                if len(self.policy_changes) > 5:
                    self.policy_changes.pop()

    async def update_config(self, config_data):
        if not self.economy:
            return

        if not self.is_running:
            await self._apply_config_updates(config_data)
        else:
            if self.pending_config_updates is None:
                self.pending_config_updates = dict(config_data)
            else:
                self.pending_config_updates.update(config_data)

manager = SimulationManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager.active_websocket = websocket
    logger.info("WebSocket connected")
    
    VALID_COMMANDS = {"SETUP", "START", "STOP", "RESET", "CONFIG", "STABILIZERS"}

    try:
        while True:
            raw = await websocket.receive_text()
            # Guard against oversized payloads (1 MB limit)
            if len(raw) > 1_048_576:
                await websocket.send_json({"error": "Payload too large (max 1 MB)"})
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            command = data.get("command")
            if command not in VALID_COMMANDS:
                await websocket.send_json({"error": f"Unknown command: {command}. Valid: {VALID_COMMANDS}"})
                continue

            if command == "SETUP":
                config = data.get("config", {})
                try:
                    manager.initialize(config)
                    await websocket.send_json({"type": "SETUP_COMPLETE"})
                except Exception as e:
                    logger.exception("SETUP failed")
                    await websocket.send_json({"error": f"SETUP failed: {e}"})
            elif command == "START":
                if not manager.economy:
                     # Auto-initialize if not done yet (fallback)
                     try:
                         manager.initialize()
                     except Exception as e:
                         logger.exception("Auto-initialize on START failed")
                         await websocket.send_json({"error": f"START failed: {e}"})
                         continue

                if not manager.is_running:
                    manager.is_running = True
                    asyncio.create_task(manager.run_loop())
                    await websocket.send_json({"type": "STARTED"})
            elif command == "STOP":
                manager.is_running = False
                manager._flush_tick_metrics_batch()
                await websocket.send_json({"type": "STOPPED"})
            elif command == "RESET":
                manager.is_running = False
                manager._close_warehouse_run("stopped")
                manager.tick = 0
                await websocket.send_json({"type": "RESET", "tick": 0})
            elif command == "CONFIG":
                config_data = data.get("config", {})
                await manager.update_config(config_data)
            elif command == "STABILIZERS":
                disable_flag = data.get("disable_stabilizers", False)
                disabled_agents = data.get("disabled_agents", [])
                manager.update_stabilizers(disable_flag, disabled_agents)
                await websocket.send_json({
                    "type": "STABILIZERS_UPDATED",
                    "state": manager.stabilizer_state
                })

    except WebSocketDisconnect:
        manager.is_running = False
        manager._close_warehouse_run("stopped")
        manager.active_websocket = None
        logger.info("Client disconnected")
    except Exception as e:
        manager.is_running = False
        manager._close_warehouse_run("failed")
        manager.active_websocket = None
        logger.exception("WebSocket loop crashed")
        try:
            await websocket.send_json({"error": f"WebSocket error: {e}"})
        except Exception:
            pass
