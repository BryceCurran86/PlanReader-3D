# GPT2 — source visibility compiler doorway-page identity gate

2026-10-29 AEST | Original source, candidate only | No quantity.

## Actual source path and first failure

The source-only `GPT2OriginalSourceGeometryBridge` uses the sealed
`SourceVisibilityProducer` revision to re-read source bytes and
confirm independently decoded floor and finish page coverage. Its
`original_doorway_bound_floor_finish_handoff` accepts two previously
SHA-checked source-native doorway rings, then calls
`audit_gpt2_original_doorway_bound_floor_finish_correspondence` and
`audit_gpt2_source_material_floor_handoff`.

The original doorway-ring producer
`audit_original_doorway_ring_candidate` emits a typed
`original_page_1_based` field on each candidate. Previously the compiler
checked only that both ring roots matched the PDF SHA; it did not check
the pair of pages passed to its own source-visibility coverage check.
A same-document source ring from other pages could therefore enter this
compiler scope under a misleading floor/finish page pair. This is not a
W4/FT source quantity issuer, but compromises diagnostic page lineage.

## Proposed source binding

Require the two requested original pages to be distinct. Before any
geometry/material call, require each input to be a dictionary with the
expected candidate original source receipt status and exact typed
`original_page_1_based` matching its own decoded page. Keep the
existing same SHA and all downstream original geometry/finish gates.
Reject wrong, missing, swapped, Boolean, string, and same-page evidence
without accepting another room by proximity, and without decoding public
original PDFs or publishing m².

Tests inject an already-decoded producer snapshot and assert the
compiler NEVER calls the geometry/material issuers for mismatched
page roots; a valid source pair remains only a noncommercial
candidate compilation with `new_firm_quantities=0`.

## Release and preservation

Actual Maryborough p7/p11 source W4 finished faces and doorway
ownership remain unresolved. No frozen 120-item benchmark truth,
signed customer rows, JobHub output, source PDF/token, 2.5 pt snap or
20,000 primitive cap is changed. Exact-head dual Python3.13/3.14 CI,
private original replay and owner source evidence review are required
before any physical quantity publication or benchmark credit.
