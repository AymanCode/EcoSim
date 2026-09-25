"""Funded sector settlement for the named PS3 payment scenarios.

This module owns physical delivery and tenancy/visit state.  PaymentBook owns
cash and seller payables, and is deliberately never asked to infer supply.
"""

from __future__ import annotations

import math
from collections import defaultdict

from config import CONFIG
from utils.category_utils import get_good_category

EPS = 1e-6


def _category(firm):
    return (firm.good_category or "").lower()


def _spendable(household):
    return max(0.0, float(household.cash_balance))


def _sale_quantity(price, planned, available, cash, share, subsidy):
    """Largest continuous sale that both payers can actually cover."""
    limit = max(0.0, min(float(planned), float(available)))
    if limit <= EPS or price <= EPS:
        return limit
    share = max(0.0, min(1.0, float(share)))
    subsidy = max(0.0, float(subsidy))
    cash = max(0.0, float(cash))
    if share >= 1.0 - EPS:
        return min(limit, (cash + subsidy) / price)
    before_cap = (cash / (price * (1.0 - share)))
    if before_cap * share * price <= subsidy + EPS:
        return min(limit, before_cap)
    return min(limit, (cash + subsidy) / price)


class PaymentGoodsMarket:
    """One immutable plan and price/supply book shared by both goods passes."""

    def __init__(self, economy, plans, firms):
        self.economy = economy
        self.firms = [f for f in firms if _category(f) not in {"housing", "healthcare"}]
        self.by_id = {f.firm_id: f for f in self.firms}
        self.by_good = defaultdict(list)
        self.categories = {f.firm_id: _category(f) for f in self.firms}
        subsidy_target = str(economy.government.sector_subsidy_target or "").lower()
        subsidy_rate = float(economy.government._sector_subsidy_rate or 0.0)
        self.subsidy_shares = {f.firm_id: subsidy_rate if subsidy_target == self.categories[f.firm_id] else 0.0
                               for f in self.firms}
        self.target_cache = {}
        self.remaining = {}
        self.prices = {}
        self.desired = {hid: dict(plan.get("planned_purchases", {})) for hid, plan in plans.items()}
        self.accepted = defaultdict(lambda: defaultdict(float))
        self.purchases = economy.payment_book.purchases
        self.sales = economy.payment_book.receipts
        self.combined_services_units = defaultdict(float)
        self._first_done = False
        self._second_done = False
        for firm in self.firms:
            available = max(0.0, float(economy._estimated_firm_market_supply(firm, current_tick_capacity=True)))
            effective = max(0.0, float(economy._effective_market_price(firm, available)))
            if _category(firm) == "services" and effective > firm.price:
                firm.price = effective
            self.remaining[firm.firm_id] = available
            self.prices[firm.firm_id] = effective
            self.by_good[firm.good_name].append(firm)
        for entries in self.by_good.values():
            entries.sort(key=lambda f: (self.prices[f.firm_id], f.firm_id))

    def _targets(self, target):
        cached = self.target_cache.get(target)
        if cached is not None:
            return cached
        if isinstance(target, int) or getattr(type(target), "__module__", "").startswith("numpy"):
            firm = self.by_id.get(int(target))
            result = (firm,) if firm is not None else ()
        else:
            result = self.by_good.get(target, ())
        self.target_cache[target] = result
        return result

    def _buy(self, household, target, wanted):
        bought = 0.0
        for firm in self._targets(target):
            if bought >= wanted - EPS:
                break
            fid = firm.firm_id
            price = self.prices[fid]
            stock = self.remaining[fid]
            if stock <= EPS:
                continue
            share = self.subsidy_shares[fid]
            free_subsidy = max(0.0, float(getattr(self.economy, "sector_subsidy_remaining_this_tick", 0.0)))
            qty = _sale_quantity(price, wanted - bought, stock, _spendable(household), share, free_subsidy)
            if qty <= EPS:
                continue
            public = min(max(0.0, share) * price * qty, free_subsidy)
            if not self.economy.payment_book.commit_sale(household, firm, qty, price, public_amount=public):
                continue
            self.remaining[fid] -= qty
            if self.categories[fid] != "services":
                firm.inventory_units = max(0.0, firm.inventory_units - qty)
                household.goods_inventory[firm.good_name] = household.goods_inventory.get(firm.good_name, 0.0) + qty
            else:
                household.services_consumed_this_tick += qty
                self.combined_services_units[fid] += qty
            bought += qty
        self.accepted[household.household_id][target] += bought
        return bought

    def first_pass(self):
        if self._first_done:
            raise RuntimeError("Food pass already settled")
        self._first_done = True
        for hid, targets in self.desired.items():
            household = self.economy.household_lookup.get(hid)
            if household is None:
                continue
            need = max(0.0, float(household.min_food_per_tick) - sum(
                qty for good, qty in household.goods_inventory.items()
                if get_good_category(good) == "food" or any(_category(f) == "food" for f in self.by_good.get(good, ()))
            ))
            for target, wanted in targets.items():
                if need <= EPS:
                    break
                candidates = self._targets(target)
                if not candidates or _category(candidates[0]) != "food":
                    continue
                bought = self._buy(household, target, min(max(0.0, wanted), need))
                need -= bought

    def second_pass(self):
        if not self._first_done or self._second_done:
            raise RuntimeError("Goods passes out of order")
        self._second_done = True
        for hid, targets in self.desired.items():
            household = self.economy.household_lookup.get(hid)
            if household is None:
                continue
            for target, wanted in targets.items():
                remainder = max(0.0, float(wanted) - self.accepted[hid][target])
                if remainder > EPS:
                    self._buy(household, target, remainder)

    def finish(self):
        if not self._second_done:
            raise RuntimeError("Goods settlement incomplete")
        for hid, targets in self.desired.items():
            for target, wanted in targets.items():
                unmet = max(0.0, float(wanted) - self.accepted[hid][target])
                if unmet <= EPS:
                    continue
                candidates = self._targets(target)
                if not candidates:
                    continue
                category = _category(candidates[0])
                if category == "food":
                    self.economy.food_unmet_demand += unmet
                elif category == "services":
                    self.economy.services_unmet_demand += unmet
                    if len(candidates) == 1:
                        fid = candidates[0].firm_id
                        self.economy.services_unmet_demand_by_firm[fid] = self.economy.services_unmet_demand_by_firm.get(fid, 0.0) + unmet
                if len(candidates) == 1:
                    self.economy._record_firm_unmet_demand(candidates[0].firm_id, unmet)
        return self.purchases, self.sales


