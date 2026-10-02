# Seller concentration with and without `fix_seller_choice_noise`, 2026-10-02

Read-only measurement for an owner decision. Nothing in the engine changed; the flag stays off by default.

`CONFIG.households.fix_seller_choice_noise` (remediation phase 6, audit B32) replaces the household seller-choice tie-break, a ±0.25 utility vector indexed by awareness-pool position, with noise hashed per (household, category, firm) within ±`tie_break_scale` (1e-3), and makes switching friction a margin of the current seller's absolute utility, so it does not invert for negative utilities. The question was whether turning it on concentrates sales on fewer sellers.

- Code: branch `fix/overdraw-services-loans-flags` at `31394ca` (engine as of `da964b1`: shopping reserve and minimum food first, demand-triggered Services loans, `fix_distress_wage_cut_persists` and `fix_preference_applied_once` on, inflation on).
- Settings: 1,500 households, `create_large_economy(1500, 10)`, legacy payment sequence, 300 ticks, seeds 42, 7 and 11, flag off and on (six separate processes).
- Per tick, per category (Food, Services), over every firm in the category including baseline firms: Herfindahl index of units sold (sum of squared unit shares; 1/N for an even split, so about 0.045-0.05 for these 20-24 sellers), the largest firm's unit share, and firms that sold nothing. Window values average the ticks, then the seeds; brackets give the per-seed range for each side.

## Food

| metric | 11-40 | 41-100 | 101-200 | 201-300 |
|---|---|---|---|---|
| HHI, off → on | 0.129 → 0.129 (off 0.127-0.130; on 0.127-0.130) | 0.073 → 0.073 (0.072-0.074; 0.072-0.076) | 0.065 → 0.066 (0.063-0.067; 0.064-0.069) | 0.062 → 0.061 (0.060-0.064; 0.060-0.063) |
| top firm share | 0.165 → 0.164 | 0.108 → 0.105 | 0.111 → 0.112 | 0.120 → 0.117 |
| firms with zero sales | 1.0 → 1.0 | 0.1 → 0.1 | 0.1 → 0.1 | 0.1 → 0.1 |
| firms | 21.6 → 21.6 | 21.9 → 21.7 | 21.9 → 21.4 | 24.0 → 23.6 |

## Services

| metric | 11-40 | 41-100 | 101-200 | 201-300 |
|---|---|---|---|---|
| HHI, off → on | 0.142 → 0.142 (off 0.139-0.146; on 0.139-0.146) | 0.072 → 0.072 (0.068-0.078; 0.069-0.077) | 0.063 → 0.061 (0.061-0.064; 0.057-0.063) | 0.064 → 0.063 (0.058-0.067; 0.061-0.066) |
| top firm share | 0.177 → 0.177 | 0.111 → 0.112 | 0.098 → 0.096 | 0.093 → 0.097 |
| firms with zero sales | 1.1 → 1.1 | 0.2 → 0.2 | 0.2 → 0.1 | 0.0 → 0.0 |
| firms | 20.3 → 20.3 | 21.2 → 21.4 | 21.1 → 21.6 | 19.0 → 19.4 |

## Firm exits and unemployment

| | 11-40 | 41-100 | 101-200 | 201-300 |
|---|---|---|---|---|
| firm exits (window sum, three-seed mean) | 0.0 → 0.0 | 7.7 → 7.0 | 8.3 → 7.7 | 3.7 → 3.7 |
| unemployment | 29.2% → 29.4% | 40.1% → 39.6% | 39.1% → 38.1% | 39.9% → 39.9% |

## Reading

Turning the flag on does not concentrate sales. In both categories the Herfindahl index and the top seller's share move by at most 0.004 in any window, inside the seed range of either side, and the number of firms selling nothing is unchanged. Firm exits are 0-0.7 lower per window with the flag on, also within seed noise for three seeds. Sales are fairly even in both settings once private firms have entered (HHI 0.06-0.07 against about 0.045-0.05 for an even split); the higher values in ticks 11-40 come from the few warm-up and early-entry sellers, not from the flag.

Three seeds only; a change smaller than the seed range is not distinguishable from noise. Throwaway scripts (`m_run.py`, `conc_table.py`) are in the task workspace, not the repository.
