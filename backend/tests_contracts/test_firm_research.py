"""Behavioral contracts for the opt-in Food/Services research experiment."""

import copy
import json
import math
import random
from dataclasses import asdict

import numpy as np
import pytest

from config import FirmBehaviorConfig, SimulationConfig, clone_config, use_config
from firm_research import ResearchProject, ResearchState, sample_entry_quality, sample_initial_quality
from tests_contracts.factories import patch_agent_method
from tools.benchmarks.panel_money import total_money_net_of_injections
from tools.runners.run_large_simulation import create_large_economy


@pytest.fixture
def research_config():
    cfg = clone_config()
    cfg.firms.quality_research_model = "project_outcome"
    with use_config(cfg):
        yield cfg


def private_firm(factory, **overrides):
    params = dict(is_baseline=False, quality_level=0.6, cash_balance=1_000_000.0,
                  last_tick_total_costs=100.0, owners=[])
    params.update(overrides)
    return factory.firm(**params)


@pytest.mark.parametrize("variant", ["project_outcome", "project_cost"])
def test_full_installments_improve_quality_only_on_completion(factory, research_config, variant):
    research_config.firms.quality_research_model = variant
    firm = private_firm(factory)
    cash = firm.cash_balance
    assert firm.advance_research(tick=0, operating_cash_generation=10_000.0) > 0
    project = firm.research_state.project
    duration, installment = project.required_ticks, project.installment
    assert duration >= 36
    assert project.funded_ticks == 1
    assert firm.quality_level == 0.6
    expected_gain, failed = project.outcome(seed=firm.research_state.seed, identity=firm.research_state.identity)
    for tick in range(1, duration - 1):
        assert firm.advance_research(tick=tick, operating_cash_generation=10_000.0) == installment
        assert firm.research_state.project is project
        assert firm.quality_level == 0.6
    assert firm.advance_research(tick=duration - 1, operating_cash_generation=10_000.0) == installment
    assert firm.research_state.project is None
    assert firm.research_state.completed == 1
    assert firm.research_state.failed == int(failed)
    assert firm.quality_level == pytest.approx(0.6 + min(expected_gain, 1.0))
    assert firm.accumulated_rd_investment == pytest.approx(duration * installment)
    assert firm.cash_balance == pytest.approx(cash - duration * installment)


def test_pause_resume_retains_terms_and_outcome_across_config_change(factory, research_config):
    firm = private_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=10_000.0)
    state = firm.research_state
    project = state.project
    expected = project.outcome(seed=state.seed, identity=state.identity)
    research_config.firms.quality_research_model = "project_cost"
    snapshot = (project.funded_ticks, project.spent, firm.accumulated_rd_investment, firm.quality_level)
    assert firm.advance_research(tick=1, operating_cash_generation=0.0, available_cash=600.0) == 0
    assert project.status == "paused"
    assert (project.funded_ticks, project.spent, firm.accumulated_rd_investment, firm.quality_level) == snapshot
    assert state.cash_ema < 10_000.0 / 7.0
    for tick in range(2, 41):
        assert firm.advance_research(tick=tick, operating_cash_generation=10_000.0) == 30.0
    assert state.project is None
    assert project.variant == "project_outcome"
    assert project.required_ticks == 40
    assert project.outcome(seed=state.seed, identity=state.identity) == expected
    assert firm.quality_level == pytest.approx(0.6 + min(expected[0], 1.0))


def test_duplicate_and_older_ticks_do_not_spend_or_update_ema(factory, research_config):
    firm = private_firm(factory)
    firm.advance_research(tick=5, operating_cash_generation=10_000.0)
    snapshot = copy.deepcopy(firm.to_dict())
    investment = firm.accumulated_rd_investment
    for tick in (5, 4):
        assert firm.advance_research(tick=tick, operating_cash_generation=-1000.0) == 0
        assert firm.to_dict() == snapshot
        assert firm.accumulated_rd_investment == investment


