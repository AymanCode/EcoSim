"""Observed consumer prices and bounded, annual private-firm pay decisions.

The index is a synthetic posted-price measure, not an empirical CPI. Category
weights are fixed. Within each category, matched sellers' price relatives are
geometrically averaged; entry/exit alone cannot change its index. Missing
comparisons carry the last category index and reduce reported coverage.
"""

from collections import deque
from dataclasses import dataclass
import math


class ConsumerPriceIndex:
    def __init__(self, weights, ticks_per_year=52):
        if ticks_per_year < 1 or int(ticks_per_year) != ticks_per_year:
            raise ValueError("Inflation requires a positive integer ticks_per_year")
        if not weights or any(k not in {"food", "housing", "services", "healthcare"}
                              or not math.isfinite(v) or v < 0 for k, v in weights.items()):
            raise ValueError("Invalid consumer basket weights")
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("Consumer basket must have positive total weight")
        self.weights = {k: v / total for k, v in weights.items() if v > 0}
        self.ticks_per_year = int(ticks_per_year)
        self.sector_indices = dict.fromkeys(self.weights, 100.0)
        self.previous_quotes = {}
        self.history = deque(maxlen=self.ticks_per_year + 1)
        self.level = 100.0
        self.weekly_rate = None
        self.annual_rate = None
        self.coverage = 0.0
        self.last_tick = None

    def observe(self, tick, firms):
        if tick == self.last_tick:
            return
        if self.last_tick is not None and tick < self.last_tick:
            raise ValueError("Price observations must advance in time")
        quotes = {}
        relatives = {k: [] for k in self.weights}
        for firm in firms:
            category = (firm.good_category or "").lower()
            if category not in self.weights:
                continue
            price = float(firm.price)
            if not math.isfinite(price) or price <= 0:
                continue
            key = (firm.firm_id, category)
            quotes[key] = price
            previous = self.previous_quotes.get(key)
            if previous is not None:
                relatives[category].append(math.log(price) - math.log(previous))
        first = self.last_tick is None
        self.coverage = sum(self.weights[k] for k, values in relatives.items() if values)
        for category, values in relatives.items():
            if values:
                self.sector_indices[category] *= math.exp(sum(values) / len(values))
        previous_level = self.level
        self.level = sum(self.weights[k] * v for k, v in self.sector_indices.items())
        if not math.isfinite(self.level) or self.level <= 0:
            raise ValueError("Consumer price index became invalid")
        consecutive = self.last_tick is not None and tick == self.last_tick + 1
        self.weekly_rate = self.level / previous_level - 1.0 if consecutive else None
        self.previous_quotes = quotes
        self.last_tick = tick
        self.history.append((tick, self.level))
        self.annual_rate = None
        if len(self.history) == self.ticks_per_year + 1:
            base_tick, base_level = self.history[0]
            if tick - base_tick == self.ticks_per_year:
                self.annual_rate = self.level / base_level - 1.0
        if first:
            self.coverage = sum(self.weights[k] for k in {key[1] for key in quotes})

    def snapshot(self):
        return {
            "definition": "ecosim.posted-consumer-prices.v1",
            "tick": self.last_tick,
            "index": self.level,
            "weekly_rate": self.weekly_rate,
            "annual_rate": self.annual_rate,
            "matched_basket_share": self.coverage,
            "basket_weights": dict(self.weights),
            "category_indices": dict(self.sector_indices),
        }


@dataclass
class WageReview:
    """One firm owns its clock; decisions use only already observed prices."""

    review_tick: int
    review_index: float
    last_cut_tick: int
    distress_streak: int = 0

    def plan(self, firm, index, tick, config, minimum_wage, planned_hires=0):
        if (not 0 <= config.annual_wage_raise_cap <= 1
                or not 0 <= config.distress_wage_cut < 1
                or config.distress_weeks < 1 or config.payroll_reserve_weeks <= 0):
            raise ValueError("Invalid annual wage review settings")
        payroll = firm._current_wage_bill()
        debt = sum(max(0.0, float(getattr(firm, field, 0.0))) for field in (
            "bank_loan_payment_per_tick", "service_infrastructure_loan_payment_per_tick",
            "loan_payment_per_tick",
        ))
        distressed = (firm.last_profit < 0 and payroll > 0
                      and firm.cash_balance < payroll * config.payroll_reserve_weeks)
        self.distress_streak = self.distress_streak + 1 if distressed else 0
        factor = 1.0
        reason = "annual_review_not_due"
        observed_change = index.level / self.review_index - 1.0
        if (self.distress_streak >= config.distress_weeks
                and tick - self.last_cut_tick >= index.ticks_per_year):
            factor = 1.0 - config.distress_wage_cut
            reason = "sustained_distress_cut"
            self.last_cut_tick = tick
        elif tick - self.review_tick >= index.ticks_per_year and payroll <= 0:
            # Owner decision 2026-10-01: a firm with no payroll does not use up
            # its review; the clock stays due until it has workers.
            reason = "annual_review_no_payroll"
        elif tick - self.review_tick >= index.ticks_per_year:
            requested = max(0.0, min(config.annual_wage_raise_cap, observed_change))
            # A raise must fit both recurring revenue and a cash payroll buffer.
            revenue_budget = max(0.0, firm.last_revenue - debt) * firm._firm_config().max_labor_share
            cash_budget = max(0.0, firm.cash_balance) / config.payroll_reserve_weeks
            projected_payroll = payroll + max(0, planned_hires) * firm.wage_offer * (1.0 + firm._expected_skill_premium())
            affordable = max(0.0, min(revenue_budget, cash_budget) / max(projected_payroll, 1.0) - 1.0)
            granted = min(requested, affordable) if payroll > 0 else 0.0
            factor += granted
            reason = "annual_inflation_raise" if granted > 0 else "annual_review_hold"
            self.review_tick, self.review_index = tick, index.level
        offer = max(minimum_wage, firm.wage_offer * factor)
        firm.decision_diagnostics.update({
            "wage_review_reason": reason, "wage_review_factor": factor,
            "wage_review_observed_inflation": observed_change,
            "wage_review_distress_weeks": self.distress_streak,
        })
        return {"wage_offer_next": offer, "contract_factor": factor,
                "review_minimum_wage": minimum_wage, "review_reason": reason}
