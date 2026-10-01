# GPT-01 / GPT-02 production coverage trace

Base: current `origin/main`, `e95ef8489f3a0b7c024fb99dc5e48fed887ee40b`.

## Observed repository behaviour

Read `AGENTS.md`, `AI_ENGINEERING_PLAYBOOK.md`, the topology architecture/spec,
the retired-public-tender notice, CI, the registry and runtime adapters, the
canonical projections, and the live/customer wall composition.

* `pb_auto_geometry_v1219._runtime_coverage_registry_summaries` accepts typed
  registries attached to the app/extractor. No live canonical producer currently
  attaches them. `build_runtime_coverage_publication` reports aggregate stages,
  without a census of the nine mature family paths.
* `collect_live_physical_net_wall_claim` already owns typed canonical walls,
  openings, rooms and floor footprints, and the actual external wall
  `QuantityEvidence` in `claim.publication`. A canonical wall candidate with
  `physical_identity_resolved=False` is not an authenticated physical wall.
* `GenericPlanReaderExtractor.extract_from_pdf` retains canonical objects but
  serializes structural coverage to a diagnostic dictionary; the live runtime
  consumer requires `CoverageRegistrySummaryV1`, not that dictionary.
* Canonical door/window payloads are filtered physical-opening objects. They
  do not establish separate filling identities. Room-owned floor footprints
  have `physical_floor_surface_identity_resolved=False`. Ceiling, slab and roof
  projections do not carry the complete document/revision/hash/snapshot lineage
  required by the registry. Finish-surface projection exists but has no live
  extractor caller. These are explicit gaps, not measured zero-object universes.
* `_try_physical_net_wall_rows` resolves workspace PDFs, but returns immediately
  after the first corroborated claim. A later source-proven PDF is therefore
  dropped before customer publication. This is the first GPT-02 target.

## Inference

Canonical presence does not establish physical admission, quantity authority,
or customer publication. Registry scope availability is also different from a
fully connected family path. The multi-PDF early return is a production bridge
defect; it requires no new extraction or authority promotion to repair.

## Proposed narrow changes

1. Publish an explicit nine-family path census from supplied typed registries:
   CONNECTED, PARTIAL, UNAVAILABLE, WRONG / DUPLICATE PATH. Unsupported family
   counts are null. Missing, conflicting and duplicate paths remain visible;
   family completeness remains UNKNOWN.
2. Reissue source-owned typed canonical objects into the existing registry
   contracts, grouped by exact document/revision/hash/snapshot lineage. Admit
   only resolved physical identities, preserve canonical IDs as exact links,
   consume original QuantityEvidence without generating new quantities, and
   leave lineage-incomplete families unavailable.
3. Attach those typed summaries at the live extractor and customer wall bridge.
   Customer row snapshots describe rows actually built by the existing writer;
   PUBLISHED still requires the same-transaction SQLite row. No row reconstructed
   from a registry and no guessed quantity-to-object link.
4. GPT-02 separately accumulates all selected, corroborated document claims;
   unselected documents, duplicates, abstention and reruns get focused tests.
5. Quantity IDs remain in the audit even when abstained or conflicting, but
   those dependencies cannot advance QUANTIFIED or PUBLISHED. Valid aggregate
   quantities require no invented per-object allocation. Live snapshots retain
   the original quantity value, status and unit for customer-row verification.

## Verification handoff

The earlier draft passed 38 focused tests before these final dependency guards.
That result does not validate the current head. The user assigned test execution,
CI review and merging to normal GPT. Syntax compilation and `git diff --check`
are performed here; the final head needs focused tests, relevant wider regression
and repository CI before promotion from draft. Do not run retired benchmarks.

## CI correction trace

Observed: the structural diagnostic quantity uses the existing
`AuthorityStatus.FIRM`, while wall publication uses
`EvidenceResolutionStatus.CORROBORATED`. The coverage adapter incorrectly
accepted only the latter. Accept those exact established verified statuses;
provisional, review, blocked, abstained and unknown dependencies remain refused.

Observed: the extractor newly called the structural diagnostic quantity builder
directly, violating its existing shadow-only import boundary and calculating the
same diagnostic result twice. Preserve that boundary by capturing the original
typed QuantityEvidence from the existing shadow collector through an optional
diagnostic sink; predictions and serialized shadow payloads remain unchanged.

Observed: `PhysicalOpeningAuthority.prove_existence` includes a proven candidate
viewport in its identity payload, but sets the resulting existence record's
viewport to None. Preserve the candidate's exact viewport id, including None for
page-scoped candidates. Do not invent a viewport, change admission or combine
cross-viewport evidence. This defect also exists in the fetched main source.

## Authority boundaries and expected abstentions

Source authority -> typed canonical producer -> read-only registry -> exact
quantity dependencies -> existing takeoff row -> transaction-backed lifecycle.
Candidate walls, projected-but-unproven floor identities, missing lineage,
unknown filling identity, conflicting evidence and orphan quantities cannot be
promoted. The registry does not discover geometry or finish extent.

V2 truth, scoring and sealed holdouts are untouched. No retired benchmark is
run, compared or used as production truth. No UI, costing, new topology or W10
authority flags change. Production tests use synthetic source documents and
existing authority contracts.
