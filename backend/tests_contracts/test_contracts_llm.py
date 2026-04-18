import asyncio
import json

import pytest

from agents import GovernmentAgent
import server
from config import CONFIG
from tools.llm.llm_government import LLMGovernmentAdvisor, apply_info_constraints_node, observe_node
from tools.llm.llm_provider import LLMProvider


class QueueProvider(LLMProvider):
    """Deterministic mock provider for contract tests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    @property
    def name(self) -> str:
        return "mock/test"

    async def health_check(self) -> bool:
        return True

    async def complete(self, system: str, user: str, temperature: float = 0.4, response_format=None) -> str:
        self.prompts.append({"system": system, "user": user, "temperature": temperature})
        if not self.responses:
            raise RuntimeError("No mock responses remaining")
        return self.responses.pop(0)


def test_contract_llm_parse_failure_falls_back_to_no_change(tiny_economy_factory, monkeypatch):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=2, disable_shocks=True, seed=901)
    provider = QueueProvider(["this is not valid json"])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    before_wage_tax = economy.government.wage_tax_rate
    result = asyncio.run(advisor.decide(economy))

    assert result["parse_ok"] is False
    assert result["decisions"] == {}
    assert economy.government.wage_tax_rate == before_wage_tax


def test_contract_llm_one_step_constraint_blocks_large_jump(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=2, disable_shocks=True, seed=902)
    economy.government.set_lever("benefit_level", "low")

    provider = QueueProvider(
        [
            json.dumps(
                {
                    "decisions": {"wage_tax_rate": 0.25, "benefit_level": "crisis"},
                    "reasoning": "Raise taxes and expand benefits to crisis level.",
                }
            )
        ]
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    result = asyncio.run(advisor.decide(economy))

    # Continuous lever (wage_tax_rate) should be accepted — no step constraint
    assert result["decisions"]["wage_tax_rate"] == 0.25
    # Discrete lever jump low->crisis (2 steps) should be blocked
    assert "benefit_level" not in result["decisions"]
    assert economy.government.benefit_level == "low"


def test_contract_llm_information_constraints_apply_noise_and_lag(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=24, num_firms_per_category=2, disable_shocks=True, seed=903)
    for _ in range(5):
        economy.step()
        economy.append_metrics_snapshot(economy.get_economic_metrics(), tick=economy.current_tick)

    state = observe_node({}, economy)
    constrained = apply_info_constraints_node(state, economy, CONFIG.llm, [])
    observed = constrained["observed_metrics"]

    assert "government_cash" in observed
    assert observed["government_cash"]["status"] == "reported"
    assert observed["government_cash"]["value"] != state["raw_metrics"]["government_cash"]

    assert "unemployment_rate" in observed
    if observed["unemployment_rate"]["status"] == "reported":
        assert observed["unemployment_rate"]["data_age_ticks"] == 2
        assert "estimated_accuracy" in observed["unemployment_rate"]


def test_contract_llm_prompt_includes_recent_policy_memory(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=2, disable_shocks=True, seed=904)
    for _ in range(4):
        economy.step()
        economy.append_metrics_snapshot(economy.get_economic_metrics(), tick=economy.current_tick)

    provider = QueueProvider(
        [
            json.dumps(
                {
                    "decisions": {"benefit_level": "high"},
                    "reasoning": "Support demand while unemployment remains elevated.",
                }
            ),
            json.dumps({"decisions": {}, "reasoning": "Hold policy steady while observing follow-through."}),
        ]
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    asyncio.run(advisor.decide(economy))
    economy.step()
    economy.append_metrics_snapshot(economy.get_economic_metrics(), tick=economy.current_tick)
    asyncio.run(advisor.decide(economy))

    second_prompt = provider.prompts[-1]["user"]
    assert "Recent policy memory" in second_prompt
    assert "benefit_level" in second_prompt


def test_contract_llm_prompt_includes_regime_state_and_lever_effects(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=2, disable_shocks=True, seed=906)
    provider = QueueProvider([json.dumps({"decisions": {}, "reasoning": "Hold."})])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    asyncio.run(advisor.decide(economy))

    prompt = provider.prompts[-1]
    assert "Regime state" in prompt["user"]
    assert "warmup_active" in prompt["user"]
    assert "Higher investment_tax_rate taxes firm R&D directly" in prompt["system"]
    assert "technology_spending: none | low | medium | high" in prompt["system"]
    assert "bailout_policy: off | sector | all" in prompt["system"]
    assert "bailout_budget: 0 | 5000 | 10000 | 25000 | 50000" in prompt["system"]


def test_contract_bailout_budget_resets_each_decision_cycle():
    government = GovernmentAgent(cash_balance=50_000.0)
    government.set_lever("bailout_policy", "sector")
    government.set_lever("bailout_target", "food")
    government.set_lever("bailout_budget", 10_000)

    assert government.bailout_budget_remaining == pytest.approx(10_000.0)
    government.record_bailout("Food", firm_id=7, amount=4_000.0)

    government.begin_decision_cycle()

    assert government.last_cycle_bailout_disbursed == pytest.approx(4_000.0)
    assert government.last_cycle_bailout_remaining == pytest.approx(6_000.0)
    assert government.last_cycle_bailout_firms_assisted == 1
    assert government.bailout_budget_remaining == pytest.approx(10_000.0)


def test_contract_technology_spending_changes_effective_market_quality(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=907)
    food_firm = next(f for f in economy.firms if f.good_category.lower() == "food")
    raw_quality = food_firm.quality_level

    economy.government.cash_balance = 50_000.0
    economy.government.set_lever("technology_spending", "high")
    spent = economy.government.invest_in_technology()
    snapshot = economy._build_category_market_snapshot()
    metrics = economy.get_economic_metrics()

    assert spent > 0.0
    assert snapshot["food"][0]["quality"] > raw_quality
    assert metrics["effective_mean_quality"] > metrics["mean_quality"]


def test_contract_economy_warmup_uses_configured_ticks(tiny_economy_factory, monkeypatch):
    monkeypatch.setattr(CONFIG.time, "warmup_ticks", 0)
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=908)

    assert economy.in_warmup is False
    assert economy.warmup_ticks == 0


def test_contract_server_llm_decision_interval_is_enforced(tiny_economy_factory, monkeypatch):
    manager = server.SimulationManager()
    manager.economy = tiny_economy_factory(num_households=15, num_firms_per_category=1, disable_shocks=True, seed=905)
    manager.tick = 4
    manager.economy.current_tick = 4

    calls = {"count": 0}

    class DummyAdvisor:
        async def decide(self, economy):
            calls["count"] += 1
            economy.government.set_lever("public_works", "on")
            return {
                "tick": economy.current_tick,
                "decisions": {"public_works": "on"},
                "reasoning": "Labor market support",
                "parse_ok": True,
                "elapsed_ms": 12.0,
                "provider": "mock/test",
            }

    async def ensure_ready():
        manager.llm_government = DummyAdvisor()
        return True

    monkeypatch.setattr(manager, "_ensure_llm_government", ensure_ready)
    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", True)
    monkeypatch.setattr(CONFIG.llm, "government_decision_interval", 4)

    result_due = asyncio.run(manager._run_llm_government_if_due())
    assert calls["count"] == 1
    assert result_due is not None
    assert manager.economy.government.public_works_toggle == "on"

    manager.tick = 5
    manager.economy.current_tick = 5
    result_not_due = asyncio.run(manager._run_llm_government_if_due())
    assert result_not_due is None
    assert calls["count"] == 1
