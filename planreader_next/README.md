# PlanReader Next — small source-bound measurement vertical slice

**Status: executable experimental engine; NOT production and NOT official V2 benchmark scoring.**

This independent package lives next to the existing application. It reuses
`pb_vector_geometry_v130.extract_native_page` and
`native_word_primitive_ref` for actual PDF primitives, but does not rewire
PlanReader/JobHub, compete with frozen V2 producers or change any signed rows.

## What actually works

- Inspect a native vector PDF page for stable rectangle/word primitive references and SHA.
- Suggest conservative rectangle/room/FT floor-code/figured-axis matches without selecting tied dimensions.
- Require review of **internal finished-wall-face** boundary ownership: suggestions always say `REVIEW_REQUIRED`; they are not auto-approved.
- Bind two independent original figured dimension words, with proximity to the correct horizontal/vertical rectangle axis, a dimension ratio check and a native room label + finish code **inside** the same closed source rectangle.
- Compute exact rectangular **floor-finish area** in square metres using Decimal integer-mm multiplication. Manually reviewed **irregular polygons** may also be measured from a consecutive closed chain of actual native PDF line/rect-edge receipts, without joining gaps or inventing endpoints. Polygon area scales source geometry using two selected, nearby figured dimension words; this remains a review draft, NOT an independently proven source metric.
- Emit one stable, source-traced **MEASURED_DRAFT_REVIEW_REQUIRED** quantity per unique physical rectangle; source conflicts produce explicit ABSTAIN instead of fabricated quantities.
- Save the JSON output create-only. `commercial_publishable=false` and `benchmark_credit=false` always. No source PDFs are copied and no frozen gold is read.
- Stop double-counting identical physical rectangle refs, cross-page words, incorrect source hashes, stale revisions and forged caller area metadata.

## Commands

```powershell
cd PlanReader-3D-next-core
python -m planreader_next inspect --pdf "<vector.pdf>" --page 0
# For a nonrectangular manually traced boundary, list exact source line refs:
python -m planreader_next inspect --pdf "<vector.pdf>" --page 0 --include-segments
python -m planreader_next suggest --pdf "<vector.pdf>" --page 0 --project-id "<id>" --revision-id "r1" --output suggested.json
# Inspect suggested.json and source page. Human must independently establish
# whether the selected rectangle is the finished internal room perimeter.
# Only then change each accepted room's boundary_basis from REVIEW_REQUIRED
# to internal_finished_wall_face. Remove unsafe/unsupported room selections.
python -m planreader_next measure --pdf "<vector.pdf>" --selection reviewed.json --output draft-quantities.json
python -m pytest -q tests/test_planreader_next_source_measurement.py
```

## Critical limitations

- This proof supports native closed rectangles and manually selected exact **closed native line polygons** (multiple independent rooms are allowed), but **does not automatically resolve** fragmented wall edges, doors, open passages, irregular room ownership, walls above openings or overlapping annotation. A manually traced polygon requires an ordered list of `boundary_segment_refs`, source-backed axis words, and independent review of the interior-finished-face boundary. If any edge is missing, it ABSTAINS rather than closing it. Auto-suggestions currently cover native rectangles only.
- Native dimension proximity and aspect-ratio corroboration are not source producer proof of actual figured dimension witness lines. They are sufficient only for an explicitly reviewed **draft**, not FIRM or independent accuracy credit. Polygon metric area additionally assumes its selected horizontal and vertical figured numbers span the full source polygon bounding extents; do not apply without independently checking both spans. A user-provided boundary assertion is not considered immutable source authority.
- Does not yet authenticate FT2/FT3 definitions cross-sheet, doorway stops, producer-owned wall/ceiling finish occurrences, physical W4 host authority, irregular real-plan openings, dynamic 3D, priced takeoffs, JobHub estimates or a live production issuer. The new wall/ceiling/door/frame measurement path is reviewer-selected DRAFT evidence only.
- Do not take a rectangle representing furniture, joinery or outer wall faces and call it an internal finished room boundary. Do not auto-inherit adjacent finish codes from doorway labels.
- It is **not** accurate to claim that this package meets the current full PlanReader functionality, can extract real Maryborough or Lot16 room finishes automatically, raises the frozen-120 benchmark score, or has passed original-source regression. The unit tests use freshly generated **synthetic PDFs**, not private customer originals.

## Rebuild migration gate

1. Extend from vector rectangles to exact W4-backed closed planar faces with authenticated unique label ownership; preserve NO-SNAP and ABSTAIN.
2. Source-own horizontal and vertical dimension witness/terminator associations across plans; cannot promote on area-product equality alone.
3. Connect doorway/opening/threshold finish extents and cross-view finish definitions. Then ceilings and wall finishes on independently owned faces.
4. Adapt corroborated quantities to existing `QuantityEvidence` and existing customer projection/seal gates with **default-off** integration; retain original signed eight Lot16 and three Maryborough full quantity/customer bodies.
5. Run genuine private original tests and the unmodified four-project 120-item benchmark. Do not merge as production until tests, ownership and regression acceptance are complete.

