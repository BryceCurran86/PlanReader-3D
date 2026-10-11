# Original historical seal regression fixture

Observed: original `seal_source_closed_run` now calls `_build_sealed_run` with
the strict partially overlapping physical identity guard merged in #2394.
`test_historically_signed_partially_overlapping_physical_claims_not_exportable`
tries to produce its historical example through that current producer before
calling `export_verified_produced_items`. The fixture fails at construction,
so the intended import/export regression never runs. This independently fails
on unchanged main `6b7908c`, in addition to the separate W21 schedule issue.

Proposed: retain a real serialized V1 run produced by the actual preceding
repository implementation at `0db404e737c2e33d31af48c128eec127f1d27e73`.
The source bytes, quantities and source traces are exactly those in the existing
synthetic test. No fingerprint, signing function or source authority is forged
or bypassed. Replay this fixture through the current exporter, whose
`load_verified_sealed_run` calls the current `_build_sealed_run` and must reject
overlap. Separately assert that the current producer cannot create that run.
Keep existing disjoint-object and separate-family positives.

This is a test-fixture repair, not a change to production authority. A valid
old fingerprint cannot override the current source-identity overlap guard.
Current seal producer, verified loader, exporter, original PDFs, source
quantities, frozen V2 and the 20,000 input bound stay untouched. No benchmark
or physical host improvement is claimed.

Fixture SHA256: `4c23815d72ee99cccf19f491618c79c5d12dab683125bd939f140bb135f65121`.
Original synthetic source SHA256:
`3c8def5c21b869a8322a68a9287921a4d17f82c619773fc15ca25eb138fcc343`.
94 focused exporter and source-closed seal regression tests pass, including
current-producer rejection and historical-import rejection with no output.
