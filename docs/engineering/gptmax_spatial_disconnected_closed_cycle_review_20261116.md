# GPT MAX spatial-subdivision review: disconnected closed wall cycles (16 November 2026)

## Source and ownership

Read AGENTS.md, docs/AI_ENGINEERING_PLAYBOOK.md and issue #4135; exact source is AntiGravity's #4358 head `2ea80b5144eba6fbbb6964e7ecfd69a1f71efc2e`, child of Cursor #4356. This child review branch changes only shadow spatial classification and its synthetic test. No original PDFs, credentials, canonical quantities, issuers, scorer, or benchmark truth are touched.

## Traced path and failure

`pb_source_native_wall_body_junction_graph_shadow.classify_source_wall_body_junctions` produces source-path-ID-bearing wall-body **candidates**. `pb_source_spatial_subdivision_shadow.build_source_spatial_subdivision` unions their polygons, selects a primary connected wall component, identifies `disconnected_body_ids`, then classifies `canvas_box.difference(wall_union)` planar regions. At `for geom in free_geoms`, a closed detached decoy creates a polygon treated as `INTERIOR_ENCLOSED_ROOM` despite its boundary being solely disconnected decoy bodies; the later decoy aggregate adds the same source IDs again as `DISCONNECTED_STRUCTURE_OR_DECOY`.

Synthetic proof at this exact head: primary closed rectangle x100..300, detached closed rectangle x750..850, canvas x0..1000. Actual candidate result: 2 interior, 1 decoy, with paths 5-8 appearing in both an interior and a decoy record. There is only one primary enclosed room. This is a P1 pre-promotion source-classification defect; current module is noncommercial, so no incorrect issued quantity is observed.

## Repair and acceptance

Precondition each non-outside candidate region on at least one source wall body **owned by the selected primary building component**; a polygon bounded exclusively by disconnected bodies must never be identified as conditioned/interior. Retain already-collected disconnected source path IDs in the existing ABSTAIN decoy record. Avoid arbitrary named-room, area, coordinate and document-specific decisions. Add a two-complete-rectangle regression that checks path-owner partition, primary room count, decoy count and zero measurement/score output. Keep all original candidate and customer issuance authorities unchanged; public synthetic pass alone is not original-source footprint acceptance.

Expected before the fix: test RED; after: source spatial tests PASS, original source acceptance still required. Re-run original Acacia and 3Laurel spatial census and check that any new interior counts correspond to source-backed primary wall cycles, not disconnected labels.
