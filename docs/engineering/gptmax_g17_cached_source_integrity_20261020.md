# G17 cached physical proofs require current original source

Depends on source receipt registration #3399. New regression first failed on
the parent: after warming a real generated-raster opening proof, removing or
damaging another supporting source receipt still returned CORROBORATED for the
untouched seed. This violates the existing all-original-inventory failure gate.

## Observed path and implementation

`prove_existence` reauthenticated the selected raster primitive but
`_prove_raster_framed_existence` then returned its cached physical proof before
checking other original supports. `_raster_primitive_snapshot_records` also
returned cached source records without checking their producer inputs.

The inventory cache now retains identity-bound source inputs: actual published
inventory, revision, snapshot, immutable bytes, original observation/fingerprint
table views, and every raster-opening receipt object. A changed receipt or any
table write invalidates all dependent positive and negative snapshot caches.
The source inventory is reauthenticated before any cached physical proof.
An interrupted read is a conflict and does not poison future repaired-source
proofs. Healthy immutable sources still reuse detection and full-inventory
authentication; a replaced plain mapping falls back to fresh scalar readers.

No caller input becomes a source token. No native/raster namespace transfer,
wall role, host, frame, metric, count, customer publication or score is granted.
Uses the original statuses and original geometry/IDs. The existing raster cap,
W2 snap, W10 and frozen benchmark are untouched.

## Proof

- Nonseed missing receipt, changed render/pixels, missing parent/fingerprint,
  other-page source damage, restored-source recovery, mid-read changes and
  healthy detection reuse have executable generated-PDF coverage.
- The initial combined targeted matrix passed 213 cases; the two additional
  transaction/fallback regressions and final failure-path repair were then
  verified separately. Exact-current-head CI is a separate required result.
- Fresh original Lot16 p3 complete report equals the pre-change main report:
  21 physical objects /15 hosts /9 frames /8 areas, exact old producer bodies
  and original snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.
  Source SHA is
  `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
- Canonical JSON SHA-256 of the entire production receipt bundle remains
  `1b4d56abd1c8f2c06e072524f8e7b052b22f084f2a1db05a41fd7a4e43fc8a99`.
- Final-code actual production claim, customer projection and opening-area
  seal were independently replayed from the original PDF. Every archived
  customer row and the complete archived signed run are equal, with historical
  fingerprint `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
- Maryborough original p7 source replay has 55,066 native visible observations,
  zero raster-opening receipts and unchanged ingestion snapshot under original
  SHA `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.
  This is source-path parity, not a full Maryborough customer replay.

New CI covers both main-target PRs and this explicit stacked parent, preserves
the main entry, and never uploads client source PDFs. Public synthetic and
archived-body tests are not a replacement for the private-original run.
Required authority review and owner approval remain open. No accuracy increase
is claimed, and test/check counts are not engineering-development counts.
