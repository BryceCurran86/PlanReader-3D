# F.07 Authoritative-Derived → Migration Viewport Ownership Architecture Report

Base main: `7a498ef9e5456e2b4d0cd9e5ebfe7801410ca5c4`

## OBSERVED

### F.07 producer

`pb_viewport_segmentation.py::segment_page_viewports` produces `SegmentedViewport` records.

For the strict producer-owned derived subtype, `_columnar_title_grid_partitions` emits:

- `status="derived"`
- `boundary_source="title_partition"`
- exact `bounding_box`
- `provenance.partition_mode="columnar_title_grid"`
- `provenance.grid_validated=True`
- `column_index`
- `column_count`
- `row_index`
- `row_count`
- `title_bbox`
- `duplicate_title_bboxes`

`is_authoritative_derived_viewport(viewport)` accepts only that subtype:
DERIVED + TITLE_PARTITION + bbox + `columnar_title_grid` + `grid_validated=True`.
The helper is already intentionally narrower than ordinary DERIVED title partitions and does not need to be broadened.

F.07 also has `validate_non_overlapping_viewports`, which rejects positive-area overlap among usable RESOLVED/DERIVED siblings.

### Migration contract

`pb_migration_contracts.py::ViewportEvidence` contains:

- viewport/document/page identity
- bbox
- view type
- resolution status
- evidence/scale IDs
- confidence/reasons
- generic `metadata`

It does **not** carry an authenticated F.07 producer lineage field or a typed F.07 provenance contract.

### Existing conversion path

There is no canonical current-main constructor or adapter that takes a `SegmentedViewport` and returns a migration `ViewportEvidence`.

Observed consumers/tests construct `ViewportEvidence` manually. Examples include:

- `tests/test_viewport_scale_binding.py::_evidence`
- direct `ViewportEvidence(...)` construction in the same scale tests
- `scripts/wall_linear_authority_real_drawing_shadow.py`

`pb_viewport_scale_binding.py::viewport_evidence_with_bound_scale` only updates an already-created `ViewportEvidence`; it is not an F.07 → migration adapter and does not preserve F.07 provenance.

Therefore the producer provenance named above is currently lost at the migration boundary unless a caller manually copies it.

### #881 ownership check

`pb_figured_span_scale_shadow.py::_scope_blockers` currently accepts only `ViewportResolutionStatus.RESOLVED` and rejects DERIVED with `viewport_not_resolved`.

That is safe today because no authenticated F.07-derived lineage exists at the `ViewportEvidence` boundary.

## INFERENCE

The key question is:

> Can an exact producer-owned F.07 `columnar_title_grid` viewport be represented at the migration `ViewportEvidence` boundary without laundering caller-supplied metadata?

**Current answer: no.**

Copying `SegmentedViewport.provenance` into `ViewportEvidence.metadata` by a caller would preserve values but not authority. A downstream caller could populate the same strings/booleans and falsely claim `grid_validated=True`.

The current architecture therefore matches acceptable outcome **C/D**:

- provenance is not canonically preserved, and
- free-form downstream metadata is forgeable and must not be trusted as certification.

## PROPOSED CHANGE

Add the smallest producer-owned migration adapter/seal without changing F.07 geometry or `is_authoritative_derived_viewport`.

1. Add a private producer lineage token/fingerprint to `SegmentedViewport`.
   - It is stamped only by `segment_page_viewports` after F.07 has completed.
   - Directly constructed `SegmentedViewport` objects used by callers/tests remain valid records but are **not producer-authenticated**.
   - The fingerprint covers the exact producer-owned ownership fields, including bbox, title bbox, status, boundary source, label/view type and provenance.
   - Any downstream mutation of bbox/title/provenance invalidates the fingerprint.

2. Add a dedicated adapter module for the migration boundary.
   - Input: full page-level F.07 viewport set, selected viewport ID, document/source/revision ownership.
   - Validate the producer token/fingerprint.
   - Validate exact page/view identity.
   - Validate the complete sibling set remains non-overlapping.
   - For DERIVED authority, call the existing `is_authoritative_derived_viewport` unchanged.
   - Preserve all requested F.07 provenance fields into `ViewportEvidence.metadata` for observability.
   - Return a separate sealed ownership proof object for authority decisions; do not trust metadata itself.

3. Narrowly extend #881 ownership checks.
   - RESOLVED migration viewports continue to work exactly as before.
   - DERIVED may enter only when accompanied by the sealed F.07 ownership proof from the adapter.
   - The proof must match document/source/revision/page/view ID and exact bbox.
   - Ordinary DERIVED, forged metadata, changed bbox, introduced sibling overlap, stale source/revision, or mismatched title ownership remain blocked.

4. Do not change:
   - `is_authoritative_derived_viewport`
   - F.07 segmentation heuristics
   - #881 scale reconciliation
   - canonical 5% scale tolerance
   - live scale publication / `bind_viewport_scale`
   - roof geometry/publication
   - commercial quantities / JobHub
   - benchmark files

## BENCHMARK FACTS EXCLUDED FROM IMPLEMENTATION

KSTVET and Lamu are development validation sources only.

No expected BOQ quantity, benchmark score, tolerance, item mapping, project filename/page identity, or project-specific rule will be used by the implementation.

The adapter and ownership proof will operate only on generic F.07 producer records and migration ownership context.

## DECISION

Proceed with acceptable outcome **C + D**:

- preserve F.07 provenance through a producer-owned adapter;
- seal the ownership boundary so arbitrary `ViewportEvidence.metadata` cannot mint authoritative-derived status;
- then allow #881 SHADOW to accept RESOLVED or strictly authenticated F.07 authoritative-derived ownership only.
