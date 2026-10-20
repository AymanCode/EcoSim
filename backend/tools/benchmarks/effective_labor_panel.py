"""Paired window panel for effective labour, including long unemployment spells.

One process, one seed, one arm. Point --backend at a checkout to measure that
tree. The spell definition lives in this repo's worker_effectiveness module so
both arms are scored the same way.

    python3 backend/tools/benchmarks/effective_labor_panel.py --seed 42 --flag
    python3 backend/tools/benchmarks/effective_labor_panel.py --aggregate /tmp/panel
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import time
from pathlib import Path


WINDOWS = (("1-100", 1, 100), ("101-200", 101, 200), ("201+", 201, None))


def _spell_snapshot():
    path = Path(__file__).resolve().parents[2] / "worker_effectiveness.py"
    name = "effective_labor_spell_measure"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.spell_snapshot


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms", type=int, default=5)
    parser.add_argument("--flag", action="store_true")
    parser.add_argument("--hash", action="store_true")
    parser.add_argument("--payment-sequence", default="legacy")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--set", action="append", default=[], dest="overrides")
    parser.add_argument("--aggregate", type=Path, default=None)
    return parser.parse_args()


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return float(ordered[low] * (1.0 - frac) + ordered[high] * frac)


def _record(economy, spell_snapshot) -> dict:
    metrics = economy.get_economic_metrics()
    households = economy.households
    liquid = [h.cash_balance + max(0.0, h.bank_deposit) for h in households]
    count = len(households) or 1
    poverty = sum(1 for value in liquid if value < 200.0) / count
    extreme = sum(1 for value in liquid if value < 100.0) / count
    food_ok = sum(
        1 for h in households if h.food_consumed_this_tick >= h.min_food_per_tick
    ) / count
    food_units = 0.0
    services_units = 0.0
    private_profit = 0.0
    visits = 0.0
    for firm in economy.firms:
        category = (firm.good_category or "").lower()
        if category == "food":
            food_units += float(firm.last_units_produced)
        elif category == "services":
            services_units += float(firm.last_units_produced)
        if not firm.is_baseline:
            private_profit += float(firm.last_profit)
        visits += float(getattr(firm, "healthcare_completed_visits_last_tick", 0.0) or 0.0)
    cpi = float(economy.consumer_prices.level)
    weekly = economy.consumer_prices.weekly_rate
    bank = float(economy.bank.cash_reserves) if economy.bank is not None else 0.0
    money = (
        sum(h.cash_balance for h in households)
        + sum(f.cash_balance for f in economy.firms)
        + float(economy.government.cash_balance)
        + bank
    )
    row = {
        "tick": int(economy.current_tick),
        "gdp": float(metrics.get("gdp_this_tick", 0.0) or 0.0),
        "unemployment": float(metrics.get("unemployment_rate", 0.0) or 0.0),
        "cpi": cpi,
        "cpi_change": 0.0 if weekly is None else float(weekly),
        "mean_price": float(metrics.get("mean_price", 0.0) or 0.0),
        "mean_wage": float(metrics.get("mean_wage", 0.0) or 0.0),
        "gov_cash": float(economy.government.cash_balance),
        "gov_revenue": float(getattr(economy.government, "last_tick_revenue", 0.0) or 0.0),
        "private_profit": private_profit,
        "poverty": poverty,
        "extreme_poverty": extreme,
        "food_sufficiency": food_ok,
        "liquid_p10": _percentile(liquid, 0.10),
        "liquid_p50": _percentile(liquid, 0.50),
        "liquid_p90": _percentile(liquid, 0.90),
        "happiness": float(metrics.get("mean_happiness", 0.0) or 0.0),
        "food_units": food_units,
        "services_units": services_units,
        "healthcare_visits": visits,
        "real_gdp": float(metrics.get("gdp_this_tick", 0.0) or 0.0) / (cpi / 100.0 if cpi else 1.0),
        "real_wage": float(metrics.get("mean_wage", 0.0) or 0.0) / (cpi / 100.0 if cpi else 1.0),
        "money": money,
    }
    row.update(spell_snapshot(households, int(economy.current_tick)))
    return row


def _run(args: argparse.Namespace) -> dict:
    backend = args.backend.resolve() if args.backend is not None else Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend))
    from config import CONFIG, clone_config, use_config
    from tools.benchmarks.regression_snapshot import ROUND_DECIMALS, _set_seed, snapshot_economy
    from tools.runners.run_large_simulation import create_large_economy

    spell_snapshot = _spell_snapshot()
    rows = []
    hashes = []
    started = time.perf_counter()
    with use_config(clone_config()):
        _set_seed(args.seed)
        if args.payment_sequence != "legacy":
            CONFIG.payment_sequence = args.payment_sequence
        if args.flag:
            if not hasattr(CONFIG.firms, "effective_labor_enabled"):
                raise SystemExit("this backend has no effective_labor_enabled flag")
            CONFIG.firms.effective_labor_enabled = True
        for item in args.overrides:
            name, raw = item.split("=", 1)
            current = getattr(CONFIG.firms, name)
            value: object
            if isinstance(current, bool):
                value = raw.lower() in {"1", "true", "yes"}
            else:
                value = float(raw)
            setattr(CONFIG.firms, name, value)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(args.households, args.firms)
            for _ in range(args.ticks):
                economy.step()
                rows.append(_record(economy, spell_snapshot))
                if args.hash:
                    payload = json.dumps(snapshot_economy(economy, ROUND_DECIMALS), sort_keys=True)
                    hashes.append(hashlib.sha256(payload.encode()).hexdigest())
    elapsed = time.perf_counter() - started
    return {
        "seed": args.seed,
        "ticks": args.ticks,
        "flag": bool(args.flag),
        "payment_sequence": args.payment_sequence,
        "overrides": list(args.overrides),
        "seconds": elapsed,
        "rows": rows,
        "hashes": hashes,
    }


def _window_rows(rows: list[dict], start: int, end: int | None) -> list[dict]:
    chosen = []
    for row in rows:
        tick = int(row["tick"])
        if tick < start:
            continue
        if end is not None and tick > end:
            continue
        chosen.append(row)
    return chosen


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    import numpy as np
    return float(np.std(np.asarray(values, dtype=float), ddof=0))


def _detrended_std(values: list[float]) -> float:
    import numpy as np
    if len(values) < 3:
        return 0.0
    y = np.asarray(values, dtype=float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    return float(np.std(resid, ddof=0))


def _annualized(start: float, end: float, n: int) -> float | None:
    if n <= 0 or start <= 0.0 or end <= 0.0:
        return None
    return float((end / start) ** (52.0 / n) - 1.0)


def _arm_window(rows: list[dict]) -> dict:
    if not rows:
        return {}
    keys = [k for k in rows[0] if k != "tick"]
    out = {"n": len(rows)}
    for key in keys:
        series = [float(row[key]) for row in rows]
        mean = _mean(series)
        std = _std(series)
        out[key] = {
            "mean": mean,
            "end": series[-1],
            "min": min(series),
            "std": std,
            "cv": (std / mean) if mean else 0.0,
            "detrended_std": _detrended_std(series),
        }
    out["cpi_inflation"] = _annualized(float(rows[0]["cpi"]), float(rows[-1]["cpi"]), len(rows))
    out["mean_price_inflation"] = _annualized(
        float(rows[0]["mean_price"]), float(rows[-1]["mean_price"]), len(rows),
    )
    out["gov_cash_negative_weeks"] = sum(1 for row in rows if float(row["gov_cash"]) < 0.0)
    out["gov_cash_below_5k_weeks"] = sum(1 for row in rows if float(row["gov_cash"]) < 5_000.0)
    return out


def _sign(delta: float) -> str:
    if delta > 1e-9:
        return "+"
    if delta < -1e-9:
        return "-"
    return "0"


def _aggregate(directory: Path) -> None:
    files = sorted(directory.glob("*.json"))
    by_seed: dict[int, dict[str, dict]] = {}
    for path in files:
        payload = json.loads(path.read_text())
        if payload.get("overrides") or payload.get("payment_sequence", "legacy") != "legacy":
            continue
        arm = "on" if payload.get("flag") else "off"
        by_seed.setdefault(int(payload["seed"]), {})[arm] = payload
    paired = {seed: arms for seed, arms in sorted(by_seed.items()) if "on" in arms and "off" in arms}
    report = {"seeds": sorted(paired), "windows": {}}
    level_keys = (
        "gdp", "real_gdp", "unemployment", "cpi", "mean_price", "mean_wage", "real_wage",
        "gov_cash", "gov_revenue", "private_profit", "poverty", "extreme_poverty",
        "food_sufficiency", "liquid_p10", "liquid_p50", "liquid_p90", "happiness",
        "food_units", "services_units", "healthcare_visits",
        "unemp_gt26", "unemp_gt52", "median_spell", "never_rehired_n", "never_rehired_skill",
    )
    for name, start, end in WINDOWS:
        window_report = {"metrics": {}}
        per_seed = []
        for seed, arms in paired.items():
            off_rows = _window_rows(arms["off"]["rows"], start, end)
            on_rows = _window_rows(arms["on"]["rows"], start, end)
            per_seed.append((seed, _arm_window(off_rows), _arm_window(on_rows)))
        for key in level_keys:
            deltas = []
            std_deltas = []
            det_deltas = []
            for _seed, off, on in per_seed:
                if key not in off or key not in on:
                    continue
                deltas.append(on[key]["mean"] - off[key]["mean"])
                std_deltas.append(on[key]["std"] - off[key]["std"])
                det_deltas.append(on[key]["detrended_std"] - off[key]["detrended_std"])
            window_report["metrics"][key] = {
                "off_mean": _mean([off[key]["mean"] for _s, off, _on in per_seed]),
                "on_mean": _mean([on[key]["mean"] for _s, _off, on in per_seed]),
                "delta_mean": _mean(deltas),
                "delta_min": min(deltas) if deltas else None,
                "delta_max": max(deltas) if deltas else None,
                "signs": "".join(_sign(d) for d in deltas),
                "std_delta_mean": _mean(std_deltas),
                "detrended_std_delta_mean": _mean(det_deltas),
            }
        for label, field in (
            ("unemployment_end", "unemployment"),
            ("gov_cash_min", "gov_cash"),
        ):
            deltas = []
            which = "end" if label == "unemployment_end" else "min"
            for _seed, off, on in per_seed:
                deltas.append(on[field][which] - off[field][which])
            window_report[label] = {
                "off": _mean([off[field][which] for _s, off, _on in per_seed]),
                "on": _mean([on[field][which] for _s, _off, on in per_seed]),
                "delta_mean": _mean(deltas),
                "delta_min": min(deltas) if deltas else None,
                "delta_max": max(deltas) if deltas else None,
                "signs": "".join(_sign(d) for d in deltas),
            }
        for label in ("cpi_inflation", "mean_price_inflation", "gov_cash_negative_weeks", "gov_cash_below_5k_weeks"):
            deltas = [on[label] - off[label] for _s, off, on in per_seed if off.get(label) is not None and on.get(label) is not None]
            offs = [off[label] for _s, off, _on in per_seed if off.get(label) is not None]
            ons = [on[label] for _s, _off, on in per_seed if on.get(label) is not None]
            window_report[label] = {
                "off": _mean(offs),
                "on": _mean(ons),
                "delta_mean": _mean(deltas),
                "delta_min": min(deltas) if deltas else None,
                "delta_max": max(deltas) if deltas else None,
                "signs": "".join(_sign(d) for d in deltas),
            }
        report["windows"][name] = window_report
    text = json.dumps(report, indent=2)
    print(text)
    (directory / "aggregate.json").write_text(text)


def main() -> None:
    args = _parse()
    if args.aggregate is not None:
        _aggregate(args.aggregate)
        return
    payload = _run(args)
    text = json.dumps(payload)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