def test_opening_cash_is_not_earnings_and_zero_sales_decay_the_ema(factory, research_config):
    firm = private_firm(factory)
    assert firm.advance_research(tick=0, operating_cash_generation=0.0) == 0
    assert firm.research_state.project is None
    assert firm.research_state.cash_ema == 0
    firm.advance_research(tick=1, operating_cash_generation=1000.0)
    assert firm.research_state.project.funded_ticks == 1
    for tick in range(2, 30):
        firm.advance_research(tick=tick, operating_cash_generation=0.0)
    assert firm.research_state.project.status == "paused"
    assert firm.research_state.cash_ema < 10.0
    assert firm.quality_level == 0.6


@pytest.mark.parametrize("blocking", ["survival", "arrears", "caller"])
def test_distress_pauses_without_free_progress(factory, research_config, blocking):
    firm = private_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=10_000.0)
    project = firm.research_state.project
    firm.survival_mode = blocking == "survival"
    firm.payment_wage_arrears = 0.01 if blocking == "arrears" else 0.0
    before = (firm.cash_balance, project.spent, project.funded_ticks)
    assert firm.advance_research(tick=1, operating_cash_generation=10_000.0, blocked=blocking == "caller") == 0
    assert project.status == "paused"
    assert (firm.cash_balance, project.spent, project.funded_ticks) == before


def test_reserve_bounds_remaining_dues_and_counts_bank_infrastructure_once(factory, research_config):
    firm = private_firm(factory, cash_balance=669.0, bank_loan_remaining=20.0,
                        bank_loan_payment_per_tick=100.0, government_loan_remaining=19.0,
                        loan_payment_per_tick=100.0, service_infrastructure_loan_payment_per_tick=100.0)
    assert firm.advance_research(tick=0, operating_cash_generation=10_000.0) == 30.0
    assert firm.cash_balance == 639.0
    assert firm.advance_research(tick=1, operating_cash_generation=10_000.0) == 0.0
    assert firm.research_state.project.status == "paused"


@pytest.mark.parametrize("available", [629.0, -100.0])
def test_available_cash_and_reserve_require_a_complete_installment(factory, research_config, available):
    firm = private_firm(factory)
    assert firm.advance_research(tick=0, operating_cash_generation=10_000.0, available_cash=available) == 0
    assert firm.research_state.project is None
    assert firm.accumulated_rd_investment == 0


def test_risk_is_bounded_and_loss_enters_the_ema(factory, research_config):
    low = private_firm(factory, risk_tolerance=-2.0)
    high = private_firm(factory, risk_tolerance=3.0)
    low.risk_tolerance = -2.0
    high.risk_tolerance = 3.0
    assert low.advance_research(tick=0, operating_cash_generation=1000.0) == 0
    assert high.advance_research(tick=0, operating_cash_generation=1000.0) == 30.0
    assert high.advance_research(tick=1, operating_cash_generation=-10_000.0) == 0
    assert high.research_state.cash_ema < 0


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["generation", "available", "costs", "cash", "risk", "debt", "quality"])
def test_nonfinite_inputs_leave_every_research_write_unchanged(factory, research_config, active, value, field):
    firm = private_firm(factory)
    if active:
        firm.advance_research(tick=0, operating_cash_generation=10_000.0)
    kwargs = dict(tick=1, operating_cash_generation=1000.0)
    if field in {"generation", "available", "costs"}:
        kwargs[{"generation": "operating_cash_generation", "available": "available_cash",
                "costs": "operating_costs"}[field]] = value
    else:
        setattr(firm, {"cash": "cash_balance", "risk": "risk_tolerance", "debt": "bank_loan_remaining",
                       "quality": "quality_level"}[field], value)
    state = copy.deepcopy(firm.research_state)
    cash, quality, invested = firm.cash_balance, firm.quality_level, firm.accumulated_rd_investment
    with pytest.raises(ValueError):
        firm.advance_research(**kwargs)
    assert firm.research_state == state
    assert firm.cash_balance is cash
    assert firm.quality_level is quality
    assert firm.accumulated_rd_investment is invested


