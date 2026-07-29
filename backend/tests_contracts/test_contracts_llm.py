import asyncio
import json

import httpx
import pytest

from agents import GovernmentAgent
import server
from config import CONFIG, use_config
from policy_schema import POLICY_SCHEMA, PROMPT_POLICY_LEVERS, normalize_current_policy
from tools.llm.llm_government import (
    LLMGovernmentAdvisor,
    _audit_evidence,
    _build_recent_policy_memory,
    _build_system_prompt,
    apply_info_constraints_node,
    build_allowed_government_actions,
    computed_fiscal_mode_from_state,
    observe_node,
    sanitize_llm_government_changes,
    sanitize_llm_government_changes_detailed,
)
from tools.llm.llm_provider import GroqProvider, LLMProvider, OpenRouterProvider


pytestmark = pytest.mark.llm


class QueueProvider(LLMProvider):
    """Deterministic mock provider for contract tests."""

    def __init__(self, responses, name="mock/test"):
        self.responses = list(responses)
        self.prompts = []
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def health_check(self) -> bool:
        return True

    async def complete(self, system: str, user: str, temperature: float = 0.4, top_p=None, response_format=None) -> str:
        self.prompts.append({"system": system, "user": user, "temperature": temperature})
        if not self.responses:
            raise RuntimeError("No mock responses remaining")
        return self.responses.pop(0)


def test_contract_groq_provider_uses_openai_compatible_chat_shape():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content.decode("utf-8"))
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["model"] == "llama-3.3-70b-versatile"
        assert payload["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ]
        assert payload["temperature"] == 0.2
        assert payload["top_p"] == 0.9
        assert payload["max_tokens"] == 777
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {}}"}}]},
        )

    provider = GroqProvider(api_key="test-key", model="llama-3.3-70b-versatile", max_tokens=777)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            provider.complete(
                system="system prompt",
                user="user prompt",
                temperature=0.2,
                top_p=0.9,
                response_format={"type": "json_object"},
            )
        )
    finally:
        asyncio.run(provider.close())

    assert requests
    assert result == "{\"changes\": {}}"


def test_contract_openrouter_provider_uses_chat_shape_and_max_tokens():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content.decode("utf-8"))
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["model"] == "inclusionai/ring-2.6-1t:free"
        assert payload["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ]
        assert payload["temperature"] == 0.2
        assert payload["top_p"] == 0.9
        assert payload["max_tokens"] == 777
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {}}"}}]},
        )

    provider = OpenRouterProvider(
        api_key="test-key",
        model="inclusionai/ring-2.6-1t:free",
        max_tokens=777,
    )
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            provider.complete(
                system="system prompt",
                user="user prompt",
                temperature=0.2,
                top_p=0.9,
                response_format={"type": "json_object"},
            )
        )
    finally:
        asyncio.run(provider.close())

    assert requests
    assert result == "{\"changes\": {}}"


def test_contract_openrouter_provider_retries_429_rate_limit():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "rate limit"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {\"benefit_level\": \"high\"}}"}}]},
        )

    provider = OpenRouterProvider(
        api_key="test-key",
        model="inclusionai/ring-2.6-1t:free",
        max_retries=1,
    )
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(provider.complete(system="system prompt", user="user prompt"))
    finally:
        asyncio.run(provider.close())

    assert len(requests) == 2
    assert result == "{\"changes\": {\"benefit_level\": \"high\"}}"


def test_contract_openrouter_provider_retries_empty_content():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {\"benefit_level\": \"high\"}}"}}]},
        )

    provider = OpenRouterProvider(
        api_key="test-key",
        model="inclusionai/ring-2.6-1t:free",
        max_retries=0,
    )
    provider.empty_response_retries = 1
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(provider.complete(system="system prompt", user="user prompt"))
    finally:
        asyncio.run(provider.close())

    assert len(requests) == 2
    assert result == "{\"changes\": {\"benefit_level\": \"high\"}}"


def test_contract_groq_provider_retries_429_rate_limit():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "rate limit"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {\"benefit_level\": \"high\"}}"}}]},
        )

    provider = GroqProvider(api_key="test-key", model="llama-3.3-70b-versatile", max_retries=1)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(provider.complete(system="system prompt", user="user prompt"))
    finally:
        asyncio.run(provider.close())

    assert len(requests) == 2
    assert result == "{\"changes\": {\"benefit_level\": \"high\"}}"


def test_contract_groq_gpt_oss_skips_response_format_and_caps_max_tokens():
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        payloads.append(payload)
        assert payload["model"] == "openai/gpt-oss-120b"
        assert payload["include_reasoning"] is False
        assert payload["reasoning_effort"] == "low"
        assert payload["max_tokens"] == 700
        assert "response_format" not in payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {\"profit_tax_rate\": 0.15}}"}}]},
        )

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b", max_tokens=1200)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            provider.complete(
                system="system prompt",
                user="user prompt",
                response_format={"type": "json_object"},
            )
        )
    finally:
        asyncio.run(provider.close())

    assert len(payloads) == 1
    assert result == "{\"changes\": {\"profit_tax_rate\": 0.15}}"


