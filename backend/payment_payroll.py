"""Fund ordinary private employment before work, without creating wage IOUs."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from config import CONFIG
from payments import MONEY_EPS


def is_private_payroll_firm(economy: Any, firm: Any) -> bool:
    return (
        not firm.is_baseline
        and not economy.government.is_baseline_firm(firm.firm_id)
        and firm.good_category.lower() in {"food", "services"}
    )


def _bank_payroll_credit(economy: Any, firm: Any, gap: float) -> tuple[float, float]:
    """One request; the bank alone funds it, with all its existing credit checks."""
    bank = economy.bank
    cfg = CONFIG.firms
    if bank is None or not cfg.working_capital_enabled:
        return 0.0, 0.0
    amount = min(
        gap, max(0.0, float(cfg.working_capital_max_loan_per_firm)),
        bank._max_firm_borrowable(firm.firm_id, firm.trailing_revenue_12t),
    )
    if amount <= MONEY_EPS:
        return 0.0, 0.0
    if (not math.isclose((firm.cash_balance + amount) - firm.cash_balance,
                         amount, rel_tol=0.0, abs_tol=MONEY_EPS)
            or not math.isclose(bank.cash_reserves - (bank.cash_reserves - amount),
                                amount, rel_tol=0.0, abs_tol=MONEY_EPS)):
        return amount, 0.0
    from payment_loans import originate_v2

    rate = bank._risk_adjusted_rate(
        bank.get_firm_credit_score(firm.firm_id), float(cfg.working_capital_spread),
    )
    loan = originate_v2(
        economy, "firm", firm.firm_id, amount, rate,
        int(cfg.working_capital_term_ticks), "working_capital", funder="bank",
    )
    if loan is None:
        return amount, 0.0
    firm.cash_balance += amount
    return amount, amount


def enforce_private_payroll(economy: Any, firm_labor_outcomes: dict, household_labor_outcomes: dict) -> None:
    """Finalize affordable contracts after raises, before crediting work history."""
    if economy.payment_sequence == "legacy":
        return
    cancelled_hires = set()
    for firm in economy.firms:
        if not is_private_payroll_firm(economy, firm):
            continue
        fid = firm.firm_id
        wages = {hid: float(firm.actual_wages.get(hid, firm.wage_offer)) for hid in firm.employees}
        if any(not math.isfinite(value) or value < 0.0 for value in wages.values()):
            raise ValueError("Private payroll contracts must be finite and nonnegative")
        cash = float(firm.cash_balance)
        if not math.isfinite(cash):
            raise ValueError("Private payroll cash must be finite")
        required = math.fsum(wages.values())
        requested = funded = 0.0
        if math.fsum([*wages.values(), -max(0.0, cash)]) > MONEY_EPS:
            gap = math.fsum([*wages.values(), -cash])
            requested, funded = _bank_payroll_credit(economy, firm, gap)
        available = max(0.0, float(firm.cash_balance))
        outcome = firm_labor_outcomes[fid]
        hires = list(outcome.get("hired_households_ids", ()))
        hired_set = set(hires)
        removed = []
        layoffs = []
        if math.fsum([*wages.values(), -available]) > MONEY_EPS:
            # Do not displace an incumbent to retain an unfunded new hire.
            order = [hid for hid in reversed(hires) if hid in wages]
            order.extend(hid for hid in firm.employees if hid not in hired_set)
            # Choose the affordable suffix directly. Subtracting a very large
            # removed wage from a rounded total can erase a small real deficit.
            # Exact binary-float ratios are used only on this distress path;
            # denominators are powers of two and the traversal remains linear.
            budget = Fraction(available) + Fraction(MONEY_EPS)
            retained_cost = Fraction(0)
            keep_from = len(order)
            for index in range(len(order) - 1, -1, -1):
                candidate_cost = retained_cost + Fraction(wages[order[index]])
                if candidate_cost > budget:
                    break
                retained_cost = candidate_cost
                keep_from = index
            for hid in order[:keep_from]:
                removed.append(hid)
                hh = economy.household_lookup[hid]
                if hid in hired_set:
                    cancelled_hires.add((fid, hid))
                else:
                    layoffs.append(hid)
                    economy.last_labor_events.append({
                        "tick": int(economy.current_tick + 1), "household_id": int(hid),
                        "firm_id": int(fid), "event_type": "layoff", "actual_wage": wages[hid],
                        "wage_offer": float(firm.wage_offer),
                        "reservation_wage": float(hh.reservation_wage),
                        "skill_level": float(hh.skills_level), "reason_code": "payroll_unfunded",
                    })
                hh.employer_id = None
                hh.wage = 0.0
                household_labor_outcomes[hid] = {
                    "employer_id": None, "wage": 0.0, "employer_category": None,
                }
            removed_set = set(removed)
            firm.employees = [hid for hid in firm.employees if hid not in removed_set]
            for hid in removed:
                firm.actual_wages.pop(hid, None)
                outcome.get("actual_wages", {}).pop(hid, None)
            firm._invalidate_wage_bill_cache()
            outcome["hired_households_ids"] = [hid for hid in hires if hid not in removed_set]
            outcome["confirmed_layoffs_ids"] = list(outcome.get("confirmed_layoffs_ids", ())) + layoffs
            cancelled_count = len(removed) - len(layoffs)
            outcome["unfilled_vacancies"] = int(outcome.get("unfilled_vacancies", 0)) + cancelled_count
            if cancelled_count:
                outcome["failed_match_reason"] = "payroll_unfunded"
            firm.last_tick_actual_hires = len(outcome["hired_households_ids"])
            firm.last_tick_unfilled_vacancies = int(outcome["unfilled_vacancies"])
            firm.last_tick_failed_match_reason = str(outcome.get("failed_match_reason", ""))
            firm.decision_diagnostics.update({
                "last_tick_unfilled_vacancies": firm.last_tick_unfilled_vacancies,
                "last_tick_failed_match_reason": firm.last_tick_failed_match_reason,
            })
            if firm._is_generic_services_firm():
                firm.service_staffing_target = min(
                    max(0, int(firm.production_capacity_units)), max(1, len(firm.employees)),
                )
                firm.service_staffing_recovery_streak = 0
                firm.service_staffing_recovery_counted_tick = firm.age_in_ticks
        firm.decision_diagnostics.update({
            "payroll_required": required, "payroll_cash_before": max(0.0, cash),
            "payroll_credit_requested": requested, "payroll_credit_funded": funded,
            "payroll_cancelled_hires": len(removed) - len(layoffs),
            "payroll_financial_layoffs": len(layoffs), "payroll_funded_workers": len(firm.employees),
        })
        economy.payment_book.funded_payroll_firms.add(fid)
    if cancelled_hires:
        economy.last_labor_events = [
            event for event in economy.last_labor_events
            if not (event["event_type"] == "hire"
                    and (event["firm_id"], event["household_id"]) in cancelled_hires)
        ]
        book = economy.payment_book
        book.net_offer_diagnostics = [
            row for row in getattr(book, "net_offer_diagnostics", ())
            if (row["offer_id"], row["household_id"]) not in cancelled_hires
        ]
