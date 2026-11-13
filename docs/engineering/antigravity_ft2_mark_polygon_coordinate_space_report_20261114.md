# Architecture report: FT2/FT3 mark-to-room coordinate-space binding (shadow ownership authority)

Author lane: AntiGravity. Base: #4301 `29d42b5be`. Scope: `pb_source_floor_finish_occurrence_ownership_shadow.py` only. Default-off/opt-in, candidate-only.

## Observed repository behaviour
- `evaluate_source_floor_finish_ownership_shadow` tests `finish_mark.mark_center_pt` against a caller-supplied `internal_face_polygon_pdf_pts` by point-in-polygon + 2.5 pt clearance. Neither `finish_mark.page_id` nor any polygon page/viewport is compared (selector.page_id is not compared to the mark either). Existing positives deliberately use a `page_11` mark with a `page_07` selector.
- Reproduced (synthetic): a mark with `page_id="11"` inside coordinates of a polygon intended for `page 7` returns `CANDIDATE` / `source_floor_finish_ownership_resolved`. Coordinates from different views coincide by chance only. The consumer (`pb_cross_view_floor_finish_authority`) already documents this exact hazard for p11-mark -> p7-floor and quarantines it; this shadow module does not.
- Record is always `CANDIDATE`, `commercial_projection_allowed=False`, `takeoff_eligible=False`, doorway/face/under-wall flags False. Competing marks are caller-supplied (completeness unproven); cross-page competing marks currently abstain (conservative).
- Only in-repo non-test consumer: `pb_source_full_plan_recovery_engine_shadow.py` (shadow).

## Inference
- Without a declared polygon coordinate space, "mark inside room" is not source correspondence; it is a numeric coincidence across views. Not a quantity/customer defect today (candidate-only), but it lets a spoofed or wrong-view mark manufacture an ownership candidate.

## Proposed change (implemented)
- New opt-in keyword `polygon_page_id`. When supplied, the mark's page must equal it (stripped, non-empty str) else `ABSTAINED` with existing `source_lineage_mismatch`. Omitted -> byte-identical legacy output (record_id and reason_codes unchanged; tested).
- Not changed: signature order, existing positives, thresholds (2.5 pt clearance/snap), 20k cap, doorway/face authentication (still False), consumer call site.

## Not done / next gate (needs owner decision)
- Making `polygon_page_id` required and wiring `pb_source_full_plan_recovery_engine_shadow` to pass the real SourceRoomFace page requires deciding how a p11 mark legitimately corresponds to a p7 room (existing cross-view correspondence producer). Not guessed here.
- Placeholder `source_word_address=(0,0,0)` default is accepted; mark is not bound to an actual source word receipt.
- Competing-mark list completeness is caller-asserted.

## Benchmark observations not used
None. No expected BOQ/benchmark value, filename or project name was an input. No private PDF used; synthetic proof only.
