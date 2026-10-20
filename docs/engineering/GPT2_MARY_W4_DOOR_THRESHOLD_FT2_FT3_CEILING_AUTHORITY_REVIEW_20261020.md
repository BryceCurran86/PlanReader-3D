# GPT2 — Maryborough physical wall, doorway-threshold, FT2/FT3 and ceiling authority review

**2026-10-20 • Architecture-first review only • Owner source SHA** `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`

This is the required first deliverable under `AGENTS.md`. **No production acceptance code or frozen benchmark truth changes are in this PR.** Approval/review of these authority boundaries is required before implementation; no quantity is declared FIRM by this report.

## 1. Read and traced

- `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` §§5,8,9,13, and `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`.
- `pb_wall_room_topology_wall_assembly.assemble_wall_candidates` → `pb_source_room_face_authority` → `pb_live_canonical_room_composition` → `pb_gpt2_w4_original_floor_handoff.audit_gpt2_w4_bound_original_floor`.
- `pb_source_open_passage_connection_shadow.evaluate_source_open_passage_connection_shadow` → `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow` → `pb_source_material_semantic_authority.SourceMaterialSemanticAuthority`.
- Cross-sheet original-source `tools/diag_ft3_p11_p7_floor_correspondence.py` and `tools/diag_gpt2_source_finish_floor_handoff_shadow.py`; source-only, NOT floor identity authorities.
- Signing seams: `pb_live_floor_area_quantity_publication.publish_live_floor_area_quantities` (already FIRM room area only), existing floor-finish `QuantityEvidence` → `pb_live_floor_finish_area_source_closed_export` → `pb_live_floor_finish_customer_projection.project_live_floor_finish_customer_rows` → `pb_source_closed_run_export.seal_source_closed_run`. Ceilings use `pb_live_ceiling_area_quantity_publication._publish_one` → ceiling source-closed exporter/customer projection; ceiling zone must be independently proved.

## 2. Observed repository behavior — actual bugs / original facts

**A. Open-passage structural obstruction bug.** `pb_source_open_passage_connection_shadow._segment_intersects_passage` checks essentially collinear wall-segment overlap only: a transverse wall crossing the doorway's interior is not found. `evaluate_source_open_passage_connection_shadow` can then return a positive shadow passage despite actual crossing wall ink. No structural W4 source owner is authenticated by caller-created `SourcePassageWallEdge`.

**B. Threshold ownership gap.** `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow` uses `doorway_authenticated = bool(doorway_transitions)`, with no geometric intersection/alignment/proven original physical door/source owner. A caller can submit one displaced or foreign `SourceDoorwayThreshold` and receive `doorway_transition_authenticated=True`. It also sets `terminates_at_internal_faces=True` / `under_wall_finish_excluded=True` for any valid caller polygon, without W4 binding evidence. Even positive `status=CANDIDATE` must not be called authenticated physical ownership.

**C. Cross-sheet floor owner still unproved.** `audit_gpt2_original_cross_sheet_ring_correspondence` explicitly declares geometric-ink candidate only; the independent `audit_gpt2_w4_bound_original_floor` requires a unique publisher-issued W4 room face, actual wall-edge member receipts, clean ownership, exact source polygon and scope. Figure values or name similarity cannot replace it.

**D. Original source census, verified from PDF bytes in isolated private runtime:** 31 pages with exact SHA above; pages 7,9,11 have 90° rotation, and native words are in unrotated PDF coordinate frame. Page-11 source contains eight *plan* FT2 and five *plan* FT3 instances, plus one legend instance of each. Source material definitions are different: FT2 800×400 STOCKTON WHITE R10; FT3 600×600 DURA GREY min R12, epoxy grout, 100mm aluminium skirting. Page 9 contains 12 native IPF1 occurrences including schedule; native plan IPF1 count is 11. These numbers are a source census only; no material-to-floor/ceiling polygon identity is inferred.

