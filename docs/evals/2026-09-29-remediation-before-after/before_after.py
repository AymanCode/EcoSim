"""Clean before/after comparison: original code (17d5c0b) vs branch head, identical settings.

Usage:
  before_after.py one <code_root> <label> <seed> <payment_sequence>
  before_after.py all
  before_after.py table
Each run is its own process so the two code versions never share imported modules.
"""
import contextlib, io, json, random, statistics, subprocess, sys, time
from pathlib import Path

S = Path("/private/tmp/claude-501/-Users-aymanislam-EcoSim-v-2-EcoSim/97e27656-19bc-4192-993f-22a3fee5b35a/scratchpad")
OUT = S / "before_after"
ROOTS = {
    "before": S / "old_code",
    "after": Path("/Users/aymanislam/EcoSim_v_2/EcoSim/.claude/worktrees/agents-economy-remediation"),
}
RUNS = [(42, "legacy"), (7, "legacy"), (11, "legacy"), (42, "income_first")]
HOUSEHOLDS, TICKS, FIRMS_PER_CAT = 1500, 300, 10
WINDOWS = [(11, 40), (41, 100), (101, 200), (201, 300)]


def gini(sorted_vals):
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if n == 0 or total <= 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    return (2 * cum) / (n * total) - (n + 1) / n


def money(eco):
    total = sum(float(h.cash_balance) for h in eco.households)
    total += sum(float(f.cash_balance) for f in eco.firms)
    total += sum(float(f.cash_balance) for f in getattr(eco, "queued_firms", []))
    total += float(eco.government.cash_balance)
    total += float(getattr(eco, "misc_firm_revenue", 0.0))
    if getattr(eco, "bank", None) is not None:
        total += float(eco.bank.cash_reserves)
    return total


def run_one(root, label, seed, seq):
    sys.path.insert(0, str(Path(root) / "backend"))
    import numpy as np
    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    rows = []
    t0 = time.time()
    with use_config(clone_config()):
        random.seed(seed); np.random.seed(seed); CONFIG.random_seed = int(seed)
        CONFIG.payment_sequence = seq
        with contextlib.redirect_stdout(io.StringIO()):
            eco = create_large_economy(HOUSEHOLDS, FIRMS_PER_CAT)
        m0 = money(eco)
        for _ in range(TICKS):
            with contextlib.redirect_stdout(io.StringIO()):
                eco.step()
            hh = eco.households
            n = len(hh)
            cash = sorted(float(h.cash_balance) for h in hh)
            employed = [h for h in hh if h.is_employed]
            wages = sorted(float(h.wage) for h in employed)
            rows.append({
                "tick": int(eco.current_tick),
                "unemp_pct": 100.0 * (n - len(employed)) / n,
                "median_wage": wages[len(wages) // 2] if wages else 0.0,
                "mean_cash": sum(cash) / n,
                "median_cash": cash[n // 2],
                "gini_cash": gini(cash),
                "firms": len(eco.firms),
                "gdp": float(sum(eco.last_tick_revenue.values())),
                "homeless": sum(1 for h in hh if h.renting_from_firm_id is None),
                "happiness": sum(float(h.happiness) for h in hh) / n,
                "gov_cash": float(eco.government.cash_balance),
                "money_change": money(eco) - m0,
                "recorded_outside_money": float(getattr(eco, "external_injection_total", 0.0)),
            })
    OUT.mkdir(exist_ok=True)
    (OUT / f"{label}_s{seed}_{seq}.json").write_text(json.dumps({"seconds": round(time.time() - t0, 1), "rows": rows}))
    print(f"done {label} s{seed} {seq} {round(time.time() - t0)}s", flush=True)


def run_all():
    for seed, seq in RUNS:
        for label in ("before", "after"):
            if (OUT / f"{label}_s{seed}_{seq}.json").exists():
                continue
            r = subprocess.run([sys.executable, __file__, "one", str(ROOTS[label]), label, str(seed), seq])
            if r.returncode:
                print(f"FAILED {label} s{seed} {seq}", flush=True)


METRICS = [("unemp_pct", "Unemployment %", 1), ("median_wage", "Median wage (employed)", 1),
           ("median_cash", "Median household cash", 0), ("gini_cash", "Cash inequality (Gini)", 3),
           ("firms", "Businesses", 1), ("gdp", "Sales per week", 0), ("homeless", "Homeless households", 0),
           ("happiness", "Mean happiness", 3), ("gov_cash", "Town hall cash", 0)]


def table():
    def load(label, seed, seq):
        return json.loads((OUT / f"{label}_s{seed}_{seq}.json").read_text())["rows"]

    def win(rows, key, a, b):
        vals = [r[key] for r in rows if a <= r["tick"] <= b]
        return sum(vals) / len(vals)

    lines = []
    for seed, seq in RUNS:
        lines.append(f"\n### seed {seed}, {seq}\n")
        lines.append("| Metric | " + " | ".join(f"ticks {a}-{b}" for a, b in WINDOWS) + " |")
        lines.append("|---|" + "---|" * len(WINDOWS))
        bef, aft = load("before", seed, seq), load("after", seed, seq)
        for key, label, d in METRICS:
            cells = []
            for a, b in WINDOWS:
                x, y = win(bef, key, a, b), win(aft, key, a, b)
                cells.append(f"{x:,.{d}f} → {y:,.{d}f}")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append(f"| Money created by tick 300 (total) | {bef[-1]['money_change']:,.0f} → {aft[-1]['money_change']:,.0f} | | | |")
        lines.append(f"| of which recorded outside money | {bef[-1]['recorded_outside_money']:,.0f} → {aft[-1]['recorded_outside_money']:,.0f} | | | |")
    # legacy averages across the three seeds, plus seed spread
    lines.append("\n### Legacy average of seeds 42, 7, 11 (spread = max-min across seeds, before code)\n")
    lines.append("| Metric | Window | Before | After | Change | Before seed spread |")
    lines.append("|---|---|---|---|---|---|")
    legacy = [(42, "legacy"), (7, "legacy"), (11, "legacy")]
    for key, label, d in METRICS:
        for a, b in WINDOWS:
            bv = [win(load("before", s, q), key, a, b) for s, q in legacy]
            av = [win(load("after", s, q), key, a, b) for s, q in legacy]
            mb, ma = sum(bv) / 3, sum(av) / 3
            lines.append(f"| {label} | {a}-{b} | {mb:,.{d}f} | {ma:,.{d}f} | {ma - mb:+,.{d}f} | {max(bv) - min(bv):,.{d}f} |")
    (OUT / "table.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "one":
        run_one(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif cmd == "all":
        run_all()
    elif cmd == "table":
        table()
