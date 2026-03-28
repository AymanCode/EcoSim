"""EcoSim WebSocket Server

FastAPI application that bridges the simulation engine with the React
frontend via a persistent WebSocket connection.  The server handles:

- **Simulation lifecycle**: setup → run (tick loop) → pause / resume / reset.
- **Real-time streaming**: each tick's aggregate metrics, per-subject
  histories, and wage-telemetry diagnostics are broadcast as JSON frames.
- **Runtime config**: stabiliser toggles, tax-rate sliders, and tracked-
  subject selection can be changed mid-run without restarting.
- **Data warehouse** (optional): when a warehouse backend (SQLite /
  TimescaleDB) is available, aggregate metrics, compact decision features,
  firm snapshots, sampled household snapshots, tracked-household history,
  and append-only events are batched and flushed for offline analysis.

Protocol
--------
The frontend opens a single ``/ws`` WebSocket.  Messages are JSON objects
with a ``type`` field:

    → ``setup``          — create economy, select households / firms to track
    → ``start``          — begin tick loop
    → ``pause`` / ``resume``
    → ``updateConfig``   — change tax rates or stabiliser flags mid-run
    ← ``tick``           — per-tick metrics payload (server → client)
    ← ``setup_complete`` — confirmation after economy initialisation
"""

import asyncio
import json
import logging
import logging.handlers
import sys
import os
import random
import time
import uuid
from collections import deque
from types import SimpleNamespace

# Add current directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import numpy as np

from config import CONFIG
from run_large_simulation import (
    create_large_economy,
    compute_firm_snapshot_rows,
    compute_firm_stats,
    compute_household_stats,
    compute_household_snapshot_rows,
    compute_sector_tick_rollups,
    compute_tracked_household_history_rows,
)
from data.versions import DECISION_FEATURE_VERSION, DIAGNOSTICS_VERSION, WAREHOUSE_SCHEMA_VERSION

_WAREHOUSE_IMPORT_ERROR = None
try:
    from data.models import (
        DecisionFeature,
        FirmSnapshot,
        HealthcareEvent,
        HouseholdSnapshot,
        LaborEvent,
        PolicyAction,
        PolicyConfig,
        RegimeEvent,
        SectorShortageDiagnostic,
        SectorTickMetrics,
        SimulationRun,
        TickDiagnostic,
        TrackedHouseholdHistory,
        TickMetrics,
    )
    from data.warehouse_factory import create_warehouse_manager
except Exception as exc:  # pragma: no cover - best-effort optional dependency
    _WAREHOUSE_IMPORT_ERROR = exc
    SimulationRun = None
    TickMetrics = None
    SectorTickMetrics = None
    DecisionFeature = None
    FirmSnapshot = None
    LaborEvent = None
    HealthcareEvent = None
    HouseholdSnapshot = None
    PolicyAction = None
    PolicyConfig = None
    RegimeEvent = None
    SectorShortageDiagnostic = None
    TrackedHouseholdHistory = None
    TickDiagnostic = None
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
    seed: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)
    disable_stabilizers: bool = False
    disabled_agents: List[str] = Field(default_factory=list)

    @field_validator("disabled_agents", mode="before")
    @classmethod
    def validate_agent_names(cls, v):
        """Reject agent names not in the allowed set."""
        valid = {"households", "firms", "government", "all"}
        for name in v:
            if name not in valid:
                raise ValueError(f"Invalid agent name '{name}'. Must be one of {valid}")
        return v


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "version": "2.0.0"}


def _get_warehouse_reader():
    """Return a warehouse manager for read-only API calls."""
    if create_warehouse_manager is None:
        raise HTTPException(status_code=503, detail="Warehouse backend is not available in this environment.")

    if manager.warehouse_manager is not None:
        return manager.warehouse_manager, False

    try:
        return create_warehouse_manager(), True
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Warehouse reader initialization failed: {exc}") from exc

