"""One shared definition of household liquid money (households 29a).

``household_liquidity`` holds the two quantities every household reader uses:
liquid wealth (cash + 100% of a positive deposit, #32's definition) and
accessible liquidity (cash + the 90% of a positive deposit the bank pays out
within a tick). The migration is behavior-preserving; these tests pin the
definitions, their edges, the scalar/array parity, and one realized outcome
of a full ``Economy.step``.
"""

import math
import random

import numpy as np
import pytest

from config import CONFIG
from household_liquidity import (
    DEPOSIT_ACCESS_SHARE,
    accessible_liquidity,
    accessible_liquidity_array,
    liquid_wealth,
    liquid_wealth_array,
    withdrawable_deposit,
)


def test_definitions_match_the_documented_formulas():
    assert liquid_wealth(120.0, 300.0) == 420.0
    assert accessible_liquidity(120.0, 300.0) == 120.0 + 0.90 * 300.0
    assert withdrawable_deposit(300.0) == pytest.approx(270.0)
    assert DEPOSIT_ACCESS_SHARE == 0.90


@pytest.mark.parametrize("cash, deposit", [(0.0, 0.0), (50.0, -10.0), (-40.0, 100.0), (-40.0, -5.0)])
def test_edges_negative_deposit_counts_zero_negative_cash_passes_through(cash, deposit):
    assert liquid_wealth(cash, deposit) == cash + max(0.0, deposit)
    assert accessible_liquidity(cash, deposit) == cash + 0.90 * max(0.0, deposit)
    assert withdrawable_deposit(deposit) >= 0.0


def test_non_finite_inputs_propagate_rather_than_being_hidden():
    # The helper does not validate; callers that require finite money
    # (payment_behavior._finite) reject NaN/inf before calling it.
    assert math.isnan(liquid_wealth(float("nan"), 10.0))
    assert math.isinf(accessible_liquidity(float("inf"), 10.0))


def test_scalar_and_array_versions_are_bit_identical():
    rng = np.random.default_rng(0)
    cash = rng.normal(200.0, 400.0, 2_000)
    deposit = rng.normal(300.0, 500.0, 2_000)
    arr_lw = liquid_wealth_array(cash, deposit)
    arr_al = accessible_liquidity_array(cash, deposit)
    for c, d, lw, al in zip(cash, deposit, arr_lw, arr_al):
        assert liquid_wealth(float(c), float(d)) == float(lw)
        assert accessible_liquidity(float(c), float(d)) == float(al)


def test_no_inline_copies_of_the_deposit_haircut_remain():
    """Every household reader goes through the helper (no 0.9/0.90 x deposit inline)."""
    import pathlib
    import re

    backend = pathlib.Path(__file__).resolve().parents[1]
    pattern = re.compile(r"0\.90?\s*\*\s*(?:np\.)?max(?:imum)?\(0\.0,\s*[\w.()]*deposit|0\.90?\s*\*\s*deposit")
    offenders = []
    for name in ("economy.py", "payment_sectors.py", "payment_behavior.py", "agents.py"):
        for lineno, line in enumerate((backend / name).read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{name}:{lineno}: {line.strip()}")
    assert offenders == []


def test_economy_step_withdrawals_never_exceed_the_accessible_share():
    """Realized outcome: in a live legacy step, the tick's pre-purchase
    withdrawal total stays within the withdrawable share of the deposits held
    at the start of the tick, and no deposit goes negative. There is no
    per-household 90% bound: the legacy cash-buffer refill in the deposit
    sweep may withdraw a whole deposit."""
    from tools.runners.run_large_simulation import create_large_economy
    import contextlib
    import io

    random.seed(42)
    np.random.seed(42)
    CONFIG.random_seed = 42
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=150, num_firms_per_category=3)
        for _ in range(12):
            economy.step()
    checked = 0
    for _ in range(6):
        before = {h.household_id: h.bank_deposit for h in economy.households}
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        for h in economy.households:
            start = before[h.household_id]
            if start <= 0.0:
                continue
            checked += 1
            # Each withdrawal call is capped at 90% of the balance at that
            # moment, several calls can run in one tick, and the legacy buffer
            # refill may withdraw the remainder, so only the sign is checked.
            assert h.bank_deposit >= -1e-9
            assert liquid_wealth(h.cash_balance, h.bank_deposit) == h.cash_balance + max(0.0, h.bank_deposit)
        # Pre-purchase withdrawals moved real money; their total is bounded by
        # the accessible share of the deposits held at the start of the tick.
        cap = sum(withdrawable_deposit(d) for d in before.values())
        assert 0.0 <= economy.last_tick_pre_purchase_deposit_withdrawals <= cap + 1e-6
    assert checked > 0