def payment_deposit_quotes(economy, plans, due_by_household):
    """Gross 5b requests; caller performs the only actual bank withdrawal."""
    id_prices = {}
    name_prices = {}
    for firm in economy.firms:
        if _category(firm) in {"housing", "healthcare"}:
            continue
        supply = economy._estimated_firm_market_supply(firm, current_tick_capacity=True)
        price = max(0.0, float(economy._effective_market_price(firm, supply)))
        id_prices[firm.firm_id] = price
        name_prices[firm.good_name] = min(price, name_prices.get(firm.good_name, math.inf))
    care_capacity = {firm.firm_id: _qualified_capacity(economy, firm)
                     for firm in economy.firms if _category(firm) == "healthcare"}
    cheapest_vacancy = min((max(0.0, float(f.price)) for f in economy.firms
                            if _category(f) == "housing" and len(f.current_tenants) < f.max_rental_units), default=0.0)
    quotes = {}
    for household in economy.households:
        hid = household.household_id
        goods = 0.0
        for target, qty in plans.get(hid, {}).get("planned_purchases", {}).items():
            is_id = isinstance(target, int) or getattr(type(target), "__module__", "").startswith("numpy")
            price = id_prices.get(int(target)) if is_id else name_prices.get(target)
            if price is not None:
                goods += max(0.0, float(qty)) * price
        rent = max(0.0, float(household.monthly_rent)) + max(0.0, float(getattr(household, "rent_arrears", 0.0))) if household.renting_from_firm_id is not None else cheapest_vacancy
        care = 0.0
        if household.queued_healthcare_firm_id is not None and getattr(economy, "payment_care_mode", "patient_pay") == "patient_pay":
            firm = economy.firm_lookup.get(household.queued_healthcare_firm_id)
            qualified = care_capacity.get(firm.firm_id, 0.0) if firm is not None else 0.0
            if firm is not None and qualified > EPS and qualified + min(1.0 - EPS, max(0.0, float(firm.healthcare_capacity_carryover))) >= 1.0 - EPS:
                care = max(0.0, float(firm.price))
        due = max(0.0, float(due_by_household.get(hid, 0.0)))
        quotes[hid] = max(0.0, goods + rent + care + due - float(household.cash_balance))
    return quotes


