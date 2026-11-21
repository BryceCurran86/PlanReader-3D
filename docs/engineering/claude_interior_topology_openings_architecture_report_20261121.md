# Claude lane: interior topology and openings. Architecture report (no code changed)

Date: 2026-11-21 (Brisbane). Base: `origin/main` `73d710872e25178ce1f5b8bf9eefb8c5605b2b21`; worktree branch `claude/interior-topology-openings-20261121`.
Lane source: hub issue #4135 comment 7054982873 (owner directive, four-agent order), confirmed by GPT MAX in comment 7055344005. Lane text: universal physical room ring closure, interior wall/threshold faces, doors including cavity sliders and internal doors, real room-opening classification, bounded door/window schedules, adjoining-room threshold logic. No hardcoded project logic, no rewriting of signed receipts, GPT MAX exterior host code untouched without a handoff.
Short ids, counts and PDF-point values only. No private words, drawing text, customer data or benchmark values enter any rule.

This is the AGENTS.md first deliverable. Sections: compliance, OBSERVED, INFERENCE, PROPOSED, BENCHMARK, owner decisions, claim.

## 1. Compliance block

**Files read.** `AGENTS.md` (origin/main, whole file); `docs/AI_ENGINEERING_PLAYBOOK.md`; `docs/engineering/CANONICAL_TRACE_ROUTE_CONTRACT_20261120.md`; `ONE_APP_PRODUCTION_CONSOLIDATION_20261112.md`; the Claude parts of `AUTONOMOUS_COMPLETION_QUEUES_20261110.md`; my `claude_3laurel_elevation_vertical_witness_shadow_results_20261109.md` and `claude_3laurel_elevation_source_subpath_attribution_20261110.md`; issues #4534, #4594, #4599; the hub tail (2,151 comments; last read 7055344005) and the 20-21 Nov 3Laurel, door and ring comments.

**Functions traced (file:function).** `pb_source_internal_door_completeness_shadow.inspect_source_internal_door_completeness`; `pb_source_internal_swing_room_barrier.detect_source_internal_swing_room_barriers`; `pb_source_native_cavity_slider_jamb_shadow.match_source_native_cavity_sliders`; `pb_three_laurel_internal_door_source_review.review_original_three_laurel_internal_door_source`; `pb_new_source_trace_preview.source_native_trace_preview` (ring call); `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`; `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings`; `pb_physical_opening_authority` (`JAMB_BOUNDED_TWO_FACE_INTERRUPTION`, `GAP_CORROBORATED_*`, caller of `pb_plan_opening_detection_indexed_v172.detect_door_candidates_indexed`); `pb_opening_kind_authority.resolve_opening_kind`; `pb_opening_label_dimension_authority` (single and two-figure parse, `_area_from_dimension_values`); `pb_document_joinery_head_height_authority`; `pb_opening_vertical_placement_authority`; `pb_door_height_owner_gate_shadow`; `pb_live_opening_area_quantity_publication._opening_quantity`; `pb_original_opening_area_gate_diagnostics._first_observable_gate` and `audit_original_opening_area_gates`; `pb_original_window_canonical_representative_review.compare_figured_window_source_to_canonical_representatives`; `pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim`.

**Authority boundaries crossed by the quantity this lane serves (internal door opening area).** source observation -> structural opening record (G17) -> kind -> host wall -> host binding or frame record -> metric axes (width, height, base) -> area basis -> `_opening_quantity` -> seal -> customer row -> unchanged evaluator. The work proposed here reads the first boundary and crosses none after it.

