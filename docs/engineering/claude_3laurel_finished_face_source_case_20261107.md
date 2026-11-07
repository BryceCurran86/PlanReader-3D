# 3Laurel finished-face source case: bedroom and robe partition (shadow, 2026-11-07)

Assignment (MAX, #4135 and #4230): establish whether the doorway-closed ring recovered for the single bedroom/robe partition follows the exposed INTERNAL finished wall face, a structural/core face, or is unresolved, from the original's own wall build-up statements, details and figured witnesses; then either let the existing issuer consume one bounded face or record the precise missing fact with an explicit noncommercial ABSTAIN and a regression. Counts, sheet ids and reason codes only: this note quotes no drawing text and gives no drawing measurement.

## 1. Observed repository behavior (main `cba3d62e3`)
- `pb_layered_wall_doorway_room_ring_shadow` recovers a room as the free region between the faces of DRAWN wall-layer strips. A chord closes a doorway; it is never a wall owner.
- With the ring controls on, the unchanged issuers publish two numbers for such a face: the same-view documented width x depth (the box between the drawn faces) and, through `build_source_room_area_bridge`, the polygon at the physical scale. Both were FIRM candidates on the original; the customer projection refused them only for missing scale metadata (#4232's seam).
- Nothing in the chain asked which face of the wall the drawn strip is.

## 2. Source observations on the original (SHA `014e9f68...`, 18-sheet index)
- A0.7 (Section A-A) carries one wall build-up statement for internal walls: a frame specification plus an internal lining specification, with an "unless otherwise noted" scope and a wet-area variant. It is read through the existing text authorities, every word proved (`WallBuildUpStatement`, one statement, one block). Code `internal_wall_build_up_statement_present`.
- On A0.3 (floor plan) the drawn internal wall strip thickness at the page scale equals the STATED FRAME thickness, not frame plus lining. Code `drawn_strip_is_frame_not_finished_face`. The ring therefore follows the frame (core) face; the statement gives the lining beyond it for internal walls, so the exposed finished face on those edges is inside the polygon by the stated lining.
- Boundary of the two recovered faces, by edge class (receipts `layered_finished_face_receipts`): the large majority of wall edge length is an internal strip equal to the stated frame (bedroom part about 85%, robe part about 98% of wall edge length); the rest is one external-wall run (bedroom part only), two short strips that are not the frame thickness, and two small unclassified wall-layer fills. Doorway/threshold chords are not wall.
- Codes that remain open: `external_wall_internal_lining_not_stated` (A0.7 defers the external build-up to a notes page / specification that is not among the 18 indexed sheets: `referenced_specification_not_in_set`), `internal_strip_thickness_not_the_stated_frame` and `wall_fill_not_classified` (the wardrobe-front end blocks, no statement names them), `room_wet_area_status_not_established` (the statement has a wet-area variant and no room-kind authority says the room is dry).
- The dimension-basis note ("from the plasterboard, not the frame") is on the joinery detail sheets only; it does not govern the plan. The plan's figured witnesses end on the strip faces.

## 3. Inference
The polygon edge on a stated-frame internal strip is a frame face with a stated lining beyond it, not the finished face. The finished face cannot be resolved for either part: the bedroom part has an external wall run with no stated internal lining, and both parts have end blocks and fills no statement classifies. The wardrobe finish is unrelated and stays unresolved.

## 4. What was built (all default-off; no default behavior changes)
- `pb_wall_build_up_statement_shadow.py`: `parse_wall_build_up_statement` (pure; one internal-wall statement or none) and `collect_wall_build_up_statements` (a block is used only if every word is proved by the text-integrity authority or the raster corroboration authority).
- `pb_layered_wall_face_identity_shadow.py`: `wall_strip_facts`, `classify_ring_face_identity` / `classify_record_face_identity`. One resolved class (a strip on an internal-wall layer whose thickness at the page scale equals the stated frame, within the repository's 0.05 pt noise bound at that scale); every other edge is an explicit unresolved class. The page scale is an input from the existing physical-scale authority, never derived here; the lining comes only from an authenticated statement.
- `layered_finished_face_gate` (explicit boolean, needs the ring control; with `layered_finished_face_statement_pages` naming the pages to read): a gated ring face is noncommercial. The same-view issuer refuses the documented area (`same_view_layered_ring_finished_face_not_established`), the room-area bridge withholds the face (`withheld_room_refs`, remove-only), documented evidence for gated faces is not passed on, and the claim carries per-face receipts.
- Even a face whose identity RESOLVES stays noncommercial in this change: no finished polygon is applied yet, so measuring the frame-face polygon would over-state the net finished area. That is regression-tested end to end.

## 5. Result on the original
The claim with every control on and the statement page named yields two canonical rooms, no room-area, floor, floor-finish or ceiling-lining quantity, and two unresolved receipts carrying the codes above. The documented route is refused, the scaled polygon route is withheld, and `same_view_layered_ring_finished_face_not_established` is the first failure.

## 6. What would resolve it
1. The internal lining of the external wall run: the notes page / specification A0.7 refers to, or a wall-type legend or section that states it.
2. What the wardrobe-front end blocks and the two small fills are (frame, jamb, joinery) and whether they are lined.
3. An authority that states the room is not a wet area (the statement's wet-area lining must not be applied to a dry room, and the general lining must not be applied to a wet one).
4. Then, and only then, a finished-polygon applier (offset each lined internal edge by its stated lining, none at a chord) feeding the existing physical-scale issuer, with the original's own figured witnesses re-based to that face. Not implemented here.

No quantity, customer row or score is claimed. The 20,000 primitive cap, the 2.5 pt snap, the frozen benchmark and every scale/length/height authority are unchanged.
