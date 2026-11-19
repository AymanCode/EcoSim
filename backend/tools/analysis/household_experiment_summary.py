"""Summarize household experiment arms against matched-seed controls (weeks 209-312).

Usage: python household_experiment_summary.py <results dir with runs/> [metric ...]
Runs come from household_experiment.py (batch mode); files are named <arm>-<government>-<seed>.json.
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

S = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir() else Path(__file__).resolve().parent
EXP = S / "runs" if (S / "runs").is_dir() else S / "exp"
SEEDS = (42, 43)
WIN = (209, 312)
ARMS = ["spending_leak", "timing", "money_lines", "savings_goal", "wellbeing", "job_choices", "leak_goal", "all"]
METRICS = {
    "u": "Unemployment (all households)", "u_lf": "Unemployment (able to work)",
    "liq_med": "Median savings", "weeks_med": "Median savings, weeks of essentials",
    "hap_lo": "Happiness at or near 0", "hap_med": "Median happiness", "hap_p10": "Happiness p10",
    "hap_p90": "Happiness p90", "mor_med": "Median morale", "health": "Mean health", "gdp": "Weekly output",
    "spent": "Share of shopping budget spent", "wage_mean": "Mean contract wage", "pov13w": "Under 13 weeks of essentials",
}


SCHEMA_VERSION = 2
REQUIRED_TOP = {"schema_version", "opening", "health_spells", "hand_to_mouth_week_26",
                "money_tick0", "seed", "sequence", "households", "ticks", "rows", "arm", "overrides", "levers"}
REQUIRED_ROWS = {"t", "u", "money_full", "money_drift", "external_injection_total", "illnesses",
                 "care_episodes_opened", "care_visits_scheduled", "care_queue_admissions_new", "care_queue_admissions_retry",
                 "care_deferrals", "care_waits", "care_denials", "care_completed", "care_receipts",
                 "care_pending_visits", "care_visit_slots", "healthcare_firms", "hc_cash", "hc_cash_min_firm",
                 "hc_firms", "hc_wage_arrears", "hc_payroll", "sick_count", "sick_entries", "sick_exits", "sick_mean_spell",
                 "health_lt_01", "health_lt_05", "health_lt_07",
                 "evictions", "evicted_household_ids", "rent_arrears", "household_loan_writeoffs",
                 "household_unpaid_dues"} | set(METRICS) | {"budget"}
REQUIRED_FIRM = {"active", "cash", "wage_arrears", "payroll", "bank_loans", "government_loans", "bailouts", "subsidies"}
REQUIRED_SPELL = {"household_id", "deprived_at_onset", "entry_week", "exit_week", "censored", "censored_at_week"}


def read_run(path, *, expected_ticks=None):
    """Reject old or incomplete cached runs instead of silently using them."""
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(run, dict) or REQUIRED_TOP - run.keys():
        raise ValueError(f"{path}: missing required run fields")
    version = run["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schema version")
    if (run["sequence"] != "income_first" or run["seed"] not in (42, 43)
            or not isinstance(run["households"], int) or isinstance(run["households"], bool)
            or not 0 < run["households"] <= 1000):
        raise ValueError(f"{path}: unsupported population, seed or payment sequence")
    if not isinstance(run["opening"], dict) or {"household_cash_total", "cash_gini", "cash_median", "cash_below_40_share", "id_skill_spearman", "doctor_opening_capacity", "healthcare_firms"} - run["opening"].keys():
        raise ValueError(f"{path}: missing opening fields")
    opening_firms = run["opening"]["healthcare_firms"]
    if not isinstance(opening_firms, dict) or any(
        not isinstance(firm, dict) or {"cash", "wage_arrears"} - firm.keys()
        for firm in opening_firms.values()
    ):
        raise ValueError(f"{path}: missing opening healthcare firm fields")
    if (not isinstance(run["ticks"], int) or isinstance(run["ticks"], bool) or run["ticks"] < 0
            or (expected_ticks is not None and run["ticks"] != expected_ticks)
            or not isinstance(run["rows"], list) or len(run["rows"]) != run["ticks"]):
        raise ValueError(f"{path}: missing weekly rows")
    if run["ticks"] >= 26 and (not isinstance(run["hand_to_mouth_week_26"], dict)
                               or {"hand_to_mouth", "not_hand_to_mouth", "zero_income"} - run["hand_to_mouth_week_26"].keys()):
        raise ValueError(f"{path}: missing week-26 proxy")
    if run["ticks"] >= 26:
        counts = run["hand_to_mouth_week_26"]
        if (any(not isinstance(counts[key], int) or isinstance(counts[key], bool) or counts[key] < 0
                for key in ("hand_to_mouth", "not_hand_to_mouth", "zero_income"))
                or sum(counts[key] for key in ("hand_to_mouth", "not_hand_to_mouth", "zero_income")) != run["households"]):
            raise ValueError(f"{path}: invalid week-26 proxy")
    household_keys = {str(i) for i in range(run["households"])}
    for week, row in enumerate(run["rows"], 1):
        if not isinstance(row, dict) or REQUIRED_ROWS - row.keys() or row["t"] != week:
            raise ValueError(f"{path}: missing or unordered fields at week {week}")
        if not isinstance(row["healthcare_firms"], dict) or any(
            not isinstance(firm, dict) or REQUIRED_FIRM - firm.keys() for firm in row["healthcare_firms"].values()
        ):
            raise ValueError(f"{path}: missing healthcare firm fields at week {week}")
        if (not isinstance(row["evicted_household_ids"], list)
                or any(not isinstance(hid, int) or isinstance(hid, bool) or not 0 <= hid < run["households"]
                       for hid in row["evicted_household_ids"])
                or row["evictions"] != len(row["evicted_household_ids"])
                or not isinstance(row["household_loan_writeoffs"], dict)
                or any(not isinstance(key, str) or not isinstance(value, int) or isinstance(value, bool) or value < 0
                       for key, value in row["household_loan_writeoffs"].items())
                or row["external_injection_total"] != 0):
            raise ValueError(f"{path}: invalid diagnostics at week {week}")
        for firm in row["healthcare_firms"].values():
            if (not isinstance(firm["active"], bool) or any(
                isinstance(firm[key], bool) or not isinstance(firm[key], (int, float)) or not math.isfinite(firm[key])
                for key in REQUIRED_FIRM - {"active"}
            )):
                raise ValueError(f"{path}: invalid healthcare firm at week {week}")
        if (not isinstance(row["household_unpaid_dues"], dict)
                or set(row["household_unpaid_dues"]) != household_keys
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(value) or value < 0 for value in row["household_unpaid_dues"].values())):
            raise ValueError(f"{path}: missing household dues at week {week}")
    if not isinstance(run["health_spells"], list) or any(
        not isinstance(spell, dict) or REQUIRED_SPELL - spell.keys() for spell in run["health_spells"]
    ):
        raise ValueError(f"{path}: missing spell fields")
    for spell in run["health_spells"]:
        if (not isinstance(spell["censored"], bool) or not isinstance(spell["deprived_at_onset"], bool)
                or not isinstance(spell["household_id"], int) or not 0 <= spell["household_id"] < run["households"]
                or not isinstance(spell["entry_week"], int) or not 0 <= spell["entry_week"] <= run["ticks"]
                or (spell["censored"] and (spell["exit_week"] is not None or spell["censored_at_week"] != run["ticks"]))
                or (not spell["censored"] and (not isinstance(spell["exit_week"], int)
                    or not spell["entry_week"] < spell["exit_week"] <= run["ticks"] or spell["censored_at_week"] is not None))):
            raise ValueError(f"{path}: invalid health spell")
    return run


def evaluate_plan2_halt_rules(treatment_file, control_file):
    """Evaluate weeks 1–52 against the matched control; strict thresholds."""
    treatment, control = read_run(treatment_file), read_run(control_file)
    if (treatment["sequence"] != "income_first" or control["sequence"] != "income_first"
            or treatment["seed"] != control["seed"] or treatment["households"] != control["households"]
            or treatment["ticks"] < 52 or control["ticks"] < 52):
        raise ValueError("halt evaluation requires matched income_first runs of at least 52 weeks")
    tr, cr = treatment["rows"][:52], control["rows"][:52]
    rules = {}

    def count_rule(name, a, b):
        ordinary = 5 if b == 0 else 2 * b
        excess = b + 50
        threshold = "excess" if excess < ordinary else ("c=0" if b == 0 else "2c")
        limit = min(ordinary, excess)
        halted = a > limit
        rules[name] = {"treatment": a, "control": b, "threshold": threshold,
                       "halt": halted, "reason": f"{a} {'exceeds' if halted else 'does not exceed'} {limit}"}

    for name, measure in (
        ("eviction_events", lambda rows: sum(r["evictions"] for r in rows)),
        ("evicted_households", lambda rows: len({hid for r in rows for hid in r["evicted_household_ids"]})),
    ):
        a, b = measure(tr), measure(cr)
        count_rule(name, a, b)
    subtypes = {subtype for row in tr + cr for subtype in row["household_loan_writeoffs"]
                if subtype == "consumption" or subtype.startswith("consumption_")}
    for subtype in sorted(subtypes | {"consumption"}):
        a = sum(r["household_loan_writeoffs"].get(subtype, 0) for r in tr)
        b = sum(r["household_loan_writeoffs"].get(subtype, 0) for r in cr)
        count_rule(f"consumption_loan_defaults:{subtype}", a, b)
    treatment_cash = [firm["cash"] for r in tr for firm in r["healthcare_firms"].values()]
    control_cash = [firm["cash"] for r in cr for firm in r["healthcare_firms"].values()]
    if not treatment_cash or not control_cash:
        raise ValueError("halt evaluation requires healthcare firm cash series")
    a, b = min(treatment_cash), min(control_cash)
    rules["healthcare_cash"] = {"treatment": a, "control": b, "threshold": "0",
                                "halt": a < 0, "reason": f"minimum treatment cash is {a}"}
    a = st.mean(r["u"] for r in tr[26:52])
    b = st.mean(r["u"] for r in cr[26:52])
    rules["unemployment"] = {"treatment": a, "control": b, "threshold": "control + 0.10",
                             "halt": a > b + 0.10,
                             "reason": f"mean treatment unemployment is {a - b:+.6f} above control"}
    reasons = [name for name, rule in rules.items() if rule["halt"]]
    return {"seed": treatment["seed"], "halt": bool(reasons), "reasons": reasons, "rules": rules}


def load(name):
    p = EXP / f"{name}.json"
    return read_run(p, expected_ticks=312)["rows"] if p.exists() else None


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
