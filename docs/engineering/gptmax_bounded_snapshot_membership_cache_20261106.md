# Bound derived snapshot membership read hints

## Observed original allocation and call path

Read AGENTS.md, engineering playbook, W1-W10/firewall/CI, takeover, and
`SourceObservationProducer._commit` -> the source store's membership cache ->
`SourceObservationAuthority.resolve` / `snapshot_contains_observation`.
The original c08a5b63 whole-role run still hit its5GiB guard at5,284,172KiB.
A separate3GiB/180s original composition observer measured60 snapshots and
435,370 stored observations while membership frozensets alone occupied
1,006,645,920 bytes. Each small derived commit added16,777,432 bytes. Native
and text receipt counts were unchanged during the measured growth interval.
The observer is private, counts-only and not a source/customer acceptance run.

## Inference and bounded correction

The immutable snapshot ID inventory is authoritative; a frozenset rebuilt from
that inventory is a disposable membership acceleration hint. Previously every
commit/read retained another complete set for every historical snapshot.
Retain only three recent membership hints, consistent with the existing
source/current/parent flat-read working set. Historical source snapshots,
records, fingerprints, IDs and lineage remain. An old selector rebuilds its
set on demand; snapshot object identity still invalidates a stale set.

Reuse the existing OrderedDict dependency. Route commit-time and read-time
cache insertions through the same bounded helper, with read hits refreshed.
No source scope, primitive, geometry,20k cap,2.5pt snap, measurement authority,
quantity ID/value/body or frozen input changes. The already-reviewed empty
scale-word fastpath is included as a separate preceding commit; it preserves
the existing no-bar ABSTAIN and does not mint physical scale.

## Required proof

First reproduce growth across real producer-owned derived generations. Check
the write and historical-read bounds, compare historical defensive reads with
their independently retained immutable inventories, and reject a replaced
snapshot omitting an otherwise present record. Run source/cache/lineage,
originalF07, archived Lot16eight and existingQ5446 retention, final dual-Python
CI, and one unchanged-budget original role replay. No memory-resolution,
customer/Maryboroughthree-retention or official4/4 claim before those results.

The derived-generation bound test failed before the fix (12 retained sets).
The fixed code passes86 focused source/history/hash/defensive-copy/scoped/
visibility tests, including historical reads after eviction and rejection of
a replaced snapshot inventory that omits a still-stored record. Original
composition measurement and release checks remain separate.

The same private original composition observer reached snapshot60 with435,370
stored observations on both versions. Membership hints fell from60 sets /
1,006,645,920 bytes to3 sets /50,332,296 bytes. At that matched stage observed
peak RSS fell from3,142,300KiB to2,293,428KiB (about27%). Native/text receipt
counts and stored observation counts were identical. The candidate stayed
below the diagnostic3GiB guard through snapshot62, then reached its180s
diagnostic timeout. This demonstrates reduced allocation, not completed
composition, source/customer success or resolution of the whole-role5GiB gate.
