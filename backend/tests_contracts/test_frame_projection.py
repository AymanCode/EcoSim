from types import SimpleNamespace

from frame_projection import build_curated_metrics, build_firm_list, firm_state, sector_mean_prices


def _firm(firm_id, name, *, cash=100.0, employees=2, hires=0, burn=False, survival=False, baseline=False,
          sector="Food", price=4.5):
    return SimpleNamespace(firm_id=firm_id, good_name=name, good_category=sector, cash_balance=cash,
                           employees=list(range(employees)), planned_hires_count=hires, burn_mode=burn,
                           survival_mode=survival, is_baseline=baseline, price=price, last_revenue=10.0,
                           last_profit=1.0, zero_cash_streak=0)


def _household(hid, *, employer=None, wage=0.0, can_work=True, food_spend=0.0, happiness=0.5):
    return SimpleNamespace(household_id=hid, employer_id=employer, wage=wage, can_work=can_work, last_food_spend=food_spend,
                           happiness=happiness)


def _economy(households, firms, bank=None):
    return SimpleNamespace(households=households, firms=firms, bank=bank,
                           government=SimpleNamespace(cash_balance=-357.5),
                           last_housing_diagnostics={"homeless_household_count": 3.0},
                           last_health_diagnostics={"healthcare_denied_count": 2.0})


def test_firm_state_prefers_struggling_over_growing():
    assert firm_state(_firm(1, "a", hires=2)) == "growing"
    assert firm_state(_firm(1, "a", hires=2, burn=True)) == "struggling"
    assert firm_state(_firm(1, "a", cash=0.0)) == "struggling"
    assert firm_state(_firm(1, "a")) == "steady"


def test_firm_list_is_richest_first_with_expected_keys():
    firms = [_firm(1, "Poor", cash=5.0), _firm(2, "Rich", cash=500.0, baseline=True), _firm(3, "Mid", cash=50.0)]
    rows = build_firm_list(SimpleNamespace(firms=firms))
    assert [r["name"] for r in rows] == ["Rich", "Mid", "Poor"]
    assert set(rows[0]) == {"id", "name", "sector", "cash", "staff", "price", "lastRevenue", "lastProfit", "state", "isBaseline"}
    assert rows[0]["isBaseline"] is True and rows[0]["staff"] == 2


def test_sector_mean_prices_are_per_sector_and_none_when_empty():
    firms = [_firm(1, "a", price=4.0), _firm(2, "b", price=6.0), _firm(3, "c", sector="Housing", price=100.0)]
    prices = sector_mean_prices(SimpleNamespace(firms=firms))
    assert prices == {"Food": 5.0, "Housing": 100.0, "Services": None, "Healthcare": None}


def test_curated_metrics_use_real_values_not_defaults():
    households = [_household(1, employer=1, wage=20.0, food_spend=3.0), _household(2, employer=1, wage=40.0, food_spend=5.0),
                  _household(3, food_spend=0.0), _household(4, can_work=False)]
    firms = [_firm(1, "a", price=4.0, hires=1, employees=2), _firm(2, "b", price=6.0, cash=0.0)]
    bank = SimpleNamespace(active_loans=[1, 2, 3], last_tick_defaults=125.0)
    econ = {"gini_coefficient": 0.41, "wealth_p10": 10.0, "wealth_p50": 50.0, "wealth_p90": 90.0,
            "payment": {"loans": {"defaults_total": 7}}}
    curated = build_curated_metrics(economy=_economy(households, firms, bank), econ_metrics=econ, tick=9, wealth_as_of_tick=5)
    assert curated["householdsTotal"] == 4
    assert abs(curated["peopleOutOfWorkPer100"] - 100.0 / 3.0) < 1e-9  # 1 of 3 who can work
    assert curated["typicalWeeklyPay"] == 30.0  # true median of [20, 40]
    assert curated["foodSpendPerHousehold"] == 2.0
    assert curated["priceFood"] == 5.0 and curated["priceServices"] is None
    assert curated["townHallCash"] == -357.5 and curated["homelessHouseholds"] == 3.0 and curated["careDenials"] == 2.0
    assert (curated["firmsOpen"], curated["firmsGrowing"], curated["firmsStruggling"], curated["firmsSteady"]) == (2, 1, 1, 0)
    assert curated["bankActiveLoans"] == 3 and curated["bankDefaultAmountThisTick"] == 125.0 and curated["bankDefaultsTotal"] == 7
    assert (curated["gini"], curated["wealthP50"], curated["wealthAsOfTick"]) == (0.41, 50.0, 5)


def test_curated_metrics_null_behaviour_without_bank_or_payment_book():
    curated = build_curated_metrics(economy=_economy([_household(1, can_work=False)], []), econ_metrics={}, tick=1, wealth_as_of_tick=1)
    assert curated["peopleOutOfWorkPer100"] == 0.0 and curated["typicalWeeklyPay"] == 0.0
    assert curated["bankActiveLoans"] is None and curated["bankDefaultAmountThisTick"] is None and curated["bankDefaultsTotal"] is None
    assert curated["gini"] is None and curated["priceFood"] is None


