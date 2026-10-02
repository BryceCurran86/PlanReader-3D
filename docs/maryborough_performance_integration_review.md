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