@pytest.mark.parametrize("category,baseline,model", [
    ("Food", True, "project_outcome"), ("Services", True, "project_cost"),
    ("Housing", False, "project_outcome"), ("Healthcare", False, "project_outcome"),
    ("PublicWorks", False, "project_outcome"), ("Food", False, "scale_only"),
    ("Services", False, "instant"),
])
def test_excluded_firms_do_no_project_work(factory, research_config, category, baseline, model):
    research_config.firms.quality_research_model = model
    firm = private_firm(factory, category=category, is_baseline=baseline, quality_decay_rate=0.2)
    quality = firm.quality_level
    assert firm.advance_research(tick=0, operating_cash_generation=10_000.0) == 0
    assert firm.research_state is None
    assert firm.quality_level == quality


@pytest.mark.parametrize("category", ["Food", "Services"])
def test_baseline_pin_and_instant_skip_are_limited_to_new_sector_models(factory, research_config, category):
    baseline = private_firm(factory, category=category, is_baseline=True)
    assert baseline.quality_level == 0.1
    assert baseline.apply_rd_and_quality_update(1000.0) == 0
    assert baseline.quality_level == 0.1
    housing = private_firm(factory, category="Housing", is_baseline=True, net_profit=100.0)
    assert housing.quality_level == 0.6
    assert housing.apply_rd_and_quality_update(1000.0) > 0


def test_config_keeps_instant_default_and_rejects_unknown_models():
    assert SimulationConfig().firms.quality_research_model == "instant"
    with pytest.raises(ValueError, match="quality research model"):
        SimulationConfig(firms=FirmBehaviorConfig(quality_research_model="unknown"))


@pytest.mark.parametrize("variant", ["project_outcome", "project_cost"])
def test_outcomes_shrink_across_the_scale_and_include_failures(variant):
    means = []
    for quality in (0.1, 1.0, 5.0, 7.0, 8.0, 9.0, 9.5, 9.99):
        outcomes = [ResearchProject.quote(variant, quality, 0, sequence).outcome(seed=42, identity="probe")
                    for sequence in range(10_000)]
        assert any(failed for _, failed in outcomes)
        assert all(gain == 0.0 for gain, failed in outcomes if failed)
        means.append(sum(gain for gain, _ in outcomes) / len(outcomes))
    assert all(a > b for a, b in zip(means, means[1:]))


@pytest.mark.parametrize("variant", ["project_outcome", "project_cost"])
@pytest.mark.parametrize("start", [0.11, 1.11, 4.99, 9.99])
def test_adversarial_maximum_paths_keep_annual_cap_bounded_state_and_upper_range(
    factory, research_config, monkeypatch, variant, start,
):
    research_config.firms.quality_research_model = variant

    def maximum(project, **_):
        difficulty = 1.0 - project.start_quality / 10.0
        return ((1.05 * difficulty ** 1.5) if project.variant == "project_outcome"
                else 0.625 * difficulty), False

    monkeypatch.setattr(ResearchProject, "outcome", maximum)
    firm = private_firm(factory, quality_level=start, cash_balance=100_000_000.0)
    gains = []
    for tick in range(520):
        firm.advance_research(tick=tick, operating_cash_generation=1_000_000.0)
        state = firm.research_state
        if state.last_gain:
            gains.append((tick, state.last_gain))
        assert len(state.gains) <= 2
        assert sum(gain for at, gain in gains if tick - 52 < at <= tick) <= 1.0 + 1e-12
        assert firm.quality_level <= 10
        if start < 5 and tick < 500:
            assert firm.quality_level < 8


