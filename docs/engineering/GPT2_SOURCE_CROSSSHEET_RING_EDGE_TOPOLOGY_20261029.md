# GPT2 — source-native cyclic room-ring edge correspondence

2026-10-29 AEST | candidate-only original source geometry | third disjoint lane claim.

## Observed path

`tools.diag_gpt2_source_room_graph_shadow.audit_original_room_edge_graph`
builds source-native, SHA-owned degree-two closed rings with ordered
`source_simple_ring_candidate.vertices_pdf_pts` and edge IDs.
`tools.diag_gpt2_source_finish_floor_handoff_shadow.audit_gpt2_original_cross_sheet_ring_correspondence`
consumes two such independently sourced room rings plus the registration
receipt. It currently compares translated **sets of vertices** and equal
source-edge counts. It returns an
`original_source_ink_ring_translation_candidate` receipt (no quantity).

## Observed defect / inference

Different *simple* floor polygons can use exactly the same vertex
coordinates in different non-intersecting cyclic orders. Equal vertex sets
and same source edge counts therefore do NOT establish matching room
perimeters. Neither set equality nor a source registration witness is a
physical W4 wall-face source authority. Reusing their alleged correspondence
would misstate room/finish identity in later candidate adapters.

## Proposal and implementation

Compare every translated **undirected cyclic boundary edge**, not just
vertices, after the existing original 0.001pt native point precision.
Include the closing edge. Require a valid source/finish polygon and
unique vertex/edge memberships. This preserves invariance to starting
vertex, reversal, native stroke direction, input order and rigid
translation. A rival ring with the same vertices but a different
topological cycle must abstain under a specific negative reason.
Do not pick one of multiple candidates.

Tests use independently generated synthetic native PDF pages through the
actual `audit_original_room_edge_graph` producer, comparing an unchanged
translated room and a non-equivalent simple rival with the same vertex
multiset and number of strokes. No benchmark gold, target floor metric,
finish schedule or customer original is consulted.

## Authority and release

Keep status source-only CANDIDATE; do not reclassify walls, supply metric
scale, infer a threshold, sign a quantity or affect commercial customer
projection. Preserve source SHA/page/revision and all original edges.
Owner p11 FT2/FT3→p7 W4 actual physical wall/doorway ownership remains
independently unresolved. Python 3.13/3.14 exact-head CI, original
trusted replay, final diff and signed/customer retention are release
gates; no accuracy credit before those checks.
