"""Payment reporting must expose settled outcomes without mutating owners."""

from copy import deepcopy
from types import SimpleNamespace

from payment_reporting import payment_snapshot


def test_payment_snapshot_uses_paid_records_and_live_claims_without_mutation():
    book = SimpleNamespace(
        paid_income={1: {"gross": 80, "net": 70, "tax": 10, "benefit": 3, "ceo": 5}},
        denied_benefits=7,
        unpaid_employed={1: {"shortfall": 2}},
        rent_detail={2: {"current": 9, "arrears": 1, "relief": 2}},
    )
    state = {
        "wage_claims": {(2, 1): 4},
        "restrictions": {"care": 11, "rent": 2},
        "loan_default_history_total": 3,
        "loan_default_history": [{"claim_id": "old"}],
        "loan_credit_cooldown_until": {("household", 1): 15},
        "housing_projects": {2: {"status": "funded"}},
        "services_project": {"status": "authorized"},
        "services_project_payables": {2: 6},
    }
    economy = SimpleNamespace(
        config=None, current_tick=10, payment_sequence="income_first",
        payment_care_mode="covered", payment_assistance="mixed",
        payment_config_snapshot={"payment_annual_quote_shift": 0.01},
        payment_state=state, payment_book=book,
        households=[SimpleNamespace(rent_arrears=3)],
        bank=SimpleNamespace(active_loans=[
            {"contract_version": 2, "principal_remaining": 20, "accrued_interest": 1, "missed_payments": 2},
            {"remaining": 5},
        ]),
        last_housing_diagnostics={"eviction_count": 1},
        payment_care_due_ages={1: 4, 2: 60},
        payment_care_due_age_255_plus=0,
        payment_care_deferrals_this_tick=2,
        payment_care_funding_denials_this_tick=1,
        payment_care_physical_waits_this_tick=3,
        healthcare_completed_visits_this_tick=4,
    )
    before = deepcopy((state, book.__dict__, economy.bank.active_loans))
    result = payment_snapshot(economy)
    assert result["scenario"] == {"timing": "income_first", "care": "covered", "assistance": "mixed"}
    assert result["income"] == {
        "ordinary_gross": 80, "ordinary_net": 70, "ordinary_tax": 10,
        "benefits_paid": 3, "ceo_paid": 5, "benefits_denied": 7,
        "unpaid_employed_count": 1, "unpaid_employed_shortfall": 2,
        "wage_claim_count": 1, "wage_claim_outstanding": 4,
    }
    assert result["rent"]["arrears_outstanding"] == 3
    assert result["rent"]["evictions_this_tick"] == 1
    assert result["care"]["due_age_buckets"] == {"0_3": 0, "4_12": 1, "13_51": 0, "52_plus": 1}
    assert result["fiscal"]["total_restricted_cash"] == 13
    assert result["loans"]["v2_outstanding"] == 21
    assert result["loans"]["v1_outstanding"] == 5
    assert result["loans"]["defaults_total"] == 3
    assert result["loans"]["cooldown_active"] == 1
    assert result["projects"]["housing_active"] == 1
    assert (state, book.__dict__, economy.bank.active_loans) == before
    state["services_project"]["status"] = "completed"
    assert payment_snapshot(economy)["projects"]["services_active"] is False
    state["services_project"]["status"] = "cancelled_unpaid_worker"
    assert payment_snapshot(economy)["projects"]["services_active"] is False


def test_legacy_snapshot_marks_payment_book_coverage():
    economy = SimpleNamespace(payment_sequence="legacy", payment_book=None,
                              payment_state={}, config=None, payment_config_snapshot={})
    assert payment_snapshot(economy)["coverage"] == "legacy_sequence_no_payment_book"
