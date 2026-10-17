"""Seeded before/after study for sticky prices (round 1 PR4a).

Runs one fixed-seed ``create_large_economy`` economy and prints, as JSON,
the economy-wide outcomes (unemployment, mean wage, GDP, inflation, firm
exits, treasury) and, per category of private firm, how prices behave:
share of firm-weeks with a posted price change, mean weeks between changes,
mean absolute size of a change, and (when sticky prices are on) mean gap
between posted and shadow price and the share of reviews that came before
the firm's calm-market interval.

Only public attributes are read, so ``--backend`` can point at another
checkout (e.g. a main worktree) for the "before" column::

    python backend/tools/benchmarks/sticky_price_study.py --seed 42
    python backend/tools/benchmarks/sticky_price_study.py --seed 42 \\
        --set firms.sticky_prices_enabled=false
    python backend/tools/benchmarks/sticky_price_study.py --seed 42 \\
        --backend /tmp/ecosim-main/backend
    python backend/tools/benchmarks/sticky_price_study.py --seed 42 \\
        --set firms.price_review_gap_scale=0.05

Metrics are averaged over ticks after ``--burn-in`` (default 26).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_BACKEND = Path(__file__).resolve().parents[2]
# A relative move below this is float noise, not a price change.
PRICE_CHANGE_EPS = 1e-3


def _parse_override(text: str) -> tuple[list[str], Any]:
    """Split ``section.key=value``; the value is parsed as JSON when it can be."""
    path, sep, raw = text.partition("=")
    if not path or not sep:
        raise argparse.ArgumentTypeError(f"expected section.key=value, got {text!r}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    if isinstance(value, list):
        value = tuple(value)
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
    """Run one seeded economy and return the summary metrics."""
    sys.path.insert(0, str(backend))
    import numpy as np
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    rows: list[dict] = []
    per_cat: dict[str, dict[str, Any]] = {}
    exits = 0
    with use_config(clone_config()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = int(seed)
        for path, value in overrides:
            _apply_override(CONFIG, path, value)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(households, firms_per_category)
            prev = {f.firm_id: float(f.price) for f in economy.firms}
            last_change: dict[int, int] = {}
            last_review: dict[int, Any] = {}
            for _ in range(ticks):
                economy.step()
                tick = int(economy.current_tick)
                current = {f.firm_id: f for f in economy.firms}
                if tick > burn_in:
                    exits += sum(1 for fid in prev if fid not in current)
                for fid, firm in current.items():
                    if firm.is_baseline or fid not in prev:
                        continue
                    cat = (firm.good_category or "").lower()
                    stats = per_cat.setdefault(cat, {"obs": 0, "changes": 0, "durations": [], "sizes": [],
                                                     "gaps": [], "reviews": 0, "early": 0})
                    old = prev[fid]
                    changed = abs(float(firm.price) - old) > PRICE_CHANGE_EPS * max(old, 1e-9)
                    if tick > burn_in:
                        stats["obs"] += 1
                        if changed:
                            stats["changes"] += 1
                            stats["sizes"].append(abs(float(firm.price) / old - 1.0) if old > 0 else 0.0)
                            if fid in last_change:
                                stats["durations"].append(tick - last_change[fid])
                        shadow = getattr(firm, "price_shadow", None)
                        if shadow:
                            stats["gaps"].append(abs(float(firm.price) / float(shadow) - 1.0))
                        review = getattr(firm, "last_price_review_tick", None)
                        if review is not None and review != last_review.get(fid):
                            stats["reviews"] += 1
                            previous = last_review.get(fid)
                            if previous is not None and review - previous < firm.price_review_interval():
                                stats["early"] += 1
                    if changed:
                        last_change[fid] = tick
                    review = getattr(firm, "last_price_review_tick", None)
                    if review is not None:
                        last_review[fid] = review
                prev = {fid: float(f.price) for fid, f in current.items()}
                m = economy.get_economic_metrics()
                m["_tick"] = tick
                m["_cpi_annual"] = economy.consumer_prices.annual_rate
                for cat in ("food", "services"):
                    ps = [float(f.price) for f in economy.firms
                          if not f.is_baseline and (f.good_category or "").lower() == cat]
                    m[f"_private_{cat}_price"] = float(mean(ps)) if ps else 0.0
                # Real output: units sold this tick by category, baseline firms included.
                for cat in ("food", "services", "healthcare"):
                    m[f"_units_{cat}"] = float(sum(
                        float(getattr(f, "last_units_sold", 0.0) or 0.0) for f in economy.firms
                        if (f.good_category or "").lower() == cat))
                rows.append(m)
    sys.path.remove(str(backend))

    window = [r for r in rows if r["_tick"] > burn_in]

    def avg(key: str) -> float:
        return float(mean(float(r.get(key, 0.0) or 0.0) for r in window))

    cpi = [float(r["_cpi_annual"]) for r in window if r["_cpi_annual"] is not None]
    out: dict[str, Any] = {
        "seed": seed, "households": households, "ticks": ticks, "burn_in": burn_in,
        "overrides": {".".join(p): v for p, v in overrides},
        "unemployment_rate_mean": avg("unemployment_rate"),
        "mean_wage_mean": avg("mean_wage"),
        "gdp_per_tick_mean": avg("gdp_this_tick"),
        "cpi_annual_inflation_mean": float(mean(cpi)) if cpi else 0.0,
        "cpi_annual_inflation_max": float(max(cpi)) if cpi else 0.0,
        "firm_exits": exits,
        "government_cash_end": float(window[-1].get("government_cash", 0.0) or 0.0),
        "mean_happiness_mean": avg("mean_happiness"),
        "mean_health_mean": avg("mean_health"),
        "food_units_sold_per_tick": avg("_units_food"),
        "services_units_sold_per_tick": avg("_units_services"),
        "healthcare_units_sold_per_tick": avg("_units_healthcare"),
    }
    for cat, s in sorted(per_cat.items()):
        out[f"{cat}_price_change_share"] = s["changes"] / s["obs"] if s["obs"] else 0.0
        out[f"{cat}_weeks_between_changes_mean"] = float(mean(s["durations"])) if s["durations"] else 0.0
        out[f"{cat}_abs_change_size_mean"] = float(mean(s["sizes"])) if s["sizes"] else 0.0
        if s["gaps"]:
            out[f"{cat}_posted_vs_shadow_gap_mean"] = float(mean(s["gaps"]))
        if s["reviews"]:
            out[f"{cat}_reviews_per_firm_week"] = s["reviews"] / s["obs"]
            out[f"{cat}_early_review_share"] = s["early"] / s["reviews"]
    for cat in ("food", "services"):
        prices = [r[f"_private_{cat}_price"] for r in window]
        if prices and prices[0] > 0:
            out[f"{cat}_private_mean_price_start"] = prices[0]
            out[f"{cat}_private_mean_price_end"] = prices[-1]
    return out


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
                        help="config override section.key=value (repeatable; JSON value)")
    args = parser.parse_args()
    print(json.dumps(run(args.backend.resolve(), args.households, args.firms_per_category, args.seed,
                         args.ticks, args.burn_in, args.overrides), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
