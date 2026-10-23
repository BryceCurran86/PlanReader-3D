# Batch44 — producer visible-segment geometry vs opening parents

## Observed

- Prior censuses counted `published.snapshot.visible_observation_ids` (always empty on `ProducerSnapshotRecord`).
- Producer wrapper `PublishedVisibleSourceSnapshot.visible_observation_ids` on Lot16 p3: **4086** (2359 `raster_pdf_visible_segment` + 1727 `native_pdf_visible_segment`).
- 2069 usable W4 primitives resolve into that geometry index; 262 do not.
- Opening parent lines vs those observation geometries: **0 exact, 0 collinear overlap** on all 6 unhosted openings → `observation_geometry_identity_unavailable`.
- Kind-unproven split: 6 empty kind; 1 `door` token without evidence IDs.
- Eight 870 mm width-only labels: `door_height_second_axis_unavailable`; no canonical `height_record_id` / `height_m`.

## Inference (not authority)

- Opening-primitive segment geometry is a different producer object from W4 `raster_segment` / visible-segment geometry, not merely an ID-namespace mismatch.
- Digit-tail collisions (batch42) remain numeric coincidence.

## Proposed (shadow only)

- Keep observation-geometry identity fail-closed.
- Unique exact or unique collinear overlap would still be `…_review_only` (no host).
- Multi-wall overlap abstains.

## Benchmark that must not drive algorithms

- Expected BOQ / V2 scores; signed area values.