def test_contract_groq_gpt_oss_reduces_max_tokens_after_413():
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        payloads.append(payload)
        if len(payloads) == 1:
            assert payload["max_tokens"] == 700
            return httpx.Response(
                413,
                json={"error": {"message": "Request too large for model on tokens per minute"}},
            )
        assert payload["max_tokens"] == 525
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"changes\": {\"social_spending\": \"low\"}}"}}]},
        )

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b", max_tokens=1200)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(provider.complete(system="system prompt", user="user prompt"))
    finally:
        asyncio.run(provider.close())

    assert len(payloads) == 2
    assert result == "{\"changes\": {\"social_spending\": \"low\"}}"


def test_contract_policy_schema_matches_government_and_server_snapshot(tiny_economy_factory):
    government = GovernmentAgent(cash_balance=50_000.0)
    for lever in POLICY_SCHEMA:
        assert lever in government.to_dict()
        government.set_lever(lever, government.to_dict()[lever])

    economy = tiny_economy_factory(num_households=12, num_firms_per_category=1, disable_shocks=True, seed=901)
    manager = server.SimulationManager()
    manager.economy = economy
    snapshot = manager._snapshot_government_levers()

    for lever in PROMPT_POLICY_LEVERS:
        assert lever in POLICY_SCHEMA
        assert lever in snapshot


def test_contract_prompt_does_not_advertise_unknown_levers():
    prompt = _build_system_prompt("capitalist", num_households=20, num_firms=4)
    advertised = set()
    in_schema = False
    for line in prompt.splitlines():
        if line.strip() == "POLICY SCHEMA:":
            in_schema = True
            continue
        if in_schema and not line.strip():
            break
        if in_schema and line.startswith("- "):
            advertised.add(line[2:].split(":", 1)[0])

    assert advertised
    assert advertised <= set(POLICY_SCHEMA)


def test_contract_prompt_has_no_policy_playbook_advice():
    prompt = _build_system_prompt("capitalist", num_households=20, num_firms=4)
    forbidden = ("Use when", "Avoid when", "Usually choose", "usually choose", "SECTOR PRIORITY", "POLICY PLAYBOOK")
    for phrase in forbidden:
        assert phrase not in prompt


def test_contract_llm_parse_failure_falls_back_to_no_change(tiny_economy_factory, monkeypatch):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=2, disable_shocks=True, seed=901)
    provider = QueueProvider(["this is not valid json"])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    before_wage_tax = economy.government.wage_tax_rate
    result = asyncio.run(advisor.decide(economy))

    assert result["parse_ok"] is False
    assert result["decisions"] == {}
    assert economy.government.wage_tax_rate == before_wage_tax