def settle_payment_rent(economy):
    """Collect current rent before old claims; give two later cure opportunities."""
    apply_payment_housing_renewals(economy)
    firms = {f.firm_id: f for f in economy.firms if _category(f) == "housing"}
    initially_housed = [h for h in economy.households if h.renting_from_firm_id is not None]
    evictions = 0
    current_paid = arrears_paid = relief_paid = 0.0
    excluded = set()

    def collect(household, firm, amount, *, old=False):
        nonlocal current_paid, arrears_paid
        paid = min(max(0.0, amount), _spendable(household))
        if paid <= EPS:
            return 0.0
        household.cash_balance -= paid
        household.add_ledger_flow("rent", -paid)
        firm.cash_balance += paid
        economy.payment_book.record_rent(firm, paid, current=0.0 if old else paid, arrears=paid if old else 0.0)
        if old:
            arrears_paid += paid
        else:
            current_paid += paid
        return paid

    for household in sorted(initially_housed, key=lambda h: h.household_id):
        firm = firms.get(household.renting_from_firm_id)
        if firm is None:
            excluded.add(household.household_id)
            household.renting_from_firm_id = None
            household.monthly_rent = 0.0
            household.owns_housing = False
            household.rent_arrears = 0.0
            household.rent_notice_remaining = 0
            evictions += 1
            continue
        old = max(0.0, float(getattr(household, "rent_arrears", 0.0)))
        current = max(0.0, float(household.monthly_rent))
        tenant_current = collect(household, firm, current)
        current_short = max(0.0, current - tenant_current)
        relief_current = relief_old = 0.0
        # Eligibility is frozen before 5b withdrawal by the integration owner.
        pre_policy_liquidity = getattr(household, "payment_pre_policy_liquidity", math.inf)
        if current_short > EPS and pre_policy_liquidity < current:
            envelope = max(0.0, float(getattr(economy, "payment_rent_relief_remaining", 0.0)))
            relief_current = min(current_short, current, envelope)
            relief_old = min(old, max(0.0, current - relief_current), max(0.0, envelope - relief_current))
            relief = relief_current + relief_old
            if relief > EPS and economy._payment_spend_restriction("rent", relief):
                economy.payment_rent_relief_remaining = max(0.0, envelope - relief)
                firm.cash_balance += relief
                economy.payment_book.record_rent(firm, relief, current=relief_current, arrears=relief_old, relief=relief)
                current_paid += relief_current
                arrears_paid += relief_old
                relief_paid += relief
            else:
                relief_current = relief_old = 0.0
        prior_collected = collect(household, firm, old - relief_old, old=True)
        total_arrears = max(0.0, old - relief_old - prior_collected + current_short - relief_current)
        household.rent_arrears = total_arrears
        receivables = getattr(firm, "rent_arrears_receivable_by_tenant", None)
        if receivables is None:
            receivables = {}
            firm.rent_arrears_receivable_by_tenant = receivables
        if total_arrears > EPS:
            receivables[household.household_id] = total_arrears
            notice = int(getattr(household, "rent_notice_remaining", 0))
            if notice == 0:
                household.rent_notice_remaining = 2
            else:
                household.rent_notice_remaining = notice - 1
                if household.rent_notice_remaining <= 0:
                    receivables.pop(household.household_id, None)
                    household.rent_arrears = 0.0
                    household.renting_from_firm_id = None
                    household.monthly_rent = 0.0
                    household.owns_housing = False
                    if household.household_id in firm.current_tenants:
                        firm.current_tenants.remove(household.household_id)
                    excluded.add(household.household_id)
                    evictions += 1
        else:
            receivables.pop(household.household_id, None)
            household.rent_notice_remaining = 0
            household.owns_housing = True

    # Preserve the existing income ordering/gate, but only actual positive cash
    # can pay the first rent. Deposits were already drawn in the common 5b pass.
    homeless = [h for h in economy.households if h.renting_from_firm_id is None and h.household_id not in excluded]
    benefit = economy.government.get_unemployment_benefit_level()
    homeless.sort(key=lambda h: h.wage if h.is_employed else benefit, reverse=True)
    failures = unaffordable = no_supply = 0
    for household in homeless:
        income = household.wage if household.employer_id is not None else benefit
        ceiling = income * CONFIG.labor_market.rent_affordability_share + _spendable(household) * 0.25
        vacant = [f for f in firms.values() if len(f.current_tenants) < f.max_rental_units]
        eligible = [f for f in vacant if f.price <= ceiling + EPS and f.price <= _spendable(household) + EPS]
        if not eligible:
            failures += 1
            if vacant:
                unaffordable += 1
            else:
                no_supply += 1
            continue
        firm = min(eligible, key=lambda f: (f.price, f.firm_id))
        rent = max(0.0, float(firm.price))
        if rent > EPS and collect(household, firm, rent) + EPS < rent:
            failures += 1
            continue
        household.renting_from_firm_id = firm.firm_id
        household.monthly_rent = rent
        household.lease_renewal_tick = economy.current_tick + CONFIG.payment_lease_term_ticks
        household.owns_housing = True
        household.rent_arrears = 0.0
        household.rent_notice_remaining = 0
        firm.current_tenants.append(household.household_id)

    total_units = sum(f.max_rental_units for f in firms.values())
    economy.last_housing_diagnostics = {
        "eviction_count": float(evictions),
        "housing_failure_count": float(failures),
        "housing_unaffordable_count": float(unaffordable),
        "housing_no_supply_count": float(no_supply),
        "homeless_household_count": float(sum(h.renting_from_firm_id is None for h in economy.households)),
        "housing_shortage_flag": float(total_units < len(economy.households)),
        "current_rent_paid": current_paid,
        "old_arrears_collected": arrears_paid,
        "relief_payer_share": relief_paid,
        "occupied_units": float(sum(h.renting_from_firm_id is not None for h in economy.households)),
    }
    return economy.last_housing_diagnostics