def test_serialized_project_contains_fixed_variant_identity_and_bounded_history(factory, research_config):
    firm = private_firm(factory)
    firm.advance_research(tick=0, operating_cash_generation=10_000.0)
    data = json.loads(json.dumps(firm.to_dict()))["research_state"]
    assert data["identity"] == "initial:1"
    assert data["project"]["variant"] == "project_outcome"
    assert data["project"]["required_ticks"] == 40
    assert data["project"]["installment"] == 30
    assert data["project"]["funded_ticks"] == 1
    assert len(data["gains"]) <= 2
    restored = ResearchState(**{**data, "project": ResearchProject(**data["project"])})
    assert restored.to_dict() == firm.research_state.to_dict()


def test_initial_quality_has_thin_tail_and_no_global_rng_effect():
    random.seed(902)
    before = random.getstate()
    values = [sample_initial_quality(seed=42, identity=f"initial:{i}", founder_skill=0.5) for i in range(10_000)]
    assert random.getstate() == before
    assert all(0.11 <= quality < 4.99 for quality in values)
    assert 60 < sum(quality > 1.11 for quality in values) < 140
    low = [sample_initial_quality(seed=42, identity=str(i), founder_skill=0.1) for i in range(1000)]
    high = [sample_initial_quality(seed=42, identity=str(i), founder_skill=0.9) for i in range(1000)]
    assert sum(high) > sum(low)


def test_entry_uses_private_median_best_peer_ceiling_and_exact_no_peer_fallback():
    draws = [sample_entry_quality(seed=42, identity=str(i), peer_qualities=[6.0, 7.0, 8.0]) for i in range(1000)]
    assert all(6.5 <= quality <= 7.15 for quality in draws)
    assert abs(sum(draws) / len(draws) - 7.0) < 0.1
    singleton = [sample_entry_quality(seed=42, identity=str(i), peer_qualities=[7.0]) for i in range(100)]
    assert all(0.11 <= quality <= 7.0 for quality in singleton)
    assert sample_entry_quality(seed=2, identity="none", peer_qualities=[], founder_skill=0.7) == (
        sample_initial_quality(seed=2, identity="none", founder_skill=0.7))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_factory_preserves_all_nonquality_fields_owners_and_rng(seed):
    snapshots = []
    rng_states = []
    for model in ("instant", "scale_only", "project_outcome", "project_cost"):
        cfg = clone_config()
        cfg.random_seed = seed
        cfg.firms.quality_research_model = model
        random.seed(seed)
        np.random.seed(seed)
        with use_config(cfg):
            economy = create_large_economy(num_households=40, num_firms_per_category=1)
            snapshots.append(([household.to_dict() for household in economy.households],
                              [asdict(firm) for firm in economy.firms + economy.queued_firms]))
            rng_states.append((random.getstate(), np.random.get_state()[1].tolist()))
    assert rng_states.count(rng_states[0]) == 4
    assert snapshots[1] == snapshots[2] == snapshots[3]
    for households, firms in snapshots[1:]:
        assert households == snapshots[0][0]
        for original, changed in zip(snapshots[0][1], firms):
            expected = copy.deepcopy(original)
            if original["good_category"] in {"Food", "Services"}:
                expected["quality_level"] = changed["quality_level"]
                if original["is_baseline"]:
                    assert changed["quality_level"] == 0.1
                else:
                    assert 0.11 <= changed["quality_level"] < 4.99
            assert changed == expected


