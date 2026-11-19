"""Food-credit action space and provider-free government decisions."""

import asyncio
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from config import CONFIG, clone_config, use_config
from policy_schema import (
    ORDERED_LEVERS,
    POLICY_SCHEMA,
    SIMPLE_ENUM_LEVERS,
    TAX_LIMITS,
    normalize_food_credit_budget,
    render_policy_schema_for_prompt,
)
from policy_vectors import PolicyVectorError, validate_policy_vector
from server import SetupConfig
from sim_setup import build_economy_from_setup
from tools.llm.llm_government import (
    LLMGovernmentAdvisor,
    _build_user_prompt,
    build_allowed_government_actions,
    sanitize_llm_government_changes,
)
from tools.llm.llm_provider import LLMProvider


class RecordedProvider(LLMProvider):
    def __init__(self, changes):
        self.changes = iter(changes)
        self.prompts = []

    @property
    def name(self):
        return "mock/food-credit"

    async def health_check(self):
        return True

    async def complete(self, system, user, **kwargs):
        self.prompts.append({"system": system, "user": user})
        return json.dumps({"changes": next(self.changes)})


@pytest.mark.parametrize("value, expected", [
    (0, 0.0),
    (-0.0, 0.0),
    (300.50, 300.50),
    (Decimal("300.500"), 300.50),
    (0.1 + 0.2, 0.30),
    (123456.78, 123456.78),
])
def test_budget_is_normalized_as_currency(value, expected):
    assert normalize_food_credit_budget(value) == expected
    assert validate_policy_vector({"food_credit_weekly_budget": value}) == {
        "food_credit_weekly_budget": expected,
    }


@pytest.mark.parametrize("value", [
    True, False, None, "300.50", [], {}, -0.01, -0.001, 1.001, 300.505, 5e-324,
    float("nan"), float("inf"), -float("inf"), Decimal("1e309"), 10**400,
    Decimal("9007199254740993"),
])
def test_budget_rejects_invalid_or_unrepresentable_values(value):
    with pytest.raises(ValueError, match="food_credit_weekly_budget"):
        normalize_food_credit_budget(value)
    with pytest.raises(PolicyVectorError, match="food_credit_weekly_budget"):
        validate_policy_vector({"food_credit_weekly_budget": value})


def test_budget_is_numeric_and_independent_of_the_toggle():
    name = "food_credit_weekly_budget"
    assert POLICY_SCHEMA[name]["type"] == "currency"
    assert name not in TAX_LIMITS and name not in ORDERED_LEVERS and name not in SIMPLE_ENUM_LEVERS
    assert validate_policy_vector({name: 300.50, "food_credit_policy": "off"}) == {
        name: 300.50, "food_credit_policy": "off",
    }
    assert validate_policy_vector({"food_credit_policy": "on"}) == {"food_credit_policy": "on"}
    assert name in render_policy_schema_for_prompt(include_food_credit=True)
    assert "food_credit_" not in render_policy_schema_for_prompt(include_food_credit=False)


@pytest.mark.parametrize("invalid", [True, -0.01, 0.001, float("inf"), "5.00"])
def test_sanitizer_uses_the_shared_budget_validation(invalid):
    gov = SimpleNamespace(cash_balance=1000, supports_food_credit=True, food_credit_weekly_budget=5.0)
    clean, rejected = sanitize_llm_government_changes(
        {"food_credit_weekly_budget": invalid}, {"food_credit_weekly_budget": 5.0}, gov, 1000, 0.0,
    )
    assert clean == {}
    assert rejected[0]["reason"] == "invalid_food_credit_budget"


def test_spending_guard_and_examples_compare_the_snapshot_even_when_zero():
    gov = SimpleNamespace(
        cash_balance=-1.0, supports_food_credit=True,
        food_credit_weekly_budget=50.0, food_credit_policy="off",
    )
    economy = SimpleNamespace(households=[object()] * 10, firms=[])
    snapshot = {"food_credit_weekly_budget": 0.0, "food_credit_policy": "off"}
    mask = build_allowed_government_actions(snapshot, gov, 1000, 0.0, economy)
    assert mask["blocked"]["simple"]["food_credit_weekly_budget"] == [
        {"value": 2.5, "reason": "spending_increase_during_fiscal_stress"},
        {"value": 5.0, "reason": "spending_increase_during_fiscal_stress"},
    ]
    for changes in ({"food_credit_weekly_budget": 0.01}, {"food_credit_policy": "on"}):
        clean, rejected = sanitize_llm_government_changes(changes, snapshot, gov, 1000, 0.0, economy)
        assert clean == {}
        assert rejected[0]["reason"] == "spending_increase_during_fiscal_stress"
    snapshot.update(food_credit_weekly_budget=100.0, food_credit_policy="on")
    for changes in ({"food_credit_weekly_budget": 7.25}, {"food_credit_policy": "off"}):
        clean, rejected = sanitize_llm_government_changes(changes, snapshot, gov, 1000, 0.0, economy)
        assert clean == changes and not rejected
    mask = build_allowed_government_actions(snapshot, gov, 1000, 0.0, economy)
    assert mask["allowed"]["simple"]["food_credit_weekly_budget"] == [0.0, 2.5, 5.0]
    clean, rejected = sanitize_llm_government_changes(
        {"food_credit_weekly_budget": 7.25, "food_credit_policy": "off"}, snapshot, gov, 1000, 0.0, economy,
    )
    assert clean == {"food_credit_weekly_budget": 7.25, "food_credit_policy": "off"}
    assert not rejected


