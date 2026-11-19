"""Funded grocery benefits for the optional income-first scenario."""
from household_liquidity import accessible_liquidity
from utils.category_utils import get_good_category


WEEKLY_GRANT = 2.50


def eligible_count(population):
    return min(population, max(1, population // 5))


def select_recipients(households):
    """The least-liquid fifth at week opening, with stable ties in small towns."""
    ordered = sorted(households, key=lambda h: (
        accessible_liquidity(h.cash_balance, h.bank_deposit), h.household_id,
    ))
    count = eligible_count(len(ordered))
    return [h.household_id for h in ordered[:count]]


def issue(book):
    ids = book.food_credit_recipients
    if not ids:
        return
    economy = book.economy
    issued = min(WEEKLY_GRANT * len(ids), economy.government.food_credit_weekly_budget,
                 economy._payment_free_treasury_cash())
    if issued == 0.0:
        return
    grant = issued / len(ids)
    balances = economy.payment_state.setdefault("food_credit", {})
    book.food_credit_issued = issued
    economy.government.cash_balance -= issued
    for hid in ids:
        balances[hid] = balances.get(hid, 0.0) + grant
        # The public transfer account includes the award. Household cash
        # receipts and wages continue to contain unrestricted payments only.
        book.benefits[hid] = book.benefits.get(hid, 0.0) + grant


def goods_quotes(economy):
    """The same eligible sellers and effective prices used to quote deposit withdrawals."""
    quotes = {}
    for firm in economy.firms:
        category = (firm.good_category or "").lower()
        if category in {"housing", "healthcare"}:
            continue
        supply = economy._estimated_firm_market_supply(firm, current_tick_capacity=True)
        price = max(0.0, float(economy._effective_market_price(firm, supply)))
        quote = (price, category)
        quotes[firm.firm_id] = quote
        if firm.good_name not in quotes or price < quotes[firm.good_name][0]:
            quotes[firm.good_name] = quote
    return quotes


def fund_basket(household, plan, cash_budget, balance, quotes, food_target):
    """Price the preferred basket, charge food to the card, and cap the cash portion.

    When a preferred non-food order exceeds available shopping cash, unused
    credit may instead buy food up to the household's ordinary food target.
    Other obligations already have their own cash reserves before this call.
    """
    food, other = {}, {}
    for target, qty in plan["planned_purchases"].items():
        quote = quotes.get(target)
        if quote is not None and qty > 0:
            orders = food if quote[1] == "food" else other
            orders[target] = qty
    food_cost = sum(qty * quotes[t][0] for t, qty in food.items())
    if food_cost > balance + cash_budget:
        scale = (balance + cash_budget) / food_cost
        food = {target: qty * scale for target, qty in food.items()}
        food_cost = balance + cash_budget
    cash_left = max(0.0, cash_budget - max(0.0, food_cost - balance))
    other_cost = sum(qty * quotes[t][0] for t, qty in other.items())
    displaced = max(0.0, other_cost - cash_left)
    if displaced:
        other = {target: qty * cash_left / other_cost for target, qty in other.items()} if cash_left else {}

    unused = balance - food_cost
    if unused > 0:
        pantry = sum(qty for name, qty in household.goods_inventory.items()
                     if get_good_category(name) == "food" or quotes.get(name, (0, None))[1] == "food")
        planned_units = pantry + sum(food.values())
        known = set(food) | set(household.awareness_pool.get("food", ()))
        offers = [(quotes[target][0], target) for target in known
                  if target in quotes and quotes[target][1] == "food" and quotes[target][0] > 0]
        if offers:
            price, target = min(offers, key=lambda offer: (offer[0], str(offer[1])))
            minimum = max(0.0, household.min_food_per_tick - planned_units) * price
            room = max(0.0, max(food_target, household.min_food_per_tick) - planned_units) * price
            extra = min(unused, room, max(minimum, displaced))
            if extra > 0:
                food[target] = food.get(target, 0.0) + extra / price
                food_cost += extra
    planned_credit = min(balance, food_cost)
    plan.update(planned_purchases={**food, **other}, cash_budget=cash_budget,
                food_credit_planned=planned_credit, budget=cash_budget + planned_credit)
