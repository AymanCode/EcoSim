"""Exercise household budgeting and settlement with a restricted grocery card."""
from types import SimpleNamespace

import pytest

from config import clone_config, use_config
from food_credit import select_recipients
from payment_loans import collect_household_dues
from payment_reporting import payment_snapshot
from payment_sectors import PaymentGoodsMarket, payment_deposit_quotes, settle_payment_care, settle_payment_rent
from payments import PaymentBook
from server import SetupConfig
from sim_setup import build_economy_from_setup


@pytest.fixture
def town(monkeypatch):
    setup = SetupConfig(num_households=3, seed=43, payment_sequence="income_first",
                        payment_food_credit_enabled=True, enable_llm_government=False)
    with use_config(clone_config()):
        e, _ = build_economy_from_setup(setup, 43)
        h = e.households[0]
        hid = h.household_id
        e.households, e.household_lookup = [h], {hid: h}
        firms = {f.good_category.lower(): f for f in e.firms}
        food, service = firms["food"], firms["services"]
        h.cash_balance = h.bank_deposit = h.wage = h.last_transfer_income = h.last_dividend_income = 0.0
        h.employer_id = h.queued_healthcare_firm_id = h.renting_from_firm_id = None
        h.category_weights = {"food": 0.5, "services": 0.5}
        h.food_preference = h.services_preference = h.spending_tendency = h.frugality = 1.0
        h.min_food_per_tick = 1.0
        h.food_consumed_last_tick = e.config.households.food_health_high_threshold
        h.goods_inventory = {}
        h.last_pool_refresh_tick = e.current_tick
        h.awareness_pool = {"food": [food.firm_id], "services": [service.firm_id]}
        for f in e.firms:
            f.price = 1.0
        monkeypatch.setattr(e, "_estimated_firm_market_supply", lambda f, **kwargs: f.inventory_units)
        monkeypatch.setattr(e, "_effective_market_price", lambda f, available: f.price)
        food.inventory_units = service.inventory_units = 10.0
        book = e.payment_book = PaymentBook(e)
        book.income_settled = book.benefits_settled = True
        book.loan_state = {"household_due_tick": e.current_tick, "household_due_totals": {}}
        snap = {k: [{"firm_id": f.firm_id, "price": f.price, "quality": 1.0}]
                for k, f in (("food", food), ("services", service))}

        def plan():
            return e._batch_plan_consumption({}, snap, settled_income=True)[hid]

        yield SimpleNamespace(e=e, h=h, firms=firms, hid=hid, food=food, service=service, plan=plan)


def test_card_alone_changes_only_grocery_orders_and_carries_after_stockout(town):
    t = town
    assert t.plan()["budget"] == 0
    balances = t.e.payment_state["food_credit"] = {t.hid: 2.5}
    first = t.plan()
    orders = first["planned_purchases"]
    assert first["cash_budget"] == 0
    assert orders[t.food.firm_id] == pytest.approx(2.5)
    assert orders.get(t.service.firm_id, 0) == 0
    assert t.e.payment_book.obligation_pressure[t.hid]["estimated_savings_liquidity"] == 0
    t.food.inventory_units = 0
    market = PaymentGoodsMarket(t.e, {t.hid: first}, [t.food, t.service])
    market.first_pass()
    market.second_pass()
    market.finish()
    assert balances[t.hid] == 2.5
    assert t.e.payment_book.food_credit_redeemed == t.h.cash_balance == t.h.bank_deposit == 0

    t.e.current_tick += 1
    book = t.e.payment_book = PaymentBook(t.e)
    book.income_settled = book.benefits_settled = True
    book.loan_state = {"household_due_tick": t.e.current_tick, "household_due_totals": {}}
    t.food.inventory_units = 10.0
    carried = t.plan()
    assert carried["planned_purchases"] == pytest.approx(orders)
    assert book.obligation_pressure[t.hid]["estimated_savings_liquidity"] == 0
    market = PaymentGoodsMarket(t.e, {t.hid: carried}, [t.food, t.service])
    market.first_pass()
    market.second_pass()
    market.finish()
    assert book.release_firm_receipts(t.food) == pytest.approx(2.5)
    assert t.h.goods_inventory[t.food.good_name] == pytest.approx(2.5)
    assert book.receipts.get(t.service.firm_id, {}).get("revenue", 0) == 0
    assert payment_snapshot(t.e)["fiscal"]["food_credit"] == pytest.approx(
        {"issued": 0, "redeemed": 2.5, "outstanding": 0})
    assert t.h.cash_balance == t.h.bank_deposit == 0


