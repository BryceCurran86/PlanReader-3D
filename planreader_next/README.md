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
- Compute exact rectangular **floor-finish area** in square metres using Decimal integer-mm multiplication.
- Emit one stable, source-traced **MEASURED_DRAFT_REVIEW_REQUIRED** quantity per unique physical rectangle; source conflicts produce explicit ABSTAIN instead of fabricated quantities.
- Save the JSON output create-only. `commercial_publishable=false` and `benchmark_credit=false` always. No source PDFs are copied and no frozen gold is read.
- Stop double-counting identical physical rectangle refs, cross-page words, incorrect source hashes, stale revisions and forged caller area metadata.

## Commands

```powershell
cd C:\Users\bryce\PlanReader-3D-next-core
python -m planreader_next inspect --pdf "<vector.pdf>" --page 0
python -m planreader_next suggest --pdf "<vector.pdf>" --page 0 --project-id "<id>" --revision-id "r1" --output suggested.json
# Inspect suggested.json and source page. Human must independently establish
# whether the selected rectangle is the finished internal room perimeter.
# Only then change each accepted room's boundary_basis from REVIEW_REQUIRED
# to internal_finished_wall_face. Remove unsafe/unsupported room selections.
python -m planreader_next measure --pdf "<vector.pdf>" --selection reviewed.json --output draft-quantities.json
python -m pytest -q tests/test_planreader_next_source_measurement.py
```

## Critical limitations

- This proof handles only a **single native closed rectangular internal-face room per selection** (multiple independent rectangles are allowed). Most real building drawings have fragmented wall edges, doors, open passages, irregular rooms, walls above openings and overlapping annotation. Those cases **do not** get auto-resolved.
- Native dimension proximity and aspect-ratio corroboration are not source producer proof of actual figured dimension witness lines. They are sufficient only for an explicitly reviewed **draft**, not FIRM or independent accuracy credit. A user-provided boundary assertion is not considered immutable source authority.
- Does not yet authenticate FT2/FT3 definitions cross-sheet, doorway stops, wall/ceiling finishes, aperture hosts, physical W4 faces, measured openings, dynamic 3D, priced takeoffs, job estimates or a live production issuer.
- Do not take a rectangle representing furniture, joinery or outer wall faces and call it an internal finished room boundary. Do not auto-inherit adjacent finish codes from doorway labels.
- It is **not** accurate to claim that this package meets the current full PlanReader functionality, can extract real Maryborough or Lot16 room finishes automatically, raises the frozen-120 benchmark score, or has passed original-source regression. The unit tests use freshly generated **synthetic PDFs**, not private customer originals.

## Rebuild migration gate

1. Extend from vector rectangles to exact W4-backed closed planar faces with authenticated unique label ownership; preserve NO-SNAP and ABSTAIN.
2. Source-own horizontal and vertical dimension witness/terminator associations across plans; cannot promote on area-product equality alone.
3. Connect doorway/opening/threshold finish extents and cross-view finish definitions. Then ceilings and wall finishes on independently owned faces.
4. Adapt corroborated quantities to existing `QuantityEvidence` and existing customer projection/seal gates with **default-off** integration; retain original signed eight Lot16 and three Maryborough full quantity/customer bodies.
5. Run genuine private original tests and the unmodified four-project 120-item benchmark. Do not merge as production until tests, ownership and regression acceptance are complete.

This package is deliberately small so that every new feature proves one complete source-to-customer path before adding another processing layer.