class SimulationManager:
    """Owns the ``Economy`` instance and drives the tick loop.

    Lifecycle: ``initialize()`` creates the economy and selects tracked
    subjects → the WebSocket handler calls ``run_tick()`` in a loop →
    each tick computes stats, appends to history arrays, and emits a
    JSON frame.  ``update_stabilizers()`` and config-update handlers
    mutate economy state between ticks.

    All mutable simulation state lives here so that a single
    ``SimulationManager`` instance can be reset and re-initialised
    without restarting the server process.
    """

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
        self.sector_tick_metrics_batch: List[Any] = []
        self.decision_features_batch: List[Any] = []
        self.tick_diagnostics_batch: List[Any] = []
        self.sector_shortage_diagnostics_batch: List[Any] = []
        self.firm_snapshots_batch: List[Any] = []
        self.household_snapshots_batch: List[Any] = []
        self.tracked_household_history_batch: List[Any] = []
        self.labor_events_batch: List[Any] = []
        self.healthcare_events_batch: List[Any] = []
        self.policy_actions_batch: List[Any] = []
        self.regime_events_batch: List[Any] = []
        self.tick_metrics_batch_size = max(1, int(os.getenv("ECOSIM_TICK_BATCH_SIZE", "50")))
        # Snapshot rows are much denser than aggregate rows, so use a separate
        # threshold to avoid flushing on every tick once firm snapshots exist.
        self.snapshot_batch_size = max(1, int(os.getenv("ECOSIM_SNAPSHOT_BATCH_SIZE", "5000")))
        self.household_snapshot_stride = max(1, int(os.getenv("ECOSIM_HOUSEHOLD_SNAPSHOT_STRIDE", "5")))
        self.decision_feature_windows = {
            "unemployment_rate": deque(maxlen=20),
            "price_basket": deque(maxlen=20),
            "inflation_rate": deque(maxlen=20),
            "hires_rate": deque(maxlen=20),
            "layoffs_rate": deque(maxlen=20),
        }
        self.decision_context_window_size = max(5, int(os.getenv("ECOSIM_DECISION_CONTEXT_WINDOW", "40")))
        self.live_decision_context_history: deque[Dict[str, Any]] = deque(maxlen=self.decision_context_window_size)
        self.latest_decision_context: Optional[Dict[str, Any]] = None
        self._warehouse_exact_household_stats: Dict[str, float] | None = None
        self.last_fully_persisted_tick = 0
        self._previous_unemployment_rate = 0.0
        self._previous_avg_health = 0.0

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
        self.sector_tick_metrics_batch = []
        self.decision_features_batch = []
        self.tick_diagnostics_batch = []
        self.sector_shortage_diagnostics_batch = []
        self.firm_snapshots_batch = []
        self.household_snapshots_batch = []
        self.tracked_household_history_batch = []
        self.labor_events_batch = []
        self.healthcare_events_batch = []
        self.policy_actions_batch = []
        self.regime_events_batch = []
        self.last_fully_persisted_tick = 0
        self._previous_unemployment_rate = 0.0
        self._previous_avg_health = 0.0

        effective_config = dict(config)
        effective_config["num_households"] = int(num_households)
        effective_config["num_firms"] = int(num_firms)
        effective_config["seed"] = int(getattr(CONFIG, "random_seed", 0))
        effective_config["stabilizers"] = dict(self.stabilizer_state)

        try:
            run = SimulationRun(
                run_id=self.warehouse_run_id,
                status="running",
                seed=int(getattr(CONFIG, "random_seed", 0)),
                num_households=num_households,
                num_firms=num_firms,
                config_json=json.dumps(effective_config, sort_keys=True),
                code_version=os.getenv("ECOSIM_CODE_VERSION", "working-tree"),
                schema_version=WAREHOUSE_SCHEMA_VERSION,
                decision_feature_version=DECISION_FEATURE_VERSION,
                diagnostics_version=DIAGNOSTICS_VERSION,
                last_fully_persisted_tick=0,
                analysis_ready=False,
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
            if self.warehouse_run_id and self.warehouse_manager is not None:
                try:
                    self.warehouse_manager.update_run_status(
                        self.warehouse_run_id,
                        status="failed",
                        total_ticks=0,
                        analysis_ready=False,
                        termination_reason="run_open_failed",
                    )
                except Exception:
                    logger.exception("Failed to mark warehouse run open failure")
            self.warehouse_run_id = None
            self.tick_metrics_batch = []
            self.sector_tick_metrics_batch = []
            self.decision_features_batch = []
            self.tick_diagnostics_batch = []
            self.sector_shortage_diagnostics_batch = []
            self.firm_snapshots_batch = []
            self.household_snapshots_batch = []
            self.tracked_household_history_batch = []
            self.labor_events_batch = []
            self.healthcare_events_batch = []
            self.policy_actions_batch = []
            self.regime_events_batch = []
            self.last_fully_persisted_tick = 0

    def _max_buffered_tick(self) -> int:
        """Return the highest tick currently buffered across all warehouse batches."""
        max_tick = self.last_fully_persisted_tick
        for collection in (
            self.tick_metrics_batch,
            self.sector_tick_metrics_batch,
            self.decision_features_batch,
            self.tick_diagnostics_batch,
            self.sector_shortage_diagnostics_batch,
            self.firm_snapshots_batch,
            self.household_snapshots_batch,
            self.tracked_household_history_batch,
            self.labor_events_batch,
            self.healthcare_events_batch,
            self.policy_actions_batch,
            self.regime_events_batch,
        ):
            if collection:
                max_tick = max(max_tick, max(int(getattr(row, "tick", 0) or 0) for row in collection))
        return max_tick

    def _flush_warehouse_batches(self):
        """Persist buffered aggregate, decision, snapshot, and event rows."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
            or (
                not self.tick_metrics_batch
                and not self.sector_tick_metrics_batch
                and not self.decision_features_batch
                and not self.tick_diagnostics_batch
                and not self.sector_shortage_diagnostics_batch
                and not self.firm_snapshots_batch
                and not self.household_snapshots_batch
                and not self.tracked_household_history_batch
                and not self.labor_events_batch
                and not self.healthcare_events_batch
                and not self.policy_actions_batch
                and not self.regime_events_batch
            )
        ):
            return True

        persisted_tick = self._max_buffered_tick()
        try:
            self.warehouse_manager.persist_flush_bundle(
                run_id=self.warehouse_run_id,
                last_fully_persisted_tick=persisted_tick,
                tick_metrics=self.tick_metrics_batch,
                sector_tick_metrics=self.sector_tick_metrics_batch,
                decision_features=self.decision_features_batch,
                tick_diagnostics=self.tick_diagnostics_batch,
                sector_shortage_diagnostics=self.sector_shortage_diagnostics_batch,
                firm_snapshots=self.firm_snapshots_batch,
                household_snapshots=self.household_snapshots_batch,
                tracked_household_history=self.tracked_household_history_batch,
                labor_events=self.labor_events_batch,
                healthcare_events=self.healthcare_events_batch,
                policy_actions=self.policy_actions_batch,
                regime_events=self.regime_events_batch,
            )
            self.tick_metrics_batch = []
            self.sector_tick_metrics_batch = []
            self.decision_features_batch = []
            self.tick_diagnostics_batch = []
            self.sector_shortage_diagnostics_batch = []
            self.firm_snapshots_batch = []
            self.household_snapshots_batch = []
            self.tracked_household_history_batch = []
            self.labor_events_batch = []
            self.healthcare_events_batch = []
            self.policy_actions_batch = []
            self.regime_events_batch = []
            self.last_fully_persisted_tick = max(self.last_fully_persisted_tick, persisted_tick)
            return True
        except Exception as exc:
            logger.error("Warehouse batch flush failed: %s", exc)
            return False

    def _build_exact_warehouse_aggregates(
        self,
        tick_duration_ms: float,
        gdp: float,
        current_gov_cash: float,
        fiscal_balance: float,
    ) -> tuple[Optional[Any], List[Any]]:
        """Build exact per-tick warehouse rows.

        The websocket path intentionally caches some frontend metrics every few
        ticks to keep the UI lightweight. The warehouse should not reuse that
        cached payload because it would record repeated stale values. This
        helper rebuilds only the aggregate facts needed for persistence:

        - one exact ``tick_metrics`` row
        - one exact ``sector_tick_metrics`` row per sector

        The work stays bounded: one firm scan, one vectorized household stats
        pass, and one household inventory valuation pass.
        """
        if not self.economy or TickMetrics is None:
            return None, []

        sector_rollups = compute_sector_tick_rollups(self.economy.firms)
        price_by_sector = {row["sector"]: row["mean_price"] for row in sector_rollups}
        household_stats = compute_household_stats(self.economy.households)
        self._warehouse_exact_household_stats = household_stats

        total_net_worth = 0.0
        for household in self.economy.households:
            total_net_worth += household.cash_balance
            for good, qty in household.goods_inventory.items():
                sector = "Food"
                lower_good = good.lower()
                if "housing" in lower_good:
                    sector = "Housing"
                elif "service" in lower_good:
                    sector = "Services"
                elif "health" in lower_good or "medical" in lower_good:
                    sector = "Healthcare"
                total_net_worth += float(qty) * float(price_by_sector.get(sector, 0.0))

        labor_diag = getattr(self.economy, "last_labor_diagnostics", {}) or {}
        total_households = max(1, int(household_stats.get("total_households", 0)))
        employed_count = float(household_stats.get("employed_count", 0))
        seeker_count = float(labor_diag.get("labor_seekers_total", 0.0))
        labor_force_participation = min(
            100.0,
            max(0.0, ((employed_count + seeker_count) / total_households) * 100.0),
        )

        open_vacancies = int(sum(max(0, row["vacancies"]) for row in sector_rollups))
        total_hires = int(sum(max(0, int(getattr(firm, "last_tick_actual_hires", 0))) for firm in self.economy.firms))
        total_layoffs = int(sum(len(getattr(firm, "planned_layoffs_ids", [])) for firm in self.economy.firms))
        healthcare_queue_depth = int(
            sum(
                len(getattr(firm, "healthcare_queue", []))
                for firm in self.economy.firms
                if (firm.good_category or "").lower() == "healthcare"
            )
        )
        struggling_firms = int(sum(1 for firm in self.economy.firms if firm.cash_balance <= 0))

        tick_metric = TickMetrics(
            run_id=self.warehouse_run_id,
            tick=self.tick,
            gdp=float(gdp),
            unemployment_rate=float(household_stats.get("unemployment_rate", 0.0) * 100.0),
            mean_wage=float(household_stats.get("mean_wage", 0.0)),
            median_wage=float(household_stats.get("median_wage", 0.0)),
            avg_happiness=float(household_stats.get("mean_happiness", 0.0) * 100.0),
            avg_health=float(household_stats.get("mean_health", 0.0) * 100.0),
            avg_morale=float(household_stats.get("mean_morale", 0.0) * 100.0),
            total_net_worth=float(total_net_worth),
            gini_coefficient=float(household_stats.get("gini_coefficient", 0.0)),
            top10_wealth_share=float(household_stats.get("top10_wealth_share", 0.0) * 100.0),
            bottom50_wealth_share=float(household_stats.get("bottom50_wealth_share", 0.0) * 100.0),
            gov_cash_balance=float(current_gov_cash),
            gov_profit=float(fiscal_balance),
            total_firms=int(len(self.economy.firms)),
            struggling_firms=struggling_firms,
            tick_duration_ms=float(tick_duration_ms),
            labor_force_participation=float(labor_force_participation),
            open_vacancies=open_vacancies,
            total_hires=total_hires,
            total_layoffs=total_layoffs,
            healthcare_queue_depth=healthcare_queue_depth,
            avg_food_price=float(price_by_sector.get("Food", 0.0)),
            avg_housing_price=float(price_by_sector.get("Housing", 0.0)),
            avg_services_price=float(price_by_sector.get("Services", 0.0)),
        )

        sector_metric_rows: List[Any] = []
        if SectorTickMetrics is not None:
            for row in sector_rollups:
                sector_metric_rows.append(
                    SectorTickMetrics(
                        run_id=self.warehouse_run_id,
                        tick=self.tick,
                        sector=str(row["sector"]),
                        firm_count=int(row["firm_count"]),
                        employees=int(row["employees"]),
                        vacancies=int(row["vacancies"]),
                        mean_wage_offer=float(row["mean_wage_offer"]),
                        mean_price=float(row["mean_price"]),
                        mean_inventory=float(row["mean_inventory"]),
                        total_output=float(row["total_output"]),
                        total_revenue=float(row["total_revenue"]),
                        total_profit=float(row["total_profit"]),
                    )
                )

        return tick_metric, sector_metric_rows

    @staticmethod
    def _rolling_mean(values: deque[float], window: int) -> float:
        """Return the mean of the most recent ``window`` observations."""
        if not values:
            return 0.0
        if len(values) <= window:
            return float(sum(values) / len(values))
        recent = list(values)[-window:]
        return float(sum(recent) / len(recent))

    @staticmethod
    def _safe_pct_change(current: float, previous: float) -> float:
        """Return percentage change while guarding against zero baselines."""
        if abs(previous) <= 1e-9:
            return 0.0
        return float(((current - previous) / previous) * 100.0)

    @staticmethod
    def _clamp_feature(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
        """Bound a derived decision score to a stable range."""
        return float(max(lower, min(upper, value)))

    def _build_live_decision_metric(
        self,
        stats: Dict[str, float],
        gdp: float,
        current_gov_cash: float,
        fiscal_balance: float,
        mean_prices: Dict[str, float],
    ) -> Any:
        """Build a narrow tick-metric-like object for live decision context.

        This path is used when the warehouse is disabled. It reuses the
        already-computed server metrics and only adds a small firm scan for the
        labor and healthcare pressure fields that the decision layer needs.
        """
        open_vacancies = 0
        total_hires = 0
        total_layoffs = 0
        healthcare_queue_depth = 0
        for firm in self.economy.firms:
            open_vacancies += max(0, int(getattr(firm, "planned_hires_count", 0)))
            total_hires += max(0, int(getattr(firm, "last_tick_actual_hires", 0)))
            total_layoffs += len(getattr(firm, "planned_layoffs_ids", []))
            if (firm.good_category or "").lower() == "healthcare":
                healthcare_queue_depth += len(getattr(firm, "healthcare_queue", []))

        return SimpleNamespace(
            tick=self.tick,
            gdp=float(gdp),
            unemployment_rate=float(stats.get("unemployment_rate", 0.0) * 100.0),
            mean_wage=float(stats.get("mean_wage", 0.0)),
            top10_wealth_share=float(stats.get("top10_wealth_share", 0.0) * 100.0),
            bottom50_wealth_share=float(stats.get("bottom50_wealth_share", 0.0) * 100.0),
            gini_coefficient=float(stats.get("gini_coefficient", 0.0)),
            gov_cash_balance=float(current_gov_cash),
            gov_profit=float(fiscal_balance),
            open_vacancies=int(open_vacancies),
            total_hires=int(total_hires),
            total_layoffs=int(total_layoffs),
            healthcare_queue_depth=int(healthcare_queue_depth),
            avg_food_price=float(mean_prices.get("Food", 0.0)),
            avg_housing_price=float(mean_prices.get("Housing", 0.0)),
            avg_services_price=float(mean_prices.get("Services", 0.0)),
        )

    def _record_live_decision_context(
        self,
        decision_feature: DecisionFeature,
        metric_like: Any,
        source: str,
    ) -> None:
        """Append a compact rolling decision-context row for future agents."""
        household_stats = self._warehouse_exact_household_stats or {}
        row = {
            "tick": int(self.tick),
            "source": str(source),
            "unemploymentRate": float(getattr(metric_like, "unemployment_rate", 0.0) or 0.0),
            "meanWage": float(getattr(metric_like, "mean_wage", 0.0) or 0.0),
            "meanUnemployedExpectedWage": float(household_stats.get("mean_unemployed_expected_wage", 0.0)),
            "gdp": float(getattr(metric_like, "gdp", 0.0) or 0.0),
            "govCashBalance": float(getattr(metric_like, "gov_cash_balance", 0.0) or 0.0),
            "govProfit": float(getattr(metric_like, "gov_profit", 0.0) or 0.0),
            "openVacancies": int(getattr(metric_like, "open_vacancies", 0) or 0),
            "totalHires": int(getattr(metric_like, "total_hires", 0) or 0),
            "totalLayoffs": int(getattr(metric_like, "total_layoffs", 0) or 0),
            "healthcareQueueDepth": int(getattr(metric_like, "healthcare_queue_depth", 0) or 0),
            "avgFoodPrice": float(getattr(metric_like, "avg_food_price", 0.0) or 0.0),
            "avgHousingPrice": float(getattr(metric_like, "avg_housing_price", 0.0) or 0.0),
            "avgServicesPrice": float(getattr(metric_like, "avg_services_price", 0.0) or 0.0),
            "unemploymentShortMa": float(decision_feature.unemployment_short_ma),
            "unemploymentLongMa": float(decision_feature.unemployment_long_ma),
            "inflationShortMa": float(decision_feature.inflation_short_ma),
            "hiringMomentum": float(decision_feature.hiring_momentum),
            "layoffMomentum": float(decision_feature.layoff_momentum),
            "vacancyFillRatio": float(decision_feature.vacancy_fill_ratio),
            "wagePressure": float(decision_feature.wage_pressure),
            "healthcarePressure": float(decision_feature.healthcare_pressure),
            "consumerDistressScore": float(decision_feature.consumer_distress_score),
            "fiscalStressScore": float(decision_feature.fiscal_stress_score),
            "inequalityPressureScore": float(decision_feature.inequality_pressure_score),
        }
        self.live_decision_context_history.append(row)
        self.latest_decision_context = row

    def get_live_decision_context(self, window: int = 20) -> Dict[str, Any]:
        """Return the most recent rolling decision context for live agents."""
        effective_window = max(1, min(int(window), self.decision_context_window_size))
        history = list(self.live_decision_context_history)[-effective_window:]
        latest = history[-1] if history else self.latest_decision_context
        return {
            "tick": int(self.tick),
            "windowSize": effective_window,
            "historyCount": len(history),
            "latest": latest,
            "history": history,
            "recentPolicyChanges": self.policy_changes[-5:],
        }

    def _build_decision_feature_row(self, tick_metric: Any) -> Optional[Any]:
        """Build one compact decision-context row for the current tick.

        The warehouse already stores raw facts. This helper converts those
        facts into a small, trend-aware feature set that a future policy agent
        or local LLM can consume without scanning raw tables. The features are
        computed from:

        - current exact tick aggregates
        - a tiny in-memory rolling window kept on the server
        - current labor and healthcare pressure state

        The live simulation does not query the warehouse back to compute these.
        """
        if (
            not self.economy
            or DecisionFeature is None
            or self.warehouse_run_id is None
            or tick_metric is None
        ):
            return None

        household_stats = self._warehouse_exact_household_stats or {}
        total_households = max(1.0, float(household_stats.get("total_households", 0.0)))

        basket_components = [
            float(getattr(tick_metric, "avg_food_price", 0.0) or 0.0),
            float(getattr(tick_metric, "avg_housing_price", 0.0) or 0.0),
            float(getattr(tick_metric, "avg_services_price", 0.0) or 0.0),
        ]
        nonzero_components = [value for value in basket_components if value > 0.0]
        price_basket = float(sum(nonzero_components) / len(nonzero_components)) if nonzero_components else 0.0

        hires_rate = float(getattr(tick_metric, "total_hires", 0) or 0) / total_households * 100.0
        layoffs_rate = float(getattr(tick_metric, "total_layoffs", 0) or 0) / total_households * 100.0

        windows = self.decision_feature_windows
        previous_price_basket = windows["price_basket"][-1] if windows["price_basket"] else price_basket
        inflation_point = self._safe_pct_change(price_basket, previous_price_basket)

        windows["unemployment_rate"].append(float(getattr(tick_metric, "unemployment_rate", 0.0) or 0.0))
        windows["price_basket"].append(price_basket)
        windows["inflation_rate"].append(inflation_point)
        windows["hires_rate"].append(hires_rate)
        windows["layoffs_rate"].append(layoffs_rate)

        unemployment_short_ma = self._rolling_mean(windows["unemployment_rate"], 5)
        unemployment_long_ma = self._rolling_mean(windows["unemployment_rate"], 20)
        inflation_short_ma = self._rolling_mean(windows["inflation_rate"], 5)

        hiring_short = self._rolling_mean(windows["hires_rate"], 5)
        hiring_long = self._rolling_mean(windows["hires_rate"], 20)
        layoff_short = self._rolling_mean(windows["layoffs_rate"], 5)
        layoff_long = self._rolling_mean(windows["layoffs_rate"], 20)

        vacancy_fill_ratio = 1.0
        open_vacancies = float(getattr(tick_metric, "open_vacancies", 0) or 0)
        if open_vacancies > 0.0:
            vacancy_fill_ratio = self._clamp_feature(
                float(getattr(tick_metric, "total_hires", 0) or 0) / open_vacancies,
                lower=0.0,
                upper=1.0,
            )

        min_wage_floor = float(getattr(self.economy.config.labor_market, "minimum_wage_floor", 1.0))
        mean_wage = float(getattr(tick_metric, "mean_wage", 0.0) or 0.0)
        mean_unemployed_expected_wage = float(household_stats.get("mean_unemployed_expected_wage", 0.0))
        wage_pressure_denominator = max(1.0, mean_wage, min_wage_floor)
        wage_pressure = ((mean_unemployed_expected_wage - mean_wage) / wage_pressure_denominator) * 100.0

        healthcare_staff = 0
        healthcare_queue_depth = int(getattr(tick_metric, "healthcare_queue_depth", 0) or 0)
        for firm in self.economy.firms:
            if (firm.good_category or "").lower() == "healthcare":
                healthcare_staff += max(0, int(getattr(firm, "medical_staff_count", len(getattr(firm, "employees", [])))))
        healthcare_pressure = float(healthcare_queue_depth / max(1, healthcare_staff))

        consumer_distress_score = self._clamp_feature(
            float(getattr(tick_metric, "unemployment_rate", 0.0) or 0.0) * 0.35
            + float(household_stats.get("cash_below_100_share", 0.0)) * 100.0 * 0.25
            + float(household_stats.get("health_below_50_share", 0.0)) * 100.0 * 0.20
            + float(household_stats.get("happiness_below_50_share", 0.0)) * 100.0 * 0.20
        )

        gdp = max(1.0, float(getattr(tick_metric, "gdp", 0.0) or 0.0))
        negative_cash_pct_gdp = max(0.0, -float(getattr(tick_metric, "gov_cash_balance", 0.0) or 0.0)) / gdp * 100.0
        negative_flow_pct_gdp = max(0.0, -float(getattr(tick_metric, "gov_profit", 0.0) or 0.0)) / gdp * 100.0
        fiscal_stress_score = self._clamp_feature(
            negative_cash_pct_gdp * 0.6 + negative_flow_pct_gdp * 0.4
        )

        top10_share = float(getattr(tick_metric, "top10_wealth_share", 0.0) or 0.0)
        bottom50_share = float(getattr(tick_metric, "bottom50_wealth_share", 0.0) or 0.0)
        inequality_pressure_score = self._clamp_feature(
            float(getattr(tick_metric, "gini_coefficient", 0.0) or 0.0) * 100.0 * 0.6
            + max(0.0, top10_share - bottom50_share) * 0.4
        )

        return DecisionFeature(
            run_id=self.warehouse_run_id,
            tick=self.tick,
            unemployment_short_ma=float(unemployment_short_ma),
            unemployment_long_ma=float(unemployment_long_ma),
            inflation_short_ma=float(inflation_short_ma),
            hiring_momentum=float(hiring_short - hiring_long),
            layoff_momentum=float(layoff_short - layoff_long),
            vacancy_fill_ratio=float(vacancy_fill_ratio),
            wage_pressure=float(wage_pressure),
            healthcare_pressure=float(healthcare_pressure),
            consumer_distress_score=float(consumer_distress_score),
            fiscal_stress_score=float(fiscal_stress_score),
            inequality_pressure_score=float(inequality_pressure_score),
        )

    @staticmethod
    def _dominant_driver(components: Dict[str, float], stable_label: str = "stable") -> str:
        """Return the highest-pressure label, falling back to a stable code."""
        if not components:
            return stable_label
        best_key = max(components, key=components.get)
        if components[best_key] <= 1e-9:
            return stable_label
        return str(best_key)

    def _build_tick_diagnostic_row(self, tick_metric: Any) -> Optional[Any]:
        """Build one compact per-tick diagnostics row for policy/debug use."""
        if (
            not self.economy
            or TickDiagnostic is None
            or self.warehouse_run_id is None
            or tick_metric is None
        ):
            return None

        household_stats = self._warehouse_exact_household_stats or {}
        labor_diag = getattr(self.economy, "last_labor_diagnostics", {}) or {}
        health_diag = getattr(self.economy, "last_health_diagnostics", {}) or {}
        firm_diag = getattr(self.economy, "last_firm_distress_diagnostics", {}) or {}
        housing_diag = getattr(self.economy, "last_housing_diagnostics", {}) or {}
        sector_shortages = getattr(self.economy, "last_sector_shortage_diagnostics", []) or []

        unemployment_rate = float(getattr(tick_metric, "unemployment_rate", 0.0) or 0.0)
        avg_health = float(getattr(tick_metric, "avg_health", 0.0) or 0.0)
        unemployment_change_pp = float(unemployment_rate - self._previous_unemployment_rate)
        avg_health_change_pp = float(avg_health - self._previous_avg_health)

        layoffs_count = int(getattr(tick_metric, "total_layoffs", 0) or 0)
        hires_count = int(getattr(tick_metric, "total_hires", 0) or 0)
        failed_hiring_firm_count = int(firm_diag.get("failed_hiring_firm_count", 0.0))
        failed_hiring_roles_count = int(firm_diag.get("failed_hiring_roles_count", 0.0))
        wage_mismatch_seeker_count = int(labor_diag.get("labor_seekers_wage_ineligible", 0.0))
        health_blocked_worker_count = int(labor_diag.get("labor_cannot_work", 0.0))
        inactive_work_capable_count = int(labor_diag.get("labor_unemployed_not_searching", 0.0))
        low_health_share = float(household_stats.get("health_below_50_share", 0.0) * 100.0)
        food_insecure_share = float(household_stats.get("food_insecure_share", 0.0) * 100.0)
        cash_stressed_share = float(household_stats.get("cash_below_100_share", 0.0) * 100.0)
        pending_healthcare_visits_total = int(household_stats.get("pending_healthcare_visits_total", 0))
        healthcare_queue_depth = int(getattr(tick_metric, "healthcare_queue_depth", 0) or 0)
        healthcare_completed_count = int(health_diag.get("healthcare_completed_count", 0.0))
        healthcare_denied_count = int(health_diag.get("healthcare_denied_count", 0.0))
        burn_mode_firm_count = int(firm_diag.get("burn_mode_firm_count", 0.0))
        survival_mode_firm_count = int(firm_diag.get("survival_mode_firm_count", 0.0))
        zero_cash_firm_count = int(firm_diag.get("zero_cash_firm_count", 0.0))
        weak_demand_firm_count = int(firm_diag.get("weak_demand_firm_count", 0.0))
        inventory_pressure_firm_count = int(firm_diag.get("inventory_pressure_firm_count", 0.0))
        bankruptcy_count = int(firm_diag.get("bankruptcy_count", 0.0))
        eviction_count = int(housing_diag.get("eviction_count", 0.0))
        housing_failure_count = int(housing_diag.get("housing_failure_count", 0.0))
        housing_unaffordable_count = int(housing_diag.get("housing_unaffordable_count", 0.0))
        housing_no_supply_count = int(housing_diag.get("housing_no_supply_count", 0.0))
        homeless_household_count = int(housing_diag.get("homeless_household_count", 0.0))
        shortage_active_sector_count = int(sum(1 for row in sector_shortages if bool(row.get("shortage_active", False))))

        unemployment_primary_driver = self._dominant_driver({
            "layoffs": float(layoffs_count),
            "failed_hiring": float(failed_hiring_roles_count),
            "wage_mismatch": float(wage_mismatch_seeker_count),
            "health_block": float(health_blocked_worker_count),
            "inactive_supply": float(inactive_work_capable_count),
        })
        health_primary_driver = self._dominant_driver({
            "food_shortfall": float(food_insecure_share),
            "healthcare_denial": float(healthcare_denied_count),
            "healthcare_queue": float(healthcare_queue_depth),
            "broad_distress": float(cash_stressed_share),
        })
        firm_distress_primary_driver = self._dominant_driver({
            "burn_mode": float(burn_mode_firm_count),
            "survival_mode": float(survival_mode_firm_count),
            "failed_hiring": float(failed_hiring_firm_count),
            "weak_demand": float(weak_demand_firm_count),
            "inventory_pressure": float(inventory_pressure_firm_count),
        })
        housing_primary_driver = self._dominant_driver({
            "unaffordable": float(housing_unaffordable_count),
            "no_supply": float(housing_no_supply_count),
            "eviction": float(eviction_count),
        })

        self._previous_unemployment_rate = unemployment_rate
        self._previous_avg_health = avg_health

        return TickDiagnostic(
            run_id=self.warehouse_run_id,
            tick=self.tick,
            unemployment_change_pp=float(unemployment_change_pp),
            unemployment_primary_driver=unemployment_primary_driver,
            layoffs_count=layoffs_count,
            hires_count=hires_count,
            failed_hiring_firm_count=failed_hiring_firm_count,
            failed_hiring_roles_count=failed_hiring_roles_count,
            wage_mismatch_seeker_count=wage_mismatch_seeker_count,
            health_blocked_worker_count=health_blocked_worker_count,
            inactive_work_capable_count=inactive_work_capable_count,
            avg_health_change_pp=float(avg_health_change_pp),
            health_primary_driver=health_primary_driver,
            low_health_share=float(low_health_share),
            food_insecure_share=float(food_insecure_share),
            cash_stressed_share=float(cash_stressed_share),
            pending_healthcare_visits_total=pending_healthcare_visits_total,
            healthcare_queue_depth=healthcare_queue_depth,
            healthcare_completed_count=healthcare_completed_count,
            healthcare_denied_count=healthcare_denied_count,
            firm_distress_primary_driver=firm_distress_primary_driver,
            burn_mode_firm_count=burn_mode_firm_count,
            survival_mode_firm_count=survival_mode_firm_count,
            zero_cash_firm_count=zero_cash_firm_count,
            weak_demand_firm_count=weak_demand_firm_count,
            inventory_pressure_firm_count=inventory_pressure_firm_count,
            bankruptcy_count=bankruptcy_count,
            housing_primary_driver=housing_primary_driver,
            eviction_count=eviction_count,
            housing_failure_count=housing_failure_count,
            housing_unaffordable_count=housing_unaffordable_count,
            housing_no_supply_count=housing_no_supply_count,
            homeless_household_count=homeless_household_count,
            shortage_active_sector_count=shortage_active_sector_count,
        )

    def _build_sector_shortage_diagnostic_rows(self) -> List[Any]:
        """Build compact per-sector shortage rows for the current tick."""
        if (
            not self.economy
            or SectorShortageDiagnostic is None
            or self.warehouse_run_id is None
        ):
            return []

        rows = getattr(self.economy, "last_sector_shortage_diagnostics", []) or []
        return [
            SectorShortageDiagnostic(
                run_id=self.warehouse_run_id,
                tick=self.tick,
                sector=str(row.get("sector", "Other")),
                shortage_active=bool(row.get("shortage_active", False)),
                shortage_severity=float(row.get("shortage_severity", 0.0) or 0.0),
                primary_driver=str(row.get("primary_driver", "stable")),
                mean_sell_through_rate=float(row.get("mean_sell_through_rate", 0.0) or 0.0),
                vacancy_pressure=float(row.get("vacancy_pressure", 0.0) or 0.0),
                inventory_pressure=float(row.get("inventory_pressure", 0.0) or 0.0),
                price_pressure=float(row.get("price_pressure", 0.0) or 0.0),
                queue_pressure=float(row.get("queue_pressure", 0.0) or 0.0),
                occupancy_pressure=float(row.get("occupancy_pressure", 0.0) or 0.0),
            )
            for row in rows
        ]

    def _buffer_regime_events(self) -> None:
        """Convert economy-emitted regime transition facts into warehouse rows."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
            or RegimeEvent is None
        ):
            return

        for idx, event in enumerate(getattr(self.economy, "last_regime_events", []) or []):
            payload = event.get("payload")
            self.regime_events_batch.append(
                RegimeEvent(
                    run_id=self.warehouse_run_id,
                    tick=int(event.get("tick", self.tick)),
                    event_type=str(event.get("event_type", "unknown")),
                    entity_type=str(event.get("entity_type", "unknown")),
                    entity_id=int(event["entity_id"]) if event.get("entity_id") is not None else None,
                    sector=str(event["sector"]) if event.get("sector") is not None else None,
                    reason_code=str(event["reason_code"]) if event.get("reason_code") is not None else None,
                    severity=float(event["severity"]) if event.get("severity") is not None else None,
                    metric_value=float(event["metric_value"]) if event.get("metric_value") is not None else None,
                    payload_json=json.dumps(payload, sort_keys=True) if payload is not None else None,
                    event_key=(
                        f"regime:{self.warehouse_run_id}:{int(event.get('tick', self.tick))}:"
                        f"{idx}:{event.get('event_type', 'unknown')}:{event.get('entity_type', 'unknown')}:"
                        f"{event.get('entity_id', 'none')}:{event.get('sector', 'none')}"
                    ),
                )
            )

    def _build_firm_snapshot_rows(self) -> List[Any]:
        """Build exact per-firm warehouse rows for the current tick.

        Firm snapshots are intentionally separate from aggregate metrics so the
        warehouse can store one analytical firm row per tick without coupling
        the schema to any frontend card or leaderboard shape.
        """
        if not self.economy or FirmSnapshot is None or self.warehouse_run_id is None:
            return []

        snapshot_rows = compute_firm_snapshot_rows(
            self.economy.firms,
            household_lookup=getattr(self.economy, "household_lookup", None),
        )
        return [
            FirmSnapshot(
                run_id=self.warehouse_run_id,
                tick=self.tick,
                firm_id=int(row["firm_id"]),
                firm_name=str(row["firm_name"]),
                sector=str(row["sector"]),
                is_baseline=bool(row["is_baseline"]),
                employee_count=int(row["employee_count"]),
                doctor_employee_count=int(row["doctor_employee_count"]),
                medical_employee_count=int(row["medical_employee_count"]),
                planned_hires_count=int(row["planned_hires_count"]),
                planned_layoffs_count=int(row["planned_layoffs_count"]),
                actual_hires_count=int(row["actual_hires_count"]),
                wage_offer=float(row["wage_offer"]),
                price=float(row["price"]),
                inventory_units=float(row["inventory_units"]),
                output_units=float(row["output_units"]),
                cash_balance=float(row["cash_balance"]),
                revenue=float(row["revenue"]),
                profit=float(row["profit"]),
                quality_level=float(row["quality_level"]),
                queue_depth=int(row["queue_depth"]),
                visits_completed=float(row["visits_completed"]),
                burn_mode=bool(row["burn_mode"]),
                zero_cash_streak=int(row["zero_cash_streak"]),
            )
            for row in snapshot_rows
        ]

    def _build_household_snapshot_rows(self) -> List[Any]:
        """Build sampled full-population household snapshot rows.

        This is the expensive household-state table, so the caller controls the
        cadence and should avoid invoking it every tick for large runs.
        """
        if not self.economy or HouseholdSnapshot is None or self.warehouse_run_id is None:
            return []

        snapshot_rows = compute_household_snapshot_rows(self.economy.households)
        return [
            HouseholdSnapshot(
                run_id=self.warehouse_run_id,
                tick=self.tick,
                household_id=int(row["household_id"]),
                state=str(row["state"]),
                medical_status=str(row["medical_status"]),
                employer_id=int(row["employer_id"]) if row["employer_id"] is not None else None,
                is_employed=bool(row["is_employed"]),
                can_work=bool(row["can_work"]),
                cash_balance=float(row["cash_balance"]),
                wage=float(row["wage"]),
                last_wage_income=float(row["last_wage_income"]),
                last_transfer_income=float(row["last_transfer_income"]),
                last_dividend_income=float(row["last_dividend_income"]),
                reservation_wage=float(row["reservation_wage"]),
                expected_wage=float(row["expected_wage"]),
                skill_level=float(row["skill_level"]),
                health=float(row["health"]),
                happiness=float(row["happiness"]),
                morale=float(row["morale"]),
                food_security=float(row["food_security"]),
                housing_security=bool(row["housing_security"]),
                unemployment_duration=int(row["unemployment_duration"]),
                pending_healthcare_visits=int(row["pending_healthcare_visits"]),
            )
            for row in snapshot_rows
        ]

    def _build_tracked_household_history_rows(self) -> List[Any]:
        """Build every-tick history rows for the small tracked-household subset."""
        if (
            not self.economy
            or TrackedHouseholdHistory is None
            or self.warehouse_run_id is None
            or not self.tracked_household_ids
        ):
            return []

        history_rows = compute_tracked_household_history_rows(
            self.economy.household_lookup,
            self.tracked_household_ids,
        )
        return [
            TrackedHouseholdHistory(
                run_id=self.warehouse_run_id,
                tick=self.tick,
                household_id=int(row["household_id"]),
                state=str(row["state"]),
                medical_status=str(row["medical_status"]),
                employer_id=int(row["employer_id"]) if row["employer_id"] is not None else None,
                is_employed=bool(row["is_employed"]),
                can_work=bool(row["can_work"]),
                cash_balance=float(row["cash_balance"]),
                wage=float(row["wage"]),
                expected_wage=float(row["expected_wage"]),
                reservation_wage=float(row["reservation_wage"]),
                health=float(row["health"]),
                happiness=float(row["happiness"]),
                morale=float(row["morale"]),
                skill_level=float(row["skill_level"]),
                unemployment_duration=int(row["unemployment_duration"]),
                pending_healthcare_visits=int(row["pending_healthcare_visits"]),
            )
            for row in history_rows
        ]

    def _snapshot_government_policy(self) -> Dict[str, float]:
        """Capture the current government policy surface for change detection."""
        if not self.economy:
            return {}

        gov = self.economy.government
        return {
            "wage_tax_rate": float(getattr(gov, "wage_tax_rate", 0.0)),
            "profit_tax_rate": float(getattr(gov, "profit_tax_rate", 0.0)),
            "unemployment_benefit_level": float(getattr(gov, "unemployment_benefit_level", 0.0)),
            "ubi_amount": float(getattr(gov, "ubi_amount", 0.0)),
            "wealth_tax_threshold": float(getattr(gov, "wealth_tax_threshold", 0.0)),
            "wealth_tax_rate": float(getattr(gov, "wealth_tax_rate", 0.0)),
            "target_inflation_rate": float(getattr(gov, "target_inflation_rate", 0.0)),
            "birth_rate": float(getattr(gov, "birth_rate", 0.0)),
        }

    def _append_policy_change_ui_record(self, policy: str, value: float, reason: str) -> None:
        """Maintain the small recent-policy list used by the frontend."""
        change_record = {
            "tick": self.tick,
            "policy": policy,
            "value": value,
            "reason": reason,
        }
        self.policy_changes.insert(0, change_record)
        if len(self.policy_changes) > 5:
            self.policy_changes.pop()

    def _buffer_policy_action(self, actor: str, action_type: str, payload: Dict[str, Any], reason_summary: str) -> None:
        """Append one policy action to the warehouse batch."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
            or PolicyAction is None
        ):
            return

        self.policy_actions_batch.append(
            PolicyAction(
                run_id=self.warehouse_run_id,
                tick=int(self.tick),
                actor=str(actor),
                action_type=str(action_type),
                payload_json=json.dumps(payload, sort_keys=True),
                reason_summary=str(reason_summary),
                event_key=(
                    f"policy:{self.warehouse_run_id}:{int(self.tick)}:"
                    f"{len(self.policy_actions_batch)}:{actor}:{action_type}"
                ),
            )
        )

    def _record_automatic_policy_changes(
        self,
        policy_before: Dict[str, float],
        policy_after: Dict[str, float],
    ) -> None:
        """Persist government auto-adjustments when policy values change."""
        tolerance = 1e-9
        for field_name, before_value in policy_before.items():
            after_value = float(policy_after.get(field_name, before_value))
            if abs(after_value - before_value) <= tolerance:
                continue

            reason = (
                f"Automatic government adjustment changed {field_name} "
                f"from {before_value:.6f} to {after_value:.6f}"
            )
            self._append_policy_change_ui_record(field_name, after_value, reason)
            self._buffer_policy_action(
                actor="government_auto",
                action_type=field_name,
                payload={"before": before_value, "after": after_value},
                reason_summary=reason,
            )

    def _buffer_simulation_events(self) -> None:
        """Convert economy-emitted event facts into warehouse rows."""
        if (
            not self.enable_warehouse
            or self.warehouse_manager is None
            or self.warehouse_run_id is None
        ):
            return

        if LaborEvent is not None:
            for idx, event in enumerate(getattr(self.economy, "last_labor_events", []) or []):
                self.labor_events_batch.append(
                    LaborEvent(
                        run_id=self.warehouse_run_id,
                        tick=int(event.get("tick", self.tick)),
                        household_id=int(event["household_id"]),
                        firm_id=int(event["firm_id"]),
                        event_type=str(event["event_type"]),
                        actual_wage=float(event["actual_wage"]) if event.get("actual_wage") is not None else None,
                        wage_offer=float(event["wage_offer"]) if event.get("wage_offer") is not None else None,
                        reservation_wage=float(event["reservation_wage"]) if event.get("reservation_wage") is not None else None,
                        skill_level=float(event["skill_level"]) if event.get("skill_level") is not None else None,
                        event_key=(
                            f"labor:{self.warehouse_run_id}:{int(event.get('tick', self.tick))}:"
                            f"{idx}:{event['household_id']}:{event['firm_id']}:{event['event_type']}"
                        ),
                    )
                )

        if HealthcareEvent is not None:
            for idx, event in enumerate(getattr(self.economy, "last_healthcare_events", []) or []):
                self.healthcare_events_batch.append(
                    HealthcareEvent(
                        run_id=self.warehouse_run_id,
                        tick=int(event.get("tick", self.tick)),
                        household_id=int(event["household_id"]),
                        firm_id=int(event["firm_id"]),
                        event_type=str(event["event_type"]),
                        queue_wait_ticks=int(event["queue_wait_ticks"]) if event.get("queue_wait_ticks") is not None else None,
                        visit_price=float(event["visit_price"]) if event.get("visit_price") is not None else None,
                        household_cost=float(event["household_cost"]) if event.get("household_cost") is not None else None,
                        government_cost=float(event["government_cost"]) if event.get("government_cost") is not None else None,
                        health_before=float(event["health_before"]) if event.get("health_before") is not None else None,
                        health_after=float(event["health_after"]) if event.get("health_after") is not None else None,
                        event_key=(
                            f"healthcare:{self.warehouse_run_id}:{int(event.get('tick', self.tick))}:"
                            f"{idx}:{event['household_id']}:{event['firm_id']}:{event['event_type']}"
                        ),
                    )
                )

        self._buffer_regime_events()

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

        flush_ok = self._flush_warehouse_batches()
        effective_status = status if flush_ok else "failed"
        analysis_ready = bool(flush_ok and status == "completed")
        termination_reason = status if flush_ok else "warehouse_flush_failed"

        try:
            self.warehouse_manager.update_run_status(
                self.warehouse_run_id,
                status=effective_status,
                total_ticks=self.tick,
                final_metrics=self._collect_final_metrics(),
                last_fully_persisted_tick=self.last_fully_persisted_tick,
                analysis_ready=analysis_ready,
                termination_reason=termination_reason,
            )
            logger.info("Closed warehouse run %s (%s)", self.warehouse_run_id, effective_status)
        except Exception as exc:
            logger.error("Failed to close warehouse run %s: %s", self.warehouse_run_id, exc)
        finally:
            self.warehouse_run_id = None
            self.tick_metrics_batch = []
            self.sector_tick_metrics_batch = []
            self.decision_features_batch = []
            self.tick_diagnostics_batch = []
            self.sector_shortage_diagnostics_batch = []
            self.firm_snapshots_batch = []
            self.household_snapshots_batch = []
            self.tracked_household_history_batch = []
            self.labor_events_batch = []
            self.healthcare_events_batch = []
            self.policy_actions_batch = []
            self.regime_events_batch = []
            self.last_fully_persisted_tick = 0
            self._previous_unemployment_rate = 0.0
            self._previous_avg_health = 0.0

    def initialize(self, config: Dict[str, Any] = None):
        """Create a fresh economy and prepare all tracking state.

        Validates *config* through the ``SetupConfig`` Pydantic model,
        builds the economy via ``create_large_economy``, applies any
        stabiliser or tax-rate overrides, selects random households and
        one firm per category for frontend tracking, and opens an
        optional warehouse run for persistence.

        Args:
            config: Raw setup dict from the WebSocket ``setup`` message.
                    Validated keys: ``num_households``, ``num_firms``,
                    ``disable_stabilizers``, ``disabled_agents``,
                    ``wage_tax``, ``profit_tax``.
        """
        if config is None:
            config = {}

        # Validate config through pydantic model
        validated = SetupConfig(**config)
        num_households = validated.num_households
        num_firms = validated.num_firms
        seed = int(validated.seed if validated.seed is not None else getattr(CONFIG, "random_seed", 0))
        CONFIG.random_seed = seed
        random.seed(seed)
        np.random.seed(seed)
        
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
        for window in self.decision_feature_windows.values():
            window.clear()
        self.live_decision_context_history.clear()
        self.latest_decision_context = None
        self._warehouse_exact_household_stats = None
        self.last_fully_persisted_tick = 0

        # Select 12 random households to track (more diverse sample)
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
        """Toggle economy stabilisers on or off mid-run.

        When *disable_flag* is ``False`` all stabilisers are re-enabled.
        Otherwise, the agents listed in *disabled_agents* (subset of
        ``{"households", "firms", "government", "all"}``) have their
        stabilisation logic bypassed.

        Args:
            disable_flag: ``True`` to disable, ``False`` to re-enable all.
            disabled_agents: Which agent groups to disable.
        """
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
                policy_before = self._snapshot_government_policy()
                self.economy.step()
                self.tick += 1
                self._record_automatic_policy_changes(
                    policy_before=policy_before,
                    policy_after=self._snapshot_government_policy(),
                )
                self._buffer_simulation_events()
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
                live_decision_metric = None
                live_decision_feature = None
                live_decision_source = "approx"
                if (
                    self.enable_warehouse
                    and self.warehouse_manager is not None
                    and self.warehouse_run_id is not None
                    and TickMetrics is not None
                ):
                    tick_metric, sector_metrics = self._build_exact_warehouse_aggregates(
                        tick_duration_ms=tick_compute_ms,
                        gdp=float(gdp),
                        current_gov_cash=float(current_gov_cash),
                        fiscal_balance=float(fiscal_balance),
                    )
                    if tick_metric is not None:
                        self.tick_metrics_batch.append(tick_metric)
                        decision_feature = self._build_decision_feature_row(tick_metric)
                        if decision_feature is not None:
                            self.decision_features_batch.append(decision_feature)
                            live_decision_feature = decision_feature
                            live_decision_metric = tick_metric
                            live_decision_source = "exact"
                        tick_diagnostic = self._build_tick_diagnostic_row(tick_metric)
                        if tick_diagnostic is not None:
                            self.tick_diagnostics_batch.append(tick_diagnostic)
                    if sector_metrics:
                        self.sector_tick_metrics_batch.extend(sector_metrics)
                    if SectorShortageDiagnostic is not None:
                        self.sector_shortage_diagnostics_batch.extend(self._build_sector_shortage_diagnostic_rows())
                    if FirmSnapshot is not None:
                        self.firm_snapshots_batch.extend(self._build_firm_snapshot_rows())
                    if TrackedHouseholdHistory is not None:
                        self.tracked_household_history_batch.extend(self._build_tracked_household_history_rows())
                    # The full-population household table is sampled. Capture
                    # tick 1 for an early baseline, then every configured stride.
                    if HouseholdSnapshot is not None and (
                        self.tick == 1 or self.tick % self.household_snapshot_stride == 0
                    ):
                        self.household_snapshots_batch.extend(self._build_household_snapshot_rows())
                    if (
                        len(self.tick_metrics_batch) >= self.tick_metrics_batch_size
                        or len(self.decision_features_batch) >= self.tick_metrics_batch_size
                        or len(self.tick_diagnostics_batch) >= self.tick_metrics_batch_size
                        or len(self.sector_tick_metrics_batch) >= self.tick_metrics_batch_size
                        or len(self.sector_shortage_diagnostics_batch) >= self.tick_metrics_batch_size
                        or len(self.firm_snapshots_batch) >= self.snapshot_batch_size
                        or len(self.household_snapshots_batch) >= self.snapshot_batch_size
                        or len(self.tracked_household_history_batch) >= self.tick_metrics_batch_size
                        or len(self.labor_events_batch) >= self.tick_metrics_batch_size
                        or len(self.healthcare_events_batch) >= self.tick_metrics_batch_size
                        or len(self.policy_actions_batch) >= self.tick_metrics_batch_size
                        or len(self.regime_events_batch) >= self.tick_metrics_batch_size
                    ):
                        self._flush_warehouse_batches()
                else:
                    self._warehouse_exact_household_stats = stats
                    live_decision_metric = self._build_live_decision_metric(
                        stats=stats,
                        gdp=float(gdp),
                        current_gov_cash=float(current_gov_cash),
                        fiscal_balance=float(fiscal_balance),
                        mean_prices=mean_prices,
                    )
                    live_decision_feature = self._build_decision_feature_row(live_decision_metric)

                if live_decision_feature is not None and live_decision_metric is not None:
                    self._record_live_decision_context(
                        decision_feature=live_decision_feature,
                        metric_like=live_decision_metric,
                        source=live_decision_source,
                    )

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
        tracked_policy_keys = {
            "wageTax",
            "profitTax",
            "minimumWage",
            "unemploymentBenefitRate",
            "universalBasicIncome",
            "wealthTaxRate",
            "wealthTaxThreshold",
            "inflationRate",
            "birthRate",
        }
        policy_key_map = {
            "wageTax": "wage_tax_rate",
            "profitTax": "profit_tax_rate",
            "minimumWage": "minimum_wage",
            "unemploymentBenefitRate": "unemployment_benefit_rate",
            "universalBasicIncome": "universal_basic_income",
            "wealthTaxRate": "wealth_tax_rate",
            "wealthTaxThreshold": "wealth_tax_threshold",
            "inflationRate": "inflation_rate",
            "birthRate": "birth_rate",
        }
        for key, value in config_data.items():
            if key in tracked_policy_keys:
                policy_name = policy_key_map.get(key, key)
                reason = f"User updated {policy_name} to {value}"
                self._append_policy_change_ui_record(policy_name, value, reason)
                self._buffer_policy_action(
                    actor="user",
                    action_type=policy_name,
                    payload={"value": value},
                    reason_summary=reason,
                )

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


@app.get("/decision-context/live")
async def get_live_decision_context(window: int = Query(default=20, ge=1, le=200)):
    """Return the current in-memory rolling decision context window."""
    return manager.get_live_decision_context(window=window)


@app.get("/warehouse/runs")
async def list_warehouse_runs(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List persisted simulation runs for warehouse-backed analysis."""
    warehouse, should_close = _get_warehouse_reader()
    try:
        runs = warehouse.get_runs(status=status, limit=limit, offset=offset)
        return {"runs": [run.to_dict() for run in runs], "count": len(runs)}
    finally:
        if should_close:
            warehouse.close()