def research_economy(factory, monkeypatch, *, cash=5000.0, wage=100.0, ceo=True, units=100.0):
    buyer = factory.household(household_id=1, cash_balance=1000.0, goods_inventory={},
                              employer_id=1 if wage else None, wage=wage)
    firm = private_firm(factory, cash_balance=cash, price=10.0, inventory_units=1000.0,
                        employees=[1] if wage else [], actual_wages={1: wage} if wage else {},
                        ceo_household_id=1 if ceo else None)
    firm.research_state = ResearchState(42, "test:1", cash_ema=1000.0)
    gov = factory.government(
        cash_balance=0.0, wage_tax_rate=0.0, profit_tax_rate=0.0,
        unemployment_benefit_level=0.0, transfer_budget=0.0,
        infrastructure_spending=0.0, technology_spending=0.0,
        social_spending=0.0, investment_tax_rate=0.1,
    )
    economy = factory.economy(households=[buyer], firms=[firm], government=gov)
    economy.current_tick = 5
    economy.warmup_ticks = 100
    economy.configure_stabilizers(households=False, firms=False, government=False)
    monkeypatch.setattr(economy, "_run_labor_matching", lambda *_: (
        {1: {"hired_households_ids": [], "confirmed_layoffs_ids": [],
             "actual_wages": {1: wage} if wage else {}}},
        {1: {"employer_id": 1 if wage else None, "wage": wage}},
    ))
    monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *_, **__: {
        1: {"planned_purchases": {1: units}, "budget": units * 10.0}
    })
    monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: None)
    monkeypatch.setattr(economy, "_enqueue_healthcare_requests", lambda: None)
    observed = []
    advance = firm.advance_research

    def observe(**kwargs):
        spending = advance(**kwargs)
        observed.append((kwargs, spending))
        return spending

    patch_agent_method(monkeypatch, firm, "advance_research", observe)
    return economy, firm, buyer, observed


@pytest.mark.parametrize("sequence,old_wages", [
    ("income_first", 0.0), ("income_late", 0.0), ("legacy", 0.0),
    ("income_first", 200.0), ("income_late", 200.0),
])
def test_step_generation_uses_paid_payroll_ceo_tax_and_actual_debt(
    factory, monkeypatch, research_config, sequence, old_wages,
):
    research_config.payment_sequence = sequence
    economy, firm, _, observed = research_economy(factory, monkeypatch)
    if old_wages:
        economy.payment_state["wage_claims"][(1, 1)] = old_wages
    firm.government_loan_remaining = 25.0
    firm.loan_payment_per_tick = 1000.0
    opening_money = total_money_net_of_injections(economy)
    economy.step()
    kwargs, spending = observed[0]
    assert kwargs["operating_cash_generation"] == pytest.approx(575.0 - old_wages)
    assert kwargs["operating_costs"] == 400.0 + old_wages
    assert kwargs["available_cash"] == pytest.approx(5575.0 - old_wages)
    assert not kwargs["blocked"]
    assert spending == 30.0
    assert firm.government_loan_remaining == 0.0
    assert firm.research_state.project.funded_ticks == 1
    assert economy.research_totals["spending"] == 30.0
    assert economy.get_economic_metrics()["firm_research"]["spending_this_tick"] == 30.0
    assert firm.cash_balance == pytest.approx(5545.0 - old_wages)
    misc_rate = random.Random(research_config.random_seed + 5 * 2_038_073 + 2700).uniform(0.0, 0.20)
    assert economy.misc_firm_revenue == pytest.approx(27.0 * (1.0 - misc_rate))
    assert economy.government.cash_balance == pytest.approx(28.0 + 27.0 * misc_rate)
    assert total_money_net_of_injections(economy) == pytest.approx(opening_money, abs=1e-8, rel=0.0)


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_zero_sales_update_ema_and_pause_through_real_step(factory, monkeypatch, research_config, sequence):
    research_config.payment_sequence = sequence
    economy, firm, _, observed = research_economy(factory, monkeypatch, units=0.0, ceo=False)
    firm.advance_research(tick=4, operating_cash_generation=10_000.0)
    firm.research_state.cash_ema = 0.0
    project = firm.research_state.project
    before = (project.funded_ticks, project.spent, firm.quality_level)
    economy.step()
    assert observed[-1][0]["operating_cash_generation"] == -100.0
    assert observed[-1][1] == 0.0
    assert firm.research_state.cash_ema == pytest.approx(-100.0 / 7.0)
    assert project.status == "paused"
    assert (project.funded_ticks, project.spent, firm.quality_level) == before


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_public_installation_cash_cannot_hide_unpaid_direct_due(factory, monkeypatch, research_config, sequence):
    import payment_government

    research_config.payment_sequence = sequence
    research_config.payment_services_project_enabled = True
    economy, firm, _, observed = research_economy(factory, monkeypatch, cash=1000.0, wage=0.0, ceo=False)
    firm.government_loan_remaining = 10_000.0
    firm.loan_payment_per_tick = 5000.0

    def installation(economy):
        firm.cash_balance += 100_000.0
        return 100_000.0

    monkeypatch.setattr(payment_government, "complete_payment_services_project", installation)
    economy.step()
    kwargs, spending = observed[0]
    assert kwargs["operating_cash_generation"] == pytest.approx(-1000.0)
    assert kwargs["available_cash"] == 0.0
    assert kwargs["blocked"]
    assert spending == 0.0
    assert firm.cash_balance == 100_000.0


