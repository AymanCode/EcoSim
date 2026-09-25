"""Small counterexamples to proposed rules, not implemented future features.
Run: PYTHONPATH=backend python docs/reviews/verify_design_counterexamples.py
"""

from collections import deque
import json

from agents import GovernmentAgent, HouseholdAgent
from config import CONFIG

results = {}
# W06's signed-M definition already offsets a treasury overdraft disbursement.
initial_m = 100.0 + 0.0
final_m = 110.0 - 10.0
results["D01"] = {
    "signed_cash_change": final_m - initial_m,
    "proposed_overdraft_creation_line": 10.0,
    "artificial_residual": (final_m - initial_m) - 10.0,
}
assert results["D01"]["artificial_residual"] == -10.0

# The actual existing progressive schedule cannot be recovered from a uniform
# headline fallback after moving away from a zero headline tax rate.
gov = GovernmentAgent()
gov.set_lever("wage_tax_rate", 0.4)
rows = [{"household_id": i, "wage_income": float(i * 40)} for i in range(1, 7)]
actual = gov.plan_taxes(rows, [])["wage_taxes"]
rates = [actual[r["household_id"]] / r["wage_income"] for r in rows]
results["D03"] = {
    "actual_effective_rates_at_headline_40_percent": rates,
    "proposed_zero_rate_fallback": [0.4] * len(rows),
    "initial_zero_expectation_after_rescale": 0 * (0.4 / 0.15),
    "two_updates_overwritten_ratio_result": 0.15 * (0.4 / 0.2),
    "required_final_headline": 0.4,
}
assert rates != [0.4] * len(rows)
assert results["D03"]["two_updates_overwritten_ratio_result"] != 0.4

# Identical previous mean and identical new observation need different results.
a, b = [0, 0, 0, 4], [4, 0, 0, 0]
results["D04"] = {
    "previous_means": [sum(a) / 4, sum(b) / 4],
    "new_observation": 0,
    "next_exact_means": [sum(a[1:]) / 4, sum(b[1:]) / 4],
}
assert results["D04"]["previous_means"][0] == results["D04"]["previous_means"][1]
assert results["D04"]["next_exact_means"][0] != results["D04"]["next_exact_means"][1]

pipeline = deque([0.0, 0.0], maxlen=2)
delivered, lengths = [], []
for spend in [1.0, 0.0, 0.0]:
    pipeline.append(spend)
    delivered.append(pipeline.popleft())
    lengths.append(len(pipeline))
results["D07"] = {"requested_delay": 2, "append_then_pop_deliveries": delivered, "queue_lengths": lengths}
assert delivered == [0.0, 1.0, 0.0]
assert lengths == [1, 1, 1]

hh = HouseholdAgent(household_id=1, skills_level=0.5, age=35, cash_balance=10000)
hh.saving_tendency = 0.9
hh.savings_drawdown_rate = 0.02
mpc = CONFIG.households.mpc_wage
results["N2"] = {
    "scalar_saving_input": hh.compute_saving_rate(),
    "batch_saving_input": hh.savings_drawdown_rate,
    "scalar_wage_mpc_before_caps": max(0.70, mpc * (1 - 0.3 * hh.compute_saving_rate())),
    "batch_wage_mpc_before_caps": max(0.70, mpc * (1 - 0.3 * hh.savings_drawdown_rate)),
}
assert results["N2"]["scalar_saving_input"] != results["N2"]["batch_saving_input"]
print(
    json.dumps(
        {
            "scope": "equation counterexamples and current source inputs; not aggregate policy effects",
            "results": results,
        },
        indent=2,
    )
)
