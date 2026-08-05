import sys
sys.path.insert(0, '.')
from tests_contracts.conftest import seed_everything
seed_everything(42)
from tests_contracts.factories import make_economy
eco = make_economy(seed=42)
print('in_warmup before tick 1:', eco.in_warmup)

# Patch _run_labor_matching to spy on plans
original_run = eco._run_labor_matching

def spy_labor(firm_production_plans, firm_wage_plans, household_labor_plans):
    for fid, pp in firm_production_plans.items():
        firm = eco.firm_lookup[fid]
        wp = firm_wage_plans[fid]
        searching = sum(1 for hid, lp in household_labor_plans.items() if lp.get('searching_for_job'))
        print(f'  {firm.good_name}: planned_hires={pp["planned_hires_count"]} wage_offer_next={wp["wage_offer_next"]:.1f}')
    print(f'  Searching households: {searching}')
    return original_run(firm_production_plans, firm_wage_plans, household_labor_plans)

eco._run_labor_matching = spy_labor

eco.step()
print('After tick 1:')
for f in eco.firms:
    print(f'  {f.good_name}: employees={len(f.employees)}')
