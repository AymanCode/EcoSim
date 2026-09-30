"""Inflation port: the same code with CONFIG.inflation.enabled off vs on.

Adapted from docs/evals/2026-09-29-remediation-before-after/before_after.py:
one code root (the branch after the port) and the switch set per run instead
of two code roots; metrics added for hiring (unfilled vacancies), real wage and
year-on-year inflation; money reported net of recorded outside money.

Usage:
  on_off.py one <off|on> <seed> <payment_sequence>
  on_off.py all
  on_off.py table
Each run is its own process; runs are sequential.
"""
import contextlib, io, json, random, statistics, subprocess, sys, time
from pathlib import Path

W = Path("/Users/aymanislam/EcoSim_v_2/EcoSim/.claude/worktrees/agents-economy-remediation")
OUT = W / ".superpowers/sdd/2026-09-28-agents-economy-remediation-plan/port3/on_off"
RUNS = [(42, "legacy"), (7, "legacy"), (11, "legacy"), (42, "income_first")]
HOUSEHOLDS, TICKS, FIRMS_PER_CAT = 1500, 300, 10
WINDOWS = [(11, 40), (41, 100), (101, 200), (201, 300)]


def money(eco):
    total = sum(float(h.cash_balance) for h in eco.households)
    total += sum(float(f.cash_balance) for f in eco.firms)
    total += sum(float(f.cash_balance) for f in getattr(eco, "queued_firms", []))
    total += float(eco.government.cash_balance)
    total += float(getattr(eco, "misc_firm_revenue", 0.0))
    if getattr(eco, "bank", None) is not None:
        total += float(eco.bank.cash_reserves)
    return total


