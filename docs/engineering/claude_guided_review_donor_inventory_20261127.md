# Guided review: donor inventory for the consolidated stack

Date: 2026-11-27. Order: #4764 7208521396 (choice (b): minimal #4795 screen patch and exact donor inventory, no wholesale merge).

Donor: #4795 head `7fb0872c2e` (base `cc8de73ea3`). Current `main` `6340ebd322` and #4806 `784179ebbe` have not changed any of these paths since that base, so each file is taken as the exact blob below.

| path | change | blob | lines (+/-) |
| --- | --- | --- | --- |
| `pb_guided_plan_review.py` | new | `904cfd515a32` | +294 |
| `pb_guided_plan_review_native.py` | new | `419f49b494df` | +208 |
| `pb_guided_plan_review_snap.py` | new | `3bc51028f51d` | +116 |
| `pb_guided_plan_review_ui.py` | new | `dba297f14cd3` | +266 |
| `pb_guided_review_source_questions.py` | new | `0812cf4588cb` | +1552 |
| `pb_planreader_3d_app.py` | tab hunk | `9f22cb6a0df7` | +8/-1 |
| `planreader_line_mapper/__init__.py` | editor options | `7dfce4b962d9` | +26 |
| `planreader_line_mapper/frontend/index.html` | snap and focus | `1dad2d799c11` | +129/-5 |
| `tests/test_guided_plan_review.py` | new | `9faf0d8628d9` | +127 |
| `tests/test_guided_plan_review_native.py` | new | `cac9b041fb3d` | +139 |
| `tests/test_guided_plan_review_snap.py` | new | `b05d058dbbe6` | +123 |
| `tests/test_guided_review_source_questions_v1.py` | new | `5c5da63410c7` | +375 |

Needs: #4801 (already on `main`) and, from #4810, the preview `piece_cache` argument and `pb_guided_review_recalculation.py`.

Apply on top of those, from the repository root:

1. `git checkout 7fb0872c2e -- <the 12 paths>`
2. `git show <#4810 head>:docs/engineering/claude_review_screen_wiring_4795.patch | git apply` (adds the recalculate button, shares the session cache with the single-page trace, and its screen test)

Verified on a clean copy of #4810 with only these donors and the patch: 101 tests pass (the donor tests, the review consumer, the piece-cache preview tests and the Streamlit screen run).

Not verified: use in a real browser; use on original drawings.