def test_groceries_release_real_cash_for_service_and_withdraw_only_the_cash_portion(town):
    t = town
    book = t.e.payment_book
    t.h.cash_balance = book.paid_income[t.hid]["benefit"] = 3
    without = t.plan()["planned_purchases"][t.service.firm_id]
    balances = t.e.payment_state["food_credit"] = {t.hid: 2.5}
    plan = t.plan()
    orders = plan["planned_purchases"]
    assert without < orders[t.service.firm_id] <= plan["cash_budget"]
    assert sum(orders.values()) - plan["food_credit_planned"] <= plan["cash_budget"] + 1e-8
    t.h.renting_from_firm_id = t.firms["housing"].firm_id
    t.h.monthly_rent, t.h.rent_arrears = 1.0, 0.0
    quoted = {t.hid: {"planned_purchases": {t.food.firm_id: 4, t.service.firm_id: 3}}}
    # $7 goods + $1 rent + $1 debt, less $2.50 grocery credit and $3 in hand.
    assert payment_deposit_quotes(t.e, quoted, {t.hid: 1})[t.hid] == pytest.approx(3.5)
    assert book.commit_sale(t.h, t.food, 4, 1)
    assert book.household_purchase_cost[t.hid][t.food.good_name] == 1.5
    assert book.release_firm_receipts(t.food) == 4
    assert book.commit_sale(t.h, t.service, 1.5, 1)
    assert book.release_firm_receipts(t.service) == 1.5
    assert t.h.cash_balance == balances.get(t.hid, 0) == 0


def test_card_cannot_pay_bills_or_create_a_cash_reserve_for_care(town, monkeypatch):
    t = town
    e, h, hid = t.e, t.h, t.hid
    balances = e.payment_state["food_credit"] = {hid: 2.5}
    book = e.payment_book
    housing, clinic = t.firms["housing"], t.firms["healthcare"]
    h.renting_from_firm_id, h.monthly_rent, h.rent_arrears = housing.firm_id, 1.0, 0
    h.lease_renewal_tick, h.rent_notice_remaining = 1000, 0
    h.payment_care_accepted_quote = 1.0
    h.queued_healthcare_firm_id = clinic.firm_id
    clinic.healthcare_queue = [hid]
    plan = t.plan()
    pressure = book.obligation_pressure[hid]
    assert pressure["nominal_access"] == pressure["healthcare_reserve"] == plan["cash_budget"] == 0
    assert not book.commit_sale(h, t.service, 1, 1)
    assert not book.commit_sale(h, t.food, 3, 1)
    # Another household's card cannot fund this order either.
    balances[hid + 1] = 100
    assert not book.commit_sale(h, t.food, 3, 1)
    settle_payment_rent(e)
    assert h.rent_arrears == 1
    loan = dict(loan_id=1, borrower_type="household", borrower_id=hid, subtype="consumption",
                remaining=2.0, payment_per_tick=1.0, term_remaining=2, missed_payments=0)
    e.bank.active_loans.append(loan)
    book.loan_state["household_due_index"] = {hid: [(1, loan, 1.0)]}
    assert collect_household_dues(e) == 0
    assert loan["remaining"] == 2 and loan["missed_payments"] == 1
    monkeypatch.setattr(e, "bank", None)
    monkeypatch.setattr("payment_sectors._qualified_capacity", lambda *args: 1.0)
    denials = getattr(e, "payment_care_funding_denials_this_tick", 0)
    settle_payment_care(e, book.receipts)
    assert e.payment_care_funding_denials_this_tick == denials + 1
    assert balances == {hid: 2.5, hid + 1: 100}
    assert book.food_credit_redeemed == 0


def test_eligibility_and_prorated_treasury_transfer(town):
    people = [SimpleNamespace(household_id=i, cash_balance=i, bank_deposit=0) for i in range(10)]
    people[0].bank_deposit = 20
    assert select_recipients(people) == [1, 2]
    e = town.e
    book = e.payment_book = PaymentBook(e)
    book.food_credit_recipients = [town.hid, town.hid + 1]
    e.government.cash_balance = 2
    e.payment_state["restrictions"]["G"] = 1
    e.payment_state["food_credit"] = {town.hid: 0.75}
    book.settle_benefits()
    book.settle_benefits()
    assert e.government.cash_balance == 1
    assert e.payment_state["food_credit"] == {town.hid: 1.25, town.hid + 1: 0.5}
    assert town.h.cash_balance == town.h.last_transfer_income == 0
    assert book.food_credit_issued == 1 and book.food_credit_redeemed == 0


def test_setup_rejects_unsupported_timing():
    with pytest.raises(ValueError, match="requires income_first"):
        SetupConfig(payment_sequence="income_late", payment_food_credit_enabled=True)


def test_public_food_subsidy_and_credit_each_pay_only_their_own_share(town):
    t = town
    book = t.e.payment_book
    balances = t.e.payment_state["food_credit"] = {t.hid: 2.5}
    t.h.cash_balance = 1.0
    t.e.payment_state["restrictions"]["G"] = 1.0
    assert not book.commit_sale(t.h, t.food, 4.5, 1, public_amount=1.5)
    assert balances[t.hid] == 2.5 and t.h.cash_balance == 1
    assert book.commit_sale(t.h, t.food, 4.5, 1, public_amount=1.0)
    assert t.e.payment_state["restrictions"]["G"] == t.h.cash_balance == 0
    assert book.food_credit_redeemed == book.food_credit_spent_by_household[t.hid] == 2.5
    assert book.household_purchase_cost[t.hid][t.food.good_name] == 1
    assert book.release_firm_receipts(t.food) == 4.5
