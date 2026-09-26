# Codex review: phase 2, slice 3

Date: 2026-09-25. Reviewer: Codex (gpt-6-astra), taking over under `.superpowers/sdd/HANDOFF-codex.md`.

## Scope and conclusion

Reviewed the Task L completion (`8fe6639..64fab2a`), followed by the whole slice (`12f7ece..64fab2a`, excluding `frontend-react/public/demo/`). Compared the current implementation with the slice-3 plan, the approved spec and mockup-06 rulings, the H–L reports/reviews, and current backend producers. This is a fresh review by the handoff recipient, including self-review of the Task L completion, not a separate reviewer of that completion.

No new Critical or Important source-level defect found within the shipped replay/live paths. Real-browser verification is still required; passing jsdom tests does not establish phone layout or the real server integration.

## Task L fix round

- m1: Added repository tests for scroll-to-top and restore from the stat-card link, live week updates without remount/focus/scroll reset, and opening from that link while Town hall is open.
- m2: The jump bar remains sticky below the measured timeline at phone width. Its links scroll in their own flex child; the labelled back button is a separate sibling, so it cannot scroll off the right edge with the chips. CSS structure and observer visibility are tested. Browser reachability remains to be checked.
- m3: A persistent polite status node in the live sheet announces lost/crashed towns and the run reaching its horizon. It reuses catalog copy and adds a catalog instruction to return to the towns. Tests cover connection loss, server error and completion while scrubbed to an earlier week, through fake sockets.
- m4: The backdrop uses `--nx-backdrop`; the stat-card link's trailing full stop comes from `COPY.numbers.moreEnd`.
- The seven-chart opening test collects cards once, scopes chart-heading queries with `within`, and alone gets 15 seconds with an explanatory comment. No global timeout change.

## Whole-slice review focus

1. **Count freshness:** `countedAt` and `countedSeriesUpTo` use `wealthAsOfTick`, including a missing count-week frame. The week-72 tests assert the week-70 count and label. Tiles, wealth bars and the enlarged chart preserve counts rather than inventing weekly measurements. The glance range excludes warm-up counts.
2. **Older recording:** the old fixture remains unmodified. Missing metric keys flow to null and the sheet's missing-measurement states. Tests exercise the whole sheet and special visuals against it.
3. **Four towns at 390px:** table scroll containers, minimum town-column widths, pinned summaries and row descriptions are covered structurally. This does not replace the pending browser measurement.
4. **Warm-up:** comparison phrases at weeks 5 and 10 say the towns are still being set up. Chart bands and future shading are present. Real rule changes made during warm-up remain visible with the explanatory wording required by the ledger.
5. **Lost town:** the fake-socket integration test keeps the sheet mounted, preserves displayed numbers and marks the town chip and both tables with the loss week. New tests add the polite announcement and preserved focus during ordinary live updates.

## Truthfulness and boundaries

- Verified the six added projection fields against current producers: per-tick household happiness; firm sales excluding rent and firms closed that tick; the four named taxes; household transfers plus the six-week post-warm-up payment; cached cash shares with their count week.
- The protocol discloses excluded taxes, payments and final-tick sales. Frontend income/support copy does not present their difference as net cash flow.
- Debt differences distinguish owing more/less from signed balance differences. Share bars reject zero-total or negative-share states instead of inventing a middle share, and rounding totals exactly $100. Flat-price claims compare raw values and require 13 weeks.
- Enlarged charts keep the default Run-screen chart path opt-in. The sheet and Town hall remain mutually exclusive. New experiment unmounts the sheet; ordinary close returns focus and scroll to the opener.
- No classic-dashboard, `src/main.jsx`, generated OpenWiki, or `backend/tools/llm/llm_government.py` edits were made in this continuation. The three excluded root files remain untracked. AI mayor work was not started.

## Validation so far

- Node 22: full Vitest twice consecutively, 57 files / 583 tests each; ESLint `src/next`; Vite production build. All pass.
- Backend: `.venv/bin/python -m pytest -q` passes (609 passes, one expected failure); Ruff passes.
- npm needed a writable cache (`npm_config_cache=/tmp/ecosim-npm-cache`) because the default cache is outside this session's writable roots.
- The workspace `.git` is read-only in this session. Commit `64fab2a` was made in a temporary checkout of the same branch; its eight changed files were byte-compared with the tested workspace. No push has occurred yet.
- OpenWiki's approved workflow requires its OpenRouter key. The CLI is installed but that key is not available in the session; no generated page was hand-edited. Refresh remains due.

## Existing reviewed exceptions

The ledger's parked K-M9 housing diagnostic default, K-M7 grey flow key/cash-card whitespace, and append-only tile-cache assumption remain unchanged. Baseline calibration and the pre-existing 721–1099px Town hall/appbar overlap remain owner decisions. Earlier slice-2 deferrals remain deferred.

## Browser verification blocker

The dev server started successfully on 5175 and was stopped after browser access was denied. The browser approval review reported permission declined for `http://localhost:5175` and forbade alternate routes. An explicit access question is pending with Ayman. No browser screenshot, console-clean claim or real live-run completion is claimed by this review.