def apply_payment_housing_renewals(economy):
    """Renew the weekly contract against the prior phase-9 posted ask."""
    firms = {f.firm_id: f for f in economy.firms if _category(f) == "housing"}
    level = str(getattr(economy.government, "rent_stabilization_level", "off") or "off").lower()
    cap = {"soft": 1.0 + CONFIG.payment_renewal_soft_cap,
           "strict": 1.0 + CONFIG.payment_renewal_strict_cap}.get(level, math.inf)
    for household in economy.households:
        if household.renting_from_firm_id not in firms:
            continue
        renewal = int(getattr(household, "lease_renewal_tick", -1))
        if renewal < 0:
            # Existing tenancy at intervention starts a full assumed term.
            household.lease_renewal_tick = economy.current_tick + CONFIG.payment_lease_term_ticks
            continue
        if economy.current_tick < renewal:
            continue
        old = max(0.0, float(household.monthly_rent))
        ask = max(0.0, float(firms[household.renting_from_firm_id].price))
        if level == "monitor" and hasattr(economy, "payment_rent_monitor_counterfactual"):
            economy.payment_rent_monitor_counterfactual += max(0.0, ask - old * (1.0 + CONFIG.payment_renewal_soft_cap))
        household.monthly_rent = min(ask, old * cap)
        household.lease_renewal_tick = economy.current_tick + CONFIG.payment_lease_term_ticks


