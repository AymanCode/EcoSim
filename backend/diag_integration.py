import sys
sys.path.insert(0, '.')
from tests_contracts.conftest import seed_everything
seed_everything(42)
from tests_contracts.factories import make_economy
eco = make_economy(seed=42)
print('in_warmup:', eco.in_warmup, 'warmup_ticks:', eco.warmup_ticks)

# Manually run tick phases to inspect
import economy as eco_module
import numpy as np

# Capture the labor plans
orig_match = eco._run_labor_matching.__func__ if hasattr(eco._run_labor_matching, '__func__') else None

# Just run one step and intercept
eco.step()

print('After tick 1:')
for f in eco.firms:
    print(f'  {f.good_name}: employees={len(f.employees)} planned_hires={f.planned_hires_count} wage={f.wage_offer:.1f}')
print('eco.in_warmup:', eco.in_warmup)
