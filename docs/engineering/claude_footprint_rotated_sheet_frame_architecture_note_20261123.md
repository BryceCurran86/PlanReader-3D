# Rotated sheets in the footprint chain: architecture note (23 Nov 2026)

For review before any code (AGENTS.md: first deliverable on a new change). Item 2 of the owner order (#2608 comment 7082410634); follows the finding in #4650. Counts and public identifiers only: no private source content, coordinates or customer data.

## 0. Compliance

- **Read:** AGENTS.md; `docs/AI_ENGINEERING_PLAYBOOK.md` (sections 1, 5, 6, 11, 12, 13); `pb_page_frame_shadow.py` (header: the canonical frame vocabulary and its promotion gate); `pb_external_footprint_first_trace.py` in full; `pb_external_footprint_inside_face_runtime.py` (signature and page-bounds use); the use sites in `pb_source_native_exterior_edge_path_ownership.py` and `pb_source_native_wall_role_and_junction_shadow.py`; `pb_planreader_pdf_extractor.py` lines 1290 to 1412 and `pb_live_physical_net_wall_integration.py` lines 540 to 640; how `pb_page_title_authority.py`, `pb_schedule_opening_instance_binding_authority.py` and `pb_source_observation_authority.py` already convert rotated pages.
- **Functions traced:** `trace_external_footprint_first` (raster to polygon) and every function that then compares the polygon or its bbox with native rows (section 1.3), plus the two live stages that receive `page.rect` (section 1.4).
- **Authority boundaries crossed:** none. The footprint candidate stays `measurement_authorized=False` and `commercial_publishable=False`; nothing here publishes a quantity.
- **Untouched by this proposal:** the live writers (`pb_planreader_pdf_extractor.py`, `pb_live_physical_net_wall_integration.py`), `pb_page_frame_shadow.py` (no production module may import it), W10, `benchmarks/frozen_holdout/full_plan_v2/**`, the 20,000-primitive cap and the 2.5 pt snap, every tool script (they pass the trace through).
- **Not done:** no code written; only the local replay measurements in section 1.5 were run.

## 1. Observed repository behavior

1. **Two coordinate spaces on a rotated page.** Verified on synthetic pages at 0, 90, 180 and 270 degrees and on real /Rotate 90 sheets: `get_drawings()` rects and `get_text("words")` boxes are in the NATIVE (unrotated) page user space; `page.rect`, `page.rotation_matrix` and the rendered pixmap are in the DISPLAY (rotated) space. `pb_page_frame_shadow.py` states the same rule, says no production module may import it, and requires real /Rotate 90, 180 and 270 files before promotion.
2. **The raster polygon is in display space.** `trace_external_footprint_first` rasterises the displayed page (its title-band cut and page-frame margins are display-space on purpose), so `polygon_pdf_pts` and `bbox_pdf_pts` are display-space despite the name. Nothing on the trace records the space.
3. **Four functions compare the polygon or bbox with native rows without conversion:** `refine_external_footprint_against_wall_ink` (polygon against `get_drawings()` segments), `bound_native_drawings_to_footprint` (bbox window on row rects), `own_exterior_contour_native_paths` (polygon against native line segments) and the window in `pb_source_native_wall_role_and_junction_shadow`. Their callers are tools and tests (`tools/run_original_footprint_first.py`, `tools/run_native_exterior_path_ownership.py` and similar). The two live callers of the first trace (`pb_planreader_pdf_extractor.py`, `pb_live_physical_net_wall_integration.py`) use only its status and diagnostics.
4. **The live extractor mixes the spaces too.** It passes `page.rect` (display extent) as `page_bounds_pdf_pts` together with native drawings and native words to `run_inside_face_footprint_runtime_stage` (which uses the bounds to refuse the page frame and in room-trace acceptance) and to `run_door_legend_read_stage`.
5. **Measured on 702 pages of 58 local original PDFs.** A census of all 774 pages of the 58 PDFs finds 621 upright and 153 at /Rotate 90 (7 originals have rotated pages; one of them, 29 of 31 pages); none is at 180 or 270. The 35 candidate pages on rotated sheets are all /Rotate 90. On the 8 candidate pages of one rotated original the scoped window selects 19,459 rows in total, against 49,836 when the polygon is mapped to native space; 9,162 rows are in both and three pages share none. Of 11 rotated floor-plan pages (at most 20,000 rows) the live inside-face stage gives a different output with native page bounds on 5; all are ABSTAINED either way, but reasons and sub-records change (for example `no_dominant_dark_outer_wall_inside_page` becomes `no_valid_left_turn_candidate`).
6. **Existing convention.** Other production modules already convert with `page.rotation_matrix` and pass a validated six-float tuple (`pb_schedule_opening_instance_binding_authority.py`: "verified six-value original page rotation required").
7. **No footprint test covers a rotated page.**

## 2. Inference

- This is a missing frame annotation, not a heuristic problem: the trace does not say which space it is in, so every consumer assumes native, which is right only on an upright page. That is why it never showed.
- Quantities do not depend on it today: the live consequence is review-only diagnostics. Where a rotated sheet loses or gains rows is the tool and shadow chain (scoped windows, edge ownership, bounded room rings), which feeds overlays and bounded-viewport diagnostics for rotated originals.
- Renaming `polygon_pdf_pts` is not an option (serialised evidence); annotating the space is.

## 3. Proposed change (shadow first, additive, upright pages byte-identical)

1. `ExternalFootprintTrace` gains one defaulted field, `page_derotation_matrix: tuple[float, float, float, float, float, float] | None = None`: the six floats of PyMuPDF's `page.derotation_matrix`, mapping the display space of the polygon to the native space of the rows. It is set only when `page.rotation != 0`. `to_dict()` emits the key only when it is set, so upright output does not change.
2. Pure helpers in the same module (no PyMuPDF): the polygon and bbox in native space, and the inverse for a corrected polygon. A matrix that is not six finite numbers abstains with `footprint_frame_matrix_invalid`; there is no silent identity.
3. The four comparison sites call the helpers. `refine_external_footprint_against_wall_ink` maps its corrected polygon back so the returned trace stays in the trace's own space. Tools need no change.
4. Not in this change: the live extractor's `page_bounds_pdf_pts=page.rect`. It is a live commercial writer, and 5 of 11 measured rotated floor plans change, so it is a separate decision for MAX with this evidence (pass the native extent, or leave it).
5. #4650 derotates the polygon itself for its edge-support check; after this lands it can use the same helper.

**Alternatives rejected.** Converting every row and word to display space at each consumer (many sites, 20,000-row transforms). Rasterising in native orientation (the title-band and frame heuristics are display-space). Making `polygon_pdf_pts` native on rotated pages (changes serialised evidence and breaks overlays that draw on the displayed raster).

## 4. Tests to write first (AGENTS.md matrix)

Synthetic positives at 0, 90, 180 and 270 degrees; look-alike negatives (a rotated page whose trace has no matrix keeps today's behaviour; an invalid matrix abstains); page-rotation invariance (the same drawing on a page turned by 0, 90, 180 or 270 must scope the same native row indices, with the building kept clear of the title band in every rotation); translation, scale, input-order and segment-splitting invariance; unrelated far content and viewport expansion; deterministic replay; no mutation of trace or rows; a cross-check of the helper against `pb_page_frame_shadow.display_to_native` (tests may import the shadow); upright `to_dict()` identical for the existing fixtures and for every upright candidate page of the local corpus; single-line mutants. Real-original replay: before and after counts on the rotated originals (reported, not tuned).

## 5. Expected behaviour (stated before the tests)

Upright pages: nothing changes, asserted. Rotated pages with a matrix: scope windows change; `bound_native_drawings_to_footprint` can move between CANDIDATE and its existing ABSTAIN reasons (`bounded_source_viewport_has_no_native_wall_ink`, `bounded_source_viewport_exceeds_20000_primitive_cap`) as the window changes; edge ownership binds different paths. The counts will be reported as measured.

## 6. Benchmark observations that must not influence implementation

The row counts above and the hub's quoted results are failure-mode evidence only. The change is an exact affine map with no threshold, no page number, no project name and no expected quantity.

## 7. Decisions for the owner

1. Approve items 1 to 3 as one shadow PR (stacked on nothing; it touches `pb_external_footprint_first_trace.py` near #4650's hunks, which merge by hand).
2. The live extractor's page bounds (item 4): a separate PR with MAX's promotion review, or leave as is.
3. Real /Rotate 180 and 270 sheets do not exist in the local corpus, so those two stay synthetic-only, as `pb_page_frame_shadow.py` requires until real files exist. Accept?
4. The extra key on rotated traces: GPT1, whose #4647 writes the trace JSON, should confirm its writer tolerates it.
