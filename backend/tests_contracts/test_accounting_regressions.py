import pytest

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def _make_firm(
    firm_id: int,
    category: str = "Food",
    *,
    cash_balance: float = 40_000.0,
    wage_offer: float = 40.0,
    price: float = 10.0,
    inventory_units: float = 500.0,
    max_rental_units: int = 0,
) -> FirmAgent:
    return FirmAgent(
        firm_id=firm_id,
        good_name=f"{category}Firm{firm_id}",
        cash_balance=cash_balance,
        inventory_units=inventory_units,
        good_category=category,
        quality_level=5.0,
        wage_offer=wage_offer,
        price=price,
        expected_sales_units=60.0,
        production_capacity_units=600.0 if category != "Housing" else float(max(max_rental_units, 1)),
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
        max_rental_units=max_rental_units,
    )


def test_contract_tier2_repayments_return_to_government_and_interest_income_accrues():
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)
    tier1_firm = _make_firm(1, cash_balance=5_000.0)
    tier2_firm = _make_firm(2, cash_balance=5_000.0)
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(
        households=[household],
        firms=[tier1_firm, tier2_firm],
        government=govt,
        bank=bank,
    )

    bank.originate_loan("firm", tier1_firm.firm_id, 1_000.0, 0.05, 10)
    gov_backed = bank.issue_government_backed_loan("firm", tier2_firm.firm_id, 1_000.0, 0.05, 10, govt)
    assert gov_backed is not None

    government_cash_after_origination = govt.cash_balance

    bank.reset_tick_telemetry()
    economy._collect_bank_loan_repayments()

    scheduled_payment = 1_000.0 * 1.05 / 10.0

    assert govt.cash_balance == pytest.approx(government_cash_after_origination + scheduled_payment)
    assert bank.last_tick_interest_income == pytest.approx(5.0)
    assert bank.last_tick_repayments == pytest.approx(scheduled_payment * 2.0)
    assert bank.cash_reserves == pytest.approx(99_105.0)


def test_contract_firm_loans_write_off_after_12_missed_payments():
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)
    firm = _make_firm(1, cash_balance=0.0)
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(
        households=[household],
        firms=[firm],
        government=govt,
        bank=bank,
    )

    bank.originate_loan("firm", firm.firm_id, 1_200.0, 0.05, 20)
    initial_outstanding = bank.total_loans_outstanding

    for _ in range(12):
        economy._collect_bank_loan_repayments()

    loan = bank.active_loans[0]
    assert loan["remaining"] == pytest.approx(0.0)
    assert bank.total_loans_outstanding < initial_outstanding
    assert bank.last_tick_defaults > 0.0
    assert bank.get_firm_credit_score(firm.firm_id) == pytest.approx(0.0)

    bank.cleanup_settled_loans()
    assert all(active["borrower_id"] != firm.firm_id for active in bank.active_loans)


def test_contract_emergency_wage_cut_overrides_stale_wage_plan():
    firm = _make_firm(1, cash_balance=20_000.0, wage_offer=100.0, price=20.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}

    firm.apply_sales_and_profit(
        {
            "units_sold": 0.0,
            "revenue": 500.0,
            "profit_taxes_paid": 0.0,
        }
    )
    firm.apply_price_and_wage_updates(
        {"price_next": firm.price, "markup_next": firm.markup},
        {"wage_offer_next": 105.0},
    )

    assert firm.wage_offer == pytest.approx(85.0)


def test_contract_price_floor_covers_unit_labor_cost():
    firm = _make_firm(1, cash_balance=20_000.0, wage_offer=100.0, price=30.0)
    firm.employees = [1, 2, 3, 4, 5]
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.apply_production_and_costs({"realized_production_units": 10.0, "other_variable_costs": 0.0})
    firm.inventory_units = 250.0
    firm.expected_sales_units = 20.0

    price_plan = firm.plan_pricing(sell_through_rate=0.1, unemployment_rate=0.1, in_warmup=False)

    assert price_plan["price_next"] >= 52.5


