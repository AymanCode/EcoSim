"""Small reproducible policy/timing smoke comparisons; not economic calibration."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import random
import sys

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / 'backend'), str(root)]
import numpy as np
from config import clone_config, use_config
from run_evidence import conditions, model_identity
from tools.runners.run_large_simulation import create_large_economy


def state_hash(economy):
    state = {
        'households': [(h.household_id, h.cash_balance, h.bank_deposit, h.employer_id,
                        h.wage, h.health, h.skills_level) for h in economy.households],
        'firms': [(f.firm_id, f.cash_balance, f.price, tuple(f.employees), f.inventory_units,
                   f.production_capacity_units) for f in economy.firms],
        'treasury': economy.government.cash_balance,
        'bank': economy.bank.cash_reserves,
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def run(seed, mode, name, timing, care, assistance, tax):
    random.seed(seed)
    np.random.seed(seed)
    cfg = clone_config()
    cfg.random_seed = seed
    cfg.payment_sequence, cfg.payment_care_mode, cfg.payment_assistance = timing, care, assistance
    with use_config(cfg), contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(100, 2)
        economy.performance_mode = mode
        economy.warmup_ticks = 3
        economy.government.wage_tax_rate = tax
        initial = state_hash(economy)
        initial_conditions = conditions(economy)
        visits = 0.0
        denied = 0
        for _ in range(60):
            economy.step()
            visits += economy.healthcare_completed_visits_this_tick
            denied += economy.payment_care_funding_denials_this_tick
        metrics = economy.get_economic_metrics()
        selected = {k: metrics[k] for k in ['unemployment_rate', 'mean_health', 'gini_coefficient',
                    'government_cash', 'gdp_this_tick', 'total_household_cash']}
        selected.update(completed_visits=visits, care_funding_denials=denied,
                        wage_claims=metrics['payment']['income']['wage_claim_outstanding'],
                        rent_arrears=metrics['payment']['rent']['arrears_outstanding'])
        return {'seed': seed, 'performance_mode': mode, 'name': name, 'ticks': 60,
                'initial_actor_hash': initial, 'final_actor_hash': state_hash(economy),
                'conditions': initial_conditions, 'outcomes': selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = [('tax15', 'income_first', 'patient_pay', 'reserve', .15),
             ('tax40', 'income_first', 'patient_pay', 'reserve', .40),
             ('late15', 'income_late', 'patient_pay', 'reserve', .15),
             ('covered15', 'income_first', 'covered', 'care', .15)]
    rows = [run(seed, mode, *case) for seed in (42, 43) for mode in (False, True) for case in cases]
    replay = run(42, False, *cases[0])
    initial_equal = all(len({r['initial_actor_hash'] for r in rows if r['seed'] == seed and r['performance_mode'] == mode}) == 1
                        for seed in (42, 43) for mode in (False, True))
    result = {'source': model_identity(root), 'rows': rows,
              'equal_initial_actor_state_per_seed_mode': initial_equal,
              'replay_matches': replay['final_actor_hash'] == rows[0]['final_actor_hash'] and replay['outcomes'] == rows[0]['outcomes'],
              'limits': 'Initial hash covers listed actor balances/contracts/health/capacity, not every hidden field. Same seed does not certify paired endogenous shocks. Covered case changes both payer and receipt earmark. Nominal sales, cash-only inequality and uncalibrated health are retained metrics.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source', 'rows')}))


if __name__ == '__main__':
    main()
