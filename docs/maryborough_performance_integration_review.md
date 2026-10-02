# Maryborough and performance integration review

## Observed repository behavior

The isolated integration starts from current main `b4c71c22`, whose tree
equals tested #1140 head `463458b3`. #1140 final CI passed 7,299 tests on
Python 3.13 and 3.14, with 55 skipped and 13 expected failures on each.
The exact private-source runtime is still being independently completed;
the merge into main does not establish that source gate.

Performance PR #1197 is inspected at `62485426`. Its CI stopped at Ruff:
`Sequence` is used without an import in `pb_physical_opening_authority.py`.
Its default `collect_item35_shadow=False` changes normal-upload diagnostics;
the existing default-behavior tests were changed to explicitly opt in.

The opening path is `SourceVisibilityProducer.physical_opening_authority`
-> `PhysicalOpeningAuthority.prove_existence` / `classify_disposition` /
`visible_candidate_structures` -> `SourceVisibilityAuthority.resolve_visible`
-> `SourceObservationAuthority.resolve`. The latter already verifies current
revision, bytes, membership and producer fingerprints. #1197 introduces
result caches ahead of those checks. `PhysicalScaleProducer.publish_scope`
likewise returns a cached attempt before its existing `_revision_inputs`
current-revision and byte-hash checks. The caches must not bypass these seams.

No benchmark/golden, scorer or V2 truth changes occur in the reviewed 32-file
performance diff. Source-neutral decoding, immutable contract hashing,
geometry broad phases and lineage copying are being checked against the
existing synthetic invariance and fail-closed tests, rather than room targets.
The inherited #1195 viewport fix and #1196 customer-source scope must survive.

## Inference and proposed narrow fixes

Reusing an authority after another revision is ingested can make a cached
positive outlive its source. Focused stale-revision and source-replacement
regressions will establish whether this occurs. The small integration fixes
are to import `Sequence`, retain the normal shadow default and its existing
behavior tests, and perform the original source guards before reusing cached
opening/scale outcomes. Candidate discovery and geometry caches remain scoped
to their exact snapshot. No room architecture is redesigned.

## Source review and validation boundaries

The pinned Maryborough PDF is read independently of its diagnostic report.
Food Prep's requested 4025 x 3297 mm / 13.270425 square metre control and
Dry Store's abstention are validation assertions, never prediction inputs.
Cold Room and Freezer evidence must use the same physical faces on both
routes; a panel-thickness difference cannot be dismissed as scoring tolerance.
Previously source-closed rooms are not removed from the project census.

The source-only ledger does not prove canonical identity or customer output.
Normal extractor -> typed authority -> canonical object -> verified quantity
-> takeoff contract -> database/output must be exercised before claiming parity.
Major room authority/publication failures are reported for the owner's design
review; only isolated integration defects are repaired here.

The old canonical-five percentage runner is explicitly retired in current
`docs/planreader_public_tender_benchmarks.md`. Active V2 validation uses four
registered sources. No old benchmark is restored, and no V2 truth, scoring,
acceptance rule, costing or VR UI is changed by this integration.

## Commit boundaries

The performance author's immutable head remains untouched. Integration is in
its own worktree, with the imported head and each local fix recorded. #1140
and its authority correction are already on main. Anti Gravity's attached
report is diagnostic evidence only; unsupported room closure or title-block
scale conversions are not copied into production.

## Focused proof

Ten stale-revision/source-replacement regressions pass against current main,
fail against the original #1197 caches, and pass after moving the existing
authority guards ahead of cache reuse. No geometry or quantity value is changed
to satisfy them. The actual combined focused pytest run passes 585 tests in
10.13 seconds, covering hatch/dimensions, topology/lineage, wall equivalence,
text integrity, source caches, schedule/opening dimensions, physical scale,
contracts, default Item 35 collection, AG-09 coverage and room-face extraction.
Ruff F821/F823, diff checks, V2 integrity/separation and provider isolation pass.

