import pytest

from policy_vectors import PolicyVectorError, policy_group_errors, validate_policy_vector

# The bailout rule, shared with the AI mayor's prompt (llm_government.py) and the new
# frontend (frontend-react/src/next/policyRules.js): target rule first, then budget.
OFF_TARGET = "bailout_policy 'off' lends nothing, so bailout_target must be 'none'"
OFF_BUDGET = "bailout_policy 'off' lends nothing, so bailout_budget must be 0"
SECTOR_TARGET = "bailout_policy 'sector' needs a bailout_target of food, housing, services or healthcare"
SECTOR_BUDGET = "bailout_policy 'sector' needs a bailout_budget above 0"
ALL_TARGET = "bailout_policy 'all' covers every sector, so bailout_target must be 'none'"
ALL_BUDGET = "bailout_policy 'all' needs a bailout_budget above 0"


def test_empty_vector_is_allowed():
    assert validate_policy_vector({}) == {}


def test_taxes_are_coerced_to_float_and_range_checked():
    assert validate_policy_vector({"wage_tax_rate": "0.30"}) == {"wage_tax_rate": 0.30}
    with pytest.raises(PolicyVectorError, match="wage_tax_rate"):
        validate_policy_vector({"wage_tax_rate": 0.9})


def test_ordered_and_enum_levers_must_be_known_values():
    assert validate_policy_vector({"benefit_level": "high", "public_works": "on"}) == {
        "benefit_level": "high", "public_works": "on",
    }
    with pytest.raises(PolicyVectorError, match="benefit_level"):
        validate_policy_vector({"benefit_level": "generous"})
    with pytest.raises(PolicyVectorError, match="unknown lever"):
        validate_policy_vector({"birth_rate": 0.1})


def test_integer_levers_accept_numeric_strings():
    assert validate_policy_vector({"sector_subsidy_target": "food", "sector_subsidy_level": "25"}) == {
        "sector_subsidy_target": "food", "sector_subsidy_level": 25,
    }


def test_grouped_levers_validate_together():
    with pytest.raises(PolicyVectorError, match="sector_subsidy_target"):
        validate_policy_vector({"sector_subsidy_level": 25})
    with pytest.raises(PolicyVectorError, match="bailout_budget"):
        validate_policy_vector({"bailout_policy": "all"})
    assert validate_policy_vector({"bailout_policy": "all", "bailout_budget": 5000}) == {
        "bailout_policy": "all", "bailout_budget": 5000,
    }


def test_unhashable_enum_values_raise_policy_vector_error():
    with pytest.raises(PolicyVectorError, match="public_works"):
        validate_policy_vector({"public_works": ["on"]})


def test_overflowing_integer_lever_raises_policy_vector_error():
    with pytest.raises(PolicyVectorError, match="bailout_budget"):
        validate_policy_vector({"bailout_budget": "1e309"})


def test_non_finite_tax_raises_policy_vector_error():
    with pytest.raises(PolicyVectorError, match="wage_tax_rate"):
        validate_policy_vector({"wage_tax_rate": float("nan")})


def test_a_group_rule_error_names_its_group():
    with pytest.raises(PolicyVectorError, match="sector_subsidy_target") as subsidy:
        validate_policy_vector({"sector_subsidy_level": 25})
    assert subsidy.value.group == "sector_subsidy"
    with pytest.raises(PolicyVectorError, match="bailout_target") as bailout:
        validate_policy_vector({"bailout_policy": "sector"})
    assert bailout.value.group == "bailout"
    with pytest.raises(PolicyVectorError, match="wage_tax_rate") as lever:
        validate_policy_vector({"wage_tax_rate": 0.9})
    assert lever.value.group is None


def test_policy_group_errors_reports_every_failing_group():
    assert policy_group_errors({}) == {}
    assert policy_group_errors({"sector_subsidy_level": 25, "bailout_policy": "all"}) == {
        "sector_subsidy": "sector_subsidy_level above 0 needs a sector_subsidy_target other than 'none'",
        "bailout": ALL_BUDGET,
    }
    assert policy_group_errors({"bailout_policy": "sector", "bailout_target": "food", "bailout_budget": 5000}) == {}


@pytest.mark.parametrize("vector, rule", [
    ({"bailout_target": "food"}, OFF_TARGET),
    ({"bailout_policy": "off", "bailout_target": "food"}, OFF_TARGET),
    ({"bailout_policy": "off", "bailout_budget": 5000}, OFF_BUDGET),
    ({"bailout_policy": "off", "bailout_target": "food", "bailout_budget": 5000}, OFF_TARGET),
    ({"bailout_policy": "sector", "bailout_budget": 5000}, SECTOR_TARGET),
    ({"bailout_policy": "sector", "bailout_target": "none", "bailout_budget": 5000}, SECTOR_TARGET),
    ({"bailout_policy": "sector", "bailout_target": "food", "bailout_budget": 0}, SECTOR_BUDGET),
    ({"bailout_policy": "sector"}, SECTOR_TARGET),
    ({"bailout_policy": "all", "bailout_target": "food", "bailout_budget": 5000}, ALL_TARGET),
    ({"bailout_policy": "all", "bailout_target": "food"}, ALL_TARGET),
    ({"bailout_policy": "all", "bailout_target": "none", "bailout_budget": 0}, ALL_BUDGET),
])
def test_bailout_rule_rejects_each_broken_combination_with_its_rule(vector, rule):
    assert policy_group_errors(vector) == {"bailout": rule}
    with pytest.raises(PolicyVectorError) as error:
        validate_policy_vector(vector)
    assert str(error.value) == rule
    assert error.value.group == "bailout"


@pytest.mark.parametrize("vector", [
    {},
    {"bailout_policy": "off", "bailout_target": "none", "bailout_budget": 0},
    {"bailout_policy": "sector", "bailout_target": "food", "bailout_budget": 5000},
    {"bailout_policy": "sector", "bailout_target": "healthcare", "bailout_budget": 50000},
    {"bailout_policy": "all", "bailout_target": "none", "bailout_budget": 5000},
    {"bailout_policy": "all", "bailout_budget": 5000},
])
def test_bailout_rule_accepts_coherent_combinations(vector):
    assert policy_group_errors(vector) == {}
    assert validate_policy_vector(vector) == vector
