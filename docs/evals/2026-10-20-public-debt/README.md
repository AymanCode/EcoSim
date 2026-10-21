# Public debt (G1, PR #43): paired runs, 2026-10-20 (rerun 2026-10-21)

`report.md` is the unedited output of

    cd backend
    PYTHONHASHSEED=0 python tools/benchmarks/run_public_debt_compare.py \
        --main-backend <checkout of main at f86f140>/backend \
        --households 1000 --firms-per-category 5 --ticks 312 --seeds 42 43 44 45 46 \
        --scenarios default stress deep --arms main off on_zero on_buffer on_noint --jobs 6

run on the PR's code. The report opens with its run environment (command, commits, Python and library
versions). Every (scenario, arm, seed) ran in its own process with `PYTHONHASHSEED=0` and `OMP_NUM_THREADS=1`,
seeded with `tools/benchmarks/regression_snapshot.py`'s `_set_seed` after its config was set. Arms: `main` (main
checkout), `off` (this branch, flag off; checked byte-identical to `main` by sha256 of the per-tick rows),
`on_zero` (debt on, borrow back to $0), `on_buffer` (debt on, borrow back to one week of spending) and `on_noint`
(`on_zero` with the weekly interest payment replaced by $0; a decomposition arm, not a policy option).
Windows: ticks 1-100, 101-200, 201-312. Paired differences are arm minus main, mean [min, max] over the five
seeds. Real GDP is GDP divided by the mean price. Liquid wealth is cash + max(0, deposit) (#32's definition);
poverty is liquid wealth below `households.poverty_threshold` ($200).