@app.get("/warehouse/runs/{run_id}/tick-metrics")
async def get_run_tick_metrics(
    run_id: str,
    tick_start: int = Query(default=0, ge=0),
    tick_end: int = Query(default=999999, ge=0),
):
    """Fetch ordered macro tick history for one run."""
    warehouse, should_close = _get_warehouse_reader()
    try:
        tick_metrics = warehouse.get_tick_metrics(run_id, tick_start=tick_start, tick_end=tick_end)
        return {"runId": run_id, "tickMetrics": tick_metrics, "count": len(tick_metrics)}
    finally:
        if should_close:
            warehouse.close()


@app.get("/warehouse/runs/{run_id}/summary")
async def get_run_summary(run_id: str):
    """Fetch one run's aggregate summary row."""
    warehouse, should_close = _get_warehouse_reader()
    try:
        summary = warehouse.get_run_summary(run_id)
        return {"runId": run_id, "summary": summary}
    finally:
        if should_close:
            warehouse.close()


@app.get("/warehouse/runs/{run_id}/decision-features")
async def get_run_decision_features(
    run_id: str,
    tick_start: int = Query(default=0, ge=0),
    tick_end: int = Query(default=999999, ge=0),
):
    """Fetch ordered compact decision-context history for one run."""
    warehouse, should_close = _get_warehouse_reader()
    try:
        features = warehouse.get_decision_features(run_id, tick_start=tick_start, tick_end=tick_end)
        return {"runId": run_id, "decisionFeatures": features, "count": len(features)}
    finally:
        if should_close:
            warehouse.close()