def run_one(switch, seed, seq):
    sys.path.insert(0, str(W / "backend"))
    import numpy as np
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy
    from inflation import ConsumerPriceIndex

    rows = []
    t0 = time.time()
    with use_config(clone_config()):
        random.seed(seed); np.random.seed(seed); CONFIG.random_seed = int(seed)
        CONFIG.payment_sequence = seq
        CONFIG.inflation.enabled = switch == "on"
        with contextlib.redirect_stdout(io.StringIO()):
            eco = create_large_economy(HOUSEHOLDS, FIRMS_PER_CAT)
        m0 = money(eco)
        # Shadow index, identical definition, observed by this script after every
        # post-warm-up tick in BOTH arms (read-only: the index never mutates a firm).
        # End-of-tick quotes are the next week's opening quotes. It gives the off
        # arm a like-for-like price level and real wage.
        shadow = ConsumerPriceIndex(CONFIG.inflation.basket_weights, CONFIG.time.ticks_per_year)
        inj0 = float(getattr(eco, "external_injection_total", 0.0))
        for _ in range(TICKS):
            with contextlib.redirect_stdout(io.StringIO()):
                eco.step()
            hh = eco.households
            n = len(hh)
            cash = sorted(float(h.cash_balance) for h in hh)
            employed = [h for h in hh if h.is_employed]
            wages = sorted(float(h.wage) for h in employed)
            median_wage = wages[len(wages) // 2] if wages else 0.0
            prices = eco.consumer_prices
            if not eco.in_warmup:
                shadow.observe(int(eco.current_tick), eco.firms)
            sobs = shadow.last_tick is not None
            rows.append({
                "tick": int(eco.current_tick),
                "unemp_pct": 100.0 * (n - len(employed)) / n,
                # planned hires this tick minus hires actually made this tick
                "unfilled": sum(max(0, int(f.planned_hires_count or 0) - int(f.last_tick_actual_hires or 0))
                                for f in eco.firms),
                "planned_hires": sum(max(0, int(f.planned_hires_count or 0)) for f in eco.firms),
                "median_wage": median_wage,
                "real_median_wage": median_wage * 100.0 / shadow.level if sobs else median_wage,
                "shadow_index": shadow.level if sobs else None,
                "shadow_yoy_pct": 100.0 * shadow.annual_rate if shadow.annual_rate is not None else None,
                "cpi": prices.level if prices.last_tick is not None else None,
                "yoy_inflation_pct": 100.0 * prices.annual_rate if prices.annual_rate is not None else None,
                "gdp": float(sum(eco.last_tick_revenue.values())),
                "firms": len(eco.firms),
                "median_cash": cash[n // 2],
                "money_change": money(eco) - m0,
                "outside_money": float(getattr(eco, "external_injection_total", 0.0)) - inj0,
            })
    OUT.mkdir(exist_ok=True)
    (OUT / f"{switch}_s{seed}_{seq}.json").write_text(json.dumps({"seconds": round(time.time() - t0, 1), "rows": rows}))
    print(f"done {switch} s{seed} {seq} {round(time.time() - t0)}s", flush=True)


def run_all():
    for seed, seq in RUNS:
        for switch in ("off", "on"):
            if (OUT / f"{switch}_s{seed}_{seq}.json").exists():
                continue
            r = subprocess.run([sys.executable, __file__, "one", switch, str(seed), seq])
            if r.returncode:
                print(f"FAILED {switch} s{seed} {seq}", flush=True)


METRICS = [("unemp_pct", "Unemployment %", 1), ("unfilled", "Unfilled vacancies per week", 1),
           ("planned_hires", "Planned hires per week", 1),
           ("median_wage", "Median wage (employed)", 1), ("real_median_wage", "Real median wage (shadow index)", 1),
           ("shadow_index", "Price index (shadow, both arms)", 1),
           ("shadow_yoy_pct", "Year-on-year inflation % (shadow, both arms)", 1),
           ("yoy_inflation_pct", "Year-on-year inflation % (engine index, on only)", 1), ("gdp", "Sales per week", 0),
           ("firms", "Businesses", 1), ("median_cash", "Median household cash", 0)]


def load(switch, seed, seq):
    return json.loads((OUT / f"{switch}_s{seed}_{seq}.json").read_text())["rows"]


def win(rows, key, a, b):
    vals = [r[key] for r in rows if a <= r["tick"] <= b and r[key] is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, d):
    return "n/a" if v is None else f"{v:,.{d}f}"


def table():
    lines = []
    for seed, seq in RUNS:
        lines.append(f"\n### seed {seed}, {seq} (off → on)\n")
        lines.append("| Metric | " + " | ".join(f"ticks {a}-{b}" for a, b in WINDOWS) + " |")
        lines.append("|---|" + "---|" * len(WINDOWS))
        off, on = load("off", seed, seq), load("on", seed, seq)
        for key, label, d in METRICS:
            cells = [f"{fmt(win(off, key, a, b), d)} → {fmt(win(on, key, a, b), d)}" for a, b in WINDOWS]
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        net_off = off[-1]["money_change"] - off[-1]["outside_money"]
        net_on = on[-1]["money_change"] - on[-1]["outside_money"]
        lines.append(f"| Money created by tick 300 | {off[-1]['money_change']:,.0f} → {on[-1]['money_change']:,.0f} | | | |")
        lines.append(f"| of which recorded outside money | {off[-1]['outside_money']:,.0f} → {on[-1]['outside_money']:,.0f} | | | |")
        lines.append(f"| net of recorded outside money | {net_off:,.0f} → {net_on:,.0f} | | | |")
    lines.append("\n### Legacy average of seeds 42, 7, 11 (spread = max-min across the three seeds)\n")
    lines.append("| Metric | Window | Off | On | Change | Off spread | On spread |")
    lines.append("|---|---|---|---|---|---|---|")
    legacy = [(42, "legacy"), (7, "legacy"), (11, "legacy")]
    for key, label, d in METRICS:
        for a, b in WINDOWS:
            ov = [win(load("off", s, q), key, a, b) for s, q in legacy]
            nv = [win(load("on", s, q), key, a, b) for s, q in legacy]
            ov_ok = [v for v in ov if v is not None]
            nv_ok = [v for v in nv if v is not None]
            mo = sum(ov_ok) / len(ov_ok) if ov_ok else None
            mn = sum(nv_ok) / len(nv_ok) if nv_ok else None
            change = f"{mn - mo:+,.{d}f}" if mo is not None and mn is not None else "n/a"
            so = f"{max(ov_ok) - min(ov_ok):,.{d}f}" if ov_ok else "n/a"
            sn = f"{max(nv_ok) - min(nv_ok):,.{d}f}" if nv_ok else "n/a"
            lines.append(f"| {label} | {a}-{b} | {fmt(mo, d)} | {fmt(mn, d)} | {change} | {so} | {sn} |")
    for switch in ("off", "on"):
        nets = [load(switch, s, q)[-1]["money_change"] - load(switch, s, q)[-1]["outside_money"] for s, q in legacy]
        lines.append(f"\nLegacy money created by tick 300 net of recorded outside money, {switch}: "
                     + ", ".join(f"{v:,.0f}" for v in nets) + " (seeds 42, 7, 11)")
    (OUT / "table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "one":
        run_one(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif cmd == "all":
        run_all()
    elif cmd == "table":
        table()
