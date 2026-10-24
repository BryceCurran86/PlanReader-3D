# Cursor — doorway/finish ownership flags remain fail-open on main

**2026-10-20 • Architecture-first note. Shadow only. No FIRM, no PDF commit, no frozen-truth change.**

## Observed

- GPT2 independently reviewed Cursor #3466 HEAD `5d685e4c` and asked that `doorway_transition_authenticated`, `terminates_at_internal_faces`, and `under_wall_finish_excluded` stay **False** until typed document/revision/SHA/snapshot/page owners are independently re-resolved. Invented string IDs are not owners.
- `#3472` already merged on main: `_threshold_aligns_with_polygon_boundary` requires both endpoints within 2.5 pt of a finite polygon edge, and open-passage obstruction includes transverse crossing. That addresses the overlong-overlap geometry GPT2 reproduced against #3466.
- Current main `evaluate_source_floor_finish_ownership_shadow` still hardcodes `terminates_at_internal_faces=True` and `under_wall_finish_excluded=True`, and sets `doorway_transition_authenticated=True` from geometry alignment of a caller-supplied `SourceDoorwayThreshold`. No `SourceRoomFaceAuthority`, W4 jamb, or native stroke receipt is consulted.

## Inference

Geometry of a caller chord is not measurement or finish-termination authority. A later wiring that actually re-resolves owned face/jamb/stroke receipts may raise these flags; this shadow evaluator must not.

## Proposed

Keep all three flags False in this module. If a threshold chord is geometrically on a polygon edge, emit a diagnostic reason only (`doorway_threshold_geometry_aligned_unauthenticated`). Add negatives for overhanging and short-overlap chords, and for forged non-empty IDs if any string-id kwargs exist (they must not create True). Do not add a string-id True path. Do not sign FIRM.

## Benchmark observations that must not influence implementation

Office/Food Prep m², FT2/FT3 BOQ values, and expected finish quantities are not inputs.
