# GPT2 — exact original cross-sheet source receipt before W4 handoff

2026-10-29 AEST | Shadow/candidate safety only | No physical-wall promotion.

## Observed current behavior and call path

Source-native geometry is recovered by
`tools/diag_gpt2_source_finish_floor_handoff_shadow.audit_gpt2_source_ink_ring_translation`
from separately identified original floor and finish ring edge sets.
It supplies a SHA-owned diagnostic tuple with
`original_floor_page`, `original_finish_page`,
`original_floor_source_ids`, `original_finish_source_ids`,
`source_cross_sheet_translation_pdf_pts`,
`source_floor_perimeter_polygon_pdf_pts`,
`source_finishes_perimeter_polygon_pdf_pts`, and literal
`geometric_ink_correspondence_only=True`.

`pb_gpt2_w4_original_floor_handoff.audit_gpt2_w4_bound_original_floor`
was accepting the same status, SHA and floor box even if the purported
geometric flag were a non-Boolean truthy object; it ignored independent
finish page, edge-set membership and translated finish ring. It then
reached the existing sealed
`canonical_rooms.room_face_authority_binding_for` →
`SourceRoomFaceAuthority.resolve_scope` issuer. It never created a
metric quantity and the source floor joined only as a CANDIDATE.

## Inference and safety decision

A caller-supplied ring polygon/flag does not establish a producer-issued
native cross-sheet source correspondence. Two independently source-owned
edge universes and a consistent finite rigid translation are necessary
negative admissions, but are NOT sufficient to prove unique W4 physical
identity, finished wall faces or material occurrence.

## Proposed implementation

At the original candidate intake only, demand exact literal Boolean True,
exact positive native integer floor/finish pages with distinct values, and
two nonempty separately identified sets of exact nonblank source-owned
edge IDs with no aliases or duplicates. Require an explicit two-number
finite translation and a valid finish-source ring that is the exact
translated floor-source polygon. Keep the existing W4 room authority
and exact source-floor polygon equality intact. Do not use title-block
scales, expected benchmark values or nearest-room selection.

New tests cover malformed flags, numeric/aliased pages, duplicate and
forged edge receipts, invalid/misaligned translations, and valid
cross-sheet candidates that still STOP at the sealed W4 owner when
unavailable. No source original is copied to public CI.

## Authority and retention limits

No source material occurrence, metric area, ceiling, signed/customer
row, JobHub output, or frozen 120-item score can be granted here.
Keep source identities and conflicting candidates, never collapse ties.
Original customer PDF and token remain private. Other agents' files,
20,000 primitive cap and 2.5-pt snap are not modified.

Full exact-head Python 3.13/3.14 CI, source-positive owner-trusted
replay, and final diff check remain release gates; synthetic-only green
tests cannot authorize original quantity publication.