@pytest.mark.parametrize("population, expected", [
    (0, [0.0]),
    (3, [0.0, 1.25, 2.50]),
    (10, [0.0, 2.50, 5.00]),
    (15, [0.0, 3.75, 7.50]),
])
def test_mask_examples_use_full_coverage_for_the_actual_recipient_count(population, expected):
    gov = SimpleNamespace(cash_balance=1000, supports_food_credit=True, food_credit_weekly_budget=99.0)
    economy = SimpleNamespace(households=[object()] * population, firms=[])
    mask = build_allowed_government_actions({"food_credit_weekly_budget": 99.0}, gov, 1000, 0.0, economy)
    assert mask["allowed"]["simple"]["food_credit_weekly_budget"] == expected


def test_provider_can_change_cap_and_toggle_independently_in_income_first():
    setup = SetupConfig(num_households=10, num_firms=1, seed=43, payment_sequence="income_first")
    changes = [
        {"food_credit_weekly_budget": 0},
        {"food_credit_weekly_budget": 300.50},
        {"food_credit_policy": "on"},
        {"food_credit_weekly_budget": 7.25},
        {"food_credit_policy": "off"},
    ]
    provider = RecordedProvider(changes)
    with use_config(clone_config()):
        economy, _ = build_economy_from_setup(setup, 43)
        economy.government.cash_balance = 100000.0
        advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)
        results = [asyncio.run(advisor.decide(economy)) for _ in changes]
        assert [result["decisions"] for result in results] == changes
        assert results[0]["current_policy_before"]["food_credit_weekly_budget"] == 5.0
        assert results[0]["current_policy_after"]["food_credit_policy"] == "off"
        assert results[1]["current_policy_before"]["food_credit_weekly_budget"] == 0.0
        assert results[1]["current_policy_after"]["food_credit_policy"] == "off"
        assert results[3]["current_policy_after"]["food_credit_policy"] == "on"
        assert results[4]["current_policy_after"]["food_credit_weekly_budget"] == 7.25
    system, user = provider.prompts[1]["system"], provider.prompts[1]["user"]
    assert "food_credit_policy: enum [off | on]" in system
    assert "food_credit_weekly_budget: nonnegative dollar amount in whole cents" in system
    assert "$2.50" in system and "least-liquid fifth" in system and "prorate equally" in system
    assert "2 eligible households and full coverage costs $5.00 per week" in system
    assert "- food_credit_weekly_budget: 0.0" in user
    assert "food_credit_weekly_budget (examples, not exclusive): [2.5, 5.0]" in user
    assert "including above full coverage" in user


def test_provider_does_not_see_or_use_food_credit_in_income_late():
    # Construct and observe an unsupported sequence; no simulation ticks are run.
    setup = SetupConfig(num_households=10, num_firms=1, seed=43, payment_sequence="income_late")
    provider = RecordedProvider([{"food_credit_policy": "on", "food_credit_weekly_budget": 300.50}])
    with use_config(clone_config()):
        economy, _ = build_economy_from_setup(setup, 43)
        economy.government.cash_balance = 100000.0
        result = asyncio.run(LLMGovernmentAdvisor(provider, CONFIG.llm).decide(economy))
    assert result["decisions"] == {}
    assert [item["reason"] for item in result["rejected_changes"]] == [
        "food_credit_requires_income_first", "food_credit_requires_income_first",
    ]
    assert "food_credit_" not in provider.prompts[0]["system"]
    assert "food_credit_" not in provider.prompts[0]["user"]
    assert not any(key.startswith("food_credit_") for key in result["current_policy_before"])
    assert not any(key.startswith("food_credit_") for key in result["current_policy_after"])


def test_user_prompt_can_report_food_credit_turnover():
    prompt = _build_user_prompt(
        raw_metrics={"payment": {"fiscal": {"food_credit": {"issued": 2.5, "redeemed": 1, "outstanding": 1.5}}}},
        sector_diagnostics={},
        current_policy={"food_credit_policy": "on", "food_credit_weekly_budget": 5.0},
    )
    assert "issued $2.50, redeemed $1.00, outstanding $1.50" in prompt
