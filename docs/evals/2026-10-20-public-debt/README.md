# Public debt (G1, PR #43): paired runs, 2026-10-20

`report.md` is the unedited output of

    cd backend
    python tools/benchmarks/run_public_debt_compare.py \
        --main-backend <checkout of main at f86f140>/backend \
        --households 1000 --ticks 312 --seeds 42 43 44 45 46 \
        --scenarios deep stress default --arms main off on_zero on_buffer

run on the PR's code (commits up to 54359d0). Every (scenario, arm, seed) ran in its own process, seeded with
`tools/benchmarks/regression_snapshot.py`'s `_set_seed` after its config was set. Arms: `main` (main checkout),
`off` (this branch, flag off; checked byte-identical to `main` by sha256 of the per-tick rows), `on_zero`
(debt on, borrow back to $0) and `on_buffer` (debt on, borrow back to one week of spending).
Windows: ticks 1-100, 101-200, 201-312. Paired differences are arm minus main, mean [min, max] over the five seeds.
Liquid wealth is cash + max(0, deposit) (#32's definition); poverty is liquid wealth below
`households.poverty_threshold` ($200).