The concurrent phrase-first room-label branch is identified at `11dd6f51`.
Only its two named commits `d009d573` and `11dd6f51` are selected: they change
the room-label module and its tests. The branch's older parent history carries
other foundation, viewer and benchmark changes; that history is not imported
wholesale. Its full room-face pytest suite is run in a separate worktree before
the two commits enter this integration. Source-only labels still cannot supply
missing physical boundaries, scale, dimensions or customer quantity authority.

The branch's real focused suite initially fails 16 tests with a missing `math`
import. Adding that import makes all 107 room-face tests pass. The two label
commits and the import correction are cherry-picked separately, without the
branch's unrelated parent history. Combined room/customer/coverage/performance
checks expose an existing authenticated viewport being lost through the new
candidate membership cache. That cache must be reused only for the exact
candidate tuple from which it was built; alternate authenticated projections
must build their own membership. The unchanged viewport regression passes after
that correction, and all 222 combined focused tests pass in 4.02 seconds.

## Real-source performance observation

The normal extractor on the pinned, unchanged Maryborough PDF, selecting A140,
reaches Item 35 at 11.37 seconds. Repeated one-minute stack snapshots then show
`_exact_fill_stroke_overprint_pair` calling `page.get_bboxlog()` for individual
words during full-source visibility ingestion. This helper reconstructs the
paint log even though `_visibility_status` already uses `_cached_bboxlog`.
The run is interrupted after recording that bottleneck; no completed source or
customer parity result is claimed from it.

The narrow proposed change is to call the existing `_cached_bboxlog` from the
overprint proof too. Both consumers read the same immutable page paint state;
the consecutive sequence numbers, exact character/font/layer identity and
complementary rendering predicates remain unchanged. The existing exception
handler still abstains if the log cannot be read. This is not a new authority
cache, metric conversion or room-closure rule. Repeated authentication, separate
pages and unavailable-paint-log cases must establish equivalent decisions before
the private-source run is repeated.

The real synthetic-PDF regression first reads the paint log five times while
authenticating and replaying native overprinted words. With the existing cache,
it reads once and returns identical trusted decisions. Separate-page mismatches
and missing paint logs still abstain. All 94 focused text-integrity/occlusion/
overprint tests pass in 0.94 seconds. No source-dependent threshold is added.

Full CI at published head `528b1439` exposes one stale instrumentation test:
`test_wall_candidate_producer_constructs_one_opening_authority_per_revision`
patches the wall-module constructor alias. #1197 deliberately moved authority
ownership to `SourceVisibilityProducer.physical_opening_authority`, so that
alias is no longer the live constructor. Count the actual class constructor
instead; keep the one-construction assertion and all scope-equivalence tests.
The Python 3.14 run otherwise passes 7,331 tests with 55 skipped/13 xfailed.

The A140 normal extractor completes at 340.07 seconds with 3,827.01 MiB peak RSS
and no predictions. Canonical rooms abstain with
`live_canonical_room_composition_unavailable` and
`source_room_face_scope_unavailable`; floor surfaces are unavailable. This is a
failed room gate, not successful source closure or customer publication.

The first local customer probe used the intermediate v1.3.5 launcher and is
interrupted without a publication claim. The deployed v1.5.1 entry point is
`pb_planreader_v133_app`; the probe is repeated through its entire normal startup
chain. The intermediate run's repeated stack snapshots nevertheless identify
an isolated allocation defect: `extract_and_calibrate_rooms` rebuilds every raw
polygon for every face before `filter_face` can reject tiny/unmeasured faces.
Its precomputed polygon tuple list is unused. Precompute the exact raw polygon
list once and pass the same read-only values to each existing filter invocation.
Do not reuse the rounded identity tuples as metric geometry. No face extraction,
filter predicate, calibration, label ownership, status or quantity rule changes.

The 2,500-face source-neutral allocation probe takes 1.077 seconds before this
change and 0.024 seconds after it; all unmeasured loops still return no rooms.
The deployed v1.5.1 customer run also reaches the same repeated polygon-list
construction in multiple one-minute stack snapshots. It is interrupted before
publication and repeated after the exact-value allocation fix. This probe is
not a substitute for the repository performance gates or real-source parity.