def test_contract_batch_consumption_budget_reserves_existing_rent():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=100.0)
    household.renting_from_firm_id = 9
    household.monthly_rent = 80.0
    firm = _make_firm(1)
    govt = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[household], firms=[firm], government=govt)

    plans = economy._batch_plan_consumption(
        market_prices={firm.good_name: firm.price},
        category_market_snapshot={
            "food": [
                {
                    "firm_id": firm.firm_id,
                    "good_name": firm.good_name,
                    "price": firm.price,
                    "quality": firm.quality_level,
                    "inventory": firm.inventory_units,
                }
            ]
        },
        good_category_lookup=economy._build_good_category_lookup(),
        unemployment_rate=0.0,
    )

    assert plans[household.household_id]["planned_budget"] <= 20.0 + 1e-9


def test_contract_new_rental_respects_existing_goods_budget():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=100.0)
    household.apply_labor_outcome({"employer_id": 77, "wage": 300.0, "employer_category": "Food"})
    housing_firm = _make_firm(
        1,
        category="Housing",
        cash_balance=40_000.0,
        price=90.0,
        inventory_units=0.0,
        max_rental_units=1,
    )
    govt = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[household], firms=[housing_firm], government=govt)
    economy._planned_consumption_budget_by_household = {household.household_id: 20.0}

    economy._clear_housing_rental_market()

    assert household.renting_from_firm_id is None
    assert household.cash_balance == pytest.approx(100.0)


def test_contract_household_spending_clamps_to_cash_floor():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=30.0)
    firm = _make_firm(1)
    govt = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[household], firms=[firm], government=govt)

    economy._batch_apply_household_updates(
        transfer_plan={},
        wage_taxes={},
        per_household_purchases={household.household_id: {firm.good_name: (10.0, 10.0)}},
        good_category_lookup=economy._build_good_category_lookup(),
    )

    assert household.cash_balance == pytest.approx(0.0)
    assert household.last_consumption_spending == pytest.approx(30.0)
    assert household.food_consumed_this_tick == pytest.approx(3.0)


def test_contract_desperation_wage_discount_stays_positive_and_monotonic():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=10_000.0)
    household.reservation_wage = 100.0
    household.price_beliefs["housing"] = 100.0
    household.price_beliefs["food"] = 10.0

    calm_wage = household.plan_labor_supply()["reservation_wage"]

    household.cash_balance = 0.0
    household.health = 0.0
    household.unemployment_duration = CONFIG.households.unemployed_forced_dissaving_duration
    desperate_wage = household.plan_labor_supply()["reservation_wage"]

    expected_floor = max(1.0, 100.0 * (1.0 - CONFIG.households.desperation_wage_discount))

    assert calm_wage == pytest.approx(100.0)
    assert desperate_wage == pytest.approx(expected_floor)
    assert 1.0 <= desperate_wage < calm_wage


def test_contract_zero_revenue_firm_cannot_receive_tier1_bank_loan():
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)
    firm = _make_firm(1, cash_balance=0.0)
    firm.trailing_revenue_12t = 0.0
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(
        households=[household],
        firms=[firm],
        government=govt,
        bank=bank,
    )

    issued = economy._issue_firm_loan(firm, amount=1_000.0, term_ticks=52, govt_rate=0.03)

    assert issued is True
    assert bank.active_loans == []
    assert firm.bank_loan_remaining == pytest.approx(0.0)
    assert firm.government_loan_remaining > 0.0


def test_contract_partial_payments_do_not_reset_missed_payment_streak():
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)
    firm = _make_firm(1, cash_balance=10.0)
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(
        households=[household],
        firms=[firm],
        government=govt,
        bank=bank,
    )

    loan = bank.originate_loan("firm", firm.firm_id, 1_000.0, 0.0, 2)

    economy._collect_bank_loan_repayments()
    assert loan["missed_payments"] == 1

    firm.cash_balance = 10.0
    economy._collect_bank_loan_repayments()
    assert loan["missed_payments"] == 2

    firm.cash_balance = 1_000.0
    economy._collect_bank_loan_repayments()
    assert loan["missed_payments"] == 0