**E. Existing real areas must be preserved.** Previously sealed generic Maryborough OFFICE 9.05352 m² and FOOD PREP 13.270425 m², among other source rooms, do not become distinct FT2/FT3 tiling quantities merely by multiplying figured dimensions again. Any new finish `QuantityEvidence` must reuse the independently sealed floor owner and avoid reissuing gross room area under multiple finish material IDs.

## 3. Inference — what the bugs can corrupt

- Missed transverse obstruction could manufacture a doorway connecting rooms across an actual wall.
- Unproved threshold can fabricate a material transition inside a polygon; failing to close actual W4 face ownership can overcount tiles beneath wall footprints.
- A label-centred nearest-match on page 11 can incorrectly bind legend FT2/FT3 or a separate adjacent room; physical registration is required, not coordinates alone.
- A source IPF1 mark does not give ceiling thickness, area or ownership absent a W4/ceiling zone and compatible signed room-floor or ceiling area.

## 4. Proposed reviewed implementation, strictly shadow first

1. **Physical opening obstruction:** Upgrade `_segment_intersects_passage` to detect both positive interior crossing and collinear source-wall overlap, retaining genuine door jamb contacts only at endpoints. Keep all source-wall contenders; abstain if obstruction or original W4 parent is ambiguous. Do not change global 2.5pt snap.
2. **W4 edge + doorway threshold owner:** Add a typed source receipt to connect exactly one published `SourceRoomFaceRecord`, its `boundary_wall_edges` and two W4 physical jambs to an original doorway threshold *source stroke*. Reject a threshold that is outside the polygon edge, parallel-displaced, crosses a wall, belongs to another page/revision, or has competing doorway owners. A geometric `SourceDoorwayThreshold` object alone **never** grants source authentication.
3. **FT2/FT3 membership:** Consume the existing `SourceMaterialSemanticAuthority` original definition and complete eligible page-11 occurrence census; use source W4-backed p11↔p7 physical polygon registration, exclude schedule marks and all contested regions, and preserve unique physical floor ID per finish mark. Same finish flows through true open passages; different finish transitions at source-owned doorway threshold; neither is a fabricated wall.
4. **Independent ceiling zones:** Consume original page-9 IPF1 / grid / soffit scope; require closed source-owned zone and independent FIRM measurement authority before ceiling quantity issuance. Do not assume ceiling equals floor or that every IPF1 mark belongs to one polygon.
5. **Publication only after typed authority review:** Existing live canonical floor/ceiling `QuantityEvidence` publishers and source-closed signers only; require exact document/revision/SHA/snapshot/decision_scope/physical floor/mark/page equivalence and original customer parity. No new quantity family, no bypass of existing FIRM gates.

## 5. Required proof, tests and safety

Synthetic: authentic source W4-bound doorway threshold, transverse crossing obstruction, collinear obstruction, wall-end legitimate doorway, displaced/foreign-page/unproved threshold, adjacent dissimilar finish/no threshold, same-finish open-passage continuity, duplicated/conflicting FT2/FT3 marks including legend, exact-FLOOR polygon vs false furniture/quads, missing W4 wall face, competing page registration and ambiguous 1620 dimension witnesses; independent IPF1 ceiling zone; rotation/translation/split invariance and no input mutation.

Original source: SHA-pinned 31-page original PDF, independent page7/11 W4-source ring/threshold/finish receipt replay and page9 RCP ceiling zone, preserving original signed quantities, customer rows and exact source replay fingerprint. Run current-head Python CI before requesting owner review. Only then consider guarded source-closed FIRM finish/ceiling areas and GPT3 V2 evaluation. Review requested before code as required by `AGENTS.md`.

## 6. Frozen benchmark observations that **must not** influence implementation

Historical development 8/51 is not a live score and may not select floors or calibrations. Never use the frozen truth, known m², labels, nearest FT mark, 1:50 title-block text, W5 visual loops, arbitrary threshold flags, or user notes to manufacture publisher authority. No benchmark-scoring code/measurements, original PDFs, 20,000 raster cap, wall snap, customer output, existing firm quantities or PRs from other agents are touched in this architecture proposal.
