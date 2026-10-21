"""Profit-tax schedule (round 3).

The default is a UK-style small rate and main rate with marginal relief.
``legacy_cash_rank`` keeps main's cash-ranked bands. The old percentile-of-profit
bracket tests that used to live here are replaced by these.
"""

import contextlib
import hashlib
import io
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from agents import FirmAgent, GovernmentAgent
from config import CONFIG, clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy


def _style(monkeypatch, style="progressive"):
    monkeypatch.setattr(CONFIG.government, "profit_tax_style", style)


def _firms(profits):
    return [{"firm_id": i + 1, "profit_before_tax": p} for i, p in enumerate(profits)]


def test_small_rate_below_the_anchor_and_main_rate_above_it(monkeypatch):
    _style(monkeypatch)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    # Seven profits. Median is 400, so L=400 and U=2000. S = 0.76 * 0.20.
    profits = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 5000.0]
    taxes = gov.plan_taxes([], _firms(profits))["profit_taxes"]
    assert gov.last_profit_tax_anchor == pytest.approx(400.0)
    assert gov.last_profit_tax_upper == pytest.approx(2000.0)
    assert taxes[1] == pytest.approx(100.0 * 0.152)  # below L
    assert taxes[4] == pytest.approx(400.0 * 0.152)  # at L
    assert taxes[7] == pytest.approx(5000.0 * 0.20)  # above U
    # Inside the band: F = (0.20-0.152)*400/1600 = 0.012, rate(800) = 0.182.
    rate_800 = gov._marginal_relief_rate(800.0, 400.0, 2000.0, 0.152, 0.20)
    assert rate_800 == pytest.approx(0.182)
    assert gov._marginal_relief_rate(2000.0, 400.0, 2000.0, 0.152, 0.20) == pytest.approx(0.20)


def test_marginal_relief_is_continuous_at_the_thresholds():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.25)
    small, main, lower, upper = 0.19, 0.25, 100.0, 500.0
    at_lower = gov._marginal_relief_rate(lower, lower, upper, small, main)
    at_upper = gov._marginal_relief_rate(upper, lower, upper, small, main)
    assert at_lower == pytest.approx(small)
    assert at_upper == pytest.approx(main)
    just_above = gov._marginal_relief_rate(lower + 1e-6, lower, upper, small, main)
    just_below = gov._marginal_relief_rate(upper - 1e-6, lower, upper, small, main)
    assert just_above == pytest.approx(small, abs=1e-6)
    assert just_below == pytest.approx(main, abs=1e-6)


def test_after_tax_profit_rises_with_pre_tax_profit(monkeypatch):
    _style(monkeypatch)
    rng = random.Random(0)
    profits = [rng.uniform(0.01, 10_000.0) for _ in range(80)]
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _firms(profits))["profit_taxes"]
    ordered = sorted(zip(profits, (taxes[i + 1] for i in range(len(profits)))))
    after = [p - t for p, t in ordered]
    assert all(after[i] <= after[i + 1] + 1e-8 for i in range(len(after) - 1))
    rates = [t / p for p, t in ordered]
    small = 0.76 * 0.20
    assert all(small - 1e-12 <= r <= 0.20 + 1e-12 for r in rates)


def test_no_anchor_charges_the_main_rate(monkeypatch):
    _style(monkeypatch)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    # Fewer than four distinct profitable firms: both pay M, not the small rate.
    taxes = gov.plan_taxes([], _firms([10.0, 10_000.0, -5.0]))["profit_taxes"]
    assert taxes[1] == pytest.approx(2.0)
    assert taxes[2] == pytest.approx(2_000.0)
    assert taxes[3] == 0.0
    assert gov.last_profit_tax_anchor == 0.0

    empty = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    losses = empty.plan_taxes([], _firms([-1.0, 0.0, -3.0]))["profit_taxes"]
    assert losses == {1: 0.0, 2: 0.0, 3: 0.0}
    assert empty.last_profit_tax_anchor == 0.0


def test_nonpositive_anchor_falls_back_to_the_main_rate(monkeypatch):
    _style(monkeypatch)
    monkeypatch.setattr("agents.statistics.median", lambda _values: 0.0)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    taxes = gov.plan_taxes([], _firms([100.0, 200.0, 300.0, 400.0]))["profit_taxes"]
    assert taxes[1] == pytest.approx(20.0)
    assert gov.last_profit_tax_anchor == 0.0


