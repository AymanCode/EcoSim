from economy import Economy


def test_contract_factory_can_handcraft_entities(factory):
    """Factory contract: handcrafted households/firms/government compose into an economy."""
    government = factory.government(cash_balance=12_000.0, unemployment_benefit_level=0.0, transfer_budget=0.0)
    households = [
        factory.household(household_id=1, health=0.4, cash_balance=800.0),
        factory.household(household_id=2, health=0.9, cash_balance=1_200.0),
    ]
    firms = [
        factory.firm(firm_id=1, category="Food", price=8.0),
        factory.firm(firm_id=2, category="Services", price=12.0, happiness_boost_per_unit=0.02),
    ]

    economy = factory.economy(
        households=households,
        firms=firms,
        government=government,
        disable_shocks=True,
    )

    assert isinstance(economy, Economy)
    assert len(economy.households) == 2
    assert len(economy.firms) == 2
    assert economy.government.cash_balance == 12_000.0
    assert economy.firms[1].good_category == "Services"


def test_contract_factory_can_generate_defaults(economy_factory):
    """Factory contract: helper can generate a deterministic tiny economy with one call."""
    economy = economy_factory(
        num_households=8,
        categories=("Food", "Services"),
        num_firms_per_category=2,
        baseline_firms=False,
        disable_shocks=True,
    )

    assert len(economy.households) == 8
    assert len(economy.firms) == 4
    categories = {firm.good_category for firm in economy.firms}
    assert categories == {"Food", "Services"}


def test_contract_factory_batch_builders_support_overrides(factory):
    """Factory contract: batch builders produce expected counts with shared overrides."""
    households = factory.households(5, household_overrides={"health": 0.75})
    firms = factory.firms(
        categories=("Healthcare",),
        num_per_category=2,
        is_baseline=False,
        firm_overrides={"price": 20.0},
    )

    assert len(households) == 5
    assert all(h.health == 0.75 for h in households)
    assert len(firms) == 2
    assert all(f.good_category == "Healthcare" for f in firms)
    assert all(f.price == 20.0 for f in firms)
