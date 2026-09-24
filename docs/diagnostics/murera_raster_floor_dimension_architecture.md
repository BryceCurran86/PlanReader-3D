# Murera raster figured-dimension architecture report

Scope: source-owned recovery of figured floor-plan dimensions from raster-only drawing content. This report changes no production behavior and grants no measurement authority.

## Compliance

Files read before proposing a change:

- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `docs/wall_topology_observability_architecture.md`
- `docs/planreader_wall_room_topology_spec.md`
- `docs/planreader_public_tender_benchmarks.md`
- `.github/workflows/ci.yml`
- `pb_planreader_pdf_extractor.py`
- `pb_explicit_floor_area_evidence.py`
- `pb_multi_space_footprint_geometry.py`
- `pb_slab_classification_geometry.py`
- `pb_figured_dimension_evidence.py`
- `pb_viewport_dimension_binding.py`
- `pb_portable_raster_ocr_authority.py`
- `pb_room_area_quantity.py`

Functions and call paths traced:

- `GenericPlanReaderExtractor.extract_from_pdf`
- `GenericPlanReaderExtractor._has_plan_footprint_context`
- `GenericPlanReaderExtractor._detect_outer_envelope`
- `extract_explicit_floor_area_evidence` / `resolve_explicit_floor_area_evidence`
- `MultiSpaceFootprintBuilder.build` / `MultiSpaceFootprintEngine.evaluate`
- `make_ocr_dimension_observation`
- `bind_observation_to_vector_geometry`
- `evidence_tier_for`
- `resolve_slabs_from_page`
- `build_room_area_quantity`

Authority boundaries crossed by the current live path:

1. PDF/native or raster observation capture.
2. Page/viewport ownership.
3. Figured-dimension candidate extraction.
4. Physical dimension-line/witness binding.
5. Measurement authority.
6. Floor footprint/area geometry.
7. Structural bed/DPM/mesh publication.

Files that must remain untouched in this diagnostic phase:

- `pb_planreader_pdf_extractor.py`
- `pb_planreader_jobhub_publish_contract.py`
- `benchmarks/**`
- `pb_benchmark_accuracy_engine.py`
- benchmark mappings, tolerances, manifests, source hashes and expected quantities.

## Observed repository behavior

The live extractor already has one shared structural-floor quantity path.

During the document pre-scan, `GenericPlanReaderExtractor.extract_from_pdf` collects explicit figured `FLOOR AREA` annotations through `pb_explicit_floor_area_evidence`. When no explicit area is available, it parses figured dimensions and calls `_detect_outer_envelope`. A page can replace the active floor footprint only when it has explicit floor-area evidence or passes `_has_plan_footprint_context`.

Once a length and width have been accepted, `MultiSpaceFootprintBuilder` creates the footprint. The extractor stores `structural_bed_area_m2` in the `floor_screed` metadata. Later, the existing substructure path reuses exactly that value for:

- `substructure_bed_dpm`
- `substructure_a142_mesh`
- `substructure_surface_bed`

provided the corresponding drawing specification evidence is present. There is therefore no need for three separate area algorithms.

The explicit-floor-area path is intentionally narrow. `pb_explicit_floor_area_evidence` requires a labelled `FLOOR AREA` square-metre value and fails closed when qualifying annotations disagree.

`pb_slab_classification_geometry` does not independently invent slab area. It may bind a slab annotation/thickness/reinforcement to an already-authoritative candidate boundary, but the area supplied to that boundary must already be unit-safe and authoritative.

`pb_figured_dimension_evidence.make_ocr_dimension_observation` can transform an OCR token into PDF coordinates only when an explicit raster-to-PDF transform is supplied. Such an observation remains OCR-derived / AI-detected and partially constrained. `pb_portable_raster_ocr_authority` likewise states that successful OCR publication is CANDIDATE only. OCR output alone is not FIRM measurement authority.

## Source observations

The SHA-pinned Murera source used by the existing diagnostics is:

`84dec737ede7adfa32b02c6732d4289a6a2d25f7ae50cf07209428f1b4e0c94b`

The relevant raster floor-plan content is on drawing page 228. Native PDF text for that page is sparse and does not expose a usable explicit floor-area annotation. The current production-bounded OCR diagnostic also returns no usable area-labelled line; its recognizable plan title is OCR'd as `LABORATORY FLOOR FLAN`, so the current semantic plan-title gate is not sufficient to establish footprint authority from OCR text.

