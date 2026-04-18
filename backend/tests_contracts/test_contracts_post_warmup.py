import pickle

import pytest

from config import CONFIG
from run_large_simulation import create_large_economy
from tests_contracts.factories import seed_everything


SCENARIO_SEED = 20260403
POST_WARMUP_HOUSEHOLDS = 120
POST_WARMUP_WARMUP_TICKS = 8
POST_WARMUP_SETTLE_LIMIT = 12
POST_WARMUP_MEASURE_TICKS = 8


def _no_random_shocks() -> None:
    """Keep post-warmup policy comparisons deterministic."""


def _private_firms(economy):
    return [firm for firm in economy.firms if not firm.is_baseline]


def _avg(rows, key: str) -> float:
    return sum(float(row[key]) for row in rows) / max(1, len(rows))


def _stress_private_food_firms(economy) -> None:
    for firm in economy.firms:
        if firm.is_baseline or (firm.good_category or "").lower() != "food":
            continue
        firm.cash_balance = min(float(firm.cash_balance), 120.0)
        firm.age_in_ticks = max(int(getattr(firm, "age_in_ticks", 0)), 10)
        firm.last_revenue = min(float(getattr(firm, "last_revenue", 0.0)), 15.0)
        firm.last_profit = min(float(getattr(firm, "last_profit", 0.0)), -250.0)
        if not firm.employees:
            firm.employees = [9_000 + firm.firm_id, 9_100 + firm.firm_id]
        firm.actual_wages = {employee_id: max(45.0, firm.wage_offer) for employee_id in firm.employees}
        firm.inventory_units = max(float(firm.inventory_units), 300.0)
        firm.price = min(float(firm.price), 7.0)