def update_payment_housing_asks(economy):
    """Sole named-arm Housing ask writer, after phase-9 firm commits."""
    firms = [f for f in economy.firms if _category(f) == "housing"]
    lm = CONFIG.labor_market
    wage_p25 = economy.cached_wage_percentiles[0]
    floor = max(lm.rent_floor_absolute_min, wage_p25 * lm.rent_affordability_share) if wage_p25 is not None else lm.rent_floor_absolute_min
    shortage = sum(f.max_rental_units for f in firms) < len(economy.households)
    for firm in firms:
        occupancy = len(firm.current_tenants) / max(firm.max_rental_units, 1)
        if occupancy >= lm.occupancy_high_threshold:
            firm.price *= lm.rent_increase_high_occupancy
        elif occupancy >= lm.occupancy_good_threshold:
            firm.price *= lm.rent_increase_good_occupancy
        elif occupancy < lm.occupancy_low_threshold:
            firm.price *= lm.rent_decrease_high_vacancy
        elif occupancy < lm.occupancy_moderate_threshold:
            firm.price *= lm.rent_decrease_moderate_vacancy
        firm.price = max(floor, firm.price)
        if shortage and occupancy >= lm.occupancy_high_threshold and economy.current_tick % lm.rent_shortage_interval_ticks == 0:
            firm.price *= lm.rent_shortage_multiplier


def _qualified_capacity(economy, firm):
    capacity = 0.0
    for hid in firm.employees:
        worker = economy.household_lookup.get(hid)
        if worker is not None and worker.employer_id == firm.firm_id:
            capacity += max(0.0, float(worker.medical_visit_capacity()))
    return capacity


def enqueue_payment_care_requests(economy):
    """Keep one illness episode while price changes the decision to request."""
    from payment_loans import prepare_household_dues

    firms = economy._healthcare_firms()
    due_by_household = prepare_household_dues(economy)
    economy.payment_care_deferrals_this_tick = 0
    economy.payment_care_funding_denials_this_tick = 0
    economy.payment_care_physical_waits_this_tick = 0
    economy.payment_care_due_ages = {}
    economy.payment_care_due_age_255_plus = 0
    slope = float(CONFIG.payment_care_request_slope)
    tick = int(economy.current_tick)
    for household in economy.households:
        if household.payment_care_due_tick >= 0:
            age = max(0, tick - household.payment_care_due_tick)
            economy.payment_care_due_ages[household.household_id] = min(255, age)
            if age >= 255:
                economy.payment_care_due_age_255_plus += 1
        if household.queued_healthcare_firm_id is not None:
            continue
        if tick < household.next_healthcare_request_tick:
            continue
        if household.pending_healthcare_visits <= 0 and household.payment_care_due_tick < 0:
            missing_pct = max(0.0, min(100.0, (1.0 - household.health) * 100.0))
            base_pct = max(0.0, min(50.0, float(household.healthcare_request_base_chance_pct)))
            chance = (base_pct + missing_pct) / (100.0 * max(1, int(CONFIG.households.healthcare_plan_interval_ticks)))
            if household._deterministic_unit_random(tick, salt=17) >= chance:
                continue
            maximum = max(1, int(CONFIG.households.healthcare_episode_max_visits))
            household.pending_healthcare_visits = max(1, min(maximum, 1 + int(round(missing_pct / 100.0 * (maximum - 1)))))
            household.payment_care_episode_id += 1
            household.payment_care_due_tick = tick
            household.pending_visit_heal_delta = max(0.0, 1.0 - household.health) / household.pending_healthcare_visits
        elif household.payment_care_due_tick < 0 and household.pending_healthcare_visits > 0:
            household.payment_care_due_tick = tick
        if household.payment_care_due_tick < 0:
            continue
        if household.household_id not in economy.payment_care_due_ages:
            economy.payment_care_due_ages[household.household_id] = 0
        provider = economy._choose_healthcare_provider(household, firms)
        if provider is None:
            continue
        rent_due = max(0.0, float(household.monthly_rent)) + max(0.0, float(household.rent_arrears))
        debt_due = max(0.0, float(due_by_household.get(household.household_id, 0.0)))
        liquidity = max(0.0, float(household.cash_balance) + 0.9 * max(0.0, float(household.bank_deposit)) - rent_due - debt_due)
        household.payment_care_planning_liquidity = liquidity
        price = float(provider.price)
        if not math.isfinite(price) or price < 0:
            raise ValueError("Care posted price must be finite and nonnegative")
        charge = 0.0 if economy.payment_care_mode == "covered" else price
        ratio = 0.0 if charge <= EPS else min(1.0, charge / max(liquidity, 1.0))
        probability = max(0.0, min(1.0, 1.0 - slope * ratio))
        critical = household.health <= float(household.healthcare_critical_threshold)
        draw = household._deterministic_unit_random(tick, salt=47 + household.payment_care_episode_id)
        retry = bool(household.payment_care_due_retry)
        unchanged_accepted_quote = retry and math.isfinite(household.payment_care_accepted_quote) and price <= household.payment_care_accepted_quote + EPS
        if not unchanged_accepted_quote and not critical and draw >= probability:
            economy.payment_care_deferrals_this_tick += 1
            continue
        if household.household_id not in provider.healthcare_queue:
            provider.healthcare_queue.append(household.household_id)
        household.queued_healthcare_firm_id = provider.firm_id
        household.healthcare_queue_enter_tick = tick
        household.payment_care_accepted_quote = price
        household.payment_care_due_retry = False
        if not retry:
            provider.healthcare_requests_last_tick += 1.0
            economy.healthcare_requests_this_tick += 1.0
    alpha = max(0.0, min(1.0, CONFIG.firms.healthcare_arrivals_ema_alpha))
    for firm in firms:
        arrivals = max(0.0, firm.healthcare_requests_last_tick)
        firm.healthcare_arrivals_ema = alpha * arrivals + (1.0 - alpha) * max(0.0, firm.healthcare_arrivals_ema)