def test_contract_openrouter_ring_blank_response_gets_json_repair_retry(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=2, disable_shocks=True, seed=901)
    provider = QueueProvider(
        [
            "",
            json.dumps(
                {
                    "fiscal_mode": "NORMAL",
                    "primary_goal": "support_households",
                    "rationale": "Government cash is stable enough to raise happiness support.",
                    "evidence": ["government_cash=$50000", "mean_happiness=0.4"],
                    "changes": {"social_spending": "high"},
                }
            ),
        ],
        name="openrouter/inclusionai/ring-2.6-1t:free",
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    result = asyncio.run(advisor.decide(economy))

    assert len(provider.prompts) == 2
    assert "RETRY AFTER INVALID OUTPUT" in provider.prompts[1]["user"]
    assert result["parse_ok"] is True
    assert result["accepted_llm_changes"] == {"social_spending": "high"}


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

    # Continuous lever jump should be blocked by the max tax step.
    assert "wage_tax_rate" not in result["decisions"]
    # Discrete lever jump low->crisis (2 steps) should be blocked
    assert "benefit_level" not in result["decisions"]
    assert economy.government.benefit_level == "low"
    reasons = {item["reason"] for item in result["rejected_changes"]}
    assert "tax_step_too_large" in reasons
    assert "ordered_step_too_large" in reasons


def test_contract_llm_accepts_rationale_and_evidence(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=918)
    provider = QueueProvider(
        [
            json.dumps(
                {
                    "fiscal_mode": "NORMAL",
                    "primary_goal": "reduce_unemployment",
                    "rationale": "Unemployment is elevated and cash is positive, so I raised benefits.",
                    "evidence": ["unemployment_rate=0.31", "government_cash=$52,340"],
                    "changes": {"benefit_level": "high"},
                }
            )
        ]
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    result = asyncio.run(advisor.decide(economy))

    assert result["parse_ok"] is True
    assert result["rationale"].startswith("Unemployment is elevated")
    assert result["reasoning"] == result["rationale"]
    assert result["evidence"] == ["unemployment_rate=0.31", "government_cash=$52,340"]
    assert "evidence_audit" in result
    assert result["decisions"]["benefit_level"] == "high"


def test_contract_llm_legacy_reasoning_normalizes_to_rationale(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=919)
    provider = QueueProvider(
        [
            json.dumps(
                {
                    "fiscal_mode": "NORMAL",
                    "primary_goal": "hold",
                    "reasoning": "Legacy public explanation.",
                    "changes": {},
                }
            )
        ]
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    result = asyncio.run(advisor.decide(economy))

    assert result["parse_ok"] is True
    assert result["rationale"] == "Legacy public explanation."
    assert result["reasoning"] == "Legacy public explanation."
    assert result["evidence"] == []


def test_contract_evidence_audit_classifies_metrics_policy_and_bad_keys():
    state = {
        "raw_metrics": {"unemployment_rate": 0.31, "government_cash": 52340.0},
        "observed_metrics": {
            "distressed_food_firms": {"status": "reported", "value": 1},
        },
        "sector_diagnostics": {"food": {"avg_price": 6.0, "price_to_median_wage": 0.16}},
        "budget_state": {"fiscal_pressure": 0.12},
        "current_policy": {"benefit_level": "medium"},
        "data_seen": {"government_cash": 52340.0},
    }

    audit = _audit_evidence(
        [
            "unemployment_rate=0.31",
            "benefit_level=medium",
            "food: avg_price=$6, baseline=$8, price/median_wage=0.16",
            "gov_ net_flow_this_tick=-100",
            "gov_warehouse_cap_this_tick=205",
        ],
        state,
    )

    assert [item["status"] for item in audit] == [
        "matched_metric",
        "matched_policy",
        "matched_metric",
        "format_issue",
        "unknown_key",
    ]


def test_contract_evidence_audit_value_mismatch_does_not_block_decision(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=930)
    provider = QueueProvider(
        [
            json.dumps(
                {
                    "fiscal_mode": "NORMAL",
                    "primary_goal": "reduce_unemployment",
                    "rationale": "Benefits are raised using cited labor data.",
                    "evidence": ["unemployment_rate=99.0"],
                    "changes": {"benefit_level": "high"},
                }
            )
        ]
    )
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    result = asyncio.run(advisor.decide(economy))

    assert result["decisions"]["benefit_level"] == "high"
    assert result["evidence_audit"][0]["status"] == "value_mismatch"


def test_contract_computed_fiscal_mode_uses_pressure_bands():
    government = GovernmentAgent(cash_balance=50_000.0)

    assert computed_fiscal_mode_from_state(government, recent_gdp=10_000.0, fiscal_pressure=0.10) == "NORMAL"
    assert computed_fiscal_mode_from_state(government, recent_gdp=10_000.0, fiscal_pressure=0.15) == "LOW_CASH"
    assert computed_fiscal_mode_from_state(government, recent_gdp=10_000.0, fiscal_pressure=0.30) == "CASH_CRISIS"


def test_contract_sanitizer_accepts_audit_style_current_policy_types():
    current = {
        "public_works_toggle": "off",
        "sector_subsidy_level": "0",
        "bailout_budget": 0.0,
        "wage_tax_rate": "0.15",
    }

    normalized = normalize_current_policy(current)

    assert normalized["public_works"] == "off"
    assert normalized["sector_subsidy_level"] == 0
    assert normalized["bailout_budget"] == 0
    assert normalized["wage_tax_rate"] == 0.15


def test_contract_sanitizer_rejects_tax_cut_during_fiscal_stress():
    government = GovernmentAgent(cash_balance=-1.0)
    current = government.to_dict()

    clean, rejected = sanitize_llm_government_changes(
        {"wage_tax_rate": current["wage_tax_rate"] - 0.05},
        current,
        government,
        gdp=10_000.0,
        unemployment_rate=0.40,
    )

    assert "wage_tax_rate" not in clean
    assert any(item["reason"] == "tax_cut_during_fiscal_stress" for item in rejected)


def test_contract_sanitizer_rejects_tick15_like_public_works_crash(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=907)
    economy.government.cash_balance = 163_487.0

    clean, rejected = sanitize_llm_government_changes(
        {"public_works": "on"},
        economy.government.to_dict(),
        economy.government,
        gdp=4_508.0,
        unemployment_rate=0.32,
        economy=economy,
    )

    assert "public_works" not in clean
    assert any("insufficient_cash_for_public_works_startup" in item["reason"] for item in rejected)


def test_contract_sanitizer_max_two_substantive_changes_with_consistency_cleanup(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=908)
    economy.government.set_lever("sector_subsidy_target", "food")
    economy.government.set_lever("sector_subsidy_level", 10)
    raw = {
        "sector_subsidy_level": 0,
        "wage_tax_rate": 0.20,
        "profit_tax_rate": 0.25,
    }

    clean, rejected = sanitize_llm_government_changes(
        raw,
        economy.government.to_dict(),
        economy.government,
        gdp=10_000.0,
        unemployment_rate=0.10,
        economy=economy,
    )

    assert clean["sector_subsidy_level"] == 0
    assert clean["wage_tax_rate"] == 0.20
    assert "profit_tax_rate" not in clean
    assert clean["sector_subsidy_target"] == "none"
    assert any(item["reason"] == "max_substantive_changes_exceeded" for item in rejected)


def test_contract_sanitizer_rejects_minimum_wage_increase_during_extreme_unemployment():
    government = GovernmentAgent(cash_balance=100_000.0)
    government.set_lever("minimum_wage_policy", "neutral")

    clean, rejected = sanitize_llm_government_changes(
        {"minimum_wage_policy": "high"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.35,
    )

    assert "minimum_wage_policy" not in clean
    assert any(item["reason"] == "minimum_wage_increase_during_extreme_unemployment" for item in rejected)


def test_contract_sanitizer_rejects_target_only_subsidy_move():
    government = GovernmentAgent(cash_balance=100_000.0)

    clean, rejected = sanitize_llm_government_changes(
        {"sector_subsidy_target": "services"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )

    assert "sector_subsidy_target" not in clean
    assert any(item["reason"] == "target_without_subsidy_level_has_no_effect" for item in rejected)


def test_contract_sanitizer_rejects_target_only_bailout_move():
    government = GovernmentAgent(cash_balance=100_000.0)
    government.set_lever("bailout_policy", "off")
    government.set_lever("bailout_budget", 0)

    clean, rejected = sanitize_llm_government_changes(
        {"bailout_target": "services"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )

    assert "bailout_target" not in clean
    assert any(item["reason"] == "bailout_target_without_active_bailout_has_no_effect" for item in rejected)


def test_contract_sanitizer_rejects_price_stabilization_soft_without_target():
    government = GovernmentAgent(cash_balance=-1.0)
    government.set_lever("price_stabilization_level", "monitor")

    clean, rejected = sanitize_llm_government_changes(
        {"price_stabilization_level": "soft"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.20,
    )

    assert "price_stabilization_level" not in clean
    assert any(item["reason"] == "price_stabilization_requires_target" for item in rejected)


def test_contract_sanitizer_forces_price_target_none_when_level_off():
    government = GovernmentAgent(cash_balance=10_000.0)
    government.set_lever("price_stabilization_target", "food")
    government.set_lever("price_stabilization_level", "monitor")

    clean, rejected = sanitize_llm_government_changes(
        {"price_stabilization_level": "off"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.20,
    )

    assert not rejected
    assert clean["price_stabilization_level"] == "off"
    assert clean["price_stabilization_target"] == "none"


def test_contract_sanitizer_allows_rent_stabilization_during_fiscal_stress():
    government = GovernmentAgent(cash_balance=-1.0)

    clean, rejected = sanitize_llm_government_changes(
        {"rent_stabilization_level": "monitor"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.20,
    )

    assert not rejected
    assert clean["rent_stabilization_level"] == "monitor"


def test_contract_grouped_price_stabilization_is_atomic():
    government = GovernmentAgent(cash_balance=50_000.0)

    target_only = sanitize_llm_government_changes_detailed(
        {"price_stabilization_target": "food"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )
    assert target_only["applied_changes"] == {}
    assert target_only["rejected_changes"][0]["group"] == "price_stabilization"

    grouped = sanitize_llm_government_changes_detailed(
        {"price_stabilization_target": "food", "price_stabilization_level": "monitor"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )
    assert grouped["accepted_llm_changes"] == {
        "price_stabilization_target": "food",
        "price_stabilization_level": "monitor",
    }
    assert grouped["mechanical_corrections"] == {}
    assert grouped["applied_changes"] == grouped["accepted_llm_changes"]


def test_contract_grouped_price_turnoff_logs_mechanical_cleanup():
    government = GovernmentAgent(cash_balance=50_000.0)
    government.set_lever("price_stabilization_target", "food")
    government.set_lever("price_stabilization_level", "monitor")

    detailed = sanitize_llm_government_changes_detailed(
        {"price_stabilization_level": "off"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )

    assert detailed["accepted_llm_changes"] == {"price_stabilization_level": "off"}
    assert detailed["mechanical_corrections"] == {"price_stabilization_target": "none"}
    assert detailed["applied_changes"] == {
        "price_stabilization_level": "off",
        "price_stabilization_target": "none",
    }


def test_contract_grouped_bailout_is_atomic():
    government = GovernmentAgent(cash_balance=100_000.0)

    invalid = sanitize_llm_government_changes_detailed(
        {"bailout_policy": "sector"},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )
    assert invalid["applied_changes"] == {}
    assert invalid["rejected_changes"][0]["group"] == "bailout"

    valid = sanitize_llm_government_changes_detailed(
        {"bailout_policy": "sector", "bailout_target": "services", "bailout_budget": 5000},
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )
    assert valid["accepted_llm_changes"] == {
        "bailout_policy": "sector",
        "bailout_target": "services",
        "bailout_budget": 5000,
    }
    assert valid["rejected_changes"] == []


def test_contract_grouped_regression_no_partial_bailout_policy_accept():
    government = GovernmentAgent(cash_balance=100_000.0)
    raw = {
        "price_stabilization_target": "services",
        "price_stabilization_level": "monitor",
        "bailout_policy": "sector",
        "bailout_target": "services",
        "bailout_budget": 5000,
        "benefit_level": "high",
    }

    detailed = sanitize_llm_government_changes_detailed(
        raw,
        government.to_dict(),
        government,
        gdp=10_000.0,
        unemployment_rate=0.10,
    )

    if "bailout_policy" in detailed["applied_changes"]:
        assert detailed["applied_changes"]["bailout_policy"] == "sector"
        assert detailed["applied_changes"]["bailout_target"] == "services"
        assert detailed["applied_changes"]["bailout_budget"] == 5000
    else:
        assert any(item.get("group") == "bailout" for item in detailed["rejected_changes"])


def test_contract_allowed_action_mask_includes_valid_subsidy_start_pair(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=20, num_firms_per_category=1, disable_shocks=True, seed=910)
    economy.government.cash_balance = 300_000.0

    mask = build_allowed_government_actions(
        economy.government.to_dict(),
        economy.government,
        recent_gdp=10_000.0,
        unemployment_rate=0.10,
        economy=economy,
    )

    assert "services" in [
        item["sector_subsidy_target"]
        for item in mask["allowed"]["groups"]["sector_subsidy"]
    ]
    assert all(
        item["sector_subsidy_target"] == "none" or int(item["sector_subsidy_level"]) > 0
        for item in mask["allowed"]["groups"]["sector_subsidy"]
    )


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
    assert constrained["rolling_windows_used"] == list(CONFIG.llm.government_rolling_windows_ticks)


def test_contract_llm_prompt_includes_recent_policy_memory(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=2, disable_shocks=True, seed=904)
    for _ in range(4):
        economy.step()
        economy.append_metrics_snapshot(economy.get_economic_metrics(), tick=economy.current_tick)

    provider = QueueProvider(
        [
            json.dumps(
                {
                    "changes": {"benefit_level": "high"},
                    "rationale": "Unemployment remains elevated, so I raised benefits one step.",
                    "evidence": ["unemployment_rate=0.31", "government_cash=$50,000"],
                }
            ),
            json.dumps(
                {
                    "changes": {},
                    "rationale": "Hold policy steady while observing follow-through.",
                    "evidence": ["benefit_level=high"],
                }
            ),
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
    assert "rationale_then: Unemployment remains elevated" in second_prompt
    assert "evidence_then:" in second_prompt
    assert "short_term_since_last_decision" in second_prompt


def test_contract_recent_policy_memory_has_short_and_mature_horizons():
    class FakeEconomy:
        metrics_history = [
            {
                "tick": 3,
                "metrics": {
                    "gdp_this_tick": 100.0,
                    "unemployment_rate": 0.30,
                    "mean_happiness": 0.50,
                    "mean_health": 0.80,
                    "government_cash": 50_000.0,
                    "gov_revenue_this_tick": 1_000.0,
                    "gov_spending_this_tick": 900.0,
                },
            },
            {
                "tick": 8,
                "metrics": {
                    "gdp_this_tick": 110.0,
                    "unemployment_rate": 0.28,
                    "mean_happiness": 0.52,
                    "mean_health": 0.79,
                    "government_cash": 50_500.0,
                    "gov_revenue_this_tick": 1_100.0,
                    "gov_spending_this_tick": 1_000.0,
                },
            },
            {
                "tick": 30,
                "metrics": {
                    "gdp_this_tick": 130.0,
                    "unemployment_rate": 0.20,
                    "mean_happiness": 0.56,
                    "mean_health": 0.81,
                    "government_cash": 52_000.0,
                    "gov_revenue_this_tick": 1_400.0,
                    "gov_spending_this_tick": 800.0,
                },
            },
        ]

    decision_history = [
        {
            "tick": 4,
            "decisions": {"benefit_level": "high"},
            "applied_changes": {"benefit_level": "high"},
            "accepted_llm_changes": {"benefit_level": "high"},
            "rejected_changes": [],
            "rationale": "Unemployment was high, so I raised benefits.",
            "evidence": ["unemployment_rate=0.30", "government_cash=$50,000"],
            "data_seen": {
                "gdp_this_tick": 100.0,
                "unemployment_rate": 0.30,
                "mean_happiness": 0.50,
                "mean_health": 0.80,
                "government_cash": 50_000.0,
                "gov_revenue_this_tick": 1_000.0,
                "gov_spending_this_tick": 900.0,
                "gov_net_flow_this_tick": 100.0,
            },
        }
    ]

    short_memory = _build_recent_policy_memory(
        decision_history,
        FakeEconomy(),
        target_tick=8,
        lookback=3,
        impact_horizon=26,
    )[0]

    assert short_memory["short_term_impact"]["status"] == "available"
    assert short_memory["short_term_impact"]["provisional"] is True
    assert short_memory["mature_impact"]["status"] == "pending"
    assert short_memory["mature_impact"]["available_at_tick"] == 30
    assert short_memory["rationale"].startswith("Unemployment was high")
    assert short_memory["data_seen"]["gov_net_flow_this_tick"] == 100.0

    mature_memory = _build_recent_policy_memory(
        decision_history,
        FakeEconomy(),
        target_tick=30,
        lookback=3,
        impact_horizon=26,
    )[0]

    assert mature_memory["mature_impact"]["status"] == "available"
    assert mature_memory["mature_impact"]["gdp_delta_pct"] == pytest.approx(30.0)
    assert mature_memory["mature_impact"]["unemployment_delta_pp"] == pytest.approx(-10.0)
    assert mature_memory["mature_impact"]["mean_happiness_delta_pp"] == pytest.approx(6.0)
    assert mature_memory["mature_impact"]["mean_health_delta_pp"] == pytest.approx(1.0)
    assert mature_memory["mature_impact"]["government_cash_delta"] == pytest.approx(2_000.0)
    assert mature_memory["mature_impact"]["net_fiscal_flow_delta"] == pytest.approx(500.0)


def test_contract_recent_policy_memory_includes_hold_rationale():
    class FakeEconomy:
        metrics_history = [
            {
                "tick": 4,
                "metrics": {
                    "gdp_this_tick": 100.0,
                    "unemployment_rate": 0.10,
                    "mean_happiness": 0.50,
                    "mean_health": 0.80,
                    "government_cash": 10_000.0,
                    "gov_revenue_this_tick": 100.0,
                    "gov_spending_this_tick": 90.0,
                },
            },
            {
                "tick": 8,
                "metrics": {
                    "gdp_this_tick": 105.0,
                    "unemployment_rate": 0.08,
                    "mean_happiness": 0.51,
                    "mean_health": 0.79,
                    "government_cash": 10_200.0,
                    "gov_revenue_this_tick": 110.0,
                    "gov_spending_this_tick": 95.0,
                },
            },
        ]

    memory = _build_recent_policy_memory(
        [
            {
                "tick": 5,
                "decisions": {},
                "applied_changes": {},
                "rejected_changes": [],
                "rationale": "Holding policy steady while observing follow-through.",
                "evidence": ["unemployment_rate=0.10"],
                "data_seen": {"unemployment_rate": 0.10},
            }
        ],
        FakeEconomy(),
        target_tick=8,
        lookback=3,
        impact_horizon=26,
    )

    assert len(memory) == 1
    assert memory[0]["decisions"] == {}
    assert memory[0]["rationale"] == "Holding policy steady while observing follow-through."
    assert memory[0]["short_term_impact"]["status"] == "available"


def test_contract_llm_prompt_includes_regime_state_and_lever_effects(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=2, disable_shocks=True, seed=906)
    provider = QueueProvider([json.dumps({"decisions": {}, "reasoning": "Hold."})])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    asyncio.run(advisor.decide(economy))

    prompt = provider.prompts[-1]
    assert "Regime state" in prompt["user"]
    assert "warmup_active" in prompt["user"]
    assert "Higher investment_tax_rate taxes firm R&D directly" in prompt["system"]
    assert "technology_spending: ordered enum [none | low | medium | high]" in prompt["system"]
    assert "social_spending: ordered enum [none | low | medium | high]" in prompt["system"]
    assert "social_spending: happiness-only public-good support rises" in prompt["system"]
    assert "does not directly improve health" in prompt["system"]
    assert "bailout_policy: ordered enum [off | sector | all]" in prompt["system"]
    assert "bailout_budget: ordered enum [0 | 5000 | 10000 | 25000 | 50000]" in prompt["system"]


def test_contract_llm_prompt_includes_affordability_diagnostics(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=2, disable_shocks=True, seed=911)
    provider = QueueProvider([json.dumps({"fiscal_mode": "NORMAL", "primary_goal": "hold", "changes": {}})])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    asyncio.run(advisor.decide(economy))

    prompt = provider.prompts[-1]
    assert "[OBSERVED ECONOMIC DATA]" in prompt["user"]
    assert "[FISCAL CONTEXT]" in prompt["user"]
    assert "Revenue this tick/window" in prompt["user"]
    assert "Spending this tick/window" in prompt["user"]
    assert "Net fiscal flow" in prompt["user"]
    assert "Spending Breakdown" in prompt["user"]
    assert "unemployment_benefits_transfers" in prompt["user"]
    assert "social_spending" in prompt["user"]
    assert "sector_subsidies" in prompt["user"]
    assert "CORE INDICATORS:" in prompt["user"]
    assert "age=" in prompt["user"] or "+/-" in prompt["user"]
    assert "[AFFORDABILITY DIAGNOSTICS]" in prompt["user"]
    assert "Wages: mean=" in prompt["user"]
    assert "median=" in prompt["user"]
    assert "Global Firm Prices" in prompt["user"]
    assert "price/median_wage" in prompt["user"]
    assert "Housing Rent Burden" in prompt["user"]
    assert "price_stabilization_level: ordered enum [off | monitor | soft | strict]" in prompt["system"]
    assert "rent_stabilization_level: ordered enum [off | monitor | soft | strict]" in prompt["system"]


def test_contract_count_like_observed_metrics_are_nonnegative_integers(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=931)
    state = observe_node({}, economy)
    state["raw_metrics"].update(
        {
            "distressed_food_firms": 1.0,
            "bankruptcy_count": 0.0,
            "healthcare_denied_count": 0.0,
            "public_works_jobs": 0.0,
            "unemployment_rate": 1.25,
        }
    )

    constrained = apply_info_constraints_node(state, economy, CONFIG.llm, [])
    observed = constrained["observed_metrics"]

    for key in ("distressed_food_firms", "bankruptcy_count", "healthcare_denied_count", "public_works_jobs"):
        value = observed[key]["value"]
        assert isinstance(value, int)
        assert value >= 0
    assert 0.0 <= observed["unemployment_rate"]["value"] <= 1.0


def test_contract_llm_prompt_uses_ratio_scaled_fiscal_pressure(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=932)
    economy.last_tick_revenue = {1: 10_000.0}
    economy._update_budget_pressure(revenue=500.0, spending=1_500.0)
    provider = QueueProvider([json.dumps({"fiscal_mode": "NORMAL", "primary_goal": "hold", "changes": {}})])
    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    asyncio.run(advisor.decide(economy))

    prompt = provider.prompts[-1]["user"]
    assert "fiscal_pressure_ratio" in prompt
    assert "instant_deficit_to_gdp_ratio" in prompt
    assert "Fiscal Pressure:" not in prompt
    assert economy.government.fiscal_pressure < 1.0


def test_contract_soft_price_stabilization_limits_upward_move(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=912)
    firm = next(f for f in economy.firms if (f.good_category or "").lower() == "food")
    economy.government.set_lever("price_stabilization_target", "food")
    economy.government.set_lever("price_stabilization_level", "soft")
    firm.price = 100.0
    firm.min_price = 1.0
    firm.unit_cost = 50.0
    plan = {"price_next": 200.0, "markup_next": 3.0}

    economy._apply_price_stabilization_to_plan(firm, plan)

    assert plan["price_next"] == pytest.approx(100.0 * CONFIG.government.price_stabilization_soft_max_increase)
    assert economy.price_increase_limited_count == 1


def test_contract_unprofitable_price_stabilization_allows_cost_recovery(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=913)
    firm = next(f for f in economy.firms if (f.good_category or "").lower() == "food")
    economy.government.set_lever("price_stabilization_target", "food")
    economy.government.set_lever("price_stabilization_level", "strict")
    firm.price = 100.0
    firm.min_price = 1.0
    firm.unit_cost = 150.0
    firm.cash_balance = -1.0
    plan = {"price_next": 200.0, "markup_next": 1.0}

    economy._apply_price_stabilization_to_plan(firm, plan)

    assert plan["price_next"] >= firm.unit_cost
    assert plan["price_next"] < 200.0


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


def test_contract_social_spending_changes_wellbeing_multiplier(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=917)

    economy.government.cash_balance = 50_000.0
    economy.government.set_lever("social_spending", "high")
    spent = economy.government.invest_in_social_programs()
    funded_multiplier = economy.government.social_happiness_multiplier

    economy.government.set_lever("social_spending", "none")
    no_spend = economy.government.invest_in_social_programs()

    assert spent == pytest.approx(1500.0)
    assert funded_multiplier > 1.0
    assert no_spend == pytest.approx(0.0)
    assert economy.government.social_happiness_multiplier < funded_multiplier
    assert economy.government.to_dict()["social_spending"] == "none"


def test_contract_economy_warmup_uses_configured_ticks(tiny_economy_factory, monkeypatch):
    monkeypatch.setattr(CONFIG.time, "warmup_ticks", 0)
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=908)

    assert economy.in_warmup is False
    assert economy.warmup_ticks == 0


def test_contract_llm_government_scheduler_respects_warmup_start_and_interval(
    tiny_economy_factory,
    monkeypatch,
):
    economy = tiny_economy_factory(num_households=15, num_firms_per_category=1, disable_shocks=True, seed=905)
    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", True)
    monkeypatch.setattr(CONFIG.time, "warmup_ticks", 10)
    monkeypatch.setattr(CONFIG.llm, "government_start_tick", 15)
    monkeypatch.setattr(CONFIG.llm, "government_start_after_warmup_ticks", 5)
    monkeypatch.setattr(CONFIG.llm, "government_decision_interval", 26)

    due_ticks = []
    for tick in range(0, 70):
        economy.current_tick = tick
        if economy.should_run_llm_government():
            due_ticks.append(tick)

    assert due_ticks == [15, 41, 67]
    for tick in (10, 11, 12, 13, 14, 26, 40):
        economy.current_tick = tick
        assert economy.should_run_llm_government() is False


def test_contract_llm_government_scheduler_respects_warmup_plus_delay(
    tiny_economy_factory,
    monkeypatch,
):
    economy = tiny_economy_factory(num_households=15, num_firms_per_category=1, disable_shocks=True, seed=906)
    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", True)
    monkeypatch.setattr(CONFIG.time, "warmup_ticks", 20)
    monkeypatch.setattr(CONFIG.llm, "government_start_tick", 15)
    monkeypatch.setattr(CONFIG.llm, "government_start_after_warmup_ticks", 5)
    monkeypatch.setattr(CONFIG.llm, "government_decision_interval", 26)

    economy.current_tick = 24
    assert economy.should_run_llm_government() is False
    economy.current_tick = 25
    assert economy.should_run_llm_government() is True
    economy.current_tick = 51
    assert economy.should_run_llm_government() is True


def test_contract_server_llm_decision_interval_is_enforced(tiny_economy_factory, monkeypatch):
    manager = server.SimulationManager()
    manager.economy = tiny_economy_factory(num_households=15, num_firms_per_category=1, disable_shocks=True, seed=905)
    manager.tick = 15
    manager.economy.current_tick = 15

    calls = {"count": 0}
    captured_actions = []

    class DummyAdvisor:
        async def decide(self, economy):
            calls["count"] += 1
            await asyncio.sleep(0.05)
            economy.government.set_lever("public_works", "on")
            return {
                "tick": economy.current_tick,
                "decisions": {"public_works": "on"},
                "rationale": "Labor market support",
                "reasoning": "Labor market support",
                "evidence": ["unemployment_rate=0.31"],
                "decision_summary": "NORMAL/reduce_unemployment; accepted: public_works=on",
                "parse_ok": True,
                "elapsed_ms": 12.0,
                "provider": "mock/test",
            }

    async def ensure_ready():
        manager.llm_government = DummyAdvisor()
        return True

    def capture_policy_action(actor, action_type, payload, reason_summary):
        captured_actions.append(
            {
                "actor": actor,
                "action_type": action_type,
                "payload": payload,
                "reason_summary": reason_summary,
            }
        )

    monkeypatch.setattr(manager, "_ensure_llm_government", ensure_ready)
    monkeypatch.setattr(manager, "_buffer_policy_action", capture_policy_action)
    monkeypatch.setattr(manager.config.llm, "enable_llm_government", True)
    monkeypatch.setattr(manager.config.time, "warmup_ticks", 10)
    monkeypatch.setattr(manager.config.llm, "government_start_tick", 15)
    monkeypatch.setattr(manager.config.llm, "government_start_after_warmup_ticks", 5)
    monkeypatch.setattr(manager.config.llm, "government_decision_interval", 26)

    async def scenario():
        with use_config(manager.config):
            loop = asyncio.get_running_loop()
            started = loop.time()
            await manager._schedule_llm_government_if_due()
            elapsed = loop.time() - started

            assert elapsed < 0.02
            assert manager.llm_task is not None
            assert manager.llm_status == "thinking"
            assert manager.economy.government.public_works_toggle != "on"

            manager.economy.step()
            manager.tick = manager.economy.current_tick
            assert manager.economy.current_tick == 16
            assert manager.economy.government.public_works_toggle != "on"

            await manager.llm_task
            manager._collect_llm_task_result()
            assert calls["count"] == 1
            assert manager.pending_llm_decision is not None
            assert manager.economy.government.public_works_toggle != "on"

            manager._apply_llm_decision_at_boundary()

    asyncio.run(scenario())

    assert manager.latest_government_decision is not None
    assert manager.latest_government_decision["snapshotTick"] == 15
    assert manager.latest_government_decision["appliedTick"] == 16
    assert manager.economy.government.public_works_toggle == "on"
    assert captured_actions
    assert captured_actions[0]["payload"]["rationale"] == "Labor market support"
    assert captured_actions[0]["payload"]["evidence"] == ["unemployment_rate=0.31"]
    assert captured_actions[0]["reason_summary"] == "Labor market support"

    manager.tick = 16
    manager.economy.current_tick = 16

    async def assert_not_due():
        with use_config(manager.config):
            await manager._schedule_llm_government_if_due()

    asyncio.run(assert_not_due())
    assert manager.llm_task is None
    assert calls["count"] == 1


def test_contract_llm_enabled_disables_legacy_government_policy_chooser(tiny_economy_factory, monkeypatch):
    economy = tiny_economy_factory(num_households=18, num_firms_per_category=1, disable_shocks=True, seed=909)
    economy.configure_stabilizers(government=True)
    monkeypatch.setattr(CONFIG.llm, "enable_llm_government", True)

    calls = {"count": 0}

    def fail_if_called():
        calls["count"] += 1
        raise AssertionError("Legacy automatic government policy chooser should not run with LLM enabled")

    monkeypatch.setattr(economy, "_adjust_government_policy", fail_if_called)

    economy.step()

    assert calls["count"] == 0
