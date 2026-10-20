"""Summarize paired by-window panels written by ``run_household_window_panel.py``.

Usage (from backend/):
    python tools/analysis/summarize_household_window_panel.py --base off_*.json --test on_*.json

Pairs runs by seed. For every metric and window (1-100, 101-200, 201+) it
prints the base and test means, the paired difference (mean and range over
seeds), and, for GDP, unemployment, prices and happiness, the per-window
standard deviation and coefficient of variation of the weekly series. The
government balance also gets its window minimum.
"""

from __future__ import annotations

import argparse
import glob
import json

import numpy as np

WINDOWS = ((1, 100), (101, 200), (201, 10**9))
VOLATILITY = ("gdp", "unemployment", "price", "happiness_mean")


def _load(pattern):
    runs = {}
    for path in sorted(glob.glob(pattern)):
        data = json.load(open(path))
        runs[data["seed"]] = data
    return runs


def _series(run, key, lo, hi):
    out = []
    for row in run["rows"]:
        if lo <= row["t"] <= hi and row.get(key) is not None:
            value = row[key]
            out.append(value)
    return out


def _metrics(run):
    keys = [k for k, v in run["rows"][-1].items() if k != "t" and (isinstance(v, (int, float)) or isinstance(v, list))]
    return keys


def summarize(base, test, decile_keys=(0, 4, 8)):
    seeds = sorted(set(base) & set(test))
    lines = [f"paired seeds: {seeds}; windows by tick: 1-100, 101-200, 201-{max(r['t'] for r in base[seeds[0]]['rows'])}"]
    keys = _metrics(base[seeds[0]])
    for key in keys:
        is_list = isinstance(base[seeds[0]]["rows"][-1][key], list)
        subkeys = [(key, i) for i in decile_keys] if is_list else [(key, None)]
        for name, idx in subkeys:
            label = f"{name}[p{(idx + 1) * 10}]" if idx is not None else name
            cells = []
            for lo, hi in WINDOWS:
                b, t, d, bsd, tsd, bcv, tcv, bmin, tmin = [], [], [], [], [], [], [], [], []
                for s in seeds:
                    sb = _series(base[s], name, lo, hi)
                    st = _series(test[s], name, lo, hi)
                    if idx is not None:
                        sb = [v[idx] for v in sb]
                        st = [v[idx] for v in st]
                    if not sb or not st:
                        continue
                    mb, mt = float(np.mean(sb)), float(np.mean(st))
                    b.append(mb)
                    t.append(mt)
                    d.append(mt - mb)
                    bsd.append(float(np.std(sb)))
                    tsd.append(float(np.std(st)))
                    bcv.append(float(np.std(sb) / abs(mb)) if mb else float("nan"))
                    tcv.append(float(np.std(st) / abs(mt)) if mt else float("nan"))
                    bmin.append(float(np.min(sb)))
                    tmin.append(float(np.min(st)))
                if not d:
                    cells.append("n/a")
                    continue
                cell = (f"{np.mean(b):.4g} -> {np.mean(t):.4g} (diff {np.mean(d):+.4g}, "
                        f"range {min(d):+.4g}..{max(d):+.4g})")
                if name in VOLATILITY:
                    cell += f" sd {np.mean(bsd):.3g}->{np.mean(tsd):.3g} cv {np.mean(bcv):.3f}->{np.mean(tcv):.3f}"
                if name == "gov_balance":
                    cell += f" min {np.mean(bmin):.4g}->{np.mean(tmin):.4g}"
                cells.append(cell)
            lines.append(f"- {label}: " + " | ".join(f"[{w}] {c}" for w, c in zip(("1-100", "101-200", "201+"), cells)))
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", required=True)
    p.add_argument("--test", required=True)
    args = p.parse_args(argv)
    print(summarize(_load(args.base), _load(args.test)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