def test_nonfinite_profit_is_excluded_and_owes_nothing(monkeypatch):
    _style(monkeypatch)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    firms = _firms([100.0, 200.0, 300.0, 400.0, 500.0, 600.0])
    firms.append({"firm_id": 99, "profit_before_tax": float("nan")})
    firms.append({"firm_id": 100, "profit_before_tax": float("inf")})
    taxes = gov.plan_taxes([], firms)["profit_taxes"]
    assert taxes[99] == 0.0
    assert taxes[100] == 0.0
    assert gov.last_profit_tax_nonfinite_excluded == 2
    # Median of the six finite profits is 350, so the nan firm did not move it.
    assert gov.last_profit_tax_anchor == pytest.approx(350.0)


def test_rate_is_clamped_to_the_small_and_main_rates():
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    # small above main: at the lower threshold the raw rate is S, which is
    # above M, and the clamp returns M. Just inside the band the raw rate
    # dips under S, and the clamp lifts it back to S.
    assert gov._marginal_relief_rate(100.0, 100.0, 500.0, 0.30, 0.10) == pytest.approx(0.10)
    assert gov._marginal_relief_rate(100.1, 100.0, 500.0, 0.30, 0.10) == pytest.approx(0.30)
    inside = gov._marginal_relief_rate(250.0, 100.0, 500.0, 0.152, 0.20)
    assert 0.152 <= inside <= 0.20


def test_lever_zero_charges_nothing(monkeypatch):
    _style(monkeypatch)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.0)
    taxes = gov.plan_taxes([], _firms([10.0, 100.0, 1_000.0, 10_000.0]))["profit_taxes"]
    assert all(amount == 0.0 for amount in taxes.values())


def test_average_rate_does_not_depend_on_firm_count(monkeypatch):
    """The same profit list, once and repeated, keeps the same average rate.

    The old percentile bands changed the average between a 400-household and a
    1,000-household firm count. Scale thresholds do not.
    """
    _style(monkeypatch)
    base = [10.0, 25.0, 40.0, 80.0, 150.0, 400.0, 900.0, 2_000.0]

    def average(profits):
        gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
        taxes = gov.plan_taxes([], _firms(profits))["profit_taxes"]
        return sum(taxes.values()) / sum(profits)

    assert average(base) == pytest.approx(average(base * 8), abs=0.01)


def test_anchor_window_drops_profits_older_than_13_weeks(monkeypatch):
    _style(monkeypatch)
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    wide = [10.0, 20.0, 30.0, 40.0, 50.0, 10_000.0]
    tight = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    gov.plan_taxes([], _firms(wide))
    assert gov.last_profit_tax_anchor == pytest.approx(35.0)
    for _ in range(13):
        gov.plan_taxes([], _firms(tight))
    # The opening week has fallen out of the 13-week window.
    assert gov.last_profit_tax_anchor == pytest.approx(100.0)
    assert len(gov.profit_tax_profit_window) == 13


def test_unknown_profit_tax_style_raises(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "profit_tax_style", "brackets")
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    with pytest.raises(ValueError, match="profit_tax_style"):
        gov.plan_taxes([], _firms([100.0]))


def test_pricing_uses_the_firms_effective_rate_and_falls_back(monkeypatch):
    monkeypatch.setattr(CONFIG.firms, "price_on_effective_profit_tax", True)
    firm = FirmAgent(
        firm_id=1, good_name="Food", cash_balance=1_000.0, inventory_units=10.0,
        good_category="Food",
    )
    # No record yet: the lever.
    assert firm._gross_up_profit_tax_rate(0.20) == pytest.approx(0.20)
    firm.record_effective_profit_tax(100.0, 15.2, 0.20, update_pricing_rate=True)
    assert firm.pricing_profit_tax_rate == pytest.approx(0.152)
    assert firm._gross_up_profit_tax_rate(0.20) == pytest.approx(0.152)
    # A loss week keeps the last valid rate.
    firm.record_effective_profit_tax(0.0, 0.0, 0.20, update_pricing_rate=True)
    assert firm.pricing_profit_tax_rate == pytest.approx(0.152)
    assert firm.last_taxable_profit == 0.0
    # Zero tax on a positive profit records 0.
    firm.record_effective_profit_tax(80.0, 0.0, 0.20, update_pricing_rate=True)
    assert firm.pricing_profit_tax_rate == 0.0
    # Above the cap, the stored rate is 0.60.
    firm.record_effective_profit_tax(100.0, 90.0, 0.20, update_pricing_rate=True)
    assert firm.pricing_profit_tax_rate == pytest.approx(0.60)
    # A non-finite tax falls back and is counted.
    before = firm.pricing_rate_nonfinite_count
    firm.pricing_profit_tax_rate_known = False
    firm.record_effective_profit_tax(100.0, float("nan"), 0.18, update_pricing_rate=True)
    assert firm.pricing_rate_nonfinite_count == before + 1
    assert firm._gross_up_profit_tax_rate(0.18) == pytest.approx(0.18)


