import pytest

from policy_vectors import PolicyVectorError, validate_policy_vector


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
        validate_policy_vector({"bailout_policy": "all", "bailout_target": "food"})
    assert validate_policy_vector({"bailout_policy": "all", "bailout_target": "food", "bailout_budget": 5000}) == {
        "bailout_policy": "all", "bailout_target": "food", "bailout_budget": 5000,
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
