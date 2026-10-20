"""One definition of a household's liquid money, shared by every reader.

Two quantities, built from the same two balances (``cash_balance`` and
``bank_deposit``):

``liquid_wealth(cash, deposit)``
    Cash plus the full positive deposit balance. This is the household's
    liquid net worth before loans (loan balances are not netted; #32). The
    poverty penalties and the wealth-loss term of wellbeing read it, because
    the deposit sweep and bank withdrawals move money between the two within
    a tick, and reading cash alone scored saving as a loss.

``accessible_liquidity(cash, deposit)``
    Cash plus the share of the positive deposit balance the bank pays out on
    demand (``DEPOSIT_ACCESS_SHARE``, 90%). This is what a household can spend
    or pay this tick: the consumption budget, the rent tests, the payment
    planners and every pre-purchase withdrawal read it. It is
    ``liquid_wealth`` minus the 10% the bank holds back.

Both take raw balances rather than a household, so the same function serves
the start-of-tick snapshot (``last_tick_cash_start``,
``last_tick_deposit_start``) and the live balances. A caller that floors cash
at zero first passes ``max(0.0, cash)``. Scalar and array versions perform
the same floating-point operations in the same order, so a migrated reader
returns bit-identical values.

Edge behavior: a negative deposit counts as 0. A negative cash balance is
passed through (callers that floor it do so explicitly). No validation is
done here; inputs are the agents' own balances.
"""

from __future__ import annotations

import numpy as np

#: Share of a positive deposit balance withdrawable on demand within a tick.
#: Existing model constant (previously repeated as 0.90 at each call site).
DEPOSIT_ACCESS_SHARE = 0.90


def withdrawable_deposit(deposit: float) -> float:
    """Deposit money a household can withdraw this tick: 90% of a positive balance."""
    return DEPOSIT_ACCESS_SHARE * max(0.0, deposit)


def liquid_wealth(cash: float, deposit: float) -> float:
    """Cash plus the whole positive deposit balance (#32's liquid wealth)."""
    return cash + max(0.0, deposit)


def accessible_liquidity(cash: float, deposit: float) -> float:
    """Cash plus the withdrawable share of a positive deposit balance."""
    return cash + withdrawable_deposit(deposit)


def liquid_wealth_array(cash: np.ndarray, deposit: np.ndarray) -> np.ndarray:
    """Vectorized ``liquid_wealth``."""
    return cash + np.maximum(deposit, 0.0)


def accessible_liquidity_array(cash: np.ndarray, deposit: np.ndarray) -> np.ndarray:
    """Vectorized ``accessible_liquidity``."""
    return cash + DEPOSIT_ACCESS_SHARE * np.maximum(deposit, 0.0)