def _collect_policy_history(
    state_bytes: bytes,
    *,
    levers: dict | None = None,
    stressor=None,
    ticks: int = POST_WARMUP_MEASURE_TICKS,
):
    seed_everything(SCENARIO_SEED)
    economy = pickle.loads(state_bytes)
    economy._apply_random_shocks = _no_random_shocks

    if stressor is not None:
        stressor(economy)

    for lever, value in (levers or {}).items():
        economy.government.set_lever(lever, value)

    history = []
    for _ in range(ticks):
        economy.step()
        metrics = dict(economy.get_economic_metrics())
        private = _private_firms(economy)
        private_food = [firm for firm in private if (firm.good_category or "").lower() == "food"]
        metrics["private_mean_profit"] = (
            sum(float(getattr(firm, "last_profit", 0.0)) for firm in private) / max(1, len(private))
        )
        metrics["private_median_cash"] = (
            sorted(float(firm.cash_balance) for firm in private)[len(private) // 2] if private else 0.0
        )
        metrics["private_food_loan_principal"] = sum(
            float(getattr(firm, "government_loan_principal", 0.0)) for firm in private_food
        )
        history.append(metrics)
    return history


@pytest.fixture(scope="module")
def post_warmup_large_state() -> bytes:
    original_warmup_ticks = CONFIG.time.warmup_ticks
    seed_everything(SCENARIO_SEED)
    CONFIG.time.warmup_ticks = POST_WARMUP_WARMUP_TICKS
    try:
        economy = create_large_economy(num_households=POST_WARMUP_HOUSEHOLDS)

        for _ in range(economy.warmup_ticks):
            economy.step()

        settle_ticks = 0
        while not _private_firms(economy) and settle_ticks < POST_WARMUP_SETTLE_LIMIT:
            economy.step()
            settle_ticks += 1

        assert economy.in_warmup is False
        assert _private_firms(economy), "expected private firms to activate after warmup"
        return pickle.dumps(economy, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        CONFIG.time.warmup_ticks = original_warmup_ticks


def test_contract_post_warmup_wage_tax_trades_household_cash_for_revenue(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    high_tax = _collect_policy_history(post_warmup_large_state, levers={"wage_tax_rate": 0.35})

    assert _avg(high_tax, "gov_revenue_this_tick") > _avg(baseline, "gov_revenue_this_tick")
    assert _avg(high_tax, "median_household_cash") < _avg(baseline, "median_household_cash")
    assert _avg(high_tax, "mean_happiness") < _avg(baseline, "mean_happiness")


def test_contract_post_warmup_profit_tax_reduces_private_profitability(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    high_profit_tax = _collect_policy_history(post_warmup_large_state, levers={"profit_tax_rate": 0.35})

    assert _avg(high_profit_tax, "gov_revenue_this_tick") > _avg(baseline, "gov_revenue_this_tick")
    assert _avg(high_profit_tax, "private_mean_profit") < _avg(baseline, "private_mean_profit")
    assert _avg(high_profit_tax, "private_median_cash") <= _avg(baseline, "private_median_cash")


def test_contract_post_warmup_food_subsidy_supports_affordability(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    food_subsidy = _collect_policy_history(
        post_warmup_large_state,
        levers={"sector_subsidy_target": "food", "sector_subsidy_level": 25},
    )

    assert _avg(food_subsidy, "gov_subsidy_spend_this_tick") > 0.0
    assert _avg(food_subsidy, "median_household_cash") > _avg(baseline, "median_household_cash")
    assert _avg(food_subsidy, "mean_happiness") >= _avg(baseline, "mean_happiness")


def test_contract_post_warmup_minimum_wage_binds_and_lifts_pay(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    high_floor = _collect_policy_history(post_warmup_large_state, levers={"minimum_wage_policy": "high"})

    assert _avg(high_floor, "wage_floor_binding_share") > max(0.30, _avg(baseline, "wage_floor_binding_share") + 0.30)
    assert _avg(high_floor, "mean_wage") > _avg(baseline, "mean_wage")


def test_contract_post_warmup_public_works_absorbs_some_unemployment(post_warmup_large_state):
    benefits_only = _collect_policy_history(post_warmup_large_state, levers={"benefit_level": "high"})
    public_works = _collect_policy_history(
        post_warmup_large_state,
        levers={"benefit_level": "high", "public_works": "on"},
    )

    assert _avg(public_works, "public_works_jobs") > 0.0
    assert _avg(public_works, "unemployment_rate") < _avg(benefits_only, "unemployment_rate")
    assert _avg(public_works, "gov_spending_this_tick") > _avg(benefits_only, "gov_spending_this_tick")


def test_contract_post_warmup_technology_spending_improves_quality(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    high_tech = _collect_policy_history(post_warmup_large_state, levers={"technology_spending": "high"})

    assert _avg(high_tech, "technology_quality") > _avg(baseline, "technology_quality")
    assert _avg(high_tech, "effective_mean_quality") > _avg(baseline, "effective_mean_quality")
    assert _avg(high_tech, "government_cash") < _avg(baseline, "government_cash")


def test_contract_post_warmup_infrastructure_spending_raises_productivity(post_warmup_large_state):
    baseline = _collect_policy_history(post_warmup_large_state)
    high_infra = _collect_policy_history(post_warmup_large_state, levers={"infrastructure_spending": "high"})

    assert _avg(high_infra, "infrastructure_productivity") > _avg(baseline, "infrastructure_productivity")
    assert _avg(high_infra, "government_cash") < _avg(baseline, "government_cash")


def test_contract_post_warmup_sector_bailouts_are_explicit_and_budgeted(post_warmup_large_state):
    no_bailout = _collect_policy_history(
        post_warmup_large_state,
        stressor=_stress_private_food_firms,
        ticks=6,
    )
    sector_bailout = _collect_policy_history(
        post_warmup_large_state,
        levers={"bailout_policy": "sector", "bailout_target": "food", "bailout_budget": 10_000},
        stressor=_stress_private_food_firms,
        ticks=6,
    )

    assert _avg(no_bailout, "gov_bailout_spend_this_tick") == 0.0
    assert _avg(no_bailout, "private_food_loan_principal") == 0.0
    assert _avg(sector_bailout, "gov_bailout_spend_this_tick") > 0.0
    assert _avg(sector_bailout, "private_food_loan_principal") > 0.0
