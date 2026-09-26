# F.07 derived viewport overlap and authority architecture report

Base inspected: `ec0423ddc1d0bf4c0f8a894450da81a2f29db03e`.

This is the required report-only first deliverable under `AGENTS.md`. It changes no production or benchmark behavior.

## Compliance

Files/functions traced:
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_viewport_segmentation.py`
  - `extract_vector_frames`
  - `_frame_resolved_viewports`
  - `_derived_partitions`
  - `_columnar_title_grid_partitions`
  - `is_authoritative_derived_viewport`
  - `segment_page_viewports`
  - `validate_non_overlapping_viewports`
- `pb_viewport_dimension_binding.py`
  - `extract_dimension_evidence_by_viewport`
- `pb_figured_dimension_evidence.py`
  - `bind_observation_to_vector_geometry`
- `pb_source_roof_covering_authority.py`
  - `get_elevation_viewport_search_bbox`
- shadow figured-span scale producer in PR #881.
- TEST-ONLY Lamu real-source trace in PR #883.

Authority boundaries crossed by any future fix:
1. title classification
2. viewport spatial ownership
3. F.13 figured-dimension ownership
4. physical-scale evidence
5. page/viewport scale authority

Files that must remain untouched in the first implementation:
- `pb_planreader_pdf_extractor.py`
- `pb_planreader_jobhub_publish_contract.py`
- `benchmarks/**`
- benchmark scoring/tolerances/mappings
- W10 commercial defaults
- live opening/deduction code

## Observed repository behavior

### Framed viewports and ordinary derived partitions are built independently

`segment_page_viewports` first resolves title anchors to vector frames through
`_frame_resolved_viewports`. It then passes only the *unresolved* title
indices to `_derived_partitions`.

For ordinary one-axis derived partitions, `_derived_partitions` computes its
outer boundaries from the page edges and its internal boundaries from the
unresolved title centers only.

It does **not** receive the already resolved framed viewports and therefore
cannot prevent an ordinary derived partition from extending across an existing
RESOLVED viewport.

The combined `framed + derived` set is returned without a final
cross-family overlap validation.

### A stricter derived subtype already exists

`_columnar_title_grid_partitions` performs a stricter 2-D title-grid
derivation and calls `validate_non_overlapping_viewports` over its own output.
`is_authoritative_derived_viewport` recognizes only that producer-owned,
validated subtype.

Ordinary `TITLE_PARTITION` viewports remain diagnostic derived evidence.

### The roof helper is not general viewport authority

`get_elevation_viewport_search_bbox` creates an elevation search region from
title placement and drafting convention when no vector frame exists. That
function is useful for roof diagnostics, but it is not F.07 viewport authority
and must not be reused to grant figured-dimension or scale authority.

## Real-source shadow observation

The SHA-pinned Lamu page-41 TEST-ONLY run in PR #883 exposed the generic failure
mode without using any benchmark expected quantity.

Default authority-sensitive F.13 binding:
- one floor-plan viewport is RESOLVED;
- three elevation viewports are DERIVED and therefore skipped.

Diagnostic `allow_derived=True`:
- ELEVATION 01 inherited many floor-plan dimensions, proving its ordinary
  derived region overlaps or otherwise contains evidence belonging to the
  already RESOLVED floor-plan viewport;
- ELEVATION 03 cleanly exposed one 16,000 mm witness-bound span at
  453.599991 pt (~0.02835 pt/mm);
- ELEVATION 02 exposed a valid 8,200 mm witness-bound span at 232.560028 pt
  (~0.028361 pt/mm), but also captured an unrelated page-bottom `200mm`
  token bound to a near-page-width line;
- the figured-span scale shadow correctly returned conflicts rather than a
  calibration or quantity.

These are diagnostic observations only. No expected roof area or benchmark
target selected any geometry or threshold.

## Inference

The first correctness defect is not scale reconciliation. It is incomplete
spatial isolation between RESOLVED framed ownership and ordinary DERIVED title
partitions.

Allowing all DERIVED viewports into F.13 would weaken authority and admit
cross-view/page-note contamination.

The safest first repair is therefore a **negative ownership invariant**:
ordinary derived viewports must never overlap any already RESOLVED viewport.

This invariant does not require choosing a new boundary. It can fail closed.

A separate later design may decide whether a stricter one-axis derived subtype
can ever become authoritative. That decision should not be bundled into the
overlap repair.

## Proposed first change

1. After `framed` and ordinary `derived` viewports are produced, validate
   overlap between every DERIVED bbox and every RESOLVED bbox.
2. If an ordinary DERIVED viewport overlaps a RESOLVED viewport by more than
   the existing geometric epsilon:
   - do not clip or reshape it;
   - replace it with an explicit non-owning AMBIGUOUS record;
   - clear `bounding_box`;
   - retain title, page, view type, original derived bbox and overlapping
     resolved viewport IDs/bboxes in provenance/reason metadata.
3. Preserve the existing strict `columnar_title_grid` subtype unchanged in
   this first patch unless its output itself overlaps a RESOLVED viewport; if
   that occurs, fail closed as well.
4. Add a final combined non-overlap invariant over all owning viewports before
   returning from `segment_page_viewports`.
5. Do not make any new DERIVED subtype authoritative in this patch.
6. Do not change `extract_dimension_evidence_by_viewport` defaults.

## Expected abstentions

- derived partition overlaps a framed viewport -> non-owning/ambiguous
- two derived viewports overlap -> fail closed
- title partitions cannot be separated without overlap -> fail closed
- single unframed title -> unsupported, unchanged
- no vector frame and no validated strict partition -> no firm ownership
- specialized roof search bbox remains diagnostic only

## Required proof

Synthetic:
- one framed viewport plus two unframed titles whose naive page-edge partition
  would overlap the frame
- same layout translated/scaled
- vertical and horizontal partition axes
- exact boundary touch (no area overlap) stays allowed
- positive-area overlap fails closed
- input order invariance
- stable IDs/provenance replay
- no mutation
- strict columnar-grid regression
- no new authority granted to ordinary DERIVED viewports

Real shadow:
- rerun the same SHA-pinned page and prove ELEVATION 01 can no longer borrow
  floor-plan evidence under any authority-sensitive consumer.

## Benchmark firewall

No development-project expected quantities, scorer tolerances, benchmark IDs,
or target values may influence the overlap rule. The rule is purely spatial
and provenance-based.