def test_contract_goods_market_legacy_fallback_uses_quality_not_price_only():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    household.quality_lavishness = 5.0
    household.price_sensitivity = 1.0
    household.price_beliefs["FoodBundle"] = 10.0

    low_quality = _make_firm(1, category="Food", price=10.0, inventory_units=10.0)
    high_quality = _make_firm(2, category="Food", price=10.0, inventory_units=10.0)
    low_quality.good_name = "FoodBundle"
    high_quality.good_name = "FoodBundle"
    low_quality.quality_level = 0.5
    high_quality.quality_level = 1.0

    govt = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[household], firms=[low_quality, high_quality], government=govt)

    _, per_firm_sales = economy._clear_goods_market(
        {
            household.household_id: {
                "household_id": household.household_id,
                "planned_purchases": {"FoodBundle": 1.0},
            }
        },
        [low_quality, high_quality],
    )

    assert per_firm_sales[high_quality.firm_id]["units_sold"] == pytest.approx(1.0)
    assert per_firm_sales[low_quality.firm_id]["units_sold"] == pytest.approx(0.0)


def test_contract_deposit_interest_stays_in_deposit_balance():
    bank = BankAgent(cash_reserves=10_000.0)
    govt = GovernmentAgent(cash_balance=10_000.0)
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=0.0)
    household.bank_deposit = 1_000.0
    household.deposit_buffer_weeks = 0.0
    bank.total_deposits = 1_000.0
    firm = _make_firm(1)
    economy = Economy(households=[household], firms=[firm], government=govt, bank=bank)

    economy._process_bank_deposits()

    assert household.cash_balance == pytest.approx(0.0)
    assert household.bank_deposit > 1_000.0


def test_contract_public_works_startup_is_funded_by_government():
    govt = GovernmentAgent(cash_balance=50_000.0)
    govt.set_lever("public_works", "on")
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    firm = _make_firm(1)
    economy = Economy(households=[household], firms=[firm], government=govt)
    initial_gov_cash = govt.cash_balance

    economy._ensure_public_works_capacity(unemployment_rate=0.2)

    public_works_firms = [f for f in economy.firms if f.good_category == "PublicWorks"]
    assert len(public_works_firms) == 1
    assert govt.cash_balance < initial_gov_cash


def test_contract_continuing_wage_refresh_syncs_household_wages():
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    firm = _make_firm(1, cash_balance=50_000.0, wage_offer=100.0)
    govt = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[household], firms=[firm], government=govt)

    household.apply_labor_outcome(
        {"employer_id": firm.firm_id, "wage": 100.0, "employer_category": firm.good_category}
    )
    firm.employees = [household.household_id]
    firm.actual_wages = {household.household_id: 100.0}
    economy.current_tick = 50

    economy._update_continuing_employee_wages()
    refreshed_wage = firm.actual_wages[household.household_id]

    assert refreshed_wage > 100.0
    assert household.wage == pytest.approx(refreshed_wage)

    firm_plans = {
        firm.firm_id: {
            "planned_production_units": 0.0,
            "planned_hires_count": 0,
            "planned_layoffs_ids": [],
            "updated_expected_sales": firm.expected_sales_units,
        }
    }
    wage_plans = {firm.firm_id: {"wage_offer_next": firm.wage_offer}}
    labor_plans = {
        household.household_id: {
            "household_id": household.household_id,
            "searching_for_job": False,
            "reservation_wage": household.reservation_wage,
            "skills_level": household.skills_level,
            "medical_only": False,
        }
    }
    _, household_outcomes = economy._run_labor_matching(firm_plans, wage_plans, labor_plans)

    assert household_outcomes[household.household_id]["wage"] == pytest.approx(refreshed_wage)


def test_contract_lossmaking_firm_keeps_minimum_rd_floor_until_cash_stress():
    firm = _make_firm(1, cash_balance=10_000.0, wage_offer=100.0)
    firm.employees = [1, 2, 3, 4]
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.net_profit = -500.0

    rd_spending = firm.apply_rd_and_quality_update(10_000.0)
    assert rd_spending == pytest.approx(100.0)

    firm.cash_balance = firm._current_wage_bill() * 4.0 - 1.0
    firm.net_profit = -500.0
    rd_spending = firm.apply_rd_and_quality_update(10_000.0)
    assert rd_spending == pytest.approx(0.0)


