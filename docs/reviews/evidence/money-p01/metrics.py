"""Read-only R&D flow observer and business stocks for MONEY-P01 panels."""
from collections import defaultdict
from agents import FirmAgent

_original_rd = FirmAgent.apply_rd_and_quality_update
_flows = defaultdict(float)


def _observe_rd(self, revenue, *args, **kwargs):
    cash = max(0.0, self.cash_balance)
    amount = _original_rd(self, revenue, *args, **kwargs)
    sector = self.good_category.lower()
    _flows['rd_calls'] += 1
    _flows['rd_unfunded_calls'] += float(amount > cash + 1e-9)
    _flows['rd_unfunded_dollars'] += max(0.0, amount - cash)
    _flows[sector + '_rd_paid'] += amount
    return amount


FirmAgent.apply_rd_and_quality_update = _observe_rd


def extra_metrics(economy):
    values = {name: _flows[name] for name in (
        'rd_calls', 'rd_unfunded_calls', 'rd_unfunded_dollars',
        'food_rd_paid', 'services_rd_paid',
    )}
    _flows.clear()
    for sector in ('food', 'services'):
        firms = [f for f in economy.firms if f.good_category.lower() == sector]
        values[sector + '_cash'] = sum(f.cash_balance for f in firms)
        values[sector + '_quality'] = sum(f.quality_level for f in firms) / len(firms) if firms else 0.0
        values[sector + '_active_accumulated_rd'] = sum(f.accumulated_rd_investment for f in firms)
    return values


METRICS = {
    'rd_unfunded_calls': ('R&D debits above nonnegative available cash', 'calls', ('sum',), None),
    'rd_unfunded_dollars': ('Unfunded R&D amount', '$', ('sum',), None),
}