def test_headline_pricing_ignores_the_effective_rate(monkeypatch):
    monkeypatch.setattr(CONFIG.firms, "price_on_effective_profit_tax", False)
    firm = FirmAgent(
        firm_id=1, good_name="Food", cash_balance=1_000.0, inventory_units=10.0,
        good_category="Food",
    )
    firm.record_effective_profit_tax(100.0, 40.0, 0.20, update_pricing_rate=False)
    assert firm.last_profit_tax_paid == pytest.approx(40.0)
    assert firm._gross_up_profit_tax_rate(0.20) == pytest.approx(0.20)


def test_legacy_cash_rank_effective_rate_differs_from_the_lever(monkeypatch):
    """Under the cash-ranked bands the effective rate is not the lever, so the
    pricing switch changes prices. The identity arm turns both off."""
    _style(monkeypatch, "legacy_cash_rank")
    gov = GovernmentAgent(cash_balance=0.0, profit_tax_rate=0.20)
    firms = [
        {"firm_id": i, "profit_before_tax": 100.0, "cash_balance": float(i)}
        for i in range(1, 21)
    ]
    taxes = gov.plan_taxes([], firms)["profit_taxes"]
    rates = {i: taxes[i] / 100.0 for i in taxes}
    assert max(rates.values()) > 0.20 + 1e-9
    assert min(rates.values()) < 0.20 - 1e-9


def _run_hash(sequence, style, price_on_effective, households, firms_per_category, ticks, lever=0.20):
    seed = 42
    with use_config(clone_config()), contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        CONFIG.payment_sequence = sequence
        CONFIG.government.profit_tax_style = style
        CONFIG.firms.price_on_effective_profit_tax = price_on_effective
        economy = create_large_economy(households, firms_per_category)
        economy.government.profit_tax_rate = lever
        economy.configure_stabilizers(households=True, firms=True, government=True)
        hasher = hashlib.sha256()
        for _ in range(ticks):
            economy.step()
            token = {
                "gov": economy.government.cash_balance,
                "profit_tax": float(economy.last_tick_gov_profit_taxes),
                "firms": [
                    (f.firm_id, f.cash_balance, f.price, len(f.employees), f.inventory_units)
                    for f in economy.firms
                ],
                "households": [
                    (h.household_id, h.cash_balance, int(h.employer_id or 0))
                    for h in economy.households
                ],
            }
            hasher.update(json.dumps(token, sort_keys=True).encode())
    return hasher.hexdigest()


def test_flat_effective_pricing_matches_flat_headline_pricing():
    """Under flat, the effective rate equals the lever whenever profit > 0."""
    left = _run_hash("income_first", "flat", True, 80, 3, 15)
    right = _run_hash("income_first", "flat", False, 80, 3, 15)
    assert left == right


def test_legacy_cash_rank_hash_repeats_on_every_sequence():
    """Hash 60 ticks, 200 households, 5 firms per category, all 3 sequences.

    Two back-to-back runs with ``legacy_cash_rank`` and headline pricing must
    match. A stored hash of main does not travel across machines (the same
    seed diverges across BLAS builds), so equality with main is the evidence
    panel's paired off-vs-main fingerprints, taken on one machine.
    """
    env = os.environ.copy()
    env.update({
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "backend"),
    })
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "repeat"],
        env=env, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr[-800:] + completed.stdout[-800:]
    lines = [line for line in completed.stdout.splitlines() if line.startswith("HASH ")]
    assert [line.split()[1] for line in lines] == ["income_first", "income_late", "legacy"]


if __name__ == "__main__":
    # ``repeat`` hashes each sequence twice under legacy_cash_rank and headline pricing.
    os.chdir(Path(__file__).resolve().parents[2])
    if sys.argv[1] != "repeat":
        raise SystemExit("usage: test_profit_tax_brackets.py repeat")
    for sequence in ("income_first", "income_late", "legacy"):
        first = _run_hash(sequence, "legacy_cash_rank", False, 200, 5, 60)
        second = _run_hash(sequence, "legacy_cash_rank", False, 200, 5, 60)
        if first != second:
            raise SystemExit(f"mismatch {sequence}")
        print(f"HASH {sequence} {first}")