def test_contract_forced_growth_bias_requires_healthy_margin_and_cash(monkeypatch):
    firm = _make_firm(1, cash_balance=20_000.0, wage_offer=100.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.last_revenue = 10_000.0
    firm.last_profit = 600.0

    monkeypatch.setattr(FirmAgent, "_workers_for_sales", lambda self, units: len(self.employees))
    monkeypatch.setattr(
        FirmAgent,
        "_profit_optimal_workers",
        lambda self, current_workers, expected_sales, wage_cost: len(self.employees),
    )

    plan = firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert plan["planned_hires_count"] == 1

    firm.last_profit = 300.0
    plan = firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert plan["planned_hires_count"] == 0

    firm.last_profit = 600.0
    firm.cash_balance = 8_000.0
    plan = firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert plan["planned_hires_count"] == 0


def test_contract_revenue_ema_smooths_single_tick_revenue_shocks():
    firm = _make_firm(1, cash_balance=20_000.0)
    firm.last_tick_total_costs = 0.0

    firm.apply_sales_and_profit({"units_sold": 0.0, "revenue": 1_000.0, "profit_taxes_paid": 0.0})
    assert firm.expected_revenue_ema == pytest.approx(1_000.0)

    firm.last_tick_total_costs = 0.0
    firm.apply_sales_and_profit({"units_sold": 0.0, "revenue": 200.0, "profit_taxes_paid": 0.0})
    assert firm.expected_revenue_ema == pytest.approx(680.0)

    firm.last_tick_total_costs = 0.0
    firm.apply_sales_and_profit({"units_sold": 0.0, "revenue": 1_000.0, "profit_taxes_paid": 0.0})
    assert firm.expected_revenue_ema == pytest.approx(808.0)


def test_contract_wealthy_households_can_save_above_fifteen_percent():
    rich = HouseholdAgent(
        household_id=1,
        skills_level=0.5,
        age=30,
        cash_balance=CONFIG.households.high_wealth_reference * 2.0,
    )
    poor = HouseholdAgent(
        household_id=2,
        skills_level=0.5,
        age=30,
        cash_balance=0.0,
    )
    rich.saving_tendency = 1.0
    poor.saving_tendency = 1.0

    assert rich.compute_saving_rate() == pytest.approx(0.40)
    assert poor.compute_saving_rate() == pytest.approx(0.045)
    assert rich.compute_saving_rate() > 0.15


def test_contract_survival_mode_steps_between_caution_and_critical():
    firm = _make_firm(1, cash_balance=5_000.0, wage_offer=100.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.last_revenue = 1_000.0

    firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert firm.survival_severity == "caution"

    firm.cash_balance = 1_500.0
    firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert firm.survival_severity == "critical"

    firm.cash_balance = 5_000.0
    firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert firm.survival_severity == "caution"

    firm.cash_balance = 9_000.0
    firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert firm.survival_severity == "none"


def test_contract_emergency_loans_bridge_firms_before_survival_mode():
    bank = BankAgent(cash_reserves=200_000.0)
    govt = GovernmentAgent(cash_balance=250_000.0)
    firm = _make_firm(1, cash_balance=4_000.0, wage_offer=100.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.trailing_revenue_12t = 5_000.0
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(households=[household], firms=[firm], government=govt, bank=bank)

    economy._offer_emergency_loans(unemployment_rate=1.0)

    assert firm.cash_balance == pytest.approx(6_000.0)
    assert firm.bank_loan_remaining > 0.0 or firm.government_loan_remaining > 0.0
    assert firm.loan_support_ticks > 0

    firm.plan_production_and_labor(last_tick_sales_units=10.0, in_warmup=False)
    assert firm.survival_severity == "none"


def test_contract_quality_bonus_improves_firm_credit_score():
    bank = BankAgent(cash_reserves=100_000.0)
    govt = GovernmentAgent(cash_balance=50_000.0)
    high_quality_firm = _make_firm(1, category="Food", cash_balance=20_000.0)
    low_quality_firm = _make_firm(2, category="Food", cash_balance=20_000.0)
    high_quality_firm.quality_level = 1.0
    low_quality_firm.quality_level = 0.3
    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=500.0)
    economy = Economy(
        households=[household],
        firms=[high_quality_firm, low_quality_firm],
        government=govt,
        bank=bank,
    )

    economy._update_credit_scores()

    assert bank.get_firm_credit_score(high_quality_firm.firm_id) == pytest.approx(0.505)
    assert bank.get_firm_credit_score(low_quality_firm.firm_id) == pytest.approx(0.5)