def settle_payment_care(economy, per_firm_sales):
    """Offer only qualified slots; a denied quote leaves the due episode alive."""
    from payment_loans import fund_medical_loan, quote_medical_loan, rollback_medical_loan

    economy.payment_care_physical_waits_this_tick = getattr(economy, "payment_care_physical_waits_this_tick", 0)
    economy.payment_care_funding_denials_this_tick = getattr(economy, "payment_care_funding_denials_this_tick", 0)
    covered = getattr(economy, "payment_care_mode", "patient_pay") == "covered"
    for firm in economy._healthcare_firms():
        firm.inventory_units = 0.0
        economy._prioritize_healthcare_queue(firm)
        capacity = _qualified_capacity(economy, firm)
        available = capacity + min(1.0 - EPS, max(0.0, float(firm.healthcare_capacity_carryover)))
        slots = int(math.floor(available + 1e-9)) if capacity > EPS else 0
        firm.healthcare_capacity_carryover = max(0.0, available - slots)
        economy.healthcare_attempted_slots_this_tick += capacity
        if slots <= 0 or not firm.healthcare_queue:
            economy.payment_care_physical_waits_this_tick += len(firm.healthcare_queue)
            continue
        queue = list(firm.healthcare_queue)
        if len(queue) > 1:
            lead = economy.household_lookup.get(queue[0])
            priority = lead is not None and lead.medical_training_status == "doctor" and lead.health < CONFIG.households.healthcare_worker_priority_health_threshold
            if not priority:
                offset = (economy.current_tick + firm.firm_id) % len(queue)
                queue = queue[offset:] + queue[:offset]
        remaining = []
        completed = 0
        for hid in queue:
            household = economy.household_lookup.get(hid)
            if household is None or household.queued_healthcare_firm_id != firm.firm_id:
                continue
            if completed >= slots:
                remaining.append(hid)
                economy.payment_care_physical_waits_this_tick += 1
                continue
            price = float(firm.price)
            if not math.isfinite(price) or price < 0:
                raise ValueError("Care quote must be finite and nonnegative")
            consent_quote = float(getattr(household, "payment_care_accepted_quote", math.inf))
            if not math.isfinite(consent_quote) or consent_quote < 0:
                raise ValueError("Due care episode lacks a finite accepted quote")
            if not covered and price > consent_quote + EPS:
                household.queued_healthcare_firm_id = None
                household.healthcare_queue_enter_tick = -1
                household.payment_care_due_retry = True
                household.payment_care_accepted_quote = math.inf  # new decision next eligible tick
                economy.healthcare_affordability_rejects_this_tick += 1
                continue
            public = price if covered else 0.0
            household_payment = 0.0 if covered else min(price, _spendable(household))
            shortfall = max(0.0, price - public - household_payment)
            if covered:
                funding_ok = max(0.0, float(getattr(economy, "payment_care_remaining", 0.0))) + EPS >= price
            else:
                funding_ok = shortfall <= EPS or quote_medical_loan(economy, household, shortfall)
            if not funding_ok:
                household.queued_healthcare_firm_id = None
                household.healthcare_queue_enter_tick = -1
                household.payment_care_due_retry = True
                economy.healthcare_affordability_rejects_this_tick += 1
                economy.payment_care_funding_denials_this_tick += 1
                continue
            bank_amount = fund_medical_loan(economy, household, shortfall) if shortfall > EPS else 0.0
            if shortfall > EPS and bank_amount + EPS < shortfall:
                raise RuntimeError("Medical quote funded less than its accepted visit")
            if not economy.payment_book.commit_sale(household, firm, 1.0, price,
                    kind="care", public_amount=public, bank_amount=bank_amount):
                if bank_amount > EPS:
                    rollback_medical_loan(economy, household)
                household.queued_healthcare_firm_id = None
                household.healthcare_queue_enter_tick = -1
                household.payment_care_due_retry = True
                continue
            if household_payment > EPS:
                household.add_ledger_flow("healthcare", -household_payment)
            if covered:
                economy.payment_care_remaining = max(0.0, economy.payment_care_remaining - public)
            health_before = float(household.health)
            heal = household.pending_visit_heal_delta
            if heal <= 0:
                heal = CONFIG.households.healthcare_visit_base_heal * (1.0 - household.health)
            household.pending_visit_heal_delta = 0.0
            household.health = min(1.0, household.health + max(0.0, heal))
            household.healthcare_consumed_this_tick += 1.0
            household.last_healthcare_units += 1.0
            household.last_healthcare_spend += household_payment
            household.last_healthcare_provider_id = firm.firm_id
            household.last_checkup_tick = economy.current_tick
            household.pending_healthcare_visits = max(0, household.pending_healthcare_visits - 1)
            household.payment_care_due_tick = -1
            if household.pending_healthcare_visits > 0:
                gap_max = max(1, int(CONFIG.households.healthcare_followup_gap_max_ticks))
                gap = 1 + int(household.health * max(0, gap_max - 1))
                household.next_healthcare_request_tick = economy.current_tick + gap
            else:
                household.next_healthcare_request_tick = economy.current_tick + 1
            household.queued_healthcare_firm_id = None
            household.healthcare_queue_enter_tick = -1
            household.payment_care_due_retry = False
            firm.healthcare_completed_visits_last_tick += 1.0
            economy.healthcare_completed_visits_this_tick += 1.0
            if per_firm_sales is not economy.payment_book.receipts:
                row = per_firm_sales.setdefault(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
                row["units_sold"] += 1.0
                row["revenue"] += price
            economy.last_healthcare_events.append({
                "tick": int(economy.current_tick + 1), "household_id": int(hid),
                "firm_id": int(firm.firm_id), "event_type": "visit_completed",
                "visit_price": price, "household_cost": household_payment,
                "government_cost": public, "health_before": health_before,
                "health_after": float(household.health),
            })
            completed += 1
        firm.healthcare_queue = remaining
        if completed:
            firm.healthcare_idle_streak = 0


def requeue_payment_care_due(economy):
    """Retry an unchanged accepted quote; a changed quote needs fresh consent."""
    firms = economy._healthcare_firms()
    for household in economy.households:
        if not getattr(household, "payment_care_due_retry", False):
            continue
        if household.queued_healthcare_firm_id is not None:
            continue
        firm = economy._choose_healthcare_provider(household, firms) if firms else None
        if firm is None:
            continue
        price = float(firm.price)
        if not math.isfinite(price) or price < 0:
            raise ValueError("Care posted price must be finite and nonnegative")
        quote = float(household.payment_care_accepted_quote)
        if not math.isfinite(quote) or quote < 0 or price > quote + EPS:
            continue
        if household.household_id not in firm.healthcare_queue:
            firm.healthcare_queue.append(household.household_id)
        household.queued_healthcare_firm_id = firm.firm_id
        household.healthcare_queue_enter_tick = economy.current_tick
        household.payment_care_due_retry = False