def test_care_denials_are_null_only_when_the_health_diagnostics_are_absent():
    economy = _economy([_household(1)], [])
    for absent in (None, {}, {"healthcare_visit_count": 4.0}):
        economy.last_health_diagnostics = absent
        assert build_curated_metrics(economy=economy, econ_metrics={}, tick=1, wealth_as_of_tick=1)["careDenials"] is None
    del economy.last_health_diagnostics
    assert build_curated_metrics(economy=economy, econ_metrics={}, tick=1, wealth_as_of_tick=1)["careDenials"] is None
    economy.last_health_diagnostics = {"healthcare_denied_count": 0.0}
    economy.last_housing_diagnostics = {}
    curated = build_curated_metrics(economy=economy, econ_metrics={}, tick=1, wealth_as_of_tick=1)
    assert curated["careDenials"] == 0.0 and curated["homelessHouseholds"] == 0.0


def test_food_spend_metrics_exist_and_agree_with_household_receipts(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=30, num_firms_per_category=1)
    economy.step()
    econ = economy.get_economic_metrics()
    total = sum(float(getattr(h, "last_food_spend", 0.0)) for h in economy.households)
    assert abs(econ["household_food_spend_total"] - total) < 1e-6
    assert abs(econ["household_food_spend_mean"] - total / len(economy.households)) < 1e-6


NEW_KEYS = ("happiness", "salesExceptRentThisWeek", "townHallIncome", "familySupportPaid", "topTenthShare", "bottomHalfShare")


def test_new_curated_numbers_equal_their_sources():
    households = [_household(1, happiness=0.2), _household(2, happiness=0.5), _household(3, happiness=0.8),
                  _household(4, happiness=0.9)]
    economy = _economy(households, [])
    economy.government.last_tick_revenue = 812.25
    economy.last_tick_revenue = {1: 100.0, 2: 250.5, 3: 0.0}
    economy.last_tick_gov_transfers = 300.0
    economy.last_tick_gov_post_warmup_stimulus = 40.0
    econ = {"top_10_percent_share": 0.42, "bottom_50_percent_share": 0.11}
    curated = build_curated_metrics(economy=economy, econ_metrics=econ, tick=12, wealth_as_of_tick=10)
    assert all(isinstance(curated[key], float) for key in NEW_KEYS)
    assert abs(curated["happiness"] - 60.0) < 1e-9  # mean of 0.2, 0.5, 0.8, 0.9, times 100
    assert curated["salesExceptRentThisWeek"] == 350.5  # sum of every firm's sales this tick (metrics.gdp in dollars)
    assert curated["townHallIncome"] == 812.25
    assert curated["familySupportPaid"] == 340.0  # benefits and top-ups plus the post-warm-up stimulus
    assert abs(curated["topTenthShare"] - 42.0) < 1e-9 and abs(curated["bottomHalfShare"] - 11.0) < 1e-9
    assert curated["wealthAsOfTick"] == 10


def test_wealth_shares_are_null_without_a_count_and_a_counted_zero_stays_zero():
    economy = _economy([_household(1)], [])
    curated = build_curated_metrics(economy=economy, econ_metrics={}, tick=3, wealth_as_of_tick=1)
    assert curated["topTenthShare"] is None and curated["bottomHalfShare"] is None
    econ = {"top_10_percent_share": 0.0, "bottom_50_percent_share": None}
    curated = build_curated_metrics(economy=economy, econ_metrics=econ, tick=3, wealth_as_of_tick=1)
    assert curated["topTenthShare"] == 0.0 and curated["bottomHalfShare"] is None


def test_new_curated_numbers_are_null_when_their_source_is_absent():
    curated = build_curated_metrics(economy=_economy([], []), econ_metrics={}, tick=1, wealth_as_of_tick=1)
    assert all(curated[key] is None for key in NEW_KEYS)
    economy = _economy([_household(1, happiness=0.25)], [])
    economy.last_tick_gov_transfers = 12.0  # an economy without the stimulus field still reports benefits
    curated = build_curated_metrics(economy=economy, econ_metrics={}, tick=1, wealth_as_of_tick=1)
    assert curated["happiness"] == 25.0 and curated["familySupportPaid"] == 12.0


def test_new_curated_numbers_match_a_stepped_economy(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=30, num_firms_per_category=1)
    for _ in range(3):
        economy.step()
    econ = economy.get_economic_metrics()
    curated = build_curated_metrics(economy=economy, econ_metrics=econ, tick=3, wealth_as_of_tick=3)
    assert all(isinstance(curated[key], float) for key in NEW_KEYS)
    mean_happiness = sum(h.happiness for h in economy.households) / len(economy.households)
    assert abs(curated["happiness"] - 100.0 * mean_happiness) < 1e-9
    assert abs(curated["salesExceptRentThisWeek"] - sum(economy.last_tick_revenue.values())) < 1e-9
    assert curated["townHallIncome"] == economy.government.last_tick_revenue
    assert curated["familySupportPaid"] == economy.last_tick_gov_transfers + economy.last_tick_gov_post_warmup_stimulus
    assert abs(curated["topTenthShare"] - 100.0 * econ["top_10_percent_share"]) < 1e-9
    assert abs(curated["bottomHalfShare"] - 100.0 * econ["bottom_50_percent_share"]) < 1e-9
