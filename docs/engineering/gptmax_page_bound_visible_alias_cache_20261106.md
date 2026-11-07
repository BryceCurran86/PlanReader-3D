# Reuse one authenticated page's native visibility read views

## Observed source/runtime trace

Read AGENTS.md, engineering playbook, W1-W10 measurement/firewall/CI rules and
the three-agent takeover. At current main 0cc74650 the existing original
Maryborough scoped room producer exceeded a 240s local diagnostic limit below
1.2GiB. A second bounded stack capture sampled `_native_visible_alias` and its
JSON payload hash via `_reusable_page_rows` ->
`authenticated_visible_observations` -> `_native_dimension_source_proof_batch`
-> `_producer_proven_page_opening_records` -> physical wall composition.

The source observation and full visibility ingestion stages separately finish
below 1.5GiB. This does not establish the cause of the larger role's prior
memory failure. It identifies avoidable CPU work in repeated page proof reads:
the existing index verifies unchanged source/snapshot/flat maps and receipts,
then recreates each native visible alias and hashes its payload again.

## Proposed bounded representation change

Retain at most one page's returned bound rows and their private source views
per source store. A hit requires the same published snapshot, record and
fingerprint flat-map identities, page address, source parent/record identities,
and origin receipts. Validate the full existing receipt index first, and
compare every returned record field with its private source view before reuse.
Caller mutation misses and rebuilds; source/snapshot/fingerprint/receipt changes
miss and undergo the existing independent source validation. Full source-byte
and competitor checks at proof entry/exit are retained. A new page replaces the
prior cache entry; no all-pages alias cache or persistent source duplicate.

## Expected outputs and proof

IDs, payload hashes, ordering, source snapshots, physical authority and signed
customer quantities must stay identical. Prove repeated page reads do not
rematerialize aliases, remain equal to scalar/full reads, return a fresh tuple,
and retain only one page. Attack returned clones, parent/competitor geometry,
fingerprints, receipts and native origin kinds. Exercise existing opening and
dimension batch tamper suites, then original bounded producer progress and
historical sealed/customer retention. Final fixed-head dual-Python/source gates
are required before release. The fixed #4223 candidate is untouched.

## Benchmark exclusion

This is a producer-owned read-view cache, not evidence or a measurement rule.
No frozen item/value/map, PDF source text/coordinates, 20k cap or 2.5pt snap
changes. No accuracy or memory-limit resolution is claimed from a cache hit.

## Focused implementation proof

The repeated-page read regression failed on the prior implementation, which
rebuilt all aliases. The fixed cache passes 73 source/visibility/physical-index
and dimension-batch tests. Returned-clone mutation still reconstructs the
authentic view, changing pages replaces the single entry, separate producers
share nothing, and off-page record/fingerprint damage still rejects the proof.

Four additional origin-receipt negatives exposed a pre-existing freshness gap:
both the full-read and page-index caches failed to notice a native visible
origin kind changed after authentication. Their identity checks now retain and
compare that receipt as well; all four mutations reject and enter independent
source revalidation. This does not change any valid original source reading.
Public source bytes, source IDs/values, per-page inventory and default authority
remain unchanged; final original/full-CI gates are pending.

## Confirmed cache-retention defect

`_SourceObservationProducer._commit` deliberately releases obsolete flattened
read maps using `retain_flats`, while preserving immutable source history.
`_remember_page_index` previously retained one entry per derived snapshot,
holding those same complete observation/fingerprint dicts alive indefinitely.
The synthetic real raster-producer sequence fails on its second snapshot:
two full indices remain despite the documented one-snapshot cache policy.
Bound this index to one snapshot and drop the previous bound-page hint when
replacing it. All historical source snapshots, records, fingerprints and
receipts remain; the test independently re-proves the old selector after
eviction and compares its complete rows. This removes a demonstrated retention
defect, but only an original bounded role replay can determine its contribution
to the earlier 5GiB MEMORY_LIMIT.

The same real producer sequence also exposed a retained whole-source clone
hint: a page proof at a new snapshot removed only a cache key for the new ID,
leaving the older snapshot's complete bound-row cache alive. Clear that
disposable hint for every page proof. The extended regression failed before
this change and still re-proves all historical source rows after eviction.

For that replay, retain the existing `run_logged` numeric resource-usage values
in the existing role-status rows instead of discarding them. Allow only its
three existing nonnegative integer/None fields. This is private diagnostic
metadata, not a seal/customer/quantity schema. The private workflow may report
only those aggregate numbers and its existing allowlisted process classes.
