"""Dashboard fiscal balance excludes public-debt financing (G1).

The frame's ``govProfit`` was the change in treasury cash, so a bank loan
that covered a deficit showed up as revenue. It is now the change in the net
position (cash minus public debt); borrowing and repayment are reported on
their own lines (``govBorrowed``, ``govRepaid``).
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402


def _manager(cash, debt=0.0, borrowed=0.0, repaid=0.0):
    manager = server.SimulationManager(session_id="fiscal-balance")
    gov = SimpleNamespace(cash_balance=cash, public_debt=debt,
                          last_tick_debt_borrowed=borrowed, last_tick_debt_repaid=repaid)
    manager.economy = SimpleNamespace(government=gov)
    return manager, gov


def test_borrowing_is_not_revenue():
    manager, gov = _manager(cash=0.0, debt=100_000.0)
    manager._treasury_flow_this_tick()
    # A week with a $5,243 deficit that the bank lends: cash ends where it began.
    gov.public_debt += 5_243.0
    gov.last_tick_debt_borrowed = 5_243.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(-5_243.0)
    assert flow["borrowed"] == pytest.approx(5_243.0)
    assert flow["debt"] == pytest.approx(105_243.0)


def test_repayment_is_not_spending():
    manager, gov = _manager(cash=60_000.0, debt=100_000.0)
    manager._treasury_flow_this_tick()
    # A $2,000 surplus week; $50,000 of cash repays debt.
    gov.cash_balance += 2_000.0 - 50_000.0
    gov.public_debt -= 50_000.0
    gov.last_tick_debt_borrowed, gov.last_tick_debt_repaid = 0.0, 50_000.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(2_000.0)
    assert flow["repaid"] == pytest.approx(50_000.0)


def test_without_debt_it_is_the_change_in_cash_as_before():
    manager, gov = _manager(cash=10_000.0)
    manager._treasury_flow_this_tick()
    gov.cash_balance = -4_000.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(-14_000.0)
    assert flow["debt"] == pytest.approx(4_000.0)  # unlent negative cash still counts as debt


def test_financing_lines_are_visible_only_with_public_debt():
    """Flag off and nothing owed: the frame carries no govBorrowed/govRepaid (main's frame)."""
    manager, gov = _manager(cash=10_000.0)
    manager.config.government.public_debt_enabled = False
    assert manager._treasury_flow_this_tick()["debt_visible"] is False

    manager.config.government.public_debt_enabled = True
    assert manager._treasury_flow_this_tick()["debt_visible"] is True

    # Debt still owed after the flag is switched off: keep showing its financing.
    manager.config.government.public_debt_enabled = False
    gov.public_debt = 1_000.0
    assert manager._treasury_flow_this_tick()["debt_visible"] is True
