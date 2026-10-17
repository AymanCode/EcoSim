"""Seeded before/after metrics for business-behavior changes.

Runs one fixed-seed economy built by ``create_large_economy`` and prints the
aggregates that the round-1 business changes are judged on: unemployment,
mean wage, price-change frequency, inflation, firm exits, output and mean
happiness. Only public economy and agent attributes are read, so the same
script also runs against an older checkout of ``backend/`` (pass
``--backend``) to produce the "before" column.

Examples (from the repository root)::

    # after: this checkout
    python backend/tools/benchmarks/business_ab_metrics.py --seed 42

    # before: a worktree of main, same script
    git worktree add /tmp/ecosim-main origin/main
    python backend/tools/benchmarks/business_ab_metrics.py --seed 42 \
        --backend /tmp/ecosim-main/backend

    # toggle a config flag (dotted path under CONFIG)
    python backend/tools/benchmarks/business_ab_metrics.py --seed 42 \
        --set firms.sticky_prices_enabled=true

Metrics are averaged over the ticks after ``--burn-in`` so start-up
transients do not dominate. Output is one JSON object on stdout.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any

DEFAULT_BACKEND = Path(__file__).resolve().parents[2]

# A price move smaller than this is treated as "no change" when counting
# repricing events, so float noise from cost recomputation is not counted.
PRICE_CHANGE_EPS = 1e-3


def _parse_override(text: str) -> tuple[list[str], Any]:
    """Split ``section.key=value`` into a path and a JSON-or-string value."""
    path, _, raw = text.partition("=")
    if not path or not _:
        raise argparse.ArgumentTypeError(f"expected section.key=value, got {text!r}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    return path.split("."), value


def _apply_override(config: Any, path: list[str], value: Any) -> None:
    target = config
    for part in path[:-1]:
        target = getattr(target, part)
    if not hasattr(target, path[-1]):
        raise SystemExit(f"unknown config key: {'.'.join(path)}")
    setattr(target, path[-1], value)


def run(backend: Path, households: int, firms_per_category: int, seed: int,
        ticks: int, burn_in: int, overrides: list[tuple[list[str], Any]]) -> dict:
    """Run one seeded economy and return the summary metrics.

    Args:
        backend: directory containing ``economy.py`` and ``config.py``.
        households: number of household agents.
        firms_per_category: private firms per essential category.
        seed: seed for ``random``, ``numpy.random`` and ``CONFIG.random_seed``.
        ticks: total ticks to run (1 tick = 1 week).
        burn_in: ticks excluded from the averaged metrics.
        overrides: config assignments applied before the economy is built.

    Returns:
        A JSON-serializable dict of metrics; see the keys below.
    """
    sys.path.insert(0, str(backend))
    import numpy as np
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    rows: list[dict] = []
    price_events = 0
    price_obs = 0
    exits = 0
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        for path, value in overrides:
            _apply_override(CONFIG, path, value)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms_per_category)
            prev_prices = {f.firm_id: float(f.price) for f in economy.firms}
            for _ in range(ticks):
                economy.step()
                tick = int(economy.current_tick)
                current = {f.firm_id: f for f in economy.firms}
                if tick > burn_in:
                    exits += sum(1 for fid in prev_prices if fid not in current)
                    for fid, firm in current.items():
                        if firm.is_baseline or fid not in prev_prices:
                            continue
                        price_obs += 1
                        old = prev_prices[fid]
                        if abs(float(firm.price) - old) > PRICE_CHANGE_EPS * max(old, 1e-9):
                            price_events += 1
                prev_prices = {fid: float(f.price) for fid, f in current.items()}
                m = economy.get_economic_metrics()
                m["_tick"] = tick
                rows.append(m)
    sys.path.remove(str(backend))

    window = [r for r in rows if r["_tick"] > burn_in]
    if len(window) < 2:
        raise SystemExit("need at least two ticks after burn-in")

    def avg(key: str) -> float:
        return float(mean(float(r.get(key, 0.0) or 0.0) for r in window))

    p0 = float(window[0].get("mean_price", 0.0) or 0.0)
    p1 = float(window[-1].get("mean_price", 0.0) or 0.0)
    weeks = window[-1]["_tick"] - window[0]["_tick"]
    weekly = [
        float(b["mean_price"]) / float(a["mean_price"]) - 1.0
        for a, b in zip(window, window[1:])
        if float(a.get("mean_price", 0.0) or 0.0) > 0
    ]
    return {
        "seed": seed, "households": households, "firms_per_category": firms_per_category,
        "ticks": ticks, "burn_in": burn_in,
        "overrides": {".".join(p): v for p, v in overrides},
        "unemployment_rate_mean": avg("unemployment_rate"),
        "mean_wage_mean": avg("mean_wage"),
        "mean_price_start": p0,
        "mean_price_end": p1,
        "inflation_annualized": (p1 / p0) ** (52.0 / weeks) - 1.0 if p0 > 0 and weeks > 0 else 0.0,
        "weekly_price_change_median_abs": float(median(abs(x) for x in weekly)) if weekly else 0.0,
        "private_price_change_share": price_events / price_obs if price_obs else 0.0,
        "firm_exits": exits,
        "firms_end": int(window[-1].get("total_firms", 0) or 0),
        "gdp_per_tick_mean": avg("gdp_this_tick"),
        "mean_happiness_mean": avg("mean_happiness"),
        "mean_health_mean": avg("mean_health"),
        "government_cash_end": float(window[-1].get("government_cash", 0.0) or 0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", type=Path, default=DEFAULT_BACKEND,
                        help="backend/ directory to import (default: this checkout)")
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=156)
    parser.add_argument("--burn-in", type=int, default=26)
    parser.add_argument("--set", dest="overrides", type=_parse_override, action="append", default=[],
                        help="config override section.key=value (repeatable; value parsed as JSON)")
    args = parser.parse_args()
    result = run(args.backend.resolve(), args.households, args.firms_per_category, args.seed,
                 args.ticks, args.burn_in, args.overrides)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
