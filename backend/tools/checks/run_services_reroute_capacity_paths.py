"""Matched bounded Services paths on either checkout's income-first engine.

Run this same file in separate processes with --backend set to each checkout
root (or its backend directory). The executable fixture fixes only the opening
market and shopping intentions. It inherits the business harness's fixed
health/wellbeing, no-entry and no-shock conditions. There is no external buyer.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from unittest.mock import patch


SEED = 43
FIRST_TICK = 40
WEEKS = 36
RECEIVER, PRIMARY = 1, 2
BUYER = 22
PATHS = ("pulse", "persistent", "direct", "cash_short_direct")
FUNDING = {
    # Opening receiver cash, bank reserves after its opening infrastructure loan.
    "standard": (8000.0, 50_000.0),
    "mixed": (1000.0, 50_000.0),
    "cash": (30_000.0, 50_000.0),
    "borrow": (500.0, 50_000.0),
    "limited_bank": (1000.0, 800.0),
    "empty_bank": (500.0, 0.0),
}


def intended_orders(path, week):
    # One customer can intentionally visit both originals; dict order puts the
    # primary's stockout first. The market decides whether and where it reroutes.
    if week <= 3:
        return {PRIMARY: 5.0, RECEIVER: 30.0}
    if week <= 5 or path == "persistent":
        primary = 110.0 if path == "persistent" else 60.0
        direct = 30.0 if path in ("direct", "cash_short_direct") else 2.0
        return {PRIMARY: primary, RECEIVER: direct}
    return {PRIMARY: 5.0, RECEIVER: 22.0}


def run_path(path, funding):
    import numpy as np

    from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
    from config import clone_config, use_config
    import payment_sectors
    from payment_loans import originate_v2
    from payments import PaymentBook
    from tools.benchmarks.panel_money import total_money_net_of_injections
    from tools.checks.run_business_scenarios import BusinessTestEconomy, Settings, snapshot

    class ObservedGoodsMarket(payment_sectors.PaymentGoodsMarket):
        def _buy_with_substitution(self, household, target, wanted):
            self.original_seller = int(target)
            return super()._buy_with_substitution(household, target, wanted)

        def _commit_experiment_sale(self, household, firm, qty, subsidy):
            paid = super()._commit_experiment_sale(household, firm, qty, subsidy)
            if paid:
                self.economy.sales_trace.append({
                    "household": household.household_id, "target": self.original_seller,
                    "seller": firm.firm_id, "units": qty, "price": self.prices[firm.firm_id],
                })
            return paid

    class CapacityEconomy(BusinessTestEconomy):
        def _batch_plan_consumption(self, *args, **kwargs):
            buyer = self.household_lookup[BUYER]
            self.checkout_cash = buyer.cash_balance
            return {
                BUYER: {
                    "household_id": BUYER, "budget": buyer.cash_balance,
                    "planned_purchases": intended_orders(path, self.current_tick - FIRST_TICK + 1),
                },
            }

        def _phase_labor_matching(self, tick):
            self.applicants = sorted(
                hid for hid, plan in tick.household_labor_plans.items()
                if plan.get("searching_for_job")
            )
            super()._phase_labor_matching(tick)

        def _fund_service_expansion(self, firm, cost, annual_rate, term_ticks, subtype, slots_added):
            cash_before = firm.cash_balance
            bank_before = self.bank.cash_reserves
            claim_count_before = len(self.bank.active_loans)
            contribution, credit = self._service_expansion_funding_quote(
                firm, cost, annual_rate, term_ticks, slots_added,
            )
            actual_credit = super()._fund_service_expansion(
                firm, cost, annual_rate, term_ticks, subtype, slots_added,
            )
            self.funding_trace.append({
                "firm": firm.firm_id, "route": subtype, "cost": cost,
                "requested_slots": slots_added, "quoted_cash": contribution, "quoted_credit": credit,
                "approved": actual_credit is not None,
                "paid_cash": cash_before - firm.cash_balance,
                "bank_debit": bank_before - self.bank.cash_reserves,
                "claims": [dict(claim) for claim in self.bank.active_loans[claim_count_before:]],
            })
            return actual_credit

        def _recycle_capital_investment(self):
            before = sum(h.cash_balance for h in self.households)
            super()._recycle_capital_investment()
            self.household_capital_credit += sum(h.cash_balance for h in self.households) - before

        def _offer_service_infrastructure_loans(self):
            before_pool = self.misc_firm_revenue
            before_treasury = self.government.cash_balance
            super()._offer_service_infrastructure_loans()
            amount = self.misc_firm_revenue - before_pool + self.government.cash_balance - before_treasury
            if amount > 0:
                self.misc_trace.append({
                    "amount": amount, "pool_credit": self.misc_firm_revenue - before_pool,
                    "treasury_credit": self.government.cash_balance - before_treasury,
                })

    config = clone_config()
    config.payment_sequence = "income_first"
    config.random_seed = SEED
    config.time.warmup_ticks = 0
    config.llm.enable_llm_government = False
    config.modes.government_stabilizers = False
    config.government.auto_working_capital_backstop = False
    config.households.fix_spending_leak = True
    config.households.job_choices = True
    random.seed(SEED)
    np.random.seed(SEED)
    cash, bank_reserves = FUNDING[funding]
    with use_config(config), patch.object(payment_sectors, "PaymentGoodsMarket", ObservedGoodsMarket):
        households = [
            HouseholdAgent(i, cash_balance=100.0, skills_level=0.5, age=30)
            for i in range(1, BUYER + 1)
        ]
        for h in households:
            h.deposit_fraction = 0.0  # Opening preference keeps bank liquidity fixtures distinct.
            h.skills_level = 0.5
            h.expected_wage = h.reservation_wage = 10.0
            h.happiness = h.morale = h.health = 0.8
        buyer = households[-1]
        buyer.cash_balance = 3800.0 if path == "cash_short_direct" else 500_000.0
        buyer.health = 0.05  # The buyer is outside this fixture's applicant pool.
        firms = []
        for fid, employees, balance, price in (
            (RECEIVER, households[:4], cash, 30.0),
            (PRIMARY, households[4:5], 30_000.0, 30.0),
        ):
            firm = FirmAgent(
                firm_id=fid, good_name=f"Service {fid}", good_category="Services",
                cash_balance=balance, wage_offer=20.0, price=price,
                inventory_units=0.0, production_capacity_units=len(employees),
                expected_sales_units=5.0 * len(employees), personality="moderate",
                is_baseline=fid == PRIMARY,
            )
            firm.wage_offer, firm.price, firm.units_per_worker = 20.0, price, 5.0
            firm.age_in_ticks, firm.ceo_household_id, firm.owners = 30, None, []
            for h in employees:
                h.employer_id, h.wage = fid, firm.wage_offer
                firm.employees.append(h.household_id)
                firm.actual_wages[h.household_id] = h.wage
            supply = firm._capacity_for_workers(len(employees))
            firm.expected_sales_units = firm.last_units_produced = firm.last_units_sold = supply
            firm.last_revenue = firm.revenue_ema = supply * price
            firm.last_tick_total_costs = len(employees) * firm.wage_offer
            firm.last_profit = firm.last_revenue - firm.last_tick_total_costs
            firm.smoothed_profit_margin = firm.last_profit / firm.last_revenue
            firm.sales_velocity_ema, firm.last_sell_through_rate = supply, 1.0
            firms.append(firm)
        govt = GovernmentAgent(cash_balance=20_000.0, unemployment_benefit_level=0, transfer_budget=0)
        govt.unemployment_benefit_level = 0
        bank = BankAgent(cash_reserves=bank_reserves + 7000.0)
        ec = CapacityEconomy(households, firms, govt, bank=bank)
        ec.scenario_settings, ec.base_productivity = Settings(category="Services"), 5.0
        ec.current_tick, ec.in_warmup = FIRST_TICK - 1, False
        ec.performance_mode, ec.audit_log_enabled = False, True

        # The receiver opens with an outstanding loan on its existing space.
        # Originate the real claim against the opening operating history. Its
        # proceeds were spent before this fixture's opening money snapshot.
        receiver = firms[0]
        ec.payment_state["prior_settled_firm_operating_cashflow"] = {RECEIVER: receiver.last_profit}
        opening_claim = originate_v2(ec, "firm", RECEIVER, 7000.0, 0.05, 104, "service_infrastructure")
        if opening_claim is None:
            raise RuntimeError("Opening infrastructure loan failed underwriting")
        ec.current_tick = FIRST_TICK
        ec.payment_book = PaymentBook(ec, timing=config.payment_sequence)
        for firm in firms:
            ec.last_tick_sales_units[firm.firm_id] = firm.last_units_sold
            ec.last_tick_sell_through_rate[firm.firm_id] = firm.last_sell_through_rate
        opening_money = total_money_net_of_injections(ec)
        opening = {
            "firms": {f.firm_id: snapshot(f) for f in firms},
            "household_cash": {h.household_id: h.cash_balance for h in households},
            "bank_cash": bank.cash_reserves, "infrastructure_claim": dict(opening_claim),
            "available_worker_ids": [h.household_id for h in households[5:-1]],
            "money_net_of_injections": opening_money,
        }
        rows = []
        for week in range(1, WEEKS + 1):
            ec.sales_trace, ec.funding_trace, ec.misc_trace = [], [], []
            ec.household_capital_credit = 0.0
            slots_before = {f.firm_id: f.production_capacity_units for f in ec.firms}
            cooldown_before = {f.firm_id: f.last_long_term_loan_tick for f in ec.firms}
            ec.step()
            audit = ec._last_tick_audit
            firm_rows = {}
            for firm in ec.firms:
                fid = firm.firm_id
                sales = [sale for sale in ec.sales_trace if sale["seller"] == fid]
                direct = sum(sale["units"] for sale in sales if sale["target"] == fid)
                fallback = sum(sale["units"] for sale in sales if sale["target"] != fid)
                firm_rows[fid] = {
                    **snapshot(firm), "slots_added": firm.production_capacity_units - slots_before[fid],
                    "output": firm.last_units_produced,
                    "idle_output": max(0.0, firm.last_units_produced - direct - fallback),
                    "direct_sales": direct, "fallback_sales": fallback,
                    "funded_own_missed_units": ec.services_unmet_demand_by_firm.get(fid, 0.0),
                    "hires_requested": audit["firm_production_plans"][fid]["planned_hires_count"],
                    "labor_outcome": audit["firm_labor_outcomes"][fid],
                    "payroll_paid": ec.payment_book.funded_wages_by_firm.get(fid, 0.0),
                    "payroll_arrears": firm.payment_wage_arrears,
                    "loan_remaining": firm.bank_loan_remaining,
                    "last_long_term_loan_tick_before": cooldown_before[fid],
                    "last_long_term_loan_tick": firm.last_long_term_loan_tick,
                    "diagnostics": {
                        key: value for key, value in firm.decision_diagnostics.items()
                        if key.startswith(("service_", "payroll_", "long_term_"))
                    },
                }
            money = total_money_net_of_injections(ec)
            rows.append({
                "week": week, "tick": ec.current_tick - 1,
                "intended_orders": intended_orders(path, week),
                "buyer_cash_at_planning": ec.checkout_cash, "buyer_cash_close": buyer.cash_balance,
                "closed_firms": sorted(slots_before.keys() - firm_rows.keys()),
                "firms": firm_rows, "sales": ec.sales_trace, "proposals": ec.funding_trace,
                "applicants": ec.applicants,
                "funded_unfilled_services": ec.services_unmet_demand,
                "capital_routes": list(ec.payment_state.get("capital_routes", ())),
                "household_capital_credit": ec.household_capital_credit, "misc_receipts": ec.misc_trace,
                "bank_cash": bank.cash_reserves, "treasury_cash": govt.cash_balance,
                "money_net_of_injections": money, "money_drift": money - opening_money,
            })
        proposals = [
            {"week": row["week"], "tick": row["tick"], **proposal}
            for row in rows for proposal in row["proposals"]
            if proposal["firm"] == RECEIVER and proposal["route"] == "long_term_capital"
        ]
        return {
            "path": path, "funding_fixture": funding, "opening": opening, "weeks": rows,
            "first_proposal": proposals[0] if proposals else None,
            "long_term_proposals": proposals,
            "max_absolute_money_drift": max(abs(row["money_drift"]) for row in rows),
        }


def check_accounting(result):
    def reconcile(left, right, description):
        if not math.isclose(left, right, rel_tol=0.0, abs_tol=1e-6):
            raise RuntimeError(f"{result['path']} week {row['week']}: {description}: {left} != {right}")

    for row in result["weeks"]:
        reconcile(row["money_drift"], 0.0, "money drift")
        long_term = infrastructure = 0.0
        installed_slots = dict.fromkeys(row["firms"], 0.0)
        for proposal in row["proposals"]:
            paid = proposal["paid_cash"] + proposal["bank_debit"]
            reconcile(paid, proposal["cost"] if proposal["approved"] else 0.0, "project funding")
            reconcile(proposal["bank_debit"], sum(c["principal"] for c in proposal["claims"]), "bank claims")
            fid = proposal["firm"]
            if proposal["approved"]:
                installed_slots[fid] += proposal["requested_slots"]
            if proposal["route"] == "long_term_capital":
                firm = row["firms"][fid]
                expected_cooldown = row["tick"] if proposal["approved"] else firm["last_long_term_loan_tick_before"]
                reconcile(firm["last_long_term_loan_tick"], expected_cooldown, "long-term cooldown")
                long_term += paid
            else:
                infrastructure += paid
        reconcile(long_term, row["household_capital_credit"], "household capital receipt")
        reconcile(long_term, sum(route["amount"] for route in row["capital_routes"]), "capital route")
        reconcile(infrastructure, sum(receipt["amount"] for receipt in row["misc_receipts"]), "infrastructure route")
        for receipt in row["misc_receipts"]:
            reconcile(receipt["amount"], receipt["pool_credit"] + receipt["treasury_credit"], "misc receipt split")
        for fid, firm in row["firms"].items():
            reconcile(firm["slots_added"], installed_slots[fid], "installed worker slots")
            reconcile(firm["direct_sales"] + firm["fallback_sales"], firm["last_sales"], "settled Services")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Checkout root or its backend directory")
    parser.add_argument("--path", choices=(*PATHS, "all"), default="all")
    parser.add_argument("--funding", choices=FUNDING, default="standard")
    args = parser.parse_args()
    backend = args.backend.resolve()
    if (backend / "backend" / "economy.py").is_file():
        backend /= "backend"
    if not (backend / "economy.py").is_file():
        parser.error(f"No backend/economy.py or economy.py under {args.backend}")
    sys.path.insert(0, str(backend))
    from tools.checks.run_agent_scenarios import json_scalar
    paths = PATHS if args.path == "all" else (args.path,)
    with contextlib.redirect_stdout(io.StringIO()):
        results = [run_path(path, args.funding) for path in paths]
    for result in results:
        check_accounting(result)
    revision = subprocess.run(["git", "-C", str(backend), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=False).stdout.strip()
    print(json.dumps({
        "backend": str(backend), "revision": revision, "seed": SEED,
        "payment_sequence": "income_first", "results": results,
    }, indent=2, default=json_scalar, allow_nan=False))


if __name__ == "__main__":
    main()
