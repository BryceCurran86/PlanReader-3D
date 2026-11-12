# Reuse authenticated page views for original figured room dimensions

## Observed behavior

The original Maryborough signed-three producer on exact head
1f9ac18681fa6fe7a103d2fd43bc19e27252126d exceeded a 900-second private replay
budget without producing a signed/customer result. Read-only stack samples
showed room-label RapidOCR first, followed by
SameViewRoomAreaProducer.publish -> _trusted_native_dimensions_for_page ->
SourceVisibilityAuthority.resolve_visible -> _native_visible_alias_identity_holds.

The dimension consumer resolves every visible segment separately for every
eligible room's dimension search. Its existing dimension-bundle cache does
not cache these independently recreated source views.

The source authority already has an authenticated single-page bound-row cache,
documented in gptmax_page_bound_visible_alias_cache_20261106.md. Physical wall
and dimension proof consumers already use that existing API.

## Change and authority boundary

Use SourceVisibilityAuthority.authenticated_visible_observations with the
original published snapshot and bind_page_id in the existing dimension
consumer. Keep its native segment/page filters, unique source mapping,
dimension text, witness, candidate-span, geometry and quantity rules intact.
A RuntimeError from the existing authority supplies no figured dimensions.

The authority continues to validate source bytes, current revision, complete
snapshot/receipt universe, parent identity, fingerprints, origin kind and
returned-clone integrity. Its existing bounded page cache owns reuse and
invalidation. No new cache, caller-provided trusted geometry, visibility
vocabulary, quantity producer or source interpretation is introduced.

## Verification scope

The regression compares complete same-view and cross-view area records with
the previous scalar source proof, checks that repeated queries stop rebuilding
native aliases, and attacks a warmed proof through parent geometry, fingerprint,
origin receipt, source bytes and returned-clone mutation. Existing same/cross-view
dimension, page-cache and batch tampering suites remain applicable.

The two sampled runtime phases are observations, not a measured speedup or
proof that OCR cost is solved. Record focused tests and a new exact-head private
replay before claiming faster completion or signed/customer retention.

The frozen #4301 aa1f985f release candidate and its running source jobs stay
unchanged. Frozen120, original PDFs, signed fixtures, 20k primitive cap and
2.5-point snap are unchanged. No new quantity or accuracy point is claimed.
