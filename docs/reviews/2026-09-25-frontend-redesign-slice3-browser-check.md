# Phase 2, slice 3: browser and live verification

Date: 2026-09-25. Source checked: `2300e59` on `feat/frontend-redesign-phase2`. After fetching origin, the branch was 45 commits ahead of `origin/main`, with none behind. This completes the browser checks left pending in the earlier [Codex review](2026-09-25-frontend-redesign-slice3-codex-review.md).

## Browser checks

Chrome, frontend on port 5175, at 1280 × 900 and 390 × 844:

- Opened `?view=next&demo&numbers`, `?view=next&demo`, `?view=next`, and the classic dashboard at `/`.
- Compared the numbers sheet with approved mockup 06: rules in force, eight headline numbers, and all six visual groups. Inspected populated desktop demo charts and phone charts with recorded and live values.
- Scrubbed the demo to weeks 72 and 73. Values changed with the clock; week 72 showed the week-70 wealth count as “Year 2, week 18”. At week 72, unemployment was 42/31 in 100, typical pay $46/$58, and town hall cash owed $11,276 / held $80,603.
- Both Run entry points opened the sheet. The sticky phone “Back to the towns” closed it after scrolling. Escape closed it and returned focus to the opener; the stat-card entry returned to its former scroll position.
- A temporary harness rendered four towns from the two demo recordings. At 390px, the rules table was 486px wide inside a 336px scroll area, and the glance values occupied 490px inside 336px. Horizontal scrolling exposed Towns C and D while the document stayed 390px wide. Group summaries and rule explanations remained readable.
- Set up and Run rendered at both widths without page overflow. Classic remained unchanged in the slice diff and connected successfully. Its existing three-column setup is cramped at 390px; it is outside this slice's editable scope.
- No browser console errors or warnings in the inspected app routes or four-town harness.

## Small live run

Backend: `.venv/bin/python -m uvicorn backend.server:app --port 8002`. Used Set up's minimum-wage question, two towns, 200 households per town, one year, generated town seed 87963. No AI provider was used.

1. Started from Set up and reached week 52. The open sheet announced that the year was up.
2. Used “Add a year”. The horizon became 104 weeks and the same towns continued.
3. With the sheet open, observed sales of $12,808/$22,516 at week 59 and $12,673/$25,779 at week 65. The clock and values advanced together.
4. Paused at week 66, opened Town hall, selected Town B, changed “Help for people out of work” from normal to high, and applied it. Its receipt named Year 2, week 15 (week 67).
5. Opened the sheet while still paused: both towns still showed normal benefits at week 66. Resumed for one week and paused again: Town A remained normal; Town B showed high with “changed in Year 2, week 15 (was normal)”. Scrubbing back to 66 and forward to 67 confirmed the exact boundary.
6. Resumed to week 104. The sheet announced “2 years are up.”

No live-backend errors or browser errors occurred. Vite logged one `EPIPE` pair on the classic dashboard's opening connection before the live run; the backend recorded a short-lived socket followed by the working classic socket. The classic dashboard remained online. This development-proxy exception did not recur during the live experiment.

## Differences from the mockup

These are recorded for Ayman; no visual redesign was made during this pass.

- Public works has a full tile, with hires/lay-offs below it across the row; the mockup uses a short public-works note and places hires beside pay.
- Town hall money flows show 26 weeks of paired bars. The mockup shows two horizontal bars for the current week. This makes the implemented money section taller and leaves extra space below the cash plot; its neutral grey legend remains the parked K-M7 item.
- Some tile order and detail differ: sales comes first in the money section's lower row, and the feel meter follows the hardship tiles. The appbar remains active and undimmed. These are existing implementation choices.
- Data-driven differences are intentional: sales explicitly exclude rent, income means taxes, family support includes welcome payments, and happiness is now measured each week. Mockup-only “NEW”, review notes, and the invented example rule change are absent.

No new source defect was found in this pass. The earlier K-M9 absent-housing-diagnostics default, K-M7 cosmetics, legacy repeated-tick cache assumption, and slice-2 deferrals remain unchanged.

## Cleanup and final checks

The temporary mockup copy and four-town harness were deleted. Browser viewport overrides were reset and the test tabs closed. Both servers exited, with no listeners remaining on ports 5175 or 8002. The classic dashboard, `src/main.jsx`, `openwiki/`, and the excluded root files were not edited.

Final commands: full Vitest, ESLint `src/next`, Vite build, full pytest, and Ruff. Results are recorded in the changelog and slice ledger.
