# Reuse complete page opening proofs across W4 scopes

Observed path: PhysicalWallCandidateProducer reconstructs source wall scopes;
_producer_opening_relation_overrides previously called prove_existence for
every visible page observation again in each W4 scope. Individual existence
results are cached, but the complete page scan and its authority calls were
still repeated. This change memoizes the complete deduplicated positive page
inventory in the existing producer-owned PhysicalOpeningAuthority.

Before every cache hit, reauthenticate the complete original visible snapshot.
Any supplied page index must exactly equal the authenticated page inventory.
Bind document, revision, source SHA, snapshot and page in the cache key, and
require the same producer's source store/authority. Damaged observations on
another page still invalidate reuse; a caller subset, geometry preflight,
wrong authority or candidate assertion cannot supply the cache.

Every authenticated observation is proved on the first visit. Even small page
inventories are traversed; there is no new family/count/completeness assumption.
The tuple contains only existing corroborated individual existence records.
No wall-face protection or partial SAME translation from the blocked #2078
branch is included. Source filtering, equivalence, geometry and identities
retain their original decisions.

Tests verify first-scan coverage, zero repeated prove_existence calls on reuse,
page separation, cold/warm integrity rejection, damaged non-support evidence,
wrong producer rejection and no cache poisoning. Real all-source Lot16 reports
are compared field for field, normalizing only two existing unordered void
reason-code lists. Original Maryborough host/frame parity remains required.
This removes redundant work; it does not claim that a production timeout is
solved without a completed real run. It authenticates no opening count, scale,
dimension, quantity, measurement or seal; the 20,000 primitive cap is unchanged.
