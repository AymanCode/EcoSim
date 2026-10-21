"""Paired, seeded before/after runs for public debt (round 1 G1).

Every (scenario, arm, seed) runs in its own Python process, seeded with
``tools/benchmarks/regression_snapshot.py``'s ``_set_seed`` after the arm's
config is set, so no run inherits RNG or config state from another. Results
are reported by tick window (1-100, 101-200, 201+) with the window mean,
within-window volatility (std dev and CV of the weekly values) and the paired
difference against the baseline arm (mean and [min, max] over seeds).

Arms:
    main       a checkout of main (``--main-backend``), unmodified config.
    off        this branch with ``public_debt_enabled=False`` (the default);
               must equal ``main`` exactly (checked per seed).
    on_zero    debt on, borrow back to $0 of cash (``public_debt_borrow_target="zero"``).
    on_buffer  debt on, borrow back to the one-week working balance ("buffer").
    on_noint   decomposition only: ``on_zero`` with the weekly interest payment
               replaced by $0 in that process, to split the effect of interest
               from the effect of borrowing. Not a policy option.

Scenarios:
    default  levers as configured.
    stress   crisis benefits plus high infrastructure and technology spending
             until mid-run, then infrastructure and technology off.
    deep     the treasury starts with no cash; crisis benefits plus high
             infrastructure, technology and social spending for the whole run.

Workers run with ``PYTHONHASHSEED=0`` and ``OMP_NUM_THREADS=1``; the report
opens with the run environment (commit, Python, numpy, pandas, platform,
households, firms per category, ticks, seeds).

Usage (from backend/), app defaults of 1,000 households and 5 firms per category:
    python tools/benchmarks/run_public_debt_compare.py \\
        --main-backend /path/to/main/backend --households 1000 --firms-per-category 5 \\
        --ticks 312 --seeds 42 43 44 45 46 --scenarios default stress deep \\
        --arms main off on_zero on_buffer on_noint --out /tmp/g1_runs
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import platform
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("default", "stress", "deep")
ARMS = ("main", "off", "on_zero", "on_buffer", "on_noint")
WINDOWS = (("1-100", 0, 100), ("101-200", 100, 200), ("201+", 200, None))
DECILES = (10, 20, 30, 40, 50, 60, 70, 80, 90)


def _worker(backend: str, arm: str, seed: int, scenario: str, ticks: int, households: int, firms: int) -> Dict:
    """Run one arm/seed/scenario in this process and return per-tick rows."""
    sys.path.insert(0, backend)
    import numpy as np  # noqa: E402

    from config import CONFIG  # noqa: E402
    from tools.benchmarks.regression_snapshot import _set_seed  # noqa: E402
    from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

    if arm != "main":
        CONFIG.government.public_debt_enabled = arm.startswith("on_")
        if arm == "on_buffer":
            CONFIG.government.public_debt_borrow_target = "buffer"
    if arm == "on_noint":
        from agents import GovernmentAgent  # noqa: E402

        def _no_interest(self, bank, recent_gdp):
            self.last_tick_debt_interest = 0.0
            self.last_tick_debt_rate = 0.0
            return 0.0

        GovernmentAgent.pay_public_debt_interest = _no_interest
    _set_seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(households, firms)
    gov, bank = economy.government, economy.bank
    if scenario in ("stress", "deep"):
        gov.set_lever("benefit_level", "crisis")
        gov.set_lever("infrastructure_spending", "high")
        gov.set_lever("technology_spending", "high")
    if scenario == "deep":
        gov.set_lever("social_spending", "high")
        gov.cash_balance = 0.0
    poverty_line = float(CONFIG.households.poverty_threshold)

    rows: List[Dict[str, float]] = []
    prev_net = gov.cash_balance - float(getattr(gov, "public_debt", 0.0))
    for tick in range(ticks):
        if scenario == "stress" and tick == ticks // 2:
            gov.set_lever("infrastructure_spending", "none")
            gov.set_lever("technology_spending", "none")
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        m = economy.get_economic_metrics()
        hs = economy.households
        # Liquid wealth as in #32: cash + max(0, deposit).
        liquid = np.array([h.cash_balance + max(0.0, h.bank_deposit) for h in hs])
        debt = float(getattr(gov, "public_debt", 0.0))
        net = float(gov.cash_balance) - debt
        row = {
            "gdp": float(m["gdp_this_tick"]),
            # Real GDP: nominal GDP deflated by the mean price (tick-0 price level not rebased).
            "real_gdp": float(m["gdp_this_tick"]) / float(m["mean_price"]) if float(m["mean_price"]) > 0 else 0.0,
            "unemployment": float(m["unemployment_rate"]),
            "mean_price": float(m["mean_price"]),
            "gov_balance": float(gov.last_tick_revenue - gov.last_tick_spending),
            "net_change": net - prev_net,
            "gov_cash": float(gov.cash_balance),
            "net_position": net,
            "public_debt": debt,
            "interest": float(getattr(gov, "last_tick_debt_interest", 0.0)),
            "borrowed": float(getattr(gov, "last_tick_debt_borrowed", 0.0)),
            "negative_cash": float(gov.cash_balance < 0.0),
            "firm_profit": float(sum(f.last_profit for f in economy.firms)),
            "poverty_share": float(np.mean(liquid < poverty_line)),
            "food_sufficiency": float(np.mean([h.food_consumed_this_tick >= h.min_food_per_tick for h in hs])),
            "happiness": float(m["mean_happiness"]),
            "bank_reserves": float(bank.cash_reserves) if bank is not None else 0.0,
            "bank_equity": float(
                bank.cash_reserves + bank.total_loans_outstanding
                + float(getattr(bank, "public_debt_held", 0.0)) - bank.total_deposits
            ) if bank is not None else 0.0,
        }
        for d, v in zip(DECILES, np.percentile(liquid, DECILES)):
            row[f"liquid_p{d}"] = float(v)
        rows.append(row)
        prev_net = net
    return {"arm": arm, "seed": seed, "scenario": scenario, "rows": rows}


def _summarize(rows: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for name, lo, hi in WINDOWS:
        window = rows[lo:hi]
        if not window:
            continue
        stats: Dict[str, float] = {"ticks": float(len(window))}
        for key in window[0]:
            values = [r[key] for r in window]
            mean = statistics.fmean(values)
            sd = statistics.pstdev(values)
            stats[key] = mean
            stats[f"sd_{key}"] = sd
            stats[f"cv_{key}"] = sd / abs(mean) if abs(mean) > 1e-9 else 0.0
            stats[f"min_{key}"] = min(values)
            stats[f"end_{key}"] = values[-1]
        out[name] = stats
    return out


def _run_one(job) -> Dict:
    backend, arm, seed, scenario, args = job
    cmd = [
        sys.executable, str(Path(__file__).resolve()), "--worker", "--backend", backend, "--arm", arm,
        "--seed", str(seed), "--scenario", scenario, "--ticks", str(args.ticks),
        "--households", str(args.households), "--firms-per-category", str(args.firms_per_category),
    ]
    env = {**os.environ, "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1"}
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=backend, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{arm} seed {seed} {scenario} failed:\n{proc.stderr[-2000:]}")
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    rows = result.pop("rows")
    result["rows_sha256"] = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    result["windows"] = _summarize(rows)
    return result


PANEL = (
    ("gdp", "GDP / wk", "{:,.0f}"), ("real_gdp", "real GDP / wk (GDP / mean price)", "{:,.0f}"),
    ("unemployment", "unemployment", "{:.4f}"), ("mean_price", "mean price", "{:.3f}"),
    ("gov_balance", "gov balance (revenue - spending) / wk, mean", "{:,.0f}"),
    ("min_gov_balance", "gov balance / wk, min", "{:,.0f}"),
    ("net_position", "treasury net position (cash - debt), mean", "{:,.0f}"),
    ("min_net_position", "treasury net position, min", "{:,.0f}"),
    ("negative_cash", "share of weeks with cash < 0", "{:.3f}"),
    ("firm_profit", "firm profits / wk", "{:,.0f}"), ("poverty_share", "share in poverty (liquid < $200)", "{:.4f}"),
    ("food_sufficiency", "share eating minimum food", "{:.4f}"),
    *((f"liquid_p{d}", f"liquid wealth p{d}", "{:,.1f}") for d in DECILES),
    ("happiness", "happiness", "{:.4f}"),
    ("public_debt", "public debt, mean", "{:,.0f}"), ("end_public_debt", "public debt, window end", "{:,.0f}"),
    ("interest", "interest / wk", "{:,.1f}"), ("bank_reserves", "bank reserves", "{:,.0f}"),
    ("bank_equity", "bank equity (books incl. public debt)", "{:,.0f}"),
)
VOLATILITY = ("gdp", "real_gdp", "unemployment", "mean_price", "happiness", "gov_balance", "public_debt", "interest")


def _fmt_cell(fmt: str, values: List[float]) -> str:
    return fmt.format(statistics.fmean(values))


def _report(scenario: str, results: List[Dict], arms: List[str], seeds: List[int]) -> str:
    by = {(r["arm"], r["seed"]): r for r in results if r["scenario"] == scenario}
    base = "main" if "main" in arms else "off"
    others = [a for a in arms if a != base]
    lines = [f"## Scenario: {scenario}", ""]
    if "main" in arms and "off" in arms:
        same = [by[("main", s)]["rows_sha256"] == by[("off", s)]["rows_sha256"] for s in seeds]
        lines.append(f"Flag off vs main, per-tick rows sha256 identical: {sum(same)}/{len(seeds)} seeds "
                     f"({', '.join(str(s) for s, ok in zip(seeds, same) if not ok) or 'none differ'})")
        lines.append("")
    for name, _, _ in WINDOWS:
        ticks = int(by[(base, seeds[0])]["windows"][name]["ticks"])
        header = f"| metric | {base} |" + "".join(f" {a} | {a} - {base} [range] |" for a in others if a != "off")
        lines += [f"### Ticks {name} ({ticks} ticks)", "", header,
                  "|---|---|" + "---|---|" * len([a for a in others if a != "off"])]
        for key, label, fmt in PANEL:
            base_vals = [by[(base, s)]["windows"][name][key] for s in seeds]
            cells = [label, _fmt_cell(fmt, base_vals)]
            for arm in others:
                if arm == "off":
                    continue
                vals = [by[(arm, s)]["windows"][name][key] for s in seeds]
                diff = [v - b for v, b in zip(vals, base_vals)]
                cells += [_fmt_cell(fmt, vals),
                          f"{fmt.format(statistics.fmean(diff))} [{fmt.format(min(diff))}, {fmt.format(max(diff))}]"]
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", f"Volatility, ticks {name}: CV of weekly values (sd / |mean|), mean over seeds; "
                  f"paired CV difference vs {base} [range]", "",
                  f"| metric | {base} CV |" + "".join(f" {a} CV | diff [range] |" for a in others if a != "off"),
                  "|---|---|" + "---|---|" * len([a for a in others if a != "off"])]
        for key in VOLATILITY:
            base_vals = [by[(base, s)]["windows"][name][f"cv_{key}"] for s in seeds]
            cells = [key, f"{statistics.fmean(base_vals):.4f}"]
            for arm in others:
                if arm == "off":
                    continue
                vals = [by[(arm, s)]["windows"][name][f"cv_{key}"] for s in seeds]
                diff = [v - b for v, b in zip(vals, base_vals)]
                cells += [f"{statistics.fmean(vals):.4f}", f"{statistics.fmean(diff):+.4f} [{min(diff):+.4f}, {max(diff):+.4f}]"]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["### Debt trajectory by window (mean over seeds [min, max])", "",
              "| arm | window | debt at window end | debt change in window | interest / wk | gov balance / wk | weeks cash < 0 |",
              "|---|---|---|---|---|---|---|"]
    for arm in [a for a in arms if a != "off"]:
        for name, _, _ in WINDOWS:
            w = [by[(arm, s)]["windows"][name] for s in seeds]
            end = [x["end_public_debt"] for x in w]
            start_vals = []
            for s in seeds:
                ws = by[(arm, s)]["windows"]
                prev = {"1-100": None, "101-200": "1-100", "201+": "101-200"}[name]
                start_vals.append(ws[prev]["end_public_debt"] if prev else 0.0)
            change = [e - b for e, b in zip(end, start_vals)]
            lines.append(
                f"| {arm} | {name} | {statistics.fmean(end):,.0f} [{min(end):,.0f}, {max(end):,.0f}] | "
                f"{statistics.fmean(change):+,.0f} [{min(change):+,.0f}, {max(change):+,.0f}] | "
                f"{statistics.fmean(x['interest'] for x in w):,.1f} | {statistics.fmean(x['gov_balance'] for x in w):,.0f} | "
                f"{statistics.fmean(x['negative_cash'] for x in w):.3f} |"
            )
    lines.append("")
    return "\n".join(lines)


def _git_head(path: str) -> str:
    """Short commit of the checkout at ``path``, with ``-dirty`` if it has uncommitted changes."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=path, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                               text=True, cwd=path, check=True).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _run_env(args) -> List[str]:
    import numpy

    try:
        import pandas
        pandas_version = pandas.__version__
    except ImportError:
        pandas_version = "not installed"
    lines = ["## Run environment", "",
             f"- command: `python {' '.join(sys.argv)}`",
             f"- branch commit: `{_git_head(str(BACKEND_ROOT))}`"]
    if args.main_backend:
        lines.append(f"- main commit: `{_git_head(args.main_backend)}`")
    lines += [f"- Python {platform.python_version()}, numpy {numpy.__version__}, pandas {pandas_version}, "
              f"{platform.system()} {platform.machine()}",
              "- workers: one process per (scenario, arm, seed), PYTHONHASHSEED=0, OMP_NUM_THREADS=1, "
              "`_set_seed(seed)` after the arm's config",
              f"- {args.households} households, {args.firms_per_category} firms per category, {args.ticks} ticks, "
              f"seeds {' '.join(str(s) for s in args.seeds)}, arms {' '.join(args.arms)}", ""]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--backend", default=str(BACKEND_ROOT), help=argparse.SUPPRESS)
    parser.add_argument("--arm", default="off", help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=42, help=argparse.SUPPRESS)
    parser.add_argument("--scenario", default="default", help=argparse.SUPPRESS)
    parser.add_argument("--main-backend", help="backend/ of a main checkout, for the 'main' arm")
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=5)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--ticks", type=int, default=312)
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS), choices=SCENARIOS)
    parser.add_argument("--arms", nargs="+", default=["off", "on_zero", "on_buffer"], choices=ARMS)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("public_debt_runs"))
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(_worker(args.backend, args.arm, args.seed, args.scenario, args.ticks,
                                 args.households, args.firms_per_category)))
        return
    if "main" in args.arms and not args.main_backend:
        parser.error("--main-backend is required for the 'main' arm")
    jobs = []
    for scenario in args.scenarios:
        for seed in args.seeds:
            for arm in args.arms:
                backend = args.main_backend if arm == "main" else str(BACKEND_ROOT)
                jobs.append((str(Path(backend).resolve()), arm, seed, scenario, args))
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(_run_one, jobs))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results))
    report = [f"# Public debt paired runs: {args.households} households, {args.ticks} ticks, seeds {args.seeds}", ""]
    report += _run_env(args)
    report += [_report(scenario, results, args.arms, args.seeds) for scenario in args.scenarios]
    (args.out / "report.md").write_text("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
