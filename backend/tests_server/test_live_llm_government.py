import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server
from config import CONFIG
from tests_contracts.factories import make_economy


def test_provider_unavailable_falls_back_without_crashing(monkeypatch):
    """Missing LLM provider disables live LLM government and leaves simulation usable."""
    manager = server.SimulationManager()
    manager.economy = make_economy(num_households=12, num_firms_per_category=1, disable_shocks=True, seed=910)

    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", True)
    monkeypatch.setattr(server, "create_provider", None)
    monkeypatch.setattr(server, "LLMGovernmentAdvisor", None)
    monkeypatch.setattr(server, "_LLM_IMPORT_ERROR", RuntimeError("provider missing"))

    assert asyncio.run(manager._ensure_llm_government()) is False
    assert manager.llm_status == "provider_unavailable"
    assert CONFIG.llm.enable_llm_government is False
    assert manager.economy.llm_government is None


def test_runtime_config_updates_apply_government_levers(monkeypatch):
    """CONFIG websocket payloads can update live policy levers through the schema path."""
    manager = server.SimulationManager()
    manager.economy = make_economy(num_households=12, num_firms_per_category=1, disable_shocks=True, seed=911)

    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", False)
    asyncio.run(
        manager._apply_config_updates(
            {
                "enableLlmGovernment": True,
                "wageTax": 0.22,
                "profitTax": 0.18,
                "publicWorks": True,
                "benefitLevel": "high",
                "minimumWagePolicy": "high",
                "sectorSubsidyTarget": "food",
                "sectorSubsidyLevel": 25,
                "infrastructureSpending": "medium",
                "technologySpending": "high",
                "socialSpending": "high",
                "priceStabilizationTarget": "food",
                "priceStabilizationLevel": "monitor",
                "rentStabilizationLevel": "soft",
                "bailoutPolicy": "sector",
                "bailoutTarget": "food",
                "bailoutBudget": 10000,
            }
        )
    )

    gov = manager.economy.government
    assert CONFIG.llm.enable_llm_government is True
    assert gov.wage_tax_rate == 0.22
    assert gov.profit_tax_rate == 0.18
    assert gov.public_works_toggle == "on"
    assert gov.benefit_level == "high"
    assert gov.minimum_wage_policy == "high"
    assert gov.sector_subsidy_target == "food"
    assert gov.sector_subsidy_level == 25
    assert gov.infrastructure_spending == "medium"
    assert gov.technology_spending == "high"
    assert gov.social_spending == "high"
    assert gov.price_stabilization_target == "food"
    assert gov.price_stabilization_level == "monitor"
    assert gov.rent_stabilization_level == "soft"
    assert gov.bailout_policy == "sector"
    assert gov.bailout_target == "food"
    assert gov.bailout_budget == 10000
