# Services experiment summaries

These compact aggregates accompany the Services pricing, space, staffing and repayment PR. They are copied by script from the validated external analysis files, not manually rounded report tables. `manifest.json` records source-file hashes, input-analysis hashes, CSV hashes, settings and distinct seed counts. Full raw case data, frozen intermediate source variants and research observers remain in the author's external evidence directory recorded in the reports; they are **not bundled here**. These CSVs alone are not a fully reproducible raw experiment archive.

- [SERVICES-01 versus main](services01-main-comparison.csv): 48 runs, three distinct seeds, two timing repeats. `baseline` is original main; `candidate` is SERVICES-01, before the repayment follow-up.
- [Component isolation](component-comparison.csv): eight combinations, three seeds, reference `income_first` at 1,000 households. P = pricing, E = staffed expansion, H = retained staffing/patience. Main corresponds to P0E0H0; SERVICES-01 to P1E1H1. Two additional loan-return replays are documented in the component report.
- [Repayment follow-up](repayment-comparison.csv): SERVICES-01 (`before`) versus SERVICES-02 (`repayment`), 16 runs, three 1k seeds and one 10k seed per named sequence.

Rows are week-80 arithmetic means across the listed distinct seeded trajectories. Timing repeats do not add independent economic observations. Prices/GDP are nominal, Services units are real quantities, and employment counts households. A missing Treasury-debt field in the older panels is blank, not zero. The repayment comparison does not establish a 5% runtime-budget pass.

Interpretation, timing, accounting perimeter and review dispositions are in [SERVICES-01 validation](../../SERVICES_DECISION_VALIDATION.md), [component results](../../SERVICES_COMPONENT_RESULTS.md) and [repayment results](../../SERVICES_REPAYMENT_RESULTS.md).

The committed contract tests exercise fixed-cost pricing, both named payment sequences, actual matching and funded payroll, both expansion routes, public slot delivery, recovery-evidence timing, repayment counting and payoff. Run them using the repository's pytest instructions. The default full backend suite requires a Unix signal implementation for its server timeout tests; this package was validated under Ubuntu/WSL as recorded in the reports.

Final pre-publication default suite: **1221 passed, 2 skipped, 8 research deselected, 1 xfailed**, including all 55 new Services regressions. The manifest records the full log hash. The prompt golden was updated only after reproducing the preceding source's digest and preserving both economic prompt snapshots, as described in the repayment report.
