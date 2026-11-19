"""Shared ordering and alternative-seller selection for the shopping experiment."""

import random

from config import CONFIG


def ordered_plans(plans, current_tick, salt):
    """Preserve insertion order unless the experimental rationing is enabled."""
    if not CONFIG.households.fix_spending_leak:
        return plans.items()
    ids = sorted(plans)
    # These fixed mixers and per-pass salts only derive independent PRNG seeds;
    # they are not behavioral parameters or real-world calibration values.
    seed = (int(CONFIG.random_seed) * 1_000_003 + int(current_tick) * 7_919 + salt) & 0xFFFFFFFF
    random.Random(seed).shuffle(ids)
    return ((hid, plans[hid]) for hid in ids)


def alternative_sellers(household, economy, target, firms, prices, remaining):
    """Stocked same-category firms in the household's preferred order."""
    category = (target.good_category or "").lower()
    target_price = prices[target.firm_id]
    pool = household.awareness_pool.get(category)
    pool_ids = set(pool) if pool else None
    options = [firm for firm in firms
               if firm.firm_id != target.firm_id
               and (firm.good_category or "").lower() == category
               and remaining[firm.firm_id] > 0
               and (pool_ids is None or firm.firm_id in pool_ids)]
    if pool_ids is None:
        return sorted(options, key=lambda firm: (prices[firm.firm_id], firm.firm_id))
    return sorted(options, key=lambda firm: (
        -(household.quality_lavishness * economy._effective_firm_quality(firm)
          - household.price_sensitivity * (prices[firm.firm_id] / target_price)),
        firm.firm_id,
    ))