@app.get("/warehouse/runs/{run_id}/sector-metrics")
async def get_run_sector_metrics(
    run_id: str,
    tick_start: int = Query(default=0, ge=0),
    tick_end: int = Query(default=999999, ge=0),
    sector: Optional[str] = Query(default=None),
):
    """Fetch sector history plus a compact sector summary for one run."""
    warehouse, should_close = _get_warehouse_reader()
    try:
        rows = warehouse.get_sector_tick_metrics(
            run_id,
            tick_start=tick_start,
            tick_end=tick_end,
            sector=sector,
        )
        summary = warehouse.get_sector_summary(
            run_id,
            tick_start=tick_start,
            tick_end=tick_end,
            sector=sector,
        )
        return {
            "runId": run_id,
            "sector": sector,
            "sectorMetrics": rows,
            "summary": summary,
            "count": len(rows),
        }
    finally:
        if should_close:
            warehouse.close()


@app.get("/warehouse/compare")
async def compare_runs(run_ids: List[str] = Query(...)):
    """Fetch compact comparison rows for a small set of runs."""
    normalized_ids = []
    seen = set()
    for run_id in run_ids:
        if run_id and run_id not in seen:
            normalized_ids.append(run_id)
            seen.add(run_id)
    if not normalized_ids:
        raise HTTPException(status_code=400, detail="At least one run_id is required.")

    warehouse, should_close = _get_warehouse_reader()
    try:
        comparison = warehouse.get_run_comparison(normalized_ids)
        return {"runIds": normalized_ids, "comparison": comparison, "count": len(comparison)}
    finally:
        if should_close:
            warehouse.close()

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
                manager._flush_warehouse_batches()
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
