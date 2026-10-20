"""Realized skill-rank loss after a year out of work (households skills PR).

Calibration check for ``skill_gain_depreciation_annual_range`` against Edin &
Gustavsson (2008): a year of non-employment moves a worker about 5.5
percentile points down the skill distribution. Runs ONE arm in this process,
seeded like ``regression_snapshot._set_seed``, and prints JSON: the mean
percentile-rank drop over 52 weeks for households employed at week t-52 and
unemployed for all of weeks t-51..t (t-52 >= 60, after warm-up), with peers
still learning, plus the realized yearly learning share of the skill gap for
households employed through weeks 100-151.

Usage (from backend/):
    python tools/analysis/run_households_skill_rank_loss.py --seed 42 --range 0.5 0.9
    python tools/analysis/run_households_skill_rank_loss.py --seed 42 --off
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
for _path in (BACKEND_ROOT, BACKEND_ROOT / "tools" / "runners", BACKEND_ROOT / "tools" / "benchmarks"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from config import clone_config, use_config  # noqa: E402
from regression_snapshot import _set_seed  # noqa: E402
from run_large_simulation import create_large_economy  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--ticks", type=int, default=260)
    p.add_argument("--households", type=int, default=1000)
    p.add_argument("--range", type=float, nargs=2, default=None)
    p.add_argument("--off", action="store_true")
    args = p.parse_args(argv)
    cfg = clone_config()
    cfg.households.skills_dynamics = not args.off
    if args.range:
        cfg.households.skill_gain_depreciation_annual_range = tuple(args.range)
    with use_config(cfg):
        _set_seed(args.seed)
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=args.households, num_firms_per_category=5)
        skills, employed = [], []
        for _ in range(args.ticks):
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            skills.append([h.skills_level for h in economy.households])
            employed.append([h.is_employed for h in economy.households])
    s, e = np.array(skills), np.array(employed)
    n = s.shape[1]
    rank = np.argsort(np.argsort(s, axis=1), axis=1) / (n - 1) * 100.0
    losses = []
    for t in range(112, s.shape[0]):
        spell = (~e[t - 51:t + 1]).all(axis=0) & e[t - 52]
        losses.extend((rank[t - 52, spell] - rank[t, spell]).tolist())
    stay = e[100:152].all(axis=0)
    learn = ((s[151] - s[99]) / np.maximum(1.0 - s[99], 1e-9))[stay]
    print(json.dumps({
        "seed": args.seed, "off": args.off, "range": args.range, "spells": len(losses),
        "rank_loss_pts": float(np.mean(losses)) if losses else None,
        "learning_share_of_gap_per_year": float(np.mean(learn)) if stay.any() else None,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
