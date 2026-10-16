# GPT2 — four source-authenticated Maryborough rooms: first measured-quantity gate

**Architecture-only design for independent review. No producer change, false FIRM, changed room, or benchmark truth.**
Tracking [#2009](https://github.com/BryceCurran86/PlanReader-3D/issues/2009).
Immutable original source PDF SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.

## Source and code read before this report

- `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`,
  `docs/wall_topology_observability_architecture.md`,
  `docs/planreader_wall_room_topology_spec.md`,
  `docs/planreader_public_tender_benchmarks.md` (retired system), and
  `.github/workflows/ci.yml`.
- `tools/diag_gpt2_source_room_handoff_integrity.report_source_room_handoff`,
  `pb_same_view_room_area_authority.SameViewRoomAreaProducer.publish`,
  `pb_cross_view_room_area_authority.CrossViewRoomAreaProducer.publish`,
  `pb_cross_view_room_area_authority._trusted_native_dimensions_for_page`,
  `_figured_pair_scale_consistent`, `_line_inside_dimension_pair`,
  `_witness_systems_intersect`,
  `pb_page_scale_calibration_authority.resolve_page_scale_calibration`, and
  `pb_figured_dimension_authority.resolve_measurement_authority`.
- Independently downloaded GitHub original-source run
  [38253592536](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38253592536),
  artifact **11750297601**, both original-producer JSON reports
  `original-maryborough-source-room-handoff.json` and
  `original-maryborough-floor-publisher-firstgate.json`.

## Observed (producer evidence; NOT a hypothesis)

The exact original source replay generated 687 canonical room/floor candidate records
and exactly eight producer-owned room+label objects. Three have FIRM authenticated
*documented* floor areas and verified customer review rows (not V2 scored):
Food Prep **13.270425 m²**, Office **9.05352 m²**, Cold Room **25.37875 m²**.

Four other rooms have **unique actual source-room face record IDs, labels,
independently backed source text observation IDs, physical room IDs and
canonical floor IDs**, but NO source-qualified metric area:

| Genuine source label | Physical room ID | Original source-face RECEIPT | Canonical floor ID | First failed authority |
|---|---|---|---|---|
| PWD | `live_physical_room_decceeeb5c395a8edee347b1454f0881` | `source_room_face_record_6722d55c0ce8c8a8706cdcc6094860f9` | `physical_room_floor_surface_5c7f261811485d3597a232c1380b277f` | FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE |
| AIRLOCK | `live_physical_room_660be6e4e831de172db0f00da88fd333` | `source_room_face_record_a0f786d8997e532c332b1a1c28980d14` | `physical_room_floor_surface_a4a5b86baf91c1d182dab8fad3c3ce01` | FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE |
| LAUNDRY | `live_physical_room_7f1b099c553030e42f0dca9e0fe22f1d` | `source_room_face_record_dde9e143bdd9627f96b7d5aaaea51f7f` | `physical_room_floor_surface_7e38f196edcfcd1d8c4b6f896f766856` | FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE |
| SALES | `live_physical_room_1807f9a27fa6ee477e5b48894d9a3aec` | `source_room_face_record_42bef3e350b3cc042f17107fe610f0d8` | `physical_room_floor_surface_e0ee4e3fccc46a209378e0fde18ad3c8` | FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE |

**Each** reports these exact three original rejection reasons:
`cross_view_owned_dimension_pair_unavailable`,
`physical_scale_bar_unavailable`,
`same_view_figured_pair_scale_inconsistent`.

Their room label record IDs and original word evidence are preserved in the
source artifact. Source page `7`, viewport `view_p7_2`. These original
objects are NOT source metric areas; page-point² must never be treated as m².
No decision_scope_id or source snapshot may be borrowed from another
source-producer replay. Current snapshot/scope must be obtained *directly*
from the matching producer record in any later quantity handoff.

**FREEZER is a different failure**: its authoritative read-only source-room
handoff has `SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE` and no canonical floor;
the later floor-publisher diagnostic's candidate room/floor does not waive
that polygon failure. Original p7 FREEZER crossing W4 diagonal has no native
l/re full-span (source PR #2768). All remaining
POS COUNTER/FOOD SERVICE/WASH UP/TRUCK DRIVER LOUNGE/M-AMB/F-AMB/DRY STORE
have `SOURCE_PHYSICAL_FACE_UNAVAILABLE`, not merely a quantity failure.

The original source floor publisher separately verifies **three** quantity
reissues and **three** review rows, **zero** floor-finish and ceiling-lining
quantities; `commercial_estimator_approved=False`.

## First producer call-path failure

`SameViewRoomAreaProducer.publish` begins from unique physical room and exact
trusted label, calls original source
`_trusted_native_dimensions_for_page`, and only accepts one uniquely owned
horizontal+vertical figured-dimension pair. It invokes
`_figured_pair_scale_consistent` to detect disagreement in their inferred
drawing ratios. That helper calls **existing**
`resolve_page_scale_calibration` only as a conflict/rejection gate. It DOES
NOT supply standalone metric authority. Non-matching/conflicting pairs
abstain as `same_view_figured_pair_scale_inconsistent`.

`CrossViewRoomAreaProducer.publish` independently requires a real source
support-page label and witnessed, owned dimension pair. Its result for these
four is `cross_view_owned_dimension_pair_unavailable`. The physical-scale
path independently returns `physical_scale_bar_unavailable`.

The first attack should therefore be **figured-dimension provenance and
witness-system identity**, *not* more room-label segmentation, a global
geometry snap, guessed page scale, derived-box overlap or arbitrary matching
of two differently scaled figured numbers.

## Inference (not authenticated)

A native figured horizontal and vertical pair *might* exist that is currently
being rejected because its original witness spans/figure values disagree, or
because an annotation belongs to a different drawing region. It could also
be truly inconsistent in the original; the present evidence does NOT prove a
bug or any missing area. Selecting the nearest pair or tweaking scale ratios
to fit a room would be self-certification.

## Smallest proposed next diagnostic — review gate

1. Replay the exact immutable original page-7 source from the same
   SourceVisibilityProducer and LiveCanonicalRoomComposition; select the
   four rooms ONLY by their **producer-issued face receipt/physical room IDs**.
   Names in this report are reporting selectors, never detection inputs.
2. Observe the existing `_trusted_native_dimensions_for_page` once,
   WITHOUT substituting results or re-reading OCR with changed thresholds.
   Retain every candidate's original page, source partition, source word
   observation, dimension ID, endpoint/witness IDs, units, orientation,
   source label line and original source snapshot/decision scope.
3. For all possible H×V pairs, retain source-authenticated reason for each
   gate: same-source label ownership, source witness overlap, ratio
   consistency, competing pairs, original material/viewport conflicts.
   Capture **both** inferred ratios and the exact existing calibration
   status/reasons. These remain CANDIDATE diagnostics.
4. Require adversarial original-source and synthetic replay:
   duplicate/foreign source words, source snapshot drift, cross-page label
   collisions, different rotation and scale, segment splitting,
   candidate permutation, source-label multiplicity, duplicate witnessed
   dimensions, conflicting original ratio, nonfinite values, source mutation,
   preservation of the original three FIRM reissues and all grid negatives.
5. Only if a **unique source-owned** pair and consistent original witness
   systems genuinely exist, propose a separate generic change at the FIRST
   failing authority, with original source and downstream independent review.
   GPT1 still publishes QuantityEvidence through existing measurement seam;
   GPT3 still verifies exact signed original source lineage separately.

## Excluded benchmark / implementation impact

No Full Plan V2 reference_takeoff, object_universe, expected tolerances,
denominator, scorer, project names or target numeric areas may act as
prediction input; the historic selected 8/51 score is NOT a heuristic
or test oracle. Do not change W2 2.5pt snap, W3 abstentions, W4 source IDs,
typed GRID, native PDF glyph/clip/OCR rules, FT3 semantics, frozen truth,
canonical graph, scale resolver, commercial signatures or original PDFs.

**This PR is the AGENTS.md first architecture deliverable. Stop for
independent source-authority review before adding any new producer code.**
