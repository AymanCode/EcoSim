"""Summarize household experiment arms against matched-seed controls (weeks 209-312).

Usage: python household_experiment_summary.py <results dir with runs/> [metric ...]
Runs come from household_experiment.py (batch mode); files are named <arm>-<government>-<seed>.json.
"""
import json
import statistics as st
import sys
from pathlib import Path

S = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir() else Path(__file__).resolve().parent
EXP = S / "runs" if (S / "runs").is_dir() else S / "exp"
SEEDS = (42, 43, 44)
WIN = (209, 312)
ARMS = ["spending_leak", "timing", "money_lines", "savings_goal", "wellbeing", "job_choices", "leak_goal", "all"]
METRICS = {
    "u": "Unemployment (all households)", "u_lf": "Unemployment (able to work)",
    "liq_med": "Median savings", "weeks_med": "Median savings, weeks of essentials",
    "hap_lo": "Happiness at or near 0", "hap_med": "Median happiness", "hap_p10": "Happiness p10",
    "hap_p90": "Happiness p90", "mor_med": "Median morale", "health": "Mean health", "gdp": "Weekly output",
    "spent": "Share of shopping budget spent", "wage_mean": "Mean contract wage", "pov13w": "Under 13 weeks of essentials",
}


def load(name):
    p = EXP / f"{name}.json"
    return json.loads(p.read_text())["rows"] if p.exists() else None


def window_stats(rows):
    w = [r for r in rows if WIN[0] <= r["t"] <= WIN[1]]
    first = [r for r in w if r["t"] <= 260]
    second = [r for r in w if r["t"] > 260]
    out, drift = {}, {}
    for k in METRICS:
        if k == "spent":
            b = sum(r["budget"] for r in w)
            out[k] = sum(r["spent"] for r in w) / b if b else 0.0
            b1, b2 = sum(r["budget"] for r in first), sum(r["budget"] for r in second)
            drift[k] = (sum(r["spent"] for r in second) / b2 if b2 else 0) - (sum(r["spent"] for r in first) / b1 if b1 else 0)
            continue
        vals = [r[k] for r in w if r[k] is not None]
        out[k] = st.mean(vals) if vals else 0.0
        a = [r[k] for r in first if r[k] is not None]
        b = [r[k] for r in second if r[k] is not None]
        drift[k] = (st.mean(b) - st.mean(a)) if a and b else 0.0
    return out, drift


def summarize():
    result = {"metrics": METRICS, "arms": {}, "controls": {}}
    for gov in ("default", "lean", "generous"):
        per_seed = {}
        for s in SEEDS:
            rows = load(f"control-{gov}-{s}")
            if rows:
                per_seed[s] = window_stats(rows)
        result["controls"][gov] = {str(s): v[0] for s, v in per_seed.items()}
        arm_list = ARMS if gov == "default" else ["all"]
        for arm in arm_list:
            deltas, levels, drifts = {k: [] for k in METRICS}, {k: [] for k in METRICS}, {k: [] for k in METRICS}
            for s in SEEDS:
                rows = load(f"{arm}-{gov}-{s}")
                if not rows or s not in per_seed:
                    continue
                stats, drift = window_stats(rows)
                for k in METRICS:
                    deltas[k].append(stats[k] - per_seed[s][0][k])
                    levels[k].append(stats[k])
                    drifts[k].append(drift[k])
            result["arms"][f"{arm}|{gov}"] = {"delta": deltas, "level": levels, "drift": drifts}
    return result


if __name__ == "__main__":
    res = summarize()
    (S / "arms_summary.json").write_text(json.dumps(res))
    keys = [a for a in sys.argv[1:] if not Path(a).is_dir()] or ["u", "weeks_med", "hap_lo", "hap_med", "mor_med", "health", "gdp", "spent", "wage_mean"]
    print("arm|gov".ljust(24) + "".join(k[:10].rjust(12) for k in keys))
    for gov in ("default", "lean", "generous"):
        c = res["controls"][gov]
        if c:
            means = {k: st.mean(v[k] for v in c.values()) for k in keys}
            print(f"control|{gov}".ljust(24) + "".join(f"{means[k]:12.3f}" for k in keys))
    for name, v in res["arms"].items():
        if not v["delta"]["u"]:
            continue
        print(name.ljust(24) + "".join(f"{st.mean(v['delta'][k]):+12.3f}" for k in keys) + f"   n={len(v['delta']['u'])}")
