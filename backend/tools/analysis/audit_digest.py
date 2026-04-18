from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""EcoSim Audit Digest Pipeline

Reads a raw JSONL audit dump and produces a compact, token-efficient
text report designed to fit in a local LLM's context window (~8-20K tokens)
without losing analytical accuracy.

Usage:
    python audit_digest.py audit_full_dump.jsonl
    python audit_digest.py audit_full_dump.jsonl --output digest.md
    python audit_digest.py audit_full_dump.jsonl --max-tokens 12000
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _r2(v) -> str:
    """Round to 2 decimal places, return as compact string."""
    if v is None:
        return "-"
    return f"{float(v):.2f}"


def _r1(v) -> str:
    if v is None:
        return "-"
    return f"{float(v):.1f}"


def _pct(v) -> str:
    """Format as percentage string."""
    if v is None:
        return "-"
    return f"{float(v) * 100:.1f}%"


def _delta(v) -> str:
    """Format a delta with +/- sign."""
    if v is None:
        return "-"
    fv = float(v)
    if fv >= 0:
        return f"+{fv:.2f}"
    return f"{fv:.2f}"


def _sparkline(values: List[float], width: int = 20) -> str:
    """Create a compact ASCII sparkline from a series of values."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn
    if rng < 1e-9:
        return "â”€" * min(width, len(values))
    chars = "â–â–‚â–ƒâ–„â–…â–†â–‡â–ˆ"
    step = len(values) / width if len(values) > width else 1
    sampled = []
    i = 0.0
    while i < len(values) and len(sampled) < width:
        idx = min(int(i), len(values) - 1)
        sampled.append(values[idx])
        i += step
    return "".join(chars[min(len(chars) - 1, int((v - mn) / rng * (len(chars) - 1)))] for v in sampled)


def percentiles(values: List[float]) -> Dict[str, float]:
    """Compute p10, p25, p50, p75, p90 from a list."""
    if not values:
        return {"p10": 0, "p25": 0, "p50": 0, "p75": 0, "p90": 0, "mean": 0}
    s = sorted(values)
    n = len(s)

    def _p(pct):
        idx = pct / 100.0 * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    return {
        "p10": round(_p(10), 2),
        "p25": round(_p(25), 2),
        "p50": round(_p(50), 2),
        "p75": round(_p(75), 2),
        "p90": round(_p(90), 2),
        "mean": round(sum(s) / n, 2),
    }


# â”€â”€ Data Loader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def load_audit(path: str) -> Tuple[Dict, List[Dict]]:
    """Load JSONL audit file. Returns (config, list_of_tick_records)."""
    # Resolve path: try as-is, then relative to this script's directory
    if not Path(path).exists():
        alt = Path(__file__).parent / path
        if alt.exists():
            path = str(alt)
    config = {}
    ticks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rtype = record.get("type", "tick")
            if rtype == "config":
                config = record
            elif rtype == "tick":
                ticks.append(record)
            elif rtype == "run_summary":
                pass  # We'll build our own digest
    return config, ticks


# â”€â”€ Digest Builders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_config_section(config: Dict) -> str:
    """One-line config summary."""
    parts = [
        f"seed={config.get('seed', '?')}",
        f"hh={config.get('households', '?')}",
        f"firms/cat={config.get('firms_per_category', '?')}",
        f"ticks={config.get('ticks', '?')}",
        f"warmup={config.get('warmup_ticks', '?')}",
        f"bank={'yes' if config.get('has_bank') else 'no'}",
        f"shocks={'off' if config.get('no_shocks') else 'on'}",
    ]
    return "CONFIG: " + " | ".join(parts)


def build_macro_timeseries(ticks: List[Dict]) -> str:
    """Compact macro metric table â€” one row per tick."""
    lines = []
    lines.append("## MACRO TIMESERIES")
    lines.append("")
    header = "tick|unemp%|GDP|firms|emp|wage_avg|hlth%|hap%|gov$|hh$|firm$|bank$|drift$"
    lines.append(header)
    lines.append("-" * len(header))

    for t in ticks:
        tick = t.get("tick", 0)
        m = t.get("metrics", {})
        ma = t.get("money_audit", {})
        unemp = float(m.get("unemployment_rate", 0) or 0) * 100
        gdp = float(m.get("gdp_this_tick", 0) or 0)
        firms = m.get("total_firms", 0)
        emp = m.get("total_employees", 0)
        wage = float(m.get("mean_wage", 0) or 0)
        health = float(m.get("mean_health", 0) or 0) * 100
        happy = float(m.get("mean_happiness", 0) or 0) * 100
        gov = float(ma.get("government_cash", 0) or 0)
        hh = float(ma.get("household_cash", 0) or 0)
        fc = float(ma.get("firm_cash", 0) or 0)
        bank = float(ma.get("bank_reserves", 0) or 0)
        total = float(ma.get("total_money", 0) or 0)
        initial_money = float(ticks[0].get("money_audit", {}).get("total_money", 0) or 0) if ticks else 0
        drift = total - initial_money

        lines.append(
            f"{tick:>3}|{unemp:>5.1f}|{gdp:>7.0f}|{firms:>5}|{emp:>4}"
            f"|{wage:>7.1f}|{health:>4.0f}|{happy:>3.0f}"
            f"|{gov:>8.0f}|{hh:>8.0f}|{fc:>7.0f}|{bank:>6.0f}|{drift:>+8.0f}"
        )
    return "\n".join(lines)


def build_sparklines(ticks: List[Dict]) -> str:
    """Sparkline trends for key metrics."""
    if len(ticks) < 3:
        return ""

    series = {
        "unemployment": [],
        "GDP": [],
        "mean_wage": [],
        "mean_health": [],
        "mean_happiness": [],
        "gov_cash": [],
    }
    for t in ticks:
        m = t.get("metrics", {})
        ma = t.get("money_audit", {})
        series["unemployment"].append(float(m.get("unemployment_rate", 0) or 0))
        series["GDP"].append(float(m.get("gdp_this_tick", 0) or 0))
        series["mean_wage"].append(float(m.get("mean_wage", 0) or 0))
        series["mean_health"].append(float(m.get("mean_health", 0) or 0))
        series["mean_happiness"].append(float(m.get("mean_happiness", 0) or 0))
        series["gov_cash"].append(float(ma.get("government_cash", 0) or 0))

    lines = ["## TRENDS (sparklines, left=tick0 right=final)"]
    for name, vals in series.items():
        spark = _sparkline(vals, width=30)
        lines.append(f"  {name:<16} {spark}  [{_r2(vals[0])} -> {_r2(vals[-1])}]")
    return "\n".join(lines)


def build_household_digest(ticks: List[Dict]) -> str:
    """Aggregate household data into distributions at key ticks."""
    lines = ["## HOUSEHOLD DISTRIBUTIONS"]
    lines.append("(p10/p25/p50/p75/p90 at selected ticks)")
    lines.append("")

    # Pick key ticks: first, 25%, 50%, 75%, last
    n = len(ticks)
    if n == 0:
        return ""
    indices = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))

    for idx in indices:
        t = ticks[idx]
        tick = t.get("tick", 0)
        households = t.get("households", [])
        if not households:
            continue

        cash_vals = [float(h.get("cash_balance", 0) or 0) for h in households]
        health_vals = [float(h.get("health", 0) or 0) for h in households]
        happy_vals = [float(h.get("happiness", 0) or 0) for h in households]
        wage_vals = [float(h.get("wage", 0) or 0) for h in households if h.get("is_employed")]
        emp_count = sum(1 for h in households if h.get("is_employed"))
        unemp_count = len(households) - emp_count
        food_insecure = sum(1 for h in households if float(h.get("food_consumed_this_tick", 0) or 0) < float(h.get("min_food_per_tick", 1) or 1) * 0.5)
        homeless = sum(1 for h in households if h.get("renting_from_firm_id") is None)
        has_medical_loan = sum(1 for h in households if float(h.get("medical_loan_remaining", 0) or 0) > 0)
        has_consumption_loan = sum(1 for h in households if float(h.get("consumption_loan_remaining", 0) or 0) > 0)

        cp = percentiles(cash_vals)
        hp = percentiles(health_vals)
        hap = percentiles(happy_vals)
        wp = percentiles(wage_vals) if wage_vals else {"p10": 0, "p25": 0, "p50": 0, "p75": 0, "p90": 0, "mean": 0}

        lines.append(f"--- Tick {tick} ({emp_count} emp, {unemp_count} unemp, {food_insecure} food-insecure, {homeless} homeless) ---")
        lines.append(f"  cash    p10={cp['p10']:>8} p25={cp['p25']:>8} p50={cp['p50']:>8} p75={cp['p75']:>8} p90={cp['p90']:>8} avg={cp['mean']:>8}")
        lines.append(f"  health  p10={hp['p10']:>5} p25={hp['p25']:>5} p50={hp['p50']:>5} p75={hp['p75']:>5} p90={hp['p90']:>5} avg={hp['mean']:>5}")
        lines.append(f"  happy   p10={hap['p10']:>5} p25={hap['p25']:>5} p50={hap['p50']:>5} p75={hap['p75']:>5} p90={hap['p90']:>5} avg={hap['mean']:>5}")
        lines.append(f"  wage*   p10={wp['p10']:>7} p25={wp['p25']:>7} p50={wp['p50']:>7} p75={wp['p75']:>7} p90={wp['p90']:>7} avg={wp['mean']:>7}")
        lines.append(f"  loans: medical={has_medical_loan} consumption={has_consumption_loan}")
        lines.append("")

    return "\n".join(lines)


def build_firm_digest(ticks: List[Dict]) -> str:
    """Compact per-firm lifecycle table."""
    if not ticks:
        return ""

    # Collect firm data across all ticks
    firm_history: Dict[int, List[Dict]] = defaultdict(list)
    firm_meta: Dict[int, Dict] = {}

    for t in ticks:
        tick = t.get("tick", 0)
        for f in t.get("firms", []):
            fid = f.get("firm_id")
            firm_history[fid].append({"tick": tick, **f})
            if fid not in firm_meta:
                firm_meta[fid] = {
                    "good_category": f.get("good_category", "?"),
                    "good_name": f.get("good_name", "?"),
                    "is_baseline": f.get("is_baseline", False),
                    "personality": f.get("personality", "?"),
                }

    lines = ["## FIRM LIFECYCLE SUMMARY"]
    lines.append("")
    lines.append("id|cat|base|pers|first|last|emp_range|price_range|wage_range|cash_range|inv_range|sold_range|rev_total|profit_total|burn_t|surv_t|capital")
    lines.append("-" * 120)

    for fid in sorted(firm_meta.keys()):
        meta = firm_meta[fid]
        history = firm_history[fid]
        if not history:
            continue

        first_tick = history[0]["tick"]
        last_tick = history[-1]["tick"]

        emp_vals = [int(h.get("employee_count", 0) or 0) for h in history]
        price_vals = [float(h.get("price", 0) or 0) for h in history]
        wage_vals = [float(h.get("wage_offer", 0) or 0) for h in history]
        cash_vals = [float(h.get("cash_balance", 0) or 0) for h in history]
        inv_vals = [float(h.get("inventory_units", 0) or 0) for h in history]
        sold_vals = [float(h.get("last_units_sold", 0) or 0) for h in history]
        rev_total = sum(float(h.get("last_revenue", 0) or 0) for h in history)
        profit_total = sum(float(h.get("last_profit", 0) or 0) for h in history)
        burn_ticks = sum(1 for h in history if h.get("burn_mode"))
        surv_ticks = sum(1 for h in history if h.get("survival_mode"))
        final_capital = float(history[-1].get("capital_stock", 0) or 0)

        def _range(vals):
            if not vals:
                return "-"
            return f"{min(vals):.0f}-{max(vals):.0f}"

        cat_short = meta["good_category"][:4] if meta["good_category"] else "?"
        base = "Y" if meta["is_baseline"] else "N"
        pers = (meta.get("personality") or "?")[:3]

        lines.append(
            f"{fid:>3}|{cat_short:<4}|{base}|{pers:<3}"
            f"|{first_tick:>4}|{last_tick:>4}"
            f"|{_range(emp_vals):>8}|{_range(price_vals):>10}|{_range(wage_vals):>10}"
            f"|{_range(cash_vals):>12}|{_range(inv_vals):>10}|{_range(sold_vals):>10}"
            f"|{rev_total:>10.0f}|{profit_total:>11.0f}"
            f"|{burn_ticks:>5}|{surv_ticks:>5}|{final_capital:>7.0f}"
        )

    # Detailed per-firm tick-by-tick for non-baseline firms (compact)
    lines.append("")
    lines.append("## FIRM TICK DETAIL (non-baseline only)")
    lines.append("")

    for fid in sorted(firm_meta.keys()):
        meta = firm_meta[fid]
        if meta.get("is_baseline"):
            continue
        history = firm_history[fid]
        if not history:
            continue

        lines.append(f"--- Firm {fid} ({meta['good_name']}, {meta.get('personality','?')}) ---")
        lines.append("  t|emp|hire|fire|prod|sold|inv|price|wage|cash|revenue|profit|burn|surv")

        for h in history:
            t = h["tick"]
            emp = h.get("employee_count", 0)
            hire = h.get("last_tick_actual_hires", h.get("last_tick_planned_hires", 0)) or 0
            fire = len(h.get("planned_layoffs_ids", []) or [])
            prod = float(h.get("last_units_produced", 0) or 0)
            sold = float(h.get("last_units_sold", 0) or 0)
            inv = float(h.get("inventory_units", 0) or 0)
            price = float(h.get("price", 0) or 0)
            wage = float(h.get("wage_offer", 0) or 0)
            cash = float(h.get("cash_balance", 0) or 0)
            rev = float(h.get("last_revenue", 0) or 0)
            prof = float(h.get("last_profit", 0) or 0)
            burn = "B" if h.get("burn_mode") else "."
            surv = "S" if h.get("survival_mode") else "."

            lines.append(
                f"  {t:>3}|{emp:>3}|{hire:>4}|{fire:>4}"
                f"|{prod:>6.1f}|{sold:>5.1f}|{inv:>6.1f}"
                f"|{price:>6.2f}|{wage:>6.1f}|{cash:>8.0f}"
                f"|{rev:>7.0f}|{prof:>7.0f}|{burn}|{surv}"
            )
        lines.append("")

    return "\n".join(lines)


def build_government_digest(ticks: List[Dict]) -> str:
    """Compact government policy + fiscal timeline."""
    lines = ["## GOVERNMENT"]
    lines.append("")
    lines.append("t|cash|w_tax%|p_tax%|benefit|min_wage|infra_mult|tech_mult|fiscal_p|spend_eff|rev|spend")
    lines.append("-" * 100)

    for t in ticks:
        tick = t.get("tick", 0)
        g = t.get("government", {})
        cash = float(g.get("cash_balance", 0) or 0)
        wtax = float(g.get("wage_tax_rate", 0) or 0) * 100
        ptax = float(g.get("profit_tax_rate", 0) or 0) * 100
        benefit_raw = g.get("benefit_level", "?")
        benefit = str(benefit_raw)[:6]
        min_wage = float(g.get("_minimum_wage_floor", 0) or 0)
        infra = float(g.get("infrastructure_productivity_multiplier", 1) or 1)
        tech = float(g.get("technology_quality_multiplier", 1) or 1)
        fp = float(g.get("fiscal_pressure", 0) or 0)
        se = float(g.get("spending_efficiency", 1) or 1)
        rev = float(g.get("last_tick_revenue", 0) or 0)
        spend = float(g.get("last_tick_spending", 0) or 0)

        lines.append(
            f"{tick:>3}|{cash:>8.0f}|{wtax:>5.1f}|{ptax:>5.1f}"
            f"|{benefit:>7}|{min_wage:>8.1f}"
            f"|{infra:>9.4f}|{tech:>9.4f}"
            f"|{fp:>7.4f}|{se:>8.4f}|{rev:>7.0f}|{spend:>7.0f}"
        )

    return "\n".join(lines)


def build_bank_digest(ticks: List[Dict]) -> str:
    """Compact bank timeline."""
    has_bank = any(t.get("bank") is not None for t in ticks)
    if not has_bank:
        return "## BANK\nNo bank in this simulation."

    lines = ["## BANK"]
    lines.append("")
    lines.append("t|reserves|deposits|loans_out|dep_rate%|new_loans|repay|defaults|int_income|loan_cnt|can_lend")
    lines.append("-" * 100)

    for t in ticks:
        tick = t.get("tick", 0)
        b = t.get("bank")
        if b is None:
            continue
        reserves = float(b.get("cash_reserves", 0) or 0)
        deposits = float(b.get("total_deposits", 0) or 0)
        loans_out = float(b.get("total_loans_outstanding", 0) or 0)
        dep_rate = float(b.get("deposit_rate", 0) or 0) * 100
        new_loans = float(b.get("last_tick_new_loans", 0) or 0)
        repay = float(b.get("last_tick_repayments", 0) or 0)
        defaults = float(b.get("last_tick_defaults", 0) or 0)
        int_income = float(b.get("last_tick_interest_income", 0) or 0)
        loan_cnt = int(b.get("active_loan_count", 0) or 0)
        can_lend = "Y" if b.get("can_lend") else "N"

        lines.append(
            f"{tick:>3}|{reserves:>8.0f}|{deposits:>8.0f}|{loans_out:>9.0f}"
            f"|{dep_rate:>8.3f}|{new_loans:>9.0f}|{repay:>6.0f}"
            f"|{defaults:>8.0f}|{int_income:>10.0f}|{loan_cnt:>8}|{can_lend}"
        )

    return "\n".join(lines)


def build_events_digest(ticks: List[Dict]) -> str:
    """Summarize regime events, labor events, healthcare events."""
    all_regime = []
    labor_summary = defaultdict(int)
    healthcare_summary = defaultdict(int)

    for t in ticks:
        tick = t.get("tick", 0)
        for evt in t.get("events", {}).get("regime_events", []) or []:
            all_regime.append({"tick": tick, **evt})
        for evt in t.get("events", {}).get("labor_events", []) or []:
            etype = evt.get("event_type", "unknown")
            labor_summary[etype] += 1
        for evt in t.get("events", {}).get("healthcare_events", []) or []:
            etype = evt.get("event_type", "unknown")
            healthcare_summary[etype] += 1

    lines = ["## EVENTS SUMMARY"]
    lines.append("")

    if labor_summary:
        lines.append("Labor events total: " + ", ".join(f"{k}={v}" for k, v in sorted(labor_summary.items())))
    else:
        lines.append("Labor events: none recorded")

    if healthcare_summary:
        lines.append("Healthcare events total: " + ", ".join(f"{k}={v}" for k, v in sorted(healthcare_summary.items())))
    else:
        lines.append("Healthcare events: none recorded")

    lines.append("")
    if all_regime:
        lines.append("Regime events (all):")
        for evt in all_regime:
            tick = evt.get("tick", "?")
            etype = evt.get("event_type", "?")
            entity = f"{evt.get('entity_type', '?')}#{evt.get('entity_id', '?')}"
            sector = evt.get("sector", "")
            reason = evt.get("reason_code", "")
            sev = evt.get("severity", "")
            lines.append(f"  t{tick}: {etype} {entity} sector={sector} reason={reason} sev={sev}")
    else:
        lines.append("Regime events: none")

    return "\n".join(lines)


def build_actions_digest(ticks: List[Dict]) -> str:
    """Summarize per-tick actions compactly."""
    lines = ["## ACTION SUMMARY PER TICK"]
    lines.append("")
    lines.append("t|hires|fires|bankruptcies|dividends|transfers$|wage_tax$|profit_tax$|new_bank_loans$|job_seekers|got_hired|got_fired")
    lines.append("-" * 120)

    for t in ticks:
        tick = t.get("tick", 0)
        actions = t.get("actions", {})
        if not actions:
            continue

        firm_actions = actions.get("firm_actions", [])
        hh_actions = actions.get("household_actions", [])
        gov_actions = actions.get("government_actions", {})
        bank_actions = actions.get("bank_actions") or {}

        total_hires = sum(len(fa.get("hired_ids", []) or []) for fa in firm_actions)
        total_fires = sum(len(fa.get("fired_ids", []) or []) for fa in firm_actions)
        bankruptcies = actions.get("bankruptcies_this_tick", 0)
        dividends = float(actions.get("total_dividends_paid", 0) or 0)
        transfers = float(gov_actions.get("total_transfers", 0) or 0)
        wage_tax = float(gov_actions.get("total_wage_taxes", 0) or 0)
        profit_tax = float(gov_actions.get("total_profit_taxes", 0) or 0)
        new_loans = float(bank_actions.get("new_loans_issued", 0) or 0)
        seekers = sum(1 for h in hh_actions if h.get("searching_for_job"))
        hired = sum(1 for h in hh_actions if h.get("got_hired"))
        fired = sum(1 for h in hh_actions if h.get("got_fired"))

        lines.append(
            f"{tick:>3}|{total_hires:>5}|{total_fires:>5}|{bankruptcies:>12}"
            f"|{dividends:>9.0f}|{transfers:>10.0f}|{wage_tax:>9.0f}"
            f"|{profit_tax:>11.0f}|{new_loans:>14.0f}"
            f"|{seekers:>11}|{hired:>10}|{fired:>9}"
        )

    return "\n".join(lines)


def build_diagnostics_digest(ticks: List[Dict]) -> str:
    """Extract diagnostics and decision features at key ticks."""
    lines = ["## DIAGNOSTICS & DECISION FEATURES"]
    lines.append("")

    n = len(ticks)
    if n == 0:
        return ""
    indices = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))

    for idx in indices:
        t = ticks[idx]
        tick = t.get("tick", 0)
        analysis = t.get("analysis", {})
        diag = t.get("diagnostics", {})
        df = analysis.get("decision_features", {})
        td = diag.get("tick_diagnostics", {})

        if not df and not td:
            continue

        lines.append(f"--- Tick {tick} ---")
        if df:
            parts = [f"{k}={_r2(v)}" for k, v in sorted(df.items())]
            lines.append(f"  decision_features: {', '.join(parts)}")
        if td:
            # Only show non-zero diagnostics to save tokens
            nonzero = {k: v for k, v in td.items() if v and v != 0 and v != "stable" and v != 0.0}
            if nonzero:
                parts = [f"{k}={v}" for k, v in sorted(nonzero.items())]
                lines.append(f"  diagnostics: {', '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


def build_money_conservation_digest(ticks: List[Dict]) -> str:
    """Track money drift over time."""
    if not ticks:
        return ""
    initial = float(ticks[0].get("money_audit", {}).get("total_money", 0) or 0)
    final = float(ticks[-1].get("money_audit", {}).get("total_money", 0) or 0)
    drift = final - initial
    drift_pct = (drift / initial * 100) if abs(initial) > 1e-9 else 0

    lines = ["## MONEY CONSERVATION"]
    lines.append(f"Initial: ${initial:,.0f} | Final: ${final:,.0f} | Drift: ${drift:+,.0f} ({drift_pct:+.3f}%)")

    # Find worst drift tick
    worst_drift = 0
    worst_tick = 0
    for t in ticks:
        tick_money = float(t.get("money_audit", {}).get("total_money", 0) or 0)
        d = abs(tick_money - initial)
        if d > worst_drift:
            worst_drift = d
            worst_tick = t.get("tick", 0)

    if worst_drift > 0:
        lines.append(f"Worst drift at tick {worst_tick}: ${worst_drift:,.0f}")

    return "\n".join(lines)


def build_anomaly_flags(ticks: List[Dict]) -> str:
    """Flag ticks with notable anomalies for the LLM to investigate."""
    lines = ["## ANOMALY FLAGS"]
    lines.append("(Ticks where something unusual happened)")
    lines.append("")

    for t in ticks:
        tick = t.get("tick", 0)
        m = t.get("metrics", {})
        actions = t.get("actions", {})
        flags = []

        unemp = float(m.get("unemployment_rate", 0) or 0)
        if unemp > 0.3:
            flags.append(f"HIGH_UNEMPLOYMENT={unemp:.1%}")

        firm_actions = actions.get("firm_actions", [])
        bankruptcies = actions.get("bankruptcies_this_tick", 0)
        if bankruptcies > 0:
            flags.append(f"BANKRUPTCIES={bankruptcies}")

        total_fires = sum(len(fa.get("fired_ids", []) or []) for fa in firm_actions)
        if total_fires > 5:
            flags.append(f"MASS_LAYOFFS={total_fires}")

        regime = t.get("events", {}).get("regime_events", []) or []
        if regime:
            flags.append(f"REGIME_EVENTS={len(regime)}")

        # Check for firms with zero revenue
        firms = t.get("firms", [])
        zero_rev = sum(1 for f in firms if not f.get("is_baseline") and float(f.get("last_revenue", 0) or 0) < 1)
        if zero_rev > 0:
            flags.append(f"ZERO_REV_FIRMS={zero_rev}")

        # Check for negative cash firms
        neg_cash = sum(1 for f in firms if not f.get("is_baseline") and float(f.get("cash_balance", 0) or 0) < 0)
        if neg_cash > 0:
            flags.append(f"NEGATIVE_CASH_FIRMS={neg_cash}")

        # Households with health < 0.3
        households = t.get("households", [])
        sick = sum(1 for h in households if float(h.get("health", 1) or 1) < 0.3)
        if sick > 0:
            flags.append(f"CRITICALLY_SICK_HH={sick}")

        if flags:
            lines.append(f"  t{tick}: {' | '.join(flags)}")

    if len(lines) == 3:
        lines.append("  (none)")

    return "\n".join(lines)


# â”€â”€ Main Pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_digest(config: Dict, ticks: List[Dict]) -> str:
    """Build the complete compact digest."""
    sections = []

    sections.append("# ECOSIM AUDIT DIGEST")
    sections.append("=" * 60)
    sections.append("This is a compressed audit of a simulation run.")
    sections.append("All data is authoritative. Use it to identify issues,")
    sections.append("anomalies, and areas for improvement in the simulation code.")
    sections.append("")

    sections.append(build_config_section(config))
    sections.append("")
    sections.append(build_money_conservation_digest(ticks))
    sections.append("")
    sections.append(build_anomaly_flags(ticks))
    sections.append("")
    sections.append(build_sparklines(ticks))
    sections.append("")
    sections.append(build_macro_timeseries(ticks))
    sections.append("")
    sections.append(build_actions_digest(ticks))
    sections.append("")
    sections.append(build_government_digest(ticks))
    sections.append("")
    sections.append(build_bank_digest(ticks))
    sections.append("")
    sections.append(build_firm_digest(ticks))
    sections.append("")
    sections.append(build_household_digest(ticks))
    sections.append("")
    sections.append(build_diagnostics_digest(ticks))
    sections.append("")
    sections.append(build_events_digest(ticks))

    return "\n".join(sections)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for dense tabular data."""
    return len(text) // 4


def parse_args():
    p = argparse.ArgumentParser(description="EcoSim Audit Digest Pipeline")
    p.add_argument("input", help="Path to JSONL audit file")
    p.add_argument("--output", "-o", help="Output path (default: stdout)")
    p.add_argument("--max-tokens", type=int, default=0,
                   help="Target max tokens (0=no limit). Will trim household detail if needed.")
    return p.parse_args()


def main():
    args = parse_args()

    print(f"Loading {args.input}...", file=sys.stderr)
    config, ticks = load_audit(args.input)
    print(f"Loaded {len(ticks)} ticks", file=sys.stderr)

    digest = build_digest(config, ticks)
    tokens = estimate_tokens(digest)
    print(f"Digest: {len(digest):,} chars, ~{tokens:,} tokens", file=sys.stderr)

    if args.max_tokens and tokens > args.max_tokens:
        print(f"Warning: digest exceeds target ({tokens} > {args.max_tokens} tokens)", file=sys.stderr)
        print(f"Consider running with fewer ticks or households", file=sys.stderr)

    if args.output:
        Path(args.output).write_text(digest, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(digest)


if __name__ == "__main__":
    main()

