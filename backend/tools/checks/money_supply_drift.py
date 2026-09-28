"""Per-tick money-supply drift diagnostic (read-only).

Builds the same seeded economy as ``tools/benchmarks/regression_snapshot.py``
(``create_large_economy`` plus Python/NumPy/CONFIG seeding), steps it, and
prints the total money stock after every tick. The total is
``tests_contracts.conftest.total_money_with_bank``: household, firm,
queued-firm and government cash, the misc-firm revenue pool, and bank cash
reserves (household deposits are already inside reserves).

A conserving economy prints deltas of zero. Nonzero deltas measure the
money created or destroyed on that tick by leaks such as those listed in
``docs/reviews/2026-09-28-agents-economy-code-audit.md`` section A.

    python -m backend.tools.checks.money_supply_drift \
        --households 1500 --ticks 120 --seed 42
"""

from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG
from tests_contracts.conftest import total_money_with_bank
from tools.runners.run_large_simulation import create_large_economy

TOP_DELTAS = 5


def _set_seed(seed: int) -> None:
    # Same seeding as regression_snapshot._set_seed.
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = int(seed)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Per-tick money-supply drift diagnostic.")
    p.add_argument("--households", type=int, default=1500)
    p.add_argument("--ticks", type=int, default=120)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--firms-per-category", type=int, default=10)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    _set_seed(args.seed)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(args.households, args.firms_per_category)

    initial = float(total_money_with_bank(economy))
    previous = initial
    deltas: list[tuple[int, float]] = []
    print(f"payment_sequence={economy.payment_sequence} households={args.households} "
          f"firms_per_category={args.firms_per_category} seed={args.seed} ticks={args.ticks}")
    print(f"tick 0 total={initial:.6f}")
    print("tick,total_money_with_bank,delta,cumulative_delta")
    for _ in range(args.ticks):
        economy.step()
        total = float(total_money_with_bank(economy))
        tick = int(economy.current_tick)
        delta = total - previous
        deltas.append((tick, delta))
        print(f"{tick},{total:.6f},{delta:+.6f},{total - initial:+.6f}")
        previous = total

    final = previous
    cumulative = final - initial
    nonzero = sum(1 for _, d in deltas if abs(d) > 1e-6)
    gross = sum(abs(d) for _, d in deltas)
    pct = (cumulative / initial * 100.0) if initial else 0.0
    print(
        f"SUMMARY initial={initial:.2f} final={final:.2f} cumulative_delta={cumulative:+.2f} "
        f"({pct:+.3f}% of initial) gross_abs_delta={gross:.2f} "
        f"nonzero_ticks={nonzero}/{len(deltas)}"
    )
    largest = sorted(deltas, key=lambda item: abs(item[1]), reverse=True)[:TOP_DELTAS]
    print("LARGEST " + "; ".join(f"tick {t}: {d:+.2f}" for t, d in largest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