This package is deliberately small so that every new feature proves one complete source-to-customer path before adding another processing layer.


## Next run: walls, ceilings, doors and frames (source-backed drafts)

The combined `takeoff` command reads a **single original PDF with multiple
pages**, including a floor plan and door schedule; it resolves each row only
against the selected native source refs and emits a single packet.

```powershell
cd PlanReader-3D-next-core
python -m planreader_next inspect --pdf "<plan-and-schedules.pdf>" --page 0 --include-segments
python -m planreader_next inspect --pdf "<plan-and-schedules.pdf>" --page 1
# Prepare a reviewed-building.json with source_sha256, project_id, revision_id,
# and optional rooms, ceilings, walls, doors arrays as described below.
python -m planreader_next takeoff --pdf "<plan-and-schedules.pdf>" --selection reviewed-building.json --output building-draft.json
python -m pytest -q tests/test_planreader_next_building.py tests/test_planreader_next_source_measurement.py
```

The `takeoff` selection is a set of **reviewer-confirmed references**, not a
prompt asking the AI to invent a rectangle, guessed height or wall host.

- `rooms`: existing `measure` room selection plus `page_index`; verifies
  rectangle or exact closed native polygon, two original dimension words,
  source-owned room and finish words, and reviewed internal-finished-face basis
- `ceilings`: distinct `ceiling_id`, `room_id`, `page_index`, actual
  ceiling-zone `rectangle_ref` (or `boundary_segment_refs` exact polygon),
  two original figured-axis refs, source room and ceiling-finish word refs
  (e.g. IPF1/GRID); `boundary_basis=source_owned_ceiling_zone`. A floor area
  is NEVER simply copied to a ceiling: the reviewed RCP zone must be supplied
- `walls`: `wall_id`, `page_index`, one exact
  `face_segment_ref`, figured `length_word_ref` on that wall's native page,
  actual height `height_word_ref` plus its `height_source_page_index`
  (typically an elevation or schedule), source `finish_word_ref` near the
  wall, and `face_basis=internal_finished_wall_face`. Output: wall length
  (m), gross finish area (m²) and net finish area (m²) **only if** the
  complete reviewed hosted door universe is supplied, measured and reconciled
- `doors`: `door_id`, explicit `host_wall_id`, plan and schedule page
  indices, original plan/schedule door-code word refs, native plan
  `opening_segment_ref` contained on its reviewed host wall line, width
  and height `schedule_*_word_ref` from a matching authentic schedule row,
  plus `host_wall_length_word_ref` for a dimension-vs-geometry ratio check,
  and `opening_reviewed=true`. Output: door count (ea), leaf width/height
  metadata (m) and leaf area (m²). Do not assume the schedule's word adjacency
  alone proves an opening or schedule identity
- `door frames`: for a door, also supply `frame_reviewed=true`,
  `frame_word_ref` from the SAME matching schedule row, and explicit
  `frame_configuration=three_sided` or `four_sided`. Output: distinct
  frame count (ea) and 2 jambs + head (+ sill if four-sided) frame length (m).
  A door still counts if frame evidence is absent; the frame explicitly ABSTAINS

**Net wall example on generated source evidence:** one 4.000 m long wall at
2.400 m height has a 9.600 m² gross area; a source-matched 920 × 2040 mm door
has 1.8768 m² leaf area; *after reviewed host/opening confirmation* the draft
net face is 7.7232 m². The associated reviewed three-sided frame length is
5.000 m. A separately drawn 4025 × 3297 mm ceiling region is 13.270425 m².
These are synthetic examples, **not** claims of measured Maryborough/Lot16
customer work or published benchmark accuracy.

**What remains intentionally unsupported:** automatic wall-face ownership,
unlabelled/fragmented walls, genuine wall holes where physical aperture geometry
cannot be reconstructed, arbitrary cross-sheet zone correspondence,
elevation dimension witness/leader matching, frames without an authentic
same-row frame source note, unfigured ceiling/door heights, and fully automatic
quantity or commercial issuing. Source-linked human review is still required;
even a reviewed measurement is a `MEASURED_DRAFT_REVIEW_REQUIRED` with
`commercial_publishable=false` and `benchmark_credit=false`.

**Owner's external-door 2100-mm rule:** for an authenticated external door
without any figured height, 2100 mm can be shown separately as **provisional
"Assumed 2100 mm — verify on site"**, never as FIRM. This experimental
engine currently **abstains** instead of using that fallback; injected
`assumed_height_mm` and `price` fields do not affect a quantity. Production
must preserve that distinction and must not claim a source-signed frame area.

This is not yet a substitute for the older commercial pipeline. Maintain the
default-off isolation and preserve the frozen 120 denominator, eight signed
Lot16 opening areas and three signed Maryborough floors.