def test_old_path_clawback_reduces_sales_once_and_is_not_a_debt_payment(factory, monkeypatch, research_config):
    research_config.payment_sequence = "legacy"
    economy, firm, buyer, observed = research_economy(factory, monkeypatch, wage=0.0, ceo=False, units=200.0)
    economy.government.sector_subsidy_target = "food"
    economy.government._sector_subsidy_rate = 0.5
    patch_agent_method(monkeypatch, economy.government, "plan_transfers", lambda *_: {})
    firm.government_loan_remaining = 25.0
    firm.loan_payment_per_tick = 25.0
    economy.step()
    assert buyer.last_food_spend == pytest.approx(1000.0)
    assert firm.last_revenue == pytest.approx(1000.0)
    assert observed[0][0]["operating_cash_generation"] == pytest.approx(975.0)
    assert observed[0][1] == 30.0


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_paid_taxes_and_previous_public_receipts_are_not_retail_earnings(
    factory, monkeypatch, research_config, sequence,
):
    research_config.payment_sequence = sequence
    research_config.government.profit_tax_style = "flat"
    economy, firm, _, observed = research_economy(factory, monkeypatch)
    economy.government.profit_tax_rate = 0.2
    economy.payment_state["services_pending_receipts"] = {1: 10_000.0}
    economy.step()
    assert firm.last_profit_tax_paid == pytest.approx(2120.0)
    assert observed[0][0]["operating_cash_generation"] == pytest.approx(-1520.0)
    assert observed[0][0]["operating_costs"] == 400.0


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
def test_unpaid_wage_claims_block_research_after_sales(factory, monkeypatch, research_config, sequence):
    research_config.payment_sequence = sequence
    economy, firm, _, observed = research_economy(factory, monkeypatch, cash=1000.0, ceo=False)
    economy.payment_state["wage_claims"][(1, 1)] = 20_000.0
    economy.step()
    assert firm.payment_wage_arrears > 0.0
    assert firm.cash_balance == pytest.approx(1000.0)
    assert observed[0][1] == 0.0
    assert firm.research_state.project is None


def test_entry_median_excludes_baselines_and_reused_ids_get_new_identity(factory, research_config):
    research_config.payment_sequence = "income_first"
    buyer = factory.household(household_id=1, cash_balance=100_000.0)
    baseline = private_firm(factory, firm_id=1, category="Services", is_baseline=True)
    incumbent = private_firm(factory, firm_id=2, category="Services", quality_level=7.0)
    economy = factory.economy(households=[buyer], firms=[baseline, incumbent],
                              government=factory.government(cash_balance=0.0))
    economy.in_warmup = False
    economy.target_total_firms = 20
    economy.services_unmet_demand = 100.0
    economy.food_unmet_demand = 0.0
    economy.current_tick = 100
    economy._maybe_create_new_firms()
    first = economy.firms[-1]
    assert first.good_category == "Services"
    assert 6.5 <= first.quality_level <= 7.0
    assert first.research_state.identity == "entry:3:100"
    economy.firms.remove(first)
    economy.firm_lookup.pop(first.firm_id)
    economy.current_tick = 101
    economy._maybe_create_new_firms()
    second = economy.firms[-1]
    assert second.firm_id == first.firm_id
    assert second.research_state.identity == "entry:3:101"
    assert second.research_state.identity != first.research_state.identity