**Files that stay untouched.** `pb_planreader_pdf_extractor.py`; `pb_physical_opening_authority.py` (open #4553, #4566); `pb_opening_kind_authority.py`; `pb_opening_host_binding_authority.py`; `pb_opening_host_frame_authority.py` and `pb_live_opening_area_quantity_publication.py` (open #4522); `pb_live_opening_external_door_height_estimate_publication.py` (open #4511); W2/W4 lineage files (open #4504); the ring options in `pb_new_source_trace_preview.py`; `benchmarks/frozen_holdout/full_plan_v2/**`; AGENTS.md; every identity map and signed fixture.

## 2. OBSERVED (repository behaviour at the base commit)

**2.1 Door-symbol evidence is a separate family from the physical-opening stack.** `inspect_source_internal_door_completeness` (`pb_source_internal_door_completeness_shadow.py:132-269`) hard-codes `physical_opening_authenticated=False` and `measurement_authorized=False` (`:39-40`, `:58-59`, `:82-83`). Its only consumer is the display summary in `pb_new_source_trace_preview.py:243-247,496-499`; no authority imports it. `pb_ag_door_symbol_legend_reader.run_door_legend_read_stage` runs inside `pb_planreader_pdf_extractor.py:1380-1420` and stores `self.door_legend_read_live`; its docstring says it feeds the completeness shadow, but nothing imports it there.

**2.2 Job-specific and convention-bound code in the internal-door evidence path.**
- `pb_three_laurel_internal_door_source_review.py:20-21,63-64,70-72,76-79,89,130-136`: SHA gate, note literal, elevation pages 4 and 5 by index, counts 8 / 6 / 14, width allowlist 720 / 870. Only its own test imports it.
- `pb_source_internal_door_completeness_shadow.py:118` repeats the 720 / 870 allowlist for hinged widths and takes the nearest token under 15 pt with a 2 pt margin.
- Four copies of the internal-wall layer predicate: `pb_source_internal_swing_room_barrier.py:19-23` and `pb_source_native_cavity_slider_jamb_shadow.py:17-22` (five conventions, anchored); `pb_source_internal_door_completeness_shadow.py:22` and `pb_ag_door_symbol_legend_reader.py:36` (three names, unanchored `search`). The inventory cannot list an unhosted swing on a layer that only the first two accept (for example `A-WALL-INTR`).
- Barrier hosting needs WHITE jamb returns and BLACK wall hosts with a 0.75 pt internal cap tolerance (`pb_source_internal_swing_room_barrier.py:114,128-131`): one CAD export style.

**2.3 The canonical opening chain, in gate order** (`pb_original_opening_area_gate_diagnostics.py:44-75`, `pb_live_opening_area_quantity_publication.py:56-150`): canonical identity, kind door or window, `host_wall_id`, host binding or frame record, positive area, evidence ids. Kind is `pb_opening_kind_authority.resolve_opening_kind` from only the structural pattern (`:35` maps door-leaf and window-jamb-pair patterns), a bound schedule type or a label kind. The pattern `jamb_bounded_two_face_interruption` carries no kind (`pb_physical_opening_authority.py:3270-3330`), and it combines every face and jamb pairing it finds, so one aperture can yield several records. G17's door pattern comes from the legacy indexed detector (perpendicular short segment near a wall, `pb_plan_opening_detection_indexed_v172.py:151`), not from swing arcs.

**2.4 Area bases and heights.** `pb_live_opening_area_quantity_publication.py:24-47` lists figured label (two figures), resolved geometry, schedule frame, elevation frame, owner-approved second axis (a review-lineage shadow row, never FIRM) and the external-door 2100 estimate (external wall role only). `pb_opening_label_dimension_authority.py:330-345` refuses an area from a single door callout. `pb_door_height_owner_gate_shadow.py:1-12` forbids 2100, 2040, 1980, 2400 as invented heights. `pb_document_joinery_head_height_authority.py:1-12` authenticates a document-wide "joinery heights ... AFL U.N.O." note as a HEAD height and says conversion to an opening height needs the base proved separately; no production module imports it, and `tests/test_live_physical_opening_void_composition.py:370-405` pins that. `pb_opening_vertical_placement_authority.py:1-12` never assumes a door sill is zero. My elevation witness registered only exterior doors; interior doors have no elevation outline.

**2.5 Ring closure.** The canonical preview pins `source_native_cs_jamb_closure=False` and `source_native_internal_swing_closure=False` (`pb_new_source_trace_preview.py:265-272`, AST-guarded by `tests/test_new_source_trace_preview.py:923+`, #4589). The function that runs is `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings` (`:2218`) with its own `LayeredRoomRingResult` (`:255`), not the same-named function in `pb_layered_wall_doorway_room_ring_shadow` (`:2129`) that the receipt string and `tools/run_canonical_source_native_preview.py:22` name. `scripts/check_canonical_trace_route.py:39` only checks that the function NAME is called.

**2.6 MEASURED (local private runs on the authenticated 3Laurel original, SHA prefix 014e9f68, page 3; clean worktree at the base commit; counts only).**
- *Inventory* (1.9 s): 11,030 paths, 1,215 words -> 14 marks: 8 hosted swings, 6 cavity-slider callouts with authenticated jambs and leaf. Equal to the existing source test's pins.
- *Real collector* `collect_live_physical_net_wall_claim(pdf, pages=(2,), recover_supported_opening_areas=True)`, other options default (471 s): claim `abstained` with 26 reason codes (including `no_authenticated_host_wall_band`, `ambiguous_physical_wall_equivalence_for_host`, `multiple_authenticated_host_wall_bands`, `opening_host_frame_host_unavailable`, `physical_wall_candidate_scope_bounds_unresolved`, `semantic_opening_physical_conflict`, `semantic_opening_universe_exhaustiveness_unproven`); 180 canonical opening records, all `jamb_bounded_two_face_interruption`; 1,555 canonical walls; 292 canonical rooms; 30 opening-area quantities issued.
- *Issuer census* (`audit_original_opening_area_gates`): kind 37 window / 16 door / 127 unresolved; first gate 127 kind unresolved, 23 host wall missing, 30 issued and retained (27 window, 3 door); basis `figured_opening_label` 54, none 126.
- *Door aperture to record binding.* Aperture boxes from the barrier gap boxes and the cavity-slider clear interval x band; a record is bound when its representative segment lies inside the box within 1.25 pt (the rule of the merged window and slider reviews). 14 apertures; 29 distinct records inside; none inside two apertures. Records per hinged aperture 6, 2, 3, 3, 5, 3, 2, 2; per cavity-slider aperture 1, 0, 1, 0, 0, 1. For the 29 records: kind unresolved 29/29, host wall 0/29, host binding or frame 0/29, area basis 2/29 (one aperture), issued 0/29. At 2.5 pt: 33 records, same gate profile. (A looser region-overlap test touched 36 records; it was discarded as over-inclusive.)
- *Ring closure* (canonical preview, native door closures pinned off as merged vs forced on through a wrapper, no repo edit): rings 18 -> 27, closures 72 -> 82, gaps 351 -> 355, unresolved gaps 70 -> 69, sliver regions 4 -> 7, ambiguous swings 5 -> 6; result type confirmed to be the `pb_next_wall_ring_preview` one. Topology candidates only.
- *Cross-drawing door detector survey* (existing detectors, nine drawings): see section 2.7.

**Cross-lane observation for MAX (integration owner).** On this base the plain collector issues 30 opening areas for the page (27 window, 3 door), while the 20 Nov core handoff reported 2. I ran no sealing, customer verification or identity map, so this is not a score; it only says the drop is not in the collector's canonical issuer with default options.

## 2.7 Cross-drawing survey (existing detectors only, local, counts only)

Nine drawings (four benchmark plan sets, the held-out Acacia sample, four public sample plan sets), 166 pages; three Maryborough pages skipped above 40,000 paths; no detector error. Per drawing, summed over pages. "Layers" is the largest number of distinct CAD layer names on one page (1 means the PDF carries no layer metadata). "Hosted" is `detect_source_internal_swing_room_barriers`; "any-layer swing" is the arc-plus-leaf symbol count of `_swing_arcs` without the layer filter.

| Drawing | Pages | Layers | Any-layer swing symbols | Hosted swings | Hosted cavity sliders | Segmented black swings | Door-tag words |
|---|---|---|---|---|---|---|---|
| 3Laurel | 18 | 20 | 28 | 19 | 6 | 0 | 0 |
| Lot16 | 13 | 1 | 0 | 0 | 0 | 0 | 1 |
| Maryborough | 31 (28 scanned) | 1 | 0 | 0 | 0 | 9 | 147 |
| Q5446 standard plans | 10 | 1 | 0 | 0 | 0 | 0 | 0 |
| Acacia sample | 10 | 1 | 0 | 0 | 0 | 0 | 0 |
| Public sample A | 13 | 32 | 0 | 0 | 0 | 0 | 27 |
| Public sample B | 23 | 1 | 12 | 0 | 0 | 0 | 63 |
| Public sample C | 36 | 1 | 0 | 0 | 0 | 0 | 0 |
| Public sample D | 12 | 2 | 27 | 0 | 0 | 0 | 0 |

Observed: the hosted-door machinery fires on 1 of 9 drawings, the one whose layer names match the internal-wall predicate (7,619 matching paths; zero on the other eight). Two drawings carry swing symbols that are never hosted (12 and 27) and have no wall-layer names. Maryborough draws swings as segmented black arcs, which only the ring producer's separate detector reads. Five drawings show no door symbol to any existing detector; whether they have none or draw them in a style no detector reads is unknown.

## 3. INFERENCE

- **I1. The internal doors are not physical openings in the canonical chain.** Kind, host and metric gates are all open for every bound record, and identity is a class, not a record: at least two competing records for 8 of 14 apertures, none for 3 of 14.
- **I2. First failing functions, in order.** (a) Identity: G17 emits several support-set records per aperture and no authority names them one physical opening before publication (the NO_OWNER finding of 13 Nov generalises). (b) `resolve_opening_kind`: a kind-agnostic pattern and no bound door evidence. (c) Host binding: `no_authenticated_host_wall_band` and `ambiguous_physical_wall_equivalence_for_host`. (d) Metric: one printed width, no second-axis authority for interior doors.
- **I3. The evidence for (b) and part of (c) already exists** as review-only source evidence in the door inventory (swing leaf, two native wall-end hosts, jambs; cavity-slider jambs, leaf, printed width). Nothing binds it to a physical aperture class. A binding that retains every representative and reports the funnel is the missing safe first piece; it parallels the merged window (#4627) and slider (#4622) reviews.
- **I4. Interior door height is an owner policy question, not an engineering gap.** There is no per-door height source (no elevation outline, no schedule). The one source fact is a document head note whose base is unproved by design, and the owner-approved second-axis lane exists as a review-lineage row.
- **I5. Native door closures change the ring candidate set materially (18 -> 27).** Acceptance needs a cross-drawing regression and a ring-to-room correctness check that do not exist yet. The flags stay pinned until then.
- **I6. The internal-door machinery is not universal.** Hosting needs a wall-layer name, and 7 of 9 drawings have none (2.7). A universal host rule needs wall evidence that does not depend on layer names; the ring producer already has layer-free wall strip sources (stroke pairs, dark fills) that are the natural input. Until then every statement about "all drawings" for interior doors would be false.

## 4. PROPOSED (shadow first; new modules; no authority or commercial change)

- **S1 (starting now). `pb_source_internal_door_aperture_review.py`**, review-only: bind each source-native internal door aperture to the canonical opening records inside it (the merged reviews' 1.25 pt containment), retain every representative, never rank or choose, report per-aperture state (`NO_REPRESENTATIVE`, `SINGLE_REPRESENTATIVE`, `MULTIPLE_REPRESENTATIVES_RETAINED`, `SHARED_REPRESENTATIVE_CONFLICT`), the record kinds seen (a window kind on a door aperture is a retained conflict), host and area counts, and the first open gate. Writes no kind, host, frame, area or quantity. Reads the existing detectors; adds no geometry rule.
- **S1b (separate small PR). Retire the job-specific parts of the evidence path:** one shared internal-wall layer predicate; replace the 720 / 870 allowlist by the plausible-width range the cavity-slider detector already uses plus unique ownership; keep `pb_three_laurel_internal_door_source_review` as a fixture-equivalence test target until a universal replacement reproduces it, then retire it.
- **S2. Kind corroboration spec** for `resolve_opening_kind`: a door-symbol input, applied only to an aperture class with exactly one symbol and no conflicting kind. Needs a claim on the composition seam with MAX; shadow output first.
- **S3. Host evidence:** map the barrier's two native wall-end paths to canonical wall candidates (review-only), measuring how many internal apertures have a unique physical host.
- **S4. Metric:** width ownership under text trust, the joinery head note plus a base proof, or the owner-approved path (decision D1).
- **S5. Ring closure acceptance:** cross-drawing regression and ring-to-room check before any flag moves; see D3.
- **S6. Layer-agnostic host evidence for door symbols:** host a swing or slider symbol on wall strips from the ring producer's layer-free sources instead of a CAD layer name, with the alternate-layer, no-layer, rotated and false-positive negatives the universal rule requires. Shadow first; measured on the nine-drawing survey.

**Expected abstentions for S1 (predicted before tests).** Aperture with no contained record: `NO_REPRESENTATIVE`. Record inside two apertures: both `SHARED_REPRESENTATIVE_CONFLICT`. Records of another SHA, page, viewport, revision or snapshot: excluded and counted; a mixed scope within the supplied set: whole review `ABSTAINED`. Record longer than the aperture or outside by more than the tolerance: not bound. Kind never written. Foreign or malformed objects: refused.

**Tests required (AGENTS.md).** Synthetic positives and look-alike negatives; ambiguity and conflict; translation, 90-degree rotation, mirror and scale metamorphic cases with margins far from the tolerance; record-order, unrelated-content and viewport-expansion invariance; deterministic replay and stable ids; no mutation of inputs; proof that no production module imports the review and that every authority flag stays false; a source scan proving no project, SHA, page or width literal; an original-source test (skipped without the private PDF) for the inventory side only. A heavy collector run stays a local diagnostic tool, not a CI test.

## 5. BENCHMARK observations that must not influence implementation

The frozen 3Laurel reference lists internal and robe doors, 22 finishes and an owner target of 49/63; the last signed baseline is 24/63 and no official score exists. None of those numbers entered a rule, threshold or cardinality. That the inventory finds 14 marks and the frozen reference lists 14 internal doors is an observation, not a target: the existing job-specific review hard-codes 14 and the replacement must not. All measurements above are diagnostic.

## 6. Decisions that are the owner's

- **D1. Interior door height and base.** The existing authorities refuse to turn the document head note into an opening height without a base proof, and the 2100 estimate is external-only. Options: (a) abstain; (b) per-door owner-approved second axis (existing review-lineage lane); (c) a new source-backed base proof (single-storey datum and no level change at the doorway) feeding a new area basis. I recommend (a) now and (b) as the explicit owner step, with (c) designed only if you want interior doors in FIRM scope.
- **D2. Where physical aperture identity is consolidated:** producer side (one record per aperture in G17) or at publication. S1 gives the data to decide.
- **D3. Which ring producer is the producer of record:** `pb_next_wall_ring_preview` (what runs) or `pb_layered_wall_doorway_room_ring_shadow` (what the receipts name and where the later improvements live).

## 7. Claim (exclusive, new files unless stated)

`pb_source_internal_door_aperture_review.py`; `tests/test_source_internal_door_aperture_review_v1.py`; `tools/diag_internal_door_aperture_review.py`; this report. For S1b, a later claim on `pb_source_internal_door_completeness_shadow.py` (width allowlist, layer predicate) and its tests only. No existing authority, issuer, extractor or ring module is edited. Dependencies: none open. Source scope: SHA-authenticated originals read in place; counts only in public text.

## 8. Status of S1 (same day, after the report)

Built, all new files: `pb_source_internal_door_aperture_review.py`, `tools/diag_internal_door_aperture_review.py`, `tests/test_source_internal_door_aperture_review_v1.py` (50 tests), `tests/test_diag_internal_door_aperture_review_v1.py` (7 tests). No existing file is edited.

Verified: 44 of 44 single-line mutants of the module are caught; 96 related tests (this module, the internal door inventory, barrier, cavity slider and window review) pass together; the repository's private-source, truth-separation, canonical-route and provider-isolation guards and `ruff --select F821,F823` pass locally. On the saved collector output of the 3Laurel original the module returns exactly the funnel of 2.6: 14 apertures, 29 records bound, none shared; 8 apertures with several representatives retained, 3 with one, 3 with none; first open gate kind unresolved on 11 and no representative on 3. Tool end to end on the original: TOOL_RESULT_PLACEHOLDER.

Measured for S1b (read only): replacing the 720 / 870 width allowlist with the plausible-width range the cavity-slider detector already uses changes nothing on the one drawing where hosted swings exist. All 8 hinged marks have exactly one plausible token within 15 pt, equal to the current pick (870 for seven, 720 for one). So that part of S1b is behaviour-preserving there and removes the project-specific literals.

Not proven: Python 3.14 and exact-head CI, the protected replay, sealing, customer output, any score. Not started: S1b, S2 to S6.
