"""Funded payment records for the income-first and income-late scenarios.

The book owns cash in clearing and paid income.  Housing owns direct rent cash,
and market adapters own physical supply; neither is a second cash release.
"""

from collections import defaultdict
from math import isfinite

MONEY_EPS = 1e-6


def _amount(value):
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError("payment amount must be finite and nonnegative")
    return number


def proportional(due, available):
    """Stable bounded allocation of one funded pool across named claims."""
    ordered = sorted((key, _amount(value)) for key, value in due.items() if value > MONEY_EPS)
    total = sum(value for _, value in ordered)
    available = min(_amount(available), total)
    if total <= MONEY_EPS or available <= MONEY_EPS:
        return {key: 0.0 for key, _ in ordered}
    allocated = {}
    left = available
    for index, (key, value) in enumerate(ordered):
        paid = min(value, max(0.0, left),
                   max(0.0, available * value / total) if index != len(ordered) - 1 else value)
        allocated[key] = paid
        left = max(0.0, left - paid)
    return allocated


class PaymentBook:
    def __init__(self, economy, timing="income_first"):
        self.economy = economy
        self.timing = timing
        self.receipts = defaultdict(lambda: {"units_sold": 0.0, "revenue": 0.0})
        self.purchases = defaultdict(dict)
        self.household_purchase_cost = defaultdict(lambda: defaultdict(float))
        self.clearing_payables = defaultdict(float)
        self.clearing_cash = 0.0
        self.rent_receipts = defaultdict(float)
        self.rent_detail = defaultdict(lambda: {"current": 0.0, "arrears": 0.0, "relief": 0.0})
        self.paid_income = defaultdict(lambda: {"gross": 0.0, "net": 0.0, "tax": 0.0, "benefit": 0.0, "ceo": 0.0})
        self.late_income = defaultdict(float)
        self.wage_taxes = {}
        self.benefits = {}
        self.denied_benefits = 0.0
        self.current_due = {}
        self.current_paid_by_firm_worker = {}
        self.funded_ceo = defaultdict(float)
        self.funded_wages_by_firm = defaultdict(float)
        self.unpaid_employed = {}
        self.medical_funding_pending = defaultdict(float)
        self.household_due_index = {}

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def settle_income(self, frozen_wages):
        """Reserve employer-funded gross in two passes, then post one population tax."""
        economy = self.economy
        state = economy.payment_state
        due_by_firm = defaultdict(dict)
        current_due_by_worker = defaultdict(float)
        for firm in economy.firms:
            for worker_id in firm.employees:
                amount = _amount(frozen_wages.get(worker_id, 0.0))
                if amount > MONEY_EPS:
                    due_by_firm[firm.firm_id][worker_id] = amount
                    current_due_by_worker[worker_id] += amount
        self.current_due = {fid: dict(due) for fid, due in due_by_firm.items()}
        payments = defaultdict(float)
        old_claims = state["wage_claims"]
        old_by_firm = defaultdict(dict)
        for (fid, hid), amount in old_claims.items():
            old_by_firm[fid][hid] = _amount(amount)
        current_payments = defaultdict(float)
        current_paid_records = {}
        firm_payment_totals = {}
        claim_updates = {}
        funded_ceo = {}
        arrears_by_worker = defaultdict(float)
        for firm in economy.firms:
            fid = firm.firm_id
            available = max(0.0, firm.cash_balance)
            current = proportional(due_by_firm.get(fid, {}), available)
            current_total = sum(current.values())
            available = max(0.0, available - current_total)
            for hid, due in due_by_firm.get(fid, {}).items():
                paid = current.get(hid, 0.0)
                payments[hid] += paid
                current_payments[hid] += paid
                current_paid_records[(fid, hid)] = paid
                unpaid = due - paid
                if unpaid > MONEY_EPS:
                    claim_updates[(fid, hid)] = old_by_firm[fid].get(hid, 0.0) + unpaid
                    arrears_by_worker[hid] += unpaid
            old = old_by_firm.get(fid, {})
            arrears_paid = proportional(old, available)
            old_total = sum(arrears_paid.values())
            available = max(0.0, available - old_total)
            for hid, paid in arrears_paid.items():
                payments[hid] += paid
                remaining = old[hid] - paid + max(0.0, due_by_firm.get(fid, {}).get(hid, 0.0) - current.get(hid, 0.0))
                claim_updates[(fid, hid)] = remaining
                arrears_by_worker[hid] += old[hid] - paid
            firm_payment_totals[fid] = current_total + old_total
            self.funded_wages_by_firm[fid] = current_total + old_total
            if firm.ceo_household_id is not None and firm.employees and available > MONEY_EPS:
                import numpy as np
                median = float(np.median([firm.actual_wages.get(hid, firm.wage_offer) for hid in firm.employees]))
                funded = min(available, 3.0 * median)
                if funded > MONEY_EPS:
                    firm_payment_totals[fid] += funded
                    funded_ceo[fid] = (firm.ceo_household_id, funded)
        # A firm's exit transferred gross to a protected hold in the previous tick.
        for hid, gross in state["recovery_holds"].items():
            payments[hid] += gross
        snapshots = [{"household_id": hh.household_id, "wage_income": payments[hh.household_id]} for hh in economy.households]
        tax_plan = economy.government.plan_taxes(snapshots, [])
        taxes = tax_plan["wage_taxes"]
        for hh in economy.households:
            gross, tax = payments[hh.household_id], _amount(taxes.get(hh.household_id, 0.0))
            if tax > gross + MONEY_EPS:
                raise ValueError("wage withholding exceeds actual funded gross")
        # No payer or claim mutates until every household's withholding is valid.
        for firm in economy.firms:
            firm.cash_balance -= firm_payment_totals.get(firm.firm_id, 0.0)
        self.current_paid_by_firm_worker = dict(current_paid_records)
        for key, remaining in claim_updates.items():
            if remaining <= MONEY_EPS:
                old_claims.pop(key, None)
            else:
                old_claims[key] = remaining
        arrears_by_firm = defaultdict(float)
        for (fid, _), remaining in old_claims.items():
            arrears_by_firm[fid] += remaining
        for firm in economy.firms:
            firm.payment_wage_arrears = arrears_by_firm[firm.firm_id]
        state["recovery_holds"].clear()
        for fid, (hid, funded) in funded_ceo.items():
            self.funded_ceo[fid] = funded
            state["ceo_holds"][hid] = state["ceo_holds"].get(hid, 0.0) + funded
        for hh in economy.households:
            hid = hh.household_id
            gross, tax = payments[hid], _amount(taxes.get(hid, 0.0))
            net = max(0.0, gross - tax)
            self.paid_income[hid]["gross"] = gross
            self.paid_income[hid]["net"] = net
            self.paid_income[hid]["tax"] = tax
            if self.timing == "income_first":
                hh.cash_balance += net
            else:
                self.late_income[hid] += net
            hh.add_ledger_flow("wage", gross)
            hh.add_ledger_flow("taxes", -tax)
            hh.last_wage_income = gross
            hh.last_other_income = -tax
            self.wage_taxes[hid] = tax
            shortfall = max(0.0, current_due_by_worker[hid] - current_payments[hid])
            if hh.employer_id is not None and shortfall > MONEY_EPS:
                streak = state["unpaid_streaks"].get(hid, 0) + 1
                state["unpaid_streaks"][hid] = streak
                self.unpaid_employed[hid] = {"shortfall": shortfall, "claim": arrears_by_worker[hid], "duration": streak}
            else:
                state["unpaid_streaks"].pop(hid, None)
        withholding = sum(self.wage_taxes.values())
        economy.government.cash_balance += withholding
        state["restrictions"]["withholding"] += withholding

    def settle_benefits(self):
        economy = self.economy
        eligible = {h.household_id: economy.government.get_unemployment_benefit_level() for h in economy.households if h.employer_id is None}
        allocation = proportional(eligible, economy.payment_state["restrictions"]["B"])
        for hid, paid in allocation.items():
            if paid <= 0:
                continue
            economy.payment_state["restrictions"]["B"] -= paid
            economy.government.cash_balance -= paid
            self.benefits[hid] = paid
            self.paid_income[hid]["benefit"] += paid
            hh = economy.household_lookup[hid]
            hh.last_transfer_income = paid
            hh.add_ledger_flow("transfers", paid)
            if self.timing == "income_first":
                hh.cash_balance += paid
            else:
                self.late_income[hid] += paid
        self.denied_benefits = max(0.0, sum(eligible.values()) - sum(allocation.values()))

    def release_late_income(self):
        for hid, amount in self.late_income.items():
            self.economy.household_lookup[hid].cash_balance += amount
        self.late_income.clear()
        for hid, amount in list(self.economy.payment_state["ceo_holds"].items()):
            hh = self.economy.household_lookup.get(hid)
            if hh is not None:
                hh.cash_balance += amount
                hh.last_wage_income += amount
                hh.add_ledger_flow("wage", amount)
                self.paid_income[hid]["ceo"] += amount
            del self.economy.payment_state["ceo_holds"][hid]

    def commit_sale(self, household, firm, qty, price, *, public_amount=0.0, bank_amount=0.0, kind="goods"):
        qty, price = _amount(qty), _amount(price)
        public_amount, bank_amount = _amount(public_amount), _amount(bank_amount)
        total = qty * price
        private = total - public_amount - bank_amount
        if private < -MONEY_EPS or private > max(0.0, household.cash_balance) + MONEY_EPS:
            return False
        restriction = "care" if kind == "care" and public_amount > 0 else "G"
        if public_amount > self.economy.payment_state["restrictions"].get(restriction, 0.0) + MONEY_EPS:
            return False
        if bank_amount > self.medical_funding_pending[household.household_id] + MONEY_EPS:
            return False
        household.cash_balance -= max(0.0, private)
        if bank_amount:
            self.medical_funding_pending[household.household_id] = max(0.0, self.medical_funding_pending[household.household_id] - bank_amount)
        if kind != "care" and private > 0:
            household.add_ledger_flow("goods", -private)
            self.household_purchase_cost[household.household_id][firm.good_name] += private
        if public_amount:
            self.economy._payment_spend_restriction(restriction, public_amount)
        self.clearing_cash += total
        self.clearing_payables[firm.firm_id] += total
        self.receipts[firm.firm_id]["units_sold"] += qty
        self.receipts[firm.firm_id]["revenue"] += total
        if kind != "care":
            before_qty, before_price = self.purchases[household.household_id].get(firm.good_name, (0.0, 0.0))
            merged = before_qty + qty
            if merged:
                self.purchases[household.household_id][firm.good_name] = (merged, (before_qty * before_price + total) / merged)
        return True

    def release_firm_receipts(self, firm):
        amount = self.clearing_payables.pop(firm.firm_id, 0.0)
        if amount > self.clearing_cash + MONEY_EPS:
            raise ValueError("seller payable exceeds clearing cash")
        firm.cash_balance += amount
        self.clearing_cash -= amount
        return amount

    def record_rent(self, firm, amount, current=0.0, arrears=0.0, relief=0.0):
        amount = _amount(amount)
        if amount <= 0:
            return
        fid = firm.firm_id
        self.rent_receipts[fid] += amount
        self.rent_detail[fid]["current"] += _amount(current)
        self.rent_detail[fid]["arrears"] += _amount(arrears)
        self.rent_detail[fid]["relief"] += _amount(relief)
