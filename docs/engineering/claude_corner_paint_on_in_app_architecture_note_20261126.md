# The app's outline step keeps mitred corner paint again (switch on in the preview)

Date: 2026-11-26. Order: owner approval ("Yes, switch it on") under directive #4764 7172590477 item 4 (reconcile #4714/#4719); claim #4764 7187903101.

## 1. Observed repository behaviour

- The canonical preview's outline step (`attempt_source_native_outer_wall_first`) abstains on 3Laurel source page index 2 (`source_dwelling_region_still_open_to_outside`) on `main`.
- Bisected: it closed before #4623 (2026-11-20) and not after. #4623 correctly stopped bare numbers counting as window labels; on that page 10 of 20 "window" bridges were such numbers, and they had been covering open corners.
- The corners are painted: the strip collector returns the mitred pieces as barrier polygons, which the outline step left out of its topology union.
- Two original-source 3Laurel tests asserting the outline have failed since then; public CI skips private-original tests.

## 2. Change

- #4714 + #4719 + the flush-side tightening: `pb_source_wall_joint_paint_continuity` admits opaque black paint on a named wall layer that is flush with admitted wall strips along two sides on different lines; topology union only, never a bar, owner, length or quantity. Library default unchanged (off).
- `source_native_trace_preview(admit_wall_joint_paint=True)` passes it (explicit boolean; False restores the previous behaviour). The summary gains `external_wall_joint_paint_count` only when pieces were used.
- The three original 3Laurel outline tests call the step the way the app does.
- Untouched: window detection, the strip collectors, quantities, authority, the 2.5 pt snap, the 20,000 cap.

## 3. Verification

- 57 synthetic tests of the corner-paint module and the preview switch; canonical route guard OK.
- Outline and preview tests with originals: 732 passed, 2 failed (the two listed under Limits).
- Originals, counts only: outline step on every page with drawable lines of the 3Laurel and Maryborough sets, off versus on: only 3Laurel source page index 2 changes (abstained to candidate, 13 pieces); the other 48 are identical.
- Canonical preview: with the switch off it is identical to `main` (page indices 2 and 8). On: page 2 gains the outline, rooms (18) and door closures (72) unchanged; page 8 still abstains and only outline-step diagnostics change.

## 4. Limits

- The mechanism needs named wall layers, so drawings without them are unchanged (Maryborough: no pieces on any page).
- `test_original_3laurel_window_preflight_retains_exact_legacy_candidate_set` still fails: it pins the window set from before #4623. Re-pinning needs the owner's decision and a source check of each bridge.
- One setout-dimension "WIN" window bridge reported false on #4135 is not addressed here.
- A Banksia-plan test in `test_exterior_rejected_loop_source_census.py` fails on `main` without this change.

## 5. Benchmark observations that must not influence the implementation

Page indices and counts above are verification observations only. No page, project, count or path index enters code.