The line-clean numeric diagnostic on the same source-owned embedded raster independently observes several plausible figured-dimension strings. In particular, one strip contains repeat observations of:

- `4100` across multiple OCR modes/rotations, with maximum reported confidence 96;
- `2250` across multiple modes/rotations, maximum reported confidence 78;
- another adjacent strip contains `3000` across multiple modes/rotations, maximum reported confidence 94.

Other numbers are also present, including lower-confidence or conflicting candidates. These values are observations only. Their repetition across OCR modes from the same raster/backend is not independent measurement authority.

The same Murera drawing package separately contains source text for ground-bearing floor construction, DPM and A142 mesh on structural/detail sheets. That specification evidence can identify material scope, but it cannot supply the missing plan area.

## Inference

The repeated page-228 OCR values are likely real figured dimensions rather than an explicit overall floor area. However, today the repository cannot prove which physical spans those OCR values dimension.

The missing generic capability is therefore not “OCR another number” and not “choose dimensions whose product matches a BOQ value.” It is a source-owned raster figured-dimension binding layer that can answer:

- which raster image/placement produced the token;
- where the token lies in PDF coordinates;
- which dimension line owns it;
- which two witness/extension endpoints terminate that dimension line;
- which floor-plan viewport owns the complete bundle;
- whether competing candidates remain.

Without those facts, combining `4100`, `3000`, `2250`, or any other OCR values into a footprint would be a heuristic and must abstain.

## Proposed change

First implementation should be a new shadow-only raster figured-dimension collector. It should reuse the repository's existing evidence vocabulary and geometry contracts rather than add a second scale or dimension authority.

The shadow collector should:

- start from immutable source PDF bytes and preserve document id, revision id, source SHA, source page, image xref and image placement rectangle;
- use a production OCR backend selected through the existing OCR provider seam;
- retain every plausible numeric candidate and all conflicting alternatives;
- map raster boxes back into PDF coordinates with `RasterCoordinateTransform`;
- detect raster dimension lines and perpendicular witness/extension lines as candidate geometry, preserving their source pixel/PDF coordinates;
- bind a numeric OCR candidate only when one unambiguous dimension line and two unambiguous witness endpoints are geometrically established;
- preserve orientation and exact endpoints;
- use `EvidenceResolutionStatus.CANDIDATE` for successful shadow observations;
- emit no floor area, no structural-bed quantity, no commercial row and no change to live predictions.

A later, separate authority review may decide whether a raster-bound figured dimension can enter the existing figured-dimension measurement authority path. This report does not grant that promotion.

## Expected abstentions

The shadow layer must abstain or conflict when any of the following occurs:

- source page/image lineage is unavailable or stale;
- one raster image has multiple unresolved placements;
- the OCR backend is unavailable;
- the numeric token has no coordinate transform;
- multiple materially different OCR readings occupy the same candidate position;
- only a dimension line is visible but fewer than two witness endpoints resolve;
- more than one plausible dimension line or witness pair owns the token;
- orientation remains unknown;
- the candidate lies outside the owned floor-plan viewport;
- viewport ownership is ambiguous/unsupported;
- a title-block, scale, grid, sheet number, reinforcement spacing, year, room number or other typed drafting token is mistaken for a dimension;
- multiple competing dimension chains remain;
- only OCR repetition, confidence, or numerical plausibility supports a value;
- a closed/complete floor boundary cannot later be proven from source geometry.

No “nearest”, “first”, “largest”, “smallest”, benchmark-nearest, or product-nearest tie-break is permitted.

## Benchmark firewall

The current development benchmark is useful only for prioritizing this investigation. Murera currently accepts 4 of 10 scored items; three remaining substructure items share the structural floor-area dependency. Their expected BOQ quantities are evaluation data.

Those benchmark quantities must not:

- select OCR tokens;
- select dimension pairs;
- determine line-removal kernels;
- determine geometric tolerances;
- determine arithmetic combinations;
- decide between competing candidates;
- alter scoring, mappings, tolerances or the benchmark denominator.

A future source-derived floor area must be produced before any gold join. If it happens to improve the development score, that is a downstream evaluation result, not an implementation input.

## Review decision required before implementation

Approve only the shadow observation layer described above. Do not approve live floor-area publication, structural-bed publication, OCR-to-FIRM promotion, or commercial projection in the same change.
